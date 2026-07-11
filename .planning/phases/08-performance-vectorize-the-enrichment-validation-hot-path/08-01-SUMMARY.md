---
phase: 08-performance-vectorize-the-enrichment-validation-hot-path
plan: 01
subsystem: testing
tags: [pandas, behavior-lock, golden-fixtures, characterization-testing, pytest]

requires:
  - phase: 07-corrected-re-validation-of-the-post-cisd-studies
    provides: "The real-data-regenerated output/validation_manifest_{discovery,oos,walkforward}.csv (07-03) that this plan reuses as the golden source, and the ~24min-parallel/~60min-sequential baseline timing measurement (07-03-SUMMARY.md) that this plan adopts rather than re-measuring."
provides:
  - "Three committed golden manifest fixtures (tests/golden/manifest_{discovery,oos,walkforward}_golden.csv.gz) proving the current pre-vectorization code's exact output"
  - "tests/test_vectorization_parity.py — 24 fast synthetic per-function parity locks for both hot functions, no real data required"
  - "tests/test_perf_characterization.py — env-gated (CISD_PERF_CHAR=1) end-to-end bit-equality gate against the golden fixtures"
  - "docs/perf_phase08.md — committed SC3 'before' baseline (adopted from Phase 7), with an '## After' placeholder for Plan 08-03"
affects: [08-02, 08-03]

tech-stack:
  added: []
  patterns:
    - "Golden fixtures for real-data-derived CSV outputs are gzipped and committed under tests/golden/ (never output/, which is gitignored) — mirrors the existing tests/test_characterization.py convention of committing real-data-derived golden literals inline, extended here to whole-file fixtures for bit-equality checks."
    - "Heavy end-to-end regeneration tests use a THREE-gate skip pattern (data absent / external-package absent / opt-in env var unset) so they never run in a routine `pytest tests/` invocation but remain available for explicit CISD_PERF_CHAR=1 invocation before/after a behavior-sensitive refactor."
    - "Fast synthetic parity tests for row-by-row annotation functions are authored by running the CURRENT function once on a hand-built minimal DataFrame and hard-coding the observed output — a legitimate behavior-lock technique distinct from re-deriving expected values analytically."

key-files:
  created:
    - tests/golden/manifest_discovery_golden.csv.gz
    - tests/golden/manifest_oos_golden.csv.gz
    - tests/golden/manifest_walkforward_golden.csv.gz
    - tests/test_vectorization_parity.py
    - tests/test_perf_characterization.py
    - docs/perf_phase08.md
  modified: []

key-decisions:
  - "Per explicit user-approved deviation, this plan did NOT run a fresh ~24min triple manifest regeneration to capture golden. Instead it gzipped the three manifests already on disk from Phase 7's Jul 11 regeneration (cisd_data.py and scripts/build_validation.py were both clean/unchanged and their last commits predate those manifests, so the manifests are provably the current code's output)."
  - "Per the same deviation, the SC3 'before' baseline in docs/perf_phase08.md was adopted from 07-03-SUMMARY.md (~24min parallel / ~60min sequential for the 3-manifest regen, ~22-28min test suite) rather than re-measured, with an explicit note that Plan 08-03 must measure 'after' using the same (parallel, 3-concurrent-process) methodology for a fair comparison."
  - "Per the same deviation, tests/test_perf_characterization.py was authored and confirmed to SKIP cleanly under a bare pytest invocation, but its live CISD_PERF_CHAR=1 pass (which would trigger the full ~24min regen) was deliberately NOT run in this plan — deferred to Plan 08-03's authoritative before/after proof."

patterns-established:
  - "Bit-preservation testing (check_exact=True after sorting by bucket keys) is documented as a distinct, stricter tolerance from the ±0.05pp reporting tolerance used in test_characterization.py — the two must never be conflated when writing future characterization tests."

requirements-completed: []  # PERF-01 remains open — this plan only builds the behavior-lock (golden fixtures + tests); the actual vectorization that PERF-01 requires lands in Plans 08-02/08-03, which will mark it complete.

