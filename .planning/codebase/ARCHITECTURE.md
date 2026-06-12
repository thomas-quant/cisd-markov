<!-- refreshed: 2026-06-12 -->
# Architecture

**Analysis Date:** 2026-06-12

## System Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                     CLI / Entry Point                           │
│  `cisd_analysis.py` main()   |   `scripts/build_*.py`          │
└───────────────────┬─────────────────────────┬───────────────────┘
                    │                         │
                    ▼                         ▼
┌───────────────────────────────┐  ┌──────────────────────────────┐
│       Data Pipeline           │  │      Script Consumers        │
│  load_1m → resample_ohlcv     │  │  build_forward_returns.py    │
│  → prepare / prepare_pair     │  │  build_expectancy.py         │
│  `cisd_analysis.py` L69–381   │  │  `scripts/`                  │
└───────────────┬───────────────┘  └──────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────────┐
│                 Enriched DataFrame (per instrument/TF)            │
│  OHLCV + direction, prev_*, cisd_type,                           │
│  has_dir_fvg_mid0/mid1, fvg_*_hold_*, has_dir_sweep,            │
│  prev_bar_is_dir_swing, cisd_bar_is_dir_swing,                   │
│  has_swing_smt, swing_smt_tag, swing_smt_role                    │
└───────────┬───────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────┐
│               Compute Functions  (per analysis key)               │
│  compute_basic / compute_mc / compute_wick / compute_combined /  │
│  compute_volume / compute_candle_size / compute_size_cross /     │
│  compute_smt_cisd / compute_cisd_fvg / compute_fvg_hold /       │
│  compute_cisd_fvg_interaction / compute_sweep / compute_sssf_swing│
│  `cisd_analysis.py` L449–993                                     │
└───────────┬───────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│          Chart Functions + Figure Builders                      │
│  chart_*(ax, data_nq, data_es)                                  │
│  build_figure / build_standalone_figure / build_csv_rows        │
│  `cisd_analysis.py` L550–1248                                   │
└─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        output/                                  │
│  {TF}.png, {TF}.csv  (per-timeframe barrier charts)            │
│  {Key}_All_Timeframes.png  (standalone charts)                  │
│  forward_returns.html  (interactive Plotly report)              │
│  cisd_expectancy.csv / cisd_expectancy.md                       │
└─────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `load_1m` | Read parquet, set DatetimeIndex, lowercase columns | `cisd_analysis.py:71` |
| `resample_ohlcv` | OHLCV aggregation from 1-min to target timeframe | `cisd_analysis.py:85` |
| `prepare` | Enrich resampled df with all CISD-derived columns | `cisd_analysis.py:90` |
| `_annotate_cisd_research` | Row-by-row annotation: FVG, sweep, swing labels | `cisd_analysis.py:191` |
| `prepare_pair` | Dual-instrument pipeline; optional SMT scan | `cisd_analysis.py:359` |
| `barrier_hit` | Core barrier logic: target before stop in LOOKAHEAD bars | `cisd_analysis.py:386` |
| `compute_*` | Per-analysis aggregation of barrier counts into nested dicts | `cisd_analysis.py:449–993` |
| `chart_*` | Matplotlib horizontal bar charts from nested dicts | `cisd_analysis.py:550–1088` |
| `ANALYSES` dict | Registry mapping key → (label, compute_fn, chart_fn) | `cisd_analysis.py:1091` |
| `build_figure` | Per-timeframe multi-analysis figure | `cisd_analysis.py:1192` |
| `build_standalone_figure` | All-TF 2×2 grid for a single analysis key | `cisd_analysis.py:1251` |
| `build_csv_rows` | Flatten all analysis results to tidy long CSV | `cisd_analysis.py:1109` |
| `main` | CLI entry: arg parsing, data load, per-TF + standalone dispatch | `cisd_analysis.py:1298` |
| `build_forward_returns.py` | Interactive Plotly HTML of forward return fans | `scripts/build_forward_returns.py` |
| `build_expectancy.py` | Stop-censored R-multiple expectancy study | `scripts/build_expectancy.py` |

## Pattern Overview

**Overall:** Single-file research engine using a registry pattern.

**Key Characteristics:**
- All analysis is driven by a central `ANALYSES` dict of `(label, compute_fn, chart_fn)` triples.
- The data pipeline is strictly one-directional: raw parquet → resampled OHLCV → enriched DataFrame → compute outputs → chart/CSV/HTML.
- All column annotations are precomputed in `prepare()` / `_annotate_cisd_research()`. Downstream `compute_*` functions read precomputed columns only — they do not rediscover events.
- Script consumers (`scripts/`) import from `cisd_analysis` as a library and extend output formats without touching the core pipeline.

## Layers

