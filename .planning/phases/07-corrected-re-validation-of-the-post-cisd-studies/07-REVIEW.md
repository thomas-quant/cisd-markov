---
phase: 07-corrected-re-validation-of-the-post-cisd-studies
reviewed: 2026-07-11T00:00:00Z
depth: quick
files_reviewed: 7
files_reviewed_list:
  - README.md
  - cisd_analysis.py
  - cisd_barriers.py
  - cisd_charts.py
  - scripts/build_post_cisd_verdict.py
  - tests/test_post_cisd_verdict.py
  - tests/test_research_extensions.py
findings:
  critical: 0
  warning: 5
  info: 2
  total: 7
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-07-11T00:00:00Z
**Depth:** quick (pattern scan + targeted read of the actual diff since `a8864de`, cross-checked against the generated `output/*.csv` artifacts where practical)
**Files Reviewed:** 7
**Status:** issues_found

## Summary

The actual diff for this phase is small: `barrier_outcome_forward` (new three-way outcome classifier), the reversal/neither partition wired into `compute_post_cisd_context`, two new chart tags, a brand-new `scripts/build_post_cisd_verdict.py` verdict builder, its unit tests, and a new README section publishing the corrected-bar rollup table.

No hardcoded secrets, `eval`/`exec`, empty catches, or debug artifacts were found via pattern scan. I traced the new `barrier_outcome_forward` / reversal-neither logic against its unit tests by hand and it checks out. I also cross-verified the headline README numbers (the `n_buckets`/`n_cleared` rollup table and the 32.9%/59.2%/7.9% discovery vs. 34.3%/57.8%/7.9% OOS continuation/reversal/neither split) against the actual generated `output/post_cisd_verdict_rollup.csv`, `output/post_cisd_verdict.csv`, and `output/validation_manifest_discovery.csv` — all figures reproduce exactly from the checked-in code, so I did not find a numeric/reporting bug in the new logic.

The findings below are all quality/robustness issues: DRY violations across the three near-identical barrier loop functions, an inconsistently-defended three-way `outer` merge in the new verdict builder, one pre-existing (not introduced by this phase, but in-scope) undercounting bug in `compute_significance`, and two pre-existing vacuous test assertions in `tests/test_research_extensions.py` that happen to live right next to the code this phase extends.

## Warnings

### WR-01: `same_side` and `_bucket_clears`'s same-side check are two independent implementations of the same rule

**File:** `scripts/build_post_cisd_verdict.py:118-137`
**Issue:** `merged["same_side"]` (lines 118-127) and the same-side branch inside `_bucket_clears` (lines 38-54, specifically lines 53-54) both re-derive "is OOS on the same side of 0.50 as discovery" from scratch, using duplicated `pd.isna`/`_side` boilerplate instead of sharing one helper. If a future change to the "same side" rule (e.g. a tolerance band, or how `oos_n == 0` is treated) is applied to one site and not the other, `same_side` and `clears_bar` will silently disagree — and since `same_side` is a diagnostic column that gets published in `output/post_cisd_verdict.csv`, a drift here would produce a CSV that visibly contradicts its own `clears_bar` verdict without either test suite catching it (the two are never cross-checked against each other in `tests/test_post_cisd_verdict.py`).
**Fix:**
```python
def _oos_same_side(discovery_rate: float, oos_rate: float, oos_n: float | None) -> bool:
    if pd.isna(oos_n) or float(oos_n) == 0 or pd.isna(oos_rate):
        return False
    d_side = _side(discovery_rate)
    return bool(d_side != 0 and d_side == _side(oos_rate))

def _bucket_clears(discovery_rate, corrected_pass, wf_verdict, oos_rate, oos_n) -> bool:
    if pd.isna(corrected_pass) or not bool(corrected_pass):
        return False
    if wf_verdict != "wf-robust":
        return False
    return _oos_same_side(discovery_rate, oos_rate, oos_n)
```
and reuse `_oos_same_side` for the `same_side` column.

### WR-02: Three-way `outer` merge in `build_verdict()` dedups only one of three inputs and never asserts key-set alignment

