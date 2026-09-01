#!/usr/bin/env python3
"""
Migration 003 — DEF-003: remove phantom "Questions Areas" 7th option.

What this fixes
---------------
Seven questions (Q13, Q31, Q53, Q71, Q88, Q106, Q129) had a phantom 7th
option whose text was literally "Questions Areas" and whose score was
the area number (18, 19, 22, 23, or 29 — never a 0-5 maturity score).

This is a known import-time leak from the XLS source: a section header
row in the spreadsheet (which contains the "Questions Areas" label and
its number in adjacent cells) is being parsed as if it were an option
row. The score column for header rows happens to land on the area
number rather than a maturity level, so the leak survives the current
import's "col7 must be int 0-5" guard — but only for area numbers 18+.

This migration drops the phantom entry from each affected question,
restoring the standard 0-5 maturity scale. **Idempotent**.

Source-of-truth note (out of scope for DEF-003)
-----------------------------------------------
The root cause is in `data/CMMI_Test_Sample_v1.xls` (a header row is
being interpreted as a question option) AND in `import_test_data.py`
(which doesn't filter out rows where col7 is outside the 0-5 range AND
col0 matches a header pattern). Patching both is a separate fix
(see migration 001's same note).

How to apply
------------
    cd /home/nortski101/.openclaw/workspace/cmmi-app
    python3 backend/migrations/003_DEF-003_remove_phantom.py

To verify after applying:

    for qid in 13 31 53 71 88 106 129; do
        curl -s http://localhost:8000/api/questions | \
            python3 -c "import sys,json; d=json.load(sys.stdin); \
                        q=[q for q in d if q['id']==$qid][0]; \
                        print(f\"Q$qid:\", len(q['options']), 'opts,', [o['score'] for o in q['options']])"
    done

Expected: each line shows 6 options with scores `[0, 1, 2, 3, 4, 5]`.

References
----------
- DEF-003 record: ~/itsm-chronos-defects/defects/DEF-003-phantom-7th-option.md
- Version tag: v0.1.2
- Sibling migrations: 002_DEF-002_add_level5.py, 004_DEF-004_dedupe_score1.py
"""
import sqlite3
import json
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "cmmi_test.sqlite"

# Phantom row signature: text == "Questions Areas" (case-sensitive, exact match)
PHANTOM_TEXT = "Questions Areas"

# Question ids known to be affected (per audit 2026-06-18 11:42 BST, see
# ~/itsm-chronos-defects/defects/DEF-001-q40-missing-level-0.md#out-of-scope)
AFFECTED_IDS = [13, 31, 53, 71, 88, 106, 129]


def main() -> int:
    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        n_changed = 0
        n_skipped = 0
        for qid in AFFECTED_IDS:
            c.execute(
                "SELECT question_text, options_json FROM questions WHERE id = ?",
                (qid,),
            )
            row = c.fetchone()
            if row is None:
                print(f"WARN: Q{qid} not found in DB — skipping.", file=sys.stderr)
                n_skipped += 1
                continue

            qtext, opts_json = row
            opts = json.loads(opts_json)
            phantoms = [o for o in opts if o.get("text") == PHANTOM_TEXT]
            if not phantoms:
                # Already clean (or the leak didn't reach this row)
                print(
                    f"OK: Q{qid} has no phantom '{PHANTOM_TEXT}' entry — no-op "
                    f"({len(opts)} options)."
                )
                continue

            if len(phantoms) > 1:
                print(
                    f"WARN: Q{qid} has {len(phantoms)} '{PHANTOM_TEXT}' entries — "
                    f"removing all (unexpected; please verify).",
                    file=sys.stderr,
                )

            new_opts = [o for o in opts if o.get("text") != PHANTOM_TEXT]
            new_scores = sorted(o["score"] for o in new_opts)

            # Sanity: the remaining scores should be the 0-5 scale (or a subset)
            expected_subset = [0, 1, 2, 3, 4, 5]
            if not all(s in expected_subset for s in new_scores):
                print(
                    f"WARN: Q{qid} after phantom removal has unexpected scores "
                    f"{new_scores} (expected 0-5). Skipping — manual review required.",
                    file=sys.stderr,
                )
                n_skipped += 1
                continue

            c.execute(
                "UPDATE questions SET options_json = ? WHERE id = ?",
                (json.dumps(new_opts), qid),
            )
            n_changed += 1
            removed_scores = [p.get("score") for p in phantoms]
            print(
                f"OK: Q{qid} \"{qtext[:50]}...\" — removed {len(phantoms)} phantom "
                f"'{PHANTOM_TEXT}' entry (score={removed_scores}). "
                f"Now {len(new_opts)} options, scores={new_scores}."
            )

        conn.commit()
        if n_changed == 0:
            print(f"\nNo changes applied.")
        else:
            print(f"\nApplied {n_changed} update(s).")
        if n_skipped:
            print(f"Skipped {n_skipped} question(s) — manual review required.", file=sys.stderr)
            return 3
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())