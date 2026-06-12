# Roadmap: CISD-Markov Research Engine

## Overview

This milestone turns a single-pass, in-sample filter-mining script into a reproducible, test-gated research engine whose findings carry honest statistics. The journey is strictly dependency-ordered: first we make the engine reproduce deterministically and lock the current published numbers behind characterization tests (so nothing can move them silently), then we build the validation harness (sacred date holdout + confidence intervals + sample-size gating). With the harness in place we re-validate the existing README findings as hypotheses and republish them honestly. The modular refactor — safe only once behavior is locked — splits the god-file and vectorizes the hot loops without moving any number. Finally, new CISD research is conducted on the validated engine, reporting through the harness from the start so no new in-sample-only findings are ever produced.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Reproducibility Foundation & Behavior Lock** - Pin the environment, run tests in CI deterministically, and lock current published numbers before anything can move them
- [ ] **Phase 2: Validation Harness** - Sacred date holdout, binomial confidence intervals, and sample-size gating on every reported rate
- [ ] **Phase 3: Re-Validate & Republish Existing Findings** - Re-run README headline results through the harness and republish with n + CI + OOS status
- [ ] **Phase 4: Test-Gated Modular Refactor** - Split the god-file, consolidate the registry, and vectorize the hot loops with all characterization tests still green
- [ ] **Phase 5: New CISD Research on the Validated Engine** - Add `candle[1]` follow-through and multi-bar post-CISD context studies, reporting through the harness from the start

## Phase Details

### Phase 1: Reproducibility Foundation & Behavior Lock

**Goal**: The engine reproduces deterministically on any machine, runs its tests in CI, and the current published headline numbers are locked so no later change can move them silently.
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, TEST-01, TEST-02
**Success Criteria** (what must be TRUE):

  1. A fresh checkout reproduces the runtime from a pinned manifest (`requirements.txt`/`pyproject.toml`), reads the SMT path from a documented env var, and every entry point — including `build_forward_returns.py` — degrades gracefully when SMT is absent
  2. The pytest suite runs automatically on push via CI, succeeds from any working directory, and computed numbers are identical across repeated runs (no wall-clock or RNG dependence)
  3. Generated `output/` artifacts are no longer tracked in git and the `data/` gitignore case mismatch is fixed
  4. Characterization tests assert the current README headline numbers and fail if any of those numbers change
  5. `compute_basic`, `compute_mc`, `compute_significance`, `compute_wick`, and `compute_combined` each have unit tests over their barrier counts

**Plans**: 3 plans
Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Dependency manifest, env-var SMT path, and graceful SMT fallback across all entry points (INFRA-01/02/03)
- [ ] 01-02-PLAN.md — CI workflow, conftest/pythonpath, determinism check, and repo hygiene (output/ untracked, gitignore fix) (INFRA-04/05/06)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 01-03-PLAN.md — Characterization tests on README headline numbers + unit tests for the five core compute functions (TEST-01/02)

### Phase 2: Validation Harness

**Goal**: Every reported rate can be gated by sample size, carries a confidence interval, and lives inside a sacred discovery/OOS holdout that the tooling defaults to keeping sacred.
**Depends on**: Phase 1
**Requirements**: VALID-01, VALID-02, VALID-03, VALID-04, VALID-05
**Success Criteria** (what must be TRUE):

  1. A chronological date holdout splits history into discovery (oldest ~70%) and OOS (newest ~30%), and discovery runs operate on the train slice only
  2. OOS confirmation is a separate, deliberate, single-evaluation path; the default run path is discovery-on-train so the holdout stays sacred
  3. Every reported barrier/hit rate displays a binomial confidence interval
  4. Buckets below a minimum-n threshold are flagged or suppressed rather than reported as findings
  5. A results manifest records n, confidence interval, and IS/OOS status for each reported bucket

**Plans**: 2 plans

Plans:

- [ ] 02-01: Sacred date holdout split + discovery-on-train default + single-evaluation OOS path (VALID-01/02)
- [ ] 02-02: Binomial confidence intervals, minimum-n gating, and the n/CI/IS-OOS results manifest (VALID-03/04/05)

### Phase 3: Re-Validate & Republish Existing Findings

