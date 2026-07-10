# Phase 5: New CISD Research on the Validated Engine - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase ships **two new post-CISD barrier studies** on the refactored `cisd_data` / `cisd_barriers` / `cisd_charts` engine, each reported through the validation harness (n + Wilson CI, IS/OOS) **from the start** — no in-sample-only findings are ever produced. It delivers:

1. **05-01 `candle[1]` follow-through (RES-01):** Does the bar after a CISD (`candle[1]`) predict continuation? Buckets CISD events by `candle[1]`'s close behaviour and measures the `candle[0]` target-before-stop barrier outcome.
2. **05-02 multi-bar post-CISD context (RES-02):** A single `post_cisd_context` analysis keyed on a failed `candle[1]` plus the gap direction on `candle[2]` (the `candle2_gap_context` / `post_cisd_reversal_context` regime).

Both studies wire into `build_validation.py`'s `build_manifest_rows()` so every reported bucket carries n, Wilson CI, the `n≥50` gate flag, and a discovery/OOS slice label (RES-03).

**Candle indexing convention (relative to the CISD event):** `candle[-1]` = bar before the CISD (the `prev_*` columns) → `candle[0]` = the CISD bar itself (where `cisd_type` fires) → `candle[1]` = bar after → `candle[2]` = two bars after.

**Explicitly NOT in this phase:** the `post_cisd_ml` model (v2, ML-01), multiple-comparisons correction (v2, MHT-01), walk-forward validation (v2, WF-01), new instruments, live signalling.

</domain>

<decisions>
## Implementation Decisions

### Success metric & barrier anchoring (RES-01)
- **D-01:** Success metric = the existing **barrier-hit** (target-before-stop), with **target/stop = `candle[0]`'s high/low** (the CISD's own extremes). The R-unit is identical to the existing engine, so RES-01 hit-rates stay loosely comparable to the published README numbers. Not a directional-close metric.
- **D-02:** RES-01 reports the barrier outcome in **both windows, side by side, per bucket**:
  - **In-window** — reuse `barrier_hit` exactly as the 14 current analyses do: evaluate `candle[0]`'s target/stop over `candle[1]`+`candle[2]`, bucketed by `candle[1]`'s close. Directly comparable to the README, but **partly mechanical** (the conditioning bar `candle[1]` sits inside the measured window → a strong `candle[1]` inflates the hit by construction — a near-tautology).
  - **Re-anchored forward** — decision point is `candle[1]`'s close; then evaluate `candle[0]`'s target/stop over **`candle[2]`+`candle[3]`** (`LOOKAHEAD=2` from the decision point). Leakage-free: the bar conditioned on is not inside the measured window. This is the honest "predict continuation" read.
  - Reporting both makes the tautology gap visible. The bucket tags must encode which window the row is for (e.g. an `inwindow` / `forward` suffix); the `{dir: {tag: {total, runs}}}` shape is preserved.

### `candle[1]` bucket definitions (RES-01)
- **D-03:** **3-way core buckets per direction:** (a) `candle[1]` closes **against** the CISD; (b) `candle[1]` closes **with** the CISD but **within** `candle[0]`'s wick (close does not clear `candle[0]`'s high/low); (c) `candle[1]` closes **with** the CISD and **past** `candle[0]`'s wick (close clears `candle[0]`'s high for bullish / low for bearish). This is the exact forward-analog of the existing `compute_wick` split (which compares `candle[0]`'s close to `candle[-1]`'s high/low), moved one bar forward.
- **D-04:** **Two wick readings, both tested.** The user was unsure which "beyond the wick" meaning was intended, so capture both:
  - Reading A (the 3-way core, D-03): `candle[1]` closes past `candle[0]`'s wick.
  - Reading B (added cut): `candle[2]` closes **beyond `candle[1]`'s wick** (a later bar clearing `candle[1]`'s range on a closing basis), reported as a **separate added cut**, not multiplied into the core (avoids a bucket explosion that the `n≥50` gate would suppress).
  - **Reading B overlaps RES-02's multi-bar territory** — the planner may home the `candle[2]`-beyond-`candle[1]` cut inside RES-02 instead of duplicating it in RES-01. Either placement is acceptable; do not double-count it.

