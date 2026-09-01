#!/usr/bin/env python3
"""
Migration 011 — DEF-017: replace missing A5 descriptor on Q8 (DB id 571).

What this fixes
---------------
Question Q8 (DB id=571, "Is the operational area separate from ordinary
office space, and secure?") has options 0–4 populated but option 5
shows "(no descriptor)". DEF-017 provides the replacement text for A5.

Display Q number vs DB row id note
----------------------------------
Display Q8 corresponds to DB row id 571 in v3 (numbering is by
ORDER BY discipline_id, area_number, id; total = 622). Q8 is the
first question in display order because discipline 1 (Service Operation)
has the lowest discipline_id.

Replacement
-----------
A5: "The operational area is fully separate from office space,
     physically secure, with controlled access, environmental
     safeguards and continuous monitoring in place to protect service
     continuity."

A0–A4 are kept untouched. Idempotent: re-running is a no-op if A5
already matches.

Source
------
DRAFT text from TACbot, confirmed by Tyto alba (DEF-017 OP) on
2026-08-01 with permission to ship using the suggested text.

How to apply
------------
    cd /home/nortski101/.openclaw/workspace/cmmi-app-v3
    python3 backend/migrations/011_DEF-017_operational_area_security_a5.py

References
----------
- DEF-017 record: see #defect-backlog Discord channel, 2026-08-01.
- Version tag: v0.1.6
"""
import sqlite3
import json
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "cmmi_v3.sqlite"
QUESTION_DB_ID = 571  # display Q8
EXPECTED_QUESTION_TEXT = "Is the operational area separate from ordinary office space, and secure?"
NEW_A5_TEXT = (
    "The operational area is fully separate from office space, "
    "physically secure, with controlled access, environmental "
    "safeguards and continuous monitoring in place to protect service "
    "continuity."
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