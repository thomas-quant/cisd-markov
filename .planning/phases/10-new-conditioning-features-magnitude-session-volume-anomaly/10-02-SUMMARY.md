---
phase: 10-new-conditioning-features-magnitude-session-volume-anomaly
plan: 02
subsystem: research-analysis
tags: [pandas, numpy, atr-bins, rvol, wilson-ci, bh-fdr, cisd]

requires:
  - phase: 10-new-conditioning-features-magnitude-session-volume-anomaly
    provides: "9 annotation columns from Plan 01 (wick_distance_atr, sweep_depth_atr, fvg_size_atr, vol_per_range, rvol, volume_zscore, session_tag + swept_level/fvg_gap_width)"
provides:
  - "6 new standalone compute_*/chart_* analyses (wick_distance, sweep_depth, fvg_size, effort_result, rvol, volume_zscore) fully registered in ANALYSES + ANALYSIS_META"
  - "frozen bin cut points for all six analyses, documented in-code with discovery-histogram derivation and 2026-07-12 date"
  - "D-06 wick_distance <-> compute_wick reconciliation rule (lo < ratio <= hi comparator)"
affects: [10-03-PLAN, 10-04-PLAN]

tech-stack:
  added: []
  patterns:
    - "lo < ratio <= hi comparator (deviation from the codebase's usual lo <= ratio < hi) used uniquely by compute_wick_distance to reconcile ratio==0 to the 'within wick' bucket, matching compute_wick's strict '>' semantics (D-06)"
    - "compute_sweep_depth/compute_fvg_size/compute_effort_result/compute_rvol/compute_volume_zscore all copy compute_smt_block_size's ATR-ratio + pd.isna(ratio) skip + fixed-BINS idiom verbatim, only swapping the source column and BINS constant"

key-files:
  created: []
  modified:
    - cisd_barriers.py
    - cisd_charts.py
    - tests/test_conditioning_features.py

key-decisions:
  - "D-06 reconciliation (frozen): compute_wick_distance uses a `lo < ratio <= hi` comparator (not the codebase's usual `lo <= ratio < hi`) so wick_distance_atr == 0 lands in the '-1x-0 ATR (within wick)' bucket, not '0-1x ATR (past wick)' — this is a mathematical identity (not just a test-fixture coincidence): wick_distance_atr's sign decomposes the exact same close-vs-prior-high/low comparison compute_wick already makes, so the two >0 bins always sum to compute_wick's past_wick total and the two <=0 bins always sum to within_wick, for any input data, verified via a 120-bar synthetic random-walk fixture run through the real prepare() pipeline."
  - "Frozen volume-anomaly bins adopted verbatim from the orchestrator's outcome-blind discovery-slice histogram (index < OOS_START, ~225k-230k finite obs, 2026-07-12) — not re-derived by this executor. Documented in-comment on each function per D-04."
  - "fvg_size uses a single flat population (mid0-priority union, per Plan 01's frozen decision) rather than splitting mid0/mid1 sub-buckets, keeping the flat {dir:{tag:{total,runs}}} shape and the generic build_manifest_rows dispatch untouched."
  - "sweep_depth/fvg_size/effort_result/rvol/volume_zscore all copy compute_smt_block_size's pd.isna(ratio) skip discipline — no re-check of has_dir_sweep/has_dir_fvg_mid0/mid1 in the compute layer, trusting the Plan 01 annotation's NaN gating (D-05)."

requirements-completed: [RES-07]

