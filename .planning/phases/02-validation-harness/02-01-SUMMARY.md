---
phase: 02-validation-harness
plan: "01"
subsystem: validation-harness
tags: [oos-holdout, constants, slicing, testing]
dependency_graph:
  requires: []
  provides: [OOS_START, MIN_N, CI_LEVEL, slice_df, build_validation]
  affects: [tests/test_validation_harness.py, scripts/build_validation.py, cisd_analysis.py]
tech_stack:
  added: []
  patterns: [sacred-oos-soft-enforcement, wilson-ci-constants, discovery-oos-slicing]
key_files:
  created:
    - scripts/build_validation.py
    - tests/test_validation_harness.py
  modified:
    - cisd_analysis.py
decisions:
  - "OOS_START = '2024-04-30': 70th-percentile of shared NQ/ES daily calendar (n=1627, idx=1138)"
  - "MIN_N = 50 enforces a stricter-than-textbook finding bar (user chose 50 over n>=30)"
  - "Slicing on resampled frame (not 1-minute) to keep consistency with prepare_pair output"
  - "soft OOS enforcement via --oos flag + loud banner; no hard lock per D-05/D-06"
  - "slice_df returns .copy() to eliminate SettingWithCopyWarning and prevent T-02-01-03 mutation"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-12"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 3
---

# Phase 2 Plan 1: Holdout Infrastructure and Sacred OOS Slicing Summary

Implemented the sacred chronological holdout infrastructure: computed and froze OOS_START as the 70th-percentile date of the shared NQ/ES daily calendar, added MIN_N=50 and CI_LEVEL=0.95 constants to cisd_analysis.py, created scripts/build_validation.py as the harness entry point with discovery-on-train default and explicit --oos path with a loud spending-your-one-sacred-evaluation banner, and wrote 6 data-free unit tests locking the slicing contract.

## Tasks Completed

| # | Name | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Add OOS_START, MIN_N, CI_LEVEL constants | d132558 | cisd_analysis.py |
| 2 | Create scripts/build_validation.py | 2f78bbc | scripts/build_validation.py |
| 3 | Data-free unit tests for slicing contract | ee13c84 | tests/test_validation_harness.py |

## What Was Built

### cisd_analysis.py (additive constants only)

Three constants were added after `_SMT_PKG_PATH`:

- `OOS_START = "2024-04-30"` — derived from the 70th-percentile date of the 1627-bar shared NQ/ES daily calendar (idx=1138); hardcoded with a "Do NOT recompute" comment guarding against T-02-01-01 drift.
- `MIN_N = 50` — minimum sample size for a reportable finding.
- `CI_LEVEL = 0.95` — Wilson score CI confidence level for plan 02-02.

No existing compute path, function, or default code path was altered. All 67 characterization and unit tests that existed before this plan continue to pass.

### scripts/build_validation.py

New standalone harness entry point following the `scripts/build_expectancy.py` structural template:

- `slice_df(df, oos=False)` — partitions any resampled DataFrame on `OOS_START` boundary using strict `<` / `>=` semantics. Returns `.copy()` to prevent view-mutation (T-02-01-03).
- Default run (discovery): `python3 scripts/build_validation.py` — operates on `df.index < OOS_START`.
- OOS run: `python3 scripts/build_validation.py --oos` — prints the sacred-evaluation banner before loading any data, then operates on `df.index >= OOS_START`.
- SMT degrades gracefully (try/except mirrors `build_expectancy.py`).
- Writes `output/validation_slices.csv` with n_bars, start_date, end_date per timeframe/instrument/slice.
- `--help` flag confirmed working.

### tests/test_validation_harness.py

Six data-free unit tests (no parquet reads, no `_DATA_PRESENT` skip guards):

1. `test_slice_df_partition` — discovery + OOS counts sum to total; boundaries correct.
2. `test_slice_df_no_overlap` — intersection of both slices is empty.
3. `test_slice_df_all_discovery` — frame entirely before OOS_START yields empty OOS slice.
4. `test_slice_df_all_oos` — frame entirely on/after OOS_START yields empty discovery slice.
5. `test_slice_df_returns_copy` — result values array is not the same object as the source.
6. `test_oos_start_and_constants` — OOS_START is a midnight-aligned string; MIN_N==50; CI_LEVEL==0.95.

## Verification Results

- `python3 scripts/build_validation.py --help` exits 0, shows `--oos` flag.
- `python3 -c "import cisd_analysis; print(cisd_analysis.OOS_START, cisd_analysis.MIN_N, cisd_analysis.CI_LEVEL)"` prints `2024-04-30 50 0.95`.
- `grep 'sacred evaluation' scripts/build_validation.py` confirms banner text present.
- `python3 -m pytest tests/test_validation_harness.py -v` — 6 PASSED.
- `python3 -m pytest tests/ -q` — 73 passed, 5 skipped (67 pre-existing + 6 new).

## Deviations from Plan

None — plan executed exactly as written.

The only implementation note: the banner line was phrased as "This is a sacred evaluation — treat it as a final exam" (rather than the plan's all-caps "SACRED OOS EVALUATION" line) to satisfy the lowercase `grep -q 'sacred evaluation'` acceptance criterion while keeping the visually loud formatting intact.

## Known Stubs

None. The validation harness is fully wired:
- OOS_START is computed from real data and hardcoded.
- `slice_df` partitions on that constant.
- The slice-summary CSV is written on a live data run.
- Tests operate on synthetic frames (intentional — data-free CI requirement).

## Threat Flags

No new network endpoints, auth paths, or schema changes introduced. All changes are pure in-process Python. No unmitigated threats beyond the plan's STRIDE register:

- T-02-01-01 (OOS_START runtime recompute): eliminated — constant is hardcoded with "Do NOT recompute" comment.
- T-02-01-02 (accidental OOS use): mitigated — default is discovery; --oos required; loud banner on OOS.
- T-02-01-03 (slice view mutation): eliminated — `.copy()` in `slice_df`; test_slice_df_returns_copy locks it.

## Self-Check: PASSED

Files exist:
- `scripts/build_validation.py` — FOUND
- `tests/test_validation_harness.py` — FOUND
- `cisd_analysis.py` (modified) — FOUND

Commits exist:
- d132558 — FOUND (feat: add OOS_START/MIN_N/CI_LEVEL)
- 2f78bbc — FOUND (feat: create build_validation.py)
- ee13c84 — FOUND (test: data-free slicing tests)
