---
phase: 09-smt-geometry-invalidation-honesty
fixed_at: 2026-07-12T10:58:24Z
review_path: .planning/phases/09-smt-geometry-invalidation-honesty/09-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 09: Code Review Fix Report

**Fixed at:** 2026-07-12T10:58:24Z
**Source review:** .planning/phases/09-smt-geometry-invalidation-honesty/09-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (CR-01, WR-01, WR-02, WR-03; IN-01 excluded per fix_scope — info-level, reviewer explicitly marked "not urgent" and out of scope as a larger refactor)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: `main()`'s SMT-package guard doesn't cover the three new SMT sub-analyses — reproduced crash

**Files modified:** `cisd_analysis.py`
**Commit:** 1eb96c2
**Applied fix:** Replaced the single `"smt_cisd" in requested` check with a module-scoped `_SMT_DEPENDENT_KEYS = {"smt_cisd", "smt_role", "smt_block_size", "smt_in_block"}` set intersection. The guard now strips all four SMT-dependent keys from `requested`/`standalone` (not just `smt_cisd`) when the SMT package is unavailable, and the warning message lists every skipped key. Verified by reproducing the exact crash scenario from the review: `SMT_PKG_PATH=/nonexistent/path .venv/bin/python3 cisd_analysis.py smt_role` now prints `[warn] SMT package not found at /nonexistent/path; skipping smt_role.` and completes the run (per-TF analyses skipped, no traceback) instead of raising `ValueError: df must contain swing_smt_role column`.

### WR-01: `build_csv_rows` dispatch not extended for the three new SMT sub-analyses

**Files modified:** `cisd_charts.py`
**Commit:** 7885d67
**Applied fix:** Widened the `elif key == "smt_cisd":` branch in `build_csv_rows` to `elif key in ("smt_cisd", "smt_role", "smt_block_size", "smt_in_block"):`. Confirmed all three new compute functions (`compute_smt_role`, `compute_smt_block_size`, `compute_smt_in_block`) return the same `{ct: {tag: {total, runs}}}` shape already handled by that branch, so no further changes were needed.

### WR-02: `compute_smt_role` docstring claims an invariant that `_annotate_swing_smt_from_events` does not actually enforce

**Files modified:** `cisd_barriers.py`
**Commit:** ec5ebd5
**Applied fix:** Rewrote the docstring to state that `swing_smt_role` is populated for the whole matched population ("w/ SMT" and "expired SMT" alike) independent of validity, and that `compute_smt_role` filters on `swing_smt_tag == "w/ SMT"` specifically (not on role) to get the valid-only population; only unmatched ("no SMT") rows carry `swing_smt_role == "none"`. Verified the underlying behavior directly against `cisd_data.py:618-621` (role assignment is unconditional on `still_valid`) and the `"none"` default init at `cisd_data.py:543` before rewording.

### WR-03: Stale test assertion no longer reflects the new three-way tag vocabulary

**Files modified:** `tests/test_swing_smt_integration.py`
**Commit:** dc45341
**Applied fix:** Widened `test_prepare_pair_swing_smt_columns_exist_when_scanner_runs`'s assertion from `<= {"w/ SMT", "no SMT"}` to `<= {"w/ SMT", "expired SMT", "no SMT"}`, and added a new dedicated test, `test_prepare_pair_annotates_expired_swing_smt_tag`, that exercises the `expired SMT` path through the full `prepare_pair` integration path (not just the lower-level `_annotate_swing_smt_from_events` unit tests) via a mocked `_scan_swing_smt_events` returning an event with `broken_ts == t` (the CISD bar itself). This closes the gap the reviewer flagged — the integration-level three-way split is now actually covered rather than only asserted-by-luck. All 13 tests in the file pass, including the new one.

## Skipped Issues

None — all in-scope findings were fixed.

---

_Fixed: 2026-07-12T10:58:24Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
