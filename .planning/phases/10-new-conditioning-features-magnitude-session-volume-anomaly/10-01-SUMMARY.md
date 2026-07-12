---
phase: 10-new-conditioning-features-magnitude-session-volume-anomaly
plan: 01
subsystem: research-annotation
tags: [pandas, numpy, vectorized-annotation, atr, session, rvol, cisd]

requires:
  - phase: 08-performance-vectorize-the-enrichment-validation-hot-path
    provides: fully vectorized `_annotate_cisd_research` (no per-row Python loop) as the insertion site for new columns
  - phase: 09-smt-geometry-invalidation-honesty
    provides: precedent for adding an ATR-gated magnitude column (`smt_block_size_atr`) inside the same annotation function
provides:
  - 9 new annotation columns on `prepare()` output (magnitude, session, volume-anomaly)
  - 4 new frozen constants (RTH_OPEN_START_MIN/RTH_OPEN_END_MIN/RTH_END_MIN/RVOL_SLOT_K)
  - frozen sweep-anchoring and mid0-priority-FVG operationalization decisions for Plan 02/03's compute layer
affects: [10-02-PLAN, 10-03-PLAN, 10-04-PLAN]

tech-stack:
  added: []
  patterns:
    - "ATR(14) computed once per magnitude block, reused by every ATR-normalized column, matching compute_candle_size's (high-low).rolling(14).mean() verbatim"
    - "safe-divisor guard (np.where(cond, arr, np.nan) before division) to avoid RuntimeWarning: divide by zero, applied to every new ratio column"
    - "groupby(minute_of_day).transform(lambda s: s.shift(1).rolling(K, min_periods=K).agg) as the vectorized same-time-of-day-slot trailing baseline idiom (new to this module)"
    - "graceful degrade-to-NaN when an optional source column (volume) is absent from a minimal test fixture, mirroring the SMT-columns-absent convention"

key-files:
  created:
    - tests/test_conditioning_features.py
  modified:
    - cisd_data.py

key-decisions:
  - "Sweep-anchoring (frozen, D-06a resolution): sweep_depth_atr/swept_level are measured at the CISD bar t against the nearest prior swing extreme as-of-t (roll_min_prior_swing_low/roll_max_prior_swing_high), NOT the specific sweep_idx within the trailing SWEEP_TOLERANCE window — swings move slowly relative to the 5-bar tolerance so this equals the triggered level in the overwhelming majority of cases while staying fully vectorized."
  - "mid0-priority FVG union (frozen, D-06a resolution): where both a mid0 and mid1 FVG exist at the same CISD bar, fvg_gap_width/fvg_size_atr take the mid0 (CISD-bar) gap — a single flat population for Plan 02's compute_fvg_size to consume via the generic manifest dispatch."
  - "wick_distance_atr's prev_high/prev_low are derived locally via high_s/low_s.shift(1) instead of read from an annotated[\"prev_high\"]/[\"prev_low\"] column, keeping _annotate_cisd_research self-contained (matches prepare()'s own definition bit-for-bit) — several pre-existing behavior-lock tests call the function directly on a minimal frame without those columns."
  - "vol_per_range/rvol/volume_zscore guard on \"volume\" in annotated.columns and degrade to NaN when absent, for the same minimal-fixture-compatibility reason."
  - "session_tag stays TF-agnostic (populated on every frame/timeframe) — the D-02 intraday-only restriction is deferred to the registry/dispatch layer in Plan 03 (ANALYSIS_META applies_to), per D-14's preferred mechanism."

requirements-completed: [RES-07]

