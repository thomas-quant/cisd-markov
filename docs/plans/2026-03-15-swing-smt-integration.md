# Swing SMT Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore library-backed Swing SMT tagging for CISD bars and the `smt_cisd` barrier analysis using the external historical SMT scanner.

**Architecture:** Add a paired-timeframe preparation flow in `cisd_analysis.py` that resamples both instruments together, runs the external historical scanner once per timeframe, and annotates each instrument's prepared DataFrame with left-looking Swing SMT tags. Then add `smt_cisd` as a standalone analysis that consumes those tags, and narrow the docs to the actually restored CLI surface.

**Tech Stack:** Python 3, pandas, numpy, matplotlib, pytest, external local package at `/mnt/e/backup/code/Finance/Misc/SMT`

---

### Task 1: Add failing tests for left-only Swing SMT annotation

**Files:**
- Create: `tests/test_swing_smt_integration.py`
- Test: `tests/test_swing_smt_integration.py`

**Step 1: Write the failing test**

```python
import pandas as pd

from cisd_analysis import _annotate_swing_smt_from_events


def test_annotate_swing_smt_uses_left_window_and_sets_role():
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    df = pd.DataFrame(
        {
            "cisd_type": [None, "bullish", "bullish", "bullish", "bearish", None],
        },
        index=index,
    )
    events = pd.DataFrame(
        [
            {
                "signal_type": "Bullish Swing SMT",
                "created_ts": index[1],
                "sweeping_asset": "NQ",
                "failing_asset": "ES",
            },
            {
                "signal_type": "Bearish Swing SMT",
                "created_ts": index[0],
                "sweeping_asset": "ES",
                "failing_asset": "NQ",
            },
        ]
    )

    nq = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    es = _annotate_swing_smt_from_events(df, events, instrument="ES")

    assert nq.loc[index[1], "swing_smt_tag"] == "w/ SMT"
    assert nq.loc[index[3], "swing_smt_tag"] == "w/ SMT"   # t-2 match still counts
    assert nq.loc[index[4], "swing_smt_tag"] == "no SMT"   # t-4 bearish event must not count
    assert nq.loc[index[1], "swing_smt_role"] == "swept"
    assert es.loc[index[1], "swing_smt_role"] == "failed_to_sweep"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_swing_smt_integration.py::test_annotate_swing_smt_uses_left_window_and_sets_role -v`

Expected: FAIL with import error or missing `_annotate_swing_smt_from_events`

**Step 3: Write minimal implementation**

Add a low-level helper in `cisd_analysis.py` near the preparation/helpers section:

```python
def _annotate_swing_smt_from_events(df: pd.DataFrame, events: pd.DataFrame, instrument: str) -> pd.DataFrame:
    # copy df
    # map event signal_type -> bullish/bearish
    # for each timestamp, keep the latest same-direction event in [t-2, t]
    # set has_swing_smt / swing_smt_tag / swing_smt_match_ts / swing_smt_role
    return annotated_df
```

Use only the event table for this helper. Do not touch the external SMT import path yet.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_swing_smt_integration.py::test_annotate_swing_smt_uses_left_window_and_sets_role -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_swing_smt_integration.py cisd_analysis.py
git commit -m "test: cover left-window swing SMT annotation"
```

### Task 2: Add paired timeframe preparation with the historical SMT scanner

**Files:**
- Modify: `cisd_analysis.py:48-97`
- Modify: `cisd_analysis.py:686-748`
- Modify: `tests/test_swing_smt_integration.py`
- Test: `tests/test_swing_smt_integration.py`

**Step 1: Write the failing test**

Extend the test file with a pair-preparation test that stubs the scanner output:

```python
import cisd_analysis


def test_prepare_pair_applies_vectorized_swing_smt_annotations(monkeypatch):
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    minute = pd.DataFrame(
        {
            "open": [1, 2, 3, 4, 5, 6],
            "high": [2, 3, 4, 5, 6, 7],
            "low": [0, 1, 2, 3, 4, 5],
            "close": [1.5, 2.5, 3.5, 4.5, 5.5, 6.5],
            "volume": [10, 10, 10, 10, 10, 10],
        },
        index=index,
    )

    monkeypatch.setattr(
        cisd_analysis,
        "_scan_swing_smt_events",
        lambda df_nq, df_es: pd.DataFrame(
            [
                {
                    "signal_type": "Bullish Swing SMT",
                    "created_ts": index[2],
                    "sweeping_asset": "NQ",
                    "failing_asset": "ES",
                }
            ]
        ),
    )

    df_nq, df_es = cisd_analysis.prepare_pair(minute, minute, "15min", with_swing_smt=True)

    assert "swing_smt_tag" in df_nq.columns
    assert "swing_smt_tag" in df_es.columns
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_swing_smt_integration.py::test_prepare_pair_applies_vectorized_swing_smt_annotations -v`

Expected: FAIL because `prepare_pair` and `_scan_swing_smt_events` do not exist yet

**Step 3: Write minimal implementation**

Add the external-SMT helpers and pair-preparation path in `cisd_analysis.py`:

```python
SMT_LOOKBACK = 20
_SMT_PKG_PATH = Path("/mnt/e/backup/code/Finance/Misc/SMT")


