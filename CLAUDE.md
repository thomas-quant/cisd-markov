# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Analysis

```bash
# All analyses — 4 per-TF PNGs + CSVs + standalone PNGs
python3 cisd_analysis.py

# Specific barrier analyses only
python3 cisd_analysis.py basic wick combined smt_cisd

# Mix anything
python3 cisd_analysis.py wick smt_cisd
```

All output goes to `output/`. Data must be in `data/nq_1m.parquet` and `data/es_1m.parquet` (1-minute OHLCV, `DateTime_ET` index column).

## Architecture

Everything lives in a single file: `cisd_analysis.py`. The flow is:

**Data pipeline:** `load_1m` → `resample_ohlcv` → `prepare` / `prepare_pair`

`prepare()` enriches a resampled DataFrame with the CISD-derived columns used by the barrier analyses: `direction`, `prev_*` shifted columns, and `cisd_type`.

`prepare_pair()` resamples both instruments together, intersects the shared index before downstream processing, optionally runs the external SMT historical scanner, and annotates each frame with `has_swing_smt`, `swing_smt_tag`, `swing_smt_match_ts`, and `swing_smt_role`.

**Output family:**

1. **Barrier analyses** — measure barrier hit rate (target hit before stop within `LOOKAHEAD=2` bars). Each analysis is a `(label, compute_fn, chart_fn)` triple registered in the `ANALYSES` dict. `compute_fn(df)` returns a nested dict of `{total, runs}` counts; `chart_fn(ax, data_nq, data_es)` renders a horizontal bar chart. Analyses in `STANDALONE_KEYS` get their own all-TF figure (`build_standalone_figure`); others appear per-TF in `build_figure`.

**Key constants** (top of file):
- `LOOKAHEAD = 2` — bars ahead for barrier logic
- `MAX_CONSEC = 3` — max consecutive opposite candles tracked
- `SMT_LOOKBACK = 20` — swing pivot lookback for SMT detection
- `_SMT_PKG_PATH` — path to local SMT package (required only for `smt_cisd`)

**SMT dependency:** `prepare_pair()` imports `smt.scan_smts_historical` from `_SMT_PKG_PATH = /mnt/e/backup/code/Finance/Misc/SMT`. Swing SMT tagging is left-only: a CISD at bar `t` matches a same-direction Swing SMT created on `t`, `t-1`, or `t-2`. "w/ SMT" means the returned signal direction matches `cisd_type`; the helper also records whether the instrument was the `sweeping_asset` or `failing_asset`.

## Adding a New Analysis

1. Write `compute_<name>(df) -> dict` returning nested `{total, runs}` counts.
2. Write `chart_<name>(ax, data_nq, data_es)` using `_bar_label` / `_style_ax` helpers.
3. Add to `ANALYSES` dict. If it should be standalone (all-TF figure), add its key to `STANDALONE_KEYS` and `FILENAMES` in `main()`.

## Research Backlog

Planned research ideas live in `docs/research_backlog.md`. Keep `README.md` focused on current behavior and findings, and use the backlog for future studies and rough ideas copied in from Discord.
