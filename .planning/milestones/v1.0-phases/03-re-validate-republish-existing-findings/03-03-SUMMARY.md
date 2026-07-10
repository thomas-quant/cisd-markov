---
phase: 03-re-validate-republish-existing-findings
plan: "03"
subsystem: documentation
tags: [readme, republish, discovery-rates, wilson-ci, oos-verdicts, honest-stats]

# Dependency graph
requires:
  - phase: 03-re-validate-republish-existing-findings/03-02
    provides: output/validation_findings.csv — 752-row labeled findings table

provides:
  - README.md — republished with discovery rates, n, 95% Wilson CI, IS/OOS verdict badges per bucket

affects:
  - README.md — §1–§8 rewritten; no compute path changes; all characterization tests still pass

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Discovery-slice rates replace full-history rates in all README tables (D-04)"
    - "Three verdict tokens: confirmed → ✓ CONFIRMED, not-confirmed → ✗ NOT CONFIRMED, below-n → below-n / not a finding"
    - "below-n and not-confirmed are visibly distinct; neither is dropped (D-03, D-06)"
    - "Methodology note under Key Findings explains Wilson CI, OOS boundary, and the three verdicts"

key-files:
  created: []
  modified:
    - README.md

key-decisions:
  - "Both tasks' deliverables written atomically to README.md in a single commit (tasks only modify README.md)"
  - "§3 Combined section uses per-TF subsections rather than a single unwieldy table to handle below-n Daily cells cleanly"
  - "§8 SMT table retains no-SMT rate as comparison column; adds Verdict column for w/ SMT bucket specifically"
  - "Data-dependent characterization tests passed (94 passed in 889s) — no computed numbers altered"

requirements-completed: [REVAL-03]

# Metrics
duration: ~30min
completed: 2026-06-13
---

# Phase 3 Plan 03: Republish README with Honest Statistics Summary

**README §1–§8 republished: discovery rates replace full-history numbers; every bucket now carries n + 95% Wilson CI + IS/OOS verdict; bearish Daily failures labeled ✗ NOT CONFIRMED; below-n buckets retained and visibly distinct; 94 tests passed**

## Performance

- **Duration:** ~30 min
- **Completed:** 2026-06-13
- **Tasks:** 2 (both committed in a single atomic README write — both tasks target only README.md)
- **Files modified:** 1 (README.md)

## Accomplishments

- Rewrote README.md §1–§8 so every headline rate is a discovery-slice rate with n, 95% Wilson CI, and a verdict badge sourced from `output/validation_findings.csv`.
- Added "How to read these tables" methodology note under "Key Findings" explaining: discovery slice (oldest ~70%, `OOS_START = 2024-04-30`), Wilson CI, the three verdict tokens, and why `below-n` and `✗ NOT CONFIRMED` are distinct states.
- All 94 tests passed including data-dependent characterization tests — the README rewrite moved no computed numbers.

## Confirmed Findings (by section)

### §1 Baseline (14 confirmed / 2 not-confirmed)
- Daily NQ/ES bullish: ✓ CONFIRMED (61.0%, 57.7%)
- Daily NQ/ES bearish: ✗ NOT CONFIRMED — bearish Daily edges did not hold OOS
- All 4H, 1H, 15min buckets: ✓ CONFIRMED

### §2 Wick Position (31 confirmed / 1 not-confirmed)
- Past-wick closure confirmed at every timeframe, both instruments, both directions
- Daily NQ bearish within_wick: ✗ NOT CONFIRMED (50.3%, n=179 → OOS 28.9%)
- All 15min and 1H wick buckets: ✓ CONFIRMED

### §3 Combined Wick × Consecutive
- 15min all 48 buckets: ✓ CONFIRMED
- 1H all 48 buckets: ✓ CONFIRMED
- 4H: 22/24 confirmed (2 not-confirmed — NQ bull 2c_within_wick, ES bull 3c_within_wick)
- Daily: most below-n; of those with n ≥ 50 — 8 not-confirmed (concentrated in within-wick bearish and ES bullish within-wick)
- Old full-history text (ES bear/36.7% mislabel) removed — replaced with discovery bucket data

