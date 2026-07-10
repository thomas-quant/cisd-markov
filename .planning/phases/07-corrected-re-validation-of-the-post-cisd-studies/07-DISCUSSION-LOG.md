# Phase 7: Corrected Re-Validation of the Post-CISD Studies - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-10
**Phase:** 7-Corrected Re-Validation of the Post-CISD Studies
**Areas discussed:** Corrected-verdict blast radius, Reversal barrier definition, Go/no-go verdict location, Sacred OOS re-run

---

## Corrected-Verdict Blast Radius

### Q: Should the FDR+walk-forward-corrected verdict logic be scoped only to post_cisd_context/candle1_followthrough, or also generically upgrade determine_verdict() for all 14 already-published analyses?

| Option | Description | Selected |
|--------|-------------|----------|
| Scoped to the 2 studies only | New/extended verdict path touches only post_cisd_context and candle1_followthrough. Matches the phase's literal title and Phase 6's "existing published numbers do not move" invariant. | ✓ |
| Generic upgrade for all analyses | Rewrites determine_verdict() to require corrected_pass + wf-robust for every analysis. More architecturally consistent but changes verdict labels for the other 14 analyses' CSV rows. | |
| You decide | | |

**User's choice:** Scoped to the 2 studies only.

### Q: What must a bucket clear to count as "a real, corrected, walk-forward-confirmed effect" (the go/no-go bar for Phase 8)?

| Option | Description | Selected |
|--------|-------------|----------|
| All three: corrected + walk-forward + OOS | corrected_pass AND wf-robust AND OOS same-side of 50%. Strictest combination. | ✓ |
| Two of three: corrected + walk-forward only | corrected_pass AND wf-robust required; OOS confirmation reported but not required. | |
| You decide | | |

**User's choice:** All three.

### Q: Should the final go/no-go verdict be judged per bucket (finest granularity) or rolled up to one verdict per post-CISD tag?

| Option | Description | Selected |
|--------|-------------|----------|
| Rolled up per tag | One verdict per tag, based on a majority of its TF/instrument/direction buckets passing. | ✓ |
| Per bucket (finest granularity) | A separate go/no-go per tag+timeframe+instrument+direction combination. | |
| You decide | | |

**User's choice:** Rolled up per tag.

### Q: Should Phase 7 add a short transparency note to README's Key Findings section stating the other 8 published analyses have not yet been re-evaluated under the Phase 6 corrected bar?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, add a brief disclaimer | One or two sentences noting the corrected bar currently applies only to the new post-CISD studies. | ✓ |
| No, out of scope | Leave README's existing Key Findings section untouched entirely. | |
| You decide | | |

**User's choice:** Yes, add a brief disclaimer.

**Notes:** This area surfaced the most consequential decision in the phase — how far the new corrected/walk-forward methodology reaches into already-published findings. Confirmed by direct inspection of `output/validation_findings.csv` and `output/validation_manifest_oos.csv` that the two post-CISD studies currently show `not-confirmed` purely due to missing OOS rows (the OOS manifest predates them), not because they failed.

---

## Reversal Barrier Definition

### Q: Should the reversal barrier for failed_gap_against use the identical lookahead window as the existing continuation measurement (barrier_hit_forward: candle[2]+candle[3])?

| Option | Description | Selected |
|--------|-------------|----------|
| Same window as continuation | Reversal = opposite extreme hit before target, within the same idx+2..idx+3 window. Continuation/reversal become mutually exclusive outcomes on the same n. | ✓ |
| Different/longer window | A separate, possibly longer lookahead tuned for reversal. Breaks comparability. | |
| You decide | | |

**User's choice:** Same window as continuation.

### Q: Does the reversal barrier need to also expose a distinct "neither" (timed out) outcome, or is a simple continuation-vs-reversal split sufficient?

