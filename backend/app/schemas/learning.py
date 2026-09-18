"""Validated contracts for the learning loop: quiz evidence, open-ended assessment and next steps.

Mastery is an estimate that evolves as new evidence arrives, so every write
endpoint here returns the refreshed mastery/growth snapshot rather than a bare
acknowledgement.
"""

from typing import Literal

from pydantic import BaseModel, Field

Difficulty = Literal["easy", "medium", "hard"]


# ---------------------------------------------------------------------------
# Adaptive quiz evidence
# ---------------------------------------------------------------------------

class QuizResultItem(BaseModel):
    """One answered multiple-choice question."""

    question: str = ""
    correct: bool


class QuizResultRequest(BaseModel):
    """Client-reported adaptive quiz outcome, scoped to one project and concept."""

    project_id: str = Field(min_length=1)
    document_id: str | None = None
    topic: str = Field(min_length=1)
    concept: str | None = None
    difficulty: Difficulty = "medium"
    results: list[QuizResultItem] = Field(min_length=1)


class MasterySnapshot(BaseModel):
    concept: str
    concept_id: str
    score: float
    attempts: int
    growth: dict


class QuizResultResponse(BaseModel):
    answered: int
    correct: int
    score: float
    mastery: MasterySnapshot | None = None
    recommendations: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Open-ended assessment
# ---------------------------------------------------------------------------

class AssessmentQuestion(BaseModel):
    id: str
    question: str
    reference_answer: str
    rubric: str = "Assess conceptual understanding, factual accuracy, relevance, and reasoning."
    source_citation: str | None = None


class AssessmentGenerateRequest(BaseModel):
    project_id: str = Field(min_length=1)
    concept: str = Field(min_length=1)
    document_id: str | None = None
    num_questions: int = Field(default=1, ge=1, le=5)
    difficulty: Difficulty = "medium"


class AssessmentGenerateResponse(BaseModel):
    project_id: str
    concept: str
    difficulty: str
    grounded: bool
    questions: list[AssessmentQuestion]


class AssessmentGradeRequest(BaseModel):
    project_id: str = Field(min_length=1)
    concept: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    reference_answer: str = ""
    rubric: str = "Assess conceptual understanding, factual accuracy, relevance, and reasoning."
    document_id: str | None = None
    difficulty: Difficulty = "medium"


class AssessmentGradeResponse(BaseModel):
    understanding: float
    accuracy: float
    overall_score: float
    concepts_covered: list[str]
    concepts_missing: list[str]
    feedback: str
    mastery: MasterySnapshot | None = None
    assessment_average: float | None = None
    recommendations: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# History / growth views
# ---------------------------------------------------------------------------

class ConceptGrowth(BaseModel):
    concept: str
    concept_id: str
    score: float
    attempts: int
    classification: str
    delta: float
    samples: int
    history: list[dict] = Field(default_factory=list)


class AssessmentHistoryItem(BaseModel):
    id: int
    concept: str | None = None
    question: str
    answer: str
    understanding: float
    accuracy: float
    overall_score: float
    feedback: str = ""
    created_at: object


class AssessmentSummaryResponse(BaseModel):
    project_id: str
    assessment_average: float | None = None
    graded_count: int
    overall_progress: float | None = None
    growth: list[ConceptGrowth] = Field(default_factory=list)
    history: list[AssessmentHistoryItem] = Field(default_factory=list)
    recommendations: list[dict] = Field(default_factory=list)
