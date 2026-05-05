# Roadmap: DataPrep Engine Restructure

## Overview

This roadmap takes the partially-working Python ETL engine from its current broken state to production readiness for the 12 target components plus iterate and Oracle support. The critical path flows from infrastructure bug fixes through Java bridge reliability and execution loop restructuring (in parallel), then fans out to component work. The Java bridge is established early because Java expressions are used throughout tMap and many other components. Transform components are split into two groups: complex components with significant bugs (aggregation, sort, filter) and lighter components (column filter, join, unite -- two of which are already functionally Green). Each phase delivers a verifiable capability, and testing is woven into component phases rather than deferred to the end.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Infrastructure Bug Fixes & Project Setup** - Fix all P0/P1 cross-cutting bugs in base classes, config alignment, and project setup so components can build on a stable foundation (completed 2026-04-14)
- [x] **Phase 2: Java Bridge Reliability** - Fix Arrow serialization, Py4J stability, and context/globalMap sync so all downstream components can depend on reliable Java expression evaluation (completed 2026-04-14)
- [x] **Phase 3: Execution Loop Restructure** - Decompose the monolithic execution loop into testable units with correct subjob tracking, trigger timing, and data flow routing (completed 2026-04-14)
- [x] **Phase 4: File I/O Components** - Deliver tFileInputDelimited and tFileOutputDelimited with full Talend feature parity (completed 2026-04-15)
- [x] **Phase 5: tMap Component** - Deliver tMap with correct join semantics, reject routing, and expression handling (completed 2026-04-15)
- [x] **Phase 5.1: Java Bridge tMap Fix** (INSERTED) - Fix Arrow type conversion and compiled tMap script execution (completed 2026-04-15)
- [x] **Phase 5.2: tMap RELOAD_AT_EACH_ROW Fix** (INSERTED) - Fix per-row dynamic lookup filtering to match Talend behavior (completed 2026-04-15)
- [x] **Phase 6: Transform Group A -- Aggregation, Sort, Filter** - Deliver tAggregateRow, tSortRow, and tFilterRow with correct Talend behavior for the hardest transform bugs (completed 2026-04-15)
- [x] **Phase 7: Transform Group B -- Column, Join, Unite** - Deliver tFilterColumns, tJoin, and tUnite (two already functionally Green, tJoin has targeted fixes) (completed 2026-04-15)
- [x] **Phase 7.1: Manager Audit & BaseComponent Fixes** (INSERTED) - Fix 48 regressions and BaseComponent gaps surfaced by the manager-commit audit (REVIEW.md, REVIEW-engine.md, REVIEW-javabridge.md, TRIAGE.md) before Phase 8 (completed 2026-04-25)
- [x] **Phase 7.2: validate-config bug sweep** (INSERTED) - Defer content checks from _validate_config (Step 2) to _process (post-resolution); 5 Group A bugs fixed, 5 Group B verdicts, Rule 12 added (completed 2026-04-29)
- [x] **Phase 8: Code Components** - Deliver tJava, tJavaRow, python_component, and python_row_component with correct Talend semantics (completed 2026-04-29)
- [x] **Phase 9: tContextLoad & Routines** - Deliver tContextLoad with full policy support and Java/Python routine infrastructure
- [ ] **Phase 10: Iterate Support** - Deliver tFlowToIterate, tFileList, tFileExist and the engine iterate execution loop
- [ ] **Phase 11: Oracle Components** - Verify and deliver Oracle connection, input, output, and supporting components
- [ ] **Phase 12: Integration Testing & Performance** - End-to-end integration tests with real Talend jobs, output comparison, and performance optimization

## Phase Details

