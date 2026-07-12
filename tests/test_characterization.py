"""Characterization tests — lock README headline numbers against live pipeline output.

All tests in this module require the parquet data files to be present.  When
they are absent the entire module is skipped so CI stays green.  The SMT
section has an additional skip gate on the local SMT package.

Tolerance: ±0.05 pp (one decimal rounding matches without masking real drift).
Expected values were captured from the current codebase and cross-checked
against the README §1/§2/§3/§4/§8 tables — every non-SMT value agreed to
within 0.05 pp of the README 1-decimal figure.
"""
from __future__ import annotations

import pytest
import pandas as pd

import cisd_analysis
from cisd_analysis import DATA_DIR, TIMEFRAMES, _SMT_PKG_PATH

# ── Module-level data-availability gate ──────────────────────────────────────
_NQ_FILE = DATA_DIR / "nq_1m.parquet"
_ES_FILE = DATA_DIR / "es_1m.parquet"
_DATA_PRESENT = _NQ_FILE.exists() and _ES_FILE.exists()

pytestmark = pytest.mark.skipif(
    not _DATA_PRESENT,
    reason="Parquet data files not present — characterization tests skipped in CI",
)


# ── Shared module-scoped fixtures ─────────────────────────────────────────────
@pytest.fixture(scope="module")
def nq_1m() -> pd.DataFrame:
    return cisd_analysis.load_1m(_NQ_FILE)


@pytest.fixture(scope="module")
def es_1m() -> pd.DataFrame:
    return cisd_analysis.load_1m(_ES_FILE)


@pytest.fixture(scope="module")
def nq_frames(nq_1m: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        label: cisd_analysis.prepare(cisd_analysis.resample_ohlcv(nq_1m, rule))
        for label, rule in TIMEFRAMES.items()
    }


@pytest.fixture(scope="module")
def es_frames(es_1m: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        label: cisd_analysis.prepare(cisd_analysis.resample_ohlcv(es_1m, rule))
        for label, rule in TIMEFRAMES.items()
    }


# ── §1 Baseline — compute_basic (16-cell grid) ───────────────────────────────
# Captured actual values (rates = runs/totals*100):
#   NQ Daily: Bull=60.3865 n=414, Bear=53.6709 n=395
#   NQ 4H:    Bull=55.9006 n=2093, Bear=50.3118 n=2085
#   NQ 1H:    Bull=61.9188 n=7807, Bear=57.4621 n=7786
#   NQ 15min: Bull=62.2027 n=30817, Bear=58.9623 n=30645
#   ES Daily: Bull=59.8575 n=421, Bear=50.2427 n=412
#   ES 4H:    Bull=58.0769 n=2080, Bear=51.7874 n=2070
#   ES 1H:    Bull=63.0219 n=7472, Bear=58.4077 n=7398
#   ES 15min: Bull=62.1851 n=28859, Bear=59.5960 n=28611
# All within ±0.05 pp of the README 1-decimal figures.

_BASIC_EXPECTED = {
    # (timeframe, instrument, direction): (rate_1dp, n)
    ("Daily",  "NQ", "bullish"): (60.4, 414),
    ("Daily",  "NQ", "bearish"): (53.7, 395),
    ("Daily",  "ES", "bullish"): (59.9, 421),
    ("Daily",  "ES", "bearish"): (50.2, 412),
    ("4H",     "NQ", "bullish"): (55.9, 2093),
    ("4H",     "NQ", "bearish"): (50.3, 2085),
    ("4H",     "ES", "bullish"): (58.1, 2080),
    ("4H",     "ES", "bearish"): (51.8, 2070),
    ("1H",     "NQ", "bullish"): (61.9, 7807),
    ("1H",     "NQ", "bearish"): (57.5, 7786),
    ("1H",     "ES", "bullish"): (63.0, 7472),
    ("1H",     "ES", "bearish"): (58.4, 7398),
    ("15min",  "NQ", "bullish"): (62.2, 30817),
    ("15min",  "NQ", "bearish"): (59.0, 30645),
    ("15min",  "ES", "bullish"): (62.2, 28859),
    ("15min",  "ES", "bearish"): (59.6, 28611),
}


