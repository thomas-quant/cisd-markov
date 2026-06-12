# Phase 2: Validation Harness - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase adds a **trust layer over existing computed numbers** — it does not change how CISD, barriers, FVG, sweep, or SMT are computed. It delivers:

1. A **sacred chronological date holdout** splitting history into discovery (oldest ~70%) and OOS (newest ~30%), with discovery-on-train as the default run path.
2. A **separate, deliberate single-evaluation OOS path** that the tooling nudges toward keeping sacred.
3. **Binomial confidence intervals** on every reported barrier/hit rate.
4. **Sample-size gating** — under-powered buckets are flagged, not reported as findings.
5. A **results manifest** recording n, CI, and IS/OOS status per bucket.

**Explicitly NOT in this phase:** re-validating/republishing the existing README findings (that is Phase 3), the modular refactor or hot-loop vectorization (Phase 4), new CISD studies (Phase 5), multiple-comparisons correction or walk-forward validation (deferred to v2). The harness is built and proven on the existing analyses; it is *applied* to retire/republish findings in Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Holdout split & boundary (VALID-01)
- **D-01:** Split ratio is **locked at oldest ~70% discovery / newest ~30% OOS, chronological** (from PROJECT.md Key Decisions — not re-litigated).
- **D-02:** The discovery/OOS boundary is a **frozen committed date constant** (e.g. `OOS_START = "YYYY-MM-DD"`), computed **once** from the current data snapshot and hardcoded — NOT recomputed at runtime. Rationale: bit-stable across runs; appending data later must not silently shrink discovery or leak into OOS. Matches PROJECT.md's "fixed data snapshot ⇒ stable OOS boundary" assumption.
- **D-03:** The split is by **event timestamp**: a CISD event belongs to discovery if its bar timestamp is `< OOS_START`, else OOS. The boundary is defined on the **shared NQ∩ES intersected calendar** (`prepare_pair` already intersects the two indices), so a single global `OOS_START` applies to both instruments.
- **D-04:** Default run path operates on the **discovery (train) slice only**. (Locked — PROJECT.md.)

### Sacred OOS enforcement (VALID-02)
- **D-05:** Enforcement is **soft, not a hard lock**: default run is discovery-only; touching OOS requires an explicit **`--oos` flag** and prints a loud "you are spending your one sacred evaluation" banner. Fits a solo, lightweight workflow while still nudging toward sacredness.
- **D-06:** OOS evaluations **may be appended to the manifest as a record** (for self-audit), but the tool **never blocks or refuses** a re-run. No committed eval-count ledger this phase.

### Confidence intervals & sample-size gating (VALID-03/04)
- **D-07:** CI method = **Wilson score interval at 95%**, implemented in **pure numpy** (no scipy). Chosen for small-n robustness — headline extremes live at n=11–18 where Wald is degenerate; Clopper-Pearson was rejected to avoid a new dependency against the "minimal deps / runs offline" constraint.
- **D-08:** Minimum-n threshold for a reportable finding = **n ≥ 50**, stored as a single `MIN_N` constant (bumpable). (User chose 50 over the suggested 30 — a stricter finding bar.)
- **D-09:** Below-threshold buckets are **flagged and kept visible** (rate + n + CI shown, marked "below-n / not a finding"), **never silently dropped**. Matches the project's "retire or label, never silently drop" ethos and lets a bucket be watched as it accumulates n.

### Reporting surface, manifest & reconciliation (VALID-05)
- **D-10:** The results manifest is a **tidy long CSV**, one row per bucket (`analysis × timeframe × instrument × direction × bucket`) with columns approximately: `rate`, `n`, `successes`, `ci_low`, `ci_high`, `ci_method`, `min_n_pass`, `slice` (`discovery`/`oos`). Mirrors the existing `output/cisd_expectancy.csv` tidy-long convention; both machine-readable (Phase 3 consumes it) and Excel-friendly.
- **D-11:** Reporting surface for THIS phase = **manifest + a discovery/OOS CSV only**. **No new PNG charts** and no CI annotation retrofitted onto existing charts this phase. Visual CI display can come with the Phase 3 republish.
- **D-12:** **Parallel-path reconciliation** with the Phase 1 characterization tests: the existing full-history default run stays **byte-identical** so the Phase 1 characterization tests stay green. The harness is **additive** — it must not mutate the existing `compute_*` outputs or the numbers the characterization tests lock. The deliberate "republish from train/OOS" happens in Phase 3, not here.

