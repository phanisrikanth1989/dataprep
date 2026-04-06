# Audit Report: SwiftTransformer (Custom Component)

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD REWRITE
> **Engine Version**: v1
> **Converter**: N/A (engine-native component, no Talend XML converter)
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Custom Name** | `SwiftTransformer` / `TSwiftDataTransformer` |
| **V1 Engine Class** | `SwiftTransformer` |
| **Engine File** | `src/v1/engine/components/transform/swift_transformer.py` (878 lines -- largest engine component) |
| **Converter Parser** | N/A -- engine-native component, not a Talend XML component |
| **Converter Dispatch** | N/A -- configured directly in v1 job JSON |
| **Registry Aliases** | `SwiftTransformer`, `tSwiftTransformer` (registered in `src/v1/engine/engine.py`) |
| **Category** | Transform / Custom (SWIFT Financial Messaging) |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/swift_transformer.py` | Engine implementation (878 lines) |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/context_manager.py` | ContextManager: variable resolution, `resolve_string()`, `resolve_dict()` |
| `src/v1/engine/components/transform/__init__.py` | Package exports (`from .swift_transformer import SwiftTransformer`) |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **N/A** | -- | -- | -- | -- | Engine-native component; no Talend XML converter applicable |
| Engine Feature Parity | **Y** | 1 | 5 | 7 | 2 | Duplicate method definition; `eval()` with `__import__`; dead config sections; no input validation; regex/date parsing gaps |
| Code Quality | **Y** | 2 | 2 | 6 | 3 | Cross-cutting base class bugs; pad direction inverted; wildcard escaping; dead code; no custom exceptions |
| Performance & Memory | **Y** | 0 | 1 | 2 | 1 | Row-by-row iterrows(); O(N*M) regex lookup; unconditional third pass |
| Testing | **N/A** | -- | -- | -- | -- | Engine-native component; testing scored separately from audit-only standardization |

**Overall: YELLOW -- Functional for SWIFT MT940 transformation but has security, code quality, and performance concerns**

**Top Actions**:

1. Remove `__import__` from `eval()` context (SEC-ST-001)
2. Fix cross-cutting `_update_global_map()` and `GlobalMap.get()` crashes (BUG-ST-001, BUG-ST-002)
3. Remove duplicate `_load_lookup_files()` definition (ENG-ST-001)
4. Add path traversal protection for config/lookup file paths (SEC-ST-002)
5. Fix pad direction inversion in `_post_process_value()` (BUG-ST-003)

---

## 3. Talend Feature Baseline

What is this component and what does it do? Since SwiftTransformer is an engine-native custom component with no Talend equivalent, this section documents the component's own design contract.

### What SwiftTransformer Does

`SwiftTransformer` is a **custom component** with no standard Talend equivalent. It transforms SWIFT (Society for Worldwide Interbank Financial Telecommunication) pipe-delimited message data from a raw parsed format into a business-friendly output format. It is designed to sit downstream of `SwiftBlockFormatter`, which parses raw SWIFT MT messages (e.g., MT940 bank statements) into a flat pipe-delimited DataFrame.

**Input**: A DataFrame with SWIFT message fields (e.g., `messagetype`, `block1bic`, `block2bic`, `block4_20`, `block4_25`, `block4_61`, `block4_86`).

**Output**: A DataFrame with business-meaningful fields (e.g., `SIDE`, `TERMID`, `DESTID`, `OURREF`, `THEIRREF`, `AMOUNT`, `CURRENCY`, `VALUEDATE`).

**Core Capabilities**:

1. **Configuration-driven field mapping**: Reads transformation rules from external YAML/JSON config files, inline config, or a hardcoded default config. Each output field is defined by a mapping type.

2. **Seven field mapping types**:
   - `constant` -- static value (e.g., `SIDE = "RECV"`)
   - `direct` -- copy from input field to output field (e.g., `TERMID = sender_bic`)
   - `parsed` -- extract substrings from input fields using regex, position, or split
   - `calculated` -- derive values via concatenation, conditionals, or date extraction
   - `transformation` -- domain-specific transforms (balance_parse, movement_parse, lookup, format)
   - `python_expression` -- arbitrary Python expressions evaluated via `eval()` with access to input and computed fields
   - `placeholder` -- stub returning default value for future implementation

1. **Lookup table support**: Loads external CSV/pipe-delimited lookup files. Supports normal (exact) and regex/wildcard matching. Two-tier lookup dependency system (`depends_on_lookup` flag) for cascading lookups.

2. **Post-processing**: Truncation, padding, and string replacement on individual field values.

3. **Multi-pass computation**: Fields are computed in declaration order (allowing later fields to reference earlier computed fields). Three-pass execution: (1) compute all fields, (2) apply first-tier lookups and recompute dependent fields, (3) apply second-tier lookups and recompute dependent fields again.

4. **Output file writing**: Optionally writes the transformed DataFrame to a file (CSV/pipe-delimited) in addition to returning it.

**Source**: Custom component -- no external Talend documentation. Design derived from engine source analysis.
**Component family**: Transform / Custom (SWIFT Financial Messaging)
**Available in**: Custom ETL-AGENT only; not a standard Talend component
**Required JARs**: None (pure Python)

