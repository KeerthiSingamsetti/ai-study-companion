"""Remove accounts created by automated tests from the development database.

This is a one-off maintenance tool, not application logic. It only ever touches
accounts whose email matches a pattern that the test suite or a verification
script is documented to generate:

| Pattern source                                   | Email pattern                       |
|--------------------------------------------------|-------------------------------------|
| ``tests/test_auth.py`` register/login cases       | ``newuser_*@example.com``           |
| ``tests/test_auth.py`` duplicate-email case       | ``duplicate_*@example.com``         |
| ``tests/test_auth.py`` login case                 | ``logintest_*@example.com``         |
| ``tests/test_auth.py`` wrong-password case        | ``wrongpass_*@example.com``         |
| ``tests/test_auth.py`` project-isolation case     | ``userb_*@example.com``             |
| ``tests/test_auth.py`` (pre-suffix fixtures)      | ``newuser@example.com`` etc.        |
| ``tests/test_vectorstore_isolation.py``           | ``iso_a_*@example.com``             |
|                                                   | ``iso_b_*@example.com``             |
| ``tests/test_chat_integration.py``                | ``test-user-*@example.com``         |
| ``tests/test_quiz_generator.py``                  | ``test-user-*@example.com``         |
| ``tests/test_conversation_memory.py``             | ``test-user-*@example.com``         |
|                                                   | ``memuser@example.com``             |
| ``tests/test_space_projects.py``                  | ``<uuid>@example.com``              |
| ``scripts/test_real_chat_e2e.py``                 | ``chat_e2e_*@example.com``          |
| ``conftest.py`` ``test_user`` fixture             | ``testuser@example.com``            |

Everything else is preserved. In particular:

* ``default_user@example.com`` is a system seed row created by ``init_db()`` and
  referenced by legacy data, so it is protected explicitly.
* Accounts registered through the UI (real people, gmail/RGUKT addresses) are
  never matched by the patterns above.
* ``flowcheck_*``/``selfrole_*`` accounts are listed for your review only. They
  look automated, but this script has no source-level evidence for them, so it
  never deletes them unless the operator passes ``--include-review-only``.

Two extra guards apply to deliberate, operator-confirmed deletions:

* ``--delete-email`` removes one explicitly confirmed account by address. It can
  never remove a protected id/address.
* The script refuses to run if the deletion would eliminate the last remaining
  ``admin`` account.

By default the script only reports. Pass ``--apply`` to perform the deletion,
which first writes a timestamped backup of the database next to it.

Usage (from ``backend/``)::

    python scripts/cleanup_test_accounts.py                 # dry run / report
    python scripts/cleanup_test_accounts.py --apply         # backup + delete
    python scripts/cleanup_test_accounts.py --database path\\to\\chatbot.db
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import DATABASE_URL as SESSION_DATABASE_URL  # noqa: E402

# --- What counts as a test account ------------------------------------------
# Each entry is (label, compiled regex, why it is safe to delete).
TEST_ACCOUNT_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("iso_a", re.compile(r"^iso_a_[0-9a-f]+@example\.com$"), "test_vectorstore_isolation.py"),
    ("iso_b", re.compile(r"^iso_b_[0-9a-f]+@example\.com$"), "test_vectorstore_isolation.py"),
    ("iso_a_legacy", re.compile(r"^iso_a@example\.com$"), "early test vectorstore run"),
    ("iso_b_legacy", re.compile(r"^iso_b@example\.com$"), "early test vectorstore run"),
    ("test-user", re.compile(r"^test-user-[0-9a-f]+@example\.com$"), "chat/quiz/conversation tests"),
    ("wrongpass", re.compile(r"^wrongpass_[0-9a-f]+@example\.com$"), "test_auth.py login failure"),
    ("logintest", re.compile(r"^logintest_[0-9a-f]+@example\.com$"), "test_auth.py login"),
    ("duplicate", re.compile(r"^duplicate_[0-9a-f]+@example\.com$"), "test_auth.py duplicate email"),
    ("newuser", re.compile(r"^newuser_[0-9a-f]+@example\.com$"), "test_auth.py registration"),
    ("chat_e2e", re.compile(r"^chat_e2e_[0-9a-f]+@example\.com$"), "scripts/test_real_chat_e2e.py"),
    ("userb", re.compile(r"^userb_[0-9a-f]+@example\.com$"), "test_auth.py isolation"),
    ("bare_fixtures", re.compile(r"^(newuser|duplicate|logintest|wrongpass|userb|memuser)@example\.com$"),
     "first run of the auth/memory tests before suffixes were added"),
    (
        "uuid_email",
        re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}@example\.com$"),
        "test_space_projects.py / test_admin_console.py throwaway users",
    ),
    ("conftest_fixture", re.compile(r"^testuser@example\.com$"), "conftest.py test_user fixture"),
]

# Looks automated, but no test file or script generates it: report only.
REVIEW_ONLY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("flowcheck", re.compile(r"^flowcheck_\d+@example\.com$")),
    ("selfrole", re.compile(r"^selfrole_\d+@example\.com$")),
]

# Never deleted, whatever else happens.
PROTECTED_EMAILS = {"default_user@example.com"}
PROTECTED_IDS = {"default_user"}


# --- Helpers ----------------------------------------------------------------


def resolve_database_path(override: str | None) -> Path:
    """Return the SQLite file this script will inspect."""
    if override:
        return Path(override).resolve()
    url = SESSION_DATABASE_URL
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise SystemExit(f"Only SQLite databases are supported (got {url!r}).")
    return Path(url[len(prefix):]).resolve()


def classify(email: str) -> tuple[str, str] | None:
    """Return (label, reason) when the email is a documented test identity."""
    for label, pattern, reason in TEST_ACCOUNT_PATTERNS:
        if pattern.match(email):
            return label, reason
    return None


def review_only(email: str) -> str | None:
    """Return the label when the email looks automated but is not confirmed."""
    for label, pattern in REVIEW_ONLY_PATTERNS:
        if pattern.match(email):
            return label
    return None


def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def backup_database(path: Path) -> Path:
    """Checkpoint WAL content and copy the database to a timestamped backup."""
    with connect(path) as con:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = path.with_name(f"{path.name}.backup-{stamp}")
    shutil.copy2(path, destination)
    return destination


# --- Deletion plan ----------------------------------------------------------
# Children first, so foreign keys stay satisfied at every step. Tables without a
# user_id foreign key to users (ai_call_log, quiz_attempts, user_memories,
# study_log, topics_cache) are listed explicitly because SQLite cannot cascade
# through them.

DELETE_PLAN: list[tuple[str, str]] = [
    ("concept_mastery", "delete from concept_mastery where user_id in ({ids})"),
    ("recommendations", "delete from recommendations where user_id in ({ids})"),
    ("assessment_attempts", "delete from assessment_attempts where user_id in ({ids})"),
    ("retrieval_traces", "delete from retrieval_traces where user_id in ({ids})"),
    ("events", "delete from events where user_id in ({ids})"),
    ("ingestion_jobs", "delete from ingestion_jobs where user_id in ({ids})"),
    ("ai_call_log", "delete from ai_call_log where user_id in ({ids})"),
    ("study_log", "delete from study_log where thread_id in (select id from threads where user_id in ({ids}))"),
    (
        "topics_cache",
        "delete from topics_cache where document_id in (select id from documents where thread_id in "
        "(select id from threads where user_id in ({ids})))",
    ),
    ("documents", "delete from documents where thread_id in (select id from threads where user_id in ({ids}))"),
    ("concepts", "delete from concepts where project_id in (select id from threads where user_id in ({ids}))"),
    ("threads", "delete from threads where user_id in ({ids})"),
    ("spaces", "delete from spaces where user_id in ({ids})"),
    ("quiz_attempts", "delete from quiz_attempts where user_id in ({ids})"),
    ("user_memories", "delete from user_memories where user_id in ({ids})"),
    ("users", "delete from users where id in ({ids})"),
]

FK_CHECKS: list[tuple[str, str, str]] = [
    ("spaces", "user_id", "users"),
    ("threads", "user_id", "users"),
    ("documents", "thread_id", "threads"),
    ("concepts", "project_id", "threads"),
    ("concept_mastery", "user_id", "users"),
    ("concept_mastery", "concept_id", "concepts"),
    ("events", "user_id", "users"),
    ("events", "project_id", "threads"),
    ("ingestion_jobs", "user_id", "users"),
    ("ingestion_jobs", "document_id", "documents"),
    ("assessment_attempts", "user_id", "users"),
    ("assessment_attempts", "project_id", "threads"),
    ("recommendations", "user_id", "users"),
    ("recommendations", "project_id", "threads"),
    ("retrieval_traces", "user_id", "users"),
    ("retrieval_traces", "project_id", "threads"),
    ("study_log", "thread_id", "threads"),
    ("topics_cache", "document_id", "documents"),
]

DATA_TABLES = [
    "spaces", "threads", "documents", "concepts", "concept_mastery", "events",
    "ingestion_jobs", "assessment_attempts", "recommendations", "quiz_attempts",
    "user_memories", "retrieval_traces", "ai_call_log", "study_log",
]

THREAD_JOINED = {"documents": "thread_id", "concepts": "project_id", "study_log": "thread_id"}


def snapshot(con: sqlite3.Connection, user_ids: list[str]) -> dict[str, dict[str, int]]:
    """Row counts per table for the given accounts (thread-joined tables included)."""
    result: dict[str, dict[str, int]] = {}
    for user_id in user_ids:
        counts: dict[str, int] = {}
        for table in DATA_TABLES:
            columns = {row["name"] for row in con.execute(f'pragma table_info("{table}")')}
            if "user_id" in columns:
                counts[table] = con.execute(
                    f'select count(*) from "{table}" where user_id = ?', (user_id,)
                ).fetchone()[0]
            elif table in THREAD_JOINED:
                column = THREAD_JOINED[table]
                counts[table] = con.execute(
                    f'select count(*) from "{table}" where {column} in '
                    "(select id from threads where user_id = ?)", (user_id,)
                ).fetchone()[0]
        result[user_id] = counts
    return result


def orphan_report(con: sqlite3.Connection) -> list[str]:
    """Return human-readable foreign-key problems, if any."""
    problems: list[str] = []
    for table, column, parent in FK_CHECKS:
        dangling = con.execute(
            f'select count(*) from "{table}" where {column} is not null and '
            f'{column} not in (select id from "{parent}")'
        ).fetchone()[0]
        if dangling:
            problems.append(f"{table}.{column} -> {parent}: {dangling} dangling row(s)")
    for row in con.execute("pragma foreign_key_check").fetchall():
        problems.append(f"foreign_key_check: table={row[0]} rowid={row[1]} parent={row[2]}")
    return problems


def build_report(
    con: sqlite3.Connection,
    *,
    include_review_only: bool = False,
    extra_emails: set[str] | None = None,
) -> tuple[list, list, list]:
    """Split accounts into (to_delete, preserve, review) using the patterns above.

    ``extra_emails`` are operator-confirmed addresses (``--delete-email``);
    ``include_review_only`` also deletes accounts matching REVIEW_ONLY_PATTERNS.
    Protected ids/addresses are honoured in both cases.
    """
    confirmed = {email.strip().lower() for email in (extra_emails or set()) if email.strip()}
    rows = con.execute(
        "select id, email, display_name, role, created_at from users order by created_at"
    ).fetchall()
    to_delete, preserve, review = [], [], []
    for row in rows:
        email = row["email"].lower()
        if row["email"] in PROTECTED_EMAILS or row["id"] in PROTECTED_IDS:
            preserve.append(row)
            continue
        hit = classify(row["email"])
        ambiguous = review_only(row["email"])
        if hit:
            to_delete.append((row, hit[0], hit[1]))
        elif email in confirmed:
            to_delete.append((row, "operator_confirmed", "explicitly confirmed via --delete-email"))
        elif ambiguous and include_review_only:
            to_delete.append((row, ambiguous, "operator-confirmed automated-check account"))
        elif ambiguous:
            review.append((row, ambiguous))
        else:
            preserve.append(row)
    return to_delete, preserve, review


def print_report(to_delete: list, preserve: list, review: list, summary_only: bool) -> None:
    by_label: dict[str, int] = {}
    for _row, label, _reason in to_delete:
        by_label[label] = by_label.get(label, 0) + 1

    print(f"Total accounts           : {len(to_delete) + len(preserve) + len(review)}")
    print(f"Test accounts to delete  : {len(to_delete)}")
    print(f"Accounts to preserve     : {len(preserve)}")
    print(f"Ambiguous (not deleted)  : {len(review)}\n")

    reasons = {label: reason for label, _pattern, reason in TEST_ACCOUNT_PATTERNS}
    reasons.update({label: "operator-confirmed automated-check account" for label, _p in REVIEW_ONLY_PATTERNS})
    reasons["operator_confirmed"] = "explicitly confirmed via --delete-email"
    ordered = [label for label, _p, _r in TEST_ACCOUNT_PATTERNS]
    ordered += [label for label, _p in REVIEW_ONLY_PATTERNS] + ["operator_confirmed"]

    print("Accounts to delete by pattern:")
    for label in ordered:
        if label in by_label:
            print(f"  {label:18s} {by_label[label]:4d}   ({reasons[label]})")

    print("\nAccounts that will be preserved:")
    for row in preserve:
        print(f"  {row['created_at']} | {row['email']:32s} | {row['display_name']} ({row['role']})")

    if review:
        print("\nAMBIGUOUS - matches no documented test pattern source; NOT deleted:")
        for row, label in review:
            print(f"  {row['created_at']} | {row['email']:42s} | {row['display_name']} [{label}]")

    if summary_only:
        print(f"\n(omitted {len(to_delete)} test account emails; omit --summary-only to list them)")
        return

    print("\nTest accounts that will be deleted:")
    for row, _label, _reason in to_delete:
        print(f"  {row['created_at']} | {row['email']:56s} | {row['display_name']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--database", help="SQLite file to clean (defaults to DATABASE_URL / backend/chatbot.db)")
    parser.add_argument("--apply", action="store_true", help="perform the deletion (default is a dry run)")
    parser.add_argument("--no-backup", action="store_true", help="skip the automatic pre-deletion backup")
    parser.add_argument("--summary-only", action="store_true", help="print counts without the full email list")
    parser.add_argument(
        "--delete-email",
        action="append",
        default=[],
        metavar="ADDRESS",
        help="also delete this explicitly confirmed account (repeatable; protected rows still win)",
    )
    parser.add_argument(
        "--include-review-only",
        action="store_true",
        help="also delete accounts that look automated but have no source-level evidence (operator-confirmed)",
    )
    args = parser.parse_args(argv)

    path = resolve_database_path(args.database)
    if not path.exists():
        print(f"Database not found: {path}")
        return 2
    print(f"Database: {path}\n")

    con = connect(path)
    try:
        to_delete, preserve, review = build_report(
            con, include_review_only=args.include_review_only, extra_emails=set(args.delete_email)
        )
        print_report(to_delete, preserve, review, args.summary_only)

        # Never remove the last administrator.
        admins = {row["email"] for row in con.execute("select email from users where role = 'admin'")}
        doomed = {row["email"] for row, _label, _reason in to_delete}
        surviving = admins - doomed
        if admins and not surviving:
            print(f"\nREFUSING: this deletion would remove every admin account ({sorted(admins)}).")
            return 3
        if doomed & admins:
            print(f"\nNote: admin account(s) {sorted(doomed & admins)} will be deleted; "
                  f"remaining admin(s): {sorted(surviving)}")

        ids = [row["id"] for row, _label, _reason in to_delete]
        before = snapshot(con, [row["id"] for row in preserve])

        if not args.apply:
            print("\nDRY RUN - nothing was deleted. Re-run with --apply to perform the cleanup.")
            return 0
        if not ids:
            print("\nNo confirmed test accounts found; nothing to delete.")
            return 0

        if not args.no_backup:
            print(f"\nBackup written to: {backup_database(path)}")

        placeholders = ",".join("?" * len(ids))
        con.execute("begin immediate")
        try:
            print("\nDeleting test-only rows:")
            for label, statement in DELETE_PLAN:
                cursor = con.execute(statement.format(ids=placeholders), ids)
                print(f"  {label:22s} removed {cursor.rowcount:5d}")
            con.commit()
        except Exception:
            con.rollback()
            raise
    finally:
        con.close()

    return verify(path, to_delete, preserve, before)


def verify(path: Path, to_delete: list, preserve: list, before: dict) -> int:
    """Re-read the database and confirm the cleanup changed nothing but test data."""
    con = connect(path)
    try:
        remaining = con.execute("select id, email from users").fetchall()
        remaining_emails = {row["email"] for row in remaining}
        remaining_ids = {row["id"] for row in remaining}
        still_there = [row["email"] for row, _l, _r in to_delete if row["email"] in remaining_emails]
        preserved_ok = all(row["id"] in remaining_ids for row in preserve)
        after = snapshot(con, [row["id"] for row in preserve])
        changed = {
            user_id: {
                table: (before[user_id][table], after[user_id][table])
                for table in before[user_id]
                if before[user_id][table] != after[user_id][table]
            }
            for user_id in before
            if before[user_id] != after[user_id]
        }
        problems = orphan_report(con)
        integrity = con.execute("pragma integrity_check").fetchone()[0]

        print("\n=== VERIFICATION ===")
        print(f"accounts remaining           : {len(remaining)}")
        print(f"test accounts still present  : {len(still_there)} (expected 0)")
        print(f"preserved accounts intact    : {preserved_ok}")
        print(f"preserved data unchanged     : {not changed}" + (f" -> {changed}" if changed else ""))
        print(f"foreign keys / orphan rows   : {'intact' if not problems else problems}")
        print(f"integrity_check              : {integrity}")

        if still_there or not preserved_ok or changed or problems or integrity != "ok":
            print("\nRESULT: REVIEW REQUIRED")
            return 1
        print("\nRESULT: cleanup verified")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())