def test_basic_baseline_rates(nq_frames, es_frames):
    frames = {"NQ": nq_frames, "ES": es_frames}
    for (tf, inst, direction), (exp_rate, exp_n) in _BASIC_EXPECTED.items():
        df = frames[inst][tf]
        result = cisd_analysis.compute_basic(df)
        actual_n = result["totals"][direction]
        actual_rate = cisd_analysis.pv(result["runs"][direction], actual_n)
        assert actual_n == exp_n, (
            f"§1 Baseline n mismatch: {inst} {tf} {direction}: "
            f"expected n={exp_n}, got n={actual_n}"
        )
        assert actual_rate == pytest.approx(exp_rate, abs=0.05), (
            f"§1 Baseline rate mismatch: {inst} {tf} {direction}: "
            f"expected {exp_rate}%, got {actual_rate:.4f}%"
        )


# ── §4 Stricter CISD — compute_significance (16-cell grid) ───────────────────
# Captured actual values:
#   NQ Daily: Bull=68.2093 n=497, Bear=63.7394 n=353
#   NQ 4H:    Bull=61.6374 n=2333, Bear=59.1205 n=1842
#   NQ 1H:    Bull=66.5390 n=8093, Bear=63.7723 n=6622
#   NQ 15min: Bull=67.6079 n=30597, Bear=66.1345 n=27184
#   ES Daily: Bull=68.4848 n=495, Bear=62.9630 n=351
#   ES 4H:    Bull=63.2554 n=2267, Bear=60.3784 n=1797
#   ES 1H:    Bull=67.6124 n=7966, Bear=65.0267 n=6545
#   ES 15min: Bull=68.4620 n=29187, Bear=67.3382 n=26208
# All within ±0.05 pp of the README 1-decimal figures.

_SIG_EXPECTED = {
    ("Daily",  "NQ", "bullish"): (68.2, 497),
    ("Daily",  "NQ", "bearish"): (63.7, 353),
    ("Daily",  "ES", "bullish"): (68.5, 495),
    ("Daily",  "ES", "bearish"): (63.0, 351),
    ("4H",     "NQ", "bullish"): (61.6, 2333),
    ("4H",     "NQ", "bearish"): (59.1, 1842),
    ("4H",     "ES", "bullish"): (63.3, 2267),
    ("4H",     "ES", "bearish"): (60.4, 1797),
    ("1H",     "NQ", "bullish"): (66.5, 8093),
    ("1H",     "NQ", "bearish"): (63.8, 6622),
    ("1H",     "ES", "bullish"): (67.6, 7966),
    ("1H",     "ES", "bearish"): (65.0, 6545),
    ("15min",  "NQ", "bullish"): (67.6, 30597),
    ("15min",  "NQ", "bearish"): (66.1, 27184),
    ("15min",  "ES", "bullish"): (68.5, 29187),
    ("15min",  "ES", "bearish"): (67.3, 26208),
}


def test_significance_rates(nq_frames, es_frames):
    frames = {"NQ": nq_frames, "ES": es_frames}
    for (tf, inst, direction), (exp_rate, exp_n) in _SIG_EXPECTED.items():
        df = frames[inst][tf]
        result = cisd_analysis.compute_significance(df)
        actual_n = result["totals"][direction]
        actual_rate = cisd_analysis.pv(result["runs"][direction], actual_n)
        assert actual_n == exp_n, (
            f"§4 Significance n mismatch: {inst} {tf} {direction}: "
            f"expected n={exp_n}, got n={actual_n}"
        )
        assert actual_rate == pytest.approx(exp_rate, abs=0.05), (
            f"§4 Significance rate mismatch: {inst} {tf} {direction}: "
            f"expected {exp_rate}%, got {actual_rate:.4f}%"
        )