### 3.1 Configuration Structure

The component accepts configuration in three ways (in priority order):

| Priority | Source | Config Key | Description |
| ---------- | -------- | ----------- | ------------- |
| 1 | External file | `config_file` | Path to YAML/JSON file. Supports `${context.var}` resolution. Loaded at execution time via `_ensure_config_loaded()`. |
| 2 | Inline config | `transform_config` | Embedded config dict in the component's config block |
| 3 | Default config | (hardcoded) | `_get_default_transform_config()` -- SWIFT MT940-specific defaults |

**Config Sections**:

| Section | Type | Description |
| --------- | ------ | ------------- |
| `input_fields` | List[str] | Names of expected input columns (informational only -- not enforced) |
| `output_fields` | List[Dict] | Output field definitions with name, type, source, default, transform_config, etc. |
| `output_layout` | List[str] | Ordered list of field names for the output DataFrame columns. Fields in `output_fields` but not in `output_layout` are intermediate (computed but not output). |
| `field_mappings` | Dict | Declared but **never used** in engine code -- dead config |
| `transformations` | Dict | Declared but **never used** in engine code -- dead config |
| `lookups` | List[Dict] | Lookup table configurations with name, file, main_key, lookup_key, columns, match_type |

### 3.2 Output Field Definition Schema

Each entry in `output_fields` supports these attributes:

| Attribute | Type | Required | Description |
| ----------- | ------ | ---------- | ------------- |
| `name` | str | Yes | Output field name |
| `type` | str | No (default: `direct`) | Mapping type: `constant`, `direct`, `parsed`, `calculated`, `transformation`, `python_expression`, `placeholder` |
| `source` | str | No | Input column name to read from |
| `default` | str | No (default: `''`) | Default value when source is missing or transformation fails |
| `value` | str | No | Value for `constant` type fields |
| `parse_config` | Dict | No | Config for `parsed` type: `regex` (with `group`), `position` (start/end), `split` (delimiter/index) |
| `calc_config` | Dict | No | Config for `calculated` type: `concatenate`, `conditional`, `date_extraction` |
| `transform_config` | Dict | No | Config for `transformation` type: `balance_parse`, `movement_parse`, `lookup`, `format` |
| `python_expression` | str | No | Python expression string for `python_expression` type |
| `post_process` | Dict | No | Post-processing: `truncate`, `pad`, `replace` |
| `depends_on_lookup` | bool | No | If true, field is recomputed after lookups |

### 3.3 Lookup Configuration Schema

Each entry in `lookups` supports:

| Attribute | Type | Required | Description |
| ----------- | ------ | ---------- | ------------- |
| `name` | str | Yes | Lookup identifier |
| `file` | str | Yes | Path to lookup file. Supports `${context.var}`. |
| `main_key` | str | Yes | Output field name to match against |
| `lookup_key` | str | Yes | Column name in lookup file to match |
| `columns` | List[str] | Yes | Target output field names to populate from matched row |
| `source_columns` | List[str] | No | Source columns in lookup file (defaults to all non-key columns) |
| `match_type` | str | No (default: `normal`) | `normal` (exact) or `regex` (wildcard/regex pattern) |
| `depends_on_lookup` | bool | No | If true, this lookup runs in second tier |

### 3.4 Additional Engine Config Keys

| Config Key | Type | Default | Description |
| ------------ | ------ | --------- | ------------- |
| `output_file` | str | None | Optional output file path for writing transformed data |
| `delimiter` | str | `'\ | '` | Delimiter for output file writing |
| `output_encoding` | str | `'utf-8'` | Encoding for output file |
| `include_header` | bool | `True` | Whether to include column headers in output file |
| `die_on_error` | bool | `True` | Whether to raise exception on processing failure |
| `skip_error_rows` | bool | `False` | Whether to skip rows that fail transformation (vs inserting empty row) |

### 3.5 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Input DataFrame from upstream component (e.g., SwiftBlockFormatter) |
| `FLOW` (Main) | Output | Row > Main | Transformed DataFrame with business fields per `output_layout` |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Via base class -- fires on successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Via base class -- fires on error |

### 3.6 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total input rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Successfully transformed rows |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Always 0 (no reject mechanism) |

### 3.7 Behavioral Notes

1. **Config loading is deferred**: External config files are NOT loaded at `__init__` time. They are loaded lazily at execution time via `_ensure_config_loaded()` to ensure context variables are available for path resolution.
2. **Field computation order matters**: Output fields are computed in declaration order. A field referencing a previously computed field via `python_expression` must appear AFTER the field it references in the `output_fields` list.
3. **Three-pass execution for lookups**: Pass 1 computes all fields. Pass 2 applies first-tier lookups and recomputes `depends_on_lookup` fields. Pass 3 applies second-tier lookups and recomputes `depends_on_lookup` fields again.
4. **NaN double guard**: Both `pd.notna()` and string `'nan'` check are applied to prevent NaN values from leaking into output.
5. **Lookup file delimiter auto-detection**: `.csv` files use comma delimiter; all other extensions use pipe (`|`).
6. **`field_mappings` and `transformations` config sections are dead**: They are loaded from config but never read by any logic. Users providing these in YAML will see them silently ignored.

