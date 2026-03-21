# Audit Report: tSortRow / SortRow

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tSortRow` |
| **V1 Engine Class** | `SortRow` |
| **Engine File** | `src/v1/engine/components/transform/sort_row.py` (397 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_sort_row()` (lines 860-889) AND `_map_component_parameters()` (lines 217-227) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tSortRow':` (lines 244-245) -> calls `parse_sort_row(node, component)` |
| **Registry Aliases** | `SortRow`, `tSortRow` (registered in `src/v1/engine/engine.py` lines 107-108) |
| **Category** | Transform / Processing |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/sort_row.py` | Engine implementation (397 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 860-889) | Dedicated `parse_sort_row()` method -- parses CRITERIA table from Talend XML |
| `src/converters/complex_converter/component_parser.py` (lines 217-227) | Deprecated `_map_component_parameters()` fallback for tSortRow -- ALSO runs before `parse_sort_row()` |
| `src/converters/complex_converter/converter.py` (lines 244-245) | Dispatch -- dedicated `elif` for `tSortRow`; calls `parse_sort_row()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ConfigurationError`, `DataValidationError`) |
| `src/v1/engine/components/transform/__init__.py` | Package exports (line 23: `from .sort_row import SortRow`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 3 | 2 | 1 | 4 of 8 Talend params extracted; missing sort type (num/alpha), case-insensitive sort, buffer size; dual-path converter conflict |
| Engine Feature Parity | **Y** | 0 | 4 | 3 | 1 | No sort type (num vs alpha) distinction; no case-insensitive sort in external mode; external sort is pseudo-external; missing globalMap vars |
| Code Quality | **R** | 3 | 6 | 5 | 1 | Cross-cutting base class bugs incl. HYBRID streaming mode producing incorrect sort order (P0); input DataFrame mutation; ascending list length mismatch; external sort finally block fragile; globalMap vars missing in streaming/external paths; null handling diverges from Talend on descending sorts; external sort missing stable sort; generator input crashes before streaming check |
| Performance & Memory | **Y** | 0 | 1 | 2 | 1 | External sort defeats purpose (loads all into memory for final sort); streaming sort collects all data; no true k-way merge |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: RED -- Not production-ready; 4 P0 issues (incl. cross-cutting HYBRID streaming mode producing incorrect results) and 15 P1 issues require resolution**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tSortRow Does

`tSortRow` sorts input data based on one or more columns. It belongs to the **Processing** family and is available in all Talend products (Standard, MapReduce, Spark Batch, Spark Streaming variants). The component buffers all incoming rows into memory (or disk, with the "Sort on disk" option), sorts them according to the configured criteria (column, sort type, sort order), and outputs the fully sorted dataset to downstream components via a Row link.

`tSortRow` is a **blocking component** -- it must receive ALL input rows before it can produce any output. This is a fundamental property of sorting: the last input row might belong at the first output position. In pipeline terms, this means `tSortRow` acts as a materialization point, breaking any streaming pipeline into pre-sort and post-sort segments.

**Source**: [tSortRow Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/tsortrow-standard-properties), [tSortRow Component Overview (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/tsortrow), [Configuring tSortRow (Talend Studio 8.0)](https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-05/configuring-tsortrow), [Configuring tSortRow (Talend Studio 7.3)](https://help.qlik.com/talend/en-us/studio-user-guide/7.3/configuring-tsortrow)

**Component family**: Processing (Integration)
**Available in**: All Talend products (Standard). Also available in Apache Spark Batch and Apache Spark Streaming variants.
**Purpose**: "Helps creating metrics and classification tables" by sorting input data.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines both the input and output structure. The output schema always matches the input schema for tSortRow (sort does not change column structure). |
| 3 | Criteria | `CRITERIA` | Table | -- | **Mandatory**. A table of sort criteria rows. Each row defines one sort level with three sub-parameters (see below). Multiple rows define multi-level sorting: the first row is the primary sort key, the second is the secondary sort key, etc. You must add at least one criterion by clicking the [+] button. |

**Criteria Table Columns**:

| Sub-Parameter | Talend XML elementRef | Type | Default | Description |
|---------------|----------------------|------|---------|-------------|
| Schema column | `COLNAME` | Dropdown (schema columns) | First column | The column to sort by. Selected from the component's schema definition. |
| Sort type (num or alpha) | `SORT_TYPE` | Dropdown: `num` / `alpha` | `alpha` | **`num`**: Numerical sorting -- values are compared as numbers. Used for integer, long, float, double, BigDecimal columns. **`alpha`**: Alphabetical sorting -- values are compared as strings using lexicographic (dictionary) order. Used for string columns. **Critical distinction**: Sorting the values `[1, 2, 10, 20]` alphabetically produces `[1, 10, 2, 20]` (string comparison), while numerically produces `[1, 2, 10, 20]` (value comparison). |
| Order (asc or desc) | `SORT` | Dropdown: `asc` / `desc` | `asc` | **`asc`**: Ascending order (smallest/earliest first). **`desc`**: Descending order (largest/latest first). |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 4 | Sort on disk | `EXTERNAL_SORT` | Boolean (CHECK) | `false` | Enable external sorting using temporary files on disk. When checked, tSortRow writes sorted chunks to temporary files on disk rather than holding all data in JVM heap memory. This allows sorting datasets much larger than available heap memory. When unchecked, all data is buffered in JVM memory. |
| 5 | Temp data directory path | `TEMPFILE` / `TEMP_DIR` | String (Expression) | System temp dir | File system path for storing temporary sort files. Only visible when "Sort on disk" is checked. Supports context variables and globalMap references (e.g., `"E:/Studio/workspace/temp" + ((Integer)globalMap.get("tCollector_1_THREAD_ID"))` for multi-threaded jobs where each thread needs its own temp directory). |
| 6 | Create temp data directory if not exists | `CREATE_TEMP_DIR` | Boolean (CHECK) | `false` | Auto-create the temporary data directory if it does not exist. Only visible when "Sort on disk" is checked. |
| 7 | Buffer size of external sort | `BUFFER_SIZE` | Integer | `1000000` | Maximum number of rows to buffer in memory before flushing to disk. "The more rows and/or columns you process, the higher the value needs to be to prevent the Job from automatically stopping." Only visible when "Sort on disk" is checked. This controls memory usage vs disk I/O tradeoff. |
| 8 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Input rows to be sorted. tSortRow buffers ALL input rows before producing any output. This is mandatory -- tSortRow requires exactly one input flow. |
| `FLOW` (Main) | Output | Row > Main | Sorted rows in the order specified by the criteria. All columns from the input schema are preserved. Row count equals input row count (no rows are added or removed by sorting). |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Used for chaining subjobs. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. More granular than SUBJOB_OK. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. The target component only executes if the condition evaluates to true. |

**Important**: `tSortRow` does **NOT** have a `REJECT` output flow. Unlike `tFilterRow` or `tFileInputDelimited`, sorting cannot produce rejected rows -- every input row has a valid sort position. If a sort operation fails (e.g., comparing incompatible types), the entire component fails rather than rejecting individual rows.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows processed (input = output for sort). This is the primary row count variable. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully output. Always equals `NB_LINE` for tSortRow since no rows are rejected. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rejected rows. Always 0 for tSortRow since sort cannot produce rejects. |
| `{id}_ERROR_MESSAGE` | String | On error | Error message generated by the component if it fails. Only available if "Die on error" is unchecked. Official Talend documentation explicitly lists this variable. |

**Note on NB_LINE**: Like all Talend components, `NB_LINE` is only available AFTER the component completes execution. It cannot be accessed during the current subjob's data flow. Since tSortRow is a blocking component that buffers all rows, `NB_LINE` is always set to the total input row count.

### 3.5 Behavioral Notes

1. **Blocking nature**: `tSortRow` must receive ALL input rows before producing any output. In a pipeline `A -> tSortRow -> B`, component B receives zero rows until A has finished sending all rows to tSortRow. This is unavoidable for a correct sort operation, but has implications for memory usage and pipeline latency.

2. **Sort stability**: Talend's tSortRow implements a **stable sort**. When two rows have equal values for all sort criteria, they retain their original relative order from the input. This is important for multi-level sorting: sorting by `[name ASC, age DESC]` first groups by name alphabetically, then within each name group orders by age descending, preserving original order for rows with identical name AND age.

3. **Sort type semantics**: The `num` vs `alpha` distinction is critical for correctness:
   - `num` (numerical): Values are compared as numbers. String representations of numbers are parsed to their numeric value before comparison. `"10"` is greater than `"2"`.
   - `alpha` (alphabetical): Values are compared as strings using Java's `String.compareTo()` (lexicographic Unicode order). `"10"` comes before `"2"` because `'1' < '2'` in character comparison.
   - Using the wrong sort type is a common source of data bugs in Talend jobs.

4. **Null handling**: In Talend's Java-generated sort code, null values are handled specially. By default, nulls sort to the end (after all non-null values) in ascending order, and to the beginning in descending order. This matches Java's `Comparator.nullsLast()` behavior.

5. **Case sensitivity**: Alphabetical sorting in Talend is **case-sensitive** by default. Uppercase letters sort before lowercase letters in Unicode order (e.g., `"Banana"` comes before `"apple"` because `'B' < 'a'`). To achieve case-insensitive sorting, users typically add a `tMap` before tSortRow that creates a lowercase copy of the sort column, sort by the lowercase column, then drop it.

6. **External sort (Sort on disk)**: When enabled, tSortRow uses a disk-based merge sort algorithm:
   - Input rows are buffered up to `BUFFER_SIZE` rows in memory
   - When the buffer is full, it is sorted and flushed to a temporary file in the configured temp directory
   - After all input is processed, the sorted temporary files are merged using a k-way merge algorithm
   - This allows sorting datasets larger than available JVM heap memory
   - Temporary files are cleaned up after sorting completes
   - Performance is slower than in-memory sort due to disk I/O

7. **Multi-threaded considerations**: When using tSortRow with parallel execution (tPartitioner/tDepartitioner), each thread must have its own temporary directory path. The recommended pattern is to append the thread ID from globalMap: `"path" + ((Integer)globalMap.get("tCollector_1_THREAD_ID"))`.

8. **Schema pass-through**: The output schema of tSortRow is always identical to its input schema. Sorting changes row order but never modifies column structure, column types, or column values.

9. **Memory implications**: For in-memory sort (default), all input rows are held in JVM heap. A dataset with N rows and M columns of average size S bytes requires approximately `N * M * S` bytes of heap. For 10 million rows with 20 columns averaging 50 bytes each, this is approximately 10GB. The "Sort on disk" option addresses this by limiting in-memory usage to `BUFFER_SIZE` rows.

10. **Dynamic schema support**: tSortRow supports Talend's dynamic schema feature for sorting data with unknown column structures at design time.

---

## 4. Converter Audit

### 4.1 Converter Flow

The converter for `tSortRow` follows a **dual-path** approach, which creates a conflict:

**Path 1 -- Generic `parse_base_component()` (runs FIRST)**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)` for ALL components
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict (lines 433-458)
3. Calls `_map_component_parameters('tSortRow', config_raw)` (line 472)
4. Returns mapped config from the deprecated `_map_component_parameters()` block (lines 217-227)
5. This produces: `sort_columns` from `config_raw.get('CRITERIA', [])`, `sort_orders` from `config_raw.get('SORT_ORDERS', [])`, etc.

**Path 2 -- Dedicated `parse_sort_row()` (runs SECOND, overwrites Path 1)**:
1. `converter.py:_parse_component()` then hits `elif component_type == 'tSortRow':` (line 244)
2. Calls `component_parser.parse_sort_row(node, component)` (line 245)
3. `parse_sort_row()` parses the CRITERIA table parameter from XML `elementValue` nodes (lines 866-874)
4. Overwrites `component['config']['sort_columns']` and `component['config']['sort_orders']`

**The conflict**: Path 1 runs first and uses `config_raw.get('CRITERIA', [])` which returns the raw CRITERIA parameter value as a string or empty list -- it does NOT parse the nested `elementValue` XML structure. Path 2 then correctly parses the XML `elementValue` nodes. However, Path 1 also sets `external_sort`, `max_memory_rows`, `temp_dir`, and `chunk_size` from `config_raw`, while Path 2 sets its own `external_sort` and `temp_file` (note: different key name -- `temp_dir` vs `temp_file`). This creates a configuration where BOTH sets of keys exist in `component['config']`, potentially causing confusion.

### 4.2 Parameter Extraction -- `parse_sort_row()` (Dedicated Parser)

| # | Talend XML Parameter | Extracted? | V1 Config Key | Parser Line | Notes |
|----|----------------------|------------|---------------|-------------|-------|
| 1 | `CRITERIA` -> `COLNAME` | **Yes** | `sort_columns` (list) | 866-871 | Correctly parses `elementValue` with `elementRef='COLNAME'`. Collects column names into a list. |
| 2 | `CRITERIA` -> `SORT` | **Yes** | `sort_orders` (list) | 872-874 | Correctly parses `elementValue` with `elementRef='SORT'`. Converts to lowercase. Default `'asc'`. |
| 3 | `CRITERIA` -> `SORT_TYPE` | **No** | -- | -- | **NOT EXTRACTED. The `num` vs `alpha` sort type distinction is completely missing.** The parser only looks for `COLNAME` and `SORT` elementRefs, but never checks for `SORT_TYPE` (or its equivalent elementRef). This is a critical gap -- numerical vs alphabetical sorting produces different results. |
| 4 | `EXTERNAL_SORT` | **Yes** | `external_sort` | 881-882 | Parsed from `elementParameter` with `name='EXTERNAL_SORT'`. Boolean conversion via `value.lower() == 'true'`. |
| 5 | `TEMPFILE` / `TEMP_DIR` | **Partial** | `temp_file` | 883-884 | Parsed as `temp_file` in `parse_sort_row()`, but engine expects `temp_dir`. Key name mismatch. Also, Path 1 sets `temp_dir` from `config_raw.get('TEMPFILE', '')`. |
| 6 | `CREATE_TEMP_DIR` | **No** | -- | -- | **Not extracted. Auto-create temp directory option unavailable.** |
| 7 | `BUFFER_SIZE` | **No** | -- | -- | **Not extracted.** Path 1 sets `max_memory_rows` from `config_raw.get('MAX_MEMORY_ROWS', '1000000')`, but Talend uses `BUFFER_SIZE` as the XML parameter name, and `MAX_MEMORY_ROWS` is a v1-invented key that would never appear in Talend XML. The value will always be the default `1000000`. |
| 8 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |

