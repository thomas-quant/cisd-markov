---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Rigorous Validation & Post-CISD Modeling
current_phase: 10
current_phase_name: New Conditioning Features — Magnitude, Session & Volume Anomaly
status: executing
stopped_at: Phase 10 context gathered
last_updated: "2026-07-12T14:49:31.201Z"
last_activity: 2026-07-12
last_activity_desc: Phase 10 execution started
progress:
  total_phases: 6
  completed_phases: 4
  total_plans: 15
  completed_plans: 12
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-10)

**Core value:** A reported edge can be trusted — every published rate is sample-size gated, carries a confidence interval, and is confirmed out-of-sample.
**Current focus:** Phase 10 — New Conditioning Features — Magnitude, Session & Volume Anomaly

## Current Position

Phase: 10 (New Conditioning Features — Magnitude, Session & Volume Anomaly) — EXECUTING
Plan: 2 of 4
Status: Ready to execute
Last activity: 2026-07-12 — Phase 10 execution started

Progress: [███░░░░░░░] 33% (2 of 6 phases complete)

## Performance Metrics

**Velocity:**

- Total plans completed: 11 (v1.0)
- Average duration: -
- Total execution time: 0 hours (v2.0)

**By Phase (v2.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 06 | 2 | - | - |
| 07 | 3 | - | - |
| 08 | 3 | - | - |
| 09 | 3 | - | - |
| 10 | TBD | - | - |
| 11 | TBD | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 06 P02 | 13min | 3 tasks | 5 files |
| Phase 08 P01 | 35min | 2 tasks | 6 files |
| Phase 08 P02 | 55min | 1 tasks | 1 files |
| Phase 09 P01 | 15min | 2 tasks | 4 files |
| Phase 09 P02 | 20min | 3 tasks | 4 files |
| Phase 09 P03 | 68min | 3 tasks | 5 files |
| Phase 10 P01 | 50min | 3 tasks | 2 files |

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
- [Phase 08]: Reused Phase 7's already-captured manifests as golden (user-approved deviation) instead of a fresh ~24min regeneration, since cisd_data.py and scripts/build_validation.py were confirmed clean/unchanged and predate the manifests on disk
- [Phase 08]: Adopted Phase 7's baseline timing (07-03-SUMMARY.md: ~24min parallel / ~60min sequential) as the SC3 'before' record; Plan 08-03 must measure 'after' comparably
- [Phase 08]: Deferred the live CISD_PERF_CHAR=1 characterization pass to Plan 08-03's authoritative before/after proof, avoiding a redundant ~24min regeneration in this behavior-lock plan
- [Phase 08]: Fully vectorized the sweep computation via a two-stage rolling reduction (per-bar trigger + rolling-any) instead of a bounded per-window loop, and left the four private enrichment helpers (_compute_three_bar_swings, _has_directional_fvg, _classify_fvg_hold, _has_directional_sweep) untouched since they are independently unit-tested and exported.
- [Phase 09-01]: D-01/D-02/D-03/D-03a validity fix (broken_ts vs t, never status, latest-match-only) + smt_broke_in_window (D-06) + smt_block_size_atr/cisd_in_smt_block geometry (D-04/D-05/D-05a) implemented vectorized in _annotate_swing_smt_from_events; updated 3 pre-existing Phase 08 parity-lock test fixtures for the widened event schema
- [Phase 09-02]: compute_smt_cisd extended to three-way (w/ SMT / expired SMT / no SMT) plus w/ SMT & survived / w/ SMT & broke diagnostic sub-buckets that never filter the aggregate w/ SMT population; new compute_smt_role/compute_smt_block_size/compute_smt_in_block registered as standalone analyses flowing through the generic manifest dispatch
- [Phase 09-03]: build_smt_invalidation_report.py enforces D-09a via build_non_smt_drift (non-zero exit on any non-smt_* rate/n drift); README documents the corrected SMT rates as a deliberate methodology change including the one verdict flip (4H ES Bearish: NOT CONFIRMED -> CONFIRMED)
- [Phase ?]: [Phase 10-01] Sweep-anchoring frozen: sweep_depth_atr/swept_level measured at the CISD bar t against the nearest prior swing extreme as-of-t (roll_min_prior_swing_low/roll_max_prior_swing_high), not the specific triggering sweep_idx within SWEEP_TOLERANCE
- [Phase ?]: [Phase 10-01] mid0-priority FVG union frozen: where both a mid0 and mid1 FVG exist at the same CISD bar, fvg_gap_width/fvg_size_atr take the mid0 (CISD-bar) gap, a single flat population for Plan 02's compute_fvg_size
- [Phase ?]: [Phase 10-01] wick_distance_atr's prev_high/prev_low derived locally from high/low.shift(1) instead of a prev_high/prev_low column; vol_per_range/rvol/volume_zscore degrade to NaN when volume column absent -- fixed a regression that broke 17 pre-existing behavior-lock tests

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

Last session: 2026-07-12T14:46:40.075Z
Stopped at: Phase 10 context gathered
Resume file: .planning/phases/10-new-conditioning-features-magnitude-session-volume-anomaly/10-CONTEXT.md

## Operator Next Steps

- Execute Phase 8 (performance / vectorization): /gsd-execute-phase 8 (Wave 1 behavior-lock first)
- Then Phases 9 (SMT geometry) and 10 (conditioning features) — independent, either order
- Phase 11 (conditional model) last, gated on corrected evidence from Phases 7/9/10
