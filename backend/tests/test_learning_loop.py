"""End-to-end tests for the learning loop wired in this change.

These cover the gap that made Project Analytics look empty: quiz answers and
open-ended assessment answers were never turning into concept-mastery evidence,
so ``overall progress``, ``concept mastery``, ``growth`` and ``recommendations``
had nothing to read.
"""

import json
from uuid import uuid4

import pytest

from app.api.dependencies import get_embeddings, get_llm
from app.main import app


class _FakeEmbeddings:
    """Deterministic embeddings so concept resolution never needs NIM.

    Content-sensitive on purpose: a length-only vector would make unrelated
    concepts resolve to each other through the 0.88 similarity threshold and
    quietly invalidate these tests.
    """

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
    """Returns schema-valid JSON for the open-ended grader."""

    def __init__(self, payload: dict):
        self.payload = payload

    def invoke(self, _messages):
        return type("Response", (), {"content": json.dumps(self.payload)})()


DEFAULT_GRADE = {
    "understanding": 88.0,
    "accuracy": 82.0,
    "concepts_covered": ["noise memorisation"],
    "concepts_missing": [],
    "feedback": "Clear explanation with correct reasoning.",
}


@pytest.fixture()
def learning_overrides(request):
    """Override embeddings and the grader LLM so the loop runs without NIM."""
    payload = getattr(request, "param", DEFAULT_GRADE)
    app.dependency_overrides[get_embeddings] = lambda: _FakeEmbeddings()
    app.dependency_overrides[get_llm] = lambda: _FakeLLM(payload)
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_embeddings, None)
        app.dependency_overrides.pop(get_llm, None)


def _make_project(test_client, auth_headers, **extra):
    space = test_client.post(
        "/spaces", headers=auth_headers, json={"name": f"Space {uuid4()}", "description": "Course container"}
    ).json()
    body = {"title": f"Project {uuid4()}", "space_id": space["id"], **extra}
    project = test_client.post("/threads", headers=auth_headers, json=body)
    assert project.status_code == 201, project.text
    return space, project.json()


def test_space_requires_description_and_supports_customization(test_client, auth_headers):
    created = test_client.post(
        "/spaces",
        headers=auth_headers,
        json={"name": "Machine Learning", "description": "  Deep learning basics  ", "accent": "#F5B54A", "icon": "brain"},
    )
    assert created.status_code == 201, created.text
    space = created.json()
    assert space["description"] == "Deep learning basics"
    assert space["accent"] == "#F5B54A"
    assert space["icon"] == "brain"

    patched = test_client.patch(
        f"/spaces/{space['id']}", headers=auth_headers, json={"description": "Updated scope"}
    )
    assert patched.status_code == 200
    assert patched.json()["description"] == "Updated scope"

    listing = test_client.get("/spaces", headers=auth_headers).json()
    assert any(item["id"] == space["id"] and item["description"] == "Updated scope" for item in listing)


def test_project_stores_description_and_learning_goal(test_client, auth_headers):
    _, project = _make_project(
        test_client,
        auth_headers,
        description="  Covers backpropagation  ",
        learning_goal="Pass the midterm",
    )
    assert project["description"] == "Covers backpropagation"
    assert project["learning_goal"] == "Pass the midterm"

    updated = test_client.patch(
        f"/threads/{project['id']}",
        headers=auth_headers,
        json={"learning_goal": "Ship the capstone"},
    )
    assert updated.status_code == 200
    assert updated.json()["learning_goal"] == "Ship the capstone"

    analytics = test_client.get(f"/analytics/projects/{project['id']}", headers=auth_headers).json()
    assert analytics["project"]["description"] == "Covers backpropagation"
    assert analytics["project"]["learning_goal"] == "Ship the capstone"


