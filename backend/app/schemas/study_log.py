"""HTTP contracts for StudyMate study activity history."""

from datetime import datetime

from pydantic import BaseModel


class StudyLogResponse(BaseModel):
    """One persisted study activity entry."""

    id: int
    thread_id: str
    document_id: str | None
    event_type: str
    topic: str | None
    created_at: datetime
