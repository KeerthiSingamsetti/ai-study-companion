"""
db/session.py
=============
Database engine and session management for AI Study Companion.
"""

from pathlib import Path
import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

BASE_DIR = Path(__file__).resolve().parents[2]   # backend/

# Always load backend/.env before computing DATABASE_URL, so this module works
# when imported standalone (scripts, tests) and not just via app.main.
# override=False keeps real environment variables (deployment) authoritative.
load_dotenv(BASE_DIR / ".env", override=False)

def _resolve_database_url(raw: str | None = None) -> str:
    """Resolve the SQLAlchemy database URL.

    ``DATABASE_URL`` wins when set (deployment); otherwise the local SQLite file
    is used, so development is unchanged. SQLAlchemy 2.x rejects the
    ``postgres://`` scheme that some hosts still emit, so it is normalised to
    ``postgresql://``.
    """
    url = (
        raw if raw is not None else os.getenv("DATABASE_URL")
    ) or f"sqlite:///{BASE_DIR / 'chatbot.db'}"
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def _is_sqlite_url(url: str) -> bool:
    """Whether *url* points at SQLite (so SQLite-only options should apply)."""
    return url.startswith("sqlite")


DATABASE_URL = _resolve_database_url()

_connect_args: dict = {}
_engine_options: dict = {}
if _is_sqlite_url(DATABASE_URL):
    # SQLite needs this to be shared across FastAPI's threadpool; passing it to
    # Postgres raises an error, so it is applied only for SQLite.
    _connect_args["check_same_thread"] = False
else:
    # Hosted Postgres (Supabase, Render) drops idle connections. Recycle and
    # pre-ping so a pooled connection is never reused after the server closed it.
    _engine_options["pool_pre_ping"] = True
    _engine_options["pool_recycle"] = 300

engine: Engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    echo=False,
    **_engine_options,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[type-arg]
    """Enable Write-Ahead Logging on every new SQLite connection.

    SQLite-only. Postgres enforces foreign keys and needs no journal pragma, so
    this listener is a no-op for a Postgres URL.
    """
    if _is_sqlite_url(DATABASE_URL):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def init_db() -> None:
    """Create all tables defined in the ORM models if they do not already exist."""
    Base.metadata.create_all(bind=engine)
    if _is_sqlite_url(DATABASE_URL):
        with engine.begin() as connection:
            columns = {
                row["name"]
                for row in connection.execute(text("PRAGMA table_info(threads)")).mappings()
            }
            if "updated_at" not in columns:
                connection.execute(text("ALTER TABLE threads ADD COLUMN updated_at DATETIME"))
                connection.execute(text("UPDATE threads SET updated_at = created_at WHERE updated_at IS NULL"))
            if "user_id" not in columns:
                connection.execute(text("ALTER TABLE threads ADD COLUMN user_id VARCHAR"))
            if "space_id" not in columns:
                connection.execute(text("ALTER TABLE threads ADD COLUMN space_id VARCHAR"))
            if "description" not in columns:
                connection.execute(text("ALTER TABLE threads ADD COLUMN description TEXT"))
            if "learning_goal" not in columns:
                connection.execute(text("ALTER TABLE threads ADD COLUMN learning_goal TEXT"))
            space_columns = {
                row["name"]
                for row in connection.execute(text("PRAGMA table_info(spaces)")).mappings()
            }
            if space_columns:
                for column, definition in (
                    ("description", "TEXT"),
                    ("accent", "VARCHAR"),
                    ("icon", "VARCHAR"),
                ):
                    if column not in space_columns:
                        connection.execute(text(f"ALTER TABLE spaces ADD COLUMN {column} {definition}"))
            for table, column, definition in (
                ("events", "processing_status", "VARCHAR DEFAULT 'processed'"),
                ("events", "processed_at", "DATETIME"),
                ("events", "error_msg", "TEXT"),
                ("ingestion_jobs", "user_id", "VARCHAR"),
                ("ingestion_jobs", "project_id", "VARCHAR"),
                ("ai_call_log", "user_id", "VARCHAR"),
                ("ai_call_log", "project_id", "VARCHAR"),
                ("assessment_attempts", "predicted_score", "FLOAT"),
                # Progress/memory isolation: scope facts and quiz history to a Project.
                ("user_memories", "project_id", "VARCHAR"),
                ("quiz_attempts", "project_id", "VARCHAR"),
            ):
                table_columns = {row["name"] for row in connection.execute(text(f"PRAGMA table_info({table})")).mappings()}
                if table_columns and column not in table_columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))

    # Progress rows written before Project scoping carry project_id = NULL, which a
    # Project-scoped read would hide. Attribute them from the document they belong
    # to; rows with no document cannot be placed in a Project and stay NULL.
    # Idempotent, so it is safe to run on every startup.
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table in ("quiz_attempts", "user_memories"):
            if not inspector.has_table(table):
                continue
            columns = {column["name"] for column in inspector.get_columns(table)}
            if "project_id" not in columns:
                continue
            connection.execute(
                text(
                    f"UPDATE {table} SET project_id = ("
                    f"SELECT thread_id FROM documents WHERE documents.id = {table}.document_id"
                    f") WHERE project_id IS NULL AND document_id IS NOT NULL"
                )
            )

    # Seed default_user row for legacy fallback & migration seed data
    db = SessionLocal()
    try:
        from app.config import DEFAULT_USER_ID
        from app.db.models import User
        if db.get(User, DEFAULT_USER_ID) is None:
            default_user = User(
                id=DEFAULT_USER_ID,
                email="default_user@example.com",
                hashed_password="default_user_hashed_password",
                display_name="Default User",
                role="student",
            )
            db.add(default_user)
            db.commit()
    finally:
        db.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a session for one request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
