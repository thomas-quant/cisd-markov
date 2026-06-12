# Codebase Concerns

**Analysis Date:** 2026-06-12

## Tech Debt

**God-file architecture in `cisd_analysis.py`:**
- Issue: All data loading, resampling, annotation, barrier logic, 14 compute functions, 14 chart functions, CSV builder, figure builder, and CLI orchestration live in one 1380-line file.
- Files: `cisd_analysis.py`
- Impact: Every new analysis requires touching the same file. Merge conflicts are likely as the analysis surface grows. Functions at the bottom are hard to navigate to quickly.
- Fix approach: Split into `cisd_data.py` (load/resample/prepare), `cisd_barriers.py` (barrier logic, compute functions), `cisd_charts.py` (chart functions), keeping `cisd_analysis.py` as a thin orchestrator that imports from those modules.

**Duplicate branch in `build_csv_rows`:**
- Issue: The key `"smt_cisd"` is handled at line 1161, but the branch at line 1184 (`elif key in ("smt_cisd", "sweep", "sssf_swing")`) is dead for `smt_cisd` because it can never be reached. `"sweep"` and `"sssf_swing"` are handled correctly by the second branch, but this looks like the `smt_cisd` case was added to the earlier explicit branch and the second branch was not cleaned up.
- Files: `cisd_analysis.py` lines 1161–1187
- Impact: `smt_cisd` rows appear in CSV output. `sweep` and `sssf_swing` rows also appear. No broken behavior today, but the redundancy is confusing and will mislead a future reader into thinking the second branch handles `smt_cisd` as a fallback.
- Fix approach: Remove `"smt_cisd"` from the `elif key in (...)` tuple at line 1184, leaving only `("sweep", "sssf_swing")`.

**`compute_significance` reimplements CISD detection:**
- Issue: Unlike every other `compute_*` function, `compute_significance` (line 483) does not consume the precomputed `cisd_type` column. It recomputes CISD conditions from scratch using a stricter definition (close past prev high/low). There is no comment distinguishing this intent from a bug.
- Files: `cisd_analysis.py` lines 483–499
- Impact: Subtle semantic difference from all other analyses. A reader adding a new analysis may copy the wrong pattern. The discrepancy is undocumented in the function signature or docstring.
- Fix approach: Add a clear docstring note explaining why this function intentionally bypasses `cisd_type`, or introduce a separate `cisd_type_strict` column computed in `prepare()` and consumed here consistently.

**`build_forward_returns.py` always requires SMT:**
- Issue: `build_dataset()` in `scripts/build_forward_returns.py` calls `prepare_pair(..., with_swing_smt=True)` unconditionally (line 359). It has no graceful fallback if `_SMT_PKG_PATH` is unavailable, unlike `build_expectancy.py` which has a try/except (line 303–306).
- Files: `scripts/build_forward_returns.py` line 359
- Impact: `build_forward_returns.py` will raise `FileNotFoundError` or `ImportError` on any machine where the SMT package is not installed at the hardcoded path. The forward-returns report cannot be generated without the external SMT dependency.
- Fix approach: Mirror the try/except fallback pattern from `build_expectancy.py`: attempt `with_swing_smt=True`, catch the exception, log a warning, and retry with `with_swing_smt=False`.

## Known Bugs

**No known functional bugs confirmed.**
- The test suite covers the core annotation paths, barrier logic, and filter chains. No incorrect outputs were identified during analysis.

## Security Considerations

**No secrets or credentials in code.**
- The codebase only reads local parquet files and writes local output. No API keys, tokens, or credentials are present.

**Note:** `.gitignore` contains `Data/*.parquet` (capital D) which does not match the actual `data/` directory (lowercase) on the Linux/WSL filesystem. This means the `.gitignore` rule for parquet exclusion is silently non-functional. The parquet files are currently not tracked in git, but if one were staged accidentally, the `.gitignore` would not prevent it.
- Files: `.gitignore` line 10
- Fix approach: Change `Data/*.parquet` and `Data/*.csv` to `data/*.parquet` and `data/*.csv`.

