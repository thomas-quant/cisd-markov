---
phase: 07-corrected-re-validation-of-the-post-cisd-studies
plan: 02
subsystem: research
tags: [pandas, verdict-computation, validation-harness]

requires:
  - phase: 07-corrected-re-validation-of-the-post-cisd-studies
    provides: "07-01's failed_gap_against_reversal / failed_gap_against_neither tags (any-tag-generic rollup verified against one of them)"
provides:
  - scripts/build_post_cisd_verdict.py — _bucket_clears (D-02), rollup_by_tag (D-03), build_verdict (D-01/D-09 I/O)
  - output/post_cisd_verdict.csv and output/post_cisd_verdict_rollup.csv schemas (not yet populated with real data — that is 07-03)
affects: [07-03]

tech-stack:
  added: []
  patterns:
    - "First cross-script import in the repo: _side imported from scripts.build_reconcile_findings rather than re-implemented"

key-files:
  created:
    - scripts/build_post_cisd_verdict.py
    - tests/test_post_cisd_verdict.py
  modified: []

key-decisions:
  - "_bucket_clears and rollup_by_tag are pure functions, fully unit-tested with in-memory rows/no disk I/O, matching the test_reconcile_findings.py style"
  - "build_verdict() applies the analysis.isin(POST_CISD_ANALYSES) filter to all three manifests immediately after read, before any merge/verdict logic (D-01 blast-radius containment)"

patterns-established:
  - "Verdict rollup is generic over tag name — no special-casing for the new reversal/neither tags, proven by a dedicated test"

requirements-completed: [RES-05]

coverage:
  - id: D1
    description: "_bucket_clears implements the strict D-02 three-condition AND; rollup_by_tag implements the D-03 strict-majority per-tag roll-up"
    requirement: RES-05
    verification:
      - kind: unit
        ref: "tests/test_post_cisd_verdict.py -k 'bucket_clears or rollup' (16 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "build_verdict joins the 3 manifests, scopes strictly to post_cisd_context/candle1_followthrough (D-01), dedupes walk-forward fold rows, and writes both verdict CSVs"
    requirement: RES-05
    verification:
      - kind: integration
        ref: "tests/test_post_cisd_verdict.py::test_build_verdict_joins_scopes_deduplicates_and_writes"
        status: pass
    human_judgment: false

duration: ~5min (Codex implementation) + orchestrator verification/commit
completed: 2026-07-11
status: complete
---

# Phase 07 Plan 02: Post-CISD Verdict Script Summary

**`scripts/build_post_cisd_verdict.py` computes the D-02 strict three-condition AND per bucket and the D-03 strict-majority per-tag roll-up, scoped to only the two post-CISD studies, fully fixture-tested with zero real-data I/O.**

## Performance

- **Duration:** ~5 min Codex implementation (task-mrgew6hi-3vgr1i, 4m36s wall) + orchestrator review/commit
- **Tasks:** 2 completed
- **Files created:** 2

## Accomplishments
- `_bucket_clears(discovery_rate, corrected_pass, wf_verdict, oos_rate, oos_n) -> bool` — True only when corrected_pass is truthy AND wf_verdict == "wf-robust" AND OOS is present and on the same non-boundary side of 0.50 as discovery.
- `rollup_by_tag(bucket_rows) -> list[dict]` — one record per (analysis, tag) with n_buckets/n_cleared/verdict, "cleared" requiring strict >50% majority; generic over tag name (verified against `failed_gap_against_reversal`).
- `build_verdict()` — reads discovery/OOS/walk-forward manifests, filters to `{post_cisd_context, candle1_followthrough}` before any verdict logic (D-01), outer-merges on the 5 bucket keys, dedupes walk-forward fold rows to one per bucket, and writes `output/post_cisd_verdict.csv` + `output/post_cisd_verdict_rollup.csv`.
- Reuses `_side` from `scripts/build_reconcile_findings.py` (first cross-script import in the repo) instead of re-implementing it.
- 12 new tests in `tests/test_post_cisd_verdict.py`, including a fixture-CSV integration test proving a third-analysis row never appears in either output and that 4 walk-forward fold rows collapse to exactly 1 merged row.

## Task Commits

Both tasks landed in a single commit — see "Deviations from Plan" below.

1. **Tasks 1 + 2: verdict logic + I/O** - `4bc3ea5` (feat)

## Files Created/Modified
- `scripts/build_post_cisd_verdict.py` - `_bucket_clears`, `rollup_by_tag`, `build_verdict`, path constants, `POST_CISD_ANALYSES`
- `tests/test_post_cisd_verdict.py` - 12 tests (pure-function + fixture-CSV integration)

## Decisions Made
- Execution was delegated to Codex (`codex:codex-rescue`) per explicit user instruction to bypass `gsd-executor` for this phase; the orchestrator retained ownership of verification, committing, and `.planning/` bookkeeping.

## Deviations from Plan

### Auto-fixed Issues

**1. [Process — commit granularity] Both tasks committed as one commit instead of two**
- **Found during:** Post-implementation commit step
- **Issue:** Both files (`scripts/build_post_cisd_verdict.py`, `tests/test_post_cisd_verdict.py`) are brand new; Codex wrote Task 1's pure-logic functions and Task 2's path constants/I/O interleaved by section (not appended sequentially), so `git add -p` hunk-splitting would have required manually reordering code into an intermediate state that was never actually written or verified independently.
- **Fix:** Committed both tasks together after independently re-running the full test suite and reviewing the diff against every acceptance criterion in the plan.
- **Files modified:** none beyond the two created files
- **Verification:** `.venv/bin/python -m pytest tests/test_post_cisd_verdict.py -q` — 17 passed, independently re-run by the orchestrator (not just trusting Codex's report).
- **Committed in:** `4bc3ea5`

---

**Total deviations:** 1 auto-fixed (process only — commit granularity). No scope creep; no functional deviation from the plan.

## Issues Encountered
Codex (`codex:codex-rescue`) could not run `git commit` itself — its sandbox mounts `.git` read-only in this environment. Same as 07-01. The orchestrator verified the working-tree diff and test results, then committed directly.

## Next Phase Readiness
- `build_post_cisd_verdict.py` is implemented and fixture-tested; it has not yet been run against real manifests (07-03's deliverable, since the OOS manifest doesn't yet carry post-CISD rows and the discovery/walk-forward manifests don't yet carry the reversal buckets from 07-01).
- No blockers — 07-03 can proceed once both 07-01 and 07-02 are complete (they now are).

---
*Phase: 07-corrected-re-validation-of-the-post-cisd-studies*
*Completed: 2026-07-11*
