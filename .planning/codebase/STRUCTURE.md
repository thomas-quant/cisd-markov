# Codebase Structure

**Analysis Date:** 2026-06-12

## Directory Layout

```
cisd-markov/
├── cisd_analysis.py        # Core analysis engine (1,380 lines) — single-file monolith
├── CLAUDE.md               # Project guidance for Claude
├── README.md               # Key findings, usage, evaluation model reference
├── data/                   # Input parquet files (not committed)
│   ├── nq_1m.parquet       # NQ 1-minute OHLCV, DateTime_ET index
│   └── es_1m.parquet       # ES 1-minute OHLCV, DateTime_ET index
├── output/                 # All generated artifacts (not committed)
│   ├── {TF}.png            # Per-timeframe barrier analysis figures (Daily/4H/1H/15min)
│   ├── {TF}.csv            # Per-timeframe tidy barrier results
│   ├── *_All_Timeframes.png# Standalone all-TF figures (9 total)
│   ├── forward_returns.html# Interactive Plotly forward-return explorer
│   ├── cisd_expectancy.csv # R-multiple expectancy tidy table
│   └── cisd_expectancy.md  # Expectancy methodology + tables
├── scripts/                # Standalone report builders (import from cisd_analysis)
│   ├── __init__.py
│   ├── build_forward_returns.py  # Interactive HTML forward-return explorer
│   └── build_expectancy.py       # R-multiple expectancy study
├── tests/                  # pytest tests (no subdirectories)
│   ├── test_research_extensions.py
│   ├── test_expectancy_builder.py
│   ├── test_forward_returns_builder.py
│   └── test_swing_smt_integration.py
├── docs/                   # Research planning only
│   └── research_backlog.md # Future study ideas and rough research notes
├── .planning/              # GSD planning artifacts
│   └── codebase/           # Codebase map documents
├── .venv/                  # Python virtual environment (not committed)
└── .gitignore
```

## Directory Purposes

**Root:**
- Purpose: Single-file analysis engine lives here alongside project docs
- Key files: `cisd_analysis.py` (the entire pipeline), `CLAUDE.md` (project context)

**`data/`:**
- Purpose: Raw input data — parquet files are the only required external dependency
- Contains: `nq_1m.parquet`, `es_1m.parquet`
- Generated: No — sourced externally
- Committed: No (gitignored)

**`output/`:**
- Purpose: All generated artifacts from analysis runs
- Contains: PNGs, CSVs, HTML, Markdown
- Generated: Yes — by `cisd_analysis.py` and `scripts/build_*.py`
- Committed: No (gitignored at the data level, but the directory may contain committed sample artifacts)

**`scripts/`:**
- Purpose: Auxiliary report builders that import `cisd_analysis` as a library and generate additional output formats
- Contains: `build_forward_returns.py` (interactive HTML), `build_expectancy.py` (R-multiple study)
- Pattern: Each script has its own `main()` and is run directly

**`tests/`:**
- Purpose: pytest test suite; all test files live flat in this directory
- Contains: Unit and integration tests for core functions and script consumers
- Key files: `test_research_extensions.py` (FVG/sweep/swing annotation), `test_swing_smt_integration.py` (SMT left-window matching), `test_expectancy_builder.py`, `test_forward_returns_builder.py`

**`docs/`:**
- Purpose: Research planning and backlog only — not consumed by code
- Contains: `research_backlog.md` — future study ideas and Discord notes

## Key File Locations

**Entry Points:**
- `cisd_analysis.py:1298`: `main()` — primary CLI entry, all barrier analyses
- `scripts/build_forward_returns.py:687`: `main()` — forward return HTML builder
- `scripts/build_expectancy.py:295`: `build()` — R-multiple expectancy builder

**Configuration (top of `cisd_analysis.py`):**
- `cisd_analysis.py:49–53`: `DATA_DIR`, `INSTRUMENTS` dict (maps instrument name → parquet path)
- `cisd_analysis.py:54–59`: `TIMEFRAMES` dict (maps label → resample rule)
- `cisd_analysis.py:60–66`: `LOOKAHEAD`, `MAX_CONSEC`, `SMT_LOOKBACK`, `FVG_HOLD_LOOKAHEAD`, `SWEEP_TOLERANCE`, `SWEEP_SWING_LOOKBACK`, `_SMT_PKG_PATH`

**Analysis Registry:**
- `cisd_analysis.py:1091`: `ANALYSES` dict — maps key → (label, compute_fn, chart_fn)
- `cisd_analysis.py:1300`: `STANDALONE_KEYS` set — keys that render as all-TF figures
- `cisd_analysis.py:1357`: `FILENAMES` dict — maps standalone key → output filename

**Core Pipeline:**
- `cisd_analysis.py:71`: `load_1m` — parquet loader
- `cisd_analysis.py:85`: `resample_ohlcv` — OHLCV aggregation
- `cisd_analysis.py:90`: `prepare` — DataFrame enrichment (all CISD columns)
- `cisd_analysis.py:359`: `prepare_pair` — dual-instrument pipeline with optional SMT
- `cisd_analysis.py:386`: `barrier_hit` — core barrier evaluation function

