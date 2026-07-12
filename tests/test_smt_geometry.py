"""
tests/test_smt_geometry.py — SMT geometry, role, and survived/broke reporting
==============================================================================
Held-out assertions for Phase 09 Plan 02 (`.planning/phases/09-smt-geometry-
invalidation-honesty/09-02-PLAN.md`): the compute layer must (a) extend
`compute_smt_cisd` to the three-way `w/ SMT` / `expired SMT` / `no SMT` split
plus the `w/ SMT & survived` / `w/ SMT & broke` diagnostic sub-buckets without
ever filtering the aggregate `w/ SMT` population (D-03/D-07), (b) add
`compute_smt_role` over the valid `w/ SMT` population only (D-08), and
(c) add `compute_smt_block_size` / `compute_smt_in_block` over the
matched-SMT population only (D-04/D-05/D-05a). Task 3 additionally adds a
manifest-shape smoke test proving the new analyses flow through
`scripts.build_validation.build_manifest_rows`'s generic dispatch.

All fixtures are synthetic (hand-built enriched frames) — no SMT package
or real data required.
"""

import numpy as np
import pandas as pd
import pytest

from cisd_barriers import (
    compute_smt_cisd,
    compute_smt_role,
    compute_smt_block_size,
    compute_smt_in_block,
)


# ── Fixture helper ───────────────────────────────────────────────────────────

def _base_df(
    n,
    cisd_types,
    tags=None,
    roles=None,
    broke=None,
    block_ratio=None,
    in_block=None,
):
    idx = pd.date_range("2026-01-01 09:30", periods=n, freq="15min")
    opens  = [100.0 + i for i in range(n)]
    highs  = [o + 1.0 for o in opens]
    lows   = [o - 1.0 for o in opens]
    closes = [o + 0.3 for o in opens]
    data = {
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "cisd_type": cisd_types,
    }
    if tags is not None:
        data["swing_smt_tag"] = tags
    if roles is not None:
        data["swing_smt_role"] = roles
    if broke is not None:
        data["smt_broke_in_window"] = broke
    if block_ratio is not None:
        data["smt_block_size_atr"] = block_ratio
    if in_block is not None:
        data["cisd_in_smt_block"] = in_block
    return pd.DataFrame(data, index=idx)


# ── compute_smt_cisd: three-way split (D-03) ────────────────────────────────

def test_compute_smt_cisd_three_way_split():
    n = 5
    cisd_types = [None, "bullish", "bullish", "bearish", None]
    tags       = ["no SMT", "w/ SMT", "expired SMT", "no SMT", "no SMT"]
    df = _base_df(n, cisd_types, tags=tags)

    stats = compute_smt_cisd(df)

    assert stats["bullish"]["w/ SMT"]["total"] == 1
    assert stats["bullish"]["expired SMT"]["total"] == 1
    # the expired-SMT row must never also increment w/ SMT or no SMT
    assert stats["bullish"]["no SMT"]["total"] == 0
    assert stats["bearish"]["no SMT"]["total"] == 1


def test_compute_smt_cisd_raises_without_swing_smt_tag():
    df = _base_df(3, [None, "bullish", None])
    with pytest.raises(ValueError, match="swing_smt_tag"):
        compute_smt_cisd(df)


# ── compute_smt_cisd: survived/broke sub-buckets, never filtered (D-07) ────

def test_compute_smt_cisd_survived_broke_never_filters_aggregate():
    n = 7
    cisd_types = [None, "bullish", "bullish", "bullish", "bullish", "bullish", None]
    tags  = ["no SMT", "w/ SMT", "w/ SMT", "w/ SMT", "w/ SMT", "w/ SMT", "no SMT"]
    broke = [False,    True,     True,     False,    False,    False,    False]
    df = _base_df(n, cisd_types, tags=tags, broke=broke)

    stats = compute_smt_cisd(df)

    assert stats["bullish"]["w/ SMT"]["total"] == 5
    assert stats["bullish"]["w/ SMT & broke"]["total"] == 2
    assert stats["bullish"]["w/ SMT & survived"]["total"] == 3
    # D-07: aggregate w/ SMT is NEVER filtered on survival
    assert stats["bullish"]["w/ SMT"]["total"] == (
        stats["bullish"]["w/ SMT & survived"]["total"]
        + stats["bullish"]["w/ SMT & broke"]["total"]
    )


