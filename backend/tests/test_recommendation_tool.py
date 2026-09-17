from types import SimpleNamespace
from app.tools.recommendation_tool import build_recommendations


def _db_with_attempts(attempts):
    class Query:
        def filter(self, *_): return self
        def order_by(self, *_): return self
        def limit(self, *_): return self
        def all(self): return attempts
    class DB:
        def query(self, *_): return Query()
    return DB()


def _recommendations(monkeypatch, *, mastery_score, attempts):
    concept = SimpleNamespace(id="c1", name="ATP")
    mastery = SimpleNamespace(mastery_score=mastery_score)
    monkeypatch.setattr("app.tools.recommendation_tool.crud.list_mastery_for_user_and_project", lambda *_: [(concept, mastery)])
    return build_recommendations(_db_with_attempts([SimpleNamespace(overall_score=s) for s in attempts]), user_id="u", project_id="p")


def test_repeated_mistakes_take_priority_in_recommendations(monkeypatch):
    result = _recommendations(monkeypatch, mastery_score=80, attempts=[30, 40, 50])
    assert result[0]["trigger"] == "repeated_mistake"


def test_low_mastery_recommendation(monkeypatch):
    result = _recommendations(monkeypatch, mastery_score=45, attempts=[100])
    assert result == [{"concept": "ATP", "trigger": "low_mastery", "action": "Review ATP and complete targeted practice."}]


def test_improving_recommendation(monkeypatch):
    result = _recommendations(monkeypatch, mastery_score=80, attempts=[80, 70])
    assert result[0]["trigger"] == "improving"


def test_repeated_mistake_outranks_low_mastery_without_duplicate(monkeypatch):
    result = _recommendations(monkeypatch, mastery_score=40, attempts=[20, 30, 40])
    assert [item["trigger"] for item in result] == ["repeated_mistake"]


def test_no_recommendations_for_healthy_stable_concept(monkeypatch):
    result = _recommendations(monkeypatch, mastery_score=80, attempts=[80, 80])
    assert result == []
