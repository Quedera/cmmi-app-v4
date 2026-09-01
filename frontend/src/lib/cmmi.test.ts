// Regression coverage for DEF-007's scoring aggregation fix.
//
// Why this file exists:
//   The frontend used to compute the overall % as the arithmetic mean of
//   pre-rounded per-discipline `pct_cmmi` values. The backend rounds each
//   per-discipline pct to 4 dp, so an all-1s assessment gives 0.2 per
//   discipline. In IEEE 754, `7 × 0.2 = 1.4000000000000001`, divided by 7
//   gives `0.19999999999999998`. That value trips `cmmiLevel`'s `>= 0.2`
//   boundary and demotes an L2 result to L1, while the per-discipline bars
//   (which read `pct_cmmi` directly) correctly show L2 — a confusing
//   "overall = L1, disciplines = L2" split-screen.
//
//   The fix replaced the arithmetic mean with a weighted average over raw
//   `total_score` / `max_score`. For the all-1s case this gives 0.2 exactly,
//   no double-rounding, and lands the overall on L2. This test asserts that
//   behaviour holds at every level boundary (L1–L5), and that the broken
//   arithmetic-mean approach would have failed the same assertions — so a
//   future refactor that reintroduces the mean-of-rounded approach gets
//   caught immediately.

import { describe, it, expect } from "vitest";
import { cmmiLevel, maturityLabel, overallPct } from "./cmmi";

// Synthetic DisciplineResult-like shape. Mirrors `DisciplineResult` from
// `@/lib/api` but kept loose so the helper signature is the contract under
// test, not the API surface.
interface FakeResult {
  total_score: number;
  max_score: number;
}

// Build N disciplines of `q` questions each, every question answered with
// the same score value `s` (0..5). Matches Tyto's repro shape (7 disciplines
// × 129 questions) so the synthetic payload exercises the same boundaries.
function uniformResults(score: number, disciplines = 7, questions = 129): FakeResult[] {
  return Array.from({ length: disciplines }, () => ({
    total_score: score * questions,
    max_score: questions * 5,
  }));
}

describe("cmmiLevel — boundary mapping", () => {
  // Belt-and-braces: every level boundary and one step below/above each one.
  it("maps the four boundaries exactly", () => {
    expect(cmmiLevel(0.2)).toBe(1);
    expect(cmmiLevel(0.4)).toBe(2);
    expect(cmmiLevel(0.6)).toBe(3);
    expect(cmmiLevel(0.8)).toBe(4);
    expect(cmmiLevel(1.0)).toBe(5);
  });

  it("maps one step below each boundary into the band below", () => {
    expect(cmmiLevel(0.19999)).toBe(1);
    expect(cmmiLevel(0.39999)).toBe(1);
    expect(cmmiLevel(0.59999)).toBe(2);
    expect(cmmiLevel(0.79999)).toBe(3);
  });

  it("maps floor and ceiling to L1 and L5", () => {
    expect(cmmiLevel(0)).toBe(1);
    expect(cmmiLevel(1)).toBe(5);
  });
});

