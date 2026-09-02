"use client";
import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, Question, Session } from "@/lib/api";

const ANSWERS_KEY = "cmmi_answers";

function getSavedAnswers(sessionId: string): Record<string, number> {
  try {
    const raw = window.localStorage.getItem(`${ANSWERS_KEY}:${sessionId}`);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveAnswer(sessionId: string, qid: number, score: number) {
  try {
    const answers = getSavedAnswers(sessionId);
    answers[String(qid)] = score;
    window.localStorage.setItem(`${ANSWERS_KEY}:${sessionId}`, JSON.stringify(answers));
  } catch {}
}

export default function Assess() {
  const params = useParams();
  const router = useRouter();
  const sessionId = (params?.session_id as string) ?? "";

  const [session, setSession] = useState<Session | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [savedAnswers, setSavedAnswers] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
    if (!sessionId) return;

    api.getSession(sessionId)
      .then((sess) => {
        setSession(sess);
        return api.getQuestions(sess.selected_disciplines || undefined);
      })
      .then(setQuestions)
      .catch((e) => {
        console.error(e);
        setError(e.message || "Failed to load session");
      })
      .finally(() => {
        setSavedAnswers(getSavedAnswers(sessionId));
        setLoading(false);
      });
  }, [sessionId]);

  const currentQ = questions[currentIdx];
  const answeredCount = Object.keys(savedAnswers).length;
  const progress = questions.length > 0 ? (answeredCount / questions.length) * 100 : 0;

  const handleSelect = useCallback((score: number) => {
    if (!currentQ || !sessionId) return;
    const updated = { ...savedAnswers, [currentQ.id]: score };
    setSavedAnswers(updated);
    saveAnswer(sessionId, currentQ.id, score);
    setTimeout(() => {
      if (currentIdx < questions.length - 1) {
        setCurrentIdx(currentIdx + 1);
      } else {
        // Last question — auto-submit with the just-updated answers. The answer
        // click IS the submit, so no extra "I'm Done" / "View My Results" tap
        // is needed (see Pulse UX cleanup).
        submitWithAnswers(updated);
      }
    }, 300);
  }, [currentQ, currentIdx, questions.length, savedAnswers, sessionId]);

  // Refactored to take the answers map explicitly — lets handleSelect pass the
  // post-click snapshot (savedAnswers in its closure is the pre-click value).
  const submitWithAnswers = async (answersMap: Record<string, number>) => {
    if (!sessionId) return;
    setSubmitting(true);
    const answers = Object.entries(answersMap).map(([qid, score]) => ({
      question_id: Number(qid),
      score,
    }));
    try {
      const result = await api.submitAnswers(sessionId, answers);
      window.localStorage.removeItem(`${ANSWERS_KEY}:${sessionId}`);
      router.push(`/results/${result.session_id}`);
    } catch (e) {
      console.error(e);
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-quedera-surface">
        <div className="text-quedera-cyan">Loading questions...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-quedera-surface p-4">
        <div className="rounded-xl border border-quedera-navy/10 bg-quedera-surface p-8 max-w-md w-full text-center shadow-sm">
          <div className="text-5xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold mb-2">
            <span className="text-pulse">Session Error</span>
          </h2>
          <p className="text-quedera-navy/70 mb-6">{error}</p>
          <button
            onClick={() => router.push("/")}
            className="btn-primary px-6 py-3 rounded-lg font-semibold"
          >
            Back to Start
          </button>
        </div>
      </div>
    );
  }

  // Loading screen — replaces the old "All Done + View My Results" flow.
  // Auto-submit on the last answer click handles the redirect; this screen is
  // purely the "Calculating…" interstitial while we wait for the API.
  if (submitting || done || (mounted && questions.length > 0 && answeredCount === questions.length && answeredCount > 0)) {
    return (
      <div className="min-h-screen bg-quedera-surface flex items-center justify-center p-4">
        <div className="rounded-xl border border-quedera-navy/10 bg-quedera-surface p-8 max-w-md w-full text-center shadow-sm">
          <div className="text-5xl mb-4">📊</div>
          <h2 className="text-2xl font-bold mb-2">
            <span className="text-pulse">All Done!</span>
          </h2>
          <p className="text-quedera-navy/70 mb-8">
            You&apos;ve answered all {questions.length} questions. Calculating your results…
          </p>
          <div className="flex items-center justify-center gap-2 text-quedera-cyan" aria-label="Loading">
            <div className="w-2 h-2 rounded-full bg-quedera-cyan animate-pulse" />
            <div className="w-2 h-2 rounded-full bg-quedera-cyan animate-pulse" style={{ animationDelay: "150ms" }} />
            <div className="w-2 h-2 rounded-full bg-quedera-cyan animate-pulse" style={{ animationDelay: "300ms" }} />
          </div>
        </div>
      </div>
    );
  }

  if (!currentQ) return null;

  const currentAnswer = savedAnswers[currentQ.id];

  return (
    <div className="min-h-screen bg-quedera-surface flex flex-col">
      {/* Header */}
      <header className="bg-header px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img src="/assets/pulse-icon.png" alt="QUEDERA Pulse" className="h-16 w-auto" />
        </div>
        <div className="text-sm text-quedera-navy/70">
          <span className="text-quedera-cyan font-semibold">{answeredCount}</span>
          <span className="text-quedera-navy/60"> / {questions.length}</span>
          <span className="text-quedera-navy/60 ml-1">answered</span>
        </div>
      </header>

      {/* Progress bar */}
      <div className="w-full h-1 bg-quedera-cyan/10">
        <div className="bg-progress h-1 transition-all duration-300" style={{ width: `${progress}%` }} />
      </div>

      {/* Question meta */}
      <div className="px-4 pt-6 pb-2 flex items-center gap-3 flex-wrap">
        <span className="inline-block bg-quedera-cyan/15 text-quedera-cyan text-xs font-semibold px-3 py-1 rounded-full uppercase tracking-wide">
          {currentQ.discipline}
        </span>
        <span className="text-quedera-navy/60 text-xs">{currentQ.area}</span>
        <span className="ml-auto text-xs text-quedera-navy/60">Q{currentIdx + 1}</span>
      </div>

      {/* Question and options */}
      <div className="px-4 py-4 flex-1">
        <div className="rounded-xl border border-quedera-navy/10 bg-quedera-surface p-6 mb-4 shadow-sm">
          <p className="text-lg font-medium text-quedera-navy leading-relaxed">{currentQ.question}</p>
        </div>

        <div className="space-y-2">
          {currentQ.options.map((opt) => (
            <button
              key={opt.score}
              onClick={() => handleSelect(opt.score)}
              className={`w-full text-left p-4 rounded-lg border-2 transition-all duration-150 ${
                currentAnswer === opt.score
                  ? "border-quedera-cyan bg-quedera-cyan/10"
                  : "border-quedera-navy/10 bg-quedera-surface hover:border-quedera-cyan/40 hover:bg-quedera-cyan/5"
              }`}
            >
              <div className="flex items-start gap-3">
                <span
                  className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                    currentAnswer === opt.score
                      ? "bg-quedera-cyan text-quedera-navy"
                      : "bg-quedera-cyan/15 text-quedera-cyan"
                  }`}
                >
                  {opt.score}
                </span>
                <span className="text-quedera-navy text-sm leading-relaxed">{opt.text}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Footer nav — Previous only. Answer click auto-advances; on the last
          question the click triggers submit, so neither a Next nor an
          "I'm Done" button is needed (Pulse UX cleanup). */}
      <div className="px-4 py-4 bg-header border-t border-quedera-navy/10 flex gap-3">
        <button
          disabled={currentIdx === 0}
          onClick={() => setCurrentIdx(Math.max(0, currentIdx - 1))}
          className="px-4 py-2 rounded-lg border border-quedera-navy/20 text-quedera-navy/70 text-sm disabled:opacity-30 hover:bg-quedera-cyan/5"
        >
          ← Previous
        </button>
      </div>
    </div>
  );
}