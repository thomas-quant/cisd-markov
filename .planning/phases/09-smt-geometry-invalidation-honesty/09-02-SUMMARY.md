---
phase: 09-smt-geometry-invalidation-honesty
plan: 02
subsystem: research-analysis
tags: [pandas, numpy, matplotlib, smt, cisd-barriers, cisd-charts, analysis-registry]

# Dependency graph
requires:
  - phase: 09-smt-geometry-invalidation-honesty (Plan 01)
    provides: "Widened `_annotate_swing_smt_from_events`: three-way swing_smt_tag, swing_smt_role, smt_broke_in_window, smt_block_size_atr, cisd_in_smt_block"
provides:
  - "compute_smt_cisd extended to three-way (w/ SMT / expired SMT / no SMT, D-03) plus w/ SMT & survived / w/ SMT & broke diagnostic sub-buckets that never filter the aggregate w/ SMT population (D-07)"
  - "compute_smt_role: swept / failed_to_sweep split over the valid w/ SMT population only (D-08)"
  - "compute_smt_block_size: <0.5x/0.5-1x/1-1.5x/>1.5x ATR buckets over the matched-SMT population (D-04/D-05a)"
  - "compute_smt_in_block: cisd_in_block / cisd_out_block split over the matched-SMT population (D-05)"
  - "chart_smt_cisd (three-way) + new chart_smt_role/chart_smt_block_size/chart_smt_in_block"
  - "smt_role, smt_block_size, smt_in_block registered in ANALYSES + ANALYSIS_META (single edit point) and re-exported through cisd_analysis.py"
  - "tests/test_smt_geometry.py — compute-layer TDD lock + manifest-shape smoke test proving generic dispatch pass-through"
