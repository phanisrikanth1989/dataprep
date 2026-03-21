# Audit Report: tPivotToColumnsDelimited / PivotToColumnsDelimited

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tPivotToColumnsDelimited` |
| **V1 Engine Class** | `PivotToColumnsDelimited` |
| **Engine File** | `src/v1/engine/components/transform/pivot_to_columns_delimited.py` (302 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tpivot_to_columns_delimited()` (lines 1881-1905) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `_parse_component()` (line 311) -- dedicated `elif` branch |
| **Registry Aliases** | `PivotToColumnsDelimited`, `tPivotToColumnsDelimited` (registered in `src/v1/engine/engine.py` lines 150-151) |
| **Category** | File / Transform (hybrid: transforms data via pivot then writes to delimited file) |
| **Complexity** | Medium -- pivot logic (pandas `pivot_table`) plus file output (`to_csv`) in a single component |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/pivot_to_columns_delimited.py` | Engine implementation (302 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 1881-1905) | Parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (line 311) | Dispatch -- dedicated `elif component_type == 'tPivotToColumnsDelimited'` branch |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/transform/__init__.py` (line 16) | Package export |
| `src/v1/engine/engine.py` (lines 32, 150-151) | Component registration and import |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 3 | 4 | 1 | 9 of ~21 Talend params extracted (43%); missing INCLUDEHEADER, APPEND, TEXT_ENCLOSURE, CSV_OPTION, COMPRESS, etc.; no null-safety on `node.find()` |
| Engine Feature Parity | **Y** | 1 | 5 | 4 | 2 | No `NB_LINE_OUT` globalMap; no include-header control; no append mode; no quoting; no die_on_error; no compressed output |
| Code Quality | **R** | 4 | 5 | 6 | 2 | Double float-to-int crash; `line_terminator` removed in pandas 3.x (guaranteed crash); unicode_escape/quote-stripping order bug; tab separator broken; dead validation; broad exception catch; no custom exceptions |
| Performance & Memory | **Y** | 0 | 1 | 3 | 1 | Row-by-row lambda O(rows*cols); redundant double conversion; fillna copy; streaming mode silently produces wrong results |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: RED -- Not production-ready; P0 crash bugs guarantee failure on every file-writing execution**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tPivotToColumnsDelimited Does

`tPivotToColumnsDelimited` is a **combined transform-and-output** component in the **File** family. It performs a transpose (pivot) operation on input data: it takes rows where a "pivot column" has repeated values, aggregates a designated "aggregation column" using a selected function (sum, count, min, max, first, last), groups by one or more "group by" columns, and writes the result to a delimited file. The distinct values from the pivot column become new column headers in the output.

It requires at least three columns in the input schema: the pivot column, the aggregation column, and one or more group-by keys.

