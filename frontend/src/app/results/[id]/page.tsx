"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, Session, DisciplineResult } from "@/lib/api";
import { cmmiLevel, maturityLabel, overallPct } from "@/lib/cmmi";
import { getOverallAdvisory } from "@/lib/advisories";

export default function ResultsPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = (params?.id as string) ?? "";

  const [session, setSession] = useState<Session | null>(null);
  const [results, setResults] = useState<DisciplineResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<"pdf" | "xlsx" | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    Promise.all([api.getSession(sessionId), api.getResults(sessionId)])
      .then(([sess, res]) => {
        setSession(sess);
        setResults(res.results);
      })
      .catch((e) => {
        console.error(e);
        setError(e.message || "Failed to load results");
      })
      .finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-quedera-surface">
        <div className="text-quedera-cyan">Loading results...</div>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-quedera-surface p-4">
        <div className="rounded-xl border border-quedera-navy/10 bg-quedera-surface p-8 max-w-md w-full text-center shadow-sm">
          <div className="text-5xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold mb-2">
            <span className="text-pulse">Results Not Found</span>
          </h2>
          <p className="text-quedera-navy/70 mb-6">{error || "Session not found."}</p>
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

  const isFullScope = session.scope === "full";
  const overallPctValue = results.length > 0 ? overallPct(results) : 0;
  const overallLevel = cmmiLevel(overallPctValue);
  const advisory = getOverallAdvisory(overallPctValue);
  const overallMat = maturityLabel(overallPctValue);
  const assessedNames = results.map((r) => r.discipline).join(" · ");

  return (
    <main className="min-h-screen flex flex-col">
      <header className="bg-header px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img src="/assets/pulse-icon.png" alt="QUEDERA Pulse" className="h-20 w-auto" />
          <span className="text-xs font-medium text-quedera-cyan uppercase tracking-widest ml-2">Results</span>
        </div>
      </header>

      <section className="flex-1 px-6 py-8 max-w-4xl mx-auto w-full">
        {/* Scope banner */}
        <div className="rounded-xl border border-quedera-navy/10 bg-quedera-surface p-5 mb-6 shadow-sm">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-xl">
              {isFullScope ? "📊" : session.scope === "single" ? "🎯" : "🔗"}
            </span>
            <h2 className="text-lg font-semibold text-quedera-navy">
              {isFullScope ? "Full Assessment" :
               session.scope === "single" ? "Single Discipline" :
               "Multiple Disciplines"}
              <span className="text-quedera-cyan ml-2">
                · {results.length} of 28 {results.length === 1 ? "discipline" : "disciplines"}
              </span>
            </h2>
          </div>
          {assessedNames && (
            <p className="text-xs text-quedera-navy/60">
              {isFullScope ? "All 28 disciplines were assessed." : `Assessed: ${assessedNames}`}
            </p>
          )}
        </div>

        {/* Overall / Scope average score card */}
        <div className="rounded-xl border border-quedera-navy/10 bg-quedera-surface p-6 mb-6 shadow-sm">
          <div className="flex items-baseline justify-between mb-2">
            <h3 className="text-sm uppercase tracking-widest text-quedera-navy/60">
              {isFullScope ? "Overall Maturity" : "Scope Average"}
            </h3>
            <span className={`text-xs uppercase tracking-widest font-semibold ${overallMat.color}`}>
              L{overallLevel} · {advisory.label}
            </span>
          </div>
          <div className="flex items-baseline gap-3">
            <span className="text-5xl font-black text-quedera-cyan">
              {Math.round(overallPctValue * 100)}%
            </span>
            {!isFullScope && (
              <span className="text-sm text-quedera-navy/60">
                (based on {results.length} {results.length === 1 ? "discipline" : "disciplines"})
              </span>
            )}
          </div>
          {!isFullScope && (
            <p className="text-xs text-quedera-navy/60 mt-3 italic">
              Partial scope — overall L1–L5 claim is per-discipline only. Top-line is a scope average.
            </p>
          )}
        </div>

        {/* Advisory */}
        <div className="rounded-xl border border-quedera-navy/10 bg-quedera-surface p-6 mb-6 shadow-sm">
          <h3 className="text-sm uppercase tracking-widest text-quedera-navy/60 mb-3">Advisory</h3>
          <p className="text-sm text-quedera-navy leading-relaxed">{advisory.text}</p>
        </div>

        {/* Per-discipline breakdown */}
        <div className="rounded-xl border border-quedera-navy/10 bg-quedera-surface p-6 mb-6 shadow-sm">
          <h3 className="text-sm uppercase tracking-widest text-quedera-navy/60 mb-4">Per-Discipline Breakdown</h3>
          {results.length === 0 ? (
            <p className="text-sm text-quedera-navy/60">No results recorded for this session yet.</p>
          ) : (
            <div className="space-y-2">
              {results.map((r) => {
                const pct = r.pct_cmmi;
                const level = cmmiLevel(pct);
                const mat = maturityLabel(pct);
                return (
                  <div key={r.discipline} className="flex items-center gap-3 p-3 rounded-lg bg-quedera-cyan/5">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm text-quedera-navy">{r.discipline}</span>
                        <span className={`text-xs font-semibold ${mat.color}`}>
                          L{level} · {mat.label}
                        </span>
                      </div>
                      <div className="w-full h-1 bg-quedera-cyan/10 rounded-full mt-2">
                        <div
                          className="h-1 bg-quedera-cyan rounded-full transition-all"
                          style={{ width: `${pct * 100}%` }}
                        />
                      </div>
                    </div>
                    <span className="text-sm font-semibold text-quedera-cyan w-14 text-right">
                      {Math.round(pct * 100)}%
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Export buttons */}
        <div className="rounded-xl border border-quedera-navy/10 bg-quedera-surface p-6">
          <h3 className="text-sm uppercase tracking-widest text-quedera-navy/60 mb-4">Export</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <button
              onClick={async () => {
                setExporting("pdf");
                try {
                  await api.exportPDF(sessionId);
                } catch (e: any) {
                  alert(`PDF export failed: ${e.message}`);
                } finally {
                  setExporting(null);
                }
              }}
              disabled={exporting !== null}
              className="btn-primary py-3 rounded-lg font-semibold disabled:opacity-50"
            >
              {exporting === "pdf" ? "Generating PDF..." : "📄 Download PDF (summary)"}
            </button>
            <button
              onClick={async () => {
                setExporting("xlsx");
                try {
                  await api.exportXLSX(sessionId);
                } catch (e: any) {
                  alert(`XLSX export failed: ${e.message}`);
                } finally {
                  setExporting(null);
                }
              }}
              disabled={exporting !== null}
              className="btn-primary py-3 rounded-lg font-semibold disabled:opacity-50"
            >
              {exporting === "xlsx" ? "Generating XLSX..." : "📊 Download XLSX (full answers)"}
            </button>
          </div>
          <p className="text-xs text-quedera-navy/60 mt-3">
            PDF is a results-only summary. XLSX contains one sheet per assessed discipline with all answers.
          </p>
        </div>

        <div className="text-center mt-8">
          <button
            onClick={() => router.push("/")}
            className="text-sm text-quedera-cyan hover:underline"
          >
            ← Start a new assessment
          </button>
        </div>
      </section>

      <footer className="text-center py-6 text-xs text-quedera-navy/60 border-t border-quedera-navy/10">
        © 2026 QUEDERA · Pulse.
      </footer>
    </main>
  );
}