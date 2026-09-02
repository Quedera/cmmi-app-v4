#!/usr/bin/env python3
"""
Migration 014 — clean underscored / truncated discipline names.

Background
----------
The seeded cmmi_v4.sqlite shipped with four malformed discipline names:
    27  'Release _ Deployment Mngt_'
    28  'Service Asset _ Config_ Mngt_'
     4  'Service Validation _ Testing'
    23  'Common Operation Mngt Activitie'   (truncated, no underscores)

These are the v4 importer leaking raw Excel sheet names instead of using the
canonical display names. They render with underscores on the assessment page
and break the per-discipline breakdown in the exported PDF/XLSX.

This migration maps each known bad name to its canonical form. Idempotent:
each UPDATE has a WHERE name = '<bad>' guard, so re-running is a no-op.

How to apply
------------
    # 1. stop the running backend (holds the DB open):
    sudo systemctl stop cmmi-v4-backend.service

    # 2. apply the migration (takes the DB path as arg):
    python3 backend/migrations/014_clean_discipline_names.py \\
        /home/nortski101/.openclaw/workspace/cmmi-app-v4/cmmi_v4.sqlite

    # 3. start the backend:
    sudo systemctl start cmmi-v4-backend.service

The deploy-v4.sh helper script wraps all three steps (use --with-migrations).
"""
import sqlite3
import sys
from pathlib import Path

# (bad_name, canonical_name)
RENAMES = [
    ("Release _ Deployment Mngt_",          "Release and Deployment Management"),
    ("Service Asset _ Config_ Mngt_",       "Service Asset and Configuration Management"),
    ("Service Validation _ Testing",        "Service Validation and Testing"),
    ("Common Operation Mngt Activitie",     "Common Operation Management Activities"),
]


def main(db_path: str) -> int:
    p = Path(db_path)
    if not p.exists():
        print(f"ERROR: DB not found at {db_path}", file=sys.stderr)
        return 1

    print(f"Connecting to {db_path}")
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Snapshot before
    bad_names = {bad for bad, _ in RENAMES}
    placeholders = ",".join("?" * len(bad_names))
    cur.execute(
        f"SELECT id, name FROM disciplines WHERE name IN ({placeholders}) ORDER BY id",
        tuple(bad_names),
    )
    before = cur.fetchall()
    print(f"Found {len(before)} malformed discipline row(s):")
    for row_id, name in before:
        print(f"  id={row_id:3}  '{name}'")

    if not before:
        print("Nothing to do — DB already clean.")
        con.close()
        return 0

    # Apply renames (idempotent — each UPDATE is guarded)
    for bad, canonical in RENAMES:
        cur.execute(
            "UPDATE disciplines SET name = ? WHERE name = ?",
            (canonical, bad),
        )
        if cur.rowcount:
            print(f"  renamed: '{bad}' → '{canonical}' ({cur.rowcount} row)")
        else:
            print(f"  no-op:   '{bad}' (no matching row)")

    con.commit()

    # Verify after
    cur.execute(
        f"SELECT id, name FROM disciplines WHERE name IN ({placeholders}) ORDER BY id",
        tuple(bad_names),
    )
    remaining = cur.fetchall()
    if remaining:
        print(f"WARNING: {len(remaining)} malformed row(s) still present:", file=sys.stderr)
        for row_id, name in remaining:
            print(f"  id={row_id:3}  '{name}'", file=sys.stderr)
        con.close()
        return 2

    print("All malformed names cleaned. DB is consistent.")
    con.close()
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: 014_clean_discipline_names.py <path-to-cmmi_v4.sqlite>", file=sys.stderr)
        sys.exit(1)
    sys.exit(main(sys.argv[1]))