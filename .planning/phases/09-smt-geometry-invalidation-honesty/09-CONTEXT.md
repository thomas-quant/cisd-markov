# Phase 9: SMT Geometry & Invalidation Honesty - Context

**Gathered:** 2026-07-12
**Status:** Ready for planning

<domain>
## Phase Boundary

The Swing-SMT annotation stops discarding the price/lifecycle data `scan_smts_historical` already returns, stops crediting SMTs that were already invalidated by the CISD bar, and gains geometry features — all pushed through the existing corrected validation harness (n + Wilson CI + BH-FDR + walk-forward). Concretely, for RES-06 this phase:

1. Carries `reference_price`, `invalidation_level`, `broken_ts`, `status` (and the supporting `reference_timestamp`, `invalidation_asset`, `invalidation_direction`) through the per-bar SMT annotation.
2. Fixes the already-invalidated-at-`t` tagging bug (see D-01).
3. Adds geometry features `smt_block_size_atr` and `cisd_in_smt_block` (D-04/D-05), a survived-vs-broke-in-window diagnostic split (D-06/D-07), and reports the previously-unused `swing_smt_role` split (D-08).
4. Documents any resulting change to the published SMT rates as a deliberate, visible methodology change (D-09) — never silent drift.

**In scope:** only the Swing-SMT study and its annotation path (`cisd_data.py`), the `smt_cisd` barrier analysis + a new `smt_role` analysis (`cisd_barriers.py` / `cisd_charts.py`), their flow through the generic validation manifest, and the README methodology writeup.

**Explicitly out of scope:** re-validating the other 15 analyses under any changed methodology; micro/FVG SMT signals (scanner is called with `enable_micro=False, enable_fvg=False`); the continuous-magnitude / session / volume feature families (those are Phase 10, RES-07); any model (Phase 11, ML-01).

</domain>

<decisions>
## Implementation Decisions

### Invalidation validity (the bug fix)
- **D-01:** A matched same-direction SMT counts as `w/ SMT` **only** if it is still valid as of the CISD bar `t` — i.e. its `broken_ts` is NaT **or strictly greater than** `t`. An SMT whose `broken_ts` lands exactly on bar `t` (invalidation breached intrabar during the CISD bar) is **disqualified** — sub-bar ordering vs the CISD close is unknowable, and the phase's honesty theme + the roadmap's "invalidated at or before `t`" wording favor the conservative cut. This is the correctness fix RES-06 requires.
- **D-02:** The validity test compares `broken_ts` **to `t`** — it must **never** filter on the `status` column. `status == "broken"` only means the SMT broke *at some point* (usually far in the future); filtering on it would be look-ahead bias. Only breaks at-or-before `t` (past information) may remove an event from `w/ SMT`.
- **D-03:** The bug fix pulls already-dead SMTs into their own reported bucket. The `smt_cisd` split becomes **three-way**: `w/ SMT` (valid at `t`) / `expired SMT` (an SMT matched in the `[t-2, t]` window but was dead by `t`) / `no SMT` (no same-direction match in the window at all). The `expired SMT` bucket makes the previously mis-credited population visible instead of silently folding it into `no SMT`.
- **D-03a (matching semantics):** Validity is checked on **only the single latest-created matched SMT** (the existing "latest-created wins" selection). If that matched SMT is dead at `t`, the CISD is `expired SMT` even when an *earlier* still-valid same-direction SMT exists in the window. Chosen deliberately: this is the minimal change that fixes the bug (add a validity check) without introducing a new re-search selection rule, and matches SC1's singular "the matched SMT."

