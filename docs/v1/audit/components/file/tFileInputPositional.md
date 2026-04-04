# Audit Report: tFileInputPositional / FileInputPositional

> **Audited**: 2026-04-03
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report is scoped to the v1 engine exclusively

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileInputPositional` |
| **V1 Engine Class** | `FileInputPositional` |
| **Engine File** | `src/v1/engine/components/file/file_input_positional.py` (359 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_input_positional.py` |
| **Converter Dispatch** | `@REGISTRY.register("tFileInputPositional")` decorator-based dispatch |
| **Registry Aliases** | `tFileInputPositional` |
| **Category** | File / Input (Positional) |
| **Complexity** | Medium -- fixed-width file reader with 20 unique parameters, 2 TABLE params, engine 359 lines |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_input_positional.py` | Engine implementation (359 lines) |
| `src/converters/talend_to_v1/components/file/file_input_positional.py` | Converter class |
| `tests/converters/talend_to_v1/components/test_file_input_positional.py` | Converter tests (68 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 20 unique params + 2 framework params extracted; FORMATS and TRIMSELECT TABLE parsers; `_build_component_dict` pattern; filepath key matches engine; 7 per-feature needs_review entries for engine gaps; USE_BYTE phantom param excluded |
| Engine Feature Parity | **Y** | 0 | 5 | 3 | 2 | Engine reads 13 of 20 unique params; ignores process_long_row, uncompress, advanced_separator, check_date, trim_select, formats, encoding mismatch (UTF-8 vs ISO-8859-15); no REJECT flow |
| Code Quality | **Y** | 1 | 3 | 3 | 1 | Cross-cutting base class bugs; dead `_validate_config()`; `id_Boolean` mapped to `object`; advanced separator applied to ALL object columns; encoding default mismatch |
| Performance & Memory | **G** | 0 | 0 | 1 | 1 | Batch-only (no streaming); BigDecimal uses slow `apply()`; post-processing iterates string columns twice |
| Testing | **Y** | 0 | 0 | 2 | 0 | 68 converter unit tests across 11 test classes per gold standard; integration + regression guard passing; engine unit tests missing (P2) -- no engine test coverage prevents Green |

**Overall: Yellow -- Converter fully standardized (Green); engine has known gaps documented via needs_review; engine/code quality gaps keep overall at Yellow**

**Top Actions:**
1. Fix `_update_global_map()` crash in base class (P0, cross-cutting)
2. Implement per-column trim support in engine to match TRIMSELECT TABLE (P1)
3. Add compressed file reading support (P1, engine gap)
4. Add REJECT flow support for malformed rows (P1, engine gap)
5. Fix engine encoding default from UTF-8 to ISO-8859-15 (P2, engine mismatch)

---

## 3. Talend Feature Baseline

### What tFileInputPositional Does

`tFileInputPositional` reads a fixed-width (positional) file row by row, splits each row into fields based on a given pattern of column widths, and outputs the parsed fields as defined in the output schema to downstream components via a Row link. Unlike delimited files where separators mark field boundaries, positional files define field boundaries by character positions -- each column occupies a fixed number of characters in every row, with optional padding characters (typically spaces).

The component supports two modes: a simple pattern-based mode where all columns are defined by a comma-separated width string (e.g., "5,4,5"), and a "Customize" mode (ADVANCED_OPTION=true) where each column can have individual size, padding character, and alignment settings via the FORMATS TABLE. Per-column trim control is available via the TRIMSELECT TABLE when ADVANCED_OPTION is enabled.

**Source**: [tFileInputPositional Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/positional/tfileinputpositional-standard-properties), [tFileInputPositional Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/positional/tfileinputpositional-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileInputPositional/tFileInputPositional_java.xml)
**Component family**: Positional (File / Input)
**Available in**: All Talend products (Standard, MapReduce, Spark Batch, Spark Streaming variants)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Column definitions with types, lengths, patterns, nullable, key. Defines output structure. |
| 2 | File Name | `FILENAME` | FILE | `""` | Absolute file path or data stream variable. Supports context variables, globalMap references, Java expressions. Required. |
| 3 | Row Separator | `ROWSEPARATOR` | TEXT | `"\n"` | Character(s) identifying end of row. Supports `\r\n`, `\n`, `\r`. |
| 4 | Pattern | `PATTERN` | TEXT | `"5,4,5"` | Comma-separated field width values defining the positional layout. Each value is number of characters (or bytes if PATTERN_UNITS=BYTES). |
| 5 | Pattern Units | `PATTERN_UNITS` | CLOSED_LIST | `"SYMBOLS"` | Whether pattern widths measure characters ("SYMBOLS") or bytes ("BYTES"). |
| 6 | Customize | `ADVANCED_OPTION` | CHECK | `false` | Enable per-column customization for padding character and alignment via FORMATS TABLE. |
| 7 | Remove Empty Row | `REMOVE_EMPTY_ROW` | CHECK | `true` | Skip rows where all fields are empty or whitespace. |
| 8 | Trim All | `TRIMALL` | CHECK | `true` | Trim leading/trailing whitespace from all fields. |
| 9 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding for file reading. Note: non-UTF-8 default is common in Talend file components. |
| 10 | Die on Error | `DIE_ON_ERROR` | CHECK | `false` | Stop execution on error. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Header | `HEADER` | COUNT | `0` | Number of header rows to skip before reading data. |
| 2 | Footer | `FOOTER` | COUNT | `0` | Number of footer rows to skip at end of file. |
| 3 | Limit | `LIMIT` | TEXT | `""` | Maximum number of data rows to read. Empty = no limit. Supports expressions. |
| 4 | Process Long Row | `PROCESS_LONG_ROW` | CHECK | `false` | When true, rows longer than the sum of pattern widths are processed rather than truncated. |
| 5 | Advanced Separator | `ADVANCED_SEPARATOR` | CHECK | `false` | Enable locale-aware number formatting with custom thousands/decimal separators. |
| 6 | Thousands Separator | `THOUSANDS_SEPARATOR` | TEXT | `","` | Thousands separator character for numeric fields. Only used when ADVANCED_SEPARATOR=true. |
| 7 | Decimal Separator | `DECIMAL_SEPARATOR` | TEXT | `"."` | Decimal separator character for numeric fields. Only used when ADVANCED_SEPARATOR=true. |
| 8 | Check Date | `CHECK_DATE` | CHECK | `false` | Validate date fields against schema date patterns during reading. |
| 9 | Uncompress | `UNCOMPRESS` | CHECK | `false` | Read from ZIP/GZIP compressed files. |

### 3.3 TABLE Parameters

#### FORMATS TABLE (when ADVANCED_OPTION=true)

| Field | elementRef | Type | Description |
|-------|-----------|------|-------------|
| Schema Column | `SCHEMA_COLUMN` | str | Column name from schema |
| Size | `SIZE` | str | Character width for this column |
| Padding Char | `PADDING_CHAR` | str | Padding character (default space) |
| Align | `ALIGN` | str | Alignment: 'L' (left), 'R' (right), 'C' (center) |

#### TRIMSELECT TABLE (when ADVANCED_OPTION=true)

| Field | elementRef | Type | Description |
|-------|-----------|------|-------------|
| Schema Column | `SCHEMA_COLUMN` | str | Column name from schema |
| Trim | `TRIM` | bool | Whether to trim this specific column |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Parsed positional data rows |
| `REJECT` | Output | Row > Reject | Malformed rows with errorCode/errorMessage columns |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful execution |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires after execution error |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully processed |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows rejected |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message |

### 3.6 Behavioral Notes

1. **ISO-8859-15 encoding default** -- Talend defaults to ISO-8859-15 (Latin-9), NOT UTF-8. This is consistent across all Talend file input components.
2. **Pattern vs Customize mode** -- When ADVANCED_OPTION=false, the PATTERN string defines all column widths. When ADVANCED_OPTION=true, the FORMATS TABLE provides per-column control (size, padding, alignment), overriding PATTERN.
3. **TRIMALL defaults True** -- Unlike most boolean params, TRIMALL defaults to true, meaning fields are trimmed by default.
4. **REMOVE_EMPTY_ROW defaults True** -- Empty rows are skipped by default.
5. **LIMIT supports expressions** -- The LIMIT field is a TEXT type supporting Java expressions and context variables, not just static integers.
6. **USE_BYTE phantom parameter** -- The `USE_BYTE` param in some Talend versions is superseded by `PATTERN_UNITS` CLOSED_LIST. Engine reads pattern_units, not use_byte.
7. **TRIMSELECT per-column trim** -- When Customize mode is enabled, individual columns can override TRIMALL with per-column trim settings.

### 3.7 Config Key Deviation: filepath

The converter maps `FILENAME` to config key `filepath` (not `filename`). This is an **intentional deviation** from the D-38 snake_case convention because the v1 engine's `FileInputPositional._process()` method reads `self.config.get('filepath')` at line 198. Using `filepath` as the config key ensures the converter output is directly consumable by the engine without modification. This deviation is documented here and in the converter module docstring.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `@REGISTRY.register("tFileInputPositional")` with the `_build_component_dict` pattern (D-40). Parameters are extracted via `_get_str()`, `_get_bool()`, and `_get_int()` base class helpers. Two module-level TABLE parsers handle FORMATS and TRIMSELECT.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `FILENAME` | Yes | `filepath` | str, default "". Config key intentionally matches engine (D-38 deviation) |
| 2 | `ROWSEPARATOR` | Yes | `row_separator` | str, default "\\n" |
| 3 | `PATTERN` | Yes | `pattern` | str, default "5,4,5" |
| 4 | `PATTERN_UNITS` | Yes | `pattern_units` | str/CLOSED_LIST, default "SYMBOLS" |
| 5 | `ADVANCED_OPTION` | Yes | `advanced_option` | bool, default False |
| 6 | `REMOVE_EMPTY_ROW` | Yes | `remove_empty_row` | bool, default True |
| 7 | `TRIMALL` | Yes | `trim_all` | bool, default True |
| 8 | `ENCODING` | Yes | `encoding` | str, default "ISO-8859-15" |
| 9 | `HEADER` | Yes | `header_rows` | int, default 0 |
| 10 | `FOOTER` | Yes | `footer_rows` | int, default 0 |
| 11 | `LIMIT` | Yes | `limit` | str, default "" (supports expressions) |
| 12 | `DIE_ON_ERROR` | Yes | `die_on_error` | bool, default False |
| 13 | `PROCESS_LONG_ROW` | Yes | `process_long_row` | bool, default False |
| 14 | `ADVANCED_SEPARATOR` | Yes | `advanced_separator` | bool, default False |
| 15 | `THOUSANDS_SEPARATOR` | Yes | `thousands_separator` | str, default "," |
| 16 | `DECIMAL_SEPARATOR` | Yes | `decimal_separator` | str, default "." |
| 17 | `CHECK_DATE` | Yes | `check_date` | bool, default False |
| 18 | `UNCOMPRESS` | Yes | `uncompress` | bool, default False |
| 19 | `FORMATS` | Yes | `formats` | TABLE, stride variable (SCHEMA_COLUMN/SIZE/PADDING_CHAR/ALIGN) |
| 20 | `TRIMSELECT` | Yes | `trim_select` | TABLE, stride-2 (SCHEMA_COLUMN/TRIM) |
| 21 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, bool, default False |
| 22 | `LABEL` | Yes | `label` | Framework param, str, default "" |

**Excluded phantom params:**
- `USE_BYTE` -- superseded by PATTERN_UNITS; engine reads pattern_units instead

**Summary**: 20 of 20 unique parameters extracted (100%). 2 framework params extracted. 1 phantom param excluded.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Direct from SchemaColumn |
| `type` | Yes | Converted via `convert_type()` (Talend id_* -> Python types) |
| `nullable` | Yes | Direct from SchemaColumn |
| `key` | Yes | Direct from SchemaColumn |
| `length` | Yes | Only when >= 0 |
| `precision` | Yes | Only when >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion via `_convert_date_pattern()` |
| `default` | No | Not supported by base class `_parse_schema()` |

### 4.3 Expression Handling

Context variables (`context.var`) and Java expressions (`{{java}}`) in parameter values are passed through as-is in the v1 JSON config. The v1 engine's `resolve_dict()` method resolves these at runtime. The converter does not attempt to evaluate or transform expressions.

### 4.4 Converter Issues

None. All parameters correctly extracted with proper defaults and types.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | `process_long_row` | Engine does not implement long-row buffering | engine_gap |
| 2 | `uncompress` | Engine does not support reading from ZIP archives | engine_gap |
| 3 | `advanced_separator` | Engine does not support locale-aware number formatting | engine_gap |
| 4 | `check_date` | Engine does not validate date fields against schema patterns | engine_gap |
| 5 | `trim_select` | Engine only supports all-or-nothing trim via trim_all, not per-column | engine_gap |
| 6 | `encoding` | Engine defaults to UTF-8 while Talend defaults to ISO-8859-15 | engine_gap |
| 7 | `formats` | Engine does not read FORMATS table -- uses pattern widths only | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | File reading (filepath) | **Yes** | High | `_process()` line 198 | Uses `pd.read_fwf()` |
| 2 | Pattern-based column widths | **Yes** | High | `_process()` line 245 | Parses comma-separated widths |
| 3 | Row separator | **Partial** | Medium | `_process()` line 199 | Config read but pandas handles line endings |
| 4 | Header skip | **Yes** | High | `_process()` line 264 | `skiprows=header_rows` |
| 5 | Footer skip | **Yes** | High | `_process()` line 267 | `skipfooter=footer_rows` |
| 6 | Row limit | **Yes** | High | `_process()` line 265 | `nrows=limit` |
| 7 | Trim all | **Yes** | Medium | `_process()` line 281 | Strips string columns only |
| 8 | Remove empty row | **Yes** | Medium | `_process()` line 288 | Uses `dropna(how='all')` |
| 9 | Schema validation | **Yes** | Medium | `_process()` line 300 | `validate_schema()` base method |
| 10 | Die on error | **Yes** | High | `_process()` line 236 | File-not-found + general exception handling |
| 11 | Advanced separator | **Partial** | Low | `_process()` line 303 | Applies to ALL object columns, not just numeric |
| 12 | Check date | **Partial** | Low | `_process()` line 310 | Uses `pd.to_datetime(errors='coerce')` |
| 13 | Encoding | **Yes** | Medium | `_process()` line 268 | Supports encoding param but defaults to UTF-8 |
| 14 | Pattern units (SYMBOLS/BYTES) | **No** | N/A | -- | Engine assumes character-based widths |
| 15 | Customize (FORMATS TABLE) | **No** | N/A | -- | Engine uses pattern string only |
| 16 | Per-column trim (TRIMSELECT) | **No** | N/A | -- | Engine uses trim_all only |
| 17 | Process long row | **No** | N/A | -- | Engine truncates to pattern width |
| 18 | Uncompress (ZIP/GZIP) | **No** | N/A | -- | Not implemented |
| 19 | REJECT flow | **No** | N/A | -- | No error row capture |
| 20 | BigDecimal conversion | **Yes** | Medium | `_process()` line 322 | Converts via `Decimal(str(x))` |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FIP-001 | **P1** | REJECT flow not implemented -- malformed rows are silently processed or skipped rather than routed to reject output with errorCode/errorMessage |
| ENG-FIP-002 | **P1** | Compressed file reading (UNCOMPRESS=true) not implemented -- raises error on compressed input |
| ENG-FIP-003 | **P1** | FORMATS TABLE per-column customization not implemented -- only pattern-based widths supported |
| ENG-FIP-004 | **P1** | Per-column trim (TRIMSELECT TABLE) not implemented -- only global trim_all supported |
| ENG-FIP-005 | **P1** | Process long row not implemented -- rows exceeding pattern width are truncated by pd.read_fwf |
| ENG-FIP-006 | **P2** | Encoding default is UTF-8 in engine but ISO-8859-15 in Talend -- files with Latin-9 characters may be misread |
| ENG-FIP-007 | **P2** | Advanced separator applies to ALL object columns, not just numeric columns with type hints |
| ENG-FIP-008 | **P2** | Check date uses `pd.to_datetime(errors='coerce')` instead of validating against schema date patterns |
| ENG-FIP-009 | **P3** | Pattern units BYTES mode not implemented -- only SYMBOLS (character) mode works |
| ENG-FIP-010 | **P3** | `{id}_ERROR_MESSAGE` globalMap variable not set on errors |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Total rows processed |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | Rows successfully processed |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | Always 0 (no reject flow) |
| `{id}_ERROR_MESSAGE` | Yes | No | -- | Not implemented (P3) |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FIP-001 | **P0** | `base_component.py:304` | CROSS-CUTTING: `_update_global_map()` crashes with AttributeError when globalMap is set. Affects stats recording. |
| BUG-FIP-002 | **P1** | `file_input_positional.py:303-307` | Advanced separator replacement applied to ALL object (string) columns, not just numeric columns. Corrupts string data containing commas or dots. |
| BUG-FIP-003 | **P1** | `file_input_positional.py:310-316` | Check date conversion uses `pd.to_datetime(errors='coerce')` which silently converts invalid dates to NaT, ignoring schema date patterns. |
| BUG-FIP-004 | **P1** | `file_input_positional.py:288-293` | `dropna(how='all')` misses rows that are blank strings (not NaN). After read_fwf, whitespace-only rows become empty strings if trim_all is applied first. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FIP-001 | **P2** | Engine class constants use `DEFAULT_REMOVE_EMPTY_ROWS` (plural) but config key is `remove_empty_row` (singular) |
| NAME-FIP-002 | **P2** | Engine default `DEFAULT_ENCODING = 'UTF-8'` does not match Talend default `ISO-8859-15` |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FIP-001 | **P2** | "Use logging, not print" | No print statements found -- compliant |
| STD-FIP-002 | **P3** | "Custom exceptions for all error types" | Uses appropriate custom exceptions (ConfigurationError, FileOperationError, ComponentExecutionError) -- compliant |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

| Concern | Assessment |
|---------|------------|
| Path traversal | No input validation on filepath -- user-controlled paths could read arbitrary files |
| File permissions | No permission check before read -- relies on OS-level permissions |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Level usage | Appropriate: info for start/complete, debug for details, error for failures |
| Sensitive data | File path logged at INFO level -- acceptable |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses ConfigurationError, FileOperationError, ComponentExecutionError -- correct hierarchy |
| Exception chaining | `ComponentExecutionError(self.id, error_msg, e)` preserves original exception |
| die_on_error handling | Properly returns empty DataFrame when die_on_error=False, raises when True |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_process()` has proper type hints for params and return |
| Parameter types | `_validate_config()` returns `List[str]` -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FIP-001 | **P2** | No streaming mode -- entire file loaded into memory. Large positional files (>1GB) may cause OOM |
| PERF-FIP-002 | **P3** | BigDecimal conversion uses slow `apply(lambda)` per cell -- could use vectorized conversion |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Not supported -- batch only via pd.read_fwf() |
| Memory threshold | No memory limit check before loading file |
| Large data handling | Limited by available memory; no chunked reading |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 68 | `tests/converters/talend_to_v1/components/test_file_input_positional.py` |
| Engine unit tests | 0 | None |
| Integration tests | Covered | `tests/converters/talend_to_v1/test_integration.py` + `test_converter_output_structure.py` |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-FIP-001 | **P2** | No engine unit tests -- FileInputPositional._process() untested directly |
| TEST-FIP-002 | **P2** | No tests for advanced_separator string corruption edge case |

