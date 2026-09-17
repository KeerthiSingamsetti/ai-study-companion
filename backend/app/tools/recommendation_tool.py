"""Read-only recommendation tool exposed to the tutor graph."""
from __future__ import annotations
import json
from typing import Any
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from app.db import crud
from app.db.models import AssessmentAttempt
from app.db.session import SessionLocal
from app.services.learning import classify_growth, repeated_mistake_detected


def build_recommendations(db: Any, *, user_id: str, project_id: str) -> list[dict[str, str]]:
    """Derive next actions from persisted evidence without mutating state."""
    results = []
    for concept, mastery in crud.list_mastery_for_user_and_project(db, user_id, project_id):
        attempts = (db.query(AssessmentAttempt).filter(
            AssessmentAttempt.user_id == user_id, AssessmentAttempt.project_id == project_id,
            AssessmentAttempt.concept_id == concept.id
        ).order_by(AssessmentAttempt.created_at.desc()).limit(10).all())
        scores = [attempt.overall_score for attempt in attempts]
        if repeated_mistake_detected(scores):
            results.append({"concept": concept.name, "trigger": "repeated_mistake", "action": f"Review {concept.name} with a worked example, then retry a short assessment."})
        elif mastery.mastery_score < 60:
            results.append({"concept": concept.name, "trigger": "low_mastery", "action": f"Review {concept.name} and complete targeted practice."})
        elif len(scores) >= 2 and classify_growth(scores[1], scores[0]) == "improving":
            results.append({"concept": concept.name, "trigger": "improving", "action": f"Continue practising {concept.name} with an application question."})
    return results[:3]


def create_recommendation_tool() -> BaseTool:
    @tool
    def get_recommendations(config: RunnableConfig) -> str:
        """Get read-only personalised next study actions for the active project."""
        project_id = config.get("configurable", {}).get("thread_id")
        if not isinstance(project_id, str) or not project_id:
            return "No active project is available for recommendations."
        db = SessionLocal()
        try:
            project = crud.get_thread(db, project_id)
            if project is None or not project.user_id:
                return "No active project is available for recommendations."
            return json.dumps(build_recommendations(db, user_id=project.user_id, project_id=project_id))
        finally:
            db.close()

    return get_recommendations
