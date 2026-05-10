# Requirements: DataPrep Engine Restructure

**Defined:** 2026-04-14
**Core Value:** Any Talend job using the target components must produce identical results when run through the Python engine

## v1 Requirements

Requirements for engine restructure milestone. Each maps to roadmap phases.

### Engine Core Infrastructure

- [x] **ENG-01**: Fix `_update_global_map()` crash — `value` variable undefined in base_component.py:304 (P0)
- [x] **ENG-02**: Fix `GlobalMap.get()` broken signature — missing `default` parameter in global_map.py:28 (P0)
- [x] **ENG-03**: Fix `replace_in_config` literal `[i]` bug — Java expressions in arrays never resolve, base_component.py:174 (P0)
- [x] **ENG-04**: Fix broken engine imports — aggregate component import chain, engine.py:40 (P0)
- [x] **ENG-05**: Fix context variable type conversion for all 16 mapped types, context_manager.py:168-186 (P0)
- [x] **ENG-06**: Fix trigger `!` replacement corrupting `!=` operators, trigger_manager.py:228 (P0)
- [x] **ENG-07**: Fix streaming mode silently dropping reject data, base_component.py:270-271 (P0)
- [x] **ENG-08**: Fix `_validate_config()` dead code — wire into execute() lifecycle (P1)
- [x] **ENG-09**: Fix BaseComponent `self.config` mutation via `resolve_dict()` making components non-re-executable (P1)
- [x] **ENG-10**: Fix OnSubjobOk trigger timing — fires after each component instead of after all subjob components complete (P1)
- [x] **ENG-11**: Replace all `print()` debug statements with `logger` across all engine components (P2)
- [x] **ENG-12**: Replace generic exceptions with custom exception hierarchy (ETLError, ConfigurationError, etc.) (P2)
- [x] **ENG-13**: Fix config key alignment between converter output and engine input — fieldseparator→delimiter, file_name→file_path, etc. (P0)
- [x] **ENG-14**: Fix encoding/delimiter/header default mismatches between Talend defaults and engine defaults (P1)
- [x] **ENG-15**: Create pyproject.toml with all Python dependencies pinned (P1)
- [x] **ENG-16**: Standardize engine component template — BaseComponent pattern as blueprint for all components (P1)
- [x] **ENG-17**: Implement REJECT flow routing in engine data flow — route reject DataFrames to downstream reject-connected components (P1)
- [x] **ENG-18**: Fix `resolve_dict` corrupting `python_code` fields during context resolution (P1)
- [x] **ENG-19**: Fix `validate_schema` inverted nullable logic (P1)
- [x] **ENG-20**: Fix `_execute_streaming` drops reject data for every component (P1)
- [x] **ENG-21**: Fix `self.config` mutation non-reentrant pattern — snapshot and restore for iterate (P1)
- [x] **ENG-22**: Fix converter `.find().get()` null-safety pattern across parsers (P2)
- [x] **ENG-23**: Discover and fix additional engine issues not captured in audit reports (P2)

### Execution Loop

- [x] **EXEC-01**: Decompose monolithic execution loop into `_execute_subjob()` with topological sort
- [x] **EXEC-02**: Extract `_route_component_outputs()` for data flow routing between components
- [x] **EXEC-03**: Extract `_build_execution_plan()` for DAG construction and dependency resolution
- [x] **EXEC-04**: Implement iterate execution — `_handle_iterate()` calling `_execute_subjob()` per iteration item
- [x] **EXEC-05**: Implement `BaseComponent.reset()` for state cleanup between iterate re-executions
- [x] **EXEC-06**: Implement config snapshot/restore for components re-executed in iterate loops
- [x] **EXEC-07**: Fix stall detection — raise error instead of silent warning when components are unreachable

### tFileInputDelimited

