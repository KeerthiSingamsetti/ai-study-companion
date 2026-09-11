"""FastAPI endpoints for thread-scoped PDF documents."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_document_service
from app.db.session import get_db
from app.rag.exceptions import PDFIngestError
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.services.document_service import DocumentNotFoundError, DocumentService, ThreadNotFoundForDocumentError

router = APIRouter(tags=["documents"])


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
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Annotated[Session, Depends(get_db)],
    files: list[UploadFile] = File(...),
) -> DocumentUploadResponse:
    """Ingest one or more PDF uploads into independent persisted indexes."""
    if any(
        file.content_type not in {"application/pdf", "application/x-pdf"}
        and not (file.filename or "").lower().endswith(".pdf")
        for file in files
    ):
        raise HTTPException(status_code=415, detail="Only PDF uploads are supported.")
    payloads = [(file.filename or "document.pdf", await file.read()) for file in files]
    try:
        documents = service.upload(db, thread_id, payloads)
    except ThreadNotFoundForDocumentError as error:
        raise HTTPException(status_code=404, detail="Thread not found.") from error
    except PDFIngestError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return DocumentUploadResponse(documents=[_serialize(document) for document in documents])


@router.get("/threads/{thread_id}/documents", response_model=list[DocumentResponse])
def list_documents(thread_id: str, service: Annotated[DocumentService, Depends(get_document_service)], db: Annotated[Session, Depends(get_db)]) -> list[DocumentResponse]:
    """List documents uploaded to an existing thread."""
    try:
        return [_serialize(document) for document in service.list_for_thread(db, thread_id)]
    except ThreadNotFoundForDocumentError as error:
        raise HTTPException(status_code=404, detail="Thread not found.") from error


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, service: Annotated[DocumentService, Depends(get_document_service)], db: Annotated[Session, Depends(get_db)]) -> None:
    """Delete one document and its persisted FAISS index."""
    try:
        service.delete(db, document_id)
    except DocumentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Document not found.") from error
