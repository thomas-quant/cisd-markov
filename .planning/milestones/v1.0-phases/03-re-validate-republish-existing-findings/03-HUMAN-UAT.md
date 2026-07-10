---
status: complete
phase: 03-re-validate-republish-existing-findings
source: [03-VERIFICATION.md]
started: 2026-06-14T00:00:00Z
updated: 2026-06-14T12:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. README §8 SMT table narrative coherence
expected: §8 table shows discovery-slice rates and n; ES Daily bearish w/ SMT shows corrected values (not stale 27.8% n=18); 4H/1H/15min cells show n in hundreds-to-thousands range; prose narrative updated to match
result: pass

### 2. output/discovery_summary.md content quality
expected: All 14 analysis sections present with rate, n, CI, OOS-eligible Y/N per bucket; analyses with all buckets below n=50 emit "no reportable findings"; readable as go/no-go review artifact
result: pass

### 3. Sacred OOS banner single-spend confirmation
expected: OOS banner printed exactly once during `build_validation.py --oos` run; validation_manifest_discovery.csv (752 rows) not clobbered after OOS run; validation_manifest_oos.csv has 752 rows with slice=oos
result: pass

### 4. README §1–§4 table visual completeness
expected: Every bucket row has discovery rate + N + 95% CI + verdict badge; below-n cells show "below-n / not a finding"; NOT CONFIRMED cells show "✗ NOT CONFIRMED"; both visually distinct; no bucket from validation_findings.csv silently missing
result: pass

### 5. README §5–§8 narrative quality
expected: Every cited rate in §5–§8 backed by a discovery bucket in validation_findings.csv; no bare full-history rates remain; "How to read these tables" methodology note reads clearly
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
