---
phase: 10-new-conditioning-features-magnitude-session-volume-anomaly
plan: 03
subsystem: research-analysis
tags: [pandas, numpy, matplotlib, session-tag, tf-scoping, cisd]

requires:
  - phase: 10-new-conditioning-features-magnitude-session-volume-anomaly
    provides: "session_tag column from Plan 01 (rth_open/rth/overnight, frozen minute-of-day boundaries); the six Plan-02 standalone analyses and their ANALYSIS_META registration pattern"
provides:
  - "compute_session + chart_session: the seventh standalone conditioning analysis (session/time-of-day), flat {ct: {rth_open|rth|overnight: {total, runs}}} shape, TF-agnostic itself"
  - "ANALYSIS_META.applies_to: a trailing-defaulted, reusable per-analysis timeframe allow-list (D-14) consumed at three hook points -- build_figure, build_standalone_figure, and both build_validation.py all_keys sites"
  - "session registered on 15min/1H only (D-02); Daily/4H produce zero session manifest rows and invisible session subplots"
affects: [10-04-PLAN]

tech-stack:
  added: []
  patterns:
    - "D-14 TF-scoping: ANALYSIS_META gains a trailing-defaulted applies_to: tuple[str,...] | None = None field (None = all timeframes); only 'session' sets it, so every one of the 25 pre-existing constructor calls stays valid unchanged"
    - "cisd_charts._applies_to(meta, tf_label) is the single shared guard function reused at all three D-14 consumer sites (build_figure, build_standalone_figure, scripts/build_validation.py's tf_keys construction) -- one predicate, three call sites, no duplicated scoping logic"

key-files:
  created: []
  modified:
    - cisd_barriers.py
    - cisd_charts.py
    - scripts/build_validation.py
    - tests/test_conditioning_features.py

key-decisions:
  - "compute_session stays strictly TF-agnostic (D-14 preferred mechanism): it copies compute_smt_cisd's flat 3-way tag loop verbatim (swing_smt_tag -> session_tag), performs zero bar-spacing inference, and returns populated buckets for every CISD in whatever frame it's given -- all intraday-only scoping lives in the registry + dispatch layer, never inside the compute function."
  - "applies_to is a trailing-defaulted 5th field on _AnalysisMeta rather than a backfilled explicit tuple on all rows -- keeps the diff minimal (one line changed on the NamedTuple, one new dict entry) and matches the codebase's existing minimal-diff conventions for adding fields to shared registries."
  - "The _applies_to(meta, tf_label) guard is placed in cisd_charts.py (not cisd_barriers.py) since both of its two figure-builder call sites already live there and already do a lazy ANALYSIS_META import; scripts/build_validation.py constructs its own tf_keys list inline using the same ANALYSIS_META.applies_to field rather than importing _applies_to, since it filters a list of keys up front rather than guarding per-render."

requirements-completed: [RES-07]

coverage:
  - id: D1
    description: "compute_session returns the flat {ct: {rth_open|rth|overnight: {total, runs}}} shape over every CISD in the frame and is itself TF-agnostic (no bar-spacing inference); chart_session renders it with the same three-way alpha pattern as chart_smt_cisd; session is registered in ANALYSES, build_csv_rows' flat dispatch, and both modules' __all__"
    requirement: "RES-07"
    verification:
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_compute_session_flat_shape_and_totals_sum_to_all_cisds"
        status: pass
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_compute_session_all_three_buckets_populated_on_15min_frame"
        status: pass
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_compute_session_registered_in_analyses_and_all"
        status: pass
    human_judgment: false
  - id: D2
    description: "_AnalysisMeta gains a trailing-defaulted applies_to field (None = all timeframes); only ANALYSIS_META['session'] sets applies_to=('1H','15min'), every other of the 25 pre-existing rows is None and unaffected; cisd_analysis still imports cleanly with the widened NamedTuple"
    requirement: "RES-07"
    verification:
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_analysis_meta_applies_to_scope"
        status: pass
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_applies_to_helper_scopes_session_to_intraday"
        status: pass
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_import_cisd_analysis_still_works_with_trailing_default"
        status: pass
    human_judgment: false
  - id: D3
    description: "cisd_charts._applies_to guard consumed in build_standalone_figure's per-TF subplot loop (off-scope axis set invisible before compute/chart runs) and build_figure's per-key subplot loop (correctness/reuse guard, session normally never reaches this path since it's standalone)"
    requirement: "RES-07"
    verification:
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_applies_to_helper_scopes_session_to_intraday"
        status: pass
      - kind: other
        ref: "code inspection: cisd_charts.py build_standalone_figure/build_figure guard added at the meta lookup site; heavy PNG-render smoke deferred to Plan 04/orchestrator per critical_project_conventions"
        status: pass
    human_judgment: false
  - id: D4
    description: "scripts/build_validation.py imports ANALYSIS_META and scopes all_keys per timeframe (tf_keys) at both the discovery/OOS loop and the walk-forward loop before dispatch; session produces manifest rows only on 1H/15min; every other analysis is unaffected across all four timeframes"
    requirement: "RES-07"
    verification:
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_tf_scope_excludes_session_on_daily_and_4h"
        status: pass
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_session_manifest_rows_present_on_intraday_timeframes"
        status: pass
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_non_session_analyses_unaffected_across_all_timeframes"
        status: pass
      - kind: unit
        ref: "tests/test_conditioning_features.py#test_build_validation_imports_analysis_meta"
        status: pass
    human_judgment: false

