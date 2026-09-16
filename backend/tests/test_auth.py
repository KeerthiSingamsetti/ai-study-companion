"""Tests for authentication endpoints, token validation, and authorization."""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal, init_db
from app.db import crud

client = TestClient(app)


def setup_module():
    init_db()


def test_register_success():
    suffix = uuid.uuid4().hex[:6]
    email = f"newuser_{suffix}@example.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "display_name": "New User"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == email


def test_register_duplicate_email():
    suffix = uuid.uuid4().hex[:6]
    email = f"duplicate_{suffix}@example.com"
    client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "display_name": "User One"},
    )
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "display_name": "User Two"},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_login_success():
    suffix = uuid.uuid4().hex[:6]
    email = f"logintest_{suffix}@example.com"
    password = "secretpassword"
    client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": "Login User"},
    )
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == email


def test_login_wrong_password():
    suffix = uuid.uuid4().hex[:6]
    email = f"wrongpass_{suffix}@example.com"
    client.post(
        "/auth/register",
        json={"email": email, "password": "correctpassword", "display_name": "User"},
    )
    response = client.post("/auth/login", json={"email": email, "password": "wrongpassword"})
    assert response.status_code == 401


def test_protected_route_unauthorized():
    response = client.get("/threads")
    assert response.status_code == 401


def test_protected_route_with_auth(auth_headers):
    response = client.get("/threads", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_project_user_isolation(auth_headers):
    suffix = uuid.uuid4().hex[:6]
    resp_b = client.post(
        "/auth/register",
        json={"email": f"userb_{suffix}@example.com", "password": "password123", "display_name": "User B"},
    )
    assert resp_b.status_code == 201
    token_b = resp_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    db = SessionLocal()
    try:
        user_a = crud.get_user_by_email(db, "testuser@example.com")
        thread_a = crud.create_thread(db, thread_id=f"thread_user_a_{suffix}", title="User A Project", user_id=user_a.id)
    finally:
        db.close()

    resp_a_get = client.get(f"/threads/{thread_a.id}/study-log", headers=auth_headers)
    assert resp_a_get.status_code == 200

    resp_b_get = client.get(f"/threads/{thread_a.id}/study-log", headers=headers_b)
    assert resp_b_get.status_code == 404
