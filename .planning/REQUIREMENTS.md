# Requirements: CISD-Markov Research Engine

**Defined:** 2026-06-12
**Core Value:** A reported edge can be trusted — every published rate is sample-size gated, carries a confidence interval, and is confirmed out-of-sample.

## v1 Requirements

Requirements for this milestone. Each maps to a roadmap phase. Sequenced by dependency; the whole milestone is test-gated (current numbers locked before anything can move them).

### Infra (Reproducibility)

- [ ] **INFRA-01**: A dependency manifest (`requirements.txt` and/or `pyproject.toml`) pins the runtime packages so the engine reproduces on another machine
- [ ] **INFRA-02**: The SMT package location is read from an environment variable with a documented default, replacing the hardcoded WSL path
- [ ] **INFRA-03**: Every entry point degrades gracefully when SMT is unavailable (`build_forward_returns.py` reaches parity with `build_expectancy.py`'s fallback)
- [ ] **INFRA-04**: CI runs the test suite automatically on push
- [ ] **INFRA-05**: Tests run from any working directory (conftest/pythonpath) and computed results are deterministic (no wall-clock or RNG dependence)
- [ ] **INFRA-06**: Generated `output/` artifacts are no longer committed, and the `data/` gitignore case mismatch is fixed

### Tests (Behavior Lock)

- [ ] **TEST-01**: Characterization tests lock the current published headline numbers before any refactor or harness change can move them
- [ ] **TEST-02**: The previously-untested core analyses (`compute_basic`, `compute_mc`, `compute_significance`, `compute_wick`, `compute_combined`) have unit tests

### Validation Harness

- [ ] **VALID-01**: A sacred date holdout splits history into discovery (oldest ~70%) and OOS (newest ~30%); discovery runs operate on the train slice only
- [ ] **VALID-02**: OOS confirmation is a separate, deliberate, single-evaluation path — the tool defaults to discovery-on-train so the holdout stays sacred
- [ ] **VALID-03**: Every reported barrier/hit rate carries a binomial confidence interval
- [ ] **VALID-04**: Reported rates are sample-size gated — buckets below a minimum-n threshold are flagged or suppressed rather than reported as findings
- [ ] **VALID-05**: A results manifest records n, confidence interval, and IS/OOS status for each reported bucket

### Re-Validation (Existing Findings)

- [ ] **REVAL-01**: The current README headline findings are re-run through the harness on the discovery (train) slice
- [ ] **REVAL-02**: Findings that survive discovery are confirmed once on the sacred OOS holdout
- [ ] **REVAL-03**: The README is republished with n + CI + OOS status per finding, and findings that do not survive are retired or labeled

### Refactor (Test-Gated, Behavior-Preserving)

- [ ] **REFAC-01**: `cisd_analysis.py` is split into `cisd_data` / `cisd_barriers` / `cisd_charts` modules with a thin orchestrator
- [ ] **REFAC-02**: The standalone-analysis registry is consolidated into one source of truth (no more 4 synchronized edits to add an analysis)
- [ ] **REFAC-03**: The `iterrows`/`get_loc` hot loops (annotation pass + compute functions) are vectorized following the `np.flatnonzero` pattern from `build_expectancy.py`
- [ ] **REFAC-04**: Audit-surfaced correctness debt is fixed (dead `smt_cisd` branch in `build_csv_rows`; `compute_significance`'s bypass of `cisd_type` is documented or unified)

### New Research

- [ ] **RES-01**: A `candle[1]` follow-through analysis measures whether the bar after a CISD predicts continuation (close in CISD direction; close beyond `candle[1]`'s wick)
- [ ] **RES-02**: A multi-bar post-CISD context analysis measures the `candle2_gap_context` / `post_cisd_reversal_context` regime (failed `candle[1]` + gap on `candle[2]`)
- [ ] **RES-03**: New studies report through the validation harness (n + CI, IS/OOS) from the start — no new in-sample-only findings are produced

## v2 Requirements

Acknowledged but deferred beyond this milestone.

### Advanced Validation

- **MHT-01**: Multiple-comparisons / data-snooping correction (Benjamini-Hochberg, Bonferroni, or White's Reality Check) across the bucket grid
- **WF-01**: Walk-forward / rolling-window validation so edges must persist across multiple train→test windows

### Modeling

- **ML-01**: `post_cisd_ml` — a small ML model over post-CISD context features, once the discrete tags prove promising

## Out of Scope

Explicitly excluded for this milestone. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Live signaling / alerting / trading system | This is a historical-research tool, not a production trading system |
| Instruments beyond NQ and ES | Milestone boundary; current findings and pipeline are NQ/ES-specific |
| Output artifact release pipeline (GitHub Releases, shared drive) | This round only stops committing `output/`; productizing artifact distribution is unnecessary |
| Multiple-comparisons correction (this milestone) | Foundational round ships CIs + n-gating; correction is the next rigor tier (see MHT-01) |
| Walk-forward validation (this milestone) | Foundational round is a single sacred holdout split (see WF-01) |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | — | Pending |
| INFRA-02 | — | Pending |
| INFRA-03 | — | Pending |
| INFRA-04 | — | Pending |
| INFRA-05 | — | Pending |
| INFRA-06 | — | Pending |
| TEST-01 | — | Pending |
| TEST-02 | — | Pending |
| VALID-01 | — | Pending |
| VALID-02 | — | Pending |
| VALID-03 | — | Pending |
| VALID-04 | — | Pending |
| VALID-05 | — | Pending |
| REVAL-01 | — | Pending |
| REVAL-02 | — | Pending |
| REVAL-03 | — | Pending |
| REFAC-01 | — | Pending |
| REFAC-02 | — | Pending |
| REFAC-03 | — | Pending |
| REFAC-04 | — | Pending |
| RES-01 | — | Pending |
| RES-02 | — | Pending |
| RES-03 | — | Pending |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 0 (roadmap pending)
- Unmapped: 23 ⚠️

---
*Requirements defined: 2026-06-12*
*Last updated: 2026-06-12 after initial definition*
