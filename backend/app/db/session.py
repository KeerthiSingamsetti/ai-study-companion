"""
db/session.py
=============
Database engine and session management for AI Study Companion.
"""

from pathlib import Path
import os
from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

BASE_DIR = Path(__file__).resolve().parents[2]   # backend/

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'chatbot.db'}"
)

_connect_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine: Engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[type-arg]
    """Enable Write-Ahead Logging on every new SQLite connection."""
    if DATABASE_URL.startswith("sqlite"):
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
    if DATABASE_URL.startswith("sqlite"):
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
            ):
                table_columns = {row["name"] for row in connection.execute(text(f"PRAGMA table_info({table})")).mappings()}
                if table_columns and column not in table_columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))

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
