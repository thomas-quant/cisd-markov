"""Unit tests for the validation harness: slicing, Wilson CI (plan 02-02), and manifest schema (plan 02-02)."""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest
import cisd_analysis
from scripts.build_validation import slice_df


def test_slice_df_partition() -> None:
    """Discovery + OOS slices must partition the full frame without gaps or overlap."""
    boundary = pd.Timestamp(cisd_analysis.OOS_START)
    start = boundary - pd.Timedelta(days=1000)
    idx = pd.date_range(start=start, periods=2000, freq="D")
    df = pd.DataFrame({"close": np.ones(len(idx))}, index=idx)

    disc = slice_df(df, oos=False)
    oos = slice_df(df, oos=True)

    assert len(disc) + len(oos) == 2000
    assert (disc.index < boundary).all()
    assert (oos.index >= boundary).all()


def test_slice_df_no_overlap() -> None:
    """No single bar may appear in both the discovery and OOS slices."""
    boundary = pd.Timestamp(cisd_analysis.OOS_START)
    start = boundary - pd.Timedelta(days=1000)
    idx = pd.date_range(start=start, periods=2000, freq="D")
    df = pd.DataFrame({"close": np.ones(len(idx))}, index=idx)

    disc = slice_df(df, oos=False)
    oos = slice_df(df, oos=True)

    assert disc.index.intersection(oos.index).empty


def test_slice_df_all_discovery() -> None:
    """When the entire frame is before OOS_START, the OOS slice must be empty."""
    boundary = pd.Timestamp(cisd_analysis.OOS_START)
    # Build a frame entirely before the boundary
    idx = pd.date_range(end=boundary - pd.Timedelta(days=1), periods=100, freq="D")
    df = pd.DataFrame({"close": np.ones(len(idx))}, index=idx)

    assert len(slice_df(df, oos=False)) == len(df)
    assert len(slice_df(df, oos=True)) == 0


def test_slice_df_all_oos() -> None:
    """When the entire frame is on or after OOS_START, the discovery slice must be empty."""
    boundary = pd.Timestamp(cisd_analysis.OOS_START)
    # Build a frame entirely from the boundary onwards
    idx = pd.date_range(start=boundary, periods=100, freq="D")
    df = pd.DataFrame({"close": np.ones(len(idx))}, index=idx)

    assert len(slice_df(df, oos=False)) == 0
    assert len(slice_df(df, oos=True)) == len(df)


def test_slice_df_returns_copy() -> None:
    """slice_df must return a copy so downstream writes cannot corrupt the source frame."""
    boundary = pd.Timestamp(cisd_analysis.OOS_START)
    start = boundary - pd.Timedelta(days=200)
    idx = pd.date_range(start=start, periods=400, freq="D")
    df = pd.DataFrame({"close": np.ones(len(idx))}, index=idx)

    sliced = slice_df(df, oos=False)
    # Verify the underlying values array is not the same object as the original
    assert sliced["close"].values is not df["close"].values


def test_oos_start_and_constants() -> None:
    """OOS_START must be a day-boundary date string; MIN_N and CI_LEVEL must have correct values."""
    assert isinstance(cisd_analysis.OOS_START, str)
    ts = pd.Timestamp(cisd_analysis.OOS_START)
    assert ts.hour == 0, f"OOS_START must be midnight-aligned, got hour={ts.hour}"
    assert ts.minute == 0
    assert cisd_analysis.MIN_N == 50
    assert cisd_analysis.CI_LEVEL == 0.95
