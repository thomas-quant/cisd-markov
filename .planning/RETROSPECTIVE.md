# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Validated Research Engine

**Shipped:** 2026-07-10
**Phases:** 5 | **Plans:** 13 | **Sessions:** not tracked

### What Was Built

- Reproducible runtime, optional SMT integration, CI, deterministic execution, and behavior-locking tests.
- A sacred discovery/OOS validation harness with Wilson confidence intervals, minimum-n gating, and durable manifests.
- Republished existing CISD findings plus new `candle[1]` and multi-bar post-CISD analyses on the validated engine.

### What Worked

- Locking behavior before the modular refactor prevented numerical drift.
- Per-slice manifests and explicit verdict labels made validation outcomes inspectable and hard to overwrite accidentally.
- A central analysis registry kept new research studies consistently wired through charts and validation output.

### What Was Inefficient

- Traceability checkboxes were not updated after Phase 2 despite passing verification.
- Human QA for Phase 3 and formal verification for Phase 5 were left incomplete at closeout.

### Patterns Established

- Treat in-sample results as hypotheses; report discovery, sample size, CI, and OOS verdict together.
- Use characterization tests as a prerequisite for behavior-preserving refactors.

### Key Lessons

1. Verification artifacts and requirements traceability must be completed in the same phase that implements the work.
2. Structural protections such as per-slice output paths are more reliable than relying on a one-time operational instruction.

### Cost Observations

- Model mix: not tracked.
- Sessions: not tracked.
- Notable: the phased test-gated workflow supported a large refactor without changing locked research results.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | not tracked | 5 | Introduced reproducibility, validation gates, and test-gated refactoring |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 94 behavior/unit tests reported during refactor | not tracked | Wilson CI implementation |

### Top Lessons (Verified Across Milestones)

1. No cross-milestone trend exists yet; establish one after the next milestone.
