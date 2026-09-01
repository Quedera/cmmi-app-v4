#!/usr/bin/env python3
"""
Migration 012 — DEF-018: replace stray backtick A0 on Q36 (DB id 41).

What this fixes
---------------
Question Q36 (DB id=41, "Is there awareness that IT Service Portfolios
exist?") has option 0 containing a single stray backtick character
("`") — almost certainly a keystroke error from the XLS source. DEF-018
provides the replacement text for A0.

Display Q number vs DB row id note
----------------------------------
Display Q36 corresponds to DB row id 41 in v3 (numbering is by
ORDER BY discipline_id, area_number, id; total = 622).

Replacement
-----------
A0: "No, there is no awareness that IT Service Portfolios exist."

A1–A5 are kept untouched. Idempotent: re-running is a no-op if A0
already matches the replacement text.

Source
------
DRAFT text from TACbot, acked by Tyto alba (DEF-018 OP) and MacWood
(second-human ack) on 2026-08-01.

How to apply
------------
    cd /home/nortski101/.openclaw/workspace/cmmi-app-v3
    python3 backend/migrations/012_DEF-018_it_service_portfolio_awareness_a0.py

References
----------
- DEF-018 record: see #defect-backlog Discord channel, 2026-08-01.
- Version tag: v0.1.7
"""
import sqlite3
import json
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "cmmi_v3.sqlite"
QUESTION_DB_ID = 41  # display Q36
EXPECTED_QUESTION_TEXT = "Is there awareness that IT Service Portfolios exist ?"
NEW_A0_TEXT = "No, there is no awareness that IT Service Portfolios exist."


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

        a0 = next(o for o in opts if o["score"] == 0)
        if a0["text"].strip() == NEW_A0_TEXT:
            print(f"OK: Q{QUESTION_DB_ID} A0 already matches replacement — no-op.")
            return 0

        old_text = a0["text"]
        a0["text"] = NEW_A0_TEXT
        c.execute(
            "UPDATE questions SET options_json = ? WHERE id = ?",
            (json.dumps(opts), QUESTION_DB_ID),
        )
        conn.commit()
        print(f"OK: Q{QUESTION_DB_ID} A0 updated.")
        print(f"  old: {old_text!r}")
        print(f"  new: {NEW_A0_TEXT!r}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())