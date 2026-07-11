# CISD-Markov Research Engine

## What This Is

A quantitative research engine for testing CISD (Change in State of Delivery) barrier-hit patterns across NQ and ES futures. It uses a strict first-touch barrier model across multiple timeframes and now produces research findings with a reproducible runtime, test coverage, sample-size gates, confidence intervals, and explicit discovery/OOS status.

## Core Value

A reported edge can be trusted: every published rate is sample-size gated, carries a confidence interval, and is confirmed on out-of-sample data rather than discovered and reported in-sample.

## Current State

**v1.0 Validated Research Engine shipped on 2026-07-10.**

- Five phases, 13 plans, and 10 recorded tasks delivered.
- The engine is pinned, deterministic, CI-tested, and behavior-locked with characterization tests.
- The validation harness uses a sacred chronological holdout, Wilson confidence intervals, and a minimum-n gate.
- Existing findings were republished with discovery/OOS verdicts; two new post-CISD studies were added to the same harness.
- Closeout is an override: Phase 3 still has five human QA checks, and Phase 5 lacks a formal verification report. See `.planning/MILESTONES.md` and `.planning/STATE.md`.

## Current Milestone: v2.0 Rigorous Validation & Post-CISD Modeling

**Goal:** Upgrade the validation harness with multiple-comparisons correction and walk-forward validation, re-validate the post-CISD studies under that harder bar, then — after vectorizing the hot path and widening the feature surface on that same validated footing — use the corrected, expanded evidence to decide whether any feature family justifies a small model.

**Target features:**
- MHT-01 — multiple-comparisons / data-snooping correction across the full bucket grid
- WF-01 — walk-forward / rolling-window validation, supplementing the single sacred discovery/OOS split
- Explicit reversal barrier for RES-02 — whether `candle[0]`'s opposite extreme is hit first, not just a depressed continuation rate
- PERF-01 — vectorize the enrichment/validation hot path so the end-to-end regen is fast (behavior-preserving; no published number moves)
- RES-06 — SMT geometry & invalidation honesty (carry the scanner's price/lifecycle fields, fix the invalidated-SMT tagging bug, add role/magnitude/CISD-in-block/survived-vs-broke features)
- RES-07 — new conditioning features: continuous magnitudes of the binary flags, session/time-of-day, and CISD volume anomalies
- ML-01 — a small model, gated on whichever feature families first show a real, corrected, OOS-confirmed effect (post-CISD tags, SMT geometry, session, volume)

## Requirements

### Validated

- ✓ Reproducible runtime, optional SMT fallback, CI, deterministic execution, and repository hygiene — v1.0
- ✓ Characterization and unit tests lock published barrier-analysis behavior — v1.0
- ✓ Sacred date holdout, deliberate OOS path, Wilson confidence intervals, minimum-n gating, and results manifests — v1.0
- ✓ Existing README findings reconciled against discovery and OOS results with explicit verdict badges — v1.0
- ✓ Modular `cisd_data` / `cisd_barriers` / `cisd_charts` architecture, central analysis registry, and vectorized hot paths — v1.0
- ✓ `candle[1]` follow-through and multi-bar post-CISD context studies wired through the validation harness — v1.0
- ✓ Explicit reversal barrier for `failed_gap_against` (`barrier_outcome_forward`) reporting continuation/reversal/neither distinctly (RES-04) — Validated in Phase 7
- ✓ Validation manifest regenerated end-to-end under the corrected methodology; `post_cisd_context` and `candle1_followthrough` now carry real, FDR-corrected, walk-forward-confirmed rates with a published per-tag go/no-go verdict (RES-05) — Validated in Phase 7

### Active

- [ ] Multiple-comparisons / data-snooping correction applied across the validation harness's full bucket grid (MHT-01).
- [ ] Walk-forward / rolling-window validation supplementing the single sacred discovery/OOS split (WF-01).
- [x] Vectorized enrichment/validation hot path so the end-to-end regen is fast, behavior-preserving (PERF-01). — Validated in Phase 8: both annotation loops vectorized + redundant recompute removed; all 3 manifests bit-identical to pre-change golden; suite 21m14s→6m35s.
- [ ] SMT geometry & invalidation honesty — carry the scanner's price/lifecycle fields, fix the invalidated-SMT tagging bug, add role/magnitude/CISD-in-block/survived-vs-broke, all validated (RES-06).
- [ ] New conditioning features — continuous magnitudes of the binary flags, session/time-of-day, and CISD volume anomalies, all validated (RES-07).
- [ ] A small model over the qualifying feature families, built only once at least one family clears the corrected evidence bar (ML-01).

### Out of Scope

- Live signaling, trading productization, and instruments beyond NQ/ES remain outside the research-engine scope.
- Phase 3's human QA checks and Phase 5's formal verification report remain open from v1.0 closeout — process debt, not v2.0 research scope. Tracked in `.planning/STATE.md` Deferred Items.

## Context

The codebase contains approximately 7,900 lines of Python and retains its offline, deterministic research constraints. Data is fixed 1-minute OHLCV parquet for NQ and ES, with `DateTime_ET` indexing. SMT is optional and degrades gracefully when unavailable; its CI integration path remains a known limitation.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Sacred chronological holdout | Prevent time-series leakage and protect OOS evidence | Implemented with a fixed `OOS_START` and deliberate OOS path |
| Wilson CI plus minimum-n gate | Establish a practical first validation baseline | Implemented; multiple-testing correction deferred |
| Characterize before refactoring | Preserve published behavior while improving structure | 94 tests confirmed the refactor was behavior-preserving |
| Single analysis registry | Avoid synchronized edits and omitted output wiring | `ANALYSIS_META` is the source of truth |
| Per-slice manifest filenames | Make discovery/OOS clobbering structurally difficult | Separate discovery and OOS manifests implemented |
| Publish failures explicitly | Avoid silently retaining only attractive findings | README distinguishes confirmed, not-confirmed, and below-n results |
| v2.0 scope = MHT-01 + WF-01 + reversal barrier + ML-01 | Matches the "v2" tags already used in STATE.md's Deferred Items; ML-01 requires the harness upgrade to run first | — Pending |
| Phase 3/5 verification debt left out of v2.0 | User chose to prioritize the research/methodology backlog over closing prior-milestone paperwork gaps | — Pending |
| v2.0 extended mid-milestone with feature engineering before ML (Phases 8–10) | Give the model economically-motivated, harness-validated inputs rather than let it mine noise; the slow single-threaded annotation hot path had to be vectorized first so feature iteration is cheap | Phases 8 (perf), 9 (SMT geometry & invalidation honesty), 10 (magnitude/session/volume) inserted; ML-01 moved to Phase 11 and broadened to consume whichever families clear the corrected bar |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-11 after Phase 8 complete — enrichment/validation hot path vectorized (PERF-01), behavior-preserving (manifests bit-identical); next: Phase 9 (SMT geometry & invalidation honesty)*