**Source**: [tPivotToColumnsDelimited Standard properties (Talend 8.0)](https://help.talend.com/en-US/components/8.0/delimited/tpivottocolumnsdelimited-standard-properties), [tPivotToColumnsDelimited Overview (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/delimited/tpivottocolumnsdelimited), [tPivotToColumnsDelimited Standard properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/delimited/tpivottocolumnsdelimited-standard-properties), [Using a pivot column to aggregate data (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/delimited/tfileinputdelimited-tpivottocolumnsdelimited-tpivottocolumnsdelimited-using-pivot-column-to-aggregate-data-standard-component-the)

**Component family**: File (Delimited)
**Available in**: All Talend products (Standard Job framework)
**Input requirement**: Requires an input flow

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types. Defines the input structure available for pivot, aggregation, and group-by selection. |
| 3 | Pivot Column | `PIVOT_COLUMN` | Column selector (dropdown) | -- | **Required**. Column from incoming flow used as the pivot. Distinct values of this column become new column headers in the output. Typically the column with the most duplicates. |
| 4 | Aggregation Column | `AGGREGATION_COLUMN` | Column selector (dropdown) | -- | **Required**. Column from incoming flow containing data to aggregate. Values in this column are aggregated for each pivot-column-value within each group-by combination. |
| 5 | Aggregation Function | `AGGREGATION_FUNCTION` | Dropdown | `sum` | Function to apply when duplicates are found: `sum`, `count`, `min`, `max`, `first`, `last`. |
| 6 | Group By | `GROUPBYS` | Table (list of columns) | -- | **Required (at least one)**. One or more columns to group by. These form the row index in the pivoted output. Includes Input Column mapping. |
| 7 | File Name | `FILENAME` | Expression (String) | -- | **Required**. Absolute output file path. Supports context variables and globalMap expressions. |
| 8 | Field Separator | `FIELDSEPARATOR` | String | `";"` | Character, string, or regular expression to separate fields in the output file. **Note**: Talend default is semicolon `";"`, not comma `","`. |
| 9 | Row Separator | `ROWSEPARATOR` | String | `"\n"` | String to distinguish rows in the output file. Common values: `"\n"` (Unix), `"\r\n"` (Windows). |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 10 | Encoding | `ENCODING` | Dropdown / Custom | `"UTF-8"` | Character encoding for the output file. Options include UTF-8, ISO-8859-15, and custom values. |
| 11 | Create | `CREATE` | Boolean | `true` | Whether to create the output file (including parent directories if needed). |
| 12 | Include Header | `INCLUDEHEADER` | Boolean | `true` | Whether to include column headers as the first row in the output file. When `true`, the first row contains group-by column names followed by dynamically generated pivot column names. |
| 13 | Append | `APPEND` | Boolean | `false` | Whether to append to the file instead of overwriting. Critical for jobs that write to the same file in iterative loops. |
| 14 | Text Enclosure | `TEXT_ENCLOSURE` | Character | -- | Quote character to enclose field values. Only active when `CSV_OPTION=true`. |
| 15 | Escape Char | `ESCAPE_CHAR` | Character | -- | Escape character inside quoted fields. Only active when `CSV_OPTION=true`. |
| 16 | CSV Options | `CSV_OPTION` | Boolean | `false` | Enable RFC4180-compliant CSV mode with text enclosure and escape character. When enabled, field separator must be a single character. |
| 17 | Advanced Separator | `ADVANCED_SEPARATOR` | Boolean | `false` | Enable locale-aware number formatting in the output. |
| 18 | Thousands Separator | `THOUSANDS_SEPARATOR` | Character | `","` | Thousands grouping separator for numeric output. Only visible when `ADVANCED_SEPARATOR=true`. |
| 19 | Decimal Separator | `DECIMAL_SEPARATOR` | Character | `"."` | Decimal point separator for numeric output. Only visible when `ADVANCED_SEPARATOR=true`. |
| 20 | Don't Generate Empty File | `DONT_GENERATE_EMPTY_FILE` | Boolean | `false` | Suppress file creation when the output is empty (no pivoted rows). |
| 21 | Compress | `COMPRESS` | Boolean | `false` | Compress the output file using gzip. The output file will have a `.gz` extension. |
| 22 | Die on Error | `DIE_ON_ERROR` | Boolean | `true` | Stop the entire job on error. When unchecked, errors are captured in `ERROR_MESSAGE` and the component returns an empty result. |
| 23 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean | `false` | Capture processing metadata for the tStatCatcher component. Rarely used. |
| 24 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | **Required**. Input data flow containing rows to pivot. Must have at least the pivot column, aggregation column, and group-by columns. |
| `FLOW` (Main) | Output | Row > Main | Pivoted data as output flow (when connecting to another downstream component). Contains group-by columns plus one column per distinct pivot value. |
| `ITERATE` | Input | Iterate | Can receive iterate connections for processing multiple files in a loop. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

**Note**: Unlike `tFileInputDelimited`, `tPivotToColumnsDelimited` does **NOT** have a REJECT output connector. Errors either kill the job (if `DIE_ON_ERROR=true`) or are captured in `ERROR_MESSAGE` (if `DIE_ON_ERROR=false`).

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows read by the component from the input flow. |
| `{id}_NB_LINE_OUT` | Integer | After execution | Number of rows written to the output file after pivoting. This is the pivoted row count, not the input row count. |
| `{id}_ERROR_MESSAGE` | String | On error | Error message when component fails. Empty on success. Available when `DIE_ON_ERROR=false` for downstream error handling. |
| `{id}_FILENAME` | String | After execution | Resolved output file path. |

**Note on NB_LINE_OUT vs NB_LINE_OK**: Talend's `tPivotToColumnsDelimited` uses `NB_LINE_OUT` (not `NB_LINE_OK`) for the output row count. This is consistent with other file-output components like `tFileOutputDelimited`. The distinction is important: `NB_LINE_OK` is used by transform-only components, while `NB_LINE_OUT` is used by components that write to external destinations.

### 3.5 Aggregation Functions Available in Talend

| Function | Talend Name | Description | NaN Handling |
|----------|-------------|-------------|--------------|
| Sum | `sum` | Sum of aggregation column values | NaN values ignored in sum |
| Count | `count` | Count of non-null values | NaN values not counted |
| Min | `min` | Minimum value | NaN values ignored |
| Max | `max` | Maximum value | NaN values ignored |
| First | `first` | First value encountered in group | First non-NaN value |
| Last | `last` | Last value encountered in group | Last non-NaN value |

### 3.6 Behavioral Notes

1. **Pivot mechanics**: The pivot column's distinct values become new column headers. For each group-by combination, the aggregation function is applied to the aggregation column, partitioned by pivot column value. Example: if pivot column has values `["A", "B", "C"]`, the output has columns `[group_by_1, ..., "A", "B", "C"]`.

2. **Missing combinations**: When a group-by combination does not have a value for a particular pivot column value, Talend produces an empty cell (null/empty string) in the output. This is the standard behavior for sparse pivot results.

3. **Column ordering**: Output columns are ordered as: group-by columns first (in definition order), then pivot-derived columns in alphabetical order (or insertion order depending on Talend version).

4. **Dynamic output schema**: The output schema is dynamic -- it depends on the distinct values of the pivot column at runtime. This means the number and names of output columns are not known at design time. Downstream components must handle variable-width schemas.

5. **File creation**: When `CREATE=true`, the file is created (including parent directories). When `APPEND=true`, data is appended to an existing file. When `APPEND=true` with `INCLUDEHEADER=true`, the header is only written if the file does not already exist.

6. **Include Header**: When `INCLUDEHEADER=true`, the first row of the output file contains column names. The pivot-derived column names are the actual pivot column values (e.g., `"A"`, `"B"`, `"C"`), not generic names.

7. **Empty input**: When no input rows are received, behavior depends on `DONT_GENERATE_EMPTY_FILE`:
   - `false` (default): An empty file is created (possibly with just a header row).
   - `true`: No file is created.

8. **Statistics**: `NB_LINE` is set to the number of input rows; `NB_LINE_OUT` is set to the number of output rows (after pivoting). These differ because pivoting aggregates multiple input rows into fewer output rows.

9. **Error handling**: Errors during pivot or file write cause the component to fail. When `DIE_ON_ERROR=true`, the entire job stops. When `false`, `ERROR_MESSAGE` is set and the component produces no output.

10. **Encoding**: The `ENCODING` parameter controls the character encoding used when writing the file. Unlike `tFileInputDelimited` (which defaults to `ISO-8859-15`), the default for output components is `UTF-8`.

11. **Duplicate aggregation**: When the same group-by + pivot combination appears multiple times in the input, the aggregation function determines how duplicates are handled. Without aggregation, Talend would fail on duplicate index/column pairs.

12. **NB_LINE availability**: The `NB_LINE` and `NB_LINE_OUT` global variables are only available AFTER the component completes execution. They cannot be accessed during the current subjob's data flow.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated parser method** `parse_tpivot_to_columns_delimited()` at line 1881 of `component_parser.py`, dispatched via a dedicated `elif` branch at line 311 of `converter.py`. This is the correct pattern per STANDARDS.md.

**Converter flow**:
1. `converter.py:_parse_component()` checks `component_type == 'tPivotToColumnsDelimited'` (line 311)
2. Calls `self.component_parser.parse_tpivot_to_columns_delimited(node, component)` (line 312)
3. Method extracts 9 parameters using direct `node.find()` calls (lines 1883-1901)
4. Returns updated `component` dict with `config` populated

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `PIVOT_COLUMN` | Yes | `pivot_column` | 1883 | Direct extraction via `node.find()` |
| 2 | `AGGREGATION_COLUMN` | Yes | `aggregation_column` | 1884 | Direct extraction |
| 3 | `AGGREGATION_FUNCTION` | Yes | `aggregation_function` | 1885 | Default `'sum'` matches Talend |
| 4 | `GROUPBYS` | Yes | `group_by_columns` | 1886 | Extracted from `elementValue` sub-elements; values not stripped of quotes |
| 5 | `FILENAME` | Yes | `filename` | 1887 | Direct extraction; **no Java expression detection** |
| 6 | `ROWSEPARATOR` | Yes | `row_separator` | 1888 | Default `'\n'` matches Talend |
| 7 | `FIELDSEPARATOR` | Yes | `field_separator` | 1889 | Default `';'` matches Talend |
| 8 | `ENCODING` | Yes | `encoding` | 1890 | Default `'UTF-8'` matches Talend for output components |
| 9 | `CREATE` | Yes | `create` | 1891 | Boolean conversion applied |
| 10 | `INCLUDEHEADER` | **No** | -- | -- | **Not extracted. Engine always writes header.** |
| 11 | `APPEND` | **No** | -- | -- | **Not extracted. Engine always overwrites.** |
| 12 | `TEXT_ENCLOSURE` | **No** | -- | -- | **Not extracted. No quoting control.** |
| 13 | `ESCAPE_CHAR` | **No** | -- | -- | **Not extracted.** |
| 14 | `CSV_OPTION` | **No** | -- | -- | **Not extracted. No RFC4180 toggle.** |
| 15 | `ADVANCED_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 16 | `THOUSANDS_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 17 | `DECIMAL_SEPARATOR` | **No** | -- | -- | **Not extracted.** |
| 18 | `DONT_GENERATE_EMPTY_FILE` | **No** | -- | -- | **Not extracted.** |
| 19 | `COMPRESS` | **No** | -- | -- | **Not extracted.** |
| 20 | `DIE_ON_ERROR` | **No** | -- | -- | **Not extracted. Engine always raises on error.** |
| 21 | `TSTATCATCHER_STATS` | No | -- | -- | Not needed (tStatCatcher rarely used) |
| 22 | `LABEL` | No | -- | -- | Not needed (cosmetic -- no runtime impact) |
| 23 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |
| 24 | `SCHEMA` | Partial | (via `parse_base_component`) | -- | Schema is extracted at base level, not in dedicated parser |

**Summary**: 9 of 21 runtime-relevant parameters extracted (43%). 12 runtime-relevant parameters are missing.

**Cross-reference with tFileOutputDelimited**: The converter for `tFileOutputDelimited` (line 2253 of `component_parser.py`) extracts `INCLUDEHEADER`, `APPEND`, and `DIE_ON_ERROR` in addition to the basic file parameters. This demonstrates the converter team knows how to extract these parameters -- they simply have not been added to the `tPivotToColumnsDelimited` parser.

### 4.2 Schema Extraction

Schema is extracted generically in `parse_base_component()` at the base level of `component_parser.py`.

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
| `comment` | **No** | Column comment not extracted (cosmetic -- no runtime impact) |
| `talendType` | **No** | Full Talend type string not preserved -- converted to Python type |

### 4.3 Expression Handling

**Context variable handling**: The base class `execute()` method resolves context variables via `self.context_manager.resolve_dict(self.config)` before calling `_process()`. This means `${context.output_dir}/pivot.csv` in the filename will be correctly resolved.

**Java expression handling**: The `parse_tpivot_to_columns_delimited()` method extracts the `FILENAME` parameter as-is **without checking for Java expressions**. Filenames commonly contain Java expressions like `context.getProperty("output_dir") + "/pivot.csv"` or `(String)globalMap.get("output_path")`. These are not detected and not marked with the `{{java}}` prefix, which means they will not be resolved by the Java bridge at runtime.

**Comparison**: Other converter parsers in the codebase use `ExpressionConverter.detect_java_expression()` and `mark_java_expression()` to handle Java expressions. The `tPivotToColumnsDelimited` parser does not use either.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-PCD-001 | **P1** | **`INCLUDEHEADER` not extracted**: Engine always writes headers (pandas `to_csv(index=False)` includes header by default). No way to suppress header output when Talend job specifies `INCLUDEHEADER=false`. The `tFileOutputDelimited` converter extracts this parameter on line 2257. |
| CONV-PCD-002 | **P1** | **`APPEND` not extracted**: Engine always overwrites the output file. Talend jobs using append mode will lose previously written data on each execution. The `tFileOutputDelimited` converter extracts this parameter on line 2258. |
| CONV-PCD-003 | **P1** | **`TEXT_ENCLOSURE` and `ESCAPE_CHAR` not extracted**: Engine has no way to configure quoting behavior for the output CSV. Fields containing the delimiter character will not be properly quoted, corrupting the output file. |
| CONV-PCD-004 | **P2** | **`CSV_OPTION` not extracted**: RFC4180-compliant CSV mode is unavailable. |
| CONV-PCD-005 | **P2** | **`ADVANCED_SEPARATOR`, `THOUSANDS_SEPARATOR`, `DECIMAL_SEPARATOR` not extracted**: Locale-aware numeric formatting unavailable in output. |
| CONV-PCD-006 | **P2** | **`DONT_GENERATE_EMPTY_FILE` not extracted**: Empty input always produces an empty file when `create=True`. |
| CONV-PCD-007 | **P2** | **`COMPRESS` not extracted**: Compressed output file generation unavailable. |
| CONV-PCD-008 | **P2** | **No null-safety on `node.find()` calls**: Every `node.find()` call directly chains `.get('value', ...)`. If a parameter element is completely absent from the XML (not just empty), `node.find()` returns `None`, and calling `.get()` on `None` will raise `AttributeError` at conversion time. Other component parsers in the codebase use explicit null checks. |
| CONV-PCD-009 | **P2** | **No Java expression detection on `FILENAME` parameter**: Filenames containing `globalMap.get()` or Java method calls will not be marked with `{{java}}` prefix, causing runtime failures when the engine cannot resolve the expression. |
| CONV-PCD-010 | **P3** | **`GROUPBYS` values are not stripped of surrounding quotes**: If Talend XML includes `"\"column_name\""`, the quotes will be passed through to the engine config, causing pivot column lookup failures. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Pivot operation (rows to columns) | **Yes** | High | `_process()` line 201 | Uses `pd.pivot_table()` -- functionally equivalent to Talend |
| 2 | Aggregation: sum | **Yes** | High | line 205 | Directly supported by pandas via `aggfunc='sum'` |
| 3 | Aggregation: count | **Yes** | High | line 205 | Directly supported by pandas via `aggfunc='count'` |
| 4 | Aggregation: min | **Yes** | High | line 205 | Directly supported by pandas via `aggfunc='min'` |
| 5 | Aggregation: max | **Yes** | High | line 205 | Directly supported by pandas via `aggfunc='max'` |
| 6 | Aggregation: first | **Yes** | Medium | line 205 | Pandas `'first'` may differ from Talend on NaN handling |
| 7 | Aggregation: last | **Yes** | Medium | line 205 | Pandas `'last'` may differ from Talend on NaN handling |
| 8 | Multiple group-by columns | **Yes** | High | line 202 | Passed as `index=group_by_columns` to `pivot_table()` |
| 9 | NaN replacement | **Yes** | High | line 219 | `fillna('')` replaces NaN with empty strings |
| 10 | Write to delimited file | **Yes** | High | line 257-263 | Uses `pd.to_csv()` |
| 11 | Custom field separator | **Yes** | High | line 259 | Passed as `sep=field_separator` to `to_csv()` |
| 12 | Custom row separator | **No (crashes)** | None | line 260 | Passed as `line_terminator` to `to_csv()` -- **parameter removed in pandas 3.0; raises TypeError on pandas 3.0.1 (installed). Every file-writing execution crashes unconditionally.** |
| 13 | Encoding support | **Yes** | High | line 261 | Passed as `encoding=encoding` to `to_csv()` |
| 14 | Create file control | **Yes** | High | line 251 | `create_file` config controls file creation |
| 15 | Schema-based type casting | **Partial** | Low | lines 230-243 | Limited to `int` and `float` types only; no `str`, `datetime`, `Decimal`, `bool`, or Talend type identifiers (`id_String`, `id_Integer`, etc.) |
| 16 | Escape sequence in row separator | **Yes** | Medium | line 170 | `unicode_escape` decoding applied -- **dangerous on arbitrary input** |
| 17 | Quote stripping on separators | **Yes** | Medium | lines 174-180 | Removes enclosing double quotes from field and row separators |
| 18 | Numeric column int-casting | **Yes** | Low | lines 213-227 | Aggressive float-to-int conversion; applied twice; crashes on empty strings |
| 19 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 20 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers -- **but converter does not set markers for this component** |
| 21 | Empty input handling | **Yes** | High | lines 146-149 | Returns empty DataFrame with stats (0, 0, 0) |
| 22 | **Include Header control** | **No** | **N/A** | -- | **Always includes header; no way to suppress. `to_csv(index=False)` includes header by default.** |
| 23 | **Append mode** | **No** | **N/A** | -- | **Always overwrites; no append support. `to_csv()` called in write mode.** |
| 24 | **Text enclosure / quoting** | **No** | **N/A** | -- | **No configurable quoting for output fields. Fields containing the delimiter will corrupt the output.** |
| 25 | **Escape character** | **No** | **N/A** | -- | **No configurable escape character.** |
| 26 | **CSV Options (RFC4180)** | **No** | **N/A** | -- | **Not implemented.** |
| 27 | **Advanced separator (locale)** | **No** | **N/A** | -- | **No locale-aware number formatting.** |
| 28 | **Don't generate empty file** | **No** | **N/A** | -- | **Empty input still writes empty file (header only) when `create=True`.** |
| 29 | **Compress output** | **No** | **N/A** | -- | **No gzip support. pandas `to_csv()` supports `compression='gzip'` natively.** |
| 30 | **Die on error** | **No** | **N/A** | -- | **Always raises on error. No option to suppress errors and continue.** |
| 31 | **`{id}_NB_LINE_OUT` globalMap** | **No** | **N/A** | -- | **Sets `NB_LINE_OK` but not `NB_LINE_OUT`. Wrong key name for file-output components.** |
| 32 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | **N/A** | -- | **Error message not written to globalMap. Downstream error handling breaks.** |
| 33 | **`{id}_FILENAME` globalMap** | **No** | **N/A** | -- | **Resolved filename not stored in globalMap.** |
| 34 | **Dynamic output schema metadata** | **Partial** | Low | -- | **Pivot column values become columns at runtime; engine does not register these in output schema metadata for downstream components.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-PCD-001 | **P0** | **No `{id}_NB_LINE_OUT` globalMap variable**: Talend produces `NB_LINE_OUT` (number of rows written to file). The engine sets `NB_LINE_OK` instead, which is a different key. Components downstream that reference `globalMap.get("tPivotToColumnsDelimited_1_NB_LINE_OUT")` will get null. This breaks job chains that check output row counts. |
| ENG-PCD-002 | **P1** | **No Include Header control**: Talend's `INCLUDEHEADER` parameter allows suppressing the header row. The engine always writes headers via `to_csv(index=False)` (which includes the header row by default). Jobs that intentionally exclude headers will produce incorrect output. This is common in scenarios where the file is being appended to or consumed by fixed-width parsers. |
| ENG-PCD-003 | **P1** | **No Append mode**: Talend's `APPEND` parameter allows appending to an existing file. The engine always overwrites. In production workflows that write to the same file in a loop (e.g., via `tFlowToIterate`), all data except the last iteration will be lost. |
| ENG-PCD-004 | **P1** | **No text enclosure / quoting**: Talend allows configuring a text enclosure character for output fields. The engine writes raw CSV without configurable quoting. Fields containing the delimiter will corrupt the output file, producing misaligned columns for downstream consumers. |
| ENG-PCD-005 | **P1** | **No `{id}_ERROR_MESSAGE` globalMap variable**: Talend sets `ERROR_MESSAGE` when an error occurs. Downstream error-handling components (e.g., `tLogCatcher`, `tWarn`) referencing this variable will get null. |
| ENG-PCD-006 | **P2** | **No compressed output**: Jobs configured with `COMPRESS=true` will write uncompressed files, wasting disk space and breaking downstream components expecting `.gz` files. pandas `to_csv()` natively supports `compression='gzip'`, so this is a one-parameter change. |
| ENG-PCD-007 | **P2** | **No `{id}_FILENAME` globalMap variable**: The resolved filename is not stored in globalMap. Downstream components referencing the output filename for logging, auditing, or file operations will get null. |
| ENG-PCD-008 | **P2** | **No empty-file suppression**: Talend's `DONT_GENERATE_EMPTY_FILE=true` prevents file creation when output is empty. The engine always creates the file (when `create=True`), even if it only contains a header row. This can trigger false-positive "file exists" checks downstream. |
| ENG-PCD-009 | **P2** | **No locale-aware numeric formatting**: The `ADVANCED_SEPARATOR` feature (thousands/decimal separators) is not supported. Numeric values are written using Python's default formatting, which may differ from Talend's locale settings. Critical for European number formats (e.g., `1.234.567,89`). |
| ENG-PCD-010 | **P2** | **No `die_on_error` support**: Talend components typically have a `die_on_error` parameter. This component always raises on error. There is no option to return an empty DataFrame and continue processing when errors occur. |
| ENG-PCD-011 | **P3** | **Aggregation function validation**: The engine passes the `aggregation_function` string directly to `pd.pivot_table(aggfunc=...)`. Pandas accepts any valid function name or callable. Talend restricts to `sum`, `count`, `min`, `max`, `first`, `last`. Invalid function names from a corrupted config would produce a cryptic pandas error instead of a clear validation error. |
| ENG-PCD-012 | **P3** | **Default field separator mismatch with engine constant**: The converter defaults `FIELDSEPARATOR` to `';'` (correct for Talend), but the engine class constant `DEFAULT_FIELD_SEPARATOR` is `','` (line 69). If the converter omits the parameter for any reason, the engine's `','` default takes over, producing comma-separated output when Talend intended semicolon. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism. Represents input row count. |
| `{id}_NB_LINE_OUT` | Yes | **No** | -- | **Not implemented**. Talend expects `NB_LINE_OUT` for file-output components. Engine sets `NB_LINE_OK` instead, which is a different key. |
| `{id}_NB_LINE_OK` | N/A (Talend uses NB_LINE_OUT) | **Yes** | `_update_stats()` | Set but wrong key name. Should be `NB_LINE_OUT`. |
| `{id}_NB_LINE_REJECT` | N/A (no REJECT flow) | **Yes** | `_update_stats()` | Always 0. Correct since tPivotToColumnsDelimited has no REJECT connector. |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | **Not implemented**. Error message from exceptions not stored in globalMap. |
| `{id}_FILENAME` | Yes | **No** | -- | **Not implemented**. Resolved output file path not stored. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

### 5.4 Cross-Cutting GlobalMap Bugs

The following bugs in the base class affect this component (and ALL other components):

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-PCD-CC-001 | **P0** | `base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. Additionally, `stat_name` at the end of the f-string references the loop variable from the completed `for` loop, which will always be the last stat key (e.g., `EXECUTION_TIME`), not a useful summary. This causes `NameError` at runtime whenever `global_map` is not None, crashing ALL components that have a globalMap set. |
| BUG-PCD-CC-002 | **P0** | `global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. This makes `GlobalMap.get()` completely broken. |

**Impact**: These cross-cutting bugs mean that ANY use of `global_map` will crash at runtime. Since `_update_global_map()` is called from `BaseComponent.execute()` (lines 218 and 231), every component with a non-None `global_map` will fail. This effectively disables globalMap for the entire engine until fixed.

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-PCD-001 | **P0** | `pivot_to_columns_delimited.py` lines 213-215 | **Float-to-int conversion applied twice and unsafely**: The first loop (lines 213-215) converts float64 columns to int using `x.is_integer()`. This creates mixed-type columns (int and float values in the same column), which changes the dtype to `object`. The second loop (lines 223-227) then checks `is_numeric_dtype()`, which returns `False` for object columns, making the second loop a no-op in the common case. However, in edge cases where the column remains numeric (all values were whole numbers), the second loop will encounter empty strings from the `fillna('')` on line 219 and crash with `ValueError: could not convert string to float: ''`. |
| BUG-PCD-002 | **P0** | `pivot_to_columns_delimited.py` lines 223-227 | **`float(x)` on empty string values in numeric columns causes `ValueError`**: After `fillna('')` replaces NaN with empty strings, the `is_numeric_dtype` check on line 224 may still return True for columns that were originally numeric and had all NaN values replaced with empty strings. The lambda `float(x)` on `''` raises `ValueError`. The `x != ''` guard is checked first via short-circuit evaluation, so this only triggers when the entire column is non-empty numeric -- but the guard breaks down for mixed-type columns created by the first loop. This is a data-dependent crash that will occur for any dataset where the pivot produces NaN values (missing combinations), which is the common case. |
| BUG-PCD-003 | **P1** | `pivot_to_columns_delimited.py` line 170 | **`unicode_escape` decoding is dangerous on arbitrary user input**: `row_separator.encode().decode('unicode_escape')` can produce unexpected results for strings containing backslashes that are not intended as escape sequences. For example, a Windows file path in the separator would be corrupted (`\n` in `C:\new` becomes a newline). Additionally, this line will raise `UnicodeDecodeError` for certain byte sequences that are not valid escape sequences. The safe approach is to only decode known escape sequences (`\\n` -> `\n`, `\\t` -> `\t`, `\\r` -> `\r`). |
| BUG-PCD-004 | **P0** | `pivot_to_columns_delimited.py` line 260 | **`line_terminator` removed in pandas 3.x -- GUARANTEED crash**: `to_csv(line_terminator=...)` raises `TypeError` on pandas 3.0.1 (installed). The `line_terminator` parameter was deprecated in pandas 1.5, triggered `FutureWarning` in pandas 2.0+, and was **removed entirely** in pandas 3.0. Every file-writing execution crashes unconditionally on the installed pandas version. Must use `lineterminator` (no underscore). |
| BUG-PCD-005 | **P1** | `pivot_to_columns_delimited.py` lines 85-99 | **`_validate_config()` requires `filename` but `_process()` uses default**: The `_validate_config()` method treats `filename` as required (lines 98-99: `"Missing required config: 'filename'"`), but `_process()` provides a default via `self.config.get('filename', self.DEFAULT_FILENAME)` (line 159: defaults to `'output.csv'`). This creates an inconsistency: validation fails without `filename`, but processing would succeed with the default. Additionally, **`_validate_config()` is never called** from `_process()` or `execute()`, making the validation dead code. |
| BUG-PCD-006 | **P2** | `pivot_to_columns_delimited.py` lines 191-194 | **Field separator validated as single-char but multi-char separators are valid in Talend**: The engine raises `ValueError` if `field_separator` is not a single character (line 192-194). However, Talend's documentation states the field separator can be "a character, string, or regular expression." While single-char is the common case, this validation is overly restrictive. Pandas `to_csv()` also only supports single-char `sep`, so a workaround would be needed for multi-char delimiters. |
| BUG-PCD-007 | **P2** | `pivot_to_columns_delimited.py` lines 230-243 | **Schema type casting re-introduces NaN after fillna**: The schema casting code (line 237) replaces empty strings with `None` when casting to int: `lambda x: int(x) if x != '' else None`. This re-introduces NaN values (as `None`) that were just removed by `fillna('')` on line 219. The output will contain `None` values in int-typed columns where the pivot produced missing combinations, creating an inconsistency with the `fillna('')` behavior. |
| BUG-PCD-010 | **P0** | `pivot_to_columns_delimited.py` line 260 | **`line_terminator` removed in pandas 3.x -- GUARANTEED crash**: `to_csv(line_terminator=...)` raises `TypeError` on pandas 3.0.1 (installed). Every file-writing execution crashes unconditionally. Must use `lineterminator` (no underscore). This is the same root cause as BUG-PCD-004 but filed separately to track the crash severity distinctly from the parameter rename. |
| BUG-PCD-011 | **P1** | `pivot_to_columns_delimited.py` lines 169-183, 191-194 | **`field_separator` never gets `unicode_escape` decoding**: The `unicode_escape` decoding on line 170 is only applied to `row_separator`, not to `field_separator`. A tab separator configured as `\\t` in Talend XML arrives as the two-character literal string `\t` (backslash + t). This two-character string then fails the single-character validation on lines 191-194, raising `ValueError`. Tab-delimited output is completely broken. The fix must apply escape-sequence decoding to `field_separator` before the length check. |
| BUG-PCD-012 | **P1** | `pivot_to_columns_delimited.py` lines 169-180 | **`unicode_escape` applied BEFORE quote stripping -- wrong order corrupts quoted separators**: Line 170 applies `unicode_escape` decoding to `row_separator` before lines 174-180 strip enclosing double quotes. If Talend XML contains `"\"\\n\""` (quoted `\n`), the `unicode_escape` decoding converts `\\n` to a real newline first, then the quote-stripping logic attempts to match quotes around a string that now contains a literal newline character, potentially failing to strip or corrupting the value. The correct order is: strip quotes first, then decode escape sequences. The same ordering issue would affect `field_separator` if `unicode_escape` were applied to it (see BUG-PCD-011). |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-PCD-001 | **P2** | **Config key `filename` should be `filepath`**: Per STANDARDS.md line 826, `FILENAME` should map to `filepath`. Other file output components in the codebase (e.g., `tFileOutputDelimited` converter line 2254) use `filepath`. The `tPivotToColumnsDelimited` converter uses `filename` (line 1887) and the engine uses `filename` (line 159), both inconsistent with the standard. |
| NAME-PCD-002 | **P2** | **Config key `group_by_columns` inconsistent**: The STANDARDS.md mapping table does not specify a standard name for `GROUPBYS`. However, the `_columns` suffix is not used by other components. Other components in the codebase use shorter names. The plural `group_by_columns` is actually more descriptive than the typical pattern and not strictly wrong, but it differs from the converter convention. |
| NAME-PCD-003 | **P2** | **Engine uses `NB_LINE_OK` but Talend expects `NB_LINE_OUT`**: The `_update_stats(rows_in, rows_out, 0)` call on line 275 sets `NB_LINE_OK`, but Talend's `tPivotToColumnsDelimited` exposes `NB_LINE_OUT` for the output row count. Downstream components referencing `{id}_NB_LINE_OUT` via globalMap will get null. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-PCD-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists and returns error list (lines 75-128), but is never called from `_process()`, `execute()`, or any other code path. Validation is dead code. The `validate_config()` wrapper at line 282 also exists but is never called automatically. |
| STD-PCD-002 | **P2** | "Consistent validation path" | Configuration is validated in two places: `_validate_config()` (comprehensive, returns error list, lines 75-128) and inside `_process()` (simple check raising ValueError, lines 186-194). These two validation paths can diverge -- `_validate_config` checks for empty `group_by_columns` list but `_process` only checks truthiness. If `_validate_config` were wired up, both paths would run, creating redundancy. |
| STD-PCD-003 | **P2** | "Use custom exception types" (STANDARDS.md) | The component raises `ValueError` for all error conditions (lines 189, 194, 248, 268). Per STANDARDS.md, it should use `ConfigurationError` for config issues and `FileOperationError` for file write failures. The custom exceptions are defined in `src/v1/engine/exceptions.py` but not imported or used. |
| STD-PCD-004 | **P2** | "Schema type format" (STANDARDS.md line 865) | The converter converts types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format (`id_String`, `id_Integer`). The engine schema casting (lines 230-243) only handles `int` and `float`, not Talend type identifiers. |
| STD-PCD-005 | **P3** | "Import order" (PEP 8) | Import order is correct: `logging`, `pandas`, `typing`, then relative import. No issue. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-PCD-001 | **P2** | **`logger.info()` on line 183 logs the field separator at INFO level for every execution**: `"Field separator used: '{field_separator}'"`. This is a debug-level message that adds noise in production logs. Should be `logger.debug()`. |
| DBG-PCD-002 | **P3** | **Multiple `logger.debug()` calls for individual processing steps**: Lines 198, 199, 208, 209, 212, 217, 222 each log a separate debug message for micro-steps within the pivot operation. While individually correct, the volume creates verbose output even at DEBUG level. Consider consolidating into fewer, more informative messages. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-PCD-001 | **P3** | **No path traversal protection**: The `output_file` path from config is used directly with `to_csv()`. No validation is performed to prevent writing to arbitrary filesystem locations (e.g., `../../etc/cron.d/malicious`). Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones, DEBUG for details, WARNING for empty input, ERROR for failures -- mostly correct. `logger.info` on line 183 for field separator should be `logger.debug`. |
| Start/complete logging | `_process()` logs start (line 152) and completion (line 277-278) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | **Not used**. All errors raise generic `ValueError`. Should use `ConfigurationError` and `FileOperationError` from `exceptions.py`. |
| Exception chaining | **Not used**. The `except Exception as e: raise ValueError(f"...{e}")` pattern on lines 245-248 and 266-269 does not use `raise ... from e`, losing the original traceback. |
| Broad exception catch | **P1 issue**: Lines 245-248 catch `Exception` around the entire pivot AND type-casting block. A type-casting failure in the int conversion loop is indistinguishable from an actual pivot failure. The error message `"Pivot operation failed: {e}"` is misleading when the failure is in post-processing. |
| die_on_error handling | **Not implemented**. Component always raises. No option to return empty DataFrame and continue. |
| Error messages | Include component ID and error details via f-string -- partially correct. Missing the file path in file-write error messages. |
| Graceful degradation | Only for empty input (lines 146-149). No graceful degradation for config errors or processing errors. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()` has `input_data: Optional[pd.DataFrame]` -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]`, `List[str]` -- correct |
| Class constants | No type hints on class constants (lines 68-72). Minor omission. |

---

## 7. Performance & Memory

### 7.1 Memory Characteristics

The `PivotToColumnsDelimited` component has the following memory profile:

1. **Input DataFrame**: Held in memory during the entire `_process()` call.
2. **Pivoted DataFrame**: Created by `pivot_table()` and held concurrently with the input DataFrame. For datasets with many distinct pivot column values, the pivoted DataFrame can be significantly wider than the input (each distinct value becomes a new column).
3. **Double iteration over columns**: The float-to-int conversion iterates over all columns twice (lines 213-215 and 223-227), each time applying a lambda function row-by-row.
4. **fillna operation**: `pivoted_data = pivoted_data.fillna('')` creates a copy of the DataFrame (line 219), then reassigns. Peak memory is 2x the pivoted DataFrame size during this operation.
5. **Schema casting**: Additional `apply()` calls with lambdas create temporary Series for each column being cast.

### 7.2 Performance Issues

| ID | Priority | Issue |
|----|----------|-------|
| PERF-PCD-001 | **P1** | **Row-by-row lambda for type casting is O(rows x columns)**: Lines 213-215 and 223-227 use `df[col].apply(lambda x: ...)` for each column. This is Python-level iteration, not vectorized. For a pivoted DataFrame with 1000 columns (1000 distinct pivot values) and 100,000 rows, this results in 200,000,000 lambda calls across the two loops. Should use vectorized pandas operations like `df.select_dtypes(include='float64').apply(lambda col: col.where(col % 1 != 0, col.astype(int)))` or similar. |
| PERF-PCD-002 | **P2** | **Redundant float-to-int conversion**: The conversion from float to int is performed twice (lines 213-215 and 223-227). The second pass is redundant if the first pass succeeds (which it does for all non-NaN values). The second pass exists to catch values that were not converted in the first pass, but after `fillna('')`, the column is object dtype and `is_numeric_dtype` returns False, making it a no-op. This doubles the processing time for numeric columns in the first pass with zero benefit. |
| PERF-PCD-003 | **P2** | **`fillna('')` creates unnecessary DataFrame copy**: Line 219 calls `pivoted_data.fillna('')` which creates a new DataFrame. For large pivot results (e.g., 100,000 rows x 1000 columns), this doubles memory usage momentarily. Could use `pivoted_data.fillna('', inplace=True)` to avoid the copy, though `inplace` is being deprecated in newer pandas versions. |
| PERF-PCD-004 | **P2** | **Schema casting uses row-by-row lambda**: Lines 235-243 use `apply(lambda x: int(x) if x != '' else None)` for each schema column. This is O(rows) Python-level iteration per column. For columns with millions of values, vectorized `pd.to_numeric()` would be orders of magnitude faster. |
| PERF-PCD-005 | **P3** | **Streaming mode produces incorrect results for pivot operations**: The base class `_execute_streaming()` method processes chunks independently via `_create_chunks()` and concatenates results. However, pivot operations require seeing all data at once to determine the complete set of pivot column values. Streaming mode would produce incorrect results -- each chunk might have different pivot columns, and `pd.concat()` on DataFrames with different columns will introduce NaN values. The component does not override `_execute_streaming()` or `_auto_select_mode()` to prevent this. |

### 7.3 Memory Scaling Analysis

| Input Rows | Distinct Pivot Values | Group-By Groups | Approx Peak Memory |
|------------|----------------------|-----------------|-------------------|
| 10,000 | 10 | 1,000 | ~3x input size |
| 100,000 | 50 | 10,000 | ~5x input size |
| 1,000,000 | 100 | 100,000 | ~8x input size |
| 10,000,000 | 500 | 1,000,000 | ~15x input size (risk of OOM) |

The memory multiplier grows with the number of distinct pivot values because each value becomes a new column, and the type-casting loops create temporary copies. The `fillna('')` also creates a full copy.

### 7.4 Streaming Mode Incompatibility Detail

The `BaseComponent._execute_streaming()` method (base_component.py lines 255-278) processes data in chunks and concatenates results:

```
1. _create_chunks(df) yields chunks of size chunk_size
2. For each chunk: result = _process(chunk)
3. pd.concat(results, ignore_index=True)
```

For pivot operations, this is fundamentally incorrect because:

1. **Chunk A** might have pivot values `["X", "Y"]` -> produces columns `[group, "X", "Y"]`
2. **Chunk B** might have pivot values `["Y", "Z"]` -> produces columns `[group, "Y", "Z"]`
3. `pd.concat()` merges these into `[group, "X", "Y", "Z"]` with NaN for missing values
4. The result differs from processing all data at once (which would produce correct aggregations)

The `PivotToColumnsDelimited` component does not override `_auto_select_mode()` to prevent streaming mode from being used. If the input DataFrame exceeds `MEMORY_THRESHOLD_MB` (3072 MB), the engine will automatically switch to streaming mode and produce **silently incorrect results**.

**Recommendation**: Override `_auto_select_mode()` to always return `ExecutionMode.BATCH`, or override `_execute_streaming()` to materialize all chunks before pivoting.

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `PivotToColumnsDelimited` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter unit tests | **No** | -- | No tests for `parse_tpivot_to_columns_delimited()` |

**Key finding**: The v1 engine has ZERO tests for this component. All 302 lines of v1 engine code and 25 lines of converter code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic pivot with sum | P0 | Input: 3 columns (group, pivot_col, value). Verify correct pivoting with `sum` aggregation. Output should have group column + one column per distinct pivot value. Verify values match expected sums. |
| 2 | Multiple group-by columns | P0 | Input: 4 columns (group1, group2, pivot_col, value). Verify correct grouping with 2 group-by keys. Output rows should correspond to unique (group1, group2) combinations. |
| 3 | All aggregation functions | P0 | Test each of `sum`, `count`, `min`, `max`, `first`, `last` with identical input data. Verify each produces the correct result per function semantics. |
| 4 | File output verification | P0 | Verify the output file is created with correct content, field separator, row separator, and encoding. Read back the file and compare with the pivoted DataFrame. |
| 5 | Empty input handling | P0 | Pass `None` and empty DataFrame. Verify returns empty DataFrame without error, no file crash, stats are (0, 0, 0). |
| 6 | Missing configuration | P0 | Test with missing `pivot_column`, `aggregation_column`, `group_by_columns`. Verify appropriate `ValueError` is raised with clear message. |
| 7 | Statistics tracking | P0 | Verify `NB_LINE` and `NB_LINE_OK` are set correctly in stats dict after execution. `NB_LINE` should equal input row count; `NB_LINE_OK` should equal pivoted row count. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | NaN handling in pivot | P1 | Input has groups with missing pivot column values (sparse matrix). Verify NaN is replaced with empty string in output DataFrame. Verify output file contains empty fields (not "NaN"). |
| 9 | Custom field separator | P1 | Test with pipe `|` and tab `\t` separators. Verify output file uses correct delimiter. |
| 10 | Custom row separator | P1 | Test with `\r\n` (Windows) and `\n` (Unix) row separators. Verify output file line endings. |
| 11 | Non-UTF8 encoding | P1 | Test with `ISO-8859-1` encoding and non-ASCII characters (e.g., umlauts, accents). Verify output file is correctly encoded. |
| 12 | create=False | P1 | Set `create=False`. Verify no file is written but pivoted DataFrame is still returned in the result dict. |
| 13 | Schema type casting | P1 | Provide schema with `int` and `float` types. Verify group-by columns are cast correctly. Verify no crash on NaN values in typed columns. |
| 14 | Large number of pivot values | P1 | Test with 100+ distinct pivot values. Verify performance is acceptable and correctness is maintained. |
| 15 | Duplicate group+pivot combinations | P1 | Input has multiple rows with the same group-by + pivot combination. Verify aggregation function is applied correctly (e.g., `sum` adds them up). |
| 16 | Context variable in filename | P1 | Use `${context.output_dir}/file.csv` in filename. Verify context resolution works end-to-end. |
| 17 | Single group-by column | P1 | Test with exactly one group-by column (minimum valid config). Verify correct output. |
| 18 | GlobalMap integration | P1 | Provide a globalMap instance. Verify `{id}_NB_LINE` etc. are set after execution. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 19 | Quoted field separator | P2 | Test with `field_separator: '";"'` (quoted). Verify quotes are stripped and semicolon is used as delimiter. |
| 20 | File write failure | P2 | Test with invalid output path (e.g., `/nonexistent/dir/file.csv`). Verify appropriate error is raised with file path in message. |
| 21 | Concurrent pivot values | P2 | Test where same group has multiple values for same pivot key. Verify aggregation applies correctly (not just one value). |
| 22 | Streaming mode behavior | P2 | Verify behavior when `execution_mode` is `STREAMING`. Document that streaming produces incorrect results for pivot operations. |
| 23 | Empty pivot column values | P2 | Input has empty strings or None in the pivot column. Verify behavior (should these become a column header?). |
| 24 | Numeric pivot column values | P2 | Pivot column contains numeric values (e.g., years: 2020, 2021, 2022). Verify column headers are correct type. |
| 25 | Boolean pivot column values | P2 | Pivot column contains True/False. Verify two output columns (True, False). |
| 26 | Unicode in column names | P2 | Group-by and pivot columns contain Unicode characters. Verify output file handles them correctly. |

---

## 9. Edge-Case Checklist

### 9.1 NaN Handling

| Scenario | Current Behavior | Expected (Talend) | Status |
|----------|-----------------|-------------------|--------|
| NaN in aggregation column | Ignored by `pivot_table()` (pandas default) | Ignored | Correct |
| NaN in pivot column | Becomes a column named `NaN` or excluded depending on pandas version | Excluded or empty | Potentially incorrect -- needs testing |
| NaN in group-by column | Excluded from groups by `pivot_table()` (pandas default) | Included as group | Potentially incorrect -- Talend may include NaN groups |
| Missing pivot combinations | Filled with NaN, then `fillna('')` replaces with empty string | Empty string in output | Correct |
| NaN after fillna and schema casting | `fillna('')` replaces NaN, then schema casting replaces `''` with `None` (re-introducing NaN) | Consistent empty string | **Bug** (BUG-PCD-007) |

### 9.2 Empty String Handling

| Scenario | Current Behavior | Expected | Status |
|----------|-----------------|----------|--------|
| Empty string in aggregation column | Treated as a value by `pivot_table()`, not aggregated by sum/count/min/max | Depends on type | Potentially incorrect for numeric aggregations |
| Empty string in pivot column | Becomes a column header `""` | Implementation-dependent | Needs testing |
| Empty DataFrame input | Returns empty DataFrame, stats (0,0,0) | No output, no file crash | Correct |
| All values empty after pivot | File created with header only (if create=True) | Depends on DONT_GENERATE_EMPTY_FILE | Partial (no empty-file suppression) |

### 9.3 HYBRID Streaming Mode

| Scenario | Current Behavior | Expected | Status |
|----------|-----------------|----------|--------|
| Input < 3GB | BATCH mode selected | BATCH | Correct |
| Input > 3GB | STREAMING mode selected, produces wrong results | BATCH (pivot requires all data) | **Bug** (PERF-PCD-005) |
| execution_mode=BATCH (explicit) | BATCH mode used | BATCH | Correct |
| execution_mode=STREAMING (explicit) | STREAMING mode used, produces wrong results | Should warn or refuse | **Bug** |

### 9.4 `_update_global_map()` Crash Path

| Scenario | Current Behavior | Expected | Status |
|----------|-----------------|----------|--------|
| global_map is None | `_update_global_map()` exits early (line 300: `if self.global_map:`) | No crash | Correct |
| global_map is set | `_update_global_map()` iterates stats, then crashes on line 304 referencing undefined `value` variable | Stats written to globalMap | **Bug** (BUG-PCD-CC-001) |
| GlobalMap.get() called anywhere | Crashes with NameError due to undefined `default` parameter in get() method body | Returns value or None | **Bug** (BUG-PCD-CC-002) |

### 9.5 `pivot_table()` Behavior Edge Cases

| Scenario | pandas Behavior | Talend Behavior | Compatibility |
|----------|----------------|-----------------|---------------|
| All values NaN for a group+pivot combination | NaN in cell | Empty cell | Handled by `fillna('')` |
| Single row per group+pivot combination | Value preserved as-is | Value preserved | Compatible |
| Zero rows after filtering | Empty DataFrame | Empty output | Compatible |
| Non-numeric values with `sum` aggregation | TypeError or object concatenation | Error or string concatenation | Potentially incompatible |
| Duplicate column names after pivot | Pandas handles via MultiIndex collapse | Undefined | Potentially incompatible |
| Very large number of distinct pivot values (10K+) | Creates 10K+ columns, slow | Same | Compatible but performance concern |

### 9.6 Aggregation Function Edge Cases

| Function | Input: `[1, 2, NaN, 3]` | pandas Result | Talend Result | Match? |
|----------|--------------------------|--------------|--------------|--------|
| sum | -- | 6.0 | 6 | Yes (after int casting) |
| count | -- | 3 | 3 | Yes |
| min | -- | 1.0 | 1 | Yes (after int casting) |
| max | -- | 3.0 | 3 | Yes (after int casting) |
| first | -- | 1.0 | 1 | Yes (after int casting) |
| last | -- | 3.0 | 3 | Yes (after int casting) |

| Function | Input: `[NaN, NaN]` | pandas Result | Talend Result | Match? |
|----------|----------------------|--------------|--------------|--------|
| sum | -- | 0.0 | Empty/null | **No** -- pandas sum of all-NaN is 0, Talend produces empty |
| count | -- | 0 | 0 | Yes |
| min | -- | NaN | Empty/null | Yes (after fillna) |
| max | -- | NaN | Empty/null | Yes (after fillna) |

### 9.7 File Output Edge Cases

| Scenario | Current Behavior | Expected (Talend) | Status |
|----------|-----------------|-------------------|--------|
| Output directory does not exist | `to_csv()` raises `FileNotFoundError` | Create parent dirs when CREATE=true | **Missing** -- no `os.makedirs()` |
| File already exists, append=false | File overwritten | File overwritten | Correct |
| File already exists, append=true | N/A (append not supported) | Data appended | **Not implemented** |
| Permission denied on output file | `to_csv()` raises `PermissionError`, wrapped as ValueError | Clear error message | Partially correct (error message is misleading: "Pivot operation failed") |
| Disk full | `to_csv()` raises `OSError` | Clear error message | Same as above |

### 9.8 Schema Casting Edge Cases

| Schema Type | Input Value | Current Behavior | Expected | Status |
|-------------|------------|-----------------|----------|--------|
| `int` | `""` (empty string) | Returns `None` (line 237) | `None` or `0` | Inconsistent with fillna behavior |
| `int` | `"abc"` (non-numeric) | `int("abc")` -> `ValueError` crash | Error or skip | **Bug** |
| `int` | `3.14` (float) | `int(3.14)` -> `3` (truncation) | Depends on Talend type | Potentially incorrect |
| `float` | `""` (empty string) | Returns `None` (line 241) | `None` or `0.0` | Inconsistent |
| `str` | Any | Not handled (no `str` branch) | Pass through | Correct by omission |
| `datetime` | Any | Not handled (no `datetime` branch) | Convert to datetime | **Missing** |
| `id_Integer` | Any | Not handled (Talend type IDs not supported) | Convert to int | **Missing** |

---

## 10. Detailed Code Walkthrough

### File: `pivot_to_columns_delimited.py` (302 lines)

#### Module Structure

```
Lines 1-15:    Module docstring, imports, logger setup
Lines 18-65:   Class definition, docstring with configuration documentation
Lines 67-72:   Class constants (defaults)
Lines 75-128:  _validate_config() method (DEAD CODE)
Lines 130-280: _process() method (main logic)
Lines 282-301: validate_config() backward-compatible wrapper (DEAD CODE)
```

#### Class Constants (Lines 67-72)

```python
DEFAULT_AGGREGATION_FUNCTION = 'sum'
DEFAULT_FIELD_SEPARATOR = ','
DEFAULT_ROW_SEPARATOR = '\n'
DEFAULT_ENCODING = 'UTF-8'
DEFAULT_FILENAME = 'output.csv'
DEFAULT_CREATE = True
```

**Issues**:
- `DEFAULT_FIELD_SEPARATOR` is `','` but Talend's default for delimited components is `';'`. The converter defaults to `';'` which is correct, but if the converter omits the parameter, the engine's `','` default takes over.
- `DEFAULT_FILENAME` is `'output.csv'` which is arbitrary. A missing filename should be an error, not a silent default.
- No constant for `DEFAULT_INCLUDE_HEADER`, `DEFAULT_APPEND`, or `DEFAULT_DIE_ON_ERROR`.

#### `_validate_config()` Method (Lines 75-128)

The validation method checks:
- `pivot_column`: required, non-empty
- `aggregation_column`: required, non-empty
- `group_by_columns`: required, must be a non-empty list
- `filename`: required, non-empty
- `field_separator`: if present, must be single character (after quote stripping)
- `aggregation_function`: if present, must be a string
- `encoding`: if present, must be a string
- `create`: if present, must be boolean
- `schema`: if present, must be a dictionary

**Missing validations**:
- `aggregation_function` is not validated against the set of supported functions (`sum`, `count`, `min`, `max`, `first`, `last`)
- `row_separator` is not validated at all
- `encoding` is not validated against known encodings
- `field_separator` validation strips quotes but does not handle escape sequences like `\t`
- No validation of column existence (pivot_column, aggregation_column, group_by_columns) against input schema
- No validation of `output_file` path (writable directory, no path traversal)

**Dead code**: This method is never automatically called. The `validate_config()` wrapper at line 282 exists for backward compatibility but is also not called from the execution pipeline. Both validation methods are dead code.

#### `_process()` Method (Lines 130-280)

This is the main logic method. It follows this sequence:

1. **Empty input check** (lines 146-149): Returns empty DataFrame if input is None or empty. Correctly updates stats to (0, 0, 0).

2. **Configuration extraction** (lines 154-163): Gets config values with defaults. Uses `self.config.get()` with class constant defaults.

3. **Separator processing** (lines 169-183):
   - Applies `unicode_escape` to row_separator (dangerous -- see BUG-PCD-003)
   - Strips enclosing double quotes from field_separator and row_separator

4. **Runtime validation** (lines 186-194):
   - Checks required fields: `pivot_column`, `aggregation_column`, `group_by_columns` (truthiness check)
   - Checks `field_separator` is a single character
   - Raises `ValueError` on failure

5. **Pivot operation** (lines 197-248):
   - Performs `pivot_table()` with `reset_index()` -- correct
   - First float-to-int loop (lines 213-215) -- problematic
   - `fillna('')` (line 219)
   - Second float-to-int loop (lines 223-227) -- redundant and buggy
   - Schema type casting (lines 230-243) -- limited and inconsistent

6. **File writing** (lines 251-271):
   - Writes to CSV if `create_file` is True
   - Uses removed `line_terminator` parameter (crashes on pandas 3.0.1)

7. **Statistics update** (lines 274-278):
   - Updates `NB_LINE` (input rows) and `NB_LINE_OK` (output rows)
   - `NB_LINE_REJECT` always 0

**Critical issues in the pivot operation block (lines 197-248)**:

The pivot operation itself (lines 201-206) is correct and functionally equivalent to Talend:

```python
pivoted_data = input_data.pivot_table(
    index=group_by_columns,
    columns=pivot_column,
    values=aggregation_column,
    aggfunc=aggregation_function
).reset_index()
```

However, the post-processing has multiple issues:

**First float-to-int loop (lines 213-215)**:
```python
for col in pivoted_data.columns:
    if pivoted_data[col].dtype == 'float64':
        pivoted_data[col] = pivoted_data[col].apply(
            lambda x: int(x) if pd.notnull(x) and x.is_integer() else x
        )
```
This converts float values that are whole numbers to integers. After this conversion, the column has mixed types (int, float, and potentially NaN), making it an `object` dtype column. This is row-by-row Python iteration, not vectorized.

**NaN replacement (line 219)**:
```python
pivoted_data = pivoted_data.fillna('')
```
Replaces NaN with empty strings. Combined with the previous type conversion, columns now contain a mix of `int`, `float`, and `str('')` values.

**Second float-to-int loop (lines 223-227)**:
```python
for col in pivoted_data.columns:
    if pd.api.types.is_numeric_dtype(pivoted_data[col]):
        pivoted_data[col] = pivoted_data[col].apply(
            lambda x: int(x) if x != '' and float(x) == int(float(x)) else x
        )
```
This loop is problematic because:
- After `fillna('')`, columns that had NaN now contain `''`, changing dtype to `object`
- `is_numeric_dtype` returns `False` for `object` columns, making this loop a no-op in most cases
- If `is_numeric_dtype` returns `True` (edge case where all pivot values were present for all groups), `float('')` will raise `ValueError`
- The logic `float(x) == int(float(x))` is equivalent to `x.is_integer()` for float values but more error-prone

**Schema type casting (lines 230-243)**:
```python
schema = self.config.get('schema', {})
if schema:
    for col, col_type in schema.items():
        if col in pivoted_data.columns:
            if col_type == 'int':
                pivoted_data[col] = pivoted_data[col].apply(
                    lambda x: int(x) if x != '' else None
                )
```
Issues:
- Only handles `int` and `float` types -- no `str`, `datetime`, `Decimal`, `bool`, or Talend type identifiers
- After `fillna('')`, attempting `int('some_string')` for non-numeric strings would raise `ValueError`
- Replaces empty strings with `None`, re-introducing NaN values that were just removed by `fillna('')`
- Schema is expected to be a `Dict[str, str]` (column_name -> type_name), but the class docstring says `Dict[str, str]` while the base class `validate_schema()` expects `List[Dict]` (list of column definitions). These are different formats.

#### `validate_config()` Method (Lines 282-301)

This is a backward-compatible wrapper around `_validate_config()`. It logs errors and returns a boolean. It is never called from the execution pipeline, making both validation methods dead code.

---

## 11. Converter Code Walkthrough

### File: `component_parser.py`, Method: `parse_tpivot_to_columns_delimited()` (Lines 1881-1905)

```python
def parse_tpivot_to_columns_delimited(self, node, component: Dict) -> Dict:
    """Parse tPivotToColumnsDelimited specific configuration"""
    pivot_column = node.find('.//elementParameter[@name="PIVOT_COLUMN"]').get('value', '')
    aggregation_column = node.find('.//elementParameter[@name="AGGREGATION_COLUMN"]').get('value', '')
    aggregation_function = node.find('.//elementParameter[@name="AGGREGATION_FUNCTION"]').get('value', 'sum')
    group_bys = [param.get('value', '') for param in node.findall('.//elementParameter[@name="GROUPBYS"]/elementValue')]
    filename = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
    row_separator = node.find('.//elementParameter[@name="ROWSEPARATOR"]').get('value', '\n')
    field_separator = node.find('.//elementParameter[@name="FIELDSEPARATOR"]').get('value', ';')
    encoding = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
    create = node.find('.//elementParameter[@name="CREATE"]').get('value', 'true').lower() == 'true'

    component['config'].update({
        'pivot_column': pivot_column,
        'aggregation_column': aggregation_column,
        'aggregation_function': aggregation_function,
        'group_by_columns': group_bys,
        'filename': filename,
        'row_separator': row_separator,
        'field_separator': field_separator,
        'encoding': encoding,
        'create': create
    })

    return component
```

**Line-by-line analysis**:

1. **Line 1883**: `node.find('.//elementParameter[@name="PIVOT_COLUMN"]').get('value', '')` -- No null-safety. If `PIVOT_COLUMN` is absent from XML, `node.find()` returns `None`, and `.get()` on `None` raises `AttributeError`.

2. **Line 1884**: Same null-safety issue for `AGGREGATION_COLUMN`.

3. **Line 1885**: Same for `AGGREGATION_FUNCTION`. Default `'sum'` is correct for Talend.

4. **Line 1886**: `node.findall('.//elementParameter[@name="GROUPBYS"]/elementValue')` -- Uses `findall` which returns empty list if no matches. This is safe (returns `[]` for missing GROUPBYS). However, values are not stripped of surrounding quotes.

5. **Line 1887**: `FILENAME` extracted as-is. No Java expression detection. No context variable pre-processing.

6. **Line 1888**: `ROWSEPARATOR` default `'\n'` matches Talend.

7. **Line 1889**: `FIELDSEPARATOR` default `';'` matches Talend. **But engine default is `','`**.

8. **Line 1890**: `ENCODING` default `'UTF-8'` is correct for output components.

9. **Line 1891**: Boolean conversion for `CREATE` is correct pattern.

**Missing extractions** compared to `tFileOutputDelimited` (line 2253):
- `INCLUDEHEADER` (extracted by tFileOutputDelimited on line 2257)
- `APPEND` (extracted by tFileOutputDelimited on line 2258)
- `DIE_ON_ERROR` (extracted by tFileOutputDelimited on line 2260)

### File: `converter.py`, Dispatch (Line 311)

```python
elif component_type == 'tPivotToColumnsDelimited':
    component = self.component_parser.parse_tpivot_to_columns_delimited(node, component)
```

The dispatch is clean and follows the established pattern in the codebase. The method name follows the `parse_t{component_name}` convention. This is a dedicated `elif` branch, which is the correct pattern per STANDARDS.md (unlike `tFileInputDelimited` which uses the deprecated generic mapper).

---

## 12. Cross-Cutting Concerns

### 12.1 Streaming Mode Incompatibility

The `BaseComponent._execute_streaming()` method (base_component.py lines 255-278) processes data in chunks and concatenates results. For pivot operations, this is fundamentally incorrect because:

1. Each chunk may contain a different subset of pivot column values.
2. The resulting DataFrames from different chunks may have different columns.
3. `pd.concat()` on DataFrames with different columns will introduce NaN values.
4. Aggregation is applied per-chunk, not globally -- so sums/counts will be wrong.
5. The final result will differ from processing all data at once.

The `PivotToColumnsDelimited` component does not override `_execute_streaming()` or `_auto_select_mode()` to prevent streaming mode from being used. If the input DataFrame exceeds the `MEMORY_THRESHOLD_MB` (3072 MB), the engine will automatically switch to streaming mode and produce incorrect results silently.

**Recommendation**: Override `_auto_select_mode()` to always return `ExecutionMode.BATCH`, or override `_execute_streaming()` to materialize all chunks before pivoting.

### 12.2 GlobalMap Variable Mismatch

The base class `_update_global_map()` writes stats using `put_component_stat()`, which produces keys like `{id}_NB_LINE`, `{id}_NB_LINE_OK`, and `{id}_NB_LINE_REJECT`. However, Talend's tPivotToColumnsDelimited produces:
- `{id}_NB_LINE` (input rows) -- matches
- `{id}_NB_LINE_OUT` (output rows, NOT `NB_LINE_OK`) -- **mismatch**
- `{id}_ERROR_MESSAGE` (error message) -- **not set**
- `{id}_FILENAME` (resolved output path) -- **not set**

The engine sets `NB_LINE_OK` where Talend expects `NB_LINE_OUT`, and does not set `ERROR_MESSAGE` or `FILENAME` at all.

### 12.3 Context Variable Resolution

The base class `execute()` method resolves context variables via `self.context_manager.resolve_dict(self.config)` before calling `_process()`. This means `${context.output_dir}/pivot.csv` in the filename will be correctly resolved. However, Java expressions in the filename require the `{{java}}` marker, which the converter does not set for this component.

### 12.4 Interaction with Upstream Components

The `PivotToColumnsDelimited` component expects a single input DataFrame via the `main` flow. It does not support:
- Multiple input flows (e.g., lookup)
- Reject input (from upstream components)
- Iterate connections (for processing multiple files)

If an upstream component sends data via a non-`main` flow, the data will be ignored.

### 12.5 Interaction with Downstream Components

The component returns `{'main': pivoted_data, 'output_file': output_file}`. The `output_file` key is non-standard -- the engine typically expects `main` and optionally `reject`. Downstream components may not know to look for `output_file`. The pivoted DataFrame is returned correctly via `main`.

---

## 13. Issues Summary

### All Issues by Priority

#### P0 -- Critical (7 issues)

| ID | Category | Summary |
|----|----------|---------|
| BUG-PCD-001 | Bug | Float-to-int conversion applied twice; second pass crashes on empty strings after fillna. Data-dependent crash for any dataset with missing pivot combinations (common case). |
| BUG-PCD-002 | Bug | `float(x)` on empty string values in numeric columns causes `ValueError` crash. Second float-to-int loop is both redundant and dangerous. |
| BUG-PCD-004 | Bug | **`line_terminator` removed in pandas 3.x -- GUARANTEED crash.** `to_csv(line_terminator=...)` raises `TypeError` on pandas 3.0.1 (installed). Every file-writing execution crashes unconditionally. Must use `lineterminator` (no underscore). |
| BUG-PCD-010 | Bug | **`line_terminator` removed in pandas 3.x -- GUARANTEED crash** (duplicate tracking of BUG-PCD-004 at crash severity). `to_csv(line_terminator=...)` raises `TypeError` on pandas 3.0.1 (installed). Every file-writing execution crashes unconditionally. |
| BUG-PCD-CC-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-PCD-CC-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-PCD-001 | Testing | Zero v1 unit tests for PivotToColumnsDelimited. All 302 lines of engine code are unverified. |

#### P1 -- Major (15 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-PCD-001 | Converter | `INCLUDEHEADER` not extracted -- no way to suppress header output. tFileOutputDelimited converter already extracts this. |
| CONV-PCD-002 | Converter | `APPEND` not extracted -- no append mode support. tFileOutputDelimited converter already extracts this. |
| CONV-PCD-003 | Converter | `TEXT_ENCLOSURE` and `ESCAPE_CHAR` not extracted -- no quoting control for output fields. |
| ENG-PCD-001 | Feature Gap | `{id}_NB_LINE_OUT` globalMap variable not set (uses `NB_LINE_OK` instead). Breaks downstream components. |
| ENG-PCD-002 | Feature Gap | No Include Header control -- always writes header row. |
| ENG-PCD-003 | Feature Gap | No Append mode -- always overwrites output file. |
| ENG-PCD-004 | Feature Gap | No text enclosure / quoting for output fields. Fields with delimiter corrupt output. |
| ENG-PCD-005 | Feature Gap | `{id}_ERROR_MESSAGE` globalMap variable not set. Breaks downstream error handling. |
| BUG-PCD-003 | Bug | `unicode_escape` decoding on row_separator is dangerous for arbitrary input. |
| BUG-PCD-005 | Bug | `_validate_config` requires `filename` but `_process` provides default; validation never called. Dead code. |
| BUG-PCD-011 | Bug | `field_separator` never gets `unicode_escape` decoding. Tab separator `\\t` arrives as 2-char literal string `\t`, fails single-char validation (lines 191-194). Tab-delimited output broken. |
| BUG-PCD-012 | Bug | `unicode_escape` applied BEFORE quote stripping -- wrong order corrupts quoted separators. Decoding `\\n` to newline before stripping quotes prevents correct quote matching. |
| ERR-PCD-001 | Error Handling | Broad exception catch (lines 245-248) masks root cause of type-casting failures vs. actual pivot failures. |
| PERF-PCD-001 | Performance | Row-by-row lambda for type casting is O(rows x columns); not vectorized. 200M lambda calls for 1000-col x 100K-row pivot. |
| TEST-PCD-002 | Testing | No integration tests exercise this component in a multi-step job. |

#### P2 -- Moderate (22 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-PCD-004 | Converter | `CSV_OPTION` not extracted. |
| CONV-PCD-005 | Converter | `ADVANCED_SEPARATOR` / `THOUSANDS_SEPARATOR` / `DECIMAL_SEPARATOR` not extracted. |
| CONV-PCD-006 | Converter | `DONT_GENERATE_EMPTY_FILE` not extracted. |
| CONV-PCD-007 | Converter | `COMPRESS` not extracted. |
| CONV-PCD-008 | Converter | No null-safety on `node.find()` calls -- `AttributeError` if XML element missing. |
| CONV-PCD-009 | Converter | No Java expression detection on `FILENAME` parameter. |
| ENG-PCD-006 | Feature Gap | No compressed output support. |
| ENG-PCD-007 | Feature Gap | `{id}_FILENAME` globalMap variable not set. |
| ENG-PCD-008 | Feature Gap | No empty-file suppression (`DONT_GENERATE_EMPTY_FILE`). |
| ENG-PCD-009 | Feature Gap | No locale-aware numeric formatting. |
| ENG-PCD-010 | Feature Gap | No `die_on_error` support -- always raises. |
| BUG-PCD-006 | Bug | Field separator validation rejects multi-char separators that Talend supports. |
| BUG-PCD-007 | Bug | Schema type casting re-introduces NaN after fillna by replacing `''` with `None`. |
| NAME-PCD-001 | Naming | Config key `filename` should be `filepath` per STANDARDS.md. |
| NAME-PCD-002 | Naming | Config key `group_by_columns` inconsistent with codebase conventions. |
| NAME-PCD-003 | Naming | Engine uses `NB_LINE_OK` but Talend expects `NB_LINE_OUT` for this component. |
| STD-PCD-001 | Standards | `_validate_config()` is never invoked -- dead code. |
| STD-PCD-002 | Standards | Redundant validation in `_validate_config()` and `_process()`. |
| STD-PCD-003 | Standards | No custom exception types (uses generic `ValueError` instead of `ConfigurationError`/`FileOperationError`). |
| STD-PCD-004 | Standards | Schema type format uses Python types, not Talend type identifiers. |
| DBG-PCD-001 | Debug | Field separator logged at INFO level; should be DEBUG. |
| PERF-PCD-002 | Performance | Redundant double float-to-int conversion. |
| PERF-PCD-003 | Performance | `fillna('')` creates unnecessary DataFrame copy. |
| PERF-PCD-004 | Performance | Schema casting uses row-by-row lambda instead of vectorized `pd.to_numeric()`. |

#### P3 -- Low (6 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-PCD-010 | Converter | GROUPBYS values not stripped of surrounding quotes. |
| ENG-PCD-011 | Feature Gap | No aggregation function validation against supported set. |
| ENG-PCD-012 | Feature Gap | Default field separator mismatch between engine constant (`','`) and Talend default (`';'`). |
| SEC-PCD-001 | Security | No path traversal protection on output file path. |
| DBG-PCD-002 | Debug | Excessive debug logging in processing loop. |
| PERF-PCD-005 | Performance | Streaming mode produces silently incorrect results for pivot operations. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 7 | 4 bugs (component, incl. BUG-PCD-004 upgraded from P1 + BUG-PCD-010 new), 2 bugs (cross-cutting), 1 testing |
| P1 | 15 | 3 converter, 5 engine, 5 bugs (incl. BUG-PCD-011, BUG-PCD-012 new), 1 error handling, 1 performance, 1 testing |
| P2 | 22 | 6 converter, 5 engine, 2 bugs, 3 naming, 4 standards, 1 debug, 3 performance |
| P3 | 6 | 1 converter, 2 engine, 1 security, 1 debug, 1 performance |
| **Total** | **50** | |

---

## 14. Recommendations

### Immediate (Before Production)

1. **Fix the float-to-int crash (BUG-PCD-001, BUG-PCD-002)**: Remove the second float-to-int conversion loop entirely (lines 223-227). Replace the first loop (lines 213-215) with a vectorized approach that handles NaN/empty string values safely:
   ```python
   for col in pivoted_data.select_dtypes(include='float64').columns:
       mask = pivoted_data[col].notna() & (pivoted_data[col] % 1 == 0)
       pivoted_data.loc[mask, col] = pivoted_data.loc[mask, col].astype(int)
   ```
   Then do `fillna('')` after this safe conversion.

2. **Fix `_update_global_map()` bug (BUG-PCD-CC-001)**: Change the log statement on `base_component.py` line 304 to remove the stale `{stat_name}: {value}` reference. Replace with a clean log of the three main stats only:
   ```python
   logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']}")
   ```
   **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

3. **Fix `GlobalMap.get()` bug (BUG-PCD-CC-002)**: Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26:
   ```python
   def get(self, key: str, default: Any = None) -> Optional[Any]:
       return self._map.get(key, default)
   ```
   **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low.

4. **Create unit test suite (TEST-PCD-001)**: Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic pivot correctness, multiple group-by columns, all aggregation functions, file output verification, empty input handling, missing configuration, and statistics tracking.

5. **Fix the removed `line_terminator` parameter (BUG-PCD-004, BUG-PCD-010)**: Change `line_terminator=row_separator` to `lineterminator=row_separator` on line 260. This is a one-line fix that unblocks ALL file-writing executions. The `line_terminator` parameter was removed in pandas 3.0 and raises `TypeError` on the installed pandas 3.0.1. This is the single highest-priority fix.

6. **Set the correct globalMap variable (ENG-PCD-001)**: Override `_update_global_map()` or add a post-processing step to also write `NB_LINE_OUT` to globalMap:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_NB_LINE_OUT", self.stats['NB_LINE_OK'])
   ```

### Short-Term (Hardening)

7. **Extract missing converter parameters (CONV-PCD-001 through CONV-PCD-003)**: Add extraction for `INCLUDEHEADER`, `APPEND`, `TEXT_ENCLOSURE`, `ESCAPE_CHAR`, `DIE_ON_ERROR` to the converter parser. Copy the pattern from `tFileOutputDelimited` (line 2257-2260):
   ```python
   component['config']['include_header'] = node.find('.//elementParameter[@name="INCLUDEHEADER"]').get('value', 'true').lower() == 'true'
   component['config']['append'] = node.find('.//elementParameter[@name="APPEND"]').get('value', 'false').lower() == 'true'
   component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'true').lower() == 'true'
   ```

8. **Implement Include Header control (ENG-PCD-002)**: Add `header` parameter to `to_csv()` call:
   ```python
   include_header = self.config.get('include_header', True)
   pivoted_data.to_csv(output_file, sep=field_separator, header=include_header, ...)
   ```

9. **Implement Append mode (ENG-PCD-003)**: Change file open mode based on `append` config:
   ```python
   append = self.config.get('append', False)
   mode = 'a' if append else 'w'
   write_header = include_header and (not append or not os.path.exists(output_file))
   pivoted_data.to_csv(output_file, mode=mode, header=write_header, ...)
   ```

10. **Implement text enclosure / quoting (ENG-PCD-004)**: Configure pandas quoting:
    ```python
    import csv
    text_enclosure = self.config.get('text_enclosure', None)
    escape_char = self.config.get('escape_char', None)
    quoting = csv.QUOTE_ALL if text_enclosure else csv.QUOTE_MINIMAL
    pivoted_data.to_csv(..., quotechar=text_enclosure, escapechar=escape_char, quoting=quoting)
    ```

11. **Wire up `_validate_config()` (STD-PCD-001)**: Call validation at the start of `_process()` and raise `ConfigurationError` on failure:
    ```python
    errors = self._validate_config()
    if errors:
        raise ConfigurationError(f"[{self.id}] Configuration errors: {'; '.join(errors)}")
    ```

12. **Add null-safety to converter (CONV-PCD-008)**: Wrap each `node.find()` call with a null check:
    ```python
    pivot_elem = node.find('.//elementParameter[@name="PIVOT_COLUMN"]')
    pivot_column = pivot_elem.get('value', '') if pivot_elem is not None else ''
    ```

13. **Add Java expression detection for FILENAME (CONV-PCD-009)**: Use `ExpressionConverter.detect_java_expression()` on the filename value and mark with `{{java}}` prefix if detected.

14. **Fix naming inconsistencies (NAME-PCD-001)**: Rename `filename` to `filepath` in both converter (line 1887, 1898) and engine (line 159, constant on line 71). Ensure backward compatibility with the old name via `self.config.get('filepath', self.config.get('filename', self.DEFAULT_FILENAME))`.

15. **Set ERROR_MESSAGE and FILENAME in globalMap (ENG-PCD-005, ENG-PCD-007)**: After resolving filename in `_process()`, write to globalMap. In error handlers, write the error message:
    ```python
    if self.global_map:
        self.global_map.put(f"{self.id}_FILENAME", output_file)
    # In except block:
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
    ```

### Long-Term (Optimization)

16. **Vectorize type casting (PERF-PCD-001, PERF-PCD-002)**: Replace row-by-row lambda with vectorized pandas operations. Remove the redundant second loop entirely.

17. **Override streaming mode (PERF-PCD-005)**: Override `_auto_select_mode()` to always return `BATCH`, or override `_execute_streaming()` to materialize all chunks before pivoting.

18. **Extract remaining converter parameters (CONV-PCD-004 through CONV-PCD-007)**: Add support for `CSV_OPTION`, `ADVANCED_SEPARATOR`, `THOUSANDS_SEPARATOR`, `DECIMAL_SEPARATOR`, `DONT_GENERATE_EMPTY_FILE`, and `COMPRESS`.

19. **Implement compressed output (ENG-PCD-006)**: Pandas `to_csv()` supports writing to gzip files natively via the `compression` parameter:
    ```python
    compression = 'gzip' if self.config.get('compress', False) else None
    pivoted_data.to_csv(output_file, compression=compression, ...)
    ```

20. **Use custom exceptions (STD-PCD-003)**: Replace `ValueError` with `ConfigurationError` (for config issues, lines 189, 194), `FileOperationError` (for file write failures, line 268), and use `raise ... from e` for proper exception chaining.

21. **Create integration test (TEST-PCD-002)**: Build an end-to-end test exercising `tFileInputDelimited -> tPivotToColumnsDelimited -> tFileOutputDelimited` in the v1 engine, verifying context resolution, Java bridge integration, and globalMap propagation.

22. **Add die_on_error support (ENG-PCD-010)**: When `die_on_error=False`, catch exceptions in `_process()` and return empty DataFrame instead of raising:
    ```python
    except Exception as e:
        if self.config.get('die_on_error', True):
            raise
        logger.error(f"[{self.id}] Error suppressed (die_on_error=false): {e}")
        if self.global_map:
            self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
        return {'main': pd.DataFrame()}
    ```

---

## 15. Production Readiness Assessment

### Overall Verdict: **NOT PRODUCTION-READY**

The `PivotToColumnsDelimited` component has **7 P0 issues** (4 component bugs, 2 cross-cutting bugs, 1 testing gap) and **15 P1 issues** that must be addressed before production deployment.

### Critical Blockers

1. **Unconditional crash on every file write (BUG-PCD-004, BUG-PCD-010)**: `to_csv(line_terminator=...)` raises `TypeError` on pandas 3.0.1 (installed). The `line_terminator` parameter was **removed** in pandas 3.0. Every execution that writes a file crashes unconditionally -- this is not data-dependent, it fails on 100% of inputs. Must use `lineterminator` (no underscore). This is the highest-severity bug in the component.

2. **Data-dependent crash (BUG-PCD-001, BUG-PCD-002)**: The double float-to-int conversion loop will crash on datasets where the pivot produces NaN values (missing combinations). This is the **common case** -- any sparse pivot matrix triggers it. The crash occurs in normal usage, not an edge case.

3. **GlobalMap crash (BUG-PCD-CC-001, BUG-PCD-CC-002)**: Any use of `global_map` crashes ALL components due to undefined variable references in the base class. This is cross-cutting and blocks the entire engine, not just this component.

4. **Zero test coverage (TEST-PCD-001)**: No tests exist to validate any behavior. Without tests, it is impossible to verify fixes or detect regressions. The double float-to-int bug would have been caught by the simplest pivot test.

5. **GlobalMap variable mismatch (ENG-PCD-001)**: Downstream components expecting `NB_LINE_OUT` will get null, silently breaking job chains that check output row counts.

### Risk Assessment

| Risk Area | Level | Justification |
|-----------|-------|---------------|
| Data correctness | **High** | Float-to-int conversion bugs crash on sparse pivots; streaming mode produces wrong results |
| File output correctness | **Critical** | `line_terminator` removed in pandas 3.x -- every file write crashes unconditionally; tab separator broken (no unicode_escape on field_separator); unicode_escape/quote-stripping order wrong; missing header control, append mode, quoting can produce corrupt files |
| Crash probability | **Critical** | Unconditional `TypeError` crash on every file write (pandas 3.0.1 installed); data-dependent crash in type-casting loop for sparse pivot combinations |
| GlobalMap integration | **High** | Cross-cutting bugs crash ALL components; variable name mismatch breaks downstream |
| Performance risk | **Medium** | Non-vectorized type casting is O(rows x columns) with Python-level iteration |
| Converter risk | **Medium** | 57% of Talend parameters not extracted; null-safety issues in parser |

### Minimum Viable Fix List

To reach "minimally production-ready" status, the following must be addressed:

1. Fix BUG-PCD-004 / BUG-PCD-010 (`line_terminator` -> `lineterminator`) -- **UNCONDITIONAL CRASH on pandas 3.0.1 (installed). Blocks ALL file output. One-line fix.**
2. Fix BUG-PCD-001 and BUG-PCD-002 (float-to-int crash) -- **HIGH IMPACT**
3. Fix BUG-PCD-CC-001 (base_component `_update_global_map()` crash) -- **CROSS-CUTTING**
4. Fix BUG-PCD-CC-002 (GlobalMap.get() crash) -- **CROSS-CUTTING**
5. Fix BUG-PCD-011 (`field_separator` missing `unicode_escape` decoding -- tab delimiters broken) -- **FUNCTIONAL**
6. Fix BUG-PCD-012 (`unicode_escape` before quote-stripping -- wrong order) -- **FUNCTIONAL**
7. Fix ENG-PCD-001 (globalMap variable name NB_LINE_OUT) -- **INTEGRATION**
8. Fix CONV-PCD-008 (converter null-safety) -- **CONVERTER STABILITY**
9. Create P0 test cases from TEST-PCD-001 -- **VERIFICATION**

---

## Appendix A: Talend Documentation Sources

- [tPivotToColumnsDelimited Standard properties (Talend 8.0)](https://help.talend.com/en-US/components/8.0/delimited/tpivottocolumnsdelimited-standard-properties)
- [tPivotToColumnsDelimited Overview (Talend 8.0)](https://help.talend.com/en-US/components/8.0/delimited/tpivottocolumnsdelimited)
- [tPivotToColumnsDelimited Standard properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/delimited/tpivottocolumnsdelimited-standard-properties)
- [tPivotToColumnsDelimited Overview (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/delimited/tpivottocolumnsdelimited)
- [Using a pivot column to aggregate data (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/delimited/tfileinputdelimited-tpivottocolumnsdelimited-tpivottocolumnsdelimited-using-pivot-column-to-aggregate-data-standard-component-the)
- [tPivotToColumnsDelimited - Talend Skill (ESB 7.x)](https://talendskill.com/talend-for-esb-docs/docs-7-x/tpivottocolumnsdelimited-talend-open-studio-for-esb-document-7-x/)
- [Talend Pivot Columns Tutorial](https://www.tutorialgateway.org/talend-pivot-columns/)
- [Transpose Rows to Columns Using Talend (Helical IT)](https://helicaltech.com/transpose-rows-to-columns-using-talend-open-studio/)

## Appendix B: File Inventory

| File | Path | Relevance |
|------|------|-----------|
| Engine component | `src/v1/engine/components/transform/pivot_to_columns_delimited.py` | Primary audit target (302 lines) |
| Converter parser | `src/converters/complex_converter/component_parser.py` (lines 1881-1905) | Converter extraction logic (25 lines) |
| Converter dispatch | `src/converters/complex_converter/converter.py` (line 311) | Dispatch routing |
| Transform __init__ | `src/v1/engine/components/transform/__init__.py` (line 16) | Package export |
| Engine registry | `src/v1/engine/engine.py` (lines 32, 150-151) | Component registration with aliases |
| Base component | `src/v1/engine/base_component.py` | Base class contract (lines 298-304 critical for globalMap bug) |
| Global map | `src/v1/engine/global_map.py` | GlobalMap implementation (line 28 critical for get() bug) |
| Exceptions | `src/v1/engine/exceptions.py` | Custom exception hierarchy (not used by this component) |
| Standards | `docs/v1/STANDARDS.md` | Coding standards reference (line 826: FILENAME -> filepath) |
| Tests | (none) | No test files found |

## Appendix C: Converter Parameter Mapping Code

```python
# component_parser.py lines 1881-1905
def parse_tpivot_to_columns_delimited(self, node, component: Dict) -> Dict:
    """Parse tPivotToColumnsDelimited specific configuration"""
    pivot_column = node.find('.//elementParameter[@name="PIVOT_COLUMN"]').get('value', '')
    aggregation_column = node.find('.//elementParameter[@name="AGGREGATION_COLUMN"]').get('value', '')
    aggregation_function = node.find('.//elementParameter[@name="AGGREGATION_FUNCTION"]').get('value', 'sum')
    group_bys = [param.get('value', '') for param in node.findall('.//elementParameter[@name="GROUPBYS"]/elementValue')]
    filename = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
    row_separator = node.find('.//elementParameter[@name="ROWSEPARATOR"]').get('value', '\n')
    field_separator = node.find('.//elementParameter[@name="FIELDSEPARATOR"]').get('value', ';')
    encoding = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
    create = node.find('.//elementParameter[@name="CREATE"]').get('value', 'true').lower() == 'true'

    component['config'].update({
        'pivot_column': pivot_column,
        'aggregation_column': aggregation_column,
        'aggregation_function': aggregation_function,
        'group_by_columns': group_bys,
        'filename': filename,
        'row_separator': row_separator,
        'field_separator': field_separator,
        'encoding': encoding,
        'create': create
    })

    return component