**File:** `scripts/build_post_cisd_verdict.py:104-116`
**Issue:** `wf_sel` is explicitly `.drop_duplicates(subset=_MERGE_KEYS, keep="first")` (line 110-113) because walk-forward has multiple fold rows per bucket, but `disc_sel` (line 104) and `oos_sel` (line 107) are used as-is. If either the discovery or OOS manifest ever contains more than one row per `_MERGE_KEYS` combo (e.g. a future bug in `build_validation.py` that double-registers a bucket, or a manual re-run that appends instead of overwrites), the two `merge(..., how="outer")` calls will silently fan out into duplicate bucket rows, inflating `n_buckets` in `rollup_by_tag` without any error or warning. Separately, the `how="outer"` join means a bucket key present in only one of the three manifests (e.g. after a schema change that adds/removes a bucket) produces a partial row with `NaN` discovery/oos/wf fields; `_bucket_clears` correctly returns `False` for that row, but the row still counts toward `n_buckets` in the rollup denominator, silently changing the "N of 16" figures published in the README. I confirmed the three manifests currently in `output/` have identical 192-row key sets for the two post-CISD analyses (no live bug today), but nothing in the code or tests would catch a future desync.
**Fix:** Dedup all three selections the same way, and assert the key sets match before merging (or use `pd.merge(..., how="outer", validate="1:1")` plus an explicit assertion that `len(merged) == len(disc_sel) == len(oos_sel)` after dedup, failing loudly instead of silently changing denominators):
```python
disc_sel = disc_sel.drop_duplicates(subset=_MERGE_KEYS, keep="first")
oos_sel  = oos_sel.drop_duplicates(subset=_MERGE_KEYS, keep="first")
...
merged = disc_sel.merge(oos_sel, on=_MERGE_KEYS, how="outer", validate="1:1")
assert len(merged) == len(disc_sel), "discovery/OOS bucket key sets diverged"
```

### WR-03: `compute_significance` silently drops CISD events in the last `LOOKAHEAD` bars of each resampled frame from its totals (pre-existing, in-scope file)

**File:** `cisd_barriers.py:170`
**Issue:** `for i in range(1, len(df) - LOOKAHEAD):` stops the loop `LOOKAHEAD` bars before the end of the frame, so a stricter-CISD event occurring on the final 1-2 bars of a resampled timeframe is never even added to `totals`/`runs`. Every other `compute_*` function (`compute_basic`, `compute_wick`, `compute_mc`, etc.) instead iterates `event_pos = np.flatnonzero(pd.notna(df["cisd_type"]))` over the *full* index and relies on `barrier_hit`'s own `if idx + j >= len(df): break` guard to correctly record such boundary events as non-hits (counted in `totals`, not in `runs`). `compute_significance` is therefore inconsistent with the rest of the codebase: it doesn't recompute cisd_type (documented, intentional) *and* it also silently excludes boundary events from the denominator (undocumented, and inconsistent with every sibling `compute_*`). Impact is small in absolute terms (at most ~2 events per instrument/timeframe out of thousands), but it is a real, reproducible undercount and it sits in a file this phase's scope explicitly includes for full review.
**Fix:**
```python
for i in range(1, len(df)):
    if i - 1 < 0:
        continue
    ph, pl, cc = df["high"].iloc[i-1], df["low"].iloc[i-1], df["close"].iloc[i]
    row = df.iloc[i]
    ...
```
`barrier_hit`'s existing bounds check already makes the manual `- LOOKAHEAD` truncation unnecessary.

### WR-04: `barrier_hit`, `barrier_hit_forward`, and the newly-added `barrier_outcome_forward` are three copy-pasted loops

**File:** `cisd_barriers.py:44-95`
**Issue:** All three functions repeat the identical `for j in range(...): bar = df.iloc[idx+j]; if ct == "bullish": ... else: ...` structure, differing only in loop bounds and return values. This phase adds the third copy (`barrier_outcome_forward`, lines 83-95), which duplicates `barrier_hit_forward`'s exact stop/target comparisons. The test suite does verify `(outcome == "continuation") == barrier_hit_forward(...)` (`tests/test_research_extensions.py`, `test_barrier_outcome_continuation_matches_barrier_hit_forward`), which is good, but that only catches drift after the fact — the implementation itself has no structural guarantee the two stay in sync, and a future edit to one (e.g. changing the same-bar tie-break order) can trivially be made to only one of the three functions.
**Fix:** Implement `barrier_hit_forward` in terms of `barrier_outcome_forward` (or extract a shared `_barrier_outcome(df, idx, row, ct, start_j, end_j)` helper) so there is exactly one place that encodes the stop/target comparison order:
```python
def barrier_hit_forward(df, idx, row, ct):
    return barrier_outcome_forward(df, idx, row, ct) == "continuation"
```

