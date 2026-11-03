"""
Sessions router — V4 scope-aware session creation/lookup + PDF/XLSX export.

End points
----------
POST /api/sessions                       — create a session with scope + disciplines
GET  /api/sessions/{id}                  — read session (scope, disciplines, timestamps)
PATCH /api/sessions/{id}/complete        — mark the session completed (set completed_at)
GET  /api/sessions/{id}/export.pdf       — server-side PDF (results-only summary)
GET  /api/sessions/{id}/export.xlsx      — server-side XLSX (one sheet per discipline + summary)

Scope semantics
---------------
- "full"   — selected_disciplines must be None (or empty); user answered all 28
- "single" — selected_disciplines must be a single-element list [id]
- "multi"  — selected_disciplines must be a 2-28 element list

Discipline IDs are 1..28 (matches `disciplines.id` in the DB).

Build log: #cmmi channel thread 1536414485181632614
"""
import json
import os
import uuid
from io import BytesIO
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, validator

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.db import database as db

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# --- Pulse brand assets ----------------------------------------------------
# Resolve the shield path relative to this file so it works whether the
# backend is launched from /workspace/cmmi-app-v4 (systemd, local) or from
# inside a Docker container with a different cwd. Override via env var if the
# layout ever changes (PULSE_LOGO_PATH=/abs/path/pulse-shield.png).
# Note: pulse-shield.png is the single shield mark cropped out of the
# pulse-icon.png header asset — the older pulse-lockup-dual.png contained two
# shields side-by-side and looked like a duplicate logo on the export cover.
_DEFAULT_LOGO = (
    Path(__file__).resolve().parent.parent.parent
    / "frontend"
    / "public"
    / "assets"
    / "pulse-shield.png"
)
PULSE_LOGO_PATH = Path(os.environ.get("PULSE_LOGO_PATH", str(_DEFAULT_LOGO)))

# QUEDERA master palette (from branding/quedera-palette.json, 2026-08-26)
PULSE_CYAN = colors.HexColor("#06B6D4")   # PULSE product brand
PULSE_NAVY = colors.HexColor("#0D182A")   # QUEDERA master wordmark
PULSE_NAVY_RGB = "0D182A"
PULSE_CYAN_RGB = "06B6D4"

SessionScope = Literal["full", "single", "multi"]

# Canonical discipline metadata: id -> name. We re-validate against this
# so the API rejects stale IDs (e.g. discipline 29 would otherwise pass).
_DISCIPLINE_IDS: set[int] = set()


def _load_discipline_ids() -> set[int]:
    """Load the live set of discipline IDs (cached at module import)."""
    global _DISCIPLINE_IDS
    if not _DISCIPLINE_IDS:
        rows = db.query_all("SELECT id FROM disciplines")
        _DISCIPLINE_IDS = {r["id"] for r in rows}
    return _DISCIPLINE_IDS


# --- CMMI helpers (mirror the frontend cmmi.ts) ---

def _cmmi_level(pct: float) -> int:
    if pct >= 1.0:
        return 5
    if pct >= 0.8:
        return 4
    if pct >= 0.6:
        return 3
    if pct >= 0.4:
        return 2
    if pct >= 0.2:
        return 1
    return 1


# Mirror of frontend/src/lib/advisories.ts (kept in sync by hand).
_ADVISORIES = [
    (0.0, 0.4, "Initial",
     "Service operations are largely reactive — success depends on individual "
     "heroics, not repeatable process. Establish a basic incident workflow "
     "(record, categorise, resolve, close) and a single source of truth for "
     "ongoing issues. Until every incident is captured, no further maturity is "
     "meaningful."),
    (0.4, 0.6, "Managed",
     "Repeatable processes exist but vary by team. Pick one process (incident, "
     "request, or change), document its steps, owners, and exit criteria, and "
     "roll it out org-wide. That's the floor for everything above."),
    (0.6, 0.8, "Defined",
     "Process is defined and consistently applied — you're at the industry "
     "baseline for ITSM. To move further, start measuring outcomes (resolution "
     "time, first-contact fix rate, change failure rate). You can't manage what "
     "you don't measure."),
    (0.8, 1.0, "Quantitatively Managed",
     "You're using data to control service quality. Next: set statistical "
     "process-control limits on your key ITSM metrics and act on early-warning "
     "signals before they breach SLA."),
    (1.0, 1.01, "Optimising",
     "Top of the maturity scale. Stay here by institutionalising continuous "
     "improvement: root-cause analysis on major incidents, deliberate process "
     "experimentation, and feeding lessons learned back into organisational "
     "standards."),
]


