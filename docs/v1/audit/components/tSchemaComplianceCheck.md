# Audit Report: tSchemaComplianceCheck / SchemaComplianceCheck

## Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tSchemaComplianceCheck` |
| **V1 Engine Class** | `SchemaComplianceCheck` |
| **Engine File** | `src/v1/engine/components/transform/schema_compliance_check.py` |
| **Converter Parser** | `component_parser.py` -> `parse_tschema_compliance_check()` (line ~2080) |
| **Converter Dispatch** | `converter.py` -> `_parse_component()` (line ~333) |
| **Registry Aliases** | `SchemaComplianceCheck`, `tSchemaComplianceCheck` |
| **Category** | Transform / Validation (Data Quality) |
| **Complexity** | Medium -- schema-driven row-level validation with reject flow |

---

## Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 |
|-----------|-------|----|----|----|----|
| Converter Coverage | Y | 1 | 2 | 2 | 1 |
| Engine Feature Parity | R | 2 | 4 | 3 | 1 |
| Code Quality | Y | 1 | 2 | 3 | 2 |
| Performance & Memory | R | 1 | 1 | 1 | 0 |
| Testing | R | 1 | 0 | 0 | 0 |

**Score Key**: G = Green (production-ready), Y = Yellow (usable with caveats), R = Red (not production-ready)

**Priority Definitions**:
- **P0**: Critical -- blocks production use or causes data corruption
- **P1**: Major -- significant functional gap or behavioral divergence
- **P2**: Moderate -- missing feature or code quality concern
- **P3**: Low -- minor improvement or cosmetic issue

---

## 1. Talend Feature Baseline

### What tSchemaComplianceCheck Does in Talend

tSchemaComplianceCheck is a data quality validation component belonging to the **Data Quality** family. It acts as an intermediary step in a data flow, validating all input rows against a reference schema by checking data types, nullability constraints, and field length limits. Non-compliant rows are routed to a REJECT output flow with supplementary `errorCode` and `errorMessage` columns for downstream error handling.

The component is **not included in Talend Studio by default** and requires installation via the Feature Manager, indicating it is a specialized data quality tool rather than a general-purpose component.

### Basic Settings (Talend Studio)

| Parameter | Talend Name | Type | Default | Description |
|-----------|-------------|------|---------|-------------|
| Base Schema | `SCHEMA` | Schema editor | Built-In | Reference schema defining column names, types, lengths, nullability |
| Schema Source | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether schema comes from local definition or metadata repository |
| Mode | `MODE` | Radio | Check All | Validation mode: "Check all columns from schema" or "Custom defined" |
| Check All Columns | `CHECK_ALL` | Boolean | true | Perform type, nullability, and length checks on all columns against the base schema |
| Custom Defined | — | Boolean | false | Enable selective checking via Checked Columns table |
| Checked Columns | `CHECKED_COLUMNS` | Table | — | Per-column validation rules (Column, Type, Date Pattern, Nullable, Max Length) |
| Use Another Schema | — | Boolean | false | Define a separate reference schema for compliance comparison |
| Trim Excess Content | `SUB_STRING` | Boolean | false | Truncate data exceeding defined length instead of rejecting (String type only) |

#### Checked Columns Table Parameters

When Mode is "Custom defined", each row in the Checked Columns table specifies:

| Column | Type | Description |
|--------|------|-------------|
| Column | String | Column name from the schema to validate |
| Type | Enum | Data type check (mandatory for all columns in custom mode) |
| Date Pattern | String | Expected date format pattern (e.g., `dd-MM-yyyy`) for Date columns |
| Nullable | Boolean | Whether the column allows null/empty values |
| Max Length | Boolean | Whether to enforce the schema-defined length constraint |

### Advanced Settings (Talend Studio)

| Parameter | Talend Name | Type | Default | Description |
|-----------|-------------|------|---------|-------------|
| Fastest Date Check | `FASTEST_DATE_CHECK` | Boolean | false | Use `TalendDate.isDate()` for fast date validation when no pattern defined |
| Strict Date Check | `STRICT_DATE_CHECK` | Boolean | false | Enable strict format validation (hides Fastest Date Check when enabled) |
| Ignore TimeZone | `IGNORE_TIMEZONE` | Boolean | false | Disregard timezone during date validation (unavailable in "Check all" mode) |
| Treat Empty as NULL | `ALL_EMPTY_ARE_NULL` | Boolean | true | Treat empty string fields as null values instead of empty strings |
| Choose Columns | — | Table | — | Per-column empty-as-null selection (appears when Treat Empty as NULL is unchecked) |
| Check String by Byte Length | `CHECK_BYTE_LENGTH` | Boolean | false | Validate string length using byte count per charset setting |
| Charset | `CHARSET` | String | Default | Character encoding for byte-length checking |
| tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean | false | Collect component-level log data |

### Connection Types

| Connector | Type | Direction | Description |
|-----------|------|-----------|-------------|
| `FLOW` (Main) | Row | Input | Incoming data rows to validate |
| `FLOW` (Main) | Row | Output | Compliant rows that pass all schema checks |
| `REJECTS` | Row | Output | Non-compliant rows with `errorCode` and `errorMessage` columns appended |

### GlobalMap Variables Produced (Talend)

| Key | Type | Description |
|-----|------|-------------|
| `{id}_NB_LINE` | int | Total rows processed (input) |
| `{id}_NB_LINE_OK` | int | Rows that passed validation (sent to FLOW output) |
| `{id}_NB_LINE_REJECT` | int | Rows that failed validation (sent to REJECTS output) |
| `{id}_ERROR_MESSAGE` | String | Error message from the component when an error occurs (After scope, requires Die on error unchecked) |

### Talend Behavioral Notes

1. **Validation Hierarchy**: The component validates in this order: (1) Nullability check, (2) Type check, (3) Length check. A row is rejected on the first violation found for any column.
2. **REJECT Flow Structure**: Rejected rows include ALL original columns plus two read-only supplementary columns: `errorCode` (integer) and `errorMessage` (string describing the violation).
3. **Error Code**: Talend uses a specific error code to identify schema compliance violations. The error code is typically an integer value associated with the type of violation.
4. **Empty String Handling**: By default (`ALL_EMPTY_ARE_NULL=true`), empty strings are treated as NULL. This means a non-nullable column receiving an empty string will be rejected.
5. **SUB_STRING (Trim) Behavior**: When enabled, strings exceeding the defined length are silently truncated to fit rather than causing rejection. This applies to String-type columns only.
6. **Date Validation Modes**: Three mutually exclusive modes exist -- no date check (default), fastest date check (uses `TalendDate.isDate()`), and strict date check (exact pattern matching). Strict mode hides the fastest option.
7. **Custom vs. Check All**: In "Check all" mode, every column in the schema is validated for type, nullability, and length. In "Custom defined" mode, only columns listed in the Checked Columns table are validated, and each check type can be selectively enabled or disabled.
8. **Byte Length Checking**: When enabled, string length is measured in bytes using the specified charset, not in characters. This is relevant for multibyte encodings (UTF-8, etc.).
9. **Component Requirement**: tSchemaComplianceCheck requires an input flow and at least one output connector. It cannot be a job start component.
10. **Type Checking Scope**: Talend validates against its full type system including: `id_String`, `id_Integer`, `id_Long`, `id_Float`, `id_Double`, `id_Boolean`, `id_Date`, `id_BigDecimal`, `id_Object`, `id_Character`, `id_Byte`, `id_Short`.

---

## 2. Converter Audit

### Parser Method: `parse_tschema_compliance_check()`

Located in `component_parser.py` at line ~2080. The parser extracts schema from FLOW metadata and four additional parameters.

