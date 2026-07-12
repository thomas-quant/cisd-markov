# Phase 9: SMT Geometry & Invalidation Honesty - Pattern Map

**Mapped:** 2026-07-12
**Files analyzed:** 6 (all modified, no new source files except possibly a doc script)
**Analogs found:** 6 / 6 (all in-repo, same-module analogs — no cross-project lookup needed)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|----------------|
| `cisd_data.py` (`_annotate_swing_smt_from_events`) | transform / enrichment | event-driven (vectorized annotation) | itself — extend the existing vectorized matcher (`cisd_data.py:451-560`) | exact (same function, widened) |
| `cisd_data.py` (`_scan_swing_smt_events`, `prepare_pair`) | service / pipeline | request-response (calls external scanner, threads columns) | itself (`cisd_data.py:586-624`) | exact |
| `cisd_barriers.py` (`compute_smt_cisd` → three-way + survived/broke) | service (compute) | CRUD/aggregate (nested-dict counters) | `compute_candle_size` (`cisd_barriers.py:277-309`) for ATR/bucket pattern; itself for the tag-dict shape | exact (self) + role-match (ATR) |
| `cisd_barriers.py` (new `compute_smt_role`) | service (compute) | CRUD/aggregate | `compute_smt_cisd` (`cisd_barriers.py:357-378`) | exact — near-identical shape, different tag source column |
| `cisd_barriers.py` (new geometry-bucket compute, e.g. `compute_smt_block_size`) | service (compute) | CRUD/aggregate | `compute_candle_size` (`cisd_barriers.py:277-309`) | exact |
| `cisd_barriers.py` (`ANALYSES` / `ANALYSIS_META` registry entries) | config/registry | request-response (dict lookup) | existing `smt_cisd` / `candle_size` rows (`cisd_barriers.py:685-741`) | exact |
| `cisd_charts.py` (new `chart_smt_role`, extended `chart_smt_cisd`) | component (chart render) | transform | `chart_smt_cisd` (`cisd_charts.py:241-253`) and `chart_size_cross` (alpha-tiered rows, `cisd_charts.py:221-238`) | exact |
| `scripts/build_validation.py` | service (manifest dispatch) | batch/transform | `build_manifest_rows` generic branch (`scripts/build_validation.py:299-304`) — **no code change expected**, only verify new bucket shapes fit | exact (pass-through) |
| New README §8 subsection ("SMT Invalidation Honesty (v2.0)") | doc | transform (script-generated numbers + hand-written prose) | Phase 7's "Post-CISD Context — Corrected Re-Validation (v2.0)" section (`README.md:400-420`) and its generator `scripts/build_post_cisd_verdict.py` | exact |
| Possible new doc-gen script (before/after SMT rates) | service (report builder) | batch/transform | `scripts/build_post_cisd_verdict.py` (full file) and `scripts/build_reconcile_findings.py` (merge + verdict pattern) | role-match |

## Pattern Assignments

### `cisd_data.py` — `_annotate_swing_smt_from_events` (transform, event-driven)

**Analog:** itself, `cisd_data.py:451-560` (the function this phase widens in place)

**Current required-columns pattern** (lines 467-473):
```python
required_event_columns = ("signal_type", "created_ts", "sweeping_asset", "failing_asset")
if "cisd_type" not in df.columns:
    raise ValueError("df must contain cisd_type column")

missing_event_columns = [column for column in required_event_columns if column not in events.columns]
if missing_event_columns:
    raise ValueError(f"events must contain columns: {', '.join(missing_event_columns)}")
```
D-01/D-02 widen `required_event_columns` to also pull `reference_price, invalidation_asset, invalidation_direction, invalidation_level, broken_ts, status, reference_timestamp` (all already in `EVENT_COLUMNS` per the SMT package — no scanner change needed).

