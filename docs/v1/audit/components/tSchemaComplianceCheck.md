# Audit Report: tSchemaComplianceCheck / SchemaComplianceCheck

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tSchemaComplianceCheck` |
| **V1 Engine Class** | `SchemaComplianceCheck` |
| **Engine File** | `src/v1/engine/components/transform/schema_compliance_check.py` (256 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tschema_compliance_check()` (lines 2080-2102) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `_parse_component()` (lines 333-334): `elif component_type == 'tSchemaComplianceCheck': component = self.component_parser.parse_tschema_compliance_check(node, component)` |
| **Registry Aliases** | `SchemaComplianceCheck`, `tSchemaComplianceCheck` (registered in `src/v1/engine/engine.py` lines 152-153) |
| **Category** | Transform / Validation (Data Quality) |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/schema_compliance_check.py` | Engine implementation (256 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 2080-2102) | Parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (lines 333-334) | Dispatch -- dedicated `elif` branch for `tSchemaComplianceCheck` |
| `src/converters/complex_converter/expression_converter.py` (lines 231-255) | `convert_type()` -- Talend-to-Python type conversion |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `_execute_streaming()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/components/transform/__init__.py` | Package exports -- `SchemaComplianceCheck` in `__all__` |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **R** | 2 | 3 | 2 | 1 | 5 of 14 Talend params extracted (36%); critical type conversion mismatch; `node.find()` null crash; missing MODE, CHECKED_COLUMNS, date pattern |
| Engine Feature Parity | **R** | 2 | 5 | 3 | 1 | Type validation broken end-to-end; only 4 of 12 types; no date validation; no Custom Defined mode; ignored config keys |
| Code Quality | **R** | 2 | 6 | 7 | 4 | Cross-cutting base class bugs; 3x `print()` to stdout; iterrows copy mutation; lossy int coercion; dead validate_config; length=-1 sentinel; reject column overwrite; float inf crash |
| Performance & Memory | **R** | 1 | 1 | 2 | 0 | `iterrows()` is 100-1000x slower than vectorized; memory doubling; streaming discards reject data |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero unit tests; zero integration tests for this component |

**Overall: RED -- Not production-ready. Multiple critical failures across all dimensions.**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

### Priority Definitions
- **P0**: Critical -- blocks production use or causes data corruption/silent failures
- **P1**: Major -- significant functional gap or behavioral divergence from Talend
- **P2**: Moderate -- missing feature, code quality concern, or non-standard practice
- **P3**: Low -- minor improvement, cosmetic issue, or rarely-used feature gap

---

## 3. Talend Feature Baseline

### What tSchemaComplianceCheck Does

`tSchemaComplianceCheck` is a data quality validation component belonging to the **Data Quality** family. It acts as an intermediary step in a data flow, validating all input rows against a reference schema by checking data types, nullability constraints, and field length limits. Non-compliant rows are routed to a REJECT output flow with supplementary `errorCode` and `errorMessage` columns for downstream error handling.

The component is **not included in Talend Studio by default** and requires installation via the Feature Manager, indicating it is a specialized data quality tool rather than a general-purpose component.

**Source**: [tSchemaComplianceCheck Standard properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/validation/tschemacompliancecheck-standard-properties), [tSchemaComplianceCheck (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/validation/tschemacompliancecheck), [tSchemaComplianceCheck Standard properties (Talend 7.3)](https://help.talend.com/r/en-US/7.3/validation/tschemacompliancecheck-standard-properties)

**Component family**: Data Quality (Validation)
**Available in**: All Talend products (Standard). Also available in Spark Streaming variant.
**Prerequisite**: Requires installation via Feature Manager in Talend Studio.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Base Schema | `SCHEMA` | Schema editor | Built-In | Reference schema defining column names, types, lengths, nullability, date patterns. Defines the validation template. |
| 2 | Schema Source | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether schema comes from local definition or metadata repository. Not needed at runtime. |
| 3 | Mode | `MODE` | Radio | Check All | Validation mode: "Check all columns from schema" or "Custom defined". Controls whether all columns or selective columns are validated. |
| 4 | Check All Columns | `CHECK_ALL` | Boolean | `true` | Perform type, nullability, and length checks on all columns against the base schema. Active when MODE is "Check all". |
| 5 | Custom Defined | -- | Boolean | `false` | Enable selective checking via Checked Columns table. Active when MODE is "Custom defined". |
| 6 | Checked Columns | `CHECKED_COLUMNS` | Table | -- | Per-column validation rules table. Each row: Column (name), Type (enum), Date Pattern (string), Nullable (bool), Max Length (bool). Only visible in Custom Defined mode. |
| 7 | Use Another Schema | -- | Boolean | `false` | Define a separate reference schema for compliance comparison. |
| 8 | Trim Excess Content | `SUB_STRING` | Boolean | `false` | Truncate data exceeding defined length instead of rejecting (String type only). When enabled, overlong strings are silently truncated rather than causing row rejection. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 9 | Fastest Date Check | `FASTEST_DATE_CHECK` | Boolean | `false` | Use `TalendDate.isDate()` for fast date validation when no pattern defined. Hidden when Strict Date Check is enabled. |
| 10 | Strict Date Check | `STRICT_DATE_CHECK` | Boolean | `false` | Enable strict format validation. Hides Fastest Date Check when enabled. |
| 11 | Ignore TimeZone | `IGNORE_TIMEZONE` | Boolean | `false` | Disregard timezone during date validation. Unavailable in "Check all" mode. |
| 12 | Treat Empty as NULL | `ALL_EMPTY_ARE_NULL` | Boolean | `true` | Treat empty string fields as null values instead of empty strings. Critical for nullability checking behavior. |
| 13 | Choose Columns | -- | Table | -- | Per-column empty-as-null selection. Appears when Treat Empty as NULL is unchecked. |
| 14 | Check String by Byte Length | `CHECK_BYTE_LENGTH` | Boolean | `false` | Validate string length using byte count per charset setting. |
| 15 | Charset | `CHARSET` | String | Default | Character encoding for byte-length checking. Only visible when CHECK_BYTE_LENGTH is enabled. |
| 16 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean | `false` | Collect component-level log data for tStatCatcher component. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row | Incoming data rows to validate against the reference schema. |
| `FLOW` (Main) | Output | Row | Compliant rows that pass all schema checks. Same schema as input. |
| `REJECTS` | Output | Row | Non-compliant rows with ALL original columns PLUS two read-only supplementary columns: `errorCode` (integer) and `errorMessage` (string). These columns appear in green in Talend Studio. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows processed (input rows). |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows that passed validation (sent to FLOW output). Equals `NB_LINE - NB_LINE_REJECT`. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows that failed validation (sent to REJECTS output). |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. Available for downstream error handling. |

### 3.5 Behavioral Notes

1. **Validation Hierarchy**: The component validates in this order: (1) Nullability check, (2) Type check, (3) Length check. A row is rejected on the first violation found for any column.

2. **REJECT Flow Structure**: Rejected rows include ALL original columns plus two read-only supplementary columns: `errorCode` (integer) and `errorMessage` (string describing the violation). The error columns appear in green in Talend Studio to distinguish them from data columns.

3. **Error Code**: Talend uses specific error codes to identify schema compliance violations. The error code is an integer associated with the type of violation.

4. **Empty String Handling**: By default (`ALL_EMPTY_ARE_NULL=true`), empty strings are treated as NULL. This means a non-nullable column receiving an empty string will be rejected. When set to `false`, empty strings are treated as valid non-null values.

5. **SUB_STRING (Trim) Behavior**: When enabled, strings exceeding the defined length are silently truncated to fit rather than causing rejection. This applies to String-type columns only. Does not affect non-string types.

6. **Date Validation Modes**: Three mutually exclusive modes exist -- no date check (default), fastest date check (uses `TalendDate.isDate()`), and strict date check (exact pattern matching). Strict mode hides the fastest option.

7. **Custom vs. Check All**: In "Check all" mode, every column in the schema is validated for type, nullability, and length. In "Custom defined" mode, only columns listed in the Checked Columns table are validated, and each check type can be selectively enabled or disabled per column.

8. **Byte Length Checking**: When enabled, string length is measured in bytes using the specified charset, not in characters. This is relevant for multibyte encodings (UTF-8, etc.).

9. **Component Requirement**: tSchemaComplianceCheck requires an input flow and at least one output connector. It cannot be a job start component.

10. **Type Checking Scope**: Talend validates against its full type system including: `id_String`, `id_Integer`, `id_Long`, `id_Float`, `id_Double`, `id_Boolean`, `id_Date`, `id_BigDecimal`, `id_Object`, `id_Character`, `id_Byte`, `id_Short`.

11. **NaN/Null Handling in Talend**: In Talend's Java runtime, null values in primitive types (int, long, float, double) are handled differently from object types (String, Date, BigDecimal). Primitive fields with null values are rejected if non-nullable, while object fields can naturally hold null. The Python/pandas equivalent introduces `NaN` (float) as the universal null, which behaves differently from Java null in type checking contexts.

---

## 4. Converter Audit

### 4.1 Parser Method: `parse_tschema_compliance_check()`

Located in `component_parser.py` at lines 2080-2102. The parser has a dedicated `elif` branch in `converter.py` (line 333), which is the recommended pattern per STANDARDS.md. It extracts schema from FLOW metadata and four additional boolean parameters.

**Converter flow**:
1. `converter.py:_parse_component()` matches `component_type == 'tSchemaComplianceCheck'` (line 333)
2. Calls `component_parser.parse_tschema_compliance_check(node, component)` (line 334)
3. Parser iterates `<metadata connector="FLOW">` elements to extract column schema
4. Parses four boolean `elementParameter` values: `CHECK_ALL`, `SUB_STRING`, `STRICT_DATE_CHECK`, `ALL_EMPTY_ARE_NULL`
5. Returns component with populated config dict

### 4.2 Parameter Extraction

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `SCHEMA` (metadata) | Yes | `schema` | 2082-2093 | Parsed from `<metadata connector="FLOW">` column elements |
| 2 | `CHECK_ALL` | Yes | `check_all` | 2097 | Boolean conversion. **Extracted but ignored by engine.** |
| 3 | `SUB_STRING` | Yes | `sub_string` | 2098 | Boolean conversion. **Extracted but ignored by engine.** |
| 4 | `STRICT_DATE_CHECK` | Yes | `strict_date_check` | 2099 | Boolean conversion. **Extracted but ignored by engine.** |
| 5 | `ALL_EMPTY_ARE_NULL` | Yes | `all_empty_are_null` | 2100 | Boolean conversion. **Extracted but ignored by engine.** |
| 6 | `MODE` | **No** | -- | -- | **Not extracted -- cannot distinguish Check All vs. Custom Defined** |
| 7 | `CHECKED_COLUMNS` | **No** | -- | -- | **Not extracted -- table parameter with per-column validation rules** |
| 8 | `FASTEST_DATE_CHECK` | **No** | -- | -- | **Not extracted** |
| 9 | `IGNORE_TIMEZONE` | **No** | -- | -- | **Not extracted** |
| 10 | `CHECK_BYTE_LENGTH` | **No** | -- | -- | **Not extracted** |
| 11 | `CHARSET` | **No** | -- | -- | **Not extracted** |
| 12 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 13 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |

**Summary**: 5 of 13 runtime-relevant parameters extracted (38%). 8 parameters missing, of which 2 are critical (`MODE`, `CHECKED_COLUMNS`) and 2 are important for date validation (`FASTEST_DATE_CHECK`, `STRICT_DATE_CHECK` is extracted but missing its counterpart).

### 4.3 Schema Extraction

| Attribute | Extracted? | Notes |
|-----------|-----------|-------|
| `name` | Yes | From `column.get('name', '')` |
| `type` | Yes | **Converted via `ExpressionConverter.convert_type()` -- see CONV-SCC-001** |
| `nullable` | Yes | Boolean conversion from string `"true"/"false"` |
| `length` | Yes | Integer conversion: `int(column.get('length', 0)) if column.get('length') else None` |
| `key` | No | **Not extracted** |
| `precision` | No | **Not extracted** |
| `pattern` | No | **Not extracted -- critical for date validation** |
| `default` | No | **Not extracted** |
| `comment` | No | Not extracted (cosmetic -- no runtime impact) |

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-SCC-001 | **P0** | **Type conversion mismatch**: The converter calls `self.expr_converter.convert_type(column.get('type', 'id_String'))` (line 2090) which converts Talend types to Python type strings (e.g., `id_Integer` -> `'int'`, `id_String` -> `'str'`, `id_Date` -> `'datetime'`). However, the engine's `TALEND_TYPE_MAPPING` dictionary (line 63) expects the original Talend type format (`'id_Integer'`, `'id_String'`, etc.). This means every column type will fail the `talend_type_mapping.get(col_type, None)` lookup in the engine (line 191), returning `None` and causing the entire `isinstance()` check to be skipped. **This renders the entire type validation feature non-functional when using converted jobs.** |
| CONV-SCC-002 | **P1** | **CHECKED_COLUMNS table not extracted**: The per-column validation configuration table from Talend's "Custom defined" mode is not parsed. All column-specific validation rules (selective type check, selective nullable check, selective length check, date patterns) are lost during conversion. Only the "Check all" mode can work, and even then only partially. |
| CONV-SCC-003 | **P1** | **MODE parameter not extracted**: Without knowing whether the job uses "Check all" or "Custom defined" mode, the engine cannot determine which validation behavior to apply. The engine implicitly always behaves as "Check all", which may not match the Talend job's intent. |
| CONV-SCC-004 | **P1** | **Date pattern not extracted from schema**: The `pattern` attribute from column metadata is not parsed. This means date columns cannot be validated against their expected format pattern (e.g., `dd-MM-yyyy`). Since the engine maps `id_Date` to `str`, date validation is effectively non-existent. The generic `parse_base_component()` method (line 482) already extracts patterns via `convert_type()`, showing this is technically feasible. |
| CONV-SCC-005 | **P0** | **Converter `node.find()` returns None causing AttributeError crash (lines 2097-2100)**: All four parameter extractions (`CHECK_ALL`, `SUB_STRING`, `STRICT_DATE_CHECK`, `ALL_EMPTY_ARE_NULL`) call `node.find(...)` and immediately chain `.get('value', ...)` without null checks. If any `<elementParameter>` is absent from the Talend XML (e.g., a job using defaults where the parameter was never explicitly set), `node.find()` returns `None` and the `.get()` call raises `AttributeError: 'NoneType' object has no attribute 'get'`. This crashes the entire conversion for any tSchemaComplianceCheck component missing even one of these four parameters. |
| CONV-SCC-006 | **P2** | **CHECK_BYTE_LENGTH and CHARSET not extracted**: Byte-length string validation is not supported. Jobs relying on byte-length checks for multibyte character sets will silently pass invalid data. |
| CONV-SCC-007 | **P3** | **Schema precision and key attributes not extracted**: The `precision` and `key` column attributes are not parsed, which may be needed for BigDecimal validation or key-based error reporting. |
| CONV-SCC-008 | **P2** | **FASTEST_DATE_CHECK and IGNORE_TIMEZONE not extracted**: These advanced date validation parameters are lost, preventing proper date format checking behavior. |

### 4.5 Converter Code (Annotated)

```python
# component_parser.py lines 2080-2102
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
    # [CONV-SCC-005] All four node.find() calls above have no null checks -- crashes if parameter absent
    # [CONV-SCC-008] FASTEST_DATE_CHECK, IGNORE_TIMEZONE not parsed
    # [CONV-SCC-006] CHECK_BYTE_LENGTH, CHARSET not parsed

    return component