**Goal**: The current README findings are treated as hypotheses, re-run through the harness on the discovery slice, confirmed once on the sacred OOS holdout, and republished honestly — survivors and casualties both labeled.
**Depends on**: Phase 2 (requires the harness; independent of and reorderable with Phase 4)
**Requirements**: REVAL-01, REVAL-02, REVAL-03
**Success Criteria** (what must be TRUE):

  1. The current README headline findings are re-run through the harness on the discovery (train) slice with n + CI attached
  2. Findings that survive discovery are confirmed exactly once on the sacred OOS holdout
  3. The republished README shows n + CI + IS/OOS status per finding
  4. Findings that do not survive OOS are retired or explicitly labeled as not-confirmed, never silently dropped

**Plans**: 2 plans

Plans:

- [ ] 03-01: Re-run README headline findings on the discovery slice; confirm survivors once on the sacred OOS holdout (REVAL-01/02)
- [ ] 03-02: Republish README with per-finding n + CI + IS/OOS status; retire or label non-survivors (REVAL-03)

### Phase 4: Test-Gated Modular Refactor

**Goal**: The 1,380-line god-file is split into focused modules with a single registry source of truth and vectorized hot loops, with every characterization and unit test still green.
**Depends on**: Phase 1 (characterization tests must exist first; independent of and reorderable with Phases 2-3)
**Requirements**: REFAC-01, REFAC-02, REFAC-03, REFAC-04
**Success Criteria** (what must be TRUE):

  1. `cisd_analysis.py` imports from `cisd_data` / `cisd_barriers` / `cisd_charts` and acts as a thin orchestrator
  2. Adding a standalone analysis touches one registry source of truth — no more four synchronized edits
  3. The `iterrows`/`get_loc` hot loops in the annotation pass and compute functions are replaced with the `np.flatnonzero` vectorized pattern and produce identical numbers
  4. The dead `smt_cisd` branch in `build_csv_rows` is removed and `compute_significance`'s `cisd_type` bypass is documented or unified
  5. All characterization and unit tests from Phase 1 still pass after the refactor

**Plans**: 3 plans

Plans:

- [ ] 04-01: Split god-file into `cisd_data` / `cisd_barriers` / `cisd_charts` with a thin orchestrator (REFAC-01)
- [ ] 04-02: Consolidate the standalone-analysis registry into one source of truth and fix audit-surfaced correctness debt (REFAC-02/04)
- [ ] 04-03: Vectorize the annotation + compute hot loops following the `build_expectancy.py` `np.flatnonzero` pattern (REFAC-03)

### Phase 5: New CISD Research on the Validated Engine

**Goal**: Two new post-CISD studies ship on the validated engine, reporting through the harness from the start — no new in-sample-only findings are ever produced.
**Depends on**: Phases 2 and 4 (requires the harness for honest reporting and the refactored engine for safe extension)
**Requirements**: RES-01, RES-02, RES-03
**Success Criteria** (what must be TRUE):

  1. A `candle[1]` follow-through analysis measures whether the bar after a CISD predicts continuation (close in CISD direction; close beyond `candle[1]`'s wick)
  2. A multi-bar post-CISD context analysis measures the `candle2_gap_context` / `post_cisd_reversal_context` regime (failed `candle[1]` + gap on `candle[2]`)
  3. Both new studies report n + CI and IS/OOS status through the validation harness from the start
  4. No new finding is published in-sample-only

**Plans**: 2 plans

Plans:

- [ ] 05-01: `candle[1]` follow-through analysis wired through the harness (RES-01, RES-03)
- [ ] 05-02: Multi-bar post-CISD context analysis wired through the harness (RES-02, RES-03)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5.
Phases 3 and 4 both depend only on Phases 1-2 and are reorderable/parallelizable relative to each other; Phase 5 requires both the harness (Phase 2) and the refactor (Phase 4).

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Reproducibility Foundation & Behavior Lock | 1/3 | In Progress|  |
| 2. Validation Harness | 0/2 | Not started | - |
| 3. Re-Validate & Republish Existing Findings | 0/2 | Not started | - |
| 4. Test-Gated Modular Refactor | 0/3 | Not started | - |
| 5. New CISD Research on the Validated Engine | 0/2 | Not started | - |
