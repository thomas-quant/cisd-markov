# Phase 5: New CISD Research on the Validated Engine - Pattern Map

**Mapped:** 2026-06-14
**Files analyzed:** 6 files to be modified
**Analogs found:** 6 / 6 (100% coverage)

---

## File Classification

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `cisd_data.py` | annotation | precompute-in-prepare | `_annotate_cisd_research()` lines 168–231 | exact (same function) |
| `cisd_barriers.py` compute | compute layer | CRUD barrier counts | `compute_wick()` lines 147–179 (RES-01), `compute_sweep()` lines 475–490 (RES-02) | exact (same pattern) |
| `cisd_barriers.py` registry | registry | N/A | `ANALYSES` dict + `ANALYSIS_META` NamedTuple lines 527–579 | exact (same registry) |
| `cisd_charts.py` | chart rendering | request-response (dict→PNG) | `chart_wick()` lines 146–160 (RES-01), `chart_sweep()` lines 310–320 (RES-02) | exact (same pattern) |
| `cisd_analysis.py` | re-export shim | module interface | Existing `__all__` list at file bottom | exact (append only) |
| `scripts/build_validation.py` | harness branch | manifest row emission | `build_manifest_rows()` dispatch block lines 155–207 (generic `else` branch) | exact (slot into existing pattern) |
| `tests/test_research_extensions.py` | unit test | assertion-based validation | Test fixtures lines 7–147, test patterns in existing file | exact (same framework) |

---

## Pattern Assignments

### `cisd_data.py` — Add annotation columns to `_annotate_cisd_research()`

**Role:** Data enrichment / column annotation  
**Data Flow:** Precompute once in prepare pipeline, consume in compute functions  
**Analog:** `_annotate_cisd_research()` lines 168–231

**Bulk-accumulate-then-assign pattern** (lines 175–231):
```python
# Pre-initialise result lists with defaults (bool columns → False; categorical → "none"/"other")
has_dir_fvg_mid0_lst          = [False] * n
has_dir_fvg_mid1_lst          = [False] * n
fvg_mid0_hold_close_near_lst  = ["none"] * n
# ... more lists ...

event_pos = np.flatnonzero(pd.notna(ct_arr) & np.isin(ct_arr, ["bullish", "bearish"]))

for idx in event_pos:
    ct = ct_arr[idx]
    # Per-event logic: compute boolean/categorical values and append to lists
    if _has_directional_fvg(annotated, idx, ct):
        has_dir_fvg_mid0_lst[idx]         = True
        fvg_mid0_hold_close_near_lst[idx] = _classify_fvg_hold(annotated, idx, ct, "close_near")

# Bulk-assign accumulated lists to columns
annotated["has_dir_fvg_mid0"]         = has_dir_fvg_mid0_lst
annotated["has_dir_fvg_mid1"]         = has_dir_fvg_mid1_lst
annotated["fvg_mid0_hold_close_near"] = fvg_mid0_hold_close_near_lst
```

**Mirror this pattern for RES-01 features:** Add lists for `candle1_close_dir`, `candle1_past_candle0_wick`, `candle2_gap_dir`, `candle1_failed_followthrough` (and any others). Loop over `event_pos`, compute feature values per event, bulk-assign to DataFrame at end.

**Key insight:** This is the ONLY place where new feature columns live; downstream compute functions read these precomputed columns and never rediscover events.

---

### `cisd_barriers.py` — Add `compute_candle1_followthrough()` (RES-01)

**Role:** Barrier count aggregation (compute layer)  
**Data Flow:** Event-bucketing → nested dict counts `{dir: {tag: {total, runs}}}`  
**Analog:** `compute_wick()` lines 147–179 (exact forward-analog: `candle[1]` close vs `candle[0]` wick)

