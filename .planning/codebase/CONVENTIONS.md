# Coding Conventions

**Analysis Date:** 2026-06-12

## Naming Patterns

**Files:**
- `snake_case.py` for all source and script files: `cisd_analysis.py`, `build_forward_returns.py`, `build_expectancy.py`
- Test files: `test_<module_or_feature>.py` in `tests/` directory

**Functions:**
- Public functions: `snake_case` — e.g., `prepare`, `resample_ohlcv`, `barrier_hit`, `compute_basic`, `chart_basic`
- Private helpers: `_snake_case` with leading underscore — e.g., `_compute_three_bar_swings`, `_has_directional_fvg`, `_classify_fvg_hold`, `_annotate_cisd_research`
- Compute functions: `compute_<analysis_name>(df) -> dict` pattern — e.g., `compute_wick`, `compute_sweep`, `compute_smt_cisd`
- Chart functions: `chart_<analysis_name>(ax, data_nq, data_es)` pattern — e.g., `chart_wick`, `chart_sweep`
- Builder functions: `build_<output>(...)` — e.g., `build_forward_return_rows`, `build_csv_rows`, `build_figure`, `build_dataset`

**Variables:**
- Local variables: `snake_case`
- Short loop variables acceptable for tight iteration: `ct` (cisd_type), `ts` (timestamp), `idx`, `i`, `j`, `k`
- Column alignment for parallel short assignments:
  ```python
  totals = {"bullish": 0, "bearish": 0}
  runs   = {"bullish": 0, "bearish": 0}
  ```

**Constants:**
- Module-level: `UPPER_SNAKE_CASE` — e.g., `LOOKAHEAD`, `MAX_CONSEC`, `SMT_LOOKBACK`, `TIMEFRAMES`, `COLORS`, `ANALYSES`
- Private module-level: `_UPPER_SNAKE_CASE` — e.g., `_SMT_PKG_PATH`
- Inline bin/bucket definitions: `UPPER_CASE` locals — e.g., `BINS`, `BUCKETS` inside compute functions

**Column names in DataFrames:**
- All lowercase with underscores: `cisd_type`, `has_dir_fvg_mid0`, `fvg_mid0_hold_close_near`, `swing_smt_tag`, `prev_bar_is_dir_swing`
- OHLCV columns lowercase: `open`, `high`, `low`, `close`, `volume`
- Direction strings are lowercase literals: `"bullish"`, `"bearish"`, `"neutral"`

## Code Style

**Formatting:**
- 4-space indentation throughout
- No formatter config file detected (no pyproject.toml, .flake8, setup.cfg)
- Column alignment used for parallel dict/variable assignments to improve readability
- No trailing whitespace convention enforced by tooling

**Linting:**
- No linting configuration detected
- Code passes clean without any noqa suppressions

**Section Separators:**
- Use `# ── Section Name ─────────────────────────────────────────────────────────────` to delineate logical sections within a module:
  ```python
  # ── Configuration ─────────────────────────────────────────────────────────────
  # ── Data Loading & Resampling ─────────────────────────────────────────────────
  # ── Core Barrier Logic ────────────────────────────────────────────────────────
  # ── Helpers ───────────────────────────────────────────────────────────────────
  # ── Compute Functions ─────────────────────────────────────────────────────────
  # ── Chart Functions ───────────────────────────────────────────────────────────
  ```

## Import Organization

**Order:**
1. `from __future__ import annotations` (in scripts only, not `cisd_analysis.py`)
2. Standard library: `sys`, `json`, `copy`, `html`, `itertools`, `pathlib`
3. Third-party: `numpy`, `pandas`, `matplotlib`
4. Local/project: `from cisd_analysis import ...` or `import cisd_analysis`

**Path injection for script imports:**
`scripts/build_forward_returns.py` and `scripts/build_expectancy.py` add `REPO_ROOT` to `sys.path` at module level so `cisd_analysis` is importable:
```python
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
```

**Lazy imports:**
Some imports placed inside functions when only needed for specific execution paths:
```python
from matplotlib.patches import Patch   # inside build_figure, build_standalone_figure
from smt import scan_smts_historical   # inside _load_scan_smts_historical
```

**Path Aliases:**
- None. Imports use direct module names or sys.path manipulation.

## Type Annotations

