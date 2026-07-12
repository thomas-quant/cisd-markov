# Phase 10: New Conditioning Features (Magnitude, Session, Volume Anomaly) - Pattern Map

**Mapped:** 2026-07-12
**Files analyzed:** 5 modules (all modified, no new source files expected)
**Analogs found:** 5 / 5 — this is explicitly "Phase 9 mechanics applied to new features"; every artifact has a strong in-repo analog, several of them Phase-9-authored code that is itself the freshest and most literal template.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|----------------|
| `cisd_data.py` — new annotation columns (`session_tag`, `wick_distance_atr`, `sweep_depth_atr` + pierced level, `fvg_size_atr` + gap width, RVOL/z-score/effort inputs) in `_annotate_cisd_research` (`:182`) | transform / enrichment | event-driven (vectorized annotation) | `smt_block_size_atr`/`cisd_in_smt_block` addition in the same function (`cisd_data.py:505-506` defaults, `:552-673` gather/scatter) — the most recent precedent for adding an ATR-normalized, gated magnitude column | exact (freshest in-repo template, same function) |
| `cisd_data.py` — sweep pierced-level / FVG gap-width extraction | transform / enrichment | event-driven (vectorized) | sweep detection block (`cisd_data.py:228-279`, `roll_min_prior_swing_low`/`roll_max_prior_swing_high`) and FVG mid0/mid1 block (`:281-303`) — the exact rolling-window values already computed just need to be *retained* as columns instead of only feeding a boolean | exact (extend existing rolling series) |
| `cisd_barriers.py` — `compute_wick_distance` (or similar; signed-continuous magnitude, all CISDs) | service (compute) | CRUD/aggregate (nested-dict counters) | `compute_candle_size` (`cisd_barriers.py:280-312`) for the ATR+fixed-bin idiom; `compute_wick` (`:187-219`) for the population (all CISDs, no gating) and to cross-check the 0-edge bin against the existing past/within split | exact (ATR-bin) + role-match (population) |
| `cisd_barriers.py` — `compute_sweep_depth` (ATR-normalized, gated on `has_dir_sweep`) | service (compute) | CRUD/aggregate | `compute_smt_block_size` (`cisd_barriers.py:444-476`) — **the single closest analog in the whole codebase**: ATR-ratio column, `pd.isna(ratio)` skip for the ungated population, same fixed BINS convention | exact |
| `cisd_barriers.py` — `compute_fvg_size` (ATR-normalized, gated on `has_dir_fvg_mid0`/`mid1`) | service (compute) | CRUD/aggregate | `compute_smt_block_size` (`cisd_barriers.py:444-476`) again, plus `compute_cisd_fvg` (`:513-548`) for the mid0/mid1 dual-population structure | exact |
| `cisd_barriers.py` — `compute_session` (3-bucket, TF-gated) | service (compute) | CRUD/aggregate | `compute_smt_role` (`cisd_barriers.py:406-441`) for the "filter to valid population first, then bucket by a precomputed string column" shape; `compute_smt_cisd` (`:360-403`) for the plain flat 3-way tag dict shape | role-match (structure identical; population filter is TF not tag) |
| `cisd_barriers.py` — `compute_effort_result`, `compute_rvol` / `compute_volume_zscore` | service (compute) | CRUD/aggregate | `compute_volume` (`cisd_barriers.py:247-277`) — same family (volume ratio, fixed bins), untouched sibling to sit beside per D-10 | exact |
| `cisd_barriers.py` — `ANALYSES` / `ANALYSIS_META` registry entries + new `applies_to`/`timeframes` field | config/registry | request-response (dict lookup) | existing `smt_role`/`smt_block_size` rows (`cisd_barriers.py:826-829`, `:868-871`) for the entry shape; `_AnalysisMeta` `NamedTuple` (`:849-854`) is the exact place to add the D-14 allow-list field | exact |
| `cisd_charts.py` — new `chart_wick_distance`, `chart_sweep_depth`, `chart_fvg_size`, `chart_session`, `chart_effort_result`, `chart_rvol` | component (chart render) | transform | `chart_candle_size` (`cisd_charts.py:204-218`, single-population 4-bin) and `chart_smt_block_size` (`:274-...`, alpha-tiered 4-bin) for magnitude charts; `chart_smt_role` (`:259-271`) for the 2-3-way tag chart shape (session/effort) | exact |
| `cisd_charts.py` — `build_figure` (`:524`) / `build_standalone_figure` (`:585`) TF-scoping for `applies_to` | component (figure dispatch) | transform | the two functions themselves, extended to skip a key when `tf_label not in ANALYSIS_META[key].applies_to` | exact (self, extended) |
| `scripts/build_validation.py` — `all_keys` TF-scoping in `main()` | service (manifest dispatch) | batch/transform | `main()`'s `for tf_label, tf_rule in TIMEFRAMES.items(): ... all_keys` loop (`scripts/build_validation.py:637`, `:677`-`693`) — filter `all_keys` per `tf_label` using the same `ANALYSIS_META[key].applies_to` field before calling `build_manifest_rows`/`build_walkforward_rows` | exact (self, extended) |
| `scripts/build_validation.py` — `build_manifest_rows` generic dispatch branch | service (manifest dispatch) | batch/transform | `build_manifest_rows` generic `else` branch (`:299-304`) — **no code change needed** as long as new compute functions stay flat `{dir: {tag: {total, runs}}}` | exact (pass-through) |
| `README.md` — new methodology subsection (magnitude/session/volume-anomaly + D-11 caveats + D-13 moved-q-value note) | doc | transform (script-generated numbers + hand-written prose) | Phase 9's SMT-invalidation-honesty README subsection and Phase 7's "Post-CISD Context — Corrected Re-Validation (v2.0)" section (`README.md:400-420`) | exact |

