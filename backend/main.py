"""Wild Wise API: login, questions, and chat history endpoints."""

import json
from contextlib import asynccontextmanager

import requests
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user, hash_password, verify_password
from config import settings
from database import SessionLocal, get_db, init_db
from models import Animal, Conversation, User
from rag import ask_ollama, get_collection, get_confidence, ingest_docs, search
from schemas import (
    AskRequest,
    AskResponse,
    ConversationOut,
    DeleteResponse,
    HealthResponse,
    IngestResponse,
    MessageResponse,
    PasswordUpdate,
    RootResponse,
    Source,
    StatsResponse,
    Token,
    UserCreate,
    UserOut,
)

# Reply for off-topic questions
NO_ANSWER = "I'm sorry, I don't have an answer for that. Please try asking a different question."


def save_animals(db: Session, fact_sheets: list[dict]) -> None:
    """Add each animal to the database, or update it if its already there."""
    for sheet in fact_sheets:
        animal = db.query(Animal).filter(Animal.name == sheet["animal"]).first()
        if not animal:
            animal = Animal(name=sheet["animal"])
            db.add(animal)
        animal.animal_class = sheet["animal_class"]
        animal.file_name = sheet["file_name"]
        animal.source_url = sheet["source_url"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the database tables, and load the fact sheets if ChromaDB is empty."""
    init_db()
    # First start on a new computer: load the animals automatically
    if settings.AUTO_INGEST and get_collection().count() == 0:
        # If loading fails (for example, offline on the first start), still start
        # the app, so POST /ingest can be run later
        try:
            fact_sheets = ingest_docs()
            with SessionLocal() as db:
                save_animals(db, fact_sheets)
                db.commit()
        except Exception as error:
            print(f"Warning: could not load the fact sheets at startup: {error}")
    yield  # The app runs while paused here


app = FastAPI(
    title="Wild Wise API",
    description="An animal education RAG chatbot app, which answers general questions.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/", response_model=RootResponse)
def root():
    """Welcome message and the model in use."""
    return RootResponse(
        message="Welcome to the Wild Wise API! Ask me anything about wild animals within the context of the app.",
        model=settings.MODEL_NAME,
    )


@app.get("/health", response_model=HealthResponse)
def health():
    """Check the health of the API and its dependencies."""
    try:
        requests.get(f"{settings.OLLAMA_URL}/api/tags", timeout=5).raise_for_status()
        ollama_status = "connected"
    except requests.RequestException:
        ollama_status = "unavailable"
    return HealthResponse(
        status="ok", ollama=ollama_status, chunks=get_collection().count()
    )


@app.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(user_create: UserCreate, db: Session = Depends(get_db)):
    """Create a new user with hashed password."""
    if db.query(User).filter(User.username == user_create.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    new_user = User(
        username=user_create.username,
        hashed_password=hash_password(user_create.password),
    )
    db.add(new_user)
    # Save now so the new user gets an id for the response
    db.flush()
    return new_user


@app.post("/auth/token", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Log in with a username and password, returning a JWT token if successful."""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(access_token=create_access_token(user.username))


@app.get("/auth/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    """Return the logged-in user."""
    return current_user


@app.put("/auth/me/password", response_model=MessageResponse)
def change_password(
    passwords: PasswordUpdate,
    current_user: User = Depends(get_current_user),
):
    """Change the logged-in user's password."""
    # Ask for the current password too, so a stolen token can't lock the user out
    if not verify_password(passwords.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    # current_user came from get_db's session, which saves the change at the end
    current_user.hashed_password = hash_password(passwords.new_password)
    return MessageResponse(message="Password updated.")


@app.post("/ingest", response_model=IngestResponse)
def ingest(
    # Requiring a logged-in user protects this endpoint from being called by anyone, which could be a security risk.
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Load the fact sheets into ChromaDB and save each animal to the database."""
    fact_sheets = ingest_docs()
    save_animals(db, fact_sheets)

    return IngestResponse(
        files=[sheet["file_name"] for sheet in fact_sheets],
        chunks=get_collection().count(),
        message=f"Loaded {len(fact_sheets)} fact sheets into ChromaDB and saved to the database.",
    )


@app.get("/stats", response_model=StatsResponse)
def stats(db: Session = Depends(get_db)):
    """Return statistics about the database and ChromaDB."""
    names = [animal.name for animal in db.query(Animal).order_by(Animal.name)]
    return StatsResponse(
        animal_count=len(names),
        chunk_count=get_collection().count(),
        animals=names,
    )


@app.post("/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Answer a question about wild animals using the fact sheets."""
    results = search(request.question, request.animal_class)
    confidence = get_confidence(results)
    # Off-topic questions skip the model and show no sources
    if confidence == "none":
        answer = NO_ANSWER
        results = []
    else:
        try:
            answer = ask_ollama(request.question, results)
        except requests.RequestException:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ollama service is unavailable. Please try again later.",
            ) from None
    # Each result has the source fields; extra keys like "text" are ignored
    sources = [Source(**result) for result in results]

    conversation = Conversation(
        user_id=current_user.id,
        question=request.question,
        answer=answer,
        confidence=confidence,
        sources=json.dumps([source.model_dump() for source in sources]),
    )
    animal_names = {source.animal for source in sources}
    conversation.animals = db.query(Animal).filter(Animal.name.in_(animal_names)).all()
    db.add(conversation)
    return AskResponse(answer=answer, confidence=confidence, sources=sources)


@app.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the logged-in user's conversations, most recent first."""
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc(), Conversation.id.desc())
        .all()
    )


@app.delete("/conversations/{conversation_id}", response_model=DeleteResponse)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a specific conversation for the current user."""
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.user_id == current_user.id, Conversation.id == conversation_id
        )
        .first()
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found."
        )
    db.delete(conversation)
    return DeleteResponse(message="Conversation deleted.")
