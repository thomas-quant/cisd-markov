# Phase 7: Corrected Re-Validation of the Post-CISD Studies - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Re-run the two post-CISD studies — `post_cisd_context` and `candle1_followthrough` — end-to-end under Phase 6's harder evidence bar (Benjamini-Hochberg FDR correction + walk-forward validation), add an explicit reversal-barrier measurement to `post_cisd_context`'s `failed_gap_against` bucket, and publish a written, per-tag go/no-go verdict that gates Phase 8's modeling decision (ML-01).

These two studies have never been fully validated: the on-disk OOS manifest predates them entirely (zero OOS rows for either), so `output/validation_findings.csv` currently shows all 160 of their bucket-rows as `not-confirmed` purely because OOS data is absent — not because they failed. This phase closes that gap under the new corrected methodology, not the old one.

**Explicitly out of scope:** re-validating the other 14 already-published analyses under the corrected bar. Phase 6 deliberately left `determine_verdict()` / `build_reconcile_findings.py` untouched, and none of README's 8 existing Key Findings sections use the FDR/walk-forward-corrected bar yet. That remains true after this phase — see Decision D-01.

</domain>

<decisions>
## Implementation Decisions

### Corrected-Verdict Blast Radius
- **D-01:** The new corrected + walk-forward verdict logic is scoped **only** to `post_cisd_context` and `candle1_followthrough`. `determine_verdict()` / `build_reconcile_findings.py`'s existing same-side-of-50% logic for the other 14 analyses is **not** touched or upgraded in this phase. Matches the phase's literal scope and Phase 6's own "existing published numbers do not move" invariant.
- **D-02:** "Clears the corrected evidence bar" (the go/no-go criterion feeding Phase 8) requires **all three**: discovery-stage `corrected_pass` (FDR-significant AND min-n) **AND** `wf_verdict == wf-robust` (walk-forward majority pass) **AND** the sacred OOS rate on the same side of 0.50 as discovery. This is the strictest combination and matches the project's core value ("sample-size gated, CI, confirmed out-of-sample") plus Phase 6's added rigor. Two-of-three was explicitly rejected.
- **D-03:** The final go/no-go verdict is **rolled up per post-CISD tag** (e.g., "failed_gap_against: cleared" / "not cleared"), not reported separately per timeframe/instrument/direction combination. Roll-up rule: a tag clears the bar if a **majority** of its TF/instrument/direction buckets individually clear it (per D-02). This matches Phase 8's roadmap framing of gating on "the discrete post-CISD tags" as a whole. The underlying per-bucket manifest data (finest granularity) is still produced and retained — only the *published verdict* is rolled up.
- **D-04:** README gets a brief transparency note (in Key Findings intro or the existing "Validation Methodology" section) stating that the corrected bar currently applies only to the new post-CISD studies, and the other 8 published findings sections have not yet been re-evaluated under it. Keeps the README honest without re-touching those 8 sections' prose.

### Reversal Barrier (RES-04)
- **D-05:** The reversal barrier for `failed_gap_against` reuses the **identical lookahead window** as the existing continuation measurement — `barrier_hit_forward`'s `idx+2..idx+3` window (re-anchored past candle[1], `LOOKAHEAD=2`). Reversal = candle[0]'s opposite extreme (the stop side) hit before the target side within that same window. This makes continuation and reversal directly comparable, mutually exclusive outcomes measured on the exact same population (same `n`).
- **D-06:** All three outcomes must be exposed and reported: **continuation** (target hit first), **reversal** (stop hit first), and **neither** (window exhausted with no barrier hit). `barrier_hit_forward()` today collapses "stop hit" and "neither hit" into the same `False` return — the reversal barrier implementation needs its own explicit check that distinguishes stop-hit-first from timeout, so "reversed" is never silently conflated with "went nowhere."
- **D-07:** The reversal barrier is scoped to **`failed_gap_against` only**, per the literal roadmap wording. It is not extended to `failed_gap_with`, `failed_gap_flat`, or `candle2_past_candle1_wick` in this phase.

