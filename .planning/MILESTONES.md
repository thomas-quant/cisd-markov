# Project Milestones: CISD-Markov Research Engine

## v1.0 Validated Research Engine (Shipped: 2026-07-10)

**Delivered:** A reproducible, validation-gated CISD research engine with honest discovery/OOS reporting and two new post-CISD studies.

**Phases completed:** 1–5 (13 plans, 10 recorded tasks)

**Key accomplishments:**

- Pinned the runtime, added CI and deterministic tests, and made SMT optional across entry points.
- Locked published behavior with characterization/unit tests before refactoring.
- Added sacred date holdout tooling, Wilson confidence intervals, minimum-n gating, and durable per-slice manifests.
- Republished existing findings with 616 confirmed, 48 not-confirmed, and 88 below-n buckets across 752 observations.
- Split the monolith into focused modules, centralized the registry, vectorized hot loops, and added two post-CISD studies.

**Stats:**

- 5 phases, 13 plans, 10 recorded tasks
- 90 files changed; 18,217 additions and 435 deletions during the milestone range
- 23 days from first Phase 1 commit (2026-06-12) to Phase 5 completion (2026-07-04)

### Known Gaps / Verification Overrides

- Phase 3 requires five documented human QA checks in `03-VERIFICATION.md`.
- Phase 5 has no formal verification report.
- `VALID-01` through `VALID-05` were implemented and Phase 2 verification passed, but their source checklist and traceability rows were still Pending at closeout; the archive normalizes their outcome to complete.

**Known verification overrides:** 2 (see `.planning/STATE.md` Deferred Items).

**What's next:** Define a fresh milestone and resolve the carried verification exceptions.

---