**Vectorized match + write pattern** (lines 496-558): this is the pattern to extend. The existing per-direction loop builds `matched_ts`, `matched_sweeping`, `matched_failing` numpy arrays gathered via `matched_candidate_pos = safe_pos[in_window]` and writes them into pre-allocated full-length arrays (`has_swing_smt`, `swing_smt_tag`, `swing_smt_match_ts`, `swing_smt_role`) using `array[match_positions] = ...`. Copy this exact gather-and-scatter idiom for the new fields:
```python
matched_sweeping = event_sweeping[matched_candidate_pos]
matched_failing  = event_failing[matched_candidate_pos]

has_swing_smt[match_positions] = True
swing_smt_tag[match_positions] = "w/ SMT"
swing_smt_match_ts[match_positions] = matched_ts
swing_smt_role[match_positions] = np.where(
    matched_sweeping == instrument, "swept",
    np.where(matched_failing == instrument, "failed_to_sweep", "none"),
)
```
D-01's validity check must be added as one more vectorized array gathered the same way — `matched_broken_ts = event_broken_ts[matched_candidate_pos]`, then `still_valid = pd.isna(matched_broken_ts) | (matched_broken_ts > row_ts)` — and used to split `swing_smt_tag[match_positions]` into `"w/ SMT"` vs `"expired SMT"` (D-03), never a re-introduced per-bar Python loop (explicit anti-pattern warning in CONTEXT.md).

**Empty/degenerate-path pattern** (lines 481-482, 493-494): both `annotated.empty or events.empty` and `filtered.empty` return the already-defaulted `annotated` early. Any new column needs its own line in the same default block (lines 475-479):
```python
annotated["has_swing_smt"] = False
annotated["swing_smt_tag"] = "no SMT"
annotated["swing_smt_match_ts"] = pd.NaT
annotated["swing_smt_role"] = "none"
```
New defaults (`annotated["smt_reference_price"] = np.nan`, `annotated["smt_broken_ts"] = pd.NaT`, `annotated["smt_status"] = "none"`, `annotated["smt_block_size_atr"] = np.nan`, `annotated["cisd_in_smt_block"] = False`, survived/broke flag) belong here, following the same one-line-per-column style.

**Docstring convention** (lines 452-466): the function's docstring documents *why* it is vectorized and cites the plan file that derived the semantics. Any new plan produced by this phase's planner should get the same citation-style docstring update.

---

### `cisd_data.py` — `_scan_swing_smt_events` / `prepare_pair` (service, request-response)

**Analog:** itself, `cisd_data.py:586-624` — **no code change expected** here per CONTEXT.md ("no scanner change and no new SMT call"); only verify the event columns already returned by `scan_smts_historical` (line 590-598) flow untouched into `_annotate_swing_smt_from_events(df_nq, events, instrument="NQ")` (line 622). This confirms the widened `required_event_columns` tuple in the annotator is the only touch point.

---

### `cisd_barriers.py` — `compute_smt_cisd` three-way + survived/broke (compute, CRUD/aggregate)

**Analog:** itself, `cisd_barriers.py:357-378` (two-way today) + `compute_candle_size` for the ATR/bucket idiom (`cisd_barriers.py:277-309`)

