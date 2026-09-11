"""HTTP contracts for the stateless chat endpoint."""

from pydantic import BaseModel, Field


class DocumentCitation(BaseModel):
    """Citation metadata for a source document page used by the assistant."""

    document: str = Field(description="The original filename of the document.")
    page: int | None = Field(default=None, description="The 1-indexed page number if available.")


class ChatRequest(BaseModel):
    """A single user message submitted to the chat endpoint."""

    message: str = Field(min_length=1, description="The user's message to StudyMate.")
    thread_id: str | None = Field(
        default=None,
        min_length=1,
        description="Optional conversation identifier for short-term memory.",
    )
    stream: bool = Field(
        default=False,
        description="Emit completed chat and structured tool results as SSE events.",
    )


class ChatResponse(BaseModel):
    """The assistant message returned by the chat endpoint."""

    message: str
    thread_id: str
    sources: list[DocumentCitation] = Field(
        default_factory=list,
        description="Optional list of source document citations if retrieval was used.",
    )
