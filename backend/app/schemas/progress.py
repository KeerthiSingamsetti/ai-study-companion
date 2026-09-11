"""Client-reported local quiz and flashcard session outcomes."""
from typing import Literal
from pydantic import BaseModel, Field

class QuizQuestionResult(BaseModel):
    question: str
    correct: bool

class QuizResultReport(BaseModel):
    document_id: str
    topic: str
    results: list[QuizQuestionResult] = Field(min_length=1)

class FlashcardStatusResult(BaseModel):
    front: str
    status: Literal["known", "learning"]

class FlashcardResultReport(BaseModel):
    document_id: str
    topic: str
    cards: list[FlashcardStatusResult]
