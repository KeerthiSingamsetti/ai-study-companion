"""Contracts for document-grounded study plans."""
from typing import Literal
from pydantic import BaseModel, Field

class StudyPlanRequest(BaseModel):
    document_id: str
    topics: list[str] | None = None
    num_days: int = Field(default=7, ge=1, le=30)
    exam_date: str | None = None

class DayPlan(BaseModel):
    day: int
    topics: list[str]
    focus: str
    tasks: list[str]

class StudyPlanResponse(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool: Literal["study_planner"] = "study_planner"
    document_id: str
    num_days: int
    days: list[DayPlan]
