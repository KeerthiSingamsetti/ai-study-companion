"""Direct API access to the document-grounded flashcard generator."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_embeddings, get_quiz_llm
from app.db import crud
from app.db.models import User
from app.db.session import get_db
from app.schemas.flashcard import FlashcardGenerateRequest, FlashcardGenerateResponse
from app.tools.flashcard_tool import FlashcardGenerationError, generate_flashcards

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


@router.post("/generate", response_model=FlashcardGenerateResponse)
def generate_flashcards_endpoint(
    payload: FlashcardGenerateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    llm: Annotated[BaseChatModel, Depends(get_quiz_llm)],
    embeddings: Annotated[Any, Depends(get_embeddings)],
    db: Annotated[Session, Depends(get_db)],
) -> FlashcardGenerateResponse:
    """Generate flashcards directly for a selected uploaded document owned by user."""
    doc = crud.get_document(db, payload.document_id)
    if doc is None or crud.get_thread(db, doc.thread_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested document does not exist.")
    try:
        return generate_flashcards(
            llm,
            payload.document_id,
            payload.topic,
            payload.num_cards,
            embeddings=embeddings,
            db=db,
        )
    except FlashcardGenerationError as error:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "does not exist" in str(error)
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail=str(error)) from error
