// Use relative URLs — Next.js rewrites handle proxying to the backend
const API_BASE = "";

export interface Discipline {
  id: number;
  name: string;
}

export interface QuestionOption {
  score: number;
  text: string;
}

export interface Question {
  id: number;
  discipline: string;
  discipline_id: number;
  area: string;
  area_number: number;
  question: string;
  options: QuestionOption[];
}

export interface AnswerInput {
  question_id: number;
  score: number;
}

export interface DisciplineResult {
  discipline: string;
  total_score: number;
  max_score: number;
  pct_cmmi: number;
  completed_at?: string;
}

export type SessionScope = "full" | "single" | "multi";

export interface Session {
  session_id: string;
  scope: SessionScope;
  selected_disciplines: number[] | null;
  respondent_role: string | null;
  respondent_company: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface SessionCreate {
  scope: SessionScope;
  selected_disciplines?: number[] | null;
  respondent_role?: string | null;
  respondent_company?: string | null;
}

// Pulse UX item 5 — the 20-role dropdown options shown on the start page.
// Mirrored on backend via the validator in SessionCreate (Other is rendered
// as a separate text input on the frontend; combined into respondent_role
// before POST). Kept in sync by hand — small enough not to warrant a config
// service.
export const ROLE_OPTIONS: string[] = [
  "Service Desk Analyst",
  "Service Desk Manager",
  "Incident Manager",
  "Problem Manager",
  "Change Manager",
  "Release & Deployment Manager",
  "Service Level Manager",
  "Availability Manager",
  "Capacity Manager",
  "IT Service Continuity Manager",
  "Information Security Manager",
  "IT Financial Manager",
  "Supplier Manager",
  "Knowledge / Catalogue Manager",
  "Strategy / Portfolio Manager",
  "IT Director / CIO",
  "Operations Manager",
  "DevOps / SRE Lead",
  "IT Architect",
  "Consultant / Assessor",
];
export const OTHER_ROLE_VALUE = "__other__";

export const api = {
  async getDisciplines(): Promise<Discipline[]> {
    const res = await fetch(`${API_BASE}/api/disciplines`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch disciplines");
    return res.json();
  },

  async getQuestions(disciplines?: number[]): Promise<Question[]> {
    const url = disciplines && disciplines.length > 0
      ? `${API_BASE}/api/questions?disciplines=${disciplines.join(",")}`
      : `${API_BASE}/api/questions`;
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch questions");
    return res.json();
  },

  async submitAnswers(sessionId: string, answers: AnswerInput[]): Promise<{ session_id: string; saved: number; results: DisciplineResult[] }> {
    const res = await fetch(`${API_BASE}/api/submit`, {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, answers }),
    });
    if (!res.ok) throw new Error("Failed to submit answers");
    return res.json();
  },

  async getResults(sessionId: string): Promise<{ session_id: string; results: DisciplineResult[] }> {
    const res = await fetch(`${API_BASE}/api/results/${sessionId}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch results");
    return res.json();
  },

  async createSession(payload: SessionCreate): Promise<Session> {
    const res = await fetch(`${API_BASE}/api/sessions`, {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => null);
      throw new Error(detail?.detail?.[0]?.msg || `Failed to create session (${res.status})`);
    }
    return res.json();
  },

  async getSession(sessionId: string): Promise<Session> {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Session not found");
    return res.json();
  },

  async exportPDF(sessionId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/export.pdf`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to export PDF");
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cmmi-${sessionId}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },

  async exportXLSX(sessionId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/export.xlsx`, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to export XLSX");
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cmmi-${sessionId}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
};
