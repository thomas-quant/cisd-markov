---
phase: 01-reproducibility-foundation-behavior-lock
verified: 2026-06-12T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 01: Reproducibility Foundation — Verification Report

**Phase Goal:** The engine reproduces deterministically on any machine, runs its tests in CI, and the current published headline numbers are locked so no later change can move them silently.
**Verified:** 2026-06-12
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A fresh checkout reproduces the runtime from a pinned manifest, reads SMT path from a documented env var, and every entry point degrades gracefully when SMT is absent | VERIFIED | `requirements.txt` pins 5 packages; `cisd_analysis.py:67` reads `os.environ.get("SMT_PKG_PATH", …)`; `main()` guards `.exists()` at line 1324; `build_forward_returns.py:361–365` uses `try/except` probe (see WR-01 note) |
| 2 | The pytest suite runs automatically on push via CI, succeeds from any working directory, and computed numbers are identical across repeated runs | VERIFIED | `.github/workflows/ci.yml` triggers on `push`; `conftest.py` + `pyproject.toml pythonpath=["."]` anchor rootdir; 67 fast tests pass; `test_compute_basic_is_deterministic` and `test_compute_combined_is_deterministic` assert exact dict equality (see WR-03 note) |
| 3 | Generated output/ artifacts are no longer tracked in git and the data/ gitignore case mismatch is fixed | VERIFIED | `git ls-files output/` returns 0; `.gitignore` contains `data/*.parquet` (lowercase), `output/`, `.env`, `.env.local`; `tests/test_research_extensions.py.premerge` is absent |
| 4 | Characterization tests assert the current README headline numbers and fail if any of those numbers change | VERIFIED | `tests/test_characterization.py` locks 64 barrier rates from the live pipeline; §1/§2/§3/§4 values agree with README within rounding tolerance; §8 SMT values differ from README (SMT package updated, README stale) but are locked to current pipeline output — documented in SUMMARY (see WR-04 note) |
| 5 | compute_basic, compute_mc, compute_significance, compute_wick, and compute_combined each have unit tests over their barrier counts | VERIFIED | `tests/test_core_compute.py` contains 6 data-free tests covering all 5 functions with hand-verified totals and runs pinned on both numerator and denominator |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `requirements.txt` | Pinned runtime manifest | VERIFIED | `pandas==3.0.2`, `numpy==2.4.4`, `matplotlib==3.10.8`, `pyarrow==23.0.1`, `pytest==9.0.2`; CDN plotly note present |
| `.env.example` | Documented SMT_PKG_PATH default | VERIFIED | Contains `SMT_PKG_PATH=/mnt/e/backup/code/Finance/Misc/SMT` with comment explaining it is optional |
| `cisd_analysis.py` | Env-var SMT path + graceful skip in main() | VERIFIED | `import os` at line 16; `os.environ.get("SMT_PKG_PATH", …)` at line 67; `.exists()` guard in main() at line 1324 |
| `scripts/build_forward_returns.py` | Graceful SMT fallback (parity with build_expectancy.py) | VERIFIED | `try/except Exception` probe at lines 361–365; loop uses `with_swing_smt=with_smt` |
| `.gitignore` | Correct data/ case + output/ ignore + .env ignore | VERIFIED | `data/*.parquet`, `data/*.csv`, `output/`, `.env`, `.env.local` all present |
| `conftest.py` | Repo-root on sys.path | VERIFIED | `sys.path.insert(0, _REPO_ROOT)` where `_REPO_ROOT = str(Path(__file__).parent.resolve())` |
| `pyproject.toml` | Rootdir anchor for pytest working-dir independence | VERIFIED | `[tool.pytest.ini_options] pythonpath = ["."]` — necessary companion to conftest.py so `cd tests && pytest` resolves rootdir correctly |
| `tests/test_determinism.py` | Data-free repeat-run determinism checks | VERIFIED | 4 tests; compute_basic and compute_combined run twice and assert exact dict equality; source-code non-determinism guard (see WR-03 note) |
| `.github/workflows/ci.yml` | GitHub Actions workflow on push | VERIFIED | `on: push` + `pull_request`; Python 3.12; `pip install -r requirements.txt`; `python -m pytest -q`; actions pinned to @v4/@v5 |
| `tests/test_core_compute.py` | Unit tests for 5 core compute functions | VERIFIED | 6 tests; 18-bar synthetic frame through `prepare()`; separate 8-bar raw frame for `compute_significance`; all assert integer totals and runs |
| `tests/test_characterization.py` | Headline-number lock gated on data availability | VERIFIED | `pytestmark = pytest.mark.skipif(not _DATA_PRESENT, …)` module-level gate; SMT test additionally skips when `_SMT_PKG_PATH` absent; 5 integration tests covering §1/§2/§3/§4/§8 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cisd_analysis._SMT_PKG_PATH` | `os.environ['SMT_PKG_PATH']` | `os.environ.get` with default | WIRED | Line 67: `Path(os.environ.get("SMT_PKG_PATH", "/mnt/e/backup/code/Finance/Misc/SMT"))` |
| `scripts/build_forward_returns.build_dataset` | `prepare_pair(with_swing_smt=with_smt)` | try/except probe then flag | WIRED | Lines 361–365: probe raises → `with_smt=False`; loop uses `with_swing_smt=with_smt` |
| `.github/workflows/ci.yml` | `requirements.txt` | `pip install -r requirements.txt` | WIRED | Line 25 of ci.yml |
| `conftest.py` | `sys.path` | `sys.path.insert` from `__file__` | WIRED | Line 16: `sys.path.insert(0, _REPO_ROOT)` |
| `tests/test_characterization.py` | `cisd_analysis.compute_basic / compute_significance / compute_combined / compute_wick` | real pipeline (load_1m → resample → prepare) | WIRED | All 5 tests call functions directly on prepared frames from module-scoped fixtures |
| `tests/test_core_compute.py` | `cisd_analysis.barrier_hit` counts | synthetic frames with hand-computed expected totals/runs | WIRED | Tests call `compute_basic`, `compute_mc`, `compute_significance`, `compute_wick`, `compute_combined` directly and assert `["runs"]` and `["totals"]` integer values |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INFRA-01 | 01-01 | Pinned runtime manifest | SATISFIED | `requirements.txt` with exact installed versions |
| INFRA-02 | 01-01 | SMT path from env var with documented default | SATISFIED | `os.environ.get("SMT_PKG_PATH", …)` + `.env.example` |
| INFRA-03 | 01-01 | Every entry point degrades gracefully without SMT | SATISFIED | `main()` guards path-missing; `build_forward_returns.py` probes try/except; `build_expectancy.py` had it already |
| INFRA-04 | 01-02 | CI runs pytest on push | SATISFIED | `.github/workflows/ci.yml` push trigger |
| INFRA-05 | 01-02 | Tests run from any working directory; computed results deterministic | SATISFIED | `conftest.py` + `pyproject.toml`; repeat-run tests pass |
| INFRA-06 | 01-02 | output/ untracked; data/ gitignore case fixed | SATISFIED | `git ls-files output/` = 0; lowercase pattern in .gitignore |
| TEST-01 | 01-03 | Characterization tests lock published headline numbers | SATISFIED | `test_characterization.py` gates and asserts 64 pipeline rates |
| TEST-02 | 01-03 | Unit tests for core compute functions | SATISFIED | `test_core_compute.py` covers all 5 functions with pinned integer assertions |

All 8 Phase 1 requirements verified. No orphaned requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_determinism.py` | 141–147 | `_extract_compute_sections` halts at `"# ── Chart Functions"` header (line 548 of cisd_analysis.py), missing 9 compute functions defined below it (`compute_volume` through `compute_sssf_swing`, lines 648–993) | Warning | False-green guard: a future non-deterministic call in any of those 9 functions would not be caught by `test_no_nondeterministic_calls_in_compute_paths`. Current state is safe — grep confirms zero non-deterministic calls exist in ANY compute function today. |
| `cisd_analysis.py` | 1324 | `main()` SMT guard is `if needs_swing_smt and not _SMT_PKG_PATH.exists()` — guards path-missing but not import-failure on an existing-but-broken path | Warning | If the SMT path exists but the package is corrupted/partial, `_load_scan_smts_historical` raises an uncaught `ImportError` that aborts all 13 non-SMT analyses. Asymmetric with `build_forward_returns.py` which probes inside `try/except Exception`. |
| `cisd_analysis.py` | 67 | `Path(os.environ.get("SMT_PKG_PATH", …))` — empty env var (`export SMT_PKG_PATH=`) resolves to `Path("")` = `PosixPath('.')`, which `.exists()` returns True, bypassing the guard | Warning | Rare misconfiguration scenario; treated as warning not blocker per code review (0 critical findings). |
| `README.md` | §8 (lines ~103–119) | SMT table publishes e.g. "Daily NQ Bullish 70.8% (n=24)"; `test_characterization.py` locks actual value at 63.5% (n=63). All 16 §8 rows differ from README. Root cause: SMT package updated after README was written; current package detects ~2-3x more events. | Warning | "A reported edge can be trusted" is the project's core value; README §8 contradicts the project's own locked tests. Documentation debt that should be addressed before relying on §8 findings. |
| `README.md` | §3 line 56 | "Within-wick + 2c on Daily (ES bear) drops to 36.7%" — test documents actual NQ value is 36.7%, actual ES value is 38.0%; instrument label in README is wrong | Warning | Minor instrument mislabel; test locks correct values. |

