"""Unit tests for the validation harness: slicing, Wilson CI (plan 02-02), and manifest schema (plan 02-02)."""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest
from unittest.mock import patch
import cisd_analysis
from scripts.build_validation import (
    slice_df, wilson_ci, n_gate, build_manifest_rows,
    p_value_vs_half, bh_correct, apply_bh_correction,
    slice_fold, evaluate_fold, walk_forward_verdict,
    build_walkforward_rows,
)
from cisd_analysis import WALK_FORWARD_FOLDS


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


# ── significance + BH correction tests (plan 06-01) ───────────────────────────

def test_p_value_vs_half_at_boundary() -> None:
    """p_value_vs_half(100, 50) must be exactly 1.0 (rate exactly 0.5 -> z=0 -> erfc(0)=1.0)."""
    assert p_value_vs_half(100, 50) == 1.0


def test_p_value_vs_half_known_value() -> None:
    """p_value_vs_half(100, 60) ~= 0.0455 within +/-0.002.

    z = (2*60-100)/sqrt(100) = 2.0; two-sided p = erfc(2/sqrt(2)).
    """
    p = p_value_vs_half(100, 60)
    assert abs(p - 0.0455) <= 0.002, f"p={p:.4f} outside expected band around 0.0455"


def test_p_value_vs_half_zero_n() -> None:
    """p_value_vs_half(0, 0) must be 1.0 (n==0 guard: no evidence against the null)."""
    assert p_value_vs_half(0, 0) == 1.0


def test_p_value_vs_half_in_unit_interval() -> None:
    """p_value_vs_half must return a float in [0.0, 1.0] for a range of (n, k) cases."""
    cases = [(1, 1), (50, 25), (200, 140), (500, 250)]
    for n, k in cases:
        p = p_value_vs_half(n, k)
        assert 0.0 <= p <= 1.0, f"p={p} out of [0,1] for n={n}, k={k}"


def test_bh_correct_known_value() -> None:
    """bh_correct at m=5, fdr=0.05 must flag exactly the two smallest p-values.

    Largest rank i with p_(i) <= (i/5)*0.05 is i=2 (0.008 <= 0.02), so exactly
    the two smallest p-values (0.001, 0.008) are significant.
    """
    pvalues = [0.001, 0.008, 0.039, 0.041, 0.9]
    results = bh_correct(pvalues, fdr=0.05)
    significant = [r["bh_significant"] for r in results]
    assert significant == [True, True, False, False, False], (
        f"expected only the two smallest p-values significant, got {significant}"
    )
    assert sum(1 for r in results if r["bh_significant"]) == 2


def test_bh_correct_preserves_input_order() -> None:
    """bh_correct must return records in original input order, not sorted order."""
    pvalues = [0.9, 0.001, 0.041, 0.008, 0.039]  # deliberately unsorted
    results = bh_correct(pvalues, fdr=0.05)
    assert len(results) == len(pvalues)
    # The smallest p-value (0.001, index 1) must have bh_rank 1.
    assert results[1]["bh_rank"] == 1
    # The largest p-value (0.9, index 0) must have bh_rank 5.
    assert results[0]["bh_rank"] == 5


def test_bh_correct_q_values_monotone() -> None:
    """bh_correct q-values must be monotone non-decreasing along ascending p_value,
    and every bh_q_value must be clamped to <= 1.0.
    """
    pvalues = [0.001, 0.008, 0.039, 0.041, 0.9]
    results = bh_correct(pvalues, fdr=0.05)
    ordered = sorted(zip(pvalues, results), key=lambda pair: pair[0])
    q_values = [r["bh_q_value"] for _, r in ordered]
    for prev_q, next_q in zip(q_values, q_values[1:]):
        assert prev_q <= next_q, f"q-values not monotone: {q_values}"
    for r in results:
        assert r["bh_q_value"] <= 1.0, f"bh_q_value {r['bh_q_value']} exceeds 1.0"


def test_bh_correct_empty_input() -> None:
    """bh_correct([]) must return [] (empty family guard)."""
    assert bh_correct([]) == []


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


# ── p_value wiring + apply_bh_correction tests (plan 06-01) ───────────────────