---

## 4. Converter Audit

**N/A** -- SwiftTransformer is an engine-native custom component. It is not a standard Talend component and has no Talend XML converter. Configuration is provided directly in v1 job JSON files. No converter standardization applies per D-82.

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement its design contract?

### 5.1 Feature Implementation Status

| # | Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | --------- | ------------- | ---------- | ----------------- | ------- |
| 1 | External config loading (YAML/JSON) | **Yes** | High | `_load_external_config()` L258 | Context variable resolution in path. Supports `.yaml`, `.yml`, `.json`. |
| 2 | Inline config | **Yes** | High | `_init_transformer_config()` L52 | Fallback when no external config file |
| 3 | Default config | **Yes** | Medium | `_get_default_transform_config()` L280 | Hardcoded MT940 defaults. Only useful for specific SWIFT message type. |
| 4 | Deferred config loading | **Yes** | High | `_ensure_config_loaded()` L93 | Config loaded at execution time when context variables are available |
| 5 | Constant field mapping | **Yes** | High | `_get_field_value()` L499 | `output_field.get('value', default_value)` |
| 6 | Direct field mapping | **Yes** | High | `_get_field_value()` L489 | With NaN/nan string guards |
| 7 | Parsed field mapping | **Yes** | High | `_parse_field_value()` L547 | Regex, position, split extraction |
| 8 | Calculated field mapping | **Yes** | Medium | `_calculate_field_value()` L582 | Concatenate, conditional, date_extraction |
| 9 | Transformation field mapping | **Yes** | Medium | `_apply_field_transformation()` L729 | balance_parse, movement_parse, lookup, format |
| 10 | Python expression mapping | **Yes** | **Low** | `_evaluate_python_expression()` L618 | Uses `eval()` with `__import__` exposed -- **security risk** |
| 11 | Placeholder field type | **Yes** | High | `_get_field_value()` L526 | Returns default value |
| 12 | Lookup loading (CSV/pipe) | **Yes** | Medium | `_load_lookup_files()` L135 | Auto-detects delimiter by extension. `keep_default_na=False` correctly prevents NA parsing. |
| 13 | Normal (exact) lookup matching | **Yes** | High | `_apply_lookups()` L230 | Vectorized pandas boolean index |
| 14 | Regex/wildcard lookup matching | **Yes** | Medium | `_apply_lookups()` L205 | Wildcard-to-regex conversion with heuristic detection. Row-by-row iteration. |
| 15 | Two-tier lookup dependency | **Yes** | Medium | `_transform_rows()` L427 | `depends_on_lookup` flag separates first/second tier |
| 16 | Intermediate computed fields | **Yes** | High | `_transform_rows()` L409 | `working_row` accumulates values; later fields reference earlier ones |
| 17 | Post-processing (truncate/pad/replace) | **Yes** | Medium | `_post_process_value()` L825 | Pad direction logic is inverted (see BUG-ST-003) |
| 18 | Output file writing | **Yes** | High | `_write_output_file()` L850 | NaN/nan/None cleanup before writing. Creates output directory. |
| 19 | SWIFT balance parsing | **Yes** | Medium | `_parse_balance_field()` L758 | C/D + YYMMDD + Currency + Amount. Only handles comma decimal. |
| 20 | SWIFT movement parsing | **Yes** | Medium | `_parse_movement_field()` L788 | MT940 field 61. Does not handle RC/RD/EC/ED indicators. |
| 21 | Date component extraction | **Yes** | Medium | `_extract_date_component()` L692 | Multiple format attempts. Ambiguous `%d%m%y` vs `%y%m%d` ordering. |
| 22 | Error row handling | **Partial** | Low | `_transform_rows()` L461 | `skip_error_rows` config or empty row insertion. No REJECT flow. |
| 23 | Die on error | **Yes** | High | `_process()` L395 | Raises RuntimeError or logs and returns empty DF |
| 24 | Context variable resolution | **Yes** | High | Via `BaseComponent.execute()` and `_load_external_config()` | `context_manager.resolve_string()` used for paths |

