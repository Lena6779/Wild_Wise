"""Pydantic models that validate every request and response."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# --- Shared Types: allowed values reused across multiple schemas ---
AnimalClass = Literal[
    "mammal", "bird", "reptile", "amphibian", "fish", "insect", "arachnid", "worm"
]

Confidence = Literal[
    "low",
    "medium",
    "high",
    "none",
]


# --- Authentication Schemas: user creation, login, and the current user ---
class UserCreate(BaseModel):
    """Request body for POST /auth/register."""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(
        min_length=8, max_length=72
    )  # bcrypt only allows passwords up to 72 bytes, anything over will be rejected and raise an error


class UserOut(BaseModel):
    """User returned by the API, without the password."""

    model_config = ConfigDict(
        from_attributes=True
    )  # Configure Pydantic to read from ORM attributes

    id: int
    username: str


class Token(BaseModel):
    """Response for POST /auth/token."""

    access_token: str
    token_type: str = "bearer"


# --- Asking Questions Schemas: question, answer, and sources ---
class Source(BaseModel):
    """One cited chunk in an answer."""

    animal: str
    animal_class: AnimalClass
    source_url: str
    chunk_index: int
    distance: float


class AskRequest(BaseModel):
    """Request body for POST /ask."""

    question: str = Field(min_length=1, max_length=500)
    animal_class: AnimalClass | None = None  # Optional filter for the animal class


class AskResponse(BaseModel):
    """Response for POST /ask."""

    answer: str
    confidence: Confidence
    sources: list[Source]


# --- Chat History Schemas: conversation and delete responses ---
class ConversationOut(BaseModel):
    """One saved conversation for GET /conversations."""

    model_config = ConfigDict(
        from_attributes=True
    )  # Configure Pydantic to read from ORM attributes

    id: int
    created_at: datetime
    question: str
    answer: str
    confidence: Confidence


class DeleteResponse(BaseModel):
    """Response for DELETE /conversations."""

    message: str


# --- App Status Schemas: root, stats, and health responses ---
class RootResponse(BaseModel):
    """Response for GET /."""

    message: str
    model: str


class StatsResponse(BaseModel):
    """Response for GET /stats."""

    animal_count: int
    chunk_count: int
    animals: list[str]


class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: str
    ollama: Literal["connected", "unavailable"]
    chunks: int


# --- Ingest Schemas: ingest response ---
class IngestResponse(BaseModel):
    """Response for POST /ingest."""

    files: list[str]
    chunks: int
    message: str

