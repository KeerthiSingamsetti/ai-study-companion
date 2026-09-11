"""FastAPI endpoints for StudyMate conversation threads."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_chat_service, get_thread_service
from app.db import crud
from app.db.session import get_db
from app.schemas.study_log import StudyLogResponse
from app.schemas.thread import ThreadChatMessage, ThreadRenameRequest, ThreadResponse
from app.services.chat_service import ChatService
from app.services.thread_service import ThreadNotFoundError, ThreadService

router = APIRouter(prefix="/threads", tags=["threads"])


def _thread_response(thread) -> ThreadResponse:
    return ThreadResponse(id=thread.id, title=thread.title, created_at=thread.created_at, updated_at=thread.updated_at)


@router.patch("/{thread_id}", response_model=ThreadResponse)
def rename_thread(
    thread_id: str,
    payload: ThreadRenameRequest,
    thread_service: Annotated[ThreadService, Depends(get_thread_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ThreadResponse:
    """Persist a manually selected title for an existing conversation."""
    try:
        thread = thread_service.rename_thread(db, thread_id, payload.title)
    except ThreadNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found."
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    return _thread_response(thread)


@router.get("", response_model=list[ThreadResponse])
def list_threads(
    thread_service: Annotated[ThreadService, Depends(get_thread_service)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ThreadResponse]:
    """List conversation threads ordered by their most recent update."""
    return [_thread_response(thread) for thread in thread_service.list_threads(db)]


@router.get("/{thread_id}/messages", response_model=list[ThreadChatMessage], response_model_exclude_none=True)
def get_thread_messages(

    thread_id: str,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ThreadChatMessage]:
    """Return chronological conversation history reconstructed from LangGraph state for an existing thread."""
    if crud.get_thread(db, thread_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found."
        )
    return chat_service.get_thread_history(thread_id)


@router.get("/{thread_id}/study-log", response_model=list[StudyLogResponse])
def get_study_log(
    thread_id: str,
    thread_service: Annotated[ThreadService, Depends(get_thread_service)],
    db: Annotated[Session, Depends(get_db)],
) -> list[StudyLogResponse]:
    """Return study activity for one existing thread."""
    try:
        entries = thread_service.study_log(db, thread_id)
    except ThreadNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.") from error
    return [StudyLogResponse(id=entry.id, thread_id=entry.thread_id, document_id=entry.document_id, event_type=entry.event_type, topic=entry.topic, created_at=entry.created_at) for entry in entries]


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(
    thread_id: str,
    thread_service: Annotated[ThreadService, Depends(get_thread_service)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete a thread and its owned vector stores, retaining checkpoints."""
    try:
        thread_service.delete_thread(db, thread_id)
    except ThreadNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.") from error
