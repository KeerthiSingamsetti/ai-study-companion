"""Read-only recommendation tool exposed to the tutor graph."""
from __future__ import annotations
import json
from typing import Any
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from app.db import crud
from app.db.session import SessionLocal
from app.services.learning import build_recommendations

__all__ = ["build_recommendations", "create_recommendation_tool"]


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
