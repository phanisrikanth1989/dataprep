# Requirements: DataPrep Engine Restructure

**Defined:** 2026-04-14
**Core Value:** Any Talend job using the target components must produce identical results when run through the Python engine

## v1 Requirements

Requirements for engine restructure milestone. Each maps to roadmap phases.

### Engine Core Infrastructure

- [ ] **ENG-01**: Fix `_update_global_map()` crash — `value` variable undefined in base_component.py:304 (P0)
- [ ] **ENG-02**: Fix `GlobalMap.get()` broken signature — missing `default` parameter in global_map.py:28 (P0)
- [ ] **ENG-03**: Fix `replace_in_config` literal `[i]` bug — Java expressions in arrays never resolve, base_component.py:174 (P0)
- [ ] **ENG-04**: Fix broken engine imports — aggregate component import chain, engine.py:40 (P0)
- [ ] **ENG-05**: Fix context variable type conversion for all 16 mapped types, context_manager.py:168-186 (P0)
- [ ] **ENG-06**: Fix trigger `!` replacement corrupting `!=` operators, trigger_manager.py:228 (P0)
- [ ] **ENG-07**: Fix streaming mode silently dropping reject data, base_component.py:270-271 (P0)
- [ ] **ENG-08**: Fix `_validate_config()` dead code — wire into execute() lifecycle (P1)
- [ ] **ENG-09**: Fix BaseComponent `self.config` mutation via `resolve_dict()` making components non-re-executable (P1)
- [ ] **ENG-10**: Fix OnSubjobOk trigger timing — fires after each component instead of after all subjob components complete (P1)
- [ ] **ENG-11**: Replace all `print()` debug statements with `logger` across all engine components (P2)
- [ ] **ENG-12**: Replace generic exceptions with custom exception hierarchy (ETLError, ConfigurationError, etc.) (P2)
- [ ] **ENG-13**: Fix config key alignment between converter output and engine input — fieldseparator→delimiter, file_name→file_path, etc. (P0)
- [ ] **ENG-14**: Fix encoding/delimiter/header default mismatches between Talend defaults and engine defaults (P1)
- [ ] **ENG-15**: Create pyproject.toml with all Python dependencies pinned (P1)
- [ ] **ENG-16**: Standardize engine component template — BaseComponent pattern as blueprint for all components (P1)
- [ ] **ENG-17**: Implement REJECT flow routing in engine data flow — route reject DataFrames to downstream reject-connected components (P1)
- [ ] **ENG-18**: Fix `resolve_dict` corrupting `python_code` fields during context resolution (P1)
- [ ] **ENG-19**: Fix `validate_schema` inverted nullable logic (P1)
- [ ] **ENG-20**: Fix `_execute_streaming` drops reject data for every component (P1)
- [ ] **ENG-21**: Fix `self.config` mutation non-reentrant pattern — snapshot and restore for iterate (P1)
- [ ] **ENG-22**: Fix converter `.find().get()` null-safety pattern across parsers (P2)
- [ ] **ENG-23**: Discover and fix additional engine issues not captured in audit reports (P2)

### Execution Loop

- [ ] **EXEC-01**: Decompose monolithic execution loop into `_execute_subjob()` with topological sort
- [ ] **EXEC-02**: Extract `_route_component_outputs()` for data flow routing between components
- [ ] **EXEC-03**: Extract `_build_execution_plan()` for DAG construction and dependency resolution
- [ ] **EXEC-04**: Implement iterate execution — `_handle_iterate()` calling `_execute_subjob()` per iteration item
- [ ] **EXEC-05**: Implement `BaseComponent.reset()` for state cleanup between iterate re-executions
- [ ] **EXEC-06**: Implement config snapshot/restore for components re-executed in iterate loops
- [ ] **EXEC-07**: Fix stall detection — raise error instead of silent warning when components are unreachable

### tFileInputDelimited

