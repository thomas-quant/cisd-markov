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

# ── Re-export shim ────────────────────────────────────────────────────────────
# All logic lives in cisd_data / cisd_barriers / cisd_charts.
# This module re-exports the full public API so that scripts/ and tests/
# can continue to import from cisd_analysis without any changes.

import sys
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from cisd_data import (
    DATA_DIR,
    INSTRUMENTS,
    TIMEFRAMES,
    LOOKAHEAD,
    MAX_CONSEC,
    SMT_LOOKBACK,
    FVG_HOLD_LOOKAHEAD,
    SWEEP_TOLERANCE,
    SWEEP_SWING_LOOKBACK,
    _SMT_PKG_PATH,
    OOS_START,
    MIN_N,
    CI_LEVEL,
    WALK_FORWARD_FOLDS,
    load_1m,
    _normalize_resample_rule,
    resample_ohlcv,
    prepare,
    _compute_three_bar_swings,
    _has_directional_fvg,
    _classify_fvg_hold,
    _has_directional_sweep,
    _annotate_cisd_research,
    _annotate_swing_smt_from_events,
    _to_smt_ohlc,
    _load_scan_smts_historical,
    _scan_swing_smt_events,
)

from cisd_barriers import (
    barrier_hit,
    barrier_hit_forward,
    _count_consecutive,
    ANALYSES,
    ANALYSIS_META,
    compute_basic,
    compute_mc,
    compute_significance,
    compute_wick,
    compute_combined,
    compute_volume,
    compute_candle_size,
    compute_size_cross,
    compute_smt_cisd,
    compute_cisd_fvg,
    compute_fvg_hold,
    compute_cisd_fvg_interaction,
    compute_sweep,
    compute_sssf_swing,
    compute_candle1_followthrough,
    compute_post_cisd_context,
)

from cisd_charts import (
    COLORS,
    pv,
    _bar_label,
    _style_ax,
    _standalone_lookahead_caption,
    chart_basic,
    chart_mc,
    chart_significance,
    chart_wick,
    chart_combined,
    chart_volume,
    chart_candle_size,
    chart_size_cross,
    chart_smt_cisd,
    chart_cisd_fvg,
    chart_fvg_hold,
    chart_cisd_fvg_interaction,
    chart_sweep,
    chart_sssf_swing,
    chart_candle1_followthrough,
    chart_post_cisd_context,
    build_csv_rows,
    build_figure,
    build_standalone_figure,
)


