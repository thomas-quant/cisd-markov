# Phase 03: Re-Validate & Republish Existing Findings - Pattern Map

**Mapped:** 2026-06-12
**Files analyzed:** 3 new/modified (+ 1 output artifact, + 1 doc)
**Analogs found:** 3 / 3

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| Discovery summary script/function | utility/script | transform | `scripts/build_expectancy.py` | exact |
| Reconciler script/function | utility/script | transform | `scripts/build_expectancy.py` | exact |
| `README.md` | documentation | static | (manual update) | manual |
| `output/validation_findings.csv` | artifact | (produced) | (output artifact) | n/a |
| WR-04 fix (regen step) | execution | (data regen) | `cisd_analysis.py` (existing) | exact |

---

## Pattern Assignments

### Discovery Summary Script/Function

**Analog:** `scripts/build_expectancy.py`

**Purpose:** Read discovery-slice rows from `validation_manifest.csv`, filter to min_n_pass=True, format as a human-readable CLI table showing rate, n, CI, and OOS eligibility.

**Imports pattern** (lines 26–32):
```python
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
```

**Data loading pattern** (lines 295–310):
```python
def build() -> pd.DataFrame:
    # Load data
    data_root = resolve_data_root()
    dfs_1m = {inst: load_1m(data_root / path.name) for inst, path in INSTRUMENTS.items()}
    
    # Process per timeframe
    for tf_label, tf_rule in TIMEFRAMES.items():
        df_nq, df_es = prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], tf_rule, with_swing_smt=with_smt)
        # ... transform and aggregate
        print(f"[ok] {tf_label}: processed {n_events} events")
    
    return df
```

**CSV reading + filtering pattern** (lines 184–201):
```python
# For the discovery summary, use pandas to read the manifest and filter:
df = pd.read_csv(MANIFEST_PATH)
discovery_only = df[df["slice"] == "discovery"]
reportable = discovery_only[discovery_only["min_n_pass"] == True]

# Group by analysis for per-finding summaries
for analysis in reportable["analysis"].unique():
    analysis_data = reportable[reportable["analysis"] == analysis]
    # ... format as table
```

**Markdown table rendering pattern** (lines 267–290):
```python
def render_markdown(df: pd.DataFrame, smt_available: bool) -> str:
    lines: list[str] = []
    lines.append("# CISD Single-Barrier Expectancy (R-multiples)")
    lines.append("")
    lines.append("| Timeframe | Case | N | Mean R | ... |")
    lines.append("|---|---|--:|--:|")
    for tf_label in TIMEFRAMES:
        tf_rows = sub[sub["timeframe"] == tf_label]
        for _, row in tf_rows.iterrows():
            lines.append(
                "| {tf} | {case} | {n} |".format(
                    tf=tf_label,
                    case=row["case_label"],
                    n=int(row["n"]),
                )
            )
    lines.append("")
    return "\n".join(lines)
```

**Output pattern** (lines 318–323):
```python
CSV_PATH = REPO_ROOT / "output" / "cisd_expectancy.csv"
MD_PATH = REPO_ROOT / "output" / "cisd_expectancy.md"

df.to_csv(CSV_PATH, index=False)
MD_PATH.write_text(render_markdown(df, with_smt))
print(f"[ok] wrote {CSV_PATH}")
print(f"[ok] wrote {MD_PATH}")
```

**Format helper for display** (lines 233–234):
```python
def _fmt(value: float, nd: int = 2) -> str:
    return "n/a" if value is None or (isinstance(value, float) and np.isnan(value)) else f"{value:.{nd}f}"
```

---

### Reconciler Script/Function

**Analog:** `scripts/build_expectancy.py` + `scripts/build_validation.py`

**Purpose:** Read both discovery and OOS slices from `validation_manifest.csv`, merge on (analysis, timeframe, instrument, direction, bucket), compute verdict labels (✓ CONFIRMED, ✗ NOT CONFIRMED, below-n), and write `output/validation_findings.csv`.