### 4.3 Parameter Extraction -- `_map_component_parameters()` (Deprecated Generic Path)

This path runs BEFORE `parse_sort_row()` and sets initial config values that may be partially overwritten:

| # | Config Key Set | Source in config_raw | Value | Notes |
|----|---------------|---------------------|-------|-------|
| 1 | `sort_columns` | `config_raw.get('CRITERIA', [])` | Raw string or `[]` | **Incorrect**: CRITERIA is a TABLE parameter -- its raw value is not a list of column names. It is the string representation of the XML parameter, NOT the parsed `elementValue` data. This value is overwritten by Path 2. |
| 2 | `sort_orders` | `config_raw.get('SORT_ORDERS', [])` | `[]` | **Incorrect**: There is no Talend parameter named `SORT_ORDERS`. The orders are embedded in the CRITERIA table. This always returns the default `[]`. Overwritten by Path 2. |
| 3 | `na_position` | `config_raw.get('NA_POSITION', 'last')` | `'last'` | **Invented**: There is no Talend parameter named `NA_POSITION`. This always returns the default `'last'`. Not overwritten by Path 2. Survives into final config. |
| 4 | `case_sensitive` | `config_raw.get('CASE_SENSITIVE', True)` | `True` | **Invented**: There is no Talend parameter named `CASE_SENSITIVE`. Talend is always case-sensitive for alphabetical sort. This always returns the default `True`. Not overwritten by Path 2. Survives into final config. |
| 5 | `external_sort` | `config_raw.get('EXTERNAL_SORT', False)` | Boolean | Correctly reads from config_raw, but config_raw stores the raw string `'true'`/`'false'` which Python treats as truthy string. May be overwritten by Path 2 with proper boolean conversion. |
| 6 | `max_memory_rows` | `config_raw.get('MAX_MEMORY_ROWS', '1000000')` | `1000000` | **Invented key**: No Talend parameter named `MAX_MEMORY_ROWS`. Always returns default. Not overwritten by Path 2. Survives into final config. |
| 7 | `temp_dir` | `config_raw.get('TEMPFILE', '')` | String | Reads from TEMPFILE if present. **Key name**: `temp_dir`. Path 2 also writes `temp_file`. Both survive in final config. |
| 8 | `chunk_size` | `config_raw.get('CHUNK_SIZE', '10000')` | `10000` | **Invented key**: No Talend parameter named `CHUNK_SIZE`. Always returns default. Not overwritten by Path 2. Survives into final config. |

**Summary**: The deprecated `_map_component_parameters()` path generates mostly invented/non-existent Talend parameter reads that always return defaults. The dedicated `parse_sort_row()` correctly parses the CRITERIA table but misses the `SORT_TYPE` elementRef. The dual-path approach creates duplicate and conflicting config keys (`temp_dir` vs `temp_file`).

### 4.4 Schema Extraction

Schema is extracted generically in `parse_base_component()` (lines 475-508 of `component_parser.py`).

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types (`str`, `int`, etc.) -- **violates STANDARDS.md** which requires Talend format (`id_String`) |
| `nullable` | Yes | Boolean conversion from string `"true"/"false"` |
| `key` | Yes | Boolean conversion from string |
| `length` | Yes | Integer conversion, only if attribute present in XML |
| `precision` | Yes | Integer conversion, only if attribute present in XML |
| `pattern` (date) | Yes | Java date pattern converted to Python strftime |
| `default` | **No** | Column default value not extracted from XML |
| `talendType` | **No** | Full Talend type string not preserved -- converted to Python type |

### 4.5 Expression Handling

**Context variable handling**: Same generic mechanism as all components. `parse_base_component()` detects `'context.' in value` in non-CODE/IMPORT fields and wraps simple context references with `${...}` for ContextManager resolution.

**Java expression handling**: After parameter extraction, `mark_java_expression()` scans all string values for Java operators, method calls, and routine references. Values detected as Java expressions are prefixed with `{{java}}` marker. This applies to the `TEMPFILE` path expression which may contain globalMap references (e.g., `"path" + ((Integer)globalMap.get("thread_id"))`).

**Known limitation**: The `CRITERIA` table `elementValue` nodes are parsed by `parse_sort_row()` directly from XML, bypassing the expression detection pipeline. If a column name in the CRITERIA table were itself a Java expression (unlikely but theoretically possible), it would not be marked for Java bridge resolution.

