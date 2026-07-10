---
phase: 06-harder-evidence-bar-multiple-comparisons-correction-walk-for
plan: 02
subsystem: testing
tags: [walk-forward, rolling-window-validation, validation-harness, pandas, cli]

# Dependency graph
requires:
  - phase: 06-01
    provides: p_value_vs_half/bh_correct/apply_bh_correction wired into the discovery manifest; same-file build_validation.py conventions to extend
provides:
  - "WALK_FORWARD_FOLDS — frozen 4-tuple of discovery-region calendar-date fold boundaries (cisd_data.py, re-exported via cisd_analysis.py)"
  - "slice_fold(df, train_end, test_end) — anchored train/test slicing confined to the discovery region (D-04/D-05)"
  - "evaluate_fold(train_rate, train_n, test_rate, test_n) — per-fold pass/fail/below-n verdict with a per-fold MIN_N gate (D-07)"
  - "walk_forward_verdict(fold_verdicts) — majority-based aggregate robustness verdict (D-07)"
  - "build_walkforward_rows(keys, df_nq, df_es, tf_label) — pure per-bucket fold aggregation, testable independent of main()"
  - "--walk-forward CLI flag and main() branch writing output/validation_manifest_walkforward.csv"
affects: [07 (post-CISD re-validation can read wf_verdict alongside corrected_pass)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Frozen-constant boundary dates (WALK_FORWARD_FOLDS) mirroring the OOS_START 'do not recompute at runtime' convention"
    - "Pure in-memory aggregation helper (build_walkforward_rows) factored out of main() so fold-join/verdict logic is unit-testable without real data files"
    - "Additive sibling artifact (validation_manifest_walkforward.csv) rather than new columns on the existing discovery/oos manifests"

key-files:
  created: []
  modified:
    - cisd_data.py
    - cisd_analysis.py
    - scripts/build_validation.py
    - tests/test_validation_harness.py
    - README.md

key-decisions:
  - "D-04: slice_fold always restricts to slice_df(df, oos=False) first, so no walk-forward fold can ever return a bar >= OOS_START even if test_end is passed after OOS_START"
  - "D-05: windows are expanding/anchored — every fold trains on all discovery history up to its boundary, not a fixed-size rolling window"
  - "D-06: WALK_FORWARD_FOLDS are 4 frozen calendar-date constants (20th/40th/60th/80th percentile of the discovery calendar), not equal bar-count boundaries, matching the OOS_START precedent"
  - "D-07: per-fold MIN_N gate resolved in favor of gating both train_n and test_n independently; the aggregate wf_verdict requires a STRICT majority (>50%) of folds to pass, with below-n folds counted in the denominator"
  - "--walk-forward takes precedence over --oos if both flags are passed (documented in --oos's own help text)"
  - "Fold-to-bucket join is on the 5-tuple (analysis, timeframe, instrument, direction, bucket); a bucket absent from a fold (compute failure/empty slice) simply contributes one fewer fold to that bucket's wf_verdict rather than crashing"

patterns-established:
  - "New per-fold/aggregate helpers land in scripts/build_validation.py's 'Walk-forward' section, directly after slice_fold, following evaluate_fold/walk_forward_verdict's D-xx docstring convention"

requirements-completed: [WF-01]

coverage:
  - id: D1
    description: "WALK_FORWARD_FOLDS frozen 4-tuple declared in cisd_data.py and re-exported through cisd_analysis.py's explicit import list + __all__"
    requirement: "WF-01"
    verification:
      - kind: unit
        ref: "tests/test_validation_harness.py#test_walk_forward_folds_frozen_and_before_oos"
        status: pass
    human_judgment: false
  - id: D2
    description: "slice_fold confines train/test windows to the discovery region, is anchored/expanding, partitions with no overlap, and returns copies"
    requirement: "WF-01"
    verification:
      - kind: unit
        ref: "tests/test_validation_harness.py#test_slice_fold_partition_no_overlap"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_slice_fold_clamps_to_discovery_even_if_test_end_after_oos"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_slice_fold_anchored_superset"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_slice_fold_returns_copies"
        status: pass
    human_judgment: false
  - id: D3
    description: "evaluate_fold classifies a fold as pass/fail/below-n with a per-fold MIN_N gate and same-side-of-0.5 confirmation"
    requirement: "WF-01"
    verification:
      - kind: unit
        ref: "tests/test_validation_harness.py#test_evaluate_fold_pass_same_side"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_evaluate_fold_fail_opposite_side"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_evaluate_fold_below_n_test"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_evaluate_fold_below_n_train"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_evaluate_fold_train_rate_exact_half_fails"
        status: pass
    human_judgment: false
  - id: D4
    description: "walk_forward_verdict returns the majority-based aggregate (wf-robust/wf-fragile/no-folds), with the 50%-exactly boundary correctly classified as fragile"
    requirement: "WF-01"
    verification:
      - kind: unit
        ref: "tests/test_validation_harness.py#test_walk_forward_verdict_majority_pass"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_walk_forward_verdict_exact_half_is_fragile"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_walk_forward_verdict_below_n_counts_in_denominator"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_walk_forward_verdict_below_n_folds_can_tip_to_fragile"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_walk_forward_verdict_no_folds"
        status: pass
    human_judgment: false
  - id: D5
    description: "build_walkforward_rows aggregates per-fold rows into a bucket-consistent wf_verdict and performs no CSV I/O itself; --walk-forward CLI flag exists and main()'s branch writes output/validation_manifest_walkforward.csv without touching the discovery/oos manifests or the sacred OOS banner"
    requirement: "WF-01"
    verification:
      - kind: unit
        ref: "tests/test_validation_harness.py#test_build_walkforward_rows_schema_and_verdicts"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_build_walkforward_rows_never_writes_csv"
        status: pass
      - kind: other
        ref: ".venv/bin/python scripts/build_validation.py --help (lists --walk-forward)"
        status: pass
    human_judgment: false
  - id: D6
    description: "README documents both the FDR correction (06-01) and walk-forward validation (06-02) as additive methodology, without altering existing published findings"
    requirement: "WF-01"
    verification:
      - kind: other
        ref: "README.md '## Validation Methodology — Harder Evidence Bar (v2.0)' section"
        status: pass
    human_judgment: false

# Metrics
duration: 13min (this task; combined with prior crashed-session Tasks 1-2, full plan spanned the same working session)
completed: 2026-07-10
status: complete
---

# Phase 6 Plan 2: Walk-Forward Validation Summary

**Frozen 4-fold anchored walk-forward validation (`WALK_FORWARD_FOLDS`, `slice_fold`, `evaluate_fold`, `walk_forward_verdict`, `build_walkforward_rows`) wired to a `--walk-forward` CLI flag that writes `output/validation_manifest_walkforward.csv` as a purely additive sibling artifact, never touching the sacred discovery/OOS manifests.**

## Performance

- **Duration:** ~13 min for Task 3 (this resumed session); Tasks 1-2 were completed and committed by a prior executor run in the same working session before it crashed on a transient API error.
- **Started:** 2026-07-10T18:43Z (Task 1 commit, prior session)
- **Completed:** 2026-07-10T18:56Z (Task 3 commit, this session)
- **Tasks:** 3
- **Files modified:** 5 (`cisd_data.py`, `cisd_analysis.py`, `scripts/build_validation.py`, `tests/test_validation_harness.py`, `README.md`)

## Accomplishments
- Declared `WALK_FORWARD_FOLDS = ("2021-05-25", "2022-02-16", "2022-11-09", "2023-08-04")` in `cisd_data.py` — 4 frozen calendar-date fold boundaries (20th/40th/60th/80th percentile of the discovery calendar), re-exported through `cisd_analysis.py`'s explicit import list and `__all__` so `cisd_analysis.WALK_FORWARD_FOLDS` resolves.
- Added `slice_fold()` — anchored/expanding (D-05) train/test slicing that first restricts to `slice_df(df, oos=False)` so no fold can ever leak a bar from the sacred OOS region (D-04), even when `test_end` is passed after `OOS_START`.
- Added `evaluate_fold()` — per-fold pass/fail/below-n classification with an independent per-fold `MIN_N` gate on both train and test (Claude's-discretion question resolved in favor of per-fold gating) and same-side-of-0.5 confirmation logic mirroring `determine_verdict`'s framing.
- Added `walk_forward_verdict()` — majority-based (`>50%`, not `>=50%`) aggregate robustness verdict, with `below-n` folds counted in the denominator (D-07).
- Added `build_walkforward_rows()` — a pure, testable per-timeframe helper that iterates the 4 folds, slices train/test for both instruments, runs the existing `build_manifest_rows()` on each half, joins train↔test on the 5 bucket keys, scores each fold via `evaluate_fold()`, and appends a per-bucket `wf_verdict` computed via `walk_forward_verdict()` onto every fold row of that bucket. Performs no CSV I/O itself.
- Added a `--walk-forward` CLI flag (mirrors `--oos`; documented to take precedence if both flags are passed) and a `main()` branch that calls `build_walkforward_rows()` across all 4 timeframes and writes `output/validation_manifest_walkforward.csv` via `_manifest_path("walkforward")` — this branch never prints `_OOS_BANNER` and never writes `validation_manifest_discovery.csv` / `validation_manifest_oos.csv`.
- Added a `README.md` methodology section ("Validation Methodology — Harder Evidence Bar (v2.0)") documenting both the FDR correction (06-01: `bh_significant`/`corrected_pass`) and walk-forward validation (06-02: `wf_verdict`) as additive — no existing manifest column or published rate changes.

## Task Commits

Each task was committed atomically:

1. **Task 1: Frozen fold boundaries and discovery-only fold slicing** - `3b47907` (test) — completed by prior executor run
2. **Task 2: Per-fold pass evaluation and aggregate robustness verdict** - `c873ff4` (feat) — completed by prior executor run
3. **Task 3: --walk-forward CLI, walkforward manifest artifact, and methodology docs** - `a1eae17` (feat) — completed this session

_Note: the prior executor run crashed on a transient API server error immediately after committing Tasks 1-2 (not a code issue); this session verified those commits and their test coverage before resuming at Task 3._

## Files Created/Modified
- `cisd_data.py` - Declared `WALK_FORWARD_FOLDS` frozen constant, added to `__all__` (Task 1, prior session).
- `cisd_analysis.py` - Re-exported `WALK_FORWARD_FOLDS` via the explicit `from cisd_data import (...)` block and cisd_analysis's own `__all__` (Task 1, prior session).
- `scripts/build_validation.py` - Added `slice_fold`, `evaluate_fold`, `walk_forward_verdict` (Tasks 1-2, prior session); added `BUCKET_KEYS`, `build_walkforward_rows`, the `--walk-forward` CLI flag, and `main()`'s walk-forward branch writing `output/validation_manifest_walkforward.csv` (Task 3, this session).
- `tests/test_validation_harness.py` - Added fold-slicing/evaluation/aggregate-verdict tests (Tasks 1-2, prior session); added `build_walkforward_rows` schema/aggregation and no-CSV-write tests (Task 3, this session).
- `README.md` - Added the "Validation Methodology — Harder Evidence Bar (v2.0)" section covering both the FDR correction and walk-forward validation as additive (Task 3, this session).

## Decisions Made
- Fold specs are built as `zip(WALK_FORWARD_FOLDS + [OOS_START])` consecutive pairs, giving 4 `(train_end, test_end)` windows: `[b1,b2), [b2,b3), [b3,b4), [b4,OOS_START)` — matching the plan's literal fold schedule.
- `build_walkforward_rows` uses 1-based `fold_index` (1..4) for human-readable CSV output.
- The train↔test join key is the 5-tuple `(analysis, timeframe, instrument, direction, bucket)` (`BUCKET_KEYS`); a bucket missing from either half of a fold (compute failure or empty slice, handled by `build_manifest_rows`'s existing warn+skip) is simply absent from that fold's rows and contributes one fewer fold to the bucket's aggregate, rather than crashing the run.
- `--walk-forward` is checked first in `main()` and returns before the `args.oos` branch, so it structurally cannot both consume the sacred OOS slice and run walk-forward in the same invocation; the `--oos` flag's help text documents that it is ignored when `--walk-forward` is also passed.

## Deviations from Plan

None - Task 3 executed exactly as specified in the plan's `<action>`/`<verify>`/`<acceptance_criteria>` blocks. `build_walkforward_rows` was factored out per the plan's own explicit allowance ("If a full end-to-end `main()` run is impractical to unit-test, factor the per-bucket fold-aggregation into a testable helper").

## Issues Encountered
- The prior executor run crashed mid-response after committing Tasks 1-2 due to a transient API server error (not a code defect). This session re-verified the existing commits (`3b47907`, `c873ff4`) and their test coverage (`.venv/bin/python -m pytest tests/test_validation_harness.py -q` — 41/41 passing before this session's changes) before resuming at Task 3, per the resumption instructions.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `output/validation_manifest_walkforward.csv` (schema: `analysis, timeframe, instrument, direction, bucket, fold_index, train_end, test_end, train_rate, train_n, test_rate, test_n, fold_verdict, wf_verdict`) is available once `python3 scripts/build_validation.py --walk-forward` is run against real data.
- Phase 6 is now complete: both MHT-01 (06-01) and WF-01 (06-02) are delivered. Phase 7's corrected re-validation of `post_cisd_context` and `candle1_followthrough` can read both `corrected_pass` (FDR) and `wf_verdict` (walk-forward) as the harder evidence bar, once the harness is re-run against real data (not part of this plan's scope — only the pure functions, CLI wiring, and unit/characterization tests were added/verified here).
- The full pre-existing test suite (`.venv/bin/python -m pytest tests/ -q`, ~22-28 min) was not re-run in this session per the project's long-job pacing convention (only `tests/test_validation_harness.py` — the file this plan modifies — was run, and passed 43/43). Recommend running the full suite once at phase-completion / milestone-closeout per the plan's own `<verification>` section.

---
*Phase: 06-harder-evidence-bar-multiple-comparisons-correction-walk-for*
*Completed: 2026-07-10*

## Self-Check: PASSED

- FOUND: scripts/build_validation.py
- FOUND: tests/test_validation_harness.py
- FOUND: README.md
- FOUND: cisd_data.py
- FOUND commit: 3b47907
- FOUND commit: c873ff4
- FOUND commit: a1eae17
- CONFIRMED: `.venv/bin/python -m pytest tests/test_validation_harness.py -q` — 43 passed
- CONFIRMED: `.venv/bin/python scripts/build_validation.py --help` lists `--walk-forward`
