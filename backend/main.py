"""Wild Wise API: login, questions, and chat history endpoints."""

from contextlib import asynccontextmanager

import requests
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from auth import create_access_token, hash_password, verify_password
from config import settings
from database import get_db, init_db
from models import User
from rag import get_collection
from schemas import HealthResponse, RootResponse, Token, UserCreate, UserOut


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the database tables when the app starts."""
    init_db()
    yield  # This is where the app runs, after this point the app is shutting down


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
    # Check Ollama connection
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
        raise HTTPException(status_code=400, detail="Username already registered")
    new_user = User(
        username=user_create.username,
        hashed_password=hash_password(user_create.password),
    )
    db.add(new_user)
    db.flush()
    return new_user


@app.post("/auth/token", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Login with a username and password, returning a JWT token if successful."""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(access_token=create_access_token(user.username))
