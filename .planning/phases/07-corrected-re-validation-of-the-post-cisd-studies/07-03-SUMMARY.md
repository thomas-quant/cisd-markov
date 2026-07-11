---
phase: 07-corrected-re-validation-of-the-post-cisd-studies
plan: 03
subsystem: research
tags: [pandas, validation-harness, readme, real-data-regeneration]

requires:
  - phase: 07-corrected-re-validation-of-the-post-cisd-studies
    provides: "07-01's reversal/neither tags and 07-02's build_post_cisd_verdict.py, both required before real-data regeneration could surface them"
provides:
  - Regenerated output/validation_manifest_{discovery,oos,walkforward}.csv carrying the reversal buckets and post-CISD OOS rows
  - output/post_cisd_verdict.csv (192 rows) + output/post_cisd_verdict_rollup.csv (12 rows) run against real data
  - README.md "## Post-CISD Context — Corrected Re-Validation (v2.0)" section + D-04 disclaimer
affects: [08]

tech-stack:
  added: []
  patterns:
    - "The three build_validation.py invocations (discovery / --oos / --walk-forward) are mutually independent (disjoint output files, --walk-forward never touches the discovery/OOS paths) and were run as three concurrent OS processes instead of sequentially, cutting wall-clock from ~60min to ~24min. Only output/validation_slices.csv (a gitignored, non-deliverable side-report) has a benign last-writer-wins race between discovery and --oos."

key-files:
  created: []
  modified:
    - output/validation_manifest_discovery.csv
    - output/validation_manifest_oos.csv
    - output/validation_manifest_walkforward.csv
    - output/validation_findings.csv
    - output/post_cisd_verdict.csv
    - output/post_cisd_verdict_rollup.csv
    - README.md

key-decisions:
  - "Task 1 (regenerating manifests, running reconcile, D-10 diff) was run directly by the orchestrator via plain Bash rather than through codex-rescue — it is pure existing-script execution with no code changes, so there was nothing for Codex to 'implement'. Confirmed with the user before starting."
  - "Task 2's build_post_cisd_verdict.py invocation was likewise run directly by the orchestrator (same reasoning); only the actual README prose authorship was delegated to codex-rescue, with the exact verified numbers handed to it up front so it had no room to recompute or diverge from the traced figures"
  - "The three regeneration runs (discovery/--oos/--walk-forward) were parallelized as concurrent OS processes after verifying they share no manifest output path and no cross-manifest input reads — a one-time ad hoc parallel invocation, not a change to the single-threaded analysis engine itself"

patterns-established: []

requirements-completed: [RES-04, RES-05]

coverage:
  - id: D1
    description: "OOS manifest now carries post_cisd_context and candle1_followthrough rows (previously exactly zero); all three manifests carry the reversal buckets and full corrected/walk-forward columns for both studies (SC-2)"
    requirement: RES-05
    verification:
      - kind: other
        ref: "automated verify: python -c assert block confirming reversal buckets + post-CISD OOS rows present — REGEN_OK"
        status: pass
    human_judgment: false
  - id: D2
    description: "The 14 pre-existing analyses' regenerated rate/successes/n match the prior published OOS numbers exactly (D-10 sanity check, SC-4)"
    requirement: RES-05
    verification:
      - kind: other
        ref: "orchestrator-run pandas diff: prev14 vs new14 outer-merge on 5 bucket keys, 0 rows present in only one side, 0 mismatches in rate/successes/n across all 752 rows — D10_SANITY_OK"
        status: pass
    human_judgment: false
  - id: D3
    description: "README publishes a per-tag go/no-go verdict and the failed_gap_against reversal reading (continuation/reversal/neither), distinct from continuation (SC-1, SC-3)"
    requirement: RES-04
    verification:
      - kind: other
        ref: "automated verify: python -c assert block confirming section heading + both verdict CSVs exist — README_OK; orchestrator cross-checked every table row and rate against output/post_cisd_verdict_rollup.csv and the manifest aggregates directly"
        status: pass
    human_judgment: false
  - id: D4
    description: "Full test suite passes at phase end (behavior-lock across all changed code paths)"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest tests/ -q — 189 passed in 1274.61s (0:21:14)"
        status: pass
    human_judgment: false

duration: "~30min (regeneration + verdict + README) + ~25min test suite, run in parallel where possible"
completed: 2026-07-11
status: complete
---

# Phase 07 Plan 03: Regenerate + Publish Corrected Evidence Summary

**Regenerated all three validation manifests against real NQ/ES data (closing the concrete gap where all 160 post-CISD bucket-rows read "not-confirmed" purely for lack of OOS data), ran the D-09 verdict script, and published the go/no-go verdict plus the reversal-barrier reading in README — 11 of 12 post-CISD tags clear the corrected bar.**

## Performance

- **Duration:** ~30 min for regeneration (3 real-data runs parallelized to ~24min wall-clock instead of ~60min sequential) + verdict script (seconds) + README authorship (~2min via codex-rescue) + full test suite (~22-28min, run last)
- **Tasks:** 2 completed
- **Files modified:** 7 (6 gitignored `output/` artifacts + README.md)

