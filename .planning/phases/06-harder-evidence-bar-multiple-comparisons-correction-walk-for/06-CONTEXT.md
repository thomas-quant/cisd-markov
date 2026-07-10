# Phase 6: Harder Evidence Bar — Multiple-Comparisons Correction & Walk-Forward Validation - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Extends the validation harness (`scripts/build_validation.py`, `cisd_data.py`, `scripts/build_reconcile_findings.py`) with two additive capabilities:
1. A Benjamini-Hochberg (FDR) multiple-comparisons correction across the full bucket grid.
2. Walk-forward validation across multiple sequential train→test windows, supplementing the single sacred discovery/OOS split.

Existing manifest columns (`rate`, `n`, `successes`, `ci_low`, `ci_high`, `min_n_pass`) and the single sacred discovery/OOS path must not change — new output is additive columns/artifacts only.

</domain>

<decisions>
## Implementation Decisions

### Significance Testing (net-new — no p-value exists today)
- **D-01:** Per-bucket p-value tests `H0: rate = 0.5` (fixed coin-flip null), not against a bucket's own parent/baseline rate. This matches the framing already used everywhere in the codebase — README.md's "✓ CONFIRMED = OOS rate held the same side of 50%" and `determine_verdict()`'s same-side-of-50% check. Important context: **no hypothesis test or p-value exists anywhere in the current harness** — `determine_verdict()` only compares point estimates to 0.5. This phase introduces significance testing for the first time; BH correction cannot exist without it.

### Correction Scope & Stage
- **D-02:** One global BH family — every bucket across every analysis × timeframe × instrument × direction is corrected together in a single pass (not grouped per-analysis-key). Matches the roadmap's literal wording ("across the full bucket grid... not just its own single-bucket CI") and the intent to account for the full extent of data-snooping across the whole engine, not one chart at a time.
- **D-03:** The correction fires at the **discovery-manifest stage only** (`validation_manifest_discovery.csv`), before the OOS look. It's a pre-registration-style gate on which buckets earn the sacred OOS look — matching `build_discovery_summary.py`'s existing purpose ("so the researcher can make a go/no-go decision before spending the one sacred OOS evaluation"). The OOS manifest and the final reconciled findings table are not separately corrected.

### Walk-Forward vs. the Sacred OOS Slice
- **D-04:** Walk-forward windows are carved entirely from the discovery slice (`df.index < OOS_START`, i.e. before 2024-04-30). The OOS slice is never touched by walk-forward — it stays reserved for the existing `--oos` flag / single sacred evaluation. This preserves the project's sacred-OOS invariant (the literal `_OOS_BANNER` warning in `build_validation.py`) without ambiguity about how many "looks" the OOS region received.

### Walk-Forward Window Scheme
- **D-05:** Expanding (anchored) windows — each fold trains on all discovery data from the start of history through the fold boundary, then tests on the following chunk. Chosen over fixed-size rolling windows because the discovery history is finite (~3.5-4 years) and every available bar should be used rather than discarding early data.
- **D-06:** 4-5 folds with **fixed calendar-date boundaries** (frozen constants), not equal bar-count boundaries. This follows the existing `OOS_START` precedent — a frozen percentile-of-calendar date, not a bar count — so every timeframe (Daily/4H/1H/15min) slices on the same real-world dates despite wildly different bar density.
- **D-07:** The aggregate "walk-forward robustness verdict" requires a **majority of test folds to pass** (>50%), not unanimous agreement. With only 4-5 folds, one noisy fold shouldn't kill an otherwise-robust edge, but "pass" still means most folds agree.

