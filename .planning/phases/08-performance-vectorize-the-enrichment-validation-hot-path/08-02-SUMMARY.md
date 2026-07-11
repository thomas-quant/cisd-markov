---
phase: 08-performance-vectorize-the-enrichment-validation-hot-path
plan: 02
subsystem: enrichment-pipeline
tags: [pandas, numpy, vectorization, performance, behavior-preserving]

requires:
  - phase: 08-performance-vectorize-the-enrichment-validation-hot-path
    plan: 01
    provides: "tests/test_vectorization_parity.py (24 synthetic parity locks), tests/golden/manifest_*_golden.csv.gz, docs/perf_phase08.md 'before' baseline — the behavior-lock this plan's rewrite must keep green."
provides:
  - "cisd_data.py::_annotate_cisd_research rewritten as whole-frame numpy/pandas expressions (no per-event Python loop), producing byte-identical enrichment columns to the pre-change implementation."
affects: [08-03]

tech-stack:
  added: []
  patterns:
    - "'Any value in a future/past window crosses a one-sided threshold' is exactly equivalent to 'the window's min (for < checks) or max (for > checks) crosses that threshold' — this reduction turns the FVG-hold any()-over-window scan and the sweep any()-over-window scan into rolling min/max reductions, eliminating the per-event nested window loop entirely."
    - "Boundary/out-of-range guards (idx==0, idx+1>=n, idx+2>=n, middle_idx<=0, middle_idx>=len-1) are reproduced for free via shift(k)-introduced NaN plus 'NaN compares False' numpy semantics, instead of explicit if-guards — verified this does not raise RuntimeWarning even under -W error in this numpy/pandas version."
    - "Masking non-qualifying rows to +inf/-inf before a rolling min/max (then checking np.isfinite on the result) distinguishes 'no swing point yet in window' (the original's `prior_lows.empty` short-circuit) from a legitimate crossed threshold — required to avoid rolling-min-of-all-inf being misread as 'sweep triggered'."

key-files:
  created: []
  modified:
    - cisd_data.py

key-decisions:
  - "Kept `_compute_three_bar_swings`, `_has_directional_fvg`, `_classify_fvg_hold`, `_has_directional_sweep` completely untouched — they are independently unit-tested (test_research_extensions.py) and part of the cisd_data.__all__ / cisd_analysis re-export surface. `_annotate_cisd_research` no longer calls them, but its vectorized logic reproduces their exact documented semantics (verified by the same test suite, which exercises both the helpers directly and the rewritten function)."
  - "The sweep computation was fully vectorized (not left as a bounded per-window loop, though the plan permitted that fallback) via a two-stage rolling reduction: per-bar 'does this bar's low/high cross the rolling-min/max of prior swing extremes in a trailing SWEEP_SWING_LOOKBACK window' trigger, then a rolling-any over a trailing SWEEP_TOLERANCE window at each CISD bar. Verified by hand-tracing the existing test_has_dir_sweep_true_when_prior_swing_low_exceeded_in_window fixture before running it, matching the exact True result at the exact window boundary."

requirements-completed: []  # PERF-01 remains open until Plan 08-03 lands the SMT-side vectorization and the authoritative 3-manifest bit-equality proof.

coverage:
  - id: D1
    description: "_annotate_cisd_research vectorized; the 24 synthetic parity locks from Plan 08-01 plus the 66-assertion research-extensions suite plus core-compute plus determinism suites (101 tests total) pass unchanged."
    requirement: PERF-01
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/test_vectorization_parity.py tests/test_research_extensions.py tests/test_core_compute.py tests/test_determinism.py -q — 101 passed"
        status: pass
    human_judgment: false
  - id: D2
    description: "Real-data non-SMT characterization rates (baseline/wick/combined/significance) unchanged after the rewrite."
    requirement: PERF-01
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/test_characterization.py -q -k \"not smt\" — 4 passed, 1 deselected in 288.60s"
        status: pass
    human_judgment: false
  - id: D3
    description: "Public import surface (cisd_analysis._annotate_cisd_research, .prepare) intact; no signature/export changes."
    requirement: PERF-01
    verification:
      - kind: unit
        ref: "python -c \"import cisd_analysis; assert hasattr(cisd_analysis,'_annotate_cisd_research') and hasattr(cisd_analysis,'prepare')\" — exit 0"
        status: pass
    human_judgment: false

