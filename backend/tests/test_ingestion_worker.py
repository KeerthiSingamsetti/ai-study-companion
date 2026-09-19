"""Background PDF upload/ingestion lifecycle regression tests.

Regression: the upload route used to ingest inline on the request thread, so a
large PDF held the HTTP connection for many minutes until the deployment proxy
killed it and the UI showed the generic "The request could not be completed."
error. Uploads must now return immediately with a queued job while a background
worker performs parse → chunk → embed → FAISS.
"""

import io
import threading
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

import app.rag.ingest as ingest_module
from app.db import crud
from app.db.session import SessionLocal
from app.main import app
from app.services import ingestion_worker as worker_module
from app.services.document_service import DocumentService
from app.services.ingestion_worker import IngestionWorker, UploadMediaStore, recover_pending_ingestion_jobs


def _pdf_bytes(text: str = "StudyMate ingestion worker test page.") -> bytes:
    buffer = io.BytesIO()
    canvas_obj = canvas.Canvas(buffer)
    canvas_obj.drawString(100, 750, text)
    canvas_obj.showPage()
    canvas_obj.save()
    return buffer.getvalue()


class InstantEmbeddings:
    """Deterministic local embeddings so tests never touch the network."""

    def embed_documents(self, texts):
        return [[float(len(text) % 7), 1.0, 0.5] for text in texts]

    def embed_query(self, text):
        return [float(len(text) % 7), 1.0, 0.5]


@pytest.fixture()
def fast_worker(monkeypatch, tmp_path):
    """Replace the process worker with a deterministic local-model one.

    The session TestClient does not run the app lifespan, so the document
    service dependency is wired here as well.
    """
    worker = IngestionWorker(InstantEmbeddings(), media_store=UploadMediaStore(base_dir=tmp_path))
    monkeypatch.setattr(worker_module, "_WORKER", worker, raising=False)
    app.state.document_service = DocumentService(InstantEmbeddings())
    yield worker
    monkeypatch.setattr(worker_module, "_WORKER", None, raising=False)


def _wait_for_status(worker: IngestionWorker, document_id: str, statuses: set[str], timeout: float = 10.0) -> str:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        db = SessionLocal()
        try:
            document = crud.get_document(db, document_id)
            assert document is not None
            job = next(
                (j for j in crud.list_ingestion_jobs_for_project(db, document.thread_id)
                 if j.document_id == document_id),
                None,
            )
            last = job.status if job else "missing"
            if last in statuses:
                return last
        finally:
            db.close()
        time.sleep(0.05)
    raise AssertionError(f"Job for {document_id} never reached {statuses}; last status {last!r}")


def _create_project(test_client: TestClient, auth_headers: dict) -> str:
    space = test_client.post("/spaces", headers=auth_headers, json={"name": f"Worker {uuid.uuid4()}"}).json()
    project = test_client.post("/threads", headers=auth_headers, json={"title": "Ingestion", "space_id": space["id"]}).json()
    return project["id"]


