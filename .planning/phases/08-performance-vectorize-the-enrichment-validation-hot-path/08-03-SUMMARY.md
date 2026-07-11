---
phase: 08-performance-vectorize-the-enrichment-validation-hot-path
plan: 03
subsystem: enrichment-pipeline
tags: [pandas, numpy, vectorization, searchsorted, performance, behavior-preserving, smt]

requires:
  - phase: 08-performance-vectorize-the-enrichment-validation-hot-path
    plan: 01
    provides: "tests/golden/manifest_*_golden.csv.gz + tests/test_perf_characterization.py (the CISD_PERF_CHAR gate) + docs/perf_phase08.md 'before' baseline — the authoritative bit-equality reference this plan proves against."
  - phase: 08-performance-vectorize-the-enrichment-validation-hot-path
    plan: 02
    provides: "vectorized _annotate_cisd_research — the first hot spot; this plan vectorizes the second and runs the combined end-to-end proof over both."
provides:
  - "cisd_data.py::_annotate_swing_smt_from_events vectorized (per-direction stable-sort + searchsorted) producing byte-identical has_swing_smt / swing_smt_tag / swing_smt_match_ts / swing_smt_role."
  - "scripts/build_validation.py — redundant first-timeframe prepare_pair SMT probe removed in both main() branches; with_smt truth-value + one-time SMT sys.path import side-effect preserved."
  - "Authoritative SC2 proof: all three manifests (discovery, OOS, walk-forward) regenerated from the fully-vectorized code are bit-identical to the Plan 08-01 golden."
affects: []

tech-stack:
  added: []
  patterns:
    - "A per-bar 'scan every event, keep the last same-direction one whose created_ts is in [index[idx-2], index[idx]]' loop is exactly a per-direction stable-sort-by-created_ts + `searchsorted(event_ts, bar_ts, side='right') - 1` (rightmost event <= bar) gated by `candidate_ts >= lower_window_ts`. A STABLE (mergesort) sort makes tied created_ts land on the last tied event, reproducing the original unconditional-overwrite tie outcome to the bit."
    - "An availability probe must call the cheapest thing that reproduces the exact success/failure surface — `_load_scan_smts_historical()` raises the identical `FileNotFoundError`/`ImportError` and performs the identical one-time sys.path insert as a full `prepare_pair(..., with_swing_smt=True)`, so it is a drop-in probe with none of the wasted resample+prepare+scan."

key-files:
  created: []
  modified:
    - cisd_data.py
    - scripts/build_validation.py
    - docs/perf_phase08.md

key-decisions:
  - "Task 3 (the authoritative end-to-end proof) was completed directly by the orchestrator rather than the plan executor: the executor correctly implemented + committed Tasks 1 and 2 but mismanaged the long-running (~45 min sequential) SC2 regen — it launched the regen as a background job and returned prematurely (only the discovery manifest had regenerated). The orchestrator re-ran the canonical `CISD_PERF_CHAR=1` gate to completion in one clean pass. This mirrors the Phase 7 precedent of the orchestrator running pure existing-script execution directly."
  - "The 'before' baseline is Phase 7's sequential estimate (~60 min); the 'after' 45m28s is a real sequential measurement of the same 3-manifest regen, so the sequential-to-sequential comparison holds. A parallel 'after' was intentionally NOT re-measured (per the 08-01 reuse-Phase-7 decision to conserve compute). The clean MEASURED before/after is the full suite: 21m14s (189 tests, Phase 7) -> 6m35s (213 tests, now) = ~3.2x on the annotation-exercising workload."

requirements-completed: [PERF-01]

