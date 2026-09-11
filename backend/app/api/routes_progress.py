from typing import Annotated, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.config import DEFAULT_USER_ID
from app.db import crud
from app.db.session import get_db
from app.schemas.progress import FlashcardResultReport, QuizResultReport
from app.tools.memory_tool import get_study_progress, record_weak_topic

router = APIRouter(prefix="/progress", tags=["progress"])

@router.get("", response_model=dict[str, Any])
def get_user_study_progress(db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    """Return factual study records for the current user."""
    return get_study_progress(db, DEFAULT_USER_ID)


@router.post("/quiz-result", status_code=204)
def report_quiz_result(payload: QuizResultReport, db: Annotated[Session, Depends(get_db)]) -> None:
    total_questions = len(payload.results)
    correct_count = sum(item.correct for item in payload.results)
    crud.create_quiz_attempt(
        db,
        user_id=DEFAULT_USER_ID,
        document_id=payload.document_id,
        topic=payload.topic,
        correct_count=correct_count,
        total_questions=total_questions,
    )
    if correct_count / total_questions < 0.6:
        record_weak_topic(
            db,
            DEFAULT_USER_ID,
            payload.topic,
            f"scored {correct_count}/{total_questions} on {payload.topic}",
            payload.document_id,
            reason="quiz_score",
        )

@router.post("/flashcard-result", status_code=204)
def report_flashcard_result(payload: FlashcardResultReport, db: Annotated[Session, Depends(get_db)]) -> None:
    """Record a weak topic only when the student explicitly marks cards learning."""
    learning_count = sum(item.status == "learning" for item in payload.cards)
    if learning_count:
        record_weak_topic(
            db,
            DEFAULT_USER_ID,
            payload.topic,
            f"marked {learning_count} cards as still learning on {payload.topic}",
            payload.document_id,
            reason="flashcard_review",
        )

