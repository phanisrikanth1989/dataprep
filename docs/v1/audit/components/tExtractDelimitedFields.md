# Audit Report: tExtractDelimitedFields / ExtractDelimitedFields

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tExtractDelimitedFields` |
| **V1 Engine Class** | `ExtractDelimitedFields` |
| **Engine File** | `src/v1/engine/components/transform/extract_delimited_fields.py` (272 lines) |
| **Converter Parser (generic)** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (lines 295-314) |
| **Converter Parser (dedicated)** | `src/converters/complex_converter/component_parser.py` -> `parse_textract_delimited_fields()` (lines 1973-1990) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tExtractDelimitedFields'` (line 321-322) -> calls `parse_textract_delimited_fields(node, component)` AFTER `parse_base_component()` has already populated config via `_map_component_parameters()` |
| **Registry Aliases** | `ExtractDelimitedFields`, `tExtractDelimitedFields` (registered in `src/v1/engine/engine.py` lines 119-120) |
| **Category** | Processing / Transform |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/extract_delimited_fields.py` | Engine implementation (272 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 295-314) | Generic parameter mapping via `_map_component_parameters()` -- runs FIRST |
| `src/converters/complex_converter/component_parser.py` (lines 1973-1990) | Dedicated parser `parse_textract_delimited_fields()` -- runs SECOND, overwrites some keys |
| `src/converters/complex_converter/converter.py` (line 321-322) | Dispatch to dedicated parser after `parse_base_component()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/engine.py` (lines 119-120) | Component registry mapping |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 3 | 1 | Dual-parser conflict; FIELD param extraction incomplete; field_separator quote stripping inconsistency; missing REJECT schema passthrough |
| Engine Feature Parity | **Y** | 1 | 5 | 3 | 1 | Row-by-row `iterrows()` loop; fragile column-index extraction logic; no REJECT with errorCode/errorMessage; check_date stub; engine default `field_separator=','` vs Talend `';'` |
| Code Quality | **R** | 3 | 4 | 4 | 2 | Cross-cutting base class bugs; NaN values bypass null check producing garbage data; brittle singular/plural name matching; numeric column names always match Tier 3; quote stripping can produce empty separator crash; col_lookup rebuilt per column per row; debug artifacts |
| Performance & Memory | **R** | 1 | 1 | 2 | 1 | `iterrows()` row-by-row loop defeats pandas vectorization; O(n*m) col_lookup rebuilds; schema column name list rebuilt per row; no chunked/streaming support |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: RED -- Not production-ready; critical bugs (NaN bypass, cross-cutting crashes) and P0/P1 fixes required**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tExtractDelimitedFields Does

`tExtractDelimitedFields` is a Processing-family component that takes a single delimited string field from an incoming data flow and splits it into multiple output columns. It is used when an upstream component (e.g., `tFileInputDelimited`, `tFixedFlowInput`, `tMySQLInput`) produces a row containing a column whose value is itself a delimited string (e.g., `"Alice,Bob,Charlie"`), and the job needs to extract those embedded values into separate output columns (e.g., `name1="Alice"`, `name2="Bob"`, `name3="Charlie"`).

The component takes an existing row with N columns and produces a new row with M columns, where the extracted columns replace or supplement the originals. The extraction is **index-based**: the first token after splitting goes to the first extracted column in the output schema, the second token to the second extracted column, and so on.

**Source**: [tExtractDelimitedFields Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/textractdelimitedfields-standard-properties), [tExtractDelimitedFields Overview (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/processing/textractdelimitedfields), [tExtractDelimitedFields -- Talend Skill (ESB 5.x)](https://talendskill.com/talend-for-esb-docs/docs-5-x/textractdelimitedfields-docs-for-esb-5-x/)

**Component family**: Processing
**Available in**: All Talend products (Standard). Also available in MapReduce (deprecated), Spark Batch, Spark Streaming variants.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Output column definitions with types, lengths, patterns, nullable, key attributes. Defines both passthrough columns (same names as input) and new extracted columns. The schema MUST include any input columns the user wants to preserve in the output, using the same column names. |
| 3 | Field to Split | `FIELD` | Dropdown (incoming columns) | -- | **Mandatory**. Selects which incoming column contains the delimited string to split. Only one field can be selected at a time. The dropdown is populated from the incoming schema. |
| 4 | Field Separator | `FIELDSEPARATOR` | String / Regex | `";"` | Character(s) or regular expression to separate fields within the selected column. Supports single characters, multi-character strings, and regex. When using regex operators, a double backslash prefix is required (e.g., `\\|` for pipe). **Note**: Talend default is semicolon, not comma. |
| 5 | Ignore NULL as source data | `IGNORE_SOURCE_NULL` | Boolean (CHECK) | `false` (unchecked) | When checked, rows where the source field is null are silently skipped (no output row generated). When unchecked, null source values generate null records in the output. |
| 6 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `true` (checked) | When checked, any extraction error stops the entire job. When unchecked, error rows are routed to the REJECT flow (if connected) or silently dropped. **Note**: Talend default is `true` (checked), unlike most other components that default to `false`. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 7 | Advanced Separator (for number) | `ADVANCED_SEPARATOR` | Boolean (CHECK) | `false` | Enable locale-aware number parsing with custom thousands and decimal separators. When checked, exposes Thousands Separator and Decimal Separator fields. |
| 8 | Thousands Separator | `THOUSANDS_SEPARATOR` | Character | `","` | Thousands grouping separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 9 | Decimal Separator | `DECIMAL_SEPARATOR` | Character | `"."` | Decimal point separator for numeric fields. Only visible when `ADVANCED_SEPARATOR=true`. |
| 10 | Trim Column | `TRIM` | Boolean (CHECK) | `false` | Remove leading and trailing whitespace from ALL extracted columns. This is a global trim -- Talend does not provide per-column trim for this component (unlike `tFileInputDelimited` which has `TRIMSELECT`). |
| 11 | Check Each Row Structure Against Schema | `CHECK_FIELDS_NUM` | Boolean (CHECK) | `false` | Validate that the number of delimited tokens in each row matches the number of extracted columns in the schema. Rows that fail this check are routed to REJECT (if connected) or cause an error (if `DIE_ON_ERROR=true`). |
| 12 | Validate Date | `CHECK_DATE` | Boolean (CHECK) | `false` | Strictly validate date-typed extracted columns against the date pattern defined in the output schema. Invalid dates cause the entire row to be rejected. |
| 13 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 14 | Label | `LABEL` | String | -- | Text label for the component in Talend Studio designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | **Required**. Incoming data flow containing the column to split. The component reads from exactly one upstream connection. |
| `FLOW` (Main) | Output | Row > Main | Successfully extracted rows with all schema columns populated. Extracted columns contain the split values; passthrough columns contain their original values. |
| `REJECT` | Output | Row > Reject | Rows that failed extraction (field count mismatch, type conversion failure, date validation error). Includes ALL original schema columns plus two additional columns: `errorCode` (String) and `errorMessage` (String). Only active when `DIE_ON_ERROR=false`. When REJECT is not connected and `DIE_ON_ERROR=false`, error rows are silently dropped. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows processed (input rows, before REJECT filtering). Primary row count variable. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully output via the FLOW (Main) connection. Equals `NB_LINE - NB_LINE_REJECT`. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows sent to the REJECT flow. Zero when no REJECT link is connected. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. Available for reference in downstream error handling flows. |

### 3.5 Behavioral Notes

1. **Schema defines output structure**: The output schema MUST include both (a) any input columns the user wants to preserve and (b) the new extracted columns. If an input column is not named in the output schema, it is dropped. This is different from `tMap` where input columns can be auto-mapped.

2. **Index-based extraction**: Extracted values are mapped to output columns by position. The first token after splitting goes to the first non-passthrough column in the schema, the second token to the second, etc. The mapping is determined by schema column order, not by column naming conventions. Talend Studio populates the schema editor sequentially.

3. **Passthrough columns**: Input columns that appear in the output schema with the same name are copied as-is. They are NOT re-extracted from the delimited string. The component identifies passthrough columns by exact name match with the input schema.

4. **REJECT flow behavior**: When `DIE_ON_ERROR=false` and a REJECT link is connected:
   - Rows that fail extraction (field count mismatch, type conversion, date validation) are sent to REJECT
   - REJECT rows contain ALL original schema columns plus `errorCode` (String) and `errorMessage` (String)
   - These extra columns appear in green in Talend Studio

5. **NULL source handling**: When `IGNORE_SOURCE_NULL=true`, rows where the source field is null produce no output row at all -- they are silently skipped (not sent to REJECT). When `false`, null source values generate a row with null values in all extracted columns.

6. **CHECK_FIELDS_NUM=true**: If the delimited string has more or fewer tokens than extracted columns in the schema, the row goes to REJECT (if connected) or causes an error. Without this check, extra tokens are silently discarded and missing tokens produce null values.

7. **Regex field separator**: Unlike `tFileInputDelimited`, the field separator in `tExtractDelimitedFields` natively supports regular expressions without a separate CSV_OPTION toggle. Double backslash prefix is required for regex operators.

8. **Die On Error default**: The default for `DIE_ON_ERROR` in `tExtractDelimitedFields` is `true` (checked), which differs from most Talend components that default to `false`. This means extraction errors will stop the job unless the user explicitly unchecks this option.

9. **NB_LINE counting**: `NB_LINE` counts input rows processed, not output rows. For this component, one input row always produces at most one output row (it is not a row-multiplying component like `tNormalize`).

---

## 4. Converter Audit

### 4.1 Dual-Parser Architecture

The converter has a **dual-parser problem** for `tExtractDelimitedFields`. Two separate code paths run in sequence:

**Path 1 -- Generic mapper** (`parse_base_component()` -> `_map_component_parameters()`):
1. `converter.py` line 226 calls `parse_base_component(node)` for ALL components
2. Since `tExtractDelimitedFields` is NOT in the `components_with_dedicated_parsers` list (lines 421-425), `parse_base_component()` runs the generic raw parameter loop (lines 433-458)
3. Calls `_map_component_parameters('tExtractDelimitedFields', config_raw)` (line 472)
4. Returns config with keys: `field`, `field_separator`, `ignore_source_null`, `die_on_error`, `advanced_separator`, `thousands_separator`, `decimal_separator`, `trim`, `check_fields_num`, `check_date`, `schema_opt_num`, `connection_format`
5. Also extracts schema from metadata nodes (lines 474-507)

**Path 2 -- Dedicated parser** (`parse_textract_delimited_fields()`):
1. `converter.py` line 321-322 calls `parse_textract_delimited_fields(node, component)` AFTER `parse_base_component()` has already populated config
2. This method OVERWRITES some keys: `field_separator`, `advanced_separator`, `thousands_separator`, `decimal_separator`, `die_on_error`
3. Also ADDS keys not in the generic mapper: `row_separator`, `trim_all`, `remove_empty_row`

**Conflict**: The two parsers produce inconsistent results for the same keys:
- `field_separator`: Generic mapper strips XML quotes; dedicated parser reads raw XML `value` attribute (may still have quotes)
- `advanced_separator`: Generic mapper passes through as boolean (from CHECK field type); dedicated parser does `.lower() == 'true'` string comparison (may get `True` the boolean, not `'true'` the string, from the already-converted CHECK field)
- `die_on_error`: Same boolean vs string inconsistency
- `trim`: Generic mapper sets `trim`; dedicated parser sets `trim_all` (different key name -- engine uses `trim`)

### 4.2 Parameter Extraction

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Location | Notes |
|----|----------------------|------------|---------------|--------------------|-------|
| 1 | `FIELD` | Yes | `field` | Generic mapper line 302 | Field to split. Extracted correctly. |
| 2 | `FIELDSEPARATOR` | Yes | `field_separator` | Generic mapper line 296-300 + Dedicated parser line 1981 | **Extracted twice with different logic**. Generic strips XML quotes; dedicated reads raw value. Last write (dedicated) wins. |
| 3 | `IGNORE_SOURCE_NULL` | Yes | `ignore_source_null` | Generic mapper line 304 | Boolean from CHECK field type |
| 4 | `DIE_ON_ERROR` | Yes | `die_on_error` | Generic mapper line 305 + Dedicated parser line 1988 | **Extracted twice**. Generic gets boolean; dedicated does string comparison. |
| 5 | `ADVANCED_SEPARATOR` | Yes | `advanced_separator` | Generic mapper line 306 + Dedicated parser line 1983 | **Extracted twice** with boolean/string inconsistency. |
| 6 | `THOUSANDS_SEPARATOR` | Yes | `thousands_separator` | Generic mapper line 307 + Dedicated parser line 1984 | **Extracted twice**. |
| 7 | `DECIMAL_SEPARATOR` | Yes | `decimal_separator` | Generic mapper line 308 + Dedicated parser line 1985 | **Extracted twice**. |
| 8 | `TRIM` | Partial | `trim` (generic) / `trim_all` (dedicated) | Generic mapper line 309 / Dedicated parser line 1986 | **Key name mismatch**: engine reads `trim`, dedicated parser writes `trim_all`. Engine always sees generic mapper's value. Dedicated parser's `trim_all` is dead code. |
| 9 | `CHECK_FIELDS_NUM` | Yes | `check_fields_num` | Generic mapper line 310 | Only in generic mapper. |
| 10 | `CHECK_DATE` | Yes | `check_date` | Generic mapper line 311 | Only in generic mapper. |
| 11 | `ROWSEPARATOR` | Partial | `row_separator` | Dedicated parser line 1982 | Only in dedicated parser. **Not used by engine** -- `tExtractDelimitedFields` does not read files; row separator is irrelevant for this component. Extraction is wasted. |
| 12 | `REMOVE_EMPTY_ROW` | Partial | `remove_empty_row` | Dedicated parser line 1987 | Only in dedicated parser. **Not used by engine** -- engine does not have remove_empty_row logic. |
| 13 | `SCHEMA_OPT_NUM` | Yes | `schema_opt_num` | Generic mapper line 312 | Not needed at runtime (code generation optimization). |
| 14 | `CONNECTION_FORMAT` | Yes | `connection_format` | Generic mapper line 313 | Not used by engine. |
| 15 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 16 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact) |
| 17 | `PROPERTY_TYPE` | **No** | -- | -- | Not needed (always Built-In in converted jobs) |

**Summary**: 12 of 14 runtime-relevant parameters extracted. However, 7 parameters are extracted by BOTH parsers with conflicting logic. 2 extracted parameters (`row_separator`, `remove_empty_row`) are irrelevant to this component.

### 4.3 Schema Extraction

Schema is extracted generically in `parse_base_component()` (lines 474-507 of `component_parser.py`).

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

**REJECT schema**: The converter DOES extract REJECT metadata (lines 506-507: `component['schema']['reject'] = schema_cols`). However, the engine never uses it -- there is no REJECT flow implementation with `errorCode`/`errorMessage` columns.

**Critical note on FIELD extraction**: The generic mapper gets `FIELD` from `config_raw.get('FIELD', '')`. In Talend XML, the `FIELD` parameter is a dropdown selection storing the column name as a string. If the Talend job stores this as a quoted value (e.g., `"product"`), the generic quote-stripping logic (lines 441-442) correctly removes them. However, if the field name contains special characters or matches a context variable pattern, it may be incorrectly wrapped with `${...}` by lines 449-456.

### 4.4 Expression Handling

**Context variable handling**: Same generic mechanism as all components. `context.var` references in parameter values are detected and wrapped as `${context.var}` for ContextManager resolution.

**Java expression handling**: After raw parameter extraction, `mark_java_expression()` scans all non-CODE/IMPORT/UNIQUE_NAME string values. Values containing Java operators or method calls are prefixed with `{{java}}` marker.

**Known limitation**: The `FIELD` parameter (field to split) is a simple column name, not an expression. However, the generic expression detection may incorrectly flag field names containing operators (e.g., a column named `total-amount` would be detected as a Java expression due to the `-` operator). This is mitigated by the dedicated parser overwriting some config keys, but `field` itself is not overwritten by the dedicated parser.

### 4.5 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-EDF-001 | **P1** | **Dual-parser conflict**: `parse_base_component()` runs `_map_component_parameters()` first, then `converter.py` calls `parse_textract_delimited_fields()` second. The two parsers extract overlapping keys with different logic (boolean vs string comparison, different quote handling). The last-write-wins semantics mean the dedicated parser's values prevail for keys it touches, but the generic mapper's values persist for keys it alone touches. This creates a fragile, order-dependent config where half the keys come from one parser and half from the other. **Fix**: Add `tExtractDelimitedFields` to the `components_with_dedicated_parsers` list (line 421) so `parse_base_component()` skips raw parameter processing, OR remove the `_map_component_parameters()` branch for this component. |
| CONV-EDF-002 | **P1** | **Misleading comment**: Line 294 of `component_parser.py` says `# tExtractJSONFields mapping` but the code on line 295 handles `tExtractDelimitedFields`. This is a copy-paste error that will confuse maintainers. |
| CONV-EDF-003 | **P2** | **`trim` vs `trim_all` key name mismatch**: The generic mapper sets `config['trim']` (line 309). The dedicated parser sets `config['trim_all']` (line 1986). The engine reads `self.config.get('trim', False)` (line 144). So the engine always reads the generic mapper's value. The dedicated parser's `trim_all` key is dead code -- never read by the engine. If the intent was to override the generic value, the dedicated parser should write to `config['trim']`, not `config['trim_all']`. |
| CONV-EDF-004 | **P2** | **`row_separator` and `remove_empty_row` extracted but irrelevant**: The dedicated parser extracts `ROWSEPARATOR` and `REMOVE_EMPTY_ROW` (lines 1982, 1987), but `tExtractDelimitedFields` does not read files -- it processes an in-memory field. These parameters are irrelevant and waste config space. They appear to be copied from `tFileInputDelimited`'s parser. |
| CONV-EDF-005 | **P2** | **Schema type format violates STANDARDS.md**: Converter converts types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format (`id_String`, `id_Integer`). While the engine handles both, this violates the documented standard. |
| CONV-EDF-006 | **P3** | **`SCHEMA_OPT_NUM` and `CONNECTION_FORMAT` extracted unnecessarily**: These are Talend Studio internals with no runtime impact. They add noise to the config without providing value. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Split field by delimiter | **Yes** | Medium | `_process()` line 178 | Uses `str(value).split(field_separator)` -- Python string split, not regex. |
| 2 | Field to split selection | **Yes** | High | `_process()` line 137, 168-170 | Case-insensitive lookup via field_lookup dict. |
| 3 | Field separator | **Yes** | Medium | `_process()` line 138, 154-155 | Handles quoted separators. **Does not support regex** -- uses `str.split()` not `re.split()`. |
| 4 | Ignore source null | **Yes** | Medium | `_process()` lines 171-175 | When true, `continue` skips the row. When false, raises `ValueError`. **Behavioral gap**: Talend produces a row with nulls when unchecked; v1 raises an exception. |
| 5 | Die on error | **Yes** | High | `_process()` lines 231-235 | Re-raises exception from the `except` block when `die_on_error=True`. |
| 6 | Schema-based output | **Yes** | Medium | `_process()` lines 148, 196-229, 238-241 | Uses schema to determine output columns and their order. |
| 7 | Passthrough columns | **Yes** | Medium | `_process()` lines 226-229 | Columns not matching the source field pattern are copied from input via case-insensitive lookup. |
| 8 | Trim extracted fields | **Yes** | High | `_process()` lines 179-180 | `[f.strip() for f in fields]` -- correct. |
| 9 | Advanced separator (numbers) | **Yes** | Medium | `_process()` lines 183-184 | Removes thousands separator and replaces decimal separator with `.`. Applied to ALL fields, not just numeric ones -- may corrupt non-numeric data. |
| 10 | Check field count | **Yes** | High | `_process()` lines 187-188 | Compares `len(fields)` to `len(extracted_columns)`. Raises `ValueError` on mismatch. |
| 11 | Check date | **Stub** | N/A | `_process()` lines 192-193 | `if check_date: pass` -- empty implementation. |
| 12 | Schema validation / type coercion | **Yes** | Medium | `_process()` lines 262-269, via `validate_schema()` | Calls `BaseComponent.validate_schema()` which handles type conversion. |
| 13 | Extracted column index mapping | **Partial** | Low | `_process()` lines 200-225 | **Complex, fragile logic** -- see detailed analysis in Section 5.2. |
| 14 | Statistics tracking | **Yes** | High | `_process()` line 255 | `_update_stats(rows_in, rows_out, rows_rejected)` |
| 15 | Empty input handling | **Yes** | High | `_process()` lines 129-132 | Returns empty DataFrames with stats (0, 0, 0). |
| 16 | **REJECT flow with errorCode/errorMessage** | **No** | N/A | -- | **No errorCode/errorMessage columns. Rejected rows go to a plain reject DataFrame with original input columns only.** |
| 17 | **Regex field separator** | **No** | N/A | -- | **Uses `str.split()`, not `re.split()`. Regex separators like `\\|` will not work.** |
| 18 | **NB_LINE_OK accurate count** | **Partial** | Low | -- | `NB_LINE_OK = rows_out` which equals `len(main_df)`. However, rows skipped by `ignore_source_null` are neither counted as OK nor REJECT -- they are lost from the count. |
| 19 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | Error message not stored in globalMap. |

