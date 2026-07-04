# Audit Report: tFileOutputPositional / FileOutputPositional

> **Audited**: 2026-04-04
> **Updated**: 2026-06-14 (Phase 7.2-02: FULL ENGINE REWRITE -- all P0/P1/P2 engine and code-quality issues fixed; 44 engine unit tests added)
> **Reconciled**: 2026-05-11
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
| **Registry Aliases** | `FileOutputPositional`, `tFileOutputPositional` -- **FIXED in Phase 7.2-02** (was NOT registered) |
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
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 20 unique params + 2 framework params extracted; FORMATS 5-field TABLE parser (stride-5); `_build_component_dict` pattern; sink schema (input populated, output empty); 11 per-feature needs_review entries |
| Engine Feature Parity | **G** | 0 | 0 | 0 | 1 | **Fixed (7.2-02)**: REGISTRY registration (ENG-FOP-001), encoding default ISO-8859-15 (ENG-FOP-002), include_header default False (ENG-FOP-003), KEEP ALL/LEFT/MIDDLE/RIGHT (ENG-FOP-004), VALID_KEEP_OPTIONS fixed (ENG-FOP-005), CENTER alignment (ENG-FOP-006). Remaining P3: die_on_error phantom param |
| Code Quality | **G** | 1 | 0 | 0 | 0 | Only open: XCUT-001 cross-cutting base class crash (P0). **Fixed (7.2-02)**: BUG-FOP-002 (VALID_KEEP_OPTIONS), BUG-FOP-003 (append+compress mode), NAME-FOP-001, NAME-FOP-002, STD-FOP-001 (f-strings) |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | **Fixed (7.2-02)**: PERF-FOP-001 (iterrows->vectorized), PERF-FOP-002 (schema_map built once), PERF-FOP-003 (string +=->Series + operator). Remaining P3: batch-only, no streaming |
| Testing | **G** | 0 | 0 | 0 | 0 | 48 converter unit tests; **44 engine unit tests across 13 test classes added in Phase 7.2-02**; integration + regression guard passing |

**Overall: Green -- Converter fully standardized; engine fully rewritten per MANUAL_COMPONENT_AUTHORING.md; all P0/P1/P2 issues resolved; 44 engine unit tests passing. Only open: XCUT-001 cross-cutting base class crash (P0).**

**Top Actions:**

1. Fix `_update_global_map()` crash in base class (XCUT-001, P0, cross-cutting)

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
| 1 | `use_existing_dynamic` | Engine does not implement dynamic schema source | engine_gap |
| 2 | `dynamic` | Engine does not implement dynamic schema source | engine_gap |
| 3 | `usestream` | Engine does not implement stream output | engine_gap |
| 4 | `streamname` | Engine does not implement stream output | engine_gap |
| 5 | `advanced_separator` | Engine does not apply locale-aware number formatting on write | engine_gap |
| 6 | `thousands_separator` | Engine does not apply locale-aware number formatting on write | engine_gap |
| 7 | `decimal_separator` | Engine does not apply locale-aware number formatting on write | engine_gap |
| 8 | `use_byte` | Engine measures column widths in characters, not bytes | engine_gap |
| 9 | `row_mode` | Engine always writes in buffered row mode | engine_gap |
| 10 | `flushonrow` / `flushonrow_num` | Engine implements flush-on-row via both `flushonrow`/`flushonrow_num` and `flush_on_row`/`flush_on_row_num` aliases | info |
| 11 | `encoding` | Engine default is now 'ISO-8859-15' matching _java.xml -- **FIXED** | resolved |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

