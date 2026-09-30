"""Barrier-trade payoff (R-multiples) for the frozen geo-significant buckets.

The validation harness tests hit RATE lifts over the corridor/ATR-regime
baseline. A higher hit rate usually comes with entry closer to the target,
i.e. a smaller reward in R, so a rate lift is not a payoff lift. This study
scores the same trade the rate was measured on:

  * entry   = close[t+k] of the analysis' scoring frame (k0: CISD close,
              k1/k2: confirm-then-enter, fwd: close[t+1] for the forward
              window of the post-CISD / candle[1] studies)
  * stop    = CISD candle's opposite extreme  -> -1R
  * target  = CISD candle's near extreme      -> +(target - entry) / risk
  * horizon = LOOKAHEAD bars after entry; neither touched -> marked at close
  * stop is checked before target within a bar (as barrier_hit does)

Per bucket it reports mean R (gross and net of a stated cost) and the lift in
mean R over the same corridor-bin x ATR-regime baseline the rate test uses,
with a cluster-robust SE (session day / week clusters, NQ+ES pooled). Costs
are known, so they are subtracted, never tested.

Bucket membership is captured from the validation compute_* functions
themselves (their _tally calls), so it is identical to the manifests.

Buckets = pooled NQ+ES rows of the FROZEN discovery manifest with geo_verdict
above-/below-baseline. Slices: discovery (< OOS_START) and the fresh holdout
(> DATA_END). Output: output/barrier_payoff.csv, output/barrier_payoff.md.
"""
from __future__ import annotations

import math
import sys
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import cisd_barriers
from cisd_analysis import (
    ANALYSES, INSTRUMENTS, TIMEFRAMES, LOOKAHEAD, MAX_CONSEC, HOLDOUT_END,
    load_1m, prepare_pair, _load_scan_smts_historical,
)
from cisd_barriers import GEO_BINS, GEO_FRAMES, _regime_codes, geo_cluster_ids
from scripts.build_validation import POOLED, slice_df, slice_holdout

DISCOVERY_MANIFEST_PATH = REPO_ROOT / "output" / "validation_manifest_discovery.csv"
CSV_PATH = REPO_ROOT / "output" / "barrier_payoff.csv"
MD_PATH  = REPO_ROOT / "output" / "barrier_payoff.md"

TICK = 0.25   # NQ and ES
# Assumed round-trip cost in index points: 1 tick slippage per side plus
# ~$4 commission round trip (NQ $5/tick -> 0.2 pt, ES $12.50/tick -> 0.08 pt).
COST_POINTS = {"NQ": 2 * TICK + 0.20, "ES": 2 * TICK + 0.08}
_Z95 = 1.959963984540054


# ── Bucket membership capture ─────────────────────────────────────────────────

@contextmanager
def _recording_tally(log: dict[int, list[tuple[int, str]]]):
    """Patch cisd_barriers._tally to record (pos, frame) per cell id.

    The frame is read off the geo array: capture_buckets() fills geo_p_<frame>
    with the frame's index in GEO_FRAMES, so geo.p[pos] names the frame.
    """
    original = cisd_barriers._tally

    def tally(cell, hit, geo, pos):
        original(cell, hit, None, pos)
        if hit is None or geo is None:
            return
        log.setdefault(id(cell), []).append((int(pos), GEO_FRAMES[int(geo.p[pos])]))

    cisd_barriers._tally = tally
    try:
        yield
    finally:
        cisd_barriers._tally = original


def _bucket_cells(analysis: str, data: dict) -> list[tuple[str, str, dict]]:
    """(direction, bucket label, cell) in build_manifest_rows' naming."""
    out = []
    for ct in ("bullish", "bearish"):
        if analysis == "mc":
            out += [(ct, f"{n}_consecutive", data[ct][n]) for n in range(1, MAX_CONSEC + 1)]
        elif analysis == "combined":
            out += [(ct, f"{nc}c_{grp}", data[ct][nc][grp])
                    for nc in range(1, MAX_CONSEC + 1) for grp in ("past_wick", "within_wick")]
        else:
            out += [(ct, tag, d) for tag, d in data[ct].items() if isinstance(d, dict) and "total" in d]
    return out


def capture_buckets(df: pd.DataFrame, analyses: list[str]) -> dict[tuple[str, str, str], list[tuple[int, str]]]:
    """{(analysis, direction, bucket): [(pos, frame), ...]} for one frame."""
    tagged = df.copy()
    for i, frame in enumerate(GEO_FRAMES):
        tagged[f"geo_p_{frame}"] = float(i)
    tagged["geo_cluster"] = 0
    members: dict[tuple[str, str, str], list[tuple[int, str]]] = {}
    for analysis in analyses:
        log: dict[int, list[tuple[int, str]]] = {}
        with _recording_tally(log):
            data = ANALYSES[analysis][1](tagged)
        for ct, bucket, cell in _bucket_cells(analysis, data):
            members[(analysis, ct, bucket)] = log.get(id(cell), [])
    return members


