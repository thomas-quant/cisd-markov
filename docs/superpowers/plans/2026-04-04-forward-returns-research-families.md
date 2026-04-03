# Forward Returns Research Families Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-maintained `output/forward_returns.html` artifact with a generated forward-returns explorer that preserves the old core filters and adds `fvg` and `structure` research families.

**Architecture:** Keep the forward-returns builder separate from the chart-generation path in `cisd_analysis.py`. A dedicated script should import the existing prep pipeline, derive direction-normalized 7-bar forward returns from prepared CISD rows, aggregate percentile fans by family-specific filter combinations, then render a self-contained Plotly HTML artifact.

**Tech Stack:** Python 3, pandas, numpy, json, pathlib, pytest, Plotly-in-HTML

---

## File Map

- `scripts/build_forward_returns.py`
  - Create the real generator for `output/forward_returns.html`.
  - Import `INSTRUMENTS`, `TIMEFRAMES`, `load_1m`, and `prepare_pair()` from [cisd_analysis.py](/mnt/e/backup/code/finance/research/cisd markov/cisd_analysis.py).
  - Own the forward-return horizon constant, family config, combination-key helpers, aggregation helpers, and HTML rendering.

- `cisd_analysis.py`
  - Expose or add small reusable helpers for core CISD segmentation where the builder would otherwise duplicate the size-cross, wick, or consecutive-count logic.
  - Keep CISD, FVG, sweep, and swing semantics sourced from the existing preparation path.

- `tests/test_forward_returns_builder.py`
  - Add focused tests for family key generation, forward-return bucketing, zero-count payloads, and HTML smoke coverage.
  - Use synthetic DataFrames rather than parquet input.

- `output/forward_returns.html`
  - Regenerate from the builder script and stop treating it as hand-authored output.

- `README.md`
  - Add a short note on how to rebuild `output/forward_returns.html` and what the new `core` / `fvg` / `structure` families mean.

### Task 1: Define The Builder Contract With Failing Tests

**Files:**
- Create: `tests/test_forward_returns_builder.py`
- Test: `tests/test_forward_returns_builder.py`

- [ ] **Step 1: Write failing tests for family keys and percentile payloads**

```python
import pandas as pd

from scripts import build_forward_returns as fr


def test_combo_key_builders_use_family_specific_dimensions():
    assert fr.core_combo_key(
        {"smt": "w/ SMT", "size_cross": "Big CISD / Small prev", "wick": "past_wick", "consec": "2"}
    ) == "w/ SMT|Big CISD / Small prev|past_wick|2"
    assert fr.fvg_combo_key(
        {"fvg_bucket": "mid1", "fvg_mode": "close_through_near_edge", "fvg_state": "failed"}
    ) == "mid1|close_through_near_edge|failed"
    assert fr.structure_combo_key(
        {"sweep": "w/ sweep", "prev_swing": "yes", "cisd_swing": "no"}
    ) == "w/ sweep|yes|no"


def test_percentile_payload_returns_none_for_empty_series():
    assert fr.percentile_payload(pd.Series(dtype=float)) is None


def test_percentile_payload_returns_expected_bands():
    series = pd.Series([1.0, 2.0, 3.0, 4.0])

    payload = fr.percentile_payload(series)

    assert payload["50"] == 2.5
    assert payload["5"] == 1.15
    assert payload["95"] == 3.85
```

- [ ] **Step 2: Run the test file to verify it fails**

Run: `python3 -m pytest tests/test_forward_returns_builder.py -v`

Expected: FAIL with `ModuleNotFoundError` or `AttributeError` because `scripts/build_forward_returns.py` and its helper API do not exist yet.

- [ ] **Step 3: Create the minimal builder module and helper API**

Create [scripts/build_forward_returns.py](/mnt/e/backup/code/finance/research/cisd markov/scripts/build_forward_returns.py):

