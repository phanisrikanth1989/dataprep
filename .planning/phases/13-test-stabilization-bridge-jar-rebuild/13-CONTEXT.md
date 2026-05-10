# Phase 13: Test Stabilization & Bridge JAR Rebuild — Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Get the test suite to **zero failures** and lock a per-module coverage baseline that Phase 14 can enforce against. Coordinated with the Java bridge JAR rebuild — manager's source changes are already committed to the repo (May 5 / May 8 updates); the JAR binary is stale (Apr 25). Phase 13 rebuilds the JAR locally, then triages and fixes the resulting 57 failing tests.

**In scope:**
- Rebuild Java bridge JAR via `mvn package` from `src/v1/java_bridge/java/`; commit the rebuilt `target/java-bridge-with-dependencies.jar`
- Triaged fix work (verified by deep-research, not hypothesis):
  - **22 CODE-CHANGE tests → 4 root-cause source patches** (Excel `input_schema` defensive read, unique_row pandas-3.0 StringDtype detection, convert_type to_numeric inference fallback, file_list `NB_FILE` globalMap put)
  - **15 TEST-CHANGE updates** (9 executor_iterate stale after Phase 12's `executor.py` finalization commit `55d8354`; 5 NeedsReview assertions match smaller current list; 1 extract_regex_fields converter test asserts wrong storage convention)
  - **11 STALE deletions** (NeedsReview tests for converter flags the engine has since implemented)
- Post-rebuild re-triage of the 9 currently-JAR-blocked tests; any remaining real signature mismatches fold into CODE/TEST buckets
- Per-module coverage baseline measured across `src/v1/engine/` + `src/converters/` and recorded in `13-COVERAGE-BASELINE.md` (consumed by Phase 14)
- Documented `pytest --cov=...` invocation in COVERAGE-BASELINE.md (the "wired and reproducible CI command")
- Add XML-aligned test infrastructure requirements: TEST-07, TEST-08 (text TBD by planner)

**Out of scope (deferred):**
- New components or features (Phase 13 is pure stabilization)
- Coverage push to the 95% per-module floor (Phase 14)
- Real-job E2E + perf benchmarks (Phase 15)
- Documentation sweep (Phase 16)
- CI pipeline file (.github/workflows/, Jenkinsfile, etc.) — only a documented command in this phase
- Phase 13.1 follow-up — NOT planned (hard-zero achievable in-phase; if execution surfaces blockers, reassess at that point)

</domain>

<decisions>
## Implementation Decisions

### Bridge JAR coordination
- **D-A1: Manager's Java source is in-tree.** `JavaBridge.java` updated 2026-05-05; `ArrowSerializer.java` updated 2026-05-08. The `executeOneTimeExpression(String, Map<String, Object>, ...)` signature exists in the Java source today. The 9 currently "JAR-blocked" tests are blocked by stale JAR binary (Apr 25 build), not by waiting on the manager.
- **D-A2: Phase 13 rebuilds the JAR locally.** First plan/task: run `mvn package` from `src/v1/java_bridge/java/`, commit `target/java-bridge-with-dependencies.jar` (and the lighter `java-bridge.jar` if applicable). Re-triage the 9 currently-blocked tests after rebuild — any remaining real signature mismatches go into CODE-CHANGE (Python client patch) or TEST-CHANGE (test update) per actual diagnosis.
- **D-A3: Hard-zero failure bar.** Phase 13 closes when `pytest tests/` returns 0 failures (excluding `-m java` opt-in tests already passing). No xfail markers added. No Phase 13.1 follow-up planned. Achievable because (a) JAR rebuild unblocks the 9 bridge-coupled tests, (b) the other 48 collapse to a small number of root causes per the triage.

### CODE-CHANGE root-cause patches (22 tests → 4 fixes)
- **D-B1: Excel `input_schema` — scoped defensive-read fix.** `src/v1/engine/components/file/file_output_excel.py` lines 216 and 244 use the un-defensive form `if self.input_schema:` while lines 435 and 474 of the same file (and all of `file_output_delimited.py`) use `getattr(self, "input_schema", None) or []`. Bring the 2 inconsistent reads into line with the existing convention. **No BaseComponent change** — fix-source-no-fallbacks rule applies; the convention IS the source contract.
- **D-B2: unique_row pandas 3.0 StringDtype detection.** `src/v1/engine/components/aggregate/unique_row.py:120` (and the parallel `dup_ci` block at line 143) gate the case-insensitive `str.lower()` temp-column build on `work[col].dtype == object`. Project runtime is pandas 3.0.1 with CoW (per project memory); string columns now have `StringDtype`, not `object`. Replace with `pd.api.types.is_object_dtype(work[col]) or pd.api.types.is_string_dtype(work[col])`.
- **D-B3: convert_type infer numeric when target_type empty.** `src/v1/engine/components/transform/convert_type.py` — when MANUALTABLE has `input_column == output_column` (in-place cast) and no output schema is set, `target_type` is empty and the column stays as `StringDtype`. Add a fallback: when target_type is empty for an in-place cast, attempt `pd.to_numeric(series, errors="coerce")` to match Talend tConvertType's MANUALTABLE default behavior.
- **D-B4: file_list NB_FILE globalMap put.** `src/v1/engine/components/file/file_list.py` — add `self.global_map.put(f"{self.id}_NB_FILE", count)` in `execute()` (or wherever the iteration count is known). Unblocks 3 `iterate_e2e` tests.

### TEST-CHANGE updates (15 tests)
- **D-C1: executor_iterate (9 tests)** — Update assertions to match Phase 12 commit `55d8354` finalization order (`reset()` runs before stall-detection raise; iterate stats may need to be sampled at a different timing). **Verify during execution that stats actually propagate**; if they don't, reclassify the affected tests as CODE-CHANGE and fix the iterate stats path. This ambiguity is explicit — do not silently flip the verdict.
- **D-C2: NeedsReview converter assertions (5 tests)** — Update assertions to the current (smaller) needs_review list. Tests stay; assertions get tightened.
- **D-C3: extract_regex_fields converter test** — Test asserts converter stores literal `\\w` (Java double-backslash). Converter at `src/converters/talend_to_v1/components/transform/extract_regex_fields.py:47` correctly unescapes to Python `\w` for runtime use. Update the test, keep the converter.

### STALE deletions (11 tests)
- **D-D1: NeedsReview deletion policy.** When the engine implements a feature the converter previously flagged with `needs_review`, the corresponding test is **DELETED**, not updated. `needs_review` is a CURRENT engine-gap signal (not historical record); Phase 12 D-E1 already established this pattern (conditional `needs_review` for genuinely deferred sub-features). Delete the 11 tests across `test_file_input_delimited.py::TestNeedsReview`, `test_file_input_fullrow.py::TestNeedsReview`, `test_file_output_delimited.py::TestNeedsReview`, `test_aggregate_row.py::TestNeedsReview` that assert obsolete `needs_review` entries.

### Coverage baseline & CI
- **D-E1: Baseline scope** — Measured per-module line coverage across **all of** `src/v1/engine/` + `src/converters/`. Whatever today's number is per module goes into `13-COVERAGE-BASELINE.md`. Phase 14 reads this as the floor for its 95% per-module gate.
- **D-E2: CI command** — Documented `pytest tests/ --cov=src/v1/engine --cov=src/converters --cov-report=term-missing --cov-report=html` invocation in `13-COVERAGE-BASELINE.md` and referenced from CLAUDE.md's testing section. No `.github/workflows/`, no Jenkinsfile, no Makefile target — "wired and reproducible" = anyone paste-runs.

### Order of operations
- **D-F1: Plan ordering** — JAR rebuild first (Plan 1), so the 9 bridge-coupled tests become testable; then CODE-CHANGE patches; then TEST-CHANGE/STALE sweep; then coverage baseline measurement; then close-out (REQUIREMENTS.md flip, ROADMAP.md flip, STATE.md update). Test-suite-green check runs after every plan.
- **D-F2: Atomic commits** — Each fix lands as its own commit (Excel: 1 commit; unique_row: 1 commit; convert_type: 1 commit; file_list: 1 commit; ~9 commits for executor_iterate test updates; 5 commits for NeedsReview assertion updates; 11 commits for STALE deletions = ~30+ commits expected). Categorize commit messages with prefixes: `fix(13): BUG-XXX`, `test(13): TEST-XXX`, `chore(13): STALE-XXX`.

### Claude's Discretion
- Plan/wave decomposition for the ~30 patch commits (planner decides — could be one plan per category, or one plan per file group, etc.)
- Specific commit message subcategories (e.g., BUG-EXC-001 / BUG-UNIQ-001 numbering scheme)
- Whether `executor_iterate` ambiguity (D-C1) needs a separate verification sub-plan or is handled inline during the test update plan
- Whether the JAR rebuild plan includes a Maven version pin verification (currently `lxml >=4.9,<7` is correct but no equivalent check exists for the Java/Maven side)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & Architecture
- `.planning/PROJECT.md` — Core value, scope discipline
- `.planning/REQUIREMENTS.md` — TEST-07 / TEST-08 to be added during planning
- `.planning/ROADMAP.md` §"Phase 13" — Goal, dependencies, 5 success criteria
- `.planning/codebase/ARCHITECTURE.md` — Component pattern (ABC + registry + per-component organization)
- `.planning/codebase/CONVENTIONS.md` — snake_case, ASCII-only logs, custom exceptions
- `.planning/codebase/TESTING.md` — pytest discovery + opt-in `-m java` marker convention
- `CLAUDE.md` — Project instructions

### Phase 12 handoff (the explicit predecessor)
- `.planning/phases/12-xml-components-audit-harden-output/12-CONTEXT.md` — D-E1/E2 deferred the bridge work to Phase 13
- `.planning/phases/12-xml-components-audit-harden-output/12-PHASE-SUMMARY.md` — final retrospective
- `.planning/phases/12-xml-components-audit-harden-output/12-08-SUMMARY.md` — `executor.py` `reset()`-before-stall change (commit `55d8354`); causes the 9 executor_iterate test drifts

### Bridge surface references
- `src/v1/java_bridge/java/pom.xml` — Maven build config; the JAR rebuild target
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java` — manager's signature surface (May 5 update)
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/ArrowSerializer.java` — manager's May 8 update
- `src/v1/java_bridge/bridge.py:308` — `execute_one_time_expression()` Python client; signature must match `executeOneTimeExpression` Java method
- `.planning/phases/05.1-java-bridge-tmap-fix/` — Arrow type + closure dispatch fix (prior bridge debugging context)
- `.planning/phases/07.1-manager-audit-and-base-component-fixes/` — BaseComponent test patterns

### CODE-CHANGE fix targets
- `src/v1/engine/components/file/file_output_excel.py` (lines 216, 244 — the 2-spot defensive-read fix)
- `src/v1/engine/components/file/file_output_delimited.py` — the convention reference (always uses defensive `getattr`)
- `src/v1/engine/components/aggregate/unique_row.py` (lines 120, 143 — pandas 3.0 StringDtype guard)
- `src/v1/engine/components/transform/convert_type.py` (in-place cast inference fallback)
- `src/v1/engine/components/file/file_list.py` (NB_FILE globalMap put)
- `src/converters/talend_to_v1/components/transform/extract_regex_fields.py:47` (Python-regex storage convention; test gets updated, not converter)

### Failing test files (Phase 13's work-list ground truth)
- `tests/v1/engine/components/file/test_file_output_excel.py` — 17 tests (CODE-CHANGE, Fix 1)
- `tests/v1/engine/components/aggregate/test_unique_row.py::TestCaseSensitivity`, `TestOnlyOnceEachDuplicate` — 4 tests (CODE-CHANGE, Fix 2)
- `tests/v1/engine/components/transform/test_convert_type.py::TestManualTable::test_string_to_int_cast` — 1 test (CODE-CHANGE, Fix 3)
- `tests/integration/test_iterate_e2e.py::TestJobTFileListExecution`, `TestJobTFlowToIterateExecution` — 3 tests (CODE-CHANGE, Fix 4)
- `tests/v1/engine/test_executor_iterate.py` — 9 tests (TEST-CHANGE D-C1, with ambiguity flag)
- `tests/converters/talend_to_v1/components/{aggregate,file}/test_*.py::TestNeedsReview` — 11 STALE + 5 TEST-CHANGE
- `tests/v1/engine/test_bridge_integration.py`, `test_java_component.py`, `test_code_components_engine_smoke.py`, `test_map_method_size.py`, `test_full_pipeline.py::TestTMapJavaExpressionPipeline` — 9 JAR-coupled (re-triage post-rebuild)
- `tests/converters/talend_to_v1/components/transform/test_extract_regex_fields.py::TestParameterExtraction::test_regex_custom` — 1 TEST-CHANGE (D-C3)

### Library/runtime references
- pandas 3.0.1 with Copy-on-Write — runtime baseline (project memory)
- pytest 9.0.2; pytest-cov 7.0.0 — for `--cov` / `--cov-report=html|term-missing`
- Maven 3.x for the JAR rebuild

</canonical_refs>

<code_context>
## Existing Code Insights

### Triage ground truth (verified deep-research, not hypothesis)
- 57 failing tests today; collapse to **5 root causes**:
  1. Excel `input_schema` defensive-read inconsistency (17 tests, 2-line fix)
  2. unique_row pandas-3.0 StringDtype guard (4 tests, 2-line fix)
  3. convert_type in-place cast inference (1 test, ~5-line fix)
  4. file_list NB_FILE not put on globalMap (3 tests, 1-line fix)
  5. JAR stale (9 tests, `mvn package` + commit)
- Plus 15 mechanical TEST-CHANGE updates (executor_iterate stale assertions, NeedsReview assertion drifts, regex storage convention test)
- Plus 11 STALE deletions (NeedsReview tests for engine-implemented features)

### Reusable patterns to mirror
- **Defensive `getattr` for engine-set attributes**: `getattr(self, "input_schema", None) or []` — established by `file_output_delimited.py` and existing spots in `file_output_excel.py`. Pattern propagates wherever engine populates an attribute lazily on the component.
- **pandas 3.0 dtype detection**: `pd.api.types.is_object_dtype(...) or pd.api.types.is_string_dtype(...)` — the right shape for Object-or-String column gates under CoW.
- **Phase 11 / 12 audit-then-fix flow** — a leaner version applies here: triage report (already done above), then per-fix atomic commits.
- **D-E1 conditional needs_review pattern** (Phase 11/12) — the precedent for "delete needs_review tests when engine implements".

### Manager's bridge surface (already in-tree)
- `JavaBridge.java:277` — `executeOneTimeExpression(String expression, Map<String, Object> contextVars, Map<String, Object> globalMap)` — signature matches what `bridge.py:308` calls. The runtime mismatch is purely "JAR was built before this method existed in source". Maven rebuild fixes it.
- `ArrowSerializer.java` — May 8 (today) update; covers the decimal nulls / large-data serialization that Phase 12's `9bee178` mentioned. Rebuilding picks this up too.

</code_context>

<specifics>
## Specific Ideas

- **Manager's bridge work is committed.** Phase 13 doesn't wait on anyone external; the JAR rebuild is purely a Maven invocation against existing source.
- **The triage already exists.** Phase 13 doesn't need a Plan-1-style audit phase — the work-list is the table in this CONTEXT.md.
- **High consolidation ratio.** 57 failures → 5 root-cause fixes + 15 mechanical test updates + 11 deletions. This is a small phase by LOC delta, even if commit count is high.
- **Verify-don't-assume on executor_iterate.** Per project memory rule "Verify audit claims": the agent classified those 9 tests as TEST-CHANGE based on commit `55d8354` being recent. During execution, the executor running the test-update plan MUST first read what stats actually contain at the assertion point. If stats are zero/None when they should have values, reclassify as CODE-CHANGE and fix the executor.
- **Atomic commits per fix.** Each of the 4 root-cause patches gets its own commit. Each TEST-CHANGE update gets its own commit. Each STALE deletion gets its own commit. ~30+ commits expected — that's fine, the phase is mechanical.

</specifics>

<deferred>
## Deferred Ideas

- **Phase 14 (Coverage Push)** — bring per-module coverage to 95%. Phase 13 only measures and records; Phase 14 enforces.
- **Phase 15 (Integration & Performance)** — real-job E2E + perf benchmarks. Out of stabilization scope.
- **Phase 16 (Documentation Sweep)** — README / contributing guide updates.
- **CI pipeline (GitHub Actions / Jenkinsfile)** — only if a future operational phase needs it. Phase 13's "wired and reproducible" is satisfied by a documented command.
- **Phase 13.1 follow-up** — NOT planned. If execution surfaces a real blocker (e.g., manager pushes another bridge change mid-phase), reassess at that boundary.
- **BaseComponent.input_schema architectural fix** — D-B1 is scoped intentionally. The "right" architectural fix (Executor populates input_schema from job config schema) is deferred; defensive `getattr` is the pragmatic Phase 13 answer. If a future phase needs schema-everywhere, that's its own work.

</deferred>

---

*Phase: 13-test-stabilization-bridge-jar-rebuild*
*Context gathered: 2026-05-08*
