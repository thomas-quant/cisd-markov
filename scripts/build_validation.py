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
    ANALYSES, INSTRUMENTS, MAX_CONSEC, TIMEFRAMES, OOS_START, MIN_N, CI_LEVEL,
    WALK_FORWARD_FOLDS,
    load_1m, resample_ohlcv, prepare_pair,
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
    """
    rows: list[dict[str, object]] = []

    def emit(analysis: str, instrument: str, direction: str, bucket: str, n: int, k: int) -> None:
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
        })

    for key in keys:
        if key not in ANALYSES:
            continue
        label, compute_fn, _ = ANALYSES[key]
        for instrument, df in (("NQ", df_nq), ("ES", df_es)):
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
                         data["totals"][ct], data["runs"][ct])

            elif key == "mc":
                for ct in ("bullish", "bearish"):
                    for n in range(1, MAX_CONSEC + 1):
                        d = data[ct][n]
                        emit(key, instrument, ct, f"{n}_consecutive",
                             d["total"], d["runs"])

            elif key == "wick":
                for ct in ("bullish", "bearish"):
                    for grp in ("past_wick", "within_wick"):
                        d = data[ct][grp]
                        emit(key, instrument, ct, grp, d["total"], d["runs"])

            elif key == "combined":
                for ct in ("bullish", "bearish"):
                    for nc in range(1, MAX_CONSEC + 1):
                        for grp in ("past_wick", "within_wick"):
                            d = data[ct][nc][grp]
                            emit(key, instrument, ct, f"{nc}c_{grp}",
                                 d["total"], d["runs"])

            elif key in ("volume", "candle_size", "size_cross"):
                for ct in ("bullish", "bearish"):
                    for bucket_lbl, d in data[ct].items():
                        emit(key, instrument, ct, bucket_lbl,
                             d["total"], d["runs"])

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
                                     d["total"], d["runs"])

            else:
                # Generic: smt_cisd, cisd_fvg, sweep, sssf_swing
                # shape: {dir: {tag: {"total", "runs"}}}
                for ct in ("bullish", "bearish"):
                    for tag, d in data[ct].items():
                        emit(key, instrument, ct, tag, d["total"], d["runs"])

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

    Rows outside the family (n < 1) get bh_rank="", bh_q_value="",
    bh_significant=False, corrected_pass=False.

    Mutates *rows* in place; only ADDS keys — never renames, reorders, or
    removes any pre-existing key (additive-only, per D-03 / roadmap success
    criterion 3).
    """
    family_indices = [i for i, row in enumerate(rows) if row.get("n", 0) >= 1]
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


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validation harness: discovery/OOS slicing, sample-size gating, manifest CSV.",
    )
    parser.add_argument(
        "--oos",
        action="store_true",
        help="Evaluate on the OOS (out-of-sample) slice. Default: discovery (train) slice.",
    )
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    if args.oos:
        print(_OOS_BANNER)

    slice_label = "oos" if args.oos else "discovery"
    print(f"Slice: {slice_label}  (OOS_START={OOS_START}, MIN_N={MIN_N}, CI_LEVEL={CI_LEVEL})")

    dfs_1m = {inst: load_1m(path) for inst, path in INSTRUMENTS.items()}

    # Try to include SMT tagging; fall back gracefully only if the external
    # scanner package is absent or unimportable.  Any other exception
    # (data error, resampling failure) should propagate so the researcher
    # sees a real traceback rather than a silent SMT disable.
    try:
        _first_rule = next(iter(TIMEFRAMES.values()))
        prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], _first_rule, with_swing_smt=True)
        with_smt = True
    except (FileNotFoundError, ImportError) as exc:
        print(f"[warn] SMT unavailable ({exc}); swing SMT columns will be absent")
        with_smt = False

    all_keys = list(ANALYSES.keys())
    slice_rows: list[dict[str, object]] = []
    manifest_rows: list[dict[str, object]] = []

    for tf_label, tf_rule in TIMEFRAMES.items():
        df_nq, df_es = prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], tf_rule, with_swing_smt=with_smt)
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
            build_manifest_rows(all_keys, nq_sl, es_sl, tf_label, slice_label)
        )

    SLICES_PATH.parent.mkdir(exist_ok=True)
    pd.DataFrame(slice_rows).to_csv(SLICES_PATH, index=False)
    print(f"Slice report → {SLICES_PATH}")

    # D-03: the BH correction fires at the discovery-manifest stage only —
    # OOS rows carry p_value but never bh_*/corrected_pass columns.
    if slice_label == "discovery":
        apply_bh_correction(manifest_rows)

    manifest_out = _manifest_path(slice_label)
    pd.DataFrame(manifest_rows).to_csv(manifest_out, index=False)
    print(f"Manifest     → {manifest_out}")


if __name__ == "__main__":
    main()