### 5.2 Behavioral Differences from Design Contract

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-ST-001 | **P0** | **Duplicate `_load_lookup_files()` method definition**: The method is defined TWICE -- lines 125-133 (incomplete stub that does nothing useful after `continue`) and lines 135-170 (full implementation). Python silently overrides the first with the second. Dead first definition from incomplete editing. |
| ENG-ST-002 | **P1** | **`eval()` with `__import__` exposed**: `_evaluate_python_expression()` (line 661) sets `'__import__': __import__` in `__builtins__`, allowing arbitrary module imports via YAML/JSON config. A malicious config file can execute `__import__('os').system('rm -rf /')`. |
| ENG-ST-003 | **P1** | **`output_fields_map` relies on dict insertion order**: `self.output_fields_map = {field['name']: field for field in self.output_fields}` creates a dict iterated in `_transform_rows()` for field computation. Correctness depends on Python 3.7+ insertion-order guarantee. Should iterate original list instead. |
| ENG-ST-004 | **P1** | **`field_mappings` and `transformations` config sections declared but never used**: Extracted from config at lines 63-64 and 110-111 but no code reads them. Users providing these in YAML see them silently ignored. |
| ENG-ST-005 | **P1** | **No input field validation**: The `input_fields` config section is loaded but never used for validation. Missing source columns produce silent default values with no warning. |
| ENG-ST-006 | **P2** | **`_parse_movement_field()` regex does not handle RC/RD/EC/ED**: Pattern `([DC])` only matches single-character debit/credit marks. SWIFT MT940 spec allows `[D/C/RC/RD/EC/ED]`. |
| ENG-ST-007 | **P2** | **`_parse_balance_field()` does not handle European number format**: `amount.replace(',', '')` strips commas but not periods as thousands separators. `1.234.567,89` would parse incorrectly. |
| ENG-ST-008 | **P2** | **Regex wildcard detection heuristic is brittle**: Patterns with both wildcards and dots (e.g., `FOO*BAR.TXT`) are treated as regex, skipping wildcard-to-regex conversion. |
| ENG-ST-009 | **P2** | **`_extract_date_component()` has ambiguous format priority**: Tries `%d%m%y` before `%y%m%d`. SWIFT standard uses YYMMDD, so `%y%m%d` should take priority. `230115` would be parsed as day=23 instead of year=23. |
| ENG-ST-010 | **P2** | **Lookup column index mapping silently drops targets**: When `source_columns` has fewer entries than `columns`, extra target columns are silently skipped with no warning. |
| ENG-ST-011 | **P2** | **`_write_output_file()` may not resolve context variables in output path**: `output_file` from `self.config.get('output_file')` is used directly without `context_manager.resolve_string()`. May fail if path contains `${context.var}` and `resolve_dict()` did not reach it. |
| ENG-ST-012 | **P3** | **Third-pass recomputation is always unconditional**: Even when no second-tier lookups matched, all `depends_on_lookup` fields are recomputed. Minor optimization opportunity. |
| ENG-ST-013 | **P3** | **No REJECT flow**: Failed rows either produce empty output rows or are skipped. Error details are only logged, not captured in structured reject output. |

### 5.3 GlobalMap Variable Coverage