# ── Per-event barrier trade ───────────────────────────────────────────────────

def event_trades(df: pd.DataFrame, frame: str) -> pd.DataFrame:
    """One row per CISD scored under *frame*: pos, R (gross), risk, stratum.

    Rows are dropped when the setup is resolved before entry (k1/k2), when the
    entry lies outside the stop..target corridor (fwd), when risk or reward is
    not positive, or when the window runs past the end of the frame.
    """
    high  = df["high"].to_numpy(dtype=float)
    low   = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    ct    = df["cisd_type"].to_numpy(dtype=object)
    regime = _regime_codes(df)
    n = len(df)
    k = 1 if frame == "fwd" else int(frame[1:])
    start = 2 if frame == "fwd" else k + 1
    rows = []
    for i in np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy()):
        bull = ct[i] == "bullish"
        hi0, lo0 = high[i], low[i]
        if i + start + LOOKAHEAD - 1 >= n or not hi0 > lo0:
            continue
        if frame not in ("k0", "fwd") and ((high[i + 1:i + k + 1] >= hi0).any() or (low[i + 1:i + k + 1] <= lo0).any()):
            continue
        entry = close[i + k]
        risk, reward = (entry - lo0, hi0 - entry) if bull else (hi0 - entry, entry - lo0)
        if not (risk > 0 and reward > 0):
            continue
        r, hit = None, False
        for j in range(start, start + LOOKAHEAD):
            if (low[i + j] <= lo0) if bull else (high[i + j] >= hi0):
                r = -1.0; break
            if (high[i + j] >= hi0) if bull else (low[i + j] <= lo0):
                r, hit = reward / risk, True; break
        if r is None:
            last = close[i + start + LOOKAHEAD - 1]
            r = ((last - entry) if bull else (entry - last)) / risk
        pos = risk / (hi0 - lo0)   # entry position from stop (0) to target (1)
        rows.append((i, 1 if bull else -1, r, hit, risk, int(regime[i]),
                     int(min(max(math.floor(pos * GEO_BINS), 0), GEO_BINS - 1))))
    return pd.DataFrame(rows, columns=["pos", "dcode", "r", "hit", "risk", "regime", "bin"])


def attach_expected(trades: pd.DataFrame, cost_points: float) -> pd.DataFrame:
    """Add net R and the stratum-mean (corridor bin x ATR regime x direction)
    baselines for gross and net R, estimated over all CISDs in the frame."""
    out = trades.copy()
    out["r_net"] = out["r"] - cost_points / out["risk"]
    key = ["dcode", "regime", "bin"]
    out["exp_r"] = out.groupby(key)["r"].transform("mean")
    out["exp_r_net"] = out.groupby(key)["r_net"].transform("mean")
    return out


def cluster_mean_ci(values: np.ndarray, clusters: np.ndarray) -> tuple[float, float, int]:
    """Mean, cluster-robust SE (max with iid SE) and number of clusters."""
    n = len(values)
    if n < 2:
        return (float(values.mean()) if n else math.nan, math.nan, n)
    mean = float(values.mean())
    resid = pd.Series(values - mean).groupby(clusters).sum().to_numpy()
    g = len(resid)
    var_cl = g / (g - 1) * float((resid ** 2).sum()) if g >= 2 else math.nan
    var_iid = n / (n - 1) * float(((values - mean) ** 2).sum())
    var = max(var_cl, var_iid) if var_cl == var_cl else var_iid
    return mean, math.sqrt(var) / n, g


# ── Study ─────────────────────────────────────────────────────────────────────

def surviving_buckets(path: Path = DISCOVERY_MANIFEST_PATH) -> pd.DataFrame:
    d = pd.read_csv(path)
    keep = (d["instrument"] == POOLED) & d["geo_verdict"].isin(["above-baseline", "below-baseline"])
    return d.loc[keep, ["analysis", "timeframe", "direction", "bucket", "geo_verdict", "geo_lift"]]