**Imports pattern** (same as Discovery Summary):
```python
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cisd_analysis import MIN_N, CI_LEVEL  # May need to import gate logic
```

**Manifest reading and slicing pattern** (from `build_validation.py` lines 202–213):
```python
def slice_df(df: pd.DataFrame, oos: bool = False) -> pd.DataFrame:
    """Return the discovery or OOS slice of *df* based on OOS_START."""
    boundary = pd.Timestamp(OOS_START)
    if oos:
        return df[df.index >= boundary].copy()
    return df[df.index < boundary].copy()

# For manifest CSV:
manifest = pd.read_csv(MANIFEST_PATH)
discovery = manifest[manifest["slice"] == "discovery"].copy()
oos = manifest[manifest["slice"] == "oos"].copy()
```

**Merge/join pattern** (similar to build_expectancy.py's long-table construction):
```python
# Merge on (analysis, timeframe, instrument, direction, bucket)
merge_keys = ["analysis", "timeframe", "instrument", "direction", "bucket"]
reconciled = discovery.merge(
    oos, 
    on=merge_keys, 
    how="outer", 
    suffixes=("_discovery", "_oos")
)

# Extract columns for output
output_rows = []
for _, row in reconciled.iterrows():
    discovery_rate = row.get("rate_discovery")
    discovery_n = row.get("n_discovery")
    oos_rate = row.get("rate_oos")
    oos_n = row.get("n_oos")
    
    # Verdict logic (from CONTEXT.md D-02: OOS confirmed if rate matches direction)
    verdict = determine_verdict(discovery_rate, discovery_n, oos_rate, oos_n)
    
    output_rows.append({
        "analysis": row["analysis"],
        "timeframe": row["timeframe"],
        "instrument": row["instrument"],
        "direction": row["direction"],
        "bucket": row["bucket"],
        "discovery_rate": discovery_rate,
        "discovery_n": discovery_n,
        "discovery_ci_low": row.get("ci_low_discovery"),
        "discovery_ci_high": row.get("ci_high_discovery"),
        "oos_rate": oos_rate,
        "oos_n": oos_n,
        "verdict": verdict,
    })
```

**Verdict determination logic** (from CONTEXT.md D-02, D-03):
```python
def determine_verdict(discovery_rate, discovery_n, oos_rate, oos_n):
    """Classify as CONFIRMED / NOT CONFIRMED / below-n.
    
    - below-n: discovery_n < MIN_N (50)
    - CONFIRMED: discovery_n >= MIN_N AND OOS rate matches direction
    - NOT CONFIRMED: discovery_n >= MIN_N AND OOS rate does NOT match direction
    """
    if pd.isna(discovery_n) or discovery_n < MIN_N:
        return "below-n"
    if pd.isna(oos_rate) or pd.isna(oos_n):
        return "below-n"  # No OOS data available
    
    # Match direction: if discovery > 0.50 (bullish edge), OOS must also be > 0.50
    discovery_bullish_edge = discovery_rate > 0.50
    oos_bullish_edge = oos_rate > 0.50
    
    if discovery_bullish_edge == oos_bullish_edge:
        return "✓ CONFIRMED"
    else:
        return "✗ NOT CONFIRMED"
```

**Output pattern** (from build_expectancy.py lines 318–323, adapted):
```python
OUTPUT_PATH = REPO_ROOT / "output" / "validation_findings.csv"

output_df = pd.DataFrame(output_rows)
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
output_df.to_csv(OUTPUT_PATH, index=False)
print(f"[ok] wrote {OUTPUT_PATH}")
```

---

### README.md Update

**Role:** Documentation/markup (manual update)

**Data source:** `output/validation_findings.csv` (produced by reconciler)

**Pattern:** Each §N table header includes discovery-slice rate, n, CI range, and verdict badge.

**Table format example** (from current README.md §8, to be updated):
```markdown
| Timeframe | Instrument | Direction | Discovery Rate | N | 95% CI | Verdict |
|---|---|---|---|---|---|---|
| Daily | NQ | Bullish | 70.8% | 24 | [52.3–84.5%] | ✓ CONFIRMED |
| Daily | NQ | Bearish | 63.6% | 11 | [32.4–87.0%] | ✓ CONFIRMED |
| Daily | ES | Bullish | 61.5% | 26 | [44.2–76.4%] | (not eligible) |
| Daily | ES | Bearish | 27.8% | 18 | [12.5–47.8%] | ✗ NOT CONFIRMED |
```

**Below-n treatment** (from CONTEXT.md D-06):
```markdown
**Below-n buckets stay visible:**

| Bucket | Rate | N | 95% CI | Status |
|---|---|---|---|---|
| xyz | 55.3% | 12 | [32.1–76.4%] | below-n / not a finding |
```

---

## Shared Patterns

### Manifest Schema (Input)

**Source:** `scripts/build_validation.py:build_manifest_rows()` (lines 108–131)

All Phase 3 scripts consuming the manifest should expect these columns:
```
analysis, timeframe, instrument, direction, bucket,
rate, n, successes, ci_low, ci_high, ci_method, min_n_pass, slice
```

where:
- `rate`, `ci_low`, `ci_high` are proportions in [0, 1] (NOT percentages)
- `min_n_pass` is Boolean (True if n ≥ MIN_N)
- `slice` is "discovery" or "oos"

---

### CSV I/O Pattern

**Used by:** All scripts reading/writing CSVs

```python
import pandas as pd

# Reading
df = pd.read_csv(path)

# Writing
df.to_csv(path, index=False)
path.parent.mkdir(parents=True, exist_ok=True)
```

---

### Progress output pattern

**Used by:** All CLI scripts (build_expectancy.py line 316, build_validation.py line 270)

```python
print(f"[ok] {label}: {detail}")  # Success
print(f"[warn] {label}: {detail}")  # Warning
```

---

### Error handling pattern

**Source:** `build_validation.py` lines 243–251

For optional external dependencies (SMT):
```python
try:
    # Attempt operation
    prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], _first_rule, with_swing_smt=True)
    with_smt = True
except Exception as exc:  # noqa: BLE001
    print(f"[warn] SMT unavailable ({exc}); feature will be empty")
    with_smt = False
```

---

## No Analog Found

All files for Phase 3 have clear analogs in the existing codebase. The discovery summary and reconciler are variations on the `build_expectancy.py` pattern (CSV read → transform → output).

---

## Metadata

**Analog search scope:** `scripts/`, `cisd_analysis.py`
**Files scanned:** 5 (build_expectancy.py, build_forward_returns.py, build_validation.py, cisd_analysis.py, README.md)
**Pattern extraction date:** 2026-06-12

---

## Integration Notes

### Plan 03-01 Workflow

1. **WR-04 fix:** Re-run `cisd_analysis.py` (full history) to regen §8 SMT + §3 within-wick data
2. **Discovery run:** `python3 scripts/build_validation.py` (discovery slice)
3. **Discovery summary:** Call discovery summary function/script → prints CLI table
4. **Researcher review:** Human reads summary, decides whether to proceed to OOS
5. **OOS run:** `python3 scripts/build_validation.py --oos` (OOS slice, prints sacred banner)
6. **Reconciler:** Call reconciler function/script → writes `output/validation_findings.csv`

### Plan 03-02 Workflow

1. Read `output/validation_findings.csv` (from 03-01)
2. Re-run `cisd_analysis.py` for full-history baseline (WR-04 ref)
3. Rewrite README.md tables:
   - Discovery-slice rate replaces full-history rate
   - Add n, CI range, verdict badge columns
   - Below-n buckets marked with "below-n / not a finding"

---

*Pattern mapping complete. Ready for planning phase.*
