"""Confidence calibration: does a learner know what they don't know?

Deliberately isolated from the development database (the existing
``test_learning_loop.py`` runs through the real app against ``chatbot.db``,
which is why that file's Spaces named ``Space <uuid>`` show up in a real admin
console). Everything here uses an in-memory database and an overridden
``get_db`` so running the suite never writes to real user data.
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import learning as learning_api
from app.api.dependencies import get_embeddings, get_llm
from app.auth.service import create_access_token
from app.config import CALIBRATION_OVERCONFIDENT_GAP
from app.db import crud
from app.db.models import AssessmentAttempt, Base, User
from app.db.session import get_db
from app.services import calibration
from app.services.learning import build_recommendations
from app.services.mastery import update_concept_mastery

# ── Pure calibration maths ────────────────────────────────────────────────


def test_confidence_scale_maps_onto_a_prediction() -> None:
    """The one-tap self-report must be comparable with a 0-100 graded score."""
    assert calibration.predicted_from_confidence(1) == 20.0
    assert calibration.predicted_from_confidence(5) == 100.0
    assert calibration.predicted_from_confidence(99) is None
    assert calibration.confidence_label(4) == "Confident"
    assert [value for value, _, _ in calibration.CONFIDENCE_SCALE] == [1, 2, 3, 4, 5]


def test_overconfident_when_predictions_run_ahead_of_results() -> None:
    summary = calibration.summarize([(80.0, 46.0), (80.0, 52.0)])
    assert summary["direction"] == calibration.DIRECTION_OVERCONFIDENT
    assert summary["bias"] == pytest.approx(31.0)
    assert summary["mean_actual"] == pytest.approx(49.0)
    assert summary["samples"] == 2


def test_underconfident_and_well_calibrated_are_distinguished() -> None:
    assert calibration.summarize([(60.0, 88.0)])["direction"] == calibration.DIRECTION_UNDERCONFIDENT
    assert calibration.summarize([(80.0, 78.0)])["direction"] == calibration.DIRECTION_CALIBRATED
    # A miss just inside the threshold is not treated as a bias.
    inside = calibration.summarize([(80.0, 80.0 - CALIBRATION_OVERCONFIDENT_GAP + 1)])
    assert inside["direction"] == calibration.DIRECTION_CALIBRATED


def test_no_evidence_is_reported_honestly_not_as_calibrated() -> None:
    empty = calibration.summarize([])
    assert empty["direction"] == calibration.DIRECTION_INSUFFICIENT
    assert empty["bias"] is None
    assert "Predict your score" in calibration.insight("Gradient descent", empty)


def test_insight_states_the_gap_and_the_remedy() -> None:
    text = calibration.insight("national income", calibration.summarize([(80.0, 46.0)]))
    assert "80/100" in text and "46/100" in text
    assert "closed-book" in text


# ── Report assembly over stored evidence ──────────────────────────────────


@pytest.fixture()
def session_factory() -> sessionmaker:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed(session_factory: sessionmaker, *, concept: str, pairs: list[tuple[float, float]], user_id: str = "u1") -> str:
    """Persist one concept with (predicted, actual) attempts. Returns concept id."""
    with session_factory() as db:
        if db.get(User, user_id) is None:
            db.add(
                User(
                    id=user_id,
                    email=f"{user_id}@example.com",
                    hashed_password="not-a-login",
                    display_name="Learner",
                    role="student",
                )
            )
        project = crud.create_thread(db, thread_id=f"p-{concept}", title="Unit 1", user_id=user_id)
        record = crud.create_concept(
            db, concept_id=f"c-{concept}", project_id=project.id, name=concept, name_normalized=concept.lower()
        )
        for index, (predicted, actual) in enumerate(pairs):
            db.add(
                AssessmentAttempt(
                    user_id=user_id,
                    project_id=project.id,
                    concept_id=record.id,
                    question=f"q{index}",
                    answer="a",
                    predicted_score=predicted,
                    understanding=actual,
                    accuracy=actual,
                    overall_score=actual,
                )
            )
        db.commit()
        return record.id


def test_report_groups_by_concept_and_ranks_the_worst_bias_first(session_factory) -> None:
    _seed(session_factory, concept="national income", pairs=[(100.0, 40.0)])
    _seed(session_factory, concept="economy growth", pairs=[(60.0, 85.0)])
    with session_factory() as db:
        report = calibration.report(db, user_id="u1", project_id="p-national income")
    assert report["samples"] == 1
    assert report["concepts"][0]["concept"] == "national income"
    assert report["concepts"][0]["direction"] == calibration.DIRECTION_OVERCONFIDENT
    assert "more than you produce" in report["headline"]


def test_unpredicted_attempts_are_excluded_from_calibration(session_factory) -> None:
    """A skipped prediction must not be silently counted as perfect foresight."""
    with session_factory() as db:
        project = crud.create_thread(db, thread_id="p2", title="Unit 2", user_id="u1")
        db.add(
            AssessmentAttempt(
                user_id="u1",
                project_id=project.id,
                question="q",
                answer="a",
                predicted_score=None,
                understanding=50.0,
                accuracy=50.0,
                overall_score=50.0,
            )
        )
        db.commit()
        report = calibration.report(db, user_id="u1", project_id="p2")
    assert report["samples"] == 0
    assert report["direction"] == calibration.DIRECTION_INSUFFICIENT


# ── Recommendations consume the calibration signal ─────────────────────────


def test_overconfidence_outranks_a_merely_mediocre_score(session_factory) -> None:
    """Mastery above the low-mastery threshold, no repeated mistakes, but the
    learner expects far more than they produce — that must drive the next step."""
    concept_id = _seed(session_factory, concept="national income", pairs=[(100.0, 70.0), (100.0, 68.0)])
    with session_factory() as db:
        update_concept_mastery(
            db, user_id="u1", project_id="p-national income", concept_id=concept_id,
            evidence_score=70.0, event_key="seed-evidence",
        )
        recommendations = build_recommendations(db, user_id="u1", project_id="p-national income")

    assert recommendations, "calibration should produce a next step"
    assert recommendations[0]["trigger"] == "overconfidence"
    assert "closed-book" in recommendations[0]["action"]


def test_well_calibrated_learners_do_not_get_a_confidence_nudge(session_factory) -> None:
    concept_id = _seed(session_factory, concept="economy growth", pairs=[(72.0, 74.0), (72.0, 70.0)])
    with session_factory() as db:
        update_concept_mastery(
            db, user_id="u1", project_id="p-economy growth", concept_id=concept_id,
            evidence_score=72.0, event_key="seed-evidence-2",
        )
        recommendations = build_recommendations(db, user_id="u1", project_id="p-economy growth")

    assert all(item["trigger"] != "overconfidence" for item in recommendations)


# ── The HTTP path ─────────────────────────────────────────────────────────


class _FakeEmbeddings:
    def _vector(self, text: str) -> list[float]:
        digest = 0
        for char in text.lower():
            digest = (digest * 31 + ord(char)) % 1_000_003
        return [float(digest % 13), float(digest % 7), 1.0, 0.5]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]


class _FakeLLM:
    def __init__(self, payload: dict):
        self.payload = payload

    def invoke(self, _messages):
        return type("Response", (), {"content": json.dumps(self.payload)})()


@pytest.fixture()
def api(session_factory, monkeypatch):
    """The learning router on an in-memory database, with the grader stubbed."""
    app = FastAPI()
    app.include_router(learning_api.router)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embeddings] = lambda: _FakeEmbeddings()
    app.dependency_overrides[get_llm] = lambda: _FakeLLM(
        {"understanding": 74.0, "accuracy": 70.0, "concepts_covered": ["income"], "concepts_missing": [], "feedback": "ok"}
    )
    # Every score here stays above the weak-topic threshold, but the memory store
    # opens its own session, so stub it rather than risk writing outside the
    # in-memory database.
    monkeypatch.setattr(learning_api, "record_weak_topic", lambda *args, **kwargs: None)

    with session_factory() as db:
        db.add(
            User(
                id="learner",
                email="learner@example.com",
                hashed_password="not-a-login",
                display_name="Learner",
                role="student",
            )
        )
        db.commit()
        crud.create_thread(db, thread_id="proj-1", title="Unit 1", user_id="learner")

    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {create_access_token(user_id='learner', role='student')}"})
    return client


def _grade(client, **overrides):
    body = {
        "project_id": "proj-1",
        "concept": "national income",
        "question": "Explain how national income is measured.",
        "answer": "Through output, income and expenditure.",
        **overrides,
    }
    return client.post("/learning/assessment/grade", json=body)


def test_prediction_is_persisted_and_returned_as_a_snapshot(api) -> None:
    """The learner rates themselves before grading; the response explains the gap."""
    response = _grade(api, predicted_score=100.0)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["overall_score"] == pytest.approx(72.0)

    snapshot = payload["calibration"]
    assert snapshot is not None
    assert snapshot["direction"] == calibration.DIRECTION_OVERCONFIDENT
    assert snapshot["mean_predicted"] == pytest.approx(100.0)
    assert snapshot["mean_actual"] == pytest.approx(72.0)
    assert "cannot yet produce" in snapshot["insight"]

    # The recommendation raised from this very answer is about confidence.
    assert any(item["trigger"] == "overconfidence" for item in payload["recommendations"])


def test_grading_still_works_without_a_prediction(api) -> None:
    """Predicting is encouraged, never required — the loop must not break."""
    response = _grade(api)
    assert response.status_code == 200, response.text
    assert response.json()["calibration"] is None


def test_summary_exposes_the_calibration_report(api) -> None:
    _grade(api, predicted_score=80.0)
    summary = api.get("/learning/assessment/proj-1")
    assert summary.status_code == 200, summary.text
    report = summary.json()["calibration"]
    assert report["samples"] == 1
    assert report["concepts"][0]["concept"] == "national income"
    assert report["concepts"][0]["insight"]
    # The prediction travels with the graded history too.
    assert summary.json()["history"][0]["predicted_score"] == pytest.approx(80.0)


def test_prediction_is_validated(session_factory, api) -> None:
    assert _grade(api, predicted_score=140.0).status_code == 422