### 4.6 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-SR-001 | **P1** | **`SORT_TYPE` (num/alpha) not extracted**: The `parse_sort_row()` method only extracts `COLNAME` and `SORT` from the CRITERIA table elementValues. It never looks for the sort type elementRef (`SORT_TYPE`, `SORT_NUM_OR_ALPHA`, or equivalent). The engine has no way to know whether a column should be sorted numerically or alphabetically. This is a correctness issue: sorting the values `[1, 2, 10, 20]` alphabetically produces `[1, 10, 2, 20]`, while numerically produces `[1, 2, 10, 20]`. |
| CONV-SR-002 | **P1** | **Dual-path converter creates conflicting config**: `_map_component_parameters()` runs first and sets `temp_dir`, `max_memory_rows`, `chunk_size`, `na_position`, `case_sensitive` from non-existent Talend parameters (always defaults). Then `parse_sort_row()` runs and sets `temp_file` (different key than `temp_dir`). The final config contains BOTH `temp_dir` and `temp_file`, plus invented parameters that can never be populated from Talend XML. |
| CONV-SR-003 | **P1** | **`BUFFER_SIZE` not extracted**: The Talend buffer size parameter (default 1000000) is not read from XML. The `_map_component_parameters()` path reads from `config_raw.get('MAX_MEMORY_ROWS', '1000000')`, but `MAX_MEMORY_ROWS` is an invented key that never exists in Talend XML. The engine always uses the hardcoded default. |
| CONV-SR-004 | **P2** | **Schema type format violates STANDARDS.md**: Converter converts types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format (`id_String`, `id_Integer`). While the engine handles both, this violates the documented standard (STANDARDS.md line 865-878). |
| CONV-SR-005 | **P2** | **`CREATE_TEMP_DIR` not extracted**: The auto-create temp directory option is not parsed. If the temp directory does not exist, external sort will fail with a filesystem error. |
| CONV-SR-006 | **P3** | **`TSTATCATCHER_STATS` not extracted**: tStatCatcher metadata capture unavailable. Low priority -- rarely used in production. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Sort by multiple columns | **Yes** | High | `_process()` lines 164-176 | Iterates `sort_columns` list, builds `by_columns` and `ascending` lists. Uses `pd.DataFrame.sort_values()` with multi-column support. |
| 2 | Ascending/Descending order per column | **Yes** | High | `_process()` lines 171-175 | Correctly maps `'desc'` and `'descending'` to `False`, else `True`. Per-column ascending list passed to `sort_values()`. |
| 3 | Numerical sort type (`num`) | **No** | N/A | -- | **NOT IMPLEMENTED. The engine has no concept of sort type.** pandas `sort_values()` sorts based on the column's dtype: numeric columns are sorted numerically, object (string) columns are sorted lexicographically. This means: (a) If a column is already numeric dtype, sorting is correctly numerical. (b) If a column is string dtype containing numeric values (e.g., `["1", "10", "2"]`), sorting is incorrectly alphabetical when `num` sort type was intended. There is no mechanism to convert string columns to numeric for sorting purposes when sort type is `num`. |
| 4 | Alphabetical sort type (`alpha`) | **Partial** | Medium | -- | pandas sorts string columns lexicographically by default, which matches `alpha`. However, there is no explicit handling -- the engine relies entirely on pandas dtype inference. If a column is numeric dtype but the Talend criteria specifies `alpha`, the engine would sort numerically instead of alphabetically. |
| 5 | Case-insensitive sorting | **Yes** | High | `_process()` lines 186-197 | Creates temporary lowercase columns (`_temp_sort_{col}`) for string columns when `case_sensitive=False`. Replaces sort column names with temp columns, sorts, then drops temp columns (lines 209-212). **Note**: This is a v1 feature that does NOT exist in standard Talend tSortRow. Talend is always case-sensitive. |
| 6 | Stable sort | **Yes** | High | `_process()` line 205 | Uses `kind='stable'` parameter in `sort_values()`. Preserves original order for equal values. Matches Talend behavior. |
| 7 | Null value positioning | **Yes** | High | `_process()` line 203 | Uses `na_position` parameter (default `'last'`). Configurable as `'first'` or `'last'`. Matches Talend default behavior (nulls at end for ascending). |
| 8 | External sort (Sort on disk) | **Partial** | Low | `_external_sort()` lines 243-335 | Implemented but **fundamentally flawed** -- see PERF-SR-001. Writes sorted chunks to parquet files, then reads ALL chunks back into memory and re-sorts the entire combined DataFrame. This defeats the purpose of external sort (memory reduction). A true external sort uses k-way merge without loading all data into memory. |
| 9 | External sort temp directory | **Yes** | Medium | `_external_sort()` line 265 | Uses `config.get('temp_dir', tempfile.gettempdir())`. But converter sets `temp_file` (Path 2) vs `temp_dir` (Path 1) -- config key mismatch may cause fallback to system temp. |
| 10 | External sort buffer size | **Partial** | Medium | `_external_sort()` line 264 | Uses `config.get('chunk_size', 10000)`. The config key `chunk_size` comes from the deprecated `_map_component_parameters()` path with hardcoded default `10000`. Talend's `BUFFER_SIZE` default is `1000000`. The v1 default is 100x smaller, causing unnecessary disk I/O. |
| 11 | External sort cleanup | **Yes** | High | `_external_sort()` lines 325-335 | Temp files and directory are cleaned up in a `finally` block. Handles cleanup errors silently. |
| 12 | Auto-switch to external sort | **Yes** | Medium | `_process()` line 159 | Automatically switches to external sort when `len(input_data) > max_memory_rows`. Default threshold is 1,000,000 rows. |
| 13 | Streaming input support | **Yes** | Medium | `_process_streaming()` lines 337-396 | Collects all streaming chunks, concatenates, sorts, returns as generator. Correctly handles the blocking nature of sort. |
| 14 | Reset index after sort | **Yes** | High | `_process()` line 204 | `ignore_index=True` resets the DataFrame index after sorting. Prevents downstream issues with non-sequential indices. |
| 15 | Empty input handling | **Yes** | High | `_process()` lines 131-134 | Returns empty DataFrame with stats (0, 0, 0). |
| 16 | Missing column handling | **Yes** | Medium | `_process()` lines 168-177 | Logs warning for missing columns, skips them. If no valid columns remain, returns unsorted data with warning. |
| 17 | Statistics tracking | **Yes** | High | `_process()` lines 215-216 | `_update_stats(row_count, row_count, 0)` sets NB_LINE, NB_LINE_OK, NB_LINE_REJECT correctly. |
| 18 | GlobalMap custom variables | **Yes** | Medium | `_process()` lines 219-221 | Sets `{id}_SORTED_BY` and `{id}_SORT_ORDERS` in globalMap. These are v1-specific (not in Talend). |
| 19 | **Sort type (num vs alpha)** | **No** | N/A | -- | **NOT IMPLEMENTED. See feature #3 above. This is the single most impactful feature gap.** |
| 20 | **Case-sensitive alpha sort (Talend default)** | **Implicit** | High | -- | pandas lexicographic sort is case-sensitive (uppercase before lowercase), matching Talend default. No explicit logic needed. |
| 21 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Not implemented. Error message not stored in globalMap on failure.** |
| 22 | **Create temp directory if not exists** | **No** | N/A | -- | **Not implemented. External sort will fail if temp directory does not exist.** |
| 23 | **Buffer size from Talend config** | **No** | N/A | -- | **Not implemented. Talend's BUFFER_SIZE parameter is never extracted from XML.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-SR-001 | **P1** | **No sort type (num vs alpha) distinction**: The engine relies entirely on pandas dtype to determine sort behavior. If a column has string dtype but should be sorted numerically (sort type = `num`), the engine sorts alphabetically instead. This is a **silent correctness issue** -- no error is raised, but the output is wrong. For example, sorting string column values `["1", "2", "10", "20"]` with sort type `num` should produce `["1", "2", "10", "20"]` but the engine produces `["1", "10", "2", "20"]` (string sort). This affects any column that is stored as string type in the DataFrame but should be sorted numerically per the Talend criteria. |
| ENG-SR-002 | **P1** | **External sort loads all data into memory for final sort**: The `_external_sort()` method writes sorted chunks to parquet files, then reads ALL chunks back into a single DataFrame (`pd.concat(all_chunks)`) and re-sorts the entire thing with `sort_values()`. This means the final sort step requires all data in memory simultaneously, completely defeating the purpose of external sort. For a 10-million-row dataset that does not fit in memory, the external sort will still OOM at the merge step. |
| ENG-SR-003 | **P1** | **Case-insensitive sort does not apply in external sort mode**: The `_external_sort()` method (lines 243-335) does NOT check or handle the `case_sensitive` config option. It only applies `sort_columns` and `sort_orders` directly. The case-insensitive temporary column logic (lines 186-212) is in the in-memory sort path only. If external sort is triggered (either by config or by row count exceeding `max_memory_rows`), case-insensitive sorting silently falls back to case-sensitive. |
| ENG-SR-004 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When the sort operation fails with an exception, the error message is not stored in globalMap. Downstream components or error handling flows referencing `{id}_ERROR_MESSAGE` will get null/None. The official Talend documentation explicitly lists `ERROR_MESSAGE` as a global variable for tSortRow. |
| ENG-SR-005 | **P2** | **Streaming sort collects all data before sorting**: The `_process_streaming()` method (lines 337-396) collects ALL streaming chunks into a list, concatenates them into a single DataFrame, then sorts. This means streaming input does NOT reduce memory usage for tSortRow -- all data is materialized. While this is inherent to sorting (a blocking operation), it means the streaming interface is misleading. The output is returned as a generator (chunked), but the sort itself requires all data in memory. |
| ENG-SR-006 | **P2** | **External sort chunk size default mismatch**: The engine uses `chunk_size` default of `10000` (line 264). Talend's `BUFFER_SIZE` default is `1000000`. The v1 default is 100x smaller, causing 100x more disk writes for the same dataset. This significantly degrades external sort performance. |
| ENG-SR-007 | **P2** | **`na_position` not configurable per column**: Talend's null handling may vary by sort direction (nulls-first in descending, nulls-last in ascending). The v1 engine applies a single `na_position` to all columns. pandas `sort_values()` only accepts a single `na_position` string, not per-column. **Note**: BUG-SR-013 (P1) upgrades the severity of this issue -- even single-column descending sorts produce incorrect null placement, not just multi-column scenarios. |
| ENG-SR-008 | **P3** | **v1-specific globalMap variables**: The engine stores `{id}_SORTED_BY` and `{id}_SORT_ORDERS` in globalMap (lines 220-221). These do not exist in Talend and may confuse users or interfere with globalMap key conventions. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Always equals NB_LINE for sort (correct -- no rejects) |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | Same mechanism | Always 0 (correct for sort) |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | **Not implemented**. Talend documentation explicitly lists this. |
| `{id}_SORTED_BY` | No (v1-only) | **Yes** | `_process()` line 220 | V1-specific, not in Talend |
| `{id}_SORT_ORDERS` | No (v1-only) | **Yes** | `_process()` line 221 | V1-specific, not in Talend |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-SR-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just SortRow, since `_update_global_map()` is called after every component execution (via `execute()` line 218). The sort operation itself completes, but the post-execution globalMap update crashes. |
| BUG-SR-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-SR-003 | **P1** | `src/v1/engine/components/transform/sort_row.py:193` | **Input DataFrame is mutated in-place for case-insensitive sort**: When `case_sensitive=False`, the code creates temporary columns directly on `input_data` (line 193: `input_data[temp_col] = input_data[col].str.lower()`). This **modifies the caller's DataFrame** since pandas DataFrames are passed by reference. After `_process()` returns, the caller's original DataFrame has been modified with extra `_temp_sort_` columns. While the sorted output has these columns removed (lines 210-212), the INPUT DataFrame retains them. This is a side-effect bug that can corrupt upstream data if the same DataFrame is used elsewhere. |
| BUG-SR-004 | **P1** | `src/v1/engine/components/transform/sort_row.py:279-280` | **External sort ascending list has incorrect length**: In `_external_sort()`, the ascending list is built as `[sort_orders[j].lower() != 'desc' for j in range(len(by_columns))]` (line 279-280). If `sort_orders` has fewer elements than `by_columns`, this raises `IndexError`. In the in-memory sort path (line 171-175), this is handled correctly with an `if i < len(sort_orders)` check and a default of `True` (ascending). The external sort path lacks this guard. |
| BUG-SR-005 | **P1** | `src/v1/engine/components/transform/sort_row.py:307-308` | **Same IndexError in final merge sort of external sort**: The merged DataFrame sort on lines 307-308 has the same unguarded `sort_orders[j]` access as BUG-SR-004. Both the chunk sort and the final merge sort will crash if `sort_orders` is shorter than `sort_columns`. |
| BUG-SR-006 | **P1** | `src/v1/engine/components/transform/sort_row.py:375-376` | **Streaming sort ascending list has incorrect length**: In `_process_streaming()`, the ascending list comprehension on lines 375-376 uses `for i in range(len(by_columns)) if i < len(sort_orders)`. The `if` clause is a FILTER on the comprehension, not a conditional default. If `sort_orders` has 1 element and `by_columns` has 3, the ascending list will have only 1 element, not 3. pandas `sort_values()` requires `ascending` to match the length of `by` or be a single boolean. A length-mismatch raises `ValueError`. |
| BUG-SR-007 | **P2** | `src/v1/engine/components/transform/sort_row.py:241` | **`_is_streaming()` false positive for lists**: The check `hasattr(data, '__iter__') and not isinstance(data, (pd.DataFrame, dict, str))` returns `True` for lists, tuples, sets, and other iterables. If `input_data` is accidentally a list (e.g., from a configuration error), it would be treated as streaming input. Lists are not generators and should not trigger streaming mode. |
| BUG-SR-008 | **P2** | `src/v1/engine/components/transform/sort_row.py:69-106` | **`_validate_config()` is never called**: The validation method exists (38 lines of validation logic) but is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Invalid configurations (empty sort_columns, non-list sort_orders, etc.) are not caught until they cause runtime errors. |
| BUG-SR-009 | **P2** | `src/v1/engine/components/transform/sort_row.py:298-301` | **External sort writes and immediately re-reads chunks**: The external sort writes each sorted chunk to a parquet file (line 289), then appends the SAME chunk to an in-memory list `chunks` (line 292). Later, it reads the parquet files back (lines 299-301) into `all_chunks`. The `chunks` list is never used after being populated. The parquet write-then-read cycle is wasteful I/O with no benefit -- the data is already in memory in `chunks`. |
| BUG-SR-010 | **P0** | `src/v1/engine/base_component.py` (HYBRID streaming mode) | **Base class HYBRID streaming mode silently produces incorrectly sorted output**: When input exceeds `MEMORY_THRESHOLD_MB`, the base class chunks the DataFrame and calls `_process()` per chunk. Each chunk is sorted independently, then `pd.concat()` merges them -- producing an **incorrectly sorted** result. Example: sorting `[5,3,1,4,2,6]` with `chunk_size=3` produces `[1,3,5,2,4,6]` instead of `[1,2,3,4,5,6]`. This is a **CROSS-CUTTING** issue affecting any component that depends on streaming mode preserving global order. For a blocking component like `tSortRow`, per-chunk sorting is fundamentally incorrect -- the entire dataset must be sorted as a unit. |
| BUG-SR-011 | **P1** | `src/v1/engine/components/transform/sort_row.py:269,333` | **External sort `finally` block not robust against setup-phase exceptions**: If `tempfile.mkdtemp()` raises (line 269), `sort_dir` is undefined when the `finally` block executes `os.rmdir(sort_dir)` (line 333), causing a `NameError`. Temp file cleanup is not robust against exceptions that occur before `sort_dir` is assigned. |
| BUG-SR-012 | **P1** | `src/v1/engine/components/transform/sort_row.py:219-221` | **Streaming/external sort paths don't set GlobalMap variables `SORTED_BY` and `SORT_ORDERS`**: Lines 219-221 set `{id}_SORTED_BY` and `{id}_SORT_ORDERS` only in the in-memory sort path. The `_external_sort()` and `_process_streaming()` methods do not set these variables. Downstream components relying on these globalMap variables after streaming or external sort will get `None`. |
| BUG-SR-013 | **P1** | `src/v1/engine/components/transform/sort_row.py:203` | **Null handling diverges from Talend for descending sorts**: Talend's null handling is direction-dependent: nulls-last for ascending, nulls-first for descending. The v1 engine uses `na_position='last'` unconditionally (line 203), placing nulls last regardless of sort direction. Even a single-column descending sort will differ from Talend when nulls are present. This upgrades the severity of ENG-SR-007 from a per-column configurability gap to a single-column correctness bug. |
| BUG-SR-014 | **P2** | `src/v1/engine/components/transform/sort_row.py:282-286,310-315` | **External sort doesn't use stable sort**: The chunk sorts (lines 282-286) and the final merge sort (lines 310-315) in `_external_sort()` do not pass `kind='stable'` to `sort_values()`. The in-memory sort path correctly uses `kind='stable'` (line 205). This creates a behavioral difference: rows with equal sort keys may not preserve their original input order in external sort mode, diverging from both the in-memory path and Talend's stable sort guarantee. |
| BUG-SR-015 | **P2** | `src/v1/engine/components/transform/sort_row.py:131,136` | **Generator input crashes before reaching `_is_streaming()` check**: Line 131 calls `input_data.empty` which raises `AttributeError` for generator objects (generators have no `.empty` attribute). Line 136 calls `len(input_data)` which raises `TypeError` for generators. Both checks execute before the `_is_streaming()` check on line 140. Generator inputs crash immediately instead of being routed to `_process_streaming()`. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-SR-001 | **P2** | **`temp_file` (converter Path 2) vs `temp_dir` (converter Path 1 and engine)**: The dedicated `parse_sort_row()` sets `component['config']['temp_file']` (line 884), but the engine reads `self.config.get('temp_dir', ...)` (line 265). The Path 1 `_map_component_parameters()` sets `temp_dir` (line 225). If only Path 2 runs without Path 1 (hypothetical), the engine would not find the temp directory config. Currently both paths run, so `temp_dir` from Path 1 is available, but the naming inconsistency is a maintenance hazard. |
| NAME-SR-002 | **P2** | **`chunk_size` (engine) vs `BUFFER_SIZE` (Talend)**: The engine uses `chunk_size` for the external sort buffer, while Talend uses `BUFFER_SIZE`. The converter uses `CHUNK_SIZE` (non-existent Talend param). Three different names for the same concept. |
| NAME-SR-003 | **P3** | **`max_memory_rows` (engine config) vs `BUFFER_SIZE` (Talend)**: The engine's auto-switch threshold is `max_memory_rows` (default 1,000,000). Talend's equivalent is `BUFFER_SIZE`. The naming does not align with Talend terminology. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-SR-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md line 91) | Method exists but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-SR-002 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md line 865) | Converter converts to Python types (`str`, `int`) instead of preserving Talend types (`id_String`, `id_Integer`). |
| STD-SR-003 | **P2** | "Every component MUST have its own `parse_*` method" (STANDARDS.md line 1214) | tSortRow HAS a dedicated `parse_sort_row()` method (compliant), BUT the deprecated `_map_component_parameters()` also runs and creates conflicting config. The deprecated path should be removed for `tSortRow`. |
| STD-SR-004 | **P3** | "No `print()` statements" (STANDARDS.md) | `component_parser.py` line 856 contains `print(f"[DEBUG] Final component config: {component['config']}")` in the `parse_aggregate_sorted_row()` method just before `parse_sort_row()`. While this is not in `parse_sort_row()` itself, it is in the same file and prints config data that may include tSortRow configs when debugging. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-SR-001 | **P3** | **`chunks` list in `_external_sort()` is populated but never used**: Line 292 appends each sorted chunk to `chunks`, but the list is never read. Lines 299-301 re-read from parquet files instead. The `chunks` list is a leftover from development/debugging. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-SR-001 | **P3** | **No path validation for temp directory**: The `temp_dir` config value is used directly with `tempfile.mkdtemp(dir=temp_dir)` (line 269). If config comes from untrusted sources, an attacker could write temporary sort files to arbitrary directories. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |
| SEC-SR-002 | **P3** | **Bare `except` in cleanup**: Lines 330-335 use bare `except:` clauses for temp file cleanup. While this is intentional (cleanup should not raise), bare `except` catches `SystemExit` and `KeyboardInterrupt`, which can mask critical signals. Should use `except OSError:` or `except Exception:`. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones (processing started/complete, external sort), DEBUG not used within the component, WARNING for empty input and missing columns, ERROR for sort failures -- mostly correct but could use more DEBUG for configuration details |
| Start/complete logging | `_process()` logs start (line 137) with row count; logs complete (line 223) with sorted row count and columns -- correct |
| External sort logging | Logs external sort decision (line 160), chunk merge count (line 295), completion (line 318) -- good |
| Streaming logging | Logs collection start (line 358), completion (line 394) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls in `sort_row.py` -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Does NOT use custom exceptions from `exceptions.py`. The `_process()` method has a bare `raise` in the except block (line 229), which re-raises whatever exception occurred. No wrapping in `ComponentExecutionError` or `DataValidationError`. This is inconsistent with the exception hierarchy defined in `exceptions.py`. |
| Exception chaining | Uses bare `raise` (line 229), not `raise ... from e`. Exception chain is preserved but not explicit. |
| Empty input | Handled gracefully (lines 131-134): returns empty DataFrame with stats (0, 0, 0). |
| Missing columns | Handled gracefully (lines 168-177): logs warning, skips missing columns. If no valid columns, returns unsorted data. |
| External sort exceptions | The `_external_sort()` method has a `finally` block for cleanup (lines 325-335) but does NOT catch exceptions. If the sort fails mid-way, the exception propagates up and the `finally` block cleans up temp files. Correct design. |
| `die_on_error` handling | **NOT IMPLEMENTED**. The SortRow component has no `die_on_error` config option. All errors are raised unconditionally. There is no mechanism to return empty DataFrame on error instead of crashing. While Talend's tSortRow does not have a `DIE_ON_ERROR` toggle (it always fails on error), the engine could still benefit from a graceful degradation mode. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()`, `_external_sort()`, `_process_streaming()` all have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]`, `List[str]` -- correct |
| Docstrings | All methods have comprehensive docstrings with Args, Returns, Raises, and Example sections -- excellent |

### 6.9 Code Structure Assessment