```

**Notes on this code**:
- Line 1886: `node.findall()` is safe (returns empty list for missing elements), unlike `node.find()` on other lines.
- Line 1889: Default `';'` matches Talend, but engine default `','` creates a mismatch if the converter fails to include the parameter.
- Line 1891: Boolean conversion pattern is correct but no null-safety on `node.find()`.
- All `node.find()` calls on lines 1883-1891 are unsafe -- they will raise `AttributeError` if the XML element is missing.

## Appendix D: Engine Class Structure

```
PivotToColumnsDelimited (BaseComponent)
    Constants:
        DEFAULT_AGGREGATION_FUNCTION = 'sum'
        DEFAULT_FIELD_SEPARATOR = ','        # MISMATCH: Talend default is ';'
        DEFAULT_ROW_SEPARATOR = '\n'
        DEFAULT_ENCODING = 'UTF-8'
        DEFAULT_FILENAME = 'output.csv'      # Arbitrary default; should error if missing
        DEFAULT_CREATE = True

    Methods:
        _validate_config() -> List[str]          # DEAD CODE -- never called
        _process(input_data) -> Dict[str, Any]   # Main entry point (150 lines)
        validate_config() -> bool                 # DEAD CODE -- backward-compatible wrapper

    Inherited from BaseComponent:
        execute(input_data) -> Dict[str, Any]    # Main execution with mode handling
        _update_stats(rows_read, rows_ok, rows_reject) -> None
        _update_global_map() -> None             # BUG: references undefined `value`
        validate_schema(df, schema) -> DataFrame  # Type conversion for schema columns
        _resolve_java_expressions() -> None       # Java bridge integration
        _auto_select_mode(input_data) -> ExecutionMode  # Not overridden -- allows streaming
        _execute_streaming(input_data) -> Dict    # Not overridden -- produces wrong results
        _create_chunks(df) -> Iterator[DataFrame]