coverage:
  - id: D1
    description: "wick_distance_atr: signed ATR-normalized distance past/within the prior bar's wick, defined over ALL CISDs with a value <= 0 at exactly the within-wick boundary"
    requirement: "RES-07"
    verification:
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_wick_distance_atr_signed_past_vs_within_wick"
        status: pass
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_wick_distance_atr_bearish_mirror"
        status: pass
    human_judgment: false
  - id: D2
    description: "swept_level + sweep_depth_atr: pierced swing level and ATR-normalized penetration depth, NaN off the has_dir_sweep population"
    requirement: "RES-07"
    verification:
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_sweep_and_fvg_magnitudes_nan_off_population"
        status: pass
    human_judgment: false
  - id: D3
    description: "fvg_gap_width + fvg_size_atr: mid0-priority FVG gap width and its ATR-normalized size, NaN off the has_dir_fvg_mid0/mid1 population"
    requirement: "RES-07"
    verification:
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_sweep_and_fvg_magnitudes_nan_off_population"
        status: pass
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_magnitude_columns_present_and_float_dtype"
        status: pass
    human_judgment: false
  - id: D4
    description: "session_tag: every bar tagged exactly one of rth_open/rth/overnight from the frozen RTH_OPEN_START_MIN/RTH_OPEN_END_MIN/RTH_END_MIN minute-of-day constants, no timezone/DST math"
    requirement: "RES-07"
    verification:
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_session_tag_partitions_every_bar"
        status: pass
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_frozen_session_constants"
        status: pass
    human_judgment: false
  - id: D5
    description: "vol_per_range/rvol/volume_zscore: effort-vs-result ratio and same-time-of-day-slot trailing RVOL/z-score baseline, frozen K=20, warm-up NaN, degenerates to a plain trailing baseline on a single-slot (Daily) frame"
    requirement: "RES-07"
    verification:
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_vol_per_range_matches_volume_over_range_and_nan_when_flat"
        status: pass
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_rvol_and_zscore_slot_baseline_trailing_and_warmup_nan"
        status: pass
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_volume_columns_present_and_float_dtype"
        status: pass
    human_judgment: false
  - id: D6
    description: "All new columns computed vectorized (no re-introduced per-row Python loop) and existing behavior-lock tests (parity + characterization) still pass byte-for-byte"
    requirement: "RES-07"
    verification:
      - kind: integration
        ref: "tests/test_vectorization_parity.py + tests/test_characterization.py (29 tests)"
        status: pass
      - kind: integration
        ref: "full non-heavy suite (236 tests, tests/ excluding test_vectorization_parity.py/test_characterization.py/test_perf_characterization.py)"
        status: pass
    human_judgment: false

duration: 50min
completed: 2026-07-12
status: complete
---

# Phase 10 Plan 01: Conditioning-Feature Annotation Columns Summary

**Added 9 vectorized annotation columns (signed wick distance, sweep depth + pierced level, FVG size + gap width, session tag, effort-vs-result, slot-normalized RVOL/z-score) and 4 frozen constants to `_annotate_cisd_research`, discovering and fixing a real regression where the new code broke 17 pre-existing behavior-lock tests that call the function on minimal fixtures.**

## Performance

- **Duration:** ~50 min (includes ~21 min of background test-suite regression runs)
- **Completed:** 2026-07-12
- **Tasks:** 3 (all `type="auto" tdd="true"`)
- **Files modified:** 2 (`cisd_data.py`, `tests/test_conditioning_features.py`)

## Accomplishments

- `wick_distance_atr` — signed, ALL CISDs: `(close-prev_high)/ATR` bullish, `(prev_low-close)/ATR` bearish, subsuming the binary `compute_wick` past/within split with a bin edge exactly at 0 (D-05/D-06)
- `swept_level` + `sweep_depth_atr` — reuse the existing `roll_min_prior_swing_low`/`roll_max_prior_swing_high` rolling arrays, gated on `has_dir_sweep`, anchored at the CISD bar `t` against the nearest prior swing extreme as-of-`t` (frozen sweep-anchoring decision, D-06a)
- `fvg_gap_width` + `fvg_size_atr` — reuse the existing FVG mid0/mid1 boundary arrays, gated on `has_dir_fvg_mid0`/`mid1`, mid0-priority union when both exist (frozen mid0-priority decision, D-06a)
- `session_tag` — `rth_open`/`rth`/`overnight` from three frozen minute-of-day constants on the tz-naive ET index, TF-agnostic (D-01/D-02a/D-03)
- `vol_per_range` — within-bar effort-vs-result ratio, baseline-free (D-07)
- `rvol` / `volume_zscore` — same-time-of-day-slot trailing baseline via `groupby(minute_of_day).transform(shift(1).rolling(K=20))`, degenerates to a plain trailing baseline on Daily's single slot (D-08)
- All 9 columns computed with whole-frame numpy/pandas operations only — zero per-row Python loop reintroduced into `_annotate_cisd_research`
- Full verification block from the plan passes: `prepare()` output on a real 1H NQ frame carries all 9 columns and `session_tag` has exactly `{overnight, rth, rth_open}`

