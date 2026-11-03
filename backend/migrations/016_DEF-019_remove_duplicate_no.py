#!/usr/bin/env python3
"""Migration 016 / DEF-019 — remove duplicated ``No`` prefixes.

The affected answer options were written as ``No, no ...`` or ``No, No ...``.
Keep the answer meaning and score, but make the displayed text grammatical.
Idempotent: updates only the known question/score pairs when their old text
is present.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

DB_DEFAULT = Path(__file__).resolve().parent.parent.parent / "cmmi_v4.sqlite"
DB_PATH = Path(os.environ.get("CMMI_DB_PATH", DB_DEFAULT))

FIXES = {
    (125, 1): "No evaluation takes place. It is sometimes considered.",
    (129, 1): "No evaluation takes place. It is not considered.",
    (312, 0): "No registration takes place.",
    (321, 0): "No policy has been defined and it is not seen as a need.",
    (322, 0): "No; neither exists.",
    (323, 0): "No Configuration Model exists.",
    (331, 0): "No secure stores exist.",
    (331, 1): "No secure stores exist; however, a need has been identified to put them in place.",
    (334, 0): "No Configuration Baseline exists.",
    (335, 0): "No Configuration Snapshot process exists.",
    (336, 0): "No Configuration Management Plan exists.",
    (348, 0): "No registration takes place.",
    (610, 0): "No registration takes place.",
}


def main() -> int:
    if not DB_PATH.exists():
        print(f"ERROR: DB not found: {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        changed = 0
        for (question_id, score), new_text in FIXES.items():
            row = conn.execute(
                "SELECT options_json FROM questions WHERE id = ?", (question_id,)
            ).fetchone()
            if row is None:
                raise RuntimeError(f"question {question_id} not found")
            options = json.loads(row[0])
            matches = [o for o in options if o.get("score") == score]
            if len(matches) != 1:
                raise RuntimeError(
                    f"question {question_id} score {score}: expected 1 option, found {len(matches)}"
                )
            if matches[0].get("text") != new_text:
                matches[0]["text"] = new_text
                conn.execute(
                    "UPDATE questions SET options_json = ? WHERE id = ?",
                    (json.dumps(options, ensure_ascii=False), question_id),
                )
                changed += 1
        conn.commit()
        print(f"{DB_PATH}: corrected {changed} option(s)")

        remaining = []
        for question_id, score in FIXES:
            raw = conn.execute(
                "SELECT options_json FROM questions WHERE id = ?", (question_id,)
            ).fetchone()[0]
            option = next(o for o in json.loads(raw) if o.get("score") == score)
            if option.get("text") != FIXES[(question_id, score)]:
                remaining.append((question_id, score, option.get("text")))
        if remaining:
            raise RuntimeError(f"verification failed: {remaining}")
        print("verification: all 13 target options match expected text")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