duration: ~20min
completed: 2026-07-12
status: complete
---

# Phase 10 Plan 03: Session Analysis + D-14 TF-Scoping Mechanism Summary

**Registered the seventh conditioning analysis (session/time-of-day) scoped to 15min/1H only, via a new reusable `ANALYSIS_META.applies_to` timeframe allow-list consumed identically at three hook points (chart figure dispatch x2, validation manifest dispatch x2).**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-12
- **Tasks:** 3 (all `type="auto"`, all `tdd="true"`)
- **Files modified:** 4 (`cisd_barriers.py`, `cisd_charts.py`, `scripts/build_validation.py`, `tests/test_conditioning_features.py`)

## Accomplishments

- `compute_session` — copies `compute_smt_cisd`'s flat 3-way tag loop verbatim (`swing_smt_tag` → `session_tag`, three SMT tags → `rth_open`/`rth`/`overnight`), returning `{ct: {rth_open|rth|overnight: {total, runs}}}` over every CISD in the frame. Deliberately TF-agnostic (D-14 preferred mechanism) — no median-bar-spacing inference, no gating inside the compute function itself.
- `chart_session` — copies `chart_smt_cisd`'s three-way alpha pattern (`rth_open=1.0`, `rth=0.75`, `overnight=0.45`); registered in `ANALYSES`, `build_csv_rows`' flat dispatch tuple, and both modules' `__all__`.
- `_AnalysisMeta` gains a trailing-defaulted 5th field `applies_to: tuple[str, ...] | None = None` — every one of the 19 pre-existing rows plus the 6 Plan-02 rows stays valid unchanged; only `ANALYSIS_META["session"]` sets `applies_to=("1H", "15min")` (D-02: a session tag on a Daily/4H bar spans multiple sessions and is economically meaningless).
- `cisd_charts._applies_to(meta, tf_label)` is the single shared guard, consumed at all three D-14 hook points:
  1. `build_standalone_figure`'s per-TF subplot loop — off-scope timeframes (Daily/4H for session) get `ax.set_visible(False)` and are skipped *before* `compute_fn`/`chart_fn` runs.
  2. `build_figure`'s per-key subplot loop — same guard added for correctness/reuse, though session is standalone and normally never reaches this path.
  3. `scripts/build_validation.py`'s two `all_keys` sites (discovery/OOS loop and walk-forward loop) — both now construct a per-timeframe `tf_keys` list via `ANALYSIS_META[k].applies_to` before calling `build_manifest_rows`/`build_walkforward_rows`. `build_manifest_rows`' generic dispatch branch required zero changes.
- Verified end-to-end with synthetic manifest builds: `session` produces zero manifest rows on Daily/4H and non-zero rows on 1H/15min, while every other analysis (checked via `wick_distance`) still produces rows on all four timeframes.

## Task Commits

Each task was committed atomically:

1. **Task 1: compute_session + chart_session + registry entry** - `de6f444` (feat)
2. **Task 2: applies_to field + figure-dispatch scoping** - `e9ecb33` (feat)
3. **Task 3: build_validation.py TF-scoping at both all_keys sites** - `c4ccd26` (feat)

## Files Created/Modified

