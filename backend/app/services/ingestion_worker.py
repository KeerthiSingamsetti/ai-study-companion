"""Background PDF ingestion worker.

The upload endpoint used to run the whole pipeline (parse → chunk → Cohere
embeddings → FAISS build) inline on the request thread. A large PDF took many
minutes, the HTTP connection sat idle, and deployment proxies killed it — the
user saw a generic "request could not be completed" error after a long
spinner.

This module moves that pipeline into a single background daemon thread:

* Upload bytes are persisted to ``backend/upload_media/`` (and renamed to the
  document id) BEFORE the HTTP request returns, so a crash or redeploy right
  after upload never loses the file.
* Jobs are queued in memory and persisted in the ``ingestion_jobs`` table
  (``queued → processing → ready/failed``). ``recover_pending_ingestion_jobs``
  re-enqueues anything left ``queued`` by a restart.
* ``retry`` re-runs a failed job from the persisted upload bytes — no re-upload
  needed.

Embeddings are injected at first use (usually the process-scoped
``LazyEmbeddings`` proxy from ``app.rag.embeddings``) so tests can substitute a
local model. Worker threads never touch the request's SQLAlchemy session; they
open short-lived sessions via ``SessionLocal`` per operation (SQLite WAL keeps
that safe).
"""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from langchain_core.embeddings import Embeddings

from app.db import crud
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_MEDIA_DIR = _BACKEND_DIR / "upload_media"


class UploadMediaStore:
    """Persist raw upload bytes on local disk, keyed by document id.

    ``save`` writes under a temporary name and returns that path so the
    ingestion endpoint can hand a stable file to the worker; ``relocate`` is
    called once the document id is known and renames the file so retries and
    restart recovery can always find the bytes again.
    """

    def __init__(self, base_dir: Path = _MEDIA_DIR) -> None:
        self._base_dir = base_dir
        self._lock = threading.Lock()

    def _document_path(self, document_id: str) -> Path:
        return self._base_dir / f"{document_id}.pdf"

    def _unique_tmp_path(self) -> Path:
        return self._base_dir / f".tmp-{uuid.uuid4().hex}.pdf"

    def _ensure_dir(self) -> None:
        with self._lock:
            self._base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, document_id: str, content: bytes) -> Path:
        """Write upload bytes to disk and return the final document-keyed path."""
        self._ensure_dir()
        final_path = self._document_path(document_id)
        tmp_path = self._unique_tmp_path()
        try:
            tmp_path.write_bytes(content)
            tmp_path.replace(final_path)
        finally:
            tmp_path.unlink(missing_ok=True)
        return final_path

    def resolve(self, document_id: str) -> Optional[Path]:
        """Return the persisted upload path for a document, or None."""
        path = self._document_path(document_id)
        return path if path.is_file() else None

    def purge(self, document_id: str) -> None:
        """Remove the persisted upload (best-effort) when a document is deleted."""
        self._document_path(document_id).unlink(missing_ok=True)


media_store = UploadMediaStore()