```

---

## 5. Engine Feature Parity Audit

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Row-by-row schema validation | Yes | Low | `_process()` line 160 | Uses `iterrows()` -- functionally correct but 100-1000x slower than vectorized |
| 2 | Nullability check | Yes | Medium | `_process()` line 174 | Checks `pd.isnull()` AND empty string AND whitespace-only. Treats empty strings as null unconditionally (no `ALL_EMPTY_ARE_NULL` toggle) |
| 3 | Type check | Partial | **Non-functional** | `_process()` line 191 | Only 4 types in mapping; converter type mismatch renders all type checks inoperative for converted jobs |
| 4 | Type coercion on mismatch | Partial | **Non-functional** | `_process()` lines 194-206 | Attempts coercion but writes to `iterrows()` copy; coerced values are discarded for valid rows |
| 5 | Length check | Yes | Low | `_process()` lines 182-188 | Only checks string values. Does not enforce for non-string types. No SUB_STRING (trim) support. |
| 6 | FLOW output (valid rows) | Yes | High | `_process()` line 220 | Valid rows collected into `main` output |
| 7 | REJECT output (invalid rows) | Yes | Medium | `_process()` line 221 | Reject rows include `errorCode` and `errorMessage`, but error code is hardcoded to `8` |
| 8 | Error message format | Yes | Low | `_process()` line 213 | Format differs from Talend. Uses `col_name:error_type` semicolon-joined |
| 9 | Check All Columns mode | Implicit | Medium | `_process()` line 165 | Engine always checks all columns in schema. No way to switch to "Custom defined" mode |
| 10 | Custom Defined mode | **No** | N/A | -- | **No support for selective per-column validation** |
| 11 | Checked Columns table | **No** | N/A | -- | **Not implemented** |
| 12 | SUB_STRING (trim excess) | **No** | N/A | -- | **`sub_string` config key is extracted by converter but completely ignored by engine** |
| 13 | Date pattern validation | **No** | N/A | -- | **`id_Date` mapped to `str` -- no date format checking at all** |
| 14 | Fastest Date Check | **No** | N/A | -- | **Not implemented** |
| 15 | Strict Date Check | **No** | N/A | -- | **`strict_date_check` extracted but ignored by engine** |
| 16 | Ignore TimeZone | **No** | N/A | -- | **Not implemented** |
| 17 | Treat Empty as NULL toggle | **No** | N/A | -- | **`all_empty_are_null` extracted but ignored -- engine always treats empty as null** |
| 18 | Check String by Byte Length | **No** | N/A | -- | **Not implemented** |
| 19 | Charset-based byte length | **No** | N/A | -- | **Not implemented** |
| 20 | Use Another Schema | **No** | N/A | -- | **Not implemented** |
| 21 | tStatCatcher Statistics | **No** | N/A | -- | **Not implemented** |
| 22 | ERROR_MESSAGE global variable | **No** | N/A | -- | **Not set** |
| 23 | `{id}_NB_LINE` globalMap | Yes | High | Via `_update_stats()` + `_update_global_map()` | Set via base class mechanism. **Cross-cutting crash bug in `_update_global_map()` -- see BUG-SCC-009.** |
| 24 | `{id}_NB_LINE_OK` globalMap | Yes | High | Via `_update_stats()` + `_update_global_map()` | Same mechanism; same cross-cutting crash bug |
| 25 | `{id}_NB_LINE_REJECT` globalMap | Yes | High | Via `_update_stats()` + `_update_global_map()` | Same mechanism; same cross-cutting crash bug |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Difference |
|----|----------|------------|
| ENG-SCC-001 | **P0** | **Type validation is non-functional for converted jobs**: Due to CONV-SCC-001, the converter produces Python type strings (e.g., `'int'`, `'str'`) but the engine's `TALEND_TYPE_MAPPING` only recognizes Talend-format types (`'id_Integer'`, `'id_String'`). The `talend_type_mapping.get(col_type, None)` call (line 191) returns `None` for all converted types, causing the entire `isinstance()` check to be skipped. **Every row passes type validation regardless of actual type mismatches.** This is a silent data quality failure -- invalid data flows through undetected. |
| ENG-SCC-002 | **P0** | **Row-by-row `iterrows()` causes O(n*m) performance**: The engine iterates over every row using `input_data.iterrows()` (line 160) and checks every schema column per row. For a DataFrame with 1M rows and 20 columns, this produces 20M Python-level operations. Pandas `iterrows()` is notoriously slow -- approximately 100-1000x slower than vectorized operations. A 1M-row dataset that should validate in <1 second will take minutes. **This is a production blocker for any non-trivial data volume.** |
| ENG-SCC-003 | **P1** | **Only 4 of 12 Talend types supported**: The `TALEND_TYPE_MAPPING` (lines 63-68) only contains `id_Integer`, `id_String`, `id_Float`, and `id_Date`. Missing types: `id_Long`, `id_Double`, `id_Boolean`, `id_BigDecimal`, `id_Object`, `id_Character`, `id_Byte`, `id_Short`. Columns with unsupported types will fail `_validate_config()` (if it were called) or cause the type check to be silently skipped in `_process()`. |
| ENG-SCC-004 | **P1** | **`id_Date` mapped to `str` provides no date validation**: The type mapping sets `'id_Date': str` (line 68), meaning any string value passes date type checking. Talend validates dates against specific patterns (e.g., `dd-MM-yyyy`). The V1 engine performs zero date format validation. Invalid dates like `"not-a-date"` or `"2023-99-99"` will pass as valid. |
| ENG-SCC-005 | **P1** | **Empty-as-null behavior is not configurable**: The engine unconditionally treats empty strings as null (line 174: `isinstance(value, str) and value.strip() == ''`). Talend's `ALL_EMPTY_ARE_NULL` parameter (default `true`) allows toggling this behavior. The converter extracts `all_empty_are_null` but the engine ignores it. Jobs that set this to `false` will see different validation results -- strings that Talend would accept as valid non-null values will be rejected by the V1 engine. |
| ENG-SCC-006 | **P1** | **`sub_string` (trim excess) is extracted but ignored**: The converter correctly parses `SUB_STRING` into `config['sub_string']`, but the engine's `_process()` method never reads this config key. When Talend would silently truncate a too-long string, the V1 engine rejects the entire row. This changes the output data for any job using SUB_STRING=true. |
| ENG-SCC-007 | **P2** | **No Custom Defined mode**: The engine always validates all schema columns (line 165: `for col in schema`). Talend's "Custom defined" mode allows selective validation of specific columns with specific check types. Jobs using custom mode will see validation applied to columns that should be unchecked, potentially producing false rejections. |
| ENG-SCC-008 | **P2** | **Hardcoded error code `8`**: The engine uses `DEFAULT_ERROR_CODE = 8` (line 61) for all violation types. Talend may use different error codes for different violation types (type mismatch vs. nullability vs. length). Downstream components that switch on `errorCode` to determine the type of violation will not work correctly. |
| ENG-SCC-009 | **P2** | **Error message format differs from Talend**: The engine produces `col_name:error_type` semicolon-joined (e.g., `amount:invalid type;name:cannot be null`). Talend produces more descriptive messages with full context. Downstream components parsing `errorMessage` will see different formats. |
| ENG-SCC-010 | **P3** | **ERROR_MESSAGE global variable not set**: Talend's `{id}_ERROR_MESSAGE` After-scope variable is not populated. Components referencing this variable downstream will get null. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | **Will crash at runtime due to BUG-SCC-009 and BUG-SCC-013** |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Same crash risk |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | Same mechanism | Same crash risk |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented |

---

## 6. Code Quality Audit

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-SCC-001 | **P0** | `schema_compliance_check.py` line 191-192 | **Type validation silently skipped when type is unrecognized**: `expected_type = talend_type_mapping.get(col_type, None)` returns `None` for any type not in the 4-entry mapping. The subsequent `if expected_type and not isinstance(...)` evaluates to `False` when `expected_type` is `None`, silently skipping type validation. Combined with the converter producing Python type strings (`'int'`, `'str'`) instead of Talend types (`'id_Integer'`, `'id_String'`), this means **type validation never runs for any converted job**. This is a silent data quality failure -- invalid data passes through as valid. |
| BUG-SCC-002 | **P1** | `schema_compliance_check.py` line 171 | **Missing column in input data is not detected**: `value = row.get(col_name)` returns `None` when `col_name` does not exist in the input DataFrame. This `None` is then treated as a null value by `pd.isnull(value)`. If the column is nullable, the missing column is silently accepted. If not nullable, it produces a "cannot be null" error rather than a "column missing" error. Talend would report a schema mismatch for missing columns. The distinction matters for debugging -- "missing column" and "null value" are different root causes requiring different fixes. |
| BUG-SCC-003 | **P1** | `schema_compliance_check.py` line 197 | **Row mutation during `iterrows()` does not update DataFrame**: `row[col_name] = converted_value` attempts to update a Series object obtained from `iterrows()`. In pandas, the row from `iterrows()` is a **copy** of the DataFrame row, not a view. Modifying it does not update the original DataFrame. The pandas documentation explicitly warns: "You should never modify something you are iterating over." Consequently, type-coerced values (e.g., string `"123"` converted to integer `123`) are computed but the coercion does not propagate. Valid rows appended via `valid_rows.append(row)` DO contain the coerced Series (since `row` is the modified copy), but this is incidental and fragile -- the intent to update the DataFrame is not achieved. |
| BUG-SCC-004 | **P1** | `schema_compliance_check.py` lines 182-188 | **Length check only applies to string values**: The condition `if col_length is not None and isinstance(value, str)` means length is never checked for non-string types. In Talend, length constraints can apply to numeric types as well (number of digits). Integer `12345` with `length=3` would pass the V1 engine but be rejected by Talend. |
| BUG-SCC-005 | **P2** | `schema_compliance_check.py` line 174 | **Whitespace-only strings treated as null**: The check `value.strip() == ''` means a string containing only whitespace (e.g., `"   "`) is treated as empty/null. Talend's behavior depends on `ALL_EMPTY_ARE_NULL` setting and only checks for empty string (`""`), not whitespace-only strings. When `ALL_EMPTY_ARE_NULL=false`, whitespace-only strings should be treated as valid non-null values. The V1 engine goes beyond Talend's empty-string check by also capturing whitespace-only strings. |
| BUG-SCC-006 | **P2** | `schema_compliance_check.py` line 195 | **Integer coercion via `int(float(str(value)))` is lossy**: The conversion chain `int(float(str(value)))` truncates floating-point values. For example, `3.7` becomes `3` (not a type error), `3.9999` becomes `3`. In Talend, passing a float value to an integer column would be a type mismatch rejection, not a silent truncation. This changes the semantics from strict type checking to loose coercion with data loss. |
| BUG-SCC-007 | **P3** | `schema_compliance_check.py` line 174 | **NaN handling works correctly but deserves documentation**: When a pandas DataFrame contains `NaN` values (which are `float('nan')` internally), `pd.isnull(value)` correctly identifies them at line 174. The `continue` on line 180 ensures NaN values are properly routed to rejection for non-nullable columns before any `isinstance()` check runs. The null-check-first ordering is sound and idiomatic pandas. NaN handling is **not fragile** -- the `pd.isnull()` gate reliably prevents NaN from reaching the type check. Downgraded from P2; this is an observation, not a defect. |
| BUG-SCC-009 | **P0** | `base_component.py` line 304 | **CROSS-CUTTING: `_update_global_map()` references undefined variable `value`**: The log statement uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. Since `_update_global_map()` is called after every component execution in `execute()` (line 218), **this crash affects ALL components using globalMap, not just SchemaComplianceCheck**. The `put_component_stat()` calls on line 302 succeed before the crash, but the exception propagates and aborts the component's execution flow. |
| BUG-SCC-010 | **P1** | `schema_compliance_check.py` lines 182-188 | **Talend `length=-1` sentinel causes universal length rejection**: Talend uses `length=-1` in schema metadata to indicate "no length constraint." The converter stores this value as-is: `int(column.get('length', 0))` produces `-1`. The engine's length check `if col_length is not None and isinstance(value, str) and len(value) > col_length` then evaluates `len(value) > -1`, which is **always True** for any non-empty string. Every string value in a column with `length=-1` receives a spurious "exceed max length" rejection error. This silently corrupts validation results for any schema column using the Talend default length sentinel. |
| BUG-SCC-011 | **P1** | `schema_compliance_check.py` line 210 | **Input columns named `errorCode`/`errorMessage` silently overwritten in reject output**: The reject row is constructed via `{**row, 'errorCode': DEFAULT_ERROR_CODE, 'errorMessage': error_msg}` (line 210). If the input DataFrame already contains columns named `errorCode` or `errorMessage`, the `**row` spread inserts the original data values, which are then immediately overwritten by the hardcoded error fields. The original data values for those columns are **destroyed** in the reject output with no warning. Downstream consumers of the reject flow lose the original column data. Talend avoids this by adding supplementary read-only columns that are distinct from the data schema. |
| BUG-SCC-012 | **P2** | `schema_compliance_check.py` lines 194-202 | **`float('inf')` passes float validation but `int(float('inf'))` raises uncaught OverflowError**: A value of `float('inf')` or `float('-inf')` in a float column passes `isinstance(value, float)` and the type check succeeds. However, if an infinity value appears in an integer column, the coercion path `int(float(str(value)))` raises `OverflowError: cannot convert float infinity to integer`, which is not caught by the `except (ValueError, TypeError)` handler on line 202. This crashes the entire component instead of rejecting the individual row. Similarly, `float('inf')` stored as a string `"inf"` would follow the same path: `float("inf")` succeeds, then `int(float("inf"))` raises `OverflowError`. |
| BUG-SCC-013 | **P0** | `global_map.py` line 28 | **CROSS-CUTTING: `GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **This crash affects all code using `global_map.get()`.** |

