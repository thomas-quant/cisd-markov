"""
CISD (Close Implies Subsequent Direction) Analysis Suite
=========================================================
Loads 1-minute NQ & ES parquet data, resamples to daily / 4H / 1H / 15min,
and runs six independent CISD analyses on each instrument × timeframe.

Analyses
--------
  basic         – Run rate after CISD
  lr            – Whether low or high is breached first
  mc            – Run rate segmented by consecutive opposite candles
  significance  – Stricter CISD (close vs previous high/low)
  wick          – Run rate by wick-position of the CISD close
  combined      – Cross-tab of wick position × consecutive count

Usage
-----
    python cisd_analysis.py                     # all instruments, all TFs, all analyses
    python cisd_analysis.py basic wick          # selected analyses only
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Fix Windows terminal encoding for box-drawing characters
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# ── Configuration ────────────────────────────────────────────────────────────
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


# ── Data Loading & Resampling ───────────────────────────────────────────────

def load_1m(path: Path) -> pd.DataFrame:
    """Load a 1-minute parquet file and return a clean datetime-indexed OHLCV frame."""
    df = pd.read_parquet(path)
    df = df.set_index("DateTime_ET").sort_index()
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = [c.lower() for c in df.columns]
    return df


def resample_ohlcv(df_1m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample 1-minute bars to a coarser timeframe."""
    agg = {
        "open":   "first",
        "high":   "max",
        "low":    "min",
        "close":  "last",
        "volume": "sum",
    }
    resampled = df_1m.resample(rule).agg(agg).dropna(subset=["open"])
    return resampled


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Add direction, previous-bar helpers, and CISD identification columns."""
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


# ── Helpers ──────────────────────────────────────────────────────────────────

def pct(num: int, den: int) -> str:
    return f"{num / den * 100:.2f}%" if den > 0 else "N/A"


def _count_consecutive(idx: int, directions: pd.Series, target: str, max_n: int) -> int:
    count = 0
    for i in range(1, max_n + 1):
        pos = idx - i
        if pos < 0 or directions.iloc[pos] != target:
            break
        count += 1
    return count


# ── Analysis Functions ───────────────────────────────────────────────────────

def analyse_basic(df: pd.DataFrame) -> None:
    """Run rate: does price breach the CISD candle's high/low within LOOKAHEAD bars?"""
    print("\n  ┌─ BASIC CISD RUN RATE")

    df_cisd = df[df["cisd_type"].notna()]
    totals = {"bullish": 0, "bearish": 0}
    runs   = {"bullish": 0, "bearish": 0}

    for ts, row in df_cisd.iterrows():
        ct = row["cisd_type"]
        totals[ct] += 1
        future = df.loc[ts:].iloc[1 : LOOKAHEAD + 1]
        if future.empty:
            continue
        if ct == "bullish" and (future["high"] >= row["high"]).any():
            runs[ct] += 1
        elif ct == "bearish" and (future["low"] <= row["low"]).any():
            runs[ct] += 1

    for ct in ("bullish", "bearish"):
        t, r = totals[ct], runs[ct]
        print(f"  │  {ct.upper():8s}  {t:>5} events  →  runs {r}/{t} = {pct(r, t)}")
    print("  └─")


def analyse_lr(df: pd.DataFrame) -> None:
    """Which side of the CISD candle gets breached first — low or high?"""
    print("\n  ┌─ LOW / HIGH CROSSED FIRST")

    df_cisd = df[df["cisd_type"].notna()]
    results = {ct: {"low_first": 0, "high_first": 0, "total": 0} for ct in ("bullish", "bearish")}
    idxs = df.index

    for ts, row in df_cisd.iterrows():
        i     = idxs.get_loc(ts)
        ct    = row["cisd_type"]
        results[ct]["total"] += 1
        first = None

        for j in range(1, LOOKAHEAD + 1):
            if i + j >= len(df):
                break
            bar = df.iloc[i + j]
            if ct == "bullish":
                if first is None and bar["low"] <= row["low"]:
                    first = "low"
                if first is None and bar["high"] >= row["high"]:
                    first = "high"
            else:
                if first is None and bar["high"] >= row["high"]:
                    first = "high"
                if first is None and bar["low"] <= row["low"]:
                    first = "low"

        if first == "low":
            results[ct]["low_first"] += 1
        elif first == "high":
            results[ct]["high_first"] += 1

    for ct in ("bullish", "bearish"):
        r = results[ct]
        print(f"  │  {ct.upper():8s}  {r['total']:>5} events  "
              f"→  low first {r['low_first']}/{r['total']} = {pct(r['low_first'], r['total'])}"
              f"   high first {r['high_first']}/{r['total']} = {pct(r['high_first'], r['total'])}")
    print("  └─")


