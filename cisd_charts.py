"""
cisd_charts.py — Chart Functions and Figure Builders
=====================================================
Contains the matplotlib rendering layer: 14 chart_* functions, the
build_figure / build_standalone_figure / build_csv_rows builders, and
the shared visual primitives (COLORS, _bar_label, _style_ax, pv).

The ANALYSES registry lives in cisd_barriers.py, which imports chart
functions from here.  build_figure, build_standalone_figure, and
build_csv_rows import ANALYSES lazily inside their function bodies to
avoid a circular import.

Import chain (one-directional, no cycles):
    cisd_analysis -> cisd_charts -> cisd_data
    cisd_analysis -> cisd_barriers -> cisd_charts -> cisd_data
"""

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from cisd_data import (
    LOOKAHEAD,
    MAX_CONSEC,
    FVG_HOLD_LOOKAHEAD,
    TIMEFRAMES,
)

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


# ── Shared Visual Primitives ──────────────────────────────────────────────────

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


def _standalone_lookahead_caption(key: str) -> str:
    if key == "fvg_hold":
        return f"FVG hold window = {FVG_HOLD_LOOKAHEAD} bars"
    if key == "cisd_fvg_interaction":
        return f"CISD barrier = {LOOKAHEAD} bars | FVG hold window = {FVG_HOLD_LOOKAHEAD} bars"
    return f"Lookahead = {LOOKAHEAD} bars"


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


def chart_volume(ax, data_nq, data_es):
    all_labels = [lbl for _, _, lbl in
                  [(0, 1.0, "<1x (lower vol)"), (1.0, 1.5, "1x-1.5x"),
                   (1.5, 2.5, "1.5x-2.5x"), (2.5, 1e18, ">2.5x (spike)")]]
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for lbl in all_labels:
                d = data[ct][lbl]
                rows.append((f"{instr} {ct.capitalize()} {lbl}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]), COLORS[instr][ct]))
    bars = [ax.barh(r[0], r[1], color=r[2], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Volume Ratio  (CISD candle vs previous)")


def chart_candle_size(ax, data_nq, data_es):
    all_labels = [lbl for _, _, lbl in
                  [(0, 0.5, "<0.5x ATR"), (0.5, 1.0, "0.5x-1x ATR"),
                   (1.0, 1.5, "1x-1.5x ATR"), (1.5, 1e18, ">1.5x ATR")]]
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for lbl in all_labels:
                d = data[ct][lbl]
                rows.append((f"{instr} {ct.capitalize()} {lbl}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]), COLORS[instr][ct]))
    bars = [ax.barh(r[0], r[1], color=r[2], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Candle Body Size vs ATR(14)")


def chart_size_cross(ax, data_nq, data_es):
    bucket_labels = ["Big CISD / Small prev", "Big CISD / Big prev",
                     "Small CISD / Small prev", "Small CISD / Big prev"]
    # Alpha: full for Big CISD rows, dimmed for Small CISD rows
    alphas = [1.0, 0.7, 0.5, 0.35]
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for lbl, alpha in zip(bucket_labels, alphas):
                d = data[ct][lbl]
                rows.append((f"{instr} {ct.capitalize()} — {lbl}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]),
                             COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55)
            for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "CISD Body x Prev Body vs ATR(14)")


def chart_smt_cisd(ax, data_nq, data_es):
    # Three-way tags only (D-03); the "w/ SMT & survived"/"w/ SMT & broke"
    # diagnostic sub-buckets are manifest-only (SC4) and intentionally not
    # rendered here to avoid double-counting rows in a single axis.
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in (("w/ SMT", 1.0), ("expired SMT", 0.75), ("no SMT", 0.45)):
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]), COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55)
            for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Swing SMT Confirmation")


def chart_smt_role(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in (("swept", 1.0), ("failed_to_sweep", 0.6)):
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]), COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55)
            for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Swing SMT Role (Swept vs Failed-to-Sweep)")


def chart_smt_block_size(ax, data_nq, data_es):
    bucket_labels = ["<0.5x ATR", "0.5x-1x ATR", "1x-1.5x ATR", ">1.5x ATR"]
    alphas = [1.0, 0.75, 0.55, 0.4]
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for lbl, alpha in zip(bucket_labels, alphas):
                d = data[ct][lbl]
                rows.append((f"{instr} {ct.capitalize()} {lbl}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]), COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55)
            for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "SMT Block Size vs ATR(14)")


def chart_smt_in_block(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in (("cisd_in_block", 1.0), ("cisd_out_block", 0.55)):
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]), COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55)
            for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "CISD Inside SMT Block")


def chart_cisd_fvg(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in (("mid0_fvg", 1.0), ("mid1_fvg", 0.75), ("no_fvg", 0.45)):
                d = data[ct][tag]
                rows.append(
                    (f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})", pv(d["runs"], d["total"]), COLORS[instr][ct], alpha)
                )
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "CISD FVG Creation")


