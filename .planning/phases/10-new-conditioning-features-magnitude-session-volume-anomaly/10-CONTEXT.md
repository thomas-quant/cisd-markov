# Phase 10: New Conditioning Features — Magnitude, Session & Volume Anomaly - Context

**Gathered:** 2026-07-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Three economically-motivated conditioning-feature families are added on top of the existing binary flags and each is pushed through the existing corrected validation harness (n + Wilson CI + BH-FDR + walk-forward), giving Phase 11's model better inputs than the current binaries. For RES-07 this phase adds:

1. **Magnitude** — continuous, ATR-normalized versions of existing binary flags: distance-past-previous-wick, sweep penetration depth, and FVG size (SC1).
2. **Session / time-of-day** — the engine's first temporal conditioning dimension, from the ET index (SC2).
3. **Volume anomaly** — measures beyond the already-negligible 1-bar volume ratio: slot-normalized rolling RVOL / z-score and effort-vs-result (SC3).

Every new bucket carries n, Wilson CI, the BH-FDR-corrected verdict, and a walk-forward robustness verdict; features that don't clear the bar are published as not-confirmed / below-n, never dropped (SC4).

**In scope:** new annotation columns in `cisd_data.py`, new standalone `compute_*` / `chart_*` analyses in `cisd_barriers.py` / `cisd_charts.py`, their registry wiring, their flow through the generic `build_validation.py` manifest dispatch, and the README methodology writeup. A small amount of new plumbing to scope the session analysis to intraday timeframes (see D-14).

**Explicitly out of scope:** cross-asset NQ↔ES volume divergence (deferred — see D-09); ICT kill-zone session taxonomy (rejected in favor of the 3-bucket RTH split — see D-01 / Deferred); any modification to the existing binary analyses' published rates (additive-only — D-12); signed/delta order-flow volume (impossible on OHLCV — D-11); any model (Phase 11, ML-01); re-validating the other analyses under a changed methodology (their base rates stay byte-stable — D-12).

</domain>

<decisions>
## Implementation Decisions

### Session / time-of-day family (SC2)

- **D-01 (taxonomy — the robust 3-way split):** The session tag is a **pure 3-bucket** split: `rth_open` (09:30–10:30 ET), `rth` (10:30–16:00 ET), `overnight` (16:00–09:30 ET, next day). Chosen deliberately over ICT kill zones: every bucket added is another hypothesis in the *global* BH-FDR family (D-13) and another cell that must survive multiple walk-forward folds, so the fewest, highest-n buckets give the phase the best odds of a feature that actually **clears** the corrected bar and can feed the Phase 11 model. Kill zones were rejected (see Deferred).
- **D-02 (timeframe scope — intraday only):** The session analysis is registered on **15min and 1H only**. A session tag on a Daily or 4H bar is economically meaningless (the bar spans multiple sessions), and populated-but-meaningless Daily/4H session rows would only add below-n cells that dilute the global FDR correction. It is **not** registered on 4H or Daily.
- **D-02a (open window):** `rth_open` = the first **60 min** (09:30–10:30 ET) — captures the full opening-drive / initial-balance window and gives healthier n (4 bars on 15min) than a 30-min definition.
- **D-03 (frozen boundaries — no back-door snooping):** All session boundaries live in **one documented constant block and are frozen**. Boundaries are **never** nudged to improve a rate — that would be silent multiple-comparisons through the back door and would violate the milestone honesty invariant. The `DateTime_ET` index is tz-naive ET wall-clock (verified: `datetime64[ns]`, no tz, all 24 hours present, 2020-08-31→2025-11-21), so session assignment is a clean hour/minute-of-day slice with **no timezone conversion or DST math** required.

### Magnitude family (SC1)

