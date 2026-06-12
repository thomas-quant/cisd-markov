"""
Unit tests for the five core compute functions using synthetic inline fixtures.

Each test uses a small, hand-verifiable OHLCV DataFrame so the expected
totals and runs can be confirmed without running the real pipeline or loading
parquet data.  These tests run in CI where no data files are present.

Design notes
------------
A shared 18-bar frame (_barrier_frame) exercises compute_basic, compute_mc,
compute_wick, and compute_combined in a single pass — the four CISD events are
constructed so each lands in a unique sub-bucket.

compute_significance receives a separate 8-bar frame because it recomputes
CISD from raw OHLC (close > prev_high / close < prev_low) and does NOT
consume cisd_type — tested independently to pin that behavior.

Neutral bars (close == open → direction="neutral") act as segment buffers,
preventing accidental CISD chaining across segments.

LOOKAHEAD = 2; the first lookahead bar always resolves the barrier so the
test does not depend on bar j+2.

Shared 18-bar frame layout
--------------------------
Block 1 (bars 0-4):
  Bar 0 : neutral buffer
  Bar 1 : 1 bearish setup  (n=1 for the upcoming Bull CISD)
  Bar 2 : BULLISH CISD     past_wick, n=1   — target hit at bar 3  → RUN
  Bar 3 : lookahead        high=118 ≥ target=118  → True
  Bar 4 : neutral buffer   (close==open prevents CISD chain)

Block 2 (bars 5-9):
  Bar 5 : 1st bearish setup
  Bar 6 : 2nd bearish setup  (n=2 for the upcoming Bull CISD)
  Bar 7 : BULLISH CISD     within_wick, n=2  — stop hit at bar 8  → NO RUN
  Bar 8 : lookahead        low=97 ≤ stop=97  → False
  Bar 9 : neutral buffer

Block 3 (bars 10-13):
  Bar 10: 1 bullish setup  (n=1 for the upcoming Bear CISD)
  Bar 11: BEARISH CISD     past_wick, n=1   — target hit at bar 12 → RUN
  Bar 12: lookahead        low=92 ≤ target=93  → True
  Bar 13: neutral buffer

Block 4 (bars 14-17):
  Bar 14: 1st bullish setup
  Bar 15: 2nd bullish setup  (n=2 for the upcoming Bear CISD)
  Bar 16: BEARISH CISD     within_wick, n=2  — stop hit at bar 17 → NO RUN
  Bar 17: lookahead        high=120 ≥ stop=120  → False

Barrier verification (LOOKAHEAD=2, first-touch semantics):
  Bar 2  bull  target=high[2]=118  → bar3.high=118 ≥ 118      → RUN
  Bar 7  bull  stop=low[7]=97      → bar8.low=97  ≤ 97         → NO RUN
  Bar 11 bear  target=low[11]=93   → bar12.low=92 ≤ 93         → RUN
  Bar 16 bear  stop=high[16]=120   → bar17.high=120 ≥ 120      → NO RUN

Wick classification (past_wick iff close > prev_high for bull, < prev_low for bear):
  Bar 2  bull  close=108 > prev_high[1]=106                    → past_wick
  Bar 7  bull  close=101 > prev_high[6]=105?  No               → within_wick
  Bar 11 bear  close=95  < prev_low[10]=97                     → past_wick
  Bar 16 bear  close=113 < prev_low[15]=104?  No               → within_wick
"""

import pandas as pd

import cisd_analysis


# ── Shared 18-bar fixture ──────────────────────────────────────────────────────

def _barrier_frame() -> pd.DataFrame:
    """
    Build the shared 18-bar synthetic frame and run it through prepare().

    All four CISDs are hand-verified (see module docstring).  The returned
    DataFrame has the cisd_type, prev_direction, prev_high, prev_low, and
    direction columns produced by the real prepare() code path.
    """
    index = pd.date_range("2026-01-05 09:30", periods=18, freq="15min")

    #          0    1    2    3    4    5    6    7    8    9   10   11   12   13   14   15   16   17
    opens  = [100, 105, 100, 113, 115, 110, 104,  99, 105, 101,  98, 107, 104,  93,  93, 105, 114, 116]
    highs  = [102, 106, 118, 118, 117, 112, 105, 120, 112, 103, 110, 110, 108,  95, 107, 117, 120, 120]
    lows   = [ 98,  98,  98, 101, 113, 103,  97,  97,  97,  99,  97,  93,  92,  91,  92, 104, 110, 108]
    closes = [100,  99, 108, 115, 115, 104,  98, 101, 101, 101, 108,  95,  93,  93, 105, 115, 113, 112]
    vols   = [1000] * 18

    raw = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=index,
    )
    return cisd_analysis.prepare(raw)