**RES-01 compute structure** (mirror `compute_wick` but read from `candle[1]` features):
```python
def compute_candle1_followthrough(df: pd.DataFrame) -> dict:
    """Barrier run rate split by candle[1] close direction and wick position."""
    stats = {
        "bullish": {
            "against_inwindow": {"total": 0, "runs": 0},
            "with_within_wick_inwindow": {"total": 0, "runs": 0},
            "with_past_wick_inwindow": {"total": 0, "runs": 0},
            "against_forward": {"total": 0, "runs": 0},
            "with_within_wick_forward": {"total": 0, "runs": 0},
            "with_past_wick_forward": {"total": 0, "runs": 0},
        },
        "bearish": { # ... symmetric ... },
    }
    ct_arr    = df["cisd_type"].to_numpy(dtype=object)
    # ... read precomputed candle[1] feature columns ...
    event_pos = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    for pos in event_pos:
        ct = ct_arr[pos]
        # Determine bucket tag from precomputed features
        tag = _classify_candle1_bucket(df, pos, ct)  # or inline logic
        stats[ct][tag]["total"] += 1
        if barrier_hit(df, pos, df.iloc[pos], ct):  # in-window: unchanged
            stats[ct][tag]["runs"] += 1
        # Forward variant: barrier_hit starting at idx+2
        if barrier_hit_forward(df, pos, df.iloc[pos], ct):  # re-anchored
            stats[ct][tag+"_forward"]["runs"] += 1
    return stats
```

**Vectorization pattern** (copy from `compute_wick` lines 159–167):
```python
bull_mask = (
    np.isin(prev_dir, ["bearish"]) &
    (close_arr > prev_close_arr)
)
for pos in np.flatnonzero(bull_mask):
    grp = "past_wick" if close_arr[pos] > prev_high_arr[pos] else "within_wick"
    stats["bullish"][grp]["total"] += 1
    if barrier_hit(df, pos, df.iloc[pos], "bullish"):
        stats["bullish"][grp]["runs"] += 1
```

**Barrier re-anchoring for forward window:** Adapt `barrier_hit(df, idx, row, ct)` logic (lines 42–58) to a variant that iterates from `idx+2` instead of `idx+1`. Same target/stop levels (`row["high"]/row["low"]`), same lookahead count `LOOKAHEAD`, just advance the starting point by 1 bar.

---

### `cisd_barriers.py` — Add `compute_post_cisd_context()` (RES-02)

**Role:** Barrier count aggregation (compute layer)  
**Data Flow:** Multi-bar event-bucketing → nested dict counts `{dir: {tag: {total, runs}}}`  
**Analog:** `compute_sweep()` lines 475–490 (minimal `{dir: {tag: {total, runs}}}` shape)

**RES-02 compute structure** (single precondition, one gap-direction bucket layer):
```python
def compute_post_cisd_context(df: pd.DataFrame) -> dict:
    """Barrier run rate: candle[1] failed continuation, bucketed by candle[2] gap direction."""
    stats = {
        "bullish": {
            "failed_gap_with": {"total": 0, "runs": 0},
            "failed_gap_against": {"total": 0, "runs": 0},
            "failed_gap_flat": {"total": 0, "runs": 0},
        },
        "bearish": { # ... symmetric ... },
    }
    ct_arr = df["cisd_type"].to_numpy(dtype=object)
    # ... read precomputed candle[1] failed / candle[2] gap features ...
    event_pos = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    for pos in event_pos:
        ct = ct_arr[pos]
        # Precondition: candle[1] failed (precomputed feature)
        if not df["candle1_failed_followthrough"].iloc[pos]:
            continue
        # Gap direction from precomputed feature
        tag = df["candle2_gap_dir"].iloc[pos]  # "gap_with", "gap_against", "flat"
        stats[ct][tag]["total"] += 1
        # Re-anchored barrier: start lookahead at candle[2] (idx+2)
        if barrier_hit_forward(df, pos, df.iloc[pos], ct):
            stats[ct][tag]["runs"] += 1
    return stats
```

**Mirror `compute_sweep` pattern** (lines 477–490 for bucket shape):
```python
stats = {
    "bullish": {"w/ sweep": {"total": 0, "runs": 0}, "no sweep": {"total": 0, "runs": 0}},
    "bearish": {"w/ sweep": {"total": 0, "runs": 0}, "no sweep": {"total": 0, "runs": 0}},
}
ct_arr    = df["cisd_type"].to_numpy(dtype=object)
sweep_arr = df["has_dir_sweep"].to_numpy(dtype=bool)
event_pos = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
for pos in event_pos:
    ct  = ct_arr[pos]
    tag = "w/ sweep" if sweep_arr[pos] else "no sweep"
    stats[ct][tag]["total"] += 1
    if barrier_hit(df, pos, df.iloc[pos], ct):
        stats[ct][tag]["runs"] += 1
```

---

### `cisd_barriers.py` — Update `ANALYSES` and `ANALYSIS_META` registries

**Role:** Declarative registry of compute+chart pairs and metadata  
**Analog:** `ANALYSES` dict lines 527–542 + `ANALYSIS_META` NamedTuple+dict lines 554–579