### 8.3 Recommended Test Cases

1. Engine test: basic file read with pattern "5,4,5" and verify column values
2. Engine test: header/footer skip with known row counts
3. Engine test: die_on_error=False with missing file returns empty DataFrame
4. Engine test: trim_all strips whitespace from string fields
5. Engine test: advanced_separator replaces separators in numeric columns

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 1 | **BUG-FIP-001** |
| P1 | 8 | **ENG-FIP-001**, **ENG-FIP-002**, **ENG-FIP-003**, **ENG-FIP-004**, **ENG-FIP-005**, **BUG-FIP-002**, **BUG-FIP-003**, **BUG-FIP-004** |
| P2 | 8 | **ENG-FIP-006**, **ENG-FIP-007**, **ENG-FIP-008**, **NAME-FIP-001**, **NAME-FIP-002**, **PERF-FIP-001**, **TEST-FIP-001**, **TEST-FIP-002** |
| P3 | 4 | **ENG-FIP-009**, **ENG-FIP-010**, **STD-FIP-002**, **PERF-FIP-002** |
| **Total** | **21** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 10 | ENG-FIP-001 through ENG-FIP-010 |
| Bug (BUG) | 4 | BUG-FIP-001 through BUG-FIP-004 |
| Naming (NAME) | 2 | NAME-FIP-001, NAME-FIP-002 |
| Standards (STD) | 1 | STD-FIP-002 |
| Performance (PERF) | 2 | PERF-FIP-001, PERF-FIP-002 |
| Testing (TEST) | 2 | TEST-FIP-001, TEST-FIP-002 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- stats lost |
| XCUT-002 | `base_component.py:202` | `self.config` mutation via `resolve_dict()` -- non-reentrant in iterate loops |

