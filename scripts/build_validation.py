"""Validation harness — discovery/OOS slicing, Wilson CI, sample-size gating, manifest CSV."""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cisd_analysis import (
    ANALYSES, ANALYSIS_META, INSTRUMENTS, MAX_CONSEC, TIMEFRAMES, OOS_START, MIN_N, CI_LEVEL,
    WALK_FORWARD_FOLDS, DATA_END, HOLDOUT_END, attach_geo_baseline, is_diagnostic,
    load_1m, resample_ohlcv, prepare_pair, _load_scan_smts_historical,
)

SLICES_PATH   = REPO_ROOT / "output" / "validation_slices.csv"
MANIFEST_PATH = REPO_ROOT / "output" / "validation_manifest.csv"  # legacy name (kept for import compat)


def _manifest_path(slice_label: str) -> Path:
    """Return the slice-suffixed manifest path (e.g. validation_manifest_discovery.csv)."""
    return REPO_ROOT / "output" / f"validation_manifest_{slice_label}.csv"

# ── Sacred OOS banner ─────────────────────────────────────────────────────────

_OOS_BANNER = """
╔══════════════════════════════════════════════════════════════╗
║  ⚠  YOU ARE SPENDING YOUR ONE SACRED OOS EVALUATION  ⚠     ║
║  This run will operate on the held-out test set.            ║
║  This is a sacred evaluation — treat it as a final exam,    ║
║  not a sandbox. Results will be added to the manifest.      ║
╚══════════════════════════════════════════════════════════════╝
"""


_HOLDOUT_BANNER = f"""
╔══════════════════════════════════════════════════════════════╗
║  ⚠  YOU ARE SPENDING THE FRESH HOLDOUT  ⚠                  ║
║  Bars after DATA_END ({DATA_END}) through {HOLDOUT_END}.     ║
║  Run it once, after the discovery verdicts are committed.   ║
╚══════════════════════════════════════════════════════════════╝
"""


# ── CI helpers ───────────────────────────────────────────────────────────────

# math.erfinv is available in Python 3.13+; provide a pure-stdlib fallback for 3.12.
try:
    _erfinv = math.erfinv  # type: ignore[attr-defined]
except AttributeError:
    def _erfinv(x: float) -> float:
        """Inverse error function: returns y such that erf(y) == x.

        Uses Winitzki's approximation (a=0.147) as the initial estimate, then
        refines with 3 Halley iterations. Accurate to ~12 significant figures.
        Matches math.erfinv results to within 1 ULP on all tested inputs.
        """
        _SQRT_PI = math.sqrt(math.pi)
        _A = 0.147
        sgn = math.copysign(1.0, x)
        t = 1.0 - x * x
        if t <= 0.0:
            return sgn * math.inf
        ln_t = math.log(t)
        c = 2.0 / (math.pi * _A) + ln_t / 2.0
        y = sgn * math.sqrt(math.sqrt(c * c - ln_t / _A) - c)
        # Halley refinement: y_{n+1} = y - f(y) / (f'(y) + y·f(y))
        # where f(y) = erf(y) - x and f'(y) = (2/√π)·exp(-y²)
        for _ in range(3):
            f  = math.erf(y) - x
            fp = (2.0 / _SQRT_PI) * math.exp(-y * y)
            y -= f / (fp + y * f)
        return y


def wilson_ci(n: int, k: int, level: float = CI_LEVEL) -> tuple[float, float]:
    """Wilson score CI for k successes in n trials. Returns (low, high) in [0, 1].

    Uses math.erfinv (stdlib, Python 3.13+) or a pure-stdlib fallback — no external deps.
    For level=0.95: z = sqrt(2) * erfinv(0.95) ≈ 1.9600.
    Returns (0.0, 0.0) for n=0.

    Derivation: erfinv(level) gives x where erf(x) = level; z = sqrt(2)*x satisfies
    Φ(z) = (1+level)/2, which is the standard z for a two-sided CI at confidence level
    `level`. For level=0.95: erfinv(0.95) ≈ 1.38590, z ≈ 1.96003 (matches
    the standard normal 97.5th percentile to 5 sig figs).
    Wilson formula: centre = (p̂ + z²/2n) / (1 + z²/n),
                    margin  = z·√(p̂(1-p̂)/n + z²/4n²) / (1 + z²/n).
    """
    if n == 0:
        return (0.0, 0.0)
    z = math.sqrt(2) * _erfinv(level)
    p_hat = k / n
    z2 = z * z
    denom  = 1.0 + z2 / n
    centre = (p_hat + z2 / (2 * n)) / denom
    margin = z * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def n_gate(n: int, min_n: int = MIN_N) -> bool:
    """Return True if n meets the minimum sample size threshold."""
    return n >= min_n


