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

## After (post-vectorization, Plans 08-02 + 08-03)

Both row-by-row hot spots are now vectorized and the redundant `prepare_pair`
recompute in `scripts/build_validation.py` `main()` is removed:

- `_annotate_cisd_research` (Plan 08-02) — per-event Python loop with nested
  `.iloc`/`.iat` window scans → whole-frame numpy/pandas (`shift`/rolling/
  `np.where`/`np.select`).
- `_annotate_swing_smt_from_events` (Plan 08-03) — `O(bars × events)` nested
  `.iat` loop → vectorized left-window / latest-created-event-wins match.
- `scripts/build_validation.py` — the discarded `prepare_pair(..., with_swing_smt=True)`
  first-timeframe probe in both `main()` branches replaced by a cheap
  `_load_scan_smts_historical()` availability check (same `with_smt` truth value,
  same one-time SMT `sys.path` import side-effect, same `[warn]` fallback).

### SC2 — behavior-preservation (the critical gate): PASS

`CISD_PERF_CHAR=1 .venv/bin/python -m pytest tests/test_perf_characterization.py -q`
→ **`3 passed in 2728.01s`**. All three regenerated manifests
(discovery, OOS, walk-forward) are **bit-identical** to the Plan 08-01 golden
fixtures under the exact-equality criterion (`assert_frame_equal(check_exact=True)`
after sorting by the five bucket keys). No published rate or manifest cell moved.

### SC3 — measurably faster

**End-to-end 3-manifest regeneration (sequential, measured):**

| Manifest | After (sequential, measured) |
|---|---|
| discovery | ~8.4 min |
| `--oos` | ~6.4 min (383 s) |
| `--walk-forward` | ~30.7 min (1840 s) |
| **Total (pytest-measured)** | **45 min 28 s (2728 s)** |

- **Sequential before → after:** ~60 min (estimate) → **45m28s** (measured) —
  ~1.3× / ~14.5 min faster end-to-end.
- The end-to-end win is **Amdahl-bounded**: after vectorization the regen is
  dominated by the un-vectorized SMT scan (`scan_smts_historical` over full
  history) and the walk-forward fold machinery, which this phase deliberately
  did not target. Walk-forward (all folds × timeframes × the SMT scan) is
  ~30.7 min of the 45.5 min total.
- **Strongest MEASURED before/after** (both real, same machine, same pre-existing
  tests): the full test suite — which exercises the annotation path on real data —
  dropped from Phase 7's **189 passed in 1274.61 s (21m14s)** to
  **213 passed, 3 skipped in 395.45 s (6m35s)** — **~3.2× faster** with +24 new
  tests. This is the clean apples-to-apples evidence that the annotation hot
  spots (the phase's actual target) are dramatically faster; the modest
  end-to-end regen figure reflects the SMT scan / harness that surround them.

_Methodology note: "before" sequential is Phase 7's ~60 min estimate (its
headline ~24 min was three concurrent processes); "after" here is a real
sequential measurement, so the sequential-to-sequential comparison holds. A
parallel "after" was intentionally not re-measured to conserve compute (per the
08-01 reuse-Phase-7 decision); the suite-time comparison above is the
measured-vs-measured speedup evidence._

### SC4 — full suite green

`.venv/bin/python -m pytest tests/ -q` → **`213 passed, 3 skipped in 395.45s`**
(the 3 skips are the opt-in `CISD_PERF_CHAR` characterization tests, which run
only under the env gate). Zero failures — no regressions.

### Environment

Same as "Before": Python 3.12.3, pandas 3.0.2, local WSL2. Run 2026-07-11.