**Current two-way shape** (lines 357-378):
```python
def compute_smt_cisd(df: pd.DataFrame) -> dict:
    """Barrier run rate split by whether a matching Swing SMT co-occurs."""
    if "swing_smt_tag" not in df.columns:
        raise ValueError("df must contain swing_smt_tag column")

    stats = {
        "bullish": {"w/ SMT": {"total": 0, "runs": 0}, "no SMT": {"total": 0, "runs": 0}},
        "bearish": {"w/ SMT": {"total": 0, "runs": 0}, "no SMT": {"total": 0, "runs": 0}},
    }

    ct_arr  = df["cisd_type"].to_numpy(dtype=object)
    tag_arr = df["swing_smt_tag"].to_numpy(dtype=object)
    event_pos = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    for pos in event_pos:
        ct  = ct_arr[pos]
        tag = tag_arr[pos]
        if ct not in stats or tag not in stats[ct]:
            continue
        stats[ct][tag]["total"] += 1
        if barrier_hit(df, pos, df.iloc[pos], ct):
            stats[ct][tag]["runs"] += 1
    return stats
```
D-03 extends `stats[ct]` to a third key `"expired SMT"` — the dict-shape and loop body are otherwise unchanged; `swing_smt_tag` just carries a third value now (written by the annotator above). D-07's survived/broke sub-buckets (`"w/ SMT & survived"`, `"w/ SMT & broke"`) are additional sibling keys in the *same* `stats[ct]` dict — added by checking a new boolean column (e.g. `smt_broke_in_window`) only when `tag == "w/ SMT"`, following the exact same `stats[ct][key]["total"] += 1` / `barrier_hit(...)` idiom. Keep this flat — do not nest — since the generic manifest dispatch (see below) expects a flat `{dir: {tag: {total, runs}}}` shape.

**ATR(14) + bucket idiom to copy for `smt_block_size_atr`** (lines 277-309, especially 282-288):
```python
atr = (df["high"] - df["low"]).rolling(14).mean()
BINS = [
    (0,    0.5,  "<0.5x ATR"),
    (0.5,  1.0,  "0.5x-1x ATR"),
    (1.0,  1.5,  "1x-1.5x ATR"),
    (1.5,  1e18, ">1.5x ATR"),
]
...
for pos in event_pos:
    atr_val = atr_arr[pos]
    if pd.isna(atr_val) or atr_val <= 0:
        continue
    body  = abs(close_arr[pos] - open_arr[pos])
    ratio = body / atr_val
    ct    = ct_arr[pos]
    for lo, hi, lbl in BINS:
        if lo <= ratio < hi:
            stats[ct][lbl]["total"] += 1
            if barrier_hit(df, pos, df.iloc[pos], ct):
                stats[ct][lbl]["runs"] += 1
            break
```
Per CONTEXT.md this is the literal reference implementation for D-04's ATR normalization and D-04's bucket-threshold convention — reuse verbatim, substituting `body = block_high - block_low` computed from the `reference_timestamp` bar's own high/low (not the CISD bar's open/close), and gate on `cisd_in_smt_block`/matched-SMT-exists per D-05a (skip `pos` entirely when no matched SMT, rather than adding a "none" bucket, to keep the population correctly restricted).

---

### `cisd_barriers.py` — new `compute_smt_role` (compute, CRUD/aggregate)

**Analog:** `compute_smt_cisd` (`cisd_barriers.py:357-378`) — near copy-paste, swap `swing_smt_tag` for `swing_smt_role` and the tag vocabulary `("w/ SMT", "no SMT")` for `("swept", "failed_to_sweep")` (per CONTEXT D-08, filtered to the valid `w/ SMT` population only — i.e. this compute should first restrict `event_pos` to rows where the *fixed* `swing_smt_tag == "w/ SMT"` before bucketing by role, since `swing_smt_role` is otherwise `"none"` for `no SMT`/`expired SMT` rows).

---

### `cisd_barriers.py` — registry wiring (config/registry)

**Analog:** existing `smt_cisd` rows in both dicts (`cisd_barriers.py:685-741`)

```python
"smt_cisd":     ("Swing SMT Confirmation",               compute_smt_cisd,     chart_smt_cisd),
...
"smt_cisd":             _AnalysisMeta(per_tf_height=4,  standalone=True,  standalone_height=6,  filename="SMT_CISD_All_Timeframes.png"),
```
D-08's new `smt_role` entry is a straight sibling line in both dicts, e.g.:
```python
"smt_role":     ("Swing SMT Role (Swept vs Failed-to-Sweep)", compute_smt_role, chart_smt_role),
...
"smt_role":             _AnalysisMeta(per_tf_height=4,  standalone=True,  standalone_height=6,  filename="SMT_Role_All_Timeframes.png"),
```
Per CLAUDE.md's "Adding a New Analysis" section, this is the *only* registry edit point — `main()`'s `STANDALONE_KEYS`/`FILENAMES` in the historical single-file version are now fully derived from `ANALYSIS_META`, so no other file needs to change for wiring (confirm at implementation time that `cisd_barriers.py`'s `main()`-equivalent entry point still reads `ANALYSIS_META` rather than a separate hardcoded dict, per the registry's own docstring at lines 705-712).