### Parameters Extracted

| Talend Parameter | Converter Extracts? | V1 Config Key | Notes |
|------------------|---------------------|---------------|-------|
| `SCHEMA` (metadata) | Yes | `schema` | Parsed from `<metadata connector="FLOW">` elements |
| `CHECK_ALL` | Yes | `check_all` | Boolean conversion |
| `SUB_STRING` | Yes | `sub_string` | Boolean conversion |
| `STRICT_DATE_CHECK` | Yes | `strict_date_check` | Boolean conversion |
| `ALL_EMPTY_ARE_NULL` | Yes | `all_empty_are_null` | Boolean conversion |
| `MODE` | No | -- | **Not extracted -- cannot distinguish Check All vs. Custom Defined** |
| `CHECKED_COLUMNS` | No | -- | **Not extracted -- table parameter with per-column validation rules** |
| `FASTEST_DATE_CHECK` | No | -- | **Not extracted** |
| `IGNORE_TIMEZONE` | No | -- | **Not extracted** |
| `CHECK_BYTE_LENGTH` | No | -- | **Not extracted** |
| `CHARSET` | No | -- | **Not extracted** |
| `TSTATCATCHER_STATS` | No | -- | **Not extracted** |
| `PROPERTY_TYPE` | No | -- | Not needed (always Built-In) |

### Schema Extraction

| Attribute | Extracted? | Notes |
|-----------|-----------|-------|
| `name` | Yes | From `column.get('name')` |
| `type` | Yes | **Converted via `ExpressionConverter.convert_type()` -- see CONV-SCC-001** |
| `nullable` | Yes | Boolean conversion from string |
| `length` | Yes | Integer conversion with None default |
| `key` | No | **Not extracted** |
| `precision` | No | **Not extracted** |
| `pattern` | No | **Not extracted -- critical for date validation** |

### Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-SCC-001 | **P0** | **Type conversion mismatch**: The converter calls `self.expr_converter.convert_type(column.get('type', 'id_String'))` which converts Talend types to Python type strings (e.g., `id_Integer` -> `'int'`, `id_String` -> `'str'`). However, the engine's `TALEND_TYPE_MAPPING` expects the original Talend type format (`id_Integer`, `id_String`, etc.). This means every column type will fail lookup in the engine's type mapping dictionary, causing type validation to be silently skipped for all columns. **This renders the entire type validation feature non-functional when using converted jobs.** |
| CONV-SCC-002 | **P1** | **CHECKED_COLUMNS table not extracted**: The per-column validation configuration table from Talend's "Custom defined" mode is not parsed. All column-specific validation rules (selective type check, selective nullable check, selective length check, date patterns) are lost during conversion. Only the "Check all" mode can work, and even then only partially. |
| CONV-SCC-003 | **P1** | **MODE parameter not extracted**: Without knowing whether the job uses "Check all" or "Custom defined" mode, the engine cannot determine which validation behavior to apply. The engine implicitly always behaves as "Check all", which may not match the Talend job's intent. |
| CONV-SCC-004 | **P1** | **Date pattern not extracted from schema**: The `pattern` attribute from column metadata is not parsed. This means date columns cannot be validated against their expected format pattern (e.g., `dd-MM-yyyy`). Since the engine maps `id_Date` to `str`, date validation is effectively non-existent. |
| CONV-SCC-005 | **P2** | **FASTEST_DATE_CHECK and IGNORE_TIMEZONE not extracted**: These advanced date validation parameters are lost, preventing proper date format checking behavior. |
| CONV-SCC-006 | **P2** | **CHECK_BYTE_LENGTH and CHARSET not extracted**: Byte-length string validation is not supported. Jobs relying on byte-length checks for multibyte character sets will silently pass invalid data. |
| CONV-SCC-007 | **P3** | **Schema precision and key attributes not extracted**: The `precision` and `key` column attributes are not parsed, which may be needed for BigDecimal validation or key-based error reporting. |

### Converter Code Excerpt (for reference)

```python
def parse_tschema_compliance_check(self, node, component: Dict) -> Dict:
    """Parse tSchemaComplianceCheck specific configuration"""
    schema = []
    for metadata in node.findall('./metadata'):
        if metadata.get('connector') == 'FLOW':
            for column in metadata.findall('./column'):
                schema.append({
                    'name': column.get('name', ''),
                    'type': self.expr_converter.convert_type(column.get('type', 'id_String')),
                    # ^^^ BUG: converts id_Integer -> 'int', but engine expects 'id_Integer'
                    'nullable': column.get('nullable', 'true').lower() == 'true',
                    'length': int(column.get('length', 0)) if column.get('length') else None
                })
    component['config']['schema'] = schema
    component['config']['check_all'] = ...
    component['config']['sub_string'] = ...
    component['config']['strict_date_check'] = ...
    component['config']['all_empty_are_null'] = ...
    return component
```

---

## 3. Engine Feature Parity Audit

### Feature Implementation Status

| Talend Feature | Implemented? | Fidelity | Notes |
|----------------|-------------|----------|-------|
| Row-by-row schema validation | Yes | Low | Uses `iterrows()` -- functionally correct but performance-critical issue |
| Nullability check | Yes | Medium | Checks `pd.isnull()` and empty string. Treats empty strings as null unconditionally (no `ALL_EMPTY_ARE_NULL` toggle) |
| Type check | Partial | Low | Only 4 types supported: `id_Integer`, `id_String`, `id_Float`, `id_Date`. Missing: `id_Long`, `id_Double`, `id_Boolean`, `id_BigDecimal`, `id_Object`, `id_Character`, `id_Byte`, `id_Short` |
| Type coercion on mismatch | Yes | Medium | Attempts `int(float(str(value)))` for Integer, `float(str(value))` for Float. May produce incorrect results for edge cases |
| Length check | Yes | Low | Only checks string values. Does not enforce for non-string types. Not triggered unless `col_length` is explicitly set |
| FLOW output (valid rows) | Yes | High | Valid rows collected into `main` output |
| REJECT output (invalid rows) | Yes | Medium | Reject rows include `errorCode` and `errorMessage`, but error code is hardcoded to `8` |
| Error message format | Yes | Low | Format differs from Talend. Uses `col_name:error_type` semicolon-joined. Talend provides more structured messages |
| Check All Columns mode | Implicit | Medium | Engine always checks all columns in schema. No way to switch to "Custom defined" mode |
| Custom Defined mode | No | N/A | **No support for selective per-column validation** |
| Checked Columns table | No | N/A | **Not implemented** |
| SUB_STRING (trim excess) | No | N/A | **`sub_string` config key is extracted by converter but completely ignored by engine** |
| Date pattern validation | No | N/A | **`id_Date` mapped to `str` -- no date format checking at all** |
| Fastest Date Check | No | N/A | **Not implemented** |
| Strict Date Check | No | N/A | **`strict_date_check` extracted but ignored by engine** |
| Ignore TimeZone | No | N/A | **Not implemented** |
| Treat Empty as NULL toggle | No | N/A | **`all_empty_are_null` extracted but ignored -- engine always treats empty as null** |
| Check String by Byte Length | No | N/A | **Not implemented** |
| Charset-based byte length | No | N/A | **Not implemented** |
| Use Another Schema | No | N/A | **Not implemented** |
| tStatCatcher Statistics | No | N/A | **Not implemented** |
| ERROR_MESSAGE global variable | No | N/A | **Not set** |
| `{id}_NB_LINE` globalMap | Yes | High | Set via `_update_stats()` and `_update_global_map()` in base class |
| `{id}_NB_LINE_OK` globalMap | Yes | High | Set via `_update_stats()` and `_update_global_map()` in base class |
| `{id}_NB_LINE_REJECT` globalMap | Yes | High | Set via `_update_stats()` and `_update_global_map()` in base class |

