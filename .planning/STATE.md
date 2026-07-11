---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Rigorous Validation & Post-CISD Modeling
current_phase: 8
current_phase_name: Performance — Vectorize the Enrichment & Validation Hot Path
status: planned
stopped_at: Phase 8 planned — 3 plans across 3 waves, ready to execute
last_updated: "2026-07-11T17:56:46.000Z"
last_activity: 2026-07-11
last_activity_desc: Phase 8 planned — 3 plans (behavior-lock → vectorize research annotation → vectorize SMT annotation + de-dupe harness), plan-checker passed
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 5
  completed_plans: 5
  percent: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-10)

**Core value:** A reported edge can be trusted — every published rate is sample-size gated, carries a confidence interval, and is confirmed out-of-sample.
**Current focus:** Phase 08 — performance: vectorize the enrichment & validation hot path

## Current Position

Phase: 8 — Performance — Vectorize the Enrichment & Validation Hot Path
Plan: 3 plans (08-01, 08-02, 08-03) across 3 waves
Status: Ready to execute — planned & checker-verified (VERIFICATION PASSED)
Last activity: 2026-07-11 — Phase 8 planned: 3 plans, plan-checker passed

Progress: [███░░░░░░░] 33% (2 of 6 phases complete)

## Performance Metrics

**Velocity:**

- Total plans completed: 5 (v1.0)
- Average duration: -
- Total execution time: 0 hours (v2.0)

**By Phase (v2.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 06 | 2 | - | - |
| 07 | 3 | - | - |
| 08 | 3 | - | - |
| 09 | TBD | - | - |
| 10 | TBD | - | - |
| 11 | TBD | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 06 P02 | 13min | 3 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [2026-07-11] v2.0 extended mid-milestone with feature engineering before ML: Phases 8 (perf/vectorize, behavior-preserving), 9 (SMT geometry & invalidation honesty), 10 (magnitude/session/volume) inserted before the model; ML-01 moved to Phase 11 and broadened to consume whichever feature families clear the corrected bar. New requirement codes PERF-01, RES-06, RES-07. User decisions: extend v2.0 (not new milestone), model consumes new features, three feature phases (perf / SMT-geometry / combined conditioning)
- v2.0 scope = MHT-01 + WF-01 (harness upgrade) → RES-04 + RES-05 (corrected re-validation of post-CISD studies) → ML-01 (conditional model); ML-01 is strictly gated on RES-05's corrected evidence
- New methodology is additive/parallel output — existing published numbers must not silently move; any change in how a prior finding reads must be deliberate and visible (carried from v1.0 behavior-lock)
- RES-04 (reversal barrier) folded into Phase 7 with RES-05 because both operate on the same `post_cisd_context` study; it does not block or get blocked by the Phase 6 harness upgrade
- ML-01's phase may validly conclude "no model warranted" — the roadmap does not presuppose the post-CISD tags clear the corrected bar
- [Phase 05-02]: post_cisd_context uses barrier_hit_forward (continuation target = candle[0] extreme in CISD direction); RES-04 adds the opposite-extreme reversal measurement
- [Phase 06]: WF-01: WALK_FORWARD_FOLDS frozen at 4 discovery-percentile calendar dates (20th/40th/60th/80th); slice_fold anchors folds to the discovery region only; evaluate_fold uses a per-fold MIN_N gate; walk_forward_verdict requires a strict majority (>50%) of folds to pass
- [Phase 06]: walk-forward CLI branch takes precedence over --oos if both are passed, and writes output/validation_manifest_walkforward.csv as a purely additive sibling artifact without touching the discovery/OOS manifests or the sacred OOS banner

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- SMT integration path remains untested in CI (hardcoded WSL path); known limitation carried from v1.0
- Phase 6 correction/walk-forward math is net-new (no prior MHT/walk-forward code in `scripts/build_validation.py`); needs its own characterization tests

### Roadmap Evolution

- Phase 8 inserted after Phase 7: Performance — vectorize the enrichment & validation hot path (behavior-preserving; PERF-01)
- Phase 9 inserted after Phase 8: SMT Geometry & Invalidation Honesty — carry SMT price/lifecycle fields, fix invalidated-SMT tagging bug, add role/magnitude/CISD-in-block/survived-vs-broke (RES-06)
- Phase 10 inserted after Phase 9: New Conditioning Features — magnitude versions of binary flags, session/time-of-day, CISD volume anomaly (RES-07)
- Phase 11 moved: Conditional Post-CISD Model moved from Phase 8 to Phase 11 and broadened to consume qualifying feature families (post-CISD tags, SMT geometry, session, volume); ML-01 gate now spans Phases 7/9/10

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Advanced validation | Multiple-comparisons correction (MHT-01) | promoted to Phase 6 | 2026-07-10 |
| Advanced validation | Walk-forward / rolling-window validation (WF-01) | promoted to Phase 6 | 2026-07-10 |
| Modeling | `post_cisd_ml` post-CISD ML model (ML-01) | moved to Phase 11 (conditional; broadened to consume SMT-geometry/session/volume features) | 2026-07-10 |
| Verification gap | Phase 03 — `03-VERIFICATION.md` human QA checks | human_needed (out of v2.0 scope) | 2026-07-10 |
| Verification gap | Phase 05 — formal verification report missing | missing (out of v2.0 scope) | 2026-07-10 |
| Traceability | VALID-01 through VALID-05 source checklist stale at closeout | normalized in archive | 2026-07-10 |

## Session Continuity

Last session: 2026-07-10T20:11:32.811Z
Stopped at: Phase 7 context gathered
Resume file: .planning/phases/07-corrected-re-validation-of-the-post-cisd-studies/07-CONTEXT.md

## Operator Next Steps

- Execute Phase 8 (performance / vectorization): /gsd-execute-phase 8 (Wave 1 behavior-lock first)
- Then Phases 9 (SMT geometry) and 10 (conditioning features) — independent, either order
- Phase 11 (conditional model) last, gated on corrected evidence from Phases 7/9/10