coverage:
  - id: D1
    description: "compute_wick_distance: signed ATR-bin analysis over ALL CISDs with an edge at 0.0, whose non-negative-past bins recover compute_wick's past_wick total and non-positive-within bins recover within_wick exactly (D-06)"
    requirement: "RES-07"
    verification:
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_wick_distance_population_all_cisds_and_nan_atr_skipped"
        status: pass
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_wick_distance_reconciles_with_compute_wick"
        status: pass
    human_judgment: false
  - id: D2
    description: "compute_sweep_depth / compute_fvg_size: ATR-binned magnitude analyses restricted to their natural population via pd.isna on the source ratio column, copying compute_smt_block_size's convention"
    requirement: "RES-07"
    verification:
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_sweep_depth_and_fvg_size_gate_on_nan_ratio"
        status: pass
    human_judgment: false
  - id: D3
    description: "compute_effort_result / compute_rvol / compute_volume_zscore: fixed, discovery-histogram-derived bins over vol_per_range/rvol/volume_zscore, frozen outcome-blind and documented in-code (D-04/D-07/D-08)"
    requirement: "RES-07"
    verification:
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_volume_anomaly_compute_functions_flat_shape_and_bin_boundaries"
        status: pass
    human_judgment: false
  - id: D4
    description: "All six analyses registered once each in ANALYSES + ANALYSIS_META (standalone=True, filename set), charted, added to build_csv_rows' flat dispatch, and flow through the generic build_manifest_rows dispatch with zero harness change (D-12)"
    requirement: "RES-07"
    verification:
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_new_analyses_registered_and_dispatch_generically"
        status: pass
      - kind: other
        ref: "python -c \"from cisd_barriers import ANALYSES, ANALYSIS_META; ...\" -> 'registry OK'; python -c \"import cisd_analysis\" exit 0"
        status: pass
    human_judgment: false
  - id: D5
    description: "compute_wick, compute_sweep, compute_cisd_fvg, compute_volume remain byte-for-byte unmodified (D-10/D-12); existing byte-stability suites (test_core_compute.py, test_characterization.py) still pass against real parquet data"
    requirement: "RES-07"
    verification:
      - kind: other
        ref: "git diff --unified=0 cisd_barriers.py | grep def compute_wick/compute_sweep/compute_cisd_fvg -> no output"
        status: pass
      - kind: integration
        ref: "tests/test_core_compute.py + tests/test_characterization.py (11 tests, real parquet data)"
        status: pass
    human_judgment: false

duration: ~30min
completed: 2026-07-12
status: complete
---

# Phase 10 Plan 02: Magnitude + Volume-Anomaly Conditioning Analyses Summary

**Added six new standalone analyses (wick_distance, sweep_depth, fvg_size, effort_result, rvol, volume_zscore) with frozen, outcome-blind bins — the signed wick_distance analysis mathematically reconciles to compute_wick's existing past/within split via a deliberately non-standard `lo < ratio <= hi` bin comparator.**

## Performance

- **Duration:** ~30 min (includes ~7 min of background byte-stability regression against real parquet data)
- **Completed:** 2026-07-12
- **Tasks:** 3 (all `type="auto"`, Tasks 1-2 `tdd="true"`)
- **Files modified:** 3 (`cisd_barriers.py`, `cisd_charts.py`, `tests/test_conditioning_features.py`)

## Accomplishments

- `compute_wick_distance` — signed ATR-bin analysis over ALL CISDs, edge exactly at 0.0. Reconciliation with `compute_wick` is a structural identity, not a coincidence: `wick_distance_atr`'s sign decomposes the exact same close-vs-prior-wick comparison `compute_wick` already makes, so the function uses a `lo < ratio <= hi` comparator (rather than the codebase's usual `lo <= ratio < hi`) so `ratio == 0` lands in "within wick" — matching `compute_wick`'s strict `>`/`<` semantics. Verified on a 120-bar synthetic random-walk fixture run through the real `prepare()` pipeline (not a hand-picked boundary case).
- `compute_sweep_depth` / `compute_fvg_size` — ATR-binned magnitude analyses (`<0.5x/0.5-1x/1-1.5x/>1.5x ATR`), copying `compute_smt_block_size`'s `pd.isna(ratio)` skip discipline near-verbatim. `fvg_size` uses the single flat mid0-priority population from Plan 01 (no mid0/mid1 split).
- `compute_effort_result` / `compute_rvol` / `compute_volume_zscore` — fixed bins adopted verbatim from the orchestrator's outcome-blind discovery-slice histogram (index < OOS_START, ~225k-230k finite obs, 2026-07-12), documented in-comment on each function.
- All six analyses registered once each in `ANALYSES` + `ANALYSIS_META` (`standalone=True`, all-TF PNG filenames), charted, and added to `build_csv_rows`' flat dispatch — `build_manifest_rows`' generic `else` branch (`scripts/build_validation.py:299`) required zero changes, confirmed by a registry smoke test.
- `compute_wick`, `compute_sweep`, `compute_cisd_fvg`, `compute_volume` remain byte-for-byte unmodified (D-10/D-12) — confirmed by `git diff` and by the full `test_core_compute.py` + `test_characterization.py` byte-stability suites (11 tests) passing against real parquet data.

## Frozen Bins (for Plan 04's README writeup)

