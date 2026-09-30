"""Barrier-trade payoff study: trade scoring, bucket capture, cluster CI."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cisd_analysis import attach_geo_baseline, barrier_hit, compute_wick, prepare
from scripts import build_barrier_payoff as bp
from scripts import build_validation as bv
from test_leakage_and_geo import _random_walk


def test_k0_trade_hit_matches_barrier_hit_and_r_is_bounded():
    df = prepare(_random_walk(1500, seed=7))
    t = bp.event_trades(df, "k0")
    assert len(t) > 200
    for _, row in t.sample(200, random_state=0).iterrows():
        pos = int(row["pos"])
        assert bool(row["hit"]) == barrier_hit(df, pos, df.iloc[pos], df["cisd_type"].iloc[pos])
    assert (t["r"] >= -1).all()
    assert (t.loc[t["hit"], "r"] > 0).all()


def test_capture_buckets_matches_the_validation_cells():
    df = prepare(_random_walk(1500, seed=7))
    members = bp.capture_buckets(df, ["wick", "post_cisd_context"])
    data = compute_wick(df)
    for ct in ("bullish", "bearish"):
        for grp in ("past_wick", "within_wick"):
            ev = members[("wick", ct, grp)]
            assert len(ev) == data[ct][grp]["total"]
            assert {f for _, f in ev} == {"k0"}
    gap = [k for k in members if k[0] == "post_cisd_context" and k[2].startswith("failed_gap")]
    assert gap and all({f for _, f in members[k]} <= {"fwd"} for k in gap)


def test_expected_r_is_the_stratum_mean_so_population_lift_is_zero():
    df = prepare(_random_walk(2000, seed=9))
    t = bp.attach_expected(bp.event_trades(df, "k0"), cost_points=0.5)
    assert (t["r"] - t["exp_r"]).mean() == pytest.approx(0, abs=1e-12)
    assert (t["r_net"] < t["r"]).all()


def test_cluster_mean_ci_widens_with_within_cluster_correlation():
    v = np.r_[np.ones(50), -np.ones(50)]
    _, se_iid, _ = bp.cluster_mean_ci(v, np.arange(100))
    _, se_cl, g = bp.cluster_mean_ci(v, np.r_[np.zeros(50), np.ones(50)].astype(int))
    assert g == 2 and se_cl > se_iid