### 5.2 Column Index Extraction Logic -- Detailed Analysis

The most critical piece of this component is how it maps extracted tokens to output columns. The engine uses a three-tier matching system (lines 196-229) that is fragile and does not match Talend's behavior:

**Tier 1 -- Exact source field match** (lines 197-199):
```python
if col.lower() == field.lower():
    output_row[col] = value  # Preserve original value
```
If the output column name exactly matches the source field name (case-insensitive), the original unsplit value is preserved. This is correct for passthrough of the source field.

**Tier 2 -- Direct prefix match** (lines 200-211):
```python
elif col.lower().startswith(field.lower()):
    idx_split = col[len(field):]
    idx_val = int(idx_split) - 1 if idx_split.isdigit() else None
```
If the output column name starts with the source field name (e.g., source field `product` matches column `product1`, `product2`, `product3`), the numeric suffix is parsed as a 1-based index. `product1` -> token at index 0, `product2` -> token at index 1, etc.

**Tier 3 -- Singular/plural flexible match** (lines 212-225):
```python
elif field.lower().startswith(col.lower().rstrip('0123456789')):
    base_col = col.lower().rstrip('0123456789')
    idx_val = int(col[len(base_col):]) - 1
```
If the source field name starts with the output column's base name (digits stripped), the numeric suffix is used as a 1-based index. E.g., source field `skills` matches column `skill1` because `"skills".startswith("skill")`. This handles singular/plural variations.

**Problems with this logic**:

1. **Not how Talend works**: Talend uses pure index-based mapping. The first non-passthrough column in the output schema gets token 0, the second gets token 1, etc. Column names are irrelevant to the mapping -- only schema position matters. The v1 engine's name-based matching is a fundamentally different algorithm.

2. **Tier 2 false positives**: If the source field is `id` and the output schema has columns `id`, `id_number`, `identifier`, then `id_number` and `identifier` both match Tier 2 (`startswith('id')`). But `id_number` has suffix `_number` which is not a digit, so `idx_val` is `None` and it gets `None`. `identifier` has suffix `entifier` which is not a digit, so it also gets `None`. The intent may have been to match `id1`, `id2`, etc., but the overly broad `startswith` check catches unrelated columns.

3. **Tier 3 ambiguity with `rstrip`**: `col.lower().rstrip('0123456789')` strips ALL trailing digits. So `field100` becomes `field`, `item2b` stays `item2b` (trailing `b` stops stripping). If the source field is `items` and columns are `item1`, `item2`, then `"items".startswith("item")` is true. But also `"items".startswith("ite")` would be true if a column `ite5` existed. The `rstrip` approach is fragile for column names ending in digits.

4. **Shadowing between tiers**: A column that matches Tier 2 will never reach Tier 3. But the two tiers use different base-name logic. If the source field is `product` and the column is `prod1`, it does NOT match Tier 2 (`"prod1".startswith("product")` is false) but DOES match Tier 3 (`"product".startswith("prod")` is true). Whether this is intentional is unclear.

5. **No pure index-based fallback**: If column names do not follow the `{field}{N}` pattern, the extraction produces all `None` values. Talend would still map by position regardless of column names.

### 5.3 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-EDF-001 | **P0** | **Row-by-row `iterrows()` loop**: The entire `_process()` method uses `for idx, row in input_data.iterrows()` (line 165) to process data one row at a time. This defeats pandas vectorization entirely. For a DataFrame with 1M rows, this is 100-1000x slower than vectorized `str.split(expand=True)`. This is a fundamental architectural issue. |
| ENG-EDF-002 | **P1** | **Column index extraction uses name-based matching, not position-based**: Talend maps extracted tokens to output columns by schema position. V1 uses a fragile three-tier name-matching algorithm (see Section 5.2). This produces incorrect results when column names do not follow the `{source_field}{N}` naming convention, which is valid and common in Talend jobs. |
| ENG-EDF-003 | **P1** | **No REJECT flow with errorCode/errorMessage**: Talend produces reject rows with `errorCode` and `errorMessage` columns when `DIE_ON_ERROR=false`. V1 collects rejected rows but without these extra columns. Downstream components expecting `errorCode`/`errorMessage` will fail. |
| ENG-EDF-004 | **P1** | **`ignore_source_null=false` raises exception instead of producing null row**: When `IGNORE_SOURCE_NULL` is unchecked and the source field is null, Talend produces an output row with null values in all extracted columns. V1 raises `ValueError("Source field is null")`, which either kills the job (die_on_error) or sends the row to reject. This is fundamentally different behavior. |
| ENG-EDF-005 | **P1** | **No regex field separator support**: The engine uses `str(value).split(field_separator)` (line 178), which is Python string split, not regex split. Talend supports regex separators (e.g., `\\|`, `[;,]`). Any job using regex separators will split incorrectly. |
| ENG-EDF-006 | **P2** | **Advanced separator applied to all fields, not just numeric**: Lines 183-184 apply thousands/decimal separator replacement to ALL extracted fields, including strings. If a non-numeric field contains a comma (thousands separator default), it will be silently removed. Talend only applies number formatting to numeric-typed columns. |
| ENG-EDF-007 | **P2** | **Check date is a stub**: Lines 192-193 are `if check_date: pass`. No date validation is performed. Jobs relying on strict date validation will silently pass invalid dates. |
| ENG-EDF-008 | **P2** | **Rows skipped by ignore_source_null not counted**: When `ignore_source_null=True` and a row's source field is null, the `continue` on line 173 skips the row entirely. It is not counted in `rows_out` (correct) but it IS counted in `rows_in` (line 134). The `NB_LINE_REJECT` does not reflect skipped null rows. Talend would not count these in `NB_LINE` since they produce no output. |
| ENG-EDF-009 | **P3** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur with `die_on_error=false`, the error message is not stored in globalMap for downstream reference. |
| BUG-EDF-009 | **P1** | **Engine default `field_separator=','` vs Talend `';'`**: The engine class constant `DEFAULT_FIELD_SEPARATOR = ','` (line 83) does not match Talend's documented default of `';'` (semicolon). If the converter fails to populate the `field_separator` config key, the engine falls back to a comma separator instead of a semicolon, producing silently incorrect split results. See also Section 6.1. |

