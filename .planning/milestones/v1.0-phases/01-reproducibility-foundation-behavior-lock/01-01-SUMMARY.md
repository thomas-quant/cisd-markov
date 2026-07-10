---
phase: 01-reproducibility-foundation-behavior-lock
plan: 01
subsystem: infra
tags: [reproducibility, pinned-deps, env-var, graceful-fallback, smt]
dependency_graph:
  requires: []
  provides: [pinned-runtime, env-var-smt-path, graceful-smt-skip]
  affects: [cisd_analysis.py, scripts/build_forward_returns.py]
tech_stack:
  added: [requirements.txt, .env.example]
  patterns: [os.environ.get with default, try/except optional-dependency probe]
key_files:
  created:
    - requirements.txt
    - .env.example
  modified:
    - cisd_analysis.py
    - scripts/build_forward_returns.py
    - README.md
    - tests/test_forward_returns_builder.py
decisions:
  - "Pin exactly the installed .venv versions (no upgrade) — pandas 3.0.2, numpy 2.4.4, matplotlib 3.10.8, pyarrow 23.0.1, pytest 9.0.2 confirmed identical"
  - "Plotly.js is CDN-only; not added to requirements.txt — documented as comment"
  - "SMT_PKG_PATH default is the existing WSL path so dev-machine behavior is byte-identical"
  - ".gitignore additions for .env/.env.local are deferred to plan 01-02 (noted in commit)"
metrics:
  duration: "4m 6s"
  completed: "2026-06-12T07:43:12Z"
  tasks_completed: 3
  files_changed: 6
---

# Phase 01 Plan 01: Reproducibility Foundation (Pin + Env-Var SMT) Summary

Pinned the runtime in requirements.txt, moved the hardcoded SMT package path to an env-var with a documented default in .env.example, and made every entry point degrade gracefully when SMT is absent — proven by a passing regression test.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Pin runtime in requirements.txt; update README | 7068f37 | requirements.txt, README.md |
| 2 | Env-var SMT path + graceful smt_cisd skip in main() | 71691c4 | cisd_analysis.py, .env.example |
| 3 | Graceful SMT fallback in build_forward_returns.py + regression test | 54e9cf5 | scripts/build_forward_returns.py, tests/test_forward_returns_builder.py |

## What Was Built

**requirements.txt** pins five packages to their exact installed versions (confirmed via `.venv/bin/python` before writing): `pandas==3.0.2`, `numpy==2.4.4`, `matplotlib==3.10.8`, `pyarrow==23.0.1`, `pytest==9.0.2`. A comment explains Plotly.js is CDN-only and not pip-installed.

**cisd_analysis.py** now reads `_SMT_PKG_PATH` from `os.environ.get("SMT_PKG_PATH", "/mnt/e/backup/code/Finance/Misc/SMT")`. The default preserves dev-machine behavior exactly. `main()` has a graceful guard: when `smt_cisd` is in the requested keys but `_SMT_PKG_PATH` does not exist on disk, it prints a `[warn]` line, drops `smt_cisd` from `requested` and `standalone`, and sets `needs_swing_smt=False` so `prepare_pair` is never called with `with_swing_smt=True`.

**build_forward_returns.py** mirrors `build_expectancy.py`'s pattern: a single probe `prepare_pair(..., with_swing_smt=True)` inside `try/except Exception` before the timeframe loop; on failure it prints `[warn]` and sets `with_smt=False`; the loop uses `with_swing_smt=with_smt`.

**tests/test_forward_returns_builder.py** gains `test_build_dataset_falls_back_when_smt_unavailable`, which monkeypatches `load_1m` (tiny synthetic frame) and `prepare_pair` (raises on `with_swing_smt=True`, returns empty OHLCV frames on `False`), then asserts `build_dataset()` completes and the `False` branch was exercised.

**.env.example** documents `SMT_PKG_PATH` with default value and explains it is optional (only needed by `smt_cisd` and `with_swing_smt=True` paths).

## Verification Results

All plan acceptance criteria passed:
- `requirements.txt` contains all 5 pinned versions; `grep -c '==' requirements.txt` returns 5
- README "Requirements" section references `pip install -r requirements.txt`
- Key Findings headline tables unchanged (verified via `git diff README.md`)
- `import cisd_analysis` succeeds with and without `SMT_PKG_PATH` set
- `SMT_PKG_PATH=/tmp/nope` sets `_SMT_PKG_PATH` to that path at import time
- `grep -q 'with_swing_smt=with_smt' scripts/build_forward_returns.py` passes
- 19/19 tests pass (`pytest tests/test_forward_returns_builder.py`)

## Deviations from Plan

### Whitespace normalization in README.md

**Found during:** Task 1
**Issue:** The existing README.md used Windows CRLF line endings; the Edit tool writes Unix LF. Git diff showed CRLF→LF normalization on all lines, not just the Requirements section.
**Fix:** Accepted as-is. No content changed; all Key Findings numbers are byte-identical. The normalization is benign and makes the file consistent with the rest of the repo (other files use LF).
**Impact:** Zero — no numbers altered, no meaning changed.

None of the STRIDE threats materialized: no new packages introduced (T-01-SC), T-01-01 accepted (same trust level as prior hardcoded path), T-01-02 fully mitigated by Tasks 2 and 3.

## Handoff Notes

- `.gitignore` additions for `.env` / `.env.local` are out of scope for this plan. Plan 01-02 owns that change (documented in Task 2 commit).
- SMT integration coverage in CI remains a known gap (acknowledged in STATE.md blockers). This plan addresses the path mechanism and graceful fallback; CI infrastructure is Phase 1 Plan 2.

## Known Stubs

None. All changes are infrastructure/configuration — no data-flow stubs introduced.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what the plan's threat model already covered.

## Self-Check: PASSED

- requirements.txt: FOUND (/mnt/e/backup/code/Finance/research/cisd-markov/requirements.txt)
- .env.example: FOUND (/mnt/e/backup/code/Finance/research/cisd-markov/.env.example)
- Commit 7068f37: FOUND
- Commit 71691c4: FOUND
- Commit 54e9cf5: FOUND
- 19/19 tests pass