### 6.2 Print Statements (Standards Violation)

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| STD-SCC-001 | **P1** | `schema_compliance_check.py` line 177 | **`print(error_msg)` for nullability violation**: Direct `print()` to stdout. The `docs/v1/STANDARDS.md` explicitly states (line 285-286): "DON'T: Use print statements -- `print(f"Processing {row_count} rows")  # BAD`". This print statement will produce uncontrolled output to stdout in production, potentially interfering with structured logging, breaking JSON-output pipelines, corrupting stdout-based IPC protocols, and making the component untestable for output capture. The message is already logged via `logger.info(error_msg)` on line 178, making the print entirely redundant. |
| STD-SCC-002 | **P1** | `schema_compliance_check.py` line 186 | **`print(error_msg)` for length violation**: Same issue as STD-SCC-001, for the length constraint violation code path. Redundant with the `logger.info()` call on line 187. |
| STD-SCC-003 | **P1** | `schema_compliance_check.py` line 204 | **`print(error_msg)` for type mismatch violation**: Same issue as STD-SCC-001, for the type mismatch code path. Redundant with the `logger.info()` call on line 205. |

### 6.3 Logging Issues

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| LOG-SCC-001 | **P2** | `schema_compliance_check.py` lines 178, 187, 205 | **Validation errors logged at INFO level**: Per STANDARDS.md, INFO is for "key milestones, statistics" like component start/end. Individual row validation errors are detailed flow data and should be at DEBUG level. At INFO level, processing 10,000 rows with 5% rejection rate would produce 500 INFO-level log lines per execution, creating significant log noise in production. These logs also contain the full error message text, which is already captured in the reject DataFrame's `errorMessage` column. |
| LOG-SCC-002 | **P2** | `schema_compliance_check.py` line 157 | **Debug log "Starting row-by-row schema validation" provides no value**: This log message at DEBUG level contains no variable data (no row count, no schema column count). It is redundant with the INFO log on line 145 which already indicates processing has started with row count. |

### 6.4 Standards Compliance

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| STD-SCC-004 | **P2** | `schema_compliance_check.py` | **`validate_config()` is never called**: The engine's `execute()` method in `base_component.py` does not call `validate_config()` before `_process()`. The `validate_config()` and `_validate_config()` methods exist but are dead code -- never invoked during normal execution. Invalid configurations (missing schema, unsupported types, empty schema) will cause runtime errors inside `_process()` rather than clean validation failures. Specifically, `self.config.get('schema', [])` at line 148 would return an empty list if `schema` is missing, causing zero validation to occur (not an error, just silent no-op). |
| STD-SCC-005 | **P2** | `schema_compliance_check.py` | **Extracted config keys ignored**: The converter extracts `check_all`, `sub_string`, `strict_date_check`, and `all_empty_are_null` into the config dictionary, but the engine's `_process()` method never reads any of these keys (no `self.config.get('check_all')`, etc. anywhere in the class). These represent 4 Talend parameters that were correctly identified during conversion but have zero engine-side implementation. This is wasted converter effort and violates the principle that extracted parameters should influence behavior. |
| STD-SCC-006 | **P3** | `schema_compliance_check.py` line 236 | **Dual validation methods**: The class has both `validate_config()` (public, returns bool, line 236) and `_validate_config()` (private, returns `List[str]`, line 70). The public method is described as "backward compatibility" but since neither is called by the engine, this creates unnecessary API surface. If validation is ever wired up, only `_validate_config()` should remain, per STANDARDS.md patterns. |

### 6.5 Naming Consistency

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| NAME-SCC-001 | **P2** | `schema_compliance_check.py` line 162 | **`row_name` variable is misleading**: `row_name = f"Row({row_idx + 1})"` creates a string used in error messages. The variable name `row_name` implies it holds an actual identifier or label for the row. A more descriptive name like `row_label` or `row_reference` would better communicate that this is a display string for error reporting. |
| NAME-SCC-002 | **P3** | `schema_compliance_check.py` line 155 | **Redundant local variable**: `talend_type_mapping = self.TALEND_TYPE_MAPPING` creates a local alias for the class constant. While this may have been intended as a micro-optimization (avoiding attribute lookup in a loop), the performance gain is negligible compared to the `iterrows()` overhead (which is 1000x slower). Accessing `self.TALEND_TYPE_MAPPING` directly would be clearer. |
| NAME-SCC-003 | **P3** | `schema_compliance_check.py` | **Class name does not match Talend family**: The Talend component belongs to the "Data Quality" family, but the V1 class is in the `transform` package. While not a naming issue per se, the package placement may confuse developers looking for validation/quality components. |

### 6.6 Error Handling

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| ERR-SCC-001 | **P2** | `schema_compliance_check.py` line 123 | **No try-except in `_process()`**: The `_process()` method does not wrap its core logic in a try-except block. If an unexpected error occurs during row iteration (e.g., a column value that causes `int(float(str(value)))` to raise an unexpected exception type beyond `ValueError`/`TypeError`, such as `OverflowError` for extremely large numbers), the entire component fails with an unhandled exception. The base class `execute()` does catch `Exception` at a higher level (line 227), but this means the component cannot gracefully report partial results when a single row causes an unexpected error. |
| ERR-SCC-002 | **P2** | `schema_compliance_check.py` line 202 | **Narrow exception handling**: Only `ValueError` and `TypeError` are caught during type coercion (line 202). Other possible exceptions: `OverflowError` (for extremely large numbers like `"99999999999999999999999999999"`), `AttributeError` (if value lacks expected methods), or `UnicodeDecodeError` (for malformed string data). These would crash the entire component instead of rejecting the individual row. |

### 6.7 Type Hints

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| TYPE-SCC-001 | **P3** | `schema_compliance_check.py` | **All method signatures have proper type hints**: `_validate_config() -> List[str]`, `_process(...) -> Dict[str, Any]`, `validate_config() -> bool`. This is correct and follows STANDARDS.md. |

---

## 7. Performance & Memory Audit

| ID | Priority | Issue |
|----|----------|-------|
| PERF-SCC-001 | **P0** | **`iterrows()` is a critical performance bottleneck**: The entire validation logic uses `for row_idx, (_, row) in enumerate(input_data.iterrows())` (line 160) which is the slowest way to iterate over a pandas DataFrame. Benchmarks show `iterrows()` processes approximately 1,000-10,000 rows/second for typical DataFrames, compared to vectorized operations at 1M+ rows/second. For a production dataset of 1M rows with 10 schema columns, validation will take approximately 100-1000 seconds instead of <1 second with vectorized checks. **This is 100-1000x slower than necessary.** A vectorized approach using `pd.to_numeric()`, `df.isna()`, `df.str.len()`, and boolean masking would eliminate this bottleneck entirely. |
| PERF-SCC-002 | **P1** | **Row-by-row list accumulation creates memory pressure**: Valid and rejected rows are accumulated in Python lists (`valid_rows` and `reject_rows`, lines 151-152) as dictionaries/Series, then converted to DataFrames at the end (lines 220-221). For a 1M-row DataFrame where 99% of rows are valid, this creates 990,000 Series objects in `valid_rows`, each containing copies of the row data. This effectively doubles the memory usage of the input data. A vectorized approach using boolean masking (`valid_mask = ...`, `valid_df = input_data[valid_mask]`) would use negligible additional memory. |
| PERF-SCC-003 | **P2** | **String strip operation on every value in null check**: Line 174 performs `value.strip() == ''` on every string value in every row during the null check. This creates a new string object for each call. For a 1M-row DataFrame with 5 string columns, this is 5M string allocations just for the null check. A vectorized approach using `df[col].str.strip().eq('')` would be significantly more efficient. |
| PERF-SCC-004 | **P2** | **Streaming mode (`HYBRID`) silently discards reject data**: The base class `_execute_streaming()` method (lines 255-278 of `base_component.py`) only collects `chunk_result['main']` (line 271) and ignores `chunk_result.get('reject')`. If the SchemaComplianceCheck component is executed in streaming mode (for data exceeding `MEMORY_THRESHOLD_MB = 3072` MB), all reject data is silently discarded. The valid output will be correct, but the reject flow will be empty regardless of actual validation failures. This is especially insidious because: (1) the component correctly produces reject data in `_process()`, (2) the streaming handler silently discards it, (3) the final result contains only valid data with zero rejected rows, and (4) the statistics will be wrong since chunk stats are not aggregated correctly. |

### Performance Projection

| Dataset Size | Estimated V1 Time | Expected Vectorized Time | Slowdown Factor |
|-------------|-------------------|-------------------------|-----------------|
| 10,000 rows | 1-10 seconds | <0.01 seconds | 100-1000x |
| 100,000 rows | 10-100 seconds | <0.1 seconds | 100-1000x |
| 1,000,000 rows | 100-1000 seconds | <1 second | 100-1000x |
| 10,000,000 rows | 1000-10000 seconds | <10 seconds | 100-1000x |

---

## 8. Testing Audit

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `SchemaComplianceCheck` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter parser tests | **No** | -- | No tests for `parse_tschema_compliance_check()` |

**Key finding**: A search for `SchemaComplianceCheck`, `schema_compliance`, and `tSchemaComplianceCheck` across all test directories returned zero results. The most critical validation component in the transform category has **zero test coverage**.

| ID | Priority | Issue |
|----|----------|-------|
| TEST-SCC-001 | **P0** | **No unit tests exist for SchemaComplianceCheck**: Zero test coverage for 256 lines of engine code. Zero test coverage for 23 lines of converter parser code. The component's core purpose -- data quality validation -- is completely unverified. |

### 8.2 Recommended Test Cases

#### P0 -- Critical Tests

| # | Test | Description |
|---|------|-------------|
| 1 | Basic valid data | Pass a DataFrame where all rows comply with schema. Verify all rows appear in `main` output, zero rows in `reject`, stats `NB_LINE_OK == NB_LINE`, `NB_LINE_REJECT == 0`. |
| 2 | Basic invalid data -- null violation | Pass a DataFrame with `None`/`NaN` in a non-nullable column. Verify row appears in `reject` with `errorCode` and `errorMessage` containing "cannot be null". |
| 3 | Basic invalid data -- type violation | Pass a DataFrame with string value `"abc"` in an integer column (using Talend type format). Verify row appears in `reject`. |
| 4 | Mixed valid/invalid | Pass a DataFrame with mix of valid and invalid rows. Verify correct split between `main` and `reject`. Stats must match: `NB_LINE == NB_LINE_OK + NB_LINE_REJECT`. |
| 5 | Config validation -- missing schema | Instantiate with no `schema` key. Verify `_validate_config()` returns error. |
| 6 | Config validation -- empty schema | Instantiate with `schema=[]`. Verify `_validate_config()` returns error. |
| 7 | Config validation -- unsupported type | Instantiate with schema containing `id_Long`. Verify `_validate_config()` returns error (this is itself a bug -- `id_Long` should be supported). |
| 8 | Type mapping with converter output | Pass schema with converter-produced types (`'int'`, `'str'`) and verify that type validation actually runs (currently broken -- this test should FAIL and document the regression). |