- [x] **FILD-01**: Fix config key mismatch — engine reads `delimiter` but converter outputs `fieldseparator`
- [x] **FILD-02**: Fix encoding default — honor ISO-8859-15 from config instead of engine's UTF-8 default
- [x] **FILD-03**: Implement REJECT output flow — capture rows failing schema validation (wrong field count, bad type)
- [x] **FILD-04**: Implement CSV mode (`CSV_OPTION`) with RFC4180 compliance for quoted fields with embedded newlines
- [x] **FILD-05**: Implement per-column trim (`TRIMSELECT` TABLE) — trim specific columns, not all
- [x] **FILD-06**: Implement `CHECK_FIELDS_NUM` — validate each row has correct column count, reject malformed
- [x] **FILD-07**: Implement `CHECK_DATE` — strict date format validation against schema patterns
- [x] **FILD-08**: Implement `{id}_FILENAME` and `{id}_ENCODING` globalMap variables
- [x] **FILD-09**: Implement advanced numeric separators (`THOUSANDS_SEPARATOR`, `DECIMAL_SEPARATOR`) for numeric columns only

### tMap

- [x] **MAP-01**: Fix UNIQUE_MATCH semantics — use first-row (Talend behavior) instead of `keep='last'`
- [x] **MAP-02**: Fix inner join reject routing — differentiate `rejectInnerJoin` from generic reject
- [x] **MAP-03**: Fix null join semantics — pandas `merge()` matches NaN==NaN but Talend/SQL does not
- [x] **MAP-04**: Refactor to use BaseComponent lifecycle instead of overriding entire `execute()` method
- [x] **MAP-05**: Implement catch output reject (`activateCondensedTool`) — capture expression evaluation errors
- [x] **MAP-06**: Implement auto type conversion for join columns (`ENABLE_AUTO_CONVERT_TYPE`)
- [x] **MAP-07**: Implement `{id}_NB_LINE` globalMap variable (fix via base class)
- [x] **MAP-08**: Implement RELOAD_AT_EACH_ROW lookup mode — re-execute lookup per main row for parameterized lookups (P1)

### tFileOutputDelimited

- [x] **FOLD-01**: Fix config key mismatch — delimiter key alignment with converter output
- [x] **FOLD-02**: Fix `INCLUDEHEADER` default — engine defaults True but Talend defaults False
- [x] **FOLD-03**: Fix encoding default — honor ISO-8859-15 from config
- [x] **FOLD-04**: Implement file splitting (`SPLIT`, `SPLIT_EVERY`) — split large outputs into N-row files
- [x] **FOLD-05**: Implement `FILE_EXIST_EXCEPTION` — prevent accidental overwrites (default true)
- [x] **FOLD-06**: Implement `{id}_FILE_NAME` globalMap variable

### tJava

- [ ] **JAVA-01**: Implement import statement support — prepend `imports` config to `java_code` before execution
- [ ] **JAVA-02**: Verify bidirectional context/globalMap sync after execution
- [ ] **JAVA-03**: Standardize component structure as engine component blueprint

### tJavaRow

- [ ] **JROW-01**: Implement import statement support — prepend `imports` config to `java_code`
- [ ] **JROW-02**: Implement REJECT output flow for per-row Java execution errors
- [ ] **JROW-03**: Verify input/output row access patterns match Talend semantics
- [ ] **JROW-04**: Standardize component structure as engine component blueprint

### tContextLoad

- [ ] **CTXL-01**: Implement `DIE_ON_ERROR` control — honor flag instead of always raising
- [ ] **CTXL-02**: Implement `LOAD_NEW_VARIABLE` policy (WARNING/ERROR/NO_WARNING) for keys not in job context
- [ ] **CTXL-03**: Implement `NOT_LOAD_OLD_VARIABLE` policy (WARNING/ERROR/NO_WARNING) for context keys not in flow
- [ ] **CTXL-04**: Verify context type preservation on reload

### tAggregateRow

- [x] **AGGR-01**: Fix `_ensure_output_columns` else-branch that nulls computed aggregation columns (P0)
- [x] **AGGR-02**: Fix output_column ignored in grouped mode — uses hardcoded column names instead of config (P1)
- [x] **AGGR-03**: Implement ignore_null support for aggregation functions (P1)
- [x] **AGGR-04**: Implement missing aggregation functions (list_object, union, population_std_dev) (P1)
- [x] **AGGR-05**: Fix per-operation merge creating O(n*ops) intermediate DataFrames — optimize to single pass (P2)
- [x] **AGGR-06**: Fix Decimal handling inconsistency in grouped mode (P2)
- [x] **AGGR-07**: Implement financial precision toggle for numeric aggregations (P2)
- [x] **AGGR-08**: Fix column collision in grouped mode (P2)
- [x] **AGGR-09**: Standardize component to engine component blueprint pattern (P3)