def analyse_mc(df: pd.DataFrame) -> None:
    """Run rate bucketed by number of consecutive opposite candles before the CISD."""
    print("\n  ┌─ CONSECUTIVE OPPOSITE CANDLES (MARKOV)")

    df_cisd    = df[df["cisd_type"].notna()]
    directions = df["direction"]
    idx_index  = df.index

    stats = {ct: {n: {"total": 0, "runs": 0} for n in range(1, MAX_CONSEC + 1)} for ct in ("bullish", "bearish")}

    for ts, row in df_cisd.iterrows():
        idx   = idx_index.get_loc(ts)
        ct    = row["cisd_type"]
        tgt   = "bearish" if ct == "bullish" else "bullish"
        consec = _count_consecutive(idx, directions, tgt, MAX_CONSEC)
        if consec < 1 or consec > MAX_CONSEC:
            continue
        stats[ct][consec]["total"] += 1
        future = df.iloc[idx + 1 : idx + 1 + LOOKAHEAD]
        if future.empty:
            continue
        ran = (future["high"] >= row["high"]).any() if ct == "bullish" else (future["low"] <= row["low"]).any()
        if ran:
            stats[ct][consec]["runs"] += 1

    for ct in ("bullish", "bearish"):
        for n in range(1, MAX_CONSEC + 1):
            t, r = stats[ct][n]["total"], stats[ct][n]["runs"]
            print(f"  │  {ct.upper():8s}  {n} consec  →  {t:>5} events  runs {r}/{t} = {pct(r, t)}")
    print("  └─")


def analyse_significance(df: pd.DataFrame) -> None:
    """Stricter CISD: bullish when close > prev HIGH, bearish when close < prev LOW."""
    print("\n  ┌─ SIGNIFICANCE TEST  (close vs prev high / low)")

    totals = {"bullish": 0, "bearish": 0}
    runs   = {"bullish": 0, "bearish": 0}

    for i in range(1, len(df) - LOOKAHEAD):
        prev_high  = df["high"].iloc[i - 1]
        prev_low   = df["low"].iloc[i - 1]
        curr_close = df["close"].iloc[i]

        if curr_close > prev_high:
            totals["bullish"] += 1
            h = df["high"].iloc[i]
            if (df["high"].iloc[i + 1 : i + 1 + LOOKAHEAD] >= h).any():
                runs["bullish"] += 1

        if curr_close < prev_low:
            totals["bearish"] += 1
            lo = df["low"].iloc[i]
            if (df["low"].iloc[i + 1 : i + 1 + LOOKAHEAD] <= lo).any():
                runs["bearish"] += 1

    for ct in ("bullish", "bearish"):
        t, r = totals[ct], runs[ct]
        print(f"  │  {ct.upper():8s}  {t:>5} events  →  runs {r}/{t} = {pct(r, t)}")
    print("  └─")


def analyse_wick(df: pd.DataFrame) -> None:
    """Run rate split by whether the CISD close exceeds the previous candle's wick."""
    print("\n  ┌─ WICK POSITION")

    stats = {
        "bullish": {"above_wick": {"total": 0, "runs": 0}, "within_wick": {"total": 0, "runs": 0}},
        "bearish": {"below_wick": {"total": 0, "runs": 0}, "within_wick": {"total": 0, "runs": 0}},
    }
    idx_index = df.index

    df_bull = df[(df["prev_direction"] == "bearish") & (df["close"] > df["prev_close"])]
    for ts, row in df_bull.iterrows():
        idx = idx_index.get_loc(ts)
        grp = "above_wick" if row["close"] > row["prev_high"] else "within_wick"
        stats["bullish"][grp]["total"] += 1
        future = df.iloc[idx + 1 : idx + 1 + LOOKAHEAD]
        if not future.empty and (future["high"] >= row["high"]).any():
            stats["bullish"][grp]["runs"] += 1

    df_bear = df[(df["prev_direction"] == "bullish") & (df["close"] < df["prev_close"])]
    for ts, row in df_bear.iterrows():
        idx = idx_index.get_loc(ts)
        grp = "below_wick" if row["close"] < row["prev_low"] else "within_wick"
        stats["bearish"][grp]["total"] += 1
        future = df.iloc[idx + 1 : idx + 1 + LOOKAHEAD]
        if not future.empty and (future["low"] <= row["low"]).any():
            stats["bearish"][grp]["runs"] += 1

    for ct, groups in stats.items():
        for grp_key, grp in groups.items():
            label = grp_key.replace("_", " ").title()
            t, r = grp["total"], grp["runs"]
            print(f"  │  {ct.upper():8s}  {label:18s}  →  {r}/{t} = {pct(r, t)}")
    print("  └─")


