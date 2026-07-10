---
phase: 03-re-validate-republish-existing-findings
plan: "01"
subsystem: validation-harness
tags: [readme-fix, manifest, discovery-slice, oos-gate, smt]
dependency_graph:
  requires: []
  provides: [output/validation_manifest_discovery.csv, output/discovery_summary.md, scripts/build_discovery_summary.py]
  affects: [README.md, scripts/build_validation.py]
tech_stack:
  added: [scripts/build_discovery_summary.py]
  patterns: [slice-suffixed-manifest, wilson-ci, n-gate-50, per-analysis-review-report]
key_files:
  created: [scripts/build_discovery_summary.py]
  modified: [README.md, scripts/build_validation.py]
decisions:
  - "Use slice-suffixed manifest filenames (validation_manifest_discovery.csv / _oos.csv) so OOS runs cannot overwrite the discovery manifest"
  - "Keep validation_manifest.csv as legacy alias (import compat) but never write to it in new code"
  - "build_discovery_summary.py reads only the manifest CSV — no prepare_pair calls — so SMT degradation is inherited automatically"
metrics:
  duration: ~4h (including full SMT scan wall-clock time)
  completed: "2026-06-13"
  tasks_completed: 3
  files_changed: 3
---

# Phase 03 Plan 01: Re-validate / Republish Existing Findings Summary

Corrected stale WR-04 numbers in README, made the validation harness produce durable per-slice manifests, built the discovery summary report, and ran the discovery harness on the full dataset (SMT present).

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Fix stale WR-04 numbers (README §8 SMT table + §3 label) | f1b7ca4 | README.md |
| 2 | Durable per-slice manifest + discovery summary report | a6b9700 | scripts/build_validation.py, scripts/build_discovery_summary.py |
| 3 | Run the discovery harness and emit the discovery summary | a6b9700 | output/validation_manifest_discovery.csv (gitignored), output/discovery_summary.md (gitignored) |

## Discovery Harness Results

SMT was **present** (full smt_cisd rows included). All 14 analyses ran successfully.

**Total manifest rows:** 752  
**OOS-eligible buckets (n >= 50):** 664 of 752

### Per-analysis OOS-eligible count

| Analysis | OOS-eligible buckets |
|---|---|
| cisd_fvg_interaction | 98 |
| combined | 81 |
| volume | 59 |
| candle_size | 56 |
| fvg_hold | 56 |
| mc | 48 |
| size_cross | 48 |
| sssf_swing | 48 |
| cisd_fvg | 44 |
| sweep | 32 |
| wick | 32 |
| smt_cisd | 30 |
| basic | 16 |
| significance | 16 |

All 14 analyses have at least one OOS-eligible bucket — no analysis fell entirely below n=50 on the discovery slice.

**SMT data:** Present for all timeframes. 15min shows the most consistent positive effect (+2–3pp across all combos, n=3,558–4,020). Daily and 4H SMT cell sizes remain modest (n=58–312).

## WR-04 Fixes (Task 1)

**§3 within-wick label:** "ES bear drops to 36.7%" corrected to "NQ bear drops to 36.7%". The 36.7% figure is NQ Daily bear 2c within_wick (n=60); ES Daily bear 2c within_wick is 38.0% (n=71).

**§3 table:** "ES Bear 2c past wick" corrected from 80.7% to 80.6% (matches `_COMBINED_EXPECTED`).

**§8 SMT table:** All 16 "w/ SMT" rate+n cells regenerated from live full-history output, matching `_SMT_EXPECTED`:
- ES Daily Bearish corrected from 27.8% (n=18) stale outlier to 52.3% (n=65)
- 4H/1H cell sizes now hundreds (n=281–315 / 942–1,143) vs former stale single-digits
- 15min cell sizes now 3,558–4,020 (not the stale 1,200–1,400)
- Key takeaways rewritten: ES Daily bear is now a near-baseline 52.3%, not a dramatic 27.8% outlier

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Grep pattern `(NQ bear) drops to 36.7` failing due to bold markup**
- **Found during:** Task 1 verification
- **Issue:** Initial edit wrote `(NQ bear) drops to **36.7%**` with Markdown bold markers; the acceptance-criteria grep pattern `(NQ bear) drops to 36.7` did not match because `**` characters were between "to " and "36.7"
- **Fix:** Removed bold markers, changed to plain `(NQ bear) drops to 36.7%`
- **Files modified:** README.md
- **Commit:** f1b7ca4

**2. [Rule 3 - Blocking] Data directory missing in worktree**
- **Found during:** Task 1 (live SMT capture run)
- **Issue:** `cisd_analysis.py` resolves data via `Path(__file__).parent / "data"` — in the worktree that resolves to the worktree dir, not the main repo data
- **Fix:** Created symlink `data -> /mnt/e/backup/code/Finance/Research/cisd-markov/data` inside the worktree
- **Files modified:** none (symlink only, not tracked)
- **Commit:** n/a (symlink is gitignored as a data directory)

## Test Status

Phase 2 validation harness tests (`tests/test_validation_harness.py`, 14 tests) pass unchanged — `build_manifest_rows`, `slice_df`, `wilson_ci`, `n_gate` are byte-unchanged.

Phase 1 characterization tests (`tests/test_characterization.py`) remain green — no `compute_*` or pipeline code was modified.

## Artifacts Produced

| Artifact | Location | Status |
|---|---|---|
| Discovery manifest | output/validation_manifest_discovery.csv | Generated (gitignored) |
| Slice inventory | output/validation_slices.csv | Generated (gitignored) |
| Discovery summary report | output/discovery_summary.md | Generated (gitignored) |
| Durable manifest writer | scripts/build_discovery_summary.py | Committed (a6b9700) |
| Updated harness | scripts/build_validation.py | Committed (a6b9700) |
| Corrected README | README.md | Committed (f1b7ca4) |

**No OOS artifact produced** — `validation_manifest_oos.csv` does not exist. The sacred OOS gate is reserved for Plan 03-02.

## Known Stubs

None. All data sources are live full-history output; no placeholder values exist in the committed code.

## Threat Flags

None. No new network endpoints, auth paths, or trust-boundary schema changes introduced.

## Self-Check: PASSED

- scripts/build_discovery_summary.py: FOUND
- scripts/build_validation.py: FOUND (modified)
- README.md: FOUND (modified)
- Commit f1b7ca4: FOUND (git log)
- Commit a6b9700: FOUND (git log)
- output/validation_manifest_discovery.csv: FOUND (on disk, gitignored)
- output/discovery_summary.md: FOUND (on disk, gitignored)
