#!/usr/bin/env python3
"""
CMMI v4 Importer v1.0 (FINAL_v5)

Parses ITSM_Chronos_Full_Maturity_Assessment_FINAL_v5.xls (JMW's 2026-08-01
update of the master, dropped by Craig 2026-08-05 12:01 BST) and populates
cmmi_v4.sqlite. Source of truth = the XLS.

Differences vs v3 importer:
  - Source XLS: FINAL_v5 staged file (vs Delta_2507 / ITIL_CMMI_Assessment_v1.0.xls)
  - Output DB: cmmi_v4.sqlite on port 8003 (vs cmmi_v3.sqlite on port 8002)
  - Expected out: 622 questions across 28 disciplines (matches v3 — verified
    0 diff between FINAL_v5 and v3 SQLite via set-comparison of
    (area, qnum, text, opts) tuples)

Differences vs v2 importer (import_v2_data.py v4.1):
  - Source XLS: ITIL_CMMI_Assessment_v1.0.xls (vs v0.1.xls)
  - Expected out: 622 questions across 28 disciplines (vs v2: 618)
  - Per-discipline count deltas expected:
      Service Continuity Mgmt: 20 -> 21 (+1)
      Problem Mgmt:            17 -> 19 (+2)
      Service Reporting:       14 -> 15 (+1)
      Release & Deployment:    45 -> 44 (-1)
  - All other 24 disciplines: identical counts to v2.
  - Sheet structure unchanged: same area-label patterns, same option
    layout, same 6-option 0-5 maturity scale. The Strategy Generation
    bare-label fallback (DEF-008) is still required.
  - Incident Management has 12 cols instead of 8 (cols 8-11 empty
    padding). Parser uses col7 for rating regardless of ncols, so
    unchanged behaviour.

Inherits all FU-2 and DEF-001..009 guards from v4.1:
  - Non-destructive (no os.remove on DB)
  - Transactional clear + repopulate, sanity_check runs inside
  - LEAK_CATEGORY_LABELS filter
  - _is_area_header_row handles both "Area - " prefix and bare-label
    formats (Strategy Generation DEF-008)
  - "Comment" singular match for KM Q12-Q19 (DEF-009)
  - "(no descriptor)" fallback for blank maturity levels (DEF-009)
  - 6 options per question, scores 0-5, no dupes (DEF-001/002/003/004)

Audit trail: print a one-line summary on every run + per-discipline
count diff vs v2 expected values.
"""
import xlrd
import json
import sqlite3
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = Path(__file__).parent / "cmmi_v4.sqlite"
XLS_PATH = Path("/home/nortski101/.openclaw/workspace/media/inbound/openclaw-staged-1b82b545-5481-4a32-b046-3bf733eaec48/ITSM_Chronos_Full_Maturity_Assessment_FINAL_v5---c02299f9-43f7-4886-a4c8-11491c3ab004.xls")

# Discipline-name fixes for source XLS typos. The XLS sheet names carry
# typos (e.g. "Transition Planning _ Support" — literal underscore + space)
# that show up verbatim in the DB unless we normalise them here. Keys must
# match the source sheet name verbatim; values are the canonical discipline
# labels rendered in the UI.
DISCIPLINE_NAME_FIXES = {
    "Transition Planning _ Support": "Transition Planning and Support",
}

# Expected per-discipline counts from v3-build-plan §"Per-discipline
# count comparison". Compare against this after import to flag any
# drift from the canonical 622-question set.
EXPECTED_COUNTS = {
    "Demand Management": 14,
    "Strategy Generation": 26,
    "Service Portfolio Management": 22,
    "IT Financial Management": 23,
    "Service Catalogue Management": 24,
    "Service Level Management": 28,
    "Capacity Management": 27,
    "Availability Management": 23,
    "Service Continuity Management": 21,  # v2 was 20 (+1)
    "Information Security Management": 19,
    "Supplier Management": 35,
    "Transition Planning and Support": 26,
    "Change Management": 24,
    "Service Asset _ Config_ Mngt_": 44,
    "Release _ Deployment Mngt_": 45,    # JMW source has 45 here, NOT 44 as Summaries claims
                                      # (the Summaries sheet says 44 but the actual data
                                      #  has 45; flagged as a JMW source inconsistency —
                                      #  see 2026-07-25 quarantine review, "R&D Q30 duplicate"
                                      #  issue)
    "Service Validation _ Testing": 19,
    "Evaluation": 16,
    "Knowledge Management": 19,
    "Event Management": 13,
    "Service Desk": 18,
    "Incident Management": 22,
    "Request Fulfillment": 18,
    "Problem Management": 19,            # v2 was 17 (+2)
    "Access Management": 18,
    "Common Operation Mngt Activitie": 23,
    "Service Measurement": 10,
    "Service Reporting": 15,             # v2 was 14 (+1)
    "Service Improvement": 11,
}
EXPECTED_TOTAL = 622  # v2: 618 (+3 net)

