# Phase 4: Test-Gated Modular Refactor - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-14
**Phase:** 4-Test-Gated Modular Refactor
**Areas discussed:** Post-split import surface, compute_significance fix, Vectorization scope

---

## Post-split import surface

| Option | Description | Selected |
|--------|-------------|----------|
| Re-export shim | cisd_analysis.py re-exports all currently-imported symbols from the new modules. Zero changes to scripts/ or tests/. cisd_analysis acts as thin orchestrator + namespace shim. | ✓ |
| Full clean split | Update all 6 test files + 2 scripts to import from cisd_data / cisd_barriers / cisd_charts directly. cisd_analysis.py becomes purely a CLI entry point. | |

**User's choice:** Re-export shim
**Notes:** Keeps the phase scope tight — zero friction on the consumer side. The thin-orchestrator intent is satisfied structurally (logic is gone, only re-exports remain).

---

## compute_significance fix

| Option | Description | Selected |
|--------|-------------|----------|
| Document it | Add a clear docstring explaining the intentional stricter close-past-prev-high/low definition rather than cisd_type. Lightweight. | ✓ |
| Unify via cisd_type_strict | Introduce cisd_type_strict column in prepare() and have compute_significance consume it consistently. Changes the pipeline. | |

**User's choice:** Document it
**Notes:** Preserves the existing semantic distinction. No change to prepare() or the characterization test baseline.

---

## Vectorization scope

| Option | Description | Selected |
|--------|-------------|----------|
| Strictly scoped | Only the iterrows/get_loc pattern: _annotate_cisd_research outer loop + all 14 compute_* functions. What REFAC-03 explicitly names. | ✓ |
| Full hot-path sweep | Also tackle _has_directional_sweep (rolling min/max) and _annotate_swing_smt_from_events (searchsorted). More work, bigger diff. | |

**User's choice:** Strictly scoped
**Notes:** Keeps REFAC-03 to its stated scope. Sweep/SMT helpers deferred to a future performance pass.

---

## Claude's Discretion

- Exact module-level `__all__` lists or re-export style in new modules and shim
- Where `ANALYSIS_META` lives (inside `cisd_barriers.py` or peer to `ANALYSES`)
- Exact column names and integration pattern for vectorized annotation pass
- Whether registry entries use dict of dicts or dataclass/NamedTuple

## Deferred Ideas

- **Vectorize `_has_directional_sweep`** — double-nested loop, rolling min/max precompute; future performance pass
- **Vectorize `_annotate_swing_smt_from_events`** — O(n×m) inner loop; future performance pass
- **Full clean import split** — updating all consumers to import from new modules directly; deferred in favor of re-export shim
