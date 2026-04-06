# Audit Report: SwiftBlockFormatter (Engine-Native Custom Component)

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: N/A -- engine-native custom component, no Talend XML conversion
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | N/A -- engine-native custom component, no Talend equivalent |
| **V1 Engine Class** | `SwiftBlockFormatter` |
| **Engine File** | `src/v1/engine/components/transform/swift_block_formatter.py` (707 lines) |
| **Converter Parser** | N/A -- no converter. Configuration supplied directly in job JSON. |
| **Converter Dispatch** | N/A -- not registered in `talend_to_v1` converter registry. |
| **Registry Aliases** | `SwiftBlockFormatter`, `tSwiftBlockFormatter` (registered in `src/v1/engine/engine.py`) |
| **Category** | Transform / Custom (SWIFT Financial Messaging) |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/swift_block_formatter.py` | Engine implementation (707 lines) |
| `src/v1/engine/engine.py` | Import and registry alias registration |
| `src/v1/engine/components/transform/__init__.py` | Package export |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **N/A** | -- | -- | -- | -- | Engine-native custom component; no Talend XML conversion. Config hand-authored in job JSON. |
| Engine Feature Parity | **Y** | 1 | 4 | 5 | 2 | Core SWIFT parsing works; edge cases around regex, block pairing, NaN, empty input, streaming |
| Code Quality | **Y** | 2 | 5 | 5 | 3 | Cross-cutting base class bugs; forced DEBUG logging; dict-in-data defensive code; regex truncation |
| Performance & Memory | **Y** | 0 | 1 | 2 | 1 | Entire file read into memory; no streaming; quadruple validation pass |
| Testing | **N/A** | -- | -- | -- | -- | Engine-native component; no converter tests applicable per D-88. Zero engine unit tests exist. |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes. Second-largest engine component (707 lines).**

**Top Actions**:

1. Fix cross-cutting `_update_global_map()` and `GlobalMap.get()` crashes (P0)
2. Remove forced `logger.setLevel(logging.DEBUG)` in `_process()` (P1)
3. Fix Block 4 regex for optional trailing hyphen (P1)
4. Fix Block 3/5 regex truncation of nested sub-tags (P1)
5. Add REJECT flow for financial data auditability (P1)

---

## 3. Talend Feature Baseline

What is this component and what does it do?

### What SwiftBlockFormatter Does

`SwiftBlockFormatter` is an engine-native custom component (no Talend equivalent) that parses SWIFT (Society for Worldwide Interbank Financial Telecommunication) messages and converts them into a flat, pipe-delimited DataFrame. SWIFT messages follow the MT (Message Type) standard with a five-block structure:

- **Block 1** (Basic Header): Application ID, service ID, BIC, session number, sequence number
- **Block 2** (Application Header): Direction (I=Input/O=Output), message type (e.g., 940, 950), BIC, timestamps
- **Block 3** (User Header): User-defined content (banking references, priorities, MUR)
- **Block 4** (Text Block): The message body containing tagged fields (`:20:`, `:61:`, `:86:`, etc.)
- **Block 5** (Trailer): Checksum, authentication data (e.g., `{CHK:...}`, `{MAC:...}`)

The component's primary purpose is to normalize multi-occurrence field 61 (Statement Line) / field 86 (Information to Account Owner) pairs. A single MT940 statement message may contain hundreds of `:61:`/`:86:` pairs representing individual transactions. The component "explodes" these into one row per 61/86 pair while repeating all single-occurrence header fields (`:20:`, `:25:`, etc.) across each row.

**Source**: Engine-native component; no external Talend documentation.
**Component family**: Transform / Custom SWIFT
**Input**: DataFrame with SWIFT message content OR raw SWIFT file path
**Output**: Flat DataFrame with one row per 61/86 pair, columns defined by `pipe_fields` config

### 3.1 Configuration Parameters

| # | Parameter | Config Key | Type | Required | Default | Description |
| --- | ----------- | ------------ | ------ | ---------- | --------- | ------------- |
| 1 | Layout File | `layout_file` | String (path) | Yes* | -- | Path to YAML file defining Block 4 field types. Must contain `swift_layout.block4_layout` key. Supports context variables via `context_manager.resolve_string()`. |
| 2 | Inline Layout | `layout` | Dict | Yes* | `{}` | Alternative to `layout_file`: inline dict mapping field keys (e.g., `block4_20`) to types (`S`=single, `M`=multiple). |
| 3 | Pipe Fields | `pipe_fields` | List | Yes | -- | Output column definitions. Each element is either a string (field name = source) or a dict with `name`, `source`, `default` keys. |
| 4 | Input File | `input_file` | String (path) | No | -- | Path to SWIFT message file. Required when no input DataFrame is provided. |
| 5 | Content Column | `content_column` | String | No | `"content"` | Column name in input DataFrame containing SWIFT message text. |
| 6 | Output File | `output_file` | String (path) | No | -- | If set, writes the result DataFrame to this path as pipe-delimited CSV. |
| 7 | Encoding | `encoding` | String | No | `"UTF-8"` | Character encoding for reading input SWIFT file. |
| 8 | Output Encoding | `output_encoding` | String | No | `"UTF-8"` | Character encoding for writing output file. |
| 9 | Delimiter | `delimiter` | String | No | `"\ | "` | Delimiter for output file writing (default pipe). |
| 10 | Include Header | `include_header` | Boolean | No | `true` | Whether to include column headers in output file. |
| 11 | Die On Error | `die_on_error` | Boolean | No | `true` | Raise exception on error vs. return empty DataFrame. |
| 12 | Processing | `processing` | Dict | No | `{}` | Processing options (stored but never used -- dead configuration). |
| 13 | Execution Mode | `execution_mode` | String | No | `"hybrid"` | Inherited from BaseComponent: batch, streaming, or hybrid. |

*One of `layout_file` or `layout` is required. If both are absent, `ValueError` is raised during `__init__`.

### 3.2 Layout File Structure

The YAML layout file must have this structure:

```yaml
swift_layout:
  block4_layout:
    block4_20: "S"   # Single occurrence field
    block4_25: "S"
    block4_61: "M"   # Multiple occurrence field
    block4_86: "M"
    block4_60F: "S"
    block4_62F: "S"
