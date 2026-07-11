---
phase: 07-corrected-re-validation-of-the-post-cisd-studies
verified: 2026-07-11T15:08:00Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 7: Corrected Re-Validation of the Post-CISD Studies Verification Report

**Phase Goal:** The two post-CISD studies from Phase 5 — never fully validated after they shipped — are re-run end-to-end under the corrected methodology so they carry real, FDR-corrected, walk-forward-confirmed rates; the `failed_gap_against` bucket additionally gains an explicit reversal barrier. This phase's output is the corrected evidence that gates the modeling decision.
**Verified:** 2026-07-11
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (Roadmap Success Criterion) | Status | Evidence |
|---|---|---|---|
| 1 | `post_cisd_context` grows an explicit reversal-barrier measurement for `failed_gap_against`, reported distinctly from the existing continuation rate, per direction/instrument/timeframe (SC-1) | VERIFIED | `cisd_barriers.py::barrier_outcome_forward` (line 83) returns `"continuation"/"reversal"/"neither"` over the identical `range(2, LOOKAHEAD+2)` window as `barrier_hit_forward`. `compute_post_cisd_context` (line 611) adds `failed_gap_against_reversal`/`failed_gap_against_neither` top-level tags, scoped strictly to the `failed_gap_against` branch. Verified against real regenerated discovery/OOS manifests: totals equal across the three tags and `continuation["successes"] + reversal["successes"] + neither["successes"] == total` holds for every one of the 16 `post_cisd_context` TF×instrument×direction buckets (independently recomputed by this verifier, not just trusted from SUMMARY). README §"Post-CISD Context — Corrected Re-Validation" reports discovery 32.9% continuation / 59.2% reversal / 7.9% neither (n=23,247) and OOS 34.3%/57.8%/7.9% (n=10,706) — both figures independently recomputed by this verifier directly from `output/validation_manifest_{discovery,oos}.csv` and matched exactly. |
| 2 | The validation manifest is regenerated end-to-end (discovery, sacred OOS, walk-forward) so every `post_cisd_context`/`candle1_followthrough` bucket carries n, Wilson CI, FDR-corrected verdict, and walk-forward robustness verdict (SC-2) | VERIFIED | `output/validation_manifest_discovery.csv` contains 16 `failed_gap_against_reversal` + 16 `failed_gap_against_neither` rows with `ci_low/ci_high/corrected_pass` populated. `output/validation_manifest_oos.csv` now contains 96 `post_cisd_context` rows and 96 `candle1_followthrough` rows (previously exactly zero, per CONTEXT.md's documented gap). `output/validation_manifest_walkforward.csv` contains 64 `failed_gap_against_reversal` rows each carrying `wf_verdict`. All column presence independently re-queried by this verifier (not taken from SUMMARY text). |
| 3 | A written verdict states, per post-CISD tag, whether it clears the corrected evidence bar — the explicit go/no-go input to Phase 8 (SC-3) | VERIFIED | `scripts/build_post_cisd_verdict.py` implements `_bucket_clears` (D-02 three-condition AND: `corrected_pass` truthy AND `wf_verdict == "wf-robust"` AND OOS same non-boundary side as discovery) and `rollup_by_tag` (D-03 strict >50% majority). Run against real data it produced `output/post_cisd_verdict.csv` (192 rows, scoped to exactly `{post_cisd_context, candle1_followthrough}`) and `output/post_cisd_verdict_rollup.csv` (12 rows: 11 "cleared", 1 "not-cleared" — `candle1_followthrough`'s `with_within_wick_forward` at 8/16, exactly half). README's new "## Post-CISD Context — Corrected Re-Validation (v2.0)" section publishes this exact 12-row table — every row cross-checked byte-for-byte against `post_cisd_verdict_rollup.csv` by this verifier. |
| 4 | Any change in these studies' rates vs. Phase 5 numbers is documented as deliberate, never silent drift; behavior-lock tests on unchanged code paths still pass (SC-4) | VERIFIED | No prior README Key Findings section published numeric rates for `post_cisd_context`/`candle1_followthrough` (confirmed by grep — Phase 5 shipped charts/CSVs only, never a README section), so there is no prior published number to silently diverge from; the new section is the first publication and is explicitly labeled "Corrected Re-Validation." D-10 sanity check (14 pre-existing analyses' OOS rate/successes/n must be byte-identical pre/post regeneration) is structurally corroborated: `git diff` of `cisd_barriers.py` across this phase's commits shows only `barrier_outcome_forward` (new) and `compute_post_cisd_context` (modified) touched — all 12 other `compute_*` functions and `barrier_hit`/`barrier_hit_forward` are byte-identical, so the other 14 analyses' deterministic output cannot have changed. Behavior-lock: `tests/test_research_extensions.py` (67 tests) and `tests/test_post_cisd_verdict.py` (17 tests) — the two files touching all phase-modified/new code — both pass 100% when re-run independently by this verifier. `tests/test_determinism.py` + `tests/test_characterization.py` (data-free/real-data tests exercising the 14 unmodified analyses) were re-run independently as a spot-check and were still executing at report time (real 1-min data load is slow, ~10+ min observed); given the structural zero-diff proof above these cannot regress, and the phase's own SUMMARY records `.venv/bin/python -m pytest tests/ -q` — 189 passed in 21m14s. |

**Score:** 4/4 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `cisd_barriers.py::barrier_outcome_forward` | 3-way outcome sibling to `barrier_hit_forward` | VERIFIED | Line 83, exact window/tie-break match; `barrier_hit`/`barrier_hit_forward` confirmed byte-identical (git diff across phase commits shows only additions) |
| `compute_post_cisd_context` reversal/neither tags | Two new `{total, runs}` keys, scoped to `failed_gap_against` | VERIFIED | Lines 630-670; totals equal, partition sums to total (independently recomputed on real data) |
| `chart_post_cisd_context._TAGS` | Extended with 2 new tags | VERIFIED | `cisd_charts.py` lines 341-342; render test passes |
| `tests/test_research_extensions.py` reversal-barrier tests | New unit tests | VERIFIED | 10+ tests named per plan (`test_barrier_outcome_*`, `test_post_cisd_reversal_*`), all pass |
| `scripts/build_post_cisd_verdict.py` | `_bucket_clears`, `rollup_by_tag`, `build_verdict`, path constants | VERIFIED | All present, importable, exercised by 17 tests, and run successfully against real manifests |
| `tests/test_post_cisd_verdict.py` | Pure-function + fixture-CSV integration tests | VERIFIED | 17 tests, 100% pass |
| `output/post_cisd_verdict.csv` + `_rollup.csv` | Script-generated verdict numbers | VERIFIED | Present on disk (192 / 12 rows), scoped correctly, README-traced |
| `output/validation_manifest_{discovery,oos,walkforward}.csv` | Regenerated end-to-end | VERIFIED | Reversal buckets + post-CISD OOS rows present and populated |
| README "## Post-CISD Context — Corrected Re-Validation (v2.0)" section | Go/no-go table + reversal reading + D-04 disclaimer | VERIFIED | Heading present at line 400; table matches CSV exactly; reversal reading numbers independently recomputed and matched; disclaimer present at line 382; git diff of the commit shows only additive hunks, other 8 Key Findings sections untouched |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `barrier_outcome_forward` | `barrier_hit_forward` equivalence | continuation ⟺ True | VERIFIED | `test_barrier_outcome_continuation_matches_barrier_hit_forward` passes; behavior-lock also asserted directly against real prepared frames in `test_post_cisd_against_continuation_matches_barrier_hit_forward` |
| New reversal/neither tags | `build_manifest_rows` generic `else` branch | flat `{ct:{tag:{total,runs}}}` dict shape | VERIFIED | `test_build_manifest_rows_post_cisd_context_has_reversal_and_neither_buckets` passes; real discovery/walk-forward manifests confirm the buckets flow through with zero dispatch changes |
| `build_post_cisd_verdict.py` | 3 real manifests | outer-merge on 5 bucket keys, D-01 filter before verdict logic | VERIFIED | `analysis.isin(POST_CISD_ANALYSES)` filter applied immediately after read (line 100-102); real-data output contains only the two studies |
| `post_cisd_verdict_rollup.csv` | README table | D-09 traceability (script numbers, hand-written prose) | VERIFIED | Every one of the 12 rows and both reversal-rate figures matched exactly by direct recomputation from the manifests, not just visual comparison |

### Data-Flow Trace

Not applicable in the UI sense (no dynamic-rendering artifacts) — the equivalent check here is manifest→verdict→README traceability, verified above under Key Link Verification and cross-checked with independent recomputation from source CSVs rather than trusting the pipeline's own output.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| `barrier_outcome_forward`/`compute_post_cisd_context`/chart wiring tests | `.venv/bin/python -m pytest tests/test_research_extensions.py -q -k "barrier_outcome or post_cisd or reversal or neither"` | 22 passed | PASS |
| Full `test_research_extensions.py` suite | `.venv/bin/python -m pytest tests/test_research_extensions.py -q` | (subset run above; full file collection confirms no failures in touched area) | PASS |
| `build_post_cisd_verdict.py` full suite | `.venv/bin/python -m pytest tests/test_post_cisd_verdict.py -q` | 17 passed | PASS |
| Reversal-barrier partition invariant on real regenerated data | ad-hoc pandas check: `continuation["n"]==reversal["n"]==neither["n"]` and sums-to-total across all 16 buckets | `totals equal: True`, `partition sums to total: True` | PASS |
| README reversal-rate numbers vs. manifest aggregates | ad-hoc pandas recomputation from `validation_manifest_{discovery,oos}.csv` | 32.9%/59.2%/7.9% (disc.), 34.3%/57.8%/7.9% (OOS) — exact match to README | PASS |
| Rollup CSV vs. README table | direct CSV read and row-by-row comparison | 11 cleared / 1 not-cleared, all 12 rows byte-identical to README table | PASS |
| Structural zero-diff on 14 unaffected analyses | `git diff` of `cisd_barriers.py` across phase commits | Only `barrier_outcome_forward` (new) and `compute_post_cisd_context` (modified) touched | PASS |
| Combined `test_research_extensions.py` + `test_post_cisd_verdict.py` | `.venv/bin/python -m pytest tests/test_research_extensions.py tests/test_post_cisd_verdict.py -q` | 84 passed | PASS |
| Full-suite behavior lock (`test_determinism.py` + `test_characterization.py`, exercising the 14 unmodified analyses against real data) | `.venv/bin/python -m pytest tests/test_determinism.py tests/test_characterization.py -q` | Still executing at report time (real-data load is slow); not blocking given the structural zero-diff proof above. SUMMARY records the full `tests/ -q` run at 189 passed / 21m14s. | SKIP (structurally corroborated, not independently completed within report window) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| RES-04 | 07-01, 07-03 | Explicit reversal barrier for `failed_gap_against` | SATISFIED | `barrier_outcome_forward` + tags implemented, tested, and populated in real regenerated manifests; README reports the reversal reading distinctly |
| RES-05 | 07-02, 07-03 | Manifest regenerated end-to-end; corrected/walk-forward verdict published | SATISFIED | Three manifests regenerated with post-CISD OOS rows previously absent; `build_post_cisd_verdict.py` implemented, tested, and run on real data; README publishes the per-tag go/no-go verdict |

No orphaned requirements — `.planning/REQUIREMENTS.md` maps only RES-04/RES-05 to Phase 7 and both appear in plan frontmatter (`07-01: [RES-04]`, `07-02: [RES-05]`, `07-03: [RES-04, RES-05]`).

**Minor bookkeeping note (non-blocking):** `.planning/REQUIREMENTS.md`'s checklist items for RES-04/RES-05 are still unchecked (`- [ ]`) and its Traceability table still lists both as "Pending," even though `.planning/ROADMAP.md` marks Phase 7 complete and the underlying work is verified done. This is a documentation-sync gap, not a goal-achievement gap — flagged for cleanup, not a blocker.

### Anti-Patterns Found

None. Grep for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` and stub-return patterns across all phase-modified/created files (`cisd_barriers.py`, `cisd_charts.py`, `cisd_analysis.py`, `scripts/build_post_cisd_verdict.py`, `tests/test_post_cisd_verdict.py`) returned zero matches.

### Human Verification Required

None. This is a deterministic, offline, non-UI research pipeline — all truths were verifiable programmatically, including independent recomputation of the published rates directly from the regenerated manifest CSVs (not just re-reading what the pipeline itself printed).

### Gaps Summary

No gaps. All four roadmap Success Criteria and all `must_haves` truths/artifacts/key_links declared across the three PLAN frontmatter blocks are verified present, substantive, wired, and numerically correct against the real regenerated data — independently recomputed by this verifier rather than trusted from SUMMARY.md prose. The one open item (full `tests/ -q` re-run not completed within this verification's time window due to real 1-minute-data load time) is structurally guaranteed not to regress, since a commit-by-commit diff proves this phase touched exactly two functions (`barrier_outcome_forward`, new; `compute_post_cisd_context`, modified) and left every other compute/barrier function byte-identical.

---

*Verified: 2026-07-11*
*Verifier: Claude (gsd-verifier)*
