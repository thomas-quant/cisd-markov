# Testing Patterns

**Analysis Date:** 2026-06-12

## Test Framework

**Runner:**
- pytest (installed in `.venv/bin/pytest`, version 9.0.2)
- Config: No `pytest.ini`, `pyproject.toml`, or `setup.cfg` — pytest uses defaults

**Assertion Library:**
- Plain `assert` for equality and membership
- `pytest.approx` for floating-point comparisons
- `pd.testing.assert_frame_equal` for DataFrame equality

**Run Commands:**
```bash
.venv/bin/python -m pytest          # Run all tests
.venv/bin/python -m pytest -q       # Quiet mode
.venv/bin/python -m pytest tests/test_research_extensions.py   # Single file
.venv/bin/python -m pytest -k "fvg" # Filter by name
```

56 tests collected; all pass as of 2026-06-12.

## Test File Organization

**Location:**
- Separate `tests/` directory at repo root — not co-located with source
- No `conftest.py`

**Naming:**
- Files: `test_<module_or_integration_area>.py`
- Functions: `test_<function_under_test>_<condition_or_expected_behavior>()`

**Files:**
```
tests/
├── test_expectancy_builder.py        # tests for scripts/build_expectancy.py
├── test_forward_returns_builder.py   # tests for scripts/build_forward_returns.py
├── test_research_extensions.py       # tests for cisd_analysis annotation/compute fns
├── test_swing_smt_integration.py     # tests for SMT annotation + prepare_pair
└── test_research_extensions.py.premerge   # pre-merge snapshot (not run by pytest)
```

## Test Structure

**Suite Organization:**
No test classes — all tests are flat module-level functions grouped by theme within a file:
```python
# test_research_extensions.py

def test_compute_three_bar_swings_marks_local_extrema():
    ...

def test_annotate_cisd_research_sets_mid0_mid1_fvg_and_hold_columns():
    ...

def test_prepare_returns_research_annotation_columns():
    ...
```

**Patterns:**
- Arrange: build a minimal DataFrame fixture via a local helper function
- Act: call the function under test directly
- Assert: plain `assert` on specific keys, columns, or values
- No `setup`/`teardown`; state is created fresh per test

## Mocking

**Framework:** `monkeypatch` (pytest built-in)

**Patterns:**
```python
# Replace an external scanner dependency
monkeypatch.setattr(
    cisd_analysis,
    "_scan_swing_smt_events",
    lambda df_nq, df_es: pd.DataFrame(
        [{"signal_type": "Bullish Swing SMT", "created_ts": index[2], ...}]
    ),
)

# Spy on a method call to assert it was called exactly once
original_rolling = pd.Series.rolling
def spy_rolling(self, *args, **kwargs):
    nonlocal calls
    calls += 1
    return original_rolling(self, *args, **kwargs)
monkeypatch.setattr(pd.Series, "rolling", spy_rolling)
```

**What to Mock:**
- `cisd_analysis._scan_swing_smt_events` — avoids the real SMT package dependency
- `build_forward_returns.REPO_ROOT` — used with `monkeypatch.setattr(fr, "REPO_ROOT", ...)` to test path resolution with `tmp_path`
- Side-effect dependencies (I/O, external packages) are mocked; pure computation is not

**What NOT to Mock:**
- pandas/numpy operations
- `prepare()`, `resample_ohlcv()`, `barrier_hit()` — these are called directly with inline DataFrames

## Fixtures and Factories

No `@pytest.fixture` decorators — fixtures are plain helper functions with leading `_`:

**Pattern:**
```python
# test_research_extensions.py
def _research_frame_for_fvg():
    index = pd.date_range("2026-01-01 09:30", periods=16, freq="15min")
    return pd.DataFrame({
        "open": [...], "high": [...], "low": [...], "close": [...],
        "volume": [100] * 16,
        "cisd_type": [None, None, "bullish", ...],
    }, index=index)

# test_forward_returns_builder.py
def _prepared_fixture() -> pd.DataFrame:
    index = pd.date_range("2026-02-01 09:30", periods=12, freq="15min")
    return pd.DataFrame({...}, index=index)

# test_expectancy_builder.py
def _bar(close, high, low, cisd_type=None, **flags):
    return {"open": close, "close": close, "high": high, "low": low,
            "cisd_type": cisd_type, **flags}

def _frame(rows: list[dict]) -> pd.DataFrame:
    index = pd.date_range("2026-02-01 09:30", periods=len(rows), freq="15min")
    df = pd.DataFrame(rows, index=index)
    for col, default in ex.CASE_FLAG_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
    return df
```