def _get_advisory(pct: float) -> tuple[str, str]:
    clamped = max(0.0, min(1.0, pct))
    for pct_min, pct_max, label, text in _ADVISORIES:
        if pct_min <= clamped < pct_max:
            return label, text
    return _ADVISORIES[-1][2], _ADVISORIES[-1][3]


def _sheet_safe_name(name: str) -> str:
    """Excel sheet name: max 31 chars, no \\ / ? * [ ] :."""
    bad = set('\\/:*?[]')
    cleaned = "".join("_" if c in bad else c for c in name)
    return cleaned[:31]


# --- Pydantic models ---

class SessionCreate(BaseModel):
    scope: SessionScope
    # Optional because scope='full' has no discipline list. For scope='single'
    # we require exactly 1; for 'multi' we require 2..28.
    selected_disciplines: Optional[list[int]] = None
    # Pulse UX item 5: optional respondent metadata. Both fields are stored
    # as-is (after trim + length cap), then rendered into the PDF/XLSX outputs.
    respondent_role: Optional[str] = None
    respondent_company: Optional[str] = None

    @validator("respondent_role")
    def _trim_role(cls, v):
        if v is None:
            return None
        v = v.strip()
        return v[:120] if v else None

    @validator("respondent_company")
    def _trim_company(cls, v):
        if v is None:
            return None
        v = v.strip()
        return v[:120] if v else None

    @validator("selected_disciplines")
    def _validate_disciplines(cls, v, values):
        scope = values.get("scope")
        ids = _load_discipline_ids()

        if scope == "full":
            if v:
                raise ValueError("selected_disciplines must be empty for scope='full'")
            return None

        if not v:
            raise ValueError(f"selected_disciplines is required for scope='{scope}'")

        if scope == "single" and len(v) != 1:
            raise ValueError("scope='single' requires exactly 1 selected_disciplines")

        if scope == "multi" and not (2 <= len(v) <= 28):
            raise ValueError("scope='multi' requires 2..28 selected_disciplines")

        # De-dup and validate against the live discipline set
        seen = set()
        for d in v:
            if d not in ids:
                raise ValueError(f"Invalid discipline_id={d} (not in DB)")
            if d in seen:
                raise ValueError(f"Duplicate discipline_id={d}")
            seen.add(d)
        return v


class SessionOut(BaseModel):
    session_id: str
    scope: SessionScope
    selected_disciplines: Optional[list[int]]
    respondent_role: Optional[str] = None
    respondent_company: Optional[str] = None
    created_at: str
    completed_at: Optional[str]


# Shared SELECT column list for the sessions table — keeps create/read/complete
# queries consistent so the row keys always include the respondent fields.
_SESSION_COLS = (
    "session_id, scope, selected_disciplines, "
    "respondent_role, respondent_company, "
    "created_at, completed_at"
)