### §4 Stricter CISD (16/16 confirmed)
- All 16 buckets ✓ CONFIRMED; +5–8pp lift over baseline holds OOS

### §5 Markov
- Daily bearish: 6 of 6 not-confirmed (all bearish Daily Markov edges failed OOS)
- Daily bullish: 4 confirmed, 2 not-confirmed
- 1H and 15min: all 24 buckets ✓ CONFIRMED
- Conclusion confirmed: flat across 1–3 consecutive; edge only emerges with wick filter (§3)

### §6 Candle Size / Size Cross
- 15min: all buckets ✓ CONFIRMED (largest samples)
- 1H: all 32 candle_size + 32 size_cross buckets ✓ CONFIRMED
- Daily/4H: some below-n; Daily NQ bear "Big CISD" buckets below-n; one 4H cell not-confirmed
- Quadrant structure confirmed: Big CISD + Small prev consistently strongest

### §7 Volume
- 1H + 15min: all 32 buckets each ✓ CONFIRMED — volume ratio is negligible at these timeframes
- Daily + 4H: several not-confirmed (1x–1.5x Daily bearish, a few 4H cells)

### §8 SMT Confirmation (26 confirmed / 4 not-confirmed / 2 below-n)
- Daily NQ w/ SMT: below-n / not a finding (both directions, n < 50)
- Daily ES bearish w/ SMT: ✗ NOT CONFIRMED
- 4H ES bearish w/ SMT: ✗ NOT CONFIRMED
- 15min all four w/ SMT buckets: ✓ CONFIRMED (+2–4pp lift)
- 1H all four w/ SMT buckets: ✓ CONFIRMED (mixed sign but direction held)
- SMT confirmation is a genuine edge at 15min; not established at Daily or 4H bearish

## Headline Casualties (✗ NOT CONFIRMED — should not be published as findings)

| Pattern | Details |
|---------|---------|
| Bearish Daily baseline | NQ 59.1% (n=279), ES 55.3% (n=293) — OOS flipped below 50% |
| Daily NQ bearish within-wick | 50.3% (n=179) — OOS 28.9% |
| Daily bearish Markov (all 3 consecutive buckets, NQ+ES) | OOS rates 30–45% |
| Daily SMT: ES bearish w/ SMT | 54.7% (n=53) — OOS 41.7% |
| 4H ES bearish SMT w/ SMT | 55.9% (n=222) — OOS 46.7% |
| Several Daily combined within-wick | 8 buckets not-confirmed |

## Task Commits

| Task | Name | Commit |
|------|------|--------|
| 1 + 2 | Republish README §1–§8 with discovery rates, CI, verdicts | ede7db9 |

## Deviations from Plan

**1. Tasks 1 and 2 committed atomically.**
Both tasks write only to `README.md`. Writing the complete file in one pass and committing once avoids a half-written README state between commits. The single commit contains all deliverables from both tasks. Verified `git diff --name-only` shows only `README.md`.

## Known Stubs

None. All rates in the README are sourced from `output/validation_findings.csv` discovery columns. No hardcoded full-history numbers remain in §1–§8.

## Threat Flags

None. This plan modifies only documentation (`README.md`). No new network endpoints, auth paths, file access patterns, or schema changes were introduced.

## Self-Check: PASSED

- README.md present and modified: confirmed (`git diff HEAD~1 HEAD` shows README.md only)
- Commit ede7db9 exists: confirmed
- All verdict badges present: `✓ CONFIRMED`, `✗ NOT CONFIRMED`, `below-n / not a finding` all present in README.md
- Wilson mention: present
- OOS boundary date (`2024-04-30`): present
- Old mislabel `(ES bear) drops to 36.7`: absent (grep confirms)
- 94 tests passed including characterization tests

---
*Phase: 03-re-validate-republish-existing-findings*
*Completed: 2026-06-13*
