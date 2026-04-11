# Audit Report: tSortRow / SortRow

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tSortRow` |
| **V1 Engine Class** | `SortRow` |
| **Engine File** | `src/v1/engine/components/transform/sort_row.py` (396 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/sort_row.py` (119 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tSortRow")` decorator-based dispatch |
| **Registry Aliases** | `SortRow`, `tSortRow` |
| **Category** | Transform / Processing |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/sort_row.py` | Engine implementation (396 lines) |
| `src/converters/talend_to_v1/components/transform/sort_row.py` | Converter class (119 lines) |
| `tests/converters/talend_to_v1/components/test_sort_row.py` | Converter tests (38 tests, 10 test classes) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 5/5 unique params + 2 framework extracted; SORT/ORDER inversion fixed; phantoms removed (SORT_TYPE, EXTERNAL_SORT, BUFFER_SIZE); 3 needs_review for engine gaps |
| Engine Feature Parity | **Y** | 0 | 3 | 2 | 1 | Engine reads na_position/case_sensitive/chunk_size not in _java.xml; no sort type distinction (num vs alpha vs date); external sort pseudo-external |
| Code Quality | **G** | 0 | 0 | 0 | 0 | Converter follows gold standard pattern; clean stride-3 parser; well-documented |
| Performance & Memory | **Y** | 0 | 1 | 1 | 0 | External sort loads all data for final sort (defeats purpose); streaming collects all data |
| Testing | **Y** | 0 | 0 | 1 | 0 | 38 converter tests passing; no engine unit tests (D-64) |

**Overall: YELLOW -- Converter is gold standard. Engine has engine-only keys and HYBRID streaming risk.**

**Top Actions**:

1. Add engine support for sort type distinction (num/alpha/date) from criteria
2. Remove engine-only `na_position`, `case_sensitive`, `chunk_size` or add to converter
3. Fix external sort to use true k-way merge (not full re-sort)
4. Add engine unit tests
5. Address HYBRID streaming mode producing incorrect sort results

---

## 3. Talend Feature Baseline

### What tSortRow Does

tSortRow sorts input data based on one or more columns. It belongs to the Processing family and is available in all Talend products (Standard, MapReduce, Spark Batch, Spark Streaming variants). The component buffers all incoming rows into memory (or disk with the "Sort on disk" option), sorts them according to the configured criteria (column, sort type, sort order), and outputs the fully sorted dataset to downstream components via a Row link.

tSortRow is a **blocking component** -- it must receive ALL input rows before it can produce any output. This is a fundamental property of sorting: the last input row might belong at the first output position. In pipeline terms, tSortRow acts as a materialization point, breaking any streaming pipeline into pre-sort and post-sort segments.

**Source**: [tSortRow Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/tsortrow-standard-properties), Talaxie GitHub _java.xml
**Component family**: Processing (Integration)
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | Schema editor | -- | Column definitions. Output schema always matches input (sort does not change structure). |
| 2 | Criteria | `CRITERIA` | TABLE (stride-3) | `[]` | Sort criteria table with 3 fields per row. At least one criterion required. |
| 2a | -- Column | `COLNAME` | elementRef | first column | Schema column to sort by |
| 2b | -- Sort type | `SORT` | elementRef | `NUM` | Data type for comparison: NUM (numerical), ALPHA (alphabetical), DATE (date) |
| 2c | -- Order | `ORDER` | elementRef | `ASC` | Sort direction: ASC (ascending) or DESC (descending) |

**CRITICAL SEMANTIC NOTE**: The _java.xml column `SORT` is the **data type** (NUM/ALPHA/DATE), NOT the direction. The column `ORDER` is the **direction** (ASC/DESC). Previous converter versions had these inverted.

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 3 | Sort on disk | `EXTERNAL` | CHECK | `false` | Enable external sorting using temporary files on disk instead of JVM heap memory |
| 4 | Temp data directory path | `TEMPFILE` | DIRECTORY | `"__COMP_DEFAULT_FILE_DIR__/temp"` | Path for temporary sort files. Supports context variables. Only relevant when EXTERNAL is true |
| 5 | Create temp dir | `CREATEDIR` | CHECK | `true` | Auto-create temp directory if it does not exist. Only relevant when EXTERNAL is true |
| 6 | Buffer size | `EXTERNAL_SORT_BUFFERSIZE` | TEXT | `"1000000"` | Maximum rows to buffer in memory before flushing to disk. Only relevant when EXTERNAL is true |
| 7 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Capture processing metadata for tStatCatcher |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Input rows to sort |
| `FLOW` (Main) | Output | Row > Main | Sorted output rows (same schema as input) |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fired on successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fired on error |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total rows processed |

### 3.5 Behavioral Notes

1. tSortRow is a **blocking** component -- all rows must be received before any output is produced.
2. SORT column = data type (NUM/ALPHA/DATE), ORDER column = direction (ASC/DESC). These are commonly confused.
3. Multiple criteria define multi-level sorting: first row = primary key, second = secondary, etc.
4. NUM sort compares values numerically; ALPHA compares lexicographically (so "10" < "2" in ALPHA mode).
5. External sort (EXTERNAL=true) writes sorted chunks to disk for datasets larger than JVM heap.
6. EXTERNAL_SORT_BUFFERSIZE is a string type (TEXT) to support Java expressions, but the value is numeric.
7. CREATEDIR defaults to true in _java.xml (auto-create temp directory).

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a stride-3 `_parse_criteria()` module-level function to parse the CRITERIA TABLE, producing a list of `{column, sort_type, order}` dicts. Scalar parameters use `_get_bool()` and `_get_str()` from the base class.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `CRITERIA` (TABLE) | Yes | `criteria` | List of dicts with column/sort_type/order. Stride-3 parser. |
| 1a | `COLNAME` | Yes | `criteria[].column` | Column name, quote-stripped |
| 1b | `SORT` | Yes | `criteria[].sort_type` | Data type: num/alpha/date (lowered). Default "num" |
| 1c | `ORDER` | Yes | `criteria[].order` | Direction: asc/desc (lowered). Default "asc" |
| 2 | `EXTERNAL` | Yes | `external` | Bool, default False |
| 3 | `TEMPFILE` | Yes | `tempfile` | String, default `"__COMP_DEFAULT_FILE_DIR__/temp"` |
| 4 | `CREATEDIR` | Yes | `createdir` | Bool, default True per _java.xml |
| 5 | `EXTERNAL_SORT_BUFFERSIZE` | Yes | `external_sort_buffersize` | String for expression support, default "1000000" |
| 6 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param |
| 7 | `LABEL` | Yes | `label` | Framework param |

**Summary**: 5 of 5 unique parameters extracted (100%) + 2 framework params.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Converted via `convert_type()` |
| `nullable` | Yes | |
| `key` | Yes | |
| `length` | Yes | Only if >= 0 |
| `precision` | Yes | Only if >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by base class |

Schema direction: transform passthrough (`input == output`).

### 4.3 Expression Handling

TEMPFILE and EXTERNAL_SORT_BUFFERSIZE are extracted as strings to preserve context variable references and Java expressions. No expression evaluation is performed at conversion time.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| ~~CONV-SR-001~~ | ~~P0~~ | **FIXED** -- SORT/ORDER semantic inversion corrected. SORT now maps to sort_type (data type), ORDER maps to order (direction) |
| ~~CONV-SR-002~~ | ~~P1~~ | **FIXED** -- Phantom SORT_TYPE column removed from CRITERIA parsing |
| ~~CONV-SR-003~~ | ~~P1~~ | **FIXED** -- EXTERNAL_SORT renamed to EXTERNAL per _java.xml |
| ~~CONV-SR-004~~ | ~~P1~~ | **FIXED** -- BUFFER_SIZE renamed to EXTERNAL_SORT_BUFFERSIZE per _java.xml |
| ~~CONV-SR-005~~ | ~~P1~~ | **FIXED** -- CREATEDIR default corrected to true per _java.xml |
| ~~CONV-SR-006~~ | ~~P2~~ | **FIXED** -- Added needs_review entries for engine-only keys |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `na_position` | Engine reads 'na_position' (default 'last') but this is not a _java.xml param | engine_gap |
| 2 | `case_sensitive` | Engine reads 'case_sensitive' (default True) but this is not a _java.xml param | engine_gap |
| 3 | `chunk_size` | Engine reads 'chunk_size' (default 10000) but this is not a _java.xml param | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Multi-column sort | **Yes** | High | `_process()` line 167-176 | Supports multiple sort columns with per-column order |
| 2 | Ascending/Descending | **Yes** | High | `_process()` line 173 | Maps 'desc'/'descending' to False, else True |
| 3 | Sort type (NUM/ALPHA/DATE) | **No** | N/A | -- | Engine does not read sort_type from criteria. Uses pandas default comparison |
| 4 | External sort | **Partial** | Low | `_external_sort()` line 243 | Pseudo-external: chunks sorted to parquet files then ALL loaded back for final sort |
| 5 | Buffer size (max_memory_rows) | **Yes** | Medium | `_process()` line 149 | Auto-triggers external sort when rows exceed threshold |
| 6 | Temp directory | **Yes** | High | `_external_sort()` line 265 | Uses config temp_dir or system tempdir |
| 7 | Create temp dir | **No** | N/A | -- | Engine does not read createdir; uses `tempfile.mkdtemp()` which always creates |
| 8 | NaN positioning | **Yes** | High | `_process()` line 200 | Engine has na_position='first'/'last' (not a Talend feature) |
| 9 | Case-insensitive sort | **Yes** | Medium | `_process()` line 186-197 | Engine has case_sensitive flag (not a Talend feature). Creates temp lowercase columns |
| 10 | Blocking behavior | **Yes** | High | `_process()` | Full materialization before output |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-SR-001 | **P1** | Engine does not distinguish sort type (NUM/ALPHA/DATE). Pandas default comparison used for all columns. Alphabetical sort of numeric strings produces wrong order (e.g., "10" < "2"). |
| ENG-SR-002 | **P1** | External sort is pseudo-external: all chunks are loaded back into memory for final `pd.concat()` + `sort_values()`. Defeats the purpose for truly large datasets. |
| ENG-SR-003 | **P1** | Engine reads `na_position`, `case_sensitive`, `chunk_size` which are engine-only keys not present in _java.xml. These engine extras have no Talend equivalent. |
| ENG-SR-004 | **P2** | External sort uses `kind='mergesort'` implicitly via pandas default, not `kind='stable'` like in-memory sort. May produce different ordering for equal values. |
| ENG-SR-005 | **P2** | Engine does not read `createdir`. Uses `tempfile.mkdtemp()` which always creates a new directory, ignoring the user's configured temp path hierarchy. |
| ENG-SR-006 | **P3** | GlobalMap variables (`{id}_SORTED_BY`, `{id}_SORT_ORDERS`) only set in in-memory path, not in streaming or external sort paths. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Set in all paths |
| `{id}_SORTED_BY` | No | Partial | `global_map.put()` line 221 | Engine extra, only in in-memory path |
| `{id}_SORT_ORDERS` | No | Partial | `global_map.put()` line 222 | Engine extra, only in in-memory path |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-SR-001 | **P1** | `sort_row.py:193` | CROSS-CUTTING: Input DataFrame mutation. `input_data[temp_col] = ...` modifies the caller's DataFrame in-place during case-insensitive sort. Should use `.copy()` first. |
| BUG-SR-002 | **P1** | `sort_row.py:279` | External sort ascending list uses `sort_orders[j]` without bounds checking. If sort_orders is shorter than sort_columns, raises IndexError. |
| BUG-SR-003 | **P1** | `sort_row.py:376` | Streaming ascending list has `if i < len(sort_orders)` guard but silently drops columns that exceed sort_orders length, producing potentially wrong results. |
| BUG-SR-004 | **P2** | `sort_row.py:325-335` | External sort finally block: bare `except:` on `os.remove()` and `os.rmdir()` silently swallows all errors including KeyboardInterrupt. |
| BUG-SR-005 | **P2** | `sort_row.py:241` | `_is_streaming()` check: `hasattr(data, '__iter__')` matches list, dict, set, etc. Only generators should be treated as streaming. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-SR-001 | **P2** | Engine reads `external_sort` but _java.xml name is `EXTERNAL`. Config key should be `external` to match converter output. |
| NAME-SR-002 | **P2** | Engine reads `max_memory_rows` but _java.xml name is `EXTERNAL_SORT_BUFFERSIZE`. Config key should be `external_sort_buffersize`. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-SR-001 | **P2** | "Use `kind='stable'` for deterministic sort" | External sort path omits `kind='stable'` in chunk sort and final merge sort |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified. No eval(), exec(), or path traversal vectors in engine code.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- module-level `logger = logging.getLogger(__name__)` |
| Level usage | Good -- info for start/end, warning for empty input, error for failures |
| Sensitive data | Clean -- no data values logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | None -- uses generic Exception raise |
| Exception chaining | Missing -- `raise` preserves traceback but no `from` chaining |
| die_on_error handling | Not implemented -- engine has no die_on_error support for sort |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- all public methods fully typed |
| Parameter types | Good -- `Dict[str, Any]`, `Optional[pd.DataFrame]`, `List[str]` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-SR-001 | **P1** | External sort defeats purpose: all chunks are loaded back into memory for `pd.concat()` + `sort_values()`. True k-way merge sort needed for memory-constrained scenarios. |
| PERF-SR-002 | **P2** | Streaming sort collects ALL chunks into memory before sorting. For truly streaming pipelines, this creates a memory bottleneck equal to full dataset size. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Poor -- collects all data, sorts as batch |
| Memory threshold | Functional -- auto-triggers external sort at max_memory_rows |
| Large data handling | Poor -- external sort still loads everything for final merge |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 38 | `tests/converters/talend_to_v1/components/test_sort_row.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None (component-specific) |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-SR-001 | **P2** | No engine unit tests for SortRow component (D-64: Testing=Y not G) |

### 8.3 Recommended Test Cases

1. **Engine**: Multi-column sort with mixed types (int + string columns)
2. **Engine**: External sort trigger at max_memory_rows threshold
3. **Engine**: Streaming input sorting (verify all chunks collected)
4. **Engine**: Empty input and single-row input edge cases
5. **Engine**: Case-insensitive sorting with mixed-case string data
6. **Engine**: NaN values with na_position='first' vs 'last'

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | -- |
| P1 | 6 | ENG-SR-001, ENG-SR-002, ENG-SR-003, BUG-SR-001, BUG-SR-002, BUG-SR-003, PERF-SR-001 |
| P2 | 8 | ENG-SR-004, ENG-SR-005, BUG-SR-004, BUG-SR-005, NAME-SR-001, NAME-SR-002, STD-SR-001, PERF-SR-002, TEST-SR-001 |
| P3 | 1 | ENG-SR-006 |
| **Total** | **15** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | All 6 resolved (~~CONV-SR-001~~ through ~~CONV-SR-006~~) |
| Engine (ENG) | 6 | ENG-SR-001 through ENG-SR-006 |
| Bug (BUG) | 5 | BUG-SR-001 through BUG-SR-005 |
| Naming (NAME) | 2 | NAME-SR-001, NAME-SR-002 |
| Standards (STD) | 1 | STD-SR-001 |
| Performance (PERF) | 2 | PERF-SR-001, PERF-SR-002 |
| Testing (TEST) | 1 | TEST-SR-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `base_component.py` | HYBRID streaming mode via base class -- sort is blocking, streaming breaks correctness |

---

## 10. Recommendations

### Immediate (Before Production)

1. Fix input DataFrame mutation in case-insensitive sort path (BUG-SR-001)
2. Fix ascending list IndexError in external sort (BUG-SR-002)
3. Add sort type (NUM/ALPHA/DATE) support to engine (ENG-SR-001)

### Short-term (Hardening)

1. Replace pseudo-external sort with true k-way merge (ENG-SR-002, PERF-SR-001)
2. Fix streaming ascending list truncation (BUG-SR-003)
3. Align engine config keys with converter output: `external` not `external_sort`, `external_sort_buffersize` not `max_memory_rows` (NAME-SR-001, NAME-SR-002)
4. Add engine unit tests (TEST-SR-001)

### Long-term (Optimization)

1. Fix bare `except:` in external sort cleanup (BUG-SR-004)
2. Improve `_is_streaming()` detection (BUG-SR-005)
3. Set GlobalMap variables in all paths, not just in-memory (ENG-SR-006)

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| HYBRID streaming mode produces incorrect sort order | High | High | Sort is a blocking operation requiring full materialization. Base class HYBRID mode chunks data and calls `_process()` per chunk, producing partially-sorted chunks instead of a globally sorted result. Disable HYBRID mode for tSortRow or force batch execution mode. |
| External sort temp file cleanup on job failure | Medium | Medium | External sort creates temp files in `sort_dir`. The `finally` block cleans up, but if the process is killed (SIGKILL, OOM killer), temp files remain as orphans. Implement periodic temp directory cleanup or use OS-level temp file management. |
| Memory exhaustion without external sort | Medium | High | Large datasets without EXTERNAL=true can exhaust JVM/Python heap memory. No configurable memory limit in _java.xml (engine has max_memory_rows but it is not a Talend param). Monitor memory usage and enable external sort for large datasets. |
| Sort type mismatch producing wrong order | High | Medium | Engine ignores sort type (NUM/ALPHA/DATE), using pandas default comparison. Alphabetical sort on numeric string columns produces "1, 10, 2, 20" instead of "1, 2, 10, 20". Document limitation and add sort type support to engine. |

### High-Risk Job Patterns

1. **Large datasets without external sort**: Jobs sorting > 1M rows with EXTERNAL=false risk OOM
2. **Streaming pipelines with tSortRow**: HYBRID mode produces partially-sorted output instead of fully sorted
3. **Numeric strings with ALPHA sort type**: Engine ignores sort type, producing incorrect lexicographic order
4. **Multi-threaded jobs with external sort**: Shared temp directory without thread-safe naming could cause conflicts

### Safe Usage Patterns

1. **Small-to-medium datasets (< 100K rows)**: In-memory sort works reliably with correct column ordering
2. **Batch mode only**: Avoid HYBRID streaming mode for sort components
3. **Numeric columns with NUM sort type**: pandas default numeric comparison matches Talend behavior
4. **Single sort column, ASC/DESC**: Simple cases work correctly across all code paths

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `<https://github.com/Talaxie/tcommon-studio-se`> | CRITERIA TABLE columns (COLNAME, SORT, ORDER), param names (EXTERNAL, TEMPFILE, CREATEDIR, EXTERNAL_SORT_BUFFERSIZE), defaults |
| Talend 8.0 docs | `<https://help.qlik.com/talend/en-US/components/8.0/processing/tsortrow-standard-properties`> | Component behavior, parameter descriptions |
| Engine source | `src/v1/engine/components/transform/sort_row.py` (396 lines) | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/transform/sort_row.py` (119 lines) | Converter audit |

## Appendix B: Engine Config Key Mapping

This appendix documents the SORT/ORDER semantic correction and engine config key mapping.

### CRITERIA TABLE Semantic Correction

| _java.xml Column | Previous Converter Mapping | Corrected Mapping | Notes |
| ------------------- | --------------------------- | ------------------- | ------- |
| `COLNAME` | column (correct) | column (unchanged) | Column name |
| `SORT` | direction (asc/desc) **WRONG** | sort_type (num/alpha/date) **FIXED** | Data type for comparison |
| `ORDER` | (not mapped) | order (asc/desc) **ADDED** | Sort direction |
| `SORT_TYPE` (phantom) | data type (num/alpha/date) | **REMOVED** | Does not exist in _java.xml |

### Scalar Parameter Name Correction

| _java.xml Name | Previous Converter Name | Corrected Config Key | Notes |
| ---------------- | ------------------------ | --------------------- | ------- |
| `EXTERNAL` | `EXTERNAL_SORT` | `external` | Bool, default False |
| `TEMPFILE` | `TEMPFILE` (correct) | `tempfile` | String, default `"__COMP_DEFAULT_FILE_DIR__/temp"` |
| `CREATEDIR` | `CREATE_TEMP_DIR` | `createdir` | Bool, default True (was missing) |
| `EXTERNAL_SORT_BUFFERSIZE` | `BUFFER_SIZE` | `external_sort_buffersize` | String, default "1000000" |

### Engine vs Converter Key Mismatches

| Engine Reads | Converter Emits | Match? | Notes |
| ------------- | ----------------- | -------- | ------- |
| `sort_columns` (list) | `criteria` (list of dicts) | No | Engine expects flat list, converter emits structured criteria. Needs engine update. |
| `sort_orders` (list) | `criteria[].order` | No | Engine expects flat list, converter embeds in criteria dicts |
| `na_position` | -- | No | Engine-only key, no _java.xml equivalent |
| `case_sensitive` | -- | No | Engine-only key, no _java.xml equivalent |
| `external_sort` | `external` | No | Key name mismatch |
| `max_memory_rows` | `external_sort_buffersize` | No | Key name mismatch |
| `chunk_size` | -- | No | Engine-only key, no _java.xml equivalent |
| `temp_dir` | `tempfile` | No | Key name mismatch |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after tSortRow converter rewrite (SORT/ORDER inversion fixed, phantoms removed, gold standard)*