### Phase 1: Infrastructure Bug Fixes & Project Setup
**Goal**: The engine's base classes and shared infrastructure are correct and stable -- any component built on top of BaseComponent, GlobalMap, ContextManager, and TriggerManager can trust their behavior
**Depends on**: Nothing (first phase)
**Requirements**: ENG-01, ENG-02, ENG-03, ENG-04, ENG-05, ENG-06, ENG-07, ENG-08, ENG-09, ENG-10, ENG-11, ENG-12, ENG-13, ENG-14, ENG-15, ENG-16, ENG-17, ENG-18, ENG-19, ENG-20, ENG-21, ENG-22, ENG-23, TEST-01, TEST-02
**Success Criteria** (what must be TRUE):
  1. All 23 engine infrastructure bugs are fixed and verified -- GlobalMap.get() accepts defaults, config resolution handles arrays, triggers preserve != operators, streaming retains reject data
  2. Engine components use structured logging (no print statements) and throw typed exceptions (ETLError, ConfigurationError) instead of generic Exception
  3. BaseComponent template is standardized with correct lifecycle (validate_config wired in, config snapshot/restore for re-execution, REJECT flow routing)
  4. Config key alignment is complete -- converter output keys match engine input keys for all target components
  5. pytest infrastructure exists (conftest.py, fixtures, markers) and core infrastructure classes (GlobalMap, ContextManager, TriggerManager) have passing unit tests
**Plans:** 7 plans
Plans:
- [x] 01-01-PLAN.md -- Project setup (pyproject.toml, pytest infrastructure)
- [x] 01-02-PLAN.md -- GlobalMap rewrite + exhaustive tests
- [x] 01-03-PLAN.md -- ContextManager rewrite + exhaustive tests
- [x] 01-04-PLAN.md -- TriggerManager rewrite + exceptions refinement + exhaustive tests
- [x] 01-05-PLAN.md -- BaseComponent + BaseIterateComponent rewrite
- [x] 01-06-PLAN.md -- BaseComponent exhaustive tests + engine.py minimal updates
- [x] 01-07-PLAN.md -- Standards docs (ENGINE_COMPONENT_PATTERN.md, ENGINE_TEST_PATTERN.md)

### Phase 2: Java Bridge Reliability
**Goal**: The Java bridge reliably serializes all data types, syncs context/globalMap bidirectionally, and handles JVM lifecycle -- so all downstream components using Java expressions can depend on correct bridge behavior
**Depends on**: Phase 1
**Requirements**: BRDG-01, BRDG-02, BRDG-03, BRDG-04, BRDG-05, BRDG-06
**Success Criteria** (what must be TRUE):
  1. Arrow serialization handles all data types (date, timestamp, decimal) using schema-driven conversion instead of data inference from first non-null value
  2. Py4J is upgraded to 0.10.9.9 with retry-on-empty-response, eliminating intermittent bridge failures
  3. Context and globalMap sync bidirectionally at every bridge call site -- not just some code paths
  4. JAR/library loading is robust with proper classpath management, and compiled script synchronization works correctly
**Plans:** 4 plans
Plans:
- [x] 02-01-PLAN.md -- Python type mapping module + bridge.py rewrite (schema-driven serialization, sync-after-every-call)
- [x] 02-02-PLAN.md -- Java bridge rewrite (decompose JavaBridge.java into 4 classes) + pom.xml updates
- [x] 02-03-PLAN.md -- JavaBridgeManager updates (fail-fast, log level) + Python unit tests (type mapping, serialization, sync)
- [x] 02-04-PLAN.md -- Java JAR build + integration tests (12-type round-trip, compiled script verification)

### Phase 3: Execution Loop Restructure
**Goal**: The engine can execute multi-subjob jobs with correct component ordering, data routing between components, trigger firing after subjob completion, and stall detection
**Depends on**: Phase 1
**Requirements**: EXEC-01, EXEC-02, EXEC-03, EXEC-07, PERF-01
**Success Criteria** (what must be TRUE):
  1. A multi-subjob job executes with components running in correct topological order within each subjob
  2. Data flows correctly between components -- main output, reject output, and iterate output each route to the correct downstream component
  3. OnSubjobOk triggers fire after all components in a subjob complete (not after each individual component)
  4. Engine raises an error with clear diagnostics when components are unreachable due to missing connections (no silent stalls)
  5. Streaming mode processes chunks without dropping reject data