### tSortRow

- [x] **SORT-01**: Implement sort type distinction (numeric vs alphabetic vs date) from criteria (P1)
- [x] **SORT-02**: Fix external sort that loads all data for final sort defeating purpose (P1)
- [x] **SORT-03**: Fix streaming mode that collects all data (P1)
- [x] **SORT-04**: Remove engine-only config keys not in Talend _java.xml (na_position, case_sensitive, chunk_size) (P2)
- [x] **SORT-05**: Standardize component to engine component blueprint pattern (P3)

### tFilterRow

- [x] **FROW-01**: Replace eval() with AST-based expression parser for security (P0)
- [x] **FROW-02**: Implement all 14+ Talend operators (currently only 6 supported) (P1)
- [x] **FROW-03**: Implement FUNCTION pre-transforms (LOWER, UPPER, LENGTH, TRIM, etc.) (P1)
- [x] **FROW-04**: Fix string coercion in condition evaluation (P1)
- [x] **FROW-05**: Fix `.toList()` case error — should be `.tolist()` (P0 crash bug)
- [x] **FROW-06**: Replace row-by-row eval() with compiled expression + native pandas operations (P2)
- [x] **FROW-07**: Remove debug print statements, use logger (P2)

### tFilterColumns

- [x] **FCOL-01**: Add engine unit tests — component is functionally Green but untested (P2)
- [x] **FCOL-02**: Verify mode and keep_row_order engine-only keys work correctly (P2)

### tJoin

- [x] **JOIN-01**: Fix case-insensitive join lowercase corruption — join mutates original data (P0)
- [x] **JOIN-02**: Fix left outer join incorrect reject output (P1)
- [x] **JOIN-03**: Fix reject schema never populated (P1)
- [x] **JOIN-04**: Implement INCLUDE_LOOKUP toggle — control whether lookup columns appear in output (P1)
- [x] **JOIN-05**: Implement ERROR_MESSAGE globalMap variable (P1)
- [x] **JOIN-06**: Fix schema attribute mismatch dead code (P2)
- [x] **JOIN-07**: Fix double merge for reject computation — optimize to single pass (P2)
- [x] **JOIN-08**: Fix null join semantics — pandas merge matches NaN==NaN but Talend/SQL does not (P1)

### tUnite

- [x] **UNIT-01**: Add engine unit tests — component is functionally Green but untested (P2)
- [x] **UNIT-02**: Verify union behavior with mismatched schemas (P2)

### Python Components

- [ ] **PYCO-01**: Standardize python_component alongside tJava — same structure, same patterns
- [ ] **PYCO-02**: Remove `os` and `sys` from execution namespace — security risk
- [ ] **PYCO-03**: Consolidate duplicated `_get_context_dict()` into BaseComponent or shared mixin
- [ ] **PYRO-01**: Standardize python_row_component alongside tJavaRow — same structure, same patterns
- [ ] **PYRO-02**: Implement compiled code execution — compile once outside loop, exec per row
- [ ] **PYRO-03**: Verify REJECT flow works correctly for per-row errors

### Iterate Components

- [x] **ITER-01**: Implement tFlowToIterate engine component — convert each input row to globalMap variables
- [x] **ITER-02**: Implement tFlowToIterate DEFAULT_MAP mode — store as `{flowName}.{columnName}` in globalMap
- [x] **ITER-03**: Implement tFlowToIterate custom MAP mode — user-defined key-value pairs
- [x] **ITER-04**: Implement tFileList engine component — iterate files matching filemask in directory
- [x] **ITER-05**: Implement tFileList globalMap variables (`CURRENT_FILEPATH`, `CURRENT_FILENAME`, `CURRENT_FILEDIRECTORY`, `CURRENT_FILEEXTENSION`, `NB_FILE`)
- [x] **ITER-06**: Implement tFileList subdirectory inclusion (`INCLUDSUBDIR`)
- [x] **ITER-07**: Implement tFileList sort order options (`ORDER_BY_*`, ascending/descending)
- [x] **ITER-08**: Fix tFileExist config key mismatch — `file_name` vs `file_path`
- [x] **ITER-09**: Implement tFileExist globalMap variables (`{id}_EXISTS`, `{id}_FILENAME`)
- [x] **ITER-10**: Register all iterate components in `COMPONENT_REGISTRY`
- [x] **ITER-11**: Implement `{id}_CURRENT_ITERATE` globalMap variable for tFlowToIterate