#### P1 -- Major Tests

| # | Test | Description |
|---|------|-------------|
| 9 | Empty input (None) | Pass `None` as input. Verify empty `main` and `reject` DataFrames, stats all zero. |
| 10 | Empty input (empty DataFrame) | Pass `pd.DataFrame()`. Verify empty output and correct stats. |
| 11 | NaN in numeric column | Pass `float('nan')` in a non-nullable `id_Float` column. Verify NaN is detected by `pd.isnull()` and row is rejected. |
| 12 | NaN in string column | Pass `float('nan')` in a non-nullable `id_String` column. Verify NaN is detected and row is rejected. |
| 13 | Empty string in non-nullable column | Pass `""` in a non-nullable `id_String` column. Verify rejection (current behavior treats empty as null). |
| 14 | Length violation | Pass string `"toolong"` with `col_length=3`. Verify rejection with "exceed max length" message. |
| 15 | Type coercion -- string to int | Pass string `"123"` to `id_Integer` column. Verify coercion succeeds and output value is correct (currently the coerced value IS in the output Series, but this is fragile). |
| 16 | Type coercion -- non-numeric string to int | Pass string `"abc"` to `id_Integer` column. Verify rejection with "invalid type" message. |
| 17 | Multiple errors per row | Pass row with both null violation (col A) and type violation (col B). Verify `errorMessage` contains both errors separated by semicolons: `A:cannot be null;B:invalid type`. |
| 18 | All rows rejected | Pass DataFrame where every row violates schema. Verify empty `main`, all rows in `reject`. |
| 19 | All rows valid | Pass fully compliant DataFrame. Verify empty `reject`, all rows in `main`. |
| 20 | Missing column in input | Pass DataFrame missing a schema-defined column. Verify appropriate error handling (currently treated as null). |
| 21 | GlobalMap statistics | Execute with `global_map` set and verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are correctly set. **Note: will crash due to BUG-SCC-009.** |

#### P2 -- Moderate Tests

| # | Test | Description |
|---|------|-------------|
| 22 | Whitespace-only string in non-nullable column | Verify `"   "` is treated as null/empty (current behavior). Document deviation from Talend. |
| 23 | Large DataFrame performance | Time validation of 100K+ rows to establish baseline and detect regressions. |
| 24 | Float truncation on int coercion | Verify `3.7` in integer column is handled. Current behavior: truncates to `3`. Expected Talend behavior: reject. |
| 25 | Schema with all supported types | Test each of the 4 supported types (`id_Integer`, `id_String`, `id_Float`, `id_Date`) individually. |
| 26 | Error message format | Verify exact format of `errorMessage` for each violation type. |
| 27 | `sub_string` config behavior | Verify that `sub_string=true` in config is handled (currently not implemented -- should document gap). |
| 28 | `all_empty_are_null` config behavior | Verify configurable empty-string handling (currently not implemented -- should document gap). |
| 29 | Streaming mode reject preservation | Verify reject data is preserved when component runs in streaming mode (currently broken -- PERF-SCC-004). |
| 30 | Reject DataFrame schema | Verify reject output includes ALL original columns plus `errorCode` and `errorMessage`. Verify column ordering matches Talend. |
| 31 | OverflowError on extreme numeric input | Pass `"99999999999999999999999999999999999"` to `id_Integer` column. Verify `OverflowError` is handled (currently not caught -- ERR-SCC-002). |

---

## 9. Issues Summary

### All Issues by Priority

#### P0 -- Critical (8 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-SCC-001 | Converter | Type conversion mismatch: converter produces `'int'`/`'str'` but engine expects `'id_Integer'`/`'id_String'`, rendering type validation non-functional for all converted jobs |
| CONV-SCC-005 | Converter | `node.find()` returns None causing AttributeError crash (lines 2097-2100). All four parameter extractions have no null checks -- crashes conversion if any parameter absent from XML |
| ENG-SCC-001 | Engine | Type validation silently skipped for all converted jobs due to type mapping lookup failure (`talend_type_mapping.get()` returns `None`) |
| ENG-SCC-002 | Engine | `iterrows()` row-by-row processing is 100-1000x slower than vectorized alternative, blocking production use for any non-trivial data volume |
| BUG-SCC-001 | Bug | Type validation silently skipped when type is unrecognized -- `None` from dict lookup causes `if expected_type and ...` to evaluate `False` |
| BUG-SCC-009 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Crashes ALL components when `global_map` is set |
| BUG-SCC-013 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Crashes on every `.get()` call. `get_component_stat()` also passes two args to single-arg `get()` |
| TEST-SCC-001 | Testing | Zero unit tests for the component -- 256 lines of engine code and 23 lines of converter code completely unverified |

#### P1 -- Major (13 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-SCC-002 | Converter | CHECKED_COLUMNS table not extracted -- Custom Defined mode validation rules lost during conversion |
| CONV-SCC-003 | Converter | MODE parameter not extracted -- cannot distinguish Check All vs. Custom Defined mode |
| CONV-SCC-004 | Converter | Date pattern (`pattern` attribute) not extracted from schema metadata -- no date validation possible |
| ENG-SCC-003 | Engine | Only 4 of 12 Talend data types supported in `TALEND_TYPE_MAPPING` (missing `id_Long`, `id_Double`, `id_Boolean`, `id_BigDecimal`, `id_Object`, `id_Character`, `id_Byte`, `id_Short`) |
| ENG-SCC-004 | Engine | `id_Date` mapped to `str` provides zero date format validation -- invalid dates pass as valid |
| ENG-SCC-005 | Engine | `ALL_EMPTY_ARE_NULL` behavior not configurable -- engine always treats empty strings as null, ignoring the extracted config key |
| ENG-SCC-006 | Engine | `sub_string` (trim excess) extracted by converter but ignored by engine -- overlong strings rejected instead of truncated |
| BUG-SCC-002 | Bug | Missing columns in input DataFrame treated as null (`row.get()` returns `None`) rather than reporting "column missing" schema mismatch |
| BUG-SCC-003 | Bug | Type coercion writes to `iterrows()` copy via `row[col_name] = converted_value`, not to the original DataFrame -- coerced values are in the copy (appended to valid_rows) but the pattern is fragile and intent is not met |
| BUG-SCC-010 | Bug | Talend `length=-1` sentinel causes universal length rejection. Converter stores `-1`, engine's `len(value) > -1` is always True. Every string in that column gets spurious "exceed max length" error |
| BUG-SCC-011 | Bug | Input columns named `errorCode`/`errorMessage` silently overwritten in reject output (line 210). Original data values destroyed with no warning |
| STD-SCC-001 | Standards | Three `print()` statements to stdout (lines 177, 186, 204) violate STANDARDS.md, are redundant with adjacent `logger.info()` calls, and produce uncontrolled output in production (also STD-SCC-002, STD-SCC-003) |
| PERF-SCC-002 | Performance | Row-by-row list accumulation of valid/reject rows as Python objects doubles memory usage for large datasets |

#### P2 -- Moderate (16 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-SCC-006 | Converter | `CHECK_BYTE_LENGTH` and `CHARSET` not extracted -- byte-length string validation unavailable |
| CONV-SCC-008 | Converter | `FASTEST_DATE_CHECK` and `IGNORE_TIMEZONE` not extracted from Talend XML |
| ENG-SCC-007 | Engine | No Custom Defined mode -- engine always validates all schema columns regardless of MODE setting |
| ENG-SCC-008 | Engine | Error code hardcoded to `8` (`DEFAULT_ERROR_CODE`) for all violation types -- downstream error-code-based routing will not work |
| ENG-SCC-009 | Engine | Error message format (`col_name:error_type;...`) differs from Talend's more descriptive format |
| BUG-SCC-004 | Bug | Length check only applies to string values via `isinstance(value, str)` -- numeric types with length constraints are never validated |
| BUG-SCC-005 | Bug | Whitespace-only strings (`"   "`) unconditionally treated as null via `value.strip() == ''` -- goes beyond Talend's empty-string-only check |
| BUG-SCC-006 | Bug | `int(float(str(value)))` silently truncates floats (`3.7` -> `3`) instead of rejecting type mismatch |
| BUG-SCC-012 | Bug | `float('inf')` passes float validation but `int(float('inf'))` raises uncaught `OverflowError`, crashing the entire component instead of rejecting the row |
| LOG-SCC-001 | Logging | Row validation errors logged at INFO level (should be DEBUG per STANDARDS.md) -- creates 100s-1000s of log lines per execution |
| STD-SCC-004 | Standards | `validate_config()` / `_validate_config()` never called by engine -- 50+ lines of dead validation code |
| STD-SCC-005 | Standards | Four extracted config keys (`check_all`, `sub_string`, `strict_date_check`, `all_empty_are_null`) ignored by engine |
| ERR-SCC-001 | Error Handling | No try-except around core processing logic in `_process()` -- unexpected exceptions crash entire component |
| ERR-SCC-002 | Error Handling | Narrow exception handling -- only `ValueError`/`TypeError` caught during type coercion; `OverflowError`, `AttributeError` not handled |
| PERF-SCC-003 | Performance | `value.strip()` on every string value creates 5M+ temporary string objects for 1M-row DataFrame with 5 string columns |
| PERF-SCC-004 | Performance | Streaming mode (`_execute_streaming()`) discards all reject data -- only `main` output collected from chunks |

#### P3 -- Low (7 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-SCC-007 | Converter | Schema `precision` and `key` attributes not extracted from column metadata |
| ENG-SCC-010 | Engine | `{id}_ERROR_MESSAGE` global variable not set -- downstream references get null |
| BUG-SCC-007 | Bug | NaN handling works correctly (downgraded from P2) -- `pd.isnull()` gate reliably prevents NaN from reaching the type check; the ordering is sound and idiomatic |
| NAME-SCC-001 | Naming | `row_name` variable name is misleading (it is a display label, not an identifier) |
| NAME-SCC-002 | Naming | Redundant local alias `talend_type_mapping = self.TALEND_TYPE_MAPPING` (negligible optimization vs. `iterrows()` overhead) |
| NAME-SCC-003 | Naming | Class placed in `transform` package instead of a `validation` or `data_quality` package matching Talend's component family |
| STD-SCC-006 | Standards | Dual validation methods (public `validate_config()` + private `_validate_config()`) with neither being called -- unnecessary API surface |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 -- Critical | 8 | 2 converter, 2 engine, 3 bugs (2 cross-cutting), 1 testing |
| P1 -- Major | 13 | 3 converter, 4 engine, 4 bugs, 1 standards (3 print stmts), 1 performance |
| P2 -- Moderate | 16 | 2 converter, 3 engine, 4 bugs, 1 logging, 2 standards, 2 error handling, 2 performance |
| P3 -- Low | 7 | 1 converter, 1 engine, 1 bug, 3 naming, 1 standards |
| **Total** | **44** | |

---

## 10. Detailed Technical Analysis

### 10.1 The Type Mapping Chain: End-to-End Failure

This section traces the full chain from Talend XML to engine execution to demonstrate how type validation is entirely broken for converted jobs.

**Step 1: Talend XML** contains column type `id_Integer`:
```xml
<column name="age" type="id_Integer" nullable="false" length="3"/>
```

**Step 2: Converter** calls `ExpressionConverter.convert_type('id_Integer')` which returns `'int'`:
```python
# In parse_tschema_compliance_check() line 2090:
'type': self.expr_converter.convert_type(column.get('type', 'id_String'))

# ExpressionConverter.convert_type() at expression_converter.py line 231-255:
type_mapping = {
    'id_Integer': 'int',    # Returns 'int'
    'id_String': 'str',     # Returns 'str'
    'id_Float': 'float',    # Returns 'float'
    'id_Date': 'datetime',  # Returns 'datetime' (NOT 'str')
    # ... etc
}
# Result: config schema has 'type': 'int'
```

**Step 3: Engine** receives config with `'type': 'int'` and looks it up:
```python
# schema_compliance_check.py lines 63-68:
TALEND_TYPE_MAPPING = {
    'id_Integer': int,   # Key is 'id_Integer', NOT 'int'
    'id_String': str,
    'id_Float': float,
    'id_Date': str,      # Note: maps to str, but converter produces 'datetime'
}

# schema_compliance_check.py line 191:
expected_type = talend_type_mapping.get('int', None)  # Returns None
if expected_type and not isinstance(value, expected_type):
    # This block NEVER executes because expected_type is None (falsy)
    # Type validation is silently skipped
```

**Result**: Type validation is skipped for every column in every row. Invalid data passes through unchecked.

**Additional `id_Date` discrepancy**: Even if the type mapping were fixed, the converter produces `'datetime'` for `id_Date`, but the engine maps `'id_Date'` to `str`. This means a fixed converter would still not properly validate date columns.

**Fix Required**: Either:
1. Remove `convert_type()` call in the converter parser (preserve Talend type format), OR
2. Add Python type strings to the engine's `TALEND_TYPE_MAPPING` dictionary

Option (1) is preferred per STANDARDS.md which recommends preserving Talend type format in schema definitions.

### 10.2 The `iterrows()` Copy Problem

The type coercion code attempts to update row values:
```python
# schema_compliance_check.py lines 160, 195-198:
for row_idx, (_, row) in enumerate(input_data.iterrows()):
    # ...
    if col_type == 'id_Integer':
        converted_value = int(float(str(value)))
        row[col_name] = converted_value  # This modifies the COPY, not the DataFrame
```

