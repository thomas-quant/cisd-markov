# CISD FVG, Sweep, and Swing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reusable FVG, sweep, and swing annotations to the CISD pipeline, then ship the five new analyses `cisd_fvg`, `fvg_hold`, `cisd_fvg_interaction`, `sweep`, and `sssf_swing`.

**Architecture:** Keep the existing single-file architecture in `cisd_analysis.py`, but push all new event semantics into a single-instrument annotation pass that runs inside `prepare()`. The new compute functions should read only precomputed columns, while chart registration, CSV flattening, and standalone figure wiring follow the existing `smt_cisd` pattern.

**Tech Stack:** Python 3, pandas, numpy, matplotlib, pytest

---

## File Map

- `cisd_analysis.py`
  - Add research constants near the existing top-level configuration block.
  - Add helper functions for three-bar swing detection, same-direction FVG detection, FVG hold classification, and sweep detection in the existing preparation section around [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L48).
  - Extend `prepare()` around [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L81) so every single-instrument prepared DataFrame includes the new research columns.
  - Add five new `compute_*` and `chart_*` functions in the compute/chart sections around [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L292).
  - Register the new analyses in `ANALYSES`, `build_csv_rows()`, `build_figure()`, `build_standalone_figure()`, `STANDALONE_KEYS`, and `FILENAMES` around [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L691).

- `tests/test_research_extensions.py`
  - Create a focused regression suite for the new annotation helpers and analysis outputs.
  - Reuse small synthetic DataFrames instead of loading parquet fixtures.

- `README.md`
  - Document the new CLI keys and the meaning of the new research outputs.
  - Note the FVG formation rule, FVG hold window, sweep tolerance window, and swing bucket meanings.

- `CLAUDE.md`
  - Update the architecture section so future agents know the new prepared columns and the new standalone analysis keys.

- `docs/research_backlog.md`
  - Mark the implemented `[next]` items as done once the code and docs are in place.

### Task 1: Add FVG and Swing Annotation Foundations

**Files:**
- Create: `tests/test_research_extensions.py`
- Modify: `cisd_analysis.py:48-234`
- Test: `tests/test_research_extensions.py`

- [ ] **Step 1: Write the failing tests for three-bar swings and FVG tagging**

```python
import pandas as pd
import cisd_analysis


def _research_frame_for_fvg() -> pd.DataFrame:
    index = pd.date_range("2026-01-01 09:30", periods=16, freq="15min")
    return pd.DataFrame(
        {
            "open":   [11, 12,  9, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25],
            "high":   [12, 11, 13, 15, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26],
            "low":    [10,  8,  9, 12, 13, 14, 15.5, 16.5, 17.5, 18.5, 19.5, 20.5, 21.5, 22.5, 23.5, 24.5],
            "close":  [11.5, 9, 12, 14, 13.5, 15.5, 16.5, 17.5, 18.5, 19.5, 20.5, 21.5, 22.5, 23.5, 24.5, 25.5],
            "volume": [100] * 16,
            "cisd_type": [None, None, "bullish", None, "bullish", None, None, None, None, None, None, None, None, None, None, None],
        },
        index=index,
    )


def test_compute_three_bar_swings_marks_local_extrema():
    df = _research_frame_for_fvg()

    swing_low, swing_high = cisd_analysis._compute_three_bar_swings(df)

    assert bool(swing_low.iloc[1])
    assert not bool(swing_low.iloc[2])
    assert bool(swing_high.iloc[3])


def test_annotate_cisd_research_sets_mid0_mid1_fvg_and_hold_columns():
    df = _research_frame_for_fvg()

    annotated = cisd_analysis._annotate_cisd_research(df)

    assert annotated.loc[df.index[2], "has_dir_fvg_mid0"]
    assert annotated.loc[df.index[2], "fvg_mid0_hold_close_near"] == "held"
    assert annotated.loc[df.index[2], "fvg_mid0_hold_wick_far"] == "held"

    assert annotated.loc[df.index[4], "has_dir_fvg_mid1"]
    assert annotated.loc[df.index[4], "fvg_mid1_hold_close_near"] == "held"
    assert annotated.loc[df.index[4], "fvg_mid1_hold_wick_far"] == "held"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m pytest tests/test_research_extensions.py::test_compute_three_bar_swings_marks_local_extrema tests/test_research_extensions.py::test_annotate_cisd_research_sets_mid0_mid1_fvg_and_hold_columns -v`

Expected: FAIL with `AttributeError` because `_compute_three_bar_swings` and `_annotate_cisd_research` do not exist yet.

- [ ] **Step 3: Write the minimal FVG and swing annotation implementation**

Add the new constants near the current configuration block in [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L48):

```python
FVG_HOLD_LOOKAHEAD = 10
SWEEP_TOLERANCE = 5
SWEEP_SWING_LOOKBACK = 20
```

Add the annotation helpers near `prepare()` in [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L81):

