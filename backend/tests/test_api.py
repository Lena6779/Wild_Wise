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


def test_health(client):
    """GET /health returns 200 with the Ollama status and chunk count."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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


def test_invalid_data_returns_422(client, auth_headers):
    """A short password or an unknown animal class gets 422."""
    response = client.post(
        "/auth/register", json={"username": "kid", "password": "short"}
    )
    assert response.status_code == 422

    response = client.post(
        "/ask",
        json={"question": "Hi", "animal_class": "dinosaur"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_change_password(client, auth_headers):
    """A user can update their password, and only the new one works after."""
    new = {"current_password": "wrongpassword", "new_password": "newpassword123"}
    response = client.put("/auth/me/password", json=new, headers=auth_headers)
    assert response.status_code == 400

    new["current_password"] = "testpassword"
    response = client.put("/auth/me/password", json=new, headers=auth_headers)
    assert response.status_code == 200

    old_login = {"username": "testuser", "password": "testpassword"}
    assert client.post("/auth/token", data=old_login).status_code == 401
    new_login = {"username": "testuser", "password": "newpassword123"}
    assert client.post("/auth/token", data=new_login).status_code == 200


def test_ask_off_topic_skips_model(client, auth_headers, monkeypatch):
    """A far-off match returns the fallback reply without calling the model."""
    far_result = {**ALLIGATOR_RESULT, "distance": 0.89}
    # Patch main's copy, since main.py did "from rag import search"
    monkeypatch.setattr(
        main, "search", lambda question, animal_class=None: [far_result]
    )

    # A fake model that fails the test if it's ever called
    def model_should_not_run(question, results):
        """Fail the test if the model is called."""
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


def test_find_animal_class_earthworm():
    """'A worm, not an insect' is labeled worm."""
    assert find_animal_class("The earthworm is a worm, not an insect.") == "worm"


def test_ask_saves_conversation(client, auth_headers, monkeypatch):
    """A good match gets an answer with sources, is saved, and can be deleted."""
    monkeypatch.setattr(
        main, "search", lambda question, animal_class=None: [ALLIGATOR_RESULT]
    )
    monkeypatch.setattr(
        main, "ask_ollama", lambda question, results: "Alligators eat fish."
    )

    response = client.post(
        "/ask", json={"question": "What do alligators eat?"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["confidence"] == "high"
    assert response.json()["answer"] == "Alligators eat fish."
    assert len(response.json()["sources"]) == 1
    assert response.json()["sources"][0]["animal"] == "American Alligator"

    history = client.get("/conversations", headers=auth_headers).json()
    assert len(history) == 1
    assert history[0]["question"] == "What do alligators eat?"

    # The user can delete their own conversation
    response = client.delete(
        f"/conversations/{history[0]['id']}", headers=auth_headers
    )
    assert response.status_code == 200
    assert client.get("/conversations", headers=auth_headers).json() == []


def test_cannot_delete_other_users_conversation(client, auth_headers, monkeypatch):
    """Another user gets 404 when trying to delete someone else's conversation."""
    # Testuser asks a question
    monkeypatch.setattr(
        main, "search", lambda question, animal_class=None: [ALLIGATOR_RESULT]
    )
    monkeypatch.setattr(
        main, "ask_ollama", lambda question, results: "Alligators eat fish."
    )
    client.post(
        "/ask", json={"question": "What do alligators eat?"}, headers=auth_headers
    )
    conversation_id = client.get("/conversations", headers=auth_headers).json()[0]["id"]
    # A second user logs in
    other = {"username": "other", "password": "otherpassword"}
    client.post("/auth/register", json=other)
    token = client.post("/auth/token", data=other).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {token}"}
    # The second user can't delete testuser's conversation
    response = client.delete(f"/conversations/{conversation_id}", headers=other_headers)
    assert response.status_code == 404