def _row_to_session(row) -> SessionOut:
    """Convert a sqlite3.Row sessions row to a SessionOut."""
    raw = row["selected_disciplines"]
    selected = json.loads(raw) if raw else None
    keys = row.keys()
    return SessionOut(
        session_id=row["session_id"],
        scope=row["scope"],
        selected_disciplines=selected,
        # Defensive: the columns exist post-migration-015; if someone runs the
        # old DB without the migration, fall back to None instead of KeyError.
        respondent_role=row["respondent_role"] if "respondent_role" in keys else None,
        respondent_company=row["respondent_company"] if "respondent_company" in keys else None,
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


@router.post("", response_model=SessionOut, status_code=201)
def create_session(payload: SessionCreate):
    """Create a new assessment session with scope + disciplines."""
    session_id = str(uuid.uuid4())
    selected_json = json.dumps(payload.selected_disciplines) if payload.selected_disciplines else None

    db.execute(
        f"""INSERT INTO sessions
            (session_id, scope, selected_disciplines,
             respondent_role, respondent_company)
            VALUES (?, ?, ?, ?, ?)""",
        (session_id, payload.scope, selected_json,
         payload.respondent_role, payload.respondent_company),
    )

    row = db.query_one(
        f"SELECT {_SESSION_COLS} FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    return _row_to_session(row)


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: str):
    """Read a session's scope + timestamps."""
    row = db.query_one(
        f"SELECT {_SESSION_COLS} FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    if row is None:
        raise HTTPException(404, f"Session {session_id} not found")
    return _row_to_session(row)


@router.patch("/{session_id}/complete", response_model=SessionOut)
def complete_session(session_id: str):
    """Mark a session completed (sets completed_at to now)."""
    row = db.query_one(
        "SELECT session_id FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    if row is None:
        raise HTTPException(404, f"Session {session_id} not found")

    db.execute(
        "UPDATE sessions SET completed_at = CURRENT_TIMESTAMP WHERE session_id = ?",
        (session_id,),
    )
    row = db.query_one(
        f"SELECT {_SESSION_COLS} FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    return _row_to_session(row)


# --- Export endpoints ---

@router.get("/{session_id}/export.pdf")
def export_pdf(session_id: str):
    """Server-side branded PDF: results-only summary, per-discipline level."""
    sess = db.query_one(
        f"SELECT {_SESSION_COLS} FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    if sess is None:
        raise HTTPException(404, f"Session {session_id} not found")

    results = db.query_all(
        "SELECT discipline_name, total_score, max_score, pct_cmmi, completed_at "
        "FROM results WHERE session_id = ? ORDER BY discipline_name",
        (session_id,),
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch,
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    story = []

    # Cover — Pulse brand: single shield mark on top, cyan rule, navy title.
    if PULSE_LOGO_PATH.exists():
        # pulse-shield.png is 770×515 (≈1.50:1). 1.2in wide → 0.80in tall.
        story.append(Image(str(PULSE_LOGO_PATH), width=1.2 * inch, height=0.80 * inch))
        story.append(Spacer(1, 0.15 * inch))
        # Thin cyan rule under the lockup (acts as the brand divider).
        rule = Table([[""]], colWidths=[7.5 * inch], rowHeights=[0.04 * inch])
        rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PULSE_CYAN)]))
        story.append(rule)
        story.append(Spacer(1, 0.25 * inch))

    pulse_title_style = ParagraphStyle(
        "PulseTitle",
        parent=styles["Title"],
        textColor=PULSE_NAVY,
        fontName="Helvetica-Bold",
    )
    story.append(Paragraph("ITSM Maturity Assessment", pulse_title_style))
    story.append(Paragraph(
        "<font color='#06B6D4'><b>QUEDERA · Pulse</b></font>",
        styles["Normal"],
    ))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"<b>Session:</b> {session_id}", styles["Normal"]))
    story.append(Paragraph(f"<b>Scope:</b> {sess['scope']}", styles["Normal"]))
    if sess["selected_disciplines"]:
        try:
            ids = json.loads(sess["selected_disciplines"])
            story.append(Paragraph(
                f"<b>Disciplines:</b> {', '.join(str(i) for i in ids)}",
                styles["Normal"],
            ))
        except (json.JSONDecodeError, TypeError):
            pass
    story.append(Paragraph(f"<b>Created:</b> {sess['created_at']}", styles["Normal"]))
    if sess["completed_at"]:
        story.append(Paragraph(f"<b>Completed:</b> {sess['completed_at']}", styles["Normal"]))

    # Respondent metadata (Pulse UX item 5). Both fields optional — only render
    # the line if at least one is set.
    role = sess["respondent_role"] if "respondent_role" in sess.keys() else None
    company = sess["respondent_company"] if "respondent_company" in sess.keys() else None
    if role and company:
        story.append(Paragraph(
            f"<b>Respondent:</b> {role} at {company}", styles["Normal"],
        ))
    elif role:
        story.append(Paragraph(f"<b>Respondent:</b> {role}", styles["Normal"]))
    elif company:
        story.append(Paragraph(f"<b>Respondent:</b> {company}", styles["Normal"]))

    story.append(Spacer(1, 0.3 * inch))

    # Per-discipline table
    if results:
        story.append(Paragraph("Per-Discipline Results", styles["Heading2"]))
        story.append(Spacer(1, 0.1 * inch))

        data = [["Discipline", "Score", "Max", "%", "Level"]]
        overall_total = 0.0
        overall_max = 0.0
        for r in results:
            pct = r["pct_cmmi"]
            level = _cmmi_level(pct)
            data.append([
                r["discipline_name"],
                f"{r['total_score']:.0f}",
                f"{r['max_score']:.0f}",
                f"{pct * 100:.0f}%",
                f"L{level}",
            ])
            overall_total += r["total_score"]
            overall_max += r["max_score"]

        t = Table(data, colWidths=[2.8 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch, 0.6 * inch])
        t.setStyle(TableStyle([
            # Pulse cyan header (was generic #0a1628 navy), navy text for contrast.
            ("BACKGROUND", (0, 0), (-1, 0), PULSE_CYAN),
            ("TEXTCOLOR", (0, 0), (-1, 0), PULSE_NAVY),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3 * inch))

        # Overall / Scope average
        if overall_max > 0:
            overall_pct = overall_total / overall_max
            overall_level = _cmmi_level(overall_pct)
            avg_label = "Overall Maturity" if sess["scope"] == "full" else "Scope Average"
            advisory_label, advisory_text = _get_advisory(overall_pct)
            story.append(Paragraph(
                f"<b>{avg_label}:</b> {overall_pct * 100:.0f}% (L{overall_level} — {advisory_label})",
                styles["Heading3"],
            ))
            story.append(Spacer(1, 0.2 * inch))

            # Advisory
            story.append(Paragraph("Advisory", styles["Heading3"]))
            story.append(Paragraph(advisory_text, styles["Normal"]))

            if sess["scope"] != "full":
                story.append(Spacer(1, 0.2 * inch))
                story.append(Paragraph(
                    "<i>Note: partial scope — overall L1–L5 claim is per-discipline only. "
                    "Top-line is a scope average.</i>",
                    styles["Italic"],
                ))
    else:
        story.append(Paragraph("No results recorded for this session yet.", styles["Normal"]))

    # Pulse brand footer line.
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph(
        "<font color='#06B6D4'><b>QUEDERA · Pulse</b></font> — ITSM Maturity Assessment",
        styles["Italic"],
    ))

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=cmmi-{session_id}.pdf"},
    )


