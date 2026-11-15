"""Database setup: the SQLAlchemy engine, sessions, and table creation"""

from config import settings
from models import Base
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False}) # Allow SQLite connections from multiple threads


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Turn on SQLite foreign keys for each connection"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables if they don't exist yet"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Give each request its own database session, then close it"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception: # If there is an error, roll back the transaction
        db.rollback()
        raise # Re-raise the exception
    finally:
        db.close()
