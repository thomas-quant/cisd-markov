# Phase 4: Test-Gated Modular Refactor - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase splits the 1,380-line god-file `cisd_analysis.py` into focused modules, consolidates the 4-edit standalone-analysis registry into one source of truth, and vectorizes the `iterrows`/`get_loc` hot loops — with every characterization and unit test still green throughout. It delivers:

1. **04-01 God-file split:** `cisd_analysis.py` moves logic into `cisd_data.py` (load/resample/prepare), `cisd_barriers.py` (barrier logic, compute functions), and `cisd_charts.py` (chart functions). `cisd_analysis.py` becomes a thin CLI orchestrator + re-export shim. (REFAC-01)
2. **04-02 Registry consolidation + correctness debt:** The 4-synchronized-edit `STANDALONE_KEYS`/`FILENAMES`/`base_h` pattern is replaced by a single `ANALYSIS_META` dict. Dead `smt_cisd` branch in `build_csv_rows` removed. `compute_significance`'s `cisd_type` bypass documented. (REFAC-02/04)
3. **04-03 Vectorization:** The `iterrows`/`get_loc` pattern in `_annotate_cisd_research` + all 14 `compute_*` functions is replaced with the `np.flatnonzero` + array-indexing pattern from `build_expectancy.py`. (REFAC-03)

**Explicitly NOT in this phase:** new research analyses (Phase 5), multiple-comparisons correction or walk-forward validation (v2), vectorizing the sweep/SMT annotation helpers (deferred).

</domain>

<decisions>
## Implementation Decisions

### Post-split import surface (REFAC-01)
- **D-01:** `cisd_analysis.py` acts as a **re-export shim** after the split. It re-exports all symbols currently imported by scripts/ and tests/ (`load_1m`, `prepare_pair`, `INSTRUMENTS`, `TIMEFRAMES`, `DATA_DIR`, `MAX_CONSEC`, `_SMT_PKG_PATH`, `_count_consecutive`, `_annotate_swing_smt_from_events`, `compute_basic`, etc.) from the new modules. **Zero changes required in the 6 test files or 2 scripts.** The thin-orchestrator intent is satisfied structurally — the logic is gone, only re-exports remain.

### compute_significance fix (REFAC-04)
- **D-02:** Fix is **documentation only** — add a clear docstring to `compute_significance` explaining that it intentionally uses a stricter close-past-prev-high/low definition rather than the precomputed `cisd_type` column, and why. No `cisd_type_strict` column introduced; `prepare()` is not touched. The semantic distinction is preserved as-is.

### Vectorization scope (REFAC-03)
- **D-03:** Vectorization is **strictly scoped** to the `iterrows`/`get_loc` pattern as named in the requirement: the outer loop in `_annotate_cisd_research` + all 14 `compute_*` functions. `_has_directional_sweep` (double-nested loop) and `_annotate_swing_smt_from_events` (O(n×m) inner loop) are **deferred** — they are not in REFAC-03 and are left for a future pass.

### Claude's Discretion
- Exact module-level `__all__` lists (or re-export style) in the new modules and in the shim `cisd_analysis.py`
- Where `ANALYSIS_META` lives (inside `cisd_barriers.py` or as a peer constant alongside `ANALYSES`) — must satisfy "one source of truth" for all 4 synchronized-edit sites
- Exact column names and integration pattern for the vectorized annotation pass (accumulate into lists, bulk-assign — per CONCERNS.md guidance)
- Whether the registry consolidation uses a dict of dicts or a dataclass/NamedTuple per entry

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & locked decisions
- `.planning/ROADMAP.md` §"Phase 4: Test-Gated Modular Refactor" — goal, 5 success criteria, 3 plan splits (04-01 split, 04-02 registry+debt, 04-03 vectorize)
- `.planning/REQUIREMENTS.md` §"Refactor (Test-Gated, Behavior-Preserving)" — REFAC-01 through REFAC-04 exact wording
- `.planning/PROJECT.md` §"Key Decisions" — behavior-preserving constraint, test-gated, characterization tests lock numbers before anything moves

### Codebase audit (the source of what to fix)
- `.planning/codebase/CONCERNS.md` — full descriptions of: god-file architecture, dead `smt_cisd` branch in `build_csv_rows` (lines 1161, 1184), `compute_significance` `cisd_type` bypass (lines 483–499), `STANDALONE_KEYS`/`FILENAMES`/`base_h` fragile 4-edit registry (lines 1199–1202, 1260–1261, 1300–1310, 1357–1367), `iterrows`/`get_loc` hot loops (62 occurrences), `_annotate_cisd_research` outer loop (lines 208–244)
- `.planning/codebase/ARCHITECTURE.md` — one-directional data flow, component responsibilities table, layer overview

### Vectorization reference implementation
- `scripts/build_expectancy.py` — `build_event_r_multiples()` uses `np.flatnonzero` + array indexing throughout; this is the in-repo reference pattern for REFAC-03

