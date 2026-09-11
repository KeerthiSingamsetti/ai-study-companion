"""Pydantic contracts for document-grounded quiz generation."""

from typing import Literal

from pydantic import BaseModel, Field


class QuizQuestion(BaseModel):
    """One multiple-choice question grounded in an uploaded document."""

    question: str
    options: list[str] = Field(min_length=2)
    correct_index: int = Field(ge=0)
    explanation: str
    source_citation: str | None = None



class QuizGenerateRequest(BaseModel):
    """Parameters selecting document context and quiz characteristics."""

    document_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    num_questions: int = Field(default=10, ge=1, le=25)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class QuizGenerateResponse(BaseModel):
    """Structured quiz result consumable by a quiz workspace."""

    type: Literal["tool_result"] = "tool_result"
    tool: Literal["quiz"] = "quiz"
    document_id: str
    topic: str
    difficulty: str
    questions: list[QuizQuestion]