duration: "~55min"
completed: 2026-07-11
status: complete
---

# Phase 8 Plan 2: Vectorize `_annotate_cisd_research` Summary

**Rewrote the primary single-instrument enrichment hot spot from a per-event Python loop into whole-frame numpy/pandas expressions — turning both the `[t-4,t]` sweep scan and the FVG hold/fail classification's `any()`-over-future-window checks into rolling min/max reductions — with zero change to any of the 14 annotated columns, proven by 101 fast tests plus the real-data non-SMT characterization suite.**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-07-11 (session start)
- **Completed:** 2026-07-11
- **Tasks:** 1/1 completed
- **Files modified:** 1 (`cisd_data.py`)

## Accomplishments

- Rewrote `_annotate_cisd_research` (cisd_data.py) to compute all 14 annotated columns via vectorized array operations instead of a `for idx in event_pos` Python loop with nested `.iloc`/`.iat` window scans:
  - **Swing flags** (`prev_bar_is_dir_swing`, `cisd_bar_is_dir_swing`): direction-selected via `np.where(is_bullish, ..., np.where(is_bearish, ..., False))` over `swing_low`/`swing_high` and their `.shift(1)` for the prev-bar case.
  - **`has_dir_sweep`**: re-expressed the nested "for each candidate sweep bar in `[idx-4, idx]`, look back up to 20 bars for a swing extreme it crosses" scan as (1) a per-bar trigger computed via `+inf`/`-inf`-masked rolling(20).min()/max() shifted by 1 (so the current bar is excluded and non-swing bars never win the reduction), gated by `np.isfinite` to distinguish "no swing point yet in window" from a real crossing, then (2) a rolling(5)-any over that trigger array to answer "did any bar in the trailing sweep-tolerance window trigger". Hand-traced against the existing `test_has_dir_sweep_true_when_prior_swing_low_exceeded_in_window` fixture (10-bar synthetic frame) before running it, confirming the exact `True` at `index[7]` and the exact window boundary semantics.
  - **`has_dir_fvg_mid0`/`mid1`**: `_has_directional_fvg`'s `left.high < right.low` (bullish) / `left.low > right.high` (bearish) comparisons reproduced via `.shift(1)`/`.shift(-1)` (mid0, left=idx-1/right=idx+1) and `.shift(-2)` (mid1, left=idx itself/right=idx+2) — the `middle_idx<=0`/`>=len-1` boundary guard falls out for free because `shift()` introduces NaN at those positions and NaN comparisons evaluate `False` in numpy (verified this raises no `RuntimeWarning` even under `-W error`).
  - **`fvg_mid0_hold_close_near`/`wick_far`, `fvg_mid1_hold_close_near`/`wick_far`**: the key insight — `_classify_fvg_hold`'s `any(future_bars violate threshold)` is a one-sided inequality (`<` or `>`), so it is exactly equivalent to comparing the future window's **min** (for `<` checks) or **max** (for `>` checks) against the threshold. Computed once via `rolling(FVG_HOLD_LOOKAHEAD, min_periods=FVG_HOLD_LOOKAHEAD).min()/.max()` on `close`/`low`/`high`, then `.shift(-k)` (k=10 for mid0, k=11 for mid1) brings the future-window reduction back to the CISD bar's position; `min_periods=FVG_HOLD_LOOKAHEAD` naturally produces NaN when the window doesn't fit, mapped to `"none"` via `np.isfinite`.
  - **`candle1_close_dir`, `candle1_past_candle0_wick`, `candle1_failed_followthrough`, `candle2_gap_dir`, `candle2_past_candle1_wick`**: rebuilt from `.shift(-1)`/`.shift(-2)` of `open`/`high`/`low`/`close`, with the same NaN-compares-False property reproducing the original's `idx+1 < n` / `idx+2 < n` guards (including the `gap == 0` and `gap is NaN` cases both correctly falling through to `"flat"`).