- [ ] **FILD-01**: Fix config key mismatch — engine reads `delimiter` but converter outputs `fieldseparator`
- [ ] **FILD-02**: Fix encoding default — honor ISO-8859-15 from config instead of engine's UTF-8 default
- [ ] **FILD-03**: Implement REJECT output flow — capture rows failing schema validation (wrong field count, bad type)
- [ ] **FILD-04**: Implement CSV mode (`CSV_OPTION`) with RFC4180 compliance for quoted fields with embedded newlines
- [ ] **FILD-05**: Implement per-column trim (`TRIMSELECT` TABLE) — trim specific columns, not all
- [ ] **FILD-06**: Implement `CHECK_FIELDS_NUM` — validate each row has correct column count, reject malformed
- [ ] **FILD-07**: Implement `CHECK_DATE` — strict date format validation against schema patterns
- [ ] **FILD-08**: Implement `{id}_FILENAME` and `{id}_ENCODING` globalMap variables
- [ ] **FILD-09**: Implement advanced numeric separators (`THOUSANDS_SEPARATOR`, `DECIMAL_SEPARATOR`) for numeric columns only

### tMap

- [ ] **MAP-01**: Fix UNIQUE_MATCH semantics — use first-row (Talend behavior) instead of `keep='last'`
- [ ] **MAP-02**: Fix inner join reject routing — differentiate `rejectInnerJoin` from generic reject
- [ ] **MAP-03**: Fix null join semantics — pandas `merge()` matches NaN==NaN but Talend/SQL does not
- [ ] **MAP-04**: Refactor to use BaseComponent lifecycle instead of overriding entire `execute()` method
- [ ] **MAP-05**: Implement catch output reject (`activateCondensedTool`) — capture expression evaluation errors
- [ ] **MAP-06**: Implement auto type conversion for join columns (`ENABLE_AUTO_CONVERT_TYPE`)
- [ ] **MAP-07**: Implement `{id}_NB_LINE` globalMap variable (fix via base class)

### tFileOutputDelimited

- [ ] **FOLD-01**: Fix config key mismatch — delimiter key alignment with converter output
- [ ] **FOLD-02**: Fix `INCLUDEHEADER` default — engine defaults True but Talend defaults False
- [ ] **FOLD-03**: Fix encoding default — honor ISO-8859-15 from config
- [ ] **FOLD-04**: Implement file splitting (`SPLIT`, `SPLIT_EVERY`) — split large outputs into N-row files
- [ ] **FOLD-05**: Implement `FILE_EXIST_EXCEPTION` — prevent accidental overwrites (default true)
- [ ] **FOLD-06**: Implement `{id}_FILE_NAME` globalMap variable

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

- [ ] **AGGR-01**: Fix `_ensure_output_columns` else-branch that nulls computed aggregation columns (P0)
- [ ] **AGGR-02**: Fix output_column ignored in grouped mode — uses hardcoded column names instead of config (P1)
- [ ] **AGGR-03**: Implement ignore_null support for aggregation functions (P1)
- [ ] **AGGR-04**: Implement missing aggregation functions (list_object, union, population_std_dev) (P1)
- [ ] **AGGR-05**: Fix per-operation merge creating O(n*ops) intermediate DataFrames — optimize to single pass (P2)
- [ ] **AGGR-06**: Fix Decimal handling inconsistency in grouped mode (P2)
- [ ] **AGGR-07**: Implement financial precision toggle for numeric aggregations (P2)
- [ ] **AGGR-08**: Fix column collision in grouped mode (P2)
- [ ] **AGGR-09**: Standardize component to engine component blueprint pattern (P3)

### tSortRow

- [ ] **SORT-01**: Implement sort type distinction (numeric vs alphabetic vs date) from criteria (P1)
- [ ] **SORT-02**: Fix external sort that loads all data for final sort defeating purpose (P1)
- [ ] **SORT-03**: Fix streaming mode that collects all data (P1)
- [ ] **SORT-04**: Remove engine-only config keys not in Talend _java.xml (na_position, case_sensitive, chunk_size) (P2)
- [ ] **SORT-05**: Standardize component to engine component blueprint pattern (P3)

### tFilterRow