### Block geometry (magnitude + containment)
- **D-04 (`smt_block_size_atr`):** The scanner emits only one swing level per asset (`reference_price` on the sweeper, `invalidation_level` on the failer) at ~10× different point scales, so `block_high − block_low` cannot be a cross-asset subtraction. Instead: **`block_high`/`block_low` = the high/low of the bar at `reference_timestamp` on the annotated instrument**, and `smt_block_size_atr = (block_high − block_low) / ATR(14)`. This is the most literal reading of "block_high − block_low," is same-instrument, role-independent, and reuses the existing ATR(14) = `(high − low).rolling(14).mean()` definition.
- **D-05 (`cisd_in_smt_block`):** True when the **CISD body (open→close of bar `t`, wicks excluded) sits fully inside** `[block_low, block_high]` (both open and close within the zone). Strict full-containment is the cleanest economic reading of "the CISD formed within the SMT block."
- **D-05a (derived):** Both geometry features are defined **only where a matched SMT event exists** (`w/ SMT` or `expired SMT`); they are NaN / excluded for `no SMT` CISDs. The barrier split for the continuous `smt_block_size_atr` is therefore bucketed only over CISDs that carry a matched block.

### Survived-vs-broke diagnostic split (SC4)
- **D-06 (window):** "Broke in window" uses the **barrier lookahead horizon**: `broke` = `broken_ts` falls within `(t, t+2]` (`LOOKAHEAD = 2`); `survived` = `broken_ts` is NaT or beyond `t+2`. Same horizon the barrier outcome is measured over, so survival is directly comparable to the run/no-run result.
- **D-07 (reporting, no filtering):** The split is reported as **two full validated sub-buckets** — `w/ SMT & survived` and `w/ SMT & broke` — **in addition to** the un-split aggregate `w/ SMT` bucket. Each sub-bucket flows through the generic manifest dispatch and therefore carries n + Wilson CI + BH-FDR + walk-forward. The `w/ SMT` population is **never filtered** on survival (that would be hindsight); the split is diagnostic only.

### Bucket granularity & role split
- **D-08 (`swing_smt_role`):** The currently-computed-but-unused role split (swept vs failed_to_sweep) is surfaced as a **new standalone analysis** (`smt_role`) with its own `ANALYSES` entry and all-TF standalone figure, splitting the valid `w/ SMT` population by role. Keeps `smt_cisd`'s clean three-way split intact and follows the "one analysis answers one question" registry convention rather than multiplying buckets inside `smt_cisd`.