### 5.4 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set via base class mechanism. But crashes at runtime due to BUG-EDF-001. |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Set correctly but may not reflect rows lost to `ignore_source_null`. |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | Same mechanism | Set correctly -- counts rows that hit the `except` block. But does not count null-skipped rows. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-EDF-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just ExtractDelimitedFields, since `_update_global_map()` is called after every component execution (via `execute()` line 218). Every component will crash at the globalMap update step. **Note**: Line 304 is OUTSIDE the for loop, not inside it. |
| BUG-EDF-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-EDF-003 | **P1** | `src/v1/engine/components/transform/extract_delimited_fields.py:165` | **Variable name shadowing with `idx`**: The `for idx, row in input_data.iterrows()` loop uses `idx` as the loop variable (the DataFrame row index). But inside the loop body, `idx_split` and `idx_val` use names that could be confused with the outer `idx`. More critically, the error message on line 232 references `row {idx}` -- if the DataFrame index is not sequential (e.g., after filtering), `idx` is the original index label, not a position. This is not strictly a bug but a maintainability and diagnostic concern. |
| BUG-EDF-004 | **P1** | `src/v1/engine/components/transform/extract_delimited_fields.py:154-155` | **Quote stripping only handles double quotes**: The separator quote stripping checks for `"` prefix/suffix but not `'` (single quotes). Talend XML may encode separators as `&quot;,&quot;` or `','`. The `&quot;` case is handled by the converter (line 299), but single-quoted values from other sources would retain the quotes, causing split to use `',"'` as the separator rather than `","`. |
| BUG-EDF-005 | **P1** | `src/v1/engine/components/transform/extract_delimited_fields.py:200-211` | **Tier 2 column matching produces false positives**: `col.lower().startswith(field.lower())` matches any column whose name begins with the source field name. If source field is `name` and output schema has `namespace`, the column `namespace` matches Tier 2. Since `"space"` is not a digit, `idx_val` is `None` and the column gets `None` instead of being copied from input. This silently corrupts passthrough columns. |
| BUG-EDF-006 | **P2** | `src/v1/engine/components/transform/extract_delimited_fields.py:228` | **`col_lookup` dict rebuilt per column per row**: Inside the triple-nested loop (`for idx, row` -> `for col in schema` -> Tier 3 `else` branch), the passthrough column lookup `{str(k).lower(): k for k in row.index}` is rebuilt for EVERY passthrough column in EVERY row. For a 10-column schema with 1M rows, this is ~10M dict constructions. Should be built once per row. Note that line 168 already builds `field_lookup` once per row, but the passthrough branch on line 228 rebuilds it independently. |
| BUG-EDF-007 | **P2** | `src/v1/engine/components/transform/extract_delimited_fields.py:87-108` | **`_validate_config()` is never called**: The method exists and validates `field` (required) and `field_separator` (type check), but it is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Missing `field` config will only cause issues at line 137 where `self.config.get('field', '')` returns empty string, leading to cryptic downstream errors. |
| BUG-EDF-008 | **P0** | `src/v1/engine/components/transform/extract_delimited_fields.py:171` | **NaN values bypass null check entirely**: Line 171 `if value is None` does NOT catch pandas NaN. `str(float('nan'))` produces literal string `'nan'` which gets split by the delimiter, producing garbage data. For example, splitting `'nan'` by `','` yields `['nan']` which is silently assigned to the first extracted column. **Fix**: use `if value is None or pd.isna(value)` to catch both `None` and `NaN`/`NaT`. |
| BUG-EDF-009 | **P1** | `src/v1/engine/components/transform/extract_delimited_fields.py:83` | **Engine default `field_separator=','` but Talend default is `';'`**: The class constant `DEFAULT_FIELD_SEPARATOR = ','` (line 83) is used as the fallback when the converter fails to set the `field_separator` config key. Talend's documented default is `";"` (semicolon). If the converter fails to set this key for any reason (e.g., missing XML parameter, converter bug), the engine uses the wrong separator, silently producing incorrect split results. |
| BUG-EDF-010 | **P1** | `src/v1/engine/components/transform/extract_delimited_fields.py:212` | **Purely numeric column names always match Tier 3**: `col.lower().rstrip('0123456789')` on a purely numeric column name like `'123'` produces an empty string `''`. Then `field.lower().startswith('')` is always `True` (every string starts with the empty string). This means numeric column names are never treated as passthrough -- their input values are silently dropped and replaced with an extracted token indexed by the full column name parsed as an integer. |
| BUG-EDF-011 | **P2** | `src/v1/engine/components/transform/extract_delimited_fields.py:154-155` | **Quote stripping can produce empty separator**: If `field_separator` is exactly `'"'` (a single double-quote character), the quote-stripping logic on lines 154-155 strips both the leading and trailing `"`, producing an empty string `''`. Calling `str.split('')` raises `ValueError: empty separator` at runtime. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-EDF-001 | **P2** | **`trim` (engine) vs `trim_all` (dedicated parser) vs `TRIM` (Talend)**: The engine reads `config.get('trim')`. The dedicated converter parser writes `config['trim_all']`. The generic converter mapper writes `config['trim']`. So the generic mapper's value is what the engine sees, and the dedicated parser's override is silently ignored. This naming inconsistency means the dedicated parser's value is dead. |
| NAME-EDF-002 | **P3** | **Class constant naming**: The class defines `DEFAULT_FIELD_SEPARATOR`, `DEFAULT_THOUSANDS_SEPARATOR`, `DEFAULT_DECIMAL_SEPARATOR` but these match the engine's `config.get()` default fallbacks. Consistent, but the constants are only used in three places each -- could be inline. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-EDF-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-EDF-002 | **P2** | "Every component MUST have its own `parse_*` method" (STANDARDS.md) | Component has BOTH a dedicated parser AND a generic mapper entry. The generic mapper should be removed since a dedicated parser exists. |
| STD-EDF-003 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts to Python types (`str`, `int`) instead of preserving Talend types. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-EDF-001 | **P3** | **Excessive debug logging in hot path**: Lines 151-152, 159-160, 246-248 log at DEBUG level inside or adjacent to the per-row loop. While DEBUG level should be filtered in production, the f-string formatting (especially `{main_df.head()}\nValues:\n{main_df.values}` on line 248) evaluates eagerly regardless of log level, causing O(n) string construction even when DEBUG is disabled. This is especially expensive for `main_df.values` which materializes the entire array. |
| DBG-EDF-002 | **P3** | **Comment artifact**: Line 1989 of `component_parser.py` contains `# ...existing code for schema parsing...` which is an editing artifact, not a real code comment. Should be removed. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-EDF-001 | **P3** | **No field name injection protection**: The `field` config value is used directly as a column name lookup key. If config comes from untrusted sources, crafted field names could potentially cause unexpected behavior in the dict lookups, though the practical risk is low since all operations are read-only on the DataFrame. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | Most log messages use `[{self.id}]` prefix; some use `[ExtractDelimitedFields]` class name instead -- **inconsistent** |
| Level usage | INFO for milestones, DEBUG for details, ERROR for failures -- mostly correct |
| Start/complete logging | `_process()` logs start (line 135) and completion (lines 258-259) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |
| **Eager f-string in DEBUG** | Line 248 uses `f"...{main_df.head()}\nValues:\n{main_df.values}"` which evaluates even when DEBUG is disabled -- **performance concern** |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Exception types | Uses generic `ValueError` and `Exception` -- does NOT use custom exceptions from `exceptions.py` (no `ConfigurationError`, `DataProcessingError`) |
| Exception chaining | Does NOT use `raise ... from e` pattern -- just `raise` on line 235 |
| `die_on_error` handling | Single try/except block wraps the per-row processing (lines 166-235). When `die_on_error=True`, exceptions propagate. When `False`, rows are appended to `reject_rows`. Correct pattern. |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Error messages include row index -- correct |
| Graceful degradation | Returns `{'main': main_df, 'reject': reject_df}` even on partial failures -- correct |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_validate_config() -> List[str]`, `_process(...) -> Dict[str, Any]` -- correct |
| Parameter types | `input_data: Optional[pd.DataFrame]` -- correct |
| Complex types | Uses `Dict[str, Any]`, `List[str]`, `Optional` -- correct |
| Class constants | No type annotations on class constants (lines 83-85) -- minor gap |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-EDF-001 | **P0** | **`iterrows()` row-by-row loop defeats pandas vectorization**: The entire extraction logic (lines 165-230) uses `for idx, row in input_data.iterrows()`. For every row, it: (a) builds a field_lookup dict (line 168), (b) splits the string (line 178), (c) iterates all schema columns (line 196), and (d) for passthrough columns, rebuilds col_lookup (line 228). This is O(rows * columns) Python-level iteration. Vectorized equivalent using `df[field].str.split(field_separator, expand=True)` would be ~100x faster for large DataFrames. For a DataFrame with 1M rows and 10 extracted columns, the iterrows approach takes minutes; vectorized takes seconds. |
| PERF-EDF-002 | **P1** | **`col_lookup` dict rebuilt per passthrough column per row**: Line 228 creates `{str(k).lower(): k for k in row.index}` inside the innermost loop. For M passthrough columns and N rows, this is O(N * M * C) dict constructions where C is the total column count. Should be built once per row (or better, once for the entire DataFrame since `row.index` is the same for all rows). |
| PERF-EDF-003 | **P2** | **`main_rows` list-of-dicts pattern**: Lines 162 and 230 build output as a list of dicts, then construct a DataFrame from it (line 240). For large datasets, this pattern is memory-inefficient -- each dict has string keys repeated for every row. A columnar approach (pre-allocate lists per column) would reduce memory overhead. |
| PERF-EDF-004 | **P3** | **Eager f-string evaluation for DEBUG logging**: Line 248 contains `f"...{main_df.head()}\nValues:\n{main_df.values}"`. Even when DEBUG logging is disabled, the f-string is evaluated, calling `main_df.head()` and `main_df.values`. For a 1M-row DataFrame, `main_df.values` materializes the entire numpy array -- a significant memory and CPU cost. Should be guarded with `if logger.isEnabledFor(logging.DEBUG)`. |
| PERF-EDF-005 | **P2** | **Schema column name list rebuilt on every row**: The list comprehension `[col['name'] for col in schema]` (line 196) is evaluated inside the per-row `iterrows()` loop. For 1M rows with a 10-column schema, this means 10M unnecessary dict lookups to rebuild the same list on every iteration. The schema does not change between rows. Should be computed once before the loop. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | **Not implemented** for this component. The `_process()` method expects a full DataFrame. `BaseComponent._execute_streaming()` calls `_process()` per chunk, which works but rebuilds all internal structures per chunk. |
| Memory threshold | Inherited from `BaseComponent.MEMORY_THRESHOLD_MB = 3072` (3GB). Above this, streaming mode activates if `execution_mode=HYBRID`. However, per-row processing means streaming provides limited benefit -- the bottleneck is Python iteration, not memory. |
| Output construction | Builds `main_rows` list (line 162) which grows linearly with input size. For very large inputs, this doubles memory (input DataFrame + output list + output DataFrame). |
| Reject construction | `reject_rows` list (line 163) stores original pandas Series objects. If most rows are rejected, this also doubles memory. |

### 7.2 Vectorization Opportunity

The entire `_process()` method (lines 129-271) could be replaced with approximately 20 lines of vectorized pandas code:

```python
# Vectorized approach (conceptual)
# 1. Split the source field
split_df = input_data[field].str.split(field_separator, expand=True)

# 2. Assign extracted columns by position
for i, col_name in enumerate(extracted_columns):
    if i < split_df.shape[1]:
        result[col_name] = split_df[i]
    else:
        result[col_name] = None

# 3. Copy passthrough columns
for col in passthrough_columns:
    result[col] = input_data[col]
