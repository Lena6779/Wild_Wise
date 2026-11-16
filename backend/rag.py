"""Load fact sheets, store chunks in ChromaDB, and answer questions from them."""

import re
from pathlib import Path

import chromadb
import requests

from config import settings

# Must match AnimalClass in schemas.py
ANIMAL_CLASSES = [
    "mammal",
    "bird",
    "reptile",
    "amphibian",
    "fish",
    "insect",
    "arachnid",
    "worm",
]


def find_animal_class(text: str) -> str:
    """Return the animal class word that appears first in the text."""
    text = text.lower()
    # Pick the earliest word so "a worm, not an insect" returns "worm"
    found = [(text.find(word), word) for word in ANIMAL_CLASSES if word in text]
    if not found:
        raise ValueError("No animal class found in text")
    return min(found)[1]


def load_fact_sheet(path: str) -> dict:
    """Read one fact sheet and return its name, class, sources, and facts."""
    text = Path(path).read_text(encoding="utf-8")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    # Layout: animal name, source URLs, then fact chunks
    animal = paragraphs[0]
    urls = [url.rstrip(".,") for url in re.findall(r"https?://\S+", paragraphs[1])]
    chunks = paragraphs[2:]
    animal_class = find_animal_class(chunks[0])

    return {
        "animal": animal,
        "animal_class": animal_class,
        "source_url": ", ".join(urls),
        "chunks": chunks,
    }


def get_collection():
    """Open the ChromaDB collection of animal fact sheet chunks."""
    # Saves to disk so chunks survive restarts
    client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
    return client.get_or_create_collection(
        name=settings.COLLECTION_NAME,
        # Cosine distance: 0 = same meaning, bigger = less similar
        metadata={"hnsw:space": "cosine"},
    )


def ingest_docs() -> list[dict]:
    """Load every fact sheet into ChromaDB and return the fact sheet data."""
    collection = get_collection()
    fact_sheets = []
    # finds every file ending in .txt
    for path in sorted(Path(settings.DOCS_DIRECTORY).glob("*.txt")):
        sheet = load_fact_sheet(path)
        sheet["file_name"] = path.name
        fact_sheets.append(sheet)

        collection.upsert(
            # path.stem is the filename without the extension
            ids=[f"{path.stem}_{i}" for i in range(len(sheet["chunks"]))],
            documents=sheet["chunks"],
            metadatas=[
                {
                    "animal": sheet["animal"],
                    "animal_class": sheet["animal_class"],
                    "source_url": sheet["source_url"],
                    "file_name": sheet["file_name"],
                    "chunk_index": i,
                }
                for i in range(len(sheet["chunks"]))
            ],
        )
    return fact_sheets


def search(question: str, animal_class: str | None = None) -> list[dict]:
    """Find the chunks closest in meaning to the question."""
    collection = get_collection()
    # Only search one animal class if the user picked one
    where = {"animal_class": animal_class} if animal_class else None
    results = collection.query(
        query_texts=[question],
        n_results=settings.MAX_RESULTS,
        where=where,
    )
    # Chroma returns one list per question, and we sent one, so use index 0
    return [
        {"text": text, "distance": distance, **metadata}
        for text, distance, metadata in zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0],
            strict=True,  # Ensure that the lengths of documents, distances, and metadatas match exactly
        )
    ]


def get_confidence(results: list[dict]) -> str:
    """Estimate confidence from the closest chunk's cosine similarity."""
    if not results:
        return "none"
    best = results[0]["distance"]
    if best <= settings.HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if best <= settings.MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    if best <= settings.LOW_CONFIDENCE_THRESHOLD:
        return "low"
    return "none"


def ask_ollama(question: str, results: list[dict]) -> str:
    """Ask the Ollama model to answer the question using only the matching chunks."""
    context = "\n\n".join(result["text"] for result in results)

    prompt = (
        "You are Wild Wise, a friendly app companion who teaches people of all ages "
        "about wild animals. Use the facts below to answer the question in plain "
        "English. Answer directly, as if you already know these facts. "
        "Only include details that are in the facts. "
        "Keep it short and simple. "
        "If the facts are about a different topic, say you don't know.\n\n"
        f"Facts:\n{context}\n\n"
        f"Question: {question}\n"
        "Answer:"
    )

    response = requests.post(
        f"{settings.OLLAMA_URL}/api/generate",
        json={
            "model": settings.MODEL_NAME,
            "prompt": prompt,
            "stream": False,
        },
        # Stop waiting after 2 minutes, since the model can take a while to respond
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["response"].strip()