| Aspect | Assessment |
|--------|------------|
| Class hierarchy | `SortRow(BaseComponent)` -- correct inheritance |
| Method count | 5 methods (`_validate_config`, `_process`, `_is_streaming`, `_external_sort`, `_process_streaming`) -- reasonable decomposition |
| Method length | `_process()`: 97 lines, `_external_sort()`: 93 lines, `_process_streaming()`: 60 lines -- acceptable |
| Constants | No class-level constants. All defaults are inline in `config.get()` calls. Should extract to class constants for maintainability. |
| Imports | Clean imports: stdlib (logging, os, tempfile), typing, pandas, base class. No unused imports. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-SR-001 | **P1** | **External sort is pseudo-external -- final merge loads all data into memory**: `_external_sort()` writes sorted chunks to parquet files (line 289), reads them ALL back (lines 299-301), concatenates into a single DataFrame (`pd.concat(all_chunks)`, line 304), then re-sorts the entire combined DataFrame (`merged_df.sort_values()`, lines 310-315). The concatenation step requires all data in memory simultaneously. For a 10-million-row dataset with 20 columns averaging 50 bytes each, this requires approximately 10GB of RAM at the concatenation step -- the same as in-memory sort. The parquet round-trip adds disk I/O overhead without reducing peak memory. A true external sort would use a heap-based k-way merge that reads one row at a time from each sorted chunk file, requiring only `num_chunks * 1 row` of memory. |
| PERF-SR-002 | **P2** | **External sort writes chunks to parquet AND keeps them in memory**: Line 292 appends each sorted chunk to the `chunks` list (in memory), while also writing to parquet (line 289). During the chunk-writing phase, each chunk exists TWICE: once in the `chunks` list and once on disk. The `chunks` list is never used -- the data is re-read from parquet files. This doubles memory usage during the chunking phase for no benefit. |
| PERF-SR-003 | **P2** | **External sort default chunk size 100x smaller than Talend**: The engine defaults to `chunk_size=10000` (line 264) while Talend defaults `BUFFER_SIZE=1000000`. For a 10-million-row dataset, the engine creates 1000 temp files vs Talend's 10. The extra files add filesystem overhead, temp directory pressure, and more merge work. |
| PERF-SR-004 | **P3** | **Case-insensitive sort creates temporary columns with `.str.lower()`**: For each string column in the sort criteria, a new column is created with `.str.lower()` applied (line 193). For a column with 1 million string values averaging 50 characters, this allocates approximately 50MB of additional memory. The temporary columns are dropped after sorting, but peak memory includes both original and lowercase columns. An alternative approach would be to use a custom `key` function with `sort_values(key=...)` (pandas 1.1+), which avoids materializing the lowercase values as a separate column. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| In-memory sort | Uses `pd.DataFrame.sort_values()` which sorts in-place or creates a new DataFrame (depending on pandas version). With `ignore_index=True`, a new index is created. Peak memory is approximately 2x the input DataFrame (original + sorted copy). |
| External sort design | Intended to handle large datasets, but current implementation loads all data into memory at the merge step. Effectively equivalent to in-memory sort with extra disk I/O overhead. |
| Auto-switch threshold | `max_memory_rows` default is 1,000,000. This is a row count threshold, not a memory size threshold. A dataset with 100 wide columns may exceed memory at 100,000 rows, while a dataset with 3 narrow columns may fit at 10,000,000 rows. Row count is a poor proxy for memory usage. The base class `MEMORY_THRESHOLD_MB = 3072` is a better approach (memory-based), but `SortRow._process()` does not use it. |
| Streaming input | Collects all chunks into memory before sorting. No memory reduction from streaming input. This is inherent to sorting (blocking operation) and is correctly documented in the code. |
| Streaming output | Returns sorted data as a generator with configurable `output_chunk_size` (default 10000). This reduces memory for DOWNSTREAM consumers but does not help the sort itself. |
| Temporary file format | Parquet (columnar, compressed). Good choice for temporary storage -- smaller files than CSV, faster read/write. |

### 7.2 Complexity Analysis

| Operation | Time Complexity | Space Complexity | Notes |
|-----------|----------------|-----------------|-------|
| In-memory sort | O(N log N) | O(N) | pandas uses introsort (hybrid quicksort/heapsort/insertion sort). Stable variant uses mergesort: O(N log N) guaranteed. |
| Case-insensitive sort | O(N * K) + O(N log N) | O(N * K) + O(N) | K = number of string sort columns. O(N * K) for `.str.lower()` column creation, then O(N log N) for sort. |
| External sort (current impl) | O(C * N/C * log(N/C)) + O(N log N) | O(N) | C = chunk_size. Sorting C chunks each of size N/C, then re-sorting all N rows. The final re-sort dominates and uses O(N) memory. |
| External sort (correct impl) | O(C * N/C * log(N/C)) + O(N * log(N/C)) | O(C + N/C) | Correct k-way merge uses a heap of size N/C (number of chunks). Total merge reads each element once with log(N/C) heap operations. Peak memory is C (one chunk) + N/C (heap entries). |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `SortRow` v1 engine component. Searched `tests/v1/` recursively. |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found for SortRow. |

**Key finding**: The v1 engine has ZERO tests for this component. All 397 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic single-column ascending sort | P0 | Sort a 10-row DataFrame by one column ascending. Verify output order matches expected sorted order. Verify row count unchanged. |
| 2 | Basic single-column descending sort | P0 | Sort by one column descending. Verify output is in reverse order. |
| 3 | Multi-column sort | P0 | Sort by two columns: first ascending, second descending. Verify multi-level sorting produces correct order. |
| 4 | Empty input DataFrame | P0 | Pass empty DataFrame to `_process()`. Verify returns empty DataFrame with stats (0, 0, 0). No error. |
| 5 | None input | P0 | Pass `None` to `_process()`. Verify returns empty DataFrame with stats (0, 0, 0). No error. |
| 6 | Statistics tracking | P0 | After sorting 100 rows, verify `stats['NB_LINE'] == 100`, `stats['NB_LINE_OK'] == 100`, `stats['NB_LINE_REJECT'] == 0`. |
| 7 | Stable sort verification | P0 | Sort rows where two rows have equal sort key values. Verify their relative order from the input is preserved in the output. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Numeric vs string sort behavior | P1 | Sort a string column containing `["1", "2", "10", "20"]`. Verify lexicographic order `["1", "10", "2", "20"]` is produced (current behavior). Document as known gap for `num` sort type. |
| 9 | Sort with null values (NaN) | P1 | Sort a column containing NaN values. Verify NaN values appear at the end (default `na_position='last'`). |
| 10 | Sort with null values -- `na_position='first'` | P1 | Configure `na_position='first'`. Verify NaN values appear at the beginning. |
| 11 | Case-insensitive sort | P1 | Configure `case_sensitive=False`. Sort `["apple", "Banana", "cherry"]`. Verify order is `["apple", "Banana", "cherry"]` (case-insensitive), not `["Banana", "apple", "cherry"]` (case-sensitive). |
| 12 | Missing sort column | P1 | Configure `sort_columns=["nonexistent"]`. Verify warning is logged and unsorted data is returned. |
| 13 | sort_orders shorter than sort_columns | P1 | Configure 3 sort columns but only 1 sort order. Verify remaining columns default to ascending. Verify no IndexError. |
| 14 | External sort basic | P1 | Configure `external_sort=True`. Sort 100 rows. Verify output is correctly sorted. Verify temp files are cleaned up. |
| 15 | External sort -- sort_orders length mismatch | P1 | Configure external sort with 3 sort columns and 1 sort order. Verify no IndexError (currently fails -- BUG-SR-004). |
| 16 | GlobalMap integration | P1 | Provide a globalMap instance. After execution, verify `{id}_NB_LINE`, `{id}_NB_LINE_OK`, `{id}_NB_LINE_REJECT` are set correctly. |
| 17 | Input DataFrame not mutated | P1 | Pass a DataFrame with a string column. Sort with `case_sensitive=False`. Verify the ORIGINAL DataFrame does not have `_temp_sort_` columns after `_process()` returns. (Currently fails -- BUG-SR-003.) |
| 18 | Sort preserves all columns | P1 | Sort a DataFrame with 10 columns by 2 columns. Verify all 10 columns are present in the output with original values. |
| 19 | Sort with mixed types | P1 | Sort a column containing mixed types (int and string in object column). Verify behavior is defined (may raise or produce consistent order). |
| 20 | No sort columns configured | P1 | Configure `sort_columns=[]`. Verify unsorted data is returned with warning logged. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 21 | Large dataset auto-switch to external | P2 | Create a DataFrame with `max_memory_rows + 1` rows. Verify external sort is automatically triggered. |
| 22 | External sort temp directory cleanup on error | P2 | Configure external sort with an intentional error (e.g., sort by non-existent column in chunk). Verify temp files are still cleaned up via `finally` block. |
| 23 | Streaming input | P2 | Pass a generator of DataFrame chunks. Verify all chunks are collected, sorted correctly, and returned as a generator. |
| 24 | Custom temp directory | P2 | Configure `temp_dir` to a custom directory. Verify temp files are created in that directory during external sort. |
| 25 | Case-insensitive sort with non-string columns | P2 | Configure `case_sensitive=False` with a mix of string and numeric sort columns. Verify only string columns get lowercase treatment; numeric columns are unaffected. |
| 26 | Single-row DataFrame | P2 | Sort a DataFrame with exactly one row. Verify the single row is returned unchanged. |
| 27 | Sort by all columns | P2 | Sort a DataFrame by every column in the schema. Verify correct multi-level sort. |
| 28 | Sort with duplicate rows | P2 | DataFrame with multiple identical rows. Verify all duplicates are preserved (sort does not deduplicate). |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-SR-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-SR-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| BUG-SR-010 | Bug (Cross-Cutting) | Base class HYBRID streaming mode silently produces incorrectly sorted output. Per-chunk `_process()` calls sort each chunk independently; `pd.concat()` merges them without a global re-sort, producing wrong order (e.g., `[1,3,5,2,4,6]` instead of `[1,2,3,4,5,6]`). Affects any order-dependent component. |
| TEST-SR-001 | Testing | Zero v1 unit tests for this component. All 397 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-SR-001 | Converter | `SORT_TYPE` (num/alpha) not extracted from CRITERIA table. Engine cannot distinguish numerical from alphabetical sorting. Silent correctness issue. |
| CONV-SR-002 | Converter | Dual-path converter creates conflicting config: `_map_component_parameters()` sets `temp_dir`, `max_memory_rows`, `chunk_size`, `na_position`, `case_sensitive` from non-existent Talend parameters (always defaults). `parse_sort_row()` sets `temp_file` (different key). Both paths run. |
| CONV-SR-003 | Converter | `BUFFER_SIZE` not extracted from Talend XML. Engine always uses hardcoded default. |
| ENG-SR-001 | Engine | No sort type (num vs alpha) distinction. String columns with numeric values sort lexicographically instead of numerically. Silent data corruption. |
| ENG-SR-002 | Engine | External sort loads all data into memory for final merge. Defeats purpose of external sort. 10M-row datasets will still OOM. |
| ENG-SR-003 | Engine | Case-insensitive sort not applied in external sort mode. Silently falls back to case-sensitive. |
| ENG-SR-004 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap on failure. Downstream error handling gets null. |
| BUG-SR-003 | Bug | Input DataFrame mutated in-place for case-insensitive sort. Caller's DataFrame gets `_temp_sort_` columns. |
| BUG-SR-004 | Bug | External sort `IndexError` when `sort_orders` shorter than `sort_columns`. Missing bounds check. |
| BUG-SR-005 | Bug | Same `IndexError` in external sort final merge step (line 307-308). |
| BUG-SR-006 | Bug | Streaming sort `ascending` list length mismatch when `sort_orders` shorter than `sort_columns`. `ValueError` from pandas. |
| BUG-SR-011 | Bug | External sort `finally` block not robust: if `tempfile.mkdtemp()` raises, `sort_dir` is undefined and `os.rmdir(sort_dir)` raises `NameError`. Temp cleanup fragile against setup-phase exceptions. |
| BUG-SR-012 | Bug | Streaming and external sort paths don't set `{id}_SORTED_BY` and `{id}_SORT_ORDERS` in globalMap. Only the in-memory path (lines 219-221) sets them. Downstream consumers get `None`. |
| BUG-SR-013 | Bug | Null handling diverges from Talend for descending sorts. Talend uses nulls-last for asc, nulls-first for desc. V1 uses `na_position='last'` unconditionally. Even single-column descending sorts produce different null placement. |
| TEST-SR-002 | Testing | No integration test for SortRow in a multi-step v1 job. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-SR-004 | Converter | Schema type format violates STANDARDS.md. Converts to Python types instead of preserving Talend types. |
| CONV-SR-005 | Converter | `CREATE_TEMP_DIR` not extracted. External sort fails if temp directory does not exist. |
| ENG-SR-005 | Engine | Streaming sort collects all data before sorting. Streaming interface is misleading for memory expectations. |
| ENG-SR-006 | Engine | External sort chunk_size default (10000) is 100x smaller than Talend BUFFER_SIZE default (1000000). Causes excessive disk I/O. |
| ENG-SR-007 | Engine | `na_position` not configurable per column. Single value applies to all sort columns. See also BUG-SR-013 (P1) which upgrades severity for single-column descending case. |
| BUG-SR-007 | Bug | `_is_streaming()` returns `True` for lists, tuples, sets. False positive for non-generator iterables. |
| BUG-SR-008 | Bug | `_validate_config()` is dead code -- never called. 38 lines of unreachable validation. |
| BUG-SR-009 | Bug | External sort writes chunks to parquet AND keeps them in `chunks` list (doubled memory). `chunks` list never used. |
| BUG-SR-014 | Bug | External sort doesn't use stable sort (`kind='stable'` missing from chunk sorts and final merge). Behavioral difference from in-memory path and Talend's stable sort guarantee. |
| BUG-SR-015 | Bug | Generator input crashes on `input_data.empty` (line 131) and `len(input_data)` (line 136) before reaching `_is_streaming()` check (line 140). Generators cannot enter the streaming path. |
| NAME-SR-001 | Naming | `temp_file` (converter) vs `temp_dir` (engine) config key mismatch. |
| NAME-SR-002 | Naming | `chunk_size` (engine) vs `BUFFER_SIZE` (Talend) naming inconsistency. |
| STD-SR-001 | Standards | `_validate_config()` exists but never called -- dead validation. |
| STD-SR-002 | Standards | Converter uses Python type format in schema instead of Talend type format. |
| STD-SR-003 | Standards | Deprecated `_map_component_parameters()` path still runs for tSortRow alongside dedicated parser. |
| PERF-SR-002 | Performance | External sort doubles memory during chunking (parquet write + in-memory list). |
| PERF-SR-003 | Performance | External sort chunk_size default 100x smaller than Talend, causing excessive temp files. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-SR-006 | Converter | `TSTATCATCHER_STATS` not extracted (rarely used). |
| ENG-SR-008 | Engine | v1-specific globalMap variables (`SORTED_BY`, `SORT_ORDERS`) not in Talend. |
| NAME-SR-003 | Naming | `max_memory_rows` does not align with Talend `BUFFER_SIZE` terminology. |
| STD-SR-004 | Standards | `print()` statement in `component_parser.py` line 856 (adjacent code, not SortRow-specific). |
| SEC-SR-001 | Security | No path validation for temp directory. |
| SEC-SR-002 | Security | Bare `except:` in cleanup catches `SystemExit` and `KeyboardInterrupt`. |
| DBG-SR-001 | Debug | `chunks` list in `_external_sort()` populated but never used. |
| PERF-SR-004 | Performance | Case-insensitive sort creates temporary columns with `.str.lower()` -- materializes full column copy. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 4 | 3 bugs (cross-cutting), 1 testing |
| P1 | 15 | 3 converter, 4 engine, 7 bugs, 1 testing |
| P2 | 17 | 2 converter, 3 engine, 5 bugs, 2 naming, 3 standards, 2 performance |
| P3 | 8 | 1 converter, 1 engine, 1 naming, 1 standards, 2 security, 1 debug, 1 performance |
| **Total** | **44** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-SR-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-SR-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-SR-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic ascending sort, basic descending sort, multi-column sort, empty input, None input, statistics tracking, and stable sort verification. Without these, no v1 engine sorting behavior is verified.

