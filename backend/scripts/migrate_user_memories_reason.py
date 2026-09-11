"""One-time SQLite migration & backfill script for user_memories.reason column.

1. Creates an automatic DB backup (chatbot.db.bak-pre-migration).
2. Adds 'reason' column to user_memories if missing.
3. Backfills existing historical records using detail string rules.
4. Deduplicates weak_topics records strictly (keeping newest per topic).
"""

import shutil
import sqlite3
from pathlib import Path
from sqlalchemy import text
from app.db.session import SessionLocal

DB_PATH = Path(__file__).resolve().parent.parent / "chatbot.db"


def run_migration() -> None:
    # 1. Create DB Backup
    if DB_PATH.exists():
        backup_path = DB_PATH.with_name("chatbot.db.bak-pre-migration")
        shutil.copy2(DB_PATH, backup_path)
        print(f"Created pre-migration backup at: {backup_path}")

    db = SessionLocal()
    try:
        conn = db.connection().connection
        cursor = conn.cursor()

        # 2. Check and add reason column if missing
        cursor.execute("PRAGMA table_info(user_memories);")
        columns = [info[1] for info in cursor.fetchall()]

        if "reason" not in columns:
            print("Adding 'reason' column to user_memories table...")
            cursor.execute("ALTER TABLE user_memories ADD COLUMN reason VARCHAR DEFAULT 'quiz_score';")
            conn.commit()

        # 3. Backfill existing historical rows
        print("Backfilling historical reason values...")
        db.execute(text("""
            UPDATE user_memories
            SET reason = CASE
                WHEN LOWER(detail) LIKE '%flashcard%' THEN 'flashcard_review'
                WHEN LOWER(detail) LIKE '%quiz%' OR LOWER(detail) LIKE '%score%' THEN 'quiz_score'
                ELSE 'manual'
            END
            WHERE reason IS NULL OR reason = 'quiz_score';
        """))

        # 4. Deduplicate weak_topics strictly (preserving studied_topics)
        print("Deduplicating weak_topic records...")
        db.execute(text("""
            DELETE FROM user_memories
            WHERE fact_type = 'weak_topic'
              AND id NOT IN (
                SELECT MAX(id)
                FROM user_memories
                WHERE fact_type = 'weak_topic' AND topic IS NOT NULL
                GROUP BY user_id, LOWER(topic)
              );
        """))

        db.commit()
        print("Migration and backfill completed successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