## Pattern Assignments

### `cisd_data.py` — new annotation columns in `_annotate_cisd_research` (transform, event-driven)

**Analog:** the `smt_block_size_atr` / `cisd_in_smt_block` addition inside the same function.

**Default-column block pattern** (`cisd_data.py:505-506`, and see `:424-432` for the general "one line per column, unconditionally set on `annotated`" convention):
```python
annotated["smt_block_size_atr"] = np.nan
annotated["cisd_in_smt_block"] = False
```
D-06a's new columns (`sweep_depth_atr`, `swept_level`, `fvg_size_atr`, `fvg_gap_width`) each need exactly one such default line — `np.nan` for ATR-ratio/level/width floats (undefined-where-not-applicable per D-05), `False`/`"none"` for any categorical flags. `session_tag` gets a placeholder default (e.g. `"none"`) on TFs where it's not registered — D-02 keeps it unregistered in the *compute/registry* layer, not necessarily absent from the annotation.

**Existing rolling-window values to *retain* instead of only using for a boolean** (`cisd_data.py:244-260`, sweep) and (`:287-303`, FVG):
```python
masked_low_for_swing  = np.where(swing_low_np, low, np.inf)
roll_min_prior_swing_low = (
    pd.Series(masked_low_for_swing, index=idx_ax)
    .rolling(window=SWEEP_SWING_LOOKBACK, min_periods=1)
    .min()
    .shift(1)
    .to_numpy()
)
...
bullish_sweep_trigger = np.isfinite(roll_min_prior_swing_low) & (low < roll_min_prior_swing_low)
```
The sweep's pierced level *is* `roll_min_prior_swing_low`/`roll_max_prior_swing_high` at the triggering bar — D-06a's `swept_level` column is this same array, gathered at the winning `sweep_idx` within the trailing `SWEEP_TOLERANCE` window (mirrors the `bullish_sweep_any` rolling-max-of-boolean reduction, but must also carry back *which* bar and *what level* triggered — likely needs a rolling `idxmax`/argmax-style companion array, still vectorized, no per-bar Python loop). `sweep_depth_atr` is then `(low[event_bar] - swept_level) / atr[event_bar]` for bullish (mirror for bearish), computed only where `has_dir_sweep` is True (else `np.nan`).