@router.get("/{session_id}/export.xlsx")
def export_xlsx(session_id: str):
    """Server-side XLSX: Summary sheet + one sheet per assessed discipline."""
    sess = db.query_one(
        f"SELECT {_SESSION_COLS} FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    if sess is None:
        raise HTTPException(404, f"Session {session_id} not found")

    results = db.query_all(
        "SELECT discipline_name, total_score, max_score, pct_cmmi, completed_at "
        "FROM results WHERE session_id = ? ORDER BY discipline_name",
        (session_id,),
    )
    answers = db.query_all(
        """
        SELECT a.question_id, a.selected_score, q.area_name, q.area_number,
               q.question_text, d.name AS discipline_name
        FROM answers a
        JOIN questions q ON q.id = a.question_id
        JOIN disciplines d ON d.id = q.discipline_id
        WHERE a.session_id = ?
        ORDER BY d.id, q.area_number, q.id
        """,
        (session_id,),
    )

    wb = Workbook()
    # Pulse brand styles: cyan header fills, navy text.
    pulse_header_fill = PatternFill(
        start_color=PULSE_CYAN_RGB,
        end_color=PULSE_CYAN_RGB,
        fill_type="solid",
    )
    pulse_header_font = Font(bold=True, size=11, color=PULSE_NAVY_RGB)
    pulse_title_font = Font(bold=True, size=16, color=PULSE_NAVY_RGB)
    pulse_label_font = Font(bold=True, size=11, color=PULSE_NAVY_RGB)
    pulse_accent_font = Font(bold=True, size=11, color=PULSE_CYAN_RGB)

    # --- Summary sheet ---
    ws = wb.active
    ws.title = "Summary"

    # Pulse shield top-right of title (D1). Shield is 770×515; scale to 90×60
    # so the wordmark on the cover (A1/A2) keeps the visual weight.
    if PULSE_LOGO_PATH.exists():
        logo = XLImage(str(PULSE_LOGO_PATH))
        logo.width = 90
        logo.height = 60
        ws.add_image(logo, "D1")

    ws["A1"] = "ITSM Maturity Assessment"
    ws["A1"].font = pulse_title_font
    ws["A2"] = "QUEDERA · Pulse"
    ws["A2"].font = Font(bold=True, size=10, color=PULSE_CYAN_RGB)

    ws["A4"] = "Session ID"
    ws["B4"] = session_id
    ws["A5"] = "Scope"
    ws["B5"] = sess["scope"]
    if sess["selected_disciplines"]:
        try:
            ids = json.loads(sess["selected_disciplines"])
            ws["A6"] = "Selected Disciplines"
            ws["B6"] = ", ".join(str(i) for i in ids)
        except (json.JSONDecodeError, TypeError):
            pass
    ws["A7"] = "Created At"
    ws["B7"] = sess["created_at"]
    ws["A8"] = "Completed At"
    ws["B8"] = sess["completed_at"] or ""

    # Respondent metadata (Pulse UX item 5). Reserved rows A9/A10 so the table
    # below keeps its anchor at A12. Blank if unset — no conditional shifting
    # of the per-discipline block.
    ws["A9"] = "Respondent Role"
    ws["B9"] = sess["respondent_role"] if "respondent_role" in sess.keys() and sess["respondent_role"] else ""
    ws["A10"] = "Respondent Company"
    ws["B10"] = sess["respondent_company"] if "respondent_company" in sess.keys() and sess["respondent_company"] else ""

    # Per-discipline summary table (anchored at A12, with row 11 as a gap).
    ws["A12"] = "Discipline"
    ws["B12"] = "Total Score"
    ws["C12"] = "Max Score"
    ws["D12"] = "Percentage"
    ws["E12"] = "Level"
    for col in ["A12", "B12", "C12", "D12", "E12"]:
        ws[col].font = pulse_header_font
        ws[col].fill = pulse_header_fill

    for i, r in enumerate(results, start=13):
        pct = r["pct_cmmi"]
        level = _cmmi_level(pct)
        ws[f"A{i}"] = r["discipline_name"]
        ws[f"B{i}"] = r["total_score"]
        ws[f"C{i}"] = r["max_score"]
        # pct is a 0..1 float; render as a percentage in Excel rather than as
        # a raw decimal (e.g. 0.8 → "80%"). Value stays 0..1 so spreadsheet
        # formulas can still do math against it.
        cell_pct = ws[f"D{i}"]
        cell_pct.value = pct
        cell_pct.number_format = "0%"
        ws[f"E{i}"] = f"L{level}"

    # Overall / scope average at the bottom
    if results:
        overall_total = sum(r["total_score"] for r in results)
        overall_max = sum(r["max_score"] for r in results)
        if overall_max > 0:
            overall_pct = overall_total / overall_max
            overall_level = _cmmi_level(overall_pct)
            avg_label = "Overall Maturity" if sess["scope"] == "full" else "Scope Average"
            summary_row = 13 + len(results) + 1
            ws[f"A{summary_row}"] = avg_label
            ws[f"A{summary_row}"].font = pulse_label_font
            # Same percent-format treatment as the per-discipline rows above.
            cell_pct = ws[f"D{summary_row}"]
            cell_pct.value = overall_pct
            cell_pct.number_format = "0%"
            ws[f"E{summary_row}"] = f"L{overall_level}"

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 15
    ws.column_dimensions["C"].width = 15
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 8

    # --- One sheet per assessed discipline ---
    assessed = {r["discipline_name"] for r in results}
    by_discipline: dict[str, list] = {}
    for a in answers:
        if a["discipline_name"] in assessed:
            by_discipline.setdefault(a["discipline_name"], []).append(a)

    for disc_name in sorted(assessed):
        ws = wb.create_sheet(title=_sheet_safe_name(disc_name))
        ws["A1"] = disc_name
        ws["A1"].font = pulse_title_font

        ws["A2"] = "QUEDERA · Pulse"
        ws["A2"].font = Font(bold=True, size=10, color=PULSE_CYAN_RGB)

        ws["A4"] = "Question ID"
        ws["B4"] = "Area"
        ws["C4"] = "Question"
        ws["D4"] = "Score"
        for col in ["A4", "B4", "C4", "D4"]:
            ws[col].font = pulse_header_font
            ws[col].fill = pulse_header_fill

        qs = by_discipline.get(disc_name, [])
        for i, q in enumerate(qs, start=5):
            ws[f"A{i}"] = q["question_id"]
            ws[f"B{i}"] = q["area_name"]
            ws[f"C{i}"] = q["question_text"]
            ws[f"D{i}"] = q["selected_score"]

        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 30
        ws.column_dimensions["C"].width = 80
        ws.column_dimensions["D"].width = 8

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=cmmi-{session_id}.xlsx"},
    )