def test_build_manifest_rows_emits_p_value() -> None:
    """Every row emitted by build_manifest_rows must carry a p_value key (D-01)."""
    dummy = pd.DataFrame()
    mock_compute = lambda df: _basic_compute_return()  # noqa: E731
    fake_analyses = {"basic": ("Basic", mock_compute, None)}

    with patch("scripts.build_validation.ANALYSES", fake_analyses):
        rows = build_manifest_rows(["basic"], dummy, dummy, "1H", "discovery")

    assert len(rows) >= 1, "Expected at least one manifest row"
    for row in rows:
        assert "p_value" in row, f"Row missing p_value key: {row}"
        assert 0.0 <= row["p_value"] <= 1.0


def test_build_manifest_rows_schema_still_subset_after_p_value() -> None:
    """The pre-existing REQUIRED_COLS schema must remain a subset of every row
    even after the additive p_value column is introduced (additive-only lock).
    """
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

    assert len(rows) >= 1
    for row in rows:
        missing = REQUIRED_COLS - row.keys()
        assert not missing, f"Row missing pre-existing columns: {missing}"


def _manifest_row(n: int, k: int, p_value: float, min_n_pass: bool) -> dict:
    """Build a minimal manifest-shaped dict for apply_bh_correction tests."""
    return {
        "analysis": "basic", "timeframe": "1H", "instrument": "NQ",
        "direction": "bullish", "bucket": "all",
        "rate": (k / n) if n else 0.0, "n": n, "successes": k,
        "ci_low": 0.0, "ci_high": 1.0, "ci_method": "wilson",
        "min_n_pass": min_n_pass, "slice": "discovery",
        "p_value": p_value,
    }


def test_apply_bh_correction_corrected_pass_requires_both_gates() -> None:
    """apply_bh_correction must set corrected_pass True only when a row is
    BOTH min_n_pass AND bh_significant; a below-n row must be corrected_pass
    False even with a tiny raw p_value. Pre-existing keys must be preserved.
    """
    rows = [
        _manifest_row(n=200, k=140, p_value=0.001, min_n_pass=True),   # eligible, high-signal
        _manifest_row(n=200, k=105, p_value=0.617, min_n_pass=True),   # eligible, weak signal
        _manifest_row(n=10,  k=9,   p_value=0.0002, min_n_pass=False), # below-n despite tiny p
    ]
    original_keys = [set(row.keys()) for row in rows]

    apply_bh_correction(rows)

    assert rows[0]["bh_significant"] is True
    assert rows[0]["corrected_pass"] is True

    assert rows[2]["corrected_pass"] is False, (
        "below-n row must not pass correction even with a tiny raw p_value"
    )

    for row, keys_before in zip(rows, original_keys):
        missing = keys_before - row.keys()
        assert not missing, f"apply_bh_correction removed pre-existing keys: {missing}"


def test_apply_bh_correction_excludes_zero_n_rows_from_family() -> None:
    """Rows with n < 1 are outside the BH family and get default non-significant flags."""
    rows = [
        _manifest_row(n=200, k=140, p_value=0.001, min_n_pass=True),
        _manifest_row(n=0,   k=0,   p_value=1.0,   min_n_pass=False),
    ]

    apply_bh_correction(rows)

    assert rows[1]["bh_rank"] == ""
    assert rows[1]["bh_q_value"] == ""
    assert rows[1]["bh_significant"] is False
    assert rows[1]["corrected_pass"] is False


# ── walk-forward fold slicing tests (plan 06-02) ──────────────────────────────

def test_walk_forward_folds_frozen_and_before_oos() -> None:
    """WALK_FORWARD_FOLDS must be a strictly-increasing 4-tuple, every entry
    strictly earlier than OOS_START (D-06)."""
    assert len(WALK_FORWARD_FOLDS) == 4
    assert list(WALK_FORWARD_FOLDS) == sorted(WALK_FORWARD_FOLDS), (
        f"WALK_FORWARD_FOLDS not strictly increasing: {WALK_FORWARD_FOLDS}"
    )
    oos_boundary = pd.Timestamp(cisd_analysis.OOS_START)
    for d in WALK_FORWARD_FOLDS:
        assert pd.Timestamp(d) < oos_boundary, f"fold boundary {d} is not before OOS_START"


def test_slice_fold_partition_no_overlap() -> None:
    """train and test slices from slice_fold must not share any bar."""
    oos_boundary = pd.Timestamp(cisd_analysis.OOS_START)
    start = oos_boundary - pd.Timedelta(days=1200)
    idx = pd.date_range(start=start, periods=1100, freq="D")
    df = pd.DataFrame({"close": np.ones(len(idx))}, index=idx)

    b1, b2 = WALK_FORWARD_FOLDS[0], WALK_FORWARD_FOLDS[1]
    train, test = slice_fold(df, train_end=b1, test_end=b2)

    assert train.index.intersection(test.index).empty
    assert (train.index < pd.Timestamp(b1)).all()
    assert (test.index >= pd.Timestamp(b1)).all()
    assert (test.index < pd.Timestamp(b2)).all()