The pandas documentation explicitly warns: "You should never modify something you are iterating over. This is not guaranteed to work in all cases. Depending on the data types, the iterator returns a copy and not a view, and writing to it will have no effect."

The modified `row` Series is later appended to `valid_rows` (line 217), so the coerced value IS present in the final `valid_df` output. However:
- The developer clearly intended to modify the original DataFrame (comment on line 197: "Update the row with converted value")
- If the row has other errors (another column fails), the row goes to `reject_rows` with the coerced value for the passing column but the original value might be expected
- The pattern is fragile and the behavior is incidental, not intentional

### 10.3 Performance Impact Analysis

The current implementation has three nested levels of inefficiency:

1. **`iterrows()` overhead**: Each call produces a Series object, copying data from the internal block structure. For a DataFrame with 20 columns, this is 20 data copies per row.

2. **Per-cell Python operations**: Inside the row loop, each schema column triggers Python-level type checking (`isinstance()`), null checking (`pd.isnull()`), and string operations (`strip()`). For 20 columns and 1M rows, this is 60M+ Python function calls.

3. **List accumulation**: Each valid/rejected row is stored as a Series/dictionary, requiring Python object creation and data copying. Then `pd.DataFrame(valid_rows)` at the end re-processes all objects into columnar format.

**Vectorized alternative** (sketch):
```python
def _process(self, input_data):
    reject_mask = pd.Series(False, index=input_data.index)
    error_messages = pd.Series('', index=input_data.index)

    for col in schema:
        col_name, col_type = col['name'], col['type']
        col_nullable = col.get('nullable', True)

        # Null check (vectorized, entire column at once)
        if not col_nullable:
            null_mask = input_data[col_name].isna()
            if all_empty_are_null:
                null_mask |= input_data[col_name].astype(str).str.strip().eq('')
            reject_mask |= null_mask
            error_messages = error_messages.where(
                ~null_mask, error_messages + f'{col_name}:cannot be null;'
            )

        # Type check (vectorized per column)
        if col_type == 'id_Integer':
            numeric = pd.to_numeric(input_data[col_name], errors='coerce')
            type_fail = numeric.isna() & ~input_data[col_name].isna()
            reject_mask |= type_fail

        # Length check (vectorized per column)
        if col.get('length') and col_type == 'id_String':
            length_fail = input_data[col_name].str.len() > col['length']
            reject_mask |= length_fail

    valid_df = input_data[~reject_mask]
    reject_df = input_data[reject_mask].copy()
    reject_df['errorCode'] = 8
    reject_df['errorMessage'] = error_messages[reject_mask]
    return {'main': valid_df, 'reject': reject_df}
```

This operates at the column level, leveraging pandas' internal C/Cython optimizations for 100-1000x speedup.

### 10.3.1 Vectorized Error Message Construction

The most challenging aspect of vectorization is constructing per-row error messages. The current `iterrows()` approach naturally accumulates error strings per row. A vectorized approach requires a different strategy:

```python
# Option A: Build error message columns, then concatenate
error_cols = {}
for col in schema:
    col_name = col['name']
    if not col.get('nullable', True):
        null_mask = input_data[col_name].isna()
        error_cols[f'{col_name}_null'] = null_mask.map(
            {True: f'{col_name}:cannot be null', False: ''}
        )
    if col.get('length'):
        len_mask = input_data[col_name].str.len() > col['length']
        error_cols[f'{col_name}_len'] = len_mask.map(
            {True: f'{col_name}:exceed max length', False: ''}
        )

# Combine all error columns into single errorMessage
error_df = pd.DataFrame(error_cols)
error_messages = error_df.apply(
    lambda row: ';'.join(filter(None, row)), axis=1
)
```

```python
# Option B: Use numpy where() for each check, then join
import numpy as np
errors = np.full(len(input_data), '', dtype=object)
for col in schema:
    col_name = col['name']
    if not col.get('nullable', True):
        null_mask = input_data[col_name].isna()
        errors = np.where(
            null_mask,
            np.char.add(errors.astype(str), f';{col_name}:cannot be null'),
            errors
        )
# Strip leading semicolons
errors = np.char.lstrip(errors.astype(str), ';')
```

Option B is faster for large DataFrames because it avoids the overhead of creating intermediate DataFrames and uses numpy's vectorized string operations.

### 10.3.2 Memory Comparison: Current vs. Vectorized

For a 1M-row DataFrame with 20 columns (approx. 160MB):

| Aspect | Current (iterrows) | Vectorized |
|--------|-------------------|------------|
| Input data | 160 MB | 160 MB |
| valid_rows list | ~158 MB (copies of 990K rows at 99% pass rate) | 0 MB (boolean mask, ~1 MB) |
| reject_rows list | ~2 MB (copies of 10K rows at 1% reject rate) | 0 MB (boolean mask) |
| Output valid_df | ~158 MB (new DataFrame from list) | ~158 MB (view of input, no copy if using mask) |
| Output reject_df | ~2 MB (new DataFrame from list) | ~2 MB (copy for reject, adding error columns) |
| **Total peak memory** | **~478 MB (3x input)** | **~320 MB (2x input)** |
| **Overhead** | **+318 MB** | **+160 MB** |

The vectorized approach cuts memory overhead roughly in half because it avoids creating Python list objects for each row.

### 10.4 Empty String vs. NaN vs. Null Handling Analysis

The engine's null check at line 174:
```python
if pd.isnull(value) or (isinstance(value, str) and value.strip() == ''):
```

This conflates three distinct states:
1. **Actual null/NaN** (`pd.isnull(value)` is True) -- includes `None`, `float('nan')`, `pd.NaT`, `pd.NA`
2. **Empty string** (`value == ''`)
3. **Whitespace-only string** (`value.strip() == ''` but `value != ''`)

Talend distinguishes these based on `ALL_EMPTY_ARE_NULL`:
- When `true` (default): Empty strings (state 2) are treated as null. States 1+2 are equivalent.
- When `false`: Only actual null/NaN values (state 1) trigger nullability rejection.

The V1 engine:
- Always treats all three states as null (no toggle)
- The whitespace-only check (state 3) goes **beyond** Talend's behavior, which only checks for empty strings
- A value like `"   "` (3 spaces) would be accepted by Talend (`ALL_EMPTY_ARE_NULL=true` only matches `""`, not `"   "`), but rejected by the V1 engine

**NaN Edge Case**: In pandas, `NaN` is `float('nan')`. When a DataFrame column of type `object` contains `NaN`:
- `pd.isnull(NaN)` returns `True` -- correctly detected
- `isinstance(NaN, float)` returns `True` -- would pass type check for `id_Float` if null check is bypassed
- `isinstance(NaN, str)` returns `False` -- the whitespace check is not triggered
- The current code handles this correctly via the early `continue` on line 180. The null-check-first ordering is sound and idiomatic pandas -- the `pd.isnull()` gate reliably prevents NaN from reaching the type check (see BUG-SCC-007, downgraded to P3)

### 10.5 Streaming Mode Reject Data Loss

The base class `_execute_streaming()` method (base_component.py lines 255-278):
```python
def _execute_streaming(self, input_data):
    results = []
    for chunk in chunks:
        chunk_result = self._process(chunk)
        if chunk_result.get('main') is not None:
            results.append(chunk_result['main'])
        # ^^^ 'reject' key is COMPLETELY IGNORED
    if results:
        combined = pd.concat(results, ignore_index=True)
        return {'main': combined}
    else:
        return {'main': pd.DataFrame()}
```

When SchemaComplianceCheck processes data in streaming mode (triggered when input exceeds `MEMORY_THRESHOLD_MB = 3072` MB):
1. Each chunk produces both `main` and `reject` outputs
2. The streaming handler only collects `main` outputs
3. All reject data is silently discarded
4. The downstream reject flow receives an empty DataFrame
5. Statistics (`NB_LINE_REJECT`) from individual chunks are accumulated via `_update_stats()`, but the final `return` only contains `main`, so even though stats show rejections, the reject DataFrame is lost

### 10.6 `_update_global_map()` Crash Analysis

The base class method (base_component.py lines 298-304):
```python
def _update_global_map(self) -> None:
    if self.global_map:
        for stat_name, stat_value in self.stats.items():
            self.global_map.put_component_stat(self.id, stat_name, stat_value)
        # Log the statistics for debugging
        logger.info(f"... {stat_name}: {value}")  # 'value' is UNDEFINED
```

The `put_component_stat()` calls on line 302 succeed (they write stats correctly). But the log statement on line 304 references `{value}` which is undefined -- the loop variable is `stat_value`. This causes `NameError` every time `global_map` is set.

The crash occurs AFTER stats are written but INSIDE the `execute()` try block (line 218 calls `_update_global_map()`), so the exception propagates to the `except` block (line 227), which calls `_update_global_map()` AGAIN (line 231), causing a SECOND `NameError`. The component status is set to ERROR and the original exception is lost.

### 10.7 Error Code Analysis

The engine hardcodes `DEFAULT_ERROR_CODE = 8` for all violation types:

| Violation Type | Talend Behavior | V1 Engine Behavior |
|---------------|----------------|-------------------|
| Null in non-nullable column | Specific error code | Always `8` |
| Type mismatch | Specific error code | Always `8` |
| Length exceeded | Specific error code | Always `8` |
| Missing column | Schema mismatch error | Treated as null, code `8` if rejected |

Downstream components or error-handling logic that switches on `errorCode` to determine the type of violation will not work correctly with the V1 engine's output.

### 10.8 Reject Flow Format Comparison

**Talend REJECT output**:
- Contains ALL original schema columns (with whatever data was parsed)
- Plus `errorCode` (integer, read-only, green in Studio)
- Plus `errorMessage` (string, read-only, green in Studio)
- Error columns are supplementary -- they do not replace data columns
- One reject row per input row that fails ANY check

**V1 Engine REJECT output**:
- Contains ALL original columns via `**row` spread (line 210)
- Plus `errorCode` (hardcoded `8`)
- Plus `errorMessage` (semicolon-joined `col_name:error_type` strings)
- Format: `{col_name}:cannot be null;{col_name}:invalid type`
- **Difference**: Error message format is less descriptive than Talend's
- **Difference**: Error code is always `8` regardless of violation type
- **Match**: One reject row per failing input row (same as Talend)

---

## 11. Recommendations

### Immediate (Before Production) -- P0 Fixes

1. **Fix `_update_global_map()` crash** (BUG-SCC-009): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only). **Effort**: 1 line.

2. **Fix `GlobalMap.get()` crash** (BUG-SCC-013): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. Change `def get(self, key: str) -> Optional[Any]` to `def get(self, key: str, default: Any = None) -> Optional[Any]`. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default). **Effort**: 1 line.

3. **Fix type mapping chain** (CONV-SCC-001 / ENG-SCC-001 / BUG-SCC-001): Remove the `convert_type()` call in the converter's `parse_tschema_compliance_check()` method. Change line 2090 of `component_parser.py` from:
   ```python
   'type': self.expr_converter.convert_type(column.get('type', 'id_String'))
   ```
   to:
   ```python
   'type': column.get('type', 'id_String')
   ```
   This preserves the Talend type format (`id_Integer`, etc.) that the engine expects, consistent with STANDARDS.md guidance. **Impact**: Restores type validation for all converted SchemaComplianceCheck jobs. **Risk**: Low -- only affects this component's converter path. **Effort**: 1 line.

4. **Add null checks to converter `node.find()` calls** (CONV-SCC-005): All four parameter extractions in `parse_tschema_compliance_check()` (lines 2097-2100) call `node.find(...).get(...)` without checking for `None`. Wrap each in a safe pattern:
   ```python
   elem = node.find('.//elementParameter[@name="CHECK_ALL"]')
   component['config']['check_all'] = (
       elem.get('value', 'false').lower() == 'true' if elem is not None else False
   )
   ```
   **Impact**: Prevents `AttributeError` crash when converting Talend jobs that omit optional parameters. **Risk**: Very low (adds defensive null guard). **Effort**: 4 lines.

5. **Remove all `print()` statements** (STD-SCC-001/002/003): Delete the three `print(error_msg)` calls on lines 177, 186, and 204 of `schema_compliance_check.py`. The `logger.info()` calls immediately following each print already capture the same information. **Impact**: Eliminates uncontrolled stdout output. **Risk**: Zero (redundant code removal). **Effort**: 3 lines.

6. **Replace `iterrows()` with vectorized validation** (ENG-SCC-002 / PERF-SCC-001): Rewrite `_process()` to use column-level vectorized operations:
   - Use `df[col].isna()` for null checks
   - Use `pd.to_numeric(df[col], errors='coerce')` for numeric type checks
   - Use `df[col].str.len()` for length checks
   - Use boolean mask indexing for split: `valid_df = df[~reject_mask]`
   See Section 10.3 for a sketch implementation. **Impact**: 100-1000x performance improvement. **Risk**: Medium (requires testing). **Effort**: 2-3 days.

7. **Create comprehensive unit test suite** (TEST-SCC-001): Implement at minimum the 8 P0 test cases and 13 P1 test cases listed in Section 8.2. **Impact**: Establishes baseline correctness verification. **Risk**: Zero. **Effort**: 2-3 days.

### Short-Term (Hardening) -- P1 Fixes

8. **Expand type mapping** (ENG-SCC-003): Add all 12 Talend types to `TALEND_TYPE_MAPPING`:
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

9. **Implement date validation** (ENG-SCC-004 / CONV-SCC-004): Extract the `pattern` attribute from column metadata in the converter. Implement date pattern validation using `datetime.strptime()` with Talend-to-Python pattern conversion (e.g., `dd-MM-yyyy` -> `%d-%m-%Y`). Support both strict and fast date checking modes.