4. **Implement sort type (num vs alpha) support** (ENG-SR-001, CONV-SR-001):
   - **Converter**: In `parse_sort_row()`, add extraction of the `SORT_TYPE` elementRef from the CRITERIA table. Store as a new config key `sort_types` (list of `'num'`/`'alpha'`).
   - **Engine**: In `_process()`, before calling `sort_values()`, convert string columns with `sort_type='num'` to numeric dtype using `pd.to_numeric(errors='coerce')`. After sorting, restore original dtypes. Alternatively, use `sort_values(key=...)` with a custom key function that converts to numeric for `num`-typed columns.
   - **Impact**: Fixes the single most impactful correctness gap. Numerical vs alphabetical sort produces different results for string columns containing numbers.
   - **Risk**: Medium (requires careful dtype handling to avoid data loss).

### Short-Term (Hardening)

5. **Fix input DataFrame mutation** (BUG-SR-003): Create a copy of the input DataFrame before adding temporary sort columns. Change line 193 from `input_data[temp_col] = input_data[col].str.lower()` to `working_df = input_data.copy()` (before the loop) and `working_df[temp_col] = working_df[col].str.lower()`. Use `working_df` for sorting. **Impact**: Prevents side-effect corruption of caller's data. **Risk**: Low (extra memory for copy, but necessary for correctness).

6. **Fix IndexError in external sort and streaming sort** (BUG-SR-004, BUG-SR-005, BUG-SR-006): Add bounds checking for `sort_orders` access in all three sort paths:
   - `_external_sort()` lines 279-280: Change to `[sort_orders[j].lower() != 'desc' if j < len(sort_orders) else True for j in range(len(by_columns))]`
   - `_external_sort()` lines 307-308: Same fix
   - `_process_streaming()` lines 375-376: Change the comprehension to match the in-memory sort path pattern
   - **Impact**: Prevents crashes when sort_orders is incomplete. **Risk**: Very low.

7. **Remove deprecated `_map_component_parameters()` path for tSortRow** (CONV-SR-002, STD-SR-003): Since `parse_sort_row()` is a dedicated parser, the `elif component_type == 'tSortRow'` block in `_map_component_parameters()` (lines 217-227) should be removed. Add any missing config keys (like `na_position`) to `parse_sort_row()` instead. This eliminates the dual-path conflict. **Impact**: Cleaner converter, no conflicting config keys. **Risk**: Low -- ensure all needed config keys are set by the dedicated parser.

8. **Fix external sort to be truly external** (ENG-SR-002, PERF-SR-001): Replace the concat-then-resort approach with a proper k-way merge:
   - Use Python's `heapq.merge()` with custom comparison keys to merge sorted chunk iterators
   - Read one row at a time from each parquet file (using `pd.read_parquet()` with `columns` parameter for lazy loading, or iterate with pyarrow)
   - Write merged output to a final parquet file or build the output DataFrame incrementally
   - **Impact**: Enables sorting datasets larger than available memory. **Risk**: Medium (significant refactor of `_external_sort()`).

9. **Apply case-insensitive sort in external sort mode** (ENG-SR-003): Add the same temporary lowercase column logic from the in-memory path to `_external_sort()`. Apply it to each chunk before sorting, and to the merge comparison. **Impact**: Consistent case-insensitive behavior across all sort modes. **Risk**: Low.

10. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-SR-004): In the `except` block of `_process()` (line 228), add `if self.global_map: self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))` before re-raising. **Impact**: Error messages available for downstream error handling. **Risk**: Very low.

11. **Wire up `_validate_config()`** (BUG-SR-008, STD-SR-001): Add a call to `_validate_config()` at the beginning of `_process()`. Check the returned error list and raise `ConfigurationError` if non-empty. This catches invalid configs early with clear error messages instead of cryptic runtime failures.

12. **Fix `temp_file` vs `temp_dir` naming** (NAME-SR-001): Standardize on `temp_dir` in both the converter and engine. Change `parse_sort_row()` line 884 from `component['config']['temp_file']` to `component['config']['temp_dir']`.

### Long-Term (Optimization)

13. **Extract `BUFFER_SIZE` from Talend XML** (CONV-SR-003): In `parse_sort_row()`, add parsing of the `BUFFER_SIZE` elementParameter and map it to `max_memory_rows` in the engine config. Remove the invented `MAX_MEMORY_ROWS` and `CHUNK_SIZE` reads from `_map_component_parameters()`.

14. **Increase default chunk_size** (PERF-SR-003): Change the default from 10000 to 1000000 to match Talend's default buffer size. This reduces temp file count by 100x for external sort.

15. **Fix `_is_streaming()` false positives** (BUG-SR-007): Add `list`, `tuple`, `set` to the exclusion list: `not isinstance(data, (pd.DataFrame, dict, str, list, tuple, set))`. Or better: check for generator type explicitly using `inspect.isgenerator(data)` or `inspect.isgeneratorfunction(data)`.

16. **Remove unused `chunks` list from `_external_sort()`** (DBG-SR-001, PERF-SR-002): Delete lines 273 and 292 (`chunks = []` and `chunks.append(sorted_chunk)`). The data is already written to parquet files and read back.

17. **Replace bare `except:` with `except Exception:`** (SEC-SR-002): In the cleanup `finally` block (lines 330-335), change `except:` to `except Exception:` to avoid catching `SystemExit` and `KeyboardInterrupt`.

18. **Optimize case-insensitive sort** (PERF-SR-004): If using pandas 1.1+, replace the temporary column approach with `sort_values(key=lambda col: col.str.lower() if col.dtype == 'object' else col)`. This avoids materializing temporary columns and is more memory-efficient.

19. **Create integration test** (TEST-SR-002): Build an end-to-end test exercising `tFileInputDelimited -> tSortRow -> tLogRow` in the v1 engine, verifying context resolution, globalMap propagation, and correct sort order.

20. **Implement per-column `na_position`** (ENG-SR-007): For advanced null handling matching Talend behavior, implement custom null positioning per sort direction. This may require splitting the sort into multiple passes or using a custom key function with sentinel values for nulls.

---

## Appendix A: Converter Parameter Mapping Code

### Dedicated Parser (`parse_sort_row`, lines 860-889)

```python
def parse_sort_row(self, node, component: Dict) -> Dict:
    """Parse tSortRow specific configuration"""
    sort_columns = []
    sort_orders = []

    # Parse CRITERIA table parameter
    for param in node.findall('.//elementParameter[@name="CRITERIA"]'):
        for item in param.findall('./elementValue'):
            if item.get('elementRef') == 'COLNAME':
                col = item.get('value', '')
                if col:
                    sort_columns.append(col)
            elif item.get('elementRef') == 'SORT':
                order = item.get('value', 'asc')
                sort_orders.append(order.lower())

    # Parse other parameters
    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '')

        if name == 'EXTERNAL_SORT':
            component['config']['external_sort'] = value.lower() == 'true'
        elif name == 'TEMPFILE':
            component['config']['temp_file'] = value.strip('"')

    component['config']['sort_columns'] = sort_columns
    component['config']['sort_orders'] = sort_orders

    return component
```

**Issues with this code**:
- Line 868: Only checks `elementRef == 'COLNAME'` and `elementRef == 'SORT'`. Does NOT check for sort type (`SORT_TYPE`, `num`/`alpha`). Missing critical Talend parameter.
- Line 884: Uses key `temp_file`, but engine reads `temp_dir`. Naming mismatch.
- No extraction of `BUFFER_SIZE`, `CREATE_TEMP_DIR`.
- The `for param in node.findall('.//elementParameter[@name="CRITERIA"]')` iterates all CRITERIA parameters. If there are multiple CRITERIA groups (one per sort level), columns and orders from ALL groups are flattened into two lists. This is correct for the Talend XML structure where each `elementValue` within a single CRITERIA parameter represents one sort criterion.

### Deprecated Generic Mapper (`_map_component_parameters`, lines 217-227)

```python
# SortRow mapping
elif component_type == 'tSortRow':
    return {
        'sort_columns': config_raw.get('CRITERIA', []),
        'sort_orders': config_raw.get('SORT_ORDERS', []),
        'na_position': config_raw.get('NA_POSITION', 'last'),
        'case_sensitive': config_raw.get('CASE_SENSITIVE', True),
        'external_sort': config_raw.get('EXTERNAL_SORT', False),
        'max_memory_rows': int(config_raw.get('MAX_MEMORY_ROWS', '1000000')) if str(config_raw.get('MAX_MEMORY_ROWS', '1000000')).isdigit() else 1000000,
        'temp_dir': config_raw.get('TEMPFILE', ''),
        'chunk_size': int(config_raw.get('CHUNK_SIZE', '10000')) if str(config_raw.get('CHUNK_SIZE', '10000')).isdigit() else 10000
    }
```

**Issues with this code**:
- Line 219: `config_raw.get('CRITERIA', [])` returns the raw CRITERIA value -- for a TABLE parameter, this is NOT a list of column names. It may be a string or the entire parameter value, not the parsed `elementValue` data.
- Line 220: `config_raw.get('SORT_ORDERS', [])` -- `SORT_ORDERS` is not a Talend parameter. Always returns `[]`.
- Line 221: `config_raw.get('NA_POSITION', 'last')` -- `NA_POSITION` is not a Talend parameter. Always returns `'last'`.
- Line 222: `config_raw.get('CASE_SENSITIVE', True)` -- `CASE_SENSITIVE` is not a Talend parameter for tSortRow. Always returns `True`.
- Line 224: `config_raw.get('MAX_MEMORY_ROWS', '1000000')` -- `MAX_MEMORY_ROWS` is not a Talend parameter. Always returns `'1000000'`.
- Line 226: `config_raw.get('CHUNK_SIZE', '10000')` -- `CHUNK_SIZE` is not a Talend parameter. Always returns `'10000'`.
- These invented keys survive into the final config because `parse_sort_row()` only overwrites `sort_columns`, `sort_orders`, `external_sort`, and `temp_file`. The keys `na_position`, `case_sensitive`, `max_memory_rows`, `chunk_size` persist with their default values.

---

## Appendix B: Engine Class Structure