def test_quiz_result_creates_mastery_growth_and_recommendations(test_client, auth_headers, learning_overrides):
    _, project = _make_project(test_client, auth_headers)

    first = test_client.post(
        "/learning/quiz-result",
        headers=auth_headers,
        json={
            "project_id": project["id"],
            "topic": "Gradient descent",
            "concept": "Gradient descent",
            "results": [{"question": "q1", "correct": True}, {"question": "q2", "correct": False}],
        },
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["score"] == 50.0
    assert body["mastery"]["score"] == 50.0  # 0.85 * 50 initial + 0.15 * 50 evidence
    assert body["mastery"]["attempts"] == 1

    # A strong second session must be classified as improving, not just recorded.
    second = test_client.post(
        "/learning/quiz-result",
        headers=auth_headers,
        json={
            "project_id": project["id"],
            "topic": "Gradient descent",
            "concept": "Gradient Descent",  # resolves to the same concept
            "results": [{"question": "q1", "correct": True}, {"question": "q2", "correct": True}],
        },
    ).json()
    assert second["mastery"]["concept"] == "Gradient descent"
    assert second["mastery"]["attempts"] == 2
    assert second["mastery"]["growth"]["classification"] == "improving"

    analytics = test_client.get(f"/analytics/projects/{project['id']}", headers=auth_headers).json()
    assert analytics["mastery"], "project analytics must expose concept mastery"
    assert analytics["overall_progress"] is not None
    assert analytics["mastery"][0]["concept"] == "Gradient descent"
    assert analytics["mastery"][0]["classification"] == "improving"
    assert analytics["assessments_graded"] == 0


def test_adaptive_target_requires_evidence(test_client, auth_headers, learning_overrides):
    _, project = _make_project(test_client, auth_headers)
    response = test_client.get(f"/learning/quiz/next?project_id={project['id']}", headers=auth_headers)
    assert response.status_code == 409
    assert "mastery evidence" in response.json()["detail"]


def test_adaptive_target_picks_weakest_concept_not_the_last_answer(
    test_client, auth_headers, learning_overrides
):
    """Selection must follow the mastery policy, not a wrong→easy / right→hard flip."""
    _, project = _make_project(test_client, auth_headers)

    def quiz(concept, correct):
        return test_client.post(
            "/learning/quiz-result",
            headers=auth_headers,
            json={
                "project_id": project["id"],
                "topic": concept,
                "concept": concept,
                "results": [{"question": "q", "correct": correct}],
            },
        )

    # A strong concept the learner just answered correctly...
    quiz("Eigenvalues", True)
    quiz("Eigenvalues", True)
    # ...and a weak one with two sustained low-scoring sessions.
    quiz("Matrix rank", False)
    quiz("Matrix rank", False)

    response = test_client.get(f"/learning/quiz/next?project_id={project['id']}", headers=auth_headers)
    assert response.status_code == 200, response.text
    target = response.json()

    # The *weakest* concept wins even though "Eigenvalues" was answered most recently.
    assert target["concept"] == "Matrix rank"
    assert target["difficulty"] == "easy"
    assert target["recent_mistakes"] == 2
    assert target["mastery_score"] < 45
    assert "below 60" in target["reason"]
    assert target["has_material"] is False


def test_adaptive_target_requires_owned_project(test_client, auth_headers, learning_overrides):
    assert test_client.get("/learning/quiz/next", headers=auth_headers).status_code == 422
    assert test_client.get(f"/learning/quiz/next?project_id={uuid4()}", headers=auth_headers).status_code == 404
    assert test_client.get(f"/learning/quiz/next?project_id={uuid4()}").status_code == 401


def test_assessment_grading_persists_attempt_and_moves_mastery(
    test_client, auth_headers, learning_overrides
):
    _, project = _make_project(test_client, auth_headers)
    graded = test_client.post(
        "/learning/assessment/grade",
        headers=auth_headers,
        json={
            "project_id": project["id"],
            "concept": "Overfitting",
            "question": "Why does p >> n increase overfitting risk?",
            "answer": "The model has enough flexibility to memorise noise.",
        },
    )
    assert graded.status_code == 200, graded.text
    result = graded.json()
    assert 0 <= result["overall_score"] <= 100
    assert result["mastery"]["score"] is not None
    assert result["assessment_average"] is not None

    summary = test_client.get(f"/learning/assessment/{project['id']}", headers=auth_headers).json()
    assert summary["graded_count"] == 1
    assert summary["history"][0]["concept"] == "Overfitting"
    assert summary["history"][0]["feedback"]
    assert summary["overall_progress"] is not None

    analytics = test_client.get(f"/analytics/projects/{project['id']}", headers=auth_headers).json()
    assert analytics["assessment_average"] == result["overall_score"]
    assert analytics["assessments_graded"] == 1


def test_assessment_generate_requires_material(test_client, auth_headers, learning_overrides):
    _, project = _make_project(test_client, auth_headers)
    response = test_client.post(
        "/learning/assessment/generate",
        headers=auth_headers,
        json={"project_id": project["id"], "concept": "Anything"},
    )
    assert response.status_code == 412


@pytest.mark.parametrize(
    "learning_overrides",
    [
        {
            "understanding": 40.0,
            "accuracy": 30.0,
            "concepts_covered": ["basic idea"],
            "concepts_missing": ["worked example"],
            "feedback": "Review the derivation.",
        }
    ],
    indirect=True,
)
def test_low_score_produces_a_persisted_recommendation(test_client, auth_headers, learning_overrides):
    _, project = _make_project(test_client, auth_headers)
    for _ in range(2):
        response = test_client.post(
            "/learning/assessment/grade",
            headers=auth_headers,
            json={
                "project_id": project["id"],
                "concept": "Backpropagation",
                "question": "Explain the chain rule here.",
                "answer": "I am not sure.",
            },
        )
        assert response.status_code == 200, response.text

    active = test_client.get(f"/learning/recommendations/{project['id']}", headers=auth_headers).json()
    assert active, "a struggling learner must get a next step"
    assert active[0]["trigger"] in {"low_mastery", "repeated_mistake"}

    dismissed = test_client.post(
        f"/learning/recommendations/{active[0]['id']}/dismiss", headers=auth_headers
    )
    assert dismissed.status_code == 204
    remaining = test_client.get(f"/learning/recommendations/{project['id']}", headers=auth_headers).json()
    assert all(item["id"] != active[0]["id"] for item in remaining)


def test_space_analytics_rolls_up_projects_and_attention(test_client, auth_headers, learning_overrides):
    space, project = _make_project(test_client, auth_headers, description="Rolled up")
    test_client.post(
        "/learning/quiz-result",
        headers=auth_headers,
        json={
            "project_id": project["id"],
            "topic": "Regularisation",
            "results": [{"question": "q1", "correct": False}],
        },
    )

    response = test_client.get(f"/analytics/spaces/{space['id']}", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["space"]["description"] == "Course container"
    assert body["projects_count"] == 1
    assert body["projects"][0]["id"] == project["id"]
    assert body["projects"][0]["concepts_tracked"] == 1
    assert body["areas_requiring_attention"]
    assert body["overall_progress"] is not None


def test_learning_endpoints_require_auth_and_project_ownership(test_client, auth_headers, learning_overrides):
    _, project = _make_project(test_client, auth_headers)
    assert test_client.post("/learning/quiz-result", json={"project_id": project["id"], "topic": "x", "results": [{"correct": True}]}).status_code == 401
    missing = test_client.post(
        "/learning/quiz-result",
        headers=auth_headers,
        json={"project_id": str(uuid4()), "topic": "x", "results": [{"correct": True}]},
    )
    assert missing.status_code == 404
    assert test_client.get(f"/learning/assessment/{uuid4()}", headers=auth_headers).status_code == 404
