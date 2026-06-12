# Technology Stack

**Analysis Date:** 2026-06-12

## Languages

**Primary:**
- Python 3.12.3 — all analysis, scripting, and test code

**Secondary:**
- JavaScript (embedded in generated HTML) — interactive chart rendering inside `output/forward_returns.html`, produced by `scripts/build_forward_returns.py`

## Runtime

**Environment:**
- CPython 3.12.3 (system Python, also used by the project's `.venv`)

**Package Manager:**
- pip 26.0.1 (inside `.venv`)
- Lockfile: not present (no `requirements.txt`, no `pyproject.toml` at repo root; package list is inferred from `.venv/lib/python3.12/site-packages/`)

**Virtual Environment:**
- `.venv/` at repo root (excluded from version control via `.gitignore`)

## Frameworks

**Testing:**
- pytest 9.0.2 — test runner for all files under `tests/`
- pluggy 1.6.0 — pytest plugin system (transitive dependency)

**Build/Dev:**
- No build framework; the project is run directly as scripts (`python3 cisd_analysis.py`, `python3 scripts/build_expectancy.py`, `python3 scripts/build_forward_returns.py`)

## Key Dependencies

**Critical:**
- pandas 3.0.2 — all OHLCV DataFrames, resampling, index alignment, and event tagging throughout `cisd_analysis.py` and both `scripts/` files
- numpy 2.4.4 — vectorised condition logic (`np.where`, `np.select`, `np.percentile`) across all analysis functions
- pyarrow 23.0.1 — Parquet file I/O; `pd.read_parquet` requires this backend; input files are `data/nq_1m.parquet` and `data/es_1m.parquet`
- matplotlib 3.10.8 — all PNG chart rendering; configured globally in `cisd_analysis.py` lines 24-40 with a dark-theme `rcParams` block

**Infrastructure:**
- Pillow 12.2.0 — image support (matplotlib transitive dependency)
- contourpy 1.3.3, cycler 0.12.1, kiwisolver 1.5.0, pyparsing 3.3.2 — matplotlib transitive dependencies
- fontTools 4.62.1 — font handling for matplotlib
- python-dateutil 2.9.0 — pandas datetime parsing (transitive)
- six 1.17.0 — python-dateutil transitive dependency
- packaging 26.0 — build/dependency resolution utility
- pygments 2.20.0 — pytest output colouring (transitive)
- iniconfig 2.3.0 — pytest config file parsing (transitive)

**Local Package (non-PyPI):**
- `smt` — local proprietary package located at `/mnt/e/backup/code/Finance/Misc/SMT`; provides `scan_smts_historical()`; requires numpy >= 1.23 and pandas >= 1.5; only imported at runtime via `_load_scan_smts_historical()` in `cisd_analysis.py` line 330; if the path does not exist, the `smt_cisd` analysis raises `FileNotFoundError`

**Frontend (CDN, no install):**
- Plotly.js 2.26.0 — loaded from `cdn.jsdelivr.net` inside the self-contained `forward_returns.html` output file; used for interactive percentile fan charts

## Configuration

**Environment:**
- No environment variables used anywhere in the codebase
- No `.env` file; all configuration is hardcoded constants at the top of `cisd_analysis.py`

**Key Constants (`cisd_analysis.py` lines 49-66):**
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

**Build:**
- No build step; scripts are run directly
- `scripts/__init__.py` exists so `tests/` can import `scripts.build_expectancy` and `scripts.build_forward_returns` as modules

## Output Artifacts

All output is written to `output/` (not committed):
- Per-timeframe PNG bar charts: `{tf_label}.png`
- Per-timeframe CSV summaries: `{tf_label}.csv`
- Standalone all-TF PNG charts (9 files, e.g. `SMT_CISD_All_Timeframes.png`)
- `cisd_expectancy.csv` — tidy long table of R-multiple distributions
- `cisd_expectancy.md` — methodology and headline expectancy tables
- `forward_returns.html` — self-contained interactive Plotly dashboard

## Platform Requirements

**Development:**
- Python 3.12+ (3.12.3 confirmed)
- Local SMT package at `/mnt/e/backup/code/Finance/Misc/SMT` (required only for `smt_cisd` analysis)
- Data files at `data/nq_1m.parquet` and `data/es_1m.parquet` (1-minute OHLCV with `DateTime_ET` column; excluded from git)

**Production:**
- No deployment target; pure local research tool run as CLI scripts

---

*Stack analysis: 2026-06-12*