```python
def _compute_three_bar_swings(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    swing_low = (df["low"] < df["low"].shift(1)) & (df["low"] < df["low"].shift(-1))
    swing_high = (df["high"] > df["high"].shift(1)) & (df["high"] > df["high"].shift(-1))
    return swing_low.fillna(False), swing_high.fillna(False)


def _has_directional_fvg(df: pd.DataFrame, middle_idx: int, direction: str) -> bool:
    if middle_idx - 1 < 0 or middle_idx + 1 >= len(df):
        return False
    left = df.iloc[middle_idx - 1]
    right = df.iloc[middle_idx + 1]
    if direction == "bullish":
        return left["high"] < right["low"]
    return left["low"] > right["high"]


def _classify_fvg_hold(df: pd.DataFrame, middle_idx: int, direction: str, failure_mode: str) -> str:
    last_idx = middle_idx + FVG_HOLD_LOOKAHEAD
    if last_idx >= len(df):
        return "none"

    left = df.iloc[middle_idx - 1]
    future = df.iloc[middle_idx + 1:last_idx + 1]
    if direction == "bullish":
        if failure_mode == "close_near":
            failed = (future["close"] < left["high"]).any()
        else:
            failed = (future["low"] < left["low"]).any()
    else:
        if failure_mode == "close_near":
            failed = (future["close"] > left["low"]).any()
        else:
            failed = (future["high"] > left["high"]).any()
    return "failed" if failed else "held"


def _annotate_cisd_research(df: pd.DataFrame) -> pd.DataFrame:
    if "cisd_type" not in df.columns:
        raise ValueError("df must contain cisd_type column")

    annotated = df.copy()
    swing_low, swing_high = _compute_three_bar_swings(annotated)
    annotated["has_dir_fvg_mid0"] = False
    annotated["has_dir_fvg_mid1"] = False
    annotated["fvg_mid0_hold_close_near"] = "none"
    annotated["fvg_mid0_hold_wick_far"] = "none"
    annotated["fvg_mid1_hold_close_near"] = "none"
    annotated["fvg_mid1_hold_wick_far"] = "none"
    annotated["has_dir_sweep"] = False
    annotated["prev_bar_is_dir_swing"] = False
    annotated["cisd_bar_is_dir_swing"] = False

    for ts, row in annotated[annotated["cisd_type"].notna()].iterrows():
        idx = annotated.index.get_loc(ts)
        direction = row["cisd_type"]
        if _has_directional_fvg(annotated, idx, direction):
            annotated.iat[idx, annotated.columns.get_loc("has_dir_fvg_mid0")] = True
            annotated.iat[idx, annotated.columns.get_loc("fvg_mid0_hold_close_near")] = _classify_fvg_hold(annotated, idx, direction, "close_near")
            annotated.iat[idx, annotated.columns.get_loc("fvg_mid0_hold_wick_far")] = _classify_fvg_hold(annotated, idx, direction, "wick_far")
        if _has_directional_fvg(annotated, idx + 1, direction):
            annotated.iat[idx, annotated.columns.get_loc("has_dir_fvg_mid1")] = True
            annotated.iat[idx, annotated.columns.get_loc("fvg_mid1_hold_close_near")] = _classify_fvg_hold(annotated, idx + 1, direction, "close_near")
            annotated.iat[idx, annotated.columns.get_loc("fvg_mid1_hold_wick_far")] = _classify_fvg_hold(annotated, idx + 1, direction, "wick_far")
    return annotated
```

Wire the helper into `prepare()` in [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L81):

```python
def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["direction"] = np.where(
        df["close"] > df["open"], "bullish",
        np.where(df["close"] < df["open"], "bearish", "neutral"),
    )
    df["prev_close"] = df["close"].shift(1)
    df["prev_direction"] = df["direction"].shift(1)
    df["prev_high"] = df["high"].shift(1)
    df["prev_low"] = df["low"].shift(1)
    df["cisd_type"] = np.select(
        [
            (df["prev_direction"] == "bearish") & (df["close"] > df["prev_close"]),
            (df["prev_direction"] == "bullish") & (df["close"] < df["prev_close"]),
        ],
        ["bullish", "bearish"],
        default=None,
    )
    return _annotate_cisd_research(df)
```

- [ ] **Step 4: Run the tests again to verify they pass**

Run: `python3 -m pytest tests/test_research_extensions.py::test_compute_three_bar_swings_marks_local_extrema tests/test_research_extensions.py::test_annotate_cisd_research_sets_mid0_mid1_fvg_and_hold_columns -v`

Expected: PASS

- [ ] **Step 5: Commit the foundation**

```bash
git add tests/test_research_extensions.py cisd_analysis.py
git commit -m "feat: add CISD FVG annotation foundations"
```

### Task 2: Add Sweep and Direction-Specific Swing Position Tags