def test_slice_fold_clamps_to_discovery_even_if_test_end_after_oos() -> None:
    """slice_fold must never return a bar >= OOS_START, even when test_end is
    passed as a date after OOS_START (D-04 clamp via slice_df(df, oos=False))."""
    oos_boundary = pd.Timestamp(cisd_analysis.OOS_START)
    start = oos_boundary - pd.Timedelta(days=1500)
    idx = pd.date_range(start=start, periods=2000, freq="D")  # spans well past OOS_START
    df = pd.DataFrame({"close": np.ones(len(idx))}, index=idx)

    b4 = WALK_FORWARD_FOLDS[-1]
    after_oos = (oos_boundary + pd.Timedelta(days=100)).strftime("%Y-%m-%d")
    train, test = slice_fold(df, train_end=b4, test_end=after_oos)

    assert (train.index < oos_boundary).all()
    assert (test.index < oos_boundary).all(), "test slice leaked bars from the sacred OOS region"


def test_slice_fold_anchored_superset() -> None:
    """Expanding/anchored property (D-05): for boundaries b1 < b2, the train
    slice for train_end=b2 must be a superset of the train slice for
    train_end=b1."""
    oos_boundary = pd.Timestamp(cisd_analysis.OOS_START)
    start = oos_boundary - pd.Timedelta(days=1200)
    idx = pd.date_range(start=start, periods=1100, freq="D")
    df = pd.DataFrame({"close": np.ones(len(idx))}, index=idx)

    b1, b2 = WALK_FORWARD_FOLDS[0], WALK_FORWARD_FOLDS[1]
    train_b1, _ = slice_fold(df, train_end=b1, test_end=b2)
    train_b2, _ = slice_fold(df, train_end=b2, test_end=WALK_FORWARD_FOLDS[2])

    assert set(train_b1.index).issubset(set(train_b2.index))
    assert len(train_b2) >= len(train_b1)


def test_slice_fold_returns_copies() -> None:
    """Both returned frames must be copies — mutating one must not alter df."""
    oos_boundary = pd.Timestamp(cisd_analysis.OOS_START)
    start = oos_boundary - pd.Timedelta(days=1200)
    idx = pd.date_range(start=start, periods=1100, freq="D")
    df = pd.DataFrame({"close": np.ones(len(idx))}, index=idx)

    b1, b2 = WALK_FORWARD_FOLDS[0], WALK_FORWARD_FOLDS[1]
    train, test = slice_fold(df, train_end=b1, test_end=b2)

    assert train["close"].values is not df["close"].values
    assert test["close"].values is not df["close"].values


# ── evaluate_fold + walk_forward_verdict tests (plan 06-02) ───────────────────

def test_evaluate_fold_pass_same_side() -> None:
    """evaluate_fold must be 'pass' when both n's clear MIN_N and train/test
    rates land on the same non-boundary side of 0.5."""
    assert evaluate_fold(0.62, 120, 0.58, 80) == "pass"


def test_evaluate_fold_fail_opposite_side() -> None:
    """evaluate_fold must be 'fail' when the test rate is on the opposite
    side of 0.5 from the train rate."""
    assert evaluate_fold(0.62, 120, 0.45, 80) == "fail"


def test_evaluate_fold_below_n_test() -> None:
    """evaluate_fold must be 'below-n' when test_n < MIN_N, even with a
    same-side train/test rate."""
    assert evaluate_fold(0.62, 120, 0.58, 40) == "below-n"


def test_evaluate_fold_below_n_train() -> None:
    """evaluate_fold must be 'below-n' when train_n < MIN_N (insufficient
    train evidence to make a directional prediction)."""
    assert evaluate_fold(0.62, 40, 0.58, 80) == "below-n"


def test_evaluate_fold_train_rate_exact_half_fails() -> None:
    """A train rate of exactly 0.5 makes no directional prediction, so the
    fold cannot pass even if both n's clear MIN_N."""
    assert evaluate_fold(0.50, 120, 0.58, 80) == "fail"


def test_walk_forward_verdict_majority_pass() -> None:
    """3/4 (75%) passing folds is a majority -> wf-robust."""
    assert walk_forward_verdict(["pass", "pass", "pass", "fail"]) == "wf-robust"