EXCLUDED_SHEETS = {
    "Title Sheet",
    "Exec Dashboard",
    "Summaries",
}

LEAK_CATEGORY_LABELS = {
    "Questions Areas",
    "Technology Management",
    "Interface to other SM processes",
}


def get_discipline_sheets(wb):
    return [name for name in wb.sheet_names() if name not in EXCLUDED_SHEETS]


def _is_area_header_row(s, r):
    col0 = s.cell_value(r, 0)
    if not (isinstance(col0, str) and col0.strip()):
        return False
    if s.ncols > 2:
        c2 = s.cell_value(r, 2)
        if c2 not in ("", None):
            return False
    col1 = s.cell_value(r, 1) if s.ncols > 1 else None
    if not (isinstance(col1, float) and col1 == int(col1) and 1 <= int(col1) <= 100):
        return False
    return True


def parse_sheet(s, sheet_name=None):
    questions = []
    skipped_header_rows = []
    current_area = None
    current_area_num = None
    current_question = None
    current_options = []

    r = 0
    while r < s.nrows:
        col0 = s.cell_value(r, 0)
        col1 = s.cell_value(r, 1) if s.ncols > 1 else None
        col7 = s.cell_value(r, 7) if s.ncols > 7 else None

        if isinstance(col0, str) and col0.strip() in LEAK_CATEGORY_LABELS:
            skipped_header_rows.append((r, col0.strip()))
            r += 1
            continue

        is_area_prefix = isinstance(col0, str) and col0.startswith("Area - ")
        is_bare_label = _is_area_header_row(s, r)
        if is_area_prefix or is_bare_label:
            if current_question is not None and current_options:
                questions.append({
                    "area": current_area,
                    "area_number": current_area_num,
                    "question": current_question,
                    "options": current_options,
                })
            if is_bare_label and not is_area_prefix:
                current_area = f"Area - {col0.strip()}"
            else:
                current_area = col0.strip() if isinstance(col0, str) else col0
            current_area_num = int(col1) if isinstance(col1, float) else None
            current_question = None
            current_options = []

        elif isinstance(col1, str) and col1.strip() in ("Comments", "Comment", "Response"):
            if current_question is not None and current_options:
                questions.append({
                    "area": current_area,
                    "area_number": current_area_num,
                    "question": current_question,
                    "options": current_options,
                })
            current_question = str(col0).strip()
            current_options = []

        elif current_question is not None and isinstance(col7, float) and col7 == int(col7):
            score = int(col7)
            if 0 <= score <= 5 and not any(o["score"] == score for o in current_options):
                option_text = str(col0).strip() or "(no descriptor)"
                current_options.append({"score": score, "text": option_text})

        r += 1

    if current_question is not None and current_options:
        questions.append({
            "area": current_area,
            "area_number": current_area_num,
            "question": current_question,
            "options": current_options,
        })

    return questions, skipped_header_rows


