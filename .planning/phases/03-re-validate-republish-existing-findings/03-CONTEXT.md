# Phase 3: Re-Validate & Republish Existing Findings - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase treats every existing README headline finding as a hypothesis and applies the Phase 2 harness to produce an honest, reproducible publication. It delivers:

1. **WR-04 fix:** Stale README §8 SMT table and §3 within-wick label regenerated from live `cisd_analysis.py` output before re-validation begins.
2. **Discovery run:** All README findings re-run through `build_validation.py` (discovery/train slice) with n + CI attached. Eligibility gated by n ≥ 50.
3. **Discovery summary report:** Auto-generated per-finding summary (rate, n, CI, OOS-eligible Y/N) for researcher review before any OOS spending.
4. **OOS confirmation:** Researcher manually triggers `build_validation.py --oos` after reviewing the summary. Findings eligible (n ≥ 50 on discovery) are confirmed if OOS rate matches direction.
5. **Reconciler script:** Takes both manifests (IS + OOS) and outputs a labeled findings CSV: `confirmed` / `not-confirmed` / `below-n`. This CSV is the single source of truth for Plan 03-02.
6. **Republished README:** Discovery-slice rates replace full-history numbers. Per-finding: rate + n + CI + IS/OOS badge. Failures labeled `✗ NOT CONFIRMED`. Below-n buckets flagged "below-n / not a finding" and kept visible (never dropped).

**Explicitly NOT in this phase:** modular refactor or hot-loop vectorization (Phase 4), new CISD studies (Phase 5), multiple-comparisons correction or walk-forward validation (v2 deferred).

</domain>

<decisions>
## Implementation Decisions

### Survival criterion (REVAL-01/02)
- **D-01:** OOS eligibility gate = **n ≥ 50 on the discovery slice only**. No CI threshold gate — any n ≥ 50 finding goes to OOS regardless of CI_low. Keeps the rule simple and unambiguous.
- **D-02:** OOS confirmed if **OOS rate matches direction** (same side as discovery rate — e.g., if discovery rate > 0.50 for bullish, OOS rate must also be > 0.50). No CI gate on OOS (OOS n is ~30% of discovery n and power is limited).
- **D-03:** Findings that fail OOS are labeled **`✗ NOT CONFIRMED`** — discovery rate + n + CI shown, OOS rate shown, verdict explicit. Never silently dropped.

### README rate display (REVAL-03)
- **D-04:** **Discovery-slice rates replace full-history rates** in all README tables. Clean break — every number in the README goes through the harness after Phase 3.
- **D-05:** **Fix stale WR-04 numbers first:** regenerate §8 SMT table and the misattributed §3 within-wick instrument label from live `cisd_analysis.py` full-history output before running the harness. Plan 03-01 handles this as a prerequisite step.
- **D-06:** **Below-n buckets stay visible** in the README with rate + n + CI + "below-n / not a finding" badge. Consistent with Phase 2 D-09 — never silently drop, so buckets can be watched as n grows.

### OOS workflow automation (REVAL-01/02)
- **D-07:** **Human-gated two-step** — discovery run first, researcher reviews the summary, then manually triggers `--oos`. Preserves the sacred-evaluation ceremony and ensures the OOS spend is a deliberate decision.
- **D-08:** **Auto-generated discovery summary report** bridges the review step: after the discovery run, a script prints a clean per-finding table (discovery rate, n, CI, OOS eligible Y/N) formatted for quick human review before OOS.
- **D-09:** **Reconciler script lives in 03-01:** after OOS is run, the reconciler reads both manifests and outputs a labeled `validation_findings.csv` (columns: analysis, timeframe, instrument, direction, bucket, discovery_rate, discovery_n, discovery_ci_low, discovery_ci_high, oos_rate, oos_n, verdict). Plan 03-02 reads this CSV to rewrite the README.

### Claude's Discretion
- Exact column names and format of the discovery summary report (CLI output or Markdown file) — as long as it shows rate, n, CI, and OOS-eligible Y/N per bucket.
- Whether `validation_findings.csv` is written to `output/` or `.planning/` — convention: `output/` consistent with other manifest artifacts.
- Exact README table layout for the CI + badge columns — must include rate, n, CI range (e.g., `[lo–hi]`), and verdict badge, but exact formatting is Claude's call.
- When an analysis produces zero n ≥ 50 buckets on the discovery slice, note it as "no reportable findings" rather than omitting the section silently.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & locked decisions
- `.planning/ROADMAP.md` §"Phase 3: Re-Validate & Republish Existing Findings" — goal, 4 success criteria, the two planned plan splits (03-01 discovery+OOS+reconciler, 03-02 README republish).
- `.planning/REQUIREMENTS.md` §"Re-Validation & Republish" — REVAL-01 through REVAL-03 exact wording.
- `.planning/PROJECT.md` §"Active" — WR-04 stale README number fix (required before republish); §"Key Decisions" — sacred holdout, behavior-preserving, n≥50 gate.