affects: [09-03-methodology-documentation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "New compute_* functions follow the existing numpy-array + np.flatnonzero(pd.notna(cisd_type)) event_pos idiom, reusing barrier_hit(df, pos, df.iloc[pos], ct) verbatim"
    - "Registry wiring is a single edit point: ANALYSES + ANALYSIS_META dicts in cisd_barriers.py; cisd_analysis.py main()'s STANDALONE_KEYS/FILENAMES derive automatically, no separate edit needed"
    - "Diagnostic sub-buckets (w/ SMT & survived / w/ SMT & broke) are sibling keys inside the same flat stats[ct] dict, not a nested level — keeps the generic build_manifest_rows dispatch working with zero harness changes"

key-files:
  created:
    - tests/test_smt_geometry.py
  modified:
    - cisd_barriers.py
    - cisd_charts.py
    - cisd_analysis.py

key-decisions:
  - "D-03/D-07 implemented as specified: compute_smt_cisd's stats[ct] dict carries five flat keys (w/ SMT, expired SMT, no SMT, w/ SMT & survived, w/ SMT & broke); the survived/broke split is computed only when smt_broke_in_window is present (graceful degradation) and only for tag == 'w/ SMT', run outcome reused from the same barrier_hit call rather than recomputed"
  - "D-08: compute_smt_role restricts event_pos to swing_smt_tag == 'w/ SMT' before bucketing by swing_smt_role, so 'no SMT'/'expired SMT' rows (role == 'none') are excluded entirely rather than appearing as a third bucket"
  - "D-04/D-05a: compute_smt_block_size reuses compute_candle_size's BINS list and bucket-threshold convention verbatim, skipping NaN smt_block_size_atr rows (unmatched population) rather than adding a 'none' bucket"
  - "D-05: compute_smt_in_block restricts event_pos to swing_smt_tag in {'w/ SMT','expired SMT'} before bucketing by cisd_in_smt_block, so a no-SMT row's default-False in_block value is never counted as cisd_out_block"
  - "chart_smt_cisd renders only the three-way tags (w/ SMT / expired SMT / no SMT); the survived/broke sub-buckets are intentionally manifest-only (SC4 reporting lives in the regenerated CSV/README, not a fourth chart tier) to avoid double-counting rows in one bar-chart axis"

requirements-completed: [RES-06]

coverage:
  - id: D1
    description: "compute_smt_cisd three-way split (w/ SMT / expired SMT / no SMT) plus w/ SMT & survived / w/ SMT & broke diagnostic sub-buckets that never filter the aggregate w/ SMT population (D-03/D-07)"
    requirement: "RES-06"
    verification:
      - kind: unit
        ref: "tests/test_smt_geometry.py::test_compute_smt_cisd_three_way_split"
        status: pass
      - kind: unit
        ref: "tests/test_smt_geometry.py::test_compute_smt_cisd_survived_broke_never_filters_aggregate"
        status: pass
      - kind: unit
        ref: "tests/test_smt_geometry.py::test_compute_smt_cisd_degrades_without_broke_column"
        status: pass
      - kind: unit
        ref: "tests/test_swing_smt_integration.py::test_compute_smt_cisd_splits_runs_by_swing_smt_tag"
        status: pass
    human_judgment: false
  - id: D2
    description: "compute_smt_role: swept / failed_to_sweep split over the valid w/ SMT population only, surfaced as a new standalone analysis (D-08/SC2)"
    requirement: "RES-06"
    verification:
      - kind: unit
        ref: "tests/test_smt_geometry.py::test_compute_smt_role_counts_only_valid_w_smt_rows"
        status: pass
      - kind: unit
        ref: "tests/test_smt_geometry.py::test_compute_smt_role_raises_without_swing_smt_role"
        status: pass
      - kind: unit
        ref: "tests/test_smt_geometry.py::test_compute_smt_role_raises_without_swing_smt_tag"
        status: pass
    human_judgment: false
  - id: D3
    description: "compute_smt_block_size (ATR-bucketed) and compute_smt_in_block (containment split) over the matched-SMT population only (D-04/D-05/D-05a/SC3)"
    requirement: "RES-06"
    verification:
      - kind: unit
        ref: "tests/test_smt_geometry.py::test_compute_smt_block_size_buckets_matched_population_only"
        status: pass
      - kind: unit
        ref: "tests/test_smt_geometry.py::test_compute_smt_in_block_matched_population_only"
        status: pass
      - kind: unit
        ref: "tests/test_smt_geometry.py::test_compute_smt_block_size_raises_without_column"
        status: pass
      - kind: unit
        ref: "tests/test_smt_geometry.py::test_compute_smt_in_block_raises_without_cisd_in_smt_block"
        status: pass
    human_judgment: false
  - id: D4
    description: "chart_smt_cisd extended to three-way tiers; new chart_smt_role/chart_smt_block_size/chart_smt_in_block render the new splits"
    requirement: "RES-06"
    verification:
      - kind: unit
        ref: "manual smoke run: chart_smt_cisd/chart_smt_role/chart_smt_block_size/chart_smt_in_block rendered against real compute() output shapes with matplotlib Agg backend, no exceptions"
        status: pass
    human_judgment: false
  - id: D5
    description: "smt_role, smt_block_size, smt_in_block registered in ANALYSES + ANALYSIS_META (single edit point), re-exported through cisd_analysis.py, and proven to emit manifest rows with n/ci_low/ci_high via build_manifest_rows's generic dispatch"
    requirement: "RES-06"
    verification:
      - kind: unit
        ref: "tests/test_smt_geometry.py::test_new_analyses_emit_manifest_rows_via_generic_dispatch"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-12
status: complete
---

# Phase 09 Plan 02: SMT Geometry Consumer Reporting Summary

**Extended `compute_smt_cisd` to a three-way validity split with survived/broke diagnostic sub-buckets, added `compute_smt_role`/`compute_smt_block_size`/`compute_smt_in_block` with matching charts, and registered all three as new standalone analyses flowing through the validation harness's generic manifest dispatch with zero harness changes.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-12T09:00Z (context load)
- **Completed:** 2026-07-12T09:05Z
- **Tasks:** 3
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- `compute_smt_cisd` now reports the three-way `w/ SMT` / `expired SMT` / `no SMT` split (D-03), making the previously mis-credited already-invalidated-SMT population visible instead of silently folding into `no SMT`
- `compute_smt_cisd` also reports `w/ SMT & survived` and `w/ SMT & broke` diagnostic sub-buckets alongside — never instead of — the un-split aggregate `w/ SMT` bucket (D-07); degrades gracefully to zero-filled sub-buckets when `smt_broke_in_window` is absent (single-instrument frames)
- New `compute_smt_role` surfaces the previously-unused role split (swept vs failed-to-sweep) as a standalone analysis over the valid `w/ SMT` population only (D-08/SC2)
- New `compute_smt_block_size` buckets `smt_block_size_atr` into the same `<0.5x/0.5-1x/1-1.5x/>1.5x ATR` convention as `compute_candle_size`, restricted to the matched-SMT population (D-04/SC3)
- New `compute_smt_in_block` splits `cisd_in_smt_block` into `cisd_in_block`/`cisd_out_block`, also restricted to the matched-SMT population so a no-SMT row's default-False never counts as `cisd_out_block` (D-05/SC3)
- Four chart functions (`chart_smt_cisd` extended + three new) render the splits using the established alpha-tiered horizontal-bar idiom
- `smt_role`, `smt_block_size`, `smt_in_block` registered in `ANALYSES` + `ANALYSIS_META` (the single edit point per CLAUDE.md's "Adding a New Analysis" recipe) and re-exported through `cisd_analysis.py`'s public API shim
- A manifest-shape smoke test proves all four analyses (`smt_role`, `smt_block_size`, `smt_in_block`, `smt_cisd`) flow through `scripts/build_validation.py`'s generic `{dir: {tag: {total, runs}}}` dispatch and emit rows with `n`/`ci_low`/`ci_high` populated — inheriting Wilson CI + BH-FDR + walk-forward for free once Plan 09-03 regenerates the manifest

## Task Commits

Each task was committed atomically (TDD RED/GREEN for Task 1):

1. **RED: failing tests for compute layer** - `9c8ebdc` (test)
2. **Task 1 GREEN: compute_smt_cisd three-way + survived/broke, new compute_smt_role/block_size/in_block** - `d3f1e01` (feat)
3. **Task 2: chart layer — chart_smt_cisd extension + chart_smt_role/block_size/in_block** - `4756474` (feat)
4. **Task 3: registry wiring + re-export shim + manifest smoke test** - `b44ddfc` (feat)

**Plan metadata:** _(pending — this commit)_

## Files Created/Modified
- `cisd_barriers.py` — `compute_smt_cisd` extended to three-way + survived/broke sub-buckets; new `compute_smt_role`, `compute_smt_block_size`, `compute_smt_in_block`; three new chart imports; `ANALYSES`/`ANALYSIS_META` sibling entries; `__all__` widened
- `cisd_charts.py` — `chart_smt_cisd` extended to three-way tiers; new `chart_smt_role`, `chart_smt_block_size`, `chart_smt_in_block`; `__all__` widened
- `cisd_analysis.py` — re-export shim widened with the three new compute_*/chart_* symbols in both import blocks and `__all__`
- `tests/test_smt_geometry.py` — new held-out test file locking the three-way split, survived/broke sub-bucket totals, role/geometry population restrictions, ValueError guard contracts, and the manifest-shape smoke test

## Decisions Made
- D-03/D-07: `compute_smt_cisd`'s `stats[ct]` dict carries five flat sibling keys; the survived/broke split reuses the single `barrier_hit()` call already made for the aggregate tag rather than recomputing it, and is computed only when `smt_broke_in_window` is present (graceful degradation for single-instrument frames)
- D-08: `compute_smt_role` filters `event_pos` to `swing_smt_tag == "w/ SMT"` before bucketing by role, excluding `no SMT`/`expired SMT` rows (role `"none"`) entirely rather than adding a third bucket
- D-04/D-05a: `compute_smt_block_size` reuses `compute_candle_size`'s `BINS` list and bucket-threshold convention verbatim; NaN `smt_block_size_atr` rows (unmatched population) are skipped, not bucketed
- D-05: `compute_smt_in_block` filters `event_pos` to `swing_smt_tag in {"w/ SMT","expired SMT"}` before bucketing by containment, so a no-SMT row's default-False `cisd_in_smt_block` is never miscounted as `cisd_out_block`
- `chart_smt_cisd` intentionally does not render the survived/broke sub-buckets — they are a manifest-only diagnostic (SC4) to avoid double-counting rows within a single bar-chart axis; the split is visible in the regenerated CSV/README instead (Plan 09-03)

## Deviations from Plan

None — plan executed exactly as written. All four compute functions, four chart functions, and the registry wiring matched the plan's specified shapes and population restrictions on first implementation; no fixture or harness breakage was introduced (existing `test_swing_smt_integration.py` and `test_vectorization_parity.py` suites remain green).

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The `ANALYSES`/`ANALYSIS_META` registry now carries `smt_role`, `smt_block_size`, `smt_in_block` alongside the extended `smt_cisd`, all flowing through `build_manifest_rows`'s generic dispatch with zero harness changes — confirmed via the manifest-shape smoke test
- Plan 09-03 (methodology documentation, D-09/D-09a) can proceed once the manifest is regenerated end-to-end: the new buckets will carry real n + Wilson CI + BH-FDR + walk-forward verdicts, and the before/after `w/ SMT` rate comparison (currently-published vs corrected) is now computable from the regenerated manifest
- No blockers identified

---
*Phase: 09-smt-geometry-invalidation-honesty*
*Completed: 2026-07-12*