For FVG, `left_high_mid0`/`right_low_mid0` (`cisd_data.py:287-290`) already are the gap boundary; gap width is simply `right_low_mid0 - left_high_mid0` (bull) / `left_low_mid0 - right_high_mid0` (bear) — a one-line vectorized subtraction using arrays already computed, gated by `has_dir_fvg_mid0`/`has_dir_fvg_mid1`.

**`wick_distance_atr` is free** — `prev_high`/`prev_low`/`close` (`cisd_data.py:87-90`) and ATR(14) (copy `compute_candle_size`'s `(df["high"] - df["low"]).rolling(14).mean()`, see below) already exist; this is a pure one-liner using `np.where`/`np.select` on `is_bullish`/`is_bearish` exactly like every other directional column in this function (e.g. `has_dir_fvg_mid0` at `:294`).

**Session tag** — a plain vectorized hour/minute-of-day slice on the tz-naive `idx_ax` (`cisd_data.py:204`), e.g.:
```python
minute_of_day = idx_ax.hour * 60 + idx_ax.minute
session_tag = np.select(
    [(minute_of_day >= 570) & (minute_of_day < 630),   # 09:30-10:30
     (minute_of_day >= 630) & (minute_of_day < 960)],  # 10:30-16:00
    ["rth_open", "rth"],
    default="overnight",
)
```
No existing time-of-day column exists in the codebase — this is genuinely new logic, but the vectorized-`np.select`-on-array style is identical to every other categorical column already in this function (e.g. `cisd_type` at `cisd_data.py:91-98`, `direction` at `:83-86`).

**RVOL / z-score slot baseline (D-08)** — no existing same-time-of-day-slot rolling baseline exists in the codebase; nearest structural analog is the plain trailing-window rolling ops already in this file (`.rolling(14).mean()`, `.rolling(SWEEP_SWING_LOOKBACK, min_periods=1).min()`), but the *grouping by slot* is new. Recommended vectorized approach: `df.groupby(minute_of_day)["volume"].transform(lambda s: s.rolling(K, min_periods=1).mean())`-style slot-grouped rolling (pandas native, still no per-bar Python loop) — or equivalently a `pivot`-then-`rolling`-then-`unstack` round trip if `groupby().rolling()` proves too slow at 1-min-index scale. Flag this to the planner as the one spot needing a fresh vectorized idiom, not a literal copy.

---

### `cisd_barriers.py` — `compute_sweep_depth` / `compute_fvg_size` (compute, CRUD/aggregate, ATR-gated)

**Analog:** `compute_smt_block_size` (`cisd_barriers.py:444-476`) — copy near-verbatim, swap the source column:
```python
def compute_smt_block_size(df: pd.DataFrame) -> dict:
    if "smt_block_size_atr" not in df.columns:
        raise ValueError("df must contain smt_block_size_atr column")

    BINS = [
        (0,    0.5,  "<0.5x ATR"),
        (0.5,  1.0,  "0.5x-1x ATR"),
        (1.0,  1.5,  "1x-1.5x ATR"),
        (1.5,  1e18, ">1.5x ATR"),
    ]
    ct_arr    = df["cisd_type"].to_numpy(dtype=object)
    ratio_arr = df["smt_block_size_atr"].to_numpy(dtype=float)
    event_pos = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    stats = {ct: {lbl: {"total": 0, "runs": 0} for _, _, lbl in BINS}
             for ct in ("bullish", "bearish")}
    for pos in event_pos:
        ratio = ratio_arr[pos]
        if pd.isna(ratio):
            continue
        ct = ct_arr[pos]
        for lo, hi, lbl in BINS:
            if lo <= ratio < hi:
                stats[ct][lbl]["total"] += 1
                if barrier_hit(df, pos, df.iloc[pos], ct):
                    stats[ct][lbl]["runs"] += 1
                break
    return stats
```
`compute_sweep_depth` = this function with `"smt_block_size_atr"` → `"sweep_depth_atr"` and the `pd.isna(ratio)` skip is exactly D-05's "depth undefined where no sweep" contract (the annotation already leaves it `np.nan` off-population, so no extra `has_dir_sweep` check is needed here — same discipline as `compute_smt_block_size` relying on `pd.isna` alone). `compute_fvg_size` = the same shape with `"fvg_size_atr"`, but per `compute_cisd_fvg`'s mid0/mid1 dual-population structure (`cisd_barriers.py:513-548`) it may need `mid0_fvg`/`mid1_fvg` sub-buckets, not one flat population — confirm at planning time whether D-05 wants mid0 and mid1 gap sizes reported separately or unioned.

---

### `cisd_barriers.py` — `compute_wick_distance` (compute, CRUD/aggregate, signed, all-CISD population)

**Analog:** `compute_candle_size` (`cisd_barriers.py:280-312`) for ATR + fixed-bin idiom, `compute_wick` (`:187-219`) for the ungated all-CISD population and the two-bucket vocabulary this feature subsumes:
```python
def compute_candle_size(df: pd.DataFrame) -> dict:
    atr = (df["high"] - df["low"]).rolling(14).mean()
    BINS = [
        (0,    0.5,  "<0.5x ATR"),
        (0.5,  1.0,  "0.5x-1x ATR"),
        (1.0,  1.5,  "1x-1.5x ATR"),
        (1.5,  1e18, ">1.5x ATR"),
    ]
    ...
    for lo, hi, lbl in BINS:
        if lo <= ratio < hi:
            ...
```
D-06 requires a **signed** bin set with an edge at exactly 0 (unlike the unsigned `compute_candle_size` BINS above), e.g.:
```python
BINS = [
    (-1e18, -1.0, "<-1x ATR (deep within wick)"),
    (-1.0,   0.0, "-1x-0 ATR (within wick)"),
    (0.0,    1.0, "0-1x ATR (past wick)"),
    (1.0,   1e18, ">1x ATR (far past wick)"),
]
```
Population is **all CISDs** (no `pd.isna` skip beyond ATR itself) — `wick_distance_atr` is always defined once ATR is defined, matching `compute_candle_size`'s ungated `event_pos` loop rather than `compute_smt_block_size`'s gated one.

---

### `cisd_barriers.py` — `compute_session` (compute, CRUD/aggregate, TF-scoped population)

**Analog:** `compute_smt_cisd` (`cisd_barriers.py:360-403`) for the plain flat 3-way tag dict shape:
```python
stats = {
    ct: {
        "w/ SMT":            {"total": 0, "runs": 0},
        "expired SMT":       {"total": 0, "runs": 0},
        "no SMT":            {"total": 0, "runs": 0},
        ...
    }
    for ct in ("bullish", "bearish")
}
...
for pos in event_pos:
    ct  = ct_arr[pos]
    tag = tag_arr[pos]
    if ct not in stats or tag not in stats[ct]:
        continue
    run = barrier_hit(df, pos, df.iloc[pos], ct)
    stats[ct][tag]["total"] += 1
    if run:
        stats[ct][tag]["runs"] += 1
```
`compute_session` swaps `swing_smt_tag` for `session_tag` and the 3-value vocabulary for `("rth_open", "rth", "overnight")`; every row has a `session_tag`, so there's no partial-match filter step (unlike `compute_smt_role`'s `if tag_arr[pos] != "w/ SMT": continue`, `cisd_barriers.py:432`, which is the closer analog *only if* a pre-filter step is needed — here it isn't). The TF-scoping itself (D-02, "only meaningful on 15min/1H") does **not** belong inside `compute_session` — it belongs in the registry (`ANALYSIS_META.applies_to`) and the two dispatch loops (`build_validation.py` TF loop, `cisd_charts.py` figure builders), per D-14's explicit guidance. `compute_session(df)` itself stays TF-agnostic and simply returns whatever the frame's `session_tag` column contains (Claude's Discretion fallback path could still guard here, but the "Preferred" path pushes scoping to the registry).

