---
phase: 05-new-cisd-research-on-the-validated-engine
plan: 01
subsystem: research
tags: [cisd, barrier-analysis, follow-through, validation-harness, tdd, wilson-ci]

# Dependency graph
requires:
  - phase: 04-test-gated-modular-refactor
    provides: cisd_data/cisd_barriers/cisd_charts modular engine, ANALYSIS_META registry, re-export shim
  - phase: 02-validation-harness
    provides: build_validation.py, wilson_ci, n_gate, OOS_START, generic else dispatch branch

provides:
  - candle1_close_dir and candle1_past_candle0_wick precomputed columns in _annotate_cisd_research
  - barrier_hit_forward — re-anchored barrier helper (lookahead starts at idx+2)
  - compute_candle1_followthrough — 6-tag two-window barrier study (in-window + forward re-anchored)
  - chart_candle1_followthrough — horizontal bar chart with alpha layering for tautology gap visibility
  - ANALYSES['candle1_followthrough'] and ANALYSIS_META['candle1_followthrough'] (standalone=True)
  - output/Candle1_Followthrough_All_Timeframes.png
  - candle1_followthrough rows in discovery/OOS manifests with Wilson CI + n-gate + slice

affects:
  - 05-02 (multi-bar post-CISD context — builds on same candle[1] failed-followthrough pattern)
  - any future research that extends the candle[1] feature columns or barrier_hit_forward

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Precompute-in-prepare, consume-in-compute (candle[1] features added to _annotate_cisd_research)
    - Two-window barrier reporting: in-window vs forward re-anchored, exposing tautology gap
    - barrier_hit_forward variant: same target/stop as barrier_hit, window shifted to idx+2
    - 6-tag dict shape {dir: {core_bucket_suffix: {total, runs}}} slots into generic harness branch

key-files:
  created: []
  modified:
    - cisd_data.py — _annotate_cisd_research: 2 new precomputed columns
    - cisd_barriers.py — barrier_hit_forward, compute_candle1_followthrough, ANALYSES, ANALYSIS_META, __all__
    - cisd_charts.py — chart_candle1_followthrough, build_csv_rows extended, __all__
    - cisd_analysis.py — re-export imports and __all__ extended
    - tests/test_research_extensions.py — 19 new tests (TDD RED+GREEN for Tasks 1-3)

key-decisions:
  - "candle[0] high/low as barrier target/stop (D-01): R-unit unchanged, RES-01 hit-rates comparable to README"
  - "In-window + forward re-anchored side by side per bucket (D-02): tautology gap made visible"
  - "3-way core buckets mirror compute_wick (D-03): against / with_within_wick / with_past_wick"
  - "Flat closes fold into against (D-04 discretion): consistent with existing neutral direction treatment"
  - "candle1_followthrough is standalone (ANALYSIS_META.standalone=True): own all-TF PNG"
  - "Generic else branch in build_manifest_rows handles new key automatically — no special-casing"
  - "barrier_hit_forward as separate function (not parameterization) to keep barrier_hit byte-identical"

patterns-established:
  - "Two-window research pattern: in-window (tautological but comparable) + forward re-anchored (honest)"
  - "Feature column precompute: idx+1 boundary guard prevents IndexError on last-bar CISD"
  - "6-tag dict naming: {core}_{inwindow|forward} — self-describing manifest bucket names"

requirements-completed: [RES-01, RES-03]

# Metrics
duration: 92min
completed: 2026-06-14
---

# Phase 5 Plan 01: Candle[1] Follow-Through Barrier Study Summary

**Candle[1] follow-through analysis measuring barrier hit in two windows (in-window vs forward re-anchored) per direction/wick-position bucket, reported through Wilson CI + n-gate + IS/OOS harness from the start**

## Performance

- **Duration:** ~92 min (full test suite ~28 min of that)
- **Started:** 2026-06-14T06:41:18Z
- **Completed:** 2026-06-14T09:00Z (approx)
- **Tasks:** 3 (all complete)
- **Files modified:** 5

## Accomplishments

