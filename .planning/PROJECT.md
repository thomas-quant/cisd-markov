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

## Requirements

### Validated

- ✓ Reproducible runtime, optional SMT fallback, CI, deterministic execution, and repository hygiene — v1.0
- ✓ Characterization and unit tests lock published barrier-analysis behavior — v1.0
- ✓ Sacred date holdout, deliberate OOS path, Wilson confidence intervals, minimum-n gating, and results manifests — v1.0
- ✓ Existing README findings reconciled against discovery and OOS results with explicit verdict badges — v1.0
- ✓ Modular `cisd_data` / `cisd_barriers` / `cisd_charts` architecture, central analysis registry, and vectorized hot paths — v1.0
- ✓ `candle[1]` follow-through and multi-bar post-CISD context studies wired through the validation harness — v1.0

### Active

- [ ] Complete the recorded Phase 3 human QA checks and produce a formal Phase 5 verification report.
- [ ] Define the next research milestone and its acceptance criteria.

### Out of Scope

- Multiple-comparisons correction and walk-forward validation remain the next rigor tier.
- `post_cisd_ml` remains deferred until the discrete post-CISD tags demonstrate durable value.
- Live signaling, trading productization, and instruments beyond NQ/ES remain outside the research-engine scope.

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

## Next Milestone Goals

1. Close the v1.0 verification exceptions before relying on its evidence for further conclusions.
2. Decide whether to add multiple-comparisons control, walk-forward validation, or another bounded research hypothesis.
3. Define fresh requirements with `$gsd-new-milestone`.

---
*Last updated: 2026-07-10 after v1.0 milestone completion*