def p_value_vs_half(n: int, k: int) -> float:
    """Two-sided significance test of H0: rate = 0.5 (D-01: the fixed coin-flip
    null, NOT a bucket's own parent/baseline rate — matches the same-side-of-0.5
    framing already used in README.md and determine_verdict()).

    Uses a normal approximation to the binomial: under H0, k successes in n
    trials is approximately Normal(n/2, n/4), so the z-statistic is
        z = (k - n/2) / sqrt(n/4) = (2*k - n) / sqrt(n).
    The two-sided p-value is P(|Z| >= |z|) for a standard normal Z, which by
    the erfc/normal-tail identity equals erfc(|z| / sqrt(2)):
        P(|Z| >= x) = erfc(x / sqrt(2)).

    Returns 1.0 when n == 0 (no evidence against the null — guard clause,
    mirrors wilson_ci's n==0 handling: no observations, no significance).

    Examples
    --------
    p_value_vs_half(100, 50) == 1.0     (rate exactly 0.5 -> z=0 -> erfc(0)=1.0)
    p_value_vs_half(100, 60) ~= 0.0455  (z=(120-100)/10=2.0 -> erfc(2/sqrt(2)))
    """
    if n == 0:
        return 1.0
    z = (2 * k - n) / math.sqrt(n)
    return math.erfc(abs(z) / math.sqrt(2))


def bh_correct(pvalues: list[float], fdr: float = 1 - CI_LEVEL) -> list[dict]:
    """Benjamini-Hochberg step-up FDR correction over ONE global family (D-02:
    every bucket across every analysis x timeframe x instrument x direction is
    corrected together in a single pass — never grouped per-analysis-key).

    Default fdr = 1 - CI_LEVEL = 0.05.

    Algorithm
    ---------
    Sort (p_value, original_index) ascending. For m = len(pvalues), rank i is
    1-based (i = 1..m). The BH critical value at rank i is (i/m)*fdr. The BH
    cutoff rank is the LARGEST i such that p_(i) <= (i/m)*fdr; every sorted
    rank <= that cutoff rank is significant (step-up procedure).

    BH-adjusted q-values are computed by the standard monotone step-up,
    walking from the largest rank down to the smallest:
        q_(m) = p_(m)
        q_(i) = min(q_(i+1), (m/i) * p_(i))   for i = m-1 .. 1
    each q is clamped to <= 1.0. This guarantees q-values are non-decreasing
    along ascending p_value order.

    Returns
    -------
    list[dict]
        One dict per input p-value, in ORIGINAL input order, with keys:
        ``bh_rank`` (int, 1-based rank in the sorted family),
        ``bh_q_value`` (float, rounded to 6dp),
        ``bh_significant`` (bool).
        Returns [] for an empty input list (guard clause — no family, no
        correction to apply).
    """
    m = len(pvalues)
    if m == 0:
        return []

    # Indices sorted by ascending p-value (ties broken by original index —
    # stable sort keeps input order for equal p-values).
    order = sorted(range(m), key=lambda i: pvalues[i])

    # Largest rank i (1-based) with p_(i) <= (i/m)*fdr.
    cutoff_rank = 0
    for rank, idx in enumerate(order, start=1):
        if pvalues[idx] <= (rank / m) * fdr:
            cutoff_rank = rank

    # Monotone q-values via the step-up formula, walking from largest rank down.
    q_sorted: list[float] = [0.0] * m
    prev_q = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        raw_q = (m / rank) * pvalues[idx]
        prev_q = min(prev_q, raw_q)
        q_sorted[rank - 1] = min(prev_q, 1.0)

    results: list[dict] = [None] * m  # type: ignore[list-item]
    for rank, idx in enumerate(order, start=1):
        results[idx] = {
            "bh_rank": rank,
            "bh_q_value": round(q_sorted[rank - 1], 6),
            "bh_significant": rank <= cutoff_rank,
        }
    return results


# GEO_MIN_EFFECT: smallest |lift| (rate points) the user cares about. A
# non-significant bucket is only called "within-3pp" when its 90% CI of lift
# sits inside +/-GEO_MIN_EFFECT (TOST equivalence at alpha=0.05, per bucket,
# uncorrected); otherwise it is "inconclusive". geo_mde is the lift detectable
# with 80% power at two-sided alpha=0.05 (uncorrected) at the bucket's SE.
GEO_MIN_EFFECT = 0.03
_Z_TOST  = 1.6448536269514722   # one-sided 95%
_Z_MDE   = 1.959963984540054 + 0.8416212335729143

POOLED = "NQ+ES"   # instrument label of the pooled headline rows