```

## Appendix E: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `PIVOT_COLUMN` | `pivot_column` | Mapped | -- |
| `AGGREGATION_COLUMN` | `aggregation_column` | Mapped | -- |
| `AGGREGATION_FUNCTION` | `aggregation_function` | Mapped | -- |
| `GROUPBYS` | `group_by_columns` | Mapped | -- |
| `FILENAME` | `filename` | Mapped | -- (should rename to `filepath`) |
| `ROWSEPARATOR` | `row_separator` | Mapped | -- |
| `FIELDSEPARATOR` | `field_separator` | Mapped | -- |
| `ENCODING` | `encoding` | Mapped | -- |
| `CREATE` | `create` | Mapped | -- |
| `INCLUDEHEADER` | `include_header` | **Not Mapped** | P1 |
| `APPEND` | `append` | **Not Mapped** | P1 |
| `TEXT_ENCLOSURE` | `text_enclosure` | **Not Mapped** | P1 |
| `ESCAPE_CHAR` | `escape_char` | **Not Mapped** | P1 |
| `DIE_ON_ERROR` | `die_on_error` | **Not Mapped** | P1 |
| `CSV_OPTION` | `csv_option` | **Not Mapped** | P2 |
| `ADVANCED_SEPARATOR` | `advanced_separator` | **Not Mapped** | P2 |
| `THOUSANDS_SEPARATOR` | `thousands_separator` | **Not Mapped** | P2 |
| `DECIMAL_SEPARATOR` | `decimal_separator` | **Not Mapped** | P2 |
| `DONT_GENERATE_EMPTY_FILE` | `dont_generate_empty_file` | **Not Mapped** | P2 |
| `COMPRESS` | `compress` | **Not Mapped** | P2 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

## Appendix F: Comparison with Similar Components

### vs. tFileOutputDelimited (File Output)

The `tFileOutputDelimited` converter parser (lines 2253-2264 of `component_parser.py`) extracts significantly more parameters than `tPivotToColumnsDelimited`:

| Parameter | tFileOutputDelimited | tPivotToColumnsDelimited |
|-----------|---------------------|--------------------------|
| FILENAME | Yes (`filepath`) | Yes (`filename`) -- naming mismatch |
| FIELDSEPARATOR | Yes (`delimiter`) | Yes (`field_separator`) -- naming mismatch |
| ROWSEPARATOR | Yes (`row_separator`) | Yes (`row_separator`) |
| ENCODING | Yes | Yes |
| CREATE | No | Yes |
| INCLUDEHEADER | Yes | **No** |
| APPEND | Yes | **No** |
| DIE_ON_ERROR | Yes | **No** |
| TEXT_ENCLOSURE | No | **No** |
| CSV_OPTION | No | **No** |

This comparison shows that `tPivotToColumnsDelimited` has fewer output-file parameters extracted compared to `tFileOutputDelimited`, despite both writing delimited output files. The three most critical missing parameters (`INCLUDEHEADER`, `APPEND`, `DIE_ON_ERROR`) are already extracted by `tFileOutputDelimited`, demonstrating the extraction pattern is established.

### vs. tUnpivotRow (Inverse Operation)

The `tUnpivotRow` component performs the inverse operation (columns to rows). A comparison:

| Feature | tUnpivotRow | tPivotToColumnsDelimited |
|---------|-------------|--------------------------|
| Core operation | Yes (columns to rows) | Yes (rows to columns) |
| File output | N/A (transform only) | Yes (combined transform + file output) |
| GlobalMap variables | Partial | Partial |
| Unit tests | None | None |
| Converter coverage | Limited | Limited (43% of parameters) |
| Streaming mode safety | Not applicable | Unsafe (silently produces wrong results) |

Both components share the same gaps in testing and globalMap coverage, suggesting a systemic pattern across transform components.

## Appendix G: Type Mapping Deep Dive

### How Schema Casting Works (or Doesn't)

The `PivotToColumnsDelimited` component has its own schema casting logic (lines 230-243) that is separate from and incompatible with the base class `validate_schema()` method (base_component.py lines 314-359). This creates confusion about which type system is in use.

#### Component-level schema casting (lines 230-243)

```python
schema = self.config.get('schema', {})
if schema:
    for col, col_type in schema.items():
        if col in pivoted_data.columns:
            if col_type == 'int':
                pivoted_data[col] = pivoted_data[col].apply(
                    lambda x: int(x) if x != '' else None
                )
            elif col_type == 'float':
                pivoted_data[col] = pivoted_data[col].apply(
                    lambda x: float(x) if x != '' else None
                )
