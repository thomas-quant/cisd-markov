# Roadmap: CISD-Markov Research Engine

## Milestones

- ✅ **v1.0 Validated Research Engine** — Phases 1–5, shipped 2026-07-10 ([archive](milestones/v1.0-ROADMAP.md)); closed with documented verification overrides.
- 🚧 **v2.0 Rigorous Validation & Post-CISD Modeling** — Phases 6–11 (planning)

## Overview

v2.0 raises the evidence bar the engine already enforces. v1.0 gave every rate a sample-size gate, a Wilson confidence interval, and a sacred discovery/OOS split. This milestone hardens that harness — a "confirmed" edge must now survive a multiple-comparisons correction across the full bucket grid (so it accounts for how many buckets were tested, not just its own single-bucket CI) and must re-confirm across multiple sequential walk-forward windows, not just one fixed holdout. With that harder bar in place, the two post-CISD studies from Phase 5 (`post_cisd_context` and `candle1_followthrough`) — never fully validated after they shipped — are re-run end-to-end under the corrected methodology, and the `failed_gap_against` bucket gains an explicit reversal barrier that measures whether `candle[0]`'s opposite extreme is hit first, not just a depressed continuation rate. Before that modeling decision, the engine's feature surface is widened on the same validated footing: first the enrichment and validation hot path is vectorized so the end-to-end regen is fast and every subsequent feature iterates cheaply (behavior-preserving — no published number moves); then the SMT study is deepened to carry the price/lifecycle geometry the scanner already returns (magnitude, CISD-in-block containment, role) while fixing a tagging-honesty bug around invalidated SMTs; and finally three new conditioning-feature families — continuous magnitudes of the existing binary flags, session/time-of-day, and CISD volume anomalies — are put through the same harness. That corrected, expanded evidence is then the strict gate for the final phase: a small model is built only over whichever feature families actually clear the bar — and "no model warranted" is an equally valid, successful outcome. The v1.0 behavior-preservation invariant carries throughout: existing published numbers must not silently move; new methodology is additive/parallel output and any change to how a prior finding is reported is deliberate and visible.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (6.1, 6.2): Urgent insertions (marked with INSERTED)

Phase numbering is continuous across milestones — v1.0 ended at Phase 5, so v2.0 begins at Phase 6.

<details>
<summary>✅ v1.0 Validated Research Engine (Phases 1–5) — SHIPPED 2026-07-10</summary>

Full phase details in [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).

- [x] **Phase 1: Reproducibility Foundation & Behavior Lock** — Pin the environment, run tests in CI deterministically, and lock current published numbers (completed 2026-06-12)
- [x] **Phase 2: Validation Harness** — Sacred date holdout, binomial confidence intervals, and sample-size gating (completed 2026-06-12)
- [x] **Phase 3: Re-Validate & Republish Existing Findings** — Re-run README headline results through the harness with n + CI + OOS status (completed 2026-06-14)
- [x] **Phase 4: Test-Gated Modular Refactor** — Split the god-file, consolidate the registry, vectorize hot loops (completed 2026-06-14)
- [x] **Phase 5: New CISD Research on the Validated Engine** — Add `candle[1]` follow-through and multi-bar post-CISD context studies (completed 2026-07-04)

</details>

### 🚧 v2.0 Rigorous Validation & Post-CISD Modeling (Planning)

**Milestone Goal:** Upgrade the validation harness with multiple-comparisons correction and walk-forward validation, re-validate the post-CISD studies under that harder bar, then — after vectorizing the hot path and widening the feature surface (SMT geometry, magnitude, session, and volume-anomaly features) on that same validated footing — use the corrected, expanded evidence to decide whether any feature family justifies a small model.

