# Phase 13 Verification Report

**Verified:** 2026-05-10
**Phase:** 13-test-stabilization-bridge-jar-rebuild
**Plans complete:** 9/9

---

## Success Criteria Evidence

### Criterion 1: Zero failing tests under `python -m pytest tests/`

**Status:** PASS

**Evidence:**
- Command: `python -m pytest tests/ -q --no-header`
- Result at Plan 13-07 completion: **6832 passed, 26 skipped, 1 xfailed, 0 failed** (44.41s)
- Result at Plan 13-08 measurement (coverage run): **6832 passed, 26 skipped, 1 xfailed, 0 failed**
- Commit establishing zero: `401b4df` (STALE-010 -- final deletion; after which `pytest tests/` first returned 0 failures)

**Failure groups resolved:**

| Failure Group | Root Count | Resolution Type | Key Commits |
|--------------|--------:|-----------------|-------------|
| Groovy script generation (BUG-BRDG-001) | 3 | CODE-CHANGE | `e7282a3` |
| BaseComponent.reset() GlobalMap wipe (BUG-BRDG-002) | 9 | CODE-CHANGE | `7df08aa` |
| Executor finalization over-reset (BUG-BRDG-003) | 9 | CODE-CHANGE | `9ca05e2` |
| Excel input_schema AttributeError (BUG-EXC-001) | 40 | CODE-CHANGE | `fff1b85` |
| unique_row pandas-3.0 StringDtype (BUG-UNIQ-001) | 42 | CODE-CHANGE | `9cf0c91` |
| convert_type MANUALTABLE numeric fallback (BUG-CT-001) | 24 | CODE-CHANGE | `c246625` |
| file_list NB_FILE not in globalMap (BUG-FL-001) | 27 | CODE-CHANGE | `bfffc32` |
| aggregate_row NeedsReview count assertion (TEST-NR-001) | 4 | TEST-CHANGE | `254e097` |
| extract_regex_fields double-backslash storage (TEST-REGEX-001) | 1 | TEST-CHANGE | `aa44a46` |
| STALE NeedsReview tests (D-D1) | 10 | DELETION | `e1ac00f`..`401b4df` |

Note: BUG-BRDG-002/003 resolved the 9 executor_iterate tests that were previously
classified as TEST-CHANGE (D-C1). The root cause was a Phase 12 regression (CR-01
finalization loop) exposed by JAR rebuild, not stale test assertions.

---

### Criterion 2: Java bridge JAR rebuilt; `executeOneTimeExpression` matches Python client

**Status:** PASS

**Evidence:**
- Maven rebuild: `mvn package -f src/v1/java_bridge/java/pom.xml` run 2026-05-10
- JAR timestamps after rebuild:
  - `java-bridge-with-dependencies.jar`: May 10 19:16 (was Apr 25 21:18)
  - `java-bridge.jar`: May 10 19:16 (was Apr 25 21:18)
- Note: `target/` is in `.gitignore` -- JAR is a build artifact; source is tracked in git
- Manager source already committed: `JavaBridge.java` (2026-05-05), `ArrowSerializer.java` (2026-05-08)
- Java method signature: `executeOneTimeExpression(String expression, Map<String, Object> contextVars, Map<String, Object> globalMap)` at `JavaBridge.java:277`
- Python client: `src/v1/java_bridge/bridge.py:308` calls `executeOneTimeExpression(expression, self.context, _coerce_global_map_for_java(self.global_map))`
- Signature match: 3-arg call matches 3-param Java method

**9 formerly-JAR-blocked tests (all now PASS):**

| Test File | Tests | Resolution |
|-----------|------:|------------|
| `tests/v1/engine/test_bridge_integration.py` | 31 | PASS-after-rebuild |
| `tests/v1/engine/components/transform/test_java_component.py` | 14 | PASS-after-rebuild |
| `tests/v1/engine/test_code_components_engine_smoke.py` (7) | 7 | PASS-after-rebuild |
| `tests/v1/engine/test_code_components_engine_smoke.py::TestPythonRowComponentEngineEnd2End` | 1 | CODE-CHANGE (BUG-BRDG-002) |
| `tests/v1/engine/components/transform/test_map_method_size.py` | 3 | CODE-CHANGE (BUG-BRDG-001) |
| `tests/v1/engine/test_full_pipeline.py::TestTMapJavaExpressionPipeline` | 1 | PASS-after-rebuild |

**3 Phase-12-induced bugs caught and fixed:**
- BUG-BRDG-001: 3 Groovy syntax bugs in `map.py::_build_compiled_script` (indentation, `def void`, `var` keyword)
- BUG-BRDG-002: `BaseComponent.reset()` called `global_map.reset_component()` wiping stats
- BUG-BRDG-003: Executor CR-01 finalization loop (`hasattr(component, "reset")`) matched ALL components including iterate body components, causing extra reset() calls

---

### Criterion 3: Per-module coverage baseline recorded in COVERAGE-BASELINE.md

**Status:** PASS

**Evidence:**
- File: `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-COVERAGE-BASELINE.md`
- Commit: `7e42224` (docs(13-08): COV-BASE-001 measure and record per-module coverage baseline)
- Measurement point: HEAD `5649b6f` (green suite, 6832 passed, 0 failed)
- Overall: **75%** (19429 statements, 4881 missed)
- Module counts (excluding complex_converter legacy):
  - Total: 198 modules
  - At or above 95%: **145** (Phase 14 PASS)
  - Below 95%: **53** (Phase 14 lift targets)