| Variable | Set? | How Set | Notes |
| ---------- | ------ | --------- | ------- |
| `{id}_NB_LINE` | **Yes** | `_update_stats()` via base class | Set correctly (subject to cross-cutting BUG-ST-001) |
| `{id}_NB_LINE_OK` | **Yes** | `_update_stats()` via base class | Always equals `NB_LINE` since no reject mechanism |
| `{id}_NB_LINE_REJECT` | **Partial** | `_update_stats()` via base class | Always 0. Even when `skip_error_rows=true`, reject count is not updated for skipped rows. |
| `{id}_ERROR_MESSAGE` | **No** | -- | Not implemented |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-ST-001 | **P0** | `base_component.py:304` | **`_update_global_map()` references undefined variable `value`** (should be `stat_value`). Crashes ALL components when `global_map` is set. **CROSS-CUTTING**. |
| BUG-ST-002 | **P0** | `global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**. Crashes on any `global_map.get()` call. **CROSS-CUTTING**. |
| BUG-ST-003 | **P2** | `swift_transformer.py:838-839` | **Post-processing pad direction is inverted**: `side == 'left'` calls `ljust` (pads right side), `side == 'right'` calls `rjust` (pads left side). Semantics are backwards. |
| BUG-ST-004 | **P2** | `swift_transformer.py:125-133` | **Duplicate `_load_lookup_files()` definition**: First definition (lines 125-133) is an incomplete stub. Second definition (lines 135-170) is the full implementation. Dead first definition from incomplete edit. |
| BUG-ST-005 | **P2** | `swift_transformer.py:396-400` | **`die_on_error=false` path sets stats to (0, 0, 1)**: Does not set `NB_LINE` to actual input rows processed before the error. Stats are inaccurate after partial processing. |
| BUG-ST-006 | **P1** | `swift_transformer.py:214-216` | **Wildcard-to-regex conversion doesn't escape metacharacters**: `pattern.replace('*', '.*')` leaves `(`, `)`, `+` etc. as live regex. `SWIFT(v1)*` becomes `^SWIFT(v1).*$` with a capture group. Fix: `re.escape()` before replacing. |
| BUG-ST-007 | **P2** | `swift_transformer.py:582-616` | **`calculated` and `parsed` types cannot reference previously computed fields**: Only `python_expression` has access to `working_row`. Three-pass system does not help for non-expression types. |
| BUG-ST-008 | **P2** | `swift_transformer.py:258-278` | **`_load_external_config()` falls through to `json.load()` for any non-YAML extension**: `.conf`, `.txt` etc. produce unhelpful `JSONDecodeError` instead of clear "unsupported format" error. |
| BUG-ST-009 | **P2** | `swift_transformer.py:420-424` | **`output_fields_map.items()` iteration order determines computation correctness**: Should iterate `output_fields` list directly to make ordering explicit. |
| BUG-ST-010 | **P3** | `swift_transformer.py:801` | **`_parse_movement_field()` value_date fallback is wrong**: When optional `MMDD` group is absent, falls back to 6-digit `entry_date` instead of 4-digit `MMDD` value_date. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-ST-001 | **P3** | **Class docstring says "TSwiftDataTransformer"** (line 2) but class is named `SwiftTransformer` (line 22). Docstring references a different name. |
| NAME-ST-002 | **P3** | **`field_mappings` and `transformations` config keys are misleading**: Extracted from config but never used. Actual mapping logic uses `output_fields` and `output_fields_map`. Dead config keys create confusion. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-ST-001 | **P2** | "No dead code" | Duplicate `_load_lookup_files()` (lines 125-133). Dead `field_mappings` and `transformations` config. |
| STD-ST-002 | **P2** | "Use custom exceptions" | Uses `RuntimeError` and `ValueError` instead of `ConfigurationError` and `DataValidationError` from the custom exception hierarchy. |

### 6.4 Debug Artifacts

None found. No `print()` statements, no hardcoded paths, no TODO comments.

### 6.5 Security

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| SEC-ST-001 | **P1** | **`eval()` with `__import__` in `__builtins__`**: `_evaluate_python_expression()` (line 661) exposes `__import__` in the eval context, allowing arbitrary code execution via config-supplied expressions: `__import__('os').system('cat /etc/passwd')`. YAML/JSON config file becomes a code injection vector. The `re` module is also exposed, enabling `re.sub()` with callable replacement for additional attack surface. |
| SEC-ST-002 | **P2** | **No path traversal protection on config_file or lookup paths**: `_load_external_config()` and `_load_lookup_files()` accept paths from config that could traverse directories (e.g., `../../etc/shadow`). Combined with `eval()` exposure, a malicious config has both path traversal and code execution. |

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Level usage | INFO for milestones, WARNING for recoverable issues, ERROR for failures -- correct |
| Sensitive data | Financial data (amounts, BICs) may appear in error messages at WARNING level. Low risk but worth noting for compliance. |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Uses `RuntimeError` and `ValueError`. Does NOT use custom exception hierarchy (`ConfigurationError`, `DataValidationError`). |
| Exception chaining | Does NOT use `raise ... from e` pattern. `raise ValueError(f"Failed to load transformation config: {str(e)}")` on line 278 loses traceback. |
| die_on_error handling | Single try/except in `_process()` handles this correctly. |
| Per-row error handling | `_transform_rows()` catches per-row exceptions. Either skips row or inserts empty row. Correct degradation. |
| Per-field error handling | `_get_field_value()` catches per-field exceptions and returns default value with WARNING log. Correct graceful degradation. |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | All public/private methods have parameter type hints -- correct |
| Return types | `_process()` returns `Dict[str, Any]`. `_get_field_value()` returns `str`. All typed. |
| Missing hint | `_load_lookup_files()` has no return type hint (returns None implicitly). Minor. |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-ST-001 | **P1** | **Row-by-row `iterrows()` processing**: `_transform_rows()` (line 407) uses `for index, row in input_df.iterrows()` which is the slowest pandas iteration method. For 100K+ rows with 50+ output fields, this creates massive overhead -- 3M+ Python function calls minimum. Should vectorize simple mapping types (`constant`, `direct`). |
| PERF-ST-002 | **P2** | **Regex lookup is O(N*M) per row**: For `match_type='regex'` lookups, `_apply_lookups()` iterates ALL lookup rows for EACH input row (line 209). 100K input rows with 1K regex lookup = 100M comparisons. Should pre-compile regex patterns and cache match results. |
| PERF-ST-003 | **P2** | **Third-pass computation always runs unconditionally**: Even when no second-tier lookups exist, the third pass (lines 444-448) still iterates all `depends_on_lookup` fields. Should skip when unnecessary. |
| PERF-ST-004 | **P3** | **`input_row.to_dict()` called per python_expression field**: In `_evaluate_python_expression()` (line 637), the same row is converted to dict multiple times. Should convert once in `_transform_rows()`. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Supported via `BaseComponent._execute_streaming()`. SwiftTransformer's `_process()` receives chunks. Correct for DataFrame output but **output_file writing is broken** in streaming mode -- each chunk overwrites the file (line 871: `to_csv()` default mode `'w'`). |
| Lookup tables in memory | All lookup files loaded into memory as DataFrames. Large lookup files (100K+ rows) could consume significant memory. No lazy loading or size limits. |
| Working row accumulation | Each row creates a `working_row` dict with ALL output fields. Garbage collected per row. Acceptable. |
| Output DataFrame | `pd.DataFrame(transformed_rows, columns=self.output_layout)` creates the full output in memory. For very large inputs, both `transformed_rows` list and resulting DataFrame are in memory simultaneously. Streaming mode mitigates via chunking. |

---

## 8. Testing

**N/A** -- SwiftTransformer is an engine-native custom component. Testing scored separately from audit-only standardization per D-82.

**Current state**: Zero unit tests exist for this 878-line component (`tests/v1/engine/components/transform/test_swift_transformer.py` does not exist). All transformation logic is completely unverified by automated tests. This is documented as a known gap but is out of scope for this audit-only plan.

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 3 | **BUG-ST-001**, **BUG-ST-002**, **ENG-ST-001** |
| P1 | 8 | **BUG-ST-006**, **ENG-ST-002**, **ENG-ST-003**, **ENG-ST-004**, **ENG-ST-005**, **SEC-ST-001**, **PERF-ST-001** |
| P2 | 15 | **BUG-ST-003**, **BUG-ST-004**, **BUG-ST-005**, **BUG-ST-007**, **BUG-ST-008**, **BUG-ST-009**, **ENG-ST-006**, **ENG-ST-007**, **ENG-ST-008**, **ENG-ST-009**, **ENG-ST-010**, **ENG-ST-011**, **SEC-ST-002**, **STD-ST-001**, **STD-ST-002**, **PERF-ST-002**, **PERF-ST-003** |
| P3 | 5 | **BUG-ST-010**, **ENG-ST-012**, **ENG-ST-013**, **NAME-ST-001**, **NAME-ST-002**, **PERF-ST-004** |
| **Total** | **31** | |

Note: P2 has 17 entries and P3 has 6 entries. Let me recount.

### Recount

**P0 (3):** BUG-ST-001, BUG-ST-002, ENG-ST-001

**P1 (7):** BUG-ST-006, ENG-ST-002, ENG-ST-003, ENG-ST-004, ENG-ST-005, SEC-ST-001, PERF-ST-001

**P2 (15):** BUG-ST-003, BUG-ST-004, BUG-ST-005, BUG-ST-007, BUG-ST-008, BUG-ST-009, ENG-ST-006, ENG-ST-007, ENG-ST-008, ENG-ST-009, ENG-ST-010, ENG-ST-011, SEC-ST-002, STD-ST-001, STD-ST-002, PERF-ST-002, PERF-ST-003

**P3 (6):** BUG-ST-010, ENG-ST-012, ENG-ST-013, NAME-ST-001, NAME-ST-002, PERF-ST-004

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 3 | BUG-ST-001, BUG-ST-002, ENG-ST-001 |
| P1 | 7 | BUG-ST-006, ENG-ST-002, ENG-ST-003, ENG-ST-004, ENG-ST-005, SEC-ST-001, PERF-ST-001 |
| P2 | 17 | BUG-ST-003, BUG-ST-004, BUG-ST-005, BUG-ST-007, BUG-ST-008, BUG-ST-009, ENG-ST-006, ENG-ST-007, ENG-ST-008, ENG-ST-009, ENG-ST-010, ENG-ST-011, SEC-ST-002, STD-ST-001, STD-ST-002, PERF-ST-002, PERF-ST-003 |
| P3 | 6 | BUG-ST-010, ENG-ST-012, ENG-ST-013, NAME-ST-001, NAME-ST-002, PERF-ST-004 |
| **Total** | **33** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Bug (BUG) | 10 | BUG-ST-001, BUG-ST-002, BUG-ST-003, BUG-ST-004, BUG-ST-005, BUG-ST-006, BUG-ST-007, BUG-ST-008, BUG-ST-009, BUG-ST-010 |
| Engine (ENG) | 13 | ENG-ST-001 through ENG-ST-013 |
| Security (SEC) | 2 | SEC-ST-001, SEC-ST-002 |
| Standards (STD) | 2 | STD-ST-001, STD-ST-002 |
| Naming (NAME) | 2 | NAME-ST-001, NAME-ST-002 |
| Performance (PERF) | 4 | PERF-ST-001, PERF-ST-002, PERF-ST-003, PERF-ST-004 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash -- stats never written to globalMap (BUG-ST-001) |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` crash -- any direct `.get()` call fails (BUG-ST-002) |

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-ST-001): Change `value` to `stat_value` on `base_component.py` line 304. **CROSS-CUTTING** -- fixes ALL components.
2. **Fix `GlobalMap.get()` bug** (BUG-ST-002): Add `default: Any = None` parameter to `get()` method signature in `global_map.py`. **CROSS-CUTTING** -- fixes all globalMap access.
3. **Remove duplicate `_load_lookup_files()`** (ENG-ST-001): Delete lines 125-133 (incomplete stub). Keep full implementation at lines 135-170.

