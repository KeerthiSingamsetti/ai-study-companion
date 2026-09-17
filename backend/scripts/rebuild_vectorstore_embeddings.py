"""Rebuild persisted StudyMate FAISS indexes with local BGE embeddings.

Each index is rebuilt from its own persisted ``chunks.pkl`` so documents never
cross project boundaries. The command only permits index paths below the
application's ``backend/vectorstores`` directory.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from app.db import crud
from app.db.session import SessionLocal
from app.rag.embeddings import get_embeddings
from app.rag.store import build_and_save_index, load_chunks

BACKEND_DIR = Path(__file__).resolve().parents[1]
VECTORSTORE_ROOT = (BACKEND_DIR / "vectorstores").resolve()


def rebuild_all() -> int:
    """Rebuild every existing persisted index from its original stored chunks."""
    embeddings = get_embeddings()
    db = SessionLocal()
    rebuilt = 0
    try:
        for project in crud.list_threads(db):
            for document in crud.list_documents_for_thread(db, project.id):
                path = Path(document.vectorstore_path).resolve()
                if VECTORSTORE_ROOT not in path.parents:
                    raise ValueError(f"Refusing to rebuild index outside vectorstore root: {path}")
                chunks = load_chunks(str(path))
                if not chunks:
                    print(f"SKIP {document.id}: no stored chunks at {path}")
                    continue
                temporary = path.with_name(f"{path.name}.bge-rebuild")
                if temporary.exists():
                    shutil.rmtree(temporary)
                build_and_save_index(chunks, embeddings, str(temporary))
                if path.exists():
                    shutil.rmtree(path)
                temporary.replace(path)
                rebuilt += 1
                print(f"REBUILT {document.id}: {path}")
        return rebuilt
    finally:
        db.close()


if __name__ == "__main__":
    print(f"Rebuilt {rebuild_all()} vectorstore index(es) with BAAI/bge-small-en-v1.5.")