## Task Commits

Each task was committed atomically (TDD RED gate first, then per-task GREEN commits, then a fix commit for the regression found during full-suite verification):

1. **RED gate: failing tests** - `5fb93a1` (test)
2. **Task 1: Magnitude annotation columns** - `5b0fad8` (feat)
3. **Task 2: Session tag annotation** - `8b80fdd` (feat)
4. **Task 3: Volume-anomaly annotation** - `0a0277b` (feat)
5. **Regression fix (Rule 1 — bug)** - `fb9f8a4` (fix)

_Note: TDD RED commit covers all three tasks' tests (single test file extended per-task); each task's GREEN commit turns its subset of tests passing while leaving later constants imported locally inside their own test functions so `-k` filtering works before later tasks land._

## Files Created/Modified

- `cisd_data.py` — 9 new columns + 4 new frozen constants added to `_annotate_cisd_research` and the Configuration block; `__all__` extended with the 3 new constants
- `tests/test_conditioning_features.py` — synthetic-fixture tests for all 9 columns and 4 constants (no data files or SMT package required)

## Decisions Made

- **Sweep-anchoring (frozen, D-06a):** `sweep_depth_atr`/`swept_level` measured at the CISD bar `t` against the nearest prior swing extreme as-of-`t`, not the specific triggering `sweep_idx` inside the 5-bar `SWEEP_TOLERANCE` window — this equals the triggered level in the overwhelming majority of cases and stays fully vectorized.
- **mid0-priority FVG union (frozen, D-06a):** where both a mid0 and a mid1 FVG exist at the same CISD bar, `fvg_gap_width`/`fvg_size_atr` take the mid0 (CISD-bar) gap, keeping a single flat population for Plan 02's `compute_fvg_size`.
- **session_tag stays TF-agnostic:** the D-02 "15min/1H only" restriction is deferred entirely to Plan 03's `ANALYSIS_META.applies_to` registry mechanism (D-14) — the annotation itself populates `session_tag` on every timeframe.
- **prev_high/prev_low derived locally, not read from a column** (see Deviations below) — this became the frozen contract going forward: any consumer relying on `wick_distance_atr` gets the value derived from the frame's own `high`/`low`, never from an external `prev_high`/`prev_low` column that might be stale or absent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `wick_distance_atr` broke 17 pre-existing behavior-lock tests by reading a `prev_high`/`prev_low` column that doesn't exist on minimal test fixtures**
- **Found during:** Task 1 verification (running the plan's mandated `tests/test_vectorization_parity.py` + `tests/test_characterization.py` behavior-lock check)
- **Issue:** The plan's action text instructed pulling `prev_high_arr = annotated["prev_high"].to_numpy(...)` directly from the frame. Several pre-existing tests in `tests/test_vectorization_parity.py` call `_annotate_cisd_research` directly on a minimal `open`/`high`/`low`/`close`/`cisd_type` frame (no `prev_high`/`prev_low` columns — those are normally set by `prepare()` before calling this function, but these tests bypass `prepare()`). The unconditional column read raised `KeyError: 'prev_high'`, breaking 17 previously-passing tests.
- **Fix:** Derive `prev_high_arr`/`prev_low_arr` locally from `high_s.shift(1)`/`low_s.shift(1)` (already-computed Series inside the function) — bit-identical to what `prepare()` would have set, but self-contained and requiring no external column.
- **Files modified:** `cisd_data.py`
- **Verification:** `tests/test_vectorization_parity.py` + `tests/test_characterization.py` (29 tests) pass; full non-heavy suite (236 tests) passes.
- **Committed in:** `fb9f8a4`

**2. [Rule 1 - Bug] `vol_per_range`/`rvol`/`volume_zscore` broke the same 17 tests a second time by reading a `volume` column absent from the same minimal fixtures**
- **Found during:** Same verification pass, second failure surfaced after fixing #1 (KeyError moved from `prev_high` to `volume`)
- **Issue:** The same minimal fixtures in `tests/test_vectorization_parity.py` have no `volume` column either. The unconditional `annotated["volume"].to_numpy(...)` raised `KeyError: 'volume'`.
- **Fix:** Guard the entire volume-anomaly block on `"volume" in annotated.columns`; degrade to an all-`NaN` array of the correct length when absent, mirroring the existing SMT-columns-absent graceful-degradation convention already used elsewhere in this module.
- **Files modified:** `cisd_data.py`
- **Verification:** Same as above.
- **Committed in:** `fb9f8a4`

**3. [Rule 1 - Bug] Divide-by-zero `RuntimeWarning` on flat-range/flat-volume synthetic rows**
- **Found during:** Task 3, running the new synthetic tests (`test_vol_per_range_matches_volume_over_range_and_nan_when_flat`, `test_rvol_and_zscore_slot_baseline_trailing_and_warmup_nan`)
- **Issue:** `vol_per_range = np.where(rng > 0, vol_arr / rng, np.nan)` still evaluates `vol_arr / rng` elementwise even where `rng == 0`, triggering `RuntimeWarning: divide by zero encountered in divide` (values discarded via `np.where` but the warning still fires). Same issue for `rvol`/`volume_zscore` when `slot_std == 0` (e.g. constant volume in a warm-up window).
- **Fix:** Added `safe_rng`/`safe_slot_mean`/`safe_slot_std` guards (`np.where(cond, arr, np.nan)` before dividing), matching the existing `safe_atr` convention already used for the magnitude columns.
- **Files modified:** `cisd_data.py`
- **Verification:** `tests/test_conditioning_features.py` runs with zero warnings.
- **Committed in:** `0a0277b` (folded into Task 3's commit, found and fixed before that commit was made)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bugs found during the plan's own mandated verification steps)
**Impact on plan:** All three were correctness/compatibility bugs in the new code, not scope creep. No existing published behavior changed — the fixes made the new columns self-contained rather than altering any output value. Full behavior-lock suite confirms zero drift.

## Issues Encountered

The plan's own `<read_first>` block for Task 1 instructed reading `prev_high`/`prev_low` directly from the annotated frame; this is correct for the real `prepare()` pipeline but not for the subset of pre-existing tests that call `_annotate_cisd_research` in isolation. Resolved by deriving both values locally instead of depending on the plan's literal instruction — same numeric result, broader compatibility.

## Next Phase Readiness

- All 9 columns and 4 constants are live on `prepare()` output for every timeframe; Plan 02 can now write `compute_wick_distance`, `compute_sweep_depth`, `compute_fvg_size`, `compute_effort_result`, `compute_rvol`, `compute_volume_zscore` reading these columns directly, with the frozen sweep-anchoring and mid0-priority-FVG operationalizations already locked in.
- Plan 03 can register `compute_session` + the `ANALYSIS_META.applies_to` TF-scoping mechanism (D-14) — `session_tag` is already populated on every frame, TF-agnostic, ready for the intraday-only registry restriction.
- No blockers. The behavior-lock regression found and fixed during this plan's own verification means Plan 02/03/04's later full-suite regens should not encounter the same class of bug (both `prev_high`/`prev_low` derivation and the `volume`-absence guard are now self-contained).

---
*Phase: 10-new-conditioning-features-magnitude-session-volume-anomaly*
*Completed: 2026-07-12*

## Self-Check: PASSED

- FOUND: `cisd_data.py`
- FOUND: `tests/test_conditioning_features.py`
- FOUND: `.planning/phases/10-new-conditioning-features-magnitude-session-volume-anomaly/10-01-SUMMARY.md`
- FOUND commit: `5fb93a1` (test: RED gate)
- FOUND commit: `5b0fad8` (feat: Task 1 magnitude columns)
- FOUND commit: `8b80fdd` (feat: Task 2 session_tag)
- FOUND commit: `0a0277b` (feat: Task 3 volume anomaly)
- FOUND commit: `fb9f8a4` (fix: regression fix)