def analyse_combined(df: pd.DataFrame) -> None:
    """Cross-tab: wick position × consecutive opposite candle count → run rate."""
    print("\n  ┌─ COMBINED  (Wick × Consecutive)")

    df_cisd    = df[df["cisd_type"].notna()]
    directions = df["direction"]
    idx_index  = df.index

    stats = {ct: {n: {"above_wick": {"total": 0, "runs": 0}, "within_wick": {"total": 0, "runs": 0}}
                  for n in range(1, MAX_CONSEC + 1)} for ct in ("bullish", "bearish")}

    for ts, row in df_cisd.iterrows():
        idx   = idx_index.get_loc(ts)
        ct    = row["cisd_type"]
        tgt   = "bearish" if ct == "bullish" else "bullish"
        consec = _count_consecutive(idx, directions, tgt, MAX_CONSEC)
        if consec < 1 or consec > MAX_CONSEC:
            continue
        if ct == "bullish":
            above = row["close"] > row["prev_high"]
        else:
            above = row["close"] < row["prev_low"]
        grp = "above_wick" if above else "within_wick"
        stats[ct][consec][grp]["total"] += 1
        future = df.iloc[idx + 1 : idx + 1 + LOOKAHEAD]
        if future.empty:
            continue
        ran = (future["high"] >= row["high"]).any() if ct == "bullish" else (future["low"] <= row["low"]).any()
        if ran:
            stats[ct][consec][grp]["runs"] += 1

    for ct in ("bullish", "bearish"):
        for n in range(1, MAX_CONSEC + 1):
            for grp_key, label in [("above_wick", "Past wick"), ("within_wick", "Within wick")]:
                t = stats[ct][n][grp_key]["total"]
                r = stats[ct][n][grp_key]["runs"]
                print(f"  │  {ct.upper():8s}  {n} consec  {label:12s}  →  {r}/{t} = {pct(r, t)}")
    print("  └─")


# ── Dispatch ─────────────────────────────────────────────────────────────────

ANALYSES = {
    "basic":        ("Basic CISD run rate",                   analyse_basic),
    "lr":           ("Low / High crossed first",              analyse_lr),
    "mc":           ("Consecutive opposite candles (Markov)", analyse_mc),
    "significance": ("Significance test (close vs prev H/L)", analyse_significance),
    "wick":         ("Wick position",                         analyse_wick),
    "combined":     ("Combined wick + consecutive",           analyse_combined),
}


def main() -> None:
    requested = sys.argv[1:] if len(sys.argv) > 1 else list(ANALYSES.keys())
    invalid = [k for k in requested if k not in ANALYSES]
    if invalid:
        print(f"Unknown key(s): {', '.join(invalid)}")
        print(f"Valid: {', '.join(ANALYSES.keys())}")
        sys.exit(1)

    for instr_name, parquet_path in INSTRUMENTS.items():
        print(f"\nLoading {instr_name} from {parquet_path.name} ...")
        df_1m = load_1m(parquet_path)
        print(f"  {len(df_1m):,} 1-min bars loaded.")

        for tf_label, tf_rule in TIMEFRAMES.items():
            df_tf = resample_ohlcv(df_1m, tf_rule)
            df    = prepare(df_tf)
            cisd_n = df["cisd_type"].notna().sum()

            print(f"\n{'═' * 60}")
            print(f"  {instr_name} — {tf_label}    ({len(df):,} bars, {cisd_n:,} CISDs)")
            print(f"  Lookahead = {LOOKAHEAD} bars   Max consec = {MAX_CONSEC}")
            print(f"{'═' * 60}")

            for key in requested:
                _, fn = ANALYSES[key]
                fn(df)

    print()


if __name__ == "__main__":
    main()