def geo_stats(cell: dict | None) -> dict[str, object]:
    """Corridor-position null (quick task 260929-mkg) for one bucket cell.

    H0: the bucket's hits equal the sum of its events' corridor/ATR-regime
    baselines (cisd_barriers.attach_geo_baseline), E = sum(p_i). Events are
    NOT independent (overlapping windows, same-day clustering, NQ/ES
    co-movement in pooled rows), so the variance is cluster-robust over
    cisd_barriers.geo_cluster_ids clusters (session day intraday, session week
    Daily/4H): V_cl = G/(G-1) * sum_c (sum_{i in c} (hit_i - p_i))^2. The test
    uses V = max(V_cl, V_iid) with V_iid = sum p_i(1-p_i) — never credits
    negative within-cluster correlation. geo_deff = V_cl / V_iid (design
    effect), geo_n_eff = geo_n * V_iid / V, geo_se = sqrt(V) / geo_n.
    geo_z_iid keeps the old independence z for provenance only.

    Returns NaN fields when the cell carries no baseline (non-barrier
    outcomes such as fvg_hold / reversal counts, or significance's own event set).
    """
    blank = {"geo_n": 0, "geo_expected_rate": math.nan, "geo_lift": math.nan,
             "geo_clusters": 0, "geo_deff": math.nan, "geo_n_eff": math.nan,
             "geo_se": math.nan, "geo_z": math.nan, "geo_z_iid": math.nan,
             "geo_p_value": math.nan, "geo_mde": math.nan, "geo_equiv": False}
    if not cell or not cell.get("geo_n"):
        return blank
    n, hits = cell["geo_n"], cell["geo_runs"]
    expected, var_iid = cell["expected"], cell["expected_var"]
    resid = list(cell.get("clusters", {}).values())
    g = len(resid)
    lift = hits / n - expected / n
    var_cl = g / (g - 1) * sum(r * r for r in resid) if g >= 2 else math.nan
    out = dict(blank, geo_n=n, geo_expected_rate=round(expected / n, 6),
               geo_lift=round(lift, 6), geo_clusters=g)
    if not (var_iid > 0 and var_cl == var_cl):
        return out
    var = max(var_cl, var_iid)
    se = math.sqrt(var) / n
    z = (hits - expected) / math.sqrt(var)
    z_iid = (hits - expected) / math.sqrt(var_iid)
    out.update(
        geo_deff=round(var_cl / var_iid, 4),
        geo_n_eff=round(n * var_iid / var, 1),
        geo_se=round(se, 6),
        geo_z=round(z, 4),
        geo_z_iid=round(z_iid, 4),
        geo_p_value=round(math.erfc(abs(z) / math.sqrt(2)), 6),
        geo_mde=round(_Z_MDE * se, 6),
        geo_equiv=abs(lift) + _Z_TOST * se < GEO_MIN_EFFECT,
    )
    return out


def pool_cells(cells: list[dict | None]) -> dict | None:
    """Merge per-instrument cells into one pooled NQ+ES cell. Cluster ids are
    shared calendar ids, so same-day NQ and ES events land in one cluster."""
    cells = [c for c in cells if c]
    if not cells:
        return None
    out: dict = {}
    for c in cells:
        for key, val in c.items():
            if key == "clusters":
                merged = out.setdefault("clusters", {})
                for cid, r in val.items():
                    merged[cid] = merged.get(cid, 0.0) + r
            else:
                out[key] = out.get(key, 0) + val
    return out


# ── Manifest ─────────────────────────────────────────────────────────────────