**Files:**
- Modify: `tests/test_research_extensions.py`
- Modify: `cisd_analysis.py:81-234`
- Test: `tests/test_research_extensions.py`

- [ ] **Step 1: Write the failing tests for sweep tolerance and swing position buckets**

Append these tests to [tests/test_research_extensions.py](/mnt/e/backup/code/finance/research/cisd markov/tests/test_research_extensions.py):

```python
def _research_frame_for_sweep_and_swing() -> pd.DataFrame:
    index = pd.date_range("2026-01-02 09:30", periods=11, freq="15min")
    return pd.DataFrame(
        {
            "open":   [12, 11, 12, 13, 11, 12, 13, 14, 17, 14, 13],
            "high":   [13, 12, 13, 14, 13, 15, 14, 16, 18, 15, 14],
            "low":    [11,  9, 10, 11,  8, 12, 11, 13, 14, 13, 12],
            "close":  [12.5, 10, 12.5, 13.5, 12, 14.5, 13.5, 15.5, 15, 14, 13],
            "volume": [100] * 11,
            "cisd_type": [None, None, None, None, None, "bullish", None, None, "bearish", None, None],
        },
        index=index,
    )


def test_annotate_cisd_research_tags_directional_sweeps_and_swing_positions():
    df = _research_frame_for_sweep_and_swing()

    annotated = cisd_analysis._annotate_cisd_research(df)

    assert annotated.loc[df.index[5], "has_dir_sweep"]
    assert annotated.loc[df.index[5], "prev_bar_is_dir_swing"]
    assert not annotated.loc[df.index[5], "cisd_bar_is_dir_swing"]

    assert annotated.loc[df.index[8], "cisd_bar_is_dir_swing"]
    assert not annotated.loc[df.index[8], "prev_bar_is_dir_swing"]
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `python3 -m pytest tests/test_research_extensions.py::test_annotate_cisd_research_tags_directional_sweeps_and_swing_positions -v`

Expected: FAIL because the annotation helper still leaves `has_dir_sweep`, `prev_bar_is_dir_swing`, and `cisd_bar_is_dir_swing` at their default values.

- [ ] **Step 3: Implement sweep detection and direction-specific swing-position tagging**

Add a sweep helper below `_classify_fvg_hold()` in [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L81):

```python
def _has_directional_sweep(
    df: pd.DataFrame,
    idx: int,
    direction: str,
    swing_low: pd.Series,
    swing_high: pd.Series,
) -> bool:
    start = max(0, idx - (SWEEP_TOLERANCE - 1))
    for sweep_idx in range(start, idx + 1):
        history_start = max(0, sweep_idx - SWEEP_SWING_LOOKBACK)
        if direction == "bullish":
            mask = swing_low.iloc[history_start:sweep_idx]
            prior_lows = df["low"].iloc[history_start:sweep_idx][mask]
            if not prior_lows.empty and df["low"].iloc[sweep_idx] < prior_lows.min():
                return True
        else:
            mask = swing_high.iloc[history_start:sweep_idx]
            prior_highs = df["high"].iloc[history_start:sweep_idx][mask]
            if not prior_highs.empty and df["high"].iloc[sweep_idx] > prior_highs.max():
                return True
    return False
```

Extend `_annotate_cisd_research()` so it fills the direction-specific swing position tags and the sweep tag:

```python
    for ts, row in annotated[annotated["cisd_type"].notna()].iterrows():
        idx = annotated.index.get_loc(ts)
        direction = row["cisd_type"]
        if direction == "bullish":
            annotated.iat[idx, annotated.columns.get_loc("prev_bar_is_dir_swing")] = bool(swing_low.iloc[idx - 1]) if idx > 0 else False
            annotated.iat[idx, annotated.columns.get_loc("cisd_bar_is_dir_swing")] = bool(swing_low.iloc[idx])
        else:
            annotated.iat[idx, annotated.columns.get_loc("prev_bar_is_dir_swing")] = bool(swing_high.iloc[idx - 1]) if idx > 0 else False
            annotated.iat[idx, annotated.columns.get_loc("cisd_bar_is_dir_swing")] = bool(swing_high.iloc[idx])

        annotated.iat[idx, annotated.columns.get_loc("has_dir_sweep")] = _has_directional_sweep(
            annotated,
            idx,
            direction,
            swing_low,
            swing_high,
        )
