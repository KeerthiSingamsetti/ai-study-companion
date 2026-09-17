"""Validated contracts for open-ended assessment grading."""
from pydantic import BaseModel, Field


class OpenEndedGrade(BaseModel):
    understanding: float = Field(ge=0, le=100)
    accuracy: float = Field(ge=0, le=100)
    concepts_covered: list[str]
    concepts_missing: list[str]
    feedback: str = Field(min_length=1)

    @property
    def overall_score(self) -> float:
        return round((self.understanding + self.accuracy) / 2, 2)