def build_manifest_rows(
    keys: list[str],
    df_nq: pd.DataFrame,
    df_es: pd.DataFrame,
    tf_label: str,
    slice_label: str,
) -> list[dict[str, object]]:
    """Return tidy long manifest rows for all buckets produced by keys on the given enriched frames.

    Columns: analysis, timeframe, instrument, direction, bucket,
             rate, n, successes, ci_low, ci_high, ci_method, min_n_pass, slice,
             p_value.
    rate/ci_low/ci_high are proportions in [0, 1] (NOT percentages).
    Buckets with n < MIN_N appear with min_n_pass=False — never dropped.
    p_value tests H0: rate = 0.5 (D-01) and is emitted for every bucket
    regardless of slice; the BH correction columns (bh_rank, bh_q_value,
    bh_significant, corrected_pass) are added separately by
    apply_bh_correction(), discovery-slice only (D-03).

    Corrected null (quick task 260929-mkg): each frame gets corridor-position
    baselines attached per call (i.e. per slice / fold chunk), and every row
    carries diagnostic + geo_n/geo_expected_rate/geo_lift/geo_z/geo_p_value
    (see geo_stats). These — not p_value — are what verdicts should read.
    """
    rows: list[dict[str, object]] = []

    def _with_geo(df: pd.DataFrame) -> pd.DataFrame:
        try:
            return attach_geo_baseline(df)
        except (KeyError, ValueError) as exc:
            print(f"[warn] geo baseline unavailable ({type(exc).__name__}: {exc})")
            return df

    frames = (("NQ", _with_geo(df_nq)), ("ES", _with_geo(df_es)))
    pool: dict[tuple[str, str, str], list[tuple[int, int, dict | None]]] = {}

    def emit(analysis: str, instrument: str, direction: str, bucket: str, n: int, k: int,
             cell: dict | None = None) -> None:
        if instrument != POOLED:
            pool.setdefault((analysis, direction, bucket), []).append((n, k, cell))
        if k > n:
            print(f"[warn] {analysis}/{instrument}/{direction}/{bucket}: k={k} > n={n}; skipping")
            return
        lo, hi = wilson_ci(n, k)
        rows.append({
            "analysis":   analysis,
            "timeframe":  tf_label,
            "instrument": instrument,
            "direction":  direction,
            "bucket":     bucket,
            "rate":       round(k / n, 6) if n > 0 else 0.0,
            "n":          n,
            "successes":  k,
            "ci_low":     round(lo, 6),
            "ci_high":    round(hi, 6),
            "ci_method":  "wilson",
            "min_n_pass": n_gate(n),
            "slice":      slice_label,
            "p_value":    round(p_value_vs_half(n, k), 6),
            "diagnostic": is_diagnostic(analysis, bucket),
            **geo_stats(cell),
        })

    for key in keys:
        if key not in ANALYSES:
            continue
        label, compute_fn, _ = ANALYSES[key]
        for instrument, df in frames:
            try:
                data = compute_fn(df)
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[warn] {key}/{instrument}/{tf_label}: compute failed"
                    f" ({type(exc).__name__}: {exc}); skipping"
                )
                continue  # degrade gracefully on empty/missing slice

            if key in ("basic", "significance"):
                for ct in ("bullish", "bearish"):
                    emit(key, instrument, ct, "all",
                         data["totals"][ct], data["runs"][ct],
                         data.get("geo", {}).get(ct))

            elif key == "mc":
                for ct in ("bullish", "bearish"):
                    for n in range(1, MAX_CONSEC + 1):
                        d = data[ct][n]
                        emit(key, instrument, ct, f"{n}_consecutive",
                             d["total"], d["runs"], d)

            elif key == "wick":
                for ct in ("bullish", "bearish"):
                    for grp in ("past_wick", "within_wick"):
                        d = data[ct][grp]
                        emit(key, instrument, ct, grp, d["total"], d["runs"], d)

            elif key == "combined":
                for ct in ("bullish", "bearish"):
                    for nc in range(1, MAX_CONSEC + 1):
                        for grp in ("past_wick", "within_wick"):
                            d = data[ct][nc][grp]
                            emit(key, instrument, ct, f"{nc}c_{grp}",
                                 d["total"], d["runs"], d)

            elif key in ("volume", "candle_size", "size_cross"):
                for ct in ("bullish", "bearish"):
                    for bucket_lbl, d in data[ct].items():
                        emit(key, instrument, ct, bucket_lbl,
                             d["total"], d["runs"], d)

            elif key == "fvg_hold":
                for ct in ("bullish", "bearish"):
                    for bucket in ("mid0", "mid1"):
                        for mode, d in data[ct][bucket].items():
                            emit(key, instrument, ct, f"{bucket}_{mode}",
                                 d["total"], d["held"])  # note: "held" not "runs"

            elif key == "cisd_fvg_interaction":
                for ct in ("bullish", "bearish"):
                    for bucket in ("mid0", "mid1"):
                        for mode, state_map in data[ct][bucket].items():
                            for state, d in state_map.items():
                                emit(key, instrument, ct, f"{bucket}_{mode}_{state}",
                                     d["total"], d["runs"], d)

            else:
                # Generic: smt_cisd, cisd_fvg, sweep, sssf_swing
                # shape: {dir: {tag: {"total", "runs"}}}
                for ct in ("bullish", "bearish"):
                    for tag, d in data[ct].items():
                        emit(key, instrument, ct, tag, d["total"], d["runs"], d)

    # Pooled NQ+ES headline rows: one test per bucket, NQ and ES events on the
    # same day in one cluster. Only buckets present for both instruments.
    for (analysis, direction, bucket), parts in pool.items():
        if len(parts) != 2:
            continue
        emit(analysis, POOLED, direction, bucket,
             sum(p[0] for p in parts), sum(p[1] for p in parts),
             pool_cells([p[2] for p in parts]))

    return rows


def apply_bh_correction(rows: list[dict[str, object]]) -> None:
    """Apply one global BH correction (D-02) to *rows* in place, discovery-stage
    only (D-03 — the caller is responsible for gating this call to the
    discovery slice; this function itself does not check `slice`).

    The BH family is every row with n >= 1 (a computable p-value) — one
    global family spanning all analyses/timeframes/instruments/directions in
    a single pass, never grouped per-analysis-key (D-02).

    Adds four keys to family rows:
        bh_rank         — 1-based rank in the sorted family (int)
        bh_q_value      — BH-adjusted q-value (float, rounded to 6dp)
        bh_significant  — whether the bucket clears the BH cutoff (bool)
        corrected_pass  — bool(min_n_pass) and bh_significant (the harder
                           evidence bar: a bucket must clear BOTH the
                           sample-size gate AND FDR significance)

    Pooled NQ+ES rows are outside this legacy family, so its numbers do not
    move when pooled rows are added.

    Rows outside the family (n < 1) get bh_rank="", bh_q_value="",
    bh_significant=False, corrected_pass=False.

    Mutates *rows* in place; only ADDS keys — never renames, reorders, or
    removes any pre-existing key (additive-only, per D-03 / roadmap success
    criterion 3).
    """
    family_indices = [i for i, row in enumerate(rows)
                      if row.get("n", 0) >= 1 and row.get("instrument") != POOLED]
    family_pvalues = [rows[i]["p_value"] for i in family_indices]
    corrected = bh_correct(family_pvalues)

    for row in rows:
        row["bh_rank"] = ""
        row["bh_q_value"] = ""
        row["bh_significant"] = False
        row["corrected_pass"] = False

    for idx, result in zip(family_indices, corrected):
        row = rows[idx]
        row["bh_rank"] = result["bh_rank"]
        row["bh_q_value"] = result["bh_q_value"]
        row["bh_significant"] = result["bh_significant"]
        row["corrected_pass"] = bool(row["min_n_pass"]) and result["bh_significant"]