---

### `cisd_barriers.py` — `compute_effort_result`, `compute_rvol` (compute, CRUD/aggregate)

**Analog:** `compute_volume` (`cisd_barriers.py:247-277`) — the sibling analysis these features sit beside, untouched (D-10):
```python
def compute_volume(df: pd.DataFrame) -> dict:
    prev_vol = df["volume"].shift(1)
    BINS = [
        (0,    1.0,  "<1x (lower vol)"),
        (1.0,  1.5,  "1x-1.5x"),
        (1.5,  2.5,  "1.5x-2.5x"),
        (2.5,  1e18, ">2.5x (spike)"),
    ]
    ...
```
`compute_effort_result` and `compute_rvol`/`compute_volume_zscore` follow the exact same fixed-bin-over-a-precomputed-ratio-column shape, sourcing from the new `effort_result` / `rvol` / `volume_zscore` annotation columns instead of a `shift(1)` ratio computed inline. Bin thresholds are Claude's Discretion (shape-informed once, outcome-blind, D-04). Decide during planning whether RVOL and z-score are one analysis with two splits or two analyses (explicit Claude's-Discretion note in CONTEXT.md).

---

### `cisd_barriers.py` — registry wiring (config/registry) + D-14's `applies_to` field

**Analog:** existing `smt_role`/`smt_block_size` rows (`cisd_barriers.py:826-829`, `868-871`) and the `_AnalysisMeta` `NamedTuple` itself:
```python
class _AnalysisMeta(NamedTuple):
    """Metadata record for a single analysis key."""
    per_tf_height:    int
    standalone:       bool
    standalone_height: int | None
    filename:         str | None
```
D-14's preferred mechanism extends this tuple with one more field, e.g. `applies_to: tuple[str, ...] | None` (default `None` = "all timeframes", matching every existing key's implicit universality — no need to backfill all 19 existing rows with an explicit `("Daily","4H","1H","15min")` tuple):
```python
class _AnalysisMeta(NamedTuple):
    per_tf_height:    int
    standalone:       bool
    standalone_height: int | None
    filename:         str | None
    applies_to:       tuple[str, ...] | None = None   # None = all timeframes
```
Then `"session"` gets `applies_to=("1H", "15min")` and every existing row is unaffected (trailing default keeps old call sites valid). New `ANALYSES`/`ANALYSIS_META` sibling lines follow the exact two-dict pattern already used for `smt_role`/`smt_block_size`/`smt_in_block` (`cisd_barriers.py:826-829`, `868-871`) — this is the single registration point per CLAUDE.md's "Adding a New Analysis," confirmed still true after Phase 9.