---

### `cisd_charts.py` — `chart_smt_cisd` extension + new `chart_smt_role`

**Analog:** `chart_smt_cisd` (`cisd_charts.py:241-253`) and the alpha-tiered pattern in `chart_size_cross` / `chart_cisd_fvg` (`cisd_charts.py:221-238`, `256-268`)

**Current two-way chart** (lines 241-253):
```python
def chart_smt_cisd(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in (("w/ SMT", 1.0), ("no SMT", 0.55)):
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]), COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55)
            for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Swing SMT Confirmation")
```
D-03's three-way split just extends the `for tag, alpha in (...)` tuple list to three entries, e.g. `(("w/ SMT", 1.0), ("expired SMT", 0.75), ("no SMT", 0.45))` — matching the exact alpha-tiering convention already used in `chart_cisd_fvg` (three-tag) and `chart_fvg_hold`/`chart_cisd_fvg_interaction` (nested tag) elsewhere in this file. `chart_smt_role` is a straight copy of this function's structure with `("swept", 1.0), ("failed_to_sweep", 0.6)` as the tag/alpha tuple and `_style_ax(ax, "Swing SMT Role")`.

---

### `scripts/build_validation.py` — `build_manifest_rows` generic dispatch

**Analog:** itself, `scripts/build_validation.py:299-304` — **verify only, do not duplicate logic**:
```python
else:
    # Generic: smt_cisd, cisd_fvg, sweep, sssf_swing
    # shape: {dir: {tag: {"total", "runs"}}}
    for ct in ("bullish", "bearish"):
        for tag, d in data[ct].items():
            emit(key, instrument, ct, tag, d["total"], d["runs"])
```
Because `compute_smt_cisd`'s three-way/survived-broke output and the new `compute_smt_role`/geometry compute all stay flat `{dir: {tag: {total, runs}}}`, they fall into this generic branch automatically — **no change to `build_validation.py` is required**, confirming CONTEXT.md's "new buckets get n/CI/FDR/WF for free via this path" claim. The only action item is adding `"smt_role"` (and the geometry-bucket key) to whatever `keys` list callers pass into `build_manifest_rows` (check `main()`/CLI arg defaults in this script and in `cisd_barriers.py` if there's a hardcoded "all analysis keys" list anywhere).

---

### README §8 new subsection (doc, transform)

**Analog:** "Post-CISD Context — Corrected Re-Validation (v2.0)" (`README.md:400-420`) and its generator `scripts/build_post_cisd_verdict.py`

The Phase 7 section shows the pattern to reuse for D-09: badge-vocabulary prose (`✓ CORRECTED-BAR CLEARED`, `not-cleared`) immediately followed by a markdown table with script-generated numeric columns (`n_buckets`, `n_cleared`, `verdict`) and hand-written interpretive prose below it discussing specific rows. `scripts/build_post_cisd_verdict.py`'s full structure (path constants at module top patched-in-tests style, `_MERGE_KEYS`, `_BUCKET_OUTPUT_COLS`/`_ROLLUP_OUTPUT_COLS`, a `_bucket_clears` verdict function, writing two CSVs) is the closest analog for a new "before vs after SMT rates" doc-gen script, should the planner choose to add one; alternatively extend `scripts/build_reconcile_findings.py` (`scripts/build_reconcile_findings.py:1-40` shows its module docstring/contract) if a single merged findings table is preferred over a bespoke script (Claude's Discretion per CONTEXT.md).