```

- [ ] **Step 4: Run the sweep and swing-position test again**

Run: `python3 -m pytest tests/test_research_extensions.py::test_annotate_cisd_research_tags_directional_sweeps_and_swing_positions -v`

Expected: PASS

- [ ] **Step 5: Commit the sweep and swing tagging**

```bash
git add tests/test_research_extensions.py cisd_analysis.py
git commit -m "feat: add CISD sweep and swing-position tags"
```

### Task 3: Add the FVG-Based Analysis Compute Functions

**Files:**
- Modify: `tests/test_research_extensions.py`
- Modify: `cisd_analysis.py:292-705`
- Test: `tests/test_research_extensions.py`

- [ ] **Step 1: Write the failing tests for `cisd_fvg`, `fvg_hold`, and `cisd_fvg_interaction`**

Append this fixture and these tests to [tests/test_research_extensions.py](/mnt/e/backup/code/finance/research/cisd markov/tests/test_research_extensions.py):

```python
def _annotated_barrier_df() -> pd.DataFrame:
    index = pd.date_range("2026-01-03 09:30", periods=6, freq="15min")
    return pd.DataFrame(
        {
            "open":    [10, 9, 11, 12, 11, 10],
            "high":    [11, 11, 15, 14, 12, 11],
            "low":     [9,  9, 10, 10, 10,  9],
            "close":   [9.5, 10.5, 12, 11.5, 10.5, 9.5],
            "direction": [None, "bullish", "bullish", "bearish", "bearish", "bearish"],
            "prev_close": [None, 9.5, 10.5, 12, 11.5, 10.5],
            "prev_direction": [None, "bearish", "bearish", "bullish", "bullish", "bullish"],
            "prev_high": [None, 11, 11, 15, 14, 12],
            "prev_low": [None, 9, 9, 10, 10, 10],
            "cisd_type": [None, "bullish", "bullish", "bearish", None, None],
            "has_dir_fvg_mid0": [False, True, False, False, False, False],
            "has_dir_fvg_mid1": [False, False, True, False, False, False],
            "fvg_mid0_hold_close_near": ["none", "held", "none", "none", "none", "none"],
            "fvg_mid0_hold_wick_far": ["none", "held", "none", "none", "none", "none"],
            "fvg_mid1_hold_close_near": ["none", "none", "failed", "none", "none", "none"],
            "fvg_mid1_hold_wick_far": ["none", "none", "failed", "none", "none", "none"],
            "has_dir_sweep": [False, True, False, False, False, False],
            "prev_bar_is_dir_swing": [False, True, False, False, False, False],
            "cisd_bar_is_dir_swing": [False, False, False, True, False, False],
        },
        index=index,
    )


def test_compute_cisd_fvg_splits_mid_buckets_and_baseline():
    stats = cisd_analysis.compute_cisd_fvg(_annotated_barrier_df())

    assert stats["bullish"]["mid0_fvg"]["total"] == 1
    assert stats["bullish"]["mid0_fvg"]["runs"] == 1
    assert stats["bullish"]["mid1_fvg"]["total"] == 1
    assert stats["bullish"]["mid1_fvg"]["runs"] == 0
    assert stats["bearish"]["no_fvg"]["total"] == 1
    assert stats["bearish"]["no_fvg"]["runs"] == 1


def test_compute_fvg_hold_counts_hold_rate_by_bucket_and_failure_mode():
    stats = cisd_analysis.compute_fvg_hold(_annotated_barrier_df())

    assert stats["bullish"]["mid0"]["close_through_near_edge"]["total"] == 1
    assert stats["bullish"]["mid0"]["close_through_near_edge"]["held"] == 1
    assert stats["bullish"]["mid1"]["wick_break_far_extreme"]["total"] == 1
    assert stats["bullish"]["mid1"]["wick_break_far_extreme"]["held"] == 0


def test_compute_cisd_fvg_interaction_splits_parent_cisd_by_linked_outcome():
    stats = cisd_analysis.compute_cisd_fvg_interaction(_annotated_barrier_df())

    assert stats["bullish"]["mid0"]["close_through_near_edge"]["held"]["total"] == 1
    assert stats["bullish"]["mid0"]["close_through_near_edge"]["held"]["runs"] == 1
    assert stats["bullish"]["mid1"]["close_through_near_edge"]["failed"]["total"] == 1
    assert stats["bullish"]["mid1"]["close_through_near_edge"]["failed"]["runs"] == 0
```

- [ ] **Step 2: Run the three tests to verify they fail**

Run: `python3 -m pytest tests/test_research_extensions.py::test_compute_cisd_fvg_splits_mid_buckets_and_baseline tests/test_research_extensions.py::test_compute_fvg_hold_counts_hold_rate_by_bucket_and_failure_mode tests/test_research_extensions.py::test_compute_cisd_fvg_interaction_splits_parent_cisd_by_linked_outcome -v`

Expected: FAIL with `AttributeError` because the three compute functions do not exist yet.

- [ ] **Step 3: Implement the FVG analysis compute functions**

Add these functions in the compute section near [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L292):

```python
def compute_cisd_fvg(df: pd.DataFrame) -> dict:
    stats = {
        "bullish": {"mid0_fvg": {"total": 0, "runs": 0}, "mid1_fvg": {"total": 0, "runs": 0}, "no_fvg": {"total": 0, "runs": 0}},
        "bearish": {"mid0_fvg": {"total": 0, "runs": 0}, "mid1_fvg": {"total": 0, "runs": 0}, "no_fvg": {"total": 0, "runs": 0}},
    }
    idx_index = df.index
    for ts, row in df[df["cisd_type"].notna()].iterrows():
        idx = idx_index.get_loc(ts)
        ct = row["cisd_type"]
        hit = barrier_hit(df, idx, row, ct)
        if row["has_dir_fvg_mid0"]:
            stats[ct]["mid0_fvg"]["total"] += 1
            if hit:
                stats[ct]["mid0_fvg"]["runs"] += 1
        if row["has_dir_fvg_mid1"]:
            stats[ct]["mid1_fvg"]["total"] += 1
            if hit:
                stats[ct]["mid1_fvg"]["runs"] += 1
        if not row["has_dir_fvg_mid0"] and not row["has_dir_fvg_mid1"]:
            stats[ct]["no_fvg"]["total"] += 1
            if hit:
                stats[ct]["no_fvg"]["runs"] += 1
    return stats


