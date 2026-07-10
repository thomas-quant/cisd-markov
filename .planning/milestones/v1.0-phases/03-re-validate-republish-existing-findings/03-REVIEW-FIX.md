---
phase: 03-re-validate-republish-existing-findings
fixed_from: 03-REVIEW.md
iteration: 1
fix_scope: critical_warning
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fix Scope:** critical_warning (Critical + Warning)
**Findings in Scope:** 5
**Fixed:** 5
**Skipped:** 0
**Status:** all_fixed

## Fixed

### CR-01: `wilson_ci` crashes with `ValueError` when `k > n`
**File:** `scripts/build_validation.py`
**Fix:** Added a defensive guard in `emit()` that checks `k > n` before calling `wilson_ci`. If `k > n`, prints a `[warn]` message and returns early without crashing the run.
**Commit:** `a3b0a8b` — fix(03): CR-01 guard against k > n crash in emit() before wilson_ci

---

### CR-02: `determine_verdict` asymmetric at exact 0.50 boundary
**File:** `scripts/build_reconcile_findings.py`
**Fix:** Introduced a `_side()` helper function that returns `1` (above 0.50), `-1` (below 0.50), or `0` (exactly 0.50). `determine_verdict` now requires both `_side(discovery_rate)` and `_side(oos_rate)` to be non-zero and equal before returning `"confirmed"`, eliminating the false-confirm when OOS rate is exactly 0.50.
**Commit:** `9978718` — fix(03): CR-02 add _side() helper to fix asymmetric 0.50 boundary in determine_verdict

---

### WR-01: `reconcile()` crashes with raw `FileNotFoundError` when OOS manifest is absent
**File:** `scripts/build_reconcile_findings.py`
**Fix:** Added `Path.exists()` guards for both `DISCOVERY_MANIFEST_PATH` and `OOS_MANIFEST_PATH` at the top of `reconcile()`. Each guard prints a user-friendly error message with the next step and calls `sys.exit(1)`.
**Commit:** `60a5269` — fix(03): WR-01 guard reconcile() against missing manifests with user-friendly errors

---

### WR-02: `build_manifest_rows` silently swallows `compute_fn` failures
**File:** `scripts/build_validation.py`
**Fix:** Changed `except Exception: continue` to `except Exception as exc:` with a `print(f"[warn] {key}/{instrument}/{tf_label}: compute failed ({type(exc).__name__}: {exc}); skipping")` before `continue`. Silent drops are now visible to the researcher.
**Commit:** `8c3730a` — fix(03): WR-02 emit warning when compute_fn fails instead of silently skipping

---

### WR-03: SMT availability probe uses bare `except Exception`
**File:** `scripts/build_validation.py`
**Fix:** Narrowed the SMT probe `except` clause from bare `except Exception` to `except (FileNotFoundError, ImportError)`. Non-SMT errors (data errors, resampling failures) now propagate as real tracebacks instead of silently disabling SMT for the entire run.
**Commit:** `c2c4e16` — fix(03): WR-03 narrow SMT probe except clause to (FileNotFoundError, ImportError) only

---

## Skipped

None — all in-scope findings were fixed automatically.

---

_Fixed: 2026-06-14T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