def test_walk_forward_verdict_exact_half_is_fragile() -> None:
    """2/4 (exactly 50%) is NOT a majority -> wf-fragile (D-07 boundary)."""
    assert walk_forward_verdict(["pass", "pass", "fail", "fail"]) == "wf-fragile"


def test_walk_forward_verdict_below_n_counts_in_denominator() -> None:
    """3/5 (60%) passing, with below-n folds counted in the denominator, is
    still a majority -> wf-robust."""
    assert walk_forward_verdict(["pass", "pass", "pass", "below-n", "fail"]) == "wf-robust"


def test_walk_forward_verdict_below_n_folds_can_tip_to_fragile() -> None:
    """2/4 (exactly 50%) with below-n folds counted in the denominator is
    NOT a majority -> wf-fragile."""
    assert walk_forward_verdict(["pass", "pass", "below-n", "below-n"]) == "wf-fragile"


def test_walk_forward_verdict_no_folds() -> None:
    """An empty fold list must return 'no-folds' (empty guard)."""
    assert walk_forward_verdict([]) == "no-folds"


# ── build_walkforward_rows tests (plan 06-02, Task 3) ─────────────────────────

def _synthetic_discovery_frame() -> pd.DataFrame:
    """A synthetic daily frame spanning well before WALK_FORWARD_FOLDS[0] up
    through OOS_START - 1 day, so every one of the 4 folds' train and test
    windows contains bars."""
    oos_boundary = pd.Timestamp(cisd_analysis.OOS_START)
    start = oos_boundary - pd.Timedelta(days=1600)
    idx = pd.date_range(start=start, periods=1600, freq="D")
    return pd.DataFrame({"close": np.ones(len(idx))}, index=idx)


def test_build_walkforward_rows_schema_and_verdicts() -> None:
    """build_walkforward_rows must emit one row per (bucket x fold) with
    fold_index/train_end/test_end/fold_verdict columns, plus a per-bucket
    wf_verdict (D-07) that is identical across every fold row of that bucket."""
    df_nq = _synthetic_discovery_frame()
    df_es = df_nq.copy()

    mock_compute = lambda df: _basic_compute_return()  # noqa: E731
    fake_analyses = {"basic": ("Basic", mock_compute, None)}

    with patch("scripts.build_validation.ANALYSES", fake_analyses):
        rows = build_walkforward_rows(["basic"], df_nq, df_es, "Daily")

    assert len(rows) > 0, "Expected at least one walk-forward row"
    REQUIRED_COLS = {
        "analysis", "timeframe", "instrument", "direction", "bucket",
        "fold_index", "train_end", "test_end",
        "train_rate", "train_n", "test_rate", "test_n",
        "fold_verdict", "wf_verdict",
    }
    for row in rows:
        missing = REQUIRED_COLS - row.keys()
        assert not missing, f"Row missing columns: {missing}"

    fold_indexes = {row["fold_index"] for row in rows}
    assert fold_indexes == {1, 2, 3, 4}, f"Expected folds 1-4, got {fold_indexes}"

    # Every bucket's fold rows must share one consistent aggregate wf_verdict.
    by_bucket: dict[tuple, set] = {}
    for row in rows:
        key = (row["analysis"], row["timeframe"], row["instrument"], row["direction"], row["bucket"])
        by_bucket.setdefault(key, set()).add(row["wf_verdict"])
    for key, verdicts in by_bucket.items():
        assert len(verdicts) == 1, f"Bucket {key} has inconsistent wf_verdict across folds: {verdicts}"


def test_build_walkforward_rows_never_writes_csv() -> None:
    """build_walkforward_rows is a pure in-memory aggregation — it must never
    perform a CSV write itself (only main()'s --walk-forward branch writes
    output/validation_manifest_walkforward.csv), so the discovery/OOS
    manifests are never touched by the walk-forward code path (D-04)."""
    df_nq = _synthetic_discovery_frame()
    df_es = df_nq.copy()

    mock_compute = lambda df: _basic_compute_return()  # noqa: E731
    fake_analyses = {"basic": ("Basic", mock_compute, None)}

    with patch("scripts.build_validation.ANALYSES", fake_analyses), \
         patch.object(pd.DataFrame, "to_csv", side_effect=AssertionError("must not write CSV")):
        rows = build_walkforward_rows(["basic"], df_nq, df_es, "Daily")

    assert len(rows) > 0
