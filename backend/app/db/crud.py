"""
db/crud.py
==========
CRUD (Create / Read / Update / Delete) operations for StudyMate.

Design principles
-----------------
1. **Pure functions**: every function takes an explicit `db: Session` argument.
   No module-level session singletons.  This makes unit-testing trivial —
   pass in an in-memory session, no patching required.

2. **No business logic**: these functions only translate between Python objects
   and database rows.  Validation, UUID generation, and path construction
   happen in the layer above (API routes or agent tools).

3. **Typed signatures**: every parameter and return value is annotated so that
   mypy / pyright can catch contract violations at the call site.

4. **Explicit commits**: callers are responsible for transaction boundaries in
   complex flows; simple helpers commit immediately for convenience.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session


from app.db.models import (
    Document,
    MemoryFactType,
    QuizAttempt,
    StudyLog,
    Thread,
    TopicsCache,
    UserMemory,
)

# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------


def create_thread(db: Session, *, thread_id: str, title: str) -> Thread:
    """
    Insert a new Thread row and return the persisted object.

    Parameters
    ----------
    db        : Active SQLAlchemy session.
    thread_id : Pre-generated UUID string (caller's responsibility).
    title     : Human-readable label for the thread.

    Returns
    -------
    The newly created Thread ORM object (already committed).
    """
    thread = Thread(
        id=thread_id,
        title=title,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def get_thread(db: Session, thread_id: str) -> Optional[Thread]:
    """
    Fetch a single Thread by its primary key.

    Returns None if no thread with that ID exists, so callers can decide
    whether to raise a 404 or handle the absence differently.
    """
    return db.get(Thread, thread_id)


def update_thread_title(db: Session, *, thread_id: str, title: str) -> Optional[Thread]:
    """Update a thread title and return the persisted thread, if it exists."""
    thread = db.get(Thread, thread_id)
    if thread is None:
        return None
    thread.title = title
    db.commit()
    db.refresh(thread)
    return thread


def list_threads(db: Session, *, limit: int = 100, offset: int = 0) -> list[Thread]:
    """
    Return all threads ordered by creation date (newest first).

    Parameters
    ----------
    limit  : Maximum number of rows to return (default 100).
    offset : Number of rows to skip — useful for pagination.
    """
    return (
        db.query(Thread)
        .order_by(Thread.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def touch_thread(db: Session, thread_id: str) -> Optional[Thread]:
    """Bump updated_at of an existing thread to the current UTC time.

    Called after each successful chat message so that active threads
    sort to the top of list_threads (ordered by updated_at DESC).

    Returns the refreshed Thread, or None if the thread was not found.
    """
    thread = db.get(Thread, thread_id)
    if thread is None:
        return None
    thread.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(thread)
    return thread


def delete_thread(db: Session, thread_id: str) -> bool:
    """
    Delete a thread by ID.  Returns True if a row was deleted, False if not found.

    Because we defined `ondelete="CASCADE"` on the FKs in models.py, the
    database automatically removes all associated documents and study_log rows.
    """
    thread = db.get(Thread, thread_id)
    if thread is None:
        return False
    db.delete(thread)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


def create_document(
    db: Session,
    *,
    document_id: str,
    thread_id: str,
    filename: str,
    vectorstore_path: str,
    page_count: int = 0,
    chunk_count: int = 0,
) -> Document:
    """
    Insert a new Document row linked to an existing thread.

    Parameters
    ----------
    db               : Active SQLAlchemy session.
    document_id      : Pre-generated UUID string.
    thread_id        : ID of the parent thread (must already exist).
    filename         : Original filename as uploaded.
    vectorstore_path : Filesystem path to the FAISS index directory.
    page_count       : Number of pages in the source PDF.
    chunk_count      : Number of text chunks ingested into the vector store.

    Returns
    -------
    The newly created Document ORM object (already committed).
    """
    document = Document(
        id=document_id,
        thread_id=thread_id,
        filename=filename,
        vectorstore_path=vectorstore_path,
        page_count=page_count,
        chunk_count=chunk_count,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_document(db: Session, document_id: str) -> Optional[Document]:
    """
    Fetch a single Document by its primary key.

    Returns None if not found.
    """
    return db.get(Document, document_id)


def list_documents_for_thread(db: Session, thread_id: str) -> list[Document]:
    """
    Return all documents belonging to a given thread, newest-first.

    Useful for the document sidebar and for loading vector stores when the
    agent needs to retrieve context from all uploaded files in a thread.
    """
    return (
        db.query(Document)
        .filter(Document.thread_id == thread_id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )


def delete_document(db: Session, document_id: str) -> bool:
    """
    Delete a document by ID.  Returns True if deleted, False if not found.

    Note: this only removes the DB row.  The caller is responsible for also
    removing the FAISS index files from disk (via vectorstore_path).
    """
    document = db.get(Document, document_id)
    if document is None:
        return False
    db.delete(document)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Study Log
# ---------------------------------------------------------------------------

# Allowed event types — enforced here so that any module importing crud.py
# can reference this set rather than hard-coding magic strings.
VALID_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "question_answered",
        "quiz_generated",
        "flashcards_generated",
        "study_plan_generated",
        "web_search_used",
    }
)


def log_study_event(
    db: Session,
    *,
    thread_id: str,
    event_type: str,
    document_id: Optional[str] = None,
    topic: Optional[str] = None,
) -> StudyLog:
    """
    Append one event to the study log for a thread.

    Parameters
    ----------
    db          : Active SQLAlchemy session.
    thread_id   : Thread in which the event occurred.
    event_type  : One of VALID_EVENT_TYPES (validated here; raises ValueError
                  if the caller passes an unknown type).
    document_id : Optional — the document that was the source of the event.
    topic       : Optional short description (e.g. 'Newton's laws').

    Returns
    -------
    The newly created StudyLog ORM object (already committed).

    Raises
    ------
    ValueError : If event_type is not in VALID_EVENT_TYPES.
    """
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"Unknown event_type {event_type!r}. "
            f"Must be one of: {sorted(VALID_EVENT_TYPES)}"
        )

    entry = StudyLog(
        thread_id=thread_id,
        document_id=document_id,
        event_type=event_type,
        topic=topic,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_study_log_for_thread(
    db: Session,
    thread_id: str,
    *,
    limit: int = 200,
    offset: int = 0,
) -> list[StudyLog]:
    """
    Return study-log entries for a thread ordered by time (newest first).

    Parameters
    ----------
    thread_id : Filter to this thread only.
    limit     : Maximum rows to return.
    offset    : Rows to skip (pagination).
    """
    return (
        db.query(StudyLog)
        .filter(StudyLog.thread_id == thread_id)
        .order_by(StudyLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_topics_cache(db: Session, document_id: str) -> TopicsCache | None:
    return db.get(TopicsCache, document_id)


def save_topics_cache(db: Session, document_id: str, topics_json: str) -> TopicsCache:
    cached = db.get(TopicsCache, document_id)
    if cached is None:
        cached = TopicsCache(document_id=document_id, topics_json=topics_json)
        db.add(cached)
    else:
        cached.topics_json = topics_json
    db.commit(); db.refresh(cached)
    return cached


def save_user_memory(
    db: Session,
    user_id: str,
    fact_type: MemoryFactType | str,
    topic: str | None,
    detail: str,
    document_id: str | None = None,
    reason: str = "quiz_score",
) -> UserMemory:
    """Persist or update (upsert) a user-scoped memory fact to prevent duplicate rows per topic."""
    fact = MemoryFactType(fact_type)
    clean_topic = topic.strip() if topic else None

    existing: UserMemory | None = None
    if clean_topic:
        existing = (
            db.query(UserMemory)
            .filter(
                UserMemory.user_id == user_id,
                UserMemory.fact_type == fact,
                func.lower(UserMemory.topic) == clean_topic.lower(),
            )
            .first()
        )

    if existing is not None:
        existing.detail = detail[:500]
        existing.reason = reason
        if document_id:
            existing.document_id = document_id
        existing.created_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    memory = UserMemory(
        user_id=user_id,
        fact_type=fact,
        topic=clean_topic,
        reason=reason,
        detail=detail[:500],
        document_id=document_id,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory



def get_user_memory(
    db: Session, user_id: str, limit: int = 20, fact_type: MemoryFactType | str | None = None,
) -> list[UserMemory]:
    """Return recent structured facts for one user, optionally by type."""
    query = db.query(UserMemory).filter(UserMemory.user_id == user_id)
    if fact_type is not None:
        query = query.filter(UserMemory.fact_type == MemoryFactType(fact_type))
    return query.order_by(UserMemory.created_at.desc()).limit(limit).all()


def create_quiz_attempt(
    db: Session,
    *,
    user_id: str,
    document_id: str,
    topic: str,
    correct_count: int,
    total_questions: int,
) -> QuizAttempt:
    """Persist one completed quiz score as a factual activity record."""
    attempt = QuizAttempt(
        user_id=user_id,
        document_id=document_id,
        topic=topic,
        correct_count=correct_count,
        total_questions=total_questions,
        created_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def get_quiz_attempts(db: Session, user_id: str, limit: int = 20) -> list[QuizAttempt]:
    """Return a user's recorded quiz attempts, newest first."""
    return (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == user_id)
        .order_by(QuizAttempt.created_at.desc())
        .limit(limit)
        .all()
    )
