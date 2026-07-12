---
phase: 09-smt-geometry-invalidation-honesty
reviewed: 2026-07-12T00:00:00Z
depth: quick
files_reviewed: 12
files_reviewed_list:
  - README.md
  - cisd_analysis.py
  - cisd_barriers.py
  - cisd_charts.py
  - cisd_data.py
  - scripts/build_smt_invalidation_report.py
  - tests/test_characterization.py
  - tests/test_smt_geometry.py
  - tests/test_smt_invalidation.py
  - tests/test_smt_invalidation_report.py
  - tests/test_swing_smt_integration.py
  - tests/test_vectorization_parity.py
findings:
  critical: 1
  warning: 3
  info: 1
  total: 5
status: issues_found
---

# Phase 09: Code Review Report

**Reviewed:** 2026-07-12
**Depth:** quick (grep-based scan, escalated to targeted code tracing + live reproduction once a crash path was suspected)
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 9 widens `_annotate_swing_smt_from_events` to a three-way `w/ SMT` / `expired SMT` / `no SMT` tag, adds geometry columns (`smt_block_size_atr`, `cisd_in_smt_block`), and adds three new registry analyses (`smt_role`, `smt_block_size`, `smt_in_block`). Grep scans for hardcoded secrets, `eval`/`exec`, debug artifacts, and empty `except` blocks turned up nothing. The core `_annotate_swing_smt_from_events` widening itself is thoroughly unit-tested and its validity/geometry semantics check out against the test suite.

However, the new registry entries were not fully threaded through two call sites that existed before this phase and were not touched by it: `cisd_analysis.py`'s `main()` SMT-availability guard, and `cisd_charts.py`'s `build_csv_rows()` dispatch. The first is a **reproduced crash** — running the tool's default invocation (or explicitly requesting `smt_role`/`smt_block_size`/`smt_in_block`) on a machine without the optional SMT package now raises an uncaught `ValueError` instead of degrading gracefully, contradicting this project's own documented constraint ("every entry point must degrade gracefully when [the SMT package] is absent"). This is a regression introduced by this phase's registry additions interacting with unmodified surrounding code.

## Critical Issues

### CR-01: `main()`'s SMT-package guard doesn't cover the three new SMT sub-analyses — reproduced crash

**File:** `cisd_analysis.py:196-206` (interacting with new registry entries added in `cisd_barriers.py:822-824,864-866`)
**Issue:**
`main()` decides whether to run the SMT scanner with:
```python
needs_swing_smt = "smt_cisd" in requested
if needs_swing_smt and not _SMT_PKG_PATH.exists():
    print(f"[warn] SMT package not found at {_SMT_PKG_PATH!s}; skipping smt_cisd analysis.")
    requested       = [k for k in requested if k != "smt_cisd"]
    standalone      = [k for k in standalone if k != "smt_cisd"]
    needs_swing_smt = False
```
This line was **not** touched by Phase 9, but Phase 9 added three new `ANALYSES`/`ANALYSIS_META` entries — `smt_role`, `smt_block_size`, `smt_in_block` — that also require the SMT-derived columns (`swing_smt_role`, `smt_block_size_atr`, `cisd_in_smt_block`), which only get populated when `prepare_pair(..., with_swing_smt=True)` runs the scanner. The guard only ever inspects `"smt_cisd" in requested` and only ever strips `"smt_cisd"` from `requested`/`standalone`. It never considers or strips the three new keys.

Two concrete failure paths:
1. `python3 cisd_analysis.py smt_role` (or `smt_block_size` / `smt_in_block`) alone, on any machine — `needs_swing_smt` is `False` because `"smt_cisd"` isn't in `requested`, so `prepare_pair` never runs the scanner, and `compute_smt_role` raises `ValueError: df must contain swing_smt_role column` inside `build_standalone_figure`.
2. `python3 cisd_analysis.py` (default, no args — the full analysis suite) on a machine **without** the SMT package installed — `smt_cisd` is stripped by the existing guard, but `smt_role`/`smt_block_size`/`smt_in_block` remain in `requested`/`standalone`, so the same crash occurs later in the run, after data has already been loaded and per-TF figures already built.

