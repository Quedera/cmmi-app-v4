#!/usr/bin/env python3
"""
Migration 009 — DEF-015: replace missing A0 descriptor on Q347 (DB id 199).

What this fixes
---------------
Question Q347 (DB id=199, "Is it clear to all staff how they are expected
to support the plan should it need to be put into practise?") has
options 1–5 populated but option 0 shows "(no descriptor)". DEF-015
provides the replacement text for A0.

Display Q number vs DB row id note
----------------------------------
Display Q347 corresponds to DB row id 199 in v3 (numbering is by
ORDER BY discipline_id, area_number, id; total = 622).

Replacement
-----------
A0: "No, staff are not aware of any continuity plan and would not
     know what to do in a major incident."

A1–A5 are kept untouched. Idempotent: re-running is a no-op if A0
already matches.

Source
------
DRAFT text from TACbot, confirmed by Tyto alba (DEF-015 OP) on
2026-08-01 with permission to ship using the suggested text.

How to apply
------------
    cd /home/nortski101/.openclaw/workspace/cmmi-app-v3
    python3 backend/migrations/009_DEF-015_service_continuity_awareness_a0.py

References
----------
- DEF-015 record: see #defect-backlog Discord channel, 2026-08-01.
- Version tag: v0.1.6 (DEF-015 through DEF-017 batch)
"""
import sqlite3
import json
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "cmmi_v3.sqlite"
QUESTION_DB_ID = 199  # display Q347
EXPECTED_QUESTION_TEXT_FRAGMENT = "Is it clear to all staff how they are expected to support the plan"
NEW_A0_TEXT = "No, staff are not aware of any continuity plan and would not know what to do in a major incident."


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
        if EXPECTED_QUESTION_TEXT_FRAGMENT not in qtext:
            print(
                f"ERROR: id={QUESTION_DB_ID} question text does not contain expected fragment.\n"
                f"  expected fragment: {EXPECTED_QUESTION_TEXT_FRAGMENT!r}\n"
                f"  found:             {qtext!r}\n"
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