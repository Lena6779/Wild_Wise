"""API tests for Wild Wise."""

import main
from rag import find_animal_class

# A fake search result, so tests do not need ChromaDB or Ollama
ALLIGATOR_RESULT = {
    "text": "Diet: American alligators are carnivores.",
    "distance": 0.24,
    "animal": "American Alligator",
    "animal_class": "reptile",
    "source_url": "https://www.nps.gov/ever/learn/nature/alligator.htm",
    "chunk_index": 2,
    "file_name": "american_alligator.txt",
}


def test_root(client):
    """GET / says welcome and names the model."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome" in response.json()["message"]


def test_register_and_duplicate(client):
    """A new user gets 201, and the same username again gets 400."""
    user = {"username": "lena", "password": "Password123"}
    response = client.post("/auth/register", json=user)
    assert response.status_code == 201
    assert response.json()["username"] == "lena"
    assert "password" not in response.json()

    response = client.post("/auth/register", json=user)
    assert response.status_code == 400


def test_login_wrong_password(client, auth_headers):
    """A wrong password gets 401."""
    response = client.post(
        "/auth/token",
        data={"username": "testuser", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_ask_requires_login(client):
    """Asking without a token gets 401."""
    response = client.post("/ask", json={"question": "What do alligators eat?"})
    assert response.status_code == 401


def test_ask_off_topic_skips_model(client, auth_headers, monkeypatch):
    """A far-off match returns the fallback reply without calling the model."""
    far_result = {**ALLIGATOR_RESULT, "distance": 0.89}
    monkeypatch.setattr(
        main, "search", lambda question, animal_class=None: [far_result]
    )

    def model_should_not_run(question, results):
        raise AssertionError("The model should not be called")

    monkeypatch.setattr(main, "ask_ollama", model_should_not_run)

    response = client.post(
        "/ask",
        json={"question": "What is the capital of France?"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["confidence"] == "none"
    assert response.json()["sources"] == []
