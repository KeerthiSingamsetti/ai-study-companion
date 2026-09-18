"""
db/models.py
============
SQLAlchemy 2.0 ORM model definitions for AI Study Companion.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import DEFAULT_USER_ID, MASTERY_INITIAL_SCORE


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------

class User(Base):
    """User account model for authentication and scoping."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="student")  # "student" | "admin"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r}>"


# ---------------------------------------------------------------------------
# spaces
# ---------------------------------------------------------------------------

class Space(Base):
    """Represents a Space (subject / course container) grouping Projects."""

    __tablename__ = "spaces"
    __table_args__ = (Index("ix_spaces_user_id", "user_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Optional description and visual customization (accent colour + icon).
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    accent: Mapped[str | None] = mapped_column(String, nullable=True)
    icon: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Space id={self.id!r} name={self.name!r}>"


# ---------------------------------------------------------------------------
# threads (Projects)
# ---------------------------------------------------------------------------

class Thread(Base):
    """
    Represents a study session / Project thread.
    Groups uploaded documents, concepts, mastery data, and conversations.
    """

    __tablename__ = "threads"
    __table_args__ = (
        Index("ix_threads_user_id", "user_id"),
        Index("ix_threads_space_id", "space_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, default=DEFAULT_USER_ID)
    space_id: Mapped[str | None] = mapped_column(String, ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    # A Project is the core learning workspace: what it covers and where it is heading.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_goal: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # --- relationships ---
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="thread", cascade="all, delete-orphan"
    )
    study_log: Mapped[list["StudyLog"]] = relationship(
        "StudyLog", back_populates="thread", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Thread id={self.id!r} title={self.title!r}>"


# ---------------------------------------------------------------------------
# documents
# ---------------------------------------------------------------------------

class Document(Base):
    """Represents a PDF document uploaded within a Project."""

    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_thread_id", "thread_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    thread_id: Mapped[str] = mapped_column(
        String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    vectorstore_path: Mapped[str] = mapped_column(String, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    thread: Mapped["Thread"] = relationship("Thread", back_populates="documents")

    def __repr__(self) -> str:
        return f"<Document id={self.id!r} filename={self.filename!r}>"


# ---------------------------------------------------------------------------
# concepts
# ---------------------------------------------------------------------------

class Concept(Base):
    """Represents an extracted learning concept within a Project."""

    __tablename__ = "concepts"
    __table_args__ = (
        UniqueConstraint("project_id", "name_normalized", name="uq_project_concept_normalized"),
        Index("ix_concepts_project_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    name_normalized: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Concept name={self.name!r}>"


# ---------------------------------------------------------------------------
# concept_mastery
# ---------------------------------------------------------------------------

class ConceptMastery(Base):
    """Recency-weighted EMA score (0-100) per user and concept."""

    __tablename__ = "concept_mastery"
    __table_args__ = (
        UniqueConstraint("user_id", "concept_id", name="uq_user_concept_mastery"),
        Index("ix_concept_mastery_user_concept", "user_id", "concept_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    concept_id: Mapped[str] = mapped_column(String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False)
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, default=MASTERY_INITIAL_SCORE)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------

class Event(Base):
    """Idempotent system event log recording activities."""

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_user_project", "user_id", "project_id"),
        Index("ix_events_event_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    processing_status: Mapped[str] = mapped_column(String, nullable=False, default="processed")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# ingestion_jobs
# ---------------------------------------------------------------------------

class IngestionJob(Base):
    """Tracks background PDF parsing & vector indexing lifecycle."""

    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")  # queued | processing | ready | failed
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# assessment_attempts
# ---------------------------------------------------------------------------

class AssessmentAttempt(Base):
    """Records open-ended question responses and LLM grading results."""

    __tablename__ = "assessment_attempts"
    __table_args__ = (Index("ix_assessment_attempts_user_project", "user_id", "project_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    concept_id: Mapped[str | None] = mapped_column(String, ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    understanding: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    # The learner's own pre-grading prediction (0-100). Nullable because answers
    # graded before this was captured, and skipped predictions, have no value.
    predicted_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    concepts_covered_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    concepts_missing_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# recommendations
# ---------------------------------------------------------------------------

class Recommendation(Base):
    """Actionable recommendations derived from growth & repeated mistakes."""

    __tablename__ = "recommendations"
    __table_args__ = (Index("ix_recommendations_user_project", "user_id", "project_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    concept_id: Mapped[str | None] = mapped_column(String, ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True)
    trigger: Mapped[str] = mapped_column(String, nullable=False)  # repeated_mistake | low_mastery | stale
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    is_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# ai_call_log
# ---------------------------------------------------------------------------

class AICallLog(Base):
    """Observability log for model calls, token usage, latency, and cost."""

    __tablename__ = "ai_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String, ForeignKey("threads.id", ondelete="SET NULL"), nullable=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    feature: Mapped[str] = mapped_column(String, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RetrievalTrace(Base):
    """Inspectable evidence used by one tutor retrieval operation."""

    __tablename__ = "retrieval_traces"
    __table_args__ = (
        Index("ix_retrieval_traces_project_created", "project_id", "created_at"),
        Index("ix_retrieval_traces_ai_call", "ai_call_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ai_call_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ai_call_log.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    strategy: Mapped[str] = mapped_column(String, nullable=False, default="hybrid_rrf_bge")
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    chunks_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grounded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ---------------------------------------------------------------------------
# Legacy tables preserved for backwards compatibility
# ---------------------------------------------------------------------------

class StudyLog(Base):
    __tablename__ = "study_log"
    __table_args__ = (
        Index("ix_study_log_thread_id", "thread_id"),
        Index("ix_study_log_event_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(
        String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    topic: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    thread: Mapped["Thread"] = relationship("Thread", back_populates="study_log")


class TopicsCache(Base):
    __tablename__ = "topics_cache"
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    topics_json: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MemoryFactType(str, Enum):
    WEAK_TOPIC = "weak_topic"
    STUDIED_TOPIC = "studied_topic"
    PREFERENCE = "preference"


class UserMemory(Base):
    __tablename__ = "user_memories"
    __table_args__ = (
        Index("ix_user_memories_user_created", "user_id", "created_at"),
        Index("ix_user_memories_user_project", "user_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, default=DEFAULT_USER_ID)
    # The Project whose learning context this fact belongs to. A Project lives
    # inside exactly one Space, so scoping by project also isolates Spaces.
    # Nullable only for legacy rows written before scoping existed.
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("threads.id", ondelete="SET NULL"), nullable=True
    )
    fact_type: Mapped[MemoryFactType] = mapped_column(SqlEnum(MemoryFactType), nullable=False)
    topic: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(String, nullable=False, default="quiz_score")
    detail: Mapped[str] = mapped_column(String, nullable=False)
    document_id: Mapped[str | None] = mapped_column(String, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        Index("ix_quiz_attempts_user_created", "user_id", "created_at"),
        Index("ix_quiz_attempts_user_project", "user_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, default=DEFAULT_USER_ID)
    # See UserMemory.project_id: this is what keeps one Project's quiz history
    # from appearing in another Project (or Space).
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("threads.id", ondelete="SET NULL"), nullable=True
    )
    document_id: Mapped[str] = mapped_column(String, nullable=False)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