- **D-04 (fixed ATR-multiple bins, not quantile):** Continuous magnitudes are bucketed with **fixed ATR-multiple bins**, reusing `compute_candle_size`'s frozen convention and its ATR(14) = `(df["high"] − df["low"]).rolling(14).mean()`. Fixed bins mean a bucket denotes the **same magnitude range** in the discovery slice, the sacred OOS slice, and every walk-forward fold — the comparability the harness depends on. Quantile bins were rejected: their boundaries are recomputed per slice (so a label means different magnitudes across the holdout) or leak OOS into the feature definition. Bin cut points may be **shape-informed once from the discovery-slice histogram** (discovery is fair game) — but chosen **outcome-blind** (never tuned to hit rates, never peeking at OOS) and then frozen.
- **D-05 (per-feature natural population):** Each magnitude is defined exactly where it is meaningful — uniformity would destroy information:
  - `wick_distance_atr` — **signed-continuous over ALL CISDs**: bullish `(close − prev_high)/ATR`, bearish `(prev_low − close)/ATR`. Negative = closed within the prior wick, positive = past it. This single feature subsumes and enriches the binary `compute_wick` past/within split (keeps the within-wick half).
  - `sweep_depth_atr` — defined **only where `has_dir_sweep`** (how far the CISD bar's extreme pierced the swept swing level, /ATR). A depth with no sweep is undefined; 0 would falsely conflate "no sweep" with "barely swept".
  - `fvg_size_atr` — defined **only where `has_dir_fvg`** (mid0/mid1) — the gap width, /ATR.
- **D-06 (edge at zero for the signed feature):** `wick_distance_atr`'s bins must place a **bin edge exactly at 0**, so the existing past-vs-within-wick rate stays recoverable and cross-checkable against `compute_wick`.
- **D-06a (annotation must carry real levels — new scope for the planner):** Sweep depth and FVG size **cannot reuse the existing flags** — the current annotation stores only booleans (`has_dir_sweep`, `has_dir_fvg_mid0/1`), not the pierced swing **level** or the gap **width**. The annotation must additionally carry the actual pierced level and the actual gap size, computed **vectorized** in the Phase-8 style (no re-introduced per-row Python loop). `wick_distance_atr` is free — `prev_high`/`prev_low`/`close` already exist.

### Volume-anomaly family (SC3)

- **D-07 (effort-vs-result — the baseline-free anchor):** `effort-vs-result` (within-bar `volume ÷ range`, and/or `÷ body`) is the cleanest measure — a within-bar ratio with **no baseline, no lookback window, and no intraday seasonality**. High-volume-goes-nowhere (churn/absorption) vs low-volume-travels (efficient delivery) is exactly the conditioning signal, immune to time-of-day. In, high confidence.
- **D-08 (rolling RVOL / z-score — same-time-of-day-slot baseline):** RVOL and z-score use a **same-time-of-day-slot** baseline (the conventional "relative volume" definition), **not** a naive trailing window: `rvol = vol / mean(same clock slot, last K)`, `zscore = (vol − slot_mean) / slot_std`. Intraday volume has a large time-of-day profile; a naive trailing baseline would partly measure *what hour it is* rather than a true anomaly. The slot baseline removes the profile **including inside the overnight window** (which a coarse session-bucket baseline would not — Asia/London/pre-market differ wildly). On Daily there is one slot, so it degenerates to a plain trailing baseline (correct — no intraday profile there). `K` is a **frozen constant (~20 slot occurrences ≈ 20 trading days)**, never tuned; a warm-up period where the baseline is undefined is tolerated (those bars fall below-n and are naturally excluded).
- **D-09 (cross-asset divergence — DEFERRED):** Cross-asset NQ↔ES volume divergence is **not built this phase**. SC3 marks it explicitly "optional"; it is the fiddliest (normalize each instrument to its own baseline, *then* difference — many researcher degrees of freedom), and every bucket it spawns raises the corrected bar on the features we do believe in. Revisit only if the core volume measures show a pulse (see Deferred).
- **D-10 (keep the negligible 1-bar ratio):** The existing `compute_volume` (1-bar CISD/prev ratio) **stays untouched**. SC3 wants the new measures *distinct from* it, not replacing it — and it is a behavior-locked published analysis (D-12).
- **D-11 (mandatory caveats):** The README/methodology writeup must state explicitly: (a) the **OHLCV-only limitation** — no signed/delta order flow is possible, so these are unsigned effort/anomaly proxies, not order-flow; (b) that slot-normalization neutralizes most but not necessarily all of the intraday profile.

### Registration & no-drift (SC4)

- **D-12 (additive standalone analyses — existing base rates byte-stable):** Each new feature is a **new standalone** `compute_*` + `chart_*` + `ANALYSES` + `ANALYSIS_META` entry + all-TF standalone figure (the Phase 9 pattern; CLAUDE.md "Adding a New Analysis"). The existing binary analyses (`compute_wick`, `compute_sweep`, `compute_cisd_fvg`, `compute_volume`) are **not modified**. Because `rate`/`n`/`successes`/`ci_low`/`ci_high`/`min_n_pass` are per-bucket and independent of the rest of the grid, existing published rates are **byte-stable** — protected by the golden characterization test, same discipline as Phase 9.
- **D-13 (moved q-values are correct, not drift):** Adding these features **will** shift the `bh_q_value` / `corrected_pass` of *existing* buckets, because `apply_bh_correction` builds **one global BH family** across every analysis × timeframe × instrument × direction × bucket in the discovery slice (`build_validation.py:309`, docstring "one global family … never grouped per-analysis-key"). This is not drift — it is exactly what MHT-01 is for (a corrected verdict should reflect how many hypotheses were tested). It is additive (the BH columns are the additive ones) and must be **documented so a moved q-value is not mistaken for a bug**.
- **D-14 (session TF-scoping — the one bit of new plumbing):** `compute_fn(df)` receives only the frame, not the TF label, so an intraday-only session analysis needs scoping support. **Preferred:** add a small `applies_to` / `timeframes` allow-list field to `ANALYSIS_META` and skip out-of-scope (analysis, TF) pairs in both the `build_validation.py` manifest loop and the `cisd_charts.py` figure dispatch (reusable, clean). **Fallback:** the session compute infers "am I intraday?" from the frame's median bar spacing and returns empty buckets otherwise. Everything else in the phase is pure Phase-9-pattern reuse; this is the only genuinely new mechanism.

### Claude's Discretion (planner / researcher call)
- Exact fixed bin cut points for each magnitude and volume feature — shape-informed once from the discovery-slice distribution, outcome-blind, then frozen (D-04). Reuse `compute_candle_size` / `compute_volume` bin styles where they fit; `wick_distance_atr` needs a signed bin set with an edge at 0 (D-06).
- Exact `K` for the RVOL slot baseline (~20 occurrences) and the exact slot key (clock `HH:MM` intraday; single slot on Daily).
- Whether RVOL and z-score are **one** analysis with two splits or **two** analyses; whether effort-vs-result uses `÷ range`, `÷ body`, or both.
- ATR anchoring for the magnitude normalization — ATR(14) at the CISD bar `t` (default, matches `compute_candle_size`) unless a per-feature anchor reads cleaner.
- Exact new column / bucket / analysis names — follow the existing lowercase-underscore + `{ct: {tag: {total, runs}}}` conventions.
- Chart layout and all-TF standalone figure wiring; how the new columns thread through `scripts/build_forward_returns.py` and `scripts/build_expectancy.py` filter families (they must degrade gracefully when a column is absent, as the SMT columns already do).
- Exact file/structure for the README methodology writeup — follow the Phase 7 / Phase 9 pattern (script-generated numbers, hand-written prose, ✓ CONFIRMED / ✗ NOT CONFIRMED / below-n badge vocabulary).
- The D-14 TF-scoping mechanism (ANALYSIS_META allow-list vs frequency inference) — planner's call following what's lowest-touch; lean allow-list.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` — Phase 10 goal + 4 success criteria; Phase 11's dependency on this phase's corrected feature evidence.
- `.planning/REQUIREMENTS.md` — RES-07 (the full phase requirement, incl. the "optional cross-asset divergence" wording D-09 relies on).
- `.planning/PROJECT.md` — Key Decisions table (sacred holdout, Wilson CI + min-n, "publish failures explicitly," "any published number that moves must be deliberate & documented," "give the model economically-motivated harness-validated inputs rather than let it mine noise").

### The corrected bar every new bucket must clear (SC4)
- `.planning/phases/06-harder-evidence-bar-multiple-comparisons-correction-walk-for/06-CONTEXT.md` — the BH-FDR + walk-forward + Wilson CI + per-fold min-n bar.
- `scripts/build_validation.py:129` (`bh_correct`), `:195` (`build_manifest_rows` — the generic `{ct:{tag:{total,runs}}}` dispatch that turns any new analysis into n/CI/FDR/WF rows with zero harness change), `:309` (`apply_bh_correction` — **one global BH family**, the basis of D-13), `:503`–`546` (walk-forward), `:613` (`main`), `:637`/`:677` (the per-TF × per-analysis loop D-14 must scope).

### Pattern to reuse (this phase = Phase 9 mechanics applied to new features)
- `.planning/phases/09-smt-geometry-invalidation-honesty/09-CONTEXT.md` — the "new feature = additive standalone analysis, inherits SC4 stats for free" pattern; its Claude's-Discretion structure and the forward-returns/expectancy graceful-degradation note.
- `.planning/phases/07-corrected-re-validation-of-the-post-cisd-studies/07-CONTEXT.md` — the README methodology-writeup pattern (D-11): new section, script-generated numbers, hand-written prose, badge vocabulary.

### Code this phase changes / reuses
- `cisd_data.py:81` (`prepare`) / `cisd_data.py:182` (`_annotate_cisd_research`) — where the new annotation columns (session tag, `wick_distance_atr`, `sweep_depth_atr` + pierced level, `fvg_size_atr` + gap width, RVOL/z-score/effort inputs) are computed, vectorized. `cisd_data.py:62` (`load_1m`) sets the tz-naive `DateTime_ET` index D-03 slices on. Sweep detection (~`:229`–`:279`) and FVG detection (~`:282`–`:303`) are where the boolean flags come from and where D-06a's level/width extraction attaches.
- `cisd_barriers.py:280` (`compute_candle_size`) — the ATR(14) definition and fixed-ATR-bin convention D-04 reuses. `cisd_barriers.py:247` (`compute_volume`), `:187` (`compute_wick`), `:644` (`compute_sweep`), `:513` (`compute_cisd_fvg`) — the existing binary analyses that stay **untouched** (D-10/D-12) and that the new magnitude/volume analyses sit beside. `cisd_barriers.py:817` (`ANALYSES`), `:857` (`ANALYSIS_META`) — where new analyses register and where D-14's TF allow-list would live.
- `cisd_charts.py` — `chart_*` helpers (`_bar_label`/`_style_ax`), `build_figure` (~`:526`), `build_standalone_figure` (~`:590`) — new charts + the figure dispatch D-14 must also TF-scope.
- `README.md` — the "Validation Methodology — Harder Evidence Bar (v2.0)" section and Key Findings badge vocabulary — home for the D-11 writeup.

No external ADRs/specs — the feature definitions are fully specified in the decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Generic validation dispatch** (`build_manifest_rows` "Generic" branch) already turns any `{ct: {tag: {total, runs}}}` compute output into n + Wilson CI + BH-FDR + walk-forward manifest rows — confirmed across Phases 6/7/9. Every new bucket in this phase inherits SC4's stats with **zero harness change**.
- **ATR(14)** = `(df["high"] − df["low"]).rolling(14).mean()` in `compute_candle_size` (`cisd_barriers.py:285`) — copy for all magnitude normalization; do not invent a true-range variant.
- **Fixed-bin idiom** — `compute_candle_size` (`<0.5×/0.5–1×/1–1.5×/>1.5× ATR`) and `compute_volume` (`<1×/1–1.5×/1.5–2.5×/>2.5×`) are the frozen-bin templates D-04 reuses.
- **Vectorized annotation** (Phase 8) — `_annotate_cisd_research` is fully vectorized (masks, `searchsorted`, rolling ops). D-06a's new level/width columns and the session/volume features must be added in the same vectorized style, not as re-introduced per-row loops.

### Established Patterns
- Compute functions return nested `{direction: {bucket: {total, runs}}}`; chart functions drive rows from a hardcoded tag/alpha list. New feature = new dict shape + chart tag list + `ANALYSES`/`ANALYSIS_META` entry + all-TF standalone figure (CLAUDE.md "Adding a New Analysis").
- Behavior-preservation invariant: additive output only; existing published base rates (`rate/n/successes/ci_low/ci_high/min_n_pass`) must be byte-stable, enforced by the golden characterization test (D-12). Non-confirming features published as ✗ NOT CONFIRMED / below-n, never dropped.
- README Key Findings use ✓ CONFIRMED / ✗ NOT CONFIRMED / below-n badges (Phase 7/9); D-11's writeup extends this vocabulary.

### Integration Points
- New annotation columns originate in `_annotate_cisd_research` (single-instrument `prepare`, so they populate on every path — no SMT dependency) → consumed by the new `compute_*` analyses → flow through `build_manifest_rows` (generic branch, no change) → BH-FDR + walk-forward → the D-11 README writeup. Volume features need only OHLCV (always present); the session feature needs only the index.
- `scripts/build_forward_returns.py` / `scripts/build_expectancy.py` filter families must tolerate the new columns being absent on paths that don't compute them (the existing SMT-absent graceful-degradation contract).
- **The one new mechanism** (D-14): `ANALYSIS_META` gains a per-analysis TF allow-list consumed by the `build_validation.py` manifest loop (`:637`/`:677`) and the `cisd_charts.py` figure dispatch, so the session analysis runs on 15min/1H only.

</code_context>

<specifics>
## Specific Ideas

- The `DateTime_ET` index is **tz-naive ET wall-clock** (verified: `datetime64[ns]`, `tz=None`, all 24 hours present, 2020-08-31 20:00 → 2025-11-21 16:59, 1.85M 1-min rows). Session assignment is therefore a plain hour/minute-of-day slice — **no tz conversion, no DST math**. Downstream agents should not add timezone handling.
- The BH-FDR family is **global** (one pass over all discovery rows with n≥1), so grid size is a real cost — the reason the phase held the line on parsimony (3-bucket session, deferred cross-asset). Roughly ~7 new analyses' worth of buckets join the family; the base rates of existing analyses stay fixed but their corrected verdicts legitimately shift (D-13).
- RVOL is the conventional same-time-of-day "relative volume," not a naive trailing ratio (D-08). Effort-vs-result is the seasonality-free anchor of the volume family (D-07).
- `wick_distance_atr` is signed so it subsumes the binary `compute_wick` split (D-05) — put a bin edge at 0 to keep the old rate recoverable (D-06).

</specifics>

<deferred>
## Deferred Ideas

- **ICT kill-zone session taxonomy** (Asia / London / NY-AM / NY-PM / lunch) — rejected in favor of the robust 3-bucket RTH split (D-01) to protect statistical power under the global FDR family and walk-forward folds. Revisit as a finer-grained follow-up only if the coarse `rth_open/rth/overnight` split shows a pulse worth resolving.
- **Cross-asset NQ↔ES volume divergence** (D-09) — SC3-optional; deferred to keep the FDR grid lean and avoid its normalize-then-difference degrees of freedom. Revisit only if the core volume measures (effort-vs-result, slot-RVOL/z-score) clear the bar.
- **Session features on Daily/4H** (D-02) — deliberately unregistered (a session tag on a multi-session bar is meaningless), not a future TODO.

</deferred>

---

*Phase: 10-New Conditioning Features — Magnitude, Session & Volume Anomaly*
*Context gathered: 2026-07-12*