### Go/No-Go Verdict Publication
- **D-08:** The per-tag go/no-go verdict is published as a **new README.md section** (e.g. "Post-CISD Context — Corrected Re-Validation (v2.0)"), following the existing Key Findings badge convention (✓ CONFIRMED / ✗ NOT CONFIRMED / below-n style), since Phase 8's roadmap entry says it "opens by reading Phase 7's per-tag verdict" and every other finding in this project is published the same way. No separate dedicated verdict file was chosen.
- **D-09:** The underlying per-tag/per-bucket verdict numbers (corrected_pass, wf_verdict, OOS same-side, and the D-03 roll-up) are **script-generated** — a script reads the discovery, OOS, and walk-forward manifests and computes the verdict deterministically, mirroring `build_reconcile_findings.py`'s existing pattern. The README prose itself is still hand-authored from those numbers (matching how the existing 8 Key Findings sections are written today) — script-generated numbers, hand-written narrative.

### Sacred OOS Re-Run
- **D-10:** Re-running `python3 scripts/build_validation.py --oos` is necessary and accepted, even though it also recomputes OOS rows for the other 14 already-published analyses (their code path is unchanged since they were last evaluated, so the numbers should be bit-identical to what's currently published). If any of those 14 analyses' regenerated OOS numbers differ from what's already published, that must be treated as a real bug to investigate — never silently republished.
- **D-11:** No separate before/after snapshot step of the current (stale, untracked) OOS manifest is needed before re-running. The determinism argument in D-10 is trusted; no extra ceremony was requested.

### Claude's Discretion
- Exact file/function structure for the new verdict computation (e.g., whether it lives as a scoped addition inside `build_reconcile_findings.py`, a new sibling script, or inline in `build_validation.py`) — planner's call, following the project's existing "pure stdlib, no scipy" and single-responsibility function conventions.
- Exact bucket/column naming for the new reversal-barrier outcome tags (e.g. `failed_gap_against_reversal`, `failed_gap_against_neither`) — follow `compute_post_cisd_context`'s existing tag-naming pattern (`{ct: {tag: {total, runs}}}` shape) and update `chart_post_cisd_context`'s `_TAGS` list accordingly.
- Exact wording/placement of the D-04 README transparency disclaimer and the D-08 new README section — keep consistent with the existing "How to read these tables" / badge legend conventions already in README.md.
- Whether the D-09 verdict-computation script also emits an intermediate CSV artifact (for auditability) in addition to feeding the README prose — roadmap only requires the written verdict; exact artifact shape is a planning decision.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` — Phase 7 goal, success criteria (4 items), and Phase 8's dependency on Phase 7's verdict
- `.planning/REQUIREMENTS.md` — RES-04 (reversal barrier), RES-05 (corrected manifest regeneration); ML-01 (Phase 8) for what the verdict must support
- `.planning/PROJECT.md` — Key Decisions table (sacred chronological holdout, Wilson CI + min-n gate, "publish failures explicitly," behavior-preservation invariant)
- `.planning/phases/06-harder-evidence-bar-multiple-comparisons-correction-walk-for/06-CONTEXT.md` — Phase 6 decisions this phase builds on (D-01 through D-07 there): p-value test definition, BH correction scope/stage, walk-forward window scheme, per-fold MIN_N gating

### Existing code this phase extends
- `cisd_barriers.py:596` (`compute_post_cisd_context`) and `cisd_barriers.py:547` (`compute_candle1_followthrough`) — the two studies being re-validated
- `cisd_barriers.py:63` (`barrier_hit_forward`) — the barrier function the reversal barrier must mirror/extend
- `scripts/build_validation.py` — `build_manifest_rows` (generic dispatch already covers both studies via the `else` branch), `apply_bh_correction`, `evaluate_fold`, `walk_forward_verdict`, `_OOS_BANNER`
- `scripts/build_reconcile_findings.py` — `determine_verdict()`, the existing discovery+OOS merge/verdict pattern (D-01 says: extend narrowly, don't rewrite generically)
- `README.md` — "Key Findings" section (badge/verdict convention to follow for D-08) and "Validation Methodology — Harder Evidence Bar (v2.0)" section (Phase 6's existing methodology writeup, natural home for the D-04 disclaimer)

No external ADRs/specs beyond the project's own planning docs — requirements are fully captured in the decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `barrier_hit_forward()` (`cisd_barriers.py:63`) — re-anchored barrier check (window = idx+2..idx+3). The reversal barrier's stop-hit-first check is a natural sibling/variant of this function (D-05).
- `compute_post_cisd_context()` (`cisd_barriers.py:596`) — already returns the `{ct: {tag: {total, runs}}}` shape that `build_manifest_rows`'s generic branch consumes; the new reversal tag(s) fit into this same dict shape without touching the dispatch code in `build_validation.py`.
- `bh_correct()` / `apply_bh_correction()` / `evaluate_fold()` / `walk_forward_verdict()` (`scripts/build_validation.py`, added in Phase 6) — already run generically across every `ANALYSES` key, including `post_cisd_context` and `candle1_followthrough` (confirmed: both already appear with `corrected_pass`/`bh_q_value` columns in the current discovery manifest and with fold rows in the walk-forward manifest). No changes needed to the correction/walk-forward machinery itself — only to how the *verdict* is derived from it (D-01/D-02/D-09).
- `determine_verdict()` (`scripts/build_reconcile_findings.py:69`) — existing discovery+OOS same-side verdict logic; the new verdict computation should sit alongside this (not replace it), scoped per D-01.

### Established Patterns
- `chart_post_cisd_context` (`cisd_charts.py:336`) drives its bar rows from a hardcoded `_TAGS` list of `(tag, alpha)` pairs — adding the reversal outcome tags means extending this list, not restructuring the chart function.
- `build_manifest_rows()`'s per-key dispatch (`scripts/build_validation.py:195`) has an explicit `else` "Generic" branch handling `{dir: {tag: {total, runs}}}` shapes — both post-CISD studies already fall through to this branch today, confirmed by inspecting the live discovery/walk-forward manifest CSVs.
- README's Key Findings legend (`✓ CONFIRMED` / `✗ NOT CONFIRMED` / `below-n`) is the established badge vocabulary; D-08's new section should extend this vocabulary (e.g. a 4th "corrected + walk-forward confirmed" tier) rather than inventing an unrelated one.

### Integration Points
- `output/validation_manifest_discovery.csv` and `output/validation_manifest_walkforward.csv` already contain rows for both studies (verified live: 160 discovery rows, 640 walk-forward rows for `post_cisd_context` alone). Only `output/validation_manifest_oos.csv` is missing them — regenerating via `--oos` (D-10) is the integration point that completes the triple needed for D-02's verdict.
- New reversal-barrier tags need wiring through: `compute_post_cisd_context` → `chart_post_cisd_context`'s `_TAGS` → (generic branch, no changes needed) `build_manifest_rows` → the new D-09 verdict script.

</code_context>

<specifics>
## Specific Ideas

- The current `output/validation_findings.csv` mislabels all 160 `post_cisd_context`/`candle1_followthrough` bucket-rows as `"not-confirmed"` purely due to missing OOS data (verified live in this discussion) — this is the concrete gap the phase closes, not a sign either study actually failed.
- `docs/research_backlog.md` originally called this idea `post_cisd_reversal_context` — same underlying concept as RES-04, now formalized as a reversal-barrier bucket within the existing `post_cisd_context` study rather than a new standalone analysis.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (The "generic upgrade to all 14 analyses" option in Corrected-Verdict Blast Radius and the "extend reversal barrier to all buckets" option were both explicitly considered and declined, not deferred as future work — see D-01 and D-07.)

</deferred>

---

*Phase: 7-Corrected Re-Validation of the Post-CISD Studies*
*Context gathered: 2026-07-10*