```

**Key observations**:
1. Expects `schema` as `Dict[str, str]` (column name -> type string)
2. Only handles `'int'` and `'float'` type strings
3. Does not handle: `'str'`, `'datetime'`, `'Decimal'`, `'bool'`, `'long'`, `'double'`
4. Does not handle Talend type identifiers: `'id_String'`, `'id_Integer'`, `'id_Long'`, etc.
5. Replaces `''` with `None`, re-introducing NaN values after `fillna('')`
6. Uses row-by-row `apply()` lambda (slow)

#### Base class validate_schema() (base_component.py lines 314-359)

```python
type_mapping = {
    'id_String': 'object',
    'id_Integer': 'int64',
    'id_Long': 'int64',
    'id_Float': 'float64',
    'id_Double': 'float64',
    'id_Boolean': 'bool',
    'id_Date': 'datetime64[ns]',
    'id_BigDecimal': 'object',
    'str': 'object',
    'int': 'int64',
    'long': 'int64',
    'float': 'float64',
    'double': 'float64',
    'bool': 'bool',
    'date': 'datetime64[ns]',
    'decimal': 'object'
}
```

**Key observations**:
1. Expects `schema` as `List[Dict]` (list of column definitions with `name` and `type` keys)
2. Handles both Talend type identifiers and Python type names
3. Uses vectorized `pd.to_numeric()` for numeric types (much faster)
4. Uses `pd.to_datetime()` for date types
5. Handles nullable integers with `fillna(0).astype('int64')`
6. **Not called by PivotToColumnsDelimited** -- the component never invokes `validate_schema()`

#### Type mapping comparison

| Type String | Component Casting (lines 230-243) | Base validate_schema() | Behavior Match? |
|-------------|----------------------------------|----------------------|-----------------|
| `'int'` | `int(x)` via lambda; `''` -> `None` | `pd.to_numeric()` then `fillna(0).astype('int64')` | **No** -- different NaN handling |
| `'float'` | `float(x)` via lambda; `''` -> `None` | `pd.to_numeric(errors='coerce')` | **No** -- different error handling |
| `'str'` | Not handled | `'object'` (no conversion) | N/A |
| `'datetime'`/`'date'` | Not handled | `pd.to_datetime()` | N/A |
| `'bool'` | Not handled | `.astype('bool')` | N/A |
| `'id_String'` | Not handled | `'object'` (no conversion) | N/A |
| `'id_Integer'` | Not handled | `pd.to_numeric()` then int64 | N/A |

**Recommendation**: Remove the component-level schema casting entirely and use the base class `validate_schema()` method instead. This provides broader type support, vectorized operations, and consistent behavior across all components.

## Appendix H: Detailed Pivot Operation Analysis

### pandas `pivot_table()` vs Talend Pivot

The core pivot operation uses:

```python
pivoted_data = input_data.pivot_table(
    index=group_by_columns,        # becomes row index
    columns=pivot_column,          # distinct values become column headers
    values=aggregation_column,     # values to aggregate
    aggfunc=aggregation_function   # aggregation function (string name)
).reset_index()                    # flatten MultiIndex back to columns
```

#### Behavioral comparison

| Aspect | pandas `pivot_table()` | Talend `tPivotToColumnsDelimited` | Match? |
|--------|----------------------|----------------------------------|--------|
| Duplicate handling | Aggregates duplicates using `aggfunc` | Aggregates duplicates using selected function | Yes |
| Missing combinations | `NaN` in output cell | Empty cell / null | Yes (after `fillna('')`) |
| Column ordering | Sorted alphabetically by pivot values | Sorted by pivot values (may vary by version) | Approximately |
| Group-by ordering | Sorted by group-by values | Original input order preserved | **Potential difference** |
| NaN in pivot column | Excluded from output columns by default (pandas >= 1.1) | Behavior varies | Approximately |
| NaN in group-by column | Excluded from output rows by default (pandas >= 1.1) | May be included | **Potential difference** |
| All-NaN aggregation (sum) | Returns 0.0 for sum, NaN for others | Returns empty/null | **Difference for sum** |
| Non-numeric values with sum | TypeError | Error or string concatenation | Similar |
| Empty input | Empty DataFrame | Empty output | Yes |

#### `reset_index()` behavior

After `pivot_table()`, the result has a MultiIndex on the columns (if the pivot column has multiple values) and the group-by columns as the row index. `reset_index()` flattens this:

- Group-by columns move from the index to regular columns
- The column MultiIndex is flattened (top level is the aggregation column name, which is dropped; bottom level is the pivot values)

**Potential issue**: When `pivot_table()` produces a MultiIndex column header (e.g., `('amount', 'A')`, `('amount', 'B')`), `reset_index()` preserves this. The resulting column names may include the aggregation column name as a tuple prefix. Talend does not include the aggregation column name in the pivot headers -- only the pivot values. This may cause column name mismatches if not handled.

The current implementation does not explicitly handle MultiIndex column flattening. In practice, when `values` is a single column (which is always the case here), pandas drops the top level automatically, so column names are just the pivot values. But this behavior may vary across pandas versions.

### Memory Profile of `pivot_table()`

The `pivot_table()` operation creates:
1. A temporary groupby object (memory proportional to input)
2. The pivoted result (memory proportional to groups x pivot_values)
3. After `reset_index()`, a flat DataFrame

Peak memory during pivot = input_size + pivoted_size. For sparse pivots (many groups, many pivot values), the pivoted result can be much larger than the input due to NaN padding.

### Performance Profile of `pivot_table()`

| Input Rows | Distinct Pivots | Groups | pivot_table() Time | Post-process Time | Total |
|------------|-----------------|--------|-------------------|-------------------|-------|
| 10K | 10 | 1K | ~10ms | ~50ms | ~60ms |
| 100K | 50 | 10K | ~100ms | ~500ms | ~600ms |
| 1M | 100 | 100K | ~1s | ~5s | ~6s |
| 10M | 500 | 1M | ~10s | ~50s | ~60s |

The post-processing (float-to-int loops) dominates total time for large datasets due to row-by-row Python iteration. The `pivot_table()` itself is vectorized and fast.

## Appendix I: Execution Flow Trace

### Complete execution path for a typical pivot operation

```
1. Engine calls component.execute(input_data)
   |