### Tests that must stay green (behavior-preservation gate)
- `tests/test_characterization.py` — locks full-history headline numbers; MUST pass unchanged after every plan in this phase
- `tests/test_core_compute.py` — unit tests for `compute_basic`, `compute_mc`, `compute_significance`, `compute_wick`, `compute_combined`
- `tests/test_research_extensions.py` — covers newer standalone analyses + `build_csv_rows` key dispatch
- `tests/test_validation_harness.py` — 14 tests on the harness (must not be broken by module splits)
- `tests/test_swing_smt_integration.py` — imports `_SMT_PKG_PATH`, `_annotate_swing_smt_from_events` directly; re-exports must cover these

### Current importers (re-export shim must cover all of these)
- `scripts/build_forward_returns.py` line 18: `from cisd_analysis import INSTRUMENTS, TIMEFRAMES, load_1m, prepare_pair, MAX_CONSEC, _count_consecutive`
- `scripts/build_expectancy.py` line 39: `from cisd_analysis import INSTRUMENTS, TIMEFRAMES, load_1m, prepare_pair`
- `tests/test_characterization.py` lines 17–18: `import cisd_analysis` + `from cisd_analysis import DATA_DIR, TIMEFRAMES, _SMT_PKG_PATH`
- `tests/test_swing_smt_integration.py` lines 1, 5: `import cisd_analysis` + `from cisd_analysis import _SMT_PKG_PATH, _annotate_swing_smt_from_events`
- `tests/test_core_compute.py` line 67: `import cisd_analysis`
- `tests/test_determinism.py` line 20: `import cisd_analysis`
- `tests/test_research_extensions.py` line 4: `import cisd_analysis`
- `tests/test_validation_harness.py` line 8: `import cisd_analysis`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/build_expectancy.py:build_event_r_multiples()`** — the reference implementation for REFAC-03; uses `np.flatnonzero(mask)` to get CISD integer positions, then indexes into `high_arr`, `low_arr`, `close_arr` NumPy arrays directly. The compute-function vectorization mirrors this pattern.
- **`cisd_analysis.py:build_csv_rows()`** — the 4-edit registry pattern this phase consolidates; `STANDALONE_KEYS` (line ~1302) and `FILENAMES` (line ~1307) in `main()`, `base_h` in `build_figure` and `build_standalone_figure` — all four sites must be driven by the single `ANALYSIS_META` dict after REFAC-02.
- **`cisd_analysis.py:ANALYSES`** — the existing `{key: (label, compute_fn, chart_fn)}` dict; REFAC-02 extends its entries with `standalone`, `height`, `filename` fields (or creates a parallel `ANALYSIS_META` dict) to eliminate the 4-edit pattern.

### Established Patterns
- **Test-gated sequencing:** Run `pytest` after each plan (04-01, 04-02, 04-03) before committing. Characterization tests fail immediately if a number moves.
- **Additive / non-breaking style:** Prior phases never removed public symbols. The re-export shim continues this — `cisd_analysis` stays importable with the same public API surface.
- **CONCERNS.md column accumulation guidance:** "Accumulate per-row results in plain Python lists/dicts indexed by integer position, then bulk-assign to columns after the loop" — this is the implementation path for vectorizing `_annotate_cisd_research`.

### Integration Points
- **04-01 → scripts/tests:** Zero changes needed in scripts/ or tests/ (D-01 re-export shim). After 04-01, `pytest` must be green with no import errors.
- **04-02 → `build_csv_rows` and `main()`:** `ANALYSIS_META` replaces the 4 synchronized sites. The dead `smt_cisd` elif branch at line 1184 is removed (only `("sweep", "sssf_swing")` remain in that branch).
- **04-03 → `_annotate_cisd_research` + 14 `compute_*` functions:** Integer-position precompute replaces `df.index.get_loc(ts)` per row. Numbers must be bit-identical; characterization tests verify this automatically.

</code_context>

<specifics>
## Specific Ideas

- The re-export shim in `cisd_analysis.py` should be explicit (`from cisd_data import load_1m, prepare_pair, ...`) rather than wildcard (`from cisd_data import *`) so the public API is auditable.
- The `ANALYSIS_META` registry should live at module level (not inside `main()`) so it can be imported and inspected by tests or future consumers.
- Vectorization must produce bit-identical numbers — the characterization tests are the automatic verification gate; no manual output comparison needed.
- `compute_significance` docstring should explain: (a) what the stricter definition is (close must pass prev high/low, not just any close), (b) why `cisd_type` is not used (different semantic intent), and (c) that this is intentional, not a bug.

</specifics>

<deferred>
## Deferred Ideas

- **Vectorize `_has_directional_sweep`** (double-nested loop, rolling min/max precompute) — explicitly out of REFAC-03 scope; future performance pass
- **Vectorize `_annotate_swing_smt_from_events`** (O(n×m) inner loop, searchsorted index) — same; deferred
- **Full clean import split** (updating 6 test files + 2 scripts to import from new modules directly) — rejected in favor of re-export shim for this phase; could be done as a follow-up cleanup if desired

None of the above stalls planning — they are intentional boundaries.

</deferred>

---

*Phase: 4-Test-Gated Modular Refactor*
*Context gathered: 2026-06-14*
