---
phase: 10-new-conditioning-features-magnitude-session-volume-anomaly
reviewed: 2026-07-13T00:00:00Z
depth: quick
files_reviewed: 9
files_reviewed_list:
  - cisd_data.py
  - cisd_barriers.py
  - cisd_charts.py
  - scripts/build_validation.py
  - scripts/build_conditioning_report.py
  - scripts/build_forward_returns.py
  - scripts/build_expectancy.py
  - tests/test_conditioning_features.py
  - tests/test_conditioning_no_drift.py
findings:
  critical: 0
  warning: 1
  info: 4
  total: 5
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-07-13
**Depth:** quick (pattern + targeted trace of Phase-10 additions only)
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed only the Phase-10 additions (via `git diff 1ec0f83..HEAD`) to the three
large modules plus the new/changed scripts and tests. The core math was traced
by hand: the new magnitude columns (`wick_distance_atr`, `swept_level`,
`sweep_depth_atr`, `fvg_gap_width`, `fvg_size_atr`), the FVG gap-width
derivations (mid0/mid1, both directions), the session minute-of-day partition,
and the slot-normalized `rvol`/`volume_zscore` baseline (trailing `shift(1)`
inside each time-of-day group — no lookahead) are all correct. CISD-gating and
NaN off-population gating in the seven new `compute_*` functions are correct, and
the `compute_wick_distance` `lo < ratio <= hi` boundary correctly places
`ratio == 0` in the "within wick" bucket.

The honesty invariant is respected on the gated path: the new columns are written
to fresh columns in `_annotate_cisd_research` without mutating any existing
column, so existing analyses' base rates stay byte-stable; `build_validation.py`
correctly TF-scopes `session` out of Daily/4H at both `all_keys` sites; and the
`build_conditioning_report.py` drift gate compares only base columns (excluding
BH/p-value by design) — and its `!=` comparison is safe because base columns are
never NaN (`wilson_ci` returns finite `(0.0, 0.0)` at n=0, `rate` defaults to
`0.0`).

No blockers found. One consistency warning and four low-severity observations.

## Warnings

### WR-01: `session` dimension exposed unscoped in forward-returns and expectancy (degenerate on Daily/4H)

**File:** `scripts/build_forward_returns.py:31,124,187-201,326-336` and `scripts/build_expectancy.py:58,82-84,181-200`
**Issue:** `build_validation.py` correctly excludes `session` from Daily/4H via
`ANALYSIS_META["session"].applies_to = ("1H", "15min")` (D-02: a session tag on a
multi-session bar is economically meaningless). The other two consumer scripts do
NOT apply that scoping. `session_tag` is derived from minute-of-day, and resampled
Daily bars are labeled at 00:00 (minute_of_day 0 -> `overnight`) while 4H bar
labels (00/04/08/12/16/20:00 ET) almost never fall inside the 09:30-10:30 RTH-open
window — so on Daily every event collapses to a single `overnight` bucket and on
4H the split is near-degenerate. The interactive `forward_returns.html` "Session"
filter and the three `session_*` expectancy cases therefore present a
split that is meaningless on those timeframes, and (for expectancy, which pools
across all TFs) silently loads all Daily events into `session_overnight`. For a
project whose thesis is "no lucky-bucket mining / honest slices," an unscoped
degenerate dimension in the published exploratory artifacts is a real consistency
gap versus the gated manifest.
**Fix:** Mirror the manifest's TF-scoping. Either restrict the session
family/cases to intraday frames when building these outputs, or annotate the
degenerate Daily/4H session buckets as such so a researcher cannot read an edge
off a single collapsed bucket. Minimal option: in `build_forward_returns.py`,
only emit the `session` family for 1H/15min datasets; in `build_expectancy.py`,
exclude Daily/4H events from the `session_*` masks (or label them explicitly).

## Info

### IN-01: `compute_wick_distance` docstring overstates exact reconciliation with `compute_wick`

**File:** `cisd_barriers.py:229-247` (docstring), reconciliation logic
**Issue:** The docstring states the two `>0` bins "recover compute_wick's
past_wick total exactly" (D-06). That identity only holds when every CISD has a
valid ATR. `wick_distance_atr` is NaN during the ATR(14) warm-up (first ~13 bars
of each resampled frame), so any CISD firing in that window is counted by
`compute_wick` (which does not require ATR) but dropped by `compute_wick_distance`
(NaN ratio skipped). The reconciliation test only passes because its fixture
forces a 20-bar monotonic warm-up with no early CISDs; on real data the totals can
differ by the count of pre-warm-up CISDs. This is a conditionally-true claim, not a
runtime miscount — both analyses are individually correct.
**Fix:** Soften the docstring to note the identity holds "for CISDs with a defined
ATR (i.e. after the ATR(14) warm-up)."

### IN-02: Lowest bin lower-bound of `0` silently drops any negative ratio

**File:** `cisd_barriers.py` `compute_sweep_depth`, `compute_fvg_size`,
`compute_effort_result`, `compute_rvol` (BINS start at `(0, ...)`)
**Issue:** These four use `lo <= ratio < hi` with the first bin lower bound at
literal `0`. A value `< 0` matches no bin, so the `break` never fires and the row
is silently uncounted (contributes to no bucket total). Today all four ratios are
non-negative by construction (`sweep_depth` > 0 for a valid directional sweep,
`fvg_size`/`vol_per_range`/`rvol` >= 0), so nothing is dropped — but it is a
latent fragility: a future annotation change producing a small negative (e.g.
float rounding) would vanish silently rather than error or land in an edge bin.
**Fix:** Set the lowest bin lower bound to `-1e18` (as `wick_distance`/`zscore`
already do) so the bins are exhaustive, or assert non-negativity.

### IN-03: Frozen-bin outcome-blindness is a process claim, not statically verifiable

**File:** `cisd_barriers.py` `compute_effort_result`/`compute_rvol`/`compute_volume_zscore` (frozen percentile bins)
**Issue:** The bin edges are documented as discovery-slice percentiles chosen
"outcome-blind" on 2026-07-12. This is the honesty invariant's crux, but static
review cannot confirm the percentiles were computed on the discovery slice with no
peek at barrier outcomes. Flagged so it is verified against the derivation
artifact, not assumed.
**Fix:** Confirm the freezing procedure (index < OOS_START, no outcome
conditioning) is recorded/reproducible in the phase artifacts; no code change if so.

### IN-04: `_annotate_cisd_research` requires a DatetimeIndex for the new session/volume columns

**File:** `cisd_data.py:379` (`idx_ax.hour`/`idx_ax.minute`)
**Issue:** The session and slot-baseline blocks call `idx_ax.hour` /
`idx_ax.minute`, which raise `AttributeError` on a non-DatetimeIndex. Production
always passes a DatetimeIndex (resample output) and all current direct-call tests
use `pd.date_range`, so this is not a live defect — but the function previously
tolerated any index for its other columns, so this is a newly-introduced implicit
precondition worth documenting.
**Fix:** Optionally guard with a clear error if `not isinstance(df.index,
pd.DatetimeIndex)`, or note the precondition in the docstring.

---

_Reviewed: 2026-07-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
