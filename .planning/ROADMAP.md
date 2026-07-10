# Roadmap: CISD-Markov Research Engine

## Milestones

- ✅ **v1.0 Validated Research Engine** — Phases 1–5, shipped 2026-07-10 ([archive](milestones/v1.0-ROADMAP.md)); closed with documented verification overrides.
- 🚧 **v2.0 Rigorous Validation & Post-CISD Modeling** — Phases 6–8 (planning)

## Overview

v2.0 raises the evidence bar the engine already enforces. v1.0 gave every rate a sample-size gate, a Wilson confidence interval, and a sacred discovery/OOS split. This milestone hardens that harness — a "confirmed" edge must now survive a multiple-comparisons correction across the full bucket grid (so it accounts for how many buckets were tested, not just its own single-bucket CI) and must re-confirm across multiple sequential walk-forward windows, not just one fixed holdout. With that harder bar in place, the two post-CISD studies from Phase 5 (`post_cisd_context` and `candle1_followthrough`) — never fully validated after they shipped — are re-run end-to-end under the corrected methodology, and the `failed_gap_against` bucket gains an explicit reversal barrier that measures whether `candle[0]`'s opposite extreme is hit first, not just a depressed continuation rate. That corrected evidence is then the strict gate for the final phase: a small `post_cisd_ml` model is built only if the discrete tags actually clear the bar — and "no model warranted" is an equally valid, successful outcome. The v1.0 behavior-preservation invariant carries throughout: existing published numbers must not silently move; new methodology is additive/parallel output and any change to how a prior finding is reported is deliberate and visible.

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

**Milestone Goal:** Upgrade the validation harness with multiple-comparisons correction and walk-forward validation, re-validate the post-CISD studies under that harder bar, then use the corrected evidence to decide whether the post-CISD context tags justify a small ML model.

- [ ] **Phase 6: Harder Evidence Bar — Multiple-Comparisons Correction & Walk-Forward Validation** - Extend the harness with FDR correction across the bucket grid and rolling walk-forward windows, as additive output that leaves existing numbers untouched
- [ ] **Phase 7: Corrected Re-Validation of the Post-CISD Studies** - Regenerate the manifest end-to-end under the corrected methodology for `post_cisd_context` / `candle1_followthrough`, add the `failed_gap_against` reversal barrier, and issue the go/no-go verdict for modeling
- [ ] **Phase 8: Conditional Post-CISD Model** - Gated strictly on Phase 7's verdict, either build and validate `post_cisd_ml` or ship a documented "no model warranted" conclusion

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
**Plans**: 2 plans
- [ ] 06-01-PLAN.md — Per-bucket significance test + Benjamini-Hochberg FDR correction across the full bucket grid, discovery-stage only (MHT-01)
- [ ] 06-02-PLAN.md — Walk-forward validation: frozen anchored folds within the discovery slice + aggregate robustness verdict as an additive artifact (WF-01)

### Phase 7: Corrected Re-Validation of the Post-CISD Studies

**Goal**: The two post-CISD studies from Phase 5 — never fully validated after they shipped — are re-run end-to-end under the corrected methodology so they carry real, FDR-corrected, walk-forward-confirmed rates; the `failed_gap_against` bucket additionally gains an explicit reversal barrier. This phase's output is the corrected evidence that gates the modeling decision.
**Depends on**: Phase 6 (requires the corrected + walk-forward harness)
**Requirements**: RES-04, RES-05
**Success Criteria** (what must be TRUE):
  1. `post_cisd_context` grows an explicit reversal-barrier measurement for `failed_gap_against`: the manifest reports, per direction/instrument/timeframe, the rate at which `candle[0]`'s opposite extreme is hit first (a true reversal), reported distinctly from the existing depressed continuation rate.
  2. The validation manifest is regenerated end-to-end (discovery, sacred OOS, and walk-forward) so every `post_cisd_context` and `candle1_followthrough` bucket carries n, Wilson CI, the FDR-corrected verdict, and a walk-forward robustness verdict.
  3. A written verdict states, per post-CISD tag, whether it clears the corrected evidence bar (a real, durable, corrected, walk-forward-confirmed effect) — serving as the explicit go/no-go input to Phase 8.
  4. Any change in how these two studies' rates read versus their Phase 5 numbers is documented as a deliberate, visible methodology change in the summary/README — never a silent drift — and the behavior-lock tests on unchanged code paths still pass.
**Plans**: TBD

### Phase 8: Conditional Post-CISD Model

**Goal**: Using Phase 7's corrected evidence as a strict gate, decide whether the discrete post-CISD context tags justify a small model. If they cleared the bar, `post_cisd_ml` is built and validated through the same harness discipline; if they did not, the phase ships a documented "no model warranted" conclusion. Both are valid, successful outcomes — the phase does not presuppose the tags pass.
**Depends on**: Phase 7 (strictly gated on its corrected go/no-go verdict)
**Requirements**: ML-01
**Success Criteria** (what must be TRUE):
  1. The phase opens by reading Phase 7's per-tag verdict and records an explicit gate decision (build vs. no-model-warranted), citing the corrected/walk-forward evidence behind it.
  2. If the gate passes: `post_cisd_ml` is built over the post-CISD context features and its performance is reported on the sacred OOS holdout (and/or walk-forward windows) through the same n + CI + corrected discipline — no in-sample-only model metric is ever published.
  3. If the gate fails: the phase ships a documented "no model warranted" conclusion naming which tags failed the corrected/walk-forward bar, and no speculative model is built.
  4. Either way the milestone's honesty invariant holds: no ML claim is made that is not gated by the corrected, out-of-sample-confirmed evidence from Phase 7.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 6 → 7 → 8. Phase 7 requires the corrected harness from Phase 6; Phase 8 is strictly gated on Phase 7's verdict. RES-04 (reversal barrier) is folded into Phase 7 alongside RES-05 because both operate on the same `post_cisd_context` study and it does not block or get blocked by the Phase 6 harness upgrade.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 6. Harder Evidence Bar (MHT + Walk-Forward) | v2.0 | 0/2 | Not started | - |
| 7. Corrected Re-Validation of Post-CISD Studies | v2.0 | 0/TBD | Not started | - |
| 8. Conditional Post-CISD Model | v2.0 | 0/TBD | Not started | - |