### Behavioral Differences from Talend

| ID | Priority | Difference |
|----|----------|------------|
| ENG-SCC-001 | **P0** | **Type validation is non-functional for converted jobs**: Due to CONV-SCC-001, the converter produces Python type strings (e.g., `'int'`, `'str'`) but the engine's `TALEND_TYPE_MAPPING` only recognizes Talend-format types (`'id_Integer'`, `'id_String'`). The `talend_type_mapping.get(col_type, None)` call returns `None` for all converted types, causing the entire `isinstance()` check to be skipped. **Every row passes type validation regardless of actual type mismatches.** |
| ENG-SCC-002 | **P0** | **Row-by-row `iterrows()` causes O(n*m) performance**: The engine iterates over every row using `input_data.iterrows()` and checks every schema column per row. For a DataFrame with 1M rows and 20 columns, this produces 20M Python-level operations. Pandas `iterrows()` is notoriously slow -- approximately 100-1000x slower than vectorized operations. A 1M-row dataset that should validate in <1 second will take minutes. **This is a production blocker for any non-trivial data volume.** |
| ENG-SCC-003 | **P1** | **Only 4 of 12 Talend types supported**: The `TALEND_TYPE_MAPPING` only contains `id_Integer`, `id_String`, `id_Float`, and `id_Date`. Missing types: `id_Long`, `id_Double`, `id_Boolean`, `id_BigDecimal`, `id_Object`, `id_Character`, `id_Byte`, `id_Short`. Columns with unsupported types will fail `_validate_config()` and the component will not execute. |
| ENG-SCC-004 | **P1** | **`id_Date` mapped to `str` provides no date validation**: The type mapping sets `'id_Date': str`, meaning any string value passes date type checking. Talend validates dates against specific patterns (e.g., `dd-MM-yyyy`). The V1 engine performs zero date format validation. Invalid dates like `"not-a-date"` will pass as valid. |
| ENG-SCC-005 | **P1** | **Empty-as-null behavior is not configurable**: The engine unconditionally treats empty strings as null (line 174: `isinstance(value, str) and value.strip() == ''`). Talend's `ALL_EMPTY_ARE_NULL` parameter (default `true`) allows toggling this behavior. The converter extracts `all_empty_are_null` but the engine ignores it. Jobs that set this to `false` will see different validation results. |
| ENG-SCC-006 | **P1** | **`sub_string` (trim excess) is extracted but ignored**: The converter correctly parses `SUB_STRING` into `config['sub_string']`, but the engine's `_process()` method never reads this config key. When Talend would silently truncate a too-long string, the V1 engine rejects the entire row. |
| ENG-SCC-007 | **P2** | **No Custom Defined mode**: The engine always validates all schema columns. Talend's "Custom defined" mode allows selective validation of specific columns with specific check types. Jobs using custom mode will see validation applied to columns that should be unchecked. |
| ENG-SCC-008 | **P2** | **Hardcoded error code `8`**: The engine uses `DEFAULT_ERROR_CODE = 8` for all violations. Talend may use different error codes for different violation types (type mismatch vs. nullability vs. length). Downstream components that switch on `errorCode` will not work correctly. |
| ENG-SCC-009 | **P2** | **Error message format differs from Talend**: The engine produces `col_name:error_type` (e.g., `amount:invalid type;name:cannot be null`). Talend produces more descriptive messages. Downstream components parsing `errorMessage` will see different formats. |
| ENG-SCC-010 | **P3** | **ERROR_MESSAGE global variable not set**: Talend's `{id}_ERROR_MESSAGE` After-scope variable is not populated. Components referencing this variable downstream will get null. |

---

## 4. Code Quality Audit

### Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-SCC-001 | **P0** | `schema_compliance_check.py` line 192 | **Type validation silently skipped when type is unrecognized**: `expected_type = talend_type_mapping.get(col_type, None)` returns `None` for any type not in the 4-entry mapping. The subsequent `if expected_type and not isinstance(...)` evaluates to `False` when `expected_type` is `None`, silently skipping type validation. Combined with the converter producing Python type strings (`'int'`, `'str'`) instead of Talend types (`'id_Integer'`, `'id_String'`), this means **type validation never runs for any converted job**. This is a silent data quality failure. |
| BUG-SCC-002 | **P1** | `schema_compliance_check.py` line 171 | **Missing column in input data is not detected**: `value = row.get(col_name)` returns `None` when `col_name` does not exist in the input DataFrame. This `None` is then treated as a null value. If the column is nullable, the missing column is silently accepted. If not nullable, it produces a "cannot be null" error rather than a "column missing" error. Talend would report a schema mismatch for missing columns. The distinction matters for debugging -- "missing column" and "null value" are different root causes. |
| BUG-SCC-003 | **P1** | `schema_compliance_check.py` line 197 | **Row mutation during iteration does not update DataFrame**: `row[col_name] = converted_value` attempts to update a Series object obtained from `iterrows()`. In pandas, the row from `iterrows()` is a **copy** of the DataFrame row, not a view. Modifying it does not update the original DataFrame. Consequently, type-coerced values (e.g., string `"123"` converted to integer `123`) are computed but discarded. The valid output DataFrame still contains the original unconverted values. This means the type coercion feature is entirely non-functional. |
| BUG-SCC-004 | **P1** | `schema_compliance_check.py` lines 182-188 | **Length check only applies to string values**: The condition `if col_length is not None and isinstance(value, str)` means length is never checked for non-string types. In Talend, length constraints can apply to numeric types as well (number of digits). Integer `12345` with `length=3` would pass the V1 engine but be rejected by Talend. |
| BUG-SCC-005 | **P2** | `schema_compliance_check.py` line 174 | **Whitespace-only strings treated as null**: The check `value.strip() == ''` means a string containing only whitespace (e.g., `"   "`) is treated as empty/null. Talend's behavior depends on `ALL_EMPTY_ARE_NULL` setting. When this setting is `false`, whitespace-only strings should be treated as non-null values. Since the engine ignores the `all_empty_are_null` config, this is always-on behavior. |
| BUG-SCC-006 | **P2** | `schema_compliance_check.py` line 195 | **Integer coercion via `int(float(str(value)))` is lossy**: The conversion chain `int(float(str(value)))` truncates floating-point values. For example, `3.7` becomes `3`, not a type error. In Talend, passing a float value to an integer column would be a type mismatch rejection, not a silent truncation. This changes the semantics of type validation from strict checking to loose coercion. |
| BUG-SCC-007 | **P2** | `schema_compliance_check.py` line 160 | **Row index from `iterrows()` ignored, using enumerate instead**: The code uses `for row_idx, (_, row) in enumerate(input_data.iterrows())`. The underscore discards the actual DataFrame index, and `row_idx` is a zero-based counter. This is functionally fine but wastes computation since `iterrows()` already provides an index. Could use `for row_idx, row in input_data.iterrows()` if the DataFrame index is sequential. |

### Print Statements (Standards Violation)

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| STD-SCC-001 | **P1** | `schema_compliance_check.py` line 177 | **`print(error_msg)` for nullability violation**: Direct `print()` to stdout. The STANDARDS.md explicitly states: "DON'T: Use print statements -- `print(f"Processing {row_count} rows")  # BAD`". This print statement will produce uncontrolled output to stdout in production, potentially interfering with structured logging, breaking JSON-output pipelines, and making the component untestable for output capture. The message is already logged via `logger.info(error_msg)` on the next line, making the print entirely redundant. |
| STD-SCC-002 | **P1** | `schema_compliance_check.py` line 186 | **`print(error_msg)` for length violation**: Same issue as STD-SCC-001, for the length constraint violation code path. Redundant with the `logger.info()` call on line 187. |
| STD-SCC-003 | **P1** | `schema_compliance_check.py` line 204 | **`print(error_msg)` for type mismatch violation**: Same issue as STD-SCC-001, for the type mismatch code path. Redundant with the `logger.info()` call on line 205. |