| Analysis | Column | Bins | Comparator |
|---|---|---|---|
| `wick_distance` | `wick_distance_atr` | `<-1x ATR (deep within wick)` / `-1x-0 ATR (within wick)` / `0-1x ATR (past wick)` / `>1x ATR (far past wick)` | `lo < ratio <= hi` (D-06 reconciliation; edge 0.0 -> within) |
| `sweep_depth` | `sweep_depth_atr` | `<0.5x ATR` / `0.5x-1x ATR` / `1x-1.5x ATR` / `>1.5x ATR` | `lo <= ratio < hi` (copied from `compute_smt_block_size`) |
| `fvg_size` | `fvg_size_atr` | `<0.5x ATR` / `0.5x-1x ATR` / `1x-1.5x ATR` / `>1.5x ATR` | `lo <= ratio < hi` |
| `effort_result` | `vol_per_range` | `<150` / `150-550` / `550-1500` / `>1500` | `lo <= ratio < hi` — derived from discovery p25/p50/p75 (156/552/1500), 2026-07-12 |
| `rvol` | `rvol` | `<0.7x slot` / `0.7x-1x slot` / `1x-1.5x slot (elevated)` / `>1.5x slot (spike)` | `lo <= ratio < hi` — 1.0 edge preserved (D-08); cuts near discovery p27/p60/p88, 2026-07-12 |
| `volume_zscore` | `volume_zscore` | `<-0.5 sigma` / `-0.5-0.5 sigma` / `0.5-1.5 sigma` / `>1.5 sigma (spike)` | `lo <= ratio < hi` — symmetric straddle of 0; cuts near discovery p35/p76/p90, 2026-07-12 |

PNG filenames (all-TF standalone figures, per `ANALYSIS_META`):
`WickDistance_All_Timeframes.png`, `SweepDepth_All_Timeframes.png`, `FVGSize_All_Timeframes.png`, `EffortResult_All_Timeframes.png`, `RVOL_All_Timeframes.png`, `VolumeZScore_All_Timeframes.png`.

## Task Commits

Each task was committed atomically (RED gate first, then per-task GREEN commits):

1. **RED gate: failing tests for all three tasks** - `7f74d42` (test)
2. **Task 1: Magnitude compute functions** - `cb5d6cc` (feat)
3. **Task 2: Volume-anomaly compute functions** - `875742e` (feat)
4. **Task 3: Charts + registry wiring** - `952eec0` (feat)

## Files Created/Modified

- `cisd_barriers.py` — 6 new `compute_*` functions, 6 new `ANALYSES` entries, 6 new `ANALYSIS_META` entries, updated `__all__` and the `from cisd_charts import (...)` block
- `cisd_charts.py` — 6 new `chart_*` functions, extended `build_csv_rows`' flat dispatch tuple, updated `__all__`
- `tests/test_conditioning_features.py` — 7 new synthetic tests covering the reconciliation identity, NaN-gating, frozen-bin boundaries, and the registry/generic-dispatch smoke test

## Decisions Made

- **D-06 reconciliation rule (frozen):** `compute_wick_distance` uses `lo < ratio <= hi` (not the codebase's usual `lo <= ratio < hi`) so `wick_distance_atr == 0` maps to "within wick", matching `compute_wick`'s strict `>`/`<` boundary. This is documented as a mathematical identity in the function's docstring, not a fixture-specific coincidence — verified against a synthetic random-walk series run through the real `prepare()` pipeline rather than hand-picked edge cases.
- **Frozen volume bins adopted verbatim** from the orchestrator-supplied discovery-slice histogram (not re-derived) — each function's docstring records the exact discovery percentiles and the 2026-07-12 derivation date per D-04's outcome-blind-freeze requirement.
- **`fvg_size` stays a single flat population** (mid0-priority union per Plan 01's frozen decision), not split into mid0/mid1 sub-buckets, to keep the flat shape and avoid a hand-added `build_manifest_rows` branch.

## Deviations from Plan

None - plan executed exactly as written, using the frozen bins and reconciliation rule supplied in the execution context.

## Issues Encountered

None.

## Next Phase Readiness

- All six new analyses are live in `ANALYSES`/`ANALYSIS_META`, run on all four timeframes, and flow through the generic `build_manifest_rows` dispatch with zero harness change — Plan 03 can now register `compute_session` alongside these using the same pattern, adding only the `ANALYSIS_META.applies_to` TF-scoping mechanism (D-14) that this plan deliberately did not need.
- Plan 04's README writeup can consume the frozen bin table above directly.
- No blockers.

---
*Phase: 10-new-conditioning-features-magnitude-session-volume-anomaly*
*Completed: 2026-07-12*

## Self-Check: PASSED

- FOUND: `cisd_barriers.py`
- FOUND: `cisd_charts.py`
- FOUND: `tests/test_conditioning_features.py`
- FOUND: `.planning/phases/10-new-conditioning-features-magnitude-session-volume-anomaly/10-02-SUMMARY.md`
- FOUND commit: `7f74d42` (test: RED gate)
- FOUND commit: `cb5d6cc` (feat: Task 1 magnitude computes)
- FOUND commit: `875742e` (feat: Task 2 volume-anomaly computes)
- FOUND commit: `952eec0` (feat: Task 3 charts + registry wiring)