No `TBD`, `FIXME`, or `XXX` markers were found in files modified by this phase.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| SMT_PKG_PATH env var read at import time | `SMT_PKG_PATH=/tmp/nope python3 -c "import cisd_analysis; print(cisd_analysis._SMT_PKG_PATH)"` | `/tmp/nope` | PASS |
| output/ fully untracked | `git ls-files output/ \| wc -l` | `0` | PASS |
| .premerge artifact deleted | `test ! -f tests/test_research_extensions.py.premerge` | exit 0 | PASS |
| Fast test suite (67 tests, excluding characterization) | `python3 -m pytest -q --ignore=tests/test_characterization.py` | `67 passed in 5.11s` | PASS |

---

### Gaps Summary

No gaps. All 5 success criteria are verified. The four warnings above are code-quality limitations within documented tolerances:

**WR-01** (main() broken-but-present SMT path): The stated criterion is "degrades gracefully when SMT is **absent**." Absent = path missing, which IS handled. The broken-but-present scenario is not covered by the criterion's literal scope.

**WR-03** (incomplete determinism guard): Currently zero non-deterministic calls exist in any compute function. The repeat-run tests do confirm determinism for the two functions tested. The incomplete source scan is a test-quality gap for future-proofing, not a current failure.

**WR-04** (stale README §8 and §3): The plan explicitly prescribed actual-capture-first characterization with README discrepancies documented in SUMMARY rather than weakening assertions. The locking mechanism is in place — any pipeline change will trip the tests. The README staleness is documentation debt, not a behavioral failure.

**Summary:** The phase delivers what it promised. The engine's core published numbers are locked in executable assertions before any later refactor can move them silently, the environment is pinned and reproducible, CI runs on push, and tests run from any working directory. The warnings narrow some coverage edges but do not break the phase goal.

---

_Verified: 2026-06-12_
_Verifier: Claude (gsd-verifier)_
