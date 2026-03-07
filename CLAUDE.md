# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Analysis

```bash
# All analyses — 4 per-TF PNGs + CSVs + standalone PNGs
python3 cisd_analysis.py

# Specific barrier analyses only
python3 cisd_analysis.py basic wick combined

# Fan charts (forward return distributions)
python3 cisd_analysis.py fan

# Fan charts sliced by feature filters (static PNGs)
python3 cisd_analysis.py fan_smt fan_size fan_wick fan_consec

# Interactive HTML report with compound filter UI
python3 cisd_analysis.py export_html

# Mix anything
python3 cisd_analysis.py wick fan export_html
```

All output goes to `output/`. Data must be in `data/nq_1m.parquet` and `data/es_1m.parquet` (1-minute OHLCV, `DateTime_ET` index column).

## Architecture

Everything lives in a single file: `cisd_analysis.py`. The flow is:

**Data pipeline:** `load_1m` → `resample_ohlcv` → `prepare`

`prepare()` enriches a resampled DataFrame with all derived columns needed by every downstream function: `direction`, `prev_*` shifted columns, `cisd_type` (the CISD signal), and three feature-tag columns (`cisd_wick_tag`, `cisd_size_tag`, `cisd_consec`) used by the fan filter analyses.

**Two separate output families:**

1. **Barrier analyses** — measure barrier hit rate (target hit before stop within `LOOKAHEAD=2` bars). Each analysis is a `(label, compute_fn, chart_fn)` triple registered in the `ANALYSES` dict. `compute_fn(df)` returns a nested dict of `{total, runs}` counts; `chart_fn(ax, data_nq, data_es)` renders a horizontal bar chart. Analyses in `STANDALONE_KEYS` get their own all-TF figure (`build_standalone_figure`); others appear per-TF in `build_figure`.

2. **Fan charts** — compute direction-normalised forward returns for every CISD event (`compute_forward_returns`), then show percentile fan bands. The `mask=` parameter filters to a subset of events. `FAN_FILTERS` registry maps filter keys (`smt`, `size`, `wick`, `consec`) to bucket lambdas that produce boolean masks from the prepared DataFrame. Static PNG versions via `fan_smt` / `fan_size` / `fan_wick` / `fan_consec` keys.

3. **Interactive HTML report** (`export_html`) — `compute_all_fan_data` pre-computes all 180 compound filter combinations (3 SMT × 5 size × 3 wick × 4 consec) using `_get_event_data` for a single-pass returns+tags extraction per (TF, instrument, direction). Each combination is stored under key `"{smt}|{size}|{wick}|{consec}"`. `build_html_report` injects the JSON into `_HTML_TEMPLATE`; the browser does a single dict lookup per render — no recomputation. `export_html` always runs SMT annotation automatically.

**Key constants** (top of file):
- `LOOKAHEAD = 2` — bars ahead for barrier logic
- `MAX_CONSEC = 3` — max consecutive opposite candles tracked
- `FORWARD_BARS / BAR_HOURS` — per-TF forward return horizon
- `SMT_LOOKBACK = 20` — swing pivot lookback for SMT detection
- `_SMT_PKG_PATH` — path to local SMT package (required only for `smt_cisd` / `fan_smt` / `export_html`)
- `_SMT_OPTS / _SIZE_OPTS / _WICK_OPTS / _CONSEC_OPTS` — canonical option lists; must match `data-val` attributes in `_HTML_TEMPLATE`

**SMT dependency:** `annotate_swing_smt` imports `smt.check_swing_smt` from `_SMT_PKG_PATH = /mnt/e/backup/code/Finance/Misc/SMT`. Called at every CISD bar with a `[pos-lookback-1 : pos+1]` window; the direction comes from `sig["signal_type"]`. Tolerance and swing pivot logic live inside that external package. "w/ SMT" means the returned signal direction matches `cisd_type`.

## Adding a New Analysis

1. Write `compute_<name>(df) -> dict` returning nested `{total, runs}` counts.
2. Write `chart_<name>(ax, data_nq, data_es)` using `_bar_label` / `_style_ax` helpers.
3. Add to `ANALYSES` dict. If it should be standalone (all-TF figure), add its key to `STANDALONE_KEYS` and `FILENAMES` in `main()`.

## Adding a New Fan Filter (static PNG)

1. Add feature tag column(s) to `prepare()` (vectorized preferred; loop only for row-dependent logic like `cisd_consec`).
2. Add an entry to `FAN_FILTERS` with `label`, `buckets` (list of `(name, lambda df: bool_series)`), and `needs_smt`.
3. Add the CLI key to `FAN_FILTER_KEYS` in `main()`.

## Adding a New Dimension to the HTML Report

1. Add the tag column to `prepare()`.
2. Add a `_NEW_OPTS` list (must start with `"all"`).
3. Extend `_get_event_data` to populate `tags["new_dim"]`.
4. Add `new_dim` to the `iproduct(...)` loop in `compute_all_fan_data` and extend the combo key.
5. Add a `<div class="filter-row">` block to `_HTML_TEMPLATE` and extend `state` / `comboKey()` in the JS.

## Future Testing

- Investigate whether `candle[1]` after a CISD helps predict continuation.
- Test whether continuation is more probable when `candle[1]` closes in the direction of the CISD.
- Test whether closing beyond the wick of `candle[1]` further improves continuation probabilities.
- Consider related `candle[1]` follow-through variants if they can be expressed cleanly as feature tags or fan-filter buckets.
