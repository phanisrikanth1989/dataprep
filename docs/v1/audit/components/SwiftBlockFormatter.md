# Audit Report: SwiftBlockFormatter (Custom Component)

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: None (custom component -- no Talend XML conversion; config provided directly in job JSON)
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | N/A -- custom component, no Talend equivalent |
| **V1 Engine Class** | `SwiftBlockFormatter` |
| **Engine File** | `src/v1/engine/components/transform/swift_block_formatter.py` (708 lines) |
| **Converter Parser** | None -- no dedicated parser in `component_parser.py`. Not referenced in any converter code. |
| **Converter Dispatch** | None -- not referenced in `converter.py`. Configuration supplied directly in job JSON. |
| **Registry Aliases** | `SwiftBlockFormatter`, `tSwiftBlockFormatter` (registered in `src/v1/engine/engine.py` lines 144-145) |
| **Category** | Transform / Custom |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/swift_block_formatter.py` | Engine implementation (708 lines) |
| `src/v1/engine/engine.py` (lines 29, 144-145) | Import and registry alias registration |
| `src/v1/engine/components/transform/__init__.py` (lines 24, 53) | Package export |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/components/transform/swift_transformer.py` | Downstream consumer: `SwiftTransformer` takes output of `SwiftBlockFormatter` |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **N/A** | -- | -- | -- | -- | Custom component; no Talend conversion needed. Config is hand-authored JSON/YAML. |
| Engine Feature Completeness | **Y** | 1 | 4 | 5 | 2 | Core SWIFT parsing works; edge cases around regex, block pairing, NaN, empty input, and streaming are problematic |
| Code Quality | **Y** | 2 | 5 | 5 | 3 | Cross-cutting base class bugs; debug logging forced to DEBUG in production; dict-in-data defensive code masks real bugs; no input validation; regex truncation corrupts Block 3/5 data |
| Performance & Memory | **Y** | 0 | 1 | 2 | 1 | Entire file read into memory; no streaming for large SWIFT files; quadruple validation pass on every row |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero unit tests; zero integration tests; 708 lines of completely unverified code |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Component Design Baseline

### What SwiftBlockFormatter Does

`SwiftBlockFormatter` is a custom component that parses SWIFT (Society for Worldwide Interbank Financial Telecommunication) messages and converts them into a flat, pipe-delimited DataFrame. SWIFT messages follow the MT (Message Type) standard with a five-block structure:

- **Block 1** (Basic Header): Application ID, service ID, BIC, session, sequence number
- **Block 2** (Application Header): Direction (I/O), message type (e.g., 940, 950), BIC, timestamps
- **Block 3** (User Header): User-defined content (banking references, priorities)
- **Block 4** (Text Block): The message body containing tagged fields (`:20:`, `:61:`, `:86:`, etc.)
- **Block 5** (Trailer): Checksum and authentication data

The component's primary purpose is to normalize multi-occurrence field 61 (Statement Line) / field 86 (Information to Account Owner) pairs. A single MT940 statement message may contain hundreds of `:61:`/`:86:` pairs representing individual transactions. The component "explodes" these into one row per 61/86 pair while repeating all single-occurrence header fields (`:20:`, `:25:`, etc.) across each row.

**Component family**: Transform / Custom SWIFT
**Input**: DataFrame with SWIFT message content OR raw SWIFT file path
**Output**: Flat DataFrame with one row per 61/86 pair, columns defined by `pipe_fields` config

### 3.1 Configuration Parameters

| # | Parameter | Config Key | Type | Required | Default | Description |
|---|-----------|------------|------|----------|---------|-------------|
| 1 | Layout File | `layout_file` | String (path) | Yes* | -- | Path to YAML file defining Block 4 field types. Must contain `swift_layout.block4_layout` key. Supports context variables. |
| 2 | Inline Layout | `layout` | Dict | Yes* | `{}` | Alternative to `layout_file`: inline dict mapping field keys (e.g., `block4_20`) to types (`S` for single, `M` for multiple). |
| 3 | Pipe Fields | `pipe_fields` | List | Yes | -- | Output column definitions. Each element is either a string (field name = source) or a dict with `name`, `source`, `default` keys. |
| 4 | Input File | `input_file` | String (path) | No | -- | Path to SWIFT message file. Required when no input DataFrame is provided. |
| 5 | Content Column | `content_column` | String | No | `"content"` | Column name in input DataFrame containing SWIFT message text. |
| 6 | Output File | `output_file` | String (path) | No | -- | If set, writes the result DataFrame to this path as pipe-delimited CSV. |
| 7 | Encoding | `encoding` | String | No | `"UTF-8"` | Character encoding for reading input SWIFT file. |
| 8 | Output Encoding | `output_encoding` | String | No | `"UTF-8"` | Character encoding for writing output file. |
| 9 | Delimiter | `delimiter` | String | No | `"\|"` | Delimiter for output file writing (default pipe). |
| 10 | Include Header | `include_header` | Boolean | No | `true` | Whether to include column headers in output file. |
| 11 | Die On Error | `die_on_error` | Boolean | No | `true` | Raise exception on error vs. return empty DataFrame. |
| 12 | Processing | `processing` | Dict | No | `{}` | Processing options (currently unused -- stored but never read). |
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
|-----------|-----------|------|-------------|
| `main` (input) | Input | DataFrame | DataFrame with SWIFT message content in a column |
| `main` (output) | Output | DataFrame | Flat DataFrame with one row per 61/86 pair |
| N/A | N/A | REJECT | **No reject flow implemented** |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of SWIFT messages parsed (NOT output rows) |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of output rows produced |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Always 0 -- no reject mechanism |
| `{id}_EXECUTION_TIME` | Float | After execution | Execution time in seconds (v1-specific) |

### 3.5 Behavioral Notes

1. **Layout deferred loading**: The layout file is NOT loaded during `__init__()`. It is loaded lazily in `_ensure_layout_loaded()`, called at the start of `_process()`. This allows context variables in `layout_file` to be resolved first.

2. **Block 61/86 pairing logic**: Field 61 (Statement Line) and field 86 (Information to Account Owner) are treated as paired entries. When a `:61:` tag is encountered, the parser checks if the next field is `:86:`. If so, they are paired. If not, an empty string is used for the 86 value. This creates the normalization axis: one output row per 61/86 pair.

3. **Field continuation lines**: Lines in Block 4 that do not start with a field tag pattern (`:NN:` or `:NNA:`) are treated as continuation lines of the current field. For field 61, continuation lines are joined with `sfield9=`. For all other fields, continuation lines are joined with a space.

4. **Layout filter**: Only fields whose key (e.g., `block4_20`) appears in the layout specification are processed. Unrecognized fields are silently dropped.

5. **Message splitting**: Messages in a multi-message file are split using the pattern `{1:...}` as a message boundary. If this pattern fails, the fallback splits by double newlines.

6. **No input DataFrame column validation**: When receiving DataFrame input, if the configured `content_column` is not found, the component heuristically searches for any column whose first row contains `{` and `:` characters.

---

## 4. Converter Audit

### 4.1 Converter Status