### Logging Issues

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| LOG-SCC-001 | **P2** | `schema_compliance_check.py` lines 178, 187, 205 | **Validation errors logged at INFO level**: Per STANDARDS.md, INFO is for "key milestones, statistics" like component start/end. Individual row validation errors are detailed flow data and should be at DEBUG level. At INFO level, processing 10,000 rows with 5% rejection rate would produce 500 INFO-level log lines per execution, creating significant log noise in production. |
| LOG-SCC-002 | **P2** | `schema_compliance_check.py` line 157 | **Debug log "Starting row-by-row schema validation" provides no value**: This log message at DEBUG level contains no variable data (no row count, no schema info). It is redundant with the INFO log on line 145 which already indicates processing has started with row count. |

### Naming Consistency

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| NAME-SCC-001 | **P2** | `schema_compliance_check.py` line 162 | **`row_name` variable is misleading**: `row_name = f"Row({row_idx + 1})"` creates a string used in error messages. The variable name `row_name` implies it holds an actual identifier or label for the row. A more descriptive name like `row_label` or `row_reference` would be clearer. |
| NAME-SCC-002 | **P3** | `schema_compliance_check.py` line 155 | **Redundant local variable**: `talend_type_mapping = self.TALEND_TYPE_MAPPING` creates a local alias for the class constant. While this may have been intended as a micro-optimization (avoiding attribute lookup in a loop), the performance gain is negligible compared to the `iterrows()` overhead. Accessing `self.TALEND_TYPE_MAPPING` directly would be clearer. |

### Standards Compliance

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| STD-SCC-004 | **P2** | `schema_compliance_check.py` | **`validate_config()` is never called**: The engine's `execute()` method in `base_component.py` does not call `validate_config()` before `_process()`. The `validate_config()` and `_validate_config()` methods exist but are dead code -- never invoked during normal execution. Invalid configurations (missing schema, unsupported types) will cause runtime errors inside `_process()` rather than clean validation failures. |
| STD-SCC-005 | **P2** | `schema_compliance_check.py` | **Extracted config keys ignored**: The converter extracts `check_all`, `sub_string`, `strict_date_check`, and `all_empty_are_null` into the config dictionary, but the engine's `_process()` method never reads any of these keys. These represent 4 Talend parameters that were correctly identified during conversion but have no engine-side implementation. |
| STD-SCC-006 | **P3** | `schema_compliance_check.py` line 236 | **Dual validation methods**: The class has both `validate_config()` (public, returns bool) and `_validate_config()` (private, returns list of errors). The public method is described as "backward compatibility" but since neither is called by the engine, this creates unnecessary API surface. |

### Error Handling

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| ERR-SCC-001 | **P2** | `schema_compliance_check.py` line 123 | **No try-except in `_process()`**: The `_process()` method does not wrap its core logic in a try-except block. If an unexpected error occurs during row iteration (e.g., a column value that causes `int(float(str(value)))` to raise an unexpected exception type beyond ValueError/TypeError), the entire component fails with an unhandled exception. The STANDARDS.md Pattern 1 recommends wrapping core processing in try-except with graceful degradation. |
| ERR-SCC-002 | **P2** | `schema_compliance_check.py` line 202 | **Narrow exception handling**: Only `ValueError` and `TypeError` are caught during type coercion. Other possible exceptions like `OverflowError` (for extremely large numbers), `AttributeError` (if value lacks expected methods), or `UnicodeDecodeError` are not handled. |

### Type Hints

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| TYPE-SCC-001 | **P3** | `schema_compliance_check.py` | **Missing return type on `validate_config()`**: The public `validate_config()` method at line 236 has a return type annotation `-> bool` which is correct. However, the method is documented as "backward compatibility" without specifying the interface contract. |

---

## 5. Performance & Memory Audit

| ID | Priority | Issue |
|----|----------|-------|
| PERF-SCC-001 | **P0** | **`iterrows()` is a critical performance bottleneck**: The entire validation logic uses `for row_idx, (_, row) in enumerate(input_data.iterrows())` which is the slowest way to iterate over a pandas DataFrame. Benchmarks show `iterrows()` processes approximately 1,000-10,000 rows/second for typical DataFrames, compared to vectorized operations at 1M+ rows/second. For a production dataset of 1M rows with 10 schema columns, validation will take approximately 100-1000 seconds instead of <1 second with vectorized checks. **This is 100-1000x slower than necessary.** A vectorized approach using `df.apply()`, `pd.to_numeric()`, `df.isna()`, and `df.str.len()` would eliminate this bottleneck entirely. |
| PERF-SCC-002 | **P1** | **Row-by-row list accumulation creates memory pressure**: Valid and rejected rows are accumulated in Python lists (`valid_rows` and `reject_rows`) as dictionaries, then converted to DataFrames at the end (lines 220-221). For a 1M-row DataFrame where 99% of rows are valid, this creates 990,000 dictionary objects in `valid_rows`, each containing copies of the row data. This effectively doubles the memory usage of the input data. A vectorized approach using boolean masking (`valid_mask = ...`, `valid_df = input_data[valid_mask]`) would use negligible additional memory. |
| PERF-SCC-003 | **P2** | **String strip operation on every value in null check**: Line 174 performs `value.strip() == ''` on every string value in every row. This creates a new string object for each call. For a 1M-row DataFrame with 5 string columns, this is 5M string allocations just for the null check. A vectorized approach using `df[col].str.strip().eq('')` would be significantly more efficient. |
| PERF-SCC-004 | **P2** | **Base class streaming mode drops reject data**: The `_execute_streaming()` method in `base_component.py` (line 270-271) only collects `chunk_result['main']` and ignores `chunk_result.get('reject')`. If the SchemaComplianceCheck component is executed in streaming mode (for data exceeding `MEMORY_THRESHOLD_MB`), all reject data is silently discarded. The valid output will be correct, but the reject flow will be empty regardless of actual validation failures. |

### Performance Projection

| Dataset Size | Estimated V1 Time | Expected Vectorized Time | Slowdown Factor |
|-------------|-------------------|-------------------------|-----------------|
| 10,000 rows | 1-10 seconds | <0.01 seconds | 100-1000x |
| 100,000 rows | 10-100 seconds | <0.1 seconds | 100-1000x |
| 1,000,000 rows | 100-1000 seconds | <1 second | 100-1000x |
| 10,000,000 rows | 1000-10000 seconds | <10 seconds | 100-1000x |

---

## 6. Testing Audit

| ID | Priority | Issue |
|----|----------|-------|
| TEST-SCC-001 | **P0** | **No unit tests exist for SchemaComplianceCheck**: A search for `SchemaComplianceCheck` or `schema_compliance` across all test directories (`tests/v1/`, `tests/v2/`) returned zero results. There is zero test coverage for this component. The most critical validation component in the transform category has never been tested. |

### Recommended Test Cases

#### P0 -- Critical Tests