### Claude's Discretion
- Exact test statistic for the p-value (e.g. normal approximation z-test vs. exact binomial test) — implement in pure Python consistent with the existing `wilson_ci()` / `_erfinv()` pattern; no scipy/statsmodels installed, and the project constraint is to keep dependencies minimal.
- The exact calendar boundary dates for the 4-5 walk-forward folds — derive and freeze them the same way `OOS_START` was derived (documented, hardcoded, with a "do not recompute at runtime" comment).
- Whether per-fold results live in new CSV column(s) on the existing manifest or a new sibling artifact — the roadmap only requires that "the manifest/summary records per-window pass/fail plus an aggregate walk-forward robustness verdict"; exact file/column layout is a planning decision.
- Whether `MIN_N` applies per walk-forward fold individually or only to the aggregate bucket.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` — Phase 6 goal, success criteria, and milestone overview (v2.0)
- `.planning/REQUIREMENTS.md` — MHT-01 (FDR correction), WF-01 (walk-forward validation)
- `.planning/PROJECT.md` — Key Decisions table (sacred chronological holdout, Wilson CI + min-n gate, behavior-preservation invariant carried from v1.0)

No external ADRs/specs beyond the project's own planning docs — requirements are fully captured in the decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `wilson_ci()` (`scripts/build_validation.py:72`) — pure-stdlib (erfinv-based) CI helper. The new p-value/test-statistic code should follow the same pure-Python, no-new-dependency pattern.
- `build_manifest_rows()` (`scripts/build_validation.py:104`) — the single dispatch point that already iterates every `ANALYSES` key × instrument × direction × bucket. Natural place to also emit p-values for the correction, since it already touches every bucket in the grid.
- `slice_df()` (`scripts/build_validation.py:214`) — existing discovery/OOS boundary logic keyed on `OOS_START`. Walk-forward fold boundaries should reuse this precedent (frozen date constants) rather than inventing a different slicing convention.
- `determine_verdict()` (`scripts/build_reconcile_findings.py`) — existing verdict logic (confirmed/not-confirmed/below-n) that the new corrected-pass flag augments per D-03; this function's existing OOS same-side check is untouched.

### Established Patterns
- No scipy/statsmodels installed (checked `.venv/lib/python3.12/site-packages/`) — BH correction and any binomial test must be pure Python, matching `wilson_ci()`'s existing `_erfinv` fallback pattern.
- Per-slice manifest filenames (`validation_manifest_discovery.csv` / `validation_manifest_oos.csv`) — new artifacts should follow this naming convention; roadmap success criterion 3 requires additive columns/artifacts, never a rewrite of the prior manifest shape.
- The `_OOS_BANNER` warning in `build_validation.py`'s `main()` marks the literal "one sacred OOS evaluation" moment — walk-forward's code path must never trigger a second consumption of that data (D-04).

### Integration Points
- New correction math likely lands in `scripts/build_validation.py` (alongside `wilson_ci`/`n_gate`) or a new sibling module — planner's call.
- Walk-forward likely needs its own CLI entry point or flag on `build_validation.py`, analogous to the existing `--oos` flag.
- `tests/test_validation_harness.py` (202 lines) is the existing characterization-test home for this module; new tests for the correction math and window-schedule math belong here per the roadmap's acceptance criterion 4.

</code_context>

<specifics>
## Specific Ideas

- "Confirmed" today (per README.md and `determine_verdict()`) means ONLY: discovery n ≥ 50 AND the OOS rate is on the same side of 50%. There is no p-value anywhere in the current pipeline — this phase introduces significance testing to the harness for the first time, it is not merely adding a correction on top of an existing test.
- `OOS_START = "2024-04-30"` was itself derived as the "70th-percentile date of the shared NQ∩ES daily calendar," then frozen as a hardcoded constant with an explicit comment: "Do NOT recompute at runtime — appending data must not silently shift the OOS boundary." The same frozen-constant approach should govern the new walk-forward fold boundaries (D-06).
- Discovery slice spans roughly late-2020 through 2024-04-30 (~3.5-4 years, derived from the 70/30 discovery/OOS split against the ~1.6yr OOS span of 489 daily bars) — plenty of history for 4-5 calendar folds across all four timeframes (Daily/4H/1H/15min).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 6-Harder Evidence Bar — Multiple-Comparisons Correction & Walk-Forward Validation*
*Context gathered: 2026-07-10*
