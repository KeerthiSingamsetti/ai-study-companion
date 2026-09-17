"""Application service for StudyMate conversation-thread lifecycle."""

from __future__ import annotations

from uuid import uuid4
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import crud
from app.db.models import Thread

DEFAULT_THREAD_TITLE = "New Chat"
_MAX_AUTOMATIC_TITLE_LENGTH = 60


class ThreadNotFoundError(LookupError):
    """Raised when a requested StudyMate thread does not exist."""


class ThreadService:
    """Create, validate, title, and rename database-backed chat threads."""

    def resolve_thread(self, db: Session, thread_id: str | None, user_id: str) -> Thread:
     """Return an existing thread owned by user_id, or create a new one for them."""
     if thread_id is None:
        thread = crud.create_thread(
            db, thread_id=str(uuid4()), title=DEFAULT_THREAD_TITLE, user_id=user_id
        )
        crud.log_event(db, event_key=f"project:{thread.id}:created", user_id=user_id,
                       project_id=thread.id, event_type="project_created",
                       payload_json=json.dumps({"title": thread.title}))
        return thread

     thread = crud.get_thread(db, thread_id)
     if thread is None or thread.user_id != user_id:
         raise ThreadNotFoundError(f"Thread {thread_id!r} does not exist.")
     return thread

    def rename_thread(self, db: Session, thread_id: str, title: str) -> Thread:
        """Persist a user-selected thread title."""
        normalized_title = " ".join(title.split())
        if not normalized_title:
            raise ValueError("Thread title must contain non-whitespace characters.")
        thread = crud.update_thread_title(
            db, thread_id=thread_id, title=normalized_title
        )
        if thread is None:
            raise ThreadNotFoundError(f"Thread {thread_id!r} does not exist.")
        return thread

    def list_threads(self, db: Session) -> list[Thread]:
        """Return all persisted threads ordered by latest update."""
        return crud.list_threads(db)

    def study_log(self, db: Session, thread_id: str):
        """Return study activity for an existing thread."""
        if crud.get_thread(db, thread_id) is None:
            raise ThreadNotFoundError(f"Thread {thread_id!r} does not exist.")
        return crud.get_study_log_for_thread(db, thread_id)

    def touch_thread(self, db: Session, thread_id: str) -> None:
        """Bump updated_at so this thread sorts first in list_threads."""
        crud.touch_thread(db, thread_id)

    def delete_thread(self, db: Session, thread_id: str) -> None:
        """Delete a thread, its database dependents, and owned FAISS indexes."""
        if crud.get_thread(db, thread_id) is None:
            raise ThreadNotFoundError(f"Thread {thread_id!r} does not exist.")
        from app.rag.store import delete_index

        for document in crud.list_documents_for_thread(db, thread_id):
            delete_index(document.vectorstore_path)
        crud.delete_thread(db, thread_id)

    def set_automatic_title(
        self, db: Session, thread_id: str, first_user_message: str
    ) -> Thread | None:
        """Set an initial title once, without overwriting a renamed thread."""
        thread = crud.get_thread(db, thread_id)
        if thread is None or thread.title != DEFAULT_THREAD_TITLE:
            return thread

        return crud.update_thread_title(
            db,
            thread_id=thread_id,
            title=self._generate_title(first_user_message),
        )

    @staticmethod
    def _generate_title(message: str) -> str:
        """Create a stable, concise initial title without another LLM request."""
        normalized_message = " ".join(message.split())
        if len(normalized_message) <= _MAX_AUTOMATIC_TITLE_LENGTH:
            return normalized_message or DEFAULT_THREAD_TITLE
        return f"{normalized_message[:_MAX_AUTOMATIC_TITLE_LENGTH - 1].rstrip()}…"