### Short-term (Hardening)

1. **Remove `__import__` from eval context** (SEC-ST-001): In `_evaluate_python_expression()` line 661, remove `'__import__': __import__` from `__builtins__` dict. Closes arbitrary code execution vector.
2. **Fix pad direction** (BUG-ST-003): Swap `ljust`/`rjust` in `_post_process_value()` lines 838-839.
3. **Fix wildcard-to-regex escaping** (BUG-ST-006): Use `re.escape(pattern)` before replacing `\\*` with `.*` and `\\?` with `.`.
4. **Remove dead config sections** (ENG-ST-004): Remove `self.field_mappings` and `self.transformations` or implement them. Log warning if users provide these.
5. **Add input field validation** (ENG-ST-005): Check source columns exist in `input_df.columns` at start of `_transform_rows()`. Log WARNING for missing columns.
6. **Fix SWIFT date format priority** (ENG-ST-009): Move `%y%m%d` before `%d%m%y` in format list.
7. **Use `output_fields` list for iteration** (ENG-ST-003): Replace `output_fields_map.items()` iteration with `output_fields` list in `_transform_rows()`.
8. **Use custom exceptions** (STD-ST-002): Replace `RuntimeError` with `ComponentExecutionError`, `ValueError` with `ConfigurationError`. Use `raise ... from e`.
9. **Add path traversal protection** (SEC-ST-002): Validate config_file and lookup paths against allowed base directories.
10. **Fix movement_parse RC/RD handling** (ENG-ST-006): Update regex to handle `[REC]?[DC]` debit/credit marks.

