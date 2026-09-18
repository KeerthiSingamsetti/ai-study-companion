"""
db/crud.py
==========
CRUD operations for AI Study Companion.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import DEFAULT_USER_ID

from app.db.models import (
    Concept,
    ConceptMastery,
    Document,
    Event,
    IngestionJob,
    AICallLog,
    RetrievalTrace,
    MemoryFactType,
    QuizAttempt,
    Recommendation,
    Space,
    StudyLog,
    Thread,
    TopicsCache,
    User,
    UserMemory,
)

# PRD §12 event taxonomy.  Keeping this at the persistence boundary prevents
# drift into opaque/free-form event names while payloads remain extensible.
EVENT_TYPES: frozenset[str] = frozenset({
    "project_created", "material_uploaded", "material_processing_started",
    "material_processing_completed", "material_processing_failed",
    "tutor_interaction", "quiz_attempted", "question_answered",
    "assessment_completed", "mastery_updated", "recommendations_generated",
    "project_activity",
})


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def has_real_registered_user(db: Session) -> bool:
    """True once any real account exists (the seeded legacy 'default_user' —
    which has an unusable password hash and cannot log in — does not count).
    Used to grant admin to the first genuine registration."""
    return (
        db.query(User)
        .filter(User.id != DEFAULT_USER_ID)
        .first()
        is not None
    )


def create_user(
    db: Session,
    *,
    user_id: str,
    email: str,
    hashed_password: str,
    display_name: str,
    role: str = "student",
) -> User:
    """Insert a new User row."""
    user = User(
        id=user_id,
        email=email.lower().strip(),
        hashed_password=hashed_password,
        display_name=display_name,
        role=role,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Fetch user by primary key."""
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Fetch user by unique email."""
    return db.query(User).filter(User.email == email.lower().strip()).first()


def list_users(db: Session, limit: int = 100, offset: int = 0) -> list[User]:
    """List users for admin reporting."""
    return db.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()


# ---------------------------------------------------------------------------
# Spaces
# ---------------------------------------------------------------------------

def create_space(
    db: Session,
    *,
    space_id: str,
    user_id: str,
    name: str,
    description: Optional[str] = None,
    accent: Optional[str] = None,
    icon: Optional[str] = None,
) -> Space:
    """Create a new Space container with optional description and customization."""
    space = Space(
        id=space_id,
        user_id=user_id,
        name=name,
        description=description,
        accent=accent,
        icon=icon,
        created_at=datetime.now(timezone.utc),
    )
    db.add(space)
    db.commit()
    db.refresh(space)
    return space


def update_space(
    db: Session,
    *,
    space_id: str,
    user_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    accent: Optional[str] = None,
    icon: Optional[str] = None,
) -> Optional[Space]:
    """Patch an owned Space without touching unspecified fields."""
    space = get_space(db, space_id, user_id=user_id)
    if space is None:
        return None
    if name is not None:
        space.name = name
    if description is not None:
        space.description = description
    if accent is not None:
        space.accent = accent
    if icon is not None:
        space.icon = icon
    db.commit()
    db.refresh(space)
    return space


def get_space(db: Session, space_id: str, user_id: Optional[str] = None) -> Optional[Space]:
    """Fetch space by ID, optionally verifying user ownership."""
    query = db.query(Space).filter(Space.id == space_id)
    if user_id is not None:
        query = query.filter(Space.user_id == user_id)
    return query.first()


def list_spaces_for_user(db: Session, user_id: str) -> list[Space]:
    """List all spaces owned by user."""
    return (
        db.query(Space)
        .filter(Space.user_id == user_id)
        .order_by(Space.created_at.desc())
        .all()
    )


def delete_space(db: Session, space_id: str, user_id: str) -> bool:
    """Delete a space if owned by user."""
    space = get_space(db, space_id, user_id=user_id)
    if space is None:
        return False
    db.delete(space)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Threads / Projects
# ---------------------------------------------------------------------------

def create_thread(
    db: Session,
    *,
    thread_id: str,
    title: str,
    user_id: Optional[str] = None,
    space_id: Optional[str] = None,
    description: Optional[str] = None,
    learning_goal: Optional[str] = None,
) -> Thread:
    """Insert a new Thread (Project) row."""
    thread = Thread(
        id=thread_id,
        title=title,
        user_id=user_id,
        space_id=space_id,
        description=description,
        learning_goal=learning_goal,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def update_thread_details(
    db: Session,
    *,
    thread_id: str,
    user_id: str,
    description: Optional[str] = None,
    learning_goal: Optional[str] = None,
) -> Optional[Thread]:
    """Patch the PRD's project description / learning goal fields."""
    thread = get_thread(db, thread_id, user_id=user_id)
    if thread is None:
        return None
    if description is not None:
        thread.description = description
    if learning_goal is not None:
        thread.learning_goal = learning_goal
    thread.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(thread)
    return thread


