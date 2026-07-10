# Phase 6: Harder Evidence Bar — Multiple-Comparisons Correction & Walk-Forward Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-10
**Phase:** 6-Harder Evidence Bar — Multiple-Comparisons Correction & Walk-Forward Validation
**Areas discussed:** Significance test / null hypothesis, Correction scope & stage, Walk-forward vs. sacred OOS, Walk-forward window scheme & pass bar

---

## Significance Test / Null Hypothesis

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed 50% (coin-flip) | One-sample test H0: rate = 0.5; matches existing "same side of 50%" framing everywhere in the codebase; no new "parent rate" concept | ✓ |
| Bucket's own parent/baseline rate | Two-proportion test vs. the unconditioned parent bucket rate; more rigorous but introduces a new concept not present in the manifest today | |

**User's choice:** Fixed 50% (coin-flip)
**Notes:** Consistent with the fact that no p-value/hypothesis test exists anywhere in the current harness — `determine_verdict()` only checks the point estimate's side of 50%.

---

## Correction Scope & Stage

**Scope sub-question:**

| Option | Description | Selected |
|--------|-------------|----------|
| One global family (everything) | Every bucket across every analysis × TF × instrument × direction in a single BH pass | ✓ |
| Grouped per analysis key | Separate BH correction per analysis key | |

**Stage sub-question:**

| Option | Description | Selected |
|--------|-------------|----------|
| Discovery manifest (pre-OOS gate) | Corrects the discovery-slice manifest only, before the sacred OOS look | ✓ |
| Final reconciled findings table | Corrects the merged discovery+OOS table | |
| Both discovery and OOS manifests separately | Independent BH pass per slice | |

**User's choice:** One global family, corrected at the discovery-manifest stage only.
**Notes:** Matches roadmap wording ("across the full bucket grid") and `build_discovery_summary.py`'s existing go/no-go-before-OOS purpose.

---

## Walk-Forward vs. the Sacred OOS Slice

| Option | Description | Selected |
|--------|-------------|----------|
| Confined to discovery slice only | Walk-forward windows carved entirely from pre-OOS_START history; OOS slice untouched | ✓ |
| Spans full history (discovery + OOS) | Walk-forward rolls through the entire dataset including OOS-region bars | |

**User's choice:** Confined to discovery slice only.
**Notes:** Preserves the project's sacred-OOS invariant (the literal `_OOS_BANNER` warning) — walk-forward never spends an additional "look" at the OOS region.

---

## Walk-Forward Window Scheme & Pass Bar

**Window construction sub-question:**

| Option | Description | Selected |
|--------|-------------|----------|
| Expanding (anchored) window | Each fold trains on all discovery data from the start through the fold boundary | ✓ |
| Rolling (fixed-size) window | Each fold trains on a fixed trailing window that slides forward | |

**Fold count / boundary sub-question:**

| Option | Description | Selected |
|--------|-------------|----------|
| 4-5 folds, calendar-date boundaries | Fixed boundary dates (frozen constants, like OOS_START), same across all timeframes | ✓ |
| 4-5 folds, equal bar-count boundaries | Equal row-count chunks per timeframe independently | |

**Pass-bar sub-question:**

| Option | Description | Selected |
|--------|-------------|----------|
| All folds pass (unanimous) | Every test fold must pass | |
| Majority of folds pass (>50%) | More than half of test folds must pass | ✓ |

**User's choice:** Expanding window; 4-5 folds with fixed calendar-date boundaries; majority-pass aggregate bar.
**Notes:** Calendar-date boundaries follow the existing `OOS_START` precedent (frozen percentile-of-calendar date) so all four timeframes slice on the same real-world dates despite very different bar density.

---

## Claude's Discretion

- Exact test statistic implementation (normal approximation z-test vs. exact binomial test) — pure Python, no new dependencies.
- Exact calendar boundary dates for the 4-5 walk-forward folds (to be derived and frozen, following the `OOS_START` precedent).
- Whether per-fold results land as new manifest columns or a new sibling artifact.
- Whether `MIN_N` gates individual walk-forward folds or only the aggregate verdict.

## Deferred Ideas

None — discussion stayed within phase scope.