| Test | Description |
|------|-------------|
| Basic valid data | Pass a DataFrame where all rows comply with schema. Verify all rows appear in `main` output, zero rows in `reject`, stats correct. |
| Basic invalid data -- null violation | Pass a DataFrame with null in a non-nullable column. Verify row appears in `reject` with correct `errorCode` and `errorMessage`. |
| Basic invalid data -- type violation | Pass a DataFrame with string value in an integer column. Verify row appears in `reject`. |
| Mixed valid/invalid | Pass a DataFrame with mix of valid and invalid rows. Verify correct split between `main` and `reject`. |
| Config validation -- missing schema | Instantiate with no `schema` key. Verify `_validate_config()` returns error. |
| Config validation -- empty schema | Instantiate with `schema=[]`. Verify `_validate_config()` returns error. |
| Config validation -- unsupported type | Instantiate with schema containing `id_Long`. Verify `_validate_config()` returns error (currently this is the case, which is itself a bug). |
| Type mapping with converter output | Pass schema with converter-produced types (`'int'`, `'str'`) and verify behavior matches expectation (currently broken). |

#### P1 -- Major Tests

| Test | Description |
|------|-------------|
| Empty input | Pass `None` and empty DataFrame. Verify empty output and correct stats. |
| Length violation | Pass string exceeding `col_length`. Verify rejection. |
| Type coercion -- string to int | Pass string `"123"` to integer column. Verify coercion succeeds and output value is correct integer (currently broken -- value not actually updated). |
| Type coercion -- non-numeric string to int | Pass string `"abc"` to integer column. Verify rejection. |
| Multiple errors per row | Pass row with both null violation and type violation. Verify `errorMessage` contains both errors separated by semicolons. |
| All rows rejected | Pass DataFrame where every row violates schema. Verify empty `main`, all rows in `reject`. |
| All rows valid | Pass fully compliant DataFrame. Verify empty `reject`. |
| Date column validation | Pass date column values and verify behavior (currently mapped to `str`, no validation). |
| Missing column in input | Pass DataFrame missing a schema-defined column. Verify appropriate error handling. |
| GlobalMap statistics | Execute with global_map and verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are correctly set. |

#### P2 -- Moderate Tests

| Test | Description |
|------|-------------|
| Whitespace-only string in non-nullable column | Verify `"   "` is treated as null/empty. |
| Large DataFrame performance | Time validation of 100K+ rows to establish baseline and detect regressions. |
| Float truncation on int coercion | Verify `3.7` in integer column is correctly handled (should reject, not truncate). |
| Schema with all supported types | Test each of the 4 supported types individually. |
| Error message format | Verify exact format of `errorMessage` for each violation type. |
| `sub_string` config behavior | Verify that `sub_string=true` is properly handled (currently not implemented). |
| `all_empty_are_null` config behavior | Verify configurable empty-string handling (currently not implemented). |
| Streaming mode reject preservation | Verify reject data is preserved when component runs in streaming mode (currently broken). |

---

## 7. Issues Summary

### All Issues by Priority

#### P0 -- Critical (5 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-SCC-001 | Converter | Type conversion mismatch: converter produces `'int'`/`'str'` but engine expects `'id_Integer'`/`'id_String'`, rendering type validation non-functional for all converted jobs |
| ENG-SCC-001 | Engine | Type validation silently skipped for all converted jobs due to type mapping lookup failure |
| ENG-SCC-002 | Engine | `iterrows()` row-by-row processing is 100-1000x slower than vectorized alternative, blocking production use for non-trivial data volumes |
| PERF-SCC-001 | Performance | `iterrows()` creates O(n*m) Python-level operations for n rows and m columns |
| TEST-SCC-001 | Testing | Zero unit tests for the component |

#### P1 -- Major (9 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-SCC-002 | Converter | CHECKED_COLUMNS table not extracted -- Custom Defined mode validation rules lost |
| CONV-SCC-003 | Converter | MODE parameter not extracted -- cannot distinguish Check All vs. Custom Defined |
| CONV-SCC-004 | Converter | Date pattern not extracted from schema metadata |
| ENG-SCC-003 | Engine | Only 4 of 12 Talend data types supported in type mapping |
| ENG-SCC-004 | Engine | `id_Date` mapped to `str` provides zero date format validation |
| ENG-SCC-005 | Engine | `ALL_EMPTY_ARE_NULL` behavior not configurable -- always treats empty as null |
| ENG-SCC-006 | Engine | `sub_string` (trim excess) extracted by converter but ignored by engine |
| BUG-SCC-003 | Bug | Type coercion writes to `iterrows()` copy, not original DataFrame -- coerced values discarded |
| STD-SCC-001 | Standards | `print()` to stdout for nullability errors (also STD-SCC-002, STD-SCC-003) |
| PERF-SCC-002 | Performance | Row-by-row list accumulation doubles memory usage |

#### P2 -- Moderate (14 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-SCC-005 | Converter | FASTEST_DATE_CHECK and IGNORE_TIMEZONE not extracted |
| CONV-SCC-006 | Converter | CHECK_BYTE_LENGTH and CHARSET not extracted |
| ENG-SCC-007 | Engine | No Custom Defined mode -- always validates all columns |
| ENG-SCC-008 | Engine | Error code hardcoded to `8` for all violation types |
| ENG-SCC-009 | Engine | Error message format differs from Talend output |
| BUG-SCC-002 | Bug | Missing columns in input treated as null rather than schema mismatch |
| BUG-SCC-004 | Bug | Length check only applies to string values, not numeric types |
| BUG-SCC-005 | Bug | Whitespace-only strings unconditionally treated as null |
| BUG-SCC-006 | Bug | `int(float(str(value)))` silently truncates floats instead of rejecting |
| LOG-SCC-001 | Logging | Row validation errors logged at INFO level instead of DEBUG |
| STD-SCC-004 | Standards | `validate_config()` / `_validate_config()` never called by engine |
| STD-SCC-005 | Standards | Four extracted config keys ignored by engine |
| ERR-SCC-001 | Error Handling | No try-except around core processing logic |
| ERR-SCC-002 | Error Handling | Narrow exception handling -- only ValueError/TypeError caught |
| PERF-SCC-003 | Performance | String strip on every value creates unnecessary allocations |
| PERF-SCC-004 | Performance | Streaming mode discards reject data |

#### P3 -- Low (5 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-SCC-007 | Converter | Schema precision and key attributes not extracted |
| ENG-SCC-010 | Engine | ERROR_MESSAGE global variable not set |
| NAME-SCC-001 | Naming | `row_name` variable is misleading |
| NAME-SCC-002 | Naming | Redundant local alias for class constant |
| STD-SCC-006 | Standards | Dual validation methods (public + private) with neither being called |

### Issue Count Summary

| Priority | Count |
|----------|-------|
| P0 -- Critical | 5 |
| P1 -- Major | 9 |
| P2 -- Moderate | 14 |
| P3 -- Low | 5 |
| **Total** | **33** |

---

## 8. Detailed Technical Analysis

### 8.1 The Type Mapping Chain: End-to-End Failure

This section traces the full chain from Talend XML to engine execution to demonstrate how type validation is entirely broken for converted jobs.

**Step 1: Talend XML** contains column type `id_Integer`:
```xml
<column name="age" type="id_Integer" nullable="false" length="3"/>
```

**Step 2: Converter** calls `ExpressionConverter.convert_type('id_Integer')` which returns `'int'`:
```python
# In parse_tschema_compliance_check():
'type': self.expr_converter.convert_type(column.get('type', 'id_String'))
# Result: 'type': 'int'
```

**Step 3: Engine** receives config with `'type': 'int'` and looks it up:
```python
TALEND_TYPE_MAPPING = {
    'id_Integer': int,   # Key is 'id_Integer', NOT 'int'
    'id_String': str,
    'id_Float': float,
    'id_Date': str,
}

expected_type = talend_type_mapping.get('int', None)  # Returns None
if expected_type and not isinstance(value, expected_type):
    # This block NEVER executes because expected_type is None
```

