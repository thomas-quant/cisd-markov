---
phase: 04-test-gated-modular-refactor
reviewed: 2026-06-14T00:00:00Z
depth: quick
files_reviewed: 4
files_reviewed_list:
  - cisd_analysis.py
  - cisd_barriers.py
  - cisd_charts.py
  - cisd_data.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-06-14T00:00:00Z
**Depth:** quick (expanded with targeted standard-depth verification for regression risk)
**Files Reviewed:** 4
**Status:** issues_found

## Summary

This phase split the 1,380-line `cisd_analysis.py` god-file into three focused
modules (`cisd_data`, `cisd_barriers`, `cisd_charts`) plus a re-export shim, and
vectorized the hot event-detection loops (`iterrows`/`get_loc` → `np.flatnonzero`).

The refactor is **correctness-clean**. I independently verified:

- **No behavior regression from vectorization.** Each rewritten compute function
  (`compute_basic`, `compute_wick`, `compute_significance`, `compute_smt_cisd`,
  and the FVG/sweep/swing family) was diffed against the pre-split original at
  `b5a988b^`. The `np.flatnonzero(pd.notna(df["cisd_type"]))` event-position
  pattern was confirmed to correctly detect `None` sentinels produced by
  `np.select(..., default=None)`, and the numpy `np.isin(...) & (close > prev)`
  masks in `compute_wick` produce bit-identical `False`/`True` results to the
  original pandas boolean masks under NaN (verified empirically).
- **No circular import.** All four modules import standalone; the documented
  `cisd_barriers → cisd_charts → cisd_data` chain holds, and `cisd_charts`
  builders import `ANALYSES`/`ANALYSIS_META` lazily inside function bodies to
  break the cycle.
- **Re-export surface is intact.** `cisd_analysis.__all__` re-exports the full
  public + private API consumed by `scripts/` and `tests/`; all four imports
  succeed and the consuming scripts (`build_expectancy`, `build_forward_returns`,
  `build_validation`) resolve their symbols.
- **`prepare_pair` redefinition is intentional and tested.** It is redefined in
  `cisd_analysis.py` (not just re-exported) so `monkeypatch.setattr(cisd_analysis,
  "_scan_swing_smt_events", ...)` intercepts the scan — confirmed by
  `test_prepare_pair_applies_vectorized_swing_smt_annotations` and
  `test_prepare_pair_aligns_misaligned_resampled_frames`.
- **Test suite passes.** 94 tests collected (matching the claim); full runs exited 0.
- **No security issues.** No `eval`/`exec`/`os.system`/`subprocess`, no hardcoded
  secrets, no bare/empty except blocks, no debug artifacts. The `sys.path.insert`
  for the optional SMT package is gated behind a `_SMT_PKG_PATH.exists()` check.

The findings below are all maintainability defects introduced by the split. None
block the behavior-preserving goal, but the duplicated `prepare_pair` is a real
divergence hazard given the OOS-validation contract requires numbers to stay stable.

## Warnings

### WR-01: Duplicated `prepare_pair` — two definitions that can silently diverge

**File:** `cisd_data.py:344` (orphaned copy) and `cisd_analysis.py:102` (live copy)
**Issue:** `prepare_pair` is defined twice with byte-identical bodies. The
`cisd_data.py` copy is never imported anywhere (`cisd_analysis.py` deliberately
omits it from its `from cisd_data import (...)` block, and no module does
`from cisd_data import *` or `cisd_data.prepare_pair`). It is exported in
`cisd_data.__all__` (line 400), advertising it as public while being dead.

Because the live copy in `cisd_analysis.py` exists only to honor the
monkeypatch-scope contract (calling `_scan_swing_smt_events` from the
`cisd_analysis` namespace), the two will drift the moment someone edits one and
not the other. In a project whose core value is "computed numbers must not
silently change," a forgotten edit to the wrong copy is a latent OOS-validation
hazard — and `cisd_data.prepare_pair` calls `cisd_data._scan_swing_smt_events`,
so the two are NOT interchangeable if the SMT logic ever changes.

**Fix:** Remove the orphaned definition from `cisd_data.py` and drop
`"prepare_pair"` from `cisd_data.__all__`. Keep the single authoritative
definition in `cisd_analysis.py`. If `cisd_data` genuinely needs a non-patchable
pipeline helper, rename it (e.g. `_prepare_pair_core`) and have the
`cisd_analysis.py` wrapper delegate to it, so there is exactly one body of logic:
```python
# cisd_analysis.py
def prepare_pair(df_nq_1m, df_es_1m, rule, with_swing_smt=False):
    # ...resample/prepare...
    events = _scan_swing_smt_events(...)   # cisd_analysis-scoped for monkeypatch
    return (_annotate_swing_smt_from_events(df_nq, events, "NQ"),
            _annotate_swing_smt_from_events(df_es, events, "ES"))
```

### WR-02: Unused import `FVG_HOLD_LOOKAHEAD` in `cisd_barriers.py`

**File:** `cisd_barriers.py:21`
**Issue:** `from cisd_data import LOOKAHEAD, MAX_CONSEC, FVG_HOLD_LOOKAHEAD` imports
`FVG_HOLD_LOOKAHEAD`, but it is never referenced in `cisd_barriers.py` (it is used
only inside `cisd_data._classify_fvg_hold` and `cisd_charts._standalone_lookahead_caption`).
Leftover import from the split. Not a correctness issue, but it misleads readers
into thinking the barrier layer participates in FVG-hold windowing, which it does
not.
**Fix:** Remove `FVG_HOLD_LOOKAHEAD` from the import on line 21:
```python
from cisd_data import LOOKAHEAD, MAX_CONSEC
```

## Info

### IN-01: Dead local variable `idx_arr` in `compute_significance`

**File:** `cisd_barriers.py:130`
**Issue:** `idx_arr = df.index` is assigned but never used. It survives from the
original positional-indexing implementation; the vectorized/range-based version
indexes by integer position via `.iloc` and `barrier_hit(df, i, row, ...)`, so the
index handle is dead.
**Fix:** Delete line 130.

### IN-02: `OOS_START`/`MIN_N`/`CI_LEVEL` re-exported but unused by reviewed modules

**File:** `cisd_data.py:41-43`, re-exported in `cisd_analysis.py:37-39`
**Issue:** These validation constants are defined and threaded through the
re-export surface but are not consumed by any of the four reviewed modules (they
are presumably consumed by `scripts/build_validation.py`, which is out of this
review's file scope). This is correct by design — flagged only so a future reader
does not mistake them for dead config and delete them. No change required; verify
the validation harness still imports them before any cleanup pass.
**Fix:** None required. Confirm `scripts/build_validation.py` is the consumer
before treating these as removable.

---

_Reviewed: 2026-06-14T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