**No converter exists for this component.** `SwiftBlockFormatter` is a custom component with no Talend equivalent. It does not appear in `component_parser.py` or `converter.py`. Configuration is supplied directly in job JSON files.

This is architecturally correct -- custom components do not need converter support. However, this means all configuration must be manually authored and validated, with no automated extraction from Talend XML metadata.

### 4.2 Configuration Validation Gap

| ID | Priority | Issue |
|----|----------|-------|
| CONV-SBF-001 | **P2** | **No configuration schema validation**: Unlike Talend-converted components that go through `_map_component_parameters()` with known parameter names, custom component configs have zero validation at the converter level. Invalid keys, typos in field names, or wrong types are not caught until runtime. A JSON schema or explicit validation in `__init__` would prevent misconfiguration. |

---

## 5. Engine Feature Audit

### 5.1 Feature Implementation Status

| # | Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|---------|-------------|----------|-----------------|-------|
| 1 | Parse Block 1 (Basic Header) | **Yes** | Medium | `_parse_block1()` line 289 | Fixed-position parsing of app_id, service_id, BIC, session, sequence |
| 2 | Parse Block 2 (Application Header) | **Yes** | Medium | `_parse_block2()` line 308 | Handles both Input (I) and Output (O) directions |
| 3 | Parse Block 3 (User Header) | **Yes** | Low | `_parse_block3()` line 331 | Stores raw content only -- no sub-tag parsing |
| 4 | Parse Block 4 (Text Block) with layout | **Yes** | High | `_parse_block4_with_layout()` line 344 | Core parsing with field tag recognition, multi-line, 61/86 pairing |
| 5 | Parse Block 5 (Trailer) | **Yes** | Low | `_parse_block5()` line 522 | Stores raw content only -- no sub-field extraction |
| 6 | Layout from YAML file | **Yes** | High | `_load_layout_from_file()` line 95 | YAML loading with type validation |
| 7 | Layout from inline config | **Yes** | High | `_ensure_layout_loaded()` line 81 | Fallback to `self.inline_layout` |
| 8 | Multi-message file splitting | **Yes** | Medium | `_split_messages()` line 245 | Regex-based with empty-line fallback |
| 9 | DataFrame input (pipeline mode) | **Yes** | Medium | `_parse_dataframe_input()` line 191 | Heuristic column detection |
| 10 | File input (standalone mode) | **Yes** | High | `_parse_swift_file()` line 218 | Direct file reading |
| 11 | 61/86 field pairing | **Yes** | High | `_parse_block4_with_layout()` line 423 | Core normalization logic |
| 12 | Multiple occurrence fields (M type) | **Yes** | High | `_parse_block4_with_layout()` line 469 | Collected into lists |
| 13 | Single occurrence fields (S type) | **Yes** | High | `_parse_block4_with_layout()` line 476 | First occurrence kept, duplicates silently ignored |
| 14 | Pipe-delimited output file | **Yes** | High | `_write_output_file()` line 688 | Uses `pd.to_csv()` |
| 15 | Field continuation lines | **Yes** | Medium | `_parse_block4_with_layout()` line 396 | Appended to current field |
| 16 | Context variable in layout_file | **Yes** | High | `_ensure_layout_loaded()` line 86 | Via `context_manager.resolve_string()` |
| 17 | Die on error toggle | **Yes** | High | `_process()` line 184 | Raises or returns empty DF |
| 18 | Schema validation | **Partial** | Low | `_convert_to_dataframe()` line 604 | Only applied if `output_schema` attribute exists |
| 19 | **REJECT flow** | **No** | N/A | -- | No reject mechanism for unparseable messages |
| 20 | **Streaming / large file support** | **No** | N/A | -- | Entire file read into memory; no chunked parsing |
| 21 | **Field tag with letter suffix (e.g., :60F:, :62M:)** | **Partial** | Low | Line 368 regex | Regex `(\d{2}[A-Z]?)` matches 2-digit + optional single letter. Does NOT match `:60F:` correctly -- see BUG-SBF-003 |

### 5.2 Behavioral Issues

| ID | Priority | Description |
|----|----------|-------------|
| ENG-SBF-001 | **P1** | **No REJECT flow**: Unparseable SWIFT messages are silently dropped (returning `None` from `_parse_single_message()` on line 287). No error details are captured. No reject DataFrame is produced. For financial message processing, silent data loss is unacceptable. Every dropped message should be logged with reason and available downstream. |
| ENG-SBF-002 | **P1** | **Block 2 Output message BIC extraction is wrong**: In `_parse_block2()` line 327, for Output ('O') messages, `block2bic` is extracted from positions `[14:26]` but the preceding field `block2_mir` is extracted from `[10:22]`. These ranges overlap (positions 14-21 are shared). The SWIFT standard for Output Block 2 is: direction(1) + msg_type(3) + input_time(4) + MIR(28) + output_date(6) + output_time(4) + priority(1). The BIC should be extracted from within the MIR field or from a different offset. |
| ENG-SBF-003 | **P1** | **Standalone block 86 handling is incorrect when block61_list is non-empty**: On line 452, the condition `elif field_tag == '86' and not block61_list` means that once ANY block 61 has been seen, ALL subsequent standalone block 86 entries (those not immediately following a 61) are caught by the `elif field_tag == '86':` branch on line 463 and silently skipped (`i += 1` only). This means standalone 86 fields (e.g., `:86:` at message-header level providing account information) that appear AFTER the first `:61:` are lost. |
| ENG-SBF-004 | **P1** | **Trailing empty block 86 values are stripped**: Lines 487-488 strip trailing empty strings from `block86_list`. This changes the pairing between 61 and 86 entries. If the last `:61:` has no corresponding `:86:`, the empty entry is removed, but `block61_list` retains all entries. This causes a length mismatch in `_normalize_message_data()` where `block4_86` has fewer entries than `block4_61`. While the padding logic on lines 636-637 adds empty strings back, the intermediate single/list decision on line 491 (`block86_list if len(block86_list) > 1 else block86_list[0]`) could produce incorrect results when all 86 values were empty and stripped. |
| ENG-SBF-005 | **P2** | **`processing` config option is stored but never used**: Line 77 stores `self.processing_options` but no code ever reads it. Dead configuration. |
| ENG-SBF-006 | **P2** | **No streaming support for large SWIFT files**: The entire SWIFT file is read into memory at once (`file.read()` on line 227). For files containing millions of SWIFT messages (common in batch reconciliation), this causes memory exhaustion. The `HYBRID` execution mode inherited from `BaseComponent` only chunks the input DataFrame -- it does not provide chunked file reading. |
| ENG-SBF-007 | **P2** | **Heuristic column detection is fragile**: In `_parse_dataframe_input()` lines 200-206, when the configured `content_column` is not found, the code searches for ANY column whose first row contains `{` and `:`. This matches JSON data, Python dicts, URLs with ports, and many other non-SWIFT content. The heuristic should at minimum check for `{1:` or `{4:` as SWIFT-specific markers. |
| ENG-SBF-008 | **P2** | **Empty DataFrame on zero messages has no columns**: On line 165, when no SWIFT messages are found, `pd.DataFrame()` is returned with no column definitions. Downstream components expecting specific columns will fail. Should return `pd.DataFrame(columns=self.pipe_fields)`. |
| ENG-SBF-009 | **P2** | **`_update_stats` conflates message count with row count**: Line 176 calls `_update_stats(len(swift_messages), len(result_df), 0)`. `NB_LINE` counts messages and `NB_LINE_OK` counts output rows. Since normalization expands 61/86 pairs, `NB_LINE_OK` can be much larger than `NB_LINE`. This breaks the Talend convention where `NB_LINE = NB_LINE_OK + NB_LINE_REJECT`. |
| ENG-SBF-010 | **P3** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur with `die_on_error=false`, the error message is not stored in globalMap for downstream reference. |
| ENG-SBF-011 | **P3** | **Block 3 sub-tags not parsed**: Block 3 can contain sub-tags like `{108:...}` (MUR), `{113:...}` (banking priority). These are stored as a single raw string. |

