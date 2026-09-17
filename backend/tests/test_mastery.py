"""Tests for the locked EMA mastery formula and its persistence boundary."""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DEFAULT_USER_ID
from app.db import crud
from app.db.models import Base, User
from app.services.mastery import calculate_ema_mastery, update_concept_mastery


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=DEFAULT_USER_ID, email="student@example.com", hashed_password="x", display_name="Student"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_mastery_uses_locked_ema_lambda() -> None:
    assert calculate_ema_mastery(50.0, 100.0) == 57.5
    assert calculate_ema_mastery(57.5, 0.0) == 48.88


def test_mastery_rejects_out_of_range_evidence() -> None:
    with pytest.raises(ValueError):
        calculate_ema_mastery(50.0, 100.1)


def test_update_mastery_records_before_after_event(db) -> None:
    project_id = str(uuid.uuid4())
    crud.create_thread(db, thread_id=project_id, title="Biology", user_id=DEFAULT_USER_ID)
    concept = crud.create_concept(db, concept_id=str(uuid.uuid4()), project_id=project_id, name="ATP", name_normalized="atp")

    result = update_concept_mastery(
        db, user_id=DEFAULT_USER_ID, project_id=project_id,
        concept_id=concept.id, evidence_score=100.0, event_key="assessment-1"
    )

    assert result.mastery_score == 57.5
    assert result.attempt_count == 1
    assert len(crud.list_events_for_project(db, project_id)) == 1