class _ProgressEmbeddings(Embeddings):
    """Counting wrapper that reports embedding progress without DB writes.

    Subclasses LangChain's ``Embeddings`` ABC (as ``CohereEmbeddings`` does)
    so FAISS still accepts it. Batching is driven here (mirroring the Cohere
    API's per-request limit) so ``on_batch`` fires after every provider round
    trip rather than once at the end. Provenance identity is excluded from
    this wrapper via ``build_and_save_index(embedding_identity=...)``.
    """

    _BATCH_SIZE = 96  # Cohere embed endpoint maximum

    def __init__(self, inner: Any, on_batch: Callable[[int], None]) -> None:
        self._inner = inner
        self._on_batch = on_batch

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._BATCH_SIZE):
            batch = texts[start : start + self._BATCH_SIZE]
            vectors.extend(self._inner.embed_documents(batch))
            self._on_batch(len(batch))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_query(text)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class IngestionWorker:
    """Single-daemon-thread FIFO processor for PDF ingestion jobs."""

    def __init__(self, embeddings: Any, media_store: Optional[UploadMediaStore] = None) -> None:
        self._embeddings = embeddings
        self.media_store = media_store if media_store is not None else UploadMediaStore()
        self._queue: "queue.Queue[tuple[str, Path]]" = queue.Queue()
        self._enqueued: set[str] = set()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._thread_lock = threading.Lock()
        # In-memory live progress per document (resets on restart):
        # {"phase": "parsing"} or {"phase": "embedding", "total_chunks": int,
        # "processed_chunks": int}. Present only while a job is active.
        self._progress: dict[str, dict[str, Any]] = {}
        self._progress_lock = threading.Lock()

    # -- queue management ----------------------------------------------------

    def _ensure_thread(self) -> None:
        with self._thread_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run,
                name="ingestion-worker",
                daemon=True,
            )
            self._thread.start()

    def enqueue(self, document_id: str, media_path: Path) -> bool:
        """Queue one document for ingestion; False if already pending."""
        with self._lock:
            if document_id in self._enqueued:
                return False
            self._enqueued.add(document_id)
        self._queue.put((document_id, media_path))
        self._ensure_thread()
        return True

    def dequeue(self, document_id: str) -> None:
        """Forget a pending document (best-effort; used on document delete)."""
        with self._lock:
            self._enqueued.discard(document_id)

    def pending_count(self) -> int:
        with self._lock:
            return len(self._enqueued)

    def progress(self, document_id: str) -> Optional[dict[str, Any]]:
        """Live progress for an active ingestion, or None if idle/finished."""
        with self._progress_lock:
            state = self._progress.get(document_id)
            return dict(state) if state else None

    # -- processing ----------------------------------------------------------

    def _run(self) -> None:
        while True:
            document_id, media_path = self._queue.get()
            try:
                self._process_job(document_id, media_path)
            except Exception:  # pragma: no cover - defensive
                logger.exception("Unexpected ingestion worker crash for document %s", document_id)
            finally:
                with self._lock:
                    self._enqueued.discard(document_id)
                self._queue.task_done()

    def _process_job(self, document_id: str, media_path: Path) -> None:
        db = SessionLocal()
        try:
            document = crud.get_document(db, document_id)
            if document is None:
                logger.info("Skipping ingestion for deleted document %s", document_id)
                return
            user_id = document.thread.user_id if document.thread is not None else None
            job = next(
                (j for j in crud.list_ingestion_jobs_for_project(db, document.thread_id)
                 if j.document_id == document_id),
                None,
            )
            if job is None:
                job = crud.create_ingestion_job(
                    db, job_id=str(uuid.uuid4()), document_id=document_id,
                    user_id=user_id or "default_user",
                    project_id=document.thread_id,
                )
            crud.update_ingestion_job_status(db, job.id, "processing")
            with self._progress_lock:
                self._progress[document_id] = {"phase": "parsing"}
            try:
                counts = self._process_document(document_id, media_path)
            except Exception as error:
                logger.exception("Ingestion failed for document %s", document_id)
                db.rollback()
                crud.update_ingestion_job_status(
                    db, job.id, "failed", error_msg=str(error)[:500],
                )
                crud.log_event(
                    db, event_key=f"material:{document_id}:failed",
                    user_id=user_id or "default_user",
                    project_id=document.thread_id,
                    event_type="material_processing_failed",
                    payload_json='{"document_id": "%s", "error": "%s"}'
                    % (document_id, str(error)[:200].replace('"', "'")),
                )
                return
            crud.update_document_counts(
                db, document_id,
                page_count=counts["page_count"], chunk_count=counts["chunk_count"],
            )
            crud.update_ingestion_job_status(db, job.id, "ready", clear_error=True)
            crud.log_event(
                db, event_key=f"material:{document_id}:processed",
                user_id=user_id or "default_user",
                project_id=document.thread_id,
                event_type="material_processing_completed",
                payload_json='{"document_id": "%s", "job_id": "%s"}'
                % (document_id, job.id),
            )
            logger.info(
                "Ingestion ready for document %s (%s pages, %s chunks)",
                document_id, counts["page_count"], counts["chunk_count"],
            )
        finally:
            with self._progress_lock:
                self._progress.pop(document_id, None)
            db.close()

    def _process_document(self, document_id: str, media_path: Path) -> dict[str, int]:
        """Parse, chunk, embed, and persist the index for one uploaded PDF."""
        from app.rag.exceptions import PDFIngestError
        from app.rag.ingest import load_and_chunk_pdf
        from app.rag.store import build_and_save_index, delete_index

        db = SessionLocal()
        try:
            document = crud.get_document(db, document_id)
            if document is None:
                raise PDFIngestError("Document was deleted before ingestion completed.")
            thread_id = document.thread_id
            save_path = document.vectorstore_path
            # Chunk metadata/citations must carry the user's filename, not the
            # internal media name ({document_id}.pdf).
            original_filename = document.filename
        finally:
            db.close()

        content = media_path.read_bytes()
        chunks, metadata = load_and_chunk_pdf(content, filename=original_filename)
        with self._progress_lock:
            self._progress[document_id] = {
                "phase": "embedding",
                "total_chunks": len(chunks),
                "processed_chunks": 0,
            }

        def _on_batch(batch_size: int) -> None:
            with self._progress_lock:
                state = self._progress.get(document_id)
                if state is not None:
                    state["processed_chunks"] = state.get("processed_chunks", 0) + batch_size

        progress_embeddings = _ProgressEmbeddings(self._embeddings, _on_batch)
        try:
            # embedding_identity pins index provenance to the REAL client so
            # later load-time validation matches; the progress wrapper is
            # scaffolding and must not appear in stored metadata.
            build_and_save_index(
                chunks, progress_embeddings, save_path,
                embedding_identity=self._embeddings,
            )
        except Exception:
            delete_index(save_path)
            raise
        return {"page_count": metadata["page_count"], "chunk_count": metadata["chunk_count"]}


