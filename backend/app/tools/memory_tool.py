"""Structured, user-scoped long-term study-memory helpers."""

from datetime import datetime
from typing import Any


from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from sqlalchemy.orm import Session

from app.config import DEFAULT_USER_ID
from app.db import crud
from app.db.models import MemoryFactType
from app.db.session import SessionLocal


def record_weak_topic(
    db: Session,
    user_id: str,
    topic: str,
    detail: str,
    document_id: str | None = None,
    reason: str = "quiz_score",
) -> None:
    """Persist a deterministic weak-topic fact derived by backend rules."""
    crud.save_user_memory(
        db, user_id, MemoryFactType.WEAK_TOPIC, topic, detail, document_id, reason=reason
    )


def record_studied_topic(
    db: Session, user_id: str, topic: str, document_id: str | None
) -> None:
    """Persist a factual record that the student generated study material."""
    crud.save_user_memory(
        db,
        user_id,
        MemoryFactType.STUDIED_TOPIC,
        topic,
        f"Studied {topic}.",
        document_id,
        reason="manual",
    )


def get_memory_context(db: Session, user_id: str) -> str:
    """Return a short prompt fragment for a fresh conversation, never a transcript."""
    facts = crud.get_user_memory(db, user_id, limit=8)
    weak = [
        fact.topic
        for fact in facts
        if fact.fact_type == MemoryFactType.WEAK_TOPIC and fact.topic
    ]
    studied = [
        fact.topic
        for fact in facts
        if fact.fact_type == MemoryFactType.STUDIED_TOPIC and fact.topic
    ]
    parts: list[str] = []
    if weak:
        parts.append(
            f"This student has previously struggled with: {', '.join(dict.fromkeys(weak[:3]))}."
        )
    if studied:
        parts.append(f"Recently studied: {', '.join(dict.fromkeys(studied[:3]))}.")
    return " ".join(parts)


def get_default_memory_context() -> str:
    """Load the temporary single-user context from a short-lived DB session."""
    db = SessionLocal()
    try:
        return get_memory_context(db, DEFAULT_USER_ID)
    finally:
        db.close()


def _format_date(value: datetime) -> str:
    """Return a stable date for persisted activity data."""
    return value.date().isoformat()


def get_study_progress(db: Session, user_id: str) -> dict[str, list[dict[str, Any]]]:
    """Return factual study records only, with standardized weak-topic schemas."""
    attempts = crud.get_quiz_attempts(db, user_id)
    weak_facts = crud.get_user_memory(
        db, user_id, fact_type=MemoryFactType.WEAK_TOPIC
    )
    studied_facts = crud.get_user_memory(
        db, user_id, fact_type=MemoryFactType.STUDIED_TOPIC
    )

    formatted_attempts = []
    attempt_by_topic: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        total = attempt.total_questions or 0
        correct = attempt.correct_count or 0
        percentage = round((correct / total) * 100) if total > 0 else 0
        item = {
            "topic": attempt.topic,
            "document_id": getattr(attempt, "document_id", None),
            "score": f"{correct}/{total}",
            "percentage": percentage,
            "formatted_score": f"{percentage}% ({correct}/{total})",
            "date": _format_date(attempt.created_at),
        }
        formatted_attempts.append(item)
        norm_topic = (attempt.topic or "").strip().lower()
        if norm_topic and norm_topic not in attempt_by_topic:
            attempt_by_topic[norm_topic] = item

    formatted_weak_topics = []
    for fact in weak_facts:
        topic_name = fact.topic or ""
        norm_topic = topic_name.strip().lower()
        matching_quiz = attempt_by_topic.get(norm_topic)
        reason = getattr(fact, "reason", None) or "quiz_score"

        formatted_weak_topics.append({
            "topic": topic_name,
            "document_id": getattr(fact, "document_id", None) or (matching_quiz["document_id"] if matching_quiz else None),
            "reason": reason,
            "detail": fact.detail,
            "score": matching_quiz["score"] if matching_quiz else None,
            "percentage": matching_quiz["percentage"] if matching_quiz else None,
            "formatted_score": matching_quiz["formatted_score"] if matching_quiz else None,
            "date": _format_date(fact.created_at),
        })


    return {
        "quiz_attempts": formatted_attempts,
        "weak_topics": formatted_weak_topics,
        "studied_topics": [
            {
                "topic": fact.topic or "",
                "date": _format_date(fact.created_at),
            }
            for fact in studied_facts
        ],
    }




def create_study_progress_tool() -> BaseTool:
    """Create the no-input agent tool for student performance questions."""

    @tool
    def get_study_progress_tool(
        config: RunnableConfig,
    ) -> dict[str, list[dict[str, str]]]:
        """Use for the student's own quiz attempts, weaknesses, progress, or history. Takes no arguments."""
        db = SessionLocal()
        try:
            return get_study_progress(db, DEFAULT_USER_ID)
        finally:
            db.close()

    get_study_progress_tool.name = "get_study_progress"
    return get_study_progress_tool