```

- `"S"` = Single occurrence: only the first occurrence of this field tag is kept
- `"M"` = Multiple occurrence: all occurrences are collected into a list

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `main` (input) | Input | DataFrame | DataFrame with SWIFT message content in a column |
| `main` (output) | Output | DataFrame | Flat DataFrame with one row per 61/86 pair |
| N/A | N/A | REJECT | **No reject flow implemented** |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total number of SWIFT messages parsed (NOT output rows) |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of output rows produced (can exceed NB_LINE due to 61/86 normalization) |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Always 0 -- no reject mechanism |
| `{id}_EXECUTION_TIME` | Float | After execution | Execution time in seconds (v1-specific) |

### 3.5 Behavioral Notes

1. **Layout deferred loading**: The layout file is NOT loaded during `__init__()`. It is loaded lazily in `_ensure_layout_loaded()`, called at the start of `_process()`. This allows context variables in `layout_file` to be resolved first.

2. **Block 61/86 pairing logic**: Field 61 (Statement Line) and field 86 (Information to Account Owner) are treated as paired entries. When a `:61:` tag is encountered, the parser checks if the next field is `:86:`. If so, they are paired. If not, an empty string is used for the 86 value.

3. **Field continuation lines**: Lines in Block 4 that do not start with a field tag pattern (`:NN:` or `:NNA:`) are treated as continuation lines of the current field. For field 61, continuation lines are joined with `sfield9=`. For all other fields, continuation lines are joined with a space.

4. **Layout filter**: Only fields whose key (e.g., `block4_20`) appears in the layout specification are processed. Unrecognized fields are silently dropped.

5. **Message splitting**: Messages in a multi-message file are split using the pattern `{1:...}` as a message boundary. If this pattern fails, the fallback splits by double newlines.

6. **Heuristic column detection**: When receiving DataFrame input and the configured `content_column` is not found, the component searches for any column whose first row contains `{` and `:` characters.

---

## 4. Converter Audit

### 4.1 Converter Status

**N/A -- Engine-native custom component.** `SwiftBlockFormatter` has no Talend equivalent and no converter in the `talend_to_v1` converter pipeline. Configuration is supplied directly in job JSON files.

This is architecturally correct -- engine-native components do not need converter support.

### 4.2 Parameter Extraction

N/A -- no converter exists.

### 4.3 Schema Extraction

N/A -- no converter exists.

### 4.4 Expression Handling

N/A -- no converter exists. Context variable resolution is handled at runtime by `context_manager.resolve_string()` for the `layout_file` path.

### 4.5 Converter Issues

None -- no converter exists.

### 4.6 Needs Review Entries

None -- no converter exists.

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement SWIFT message parsing?

### 5.1 Feature Implementation Status

| # | Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | --------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Parse Block 1 (Basic Header) | **Yes** | Medium | `_parse_block1()` line 289 | Fixed-position parsing of app_id, service_id, BIC, session, sequence |
| 2 | Parse Block 2 (Application Header) | **Yes** | Medium | `_parse_block2()` line 308 | Handles both Input (I) and Output (O) directions |
| 3 | Parse Block 3 (User Header) | **Yes** | Low | `_parse_block3()` line 331 | Stores raw content only -- no sub-tag parsing. Regex truncates nested content. |
| 4 | Parse Block 4 (Text Block) with layout | **Yes** | High | `_parse_block4_with_layout()` line 344 | Core parsing with field tag recognition, multi-line, 61/86 pairing |
| 5 | Parse Block 5 (Trailer) | **Yes** | Low | `_parse_block5()` line 522 | Stores raw content only -- regex truncates nested content. |
| 6 | Layout from YAML file | **Yes** | High | `_load_layout_from_file()` line 95 | YAML loading with `safe_load`, type validation, dict value filtering |
| 7 | Layout from inline config | **Yes** | High | `_ensure_layout_loaded()` line 81 | Fallback to `self.inline_layout` |
| 8 | Multi-message file splitting | **Yes** | Medium | `_split_messages()` line 245 | Regex-based with empty-line fallback |
| 9 | DataFrame input (pipeline mode) | **Yes** | Medium | `_parse_dataframe_input()` line 191 | Heuristic column detection when configured column missing |
| 10 | File input (standalone mode) | **Yes** | High | `_parse_swift_file()` line 218 | Direct file reading with configurable encoding |
| 11 | 61/86 field pairing | **Yes** | High | `_parse_block4_with_layout()` line 423 | Core normalization logic |
| 12 | Multiple occurrence fields (M type) | **Yes** | High | `_parse_block4_with_layout()` line 469 | Collected into lists |
| 13 | Single occurrence fields (S type) | **Yes** | High | `_parse_block4_with_layout()` line 476 | First occurrence kept, duplicates silently ignored |
| 14 | Pipe-delimited output file | **Yes** | High | `_write_output_file()` line 688 | Uses `pd.to_csv()` with configurable delimiter |
| 15 | Field continuation lines | **Yes** | Medium | `_parse_block4_with_layout()` line 396 | Appended to current field with `sfield9=` (field 61) or space |
| 16 | Context variable in layout_file | **Yes** | High | `_ensure_layout_loaded()` line 86 | Via `context_manager.resolve_string()` |
| 17 | Die on error toggle | **Yes** | High | `_process()` line 184 | Raises RuntimeError or returns empty DataFrame |
| 18 | Schema validation | **Partial** | Low | `_convert_to_dataframe()` line 604 | Only applied if `output_schema` attribute exists |
| 19 | REJECT flow | **No** | N/A | -- | No reject mechanism for unparseable messages |
| 20 | Streaming / large file support | **No** | N/A | -- | Entire file read into memory; no chunked parsing |
| 21 | Field tags with letter suffix | **Partial** | Low | Line 368 regex | `(\d{2}[A-Z]?)` matches 2-digit + optional single letter. Does NOT match 3-digit tags. |

### 5.2 Behavioral Differences

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-SBF-001 | **P1** | **No REJECT flow**: Unparseable SWIFT messages are silently dropped (returning `None` from `_parse_single_message()` line 287). No error details captured. No reject DataFrame produced. For financial message processing, silent data loss is unacceptable. |
| ENG-SBF-002 | **P1** | **Block 2 Output message BIC extraction wrong**: In `_parse_block2()` line 327, for Output ('O') messages, `block2bic` extracted from positions `[14:26]` overlaps with `block2_mir` at `[10:22]`. The SWIFT standard Block 2 Output format has different offsets. |
| ENG-SBF-003 | **P1** | **Standalone block 86 entries lost after first block 61**: Condition `elif field_tag == '86' and not block61_list` (line 452) means once ANY `:61:` has been seen, ALL subsequent standalone `:86:` entries not immediately following a `:61:` are silently skipped. |
| ENG-SBF-004 | **P1** | **Trailing empty block 86 values stripped**: Lines 487-488 strip trailing empty strings from `block86_list`, changing the pairing between 61 and 86 entries and creating potential length mismatch. |
| ENG-SBF-005 | **P2** | **`processing` config option stored but never used**: Line 77 stores `self.processing_options` but no code reads it. Dead configuration. |
| ENG-SBF-006 | **P2** | **No streaming support for large SWIFT files**: Entire file read into memory via `file.read()` (line 227). For GB-scale batch reconciliation files, this causes memory exhaustion. |
| ENG-SBF-007 | **P2** | **Heuristic column detection fragile**: Lines 200-206 search for columns containing `{` and `:`, matching JSON, Python dicts, URLs. Should check for SWIFT-specific `{1:` or `:20:` markers. |
| ENG-SBF-008 | **P2** | **Empty DataFrame on zero messages has no columns**: Line 165 returns `pd.DataFrame()` without column definitions. Should use `pd.DataFrame(columns=self.pipe_fields)`. |
| ENG-SBF-009 | **P2** | **`_update_stats` conflates message count with row count**: Line 176 sets `NB_LINE` to message count and `NB_LINE_OK` to row count. Since normalization expands 61/86 pairs, `NB_LINE_OK > NB_LINE`. Breaks Talend convention of `NB_LINE = NB_LINE_OK + NB_LINE_REJECT`. |
| ENG-SBF-010 | **P3** | **`{id}_ERROR_MESSAGE` not set in globalMap**: Errors with `die_on_error=false` are logged but not stored for downstream reference. |
| ENG-SBF-011 | **P3** | **Block 3 sub-tags not parsed**: Block 3 contains sub-tags like `{108:...}` (MUR), `{113:...}` (banking priority), stored as raw string only. |

### 5.3 GlobalMap Variable Coverage

| Variable | Expected? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ----------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` | Set to message count, not row count |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Set to output row count (can exceed NB_LINE) |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Always 0 -- no reject mechanism |
| `{id}_ERROR_MESSAGE` | Expected | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-SBF-001 | **P0** | `base_component.py:304` | **CROSS-CUTTING: `_update_global_map()` references undefined variable `value`**: The log statement uses `{stat_name}: {value}` but the loop variable is `stat_value`. Causes `NameError` whenever `global_map` is not None. Affects ALL components. |
| BUG-SBF-002 | **P0** | `global_map.py:28` | **CROSS-CUTTING: `GlobalMap.get()` references undefined `default` parameter**: Method signature has no `default` param but body calls `self._map.get(key, default)`. Crashes on every `.get()` call. Affects ALL components. |
| BUG-SBF-003 | **P1** | `swift_block_formatter.py:368` | **Field tag regex limited to 2-digit tags**: Pattern `r':(\d{2}[A-Z]?):(.*)'` requires exactly 2 digits. Correctly matches `:20:`, `:61:`, `:60F:` but silently drops any 3-digit tags (rare but possible in certain MT types). |
| BUG-SBF-004 | **P1** | `swift_block_formatter.py:149` | **Logger level forced to DEBUG in production**: `logger.setLevel(logging.DEBUG)` called unconditionally in `_process()`, overriding application log configuration. Floods production logs and leaks sensitive financial data. |
| BUG-SBF-005 | **P1** | `swift_block_formatter.py:349` | **Block 4 regex requires trailing hyphen**: Pattern `r'\{4:(.*?)-\}'` fails for SWIFT messages without `-}` terminator (some generators omit hyphen), losing ALL Block 4 content silently. |
| BUG-SBF-006 | **P2** | `swift_block_formatter.py:251` | **Message split regex edge case**: Pattern `r'(\{1:[^}]*\}.*?)(?=\{1: | $)'` could false-split if `{1:` appears inside Block 4 body. Extremely rare but unprotected. |
| BUG-SBF-007 | **P2** | `swift_block_formatter.py:377-379` | **Field 61 continuation uses hardcoded `sfield9=`**: Not configurable. Could corrupt data if content contains this literal string. |
| BUG-SBF-008 | **P2** | `swift_block_formatter.py:483-491` | **Single-item list vs. scalar inconsistency**: Block 61/86 data stored as scalar when single entry, list when multiple. `_normalize_message_data()` must re-wrap, creating fragile code. |
| BUG-SBF-009 | **P2** | `swift_block_formatter.py:201` | **NaN in content column causes heuristic to skip valid columns**: `str(NaN)` produces `"nan"` which lacks `{` and `:`, so heuristic skips columns with NaN first row even if they contain SWIFT data. |
| BUG-SBF-010 | **P3** | `swift_block_formatter.py:293-304` | **Block 1 length guard `>= 11` misleading**: Subsequent extractions require `len > 24` for full content. Initial check allows partial extraction with incomplete data. |
| BUG-SBF-012 | **P1** | `swift_block_formatter.py:331,522` | **Block 3/5 regex `[^}]*` truncates nested sub-tags**: Patterns `r'\{3:([^}]*)\}'` and `r'\{5:([^}]*)\}'` stop at first `}`, corrupting content like `{3:{108:MT940}{113:xxxx}}` (captures only `{108:MT940`). Actual data corruption, not low fidelity. |
| BUG-SBF-013 | **P1** | `swift_block_formatter.py:308-327` | **Block 2 Output BIC fallback offset inconsistency**: Primary path extracts BIC from `[14:26]` but fallback uses `[16:]` -- 2-character discrepancy produces different BIC values depending on message length. |
| BUG-SBF-014 | **P2** | `swift_block_formatter.py` (normalize) | **M-type fields other than 61/86 silently lose all but first element**: `_normalize_message_data()` only expands 61/86 pairs. Other M-type fields used as pipe_field sources are serialized or first-element-only with no warning. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-SBF-001 | **P3** | **`messagetype` lacks underscore**: Block 1/2/3/5 fields use `block{N}_fieldname` convention but `messagetype` (line 274) breaks it. Should be `block2_msg_type`. |
| NAME-SBF-002 | **P3** | **`pipe_fields` / `pipe_fields_mapping` dual structures**: Always used together but maintained separately. Could be a single OrderedDict. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-SBF-001 | **P2** | "Every component SHOULD have `_validate_config()`" | No `_validate_config()` method. Validation scattered across `__init__` and `_ensure_layout_loaded()`. |
| STD-SBF-002 | **P2** | "No forced log level changes" | Line 149 `logger.setLevel(logging.DEBUG)` overrides application-level logging configuration. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| DBG-SBF-001 | **P1** | `logger.setLevel(logging.DEBUG)` on line 149: Forces DEBUG level for every invocation. Development artifact never removed. |
| DBG-SBF-002 | **P3** | Commented-out debug log lines on lines 542, 554. Should be removed or converted to conditional debug logging. |
| DBG-SBF-003 | **P3** | 70+ lines of defensive dict-checking code (lines 496-592) work around a real bug rather than fixing the root cause. |

### 6.5 Security

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| SEC-SBF-001 | **P2** | **YAML loaded with `yaml.safe_load()` -- correct**: Uses `safe_load` not `load`, preventing arbitrary code execution. Positive finding. |
| SEC-SBF-002 | **P3** | **No path traversal protection**: File paths from config used directly with `os.path.exists()` and `open()`. Low risk for trusted job configs. |

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Level usage | **BROKEN** -- `logger.setLevel(logging.DEBUG)` forced on line 149 overrides all configuration. Many `logger.error()` calls for dict-in-data situations should be `logger.warning()`. |
| Sensitive data | SWIFT message content (account numbers, BICs, amounts) logged at DEBUG level. With forced DEBUG, this is a data leakage concern. |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Not used. Raises generic `ValueError` and `RuntimeError`. |
| Exception chaining | Does NOT use `raise ... from e`. Line 138 loses original exception. |
| die_on_error handling | Single try/except in `_process()`. Correctly raises or returns empty DF. |
| Silent message drops | `_parse_single_message()` returns `None` on any exception (line 287). Failed messages logged but not counted or available downstream. |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | All public methods have return type hints -- correct |
| Parameter types | All methods have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]`, `List[Dict[str, Any]]`, `List[List[str]]` -- correct |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-SBF-001 | **P1** | **Entire SWIFT file read into memory**: `_parse_swift_file()` line 227 calls `file.read()` loading the complete file. For batch reconciliation files (multi-GB, millions of MT940 messages), this causes memory exhaustion. |
| PERF-SBF-002 | **P2** | **Quadruple iteration over row data**: `_convert_to_dataframe()` iterates all rows 4 times: dict checking (lines 545-551), item checking (562-570), validation/stringify (574-592), DataFrame construction. Single pass should combine all. |
| PERF-SBF-003 | **P2** | **Regex patterns not compiled/cached**: All `re.search()`/`re.match()` calls use string patterns recompiled per invocation. For thousands of messages, should use class-level `re.compile()`. |
| PERF-SBF-004 | **P3** | **String concatenation in field value building**: `'\n'.join()` followed by `.replace('\n', ...)` is O(n) twice. Minor for typical SWIFT fields but matters for long `:86:` narrative text. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | NOT implemented for SWIFT file reading. `file.read()` loads entire file. BaseComponent HYBRID mode only chunks DataFrame processing, not file I/O. |
| Memory threshold | 3072 MB (3GB) inherited from BaseComponent. Irrelevant since file is fully loaded before mode selection. |
| Chunked processing | Not available. Each message parsed independently so chunking is architecturally feasible but not implemented. |
| Output accumulation | `all_rows` list accumulates all normalized rows before DataFrame creation. Doubles memory for large files. |

---

## 8. Testing

### 8.1 Current Coverage

**N/A per D-88** -- Engine-native custom component with no converter tests applicable.

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | N/A | No converter exists |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None |

**Note**: While converter testing is N/A for this audit-only component, the complete absence of engine unit tests for 707 lines of financial message parsing code is a significant production risk documented in Section 11.

### 8.2 Test Gaps

No tests exist. All 707 lines of engine code are completely unverified.

### 8.3 Recommended Test Cases

Recommended engine tests (for future implementation, not part of D-82 scope):

| # | Test Case | Priority | Description |
| ---- | ----------- | ---------- | ------------- |
| 1 | Basic MT940 parse | P0 | Parse single MT940 with blocks 1-5, verify all fields extracted |
| 2 | 61/86 single pair | P0 | One `:61:`/`:86:` pair, verify one output row |
| 3 | 61/86 multiple pairs | P0 | Three pairs, verify three rows with header field repetition |
| 4 | 61 without matching 86 | P0 | Missing `:86:`, verify empty string substitution |
| 5 | Layout loading from YAML | P0 | Valid YAML, verify field filtering |
| 6 | Missing layout file | P0 | Non-existent path, verify `ValueError` |
| 7 | Empty pipe_fields | P0 | Empty list, verify `ValueError` during `__init__` |
| 8 | Multi-message file | P1 | 3 messages, verify all parsed correctly |
| 9 | Block 2 Input vs Output | P1 | Both I and O type headers |
| 10 | Die on error toggle | P1 | Both true/false paths |

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 3 | **BUG-SBF-001**, **BUG-SBF-002**, **TEST-SBF-001** |
| P1 | 10 | **ENG-SBF-001**, **ENG-SBF-002**, **ENG-SBF-003**, **ENG-SBF-004**, **BUG-SBF-003**, **BUG-SBF-004**, **BUG-SBF-005**, **BUG-SBF-012**, **BUG-SBF-013**, **PERF-SBF-001** |
| P2 | 16 | **ENG-SBF-005** thru **ENG-SBF-009**, **BUG-SBF-006** thru **BUG-SBF-009**, **BUG-SBF-014**, **STD-SBF-001**, **STD-SBF-002**, **SEC-SBF-001**, **PERF-SBF-002**, **PERF-SBF-003** |
| P3 | 9 | **ENG-SBF-010**, **ENG-SBF-011**, **BUG-SBF-010**, **NAME-SBF-001**, **NAME-SBF-002**, **SEC-SBF-002**, **DBG-SBF-002**, **DBG-SBF-003**, **PERF-SBF-004** |
| **Total** | **38** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 11 | ENG-SBF-001 thru ENG-SBF-011 |
| Bug (BUG) | 14 | BUG-SBF-001 thru BUG-SBF-014 (no BUG-SBF-011) |
| Standards (STD) | 2 | STD-SBF-001, STD-SBF-002 |
| Naming (NAME) | 2 | NAME-SBF-001, NAME-SBF-002 |
| Security (SEC) | 2 | SEC-SBF-001 (positive), SEC-SBF-002 |
| Performance (PERF) | 4 | PERF-SBF-001 thru PERF-SBF-004 |
| Debug (DBG) | 3 | DBG-SBF-001 thru DBG-SBF-003 |
| Testing (TEST) | 1 | TEST-SBF-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| BUG-SBF-001 | `base_component.py:304` | `_update_global_map()` crash -- all stats lost |
| BUG-SBF-002 | `global_map.py:28` | `GlobalMap.get()` crash -- any direct `.get()` fails |

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

1. **Fix cross-cutting `_update_global_map()` bug** (BUG-SBF-001): Change `value` to `stat_value` on `base_component.py` line 304. Fixes ALL components.
2. **Fix cross-cutting `GlobalMap.get()` bug** (BUG-SBF-002): Add `default: Any = None` to `get()` signature. Fixes ALL components.
3. **Remove forced DEBUG log level** (BUG-SBF-004): Delete line 149. Eliminates production log flooding and sensitive data leakage.
4. **Fix Block 4 regex for optional hyphen** (BUG-SBF-005): Change to `r'\{4:(.*?)(?:-\}|\})'`.
5. **Fix Block 3/5 regex for nested sub-tags** (BUG-SBF-012): Use balanced-brace matching or non-greedy pattern that handles nested `{...}`.
6. **Create P0 engine test suite** (TEST-SBF-001): 7 P0 test cases with sample MT940 data.

### Short-term (Hardening)

1. **Implement REJECT flow** (ENG-SBF-001): Return `{'main': good_df, 'reject': reject_df}` from `_process()`.
2. **Fix Block 2 Output BIC extraction** (ENG-SBF-002, BUG-SBF-013): Correct position offsets per SWIFT standard.
3. **Fix standalone block 86 handling** (ENG-SBF-003): Track pairing state explicitly instead of using `not block61_list`.
4. **Fix empty DataFrame columns** (ENG-SBF-008): Return `pd.DataFrame(columns=self.pipe_fields)`.
5. **Add streaming file reading** (PERF-SBF-001): Process messages in batches to control memory.
6. **Compile regex patterns** (PERF-SBF-003): Move to class-level `re.compile()`.

### Long-term (Optimization)

1. **Eliminate dict-in-data defensive code** (DBG-SBF-003): Fix root cause, remove 70+ lines of isinstance checks.
2. **Fix NB_LINE/NB_LINE_OK semantics** (ENG-SBF-009): Align with Talend convention.
3. **Add `_validate_config()` method** (STD-SBF-001): Centralize all config validation.
4. **Make field 61 continuation separator configurable** (BUG-SBF-007): Add `field61_continuation_separator` config.
5. **Consolidate single/list storage** (BUG-SBF-008): Always store multi-occurrence fields as lists.

---

## 11. Risk Assessment

This section is **required per D-79** -- SwiftBlockFormatter has 707 lines of engine code (second-largest engine component) processing financial messages.

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| **YAML layout file path traversal** | Low | High | `layout_file` config path used directly with `open()`. If config from untrusted source, arbitrary file read possible. Currently uses `yaml.safe_load()` (no code exec) but file content still exposed. Mitigate: validate path against allowed directories. |
| **YAML deserialization of untrusted layout** | Low | Medium | `yaml.safe_load()` prevents code execution but malformed YAML can cause parsing errors that crash the component. Mitigate: validate YAML structure before use. |
| **ValueError on missing pipe_fields crashes entire job** | Medium | High | `__init__()` raises `ValueError` when `pipe_fields` is empty or all entries invalid. This crashes the entire ETL job during component initialization with no graceful recovery. Mitigate: validate config before component construction, return informative error. |
| **ValueError on missing layout crashes entire job** | Medium | High | Both `__init__()` and `_ensure_layout_loaded()` raise `ValueError` for missing layout configuration. No retry or fallback mechanism. Mitigate: validate layout availability before job execution. |
| **Silent data loss from unparseable messages** | High | Critical | `_parse_single_message()` returns `None` on any exception. Failed messages are silently filtered with only a log entry. For financial data processing (bank statements, transaction records), silent data loss is unacceptable for audit compliance. Mitigate: implement REJECT flow. |
| **Block formatting edge cases: field overflow** | Medium | Medium | Fields exceeding expected fixed-width positions are not truncated or validated. Oversized BIC codes, long transaction references, or multi-line narrative text can produce malformed output rows. Mitigate: add field length validation per layout spec. |
| **Encoding issues in fixed-width output** | Low | Medium | Multi-byte characters (e.g., UTF-8 accented characters in `:86:` narrative fields) occupy more bytes than display characters, potentially misaligning fixed-width output. The component uses character-based operations, not byte-based. Mitigate: document encoding requirements for downstream consumers. |
| **Memory exhaustion on large datasets** | High | High | Entire SWIFT file loaded into memory (`file.read()`). Batch reconciliation files in banking can be multi-GB with millions of messages. No streaming or chunked processing. Mitigate: implement streaming message reader yielding one message at a time. |
| **Silent data truncation in Block 3/5** | High | Medium | Regex `[^}]*` truncates nested sub-tag content. Block 3 MUR (`{108:...}`) and Block 5 checksum (`{CHK:...}`) are silently corrupted. Downstream processes relying on these values (e.g., message correlation, integrity verification) receive incorrect data. Mitigate: fix regex to handle nested braces. |
| **Layout validation: missing or malformed definitions** | Medium | Medium | Layout YAML with wrong structure (missing `swift_layout.block4_layout`) raises `ValueError` but provides limited diagnostic information. Layout with wrong field types (neither S nor M) is not validated. Mitigate: add layout schema validation with field type enumeration. |
| **Forced DEBUG logging leaks financial data** | High | High | `logger.setLevel(logging.DEBUG)` exposes SWIFT message content (BICs, account numbers, transaction amounts) in production logs. Violates PCI-DSS and banking data protection requirements. Mitigate: remove forced DEBUG level immediately. |

### High-Risk Job Patterns

1. **Large batch files (GB-scale)**: Multi-million message reconciliation files will exhaust memory. The component has no streaming file reader -- `file.read()` loads everything at once.
2. **Messages from non-standard generators**: SWIFT messages without `-}` Block 4 terminator lose all transaction data silently.
3. **Outbound (O-type) messages**: Block 2 BIC extraction has overlapping position ranges, producing incorrect BIC for outbound messages.
4. **Messages with standalone `:86:` after `:61:` pairs**: Account information in header-level `:86:` tags is silently lost after any `:61:` is encountered.
5. **Pipeline mode with NaN data**: DataFrame input where content column has NaN in first row causes heuristic to skip valid SWIFT columns.
6. **Context variable resolving to empty path**: Empty `layout_file` path resolves to current directory (`.`) instead of raising error.

### Safe Usage Patterns

1. **Single MT940/MT950 messages**: Single-message processing works reliably for standard messages with `-}` Block 4 terminator.
2. **Small-to-medium batch files**: Files under 100MB with standard formatting parse correctly.
3. **Pipeline mode with explicit content_column**: When `content_column` is correctly configured (not relying on heuristic), DataFrame input works reliably.
4. **Inline layout configuration**: Avoids YAML file loading entirely, reducing failure points.
5. **UTF-8 encoded files**: Default encoding works for standard SWIFT ASCII content.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Engine source | `src/v1/engine/components/transform/swift_block_formatter.py` | Complete engine analysis (707 lines) |
| Base component | `src/v1/engine/base_component.py` | Cross-cutting bugs, streaming mode, stats |
| GlobalMap | `src/v1/engine/global_map.py` | GlobalMap.get() bug analysis |
| Engine registry | `src/v1/engine/engine.py` | Registry alias registration |
| Package init | `src/v1/engine/components/transform/__init__.py` | Package export verification |
| SWIFT MT940 standard | ISO 15022 / SWIFT User Handbook | Block structure, field tag definitions |

## Appendix B: Engine Class Structure

```
SwiftBlockFormatter (BaseComponent)
    Instance Variables:
        layout_file: Optional[str]           # Path to YAML layout file
        layout_spec: Optional[Dict]          # Loaded layout specification
        inline_layout: Dict                  # Inline layout fallback
        pipe_fields: List[str]               # Output column names
        pipe_fields_mapping: Dict            # Source/default mapping per field
        processing_options: Dict             # Unused processing config

    Methods:
        _init_swift_parser()                 # Init config, parse pipe_fields
        _ensure_layout_loaded()              # Lazy layout loading
        _load_layout_from_file(path) -> Dict # YAML file loading + validation
        _process(input_data) -> Dict         # Main entry point
        _parse_dataframe_input(df) -> List   # Parse SWIFT from DataFrame
        _parse_swift_file(path) -> List      # Parse SWIFT from file
        _split_messages(content) -> List     # Split multi-message content
        _parse_single_message(msg) -> Dict   # Parse one SWIFT message
        _parse_block1(msg) -> Dict           # Block 1 parsing
        _parse_block2(msg) -> Dict           # Block 2 parsing
        _parse_block3(msg) -> Dict           # Block 3 parsing
        _parse_block4_with_layout(msg) -> Dict # Block 4 with layout and 61/86 pairing
        _parse_block5(msg) -> Dict           # Block 5 parsing
        _convert_to_dataframe(msgs) -> DF    # Convert parsed messages to DataFrame
        _normalize_message_data(data) -> List # Normalize 61/86 pairs into rows
        _write_output_file(df, path)         # Write pipe-delimited output
```

---

*Report generated: 2026-03-21*
*Last updated: 2026-04-04 after gold-standard rewrite with Section 11 per D-79/D-82*
