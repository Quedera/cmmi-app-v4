#!/usr/bin/env python3
"""
Migration 007 — DEF-013: replace all six "(no descriptor)" entries on
Q412 (DB id 287).

What this fixes
---------------
Question Q412 (DB id=287, "Is there a process in place to review
service documentation?") has all six options showing "(no descriptor)".
DEF-013 provides the full replacement set for A0–A5.

Display Q number vs DB row id note
----------------------------------
Display Q412 corresponds to DB row id 287 in v3 (numbering is by
ORDER BY discipline_id, area_number, id; total = 622).

Replacements
------------
A0: "There is no process to review service documentation."
A1: "Service documentation is reviewed occasionally on an informal basis
     with no defined schedule or ownership."
A2: "A documented review process exists for key service documentation,
     but it is not consistently followed."
A3: "Service documentation is reviewed against defined criteria, with
     review responsibilities, approvals and version control established."
A4: "Documentation reviews are integrated into Service Management
     processes and conducted at planned intervals or following
     significant changes."
A5: "A formal review process ensures all service documentation remains
     accurate, complete and current, with findings driving continual
     improvement."

How to apply
------------
    cd /home/nortski101/.openclaw/workspace/cmmi-app-v3
    python3 backend/migrations/007_DEF-013_review_doc_descriptors.py

References
----------
- DEF-013 record: see #defect-backlog Discord channel, 2026-07-31.
- Version tag: v0.1.5
"""
import sqlite3
import json
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "cmmi_v3.sqlite"
QUESTION_DB_ID = 287  # display Q412
EXPECTED_QUESTION_TEXT = "Is there a process in place to review service documentation?"

NEW_OPTIONS = {
    0: "There is no process to review service documentation.",
    1: "Service documentation is reviewed occasionally on an informal basis with no defined schedule or ownership.",
    2: "A documented review process exists for key service documentation, but it is not consistently followed.",
    3: "Service documentation is reviewed against defined criteria, with review responsibilities, approvals and version control established.",
    4: "Documentation reviews are integrated into Service Management processes and conducted at planned intervals or following significant changes.",
    5: "A formal review process ensures all service documentation remains accurate, complete and current, with findings driving continual improvement.",
}


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

        by_score = {o["score"]: o for o in opts}
        new_opts = [{"score": s, "text": NEW_OPTIONS[s]} for s in range(6)]

        already_current = all(by_score[s]["text"] == NEW_OPTIONS[s] for s in range(6))
        if already_current:
            print(f"OK: Q{QUESTION_DB_ID} all six options already match replacement — no-op.")
            return 0

        c.execute(
            "UPDATE questions SET options_json = ? WHERE id = ?",
            (json.dumps(new_opts), QUESTION_DB_ID),
        )
        conn.commit()
        print(f"OK: Q{QUESTION_DB_ID} all six options replaced:")
        for o in new_opts:
            print(f"  A{o['score']}: {o['text'][:90]}{'...' if len(o['text']) > 90 else ''}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())