**Result**: Type validation is skipped for every column in every row. Invalid data passes through unchecked.

**Fix Required**: Either:
1. Remove `convert_type()` call in the converter parser (preserve Talend type format), OR
2. Add Python type strings to the engine's `TALEND_TYPE_MAPPING` dictionary

Option (1) is preferred per STANDARDS.md which states: "In schema definitions, use Talend type format (`id_String`, `id_Integer`, etc.)" and "The v1 engine maps these types internally."

### 8.2 The `iterrows()` Copy Problem

The type coercion code attempts to update row values:
```python
for row_idx, (_, row) in enumerate(input_data.iterrows()):
    # ...
    if col_type == 'id_Integer':
        converted_value = int(float(str(value)))
        row[col_name] = converted_value  # This does NOTHING to the DataFrame
```

The pandas documentation explicitly warns: "You should never modify something you are iterating over. This is not guaranteed to work in all cases. Depending on the data types, the iterator returns a copy and not a view, and writing to it will have no effect."

After the loop, `valid_rows.append(row)` appends the modified Series copy, so valid rows in the output DataFrame will contain the coerced value. However, this creates an inconsistency: the coerced value is only present in the `valid_df` output if the row was not rejected. If the row has other errors (e.g., another column fails validation), the row in `reject_df` will contain the coerced value for the passing column but the original value for the failing column, creating an inconsistent state.

More critically, the comment on line 197 says "Update the row with converted value", suggesting the developer believed this would modify the original DataFrame. The actual behavior does not match the intent.

### 8.3 Performance Impact Analysis

The current implementation has three nested levels of inefficiency:

1. **`iterrows()` overhead**: Each call produces a Series object, copying data from the internal block structure. For a DataFrame with 20 columns, this is 20 data copies per row.

2. **Per-cell Python operations**: Inside the row loop, each schema column triggers Python-level type checking (`isinstance()`), null checking (`pd.isnull()`), and string operations (`strip()`). For 20 columns and 1M rows, this is 60M+ Python function calls.

3. **List accumulation**: Each valid/rejected row is stored as a dictionary, requiring Python dict creation and data copying. Then `pd.DataFrame(valid_rows)` at the end re-processes all dictionaries into columnar format.

**Vectorized alternative** (sketch):
```python
# Null check (vectorized, all columns at once)
for col in schema:
    if not col['nullable']:
        null_mask = df[col['name']].isna() | (df[col['name']].astype(str).str.strip() == '')
        reject_mask |= null_mask

# Type check (vectorized per column)
for col in schema:
    if col['type'] == 'id_Integer':
        numeric = pd.to_numeric(df[col['name']], errors='coerce')
        type_fail_mask = numeric.isna() & ~df[col['name']].isna()
        reject_mask |= type_fail_mask

# Length check (vectorized per column)
for col in schema:
    if col.get('length') and col['type'] == 'id_String':
        length_mask = df[col['name']].str.len() > col['length']
        reject_mask |= length_mask

valid_df = df[~reject_mask]
reject_df = df[reject_mask].copy()
reject_df['errorCode'] = 8
reject_df['errorMessage'] = # vectorized error message construction
```

This approach operates at the column level rather than the cell level, leveraging pandas' internal C/Cython optimizations.

### 8.4 Empty String vs. Null Handling Analysis

The engine's null check at line 174:
```python
if pd.isnull(value) or (isinstance(value, str) and value.strip() == ''):
```

This conflates three distinct states:
1. **Actual null/NaN** (`pd.isnull(value)` is True)
2. **Empty string** (`value == ''`)
3. **Whitespace-only string** (`value.strip() == ''` but `value != ''`)

Talend distinguishes these based on `ALL_EMPTY_ARE_NULL`:
- When `true` (default): Empty strings are treated as null (states 1+2 are equivalent)
- When `false`: Only actual null/NaN values trigger nullability rejection

The V1 engine always treats all three states as null, which matches Talend's default behavior but cannot handle the `false` case. Additionally, the whitespace-only check (state 3) goes beyond Talend's behavior, which only checks for empty strings, not whitespace-only strings.

### 8.5 Streaming Mode Reject Data Loss

The base class `_execute_streaming()` method:
```python
def _execute_streaming(self, input_data):
    results = []
    for chunk in chunks:
        chunk_result = self._process(chunk)
        if chunk_result.get('main') is not None:
            results.append(chunk_result['main'])
    # ^^^ 'reject' key is completely ignored
    if results:
        combined = pd.concat(results, ignore_index=True)
        return {'main': combined}
    else:
        return {'main': pd.DataFrame()}
```

When SchemaComplianceCheck processes a large dataset in streaming mode (triggered when data exceeds `MEMORY_THRESHOLD_MB = 3072` MB), each chunk produces both `main` and `reject` outputs. The streaming handler only collects `main` outputs, silently discarding all reject data. The downstream reject flow receives an empty DataFrame.

This is especially insidious because:
1. The component correctly produces reject data in `_process()`
2. The streaming handler silently discards it
3. The final result contains only valid data with zero rejected rows
4. The statistics (`NB_LINE_REJECT`) will show zero rejections (since streaming processes chunks independently and stats from individual chunks are not aggregated correctly)

### 8.6 Error Code Analysis

The engine hardcodes `DEFAULT_ERROR_CODE = 8` for all violation types. In Talend, the error code provides structured information about the type of violation:

| Violation Type | Talend Behavior | V1 Engine Behavior |
|---------------|----------------|-------------------|
| Null in non-nullable column | Specific error code | Always `8` |
| Type mismatch | Specific error code | Always `8` |
| Length exceeded | Specific error code | Always `8` |
| Missing column | Schema mismatch error | Treated as null (no distinct handling) |

Downstream components or error-handling logic that switches on `errorCode` to determine the type of violation will not work correctly with the V1 engine's output.

---

## 9. Recommendations

### Immediate (Before Production) -- P0 Fixes

1. **Fix type mapping chain (CONV-SCC-001 / ENG-SCC-001 / BUG-SCC-001)**:
   Remove the `convert_type()` call in the converter's `parse_tschema_compliance_check()` method. Change:
   ```python
   'type': self.expr_converter.convert_type(column.get('type', 'id_String'))
   ```
   to:
   ```python
   'type': column.get('type', 'id_String')
   ```
   This preserves the Talend type format (`id_Integer`, etc.) that the engine expects, consistent with STANDARDS.md guidance.

2. **Replace `iterrows()` with vectorized validation (ENG-SCC-002 / PERF-SCC-001)**:
   Rewrite `_process()` to use column-level vectorized operations:
   - Use `df[col].isna()` for null checks
   - Use `pd.to_numeric(df[col], errors='coerce')` for numeric type checks
   - Use `df[col].str.len()` for length checks
   - Use boolean mask indexing for split: `valid_df = df[~reject_mask]`
   This will improve performance by 100-1000x and eliminate the memory doubling issue.

3. **Remove all `print()` statements (STD-SCC-001/002/003)**:
   Delete the three `print(error_msg)` calls on lines 177, 186, and 204. The `logger.info()` calls immediately following each print already capture the same information.

4. **Create comprehensive unit test suite (TEST-SCC-001)**:
   Implement the P0 and P1 test cases listed in Section 6. Minimum coverage must include: valid data passthrough, null violation rejection, type violation rejection, mixed data, empty input, and config validation.

### Short-Term (Hardening) -- P1 Fixes