- [x] **Phase 6: Harder Evidence Bar — Multiple-Comparisons Correction & Walk-Forward Validation** - Extend the harness with FDR correction across the bucket grid and rolling walk-forward windows, as additive output that leaves existing numbers untouched (completed 2026-07-10)
- [x] **Phase 7: Corrected Re-Validation of the Post-CISD Studies** - Regenerate the manifest end-to-end under the corrected methodology for `post_cisd_context` / `candle1_followthrough`, add the `failed_gap_against` reversal barrier, and issue the go/no-go verdict for modeling (completed 2026-07-11)
- [x] **Phase 8: Performance — Vectorize the Enrichment & Validation Hot Path** - Vectorize the row-by-row annotation loops (SMT event tagging + CISD research annotation) and remove redundant re-computation so the end-to-end manifest regen is fast; strictly behavior-preserving — no published number moves (completed 2026-07-11)
- [x] **Phase 9: SMT Geometry & Invalidation Honesty** - Carry the SMT price/lifecycle fields the scanner already returns; fix the already-invalidated-SMT tagging bug; add SMT role, magnitude, and CISD-in-block containment features plus a survived-vs-broke-in-window split, all through the validation harness (completed 2026-07-12)
- [ ] **Phase 10: New Conditioning Features — Magnitude, Session & Volume Anomaly** - Add continuous magnitude versions of the binary flags, session/time-of-day tags, and CISD volume-anomaly measures; validate each through the harness
- [ ] **Phase 11: Conditional Post-CISD Model** - Gated on the corrected evidence from Phases 7/9/10, either build and validate a model over whichever feature families cleared the bar, or ship a documented "no model warranted" conclusion

## Phase Details

### Phase 6: Harder Evidence Bar — Multiple-Comparisons Correction & Walk-Forward Validation

**Goal**: The validation harness measures every edge against a harder, honest bar — a bucket's "confirmed" status accounts for how many buckets were tested (FDR control across the full grid), and its robustness is re-confirmed across multiple sequential walk-forward windows rather than a single fixed split. The new methodology is additive/parallel; existing published numbers do not move.
**Depends on**: Phase 5 (the validated, refactored engine and its existing `scripts/build_validation.py` harness)
**Requirements**: MHT-01, WF-01
**Success Criteria** (what must be TRUE):

  1. The validation manifest CSV carries a multiple-comparisons-corrected column (e.g. a Benjamini-Hochberg adjusted q-value plus a corrected pass/fail flag) computed across the full bucket grid, so a bucket's "confirmed" status reflects the number of buckets tested — not just its own single-bucket Wilson CI.
  2. Running the harness produces walk-forward output: each edge is evaluated across multiple sequential train→test windows, and the manifest/summary records per-window pass/fail plus an aggregate walk-forward robustness verdict.
  3. The single sacred discovery/OOS path still runs unchanged, and its existing manifest columns (`rate`, `n`, `successes`, `ci_low`, `ci_high`, `min_n_pass`) are identical to the pre-change output — the correction and walk-forward results are additive columns/artifacts, never a rewrite of the prior numbers.
  4. Characterization/unit tests cover the new math (a known bucket grid yields known adjusted q-values; a known window schedule yields known per-window splits), and the full pre-existing test suite still passes green.

**Plans**: 2/2 plans complete
**Wave 1**

- [x] 06-01-PLAN.md — Per-bucket significance test + Benjamini-Hochberg FDR correction across the full bucket grid, discovery-stage only (MHT-01)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 06-02-PLAN.md — Walk-forward validation: frozen anchored folds within the discovery slice + aggregate robustness verdict as an additive artifact (WF-01)

### Phase 7: Corrected Re-Validation of the Post-CISD Studies

**Goal**: The two post-CISD studies from Phase 5 — never fully validated after they shipped — are re-run end-to-end under the corrected methodology so they carry real, FDR-corrected, walk-forward-confirmed rates; the `failed_gap_against` bucket additionally gains an explicit reversal barrier. This phase's output is the corrected evidence that gates the modeling decision.
**Depends on**: Phase 6 (requires the corrected + walk-forward harness)
**Requirements**: RES-04, RES-05
**Success Criteria** (what must be TRUE):

  1. `post_cisd_context` grows an explicit reversal-barrier measurement for `failed_gap_against`: the manifest reports, per direction/instrument/timeframe, the rate at which `candle[0]`'s opposite extreme is hit first (a true reversal), reported distinctly from the existing depressed continuation rate.
  2. The validation manifest is regenerated end-to-end (discovery, sacred OOS, and walk-forward) so every `post_cisd_context` and `candle1_followthrough` bucket carries n, Wilson CI, the FDR-corrected verdict, and a walk-forward robustness verdict.
  3. A written verdict states, per post-CISD tag, whether it clears the corrected evidence bar (a real, durable, corrected, walk-forward-confirmed effect) — serving as the explicit go/no-go input to Phase 8.
  4. Any change in how these two studies' rates read versus their Phase 5 numbers is documented as a deliberate, visible methodology change in the summary/README — never a silent drift — and the behavior-lock tests on unchanged code paths still pass.

