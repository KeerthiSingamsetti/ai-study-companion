"""HTTP contracts for StudyMate conversation-thread management."""

from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.chat import DocumentCitation


class ThreadCreateRequest(BaseModel):
    """Create a project inside an explicitly selected Space.

    A Project is the core learning workspace: the name says what it is, the
    description says what it covers, and the learning goal says where the
    learner is heading.
    """

    title: str = Field(min_length=1, max_length=200)
    space_id: str = Field(min_length=1)
    description: str | None = Field(default=None, max_length=2000)
    learning_goal: str | None = Field(default=None, max_length=2000)


class ThreadUpdateRequest(BaseModel):
    """Partial update for a project's title, description or learning goal."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    learning_goal: str | None = Field(default=None, max_length=2000)

    def has_changes(self) -> bool:
        return any(value is not None for value in (self.title, self.description, self.learning_goal))


# Backwards-compatible alias for callers that only rename.
ThreadRenameRequest = ThreadUpdateRequest


class ThreadResponse(BaseModel):
    """Serialized StudyMate conversation thread."""

    id: str
    title: str
    space_id: str | None = None
    description: str | None = None
    learning_goal: str | None = None
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