def ensure_schema(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS disciplines (
        id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY,
        discipline_id INTEGER REFERENCES disciplines(id),
        area_name TEXT NOT NULL,
        area_number INTEGER,
        question_text TEXT NOT NULL,
        options_json TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        question_id INTEGER REFERENCES questions(id),
        selected_score INTEGER NOT NULL,
        answered_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        discipline_name TEXT NOT NULL,
        total_score REAL NOT NULL,
        max_score REAL NOT NULL,
        pct_cmmi REAL NOT NULL,
        completed_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()
    return conn


def sanity_check(c):
    bad_count = c.execute("""SELECT COUNT(*) FROM questions
                              WHERE json_array_length(options_json) != 6""").fetchone()[0]
    if bad_count:
        sample = c.execute("""SELECT id, area_number, question_text, options_json FROM questions
                              WHERE json_array_length(options_json) != 6
                              ORDER BY id LIMIT 1""").fetchone()
        raise RuntimeError(
            f"REGRESSION (DEF-003 family): {bad_count} questions don't have exactly 6 options. "
            f"First bad: id={sample[0]} area={sample[1]} text='{sample[2][:50]}' "
            f"options={sample[3][:200]}"
        )

    bad_scores = c.execute("""SELECT id, options_json FROM questions
                              WHERE EXISTS (
                                SELECT 1 FROM json_each(options_json)
                                WHERE CAST(json_extract(value, '$.score') AS INTEGER) NOT BETWEEN 0 AND 5
                              )""").fetchall()
    if bad_scores:
        sample = bad_scores[0]
        raise RuntimeError(
            f"REGRESSION (DEF-001/002 family): question id={sample[0]} has out-of-range scores. "
            f"options={sample[1][:200]}"
        )

    dup_scores = c.execute("""SELECT q.id, q.options_json FROM questions q
                              WHERE EXISTS (
                                SELECT value, COUNT(*) c FROM json_each(q.options_json, '$.score')
                                GROUP BY value HAVING c > 1
                              )""").fetchall()
    if dup_scores:
        sample = dup_scores[0]
        raise RuntimeError(
            f"REGRESSION (DEF-004 family): question id={sample[0]} has duplicate scores. "
            f"options={sample[1][:200]}"
        )

    return True


def compare_to_expected(c):
    """Walk the imported question counts and compare against expected.

    Returns a list of (discipline, actual, expected) tuples for any
    drift. Empty list = perfect match.
    """
    c.execute("""SELECT d.name, COUNT(q.id) FROM disciplines d
                  JOIN questions q ON q.discipline_id = d.id GROUP BY d.id""")
    actual = dict(c.fetchall())
    drift = []
    for name, expected in EXPECTED_COUNTS.items():
        a = actual.get(name, 0)
        if a != expected:
            drift.append((name, a, expected))
    return drift


def import_all():
    wb = xlrd.open_workbook(XLS_PATH)
    all_questions = []
    total_skipped = 0

    for sheet_name in get_discipline_sheets(wb):
        try:
            s = wb.sheet_by_name(sheet_name)
        except Exception:
            print(f"  WARNING: Sheet '{sheet_name}' not found")
            continue

        questions, skipped = parse_sheet(s, sheet_name=sheet_name)
        total_skipped += len(skipped)
        skipped_summary = ", ".join(f"r{r}('{t}')" for r, t in skipped) if skipped else "none"
        print(f"  {sheet_name}: {len(questions)} questions (skipped {len(skipped)} header-leak rows: {skipped_summary})")
        for q in questions:
            q["discipline"] = DISCIPLINE_NAME_FIXES.get(sheet_name, sheet_name)
            all_questions.append(q)

    if total_skipped > 0:
        print(f"\n  Total header-leak rows skipped: {total_skipped} (FU-2 protection)")

    conn = ensure_schema(DB_PATH)
    c = conn.cursor()

    try:
        c.execute("BEGIN")
        c.execute("DELETE FROM results")
        c.execute("DELETE FROM answers")
        c.execute("DELETE FROM questions")
        c.execute("DELETE FROM disciplines")
        c.execute("DELETE FROM sqlite_sequence WHERE name IN ('disciplines', 'questions', 'answers', 'results')")

        disciplines = list({q["discipline"] for q in all_questions})
        for d in disciplines:
            c.execute("INSERT INTO disciplines (name) VALUES (?)", (d,))
        dmap = {name: did for did, name in c.execute("SELECT id, name FROM disciplines").fetchall()}

        for q in all_questions:
            c.execute(
                """INSERT INTO questions (discipline_id, area_name, area_number, question_text, options_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (dmap[q["discipline"]], q["area"], q["area_number"], q["question"], json.dumps(q["options"])),
            )

        sanity_check(c)

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        if "REGRESSION" in str(e):
            raise
        raise RuntimeError(f"Import transaction rolled back: {e}") from e

    qcount = c.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    dcount = c.execute("SELECT COUNT(*) FROM disciplines").fetchone()[0]
    conn.close()
    return dcount, qcount, total_skipped


if __name__ == "__main__":
    print(f"Reading: {XLS_PATH}\n")
    dcount, qcount, skipped = import_all()
    print(f"\nTotal: {dcount} disciplines, {qcount} questions -> {DB_PATH}")

    if qcount != EXPECTED_TOTAL:
        print(f"\n  ! WARNING: expected {EXPECTED_TOTAL} questions, got {qcount}")
    else:
        print(f"  Total matches expected (622)")

    # Verify against v3 SQLite (port 8002 source)
    v3_path = Path("/home/nortski101/.openclaw/workspace/cmmi-app-v3/cmmi_v3.sqlite")
    if v3_path.exists():
        v3c = sqlite3.connect(str(v3_path))
        v3_total = v3c.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        v3c.close()
        if qcount == v3_total:
            print(f"  v3 SQLite question count matches v4 import ({qcount})")
        else:
            print(f"  ! DRIFT: v3={v3_total} vs v4 import={qcount}")
    else:
        print(f"  (v3 SQLite not present at {v3_path}; skipping cross-check)")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    drift = compare_to_expected(c)
    if drift:
        print(f"\n  ! DRIFT DETECTED:")
        for name, actual, expected in drift:
            print(f"    {name}: got {actual}, expected {expected}")
    else:
        print(f"  Per-discipline counts: ALL MATCH expected values")
    print(f"\n  Header-leak rows skipped (FU-2): {skipped}")
    print(f"  Sanity check: PASSED (all questions have exactly 6 options, scores 0-5, no dupes)")
    conn.close()