---

## 10. Recommendations

### Immediate (Before Production)

1. Fix `_update_global_map()` crash in base class (P0 cross-cutting, BUG-FIP-001)

### Short-term (Hardening)

2. Implement REJECT flow for malformed rows (ENG-FIP-001)
3. Add compressed file reading support (ENG-FIP-002)
4. Implement FORMATS TABLE per-column customization (ENG-FIP-003)
5. Implement TRIMSELECT per-column trim (ENG-FIP-004)
6. Implement process long row buffering (ENG-FIP-005)
7. Fix advanced separator to only apply to numeric-typed columns (BUG-FIP-002)
8. Fix check_date to use schema date patterns (BUG-FIP-003)
9. Fix empty row detection for blank strings (BUG-FIP-004)

### Long-term (Optimization)

10. Implement BYTES pattern units mode (ENG-FIP-009)
11. Set `{id}_ERROR_MESSAGE` globalMap on errors (ENG-FIP-010)
12. Add vectorized BigDecimal conversion (PERF-FIP-002)
13. Add engine unit tests (TEST-FIP-001, TEST-FIP-002)

---

## 11. Risk Assessment

This section is included because tFileInputPositional handles fixed-width file parsing with character position-dependent logic -- errors in position calculation silently corrupt all downstream data. The 359-line engine has 10 engine feature gaps and 4 bugs.

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Position offset error corrupts all columns | Medium | High -- silent data corruption: all fields shifted, no error raised | Validate that sum of pattern widths matches actual row length; add REJECT flow for mismatched rows |
| Encoding mismatch silently garbles data | High | Medium -- Latin-9 characters (Euro sign, accented chars) become garbage when engine defaults to UTF-8 | Always pass encoding explicitly from converter config; fix engine default to ISO-8859-15 |
| Large file OOM crash | Medium | High -- no streaming; 1GB+ files loaded entirely into memory | Add chunked reading via pd.read_fwf(chunksize=); implement streaming mode |
| TRIMSELECT ignored causes precision loss | Low | Medium -- numeric fields with embedded spaces may be incorrectly trimmed or not trimmed | Implement per-column trim; until then document that TRIMALL controls all columns |
| Blank rows pass through as data | Medium | Low -- dropna(how='all') misses whitespace-only rows after trim | Apply remove_empty_row check after trim, not before; check for empty strings too |
| Advanced separator corrupts string data | Low | High -- commas and dots removed from all string columns, not just numeric | Filter columns by schema type before applying separator replacement |
| skipfooter + nrows interaction | Low | Medium -- pd.read_fwf with both skipfooter and nrows may yield unexpected row counts | Test and document interaction; consider manual footer handling |