- [ ] **FROW-01**: Replace eval() with AST-based expression parser for security (P0)
- [ ] **FROW-02**: Implement all 14+ Talend operators (currently only 6 supported) (P1)
- [ ] **FROW-03**: Implement FUNCTION pre-transforms (LOWER, UPPER, LENGTH, TRIM, etc.) (P1)
- [ ] **FROW-04**: Fix string coercion in condition evaluation (P1)
- [ ] **FROW-05**: Fix `.toList()` case error — should be `.tolist()` (P0 crash bug)
- [ ] **FROW-06**: Replace row-by-row eval() with compiled expression + native pandas operations (P2)
- [ ] **FROW-07**: Remove debug print statements, use logger (P2)

### tFilterColumns

- [ ] **FCOL-01**: Add engine unit tests — component is functionally Green but untested (P2)
- [ ] **FCOL-02**: Verify mode and keep_row_order engine-only keys work correctly (P2)

### tJoin

- [ ] **JOIN-01**: Fix case-insensitive join lowercase corruption — join mutates original data (P0)
- [ ] **JOIN-02**: Fix left outer join incorrect reject output (P1)
- [ ] **JOIN-03**: Fix reject schema never populated (P1)
- [ ] **JOIN-04**: Implement INCLUDE_LOOKUP toggle — control whether lookup columns appear in output (P1)
- [ ] **JOIN-05**: Implement ERROR_MESSAGE globalMap variable (P1)
- [ ] **JOIN-06**: Fix schema attribute mismatch dead code (P2)
- [ ] **JOIN-07**: Fix double merge for reject computation — optimize to single pass (P2)
- [ ] **JOIN-08**: Fix null join semantics — pandas merge matches NaN==NaN but Talend/SQL does not (P1)

### tUnite

- [ ] **UNIT-01**: Add engine unit tests — component is functionally Green but untested (P2)
- [ ] **UNIT-02**: Verify union behavior with mismatched schemas (P2)

### Python Components

- [ ] **PYCO-01**: Standardize python_component alongside tJava — same structure, same patterns
- [ ] **PYCO-02**: Remove `os` and `sys` from execution namespace — security risk
- [ ] **PYCO-03**: Consolidate duplicated `_get_context_dict()` into BaseComponent or shared mixin
- [ ] **PYRO-01**: Standardize python_row_component alongside tJavaRow — same structure, same patterns
- [ ] **PYRO-02**: Implement compiled code execution — compile once outside loop, exec per row
- [ ] **PYRO-03**: Verify REJECT flow works correctly for per-row errors

### Iterate Components

- [ ] **ITER-01**: Implement tFlowToIterate engine component — convert each input row to globalMap variables
- [ ] **ITER-02**: Implement tFlowToIterate DEFAULT_MAP mode — store as `{flowName}.{columnName}` in globalMap
- [ ] **ITER-03**: Implement tFlowToIterate custom MAP mode — user-defined key-value pairs
- [ ] **ITER-04**: Implement tFileList engine component — iterate files matching filemask in directory
- [ ] **ITER-05**: Implement tFileList globalMap variables (`CURRENT_FILEPATH`, `CURRENT_FILENAME`, `CURRENT_FILEDIRECTORY`, `CURRENT_FILEEXTENSION`, `NB_FILE`)
- [ ] **ITER-06**: Implement tFileList subdirectory inclusion (`INCLUDSUBDIR`)
- [ ] **ITER-07**: Implement tFileList sort order options (`ORDER_BY_*`, ascending/descending)
- [ ] **ITER-08**: Fix tFileExist config key mismatch — `file_name` vs `file_path`
- [ ] **ITER-09**: Implement tFileExist globalMap variables (`{id}_EXISTS`, `{id}_FILENAME`)
- [ ] **ITER-10**: Register all iterate components in `COMPONENT_REGISTRY`
- [ ] **ITER-11**: Implement `{id}_CURRENT_ITERATE` globalMap variable for tFlowToIterate

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