**Data Loading Layer:**
- Purpose: Load and normalize raw 1-minute parquet data
- Location: `cisd_analysis.py:69–87`
- Contains: `load_1m`, `resample_ohlcv`, `_normalize_resample_rule`
- Depends on: `pandas`, `pyarrow` (parquet), `data/` directory
- Used by: `prepare_pair`, `main`, script consumers

**Enrichment Layer:**
- Purpose: Compute all CISD-derived columns once; results are stable for reuse across all analyses
- Location: `cisd_analysis.py:90–381`
- Contains: `prepare`, `_annotate_cisd_research`, `_compute_three_bar_swings`, `_has_directional_fvg`, `_classify_fvg_hold`, `_has_directional_sweep`, `prepare_pair`, SMT helpers
- Depends on: Data Loading Layer, optional external SMT package
- Used by: Compute Layer, script consumers

**Compute Layer:**
- Purpose: Aggregate barrier hit counts into nested dicts by bucket/direction
- Location: `cisd_analysis.py:449–993`
- Contains: `compute_basic`, `compute_mc`, `compute_wick`, `compute_combined`, `compute_volume`, `compute_candle_size`, `compute_size_cross`, `compute_smt_cisd`, `compute_cisd_fvg`, `compute_fvg_hold`, `compute_cisd_fvg_interaction`, `compute_sweep`, `compute_sssf_swing`
- Depends on: Enrichment Layer output (enriched DataFrame columns), `barrier_hit`
- Used by: Rendering Layer, `build_csv_rows`

**Rendering Layer:**
- Purpose: Transform compute outputs into visual or tabular form
- Location: `cisd_analysis.py:550–1381`; `scripts/build_forward_returns.py`; `scripts/build_expectancy.py`
- Contains: `chart_*` functions, `build_figure`, `build_standalone_figure`, `build_csv_rows`, `main`, and the two script entrypoints
- Depends on: Compute Layer, `matplotlib`
- Used by: CLI invocation only

## Data Flow

### Primary Barrier Analysis Path

1. CLI args parsed in `main()` — analysis keys split into `per_tf_keys` and `standalone` (`cisd_analysis.py:1312`)
2. `load_1m` reads `data/nq_1m.parquet` + `data/es_1m.parquet` (`cisd_analysis.py:1330`)
3. For each timeframe: `prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], tf_rule, with_swing_smt=...)` (`cisd_analysis.py:1339`)
   - Calls `resample_ohlcv` then `prepare` for each instrument
   - If SMT needed: intersects shared index, runs `_scan_swing_smt_events`, calls `_annotate_swing_smt_from_events`
4. Per-TF keys: `build_figure` → for each key calls `compute_fn(df)` then `chart_fn(ax, d_nq, d_es)` → saves `output/{TF}.png` + `output/{TF}.csv`
5. Standalone keys: `build_standalone_figure(key, prepared)` iterates all TFs in a 2×2 grid → saves `output/{Key}_All_Timeframes.png`

### Forward Returns Path

1. `scripts/build_forward_returns.py main()` calls `build_dataset()`
2. `build_dataset` loads 1-min data, calls `prepare_pair(..., with_swing_smt=True)` for each TF
3. `build_forward_return_rows(df, instrument)` computes filter columns and 7-bar forward return percentiles per CISD event
4. `aggregate_family_payload` applies `apply_family_filters` for all combo-key states across three families (`core`, `fvg`, `structure`)
5. Pre-computed JSON payload embedded in `render_html` → written to `output/forward_returns.html`

### Expectancy Path

1. `scripts/build_expectancy.py build()` loads data, calls `prepare_pair` with optional SMT
2. `build_event_r_multiples(prepared, instrument)` computes stop-censored R-multiples for each CISD event
3. `build_long_table` applies `case_masks` and `summarize_horizon` across all cases
4. Outputs: `output/cisd_expectancy.csv` + `output/cisd_expectancy.md`

**State Management:**
- No shared mutable state. All DataFrame mutations use `.copy()` before modification. The `prepared` dict in `main()` is an in-process cache of enriched DataFrames for reuse by standalone figures.

## Key Abstractions

**ANALYSES Registry:**
- Purpose: Declarative mapping of analysis key → (human label, compute function, chart function)
- Location: `cisd_analysis.py:1091`
- Pattern: `dict[str, tuple[str, Callable, Callable]]`; all three elements consumed by `build_figure` and `build_standalone_figure`

**Enriched DataFrame:**
- Purpose: Single annotated DataFrame that all compute functions consume without rediscovery
- Key columns: `cisd_type`, `direction`, `prev_*`, `has_dir_fvg_mid0`, `has_dir_fvg_mid1`, `fvg_*_hold_*`, `has_dir_sweep`, `prev_bar_is_dir_swing`, `cisd_bar_is_dir_swing`, `has_swing_smt`, `swing_smt_tag`, `swing_smt_role`
- Pattern: All annotations are boolean flags or categorical strings; no nested structures in the DataFrame

