#!/usr/bin/env python3
"""
Migration 004 — DEF-004: dedupe the score=1 row in Q116-Q128.

What this fixes
---------------
Thirteen questions (Q116 through Q128) had a 7th option row that
duplicated the score=1 entry. Looking at the data, the duplicate is
ALWAYS the LAST option and ALWAYS has text that is a category-label
leak from the XLS source — one of:

  - "Technology Management"      (Q116, Q117, Q118)
  - "Interface to other SM processes"  (Q119, Q120, Q121, Q122,
                                          Q123, Q124, Q125, Q126,
                                          Q127, Q128)

These are header-row labels from the CMMI areas, not question options.
The "real" level 1 answer is the FIRST score=1 entry in the list (a
sentence-length description specific to the question). Keeping the real
one and dropping the category-label leak restores the standard 0-5
maturity scale.

This migration drops the trailing duplicate. **Idempotent**.

Source-of-truth note (out of scope for DEF-004)
-----------------------------------------------
Root cause is the same as DEF-003: `data/CMMI_Test_Sample_v1.xls` has
rows that look like options (text in col0, integer in col7) but are
actually category headers, and `import_test_data.py` doesn't filter
them. Patching both is a separate fix.

How to apply
------------
    cd /home/nortski101/.openclaw/workspace/cmmi-app
    python3 backend/migrations/004_DEF-004_dedupe_score1.py

To verify after applying:

    for qid in $(seq 116 128); do
        curl -s http://localhost:8000/api/questions | \
            python3 -c "import sys,json; d=json.load(sys.stdin); \
                        q=[q for q in d if q['id']==$qid][0]; \
                        print(f\"Q$qid:\", [o['score'] for o in q['options']])"
    done

Expected: each line shows scores `[0, 1, 2, 3, 4, 5]`.

References
----------
- DEF-004 record: ~/itsm-chronos-defects/defects/DEF-004-duplicated-score-1.md
- Version tag: v0.1.2
- Sibling migrations: 002_DEF-002_add_level5.py, 003_DEF-003_remove_phantom.py
"""
import sqlite3
import json
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "cmmi_test.sqlite"

# The known category-label leak texts. If we see a second score=1 row
# matching one of these, it's the duplicate to drop.
LEAK_CATEGORY_LABELS = {
    "Technology Management",
    "Interface to other SM processes",
}

# Question ids known to be affected
AFFECTED_IDS = list(range(116, 129))  # 116..128 inclusive


def _is_duplicate_score1(opts):
    """Return the index of the trailing score=1 duplicate if present, else None.

    Rules:
    - Exactly 2 options have score=1
    - The second one is the last option in the list
    - The second one's text is in LEAK_CATEGORY_LABELS
    """
    score1_idxs = [i for i, o in enumerate(opts) if o.get("score") == 1]
    if len(score1_idxs) != 2:
        return None
    first, second = score1_idxs
    if second != len(opts) - 1:
        return None
    if opts[second].get("text") not in LEAK_CATEGORY_LABELS:
        return None
    # Sanity: the first score=1 row should be a sentence, not a label
    if opts[first].get("text") in LEAK_CATEGORY_LABELS:
        return None
    return second


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
            dup_idx = _is_duplicate_score1(opts)
            if dup_idx is None:
                # Already clean, or pattern doesn't match (manual review needed)
                score1_count = sum(1 for o in opts if o.get("score") == 1)
                if score1_count == 1:
                    print(
                        f"OK: Q{qid} has exactly one score=1 entry — no-op "
                        f"({len(opts)} options)."
                    )
                else:
                    print(
                        f"WARN: Q{qid} has {score1_count} score=1 entries but the "
                        f"duplicate-pattern check failed. Skipping — manual review required.",
                        file=sys.stderr,
                    )
                    n_skipped += 1
                continue

            removed = opts[dup_idx]
            new_opts = [o for i, o in enumerate(opts) if i != dup_idx]
            new_scores = sorted(o["score"] for o in new_opts)
            assert new_scores == [0, 1, 2, 3, 4, 5], f"unexpected: {new_scores}"
            assert len(new_opts) == 6, f"unexpected len: {len(new_opts)}"

            c.execute(
                "UPDATE questions SET options_json = ? WHERE id = ?",
                (json.dumps(new_opts), qid),
            )
            n_changed += 1
            print(
                f"OK: Q{qid} \"{qtext[:50]}...\" — removed trailing score=1 duplicate "
                f"(text=\"{removed.get('text')}\"). Now {len(new_opts)} options, "
                f"scores={new_scores}."
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