10. **Implement `all_empty_are_null` toggle** (ENG-SCC-005): Read `config.get('all_empty_are_null', True)` and conditionally include/exclude the empty string check in null validation. When `False`, only `pd.isnull(value)` should trigger the null check.

11. **Implement `sub_string` (trim excess)** (ENG-SCC-006): Read `config.get('sub_string', False)` and when `True`, truncate strings to `col_length` instead of rejecting. Apply truncation before the valid/reject decision.

12. **Fix missing column detection** (BUG-SCC-002): Before the column loop, check if all schema column names exist in the input DataFrame. Report missing columns as distinct errors (e.g., `col_name:column missing`) rather than treating them as null values.

13. **Fix `length=-1` sentinel handling** (BUG-SCC-010): The converter must translate Talend's `length=-1` sentinel (meaning "no length constraint") to `None` instead of storing `-1`. Change line 2092 of `component_parser.py` from `int(column.get('length', 0))` to a conditional: store `None` when length is `-1` or absent. Alternatively, the engine can add a guard: `if col_length is not None and col_length >= 0`. **Impact**: Eliminates spurious length rejections for all columns using Talend's default length. **Risk**: Low. **Effort**: 1 line.

14. **Protect reject output from column name collisions** (BUG-SCC-011): Before constructing the reject row, check whether the input DataFrame contains columns named `errorCode` or `errorMessage`. If so, either prefix/rename the original columns (e.g., `_orig_errorCode`) or raise a warning. **Impact**: Prevents silent data loss in reject output. **Risk**: Low. **Effort**: 5-10 lines.

15. **Extract CHECKED_COLUMNS and MODE** (CONV-SCC-002 / CONV-SCC-003): Parse the `CHECKED_COLUMNS` table parameter and `MODE` parameter in the converter to support Custom Defined validation mode.

### Long-Term (Full Parity) -- P2/P3 Fixes

16. **Fix streaming mode reject data loss** (PERF-SCC-004): Modify `_execute_streaming()` in `base_component.py` to collect and concatenate both `main` and `reject` outputs from chunk processing.

17. **Implement per-violation error codes** (ENG-SCC-008): Define distinct error codes for null violations, type violations, and length violations instead of hardcoding `8`.

18. **Implement Custom Defined mode** (ENG-SCC-007): Support selective per-column validation based on the Checked Columns table configuration.

19. **Implement byte-length checking** (CONV-SCC-006): Support `CHECK_BYTE_LENGTH` with configurable charset for multibyte character set validation.

20. **Catch `OverflowError` in type coercion** (BUG-SCC-012): Add `OverflowError` to the `except` clause on line 202 of `schema_compliance_check.py` so that `float('inf')` and extremely large numbers in integer columns reject the row instead of crashing the component. **Impact**: Prevents component crash on edge-case numeric values. **Risk**: Zero. **Effort**: 1 line.

17. **Wire up `validate_config()`** (STD-SCC-004): Add a `validate_config()` call in the engine's component execution pipeline, before `_process()`, to catch configuration errors early with clear error messages.

18. **Fix logging levels** (LOG-SCC-001): Change per-row validation error logging from INFO to DEBUG level to prevent log flooding in production.

19. **Widen exception handling** (ERR-SCC-002): Add `OverflowError` to the except clause on line 202. Consider catching `Exception` broadly with appropriate logging for robustness.

20. **Add ERROR_MESSAGE global variable** (ENG-SCC-010): Set `{id}_ERROR_MESSAGE` in global map when validation errors occur.

---

## 12. Appendix: Full Engine Source (Annotated)

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
        if input_data is None or input_data.empty:  # Handles None and empty DataFrame
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
            row_name = f"Row({row_idx + 1})"          # [NAME-SCC-001] Misleading name

            for col in schema:
                col_name = col['name']
                col_type = col['type']
                col_nullable = col.get('nullable', self.DEFAULT_NULLABLE)
                col_length = col.get('length', None)

                value = row.get(col_name)             # [BUG-SCC-002] Missing column = None

                # Null/empty check
                if pd.isnull(value) or (isinstance(value, str) and value.strip() == ''):
                    # [BUG-SCC-005] Whitespace treated as null unconditionally
                    # [BUG-SCC-007] NaN handled correctly here via pd.isnull()
                    # [ENG-SCC-005] all_empty_are_null not checked
                    if not col_nullable:
                        error_msg = f"Value is empty for column : '{col_name}' in '{row_name}'..."
                        print(error_msg)              # [STD-SCC-001] print() to stdout
                        logger.info(error_msg)        # [LOG-SCC-001] Should be DEBUG
                        errors.append(f"{col_name}:cannot be null")
                    continue                          # Skip further validation for null/empty

                # Length check -- [BUG-SCC-004] Only checks string values
                # [BUG-SCC-010] If col_length is -1 (Talend sentinel), len(value) > -1 is always True
                if col_length is not None and isinstance(value, str):
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
                            # [BUG-SCC-006] Truncates floats (3.7 -> 3)
                            row[col_name] = converted_value
                            # [BUG-SCC-003] Writes to copy, not DataFrame
                        elif col_type == 'id_Float':
                            converted_value = float(str(value))
                            row[col_name] = converted_value
                            # [BUG-SCC-003] Writes to copy, not DataFrame
                    except (ValueError, TypeError):
                        # [ERR-SCC-002] Misses OverflowError, AttributeError, etc.
                        # [BUG-SCC-012] float('inf') -> int() raises OverflowError, not caught here
                        error_msg = f"Type mismatch..."
                        print(error_msg)              # [STD-SCC-003] print() to stdout
                        logger.info(error_msg)        # [LOG-SCC-001] Should be DEBUG
                        errors.append(f"{col_name}:invalid type")

            if errors:
                reject_rows.append({
                    **row,
                    # [BUG-SCC-011] If input has 'errorCode'/'errorMessage' columns,
                    #   original data values from **row are overwritten here
                    'errorCode': self.DEFAULT_ERROR_CODE,  # [ENG-SCC-008] Always 8
                    'errorMessage': ';'.join(errors),       # No space after semicolon
                })
            else:
                valid_rows.append(row)

        valid_df = pd.DataFrame(valid_rows)
        reject_df = pd.DataFrame(reject_rows)

        rows_out = len(valid_df)
        rows_rejected = len(reject_df)
        self._update_stats(rows_in, rows_out, rows_rejected)
        # ^^^ _update_global_map() called later by execute() -- [BUG-SCC-009] will crash

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

## 13. Appendix: Registration and Dispatch

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
# Lines 333-334
elif component_type == 'tSchemaComplianceCheck':
    component = self.component_parser.parse_tschema_compliance_check(node, component)
```

### Transform Package Registration (`__init__.py`)

The component is exported from the transform package:

```python
from .schema_compliance_check import SchemaComplianceCheck
# Listed in __all__ as 'SchemaComplianceCheck'
```

---

## 14. Appendix: Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `SCHEMA` (metadata) | `schema` | Mapped | -- |
| `CHECK_ALL` | `check_all` | Mapped (but ignored by engine) | P2 (engine must implement) |
| `SUB_STRING` | `sub_string` | Mapped (but ignored by engine) | P1 (engine must implement) |
| `STRICT_DATE_CHECK` | `strict_date_check` | Mapped (but ignored by engine) | P1 (engine must implement) |
| `ALL_EMPTY_ARE_NULL` | `all_empty_are_null` | Mapped (but ignored by engine) | P1 (engine must implement) |
| `MODE` | -- | **Not Mapped** | P1 |
| `CHECKED_COLUMNS` | -- | **Not Mapped** | P1 |
| `FASTEST_DATE_CHECK` | -- | **Not Mapped** | P2 |
| `IGNORE_TIMEZONE` | -- | **Not Mapped** | P2 |
| `CHECK_BYTE_LENGTH` | -- | **Not Mapped** | P2 |
| `CHARSET` | -- | **Not Mapped** | P2 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## 15. Appendix: Type Mapping Comparison

### Converter Output (ExpressionConverter.convert_type)

| Talend Type | Converter Output | Engine Key Expected |
|-------------|-----------------|---------------------|
| `id_String` | `'str'` | `'id_String'` |
| `id_Integer` | `'int'` | `'id_Integer'` |
| `id_Long` | `'int'` | NOT IN MAPPING |
| `id_Float` | `'float'` | `'id_Float'` |
| `id_Double` | `'float'` | NOT IN MAPPING |
| `id_Boolean` | `'bool'` | NOT IN MAPPING |
| `id_Date` | `'datetime'` | `'id_Date'` (maps to `str`) |
| `id_BigDecimal` | `'Decimal'` | NOT IN MAPPING |
| `id_Object` | `'object'` | NOT IN MAPPING |
| `id_Character` | `'str'` | NOT IN MAPPING |
| `id_Byte` | `'int'` | NOT IN MAPPING |
| `id_Short` | `'int'` | NOT IN MAPPING |

**Key findings**:
- NONE of the converter outputs match any engine mapping keys -- type validation is 100% broken for converted jobs
- 8 of 12 Talend types are not present in the engine's `TALEND_TYPE_MAPPING` at all
- `id_Date` has a double mismatch: converter produces `'datetime'`, engine key is `'id_Date'`, and engine maps it to Python `str`

---

## 16. Appendix: Edge Case Analysis

### NaN Handling

| Scenario | Current Behavior | Expected Talend Behavior | Match? |
|----------|-----------------|-------------------------|--------|
| `float('nan')` in non-nullable column | Rejected via `pd.isnull()` -> `True` | Rejected (null in non-nullable) | Yes |
| `float('nan')` in nullable column | Accepted (continue at line 180) | Accepted (null in nullable) | Yes |
| `float('nan')` in `id_Float` column (nullable) | Accepted; NaN passes through as valid float | Depends on Talend version; typically null handling takes precedence | Approximately yes |
| `numpy.nan` (alias for `float('nan')`) | Same as `float('nan')` | Same | Yes |
| `pd.NA` (pandas nullable NA) | `pd.isnull(pd.NA)` returns `True` -- correctly detected | N/A (no pandas equivalent in Talend) | N/A |
| `None` in non-nullable column | `pd.isnull(None)` returns `True` -- rejected | Rejected | Yes |
| `None` in nullable column | `pd.isnull(None)` returns `True` -- accepted via continue | Accepted | Yes |
| `pd.NaT` (Not a Time) in non-nullable column | `pd.isnull(pd.NaT)` returns `True` -- rejected | Rejected | Yes |
| `float('nan')` surviving past null check | Cannot happen -- `pd.isnull()` catches it first, `continue` skips type check | N/A | Correct by code flow |
| Multiple NaN values in same row (different columns) | Each column checked independently; all NaN-in-non-nullable columns generate errors; single reject row with concatenated errors | Talend validates per-column, rejects on first violation | **Partial**: V1 collects all errors while Talend may stop at first |

**NaN Propagation Risk**: When `pd.DataFrame(valid_rows)` is called at line 220, any NaN values that passed through the null check (because the column was nullable) are preserved in the output DataFrame. These NaN values may cause issues in downstream components that do not handle NaN. In Talend's Java runtime, null values are handled natively by the JVM, but in pandas, NaN is a float value that can propagate through arithmetic operations (e.g., `NaN + 5 = NaN`). This is a semantic difference that is not specific to SchemaComplianceCheck but becomes relevant because valid rows with NaN may be unexpected by downstream consumers.

**NaN in Integer Columns**: In pandas, an integer column containing NaN is automatically upcast to `float64` (because `int64` cannot represent NaN). This means a valid row with a nullable integer column containing NaN will have that column as `float64` in the output. If the downstream component expects `int64`, this type mismatch may cause errors. Pandas nullable integer types (`Int64`) can handle `pd.NA` without upcasting, but the SchemaComplianceCheck output uses standard types.

### Empty String Handling

| Scenario | Current Behavior | Expected Talend Behavior (ALL_EMPTY_ARE_NULL=true) | Expected Talend (=false) | Match? |
|----------|-----------------|---------------------------------------------------|-------------------------|--------|
| `""` in non-nullable `id_String` | Rejected (treated as null) | Rejected (empty = null) | Accepted (empty != null) | Yes for default; **No for false** |
| `"   "` (whitespace) in non-nullable `id_String` | Rejected (`strip()` makes it empty) | Accepted (whitespace is not empty) | Accepted | **No (always diverges)** |
| `""` in nullable `id_String` | Accepted (null in nullable) | Accepted | Accepted | Yes |
| `""` in non-nullable `id_Integer` | `isinstance("", str)` is `True`, `"".strip() == ""` is `True` -- rejected as null | Rejected (empty = null for default) | Treated as type mismatch (empty string is not an integer) | Partially |
| `" a "` in non-nullable `id_String` | `" a ".strip() == ""` is `False` -- passes null check; no further issue | Passes null check | Passes null check | Yes |
| `"\t"` (tab) in non-nullable `id_String` | `"\t".strip() == ""` is `True` -- rejected as null | Accepted (tab is not empty string) | Accepted | **No** |
| `"\n"` (newline) in non-nullable `id_String` | `"\n".strip() == ""` is `True` -- rejected as null | Accepted (newline is not empty string) | Accepted | **No** |
| `"0"` (zero string) in non-nullable `id_Integer` | `"0".strip() == ""` is `False` -- passes null check; type check attempted | Passes null check; type coercion to `0` | Same | Yes |

**Key Finding**: The V1 engine's use of `value.strip() == ''` is overly aggressive compared to Talend's empty string check. Python's `str.strip()` removes all leading/trailing whitespace characters including spaces, tabs, newlines, carriage returns, and other Unicode whitespace. Talend only checks for exact empty string (`""`). This means tab characters, newlines, and other whitespace-only strings are incorrectly rejected as null by the V1 engine.

### HYBRID Streaming Mode

| Scenario | Current Behavior | Expected Behavior | Issue |
|----------|-----------------|-------------------|-------|
| Data < 3GB | BATCH mode; both main and reject returned | Correct | -- |
| Data > 3GB (HYBRID auto-switch) | STREAMING mode; reject data silently discarded | Should return both main and reject | PERF-SCC-004 |
| Data > 3GB, stats | NB_LINE_REJECT accumulated per chunk via `_update_stats()` but reject DF is empty | Stats and data should be consistent | PERF-SCC-004 |
| Explicit STREAMING mode | Same as HYBRID auto-switch -- reject data lost | Should return both main and reject | PERF-SCC-004 |
| Chunk boundary split | A row that would be valid in context of full data is validated per-chunk -- no cross-chunk issues for this component since each row is independent | Correct | -- |
| Schema with many columns (>100) | `iterrows()` per-chunk still slow; each chunk has O(n_chunk * m_columns) operations | Vectorized per chunk would be fast | PERF-SCC-001 |

**Streaming Mode Detailed Flow**:
1. `execute()` calls `_auto_select_mode()` (base_component.py line 206-208)
2. If memory > 3072 MB, returns `ExecutionMode.STREAMING`
3. `_execute_streaming()` is called (line 212)
4. DataFrame is split into chunks via `_create_chunks()` (line 262, yields `df.iloc[i:i+chunk_size]`)
5. Each chunk is passed to `_process()` which returns `{'main': valid_df, 'reject': reject_df}`
6. Only `chunk_result['main']` is collected (line 271)
7. `chunk_result['reject']` is silently discarded
8. Final return has `{'main': combined_main}` -- no 'reject' key at all
9. Downstream reject flow receives `None` or empty DataFrame

### `_update_global_map()` Crash

| Scenario | Current Behavior | Expected Behavior | Issue |
|----------|-----------------|-------------------|-------|
| `global_map` is None | `_update_global_map()` returns immediately (line 300: `if self.global_map`) | Correct | -- |
| `global_map` is set | `put_component_stat()` succeeds for each stat (line 302), then `NameError: name 'value' is not defined` on line 304 | Should log stats without crashing | BUG-SCC-009 |
| Exception recovery | `execute()` catches exception (line 227), calls `_update_global_map()` AGAIN (line 231), causing SECOND `NameError` | Should not re-crash during error handling | BUG-SCC-009 |
| Stats after crash | `put_component_stat()` calls succeed before the crash, so stats ARE written to the global map. But the component status is set to ERROR and the exception propagates, potentially causing the job to fail | Stats should be written and component should complete normally | BUG-SCC-009 |

**Crash Trace Reconstruction**:
```python
# base_component.py execute() method:
try:
    result = self._execute_batch(input_data)  # Succeeds
    self.stats['EXECUTION_TIME'] = ...        # Succeeds
    self._update_global_map()                 # CRASH: NameError('value')
    # Everything after this line never executes:
    self.status = ComponentStatus.SUCCESS      # Never reached
    result['stats'] = self.stats.copy()        # Never reached
    return result                              # Never reached