```
SortRow (BaseComponent)
    Configuration Keys:
        sort_columns: List[str]       # Column names to sort by (from converter)
        sort_orders: List[str]        # 'asc'/'desc' per column (from converter)
        na_position: str              # 'first'/'last' (from deprecated mapper, default 'last')
        case_sensitive: bool          # True/False (from deprecated mapper, default True)
        external_sort: bool           # Force external sort (from converter)
        max_memory_rows: int          # Auto-switch threshold (from deprecated mapper, default 1000000)
        chunk_size: int               # External sort chunk size (from deprecated mapper, default 10000)
        temp_dir: str                 # Temp directory for external sort (from deprecated mapper)
        temp_file: str                # Temp directory for external sort (from dedicated parser -- CONFLICTS with temp_dir)
        output_chunk_size: int        # Streaming output chunk size (default 10000)

    Methods:
        _validate_config() -> List[str]          # DEAD CODE -- never called
        _process(input_data) -> Dict[str, Any]   # Main entry point: routes to in-memory, external, or streaming
        _is_streaming(data) -> bool              # Check if data is generator (has false positives)
        _external_sort(data, ...) -> Dict        # Pseudo-external sort (loads all into memory)
        _process_streaming(input_data) -> Dict   # Collect-then-sort for streaming input

    Inherited from BaseComponent:
        execute(input_data) -> Dict[str, Any]    # Lifecycle: Java expressions -> context -> mode selection -> _process()
        _update_stats(rows_read, rows_ok, rows_reject) -> None
        _update_global_map() -> None             # BUGGY: references undefined 'value'
        validate_schema(df, schema) -> pd.DataFrame
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `CRITERIA` -> `COLNAME` | `sort_columns` | Mapped | -- |
| `CRITERIA` -> `SORT` | `sort_orders` | Mapped | -- |
| `CRITERIA` -> `SORT_TYPE` | -- | **Not Mapped** | **P1** -- Critical correctness gap |
| `EXTERNAL_SORT` | `external_sort` | Mapped | -- |
| `TEMPFILE` / `TEMP_DIR` | `temp_file` / `temp_dir` | Mapped (both paths, conflicting keys) | Fix naming |
| `CREATE_TEMP_DIR` | -- | **Not Mapped** | P2 |
| `BUFFER_SIZE` | `max_memory_rows` (invented) | **Not Mapped** (always default) | P1 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |
| `SCHEMA` | `schema` (generic) | Mapped | -- |

---

## Appendix D: Sort Type Impact Analysis

### The `num` vs `alpha` Gap in Detail

The missing sort type is the most impactful correctness gap. Here is a detailed analysis of how it affects different data scenarios:

#### Scenario 1: Pure Numeric Column (int64/float64 dtype)

| Sort Type | Talend Result | V1 Result | Match? |
|-----------|--------------|-----------|--------|
| `num` | `[1, 2, 10, 20]` | `[1, 2, 10, 20]` | Yes -- pandas sorts numeric dtypes numerically |
| `alpha` | `["1", "10", "2", "20"]` | `[1, 2, 10, 20]` | **NO** -- v1 sorts numerically, Talend would sort alphabetically |

#### Scenario 2: String Column with Numeric Values (object dtype)

| Sort Type | Talend Result | V1 Result | Match? |
|-----------|--------------|-----------|--------|
| `num` | `["1", "2", "10", "20"]` (numeric order) | `["1", "10", "2", "20"]` (string order) | **NO** -- v1 sorts alphabetically, Talend would sort numerically |
| `alpha` | `["1", "10", "2", "20"]` | `["1", "10", "2", "20"]` | Yes -- both sort alphabetically |

#### Scenario 3: Mixed Null Values

| Sort Type | Talend Result | V1 Result | Match? |
|-----------|--------------|-----------|--------|
| `num` with nulls | `[1, 2, 10, null]` | `[1, 2, 10, NaN]` (if numeric dtype) | Yes -- nulls last for both |
| `alpha` with nulls | `["1", "10", "2", null]` | `["1", "10", "2", NaN]` (if string dtype) | Yes -- nulls last for both |

#### Scenario 4: String Column with Leading Zeros

| Sort Type | Talend Result | V1 Result | Match? |
|-----------|--------------|-----------|--------|
| `num` | `["001", "002", "010"]` (numeric: 1, 2, 10) | `["001", "002", "010"]` (string: alphabetical happens to match for leading zeros) | **Partial** -- correct by coincidence for this specific case |
| `alpha` | `["001", "002", "010"]` | `["001", "002", "010"]` | Yes |

#### Scenario 5: String Column with Negative Numbers

| Sort Type | Talend Result | V1 Result | Match? |
|-----------|--------------|-----------|--------|
| `num` | `["-10", "-2", "1", "5"]` (numeric: -10, -2, 1, 5) | `["-10", "-2", "1", "5"]` (string: `-` < digits, then `1` < `2`) | **Partial** -- coincidental match for this case, but `["-1", "-20"]` would differ: numeric gives `[-20, -1]`, string gives `["-1", "-20"]` |
| `alpha` | `["-1", "-10", "-2", "-20"]` | Same | Yes |

#### Scenario 6: Mixed Numeric and Non-Numeric Strings

| Sort Type | Talend Result | V1 Result | Match? |
|-----------|--------------|-----------|--------|
| `num` | Java NumberFormatException for non-numeric strings -- row may fail | pandas sorts as strings (no error) | **DIFFERENT behavior** -- Talend errors, v1 silently sorts alphabetically |
| `alpha` | Alphabetical sort including non-numeric strings | Same | Yes |

**Summary**: The gap is most critical for **Scenario 2** (string columns containing numeric values with sort type `num`). This is a common pattern in Talend jobs where ID columns or code columns are stored as strings but sorted numerically. The v1 engine will silently produce incorrect sort order for these cases.

---

## Appendix E: Detailed Code Analysis

### `_validate_config()` (Lines 69-106)

This method validates:
- `sort_columns` is present and is a list (required)
- `sort_orders` is a list (if present)
- `na_position` is `'first'` or `'last'`
- `case_sensitive` is boolean
- `external_sort` is boolean
- `max_memory_rows` is a positive integer

**Not validated**: `temp_dir` (path existence), `chunk_size`, `output_chunk_size`, `sort_types` (does not exist yet).

**Critical**: This method is never called. Even if it were, it returns a list of error strings but no caller checks the list or raises exceptions. The base class `BaseComponent` does not call `_validate_config()` either.

### `_process()` (Lines 108-229)

The main processing method:
1. Check for empty/None input (lines 131-134): returns empty DataFrame
2. Check for streaming input (lines 140-141): delegates to `_process_streaming()`
3. Extract config values (lines 144-149): `sort_columns`, `sort_orders`, `na_position`, `case_sensitive`, `external_sort`, `max_memory_rows`
4. Validate sort_columns non-empty (lines 152-155): returns unsorted data with warning
5. Check if external sort needed (lines 159-161): delegates to `_external_sort()` if `external_sort=True` or `len(input_data) > max_memory_rows`
6. Build sort parameters (lines 164-176): iterate sort_columns, validate each exists in DataFrame, build ascending list with bounds checking
7. Handle case-insensitive sorting (lines 186-197): create temp lowercase columns for string columns
8. Perform sort (lines 200-206): `sort_values()` with stable sort, na_position, ignore_index
9. Remove temp columns (lines 209-212): drop `_temp_sort_*` columns from sorted result
10. Update stats (lines 215-216): set NB_LINE = NB_LINE_OK = row_count, NB_LINE_REJECT = 0
11. Set globalMap vars (lines 219-221): SORTED_BY and SORT_ORDERS (v1-specific)
12. Return result (line 225): `{'main': sorted_df}`
13. Exception handling (lines 227-229): log error and re-raise

### `_external_sort()` (Lines 243-335)

External sorting (pseudo-external -- see PERF-SR-001):
1. Get config: `chunk_size` (default 10000), `temp_dir` (default system temp)
2. Create temp directory (line 269): `tempfile.mkdtemp(prefix='sort_', dir=temp_dir)`
3. Split into chunks (lines 274-292): iterate input in `chunk_size` slices
   - Sort each chunk (lines 282-286): `sort_values()` with ascending list
   - Write to parquet (line 289): `sorted_chunk.to_parquet(temp_file)`
   - Also append to in-memory `chunks` list (line 292): UNUSED -- wasted memory
4. Read chunks back from parquet (lines 299-301): `pd.read_parquet(temp_file)` for each
5. Concatenate all chunks (line 304): `pd.concat(all_chunks, ignore_index=True)` -- ALL data in memory
6. Re-sort entire merged DataFrame (lines 310-315): `merged_df.sort_values()` -- defeats external sort
7. Update stats (lines 318-319): NB_LINE = NB_LINE_OK = row_count
8. Cleanup in `finally` block (lines 325-335): delete temp files and directory

**Key flaw**: Steps 5-6 require all data in memory simultaneously, making this functionally equivalent to in-memory sort with extra disk I/O overhead.

### `_process_streaming()` (Lines 337-396)

Streaming input handling:
1. Extract config (lines 350-352): sort_columns, sort_orders, na_position
2. Collect all chunks (lines 360-363): iterate generator, append non-empty chunks
3. Check for empty input (lines 365-368): return empty DataFrame
4. Concatenate chunks (line 371): `pd.concat(all_chunks, ignore_index=True)` -- ALL data in memory
5. Sort combined data (lines 378-383): `sort_values()`
6. Update stats (line 386): total_rows across all chunks
7. Return as generator (lines 389-394): yield sorted data in `output_chunk_size` chunks

**Key characteristic**: Sorting is a blocking operation, so streaming input must be fully materialized before sorting. The output is returned as a generator for downstream streaming consumers.

### `_is_streaming()` (Lines 231-241)

Simple check: `hasattr(data, '__iter__') and not isinstance(data, (pd.DataFrame, dict, str))`.

**Issue**: Returns `True` for lists, tuples, sets, and other iterables that are not generators. Should use `inspect.isgenerator()` or add more types to the exclusion list.

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty DataFrame input

| Aspect | Detail |
|--------|--------|
| **Talend** | tSortRow with 0 input rows produces 0 output rows. NB_LINE=0. |
| **V1** | `_process()` checks `input_data.empty` (line 131). Returns empty DataFrame with stats (0, 0, 0). |
| **Verdict** | CORRECT |

### Edge Case 2: Single-row DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Single row is output unchanged. NB_LINE=1. |
| **V1** | `sort_values()` on a single-row DataFrame returns it unchanged. Stats (1, 1, 0). |
| **Verdict** | CORRECT |

### Edge Case 3: All rows have same sort key value

| Aspect | Detail |
|--------|--------|
| **Talend** | Output order matches input order (stable sort). NB_LINE = input count. |
| **V1** | `kind='stable'` ensures original order is preserved. Correct. |
| **Verdict** | CORRECT |

### Edge Case 4: Sort column contains only null values

| Aspect | Detail |
|--------|--------|
| **Talend** | All nulls are equal -- original order preserved (stable sort). |
| **V1** | pandas `sort_values()` with `na_position='last'` places all NaN together. With stable sort, original order within the all-NaN group is preserved. |
| **Verdict** | CORRECT |

### Edge Case 5: Sort column does not exist in DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Job fails with compile error (column validated at design time). |
| **V1** | Missing column logged as warning (line 177), skipped. If NO valid columns remain, returns unsorted data. |
| **Verdict** | BEHAVIORAL DIFFERENCE -- V1 is more lenient (warning + unsorted) vs Talend (error). Acceptable for runtime flexibility. |

### Edge Case 6: String column with numeric values sorted alphabetically

| Aspect | Detail |
|--------|--------|
| **Talend** | With sort type `alpha`: `["1", "10", "2", "20"]`. With sort type `num`: `["1", "2", "10", "20"]`. |
| **V1** | Always alphabetical for string columns: `["1", "10", "2", "20"]`. No sort type distinction. |
| **Verdict** | **GAP for `num` sort type** -- silent incorrect ordering when numeric sort is intended on string columns. |

### Edge Case 7: Sort with 10+ million rows (external sort trigger)

| Aspect | Detail |
|--------|--------|
| **Talend** | With Sort on disk enabled: uses disk-based merge sort. Memory limited to BUFFER_SIZE rows. |
| **V1** | Auto-switches to external sort at `max_memory_rows` (default 1M). BUT the external sort loads all data into memory at the merge step. OOM for very large datasets. |
| **Verdict** | **GAP** -- external sort does not actually reduce memory usage. |

### Edge Case 8: Case-insensitive sort with external sort enabled

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- Talend tSortRow does not have case-insensitive option. |
| **V1** | case_sensitive=False with external_sort=True: external sort ignores case_sensitive flag. Silently sorts case-sensitively. |
| **Verdict** | **BUG** -- inconsistent behavior between in-memory and external sort modes. |

### Edge Case 9: sort_orders list shorter than sort_columns list

| Aspect | Detail |
|--------|--------|
| **Talend** | Each criterion always has all three sub-parameters. List length mismatch cannot occur. |
| **V1 (in-memory)** | Handled correctly: `if i < len(sort_orders)` check defaults to ascending. |
| **V1 (external)** | **CRASHES**: `sort_orders[j]` IndexError. No bounds check. |
| **V1 (streaming)** | **CRASHES**: ascending list has wrong length, pandas raises ValueError. |
| **Verdict** | **BUG in external and streaming paths**. In-memory path is correct. |

### Edge Case 10: Sort column is date type

| Aspect | Detail |
|--------|--------|
| **Talend** | Date columns sorted chronologically (earlier dates first for ascending). Sort type should be `num`. |
| **V1** | pandas sorts `datetime64` columns chronologically by default. Correct behavior without sort type. |
| **Verdict** | CORRECT (for datetime64 dtype). If date is stored as string, same gap as Edge Case 6 applies. |

### Edge Case 11: Sort column is boolean type

| Aspect | Detail |
|--------|--------|
| **Talend** | Boolean values sorted: False (0) before True (1) for ascending. |
| **V1** | pandas sorts boolean columns as False < True. Ascending puts False first. |
| **Verdict** | CORRECT |

### Edge Case 12: Very wide DataFrame (100+ columns, sort by 1)

| Aspect | Detail |
|--------|--------|
| **Talend** | Sorts efficiently -- only sort key column is compared. |
| **V1** | `sort_values()` only compares specified columns. Other columns are reordered but not compared. pandas handles this efficiently. |
| **Verdict** | CORRECT |

### Edge Case 13: DataFrame with duplicate column names

| Aspect | Detail |
|--------|--------|
| **Talend** | Schema does not allow duplicate column names. |
| **V1** | pandas allows duplicate column names. `sort_values(by=[col])` may produce unexpected results if `col` matches multiple columns. |
| **Verdict** | EDGE CASE -- unlikely in Talend-converted jobs but possible in v1-native usage. |

### Edge Case 14: Sort order contains unexpected values (e.g., 'ascending')

| Aspect | Detail |
|--------|--------|
| **Talend** | Only 'asc' or 'desc' possible (dropdown selection). |
| **V1** | In-memory path (line 173): checks for `'desc'` and `'descending'`, else defaults to ascending. `'ascending'` would correctly default to ascending (True). `'invalid'` would also default to ascending. |
| **Verdict** | CORRECT -- lenient parsing handles edge cases. |

### Edge Case 15: External sort with temp directory that does not exist

| Aspect | Detail |
|--------|--------|
| **Talend** | With `CREATE_TEMP_DIR=true`, directory is created. With `CREATE_TEMP_DIR=false`, job fails. |
| **V1** | `tempfile.mkdtemp(dir=temp_dir)` creates a subdirectory within `temp_dir`, but `temp_dir` itself must exist. If it does not, `FileNotFoundError` is raised. No auto-create option. |
| **Verdict** | **GAP** -- `CREATE_TEMP_DIR` not implemented. |

---

## Appendix G: Talend XML Structure for CRITERIA Table

The CRITERIA parameter in Talend XML uses a table structure with `elementValue` child nodes. Each sort criterion is represented by a group of `elementValue` nodes with different `elementRef` attributes:

```xml
<elementParameter field="TABLE" name="CRITERIA">
  <!-- First sort criterion -->
  <elementValue elementRef="COLNAME" value="name"/>
  <elementValue elementRef="SORT" value="asc"/>
  <elementValue elementRef="SORT_TYPE" value="alpha"/>
  <!-- Second sort criterion -->
  <elementValue elementRef="COLNAME" value="age"/>
  <elementValue elementRef="SORT" value="desc"/>
  <elementValue elementRef="SORT_TYPE" value="num"/>
