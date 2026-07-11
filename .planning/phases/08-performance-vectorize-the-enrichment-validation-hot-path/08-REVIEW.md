---
phase: 08-performance-vectorize-the-enrichment-validation-hot-path
reviewed: 2026-07-11T21:04:36Z
depth: quick
files_reviewed: 4
files_reviewed_list:
  - cisd_data.py
  - scripts/build_validation.py
  - tests/test_vectorization_parity.py
  - tests/test_perf_characterization.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-07-11T21:04:36Z
**Depth:** quick (pattern-focused, edge-case reasoning)
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 08 vectorizes the two enrichment hot functions (`_annotate_cisd_research`,
`_annotate_swing_smt_from_events`) and swaps the SMT-availability probe in
`build_validation.py`. I traced every vectorized column against the original
loop semantics with attention to the exact edge cases bit-equality-on-current-data
cannot catch (NaN-compares-False boundary guards, `searchsorted` tie-breaking,
`±inf` masking in the rolling sweep, `min_periods` boundaries, empty-frame paths).

**Correctness verdict: the rewrite is sound.** Every equivalence I checked holds:

- **Sweep** — `rolling(SWEEP_SWING_LOOKBACK).min().shift(1)` reproduces the prior-swing
  window `[p-LOOKBACK, p-1]` exactly; `±inf` masking of non-swing bars plus
  `np.isfinite(...)` correctly reproduces the original `prior_lows.empty` short-circuit;
  the `rolling(SWEEP_TOLERANCE).max() > 0` any() matches the `[idx-4, idx]` scan window.
- **FVG detection / hold** — `shift(±k)` NaN-at-boundary reproduces `_has_directional_fvg`'s
  `middle_idx<=0 / >=len-1` guards; `min_periods=FVG_HOLD_LOOKAHEAD` + `shift(-k)` makes
  `mid*_future_min_close` NaN in exactly the rows where the original returns `"none"`; the
  forward rolling min/max reduction is a faithful `.any()` over one-sided inequalities.
  Left-bar thresholds (`idx-1` for mid0, CISD bar itself for mid1) are correctly wired.
- **candle[1]/[2] follow-through** — NaN-compares-False on `shift(-1)/shift(-2)` reproduces
  the `idx+1<n / idx+2<n` guards; zero-gap and out-of-range both fall to `"flat"` as before.
- **Swing SMT** — stable `mergesort` + `searchsorted(side="right")-1` reproduces the
  "last matching event in ascending-created_ts, ties by original order, wins" overwrite
  semantic; inclusive `[lower_ts, ts]` window preserved; role assignment order preserved.
- Data cannot introduce NaN mid-frame (`resample_ohlcv(...).dropna(subset=["open"])`
  drops empty periods and OHLC are co-present), so the NaN-propagation-through-rolling
  divergence is not reachable on this pipeline.

The single finding worth acting on is a **maintainability/fragility hazard** that will
bite Phases 9-10, not a behavior defect.

## Warnings

### WR-01: Retired FVG/sweep helpers are now unused in production — silent-divergence trap

**File:** `cisd_data.py:120, 133, 159` (helpers) vs `cisd_data.py:191+` (inline vectorization)
**Issue:** `_has_directional_fvg`, `_classify_fvg_hold`, and `_has_directional_sweep` are
no longer called by any production code — `grep` confirms the only references in
`cisd_data.py`/`cisd_analysis.py`/`scripts/` are the docstring/comment mentions plus their
`__all__` re-export. `_annotate_cisd_research` now re-implements their exact semantics inline
with numpy/pandas. That leaves **two parallel implementations of the same logic** that can
drift independently. The parity test (`test_vectorization_parity.py`) locks hard-coded
*output values* of `_annotate_cisd_research`; it does **not** assert that the retired helpers
still agree with the inline form. So a future edit to (say) `_has_directional_sweep` — which
is still exported and unit-tested, making it look live — would change the helper's tests but
leave production untouched, or vice-versa, with no test failing to flag the split. For a
performance phase whose whole contract is "behavior-preserving," retaining a second,
now-authoritative-looking copy of the semantics is exactly the fragility Phases 9-10 build on.
**Fix:** Pick one of:
1. Add an equivalence test that runs both the retired helper and the inline result over a
   handful of randomized small frames and asserts they match (turns "they must stay in sync"
   from a comment into a gate); or
2. Add a one-line banner to each retired helper — e.g.
   `# REFERENCE/UNIT-TEST ONLY — production path is the inline vectorization in _annotate_cisd_research`
   so a future editor knows changing it does nothing to output; or
3. If nothing depends on the re-export, delete the helpers and their `__all__` entries to
   remove the dead second copy outright.

## Info

### IN-01: `_annotate_cisd_research` is now a single ~150-line dense array block

**File:** `cisd_data.py:182-350` (approx.)
**Issue:** The function is well-commented but long and flat — sweep, both FVG mids, hold
classification, and candle[1]/[2] features are all inline with many parallel `shift`/`np.where`
locals. Cyclomatic complexity is low (no branching), but the cognitive load and the number of
co-varying `shift(-k)`/`min_periods` offsets make it error-prone to extend. Not a defect.
**Fix:** Optional — extract cohesive sub-blocks into small vectorized privates
(`_vec_sweep(...)`, `_vec_fvg_hold(...)`) so each equivalence is independently testable and the
top-level function reads as a pipeline. Would also give WR-01's equivalence test a natural seam.

### IN-02: `build_validation.py` SMT probe swap — verified equivalent, one behavioral nuance recorded

**File:** `scripts/build_validation.py:629, 667`
**Issue (informational, no defect):** Replacing the discarded
`prepare_pair(..., with_swing_smt=True)` probe with `_load_scan_smts_historical()` preserves
the two properties that matter: it raises exactly `FileNotFoundError`/`ImportError` (the caught
set), and it performs the one-time `sys.path.insert(0, ...)` side-effect before the loop's real
`prepare_pair(..., with_swing_smt=with_smt)`. The one nuance: the old probe would also *execute*
the full scan+annotate, so an SMT runtime error (not `FileNotFoundError`/`ImportError`) surfaced
*at probe time*; now it surfaces later at the first real `prepare_pair` call instead. Net effect
is identical (same uncaught exception propagates, nothing newly swallowed) — recorded only so
the timing shift is on the record. This is also strictly less wasted compute.
**Fix:** None required.

---

_Reviewed: 2026-07-11T21:04:36Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
