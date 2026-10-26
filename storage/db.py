"""Sync SQLAlchemy engine/session, used by Alembic and any direct DB access."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv is already in project deps
    pass

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://unblock:unblock@localhost:5433/unblock"
)

# SQLAlchemy needs an explicit driver name; psycopg[binary] in requirements.txt is psycopg3.
_SQLALCHEMY_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(_SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI-style dependency: yields a session, closes it when the caller is done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
