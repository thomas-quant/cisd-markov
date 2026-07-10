---
phase: 4
plan: "04-01"
subsystem: "core"
tags: [refactor, modular, god-file-split, re-export-shim]
dependency_graph:
  requires: []
  provides: [cisd_data, cisd_barriers, cisd_charts, cisd_analysis-shim]
  affects: [all-consumers-of-cisd_analysis]
tech_stack:
  added: []
  patterns: [re-export-shim, lazy-import-for-cycle-breaking, module-level-monkeypatch-compatibility]
key_files:
  created:
    - cisd_data.py
    - cisd_barriers.py
    - cisd_charts.py
  modified:
    - cisd_analysis.py
decisions:
  - "D-01 implemented: cisd_analysis.py is an explicit named re-export shim covering all symbols imported by scripts/ and tests/; zero changes required in 6 test files or 2 scripts"
  - "prepare_pair defined in cisd_analysis.py (not just re-exported) to preserve monkeypatching compatibility of _scan_swing_smt_events in test_swing_smt_integration"
  - "cisd_barriers imports chart_* from cisd_charts at module level; cisd_charts imports ANALYSES lazily inside builder functions (build_figure/build_standalone_figure/build_csv_rows) to break the potential circular dependency"
metrics:
  duration: "~30m"
  completed: "2026-06-14T02:13:05Z"
  tasks_completed: 3
  files_created: 3
  files_modified: 1
---

# Phase 4 Plan 01: Split god-file into cisd_data / cisd_barriers / cisd_charts with a thin re-export shim

Split the 1,380-line monolithic `cisd_analysis.py` into three focused modules (`cisd_data`, `cisd_barriers`, `cisd_charts`) and a thin re-export shim + CLI orchestrator — zero behavioral change, all 89 tests green.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 04-01-01 | Create cisd_data.py with data/enrichment layer | c159e7b | cisd_data.py |
| 04-01-02 | Create cisd_barriers.py and cisd_charts.py | 634495d | cisd_barriers.py, cisd_charts.py |
| 04-01-03 | Rewrite cisd_analysis.py as re-export shim + main() | cd1acca | cisd_analysis.py |

## What Was Built

**cisd_data.py** — Data loading, resampling, enrichment, and SMT helpers:
- All config constants (LOOKAHEAD, MAX_CONSEC, OOS_START, MIN_N, CI_LEVEL, DATA_DIR, INSTRUMENTS, TIMEFRAMES, SMT_LOOKBACK, FVG_HOLD_LOOKAHEAD, SWEEP_TOLERANCE, SWEEP_SWING_LOOKBACK, _SMT_PKG_PATH)
- load_1m, resample_ohlcv, prepare, _annotate_cisd_research, prepare_pair, and all SMT helpers
- No matplotlib dependency — headless-safe

**cisd_barriers.py** — Barrier logic and compute layer:
- barrier_hit, _count_consecutive
- All 14 compute_* functions (compute_basic through compute_sssf_swing)
- ANALYSES registry (14 entries)
- Imports LOOKAHEAD/MAX_CONSEC from cisd_data; imports chart_* from cisd_charts

**cisd_charts.py** — Rendering layer:
- matplotlib rcParams block, COLORS dict, pv, _bar_label, _style_ax, _standalone_lookahead_caption
- All 14 chart_* functions
- build_figure, build_standalone_figure, build_csv_rows
- Imports ANALYSES lazily inside builder functions (avoids circular import with cisd_barriers)

**cisd_analysis.py** (rewritten) — Re-export shim + CLI:
- Explicit named imports from all three modules (auditable)
- prepare_pair defined here (not re-exported) for monkeypatch compatibility
- main() with STANDALONE_KEYS and FILENAMES inline (consolidated in 04-02)
- Zero compute_ or chart_ function definitions remain

## Import Chain (one-directional, no cycles)

```
cisd_analysis -> cisd_data          (data functions)
cisd_analysis -> cisd_barriers      (compute functions, ANALYSES)
cisd_analysis -> cisd_charts        (chart functions, builders)
cisd_barriers -> cisd_charts        (chart_* for ANALYSES registry)
cisd_barriers -> cisd_data          (LOOKAHEAD, MAX_CONSEC)
cisd_charts   -> cisd_data          (LOOKAHEAD, MAX_CONSEC, FVG_HOLD_LOOKAHEAD, TIMEFRAMES)
cisd_charts   -> cisd_barriers      (ANALYSES, lazy import inside builder functions)
```

## Verification Results

- `pytest tests/` — 89 passed, 5 skipped (data-absent CI skips), 0 failed
- All 7 script importers resolve through the shim without modification
- `len(cisd_barriers.ANALYSES) == 14` confirmed
- No circular import errors
- No compute_ or chart_ definitions remain in cisd_analysis.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] prepare_pair defined in cisd_analysis.py rather than re-exported**
- **Found during:** Task 3 (pytest run)
- **Issue:** `test_prepare_pair_aligns_misaligned_resampled_frames` uses `monkeypatch.setattr(cisd_analysis, "_scan_swing_smt_events", fake_scan)`. After refactoring, if `prepare_pair` is re-exported from `cisd_data`, the monkeypatch only affects `cisd_analysis._scan_swing_smt_events` but `prepare_pair` in `cisd_data` calls `_scan_swing_smt_events` from `cisd_data`'s namespace — the patch is invisible to it. The test would fail with `KeyError: 'nq_index'`.
- **Fix:** Define `prepare_pair` in `cisd_analysis.py` (not just re-export it from `cisd_data`) so it calls `_scan_swing_smt_events` from `cisd_analysis`'s module namespace, which monkeypatch reaches. `cisd_data.prepare_pair` still exists (the Task 1 acceptance criterion is satisfied) as the canonical implementation. The plan's "D-01: zero changes required in 6 test files" constraint is preserved.
- **Files modified:** cisd_analysis.py
- **Commit:** cd1acca

## Known Stubs

None — all functions are fully implemented, all tests pass.

## Threat Flags

None — this is a pure structural refactor with no new network endpoints, auth paths, or schema changes.

## Self-Check: PASSED

- `cisd_data.py` exists: FOUND
- `cisd_barriers.py` exists: FOUND
- `cisd_charts.py` exists: FOUND
- `cisd_analysis.py` modified: FOUND
- Commit c159e7b exists: FOUND
- Commit 634495d exists: FOUND
- Commit cd1acca exists: FOUND
- pytest 89 passed, 5 skipped, 0 failed: CONFIRMED
