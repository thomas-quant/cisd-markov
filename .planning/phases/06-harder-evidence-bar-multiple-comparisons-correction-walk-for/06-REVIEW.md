---
phase: 06-harder-evidence-bar-multiple-comparisons-correction-walk-for
reviewed: 2026-07-10T00:00:00Z
depth: quick
files_reviewed: 4
files_reviewed_list:
  - cisd_analysis.py
  - cisd_data.py
  - scripts/build_validation.py
  - tests/test_validation_harness.py
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-07-10T00:00:00Z
**Depth:** quick
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the two new features added in this phase: (1) per-bucket significance
testing (`p_value_vs_half`) + Benjamini-Hochberg FDR correction (`bh_correct`,
`apply_bh_correction`), and (2) walk-forward rolling-window validation
(`slice_fold`, `evaluate_fold`, `walk_forward_verdict`, `build_walkforward_rows`),
plus the `WALK_FORWARD_FOLDS` re-export wiring between `cisd_data.py` and
`cisd_analysis.py`.

**Re-export wiring (explicitly requested check):** `WALK_FORWARD_FOLDS` is
present in `cisd_data.py`'s `__all__` (`cisd_data.py:463`), imported explicitly
in `cisd_analysis.py`'s `from cisd_data import (...)` block (`cisd_analysis.py:40`),
and re-listed in `cisd_analysis.py`'s own `__all__` (`cisd_analysis.py:145`).
`scripts/build_validation.py` imports it directly from `cisd_analysis`
(`scripts/build_validation.py:18`) and `tests/test_validation_harness.py`
imports it the same way (`tests/test_validation_harness.py:15`). All four
files agree — no broken import chain.

**Sacred OOS slice (explicitly requested check):** `slice_fold()` always
derives both `train` and `test` from `slice_df(df, oos=False)` first
(`scripts/build_validation.py:383`), so even when `test_end` is a date at or
after `OOS_START` (the last fold's `test_end` is literally `OOS_START`), the
result is clamped to `df.index < OOS_START`. `build_walkforward_rows()` never
calls `slice_df(df, oos=True)`. Traced this by hand across all 4 fold
boundaries and confirmed with the existing test
`test_slice_fold_clamps_to_discovery_even_if_test_end_after_oos` (passes).
The `--walk-forward` CLI branch in `main()` also never touches
`_OOS_BANNER` or the discovery/oos manifest paths — it writes only to
`validation_manifest_walkforward.csv` via `_manifest_path("walkforward")`,
which does not collide with `validation_manifest_discovery.csv` /
`validation_manifest_oos.csv`.

**Correctness spot-checks performed:** manually traced the BH step-up
algorithm (cutoff-rank search + monotone q-value walk) against the
`bh_correct` docstring's formula and against `test_bh_correct_known_value`;
verified `p_value_vs_half(100, 60) ≈ 0.0455` numerically; ran
`tests/test_validation_harness.py` (43/43 pass). No incorrect behavior found
in the significance-testing or walk-forward logic itself. The findings below
are quality/maintainability issues, not correctness bugs.

## Warnings

### WR-01: Duplicated SMT-availability probe block in `main()`

**File:** `scripts/build_validation.py:626-634` and `scripts/build_validation.py:667-673`
**Issue:** The `--walk-forward` branch and the discovery/oos branch of `main()`
each contain a near-identical block that resamples the first timeframe, calls
`prepare_pair(..., with_swing_smt=True)` purely to detect whether the SMT
package is importable, and sets a `with_smt` flag in an
`except (FileNotFoundError, ImportError)` handler:
```python
try:
    _first_rule = next(iter(TIMEFRAMES.values()))
    prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], _first_rule, with_swing_smt=True)
    with_smt = True
except (FileNotFoundError, ImportError) as exc:
    print(f"[warn] SMT unavailable ({exc}); swing SMT columns will be absent")
    with_smt = False
```
This duplication means any future fix to the SMT-detection logic (e.g.
tightening the exception types, or avoiding the wasted full-pipeline
recomputation) has to be applied in two places, and the two copies can
silently drift apart over time.
**Fix:** Extract a `_detect_smt_availability(dfs_1m) -> bool` helper and call
it from both branches of `main()`.

## Info

### IN-01: Fold-index docstring is ambiguous about 0- vs 1-based `WALK_FORWARD_FOLDS` indexing

**File:** `scripts/build_validation.py:493-495`
**Issue:** The docstring for `build_walkforward_rows` states "fold i's test
chunk is `[WALK_FORWARD_FOLDS[i], next_boundary)`", but the actual code's
`fold_index` is 1-based (`enumerate(fold_specs, start=1)`) while
`WALK_FORWARD_FOLDS` is a plain 0-indexed tuple, so "fold 1"'s test chunk is
actually `[WALK_FORWARD_FOLDS[0], WALK_FORWARD_FOLDS[1])`, not
`[WALK_FORWARD_FOLDS[1], ...)`. The behavior itself is correct (verified by
`test_build_walkforward_rows_schema_and_verdicts` and manual trace of
`fold_boundaries`/`fold_specs`), but the prose is confusing to a future reader
trying to map `fold_index` back to `WALK_FORWARD_FOLDS` positions.
**Fix:** Reword to "fold `fold_index`'s test chunk is
`[fold_boundaries[fold_index-1], fold_boundaries[fold_index])`" or otherwise
clarify the index base explicitly.

### IN-02: BH correction operates on already-rounded (6dp) p-values, not raw p-values

**File:** `scripts/build_validation.py:235` (rounding) and `scripts/build_validation.py:334` (consumption)
**Issue:** `emit()` stores `p_value` rounded to 6 decimal places into each
manifest row; `apply_bh_correction()` then reads `rows[i]["p_value"]` (the
rounded value) as input to `bh_correct()`. In the vanishingly rare case where
two distinct raw p-values round to the same 6dp value that straddles a BH
rank boundary, the reported `bh_rank`/`bh_significant` could differ by one
rank from what a correction computed on unrounded p-values would produce.
This is a second-order precision concern, not a logic bug, but worth noting
since MHT correction rank ordering is exactly the kind of place where silent
precision loss can matter.
**Fix:** Either compute BH correction from unrounded p-values (store both a
raw and a display-rounded copy) or explicitly document that the 6dp rounding
is intentional and considered negligible for this dataset's p-value
distribution.

### IN-03: `MANIFEST_PATH` constant is dead code (pre-existing, unrelated to this phase's diff)

**File:** `scripts/build_validation.py:23`
**Issue:** `MANIFEST_PATH = REPO_ROOT / "output" / "validation_manifest.csv"  # legacy name (kept for import compat)`
is defined but never referenced anywhere else in the file, and no other
module in the repo imports it (`grep` across the repo found zero
consumers). This predates the phase-06 diff, but since the file was in
scope for this review it's worth flagging as unused/dead code that can be
removed.
**Fix:** Delete the constant, or if it truly exists for external import
compatibility, add a comment naming the consumer that requires it.

---

_Reviewed: 2026-07-10T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
