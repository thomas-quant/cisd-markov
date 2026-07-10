---
phase: 01-reproducibility-foundation-behavior-lock
plan: 03
subsystem: testing

tags: [pytest, characterization-tests, unit-tests, compute_basic, compute_significance, compute_combined, compute_wick, compute_smt_cisd]

requires:
  - phase: 01-02
    provides: "pyproject.toml conftest.py and CI workflow; working-directory independence for test imports"

provides:
  - "Unit tests for five core compute functions on synthetic fixtures (TEST-02)"
  - "Characterization tests locking README headline numbers against live pipeline output (TEST-01)"
  - "Module-level skip gate so CI stays green when parquet data is absent"
  - "SMT per-function skip gate when local SMT package unavailable"

affects:
  - Phase 02 (validation harness) — these tests are the regression safety net for all later refactors
  - Phase 04 (god-file refactor) — any compute function change will trip these tests

tech-stack:
  added: []
  patterns:
    - "Module-level pytestmark.skipif gate on data availability (used in test_characterization.py)"
    - "module-scoped pytest fixtures for expensive parquet + prepare() loads shared across multiple test functions"
    - "Actual-capture-first characterization: run code, capture output, assert that output — cross-check against README and document discrepancies"

key-files:
  created:
    - tests/test_characterization.py
  modified:
    - tests/test_core_compute.py  # created in this plan (Task 1)

key-decisions:
  - "Assert actual captured output, not README values — README is cross-checked and discrepancies are documented"
  - "SMT characterization uses actual code output (not README) because README §8 was stale; n values 2-3x larger in current SMT package version"
  - "module-scoped fixtures load each parquet file once per pytest session, avoiding 8x redundant 1.85M-row loads"

patterns-established:
  - "Characterization test pattern: module-skip on data absence + module-scoped fixtures + actual-capture assertions"

requirements-completed: [TEST-01, TEST-02]

duration: ~13h (across two sessions; dominated by 4x SMT scan at ~11 min each)
completed: 2026-06-12
---

# Phase 01 Plan 03: Test Suite — Unit + Characterization Tests Summary

**Two test modules that pin the engine's published barrier rates in executable assertions before any refactor can move them silently.**

## Performance

- **Duration:** ~13h across two sessions (test run time dominated by SMT scans: ~11 min each)
- **Completed:** 2026-06-12
- **Tasks:** 2 of 2
- **Files created:** 2

## Accomplishments

- `tests/test_core_compute.py` — 6 data-free unit tests covering `compute_basic`, `compute_mc`, `compute_significance`, `compute_wick`, and `compute_combined` via 18-bar synthetic OHLCV fixtures with hand-verified counts.
- `tests/test_characterization.py` — 5 integration tests that run the real pipeline (`load_1m` → `resample_ohlcv` → `prepare`) and assert 64 barrier rates across §1 Baseline (16), §4 Significance (16), §3 Combined (6 headline buckets), §2 Wick (1 flagship stat), and §8 SMT (16). Module skips cleanly when data absent; SMT test skips when local SMT package absent.
- Full test suite (66 tests + 5 new) passes on the dev machine and skips gracefully in CI.

## Task Commits

1. **Task 1: Unit tests for five core compute functions** — `fa7e2ee` (test)
2. **Task 2: Characterization tests locking README headline numbers** — `23e3b9f` (test)

**Plan metadata:** _(pending final metadata commit)_

## Files Created

- `/mnt/e/backup/code/Finance/research/cisd-markov/tests/test_core_compute.py` — 6 data-free unit tests using 18-bar synthetic frame through `prepare()` and a separate 8-bar frame for `compute_significance`.
- `/mnt/e/backup/code/Finance/research/cisd-markov/tests/test_characterization.py` — 5 integration characterization tests; all expected values captured from current code.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] README §8 SMT expected values were stale**
- **Found during:** Task 2 verification (test_smt_cisd_rates FAILED)
- **Issue:** README §8 table was produced by an older SMT package version. Current SMT package generates 2-3x more events per cell, so sample sizes and rates have shifted. E.g., NQ Daily bullish w/ SMT: README n=24, actual n=63.
- **Fix:** Ran `_capture_smt.py` script to independently capture all 16 actual values from current code; updated `_SMT_EXPECTED` dict in `test_characterization.py` to use actual values.
- **Files modified:** `tests/test_characterization.py`
- **Commit:** `23e3b9f` (same task commit — value capture was part of the verification step)

### README Discrepancies Found (no code changed; documented per plan rule)

**§3 Combined — ES Daily Bear 2c past_wick**
- README states: 80.7%
- Actual captured: 80.6452% (rounds to 80.6%)
- Delta: 0.055pp — just outside the 1-decimal rounding window
- Assertion uses actual (80.6); README value 80.7 is off by 0.05pp

**§3 Combined — Wrong instrument label in README text**
- README text says: "Within-wick + 2c on Daily (ES bear) drops to 36.7%"
- Actual ES Daily Bear 2c within_wick: 38.0282% (rounds to 38.0%)
- Actual NQ Daily Bear 2c within_wick: 36.6667% (rounds to 36.7%)
- The 36.7% figure matches NQ, not ES. README has the instrument label wrong.
- Assertion uses actual ES value (38.0); test comment documents the mislabel.

**§8 SMT — All 16 cells differ from README**

Full discrepancy table (README → Actual):

| Cell | README rate | README n | Actual rate | Actual n |
|------|-------------|----------|-------------|----------|
| NQ Daily bullish | 70.8% | 24 | 63.5% | 63 |
| NQ Daily bearish | 63.6% | 11 | 60.3% | 58 |
| NQ 4H bullish | 53.1% | 81 | 56.2% | 292 |
| NQ 4H bearish | 51.1% | 94 | 51.4% | 315 |
| NQ 1H bullish | 62.8% | 301 | 64.3% | 984 |
| NQ 1H bearish | 59.3% | 388 | 56.0% | 1143 |
| NQ 15min bullish | 64.7% | 1237 | 64.7% | 3761 |
| NQ 15min bearish | 62.5% | 1363 | 61.9% | 4020 |
| ES Daily bullish | 61.5% | 26 | 57.6% | 66 |
| ES Daily bearish | 27.8% | 18 | 52.3% | 65 |
| ES 4H bullish | 61.0% | 82 | 60.9% | 281 |
| ES 4H bearish | 51.0% | 98 | 53.2% | 312 |
| ES 1H bullish | 63.6% | 272 | 64.3% | 942 |
| ES 1H bearish | 58.2% | 364 | 56.8% | 1086 |
| ES 15min bullish | 64.3% | 1219 | 64.0% | 3558 |
| ES 15min bearish | 62.2% | 1335 | 61.3% | 3779 |

Root cause: SMT package was updated after the README was written. The new version detects ~2-3x more Swing SMT events (different lookback or matching logic). README §8 is stale and should be regenerated. This is outside the scope of Plan 03 (which is test-only, no source changes).

## Known Stubs

None — all test expectations are wired to real pipeline output.

## Threat Flags

None — test files only; no new network endpoints, auth paths, or schema changes.

## Self-Check: PASSED

- `tests/test_core_compute.py` — exists (committed fa7e2ee)
- `tests/test_characterization.py` — exists (committed 23e3b9f)
- Both commits present in `git log --oneline`
- Full suite: 5 passed in 618.81s (characterization) + 6 passed (unit tests)