coverage:
  - id: D1
    description: "SC1 — both hot spots vectorized: _annotate_swing_smt_from_events (this plan) and _annotate_cisd_research (08-02); redundant prepare_pair recompute removed in both build_validation.py main() branches."
    requirement: PERF-01
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/test_swing_smt_integration.py tests/test_vectorization_parity.py tests/test_validation_harness.py -q — 79 passed (left-window/role, latest-wins ties, ValueError guards, harness unaffected)"
        status: pass
    human_judgment: false
  - id: D2
    description: "SC2 — the three regenerated manifests (discovery, OOS, walk-forward) are bit-identical to the Plan 08-01 golden (behavior-preserving: no published number moves)."
    requirement: PERF-01
    verification:
      - kind: integration
        ref: "CISD_PERF_CHAR=1 .venv/bin/python -m pytest tests/test_perf_characterization.py -q — 3 passed in 2728.01s"
        status: pass
    human_judgment: false
  - id: D3
    description: "SC3 — end-to-end regen measurably faster: 45m28s sequential (after, measured) vs ~60 min sequential (before, est.); full suite 21m14s -> 6m35s (~3.2x, measured before/after)."
    requirement: PERF-01
    verification:
      - kind: integration
        ref: "docs/perf_phase08.md '## After' — per-manifest + total after-timing, before->after delta; SC2 fixture wall-clock 2728s vs ~60 min baseline"
        status: pass
    human_judgment: false
  - id: D4
    description: "SC4 — the full pre-existing suite passes green with no regressions."
    requirement: PERF-01
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/ -q — 213 passed, 3 skipped in 395.45s (the 3 skips are the opt-in CISD_PERF_CHAR gate)"
        status: pass
    human_judgment: false

duration: "~90min (executor Tasks 1-2 + orchestrator-completed Task 3 proof incl. ~45 min regen + ~6.5 min suite)"
completed: 2026-07-11
status: complete
---

# Phase 8 Plan 3: Vectorize `_annotate_swing_smt_from_events` + End-to-End Proof

**Vectorized the second (SMT) hot spot and removed the redundant `prepare_pair` recompute, then proved the whole phase behavior-preserving: all three validation manifests regenerated from the fully-vectorized code are bit-identical to the pre-change golden (SC2), the regen is measurably faster (SC3 — the annotation-exercising suite is ~3.2× faster, 21m14s→6m35s), and the full suite is green (SC4 — 213 passed).**

## Performance

- **Duration:** ~90 min (Tasks 1–2 by the plan executor; Task 3 authoritative proof completed by the orchestrator — ~45 min sequential regen + ~6.5 min suite)
- **Completed:** 2026-07-11
- **Tasks:** 3/3 completed
- **Files modified:** 3 (`cisd_data.py`, `scripts/build_validation.py`, `docs/perf_phase08.md`)

## Accomplishments

- **Task 1 — vectorized `_annotate_swing_smt_from_events`** (`cisd_data.py`, 91 insertions / 41 deletions): replaced the `O(bars × events)` nested `.iat` per-bar scan with, per direction, a stable (mergesort) sort of that direction's events by `created_ts` and `np.searchsorted(event_ts, bar_ts, side="right") - 1` to find the rightmost event with `created_ts <= bar_ts`, then gate it by `candidate_ts >= index[max(0, idx-2)]` (the left-only `[t-2, t]` timestamp window). The stable sort makes tied `created_ts` land on the last tied event, reproducing the original loop's unconditional-overwrite tie outcome exactly. All four output columns (`has_swing_smt`, `swing_smt_tag`, `swing_smt_match_ts`, `swing_smt_role`), the two `ValueError` guards, the empty-frame/empty-events early return, the event filtering (NaT `created_ts` / unrecognized `signal_type` dropped), and the role resolution (`swept`/`failed_to_sweep`/`none`) are preserved.
- **Task 2 — removed the redundant `prepare_pair` recompute** (`scripts/build_validation.py`): both `main()` branches previously ran a full `prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], _first_rule, with_swing_smt=True)` purely to detect SMT availability, discarding the result and redoing the first timeframe's work in the following loop. Replaced each with a direct `_load_scan_smts_historical()` call inside the same `try/except (FileNotFoundError, ImportError)`, which performs the identical path check + one-time `sys.path` insert + `from smt import scan_smts_historical` import (the same two-exception surface and the same `with_smt` truth value and `[warn]` fallback), without the wasted resample+prepare+scan.
- **Task 3 — authoritative end-to-end proof (SC2/SC3/SC4):**
  - **SC2 (bit-equality):** `CISD_PERF_CHAR=1 pytest tests/test_perf_characterization.py -q` → **3 passed in 2728.01s**. Discovery, OOS, and walk-forward manifests regenerated from the now-fully-vectorized code are byte-for-byte equal to the Plan 08-01 golden under `assert_frame_equal(check_exact=True)` (sorted by the five bucket keys). No golden was touched.
  - **SC3 (speedup):** recorded in `docs/perf_phase08.md` "## After". Sequential 3-manifest regen **45m28s** (measured) vs **~60 min** sequential baseline; per-manifest discovery ~8.4 min / OOS ~6.4 min / walk-forward ~30.7 min. The cleanest measured before/after is the full suite: **1274.61s (189 tests) → 395.45s (213 tests) ≈ 3.2×**. The end-to-end regen win is Amdahl-bounded because the un-vectorized SMT scan + walk-forward fold harness dominate the residual time (walk-forward alone is ~30.7 of the 45.5 min).
  - **SC4 (suite green):** `pytest tests/ -q` → **213 passed, 3 skipped in 395.45s** — zero failures. The 3 skips are the opt-in `CISD_PERF_CHAR` characterization tests (env-gated out of the routine suite by design).