## Accomplishments
- `output/validation_manifest_discovery.csv` now carries `failed_gap_against_reversal` / `failed_gap_against_neither` buckets (16 rows each for `post_cisd_context`, as expected: 4 TF × 2 instruments × 2 directions), with the global BH family recomputed across the larger bucket grid.
- `output/validation_manifest_oos.csv` now carries `post_cisd_context` and `candle1_followthrough` rows — previously exactly zero. This closes the SC-2 gap: `validation_findings.csv` no longer reads all 192 post-CISD rows as `not-confirmed` for lack of OOS data (now 175 confirmed / 14 below-n / 3 not-confirmed).
- `output/validation_manifest_walkforward.csv` carries the reversal buckets with `wf_verdict` (3,776 rows total: 2,184 wf-robust / 1,592 wf-fragile).
- D-10 sanity check: the 14 pre-existing analyses' `rate`/`successes`/`n` are byte-identical between the pre-regeneration OOS manifest and the regenerated one (752/752 rows matched, 0 mismatches, 0 rows present on only one side) — no silent drift.
- `output/post_cisd_verdict.csv` (192 rows) and `output/post_cisd_verdict_rollup.csv` (12 rows) run against the real regenerated manifests: **11 of 12 post-CISD tags clear the corrected bar**; only `candle1_followthrough`'s `with_within_wick_forward` does not (8/16 buckets cleared — exactly half, which is `not-cleared` under the strict-majority rule).
- README gains `## Post-CISD Context — Corrected Re-Validation (v2.0)`: a 4th badge tier (`✓ CORRECTED-BAR CLEARED`), the full 12-row go/no-go table, and the failed_gap_against reversal reading — **discovery: 32.9% continuation / 59.2% reversal / 7.9% neither** (n=23,247), **OOS: 34.3% continuation / 57.8% reversal / 7.9% neither** (n=10,706). The majority of "failed gap against" CISD events actually reverse, not continue — a materially different picture than the depressed continuation rate alone would suggest.
- D-04 transparency disclaimer added to the existing "Validation Methodology" section: the corrected bar applies only to these two studies; the other 8 published Key Findings sections are unevaluated under it (verified untouched via diff).

## Task Commits

1. **Task 1: Regenerate all three manifests + D-10 sanity check** - no code commit (only gitignored `output/*.csv` changed; nothing to commit here)
2. **Task 2: Run verdict script + publish README go/no-go section** - `464e952` (docs)

## Files Created/Modified
- `output/validation_manifest_discovery.csv` - regenerated, +reversal buckets, recomputed BH family (gitignored)
- `output/validation_manifest_oos.csv` - regenerated, +post_cisd_context/candle1_followthrough rows (gitignored)
- `output/validation_manifest_walkforward.csv` - regenerated, +reversal buckets with wf_verdict (gitignored)
- `output/validation_findings.csv` - rebuilt from regenerated discovery+OOS (gitignored)
- `output/post_cisd_verdict.csv` - new, 192 rows, run against real data (gitignored)
- `output/post_cisd_verdict_rollup.csv` - new, 12 rows, run against real data (gitignored)
- `README.md` - new "Post-CISD Context — Corrected Re-Validation (v2.0)" section + D-04 disclaimer bullet

## Decisions Made
- Task 1's script regeneration and Task 2's verdict-script invocation were run directly by the orchestrator (plain Bash) rather than through codex-rescue, since both are pure existing-script execution with zero code changes — confirmed with the user via AskUserQuestion before starting. Only the actual README prose (genuine content authorship) was delegated to codex-rescue, and it was handed the exact orchestrator-verified numbers up front rather than being asked to (re)compute them, closing the T-07-06 "human transcription" risk at the source.
- The three `build_validation.py` invocations (discovery / `--oos` / `--walk-forward`) were parallelized as three concurrent OS processes after the orchestrator confirmed via source inspection that they are fully independent: distinct output files, `--walk-forward` returns before ever touching the discovery/OOS code path, and the one shared write (`output/validation_slices.csv`, a gitignored side-report not in this plan's deliverables) has no downstream consumer, so a last-writer-wins race on it is harmless. This cut wall-clock from ~60min sequential to ~24min. This is a one-time ad hoc parallel invocation for this regeneration, not a change to the single-threaded analysis engine's architecture.

## Deviations from Plan

None — plan executed exactly as written, aside from the execution-mechanism substitution (orchestrator-direct + codex-rescue instead of gsd-executor) that was the explicit, pre-agreed premise for this entire phase's execution.

## Issues Encountered
None. The plan's final verification step (full test suite at phase end) was launched in the background immediately after the README commit and completed clean: 189 passed in 1274.61s (21m14s) — no regressions from any of this phase's changes.

## Next Phase Readiness
- The RES-04/RES-05 corrected evidence is published and traceable. Phase 8's modeling decision is gated on this verdict: 11/12 post-CISD tags clear the corrected bar (only `candle1_followthrough`'s `with_within_wick_forward` does not).
- No blockers. Full test suite green (189 passed).

---
*Phase: 07-corrected-re-validation-of-the-post-cisd-studies*
*Completed: 2026-07-11*