**Annotation Helpers (private, called from `prepare`):**
- `cisd_analysis.py:111`: `_compute_three_bar_swings`
- `cisd_analysis.py:129`: `_has_directional_fvg`
- `cisd_analysis.py:142`: `_classify_fvg_hold`
- `cisd_analysis.py:168`: `_has_directional_sweep`
- `cisd_analysis.py:191`: `_annotate_cisd_research`

**SMT Helpers (private):**
- `cisd_analysis.py:249`: `_annotate_swing_smt_from_events`
- `cisd_analysis.py:320`: `_to_smt_ohlc`
- `cisd_analysis.py:330`: `_load_scan_smts_historical`
- `cisd_analysis.py:343`: `_scan_swing_smt_events`

**Testing:**
- `tests/test_research_extensions.py`: FVG, sweep, swing annotation unit tests
- `tests/test_swing_smt_integration.py`: SMT left-window matching and role assignment
- `tests/test_expectancy_builder.py`: R-multiple builder tests
- `tests/test_forward_returns_builder.py`: Forward return row builder tests

## Naming Conventions

**Files:**
- Snake case for Python modules: `cisd_analysis.py`, `build_forward_returns.py`, `build_expectancy.py`
- Snake case with `test_` prefix for test files: `test_research_extensions.py`
- Upper camel case + suffix for output PNGs: `CISD_FVG_All_Timeframes.png`, `CandleSize_All_Timeframes.png`

**Functions:**
- Public pipeline functions: `snake_case` — `load_1m`, `prepare`, `prepare_pair`, `barrier_hit`
- Compute functions: `compute_{key}` — always takes `df: pd.DataFrame`, returns nested dict
- Chart functions: `chart_{key}` — always takes `(ax, data_nq, data_es)`
- Private helpers: `_snake_case` prefix — `_annotate_cisd_research`, `_has_directional_fvg`, etc.

**DataFrame Columns:**
- Enriched boolean flags: `has_dir_fvg_mid0`, `has_dir_sweep`, `prev_bar_is_dir_swing`, `cisd_bar_is_dir_swing`
- Hold state strings: `fvg_mid0_hold_close_near`, `fvg_mid0_hold_wick_far` (values: `"held"`, `"failed"`, `"none"`)
- SMT columns: `has_swing_smt` (bool), `swing_smt_tag` (str: `"w/ SMT"` / `"no SMT"`), `swing_smt_role` (str: `"swept"` / `"failed_to_sweep"` / `"none"`)
- Direction strings: `"bullish"`, `"bearish"`, `"neutral"` (never abbreviated)

**Analysis Keys:**
- Short snake_case identifiers used as CLI args and dict keys: `basic`, `mc`, `wick`, `combined`, `cisd_fvg`, `fvg_hold`, `smt_cisd`, `sweep`, `sssf_swing`

## Where to Add New Code

**New Barrier Analysis:**
1. Write `compute_{name}(df: pd.DataFrame) -> dict` consuming precomputed columns from `prepare()` — add to `cisd_analysis.py` after the existing compute functions (around L993)
2. Write `chart_{name}(ax, data_nq, data_es)` using `_bar_label` / `_style_ax` helpers — add after existing chart functions (around L1088)
3. Register in `ANALYSES` dict at `cisd_analysis.py:1091`
4. If standalone (all-TF figure): add key to `STANDALONE_KEYS` set and `FILENAMES` dict inside `main()` (`cisd_analysis.py:1300`, `1357`)
5. Add CSV flattening logic to the `build_csv_rows` key-dispatch block (`cisd_analysis.py:1109`)
6. Add tests in `tests/test_research_extensions.py` or a new `tests/test_{name}.py`

**New Annotation Column (added to `prepare()`):**
1. Add column initialization with safe default in `_annotate_cisd_research` before the main loop (`cisd_analysis.py:198–207`)
2. Populate the column inside the existing `for idx, ct in enumerate(annotated["cisd_type"])` loop
3. Add column name + default to `CASE_FLAG_DEFAULTS` in `scripts/build_expectancy.py:50` if it should appear in the expectancy study
4. Add `_ensure_column` call + derived column logic in `build_forward_return_rows` (`scripts/build_forward_returns.py:97`)

**New Script (auxiliary output format):**
- Create `scripts/build_{name}.py`
- Import needed symbols: `from cisd_analysis import INSTRUMENTS, TIMEFRAMES, load_1m, prepare_pair`
- Include `resolve_data_root()` for worktree support (mirror pattern from `scripts/build_forward_returns.py:339`)
- Add `if __name__ == "__main__": main()` guard

**Utilities:**
- Shared charting helpers: `_bar_label`, `_style_ax`, `_standalone_lookahead_caption` in `cisd_analysis.py:417–444`
- `pv(num, den)` percentage helper: `cisd_analysis.py:417`
- `_count_consecutive` helper: `cisd_analysis.py:405`

## Special Directories

**`.planning/`:**
- Purpose: GSD planning artifacts (phase plans, codebase map)
- Generated: Yes — by GSD tooling
- Committed: Yes

**`.venv/`:**
- Purpose: Python virtual environment
- Generated: Yes
- Committed: No

**`.pytest_cache/`:**
- Purpose: pytest cache
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-06-12*