Reproduced live (SMT package path overridden to a nonexistent path to simulate an environment without it):
```
$ SMT_PKG_PATH=/nonexistent/path .venv/bin/python3 cisd_analysis.py smt_role
...
Building standalone: smt_role ... Traceback (most recent call last):
  File ".../cisd_charts.py", line 615, in build_standalone_figure
    d_nq = compute_fn(prepared["NQ"][tf_label])
  File ".../cisd_barriers.py", line 413, in compute_smt_role
    raise ValueError("df must contain swing_smt_role column")
ValueError: df must contain swing_smt_role column
```
This directly contradicts the project's own documented architectural constraint (CLAUDE.md): *"External dependency: SMT package ... is optional — every entry point must degrade gracefully when it is absent."*

**Fix:**
```python
_SMT_DEPENDENT_KEYS = {"smt_cisd", "smt_role", "smt_block_size", "smt_in_block"}
needs_swing_smt = bool(_SMT_DEPENDENT_KEYS & set(requested))

if needs_swing_smt and not _SMT_PKG_PATH.exists():
    skipped = _SMT_DEPENDENT_KEYS & set(requested)
    print(f"[warn] SMT package not found at {_SMT_PKG_PATH!s}; skipping {', '.join(sorted(skipped))}.")
    requested       = [k for k in requested if k not in _SMT_DEPENDENT_KEYS]
    standalone      = [k for k in standalone if k not in _SMT_DEPENDENT_KEYS]
    needs_swing_smt = False
```
(Consider deriving `_SMT_DEPENDENT_KEYS` from `ANALYSIS_META` rather than hardcoding, to avoid this drifting again the next time an SMT-dependent analysis is added.)

## Warnings

### WR-01: `build_csv_rows` dispatch not extended for the three new SMT sub-analyses

**File:** `cisd_charts.py:439-521` (elif chain at 493, 498, 503, 509, 516)
**Issue:** Phase 9 added `smt_role`, `smt_block_size`, and `smt_in_block` to `ANALYSES`/`ANALYSIS_META` (`cisd_barriers.py:822-824,864-866`) and their `chart_*` functions (`cisd_charts.py`), but `build_csv_rows`'s key-dispatch `elif` chain was not extended to cover them. Their `compute_fn` shape (`{ct: {tag: {total, runs}}}`) is identical to the already-handled `smt_cisd`/`sweep`/`sssf_swing` shapes, so this looks like a simple oversight rather than an intentional exclusion. Currently this is **dormant** — all three keys are `standalone=True` in `ANALYSIS_META`, so `main()`'s `per_tf_keys` filter always excludes them from the `build_csv_rows(per_tf_keys, ...)` call, meaning the gap is never hit through the CLI today. But `build_csv_rows` is documented as "Flatten all analysis results into a tidy long-format table" and is a public, directly-importable function (`cisd_analysis.build_csv_rows`) — any future caller (a script, a test, or a CLI change that starts using it for standalone keys) that passes one of these three keys will get a silently empty result for that key instead of an error, which is a much harder failure mode to notice than a crash.
**Fix:** Add the missing branch, mirroring `smt_cisd`:
```python
elif key in ("smt_cisd", "smt_role", "smt_block_size", "smt_in_block"):
    for ct in ("bullish", "bearish"):
        for tag, d in data[ct].items():
            add(label, instr, ct, tag, d["total"], d["runs"])
```

### WR-02: `compute_smt_role` docstring claims an invariant that `_annotate_swing_smt_from_events` does not actually enforce