### Java Bridge

- [ ] **BRDG-01**: Identify and fix data type serialization failures in Arrow (date, timestamp, decimal types)
- [ ] **BRDG-02**: Implement schema-driven Arrow serialization instead of data inference from first non-null value
- [ ] **BRDG-03**: Fix context/globalMap sync at every bridge call site — not just some code paths
- [ ] **BRDG-04**: Strengthen JAR/library loading — robust classpath management for tLibraryLoad equivalent
- [ ] **BRDG-05**: Upgrade Py4J Python to 0.10.9.9 (retry on empty response)
- [ ] **BRDG-06**: Fix compiled script synchronization in Java bridge

### Routines

- [ ] **ROUT-01**: Java routines — make custom utility functions callable from Java expressions
- [ ] **ROUT-02**: Python routines — extend PythonRoutineManager for general-purpose routine loading
- [ ] **ROUT-03**: Routine discovery from job config — auto-load routines referenced by jobs

### Oracle Components

- [x] **ORAC-01**: Verify status of Oracle engine implementations (present vs missing)
- [x] **ORAC-02**: Implement or fix Oracle connection component using oracledb (not cx_Oracle)
- [x] **ORAC-03**: Implement or fix Oracle input component
- [x] **ORAC-04**: Implement or fix Oracle output component
- [x] **ORAC-05**: Implement or fix Oracle supporting components (commit, rollback, close, row, SP, bulk exec)

### XML Components (Phase 12)

- [x] **XML-01**: The 4 input XML components (`tFileInputXML`, `tFileInputMSXML`, `tExtractXMLField`, `tXMLMap`) match Talaxie javajet behavior parameter-by-parameter; gaps surfaced by the Phase 12 audit (12-01-AUDIT.md) are either fixed in code OR converted to a conditional `needs_review` (D-E1 pattern) for explicitly out-of-scope sub-features (XSLT, XInclude, custom DTD, Document output for tXMLMap, lookup/join for tXMLMap, expression_filter for tXMLMap)
- [x] **XML-02**: A new `tFileOutputXML` engine component is built with full simple/flat XML emission (one row per ROW_TAG, columns->sub-elements or attributes via MAPPING) and registered alongside a new `FileOutputXMLConverter` class (one does not exist today; only `tAdvancedFileOutputXML` is registered)
- [x] **XML-03**: A new `tAdvancedFileOutputXML` engine component is built with hierarchical emission (ROOT/GROUP/LOOP TABLE-driven nesting, attributes via ATTRIBUTE flag, namespace support); converter `AdvancedFileOutputXmlConverter` already extracts all 33 params, so no converter rewrite needed; the 6 sub-features in the conditional needs_review list (DTD_VALID, XSL_VALID, OUTPUT_AS_XSD, ADD_DOCUMENT_AS_NODE, ADD_UNMAPPED_ATTRIBUTE, MERGE) emit needs_review per D-E1
- [x] **XML-04**: All 6 in-scope components are unified on lxml >= 4.9 (already pinned via the `xml` extra in pyproject.toml). `file_input_xml.py` is migrated from stdlib `xml.etree.ElementTree` to lxml. Threshold-switched DOM (`etree.parse`)/streaming (`etree.iterparse + element.clear(keep_tail=True)`) at the configured threshold (`xml_streaming_threshold_mb`, default 50 MB). Per-input-boundary secure-XMLParser flags (`resolve_entities=False, no_network=True, load_dtd=False`) -- substituting for the deprecated `defusedxml.lxml` per D-C4 caveat. Per-module 95% line coverage floor and per-parameter positive+negative test rule met

