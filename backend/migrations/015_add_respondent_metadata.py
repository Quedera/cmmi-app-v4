#!/usr/bin/env python3
"""
Migration 015 — add respondent metadata columns to sessions.

Background
----------
Item 5 of the Pulse UX cleanup: capture optional role + company at the start
of an assessment so the respondent is identifiable on the output document
and (later) per-org analytics.

Adds two nullable TEXT columns to `sessions`:
    respondent_role     TEXT   -- selected from a fixed dropdown + Other (free text)
    respondent_company  TEXT   -- free text, capped at 120 chars in the API

Both columns are optional — empty/NULL values render blank in PDF/XLSX
exports, no breakage on existing data. Idempotent (PRAGMA-guarded ALTERs).

How to apply
------------
    sudo systemctl stop cmmi-v4-backend.service
    python3 backend/migrations/015_add_respondent_metadata.py \\
        /home/nortski101/.openclaw/workspace/cmmi-app-v4/cmmi_v4.sqlite
    sudo systemctl start cmmi-v4-backend.service

The deploy-v4.sh --with-migrations helper wraps all three steps.
"""
import sqlite3
import sys
from pathlib import Path

COLUMNS = [
    ("respondent_role", "TEXT"),
    ("respondent_company", "TEXT"),
]


def main(db_path: str) -> int:
    p = Path(db_path)
    if not p.exists():
        print(f"ERROR: DB not found at {db_path}", file=sys.stderr)
        return 1

    print(f"Connecting to {db_path}")
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.execute("PRAGMA table_info(sessions)")
    existing = {row[1] for row in cur.fetchall()}
    print(f"Existing columns: {sorted(existing)}")

    added = 0
    for col_name, col_type in COLUMNS:
        if col_name in existing:
            print(f"  no-op: {col_name} already exists")
            continue
        cur.execute(f"ALTER TABLE sessions ADD COLUMN {col_name} {col_type}")
        print(f"  added: {col_name} {col_type}")
        added += 1

    con.commit()

    # Verify after
    cur.execute("PRAGMA table_info(sessions)")
    after = {row[1] for row in cur.fetchall()}
    missing = {c for c, _ in COLUMNS} - after
    if missing:
        print(f"ERROR: columns still missing after migration: {missing}", file=sys.stderr)
        con.close()
        return 2

    print(f"Done. {added} column(s) added. Schema consistent.")
    con.close()
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: 015_add_respondent_metadata.py <path-to-cmmi_v4.sqlite>", file=sys.stderr)
        sys.exit(1)
    sys.exit(main(sys.argv[1]))