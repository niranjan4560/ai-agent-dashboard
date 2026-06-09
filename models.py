from sqlalchemy import (Column,Integer,Text,DateTime,Boolean,String,ForeignKey)
from sqlalchemy.sql import func
from datetime import datetime
from database import Base



class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    username = Column(
        String(100),
        unique=True
    )

    email = Column(
        String(200),
        unique=True
    )

    password_hash = Column(
        String(255)
    )


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    user_message = Column(
        Text
    )

    ai_response = Column(
        Text
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class Todo(Base):
    __tablename__ = "todos"
 
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    text       = Column(String(500), nullable=False)
    priority   = Column(String(10), default="medium")   # low | medium | high
    done       = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())