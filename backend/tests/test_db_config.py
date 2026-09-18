"""Tests for database URL resolution (SQLite locally, Postgres in deployment)."""

from app.db.session import _is_sqlite_url, _resolve_database_url


def test_postgres_scheme_is_normalized_for_sqlalchemy() -> None:
    """Some hosts emit ``postgres://``, which SQLAlchemy 2.x rejects as a dialect."""
    assert (
        _resolve_database_url("postgres://u:p@host:5432/db")
        == "postgresql://u:p@host:5432/db"
    )
    assert (
        _resolve_database_url("postgresql://u:p@host/db")
        == "postgresql://u:p@host/db"
    )


def test_sqlite_and_postgres_urls_are_classified() -> None:
    """SQLite-only options must never be applied to a Postgres connection."""
    assert _is_sqlite_url("sqlite:///./dev.db") is True
    assert _is_sqlite_url("postgresql://u:p@host/db") is False
    assert _is_sqlite_url("postgres://u:p@host/db") is False


def test_missing_url_falls_back_to_local_sqlite() -> None:
    """An unset/empty DATABASE_URL keeps the existing local development database."""
    fallback = _resolve_database_url("")
    assert fallback.startswith("sqlite:///")
    assert fallback.endswith("chatbot.db")