### RES-02 regime structure (RES-02)
- **D-05:** **One analysis** (`post_cisd_context`), not two. `post_cisd_reversal_context` is the **bucket** of `candle2_gap_context` where `candle[1]` failed AND `candle[2]` gapped against the CISD — not a separate analysis. One `compute_`/`chart_`/registry entry and one harness branch (matches roadmap plan 05-02 being a single plan).
- **D-06:** **Bucket structure:** precondition = `candle[1]` **fails to close beyond `candle[0]`'s extreme** (weak follow-through), then bucket by **`candle[2]` gap direction**: gap-with-CISD / gap-against-CISD / flat. The **reversal context** = failed `candle[1]` + gap-against. Because the conditioning runs through `candle[2]`, RES-02 is **inherently re-anchored forward** — continuation is measured *after* `candle[2]` (no in-window comparable variant; the window would be fully consumed by the conditioning bars).
- **D-07:** **Gap definition = signed `candle[2].open − candle[1].close`.** Sign gives gap-with / gap-against / flat. This is the only definition that captures anything on continuously-traded, 1-minute-resampled futures: it is non-trivial across the **Daily / weekend session boundary** and collapses to ~flat intraday (4H/1H/15min) — which the data will show honestly. A strict non-overlapping gap (`candle[2].low > candle[1].high`) was rejected as near-empty by construction.
- **D-08:** **Run RES-02 on all 4 timeframes** (Daily/4H/1H/15min) like every other analysis — no special-casing. The harness already iterates all TFs; the `n≥50` gate plus the data show intraday gap buckets collapse to ~flat, and the Daily (and possibly 4H) buckets are where any real signal surfaces.

### Harness reporting (RES-03 — locked, carried forward)
- **D-09:** Both studies report through `build_validation.py` from the start: Wilson CI, `n≥50` gate (below-n flagged but **kept visible, never dropped**), discovery/OOS slice via `OOS_START="2024-04-30"`. No new in-sample-only finding is published. (Phase 2/3 decisions, not re-litigated.)