def compute_fvg_hold(df: pd.DataFrame) -> dict:
    stats = {
        "bullish": {"mid0": {"close_through_near_edge": {"total": 0, "held": 0}, "wick_break_far_extreme": {"total": 0, "held": 0}},
                    "mid1": {"close_through_near_edge": {"total": 0, "held": 0}, "wick_break_far_extreme": {"total": 0, "held": 0}}},
        "bearish": {"mid0": {"close_through_near_edge": {"total": 0, "held": 0}, "wick_break_far_extreme": {"total": 0, "held": 0}},
                    "mid1": {"close_through_near_edge": {"total": 0, "held": 0}, "wick_break_far_extreme": {"total": 0, "held": 0}}},
    }
    for _, row in df[df["cisd_type"].notna()].iterrows():
        ct = row["cisd_type"]
        for bucket, close_col, wick_col in (
            ("mid0", "fvg_mid0_hold_close_near", "fvg_mid0_hold_wick_far"),
            ("mid1", "fvg_mid1_hold_close_near", "fvg_mid1_hold_wick_far"),
        ):
            close_state = row[close_col]
            if close_state != "none":
                stats[ct][bucket]["close_through_near_edge"]["total"] += 1
                if close_state == "held":
                    stats[ct][bucket]["close_through_near_edge"]["held"] += 1
            wick_state = row[wick_col]
            if wick_state != "none":
                stats[ct][bucket]["wick_break_far_extreme"]["total"] += 1
                if wick_state == "held":
                    stats[ct][bucket]["wick_break_far_extreme"]["held"] += 1
    return stats


def compute_cisd_fvg_interaction(df: pd.DataFrame) -> dict:
    stats = {
        "bullish": {"mid0": {"close_through_near_edge": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}},
                             "wick_break_far_extreme": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}}},
                    "mid1": {"close_through_near_edge": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}},
                             "wick_break_far_extreme": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}}}},
        "bearish": {"mid0": {"close_through_near_edge": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}},
                             "wick_break_far_extreme": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}}},
                    "mid1": {"close_through_near_edge": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}},
                             "wick_break_far_extreme": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}}}},
    }
    idx_index = df.index
    for ts, row in df[df["cisd_type"].notna()].iterrows():
        idx = idx_index.get_loc(ts)
        ct = row["cisd_type"]
        hit = barrier_hit(df, idx, row, ct)
        for bucket, close_col, wick_col in (
            ("mid0", "fvg_mid0_hold_close_near", "fvg_mid0_hold_wick_far"),
            ("mid1", "fvg_mid1_hold_close_near", "fvg_mid1_hold_wick_far"),
        ):
            close_state = row[close_col]
            if close_state in ("held", "failed"):
                stats[ct][bucket]["close_through_near_edge"][close_state]["total"] += 1
                if hit:
                    stats[ct][bucket]["close_through_near_edge"][close_state]["runs"] += 1
            wick_state = row[wick_col]
            if wick_state in ("held", "failed"):
                stats[ct][bucket]["wick_break_far_extreme"][wick_state]["total"] += 1
                if hit:
                    stats[ct][bucket]["wick_break_far_extreme"][wick_state]["runs"] += 1
    return stats