```python
from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd

from cisd_analysis import INSTRUMENTS, TIMEFRAMES, load_1m, prepare_pair

FORWARD_RETURNS_LOOKAHEAD = 7
PERCENTILE_LEVELS = [5, 25, 50, 75, 95]


def core_combo_key(state: dict[str, str]) -> str:
    return "|".join(
        [
            state["smt"],
            state["size_cross"],
            state["wick"],
            state["consec"],
        ]
    )


def fvg_combo_key(state: dict[str, str]) -> str:
    return "|".join(
        [
            state["fvg_bucket"],
            state["fvg_mode"],
            state["fvg_state"],
        ]
    )


def structure_combo_key(state: dict[str, str]) -> str:
    return "|".join(
        [
            state["sweep"],
            state["prev_swing"],
            state["cisd_swing"],
        ]
    )


def percentile_payload(series: pd.Series) -> dict[str, float] | None:
    if series.empty:
        return None
    return {
        str(level): float(np.percentile(series.to_numpy(dtype=float), level))
        for level in PERCENTILE_LEVELS
    }
```

Add `scripts/__init__.py` if needed so the test import works:

```python
# Package marker for builder scripts imported by tests.
```

- [ ] **Step 4: Run the tests again to verify they pass**

Run: `python3 -m pytest tests/test_forward_returns_builder.py -v`

Expected: PASS

- [ ] **Step 5: Commit the builder contract**

```bash
git add scripts/__init__.py scripts/build_forward_returns.py tests/test_forward_returns_builder.py
git commit -m "test: add forward returns builder contract coverage"
```

### Task 2: Add Direction-Normalized Forward-Return Aggregation

**Files:**
- Modify: `scripts/build_forward_returns.py`
- Modify: `cisd_analysis.py`
- Modify: `tests/test_forward_returns_builder.py`
- Test: `tests/test_forward_returns_builder.py`

- [ ] **Step 1: Write failing tests for CISD row enrichment and family filters**

Append these tests to [tests/test_forward_returns_builder.py](/mnt/e/backup/code/finance/research/cisd markov/tests/test_forward_returns_builder.py):

