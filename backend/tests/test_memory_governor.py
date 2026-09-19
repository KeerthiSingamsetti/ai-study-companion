"""Memory-governor tests.

Regression context: the deployment was OOM-killed ("Ran out of memory, used
over 512MB") while ingesting. That returned 502 to every user and lost the
uploaded bytes. The governor must (a) report the container limit when it is
detectable, (b) refuse to *start* an ingestion when there is no headroom, and
(c) abort politely mid-embedding rather than growing until the kernel kills the
process — a clean failure is retryable and keeps the service serving.
"""

import pytest

from app import memory
from app.services import ingestion_worker as worker_module


@pytest.fixture
def limit_512(monkeypatch):
    monkeypatch.setenv("MEMORY_LIMIT_MB", "512")


def test_limit_override_is_read(limit_512):
    assert memory.memory_limit_mb() == 512.0


def test_invalid_override_falls_back_to_detection(monkeypatch):
    monkeypatch.setenv("MEMORY_LIMIT_MB", "not-a-number")
    # Detection may legitimately find nothing outside a cgroup, so the contract
    # here is only "a valid limit or None" — never a crash or a bogus number.
    detected = memory.memory_limit_mb()
    assert detected is None or detected > 0


def test_headroom_is_limit_minus_rss(limit_512, monkeypatch):
    monkeypatch.setattr(memory, "process_rss_mb", lambda: 400.0)
    assert memory.memory_headroom_mb() == 112.0


def test_unknown_limit_is_not_treated_as_no_room(monkeypatch):
    """An undetectable platform must never block ingestion outright."""
    monkeypatch.setattr(memory, "memory_limit_mb", lambda: None)
    assert memory.has_room_for_ingestion() is True
    assert memory.exceeds_abort_threshold() is False


def test_ingestion_refused_without_headroom(limit_512, monkeypatch):
    monkeypatch.setattr(memory, "process_rss_mb", lambda: 480.0)
    assert memory.has_room_for_ingestion() is False
    message = memory.memory_budget_message()
    assert "512" in message and "smaller PDF" in message


def test_abort_threshold_trips_near_the_limit(limit_512, monkeypatch):
    monkeypatch.setattr(memory, "process_rss_mb", lambda: 300.0)
    assert memory.exceeds_abort_threshold() is False
    monkeypatch.setattr(memory, "process_rss_mb", lambda: 460.0)
    assert memory.exceeds_abort_threshold() is True


def test_reranking_declined_on_small_instances(limit_512):
    assert memory.reranking_is_feasible() is False


def test_reranking_allowed_on_large_instances(monkeypatch):
    monkeypatch.setenv("MEMORY_LIMIT_MB", "4096")
    assert memory.reranking_is_feasible() is True


def test_progress_embeddings_reports_each_batch():
    """Progress must advance per provider round trip, not once at the end."""
    seen: list[int] = []

    class _Inner:
        def embed_documents(self, texts):
            return [[0.0]] * len(texts)

        def embed_query(self, text):
            return [0.0]

    wrapper = worker_module._ProgressEmbeddings(_Inner(), seen.append)
    vectors = wrapper.embed_documents(["x"] * 200)

    assert len(vectors) == 200
    # 200 texts at the provider batch size (96) => 96 + 96 + 8.
    assert seen == [96, 96, 8]


def test_mid_embedding_abort_surfaces_as_a_clean_failure(limit_512, monkeypatch):
    """The worker aborts between batches when memory is nearly exhausted."""

    class _Inner:
        def embed_documents(self, texts):
            return [[0.0]] * len(texts)

        def embed_query(self, text):
            return [0.0]

    def _on_batch(_size: int) -> None:
        if memory.exceeds_abort_threshold():
            raise worker_module.MemoryBudgetError(memory.memory_budget_message())

    monkeypatch.setattr(memory, "process_rss_mb", lambda: 500.0)
    wrapper = worker_module._ProgressEmbeddings(_Inner(), _on_batch)

    with pytest.raises(worker_module.MemoryBudgetError) as error:
        wrapper.embed_documents(["x"] * 10)

    # Actionable, user-visible text — not a bare RuntimeError.
    assert "smaller PDF" in str(error.value)
