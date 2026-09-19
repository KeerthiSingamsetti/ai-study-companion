"""Business operations for PDF ingestion and persisted vector stores.

Uploads are asynchronous: the service persists the raw upload to disk, creates
the ``documents`` and ``ingestion_jobs`` rows, and hands the file to the
background ingestion worker before the HTTP response returns. The heavy
pipeline (parse → chunk → embed → FAISS) runs off the request thread and its
progress is visible through the ingestion-jobs endpoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import DEFAULT_USER_ID
from app.db import crud
from app.db.models import Document

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_VECTORSTORE_DIR = _BACKEND_DIR / "vectorstores"


class ThreadNotFoundForDocumentError(LookupError):
    """Raised when a document operation references an absent thread."""


class DocumentNotFoundError(LookupError):
    """Raised when a document operation references an absent document."""


class DocumentService:
    """Queue PDFs for background ingestion and manage their FAISS stores."""

    def __init__(self, embeddings: Any) -> None:
        self._embeddings = embeddings

    def _worker(self):
        # Imported lazily so importing this module never pulls the worker (or
        # the embeddings stack) into unrelated processes such as scripts.
        from app.services.ingestion_worker import get_ingestion_worker

        return get_ingestion_worker(self._embeddings)

    def upload(self, db: Session, thread_id: str, files: list[tuple[str, bytes]]) -> list[Document]:
        """Persist upload media and queue each PDF for background ingestion.

        Returns the document rows immediately with zero page/chunk counts; the
        ingestion job (visible via ``/threads/{id}/ingestion-jobs``) moves the
        row to ``ready`` once the index is built.
        """
        thread = crud.get_thread(db, thread_id)
        if thread is None:
            raise ThreadNotFoundForDocumentError(thread_id)

        worker = self._worker()
        documents: list[Document] = []
        for filename, content in files:
            document_id = str(uuid4())
            save_path = str(_VECTORSTORE_DIR / thread_id / document_id)
            document = crud.create_document(
                db,
                document_id=document_id,
                thread_id=thread_id,
                filename=filename,
                vectorstore_path=save_path,
                page_count=0,
                chunk_count=0,
            )
            # Upload bytes land in the database (FK requires the row above to
            # exist first) BEFORE this request returns — they must survive any
            # restart or redeploy.
            worker.media_store.save(document_id, content)
            # Persisted immediately so the polling UI sees 'queued' even if the
            # process restarts before the worker picks the job up.
            crud.create_ingestion_job(
                db, job_id=str(uuid4()), document_id=document_id,
                user_id=(thread.user_id if thread is not None else None) or DEFAULT_USER_ID,
                project_id=thread_id,
            )
            worker.enqueue(document_id)
            documents.append(document)
        return documents

    def retry_document(self, db: Session, document_id: str) -> bool:
        """Re-enqueue ingestion for a document; False if its upload is gone."""
        document = crud.get_document(db, document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)
        worker = self._worker()
        if worker.media_store.resolve_bytes(document_id) is None:
            return False
        worker.enqueue(document_id)
        return True

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

        # Keep the upload media until the row is gone so a queued retry after
        # a transient delete failure can still recover the bytes.
        delete_index(document.vectorstore_path)
        crud.delete_document(db, document_id)
        try:
            self._worker().media_store.purge(document_id)
        except Exception:
            pass