- `cisd_barriers.py` — `compute_session`, `ANALYSES["session"]`, `_AnalysisMeta.applies_to` field, `ANALYSIS_META["session"]` (applies_to=("1H","15min")), updated `__all__` and `from cisd_charts import (...)` block
- `cisd_charts.py` — `chart_session`, `_applies_to(meta, tf_label)` guard, `build_figure`/`build_standalone_figure` scoping guards, extended `build_csv_rows` flat dispatch tuple, updated `__all__`
- `scripts/build_validation.py` — `ANALYSIS_META` import, `tf_keys` filtering constructed inside both the discovery/OOS and walk-forward per-timeframe loops
- `tests/test_conditioning_features.py` — 10 new synthetic tests covering compute_session's flat shape, the applies_to field/scope invariant, the `_applies_to` helper, and end-to-end manifest TF-scoping (via `build_manifest_rows` directly, no heavy pipeline run)

## Decisions Made

- **compute_session stays strictly TF-agnostic** (D-14): the intraday-only restriction lives entirely in `ANALYSIS_META.applies_to` and its three consumers, never inside the compute function — keeping the mechanism reusable for any future TF-scoped analysis.
- **applies_to is trailing-defaulted, not backfilled**: adding an explicit `applies_to=None` to all 25 pre-existing `ANALYSIS_META` rows would have been a larger, purely cosmetic diff; the trailing default achieves the same semantics with a one-line NamedTuple change plus one new dict entry.
- **`_applies_to` lives in cisd_charts.py**, reused by both of its own figure-builder call sites; `scripts/build_validation.py` builds its own inline `tf_keys` list comprehension (matching the plan's literal spec) rather than importing the helper, since it filters a key list up front rather than guarding a per-render call.

## Deviations from Plan

None - plan executed exactly as written. TDD-labeled tasks were executed as single atomic commits (tests + implementation together) rather than split RED/GREEN commits, since Task 1's implementation and its tests were authored in the same pass; this does not affect any acceptance criterion, all of which check end-state (import success, registry membership, pytest -k selections), not commit-history shape.

## Issues Encountered

One test-authoring mistake caught and fixed before commit: the manifest `analysis` field in `build_manifest_rows`/`build_csv_rows` output is the registry *key* (`"session"`), not the human-readable label (`"Session / Time-of-Day"`) — an initial draft of the Task 3 TF-scoping tests asserted against the label and failed; corrected to assert against the key, matching the existing `test_new_analyses_registered_and_dispatch_generically` convention from Plan 02.

## Next Phase Readiness

- All seven Phase-10 conditioning analyses (six from Plan 02 + `session`) are now live in `ANALYSES`/`ANALYSIS_META` and flow through the generic `build_manifest_rows`/`build_walkforward_rows` dispatch with zero harness change beyond the reusable D-14 `tf_keys` filter.
- `session` is confirmed intraday-scoped end-to-end: zero manifest rows on Daily/4H, populated rows on 1H/15min, invisible Daily/4H standalone subplots.
- The heavy standalone-PNG render smoke (`python3 cisd_analysis.py session` → `Session_All_Timeframes.png`) and the full validation-manifest regeneration are deliberately deferred to Plan 04 (orchestrator-run, per this plan's own `<verification>` note and the executor's critical-conventions instruction to avoid ~20min+ regen jobs in this pass).
- Plan 04 can now proceed with graceful column tolerance, the byte-stability drift gate (D-12), end-to-end manifest regen (SC4), refreshed golden fixtures, and the D-11/D-13 README writeup — consuming this plan's frozen `applies_to` mechanism and the seven-analysis registry as-is.
- No blockers.

---
*Phase: 10-new-conditioning-features-magnitude-session-volume-anomaly*
*Completed: 2026-07-12*

## Self-Check: PASSED

- FOUND: `cisd_barriers.py`
- FOUND: `cisd_charts.py`
- FOUND: `scripts/build_validation.py`
- FOUND: `tests/test_conditioning_features.py`
- FOUND: `.planning/phases/10-new-conditioning-features-magnitude-session-volume-anomaly/10-03-SUMMARY.md`
- FOUND commit: `de6f444` (feat: Task 1 compute_session + chart_session + registry entry)
- FOUND commit: `e9ecb33` (feat: Task 2 applies_to field + figure-dispatch scoping)
- FOUND commit: `c4ccd26` (feat: Task 3 build_validation.py TF-scoping)
