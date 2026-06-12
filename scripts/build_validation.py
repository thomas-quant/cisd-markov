"""Validation harness — discovery/OOS slicing, Wilson CI, sample-size gating, manifest CSV."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cisd_analysis import (
    INSTRUMENTS, TIMEFRAMES, OOS_START, MIN_N, CI_LEVEL,
    load_1m, resample_ohlcv, prepare_pair,
)

SLICES_PATH = REPO_ROOT / "output" / "validation_slices.csv"

# ── Sacred OOS banner ─────────────────────────────────────────────────────────

_OOS_BANNER = """
╔══════════════════════════════════════════════════════════════╗
║  ⚠  YOU ARE SPENDING YOUR ONE SACRED OOS EVALUATION  ⚠     ║
║  This run will operate on the held-out test set.            ║
║  This is a sacred evaluation — treat it as a final exam,    ║
║  not a sandbox. Results will be added to the manifest.      ║
╚══════════════════════════════════════════════════════════════╝
"""


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

    # Try to include SMT tagging; fall back gracefully if the external scanner
    # is unavailable so the rest of the study still runs.
    try:
        _first_rule = next(iter(TIMEFRAMES.values()))
        prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], _first_rule, with_swing_smt=True)
        with_smt = True
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] SMT unavailable ({exc}); swing SMT columns will be absent")
        with_smt = False

    rows = []
    for tf_label, tf_rule in TIMEFRAMES.items():
        df_nq, df_es = prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], tf_rule, with_swing_smt=with_smt)
        nq_sl = slice_df(df_nq, oos=args.oos)
        es_sl = slice_df(df_es, oos=args.oos)
        for inst, sl in (("NQ", nq_sl), ("ES", es_sl)):
            rows.append({
                "timeframe":  tf_label,
                "instrument": inst,
                "slice":      slice_label,
                "n_bars":     len(sl),
                "start_date": str(sl.index.min().date()) if len(sl) else "",
                "end_date":   str(sl.index.max().date()) if len(sl) else "",
            })
            print(f"  {tf_label} {inst}: {len(sl):,} bars ({slice_label})")

    SLICES_PATH.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(SLICES_PATH, index=False)
    print(f"Slice report → {SLICES_PATH}")
    print("Note: plan 02-02 will add the full per-bucket CI/n manifest (validation_manifest.csv).")


if __name__ == "__main__":
    main()