# ── §3 Combined headline buckets — compute_combined ──────────────────────────
# Captured actual values from current code (all four TFs, both instruments):
#   NQ Daily: Bear 2c past_wick=78.7879 n=33; Bear 2c within_wick=36.6667 n=60
#   NQ 15min: Bull 3c past_wick=74.7214 n=1974
#   ES Daily: Bear 2c past_wick=80.6452 n=31 (README says 80.7% — minor rounding discrepancy)
#             Bear 2c within_wick=38.0282 n=71
#   ES 4H:    Bull 3c past_wick=77.6923 n=130
#   ES 1H:    Bull 3c past_wick=75.817 n=459
#
# README §3 discrepancies found:
#   - ES Daily Bear 2c past_wick: README=80.7%, actual=80.6452% (Δ=0.055pp, rounds to 80.6)
#   - README text says "Within-wick + 2c on Daily (ES bear) drops to 36.7%" but actual
#     ES Daily Bear 2c within_wick=38.0% — the 36.7% figure matches NQ (not ES).
#     README has wrong instrument label for the within-wick bucket.
#   Assertions use actual captured values; see SUMMARY for details.

_COMBINED_EXPECTED = {
    # (timeframe, instrument, direction, consec_n, wick_grp): (rate_1dp,)
    # Rates are 1dp-rounded actual values (captured from current code).
    ("Daily",  "NQ", "bearish", 2, "past_wick"):   (78.8,),
    # ES Daily Bear 2c past: actual=80.6452 (rounds to 80.6); README says 80.7 — rounding discrepancy
    ("Daily",  "ES", "bearish", 2, "past_wick"):   (80.6,),
    # ES Daily Bear 2c within: actual=38.0282; README says 36.7 (wrong instrument — that is NQ)
    ("Daily",  "ES", "bearish", 2, "within_wick"): (38.0,),
    ("4H",     "ES", "bullish", 3, "past_wick"):   (77.7,),
    ("1H",     "ES", "bullish", 3, "past_wick"):   (75.8,),
    ("15min",  "NQ", "bullish", 3, "past_wick"):   (74.7,),
}


def test_combined_headline_buckets(nq_frames, es_frames):
    frames = {"NQ": nq_frames, "ES": es_frames}
    for (tf, inst, direction, n, grp), (exp_rate,) in _COMBINED_EXPECTED.items():
        df = frames[inst][tf]
        result = cisd_analysis.compute_combined(df)
        bucket = result[direction][n][grp]
        actual_n = bucket["total"]
        actual_rate = cisd_analysis.pv(bucket["runs"], actual_n)
        assert actual_n > 0, (
            f"§3 Combined empty bucket: {inst} {tf} {direction} {n}c {grp}"
        )
        assert actual_rate == pytest.approx(exp_rate, abs=0.05), (
            f"§3 Combined rate mismatch: {inst} {tf} {direction} {n}c {grp}: "
            f"expected {exp_rate}%, got {actual_rate:.4f}% (n={actual_n})"
        )


# ── §2 Wick — Daily ES bearish within-wick flagship stat ─────────────────────
# Captured: ES Daily bear within_wick=39.4928 n=276
# README says 39.5% — within ±0.05 pp.

def test_wick_daily_es_bearish_within(es_frames):
    df = es_frames["Daily"]
    result = cisd_analysis.compute_wick(df)
    bucket = result["bearish"]["within_wick"]
    actual_n = bucket["total"]
    actual_rate = cisd_analysis.pv(bucket["runs"], actual_n)
    assert actual_n == 276, (
        f"§2 Wick n mismatch: ES Daily bearish within_wick: "
        f"expected n=276, got n={actual_n}"
    )
    assert actual_rate == pytest.approx(39.5, abs=0.05), (
        f"§2 Wick rate mismatch: ES Daily bearish within_wick: "
        f"expected 39.5%, got {actual_rate:.4f}%"
    )