**Coverage:**
- `cisd_analysis.py`: Most public and private functions fully annotated. `main()` has `-> None`. `chart_*` functions annotate `title: str` but omit `ax` and `data_*` types (matplotlib Axes not imported at module level for type purposes).
- `scripts/build_forward_returns.py`, `scripts/build_expectancy.py`: Full annotations with `from __future__ import annotations`; use `dict[str, str]`, `dict[str, object]`, `list[dict[str, str]]`, `dict[str, float] | None`

**Return types:**
- Compute functions: `-> dict` (bare dict, not fully parameterized)
- Pipeline functions: `-> pd.DataFrame` or `-> tuple[pd.DataFrame, pd.DataFrame]`
- Boolean predicates: `-> bool`
- Classification functions: `-> str`
- Builder config functions: `-> dict[str, object]`

## Error Handling

**Patterns:**
- Guard clauses at function entry for precondition violations — `raise ValueError(...)` with descriptive messages:
  ```python
  if "cisd_type" not in df.columns:
      raise ValueError("df must contain cisd_type column")
  ```
- Enumerate all missing columns before raising, not just the first:
  ```python
  missing_event_columns = [col for col in required if col not in events.columns]
  if missing_event_columns:
      raise ValueError(f"events must contain columns: {', '.join(missing_event_columns)}")
  ```
- External dependency failures: `raise FileNotFoundError(...)` and `raise ImportError(...) from exc` with chaining
- Edge cases return sentinel values rather than raising: `return "none"` (incomplete FVG window), `return False` (boundary checks), `return 0.0` (zero denominator)

**No try/except:** No exception catching in the codebase; errors propagate to the caller or to `main()`.

## Logging

**Framework:** `print()` to stdout — no logging library.

**Patterns:**
- Progress messages in `main()` use `end=" ", flush=True` for inline status:
  ```python
  print(f"  {instr} from {path.name} ...", end=" ", flush=True)
  print(f"{len(dfs_1m[instr]):,} bars")
  ```
- User-facing errors printed before `sys.exit(1)`:
  ```python
  print(f"Unknown key(s): {', '.join(invalid)}")
  print(f"Valid: {', '.join(ANALYSES.keys())}")
  sys.exit(1)
  ```

## Comments

**When to Comment:**
- Docstrings on all public `compute_*` functions (single-line describing the metric)
- Multi-line docstrings on complex builder functions documenting columns, conventions, and math
- Inline comments explain non-obvious logic (barrier stop/target semantics, bin boundaries, window logic)
- No docstrings on `chart_*` or `_*` private helpers

**Style:**
```python
def compute_basic(df: pd.DataFrame) -> dict:
    """Barrier run rate across all CISDs."""
    ...

def barrier_hit(df: pd.DataFrame, idx: int, row: pd.Series, ct: str) -> bool:
    """
    Returns True if the TARGET is hit before the STOP within LOOKAHEAD bars.
      Bullish: target = CISD high, stop = CISD low
      Bearish: target = CISD low,  stop = CISD high
    """
    ...
```

## Function Design

**Size:** Compute functions are typically 15–40 lines. Chart functions 15–30 lines. Heavy annotation loops live in `_annotate_cisd_research` (~55 lines).

**Immutability:** DataFrames are copied at the start of pipeline functions to avoid mutating inputs:
```python
df = df.copy()       # in prepare()
annotated = df.copy()  # in _annotate_cisd_research()
```

**Return Values:**
- `compute_*` functions return nested dicts with consistent shape: `{direction: {category: {"total": int, "runs": int}}}`
- `fvg_hold` uses `"held"` instead of `"runs"` as the key: `{"total": int, "held": int}`
- Pipeline functions (`prepare`, `prepare_pair`) return new DataFrames

## Module Design

**Exports:**
- `cisd_analysis.py` has no `__all__`; all public-named symbols are importable
- `scripts/__init__.py` is empty — scripts are importable as a package only for testing convenience

**Registration Pattern:**
All analyses registered in a single dict:
```python
ANALYSES = {
    "basic":  ("Basic Barrier Run Rate",  compute_basic,  chart_basic),
    "sweep":  ("Sweep Confirmation",      compute_sweep,  chart_sweep),
    # ...
}
```

Each entry is a `(label: str, compute_fn: Callable, chart_fn: Callable)` triple. Adding a new analysis requires adding one entry here plus optionally to `STANDALONE_KEYS` and `FILENAMES` in `main()`.

---

*Convention analysis: 2026-06-12*
