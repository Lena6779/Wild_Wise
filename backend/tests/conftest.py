"""Shared test setup: a test database, a test client, and a logged-in test user."""

import os

import pytest

# Point the app at test settings BEFORE it's imported
os.environ["DATABASE_URL"] = "sqlite:///./test_wildwise.db"
os.environ["CHROMA_PATH"] = "./test_chroma"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-at-least-32-characters-long"

from fastapi.testclient import TestClient  # noqa: E402

from database import engine  # noqa: E402
from main import app  # noqa: E402
from models import Base  # noqa: E402


@pytest.fixture
def client():
    """A test client with fresh, empty tables for each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    """Register and log in a test user, and return the login header."""
    response = client.post(
        "/auth/register",
        json={"username": "testuser", "password": "testpassword"},
    )
    assert response.status_code == 201

    response = client.post(
        "/auth/token",
        data={"username": "testuser", "password": "testpassword"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
