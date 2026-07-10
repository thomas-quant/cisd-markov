# Phase 2: Validation Harness - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-12
**Phase:** 2-Validation Harness
**Areas discussed:** Holdout boundary pinning, Sacredness enforcement, CI method + n-gating, Coverage + default reconciliation

---

## Holdout boundary pinning

| Option | Description | Selected |
|--------|-------------|----------|
| Frozen committed date | Compute the 70th-pct boundary once from the snapshot, hardcode as a constant. Bit-stable; appending data won't silently shift the holdout. | ✓ |
| Runtime 70th-percentile | Recompute the boundary each run from present dates. Self-adjusting but the holdout moves underneath you. | |

**User's choice:** Frozen committed date.
**Notes:** Split ratio (70/30) and discovery-on-train default were already locked in PROJECT.md and not re-asked. Actual `OOS_START` value to be computed from the shared NQ∩ES calendar during planning/execution.

---

## Sacredness enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Soft: `--oos` flag + warning | Default discovery-only; explicit `--oos` flag + loud "spending your one sacred evaluation" banner; optional manifest log; never blocks. | ✓ |
| Hard ledger | Committed eval-count file; warns/refuses repeat OOS runs. | |
| Separate script only | OOS in its own entry point, no flag/ledger; pure discipline. | |

**User's choice:** Soft — `--oos` flag + warning.
**Notes:** Fits the solo, lightweight workflow while still nudging toward sacred. Hard ledger deferred.

---

## CI method + n-gating

| Option | Description | Selected |
|--------|-------------|----------|
| Wilson score, 95% | Closed-form, small-n robust, pure numpy, no new dep. | ✓ |
| Clopper-Pearson exact, 95% | Most conservative; needs scipy (new dep). | |
| Wald normal, 95% | Simplest; degenerate at n=11–18 and near 0/1. | |

**User's choice (CI method):** Wilson score, 95%.

| Option | Description | Selected |
|--------|-------------|----------|
| n ≥ 30 | Textbook rule-of-thumb; flags the n=11/18 extremes. | |
| n ≥ 50 | Stricter finding bar; flags more buckets. | ✓ |
| n ≥ 100 | Very strict; likely retires most per-direction/TF buckets. | |

**User's choice (min-n threshold):** n ≥ 50 (chose stricter than the recommended 30).

| Option | Description | Selected |
|--------|-------------|----------|
| Flag, keep visible | Show rate + n + CI, mark "below-n / not a finding"; never silently dropped. | ✓ |
| Suppress / hide | Omit below-threshold buckets from the findings surface. | |

**User's choice (below-threshold):** Flag, keep visible.

| Option | Description | Selected |
|--------|-------------|----------|
| Tidy long CSV | One row per bucket; rate/n/ci_low/ci_high/min_n_pass/slice. Matches cisd_expectancy.csv convention. | ✓ |
| JSON manifest | Structured/nested; best for programmatic consumption, breaks CSV convention. | |
| Markdown table | Human-readable; poor machine input for Phase 3 republish. | |

**User's choice (manifest format):** Tidy long CSV.
**Notes:** Wilson chosen specifically because the most important buckets live at n=11–18 where Wald lies. n≥50 makes headline eligibility mean something on this dataset.

---

## Coverage + default reconciliation

| Option | Description | Selected |
|--------|-------------|----------|
| Parallel path, keep full-history default | Harness adds train/OOS outputs + manifest; existing full-history run stays byte-identical so Phase 1 characterization tests stay green; Phase 3 republishes. | ✓ |
| Replace default with discovery-on-train now | Existing outputs become train-slice; re-point characterization tests in THIS phase. | |

**User's choice (reconciliation):** Parallel path, keep full-history default.

| Option | Description | Selected |
|--------|-------------|----------|
| Manifest + CSV only | Tabular reporting surface this phase; no new PNGs; existing full-history PNGs stay locked. | ✓ |
| Also render annotated charts | Additionally produce train/OOS PNGs with CI whiskers + n labels. | |

**User's choice (charts):** Manifest + CSV only.
**Notes:** Keeps the phase tight and behavior-preserving; visual CI annotation deferred to the Phase 3 republish.

---

## Claude's Discretion

- Exact `OOS_START` value: compute the 70th percentile of available bar dates on the shared NQ∩ES calendar, snap to a sensible session/day boundary, freeze and document.
- Harness code location (new `cisd_validation.py` module vs `scripts/build_validation.py` consumer) — constraint: additive, don't edit the locked compute path, degrade gracefully without SMT.
- Manifest column names/order and the discovery/OOS CSV layout (as long as the agreed fields are present).
- Whether train/OOS slicing happens pre- or post-resample, provided results match a full-history run restricted to the slice (no boundary-bar leakage).

## Deferred Ideas

- Visual CI annotation on PNG/HTML — Phase 3 republish.
- Hard evaluation ledger — rejected this phase; revisit if discipline insufficient.
- Multiple-comparisons correction (MHT-01) and walk-forward validation (WF-01) — v2.
- Clopper-Pearson exact CI — rejected to avoid scipy; revisit only if exact coverage required.