- Precomputed `candle1_close_dir` ("with"/"against") and `candle1_past_candle0_wick` (bool) columns in `_annotate_cisd_research`, following the existing bulk-accumulate-then-assign pattern with boundary guards
- Added `barrier_hit_forward` (window starts at idx+2) and `compute_candle1_followthrough` (6-tag two-window dict) to `cisd_barriers.py`, plus `chart_candle1_followthrough` to `cisd_charts.py` — all registered and re-exported
- Wired through validation harness with zero code changes to `build_validation.py` (generic else branch auto-handles the {dir:{tag:{total,runs}}} shape); standalone PNG produced via `cisd_analysis.py candle1_followthrough`

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Add failing tests for candle[1] feature columns** - `c5c1417` (test)
2. **Task 1 GREEN: Precompute candle[1] feature columns in _annotate_cisd_research** - `2a4049b` (feat)
3. **Task 2 RED: Add failing tests for compute_candle1_followthrough, chart, registry** - `f5f930e` (test)
4. **Task 2 GREEN: Add compute_candle1_followthrough, chart, forward barrier, registry** - `1186417` (feat)
5. **Task 3: Wire candle1_followthrough through validation harness, add tests** - `92c2669` (feat)

## Files Created/Modified

- `/mnt/e/backup/code/Finance/Research/cisd-markov/cisd_data.py` — `_annotate_cisd_research`: 2 new precomputed columns (`candle1_close_dir`, `candle1_past_candle0_wick`) with last-bar boundary guard
- `/mnt/e/backup/code/Finance/Research/cisd-markov/cisd_barriers.py` — `barrier_hit_forward`, `compute_candle1_followthrough`, ANALYSES + ANALYSIS_META entries, `__all__` extended
- `/mnt/e/backup/code/Finance/Research/cisd-markov/cisd_charts.py` — `chart_candle1_followthrough`, `build_csv_rows` extended for new key, `__all__` extended
- `/mnt/e/backup/code/Finance/Research/cisd-markov/cisd_analysis.py` — import blocks and `__all__` extended for all new symbols
- `/mnt/e/backup/code/Finance/Research/cisd-markov/tests/test_research_extensions.py` — 19 new unit tests covering Tasks 1, 2, and 3

## Decisions Made

- Used separate `barrier_hit_forward` function rather than parameterizing `barrier_hit` with a `start_offset` keyword — this keeps `barrier_hit` byte-identical so all locked characterization numbers are preserved
- No changes to `build_validation.py` were needed: the 6-tag {dir:{tag:{total,runs}}} shape falls through the existing generic `else` branch automatically, and `main()` auto-includes new ANALYSES keys via `list(ANALYSES.keys())`
- `build_csv_rows` in `cisd_charts.py` was extended to include `"candle1_followthrough"` in its sweep/sssf_swing branch to avoid the catch-all fallback that would silently produce no rows

## Deviations from Plan

None — plan executed exactly as written. The only discovery was that `build_csv_rows` needed a one-line update (adding `"candle1_followthrough"` to an existing branch) to ensure the key is handled there too. This is consistent with the existing pattern and not a deviation.

## Issues Encountered

None. The generic harness branch required zero changes. All three TDD cycles (RED → GREEN) completed cleanly on the first attempt.

## Known Stubs

None — the new analysis is fully wired: precomputed columns → compute function → chart function → ANALYSES registry → re-export shim → validation harness manifest. No placeholder data, no hardcoded empty values.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. This plan is purely additive: new in-memory columns, pure-Python compute functions, and CSV/PNG output.

## Next Phase Readiness

- RES-01 complete: `candle1_followthrough` analysis shipping through the harness with honest statistics from the start
- RES-03 half-complete (this plan's half): candle[1] study reports Wilson CI + n-gate + IS/OOS slice
- 05-02 can now build on `candle1_close_dir` / `candle1_past_candle0_wick` feature columns and `barrier_hit_forward` already precomputed

## Self-Check: PASSED

- `cisd_data.py` modified with 2 new columns: CONFIRMED
- `cisd_barriers.py` modified with barrier_hit_forward + compute_candle1_followthrough + registry: CONFIRMED
- `cisd_charts.py` modified with chart_candle1_followthrough: CONFIRMED
- `cisd_analysis.py` re-export shim updated: CONFIRMED
- `tests/test_research_extensions.py` has 19 new tests: CONFIRMED
- Full test suite: 113 passed (94 original + 19 new), exit code 0: CONFIRMED
- `cisd_analysis.py candle1_followthrough` produced `output/Candle1_Followthrough_All_Timeframes.png`: CONFIRMED
- Re-export shim verify: `import cisd_analysis; cisd_analysis.compute_candle1_followthrough; cisd_analysis.chart_candle1_followthrough` — exit 0: CONFIRMED

---
*Phase: 05-new-cisd-research-on-the-validated-engine*
*Completed: 2026-06-14*