</elementParameter>
```

The `parse_sort_row()` method correctly iterates these `elementValue` nodes but only extracts `COLNAME` and `SORT`, missing `SORT_TYPE`. To fix CONV-SR-001, the parser should also capture `SORT_TYPE`:

```python
# Proposed fix for parse_sort_row():
sort_types = []
for item in param.findall('./elementValue'):
    if item.get('elementRef') == 'COLNAME':
        col = item.get('value', '')
        if col:
            sort_columns.append(col)
    elif item.get('elementRef') == 'SORT':
        order = item.get('value', 'asc')
        sort_orders.append(order.lower())
    elif item.get('elementRef') == 'SORT_TYPE':
        sort_type = item.get('value', 'alpha')
        sort_types.append(sort_type.lower())

component['config']['sort_types'] = sort_types
```

**Note**: The exact `elementRef` name for sort type may vary between Talend versions. Common names include `SORT_TYPE`, `SORT_NUM_OR_ALPHA`, `num_or_alpha`. The converter should check all known variants or use a fallback strategy.

---

## Appendix H: Cross-Cutting Bug Impact on SortRow

### BUG-SR-001: `_update_global_map()` undefined `value`

**Location**: `src/v1/engine/base_component.py` line 304

```python
def _update_global_map(self) -> None:
    """Update global map with component statistics"""
    if self.global_map:
        for stat_name, stat_value in self.stats.items():
            self.global_map.put_component_stat(self.id, stat_name, stat_value)
        # Log the statistics for debugging
        logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} {stat_name}: {value}")
```

The variable `value` on line 304 is undefined. The loop variable is `stat_value` (line 301). When `global_map` is not None, this raises `NameError: name 'value' is not defined` after the for loop completes.

**Impact on SortRow**: After `_process()` successfully sorts data and calls `_update_stats()`, the `execute()` method calls `_update_global_map()` (line 218 of `base_component.py`). If `global_map` is provided, the stats are written correctly (line 302 works fine), but the log statement on line 304 crashes. The exception propagates up through `execute()`, causing the SortRow execution to FAIL despite the sort having completed successfully.

**Workaround**: Pass `global_map=None` to avoid the crash. Stats will not be written to globalMap.

### BUG-SR-002: `GlobalMap.get()` undefined `default`

**Location**: `src/v1/engine/global_map.py` line 28

```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

The `default` parameter is not in the method signature. This causes `NameError: name 'default' is not defined` on every `.get()` call.

**Impact on SortRow**: If any downstream code calls `global_map.get(f"{sort_row_id}_NB_LINE")`, it will crash. Additionally, `get_component_stat()` (line 58) calls `self.get(key, default)` with two arguments, but `get()` only accepts one positional argument, causing `TypeError`.

**Note**: SortRow's `_process()` method only calls `global_map.put()` (lines 220-221), which works correctly. The `get()` bug affects consumers of SortRow's globalMap variables, not SortRow itself.

---

## Appendix I: In-Memory Sort Path -- Line-by-Line Walkthrough

This appendix traces the exact execution flow of the in-memory sort path for a concrete example.

### Example Input

```python
input_data = pd.DataFrame({
    'name': ['Charlie', 'Alice', 'Bob', 'Alice', 'Bob'],
    'age': [30, 25, 35, 22, 35],
    'city': ['NYC', 'LA', 'NYC', 'SF', 'LA']
})

config = {
    'sort_columns': ['name', 'age'],
    'sort_orders': ['asc', 'desc'],
    'na_position': 'last',
    'case_sensitive': True,
    'external_sort': False,
    'max_memory_rows': 1000000
}
```

### Execution Trace

**Line 131**: `input_data is None or input_data.empty` -> False (5 rows, not empty). Continues.

**Line 137**: Logs `[tSortRow_1] Processing started: 5 rows`.

**Line 140-141**: `self._is_streaming(input_data)` -> False (input_data is a DataFrame). Continues to in-memory path.

**Lines 144-149**: Extract config:
- `sort_columns = ['name', 'age']`
- `sort_orders = ['asc', 'desc']`
- `na_position = 'last'`
- `case_sensitive = True`
- `external_sort = False`
- `max_memory_rows = 1000000`

**Line 152**: `if not sort_columns:` -> False (`['name', 'age']` is truthy). Continues.

**Line 159**: `if external_sort or len(input_data) > max_memory_rows:` -> `False or (5 > 1000000)` -> False. Uses in-memory sort.

**Lines 164-176**: Build sort parameters:
- Iteration 0: `col = 'name'`, exists in columns. `by_columns = ['name']`. `i=0 < len(sort_orders)=2`, `order = 'asc'`, `ascending = [True]`.
- Iteration 1: `col = 'age'`, exists in columns. `by_columns = ['name', 'age']`. `i=1 < len(sort_orders)=2`, `order = 'desc'`, `ascending = [True, False]`.

**Line 179**: `if not by_columns:` -> False. Continues.

**Line 186**: `if not case_sensitive:` -> `not True` -> False. Skip case-insensitive logic.

**Lines 200-206**: Perform sort:
```python
sorted_df = input_data.sort_values(
    by=['name', 'age'],
    ascending=[True, False],
    na_position='last',
    ignore_index=True,
    kind='stable'
)
```

**Result**:
```
   name  age city
0  Alice   25   LA    # Alice group, age desc: 25 first
1  Alice   22   SF    # Alice group, age desc: 22 second
2    Bob   35  NYC    # Bob group, age desc: 35 first
3    Bob   35   LA    # Bob group, age desc: 35 (stable: original order preserved)
4 Charlie  30  NYC    # Charlie group
```

**Lines 209-212**: No temp columns to drop (case_sensitive=True).

**Lines 215-216**: `_update_stats(5, 5, 0)`:
- `stats['NB_LINE'] = 5`
- `stats['NB_LINE_OK'] = 5`
- `stats['NB_LINE_REJECT'] = 0`

**Lines 219-221**: GlobalMap:
- `global_map.put("tSortRow_1_SORTED_BY", "name,age")`
- `global_map.put("tSortRow_1_SORT_ORDERS", "asc,desc")`

**Line 223**: Logs `[tSortRow_1] Processing complete: sorted 5 rows by ['name', 'age']`.

**Line 225**: Returns `{'main': sorted_df}`.

### Expected vs Actual Output

| Row | name | age | city | Sort Position |
|-----|------|-----|------|---------------|
| 0 | Alice | 25 | LA | Primary: 'A' (asc, first). Secondary: 25 > 22 (desc, first in Alice group). |
| 1 | Alice | 22 | SF | Primary: 'A' (asc, first). Secondary: 22 < 25 (desc, second in Alice group). |
| 2 | Bob | 35 | NYC | Primary: 'B' (asc, second). Secondary: 35 (desc, first in Bob group). |
| 3 | Bob | 35 | LA | Primary: 'B' (asc, second). Secondary: 35 = 35 (stable: original order). |
| 4 | Charlie | 30 | NYC | Primary: 'C' (asc, third). Only one Charlie row. |

---

## Appendix J: External Sort Path -- Line-by-Line Walkthrough

### Example Input

Same data as Appendix I, but with external sort forced:

```python
config = {
    'sort_columns': ['name', 'age'],
    'sort_orders': ['asc', 'desc'],
    'external_sort': True,
    'chunk_size': 2,  # Small chunks for demonstration
    'temp_dir': '/tmp'
}
```

### Execution Trace

**Line 159**: `if external_sort or len(input_data) > max_memory_rows:` -> `True or ...` -> True. Delegates to `_external_sort()`.

**Line 161**: Returns `self._external_sort(input_data, ['name', 'age'], ['asc', 'desc'], 'last')`.

**_external_sort() Line 264**: `chunk_size = self.config.get('chunk_size', 10000)` -> 2.

**Line 265**: `temp_dir = self.config.get('temp_dir', tempfile.gettempdir())` -> '/tmp'.

**Line 269**: `sort_dir = tempfile.mkdtemp(prefix='sort_', dir='/tmp')` -> e.g., '/tmp/sort_abc123'.

**Lines 274-292**: Split into chunks:
- Chunk 0 (rows 0-1): `['Charlie', 30]`, `['Alice', 25]`. Sorted: `['Alice', 25]`, `['Charlie', 30]`. Written to `chunk_0.parquet`.
- Chunk 1 (rows 2-3): `['Bob', 35]`, `['Alice', 22]`. Sorted: `['Alice', 22]`, `['Bob', 35]`. Written to `chunk_1.parquet`.
- Chunk 2 (row 4): `['Bob', 35]`. Sorted: `['Bob', 35]` (single row). Written to `chunk_2.parquet`.

**Line 279-280**: `ascending = [sort_orders[j].lower() != 'desc' for j in range(len(by_columns))]`:
- `j=0`: `'asc' != 'desc'` -> True (ascending)
- `j=1`: `'desc' != 'desc'` -> False (descending)
- `ascending = [True, False]`

**WARNING**: If `sort_orders` had fewer elements than `by_columns`, this would raise `IndexError` (BUG-SR-004).

**Lines 299-301**: Read chunks back from parquet files.

**Line 304**: `merged_df = pd.concat(all_chunks, ignore_index=True)` -> All 5 rows in memory.

**Lines 310-315**: Re-sort entire merged DataFrame with `sort_values()`. Same parameters as chunk sort.

**Final result**: Same as in-memory sort. But with extra disk I/O overhead.

**Lines 325-335**: Cleanup: delete 3 parquet files + sort directory.

### Memory Profile

| Phase | Memory Usage | Notes |
|-------|-------------|-------|
| Chunk creation | ~2 rows at a time | Good -- only chunk_size rows in memory |
| Chunk list (`chunks`) | All 5 rows | BAD -- BUG-SR-009: chunks list keeps all data |
| Parquet read-back | All 5 rows | BAD -- all chunks read into `all_chunks` |
| Concat | All 5 rows + concat overhead | BAD -- PERF-SR-001 |
| Re-sort | All 5 rows + sort overhead | BAD -- defeats external sort purpose |
| Peak memory | ~3x input data | Much worse than in-memory sort (~2x) |

---

## Appendix K: Streaming Sort Path -- Line-by-Line Walkthrough

### Example Input

```python
def streaming_input():
    yield pd.DataFrame({'name': ['Charlie', 'Alice'], 'age': [30, 25]})
    yield pd.DataFrame({'name': ['Bob', 'Alice', 'Bob'], 'age': [35, 22, 35]})

config = {
    'sort_columns': ['name'],
    'sort_orders': ['asc'],
    'na_position': 'last',
    'output_chunk_size': 2
}
```

### Execution Trace

**Line 140-141**: `self._is_streaming(streaming_input())` -> True (generator object has `__iter__` and is not DataFrame/dict/str).

**Line 141**: Returns `self._process_streaming(input_data)`.

**_process_streaming() Lines 350-352**: Extract config.

**Lines 360-363**: Collect chunks:
- Chunk 0: 2 rows (`Charlie`, `Alice`). Non-empty -> appended. `total_rows = 2`.
- Chunk 1: 3 rows (`Bob`, `Alice`, `Bob`). Non-empty -> appended. `total_rows = 5`.

**Line 371**: `combined_df = pd.concat(all_chunks, ignore_index=True)` -> All 5 rows.

**Lines 374-376**: Build sort parameters:
- `by_columns = ['name']` (exists in combined_df)
- `ascending = [sort_orders[i].lower() != 'desc' for i in range(len(by_columns)) if i < len(sort_orders)]`
- `i=0, i < 1` -> True. `'asc' != 'desc'` -> True. `ascending = [True]`.

**Lines 378-383**: Sort combined data.

**Line 386**: `_update_stats(5, 5, 0)`.

**Lines 389-394**: Return generator:
```python
def sorted_generator():
    chunk_size = 2  # output_chunk_size
    for i in range(0, 5, 2):
        yield sorted_df.iloc[i:i+2]
```

Generator yields:
- Chunk 0: rows 0-1 (`Alice(22)`, `Alice(25)`)
- Chunk 1: rows 2-3 (`Bob(35)`, `Bob(35)`)
- Chunk 2: row 4 (`Charlie(30)`)

### Memory Profile