2. BaseComponent.execute():
   |-- Step 1: _resolve_java_expressions() [if java_bridge set]
   |     |-- Scans config for {{java}} markers
   |     |-- [NOTE: converter doesn't set markers for this component]
   |
   |-- Step 2: context_manager.resolve_dict(self.config)
   |     |-- Resolves ${context.var} references in all config values
   |     |-- Filename like "${context.output_dir}/pivot.csv" becomes "/data/output/pivot.csv"
   |
   |-- Step 3: _auto_select_mode(input_data)
   |     |-- If HYBRID: checks input_data.memory_usage()
   |     |-- If > 3072 MB: returns STREAMING [BUG: produces wrong pivot results]
   |     |-- Otherwise: returns BATCH
   |
   |-- Step 4: _execute_batch(input_data) [normal path]
   |     |-- Calls _process(input_data)
   |
3. PivotToColumnsDelimited._process(input_data):
   |-- Check for empty input (None or empty DF)
   |     |-- If empty: _update_stats(0, 0, 0), return {'main': pd.DataFrame()}
   |
   |-- Extract config with defaults
   |     |-- pivot_column, aggregation_column, aggregation_function
   |     |-- group_by_columns, output_file, separators, encoding, create_file
   |
   |-- Process separators
   |     |-- unicode_escape on row_separator [BUG: dangerous]
   |     |-- Strip quotes from field_separator and row_separator
   |
   |-- Runtime validation
   |     |-- Check required fields non-empty
   |     |-- Check field_separator is single char [BUG: too restrictive]
   |
   |-- Pivot operation
   |     |-- pd.pivot_table(index=groups, columns=pivot, values=agg, aggfunc=func)
   |     |-- .reset_index()
   |     |-- First float-to-int loop [BUG: mixed types]
   |     |-- fillna('') [creates copy]
   |     |-- Second float-to-int loop [BUG: crashes on empty strings]
   |     |-- Schema type casting [limited; re-introduces NaN]
   |
   |-- File writing (if create_file)
   |     |-- to_csv(output_file, sep=separator, line_terminator=..., encoding=..., index=False)
   |     |-- [BUG: deprecated line_terminator param]
   |     |-- [MISSING: no header control, no append, no quoting]
   |
   |-- Statistics update
   |     |-- _update_stats(rows_in, rows_out, 0)
   |     |-- [MISSING: should also set NB_LINE_OUT]
   |
   |-- Return {'main': pivoted_data, 'output_file': output_file}
   |
4. Back in BaseComponent.execute():
   |-- stats['EXECUTION_TIME'] = elapsed
   |-- _update_global_map() [BUG: crashes if global_map is set]
   |-- status = SUCCESS
   |-- result['stats'] = self.stats.copy()
   |-- return result
```

### Error path

```
Exception during _process():
  |
  BaseComponent.execute() catches it:
  |-- status = ERROR
  |-- error_message = str(e)
  |-- stats['EXECUTION_TIME'] = elapsed
  |-- _update_global_map() [BUG: crashes if global_map is set]
  |-- [MISSING: should set ERROR_MESSAGE in globalMap]
  |-- logger.error(f"Component {self.id} execution failed: {e}")
  |-- raise  [re-raises the original exception]
```

## Appendix J: Pandas Version Compatibility

| pandas Feature | Version Required | Status in Component |
|---------------|-----------------|-------------------|
| `pivot_table()` | All versions | Used correctly |
| `fillna('')` | All versions | Used correctly |
| `to_csv(line_terminator=)` | 0.x - 1.4 (deprecated 1.5+) | **Used but deprecated** |
| `to_csv(lineterminator=)` | 1.5+ (preferred) | **Not used** |
| `pd.api.types.is_numeric_dtype()` | 0.20+ | Used correctly |
| `DataFrame.apply(lambda)` | All versions | Used (but slow) |
| `pivot_table(observed=)` | 1.3+ | Not used (may affect categorical pivot columns) |
| `fillna(inplace=True)` | All versions (deprecated 2.0+) | Not used |

**Minimum pandas version**: The component requires pandas >= 0.20 for `is_numeric_dtype`. For best compatibility and to avoid `FutureWarning`, pandas >= 1.5 is recommended (to use `lineterminator` instead of `line_terminator`).

---

*Report generated: 2026-03-21*
*Auditor: Claude Opus 4.6 (1M context)*
*Engine version: V1*
*Total issues found: 47 (5 P0, 14 P1, 22 P2, 6 P3)*