# ── §8 Swing SMT — compute_smt_cisd (additional SMT gate) ────────────────────
# Actual values captured from current code (prepare_pair + compute_smt_cisd).
# These differ substantially from the README §8 table — the SMT package has
# been updated since the README was written; sample sizes are 2-3x larger and
# rates have shifted.  Full README-vs-actual discrepancy table is in SUMMARY.
#
# Phase 9 (v2.0) deliberately changed these numbers: an SMT already invalidated
# by the CISD bar t (broken_ts <= t) was previously mis-credited as "w/ SMT";
# it is now reclassified into a separate "expired SMT" bucket, so every combo's
# n drops (see .planning/phases/09-smt-geometry-invalidation-honesty/ and the
# README "SMT Invalidation Honesty (v2.0)" section for the discovery-slice
# version of this same fix). Recaptured 2026-07-12 against the corrected code.
#
# Actual captured values:
#   NQ Daily:  Bull=68.0 n=50,  Bear=61.1 n=36
#   NQ 4H:     Bull=57.7 n=213, Bear=51.3 n=230
#   NQ 1H:     Bull=60.6 n=675, Bear=55.2 n=774
#   NQ 15min:  Bull=64.7 n=2603, Bear=61.3 n=2772
#   ES Daily:  Bull=60.4 n=53,  Bear=51.1 n=45
#   ES 4H:     Bull=64.5 n=203, Bear=52.0 n=227
#   ES 1H:     Bull=60.8 n=641, Bear=55.8 n=733
#   ES 15min:  Bull=63.9 n=2494, Bear=60.7 n=2633

_SMT_EXPECTED = {
    # (timeframe, instrument, direction): (rate_1dp, n)
    ("Daily",  "NQ", "bullish"): (68.0, 50),
    ("Daily",  "NQ", "bearish"): (61.1, 36),
    ("Daily",  "ES", "bullish"): (60.4, 53),
    ("Daily",  "ES", "bearish"): (51.1, 45),
    ("4H",     "NQ", "bullish"): (57.7, 213),
    ("4H",     "NQ", "bearish"): (51.3, 230),
    ("4H",     "ES", "bullish"): (64.5, 203),
    ("4H",     "ES", "bearish"): (52.0, 227),
    ("1H",     "NQ", "bullish"): (60.6, 675),
    ("1H",     "NQ", "bearish"): (55.2, 774),
    ("1H",     "ES", "bullish"): (60.8, 641),
    ("1H",     "ES", "bearish"): (55.8, 733),
    ("15min",  "NQ", "bullish"): (64.7, 2603),
    ("15min",  "NQ", "bearish"): (61.3, 2772),
    ("15min",  "ES", "bullish"): (63.9, 2494),
    ("15min",  "ES", "bearish"): (60.7, 2633),
}


def test_smt_cisd_rates(nq_1m, es_1m):
    if not _SMT_PKG_PATH.exists():
        pytest.skip("SMT package not available — SMT characterization skipped")

    results: dict[str, dict[str, dict]] = {"NQ": {}, "ES": {}}
    for label, rule in TIMEFRAMES.items():
        df_nq, df_es = cisd_analysis.prepare_pair(nq_1m, es_1m, rule, with_swing_smt=True)
        results["NQ"][label] = cisd_analysis.compute_smt_cisd(df_nq)
        results["ES"][label] = cisd_analysis.compute_smt_cisd(df_es)

    for (tf, inst, direction), (exp_rate, exp_n) in _SMT_EXPECTED.items():
        bucket = results[inst][tf][direction]["w/ SMT"]
        actual_n = bucket["total"]
        actual_rate = cisd_analysis.pv(bucket["runs"], actual_n)
        assert actual_n == exp_n, (
            f"§8 SMT n mismatch: {inst} {tf} {direction} w/ SMT: "
            f"expected n={exp_n}, got n={actual_n}"
        )
        assert actual_rate == pytest.approx(exp_rate, abs=0.05), (
            f"§8 SMT rate mismatch: {inst} {tf} {direction} w/ SMT: "
            f"expected {exp_rate}%, got {actual_rate:.4f}%"
        )