def geo_family_verdict(row: dict[str, object], bh_significant: bool) -> str:
    """Verdict for one row of the geo family (see apply_geo_bh_correction)."""
    n_eff = row.get("geo_n_eff")
    if not (isinstance(n_eff, float) and math.isfinite(n_eff)) or not n_gate(n_eff):
        return "below-n"
    if bh_significant:
        return "above-baseline" if row["geo_lift"] > 0 else "below-baseline"
    return f"within-{round(GEO_MIN_EFFECT * 100)}pp" if row.get("geo_equiv") else "inconclusive"


def apply_geo_bh_correction(rows: list[dict[str, object]]) -> None:
    """BH-FDR over the corridor/ATR-regime null (quick task 260929-mkg),
    discovery-stage only, one global family like apply_bh_correction.

    Family = pooled NQ+ES, non-diagnostic rows with a finite geo_p_value —
    one hypothesis per bucket, so NQ and ES never count as two confirmations.
    Per-instrument rows keep their clustered geo stats as description and get
    geo_verdict "per-instrument". Adds geo_bh_q_value, geo_bh_significant,
    geo_corrected_pass (geo_n_eff >= MIN_N and BH-significant) and
    geo_verdict: "above-baseline" / "below-baseline" (corrected pass, by sign
    of geo_lift), "within-3pp" (not significant and TOST-equivalent to zero
    within GEO_MIN_EFFECT), "inconclusive" (neither), "below-n" (geo_n_eff <
    MIN_N), "diagnostic" (outcome-leaking bucket, never tested),
    "no-baseline" or "per-instrument".
    """
    family = [
        i for i, row in enumerate(rows)
        if row.get("instrument") == POOLED and not row.get("diagnostic")
        and isinstance(row.get("geo_p_value"), float) and math.isfinite(row["geo_p_value"])
    ]
    corrected = bh_correct([rows[i]["geo_p_value"] for i in family])

    for row in rows:
        row["geo_bh_q_value"] = ""
        row["geo_bh_significant"] = False
        row["geo_corrected_pass"] = False
        if row.get("diagnostic"):
            row["geo_verdict"] = "diagnostic"
        elif row.get("instrument") != POOLED:
            row["geo_verdict"] = "per-instrument"
        else:
            row["geo_verdict"] = "no-baseline"

    for idx, result in zip(family, corrected):
        row = rows[idx]
        row["geo_bh_q_value"] = result["bh_q_value"]
        row["geo_bh_significant"] = result["bh_significant"]
        row["geo_verdict"] = geo_family_verdict(row, result["bh_significant"])
        row["geo_corrected_pass"] = row["geo_verdict"] in ("above-baseline", "below-baseline")


# ── Slicing ───────────────────────────────────────────────────────────────────

def slice_df(df: pd.DataFrame, oos: bool = False) -> pd.DataFrame:
    """Return the discovery or OOS slice of *df* based on OOS_START.

    Discovery slice: df.index < OOS_START  (default)
    OOS slice:       df.index >= OOS_START  (--oos flag)

    Returns a copy to prevent SettingWithCopyWarning on downstream writes.
    """
    boundary = pd.Timestamp(OOS_START)
    if oos:
        return df[df.index >= boundary].copy()
    return df[df.index < boundary].copy()


def slice_holdout(df: pd.DataFrame) -> pd.DataFrame:
    """Return the fresh holdout: bars after DATA_END (the frame must have been
    built from load_1m(..., end=HOLDOUT_END) so it extends past DATA_END)."""
    return df[df.index >= pd.Timestamp(DATA_END) + pd.Timedelta(days=1)].copy()