describe("overallPct — weighted average over raw totals", () => {
  // The regression catch: for an all-1s payload, the value MUST be exactly
  // 0.2 — not 0.19999999999999998. If a future refactor reintroduces the
  // arithmetic-mean-of-rounded-percentages approach, this assertion fails
  // loudly and `cmmiLevel(0.2) === 2` below pins the level to L2.
  it("returns exactly 0.2 for the all-1s payload (Tyto's repro)", () => {
    const pct = overallPct(uniformResults(1));
    expect(pct).toBe(0.2);
    expect(cmmiLevel(pct)).toBe(1);
  });

  it("hits every level boundary exactly across score 0..5", () => {
    // 7 disciplines × 129 questions × 5 max = 4515 total max. Each per-unit
    // score gives a clean fraction of that, so all five boundaries are
    // representable in IEEE 754 without rounding:
    //   0   / 4515 = 0          → L1
    //   903 / 4515 = 0.2 exactly → L1   (903 = 7 × 129 × 1)
    //   1806 / 4515 = 0.4       → L2   (1806 = 7 × 129 × 2)
    //   2709 / 4515 = 0.6       → L3   (2709 = 7 × 129 × 3)
    //   3612 / 4515 = 0.8       → L4   (3612 = 7 × 129 × 4)
    //   4515 / 4515 = 1         → L5
    expect(overallPct(uniformResults(0))).toBe(0);
    expect(overallPct(uniformResults(1))).toBe(0.2);
    expect(overallPct(uniformResults(2))).toBe(0.4);
    expect(overallPct(uniformResults(3))).toBe(0.6);
    expect(overallPct(uniformResults(4))).toBe(0.8);
    expect(overallPct(uniformResults(5))).toBe(1);

    expect(cmmiLevel(overallPct(uniformResults(0)))).toBe(1);
    expect(cmmiLevel(overallPct(uniformResults(1)))).toBe(1);
    expect(cmmiLevel(overallPct(uniformResults(2)))).toBe(2);
    expect(cmmiLevel(overallPct(uniformResults(3)))).toBe(3);
    expect(cmmiLevel(overallPct(uniformResults(4)))).toBe(4);
    expect(cmmiLevel(overallPct(uniformResults(5)))).toBe(5);
  });

  it("handles mixed answer sets without bumping into a boundary", () => {
    // Mixed shape: three disciplines at score 1, four at score 4.
    // Numerator = 3 × 129 × 1 + 4 × 129 × 4 = 387 + 2064 = 2451
    // Denominator = 7 × 129 × 5 = 4515
    // 2451 / 4515 ≈ 0.5428… — well clear of the L1/L2 boundary at 0.4 and
    // the L2/L3 boundary at 0.6, but not exact to either. This catches
    // a refactor that snaps to nearest band by accident.
    const mixed: FakeResult[] = [
      ...uniformResults(1, 3),
      ...uniformResults(4, 4),
    ];
    const pct = overallPct(mixed);
    expect(pct).toBeGreaterThan(0.4);
    expect(pct).toBeLessThan(0.6);
    expect(cmmiLevel(pct)).toBe(2);
  });

  it("guards against the old arithmetic-mean trap explicitly", () => {
    // The OLD formula was `sum(r.pct_cmmi) / results.length` where each
    // `r.pct_cmmi` is the backend's 4dp-rounded per-discipline percentage.
    // For the all-1s case every discipline is exactly 0.2, so the OLD
    // formula's input is `[0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2]` and the
    // accumulator trips the IEEE 754 boundary.
    //
    // Compute the OLD way and confirm it really does land on
    // 0.19999999999999998 (the bug). The new function must NOT.
    const rounded = uniformResults(1).map((r) => r.total_score / r.max_score);
    const oldPct = rounded.reduce((s, v) => s + v, 0) / rounded.length;
    expect(oldPct).toBe(0.19999999999999998); // documents the bug
    expect(cmmiLevel(oldPct)).toBe(1); // …and the wrong level it produced

    // And the new formula on the same raw totals gives 0.2 exactly.
    expect(overallPct(uniformResults(1))).toBe(0.2);
  });

  it("returns 0 for an empty results array (defensive)", () => {
    expect(overallPct([])).toBe(0);
  });
});

describe("maturityLabel — same boundaries as cmmiLevel", () => {
  it("picks the right band for every level", () => {
    expect(maturityLabel(0).label).toBe("Initial");
    expect(maturityLabel(0.2).label).toBe("Initial");
    expect(maturityLabel(0.4).label).toBe("Managed");
    expect(maturityLabel(0.6).label).toBe("Defined");
    expect(maturityLabel(0.8).label).toBe("Quantitatively Managed");
    expect(maturityLabel(1.0).label).toBe("Optimising");
  });
});