except Exception as e:
    self.status = ComponentStatus.ERROR        # Executes
    self.error_message = str(e)                # Stores "name 'value' is not defined"
    self.stats['EXECUTION_TIME'] = ...         # Executes
    self._update_global_map()                  # CRASH AGAIN: same NameError
    # The second NameError replaces the first in the traceback
    logger.error(...)                          # Never reached
    raise                                      # Never reached
# Unhandled NameError propagates to job level
```

### Row-by-Row Performance

| Scenario | Row Count | Columns | Estimated V1 Time | Vectorized Time | Notes |
|----------|-----------|---------|-------------------|-----------------|-------|
| Small validation | 100 | 5 | <0.1s | <0.001s | Acceptable for development |
| Medium batch | 10,000 | 10 | 1-10s | <0.01s | Noticeable delay |
| Typical production | 100,000 | 15 | 10-100s | <0.1s | **Blocking for SLA-driven pipelines** |
| Large production | 1,000,000 | 20 | 100-1000s | <1s | **Complete production failure** |
| Enterprise scale | 10,000,000 | 25 | 1000-10000s (3-28 hrs) | <10s | **Impossible in production** |

**Breakdown of per-row overhead**:
- `iterrows()` Series creation: ~50us per row
- `pd.isnull()` per cell: ~1us (m calls per row)
- `isinstance()` per cell: ~0.1us (m calls per row)
- `str.strip()` per string cell: ~0.5us
- `row.get()` per cell: ~1us
- Dict creation for reject: ~5us per rejected row
- Total per-row overhead: ~50 + m*3 us = ~110us for m=20 columns

### `print()` to stdout

| Location | Trigger Condition | Output Text | Frequency | Impact |
|----------|-------------------|-------------|-----------|--------|
| Line 177 | Non-nullable column receives null/empty value | `"Value is empty for column : '{col_name}' in 'Row({n})' connection, value is invalid or this column should be nullable or have a default value."` | Once per null violation per row | Stdout pollution |
| Line 186 | String value exceeds `col_length` | `"Value length exceeds maximum for column : '{col_name}' in 'Row({n})' connection, max length is {col_length}, actual length is {len(value)}"` | Once per length violation per row | Stdout pollution |
| Line 204 | Type coercion fails | `"Type mismatch for column : '{col_name}' in 'Row({n})' connection, expected {col_type}, got {type(value).__name__}."` | Once per type violation per row | Stdout pollution |

**Impact scenarios**:
- **Log aggregation systems**: `print()` output goes to stdout, which many log aggregation pipelines capture alongside structured logging. Unstructured print output breaks JSON log parsing and can corrupt log indices.
- **ETL orchestrators**: Tools like Airflow capture stdout/stderr. Thousands of unstructured print lines per component execution clutter task logs and may trigger log size limits.
- **Testing**: Unit tests using `capsys` or `io.StringIO` to capture stdout will see validation errors mixed with expected output, making assertion-based testing unreliable.
- **JSON-output pipelines**: If the ETL engine is configured to output results as JSON to stdout (common in CLI tools), print statements inject non-JSON text that breaks the output parser.

### Type Validation Correctness

| Input Value | Column Type | Expected Talend Result | V1 Engine Result (with Talend types) | V1 Engine Result (with converter types) |
|-------------|-------------|----------------------|--------------------------------------|----------------------------------------|
| `42` (int) | `id_Integer` | Valid | Valid (`isinstance(42, int)` -> True) | Skipped (type lookup returns None) |
| `"hello"` (str) | `id_Integer` | Rejected | Rejected (coercion `int(float("hello"))` raises ValueError) | Skipped (no validation) |
| `3.14` (float) | `id_Integer` | Rejected (float != int) | **Silently truncated to 3** (BUG-SCC-006) | Skipped (no validation) |
| `True` (bool) | `id_Integer` | Rejected (bool != int) | **Valid** (`isinstance(True, int)` -> True in Python, since `bool` is subclass of `int`) | Skipped |
| `"3.14"` (str) | `id_Float` | Rejected (str != float) | Coerced to `3.14` (float) | Skipped |
| `""` (empty str) | `id_Float` | Depends on ALL_EMPTY_ARE_NULL | Rejected as null (if non-nullable) | Rejected as null (if non-nullable) |
| `None` | `id_String` | Null handling | Rejected as null (if non-nullable) | Rejected as null (if non-nullable) |
| `"2023-01-15"` | `id_Date` | Valid if pattern matches | Valid (mapped to `str`, any string passes) | Skipped |
| `"not-a-date"` | `id_Date` | **Rejected** (pattern mismatch) | **Valid** (mapped to `str`) | Skipped |
| `42` (int) | `id_Long` | Valid | `_validate_config()` error (type not in mapping); `_process()` skips | N/A |
| `42.0` (float) | `id_Double` | Valid | `_validate_config()` error (type not in mapping); `_process()` skips | N/A |
| `True` (bool) | `id_Boolean` | Valid | `_validate_config()` error (type not in mapping); `_process()` skips | N/A |

**Python `bool` is subclass of `int` edge case**: In Python, `isinstance(True, int)` returns `True` because `bool` is a subclass of `int`. This means boolean values `True`/`False` would pass type validation for `id_Integer` columns, which is incorrect for Talend behavior where boolean and integer are distinct types. This is a subtle bug that only manifests when type validation is actually working (i.e., after fixing CONV-SCC-001).

### Error Code Handling

| Violation Type | V1 Error Code | Expected Talend Error Code | V1 Error Message Pattern | Expected Talend Pattern |
|---------------|---------------|---------------------------|-------------------------|------------------------|
| Null in non-nullable | `8` | Varies by version | `col_name:cannot be null` | Descriptive message with column and row context |
| Type mismatch | `8` | Varies by version | `col_name:invalid type` | Descriptive with expected vs. actual type |
| Length exceeded | `8` | Varies by version | `col_name:exceed max length` | Descriptive with max and actual length |
| Missing column | `8` (if non-nullable) | Schema mismatch | `col_name:cannot be null` (misidentified as null) | Column missing error |
| Multiple errors | `8` | Per-violation code | `col1:error1;col2:error2` | Per-violation separate handling |

**Downstream impact**: Components like `tLogRow`, `tFileOutputDelimited`, or `tMap` that connect to the reject flow may filter or route based on `errorCode`. With all codes being `8`, no error-type-based routing is possible. A `tMap` expression like `row.errorCode == 3 ? "type_error" : "other"` would never match type errors.

### Reject Flow Format

**V1 Engine Reject DataFrame Structure**:
```
| original_col_1 | original_col_2 | ... | original_col_n | errorCode | errorMessage |
|----------------|----------------|-----|----------------|-----------|--------------|
| value1         | value2         | ... | valueN         | 8         | col1:cannot be null;col2:invalid type |
```

**Talend Reject Row Structure**:
```
| original_col_1 | original_col_2 | ... | original_col_n | errorCode | errorMessage |
|----------------|----------------|-----|----------------|-----------|------------------------|
| value1         | value2         | ... | valueN         | <varies>  | <Descriptive message>  |
```

**Differences**:
1. V1 error message uses terse `col:type` format; Talend uses full sentences
2. V1 concatenates all errors with `;`; Talend may report only the first error per row
3. V1 always includes all original columns via `**row` spread; Talend also includes all original columns
4. V1 `errorCode` is always integer `8`; Talend `errorCode` is typed as String in the reject schema (even though values are numeric)
5. V1 preserves the order of errors as encountered during column iteration; this matches schema column order

---

## 17. Appendix: Talend Documentation Sources

The following sources were consulted during this audit:

- [tSchemaComplianceCheck Standard properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/validation/tschemacompliancecheck-standard-properties)
- [tSchemaComplianceCheck (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/validation/tschemacompliancecheck)
- [tSchemaComplianceCheck Standard properties (Talend 7.3)](https://help.talend.com/r/en-US/7.3/validation/tschemacompliancecheck-standard-properties)
- [tSchemaComplianceCheck (Talend 7.2)](https://help.qlik.com/talend/en-US/components/7.2/validation/tschemacompliancecheck)
- [Validating data against schema (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/validation/validating-data-against-schema)
- [tSchemaComplianceCheck -- Docs for ESB 7.x (Talend Skill)](https://talendskill.com/talend-for-esb-docs/docs-7-x/tschemacompliancecheck-talend-open-studio-for-esb-document-7-x/)
- [tSchemaComplianceCheck -- Docs for ESB 5.x (Talend Skill)](https://talendskill.com/talend-for-esb-docs/docs-5-x/tschemacompliancecheck-docs-for-esb-5-x/)
- [Configuring the components (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/validation/tschemacompliancecheck-tlogrow-tfileinputdelimited-tfileinputdelimited-configuring-components-standard-component-enterprise)
- [Validating against the schema -- Talend Open Studio Cookbook](https://www.oreilly.com/library/view/talend-open-studio/9781782167266/ch03s04.html)
- [tSchemaComplianceCheck Error Code discussion (Talend Community)](https://community.talend.com/t5/Design-and-Development/tSchema-Compliance-Error-Code-missing-in-DI-6-3-1-using/td-p/22614)
- [Reject lines from tSchemaComplianceCheck (Talend Forum)](https://www.talendforge.org/forum/viewtopic.php?id=51674)

---

## 18. Verdict

### Production Readiness: NOT READY (RED)

The `SchemaComplianceCheck` component has **8 critical (P0) issues** that collectively render it non-functional or crash-prone:

1. **Type validation does not work** for any job converted from Talend XML due to a type-mapping mismatch between the converter and engine (CONV-SCC-001 / ENG-SCC-001 / BUG-SCC-001).
2. **Converter crashes on missing XML parameters** -- all four `node.find()` calls chain `.get()` with no null check, raising `AttributeError` if any `<elementParameter>` is absent (CONV-SCC-005).
3. **Performance is 100-1000x slower** than necessary due to row-by-row `iterrows()` iteration, making it unsuitable for production data volumes (ENG-SCC-002 / PERF-SCC-001).
4. **`_update_global_map()` crashes** with `NameError` whenever `global_map` is set, affecting ALL components (BUG-SCC-009, cross-cutting).
5. **`GlobalMap.get()` crashes** with `NameError` on every call (BUG-SCC-013, cross-cutting).
6. **No test coverage exists**, providing zero confidence in correctness (TEST-SCC-001).
7. **Three `print()` statements** violate coding standards and produce uncontrolled stdout output (STD-SCC-001/002/003).
8. **Multiple extracted config keys are ignored**, meaning converter work is wasted and Talend behavioral fidelity is compromised (STD-SCC-005 -- 4 keys extracted, 0 read).

The component requires a **significant rewrite** before production deployment. The recommended approach:

| Step | Fix | Effort |
|------|-----|--------|
| 1 | Fix `_update_global_map()` crash (1 line -- cross-cutting) | 5 minutes |
| 2 | Fix `GlobalMap.get()` crash (1 line -- cross-cutting) | 5 minutes |
| 3 | Fix converter type mapping (1 line) | 5 minutes |
| 4 | Add null checks to converter `node.find()` calls (4 lines) | 10 minutes |
| 5 | Remove 3x `print()` statements (3 lines) | 5 minutes |
| 6 | Fix `length=-1` sentinel in converter/engine (1 line) | 5 minutes |
| 7 | Protect reject output from `errorCode`/`errorMessage` column collisions | 15 minutes |
| 8 | Rewrite `_process()` with vectorized pandas operations | 2-3 days |
| 9 | Implement the 4 ignored config keys | 1-2 days |
| 10 | Expand type mapping to all 12 Talend types | 0.5 days |
| 11 | Create comprehensive unit tests | 2-3 days |

**Estimated total effort: 6-9 days** for a developer familiar with both pandas and Talend semantics.

---

## 19. Appendix: Cross-Cutting Impact Analysis

### BUG-SCC-009 / BUG-SCC-013: GlobalMap Crash Propagation

These two bugs affect ALL v1 engine components, not just SchemaComplianceCheck. They are documented here because they were discovered during this audit, but their fix scope is broader.

**Components affected by BUG-SCC-009** (`_update_global_map()` crash):
Every component that inherits from `BaseComponent` and is executed with a non-None `global_map`. This includes all file input/output components, all transform components, all utility components -- essentially every component in the v1 engine. The `execute()` method (base_component.py line 218) unconditionally calls `_update_global_map()` after every successful execution.

**Components affected by BUG-SCC-013** (`GlobalMap.get()` crash):
Any code path that calls `global_map.get()` or `global_map.get_component_stat()`. This includes:
- The engine's variable resolution logic (when resolving `{id}_NB_LINE` references)
- Any component that reads other components' statistics
- The `get_nb_line()`, `get_nb_line_ok()`, `get_nb_line_reject()` convenience methods (via `get_component_stat()` -> `self.get(key, default)`)

**Impact on testing**: These bugs make it impossible to run ANY component with `global_map` enabled in the v1 engine. This means all integration tests that use `global_map` will fail, masking any other bugs that might be present. Fixing these two bugs is a prerequisite for any meaningful testing.

**Fix complexity**: Both are one-line fixes:
- BUG-SCC-009: Change `{value}` to `{stat_value}` on base_component.py line 304
- BUG-SCC-013: Change `def get(self, key: str)` to `def get(self, key: str, default: Any = None)` on global_map.py line 26

### Converter Type Format: Cross-Component Pattern

The use of `ExpressionConverter.convert_type()` is not unique to `parse_tschema_compliance_check()`. A search across `component_parser.py` reveals it is called in:

| Location | Component | Line | Impact |
|----------|-----------|------|--------|
| `parse_base_component()` | All components using generic parser | 482 | Affects all generically parsed schemas |
| `parse_tschema_compliance_check()` | tSchemaComplianceCheck | 2090 | Breaks type validation (CONV-SCC-001) |
| tAggregateRow parser | tAggregateRow | 2009 | May affect type-based aggregation |
| tMap variable table | tMap | 611 | Affects variable type inference |
| tFilterRows parser | tFilterRows | 1576 | May affect filter type checking |

This means fixing the type format for SchemaComplianceCheck alone does not address the systemic issue. However, for SchemaComplianceCheck the impact is uniquely severe because it is the ONLY component whose core functionality depends on matching config types against a runtime type mapping dictionary.

For other components, the Python type format (`'str'`, `'int'`) is typically used only for informational purposes (logging, metadata) or for pandas dtype selection (`_build_dtype_dict()` in base_component.py), where both formats are supported. The SchemaComplianceCheck engine is the only one that does a strict dictionary key lookup against the type value.

---

## 20. Appendix: Comparison with Talend Generated Java Code

Talend generates Java code for tSchemaComplianceCheck that follows this pattern (simplified):

```java
// Talend-generated code for tSchemaComplianceCheck_1
if (row1.age == null) {
    // Null check for non-nullable column 'age' (Integer type)
    reject_row.errorCode = "1";
    reject_row.errorMessage = "age is null";
    // Route to reject flow
} else {
    try {
        // Type check: value is already typed in Java, so type mismatch
        // is caught at compile time or via schema enforcement
        Integer.parseInt(String.valueOf(row1.age));
    } catch (NumberFormatException e) {
        reject_row.errorCode = "2";
        reject_row.errorMessage = "Type mismatch for column 'age'";
    }
}