def get_thread(db: Session, thread_id: str, user_id: Optional[str] = None) -> Optional[Thread]:
    """Fetch Thread by ID, optionally scoping by user_id."""
    query = db.query(Thread).filter(Thread.id == thread_id)
    if user_id is not None:
        query = query.filter(Thread.user_id == user_id)
    return query.first()


def update_thread_title(
    db: Session, *, thread_id: str, title: str, user_id: Optional[str] = None
) -> Optional[Thread]:
    """Update thread title."""
    thread = get_thread(db, thread_id, user_id=user_id)
    if thread is None:
        return None
    thread.title = title
    db.commit()
    db.refresh(thread)
    return thread


def list_threads(
    db: Session, *, user_id: Optional[str] = None, space_id: Optional[str] = None, limit: int = 100, offset: int = 0
) -> list[Thread]:
    """List threads ordered by updated_at DESC, scoped by user_id/space_id if provided."""
    query = db.query(Thread)
    if user_id is not None:
        query = query.filter(Thread.user_id == user_id)
    if space_id is not None:
        query = query.filter(Thread.space_id == space_id)
    return query.order_by(Thread.updated_at.desc()).offset(offset).limit(limit).all()


def touch_thread(db: Session, thread_id: str) -> Optional[Thread]:
    """Bump updated_at of an existing thread."""
    thread = db.get(Thread, thread_id)
    if thread is None:
        return None
    thread.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(thread)
    return thread


def delete_thread(db: Session, thread_id: str, user_id: Optional[str] = None) -> bool:
    """Delete a thread by ID, verifying user_id if provided."""
    thread = get_thread(db, thread_id, user_id=user_id)
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
    """Insert a Document row."""
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
    """Fetch Document by ID."""
    return db.get(Document, document_id)