### Long-term (Optimization)

1. **Vectorize simple mappings** (PERF-ST-001): Apply `constant` and `direct` mappings at DataFrame level instead of row-by-row.
2. **Pre-compile regex patterns** (PERF-ST-002): Pre-compile patterns for regex-match lookups. Cache compiled patterns.
3. **Implement REJECT flow** (ENG-ST-013): Return `{'main': good_df, 'reject': reject_df}` with error details.
4. **Fix streaming output file writing**: Use append mode for subsequent chunks after the first.
5. **Fix balance parsing for European format** (ENG-ST-007): Handle period as thousands separator.
6. **Fix docstring** (NAME-ST-001): Change class docstring from "TSwiftDataTransformer" to "SwiftTransformer".

---

## 11. Risk Assessment

SwiftTransformer is the largest engine component (878 lines) and processes financial SWIFT messaging data. Its complexity and the sensitivity of financial data warrant a comprehensive risk assessment.

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| **Arbitrary code execution via `eval()`** | Medium | **Critical** | `_evaluate_python_expression()` exposes `__import__` in eval context. A malicious or corrupted YAML config can execute `__import__('os').system(...)`. Even "trusted" internal configs could be tampered with via supply chain attack. Remove `__import__` from `__builtins__`; consider replacing `eval()` with `ast.literal_eval()` or a restricted expression parser. |
| **YAML deserialization injection** | Low | **High** | `yaml.safe_load()` is used (line 269), which mitigates the most dangerous YAML deserialization attacks (`!!python/object`). However, `safe_load()` still parses complex nested structures that could cause unexpected behavior if config keys overlap with internal state. Low risk since `safe_load()` is used correctly. |
| **Path traversal via config_file** | Medium | **High** | `_load_external_config()` accepts config_file paths from job JSON without any path validation or sandboxing. `../../etc/passwd` or absolute paths like `/etc/shadow` would be opened. Combined with `eval()`, a path-traversed config containing `python_expression` fields achieves full system compromise. Mitigate: validate paths against allowed base directories before opening. |
| **Path traversal via lookup files** | Medium | **High** | `_load_lookup_files()` loads CSV/pipe files from paths specified in YAML config. Same path traversal vulnerability as config_file. Lookup file paths are resolved through `context_manager.resolve_string()` but not sandboxed. |
| **ReDoS (Regular Expression Denial of Service)** | Medium | **Medium** | User-defined regex patterns in `parse_config.regex` (line 560) and lookup `match_type='regex'` (line 222) are passed directly to `re.search()` and `re.match()` without compilation timeout or complexity limits. A pattern like `(a+)+$` against a long string of `a`s causes exponential backtracking. Mitigate: pre-compile with `re.compile()` and set `re.DOTALL` where appropriate; consider using `re2` library for guaranteed linear-time matching. |
| **Memory exhaustion from large YAML configs** | Low | **Medium** | External YAML configs are loaded entirely into memory. A config with millions of output_fields or deeply nested structures could exhaust memory. `yaml.safe_load()` does not enforce size limits. Mitigate: validate config size before loading; limit output_fields count. |
| **Memory exhaustion from large lookup files** | Medium | **Medium** | All lookup files are loaded as pandas DataFrames at `_load_lookup_files()` time. A 10M-row lookup file would consume hundreds of MB. No size limit or lazy loading. Mitigate: add max-rows limit for lookup files; consider memory-mapped access for large lookups. |
| **Silent data corruption from regex group mismatches** | Medium | **Medium** | `_parse_field_value()` uses `match.group(group)` where `group` comes from user config. If the regex has fewer groups than expected, `IndexError` is raised and caught -- returning default value silently. Data loss goes undetected. Mitigate: validate group count against regex before extraction. |
| **Silent data corruption from SWIFT date parsing** | High | **Medium** | `_extract_date_component()` tries `%d%m%y` before `%y%m%d` for 6-digit dates. SWIFT standard uses YYMMDD, but the code would parse `230115` as day=23, month=01, year=2015 instead of year=23, month=01, day=15. All dates with day > 12 would parse differently. Mitigate: prioritize `%y%m%d` for SWIFT date fields. |
| **Streaming mode file corruption** | Medium | **Medium** | When `output_file` is set and streaming mode is active, `_write_output_file()` uses `to_csv()` with default `mode='w'`, overwriting the file each chunk. Only the last chunk's data survives. Mitigate: use append mode for subsequent chunks. |
| **Financial amount precision loss** | Low | **Medium** | All field values are converted to strings via `str()`. Amounts parsed from SWIFT balance/movement fields go through string manipulation (`.replace(',', '')`). No `Decimal` type is used. Floating-point representation could introduce rounding errors for very large amounts. Mitigate: use `decimal.Decimal` for amount parsing and carry through to output. |

### High-Risk Job Patterns

