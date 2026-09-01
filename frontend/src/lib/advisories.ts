// ITSM Chronos — overall-level advisory content.
// Drives the advisory card on the results page (frontend/src/app/results/[id]/page.tsx).
// Keyed by achieved CMMI level (1–5). Plain TS so it's trivial to extract to a JSON
// config file later if we want copy edits without a code deploy (open as v2).
//
// Added for DEF-006. See:
//   defects/DEF-006-advisory-note-not-displayed.md
//   https://discord.com/channels/1478151399421251685/1520488180112036145

export interface LevelAdvisory {
  level: number;          // CMMI level 1–5
  label: string;          // maturity label (matches the pill in the score card)
  pct_min: number;        // inclusive lower bound of overall % for this level
  pct_max: number;        // exclusive upper bound (last level uses 1.01 to be inclusive at 100%)
  text: string;           // the advisory copy shown to the user
}

export const LEVEL_ADVISORIES: LevelAdvisory[] = [
  {
    level: 1,
    label: "Initial",
    pct_min: 0.0,
    pct_max: 0.4,
    text:
      "Service operations are largely reactive — success depends on individual heroics, not repeatable process. Establish a basic incident workflow (record, categorise, resolve, close) and a single source of truth for ongoing issues. Until every incident is captured, no further maturity is meaningful.",
  },
  {
    level: 2,
    label: "Managed",
    pct_min: 0.4,
    pct_max: 0.6,
    text:
      "Repeatable processes exist but vary by team. Pick one process (incident, request, or change), document its steps, owners, and exit criteria, and roll it out org-wide. That's the floor for everything above.",
  },
  {
    level: 3,
    label: "Defined",
    pct_min: 0.6,
    pct_max: 0.8,
    text:
      "Process is defined and consistently applied — you're at the industry baseline for ITSM. To move further, start measuring outcomes (resolution time, first-contact fix rate, change failure rate). You can't manage what you don't measure.",
  },
  {
    level: 4,
    label: "Quantitatively Managed",
    pct_min: 0.8,
    pct_max: 1.0,
    text:
      "You're using data to control service quality. Next: set statistical process-control limits on your key ITSM metrics and act on early-warning signals before they breach SLA.",
  },
  {
    level: 5,
    label: "Optimising",
    pct_min: 1.0,
    pct_max: 1.01,
    text:
      "Top of the maturity scale. Stay here by institutionalising continuous improvement: root-cause analysis on major incidents, deliberate process experimentation, and feeding lessons learned back into organisational standards.",
  },
];

/**
 * Returns the advisory whose [pct_min, pct_max) band contains the given overall %.
 * Pure function — safe to call from server components or tests.
 */
export function getOverallAdvisory(overallPct: number): LevelAdvisory {
  const clamped = Math.max(0, Math.min(1, overallPct));
  // Levels are ordered ascending; pick the last one whose pct_min <= clamped.
  let chosen: LevelAdvisory = LEVEL_ADVISORIES[0];
  for (const advisory of LEVEL_ADVISORIES) {
    if (clamped >= advisory.pct_min) {
      chosen = advisory;
    } else {
      break;
    }
  }
  return chosen;
}
