"""Direct API access to the document-grounded quiz generator."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_embeddings, get_quiz_llm
from app.db.session import get_db
from app.schemas.quiz import QuizGenerateRequest, QuizGenerateResponse
from app.tools.quiz_generator_tool import QuizGenerationError, generate_quiz

router = APIRouter(prefix="/quiz", tags=["quiz"])


@router.post("/generate", response_model=QuizGenerateResponse)
def generate_quiz_endpoint(
    payload: QuizGenerateRequest,
    llm: Annotated[BaseChatModel, Depends(get_quiz_llm)],
    embeddings: Annotated[Any, Depends(get_embeddings)],
    db: Annotated[Session, Depends(get_db)],
) -> QuizGenerateResponse:
    """Generate a quiz directly for a selected uploaded document."""
    try:
        return generate_quiz(
            llm,
            payload.document_id,
            payload.topic,
            payload.num_questions,
            payload.difficulty,
            embeddings=embeddings,
            db=db,
        )
    except QuizGenerationError as error:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "does not exist" in str(error)
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail=str(error)) from error
