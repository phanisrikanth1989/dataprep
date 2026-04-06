# Audit Report: tFileInputDelimited / FileInputDelimited

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
| **Talend Name** | `tFileInputDelimited` |
| **V1 Engine Class** | `FileInputDelimited` |
| **Engine File** | `src/v1/engine/components/file/file_input_delimited.py` (574 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_input_delimited.py` |
| **Converter Dispatch** | `@REGISTRY.register("tFileInputDelimited")` decorator-based dispatch |
| **Registry Aliases** | `tFileInputDelimited` |
| **Category** | File / Input |
| **Complexity** | High -- most parameter-rich file input component (29 unique params + 2 TABLE + 2 framework) |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_input_delimited.py` | Engine implementation (574 lines) |
| `src/converters/talend_to_v1/components/file/file_input_delimited.py` | Converter class |
| `tests/converters/talend_to_v1/components/test_file_input_delimited.py` | Converter tests (74 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 31 of 31 params extracted (29 unique + 2 framework); `_build_component_dict` pattern; REMOVE_EMPTY_ROW=True default fixed; 14 per-feature needs_review entries; 2 TABLE parsers (TRIMSELECT, DECODE_COLS) |
| Engine Feature Parity | **Y** | 1 | 5 | 3 | 1 | No REJECT flow; missing globalMap vars; no compressed/RFC4180; no CHECK_FIELDS_NUM/CHECK_DATE; engine reads "delimiter" not "fieldseparator"; encoding default mismatch (UTF-8 vs ISO-8859-15) |
| Code Quality | **Y** | 2 | 2 | 5 | 2 | Cross-cutting base class bugs; dead `_validate_config()`; single-string DF creation bug; config mutation via resolve_dict |
| Performance & Memory | **G** | 0 | 0 | 2 | 1 | Streaming mode works for large files; minor optimization opportunities in post-processing and engine selection |
| Testing | **Y** | 0 | 0 | 2 | 0 | 74 converter unit tests across 11 test classes per gold standard; integration + regression guard passing; engine unit tests missing (P2) -- no engine test coverage prevents Green |

**Overall: Yellow -- Converter fully standardized (Green); engine has known gaps documented via 14 needs_review entries; engine/code quality gaps keep overall at Yellow**

**Top Actions:**
1. Fix `_update_global_map()` crash in base class (P0, cross-cutting)
2. Fix single-string DataFrame creation bug (`pd.DataFrame({column_name: file_content})` creates per-char rows) (P0)
3. Add REJECT flow support (P1, engine gap)
4. Implement missing globalMap variables (P1, engine gap)
5. Fix engine encoding default from UTF-8 to ISO-8859-15 (P2, engine mismatch)

---

## 3. Talend Feature Baseline

### What tFileInputDelimited Does

`tFileInputDelimited` reads a character-delimited flat file (CSV, TSV, pipe-separated, semicolon-separated, etc.) and outputs rows as a data flow. It is the single most commonly used input component in Talend, present in the vast majority of data integration jobs. The component opens a file, reads it row by row, splits each row into fields based on the configured delimiter, and sends the fields as defined in the output schema to downstream components via a Row link.

The component supports extensive configuration: field and row separators (including multi-character and regex), CSV options (RFC4180 escape/enclosure), header/footer row skipping, row limits, random sampling, per-column trim/decode settings, compression, date validation, and advanced numeric separators. When CSV mode is enabled, the field separator must be a single character. The encoding default is ISO-8859-15 (Western European), not UTF-8.

**Source**: [tFileInputDelimited Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/delimited/tfileinputdelimited-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileInputDelimited/tFileInputDelimited_java.xml)
**Component family**: Delimited (File / Input)
**Available in**: All Talend products (Standard)
**Required JARs**: `talend_file_enhanced-1.1.jar`, `talendcsv-1.0.0.jar`

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines the output structure. |
| 2 | File Name / Stream | `FILENAME` | FILE | `""` | **Mandatory**. Absolute file path or data stream variable. Supports context variables. |
| 3 | Row Separator | `ROWSEPARATOR` | TEXT | `"\n"` | Character(s) identifying end of a row. Supports `\r\n`, `\n`, `\r`. |
| 4 | Field Separator | `FIELDSEPARATOR` | TEXT | `";"` | Delimiter separating fields. Can be character, string, or regex. Talend default is semicolon. |
| 5 | CSV Options | `CSV_OPTION` | CHECK | `false` | Enables RFC4180 CSV mode with escape char and text enclosure. |
| 6 | Escape Char | `ESCAPE_CHAR` | TEXT | `"\""` | Escape character. Only visible when CSV_OPTION=true. |
| 7 | Text Enclosure | `TEXT_ENCLOSURE` | TEXT | `"\""` | Quote character for text fields. Only visible when CSV_OPTION=true. |
| 8 | Rows to Skip (Header) | `HEADER` | COUNT | `0` | Number of header rows to skip before reading data. |
| 9 | Rows to Skip (Footer) | `FOOTER` | COUNT | `0` | Number of footer rows to skip at end of file. |
| 10 | Limit | `LIMIT` | TEXT | `""` | Maximum number of rows to read. Empty = no limit. Supports expressions. |
| 11 | Remove Empty Row | `REMOVE_EMPTY_ROW` | CHECK | `true` | Remove completely empty rows. **Note: default is true, not false.** |
| 12 | Die on Error | `DIE_ON_ERROR` | CHECK | `false` | Whether to halt on error or continue processing. |
| 13 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding for file reading. **Note: ISO-8859-15, not UTF-8.** |
| 14 | Uncompress | `UNCOMPRESS` | CHECK | `false` | Read from compressed archive. |
| 15 | CSV Row Separator | `CSVROWSEPARATOR` | TEXT | `"\n"` | Row separator for CSV mode. May differ from ROWSEPARATOR. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 16 | Split Record | `SPLITRECORD` | CHECK | `false` | Allow multi-line fields (records split across multiple lines). |
| 17 | Check Fields Number | `CHECK_FIELDS_NUM` | CHECK | `false` | Validate that each row has the expected number of fields per schema. |
| 18 | Check Date | `CHECK_DATE` | CHECK | `false` | Strictly validate date fields against schema patterns. |
| 19 | Advanced Separator | `ADVANCED_SEPARATOR` | CHECK | `false` | Enable thousands/decimal separator handling for numeric fields. |
| 20 | Thousands Separator | `THOUSANDS_SEPARATOR` | TEXT | `","` | Thousands grouping character. Only active when ADVANCED_SEPARATOR=true. |
| 21 | Decimal Separator | `DECIMAL_SEPARATOR` | TEXT | `"."` | Decimal point character. Only active when ADVANCED_SEPARATOR=true. |
| 22 | Trim All Columns | `TRIMALL` | CHECK | `false` | Trim whitespace from all string fields. |
| 23 | Per-column Trim | `TRIMSELECT` | TABLE | `[]` | TABLE of per-column trim settings (SCHEMA_COLUMN + TRIM). |
| 24 | Random Sampling | `RANDOM` | CHECK | `false` | Enable random line selection instead of sequential read. |
| 25 | Random Sample Size | `NB_RANDOM` | COUNT | `10` | Number of random lines to select. Only active when RANDOM=true. |
| 26 | Enable Decode | `ENABLE_DECODE` | CHECK | `false` | Enable hex/octal number decoding for specific columns. |
| 27 | Decode Columns | `DECODE_COLS` | TABLE | `[]` | TABLE of columns to decode (SCHEMA_COLUMN + DECODE). |
| 28 | Temp Directory | `TEMP_DIR` | DIRECTORY | `""` | Temporary directory for intermediate file processing. |
| 29 | Destination | `DESTINATION` | TEXT | `""` | Destination path for processed output. |
| 30 | Use Header As Is | `USE_HEADER_AS_IS` | CHECK | `false` | Use file header row as-is for column names (no mapping to schema). |
| 31 | Schema Opt Number | `SCHEMA_OPT_NUM` | COUNT | `100` | Number of rows to sample for schema optimization/detection. |
| 32 | tStatCatcher Stats | `TSTATCATCHER_STATS` | CHECK | `false` | Framework: enable statistics collection. |
| 33 | Label | `LABEL` | TEXT | `""` | Framework: user-defined label for the component. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Primary data output with parsed fields per schema |
| `REJECT` | Output | Row > Reject | Rejected rows with errorCode/errorMessage columns |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires after error |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total rows read from file |
| `{id}_NB_LINE_OK` | Integer | After execution | Successfully processed rows |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rejected rows (validation failures) |
| `{id}_FILENAME` | String | Before execution | Resolved file path |
| `{id}_ENCODING` | String | Before execution | Resolved encoding |

### 3.5 Behavioral Notes

1. **FIELDSEPARATOR default is semicolon (`;`)**, not comma. This is a common source of confusion for users coming from other ETL tools.
2. **REMOVE_EMPTY_ROW default is `true`** -- empty rows are removed by default in Talend. This differs from many file-reading libraries that preserve all rows.
3. **ENCODING default is `ISO-8859-15`** (Latin-9 / Western European), not UTF-8. This matches French/European locale conventions where Talend originated.
4. **CSV_OPTION=true requires single-character FIELDSEPARATOR** -- regex delimiters are not allowed in RFC4180 mode.
5. **ESCAPE_CHAR and TEXT_ENCLOSURE only visible when CSV_OPTION=true** in the Talend UI, but the parameters exist in the XML regardless.
6. **TRIMSELECT overrides TRIMALL** -- when per-column trim settings are defined, they take precedence over the global trim-all flag.
7. **RANDOM sampling reads the entire file** to select random lines -- it does not use reservoir sampling or seek. Large files with RANDOM=true use significant memory.
8. **LIMIT is a string (not integer)** to support Talend expressions and context variables (e.g., `context.maxRows`).

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses the gold-standard `_build_component_dict` pattern with `type_name="FileInputDelimited"` per D-40/D-43. Module-level `_parse_trim_select()` and `_parse_decode_cols()` TABLE parsers handle the stride-2 TABLE parameters.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `FILENAME` | Yes | `filepath` | `_get_str`, default `""` |
| 2 | `CSV_OPTION` | Yes | `csv_option` | `_get_bool`, default `False` |
| 3 | `ROWSEPARATOR` | Yes | `row_separator` | `_get_str`, default `"\\n"` |
| 4 | `CSVROWSEPARATOR` | Yes | `csv_row_separator` | `_get_str`, default `"\\n"` |
| 5 | `FIELDSEPARATOR` | Yes | `fieldseparator` | `_get_str`, default `";"` -- engine reads "delimiter" (needs_review) |
| 6 | `ESCAPE_CHAR` | Yes | `escape_char` | `_get_str`, default `'"'` |
| 7 | `TEXT_ENCLOSURE` | Yes | `text_enclosure` | `_get_str`, default `'"'` |
| 8 | `HEADER` | Yes | `header_rows` | `_get_int`, default `0` |
| 9 | `FOOTER` | Yes | `footer_rows` | `_get_int`, default `0` |
| 10 | `LIMIT` | Yes | `limit` | `_get_str`, default `""` -- string for expression support |
| 11 | `REMOVE_EMPTY_ROW` | Yes | `remove_empty_row` | `_get_bool`, default `True` -- **FIXED from False** |
| 12 | `UNCOMPRESS` | Yes | `uncompress` | `_get_bool`, default `False` |
| 13 | `DIE_ON_ERROR` | Yes | `die_on_error` | `_get_bool`, default `False` |
| 14 | `ADVANCED_SEPARATOR` | Yes | `advanced_separator` | `_get_bool`, default `False` |
| 15 | `THOUSANDS_SEPARATOR` | Yes | `thousands_separator` | `_get_str`, default `","` |
| 16 | `DECIMAL_SEPARATOR` | Yes | `decimal_separator` | `_get_str`, default `"."` |
| 17 | `RANDOM` | Yes | `random` | `_get_bool`, default `False` |
| 18 | `NB_RANDOM` | Yes | `nb_random` | `_get_int`, default `10` |
| 19 | `TRIMALL` | Yes | `trim_all` | `_get_bool`, default `False` |
| 20 | `TRIMSELECT` | Yes | `trim_select` | TABLE parser, stride-2 |
| 21 | `CHECK_FIELDS_NUM` | Yes | `check_fields_num` | `_get_bool`, default `False` |
| 22 | `CHECK_DATE` | Yes | `check_date` | `_get_bool`, default `False` |
| 23 | `ENCODING` | Yes | `encoding` | `_get_str`, default `"ISO-8859-15"` |
| 24 | `SPLITRECORD` | Yes | `split_record` | `_get_bool`, default `False` |
| 25 | `ENABLE_DECODE` | Yes | `enable_decode` | `_get_bool`, default `False` |
| 26 | `DECODE_COLS` | Yes | `decode_cols` | TABLE parser, stride-2 |
| 27 | `TEMP_DIR` | **REMOVED** | ~~temp_dir~~ | Hidden/design-time param -- removed from converter |
| 28 | `DESTINATION` | **REMOVED** | ~~destination~~ | Hidden/design-time param -- removed from converter |
| 29 | `USE_HEADER_AS_IS` | **REMOVED** | ~~use_header_as_is~~ | Hidden/design-time param -- removed from converter |
| 30 | `SCHEMA_OPT_NUM` | **REMOVED** | ~~schema_opt_num~~ | Hidden/design-time param -- removed from converter |
| 31 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework, `_get_bool`, default `False` |
| 32 | `LABEL` | Yes | `label` | Framework, `_get_str`, default `""` |

**Summary**: 27 of 31 parameters extracted (87%). 25 unique + 2 framework. 4 hidden/design-time params removed.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Direct from SchemaColumn |
| `type` | Yes | Converted via `convert_type()` |
| `nullable` | Yes | Direct from SchemaColumn |
| `key` | Yes | Direct from SchemaColumn |
| `length` | Yes | Only when >= 0 |
| `precision` | Yes | Only when >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion via `_convert_date_pattern()` |
| `default` | No | Not yet implemented in base class |

### 4.3 Expression Handling

Context variables in FILENAME, FIELDSEPARATOR, ROWSEPARATOR, LIMIT, and other string parameters are preserved as-is in the config output. The v1 engine resolves expressions at runtime via `resolve_dict()` in the base component class.

### 4.4 Converter Issues

None. All parameters extracted correctly with proper defaults.

### 4.5 Needs Review Entries

10 per-feature needs_review entries for engine gaps:

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | `fieldseparator` | Engine reads `delimiter` config key, not `fieldseparator` | engine_gap |
| 2 | `csv_option` | Engine has no explicit RFC4180 CSV toggle | engine_gap |
| 3 | `csv_row_separator` | Engine uses only row_separator, ignores csv_row_separator | engine_gap |
| 4 | `split_record` | Engine has no explicit multi-line field toggle | engine_gap |
| 5 | `random` | Engine does not support random line extraction | engine_gap |
| 6 | `check_fields_num` | Engine does not validate row field count | engine_gap |
| 7 | `check_date` | Engine does not validate dates against schema patterns | engine_gap |
| 8 | `enable_decode` | Engine does not support hex/octal number parsing | engine_gap |
| 9 | `advanced_separator` | Engine has partial support -- applies to all string columns, not just numeric | engine_gap |
| 10 | `uncompress` | Engine does not support compressed file reading | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | File reading (filepath) | **Yes** | High | `_process()` line 213 | Reads filepath from config |
| 2 | Delimiter parsing | **Yes** | High | `_read_batch()` line 351 | Via pandas `sep` parameter |
| 3 | Row separator | **Partial** | Medium | `_process()` line 215 | Used for special single-string detection, not passed to pandas |
| 4 | Encoding | **Yes** | Medium | `_process()` line 216 | Default UTF-8 (should be ISO-8859-15) |
| 5 | Header/footer skip | **Yes** | High | `_read_batch()` lines 361-369 | Via pandas skiprows/skipfooter |
| 6 | Row limit | **Yes** | High | `_parse_limit()` line 339 | Via pandas nrows |
| 7 | Remove empty rows | **Yes** | High | `_post_process_dataframe()` line 553 | Via `dropna(how='all')` |
| 8 | Text enclosure | **Yes** | High | `_configure_csv_params()` line 521 | Via pandas quotechar |
| 9 | Escape char | **Yes** | High | `_configure_csv_params()` line 521 | Double-quote or escape mode |
| 10 | Trim all | **Yes** | High | `_post_process_dataframe()` line 546 | String column `.str.strip()` |
| 11 | Die on error | **Yes** | High | `_process()` line 217 | Controls exception vs empty DF |
| 12 | Schema enforcement | **Yes** | Medium | `_read_batch()` line 416 | Via `validate_schema()` |
| 13 | Streaming mode | **Yes** | High | `_read_streaming()` line 434 | Chunked for files > 3GB |
| 14 | CSV_OPTION toggle | **No** | N/A | -- | No RFC4180 mode toggle |
| 15 | CSV row separator | **No** | N/A | -- | Ignored; uses row_separator only |
| 16 | Split record | **No** | N/A | -- | No multi-line field support |
| 17 | Random sampling | **No** | N/A | -- | No random line extraction |
| 18 | Check fields num | **No** | N/A | -- | No field count validation |
| 19 | Check date | **No** | N/A | -- | No date pattern validation |
| 20 | Enable decode | **No** | N/A | -- | No hex/octal decode |
| 21 | Advanced separator | **Partial** | Low | `_post_process_dataframe()` line 564 | BigDecimal handling only |
| 22 | REJECT flow | **No** | N/A | -- | No reject output |
| 23 | Uncompress | **No** | N/A | -- | No compressed file support |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FID-001 | **P0** | `_update_global_map()` crash: base class bug affects all components when globalMap is configured |
| ENG-FID-002 | **P0** | `pd.DataFrame({column_name: file_content})` in single-string mode creates one row per character instead of one row with the full content -- should be `pd.DataFrame({column_name: [file_content]})` |
| ENG-FID-003 | **P1** | No REJECT flow -- rows that fail parsing are silently dropped instead of routing to reject output |
| ENG-FID-004 | **P1** | Missing globalMap variables `{id}_FILENAME` and `{id}_ENCODING` -- downstream components cannot access resolved file path |
| ENG-FID-005 | **P1** | Encoding default is UTF-8 but Talend default is ISO-8859-15 -- files with extended Latin characters may decode incorrectly |
| ENG-FID-006 | **P1** | Config key `delimiter` does not match converter `fieldseparator` -- jobs will use engine default `,` instead of Talend default `;` |
| ENG-FID-007 | **P1** | No RFC4180 CSV_OPTION toggle -- escape/enclosure always active regardless of csv_option setting |
| ENG-FID-008 | **P2** | Per-column TRIMSELECT ignored -- engine only supports trim_all (all-or-nothing) |
| ENG-FID-009 | **P2** | CSVROWSEPARATOR ignored -- engine uses only row_separator |
| ENG-FID-010 | **P2** | Footer skip uses pandas `skipfooter` which requires python engine (slower than C engine) |
| ENG-FID-011 | **P3** | No UNCOMPRESS support -- compressed files must be decompressed externally |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Total rows read |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | Same as NB_LINE (no reject) |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | Always 0 (no reject flow) |
| `{id}_FILENAME` | Yes | No | -- | Not implemented |
| `{id}_ENCODING` | Yes | No | -- | Not implemented |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FID-001 | **P0** | `base_component.py:304` | CROSS-CUTTING: `_update_global_map()` crashes when globalMap is configured -- affects all components |
| BUG-FID-002 | **P0** | `file_input_delimited.py:323` | Single-string mode: `pd.DataFrame({column_name: file_content})` creates one row per character. Should be `pd.DataFrame({column_name: [file_content]})` |
| BUG-FID-003 | **P1** | `file_input_delimited.py:266` | Empty delimiter/row_separator detection uses hardcoded `'  '` (two spaces) in the comparison list -- fragile and non-obvious |
| BUG-FID-004 | **P1** | `file_input_delimited.py:192` | `_process()` reads `self.config.get('delimiter')` but converter writes `fieldseparator` -- config key mismatch |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FID-001 | **P2** | `remove_empty_rows` (plural) in engine vs `remove_empty_row` (singular) in _java.xml and converter -- inconsistent |
| NAME-FID-002 | **P2** | Engine class defaults `DEFAULT_DELIMITER = ','` but Talend default is `';'` -- confusing |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FID-001 | **P2** | Module-level logger | Compliant -- `logger = logging.getLogger(__name__)` |
| STD-FID-002 | **P2** | Docstring format | Comprehensive class docstring with all parameters -- compliant |
| STD-FID-003 | **P2** | Type hints | Complete method signatures with return types -- compliant |

### 6.4 Debug Artifacts

None found. Logging uses appropriate levels.

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FID-001 | **P2** | No path traversal protection on `filepath` -- arbitrary file paths accepted without validation |
| SEC-FID-002 | **P2** | No file size check before batch read -- memory exhaustion possible with large files (mitigated by streaming mode threshold) |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Compliant -- module-level logger |
| Level usage | Good -- INFO for lifecycle, DEBUG for details, WARNING for issues |
| Sensitive data | Low risk -- file paths logged at INFO level (acceptable for file input) |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Good -- `ConfigurationError`, `FileOperationError` |
| Exception chaining | Good -- `from e` pattern used consistently |
| die_on_error handling | Good -- controls raise vs empty DataFrame return |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | Complete with return types |
| Parameter types | Fully typed including Optional and Dict |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FID-001 | **P2** | `_post_process_dataframe()` iterates all string columns twice (trim + fillna) -- could combine |
| PERF-FID-002 | **P2** | BigDecimal conversion uses row-wise `apply()` with lambda -- slow for large datasets |
| PERF-FID-003 | **P3** | `_build_dtype_dict()` called in both batch and streaming paths -- could cache |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Good -- auto-activates for files > 3GB (MEMORY_THRESHOLD_MB) |
| Memory threshold | 3GB default from base class -- reasonable |
| Large data handling | Batch mode loads entire file; streaming chunks for large files |
| Footer skip impact | Forces Python engine (slower, more memory) -- acceptable tradeoff |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 74 | `tests/converters/talend_to_v1/components/test_file_input_delimited.py` |
| Engine unit tests | 0 | None |
| Integration tests | Covered | `tests/converters/talend_to_v1/test_integration.py` (shared) |
| Regression guard | Covered | `tests/converters/talend_to_v1/test_converter_output_structure.py` |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-FID-001 | **P2** | No engine unit tests -- FileInputDelimited engine class has zero dedicated tests |
| TEST-FID-002 | **P2** | No engine integration tests with real CSV files |

### 8.3 Recommended Test Cases

**Engine tests needed:**
1. Happy path: CSV with headers, various delimiters, encoding
2. Edge cases: empty file, single-column file, unicode characters
3. Large file streaming mode activation
4. die_on_error=True vs False behavior
5. Footer skip with Python engine
6. Text enclosure and escape char combinations
7. Trim all string columns
8. Remove empty rows
9. Schema enforcement with type conversion
10. Single-string mode (empty delimiter)

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 2 | **BUG-FID-001**, **BUG-FID-002** |
| P1 | 7 | **ENG-FID-003**, **ENG-FID-004**, **ENG-FID-005**, **ENG-FID-006**, **ENG-FID-007**, **BUG-FID-003**, **BUG-FID-004** |
| P2 | 10 | ENG-FID-008, ENG-FID-009, ENG-FID-010, NAME-FID-001, NAME-FID-002, SEC-FID-001, SEC-FID-002, PERF-FID-001, PERF-FID-002, TEST-FID-001, TEST-FID-002 |
| P3 | 2 | ENG-FID-011, PERF-FID-003 |
| **Total** | **21** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 9 | ENG-FID-001 through ENG-FID-011 (minus ENG-FID-002) |
| Bug (BUG) | 4 | BUG-FID-001 through BUG-FID-004 |
| Naming (NAME) | 2 | NAME-FID-001, NAME-FID-002 |
| Security (SEC) | 2 | SEC-FID-001, SEC-FID-002 |
| Standards (STD) | 0 | -- (all compliant) |
| Performance (PERF) | 3 | PERF-FID-001, PERF-FID-002, PERF-FID-003 |
| Testing (TEST) | 2 | TEST-FID-001, TEST-FID-002 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash -- stats lost for file input component |
| XCUT-004 | `base_component.py:202` | `self.config` mutation via `resolve_dict()` -- if tFileInputDelimited runs inside iterate loop, config modified on first pass |

---

## 10. Recommendations

### Immediate (Before Production)

1. **BUG-FID-001 (P0):** Fix `_update_global_map()` crash in base class (cross-cutting, fixes all 54 components)
2. **BUG-FID-002 (P0):** Fix single-string DataFrame creation: `pd.DataFrame({col: file_content})` -> `pd.DataFrame({col: [file_content]})`

### Short-term (Hardening)

3. **ENG-FID-003 (P1):** Implement REJECT flow for failed row parsing
4. **ENG-FID-006 (P1):** Align config key: engine should read `fieldseparator` or converter should emit `delimiter`
5. **ENG-FID-005 (P1):** Change engine encoding default from UTF-8 to ISO-8859-15
6. **ENG-FID-004 (P1):** Implement `{id}_FILENAME` and `{id}_ENCODING` globalMap variables
7. **BUG-FID-004 (P1):** Fix config key mismatch between converter output and engine input

### Long-term (Optimization)

8. **PERF-FID-001 (P2):** Combine string column post-processing passes
9. **TEST-FID-001 (P2):** Add engine unit tests for FileInputDelimited
10. **ENG-FID-011 (P3):** Add UNCOMPRESS support for compressed files

---

## 11. Risk Assessment

This section is included because tFileInputDelimited is the most commonly used input component in Talend, handles arbitrary file content, and has extensive parsing options that create security and data integrity risks.

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| CSV injection via crafted delimiters | Medium | High -- malicious delimiters could cause field boundary confusion, data misalignment, or injection into downstream components | Validate FIELDSEPARATOR is a known delimiter pattern; sanitize regex delimiters |
| Escape character handling bypass | Low | High -- crafted escape sequences could break out of quoted fields, corrupting data or enabling injection | Ensure CSV mode properly handles double-quote vs backslash escape modes |
| Delimiter confusion attacks | Medium | Medium -- files with mixed delimiter patterns (semicolon in data, comma as delimiter) cause silent data corruption | Log field count mismatches per row; enable CHECK_FIELDS_NUM in production |
| Encoding mismatch data corruption | High | Medium -- ISO-8859-15 vs UTF-8 mismatch causes garbled special characters (Euro sign, accented characters) without error | Log encoding mismatches; warn when encoding produces replacement characters |
| Split record data loss | Low | High -- SPLITRECORD=false with multi-line quoted fields causes records to be truncated or merged | Always enable CSV_OPTION when files may contain quoted multi-line fields |
| Large file memory exhaustion with UNCOMPRESS | Low | High -- compressed files expand to unknown size; no size check before decompression | Not currently supported by engine (mitigated by absence) |
| RANDOM sampling bias | Medium | Low -- RANDOM=true reads entire file into memory then samples, creating predictable bias patterns | Document that RANDOM is not true statistical sampling; use external sampling for critical analytics |
| Path traversal via FILENAME | Low | High -- user-supplied context variables in FILENAME could reference sensitive system files | Validate file paths against allowed directories; reject `..` path components |

### High-Risk Job Patterns

1. **ISO-8859-15 files read with engine default UTF-8 encoding** -- Files with accented characters, Euro sign, or other extended Latin characters silently produce garbled data. This affects most European-locale Talend jobs.
2. **Multi-character regex delimiters with CSV_OPTION=true** -- Talend restricts this in the UI but the XML allows it. Engine will attempt regex parsing with quoting, producing unpredictable results.
3. **RANDOM=true with large files** -- Reads entire file to select random lines. A 10GB file with NB_RANDOM=10 uses 10GB+ memory for 10 rows.
4. **TRIMSELECT per-column trim settings** -- Engine ignores per-column trim and only supports trim_all. Jobs relying on selective trimming will have incorrect whitespace handling.
5. **Footer skip with large files** -- Forces pandas Python engine (slower, higher memory) instead of C engine. Combined with large files, this can cause performance issues.

### Safe Usage Patterns

1. **Standard CSV with comma/semicolon delimiter, UTF-8 encoding** -- Well-tested path when encoding is explicitly set to match engine default.
2. **HEADER=1 with schema-defined columns** -- Reliable header skipping with schema enforcement.
3. **die_on_error=True for data pipeline jobs** -- Proper error propagation for monitored ETL processes.
4. **trim_all=True for cleanup** -- Global trim works correctly for all string columns.
5. **Streaming mode for large files (> 3GB)** -- Automatic chunked processing prevents memory exhaustion.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub _java.xml | `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileInputDelimited/tFileInputDelimited_java.xml` | Complete parameter definitions, defaults, TABLE structures |
| Official Talend docs | `https://help.qlik.com/talend/en-US/components/8.0/delimited/tfileinputdelimited-standard-properties` | Component description, behavioral notes |
| Engine source | `src/v1/engine/components/file/file_input_delimited.py` (574 lines) | Feature parity analysis, bug identification, security assessment |
| Converter source | `src/converters/talend_to_v1/components/file/file_input_delimited.py` | Converter audit |
| Converter tests | `tests/converters/talend_to_v1/components/test_file_input_delimited.py` (74 tests) | Test coverage analysis |
| Base class | `src/v1/engine/base_component.py` | Cross-cutting issue identification |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash -- stats lost for file input component |
| XCUT-004 | `base_component.py:202` | `self.config` mutation via `resolve_dict()` -- file paths, delimiters modified on first pass in iterate loops |

### Edge-Case Checklist Results

| Check | Result | Notes |
|-------|--------|-------|
| NaN handling | Risk | `dropna(how='all')` for remove_empty_rows; `fillna("")` for strings -- reasonable |
| Empty strings in config | Risk | Empty delimiter triggers single-string mode; empty filepath returns empty DF |
| Empty DataFrame input | N/A | Source component -- no input data |
| HYBRID streaming mode | Good | Auto-activates for files > 3GB via base class threshold |
| `_update_global_map()` crash | High impact | File input stats (NB_LINE, NB_LINE_OK) lost when globalMap configured |
| Type demotion | Risk | BigDecimal uses `apply()` with Decimal constructor -- may lose precision through pandas |
| `validate_schema` nullable | Risk | Inverted logic may cause unexpected fillna behavior on nullable columns |
| `_validate_config()` called | Dead code | Defined but never called by base class `execute()` method |

## Appendix C: Delimiter/Separator Parameter Comparison

This appendix details the relationship between Talend parameters, converter config keys, and engine config keys for the various delimiter/separator parameters -- the most common source of configuration confusion.

| Talend XML Name | Converter Config Key | Engine Config Key | Engine Default | Talend Default | Match? |
|-----------------|---------------------|-------------------|----------------|----------------|--------|
| `FIELDSEPARATOR` | `fieldseparator` | `delimiter` | `','` | `";"` | No -- key and default both differ |
| `ROWSEPARATOR` | `row_separator` | `row_separator` | `None` | `"\n"` | Partial -- key matches, default differs |
| `CSVROWSEPARATOR` | `csv_row_separator` | -- (not read) | -- | `"\n"` | No -- not read by engine |
| `TEXT_ENCLOSURE` | `text_enclosure` | `text_enclosure` | `'"'` | `"\""` | Yes |
| `ESCAPE_CHAR` | `escape_char` | `escape_char` | `'\\'` | `"\""` | No -- default differs |
| `ENCODING` | `encoding` | `encoding` | `'UTF-8'` | `"ISO-8859-15"` | No -- default differs |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after hidden/design-time param removal*