**Plans**: 3/3 plans complete

**Wave 1** *(parallel — disjoint files)*

- [x] 07-01-PLAN.md — Reversal barrier for `failed_gap_against`: `barrier_outcome_forward` (continuation/reversal/neither) + new tags on `compute_post_cisd_context` + chart (RES-04)
- [x] 07-02-PLAN.md — Corrected go/no-go verdict script (`build_post_cisd_verdict.py`): D-02 three-condition bar + D-03 per-tag majority roll-up, fixture-tested (RES-05)

**Wave 2** *(blocked on Wave 1)*

- [x] 07-03-PLAN.md — Regenerate all three manifests end-to-end + D-10 sanity check, run the verdict script, publish the go/no-go README section + D-04 disclaimer (RES-04, RES-05)

### Phase 8: Performance — Vectorize the Enrichment & Validation Hot Path

**Goal**: The end-to-end validation regen (discovery + OOS + walk-forward, ×4 timeframes, with the SMT scan) runs fast enough to iterate on, by replacing the row-by-row annotation loops with vectorized numpy/pandas and removing redundant re-computation. Strictly behavior-preserving: every existing published rate and manifest value is identical before and after — this is a speed change, not a methodology change. This phase is a prerequisite enabler so the feature work in Phases 9–10 is fast to build and runs in the vectorized style.
**Depends on**: Phase 7 (the corrected, refactored harness whose output must be reproduced identically)
**Requirements**: PERF-01
**Success Criteria** (what must be TRUE):

  1. `_annotate_swing_smt_from_events` (currently ~O(bars × events) nested Python loop with `.iat` scalar access) and `_annotate_cisd_research` (per-event Python loop with `.iloc`/`.iat` scalar reads and nested window loops) are re-expressed vectorized, and redundant `prepare_pair` calls in `scripts/build_validation.py` `main()` are eliminated.
  2. A characterization test proves the regenerated manifests (discovery, OOS, walk-forward) are identical to the pre-change output — the same behavior-lock discipline used for the Phase 4 refactor; no published number moves.
  3. The end-to-end manifest regeneration is measurably faster (wall-clock recorded before/after), with the dominant single-threaded hot spots removed; any residual parallelization across independent timeframes is optional and additive, not the primary win.
  4. The full pre-existing test suite still passes green.

**Plans**: 3/3 plans complete

**Wave 1** *(behavior-lock — must land before any vectorization)*

- [x] 08-01-PLAN.md — Capture golden manifests (discovery/OOS/walk-forward) from pre-change code, author the data+SMT+env-gated end-to-end bit-equality test + fast synthetic parity tests, record SC3 baseline timing (PERF-01)

**Wave 2** *(blocked on Wave 1)*

- [x] 08-02-PLAN.md — Vectorize `_annotate_cisd_research` (FVG/sweep/swing/candle features), byte-identical enrichment columns (PERF-01)

**Wave 3** *(blocked on Wave 2 — same file cisd_data.py)*

- [x] 08-03-PLAN.md — Vectorize `_annotate_swing_smt_from_events` + remove redundant `prepare_pair` recompute (preserving `with_smt`/sys.path side-effect) + end-to-end golden bit-equality + after-timing + full suite (PERF-01)

### Phase 9: SMT Geometry & Invalidation Honesty