### Testing

- [x] **TEST-01**: Create pytest infrastructure (conftest.py, fixtures, markers)
- [x] **TEST-02**: Engine unit tests for core infrastructure (GlobalMap, ContextManager, TriggerManager, JavaBridgeManager)
- [x] **TEST-03**: Engine unit tests for all 12 target components
- [x] **TEST-04**: Engine unit tests for iterate components (tFlowToIterate, tFileList, tFileExist)
- [x] **TEST-08**: Engine unit tests for new transform components (tAggregateRow, tSortRow, tFilterRow, tFilterColumns, tJoin, tUnite)
- [ ] **TEST-05**: Integration tests using real .item samples — convert → run → verify output
- [ ] **TEST-06**: Talend output comparison tests — verify identical results for same input data
- [x] **TEST-07**: Engine unit tests for Python components (python_component, python_row_component)
- [x] **TEST-09**: Full test suite achieves zero failures under `python -m pytest tests/`; all inherited pre-existing failures from Phases 1-12 resolved via root-cause source patches or verified test-expectation corrections; no xfail markers added; 10 STALE NeedsReview tests deleted (D-D1); test count net delta: -10 STALE deletions (Phase 13)
- [x] **TEST-10**: Per-module coverage baseline measured and recorded in `13-COVERAGE-BASELINE.md` covering all modules in `src/v1/engine/` and `src/converters/`; 6832 tests pass, 0 failed at measurement point; overall 75% coverage (19429 stmts, 4881 missed); baseline consumed by Phase 14 as the 95% per-module floor; reproducible via `python -m pytest tests/ --cov=src/v1/engine --cov=src/converters --cov-report=term-missing --cov-report=html -q` command documented in CLAUDE.md (Phase 13)

### Performance & Memory

- [x] **PERF-01**: Fix streaming mode — proper chunk processing without reject data loss
- [ ] **PERF-02**: Implement compiled code execution for PythonRowComponent (compile once, exec per row)
- [ ] **PERF-03**: Expand tMap Python-side expression handling to reduce Java bridge round-trips
- [ ] **PERF-04**: Replace FilterRows `eval()` per row with compiled expression + native pandas operations

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Advanced tMap Features

- **MAP-V2-02**: Disk-based lookup caching (`STORE_ON_DISK`, `ROWS_BUFFER_SIZE`)
- **MAP-V2-03**: Parallel lookup loading (`LKUP_PARALLELIZE`)
- **MAP-V2-04**: Fuzzy matching (Levenshtein/Jaccard distance thresholds)
- **MAP-V2-05**: BigDecimal hash/equals for join keys

### Advanced File Features

- **FILE-V2-01**: Compressed file reading/writing (ZIP)
- **FILE-V2-02**: Random sampling (`RANDOM`, `NB_RANDOM`)
- **FILE-V2-03**: Split record / multi-line fields
- **FILE-V2-04**: Output stream mode (`USESTREAM`)
- **FILE-V2-05**: Hex/octal decoding

### Remaining Components