### 5.3 GlobalMap Variable Coverage

| Variable | Expected? | V1 Sets? | How V1 Sets It | Notes |
|----------|-----------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` | Set to message count, not row count |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Set to output row count (can exceed NB_LINE due to normalization) |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Always 0 -- no reject mechanism |
| `{id}_ERROR_MESSAGE` | Expected | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-SBF-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement uses `{stat_name}: {value}` but the loop variable is `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: Affects ALL components, not just SwiftBlockFormatter, since `_update_global_map()` is called after every component execution via `execute()` line 218. |
| BUG-SBF-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: Method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-SBF-003 | **P1** | `swift_block_formatter.py:368` | **Field tag regex does not match 2-digit tags with letter suffixes correctly for all SWIFT fields**: The regex `r':(\d{2}[A-Z]?):(.*)'` expects exactly 2 digits followed by an optional single uppercase letter. This correctly matches `:20:`, `:61:`, `:86:`, `:60F:`, `:62F:`, `:25:`. However, SWIFT MT messages also contain field tags like `:28C:` (Statement Number/Sequence Number) which this regex handles correctly, but real-world SWIFT messages can have 3-digit tags in certain MT types (e.g., `:258:` in MT300). The pattern `\d{2}` strictly limits to 2-digit tags, silently dropping any 3-digit tagged fields. |
| BUG-SBF-004 | **P1** | `swift_block_formatter.py:149` | **Logger level forced to DEBUG in production**: Line 149 calls `logger.setLevel(logging.DEBUG)` unconditionally inside `_process()`. This overrides whatever log level the application has configured (e.g., INFO or WARNING in production). Every invocation of this component enables DEBUG logging for the entire logger hierarchy under this module. This is a debug artifact that will flood production logs. |
| BUG-SBF-005 | **P1** | `swift_block_formatter.py:349` | **Block 4 regex `\{4:(.*?)-\}` requires trailing hyphen before closing brace**: The SWIFT standard terminates Block 4 with `-}` (hyphen then close brace). However, some SWIFT message generators omit the trailing hyphen, producing `{4:...}` without the `-}` terminator. The regex will fail to match Block 4 content in these messages, causing all Block 4 data to be lost. The regex should be `r'\{4:(.*?)(?:-\}|\})'` to handle both cases. |
| BUG-SBF-006 | **P2** | `swift_block_formatter.py:251` | **Message split regex non-greedy `.*?` with `re.DOTALL` may fail on edge cases**: The pattern `r'(\{1:[^}]*\}.*?)(?=\{1:|$)'` with `re.DOTALL` uses `.*?` (non-greedy) which matches as little as possible. Since the lookahead checks for `{1:` OR end-of-string, the non-greedy match will stop at the FIRST `{1:` encountered anywhere in the message content (including inside Block 4 text). While `{1:` appearing inside message body is extremely rare in real SWIFT data, the regex has no protection against it. A more robust approach would split on `{1:` boundaries first, then reassemble. |
| BUG-SBF-007 | **P2** | `swift_block_formatter.py:377-379` | **Field 61 continuation line joining uses `sfield9=` literal string**: When field 61 has continuation lines, they are joined with the string `sfield9=` (line 378: `field_value = field_value.replace('\n', 'sfield9=')`). This appears to be a domain-specific convention for marking the supplementary details (sub-field 9) of a `:61:` field. However, this hardcoded string is not configurable and will corrupt data if the actual SWIFT field 61 content itself contains `sfield9=`. A configurable separator or proper sub-field extraction would be safer. |
| BUG-SBF-008 | **P2** | `swift_block_formatter.py:483-491` | **Single-item list vs. scalar inconsistency in block4 data storage**: When `block61_list` has exactly one entry, line 483 stores it as a scalar string (`block61_list[0]`). When it has multiple entries, it stores as a list. The same logic applies to `block86_list` (line 491). `_normalize_message_data()` then checks `isinstance(block4_61_data, str)` and wraps it back into a list (line 619). This scalar/list duality creates fragile code. If any intermediate processing step accidentally wraps or unwraps, data is corrupted. |
| BUG-SBF-009 | **P2** | `swift_block_formatter.py:201` | **`iloc[0]` on empty DataFrame raises IndexError**: Line 201 calls `input_data[col].iloc[0]` inside a guard `if len(input_data) > 0`, but the `for col in input_data.columns` loop iterates all columns even if the DataFrame has zero rows. The guard protects the `iloc[0]` call, but the `else` clause (line 202) is `""` which means the heuristic falls through to the `for...else` raise. This is correct behavior but confusing control flow. More critically, if the DataFrame has rows but a column contains NaN/None in the first row, `str(input_data[col].iloc[0])` converts to `"nan"` which contains neither `{` nor `:`, so the heuristic skips valid SWIFT content columns that happen to have a NaN first row. |
| BUG-SBF-010 | **P3** | `swift_block_formatter.py:293-304` | **Block 1 BIC extraction has overlapping/incorrect position ranges**: The comment says `len(block1_content) >= 11` but then extracts BIC from positions `[3:15]` (12 chars) requiring length > 14. Standard Block 1 is 25 characters: `F01BANKBEBBAXXX0168497562`. BIC is positions 3-14 (12 characters, including logical terminal and branch). The length guards (`len > 14`, `len > 18`, `len > 24`) are correct for full-length messages but the `>= 11` initial check is misleading -- a content of length 11 would produce empty BIC (`block1_content[3:]` would be 8 chars, not 12). |
| BUG-SBF-012 | **P1** | `swift_block_formatter.py:331,522` | **Block 3 and Block 5 regex `[^}]*` truncates at first `}`, silently corrupting content**: The regex patterns for Block 3 (`r'\{3:([^}]*)\}'`) and Block 5 (`r'\{5:([^}]*)\}'`) use `[^}]*` which stops matching at the first `}` character. Standard SWIFT has nested sub-tags like `{3:{108:MT940}{113:xxxx}}` -- the regex captures only `{108:MT940` (truncated, missing closing brace and second sub-tag). This is not merely "low fidelity" raw storage -- it is actual data corruption. Any downstream code relying on Block 3 or Block 5 content (e.g., MUR extraction from `{108:...}`, banking priority from `{113:...}`, checksum from `{CHK:...}`) receives silently truncated data. |
| BUG-SBF-013 | **P1** | `swift_block_formatter.py:308-327` | **Block 2 Output BIC fallback offset inconsistency**: In `_parse_block2()`, the primary path extracts the BIC for Output ('O') messages using positions `[14:26]`, but the fallback extraction path uses `[16:]` -- a 2-character discrepancy. This means the BIC produced depends on which code path executes (determined by content length), yielding different BIC values for the same logical field depending on message length. One path is necessarily wrong, and the inconsistency makes debugging extremely difficult since the result varies silently per message. |
| BUG-SBF-014 | **P2** | `swift_block_formatter.py` (`_normalize_message_data`) | **`_normalize_message_data` silently discards all but first element of any M-type field (other than 61/86) used as `pipe_field` source**: When a field is declared as `M` (multiple occurrence) in the layout and appears more than once in a message, the parser correctly collects all occurrences into a list. However, `_normalize_message_data()` only expands 61/86 pairs into multiple rows. For any other M-type field used as a `pipe_field` source, the list is either serialized to a string representation or only the first element is taken, with no warning emitted. All occurrences beyond the first are silently lost. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-SBF-001 | **P3** | **Inconsistent naming between `messagetype` (no underscore) and `block1_app_id` (with underscores)**: Block 1/2/3/5 fields use `block{N}_fieldname` convention. But `messagetype` (line 274) breaks this convention. Should be `block2_msg_type` (which is also separately stored on line 320). |
| NAME-SBF-002 | **P3** | **`pipe_fields` vs `pipe_fields_mapping` dual data structures**: `self.pipe_fields` is a list of field names (line 54). `self.pipe_fields_mapping` is a dict with source/default (line 55). These are always used together but maintained separately. Could be a single OrderedDict. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-SBF-001 | **P2** | "Every component SHOULD have `_validate_config()` returning `List[str]`" (METHODOLOGY.md) | No `_validate_config()` method exists. Configuration validation is scattered across `__init__` (pipe_fields) and `_ensure_layout_loaded()` (layout). No centralized validation. |
| STD-SBF-002 | **P2** | "No forced log level changes in component code" (implied standard) | Line 149 calls `logger.setLevel(logging.DEBUG)` unconditionally, overriding application-level logging configuration. |
| STD-SBF-003 | **P3** | "No `print()` statements" (STANDARDS.md) | No print statements found -- compliant. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-SBF-001 | **P1** | **`logger.setLevel(logging.DEBUG)` on line 149**: Forces DEBUG level for every invocation. This is a debug artifact from development that was never removed before integration. |
| DBG-SBF-002 | **P3** | **Commented-out debug log lines**: Lines 542 (`#logger.debug(...)`) and 554 (`#logger.debug(...)`) contain commented-out debug statements. Should be removed or converted to proper conditional debug logging. |
| DBG-SBF-003 | **P3** | **Excessive defensive dict-checking code**: Lines 496-518 (block4_data dict validation), lines 545-551 (message dict check), lines 562-570 (row validation), lines 573-592 (validated_rows construction) contain 70+ lines of defensive code checking for dict values in what should be string data. This suggests the code was written to work around a real bug (dict values leaking into data) rather than fixing the root cause. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-SBF-001 | **P2** | **YAML layout file loaded with `yaml.safe_load()` -- correct**: Uses `safe_load` not `load`, preventing arbitrary code execution via YAML deserialization. |
| SEC-SBF-002 | **P3** | **No path traversal protection on `layout_file` or `input_file`**: File paths from config are used directly with `os.path.exists()` and `open()`. If config comes from untrusted sources, path traversal is possible. Not a concern for trusted job configs. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages include `f"Component {self.id}: ..."` -- correct |
| Level usage | **BROKEN** -- `logger.setLevel(logging.DEBUG)` forced on line 149 overrides all level configuration. Many `logger.error()` calls for dict-in-data situations that should be `logger.warning()` at most. |
| Start/complete logging | `_init_swift_parser()` logs initialization (line 79). `_process()` logs completion with counts (line 178). No explicit start log for `_process()`. |
| Sensitive data | SWIFT message content may contain account numbers, BICs, and transaction amounts. These are logged at DEBUG level in several places. With the forced DEBUG level (line 149), this is a data leakage concern in production. |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Does not use custom exceptions from `exceptions.py`. Raises generic `ValueError` and `RuntimeError`. |
| Exception chaining | Does NOT use `raise ... from e` pattern. Line 138: `raise ValueError(f"Failed to load layout configuration: {str(e)}")` -- original exception is lost. |
| `die_on_error` handling | Single try/except in `_process()` (lines 144-189). Correctly raises or returns empty DF based on flag. |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID and relevant context -- mostly correct |
| Graceful degradation | Returns empty DataFrame when `die_on_error=false` -- correct |
| Silent message drops | `_parse_single_message()` returns `None` on ANY exception (line 287), which `_parse_swift_file()` silently filters out (line 235 `if parsed_msg`). Failed messages are logged but not counted or available downstream. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All public methods have return type hints -- correct |
| Parameter types | `_process()`, `_parse_dataframe_input()`, etc. all have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]`, `List[Dict[str, Any]]`, `List[str]`, `List[List[str]]` -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-SBF-001 | **P1** | **Entire SWIFT file read into memory at once**: `_parse_swift_file()` line 227 calls `file.read()` which loads the complete file into a single string. For batch reconciliation files containing millions of MT940 messages (common in banking -- files can be multiple GB), this causes memory exhaustion. The file should be read and split in a streaming fashion, processing messages one at a time. |
| PERF-SBF-002 | **P2** | **Quadruple iteration over row data for dict-checking**: `_convert_to_dataframe()` iterates over all rows 4 times: (1) lines 545-551 check message dicts, (2) lines 562-570 check row items, (3) lines 574-592 validate/stringify all items, (4) DataFrame construction. For large result sets (100K+ rows from a batch file), this creates significant overhead. A single pass should combine all validation. |
| PERF-SBF-003 | **P2** | **Regex compilation not cached**: `_parse_block1()`, `_parse_block2()`, `_parse_block3()`, `_parse_block4_with_layout()`, `_parse_block5()`, `_split_messages()`, and `_parse_single_message()` all call `re.search()` or `re.match()` with string patterns that are recompiled on every call. For thousands of messages, these should be compiled once at class level (`re.compile()`). |
| PERF-SBF-004 | **P3** | **String concatenation in field value building**: `_parse_block4_with_layout()` uses `'\n'.join(current_value)` followed by `.replace('\n', ...)` (lines 374-379). For fields with many continuation lines, the join+replace is O(n) twice. Minor for typical SWIFT messages (few continuation lines) but could matter for `:86:` fields with extensive narrative text. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | NOT implemented for SWIFT file reading. `_parse_swift_file()` reads entire file into memory. BaseComponent's HYBRID mode only chunks DataFrame processing, not file I/O. |
| Memory threshold | 3072 MB (3GB) inherited from BaseComponent. Irrelevant since file is fully loaded before mode selection. |
| Chunked processing | Not available for SWIFT parsing. Each message is parsed independently, so chunked processing is architecturally feasible but not implemented. |
| Output DataFrame construction | `all_rows` list accumulates all normalized rows in memory before DataFrame creation. For files with millions of 61/86 pairs, this doubles memory usage (raw list + DataFrame). |

### 7.2 Streaming Mode Limitations

| Issue | Description |
|-------|-------------|
| File reading | `file.read()` loads entire file. No streaming file reader. |
| Message splitting | `_split_messages()` operates on the complete file content string. Cannot work on chunks. |
| DataFrame input | When input is a DataFrame (pipeline mode), BaseComponent's streaming mode chunks the input DataFrame. Each chunk is processed by `_process()` independently. This works but re-loads the layout file for each chunk (since `_ensure_layout_loaded()` checks `self.layout_spec is None` which is set on first call). |
| Output accumulation | `_convert_to_dataframe()` builds the complete result in memory. No chunked output. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `SwiftBlockFormatter` |
| V1 engine integration tests | **No** | -- | No integration tests found |
| Sample SWIFT test data | **No** | -- | No YAML layout files or sample SWIFT messages in repository |

**Key finding**: The v1 engine has ZERO tests for this component. All 708 lines of v1 engine code are completely unverified. No sample layout YAML files or test SWIFT messages exist in the repository.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic MT940 parse | P0 | Parse a single MT940 message with blocks 1-5, verify all block fields extracted correctly |
| 2 | 61/86 pairing (single pair) | P0 | Single `:61:` followed by `:86:`, verify one output row with both values |
| 3 | 61/86 pairing (multiple pairs) | P0 | Three `:61:`/`:86:` pairs, verify three output rows with correct pairing and header field repetition |
| 4 | 61 without matching 86 | P0 | `:61:` with no following `:86:`, verify empty string for 86 value |
| 5 | Layout loading from YAML | P0 | Load valid YAML layout file, verify field filtering works (unlisted fields dropped) |
| 6 | Missing layout file | P0 | Non-existent layout file path, verify `ValueError` raised with descriptive message |
| 7 | Empty pipe_fields config | P0 | Empty `pipe_fields` list, verify `ValueError` raised during `__init__` |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Multi-message file | P1 | File with 3 MT940 messages, verify all 3 parsed and output rows correctly accumulated |
| 9 | Field continuation lines | P1 | `:86:` field spanning 4 lines, verify lines joined with space separator |
| 10 | Field 61 continuation | P1 | `:61:` field with supplementary details on next line, verify `sfield9=` joining |
| 11 | DataFrame input (pipeline mode) | P1 | Input DataFrame with `content` column containing SWIFT messages, verify correct parsing |
| 12 | Heuristic column detection | P1 | DataFrame without `content` column but with SWIFT data in `raw_msg` column, verify heuristic finds correct column |
| 13 | Die on error=true | P1 | Malformed SWIFT message with `die_on_error=true`, verify `RuntimeError` raised |
| 14 | Die on error=false | P1 | Malformed SWIFT message with `die_on_error=false`, verify empty DataFrame returned and stats updated |
| 15 | Output file writing | P1 | Verify pipe-delimited output file matches expected content |
| 16 | GlobalMap stats | P1 | Verify `{id}_NB_LINE` and `{id}_NB_LINE_OK` set correctly in globalMap after execution |
| 17 | Block 2 Input vs Output | P1 | Parse both I-type and O-type Block 2 headers, verify correct field extraction for each direction |
| 18 | Inline layout config | P1 | Use `layout` dict instead of `layout_file`, verify same behavior |
| 19 | Context variable in layout_file | P1 | `${context.config_dir}/swift_layout.yaml` should resolve via context manager |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 20 | Empty SWIFT file | P2 | Empty input file, verify empty DataFrame returned without error |
| 21 | NaN in content column | P2 | DataFrame input where first row of content column is NaN, verify heuristic handles correctly |
| 22 | Empty string content | P2 | DataFrame with empty string values in content column, verify no crash |
| 23 | Block 4 without trailing hyphen | P2 | `{4:...}` instead of `{4:...-}`, verify parsing still works (currently FAILS -- see BUG-SBF-005) |
| 24 | Large file (1000+ messages) | P2 | Performance test: parse file with 1000 MT940 messages, verify memory and time within bounds |
| 25 | Layout with non-string values | P2 | YAML layout containing integer or boolean values, verify conversion to string (current behavior) |
| 26 | Standalone 86 after 61/86 pairs | P2 | Message with `:86:` providing account info at header level, followed by `:61:`/`:86:` pairs, verify standalone 86 not lost |
| 27 | pipe_fields with dict config | P2 | `pipe_fields` entries using dict format with `name`, `source`, `default`, verify field mapping works |
| 28 | Encoding ISO-8859-1 | P2 | SWIFT file with non-UTF8 characters, verify correct decoding with configured encoding |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-SBF-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-SBF-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-SBF-001 | Testing | Zero v1 unit tests. Zero integration tests. All 708 lines completely unverified. No sample SWIFT test data in repository. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| ENG-SBF-001 | Engine | **No REJECT flow** -- unparseable SWIFT messages silently dropped. For financial data processing, silent data loss is unacceptable. |
| ENG-SBF-002 | Engine | Block 2 Output message BIC extraction has overlapping position ranges with MIR field. Produces incorrect BIC for outbound messages. |
| ENG-SBF-003 | Engine | Standalone block 86 entries lost when they appear after any block 61. Only `:86:` entries immediately following `:61:` are paired; all others after the first `:61:` are silently skipped. |
| ENG-SBF-004 | Engine | Trailing empty block 86 values stripped, causing potential single/list type inconsistency in 61/86 pairing. |
| BUG-SBF-003 | Bug | Field tag regex limited to 2-digit tags. Any 3-digit SWIFT tags (rare but possible in certain MT types) are silently dropped. |
| BUG-SBF-004 | Bug (Debug Artifact) | `logger.setLevel(logging.DEBUG)` forced unconditionally in `_process()`, flooding production logs with DEBUG output and potentially leaking sensitive financial data. |
| BUG-SBF-005 | Bug | Block 4 regex requires `-}` terminator. SWIFT messages without trailing hyphen lose all Block 4 content. |
| BUG-SBF-012 | Bug | Block 3 and Block 5 regex `[^}]*` truncates at first `}`, silently corrupting nested sub-tag content like `{3:{108:MT940}{113:xxxx}}`. Actual data corruption, not just low fidelity. |
| BUG-SBF-013 | Bug | Block 2 Output BIC fallback offset inconsistency: primary path uses `[14:26]` but fallback uses `[16:]` -- 2-character discrepancy produces different BIC depending on content length. |
| PERF-SBF-001 | Performance | Entire SWIFT file read into memory. No streaming support for large batch files (GB-scale). |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-SBF-001 | Configuration | No schema validation for custom component config. Invalid keys or types not caught until runtime. |
| ENG-SBF-005 | Engine | `processing` config option stored but never used (dead configuration). |
| ENG-SBF-006 | Engine | No streaming support for large SWIFT files. File entirely in memory before processing. |
| ENG-SBF-007 | Engine | Heuristic column detection matches any content with `{` and `:`, not SWIFT-specific patterns. False positives on JSON, URLs, Python dicts. |
| ENG-SBF-008 | Engine | Empty DataFrame returned on zero messages has no column definitions, breaking downstream expectations. |
| ENG-SBF-009 | Engine | `_update_stats` conflates message count (NB_LINE) with output row count (NB_LINE_OK), violating Talend convention. |
| BUG-SBF-006 | Bug | Message split regex non-greedy `.*?` with `re.DOTALL` could false-split on `{1:` appearing inside message body content (extremely rare but unprotected). |
| BUG-SBF-007 | Bug | Field 61 continuation line joining uses hardcoded `sfield9=` string. Not configurable and could corrupt data if content contains this literal. |
| BUG-SBF-008 | Bug | Single-item list vs. scalar inconsistency in block4 data storage creates fragile code requiring defensive isinstance checks. |
| BUG-SBF-009 | Bug | NaN first row in content column causes heuristic to skip valid SWIFT content columns. |
| BUG-SBF-014 | Bug | `_normalize_message_data` silently discards all but first element of any M-type field (other than 61/86) used as `pipe_field` source. No warning emitted. |
| STD-SBF-001 | Standards | No `_validate_config()` method. Configuration validation scattered across init and execution. |
| STD-SBF-002 | Standards | Forced `logger.setLevel(logging.DEBUG)` overrides application logging configuration. |
| SEC-SBF-001 | Security | `yaml.safe_load()` used correctly for YAML parsing -- no vulnerability. (Positive finding.) |
| PERF-SBF-002 | Performance | Quadruple iteration over row data for dict-checking. Should be single pass. |
| PERF-SBF-003 | Performance | Regex patterns not compiled/cached. Recompiled on every message parse. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| ENG-SBF-010 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap on error. |
| ENG-SBF-011 | Engine | Block 3 sub-tags not parsed. Stored as raw string. |
| BUG-SBF-010 | Bug | Block 1 length guard `>= 11` is misleading for subsequent position extractions requiring length > 24. |
| NAME-SBF-001 | Naming | `messagetype` (no underscore) inconsistent with `block1_app_id` (with underscore) convention. |
| NAME-SBF-002 | Naming | `pipe_fields` and `pipe_fields_mapping` are dual data structures for the same concern. |
| SEC-SBF-002 | Security | No path traversal protection on `layout_file` or `input_file`. Low risk for trusted config. |
| DBG-SBF-002 | Debug | Commented-out debug log lines on lines 542 and 554. |
| DBG-SBF-003 | Debug | 70+ lines of defensive dict-checking code masking a root cause bug rather than fixing it. |
| PERF-SBF-004 | Performance | String join+replace for field continuation is O(n) twice. Minor impact for typical SWIFT fields. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 10 | 4 engine, 5 bugs, 1 performance |
| P2 | 16 | 5 engine, 1 converter, 5 bugs, 2 standards, 1 security (positive), 2 performance |
| P3 | 9 | 2 engine, 1 bug, 2 naming, 1 security, 2 debug, 1 performance |
| **Total** | **38** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-SBF-001): Change `value` to `stat_value` on `base_component.py` line 304, or better, remove the stale `{stat_name}: {value}` reference entirely. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-SBF-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. **Impact**: Fixes ALL components. **Risk**: Very low.

3. **Remove forced DEBUG log level** (BUG-SBF-004): Delete line 149 (`logger.setLevel(logging.DEBUG)`). This is the single highest-impact one-line fix for this component -- it eliminates production log flooding and sensitive data leakage. **Risk**: None.

4. **Fix Block 4 regex for optional hyphen** (BUG-SBF-005): Change `r'\{4:(.*?)-\}'` to `r'\{4:(.*?)(?:-\}|\})'` to handle SWIFT messages without trailing hyphen. **Risk**: Very low.

5. **Create unit test suite** (TEST-SBF-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. Create sample SWIFT MT940 test messages and YAML layout files in the test fixtures directory.

### Short-Term (Hardening)

6. **Implement REJECT flow** (ENG-SBF-001): Instead of returning `None` from `_parse_single_message()`, return both a parsed result and a list of errors. Collect failed messages into a reject DataFrame with `errorCode`, `errorMessage`, and raw message content. Return `{'main': good_df, 'reject': reject_df}` from `_process()`.

7. **Fix Block 2 BIC extraction** (ENG-SBF-002): Correct the position offsets for Output message BIC parsing. The SWIFT Block 2 Output format is: `O` + msg_type(3) + input_time(4) + MIR(28) + output_date(6) + output_time(4) + priority(1). Validate against the SWIFT User Handbook.

8. **Fix Block 4 regex for optional hyphen** (BUG-SBF-005): Change the regex from `r'\{4:(.*?)-\}'` to `r'\{4:(.*?)(?:-\}|\})'` to handle SWIFT messages without the standard `-}` terminator.

9. **Fix standalone block 86 handling** (ENG-SBF-003): The condition on line 452 (`elif field_tag == '86' and not block61_list`) should instead track whether we are currently "inside" a 61/86 pairing section. Standalone 86 entries (before the first 61 or clearly not paired) should be stored as regular fields.

10. **Fix empty DataFrame column definition** (ENG-SBF-008): Change line 165 from `pd.DataFrame()` to `pd.DataFrame(columns=self.pipe_fields)`.

11. **Add streaming file reading** (PERF-SBF-001): Instead of `file.read()`, implement a streaming message reader that yields one SWIFT message at a time. Process messages in batches (e.g., 1000 at a time) to control memory usage.

12. **Compile regex patterns** (PERF-SBF-003): Move all regex patterns to class-level `re.compile()` calls. For example:
    ```python
    _BLOCK1_PATTERN = re.compile(r'\{1:([^}]*)\}')
    _BLOCK2_PATTERN = re.compile(r'\{2:([^}]*)\}')
    _FIELD_TAG_PATTERN = re.compile(r':(\d{2,3}[A-Z]?):(.*)')
    ```

### Long-Term (Optimization)

13. **Eliminate dict-in-data defensive code** (DBG-SBF-003): Investigate and fix the root cause of dict values appearing in parsed data. The 70+ lines of isinstance(value, dict) checks on lines 496-592 suggest a real bug in the parsing logic where dict YAML values or other non-string data leaks through. Once fixed, remove all defensive conversion code.

14. **Fix NB_LINE / NB_LINE_OK semantics** (ENG-SBF-009): Either set both NB_LINE and NB_LINE_OK to the output row count (consistent with Talend convention) or add a new stat like `NB_MESSAGES` for the message count.

15. **Add config schema validation** (CONV-SBF-001): Create a JSON schema or explicit `_validate_config()` method that validates all required keys, types, and value ranges before execution begins.

16. **Improve heuristic column detection** (ENG-SBF-007): Check for SWIFT-specific patterns like `{1:` or `:20:` instead of generic `{` and `:`.

17. **Make field 61 continuation separator configurable** (BUG-SBF-007): Add a config option like `field61_continuation_separator` defaulting to `sfield9=` to allow job-specific customization.

18. **Consolidate single/list storage** (BUG-SBF-008): Always store multi-occurrence fields as lists, even when there is only one occurrence. This eliminates all isinstance checks in `_normalize_message_data()`.

---

## Appendix A: Engine Class Structure

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

## Appendix B: SWIFT MT940 Message Structure Reference

A standard MT940 (Customer Statement Message) follows this structure:

```
{1:F01BANKBEBBAXXX0168497562}          <- Block 1: Basic Header
{2:O9400845170607BANKBEBBAXXX00000000001706070845N}  <- Block 2: Application Header
{3:{108:MT940}}                        <- Block 3: User Header
{4:                                    <- Block 4: Text Block (start)
:20:STARTOFSTMT                        <- Transaction Reference Number (single)
:25:BE68539007547034                   <- Account Identification (single)
:28C:00001/001                         <- Statement Number/Sequence Number (single)
:60F:C170601EUR1234,56                 <- Opening Balance (single)
:61:170602C100,00NTRF12345//REF123     <- Statement Line (multiple - transaction 1)
:86:PAYMENT FROM CUSTOMER ABC          <- Info to Account Owner (paired with 61)
:61:170603D50,00NTRF67890//REF456      <- Statement Line (transaction 2)
:86:TRANSFER TO VENDOR XYZ            <- Info to Account Owner (paired with 61)
:62F:C170603EUR1284,56                 <- Closing Balance (single)
-}                                     <- Block 4: Text Block (end with hyphen)
{5:{CHK:ABCDEF123456}}                <- Block 5: Trailer
```

**Key normalization**: The above message would produce 2 output rows (one per 61/86 pair), with fields like `:20:`, `:25:`, `:28C:`, `:60F:`, `:62F:` repeated in both rows.

---

## Appendix C: Edge Case Analysis

### Edge Case 1: Empty SWIFT file

| Aspect | Detail |
|--------|--------|
| **Expected** | Return empty DataFrame with correct columns, NB_LINE=0 |
| **V1** | `_parse_swift_file()` reads empty file, `_split_messages()` returns empty list, `_process()` returns `pd.DataFrame()` with NO columns |
| **Verdict** | **GAP** -- empty DataFrame has no columns. Should use `pd.DataFrame(columns=self.pipe_fields)`. See ENG-SBF-008. |

### Edge Case 2: NaN values in content column

| Aspect | Detail |
|--------|--------|
| **Expected** | NaN rows should be skipped gracefully |
| **V1** | `str(row[content_column])` on line 210 converts NaN to string `"nan"`. Line 211 checks `if message_content and message_content.strip()` -- `"nan"` is truthy. So NaN rows are passed to `_parse_single_message()` which tries to parse `"nan"` as SWIFT. No blocks match, returns nearly-empty dict. |
| **Verdict** | **GAP** -- NaN rows produce malformed output rows instead of being skipped. Should check `pd.isna(row[content_column])` before processing. |

### Edge Case 3: Empty string in content column

| Aspect | Detail |
|--------|--------|
| **Expected** | Empty strings should be skipped |
| **V1** | `str("")` is `""`, `""` is falsy in Python. Line 211 `if message_content and message_content.strip()` correctly skips empty strings. |
| **Verdict** | **CORRECT** |

### Edge Case 4: SWIFT message without Block 4

| Aspect | Detail |
|--------|--------|
| **Expected** | Produce one row with header fields only, all Block 4 fields empty |
| **V1** | `_parse_block4_with_layout()` returns empty dict (no regex match). `_normalize_message_data()` finds no `block4_61` data, creates `block4_61_data = ['']`. Produces one row with empty 61/86 values. Header fields from blocks 1/2 are populated. |
| **Verdict** | **CORRECT** -- reasonable behavior |

### Edge Case 5: Block 4 without trailing hyphen

| Aspect | Detail |
|--------|--------|
| **Expected** | Parse Block 4 content, possibly with warning |
| **V1** | Regex `r'\{4:(.*?)-\}'` requires `-}` terminator. Without hyphen, no match. All Block 4 content lost silently. |
| **Verdict** | **GAP** -- see BUG-SBF-005. Critical for messages from non-standard SWIFT generators. |

### Edge Case 6: Multiple `:86:` fields not paired with `:61:`

| Aspect | Detail |
|--------|--------|
| **Expected** | Standalone `:86:` stored as regular field (per layout type S or M) |
| **V1** | Before any `:61:` is seen, standalone `:86:` entries are handled correctly (line 452-460). After the first `:61:`, ALL `:86:` entries not immediately following a `:61:` are skipped (line 463-465). |
| **Verdict** | **GAP** -- see ENG-SBF-003. Post-61 standalone 86 entries lost. |

### Edge Case 7: `:61:` field with sub-field 9 (supplementary details)

| Aspect | Detail |
|--------|--------|
| **Expected** | Supplementary details on continuation line correctly extracted |
| **V1** | Continuation lines joined with `sfield9=` separator. If `:61:` is `170602C100,00NTRF12345//REF123` and next line (not a new tag) is `SUPPLEMENTARY DETAILS`, result is `170602C100,00NTRF12345//REF123sfield9=SUPPLEMENTARY DETAILS`. |
| **Verdict** | **PARTIAL** -- works as designed but `sfield9=` is hardcoded and unconventional. Standard SWIFT parsing typically uses CRLF or specific delimiters. |

### Edge Case 8: YAML layout with nested dict values

| Aspect | Detail |
|--------|--------|
| **Expected** | Reject or convert gracefully |
| **V1** | `_load_layout_from_file()` line 119-120 detects dict values and skips them with a warning. Non-string values are converted to string (line 123-124). |
| **Verdict** | **CORRECT** -- defensive handling with logging |

### Edge Case 9: pipe_fields with dict entries missing 'name' key

| Aspect | Detail |
|--------|--------|
| **Expected** | Skip invalid entries with warning |
| **V1** | Line 70-71 catches `isinstance(field, dict) and 'name' in field` -- entries without 'name' fall to the `else` branch which logs a warning. After the loop, line 73 checks if `self.pipe_fields` is empty and raises `ValueError`. |
| **Verdict** | **CORRECT** |

### Edge Case 10: Multi-message file with inconsistent formats

| Aspect | Detail |
|--------|--------|
| **Expected** | Parse each message independently, handle failures per-message |
| **V1** | `_parse_swift_file()` calls `_parse_single_message()` for each message in a loop. Each call has its own try/except returning `None` on failure. Failed messages are silently filtered. |
| **Verdict** | **PARTIAL** -- failures are handled but silently dropped. No reject count or error reporting per message. |

### Edge Case 11: Context variable in layout_file resolving to empty

| Aspect | Detail |
|--------|--------|
| **Expected** | Clear error about missing layout |
| **V1** | `context_manager.resolve_string()` on empty/None returns empty string. `_load_layout_from_file("")` calls `os.path.normpath("")` which returns `"."`. `os.path.exists(".")` is True (current directory). Then `yaml.safe_load()` tries to load a directory, which may produce `None` or error. |
| **Verdict** | **GAP** -- empty layout_file path resolves to current directory instead of raising a clear error. Should validate resolved path is non-empty and is a file. |

### Edge Case 12: SWIFT message with `{1:` appearing inside Block 4 content

| Aspect | Detail |
|--------|--------|
| **Expected** | `{1:` inside Block 4 should not split the message |
| **V1** | `_split_messages()` uses regex `r'(\{1:[^}]*\}.*?)(?=\{1:|$)'`. Since Block 4 content is inside `{4:...-}`, the `{1:` inside Block 4 would be a false message boundary. However, this scenario is extremely rare in real SWIFT data. |
| **Verdict** | **EDGE CASE** -- theoretically possible but very unlikely in real SWIFT messages. |

### Edge Case 13: HYBRID execution mode with large DataFrame input

| Aspect | Detail |
|--------|--------|
| **Expected** | BaseComponent chunks the DataFrame and calls `_process()` per chunk |
| **V1** | `BaseComponent._execute_streaming()` splits input into chunks via `_create_chunks()`. Each chunk goes through `_process()`. The first chunk call loads the layout (`_ensure_layout_loaded()` sets `self.layout_spec`). Subsequent chunks reuse the loaded layout. Results are concatenated. |
| **Verdict** | **CORRECT** -- layout loading is properly lazy and cached |

---

## Appendix D: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `SwiftBlockFormatter`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-SBF-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-SBF-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix E: Implementation Fix Guides

### Fix Guide: BUG-SBF-004 -- Remove forced DEBUG log level

**File**: `src/v1/engine/components/transform/swift_block_formatter.py`
**Line**: 149

**Current code (broken)**:
```python
# Enable debug logging for this component
logger.setLevel(logging.DEBUG)
```

**Fix**: Delete both lines (148-149). No replacement needed. Application-level logging configuration should control log levels.

**Impact**: Eliminates production log flooding and sensitive financial data leakage. **Risk**: None.

---

### Fix Guide: BUG-SBF-005 -- Block 4 regex optional hyphen

**File**: `src/v1/engine/components/transform/swift_block_formatter.py`
**Line**: 349

**Current code**:
```python
block4_pattern = r'\{4:(.*?)-\}'
```

**Fix**:
```python
block4_pattern = r'\{4:(.*?)(?:-\}|\})'
```

**Explanation**: The SWIFT standard uses `-}` to terminate Block 4, but some generators omit the hyphen. The fix accepts both terminators.

**Impact**: Prevents silent data loss for non-standard SWIFT messages. **Risk**: Low -- the standard terminator still works. Non-greedy `.*?` ensures the first closing match is used.

---

### Fix Guide: BUG-SBF-006 -- Message split regex edge case

**File**: `src/v1/engine/components/transform/swift_block_formatter.py`
**Line**: 251

**Current code**:
```python
message_pattern = r'(\{1:[^}]*\}.*?)(?=\{1:|$)'
```

The regex is syntactically correct -- the `|` inside the lookahead `(?=\{1:|$)` acts as the alternation operator (match `{1:` OR end-of-string). The non-greedy `.*?` combined with `re.DOTALL` will match as little as possible, stopping at the first `{1:` boundary. This is correct for typical multi-message files. The edge case is if `{1:` appears inside Block 4 body content, which would cause a false split. This is extremely unlikely in real SWIFT data.

**Recommended hardening** (optional): Split by `{1:` boundaries explicitly instead of regex:
```python
parts = content.split('{1:')
messages = ['{1:' + part for part in parts[1:] if part.strip()]
```

---

### Fix Guide: ENG-SBF-008 -- Empty DataFrame with correct columns

**File**: `src/v1/engine/components/transform/swift_block_formatter.py`
**Line**: 165

**Current code**:
```python
return {'main': pd.DataFrame()}
```

**Fix**:
```python
return {'main': pd.DataFrame(columns=self.pipe_fields)}
```

**Impact**: Downstream components receive a DataFrame with correct column structure even when no messages are found. **Risk**: None.

---

### Fix Guide: ENG-SBF-003 -- Standalone block 86 after first 61

**File**: `src/v1/engine/components/transform/swift_block_formatter.py`
**Lines**: 423-465

**Current logic** (simplified):
```python
if field_tag == '61':
    # Start 61/86 pair tracking
elif field_tag == '86' and not block61_list:
    # Standalone 86 (before any 61)
elif field_tag == '86':
    # Skip (assumed already handled)
```

**Fix**: Track pairing state explicitly:
```python
expecting_86_for_61 = False

if field_tag == '61':
    block61_list.append(field_value)
    expecting_86_for_61 = True
    # Check next field for 86 pair...
elif field_tag == '86' and expecting_86_for_61:
    block86_list.append(field_value)
    expecting_86_for_61 = False
elif field_tag == '86':
    # Standalone 86 -- process as regular field
    ...
```

**Impact**: Preserves standalone block 86 data regardless of position in message. **Risk**: Medium -- changes pairing semantics; requires thorough testing with real MT940 data.

---

## Appendix F: Risk Assessment for Production Use

### High-Risk Scenarios

| Scenario | Risk Level | Mitigation |
|----------|-----------|------------|
| Large batch files (GB-scale) with millions of messages | **Critical** | Must implement streaming file reading (PERF-SBF-001) before processing production batch files |
| Messages from non-standard SWIFT generators | **High** | Fix Block 4 regex (BUG-SBF-005) to handle missing trailing hyphen |
| Silent message drops in financial data | **High** | Implement REJECT flow (ENG-SBF-001) and message-level error reporting |
| Outbound (O-type) messages with wrong BIC | **High** | Fix Block 2 position offsets (ENG-SBF-002) |
| Production log flooding | **High** | Remove forced DEBUG level (BUG-SBF-004) immediately |
| `_update_global_map` crash | **Critical** | Fix cross-cutting bugs (BUG-SBF-001, BUG-SBF-002) |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Block 3 sub-tag parsing | Low | Raw content stored; sub-tags rarely needed downstream |
| Block 5 sub-field parsing | Low | Trailer data rarely used in business logic |
| 3-digit field tags | Low | Extremely rare in MT940/MT950 messages |
| Hex/octal in SWIFT content | N/A | Not applicable to SWIFT messages |

### Recommended Production Readiness Checklist

1. Fix all P0 bugs (cross-cutting base class + GlobalMap)
2. Remove forced DEBUG logging (BUG-SBF-004)
3. Fix Block 4 regex for optional hyphen (BUG-SBF-005)
4. Fix Block 2 Output BIC extraction (ENG-SBF-002)
5. Create P0 test suite with real MT940 samples
6. Implement REJECT flow for financial data auditability
7. Add streaming file reading for production batch volumes
8. Validate against known-good Talend output for 3+ production jobs
