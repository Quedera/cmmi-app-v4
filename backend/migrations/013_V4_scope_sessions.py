#!/usr/bin/env python3
"""
Migration 013 — V4 feature: scope + selected_disciplines + sessions table.

What this adds
--------------
1. New `sessions` table — captures the scope decision (full / single / multi)
   and the selected disciplines (JSON array of discipline IDs, NULL for full).
2. Backfill — existing 622 historical answers all came from a full-scope
   session (V4 was built full-only before this migration). Tag them all
   as `scope='full'`, `selected_disciplines=NULL`.
3. UNIQUE (session_id, discipline_name) on `results` — drive-by fix
   for the duplicate-row bug on re-submit (re-submit would create
   duplicate `results` rows because /api/submit uses plain INSERT
   on `results` instead of INSERT OR REPLACE).

Idempotent — all operations are IF NOT EXISTS / ON CONFLICT.

DB path
-------
Respects `CMMI_DB_PATH` env var (matches the backend pattern in
backend/db/database.py). Defaults to `cmmi_v4.sqlite` sibling to the
project root. Never hardcodes — the existing v1 migrations point at
`cmmi_test.sqlite` which is wrong for v4; this one fixes that.

How to apply
------------
    cd /home/nortski101/.openclaw/workspace/cmmi-app-v4
    python3 backend/migrations/013_V4_scope_sessions.py

To verify after applying:

    python3 -c "
    import sqlite3
    conn = sqlite3.connect('cmmi_v4.sqlite')
    print('sessions:', conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0])
    print('by scope:', list(conn.execute('SELECT scope, COUNT(*) FROM sessions GROUP BY scope')))
    print('idx:', list(conn.execute(\"SELECT name FROM sqlite_master WHERE name='idx_results_session_discipline'\")))
    "

References
----------
- V4 enhancements thread: Discord #cmmi thread 1536414485181632614
- Pre-V4 snapshots: cmmi_v4.sqlite.pre-v4-features-20260811T1827Z
- Sibling migrations: 002-012 (DEF-002 through DEF-018)
"""
import os
import sqlite3
import sys
from pathlib import Path

# Use CMMI_DB_PATH env var to match the backend pattern. Default to v4 DB
# so the script works without explicit env if run from the v4 dir.
_DB_DEFAULT = str(Path(__file__).resolve().parent.parent.parent / "cmmi_v4.sqlite")
DB_PATH = Path(os.environ.get("CMMI_DB_PATH", _DB_DEFAULT))


def main() -> int:
    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()

        # 1. Create sessions table
        print("=== 1. CREATE TABLE sessions ===")
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id     TEXT PRIMARY KEY,
                scope          TEXT NOT NULL CHECK (scope IN ('full','single','multi')),
                selected_disciplines TEXT,
                created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at   TEXT
            )
        """)
        print("OK: sessions table ensured")

        # 2. Backfill from existing answers
        print("\n=== 2. Backfill historical sessions ===")
        c.execute("""
            INSERT OR IGNORE INTO sessions (session_id, scope, selected_disciplines)
            SELECT DISTINCT session_id, 'full', NULL
            FROM answers
        """)
        n_backfilled = c.rowcount
        print(f"OK: backfilled {n_backfilled} historical session(s) as scope='full'")

        # 3. UNIQUE INDEX on results (drive-by fix)
        print("\n=== 3. UNIQUE INDEX on results (session_id, discipline_name) ===")
        # Defensive: check for duplicates first. If any exist, refuse to
        # add the UNIQUE constraint — better to fail loudly than to silently
        # keep duplicates.
        c.execute("""
            SELECT session_id, discipline_name, COUNT(*) AS cnt
            FROM results
            GROUP BY session_id, discipline_name
            HAVING COUNT(*) > 1
        """)
        dupes = c.fetchall()
        if dupes:
            print(f"ERROR: {len(dupes)} duplicate (session_id, discipline_name) rows exist:")
            for d in dupes[:5]:
                print(f"  session_id={d[0][:24]}... discipline={d[1]} count={d[2]}")
            print("\nResolve duplicates first, then re-run this migration.")
            return 2

        c.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_results_session_discipline
            ON results(session_id, discipline_name)
        """)
        print("OK: UNIQUE INDEX idx_results_session_discipline ensured")

        conn.commit()

        # Verification
        print("\n=== Verification ===")
        c.execute("SELECT COUNT(*) FROM sessions")
        n_sessions = c.fetchone()[0]
        print(f"  sessions row count:           {n_sessions}")

        c.execute("SELECT scope, COUNT(*) FROM sessions GROUP BY scope")
        print("  sessions by scope:")
        for row in c.fetchall():
            print(f"    {row[0]:<10s} {row[1]}")

        c.execute("""
            SELECT COUNT(*) FROM results
            WHERE session_id NOT IN (SELECT session_id FROM sessions)
        """)
        orphaned_results = c.fetchone()[0]
        print(f"  orphaned results (no session): {orphaned_results}")

        c.execute("""
            SELECT COUNT(*) FROM answers
            WHERE session_id NOT IN (SELECT session_id FROM sessions)
        """)
        orphaned_answers = c.fetchone()[0]
        print(f"  orphaned answers (no session): {orphaned_answers}")

        c.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_results_session_discipline'
        """)
        idx = c.fetchone()
        print(f"  idx_results_session_discipline: {'present' if idx else 'MISSING'}")

        print("\n=== Migration 013 applied successfully ===")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
