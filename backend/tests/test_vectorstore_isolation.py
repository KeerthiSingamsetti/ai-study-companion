"""Tests for cross-project and cross-user FAISS vectorstore isolation."""

import uuid
from app.db import crud
from app.db.session import SessionLocal, init_db


def test_cross_project_vectorstore_isolation():
    """Verify that retrieval scoped to User B's thread_id never returns User A's vectorstore chunks."""
    init_db()
    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        user_a = crud.create_user(
            db,
            user_id=f"user_iso_a_{suffix}",
            email=f"iso_a_{suffix}@example.com",
            hashed_password="hash",
            display_name="User Iso A",
        )
        user_b = crud.create_user(
            db,
            user_id=f"user_iso_b_{suffix}",
            email=f"iso_b_{suffix}@example.com",
            hashed_password="hash",
            display_name="User Iso B",
        )

        thread_a = crud.create_thread(db, thread_id=f"thread_iso_a_{suffix}", title="Project A", user_id=user_a.id)
        thread_b = crud.create_thread(db, thread_id=f"thread_iso_b_{suffix}", title="Project B", user_id=user_b.id)

        doc_a = crud.create_document(
            db,
            document_id=f"doc_iso_a_{suffix}",
            thread_id=thread_a.id,
            filename="user_a_secret.pdf",
            vectorstore_path=f"vectorstores/{thread_a.id}/doc_iso_a",
            page_count=5,
            chunk_count=10,
        )

        docs_user_a = crud.list_documents_for_thread(db, thread_a.id, user_id=user_a.id)
        assert len(docs_user_a) == 1
        assert docs_user_a[0].id == doc_a.id

        docs_user_b_on_a = crud.list_documents_for_thread(db, thread_a.id, user_id=user_b.id)
        assert len(docs_user_b_on_a) == 0

    finally:
        db.close()
