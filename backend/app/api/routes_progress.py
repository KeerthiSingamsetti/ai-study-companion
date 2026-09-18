from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import crud
from app.db.models import User
from app.db.session import get_db
from app.schemas.progress import FlashcardResultReport, QuizResultReport
from app.tools.memory_tool import get_study_progress, record_weak_topic

router = APIRouter(prefix="/progress", tags=["progress"])


def _owned_project_id(db: Session, document_id: str, user: User) -> str:
    """Resolve the Project a reported document belongs to, enforcing ownership.

    A Project belongs to exactly one Space, so attributing every progress
    record to its Project is what keeps one Space's memory out of another's.
    A document that does not exist or is not owned raises 404 rather than being
    silently recorded against the account as a whole.
    """
    document = crud.get_document(db, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    project = crud.get_thread(db, document.thread_id, user_id=user.id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    return project.id


@router.get("", response_model=dict[str, Any])
def get_user_study_progress(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    project_id: str | None = None,
) -> dict[str, Any]:
    """Return factual study records for the authenticated user.

    Restricted to a single Project when ``project_id`` is supplied; ownership is
    verified first so a caller can never read another Project's or Space's
    records by guessing an id.
    """
    if project_id is not None:
        if crud.get_thread(db, project_id, user_id=current_user.id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found."
            )
    return get_study_progress(db, current_user.id, project_id)


@router.post("/quiz-result", status_code=204)
def report_quiz_result(
    payload: QuizResultReport,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    project_id = _owned_project_id(db, payload.document_id, current_user)
    total_questions = len(payload.results)
    correct_count = sum(item.correct for item in payload.results)
    crud.create_quiz_attempt(
        db,
        user_id=current_user.id,
        document_id=payload.document_id,
        topic=payload.topic,
        correct_count=correct_count,
        total_questions=total_questions,
        project_id=project_id,
    )
    if correct_count / total_questions < 0.6:
        record_weak_topic(
            db,
            current_user.id,
            payload.topic,
            f"scored {correct_count}/{total_questions} on {payload.topic}",
            payload.document_id,
            reason="quiz_score",
            project_id=project_id,
        )


@router.post("/flashcard-result", status_code=204)
def report_flashcard_result(
    payload: FlashcardResultReport,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Record a weak topic only when the student explicitly marks cards learning."""
    learning_count = sum(item.status == "learning" for item in payload.cards)
    if learning_count:
        project_id = _owned_project_id(db, payload.document_id, current_user)
        record_weak_topic(
            db,
            current_user.id,
            payload.topic,
            f"marked {learning_count} cards as still learning on {payload.topic}",
            payload.document_id,
            reason="flashcard_learning",
            project_id=project_id,
        )
