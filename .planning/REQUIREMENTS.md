# Requirements: CISD-Markov Research Engine

**Defined:** 2026-07-10
**Core Value:** A reported edge can be trusted — every published rate is sample-size gated, carries a confidence interval, and is confirmed out-of-sample.

## v1 Requirements

Requirements for milestone v2.0. Each maps to a roadmap phase.

### Advanced Validation

- [x] **MHT-01**: Multiple-comparisons / data-snooping correction (FDR control, e.g. Benjamini-Hochberg) is applied across the full bucket grid reported by the validation harness — a "confirmed" edge accounts for how many buckets were tested, not just its own single-bucket confidence interval.
- [x] **WF-01**: Walk-forward / rolling-window validation supplements the single sacred discovery/OOS holdout — edges must be re-confirmed as robust across multiple sequential train→test windows, not just one fixed split.

### Research Extensions

- [x] **RES-04**: An explicit reversal barrier for the `post_cisd_context` `failed_gap_against` bucket measures whether `candle[0]`'s opposite extreme is hit first, not just a depressed continuation rate.
- [x] **RES-05**: The validation manifest is regenerated end-to-end under the new methodology so `post_cisd_context` and `candle1_followthrough` — never fully validated after Phase 5 — carry real, corrected, walk-forward-confirmed rates.

### Modeling

- [ ] **ML-01**: `post_cisd_ml`, a small ML model over the post-CISD context features, is built only if RES-05's corrected results show the discrete tags carry a real, durable effect.

## v2 Requirements

None — this milestone completes the acknowledged v2 backlog from v1.0 closeout.

## Out of Scope

Explicitly excluded for this milestone. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Live signaling / alerting / trading system | Historical-research tool, not a production trading system (carried from v1.0) |
| Instruments beyond NQ and ES | Milestone boundary; findings and pipeline stay NQ/ES-specific |
| Phase 3 human QA sign-off / Phase 5 formal verification report | Carried-forward process debt from v1.0 closeout; user chose to prioritize research/methodology work this milestone instead — tracked in `.planning/STATE.md` Deferred Items |
| Exhaustive implementation of every correction/walk-forward method | One correction method and one walk-forward scheme is sufficient to meet MHT-01/WF-01; exact method choice is a phase-planning decision |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MHT-01 | Phase 6 | Complete |
| WF-01 | Phase 6 | Complete |
| RES-04 | Phase 7 | Complete |
| RES-05 | Phase 7 | Complete |
| ML-01 | Phase 8 | Pending |

**Coverage:**

- v1 requirements: 5 total
- Mapped to phases: 5
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-10*
*Last updated: 2026-07-10 after roadmap creation (Phases 6–8 mapped)*