**Goal**: The SMT study stops discarding the price and lifecycle data the scanner already returns, and stops crediting SMTs that were already invalidated. `reference_price`, `invalidation_level`, `broken_ts`, and `status` are carried through the SMT annotation; the correctness bug where an SMT invalidated at or before the CISD bar `t` is still tagged `w/ SMT` is fixed; and new geometry features (role, magnitude, CISD-in-block containment) plus a survived-vs-broke-in-window diagnostic split are added and put through the full validation harness. Any change to the published SMT numbers is a deliberate, documented methodology change, never silent drift.
**Depends on**: Phase 8 (builds on the vectorized SMT annotation path)
**Requirements**: RES-06
**Success Criteria** (what must be TRUE):

  1. The SMT annotation carries `reference_price`, `invalidation_level`, `broken_ts`, and `status`, and the `w/ SMT` tag is only assigned when the matched same-direction SMT is still valid as of the CISD bar `t` (the already-invalidated-at-`t` tagging bug is fixed); the resulting change to the SMT rates is documented as a deliberate methodology change with before/after visible.
  2. `swing_smt_role` (swept vs. failed_to_sweep) — currently computed but consumed by no analysis — is reported as an analyzed bucket split.
  3. New features `smt_block_size_atr` (SMT magnitude, `block_high − block_low` normalized by ATR) and `cisd_in_smt_block` (whether the CISD body lies within the SMT block zone) are computed same-timeframe and split through the barrier model.
  4. The `w/ SMT` bucket additionally reports a survived-vs-broke-in-window diagnostic split (the population is never filtered on survival — that would be hindsight); and every new bucket carries n, Wilson CI, the FDR-corrected verdict, and a walk-forward robustness verdict.

**Plans**: 3/3 plans complete

**Wave 1**

- [x] 09-01-PLAN.md — SMT annotation: carry lifecycle fields, fix the already-invalidated-at-`t` tagging bug (three-way tag + survived/broke flag), add geometry columns (RES-06)

**Wave 2** *(blocked on Wave 1 — reads the new annotation columns)*

- [x] 09-02-PLAN.md — SMT barrier consumers: three-way + survived/broke `smt_cisd`, new `smt_role` / `smt_block_size` / `smt_in_block` analyses + charts + registry wiring (RES-06)

**Wave 3** *(blocked on Waves 1-2 — regen depends on the fixed/extended code)*

- [x] 09-03-PLAN.md — Regenerate manifests + before/after methodology report + README "SMT Invalidation Honesty (v2.0)" writeup (operator-run heavy regen) (RES-06)

### Phase 10: New Conditioning Features — Magnitude, Session & Volume Anomaly

**Goal**: Three families of economically-motivated conditioning features are added and validated through the harness, giving the eventual model better inputs than the current binary flags. (a) Continuous magnitude versions of existing binary flags; (b) session / time-of-day structure the engine currently lacks entirely; (c) CISD volume-anomaly measures that go beyond the already-negligible 1-bar volume ratio. Each is put through the same n + CI + FDR + walk-forward discipline; features that do not clear the bar are reported as such, not hidden.
**Depends on**: Phase 8 (built on the fast, vectorized annotation path; independent of Phase 9)
**Requirements**: RES-07
**Success Criteria** (what must be TRUE):

  1. Magnitude features augment the binary flags with continuous, ATR-normalized versions — at minimum distance-past-previous-wick, sweep penetration depth, and FVG size — bucketed and run through the barrier model.
  2. Session / time-of-day tags derived from the ET index (e.g. kill-zones, RTH-open vs. overnight) are added and split through the harness; the engine gains its first temporal conditioning dimension.
  3. CISD volume-anomaly measures — rolling RVOL / z-score (distinct from the existing negligible 1-bar ratio), effort-vs-result (volume ÷ range/body), and optional cross-asset NQ-vs-ES volume divergence on normalized terms — are computed and validated; the OHLCV-only limitation (no signed/delta order flow) is stated explicitly.
  4. Every new bucket carries n, Wilson CI, the FDR-corrected verdict, and a walk-forward robustness verdict; non-confirming features are published as not-confirmed / below-n rather than dropped.

