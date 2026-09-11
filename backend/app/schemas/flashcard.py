"""Pydantic contracts for document-grounded flashcard generation."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Flashcard(BaseModel):
    """One recall-based study flashcard grounded in an uploaded document."""

    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    hint: Optional[str] = None


class FlashcardGenerateRequest(BaseModel):
    """Parameters selecting document context and flashcard characteristics."""

    document_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    num_cards: int = Field(default=10, ge=1, le=25)


class FlashcardGenerateResponse(BaseModel):
    """Structured flashcard result consumable by a flashcard workspace."""

    type: Literal["tool_result"] = "tool_result"
    tool: Literal["flashcards"] = "flashcards"
    document_id: str
    topic: str
    cards: list[Flashcard]
