# Audit Report: tFileOutputPositional / FileOutputPositional

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report is scoped to the v1 engine exclusively

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileOutputPositional` |
| **V1 Engine Class** | `FileOutputPositional` |
| **Engine File** | `src/v1/engine/components/file/file_output_positional.py` (468 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_output_positional.py` (178 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileOutputPositional")` decorator-based dispatch |
| **Registry Aliases** | **NONE** -- FileOutputPositional is NOT registered in engine `COMPONENT_REGISTRY` despite having a 468-line engine file (CRITICAL gap) |
| **Category** | File / Output (Positional) |
| **Complexity** | Medium-High -- sink component with 20 unique parameters, FORMATS 5-field TABLE, engine 468 lines, but engine not registered |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_output_positional.py` | Engine implementation (468 lines) -- exists but NOT registered |
| `src/converters/talend_to_v1/components/file/file_output_positional.py` | Converter class (178 lines) |
| `tests/converters/talend_to_v1/components/test_file_output_positional.py` | Converter tests (48 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 20 unique params + 2 framework params extracted; FORMATS 5-field TABLE parser (stride-5); `_build_component_dict` pattern; sink schema (input populated, output empty); 12 per-feature needs_review entries + 1 registration gap entry |
| Engine Feature Parity | **Y** | 1 | 3 | 2 | 1 | CRITICAL: Engine file NOT registered in COMPONENT_REGISTRY (P0); engine defaults differ from _java.xml (encoding utf-8 vs ISO-8859-15, include_header True vs false); KEEP truncation incomplete; 11 config keys not read by engine |
| Code Quality | **Y** | 1 | 2 | 3 | 1 | Cross-cutting `_update_global_map()` crash (P0); VALID_KEEP_OPTIONS has incorrect values; append+compress mode logic bug; f-string logger |
| Performance & Memory | **Y** | 0 | 1 | 1 | 1 | `iterrows()` for row-by-row writing (slow for large DataFrames); schema_map rebuilt per row; string concatenation in loop |
| Testing | **Y** | 0 | 0 | 1 | 0 | 48 converter unit tests across 9 test classes per gold standard; integration + regression guard passing; engine unit tests missing (P2) -- no engine test coverage prevents Green |

**Overall: Yellow -- Converter fully standardized (Green); engine file exists but NOT registered in COMPONENT_REGISTRY (critical gap); engine/code quality gaps keep overall at Yellow**

**Top Actions:**

1. Register FileOutputPositional in engine `COMPONENT_REGISTRY` (P0, critical -- engine file exists but cannot be instantiated)
2. Fix `_update_global_map()` crash in base class (P0, cross-cutting)
3. Fix engine encoding default from `utf-8` to `ISO-8859-15` (P1, engine default mismatch)
4. Fix engine `include_header` default from `True` to `False` (P1, engine default mismatch)
5. Add engine unit tests for FileOutputPositional (P2, testing gap)

---

## 3. Talend Feature Baseline

### What tFileOutputPositional Does

`tFileOutputPositional` writes data to a fixed-width (positional) file where each column occupies a fixed number of characters in every row. Fields are padded with a configurable character (typically spaces or zeros) and aligned left, center, or right within their fixed-width slot. Unlike delimited files, there are no field separators -- field boundaries are defined purely by character positions.

The component is commonly used for writing COBOL/mainframe-compatible files, EDI records, report files with aligned columns, and legacy system integration where fixed-width formats are required. It supports 20 unique parameters covering file path, row separators, column formatting (via a 5-field FORMATS TABLE), compression (gzip), encoding, and various output options.

Each column in the FORMATS TABLE defines: `SCHEMA_COLUMN` (column name), `SIZE` (fixed width in characters), `PADDING_CHAR` (fill character), `ALIGN` (LEFT/CENTER/RIGHT), and `KEEP` (which part to keep when data exceeds size -- ALL/LEFT/MIDDLE/RIGHT).

**Source**: [Talend 7.3 tFileOutputPositional docs](https://help.qlik.com/talend/en-US/components/7.3/positional/tfileoutputpositional-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileOutputPositional/tFileOutputPositional_java.xml)
**Component family**: Positional (File / Output)
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Use existing dynamic schema | `USE_EXISTING_DYNAMIC` | CHECK | `false` | When true, uses an existing dynamic schema from another component referenced by DYNAMIC. |
| 2 | Dynamic schema source | `DYNAMIC` | COMPONENT_LIST | `""` | Component ID providing the dynamic schema. Conditional on USE_EXISTING_DYNAMIC=true. |
| 3 | Use stream | `USESTREAM` | CHECK | `false` | Write to a named output stream instead of a file. When true, FILENAME is ignored. |
| 4 | Stream name | `STREAMNAME` | TEXT | `"outputStream"` | Name of the output stream variable. Conditional on USESTREAM=true. |
| 5 | File name | `FILENAME` | FILE | `""` | Absolute output file path. Supports context variables and Java expressions. Required when USESTREAM=false. |
| 6 | Row separator | `ROWSEPARATOR` | TEXT | `"\n"` | Character(s) identifying end of row. Supports escape sequences (\r\n, \n, \r). |
| 7 | Append | `APPEND` | CHECK | `false` | Append to existing file instead of overwriting. |
| 8 | Include header | `INCLUDEHEADER` | CHECK | `false` | Write column names as the first row. |
| 9 | Compress | `COMPRESS` | CHECK | `false` | Compress output using gzip. |
| 10 | Formats | `FORMATS` | TABLE | `[]` | Column format definitions. 5-field TABLE: SCHEMA_COLUMN, SIZE, PADDING_CHAR, ALIGN (CLOSED_LIST: LEFT/CENTER/RIGHT), KEEP (CLOSED_LIST: ALL/LEFT/MIDDLE/RIGHT). |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 11 | Advanced separator | `ADVANCED_SEPARATOR` | CHECK | `false` | Enable locale-aware number formatting with custom thousands/decimal separators. |
| 12 | Thousands separator | `THOUSANDS_SEPARATOR` | TEXT | `","` | Thousands grouping separator. Conditional on ADVANCED_SEPARATOR=true. |
| 13 | Decimal separator | `DECIMAL_SEPARATOR` | TEXT | `"."` | Decimal point separator. Conditional on ADVANCED_SEPARATOR=true. |
| 14 | Use byte | `USE_BYTE` | CHECK | `false` | Measure column widths in bytes instead of characters (for multi-byte encodings). |
| 15 | Create directory | `CREATE` | CHECK | `true` | Automatically create parent directories if they don't exist. |
| 16 | Flush on row | `FLUSHONROW` | CHECK | `false` | Flush the output buffer after a group of rows. |
| 17 | Flush row count | `FLUSHONROW_NUM` | TEXT | `"1"` | Number of rows per flush group. Supports expressions. |
| 18 | Row mode | `ROW_MODE` | CHECK | `false` | Write each row individually instead of buffering. |
| 19 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding for the output file. Default is ISO-8859-15, NOT UTF-8. |
| 20 | Delete empty file | `DELETE_EMPTYFILE` | CHECK | `false` | Delete the output file if no data was written. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Data to write to the positional file. Each row becomes one fixed-width line. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after all rows have been written successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires if the component fails. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total rows processed (written) |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully written |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows that failed (typically 0) |

### 3.5 Behavioral Notes

1. **ISO-8859-15 encoding default**: Talend defaults to ISO-8859-15 (Latin-9), not UTF-8. This is important for Western European character sets and differs from what most developers would expect.
2. **FORMATS TABLE is required for meaningful output**: Without FORMATS entries, no columns are written. The TABLE defines the physical layout of every output column.
3. **KEEP determines truncation behavior**: When data exceeds SIZE, KEEP controls which part is retained: ALL (no truncation, may exceed width), LEFT (keep leftmost chars), MIDDLE (keep center), RIGHT (keep rightmost chars).
4. **ALIGN determines padding placement**: LEFT pads on right, CENTER pads both sides, RIGHT pads on left.
5. **PADDING_CHAR is typically a single character**: Common values are space (' ') and zero ('0'). The converter preserves the raw value from _java.xml with quotes stripped.
6. **Gzip compression changes file mode**: When COMPRESS=true, the engine opens the file in binary mode ('ab') and encodes strings before writing.
7. **CREATE=true by default**: Parent directories are automatically created, which differs from some other file components.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `@REGISTRY.register("tFileOutputPositional")` decorator-based dispatch. It extracts all 20 unique parameters plus 2 framework parameters using `_get_str()`, `_get_bool()`, and `_get_str()` (for FLUSHONROW_NUM as string for expression support). FORMATS TABLE is parsed by a module-level `_parse_formats()` function using stride-5 grouping with quote stripping.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `USE_EXISTING_DYNAMIC` | Yes | `use_existing_dynamic` | bool, default False. Was MISSING in prior version. |
| 2 | `DYNAMIC` | Yes | `dynamic` | str, default "". Was MISSING in prior version. |
| 3 | `USESTREAM` | Yes | `usestream` | bool, default False. Was MISSING in prior version. |
| 4 | `STREAMNAME` | Yes | `streamname` | str, default "outputStream". Was MISSING in prior version. |
| 5 | `FILENAME` | Yes | `filepath` | str, default "" |
| 6 | `ROWSEPARATOR` | Yes | `row_separator` | str, default "\\n" |
| 7 | `APPEND` | Yes | `append` | bool, default False |
| 8 | `INCLUDEHEADER` | Yes | `include_header` | bool, default False |
| 9 | `COMPRESS` | Yes | `compress` | bool, default False |
| 10 | `FORMATS` | Yes | `formats` | TABLE, stride-5 (SCHEMA_COLUMN, SIZE, PADDING_CHAR, ALIGN, KEEP). Quotes stripped. |
| 11 | `ADVANCED_SEPARATOR` | Yes | `advanced_separator` | bool, default False |
| 12 | `THOUSANDS_SEPARATOR` | Yes | `thousands_separator` | str, default "," |
| 13 | `DECIMAL_SEPARATOR` | Yes | `decimal_separator` | str, default "." |
| 14 | `USE_BYTE` | Yes | `use_byte` | bool, default False |
| 15 | `CREATE` | Yes | `create` | bool, default True |
| 16 | `FLUSHONROW` | Yes | `flushonrow` | bool, default False |
| 17 | `FLUSHONROW_NUM` | Yes | `flushonrow_num` | str, default "1". Stored as string for expression support. |
| 18 | `ROW_MODE` | Yes | `row_mode` | bool, default False |
| 19 | `ENCODING` | Yes | `encoding` | str, default "ISO-8859-15" |
| 20 | `DELETE_EMPTYFILE` | Yes | `delete_empty_file` | bool, default False |
| F1 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | bool, default False (framework) |
| F2 | `LABEL` | Yes | `label` | str, default "" (framework) |

**Summary**: 20 of 20 unique parameters extracted (100%) + 2 framework params.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | From FLOW connector columns |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | |
| `key` | Yes | |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion via `_convert_date_pattern()` |
| `default` | No | Not extracted by base class `_parse_schema()` |

Schema direction: **Sink component** -- `schema["input"]` populated from FLOW, `schema["output"]` always empty (per D-55).

### 4.3 Expression Handling

String parameters (`filepath`, `streamname`, `row_separator`, `flushonrow_num`) preserve raw values which may contain context variable references (`context.varName`) or Java expressions. These are not evaluated by the converter -- they pass through to the engine for runtime resolution.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| ~~CONV-FOP-001~~ | ~~P1~~ | **FIXED** -- USE_EXISTING_DYNAMIC, DYNAMIC, USESTREAM, STREAMNAME now extracted |
| ~~CONV-FOP-002~~ | ~~P2~~ | **FIXED** -- Now uses `_build_component_dict` pattern with proper component wrapper |
| ~~CONV-FOP-003~~ | ~~P2~~ | **FIXED** -- FLUSHONROW_NUM now stored as str for expression support (was int) |
| ~~CONV-FOP-004~~ | ~~P2~~ | **FIXED** -- Config key renamed from flush_on_row to flushonrow per D-38 snake_case |
| ~~CONV-FOP-005~~ | ~~P2~~ | **FIXED** -- Conditional warnings replaced with per-feature needs_review entries |

### 4.5 Needs Review Entries

The converter emits 12 per-feature needs_review entries for engine gaps:

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | -- | FileOutputPositional engine file exists (468 lines) but is NOT registered in COMPONENT_REGISTRY -- component cannot be instantiated at runtime | engine_gap |
| 2 | `use_existing_dynamic` | Engine does not read this config key | engine_gap |
| 3 | `dynamic` | Engine does not read this config key | engine_gap |
| 4 | `usestream` | Engine does not read this config key | engine_gap |
| 5 | `streamname` | Engine does not read this config key | engine_gap |
| 6 | `encoding` | Engine defaults to 'utf-8', _java.xml defaults to 'ISO-8859-15' | engine_gap |
| 7 | `include_header` | Engine defaults to True, _java.xml defaults to false | engine_gap |
| 8 | `advanced_separator` | Engine does not read this config key | engine_gap |
| 9 | `thousands_separator` | Engine does not read this config key | engine_gap |
| 10 | `decimal_separator` | Engine does not read this config key | engine_gap |
| 11 | `use_byte` | Engine does not read this config key | engine_gap |
| 12 | `row_mode` | Engine does not read this config key | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

**CRITICAL: FileOutputPositional is NOT registered in the engine COMPONENT_REGISTRY** (`src/v1/engine/engine.py` lines 56-120). The class `FileOutputPositional` is imported in `src/v1/engine/components/file/__init__.py` (line 12) and exported in `__all__` (line 35), but the engine's `COMPONENT_REGISTRY` dict does not include either `'FileOutputPositional'` or `'tFileOutputPositional'` as keys. This means the engine cannot instantiate this component at runtime.

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | File writing | **Yes** | High | `_write_positional_file()` line 261 | Core functionality works correctly |
| 2 | Column formatting | **Yes** | High | `_format_data_row()` line 416 | Left/right alignment, padding, size control |
| 3 | Header writing | **Yes** | Medium | `_format_header_row()` line 384 | Default is True (Talend default is false) |
| 4 | Gzip compression | **Yes** | Medium | `_write_positional_file()` line 298 | Opens in binary mode for compression |
| 5 | Directory creation | **Yes** | High | `_write_positional_file()` line 291 | Uses `os.makedirs(exist_ok=True)` |
| 6 | Row separator | **Yes** | Medium | `_write_positional_file()` line 225 | Decodes escape sequences |
| 7 | Flush control | **Yes** | High | `_write_positional_file()` line 325 | Row-based flush buffering |
| 8 | Delete empty file | **Yes** | High | `_process()` line 236 | Checks file size after write |
| 9 | Encoding | **Partial** | Low | `_write_positional_file()` line 301 | Default is 'utf-8', should be 'ISO-8859-15' |
| 10 | Advanced separator | **No** | N/A | -- | No locale-aware number formatting |
| 11 | Use byte | **No** | N/A | -- | No byte-length column sizing |
| 12 | Row mode | **No** | N/A | -- | Always writes in row mode |
| 13 | Stream output | **No** | N/A | -- | No USESTREAM/STREAMNAME support |
| 14 | Dynamic schema | **No** | N/A | -- | No USE_EXISTING_DYNAMIC/DYNAMIC support |
| 15 | KEEP truncation | **Partial** | Low | `_format_data_row()` line 456 | Only 'C' (center) implemented; ALL/LEFT/MIDDLE/RIGHT missing |
| 16 | CENTER alignment | **No** | N/A | `_format_data_row()` line 461 | Only L and R supported; CENTER missing |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-FOP-001 | **P0** | **Engine NOT registered in COMPONENT_REGISTRY** -- despite 468-line implementation, FileOutputPositional cannot be instantiated by the engine. Neither `'FileOutputPositional'` nor `'tFileOutputPositional'` appear in the registry dict. |
| ENG-FOP-002 | **P1** | **Encoding default mismatch** -- engine defaults to `'utf-8'` (line 74 in constants), Talend _java.xml defaults to `"ISO-8859-15"`. Jobs relying on default encoding will produce differently-encoded files. |
| ENG-FOP-003 | **P1** | **Include header default mismatch** -- engine defaults to `True` (line 77 in constants), Talend _java.xml defaults to `false`. Jobs relying on default will get unexpected header rows. |
| ENG-FOP-004 | **P1** | **KEEP truncation incomplete** -- engine only implements 'C' keep mode (truncate to center). Talend supports ALL (no truncation), LEFT (keep left chars), MIDDLE (keep middle chars), RIGHT (keep right chars). |
| ENG-FOP-005 | **P2** | **VALID_KEEP_OPTIONS incorrect** -- engine defines `VALID_KEEP_OPTIONS = ['A', 'C']` (line 89) but Talend KEEP is a CLOSED_LIST with ALL/LEFT/MIDDLE/RIGHT values, not single-letter codes. |
| ENG-FOP-006 | **P2** | **No CENTER alignment** -- engine only supports 'L' and 'R' alignment. Talend ALIGN CLOSED_LIST includes LEFT/CENTER/RIGHT. |
| ENG-FOP-007 | **P3** | **die_on_error config key** -- engine reads `die_on_error` (line 184) but this param does not exist in _java.xml for tFileOutputPositional. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Set after execution |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | Rows successfully written |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | Rows that failed |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-FOP-001 | **P0** | `base_component.py:304` | **CROSS-CUTTING**: `_update_global_map()` crashes ALL components when globalMap is set. Affects all components inheriting from BaseComponent. |
| BUG-FOP-002 | **P1** | `file_output_positional.py:89` | `VALID_KEEP_OPTIONS = ['A', 'C']` -- incorrect values. Talend KEEP CLOSED_LIST is ALL/LEFT/MIDDLE/RIGHT, not single letters. Validation would reject valid Talend values. |
| BUG-FOP-003 | **P1** | `file_output_positional.py:285` | Append+compress mode logic: `mode = 'ab' if compress` ignores the `append` flag when compress is True -- always uses 'ab' (append binary) even for non-append compressed files. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-FOP-001 | **P2** | Engine uses `flush_on_row` / `flush_on_row_num` (with underscores); converter now uses `flushonrow` / `flushonrow_num` (no underscores) per D-38 snake_case of _java.xml name `FLUSHONROW`. Documented as engine_gap. |
| NAME-FOP-002 | **P2** | Engine uses `include_header` with default True; converter uses `include_header` with default False per _java.xml. Config key matches but default differs. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-FOP-001 | **P2** | "Use `logger.info()` not f-string" | Engine uses f-string interpolation in logger calls (e.g., line 169 `logger.info(f"[{self.id}]...")`) -- should use lazy `%s` formatting for performance |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

See Section 11 Risk Assessment for comprehensive security analysis.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | **Good** -- module-level `logger = logging.getLogger(__name__)` |
| Level usage | **Good** -- info for success, debug for verbose, error for failures |
| Sensitive data | **OK** -- file paths logged (may contain sensitive path info) |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | **Absent** -- uses generic ValueError for required field errors |
| Exception chaining | **Absent** -- `raise` re-raises without chaining |
| die_on_error handling | **Present** -- respects die_on_error flag for graceful vs hard failure (lines 184-195) |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | **Good** -- all methods have return type hints |
| Parameter types | **Good** -- all parameters typed |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-FOP-001 | **P1** | `iterrows()` row-by-row writing (line 317) -- O(n) Python loop instead of vectorized string formatting. For large DataFrames (100K+ rows), this is significantly slower than vectorized approaches. |
| PERF-FOP-002 | **P2** | Double schema lookup in `_format_data_row()` -- rebuilds `schema_map` dict on every row (line 432-433). Should be built once in the outer method. |
| PERF-FOP-003 | **P3** | String concatenation for line building (line 431) -- uses `line += val` in a loop instead of `''.join()` which is faster for many columns. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | **Not supported** -- entire DataFrame must fit in memory. No chunked writing. |
| Memory threshold | **Low risk** -- writes row-by-row, so output buffer is small. Input DataFrame is the bottleneck. |
| Large data handling | **Adequate** -- input is already loaded as DataFrame; writing is incremental via iterrows(). |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 48 | `tests/converters/talend_to_v1/components/test_file_output_positional.py` |
| Engine unit tests | 0 | None |
| Integration tests | Passing | `tests/converters/talend_to_v1/test_integration.py` |
| Regression guard | Passing | `tests/converters/talend_to_v1/test_converter_output_structure.py` |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-FOP-001 | **P2** | No engine unit tests for FileOutputPositional -- 468-line engine class has zero test coverage. Prevents Testing dimension from reaching Green. |

### 8.3 Recommended Test Cases

1. Engine unit test: write positional file with basic formats, verify output matches expected fixed-width layout
2. Engine unit test: append mode -- verify data is appended not overwritten
3. Engine unit test: gzip compression -- verify compressed output is valid gzip
4. Engine unit test: empty input with delete_empty_file=True -- verify file is deleted
5. Engine unit test: header row -- verify column names written with correct formatting
6. Engine unit test: various KEEP modes (if implemented) -- verify truncation behavior
7. Engine unit test: non-ASCII characters with different encodings

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 2 | **ENG-FOP-001** (not registered), **BUG-FOP-001** (globalMap crash, cross-cutting) |
| P1 | 6 | **ENG-FOP-002** (encoding default), **ENG-FOP-003** (include_header default), **ENG-FOP-004** (KEEP incomplete), **BUG-FOP-002** (VALID_KEEP_OPTIONS wrong), **BUG-FOP-003** (append+compress), **PERF-FOP-001** (iterrows) |
| P2 | 7 | ENG-FOP-005, ENG-FOP-006, NAME-FOP-001, NAME-FOP-002, STD-FOP-001, PERF-FOP-002, TEST-FOP-001 |
| P3 | 2 | ENG-FOP-007, PERF-FOP-003 |
| **Total** | **17** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | All fixed (5 resolved) |
| Engine (ENG) | 7 | ENG-FOP-001 through ENG-FOP-007 |
| Bug (BUG) | 3 | BUG-FOP-001 through BUG-FOP-003 |
| Naming (NAME) | 2 | NAME-FOP-001, NAME-FOP-002 |
| Standards (STD) | 1 | STD-FOP-001 |
| Performance (PERF) | 3 | PERF-FOP-001 through PERF-FOP-003 |
| Testing (TEST) | 1 | TEST-FOP-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap is set |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Register FileOutputPositional in COMPONENT_REGISTRY** (ENG-FOP-001, P0) -- add `'FileOutputPositional': FileOutputPositional, 'tFileOutputPositional': FileOutputPositional` entries
2. **Fix `_update_global_map()` crash** (BUG-FOP-001, P0, cross-cutting) -- affects all components

### Short-term (Hardening)

1. Fix encoding default from 'utf-8' to 'ISO-8859-15' (ENG-FOP-002, P1)
2. Fix include_header default from True to False (ENG-FOP-003, P1)
3. Implement all KEEP modes: ALL, LEFT, MIDDLE, RIGHT (ENG-FOP-004, P1)
4. Fix VALID_KEEP_OPTIONS to match Talend CLOSED_LIST (BUG-FOP-002, P1)
5. Fix append+compress mode logic (BUG-FOP-003, P1)
6. Optimize row writing for large DataFrames (PERF-FOP-001, P1)

### Long-term (Optimization)

1. Add CENTER alignment support (ENG-FOP-006, P2)
2. Add engine unit tests (TEST-FOP-001, P2)
3. Fix schema_map rebuild per row (PERF-FOP-002, P2)
4. Remove die_on_error from engine (ENG-FOP-007, P3)

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| **Component not instantiable** -- FileOutputPositional is not registered in COMPONENT_REGISTRY. Any job using tFileOutputPositional will fail at runtime | High | High | Register the component immediately (ENG-FOP-001). This is the highest-priority fix. |
| **Encoding mismatch** -- engine defaults UTF-8, Talend defaults ISO-8859-15. Silent data corruption for non-ASCII characters | High | Medium | Fix encoding default to match _java.xml. Always specify encoding explicitly in job configs. |
| **File path traversal** -- FILENAME accepts arbitrary paths including `../` sequences | Medium | High | Validate/sanitize file paths before writing. Restrict to allowed output directories. |
| **Padding character injection** -- PADDING_CHAR from FORMATS TABLE is user-controlled. Malicious padding chars could corrupt downstream parsers | Low | Medium | Validate PADDING_CHAR is a single printable character. Document expected values in job config validation. |
| **Fixed-width data truncation** -- KEEP=ALL means no truncation, potentially producing lines wider than expected. Downstream parsers may fail | Medium | Medium | Validate output line lengths. Use KEEP=LEFT or KEEP=RIGHT for strict width enforcement. |
| **Gzip compression with append** -- engine mode logic uses 'ab' for all compressed files regardless of append flag. May produce invalid gzip files when append=false | Medium | High | Fix append+compress mode logic (BUG-FOP-003). Test gzip output validity. |
| **Empty file deletion race condition** -- delete_empty_file checks file size after write. Concurrent access could delete non-empty files | Low | Medium | Use file locking or atomic write patterns for concurrent scenarios. |

### High-Risk Job Patterns

1. **Jobs using tFileOutputPositional at all** -- component cannot be instantiated due to registration gap
2. **Jobs relying on default encoding** -- will get UTF-8 instead of ISO-8859-15, corrupting Western European characters
3. **Jobs using KEEP=LEFT/MIDDLE/RIGHT** -- only 'C' (center) is implemented in engine
4. **Jobs using CENTER alignment** -- not implemented
5. **Jobs using gzip compression without append** -- may produce invalid gzip headers due to 'ab' mode

### Safe Usage Patterns

1. **Note**: No safe usage pattern exists until ENG-FOP-001 is fixed (registration gap)
2. **Explicitly specify encoding** -- never rely on default (use "ISO-8859-15" or "UTF-8" per data requirements)
3. **Use KEEP=ALL or KEEP=LEFT** -- safest truncation modes for most use cases
4. **Use LEFT or RIGHT alignment only** -- CENTER is not implemented
5. **Avoid gzip compression for append mode** -- mode logic has bugs

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Official Talend docs | [tFileOutputPositional Standard Properties (7.3)](https://help.qlik.com/talend/en-US/components/7.3/positional/tfileoutputpositional-standard-properties) | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | [tFileOutputPositional_java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileOutputPositional/tFileOutputPositional_java.xml) | Component definition XML (source of truth) |
| Engine source | `src/v1/engine/components/file/file_output_positional.py` | Feature parity analysis (468 lines) |
| Engine registry | `src/v1/engine/engine.py` lines 56-120 | Registration gap verification |
| Converter source | `src/converters/talend_to_v1/components/file/file_output_positional.py` | Converter audit (178 lines) |
| Converter tests | `tests/converters/talend_to_v1/components/test_file_output_positional.py` | Test coverage analysis (48 tests) |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap is set |

## Appendix C: Engine Registration Gap Analysis

The `FileOutputPositional` class is fully implemented (468 lines) in `src/v1/engine/components/file/file_output_positional.py`. It is:

- **Imported** in `src/v1/engine/components/file/__init__.py` (line 12)
- **Exported** in `__all__` list (line 35)
- **NOT registered** in `ETLEngine.COMPONENT_REGISTRY` in `src/v1/engine/engine.py`

This appears to be an oversight during development. The class follows the same pattern as all other file components (inherits from BaseComponent, implements `_process()` and `_validate_config()`). Adding two lines to COMPONENT_REGISTRY would enable it:
```python
'FileOutputPositional': FileOutputPositional,
'tFileOutputPositional': FileOutputPositional,
```

Note: The import in engine.py would also need to be added since only `file/__init__.py` currently imports the class.

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after Phase 10 Plan 09 converter standardization*