---

### `cisd_charts.py` — new chart functions

**Analog for magnitude (4-bin ATR)**: `chart_candle_size` (`cisd_charts.py:204-218`) — flat 4-bucket, no alpha tiering — copy for `chart_wick_distance` with the signed bin labels. `chart_smt_block_size` (`:274-...`) is the alpha-tiered 4-bin variant if the planner wants dimming on the extreme bins — either is a valid literal copy target.

**Analog for tag/role charts (2-3 way)**: `chart_smt_role` (`cisd_charts.py:259-271`) for `chart_effort_result`/binary splits:
```python
def chart_smt_role(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in (("swept", 1.0), ("failed_to_sweep", 0.6)):
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]), COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55)
            for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Swing SMT Role (Swept vs Failed-to-Sweep)")
```
`chart_session` uses `chart_smt_cisd`'s exact three-way alpha pattern (`cisd_charts.py:241-256`: `(("w/ SMT", 1.0), ("expired SMT", 0.75), ("no SMT", 0.45))`) with `(("rth_open", 1.0), ("rth", 0.75), ("overnight", 0.45))`.

**Analog for TF-scoping in the figure dispatch (D-14)**: `build_figure` (`cisd_charts.py:524-582`) and `build_standalone_figure` (`:585-...`) both already read `ANALYSIS_META[k]` per key (`:539`, `:598-599`) — add an early `if tf_label not in (meta.applies_to or TF_TUPLE): continue/skip axis` guard right where `meta` is already fetched, no new lookup pattern needed. `build_standalone_figure`'s 2×2-all-TF loop (`:613-620`) needs the same guard per subplot (`i, tf_label in enumerate(tf_labels)`), turning off-scope subplots invisible the same way `build_figure` already does for unused trailing axes (`:567-568`: `axes_flat[j].set_visible(False)`).