# ── compute_basic ─────────────────────────────────────────────────────────────

def test_compute_basic_totals_and_runs():
    """
    compute_basic over the 18-bar frame must detect exactly 2 bull and 2 bear
    CISDs and count 1 run for each direction — one event hits target, the other
    hits stop.
    """
    df = _barrier_frame()
    result = cisd_analysis.compute_basic(df)

    assert result["totals"]["bullish"] == 2
    assert result["totals"]["bearish"] == 2
    assert result["runs"]["bullish"]   == 1
    assert result["runs"]["bearish"]   == 1


# ── compute_mc ───────────────────────────────────────────────────────────────

def test_compute_mc_buckets_total_and_runs():
    """
    compute_mc must assign each CISD to the correct consecutive-candle bucket
    and count barrier outcomes per bucket independently.

    Expected from the 18-bar frame:
      bull n=1: total=1  runs=1  (past_wick target hit)
      bull n=2: total=1  runs=0  (within_wick stop hit)
      bull n=3: total=0  runs=0  (no events)
      bear n=1: total=1  runs=1  (past_wick target hit)
      bear n=2: total=1  runs=0  (within_wick stop hit)
      bear n=3: total=0  runs=0  (no events)
    """
    df = _barrier_frame()
    result = cisd_analysis.compute_mc(df)

    assert result["bullish"][1]["total"] == 1
    assert result["bullish"][1]["runs"]  == 1
    assert result["bullish"][2]["total"] == 1
    assert result["bullish"][2]["runs"]  == 0
    assert result["bullish"][3]["total"] == 0
    assert result["bullish"][3]["runs"]  == 0

    assert result["bearish"][1]["total"] == 1
    assert result["bearish"][1]["runs"]  == 1
    assert result["bearish"][2]["total"] == 1
    assert result["bearish"][2]["runs"]  == 0
    assert result["bearish"][3]["total"] == 0
    assert result["bearish"][3]["runs"]  == 0


# ── compute_significance ──────────────────────────────────────────────────────
#
# compute_significance recomputes CISD independently from raw OHLC:
#   bullish sig: close[i] > high[i-1]
#   bearish sig: close[i] < low[i-1]
# It does NOT consume cisd_type.  The tests below pin both behaviors.
#
# 8-bar frame:
#   Bar 0 : bearish;      high[0]=106, low[0]=98
#   Bar 1 : close=107 > high[0]=106  → bullish sig CISD; target=108, stop=101
#   Bar 2 : high=108 ≥ 108           → TARGET HIT  (runs["bullish"] += 1)
#   Bar 3 : no sig CISD  (close=105; 105 ≤ high[2]=108 and 105 ≥ low[2]=103)
#   Bar 4 : close=95  < low[3]=103   → bearish sig CISD; target=94,  stop=110
#   Bar 5 : high=110 ≥ high[4]=110   → STOP HIT   (runs["bearish"] unchanged)
#   Bars 6-7: padding (loop range is [1 .. len(df)-LOOKAHEAD-1] = [1..5])

def _significance_frame() -> pd.DataFrame:
    """
    Build an 8-bar raw OHLCV frame for compute_significance.

    prepare() is intentionally NOT called — compute_significance only reads
    the raw high, low, close columns and does not consume cisd_type or any
    prev_* column.
    """
    index = pd.date_range("2026-01-06 09:30", periods=8, freq="15min")

    #          0    1    2    3    4    5    6    7
    opens  = [104, 101, 105, 104, 107, 100, 108, 108]
    highs  = [106, 108, 108, 107, 110, 110, 110, 111]
    lows   = [ 98, 101, 103, 103,  94,  98, 106, 107]
    closes = [100, 107, 104, 105,  95, 108, 108, 109]
    vols   = [1000] * 8

    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=index,
    )


