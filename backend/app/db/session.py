"""
db/session.py
=============
Database engine and session management for StudyMate.

Public surface
--------------
- `engine`    : The SQLAlchemy engine (created once at import time).
- `init_db()` : Creates all tables if they don't already exist.
- `get_db()`  : FastAPI-compatible dependency that yields a Session and
                guarantees it is closed on teardown.

Portability note
----------------
The only thing that changes when moving from SQLite → Postgres is the value
of `DATABASE_URL`.  Everything else in this file — and in crud.py — stays
identical because we use the SQLAlchemy abstraction layer throughout.

SQLite-specific tweaks
----------------------
- `connect_args={"check_same_thread": False}` is required for SQLite because
  FastAPI uses a thread pool; without this flag SQLite raises an error when a
  connection created in one thread is used in another.
- This flag has no effect on other DB backends and is safe to leave in.
"""

from pathlib import Path
import os
from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

# ---------------------------------------------------------------------------
# Connection URL
# ---------------------------------------------------------------------------
# Default: SQLite file at backend/chatbot.db (one directory above this package).
# Override by setting the DATABASE_URL environment variable before startup.
# Example Postgres override:
#   export DATABASE_URL="postgresql+psycopg2://user:pass@localhost:5432/studymate"
# ---------------------------------------------------------------------------



BASE_DIR = Path(__file__).resolve().parents[2]   # backend/

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'chatbot.db'}"
)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

_connect_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    # Needed so FastAPI's thread-pool workers can share connections safely.
    _connect_args["check_same_thread"] = False

engine: Engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    # echo=True would log every SQL statement — useful during development,
    # but disabled by default to avoid noise in production.
    echo=False,
)


# ---------------------------------------------------------------------------
# Enable WAL mode for SQLite (no-op for other backends)
# This dramatically improves concurrent read performance and prevents
# "database is locked" errors during overlapping requests.
# ---------------------------------------------------------------------------

@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[type-arg]
    """Enable Write-Ahead Logging on every new SQLite connection."""
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,  # We control transactions explicitly
    autoflush=False,   # Flush only when we commit — avoids partial-write surprises
    expire_on_commit=False,  # Keep objects usable after commit without a re-query
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Create all tables defined in the ORM models if they do not already exist.

    Safe to call every time the application starts; SQLAlchemy uses
    CREATE TABLE IF NOT EXISTS semantics under the hood.

    Call this once from `main.py` inside the FastAPI `lifespan` handler.
    """
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


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session for one request.

    Usage
    -----
    ```python
    @router.get("/threads")
    def list_threads(db: Session = Depends(get_db)):
        return crud.list_threads(db)
    ```

    The session is always closed in the `finally` block, even if the
    route handler raises an exception, preventing connection leaks.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