def prepare_pair(
    df_nq_1m: pd.DataFrame,
    df_es_1m: pd.DataFrame,
    rule: str,
    with_swing_smt: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Dual-instrument pipeline with optional SMT scan.

    Defined here (not just re-exported from cisd_data) so that
    ``monkeypatch.setattr(cisd_analysis, '_scan_swing_smt_events', ...)``
    in tests intercepts the scan call — monkeypatching a re-exported name
    only affects this module's namespace, which this function honours because
    it calls ``_scan_swing_smt_events`` from its own (cisd_analysis) scope.
    """
    resampled_nq = resample_ohlcv(df_nq_1m, rule)
    resampled_es = resample_ohlcv(df_es_1m, rule)
    df_nq = prepare(resampled_nq)
    df_es = prepare(resampled_es)

    if not with_swing_smt:
        return df_nq, df_es

    shared_index = resampled_nq.index.intersection(resampled_es.index)
    events = _scan_swing_smt_events(
        resampled_nq.loc[shared_index],
        resampled_es.loc[shared_index],
    )
    return (
        _annotate_swing_smt_from_events(df_nq, events, instrument="NQ"),
        _annotate_swing_smt_from_events(df_es, events, instrument="ES"),
    )


__all__ = [
    # cisd_data exports
    "DATA_DIR", "INSTRUMENTS", "TIMEFRAMES", "LOOKAHEAD", "MAX_CONSEC",
    "SMT_LOOKBACK", "FVG_HOLD_LOOKAHEAD", "SWEEP_TOLERANCE", "SWEEP_SWING_LOOKBACK",
    "_SMT_PKG_PATH", "OOS_START", "MIN_N", "CI_LEVEL", "WALK_FORWARD_FOLDS",
    "load_1m", "_normalize_resample_rule", "resample_ohlcv", "prepare",
    "_compute_three_bar_swings", "_has_directional_fvg", "_classify_fvg_hold",
    "_has_directional_sweep", "_annotate_cisd_research",
    "_annotate_swing_smt_from_events", "_to_smt_ohlc",
    "_load_scan_smts_historical", "_scan_swing_smt_events", "prepare_pair",
    # cisd_barriers exports
    "barrier_hit", "barrier_hit_forward", "_count_consecutive", "ANALYSES", "ANALYSIS_META",
    "compute_basic", "compute_mc", "compute_significance", "compute_wick",
    "compute_combined", "compute_volume", "compute_candle_size", "compute_size_cross",
    "compute_smt_cisd", "compute_cisd_fvg", "compute_fvg_hold",
    "compute_cisd_fvg_interaction", "compute_sweep", "compute_sssf_swing",
    "compute_candle1_followthrough",
    # cisd_charts exports
    "COLORS", "pv", "_bar_label", "_style_ax", "_standalone_lookahead_caption",
    "chart_basic", "chart_mc", "chart_significance", "chart_wick", "chart_combined",
    "chart_volume", "chart_candle_size", "chart_size_cross", "chart_smt_cisd",
    "chart_cisd_fvg", "chart_fvg_hold", "chart_cisd_fvg_interaction",
    "chart_sweep", "chart_sssf_swing",
    "chart_candle1_followthrough",
    "build_csv_rows", "build_figure", "build_standalone_figure",
]


# ── CLI Orchestrator ──────────────────────────────────────────────────────────

def main() -> None:
    # Keys that get their own all-TF figure rather than appearing per-TF.
    # Derived from ANALYSIS_META — adding a new standalone analysis only requires
    # editing ANALYSIS_META in cisd_barriers.py (REFAC-02).
    STANDALONE_KEYS = {k for k, m in ANALYSIS_META.items() if m.standalone}

    requested = sys.argv[1:] if len(sys.argv) > 1 else list(ANALYSES.keys())
    invalid = [k for k in requested if k not in ANALYSES]
    if invalid:
        print(f"Unknown key(s): {', '.join(invalid)}")
        print(f"Valid: {', '.join(ANALYSES.keys())}")
        sys.exit(1)

    per_tf_keys  = [k for k in requested if k not in STANDALONE_KEYS]
    standalone   = [k for k in requested if k in STANDALONE_KEYS]
    needs_swing_smt = "smt_cisd" in requested

    if needs_swing_smt and not _SMT_PKG_PATH.exists():
        print(f"[warn] SMT package not found at {_SMT_PKG_PATH!s}; skipping smt_cisd analysis.")
        requested       = [k for k in requested if k != "smt_cisd"]
        standalone      = [k for k in standalone if k != "smt_cisd"]
        needs_swing_smt = False

    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)

    # Load 1-min data once per instrument
    print("Loading parquet data...")
    dfs_1m = {}
    for instr, path in INSTRUMENTS.items():
        print(f"  {instr} from {path.name} ...", end=" ", flush=True)
        dfs_1m[instr] = load_1m(path)
        print(f"{len(dfs_1m[instr]):,} bars")

    # Cache prepared DFs — needed for standalone figures
    prepared = {"NQ": {}, "ES": {}}

    for tf_label, tf_rule in TIMEFRAMES.items():
        print(f"\nComputing {tf_label} ...", end=" ", flush=True)
        df_nq, df_es = prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], tf_rule, with_swing_smt=needs_swing_smt)
        prepared["NQ"][tf_label] = df_nq
        prepared["ES"][tf_label] = df_es

        if per_tf_keys:
            fig  = build_figure(tf_label, df_nq, df_es, per_tf_keys)
            png  = out_dir / f"{tf_label}.png"
            fig.savefig(png, dpi=150, bbox_inches="tight")
            plt.close(fig)

            csv_df   = build_csv_rows(per_tf_keys, df_nq, df_es)
            csv_path = out_dir / f"{tf_label}.csv"
            csv_df.to_csv(csv_path, index=False)
            print(f"saved -> {png.name}  +  {csv_path.name}")
        else:
            print("(per-TF analyses skipped)")

    # ── Standalone all-TF figures ─────────────────────────────────────────────
    # Derived from ANALYSIS_META — single source of truth for filenames (REFAC-02).
    FILENAMES = {k: m.filename for k, m in ANALYSIS_META.items() if m.standalone}
    for key in standalone:
        print(f"\nBuilding standalone: {key} ...", end=" ", flush=True)
        fig  = build_standalone_figure(key, prepared)
        png  = out_dir / FILENAMES[key]
        fig.savefig(png, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"saved -> {png.name}")

    print(f"\nDone. Output: {out_dir}")


if __name__ == "__main__":
    main()
