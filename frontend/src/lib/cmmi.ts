// Pure helpers for the results page. Kept dependency-free so they can be
// unit-tested without pulling in React or Next.js.
//
// Brand palette: branding/quedera-palette.json
// RULE: palette codes only — no off-palette colours. Per-level colours
// below use only the seven QUEDERA tokens (cyan/amber/violet/navy + opacity).
// — MacWood, 2026-08-26 21:10 BST, #branding.

export interface MaturityInfo {
  label: string;
  color: string;
  bg: string;
}

/**
 * Map an overall percentage (0..1) to one of the five CMMI maturity levels.
 *
 * Boundaries are exact: `>= 1.0` → L5, `>= 0.8` → L4, `>= 0.6` → L3, `>= 0.4` → L2,
 * `>= 0.2` → L1, else L1 floor. The mapping is "answer-option-K = level-K" —
 * an all-3s assessment (pct 0.6) lands on L3 (Defined), not L4.
 *
 * Callers must feed this a value derived from raw integer totals, NOT an
 * arithmetic mean of pre-rounded per-discipline percentages — see DEF-007 for
 * why: `7 × 0.2 = 1.4000000000000001`, divided by 7 = `0.19999999999999998`,
 * which would fail the `>= 0.2` boundary and silently demote to the L1 floor.
 */
export function cmmiLevel(pct: number): number {
  if (pct >= 1.0) return 5;
  if (pct >= 0.8) return 4;
  if (pct >= 0.6) return 3;
  if (pct >= 0.4) return 2;
  if (pct >= 0.2) return 1;
  return 1;
}

/**
 * Human label + palette-only colour tokens for a given overall percentage.
 *
 * Mapping (best → worst):
 *   L5 Optimising          → text-quedera-cyan (Pulse product brand)
 *   L4 Quantitatively Mgd  → text-quedera-cyan/80
 *   L3 Defined             → text-quedera-amber (BEACON product brand)
 *   L2 Managed             → text-quedera-violet/80 (DUET product brand)
 *   L1 Initial             → text-quedera-navy/60 (muted)
 *
 * Backgrounds use the same tokens at low opacity for subtle chips.
 */
export function maturityLabel(pct: number): MaturityInfo {
  if (pct >= 1.0) return { label: "Optimising",            color: "text-quedera-cyan",       bg: "bg-quedera-cyan/10" };
  if (pct >= 0.8) return { label: "Quantitatively Managed", color: "text-quedera-cyan/80",    bg: "bg-quedera-cyan/10" };
  if (pct >= 0.6) return { label: "Defined",               color: "text-quedera-amber",      bg: "bg-quedera-amber/10" };
  if (pct >= 0.4) return { label: "Managed",               color: "text-quedera-violet/80",  bg: "bg-quedera-violet/10" };
  return            { label: "Initial",                color: "text-quedera-navy/60",     bg: "bg-quedera-navy/5" };
}

/**
 * Compute the overall % for the results page.
 *
 * This is a *weighted* average over raw `total_score` / `max_score`, not the
 * arithmetic mean of pre-rounded per-discipline percentages. See DEF-007 for
 * why the latter is broken: per-discipline `pct_cmmi` is rounded to 4 dp on
 * the backend (e.g. 0.2 for an all-1s assessment), and `7 × 0.2 ≠ 1.4` in IEEE
 * 754 — the accumulated rounding error trips `cmmiLevel`'s `>= 0.2` boundary
 * and demotes boundary-case rollups by one level. Computing over raw totals
 * gives 0.2 exactly for an all-1s payload, matches every per-discipline bar,
 * and the advisory card keys off the correct level.
 */
export function overallPct(
  results: ReadonlyArray<{ total_score: number; max_score: number }>,
): number {
  const totalScore = results.reduce((sum, r) => sum + r.total_score, 0);
  const maxScore = results.reduce((sum, r) => sum + r.max_score, 0);
  if (maxScore <= 0) return 0;
  return totalScore / maxScore;
}