**File:** `cisd_barriers.py:406-411`; contradicted by `cisd_data.py:618-621`
**Issue:** The docstring states: *"Rows tagged 'no SMT' or 'expired SMT' carry swing_smt_role == 'none' and are excluded."* In fact, `swing_smt_role[match_positions] = np.where(matched_sweeping == instrument, "swept", ...)` in `_annotate_swing_smt_from_events` is computed for **every** matched position — `w/ SMT` and `expired SMT` alike — without conditioning on validity. Reproduced directly:
```python
# event created at t-2, broken_ts == t (expires exactly at the CISD bar)
row["swing_smt_tag"]  == "expired SMT"
row["swing_smt_role"] == "swept"          # NOT "none", contradicting the docstring
```
`compute_smt_role` itself is still correct (it filters on `tag_arr[pos] != "w/ SMT"`, not on role), so there is no live behavioral bug today. But the docstring documents a false invariant about the underlying data — a future maintainer who trusts `swing_smt_role == "none"` as a proxy for "not a valid w/ SMT match" (e.g. in a new analysis, a manifest filter, or `scripts/build_validation.py`) will get silently wrong results for expired-but-role-resolved rows.
**Fix:** Correct the docstring to describe what actually happens, e.g.: *"`swing_smt_role` is populated for the whole matched population (w/ SMT and expired SMT alike) independent of validity; this function filters on `swing_smt_tag == 'w/ SMT'` specifically, not on role, to get the valid-only population."*

### WR-03: Stale test assertion no longer reflects the new three-way tag vocabulary

**File:** `tests/test_swing_smt_integration.py:251`
**Issue:** `test_prepare_pair_swing_smt_columns_exist_when_scanner_runs` asserts:
```python
assert set(df_nq["swing_smt_tag"].unique()) <= {"w/ SMT", "no SMT"}
```
Phase 9 introduced the `"expired SMT"` tag value and edited three other call sites in this same file to add the new event lifecycle columns (`reference_price`, `broken_ts`, `status`, etc. — see the diff at lines 12-16, 27-33, 130-136), but did not update this assertion. This test is gated on the real SMT package being installed and currently only exercises synthetic, monotonically-increasing OHLC data, so it likely never produces an `expired SMT` match today and passes by luck rather than by correctness. If the synthetic fixture (or a future edit to it) ever produces a match whose `broken_ts <= t`, this assertion will start failing — or worse, if the set were changed to `==` instead of `<=` it would already be silently too permissive. As written it gives a false sense that the three-way tag split is exercised end-to-end through `prepare_pair`, when it is not.
**Fix:** Widen the assertion to `<= {"w/ SMT", "expired SMT", "no SMT"}`, and/or add a dedicated assertion (or a new test) that exercises the `expired SMT` path through `prepare_pair` with a mocked `_scan_swing_smt_events` returning a `broken_ts <= t` event, so the integration path for the new tag is actually covered rather than only the lower-level `_annotate_swing_smt_from_events` unit tests in `tests/test_smt_invalidation.py`.

## Info

### IN-01: Duplicated barrier-window loop across three near-identical functions

**File:** `cisd_barriers.py:47-98` (`barrier_hit`, `barrier_hit_forward`, `barrier_outcome_forward`)
**Issue:** All three functions repeat the same bullish/bearish target-vs-stop comparison logic with only the loop range (`range(1, LOOKAHEAD+1)` vs `range(2, LOOKAHEAD+2)`) and the return values differing. This predates Phase 9 in spirit but `barrier_hit_forward`/`barrier_outcome_forward` were introduced in a prior phase and Phase 9's new compute functions (`compute_smt_role`, `compute_smt_block_size`, `compute_smt_in_block`) all call `barrier_hit`, adding three more call sites that would benefit from a shared, parameterized implementation.
**Fix:** Not urgent — no behavioral risk today since the three functions are independently unit/characterization-tested — but a `_barrier_outcome(df, idx, row, ct, start_offset) -> Literal["continuation","reversal","neither"]` helper, with `barrier_hit`/`barrier_hit_forward` as thin boolean wrappers, would remove ~35 lines of duplication and reduce the risk of the three implementations drifting apart on a future edit.

---

_Reviewed: 2026-07-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