**Add to `ANALYSES` dict** (mirror structure, lines 528–541):
```python
ANALYSES = {
    # ... existing 14 analyses ...
    "candle1_followthrough": ("Candle[1] Follow-Through", compute_candle1_followthrough, chart_candle1_followthrough),
    "post_cisd_context":     ("Post-CISD Context",        compute_post_cisd_context,     chart_post_cisd_context),
}
```

**Add to `ANALYSIS_META` dict** (mirror structure, lines 562–579):
```python
ANALYSIS_META: dict[str, _AnalysisMeta] = {
    # ... existing entries ...
    # Standalone analyses (assuming user decides both are standalone per discretion note)
    "candle1_followthrough": _AnalysisMeta(per_tf_height=8,  standalone=True,  standalone_height=8,  filename="Candle1_Followthrough_All_Timeframes.png"),
    "post_cisd_context":     _AnalysisMeta(per_tf_height=6,  standalone=True,  standalone_height=6,  filename="PostCISD_Context_All_Timeframes.png"),
}
```

**Key insight:** These two dicts are the single source of truth. Adding an entry here automatically makes the analysis discoverable by `main()`, `build_figure()`, `build_validation.py`, and the re-export shim.

---

### `cisd_charts.py` — Add `chart_candle1_followthrough()` and `chart_post_cisd_context()`

**Role:** Matplotlib rendering (dict → horizontal bar chart)  
**Data Flow:** Nested dict computed from compute function → visual output  
**Analog (RES-01):** `chart_wick()` lines 146–160 (same 2-level nesting: direction → bucket tags → `{total, runs}`)

**RES-01 chart pattern** (mirror `chart_wick` structure):
```python
def chart_candle1_followthrough(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in (
                ("against_inwindow", 1.0),
                ("with_within_wick_inwindow", 0.65),
                ("with_past_wick_inwindow", 1.0),
                ("against_forward", 0.5),
                ("with_within_wick_forward", 0.3),
                ("with_past_wick_forward", 0.8),
            ):
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]),
                             COLORS[instr][ct],
                             alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Candle[1] Follow-Through (In-Window vs Forward Re-Anchored)")
```

**Analog (RES-02):** `chart_sweep()` lines 310–320 (minimal 1-level nesting: direction → tag → `{total, runs}`)

**RES-02 chart pattern** (mirror `chart_sweep` structure):
```python
def chart_post_cisd_context(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in (
                ("failed_gap_with", 1.0),
                ("failed_gap_against", 0.6),
                ("failed_gap_flat", 0.3),
            ):
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]),
                             COLORS[instr][ct],
                             alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Post-CISD Context (Candle[1] Failed + Candle[2] Gap)")
```

---

### `cisd_analysis.py` — Update re-export `__all__`

**Role:** Module interface / public symbol export  
**Data Flow:** Forward-export from `cisd_barriers` and `cisd_charts`  
**Analog:** Existing `__all__` list at bottom of file

**Action:** Append the new compute and chart function names to the public exports so they remain importable by scripts and tests:
```python
__all__ = [
    # ... existing exports ...
    # New RES-01 and RES-02
    "compute_candle1_followthrough",
    "chart_candle1_followthrough",
    "compute_post_cisd_context",
    "chart_post_cisd_context",
]
```

**Key insight:** The re-export shim ensures that `scripts/build_validation.py` and tests can import these functions as `from cisd_analysis import compute_candle1_followthrough`, maintaining the current import convention.

---

### `scripts/build_validation.py` — Add manifest dispatch branch

**Role:** Harness row-emission layer (compute dict → tidy long manifest rows)  
**Data Flow:** Request-response: (df, key, instrument) → list of manifest row dicts  
**Analog:** `build_manifest_rows()` dispatch block lines 155–207

**Generic fallback pattern** (lines 202–207, re-usable for both RES-01 and RES-02):
```python
else:
    # Generic: smt_cisd, cisd_fvg, sweep, sssf_swing
    # shape: {dir: {tag: {"total", "runs"}}}
    for ct in ("bullish", "bearish"):
        for tag, d in data[ct].items():
            emit(key, instrument, ct, tag, d["total"], d["runs"])
```

**Both RES-01 (`candle1_followthrough`) and RES-02 (`post_cisd_context`) should fit into this generic branch** (they return `{dir: {tag: {total, runs}}}` shape). No special-case branch required if the nested dict shape matches.

