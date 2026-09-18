"""Tests for the dedicated admin console API.

Covers the two properties that matter for §15/§16: the endpoints exist for
admins, and they are closed to everyone else. Also verifies the read-only
nature (no product state created) and the user inspector's isolation.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.admin import router as admin_router
from app.api.dependencies import get_current_user
from app.db import crud
from app.db.models import Base, Concept, Document, Event, IngestionJob, Space, Thread, User
from app.db.session import get_db
from app.services.mastery import update_concept_mastery


def _session_factory() -> sessionmaker:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _client(session_factory: sessionmaker, user_id: str, role: str) -> TestClient:
    """App with the real auth dependency decoding a token for `user_id`.
    The user row must already exist in the overridden session's database."""
    from app.auth.service import create_access_token

    app = FastAPI()
    app.include_router(admin_router)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {create_access_token(user_id=user_id, role=role)}"})
    return client


def _seed_user(session_factory: sessionmaker, user_id: str, role: str) -> None:
    with session_factory() as db:
        if db.get(User, user_id) is None:
            db.add(
                User(
                    id=user_id,
                    email=f"{user_id}@example.com",
                    hashed_password="not-a-login",
                    display_name=user_id.replace("-", " ").title(),
                    role=role,
                )
            )
            db.commit()


@pytest.fixture()
def platform():
    """A fresh platform in ONE in-memory database: one admin, two students."""
    factory = _session_factory()
    _seed_user(factory, "admin-1", "admin")
    _seed_user(factory, "student-a", "student")
    _seed_user(factory, "student-b", "student")
    return factory


def test_admin_endpoints_require_admin_role(platform) -> None:
    """Every admin route answers 200 for an admin and 403 for a student."""
    admin_client = _client(platform, "admin-1", "admin")
    student_client = _client(platform, "student-b", "student")

    for path in ("/admin/overview", "/admin/users", "/admin/spaces", "/admin/projects",
                 "/admin/ai-usage", "/admin/evaluation", "/admin/jobs", "/admin/health",
                 "/admin/activity", "/admin/activity/types", "/admin/activity/filters"):
        assert admin_client.get(path).status_code == 200, path
        assert student_client.get(path).status_code == 403, path


def test_admin_endpoints_reject_anonymous(platform) -> None:
    client = _client(platform, "admin-1", "admin")
    client.headers.pop("Authorization")
    assert client.get("/admin/overview").status_code == 401


def test_overview_counts_the_platform(platform) -> None:
    """The overview aggregates accounts, Spaces, Projects, jobs and AI calls."""
    factory = platform
    with factory() as db:
        admin_id = db.query(User).filter_by(role="admin").first().id
        space = crud.create_space(db, space_id="s1", user_id=admin_id, name="S", description="d")
        project = crud.create_thread(db, thread_id="p1", title="P1", user_id="student-a", space_id=space.id)
        db.add(Document(id="doc-1", thread_id="p1", filename="a.pdf", vectorstore_path="/tmp/vs-1"))
        db.commit()
        crud.log_event(db, user_id="student-a", project_id="p1", event_type="material_uploaded", payload_json="{}", event_key="e1")

    client = _client(factory, "admin-1", "admin")
    data = client.get("/admin/overview").json()
    assert data["users"] >= 3
    assert data["spaces"] == 1
    assert data["projects"] >= 1
    assert set(data["ingestion"]) == {"queued", "processing", "ready", "failed"}


def test_user_list_includes_rollups_without_exposing_other_data(platform) -> None:
    client = _client(platform, "admin-1", "admin")
    data = client.get("/admin/users").json()
    emails = {row["email"] for row in data["users"]}
    assert "student-a@example.com" in emails
    row = next(row for row in data["users"] if row["email"] == "student-a@example.com")
    assert {"spaces_count", "projects_count", "active_projects_30d", "ai_calls"} <= set(row)


def test_user_search_filters_by_email(platform) -> None:
    client = _client(platform, "admin-1", "admin")
    data = client.get("/admin/users", params={"q": "student-a"}).json()
    assert {row["email"] for row in data["users"]} == {"student-a@example.com"}