**Plans:** 4/4 plans complete
Plans:
- [x] 03-01-PLAN.md -- Component registry + StubComponent test fixture + registry tests
- [x] 03-02-PLAN.md -- ExecutionPlan (DAG, topo sort, validation) + tests
- [x] 03-03-PLAN.md -- OutputRouter (data flow routing, memory management) + tests
- [x] 03-04-PLAN.md -- Executor + engine.py rewrite + orchestration tests

### Phase 4: File I/O Components
**Goal**: Users can read and write delimited files with full Talend feature parity -- encoding, delimiters, headers, CSV mode, field validation, file splitting, and all globalMap variables
**Depends on**: Phase 3
**Requirements**: FILD-01, FILD-02, FILD-03, FILD-04, FILD-05, FILD-06, FILD-07, FILD-08, FILD-09, FOLD-01, FOLD-02, FOLD-03, FOLD-04, FOLD-05, FOLD-06, TEST-03
**Success Criteria** (what must be TRUE):
  1. tFileInputDelimited reads files with correct encoding (ISO-8859-15 etc.), delimiters, headers/footers, and CSV mode handles RFC4180 quoted fields with embedded newlines
  2. Rows failing schema validation (wrong column count, bad types, invalid dates) route to the REJECT output flow instead of being silently dropped
  3. tFileOutputDelimited writes files with correct encoding, delimiters, append mode, header control, and splits large outputs into N-row files when configured
  4. All file I/O globalMap variables are set ({id}_FILENAME, {id}_ENCODING, {id}_FILE_NAME, FILE_EXIST_EXCEPTION)
  5. Engine unit tests pass for both tFileInputDelimited and tFileOutputDelimited covering all implemented features
**Plans:** 3 plans
Plans:
- [x] 04-01-PLAN.md -- FileInputDelimited rewrite + exhaustive unit tests
- [x] 04-02-PLAN.md -- FileOutputDelimited rewrite + exhaustive unit tests
- [x] 04-03-PLAN.md -- Package init update + integration tests with converter JSON

### Phase 5: tMap Component
**Goal**: tMap correctly performs joins, applies expressions and filters, routes to multiple outputs including reject, and handles all Talend join semantics (UNIQUE_MATCH, null handling, inner join rejects)
**Depends on**: Phase 2, Phase 3
**Requirements**: MAP-01, MAP-02, MAP-03, MAP-04, MAP-05, MAP-06, MAP-07, MAP-08, TEST-03
**Success Criteria** (what must be TRUE):
  1. UNIQUE_MATCH uses last-row semantics (matching Talend -- HashMap.put overwrites, confirmed by research), inner join rejects route separately from generic rejects, and null keys never match in joins
  2. tMap uses BaseComponent lifecycle instead of overriding execute(), and supports activateCondensedTool catch output for expression errors
  3. Auto type conversion for join columns works when ENABLE_AUTO_CONVERT_TYPE is configured
  4. RELOAD_AT_EACH_ROW lookup mode re-executes lookup per main row for parameterized lookups
  5. {id}_NB_LINE globalMap variable is correctly set after execution
  6. Engine unit tests pass for tMap covering join modes, reject routing, expressions, reload modes, and multi-output scenarios
**Plans:** 3 plans
Plans:
- [x] 05-01-PLAN.md -- Core tMap engine component rewrite (all MAP requirements)
- [x] 05-02-PLAN.md -- Exhaustive unit test suite (60-100 tests)
- [x] 05-03-PLAN.md -- Converter update for MAP-06 + integration tests

### Phase 05.1: Java Bridge tMap Fix (INSERTED)