- Left `_compute_three_bar_swings`, `_has_directional_fvg`, `_classify_fvg_hold`, `_has_directional_sweep` completely unmodified — `_annotate_cisd_research` no longer calls them (it inlines their vectorized equivalents), but all four remain exported and independently tested by `tests/test_research_extensions.py`.
- Explicit `.astype(bool)` casts on all boolean-column assignments to guarantee `dtype == bool` (not `object`), satisfying `test_research_annotation_flags_use_boolean_dtype`.
- Verified column append order, names, and default values (`False`/`"none"`/`"against"`/`"flat"`) are unchanged — confirmed via the full parity + research-extensions + core-compute + determinism suite (101 passed) and the real-data non-SMT characterization suite (4 passed).

## Task Commits

1. **Task 1: Vectorize `_annotate_cisd_research` preserving every annotated column** - `d41eb99` (perf)

## Files Created/Modified

- `cisd_data.py` - `_annotate_cisd_research` rewritten as vectorized numpy/pandas expressions (246 insertions, 117 deletions); no other functions changed.

## Decisions Made

- Fully vectorized the sweep computation (two-stage rolling reduction) rather than falling back to the plan's permitted "bounded vectorized-per-window form", since the equivalence (per-bar trigger + rolling-any) could be verified exactly against the existing hand-traced test fixture without edge-case ambiguity.
- Left the four private helper functions (`_compute_three_bar_swings`, `_has_directional_fvg`, `_classify_fvg_hold`, `_has_directional_sweep`) untouched rather than vectorizing or removing them, since they are directly unit-tested and exported; `_annotate_cisd_research` reproduces their semantics inline instead of calling them, avoiding any risk of subtly changing their independently-tested behavior.

## Deviations from Plan

None. The plan explicitly gave executor discretion on the exact vectorization technique (shift/rolling/searchsorted/np.select all acceptable, sweep may retain a bounded per-window form) — the fully-vectorized rolling-reduction approach taken here is within that discretion, not a deviation.

## Issues Encountered

None. All four required verification commands passed on the first attempt:
1. `.venv/bin/python -m pytest tests/test_vectorization_parity.py tests/test_research_extensions.py tests/test_core_compute.py tests/test_determinism.py -q` → **101 passed** (7.60s)
2. `.venv/bin/python -m pytest tests/test_characterization.py -q -k "not smt"` → **4 passed, 1 deselected** (288.60s / ~4min48s) — real data was present in this environment so this ran (did not skip); non-SMT enrichment rates confirmed unchanged.
3. `.venv/bin/python -c "import cisd_analysis; assert hasattr(cisd_analysis,'_annotate_cisd_research') and hasattr(cisd_analysis,'prepare')"` → exit 0.
4. `_annotate_cisd_research` still appends exactly the 14 documented columns with the same names/defaults — confirmed by the passing test suite (which asserts column presence, dtype, and default values).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `_annotate_cisd_research` is fully vectorized and proven behavior-identical by every fast/medium check this plan requires. Its private helper functions remain untouched and independently tested.
- `_annotate_swing_smt_from_events` (the other Phase 8 hot spot) is still the original per-event loop — untouched per this plan's scope, deferred to Plan 08-03.
- Plan 08-03 must: (1) vectorize `_annotate_swing_smt_from_events`, (2) run the authoritative `CISD_PERF_CHAR=1 .venv/bin/python -m pytest tests/test_perf_characterization.py -q` end-to-end 3-manifest bit-equality gate covering BOTH vectorized functions together, (3) measure the "after" wall-clock using the same 3-concurrent-process methodology as the "before" baseline in `docs/perf_phase08.md`, and (4) mark PERF-01 complete once both functions are vectorized and the bit-equality proof passes.
- No blockers.

---
*Phase: 08-performance-vectorize-the-enrichment-validation-hot-path*
*Completed: 2026-07-11*

## Self-Check: PASSED

Verified `cisd_data.py` modification present via `git show d41eb99 --stat`. Verified commit `d41eb99` present in `git log --oneline --all`. Verified all 101 tests in the fast/medium suite pass and the non-SMT characterization suite (4 tests) passes, both re-confirmed via the exact commands recorded above.
