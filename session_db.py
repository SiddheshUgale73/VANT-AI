from sqlalchemy import create_engine, Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid

Base = declarative_base()

class ChatSession(Base):
    """Represents a chat session containing multiple messages."""
    __tablename__ = 'sessions'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    """Represents an individual message within a chat session."""
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey('sessions.id'))
    role = Column(String) # 'user' or 'assistant'
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    session = relationship("ChatSession", back_populates="messages")

engine = create_engine('sqlite:///chat_history.db', connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency for providing a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
