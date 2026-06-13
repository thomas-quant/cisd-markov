"""Data-free unit tests for the reconciler: determine_verdict + output schema (plan 03-02).

All tests operate on synthetic in-memory data — no parquet reads, no disk I/O.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ── Import the module under test ──────────────────────────────────────────────

import importlib
import scripts.build_reconcile_findings as reconcile_mod
from scripts.build_reconcile_findings import determine_verdict


# ── determine_verdict: eligibility and verdict rules ─────────────────────────

def test_determine_verdict_below_min_n_small() -> None:
    """Test 1: discovery_n=40 (below MIN_N=50) returns 'below-n' regardless of OOS."""
    assert determine_verdict(0.65, 40, 0.62, 30) == "below-n"
    assert determine_verdict(0.65, 40, 0.42, 30) == "below-n"
    assert determine_verdict(0.40, 40, 0.38, 30) == "below-n"


def test_determine_verdict_below_min_n_nan() -> None:
    """Test 2: discovery_n missing/NaN returns 'below-n'."""
    assert determine_verdict(0.65, float("nan"), 0.62, 30) == "below-n"
    assert determine_verdict(0.65, None, 0.62, 30) == "below-n"


def test_determine_verdict_confirmed_both_above_half() -> None:
    """Test 3: discovery_n=60, discovery_rate=0.63, oos_rate=0.58 returns 'confirmed'.

    Both rates > 0.50 so the direction matches.
    """
    result = determine_verdict(0.63, 60, 0.58, 20)
    assert result == "confirmed", f"Expected 'confirmed', got '{result}'"


def test_determine_verdict_not_confirmed_opposite_sides() -> None:
    """Test 4: discovery_n=60, discovery_rate=0.63, oos_rate=0.45 returns 'not-confirmed'.

    Discovery > 0.50 but OOS < 0.50 — direction does not match.
    """
    result = determine_verdict(0.63, 60, 0.45, 20)
    assert result == "not-confirmed", f"Expected 'not-confirmed', got '{result}'"


def test_determine_verdict_confirmed_weakness() -> None:
    """Test 5: discovery_rate=0.38 (sub-0.50 weakness), oos_rate=0.42 returns 'confirmed'.

    Both rates < 0.50 — the weakness persists on OOS.
    """
    result = determine_verdict(0.38, 60, 0.42, 20)
    assert result == "confirmed", f"Expected 'confirmed' for weakness, got '{result}'"


def test_determine_verdict_not_confirmed_no_oos_data() -> None:
    """Test 6: discovery_n=60 (eligible), oos_n=0 returns 'not-confirmed'.

    An eligible bucket with no OOS evidence is 'not-confirmed', never 'below-n'.
    'below-n' is reserved for discovery_n < MIN_N only (D-03).
    """
    result_zero_n = determine_verdict(0.63, 60, float("nan"), 0)
    assert result_zero_n == "not-confirmed", (
        f"oos_n=0 for eligible bucket should be 'not-confirmed', got '{result_zero_n}'"
    )

    result_nan_rate = determine_verdict(0.63, 60, float("nan"), float("nan"))
    assert result_nan_rate == "not-confirmed", (
        f"nan oos_rate for eligible bucket should be 'not-confirmed', got '{result_nan_rate}'"
    )


def test_determine_verdict_valid_tokens_only() -> None:
    """All returned verdict strings must be in the allowed token set."""
    VALID_TOKENS = {"confirmed", "not-confirmed", "below-n"}
    cases = [
        (0.65, 40,          0.62, 30),   # below-n
        (0.65, float("nan"), 0.62, 30),  # below-n
        (0.63, 60,          0.58, 20),   # confirmed
        (0.63, 60,          0.45, 20),   # not-confirmed
        (0.38, 60,          0.42, 20),   # confirmed weakness
        (0.63, 60, float("nan"),  0),    # not-confirmed (no OOS)
    ]
    for args in cases:
        verdict = determine_verdict(*args)
        assert verdict in VALID_TOKENS, (
            f"determine_verdict{args} returned '{verdict}' which is not in {VALID_TOKENS}"
        )


# ── Schema test: reconcile() column contract ──────────────────────────────────

_DISCOVERY_ROWS = [
    {
        "analysis": "basic", "timeframe": "Daily", "instrument": "NQ",
        "direction": "bullish", "bucket": "all",
        "rate": 0.63, "n": 60, "successes": 38,
        "ci_low": 0.50, "ci_high": 0.74,
        "ci_method": "wilson", "min_n_pass": True, "slice": "discovery",
    },
    {
        "analysis": "basic", "timeframe": "Daily", "instrument": "ES",
        "direction": "bullish", "bucket": "all",
        "rate": 0.45, "n": 40, "successes": 18,
        "ci_low": 0.31, "ci_high": 0.60,
        "ci_method": "wilson", "min_n_pass": False, "slice": "discovery",
    },
]

_OOS_ROWS = [
    {
        "analysis": "basic", "timeframe": "Daily", "instrument": "NQ",
        "direction": "bullish", "bucket": "all",
        "rate": 0.58, "n": 20, "successes": 12,
        "ci_low": 0.38, "ci_high": 0.76,
        "ci_method": "wilson", "min_n_pass": False, "slice": "oos",
    },
]


def test_reconcile_output_schema(tmp_path: Path) -> None:
    """Test 7 (schema): reconciling a tiny synthetic pair yields the 12-column D-09 schema.

    Columns in order: analysis, timeframe, instrument, direction, bucket,
    discovery_rate, discovery_n, discovery_ci_low, discovery_ci_high,
    oos_rate, oos_n, verdict.

    All verdict values must be in {confirmed, not-confirmed, below-n}.
    """
    EXPECTED_COLS = [
        "analysis", "timeframe", "instrument", "direction", "bucket",
        "discovery_rate", "discovery_n", "discovery_ci_low", "discovery_ci_high",
        "oos_rate", "oos_n", "verdict",
    ]
    VALID_VERDICTS = {"confirmed", "not-confirmed", "below-n"}

    disc_path = tmp_path / "validation_manifest_discovery.csv"
    oos_path  = tmp_path / "validation_manifest_oos.csv"
    out_path  = tmp_path / "validation_findings.csv"

    pd.DataFrame(_DISCOVERY_ROWS).to_csv(disc_path, index=False)
    pd.DataFrame(_OOS_ROWS).to_csv(oos_path, index=False)

    with (
        patch.object(reconcile_mod, "DISCOVERY_MANIFEST_PATH", disc_path),
        patch.object(reconcile_mod, "OOS_MANIFEST_PATH",       oos_path),
        patch.object(reconcile_mod, "FINDINGS_PATH",           out_path),
    ):
        reconcile_mod.reconcile()

    assert out_path.exists(), "reconcile() must write validation_findings.csv"

    result = pd.read_csv(out_path)

    # Column order must match exactly
    assert list(result.columns) == EXPECTED_COLS, (
        f"Column mismatch.\nExpected: {EXPECTED_COLS}\nGot:      {list(result.columns)}"
    )

    # Every verdict must be a valid token
    bad_verdicts = set(result["verdict"].unique()) - VALID_VERDICTS
    assert not bad_verdicts, f"Invalid verdict values: {bad_verdicts}"

    # Both discovery rows must appear (outer merge — never drop)
    assert len(result) == 2, (
        f"Expected 2 rows (outer merge preserves all discovery rows), got {len(result)}"
    )

    # NQ row: eligible (n=60) with matching OOS rate => confirmed
    nq_row = result[(result["instrument"] == "NQ") & (result["analysis"] == "basic")]
    assert len(nq_row) == 1
    assert nq_row.iloc[0]["verdict"] == "confirmed"

    # ES row: below-n (discovery_n=40) => below-n
    es_row = result[(result["instrument"] == "ES") & (result["analysis"] == "basic")]
    assert len(es_row) == 1
    assert es_row.iloc[0]["verdict"] == "below-n"
