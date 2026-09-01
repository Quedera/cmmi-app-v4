from fastapi import APIRouter, HTTPException
from typing import Optional
import json
from backend.db import database as db

router = APIRouter(prefix="/api", tags=["question_bank"])


@router.get("/disciplines")
def get_disciplines():
    rows = db.query_all("SELECT id, name FROM disciplines ORDER BY id")
    return [{"id": r["id"], "name": r["name"]} for r in rows]


@router.get("/questions")
def get_all_questions(disciplines: Optional[str] = None):
    """
    Return all questions, optionally filtered to specific discipline IDs.

    `disciplines` is a comma-separated list of IDs, e.g. `?disciplines=1,2,3`.
    Omit (or pass empty) to return all 622 questions across all 28 disciplines.
    """
    if disciplines:
        try:
            ids = [int(d) for d in disciplines.split(",") if d.strip()]
        except ValueError:
            raise HTTPException(400, "Invalid disciplines parameter (must be comma-separated integers)")
        if not ids:
            raise HTTPException(400, "disciplines parameter is empty")
        placeholders = ",".join("?" * len(ids))
        rows = db.query_all(f"""
            SELECT q.id, q.area_name, q.area_number, q.question_text,
                   q.options_json, d.name as discipline, d.id as discipline_id
            FROM questions q
            JOIN disciplines d ON d.id = q.discipline_id
            WHERE q.discipline_id IN ({placeholders})
            ORDER BY d.id, q.area_number, q.id
        """, tuple(ids))
    else:
        rows = db.query_all("""
            SELECT q.id, q.area_name, q.area_number, q.question_text,
                   q.options_json, d.name as discipline, d.id as discipline_id
            FROM questions q
            JOIN disciplines d ON d.id = q.discipline_id
            ORDER BY d.id, q.area_number, q.id
        """)
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "discipline": r["discipline"],
            "discipline_id": r["discipline_id"],
            "area": r["area_name"],
            "area_number": r["area_number"],
            "question": r["question_text"],
            "options": json.loads(r["options_json"]),
        })
    return result


@router.get("/disciplines/{discipline_id}/questions")
def get_discipline_questions(discipline_id: int):
    rows = db.query_all("""
        SELECT q.id, q.area_name, q.area_number, q.question_text, q.options_json
        FROM questions q
        WHERE q.discipline_id = ?
        ORDER BY q.area_number, q.id
    """, (discipline_id,))
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "area": r["area_name"],
            "area_number": r["area_number"],
            "question": r["question_text"],
            "options": json.loads(r["options_json"]),
        })
    return result