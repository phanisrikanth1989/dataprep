# Audit Report: tFileInputFullRow / FileInputFullRowComponent

> **Audited**: 2026-04-03
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report is scoped to the v1 engine exclusively

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileInputFullRow` |
| **V1 Engine Class** | `FileInputFullRowComponent` |
| **Engine File** | `src/v1/engine/components/file/file_input_fullrow.py` (213 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_input_fullrow.py` (93 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileInputFullRow")` decorator-based dispatch |
| **Registry Aliases** | `tFileInputFullRow` |
| **Category** | File / Input |
| **Complexity** | Low-Medium -- single-column line reader with configurable header/footer/random extraction |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_input_fullrow.py` | Engine implementation (213 lines) |
| `src/converters/talend_to_v1/components/file/file_input_fullrow.py` | Converter class (93 lines) |
| `tests/converters/talend_to_v1/components/test_file_input_fullrow.py` | Converter tests (48 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 8 unique params + 2 framework params extracted; `_build_component_dict` pattern; 4 per-feature needs_review entries for engine gaps; phantom DIE_ON_ERROR removed |
| Engine Feature Parity | **Y** | 0 | 4 | 1 | 0 | Engine reads 6 of 10 params (filename, row_separator, remove_empty_row, encoding, limit, die_on_error); ignores header_rows, footer_rows, random, nb_random; encoding default mismatch (UTF-8 vs ISO-8859-15) |
| Code Quality | **Y** | 1 | 2 | 3 | 1 | unicode_escape crash risk; _validate_config() dead code; strip() filters whitespace-only lines; base class cross-cutting bugs |
| Performance & Memory | **Y** | 0 | 1 | 1 | 1 | Entire file loaded into memory; intermediate list for filtering; suboptimal DataFrame construction |
| Testing | **Y** | 0 | 0 | 2 | 0 | 48 converter unit tests across 10 test classes per gold standard; integration + regression guard passing; engine unit tests missing (P2) -- no engine test coverage prevents Green |

**Overall: Yellow -- Converter fully standardized (Green); engine has 4 known gaps documented via needs_review; engine/code quality/performance gaps keep overall at Yellow**

**Top Actions:**

1. Fix `_update_global_map()` crash in base class (P0, cross-cutting)
2. Add header row skipping to engine (P1, engine gap)
3. Add footer row skipping to engine (P1, engine gap)
4. Add random line extraction to engine (P1, engine gap)
5. Fix engine encoding default from UTF-8 to ISO-8859-15 (P2, engine mismatch)

---

## 3. Talend Feature Baseline

### What tFileInputFullRow Does

`tFileInputFullRow` reads each row of a file as a single string value. Unlike `tFileInputDelimited` which parses structured data into multiple columns, `tFileInputFullRow` treats each line as one atomic value -- outputting a single column (typically named "line") containing the entire row text. This makes it suitable for reading log files, unstructured text, or files that need custom downstream parsing.

The component supports configurable row separators, header/footer row skipping, row limiting, empty row removal, random line extraction, and multiple character encodings.

**Source**: [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileInputFullRow/tFileInputFullRow_java.xml)
**Component family**: File / Input
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Output schema definition. Typically a single column named "line". |
| 2 | File Name | `FILENAME` | FILE | `""` | Path to the file to read. Required. Supports context variables. |
| 3 | Row Separator | `ROWSEPARATOR` | TEXT | `"\\n"` | Character(s) used to delimit rows. |
| 4 | Header | `HEADER` | TEXT | `""` (functionally 0) | Number of header rows to skip. |
| 5 | Footer | `FOOTER` | TEXT | `""` (functionally 0) | Number of footer rows to skip. |
| 6 | Limit | `LIMIT` | TEXT | `""` | Maximum rows to read. Empty = unlimited. |
| 7 | Remove Empty Row | `REMOVE_EMPTY_ROW` | CHECK | `true` | Filter out empty rows from output. |
| 8 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding for reading the file. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 9 | Random | `RANDOM` | CHECK | `false` | Enable random line extraction mode. |
| 10 | Nb Random | `NB_RANDOM` | TEXT | `10` | Number of random lines to extract when RANDOM is enabled. |

### 3.3 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 11 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Enable statistics collection. |
| 12 | Label | `LABEL` | TEXT | `""` | Component label for display. |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Output | Row > Main | One row per file line, single column containing full row text |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful execution |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires after failed execution |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | int | After execution | Total rows read from file |
| `{id}_NB_LINE_OK` | int | After execution | Successfully processed rows |
| `{id}_NB_LINE_REJECT` | int | After execution | Rejected rows (always 0 for this component) |

### 3.6 Note on DIE_ON_ERROR

DIE_ON_ERROR is NOT listed in the tFileInputFullRow _java.xml definition. However, the engine implementation reads it from config. The converter does NOT extract this param (removed as phantom per _java.xml source of truth). The engine provides its own default (`True`).

---

## 4. Converter Coverage

### 4.1 Parameter Mapping

| # | Talend XML | Config Key | Type | Default | Converter | Status |
| --- | ----------- | ------------ | ------ | --------- | ----------- | -------- |
| 1 | FILENAME | filename | str | `""` | `_get_str(node, "FILENAME", "")` | OK |
| 2 | ROWSEPARATOR | row_separator | str | `"\\n"` | `_get_str(node, "ROWSEPARATOR", "\\n")` | OK |
| 3 | HEADER | header_rows | int | `0` | `_get_int(node, "HEADER", 0)` | OK |
| 4 | FOOTER | footer_rows | int | `0` | `_get_int(node, "FOOTER", 0)` | OK |
| 5 | LIMIT | limit | str | `""` | `_get_str(node, "LIMIT", "")` | OK |
| 6 | REMOVE_EMPTY_ROW | remove_empty_row | bool | `True` | `_get_bool(node, "REMOVE_EMPTY_ROW", True)` | OK |
| 7 | ENCODING | encoding | str | `"ISO-8859-15"` | `_get_str(node, "ENCODING", "ISO-8859-15")` | OK |
| 8 | RANDOM | random | bool | `False` | `_get_bool(node, "RANDOM", False)` | OK |
| 9 | NB_RANDOM | nb_random | int | `10` | `_get_int(node, "NB_RANDOM", 10)` | OK |
| 10 | TSTATCATCHER_STATS | tstatcatcher_stats | bool | `False` | `_get_bool(node, "TSTATCATCHER_STATS", False)` | OK |
| 11 | LABEL | label | str | `""` | `_get_str(node, "LABEL", "")` | OK |

### 4.2 Phantom Parameters Removed

| Parameter | Was In Converter | In _java.xml | Action |
| ----------- | ----------------- | -------------- | -------- |
| DIE_ON_ERROR | Yes (default True) | No | Removed from converter output |

### 4.3 Schema Handling

- **Direction**: Source component -- `{"input": [], "output": self._parse_schema(node)}`
- **FLOW schema**: Parsed via `_parse_schema(node)` with full column attributes (name, type, nullable, key, length, precision, date_pattern)
- **Date pattern conversion**: Java SimpleDateFormat -> Python strftime via `_convert_date_pattern()`

### 4.4 Engine Gap needs_review Entries

| # | Config Key | Severity | Issue |
| --- | ----------- | ---------- | ------- |
| 1 | header_rows | engine_gap | Engine does not support skipping header rows |
| 2 | footer_rows | engine_gap | Engine does not support skipping footer rows |
| 3 | random | engine_gap | Engine does not support random line extraction |
| 4 | nb_random | engine_gap | Engine does not support random line count |

### 4.5 Converter Issues

None. All parameters correctly extracted with proper defaults per _java.xml source of truth.

---

## 5. Engine Implementation

### 5.1 What the Engine Does

The engine reads a file line-by-line using configurable encoding and row separator, optionally removes empty rows and applies a row limit. Each line becomes a single row in a DataFrame with column name "line". The engine supports `die_on_error` to control error behavior.

**Engine reads these config keys:**

- `filename` -- path to file (required)
- `row_separator` -- split delimiter (default `\n`)
- `remove_empty_row` -- filter empty lines (default `False` -- differs from Talend's `True`)
- `encoding` -- file encoding (default `UTF-8` -- differs from Talend's `ISO-8859-15`)
- `limit` -- max rows (string, uses `.isdigit()`)
- `die_on_error` -- error behavior (default `True`)

**Engine ignores these config keys:**

- `header_rows` -- no header row skipping logic
- `footer_rows` -- no footer row skipping logic
- `random` -- no random extraction mode
- `nb_random` -- no random count handling

### 5.2 Engine Default Mismatches

| Config Key | Talend Default | Engine Default | Impact |
| ----------- | --------------- | ---------------- | -------- |
| remove_empty_row | `True` | `False` | Empty rows preserved when converter default is used but engine overrides |
| encoding | `ISO-8859-15` | `UTF-8` | Encoding mismatch may cause garbled text for non-ASCII content |

### 5.3 Engine Processing Flow

1. Extract config with defaults
2. Strip quotes from `row_separator`, decode escape sequences (`unicode_escape`)
3. Normalize `\r\n` to `\n` in file content
4. Split on `row_separator`
5. Remove empty rows if configured (uses `line.strip()` -- filters whitespace-only lines too)
6. Apply limit if numeric
7. Build DataFrame with `{'line': line}` dicts
8. Update statistics

---

## 6. Engine Issues

| ID | Priority | Status | Description |
| ---- | ---------- | -------- | ------------- |
| ENG-FIFR-001 | **P1** | **OPEN** | No header row skipping -- HEADER value is passed through converter but engine ignores it entirely |
| ENG-FIFR-002 | **P1** | **OPEN** | No footer row skipping -- FOOTER value is passed through converter but engine ignores it entirely |
| ENG-FIFR-003 | **P1** | **OPEN** | No random line extraction -- RANDOM and NB_RANDOM ignored by engine |
| ENG-FIFR-004 | **P1** | **OPEN** | No REJECT flow -- error rows are silently dropped or crash the job |
| ENG-FIFR-005 | **P2** | **OPEN** | Encoding default mismatch -- engine uses UTF-8 but Talend defaults to ISO-8859-15 |
| ENG-FIFR-006 | **P2** | **OPEN** | `remove_empty_row` default mismatch -- engine defaults False, Talend defaults True |
| ENG-FIFR-007 | **P2** | **OPEN** | Hardcoded output column name 'line' -- ignores schema-defined column name |

---

## 7. Code Quality

| ID | Priority | Status | Description |
| ---- | ---------- | -------- | ------------- |
| BUG-FIFR-001 | **P0** | **OPEN** | `_update_global_map()` crash -- base class references undefined variable. Cross-cutting: affects ALL components. |
| BUG-FIFR-002 | **P1** | **OPEN** | `unicode_escape` decoding of `row_separator` -- can crash on invalid escape sequences (e.g., `\x` without hex digits) |
| BUG-FIFR-003 | **P1** | **OPEN** | `strip()` in empty row removal filters whitespace-only lines, not just truly empty lines -- behavioral difference from Talend |
| BUG-FIFR-004 | **P2** | **OPEN** | `_validate_config()` is dead code -- called only from public `validate_config()` wrapper which is never called by base class `execute()` |
| BUG-FIFR-005 | **P2** | **OPEN** | Dual validation methods -- both `_validate_config()` and `validate_config()` exist with overlapping logic |
| BUG-FIFR-006 | **P2** | **OPEN** | `limit=0` reads zero rows -- Talend treats 0 as unlimited; engine treats "0" as `.isdigit()` == True -> limit 0 rows |
| BUG-FIFR-007 | **P3** | **OPEN** | `\r\n` normalization is always applied even when row_separator is not `\n` -- may alter content unexpectedly |

---

## 8. Performance & Memory

| ID | Priority | Status | Description |
| ---- | ---------- | -------- | ------------- |
| PERF-FIFR-001 | **P1** | **OPEN** | Entire file loaded into memory -- no streaming/chunked reading. Large files (>1GB) will cause OOM. |
| PERF-FIFR-002 | **P2** | **OPEN** | Intermediate list of dicts for DataFrame construction -- `[{'line': line} for line in lines]` creates unnecessary overhead |
| PERF-FIFR-003 | **P3** | **OPEN** | Filter + limit applied sequentially with list comprehension + slice -- could use generator with `islice()` |

---

## 9. Testing

### 9.1 Converter Tests

| Category | Count | Status |
| ---------- | ------- | -------- |
| TestRegistration | 1 | PASS |
| TestDefaults | 9 | PASS |
| TestParameterExtraction | 10 | PASS |
| TestFrameworkParams | 4 | PASS |
| TestSchema | 3 | PASS |
| TestNeedsReview | 8 | PASS |
| TestCompleteness | 2 | PASS |
| TestPhantomParams | 1 | PASS |
| TestComponentStructure | 8 | PASS |
| TestWarnings | 2 | PASS |
| **Total** | **48** | **ALL PASS** |

### 9.2 Integration Tests

- Converter output structure regression guard: PASS
- Integration tests: PASS (399 tests)

### 9.3 Engine Tests

- Engine unit tests: **NONE** (P2 -- prevents Testing from reaching Green)
- Engine integration tests: **NONE**

### 9.4 Testing Issues

| ID | Priority | Status | Description |
| ---- | ---------- | -------- | ------------- |
| TEST-FIFR-001 | **P2** | **OPEN** | Zero engine unit tests -- no `_process()` verification, no edge case coverage |
| TEST-FIFR-002 | **P2** | **OPEN** | Zero engine integration tests -- no end-to-end file reading verification |

---

## 10. Recommendations

### Immediate (P0)

1. Fix `_update_global_map()` base class crash (cross-cutting)

### Short-term (P1)

1. Implement header row skipping in engine
2. Implement footer row skipping in engine
3. Add random line extraction to engine
4. Fix `unicode_escape` crash risk for invalid escape sequences
5. Fix `strip()` behavior to match Talend's empty-row definition

### Medium-term (P2)

1. Fix encoding default mismatch (UTF-8 -> ISO-8859-15)
2. Fix remove_empty_row default mismatch (False -> True)
3. Fix limit=0 semantic to match Talend (0 = unlimited)
4. Respect schema-defined column name instead of hardcoded 'line'
5. Wire `_validate_config()` into base class lifecycle or remove dead code
6. Add engine unit tests and integration tests

### Low Priority (P3)

1. Add streaming support for large files
2. Optimize DataFrame construction
3. Make `\r\n` normalization conditional on row_separator

---

## Appendix A: _java.xml Parameter Source

Source: `tFileInputFullRow_java.xml` from Talaxie GitHub

```
SCHEMA          SCHEMA_TYPE     (schema definition)
FILENAME        FILE            default=""
ROWSEPARATOR    TEXT            default="\\n"
HEADER          TEXT            default=""
FOOTER          TEXT            default=""
LIMIT           TEXT            default=""
REMOVE_EMPTY_ROW CHECK          default=true
ENCODING        ENCODING_TYPE   default="ISO-8859-15"
RANDOM          CHECK           default=false
NB_RANDOM       TEXT            default=10
TSTATCATCHER_STATS CHECK        default=false
```

Note: DIE_ON_ERROR is NOT in this _java.xml file. It is extracted by the engine from its own config but is not a Talend-declared parameter for this component.

---

## Appendix B: Engine Config Key Cross-Reference

| Config Key | Converter Extracts | Engine Reads | Match |
| ----------- | ------------------- | -------------- | ------- |
| filename | Yes | Yes | OK |
| row_separator | Yes | Yes | OK |
| header_rows | Yes | No | ENGINE GAP |
| footer_rows | Yes | No | ENGINE GAP |
| limit | Yes | Yes | OK |
| remove_empty_row | Yes | Yes | OK (default mismatch) |
| encoding | Yes | Yes | OK (default mismatch) |
| random | Yes | No | ENGINE GAP |
| nb_random | Yes | No | ENGINE GAP |
| die_on_error | No (phantom) | Yes (own default) | N/A |
| tstatcatcher_stats | Yes | No (framework) | N/A |
| label | Yes | No (framework) | N/A |