```

- [ ] **Step 4: Run the FVG compute tests again**

Run: `python3 -m pytest tests/test_research_extensions.py::test_compute_cisd_fvg_splits_mid_buckets_and_baseline tests/test_research_extensions.py::test_compute_fvg_hold_counts_hold_rate_by_bucket_and_failure_mode tests/test_research_extensions.py::test_compute_cisd_fvg_interaction_splits_parent_cisd_by_linked_outcome -v`

Expected: PASS

- [ ] **Step 5: Commit the FVG compute layer**

```bash
git add tests/test_research_extensions.py cisd_analysis.py
git commit -m "feat: add CISD FVG analysis computes"
```

### Task 4: Add Sweep and SSSF Analysis Integration

**Files:**
- Modify: `tests/test_research_extensions.py`
- Modify: `cisd_analysis.py:392-929`
- Test: `tests/test_research_extensions.py`

- [ ] **Step 1: Write the failing tests for sweep, SSSF swing, and CSV flattening**

Append these tests to [tests/test_research_extensions.py](/mnt/e/backup/code/finance/research/cisd markov/tests/test_research_extensions.py):

```python
def test_compute_sweep_splits_binary_tag():
    stats = cisd_analysis.compute_sweep(_annotated_barrier_df())

    assert stats["bullish"]["w/ sweep"]["total"] == 1
    assert stats["bullish"]["w/ sweep"]["runs"] == 1
    assert stats["bullish"]["no sweep"]["total"] == 1
    assert stats["bullish"]["no sweep"]["runs"] == 0


def test_compute_sssf_swing_splits_prev_current_and_neither():
    stats = cisd_analysis.compute_sssf_swing(_annotated_barrier_df())

    assert stats["bullish"]["prev_bar_is_swing"]["total"] == 1
    assert stats["bullish"]["prev_bar_is_swing"]["runs"] == 1
    assert stats["bullish"]["neither"]["total"] == 1
    assert stats["bearish"]["cisd_bar_is_swing"]["total"] == 1