## Task Commits

1. **Task 1: Vectorize `_annotate_swing_smt_from_events`** — `6037919` (perf)
2. **Task 2: Remove redundant `prepare_pair` SMT probe in build_validation** — `6cc09d0` (perf)
3. **Task 3: After-timing + SUMMARY + tracking** — see the docs/tracking commit below (Task 3 was proof-only: no production code change beyond the `docs/perf_phase08.md` "## After" record).

## Files Created/Modified

- `cisd_data.py` — `_annotate_swing_smt_from_events` vectorized (searchsorted); helper `_direction_for_signal_type` factored out. No other functions changed.
- `scripts/build_validation.py` — redundant probe removed in both `main()` branches; `_load_scan_smts_historical` added to the `cisd_analysis` import.
- `docs/perf_phase08.md` — "## After" section with per-manifest + total after-timing, before→after delta, the measured suite speedup, and the hot-spots-removed statement.

## Decisions Made

- **Orchestrator completed Task 3 directly.** The executor implemented and committed Tasks 1 and 2 correctly but mismanaged the long-running SC2 regen (launched it as a background job and returned before it finished — only the discovery manifest had regenerated). Rather than re-engage a confused agent, the orchestrator verified Tasks 1–2 (79 fast tests pass, import surface intact, `build_validation.main` callable) and ran the canonical `CISD_PERF_CHAR=1` gate + full suite to completion in one clean background pass. Pure existing-script execution, per the Phase 7 precedent.
- **Sequential-to-sequential SC3 comparison + measured suite corroboration.** The "before" was Phase 7's ~60 min sequential estimate; the measured "after" is sequential (the characterization fixture regenerates the three manifests in one process). A parallel "after" was not re-measured to conserve compute (08-01 reuse-Phase-7 decision). The suite time (21m14s → 6m35s) is the clean measured-vs-measured evidence.

## Deviations from Plan

- **Task 3 executed by the orchestrator, not the plan executor** (see Decisions). The work performed is exactly what the plan's Task 3 specifies — the canonical `CISD_PERF_CHAR=1` gate, the after-timing record, and the full suite — with no scope change.
- **Per-manifest "after" reported as sequential only** (not the parallel 3-process figure the plan's after_timing note offered as one option). This is the plan's explicitly-permitted alternative: the sequential figure is compared against the sequential "before", and the note's requirement for an apples-to-apples comparison is met. Parallel re-measurement was skipped by design to conserve compute.

## Issues Encountered

- The plan executor's premature return on the background regen (resolved by orchestrator takeover — see Decisions). No code defect: Tasks 1–2 were correct and the SC2 gate passed on the first complete run, confirming the swing-SMT vectorization is bit-preserving.

## User Setup Required

None.

## Next Phase Readiness

- **PERF-01 satisfied:** both row-by-row hot spots (`_annotate_cisd_research`, `_annotate_swing_smt_from_events`) are vectorized, the redundant `prepare_pair` recompute is gone, all three manifests are proven bit-identical to pre-phase, the regen is faster, and the full suite is green.
- The vectorized enrichment path is the fast footing Phases 9 (SMT geometry) and 10 (new conditioning features) build on.
- No blockers.

---
*Phase: 08-performance-vectorize-the-enrichment-validation-hot-path*
*Completed: 2026-07-11*

## Self-Check: PASSED

Verified `6037919` (cisd_data.py) and `6cc09d0` (scripts/build_validation.py) present in `git log`. Verified SC2 (`3 passed in 2728.01s`), SC3 (docs/perf_phase08.md "## After" + suite 21m14s→6m35s), and SC4 (`213 passed, 3 skipped in 395.45s`) from the recorded run logs. `cisd_barriers.py` / `cisd_charts.py` untouched; public import surface (`_annotate_swing_smt_from_events`, `prepare_pair`, `_load_scan_smts_historical`) intact.