coverage:
  - id: D1
    description: "Three golden manifest CSVs (discovery/oos/walkforward) captured from the current, unchanged code and committed as gzip fixtures under tests/golden/"
    requirement: PERF-01
    verification:
      - kind: other
        ref: "pd.testing.assert_frame_equal(golden, output/validation_manifest_*.csv) raised nothing for all three; row counts 944/944/3776 confirmed via pd.read_csv"
        status: pass
    human_judgment: false
  - id: D2
    description: "tests/test_vectorization_parity.py pins the trickier per-column semantics of both hot functions on synthetic data, no real data required"
    requirement: PERF-01
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/test_vectorization_parity.py -q — 24 passed"
        status: pass
    human_judgment: false
  - id: D3
    description: "tests/test_perf_characterization.py regenerates all three manifests and asserts exact equality vs golden; SKIPS cleanly (exit 0) when CISD_PERF_CHAR is unset, even with data+SMT present"
    requirement: PERF-01
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/test_perf_characterization.py -q — 3 skipped, exit 0 (confirmed data present, SMT present, only the CISD_PERF_CHAR env gate caused the skip)"
        status: pass
    human_judgment: false
  - id: D4
    description: "docs/perf_phase08.md records the SC3 'before' baseline (adopted from Phase 7) with golden row counts and Python version, plus an '## After' placeholder"
    verification: []
    human_judgment: true
    rationale: "The live CISD_PERF_CHAR=1 regeneration that would independently re-measure this baseline was deliberately deferred to Plan 08-03 per user-approved deviation; this deliverable's numeric accuracy rests on a citation from 07-03-SUMMARY.md rather than a fresh automated measurement in this plan, so a human should confirm the citation is applied correctly when 08-03 fills in '## After'."

duration: "~35min"
completed: 2026-07-11
status: complete
---

# Phase 8 Plan 1: Behavior-Lock — Golden Manifests + Parity/Characterization Tests Summary

**Locked the current enrichment/validation pipeline's exact output via three committed golden manifest fixtures (reused from Phase 7's real-data regeneration), 24 fast synthetic parity tests for both hot functions, and an opt-in end-to-end bit-equality gate — zero production code touched.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-07-11 (session start)
- **Completed:** 2026-07-11
- **Tasks:** 2/2 completed
- **Files modified:** 6 created (3 golden fixtures, 2 test modules, 1 doc); 0 production files touched

