"""
conftest.py
===========
Root pytest configuration for the AI Study Companion backend.

Test database isolation
-----------------------
``app.db.session`` resolves ``DATABASE_URL`` exactly once, at import time, and
otherwise falls back to the development database (``backend/chatbot.db``).
Several tests drive the real application object (``TestClient(app)``) or use the
real ``SessionLocal`` factory, so without an override the suite registers its
fixture users (``iso_a_*``, ``test-user-*``, ``newuser_*``, ...) into real data.

To make that impossible, this module points ``DATABASE_URL`` at a disposable
file *before* any ``app.*`` module is imported, discards the previous run's file
and re-creates the schema. The development database is never opened by tests,
and a guard fails the session loudly if the isolation is ever bypassed.

Run the suite from ``backend/``: ``python -m pytest tests/``.
"""
import sys
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent

# --- Isolated test database -------------------------------------------------
# This must stay above every `app.*` import: `app.db.session` (and anything that
# imports it, like `app.main`) reads the environment variable on first import.
# `app.main` loads `backend/.env` with override enabled, but that file defines no
# DATABASE_URL, so the value below is what the test process actually uses.
TEST_DB_PATH = BACKEND_DIR / "tests" / ".studymate-test.db"
DEV_DB_PATH = BACKEND_DIR / "chatbot.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

# Embeddings come from Cohere's hosted API in production, but tests never touch
# the network: services inject fake embedding providers. The dummy key only
# satisfies the constructor guard should something unexpectedly build the real
# client. Reranking (local torch cross-encoder) stays disabled so the suite
# exercises the default deployment configuration.
os.environ.setdefault("COHERE_API_KEY", "test-only-dummy-key")
os.environ.setdefault("RERANKING_ENABLED", "false")

# Ensure `backend/` is on the path so `app.*` imports resolve correctly.
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
from app.auth.service import create_access_token
from app.db.session import DATABASE_URL, SessionLocal, engine, init_db
from app.db import crud


def _assert_isolated_database() -> None:
    """Refuse to run if the suite is not bound to the disposable test database."""
    resolved_name = Path(str(engine.url.database or "")).name
    if resolved_name == DEV_DB_PATH.name or resolved_name != TEST_DB_PATH.name:
        raise RuntimeError(
            "Refusing to run tests against "
            f"{DATABASE_URL!r}. The suite must use the isolated test database "
            f"({TEST_DB_PATH}). Check the environment for a DATABASE_URL override."
        )


def _discard_previous_test_database() -> None:
    """Remove the last run's database so every run starts from a clean schema."""
    for suffix in ("", "-wal", "-shm"):
        Path(f"{TEST_DB_PATH}{suffix}").unlink(missing_ok=True)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initialize the schema of the isolated test database for the whole session."""
    _assert_isolated_database()
    _discard_previous_test_database()
    init_db()


@pytest.fixture(scope="session")
def test_client():
    """FastAPI test client instance."""
    return TestClient(app)


@pytest.fixture(scope="session")
def test_user():
    """Create a default test user and return the User model."""
    db = SessionLocal()
    try:
        user = crud.get_user_by_email(db, "testuser@example.com")
        if user is None:
            user = crud.create_user(
                db,
                user_id="test_user_id_123",
                email="testuser@example.com",
                hashed_password="hashed_test_password",
                display_name="Test Student",
                role="student",
            )
        return user
    finally:
        db.close()


@pytest.fixture(scope="session")
def auth_headers(test_user):
    """Return Bearer token headers for test_user."""
    token = create_access_token(user_id=test_user.id, role=test_user.role)
    return {"Authorization": f"Bearer {token}"}