### WR-05: Vacuous/conditionally-skipped assertions in `tests/test_research_extensions.py` (pre-existing, in-scope file)

**File:** `tests/test_research_extensions.py:389-404`, `tests/test_research_extensions.py:581-603`
**Issue:** Two tests reduce the reliability of the test suite this phase's new code relies on for confidence:
- `test_candle1_past_candle0_wick_true_when_close_clears_cisd_high` (line 389) wraps its only assertion inside three nested `if` guards (`if len(bullish_events) > 0`, `if ... == "with"`, `if next_close is not None and next_close > cisd_high`). If any guard is false — which depends on incidental fixture arithmetic, not on anything the test controls explicitly — the test body falls through with zero assertions executed and reports as passing. It currently happens to hit the assertion, but the test can silently stop testing anything after an unrelated fixture edit.
- `test_barrier_hit_forward_not_the_same_as_barrier_hit_on_same_call` (line 581) ends with `assert hasattr(cisd_analysis, "barrier_hit") or True  # already confirmed existing` (line 603) — this assertion is a tautology (`X or True` is always `True`) and never fails regardless of `barrier_hit`'s presence or correctness. The test's docstring/name claims to verify `barrier_hit_forward` starts its lookahead at `idx+2`, but no such assertion exists in the body.

These predate this phase (both introduced in earlier phases, `f5f930e` / before `a8864de`), but they sit directly next to — and are meant to lend confidence to — the `barrier_hit_forward`/`barrier_outcome_forward` machinery this phase's `compute_post_cisd_context` change depends on, so a reviewer relying on "the test suite already covers this" would be over-trusting these two.
**Fix:** Replace the nested-`if` test with an unconditional fixture that deterministically produces a bullish CISD with `candle1_close_dir == "with"` and a close that clears the CISD high, and assert on it directly. Replace the tautological line with a real assertion, e.g. compute the barrier at `idx+1` window vs `idx+2` window explicitly and assert they differ for the constructed fixture (the docstring already describes the exact scenario needed).

## Info

### IN-01: Dead defensive check in `rollup_by_tag`

**File:** `scripts/build_post_cisd_verdict.py:69`
**Issue:** `if not pd.isna(flag) and bool(flag)` — `flag` is always the return value of `_bucket_clears`, which always returns a definite `bool` (never `NaN`). The `pd.isna(flag)` branch is therefore unreachable dead code that adds a false impression of NaN-handling.
**Fix:** Drop the `pd.isna` check (`sum(1 for flag in clears_flags if flag)`), or if defending against a future caller that might pass `NaN`, add a comment explaining why, and a test that exercises that path.

### IN-02: Same-bar stop/target tie-break assumption isn't disclosed for the new reversal/continuation/neither split

**File:** `cisd_barriers.py:83-95`
**Issue:** `barrier_outcome_forward` (like `barrier_hit`/`barrier_hit_forward` before it) checks the stop condition before the target condition within the same OHLC bar, so a bar whose range spans both the CISD high and low is always classified as a stop/reversal rather than a target/continuation — an inherent OHLC ambiguity that can't be resolved without intrabar data. This assumption is consistent with the rest of the codebase's methodology (not a new bug), but this phase is the first to publish a headline reversal-vs-continuation-vs-neither percentage split in the README (32.9%/59.2%/7.9%) built directly on top of it, and the README's "Validation Methodology" section doesn't mention the tie-break rule anywhere.
**Fix:** Add one sentence to the README's Post-CISD Context section (or the Research Tag Rules section) noting the same-bar stop-before-target convention, so the reported reversal rate is read with the correct caveat.

---

_Reviewed: 2026-07-11T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