```

This would transform the O(rows * columns) Python loop into O(columns) vectorized operations, each operating at C speed internally. Expected speedup: 50-200x for DataFrames with 100K+ rows.

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `ExtractDelimitedFields` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter unit tests | **No** | -- | No tests for `_map_component_parameters('tExtractDelimitedFields')` or `parse_textract_delimited_fields()` |

**Key finding**: The v1 engine has ZERO tests for this component. All 272 lines of engine code and both converter code paths are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic field extraction | P0 | Split `"Alice,Bob,Charlie"` by `,` into 3 output columns. Verify values match by position. |
| 2 | Passthrough columns preserved | P0 | Input has `id`, `name`, `data` columns. Extract `data` field. Verify `id` and `name` are preserved in output with original values. |
| 3 | Schema enforcement | P0 | Extract into typed schema (int, float, string columns). Verify correct type coercion via `validate_schema()`. |
| 4 | Empty input DataFrame | P0 | Pass empty DataFrame. Verify returns `{'main': empty_df, 'reject': empty_df}` with stats (0, 0, 0). |
| 5 | None input | P0 | Pass `None`. Verify returns empty result with stats (0, 0, 0). |
| 6 | Die on error + extraction failure | P0 | Set `die_on_error=True` with `check_fields_num=True` and wrong field count. Verify exception is raised. |
| 7 | Statistics tracking | P0 | Process 10 rows, 2 of which fail. Verify `NB_LINE=10`, `NB_LINE_OK=8`, `NB_LINE_REJECT=2`. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Null source field + ignore_source_null=True | P1 | Source field is null/NaN. Verify row is silently skipped, not in output or reject. |
| 9 | Null source field + ignore_source_null=False | P1 | Source field is null. Verify row goes to reject (not exception unless die_on_error). |
| 10 | Trim extracted fields | P1 | Source `" Alice , Bob , Charlie "`. Verify trim removes whitespace from each token. |
| 11 | Advanced separator for numbers | P1 | Source `"1,234.56;2,345.67"` with `;` separator, thousands=`,`, decimal=`.`. Verify numeric conversion. |
| 12 | Check fields num mismatch | P1 | Schema expects 3 extracted columns but source has 2 tokens. Verify rejection. |
| 13 | Case-insensitive field lookup | P1 | Source field config is `"Product"` but input column is `"product"` (lowercase). Verify correct match. |
| 14 | Custom separator (tab) | P1 | Field separator `\t`. Verify tab-separated values are correctly split. |
| 15 | Custom separator (pipe) | P1 | Field separator `|`. Verify pipe-separated values are correctly split. |
| 16 | Multiple extracted columns from one field | P1 | Source has 5 delimited values, schema has 5 extracted columns + 2 passthrough. Verify all 7 output columns correct. |
| 17 | More tokens than columns | P1 | Source has 5 tokens but schema defines only 3 extracted columns. Verify extra tokens are silently dropped. |
| 18 | Fewer tokens than columns | P1 | Source has 2 tokens but schema defines 5 extracted columns. Verify missing columns get `None`. |
| 19 | Context variable in config | P1 | `field_separator` contains `${context.delimiter}`. Verify resolution via context manager. |
| 20 | GlobalMap integration | P1 | Verify `{id}_NB_LINE`, `{id}_NB_LINE_OK`, `{id}_NB_LINE_REJECT` are set in globalMap after execution. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 21 | Large DataFrame performance | P2 | Process 100K rows with 5 extracted columns. Measure execution time. Flag if > 30 seconds (vectorized should be < 1 second). |
| 22 | Non-matching column names | P2 | Schema has extracted columns like `firstname`, `lastname` (not following `{field}{N}` convention). Verify correct behavior (currently produces None -- should work by position). |
| 23 | Column name that starts with field name but is unrelated | P2 | Source field `name`, output schema has `namespace` column. Verify `namespace` is treated as passthrough, not extracted. |
| 24 | Unicode in source field | P2 | Source contains unicode characters. Verify correct splitting and output. |
| 25 | Empty string in source field | P2 | Source field is `""` (empty string). Verify behavior (split produces `[""]`). |
| 26 | Reject DataFrame structure | P2 | Verify rejected rows contain original input columns (matching input_data.columns). |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-EDF-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value`. Line 304 is OUTSIDE the for loop, so `stat_name` is also undefined at that scope. Remove `{stat_name}: {value}` entirely -- NB_LINE/NB_LINE_OK/NB_LINE_REJECT are already logged explicitly in the same f-string. Will crash ALL components when `global_map` is set. |
| BUG-EDF-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| BUG-EDF-008 | Bug | NaN values bypass null check entirely. Line 171 `if value is None` does NOT catch pandas NaN. `str(float('nan'))` produces literal string `'nan'` which gets split by delimiter, producing garbage data. Fix: use `if value is None or pd.isna(value)`. |
| PERF-EDF-001 | Performance | `iterrows()` row-by-row loop defeats pandas vectorization. 100-1000x slower than vectorized `str.split(expand=True)`. Blocking for production use with datasets > 10K rows. |
| TEST-EDF-001 | Testing | Zero v1 unit tests for this component. All 272 lines of engine code and both converter code paths are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-EDF-001 | Converter | Dual-parser conflict: `_map_component_parameters()` and `parse_textract_delimited_fields()` both run for this component with overlapping keys and conflicting logic. |
| CONV-EDF-002 | Converter | Misleading comment on line 294: says `# tExtractJSONFields mapping` but code handles `tExtractDelimitedFields`. Copy-paste error. |
| ENG-EDF-002 | Engine | Column index extraction uses name-based matching instead of Talend's position-based mapping. Produces incorrect results for non-`{field}{N}` naming conventions. |
| ENG-EDF-003 | Engine | No REJECT flow with `errorCode`/`errorMessage` columns. Rejected rows are plain input rows without error metadata. |
| ENG-EDF-004 | Engine | `ignore_source_null=false` raises exception instead of producing null row (Talend behavior). |
| ENG-EDF-005 | Engine | No regex field separator support. Uses `str.split()` not `re.split()`. Regex separators like `\\|` or `[;,]` will not work. |
| BUG-EDF-003 | Bug | Variable name shadowing: outer `idx` (row index) vs inner `idx_split`/`idx_val`. Diagnostic confusion in error messages for non-sequential DataFrame indices. |
| BUG-EDF-004 | Bug | Quote stripping only handles double quotes, not single quotes. Single-quoted separators from some Talend XML sources will be parsed incorrectly. |
| BUG-EDF-005 | Bug | Tier 2 column matching false positives: `startswith(field)` matches unrelated columns (e.g., field=`name` matches `namespace`), causing passthrough columns to get `None` instead of their input values. |
| BUG-EDF-009 | Bug | Engine default `field_separator=','` (line 83) but Talend default is `';'`. If converter fails to set this key, engine uses wrong separator. |
| BUG-EDF-010 | Bug | Purely numeric column names always match Tier 3 (line 212). `col.lower().rstrip('0123456789')` on a numeric name like `'123'` produces empty string. `field.lower().startswith('')` is always True. Numeric columns are never treated as passthrough -- their input values are silently dropped. |
| PERF-EDF-002 | Performance | `col_lookup` dict rebuilt per passthrough column per row: O(N * M * C) dict constructions in the innermost loop. |
| TEST-EDF-002 | Testing | No integration test for this component in a multi-step v1 job (e.g., `tFileInputDelimited -> tExtractDelimitedFields -> tFileOutputDelimited`). |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-EDF-003 | Converter | `trim` vs `trim_all` key name mismatch. Engine reads `trim`; dedicated parser writes `trim_all` (dead code). |
| CONV-EDF-004 | Converter | `row_separator` and `remove_empty_row` extracted but irrelevant to this component. Copied from file input parser. |
| CONV-EDF-005 | Converter | Schema type format violates STANDARDS.md: Python types (`str`) instead of Talend types (`id_String`). |
| ENG-EDF-006 | Engine | Advanced separator applied to all fields, not just numeric. Corrupts non-numeric data containing thousands separator character. |
| ENG-EDF-007 | Engine | `check_date` is a stub (`if check_date: pass`). No date validation performed. |
| ENG-EDF-008 | Engine | Rows skipped by `ignore_source_null` not reflected in statistics. `NB_LINE` counts them but `NB_LINE_REJECT` does not. |
| BUG-EDF-006 | Bug | `col_lookup` rebuilt per column per row in passthrough branch (line 228). Massive redundant computation. |
| BUG-EDF-007 | Bug | `_validate_config()` is dead code -- never called by any code path. 22 lines of unreachable validation. |
| BUG-EDF-011 | Bug | Quote stripping can produce empty separator (lines 154-155). If `field_separator` is exactly `'"'`, stripping produces `''` which crashes `str.split('')` with `ValueError: empty separator`. |
| PERF-EDF-005 | Performance | Schema column name list `[col['name'] for col in schema]` rebuilt on every row (line 196). For 1M rows x 10 columns = 10M unnecessary dict lookups. |
| STD-EDF-001 | Standards | `_validate_config()` exists but never called -- dead validation. |
| STD-EDF-002 | Standards | Both generic and dedicated parser exist for same component -- violates single-parser principle. |
| STD-EDF-003 | Standards | Converter uses Python type format in schema instead of Talend type format. |
| PERF-EDF-003 | Performance | `main_rows` list-of-dicts pattern is memory-inefficient for large datasets. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-EDF-006 | Converter | `SCHEMA_OPT_NUM` and `CONNECTION_FORMAT` extracted unnecessarily (no runtime impact). |
| ENG-EDF-009 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap. |
| NAME-EDF-001 | Naming | `trim` (engine) vs `trim_all` (dedicated parser) naming inconsistency. |
| NAME-EDF-002 | Naming | Class constant naming is consistent but could be inline. |
| DBG-EDF-001 | Debug | Eager f-string evaluation in DEBUG logging materializes entire DataFrame. |
| DBG-EDF-002 | Debug | `# ...existing code for schema parsing...` comment artifact in converter. |
| SEC-EDF-001 | Security | No field name injection protection (low practical risk). |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 5 | 3 bugs (2 cross-cutting, 1 NaN bypass), 1 performance, 1 testing |
| P1 | 13 | 2 converter, 4 engine, 5 bugs, 1 performance, 1 testing |
| P2 | 14 | 3 converter, 3 engine, 3 bugs, 3 standards, 2 performance |
| P3 | 7 | 1 converter, 1 engine, 2 naming, 2 debug, 1 security |
| **Total** | **39** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-EDF-001): Line 304 is OUTSIDE the for loop (line 301), so `stat_name` and `value` are both undefined at that point. Remove the `{stat_name}: {value}` interpolation entirely -- `NB_LINE`, `NB_LINE_OK`, and `NB_LINE_REJECT` are already logged explicitly in the same f-string on that line. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message fix only).

2. **Fix `GlobalMap.get()` bug** (BUG-EDF-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter).

3. **Replace `iterrows()` with vectorized extraction** (PERF-EDF-001): Rewrite `_process()` to use `df[field].str.split(field_separator, expand=True)` for the core extraction, then assign columns by position (not by name matching). This is the single highest-impact change: 100-1000x speedup for large DataFrames. **Risk**: Medium -- requires rethinking the column assignment logic. Recommend implementing the vectorized path alongside the existing row-by-row path as a fallback.

4. **Fix NaN bypass in null check** (BUG-EDF-008): On line 171, change `if value is None` to `if value is None or pd.isna(value)`. This prevents pandas NaN values from being converted to the literal string `'nan'` and split by the delimiter, producing garbage data. **Impact**: Fixes silent data corruption for any row with NaN in the source field. **Risk**: Very low.

5. **Create unit test suite** (TEST-EDF-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic extraction, passthrough preservation, schema enforcement, empty/null input handling, die_on_error, and statistics tracking. Without these, no engine behavior is verified.

### Short-Term (Hardening)

6. **Fix column index extraction to use position-based mapping** (ENG-EDF-002): Replace the three-tier name-matching logic (lines 196-229) with Talend's position-based approach. Identify which output schema columns are passthrough (exact name match with input columns) and which are extracted (all others). Map extracted columns to split tokens by position order, regardless of column names. This fixes the false-positive bug (BUG-EDF-005) and the numeric column name bug (BUG-EDF-010) as well.

7. **Resolve dual-parser conflict** (CONV-EDF-001): Add `tExtractDelimitedFields` to the `components_with_dedicated_parsers` list in `parse_base_component()` (line 421). Then enhance `parse_textract_delimited_fields()` to extract ALL needed parameters (currently missing: `field`, `ignore_source_null`, `check_fields_num`, `check_date`). Remove the `_map_component_parameters()` branch for this component (lines 295-314). Fix the misleading comment on line 294 (CONV-EDF-002).

8. **Fix engine default `field_separator`** (BUG-EDF-009): Change the class constant `DEFAULT_FIELD_SEPARATOR = ','` on line 83 to `DEFAULT_FIELD_SEPARATOR = ';'` to match Talend's documented default. This ensures correct behavior when the converter fails to set the config key. **Risk**: Very low.

9. **Fix `ignore_source_null=false` behavior** (ENG-EDF-004): When the source field is null and `ignore_source_null=false`, produce an output row with `None` in all extracted columns (matching Talend behavior) instead of raising `ValueError`.

10. **Implement REJECT flow with errorCode/errorMessage** (ENG-EDF-003): When rows fail extraction and `die_on_error=false`, build reject rows with ALL original schema columns plus `errorCode` (String) and `errorMessage` (String). Return these in the `reject` key of the result dict.

11. **Add regex field separator support** (ENG-EDF-005): Detect whether the field separator contains regex metacharacters. If so, use `re.split(field_separator, value)` instead of `str(value).split(field_separator)`. This enables support for separators like `\\|`, `[;,]`, etc.

12. **Fix Tier 2 false positive matching** (BUG-EDF-005): If keeping name-based matching as a fallback, require an EXACT match followed by digits only, not a `startswith` prefix. E.g., column `product1` should match field `product` + digits `1`, but column `production` should NOT match.

13. **Fix numeric column name Tier 3 match** (BUG-EDF-010): Add a guard in Tier 3 (line 212) to skip the match when `base_col` (after `rstrip('0123456789')`) is empty. This prevents purely numeric column names from always matching every source field.

14. **Fix quote stripping empty separator crash** (BUG-EDF-011): After the quote-stripping logic on lines 154-155, add a guard to check if `field_separator` is empty. If so, raise a clear `ConfigurationError` or fall back to the default separator rather than allowing `str.split('')` to crash.

15. **Fix trim key name mismatch** (CONV-EDF-003): Change the dedicated parser (line 1986) to write `config['trim']` instead of `config['trim_all']`, matching what the engine reads.

### Long-Term (Optimization)

16. **Hoist schema column name list out of row loop** (PERF-EDF-005): Move `[col['name'] for col in schema]` (line 196) above the `for idx, row in input_data.iterrows()` loop so it is computed once, not per row. **Risk**: Very low.

17. **Implement check_date** (ENG-EDF-007): After extraction, validate date-typed columns against the schema pattern using `pd.to_datetime(format=pattern, errors='coerce')`. Rows where date conversion failed (NaT) should be routed to REJECT.

18. **Restrict advanced separator to numeric columns only** (ENG-EDF-006): Check the schema type of each extracted column before applying thousands/decimal separator replacement. Only apply to numeric types (`id_Integer`, `id_Long`, `id_Float`, `id_Double`, `id_BigDecimal`).

19. **Guard DEBUG logging** (DBG-EDF-001): Wrap expensive debug logging (especially line 248) with `if logger.isEnabledFor(logging.DEBUG)` to prevent eager f-string evaluation in production.

20. **Wire up `_validate_config()`** (BUG-EDF-007): Add a call to `_validate_config()` at the beginning of `_process()`, checking the returned error list and raising appropriate exceptions.

21. **Remove irrelevant converter parameters** (CONV-EDF-004): Remove `row_separator`, `remove_empty_row`, `schema_opt_num`, and `connection_format` from the converter output for this component. These are not used by the engine and add config noise.

22. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-EDF-009): In the `except` block (line 231), call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))` when `global_map` is available.

23. **Create integration test** (TEST-EDF-002): Build an end-to-end test exercising `tFileInputDelimited -> tExtractDelimitedFields -> tFileOutputDelimited` in the v1 engine, verifying correct extraction, schema enforcement, and statistics propagation.

---

## Appendix A: Converter Parameter Mapping Code

### Generic Mapper (`_map_component_parameters`, lines 295-314)

```python
# tExtractJSONFields mapping   <-- BUG: Comment says tExtractJSONFields, code handles tExtractDelimitedFields
elif component_type == 'tExtractDelimitedFields':
    sep = config_raw.get('FIELDSEPARATOR', ';')
    sep = sep.strip()
    # Handle XML-encoded and plain quoted values
    if (sep.startswith('&quot;') and sep.endswith('&quot;')) or (sep.startswith('"') and sep.endswith('"')):
        sep = sep[1:-1]
    return {
        'field': config_raw.get('FIELD', ''),
        'field_separator': sep,
        'ignore_source_null': config_raw.get('IGNORE_SOURCE_NULL', False),
        'die_on_error': config_raw.get('DIE_ON_ERROR', False),
        'advanced_separator': config_raw.get('ADVANCED_SEPARATOR', False),
        'thousands_separator': config_raw.get('THOUSANDS_SEPARATOR', ','),
        'decimal_separator': config_raw.get('DECIMAL_SEPARATOR', '.'),
        'trim': config_raw.get('TRIM', False),
        'check_fields_num': config_raw.get('CHECK_FIELDS_NUM', False),
        'check_date': config_raw.get('CHECK_DATE', False),
        'schema_opt_num': config_raw.get('SCHEMA_OPT_NUM', '100'),
        'connection_format': config_raw.get('CONNECTION_FORMAT', 'row')
    }