**Key characteristics:**
- All fixture DataFrames use `pd.date_range` with a fixed `"2026-01-01 09:30"` or `"2026-02-01 09:30"` start and a `freq="15min"` index
- Fixtures are minimal — just enough bars to exercise the logic under test
- `cisd_type` column is explicitly set with `None` for non-CISD bars and `"bullish"`/`"bearish"` for CISD bars
- The `_frame` + `_bar` factory pattern in `test_expectancy_builder.py` composably builds row lists:
  ```python
  rows = [_bar(100, 101, 98, "bullish")]
  for c in (101, 102, 103, 104, 105, 106, 107):
      rows.append(_bar(c, c + 1, 100))
  events = ex.build_event_r_multiples(_frame(rows), "NQ")
  ```

**Location:**
- All fixture helpers are defined within the same test file that uses them — no shared fixture module

## Coverage

**Requirements:** None enforced — no coverage config or thresholds

**View Coverage:**
```bash
.venv/bin/python -m pytest --cov=cisd_analysis --cov=scripts
```

**Observed gaps:**
- `main()` in `cisd_analysis.py` and `scripts/build_expectancy.py` are not tested (requires real parquet data)
- `chart_*` functions in `cisd_analysis.py` are not tested (matplotlib rendering)
- `render_html` template emission is tested via string presence checks (not DOM parsing)

## Test Types

**Unit Tests:**
- `test_research_extensions.py`: Fine-grained unit tests on `_compute_three_bar_swings`, `_annotate_cisd_research`, `_classify_fvg_hold`, `compute_cisd_fvg`, `compute_fvg_hold`, `compute_sweep`, `compute_sssf_swing`, `build_csv_rows`
- `test_expectancy_builder.py`: Unit tests on `build_event_r_multiples`, `case_masks`, `summarize_horizon`
- `test_forward_returns_builder.py`: Unit tests on combo key builders, `percentile_payload`, `build_forward_return_rows`, `apply_family_filters`, `aggregate_family_payload`

**Integration Tests:**
- `test_swing_smt_integration.py`: Tests `prepare_pair` with monkeypatched scanner; tests `_annotate_swing_smt_from_events` with realistic event DataFrames; tests `resample_ohlcv` alias handling
- `test_forward_returns_builder.py`: Tests `render_html` / `write_html` end-to-end with synthetic data structs; tests `resolve_data_root` with `tmp_path`

**E2E Tests:**
- `test_swing_smt_integration.py::test_prepare_pair_swing_smt_columns_exist_when_scanner_runs` — runs against the real SMT package when `_SMT_PKG_PATH` exists; skipped otherwise via `pytest.skip()`

## Common Patterns

**Parametrize for input variation:**
```python
@pytest.mark.parametrize("direction", ["sideways", ""])
def test_classify_fvg_hold_rejects_invalid_direction(direction):
    with pytest.raises(ValueError, match="direction"):
        cisd_analysis._classify_fvg_hold(df, 2, direction, "close_near")

@pytest.mark.parametrize("rule,normalized_rule", [("1H", "1h"), ("4H", "4h")])
def test_resample_ohlcv_accepts_legacy_uppercase_hour_aliases(rule, normalized_rule):
    pd.testing.assert_frame_equal(
        cisd_analysis.resample_ohlcv(df, rule),
        cisd_analysis.resample_ohlcv(df, normalized_rule),
    )
```

**Error Testing:**
```python
with pytest.raises(ValueError, match="cisd_type"):
    cisd_analysis._annotate_cisd_research(df)

with pytest.raises(ValueError, match=missing_column):
    _annotate_swing_smt_from_events(df, events, instrument="NQ")
```

**Floating-point Assertions:**
```python
assert row["risk"] == pytest.approx(2.0)
assert [row[f"r_{h}"] for h in ex.HORIZONS] == pytest.approx(expected)
assert stats["mean_r"] == pytest.approx((2.0 - 1.0 + 0.5 - 0.5) / 4)
```

**Schema / Column Presence Assertions:**
```python
assert {"cisd_type", "has_dir_fvg_mid0", "has_dir_sweep", ...} <= set(prepared.columns)
assert set(["instrument", "cisd_type", "forward_return_pct", ...]) <= set(rows.columns)
```

**Empty Output Assertions:**
```python
rows = fr.build_forward_return_rows(prepared, "ES")
assert rows.empty
assert {"instrument", "smt", "forward_return_pct", ...} <= set(rows.columns)
```

**Filesystem Testing (tmp_path):**
```python
def test_write_html_persists_generated_family_controls(tmp_path):
    output = tmp_path / "forward_returns.html"
    fr.write_html(output, data, config)
    html = output.read_text(encoding="utf-8")
    assert output.exists()
    assert "Core" in html
```

**Conditional Skip:**
```python
def test_prepare_pair_swing_smt_columns_exist_when_scanner_runs():
    if not _SMT_PKG_PATH.exists():
        pytest.skip("SMT package not available")
    ...
```

---

*Testing analysis: 2026-06-12*
