---
phase: 03-re-validate-republish-existing-findings
reviewed: 2026-06-14T00:00:00Z
depth: quick
files_reviewed: 5
files_reviewed_list:
  - README.md
  - scripts/build_discovery_summary.py
  - scripts/build_reconcile_findings.py
  - scripts/build_validation.py
  - tests/test_reconcile_findings.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-06-14T00:00:00Z
**Depth:** quick
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Five files were reviewed: the updated README and four new Python files implementing the phase-03 validation harness (`build_validation.py`, `build_reconcile_findings.py`, `build_discovery_summary.py`) and its accompanying unit test (`test_reconcile_findings.py`). The overall structure is sound: the manifest/reconcile/summary pipeline is clearly separated, the outer-merge guard (D-06) is implemented correctly, and the Wilson CI math is correct. Two correctness bugs were found — one that crashes the process and one that silently mislabels a statistical result — plus three warnings around silent failure modes and missing guards.

## Critical Issues

### CR-01: `wilson_ci` crashes with `ValueError` when `k > n`

**File:** `scripts/build_validation.py:93`
**Issue:** `p_hat = k / n` produces a value greater than 1.0 when successes exceed total observations. The subsequent `math.sqrt(p_hat * (1 - p_hat) / n + ...)` call receives a negative radicand and raises `ValueError: math domain error`. Although a correctly-implemented `compute_*` function will never return `runs > total`, any regression or bug in a compute function would cause `build_manifest_rows` to crash the entire run rather than skipping the bad bucket. The `except Exception: continue` guard at line 145 only wraps the `compute_fn(df)` call, not the downstream `emit()` call, so the exception escapes.

```python
# scripts/build_validation.py – emit() function, around line 120

def emit(analysis: str, instrument: str, direction: str, bucket: str, n: int, k: int) -> None:
    # Add a defensive guard before calling wilson_ci
    if k > n:
        # Corrupt output from compute_fn — skip and warn; never crash the run
        print(f"[warn] {analysis}/{instrument}/{direction}/{bucket}: k={k} > n={n}; skipping")
        return
    lo, hi = wilson_ci(n, k)
    rows.append({...})
```

---

### CR-02: `determine_verdict` asymmetric at the exact 0.50 boundary — mislabels sub-50% discovery with OOS=0.50 as "confirmed"

**File:** `scripts/build_reconcile_findings.py:98`
**Issue:** The verdict comparison is `(discovery_rate > 0.50) == (oos_rate > 0.50)`. When `discovery_rate < 0.50` (a "weakness" direction) and `oos_rate == 0.50` exactly, both expressions evaluate to `False`, making them "equal", and the function returns `"confirmed"`. This is semantically wrong: an OOS rate of exactly 0.50 is not on the "same side" as a sub-50% discovery rate; it sits on the boundary and provides no directional evidence. In practice `k/n` can equal exactly 0.50 whenever `n` is even and `k = n/2`.

The symmetric case (`discovery_rate > 0.50`, `oos_rate == 0.50`) correctly returns `"not-confirmed"`, creating an inconsistency: the exact boundary is treated differently depending on which half the discovery rate falls in.

```python
# scripts/build_reconcile_findings.py

# Current (buggy for discovery < 0.50 when oos == 0.50):
if (discovery_rate > 0.50) == (oos_rate > 0.50):
    return "confirmed"

# Fixed — treat exact 0.50 OOS as "no directional evidence":
def _side(r: float) -> int:
    if r > 0.50:
        return 1
    if r < 0.50:
        return -1
    return 0  # exact tie — neither side

if _side(discovery_rate) != 0 and _side(oos_rate) != 0 and _side(discovery_rate) == _side(oos_rate):
    return "confirmed"
return "not-confirmed"
```

---

## Warnings

### WR-01: `reconcile()` crashes with raw `FileNotFoundError` when OOS manifest is absent

**File:** `scripts/build_reconcile_findings.py:119-120`
**Issue:** `reconcile()` calls `pd.read_csv(OOS_MANIFEST_PATH)` without first checking whether the file exists. If a researcher runs `python3 scripts/build_reconcile_findings.py` before the OOS evaluation has been performed, they receive an opaque OS-level `FileNotFoundError` with no guidance. Compare: `build_discovery_summary.py` correctly guards with an `exists()` check and prints a user-friendly error (line 127). The OOS manifest file deserves the same treatment, with additional wording that warns the OOS evaluation has not been run yet.

