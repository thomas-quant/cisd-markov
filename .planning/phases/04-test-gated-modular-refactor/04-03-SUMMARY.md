---
phase: 4
plan: "04-03"
subsystem: "core"
tags: [refactor, vectorize, performance, numpy, flatnonzero, bit-identical]
dependency_graph:
  requires: [04-01]
  provides: [vectorized-annotation-pass, vectorized-compute-functions]
  affects: [cisd_data, cisd_barriers, all-compute-consumers]
tech_stack:
  added: [numpy-flatnonzero-pattern]
  patterns: [np.flatnonzero-event-position-array, list-accumulate-bulk-assign, integer-position-barrier-hit]
key_files:
  created: []
  modified:
    - cisd_data.py
    - cisd_barriers.py
decisions:
  - "_annotate_cisd_research outer loop: list-accumulate + bulk-assign pattern (9 result lists, flatnonzero event positions, no iat/get_loc)"
  - "compute_wick uses two separate flatnonzero calls (one per directional mask) matching original two-pass semantics"
  - "_has_directional_sweep and _annotate_swing_smt_from_events left untouched per D-03 (out of REFAC-03 scope)"
  - "compute_fvg_hold vectorized via flatnonzero + 4 object arrays despite having no barrier_hit call, per REFAC-03 all-14 wording"
  - "All barrier_hit calls pass integer position as first arg and df.iloc[pos] as row arg — identical values to iterrows row"
metrics:
  duration: "~35m"
  completed: "2026-06-14T02:43:58Z"
  tasks_completed: 3
  files_created: 0
  files_modified: 2
---

# Phase 4 Plan 03: Vectorize annotation + compute hot loops with np.flatnonzero pattern

Replace the `iterrows()` + `df.index.get_loc(ts)` hot-loop pattern in `_annotate_cisd_research` (outer CISD loop) and in all 14 `compute_*` functions with the `np.flatnonzero` + NumPy-array-indexing pattern proven in `scripts/build_expectancy.py:build_event_r_multiples()`. All characterization tests confirm bit-identical numbers.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 04-03-01 | Vectorize _annotate_cisd_research outer loop (list-accumulate + bulk-assign) | 6bec198 | cisd_data.py |
| 04-03-02 | Vectorize 7 single-pass compute_* functions | df1fccd | cisd_barriers.py |
| 04-03-03 | Vectorize 5 consec/bucket compute_* functions and compute_fvg_hold | ce4d15f | cisd_barriers.py |

## What Was Built

**Task 04-03-01 — cisd_data.py `_annotate_cisd_research` outer loop:**
- Replaced `for idx, ct in enumerate(annotated["cisd_type"]):` with `event_pos = np.flatnonzero(pd.notna(ct_arr) & np.isin(ct_arr, ["bullish", "bearish"]))`
- Pre-initialise 9 result lists (defaults: `False` for bool columns, `"none"` for hold columns) before the loop
- Loop `for idx in event_pos:` reads `ct = ct_arr[idx]`, calls per-event helpers unchanged, writes into lists at position `idx`
- After loop: bulk-assign all 9 lists to their DataFrame columns via `annotated["col"] = list`
- `_has_directional_sweep` and `_annotate_swing_smt_from_events` bodies unchanged (D-03 deferral)

**Task 04-03-02 — 7 single-pass `compute_*` functions in cisd_barriers.py:**
- Added `import numpy as np` to cisd_barriers.py
- `compute_basic`: `flatnonzero` on `cisd_type.notna()`, integer-pos `barrier_hit` calls
- `compute_wick`: two `flatnonzero` calls on directional boolean masks (bull/bear); close/prev_high/prev_low as NumPy arrays
- `compute_smt_cisd`: `flatnonzero` + `ct_arr`/`tag_arr` object arrays
- `compute_cisd_fvg`: `flatnonzero` + `mid0_arr`/`mid1_arr` bool arrays
- `compute_cisd_fvg_interaction`: `flatnonzero` + 4 hold-state object arrays
- `compute_sweep`: `flatnonzero` + `sweep_arr` bool array
- `compute_sssf_swing`: `flatnonzero` + `prev_swing`/`cisd_swing` bool arrays

**Task 04-03-03 — 6 remaining `compute_*` functions:**
- `compute_mc`: `flatnonzero` + pass integer position to `_count_consecutive` (Series still passed for `.iloc` indexing inside)
- `compute_combined`: `flatnonzero` + `close_arr`/`prev_high_arr`/`prev_low_arr`
- `compute_volume`: `flatnonzero` + `vol_arr`/`prev_vol_arr` (precomputed `shift(1)` converted to array)
- `compute_candle_size`: `flatnonzero` + `close_arr`/`open_arr`/`atr_arr` (rolling ATR converted to array)
- `compute_size_cross`: `flatnonzero` + `close_arr`/`open_arr`/`atr_arr`/`prev_body_arr`
- `compute_fvg_hold`: `flatnonzero` + 4 hold-state object arrays (no barrier_hit — reads only hold columns)

## Unchanged Deferred Functions

Per CONTEXT.md D-03:
- `_has_directional_sweep` (double-nested loop with rolling min/max) — left for a future pass
- `_annotate_swing_smt_from_events` (O(n×m) inner loop, searchsorted-style) — left for a future pass
- `barrier_hit` — signature and body preserved exactly
- `_count_consecutive` — body preserved exactly; only the call-site variable name changed (`idx` → `pos`)

## Verification Results

- `grep -c "\.iterrows()" cisd_barriers.py` → 0 (all 14 compute functions vectorized)
- `grep -c "index.get_loc" cisd_barriers.py` → 0
- `grep -c "np.flatnonzero" cisd_barriers.py` → 14
- `grep -n "np.flatnonzero" cisd_data.py` → 1 (in `_annotate_cisd_research`)
- `grep -c "annotated.iat\[idx, annotated.columns.get_loc" cisd_data.py` → 0 in `_annotate_cisd_research`
- `pytest tests/` → 89 passed, 5 skipped (data-absent CI skips), 0 failed
- Characterization tests confirmed bit-identical numbers (5 data-absent skips are expected)

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria met per task.

## Known Stubs

None — all functions are fully implemented with bit-identical behavior.

## Threat Flags

None — this is a pure internal performance refactor with no new network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check: PASSED

- `cisd_data.py` modified: FOUND
- `cisd_barriers.py` modified: FOUND
- Commit 6bec198 exists: FOUND
- Commit df1fccd exists: FOUND
- Commit ce4d15f exists: FOUND
- `np.flatnonzero` in `_annotate_cisd_research`: CONFIRMED
- Zero `annotated.iat` in `_annotate_cisd_research` outer loop: CONFIRMED (remaining iat are in deferred `_annotate_swing_smt_from_events`)
- Zero `iterrows()` in `cisd_barriers.py`: CONFIRMED
- Zero `index.get_loc` in `cisd_barriers.py`: CONFIRMED
- 14 `np.flatnonzero` in `cisd_barriers.py`: CONFIRMED
- `barrier_hit` signature unchanged: CONFIRMED
- `_count_consecutive` body unchanged: CONFIRMED
- BINS/BUCKETS literals unchanged: CONFIRMED
- pytest 89 passed, 5 skipped, 0 failed: CONFIRMED