**Plans**: 1/4 plans executed

**Wave 1**

- [x] 10-01-PLAN.md — Annotation layer: all new columns for the three feature families in `_annotate_cisd_research` (signed wick distance, sweep depth + pierced level, FVG size + gap width, session tag, effort-vs-result, slot-normalized RVOL / z-score) (RES-07)

**Wave 2** *(blocked on Wave 1 — reads the new annotation columns)*

- [ ] 10-02-PLAN.md — Magnitude + volume-anomaly analyses: 6 standalone `compute_*`/`chart_*`/registry entries (wick_distance, sweep_depth, fvg_size, effort_result, rvol, volume_zscore) with outcome-blind frozen bins (RES-07)

**Wave 3** *(blocked on Wave 2 — shares cisd_barriers.py / cisd_charts.py)*

- [ ] 10-03-PLAN.md — Session analysis + the D-14 TF-scoping mechanism (ANALYSIS_META `applies_to` allow-list; session validated on 15min/1H only) (RES-07)

**Wave 4** *(blocked on Waves 2-3 — regen runs the full registry)*

- [ ] 10-04-PLAN.md — Graceful column tolerance, byte-stability drift gate (D-12), end-to-end manifest regen (SC4), refreshed golden fixtures, and the D-11/D-13 README writeup (RES-07)

### Phase 11: Conditional Post-CISD Model

**Goal**: Using the corrected evidence from Phases 7, 9, and 10 as a strict gate, decide whether any feature family justifies a small model. The model is built only over whichever families (post-CISD context tags, SMT geometry, session, volume anomaly) actually cleared the corrected/walk-forward bar; if none cleared, the phase ships a documented "no model warranted" conclusion. Both are valid, successful outcomes — the phase does not presuppose any family passes.
**Depends on**: Phases 9 and 10 (their corrected feature evidence) and Phase 7 (the post-CISD go/no-go verdict)
**Requirements**: ML-01
**Success Criteria** (what must be TRUE):

  1. The phase opens by reading the per-tag / per-feature corrected verdicts from Phases 7, 9, and 10 and records an explicit gate decision (build vs. no-model-warranted), citing the corrected/walk-forward evidence and naming which feature families qualify.
  2. If the gate passes: a model is built only over the qualifying feature families and its performance is reported on the sacred OOS holdout (and/or walk-forward windows) through the same n + CI + corrected discipline — no in-sample-only model metric is ever published.
  3. If the gate fails: the phase ships a documented "no model warranted" conclusion naming which families failed the corrected/walk-forward bar, and no speculative model is built.
  4. Either way the milestone's honesty invariant holds: no ML claim is made that is not gated by corrected, out-of-sample-confirmed evidence.

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 6 → 7 → 8 → 9 → 10 → 11. Phase 7 requires the corrected harness from Phase 6. Phase 8 (performance) is a behavior-preserving enabler that must precede the feature work so it iterates fast. Phases 9 (SMT geometry) and 10 (new conditioning features) both build on Phase 8 and are mutually independent — disjoint feature families, so either order (or parallel) works. Phase 11 (the model) is gated on the corrected evidence from Phases 7, 9, and 10. RES-04 (reversal barrier) was folded into Phase 7 alongside RES-05 because both operate on the same `post_cisd_context` study.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 6. Harder Evidence Bar (MHT + Walk-Forward) | v2.0 | 2/2 | Complete    | 2026-07-10 |
| 7. Corrected Re-Validation of Post-CISD Studies | v2.0 | 3/3 | Complete    | 2026-07-11 |
| 8. Performance — Vectorize Enrichment & Validation Hot Path | v2.0 | 3/3 | Complete    | 2026-07-11 |
| 9. SMT Geometry & Invalidation Honesty | v2.0 | 3/3 | Complete    | 2026-07-12 |
| 10. New Conditioning Features (Magnitude, Session, Volume Anomaly) | v2.0 | 1/4 | In Progress|  |
| 11. Conditional Post-CISD Model | v2.0 | 0/TBD | Not started | - |
