"""Tests for user-scoped long-term memory persistence."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import crud
from app.db.models import Base, MemoryFactType
from app.tools.memory_tool import get_memory_context


def test_user_memory_is_scoped_and_formats_compact_context() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    crud.save_user_memory(db, "user-a", MemoryFactType.WEAK_TOPIC, "backpropagation", "Missed 3 of 5 questions.")
    crud.save_user_memory(db, "user-a", MemoryFactType.STUDIED_TOPIC, "neural networks", "Studied neural networks.")
    crud.save_user_memory(db, "user-b", MemoryFactType.WEAK_TOPIC, "calculus", "Needs review.")

    assert [item.topic for item in crud.get_user_memory(db, "user-a")] == ["neural networks", "backpropagation"]
    context = get_memory_context(db, "user-a")
    assert "backpropagation" in context
    assert "neural networks" in context
    assert "calculus" not in context
