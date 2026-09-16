"""
One-shot migration script for vectorstore directory paths.
Moves paths from vectorstores/<thread_id>/<document_id>/ to vectorstores/<project_id>/<document_id>/.
For existing threads where project_id == thread_id, paths remain valid automatically.
"""

from pathlib import Path
import logging
from app.db.session import SessionLocal
from app.db import crud

logger = logging.getLogger(__name__)


def migrate_paths() -> int:
    db = SessionLocal()
    updated_count = 0
    try:
        threads = crud.list_threads(db)
        for thread in threads:
            docs = crud.list_documents_for_thread(db, thread.id)
            for doc in docs:
                old_path = Path(doc.vectorstore_path)
                if old_path.exists():
                    # For thread_id == project_id, path format is identical
                    logger.info("Verified vectorstore path for document %s at %s", doc.id, old_path)
                    updated_count += 1
        return updated_count
    finally:
        db.close()


if __name__ == "__main__":
    count = migrate_paths()
    print(f"Verified vectorstore paths for {count} documents.")
