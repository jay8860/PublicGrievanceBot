"""Database layer for the grievance platform.

Defaults to a local SQLite file so development/tests need no infrastructure;
set ``DATABASE_URL`` (PostgreSQL) in production.  Railway/Heroku hand out
``postgres://`` URLs, which SQLAlchemy 2 no longer understands - normalised
below.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

def _normalise(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


DATABASE_URL = _normalise(os.getenv("DATABASE_URL", "").strip() or "sqlite:///./grievance.db")

_connect_args = ({"check_same_thread": False, "timeout": 30}
                 if DATABASE_URL.startswith("sqlite") else {})

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True, connect_args=_connect_args)

if DATABASE_URL.startswith("sqlite"):
    # On a Railway volume the API and the Telegram bot write the same SQLite
    # file from one container. WAL lets readers run while a write is in flight
    # and the busy timeout makes a concurrent write wait instead of failing
    # with "database is locked".
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
        finally:
            cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_session():
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables if they do not exist (no destructive migration)."""
    from . import models  # noqa: F401  (registers the mappers)

    Base.metadata.create_all(bind=engine)
    return DATABASE_URL