## Accomplishments
- Captured `tests/golden/manifest_{discovery,oos,walkforward}_golden.csv.gz` by gzipping the exact `output/validation_manifest_*.csv` files already on disk from Phase 7's Jul 11 regeneration (verified via `git log` that `cisd_data.py` and `scripts/build_validation.py` were both clean and their last commits predate those manifests). Each golden verified non-empty and byte-for-byte equal to its source manifest via `pd.testing.assert_frame_equal`. Row counts: **discovery 944×18, oos 944×14, walkforward 3776×14.**
- Authored `docs/perf_phase08.md` recording the SC3 "before" baseline adopted from `07-03-SUMMARY.md`: **~24 min parallel** (3 concurrent OS processes) / **~60 min sequential estimate** for the 3-manifest regen, **~22-28 min** full test suite, golden row counts, and the `.venv/bin/python --version` → Python 3.12.3 environment. Left an explicit methodology note that Plan 08-03 must measure "after" using the same parallel-process methodology (or record both) for a fair comparison, plus an empty "## After" placeholder heading.
- Authored `tests/test_vectorization_parity.py` — 24 fast, synthetic, no-real-data tests pinning:
  - `_annotate_swing_smt_from_events`: last-matching-event-in-window wins (later `created_ts` overwrites an earlier same-direction match), opposite-direction events ignored, events outside the `[t-2, t]` left window ignored, `swept`/`failed_to_sweep`/`none` role resolution, empty-events and empty-frame default columns.
  - `_annotate_cisd_research`: `has_dir_sweep` true/false at the `[t-4, t]` window boundary, `has_dir_fvg_mid1` + `close_near`/`wick_far` hold classifications (held / failed / none when the `FVG_HOLD_LOOKAHEAD=10` window doesn't fit), `candle1_close_dir`/`candle1_past_candle0_wick` for both bullish and bearish (with/against, past-wick true/false, `candle1_failed_followthrough`), `candle2_gap_dir` mapping (`gap_with`/`gap_against`/`flat`, both directions) + `candle2_past_candle1_wick`, and end-of-frame defaults when `idx+1` or `idx+2` is out of range.
  - All expected values were derived by running the CURRENT (unchanged) functions once during authoring and hard-coding the observed outputs.
  - Confirmed GREEN: `.venv/bin/python -m pytest tests/test_vectorization_parity.py -q` → **24 passed**.
- Authored `tests/test_perf_characterization.py` — the authoritative end-to-end bit-equality gate (SC2). Regenerates all three manifests by invoking `scripts/build_validation.py` (default / `--oos` / `--walk-forward`) via subprocess, then compares each against its `tests/golden/*.gz` fixture using `pd.testing.assert_frame_equal(check_exact=True)` after sorting both frames by the five bucket keys (`analysis, timeframe, instrument, direction, bucket`). Module docstring explicitly documents this bit-preservation criterion as distinct from `test_characterization.py`'s ±0.05pp reporting tolerance, plus a documented (unused) float-tolerance fallback.
  - Triple-gated: data absent / SMT absent / `CISD_PERF_CHAR` unset.
  - Confirmed: `.venv/bin/python -m pytest tests/test_perf_characterization.py -q` (no env var) → **3 skipped, exit 0** — verified this environment actually HAS both data and the SMT package present, so the skip is provably driven by the `CISD_PERF_CHAR` gate alone, not masked by the other two gates.
  - Per the user-approved deviation, the live `CISD_PERF_CHAR=1` pass (which would trigger the full ~24min regeneration) was NOT run in this plan — deferred to Plan 08-03's authoritative before/after proof.
- Confirmed `cisd_data.py` and `scripts/build_validation.py` remain byte-for-byte unchanged throughout this plan (`git status --short` shows no modifications to either file) — the golden fixtures and baseline provably reflect pre-vectorization behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1: Capture golden manifests from pre-change code + record baseline timing** - `9b04e7c` (test)
2. **Task 2: Author the full-manifest golden characterization test + fast synthetic parity tests** - `57dc72d` (test)

_Note: Both commits use the `test` type since all changes in this plan are test fixtures/modules and documentation — no production code was touched._

## Files Created/Modified
- `tests/golden/manifest_discovery_golden.csv.gz` - gzip of `output/validation_manifest_discovery.csv` (944 rows × 18 cols), byte-equal to source
- `tests/golden/manifest_oos_golden.csv.gz` - gzip of `output/validation_manifest_oos.csv` (944 rows × 14 cols), byte-equal to source
- `tests/golden/manifest_walkforward_golden.csv.gz` - gzip of `output/validation_manifest_walkforward.csv` (3776 rows × 14 cols), byte-equal to source
- `docs/perf_phase08.md` - SC3 "before" baseline (adopted from Phase 7), golden row counts, environment, "## After" placeholder
- `tests/test_vectorization_parity.py` - 24 fast synthetic parity tests for both hot functions
- `tests/test_perf_characterization.py` - env-gated end-to-end bit-equality gate (SC2)

## Decisions Made
- Reused Phase 7's already-captured manifests as golden instead of running a fresh ~24min regeneration, since both `cisd_data.py` and `scripts/build_validation.py` were confirmed clean and their last commits predate the manifests on disk — an explicit user-approved deviation from the plan's literal Task 1 instructions, documented in full in the "Deviations from Plan" section below.
- Adopted Phase 7's baseline timing (07-03-SUMMARY.md) as the SC3 "before" record rather than re-measuring, with an explicit methodology note for Plan 08-03 to ensure an apples-to-apples before/after comparison (same parallel-process measurement approach).
- Deferred the live `CISD_PERF_CHAR=1` regeneration pass to Plan 08-03, since the user opted to spend the one ~24min live regen on the authoritative after-vectorization proof rather than spending it twice (once here on unchanged code, once again in 08-03).
- Used `test(08-01): ...` as the commit type for both tasks since every artifact produced (golden fixtures, test modules, and the baseline doc) is test/verification infrastructure, not production code.

## Deviations from Plan

This plan followed a user-approved deviation from its literal PLAN.md instructions, communicated directly in the execution prompt (not a runtime discovery under Rules 1-4):

**1. [User-directed] Golden capture reused Phase 7's existing manifests instead of a fresh regeneration**
- **Found during:** Task 1
- **Plan said:** Run three fresh ~24-minute `scripts/build_validation.py` invocations (discovery / `--oos` / `--walk-forward`) against real data to capture golden.
- **What was done instead:** Gzipped the three manifests already on disk (`output/validation_manifest_{discovery,oos,walkforward}.csv`), produced by Phase 7's Jul 11 regeneration.
- **Why this is valid:** `git log` confirmed both `cisd_data.py` (last commit Jul 10 18:56) and `scripts/build_validation.py` (last commit Jul 10 18:56) were clean and unchanged, and both commits predate the Jul 11 manifest timestamps — so the on-disk manifests are provably the current, unchanged code's output. Each golden was independently verified byte-for-byte equal to its source manifest via `pd.testing.assert_frame_equal`.
- **Files affected:** `tests/golden/manifest_{discovery,oos,walkforward}_golden.csv.gz`
- **Commit:** `9b04e7c`

**2. [User-directed] SC3 "before" baseline cited from Phase 7 rather than freshly measured**
- **Found during:** Task 1
- **Plan said:** Measure a fresh baseline wall-clock for the 3-manifest regeneration.
- **What was done instead:** Cited `07-03-SUMMARY.md`'s already-recorded measurement (~24min parallel / ~60min sequential estimate, ~22-28min test suite) in `docs/perf_phase08.md`, with an explicit note that this is the PARALLEL (3-concurrent-process) figure and Plan 08-03 must measure "after" comparably.
- **Files affected:** `docs/perf_phase08.md`
- **Commit:** `9b04e7c`

**3. [User-directed] Live `CISD_PERF_CHAR=1` characterization pass deferred to Plan 08-03**
- **Found during:** Task 2
- **Plan said:** Confirm `CISD_PERF_CHAR=1 .venv/bin/python -m pytest tests/test_perf_characterization.py -q` PASSES on the current unchanged code.
- **What was done instead:** The test module was authored and confirmed to SKIP cleanly (`3 skipped`, exit 0) under a bare invocation, with this environment's data and SMT package both confirmed present (so the skip is provably driven by the `CISD_PERF_CHAR` env gate alone). The live env-var-enabled pass — which triggers the full ~24min regeneration — was intentionally not run here.
- **Files affected:** none (verification-only deviation)
- **Commit:** N/A (no code change; documented for transparency)

---

**Total deviations:** 3, all explicit user-directed deviations agreed before this plan began execution (not autonomous Rule 1-4 fixes).
**Impact on plan:** No scope creep — all three deviations reduce redundant ~24min real-data regeneration runs (avoiding running the same expensive regen twice across Plans 08-01 and 08-03) while preserving full provability of the golden fixtures and the adopted baseline via git history and independent equality verification.

## Issues Encountered
None. All verification commands (golden row counts, byte-equality checks, parity test suite, characterization skip confirmation) succeeded on the first attempt.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The behavior-lock is complete: `tests/golden/*.gz` fixtures, `tests/test_vectorization_parity.py` (24 passing), and `tests/test_perf_characterization.py` (correctly skipping without `CISD_PERF_CHAR`) are all committed and ready to catch any regression introduced by Plans 08-02/08-03's vectorization of `_annotate_cisd_research` / `_annotate_swing_smt_from_events`.
- `docs/perf_phase08.md` has the "## Before" baseline recorded (adopted from Phase 7) and an "## After" placeholder ready for Plan 08-03.
- No blockers. `cisd_data.py` and `scripts/build_validation.py` remain untouched, confirmed via `git status`.
- Plan 08-03 must: (1) run the vectorized code through `CISD_PERF_CHAR=1 .venv/bin/python -m pytest tests/test_perf_characterization.py -q` as the authoritative before/after proof, and (2) measure the "after" wall-clock using the same 3-concurrent-process methodology as this plan's adopted "before" baseline (or record both parallel and sequential) for an apples-to-apples comparison.

---
*Phase: 08-performance-vectorize-the-enrichment-validation-hot-path*
*Completed: 2026-07-11*

## Self-Check: PASSED

All created files verified present on disk (`tests/golden/manifest_{discovery,oos,walkforward}_golden.csv.gz`, `tests/test_vectorization_parity.py`, `tests/test_perf_characterization.py`, `docs/perf_phase08.md`). Both task commits (`9b04e7c`, `57dc72d`) verified present in `git log --oneline --all`.
