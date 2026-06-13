---
phase: 03-re-validate-republish-existing-findings
plan: "02"
subsystem: testing
tags: [validation, oos, reconciler, findings, wilson-ci]

# Dependency graph
requires:
  - phase: 03-re-validate-republish-existing-findings/03-01
    provides: validation_manifest_discovery.csv, discovery_summary.md, build_validation.py --oos path

provides:
  - scripts/build_reconcile_findings.py — determine_verdict + reconcile() producing validation_findings.csv
  - tests/test_reconcile_findings.py — 7 data-free unit tests locking verdict logic
  - output/validation_manifest_oos.csv — sacred OOS evaluation manifest (slice=oos)
  - output/validation_findings.csv — 12-column labeled findings table (confirmed/not-confirmed/below-n)

affects:
  - 03-03-republish-readme — reads validation_findings.csv as single source of truth for README tables

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Outer-merge reconciliation: discovery + OOS manifests joined on 5 bucket keys; no bucket silently dropped (D-06)"
    - "determine_verdict: eligibility gated on discovery_n >= MIN_N (D-01); confirmation requires OOS rate same side of 0.50 as discovery (D-02)"
    - "below-n reserved exclusively for discovery_n < 50; eligible buckets with no OOS data -> not-confirmed (D-03)"

key-files:
  created:
    - scripts/build_reconcile_findings.py
    - tests/test_reconcile_findings.py
    - output/validation_manifest_oos.csv
    - output/validation_findings.csv
  modified: []

key-decisions:
  - "OOS spend approved (Task 2 gate: spend-oos) — sacred evaluation spent on 2026-06-13"
  - "SMT package was present and fully operational for the OOS run — all 32 smt_cisd buckets evaluated"
  - "Bearish Daily pattern dominates not-confirmed: 24 of 48 not-confirmed rows are Daily/bearish across 10 analyses — consistently failed OOS confirmation (discovery edges did not hold on holdout data)"
  - "Bullish patterns confirm robustly at 15min and 1H across both instruments; bearish Daily edges should not be published as findings in Plan 03-03"

patterns-established:
  - "verdict CSV (validation_findings.csv) is the single source of truth Plan 03-03 reads; never regenerate from raw manifests"
  - "SMT degradation check: count smt_cisd rows in OOS manifest; zero rows = SMT absent; 32 rows here = SMT fully present"

requirements-completed: [REVAL-02]

# Metrics
duration: 15min
completed: 2026-06-13
---

# Phase 3 Plan 02: Sacred OOS Evaluation + Findings Reconciliation Summary

**616 confirmed / 48 not-confirmed / 88 below-n across 752 buckets; bearish Daily edges failed OOS across 10 analyses while bullish 15min/1H patterns held; smt_cisd fully evaluated (SMT present)**

## Performance

- **Duration:** ~15 min (OOS harness + reconciler)
- **Started:** 2026-06-13T00:00:00Z (approx)
- **Completed:** 2026-06-13
- **Tasks:** 3 (Task 1 committed in prior wave; Task 2 human gate approved; Task 3 this wave)
- **Files created:** 4 (build_reconcile_findings.py, test_reconcile_findings.py, validation_manifest_oos.csv, validation_findings.csv)
- **Files modified:** 0

## Gate Decision

**Task 2 outcome:** spend-oos

The researcher reviewed `output/discovery_summary.md` and authorized the sacred OOS spend. The OOS evaluation ran exactly once. The sacred banner appeared once in stdout. Discovery manifest (`validation_manifest_discovery.csv`) was not clobbered — it retained all 752 rows with `slice='discovery'`.

## Accomplishments

- Sacred OOS harness ran once, producing `output/validation_manifest_oos.csv` (752 rows, all `slice='oos'`). SMT package was available — all 32 `smt_cisd` OOS buckets were evaluated (no degradation).
- Reconciler merged both manifests via outer join on 5 bucket keys, applied `determine_verdict` per row, and wrote `output/validation_findings.csv` with exactly the 12-column D-09 schema.
- Automated verification passed: column order correct, all verdict values in `{confirmed, not-confirmed, below-n}`, discovery manifest row count unchanged.

## Verdict Summary

| Verdict | Count |
|---------|-------|
| confirmed | 616 |
| not-confirmed | 48 |
| below-n | 88 |
| **Total** | **752** |

### Confirmed counts by analysis

| Analysis | Confirmed |
|----------|-----------|
| cisd_fvg_interaction | 98 |
| combined | 75 |
| candle_size | 53 |
| fvg_hold | 53 |
| volume | 53 |
| sssf_swing | 46 |
| size_cross | 45 |
| cisd_fvg | 43 |
| mc | 38 |
| wick | 31 |
| smt_cisd | 26 |
| sweep | 25 |
| significance | 16 |
| basic | 14 |

### Confirmed counts by timeframe

| Timeframe | Confirmed |
|-----------|-----------|
| 15min | 188 |
| 1H | 187 |
| 4H | 168 |
| Daily | 73 |

## Headline Findings That Did Not Survive OOS

### Pattern: Bearish Daily failed broadly (24 of 48 not-confirmed)