```python
def _prepared_fixture() -> pd.DataFrame:
    index = pd.date_range("2026-02-01 09:30", periods=12, freq="15min")
    return pd.DataFrame(
        {
            "open":  [99, 100, 102, 106, 105, 104, 107, 108, 109, 110, 111, 112],
            "close": [100, 101, 103, 104, 106, 105, 108, 109, 110, 111, 112, 113],
            "high":  [101, 102, 104, 105, 107, 106, 109, 110, 111, 112, 113, 114],
            "low":   [ 99, 100, 102, 103, 104, 104, 107, 108, 109, 110, 111, 112],
            "cisd_type": [None, "bullish", None, "bearish", None, "bullish", None, None, None, None, None, None],
            "swing_smt_tag": ["no SMT", "w/ SMT", "no SMT", "no SMT", "no SMT", "w/ SMT", "no SMT", "no SMT", "no SMT", "no SMT", "no SMT", "no SMT"],
            "direction": [None, "bullish", "bullish", "bearish", "bullish", "bearish", "bullish", "bullish", "bullish", "bullish", "bullish", "bullish"],
            "prev_direction": [None, "bearish", "bullish", "bullish", "bearish", "bullish", "bearish", "bullish", "bullish", "bullish", "bullish", "bullish"],
            "prev_close": [None, 100, 101, 103, 104, 106, 105, 108, 109, 110, 111, 112],
            "prev_high": [None, 101, 102, 104, 105, 107, 106, 109, 110, 111, 112, 113],
            "prev_low": [None, 99, 100, 102, 103, 104, 104, 107, 108, 109, 110, 111],
            "has_dir_fvg_mid0": [False, True, False, False, False, False, False, False, False, False, False, False],
            "has_dir_fvg_mid1": [False, False, False, True, False, False, False, False, False, False, False, False],
            "fvg_mid0_hold_close_near": ["none", "held", "none", "none", "none", "none", "none", "none", "none", "none", "none", "none"],
            "fvg_mid0_hold_wick_far": ["none", "held", "none", "none", "none", "none", "none", "none", "none", "none", "none", "none"],
            "fvg_mid1_hold_close_near": ["none", "none", "none", "failed", "none", "none", "none", "none", "none", "none", "none", "none"],
            "fvg_mid1_hold_wick_far": ["none", "none", "none", "failed", "none", "none", "none", "none", "none", "none", "none", "none"],
            "has_dir_sweep": [False, True, False, False, False, False, False, False, False, False, False, False],
            "prev_bar_is_dir_swing": [False, True, False, False, False, False, False, False, False, False, False, False],
            "cisd_bar_is_dir_swing": [False, False, False, True, False, False, False, False, False, False, False, False],
        },
        index=index,
    )


def test_build_forward_return_rows_adds_normalized_returns_and_core_tags():
    rows = fr.build_forward_return_rows(_prepared_fixture(), "NQ")

    assert set(["instrument", "cisd_type", "forward_return_pct", "smt", "size_cross", "wick", "consec"]) <= set(rows.columns)
    assert rows.loc[rows.index[0], "forward_return_pct"] > 0
    assert rows.loc[rows.index[1], "forward_return_pct"] < 0


def test_apply_fvg_filters_respects_bucket_mode_and_state():
    rows = fr.build_forward_return_rows(_prepared_fixture(), "NQ")

    filtered = fr.apply_family_filters(
        rows,
        "fvg",
        {
            "fvg_bucket": "mid0",
            "fvg_mode": "close_through_near_edge",
            "fvg_state": "held",
        },
    )

    assert filtered["fvg_bucket"].unique().tolist() == ["mid0"]
    assert filtered["fvg_state_close_through_near_edge"].unique().tolist() == ["held"]


def test_apply_structure_filters_respects_sweep_and_swing_flags():
    rows = fr.build_forward_return_rows(_prepared_fixture(), "NQ")

    filtered = fr.apply_family_filters(
        rows,
        "structure",
        {"sweep": "w/ sweep", "prev_swing": "yes", "cisd_swing": "no"},
    )

    assert len(filtered) == 1
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m pytest tests/test_forward_returns_builder.py::test_build_forward_return_rows_adds_normalized_returns_and_core_tags tests/test_forward_returns_builder.py::test_apply_fvg_filters_respects_bucket_mode_and_state tests/test_forward_returns_builder.py::test_apply_structure_filters_respects_sweep_and_swing_flags -v`

Expected: FAIL because `build_forward_return_rows()` and `apply_family_filters()` do not exist yet.

- [ ] **Step 3: Implement the row builder and family filter helpers**

Update the builder import line first:

```python
from cisd_analysis import (
    INSTRUMENTS,
    TIMEFRAMES,
    MAX_CONSEC,
    _count_consecutive,
    load_1m,
    prepare_pair,
)
```

Extend [scripts/build_forward_returns.py](/mnt/e/backup/code/finance/research/cisd markov/scripts/build_forward_returns.py):

