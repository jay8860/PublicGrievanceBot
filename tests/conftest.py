"""Shared pytest fixtures: isolated SQLite database + no external calls."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Must be set BEFORE importing core.* / config (they read env at import time).
os.environ["DATABASE_URL"] = "sqlite:///./_test_grievance.db"
os.environ["TELEGRAM_BOT_TOKEN"] = ""          # notifications are logged as "skipped"
os.environ["OPENROUTER_API_KEY"] = ""          # AI calls fail closed -> manual review
os.environ["OPENROUTER_MODEL"] = "test/model"
os.environ["ENABLE_ESCALATION_SCHEDULER"] = "false"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"

import pytest  # noqa: E402

from core.db import Base, SessionLocal, engine  # noqa: E402
import core.models  # noqa: F401,E402  (register mappers)


@pytest.fixture()
def db():
    """Fresh schema + session per test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
