# Audit Report: tPivotToColumnsDelimited / PivotToColumnsDelimited

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tPivotToColumnsDelimited` |
| **V1 Engine Class** | `PivotToColumnsDelimited` |
| **Engine File** | `src/v1/engine/components/transform/pivot_to_columns_delimited.py` (301 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/pivot_to_columns_delimited.py` (148 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tPivotToColumnsDelimited")` decorator-based dispatch |
| **Registry Aliases** | `PivotToColumnsDelimited`, `tPivotToColumnsDelimited` |
| **Category** | Transform / File (hybrid: pivots data then writes to delimited file) |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/pivot_to_columns_delimited.py` | Engine implementation (301 lines) |
| `src/converters/talend_to_v1/components/transform/pivot_to_columns_delimited.py` | Converter class (148 lines) |
| `tests/converters/talend_to_v1/components/test_pivot_to_columns_delimited.py` | Converter tests (51 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 18/18 params extracted (16 _java.xml + 2 framework); D-38 config keys; GROUPBYS TABLE stride-1; 7 needs_review (all engine_gap) |
| Engine Feature Parity | **Y** | 1 | 5 | 4 | 2 | No NB_LINE_OUT globalMap; no include-header control; no append mode; no quoting; no die_on_error |
| Code Quality | **R** | 4 | 5 | 6 | 2 | line_terminator removed in pandas 3.x (guaranteed crash); double float-to-int crash; unicode_escape order bug |
| Performance & Memory | **Y** | 0 | 1 | 3 | 1 | Row-by-row lambda O(rows*cols); streaming mode silently produces wrong results |
| Testing | **Y** | 0 | 0 | 1 | 0 | 51 converter tests (gold standard); zero engine unit tests |

**Overall: YELLOW -- Converter production-ready (Green); engine has P0 crash bugs and significant feature gaps**

**Top Actions**:
1. Fix `line_terminator` -> `lineterminator` (P0 crash on pandas 3.x)
2. Fix double float-to-int conversion crash on empty strings (P0)
3. Fix cross-cutting `_update_global_map()` crash (P0)
4. Add `NB_LINE_OUT` globalMap variable (P0)
5. Add engine unit tests

---

## 3. Talend Feature Baseline

### What tPivotToColumnsDelimited Does

`tPivotToColumnsDelimited` is a **combined transform-and-output** component in the **File** family. It performs a transpose (pivot) operation on input data: it takes rows where a "pivot column" has repeated values, aggregates a designated "aggregation column" using a selected function (sum, count, min, max, first, last), groups by one or more "group by" columns, and writes the result to a delimited file. The distinct values from the pivot column become new column headers in the output.

It requires at least three columns in the input schema: the pivot column, the aggregation column, and one or more group-by keys.

**Source**: [tPivotToColumnsDelimited Standard properties (Talend 8.0)](https://help.talend.com/en-US/components/8.0/delimited/tpivottocolumnsdelimited-standard-properties), [Talaxie GitHub _java.xml](https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tPivotToColumnsDelimited/tPivotToColumnsDelimited_java.xml)
**Component family**: File (Delimited)
**Available in**: All Talend products (Standard Job framework)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Schema | `SCHEMA` | Schema editor | -- | Column definitions. Defines input structure for pivot, aggregation, and group-by selection. |
| 2 | Pivot Column | `PIVOT_COLUMN` | Column selector | -- | **Required**. Column whose distinct values become new column headers. |
| 3 | Aggregation Column | `AGGREGATION_COLUMN` | Column selector | -- | **Required**. Column containing data to aggregate. |
| 4 | Aggregation Function | `AGGREGATION_FUNCTION` | CLOSED_LIST | `"sum"` | Function: sum, count, min, max, first, last. |
| 5 | Group By | `GROUPBYS` | TABLE (stride-1) | -- | One or more columns to group by. Form the row index in pivoted output. |
| 6 | File Name | `FILENAME` | TEXT (expression) | -- | **Required**. Absolute output file path. |
| 7 | Row Separator | `ROWSEPARATOR` | TEXT | `"\\n"` | Row delimiter for output file. |
| 8 | Field Separator | `FIELDSEPARATOR` | TEXT | `";"` | Field delimiter for output file. Talend default is semicolon. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 9 | Create | `CREATE` | BOOLEAN (CHECK) | `true` | Create output file including parent directories. |
| 10 | Encoding | `ENCODING` | CLOSED_LIST | `"ISO-8859-15"` | Character encoding for output. _java.xml default is ISO-8859-15, not UTF-8. |
| 11 | Advanced Separator | `ADVANCED_SEPARATOR` | BOOLEAN (CHECK) | `false` | Enable locale-aware number formatting. |
| 12 | Thousands Separator | `THOUSANDS_SEPARATOR` | TEXT | `","` | Thousands grouping char. Visible when ADVANCED_SEPARATOR=true. |
| 13 | Decimal Separator | `DECIMAL_SEPARATOR` | TEXT | `"."` | Decimal point char. Visible when ADVANCED_SEPARATOR=true. |
| 14 | CSV Options | `CSV_OPTION` | BOOLEAN (CHECK) | `false` | Enable RFC4180 CSV mode with quoting. |
| 15 | Escape Char | `ESCAPE_CHAR` | TEXT | `'"'` | Escape character inside quoted fields. Active when CSV_OPTION=true. |
| 16 | Text Enclosure | `TEXT_ENCLOSURE` | TEXT | `'"'` | Quote character for field values. Active when CSV_OPTION=true. |
| 17 | Don't Generate Empty File | `DELETE_EMPTYFILE` | BOOLEAN (CHECK) | `false` | Suppress file creation when output is empty. |
| 18 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | BOOLEAN (CHECK) | `false` | Framework param. Capture stats for tStatCatcher. |

**Not in _java.xml**: `INCLUDEHEADER`, `APPEND`, `COMPRESS`, `DIE_ON_ERROR`. These appear in online documentation but not in the actual `tPivotToColumnsDelimited_java.xml` on Talaxie GitHub. Converter correctly omits them.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | **Required**. Input data with pivot, aggregation, and group-by columns. |
| `FLOW` (Main) | Output | Row > Main | Pivoted data: group-by columns plus one column per distinct pivot value. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires on subjob success. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on subjob error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires on component success. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires on component error. |

**Note**: No REJECT output connector. Errors either halt the job or are captured in ERROR_MESSAGE.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total input rows read. |
| `{id}_NB_LINE_OUT` | Integer | After execution | Rows written to output file after pivoting. |
| `{id}_ERROR_MESSAGE` | String | On error | Error message when component fails. |
| `{id}_FILENAME` | String | After execution | Resolved output file path. |

### 3.5 Behavioral Notes

1. **Pivot mechanics**: Distinct values of the pivot column become new column headers. For each group-by combination, the aggregation function is applied to the aggregation column partitioned by pivot value.
2. **Missing combinations**: Sparse pivot results produce empty cells (null/empty string) where a group-by combination lacks a pivot value.
3. **Dynamic output schema**: Output column count depends on runtime data. Downstream components must handle variable-width schemas.
4. **Encoding**: _java.xml default is ISO-8859-15, matching other Talend file I/O components.
5. **Statistics**: NB_LINE = input rows; NB_LINE_OUT = pivoted output rows. These differ because pivoting aggregates multiple input rows.
6. **File creation**: When CREATE=true, file and parent directories are created.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

**Converter**: `PivotToColumnsDelimitedConverter` registered via `@REGISTRY.register("tPivotToColumnsDelimited")` decorator. Uses `_build_component_dict()` with `type_name="PivotToColumnsDelimited"`.

**Converter flow**:
1. Registry dispatches to `PivotToColumnsDelimitedConverter.convert()`
2. Extracts all 16 _java.xml params using `_get_str()`, `_get_bool()` helpers
3. GROUPBYS TABLE parsed via module-level `_parse_group_bys()` function (stride-1)
4. 2 framework params extracted last
5. Returns `ComponentResult` with component dict, warnings, and 7 needs_review entries

| # | Talend XML Parameter | Extracted? | V1 Config Key | Default | Notes |
|----|----------------------|------------|---------------|---------|-------|
| 1 | `PIVOT_COLUMN` | Yes | `pivot_column` | `""` | Via `_get_str()` |
| 2 | `AGGREGATION_COLUMN` | Yes | `aggregation_column` | `""` | Via `_get_str()` |
| 3 | `AGGREGATION_FUNCTION` | Yes | `aggregation_function` | `"sum"` | CLOSED_LIST default matches Talend |
| 4 | `GROUPBYS` | Yes | `groupbys` | `[]` | TABLE stride-1 via `_parse_group_bys()`, quotes stripped |
| 5 | `FILENAME` | Yes | `filename` | `""` | Via `_get_str()` |
| 6 | `CREATE` | Yes | `create` | `True` | Via `_get_bool()` |
| 7 | `ROWSEPARATOR` | Yes | `rowseparator` | `"\\n"` | D-38 config key |
| 8 | `FIELDSEPARATOR` | Yes | `fieldseparator` | `";"` | D-38 config key |
| 9 | `ENCODING` | Yes | `encoding` | `"ISO-8859-15"` | Correct _java.xml default |
| 10 | `ADVANCED_SEPARATOR` | Yes | `advanced_separator` | `False` | Via `_get_bool()` |
| 11 | `THOUSANDS_SEPARATOR` | Yes | `thousands_separator` | `","` | Via `_get_str()` |
| 12 | `DECIMAL_SEPARATOR` | Yes | `decimal_separator` | `"."` | Via `_get_str()` |
| 13 | `CSV_OPTION` | Yes | `csv_option` | `False` | Via `_get_bool()` |
| 14 | `ESCAPE_CHAR` | Yes | `escape_char` | `'"'` | Via `_get_str()` |
| 15 | `TEXT_ENCLOSURE` | Yes | `text_enclosure` | `'"'` | Via `_get_str()` |
| 16 | `DELETE_EMPTYFILE` | Yes | `delete_emptyfile` | `False` | Via `_get_bool()` |
| 17 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | `False` | Framework param |
| 18 | `LABEL` | Yes | `label` | `""` | Framework param |
| -- | `SCHEMA` | Yes | (schema) | -- | Via `_parse_schema()` base class |

**Summary**: 18 of 18 applicable parameters extracted (100%). All 16 _java.xml params + 2 framework params.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Via `_parse_schema()` base class |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | |
| `key` | Yes | |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by base class |

### 4.3 Expression Handling

Context variables (`context.var`) and Java expressions are handled at the orchestrator level before the converter is called. The converter stores raw string values; expression resolution happens at engine runtime via `BaseComponent.execute()`.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| ~~CONV-PCD-001~~ | ~~P1~~ | **SUPERSEDED** -- Old complex_converter issues replaced by talend_to_v1 rewrite |

**No open converter issues.** The talend_to_v1 converter extracts all 16 _java.xml params with correct defaults.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | `advanced_separator` | Engine does not read from config | engine_gap |
| 2 | `thousands_separator` | Engine does not read from config | engine_gap |
| 3 | `decimal_separator` | Engine does not read from config | engine_gap |
| 4 | `csv_option` | Engine does not read from config | engine_gap |
| 5 | `escape_char` | Engine does not read from config | engine_gap |
| 6 | `text_enclosure` | Engine does not read from config | engine_gap |
| 7 | `delete_emptyfile` | Engine does not read from config | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Pivot operation | **Yes** | High | `_process()` line 201 | Uses `pd.pivot_table()` |
| 2 | Aggregation functions (sum/count/min/max) | **Yes** | High | line 205 | Directly supported by pandas |
| 3 | Aggregation (first/last) | **Yes** | Medium | line 205 | NaN handling may differ from Talend |
| 4 | Multiple group-by columns | **Yes** | High | line 202 | Passed as `index=` |
| 5 | NaN replacement | **Yes** | High | line 219 | `fillna('')` |
| 6 | Write to delimited file | **Yes** | High | line 257 | Uses `pd.to_csv()` |
| 7 | Custom field separator | **Yes** | High | line 259 | `sep=field_separator` |
| 8 | Custom row separator | **No (crashes)** | None | line 260 | `line_terminator` removed in pandas 3.x |
| 9 | Encoding support | **Yes** | High | line 261 | |
| 10 | Create file control | **Yes** | High | line 251 | |
| 11 | Include Header control | **No** | N/A | -- | Always includes header |
| 12 | Append mode | **No** | N/A | -- | Always overwrites |
| 13 | Text enclosure / quoting | **No** | N/A | -- | Not implemented |
| 14 | CSV Options (RFC4180) | **No** | N/A | -- | Not implemented |
| 15 | Advanced separator (locale) | **No** | N/A | -- | Not implemented |
| 16 | Empty file suppression | **No** | N/A | -- | Always creates file |
| 17 | Die on error | **No** | N/A | -- | Always raises |
| 18 | `{id}_NB_LINE_OUT` globalMap | **No** | N/A | -- | Sets NB_LINE_OK instead (wrong key) |
| 19 | `{id}_ERROR_MESSAGE` globalMap | **No** | N/A | -- | Not implemented |
| 20 | `{id}_FILENAME` globalMap | **No** | N/A | -- | Not implemented |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-PCD-001 | **P0** | **No `{id}_NB_LINE_OUT` globalMap**: Sets `NB_LINE_OK` instead. Downstream components referencing NB_LINE_OUT get null. |
| ENG-PCD-002 | **P1** | **No Include Header control**: Always writes headers. Jobs suppressing headers produce incorrect output. |
| ENG-PCD-003 | **P1** | **No Append mode**: Always overwrites. Iterative jobs lose all data except last iteration. |
| ENG-PCD-004 | **P1** | **No text enclosure / quoting**: Fields containing delimiter corrupt output. |
| ENG-PCD-005 | **P1** | **No `{id}_ERROR_MESSAGE` globalMap**: Downstream error handlers get null. |
| ENG-PCD-006 | **P2** | **No compressed output**: COMPRESS=true writes uncompressed files. |
| ENG-PCD-007 | **P2** | **No `{id}_FILENAME` globalMap**: Resolved filename not stored. |
| ENG-PCD-008 | **P2** | **No empty-file suppression**: DELETE_EMPTYFILE ignored. |
| ENG-PCD-009 | **P2** | **No locale-aware numeric formatting**: ADVANCED_SEPARATOR features ignored. |
| ENG-PCD-010 | **P1** | **No die_on_error support**: Always raises on error. |
| ENG-PCD-011 | **P3** | **Aggregation function not validated**: Invalid function names produce cryptic pandas errors. |
| ENG-PCD-012 | **P3** | **Default field separator mismatch**: Engine default is `','`; Talend default is `';'`. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` | Input row count. Correct. |
| `{id}_NB_LINE_OUT` | Yes | **No** | -- | Engine sets NB_LINE_OK (wrong key). |
| `{id}_NB_LINE_OK` | N/A | **Yes** | `_update_stats()` | Wrong key for file-output components. |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Not implemented. |
| `{id}_FILENAME` | Yes | **No** | -- | Not implemented. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-PCD-001 | **P0** | `pivot_to_columns_delimited.py:213-215` | **Float-to-int conversion creates mixed-type columns**: Row-by-row lambda produces int/float/NaN mix, changing dtype to object. Combined with subsequent fillna('') and second conversion loop, crashes on empty strings. |
| BUG-PCD-002 | **P0** | `pivot_to_columns_delimited.py:223-227` | **`float(x)` on empty string after fillna**: After NaN replaced with '', numeric dtype check may still pass, causing `ValueError: could not convert string to float: ''`. Data-dependent crash. |
| BUG-PCD-003 | **P0** | `pivot_to_columns_delimited.py:260` | **`line_terminator` removed in pandas 3.x**: `to_csv(line_terminator=...)` raises `TypeError` on pandas 3.0+. Must use `lineterminator`. Every file-writing execution crashes unconditionally. |
| BUG-PCD-004 | **P0** | `base_component.py:304` | **CROSS-CUTTING: `_update_global_map()` undefined `value` variable**: Crashes all components when globalMap is set. |
| BUG-PCD-005 | **P1** | `pivot_to_columns_delimited.py:170` | **`unicode_escape` decoding dangerous**: Can corrupt Windows paths and raise UnicodeDecodeError. |
| BUG-PCD-006 | **P1** | `pivot_to_columns_delimited.py:169-183` | **unicode_escape applied BEFORE quote stripping**: Wrong order corrupts quoted separators. |
| BUG-PCD-007 | **P1** | `pivot_to_columns_delimited.py:191-194` | **Tab separator fails single-char validation**: `\t` arrives as two chars, fails validation. Tab-delimited output broken. |
| BUG-PCD-008 | **P1** | `pivot_to_columns_delimited.py:85-99` | **`_validate_config()` is dead code**: Never called from _process() or execute(). |
| BUG-PCD-009 | **P1** | `pivot_to_columns_delimited.py:245-248` | **Broad exception catch**: Post-processing failures misreported as "Pivot operation failed". |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-PCD-001 | **P2** | **Engine config key `group_by_columns`**: Converter now uses `groupbys` (D-38). Engine reads `group_by_columns`. Key mismatch documented as engine_gap via needs_review. |
| NAME-PCD-002 | **P2** | **Engine config key `row_separator`/`field_separator`**: Converter uses `rowseparator`/`fieldseparator` (D-38). Engine reads `row_separator`/`field_separator`. Key mismatch. |
| NAME-PCD-003 | **P2** | **NB_LINE_OK vs NB_LINE_OUT**: Engine sets wrong globalMap key for file-output component. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-PCD-001 | **P2** | "`_validate_config()` called or dead code" | Method exists but never called. Dead code. |
| STD-PCD-002 | **P2** | "Use custom exception types" | Raises generic `ValueError`. Should use `ConfigurationError`/`FileOperationError`. |
| STD-PCD-003 | **P2** | "Consistent validation path" | Config validated in two places that can diverge. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-PCD-001 | **P2** | `logger.info()` on line 183 logs field separator at INFO level. Should be `logger.debug()`. |
| DBG-PCD-002 | **P3** | Multiple verbose debug messages for micro-steps (lines 198, 199, 208, 209, 212, 217, 222). |

### 6.5 Security

No critical security concerns. Path traversal is not a concern for Talend-converted jobs where config is trusted.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Level usage | Mostly correct. One INFO-level message should be DEBUG (line 183). |
| Sensitive data | No sensitive data logged. |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | **Not used**. All errors raise generic `ValueError`. |
| Exception chaining | **Not used**. `raise ValueError(f"...{e}")` loses traceback. |
| die_on_error handling | **Not implemented**. Always raises. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints. |
| Parameter types | `_process()` uses `Optional[pd.DataFrame]` -- correct. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-PCD-001 | **P1** | **Row-by-row lambda O(rows*cols)**: Lines 213-215 and 223-227 use per-cell Python lambdas. For 1000 pivot columns x 100K rows = 200M calls. Should use vectorized operations. |
| PERF-PCD-002 | **P2** | **Redundant double float-to-int conversion**: Second loop is no-op after fillna changes dtype to object. |
| PERF-PCD-003 | **P2** | **`fillna('')` creates DataFrame copy**: Doubles memory for large pivot results. |
| PERF-PCD-004 | **P3** | **Streaming mode produces incorrect results**: Pivot requires all data; chunked execution produces wrong aggregations with NaN artifacts. Component does not override `_auto_select_mode()`. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | **Incompatible**. Pivot requires all data. Streaming produces silently wrong results. Not overridden to prevent. |
| Memory threshold | At 3GB auto-threshold, switches to streaming (incorrect). |
| Large data handling | Memory scales with distinct pivot values * group-by groups. 10K+ pivot values risk OOM. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 51 | `tests/converters/talend_to_v1/components/test_pivot_to_columns_delimited.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None (converter covered by regression guard) |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-PCD-001 | **P2** | No engine unit tests for PivotToColumnsDelimited (301 lines untested) |

### 8.3 Recommended Test Cases

**P0 -- Must Have Before Production**:
1. Basic pivot with sum aggregation
2. Multiple group-by columns
3. All aggregation functions (sum, count, min, max, first, last)
4. File output with correct separator, encoding
5. Empty input handling (None and empty DataFrame)
6. Missing configuration validation

**P1 -- Important**:
7. NaN handling in sparse pivots
8. Custom field and row separators (including tab)
9. Non-UTF8 encoding with special characters
10. create=False skips file write

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 4 | **BUG-PCD-001**, **BUG-PCD-002**, **BUG-PCD-003**, **BUG-PCD-004** |
| P1 | 5 | **BUG-PCD-005**, **BUG-PCD-006**, **BUG-PCD-007**, **BUG-PCD-008**, **BUG-PCD-009** |
| P2 | 9 | **NAME-PCD-001**, **NAME-PCD-002**, **NAME-PCD-003**, **STD-PCD-001**, **STD-PCD-002**, **STD-PCD-003**, **DBG-PCD-001**, **PERF-PCD-002**, **PERF-PCD-003** |
| P3 | 2 | **DBG-PCD-002**, **PERF-PCD-004** |
| **Total** | **20** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Bug (BUG) | 9 | BUG-PCD-001 through BUG-PCD-009 |
| Engine (ENG) | 12 | ENG-PCD-001 through ENG-PCD-012 |
| Naming (NAME) | 3 | NAME-PCD-001 through NAME-PCD-003 |
| Standards (STD) | 3 | STD-PCD-001 through STD-PCD-003 |
| Performance (PERF) | 4 | PERF-PCD-001 through PERF-PCD-004 |
| Testing (TEST) | 1 | TEST-PCD-001 |
| Debug (DBG) | 2 | DBG-PCD-001, DBG-PCD-002 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` undefined `default` parameter |

---

## 10. Recommendations

### Immediate (Before Production)
- Fix `line_terminator` -> `lineterminator` for pandas 3.x compatibility (BUG-PCD-003)
- Fix double float-to-int conversion crash (BUG-PCD-001, BUG-PCD-002)
- Fix cross-cutting `_update_global_map()` crash (BUG-PCD-004)
- Add `NB_LINE_OUT` globalMap variable (ENG-PCD-001)

### Short-term (Hardening)
- Fix unicode_escape ordering and tab separator handling (BUG-PCD-005/006/007)
- Add include-header and append mode support (ENG-PCD-002/003)
- Add text enclosure / quoting support (ENG-PCD-004)
- Add die_on_error support (ENG-PCD-010)
- Add engine unit tests (TEST-PCD-001)

### Long-term (Optimization)
- Vectorize float-to-int conversion (PERF-PCD-001)
- Override `_auto_select_mode()` to prevent streaming (PERF-PCD-004)
- Add aggregation function validation (ENG-PCD-011)

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Streaming mode data loss | **High** | **High** | Pivot requires all data; chunked execution produces silently wrong aggregations. Override `_auto_select_mode()` to always return BATCH. |
| Pivot column cardinality explosion | **Medium** | **High** | Unbounded pivot values create extremely wide DataFrames (10K+ columns). Causes OOM for large datasets. Add cardinality check with configurable limit. |
| File output race conditions | **Medium** | **Medium** | Concurrent jobs writing to same file path produce corrupted output. No file locking. Add advisory file locking or unique temp file + atomic rename. |
| Memory usage for large group-by cardinality | **Medium** | **Medium** | High-cardinality group-by (1M+ groups) with many pivot values creates very large DataFrames. Monitor memory and add configurable threshold. |
| Encoding mismatch (ISO-8859-15 vs UTF-8) | **High** | **Medium** | _java.xml default is ISO-8859-15 but engine default is UTF-8. Converter now emits correct default. Jobs with non-ASCII data and mismatched encoding produce garbled output. |
| CSV injection via unescaped pivot values | **Low** | **Medium** | Pivot column values become column headers in output CSV. Malicious values (e.g., `=CMD("...")`) could trigger formula injection in downstream spreadsheet applications. Add sanitization for CSV output. |

### High-Risk Job Patterns

1. **Large-cardinality pivots**: Jobs where pivot column has 1000+ distinct values produce extremely wide output DataFrames. Memory grows linearly with distinct values.
2. **Iterative file output**: Jobs using tFlowToIterate that call tPivotToColumnsDelimited in a loop. No append mode means each iteration overwrites the file.
3. **Streaming threshold exceeded**: Input data > 3GB triggers automatic streaming mode, producing silently incorrect results. No warning emitted.
4. **Mixed-type aggregation columns**: Aggregation column with mixed types (numeric and string) causes pandas `pivot_table()` to fall back to object dtype, breaking numeric aggregation functions.

### Safe Usage Patterns

1. **Moderate cardinality**: Pivot column with < 100 distinct values, group-by with < 10K groups. Fits comfortably in memory.
2. **Batch mode explicit**: Force `execution_mode=BATCH` in config to prevent streaming.
3. **Numeric-only aggregation**: Ensure aggregation column is purely numeric (no strings, no mixed types).
4. **Single-file output**: Each subjob writes to a unique file path. No concurrent access.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talend 8.0 docs | https://help.talend.com/en-US/components/8.0/delimited/tpivottocolumnsdelimited-standard-properties | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tPivotToColumnsDelimited/tPivotToColumnsDelimited_java.xml | Component definition XML |
| Engine source | `src/v1/engine/components/transform/pivot_to_columns_delimited.py` | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/transform/pivot_to_columns_delimited.py` | Converter audit |
| Converter tests | `tests/converters/talend_to_v1/components/test_pivot_to_columns_delimited.py` | Test coverage assessment |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` undefined `default` parameter |
| XCUT-003 | `base_component.py:174` | `replace_in_config` literal `[i]` bug |
| XCUT-004 | `base_component.py:351` | `validate_schema` inverted nullable logic |
| XCUT-005 | `base_component.py:267-278` | `_execute_streaming` drops reject DataFrames |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after gold-standard rewrite with Section 11 Risk Assessment*