Existing §8 table header to extend/replace in place (`README.md:256`):
```
| Timeframe | Instrument | Direction | w/ SMT Rate | w/ SMT N | 95% CI | no SMT Rate | Δ | Verdict (w/ SMT) |
```
D-09's refresh adds the `expired SMT` bucket's rate/n as new columns or a companion table, and the new before/after subsection sits immediately above or below this table, per Phase 7's precedent of appending rather than deleting prior content.

---

## Shared Patterns

### Vectorized gather-scatter annotation (no per-bar Python loops)
**Source:** `cisd_data.py:496-558` (`_annotate_swing_smt_from_events`)
**Apply to:** all new/widened SMT annotation columns
```python
matched_candidate_pos = safe_pos[in_window]
matched_x = event_x[matched_candidate_pos]      # gather from event arrays
array_x[match_positions] = matched_x            # scatter into full-length output array
```
This is an explicit CLAUDE.md/CONTEXT.md-flagged anti-pattern boundary: do NOT reintroduce a per-bar Python loop for D-01's validity check or any geometry feature.

### Nested-dict compute shape `{direction: {tag: {"total": int, "runs": int}}}`
**Source:** every `compute_*` in `cisd_barriers.py` except `fvg_hold` (`"held"` key) and `cisd_fvg_interaction` (extra nesting level)
**Apply to:** `compute_smt_cisd` (extended), `compute_smt_role`, geometry-bucket compute — all must stay flat two-level so they hit `build_manifest_rows`'s generic branch (`scripts/build_validation.py:299-304`) with zero harness changes.

### ATR(14) normalization
**Source:** `cisd_barriers.py:282` — `(df["high"] - df["low"]).rolling(14).mean()`
**Apply to:** `smt_block_size_atr` (D-04) — do not invent a true-range variant; reuse this exact one-liner, evaluated at bar `t` per Claude's Discretion default.

### Bucket-threshold convention `<0.5x / 0.5-1x / 1-1.5x / >1.5x ATR`
**Source:** `cisd_barriers.py:283-288` (`compute_candle_size` BINS list)
**Apply to:** the new `smt_block_size_atr` bucketing, per CONTEXT.md's explicit instruction to follow this convention.

### Alpha-tiered chart rows for multi-tag splits
**Source:** `cisd_charts.py:241-253` (`chart_smt_cisd`), `221-238` (`chart_size_cross`), `256-268` (`chart_cisd_fvg`)
**Apply to:** `chart_smt_cisd`'s three-way extension and new `chart_smt_role` — full alpha (1.0) for the primary/valid tag, progressively dimmer for secondary/negative tags.

### Registry-driven wiring (no scattered hardcoded key lists)
**Source:** `cisd_barriers.py:685-741` (`ANALYSES` + `ANALYSIS_META`)
**Apply to:** the new `smt_role` analysis — add exactly one line to each dict; per the `_AnalysisMeta` docstring (`cisd_barriers.py:705-712`) this is deliberately the single edit point that used to require synchronizing 4 call sites.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| New before/after SMT-rate doc-gen script (if planner adds a distinct file rather than extending `build_reconcile_findings.py`) | service (report builder) | batch/transform | No prior script diffs two versions of the *same* analysis's published rate under a methodology fix — `build_post_cisd_verdict.py` is the nearest analog (verdict/rollup CSV pattern) but answers a different question (corrected-bar clearing, not before/after drift); planner should decide new-file-vs-extend per CONTEXT.md's Claude's Discretion note. |

## Metadata

**Analog search scope:** `cisd_data.py`, `cisd_barriers.py`, `cisd_charts.py`, `scripts/build_validation.py`, `scripts/build_reconcile_findings.py`, `scripts/build_post_cisd_verdict.py`, `README.md`
**Files scanned:** 7
**Pattern extraction date:** 2026-07-12