```python
def classify_wick(prepared: pd.DataFrame, idx: int, ct: str) -> str:
    row = prepared.iloc[idx]
    if ct == "bullish":
        return "past_wick" if row["close"] > row["prev_high"] else "within_wick"
    return "past_wick" if row["close"] < row["prev_low"] else "within_wick"


def classify_size_cross(prepared: pd.DataFrame, idx: int) -> str:
    atr = (prepared["high"] - prepared["low"]).rolling(14).mean().iloc[idx]
    if pd.isna(atr) or atr <= 0:
        return "all"
    cisd_big = abs(prepared.iloc[idx]["close"] - prepared.iloc[idx]["open"]) >= atr
    prev_big = abs(prepared.iloc[idx - 1]["close"] - prepared.iloc[idx - 1]["open"]) >= atr if idx > 0 else False
    if cisd_big and not prev_big:
        return "Big CISD / Small prev"
    if cisd_big and prev_big:
        return "Big CISD / Big prev"
    if not cisd_big and not prev_big:
        return "Small CISD / Small prev"
    return "Small CISD / Big prev"


def build_forward_return_rows(prepared: pd.DataFrame, instrument: str) -> pd.DataFrame:
    rows = prepared[prepared["cisd_type"].notna()].copy()
    rows["instrument"] = instrument
    rows["smt"] = rows.get("swing_smt_tag", pd.Series("no SMT", index=rows.index))
    rows["size_cross"] = "all"
    rows["wick"] = "all"
    rows["consec"] = "all"
    rows["fvg_bucket"] = np.select(
        [rows["has_dir_fvg_mid0"], rows["has_dir_fvg_mid1"]],
        ["mid0", "mid1"],
        default="no_fvg",
    )
    rows["fvg_state_close_through_near_edge"] = np.select(
        [rows["has_dir_fvg_mid0"], rows["has_dir_fvg_mid1"]],
        [rows["fvg_mid0_hold_close_near"], rows["fvg_mid1_hold_close_near"]],
        default="none",
    )
    rows["fvg_state_wick_break_far_extreme"] = np.select(
        [rows["has_dir_fvg_mid0"], rows["has_dir_fvg_mid1"]],
        [rows["fvg_mid0_hold_wick_far"], rows["fvg_mid1_hold_wick_far"]],
        default="none",
    )
    rows["sweep"] = np.where(rows["has_dir_sweep"], "w/ sweep", "no sweep")
    rows["prev_swing"] = np.where(rows["prev_bar_is_dir_swing"], "yes", "no")
    rows["cisd_swing"] = np.where(rows["cisd_bar_is_dir_swing"], "yes", "no")

    directions = prepared["direction"]
    for ts, row in rows.iterrows():
        idx = prepared.index.get_loc(ts)
        target = "bearish" if row["cisd_type"] == "bullish" else "bullish"
        rows.at[ts, "wick"] = classify_wick(prepared, idx, row["cisd_type"])
        rows.at[ts, "size_cross"] = classify_size_cross(prepared, idx)
        rows.at[ts, "consec"] = str(_count_consecutive(idx, directions, target, MAX_CONSEC))

    future_close = prepared["close"].shift(-FORWARD_RETURNS_LOOKAHEAD).reindex(rows.index)
    raw_return = (future_close / rows["close"] - 1.0) * 100.0
    rows["forward_return_pct"] = np.where(rows["cisd_type"] == "bearish", -raw_return, raw_return)
    return rows[rows["forward_return_pct"].notna()].copy()


def apply_family_filters(rows: pd.DataFrame, family: str, state: dict[str, str]) -> pd.DataFrame:
    filtered = rows
    if family == "core":
        for column, key in [("smt", "smt"), ("size_cross", "size_cross"), ("wick", "wick"), ("consec", "consec")]:
            if state[key] != "all":
                filtered = filtered[filtered[column] == state[key]]
        return filtered
    if family == "fvg":
        if state["fvg_bucket"] != "all":
            filtered = filtered[filtered["fvg_bucket"] == state["fvg_bucket"]]
        if state["fvg_mode"] != "all" and state["fvg_state"] != "all":
            column = f"fvg_state_{state['fvg_mode']}"
            filtered = filtered[filtered[column] == state["fvg_state"]]
        return filtered
    if family == "structure":
        for column, key in [("sweep", "sweep"), ("prev_swing", "prev_swing"), ("cisd_swing", "cisd_swing")]:
            if state[key] != "all":
                filtered = filtered[filtered[column] == state[key]]
        return filtered
    raise ValueError(f"unknown family: {family}")
```

- [ ] **Step 4: Run the tests again to verify they pass**

Run: `python3 -m pytest tests/test_forward_returns_builder.py -v`

Expected: PASS

- [ ] **Step 5: Commit the aggregation helpers**

```bash
git add scripts/build_forward_returns.py tests/test_forward_returns_builder.py
git commit -m "feat: add forward returns family aggregation"
```

### Task 3: Generate Family Payloads And Render The HTML

**Files:**
- Modify: `scripts/build_forward_returns.py`
- Modify: `tests/test_forward_returns_builder.py`
- Test: `tests/test_forward_returns_builder.py`

- [ ] **Step 1: Write failing tests for nested data generation and HTML smoke coverage**