| Phase | Memory Usage | Notes |
|-------|-------------|-------|
| Chunk collection | Accumulated: 2, then 5 rows | Grows linearly with total input |
| Concat | All 5 rows | Full materialization |
| Sort | All 5 rows + sort overhead | Full dataset in memory |
| Generator output | 2 rows at a time | Only output is chunked |
| Peak memory | ~2x input data | Same as in-memory sort |

**Key insight**: The streaming input does NOT reduce memory for sorting. All data is collected before sorting can begin. The only benefit of the streaming OUTPUT is reduced memory for downstream consumers.

---

## Appendix L: Comparison with Other v1 Transform Components

### Feature Parity Comparison

| Feature | SortRow | FilterRows | AggregateRow | UniqueRow |
|---------|---------|------------|--------------|-----------|
| Dedicated converter parser | Yes (`parse_sort_row`) | Yes (`parse_filter_rows`) | Yes (`parse_aggregate`) | Yes (`parse_unique`) |
| Deprecated mapper also runs | **Yes** (dual-path) | No | No | **Yes** (dual-path) |
| `_validate_config()` called | **No** (dead code) | **No** (dead code) | **No** (dead code) | **No** (dead code) |
| Custom exception usage | No (bare raise) | No (bare raise) | No (bare raise) | No (bare raise) |
| GlobalMap stats | Yes (via base class) | Yes (via base class) | Yes (via base class) | Yes (via base class) |
| V1-specific globalMap vars | Yes (SORTED_BY, SORT_ORDERS) | No | No | No |
| Streaming support | Yes (collect-then-sort) | Yes (filter per chunk) | Yes (collect-then-aggregate) | Yes (collect-then-dedupe) |
| External/disk mode | Yes (pseudo-external) | N/A | No | No |
| REJECT flow | N/A (sort has no rejects) | **No** (should have rejects) | N/A | **No** (should have duplicates) |
| v1 unit tests | **None** | **None** | **None** | **None** |

### Pattern: Dead `_validate_config()`

The `_validate_config()` method is dead code across ALL audited transform components. This is a systemic issue in the v1 engine, not specific to SortRow. The base class `BaseComponent` defines `_process()` as abstract but does NOT define or call `_validate_config()`. Each component implements it independently, but no component or base class calls it.

**Recommended fix**: Add validation as a standard lifecycle step in `BaseComponent.execute()`, before `_process()` is called. This fixes the issue for ALL components in one change.

### Pattern: No Custom Exception Usage

All audited transform components use bare `raise` (re-raise) or `raise Exception(...)` instead of the custom exception hierarchy defined in `src/v1/engine/exceptions.py` (`ConfigurationError`, `DataValidationError`, `ComponentExecutionError`). The exception hierarchy exists but is unused by transform components.

**Recommended fix**: Wrap exceptions in `ComponentExecutionError(self.id, message, cause=e)` for consistent error handling across all components.

---

## Appendix M: Proposed Engine Fix for Sort Type Support

### Implementation Strategy

The sort type (`num` vs `alpha`) can be implemented using pandas `sort_values(key=...)` parameter (available since pandas 1.1.0):

```python
# In _process(), after building by_columns and ascending lists:

sort_types = self.config.get('sort_types', [])

def make_sort_key(col_series, col_index):
    """Create sort key based on sort type."""
    if col_index < len(sort_types) and sort_types[col_index] == 'num':
        # Numerical sort: convert to numeric, coercing errors to NaN
        return pd.to_numeric(col_series, errors='coerce')
    elif col_index < len(sort_types) and sort_types[col_index] == 'alpha':
        # Alphabetical sort: convert to string
        return col_series.astype(str)
    else:
        # Default: use existing dtype (pandas default behavior)
        return col_series

# Build key function mapping
key_functions = {}
for i, col in enumerate(by_columns):
    col_idx = i  # capture for closure
    key_functions[col] = lambda s, idx=col_idx: make_sort_key(s, idx)

# Perform sort with key functions
sorted_df = input_data.sort_values(
    by=by_columns,
    ascending=ascending,
    na_position=na_position,
    ignore_index=True,
    kind='stable',
    key=lambda col: key_functions.get(col.name, lambda s: s)(col)
)
```

### Alternative Strategy (Pre-sort Column Conversion)

If the `key=` parameter approach is not feasible (e.g., pandas version compatibility), an alternative is to:

1. Create temporary columns with converted dtypes
2. Sort by temporary columns
3. Drop temporary columns

```python
temp_cols = {}
for i, col in enumerate(by_columns):
    if i < len(sort_types) and sort_types[i] == 'num':
        temp_col = f'_sort_num_{col}'
        input_data[temp_col] = pd.to_numeric(input_data[col], errors='coerce')
        temp_cols[col] = temp_col
    elif i < len(sort_types) and sort_types[i] == 'alpha':
        temp_col = f'_sort_alpha_{col}'
        input_data[temp_col] = input_data[col].astype(str)
        temp_cols[col] = temp_col

# Replace column names in by_columns with temp columns
sort_by = [temp_cols.get(col, col) for col in by_columns]

# Sort using temp columns
sorted_df = input_data.sort_values(by=sort_by, ascending=ascending, ...)

# Drop temp columns
sorted_df = sorted_df.drop(columns=list(temp_cols.values()))
```

**Warning**: This approach has the same input-mutation issue as the case-insensitive sort (BUG-SR-003). Must use `input_data.copy()` first.

### Converter Changes Required

In `parse_sort_row()`, add extraction of `SORT_TYPE`:

```python
sort_types = []
for item in param.findall('./elementValue'):
    if item.get('elementRef') == 'COLNAME':
        col = item.get('value', '')
        if col:
            sort_columns.append(col)
    elif item.get('elementRef') == 'SORT':
        order = item.get('value', 'asc')
        sort_orders.append(order.lower())
    elif item.get('elementRef') in ('SORT_TYPE', 'SORT_NUM_OR_ALPHA'):
        sort_type = item.get('value', 'alpha')
        sort_types.append(sort_type.lower())

component['config']['sort_types'] = sort_types
```

### Validation Changes Required

In `_validate_config()`, add validation for `sort_types`:

```python
sort_types = self.config.get('sort_types', [])
if sort_types and not isinstance(sort_types, list):
    errors.append("Config 'sort_types' must be a list")
for st in sort_types:
    if st not in ('num', 'alpha'):
        errors.append(f"Invalid sort type '{st}': must be 'num' or 'alpha'")
```

---

## Appendix N: Risk Assessment Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Wrong sort order due to missing sort type | **High** -- affects any job with numeric strings | **High** -- data silently sorted incorrectly | Implement sort type support (Rec #4) |
| OOM during external sort | **Medium** -- only affects datasets > memory | **High** -- job crash with no recovery | Fix external sort to use k-way merge (Rec #8) |
| IndexError in external/streaming sort | **Low** -- only when sort_orders < sort_columns | **High** -- job crash | Add bounds checking (Rec #6) |
| DataFrame mutation from case-insensitive sort | **Low** -- only when case_sensitive=False | **Medium** -- upstream data corruption | Copy DataFrame before modification (Rec #5) |
| GlobalMap crash from base class bug | **High** -- any use of global_map | **High** -- ALL components fail | Fix _update_global_map() (Rec #1) |
| Performance degradation from small chunk_size | **Medium** -- only external sort | **Low** -- slower but correct | Increase default to 1000000 (Rec #14) |
| Temp directory not created | **Low** -- only when using custom temp dir | **Medium** -- external sort fails | Extract CREATE_TEMP_DIR or auto-create (Rec #5) |

### Production Usage Scenarios

| Scenario | Risk Level | Issues Affecting | Workaround |
|----------|-----------|-----------------|------------|
| Simple ascending sort by one string column | **Low** | BUG-SR-001/002 (if globalMap used) | Pass global_map=None |
| Multi-column sort with mixed types | **Medium** | ENG-SR-001 (sort type), BUG-SR-001/002 | Ensure columns have correct dtypes before sorting |
| Sort with case_sensitive=False | **Medium** | BUG-SR-003 (mutation), ENG-SR-003 (external) | Use in-memory sort only; accept mutation |
| External sort for large datasets | **High** | ENG-SR-002 (OOM), BUG-SR-004/005 (IndexError), PERF-SR-001/002/003 | Use in-memory sort with increased JVM/Python memory |
| Sort in multi-component pipeline | **Medium** | BUG-SR-001/002 (globalMap), BUG-SR-003 (mutation) | Isolate sort; pass global_map=None |
| Streaming input to sort | **Medium** | BUG-SR-006 (ascending mismatch), ENG-SR-005 (all-in-memory) | Pre-collect data; call _process() directly |

---

## Appendix O: Version History and Change Log

### Current State

- **Engine file**: `src/v1/engine/components/transform/sort_row.py` -- 397 lines
- **Converter parser**: `src/converters/complex_converter/component_parser.py` lines 860-889 (30 lines)
- **Converter generic mapper**: `src/converters/complex_converter/component_parser.py` lines 217-227 (11 lines)
- **Engine registry**: `src/v1/engine/engine.py` lines 107-108
- **Package exports**: `src/v1/engine/components/transform/__init__.py` line 23

### Files That Would Need Changes for Full Production Readiness

| File | Changes Needed | Priority |
|------|---------------|----------|
| `src/v1/engine/base_component.py` line 304 | Fix `value` -> `stat_value` | P0 |
| `src/v1/engine/global_map.py` line 26 | Add `default` parameter to `get()` | P0 |
| `src/v1/engine/components/transform/sort_row.py` lines 186-212 | Copy DataFrame before mutation; add sort type support | P1 |
| `src/v1/engine/components/transform/sort_row.py` lines 279-280, 307-308 | Add bounds check for sort_orders | P1 |
| `src/v1/engine/components/transform/sort_row.py` lines 375-376 | Fix ascending list length for streaming | P1 |
| `src/v1/engine/components/transform/sort_row.py` lines 243-335 | Rewrite external sort with proper k-way merge | P1 |
| `src/converters/complex_converter/component_parser.py` lines 860-889 | Add SORT_TYPE extraction; fix temp_file->temp_dir | P1 |
| `src/converters/complex_converter/component_parser.py` lines 217-227 | Remove deprecated tSortRow block from generic mapper | P2 |
| `tests/v1/unit/` | Create test_sort_row.py with P0/P1 test cases | P0 |

---

## Appendix P: Talend tSortRow Generated Java Code Pattern

Understanding the Java code that Talend generates for tSortRow helps identify behavioral expectations that the v1 Python engine should match.

### Talend Generated Sort Comparator (Simplified)

When Talend compiles a job containing tSortRow, it generates a Java `Comparator` class that implements the sort criteria. The generated pattern looks approximately like this:

```java
// Talend-generated comparator for tSortRow_1
// Criteria: name (alpha, asc), age (num, desc)
class SortableRow implements Comparable<SortableRow> {
    String name;
    Integer age;
    // ... other columns

    @Override
    public int compareTo(SortableRow other) {
        int result;

        // Criterion 1: name, alpha, asc
        if (this.name == null && other.name == null) {
            result = 0;
        } else if (this.name == null) {
            result = 1;  // nulls last for ascending
        } else if (other.name == null) {
            result = -1;
        } else {
            result = this.name.compareTo(other.name);  // String comparison
        }
        if (result != 0) return result;  // ascending: no negation

        // Criterion 2: age, num, desc
        if (this.age == null && other.age == null) {
            result = 0;
        } else if (this.age == null) {
            result = -1;  // nulls last for descending (reversed)
        } else if (other.age == null) {
            result = 1;
        } else {
            result = this.age.compareTo(other.age);  // Numeric comparison
        }
        if (result != 0) return -result;  // descending: negated

        return 0;  // equal on all criteria
    }
}
```

### Key Behavioral Implications

1. **Null handling is direction-dependent**: For ascending, nulls sort AFTER non-null values (nulls-last). For descending, the comparator is negated, which means nulls-last in the original comparison becomes nulls-first after negation. The v1 engine applies a single `na_position` to ALL columns regardless of direction, which may differ for descending columns.

2. **Sort type determines comparison method**: `alpha` uses `String.compareTo()` (lexicographic), `num` uses `Number.compareTo()` (value-based). The v1 engine has no equivalent mechanism -- it relies entirely on pandas dtype.

3. **Stable sort via Collections.sort()**: Talend uses `java.util.Collections.sort()` with the generated comparator. Java's merge sort is guaranteed stable. The v1 engine matches this with `kind='stable'`.

4. **External sort uses TreeMap-based merge**: When "Sort on disk" is enabled, Talend uses a `TreeMap` (balanced binary tree) to perform k-way merge of sorted chunk files. This guarantees O(N * log(K)) merge time where K is the number of chunks, with only K rows in memory during the merge. The v1 engine's `pd.concat()` + `sort_values()` approach is O(N * log(N)) and requires all N rows in memory.

5. **Buffer flushing**: Talend flushes the in-memory buffer to a temporary file using Java serialization when the buffer reaches `BUFFER_SIZE` rows. Each flushed file is independently sorted. The v1 engine uses parquet format for temporary files, which is a reasonable alternative.

### Behavioral Mapping Summary

| Talend Java Behavior | V1 Python Equivalent | Fidelity |
|---------------------|---------------------|----------|
| `String.compareTo()` for alpha | pandas lexicographic sort on object dtype | High |
| `Number.compareTo()` for num | pandas numeric sort on numeric dtype | High (if dtype is numeric) |
| Null handling per direction | Single `na_position` for all columns | **Medium** -- differs for mixed asc/desc |
| `Collections.sort()` stable | `sort_values(kind='stable')` | High |
| TreeMap k-way merge | `pd.concat()` + `sort_values()` | **Low** -- not a true merge |
| Buffer size = `BUFFER_SIZE` | chunk_size (default 10000, not from Talend) | **Low** -- 100x smaller default |
| Temp files via Java serialization | Temp files via parquet | Medium (different format, same concept) |
| Direction-dependent null position | Global `na_position` | **Medium** |
