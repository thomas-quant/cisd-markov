# Phase 6: Harder Evidence Bar — Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 3 (2 modified, 1 new module likely; test file modified)
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `scripts/build_validation.py` (extend: p-value emission, BH correction, walk-forward folds, new CLI flag) | service/CLI (statistics + manifest builder) | batch/CRUD (reads parquet → computes buckets → writes CSV) | itself (`scripts/build_validation.py`) | exact (in-place extension) |
| New sibling module for correction math, e.g. `scripts/build_multiple_comparisons.py` or inline in `build_validation.py` (planner's call per CONTEXT integration point) | utility (pure statistics functions) | transform (list of p-values → corrected flags) | `wilson_ci()` / `n_gate()` in `scripts/build_validation.py:72-99` | exact (same file, same "pure stdlib, no scipy" pattern) |
| `scripts/build_reconcile_findings.py` (possibly augmented with corrected-pass flag per D-03, though D-03 says correction is discovery-stage only — likely untouched or minimally touched) | service/CLI (merge + verdict) | batch/CRUD | itself (`scripts/build_reconcile_findings.py`) | exact |
| `tests/test_validation_harness.py` (extend with tests for p-value, BH correction, walk-forward fold math) | test | request-response (pure function assertions) | itself (`tests/test_validation_harness.py`) | exact |

No net-new controller/component/route files — this phase is purely additive statistics logic within the existing validation-harness script family.

## Pattern Assignments

### `scripts/build_validation.py` — p-value + BH correction + walk-forward extension

**Analog:** itself, `wilson_ci()` and `build_manifest_rows()` / `slice_df()` / `main()` in the same file.

**Imports pattern** (lines 1-19):
```python
"""Validation harness — discovery/OOS slicing, Wilson CI, sample-size gating, manifest CSV."""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cisd_analysis import (
    ANALYSES, INSTRUMENTS, MAX_CONSEC, TIMEFRAMES, OOS_START, MIN_N, CI_LEVEL,
    load_1m, resample_ohlcv, prepare_pair,
)
```
New code should follow this exact style: relative import of `REPO_ROOT` inserted into `sys.path`, constants imported from `cisd_analysis`, no new third-party dependency (no scipy/statsmodels — confirmed absent in `.venv`).

**Pure-stdlib statistical helper pattern** (`wilson_ci`, lines 72-94, and the `_erfinv` fallback, lines 43-69):
```python
try:
    _erfinv = math.erfinv  # type: ignore[attr-defined]
except AttributeError:
    def _erfinv(x: float) -> float:
        """Inverse error function ..."""
        ...

def wilson_ci(n: int, k: int, level: float = CI_LEVEL) -> tuple[float, float]:
    """Wilson score CI for k successes in n trials. Returns (low, high) in [0, 1]."""
    if n == 0:
        return (0.0, 0.0)
    z = math.sqrt(2) * _erfinv(level)
    ...
```
The new p-value test (`H0: rate = 0.5`, per D-01) and the BH correction routine must follow this identical pattern: pure `math`-module implementation, guard clause for `n == 0`, full docstring with the derivation/formula spelled out, return simple tuples/floats — no new imports.

**Sample-size gate pattern** (`n_gate`, lines 97-99):
```python
def n_gate(n: int, min_n: int = MIN_N) -> bool:
    """Return True if n meets the minimum sample size threshold."""
    return n >= min_n
```
A parallel `bh_gate` / `corrected_pass` boolean helper should mirror this one-line, single-responsibility, module-level function style — not a class or config object.

**Dispatch/aggregation pattern** (`build_manifest_rows`, lines 104-209, esp. the `emit()` inner closure at 120-139):
```python
def emit(analysis: str, instrument: str, direction: str, bucket: str, n: int, k: int) -> None:
    if k > n:
        print(f"[warn] {analysis}/{instrument}/{direction}/{bucket}: k={k} > n={n}; skipping")
        return
    lo, hi = wilson_ci(n, k)
    rows.append({
        "analysis":   analysis,
        ...
        "rate":       round(k / n, 6) if n > 0 else 0.0,
        "n":          n,
        "successes":  k,
        "ci_low":     round(lo, 6),
        "ci_high":    round(hi, 6),
        "ci_method":  "wilson",
        "min_n_pass": n_gate(n),
        "slice":      slice_label,
    })
```
This is the natural place to add a `p_value` column via the same `emit()` closure (per CONTEXT's "Reusable Assets" note — `build_manifest_rows` already iterates every bucket in the grid). The BH correction itself is a **second pass over the full `rows` list** after all `emit()` calls complete (since BH requires the full p-value distribution sorted, not per-row computation) — add it as a separate function, e.g. `apply_bh_correction(rows: list[dict]) -> list[dict]`, called once in `main()` right before `pd.DataFrame(manifest_rows).to_csv(...)` (lines 293-295), mutating/adding `p_value`, `bh_rank`, `bh_threshold`, `bh_significant` keys onto each row dict — additive columns only, matching the "existing manifest columns must not change" constraint (CONTEXT domain section).

**Slicing pattern for walk-forward folds** (`slice_df`, lines 214-225):
```python
def slice_df(df: pd.DataFrame, oos: bool = False) -> pd.DataFrame:
    """Return the discovery or OOS slice of *df* based on OOS_START.
    ...
    Returns a copy to prevent SettingWithCopyWarning on downstream writes.
    """
    boundary = pd.Timestamp(OOS_START)
    if oos:
        return df[df.index >= boundary].copy()
    return df[df.index < boundary].copy()
```
Walk-forward fold slicing (D-04, D-05, D-06) should add a sibling function, e.g. `slice_fold(df: pd.DataFrame, train_end: str, test_end: str) -> tuple[pd.DataFrame, pd.DataFrame]`, using the same `pd.Timestamp(...)` boundary + `.copy()` pattern, and must only ever operate on `df.index < OOS_START` data (call `slice_df(df, oos=False)` first, then sub-slice). Frozen fold boundary dates should be declared as new module-level constants alongside `OOS_START` in `cisd_analysis.py`, with the same "Do NOT recompute at runtime" comment style — check `cisd_analysis.py` around line 37-39 / 144 for the exact declaration + `__all__`-style export list to extend.

**CLI flag pattern** (`parse_args`, lines 230-239, and slice-label dispatch in `main()`, lines 244-296):
```python
parser.add_argument(
    "--oos",
    action="store_true",
    help="Evaluate on the OOS (out-of-sample) slice. Default: discovery (train) slice.",
)
```
A new `--walk-forward` flag should mirror this `action="store_true"` style, with `main()` branching similarly to how `args.oos` currently branches (banner print, slice_label, manifest path suffix). The walk-forward path likely writes a **new sibling artifact** (e.g. `validation_manifest_walkforward.csv`) using the `_manifest_path(slice_label)` helper (lines 25-27) rather than overloading the existing discovery/oos manifest shape — matches CONTEXT's "additive columns/artifacts only" constraint and D-03's requirement that discovery/OOS manifests stay untouched by walk-forward.

**Error handling pattern** (compute-failure guard, lines 146-153):
```python
try:
    data = compute_fn(df)
except Exception as exc:  # noqa: BLE001
    print(
        f"[warn] {key}/{instrument}/{tf_label}: compute failed"
        f" ({type(exc).__name__}: {exc}); skipping"
    )
    continue  # degrade gracefully on empty/missing slice
```
Any new per-fold compute loop (walk-forward) should degrade the same way — skip a fold on failure with a `[warn]` print, never crash the whole run, matching the project's graceful-degradation convention for empty/small slices.

---

### `scripts/build_reconcile_findings.py` — verdict augmentation (if touched)

**Analog:** itself, `determine_verdict()` (lines 69-113) and `_side()` (lines 57-66).

Per D-03, the BH correction fires at the discovery-manifest stage only — the OOS manifest and `validation_findings.csv` schema are explicitly **not** separately corrected. If the planner decides `determine_verdict()` needs a `bh_significant` input, follow the existing signature/docstring style exactly:
```python
def determine_verdict(
    discovery_rate: float,
    discovery_n: float | None,
    oos_rate: float,
    oos_n: float | None,
) -> str:
    """Return a lowercase verdict token for one bucket row.
    ...
    Notes
    -----
    D-01: Eligibility is gated on discovery_n >= MIN_N only.
    D-02: Confirmed iff eligible and OOS rate is on the same side of 0.50.
    ...
    """
```
Keep the "D-xx" decision-ID references in docstrings — this is the established convention for traceability back to CONTEXT.md decisions in this file.

---

### `tests/test_validation_harness.py` — new test additions

**Analog:** itself; existing test structure at lines 84-135 (`wilson_ci`/`n_gate` tests) and 137-203 (`build_manifest_rows` tests with `patch("scripts.build_validation.ANALYSES", ...)`).

**Known-value test pattern** (lines 86-94):
```python
def test_wilson_ci_known_value() -> None:
    """wilson_ci(100, 60) at 95% CI should match expected Wilson score bounds.
    ...
    """
    lo, hi = wilson_ci(100, 60)
    assert 0.495 <= lo <= 0.510, f"CI lower bound {lo:.4f} outside expected range [0.495, 0.510]"
    assert 0.685 <= hi <= 0.705, f"CI upper bound {hi:.4f} outside expected range [0.685, 0.705]"
```
New p-value / BH-correction tests should use this "known value with tolerance band + descriptive assertion message" style — e.g. a hand-computed BH-adjusted p-value for a small fixed list of p-values, asserted within a tolerance.

**Boundary test pattern** (lines 128-134, `n_gate`):
```python
def test_n_gate_boundary() -> None:
    """n_gate must return True exactly when n >= MIN_N (boundary: 49=False, 50=True, 51=True)."""
    min_n = cisd_analysis.MIN_N  # 50
    assert n_gate(min_n - 1) is False, f"n={min_n-1} should fail gate"
    assert n_gate(min_n) is True, f"n={min_n} should pass gate"
    assert n_gate(min_n + 1) is True, f"n={min_n+1} should pass gate"
    assert n_gate(0) is False
```
Walk-forward fold-boundary tests (partition, no-overlap, all-discovery, all-oos — mirroring `test_slice_df_partition`/`test_slice_df_no_overlap`/`test_slice_df_all_discovery`/`test_slice_df_all_oos` at lines 12-59) should be written for the fold-slicing function using synthetic `pd.date_range` DataFrames exactly like those four existing tests.

**Mock/patch pattern for manifest-row tests** (lines 155-172):
```python
def test_build_manifest_rows_schema() -> None:
    REQUIRED_COLS = {...}
    dummy = pd.DataFrame()
    mock_compute = lambda df: _basic_compute_return()  # noqa: E731
    fake_analyses = {"basic": ("Basic", mock_compute, None)}

    with patch("scripts.build_validation.ANALYSES", fake_analyses):
        rows = build_manifest_rows(["basic"], dummy, dummy, "1H", "discovery")

    assert len(rows) >= 1, "Expected at least one manifest row"
    for row in rows:
        missing = REQUIRED_COLS - row.keys()
        assert not missing, f"Row missing columns: {missing}"
```
Use `unittest.mock.patch("scripts.build_validation.ANALYSES", fake_analyses)` the same way to test that the new `p_value` column appears in every emitted row without requiring real data files.

## Shared Patterns

### Pure-stdlib statistics, no new dependencies
**Source:** `wilson_ci()` / `_erfinv` fallback, `scripts/build_validation.py:43-94`
**Apply to:** BH correction function and the new p-value test statistic (binomial/normal-approx z-test)
```python
try:
    _erfinv = math.erfinv
except AttributeError:
    def _erfinv(x: float) -> float:
        ...
```
Confirmed: no scipy/statsmodels in `.venv/lib/python3.12/site-packages/`. Any new statistical function must be implementable with `math` alone (or plain Python loops/sorts for BH ranking — no numpy required either, though numpy is already a project dependency and may be used for vectorized CI computation across manifest rows if helpful).

### Frozen-constant boundary dates ("do not recompute at runtime")
**Source:** `OOS_START` declaration and comment convention in `cisd_analysis.py` (imported at `scripts/build_validation.py:17`)
**Apply to:** New walk-forward fold boundary constants
```python
OOS_START = "2024-04-30"  # frozen 70th-percentile date; do NOT recompute at runtime —
                            # appending data must not silently shift the OOS boundary.
```
New fold-boundary constants (D-06) must be declared the same way: hardcoded string dates, with an explicit comment documenting how they were derived and a warning against runtime recomputation. Read `cisd_analysis.py` lines 30-45 directly (not shown above — Read that range before editing) to see the exact declaration site and `__all__`/export-list pattern (line 144) that must be extended for the new constants to be importable.

### Additive-only manifest columns
**Source:** CONTEXT.md domain constraint + `build_manifest_rows()` row-dict shape (`scripts/build_validation.py:125-139`)
**Apply to:** Any new column added to `validation_manifest_discovery.csv`
Existing columns (`rate`, `n`, `successes`, `ci_low`, `ci_high`, `ci_method`, `min_n_pass`, `slice`, plus `analysis`/`timeframe`/`instrument`/`direction`/`bucket`) must not be renamed, reordered, or removed. New columns (`p_value`, `bh_significant`, etc.) are appended as new dict keys in the `emit()` closure — never restructure the existing keys.

### Graceful degradation on missing/failed inputs
**Source:** `scripts/build_validation.py:146-153` (compute failure) and `scripts/build_reconcile_findings.py:132-139` (missing manifest file)
**Apply to:** Walk-forward fold loop (a fold with too little data should warn+skip, not crash) and any BH-correction edge cases (e.g. all-p-values-NaN)
```python
if not DISCOVERY_MANIFEST_PATH.exists():
    print(f"[error] discovery manifest not found: {DISCOVERY_MANIFEST_PATH}")
    print("Run `python3 scripts/build_validation.py` (discovery) first.")
    sys.exit(1)
```

## No Analog Found

None — this phase extends an existing, well-established validation-harness module family; every new piece of logic (p-value test, BH correction, walk-forward folds) has a directly analogous existing pattern in `scripts/build_validation.py` itself (Wilson CI, n_gate, slice_df, build_manifest_rows) to copy structurally.

## Metadata

**Analog search scope:** `scripts/`, `tests/test_validation_harness.py`, `cisd_analysis.py` (constants section)
**Files scanned:** `scripts/build_validation.py` (full, 299 lines), `scripts/build_reconcile_findings.py` (full, 192 lines), `tests/test_validation_harness.py` (full, 203 lines), `cisd_analysis.py` (grep for OOS_START/MIN_N/CI_LEVEL)
**Pattern extraction date:** 2026-07-10
