"""Business operations for PDF ingestion and persisted vector stores."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db import crud
from app.db.models import Document

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_VECTORSTORE_DIR = _BACKEND_DIR / "vectorstores"


class ThreadNotFoundForDocumentError(LookupError):
    """Raised when a document operation references an absent thread."""


class DocumentNotFoundError(LookupError):
    """Raised when a document operation references an absent document."""


class DocumentService:
    """Ingest PDFs and coordinate their existing FAISS stores with CRUD records."""

    def __init__(self, embeddings: Any) -> None:
        self._embeddings = embeddings

    def upload(self, db: Session, thread_id: str, files: list[tuple[str, bytes]]) -> list[Document]:
        """Chunk, index, and persist one or more PDFs for an existing thread."""
        if crud.get_thread(db, thread_id) is None:
            raise ThreadNotFoundForDocumentError(thread_id)

        documents: list[Document] = []
        from app.rag.ingest import load_and_chunk_pdf
        from app.rag.store import build_and_save_index, delete_index

        for filename, content in files:
            document_id = str(uuid4())
            save_path = _VECTORSTORE_DIR / thread_id / document_id
            chunks, metadata = load_and_chunk_pdf(content, filename=filename)
            try:
                build_and_save_index(chunks, self._embeddings, str(save_path))
                documents.append(crud.create_document(
                    db,
                    document_id=document_id,
                    thread_id=thread_id,
                    filename=filename,
                    vectorstore_path=str(save_path),
                    page_count=metadata["page_count"],
                    chunk_count=metadata["chunk_count"],
                ))
            except Exception:
                delete_index(str(save_path))
                raise
        return documents

    def list_for_thread(self, db: Session, thread_id: str) -> list[Document]:
        """Return documents for an existing thread."""
        if crud.get_thread(db, thread_id) is None:
            raise ThreadNotFoundForDocumentError(thread_id)
        return crud.list_documents_for_thread(db, thread_id)

    def delete(self, db: Session, document_id: str) -> None:
        """Remove a persisted vector store and its database record."""
        document = crud.get_document(db, document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)
        from app.rag.store import delete_index

        delete_index(document.vectorstore_path)
        crud.delete_document(db, document_id)
