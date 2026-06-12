# Phase 3: Re-Validate & Republish Existing Findings - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-12
**Phase:** 3-Re-Validate & Republish Existing Findings
**Areas discussed:** Survival criterion, README rate display, OOS workflow automation

---

## Survival criterion

### Q1: OOS eligibility gate

| Option | Description | Selected |
|--------|-------------|----------|
| n ≥ 50 only | Any n≥50 finding goes to OOS regardless of CI_low | ✓ |
| n ≥ 50 AND CI_low > 0.50 | Must be statistically above chance on discovery slice | |
| n ≥ 50 AND CI_low > 0.55 | Stricter: meaningful edge, not just above-chance noise | |

**User's choice:** n ≥ 50 only
**Notes:** Keeps the survival rule simple and locked. CI is informational, not a gate.

### Q2: Label for OOS failures

| Option | Description | Selected |
|--------|-------------|----------|
| ✗ NOT CONFIRMED | Clear failure badge; discovery + OOS rates shown; verdict explicit | ✓ |
| Below threshold / inconclusive | Softer label for ambiguous cases | |
| Retired (removed from headline tables) | Pull from tables, add "Retired Findings" section | |

**User's choice:** ✗ NOT CONFIRMED
**Notes:** Consistent with project ethos: honest and explicit.

### Q3: OOS confirmation bar

| Option | Description | Selected |
|--------|-------------|----------|
| OOS rate matches direction | OOS rate just needs to be on same side as discovery rate | ✓ |
| OOS CI_low > 0.50 | OOS confidence interval must also clear chance | |
| You decide | Leave OOS confirmation threshold to Claude's discretion | |

**User's choice:** OOS rate matches direction
**Notes:** OOS n is ~30% of discovery n — a CI gate would kill real edges from lower OOS power.

---

## README rate display

### Q1: What numbers appear in republished README tables?

| Option | Description | Selected |
|--------|-------------|----------|
| Discovery-slice rates replace full-history | Clean break — everything goes through the harness | ✓ |
| Full-history rates kept, IS/OOS status added | Keep existing %, add badge | |
| Both side-by-side | Full-history and discovery-slice shown together | |

**User's choice:** Discovery-slice rates replace full-history
**Notes:** Clean break — after Phase 3, every README number comes from the harness.

### Q2: Stale WR-04 numbers (§8 SMT table + §3 wrong label)

| Option | Description | Selected |
|--------|-------------|----------|
| Fix inline — regenerate from live output first | Run cisd_analysis.py, correct stale §8 table + wrong label, then re-validate | ✓ |
| Treat stale numbers as the hypothesis | Re-validate as-is; harness produces correct discovery numbers regardless | |
| You decide | Leave to Claude's discretion during planning | |

**User's choice:** Fix inline — regenerate from live output first
**Notes:** Plan 03-01 handles WR-04 as a prerequisite step before running the harness.

### Q3: Presentation of below-n buckets in README

| Option | Description | Selected |
|--------|-------------|----------|
| Show rate + n + CI + "below-n / not a finding" badge | Visible but flagged; consistent with Phase 2 D-09 | ✓ |
| Omit from headline tables entirely | Only n≥50 findings appear; below-n in manifest CSV only | |
| You decide | Leave presentation to Claude's discretion | |

**User's choice:** Show rate + n + CI + "below-n / not a finding" badge
**Notes:** Consistent with Phase 2 D-09 — never silently drop; watch as n grows.

---

## OOS workflow automation

### Q1: How does 03-01 handle the discovery → OOS sequence?

| Option | Description | Selected |
|--------|-------------|----------|
| Human-gated two-step | Discovery → researcher reviews summary → manual --oos trigger | ✓ |
| Single comparison script | Discovery → automatic OOS if survivors exist, outputs labeled table | |

**User's choice:** Human-gated two-step
**Notes:** Preserves the sacred-evaluation ceremony and audit trail.

### Q2: Artifact bridging discovery run and OOS review

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-generated discovery summary report | Clean formatted table: rate, n, CI, OOS eligible Y/N per finding | ✓ |
| Raw manifest CSV only | Point at manifest; researcher filters themselves | |

**User's choice:** Auto-generated discovery summary report
**Notes:** Formatted for quick go/no-go review without opening Excel.

### Q3: Reconciler script scope

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — include reconciler in 03-01 | IS + OOS → labeled validation_findings.csv; 03-02 reads this | ✓ |
| No — 03-02 reads both manifests directly | Keep 03-01 focused on running slices; 03-02 reconciles | |

**User's choice:** Yes — include reconciler in 03-01
**Notes:** Clean plan boundary: 03-01 delivers all the data machinery; 03-02 is purely README authoring.

---

## Claude's Discretion

- Exact format of the discovery summary report (CLI output vs Markdown file)
- Whether `validation_findings.csv` goes in `output/` or `.planning/` (convention: `output/`)
- Exact README table layout for CI + badge columns (must include rate, n, CI range, verdict badge)
- Handling of analyses with zero n≥50 buckets on discovery slice

## Deferred Ideas

- Visual CI annotation (CI whiskers / shading on PNG charts) — deferred from Phase 2; still not in scope here
- Multiple-comparisons correction (BH, Bonferroni, White's Reality Check) — v2
- Walk-forward validation — v2
