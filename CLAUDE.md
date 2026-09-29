# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Analysis

```bash
# All analyses — 4 per-TF PNGs + CSVs + 9 standalone PNGs
python3 cisd_analysis.py

# Specific barrier analyses only
python3 cisd_analysis.py basic wick combined smt_cisd

# Mix anything
python3 cisd_analysis.py cisd_fvg fvg_hold cisd_fvg_interaction sweep sssf_swing
```

All output goes to `output/`. Data must be in `data/nq_1m.parquet` and `data/es_1m.parquet` (1-minute OHLCV with a `DateTime_ET` or UTC `datetime_utc` column; `load_1m` converts to ET and pins `DATA_START..DATA_END` = 2020-08-31..2025-11-21).

## Architecture

Everything lives in a single file: `cisd_analysis.py`. The flow is:

**Data pipeline:** `load_1m` → `resample_ohlcv` → `prepare` / `prepare_pair`

`prepare()` enriches a resampled DataFrame with the CISD-derived columns used by the barrier analyses:
- `direction`, `prev_*` shifted columns, and `cisd_type`
- FVG annotations: `has_dir_fvg_mid0`, `has_dir_fvg_mid1`, `fvg_mid0_hold_close_near`, `fvg_mid0_hold_wick_far`, `fvg_mid1_hold_close_near`, `fvg_mid1_hold_wick_far`
- sweep/swing annotations: `has_dir_sweep`, `prev_bar_is_dir_swing`, `cisd_bar_is_dir_swing`

The research annotations are all single-instrument and are computed inside `prepare()`. The intent is that later `compute_*` functions consume only these precomputed columns instead of rediscovering events.

`prepare_pair()` resamples both instruments together, intersects the shared index before downstream processing, optionally runs the external SMT historical scanner, and annotates each frame with `has_swing_smt`, `swing_smt_tag`, `swing_smt_match_ts`, and `swing_smt_role`.

**Output family:**

1. **Barrier analyses** — measure barrier hit rate (target hit before stop within `LOOKAHEAD=2` bars). Each analysis is a `(label, compute_fn, chart_fn)` triple registered in the `ANALYSES` dict. `compute_fn(df)` returns a nested dict of counts, while `chart_fn(ax, data_nq, data_es)` renders a horizontal bar chart. Analyses in `STANDALONE_KEYS` get their own all-TF figure (`build_standalone_figure`); others appear per-TF in `build_figure`.

Current standalone research keys are:
- `volume`
- `candle_size`
- `size_cross`
- `smt_cisd`
- `cisd_fvg`
- `fvg_hold`
- `cisd_fvg_interaction`
- `sweep`
- `sssf_swing`

**Key constants** (top of file):
- `LOOKAHEAD = 2` — bars ahead for barrier logic
- `MAX_CONSEC = 3` — max consecutive opposite candles tracked
- `SMT_LOOKBACK = 20` — swing pivot lookback for SMT detection
- `FVG_HOLD_LOOKAHEAD = 10` — bars after the FVG middle candle used to classify hold/fail
- `SWEEP_TOLERANCE = 5` — bars in the CISD-relative sweep window `[t-4, t]`
- `SWEEP_SWING_LOOKBACK = 20` — historical swing search depth for sweep detection
- `_SMT_PKG_PATH` — path to local SMT package (required only for `smt_cisd`)

**SMT dependency:** `prepare_pair()` imports `smt.scan_smts_historical` from `_SMT_PKG_PATH = /mnt/e/backup/code/Finance/Misc/SMT`. Swing SMT tagging is left-only: a CISD at bar `t` matches a same-direction Swing SMT created on `t`, `t-1`, or `t-2`. "w/ SMT" means the returned signal direction matches `cisd_type`; the helper also records whether the instrument was the `sweeping_asset` or `failing_asset`.

## Adding a New Analysis

1. Write `compute_<name>(df) -> dict` returning nested `{total, runs}` counts.
2. Write `chart_<name>(ax, data_nq, data_es)` using `_bar_label` / `_style_ax` helpers.
3. Add to `ANALYSES` dict. If it should be standalone (all-TF figure), add its key to `STANDALONE_KEYS` and `FILENAMES` in `main()`.

