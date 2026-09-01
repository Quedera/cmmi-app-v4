import uuid
import json
from fastapi import APIRouter
from pydantic import BaseModel
from backend.db import database as db

router = APIRouter(prefix="/api", tags=["assessments"])


class AnswerInput(BaseModel):
    question_id: int
    score: int


class AnswerSubmission(BaseModel):
    session_id: str
    answers: list[AnswerInput]


class DisciplineResult(BaseModel):
    discipline: str
    total_score: float
    max_score: float
    pct_cmmi: float


@router.post("/submit")
def submit_answers(sub: AnswerSubmission):
    # Backward-compat: ensure a sessions row exists. If the client created one
    # via POST /api/sessions, INSERT OR IGNORE is a no-op (preserves scope +
    # selected_disciplines). If not, tag as scope='full' so legacy callers
    # (e.g. Tyto's pre-V4 demo run) still work.
    db.execute(
        """INSERT OR IGNORE INTO sessions (session_id, scope, selected_disciplines)
           VALUES (?, 'full', NULL)""",
        (sub.session_id,),
    )

    saved = 0
    for a in sub.answers:
        db.execute(
            "INSERT OR REPLACE INTO answers (session_id, question_id, selected_score) VALUES (?, ?, ?)",
            (sub.session_id, a.question_id, a.score),
        )
        saved += 1

    # Calculate per-discipline results
    rows = db.query_all("""
        SELECT d.name as discipline, q.id as qid, a.selected_score,
               q.options_json
        FROM answers a
        JOIN questions q ON q.id = a.question_id
        JOIN disciplines d ON d.id = q.discipline_id
        WHERE a.session_id = ?
        ORDER BY d.id, q.id
    """, (sub.session_id,))

    # Group by discipline
    from collections import defaultdict
    by_discipline = defaultdict(list)
    for r in rows:
        by_discipline[r["discipline"]].append(r)

    results = []
    for discipline, answers in by_discipline.items():
        total_score = sum(a["selected_score"] for a in answers)
        # Max = number of questions * 5 (max option score)
        max_score = len(answers) * 5.0
        pct_cmmi = total_score / max_score if max_score > 0 else 0
        # INSERT OR REPLACE so re-submit overwrites cleanly (UNIQUE INDEX
        # idx_results_session_discipline enforces session_id +
        # discipline_name uniqueness — fixes the duplicate-row bug).
        db.execute(
            """INSERT OR REPLACE INTO results
               (session_id, discipline_name, total_score, max_score, pct_cmmi)
               VALUES (?, ?, ?, ?, ?)""",
            (sub.session_id, discipline, total_score, max_score, pct_cmmi),
        )
        results.append(DisciplineResult(
            discipline=discipline,
            total_score=total_score,
            max_score=max_score,
            pct_cmmi=round(pct_cmmi, 4),
        ))

    # Mark session completed (auto-completion on submit).
    db.execute(
        "UPDATE sessions SET completed_at = CURRENT_TIMESTAMP WHERE session_id = ?",
        (sub.session_id,),
    )

    return {"session_id": sub.session_id, "saved": saved, "results": results}


@router.get("/results/{session_id}")
def get_results(session_id: str):
    rows = db.query_all("""
        SELECT discipline_name, total_score, max_score, pct_cmmi, completed_at
        FROM results
        WHERE session_id = ?
        ORDER BY pct_cmmi DESC
    """, (session_id,))
    if not rows:
        return {"session_id": session_id, "results": []}
    return {
        "session_id": session_id,
        "results": [
            {
                "discipline": r["discipline_name"],
                "total_score": r["total_score"],
                "max_score": r["max_score"],
                "pct_cmmi": round(r["pct_cmmi"], 4),
                "completed_at": r["completed_at"],
            }
            for r in rows
        ],
    }


@router.get("/sessions/{session_id}/answers")
def get_session_answers(session_id: str):
    rows = db.query_all("""
        SELECT question_id, selected_score FROM answers WHERE session_id = ?
    """, (session_id,))
    return {str(r["question_id"]): r["selected_score"] for r in rows}