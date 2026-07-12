---
phase: 09-smt-geometry-invalidation-honesty
plan: 01
subsystem: research-annotation
tags: [pandas, numpy, vectorized, smt, cisd-data]

# Dependency graph
requires:
  - phase: 08-performance-vectorize-the-enrichment-validation-hot-path
    provides: "Vectorized `_annotate_swing_smt_from_events` (searchsorted gather-and-scatter idiom, no per-bar Python loop)"
provides:
  - "Widened `_annotate_swing_smt_from_events`: lifecycle fields, three-way validity tag (w/ SMT / expired SMT / no SMT), smt_broke_in_window horizon flag, smt_block_size_atr + cisd_in_smt_block geometry columns"
  - "tests/test_smt_invalidation.py — held-out TDD lock on the validity/geometry semantics"
affects: [09-02-consumer-reporting, 09-03-methodology-documentation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Vectorized gather-and-scatter extended with additional per-match numpy arrays (lifecycle fields, validity mask, geometry) rather than a re-introduced per-bar loop"
    - "ATR(14) and block containment computed once outside the direction loop, reused inside via positional gather (matched_candidate_pos / match_positions)"

key-files:
  created:
    - tests/test_smt_invalidation.py
  modified:
    - cisd_data.py
    - tests/test_swing_smt_integration.py
    - tests/test_vectorization_parity.py

key-decisions:
  - "D-01/D-02/D-03/D-03a implemented exactly as specified: validity = broken_ts NaT or > t, checked only on the latest-created matched SMT, never reading status"
  - "D-04 ATR anchored at bar t (Claude's Discretion default), reusing compute_candle_size's (high-low).rolling(14).mean() convention verbatim"
  - "D-05 containment requires both open_t and close_t inside [block_low, block_high] (wicks excluded, full body containment)"
  - "Rule 1 auto-fix: widening required_event_columns and computing ATR/OHLC arrays unconditionally broke 3 fixtures in tests/test_swing_smt_integration.py and 7 fixtures in tests/test_vectorization_parity.py (both pre-existing, Phase 08 parity-lock tests) that only supplied the original 4-column event schema and/or lacked OHLC columns; updated those fixtures with the widened schema and still-valid lifecycle defaults, preserving all original assertions"

requirements-completed: [RES-06]

coverage:
  - id: D1
    description: "Three-way swing_smt_tag split (w/ SMT / expired SMT / no SMT) with broken_ts-vs-t validity, never reading status; latest-created-match-only semantics (D-01/D-02/D-03/D-03a)"
    requirement: "RES-06"
    verification:
      - kind: unit
        ref: "tests/test_smt_invalidation.py::test_broken_ts_equal_to_cisd_bar_yields_expired_smt"
        status: pass
      - kind: unit
        ref: "tests/test_smt_invalidation.py::test_status_broken_far_future_does_not_disqualify"
        status: pass
      - kind: unit
        ref: "tests/test_smt_invalidation.py::test_expired_latest_match_not_rescued_by_earlier_valid_event"
        status: pass
    human_judgment: false
  - id: D2
    description: "Lifecycle fields (smt_reference_price, smt_invalidation_level, smt_broken_ts, smt_status, smt_reference_timestamp, smt_invalidation_asset, smt_invalidation_direction) carried at matched rows, defaulted elsewhere"
    requirement: "RES-06"
    verification:
      - kind: unit
        ref: "tests/test_smt_invalidation.py::test_lifecycle_fields_populated_at_matched_rows"
        status: pass
      - kind: unit
        ref: "tests/test_smt_invalidation.py::test_lifecycle_fields_default_at_no_smt_rows"
        status: pass
    human_judgment: false
  - id: D3
    description: "smt_broke_in_window flag True iff broken_ts falls in (t, t+2] under LOOKAHEAD=2 (D-06)"
    requirement: "RES-06"
    verification:
      - kind: unit
        ref: "tests/test_smt_invalidation.py::test_smt_broke_in_window_flag"
        status: pass
    human_judgment: false
  - id: D4
    description: "smt_block_size_atr = (reference-bar high - low) / ATR(14)-at-t and cisd_in_smt_block full-body containment, computed for the matched population (w/ SMT + expired SMT), NaN/False for no-SMT and reindex-miss/ATR-NaN cases (D-04/D-05/D-05a)"
    requirement: "RES-06"
    verification:
      - kind: unit
        ref: "tests/test_smt_invalidation.py::test_smt_block_size_atr_matches_reference_bar_range_over_atr"
        status: pass
      - kind: unit
        ref: "tests/test_smt_invalidation.py::test_cisd_in_smt_block_true_when_body_fully_contained"
        status: pass
      - kind: unit
        ref: "tests/test_smt_invalidation.py::test_geometry_columns_set_for_expired_smt_rows_too"
        status: pass
      - kind: unit
        ref: "tests/test_smt_invalidation.py::test_smt_block_size_atr_nan_and_containment_false_on_reindex_miss"
        status: pass
    human_judgment: false
  - id: D5
    description: "No per-bar Python loop reintroduced; existing behavior-lock suites (test_swing_smt_integration.py, test_vectorization_parity.py) still pass"
    requirement: "RES-06"
    verification:
      - kind: unit
        ref: "tests/test_swing_smt_integration.py (12 tests)"
        status: pass
      - kind: unit
        ref: "tests/test_vectorization_parity.py (24 tests)"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-07-12
status: complete
---

# Phase 09 Plan 01: SMT Invalidation Honesty + Geometry Annotation Summary

**Widened `_annotate_swing_smt_from_events` to fix the already-invalidated-SMT tagging bug (three-way `w/ SMT` / `expired SMT` / `no SMT` split, D-01/D-02/D-03/D-03a), carry the scanner's lifecycle fields, and add `smt_block_size_atr` / `cisd_in_smt_block` geometry plus the `smt_broke_in_window` horizon flag — all vectorized, no per-bar loop.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-12T08:40Z (context load)
- **Completed:** 2026-07-12T08:54Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- Fixed the already-invalidated-at-`t` SMT tagging bug: a matched SMT whose `broken_ts` lands exactly on the CISD bar is now tagged `expired SMT` instead of being silently credited as `w/ SMT`
- Validity check compares `broken_ts` to `t` only — never reads `status` (D-02), and is evaluated only on the single latest-created matched SMT (D-03a), matching the existing selection rule
- Carried through the scanner's full lifecycle schema (`reference_price`, `invalidation_level`, `broken_ts`, `status`, `reference_timestamp`, `invalidation_asset`, `invalidation_direction`) at matched rows
- Added `smt_broke_in_window`: True iff `broken_ts` falls in `(t, t+2]` under `LOOKAHEAD=2`
- Added `smt_block_size_atr` (reference-bar range / ATR(14)-at-`t`, reusing `compute_candle_size`'s ATR convention) and `cisd_in_smt_block` (full-body containment) over the whole matched population (`w/ SMT` and `expired SMT` alike), NaN/False for `no SMT` and graceful NaN/False on ATR-not-yet-available or reindex-miss
- All changes are vectorized gather-and-scatter extensions of the existing per-direction `searchsorted` matcher — no per-bar Python loop reintroduced

## Task Commits

Each task was committed atomically (TDD RED → GREEN split further into Task 1 / Task 2 GREEN commits):

1. **RED: failing tests for both tasks** - `a370d07` (test)
2. **Task 1: fix expired-SMT tagging bug + carry lifecycle fields (D-01..D-03a, D-06)** - `c290fd4` (feat)
3. **Task 2: add smt_block_size_atr + cisd_in_smt_block geometry columns (D-04/D-05)** - `28b4d9c` (feat)
4. **Fix: update pre-existing parity-lock fixtures for widened SMT event schema** - `4f256e6` (test)

**Plan metadata:** _(pending — this commit)_

## Files Created/Modified
- `cisd_data.py` - `_annotate_swing_smt_from_events` widened: three-way validity tag, lifecycle field carry-through, `smt_broke_in_window`, `smt_block_size_atr`, `cisd_in_smt_block`
- `tests/test_smt_invalidation.py` - new held-out test file locking validity semantics (D-01/D-02/D-03/D-03a), the broke-in-window flag (D-06), and geometry columns (D-04/D-05/D-05a)
- `tests/test_swing_smt_integration.py` - fixtures updated with the widened event schema (still-valid lifecycle defaults); one fixture also gained OHLC columns now required unconditionally by the geometry computation
- `tests/test_vectorization_parity.py` - Phase 08 parity-lock fixtures updated with shared `_event()` / `_ohlc_df()` helpers supplying the widened schema; all original behavior assertions unchanged

## Decisions Made
- D-01/D-02/D-03/D-03a implemented per CONTEXT.md exactly: `broken_ts` NaT or strictly `> t` keeps `w/ SMT`; `broken_ts == t` (or earlier) is `expired SMT`; validity never reads `status`; only the latest-created matched SMT is checked (no re-search rescue by an earlier still-valid event)
- D-04: ATR(14) evaluated at bar `t` (the documented default), reusing `compute_candle_size`'s `(high - low).rolling(14).mean()` one-liner verbatim; block extremes gathered from the matched event's `reference_timestamp` bar on the annotated instrument's own high/low via `reindex` (NaN on a miss propagates gracefully)
- D-05: `cisd_in_smt_block` requires both `open_t` and `close_t` (wicks excluded) inside `[block_low, block_high]` — full body containment
- D-05a: both geometry columns are populated for the entire matched population (`w/ SMT` and `expired SMT`), left at NaN/False for `no SMT`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, test breakage caused by this task's changes] Updated pre-existing Phase 08 parity-lock fixtures for the widened SMT event schema and unconditional OHLC/ATR computation**
- **Found during:** Task 1/Task 2 verification (running the wider test suite beyond the plan's named verify command)
- **Issue:** Widening `required_event_columns` (Task 1) and computing ATR/open/close arrays unconditionally (Task 2) broke `tests/test_swing_smt_integration.py` (3 tests) and `tests/test_vectorization_parity.py` (7 tests) — both pre-existing suites whose synthetic fixtures only supplied the original 4-column event schema and, in one case, a df with no OHLC columns at all
- **Fix:** Added the newly-required event columns (`reference_price`, `invalidation_asset`, `invalidation_direction`, `invalidation_level`, `broken_ts`, `status`, `reference_timestamp`) with still-valid defaults (`broken_ts=NaT`, `status="active"`) to each affected fixture, preserving every original assertion; added OHLC columns to one `test_swing_smt_integration.py` fixture and introduced shared `_event()` / `_ohlc_df()` helpers in `test_vectorization_parity.py` to keep the fix DRY
- **Files modified:** tests/test_swing_smt_integration.py, tests/test_vectorization_parity.py
- **Verification:** `.venv/bin/python -m pytest tests/test_smt_invalidation.py tests/test_swing_smt_integration.py tests/test_vectorization_parity.py -q` — 57 passed
- **Committed in:** c290fd4 (test_swing_smt_integration.py fix, part of Task 1 commit), 28b4d9c (OHLC fixture fix, part of Task 2 commit), 4f256e6 (test_vectorization_parity.py fix, standalone follow-up commit)

---

**Total deviations:** 1 auto-fixed (Rule 1, test-fixture updates caused directly by this task's schema widening)
**Impact on plan:** Necessary to keep the existing Phase 08 behavior-lock/parity suites green; no scope creep — only fixture schema was touched, no assertions changed, no production behavior for still-valid SMTs altered.

## Issues Encountered
None beyond the fixture-compatibility fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The widened annotation frame now carries every column Plan 09-02 needs: the three-way `swing_smt_tag`, lifecycle fields, `smt_broke_in_window`, `smt_block_size_atr`, and `cisd_in_smt_block`
- Plan 09-02 (consumer reporting: `compute_smt_cisd` three-way split + survived/broke sub-buckets, new `compute_smt_role`, geometry-bucket compute, chart/registry wiring) can proceed without further annotation-layer changes
- Plan 09-03 (methodology documentation, D-09/D-09a) is unblocked once 09-02's regenerated manifest numbers are available
- No blockers identified

---
*Phase: 09-smt-geometry-invalidation-honesty*
*Completed: 2026-07-12*

## Self-Check: PASSED

All created/modified files and referenced commit hashes verified present on disk / in git log.