| Option | Description | Selected |
|--------|-------------|----------|
| Expose all three outcomes | Continuation, reversal, and neither (1 - continuation - reversal) all reported. | ✓ |
| Binary split only | Just report reversal rate as a new bucket alongside continuation; don't surface "neither" separately. | |
| You decide | | |

**User's choice:** Expose all three outcomes.

### Q: Should the reversal barrier stay scoped to failed_gap_against only, or extend to the other post_cisd_context buckets too?

| Option | Description | Selected |
|--------|-------------|----------|
| failed_gap_against only | Matches the literal roadmap success criterion. | ✓ |
| All post_cisd_context buckets | Broader comparative picture, beyond literal roadmap wording. | |
| You decide | | |

**User's choice:** failed_gap_against only.

**Notes:** Confirmed via code inspection that `barrier_hit_forward()` currently collapses "stop hit" and "neither hit" into the same `False` return — the reversal barrier implementation needs its own explicit stop-hit-first check to keep these distinguishable (D-06).

---

## Go/No-Go Verdict Location

### Q: Where should Phase 7's written, per-tag go/no-go verdict live so Phase 8 can read it as an explicit gate?

| Option | Description | Selected |
|--------|-------------|----------|
| New README section | Follows the existing Key Findings badge convention. | ✓ |
| Dedicated verdict file | A standalone machine/human-readable file separate from README. | |
| Both | Dedicated artifact plus a README summary/link. | |
| You decide | | |

**User's choice:** New README section.

### Q: Should the go/no-go verdict artifact be regenerated automatically by a script, or hand-written after review?

| Option | Description | Selected |
|--------|-------------|----------|
| Script-generated | Deterministic, reproducible, matches build_reconcile_findings.py's existing pattern. | ✓ |
| Hand-written after review | Numbers computed by scripts, but final prose judgment written by hand. | |
| You decide | | |

**User's choice:** Script-generated.

**Notes:** Reconciled as: numbers are script-generated, but the README prose narrative itself is still hand-authored from those numbers — consistent with how the existing 8 Key Findings sections work today (no contradiction between "script-generated" and "README prose").

---

## Sacred OOS Re-Run

### Q: Is it acceptable to re-run --oos, which is required for the 2 new studies but also deterministically recomputes OOS rows for the other 14 already-published analyses?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, re-run and verify identical | If any of the 14 analyses' regenerated numbers differ from published, treat as a real bug to investigate. | ✓ |
| Yes, but only if a safety check confirms no drift | Same, but make the identical-numbers check a hard automated gate. | |
| You decide | | |

**User's choice:** Yes, re-run and verify identical.

### Q: Should Phase 7's plan snapshot the pre-re-run OOS numbers for the 14 existing analyses as a before/after safety comparison?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, snapshot before re-running | Cheap insurance given the sacred-OOS discipline this project cares about. | |
| No, not necessary | Trust the code is deterministic and unchanged; skip extra process overhead. | ✓ |
| You decide | | |

**User's choice:** No, not necessary.

**Notes:** Confirmed live that `output/validation_manifest_oos.csv` is gitignored/untracked and stale (last regenerated before the two post-CISD studies were wired into `ANALYSES`), which is why it has zero rows for them today.

---

## Claude's Discretion

- Exact file/function structure for the new verdict computation (scoped addition to `build_reconcile_findings.py` vs. a new sibling script vs. inline in `build_validation.py`).
- Exact bucket/column naming for the new reversal-barrier outcome tags, and how `chart_post_cisd_context`'s `_TAGS` list is extended.
- Exact wording/placement of the README transparency disclaimer and the new go/no-go README section.
- Whether the verdict-computation script also emits an intermediate CSV artifact for auditability, beyond feeding the README prose.

## Deferred Ideas

None — discussion stayed within phase scope. Two options were explicitly considered and declined rather than deferred: generically upgrading `determine_verdict()` for all 14 analyses, and extending the reversal barrier beyond `failed_gap_against`.