---

### `scripts/build_validation.py` — TF-scoping in `main()` (D-14, the one new mechanism)

**Analog:** the two `for tf_label, tf_rule in TIMEFRAMES.items():` loops (`scripts/build_validation.py:637`, `:677`) that currently pass the same `all_keys = list(ANALYSES.keys())` (`:635`, `:673`) to every timeframe unconditionally:
```python
all_keys = list(ANALYSES.keys())
for tf_label, tf_rule in TIMEFRAMES.items():
    df_nq, df_es = prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], tf_rule, with_swing_smt=with_smt)
    ...
    manifest_rows.extend(
        build_manifest_rows(all_keys, nq_sl, es_sl, tf_label, slice_label)
    )
```
Change to scope `all_keys` per `tf_label` using `ANALYSIS_META`:
```python
tf_keys = [k for k in all_keys
           if (ANALYSIS_META[k].applies_to is None) or (tf_label in ANALYSIS_META[k].applies_to)]
manifest_rows.extend(
    build_manifest_rows(tf_keys, nq_sl, es_sl, tf_label, slice_label)
)
```
Apply identically at the walk-forward site (`:635-639`). This is the only functional change `build_validation.py` needs — `build_manifest_rows`' generic dispatch branch (`:299-304`) requires **zero** changes as long as every new `compute_*` stays flat `{dir: {tag: {total, runs}}}`.

---

### `README.md` new subsection (doc, transform)