### Validation harness (the tool Phase 3 uses)
- `scripts/build_validation.py` — the harness entry point: `--oos` flag, `build_manifest_rows()` (all 14 analyses wired), `slice_df()` (discovery/OOS slicing on the shared NQ∩ES calendar), `wilson_ci()`, `n_gate()`.
- `cisd_analysis.py` — constants: `OOS_START = "2024-04-30"`, `MIN_N = 50`, `CI_LEVEL = 0.95` (lines 69–74). Also the source for regenerating WR-04 numbers.
- `.planning/phases/02-validation-harness/02-CONTEXT.md` — Phase 2 decisions: D-07 (Wilson CI, pure stdlib), D-08 (n≥50 gate), D-09 (below-n flagged, never dropped), D-10 (manifest tidy-long CSV schema), D-11 (manifest is additive; existing chart outputs unchanged), D-12 (behavior-preserving).

### Current README (what gets replaced/annotated)
- `README.md` — §1 Baseline, §2 Wick Position, §3 Combined Wick×Consecutive, §4 Stricter CISD, §5 Markov, §6 Candle Body/ATR, §7 Volume Ratio, §8 SMT Confirmation. These are the in-sample numbers Phase 3 re-validates. §8 and §3 have stale/misattributed values per WR-04.

### Prior phase manifests (if they already exist)
- `output/validation_manifest.csv` — may already contain discovery rows from Phase 2 testing; check before re-running.
- `output/validation_slices.csv` — slice inventory (n_bars, date ranges per TF/instrument).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`build_validation.py:build_manifest_rows()`** — already produces all 14 analyses × all TFs × IS/OOS. Phase 3 reads its output; does not reimplement it.
- **`build_validation.py:wilson_ci()` / `n_gate()`** — CI and gate logic already callable as library functions; reconciler script can import them directly.
- **`build_validation.py:_OOS_BANNER`** — the sacred banner is already wired into the `--oos` path. No changes needed.
- **`output/cisd_expectancy.csv`** — tidy-long CSV precedent for `validation_findings.csv` format.

### Established Patterns
- **Additive output pattern:** Phase 3 writes new files (`validation_findings.csv`, updated `README.md`). It does not overwrite `{tf}.csv` / `{tf}.png` / existing manifest columns or break Phase 1 characterization tests.
- **Graceful SMT degradation:** Both `build_validation.py` and `build_expectancy.py` already degrade gracefully when SMT is absent. Reconciler and summary scripts must follow the same pattern.
- **Tidy-long CSV convention:** `output/` artifacts are tidy long tables (one row per bucket), not wide pivot tables. `validation_findings.csv` follows this.

### Integration Points
- **Plan 03-01:** runs `build_validation.py` (discovery) → prints discovery summary → researcher reviews → researcher runs `build_validation.py --oos` → reconciler reads both manifests → writes `output/validation_findings.csv`.
- **Plan 03-02:** reads `output/validation_findings.csv` + re-runs `cisd_analysis.py` for WR-04 numbers → rewrites `README.md` tables with discovery-slice rates + n + CI + verdict badges.
- **Phase 1 tests:** `tests/test_characterization.py` locks full-history numbers. Phase 3 does NOT touch the full-history compute path — tests must stay green.

</code_context>

<specifics>
## Specific Ideas

- "Sacred" evaluation stays ceremonious: the `--oos` flag + ASCII banner is already in the harness. Phase 3 relies on this and adds the human review step (discovery summary) between discovery and OOS.
- Discovery summary is a formatted CLI table (or brief Markdown file), not a raw CSV dump — the point is to make the go/no-go review easy for the researcher without opening Excel.
- `✗ NOT CONFIRMED` and `✓ CONFIRMED` verdict labels must be consistent between the `validation_findings.csv` and the README badge format so they're machine-readable (e.g., for future automation).
- Below-n badge in README should distinguish "below-n" from "not-confirmed-OOS" — they have different meanings even though both are not headline findings.

</specifics>

<deferred>
## Deferred Ideas

- **Visual CI annotation** (CI whiskers / shading on PNG charts) — deferred from Phase 2; still not in scope here. Natural fit for a future polish pass.
- **Multiple-comparisons correction** (BH, Bonferroni, White's Reality Check) — MHT-01, explicitly v2.
- **Walk-forward validation** — WF-01, explicitly v2.

None of the above stalls planning — they are intentional boundaries.

</deferred>

---

*Phase: 3-Re-Validate & Republish Existing Findings*
*Context gathered: 2026-06-12*