def list_documents_for_thread(db: Session, thread_id: str, user_id: Optional[str] = None) -> list[Document]:
    """Return all documents for a thread, validating thread ownership if user_id is supplied."""
    if user_id is not None:
        thread = get_thread(db, thread_id, user_id=user_id)
        if thread is None:
            return []
    return (
        db.query(Document)
        .filter(Document.thread_id == thread_id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )


def delete_document(db: Session, document_id: str, user_id: Optional[str] = None) -> bool:
    """Delete a document by ID."""
    document = db.get(Document, document_id)
    if document is None:
        return False
    if user_id is not None:
        thread = get_thread(db, document.thread_id, user_id=user_id)
        if thread is None:
            return False
    db.delete(document)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Concepts & Mastery
# ---------------------------------------------------------------------------

def create_concept(db: Session, *, concept_id: str, project_id: str, name: str, name_normalized: str) -> Concept:
    """Create a concept row."""
    concept = Concept(
        id=concept_id,
        project_id=project_id,
        name=name,
        name_normalized=name_normalized,
        created_at=datetime.now(timezone.utc),
    )
    db.add(concept)
    db.commit()
    db.refresh(concept)
    return concept


def list_concepts_for_project(db: Session, project_id: str) -> list[Concept]:
    """List all concepts for a project."""
    return db.query(Concept).filter(Concept.project_id == project_id).all()


def get_concept_by_normalized_name(db: Session, project_id: str, name_normalized: str) -> Optional[Concept]:
    """Fast-path lookup for exact normalized name."""
    return (
        db.query(Concept)
        .filter(Concept.project_id == project_id, Concept.name_normalized == name_normalized)
        .first()
    )


def get_concept_mastery(db: Session, user_id: str, concept_id: str) -> Optional[ConceptMastery]:
    """Fetch mastery record for a user and concept."""
    return (
        db.query(ConceptMastery)
        .filter(ConceptMastery.user_id == user_id, ConceptMastery.concept_id == concept_id)
        .first()
    )


def upsert_concept_mastery(db: Session, *, user_id: str, concept_id: str, mastery_score: float) -> ConceptMastery:
    """Update or create a concept mastery score."""
    mastery = get_concept_mastery(db, user_id, concept_id)
    if mastery is None:
        mastery = ConceptMastery(
            user_id=user_id,
            concept_id=concept_id,
            mastery_score=mastery_score,
            attempt_count=1,
            last_updated=datetime.now(timezone.utc),
        )
        db.add(mastery)
    else:
        mastery.mastery_score = mastery_score
        mastery.attempt_count += 1
        mastery.last_updated = datetime.now(timezone.utc)
    db.commit()
    db.refresh(mastery)
    return mastery


def list_mastery_for_user_and_project(db: Session, user_id: str, project_id: str) -> list[tuple[Concept, ConceptMastery]]:
    """Return concepts paired with mastery records for a user within a project."""
    return (
        db.query(Concept, ConceptMastery)
        .join(ConceptMastery, (ConceptMastery.concept_id == Concept.id) & (ConceptMastery.user_id == user_id))
        .filter(Concept.project_id == project_id)
        .all()
    )


# ---------------------------------------------------------------------------
# Events Log
# ---------------------------------------------------------------------------

def log_event(
    db: Session,
    *,
    event_key: str,
    user_id: str,
    event_type: str,
    project_id: Optional[str] = None,
    payload_json: str = "{}",
) -> Event:
    """Insert an idempotent system event row."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown system event_type {event_type!r}.")
    existing = db.query(Event).filter(Event.event_key == event_key).first()
    if existing:
        return existing

    event = Event(
        event_key=event_key,
        user_id=user_id,
        project_id=project_id,
        event_type=event_type,
        payload_json=payload_json,
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def event_exists(db: Session, event_key: str) -> bool:
    """Return whether an idempotency key has already been accepted."""
    return db.query(Event.id).filter(Event.event_key == event_key).first() is not None


def list_events_for_user(db: Session, user_id: str, limit: int = 50, offset: int = 0) -> list[Event]:
    """List recent user events."""
    return (
        db.query(Event)
        .filter(Event.user_id == user_id)
        .order_by(Event.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def create_recommendation(
    db: Session,
    *,
    user_id: str,
    project_id: str,
    trigger: str,
    recommendation: str,
    concept_id: Optional[str] = None,
) -> Recommendation:
    """Persist one actionable next step so it survives across sessions."""
    row = Recommendation(
        user_id=user_id,
        project_id=project_id,
        concept_id=concept_id,
        trigger=trigger,
        recommendation=recommendation,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_active_recommendations_for_project(db: Session, user_id: str, project_id: str) -> list[Recommendation]:
    """Return non-dismissed recommendations, newest first."""
    return (
        db.query(Recommendation)
        .filter(
            Recommendation.user_id == user_id,
            Recommendation.project_id == project_id,
            Recommendation.is_dismissed.is_(False),
        )
        .order_by(Recommendation.created_at.desc())
        .all()
    )


def get_recommendation(db: Session, recommendation_id: int, user_id: str) -> Optional[Recommendation]:
    """Fetch one owned recommendation."""
    return (
        db.query(Recommendation)
        .filter(Recommendation.id == recommendation_id, Recommendation.user_id == user_id)
        .first()
    )


def dismiss_recommendation(db: Session, recommendation_id: int, user_id: str) -> Optional[Recommendation]:
    """Mark a recommendation dismissed so it stops resurfacing."""
    row = get_recommendation(db, recommendation_id, user_id)
    if row is None:
        return None
    row.is_dismissed = True
    db.commit()
    db.refresh(row)
    return row


def list_events_for_project(db: Session, project_id: str, limit: int = 50, offset: int = 0) -> list[Event]:
    """List recent events for a project."""
    return (
        db.query(Event)
        .filter(Event.project_id == project_id)
        .order_by(Event.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Ingestion Jobs
# ---------------------------------------------------------------------------

def create_ingestion_job(db: Session, *, job_id: str, document_id: str, user_id: str, project_id: str) -> IngestionJob:
    """Create background ingestion job."""
    job = IngestionJob(
        id=job_id,
        document_id=document_id,
        user_id=user_id,
        project_id=project_id,
        status="queued",
        retry_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_ingestion_job(db: Session, job_id: str) -> Optional[IngestionJob]:
    return db.get(IngestionJob, job_id)


def list_ingestion_jobs_for_project(db: Session, project_id: str) -> list[IngestionJob]:
    return db.query(IngestionJob).filter(IngestionJob.project_id == project_id).order_by(IngestionJob.created_at.desc()).all()


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

def log_ai_call(db: Session, *, model: str, feature: str, latency_ms: int, input_tokens: int = 0,
                output_tokens: int = 0, estimated_cost_usd: float = 0.0, success: bool = True,
                error_msg: str | None = None, user_id: str | None = None, project_id: str | None = None) -> AICallLog:
    record = AICallLog(model=model, feature=feature, latency_ms=latency_ms, input_tokens=input_tokens,
                       output_tokens=output_tokens, estimated_cost_usd=estimated_cost_usd, success=success,
                       error_msg=error_msg, user_id=user_id, project_id=project_id, created_at=datetime.now(timezone.utc))
    db.add(record); db.commit(); db.refresh(record)
    return record


def finish_ai_call(db: Session, call_id: int, *, latency_ms: int, input_tokens: int, output_tokens: int,
                   success: bool, error_msg: str | None = None) -> Optional[AICallLog]:
    record = db.get(AICallLog, call_id)
    if record is None:
        return None
    record.latency_ms = latency_ms
    record.input_tokens = input_tokens
    record.output_tokens = output_tokens
    record.success = success
    record.error_msg = error_msg
    db.commit(); db.refresh(record)
    return record


def log_retrieval_trace(db: Session, *, user_id: str, project_id: str, query: str, threshold: float,
                        chunks_json: str, selected_count: int, grounded: bool = False,
                        ai_call_id: int | None = None, strategy: str = "hybrid_rrf_bge") -> RetrievalTrace:
    trace = RetrievalTrace(ai_call_id=ai_call_id, user_id=user_id, project_id=project_id, query=query,
                           threshold=threshold, chunks_json=chunks_json, selected_count=selected_count,
                           grounded=grounded, strategy=strategy, created_at=datetime.now(timezone.utc))
    db.add(trace); db.commit(); db.refresh(trace)
    return trace


def list_retrieval_traces(db: Session, project_id: str, limit: int = 50) -> list[RetrievalTrace]:
    return db.query(RetrievalTrace).filter(RetrievalTrace.project_id == project_id).order_by(RetrievalTrace.created_at.desc()).limit(limit).all()


def update_ingestion_job_status(
    db: Session, job_id: str, status: str, retry_count: Optional[int] = None, error_msg: Optional[str] = None
) -> Optional[IngestionJob]:
    """Update background job status."""
    job = db.get(IngestionJob, job_id)
    if job is None:
        return None
    job.status = status
    if retry_count is not None:
        job.retry_count = retry_count
    if error_msg is not None:
        job.error_msg = error_msg
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


# ---------------------------------------------------------------------------
# Legacy Study Log & Memories
# ---------------------------------------------------------------------------

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
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"Unknown event_type {event_type!r}.")

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
    db.commit()
    db.refresh(cached)
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
    db: Session, user_id: str, limit: int = 20, fact_type: MemoryFactType | str | None = None
) -> list[UserMemory]:
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
    return (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == user_id)
        .order_by(QuizAttempt.created_at.desc())
        .limit(limit)
        .all()
    )
