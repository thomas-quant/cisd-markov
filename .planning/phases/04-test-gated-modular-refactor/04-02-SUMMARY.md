---
phase: 4
plan: "04-02"
subsystem: "core"
tags: [refactor, registry, single-source-of-truth, analysis-meta, documentation]
dependency_graph:
  requires: [04-01]
  provides: [ANALYSIS_META-registry, documented-compute_significance, clean-csv-branch]
  affects: [cisd_barriers, cisd_charts, cisd_analysis]
tech_stack:
  added: [typing.NamedTuple]
  patterns: [single-source-of-truth-registry, NamedTuple-metadata, lazy-import-pattern]
key_files:
  created: []
  modified:
    - cisd_barriers.py
    - cisd_charts.py
    - cisd_analysis.py
decisions:
  - "ANALYSIS_META uses a NamedTuple (_AnalysisMeta) for clean attribute access and type clarity"
  - "ANALYSIS_META lives at module level in cisd_barriers.py alongside ANALYSES (natural peer)"
  - "build_figure/build_standalone_figure import ANALYSIS_META lazily (same pattern as ANALYSES) to preserve no-cycle guarantee"
  - "Dead smt_cisd build_csv_rows branch was already absent from cisd_charts.py (cleaned during 04-01 split) — acceptance criteria confirmed satisfied without additional change"
  - "compute_significance docstring enhanced from 04-01 multi-line form to fully explicit three-point form covering (a) stricter definition, (b) why cisd_type unused, (c) behavior-locked intent"
metrics:
  duration: "~15m"
  completed: "2026-06-14"
  tasks_completed: 3
  files_created: 0
  files_modified: 3
---

# Phase 4 Plan 02: Consolidate standalone-analysis registry into ANALYSIS_META and fix audit-surfaced correctness debt

ANALYSIS_META NamedTuple registry (14 keys) in cisd_barriers.py drives all four previously-synchronized sites; compute_significance docstring explicitly documents the intentional cisd_type bypass with three labelled points.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 04-02-01 | Define ANALYSIS_META and drive build_figure/build_standalone_figure from it | ee6cbce | cisd_barriers.py, cisd_charts.py |
| 04-02-02 | Drive main() STANDALONE_KEYS + FILENAMES from ANALYSIS_META | 52d46b1 | cisd_analysis.py |
| 04-02-03 | Document compute_significance's intentional cisd_type bypass | 7acd8fe | cisd_barriers.py |

## What Was Built

**ANALYSIS_META registry (cisd_barriers.py)**
- `_AnalysisMeta` NamedTuple with four fields: `per_tf_height` (int), `standalone` (bool), `standalone_height` (int | None), `filename` (str | None)
- `ANALYSIS_META` dict-of-NamedTuple at module level with all 14 analysis keys, carrying the exact values that were previously scattered across 4 sites
- Added to `__all__` and re-exported through cisd_analysis.py shim

**Refactored consumers (cisd_charts.py, cisd_analysis.py)**
- `build_figure`: replaced inline `base_h` dict with `ANALYSIS_META[k].per_tf_height` lookup (fallback-to-4 for unknown keys preserved)
- `build_standalone_figure`: replaced inline `base_h` dict with `ANALYSIS_META[key].standalone_height` (fallback-to-6 for None/unknown preserved)
- `main()` STANDALONE_KEYS: replaced 9-key set literal with `{k for k, m in ANALYSIS_META.items() if m.standalone}`
- `main()` FILENAMES: replaced 9-key dict literal with `{k: m.filename for k, m in ANALYSIS_META.items() if m.standalone}`
- Both inline `base_h = {` dicts removed from cisd_charts.py (grep -c returns 0)

**compute_significance docstring (cisd_barriers.py)**
- Expanded to three explicit labelled points: (a) stricter definition `close > prev_high` / `close < prev_low`, (b) why `cisd_type` is intentionally not consumed, (c) this divergence is behavior-locked and must not be "fixed"
- Zero executable lines changed — only the docstring block modified

## Verification Results

- `pytest tests/` — 89 passed, 5 skipped (data-absent CI skips), 0 failed
- `grep -c "base_h = {" cisd_charts.py` → 0 (both inline dicts removed)
- `grep -c '"smt_cisd"' cisd_charts.py` → 1 (live explicit branch only; dead tuple absent)
- `python3 -c "import cisd_barriers as b; assert set(b.ANALYSIS_META) == set(b.ANALYSES)"` → OK
- `python3 -c "...; assert sorted(std) == ['candle_size', 'cisd_fvg', ...]"` → OK
- `python3 -c "import cisd_barriers; d=cisd_barriers.compute_significance.__doc__; assert d and 'cisd_type' in d and 'intentional' in d.lower()"` → OK

## Deviations from Plan

### Auto-fixed Issues

None.

### Observations (Not Bugs)

**Dead smt_cisd build_csv_rows branch already absent**
- The plan said to remove `"smt_cisd"` from the `elif key in ("smt_cisd", "sweep", "sssf_swing"):` tuple in `build_csv_rows`.
- Inspection of `cisd_charts.py` (created in 04-01) revealed the tuple was never included in the split — the original dead branch from the god-file was not carried over during 04-01. The live `elif key == "smt_cisd":` branch is present and correct at line 392.
- All acceptance criteria for this sub-task were already satisfied. No change required.

## Known Stubs

None — all changes are structural (registry consolidation) or documentation only.

## Threat Flags

None — pure structural refactor and docstring addition; no new network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check: PASSED

- cisd_barriers.py modified: FOUND
- cisd_charts.py modified: FOUND
- cisd_analysis.py modified: FOUND
- Commit ee6cbce exists: FOUND
- Commit 52d46b1 exists: FOUND
- Commit 7acd8fe exists: FOUND
- pytest 89 passed, 5 skipped, 0 failed: CONFIRMED
