"""SQLAlchemy models: users, conversations, animals, and the conversation-animal link table."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all Wild Wise models"""


class User(Base):
    """A Registered Wild Wise User"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan" # delete-orphan removes a user's conversations when the user is deleted from the app
    )


class Animal(Base):
    """A Wild Wise Animal"""
    __tablename__ = "animals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    animal_class: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        secondary="conversation_animals", # go through the link table to connect conversations to animals
        back_populates="animals",
    )


class Conversation(Base):
    """A Wild Wise Conversation"""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON list
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    animals: Mapped[list["Animal"]] = relationship(
        "Animal",
        secondary="conversation_animals",
        back_populates="conversations",
    )


class ConversationAnimal(Base):
    """The link between conversations and animals"""
    __tablename__ = "conversation_animals"

    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), primary_key=True)