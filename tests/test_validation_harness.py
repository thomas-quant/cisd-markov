"""Unit tests for the validation harness: slicing, Wilson CI (plan 02-02), and manifest schema (plan 02-02)."""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest
from unittest.mock import patch
import cisd_analysis
from scripts.build_validation import slice_df, wilson_ci, n_gate, build_manifest_rows


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


# ── Wilson CI and n_gate tests (plan 02-02) ───────────────────────────────────

def test_wilson_ci_known_value() -> None:
    """wilson_ci(100, 60) at 95% CI should match expected Wilson score bounds.

    The Wilson score for p=0.60, n=100, z=1.96 gives approximately [0.502, 0.690].
    Accept a tolerance band of ±0.010 to allow for minor floating-point variation.
    """
    lo, hi = wilson_ci(100, 60)
    assert 0.495 <= lo <= 0.510, f"CI lower bound {lo:.4f} outside expected range [0.495, 0.510]"
    assert 0.685 <= hi <= 0.705, f"CI upper bound {hi:.4f} outside expected range [0.685, 0.705]"


def test_wilson_ci_zero_n() -> None:
    """wilson_ci must return (0.0, 0.0) when n=0 (no observations)."""
    lo, hi = wilson_ci(0, 0)
    assert (lo, hi) == (0.0, 0.0)


def test_wilson_ci_all_successes() -> None:
    """wilson_ci for k==n should return a CI that does not include 0.0 for large n."""
    lo, hi = wilson_ci(100, 100)
    assert lo > 0.0, "Lower bound must be > 0 when all trials are successes (n=100)"
    assert hi <= 1.0, "Upper bound must be <= 1.0"


def test_wilson_ci_small_n() -> None:
    """wilson_ci is defined for n=1 and must return a valid CI in [0, 1]."""
    lo, hi = wilson_ci(1, 1)
    assert 0.0 <= lo <= 1.0
    assert 0.0 <= hi <= 1.0
    assert lo <= hi


def test_wilson_ci_bounds_in_unit_interval() -> None:
    """Wilson CI bounds must always lie in [0, 1] for a range of inputs."""
    cases = [(1, 0), (1, 1), (10, 3), (50, 25), (100, 0), (100, 100), (1000, 500)]
    for n, k in cases:
        lo, hi = wilson_ci(n, k)
        assert 0.0 <= lo <= 1.0, f"Lower {lo} out of [0,1] for n={n}, k={k}"
        assert 0.0 <= hi <= 1.0, f"Upper {hi} out of [0,1] for n={n}, k={k}"
        assert lo <= hi, f"Lower {lo} > upper {hi} for n={n}, k={k}"


def test_n_gate_boundary() -> None:
    """n_gate must return True exactly when n >= MIN_N (boundary: 49=False, 50=True, 51=True)."""
    min_n = cisd_analysis.MIN_N  # 50
    assert n_gate(min_n - 1) is False, f"n={min_n-1} should fail gate"
    assert n_gate(min_n) is True, f"n={min_n} should pass gate"
    assert n_gate(min_n + 1) is True, f"n={min_n+1} should pass gate"
    assert n_gate(0) is False


# ── build_manifest_rows tests (plan 02-02) ────────────────────────────────────

def _make_empty_df() -> pd.DataFrame:
    """Return a minimal enriched DataFrame that compute_basic won't crash on.

    We use a mock instead of real data, so we just need the shape correct.
    """
    return pd.DataFrame()


def _basic_compute_return() -> dict:
    """Minimal compute_basic-shaped return value (flat totals/runs)."""
    return {
        "totals": {"bullish": 60, "bearish": 40},
        "runs":   {"bullish": 36, "bearish": 20},
    }


def test_build_manifest_rows_schema() -> None:
    """build_manifest_rows must return rows with the required 13-column schema."""
    REQUIRED_COLS = {
        "analysis", "timeframe", "instrument", "direction", "bucket",
        "rate", "n", "successes", "ci_low", "ci_high",
        "ci_method", "min_n_pass", "slice",
    }
    dummy = pd.DataFrame()
    mock_compute = lambda df: _basic_compute_return()  # noqa: E731
    fake_analyses = {"basic": ("Basic", mock_compute, None)}

    with patch("scripts.build_validation.ANALYSES", fake_analyses):
        rows = build_manifest_rows(["basic"], dummy, dummy, "1H", "discovery")

    assert len(rows) >= 1, "Expected at least one manifest row"
    for row in rows:
        missing = REQUIRED_COLS - row.keys()
        assert not missing, f"Row missing columns: {missing}"


def test_build_manifest_below_min_n_flagged_not_dropped() -> None:
    """Buckets with n < MIN_N must appear in the manifest with min_n_pass=False.

    Buckets are never silently dropped — below-threshold rows serve as a
    reminder that the edge has insufficient evidence.
    """
    min_n = cisd_analysis.MIN_N  # 50
    small_n = min_n - 1  # definitely below threshold

    def mock_compute(df):  # noqa: ANN001
        return {
            "totals": {"bullish": small_n, "bearish": small_n},
            "runs":   {"bullish": 10,      "bearish": 10},
        }

    fake_analyses = {"basic": ("Basic", mock_compute, None)}
    dummy = pd.DataFrame()

    with patch("scripts.build_validation.ANALYSES", fake_analyses):
        rows = build_manifest_rows(["basic"], dummy, dummy, "Daily", "discovery")

    assert len(rows) >= 1, "Expected at least one manifest row for below-MIN_N bucket"
    flagged = [r for r in rows if r["n"] == small_n]
    assert flagged, f"No row found with n={small_n}; manifest incorrectly dropped it"
    for row in flagged:
        assert row["min_n_pass"] is False, (
            f"Row with n={small_n} should have min_n_pass=False, got {row['min_n_pass']}"
        )
