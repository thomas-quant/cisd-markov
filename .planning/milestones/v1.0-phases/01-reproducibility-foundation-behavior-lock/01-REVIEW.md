---
phase: 01-reproducibility-foundation-behavior-lock
reviewed: 2026-06-12
depth: quick
files_reviewed: 13
files_reviewed_list:
  - cisd_analysis.py
  - scripts/build_forward_returns.py
  - conftest.py
  - pyproject.toml
  - requirements.txt
  - .env.example
  - .gitignore
  - .github/workflows/ci.yml
  - README.md
  - tests/test_core_compute.py
  - tests/test_characterization.py
  - tests/test_determinism.py
  - tests/test_forward_returns_builder.py
findings:
  critical: 0
  warning: 4
  info: 2
  total: 6
status: issues_found
---

# Phase 01: Code Review Report

**Depth:** quick (read-through for the three flagged focus areas: graceful-degradation, env-var path handling, test soundness)
**Status:** issues_found

## Summary

The reproducibility work is largely sound: `requirements.txt` is pinned, `conftest.py`/`pyproject.toml` fix import paths, the SMT path is now env-overridable, and most graceful-degradation and behavior-lock tests genuinely exercise their fallback branches (`test_build_dataset_falls_back_when_smt_unavailable` correctly drives both the probe and the fallback). No security vulnerabilities, secrets, injection vectors, or data-loss risks were found, so there are **no BLOCKERs**.

However, the adversarial pass surfaced four WARNINGs concentrated in exactly the three areas flagged for scrutiny: (1) `main()`'s SMT degradation is weaker than `build_dataset()`'s and crashes on an existing-but-broken path; (2) an empty `SMT_PKG_PATH` env var silently defeats the `.exists()` guard; (3) the determinism source-scan guard is a **false-green** — it never inspects 9 of the 14 compute functions; and (4) the README still publishes SMT/combined headline numbers that the project's own characterization tests document as stale/wrong — directly undermining the project's stated core value ("a reported edge can be trusted").

## Warnings

### WR-01: `main()` SMT degradation only guards `.exists()`, crashes on existing-but-broken package

**File:** `cisd_analysis.py:1324` (with `:331-341`, `:1346`)
**Issue:** The entry-point guard is `if needs_swing_smt and not _SMT_PKG_PATH.exists():`. It only skips `smt_cisd` when the path is *missing*. If the path exists but the `smt` package fails to import (corrupt/partial checkout, wrong directory), `prepare_pair(..., with_swing_smt=True)` → `_scan_swing_smt_events` → `_load_scan_smts_historical` raises `ImportError`, which `main()` never catches. The entire run aborts and all 13 non-SMT analyses are lost. This is asymmetric with `scripts/build_forward_returns.py:360-365`, which probes inside `try/except Exception` and degrades to `with_smt=False`. The phase goal was "graceful SMT degradation across all entry points," and `main()` is an entry point that does not fully degrade.
**Fix:** Mirror the `build_dataset()` pattern — wrap the SMT-dependent path in `try/except`, e.g.:
```python
if needs_swing_smt:
    try:
        _load_scan_smts_historical()  # cheap probe: path exists AND import works
    except (FileNotFoundError, ImportError) as exc:
        print(f"[warn] SMT unavailable ({exc!r}); skipping smt_cisd analysis.")
        requested  = [k for k in requested if k != "smt_cisd"]
        standalone = [k for k in standalone if k != "smt_cisd"]
        needs_swing_smt = False
```

### WR-02: Empty `SMT_PKG_PATH` resolves to the cwd and bypasses the degradation guard

**File:** `cisd_analysis.py:67`
**Issue:** `_SMT_PKG_PATH = Path(os.environ.get("SMT_PKG_PATH", "/mnt/...SMT"))`. A common misconfiguration — `export SMT_PKG_PATH=` (empty) or a blank CI secret — yields `Path("")`, which Python resolves to `PosixPath('.')` (`Path('').exists()` is `True`). The `.exists()` guards in `main()` (`:1324`) and `_load_scan_smts_historical()` (`:332`) therefore pass, `"."` is inserted into `sys.path`, and `from smt import scan_smts_historical` raises an uncaught `ImportError` (same crash path as WR-01). An empty override is strictly worse than no override.
**Fix:** Treat empty/whitespace as unset, and resolve:
```python
_raw = os.environ.get("SMT_PKG_PATH", "").strip()
_SMT_PKG_PATH = Path(_raw).expanduser() if _raw else Path("/mnt/e/backup/code/Finance/Misc/SMT")
```

