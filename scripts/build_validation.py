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
             rate, n, successes, ci_low, ci_high, ci_method, min_n_pass, slice.
    rate/ci_low/ci_high are proportions in [0, 1] (NOT percentages).
    Buckets with n < MIN_N appear with min_n_pass=False — never dropped.
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

    manifest_out = _manifest_path(slice_label)
    pd.DataFrame(manifest_rows).to_csv(manifest_out, index=False)
    print(f"Manifest     → {manifest_out}")


if __name__ == "__main__":
    main()
