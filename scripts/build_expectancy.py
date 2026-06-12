"""Single-barrier forward-return expectancy for CISD events.

Unlike the stopless percentile-fan explorer (``build_forward_returns.py``), this
study treats each CISD as a *one-barrier trade*:

  * entry      = CISD close
  * invalidation (the only barrier) = CISD low (bullish) / CISD high (bearish),
    matching ``cisd_analysis.barrier_hit``'s stop definition
  * 1R         = |entry - invalidation|  (the risk unit)
  * upside is left OPEN and marked-to-close in R units at each forward horizon

For each forward horizon ``h`` in ``1..HORIZON`` the realised return is:

  * exactly ``-1R`` if the invalidation was breached on any bar ``t+1..t+h``
    (intrabar fill assumed at the invalidation level)
  * otherwise ``(close[t+h] - entry) / risk`` for longs, sign-flipped for shorts

The result is a stop-censored R-multiple distribution whose mean is the per-trade
expectancy. We report it for every research case (all CISDs, CISD-FVG buckets,
sweep, swing, SMT) so the relative edge of each setup is directly comparable.

Outputs:
  * output/cisd_expectancy.csv  -- tidy long table, full 1..HORIZON fan
  * output/cisd_expectancy.md   -- methodology + headline expectancy tables
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cisd_analysis import INSTRUMENTS, TIMEFRAMES, load_1m, prepare_pair

HORIZON = 7  # max forward bars, parity with build_forward_returns.py
HORIZONS = list(range(1, HORIZON + 1))
PERCENTILE_LEVELS = [5, 25, 50, 75, 95]

CSV_PATH = REPO_ROOT / "output" / "cisd_expectancy.csv"
MD_PATH = REPO_ROOT / "output" / "cisd_expectancy.md"

# Case-flag columns carried onto each event row, with safe defaults when a run
# did not produce them (e.g. SMT scan unavailable).
CASE_FLAG_DEFAULTS = {
    "has_dir_fvg_mid0": False,
    "has_dir_fvg_mid1": False,
    "has_dir_sweep": False,
    "prev_bar_is_dir_swing": False,
    "cisd_bar_is_dir_swing": False,
    "swing_smt_tag": "no SMT",
}

# (case key, human label). Masks are resolved in ``case_masks``.
CASES = [
    ("all_cisd", "All CISDs"),
    ("fvg_any", "CISD w/ FVG (mid0|mid1)"),
    ("fvg_mid0", "CISD-FVG mid0"),
    ("fvg_mid1", "CISD-FVG mid1"),
    ("fvg_none", "CISD no FVG"),
    ("sweep", "CISD w/ sweep"),
    ("no_sweep", "CISD no sweep"),
    ("prev_swing", "prev-bar swing"),
    ("cisd_swing", "CISD-bar swing"),
    ("smt", "CISD w/ SMT"),
    ("no_smt", "CISD no SMT"),
]


def resolve_data_root() -> Path:
    """Mirror build_forward_returns.resolve_data_root for worktree support."""
    local_data_root = REPO_ROOT / "data"
    if local_data_root.exists():
        return local_data_root
    if REPO_ROOT.parent.name == ".worktrees":
        parent_data_root = REPO_ROOT.parent.parent / "data"
        if parent_data_root.exists():
            return parent_data_root
    return local_data_root


def build_event_r_multiples(prepared: pd.DataFrame, instrument: str) -> pd.DataFrame:
    """One row per CISD event with a complete HORIZON-bar window and risk > 0.

    Columns: instrument, ts, cisd_type, risk, stop_bar (1..HORIZON or 0 if never
    stopped within the window), r_1..r_HORIZON, plus the carried case flags.
    """
    frame = prepared
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    cisd = frame["cisd_type"].to_numpy(dtype=object)
    n = len(frame)
    index = frame.index

    flags = {}
    for col, default in CASE_FLAG_DEFAULTS.items():
        if col in frame.columns:
            flags[col] = frame[col].to_numpy()
        else:
            flags[col] = np.full(n, default, dtype=object)

    event_pos = np.flatnonzero(pd.notna(frame["cisd_type"]).to_numpy())
    records = []
    for i in event_pos:
        # Need close[i+HORIZON] to exist for a full fan (matches the stopless
        # builder's complete-path convention; drops events near the data end).
        if i + HORIZON >= n:
            continue
        direction = cisd[i]
        entry = close[i]
        if direction == "bullish":
            inval = low[i]
            risk = entry - inval
        else:
            inval = high[i]
            risk = inval - entry
        if risk <= 0:  # degenerate: close sits on the invalidation extreme
            continue

        stop_bar = 0
        for k in range(1, HORIZON + 1):
            if direction == "bullish":
                if low[i + k] <= inval:
                    stop_bar = k
                    break
            else:
                if high[i + k] >= inval:
                    stop_bar = k
                    break

        rec = {
            "instrument": instrument,
            "ts": index[i],
            "cisd_type": direction,
            "risk": risk,
            "stop_bar": stop_bar,
        }
        for h in HORIZONS:
            if stop_bar and stop_bar <= h:
                rec[f"r_{h}"] = -1.0
            else:
                term = close[i + h]
                rec[f"r_{h}"] = (term - entry) / risk if direction == "bullish" else (entry - term) / risk
        for col in CASE_FLAG_DEFAULTS:
            rec[col] = flags[col][i]
        records.append(rec)

    columns = (
        ["instrument", "ts", "cisd_type", "risk", "stop_bar"]
        + [f"r_{h}" for h in HORIZONS]
        + list(CASE_FLAG_DEFAULTS)
    )
    return pd.DataFrame.from_records(records, columns=columns)


def case_masks(events: pd.DataFrame) -> dict[str, pd.Series]:
    """Boolean masks over event rows for each research case."""
    mid0 = events["has_dir_fvg_mid0"].astype(bool)
    mid1 = events["has_dir_fvg_mid1"].astype(bool)
    sweep = events["has_dir_sweep"].astype(bool)
    has_smt = events["swing_smt_tag"].astype(str) != "no SMT"
    truthy = pd.Series(True, index=events.index)
    return {
        "all_cisd": truthy,
        "fvg_any": mid0 | mid1,
        "fvg_mid0": mid0,
        "fvg_mid1": mid1,
        "fvg_none": ~(mid0 | mid1),
        "sweep": sweep,
        "no_sweep": ~sweep,
        "prev_swing": events["prev_bar_is_dir_swing"].astype(bool),
        "cisd_swing": events["cisd_bar_is_dir_swing"].astype(bool),
        "smt": has_smt,
        "no_smt": ~has_smt,
    }


def summarize_horizon(slice_df: pd.DataFrame, horizon: int) -> dict[str, float]:
    """Expectancy + distribution stats for one case slice at one horizon."""
    col = f"r_{horizon}"
    r = slice_df[col].to_numpy(dtype=float)
    n = len(r)
    stopped_by_h = slice_df["stop_bar"].between(1, horizon).to_numpy()
    out = {
        "n": int(n),
        "mean_r": float(np.mean(r)),
        "median_r": float(np.median(r)),
        "std_r": float(np.std(r, ddof=1)) if n > 1 else float("nan"),
        "win_rate": float(np.mean(r > 0) * 100.0),
        "stop_rate": float(np.mean(stopped_by_h) * 100.0),
    }
    for level in PERCENTILE_LEVELS:
        out[f"p{level}"] = float(np.percentile(r, level))
    return out


def build_long_table(events_by_inst: dict[str, pd.DataFrame], tf_label: str) -> list[dict]:
    """Tidy rows for (instrument, tf, direction, case, horizon)."""
    rows = []
    for instrument, events in events_by_inst.items():
        masks = case_masks(events)
        for case_key, case_label in CASES:
            case_slice = events[masks[case_key]]
            for direction in ("both", "bullish", "bearish"):
                if direction == "both":
                    dslice = case_slice
                else:
                    dslice = case_slice[case_slice["cisd_type"] == direction]
                if dslice.empty:
                    continue
                for h in HORIZONS:
                    stats = summarize_horizon(dslice, h)
                    rows.append(
                        {
                            "timeframe": tf_label,
                            "instrument": instrument,
                            "direction": direction,
                            "case": case_key,
                            "case_label": case_label,
                            "horizon": h,
                            **stats,
                        }
                    )
    return rows


def _fmt(value: float, nd: int = 2) -> str:
    return "n/a" if value is None or (isinstance(value, float) and np.isnan(value)) else f"{value:.{nd}f}"


def render_markdown(df: pd.DataFrame, smt_available: bool) -> str:
    lines: list[str] = []
    lines.append("# CISD Single-Barrier Expectancy (R-multiples)")
    lines.append("")
    lines.append(
        "Each CISD is treated as a one-barrier trade: entry at the CISD close, "
        "the **only** barrier is the CISD invalidation (low for bullish, high for "
        "bearish), and `1R = |entry - invalidation|`. A stopped trade locks at "
        "`-1R`; otherwise the position is marked-to-close in R units. Upside is "
        "left open. `mean_r` is the per-trade expectancy."
    )
    lines.append("")
    lines.append(
        f"- Forward horizon: 1..{HORIZON} bars (headline tables show the terminal "
        f"`h={HORIZON}` bar).\n"
        "- `stop_rate` = % of trades whose invalidation was breached within the window.\n"
        "- `win_rate` = % of trades with R > 0 at the horizon.\n"
        "- Events without a full forward window (data end) or with zero risk are excluded.\n"
        f"- SMT cases: {'included' if smt_available else 'UNAVAILABLE this run (SMT scan skipped)'}."
    )
    lines.append("")

    terminal = df[df["horizon"] == HORIZON]
    for instrument in terminal["instrument"].drop_duplicates():
        for direction in ("both", "bullish", "bearish"):
            sub = terminal[(terminal["instrument"] == instrument) & (terminal["direction"] == direction)]
            if sub.empty:
                continue
            lines.append(f"## {instrument} — {direction} (h={HORIZON})")
            lines.append("")
            lines.append("| Timeframe | Case | N | Mean R | Median R | Win % | Stop % | p5 | p25 | p50 | p75 | p95 |")
            lines.append("|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
            for tf_label in TIMEFRAMES:
                tf_rows = sub[sub["timeframe"] == tf_label]
                case_order = [c for c, _ in CASES]
                tf_rows = tf_rows.set_index("case").reindex(case_order).dropna(how="all").reset_index()
                for _, row in tf_rows.iterrows():
                    lines.append(
                        "| {tf} | {case} | {n} | {mean} | {med} | {win} | {stop} | "
                        "{p5} | {p25} | {p50} | {p75} | {p95} |".format(
                            tf=tf_label,
                            case=row["case_label"],
                            n=int(row["n"]),
                            mean=_fmt(row["mean_r"]),
                            med=_fmt(row["median_r"]),
                            win=_fmt(row["win_rate"], 1),
                            stop=_fmt(row["stop_rate"], 1),
                            p5=_fmt(row["p5"]),
                            p25=_fmt(row["p25"]),
                            p50=_fmt(row["p50"]),
                            p75=_fmt(row["p75"]),
                            p95=_fmt(row["p95"]),
                        )
                    )
            lines.append("")
    return "\n".join(lines)


def build() -> pd.DataFrame:
    data_root = resolve_data_root()
    dfs_1m = {inst: load_1m(data_root / path.name) for inst, path in INSTRUMENTS.items()}

    # Try to include SMT tagging; fall back gracefully if the external scanner
    # is unavailable so the rest of the study still runs.
    with_smt = True
    try:
        prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], next(iter(TIMEFRAMES.values())), with_swing_smt=True)
    except Exception as exc:  # noqa: BLE001 - optional dependency
        print(f"[warn] SMT scan unavailable ({exc!r}); SMT cases will be empty.")
        with_smt = False

    all_rows: list[dict] = []
    for tf_label, tf_rule in TIMEFRAMES.items():
        df_nq, df_es = prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], tf_rule, with_swing_smt=with_smt)
        events_by_inst = {
            "NQ": build_event_r_multiples(df_nq, "NQ"),
            "ES": build_event_r_multiples(df_es, "ES"),
        }
        all_rows.extend(build_long_table(events_by_inst, tf_label))
        print(f"[ok] {tf_label}: NQ={len(events_by_inst['NQ'])} ES={len(events_by_inst['ES'])} events")

    df = pd.DataFrame(all_rows)
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_PATH, index=False)
    MD_PATH.write_text(render_markdown(df, with_smt))
    print(f"[ok] wrote {CSV_PATH}")
    print(f"[ok] wrote {MD_PATH}")
    return df


if __name__ == "__main__":
    build()
