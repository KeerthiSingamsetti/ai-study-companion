"""HTTP contracts for uploaded StudyMate documents."""

from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    """Persisted document metadata returned by document endpoints."""

    id: str
    thread_id: str
    filename: str
    vectorstore_path: str
    page_count: int
    chunk_count: int
    uploaded_at: datetime


class DocumentUploadResponse(BaseModel):
    """Documents successfully ingested and indexed for a thread."""

    documents: list[DocumentResponse]
