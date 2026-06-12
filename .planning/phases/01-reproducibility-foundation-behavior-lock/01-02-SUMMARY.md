---
phase: 01-reproducibility-foundation-behavior-lock
plan: 02
subsystem: infra
tags: [ci, determinism, gitignore, conftest, pytest, github-actions]
dependency_graph:
  requires: [pinned-runtime, env-var-smt-path]
  provides: [ci-pipeline, determinism-tests, repo-hygiene, working-dir-independence]
  affects: [.gitignore, conftest.py, pyproject.toml, tests/test_determinism.py, .github/workflows/ci.yml]
tech_stack:
  added: [pyproject.toml, conftest.py, .github/workflows/ci.yml, tests/test_determinism.py]
  patterns: [sys.path.insert in conftest, pyproject.toml rootdir anchor, GitHub Actions workflow, data-free synthetic fixture via prepare()]
key_files:
  created:
    - .github/workflows/ci.yml
    - conftest.py
    - pyproject.toml
    - tests/test_determinism.py
  modified:
    - .gitignore
decisions:
  - "pyproject.toml [tool.pytest.ini_options] with pythonpath=['.'] added alongside conftest.py — without a rootdir anchor, conftest.py is not loaded when pytest is invoked from tests/ (CONCERNS.md explicitly recommends this as the alternative)"
  - "output/ files removed from git index with git rm -r --cached (files remain on disk)"
  - "tests/test_research_extensions.py.premerge deleted (untracked file, no git history needed)"
metrics:
  duration: "8m"
  completed: "2026-06-12T07:53:24Z"
  tasks_completed: 3
  files_changed: 7
---

# Phase 01 Plan 02: CI + Determinism + Repo Hygiene Summary

CI workflow, conftest.py with pyproject.toml rootdir anchor, data-free determinism tests locking compute-function repeat-run identity, and repo hygiene: 25 committed output/ blobs untracked, data/ gitignore case fixed (capital D to lowercase), output/ and .env ignored, leftover .premerge artifact deleted.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Repo hygiene: fix gitignore case, untrack output/, ignore .env, delete .premerge | 349f542 | .gitignore |
| 2 | conftest.py + pyproject.toml + determinism tests | e50fdf8 | conftest.py, pyproject.toml, tests/test_determinism.py |
| 3 | GitHub Actions CI workflow | c319515 | .github/workflows/ci.yml |

## What Was Built

**.gitignore** corrected: `Data/*.parquet` and `Data/*.csv` (capital D — silently non-functional on Linux) changed to `data/*.parquet` and `data/*.csv`. Added `output/` to stop generated PNGs/CSVs/HTML from being tracked. Added `.env` and `.env.local` (only `.env.example` stays tracked, per plan 01-01 deferral). `git rm -r --cached output/` removed all 25 committed generated blobs from the index while leaving files on disk. Deleted `tests/test_research_extensions.py.premerge` (untracked pre-merge artifact).

**conftest.py** at repo root inserts `str(Path(__file__).parent)` at the front of `sys.path` so `import cisd_analysis` and `import scripts.*` work regardless of working directory.

**pyproject.toml** (Rule 2 deviation — see below) anchors pytest's rootdir at the repo root via `[tool.pytest.ini_options] pythonpath = ["."]`. Without this, pytest running from `tests/` sets rootdir = `tests/` and skips the parent-directory `conftest.py`, leaving the working-directory-independence goal unachieved. The CONCERNS.md document explicitly recommends this as the complementary fix.

**tests/test_determinism.py** contains four data-free tests:
- `test_compute_basic_is_deterministic` — calls `compute_basic` twice on the same prepared inline frame and asserts exact dict equality.
- `test_compute_combined_is_deterministic` — same for `compute_combined`.
- `test_prepared_frame_contains_at_least_one_cisd` — guards that the synthetic fixture actually produces CISDs so the above tests are not vacuously true. The 25-bar sequence through `prepare()` produces a bearish CISD at bar 1 and a bullish CISD at bar 2.
- `test_no_nondeterministic_calls_in_compute_paths` — source-code pattern scan over the Data Loading + Compute Functions sections of `cisd_analysis.py`; FAILS LOUDLY if `datetime.now`, `datetime.utcnow`, `time.time`, unseeded `random.*`, or unseeded `np.random.*` appear in the computed pipeline.

**.github/workflows/ci.yml** triggers on `push` and `pull_request`. One job: `ubuntu-latest`, Python 3.12, `pip install -r requirements.txt`, `python -m pytest -q`. Actions pinned to `actions/checkout@v4` and `actions/setup-python@v5`. No SMT package or parquet data provided — tests that need them skip cleanly via existing `pytest.skip` guards.

## Verification Results

All plan acceptance criteria passed:

- `grep -q '^data/\*\.parquet' .gitignore` — PASS
- `grep -q '^output/' .gitignore && grep -q '^\.env' .gitignore` — PASS
- `git ls-files output/ | wc -l` → 0 — PASS (output/ fully untracked)
- `ls output/` — files still on disk — PASS
- `test ! -f tests/test_research_extensions.py.premerge` — PASS
- `pytest -q tests/test_determinism.py` from repo root → 4 passed — PASS
- `cd tests && pytest -q test_determinism.py` from subdirectory → 4 passed — PASS
- Full suite `pytest -q` → 61 passed — PASS
- `ci.yml` has push trigger, requirements.txt install, pytest run, Python 3.12, pinned actions — PASS

## Deviations from Plan

### Auto-added Missing Critical Functionality

**1. [Rule 2 - Missing Critical] pyproject.toml to anchor pytest rootdir**
- **Found during:** Task 2
- **Issue:** `conftest.py` at the repo root is only loaded when pytest's rootdir resolves to the repo root. Without an ini file (`pytest.ini`, `pyproject.toml`, or `setup.cfg`) at the repo root, running `cd tests && pytest` sets rootdir = `tests/` and skips `conftest.py`, breaking the stated goal of "tests run from any working directory." Confirmed: all 60 pre-existing tests raised `ModuleNotFoundError: No module named 'cisd_analysis'` when run from `tests/`.
- **Fix:** Created `pyproject.toml` with `[tool.pytest.ini_options] pythonpath = ["."]`. This anchors rootdir at the repo root and adds `.` to Python path via pytest's native mechanism — exactly the alternative prescribed in CONCERNS.md.
- **Files modified:** `pyproject.toml` (new)
- **Commit:** e50fdf8

## Known Stubs

None. All changes are infrastructure — no data-flow stubs introduced.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes beyond the planned CI trust boundary (T-02-SC: pip install on hosted runner, mitigated by pinned requirements.txt and pinned action major tags; T-02-01: .env isolation, fully mitigated by Task 1).

## Self-Check: PASSED

- .gitignore: FOUND, contains data/*.parquet (lowercase), output/, .env
- conftest.py: FOUND at /mnt/e/backup/code/Finance/research/cisd-markov/conftest.py
- pyproject.toml: FOUND at /mnt/e/backup/code/Finance/research/cisd-markov/pyproject.toml
- tests/test_determinism.py: FOUND
- .github/workflows/ci.yml: FOUND
- output/ tracked files: 0 (all untracked)
- tests/test_research_extensions.py.premerge: DELETED
- Commit 349f542: FOUND
- Commit e50fdf8: FOUND
- Commit c319515: FOUND
- 61/61 tests pass from repo root
- 4/4 determinism tests pass from tests/ subdirectory