- **COMP-V2-01**: Remaining ~74 engine components brought to production quality (following patterns from this milestone)
- **COMP-V2-02**: MSSQL database components (tMSSqlConnection, tMSSqlInput)
- **COMP-V2-03**: Control components (tDie, tWarn, tSleep, tSendMail, tLoop, tParallelize, tRunJob, tPrejob, tPostjob)
- **COMP-V2-04**: Remaining file components (tFileInputExcel, tFileOutputExcel, tFileInputJSON, tFileInputXML, etc.)
- **COMP-V2-05**: Remaining transform components (tNormalize, tDenormalize, tExtract*, tXMLMap, tRowGenerator, etc.)
- **COMP-V2-06**: Python/Swift components (PythonDataFrameComponent, SwiftTransformer, SwiftBlockFormatter)
- **COMP-V2-07**: Additional iterate/aggregate (tForeach, tLoop, tUniqueRow, tAggregateSortedRow)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Legacy complex_converter removal | Not blocking production, cleanup for later |
| UI job designer frontend | Separate concern, independent development track |
| Distributed/parallel execution | Single-threaded sufficient for current workloads |
| Docker/container deployment | Linux server deployment, containerization deferred |
| pandas 3.0 upgrade | Breaking changes (CoW, Arrow strings) require separate milestone |
| Web service / API layer | Batch ETL system, no web interface needed |
| Remaining ~74 engine components | Follow patterns established by the 12 priority components in future milestones |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENG-01 | Phase 1 | Complete |
| ENG-02 | Phase 1 | Complete |
| ENG-03 | Phase 1 | Complete |
| ENG-04 | Phase 1 | Complete |
| ENG-05 | Phase 1 | Complete |
| ENG-06 | Phase 1 | Complete |
| ENG-07 | Phase 1 | Complete |
| ENG-08 | Phase 1 | Complete |
| ENG-09 | Phase 1 | Complete |
| ENG-10 | Phase 1 | Complete |
| ENG-11 | Phase 1 | Complete |
| ENG-12 | Phase 1 | Complete |
| ENG-13 | Phase 1 | Complete |
| ENG-14 | Phase 1 | Complete |
| ENG-15 | Phase 1 | Complete |
| ENG-16 | Phase 1 | Complete |
| ENG-17 | Phase 1 | Complete |
| ENG-18 | Phase 1 | Complete |
| ENG-19 | Phase 1 | Complete |
| ENG-20 | Phase 1 | Complete |
| ENG-21 | Phase 1 | Complete |
| ENG-22 | Phase 1 | Complete |
| ENG-23 | Phase 1 | Complete |
| EXEC-01 | Phase 3 | Complete |
| EXEC-02 | Phase 3 | Complete |
| EXEC-03 | Phase 3 | Complete |
| EXEC-04 | Phase 10 | Complete |
| EXEC-05 | Phase 10 | Complete |
| EXEC-06 | Phase 10 | Complete |
| EXEC-07 | Phase 3 | Complete |
| FILD-01 | Phase 4 | Complete |
| FILD-02 | Phase 4 | Complete |
| FILD-03 | Phase 4 | Complete |
| FILD-04 | Phase 4 | Complete |
| FILD-05 | Phase 4 | Complete |
| FILD-06 | Phase 4 | Complete |
| FILD-07 | Phase 4 | Complete |
| FILD-08 | Phase 4 | Complete |
| FILD-09 | Phase 4 | Complete |
| MAP-01 | Phase 5 | Complete |
| MAP-02 | Phase 5 | Complete |
| MAP-03 | Phase 5 | Complete |
| MAP-04 | Phase 5 | Complete |
| MAP-05 | Phase 5 | Complete |
| MAP-06 | Phase 5 | Complete |
| MAP-07 | Phase 5 | Complete |
| MAP-08 | Phase 5 | Complete |
| FOLD-01 | Phase 4 | Complete |
| FOLD-02 | Phase 4 | Complete |
| FOLD-03 | Phase 4 | Complete |
| FOLD-04 | Phase 4 | Complete |
| FOLD-05 | Phase 4 | Complete |
| FOLD-06 | Phase 4 | Complete |
| JAVA-01 | Phase 8 | Pending |
| JAVA-02 | Phase 8 | Pending |
| JAVA-03 | Phase 8 | Pending |
| JROW-01 | Phase 8 | Pending |
| JROW-02 | Phase 8 | Pending |
| JROW-03 | Phase 8 | Pending |
| JROW-04 | Phase 8 | Pending |
| CTXL-01 | Phase 9 | Pending |
| CTXL-02 | Phase 9 | Pending |
| CTXL-03 | Phase 9 | Pending |
| CTXL-04 | Phase 9 | Pending |
| AGGR-01 | Phase 6 | Complete |
| AGGR-02 | Phase 6 | Complete |
| AGGR-03 | Phase 6 | Complete |
| AGGR-04 | Phase 6 | Complete |
| AGGR-05 | Phase 6 | Complete |
| AGGR-06 | Phase 6 | Complete |
| AGGR-07 | Phase 6 | Complete |
| AGGR-08 | Phase 6 | Complete |
| AGGR-09 | Phase 6 | Complete |
| SORT-01 | Phase 6 | Complete |
| SORT-02 | Phase 6 | Complete |
| SORT-03 | Phase 6 | Complete |
| SORT-04 | Phase 6 | Complete |
| SORT-05 | Phase 6 | Complete |
| FROW-01 | Phase 6 | Complete |
| FROW-02 | Phase 6 | Complete |
| FROW-03 | Phase 6 | Complete |
| FROW-04 | Phase 6 | Complete |
| FROW-05 | Phase 6 | Complete |
| FROW-06 | Phase 6 | Complete |
| FROW-07 | Phase 6 | Complete |
| FCOL-01 | Phase 7 | Complete |
| FCOL-02 | Phase 7 | Complete |
| JOIN-01 | Phase 7 | Complete |
| JOIN-02 | Phase 7 | Complete |
| JOIN-03 | Phase 7 | Complete |
| JOIN-04 | Phase 7 | Complete |
| JOIN-05 | Phase 7 | Complete |
| JOIN-06 | Phase 7 | Complete |
| JOIN-07 | Phase 7 | Complete |
| JOIN-08 | Phase 7 | Complete |
| UNIT-01 | Phase 7 | Complete |
| UNIT-02 | Phase 7 | Complete |
| PYCO-01 | Phase 8 | Pending |
| PYCO-02 | Phase 8 | Pending |
| PYCO-03 | Phase 8 | Pending |
| PYRO-01 | Phase 8 | Pending |
| PYRO-02 | Phase 8 | Pending |
| PYRO-03 | Phase 8 | Pending |
| ITER-01 | Phase 10 | Complete |
| ITER-02 | Phase 10 | Complete |
| ITER-03 | Phase 10 | Complete |
| ITER-04 | Phase 10 | Complete |
| ITER-05 | Phase 10 | Complete |
| ITER-06 | Phase 10 | Complete |
| ITER-07 | Phase 10 | Complete |
| ITER-08 | Phase 10 | Complete |
| ITER-09 | Phase 10 | Complete |
| ITER-10 | Phase 10 | Complete |
| ITER-11 | Phase 10 | Complete |
| BRDG-01 | Phase 2 | Complete |
| BRDG-02 | Phase 2 | Complete |
| BRDG-03 | Phase 2 | Complete |
| BRDG-04 | Phase 2 | Complete |
| BRDG-05 | Phase 2 | Complete |
| BRDG-06 | Phase 2 | Complete |
| ROUT-01 | Phase 9 | Pending |
| ROUT-02 | Phase 9 | Pending |
| ROUT-03 | Phase 9 | Pending |
| ORAC-01 | Phase 11 | Complete |
| ORAC-02 | Phase 11 | Complete |
| ORAC-03 | Phase 11 | Complete |
| ORAC-04 | Phase 11 | Complete |
| ORAC-05 | Phase 11 | Complete |
| XML-01 | Phase 12 | Complete |
| XML-02 | Phase 12 | Complete |
| XML-03 | Phase 12 | Complete |
| XML-04 | Phase 12 | Complete |
| TEST-01 | Phase 1 | Complete |
| TEST-02 | Phase 1 | Complete |
| TEST-03 | Phase 4, 5 | Complete |
| TEST-04 | Phase 10 | Complete |
| TEST-05 | Phase 12 | Pending |
| TEST-06 | Phase 12 | Pending |
| TEST-07 | Phase 8 | Complete |
| TEST-08 | Phase 6 | Complete |
| TEST-09 | Phase 13 | Complete |
| TEST-10 | Phase 13 | Complete |
| PERF-01 | Phase 3 | Complete |
| PERF-02 | Phase 8 | Pending |
| PERF-03 | Phase 12 | Pending |
| PERF-04 | Phase 12 | Pending |

**Coverage:**
- v1 requirements: 125 total
- Mapped to phases: 125
- Unmapped: 0

**Note:** TEST-03 covers unit tests for target components and is split across Phase 4 (file I/O tests) and Phase 5 (tMap tests). All other requirements map to exactly one phase.

---
*Requirements defined: 2026-04-14*
*Last updated: 2026-05-10 after Phase 13 closure (TEST-09, TEST-10 added and Complete)*