def payoff_rows(frames: dict[str, pd.DataFrame], tf_label: str, slice_label: str,
                wanted: pd.DataFrame) -> list[dict]:
    """frames: {instrument: sliced prepared frame} for one timeframe."""
    wanted = wanted[wanted["timeframe"] == tf_label]
    analyses = sorted(wanted["analysis"].unique())
    pooled: dict[tuple, list[pd.DataFrame]] = {}
    for inst, df in frames.items():
        clusters = geo_cluster_ids(df.index)
        members = capture_buckets(df, analyses)
        trades = {f: attach_expected(event_trades(df, f), COST_POINTS[inst]).set_index("pos")
                  for f in {fr for m in members.values() for _, fr in m} | {"k0"}}
        all_k0 = trades["k0"].assign(cluster=clusters[trades["k0"].index])
        pooled.setdefault(("all_cisd", "both", "all", "k0"), []).append(all_k0)
        for _, w in wanted.iterrows():
            ev = members.get((w["analysis"], w["direction"], w["bucket"]), [])
            if not ev:
                continue
            frame = ev[0][1]
            pos = [p for p, _ in ev if p in trades[frame].index]
            sel = trades[frame].loc[pos]
            pooled.setdefault((w["analysis"], w["direction"], w["bucket"], frame), []).append(
                sel.assign(cluster=clusters[sel.index]))

    rows = []
    for (analysis, direction, bucket, frame), parts in pooled.items():
        t = pd.concat(parts)
        if t.empty:
            continue
        cl = t["cluster"].to_numpy()
        gross, gross_se, g = cluster_mean_ci(t["r"].to_numpy(), cl)
        net, net_se, _ = cluster_mean_ci(t["r_net"].to_numpy(), cl)
        lift, lift_se, _ = cluster_mean_ci((t["r"] - t["exp_r"]).to_numpy(), cl)
        lift_net, lift_net_se, _ = cluster_mean_ci((t["r_net"] - t["exp_r_net"]).to_numpy(), cl)
        rows.append({
            "slice": slice_label, "timeframe": tf_label, "analysis": analysis,
            "direction": direction, "bucket": bucket, "frame": frame,
            "n": len(t), "clusters": g,
            "hit_rate": round(float(t["hit"].mean()), 4),
            "mean_r_gross": round(gross, 4), "mean_r_gross_ci": round(_Z95 * gross_se, 4),
            "mean_r_net": round(net, 4), "mean_r_net_ci": round(_Z95 * net_se, 4),
            "lift_r_gross": round(lift, 4), "lift_r_gross_ci": round(_Z95 * lift_se, 4),
            "lift_r_net": round(lift_net, 4), "lift_r_net_ci": round(_Z95 * lift_net_se, 4),
            "median_risk_pts": round(float(t["risk"].median()), 2),
        })
    return rows


def render_markdown(df: pd.DataFrame) -> str:
    lines = ["# Barrier-trade payoff of the frozen geo-significant buckets", "",
             "Same trade as the rate test: entry close[t+k], stop = CISD opposite extreme (-1R), "
             "target = CISD near extreme, LOOKAHEAD bars, else marked at close. "
             f"Net = gross minus an assumed round-trip cost of {COST_POINTS['NQ']:.2f} pt (NQ) / "
             f"{COST_POINTS['ES']:.2f} pt (ES): 1 tick slippage per side + ~$4 commission. "
             "`lift` = mean R minus the corridor-bin x ATR-regime baseline mean R. CIs are 95%, "
             "cluster-robust (session day / week, NQ+ES pooled). The buckets nest and overlap; "
             "rows are not independent.", ""]
    for slice_label in df["slice"].drop_duplicates():
        lines += [f"## {slice_label}", "",
                  "| TF | Analysis | Dir | Bucket | n | Hit % | Mean R net (±CI) | Lift R gross (±CI) | Lift R net (±CI) | Median risk pt |",
                  "|---|---|---|---|--:|--:|--:|--:|--:|--:|"]
        sub = df[df["slice"] == slice_label]
        for _, r in sub.iterrows():
            lines.append(
                f"| {r.timeframe} | {r.analysis} | {r.direction} | {r.bucket} | {r.n} | {100 * r.hit_rate:.1f} | "
                f"{r.mean_r_net:+.3f} (±{r.mean_r_net_ci:.3f}) | {r.lift_r_gross:+.3f} (±{r.lift_r_gross_ci:.3f}) | "
                f"{r.lift_r_net:+.3f} (±{r.lift_r_net_ci:.3f}) | {r.median_risk_pts:.2f} |")
        lines.append("")
    return "\n".join(lines)


def build() -> pd.DataFrame:
    wanted = surviving_buckets()
    try:
        _load_scan_smts_historical()
        with_smt = True
    except (FileNotFoundError, ImportError) as exc:
        print(f"[warn] SMT unavailable ({exc}); SMT buckets will be empty")
        with_smt = False
    dfs_1m = {inst: load_1m(path, end=HOLDOUT_END) for inst, path in INSTRUMENTS.items()}
    rows: list[dict] = []
    for tf_label, tf_rule in TIMEFRAMES.items():
        if tf_label not in set(wanted["timeframe"]):
            continue
        df_nq, df_es = prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], tf_rule, with_swing_smt=with_smt)
        # Features are built on the full history (trailing windows only);
        # discovery = bars < OOS_START, holdout = bars after DATA_END.
        for slice_label, cut in (("discovery", slice_df), ("holdout", slice_holdout)):
            rows += payoff_rows({"NQ": cut(df_nq), "ES": cut(df_es)}, tf_label, slice_label, wanted)
        print(f"[ok] {tf_label}")
    out = pd.DataFrame(rows).sort_values(["slice", "timeframe", "analysis", "direction", "bucket"])
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(CSV_PATH, index=False)
    MD_PATH.write_text(render_markdown(out))
    print(f"[ok] wrote {CSV_PATH}\n[ok] wrote {MD_PATH}")
    return out


if __name__ == "__main__":
    build()