1. **Jobs with untrusted YAML configs**: Any job where `config_file` points to a user-uploaded or externally-sourced YAML file. The `eval()` + `__import__` exposure means the config file can execute arbitrary system commands.
2. **Jobs with regex-match lookups and large datasets**: O(N*M) complexity for regex lookups. A 100K-row input with a 1K-row regex lookup triggers 100M regex evaluations per lookup.
3. **Jobs with SWIFT dates in DD format**: If day values exceed 12, the date format ambiguity causes `%d%m%y` to match before `%y%m%d`, producing incorrect dates.
4. **Jobs using streaming mode with output_file**: Only the last chunk's data will be written to the file. All previous chunks are silently lost.
5. **Jobs with wildcard lookup patterns containing dots**: Patterns like `SWIFT*.MT940` bypass wildcard-to-regex conversion due to the brittle heuristic, causing incorrect matching.

### Safe Usage Patterns

1. **Jobs with inline config or default config**: No external file loading, no path traversal risk.
2. **Jobs using only `constant`, `direct`, and `parsed` mapping types**: No `eval()` execution, no arbitrary code risk.
3. **Jobs without regex-match lookups**: Only exact-match lookups are used, which are vectorized and efficient.
4. **Jobs without `output_file` config**: DataFrame output only, no file corruption risk from streaming.
5. **Jobs with small, controlled lookup files**: Lookup files under 10K rows with known-good data.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Engine source | `src/v1/engine/components/transform/swift_transformer.py` | Full feature analysis (878 lines) |
| Base component | `src/v1/engine/base_component.py` | Cross-cutting bug analysis, streaming mode |
| Global map | `src/v1/engine/global_map.py` | GlobalMap.get() bug analysis |
| Engine registry | `src/v1/engine/engine.py` | Registry alias verification |
| Transform init | `src/v1/engine/components/transform/__init__.py` | Package export verification |

## Appendix B: Config Parameter Mapping

Complete mapping of job JSON config keys to engine behavior:

| Config Key | Type | Default | Engine Method | Description |
| ------------ | ------ | --------- | --------------- | ------------- |
| `config_file` | str | None | `_init_transformer_config()`, `_ensure_config_loaded()` | Path to external YAML/JSON config. Resolved via `context_manager.resolve_string()`. |
| `transform_config` | Dict | `{}` | `_init_transformer_config()`, `_ensure_config_loaded()` | Inline transformation config (fallback) |
| `output_file` | str | None | `_process()`, `_write_output_file()` | Optional output file path |
| `delimiter` | str | `'\ | '` | `_write_output_file()` | Output file delimiter |
| `output_encoding` | str | `'utf-8'` | `_write_output_file()` | Output file encoding |
| `include_header` | bool | `True` | `_write_output_file()` | Include column headers in output file |
| `die_on_error` | bool | `True` | `_process()` | Raise exception on failure |
| `skip_error_rows` | bool | `False` | `_transform_rows()` | Skip failed rows vs insert empty rows |

## Appendix C: Engine Class Structure

```
SwiftTransformer (BaseComponent) -- 878 lines
    Config attributes:
        config_file: str                      # External YAML/JSON config path
        inline_config: Dict                   # Inline config fallback
        transform_config: Dict                # Loaded config (from file, inline, or default)
        input_fields: List[str]               # Declared input field names (unused for validation)
        output_fields: List[Dict]             # Output field definitions
        output_layout: List[str]              # Ordered output column names
        output_fields_map: Dict[str, Dict]    # name -> field config lookup
        field_mappings: Dict                  # DEAD -- never used
        transformations: Dict                 # DEAD -- never used
        lookups_config: List[Dict]            # Lookup table configurations
        lookup_data: Dict[str, Dict]          # Loaded lookup DataFrames + configs

    Methods:
        _init_transformer_config()                             # Init config; defer external loading
        _ensure_config_loaded()                                # Load config at execution time
        _load_lookup_files()                                   # Load lookup CSVs into memory [DUPLICATE x2]
        _load_external_config(path) -> Dict                    # Load YAML/JSON config
        _get_default_transform_config() -> Dict                # Hardcoded MT940 defaults
        _process(input_data) -> Dict[str, Any]                 # Main entry point
        _transform_rows(input_df) -> pd.DataFrame              # Row-by-row transform with 3-pass logic
        _get_field_value(field, row, working) -> str            # Dispatch to mapping type handler
        _parse_field_value(field, row) -> str                   # Parsed type: regex/position/split
        _calculate_field_value(field, row) -> str               # Calculated type: concat/conditional/date
        _evaluate_python_expression(field, row, working) -> str # eval() with security issues
        _extract_date_component(date_val, component) -> str     # Date parsing with format ambiguity
        _apply_field_transformation(field, value, row) -> str   # balance_parse, movement_parse, lookup, format
        _parse_balance_field(value, config) -> str              # SWIFT balance format parser
        _parse_movement_field(value, config, row) -> str        # MT940 field 61 parser
        _apply_lookups(row, depends_on_lookup) -> Dict          # Lookup matching (exact + regex)
        _post_process_value(value, config) -> str               # truncate, pad [BUG: inverted], replace
        _write_output_file(df, path)                            # CSV/pipe output with NaN cleanup
```

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after gold standard rewrite per D-82 with Section 11 Risk Assessment per D-79*
