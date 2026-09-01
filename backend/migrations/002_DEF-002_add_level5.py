#!/usr/bin/env python3
"""
Migration 002 — DEF-002: add missing level 5 option to Q3 and Q114.

What this fixes
---------------
Q3  ("What is the Scope of Event Management?") had options 0-4 only.
Q114 ("Is the operational area separate from ordinary office space, and secure?")
     had options 0-4 only.

Both questions were missing the level 5 ("Optimised / Excellent") entry
that every other question in the assessment has. This broke the maturity
calculation in `backend/routers/assessments.py` for any session that
answered these questions.

This migration inserts the missing level 5 options. **Idempotent** —
running it twice has no extra effect.

Source-of-truth note (out of scope for DEF-002)
-----------------------------------------------
The missing level 5 rows are in the XLS source `data/CMMI_Test_Sample_v1.xls`.
Re-running `python3 import_test_data.py` will:

  1. Wipe the live `cmmi_test.sqlite` (it does `os.remove(db_path)`
     before recreating — destructive, drops all `answers` and `results`).
  2. Re-import from the broken XLS, reintroducing the bug.

Patching the XLS is out of scope here (see migration 001 for the same note).

How to apply
------------
    cd /home/nortski101/.openclaw/workspace/cmmi-app
    python3 backend/migrations/002_DEF-002_add_level5.py

To verify after applying:

    curl -s http://localhost:8000/api/questions | \
        python3 -c "import sys,json; \
                    d=json.load(sys.stdin); \
                    for qid in (3, 114): \
                        q=[q for q in d if q['id']==qid][0]; \
                        print(f\"Q{qid}:\", [o['score'] for o in q['options']])"

Expected: `Q3: [0, 1, 2, 3, 4, 5]` and `Q114: [0, 1, 2, 3, 4, 5]`.

References
----------
- DEF-002 record: ~/itsm-chronos-defects/defects/DEF-002-missing-level-5.md
- Version tag: v0.1.2
- Original report: Discord message id 1517197929239150602 (channel #defect-backlog)
- Sibling migrations: 003_DEF-003_remove_phantom.py, 004_DEF-004_dedupe_score1.py
"""
import sqlite3
import json
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "cmmi_test.sqlite"

# Question id -> (level 5 text)  mapping
LEVEL5_TEXT = {
    3: "Event Management is used as above but also for Software Licence monitoring "
       "and active business-impact analysis with predictive alerting and trend reporting.",
    114: "All Service Operational activities takes place in secure areas with continuous "
         "environmental monitoring, access logging, and regular audits to maintain "
         "certification (e.g. ISO 27001).",
}


def main() -> int:
    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        n_changed = 0
        for qid, level5_text in LEVEL5_TEXT.items():
            c.execute(
                "SELECT question_text, options_json FROM questions WHERE id = ?",
                (qid,),
            )
            row = c.fetchone()
            if row is None:
                print(f"ERROR: Q{qid} not found in {DB_PATH}", file=sys.stderr)
                return 2

            qtext, opts_json = row
            opts = json.loads(opts_json)
            scores = sorted(o.get("score") for o in opts)

            if 5 in scores:
                existing = next(o for o in opts if o.get("score") == 5)
                if existing.get("text") == level5_text:
                    print(
                        f"OK: Q{qid} already has expected level 5 — migration is a no-op. "
                        f"({len(opts)} options, scores={scores})"
                    )
                    continue
                else:
                    # Mismatch — level 5 exists but with different text. Don't silently overwrite.
                    print(
                        f"WARN: Q{qid} already has level 5 but with different text:\n"
                        f"  existing: {existing.get('text')}\n"
                        f"  expected: {level5_text}\n"
                        f"  skipping — manual resolution required.",
                        file=sys.stderr,
                    )
                    continue

            new_opts = opts + [{"score": 5, "text": level5_text}]
            new_scores = sorted(o["score"] for o in new_opts)
            assert new_scores == [0, 1, 2, 3, 4, 5], f"unexpected: {new_scores}"
            assert len(new_opts) == 6, f"unexpected len: {len(new_opts)}"

            c.execute(
                "UPDATE questions SET options_json = ? WHERE id = ?",
                (json.dumps(new_opts), qid),
            )
            n_changed += 1
            print(
                f"OK: Q{qid} \"{qtext[:60]}\" — added level 5 option: "
                f"\"{level5_text[:60]}...\". Now {len(new_opts)} options, scores={new_scores}."
            )

        conn.commit()
        if n_changed == 0:
            print(f"\nNo changes applied (all questions already have expected level 5).")
        else:
            print(f"\nApplied {n_changed} update(s).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())