```python
# scripts/build_reconcile_findings.py – top of reconcile()

def reconcile() -> None:
    if not DISCOVERY_MANIFEST_PATH.exists():
        print(f"[error] discovery manifest not found: {DISCOVERY_MANIFEST_PATH}")
        print("Run `python3 scripts/build_validation.py` (discovery) first.")
        sys.exit(1)
    if not OOS_MANIFEST_PATH.exists():
        print(f"[error] OOS manifest not found: {OOS_MANIFEST_PATH}")
        print("Run `python3 scripts/build_validation.py --oos` before reconciling.")
        sys.exit(1)
    disc = pd.read_csv(DISCOVERY_MANIFEST_PATH)
    oos  = pd.read_csv(OOS_MANIFEST_PATH)
    ...
```

---

### WR-02: `build_manifest_rows` silently swallows `compute_fn` failures with no diagnostic output

**File:** `scripts/build_validation.py:143-146`
**Issue:** The `except Exception: continue` block at line 145 degrades gracefully when a compute function fails on an empty slice, but it emits no warning. If `compute_fn` fails for a non-empty slice (e.g., a missing column due to `with_swing_smt=False` when `smt_cisd` is in the key list), the bucket silently disappears from the manifest with no indication that rows were dropped. The researcher would discover the gap only by noticing missing rows in the output CSV.

```python
            try:
                data = compute_fn(df)
            except Exception as exc:  # noqa: BLE001
                # Add a warning so silent drops are visible:
                print(
                    f"[warn] {key}/{instrument}/{tf_label}: compute failed"
                    f" ({type(exc).__name__}: {exc}); skipping"
                )
                continue
```

---

### WR-03: SMT availability probe in `main()` uses a full `prepare_pair` call that silently disables SMT for all timeframes if any non-SMT error occurs

**File:** `scripts/build_validation.py:250-256`
**Issue:** The probe at line 251-252 runs a full `prepare_pair(..., with_swing_smt=True)` on the first timeframe to check whether the SMT package is available. The surrounding `except Exception` block catches any exception — including data errors, empty-frame errors, or resampling failures that have nothing to do with SMT availability. If such an error occurs on the probe timeframe, `with_smt` is silently set to `False` and SMT tagging is disabled globally for the entire run, producing a manifest without SMT data and no actionable error message.

```python
    try:
        _first_rule = next(iter(TIMEFRAMES.values()))
        prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], _first_rule, with_swing_smt=True)
        with_smt = True
    except (FileNotFoundError, ImportError):
        # Only suppress SMT-specific failures (package absent or unimportable)
        print(f"[warn] SMT unavailable; swing SMT columns will be absent")
        with_smt = False
    # Let all other exceptions propagate — they indicate a data or pipeline problem
```

---

## Info

### IN-01: Dead module-level constant `MANIFEST_PATH` in `build_validation.py`

**File:** `scripts/build_validation.py:22`
**Issue:** `MANIFEST_PATH = REPO_ROOT / "output" / "validation_manifest.csv"` is defined at module level with a comment "legacy name (kept for import compat)" but is never written to and is not imported by any other file in the codebase. If no external consumer depends on this name, it should be removed to avoid confusion about which manifest file is the active output.

**Fix:** Verify no external code imports `MANIFEST_PATH` from this module, then delete the constant. If it must be kept for a future consumer, add a `__all__` entry and a note about what will consume it.

---

### IN-02: README `python` vs `python3` inconsistency in Usage section

**File:** `README.md:328,333`
**Issue:** The Usage section (lines 328 and 333) shows `python cisd_analysis.py` and `python cisd_analysis.py cisd_fvg ...` without the `3` suffix. All other references in the project (CLAUDE.md, the introduction block in README itself line 326) use `python3`. On systems where `python` resolves to Python 2, these commands would silently fail.

**Fix:** Change both occurrences to `python3 cisd_analysis.py`.

---

_Reviewed: 2026-06-14T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