5. **Expand type mapping (ENG-SCC-003)**:
   Add all 12 Talend types to `TALEND_TYPE_MAPPING`:
   ```python
   TALEND_TYPE_MAPPING = {
       'id_Integer': int,
       'id_Long': int,
       'id_Short': int,
       'id_Byte': int,
       'id_String': str,
       'id_Character': str,
       'id_Float': float,
       'id_Double': float,
       'id_Boolean': bool,
       'id_Date': 'date',      # Special handling needed
       'id_BigDecimal': Decimal,
       'id_Object': object,
   }
   ```

6. **Implement date validation (ENG-SCC-004 / CONV-SCC-004)**:
   - Extract the `pattern` attribute from column metadata in the converter
   - Implement date pattern validation using `datetime.strptime()` with Talend-to-Python pattern conversion
   - Support both strict and fast date checking modes

7. **Implement `all_empty_are_null` toggle (ENG-SCC-005)**:
   Read `config.get('all_empty_are_null', True)` and conditionally include/exclude the empty string check in null validation.

8. **Implement `sub_string` (trim excess) (ENG-SCC-006)**:
   Read `config.get('sub_string', False)` and when `True`, truncate strings to `col_length` instead of rejecting.

9. **Fix `iterrows()` copy mutation (BUG-SCC-003)**:
   This is resolved by recommendation #2 (vectorized rewrite). If the iterrows approach is temporarily retained, either track coerced values separately or use `df.at[idx, col_name]` for direct DataFrame mutation.

10. **Extract CHECKED_COLUMNS and MODE (CONV-SCC-002 / CONV-SCC-003)**:
    Parse the `CHECKED_COLUMNS` table parameter and `MODE` parameter in the converter to support Custom Defined validation mode.

### Long-Term (Full Parity) -- P2/P3 Fixes

11. **Fix streaming mode reject data loss (PERF-SCC-004)**:
    Modify `_execute_streaming()` in `base_component.py` to collect and concatenate both `main` and `reject` outputs from chunk processing.

12. **Implement per-violation error codes (ENG-SCC-008)**:
    Define distinct error codes for null violations, type violations, and length violations instead of hardcoding `8`.

13. **Implement Custom Defined mode (ENG-SCC-007)**:
    Support selective per-column validation based on the Checked Columns table.

14. **Implement byte-length checking (CONV-SCC-006)**:
    Support `CHECK_BYTE_LENGTH` with configurable charset.

15. **Call `validate_config()` from engine (STD-SCC-004)**:
    Add a `validate_config()` call in the engine's component execution pipeline, before `_process()`, to catch configuration errors early with clear error messages.

16. **Fix logging levels (LOG-SCC-001)**:
    Change per-row validation error logging from INFO to DEBUG level.

17. **Add ERROR_MESSAGE global variable (ENG-SCC-010)**:
    Set `{id}_ERROR_MESSAGE` in global map when validation errors occur.

---

## 10. Appendix: Full Engine Source (Annotated)

```python
"""
TSchemaComplianceCheck - Validate data against predefined schema rules.
Talend equivalent: tSchemaComplianceCheck
"""
import logging
import pandas as pd
from typing import Dict, Any, Optional, List
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class SchemaComplianceCheck(BaseComponent):
    """[docstring omitted for brevity]"""

    # Class constants
    DEFAULT_ERROR_CODE = 8                          # [ENG-SCC-008] Hardcoded for all violations
    DEFAULT_NULLABLE = True
    TALEND_TYPE_MAPPING = {
        'id_Integer': int,                          # [ENG-SCC-003] Only 4 of 12 types
        'id_String': str,
        'id_Float': float,
        'id_Date': str,                             # [ENG-SCC-004] No date validation
    }

    def _validate_config(self) -> List[str]:        # [STD-SCC-004] Never called by engine
        """..."""
        errors = []
        if 'schema' not in self.config:
            errors.append("Missing required config: 'schema'")
            return errors
        schema = self.config['schema']
        if not isinstance(schema, list):
            errors.append("Config 'schema' must be a list")
            return errors
        if len(schema) == 0:
            errors.append("Config 'schema' cannot be empty")
            return errors
        for i, col in enumerate(schema):
            if not isinstance(col, dict):
                errors.append(f"Schema column {i} must be a dictionary")
                continue
            if 'name' not in col:
                errors.append(f"Schema column {i}: missing required field 'name'")
            elif not isinstance(col['name'], str):
                errors.append(f"Schema column {i}: 'name' must be a string")
            if 'type' not in col:
                errors.append(f"Schema column {i}: missing required field 'type'")
            elif not isinstance(col['type'], str):
                errors.append(f"Schema column {i}: 'type' must be a string")
            elif col['type'] not in self.TALEND_TYPE_MAPPING:     # [BUG-SCC-001] Fails for converter output
                valid_types = list(self.TALEND_TYPE_MAPPING.keys())
                errors.append(f"Schema column {i}: unsupported type '{col['type']}'. "
                              f"Valid types: {valid_types}")
            if 'nullable' in col and not isinstance(col['nullable'], bool):
                errors.append(f"Schema column {i}: 'nullable' must be boolean")
            if 'length' in col and not isinstance(col['length'], int):
                errors.append(f"Schema column {i}: 'length' must be an integer")
        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """..."""
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        schema = self.config.get('schema', [])
        # [STD-SCC-005] check_all, sub_string, strict_date_check, all_empty_are_null never read
        logger.debug(f"[{self.id}] Schema validation with {len(schema)} column definitions")

        reject_rows = []                              # [PERF-SCC-002] Memory doubling
        valid_rows = []

        talend_type_mapping = self.TALEND_TYPE_MAPPING # [NAME-SCC-002] Redundant alias
        logger.debug(f"[{self.id}] Starting row-by-row schema validation") # [LOG-SCC-002] No value

        # [PERF-SCC-001] iterrows() -- 100-1000x slower than vectorized
        for row_idx, (_, row) in enumerate(input_data.iterrows()):
            errors = []
            row_name = f"Row({row_idx + 1})"

            for col in schema:
                col_name = col['name']
                col_type = col['type']
                col_nullable = col.get('nullable', self.DEFAULT_NULLABLE)
                col_length = col.get('length', None)

                value = row.get(col_name)             # [BUG-SCC-002] Missing column = None

                # Null/empty check
                if pd.isnull(value) or (isinstance(value, str) and value.strip() == ''):
                    # [BUG-SCC-005] Whitespace treated as null unconditionally
                    # [ENG-SCC-005] all_empty_are_null not checked
                    if not col_nullable:
                        error_msg = f"Value is empty for column : '{col_name}' in '{row_name}'..."
                        print(error_msg)              # [STD-SCC-001] print() to stdout
                        logger.info(error_msg)        # [LOG-SCC-001] Should be DEBUG
                        errors.append(f"{col_name}:cannot be null")
                    continue

                # Length check
                if col_length is not None and isinstance(value, str):
                    # [BUG-SCC-004] Only checks string values
                    # [ENG-SCC-006] sub_string not checked
                    if len(value) > col_length:
                        error_msg = f"Value length exceeds maximum..."
                        print(error_msg)              # [STD-SCC-002] print() to stdout
                        logger.info(error_msg)        # [LOG-SCC-001] Should be DEBUG
                        errors.append(f"{col_name}:exceed max length")

                # Type check
                expected_type = talend_type_mapping.get(col_type, None)
                # [BUG-SCC-001] Returns None for converter-produced types ('int', 'str')
                if expected_type and not isinstance(value, expected_type):
                    try:
                        if col_type == 'id_Integer':
                            converted_value = int(float(str(value)))
                            # [BUG-SCC-006] Truncates floats
                            row[col_name] = converted_value
                            # [BUG-SCC-003] Writes to copy, not DataFrame
                        elif col_type == 'id_Float':
                            converted_value = float(str(value))
                            row[col_name] = converted_value
                            # [BUG-SCC-003] Writes to copy, not DataFrame
                    except (ValueError, TypeError):
                        # [ERR-SCC-002] Misses OverflowError, etc.
                        error_msg = f"Type mismatch..."
                        print(error_msg)              # [STD-SCC-003] print() to stdout
                        logger.info(error_msg)        # [LOG-SCC-001] Should be DEBUG
                        errors.append(f"{col_name}:invalid type")

            if errors:
                reject_rows.append({
                    **row,
                    'errorCode': self.DEFAULT_ERROR_CODE,  # [ENG-SCC-008] Always 8
                    'errorMessage': ';'.join(errors),
                })
            else:
                valid_rows.append(row)

        valid_df = pd.DataFrame(valid_rows)
        reject_df = pd.DataFrame(reject_rows)

        rows_out = len(valid_df)
        rows_rejected = len(reject_df)
        self._update_stats(rows_in, rows_out, rows_rejected)

        logger.info(f"[{self.id}] Schema validation complete: "
                     f"in={rows_in}, valid={rows_out}, rejected={rows_rejected}")
        if rows_rejected > 0:
            logger.info(f"[{self.id}] Rejected {rows_rejected} rows due to schema violations")

        return {'main': valid_df, 'reject': reject_df}

    def validate_config(self) -> bool:                # [STD-SCC-006] Dual methods, neither called
        """..."""
        errors = self._validate_config()
        if errors:
            for error in errors:
                logger.error(f"[{self.id}] Configuration error: {error}")
            return False
        logger.debug(f"[{self.id}] Configuration validation passed")
        return True
```