### Claude's Discretion (for research/planner)
- The exact `OOS_START` value must be **computed and committed** during planning/execution: take the 70th percentile of available bar dates on the shared NQ∩ES calendar (decide rounding — e.g. snap to a session/day boundary) and freeze it. Document how it was derived next to the constant.
- Where the harness code lives (new `cisd_validation.py` module vs a `scripts/build_validation.py` consumer) is a planning decision — constraint: **additive, do not edit the locked compute path**, and degrade gracefully when SMT is absent (mirror Phase 1's optional-SMT pattern).
- Exact manifest column names/order and the discovery/OOS CSV layout, as long as D-10's fields are all present.
- Whether train/OOS slicing happens on the 1-minute frame before resampling or on the resampled frame — pick whichever keeps results identical to a full-history run restricted to the slice (verify no boundary-bar leakage either way).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & locked decisions
- `.planning/ROADMAP.md` §"Phase 2: Validation Harness" — goal, 5 success criteria, the two planned plan splits (02-01 holdout/sacred-OOS, 02-02 CI/gating/manifest).
- `.planning/REQUIREMENTS.md` §"Validation Harness" — VALID-01 through VALID-05 exact wording (the acceptance bar).
- `.planning/PROJECT.md` §"Key Decisions" + §"Constraints" — sacred holdout, behavior-preserving refactor, foundational depth (CIs + n-gating only; MHT & walk-forward are v2), minimal-deps / offline / deterministic constraints.

### The problem being solved
- `.planning/codebase/CONCERNS.md` — the in-sample / no-CI / no-MHT trust gap and the tiny-n headline extremes this harness gates.
- `.planning/codebase/ARCHITECTURE.md` — one-directional data flow (parquet → resample → enriched DF → compute → chart/CSV) the harness layers onto.

### Code to build on / mirror
- `cisd_analysis.py` — `barrier_hit` (line ~386), the `compute_*` functions returning nested `{total, runs}` counts (the `n`=total and `successes`=runs that feed Wilson CI), `build_csv_rows` (tidy-long CSV builder to mirror), `main()` (line ~1298, load-once + per-TF loop where train/OOS slicing plugs in), `prepare_pair` (NQ∩ES index intersection = the shared calendar for `OOS_START`).
- `scripts/build_expectancy.py` — reference for a tidy-long CSV manifest (`output/cisd_expectancy.csv`) and the `np.flatnonzero` vectorized pattern; also the graceful-SMT-degradation pattern.
- `README.md` — the headline numbers Phase 3 will re-run through this harness (this phase must not move them).
- `tests/` (Phase 1 characterization + unit tests) — MUST stay green; they lock full-history numbers the harness must not alter.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`compute_*` nested-dict outputs** (`{direction: {bucket: {"total": int, "runs": int}}}`): `total` → binomial n, `runs` → successes. Wilson CI + n-gating consume these directly — no re-counting needed.
- **`pv(num, den)`** helper already computes the percent rate; the harness adds CI bounds around it.
- **`build_csv_rows`** (tidy-long flattening) and **`scripts/build_expectancy.py`**'s `cisd_expectancy.csv`: existing tidy-long CSV precedents for the manifest's shape and writing convention.
- **`prepare_pair`** already intersects the NQ and ES indices — gives the single shared calendar `OOS_START` is defined on.

### Established Patterns
- **Module-level `UPPER_SNAKE` constants** at the top of `cisd_analysis.py` (`LOOKAHEAD`, `MIN_N` slot fits here): add `OOS_START`, `MIN_N`, `CI_LEVEL` following this convention.
- **Optional external dep / graceful degradation** (Phase 1: env-var `SMT_PKG_PATH`, every entry point degrades when SMT absent): the harness must keep this property.
- **Behavior-preserving / characterization-locked**: additive code only; the existing full-history compute path stays byte-identical.

### Integration Points
- Train/OOS slicing plugs in around `prepare_pair` / the per-TF loop in `main()` (or a parallel harness entry point) — slice the event set by `OOS_START`, then run the same `compute_*` functions on each slice.
- The harness emits NEW artifacts under `output/` (manifest CSV + discovery/OOS CSV); it does not overwrite the locked `{tf}.csv` / `{tf}.png` / standalone PNGs.

</code_context>

<specifics>
## Specific Ideas

- "Sacred" is taken literally: the default path should make it *hard to accidentally* burn the OOS evaluation — hence discovery-on-train default + explicit `--oos` + a loud spending-your-one-shot warning.
- Wilson specifically because the buckets that matter most (Daily ES/NQ bear w/ SMT at n=11–18) are exactly where naive Wald intervals lie.
- `n ≥ 50` is a deliberately stricter finding bar than the textbook n≥30 — the user wants headline eligibility to mean something on this dataset.

</specifics>

<deferred>
## Deferred Ideas

- **Visual CI annotation** (CI whiskers + n labels + below-n shading on PNG/HTML) — deferred; natural fit for the Phase 3 republish, not this phase.
- **Hard evaluation ledger** (committed OOS eval-count that warns/refuses repeats) — considered and rejected for this phase in favor of the soft `--oos` + warning; could revisit if self-discipline proves insufficient.
- **Multiple-comparisons / data-snooping correction** (Benjamini-Hochberg, Bonferroni, White's Reality Check) and **walk-forward validation** — explicitly v2 (MHT-01, WF-01), out of scope.
- **Clopper-Pearson exact CI** — rejected this phase to avoid a scipy dependency; revisit only if exact coverage is ever required.

None of the above stalls planning — they are intentional boundaries.

</deferred>

---

*Phase: 2-Validation Harness*
*Context gathered: 2026-06-12*
