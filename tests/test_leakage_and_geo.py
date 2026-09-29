"""Quick task 260929-mkg — look-ahead leakage, corridor-position null, session.

1. Causality: every conditioning column is invariant to bars after the bar
   at which it is claimed to be known (k=0: the CISD bar, k=1: t+1, k=2: t+2).
   The scoring frame of each analysis must start after its conditioners' k.
2. barrier_hit_after: confirm-then-enter entry and resolved-before-entry exclusion.
3. Corridor-position baseline math, manifest geo columns, geo verdicts.
4. Session tagging at the bar midpoint (1H 09:00 bar contains the 09:30 open).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import cisd_analysis
from cisd_analysis import (
    attach_geo_baseline, barrier_hit, barrier_hit_after, compute_basic, is_diagnostic, prepare,
)
from scripts import build_validation as bv
from scripts.build_reconcile_findings import determine_geo_verdict


def _random_walk(n: int, seed: int, start: float = 100.0, freq: str = "15min",
                 t0: str = "2026-01-05 00:00") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = start + np.cumsum(rng.normal(0, 1, n))
    open_ = np.r_[start, close[:-1]] + rng.normal(0, 0.2, n)
    high = np.maximum(open_, close) + rng.exponential(0.5, n)
    low = np.minimum(open_, close) - rng.exponential(0.5, n)
    volume = rng.integers(100, 1000, n).astype(float)
    idx = pd.date_range(t0, periods=n, freq=freq)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)


# Conditioning columns by the last bar they may read (relative to the CISD bar t).
_KNOWN_AT = {
    0: ["cisd_type", "wick_distance_atr", "swept_level", "sweep_depth_atr", "has_dir_sweep",
        "prev_bar_is_dir_swing", "session_tag", "vol_per_range", "rvol", "volume_zscore"],
    1: ["has_dir_fvg_mid0", "cisd_bar_is_dir_swing", "candle1_close_dir",
        "candle1_past_candle0_wick", "candle1_failed_followthrough"],
    2: ["has_dir_fvg_mid1", "fvg_gap_width", "fvg_size_atr", "candle2_past_candle1_wick"],
}

# Scoring frame (first bar of the barrier window minus one) per analysis whose
# conditioners live above k=0. Every conditioner an analysis reads must have
# known-at <= its frame's k.
_ANALYSIS_FRAME = {"cisd_fvg": 2, "fvg_size": 2, "sssf_swing": 1}


def _same(a: object, b: object) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


@pytest.mark.parametrize("k", [0, 1, 2])
def test_conditioners_are_invariant_to_bars_after_their_known_bar(k):
    base = _random_walk(700, seed=7)
    ref = prepare(base)
    positions = range(60, 640, 23)
    for t in positions:
        alt = base.copy()
        tail = _random_walk(len(base) - (t + k + 1), seed=1000 + t,
                            start=float(base["close"].iloc[t + k]))
        alt.iloc[t + k + 1:, :] = tail.to_numpy()
        got = prepare(alt)
        for col in _KNOWN_AT[k]:
            assert _same(ref[col].iloc[t], got[col].iloc[t]), (
                f"{col} at t={t} changed when bars after t+{k} changed (look-ahead)"
            )


def test_leaky_conditioners_are_scored_after_confirmation():
    assert _ANALYSIS_FRAME["cisd_fvg"] >= 2 and _ANALYSIS_FRAME["fvg_size"] >= 2
    assert _ANALYSIS_FRAME["sssf_swing"] >= 1
    # Behavioral check on a random walk: under confirm-then-enter a mid0 FVG
    # event can be stopped on the first scored bar again (it could not be
    # stopped on t+1 under the old in-window frame).
    df = prepare(_random_walk(3000, seed=3))
    stopped_first = 0
    for pos in np.flatnonzero(df["has_dir_fvg_mid0"].to_numpy()):
        ct, row = df["cisd_type"].iloc[pos], df.iloc[pos]
        if barrier_hit_after(df, pos, row, ct, 2) is None or pos + 3 >= len(df):
            continue
        nxt = df.iloc[pos + 3]
        stopped_first += (nxt["low"] <= row["low"]) if ct == "bullish" else (nxt["high"] >= row["high"])
    assert stopped_first > 0


# ── barrier_hit_after ─────────────────────────────────────────────────────────

def _cte_frame() -> pd.DataFrame:
    idx = pd.date_range("2026-01-05 09:30", periods=8, freq="15min")
    return pd.DataFrame({
        "open":  [10, 9, 10, 10, 11, 12, 11, 10.5],
        "high":  [10.5, 12, 11.5, 11.8, 12.5, 13, 12, 11],
        "low":   [9.5, 8, 9, 9.5, 10, 10, 9.5, 10.2],
        "close": [10, 11, 10, 11, 12, 10.5, 10.5, 10.5],
        "cisd_type": [None, "bullish", None, None, None, "bearish", None, None],
    }, index=idx)


def test_barrier_hit_after_shifts_the_window_past_the_confirming_bar():
    df = _cte_frame()
    row = df.iloc[1]
    assert barrier_hit(df, 1, row, "bullish") is False         # bars 2-3: timeout
    assert barrier_hit_after(df, 1, row, "bullish", 1) is True  # bars 3-4
    assert barrier_hit_after(df, 1, row, "bullish", 2) is True  # bars 4-5


def test_barrier_hit_after_excludes_setups_resolved_before_entry():
    df = _cte_frame()
    row = df.iloc[5]
    assert barrier_hit(df, 5, row, "bearish") is True           # target on bar 6
    assert barrier_hit_after(df, 5, row, "bearish", 1) is None
    assert barrier_hit_after(df, 5, row, "bearish", 2) is None


def test_barrier_hit_after_is_none_when_window_runs_off_the_data():
    df = _cte_frame().iloc[:4]
    assert barrier_hit_after(df, 1, df.iloc[1], "bullish", 2) is None


# ── Corridor-position baseline ────────────────────────────────────────────────

def test_geo_baseline_k0_is_the_direction_x_corridor_bin_hit_rate():
    df = attach_geo_baseline(prepare(_random_walk(2000, seed=11)))
    ev = np.flatnonzero(df["cisd_type"].notna().to_numpy())
    recs = []
    for pos in ev:
        row, ct = df.iloc[pos], df["cisd_type"].iloc[pos]
        rng = row["high"] - row["low"]
        if not rng > 0:
            continue
        clv = (row["close"] - row["low"]) / rng if ct == "bullish" else (row["high"] - row["close"]) / rng
        recs.append((pos, ct, min(int(np.floor(clv * 10)), 9), barrier_hit(df, pos, row, ct)))
    t = pd.DataFrame(recs, columns=["pos", "ct", "bin", "hit"])
    t["expected"] = t.groupby(["ct", "bin"])["hit"].transform("mean")
    np.testing.assert_allclose(df["geo_p_k0"].to_numpy()[t["pos"]], t["expected"].to_numpy())


def test_geo_expected_hits_sum_to_observed_over_the_whole_population():
    # Indirect standardization identity: over the full event population the
    # baseline reproduces the observed hit count, so compute_basic's lift is 0.
    df = attach_geo_baseline(prepare(_random_walk(2000, seed=5)))
    cells = compute_basic(df)["geo"]
    for ct in ("bullish", "bearish"):
        cell = cells[ct]
        assert cell["geo_n"] > 0
        assert cell["expected"] == pytest.approx(cell["geo_runs"])


def test_geo_stats_z_lift_and_p_value():
    stats = bv.geo_stats({"geo_n": 100, "geo_runs": 60, "expected": 50.0, "expected_var": 25.0})
    assert stats["geo_expected_rate"] == pytest.approx(0.5)
    assert stats["geo_lift"] == pytest.approx(0.1)
    assert stats["geo_z"] == pytest.approx(2.0)
    assert stats["geo_p_value"] == pytest.approx(math.erfc(2 / math.sqrt(2)), abs=1e-6)
    assert math.isnan(bv.geo_stats(None)["geo_p_value"])


def test_manifest_rows_carry_geo_and_diagnostic_columns():
    df = prepare(_random_walk(1500, seed=2))
    rows = bv.build_manifest_rows(["basic", "cisd_fvg_interaction", "fvg_hold"], df, df, "15min", "discovery")
    basic = [r for r in rows if r["analysis"] == "basic"]
    assert basic and all(r["geo_n"] > 0 and not r["diagnostic"] for r in basic)
    inter = [r for r in rows if r["analysis"] == "cisd_fvg_interaction"]
    assert inter and all(r["diagnostic"] for r in inter)
    hold = [r for r in rows if r["analysis"] == "fvg_hold"]
    assert hold and all(math.isnan(r["geo_p_value"]) for r in hold)   # not a barrier outcome


def test_apply_geo_bh_correction_excludes_diagnostics_and_labels_direction():
    def row(p, lift, n=200, diagnostic=False):
        return {"geo_p_value": p, "geo_lift": lift, "geo_n": n, "diagnostic": diagnostic}
    rows = [row(1e-6, 0.1), row(1e-6, -0.1), row(0.9, 0.01), row(1e-6, 0.2, n=10),
            row(1e-9, 0.3, diagnostic=True), row(math.nan, math.nan, n=0)]
    bv.apply_geo_bh_correction(rows)
    assert [r["geo_verdict"] for r in rows] == [
        "above-baseline", "below-baseline", "not-significant", "below-n", "diagnostic", "no-baseline",
    ]
    assert rows[4]["geo_bh_q_value"] == ""


def test_evaluate_geo_fold():
    assert bv.evaluate_geo_fold(0.05, 100, 0.02, 100, False) == "pass"
    assert bv.evaluate_geo_fold(0.05, 100, -0.02, 100, False) == "fail"
    assert bv.evaluate_geo_fold(0.05, 10, 0.02, 100, False) == "below-n"
    assert bv.evaluate_geo_fold(math.nan, 100, 0.02, 100, False) == "no-baseline"
    assert bv.evaluate_geo_fold(0.05, 100, 0.02, 100, True) == "diagnostic"


def test_determine_geo_verdict():
    assert determine_geo_verdict("above-baseline", 0.05, 0.01, 100) == "confirmed"
    assert determine_geo_verdict("above-baseline", 0.05, -0.01, 100) == "not-confirmed"
    assert determine_geo_verdict("below-baseline", -0.05, -0.01, 10) == "not-confirmed"
    assert determine_geo_verdict("not-significant", 0.05, 0.01, 100) == "not-significant"
    assert determine_geo_verdict(float("nan"), 0.05, 0.01, 100) == "no-baseline"


def test_is_diagnostic():
    assert is_diagnostic("smt_cisd", "w/ SMT & broke")
    assert not is_diagnostic("smt_cisd", "w/ SMT")
    assert is_diagnostic("candle1_followthrough", "against_inwindow")
    assert not is_diagnostic("candle1_followthrough", "against_forward")
    assert is_diagnostic("cisd_fvg_interaction", "mid0_close_through_near_edge_held")


# ── Session midpoint ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("freq, stamps, expected", [
    ("1h", ["08:00", "09:00", "10:00", "15:00", "16:00"],
     ["overnight", "rth_open", "rth", "rth", "overnight"]),
    ("15min", ["09:15", "09:30", "10:15", "10:30", "15:45", "16:00"],
     ["overnight", "rth_open", "rth_open", "rth", "rth", "overnight"]),
])
def test_session_tag_uses_the_bar_midpoint(freq, stamps, expected):
    df = prepare(_random_walk(200, seed=1, freq=freq))
    tags = df["session_tag"]
    got = [tags[tags.index.strftime("%H:%M") == s].iloc[0] for s in stamps]
    assert got == expected


def test_load_1m_accepts_utc_schema_and_pins_the_window(tmp_path):
    ts = pd.to_datetime(["2020-08-30 12:00", "2020-08-31 14:00", "2025-11-21 21:59",
                         "2025-11-22 06:00"], utc=True)
    raw = pd.DataFrame({"datetime_utc": ts, "Open": 1.0, "High": 2.0, "Low": 0.5,
                        "Close": 1.5, "Volume": 10})
    path = tmp_path / "x.parquet"
    raw.to_parquet(path)
    out = cisd_analysis.load_1m(path)
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]
    # 14:00 UTC = 10:00 EDT; 21:59 UTC = 16:59 EST; 2025-11-22 01:00 EST is past DATA_END
    assert list(out.index) == [pd.Timestamp("2020-08-31 10:00"), pd.Timestamp("2025-11-21 16:59")]
