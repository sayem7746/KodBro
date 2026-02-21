"""
SQLAlchemy database setup and models for Railway PostgreSQL.
"""
import os
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


def get_engine():
    """Create engine from DATABASE_URL. Uses sync driver for simplicity."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    # Railway PostgreSQL may use postgres:// - SQLAlchemy 2 prefers postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None


def get_db():
    """Dependency for FastAPI - yields a DB session."""
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL not set")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----- Models -----


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(Text, nullable=False)
    display_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tokens = relationship("UserToken", back_populates="user", cascade="all, delete-orphan")
    jobs = relationship("AppJob", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("AgentSession", back_populates="user", cascade="all, delete-orphan")


class UserToken(Base):
    __tablename__ = "user_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)  # github, vercel, railway
    encrypted_value = Column(LargeBinary, nullable=False)
    iv = Column(LargeBinary, nullable=False)
    team_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="tokens")


class AppJob(Base):
    __tablename__ = "app_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    app_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    prompt = Column(Text, nullable=True)
    status = Column(String(50), nullable=False)
    repo_url = Column(Text, nullable=True)
    deploy_url = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="jobs")


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_uuid = Column(String(36), unique=True, nullable=True, index=True)  # Links to in-memory session_id
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cursor_agent_id = Column(String(255), nullable=True)
    cursor_repo_url = Column(Text, nullable=True)
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="sessions")


def init_db():
    """Create all tables. Call at startup (after engine is ready)."""
    if engine is None:
        return
    Base.metadata.create_all(bind=engine)