**Reproducible command (from COVERAGE-BASELINE.md and CLAUDE.md):**
```bash
python -m pytest tests/ \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  -q
```

---

### Criterion 4: Pre-existing failure groups documented and resolved (no deferred items)

**Status:** PASS

**Evidence:**

All 7 CODE-CHANGE root-cause bugs patched; all TEST-CHANGE tests updated; all STALE tests deleted.
Zero xfail markers added. Zero failures deferred.

| Category | Count | All Resolved? |
|----------|------:|:-------------:|
| CODE-CHANGE (source patches) | 7 bugs (4 distinct component areas) | YES |
| TEST-CHANGE (test expectation updates) | 2 test methods | YES |
| STALE (test deletions per D-D1) | 10 test methods | YES |
| JAR-blocked (post-rebuild pass) | 9 tests (some further fixed by CODE-CHANGE) | YES |

**D-D1 deletion policy followed:** When engine implements a feature the converter flagged with
`needs_review`, the corresponding test is DELETED (not updated). 10 STALE deletions confirmed
across 3 converter test files.

**No deferred items:** CONTEXT.md listed 4 CODE-CHANGE root causes (D-B1..D-B4) and 3 TEST-CHANGE
groups (D-C1..D-C3). All resolved in Phases 13-01 through 13-07.

---

### Criterion 5: CI command for coverage measurement wired and reproducible

**Status:** PASS

**Evidence:**
- Command in `13-COVERAGE-BASELINE.md` (Reproducible Command section): `python -m pytest tests/ --cov=src/v1/engine --cov=src/converters --cov-report=term-missing --cov-report=html -q`
- Same command added to `CLAUDE.md` (Coverage section) via commit `7e42224`
- Command produces: terminal per-module table (this baseline's data source) + `htmlcov/index.html` (gitignored)
- Note: `--cov-branch` NOT added -- Phase 14's 95% gate is line coverage only (documented in baseline)
- `htmlcov/` is gitignored (`7e42224` confirmed zero untracked files after run)

---

## Context Decisions Adherence

| Decision | Intent | Adherence |
|----------|--------|-----------|
| D-A3: Hard-zero failure bar | pytest tests/ returns 0 failures; no xfail | FOLLOWED. Final count: 0 failures. No xfail markers added. |
| D-B1: FileOutputExcel defensive-read fix | getattr pattern at 2 inconsistent spots | FOLLOWED. Lines 216, 244 fixed; all 4 read sites now use getattr. |
| D-B2: unique_row pandas 3.0 StringDtype | dual dtype check for object + StringDtype | FOLLOWED. `is_object_dtype OR is_string_dtype` at line 119. |
| D-B3: convert_type numeric fallback | pd.to_numeric for in-place cast with empty target_type | FOLLOWED. Whole-column replacement (not loc-based) used to handle StringDtype correctly. |
| D-B4: file_list NB_FILE globalMap put | put in execute() or finalize() | FOLLOWED. Put added in `finalize()` with None guard. |
| D-C1: executor_iterate ambiguity | Verify stats actually propagate; reclassify if CODE-CHANGE | FOLLOWED. All 9 tests were CODE-CHANGE (BUG-BRDG-002/003), not TEST-CHANGE. Reclassified. |
| D-D1: NeedsReview deletion policy | DELETED not updated | FOLLOWED. 10 tests deleted. |
| D-E1/D-E2: Coverage baseline scope | All of src/v1/engine + src/converters; no JAR changes in XML phase | FOLLOWED. Baseline covers both targets. |
| D-F1: Plan ordering | JAR first, then CODE, then TEST/STALE, then coverage, then close-out | FOLLOWED. Plans 01->02-05->06-07->08->09 in order. |

---

## Deviations from CONTEXT.md Decisions

1. **JAR not committed to git** (D-A2 said "commit the JAR binary"): `target/` is in `.gitignore`. JAR is a build artifact; source is tracked. Deviation documented in 13-01-SUMMARY.md. Anyone can reproduce with `mvn package`.

2. **STALE count: 10 not 11** (D-D1 anticipated 11): `test_aggregate_row.py` had 0 STALE tests -- its only failure was a TEST-CHANGE (count assertion), resolved in Plan 13-06.

3. **TEST-CHANGE count: 2 not 15** (D-C1..C3 anticipated 15): Plan 13-01 BUG-BRDG-002/003 fixes resolved all 9 executor_iterate tests as CODE-CHANGE. Only 2 TEST-CHANGE remained: aggregate_row count + regex_custom.

4. **TEST-09/TEST-10** (not TEST-07/TEST-08 as plan frontmatter stated): TEST-07 is Phase 8 (Python components) and TEST-08 is Phase 6 (transform components) -- already defined. Phase 13 uses TEST-09 and TEST-10.

---

## Overall Verdict

**COMPLETE**

All 5 Phase 13 success criteria are met. Zero deferred items. Test suite at hard-zero failures.
Coverage baseline recorded. CI command documented. Phase 14 can begin.

---

*Phase: 13-test-stabilization-bridge-jar-rebuild*
*Verified: 2026-05-10*