## Performance Bottlenecks

**Row-by-row Python loops in `_annotate_cisd_research`:**
- Problem: The core annotation function iterates every row with `for idx, ct in enumerate(annotated["cisd_type"])` and writes back using `iat` + `columns.get_loc()` (lines 208–244). Each CISD event triggers 6–8 individual cell writes. For large Daily frames this is still fast, but 15-minute frames with thousands of CISDs make this the hottest code path.
- Files: `cisd_analysis.py` lines 208–244
- Cause: FVG detection and FVG hold classification require looking at neighboring rows, making vectorization non-trivial. However, `has_dir_sweep`, `prev_bar_is_dir_swing`, and `cisd_bar_is_dir_swing` could be written to temporary arrays and assigned in bulk at the end.
- Improvement path: Accumulate all per-row results in plain Python lists/dicts indexed by integer position, then bulk-assign to columns after the loop using `df[col] = values_array`. This avoids repeated `iat`+`get_loc` overhead.

**`_has_directional_sweep` double-nested Python loop:**
- Problem: For each CISD event, `_has_directional_sweep` runs up to `SWEEP_TOLERANCE × SWEEP_SWING_LOOKBACK = 5 × 20 = 100` iterations (lines 174–188). Called once per CISD inside `_annotate_cisd_research`'s outer loop, this compounds the Python-loop overhead.
- Files: `cisd_analysis.py` lines 168–188
- Cause: The sweep window `[t-4, t]` is small enough that vectorization via rolling operations is feasible but not yet implemented.
- Improvement path: Precompute a rolling boolean "did this bar sweep a prior swing" mask for the whole DataFrame using rolling min/max comparisons against shifted swing pivot series, then extract the result per CISD index.

**O(n×m) inner loop in `_annotate_swing_smt_from_events`:**
- Problem: For each CISD row, the function iterates the entire `event_rows` list (lines 292–306). This is O(n_cisd × n_events). For long timeframes with many events this becomes noticeable.
- Files: `cisd_analysis.py` lines 292–316
- Cause: The matching window is `[t-2, t]` per CISD. The events list is not indexed.
- Improvement path: Build a mapping from event timestamp to event dict, then for each CISD use `pd.Index.searchsorted` to find events in the 2-bar window in O(log m) per CISD.

**`iterrows()` in every `compute_*` function:**
- Problem: All 14 compute functions iterate `df_cisd.iterrows()` with an explicit Python loop and call `df.index.get_loc(ts)` on each iteration (62 combined occurrences in `cisd_analysis.py`). Each `get_loc` involves a hashtable lookup on the DatetimeIndex.
- Files: `cisd_analysis.py` lines 455, 463, 502, 524 etc.
- Cause: Barrier logic in `barrier_hit()` operates on integer positions, requiring `idx = index.get_loc(ts)` to convert timestamp to position.
- Improvement path: Precompute an integer-position array for all CISD rows once (e.g., `np.flatnonzero(df["cisd_type"].notna())`), then index into NumPy arrays directly — as already done in `build_expectancy.py`'s `build_event_r_multiples()` which uses `np.flatnonzero` and array indexing throughout. The expectancy builder is the reference implementation to follow.

**`build_forward_returns.py` row-mutation loop:**
- Problem: `build_forward_return_rows()` uses `for ts, row in rows.iterrows()` with `rows.at[ts, col] = value` writes per row (lines 138–143) to assign `size_cross`, `wick`, and `consec` columns.
- Files: `scripts/build_forward_returns.py` lines 138–143
- Cause: `_classify_size_cross` and `_classify_wick` operate per-row. They could be refactored to accept and return Series.
- Improvement path: Vectorize `_classify_wick` and `_classify_size_cross` to accept a whole DataFrame and return a Series, then assign the column result at once.

## Fragile Areas