### Documenting the methodology change (SC1)
- **D-09:** The invalidation fix's before/after change to published SMT rates is documented in a **new README methodology subsection** ("SMT Invalidation Honesty (v2.0)") showing before (buggy) vs after (fixed) `w/ SMT` rates and n deltas, following Phase 7's pattern (script-generated numbers, hand-written prose, ✓/✗/below-n badge vocabulary), **plus** refreshing the existing Key Finding section 8 table with the corrected numbers.
- **D-09a:** No separate before-snapshot ceremony is needed — the "before" numbers are the currently-published section 8 / manifest values already on record (mirrors Phase 7 D-11's determinism trust). "After" is the regenerated manifest. Any regenerated number for the *other* analyses that differs from what's published must be treated as a real bug to investigate, never silently republished.

### Claude's Discretion (planner / researcher call)
- Exact ATR anchoring for `smt_block_size_atr` — ATR(14) evaluated at the CISD bar `t` (default, matches `compute_candle_size`'s convention) vs at the `reference_timestamp` bar. Default to bar `t`.
- Bucket thresholds for the continuous `smt_block_size_atr` — follow the existing `candle_size` convention (`<0.5×` / `0.5–1×` / `1–1.5×` / `>1.5×` ATR).
- Whether the `expired SMT` bucket and/or `smt_role` also carry the geometry features, or stay barrier-only — planner's call following what's cleanest; not required by RES-06.
- How the new columns thread through `scripts/build_forward_returns.py` and `scripts/build_expectancy.py` filter families (they degrade gracefully when SMT is absent already).
- Exact file/function structure for the before/after documentation script (new sibling vs extension of `build_reconcile_findings.py`), following Phase 7's single-responsibility pattern.
- Exact column/bucket naming for the new features and buckets — follow the existing lowercase-underscore + `{ct: {tag: {total, runs}}}` conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` — Phase 9 goal + 4 success criteria; Phase 11's dependency on Phase 9's corrected SMT evidence
- `.planning/REQUIREMENTS.md` — RES-06 (the full phase requirement); RES-07 (Phase 10, for the out-of-scope boundary)
- `.planning/PROJECT.md` — Key Decisions table (sacred holdout, Wilson CI + min-n, "publish failures explicitly," "any published number that moves must be deliberate & documented")
- `.planning/phases/07-corrected-re-validation-of-the-post-cisd-studies/07-CONTEXT.md` — Phase 7's publication pattern this phase reuses for D-09 (D-08 new README section, D-09 script-generated numbers/hand-written prose, D-10/D-11 OOS re-run determinism trust)
- `.planning/phases/06-harder-evidence-bar-multiple-comparisons-correction-walk-for/06-CONTEXT.md` — the corrected bar (BH-FDR + walk-forward + Wilson CI + per-fold min-n) that every new bucket in this phase must clear (SC4)

### The SMT annotation & scanner (the code this phase changes)
- `cisd_data.py:451` (`_annotate_swing_smt_from_events`) — the per-bar matcher; today consumes only `signal_type`, `created_ts`, `sweeping_asset`, `failing_asset` and discards everything else. D-01/D-02/D-03/D-04/D-05 all land here.
- `cisd_data.py:586` (`_scan_swing_smt_events`) / `cisd_data.py:602` (`prepare_pair`) — where the scanner is called (`enable_micro=False`, `enable_swing=True`, `enable_fvg=False`) and where the returned event columns must be threaded into the annotation.
- `/mnt/e/backup/code/Finance/Misc/SMT/smt/historical.py` — the scanner. `EVENT_COLUMNS` (line 12) is the authoritative returned schema: `signal_type, created_ts, reference_timestamp, sweeping_asset, failing_asset, reference_price, invalidation_asset, invalidation_direction, invalidation_level, broken_ts, status`. `_resolve_broken_ts` (line 60) computes `broken_ts` as the first bar **strictly after** `created_ts` where `invalidation_level` is breached on the `invalidation_asset` — this is the field D-01 tests against `t`. Swing `reference_price`/`invalidation_level` construction: lines 239–240 (reference_price = sweeping asset's swing extreme, invalidation_level = failing asset's).

### The SMT barrier analysis (consumers)
- `cisd_barriers.py:357` (`compute_smt_cisd`) — the two-way `w/ SMT` / `no SMT` split that becomes three-way (D-03) and gains the survived/broke sub-buckets (D-07); the new `compute_smt_role` and geometry-bucket computes are siblings.
- `cisd_barriers.py:279` (`compute_candle_size`) — reference implementation for ATR(14) (`(high − low).rolling(14).mean()`) and the `<0.5×/0.5–1×/1–1.5×/>1.5× ATR` bucket convention D-04 reuses.
- `cisd_charts.py:336`-style `chart_*` + `ANALYSES` / `ANALYSIS_META` registry (`cisd_barriers.py:~694`, `~733`) — where `smt_cisd` is registered and where the new `smt_role` analysis + standalone figure get wired (see CLAUDE.md "Adding a New Analysis").
- `scripts/build_validation.py` — `build_manifest_rows`'s generic `{dir: {tag: {total, runs}}}` dispatch (Phase 6/7 confirmed it covers any `ANALYSES` key automatically) + `apply_bh_correction` / `evaluate_fold` / `walk_forward_verdict`; new buckets get n/CI/FDR/WF for free via this path (SC4).
- `README.md` §8 "Swing SMT Confirmation" (~line 250) and the "Validation Methodology — Harder Evidence Bar (v2.0)" section — the badge vocabulary and natural home for the D-09 before/after writeup.

No external ADRs/specs beyond the project's own planning docs and the local SMT package — the geometry/validity definitions are fully specified in the decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **The scanner already returns every field this phase needs.** `_scan_swing_smt_events` returns the full `EVENT_COLUMNS` DataFrame; only `_annotate_swing_smt_from_events`'s `required_event_columns` tuple (currently 4 columns) and its per-bar writes need widening — no scanner change and no new SMT call.
- **ATR(14)** = `(df["high"] - df["low"]).rolling(14).mean()` in `compute_candle_size` (`cisd_barriers.py:282`) — copy for D-04's normalization; do not invent a true-range variant.
- **Generic validation dispatch** (`build_manifest_rows` "Generic" branch) already turns any `{ct: {tag: {total, runs}}}` compute output into n/CI/FDR/WF manifest rows — the three-way split, survived/broke sub-buckets, geometry buckets, and `smt_role` all inherit SC4's stats with zero harness changes (confirmed pattern from Phase 7 D-context).
- **`swing_smt_role`** is already computed at `cisd_data.py:550` (`swept` / `failed_to_sweep` / `none`) — D-08 only needs a `compute_smt_role` + chart + registry entry to consume it.

### Established Patterns
- Vectorized annotation (Phase 8): `_annotate_swing_smt_from_events` is a per-direction `searchsorted` matcher. D-01's validity check must be added **vectorized** alongside the existing `in_window` mask (compare the matched event's `broken_ts` array to `row_ts`), not as a re-introduced per-bar Python loop.
- Compute functions return nested `{direction: {bucket: {total, runs}}}`; chart functions drive rows from a hardcoded tag/alpha list. New buckets = extend the dict shape + the chart's tag list (per CLAUDE.md "Adding a New Analysis").
- README Key Findings use ✓ CONFIRMED / ✗ NOT CONFIRMED / below-n badges; D-09's new section extends this vocabulary, matching Phase 7 D-08.

### Integration Points
- New annotation columns (`smt_reference_price`, `smt_invalidation_level`, `smt_broken_ts`, `smt_status`, `smt_block_size_atr`, `cisd_in_smt_block`, plus the survived/broke flag) originate in `_annotate_swing_smt_from_events` → consumed by `compute_smt_cisd` (three-way + survived/broke), new `compute_smt_role`, and the geometry-bucket compute → flow through `build_manifest_rows` (generic branch, no change) → the D-09 before/after doc script + README.
- `prepare_pair(..., with_swing_smt=True)` is the only entry that populates these columns; every other path (single-instrument `prepare`) leaves them at their no-SMT defaults, so consumers must tolerate absent SMT columns (the existing `smt_cisd` graceful-degradation contract).

</code_context>

<specifics>
## Specific Ideas

- The roadmap's literal `smt_block_size_atr = block_high − block_low` formula does **not** map to the swing-SMT scanner output (no `block_high`/`block_low`; only one cross-asset swing level per asset). D-04 resolves this by defining the block as the `reference_timestamp` bar's own high/low on the annotated instrument — the closest computable, same-instrument reading. Downstream agents should not attempt a cross-asset `reference_price − invalidation_level` subtraction.
- `broken_ts` is, by construction (`historical.py:80`, `index > created_ts`), always strictly after `created_ts`. So an SMT created **at** bar `t` (`created_ts == t`) is always valid at `t`; the invalidation bug only ever affects SMTs created at `t-1` or `t-2` (D-01).
- The "before" numbers for the D-09 methodology writeup already exist as the currently-published section 8 table — no snapshot step needed.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Continuous-magnitude features, session/time-of-day tags, and volume-anomaly measures were explicitly kept out (Phase 10 / RES-07), and micro/FVG SMT signals remain disabled at the scanner call.

</deferred>

---

*Phase: 9-SMT Geometry & Invalidation Honesty*
*Context gathered: 2026-07-12*