**Analog:** Phase 9's SMT-invalidation-honesty README subsection (structure: badge-vocabulary prose immediately followed by a script-generated table, hand-written interpretive prose below) and Phase 7's "Post-CISD Context — Corrected Re-Validation (v2.0)" section (`README.md:400-420`). Reuse the ✓ CONFIRMED / ✗ NOT CONFIRMED / below-n badge vocabulary verbatim (D-11's mandatory caveats — OHLCV-only limitation, slot-normalization imperfection — are new prose, not a new format). D-13's "moved q-value ≠ bug" note is new prose analogous in tone to the "one global BH family" docstring in `apply_bh_correction` (`scripts/build_validation.py:309-315`) — quote/paraphrase that docstring rather than inventing new wording.

## Shared Patterns

### ATR(14) normalization
**Source:** `cisd_barriers.py:285` — `atr = (df["high"] - df["low"]).rolling(14).mean()`
**Apply to:** `wick_distance_atr`, `sweep_depth_atr`, `fvg_size_atr` (D-04). Compute once per magnitude function (or once in `_annotate_cisd_research` and thread the column through) — do not invent a true-range variant.

### Fixed-ATR-multiple bucket-threshold convention
**Source:** `cisd_barriers.py:283-288` (`compute_candle_size` BINS), `:454-459` (`compute_smt_block_size` BINS, identical) — `<0.5x / 0.5-1x / 1-1.5x / >1.5x ATR`
**Apply to:** all magnitude compute functions except `wick_distance_atr` (which needs a signed variant with an edge at 0, D-06).

### ATR-gated "skip if NaN" population restriction
**Source:** `cisd_barriers.py:465-468` (`compute_smt_block_size`'s `if pd.isna(ratio): continue`)
**Apply to:** `compute_sweep_depth`, `compute_fvg_size` — the annotation leaves the column `np.nan` off-population (D-05); the compute function trusts that and skips, never re-checking the boolean flag column directly.

### Vectorized annotation, no per-bar Python loops
**Source:** `cisd_data.py:182-...` (`_annotate_cisd_research`) — masks, `np.select`, `.rolling()`, `.shift()`
**Apply to:** every new annotation column in this phase (D-06a explicitly calls this out — "computed vectorized in the Phase-8 style, no re-introduced per-row Python loop"). Session tag, wick distance, sweep depth/level, FVG size/width, effort-vs-result, and RVOL/z-score inputs all follow this discipline; RVOL's slot-grouped rolling baseline is the one genuinely new idiom (`groupby(slot_key).rolling(K)` or pivot/rolling/unstack), not a literal copy of an existing block.

### Nested-dict compute shape `{direction: {tag: {"total": int, "runs": int}}}`
**Source:** every `compute_*` in `cisd_barriers.py` except `fvg_hold` (`"held"` key) and `cisd_fvg_interaction`/`combined` (extra nesting level)
**Apply to:** all seven-ish new compute functions this phase adds — must stay flat two-level (or the established mid0/mid1-style one extra level, per `compute_cisd_fvg`) so they hit `build_manifest_rows`'s generic `else` branch (`scripts/build_validation.py:299-304`) with zero harness changes. If any new analysis needs a genuinely new shape (e.g. `fvg_size` split by mid0/mid1), a new `elif key == "..."` branch must be hand-added to `build_manifest_rows`, following the `fvg_hold`/`cisd_fvg_interaction` precedent (`:284-297`) rather than forcing a flat shape that loses information.

### Registry-driven wiring (single edit point)
**Source:** `cisd_barriers.py:817-879` (`ANALYSES` + `ANALYSIS_META`)
**Apply to:** every new analysis this phase adds — one line in each dict is the *only* registration point (per the dict's own docstring at `:840-847`); no other file needs editing for wiring beyond the D-14 TF-scoping consumers below.

### D-14 TF-scoping consumers (the one new mechanism)
**Source:** `ANALYSIS_META[key]` lookups already present at `cisd_charts.py:539`, `:598-599` and the `all_keys` construction in `scripts/build_validation.py:635`, `:673`
**Apply to:** add `applies_to` to `_AnalysisMeta`, default `None` (= all timeframes, zero impact on existing 19 rows), then guard three call sites: `build_figure`'s per-key subplot loop, `build_standalone_figure`'s per-TF subplot loop, and `build_validation.py`'s two `all_keys`-per-`tf_label` sites. `compute_session` itself stays TF-agnostic per the "Preferred" mechanism in D-14.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| RVOL/z-score slot-grouped rolling baseline (`cisd_data.py`, new annotation logic) | transform / enrichment | event-driven (vectorized, but grouped) | No existing column in the codebase groups by time-of-day slot before applying a rolling window — every existing rolling op (`ATR`, sweep-swing lookback, FVG-hold lookahead) is a plain trailing window over the full series. Needs a fresh (still-vectorized) idiom: `groupby(minute_of_day)[...].rolling(K)` or an equivalent pivot/rolling/unstack round trip. Flag explicitly to the planner as the one place a literal "copy this block" instruction won't suffice. |
| Session hour/minute-of-day slicing (`cisd_data.py`, new annotation logic) | transform / enrichment | event-driven (vectorized) | No prior temporal-conditioning column exists (D-01's own text: "the engine's first temporal conditioning dimension"). The `np.select`-on-array style is a direct copy of `cisd_type`'s pattern, but the underlying minute-of-day arithmetic itself is new — low risk, but worth flagging as net-new logic rather than a literal excerpt. |

## Metadata

**Analog search scope:** `cisd_data.py`, `cisd_barriers.py`, `cisd_charts.py`, `scripts/build_validation.py`, `README.md`, `.planning/phases/09-smt-geometry-invalidation-honesty/09-PATTERNS.md`
**Files scanned:** 5 source modules + 1 prior-phase pattern map
**Pattern extraction date:** 2026-07-12
