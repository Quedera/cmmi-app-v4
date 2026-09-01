#!/usr/bin/env python3
"""
Migration 005 — DEF-011: replace missing A5 descriptor on Q377 (DB id 458).

What this fixes
---------------
Question Q377 (DB id=458, "What is the Scope of Event Management?") has
options 0–4 populated but option 5 shows "(no descriptor)". DEF-011
provides the replacement text for A5.

Display Q number vs DB row id note
----------------------------------
The UI numbers questions sequentially by ORDER BY discipline_id,
area_number, id (total = 622 in v3). So display Q377 corresponds to
DB row id 458. The defect was cited using the display Q number; this
migration targets the DB row id.

Replacement
-----------
A5: "Event Management provides comprehensive end-to-end monitoring
     across the service landscape, using automated correlation,
     predictive analysis and continual improvement to support business
     services and operational resilience."

A0–A4 are kept untouched. Idempotent: re-running is a no-op if A5
already matches.

How to apply
------------
    cd /home/nortski101/.openclaw/workspace/cmmi-app-v3
    python3 backend/migrations/005_DEF-011_event_mgmt_scope_a5.py

References
----------
- DEF-011 record: see #defect-backlog Discord channel, 2026-07-31.
- Version tag: v0.1.5 (DEF-011 through DEF-014 batch)
"""
import sqlite3
import json
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "cmmi_v3.sqlite"
QUESTION_DB_ID = 458  # display Q377
EXPECTED_QUESTION_TEXT = "What is the Scope of Event Management?"
NEW_A5_TEXT = (
    "Event Management provides comprehensive end-to-end monitoring "
    "across the service landscape, using automated correlation, "
    "predictive analysis and continual improvement to support business "
    "services and operational resilience."
)


def main() -> int:
    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            "SELECT question_text, options_json FROM questions WHERE id = ?",
            (QUESTION_DB_ID,),
        )
        row = c.fetchone()
        if row is None:
            print(f"ERROR: question id={QUESTION_DB_ID} not found in DB.", file=sys.stderr)
            return 2

        qtext, opts_json = row
        if qtext.strip() != EXPECTED_QUESTION_TEXT:
            print(
                f"ERROR: id={QUESTION_DB_ID} question text mismatch.\n"
                f"  expected: {EXPECTED_QUESTION_TEXT!r}\n"
                f"  found:    {qtext!r}\n"
                f"Refusing to update — manual review required.",
                file=sys.stderr,
            )
            return 3

        opts = json.loads(opts_json)
        scores = sorted(o["score"] for o in opts)
        if scores != [0, 1, 2, 3, 4, 5]:
            print(
                f"ERROR: id={QUESTION_DB_ID} has unexpected score set: {scores}\n"
                f"Refusing to update — manual review required.",
                file=sys.stderr,
            )
            return 3

        a5 = next(o for o in opts if o["score"] == 5)
        if a5["text"].strip() == NEW_A5_TEXT:
            print(f"OK: Q{QUESTION_DB_ID} A5 already matches replacement — no-op.")
            return 0

        old_text = a5["text"]
        a5["text"] = NEW_A5_TEXT
        c.execute(
            "UPDATE questions SET options_json = ? WHERE id = ?",
            (json.dumps(opts), QUESTION_DB_ID),
        )
        conn.commit()
        print(f"OK: Q{QUESTION_DB_ID} A5 updated.")
        print(f"  old: {old_text!r}")
        print(f"  new: {NEW_A5_TEXT!r}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())