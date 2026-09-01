#!/usr/bin/env python3
"""
Migration 006 — DEF-012: replace missing A1–A4 descriptors + full A5
overwrite on Q411 (DB id 286).

What this fixes
---------------
Question Q411 (DB id=286, "Are there standard OLA's produced") has:
  - A0: "There are no OLA's"  (kept as-is, confirmed by Tyto alba 2026-08-01)
  - A1, A2, A3, A4: "(no descriptor)"  ← need replacement
  - A5: "All Service have standard OLA's agreed and produced"  ← needs
        full replacement (overwrite, not append — confirmed by Tyto).

Display Q number vs DB row id note
----------------------------------
Display Q411 corresponds to DB row id 286 in v3 (numbering is by
ORDER BY discipline_id, area_number, id; total = 622).

Replacements
------------
A1: "Operational Level Agreements (OLAs) are produced on an ad hoc basis,
     with no standard format or governance."
A2: "Standard OLA templates exist and are used for some services,
     although adoption is inconsistent."
A3: "Standard OLAs are documented for all relevant services, with
     defined roles, responsibilities and service targets."
A4: "OLAs are regularly reviewed, approved and aligned with Service
     Level Agreements (SLAs), supporting effective service delivery."
A5: "Standard OLAs are fully implemented, maintained and integrated with
     Service Management processes, with performance measured and
     continually improved."

How to apply
------------
    cd /home/nortski101/.openclaw/workspace/cmmi-app-v3
    python3 backend/migrations/006_DEF-012_olas_a1_to_a5.py

References
----------
- DEF-012 record: see #defect-backlog Discord channel, 2026-07-31.
- Tyto alba confirmations on A0 keep-as-is + A5 overwrite vs append:
  2026-08-01 11:37 BST.
- Version tag: v0.1.5
"""
import sqlite3
import json
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "cmmi_v3.sqlite"
QUESTION_DB_ID = 286  # display Q411
EXPECTED_QUESTION_TEXT = "Are there standard OLA's produced"

NEW_OPTIONS = {
    0: "There are no OLA's",  # unchanged
    1: "Operational Level Agreements (OLAs) are produced on an ad hoc basis, with no standard format or governance.",
    2: "Standard OLA templates exist and are used for some services, although adoption is inconsistent.",
    3: "Standard OLAs are documented for all relevant services, with defined roles, responsibilities and service targets.",
    4: "OLAs are regularly reviewed, approved and aligned with Service Level Agreements (SLAs), supporting effective service delivery.",
    5: "Standard OLAs are fully implemented, maintained and integrated with Service Management processes, with performance measured and continually improved.",
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

        # Build new options list
        by_score = {o["score"]: o for o in opts}
        new_opts = []
        for score in range(6):
            existing = by_score[score]
            new_opts.append({"score": score, "text": NEW_OPTIONS[score]})

        # Idempotency check: are we already current?
        already_current = all(
            by_score[s]["text"] == NEW_OPTIONS[s] for s in range(6)
        )
        if already_current:
            print(f"OK: Q{QUESTION_DB_ID} all six options already match replacement — no-op.")
            return 0

        c.execute(
            "UPDATE questions SET options_json = ? WHERE id = ?",
            (json.dumps(new_opts), QUESTION_DB_ID),
        )
        conn.commit()
        print(f"OK: Q{QUESTION_DB_ID} options updated (A0 kept, A1–A5 replaced):")
        for o in new_opts:
            marker = " (kept)" if o["score"] == 0 else " (replaced)"
            print(f"  A{o['score']}{marker}: {o['text'][:90]}{'...' if len(o['text']) > 90 else ''}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())