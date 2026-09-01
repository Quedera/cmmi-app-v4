"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, Discipline, SessionScope } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [disciplines, setDisciplines] = useState<Discipline[]>([]);
  const [scope, setScope] = useState<SessionScope>("full");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getDisciplines()
      .then(setDisciplines)
      .catch((e) => {
        console.error(e);
        setError("Could not load disciplines. Is the backend running?");
      })
      .finally(() => setLoading(false));
  }, []);

  const toggleDiscipline = (id: number) => {
    if (scope === "single") {
      setSelected(new Set([id]));
    } else if (scope === "multi") {
      const next = new Set(selected);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      setSelected(next);
    }
  };

  const canStart = () => {
    if (scope === "full") return true;
    if (scope === "single") return selected.size === 1;
    if (scope === "multi") return selected.size >= 2 && selected.size <= 28;
    return false;
  };

  const handleStart = async () => {
    if (!canStart()) return;
    setSubmitting(true);
    setError(null);
    try {
      const payload = scope === "full"
        ? { scope: "full" as SessionScope }
        : { scope, selected_disciplines: Array.from(selected).sort((a, b) => a - b) };
      const session = await api.createSession(payload);
      router.push(`/assess/${session.session_id}`);
    } catch (e: any) {
      setError(e.message || "Failed to start assessment");
      setSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-header px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img src="/assets/pulse-icon.png" alt="QUEDERA Pulse" className="h-20 w-auto" />
          <span className="text-xs font-medium text-quedera-cyan uppercase tracking-widest ml-2">Assessment</span>
        </div>
      </header>

      {/* Hero */}
      <section
        className="flex-1 flex flex-col items-center justify-center px-6 py-12"
        style={{
          background:
            'radial-gradient(ellipse 60% 40% at 50% 0%, rgba(6, 182, 212, 0.10) 0%, transparent 70%)',
        }}
      >
        <h1 className="text-4xl md:text-5xl font-black mb-6 text-center">
          <span className="text-pulse">ITSM Maturity Assessment</span>
        </h1>

        {loading ? (
          <div className="text-quedera-navy/60 py-8">Loading disciplines...</div>
        ) : (
          <div className="w-full max-w-3xl">
            {/* Scope picker */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <ScopeCard
                title="Full Assessment"
                description="All 28 disciplines, 622 questions"
                selected={scope === "full"}
                onClick={() => { setScope("full"); setSelected(new Set()); }}
                emoji="📊"
              />
              <ScopeCard
                title="Single Discipline"
                description="Focus on one discipline"
                selected={scope === "single"}
                onClick={() => { setScope("single"); setSelected(new Set()); }}
                emoji="🎯"
              />
              <ScopeCard
                title="Multiple Disciplines"
                description="Pick 2-28 disciplines"
                selected={scope === "multi"}
                onClick={() => { setScope("multi"); setSelected(new Set()); }}
                emoji="🔗"
              />
            </div>

            {/* Discipline selector for single/multi */}
            {scope !== "full" && (
              <div className="rounded-xl border border-quedera-navy/10 bg-quedera-surface p-6 mb-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-quedera-navy">
                    {scope === "single"
                      ? "Pick a discipline"
                      : `Selected disciplines (${selected.size}/28)`}
                  </h2>
                  {scope === "multi" && (
                    <div className="flex gap-3">
                      <button
                        onClick={() => setSelected(new Set(disciplines.map((d) => d.id)))}
                        className="text-xs text-quedera-cyan hover:underline"
                      >Select all</button>
                      <button
                        onClick={() => setSelected(new Set())}
                        className="text-xs text-quedera-cyan hover:underline"
                      >Clear</button>
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-96 overflow-y-auto pr-2">
                  {disciplines.map((d) => {
                    const isSelected = selected.has(d.id);
                    return (
                      <button
                        key={d.id}
                        onClick={() => toggleDiscipline(d.id)}
                        className={`text-left p-3 rounded-lg border-2 transition-all ${
                          isSelected
                            ? "border-quedera-cyan bg-quedera-cyan/10"
                            : "border-quedera-navy/10 bg-quedera-surface hover:border-quedera-cyan/40"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className={`flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center ${
                              isSelected
                                ? "bg-quedera-cyan border-quedera-cyan"
                                : "border-quedera-navy/30 bg-quedera-surface"
                            }`}
                          >
                            {isSelected && (
                              <svg
                                className="w-3 h-3 text-quedera-navy"
                                fill="currentColor"
                                viewBox="0 0 20 20"
                              >
                                <path
                                  fillRule="evenodd"
                                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                  clipRule="evenodd"
                                />
                              </svg>
                            )}
                          </span>
                          <span className="text-sm text-quedera-navy">{d.name}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
                {scope === "single" && selected.size === 0 && (
                  <p className="text-xs text-quedera-navy/60 mt-2">Pick 1 discipline to continue.</p>
                )}
                {scope === "multi" && selected.size < 2 && (
                  <p className="text-xs text-quedera-navy/60 mt-2">Pick at least 2 disciplines (max 28).</p>
                )}
              </div>
            )}

            {error && (
              <div className="mb-4 p-3 bg-quedera-amber/10 border border-quedera-amber/40 rounded-lg text-quedera-amber text-sm">
                {error}
              </div>
            )}

            <button
              onClick={handleStart}
              disabled={!canStart() || submitting}
              className="w-full btn-primary py-4 rounded-lg font-bold text-lg"
            >
              {submitting ? "Starting..." : "Start Assessment →"}
            </button>
          </div>
        )}
      </section>

      {/* Footer */}
      <footer className="text-center py-6 text-xs text-quedera-navy/60 border-t border-quedera-navy/10">
        © 2026 QUEDERA · Pulse.
      </footer>
    </main>
  );
}

function ScopeCard({
  title,
  description,
  selected,
  onClick,
  emoji,
}: {
  title: string;
  description: string;
  selected: boolean;
  onClick: () => void;
  emoji: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`text-left p-5 rounded-xl border-2 transition-all ${
        selected
          ? "border-quedera-cyan bg-quedera-cyan/10"
          : "border-quedera-navy/10 bg-quedera-surface hover:border-quedera-cyan/40"
      }`}
    >
      <div className="text-2xl mb-2">{emoji}</div>
      <div className="text-lg font-semibold text-quedera-navy mb-1">{title}</div>
      <div className="text-sm text-quedera-navy/60">{description}</div>
    </button>
  );
}