**Hardcoded machine-specific path for SMT package:**
- Files: `cisd_analysis.py` line 66
- Why fragile: `_SMT_PKG_PATH = Path("/mnt/e/backup/code/Finance/Misc/SMT")` is a WSL-specific absolute path that will not resolve on any other machine, CI environment, or if the SMT package is moved.
- Safe modification: Set via an environment variable or a config file. Example: `_SMT_PKG_PATH = Path(os.environ.get("SMT_PKG_PATH", "/mnt/e/backup/code/Finance/Misc/SMT"))`. Add a `SMT_PKG_PATH` entry to a `.env.example` file.
- Test coverage: `test_prepare_pair_swing_smt_columns_exist_when_scanner_runs` is skipped when the path is unavailable (guarded by `pytest.skip`), so SMT integration is not tested in CI.

**`STANDALONE_KEYS` and `FILENAMES` are defined inside `main()` and duplicated with `base_h` dicts:**
- Files: `cisd_analysis.py` lines 1199–1202, 1260–1261, 1300–1310, 1357–1367
- Why fragile: Adding a new standalone analysis requires four separate edits: `base_h` dict in `build_figure`, `base_h` dict in `build_standalone_figure`, `STANDALONE_KEYS` set in `main()`, and `FILENAMES` dict in `main()`. Missing any one of these causes either a KeyError or a missing output file with no error message.
- Safe modification: Consolidate into a single `ANALYSIS_META` registry dict at module level with `standalone`, `height`, and `filename` fields per key, and derive all four usages from it.

**No `tests/__init__.py` or `conftest.py`:**
- Files: `tests/` directory
- Why fragile: Tests import `cisd_analysis` and `scripts.build_forward_returns` without any path configuration file. This works when pytest is run from the repo root (the default) but will fail silently if invoked from a subdirectory or if a test runner uses a different working directory.
- Safe modification: Add a `conftest.py` at the repo root that inserts `str(Path(__file__).parent)` into `sys.path`, or add a minimal `pyproject.toml` with `[tool.pytest.ini_options] pythonpath = ["."]`.

**`prepare_pair` alignment asymmetry with `with_swing_smt=True`:**
- Files: `cisd_analysis.py` lines 367–381
- Why fragile: `prepare()` is called on each instrument's full resampled frame (unrestricted), then the index intersection is computed for the SMT scan only. The returned `df_nq`/`df_es` cover more bars than the SMT scan saw. A future analysis that assumes SMT-tagged CISDs were scanned against aligned peer data will be correct, but the annotation silently applies "no SMT" to out-of-intersection bars rather than "data unavailable". The distinction is not flagged.
- Safe modification: This is the intended design per CLAUDE.md. Document the behavior in a comment at the intersection computation (line 373).

## Scaling Limits

**No concern for current data size.** The parquet files are 1-minute OHLCV for NQ and ES. At the current scale (daily runs, four timeframes, two instruments), runtimes are measured in seconds. Performance concerns above become relevant if the dataset is extended to include additional instruments or finer granularity (e.g., tick data).

## Dependencies at Risk

**External SMT package at `_SMT_PKG_PATH`:**
- Risk: The SMT dependency is an unversioned local checkout at a hardcoded WSL path. There is no requirements file, lockfile, or version pin for it.
- Impact: `smt_cisd` analysis and `build_forward_returns.py` break silently if the path moves or the SMT package API changes.
- Migration plan: Publish the SMT package as an installable wheel or add it as a git submodule with a pinned commit hash. Reference via `pip install -e /path/to/SMT` and add to `requirements.txt`.

**No `requirements.txt` or `pyproject.toml`:**
- Risk: The only way to determine which packages are required is to read the imports. The `.venv/` is present but not documented.
- Impact: Reproducing the environment on another machine requires manual package identification.
- Migration plan: Add `requirements.txt` with pinned versions of `pandas`, `numpy`, `matplotlib`, `pyarrow` (for parquet), and optionally `plotly` (referenced in the HTML output via CDN, not installed locally).