24 of the 48 not-confirmed rows are `timeframe=Daily, direction=bearish`, spanning 10 of 14 analyses. This is the dominant casualty pattern. Examples:

| Analysis | TF | Instr | Direction | Bucket | Disc rate (n) | OOS rate (n) |
|----------|----|-------|-----------|--------|---------------|--------------|
| basic | Daily | NQ | bearish | all | 0.591 (279) | 0.405 (116) |
| basic | Daily | ES | bearish | all | 0.553 (293) | 0.370 (119) |
| smt_cisd | Daily | NQ | bearish | no SMT | 0.575 (233) | 0.413 (104) |
| smt_cisd | Daily | ES | bearish | no SMT | 0.554 (240) | 0.364 (107) |
| smt_cisd | Daily | ES | bearish | w/ SMT | 0.547 (53) | 0.417 (12) |
| sweep | Daily | NQ | bearish | w/ sweep | 0.562 (121) | 0.390 (59) |
| sweep | Daily | NQ | bearish | no sweep | 0.614 (158) | 0.421 (57) |
| sweep | Daily | ES | bearish | no sweep | 0.575 (153) | 0.389 (54) |
| wick | Daily | NQ | bearish | within_wick | 0.503 (179) | 0.289 (83) |
| mc | Daily | NQ | bearish | 1_consecutive | 0.583 (127) | 0.423 (52) |
| mc | Daily | NQ | bearish | 2_consecutive | 0.576 (66) | 0.370 (27) |
| mc | Daily | NQ | bearish | 3_consecutive | 0.616 (86) | 0.389 (36) |
| mc | Daily | ES | bearish | 1_consecutive | 0.541 (146) | 0.382 (55) |

Plan 03-03 must label all bearish Daily buckets as `not-confirmed` and suppress them from headline findings.

### smt_cisd: bearish Daily and 4H ES bearish not confirmed

| Bucket | TF | Instr | Direction | Disc rate (n) | OOS rate (n) | Verdict |
|--------|----|-------|-----------|---------------|--------------|---------|
| no SMT | Daily | NQ | bearish | 0.575 (233) | 0.413 (104) | not-confirmed |
| no SMT | Daily | ES | bearish | 0.554 (240) | 0.364 (107) | not-confirmed |
| w/ SMT | Daily | ES | bearish | 0.547 (53) | 0.417 (12) | not-confirmed |
| w/ SMT | 4H | ES | bearish | 0.559 (222) | 0.467 (90) | not-confirmed |

All bullish smt_cisd buckets at 15min and 1H are confirmed, as are bearish 15min and 1H. SMT confirmation lift appears genuine at intraday timeframes but failed to hold on Daily bearish in the OOS window.

### combined: mixed Daily results

4 daily combined buckets not-confirmed, split between bullish and bearish directions. 4H combined shows some not-confirmed (rate very close to 0.50 in both slices).

## SMT Availability

SMT package at `/mnt/e/backup/code/Finance/Misc/SMT` was **present and fully operational** for the OOS run. The OOS manifest contains 32 `smt_cisd` rows (same count as discovery), all with `slice='oos'`. No graceful-degradation path was triggered. The section 8 SMT verdicts are fully evaluated.

## Task Commits

| Task | Name | Commit |
|------|------|--------|
| 1 (prior wave) | Add failing tests for determine_verdict and reconcile schema | cc6e06b |
| 1 (prior wave) | Implement determine_verdict and reconcile() for validation_findings.csv | 0bf7663 |
| 2 | Human gate: spend-oos decision | (no commit — checkpoint only) |
| 3 | Run OOS harness + reconcile; write SUMMARY | (this commit) |

## Files Created/Modified

- `scripts/build_reconcile_findings.py` — `determine_verdict` + `reconcile()`, reads both manifests, writes `validation_findings.csv` (Task 1, prior wave)
- `tests/test_reconcile_findings.py` — 7 data-free unit tests covering all verdict logic cases (Task 1, prior wave)
- `output/validation_manifest_oos.csv` — 752-row OOS manifest from sacred evaluation (Task 3)
- `output/validation_findings.csv` — 752-row labeled findings table with 12 D-09 columns (Task 3)

## Deviations from Plan

None — plan executed exactly as written. Worktree required `data/` and `output/` symlinks to the main repo (same pattern as Plan 03-01), applied without deviation tracking as it is standard worktree setup.

## Issues Encountered

None. The OOS harness completed cleanly. SMT was available. Both manifests loaded and merged without errors.

## Next Phase Readiness

`output/validation_findings.csv` is the single source of truth for Plan 03-03 (README republish). It contains:
- 616 confirmed buckets to republish with discovery rates + CI
- 48 not-confirmed buckets to label `not-confirmed` (never dropped per D-03)
- 88 below-n buckets to flag "below-n / not a finding" (D-06)

Plan 03-03 should prioritize: bearish Daily findings need `not-confirmed` labels across most analyses. Bullish intraday (15min, 1H) patterns are robustly confirmed. SMT lift at intraday is confirmed; SMT Daily bearish is not.

---
*Phase: 03-re-validate-republish-existing-findings*
*Completed: 2026-06-13*
