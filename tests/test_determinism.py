"""
Determinism tests for cisd_analysis compute functions.

These tests are data-free — they build synthetic inline DataFrames and confirm
that:
  1. Running the same compute function twice on identical input produces
     identical results (repeat-run determinism).
  2. No non-deterministic calls (datetime.now, time.time, unseeded random)
     exist in the computed code paths.

Both tests run in CI where the parquet data files and the SMT package are
absent.
"""

import re
from pathlib import Path

import pandas as pd

import cisd_analysis


# ── Synthetic data fixture ─────────────────────────────────────────────────────

def _prepared_determinism_frame() -> pd.DataFrame:
    """
    Build a minimal synthetic prepared DataFrame via cisd_analysis.prepare().

    The 25-bar OHLCV sequence is designed so that prepare() produces at least
    one bullish and one bearish CISD (confirmed manually below), giving
    compute_basic and compute_combined non-trivial work to do.

    Bar conventions:
    - high >= max(open, close), low <= min(open, close)
    - direction: close > open → bullish, close < open → bearish
    - bullish CISD at bar t: prev_direction=bearish AND close > prev_close
    - bearish CISD at bar t: prev_direction=bullish AND close < prev_close

    The sequence is fixed; no RNG or wall-clock calls are made.
    """
    # 25 bars at 15-minute resolution starting at a fixed timestamp.
    index = pd.date_range("2026-01-05 09:30", periods=25, freq="15min")

    # Prices chosen so:
    #   Bar 1: prev=bullish(bar 0), close=97 < prev_close=101 → bearish CISD
    #   Bar 2: prev=bearish(bar 1), close=104 > prev_close=97  → bullish CISD
    # Bars 3–24: gentle uptrend providing lookahead and FVG-hold windows.
    opens  = [100, 101, 97,  104, 105, 106, 107, 108, 109, 110,
              111, 112, 113, 114, 115, 116, 117, 118, 119, 120,
              121, 122, 123, 124, 125]
    highs  = [102, 103, 106, 107, 108, 109, 110, 111, 112, 113,
              114, 115, 116, 117, 118, 119, 120, 121, 122, 123,
              124, 125, 126, 127, 128]
    lows   = [98,  96,  95,  103, 104, 105, 106, 107, 108, 109,
              110, 111, 112, 113, 114, 115, 116, 117, 118, 119,
              120, 121, 122, 123, 124]
    closes = [101, 97,  104, 106, 107, 108, 109, 110, 111, 112,
              113, 114, 115, 116, 117, 118, 119, 120, 121, 122,
              123, 124, 125, 126, 127]
    volumes = [1000] * 25

    raw = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows,
         "close": closes, "volume": volumes},
        index=index,
    )
    return cisd_analysis.prepare(raw)


# ── Determinism tests ─────────────────────────────────────────────────────────

def test_compute_basic_is_deterministic():
    """Calling compute_basic twice on identical input returns identical dicts."""
    df = _prepared_determinism_frame()
    result_a = cisd_analysis.compute_basic(df)
    result_b = cisd_analysis.compute_basic(df)
    assert result_a == result_b, (
        f"compute_basic returned different values on repeated calls:\n"
        f"  first:  {result_a}\n"
        f"  second: {result_b}"
    )


def test_compute_combined_is_deterministic():
    """Calling compute_combined twice on identical input returns identical dicts."""
    df = _prepared_determinism_frame()
    result_a = cisd_analysis.compute_combined(df)
    result_b = cisd_analysis.compute_combined(df)
    assert result_a == result_b, (
        f"compute_combined returned different values on repeated calls:\n"
        f"  first:  {result_a}\n"
        f"  second: {result_b}"
    )


def test_prepared_frame_contains_at_least_one_cisd():
    """Guard: the synthetic frame must have CISDs so the determinism tests are non-trivial."""
    df = _prepared_determinism_frame()
    cisd_count = df["cisd_type"].notna().sum()
    assert cisd_count >= 1, (
        f"Synthetic frame produced 0 CISDs — the determinism tests would pass vacuously. "
        f"Fix the fixture data."
    )


# ── Source-code non-determinism guard ─────────────────────────────────────────

# Patterns that would introduce non-determinism in computed paths.
_NON_DETERMINISTIC_PATTERNS: list[tuple[str, str]] = [
    # (human-readable name, regex pattern)
    ("datetime.now()",      r"\bdatetime\.now\s*\("),
    ("datetime.utcnow()",   r"\bdatetime\.utcnow\s*\("),
    ("time.time()",         r"\btime\.time\s*\("),
    ("random. (unseeded)",  r"\brandom\s*\.\s*(?!seed\b)\w+\s*\("),
    ("np.random. (unseeded)", r"\bnp\.random\s*\.\s*(?!seed\b)\w+\s*\("),
]

# Functions that are purely for output/IO and are allowed to use wall-clock time.
# The guard applies to the compute pipeline; chart rendering and main() logging
# may legitimately call time functions.
_COMPUTE_FUNCTION_PREFIXES = ("compute_", "prepare", "barrier_hit", "_annotate",
                               "_classify", "_has_directional", "_compute_three",
                               "_count_consecutive", "_has_directional_sweep")


def _extract_compute_sections(source: str) -> str:
    """
    Extract only the source lines belonging to compute-pipeline functions.

    This is a best-effort heuristic: it selects lines after the
    '# Compute Functions' section header and before the '# Chart Functions'
    header, plus the prepare/barrier_hit helpers before them.  The purpose is
    to avoid false positives from chart rendering or __main__ code that
    legitimately calls datetime.now() for logging.
    """
    lines = source.splitlines()
    in_section = False
    selected: list[str] = []
    for line in lines:
        # Start capturing at the data pipeline / compute sections.
        if "# ── Data Loading" in line or "# ── Compute Functions" in line:
            in_section = True
        # Stop at chart rendering — wall-clock is allowed there.
        if "# ── Chart Functions" in line:
            in_section = False
        if in_section:
            selected.append(line)
    return "\n".join(selected)


def test_no_nondeterministic_calls_in_compute_paths():
    """
    Assert that no unseeded non-deterministic calls exist in the compute pipeline.

    This test FAILS LOUDLY if someone introduces datetime.now(), time.time(),
    or unseeded random calls inside prepare(), compute_*(), barrier_hit(), or
    the annotation helpers.  It does NOT fire on chart functions or main()
    where wall-clock usage is acceptable.
    """
    source_path = Path(cisd_analysis.__file__)
    full_source = source_path.read_text(encoding="utf-8")
    compute_source = _extract_compute_sections(full_source)

    violations: list[str] = []
    for name, pattern in _NON_DETERMINISTIC_PATTERNS:
        if re.search(pattern, compute_source):
            violations.append(f"  - {name}: pattern /{pattern}/ matched")

    assert not violations, (
        "Non-deterministic call(s) found in the compute pipeline:\n"
        + "\n".join(violations)
        + "\nRemove them or move them to chart/IO functions where wall-clock is acceptable."
    )