def slice_fold(
    df: pd.DataFrame, train_end: str, test_end: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (train, test) slices for one walk-forward fold, confined to the
    discovery region (D-04: walk-forward never touches the sacred OOS slice —
    even if *test_end* is a date at or after OOS_START, the result is clamped
    to df.index < OOS_START via slice_df(df, oos=False) below).

    train: discovery bars with df.index < train_end (anchored/expanding — D-05:
           every fold trains on all discovery history up to its boundary, so
           the train slice grows monotonically as train_end advances).
    test:  discovery bars with train_end <= df.index < test_end.

    Both returned frames are copies (mirrors slice_df's copy-on-return
    convention to prevent SettingWithCopyWarning on downstream writes).
    """
    disc = slice_df(df, oos=False)
    train_boundary = pd.Timestamp(train_end)
    test_boundary = pd.Timestamp(test_end)
    train = disc[disc.index < train_boundary].copy()
    test = disc[(disc.index >= train_boundary) & (disc.index < test_boundary)].copy()
    return train, test


# ── Walk-forward ───────────────────────────────────────────────────────────────

def _side(r: float) -> int:
    """Return 1 if r > 0.50, -1 if r < 0.50, 0 if r == 0.50 exactly.

    Mirrors build_reconcile_findings.py's _side() helper: exact 0.50 is
    treated as neither side — no directional evidence.
    """
    if r > 0.50:
        return 1
    if r < 0.50:
        return -1
    return 0  # exact tie — neither side


def evaluate_fold(
    train_rate: float, train_n: float, test_rate: float, test_n: float
) -> str:
    """Return a lowercase verdict token for one walk-forward fold.

    Parameters
    ----------
    train_rate, train_n:
        Barrier-hit rate and sample size on the fold's anchored train window.
    test_rate, test_n:
        Barrier-hit rate and sample size on the fold's test chunk.

    Returns
    -------
    str
        One of ``"pass"``, ``"fail"``, or ``"below-n"``.

    Notes
    -----
    D-07 / per-fold MIN_N gate: the Claude's-discretion question of whether
    MIN_N applies per fold is resolved in favor of per-fold gating — both the
    anchored train window and the test chunk must independently carry enough
    evidence (n >= MIN_N) for the fold to count at all; otherwise the fold
    is ``"below-n"`` and contributes neither a pass nor a fail signal (though
    it still counts in walk_forward_verdict's denominator, per D-07).

    Given both n's clear MIN_N, the fold is ``"pass"`` iff train_rate and
    test_rate are on the SAME non-boundary side of 0.50 (train predicts a
    directional side, test must confirm it) — mirroring determine_verdict's
    same-side-of-0.5 semantics in build_reconcile_findings.py. An exact 0.50
    on either side is treated as no directional evidence, so the fold
    ``"fail"``s (a train rate of exactly 0.50 makes no prediction to confirm).
    """
    if train_n < MIN_N or test_n < MIN_N:
        return "below-n"
    train_side = _side(train_rate)
    test_side = _side(test_rate)
    if train_side != 0 and test_side != 0 and train_side == test_side:
        return "pass"
    return "fail"


def walk_forward_verdict(fold_verdicts: list[str]) -> str:
    """Return the aggregate robustness verdict for one bucket's walk-forward folds.

    Parameters
    ----------
    fold_verdicts:
        The per-fold ``evaluate_fold`` results ("pass"/"fail"/"below-n") for
        every fold evaluated for one bucket.

    Returns
    -------
    str
        One of ``"wf-robust"``, ``"wf-fragile"``, or ``"no-folds"``.

    Notes
    -----
    D-07: the aggregate walk-forward robustness verdict requires a MAJORITY
    (strictly greater than 50%) of test folds to pass, not unanimity — one
    noisy fold should not kill an otherwise-robust edge, but exactly 50% is
    NOT a majority (``"wf-fragile"``). The denominator is the total number of
    folds evaluated; ``"below-n"`` folds count against the majority (they are
    not excluded from the denominator) since they represent folds where the
    edge could not even be tested for robustness.

    Returns ``"no-folds"`` for an empty list (guard clause — no folds, no
    verdict to report).
    """
    total = len(fold_verdicts)
    if total == 0:
        return "no-folds"
    passes = sum(1 for v in fold_verdicts if v == "pass")
    return "wf-robust" if passes > total / 2 else "wf-fragile"


def evaluate_geo_fold(
    train_lift: float, train_n: float, test_lift: float, test_n: float, diagnostic: bool,
) -> str:
    """Walk-forward fold verdict on the corridor-position null (quick task
    260929-mkg): "pass" iff both halves carry effective n (geo_n_eff) >= MIN_N and
    the train and test lifts have the same non-zero sign; "diagnostic" for
    outcome-leaking buckets; "no-baseline" when either lift is undefined."""
    if diagnostic:
        return "diagnostic"
    if not (isinstance(train_lift, float) and isinstance(test_lift, float)) \
            or math.isnan(train_lift) or math.isnan(test_lift):
        return "no-baseline"
    if not (train_n >= MIN_N and test_n >= MIN_N):   # NaN n_eff counts as below-n
        return "below-n"
    if train_lift != 0 and test_lift != 0 and (train_lift > 0) == (test_lift > 0):
        return "pass"
    return "fail"


BUCKET_KEYS = ("analysis", "timeframe", "instrument", "direction", "bucket")


def build_walkforward_rows(
    keys: list[str],
    df_nq: pd.DataFrame,
    df_es: pd.DataFrame,
    tf_label: str,
) -> list[dict[str, object]]:
    """Build long-form walk-forward manifest rows for one timeframe's NQ/ES frames.

    Iterates the 4 anchored folds implied by WALK_FORWARD_FOLDS (D-06): fold
    i's test chunk is ``[WALK_FORWARD_FOLDS[i], next_boundary)`` where
    ``next_boundary`` is ``WALK_FORWARD_FOLDS[i+1]`` for the first three folds
    and ``OOS_START`` for the last fold, and its train window is every
    discovery bar strictly before the chunk start (anchored/expanding,
    D-05). Both windows are carved via ``slice_fold()``, which clamps to the
    discovery region (D-04) — this function never calls
    ``slice_df(df, oos=True)`` and never touches the sacred OOS slice.

    For each fold: computes bucket rate/n on the train and test halves via
    ``build_manifest_rows()`` (reusing the existing per-bucket dispatch and
    its graceful compute-failure warn+skip), joins train<->test on the five
    bucket keys (``BUCKET_KEYS``: analysis, timeframe, instrument, direction,
    bucket), and evaluates the fold via ``evaluate_fold()``. A bucket missing
    from either half of a fold (e.g. a compute failure or an empty slice) is
    silently absent from that fold's output rows — it simply contributes one
    fewer fold to that bucket's aggregate, matching the project's graceful-
    degradation convention.

    After all folds, groups rows by ``BUCKET_KEYS`` and computes each
    bucket's aggregate ``wf_verdict`` via ``walk_forward_verdict()`` (D-07)
    over that bucket's ``fold_verdict`` sequence, writing the same
    ``wf_verdict`` onto every fold row of that bucket — so a bucket present
    in fewer than 4 folds still gets a ``wf_verdict`` computed over the folds
    it has.

    This function performs no I/O — it is a pure in-memory aggregation.
    Only the ``--walk-forward`` branch of ``main()`` writes
    ``output/validation_manifest_walkforward.csv``; the discovery/OOS
    manifests are never written or read here.

    Returns
    -------
    list[dict[str, object]]
        One row per (bucket x fold) with columns: analysis, timeframe,
        instrument, direction, bucket, fold_index (1-based), train_end,
        test_end, train_rate, train_n, test_rate, test_n, fold_verdict,
        wf_verdict.
    """
    fold_boundaries = list(WALK_FORWARD_FOLDS) + [OOS_START]
    fold_specs = list(zip(fold_boundaries[:-1], fold_boundaries[1:]))

    fold_rows: list[dict[str, object]] = []
    for fold_index, (train_end, test_end) in enumerate(fold_specs, start=1):
        train_nq, test_nq = slice_fold(df_nq, train_end, test_end)
        train_es, test_es = slice_fold(df_es, train_end, test_end)

        train_by_key = {
            tuple(row[k] for k in BUCKET_KEYS): row
            for row in build_manifest_rows(keys, train_nq, train_es, tf_label, "wf_train")
        }
        test_by_key = {
            tuple(row[k] for k in BUCKET_KEYS): row
            for row in build_manifest_rows(keys, test_nq, test_es, tf_label, "wf_test")
        }

        for bucket_key in sorted(set(train_by_key) & set(test_by_key)):
            tr = train_by_key[bucket_key]
            te = test_by_key[bucket_key]
            verdict = evaluate_fold(tr["rate"], tr["n"], te["rate"], te["n"])
            analysis, timeframe, instrument, direction, bucket = bucket_key
            fold_rows.append({
                "analysis":     analysis,
                "timeframe":    timeframe,
                "instrument":   instrument,
                "direction":    direction,
                "bucket":       bucket,
                "fold_index":   fold_index,
                "train_end":    train_end,
                "test_end":     test_end,
                "train_rate":   tr["rate"],
                "train_n":      tr["n"],
                "test_rate":    te["rate"],
                "test_n":       te["n"],
                "fold_verdict": verdict,
                "diagnostic":     te["diagnostic"],
                "train_geo_lift": tr["geo_lift"],
                "train_geo_n":    tr["geo_n"],
                "train_geo_n_eff": tr["geo_n_eff"],
                "test_geo_lift":  te["geo_lift"],
                "test_geo_n":     te["geo_n"],
                "test_geo_n_eff": te["geo_n_eff"],
                "geo_fold_verdict": evaluate_geo_fold(
                    tr["geo_lift"], tr["geo_n_eff"], te["geo_lift"], te["geo_n_eff"], te["diagnostic"]),
            })

    by_bucket: dict[tuple, list[int]] = {}
    for i, row in enumerate(fold_rows):
        key = tuple(row[k] for k in BUCKET_KEYS)
        by_bucket.setdefault(key, []).append(i)

    for idxs in by_bucket.values():
        wf = walk_forward_verdict([fold_rows[i]["fold_verdict"] for i in idxs])
        geo_verdicts = [fold_rows[i]["geo_fold_verdict"] for i in idxs]
        if all(v == "diagnostic" for v in geo_verdicts):
            geo_wf = "diagnostic"
        elif all(v == "no-baseline" for v in geo_verdicts):
            geo_wf = "no-baseline"
        else:
            geo_wf = walk_forward_verdict(geo_verdicts)
        for i in idxs:
            fold_rows[i]["wf_verdict"] = wf
            fold_rows[i]["geo_wf_verdict"] = geo_wf

    return fold_rows


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validation harness: discovery/OOS slicing, sample-size gating, manifest CSV.",
    )
    parser.add_argument(
        "--oos",
        action="store_true",
        help=(
            "Evaluate on the OOS (out-of-sample) slice. Default: discovery"
            " (train) slice. Ignored if --walk-forward is also passed."
        ),
    )
    parser.add_argument(
        "--holdout",
        action="store_true",
        help=(
            "Evaluate on the fresh holdout (bars after DATA_END through"
            " HOLDOUT_END); writes output/validation_manifest_holdout.csv."
            " Features are built on the full history so trailing windows are"
            " warm; the corridor baseline is estimated within the holdout."
        ),
    )
    parser.add_argument(
        "--walk-forward",
        action="store_true",
        help=(
            "Evaluate across the 4 sequential walk-forward folds carved from"
            " the discovery slice (D-04/D-05/D-06); writes"
            " output/validation_manifest_walkforward.csv and never touches"
            " the discovery/OOS manifests or the sacred OOS banner. Takes"
            " precedence over --oos if both are passed."
        ),
    )
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # D-04: walk-forward is entirely additive and never consumes the sacred
    # OOS slice, so it branches out before the _OOS_BANNER / discovery-oos
    # slice logic below and never writes the discovery/oos manifest paths.
    if args.walk_forward:
        print(
            f"Walk-forward: {len(WALK_FORWARD_FOLDS)} folds over the discovery"
            f" slice (WALK_FORWARD_FOLDS={WALK_FORWARD_FOLDS},"
            f" OOS_START={OOS_START}, MIN_N={MIN_N})"
        )

        dfs_1m = {inst: load_1m(path) for inst, path in INSTRUMENTS.items()}

        try:
            _load_scan_smts_historical()
            with_smt = True
        except (FileNotFoundError, ImportError) as exc:
            print(f"[warn] SMT unavailable ({exc}); swing SMT columns will be absent")
            with_smt = False

        all_keys = list(ANALYSES.keys())
        wf_rows: list[dict[str, object]] = []
        for tf_label, tf_rule in TIMEFRAMES.items():
            # D-14: scope all_keys per timeframe so e.g. session (D-02,
            # applies_to=("1H", "15min")) is excluded from Daily/4H folds.
            tf_keys = [k for k in all_keys
                       if (ANALYSIS_META[k].applies_to is None) or (tf_label in ANALYSIS_META[k].applies_to)]
            df_nq, df_es = prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], tf_rule, with_swing_smt=with_smt)
            wf_rows.extend(build_walkforward_rows(tf_keys, df_nq, df_es, tf_label))

        wf_out = _manifest_path("walkforward")
        wf_out.parent.mkdir(exist_ok=True)
        pd.DataFrame(wf_rows).to_csv(wf_out, index=False)

        verdict_counts: dict[str, int] = {}
        for row in wf_rows:
            verdict_counts[row["wf_verdict"]] = verdict_counts.get(row["wf_verdict"], 0) + 1
        print(
            f"Walk-forward manifest → {wf_out} ({len(wf_rows)} rows;"
            f" wf_verdict counts: {verdict_counts})"
        )
        return

    if args.oos and args.holdout:
        print("[error] --oos and --holdout are separate slices; pass one.")
        sys.exit(1)
    if args.oos:
        print(_OOS_BANNER)
    if args.holdout:
        print(_HOLDOUT_BANNER)

    slice_label = "holdout" if args.holdout else "oos" if args.oos else "discovery"
    print(f"Slice: {slice_label}  (OOS_START={OOS_START}, DATA_END={DATA_END}, MIN_N={MIN_N}, CI_LEVEL={CI_LEVEL})")

    end = HOLDOUT_END if args.holdout else DATA_END
    dfs_1m = {inst: load_1m(path, end=end) for inst, path in INSTRUMENTS.items()}

    # Try to include SMT tagging; fall back gracefully only if the external
    # scanner package is absent or unimportable.  Any other exception
    # (data error, resampling failure) should propagate so the researcher
    # sees a real traceback rather than a silent SMT disable.
    try:
        _load_scan_smts_historical()
        with_smt = True
    except (FileNotFoundError, ImportError) as exc:
        print(f"[warn] SMT unavailable ({exc}); swing SMT columns will be absent")
        with_smt = False

    all_keys = list(ANALYSES.keys())
    slice_rows: list[dict[str, object]] = []
    manifest_rows: list[dict[str, object]] = []

    for tf_label, tf_rule in TIMEFRAMES.items():
        # D-14: scope all_keys per timeframe so e.g. session (D-02,
        # applies_to=("1H", "15min")) produces manifest rows only on 1H/15min.
        tf_keys = [k for k in all_keys
                   if (ANALYSIS_META[k].applies_to is None) or (tf_label in ANALYSIS_META[k].applies_to)]
        df_nq, df_es = prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], tf_rule, with_swing_smt=with_smt)
        if args.holdout:
            nq_sl, es_sl = slice_holdout(df_nq), slice_holdout(df_es)
        else:
            nq_sl = slice_df(df_nq, oos=args.oos)
            es_sl = slice_df(df_es, oos=args.oos)
        for inst, sl in (("NQ", nq_sl), ("ES", es_sl)):
            slice_rows.append({
                "timeframe":  tf_label,
                "instrument": inst,
                "slice":      slice_label,
                "n_bars":     len(sl),
                "start_date": str(sl.index.min().date()) if len(sl) else "",
                "end_date":   str(sl.index.max().date()) if len(sl) else "",
            })
            print(f"  {tf_label} {inst}: {len(sl):,} bars ({slice_label})")
        manifest_rows.extend(
            build_manifest_rows(tf_keys, nq_sl, es_sl, tf_label, slice_label)
        )

    slices_path = SLICES_PATH.with_name(f"validation_slices_{slice_label}.csv") if args.holdout else SLICES_PATH
    slices_path.parent.mkdir(exist_ok=True)
    pd.DataFrame(slice_rows).to_csv(slices_path, index=False)
    print(f"Slice report → {slices_path}")

    # D-03: the BH correction fires at the discovery-manifest stage only —
    # OOS rows carry p_value but never bh_*/corrected_pass columns.
    if slice_label == "discovery":
        apply_bh_correction(manifest_rows)
        apply_geo_bh_correction(manifest_rows)

    manifest_out = _manifest_path(slice_label)
    pd.DataFrame(manifest_rows).to_csv(manifest_out, index=False)
    print(f"Manifest     → {manifest_out}")


if __name__ == "__main__":
    main()