### WR-03: Determinism guard is a false-green — 9 of 14 compute functions are never scanned

**File:** `tests/test_determinism.py:126-148` (assertion at `:151`)
**Issue:** `_extract_compute_sections()` captures lines only while `in_section` is `True`, sets it `False` at `"# ── Chart Functions"` (cisd_analysis.py:548), and never re-enables it. But 9 compute functions are defined **below** that header — `compute_volume` (648), `compute_candle_size` (697), `compute_size_cross` (746), `compute_smt_cisd` (808), `compute_cisd_fvg` (831), `compute_fvg_hold` (864), `compute_cisd_fvg_interaction` (906), `compute_sweep` (951), `compute_sssf_swing` (967). A `datetime.now()` / unseeded `random.*` introduced into any of these would pass the guard undetected, while the test docstring claims it protects "the compute pipeline." Note also that `_COMPUTE_FUNCTION_PREFIXES` (`:121-123`) — the function-prefix list that *would* have covered all of them — is defined but never used (dead code).
**Fix:** Scan by function rather than by section header — either scan the entire source, or use `ast` to extract function bodies whose names match `_COMPUTE_FUNCTION_PREFIXES`, then run the regexes against those bodies.

### WR-04: README headline numbers are stale/known-wrong per the project's own tests

**File:** `README.md:101-126` (§8) and `:52-56` (§3)
**Issue:** The characterization tests document, in their own comments, that the README is wrong, yet the README was not updated:
- §8 SMT table publishes e.g. "Daily NQ Bullish 70.8% (n=24)", but `test_characterization.py:230-258` locks the current-code value at 63.5% (n=63), noting "These differ substantially from the README §8 table ... sample sizes are 2-3x larger." Every §8 row is superseded.
- §3 line 53 lists "ES Bear 2c past wick 80.7%" but the test (`:177-180`) records actual 80.6%; line 56 says "Within-wick + 2c on Daily (ES bear) drops to 36.7%", but the test (`:169-171`, `:179-180`) notes 36.7% is the **NQ** figure (wrong instrument) — actual ES is 38.0%.

For a project whose stated core value is "a reported edge can be trusted," shipping published rates the codebase's own tests contradict is a correctness/credibility defect.
**Fix:** Regenerate README §3 and §8 from current pipeline output (and correct the misattributed within-wick instrument label), or annotate the tables as superseded with a regeneration date.

## Info

### IN-01: Behavior-lock and SMT characterization tests never run in CI

**File:** `tests/test_characterization.py:25-28`, `:261-263`; `.github/workflows/ci.yml:28`
**Issue:** The entire characterization module is `skipif`'d when parquet data is absent, and `test_smt_cisd_rates` additionally skips without the SMT package — neither is present in CI. The headline-number "behavior lock" is therefore enforced only on the developer's machine; CI cannot detect drift in `compute_basic`/`compute_significance`/`compute_combined`/`compute_smt_cisd` outputs. This is documented and legitimate (data is gitignored), but it means the phase's "behavior lock" guarantee does not hold in CI. Consider committing a tiny synthetic/anonymized fixture so at least a reduced lock runs in CI.

### IN-02: `.env.example` implies a `.env` is auto-loaded, but no loader exists

**File:** `.env.example:1-10`
**Issue:** The code reads `os.environ.get("SMT_PKG_PATH", ...)` directly; there is no `python-dotenv` dependency or `load_dotenv()` call. A user who copies `.env.example` to `.env` expecting it to be picked up automatically will see no effect unless their shell/tooling exports it. Add a one-line note ("export this var or source the file; `.env` is not auto-loaded") to avoid the misconception.

---

_Reviewer: Claude (gsd-code-reviewer) · Depth: quick_
