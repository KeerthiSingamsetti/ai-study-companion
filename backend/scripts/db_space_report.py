"""Read-only census: users, their Spaces, and Project counts per Space.

Run from anywhere with the backend venv:
    backend\\venv\\Scripts\\python.exe backend\\scripts\\db_space_report.py

Opens chatbot.db in SQLite read-only mode, so it never locks or writes.
"""
from pathlib import Path
import sqlite3
import sys

DEFAULT_DB = Path(__file__).resolve().parents[1] / "chatbot.db"


def main() -> None:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    print(f"Database: {db_path}\n")
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        for table in ("users", "spaces", "threads"):
            columns = [row["name"] for row in cur.execute(f"PRAGMA table_info({table})")]
            print(f"{table}: {', '.join(columns)}")
        print()

        for user in cur.execute("SELECT * FROM users ORDER BY created_at"):
            user = dict(user)
            spaces = [
                dict(row)
                for row in cur.execute(
                    "SELECT * FROM spaces WHERE user_id = ? ORDER BY created_at", (user["id"],)
                )
            ]
            print(f"{user['email']}: {len(spaces)} Spaces")
            for space in spaces:
                (project_count,) = cur.execute(
                    "SELECT COUNT(*) FROM threads WHERE space_id = ?", (space["id"],)
                ).fetchone()
                print(f"  - {space['name']!r} (id={space['id']}) projects={project_count}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