def test_user_inspector_returns_the_full_journey(platform) -> None:
    """PRD §16: inspect a user and see projects, activity, assessments, mastery."""
    factory = platform
    with factory() as db:
        crud.create_thread(db, thread_id="p1", title="ML Basics", user_id="student-a")
        db.add(Concept(id="c1", project_id="p1", name="Regularisation", name_normalized="regularisation"))
        db.commit()
        crud.log_event(
            db,
            user_id="student-a",
            project_id="p1",
            event_type="project_created",
            payload_json="{}",
            event_key="inspect-e1",
        )
        update_concept_mastery(
            db,
            user_id="student-a",
            project_id="p1",
            concept_id="c1",
            evidence_score=88.0,
            event_key="seed-evidence-1",
        )

    client = _client(factory, "admin-1", "admin")
    student_id = "student-a"
    data = client.get(f"/admin/users/{student_id}").json()
    assert data["user"]["email"] == "student-a@example.com"
    assert data["projects"] and data["projects"][0]["id"] == "p1"
    assert data["activity"], "events should be visible to the inspector"
    assert data["mastery"] and data["mastery"][0]["concept"] == "Regularisation"
    assert "ai_usage" in data


def test_user_inspector_404_for_unknown_user(platform) -> None:
    client = _client(platform, "admin-1", "admin")
    assert client.get("/admin/users/does-not-exist").status_code == 404


def test_job_list_renders_with_a_document_attached(platform) -> None:
    """Regression: an empty pipeline returned 200, so a broken document lookup
    behind it was never exercised. Jobs must serialise their own document."""
    factory = platform
    with factory() as db:
        crud.create_thread(db, thread_id="p1", title="ML Basics", user_id="student-a")
        db.add(Document(id="doc-1", thread_id="p1", filename="unit-1.pdf", vectorstore_path="/tmp/vs-1"))
        db.add(
            IngestionJob(
                id="job-1",
                document_id="doc-1",
                user_id="student-a",
                project_id="p1",
                status="ready",
                retry_count=2,
            )
        )
        db.commit()

    client = _client(factory, "admin-1", "admin")
    response = client.get("/admin/jobs")
    assert response.status_code == 200, response.text
    job = response.json()["jobs"][0]
    assert job["document_filename"] == "unit-1.pdf"
    assert job["retry_count"] == 2
    assert response.json()["states"]["ready"] == 1


def test_activity_filters_offer_names_not_identifiers(platform) -> None:
    """Operators pick a learner or Project by label; ids stay internal."""
    factory = platform
    with factory() as db:
        crud.create_space(db, space_id="s1", user_id="admin-1", name="Maths")
        crud.create_thread(db, thread_id="p1", title="Unit 1", user_id="student-a", space_id="s1")
        crud.log_event(db, user_id="student-a", project_id="p1", event_type="material_uploaded", payload_json="{}", event_key="f1")

    client = _client(factory, "admin-1", "admin")
    data = client.get("/admin/activity/filters").json()
    assert "student-a@example.com" in {row["email"] for row in data["users"]}
    assert [row["label"] for row in data["projects"]] == ["Unit 1"]
    assert data["projects"][0]["space"] == "Maths"

    # Silent accounts and Projects cannot produce events, so offering them in a
    # picker would only ever filter the feed to nothing.
    assert data["users"] == [{"id": "student-a", "label": "Student A", "email": "student-a@example.com"}]

    narrowed = client.get("/admin/activity/filters", params={"user_id": "student-b"}).json()
    assert narrowed["projects"] == []


def test_admin_views_create_no_product_state(platform) -> None:
    """Read-only guarantee: browsing every admin view writes nothing."""
    factory = platform
    client = _client(factory, "admin-1", "admin")
    for path in ("/admin/overview", "/admin/users", "/admin/spaces", "/admin/projects",
                 "/admin/ai-usage", "/admin/evaluation", "/admin/jobs", "/admin/health",
                 "/admin/activity", "/admin/activity/filters"):
        client.get(path)

    with factory() as db:
        assert db.query(Event).count() == 0
        assert db.query(Thread).count() == 0
        assert db.query(Space).count() == 0