def _upload(test_client: TestClient, auth_headers: dict, thread_id: str, filename: str = "notes.pdf") -> dict:
    response = test_client.post(
        f"/threads/{thread_id}/documents/upload",
        headers=auth_headers,
        files={"files": (filename, _pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["documents"][0]


def _first_job(test_client: TestClient, auth_headers: dict, thread_id: str, document_id: str) -> dict:
    jobs = test_client.get(f"/threads/{thread_id}/ingestion-jobs", headers=auth_headers).json()
    return next(job for job in jobs if job["document_id"] == document_id)


def test_upload_returns_immediately_with_queued_job(test_client, auth_headers, fast_worker):
    # Hold the embeddings hostage so the background worker provably cannot
    # finish while the request is being served.
    gate = threading.Event()

    class Gated(InstantEmbeddings):
        def embed_documents(self, texts):
            gate.wait(timeout=10)
            return super().embed_documents(texts)

    fast_worker._embeddings = Gated()
    try:
        thread_id = _create_project(test_client, auth_headers)
        document = _upload(test_client, auth_headers, thread_id)
        assert document["page_count"] == 0 and document["chunk_count"] == 0
        # The response is back while embeddings are still gated — ingestion did
        # not block the request. Either pre-worker state is acceptable.
        job = _first_job(test_client, auth_headers, thread_id, document["id"])
        assert job["status"] in {"queued", "processing"}
    finally:
        gate.set()
    assert _wait_for_status(fast_worker, document["id"], {"ready"}) == "ready"


def test_worker_processes_upload_to_ready(test_client, auth_headers, fast_worker):
    thread_id = _create_project(test_client, auth_headers)
    document = _upload(test_client, auth_headers, thread_id)

    assert _wait_for_status(fast_worker, document["id"], {"ready", "failed"}) == "ready"

    docs = test_client.get(f"/threads/{thread_id}/documents", headers=auth_headers).json()
    updated = next(d for d in docs if d["id"] == document["id"])
    assert updated["page_count"] == 1
    assert updated["chunk_count"] > 0


def test_failed_ingestion_records_error_and_retry_recovers(test_client, auth_headers, fast_worker, monkeypatch):
    thread_id = _create_project(test_client, auth_headers)
    document = _upload(test_client, auth_headers, thread_id, filename="broken.pdf")
    assert _wait_for_status(fast_worker, document["id"], {"ready"}) == "ready"

    # Force the next attempt to fail inside the parse step, and drive that
    # attempt through the worker so the job honestly reaches 'failed'. A
    # separate patch object: undoing the fixture monkeypatch would also remove
    # the _WORKER test seam.
    def boom(*args, **kwargs):
        raise RuntimeError("disk exploded")

    fault_patch = pytest.MonkeyPatch()
    try:
        fault_patch.setattr(ingest_module, "load_and_chunk_pdf", boom)
        job_id = _first_job(test_client, auth_headers, thread_id, document["id"])["id"]
        assert fast_worker.enqueue(
            document["id"], fast_worker.media_store.resolve(document["id"])
        )
        assert _wait_for_status(fast_worker, document["id"], {"failed"}) == "failed"
    finally:
        fault_patch.undo()

    # Remove the fault and retry through the API.
    retry = test_client.post(f"/ingestion-jobs/{job_id}/retry", headers=auth_headers)
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "queued"

    assert _wait_for_status(fast_worker, document["id"], {"ready"}) == "ready"
    retried = _first_job(test_client, auth_headers, thread_id, document["id"])
    assert retried["id"] == job_id
    assert retried["retry_count"] == 1
    assert retried["error_msg"] is None


def test_retry_rejects_nonfailed_job(test_client, auth_headers, fast_worker):
    thread_id = _create_project(test_client, auth_headers)
    document = _upload(test_client, auth_headers, thread_id)
    _wait_for_status(fast_worker, document["id"], {"ready"})
    ready_job = _first_job(test_client, auth_headers, thread_id, document["id"])
    assert test_client.post(f"/ingestion-jobs/{ready_job['id']}/retry", headers=auth_headers).status_code == 409


def test_jobs_endpoint_reports_live_embedding_progress(test_client, auth_headers, fast_worker):
    thread_id = _create_project(test_client, auth_headers)
    gate = threading.Event()

    class Gated(InstantEmbeddings):
        def embed_documents(self, texts):
            gate.wait(timeout=10)
            return super().embed_documents(texts)

    fast_worker._embeddings = Gated()
    try:
        document = _upload(test_client, auth_headers, thread_id)
        deadline = time.monotonic() + 10
        progress = None
        while time.monotonic() < deadline:
            job = _first_job(test_client, auth_headers, thread_id, document["id"])
            progress = job.get("progress")
            if progress and progress.get("phase") == "embedding":
                break
            time.sleep(0.05)
        assert progress == {
            "phase": "embedding",
            "total_chunks": progress["total_chunks"],
            "processed_chunks": 0,
        }
        assert progress["total_chunks"] > 0
    finally:
        gate.set()
    assert _wait_for_status(fast_worker, document["id"], {"ready"}) == "ready"


def test_recover_fails_stale_processing_jobs_instead_of_recrashing(test_client, auth_headers, fast_worker, monkeypatch):
    """A job that died mid-processing must NOT auto-resume at boot.

    Auto-resume crashed-looped the small Render container (embed → OOM →
    restart → embed again → Bad Gateway). Instead recovery marks the job
    failed with a retryable message; the user re-runs it via Retry.
    """
    thread_id = _create_project(test_client, auth_headers)
    document = _upload(test_client, auth_headers, thread_id)
    job = _first_job(test_client, auth_headers, thread_id, document["id"])
    assert _wait_for_status(fast_worker, document["id"], {"ready"}) == "ready"

    # Simulate a crash mid-processing: the row was left 'processing'.
    db = SessionLocal()
    try:
        crud.update_ingestion_job_status(db, job["id"], "processing")
    finally:
        db.close()

    restarted = IngestionWorker(InstantEmbeddings(), media_store=fast_worker.media_store)
    monkeypatch.setattr(worker_module, "_WORKER", restarted, raising=False)
    recover_pending_ingestion_jobs()

    recovered = _first_job(test_client, auth_headers, thread_id, document["id"])
    assert recovered["status"] == "failed"
    assert "interrupted" in recovered["error_msg"].lower()

    # The failed job stays retryable through the normal API path.
    retry = test_client.post(f"/ingestion-jobs/{job['id']}/retry", headers=auth_headers)
    assert retry.status_code == 200, retry.text
    assert _wait_for_status(restarted, document["id"], {"ready"}) == "ready"


def test_recover_pending_ingestion_jobs_requeues(test_client, auth_headers, fast_worker, monkeypatch):
    # Freeze the first worker so the job row stays 'queued' exactly as it
    # would when a process dies before draining its queue.
    original_start = IngestionWorker._ensure_thread
    monkeypatch.setattr(IngestionWorker, "_ensure_thread", lambda self: None)
    thread_id = _create_project(test_client, auth_headers)
    document = _upload(test_client, auth_headers, thread_id, filename="recover.pdf")
    assert _first_job(test_client, auth_headers, thread_id, document["id"])["status"] == "queued"

    # Simulate a restart: fresh worker instance with an empty queue but the
    # same media store (as a redeployed process would share persisted files).
    monkeypatch.setattr(IngestionWorker, "_ensure_thread", original_start)
    restarted = IngestionWorker(InstantEmbeddings(), media_store=fast_worker.media_store)
    monkeypatch.setattr(worker_module, "_WORKER", restarted, raising=False)
    assert recover_pending_ingestion_jobs() >= 1
    assert _wait_for_status(restarted, document["id"], {"ready"}) == "ready"


def test_quiz_generation_rejects_unprocessed_document(test_client, auth_headers, fast_worker):
    from app.tools.quiz_generator_tool import QuizGenerationError, generate_quiz

    thread_id = _create_project(test_client, auth_headers)
    document = _upload(test_client, auth_headers, thread_id, filename="pending.pdf")

    db = SessionLocal()
    try:
        with pytest.raises(QuizGenerationError, match="still processing"):
            generate_quiz(
                llm=None, document_id=document["id"], topic="anything",
                embeddings=InstantEmbeddings(), db=db,
            )
    finally:
        db.close()


def test_secret_key_meets_hs256_minimum(monkeypatch):
    import importlib

    import app.config as config_module

    monkeypatch.setenv("SECRET_KEY", "short")
    reloaded = importlib.reload(config_module)
    try:
        assert len(reloaded.SECRET_KEY.encode("utf-8")) >= 32
        # Deterministic: same env value must produce the same effective key.
        importlib.reload(config_module)
        assert reloaded.SECRET_KEY == config_module.SECRET_KEY
    finally:
        monkeypatch.undo()
        importlib.reload(config_module)