def test_compute_significance_does_not_use_cisd_type():
    """
    compute_significance must work on a raw (non-prepared) DataFrame.
    The 'cisd_type' column must be absent, and the function must not raise.
    """
    df = _significance_frame()
    assert "cisd_type" not in df.columns

    result = cisd_analysis.compute_significance(df)

    assert "totals" in result
    assert "runs" in result


def test_compute_significance_totals_and_runs():
    """
    compute_significance on the 8-bar frame must detect exactly 1 bullish sig
    CISD (hits target) and 1 bearish sig CISD (hits stop), yielding:
      totals = {"bullish": 1, "bearish": 1}
      runs   = {"bullish": 1, "bearish": 0}
    """
    df = _significance_frame()
    result = cisd_analysis.compute_significance(df)

    assert result["totals"]["bullish"] == 1
    assert result["totals"]["bearish"] == 1
    assert result["runs"]["bullish"]   == 1
    assert result["runs"]["bearish"]   == 0


# ── compute_wick ──────────────────────────────────────────────────────────────

def test_compute_wick_past_and_within_totals_and_runs():
    """
    compute_wick on the 18-bar frame must populate all four wick/direction
    buckets and record the correct barrier outcome for each:
      bull past_wick:   total=1  runs=1   (bar 2 hits target)
      bull within_wick: total=1  runs=0   (bar 7 hits stop)
      bear past_wick:   total=1  runs=1   (bar 11 hits target)
      bear within_wick: total=1  runs=0   (bar 16 hits stop)
    """
    df = _barrier_frame()
    result = cisd_analysis.compute_wick(df)

    assert result["bullish"]["past_wick"]["total"]   == 1
    assert result["bullish"]["past_wick"]["runs"]    == 1
    assert result["bullish"]["within_wick"]["total"] == 1
    assert result["bullish"]["within_wick"]["runs"]  == 0

    assert result["bearish"]["past_wick"]["total"]   == 1
    assert result["bearish"]["past_wick"]["runs"]    == 1
    assert result["bearish"]["within_wick"]["total"] == 1
    assert result["bearish"]["within_wick"]["runs"]  == 0


# ── compute_combined ──────────────────────────────────────────────────────────

def test_compute_combined_cross_tab_totals_and_runs():
    """
    compute_combined cross-tabs wick position × consecutive candle count.
    The 18-bar frame places exactly one event in each of four occupied cells;
    all other cells must be empty.

    Occupied:
      bull n=1 past_wick:   total=1  runs=1
      bull n=2 within_wick: total=1  runs=0
      bear n=1 past_wick:   total=1  runs=1
      bear n=2 within_wick: total=1  runs=0
    """
    df = _barrier_frame()
    result = cisd_analysis.compute_combined(df)

    # Bullish occupied buckets
    assert result["bullish"][1]["past_wick"]["total"]   == 1
    assert result["bullish"][1]["past_wick"]["runs"]    == 1
    assert result["bullish"][2]["within_wick"]["total"] == 1
    assert result["bullish"][2]["within_wick"]["runs"]  == 0

    # Bullish empty buckets
    assert result["bullish"][1]["within_wick"]["total"] == 0
    assert result["bullish"][2]["past_wick"]["total"]   == 0
    assert result["bullish"][3]["past_wick"]["total"]   == 0
    assert result["bullish"][3]["within_wick"]["total"] == 0

    # Bearish occupied buckets
    assert result["bearish"][1]["past_wick"]["total"]   == 1
    assert result["bearish"][1]["past_wick"]["runs"]    == 1
    assert result["bearish"][2]["within_wick"]["total"] == 1
    assert result["bearish"][2]["within_wick"]["runs"]  == 0

    # Bearish empty buckets
    assert result["bearish"][1]["within_wick"]["total"] == 0
    assert result["bearish"][2]["past_wick"]["total"]   == 0
    assert result["bearish"][3]["past_wick"]["total"]   == 0
    assert result["bearish"][3]["within_wick"]["total"] == 0
