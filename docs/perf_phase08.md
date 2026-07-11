# Phase 08 Performance Baseline — Vectorize the Enrichment/Validation Hot Path

This document tracks the before/after wall-clock for the `_annotate_cisd_research`
/ `_annotate_swing_smt_from_events` vectorization work in Phase 08. Plan 08-01 is
the behavior-lock wave (no production code changes); this section records the
"before" baseline. Plan 08-03 will fill in "## After" once the vectorized code
lands, using the same measurement methodology (see note below).

## Before (pre-vectorization, Phase 08 baseline)

**Source:** This baseline is adopted from Phase 7's already-completed real-data
regeneration rather than re-measured in Plan 08-01, per explicit user-approved
deviation (see `.planning/phases/08-performance-vectorize-the-enrichment-validation-hot-path/08-01-SUMMARY.md`
for the full rationale). The golden fixtures captured in this same plan are
gzips of the exact manifests produced by that Phase 7 regeneration, so the
timing and the fixtures come from the same run.

Cited from `.planning/phases/07-corrected-re-validation-of-the-post-cisd-studies/07-03-SUMMARY.md`:

- **3-manifest regeneration (discovery + `--oos` + `--walk-forward`):**
  - **~24 min wall-clock** when the three `scripts/build_validation.py`
    invocations are run as **three concurrent OS processes** (this is the
    PARALLEL measurement — the three runs are mutually independent: disjoint
    output files, `--walk-forward` never touches the discovery/OOS manifest
    paths).
  - **~60 min wall-clock estimate** if run **sequentially** (one process at a
    time, summing the three individual invocations).
- **Full test suite:** ~22–28 min (`.venv/bin/python -m pytest tests/ -q`).
  Phase 7's own suite run: 189 passed in 1274.61s (21m14s).
- **Sanity check (D-10):** the pre-existing (pre-vectorization) analyses'
  `rate` / `successes` / `n` were confirmed byte-identical across that
  regeneration — 752/752 bucket-rows matched, 0 drift. This is independent
  confirmation that the current code's output is stable and reproducible,
  which is exactly the property this phase's golden fixtures depend on.

**IMPORTANT — apples-to-apples methodology note for Plan 08-03:** The
`~24 min` figure above is the **PARALLEL** (concurrent 3-process) measurement,
not a sequential one. For a fair before/after comparison, Plan 08-03 must
either:
1. Measure "after" the same way (three concurrent OS processes), and compare
   against this ~24 min parallel "before", OR
2. Record **both** parallel and sequential numbers for "after" so the
   comparison is apples-to-apples regardless of which methodology is used
   (this baseline provides both: ~24 min parallel / ~60 min sequential
   estimate).

### Golden fixture row counts (captured in this plan, Task 1)

These gzipped fixtures are exact copies of the manifests produced by the
Phase 7 regeneration cited above (`cisd_data.py` and `scripts/build_validation.py`
were both clean/unchanged at golden-capture time, and their last commits
predate the manifests, so the manifests are provably the current code's
output):

| Fixture | Rows | Columns | Source |
|---|---|---|---|
| `tests/golden/manifest_discovery_golden.csv.gz` | 944 | 18 | `output/validation_manifest_discovery.csv` |
| `tests/golden/manifest_oos_golden.csv.gz` | 944 | 14 | `output/validation_manifest_oos.csv` |
| `tests/golden/manifest_walkforward_golden.csv.gz` | 3776 | 14 | `output/validation_manifest_walkforward.csv` |

Each golden `.csv.gz` was verified to be byte-for-byte equal (via
`pandas.testing.assert_frame_equal`, no manual edits) to the on-disk manifest
it was gzipped from.

### Environment

- Python: `.venv/bin/python --version` → **Python 3.12.3**
- pandas: 3.0.2 (per project Technology Stack doc)
- Machine: local WSL2 (Linux 6.18.33.2-microsoft-standard-WSL2), same
  environment used for the Phase 7 regeneration cited above.

## After

_(Placeholder — to be filled in by Plan 08-03 after the vectorized
`_annotate_cisd_research` / `_annotate_swing_smt_from_events` land. Must
report both the per-manifest wall-clock using the SAME methodology as
"Before" — i.e., three concurrent OS processes for the parallel figure,
plus a sequential figure if available — and confirm the regenerated
manifests are bit-identical to the golden fixtures above via
`tests/test_perf_characterization.py` run with `CISD_PERF_CHAR=1`.)_