## Missing Critical Features

**No CI pipeline:**
- Problem: There is no `.github/workflows/`, `.gitlab-ci.yml`, or equivalent. Tests run only manually.
- Blocks: Automated validation that new analyses don't break existing ones. Undetected regressions in annotation logic.

**No test for `build_csv_rows` with `sweep` or `sssf_swing` keys:**
- Problem: The test `test_build_csv_rows_supports_new_research_keys` in `test_research_extensions.py` (line 297) tests `cisd_fvg`, `fvg_hold`, `cisd_fvg_interaction`, `sweep`, and `sssf_swing`, but does not verify that the dead `smt_cisd` branch at line 1184 is never reached. If a future refactor removes the earlier `smt_cisd` branch at line 1161, the dead branch would silently activate.

## Test Coverage Gaps

**`compute_basic`, `compute_mc`, `compute_significance`, `compute_wick`, `compute_combined` have no unit tests:**
- What's not tested: The five "per-TF" barrier analyses that appear in the left-half per-timeframe figure. `test_research_extensions.py` only covers the newer standalone analyses added later.
- Files: `cisd_analysis.py` lines 449–544
- Risk: Changes to `barrier_hit()` or the direction/prev_* shift logic could silently alter these results.
- Priority: Medium — these are the core Markov/barrier analyses the project is named after.

**`build_csv_rows` CSV row shape not verified for `fvg_hold`:**
- What's not tested: `test_build_csv_rows_supports_new_research_keys` does not assert the row count or `Rate_pct` values for `fvg_hold`. The `fvg_hold` key uses `d["held"]` rather than `d["runs"]` for the rate column, which is unique among the CSV serialization branches.
- Files: `cisd_analysis.py` lines 1171–1175, `tests/test_research_extensions.py` lines 297–315
- Risk: A rename of `"held"` to `"runs"` in `compute_fvg_hold` would silently produce zero rates in the CSV.
- Priority: Low.

**No integration test for full `main()` pipeline:**
- What's not tested: No test exercises the end-to-end path from `load_1m` through `prepare_pair` through `build_figure` through `fig.savefig`. If the parquet schema changes (e.g., column renamed from `DateTime_ET` to `datetime_et`), the failure would only be caught when running `python cisd_analysis.py` manually.
- Files: `cisd_analysis.py` lines 1298–1380
- Risk: Silent breakage on data schema changes.
- Priority: Low — acceptable given the research-tool nature of the project, but worth a smoke test.

## Repository Hygiene

**25 generated output files committed to git:**
- Files: All files under `output/` in `git ls-files`
- Issue: PNGs (up to 772KB each), CSVs, and a 2.8MB HTML file are committed and will create a new blob for every regeneration. The `forward_returns.html` alone is 2.8MB of embedded JSON.
- Impact: Repo size grows with each analysis run that is committed. Git history becomes difficult to diff meaningfully.
- Fix approach: Add `output/` to `.gitignore`. If output artifacts need to be shared, use a separate release mechanism (GitHub Releases, shared drive) rather than git tracking.

**Leftover pre-merge artifact:**
- Files: `tests/test_research_extensions.py.premerge`
- Issue: A `.premerge` backup of the test file is present in the working tree but not tracked in git (shown as `??` in `git status`). It is likely a merge conflict resolution artifact.
- Fix approach: Delete `tests/test_research_extensions.py.premerge`.

**`.gitignore` case mismatch for data files:**
- Files: `.gitignore` lines 10–11
- Issue: The ignore patterns are `Data/*.parquet` and `Data/*.csv` (capital D), but the actual directory is `data/` (lowercase). On Linux/WSL filesystems (case-sensitive), these patterns never match. Parquet files are not currently tracked, but the safeguard is ineffective.
- Fix approach: Change to `data/*.parquet` and `data/*.csv` (lowercase d).

---

*Concerns audit: 2026-06-12*