```

**Notes on this code**:
- Line 294: Comment says `tExtractJSONFields` but code handles `tExtractDelimitedFields`. Copy-paste error.
- Lines 296-300: Quote stripping handles both `&quot;` (XML entity) and `"` (plain) formats. But the `&quot;` check uses `startswith`/`endswith` with the full entity string, then slices `[1:-1]` which only removes one character from each end. For `&quot;,&quot;`, this produces `quot;,&quo` -- incorrect. The intent may have been to handle the case where the converter has already decoded XML entities.
- Line 304: `IGNORE_SOURCE_NULL` defaults to `False` (a Python boolean). But if the Talend XML has this as a CHECK field, `parse_base_component()` already converted it to `True`/`False` boolean on line 446.
- Line 305: `DIE_ON_ERROR` defaults to `False`, but Talend default is `True` (checked). This mismatch means jobs relying on Talend's default will have `die_on_error=False` instead of `True`.

### Dedicated Parser (`parse_textract_delimited_fields`, lines 1973-1990)

```python
def parse_textract_delimited_fields(self, node, component: Dict) -> Dict:
    """Parse tExtractDelimitedFields specific configuration"""
    config = component['config']

    def get_param(name, default=None):
        elem = node.find(f'.//elementParameter[@name="{name}"]')
        return elem.get('value', default) if elem is not None else default

    config['field_separator'] = get_param('FIELDSEPARATOR', ';')
    config['row_separator'] = get_param('ROWSEPARATOR', '\n')
    config['advanced_separator'] = get_param('ADVANCED_SEPARATOR', 'false').lower() == 'true'
    config['thousands_separator'] = get_param('THOUSANDS_SEPARATOR', ',')
    config['decimal_separator'] = get_param('DECIMAL_SEPARATOR', '.')
    config['trim_all'] = get_param('TRIMALL', 'false').lower() == 'true'
    config['remove_empty_row'] = get_param('REMOVE_EMPTY_ROW', 'false').lower() == 'true'
    config['die_on_error'] = get_param('DIE_ON_ERROR', 'false').lower() == 'true'
    # ...existing code for schema parsing...
    return component
```

**Notes on this code**:
- The dedicated parser reads raw XML values (not pre-processed by generic loop), so it does its own boolean parsing via `.lower() == 'true'`.
- `field_separator` is read as raw XML value with default `';'`. No quote stripping is performed, unlike the generic mapper. If the XML value is `","`, the engine receives the quoted value.
- `trim_all` is written to config, but the engine reads `trim`. Dead code.
- `row_separator` and `remove_empty_row` are irrelevant to this component (it does not read files).
- The dedicated parser does NOT extract `field`, `ignore_source_null`, `check_fields_num`, or `check_date` -- those persist from the generic mapper.

---

## Appendix B: Engine Class Structure

