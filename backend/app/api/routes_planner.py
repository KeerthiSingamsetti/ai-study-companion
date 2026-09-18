"""Direct API access to the study plan generator."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_quiz_llm
from app.db import crud
from app.db.models import User
from app.db.session import get_db
from app.schemas.planner import StudyPlanRequest, StudyPlanResponse
from app.tools.study_planner_tool import StudyPlanGenerationError, generate_study_plan

router = APIRouter(prefix="/planner", tags=["planner"])


@router.post("/generate", response_model=StudyPlanResponse)
def generate_plan(
    payload: StudyPlanRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    llm: Annotated[object, Depends(get_quiz_llm)],
    db: Annotated[Session, Depends(get_db)],
) -> StudyPlanResponse:
    """Generate a study plan directly for a document owned by user."""
    doc = crud.get_document(db, payload.document_id)
    if doc is None or crud.get_thread(db, doc.thread_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested document does not exist.")
    try:
        return generate_study_plan(
            llm,
            payload.document_id,
            payload.topics,
            payload.num_days,
            payload.exam_date,
            user_id=current_user.id,
            project_id=doc.thread_id,
        )
    except StudyPlanGenerationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