Append these tests to [tests/test_forward_returns_builder.py](/mnt/e/backup/code/finance/research/cisd markov/tests/test_forward_returns_builder.py):

```python
def test_aggregate_family_payload_returns_zero_count_for_empty_combos():
    rows = fr.build_forward_return_rows(_prepared_fixture(), "NQ")

    payload = fr.aggregate_family_payload(
        rows,
        "structure",
        {"sweep": "w/ sweep", "prev_swing": "no", "cisd_swing": "yes"},
    )

    assert payload["n"] == 0
    assert payload["data"] is None


def test_render_html_includes_family_config_and_labels():
    html = fr.render_html(
        data={"Daily": {"family": "placeholder"}},
        config={
            "families": {
                "core": {"label": "Core"},
                "fvg": {"label": "FVG"},
                "structure": {"label": "Structure"},
            }
        },
    )

    assert "data-dim=\"family\"" in html
    assert "fvg_bucket" in html
    assert "structure" in html
    assert "CISD Forward Returns" in html
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m pytest tests/test_forward_returns_builder.py::test_aggregate_family_payload_returns_zero_count_for_empty_combos tests/test_forward_returns_builder.py::test_render_html_includes_family_config_and_labels -v`

Expected: FAIL because `aggregate_family_payload()` and `render_html()` do not exist yet.

- [ ] **Step 3: Implement payload aggregation, config generation, and HTML rendering**

Extend [scripts/build_forward_returns.py](/mnt/e/backup/code/finance/research/cisd markov/scripts/build_forward_returns.py):

```python
DEFAULT_STATE = {
    "core": {"smt": "all", "size_cross": "all", "wick": "all", "consec": "all"},
    "fvg": {"fvg_bucket": "all", "fvg_mode": "all", "fvg_state": "all"},
    "structure": {"sweep": "all", "prev_swing": "all", "cisd_swing": "all"},
}


def aggregate_family_payload(rows: pd.DataFrame, family: str, state: dict[str, str]) -> dict[str, object]:
    filtered = apply_family_filters(rows, family, state)
    return {"n": int(len(filtered)), "data": percentile_payload(filtered["forward_return_pct"])}


def build_config() -> dict[str, object]:
    return {
        "forward_horizon": FORWARD_RETURNS_LOOKAHEAD,
        "families": {
            "core": {
                "label": "Core",
                "dimensions": {
                    "smt": ["all", "w/ SMT", "no SMT"],
                    "size_cross": ["all", "Big CISD / Small prev", "Big CISD / Big prev", "Small CISD / Small prev", "Small CISD / Big prev"],
                    "wick": ["all", "past_wick", "within_wick"],
                    "consec": ["all", "1", "2", "3"],
                },
            },
            "fvg": {
                "label": "FVG",
                "dimensions": {
                    "fvg_bucket": ["all", "mid0", "mid1", "no_fvg"],
                    "fvg_mode": ["all", "close_through_near_edge", "wick_break_far_extreme"],
                    "fvg_state": ["all", "held", "failed", "none"],
                },
            },
            "structure": {
                "label": "Structure",
                "dimensions": {
                    "sweep": ["all", "w/ sweep", "no sweep"],
                    "prev_swing": ["all", "yes", "no"],
                    "cisd_swing": ["all", "yes", "no"],
                },
            },
        },
    }


def render_html(data: dict[str, object], config: dict[str, object]) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CISD Forward Returns</title>
  <script src="https://cdn.jsdelivr.net/npm/plotly.js-dist@2.26.0/plotly.min.js" crossorigin="anonymous"></script>
</head>
<body>
  <header>
    <h1>CISD Forward Returns</h1>
    <span>Positive = CISD was correct | {config['forward_horizon']} bars ahead</span>
  </header>
  <div class="filters">
    <div class="filter-row">
      <button class="btn active" data-dim="family" data-val="core">Core</button>
      <button class="btn" data-dim="family" data-val="fvg">FVG</button>
      <button class="btn" data-dim="family" data-val="structure">Structure</button>
    </div>
  </div>
  <div id="app"></div>
  <script>
  const CONFIG = {json.dumps(config)};
  const DATA = {json.dumps(data)};
  </script>
</body>
</html>"""
```

