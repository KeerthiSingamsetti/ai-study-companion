"""FastAPI endpoints for thread-scoped PDF documents.

Uploads return immediately with a ``queued`` ingestion job; the heavy
parse/embed/index pipeline runs in the background worker
(``app.services.ingestion_worker``) and its progress is exposed through the
ingestion-jobs endpoints.
"""

from typing import Annotated
import gc
import json
import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_document_service
from app.db import crud
from app.db.models import User
from app.db.session import get_db
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.services.document_service import DocumentNotFoundError, DocumentService, ThreadNotFoundForDocumentError
from app.services.ingestion_worker import get_ingestion_worker, sweep_stalled_jobs

router = APIRouter(tags=["documents"])

# A compact instance cannot buffer an arbitrary upload: the bytes are read into
# memory once for the response and copied again through the database round trip.
# Reject oversized files up front with an actionable message instead of holding
# them and being OOM-killed mid-request (which returns 502 to everyone).
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "25"))
_MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def _too_large_detail(name: str) -> str:
    return (
        f"{name} is larger than this server's {MAX_UPLOAD_MB:.0f} MB upload limit. "
        "Split the PDF and upload the parts, or use a smaller file."
    )


def _serialize(document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        thread_id=document.thread_id,
        filename=document.filename,
        vectorstore_path=document.vectorstore_path,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        uploaded_at=document.uploaded_at,
    )


@router.post(
    "/threads/{thread_id}/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["files"],
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary"},
                            }
                        },
                    }
                }
            }
        }
    },
)
async def upload_documents(
    thread_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
    files: list[UploadFile] = File(...),
) -> DocumentUploadResponse:
    """Ingest one or more PDF uploads into independent persisted indexes for an owned project."""
    if crud.get_thread(db, thread_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="Thread not found.")
    if any(
        file.content_type not in {"application/pdf", "application/x-pdf"}
        and not (file.filename or "").lower().endswith(".pdf")
        for file in files
    ):
        raise HTTPException(status_code=415, detail="Only PDF uploads are supported.")
    # Reject on the declared size first: an oversized file must never be read
    # into memory at all. ``size`` is None for some multipart encodings, so the
    # read length is checked again below.
    for file in files:
        declared = getattr(file, "size", None)
        if declared is not None and declared > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=_too_large_detail(file.filename or "This file"))
    payloads = [(file.filename or "document.pdf", await file.read()) for file in files]
    for name, content in payloads:
        if len(content) > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=_too_large_detail(name))
    try:
        documents = service.upload(db, thread_id, payloads)
    except ThreadNotFoundForDocumentError as error:
        raise HTTPException(status_code=404, detail="Thread not found.") from error
    except OSError as error:
        raise HTTPException(status_code=500, detail="Could not store the uploaded file.") from error
    finally:
        # The bytes are already persisted durably; holding a second reference
        # while the response is serialized only inflates peak memory.
        payloads = []
        gc.collect()
    for document in documents:
        # Jobs are created by the upload service and managed by the background
        # worker; here we only record the upload event for the activity feed.
        crud.log_event(db, event_key=f"material:{document.id}:uploaded", user_id=current_user.id,
                       project_id=thread_id, event_type="material_uploaded",
                       payload_json=json.dumps({"document_id": document.id, "filename": document.filename}))
    return DocumentUploadResponse(documents=[_serialize(document) for document in documents])


@router.get("/threads/{thread_id}/ingestion-jobs")
def list_ingestion_jobs(
    thread_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    if crud.get_thread(db, thread_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="Thread not found.")
    # Self-healing: fail jobs stuck in 'processing' that no live worker is
    # running (cheap query, runs alongside the UI's 4s polling).
    try:
        sweep_stalled_jobs()
    except Exception:  # pragma: no cover - never block the listing
        pass
    worker = get_ingestion_worker()
    return [{"id": job.id, "document_id": job.document_id, "status": job.status,
             "retry_count": job.retry_count, "error_msg": job.error_msg,
             "progress": worker.progress(job.document_id),
             "created_at": job.created_at, "updated_at": job.updated_at}
            for job in crud.list_ingestion_jobs_for_project(db, thread_id)]


@router.post("/ingestion-jobs/{job_id}/retry")
def retry_ingestion_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    job = crud.get_ingestion_job(db, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ingestion job not found.")
    if job.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed ingestion jobs can be retried.")
    # Mark queued BEFORE enqueueing: the worker only ever moves the status
    # forward, so it can never race this update back to 'queued' after it has
    # already finished the retried job.
    updated = crud.update_ingestion_job_status(db, job.id, "queued", retry_count=job.retry_count + 1, error_msg=None)
    if updated is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found.")
    try:
        enqueued = service.retry_document(db, job.document_id)
    except DocumentNotFoundError as error:
        # Keep the job retryable rather than stranding it in 'queued'.
        crud.update_ingestion_job_status(db, job.id, "failed", error_msg="Retry failed: document is missing.")
        raise HTTPException(status_code=404, detail="Document not found.") from error
    if not enqueued:
        crud.update_ingestion_job_status(
            db, job.id, "failed",
            error_msg="Original upload file is no longer stored; upload the PDF again.",
        )
        raise HTTPException(
            status_code=409,
            detail="The original upload file is no longer stored; please upload the PDF again.",
        )
    crud.log_event(db, event_key=f"ingestion:{job.id}:retry:{updated.retry_count}", user_id=current_user.id,
                   project_id=job.project_id, event_type="material_processing_started",
                   payload_json=json.dumps({"job_id": job.id, "retry_count": updated.retry_count}))
    return {"id": updated.id, "status": updated.status, "retry_count": updated.retry_count}


@router.get("/threads/{thread_id}/documents", response_model=list[DocumentResponse])
def list_documents(
    thread_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DocumentResponse]:
    """List documents uploaded to an existing thread owned by current user."""
    if crud.get_thread(db, thread_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="Thread not found.")
    try:
        return [_serialize(document) for document in service.list_for_thread(db, thread_id)]
    except ThreadNotFoundForDocumentError as error:
        raise HTTPException(status_code=404, detail="Thread not found.") from error


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete one document owned by current user and its persisted FAISS index."""
    doc = crud.get_document(db, document_id)
    if doc is None or crud.get_thread(db, doc.thread_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        service.delete(db, document_id)
    except DocumentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Document not found.") from error
