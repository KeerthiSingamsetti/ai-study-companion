"""HTTP contracts for StudyMate conversation-thread management."""

from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.chat import DocumentCitation


class ThreadCreateRequest(BaseModel):
    """Create a project inside an explicitly selected Space."""

    title: str = Field(min_length=1, max_length=200)
    space_id: str = Field(min_length=1)


class ThreadRenameRequest(BaseModel):
    """User-selected replacement title for a conversation thread."""

    title: str = Field(min_length=1, max_length=200)


class ThreadResponse(BaseModel):
    """Serialized StudyMate conversation thread."""

    id: str
    title: str
    space_id: str | None = None
    created_at: datetime
    updated_at: datetime


from typing import Any


class ThreadChatMessage(BaseModel):
    """Single message in a thread's conversation history."""

    role: str = Field(description="Message role ('user' or 'assistant').")
    content: str = Field(description="Text content of the message.")
    sources: list[DocumentCitation] = Field(
        default_factory=list,
        description="Optional list of source document citations if retrieval was used.",
    )
    progress_data: dict[str, Any] | None = Field(
        default=None,
        description="Optional snapshot of structured study progress data for thread history.",
    )

