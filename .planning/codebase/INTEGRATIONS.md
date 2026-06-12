# External Integrations

**Analysis Date:** 2026-06-12

## APIs & External Services

**JavaScript CDN (HTML output only):**
- Plotly.js 2.26.0 — loaded at browser runtime from `https://cdn.jsdelivr.net/npm/plotly.js-dist@2.26.0/plotly.min.js` inside the generated `output/forward_returns.html`; no API key; no server-side call; purely a static asset reference embedded by `scripts/build_forward_returns.py` line 432

No other external APIs or web services are used. There are no HTTP clients, REST calls, or network requests in any Python source file.

## Data Storage

**Databases:**
- None. No SQL or NoSQL database.

**File-Based Data Store:**
- Parquet files — `data/nq_1m.parquet` (NQ futures, 1-minute OHLCV) and `data/es_1m.parquet` (ES futures, 1-minute OHLCV)
  - Index column: `DateTime_ET` (Eastern Time timezone-aware datetime)
  - Columns: `Open`, `High`, `Low`, `Close`, `Volume`
  - Read via `pd.read_parquet()` backed by pyarrow 23.0.1
  - These files are excluded from git (`.gitignore` pattern `Data/*.parquet`; actual path is `data/` lowercase)
  - No write-back; data is read-only input

**File Storage:**
- Local filesystem only. Output artifacts (PNG, CSV, HTML, MD) are written to `output/` by the analysis scripts.

**Caching:**
- None.

## Authentication & Identity

**Auth Provider:**
- Not applicable. No authentication layer of any kind.

## Monitoring & Observability

**Error Tracking:**
- None. No Sentry, Rollbar, or equivalent.

**Logs:**
- `print()` statements to stdout only. Notable examples:
  - `cisd_analysis.py` line 1327: `"Loading parquet data..."`
  - Runtime errors surface as Python exceptions with tracebacks

## CI/CD & Deployment

**Hosting:**
- Not applicable. Local research tool only.

**CI Pipeline:**
- None detected. No `.github/`, `.gitlab-ci.yml`, or equivalent CI config.

## Environment Configuration

**Required env vars:**
- None. Zero environment variables are read anywhere in the codebase.

**Secrets location:**
- Not applicable. No secrets or credentials of any kind.

## Local Package Dependency

**SMT Package (`/mnt/e/backup/code/Finance/Misc/SMT`):**
- A local proprietary package that is NOT on PyPI and NOT inside this repo
- Imported lazily at runtime via path injection in `cisd_analysis.py` lines 330-340
- Provides `smt.scan_smts_historical(df_nq, df_es, asset_names, lookback_period, enable_micro, enable_swing, enable_fvg)` returning a DataFrame of SMT divergence events
- Expected columns in the returned DataFrame: `signal_type`, `created_ts`, `sweeping_asset`, `failing_asset`
- Only required when running the `smt_cisd` analysis or calling `prepare_pair(..., with_swing_smt=True)`
- If the path does not exist, `FileNotFoundError` is raised; if the import fails, `ImportError` is raised
- Package metadata (`/mnt/e/backup/code/Finance/Misc/SMT/pyproject.toml`): name `smt`, version `0.1.0`, requires Python >= 3.9, depends on numpy >= 1.23 and pandas >= 1.5

## Webhooks & Callbacks

**Incoming:**
- None.

**Outgoing:**
- None.

---

*Integration audit: 2026-06-12*
