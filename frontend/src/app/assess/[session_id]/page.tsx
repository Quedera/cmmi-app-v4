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
      if (currentIdx < questions.length - 1) setCurrentIdx(currentIdx + 1);
    }, 300);
  }, [currentQ, currentIdx, questions.length, savedAnswers, sessionId]);

  const handleSubmit = async () => {
    if (!sessionId) return;
    setSubmitting(true);
    const answers = Object.entries(savedAnswers).map(([qid, score]) => ({
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

  // Show done screen only when all questions answered
  if (done || (mounted && questions.length > 0 && answeredCount === questions.length && answeredCount > 0)) {
    return (
      <div className="min-h-screen bg-quedera-surface flex items-center justify-center p-4">
        <div className="rounded-xl border border-quedera-navy/10 bg-quedera-surface p-8 max-w-md w-full text-center shadow-sm">
          <div className="text-5xl mb-4">📊</div>
          <h2 className="text-2xl font-bold mb-2">
            <span className="text-pulse">All Done!</span>
          </h2>
          <p className="text-quedera-navy/70 mb-8">
            You&apos;ve answered {answeredCount} of {questions.length} questions.
            Ready to see your results?
          </p>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="w-full btn-primary py-4 rounded-lg font-semibold text-lg disabled:opacity-50"
          >
            {submitting ? "Calculating..." : "View My Results →"}
          </button>
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

      {/* Footer nav */}
      <div className="px-4 py-4 bg-header border-t border-quedera-navy/10 flex gap-3">
        <button
          disabled={currentIdx === 0}
          onClick={() => setCurrentIdx(Math.max(0, currentIdx - 1))}
          className="px-4 py-2 rounded-lg border border-quedera-navy/20 text-quedera-navy/70 text-sm disabled:opacity-30 hover:bg-quedera-cyan/5"
        >
          ← Previous
        </button>

        {currentIdx < questions.length - 1 ? (
          <button
            onClick={() => setCurrentIdx(currentIdx + 1)}
            className="flex-1 btn-primary py-2 rounded-lg text-sm font-medium"
          >
            Next →
          </button>
        ) : (
          <button
            onClick={() => setDone(true)}
            className="flex-1 bg-quedera-cyan text-quedera-navy py-2 rounded-lg text-sm font-medium hover:bg-quedera-cyan/90"
          >
            I&apos;m Done — Show Results
          </button>
        )}
      </div>
    </div>
  );
}