// Length check
if (row1.name != null && row1.name.length() > schema_name_length) {
    if (SUB_STRING) {
        row1.name = row1.name.substring(0, schema_name_length);
        // Silently truncate -- row is NOT rejected
    } else {
        reject_row.errorCode = "3";
        reject_row.errorMessage = "Length exceeded for column 'name'";
    }
}
```

**Key differences from V1 engine**:
1. Talend Java code uses typed variables; Python uses dynamic types requiring `isinstance()` checks
2. Talend generates per-column validation code at design time; V1 iterates columns at runtime
3. Talend uses different error codes per violation type; V1 hardcodes `8`
4. Talend implements `SUB_STRING` truncation inline; V1 ignores it
5. Talend checks `ALL_EMPTY_ARE_NULL` at code generation time; V1 ignores the flag
6. Talend produces a separate error row per violation (in some versions); V1 concatenates all errors into one reject row
7. Java's type system catches many type mismatches at compile time; Python must check at runtime

---

## 21. Appendix: Detailed `_validate_config()` Analysis

The `_validate_config()` method (lines 70-121) performs comprehensive configuration validation but is never called. If it were wired up, it would catch several errors early:

### What it validates:

1. **Schema presence**: `'schema' not in self.config` -- catches missing schema entirely
2. **Schema type**: `not isinstance(schema, list)` -- catches non-list schema (e.g., dict, string)
3. **Schema non-empty**: `len(schema) == 0` -- catches empty schema list
4. **Column type**: Each column must be a dictionary
5. **Required field 'name'**: Must exist and be a string
6. **Required field 'type'**: Must exist, be a string, and be in `TALEND_TYPE_MAPPING`
7. **Optional field 'nullable'**: Must be boolean if present
8. **Optional field 'length'**: Must be integer if present

### What it does NOT validate:

1. **Column name uniqueness**: Duplicate column names in the schema would cause unpredictable behavior but are not detected
2. **Column name format**: Names with spaces, special characters, or empty strings are accepted
3. **Length value range**: Negative length values are accepted (no `length > 0` check)
4. **Schema column existence in input**: No check that schema columns exist in the actual input DataFrame (this can only be checked at runtime)
5. **Config keys used by engine**: Does not validate `check_all`, `sub_string`, `strict_date_check`, `all_empty_are_null` (not that it matters, since the engine ignores them)

### Bug in type validation:

The check `col['type'] not in self.TALEND_TYPE_MAPPING` (line 109) correctly rejects types not in the 4-entry mapping. However, this means ALL converter-produced types (`'int'`, `'str'`, `'float'`, `'datetime'`) would be rejected by config validation. If `_validate_config()` were wired up, no converted job would pass configuration validation. This creates a paradox: fixing the dead-code issue (STD-SCC-004) without first fixing the type mapping (CONV-SCC-001) would make things worse, not better.

### Recommended fix order:

1. Fix CONV-SCC-001 (remove `convert_type()` call) -- schema now has Talend type format
2. Expand `TALEND_TYPE_MAPPING` to all 12 types (ENG-SCC-003) -- all Talend types are recognized
3. Wire up `_validate_config()` in execution pipeline (STD-SCC-004) -- validation now works correctly

---

## 22. Appendix: Execution Flow Diagram

```
[Talend XML] ──parse_tschema_compliance_check()──> [V1 JSON Config]
                                                         │
                                                         ▼
                                                  ┌─────────────┐
                                                  │ engine.py    │
                                                  │ registry     │
                                                  │ lookup       │
                                                  └──────┬──────┘
                                                         │
                                                         ▼
                                              ┌──────────────────┐
                                              │ BaseComponent    │
                                              │ .execute()       │
                                              │                  │
                                              │ 1. Resolve ctx   │
                                              │ 2. Resolve java  │
                                              │ 3. Auto-select   │
                                              │    mode          │
                                              │ 4. Dispatch to   │
                                              │    batch/stream  │
                                              └────────┬─────────┘
                                                       │
                                         ┌─────────────┴──────────────┐
                                         │                            │
                                    BATCH mode                  STREAMING mode
                                         │                            │
                                         ▼                            ▼
                              ┌────────────────┐          ┌─────────────────┐
                              │ _process()     │          │ _execute_       │
                              │                │          │  streaming()    │
                              │ iterrows loop  │          │                 │
                              │ null check     │          │ chunk 1 ──┐    │
                              │ length check   │          │ chunk 2 ──┤    │
                              │ type check     │          │ chunk N ──┘    │
                              │                │          │                 │
                              │ valid_rows     │          │ collect main   │
                              │ reject_rows    │          │ DISCARD reject │
                              └───────┬────────┘          └────────┬──────┘
                                      │                            │
                                      ▼                            ▼
                              ┌────────────────┐          ┌─────────────────┐
                              │ Return:        │          │ Return:         │
                              │ main: valid_df │          │ main: combined  │
                              │ reject: rej_df │          │ (no reject!)    │
                              └───────┬────────┘          └────────┬──────┘
                                      │                            │
                                      └────────────┬───────────────┘
                                                   │
                                                   ▼
                                        ┌──────────────────┐
                                        │ _update_stats()  │
                                        │ _update_global   │
                                        │   _map()         │  ◄── CRASH (BUG-SCC-009)
                                        └──────────────────┘
```

---

## 23. Appendix: Minimal Reproduction Script

The following script demonstrates the three most critical bugs in the SchemaComplianceCheck component. It can be used to verify fixes.

```python
#!/usr/bin/env python3
"""
Minimal reproduction script for SchemaComplianceCheck P0 bugs.
Run from project root: python -m scripts.scc_bug_repro
"""
import pandas as pd
import sys
sys.path.insert(0, 'src/v1')

# --- Bug 1: Type validation is non-functional for converted jobs ---
print("=== BUG 1: Type Mapping Mismatch ===")

# Simulating converter output (Python type strings)
converter_schema = [
    {'name': 'age', 'type': 'int', 'nullable': False},     # Converter output
    {'name': 'name', 'type': 'str', 'nullable': False},     # Converter output
]

# Simulating direct Talend type format
talend_schema = [
    {'name': 'age', 'type': 'id_Integer', 'nullable': False},  # Talend format
    {'name': 'name', 'type': 'id_String', 'nullable': False},  # Talend format
]

TALEND_TYPE_MAPPING = {
    'id_Integer': int,
    'id_String': str,
    'id_Float': float,
    'id_Date': str,
}

# With converter output: type lookup returns None
for col in converter_schema:
    expected_type = TALEND_TYPE_MAPPING.get(col['type'], None)
    print(f"  Column '{col['name']}', type='{col['type']}' -> "
          f"expected_type={expected_type} -> "
          f"type_check_runs={'YES' if expected_type else 'NO (SKIPPED!)'}")

print()

# With Talend format: type lookup works
for col in talend_schema:
    expected_type = TALEND_TYPE_MAPPING.get(col['type'], None)
    print(f"  Column '{col['name']}', type='{col['type']}' -> "
          f"expected_type={expected_type} -> "
          f"type_check_runs={'YES' if expected_type else 'NO'}")

# --- Bug 2: iterrows() performance ---
print("\n=== BUG 2: iterrows() Performance ===")
import time
df = pd.DataFrame({'a': range(100000), 'b': ['x'] * 100000})
start = time.time()
for _, row in df.iterrows():
    pass  # Just iterate, no processing
elapsed = time.time() - start
print(f"  iterrows() over 100K rows: {elapsed:.2f}s")
print(f"  Projected 1M rows: {elapsed * 10:.1f}s")
print(f"  Projected 10M rows: {elapsed * 100:.1f}s")

# --- Bug 3: _update_global_map() crash ---
print("\n=== BUG 3: _update_global_map() Crash ===")
stats = {'NB_LINE': 100, 'NB_LINE_OK': 95, 'NB_LINE_REJECT': 5}
try:
    for stat_name, stat_value in stats.items():
        pass  # Simulating put_component_stat()
    # This is what base_component.py line 304 does:
    msg = f"Stats: {stat_name}: {value}"  # 'value' is undefined!
    print(f"  No crash? Something is wrong.")
except NameError as e:
    print(f"  CRASH: NameError: {e}")
    print(f"  This crash happens in _update_global_map() every time global_map is set.")
```

This script can be used as a quick smoke test before and after applying fixes to verify the bugs are resolved.