def test_build_csv_rows_supports_new_research_keys():
    df = _annotated_barrier_df()

    csv_df = cisd_analysis.build_csv_rows(
        ["cisd_fvg", "fvg_hold", "cisd_fvg_interaction", "sweep", "sssf_swing"],
        df,
        df,
    )

    assert {"CISD FVG Creation", "FVG Hold", "CISD FVG Interaction", "Sweep Confirmation", "SSSF Swing"} <= set(csv_df["Analysis"])
    assert "mid0_fvg" in set(csv_df["Category"])
    assert "mid0_close_through_near_edge_held" in set(csv_df["Category"])
    assert "w/ sweep" in set(csv_df["Category"])
    assert "prev_bar_is_swing" in set(csv_df["Category"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_research_extensions.py::test_compute_sweep_splits_binary_tag tests/test_research_extensions.py::test_compute_sssf_swing_splits_prev_current_and_neither tests/test_research_extensions.py::test_build_csv_rows_supports_new_research_keys -v`

Expected: FAIL with `AttributeError` or missing-key errors because the sweep/SSSF compute functions and new CSV flattening branches are not registered yet.

- [ ] **Step 3: Implement the new compute functions, charts, registry entries, and CSV flattening**

Add the remaining compute functions in [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L292):

```python
def compute_sweep(df: pd.DataFrame) -> dict:
    stats = {
        "bullish": {"w/ sweep": {"total": 0, "runs": 0}, "no sweep": {"total": 0, "runs": 0}},
        "bearish": {"w/ sweep": {"total": 0, "runs": 0}, "no sweep": {"total": 0, "runs": 0}},
    }
    idx_index = df.index
    for ts, row in df[df["cisd_type"].notna()].iterrows():
        idx = idx_index.get_loc(ts)
        ct = row["cisd_type"]
        tag = "w/ sweep" if row["has_dir_sweep"] else "no sweep"
        stats[ct][tag]["total"] += 1
        if barrier_hit(df, idx, row, ct):
            stats[ct][tag]["runs"] += 1
    return stats


def compute_sssf_swing(df: pd.DataFrame) -> dict:
    stats = {
        "bullish": {"prev_bar_is_swing": {"total": 0, "runs": 0}, "cisd_bar_is_swing": {"total": 0, "runs": 0}, "neither": {"total": 0, "runs": 0}},
        "bearish": {"prev_bar_is_swing": {"total": 0, "runs": 0}, "cisd_bar_is_swing": {"total": 0, "runs": 0}, "neither": {"total": 0, "runs": 0}},
    }
    idx_index = df.index
    for ts, row in df[df["cisd_type"].notna()].iterrows():
        idx = idx_index.get_loc(ts)
        ct = row["cisd_type"]
        if row["prev_bar_is_dir_swing"]:
            tag = "prev_bar_is_swing"
        elif row["cisd_bar_is_dir_swing"]:
            tag = "cisd_bar_is_swing"
        else:
            tag = "neither"
        stats[ct][tag]["total"] += 1
        if barrier_hit(df, idx, row, ct):
            stats[ct][tag]["runs"] += 1
    return stats
```

Add chart functions near the existing chart block in [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L392):

```python
def chart_cisd_fvg(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in (("mid0_fvg", 1.0), ("mid1_fvg", 0.75), ("no_fvg", 0.45)):
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})", pv(d["runs"], d["total"]), COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "CISD FVG Creation")


def chart_fvg_hold(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for bucket, alpha in (("mid0", 1.0), ("mid1", 0.7)):
                for mode, label in (("close_through_near_edge", "close near"), ("wick_break_far_extreme", "wick far")):
                    d = data[ct][bucket][mode]
                    rows.append((f"{instr} {ct.capitalize()} {bucket} {label}  (n={d['total']:,})", pv(d["held"], d["total"]), COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "FVG Hold")
    ax.set_xlabel("Hold Rate (%)")


def chart_cisd_fvg_interaction(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for bucket, alpha in (("mid0", 1.0), ("mid1", 0.7)):
                for mode, label in (("close_through_near_edge", "close near"), ("wick_break_far_extreme", "wick far")):
                    for state in ("held", "failed"):
                        d = data[ct][bucket][mode][state]
                        rows.append((f"{instr} {ct.capitalize()} {bucket} {label} {state}  (n={d['total']:,})", pv(d["runs"], d["total"]), COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.5) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "CISD FVG Interaction")


def chart_sweep(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in (("w/ sweep", 1.0), ("no sweep", 0.55)):
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})", pv(d["runs"], d["total"]), COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Sweep Confirmation")


def chart_sssf_swing(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in (("prev_bar_is_swing", 1.0), ("cisd_bar_is_swing", 0.75), ("neither", 0.45)):
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})", pv(d["runs"], d["total"]), COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "SSSF Swing")
```

Register the new keys in `ANALYSES` around [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L691):

```python
ANALYSES = {
    "basic": ("Basic Barrier Run Rate", compute_basic, chart_basic),
    "mc": ("Consecutive Candles (Markov)", compute_mc, chart_mc),
    "significance": ("Significance Test", compute_significance, chart_significance),
    "wick": ("Wick Position", compute_wick, chart_wick),
    "combined": ("Combined: Wick x Consecutive", compute_combined, chart_combined),
    "volume": ("Volume Ratio", compute_volume, chart_volume),
    "candle_size": ("Candle Body vs ATR(14)", compute_candle_size, chart_candle_size),
    "size_cross": ("CISD Body x Prev Body vs ATR", compute_size_cross, chart_size_cross),
    "smt_cisd": ("Swing SMT Confirmation", compute_smt_cisd, chart_smt_cisd),
    "cisd_fvg": ("CISD FVG Creation", compute_cisd_fvg, chart_cisd_fvg),
    "fvg_hold": ("FVG Hold", compute_fvg_hold, chart_fvg_hold),
    "cisd_fvg_interaction": ("CISD FVG Interaction", compute_cisd_fvg_interaction, chart_cisd_fvg_interaction),
    "sweep": ("Sweep Confirmation", compute_sweep, chart_sweep),
    "sssf_swing": ("SSSF Swing", compute_sssf_swing, chart_sssf_swing),
}
```

Extend `build_csv_rows()` around [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L704):

```python
            elif key == "cisd_fvg":
                for ct in ("bullish", "bearish"):
                    for tag, d in data[ct].items():
                        add(label, instr, ct, tag, d["total"], d["runs"])

            elif key == "fvg_hold":
                for ct in ("bullish", "bearish"):
                    for bucket in ("mid0", "mid1"):
                        for mode, d in data[ct][bucket].items():
                            add(label, instr, ct, f"{bucket}_{mode}", d["total"], d["held"])

            elif key == "cisd_fvg_interaction":
                for ct in ("bullish", "bearish"):
                    for bucket in ("mid0", "mid1"):
                        for mode, state_map in data[ct][bucket].items():
                            for state, d in state_map.items():
                                add(label, instr, ct, f"{bucket}_{mode}_{state}", d["total"], d["runs"])

            elif key in ("smt_cisd", "sweep", "sssf_swing"):
                for ct in ("bullish", "bearish"):
                    for tag, d in data[ct].items():
                        add(label, instr, ct, tag, d["total"], d["runs"])
```

Update the sizing and standalone registrations around [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L770) and [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py#L868):

```python
base_h = {
    "basic": 3,
    "significance": 3,
    "mc": 6,
    "wick": 5,
    "combined": 10,
    "volume": 6,
    "candle_size": 6,
    "size_cross": 6,
    "smt_cisd": 4,
    "cisd_fvg": 6,
    "fvg_hold": 8,
    "cisd_fvg_interaction": 10,
    "sweep": 4,
    "sssf_swing": 5,
}
```

```python
STANDALONE_KEYS = {
    "volume",
    "candle_size",
    "size_cross",
    "smt_cisd",
    "cisd_fvg",
    "fvg_hold",
    "cisd_fvg_interaction",
    "sweep",
    "sssf_swing",
}
```

```python
FILENAMES = {
    "volume": "Volume_All_Timeframes.png",
    "candle_size": "CandleSize_All_Timeframes.png",
    "size_cross": "SizeCross_All_Timeframes.png",
    "smt_cisd": "SMT_CISD_All_Timeframes.png",
    "cisd_fvg": "CISD_FVG_All_Timeframes.png",
    "fvg_hold": "FVG_Hold_All_Timeframes.png",
    "cisd_fvg_interaction": "CISD_FVG_Interaction_All_Timeframes.png",
    "sweep": "Sweep_CISD_All_Timeframes.png",
    "sssf_swing": "SSSF_Swing_All_Timeframes.png",
}
```

- [ ] **Step 4: Run the sweep, SSSF, and CSV tests again**

Run: `python3 -m pytest tests/test_research_extensions.py::test_compute_sweep_splits_binary_tag tests/test_research_extensions.py::test_compute_sssf_swing_splits_prev_current_and_neither tests/test_research_extensions.py::test_build_csv_rows_supports_new_research_keys -v`

Expected: PASS

- [ ] **Step 5: Commit the new analysis surface**

```bash
git add tests/test_research_extensions.py cisd_analysis.py
git commit -m "feat: add CISD FVG sweep and swing analyses"
```

### Task 5: Align Docs and Run End-to-End Verification

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `docs/research_backlog.md`
- Test: `tests/test_research_extensions.py`

- [ ] **Step 1: Update the user-facing docs and backlog**

Update the CLI examples and analysis table in [README.md](/mnt/e/backup/code/finance/research/cisd markov/README.md):

````markdown
### Run specific models:
```powershell
python cisd_analysis.py cisd_fvg fvg_hold cisd_fvg_interaction sweep sssf_swing
```

| `cisd_fvg` | **CISD FVG Creation** | Barrier rate split by whether the CISD is the middle candle of a same-direction FVG (`mid0`), the parent of a next-bar same-direction FVG (`mid1`), or neither. |
| `fvg_hold` | **FVG Hold** | Hold rate of CISD-linked same-direction FVGs over 10 bars from the FVG middle candle, reported for both failure modes. |
| `cisd_fvg_interaction` | **CISD FVG Interaction** | Barrier rate of parent CISDs split by whether the linked same-direction FVG held or failed. |
| `sweep` | **Sweep Confirmation** | Barrier rate split by whether a same-direction sweep occurred in `[t-4, t]`. |
| `sssf_swing` | **SSSF Swing** | Barrier rate split by whether `candle[-1]` or `candle[0]` is the relevant direction-specific swing point. |
````

Update the architecture notes in [CLAUDE.md](/mnt/e/backup/code/finance/research/cisd markov/CLAUDE.md):

```markdown
`prepare()` now enriches each resampled frame with the base CISD columns plus the research annotations used by `cisd_fvg`, `fvg_hold`, `cisd_fvg_interaction`, `sweep`, and `sssf_swing`. Those tags include `has_dir_fvg_mid0`, `has_dir_fvg_mid1`, the four `fvg_*` hold-state columns, `has_dir_sweep`, `prev_bar_is_dir_swing`, and `cisd_bar_is_dir_swing`.
```

Mark the backlog items as done in [docs/research_backlog.md](/mnt/e/backup/code/finance/research/cisd markov/docs/research_backlog.md):

```markdown
- `[done]` `cisd_fvg`: measure the hold rate of CISDs that create FVGs.
- `[done]` `fvg_hold`: measure the hold rate of FVGs created by CISDs.
- `[done]` `cisd_fvg_interaction`: test whether an FVG holding increases the hold rate of the parent CISD.
- `[done]` `sssf_swing`: measure the hold rate of CISDs where either `candle[0]` or `candle[-1]` creates a swing, and differentiate which candle created the swing.
- `[done]` `sweep`: measure the hold rate of CISDs with a direction-matched swing sweep in `[t-4, t]`.
```

- [ ] **Step 2: Run the focused regression suite**

Run: `python3 -m pytest tests/test_swing_smt_integration.py tests/test_research_extensions.py -v`

Expected: PASS

- [ ] **Step 3: Run the CLI smoke test for the new analysis keys**

Run: `python3 cisd_analysis.py cisd_fvg fvg_hold cisd_fvg_interaction sweep sssf_swing`

Expected: the command finishes without tracebacks and writes:

- `output/CISD_FVG_All_Timeframes.png`
- `output/FVG_Hold_All_Timeframes.png`
- `output/CISD_FVG_Interaction_All_Timeframes.png`
- `output/Sweep_CISD_All_Timeframes.png`
- `output/SSSF_Swing_All_Timeframes.png`

- [ ] **Step 4: Verify the output files exist**

Run: `ls output/CISD_FVG_All_Timeframes.png output/FVG_Hold_All_Timeframes.png output/CISD_FVG_Interaction_All_Timeframes.png output/Sweep_CISD_All_Timeframes.png output/SSSF_Swing_All_Timeframes.png`

Expected: all five paths print without `No such file or directory`

- [ ] **Step 5: Commit the docs and verified outputs**

```bash
git add README.md CLAUDE.md docs/research_backlog.md tests/test_research_extensions.py cisd_analysis.py
git commit -m "docs: document CISD FVG sweep and swing research"
```