Add `build_dataset()` and `main()` in the same file to iterate `TIMEFRAMES`, call `prepare_pair(..., with_swing_smt=True)`, build rows for `NQ` and `ES`, aggregate all configured family combinations, then write `output/forward_returns.html`.

- [ ] **Step 4: Run the tests again to verify they pass**

Run: `python3 -m pytest tests/test_forward_returns_builder.py -v`

Expected: PASS

- [ ] **Step 5: Commit the renderer**

```bash
git add scripts/build_forward_returns.py tests/test_forward_returns_builder.py
git commit -m "feat: generate forward returns research families html"
```

### Task 4: Regenerate The Artifact And Document The Builder

**Files:**
- Modify: `README.md`
- Modify: `output/forward_returns.html`
- Test: `tests/test_forward_returns_builder.py`

- [ ] **Step 1: Write the failing documentation smoke assertion**

Append this test to [tests/test_forward_returns_builder.py](/mnt/e/backup/code/finance/research/cisd markov/tests/test_forward_returns_builder.py):

```python
from pathlib import Path


def test_generated_html_mentions_all_research_families(tmp_path: Path):
    out_path = tmp_path / "forward_returns.html"

    fr.write_html(
        out_path,
        data={"Daily": {}},
        config=fr.build_config(),
    )

    html = out_path.read_text()
    assert "Core" in html
    assert "FVG" in html
    assert "Structure" in html
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `python3 -m pytest tests/test_forward_returns_builder.py::test_generated_html_mentions_all_research_families -v`

Expected: FAIL because `write_html()` does not exist yet.

- [ ] **Step 3: Add the file writer, update docs, and regenerate the artifact**

Extend [scripts/build_forward_returns.py](/mnt/e/backup/code/finance/research/cisd markov/scripts/build_forward_returns.py):

```python
def write_html(path: Path, data: dict[str, object], config: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(data, config))
```

Update [README.md](/mnt/e/backup/code/finance/research/cisd markov/README.md) with a short rebuild section:

```md
## Forward Returns Explorer

Rebuild the interactive forward-returns explorer with:
`python3 scripts/build_forward_returns.py`

The page exposes three research families:

- `core`: SMT, size-cross, wick, and consecutive-bar filters
- `fvg`: same-direction CISD-linked FVG creation and hold/fail filters
- `structure`: sweep and direction-specific swing-position filters
```

Run the builder:

```bash
python3 scripts/build_forward_returns.py
```

Expected: [output/forward_returns.html](/mnt/e/backup/code/finance/research/cisd markov/output/forward_returns.html) is rewritten and contains the `family` selector plus `fvg` and `structure` filters.

- [ ] **Step 4: Run the full targeted verification**

Run: `python3 -m pytest tests/test_forward_returns_builder.py -v`

Expected: PASS

Run: `python3 scripts/build_forward_returns.py`

Expected: `output/forward_returns.html` regenerated successfully.

- [ ] **Step 5: Commit the generated artifact and docs**

```bash
git add README.md scripts/build_forward_returns.py tests/test_forward_returns_builder.py output/forward_returns.html
git commit -m "feat: rebuild forward returns explorer by research family"
```

## Self-Review

- Spec coverage:
  - builder script and generated artifact are covered in Tasks 1, 3, and 4
  - family-scoped `core`, `fvg`, and `structure` filters are covered in Tasks 2 and 3
  - forward horizon parity and self-contained HTML are covered in Tasks 3 and 4
  - tests for keys, aggregation, zero-count combos, and HTML smoke are covered in Tasks 1 through 4
- Placeholder scan:
  - no `TODO`, `TBD`, or “implement later” placeholders remain
- Type consistency:
  - helper names are consistent across tasks: `core_combo_key`, `fvg_combo_key`, `structure_combo_key`, `percentile_payload`, `build_forward_return_rows`, `apply_family_filters`, `aggregate_family_payload`, `render_html`, and `write_html`