**Barrier Hit Logic:**
- Purpose: Strict first-touch evaluation — target reached before stop within `LOOKAHEAD` bars
- Location: `cisd_analysis.py:386`
- Used by: every `compute_*` function; also reimplemented inline in `build_expectancy.py` as stop-censored R-multiple logic

**Research Families (forward returns):**
- Purpose: Group filter dimensions for the interactive HTML report
- Location: `scripts/build_forward_returns.py:26–50`
- Three families: `core` (SMT, size cross, wick, consec), `fvg` (bucket, mode, state), `structure` (sweep, prev swing, CISD swing)

## Entry Points

**`cisd_analysis.py` main():**
- Location: `cisd_analysis.py:1298`
- Triggers: `python3 cisd_analysis.py [key1 key2 ...]`
- Responsibilities: CLI parsing, data load, per-TF figure + CSV + standalone figure dispatch

**`scripts/build_forward_returns.py` main():**
- Location: `scripts/build_forward_returns.py:687`
- Triggers: `python3 scripts/build_forward_returns.py`
- Responsibilities: Build forward return dataset and render interactive HTML to `output/forward_returns.html`

**`scripts/build_expectancy.py` build():**
- Location: `scripts/build_expectancy.py:295`
- Triggers: `python3 scripts/build_expectancy.py`
- Responsibilities: Build R-multiple expectancy study, write CSV + Markdown to `output/`

## Architectural Constraints

- **Threading:** Single-threaded. All loops over CISD events are sequential Python `for` loops over DataFrame rows. No multiprocessing.
- **Global state:** Module-level constants (`LOOKAHEAD`, `MAX_CONSEC`, `TIMEFRAMES`, etc.) at the top of `cisd_analysis.py:60–66` are shared across all functions. `matplotlib.rcParams` mutated once at import time.
- **Circular imports:** None. Script consumers import from `cisd_analysis` unidirectionally.
- **External dependency:** SMT package at `_SMT_PKG_PATH = /mnt/e/backup/code/Finance/Misc/SMT` is dynamically injected into `sys.path` at call time (`cisd_analysis.py:330`). Only required for `smt_cisd` analysis and `prepare_pair(..., with_swing_smt=True)`. Both `build_expectancy.py` and `build_forward_returns.py` degrade gracefully when the SMT package is unavailable.
- **Data locality:** Parquet files must reside in `data/` adjacent to `cisd_analysis.py`. `scripts/` consumers resolve the data root relative to the repo root and support git worktree layouts (`scripts/build_forward_returns.py:339`).

## Anti-Patterns

### `build_csv_rows` key-dispatch block

**What happens:** `build_csv_rows` (`cisd_analysis.py:1109`) switches on each analysis key with `if key in (...)` to unpack the specific nested dict structure returned by each `compute_*` function.
**Why it's wrong:** Adding a new analysis requires edits in three places: `ANALYSES`, the dispatch block in `build_csv_rows`, and `build_figure`/`STANDALONE_KEYS`. The dispatch block is not driven by the `ANALYSES` registry.
**Do this instead:** Each `compute_*` function should return a normalized tidy format or a separate `flatten_*` function should be registered alongside `compute_fn` and `chart_fn` in `ANALYSES`.

### Row-by-row Python loops in annotation

**What happens:** `_annotate_cisd_research` (`cisd_analysis.py:208`) and all `compute_*` functions iterate over DataFrame rows with `for ts, row in df.iterrows()`.
**Why it's wrong:** `iterrows` is O(n) Python-level iteration over large DataFrames; at 1-min granularity this is slow. The annotation pass in particular is performed once per instrument per timeframe.
**Do this instead:** Vectorize using `np.where`/`pd.Series.apply` for simple conditions; use positional index arrays (`np.flatnonzero`) for event-driven scans (as `build_expectancy.py` already does at `scripts/build_expectancy.py:108`).

## Error Handling

**Strategy:** Fail-fast with `ValueError` for programmer errors (missing required columns); graceful degradation for optional external dependency (SMT package).

**Patterns:**
- Missing required columns raise `ValueError` immediately: `_annotate_swing_smt_from_events` (`cisd_analysis.py:254`), `_to_smt_ohlc` (`cisd_analysis.py:322`), `compute_smt_cisd` (`cisd_analysis.py:808`)
- SMT scan failure is caught with bare `except Exception` in `build_expectancy.py:304` and `build_forward_returns.py` (implicitly via `with_swing_smt` flag)
- Invalid CLI keys cause `sys.exit(1)` with informative message (`cisd_analysis.py:1314`)

## Cross-Cutting Concerns

**Logging:** `print()` statements only — no structured logging. Progress lines use `end=" ", flush=True` pattern.
**Validation:** Column existence checked at annotation/compute boundaries. No schema enforcement on parquet input beyond expected column names.
**Authentication:** Not applicable (local file system only).

---

*Architecture analysis: 2026-06-12*