```
ExtractDelimitedFields (BaseComponent)
    Constants:
        DEFAULT_FIELD_SEPARATOR = ','
        DEFAULT_THOUSANDS_SEPARATOR = ','
        DEFAULT_DECIMAL_SEPARATOR = '.'

    Methods:
        _validate_config() -> List[str]          # DEAD CODE -- never called
        _process(input_data) -> Dict[str, Any]   # Main entry point (row-by-row iterrows loop)

    Processing Logic (inside _process):
        1. Extract config values with defaults
        2. Determine output columns and extracted columns from schema
        3. For each row (iterrows):
           a. Case-insensitive field lookup
           b. Null check (skip or raise)
           c. Split by field separator
           d. Apply trim (if enabled)
           e. Apply advanced separator (if enabled)
           f. Check field count (if enabled)
           g. Check date (stub -- no-op)
           h. Build output row:
              - Tier 1: Exact match -> preserve original value
              - Tier 2: Prefix match + digit suffix -> extract by index
              - Tier 3: Flexible singular/plural match -> extract by index
              - Else: Passthrough from input
        4. Build output DataFrame from list of dicts
        5. Validate schema (type coercion)
        6. Update stats, return main + reject
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Fix |
|------------------|---------------|--------|-----------------|
| `FIELD` | `field` | Mapped (generic only) | -- |
| `FIELDSEPARATOR` | `field_separator` | Mapped (both parsers -- conflict) | P1 (resolve dual-parser) |
| `IGNORE_SOURCE_NULL` | `ignore_source_null` | Mapped (generic only) | -- |
| `DIE_ON_ERROR` | `die_on_error` | Mapped (both parsers -- conflict) | P1 (default mismatch: v1=False, Talend=True) |
| `ADVANCED_SEPARATOR` | `advanced_separator` | Mapped (both parsers -- conflict) | P1 (resolve dual-parser) |
| `THOUSANDS_SEPARATOR` | `thousands_separator` | Mapped (both parsers) | -- |
| `DECIMAL_SEPARATOR` | `decimal_separator` | Mapped (both parsers) | -- |
| `TRIM` | `trim` (generic) / `trim_all` (dedicated -- dead) | Mapped with key mismatch | P2 (fix key name) |
| `CHECK_FIELDS_NUM` | `check_fields_num` | Mapped (generic only) | -- |
| `CHECK_DATE` | `check_date` | Mapped (generic only) | -- (engine stub) |
| `ROWSEPARATOR` | `row_separator` | Mapped (dedicated only) | P2 (remove -- irrelevant) |
| `REMOVE_EMPTY_ROW` | `remove_empty_row` | Mapped (dedicated only) | P2 (remove -- irrelevant) |
| `SCHEMA_OPT_NUM` | `schema_opt_num` | Mapped (generic only) | P3 (remove -- no runtime use) |
| `CONNECTION_FORMAT` | `connection_format` | Mapped (generic only) | P3 (remove -- no runtime use) |
| `TSTATCATCHER_STATS` | -- | Not Mapped | -- (low priority) |
| `LABEL` | -- | Not Mapped | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not Mapped | -- (always Built-In) |

---

## Appendix D: Type Mapping Comparison

### Converter Output (ExpressionConverter.convert_type)

| Talend Type | Converter Output |
|-------------|-----------------|
| `id_String` | `str` |
| `id_Integer` | `int` |
| `id_Long` | `int` |
| `id_Float` | `float` |
| `id_Double` | `float` |
| `id_Boolean` | `bool` |
| `id_Date` | `datetime` |
| `id_BigDecimal` | `Decimal` |

### Engine validate_schema() (post-extraction conversion in base_component.py)

| Type Input | Pandas Dtype | Conversion Method |
|------------|-------------|-------------------|
| `id_String` / `str` | `object` | No conversion |
| `id_Integer` / `int` | `int64` (non-nullable) | `pd.to_numeric(errors='coerce')` then `fillna(0).astype('int64')` |
| `id_Long` / `long` | `int64` (non-nullable) | Same as Integer |
| `id_Float` / `float` | `float64` | `pd.to_numeric(errors='coerce')` |
| `id_Double` / `double` | `float64` | Same as Float |
| `id_Boolean` / `bool` | `bool` | `.astype('bool')` |
| `id_Date` / `date` | `datetime64[ns]` | `pd.to_datetime()` -- no format specification, uses pandas' flexible parser |
| `id_BigDecimal` / `decimal` | `object` | No conversion in validate_schema |

**Key note for ExtractDelimitedFields**: All extracted values start as strings (the result of `str.split()`). The `validate_schema()` call on line 263 converts these strings to the target types. This means numeric and date type conversions always go through `pd.to_numeric(errors='coerce')` or `pd.to_datetime()`, both of which silently produce NaN/NaT on failure rather than raising errors. This effectively means type conversion errors are swallowed, not routed to REJECT -- a silent data quality gap.

---

## Appendix E: Detailed Code Analysis

### `_validate_config()` (Lines 87-108)

This method validates:
- `field` is present and non-empty (required)
- `field_separator` is a string (if present, type check only)

**Not validated**: `ignore_source_null`, `die_on_error`, `advanced_separator`, `thousands_separator`, `decimal_separator`, `trim`, `check_fields_num`, `check_date`, `schema`.

**Critical**: This method is never called. Even if it were, it returns a list of error strings but no caller checks the list or raises exceptions. Missing `field` config will only surface at runtime when `self.config.get('field', '')` returns empty string, leading to the field_lookup finding an empty-string match (line 169), which then looks up `row.get('', None)` -- which returns `None`, triggering the `ignore_source_null` path.

### `_process()` (Lines 110-271)

The main processing method:
1. Lines 129-132: Early return for empty/None input
2. Lines 134-148: Extract all config values with defaults
3. Lines 153-155: Strip quotes from field_separator
4. Lines 157-160: Build `output_columns` (all schema columns except source field) and `extracted_columns` (output columns starting with source field name)
5. Lines 162-163: Initialize `main_rows` and `reject_rows` accumulators
6. Lines 165-235: **Row-by-row iterrows loop** -- the performance bottleneck
7. Lines 238-243: Build output DataFrames from accumulated lists
8. Lines 251-255: Update statistics
9. Lines 262-269: Schema validation and column ordering
10. Line 271: Return `{'main': main_df, 'reject': reject_df}`

### Column Matching (Lines 196-229)

Four branches determine how each output column gets its value:

1. **Exact match** (line 197-199): `col.lower() == field.lower()` -- preserve original value
2. **Prefix match** (line 200-211): `col.lower().startswith(field.lower())` -- extract by numeric suffix
3. **Flexible match** (line 212-225): `field.lower().startswith(col.lower().rstrip('0123456789'))` -- singular/plural handling
4. **Passthrough** (line 226-229): Copy from input row

**Tier 2 detail**: `idx_split = col[len(field):]` extracts the part of the column name after the field name. If this is a digit string, it is parsed as a 1-based index into the split tokens. Example: field=`product`, col=`product3` -> `idx_split="3"` -> `idx_val=2` -> `fields[2]`.

**Tier 3 detail**: `base_col = col.lower().rstrip('0123456789')` strips trailing digits from the column name. Then checks if `field.lower().startswith(base_col)`. If true, the stripped digits are parsed as a 1-based index. Example: field=`skills`, col=`skill1` -> `base_col="skill"` -> `"skills".startswith("skill")` is true -> `idx_val=0` -> `fields[0]`.

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty source field value

| Aspect | Detail |
|--------|--------|
| Input | Source field value is `""` (empty string) |
| Talend behavior | `str.split()` produces `[""]` (one empty token). First extracted column gets empty string. |
| V1 behavior | `str("").split(",")` produces `[""]`. Same as Talend. **Correct.** |

### Edge Case 2: Source field is null/NaN

| Aspect | Detail |
|--------|--------|
| Input | Source field value is `None` or `NaN` |
| Talend behavior (ignore=true) | Row silently skipped -- no output row |
| Talend behavior (ignore=false) | Output row generated with null in all extracted columns |
| V1 behavior (ignore=true) | `continue` -- row skipped. **Correct.** |
| V1 behavior (ignore=false) | Raises `ValueError("Source field is null")`. **INCORRECT** -- should produce null row. |

### Edge Case 3: More tokens than extracted columns

| Aspect | Detail |
|--------|--------|
| Input | 5 tokens but only 3 extracted columns in schema |
| Talend behavior | Extra tokens silently discarded |
| V1 behavior | Tier 2 matching: `idx_val` for columns 1-3 are in range, extras are never accessed. **Correct** (tokens 4 and 5 are ignored). |

### Edge Case 4: Fewer tokens than extracted columns

| Aspect | Detail |
|--------|--------|
| Input | 2 tokens but 5 extracted columns in schema |
| Talend behavior | Missing columns get null |
| V1 behavior | Tier 2 matching: `idx_val >= len(fields)` check (line 208) produces `None`. **Correct.** |

### Edge Case 5: Source field name matches extracted column name pattern

| Aspect | Detail |
|--------|--------|
| Input | Source field is `item`, extracted columns are `item`, `item1`, `item2` |
| Talend behavior | `item` in output preserves original value; `item1`, `item2` get extracted tokens |
| V1 behavior | Tier 1 catches `item` (exact match). Tier 2 catches `item1`, `item2` (prefix match). **Correct.** |

### Edge Case 6: Column name starts with field name but is unrelated

| Aspect | Detail |
|--------|--------|
| Input | Source field is `name`, output column is `namespace` |
| Talend behavior | `namespace` treated as a passthrough column (or new extracted column by position) |
| V1 behavior | Tier 2: `"namespace".startswith("name")` is TRUE. `idx_split = "space"`. `"space".isdigit()` is FALSE. `idx_val = None`. Output: `None`. **BUG** -- `namespace` gets `None` instead of its input value. Never reaches Tier 4 (passthrough). |

### Edge Case 7: Singular/plural name matching

| Aspect | Detail |
|--------|--------|
| Input | Source field is `skills`, extracted columns are `skill1`, `skill2`, `skill3` |
| Talend behavior | By position: `skill1` = token 0, `skill2` = token 1, `skill3` = token 2 |
| V1 behavior | Tier 2: `"skill1".startswith("skills")` is FALSE. Tier 3: `base_col = "skill"`, `"skills".startswith("skill")` is TRUE. `idx_val = 0`. **Correct** for this specific case, but relies on naming convention rather than position. |

### Edge Case 8: Die on error default mismatch

| Aspect | Detail |
|--------|--------|
| Config | No explicit `die_on_error` setting in Talend job |
| Talend behavior | Default is `true` (checked) -- errors stop the job |
| V1 behavior | Generic mapper default is `False` (line 305 of component_parser.py). Engine default is `False` (line 140). **MISMATCH** -- V1 silently continues on errors that should stop the job. |

### Edge Case 9: Field separator with regex metacharacters

| Aspect | Detail |
|--------|--------|
| Input | Field separator is `|` (pipe -- regex metacharacter) |
| Talend behavior | Talend documentation says to use `\\|` for regex operators. Standard `|` works as regex alternation. |
| V1 behavior | `str.split('|')` treats `|` as a literal character (Python string split ignores regex). **Different from Talend** but accidentally correct for the common single-pipe case. `str.split('\\|')` would look for literal `\|` which is wrong. |

### Edge Case 10: Schema with no extracted columns (all passthrough)

| Aspect | Detail |
|--------|--------|
| Input | Output schema has same columns as input, none matching the field name pattern |
| Talend behavior | All columns are passthrough. The split happens but no tokens are assigned. |
| V1 behavior | `extracted_columns` is empty (line 158). `output_columns` contains all non-field columns. All go to Tier 4 (passthrough). The split still happens (line 178) but results are unused. **Functionally correct** but wasteful. |

---

## Appendix G: Cross-Cutting Issues Shared with Other Components

The following issues are not specific to `ExtractDelimitedFields` but affect it:

| ID | Location | Shared With | Description |
|----|----------|-------------|-------------|
| BUG-EDF-001 | `base_component.py:304` | ALL components | `_update_global_map()` undefined variable `value` |
| BUG-EDF-002 | `global_map.py:28` | ALL components | `GlobalMap.get()` undefined parameter `default` |
| STD-EDF-003 | `component_parser.py` | ALL components using generic schema extraction | Schema types converted to Python format instead of Talend format |

These cross-cutting issues are the highest priority fixes because resolving them benefits the entire engine, not just this component.

---

## Appendix H: Line-by-Line Engine Code Walkthrough

### Lines 1-18: Module Header and Imports

```python
"""
ExtractDelimitedFields - Extracts fields from a delimited string based on configuration.

Talend equivalent: tExtractDelimitedFields

This component splits a delimited string field into multiple output columns
based on the specified field separator. Supports advanced number formatting,
field validation, and flexible schema mapping.
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)
```

**Assessment**: Clean imports. Uses only `logging`, `typing`, `pandas`, and `BaseComponent`. No unnecessary imports. Module-level logger follows STANDARDS.md pattern. The docstring accurately describes the component's purpose.

**Missing imports**: `re` module is not imported, which is why regex field separators are not supported. If regex support is added, `import re` would be needed. Also missing `decimal.Decimal` for BigDecimal handling, but this is handled by `validate_schema()` in the base class.

### Lines 20-80: Class Definition and Docstring

The class `ExtractDelimitedFields` inherits from `BaseComponent`. The docstring is comprehensive (60 lines), documenting:
- Purpose and behavior
- Configuration parameters with types and defaults
- Inputs and outputs
- Statistics keys
- Example configuration
- Notes on behavior

**Assessment**: The docstring is thorough and well-structured. However, it does not mention the three-tier column matching logic, which is the most complex and non-obvious behavior. A maintainer reading only the docstring would expect simple index-based extraction. The example configuration (lines 65-73) shows a realistic schema with `product`, `product1`, `product2`, `product3` columns, which is the Tier 2 naming convention. There is no example showing Tier 3 (singular/plural) or Tier 4 (pure passthrough).

**Concern**: Line 76 says "Field names are matched case-insensitively" which is correct. Line 78 says "Extracted fields are mapped by position (field1, field2, etc.)" which is MISLEADING -- it implies position-based mapping but the actual implementation uses name-based matching. The "(field1, field2, etc.)" parenthetical further reinforces the expectation that column names must follow the `{field}{N}` convention.

### Lines 82-86: Class Constants

```python
# Class constants for default values
DEFAULT_FIELD_SEPARATOR = ','
DEFAULT_THOUSANDS_SEPARATOR = ','
DEFAULT_DECIMAL_SEPARATOR = '.'
```

**Assessment**: Three constants defined. Note that `DEFAULT_FIELD_SEPARATOR = ','` (comma) differs from Talend's default of `';'` (semicolon). This is a default mismatch that the converter is responsible for overriding. The converter's generic mapper also defaults to `';'` (line 296 of component_parser.py), so the engine default is only used when the converter does not provide a value -- which should never happen for properly converted jobs.

**Missing constants**: No constants for `DEFAULT_IGNORE_SOURCE_NULL`, `DEFAULT_DIE_ON_ERROR`, `DEFAULT_TRIM`, `DEFAULT_CHECK_FIELDS_NUM`, `DEFAULT_CHECK_DATE`, `DEFAULT_ADVANCED_SEPARATOR`. These are all handled as inline defaults in `config.get()` calls. While not a bug, using constants would improve consistency and make default values more discoverable.

### Lines 87-108: `_validate_config()` (Dead Code)

```python
def _validate_config(self) -> List[str]:
    errors = []
    if 'field' not in self.config:
        errors.append("Missing required config: 'field'")
    elif not self.config.get('field'):
        errors.append("Config 'field' cannot be empty")
    if 'field_separator' in self.config:
        field_sep = self.config['field_separator']
        if not isinstance(field_sep, str):
            errors.append("Config 'field_separator' must be a string")
    return errors
```

**Assessment**: This method is DEAD CODE -- never called anywhere. Even if called, it only validates two of the twelve config parameters:
1. `field` -- required, non-empty
2. `field_separator` -- string type check (only if present)

**Not validated** (10 missing):
- `ignore_source_null` -- should be boolean
- `die_on_error` -- should be boolean
- `advanced_separator` -- should be boolean
- `thousands_separator` -- should be string, single character
- `decimal_separator` -- should be string, single character
- `trim` -- should be boolean
- `check_fields_num` -- should be boolean
- `check_date` -- should be boolean
- `schema` -- should be non-empty list of dicts with `name` key
- `output_schema` -- should match schema format if present

**Recommendation**: Either wire this method into `_process()` (call at the start, check for errors, raise/return based on die_on_error) or delete it entirely. Dead validation code is worse than no validation -- it gives a false sense of safety during code review.

### Lines 110-132: `_process()` Entry and Empty Input Handling

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    if input_data is None or input_data.empty:
        logger.warning(f"[{self.id}] Empty input received")
        self._update_stats(0, 0, 0)
        return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}
```

**Assessment**: Correct handling of empty/None input. Returns empty DataFrames for both `main` and `reject` outputs. Stats are set to (0, 0, 0). Warning logged with component ID prefix.

**Subtle issue**: When `input_data` is an empty DataFrame (has columns but no rows), the returned `pd.DataFrame()` has NO columns. This means downstream components receiving the output will see a DataFrame with no columns instead of one with the expected schema columns. Talend's behavior would be to output a DataFrame with the correct schema columns but zero rows. This can cause `KeyError` in downstream components that try to access expected columns.

**Fix**: Replace `pd.DataFrame()` with `pd.DataFrame(columns=[col['name'] for col in schema])` when schema is available.

### Lines 134-160: Config Extraction and Column Classification

```python
rows_in = len(input_data)
logger.info(f"[{self.id}] Processing started: {rows_in} rows")

field = self.config.get('field', '')
field_separator = self.config.get('field_separator', self.DEFAULT_FIELD_SEPARATOR)
ignore_source_null = self.config.get('ignore_source_null', True)
die_on_error = self.config.get('die_on_error', False)
advanced_separator = self.config.get('advanced_separator', False)
thousands_separator = self.config.get('thousands_separator', self.DEFAULT_THOUSANDS_SEPARATOR)
decimal_separator = self.config.get('decimal_separator', self.DEFAULT_DECIMAL_SEPARATOR)
trim = self.config.get('trim', False)
check_fields_num = self.config.get('check_fields_num', False)
check_date = self.config.get('check_date', False)
schema = self.output_schema or self.config.get('schema', [])

# Debug logging
logger.debug(f"[ExtractDelimitedFields] schema: {schema}")
logger.debug(f"[ExtractDelimitedFields] config field: {field}, field_separator: {field_separator}")

# Remove quotes from field_separator if present
if field_separator.startswith('"') and field_separator.endswith('"'):
    field_separator = field_separator[1:-1]

# Make output_columns and extracted_columns case-insensitive
output_columns = [col['name'] for col in schema if col['name'].lower() != field.lower()]
extracted_columns = [col for col in output_columns if col.lower().startswith(field.lower())]
```

**Assessment -- Config extraction** (lines 137-148):
- `field` defaults to `''` -- this means a missing `field` config silently uses empty string, which will match column names starting with empty string (i.e., everything). This is a bug pathway.
- `ignore_source_null` defaults to `True` -- matches the Talend "Ignore NULL as source data" checkbox being checked. Correct.
- `die_on_error` defaults to `False` -- **does NOT match Talend default of `true`**. This is a critical behavioral mismatch.
- `schema` uses `self.output_schema` as primary source, falling back to `self.config.get('schema', [])`. This is correct -- output_schema comes from the engine's schema resolution which is more reliable than raw config.

**Assessment -- Quote stripping** (lines 154-155):
- Only handles double quotes. Does not handle single quotes, XML entities (`&quot;`), or escaped quotes.
- If `field_separator` is a single quote character, this check incorrectly fails (length must be > 1 for startswith/endswith to both match).

**Assessment -- Column classification** (lines 157-158):
- `output_columns`: All schema columns except the source field itself. Case-insensitive comparison.
- `extracted_columns`: Subset of output_columns that start with the source field name. This is the set of columns that Tier 2 matching will try to populate.

**Subtle issue**: The `extracted_columns` classification is used by `check_fields_num` (line 187) to determine expected field count. But this classification is based on name matching, not on Talend's schema position. If the output schema has 3 extracted columns that do NOT follow the `{field}{N}` naming convention, `extracted_columns` will be empty, and `check_fields_num` will check `len(fields) != 0`, which is always true for non-empty source values. This means field count checking is effectively disabled for non-standard column names.

### Lines 162-165: Loop Initialization

```python
main_rows = []
reject_rows = []

for idx, row in input_data.iterrows():
```

**Assessment**: `iterrows()` is the slowest way to iterate over a pandas DataFrame. According to the pandas documentation: "Iterating over a DataFrame rows is generally slow. In many cases, iterating over the rows manually is not needed and can be avoided." The pandas documentation recommends using vectorized operations or `apply()` instead.

Performance comparison for 1M rows (approximate):
- `iterrows()`: ~60-120 seconds (current implementation)
- `apply()`: ~30-60 seconds
- Vectorized `str.split(expand=True)`: ~0.5-2 seconds

### Lines 166-175: Per-Row Field Lookup and Null Handling

```python
try:
    # Case-insensitive field lookup
    field_lookup = {str(k).lower(): k for k in row.index}
    actual_field = field_lookup.get(field.lower(), field)
    value = row.get(actual_field, None)
    if value is None:
        if ignore_source_null:
            continue
        else:
            raise ValueError("Source field is null")
```

**Assessment**:
- Line 168: `field_lookup` dict is rebuilt for EVERY row. Since `row.index` is the same for all rows in a DataFrame, this is wasteful. Should be built once outside the loop.
- Line 169: `actual_field` resolves the case-insensitive field name to the actual column name. Correct.
- Line 170: `row.get(actual_field, None)` retrieves the value. Returns `None` if the field does not exist in the row (should not happen after lookup, but defensive).
- Lines 171-175: Null handling. `continue` skips the row when `ignore_source_null=True`. But `value` is checked against `None`, not `pd.isna()`. This means NaN values (which pandas uses for missing data) will NOT be caught as null. `str(NaN)` becomes `"nan"`, which will be split by the delimiter. This is a subtle bug: pandas NaN is not Python None, so the null check fails.

**Fix for NaN detection**:
```python
if value is None or (isinstance(value, float) and pd.isna(value)):
```
Or more robustly:
```python
if pd.isna(value):
```

### Lines 177-193: Splitting, Trimming, Advanced Separator, and Validation

```python
# Split using the field separator
fields = str(value).split(field_separator)
if trim:
    fields = [f.strip() for f in fields]

# Advanced separator handling (for numbers)
if advanced_separator:
    fields = [f.replace(thousands_separator, '').replace(decimal_separator, '.') for f in fields]

# Check number of fields
if check_fields_num and len(fields) != len(extracted_columns):
    raise ValueError(f"Field count mismatch: expected {len(extracted_columns)}, got {len(fields)}")

# Optionally check date fields (not implemented in detail)
if check_date:
    pass
```

**Assessment -- Splitting** (line 178):
- `str(value)` converts any value to string before splitting. This handles numeric values correctly but also means `True` becomes `"True"`, `None` becomes `"None"` (but None should be caught earlier), and `NaN` becomes `"nan"`.
- `.split(field_separator)` is Python string split, NOT regex split. This means:
  - `|` is treated as a literal pipe character (correct for common case)
  - `[;,]` is treated as a literal 4-character string (incorrect for regex)
  - `\t` is treated as literal backslash-t, not as tab (incorrect)
  - Tab character must be an actual `\t` character in the config, not the escaped string `"\\t"`

**Assessment -- Trim** (lines 179-180):
- `[f.strip() for f in fields]` correctly strips leading and trailing whitespace from each extracted token.
- This is a list comprehension that creates a new list. For performance, `fields = list(map(str.strip, fields))` would be marginally faster but functionally identical.

**Assessment -- Advanced separator** (lines 183-184):
- Replaces thousands separator with empty string and decimal separator with `.` in ALL fields, regardless of type.
- **Bug**: If a field contains the thousands separator character as part of non-numeric data (e.g., an address like "123 Main St, Suite 456"), the comma would be stripped, producing "123 Main St Suite 456".
- **Bug**: If the decimal separator is the same as the field separator (unusual but possible), the field was already split by it, so this replacement would never find it.

**Assessment -- Field count check** (lines 187-188):
- Compares `len(fields)` (actual tokens) to `len(extracted_columns)` (columns matching name pattern).
- As discussed in the column classification section, `extracted_columns` may be empty for non-standard column names, making this check effectively disabled.

**Assessment -- Date check** (lines 192-193):
- Empty `pass` statement. This is a documented stub with no implementation. Jobs relying on strict date validation will silently pass invalid dates through to the output.
- To implement properly, would need to: (a) identify which extracted columns are date-typed from the schema, (b) parse each value against the date pattern, (c) raise `ValueError` for invalid dates. The schema provides `date_pattern` from the converter if a pattern was specified in Talend.

### Lines 195-230: Output Row Construction (Four-Tier Matching)

This is the most complex and fragile part of the component. For each output schema column, four matching tiers are tried in order:

**Tier 1 -- Exact source field match** (lines 197-199):
```python
if col.lower() == field.lower():
    output_row[col] = value
```
Purpose: Preserve the original unsplit value for the source field column. This happens when the output schema includes the source field itself (e.g., the schema has `product` and the source field is `product`).

Correctness: Correct. Talend preserves the original value in the source field column.

**Tier 2 -- Direct prefix match with numeric suffix** (lines 200-211):
```python
elif col.lower().startswith(field.lower()):
    idx_split = col[len(field):]
    idx_val = None
    try:
        idx_val = int(idx_split) - 1 if idx_split.isdigit() else None
    except Exception:
        pass
    if idx_val is not None and idx_val >= 0 and idx_val < len(fields):
        output_row[col] = fields[idx_val]
    else:
        output_row[col] = None
```
Purpose: Match columns like `product1`, `product2`, `product3` when source field is `product`.

**Bug -- False positives**: `startswith` is too broad. Examples of false positives:
- Source field `name` matches `namespace` (Tier 2: `idx_split="space"`, not a digit, so `idx_val=None`, column gets `None`)
- Source field `id` matches `identity` (Tier 2: `idx_split="entity"`, not a digit, so `idx_val=None`, column gets `None`)
- Source field `col` matches `color` (Tier 2: `idx_split="or"`, not a digit, so `idx_val=None`, column gets `None`)

In all these cases, the column is intended as a passthrough but gets `None` instead. The column never reaches Tier 4 (passthrough) because the `elif` chain short-circuits.

**Bug -- Case sensitivity in idx_split**: `idx_split = col[len(field):]` uses the original `col` name length but `field`'s length. If `field="Product"` and `col="product1"`, then `len(field)=7` and `col[7:]="1"` -- correct. But if `field="product"` and `col="Product1"`, then `col[7:]="1"` -- also correct. The case-insensitive check is only on `startswith`, and `len(field)` is used for slicing which works because `startswith` already confirmed the prefix length matches.

**Tier 3 -- Flexible singular/plural match** (lines 212-225):
```python
elif field.lower().startswith(col.lower().rstrip('0123456789')):
    base_col = col.lower().rstrip('0123456789')
    if len(col) > len(base_col):
        try:
            idx_val = int(col[len(base_col):]) - 1
            if idx_val >= 0 and idx_val < len(fields):
                output_row[col] = fields[idx_val]
            else:
                output_row[col] = None
        except (ValueError, IndexError):
            output_row[col] = None
    else:
        output_row[col] = None
```
Purpose: Handle singular/plural variations where the source field name is a variation of the column base name. E.g., source field `skills` with columns `skill1`, `skill2`, `skill3`.

**How it works**:
1. Strip trailing digits from column name: `skill1` -> `skill`
2. Check if source field starts with the stripped name: `"skills".startswith("skill")` -> true
3. Parse the stripped digits as a 1-based index: `1` -> index 0
4. Extract from split tokens: `fields[0]`

**Problems**:
- `rstrip('0123456789')` strips ALL trailing digits: `field100` becomes `field`, `item2b` stays `item2b`.
- The check `field.lower().startswith(base_col)` is broad. If base_col is empty (all digits stripped), it always matches. E.g., column `123` has base_col `""` (empty string), and any field name starts with empty string.
- If `len(col) == len(base_col)`, the column has no trailing digits, so no index can be extracted. Gets `None`.
- The `try/except (ValueError, IndexError)` catches integer parse failures, but `IndexError` is never actually raised here (only `ValueError` from `int()` would be relevant).

**Tier 4 -- Passthrough** (lines 226-229):
```python
else:
    col_lookup = {str(k).lower(): k for k in row.index}
    output_row[col] = row.get(col_lookup.get(col.lower(), col), None)
```
Purpose: Copy the value from the input row for columns that are not the source field and not extracted columns.

**Performance issue**: `col_lookup` is rebuilt for every passthrough column in every row. This is the same dict as `field_lookup` (line 168) but constructed independently. For N rows and M passthrough columns, this is O(N * M) unnecessary dict constructions.

**Correctness**: The case-insensitive lookup is correct. `col_lookup.get(col.lower(), col)` falls back to the original column name if no case-insensitive match is found, then `row.get(..., None)` returns None if the column does not exist. This correctly handles the case where output schema has columns not present in the input.

### Lines 237-270: DataFrame Construction, Schema Validation, and Return

```python
# Build DataFrames
if schema:
    schema_cols = [col['name'] for col in schema]
    main_df = pd.DataFrame(main_rows, columns=schema_cols)
else:
    main_df = pd.DataFrame(main_rows)
reject_df = pd.DataFrame(reject_rows) if reject_rows else pd.DataFrame(columns=input_data.columns)

# Debug logging
logger.debug(f"[ExtractDelimitedFields] main_df shape: {main_df.shape}")
logger.debug(f"[ExtractDelimitedFields] main_df columns: {list(main_df.columns)}")
logger.debug(f"[ExtractDelimitedFields] main_df head:\n{main_df.head()}\nValues:\n{main_df.values}")

# Stats
rows_out = len(main_df)
rows_rejected = len(reject_df)
self._update_stats(rows_in, rows_out, rows_rejected)

logger.info(f"[{self.id}] Processing complete: "
             f"in={rows_in}, out={rows_out}, rejected={rows_rejected}")

# Schema validation
if schema:
    main_df = self.validate_schema(main_df, schema)
    schema_cols = [col['name'] for col in schema]
    for col in schema_cols:
        if col not in main_df.columns:
            main_df[col] = None
    main_df = main_df[schema_cols]

return {'main': main_df, 'reject': reject_df}
```

**Assessment -- DataFrame construction** (lines 238-243):
- `pd.DataFrame(main_rows, columns=schema_cols)`: Creates DataFrame from list of dicts. When a dict is missing a key, the value becomes NaN. The `columns=schema_cols` parameter enforces column order and presence.
- `pd.DataFrame(reject_rows)`: Creates DataFrame from list of pandas Series (original rows). The columns come from the Series index, which is the input DataFrame's columns. This is correct -- reject rows have input columns, not output columns.
- When `reject_rows` is empty, creates a DataFrame with input columns but no rows. Correct.

**Assessment -- Debug logging** (lines 246-248):
- Line 248 is extremely problematic: `f"...{main_df.head()}\nValues:\n{main_df.values}"` evaluates even when DEBUG logging is disabled because f-strings are always evaluated in Python. `main_df.values` creates a full numpy array copy of the entire DataFrame. For a 1M-row, 10-column DataFrame of strings, this could allocate 100MB+ of memory just for a log message that will never be written.

**Assessment -- Stats** (lines 251-255):
- `self._update_stats(rows_in, rows_out, rows_rejected)`: Correctly updates all three stat counters.
- Note that `rows_in` is `len(input_data)` (all input rows), but `rows_out + rows_rejected` may not equal `rows_in` because rows skipped by `ignore_source_null` are counted in `rows_in` but not in either `rows_out` or `rows_rejected`. This means `NB_LINE > NB_LINE_OK + NB_LINE_REJECT` when null rows are skipped.

**Assessment -- Schema validation** (lines 262-269):
- `validate_schema()` calls `BaseComponent.validate_schema()` which converts column types according to the schema. This is called AFTER stats are updated, so rows dropped or modified by type conversion are not reflected in the stats.
- Lines 266-268: Ensure all schema columns exist in the output. Missing columns get `None`.
- Line 269: `main_df = main_df[schema_cols]` reorders columns to match schema order. This is important for Talend compatibility where column order matters.

---

## Appendix I: Converter Code Flow Detailed Analysis

### Step 1: `converter.py` calls `parse_base_component(node)` (line 226)

This is the entry point for ALL components. For `tExtractDelimitedFields`, the flow is:

1. **Component identification** (lines 390-404): Extract `componentName` = `"tExtractDelimitedFields"` and `unique_name` from the XML node.

2. **Type mapping** (line 404): `self.component_mapping.get('tExtractDelimitedFields')` returns `'ExtractDelimitedFields'` (from line 69 of component_parser.py).

3. **Component dict initialization** (lines 406-418): Creates the base structure:
   ```python
   component = {
       'id': unique_name,
       'type': 'ExtractDelimitedFields',
       'original_type': 'tExtractDelimitedFields',
       'position': {'x': ..., 'y': ...},
       'config': {},
       'schema': {'input': [], 'output': []},
       'inputs': [],
       'outputs': []
   }
   ```

4. **Dedicated parser check** (lines 421-430): `tExtractDelimitedFields` is NOT in `components_with_dedicated_parsers` (which only contains `tFileInputExcel` and `tMap`). So the generic path executes.

5. **Raw parameter extraction** (lines 433-458): Iterates all `<elementParameter>` nodes in the XML. For each:
   - Strips surrounding quotes from values
   - Converts CHECK fields to Python booleans
   - Detects and wraps context variable references
   - Builds `config_raw` dict

6. **Java expression marking** (lines 462-469): Scans `config_raw` for Java expression patterns. Any value containing Java operators, method calls, etc. gets prefixed with `{{java}}`.

7. **Parameter mapping** (line 472): Calls `_map_component_parameters('tExtractDelimitedFields', config_raw)`. This returns the mapped config dict for the specific component type.

8. **Schema extraction** (lines 474-507): Iterates `<metadata>` nodes. For each column, extracts name, type, nullable, key, length, precision, and date pattern. Converts Java date patterns to Python strftime format. Assigns to `component['schema']['output']` (FLOW) or `component['schema']['reject']` (REJECT).

### Step 2: `converter.py` calls `parse_textract_delimited_fields(node, component)` (line 322)

After `parse_base_component()` returns, `converter.py` checks the component type and dispatches to the dedicated parser. The dedicated parser receives the `component` dict which already has config populated from Step 1.

The dedicated parser then **overwrites** some config keys:
- `field_separator` -- overwritten with raw XML value (no quote stripping)
- `row_separator` -- **added** (not in generic mapper, and irrelevant to this component)
- `advanced_separator` -- overwritten with string-based boolean parsing
- `thousands_separator` -- overwritten
- `decimal_separator` -- overwritten
- `trim_all` -- **added** (different key than engine's `trim`)
- `remove_empty_row` -- **added** (irrelevant to this component)
- `die_on_error` -- overwritten with string-based boolean parsing

**Keys NOT overwritten by dedicated parser** (persist from generic mapper):
- `field` -- source field to split
- `ignore_source_null`
- `trim` -- engine reads this, not `trim_all`
- `check_fields_num`
- `check_date`
- `schema_opt_num`
- `connection_format`

This means the final config is a HYBRID of both parsers, with different keys coming from different sources with different processing logic.

### Impact Analysis of Dual-Parser Conflict

**Scenario 1: Talend job with `FIELDSEPARATOR=","` (comma, quoted in XML)**

1. Generic mapper: `config_raw.get('FIELDSEPARATOR', ';')` gets `","` (quotes already stripped by line 441-442 of parse_base_component). Wait -- line 441-442 strips quotes if the value starts AND ends with `"`. For `","`, this IS true: starts with `"`, ends with `"`. So `config_raw['FIELDSEPARATOR']` = `,`. Then line 296-300: `sep = ','`, `sep.strip()` = `,`, does not start with `"` or `&quot;`, so no further stripping. Generic mapper produces `field_separator=","`.

2. Dedicated parser: `get_param('FIELDSEPARATOR', ';')` reads the RAW XML value attribute. If the XML is `value="&quot;,&quot;"`, then `elem.get('value')` returns `","` (XML entity already decoded by ElementTree). So dedicated parser produces `field_separator=","`.

In this scenario, both parsers produce the same result. The dedicated parser's last-write wins, but the value is identical.

**Scenario 2: Talend job with `ADVANCED_SEPARATOR=true`**

1. Generic mapper: Line 446 of parse_base_component converts CHECK field to boolean: `value = 'true'.lower() == 'true'` = `True` (Python boolean). So `config_raw['ADVANCED_SEPARATOR'] = True`. Line 306: `config_raw.get('ADVANCED_SEPARATOR', False)` = `True`.

2. Dedicated parser: `get_param('ADVANCED_SEPARATOR', 'false')` returns `"true"` (raw XML string). `.lower() == 'true'` = `True`.

Both produce `True`. But if the generic mapper's boolean `True` were somehow passed to the dedicated parser instead of the raw XML value, `.lower()` would fail on a boolean (`AttributeError: 'bool' object has no attribute 'lower'`). The dedicated parser's `get_param()` reads from XML, not from `config`, so this scenario does not occur. But it illustrates the fragility of the dual-parser design.

**Scenario 3: Talend job with `DIE_ON_ERROR` not explicitly set (using Talend default)**

1. Talend default: `true` (checked). The Talend XML would have `value="true"` for the elementParameter.
2. Generic mapper: CHECK field converts to `True`. `config_raw.get('DIE_ON_ERROR', False)` = `True`.
3. Dedicated parser: `get_param('DIE_ON_ERROR', 'false')` reads raw XML value `"true"`. `.lower() == 'true'` = `True`.

Both produce `True`. But if the elementParameter is ABSENT from the XML (Talend sometimes omits default values), then:
1. Generic mapper: `config_raw.get('DIE_ON_ERROR', False)` = `False` (Python default).
2. Dedicated parser: `get_param('DIE_ON_ERROR', 'false')` = `'false'`. `.lower() == 'true'` = `False`.

Both produce `False`, but Talend's runtime default is `True`. **This is a default mismatch** -- the converter should default to `True` to match Talend behavior.

---

## Appendix J: Comparison with Related Components

### ExtractDelimitedFields vs ExtractJSONFields

| Aspect | ExtractDelimitedFields | ExtractJSONFields |
|--------|----------------------|-------------------|
| Source field type | Delimited string | JSON string |
| Extraction method | String split by delimiter | JSON path expressions |
| Column mapping | Name-based (3-tier) | JSON path-based |
| Performance | `iterrows()` loop | Likely similar (not audited) |
| Regex support | No | N/A |
| REJECT flow | Partial (no errorCode) | Unknown |
| Converter parser | Dual-parser (bug) | Dedicated only |

### ExtractDelimitedFields vs tFileInputDelimited (file reading)

| Aspect | ExtractDelimitedFields | FileInputDelimited |
|--------|----------------------|-------------------|
| Input | DataFrame column | File on disk |
| Row handling | Per-row `iterrows()` | `pd.read_csv()` vectorized |
| Performance | O(rows * columns) Python | C-level pandas engine |
| Streaming | Not implemented | Chunked reading available |
| REJECT flow | Partial | Not implemented |
| Code maturity | 272 lines, simpler | 575 lines, more robust |
| Tests | Zero | Zero |

### Shared patterns across Extract* components

All Extract* components (`ExtractDelimitedFields`, `ExtractJSONFields`, `ExtractRegexFields`, `ExtractPositionalFields`, `ExtractXMLField`) share:
1. Input: DataFrame with a source field to extract from
2. Output: DataFrame with extracted columns + passthrough columns
3. Config: `field` (source), `die_on_error`, `trim`
4. Pattern: Per-row processing loop
5. Issue: None have proper REJECT flow with errorCode/errorMessage

A refactoring opportunity exists to create a base `ExtractFieldsBase` class that handles common logic (null checking, error handling, stats, passthrough columns) and delegates the extraction method to subclasses.

---

## Appendix K: Talend Generated Java Code Reference

For reference, Talend's generated Java code for `tExtractDelimitedFields` follows this pattern:

```java
// Simplified Talend-generated code for tExtractDelimitedFields
String[] fields = source_value.split(fieldSeparator);
if (checkFieldsNum && fields.length != expectedFieldCount) {
    // Route to REJECT
    reject_row.errorCode = "FIELD_COUNT_MISMATCH";
    reject_row.errorMessage = "Expected " + expectedFieldCount + " fields, got " + fields.length;
    // ... send to reject flow
} else {
    // Index-based assignment to output columns
    output_row.field1 = fields.length > 0 ? fields[0] : null;
    output_row.field2 = fields.length > 1 ? fields[1] : null;
    output_row.field3 = fields.length > 2 ? fields[2] : null;
    // ... copy passthrough columns
    output_row.id = input_row.id;
    output_row.name = input_row.name;
}
```

Key observations from the Talend-generated Java:
1. **Index-based, not name-based**: `fields[0]`, `fields[1]`, `fields[2]` -- pure positional mapping regardless of output column names.
2. **Null-safe extraction**: `fields.length > N ? fields[N] : null` -- handles fewer tokens than columns gracefully.
3. **REJECT with error details**: Explicitly sets `errorCode` and `errorMessage` on the reject row.
4. **Passthrough is explicit copy**: `output_row.id = input_row.id` -- no name matching or lookup needed; the schema defines which columns are passthrough.

The v1 engine's approach of name-based matching with three tiers is a departure from this straightforward index-based approach. A closer match to Talend's behavior would be:

```python
# Determine extracted vs passthrough columns by comparing with input columns
input_col_names = set(c.lower() for c in input_data.columns)
extracted_cols = []
passthrough_cols = []
for col_def in schema:
    col_name = col_def['name']
    if col_name.lower() == field.lower():
        passthrough_cols.append(col_name)  # Source field preserved
    elif col_name.lower() in input_col_names:
        passthrough_cols.append(col_name)  # Exists in input -> passthrough
    else:
        extracted_cols.append(col_name)  # New column -> extracted by position
```

This approach uses the presence/absence of a column in the input DataFrame to determine whether it is a passthrough or extracted column. It is simpler, faster, and matches Talend's position-based semantics.

---

## Appendix L: Recommended Vectorized Implementation

Below is a complete vectorized implementation that addresses the P0 performance issue and the P1 column-mapping issue:

```python
def _process_vectorized(self, input_data: pd.DataFrame) -> Dict[str, Any]:
    """Vectorized implementation of field extraction."""
    field = self.config.get('field', '')
    field_separator = self.config.get('field_separator', self.DEFAULT_FIELD_SEPARATOR)
    ignore_source_null = self.config.get('ignore_source_null', True)
    die_on_error = self.config.get('die_on_error', False)
    trim = self.config.get('trim', False)
    check_fields_num = self.config.get('check_fields_num', False)
    schema = self.output_schema or self.config.get('schema', [])

    rows_in = len(input_data)

    # Resolve case-insensitive field name
    field_col = None
    for col in input_data.columns:
        if col.lower() == field.lower():
            field_col = col
            break
    if field_col is None:
        raise ValueError(f"Source field '{field}' not found in input columns")

    # Classify output columns: passthrough vs extracted
    input_cols_lower = {c.lower(): c for c in input_data.columns}
    schema_cols = [col_def['name'] for col_def in schema]
    passthrough_cols = []
    extracted_cols = []
    for col_name in schema_cols:
        if col_name.lower() == field.lower():
            passthrough_cols.append((col_name, field_col))  # Source field
        elif col_name.lower() in input_cols_lower:
            passthrough_cols.append((col_name, input_cols_lower[col_name.lower()]))
        else:
            extracted_cols.append(col_name)

    # Handle null source values
    null_mask = input_data[field_col].isna()
    if ignore_source_null:
        work_data = input_data[~null_mask]
    else:
        # For non-null-ignoring mode, fill nulls with empty string
        work_data = input_data.copy()
        work_data[field_col] = work_data[field_col].fillna('')

    # Split the source field (vectorized)
    split_result = work_data[field_col].astype(str).str.split(
        field_separator, expand=True
    )

    if trim:
        split_result = split_result.apply(lambda col: col.str.strip())

    # Build output DataFrame
    result = pd.DataFrame(index=work_data.index)

    # Copy passthrough columns
    for out_name, in_name in passthrough_cols:
        result[out_name] = work_data[in_name]

    # Assign extracted columns by position
    for i, col_name in enumerate(extracted_cols):
        if i < split_result.shape[1]:
            result[col_name] = split_result.iloc[:, i]
        else:
            result[col_name] = None

    # Ensure schema column order
    result = result.reindex(columns=schema_cols)

    # Check field count (vectorized)
    reject_mask = pd.Series(False, index=work_data.index)
    if check_fields_num:
        actual_counts = split_result.notna().sum(axis=1)
        expected = len(extracted_cols)
        reject_mask = actual_counts != expected

    main_df = result[~reject_mask].reset_index(drop=True)
    reject_df = pd.DataFrame()
    if reject_mask.any():
        reject_df = input_data.loc[reject_mask.index[reject_mask]]

    rows_out = len(main_df)
    rows_rejected = len(reject_df)
    self._update_stats(rows_in, rows_out, rows_rejected)

    return {'main': main_df, 'reject': reject_df}
```

**Benefits of this implementation**:
1. **Performance**: `str.split(expand=True)` operates at C speed via pandas. 100-1000x faster than `iterrows()`.
2. **Correctness**: Position-based extraction matches Talend behavior. No name-matching heuristics.
3. **Null handling**: Uses `pd.isna()` which correctly detects NaN, None, and pd.NA.
4. **Field count checking**: Vectorized via `notna().sum(axis=1)`.
5. **Memory**: No intermediate list-of-dicts. DataFrame operations are in-place or view-based.

**Limitations**:
- Does not support advanced separator (would need additional vectorized string operations).
- Does not support check_date (would need per-column date validation).
- Does not add errorCode/errorMessage to reject rows (would need additional columns).

---

## Appendix M: Risk Assessment for Production Deployment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Incorrect extraction due to name-based matching | **High** | **High** | Any job with non-`{field}{N}` column names will produce wrong results. Immediate fix needed. |
| Performance degradation on large datasets | **High** | **High** | 1M+ row datasets will take minutes instead of seconds. Vectorization needed for production. |
| Silent data corruption from Tier 2 false positives | **Medium** | **High** | Passthrough columns starting with source field name get `None`. Hard to detect because output has correct schema shape. |
| `die_on_error` default mismatch | **Medium** | **Medium** | Jobs omitting explicit `die_on_error` will silently continue on errors instead of stopping. May produce corrupt output. |
| Advanced separator corrupting non-numeric fields | **Medium** | **Medium** | Fields containing comma characters will have them stripped when advanced_separator is enabled. |
| NaN not detected as null | **Medium** | **Medium** | pandas NaN values in source field will be converted to string `"nan"` and split, producing garbage output. |
| GlobalMap crash on `_update_global_map()` | **Certain** | **Medium** | Every execution with globalMap enabled will crash. Must be fixed first. |
| Memory explosion from DEBUG logging | **Low** | **High** | Only occurs if DEBUG logging is enabled in production. Line 248 materializes entire DataFrame. |

### Go/No-Go Assessment

| Criterion | Status | Blocking? |
|-----------|--------|-----------|
| Core extraction works for simple cases | Pass | -- |
| Core extraction works for all valid Talend schemas | **Fail** | **Yes** -- name-based matching breaks for non-standard column names |
| Performance acceptable for production datasets | **Fail** | **Yes** -- `iterrows()` is 100x too slow for > 100K rows |
| Cross-cutting bugs fixed | **Fail** | **Yes** -- `_update_global_map()` and `GlobalMap.get()` crash |
| REJECT flow complete | **Fail** | No -- can work without REJECT for jobs that do not use it |
| Tests exist | **Fail** | **Yes** -- zero tests means zero confidence |
| Converter produces correct config | **Partial** | No -- dual-parser is fragile but produces correct values in common cases |

**Verdict**: **Not ready for production**. Four blocking criteria fail. Minimum required before production:
1. Fix cross-cutting GlobalMap bugs (BUG-EDF-001, BUG-EDF-002)
2. Replace name-based matching with position-based matching (ENG-EDF-002)
3. Replace `iterrows()` with vectorized extraction (PERF-EDF-001)
4. Create basic unit test suite (TEST-EDF-001)

---

## Appendix N: NaN vs None Detection Deep Dive

A subtle but important issue in the null handling logic:

```python
value = row.get(actual_field, None)
if value is None:
    if ignore_source_null:
        continue
    else:
        raise ValueError("Source field is null")
```

In pandas, missing values are represented as `float('nan')` (NaN), NOT as Python `None`. When you access a value from a pandas Series via `row.get()`:

- If the cell contains `None` (explicitly set), pandas stores it as `NaN` (for numeric columns) or `None` (for object columns).
- If the cell is empty/missing, pandas stores it as `NaN` (float).
- `NaN is None` evaluates to `False`.
- `NaN == None` evaluates to `False`.
- `NaN == NaN` evaluates to `False` (IEEE 754 standard).

So the check `if value is None` will ONLY catch values that are actual Python `None` objects in object-typed columns. It will NOT catch:
- `float('nan')` -- the standard pandas missing value
- `pd.NA` -- the nullable integer/boolean missing value
- `np.nan` -- numpy's NaN

**Consequence**: When the source field column contains NaN (the most common "null" in pandas), the check fails, `value` is `NaN`, and the code proceeds to `str(NaN).split(separator)` which produces `["nan"]`. The first extracted column gets the literal string `"nan"` instead of `None`. This is a data corruption bug.

**Fix**: Replace `if value is None:` with `if pd.isna(value):` which correctly detects NaN, None, pd.NA, and np.nan.

**Test case to verify**:
```python
import pandas as pd
df = pd.DataFrame({'data': ['a,b,c', None, 'x,y,z', float('nan')]})
# Current behavior: rows 1 and 3 produce ["None"] and ["nan"] respectively
# Expected: rows 1 and 3 should be treated as null source values
```