def chart_fvg_hold(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for bucket, alpha in (("mid0", 1.0), ("mid1", 0.7)):
                for mode, label in (("close_through_near_edge", "close near"), ("wick_break_far_extreme", "wick far")):
                    d = data[ct][bucket][mode]
                    rows.append(
                        (f"{instr} {ct.capitalize()} {bucket} {label}  (n={d['total']:,})", pv(d["held"], d["total"]), COLORS[instr][ct], alpha)
                    )
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "FVG Hold")
    ax.set_xlabel("Hold Rate (%)")


def chart_cisd_fvg_interaction(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for bucket, alpha in (("mid0", 1.0), ("mid1", 0.7)):
                for mode, label in (("close_through_near_edge", "close near"), ("wick_break_far_extreme", "wick far")):
                    for state in ("held", "failed"):
                        d = data[ct][bucket][mode][state]
                        rows.append(
                            (
                                f"{instr} {ct.capitalize()} {bucket} {label} {state}  (n={d['total']:,})",
                                pv(d["runs"], d["total"]),
                                COLORS[instr][ct],
                                alpha,
                            )
                        )
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.5) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "CISD FVG Interaction")


def chart_sweep(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in (("w/ sweep", 1.0), ("no sweep", 0.55)):
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})", pv(d["runs"], d["total"]), COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Sweep Confirmation")


def chart_sssf_swing(ax, data_nq, data_es):
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in (("prev_bar_is_swing", 1.0), ("cisd_bar_is_swing", 0.75), ("neither", 0.45)):
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})", pv(d["runs"], d["total"]), COLORS[instr][ct], alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "SSSF Swing")


def chart_post_cisd_context(ax, data_nq, data_es):
    # Tag order: gap_with (most aligned), gap_against (reversal context), gap_flat, Reading B
    _TAGS = [
        ("failed_gap_with",          1.0),
        ("failed_gap_against",       0.7),
        ("failed_gap_against_reversal", 0.55),
        ("failed_gap_against_neither",  0.4),
        ("failed_gap_flat",          0.45),
        ("candle2_past_candle1_wick", 0.85),
    ]
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in _TAGS:
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]),
                             COLORS[instr][ct],
                             alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Post-CISD Context (Candle[1] Failed + Candle[2] Gap)")


def chart_candle1_followthrough(ax, data_nq, data_es):
    # Tag order: in-window first (alpha 1.0/0.7/0.85), forward after (alpha 0.55/0.35/0.65)
    # Visual layering: in-window is solid, forward is dimmed to make the tautology gap visible
    _TAGS = [
        ("against_inwindow",       1.0),
        ("with_within_wick_inwindow", 0.7),
        ("with_past_wick_inwindow",   0.85),
        ("against_forward",           0.5),
        ("with_within_wick_forward",  0.35),
        ("with_past_wick_forward",    0.65),
    ]
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in _TAGS:
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]),
                             COLORS[instr][ct],
                             alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Candle[1] Follow-Through (In-Window vs Forward Re-Anchored)")


# ── Figure Builders ───────────────────────────────────────────────────────────