def _scan_swing_smt_events(df_nq: pd.DataFrame, df_es: pd.DataFrame) -> pd.DataFrame:
    # import scan_smts_historical lazily from the external package
    # convert lowercase OHLC -> Open/High/Low/Close copies
    # validate aligned indices
    # call scan_smts_historical(..., enable_swing=True, enable_micro=False, enable_fvg=False)
    # return only swing rows


def prepare_pair(df_nq_1m: pd.DataFrame, df_es_1m: pd.DataFrame, rule: str, with_swing_smt: bool = False):
    # resample both
    # prepare both
    # optionally annotate both via _scan_swing_smt_events + _annotate_swing_smt_from_events
    # return df_nq, df_es
```

Update `main()` to call `prepare_pair(...)` instead of preparing NQ and ES independently.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_swing_smt_integration.py::test_prepare_pair_applies_vectorized_swing_smt_annotations -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_swing_smt_integration.py cisd_analysis.py
git commit -m "feat: add paired swing SMT preparation"
```

### Task 3: Restore the `smt_cisd` analysis with a regression test

**Files:**
- Modify: `tests/test_swing_smt_integration.py`
- Modify: `cisd_analysis.py:155-525`
- Modify: `cisd_analysis.py:528-748`
- Test: `tests/test_swing_smt_integration.py`

**Step 1: Write the failing test**

Add a regression test for `compute_smt_cisd`:

```python
def test_compute_smt_cisd_splits_runs_by_swing_smt_tag():
    index = pd.date_range("2026-01-01 09:30", periods=5, freq="15min")
    df = pd.DataFrame(
        {
            "open": [10, 9, 11, 12, 12],
            "high": [11, 10, 13, 13, 14],
            "low": [9, 8, 10, 11, 11],
            "close": [9, 11, 12, 12, 13],
            "direction": ["bearish", "bullish", "bullish", "neutral", "bullish"],
            "prev_close": [None, 9, 11, 12, 12],
            "prev_direction": [None, "bearish", "bullish", "bullish", "neutral"],
            "prev_high": [None, 11, 10, 13, 13],
            "prev_low": [None, 9, 8, 10, 11],
            "cisd_type": [None, "bullish", None, None, None],
            "swing_smt_tag": ["no SMT", "w/ SMT", "no SMT", "no SMT", "no SMT"],
        },
        index=index,
    )

    stats = compute_smt_cisd(df)

    assert stats["bullish"]["w/ SMT"]["total"] == 1
    assert stats["bullish"]["no SMT"]["total"] == 0
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_swing_smt_integration.py::test_compute_smt_cisd_splits_runs_by_swing_smt_tag -v`

Expected: FAIL because `compute_smt_cisd` is missing

**Step 3: Write minimal implementation**

Add the new analysis in `cisd_analysis.py`:

```python
def compute_smt_cisd(df: pd.DataFrame) -> dict:
    stats = {
        "bullish": {"w/ SMT": {"total": 0, "runs": 0}, "no SMT": {"total": 0, "runs": 0}},
        "bearish": {"w/ SMT": {"total": 0, "runs": 0}, "no SMT": {"total": 0, "runs": 0}},
    }
    ...


def chart_smt_cisd(ax, data_nq, data_es):
    ...
```

Register `"smt_cisd"` in `ANALYSES`, teach `build_csv_rows(...)` how to flatten it, and add it to `STANDALONE_KEYS` / `FILENAMES` so `python3 cisd_analysis.py smt_cisd` produces `output/SMT_CISD_All_Timeframes.png`.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_swing_smt_integration.py::test_compute_smt_cisd_splits_runs_by_swing_smt_tag -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_swing_smt_integration.py cisd_analysis.py
git commit -m "feat: restore swing SMT CISD analysis"
```

### Task 4: Align the docs and verify the SMT-backed CLI path

**Files:**
- Modify: `README.md:153-204`
- Modify: `CLAUDE.md:7-65`
- Test: `tests/test_swing_smt_integration.py`

**Step 1: Write the failing test**

Add one smoke-style test for the real paired preparation path, using the real scanner only if the external package path exists:

```python
def test_prepare_pair_swing_smt_columns_exist_when_scanner_runs():
    ...
    df_nq, df_es = prepare_pair(df_nq_1m, df_es_1m, "15min", with_swing_smt=True)
    assert {"has_swing_smt", "swing_smt_tag", "swing_smt_match_ts", "swing_smt_role"} <= set(df_nq.columns)
```

Keep the fixture small and deterministic. If the real scanner path makes this too brittle, skip this exact test and rely on the Task 2 stub test plus the CLI smoke command below.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_swing_smt_integration.py -v`

Expected: at least the new smoke assertion fails until docs/code are aligned

**Step 3: Write minimal implementation**

Update the docs to match the actual restored surface:

- `README.md`: document `smt_cisd`, the external SMT dependency, and the left-only `[t-2, t]` matching rule
- `CLAUDE.md`: replace the old per-row `check_swing_smt` note with the historical `scan_smts_historical(...)` path and the new classification fields
- remove or clearly mark unavailable `fan*` / `export_html` commands if they are still not implemented in this pass

Then run the real CLI smoke command:

Run: `python3 cisd_analysis.py smt_cisd`

Expected: generates `output/SMT_CISD_All_Timeframes.png` without import/index errors

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_swing_smt_integration.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_swing_smt_integration.py cisd_analysis.py README.md CLAUDE.md
git commit -m "docs: align swing SMT analysis with vectorized scanner"
```