### Claude's Discretion
- **RES-02 outcome metric** (user said "you decide"): **continuation hit-rate only** for the first pass (harness-native, one `{total,runs}` per bucket, consistent with RES-01 and all 14 existing analyses; the conditioned sub-buckets are already fighting the `n≥50` gate). A depressed continuation rate in the reversal-context bucket *is* the finding. The **explicit reversal barrier** (measuring whether `candle[0]`'s opposite extreme is hit first) is recorded as an **optional extension** the planner may add later if the continuation-complement proves interesting — deliberately not in the first pass.
- Neutral / doji `candle[1]` handling (a flat close): fold into the "against" bucket or track separately — implementer's call; flat closes are rare on continuous data. Be consistent with how the existing `direction` column treats `"neutral"`.
- Whether the new analyses are **standalone** (own all-TF PNG via `ANALYSIS_META.standalone=True`) or per-TF only — default to standalone, consistent with the other research analyses (`sweep`, `sssf_swing`, etc.), but the planner may decide.
- Exact bucket-tag strings, the `build_manifest_rows` branch shape (generic `{dir:{tag:{total,runs}}}` vs a custom branch), `ANALYSIS_META` heights/filenames, and new annotation column names — implementer's call following the Phase 4 conventions.
- Where the `candle[2]`-beyond-`candle[1]` cut lives (RES-01 added cut vs inside RES-02) — planner decides; do not double-count.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & locked decisions
- `.planning/ROADMAP.md` §"Phase 5: New CISD Research on the Validated Engine" — goal, 4 success criteria, the two plan splits (05-01 `candle[1]` follow-through, 05-02 multi-bar post-CISD context).
- `.planning/REQUIREMENTS.md` §"New Research" — RES-01, RES-02, RES-03 exact wording (the acceptance bar).
- `.planning/PROJECT.md` §"Key Decisions" + §"Active" — sacred holdout, behavior-preserving / additive style, foundational depth (CIs + n-gating only), the `candle[1]` follow-through and multi-bar post-CISD context backlog items this phase implements.

### The research questions being implemented
- `docs/research_backlog.md` §"CISD Follow-Through on `candle[1]`" and §"Multi-Bar Post-CISD Context" — the source hypotheses for RES-01 (`candle[1]` close direction / past-wick → continuation) and RES-02 (`candle2_gap_context`, `post_cisd_reversal_context`). Move graduated findings into README and trim these entries when done.

### Add-an-analysis recipe & the engine to extend
- `cisd_barriers.py` — `barrier_hit` (the locked first-touch target/stop), the 14 `compute_*` functions (all return nested `{dir: {tag: {total, runs}}}`; `compute_wick` is the closest analog for RES-01's wick split, `compute_sweep`/`compute_sssf_swing` for the simple `{dir:{tag:{total,runs}}}` shape), the `ANALYSES` registry, and the `ANALYSIS_META` single-source-of-truth registry (`_AnalysisMeta` NamedTuple: `per_tf_height`, `standalone`, `standalone_height`, `filename`). **Adding a standalone analysis edits only `ANALYSES` + `ANALYSIS_META`.**
- `cisd_data.py` — `prepare()` → `_annotate_cisd_research()` is where new precomputed boolean/categorical columns belong (e.g. `candle1_close_dir`, `candle1_past_candle0_wick`, `candle2_gap_dir`, `candle1_failed_followthrough`). Follow the bulk-accumulate-then-assign pattern already used there. Compute functions consume precomputed columns only — they do not rediscover events. `CLAUDE.md` "Adding a New Analysis" section documents the recipe.
- `cisd_analysis.py` — the re-export shim; new public symbols must stay importable through it (scripts/tests import from `cisd_analysis`).

### Harness wiring (RES-03 — report from the start)
- `scripts/build_validation.py` — `build_manifest_rows()` has a per-key dispatch block; new analyses need a branch here (or fall into the generic `else` branch if their shape is `{dir: {tag: {total, runs}}}`). `wilson_ci()`, `n_gate()`, `slice_df()`, `OOS_START`/`MIN_N`/`CI_LEVEL`, and the `--oos` sacred path are all reusable as-is. Tidy-long manifest columns: `analysis, timeframe, instrument, direction, bucket, rate, n, successes, ci_low, ci_high, ci_method, min_n_pass, slice`.
- `scripts/build_discovery_summary.py` and `scripts/build_reconcile_findings.py` — the discovery-summary + IS/OOS reconciler from Phase 3; check whether new analyses need to be threaded through these for the honest publish step.

### Prior phase context
- `.planning/phases/02-validation-harness/02-CONTEXT.md` — D-07 (Wilson CI, pure stdlib), D-08 (`n≥50`), D-09 (below-n visible), D-10 (manifest schema), D-12 (additive / behavior-preserving).
- `.planning/phases/04-test-gated-modular-refactor/04-CONTEXT.md` — the module split, re-export shim, `ANALYSIS_META` registry, and vectorization (`np.flatnonzero`) pattern new compute functions should follow.

### Tests that must stay green (behavior-preservation gate)
- `tests/test_characterization.py`, `tests/test_core_compute.py`, `tests/test_research_extensions.py`, `tests/test_validation_harness.py` — new analyses are **additive**; existing locked numbers must not move. New unit tests for the two studies should follow `tests/test_research_extensions.py`'s style.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`cisd_barriers.py:barrier_hit(df, idx, row, ct)`** — the locked first-touch barrier. RES-01's in-window variant calls it unchanged at `candle[0]`'s position. The re-anchored variant needs the same target/stop levels (`candle[0]` high/low) but the lookahead loop must start at `candle[2]` (idx+2) — likely a small variant/parameterization rather than a rewrite.
- **`cisd_barriers.py:compute_wick`** — the canonical "within_wick / past_wick" split (compares `candle[0]` close to `candle[-1]` high/low). RES-01's wick logic is the same idea one bar forward (`candle[1]` close vs `candle[0]` high/low) — mirror its `np.flatnonzero` + array-indexing structure.
- **`cisd_barriers.py:compute_sweep` / `compute_sssf_swing`** — minimal `{dir: {tag: {total, runs}}}` shape that drops straight into the harness's generic `else` branch; the closest templates for the new compute functions.
- **`cisd_data.py:_annotate_cisd_research`** — already accumulates per-event boolean/categorical lists and bulk-assigns them as columns; add the new `candle[1]`/`candle[2]` feature columns here using the same pattern.
- **`scripts/build_validation.py:build_manifest_rows` / `wilson_ci` / `n_gate` / `slice_df`** — the full harness; new analyses report through it by adding a key to `ANALYSES` (auto-iterated via `list(ANALYSES.keys())`) plus a dispatch branch.

### Established Patterns
- **Additive / behavior-preserving:** prior phases never moved a published number or removed a public symbol. These two analyses are pure additions — characterization tests must stay green. New columns/keys only.
- **Precompute-in-`prepare`, consume-in-`compute`:** all event features are annotated once in `_annotate_cisd_research`; `compute_*` reads precomputed columns and never rediscovers events. The new `candle[1]`/`candle[2]` features follow this.
- **Vectorized hot loops:** Phase 4 vectorized all `compute_*` to the `np.flatnonzero(mask)` + NumPy array-indexing pattern. New compute functions should be written in that style from the start.
- **Harness-native bucket shape:** keep outputs as `{dir: {tag: {total, runs}}}` so they slot into the generic harness branch and the discovery/OOS manifest with no special-casing.

### Integration Points
- **New annotation columns** → `cisd_data.py:_annotate_cisd_research` (and the `prepare` pipeline).
- **New compute + chart functions** → `cisd_barriers.py` (compute, `ANALYSES`, `ANALYSIS_META`) + `cisd_charts.py` (chart). Re-export through `cisd_analysis.py` if any new public symbol must be importable by scripts/tests.
- **Harness** → a `build_manifest_rows` branch (or generic fallback) in `scripts/build_validation.py`; then the new analyses appear automatically in the discovery and `--oos` manifests.
- **Publish** → discovery run → human review (`build_discovery_summary.py`) → single sacred `--oos` → reconcile (`build_reconcile_findings.py`) → README. New findings follow the same honest-publish flow as Phase 3.

</code_context>

<specifics>
## Specific Ideas

- The **tautology insight** is the methodological spine of RES-01: conditioning on `candle[1]`'s close while `candle[1]` is inside the barrier window inflates the in-window hit rate mechanically. Reporting in-window AND re-anchored side by side is deliberately chosen so the gap between them is visible and the honest (re-anchored) number is never mistaken for the comparable (in-window) one.
- RES-01's re-anchored variant keeps `candle[0]`'s target/stop levels (not `candle[1]`'s) so a "hit" means the same thing as everywhere else in the engine — only the lookahead clock moves to start at `candle[2]`.
- RES-02's gap dimension is expected to be **Daily-dominant**; intraday gap-with/gap-against buckets will be near-empty. This is acceptable and honest — the `n≥50` gate marks them below-n and they stay visible, never silently dropped.
- Bucket-tag naming should make the anchor explicit for RES-01 (e.g. `with_past_wick_inwindow` vs `with_past_wick_forward`) so the manifest is self-describing.

</specifics>

<deferred>
## Deferred Ideas

- **`post_cisd_ml`** — a small ML model over post-CISD context features (RES-02's failed-`candle[1]` + gap tags as inputs). Explicitly v2 (ML-01); validate the discrete tags first.
- **Explicit reversal barrier for RES-02** — measuring whether `candle[0]`'s opposite extreme is hit first (not just a depressed continuation rate). Recorded as an optional extension; not in the first pass (D-07 discretion).
- **Multiple-comparisons / data-snooping correction** (MHT-01) — adding RES-01/02 grows the bucket grid; correction is still the next rigor tier (v2), not this phase.
- **Walk-forward / rolling-window validation** (WF-01) — v2.

None of the above stalls planning — they are intentional boundaries.

</deferred>

---

*Phase: 5-New CISD Research on the Validated Engine*
*Context gathered: 2026-06-14*