**CRITICAL: FileOutputPositional is NOT registered in the engine COMPONENT_REGISTRY** (`src/v1/engine/engine.py` lines 56-120). The class `FileOutputPositional` is imported in `src/v1/engine/components/file/__init__.py` (line 12) and exported in `__all__` (line 35), but the engine's `COMPONENT_REGISTRY` dict does not include either `'FileOutputPositional'` or `'tFileOutputPositional'` as keys. This means the engine cannot instantiate this component at runtime.

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | File writing | **Yes** | High | `_write_positional_file()` | Core functionality works correctly |
| 2 | Column formatting | **Yes** | High | `_format_columns()` | Vectorized per-column Series formatting |
| 3 | Header writing | **Yes** | High | `_format_header_row()` | Default is now False (matches Talend). **Fixed (7.2-02)** |
| 4 | Gzip compression | **Yes** | High | `_write_positional_file()` | Binary/text modes correctly selected. **Fixed (7.2-02 BUG-FOP-003)** |
| 5 | Directory creation | **Yes** | High | `_write_positional_file()` | Uses `os.makedirs(exist_ok=True)` |
| 6 | Row separator | **Yes** | Medium | `_write_positional_file()` | Decodes escape sequences |
| 7 | Flush control | **Yes** | High | `_write_positional_file()` | Both `flushonrow`/`flush_on_row` aliases supported |
| 8 | Delete empty file | **Yes** | High | `_process()` | Checks empty input DataFrame |
| 9 | Encoding | **Yes** | High | `_write_positional_file()` | Default is now 'ISO-8859-15'. **Fixed (7.2-02)** |
| 10 | KEEP ALL/LEFT/MIDDLE/RIGHT | **Yes** | High | `_format_columns()` | All four modes implemented. **Fixed (7.2-02 ENG-FOP-004)** |
| 11 | CENTER alignment | **Yes** | High | `_format_columns()` | CENTER/CENTRE mapped via _ALIGN_ALIAS. **Fixed (7.2-02 ENG-FOP-006)** |
| 12 | Advanced separator | **No** | N/A | -- | No locale-aware number formatting on write |
| 13 | Use byte | **No** | N/A | -- | No byte-length column sizing |
| 14 | Row mode | **No** | N/A | -- | Always writes in buffered row mode |
| 15 | Stream output | **No** | N/A | -- | No USESTREAM/STREAMNAME support |
| 16 | Dynamic schema | **No** | N/A | -- | No USE_EXISTING_DYNAMIC/DYNAMIC support |

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
| BUG-FOP-002 | **P1 -- FIXED** | ~~`file_output_positional.py:89`~~ | ~~`VALID_KEEP_OPTIONS = ['A', 'C']` -- incorrect values.~~ **Fixed in Phase 7.2-02: VALID_KEEP_OPTIONS = ['ALL', 'LEFT', 'MIDDLE', 'RIGHT']** |
| BUG-FOP-003 | **P1 -- FIXED** | ~~`file_output_positional.py:285`~~ | ~~Append+compress mode logic: `mode = 'ab' if compress` ignores the `append` flag when compress is True.~~ **Fixed in Phase 7.2-02: `mode = ('ab' if append else 'wb') if compress else ('a' if append else 'w')`** |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-FOP-001 | **P2 -- FIXED** | ~~Engine uses `flush_on_row` / `flush_on_row_num` (with underscores); converter uses `flushonrow` / `flushonrow_num` (no underscores)~~ **Fixed in Phase 7.2-02: engine now accepts both aliases using explicit `is not None` checks** |
| NAME-FOP-002 | **P2 -- FIXED** | ~~Engine uses `include_header` with default True; converter uses `include_header` with default False per _java.xml~~ **Fixed in Phase 7.2-02: DEFAULT_INCLUDE_HEADER = False** |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-FOP-001 | **P2 -- FIXED** | "Use `logger.info()` not f-string" | ~~Engine uses f-string interpolation in logger calls~~ **Fixed in Phase 7.2-02: all logger calls use %s lazy format** |

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
| Custom exceptions | **Good** -- uses ConfigurationError, FileOperationError, ComponentExecutionError throughout. **Fixed (7.2-02)** |
| Exception chaining | **Good** -- `raise XxxError(...) from e` throughout |
| die_on_error handling | **Present** -- respects die_on_error flag for graceful vs hard failure |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | **Good** -- all methods have return type hints |
| Parameter types | **Good** -- all parameters typed |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-FOP-001 | **P1 -- FIXED** | ~~`iterrows()` row-by-row writing~~ **Fixed in Phase 7.2-02: vectorized `_format_columns()` applies pandas str operations per column; `_build_row_strings()` uses Series + operator** |
| PERF-FOP-002 | **P2 -- FIXED** | ~~Double schema lookup in `_format_data_row()` -- rebuilds `schema_map` dict on every row~~ **Fixed in Phase 7.2-02: schema_map built once before the write loop** |
| PERF-FOP-003 | **P3 -- FIXED** | ~~String concatenation for line building -- uses `line += val` in a loop~~ **Fixed in Phase 7.2-02: `_build_row_strings()` uses Series concatenation and `.tolist()`** |
| PERF-FOP-004 | **P3** | No streaming mode -- entire DataFrame must be in memory for vectorized formatting |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | **Not supported** -- entire DataFrame formatted at once. No chunked writing. |
| Memory threshold | **Medium** -- vectorized formatting creates intermediate Series objects proportional to DataFrame size. |
| Large data handling | **Good for typical batch sizes** -- vectorized approach is fast; may need chunking for >1M rows. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 48 | `tests/converters/talend_to_v1/components/test_file_output_positional.py` |
| Engine unit tests | **44** | `tests/v1/engine/components/file/test_file_output_positional.py` (13 test classes; added Phase 7.2-02) |
| Engine coverage lift | Added | Phase 14-08 lifted module to 99.6% (COV-FOP-001), commit 5860d4d |
| Integration tests | Passing | `tests/converters/talend_to_v1/test_integration.py` |
| Regression guard | Passing | `tests/converters/talend_to_v1/test_converter_output_structure.py` |