def build_csv_rows(keys: list, df_nq: pd.DataFrame, df_es: pd.DataFrame) -> pd.DataFrame:
    """Flatten all analysis results into a tidy long-format table."""
    from cisd_barriers import ANALYSES  # lazy import to avoid circular dependency

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

            elif key in ("volume", "candle_size", "size_cross"):
                # Generic: data[ct] is a dict of label -> {total, runs}
                for ct in ("bullish", "bearish"):
                    for bucket_lbl, d in data[ct].items():
                        add(label, instr, ct, bucket_lbl, d["total"], d["runs"])

            elif key == "smt_cisd":
                for ct in ("bullish", "bearish"):
                    for tag, d in data[ct].items():
                        add(label, instr, ct, tag, d["total"], d["runs"])

            elif key == "cisd_fvg":
                for ct in ("bullish", "bearish"):
                    for tag, d in data[ct].items():
                        add(label, instr, ct, tag, d["total"], d["runs"])

            elif key == "fvg_hold":
                for ct in ("bullish", "bearish"):
                    for bucket in ("mid0", "mid1"):
                        for mode, d in data[ct][bucket].items():
                            add(label, instr, ct, f"{bucket}_{mode}", d["total"], d["held"])

            elif key == "cisd_fvg_interaction":
                for ct in ("bullish", "bearish"):
                    for bucket in ("mid0", "mid1"):
                        for mode, state_map in data[ct][bucket].items():
                            for state, d in state_map.items():
                                add(label, instr, ct, f"{bucket}_{mode}_{state}", d["total"], d["runs"])

            elif key in ("sweep", "sssf_swing", "candle1_followthrough", "post_cisd_context"):
                for ct in ("bullish", "bearish"):
                    for tag, d in data[ct].items():
                        add(label, instr, ct, tag, d["total"], d["runs"])

    return pd.DataFrame(rows)


def build_figure(tf_label: str, df_nq: pd.DataFrame, df_es: pd.DataFrame, keys: list) -> plt.Figure:
    """One figure per timeframe — all analyses as subplots, NQ & ES compared in each."""
    from cisd_barriers import ANALYSES, ANALYSIS_META  # lazy import to avoid circular dependency

    n = len(keys)
    ncols = 2 if n > 1 else 1
    nrows = (n + 1) // 2

    # Per-subplot height hints derived from ANALYSIS_META (single source of truth).
    # Fall back to 4 for any key absent from ANALYSIS_META to preserve prior semantics.
    row_heights = []
    for i, key in enumerate(keys):
        if i % 2 == 0:
            pair = keys[i:i+2]
            row_heights.append(max(
                ANALYSIS_META[k].per_tf_height if k in ANALYSIS_META else 4
                for k in pair
            ))

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


def build_standalone_figure(key: str, prepared: dict) -> plt.Figure:
    """
    Dedicated figure for a single analysis showing all 4 timeframes in a 2x2 grid.
    `prepared` = {"NQ": {tf_label: df, ...}, "ES": {tf_label: df, ...}}
    """
    from cisd_barriers import ANALYSES, ANALYSIS_META  # lazy import to avoid circular dependency
    from matplotlib.patches import Patch

    _, compute_fn, chart_fn = ANALYSES[key]
    tf_labels = list(TIMEFRAMES.keys())   # Daily, 4H, 1H, 15min

    # Standalone subplot height derived from ANALYSIS_META (single source of truth).
    # standalone_height is None for non-standalone keys; fall back to 6 in that case.
    meta = ANALYSIS_META.get(key)
    subplot_h = (meta.standalone_height if meta is not None and meta.standalone_height is not None else 6)
    fig, axes = plt.subplots(
        2, 2,
        figsize=(20, subplot_h * 2),
        squeeze=False,
    )
    axes_flat = [ax for row in axes for ax in row]

    analysis_label = ANALYSES[key][0]
    fig.suptitle(
        f"{analysis_label}  —  All Timeframes  |  {_standalone_lookahead_caption(key)}",
        fontsize=13, fontweight="bold", color="#e0e4f0", y=1.01,
    )

    for i, tf_label in enumerate(tf_labels):
        ax = axes_flat[i]
        d_nq = compute_fn(prepared["NQ"][tf_label])
        d_es = compute_fn(prepared["ES"][tf_label])
        chart_fn(ax, d_nq, d_es)
        # Prefix the subplot title with the timeframe
        ax.set_title(f"{tf_label}  —  {ax.get_title()}", fontsize=10,
                     fontweight="bold", pad=6)

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


__all__ = [
    # Visual primitives
    "COLORS",
    "pv",
    "_bar_label",
    "_style_ax",
    "_standalone_lookahead_caption",
    # Chart functions
    "chart_basic",
    "chart_mc",
    "chart_significance",
    "chart_wick",
    "chart_combined",
    "chart_volume",
    "chart_candle_size",
    "chart_size_cross",
    "chart_smt_cisd",
    "chart_smt_role",
    "chart_smt_block_size",
    "chart_smt_in_block",
    "chart_cisd_fvg",
    "chart_fvg_hold",
    "chart_cisd_fvg_interaction",
    "chart_sweep",
    "chart_sssf_swing",
    "chart_candle1_followthrough",
    "chart_post_cisd_context",
    # Figure builders
    "build_csv_rows",
    "build_figure",
    "build_standalone_figure",
]