- [ ] **ORAC-01**: Verify status of Oracle engine implementations (present vs missing)
- [ ] **ORAC-02**: Implement or fix Oracle connection component using oracledb (not cx_Oracle)
- [ ] **ORAC-03**: Implement or fix Oracle input component
- [ ] **ORAC-04**: Implement or fix Oracle output component
- [ ] **ORAC-05**: Implement or fix Oracle supporting components (commit, rollback, close, row, SP, bulk exec)

### Testing

- [ ] **TEST-01**: Create pytest infrastructure (conftest.py, fixtures, markers)
- [ ] **TEST-02**: Engine unit tests for core infrastructure (GlobalMap, ContextManager, TriggerManager, JavaBridgeManager)
- [ ] **TEST-03**: Engine unit tests for all 12 target components
- [ ] **TEST-04**: Engine unit tests for iterate components (tFlowToIterate, tFileList, tFileExist)
- [ ] **TEST-08**: Engine unit tests for new transform components (tAggregateRow, tSortRow, tFilterRow, tFilterColumns, tJoin, tUnite)
- [ ] **TEST-05**: Integration tests using real .item samples — convert → run → verify output
- [ ] **TEST-06**: Talend output comparison tests — verify identical results for same input data
- [ ] **TEST-07**: Engine unit tests for Python components (python_component, python_row_component)

### Performance & Memory

- [ ] **PERF-01**: Fix streaming mode — proper chunk processing without reject data loss
- [ ] **PERF-02**: Implement compiled code execution for PythonRowComponent (compile once, exec per row)
- [ ] **PERF-03**: Expand tMap Python-side expression handling to reduce Java bridge round-trips
- [ ] **PERF-04**: Replace FilterRows `eval()` per row with compiled expression + native pandas operations

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Advanced tMap Features

- **MAP-V2-01**: RELOAD_AT_EACH_ROW lookup mode with caching
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

- **COMP-V2-01**: All remaining ~38 engine components brought to production quality
- **COMP-V2-02**: MSSQL database components
- **COMP-V2-03**: Additional control components (tLoop, tParallelize, tRunJob, tPrejob, tPostjob)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Legacy complex_converter removal | Not blocking production, cleanup for later |
| UI job designer frontend | Separate concern, independent development track |
| Distributed/parallel execution | Single-threaded sufficient for current workloads |
| Docker/container deployment | Linux server deployment, containerization deferred |
| pandas 3.0 upgrade | Breaking changes (CoW, Arrow strings) require separate milestone |
| Web service / API layer | Batch ETL system, no web interface needed |
| Remaining 44 engine components | Follow patterns from this milestone in v2 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENG-01 through ENG-23 | TBD | Pending |
| EXEC-01 through EXEC-07 | TBD | Pending |
| FILD-01 through FILD-09 | TBD | Pending |
| MAP-01 through MAP-07 | TBD | Pending |
| FOLD-01 through FOLD-06 | TBD | Pending |
| JAVA-01 through JAVA-03 | TBD | Pending |
| JROW-01 through JROW-04 | TBD | Pending |
| CTXL-01 through CTXL-04 | TBD | Pending |
| AGGR-01 through AGGR-09 | TBD | Pending |
| SORT-01 through SORT-05 | TBD | Pending |
| FROW-01 through FROW-07 | TBD | Pending |
| FCOL-01 through FCOL-02 | TBD | Pending |
| JOIN-01 through JOIN-08 | TBD | Pending |
| UNIT-01 through UNIT-02 | TBD | Pending |
| PYCO-01 through PYCO-03 | TBD | Pending |
| PYRO-01 through PYRO-03 | TBD | Pending |
| ITER-01 through ITER-11 | TBD | Pending |
| BRDG-01 through BRDG-06 | TBD | Pending |
| ROUT-01 through ROUT-03 | TBD | Pending |
| ORAC-01 through ORAC-05 | TBD | Pending |
| TEST-01 through TEST-08 | TBD | Pending |
| PERF-01 through PERF-04 | TBD | Pending |

**Coverage:**
- v1 requirements: 118 total
- Mapped to phases: 0 (pending roadmap creation)
- Unmapped: 118 ⚠️

---
*Requirements defined: 2026-04-14*
*Last updated: 2026-04-14 after initial definition*