**If bucket tags need custom handling** (e.g., splitting on a suffix like `_inwindow` vs `_forward`), add a dedicated branch:
```python
elif key == "candle1_followthrough":
    for ct in ("bullish", "bearish"):
        for tag, d in data[ct].items():
            emit(key, instrument, ct, tag, d["total"], d["runs"])
elif key == "post_cisd_context":
    for ct in ("bullish", "bearish"):
        for tag, d in data[ct].items():
            emit(key, instrument, ct, tag, d["total"], d["runs"])
```

**Key insight:** The `emit()` helper (lines 120–139) already handles Wilson CI, n-gating, and slice labeling. Just call it once per bucket with `(analysis, instrument, direction, bucket, n, k)` and the row is ready for the manifest CSV.

---

### `tests/test_research_extensions.py` — Add unit tests for RES-01 and RES-02

**Role:** Behavior-locking unit tests  
**Data Flow:** Synthetic test frames → fixture → assertion on computed dict  
**Analog:** Existing test file structure lines 7–147 (fixture-based test framework)

**Test fixture pattern** (re-use `_annotated_barrier_df()` or create `_candle1_followthrough_df()`):
```python
def _candle1_followthrough_df():
    """Synthetic frame with candle[1] feature columns pre-annotated."""
    index = pd.date_range("2026-01-01 09:30", periods=10, freq="15min")
    return pd.DataFrame({
        "open": [...],
        "high": [...],
        "low": [...],
        "close": [...],
        "cisd_type": [...],
        "candle1_close_dir": [...],  # precomputed features
        "candle1_past_candle0_wick": [...],
        "candle2_gap_dir": [...],
        "candle1_failed_followthrough": [...],
        # ... other required annotation columns ...
    }, index=index)
```

**Test assertion pattern** (lock behavior before implementation):
```python
def test_compute_candle1_followthrough_returns_nested_dict():
    df = _candle1_followthrough_df()
    result = cisd_analysis.compute_candle1_followthrough(df)
    
    # Verify shape: {dir: {tag: {total, runs}}}
    assert isinstance(result, dict)
    assert set(result.keys()) == {"bullish", "bearish"}
    for ct in ("bullish", "bearish"):
        assert isinstance(result[ct], dict)
        for tag, d in result[ct].items():
            assert set(d.keys()) == {"total", "runs"}
            assert d["total"] >= 0 and d["runs"] >= 0
            assert d["runs"] <= d["total"]

def test_compute_post_cisd_context_respects_precondition():
    """Verify that events are only counted if candle[1] failed."""
    df = _candle1_followthrough_df()
    result = cisd_analysis.compute_post_cisd_context(df)
    
    # All buckets should have n <= (number of events with candle[1] failed)
    expected_max_n = df["candle1_failed_followthrough"].sum()
    total_n = sum(d["total"] for ct in result.values() for d in ct.values())
    assert total_n <= expected_max_n
```

**Key insight:** These tests lock the EXACT output shape before the implementation details change. They run on every commit and prevent silent behavior shifts.

---

## Shared Patterns

### Barrier Lookahead and Re-anchoring
**Source:** `cisd_barriers.py:barrier_hit()` lines 42–58  
**Apply to:** Both `compute_candle1_followthrough()` and `compute_post_cisd_context()` for forward-window variant  

The core lookahead loop:
```python
def barrier_hit(df: pd.DataFrame, idx: int, row: pd.Series, ct: str) -> bool:
    """Returns True if TARGET hit before STOP within LOOKAHEAD bars."""
    for j in range(1, LOOKAHEAD + 1):
        if idx + j >= len(df):
            break
        bar = df.iloc[idx + j]
        if ct == "bullish":
            if bar["low"] <= row["low"]:    return False   # stop
            if bar["high"] >= row["high"]:  return True    # target
        else:
            if bar["high"] >= row["high"]:  return False   # stop
            if bar["low"] <= row["low"]:    return True    # target
    return False
```

**For re-anchored forward window (RES-01):** Create a variant that iterates `for j in range(2, LOOKAHEAD + 2)` (or parameterize `start_offset`), keeping the same target/stop logic but advancing the window by 1 bar.

### Vectorized Event Detection
**Source:** `cisd_data.py:_annotate_cisd_research()` lines 189–230  
**Apply to:** Feature column precomputation in `_annotate_cisd_research()`