**Phase 14 floor:** Module meets >= 95% per-module line coverage floor. [RESOLVED in Phase 14-08, commit 5860d4d (COV-FOP-001)]

### 8.2 Engine Test Classes (Phase 7.2-02)

| # | Class | Tests | Covers |
| --- | ------- | ------- | -------- |
| 1 | `TestRegistration` | 2 | REGISTRY.get("FileOutputPositional") and REGISTRY.get("tFileOutputPositional") |
| 2 | `TestValidateConfig` | 7 | Structural ConfigurationError for missing filepath/formats/schema_column/size |
| 3 | `TestProcessContentValidation` | 5 | size=0, bad size, invalid align, invalid keep, flushonrow_num=0 raise ConfigurationError in _process() |
| 4 | `TestBasicWrite` | 3 | Two rows no header, passthrough returns original df, creates directory |
| 5 | `TestHeaderRow` | 2 | Default no header, include_header=True writes names |
| 6 | `TestAppendMode` | 2 | Append adds rows, no-append overwrites |
| 7 | `TestEncoding` | 2 | Default is ISO-8859-15, explicit UTF-8 works |
| 8 | `TestAlignment` | 5 | L, R, C, full-word LEFT, full-word CENTER |
| 9 | `TestKeepModes` | 7 | ALL overflow, LEFT first N, RIGHT last N, MIDDLE center N, no truncation when fits, legacy 'A'->ALL, legacy 'C'->LEFT |
| 10 | `TestGzipCompression` | 3 | Valid gzip, compress without append overwrites (BUG-FOP-003), compress with append appends |
| 11 | `TestDeleteEmptyFile` | 2 | Empty input deletes existing, without flag doesn't delete |
| 12 | `TestFlushOnRowAliases` | 2 | flushonrow and flush_on_row both work |
| 13 | `TestStatistics` | 2 | comp.stats["NB_LINE"] checks after _process() |

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **BUG-FOP-001** (globalMap crash, cross-cutting) |
| P1 | 0 | ~~ENG-FOP-001 through ENG-FOP-004~~ all fixed; ~~BUG-FOP-002, BUG-FOP-003~~ all fixed; ~~PERF-FOP-001~~ fixed |
| P2 | 0 | ~~ENG-FOP-005, ENG-FOP-006, NAME-FOP-001, NAME-FOP-002, STD-FOP-001, PERF-FOP-002, TEST-FOP-001~~ all fixed |
| P3 | 2 | ENG-FOP-007 (die_on_error phantom), PERF-FOP-004 (batch-only) |
| **Total (open)** | **3** | |
| **Fixed (Phase 7.2-02)** | **14** | ENG-FOP-001..006, BUG-FOP-002..003, NAME-FOP-001..002, STD-FOP-001, PERF-FOP-001..003, TEST-FOP-001 |

### By Category (remaining open)

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Cross-cutting (XCUT) | 1 | BUG-FOP-001 (base_component.py crash) |
| Engine (ENG) | 1 | ENG-FOP-007 (phantom die_on_error) |
| Performance (PERF) | 1 | PERF-FOP-004 (no streaming) |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap is set |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` crash** (BUG-FOP-001, P0, cross-cutting) -- affects all components

### Long-term (Optimization)

1. Add streaming/chunked write support for DataFrames > 1M rows (PERF-FOP-004, P3)
2. Remove phantom die_on_error config key (ENG-FOP-007, P3)
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

~~This appears to be an oversight during development. The class follows the same pattern as all other file components (inherits from BaseComponent, implements `_process()` and `_validate_config()`). Adding two lines to COMPONENT_REGISTRY would enable it:~~
~~```python~~
~~'FileOutputPositional': FileOutputPositional,~~
~~'tFileOutputPositional': FileOutputPositional,~~
~~```~~
~~Note: The import in engine.py would also need to be added since only `file/__init__.py` currently imports the class.~~

**[RESOLVED in Phase 7.2-02]**: `@REGISTRY.register('FileOutputPositional', 'tFileOutputPositional')` decorator added to the engine class. Registration gap closed. The static COMPONENT_REGISTRY dict no longer exists (replaced by decorator-based REGISTRY in Phase 15-02).

Additionally, Phase 14-08 commit 5860d4d lifted the module to 99.6% line coverage (COV-FOP-001) -- 9 test classes, 43 of 44 originally-missed lines covered.

---

*Report generated: 2026-04-04*
*Last updated: 2026-05-11 after Phase 15.1 reconciliation -- Phase 7.2-02 registration fix confirmed; Phase 14-08 coverage lift commit 5860d4d cited*