**Goal**: Fix the Java bridge compiled script execution for tMap. Phase 2's rewrite broke RowWrapper Arrow type conversion (returns raw Arrow Text objects instead of Java Strings) and removed the 3-arg constructor that compiled tMap scripts depended on. Restore proper type-specific extraction, ensure compiled scripts work with correct Java types, verify with real .item file pipeline.
**Depends on**: Phase 5
**Requirements**: BRDG-06
**Success Criteria** (what must be TRUE):
  1. buildArrowRowWrapper (or RowWrapper constructor) converts Arrow VarChar to Java String, IntVector to int, Float8Vector to double, etc. -- not raw Arrow objects
  2. Compiled tMap scripts can create RowWrappers per row and access column values with correct Java types (string concat, comparisons, ternary all work)
  3. Real .item file pipeline (Job_tMap_0.1 with employees + country lookup) runs end-to-end: read CSV -> tMap join with Java expressions (string concat, ternary conditional) -> write CSV
  4. All 86 existing tMap unit tests + 11 integration tests still pass
**Plans:** 2/2 plans complete

Plans:
- [x] 05.1-01-PLAN.md -- Fix JavaBridge.java extractTypedValue + bridge integration tests
- [x] 05.1-02-PLAN.md -- Full pipeline test (employees + country_lookup CSVs) + regression gate

### Phase 05.2: tMap RELOAD_AT_EACH_ROW Fix (INSERTED)