Pattern for finding CISD events:
```python
ct_arr = annotated["cisd_type"].to_numpy(dtype=object)
event_pos = np.flatnonzero(pd.notna(ct_arr) & np.isin(ct_arr, ["bullish", "bearish"]))

for idx in event_pos:
    ct = ct_arr[idx]
    # ... per-event logic ...
```

**For new features:** Use the same `event_pos` loop to compute `candle[1]` and `candle[2]` features, appending to pre-initialized lists, then bulk-assign.

### Manifest Row Emission (Harness Integration)
**Source:** `scripts/build_validation.py:build_manifest_rows()` lines 120–139 (emit helper)  
**Apply to:** Both RES-01 and RES-02 manifest rows

The `emit()` function signature and usage:
```python
def emit(analysis: str, instrument: str, direction: str, bucket: str, n: int, k: int) -> None:
    if k > n:
        print(f"[warn] {analysis}/{instrument}/{direction}/{bucket}: k={k} > n={n}; skipping")
        return
    lo, hi = wilson_ci(n, k)
    rows.append({
        "analysis":   analysis,
        "timeframe":  tf_label,
        "instrument": instrument,
        "direction":  direction,
        "bucket":     bucket,
        "rate":       round(k / n, 6) if n > 0 else 0.0,
        "n":          n,
        "successes":  k,
        "ci_low":     round(lo, 6),
        "ci_high":    round(hi, 6),
        "ci_method":  "wilson",
        "min_n_pass": n_gate(n),
        "slice":      slice_label,
    })
```

**Both analyses should use the generic dispatch branch** (lines 202–207) which iterates over `{dir: {tag: {total, runs}}}` and calls `emit()` once per bucket. No special casing needed if the nested dict shape is consistent.

---

## No Analog Found

All target files have clear analogs in the existing codebase. Full coverage achieved.

---

## Metadata

**Analog search scope:** Core modules (`cisd_data.py`, `cisd_barriers.py`, `cisd_charts.py`) + scripts (`build_validation.py`) + tests (`test_research_extensions.py`)

**Files scanned:** 7 (all target files plus dependencies)

**Pattern extraction date:** 2026-06-14

**Confidence level:** High — the refactored engine has locked patterns (vectorization style, registry structure, harness dispatch) that carry forward to the two new analyses with minimal variation.

---

## PATTERN MAPPING COMPLETE

**Phase:** 5 - New CISD Research on the Validated Engine  
**Files classified:** 6 (1 annotation enrichment, 2 compute functions, 1 chart pair, 1 re-export shim, 1 harness branch, 1 test suite)  
**Analogs found:** 6 / 6 (100% match coverage)

### Coverage Summary
- Annotation columns: `_annotate_cisd_research()` loop pattern (exact match)
- Compute RES-01: `compute_wick()` vectorization + `barrier_hit()` re-anchoring (exact match)
- Compute RES-02: `compute_sweep()` minimal dict shape (exact match)
- Chart RES-01: `chart_wick()` 2-level nesting (exact match)
- Chart RES-02: `chart_sweep()` 1-level nesting (exact match)
- Registry: `ANALYSES` + `ANALYSIS_META` structure (exact match)
- Harness: `build_manifest_rows()` generic fallback branch (exact match)
- Tests: Fixture-based assertion pattern (exact match)

### Key Patterns Identified
1. **Precompute-in-prepare, consume-in-compute:** All new feature columns live in `_annotate_cisd_research()`; compute functions read precomputed flags only.
2. **Vectorized event loops:** Use `np.flatnonzero()` + array indexing; accumulate in lists, bulk-assign to DataFrame at end.
3. **Nested dict shape consistency:** Both RES-01 and RES-02 return `{dir: {tag: {total, runs}}}` so they slot into the generic harness branch without special-casing.
4. **Barrier re-anchoring:** Duplicate the `barrier_hit()` logic but start the lookahead at `idx+2` instead of `idx+1` for forward-window metrics (same target/stop levels).
5. **Manifest integration:** The harness `emit()` helper handles Wilson CI, n-gating, and slice labeling; both new analyses need only call `emit()` once per bucket.
6. **Chart alpha layering:** Use alpha transparency (1.0, 0.65, 0.3) to visually distinguish bucket prominence; follow the existing color scheme (NQ teal, ES amber).

### Ready for Planning
Pattern mapping complete. Planner can now assign work to implement RES-01 and RES-02 by copying and adapting the concrete code excerpts above. All files are additive (no modifications to existing compute/chart/test behavior); characterization tests will remain locked.