## Research Backlog

Planned research ideas live in `docs/research_backlog.md`. Keep `README.md` focused on current behavior and findings, and use the backlog for future studies and rough ideas copied in from Discord.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**CISD-Markov Research Engine**

A quantitative research engine that tests **CISD** (Change in State of Delivery) barrier-hit patterns across NQ and ES futures, on multiple timeframes, using a strict first-touch barrier model (target before stop within a lookahead window). It already produces per-timeframe charts, CSVs, an interactive forward-returns report, and a stop-censored expectancy study. This milestone upgrades it from a single-pass, in-sample filter-mining script into a **reproducible, test-gated research engine whose findings carry honest statistics** (in-sample/out-of-sample validation, confidence intervals, sample-size gating).

**Core Value:** A reported edge can be trusted: every published rate is gated by sample size, carries a confidence interval, and is confirmed on out-of-sample data — not discovered and reported in-sample on a lucky bucket.

### Constraints

- **Tech stack**: Python 3.10+, pandas / numpy / matplotlib / pyarrow (plotly via CDN for the HTML report). Keep dependencies minimal — research must run offline and deterministically.
- **Data**: 1-minute OHLCV parquet for NQ + ES in `data/` (`DateTime_ET` or UTC `datetime_utc`). The window is pinned by `DATA_START`/`DATA_END` in `cisd_data.py` so the OOS boundary and walk-forward folds stay stable; bars after `DATA_END` are an untouched holdout.
- **External dependency**: SMT package (currently a hardcoded WSL path) is optional — every entry point must degrade gracefully when it is absent.
- **Determinism**: results must be reproducible — pinned dependencies, no wall-clock or RNG dependence in computed numbers.
- **Behavior-preserving**: the refactor and the validation harness must not silently alter existing computed numbers. Characterization tests lock current behavior *before* those changes land.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12.3 — all analysis, scripting, and test code
- JavaScript (embedded in generated HTML) — interactive chart rendering inside `output/forward_returns.html`, produced by `scripts/build_forward_returns.py`
## Runtime
- CPython 3.12.3 (system Python, also used by the project's `.venv`)
- pip 26.0.1 (inside `.venv`)
- Lockfile: not present (no `requirements.txt`, no `pyproject.toml` at repo root; package list is inferred from `.venv/lib/python3.12/site-packages/`)
- `.venv/` at repo root (excluded from version control via `.gitignore`)
## Frameworks
- pytest 9.0.2 — test runner for all files under `tests/`
- pluggy 1.6.0 — pytest plugin system (transitive dependency)
- No build framework; the project is run directly as scripts (`python3 cisd_analysis.py`, `python3 scripts/build_expectancy.py`, `python3 scripts/build_forward_returns.py`)
## Key Dependencies
- pandas 3.0.2 — all OHLCV DataFrames, resampling, index alignment, and event tagging throughout `cisd_analysis.py` and both `scripts/` files
- numpy 2.4.4 — vectorised condition logic (`np.where`, `np.select`, `np.percentile`) across all analysis functions
- pyarrow 23.0.1 — Parquet file I/O; `pd.read_parquet` requires this backend; input files are `data/nq_1m.parquet` and `data/es_1m.parquet`
- matplotlib 3.10.8 — all PNG chart rendering; configured globally in `cisd_analysis.py` lines 24-40 with a dark-theme `rcParams` block
- Pillow 12.2.0 — image support (matplotlib transitive dependency)
- contourpy 1.3.3, cycler 0.12.1, kiwisolver 1.5.0, pyparsing 3.3.2 — matplotlib transitive dependencies
- fontTools 4.62.1 — font handling for matplotlib
- python-dateutil 2.9.0 — pandas datetime parsing (transitive)
- six 1.17.0 — python-dateutil transitive dependency
- packaging 26.0 — build/dependency resolution utility
- pygments 2.20.0 — pytest output colouring (transitive)
- iniconfig 2.3.0 — pytest config file parsing (transitive)
- `smt` — local proprietary package located at `/mnt/e/backup/code/Finance/Misc/SMT`; provides `scan_smts_historical()`; requires numpy >= 1.23 and pandas >= 1.5; only imported at runtime via `_load_scan_smts_historical()` in `cisd_analysis.py` line 330; if the path does not exist, the `smt_cisd` analysis raises `FileNotFoundError`
- Plotly.js 2.26.0 — loaded from `cdn.jsdelivr.net` inside the self-contained `forward_returns.html` output file; used for interactive percentile fan charts
## Configuration
- No environment variables used anywhere in the codebase
- No `.env` file; all configuration is hardcoded constants at the top of `cisd_analysis.py`
- `DATA_DIR` — `Path(__file__).parent / "data"` (resolved at import time)
- `INSTRUMENTS` — maps `"NQ"` and `"ES"` to their Parquet paths
- `TIMEFRAMES` — `{"Daily": "1D", "4H": "4h", "1H": "1h", "15min": "15min"}`
- `LOOKAHEAD = 2` — barrier look-ahead bars
- `MAX_CONSEC = 3` — max consecutive opposite candles
- `SMT_LOOKBACK = 20` — swing pivot lookback
- `FVG_HOLD_LOOKAHEAD = 10` — FVG hold/fail classification window
- `SWEEP_TOLERANCE = 5` — bars in CISD-relative sweep window
- `SWEEP_SWING_LOOKBACK = 20` — historical swing search depth
- `_SMT_PKG_PATH = Path("/mnt/e/backup/code/Finance/Misc/SMT")` — absolute path to local SMT package
- No build step; scripts are run directly
- `scripts/__init__.py` exists so `tests/` can import `scripts.build_expectancy` and `scripts.build_forward_returns` as modules
## Output Artifacts
- Per-timeframe PNG bar charts: `{tf_label}.png`
- Per-timeframe CSV summaries: `{tf_label}.csv`
- Standalone all-TF PNG charts (9 files, e.g. `SMT_CISD_All_Timeframes.png`)
- `cisd_expectancy.csv` — tidy long table of R-multiple distributions
- `cisd_expectancy.md` — methodology and headline expectancy tables
- `forward_returns.html` — self-contained interactive Plotly dashboard
## Platform Requirements
- Python 3.12+ (3.12.3 confirmed)
- Local SMT package at `/mnt/e/backup/code/Finance/Misc/SMT` (required only for `smt_cisd` analysis)
- Data files at `data/nq_1m.parquet` and `data/es_1m.parquet` (1-minute OHLCV with `DateTime_ET` or `datetime_utc` column; excluded from git)
- No deployment target; pure local research tool run as CLI scripts
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- `snake_case.py` for all source and script files: `cisd_analysis.py`, `build_forward_returns.py`, `build_expectancy.py`
- Test files: `test_<module_or_feature>.py` in `tests/` directory
- Public functions: `snake_case` — e.g., `prepare`, `resample_ohlcv`, `barrier_hit`, `compute_basic`, `chart_basic`
- Private helpers: `_snake_case` with leading underscore — e.g., `_compute_three_bar_swings`, `_has_directional_fvg`, `_classify_fvg_hold`, `_annotate_cisd_research`
- Compute functions: `compute_<analysis_name>(df) -> dict` pattern — e.g., `compute_wick`, `compute_sweep`, `compute_smt_cisd`
- Chart functions: `chart_<analysis_name>(ax, data_nq, data_es)` pattern — e.g., `chart_wick`, `chart_sweep`
- Builder functions: `build_<output>(...)` — e.g., `build_forward_return_rows`, `build_csv_rows`, `build_figure`, `build_dataset`
- Local variables: `snake_case`
- Short loop variables acceptable for tight iteration: `ct` (cisd_type), `ts` (timestamp), `idx`, `i`, `j`, `k`
- Column alignment for parallel short assignments:
- Module-level: `UPPER_SNAKE_CASE` — e.g., `LOOKAHEAD`, `MAX_CONSEC`, `SMT_LOOKBACK`, `TIMEFRAMES`, `COLORS`, `ANALYSES`
- Private module-level: `_UPPER_SNAKE_CASE` — e.g., `_SMT_PKG_PATH`
- Inline bin/bucket definitions: `UPPER_CASE` locals — e.g., `BINS`, `BUCKETS` inside compute functions
- All lowercase with underscores: `cisd_type`, `has_dir_fvg_mid0`, `fvg_mid0_hold_close_near`, `swing_smt_tag`, `prev_bar_is_dir_swing`
- OHLCV columns lowercase: `open`, `high`, `low`, `close`, `volume`
- Direction strings are lowercase literals: `"bullish"`, `"bearish"`, `"neutral"`
## Code Style
- 4-space indentation throughout
- No formatter config file detected (no pyproject.toml, .flake8, setup.cfg)
- Column alignment used for parallel dict/variable assignments to improve readability
- No trailing whitespace convention enforced by tooling
- No linting configuration detected
- Code passes clean without any noqa suppressions
- Use `# ── Section Name ─────────────────────────────────────────────────────────────` to delineate logical sections within a module:
## Import Organization
- None. Imports use direct module names or sys.path manipulation.
## Type Annotations
- `cisd_analysis.py`: Most public and private functions fully annotated. `main()` has `-> None`. `chart_*` functions annotate `title: str` but omit `ax` and `data_*` types (matplotlib Axes not imported at module level for type purposes).
- `scripts/build_forward_returns.py`, `scripts/build_expectancy.py`: Full annotations with `from __future__ import annotations`; use `dict[str, str]`, `dict[str, object]`, `list[dict[str, str]]`, `dict[str, float] | None`
- Compute functions: `-> dict` (bare dict, not fully parameterized)
- Pipeline functions: `-> pd.DataFrame` or `-> tuple[pd.DataFrame, pd.DataFrame]`
- Boolean predicates: `-> bool`
- Classification functions: `-> str`
- Builder config functions: `-> dict[str, object]`
## Error Handling
- Guard clauses at function entry for precondition violations — `raise ValueError(...)` with descriptive messages:
- Enumerate all missing columns before raising, not just the first:
- External dependency failures: `raise FileNotFoundError(...)` and `raise ImportError(...) from exc` with chaining
- Edge cases return sentinel values rather than raising: `return "none"` (incomplete FVG window), `return False` (boundary checks), `return 0.0` (zero denominator)
## Logging
- Progress messages in `main()` use `end=" ", flush=True` for inline status:
- User-facing errors printed before `sys.exit(1)`:
## Comments
- Docstrings on all public `compute_*` functions (single-line describing the metric)
- Multi-line docstrings on complex builder functions documenting columns, conventions, and math
- Inline comments explain non-obvious logic (barrier stop/target semantics, bin boundaries, window logic)
- No docstrings on `chart_*` or `_*` private helpers
## Function Design
- `compute_*` functions return nested dicts with consistent shape: `{direction: {category: {"total": int, "runs": int}}}`
- `fvg_hold` uses `"held"` instead of `"runs"` as the key: `{"total": int, "held": int}`
- Pipeline functions (`prepare`, `prepare_pair`) return new DataFrames
## Module Design
- `cisd_analysis.py` has no `__all__`; all public-named symbols are importable
- `scripts/__init__.py` is empty — scripts are importable as a package only for testing convenience
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```text
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
- All analysis is driven by a central `ANALYSES` dict of `(label, compute_fn, chart_fn)` triples.
- The data pipeline is strictly one-directional: raw parquet → resampled OHLCV → enriched DataFrame → compute outputs → chart/CSV/HTML.
- All column annotations are precomputed in `prepare()` / `_annotate_cisd_research()`. Downstream `compute_*` functions read precomputed columns only — they do not rediscover events.
- Script consumers (`scripts/`) import from `cisd_analysis` as a library and extend output formats without touching the core pipeline.
## Layers
- Purpose: Load and normalize raw 1-minute parquet data
- Location: `cisd_analysis.py:69–87`
- Contains: `load_1m`, `resample_ohlcv`, `_normalize_resample_rule`
- Depends on: `pandas`, `pyarrow` (parquet), `data/` directory
- Used by: `prepare_pair`, `main`, script consumers
- Purpose: Compute all CISD-derived columns once; results are stable for reuse across all analyses
- Location: `cisd_analysis.py:90–381`
- Contains: `prepare`, `_annotate_cisd_research`, `_compute_three_bar_swings`, `_has_directional_fvg`, `_classify_fvg_hold`, `_has_directional_sweep`, `prepare_pair`, SMT helpers
- Depends on: Data Loading Layer, optional external SMT package
- Used by: Compute Layer, script consumers
- Purpose: Aggregate barrier hit counts into nested dicts by bucket/direction
- Location: `cisd_analysis.py:449–993`
- Contains: `compute_basic`, `compute_mc`, `compute_wick`, `compute_combined`, `compute_volume`, `compute_candle_size`, `compute_size_cross`, `compute_smt_cisd`, `compute_cisd_fvg`, `compute_fvg_hold`, `compute_cisd_fvg_interaction`, `compute_sweep`, `compute_sssf_swing`
- Depends on: Enrichment Layer output (enriched DataFrame columns), `barrier_hit`
- Used by: Rendering Layer, `build_csv_rows`
- Purpose: Transform compute outputs into visual or tabular form
- Location: `cisd_analysis.py:550–1381`; `scripts/build_forward_returns.py`; `scripts/build_expectancy.py`
- Contains: `chart_*` functions, `build_figure`, `build_standalone_figure`, `build_csv_rows`, `main`, and the two script entrypoints
- Depends on: Compute Layer, `matplotlib`
- Used by: CLI invocation only
## Data Flow
### Primary Barrier Analysis Path
### Forward Returns Path
### Expectancy Path
- No shared mutable state. All DataFrame mutations use `.copy()` before modification. The `prepared` dict in `main()` is an in-process cache of enriched DataFrames for reuse by standalone figures.
## Key Abstractions
- Purpose: Declarative mapping of analysis key → (human label, compute function, chart function)
- Location: `cisd_analysis.py:1091`
- Pattern: `dict[str, tuple[str, Callable, Callable]]`; all three elements consumed by `build_figure` and `build_standalone_figure`
- Purpose: Single annotated DataFrame that all compute functions consume without rediscovery
- Key columns: `cisd_type`, `direction`, `prev_*`, `has_dir_fvg_mid0`, `has_dir_fvg_mid1`, `fvg_*_hold_*`, `has_dir_sweep`, `prev_bar_is_dir_swing`, `cisd_bar_is_dir_swing`, `has_swing_smt`, `swing_smt_tag`, `swing_smt_role`
- Pattern: All annotations are boolean flags or categorical strings; no nested structures in the DataFrame
- Purpose: Strict first-touch evaluation — target reached before stop within `LOOKAHEAD` bars
- Location: `cisd_analysis.py:386`
- Used by: every `compute_*` function; also reimplemented inline in `build_expectancy.py` as stop-censored R-multiple logic
- Purpose: Group filter dimensions for the interactive HTML report
- Location: `scripts/build_forward_returns.py:26–50`
- Three families: `core` (SMT, size cross, wick, consec), `fvg` (bucket, mode, state), `structure` (sweep, prev swing, CISD swing)
## Entry Points
- Location: `cisd_analysis.py:1298`
- Triggers: `python3 cisd_analysis.py [key1 key2 ...]`
- Responsibilities: CLI parsing, data load, per-TF figure + CSV + standalone figure dispatch
- Location: `scripts/build_forward_returns.py:687`
- Triggers: `python3 scripts/build_forward_returns.py`
- Responsibilities: Build forward return dataset and render interactive HTML to `output/forward_returns.html`
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
### Row-by-row Python loops in annotation
## Error Handling
- Missing required columns raise `ValueError` immediately: `_annotate_swing_smt_from_events` (`cisd_analysis.py:254`), `_to_smt_ohlc` (`cisd_analysis.py:322`), `compute_smt_cisd` (`cisd_analysis.py:808`)
- SMT scan failure is caught with bare `except Exception` in `build_expectancy.py:304` and `build_forward_returns.py` (implicitly via `with_swing_smt` flag)
- Invalid CLI keys cause `sys.exit(1)` with informative message (`cisd_analysis.py:1314`)
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
