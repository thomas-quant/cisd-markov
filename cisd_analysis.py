"""
CISD (Close Implies Subsequent Direction) Analysis Suite
=========================================================
All analyses use BARRIER logic: a "run" only counts if the
target (high for bullish, low for bearish) is hit BEFORE
the stop (low for bullish, high for bearish) within LOOKAHEAD bars.

Output: one PNG per timeframe, NQ and ES compared side-by-side.

Usage
-----
    python cisd_analysis.py                     # all TFs, all analyses
    python cisd_analysis.py basic wick          # selected analyses only
"""

import sys
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path

matplotlib.rcParams.update({
    "figure.facecolor":  "#0f1117",
    "axes.facecolor":    "#1a1d27",
    "axes.edgecolor":    "#3a3d4d",
    "axes.labelcolor":   "#c0c4d0",
    "axes.titlecolor":   "#e0e4f0",
    "axes.grid":         True,
    "grid.color":        "#2a2d3d",
    "grid.linewidth":    0.6,
    "xtick.color":       "#7a7d90",
    "ytick.color":       "#7a7d90",
    "text.color":        "#c0c4d0",
    "font.family":       "sans-serif",
    "font.size":         9,
    "legend.facecolor":  "#1a1d27",
    "legend.edgecolor":  "#3a3d4d",
})

# NQ = teal family, ES = amber family
COLORS = {
    "NQ": {"bullish": "#26a69a", "bearish": "#80cbc4"},   # teal / light teal
    "ES": {"bullish": "#ffa726", "bearish": "#ffcc80"},   # amber / light amber
}

# ── Configuration ─────────────────────────────────────────────────────────────
DATA_DIR    = Path(__file__).parent / "data"
INSTRUMENTS = {
    "NQ": DATA_DIR / "nq_1m.parquet",
    "ES": DATA_DIR / "es_1m.parquet",
}
TIMEFRAMES = {
    "Daily": "1D",
    "4H":    "4h",
    "1H":    "1h",
    "15min": "15min",
}
LOOKAHEAD  = 2   # bars to look ahead after a CISD
MAX_CONSEC = 3   # max consecutive opposite candles to segment by


# ── Data Loading & Resampling ─────────────────────────────────────────────────

