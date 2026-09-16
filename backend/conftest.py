"""
conftest.py
===========
Root pytest configuration for the AI Study Companion backend.
"""
import sys
import os
import pytest
from fastapi.testclient import TestClient

# Ensure `backend/` is on the path so `app.*` imports resolve correctly.
sys.path.insert(0, os.path.dirname(__file__))

from app.main import app
from app.auth.service import create_access_token
from app.db.session import SessionLocal, init_db
from app.db import crud


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure DB schema is initialized for tests."""
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
