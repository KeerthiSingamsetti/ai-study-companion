"""Remove pre-score-gating weak-topic facts from the single-user development DB.

Run once from ``backend`` with:
``.venv\\Scripts\\python.exe -m scripts.cleanup_legacy_weak_memory``.
"""

from __future__ import annotations

from app.config import DEFAULT_USER_ID
from app.db import crud
from app.db.models import MemoryFactType, UserMemory
from app.db.session import SessionLocal


def _topic_key(topic: str | None) -> str:
    return (topic or "").strip().casefold()


def main() -> None:
    """Keep only weak facts backed by a real below-60% quiz attempt."""
    db = SessionLocal()
    try:
        valid_topics = {
            _topic_key(attempt.topic)
            for attempt in crud.get_quiz_attempts(db, DEFAULT_USER_ID)
            if attempt.total_questions > 0
            and attempt.correct_count / attempt.total_questions < 0.6
        }
        stale_facts = (
            db.query(UserMemory)
            .filter(
                UserMemory.user_id == DEFAULT_USER_ID,
                UserMemory.fact_type == MemoryFactType.WEAK_TOPIC,
            )
            .all()
        )
        removed = 0
        for fact in stale_facts:
            if _topic_key(fact.topic) not in valid_topics:
                db.delete(fact)
                removed += 1
        db.commit()
        print(f"Removed {removed} unverified legacy weak-topic facts.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
