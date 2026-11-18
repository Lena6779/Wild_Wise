"""Settings for Wild Wise, read from environment variables with default values as stated by the environment variable names."""
import os


class Settings:
    """Application settings loaded from environment variables"""

    # Ollama config
    OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    MODEL_NAME: str = os.environ.get("MODEL_NAME", "llama3.2:1b")

    # ChromaDB config
    CHROMA_PATH: str = os.environ.get("CHROMA_PATH", "./chroma_data")
    COLLECTION_NAME: str = os.environ.get("COLLECTION_NAME", "animals")

    # RAG config
    MAX_RESULTS: int = int(os.environ.get("MAX_RESULTS", "3"))
    LOW_CONFIDENCE_THRESHOLD: float = float(os.environ.get("LOW_CONFIDENCE_THRESHOLD", "0.7"))
    HIGH_CONFIDENCE_THRESHOLD: float = float(os.environ.get("HIGH_CONFIDENCE_THRESHOLD", "0.3"))
    MEDIUM_CONFIDENCE_THRESHOLD: float = float(os.environ.get("MEDIUM_CONFIDENCE_THRESHOLD", "0.6"))

    # Application settings
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"
    DOCS_DIRECTORY: str = os.environ.get("DOCS_DIRECTORY", "./docs")
    AUTO_INGEST: bool = os.environ.get("AUTO_INGEST", "true").lower() == "true"

    # Database config
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./wildwise.db")

    # JWT login config
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "change-me")
    JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


settings = Settings()

# Print configuration on startup (useful for debugging)
if settings.DEBUG:
    print("=== Configuration ===")
    print(f"  Ollama URL: {settings.OLLAMA_URL}")
    print(f"  Model: {settings.MODEL_NAME}")
    print(f"  Database URL: {settings.DATABASE_URL}")
    print(f"  ChromaDB: {settings.CHROMA_PATH}")
    print(f"  Collection: {settings.COLLECTION_NAME}")
    print(f"  Max Results: {settings.MAX_RESULTS}")
    print(f"  Low Threshold: {settings.LOW_CONFIDENCE_THRESHOLD}")
    print(f"  Medium Threshold: {settings.MEDIUM_CONFIDENCE_THRESHOLD}")
    print(f"  High Threshold: {settings.HIGH_CONFIDENCE_THRESHOLD}")
    print(f"  Docs: {settings.DOCS_DIRECTORY}")
    print(f"  Debug: {settings.DEBUG}")