### High-Risk Job Patterns

1. **Non-UTF-8 files with default encoding** -- Engine defaults to UTF-8, but Talend uses ISO-8859-15. Any positional file with Latin-9 characters will be misread unless encoding is explicitly set.
2. **Customize mode with FORMATS TABLE** -- Engine ignores FORMATS table and uses only the PATTERN string. Jobs relying on per-column padding/alignment will produce incorrect field boundaries.
3. **Advanced separator with mixed data types** -- Separator replacement applied to ALL string columns corrupts non-numeric data.
4. **Large files (>500MB)** -- No streaming or chunked reading; entire file loaded into DataFrame memory.
5. **Per-column trim (TRIMSELECT)** -- Engine ignores per-column trim settings; only TRIMALL is applied.

### Safe Usage Patterns

1. **Simple pattern-based files with TRIMALL=true** -- Core path works correctly when all columns use character-based widths defined by PATTERN string.
2. **Explicit UTF-8 encoding** -- When ENCODING is explicitly set to match the file's actual encoding, parsing works correctly.
3. **Small to medium files (<100MB)** -- Memory is sufficient for batch processing.
4. **die_on_error=True with monitored jobs** -- Error handling correctly raises exceptions for missing files and invalid configurations.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub _java.xml | `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileInputPositional/tFileInputPositional_java.xml` | Complete parameter definitions, CLOSED_LIST values, defaults, TABLE structures |
| Official Talend docs (8.0) | `https://help.qlik.com/talend/en-US/components/8.0/positional/tfileinputpositional-standard-properties` | Component description, behavioral notes |
| Official Talend docs (7.3) | `https://help.qlik.com/talend/en-US/components/7.3/positional/tfileinputpositional-standard-properties` | Cross-version parameter validation |
| Engine source | `src/v1/engine/components/file/file_input_positional.py` (359 lines) | Feature parity analysis, bug identification |
| Converter source | `src/converters/talend_to_v1/components/file/file_input_positional.py` | Converter audit |
| Converter tests | `tests/converters/talend_to_v1/components/test_file_input_positional.py` (68 tests) | Test coverage analysis |
| Base class | `src/v1/engine/base_component.py` | Cross-cutting issue identification |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- stats recording fails |
| XCUT-002 | `base_component.py:202` | `self.config` mutation via `resolve_dict()` -- if component runs in iterate loop, config modified on first pass |
| XCUT-003 | `base_component.py:174` | `replace_in_config` literal `[i]` -- affects globalMap key interpolation |

### Edge-Case Checklist Results

| Check | Result | Notes |
|-------|--------|-------|
| NaN handling | Risk | `dropna(how='all')` correct for NaN but misses empty strings |
| Empty strings in config | Safe | Empty filepath triggers warning in converter; engine raises ConfigurationError |
| Empty DataFrame input | N/A | Source component -- no input data |
| HYBRID streaming mode | N/A | Not used for input components |
| `_update_global_map()` crash | Risk | Stats lost when globalMap set (XCUT-001) |
| Type demotion | Risk | BigDecimal->float64 during iterrows reconstruction |
| `validate_schema` nullable logic | Risk | Inverted nullable logic may fill wrong columns |
| `_validate_config()` dead code | Yes | Defined but never called by base class |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after v1.1 converter standardization (Phase 09-10)*
