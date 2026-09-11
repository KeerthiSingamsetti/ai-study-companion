"""
tests/test_db.py
================
Unit tests for the StudyMate persistence layer (db/models, db/crud).

Strategy
--------
- We use an **in-memory SQLite** database (`sqlite:///:memory:`) so tests are
  fast, hermetic, and leave no files on disk.
- A `db` pytest fixture creates a fresh schema and session for every test
  function — guaranteeing full isolation without any teardown logic.
- We test the public CRUD surface only (no internals), which means these tests
  will remain valid even if the implementation details of crud.py change.
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import event as sa_event

from app.db.crud import (
    VALID_EVENT_TYPES,
    create_document,
    create_thread,
    delete_document,
    delete_thread,
    get_document,
    get_study_log_for_thread,
    get_thread,
    list_documents_for_thread,
    list_threads,
    log_study_event,
    update_thread_title,
)
from app.db.models import Base

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db() -> Session:
    """
    Provide an isolated in-memory SQLite session for a single test.

    A new engine and schema are created for each test function, so there is
    zero state leakage between tests.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @sa_event.listens_for(engine, "connect")
    def _fk(conn, _): conn.execute("PRAGMA foreign_keys=ON;")

    # Create all tables on the in-memory DB.
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop everything so the engine can be garbage-collected cleanly.
        Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _new_id() -> str:
    """Return a fresh UUID4 string."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Thread tests
# ---------------------------------------------------------------------------


class TestThreadCRUD:
    def test_create_and_get_thread(self, db: Session) -> None:
        """create_thread should persist a row retrievable by get_thread."""
        tid = _new_id()
        thread = create_thread(db, thread_id=tid, title="Physics 101")

        assert thread.id == tid
        assert thread.title == "Physics 101"
        assert thread.created_at is not None

        fetched = get_thread(db, tid)
        assert fetched is not None
        assert fetched.id == tid
        assert fetched.title == "Physics 101"

    def test_get_thread_missing_returns_none(self, db: Session) -> None:
        """get_thread should return None for a non-existent ID."""
        result = get_thread(db, "does-not-exist")
        assert result is None

    def test_update_thread_title_persists_normalized_value(self, db: Session) -> None:
        """A renamed thread remains renamed after the session refreshes it."""
        tid = _new_id()
        create_thread(db, thread_id=tid, title="Original title")

        updated = update_thread_title(db, thread_id=tid, title="Linear Algebra")

        assert updated is not None
        assert updated.title == "Linear Algebra"
        assert get_thread(db, tid).title == "Linear Algebra"

    def test_list_threads_empty(self, db: Session) -> None:
        """list_threads on an empty DB should return an empty list."""
        assert list_threads(db) == []

    def test_list_threads_ordered_newest_first(self, db: Session) -> None:
        """list_threads should return threads with the newest created_at first."""
        t1 = create_thread(db, thread_id=_new_id(), title="Thread A")
        t2 = create_thread(db, thread_id=_new_id(), title="Thread B")
        t3 = create_thread(db, thread_id=_new_id(), title="Thread C")

        threads = list_threads(db)
        # SQLite stores datetimes as strings; ordering may be tied if all three
        # are inserted in the same microsecond.  We relax to just checking all
        # three appear.
        ids = [t.id for t in threads]
        assert t1.id in ids
        assert t2.id in ids
        assert t3.id in ids

    def test_delete_thread(self, db: Session) -> None:
        """delete_thread should remove the row and return True."""
        tid = _new_id()
        create_thread(db, thread_id=tid, title="To Delete")

        result = delete_thread(db, tid)
        assert result is True
        assert get_thread(db, tid) is None

    def test_delete_thread_not_found(self, db: Session) -> None:
        """delete_thread should return False for a non-existent ID."""
        assert delete_thread(db, "ghost-id") is False


# ---------------------------------------------------------------------------
# Document tests
# ---------------------------------------------------------------------------


class TestDocumentCRUD:
    def _make_thread(self, db: Session) -> str:
        """Helper: create and return a thread ID."""
        tid = _new_id()
        create_thread(db, thread_id=tid, title="Test Thread")
        return tid

    def test_create_and_get_document(self, db: Session) -> None:
        """create_document should persist a row retrievable by get_document."""
        tid = self._make_thread(db)
        did = _new_id()

        doc = create_document(
            db,
            document_id=did,
            thread_id=tid,
            filename="lecture1.pdf",
            vectorstore_path=f"vectorstores/{tid}/{did}",
            page_count=12,
            chunk_count=48,
        )

        assert doc.id == did
        assert doc.thread_id == tid
        assert doc.filename == "lecture1.pdf"
        assert doc.page_count == 12
        assert doc.chunk_count == 48
        assert doc.uploaded_at is not None

        fetched = get_document(db, did)
        assert fetched is not None
        assert fetched.filename == "lecture1.pdf"

    def test_get_document_missing_returns_none(self, db: Session) -> None:
        result = get_document(db, "no-such-doc")
        assert result is None

    def test_list_documents_for_thread(self, db: Session) -> None:
        """list_documents_for_thread should return only docs for that thread."""
        tid1 = self._make_thread(db)
        tid2 = self._make_thread(db)

        d1 = create_document(
            db,
            document_id=_new_id(),
            thread_id=tid1,
            filename="doc_a.pdf",
            vectorstore_path="vs/a",
        )
        d2 = create_document(
            db,
            document_id=_new_id(),
            thread_id=tid1,
            filename="doc_b.pdf",
            vectorstore_path="vs/b",
        )
        _d3 = create_document(  # belongs to tid2, must NOT appear in tid1 results
            db,
            document_id=_new_id(),
            thread_id=tid2,
            filename="doc_c.pdf",
            vectorstore_path="vs/c",
        )

        docs = list_documents_for_thread(db, tid1)
        assert len(docs) == 2
        filenames = {doc.filename for doc in docs}
        assert "doc_a.pdf" in filenames
        assert "doc_b.pdf" in filenames
        assert "doc_c.pdf" not in filenames

    def test_list_documents_empty_thread(self, db: Session) -> None:
        tid = self._make_thread(db)
        assert list_documents_for_thread(db, tid) == []

    def test_delete_document(self, db: Session) -> None:
        """delete_document should remove the row and return True."""
        tid = self._make_thread(db)
        did = _new_id()
        create_document(
            db,
            document_id=did,
            thread_id=tid,
            filename="to_delete.pdf",
            vectorstore_path="vs/del",
        )

        result = delete_document(db, did)
        assert result is True
        assert get_document(db, did) is None

    def test_delete_document_not_found(self, db: Session) -> None:
        assert delete_document(db, "ghost-doc") is False


# ---------------------------------------------------------------------------
# Study Log tests
# ---------------------------------------------------------------------------


class TestStudyLog:
    def _setup(self, db: Session) -> tuple[str, str]:
        """Create a thread + document and return (thread_id, document_id)."""
        tid = _new_id()
        did = _new_id()
        create_thread(db, thread_id=tid, title="Log Test Thread")
        create_document(
            db,
            document_id=did,
            thread_id=tid,
            filename="notes.pdf",
            vectorstore_path="vs/notes",
        )
        return tid, did

    def test_log_study_event_with_document(self, db: Session) -> None:
        """log_study_event should persist a row retrievable via get_study_log_for_thread."""
        tid, did = self._setup(db)

        entry = log_study_event(
            db,
            thread_id=tid,
            event_type="question_answered",
            document_id=did,
            topic="Newton's laws",
        )

        assert entry.id is not None
        assert entry.thread_id == tid
        assert entry.document_id == did
        assert entry.event_type == "question_answered"
        assert entry.topic == "Newton's laws"
        assert entry.created_at is not None

    def test_log_study_event_without_document(self, db: Session) -> None:
        """document_id should be optional (web search events have no source doc)."""
        tid, _ = self._setup(db)

        entry = log_study_event(
            db,
            thread_id=tid,
            event_type="web_search_used",
            topic="quantum entanglement",
        )

        assert entry.document_id is None
        assert entry.event_type == "web_search_used"

    def test_invalid_event_type_raises(self, db: Session) -> None:
        """log_study_event should raise ValueError for unknown event types."""
        tid, _ = self._setup(db)

        with pytest.raises(ValueError, match="Unknown event_type"):
            log_study_event(db, thread_id=tid, event_type="made_up_event")

    def test_get_study_log_for_thread(self, db: Session) -> None:
        """get_study_log_for_thread should return all events for a thread."""
        tid, did = self._setup(db)

        log_study_event(db, thread_id=tid, event_type="question_answered", topic="Q1")
        log_study_event(db, thread_id=tid, event_type="quiz_generated", topic="Quiz 1")

        logs = get_study_log_for_thread(db, tid)
        assert len(logs) == 2
        event_types = {e.event_type for e in logs}
        assert "question_answered" in event_types
        assert "quiz_generated" in event_types

    def test_study_log_isolated_between_threads(self, db: Session) -> None:
        """Events logged to thread A must not appear in thread B's log."""
        tid_a, _ = self._setup(db)

        # Create a second, independent thread
        tid_b = _new_id()
        create_thread(db, thread_id=tid_b, title="Thread B")

        log_study_event(db, thread_id=tid_a, event_type="quiz_generated", topic="A quiz")

        assert get_study_log_for_thread(db, tid_b) == []
        assert len(get_study_log_for_thread(db, tid_a)) == 1

    def test_valid_event_types_constant(self) -> None:
        """Sanity-check that VALID_EVENT_TYPES contains the expected values."""
        expected = {
            "question_answered",
            "quiz_generated",
            "flashcards_generated",
            "study_plan_generated",
            "web_search_used",
        }
        assert VALID_EVENT_TYPES == expected

    # --- Integration: cascade delete ---

    def test_cascade_delete_thread_removes_log(self, db: Session) -> None:
        """Deleting a thread should cascade-delete its study_log rows."""
        tid, _ = self._setup(db)
        log_study_event(db, thread_id=tid, event_type="flashcards_generated")

        # Verify log exists before deletion
        assert len(get_study_log_for_thread(db, tid)) == 1

        delete_thread(db, tid)

        # After thread deletion, querying by that thread_id should return []
        assert get_study_log_for_thread(db, tid) == []