_WORKER: Optional[IngestionWorker] = None
_WORKER_LOCK = threading.Lock()


def get_ingestion_worker(embeddings: Any = None) -> IngestionWorker:
    """Return the process-scoped worker, creating it on first use.

    ``embeddings`` is honoured only when the worker is first created; later
    callers may omit it.
    """
    global _WORKER
    with _WORKER_LOCK:
        if _WORKER is None:
            if embeddings is None:
                from app.rag.embeddings import get_embeddings

                embeddings = get_embeddings()
            _WORKER = IngestionWorker(embeddings)
        return _WORKER


def set_ingestion_worker(worker: Optional[IngestionWorker]) -> None:
    """Replace the process-scoped worker (test seam)."""
    global _WORKER
    with _WORKER_LOCK:
        _WORKER = worker


def recover_pending_ingestion_jobs() -> int:
    """Reconcile unfinished ingestion jobs after a restart/redeploy.

    Jobs that never started (``queued``) and documents without job rows are
    re-enqueued. Jobs that died mid-flight (``processing``) are marked
    ``failed`` with a retryable message instead of auto-resuming — resuming
    them immediately crash-looped memory-constrained containers
    (embed → OOM → restart → embed again → Bad Gateway). Returns the number
    of documents re-enqueued.
    """
    from app.config import DEFAULT_USER_ID

    requeued = 0
    failed_stale = 0
    db = SessionLocal()
    try:
        worker = get_ingestion_worker()
        media_store = worker.media_store
        # Jobs that never started are safe to auto-resume.
        for job in crud.list_ingestion_jobs_by_status(db, "queued"):
            document = crud.get_document(db, job.document_id)
            if document is None:
                continue
            media_path = media_store.resolve(document.id)
            if media_path is not None and worker.enqueue(document.id, media_path):
                requeued += 1
        # 'processing' rows are stale after a restart — the process died
        # mid-job. Fail them explicitly; the user retries on a stable service.
        for job in crud.list_ingestion_jobs_by_status(db, "processing"):
            document = crud.get_document(db, job.document_id)
            if document is None:
                continue
            if media_store.resolve(document.id) is not None:
                message = "Ingestion was interrupted by a restart. Press Retry to resume it."
            else:
                message = "Ingestion was interrupted by a restart and the upload file is gone. Upload the PDF again."
            crud.update_ingestion_job_status(db, job.id, "failed", error_msg=message)
            failed_stale += 1
        for document in crud.list_documents_missing_ingestion_jobs(db):
            media_path = media_store.resolve(document.id)
            if media_path is None:
                continue
            user_id = document.thread.user_id if document.thread is not None else None
            crud.create_ingestion_job(
                db, job_id=str(uuid.uuid4()), document_id=document.id,
                user_id=user_id or DEFAULT_USER_ID, project_id=document.thread_id,
            )
            worker.enqueue(document.id, media_path)
            requeued += 1
    finally:
        db.close()
    if requeued:
        logger.info("Re-enqueued %d pending ingestion job(s) after restart.", requeued)
    if failed_stale:
        logger.info("Marked %d interrupted ingestion job(s) as failed (retryable).", failed_stale)
    return requeued