---

## 11. Appendix: Converter Parser Source (Annotated)

```python
def parse_tschema_compliance_check(self, node, component: Dict) -> Dict:
    """Parse tSchemaComplianceCheck specific configuration"""
    schema = []

    # Parse schema from metadata
    for metadata in node.findall('./metadata'):
        if metadata.get('connector') == 'FLOW':
            for column in metadata.findall('./column'):
                schema.append({
                    'name': column.get('name', ''),
                    'type': self.expr_converter.convert_type(
                        column.get('type', 'id_String')
                    ),
                    # ^^^ [CONV-SCC-001] Converts 'id_Integer' -> 'int'
                    #     Engine expects 'id_Integer'
                    'nullable': column.get('nullable', 'true').lower() == 'true',
                    'length': int(column.get('length', 0)) if column.get('length') else None
                    # [CONV-SCC-007] 'key', 'precision', 'pattern' not extracted
                })

    # Parse additional parameters
    component['config']['schema'] = schema
    component['config']['check_all'] = node.find(
        './/elementParameter[@name="CHECK_ALL"]'
    ).get('value', 'false').lower() == 'true'
    component['config']['sub_string'] = node.find(
        './/elementParameter[@name="SUB_STRING"]'
    ).get('value', 'false').lower() == 'true'
    component['config']['strict_date_check'] = node.find(
        './/elementParameter[@name="STRICT_DATE_CHECK"]'
    ).get('value', 'false').lower() == 'true'
    component['config']['all_empty_are_null'] = node.find(
        './/elementParameter[@name="ALL_EMPTY_ARE_NULL"]'
    ).get('value', 'false').lower() == 'true'
    # [CONV-SCC-002] CHECKED_COLUMNS table not parsed
    # [CONV-SCC-003] MODE parameter not parsed
    # [CONV-SCC-005] FASTEST_DATE_CHECK, IGNORE_TIMEZONE not parsed
    # [CONV-SCC-006] CHECK_BYTE_LENGTH, CHARSET not parsed

    return component
```

---

## 12. Appendix: Registration and Dispatch

### Engine Registration (`engine.py`)

The component is registered with two aliases in the engine's component registry:

```python
# Line 32
from .components.transform import Join, PivotToColumnsDelimited, SchemaComplianceCheck

# Lines 152-153
'SchemaComplianceCheck': SchemaComplianceCheck,
'tSchemaComplianceCheck': SchemaComplianceCheck,
```

Both `SchemaComplianceCheck` and `tSchemaComplianceCheck` resolve to the same class.

### Converter Dispatch (`converter.py`)

The converter dispatches to the parser method based on `component_type`:

```python
# Line 333-334
elif component_type == 'tSchemaComplianceCheck':
    component = self.component_parser.parse_tschema_compliance_check(node, component)
```

### Transform Package Registration (`__init__.py`)

The component is exported from the transform package:

```python
from .schema_compliance_check import SchemaComplianceCheck
# Listed in __all__
```

---

## 13. Appendix: Talend Documentation Sources

The following sources were consulted during this audit:

- [tSchemaComplianceCheck Standard properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/validation/tschemacompliancecheck-standard-properties)
- [tSchemaComplianceCheck (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/validation/tschemacompliancecheck)
- [Validating data against schema (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/validation/validating-data-against-schema)
- [tSchemaComplianceCheck Standard properties (Talend 7.3)](https://help.talend.com/r/en-US/7.3/validation/tschemacompliancecheck-standard-properties)
- [tSchemaComplianceCheck (Talend 7.2)](https://help.qlik.com/talend/en-US/components/7.2/validation/tschemacompliancecheck)
- [tSchemaComplianceCheck -- Docs for ESB 7.x (Talend Skill)](https://talendskill.com/talend-for-esb-docs/docs-7-x/tschemacompliancecheck-talend-open-studio-for-esb-document-7-x/)
- [tSchemaComplianceCheck -- Docs for ESB 5.x (Talend Skill)](https://talendskill.com/talend-for-esb-docs/docs-5-x/tschemacompliancecheck-docs-for-esb-5-x/)
- [Configuring the components (Talend 7.3)](https://help.talend.com/en-US/components/7.3/validation/tschemacompliancecheck-tlogrow-tfileinputdelimited-tfileinputdelimited-configuring-components-standard-component-enterprise)
- [Validating against the schema -- Talend Open Studio Cookbook](https://www.oreilly.com/library/view/talend-open-studio/9781782167266/ch03s04.html)
- [Data validation with tSchemaComplianceCheck (ETLGeeks Blog)](https://etlgeeks.blogspot.com/2015/01/data-validation-with.html)
- [About tSchemaComplianceCheck nullable (Talend Forum)](https://www.talendforge.org/forum/viewtopic.php?id=11894)

---

## 14. Appendix: Verdict

### Production Readiness: NOT READY

The `SchemaComplianceCheck` component has **5 critical (P0) issues** that collectively render it non-functional for its primary purpose:

1. **Type validation does not work** for any job converted from Talend XML due to a type-mapping mismatch between the converter and engine.
2. **Performance is 100-1000x slower** than necessary due to row-by-row `iterrows()` iteration, making it unsuitable for production data volumes.
3. **No test coverage exists**, providing zero confidence in correctness.
4. **`print()` statements** violate coding standards and produce uncontrolled stdout output.
5. **Multiple extracted config keys are ignored**, meaning converter work is wasted and Talend behavioral fidelity is compromised.

The component requires a **significant rewrite** before production deployment. The recommended approach is:

1. Fix the converter type mapping (1 line change)
2. Rewrite `_process()` with vectorized pandas operations (eliminate `iterrows()`)
3. Remove `print()` statements
4. Implement the 4 ignored config keys (`check_all`, `sub_string`, `strict_date_check`, `all_empty_are_null`)
5. Expand type mapping to cover all 12 Talend types
6. Create comprehensive unit tests

Estimated effort: **3-5 days** for a developer familiar with both pandas and Talend semantics.