**Goal**: Fix RELOAD_AT_EACH_ROW lookup mode in tMap to match Talend behavior. The current implementation has a working skeleton but 4 bugs prevent it from functioning correctly for real Talend jobs that use per-row dynamic lookup filtering.
**Depends on**: Phase 5, Phase 5.1
**Requirements**: MAP-08
**Success Criteria** (what must be TRUE):
  1. Lookup filter is NOT pre-applied before RELOAD_AT_EACH_ROW routing -- per-row loop receives the full unfiltered lookup
  2. Per-row filter expression can reference main row values via globalMap (e.g., filter lookup by current main row's region)
  3. Join key comparison is type-aware (int/float/string) -- not string-cast everything
  4. LEFT_OUTER_JOIN unmatched rows have proper NaN-filled lookup columns (no column misalignment)
  5. Existing LOAD_ONCE tests and all other tMap tests still pass (no regression)
**Plans:** 2/2 plans complete

Plans:
- [x] 05.2-01-PLAN.md -- Fix all 4 RELOAD_AT_EACH_ROW bugs in map.py + regression verification
- [x] 05.2-02-PLAN.md -- Comprehensive unit tests (10-15 new) + @pytest.mark.java integration test

### Phase 6: Transform Group A -- Aggregation, Sort, Filter
**Goal**: The three most complex transform components (tAggregateRow, tSortRow, tFilterRow) produce correct results matching Talend behavior, with all P0/P1 bugs fixed and full operator/function support
**Depends on**: Phase 3
**Requirements**: AGGR-01, AGGR-02, AGGR-03, AGGR-04, AGGR-05, AGGR-06, AGGR-07, AGGR-08, AGGR-09, SORT-01, SORT-02, SORT-03, SORT-04, SORT-05, FROW-01, FROW-02, FROW-03, FROW-04, FROW-05, FROW-06, FROW-07, TEST-08
**Success Criteria** (what must be TRUE):
  1. tAggregateRow correctly groups data, applies all aggregation functions (including list_object, union, population_std_dev), respects ignore_null and output_column config, and handles Decimal types correctly
  2. tFilterRow uses operator-function map (no eval()), supports all 14+ Talend operators and FUNCTION pre-transforms (LOWER, UPPER, LENGTH, TRIM, LTRIM, RTRIM, LEFT, RIGHT), and handles type-aware comparison correctly
  3. tSortRow distinguishes numeric/alphabetic/date sort types via pandas sort_values(key=), simplified to batch-only sort
  4. Engine unit tests pass for tAggregateRow, tSortRow, and tFilterRow covering all implemented features
**Plans:** 4 plans
Plans:
- [x] 06-01-PLAN.md -- AggregateRow rewrite (converter fix + engine component)
- [x] 06-02-PLAN.md -- SortRow rewrite
- [x] 06-03-PLAN.md -- FilterRows rewrite
- [x] 06-04-PLAN.md -- Combined test suites for all three components

### Phase 7: Transform Group B -- Column, Join, Unite
**Goal**: tFilterColumns, tJoin, and tUnite produce correct results -- tFilterColumns and tUnite (already functionally Green) get test coverage, and tJoin gets targeted bug fixes for case-insensitive joins, reject output, and null semantics
**Depends on**: Phase 3
**Requirements**: FCOL-01, FCOL-02, JOIN-01, JOIN-02, JOIN-03, JOIN-04, JOIN-05, JOIN-06, JOIN-07, JOIN-08, UNIT-01, UNIT-02
**Success Criteria** (what must be TRUE):
  1. tJoin performs case-insensitive joins without corrupting original data, correctly computes reject output, supports INCLUDE_LOOKUP toggle, and null keys never match
  2. tFilterColumns and tUnite have engine unit tests confirming their existing Green functionality works correctly with the restructured engine
  3. All three components set appropriate globalMap variables and handle edge cases (empty inputs, mismatched schemas)
**Plans:** 2 plans
Plans:
- [x] 07-01-PLAN.md -- tJoin full rewrite (8 bugs, reject_schema engine fix)
- [x] 07-02-PLAN.md -- FilterColumns + Unite rewrites + all tests (Join, FilterColumns, Unite)

### Phase 07.2: validate-config bug sweep -- move pre-resolution content checks to _process across 11 components (INSERTED) ✓ COMPLETED 2026-04-29

**Goal:** Eliminate the systemic bug class where `_validate_config()` (BaseComponent.execute() Step 2) inspects content of config fields BEFORE context resolution (Step 3), causing spurious rejection or crashes when fields hold context-var references. Establish a permanent process rule preventing recurrence in Phase 8 onward.
**Requirements**: VC-01, VC-02, VC-03, VC-04, TEST-08
**Depends on:** Phase 7
**Plans:** 4 plans

Plans:
- [ ] 07.2-01-PLAN.md -- Group A confirmed fixes (5 components: file_archive, file_input_positional, log_row, pivot_to_columns_delimited, file_input_excel)
- [ ] 07.2-02-PLAN.md -- Group B suspect verdicts (5 components: file_input_raw, fixed_flow_input, unique_row, context_load, send_mail)
- [ ] 07.2-03-PLAN.md -- Add Rule 12 to MANUAL_COMPONENT_AUTHORING.md
- [ ] 07.2-04-PLAN.md -- Verification + phase summary

### Phase 07.1: Manager Audit & BaseComponent Fixes (INSERTED)

**Goal**: BaseComponent and downstream components produce correct, Talend-compatible output after fixing 48 regressions and gaps surfaced by the out-of-band audit of manager commits (range 52dbada..f0f6351, 19 commits, 28 files), and the Java bridge JAR builds successfully on Mac/Linux. This phase exists because manager commits landed outside the GSD workflow and introduced regressions in already-shipped phases (Phase 1 BaseComponent, Phase 4 file I/O, Phase 6 aggregate, Phase 7 filter_rows) plus a build blocker. Phase 8 must NOT start until these are resolved -- code components inherit BaseComponent's behavior.
**Depends on**: Phase 1, Phase 4, Phase 6, Phase 7
**Requirements**: AUDIT-7.1 (umbrella -- see .planning/review/TRIAGE.md for the 48 in-scope items mapped to fix areas)
**Success Criteria** (what must be TRUE):
  1. BaseComponent's schema validation, column ordering, type coercion (datetime/Decimal/float/string with precision), reject flow, and die_on_error contract are correct -- no crashes on valid configs, no silent data loss (resolves CR-01, CR-02, WR-01/02/03, G-01..G-05, G-10, G-12)
  2. Phase 4 file I/O (FileInputDelimited, FileOutputDelimited) handles multi-char delimiters, escape characters, empty-output-with-header, date_patterns, and reject flow correctly without silent data mutation (resolves CR-03, CR-06, CR-09, ENG-CR-06, WR-04, WR-06, WR-17, ENG-WR-04/05/11, ENG-IN-04)
  3. Phase 6 AggregateRow operators match Talend semantics: list_object returns list, count honors ignore_null=False, sort preserves input order, median preserves financial precision (resolves CR-05, WR-09/10/11)
  4. Phase 7 FilterRows lifecycle invariants are restored: no manual validate_schema bypass, no config mutation mid-execute, errorMessage column does not collide with user columns (resolves WR-07/08, ENG-CR-05/07, ENG-WR-06/07/08)
  5. New Normalize component is vectorized, contract-correct (raises ConfigurationError, not returns list), and Talend-parity for discard_trailing_empty_str / dedupe / trim semantics (resolves ENG-CR-01/02/03, ENG-WR-01/02/03/10)
  6. Talend Java routines (Numeric.INT, TalendDate.parseDate, StringHandling.LEN/INSTR, Mathematical.CHAR) match Talend semantics for null handling, parse-error wrapping, and type coercion (resolves CR-07, CR-08, WR-14/15, IN-01)
  7. Java bridge JAR builds successfully on Mac/Linux: pom.xml uses portable Maven repo path (resolves CR-04)
  8. Converter orchestrator's _propagate_input_schemas works for multi-input components like tMap (case-correct connector lookup) (resolves ENG-CR-04)
  9. No regressions in already-passing tests for Phases 1, 4, 5, 5.1, 5.2, 6, 7, 9
**Plans:** 8/8 plans complete
Plans:
- [x] 07.1-01-PLAN.md -- BaseComponent rewrite (schema validation, ordering, datetime/Decimal/float precision, die_on_error reject routing, per-chunk streaming, treat_empty_as_null) -- Wave 1
- [x] 07.1-02-PLAN.md -- Maven pom.xml fix + vendored routines-system JAR + Apache 2.0 sign-off -- Wave 1
- [x] 07.1-03-PLAN.md -- file_output_delimited rewrite (multi-char sep, passthrough integrity, escape, JSON bool, CSV header) -- Wave 2
- [x] 07.1-04-PLAN.md -- file_input_delimited patch (DataValidationError leak, _fast_path reject indices, no-schema warning) -- Wave 2
- [x] 07.1-05-PLAN.md -- filter_rows engine + converter patch + folded ENG-CR-04 multi-input schema propagation -- Wave 2
- [x] 07.1-06-PLAN.md -- aggregate_row patch (list_object as Python list, union dedupe, median precision warn, sort preserve order; WR-10 documented WRONG) -- Wave 2
- [x] 07.1-07-PLAN.md -- normalize.py rewrite (vectorized, ConfigurationError, Talend ordering discard->trim->dedupe, trailing-only discard) -- Wave 2
- [x] 07.1-08-PLAN.md -- Java routines patches (WR-15 INSTR bounds, WR-16 Float.valueOf, CR-08 partial parseDate; CR-07/WR-14/IN-01 documented WRONG with regression guards) -- Wave 2

### Phase 8: Code Components
**Goal**: tJava, tJavaRow, python_component, and python_row_component all execute code with correct Talend semantics, proper import support, and secure execution
**Depends on**: Phase 2
**Requirements**: JAVA-01, JAVA-02, JAVA-03, JROW-01, JROW-02, JROW-03, JROW-04, PYCO-01, PYCO-02, PYCO-03, PYRO-01, PYRO-02, PYRO-03, TEST-07, PERF-02
**Success Criteria** (what must be TRUE):
  1. tJava and tJavaRow execute Java code with import support, and context/globalMap access matches Talend behavior including REJECT flow for per-row errors
  2. python_component and python_row_component mirror tJava/tJavaRow patterns, use secure execution namespace (no os/sys), and python_row_component uses compiled code execution (compile once, exec per row)
  3. Duplicated _get_context_dict() is consolidated into BaseComponent or shared mixin
  4. Engine unit tests pass for all four code components
**Plans:** 6/6 plans complete

Plans:
- [x] 08-01-PLAN.md -- CodeComponentMixin extraction + java_component.py rewrite (one-shot tJava with imports prepend) -- Wave 1
- [x] 08-02-PLAN.md -- python_component.py rewrite (one-shot tPython with D-11 secure namespace) -- Wave 2
- [x] 08-03-PLAN.md -- java_row_component.py rewrite (per-row tJavaRow with NO REJECT -- Talend parity revision 2) -- Wave 3
- [x] 08-04-PLAN.md -- python_row_component.py rewrite (per-row tPythonRow with compile-once + errorMessage-only REJECT, revision 2) -- Wave 3
- [x] 08-05-PLAN.md -- java_bridge fixture wiring + engine-level smoke tests + checkpoint -- Wave 4
- [x] 08-06-PLAN.md -- 08-PHASE-SUMMARY + ROADMAP/STATE close-out (records revision-2 parity corrections + D-26 supersession) -- Wave 5

### Phase 9: tContextLoad & Routines
**Goal**: Jobs can dynamically load context variables from data flows with full policy control, and custom Java/Python routines are discoverable and callable from expressions
**Depends on**: Phase 2, Phase 8
**Requirements**: CTXL-01, CTXL-02, CTXL-03, CTXL-04, ROUT-01, ROUT-02, ROUT-03
**Success Criteria** (what must be TRUE):
  1. tContextLoad honors DIE_ON_ERROR flag, correctly applies LOAD_NEW_VARIABLE and NOT_LOAD_OLD_VARIABLE policies (WARNING/ERROR/NO_WARNING), and preserves type information on reload
  2. Java routines are callable from Java expressions executed via the bridge, matching Talend's routine.jar behavior
  3. Python routines load via PythonRoutineManager and are callable from Python expressions and components
  4. Routines referenced by job configs are auto-discovered and loaded at job startup
**Plans:** 2 plans
Plans:
- [x] 09-01-PLAN.md -- tContextLoad rewrite with full policy support + exhaustive tests
- [x] 09-02-PLAN.md -- Java/Python routine loading enhancements + tests

### Phase 10: Iterate Support
**Goal**: The 30% of production jobs that use iterate patterns execute correctly -- tFlowToIterate converts rows to globalMap variables, tFileList/tFileExist iterate over files, and downstream subjobs re-execute per iteration item
**Depends on**: Phase 3
**Requirements**: EXEC-04, EXEC-05, EXEC-06, ITER-01, ITER-02, ITER-03, ITER-04, ITER-05, ITER-06, ITER-07, ITER-08, ITER-09, ITER-10, ITER-11, TEST-04
**Success Criteria** (what must be TRUE):
  1. tFlowToIterate converts each input row to globalMap variables in both DEFAULT_MAP and custom MAP modes, and sets {id}_CURRENT_ITERATE
  2. tFileList iterates over files matching a filemask with subdirectory inclusion and sort order options, setting all five globalMap variables (CURRENT_FILEPATH, CURRENT_FILENAME, etc.)
  3. tFileExist checks file existence and sets globalMap variables, with correct config key handling
  4. Downstream subjobs connected via iterate triggers re-execute once per iteration item, with components properly reset (state cleanup + config snapshot/restore) between iterations
  5. Engine unit tests pass for all three iterate components and the iterate execution loop
**Plans**: 8 plans
- [x] 10-01-PLAN.md -- BaseIterateComponent enhancements (9 hooks, iterator items, _CURRENT_ITERATION fix, execute() override)
- [ ] 10-02-PLAN.md -- Executor _execute_iterate_body + ExecutionPlan body BFS + nested-iterate detection + OutputRouter helpers
- [ ] 10-03-PLAN.md -- tFileList engine component (16 params, 5 RETURN globalMap vars, glob/regex, sort, ERROR=true 0-match)
- [ ] 10-04-PLAN.md -- tFlowToIterate engine component + new iterate/ engine package (DEFAULT_MAP true/false, pd.NA handling)
- [ ] 10-05-PLAN.md -- Converter ENABLE_PARALLEL/NUMBER_PARALLEL extraction + engine_gap needs_review
- [ ] 10-06-PLAN.md -- ASCII-only iterate logging infrastructure (4-tier, threshold-aware, D-H1..H7)
- [ ] 10-07-PLAN.md -- Integration tests with both .item samples + @pytest.mark.java + coverage gate >=90%
- [ ] 10-08-PLAN.md -- tFileExist verify-only integration test (ITER-08, ITER-09, RUN_IF branching)

### Phase 11: Oracle Components
**Goal**: Jobs using Oracle databases can connect, read, write, and execute operations through the Python engine with the same behavior as Talend
**Depends on**: Phase 1
**Requirements**: ORAC-01, ORAC-02, ORAC-03, ORAC-04, ORAC-05
**Success Criteria** (what must be TRUE):
  1. Oracle connection component establishes connections using oracledb (not cx_Oracle) with proper credential and connection string handling
  2. Oracle input component reads data with correct type mapping between Oracle and Python/pandas types
  3. Oracle output component writes data with correct type handling, commit control, and batch sizing
  4. Supporting Oracle components (commit, rollback, close, row, SP, bulk exec) function correctly in job workflows
**Plans**: TBD

### Phase 12: Integration Testing & Performance
**Goal**: Real Talend jobs converted from .item XML run end-to-end through the Python engine and produce identical output to Talend, with acceptable performance for production workloads
**Depends on**: Phase 4, Phase 5, Phase 6, Phase 7, Phase 8, Phase 9, Phase 10, Phase 11
**Requirements**: TEST-05, TEST-06, PERF-03, PERF-04
**Success Criteria** (what must be TRUE):
  1. Integration tests convert real .item samples from tests/talend_xml_samples/, execute them through the engine, and verify output correctness
  2. Talend output comparison tests confirm identical results between Talend and the Python engine for the same input data and job configuration
  3. tMap Python-side expression handling is expanded to reduce Java bridge round-trips for common expressions
  4. tFilterRow uses compiled expressions with native pandas operations instead of per-row eval() for production-acceptable performance
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order. Phases 2 and 3 can run in parallel after Phase 1. Phases 4, 6, 7, 10 can start after Phase 3. Phase 5 requires both Phase 2 and 3. Phase 8 can start after Phase 2. Phase 11 can start after Phase 1.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure Bug Fixes & Project Setup | 7/7 | Complete | 2026-04-14 |
| 2. Java Bridge Reliability | 4/4 | Complete | 2026-04-14 |
| 3. Execution Loop Restructure | 4/4 | Complete | 2026-04-14 |
| 4. File I/O Components | 3/3 | Complete | 2026-04-15 |
| 5. tMap Component | 3/3 | Complete | 2026-04-15 |
| 5.1. Java Bridge tMap Fix | 2/2 | Complete | 2026-04-15 |
| 5.2. tMap RELOAD_AT_EACH_ROW Fix | 2/2 | Complete | 2026-04-15 |
| 6. Transform Group A -- Aggregation, Sort, Filter | 4/4 | Complete | 2026-04-15 |
| 7. Transform Group B -- Column, Join, Unite | 2/2 | Complete | 2026-04-15 |
| 8. Code Components | 6/6 | Complete | 2026-04-29 |
| 9. tContextLoad & Routines | 2/2 | Complete | - |
| 10. Iterate Support | 1/8 | In Progress|  |
| 11. Oracle Components | 0/TBD | Not started | - |
| 12. Integration Testing & Performance | 0/TBD | Not started | - |