def test_compute_smt_cisd_degrades_without_broke_column():
    n = 3
    cisd_types = [None, "bullish", None]
    tags = ["no SMT", "w/ SMT", "no SMT"]
    df = _base_df(n, cisd_types, tags=tags)  # no smt_broke_in_window column

    stats = compute_smt_cisd(df)

    assert stats["bullish"]["w/ SMT"]["total"] == 1
    assert stats["bullish"]["w/ SMT & survived"]["total"] == 0
    assert stats["bullish"]["w/ SMT & broke"]["total"] == 0


# ── compute_smt_role: valid w/ SMT population only (D-08) ──────────────────

def test_compute_smt_role_counts_only_valid_w_smt_rows():
    n = 6
    cisd_types = [None, "bullish", "bullish", "bullish", "bearish", None]
    tags  = ["no SMT", "w/ SMT", "w/ SMT",          "expired SMT", "no SMT", "no SMT"]
    roles = ["none",   "swept",  "failed_to_sweep", "none",        "none",   "none"]
    df = _base_df(n, cisd_types, tags=tags, roles=roles)

    stats = compute_smt_role(df)

    assert stats["bullish"]["swept"]["total"] == 1
    assert stats["bullish"]["failed_to_sweep"]["total"] == 1
    # expired SMT / no SMT rows are excluded from the role split entirely
    assert stats["bearish"]["swept"]["total"] == 0
    assert stats["bearish"]["failed_to_sweep"]["total"] == 0


def test_compute_smt_role_raises_without_swing_smt_role():
    df = _base_df(3, [None, "bullish", None], tags=["no SMT", "w/ SMT", "no SMT"])
    with pytest.raises(ValueError, match="swing_smt_role"):
        compute_smt_role(df)


def test_compute_smt_role_raises_without_swing_smt_tag():
    df = _base_df(3, [None, "bullish", None], roles=["none", "swept", "none"])
    with pytest.raises(ValueError, match="swing_smt_tag"):
        compute_smt_role(df)


# ── compute_smt_block_size: matched population, NaN-skip (D-04/D-05a) ──────

def test_compute_smt_block_size_buckets_matched_population_only():
    n = 6
    cisd_types = [None, "bullish", "bullish", "bullish", "bullish", None]
    ratios     = [np.nan, 0.3,      0.7,       1.2,       np.nan,    np.nan]
    df = _base_df(n, cisd_types, block_ratio=ratios)

    stats = compute_smt_block_size(df)

    assert stats["bullish"]["<0.5x ATR"]["total"] == 1
    assert stats["bullish"]["0.5x-1x ATR"]["total"] == 1
    assert stats["bullish"]["1x-1.5x ATR"]["total"] == 1
    assert stats["bullish"][">1.5x ATR"]["total"] == 0
    # NaN ratio (unmatched population) must not be bucketed anywhere
    total_bucketed = sum(v["total"] for v in stats["bullish"].values())
    assert total_bucketed == 3


def test_compute_smt_block_size_raises_without_column():
    df = _base_df(3, [None, "bullish", None])
    with pytest.raises(ValueError, match="smt_block_size_atr"):
        compute_smt_block_size(df)


# ── compute_smt_in_block: matched population only (D-05) ───────────────────

def test_compute_smt_in_block_matched_population_only():
    n = 6
    cisd_types = [None, "bullish", "bullish",     "bullish", "bearish", None]
    tags       = ["no SMT", "w/ SMT", "expired SMT", "no SMT",  "w/ SMT",  "no SMT"]
    in_block   = [False,    True,     False,         False,     True,      False]
    df = _base_df(n, cisd_types, tags=tags, in_block=in_block)

    stats = compute_smt_in_block(df)

    assert stats["bullish"]["cisd_in_block"]["total"] == 1
    assert stats["bullish"]["cisd_out_block"]["total"] == 1
    assert stats["bearish"]["cisd_in_block"]["total"] == 1
    assert stats["bearish"]["cisd_out_block"]["total"] == 0
    # the no-SMT row's default-False in_block must NOT count as cisd_out_block
    total_bucketed = sum(
        v["total"] for ct_stats in stats.values() for v in ct_stats.values()
    )
    assert total_bucketed == 3


def test_compute_smt_in_block_raises_without_cisd_in_smt_block():
    df = _base_df(3, [None, "bullish", None], tags=["no SMT", "w/ SMT", "no SMT"])
    with pytest.raises(ValueError, match="cisd_in_smt_block"):
        compute_smt_in_block(df)


def test_compute_smt_in_block_raises_without_swing_smt_tag():
    df = _base_df(3, [None, "bullish", None], in_block=[False, True, False])
    with pytest.raises(ValueError, match="swing_smt_tag"):
        compute_smt_in_block(df)