def load_1m(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df = df.set_index("DateTime_ET").sort_index()
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = [c.lower() for c in df.columns]
    return df


def resample_ohlcv(df_1m: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df_1m.resample(rule).agg(agg).dropna(subset=["open"])


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["direction"] = np.where(
        df["close"] > df["open"], "bullish",
        np.where(df["close"] < df["open"], "bearish", "neutral"),
    )
    df["prev_close"]     = df["close"].shift(1)
    df["prev_direction"] = df["direction"].shift(1)
    df["prev_high"]      = df["high"].shift(1)
    df["prev_low"]       = df["low"].shift(1)
    df["cisd_type"] = np.select(
        [
            (df["prev_direction"] == "bearish") & (df["close"] > df["prev_close"]),
            (df["prev_direction"] == "bullish") & (df["close"] < df["prev_close"]),
        ],
        ["bullish", "bearish"],
        default=None,
    )
    return df


# ── Core Barrier Logic ────────────────────────────────────────────────────────

def barrier_hit(df: pd.DataFrame, idx: int, row: pd.Series, ct: str) -> bool:
    """
    Returns True if the TARGET is hit before the STOP within LOOKAHEAD bars.
      Bullish: target = CISD high, stop = CISD low
      Bearish: target = CISD low,  stop = CISD high
    """
    for j in range(1, LOOKAHEAD + 1):
        if idx + j >= len(df):
            break
        bar = df.iloc[idx + j]
        if ct == "bullish":
            if bar["low"] <= row["low"]:    return False   # stop
            if bar["high"] >= row["high"]:  return True    # target
        else:
            if bar["high"] >= row["high"]:  return False   # stop
            if bar["low"] <= row["low"]:    return True    # target
    return False


def _count_consecutive(idx: int, directions: pd.Series, target: str, max_n: int) -> int:
    count = 0
    for i in range(1, max_n + 1):
        pos = idx - i
        if pos < 0 or directions.iloc[pos] != target:
            break
        count += 1
    return count


# ── Helpers ───────────────────────────────────────────────────────────────────

def pv(num: int, den: int) -> float:
    return (num / den * 100) if den > 0 else 0.0


def _bar_label(ax, bars):
    for bar in bars:
        w = bar.get_width()
        if w > 0:
            ax.text(
                min(w + 0.5, 103), bar.get_y() + bar.get_height() / 2,
                f"{w:.1f}%", va="center", ha="left", fontsize=7.5, color="#c0c4d0",
            )


def _style_ax(ax, title: str):
    ax.set_title(title, fontsize=10, fontweight="bold", pad=6)
    ax.set_xlabel("Success Rate (%) — target hit before stop")
    ax.set_xlim(0, 108)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%g%%"))
    ax.spines[["top", "right"]].set_visible(False)


# ── Compute Functions ─────────────────────────────────────────────────────────

def compute_basic(df: pd.DataFrame) -> dict:
    """Barrier run rate across all CISDs."""
    df_cisd = df[df["cisd_type"].notna()]
    idx_index = df.index
    totals = {"bullish": 0, "bearish": 0}
    runs   = {"bullish": 0, "bearish": 0}
    for ts, row in df_cisd.iterrows():
        ct = row["cisd_type"]
        totals[ct] += 1
        if barrier_hit(df, idx_index.get_loc(ts), row, ct):
            runs[ct] += 1
    return {"totals": totals, "runs": runs}


def compute_mc(df: pd.DataFrame) -> dict:
    """Barrier run rate bucketed by consecutive opposite candles before CISD."""
    df_cisd    = df[df["cisd_type"].notna()]
    directions = df["direction"]
    idx_index  = df.index
    stats = {ct: {n: {"total": 0, "runs": 0} for n in range(1, MAX_CONSEC + 1)}
             for ct in ("bullish", "bearish")}
    for ts, row in df_cisd.iterrows():
        idx    = idx_index.get_loc(ts)
        ct     = row["cisd_type"]
        tgt    = "bearish" if ct == "bullish" else "bullish"
        consec = _count_consecutive(idx, directions, tgt, MAX_CONSEC)
        if consec < 1 or consec > MAX_CONSEC:
            continue
        stats[ct][consec]["total"] += 1
        if barrier_hit(df, idx, row, ct):
            stats[ct][consec]["runs"] += 1
    return stats


def compute_significance(df: pd.DataFrame) -> dict:
    """Barrier run rate using stricter CISD (close vs prev high/low)."""
    idx_arr = df.index
    totals = {"bullish": 0, "bearish": 0}
    runs   = {"bullish": 0, "bearish": 0}
    for i in range(1, len(df) - LOOKAHEAD):
        ph, pl, cc = df["high"].iloc[i-1], df["low"].iloc[i-1], df["close"].iloc[i]
        row = df.iloc[i]
        if cc > ph:
            totals["bullish"] += 1
            if barrier_hit(df, i, row, "bullish"):
                runs["bullish"] += 1
        if cc < pl:
            totals["bearish"] += 1
            if barrier_hit(df, i, row, "bearish"):
                runs["bearish"] += 1
    return {"totals": totals, "runs": runs}


def compute_wick(df: pd.DataFrame) -> dict:
    """Barrier run rate split by wick position of the CISD close."""
    stats = {
        "bullish": {"past_wick": {"total": 0, "runs": 0}, "within_wick": {"total": 0, "runs": 0}},
        "bearish": {"past_wick": {"total": 0, "runs": 0}, "within_wick": {"total": 0, "runs": 0}},
    }
    idx_index = df.index
    for ts, row in df[(df["prev_direction"] == "bearish") & (df["close"] > df["prev_close"])].iterrows():
        idx = idx_index.get_loc(ts)
        grp = "past_wick" if row["close"] > row["prev_high"] else "within_wick"
        stats["bullish"][grp]["total"] += 1
        if barrier_hit(df, idx, row, "bullish"):
            stats["bullish"][grp]["runs"] += 1
    for ts, row in df[(df["prev_direction"] == "bullish") & (df["close"] < df["prev_close"])].iterrows():
        idx = idx_index.get_loc(ts)
        grp = "past_wick" if row["close"] < row["prev_low"] else "within_wick"
        stats["bearish"][grp]["total"] += 1
        if barrier_hit(df, idx, row, "bearish"):
            stats["bearish"][grp]["runs"] += 1
    return stats


def compute_combined(df: pd.DataFrame) -> dict:
    """Barrier run rate cross-tabulated: wick position x consecutive candle count."""
    df_cisd    = df[df["cisd_type"].notna()]
    directions = df["direction"]
    idx_index  = df.index
    stats = {ct: {n: {"past_wick": {"total": 0, "runs": 0},
                       "within_wick": {"total": 0, "runs": 0}}
                  for n in range(1, MAX_CONSEC + 1)} for ct in ("bullish", "bearish")}
    for ts, row in df_cisd.iterrows():
        idx    = idx_index.get_loc(ts)
        ct     = row["cisd_type"]
        tgt    = "bearish" if ct == "bullish" else "bullish"
        consec = _count_consecutive(idx, directions, tgt, MAX_CONSEC)
        if consec < 1 or consec > MAX_CONSEC:
            continue
        above = row["close"] > row["prev_high"] if ct == "bullish" else row["close"] < row["prev_low"]
        grp = "past_wick" if above else "within_wick"
        stats[ct][consec][grp]["total"] += 1
        if barrier_hit(df, idx, row, ct):
            stats[ct][consec][grp]["runs"] += 1
    return stats


# ── Chart Functions ───────────────────────────────────────────────────────────
# Each chart_* function takes an Axes and data dicts for NQ and ES.

def chart_basic(ax, data_nq, data_es):
    rows = [
        ("NQ  Bullish", pv(data_nq["runs"]["bullish"], data_nq["totals"]["bullish"]),
         COLORS["NQ"]["bullish"], f"n={data_nq['totals']['bullish']:,}"),
        ("NQ  Bearish", pv(data_nq["runs"]["bearish"], data_nq["totals"]["bearish"]),
         COLORS["NQ"]["bearish"], f"n={data_nq['totals']['bearish']:,}"),
        ("ES  Bullish", pv(data_es["runs"]["bullish"], data_es["totals"]["bullish"]),
         COLORS["ES"]["bullish"], f"n={data_es['totals']['bullish']:,}"),
        ("ES  Bearish", pv(data_es["runs"]["bearish"], data_es["totals"]["bearish"]),
         COLORS["ES"]["bearish"], f"n={data_es['totals']['bearish']:,}"),
    ]
    labels = [f"{r[0]}  ({r[3]})" for r in rows]
    values = [r[1] for r in rows]
    colors = [r[2] for r in rows]
    bars = ax.barh(labels, values, color=colors, height=0.5)
    _bar_label(ax, bars)
    _style_ax(ax, f"Basic Barrier Run Rate  (lookahead={LOOKAHEAD})")


def chart_mc(ax, data_nq, data_es):
    y_pos, y_labels, y_colors, y_vals = [], [], [], []
    y = 0
    for n in range(1, MAX_CONSEC + 1):
        for ct in ("bullish", "bearish"):
            for instr, data, h in (("NQ", data_nq, 0.35), ("ES", data_es, 0.35)):
                d = data[ct][n]
                y_labels.append(f"{instr} {ct.capitalize()} {n}c  (n={d['total']:,})")
                y_vals.append(pv(d["runs"], d["total"]))
                y_colors.append(COLORS[instr][ct])
                y_pos.append(y)
                y += 1
        y += 0.4   # small gap between n groups
    bars = ax.barh(y_pos, y_vals, color=y_colors, height=0.6)
    _bar_label(ax, bars)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(y_labels, fontsize=7.5)
    _style_ax(ax, "Consecutive Opposite Candles (Markov)")


def chart_significance(ax, data_nq, data_es):
    rows = [
        ("NQ  Bullish", pv(data_nq["runs"]["bullish"], data_nq["totals"]["bullish"]),
         COLORS["NQ"]["bullish"], f"n={data_nq['totals']['bullish']:,}"),
        ("NQ  Bearish", pv(data_nq["runs"]["bearish"], data_nq["totals"]["bearish"]),
         COLORS["NQ"]["bearish"], f"n={data_nq['totals']['bearish']:,}"),
        ("ES  Bullish", pv(data_es["runs"]["bullish"], data_es["totals"]["bullish"]),
         COLORS["ES"]["bullish"], f"n={data_es['totals']['bullish']:,}"),
        ("ES  Bearish", pv(data_es["runs"]["bearish"], data_es["totals"]["bearish"]),
         COLORS["ES"]["bearish"], f"n={data_es['totals']['bearish']:,}"),
    ]
    labels = [f"{r[0]}  ({r[3]})" for r in rows]
    bars = ax.barh(labels, [r[1] for r in rows], color=[r[2] for r in rows], height=0.5)
    _bar_label(ax, bars)
    _style_ax(ax, "Significance Test  (close past prev High/Low)")


def chart_wick(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            side = "bullish" if ct == "bullish" else "bearish"
            for grp, glabel in (("past_wick", "past wick"), ("within_wick", "within wick")):
                d = data[ct][grp]
                rows.append((f"{instr} {ct.capitalize()} {glabel}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]),
                             COLORS[instr][ct],
                             1.0 if grp == "past_wick" else 0.55))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Wick Position Split")


def chart_combined(ax, data_nq, data_es):
    y_pos, y_labels, y_colors, y_alphas, y_vals = [], [], [], [], []
    y = 0
    for n in range(1, MAX_CONSEC + 1):
        for instr, data in (("NQ", data_nq), ("ES", data_es)):
            for ct in ("bullish", "bearish"):
                for grp, glabel, alpha in (("past_wick", "past wick", 1.0),
                                            ("within_wick", "within wick", 0.55)):
                    d = data[ct][n][grp]
                    y_labels.append(f"{instr} {ct.capitalize()} {n}c {glabel}  (n={d['total']:,})")
                    y_vals.append(pv(d["runs"], d["total"]))
                    y_colors.append(COLORS[instr][ct])
                    y_alphas.append(alpha)
                    y_pos.append(y)
                    y += 1
        y += 0.5
    for i in range(len(y_pos)):
        bar = ax.barh(y_pos[i], y_vals[i], color=y_colors[i], alpha=y_alphas[i], height=0.7)
        _bar_label(ax, bar)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(y_labels, fontsize=7)
    _style_ax(ax, "Combined: Wick x Consecutive")


# ── Dispatch ──────────────────────────────────────────────────────────────────

ANALYSES = {
    "basic":        ("Basic Barrier Run Rate",               compute_basic,        chart_basic),
    "mc":           ("Consecutive Candles (Markov)",         compute_mc,           chart_mc),
    "significance": ("Significance Test",                    compute_significance, chart_significance),
    "wick":         ("Wick Position",                        compute_wick,         chart_wick),
    "combined":     ("Combined: Wick x Consecutive",         compute_combined,     chart_combined),
}


def build_csv_rows(keys: list, df_nq: pd.DataFrame, df_es: pd.DataFrame) -> pd.DataFrame:
    """Flatten all analysis results into a tidy long-format table."""
    rows = []

    def add(analysis, instr, direction, category, n, runs):
        rows.append({
            "Analysis":   analysis,
            "Instrument": instr,
            "Direction":  direction,
            "Category":   category,
            "N":          n,
            "Runs":       runs,
            "Rate_pct":   round(pv(runs, n), 2),
        })

    for key in keys:
        label, compute_fn, _ = ANALYSES[key]
        for instr, df in (("NQ", df_nq), ("ES", df_es)):
            data = compute_fn(df)

            if key in ("basic", "significance"):
                for ct in ("bullish", "bearish"):
                    add(label, instr, ct, "all",
                        data["totals"][ct], data["runs"][ct])

            elif key == "mc":
                for ct in ("bullish", "bearish"):
                    for n in range(1, MAX_CONSEC + 1):
                        d = data[ct][n]
                        add(label, instr, ct, f"{n}_consecutive",
                            d["total"], d["runs"])

            elif key == "wick":
                for ct in ("bullish", "bearish"):
                    for grp in ("past_wick", "within_wick"):
                        d = data[ct][grp]
                        add(label, instr, ct, grp, d["total"], d["runs"])

            elif key == "combined":
                for ct in ("bullish", "bearish"):
                    for n in range(1, MAX_CONSEC + 1):
                        for grp in ("past_wick", "within_wick"):
                            d = data[ct][n][grp]
                            add(label, instr, ct, f"{n}c_{grp}",
                                d["total"], d["runs"])

    return pd.DataFrame(rows)


def build_figure(tf_label: str, df_nq: pd.DataFrame, df_es: pd.DataFrame, keys: list) -> plt.Figure:
    """One figure per timeframe — all analyses as subplots, NQ & ES compared in each."""
    n = len(keys)
    ncols = 2 if n > 1 else 1
    nrows = (n + 1) // 2

    # Combined chart taller since rows scale with data
    base_h = {"basic": 3, "significance": 3, "mc": 6, "wick": 5, "combined": 10}
    row_heights = []
    for i, key in enumerate(keys):
        if i % 2 == 0:
            pair = keys[i:i+2]
            row_heights.append(max(base_h.get(k, 4) for k in pair))

    fig, axes = plt.subplots(
        nrows, ncols,
        figsize=(ncols * 9, sum(row_heights)),
        squeeze=False,
        gridspec_kw={"height_ratios": row_heights} if row_heights else None,
    )
    axes_flat = [ax for row in axes for ax in row]

    nq_cisds = df_nq["cisd_type"].notna().sum()
    es_cisds = df_es["cisd_type"].notna().sum()
    fig.suptitle(
        f"{tf_label}   |   "
        f"NQ: {len(df_nq):,} bars / {nq_cisds:,} CISDs     "
        f"ES: {len(df_es):,} bars / {es_cisds:,} CISDs     "
        f"Lookahead = {LOOKAHEAD} bars",
        fontsize=12, fontweight="bold", color="#e0e4f0", y=1.01,
    )

    for i, key in enumerate(keys):
        _, compute_fn, chart_fn = ANALYSES[key]
        d_nq = compute_fn(df_nq)
        d_es = compute_fn(df_es)
        chart_fn(axes_flat[i], d_nq, d_es)

    for j in range(len(keys), len(axes_flat)):
        axes_flat[j].set_visible(False)

    # Legend patch
    from matplotlib.patches import Patch
    legend_handles = [
        Patch(color=COLORS["NQ"]["bullish"], label="NQ Bullish"),
        Patch(color=COLORS["NQ"]["bearish"], label="NQ Bearish"),
        Patch(color=COLORS["ES"]["bullish"], label="ES Bullish"),
        Patch(color=COLORS["ES"]["bearish"], label="ES Bearish"),
    ]
    fig.legend(handles=legend_handles, loc="upper right", ncol=4,
               fontsize=9, framealpha=0.8)

    fig.tight_layout()
    return fig


def main() -> None:
    requested = sys.argv[1:] if len(sys.argv) > 1 else list(ANALYSES.keys())
    invalid = [k for k in requested if k not in ANALYSES]
    if invalid:
        print(f"Unknown key(s): {', '.join(invalid)}")
        print(f"Valid: {', '.join(ANALYSES.keys())}")
        sys.exit(1)

    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)

    # Load 1-min data once per instrument
    print("Loading parquet data...")
    dfs_1m = {}
    for instr, path in INSTRUMENTS.items():
        print(f"  {instr} from {path.name} ...", end=" ", flush=True)
        dfs_1m[instr] = load_1m(path)
        print(f"{len(dfs_1m[instr]):,} bars")

    for tf_label, tf_rule in TIMEFRAMES.items():
        print(f"\nComputing {tf_label} ...", end=" ", flush=True)
        df_nq = prepare(resample_ohlcv(dfs_1m["NQ"], tf_rule))
        df_es = prepare(resample_ohlcv(dfs_1m["ES"], tf_rule))

        # Chart
        fig  = build_figure(tf_label, df_nq, df_es, requested)
        png  = out_dir / f"{tf_label}.png"
        fig.savefig(png, dpi=150, bbox_inches="tight")
        plt.close(fig)

        # CSV
        csv_df = build_csv_rows(requested, df_nq, df_es)
        csv_path = out_dir / f"{tf_label}.csv"
        csv_df.to_csv(csv_path, index=False)

        print(f"saved -> {png.name}  +  {csv_path.name}")

    print(f"\nDone. Charts saved to: {out_dir}")


if __name__ == "__main__":
    main()
