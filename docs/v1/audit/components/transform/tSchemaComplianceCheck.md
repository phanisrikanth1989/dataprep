# Audit Report: tSchemaComplianceCheck / SchemaComplianceCheck

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tSchemaComplianceCheck` |
| **V1 Engine Class** | `SchemaComplianceCheck` |
| **Engine File** | `src/v1/engine/components/transform/schema_compliance_check.py` (255 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/schema_compliance_check.py` (249 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tSchemaComplianceCheck")` decorator-based dispatch |
| **Registry Aliases** | `SchemaComplianceCheck`, `tSchemaComplianceCheck` |
| **Category** | Transform / Validation (Data Quality) |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/schema_compliance_check.py` | Engine implementation (255 lines) |
| `src/converters/talend_to_v1/components/transform/schema_compliance_check.py` | Converter class (249 lines) |
| `tests/converters/talend_to_v1/components/test_schema_compliance_check.py` | Converter tests (46 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 15 config keys extracted (13 unique + 2 framework). CHECKCOLS stride-5, EMPTY_NULL_TABLE stride-2. 12 per-feature needs_review. All defaults verified against _java.xml. |
| Engine Feature Parity | **R** | 2 | 5 | 3 | 1 | Engine reads ONLY schema; ignores all 12 config params. Type validation broken (4 of 12 types). No date validation. No Custom Defined mode. |
| Code Quality | **G** | 0 | 0 | 0 | 0 | Converter follows gold standard pattern. Uses _build_component_dict, proper TABLE parsers, correct needs_review structure. |
| Performance & Memory | **N/A** | 0 | 0 | 0 | 0 | Converter is stateless XML-to-JSON transform. Engine performance issues documented under Engine. |
| Testing | **Y** | 0 | 0 | 1 | 0 | 46 converter tests across 8 test classes. No engine unit tests. |

**Overall: Y -- Converter and code quality are production-ready (Green). Testing is Yellow (no engine tests). Engine remains Red (reads only schema, ignores all config).**

**Top Actions**:

1. Add engine unit tests for SchemaComplianceCheck
2. Engine: implement config param reading (12 params currently ignored)
3. Engine: expand type mapping beyond 4 types
4. Engine: add date validation support

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from .item files, _java.xml, and official docs.

### What tSchemaComplianceCheck Does

`tSchemaComplianceCheck` is a data quality validation component belonging to the **Data Quality** family. It acts as an intermediary step in a data flow, validating all input rows against a reference schema by checking data types, nullability constraints, and field length limits. Non-compliant rows are routed to a REJECT output flow with supplementary `errorCode` and `errorMessage` columns for downstream error handling.

The component supports three validation modes: "Check all columns" (default), "Custom defined" (selective per-column validation via CHECKCOLS TABLE), and "Use another schema" (external reference schema). Advanced features include fast/strict date checking, timezone handling, empty-as-null treatment, and byte-length string validation.

The component is **not included in Talend Studio by default** and requires installation via the Feature Manager, indicating it is a specialized data quality tool rather than a general-purpose component.

**Source**: [tSchemaComplianceCheck Standard properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/validation/tschemacompliancecheck-standard-properties), [Talaxie GitHub tSchemaComplianceCheck_java.xml](https://github.com/nicosommi/talaxie-tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tSchemaComplianceCheck/tSchemaComplianceCheck_java.xml)
**Component family**: Data Quality (Validation)
**Available in**: All Talend products (Standard). Also available in Spark Streaming variant.
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Check All Columns | `CHECK_ALL` | Boolean (RADIO) | `true` | Validate all columns against schema. Default RADIO selection in MODE group. |
| 2 | Custom Defined | `CUSTOMER` | Boolean (RADIO) | `false` | Enable selective per-column validation via CHECKCOLS table. RADIO group MODE. |
| 3 | Use Another Schema | `CHECK_ANOTHER` | Boolean (RADIO) | `false` | Reference a separate schema for validation. RADIO group MODE. |
| 4 | Checked Columns | `CHECKCOLS` | Table (stride-5, BASED_ON_SCHEMA) | `[]` | Per-column validation rules: SCHEMA_COLUMN, SELECTED_TYPE, DATEPATTERN, NULLABLE, MAX_LENGTH. Visible in Custom Defined mode. |
| 5 | Trim Excess Content | `SUB_STRING` | Boolean | `false` | Truncate overlong strings instead of rejecting. String type only. |
| 6 | Strict Date Check | `STRICT_DATE_CHECK` | Boolean | `false` | Strict format validation for dates. |
| 7 | Treat Empty as NULL | `ALL_EMPTY_ARE_NULL` | Boolean | `true` | Treat empty strings as null values. Critical for nullability checks. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 8 | Fast Date Check | `FAST_DATE_CHECK` | Boolean | `false` | Use TalendDate.isDate() for fast date validation. Hidden when Strict enabled. |
| 9 | Ignore TimeZone | `IGNORE_TIMEZONE` | Boolean | `false` | Disregard timezone during date validation. |
| 10 | Choose Columns (Empty/Null) | `EMPTY_NULL_TABLE` | Table (stride-2, BASED_ON_SCHEMA) | `[]` | Per-column empty-as-null selection: SCHEMA_COLUMN, EMPTY_NULL. Visible when ALL_EMPTY_ARE_NULL unchecked. |
| 11 | Check String by Byte Length | `CHECK_STRING_BY_BYTE_LENGTH` | Boolean | `false` | Validate string length in bytes per charset. |
| 12 | Charset | `CHARSET` | String | `""` | Character encoding for byte-length checking. Visible when CHECK_STRING_BY_BYTE_LENGTH enabled. |
| 13 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean | `false` | Framework param: collect component-level stats. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row | Incoming data rows to validate against the reference schema. |
| `FLOW` (Main) | Output | Row | Compliant rows that pass all schema checks. Same schema as input. |
| `REJECTS` | Output | Row | Non-compliant rows with errorCode and errorMessage columns appended. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when subjob fails with error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when component fails with error. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total rows processed (input). |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows that passed validation. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows that failed validation. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if error occurred. |

### 3.5 Behavioral Notes

1. **Validation Hierarchy**: Validates in order: (1) Nullability check, (2) Type check, (3) Length check. Row rejected on first violation.
2. **REJECT Flow**: Rejected rows include ALL original columns plus errorCode (integer) and errorMessage (string).
3. **Empty String Handling**: By default (ALL_EMPTY_ARE_NULL=true), empty strings are treated as NULL for nullability checks.
4. **SUB_STRING Behavior**: When enabled, overlong strings are silently truncated rather than causing rejection. String type only.
5. **Date Validation Modes**: Three mutually exclusive: no date check (default), fast (TalendDate.isDate()), strict (exact pattern matching).
6. **Custom vs. Check All**: In "Check all" mode, every column validated. In "Custom defined", only CHECKCOLS table columns validated selectively.
7. **Byte Length**: When CHECK_STRING_BY_BYTE_LENGTH enabled, string length measured in bytes per CHARSET encoding.
8. **RADIO Group**: CHECK_ALL, CUSTOMER, CHECK_ANOTHER are mutually exclusive. Only one can be true at a time.

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The `SchemaComplianceCheckConverter` uses `@REGISTRY.register("tSchemaComplianceCheck")` decorator for dispatch. It extracts 13 unique params + 2 framework params + schema from FLOW metadata. Two TABLE params use dedicated module-level parsers: `_parse_checkcols()` (stride-5) and `_parse_empty_null_table()` (stride-2). Returns `ComponentResult` via `_build_component_dict(type_name="SchemaComplianceCheck")`.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `CHECK_ALL` | Yes | `check_all` | Bool, default True. RADIO GROUP MODE. |
| 2 | `CUSTOMER` | Yes | `customer` | Bool, default False. RADIO GROUP MODE. |
| 3 | `CHECK_ANOTHER` | Yes | `check_another` | Bool, default False. RADIO GROUP MODE. |
| 4 | `CHECKCOLS` | Yes | `checkcols` | TABLE stride-5 (BASED_ON_SCHEMA): SCHEMA_COLUMN, SELECTED_TYPE, DATEPATTERN, NULLABLE, MAX_LENGTH. |
| 5 | `SUB_STRING` | Yes | `sub_string` | Bool, default False. |
| 6 | `STRICT_DATE_CHECK` | Yes | `strict_date_check` | Bool, default False. |
| 7 | `ALL_EMPTY_ARE_NULL` | Yes | `all_empty_are_null` | Bool, default True. |
| 8 | `FAST_DATE_CHECK` | Yes | `fast_date_check` | Bool, default False. |
| 9 | `IGNORE_TIMEZONE` | Yes | `ignore_timezone` | Bool, default False. |
| 10 | `EMPTY_NULL_TABLE` | Yes | `empty_null_table` | TABLE stride-2 (BASED_ON_SCHEMA): SCHEMA_COLUMN, EMPTY_NULL. |
| 11 | `CHECK_STRING_BY_BYTE_LENGTH` | Yes | `check_string_by_byte_length` | Bool, default False. |
| 12 | `CHARSET` | Yes | `charset` | Str, default "". |
| 13 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, default False. |
| 14 | `LABEL` | Yes | `label` | Framework param, default "". |
| -- | `SCHEMA` (metadata) | Yes | `schema` (config) | Via _parse_schema() base class: name, type, nullable, length. |

**Summary**: 14 of 14 applicable parameters extracted (100%). All defaults verified against _java.xml.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Direct from SchemaColumn |
| `type` | Yes | Converted from Talend types via convert_type() |
| `nullable` | Yes | Direct boolean |
| `key` | Yes | Direct boolean |
| `length` | Yes | Only included when >= 0 |
| `precision` | Yes | Only included when >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not needed for compliance checking |

Config-level schema additionally extracts subset: name, type, nullable, length.

### 4.3 Expression Handling

Context variables (`context.var`) are passed through as string values via `_get_str()`. Java expressions are not evaluated at conversion time -- they remain as string values in the config for potential runtime resolution.

### 4.4 Converter Issues

No open converter issues. All previous CONV-SCC-001 through CONV-SCC-008 are **SUPERSEDED** by the talend_to_v1 rewrite.

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| CONV-SCC-001 | ~~P1~~ | **SUPERSEDED** -- Type conversion now handled by base class _parse_schema() |
| CONV-SCC-002 | ~~P1~~ | **SUPERSEDED** -- CHECKCOLS extracted with stride-5 parser |
| CONV-SCC-003 | ~~P1~~ | **SUPERSEDED** -- RADIO MODE params extracted as individual booleans |
| CONV-SCC-004 | ~~P1~~ | **SUPERSEDED** -- Date pattern handled by base class |
| CONV-SCC-005 | ~~P0~~ | **SUPERSEDED** -- talend_to_v1 uses null-safe _get_str()/_get_bool() |
| CONV-SCC-006 | ~~P1~~ | **SUPERSEDED** -- CHECK_STRING_BY_BYTE_LENGTH and CHARSET extracted |
| CONV-SCC-007 | ~~P2~~ | **SUPERSEDED** -- Schema precision/key handled by base class |
| CONV-SCC-008 | ~~P1~~ | **SUPERSEDED** -- FAST_DATE_CHECK and IGNORE_TIMEZONE extracted |

### 4.5 Needs Review Entries

The converter emits 12 per-feature engine_gap entries. The engine reads ONLY the schema config key and ignores all other parameters:

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `check_all` | Engine does not read 'check_all' from config | engine_gap |
| 2 | `customer` | Engine does not read 'customer' from config | engine_gap |
| 3 | `check_another` | Engine does not read 'check_another' from config | engine_gap |
| 4 | `checkcols` | Engine does not read 'checkcols' from config | engine_gap |
| 5 | `sub_string` | Engine does not read 'sub_string' from config | engine_gap |
| 6 | `strict_date_check` | Engine does not read 'strict_date_check' from config | engine_gap |
| 7 | `all_empty_are_null` | Engine does not read 'all_empty_are_null' from config | engine_gap |
| 8 | `fast_date_check` | Engine does not read 'fast_date_check' from config | engine_gap |
| 9 | `ignore_timezone` | Engine does not read 'ignore_timezone' from config | engine_gap |
| 10 | `empty_null_table` | Engine does not read 'empty_null_table' from config | engine_gap |
| 11 | `check_string_by_byte_length` | Engine does not read 'check_string_by_byte_length' from config | engine_gap |
| 12 | `charset` | Engine does not read 'charset' from config | engine_gap |

Framework params (tstatcatcher_stats, label) exempt from needs_review per convention.

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Row-by-row validation | Yes | Low | `_process()` L160 | Uses iterrows() -- functional but very slow |
| 2 | Nullability check | Yes | Medium | `_process()` L174 | Checks pd.isnull() + empty string + whitespace. No ALL_EMPTY_ARE_NULL toggle. |
| 3 | Type check | Partial | Low | `_process()` L191 | Only 4 types in mapping (Integer, String, Float, Date). Converter types != engine types. |
| 4 | Type coercion | Partial | Low | `_process()` L194-206 | Writes to iterrows() copy; coerced values discarded. |
| 5 | Length check | Yes | Low | `_process()` L182-188 | Only string values. No SUB_STRING support. |
| 6 | FLOW output | Yes | High | `_process()` L220 | Valid rows collected correctly. |
| 7 | REJECT output | Yes | Medium | `_process()` L221 | Has errorCode + errorMessage but code hardcoded to 8. |
| 8 | Check All mode | Implicit | Medium | `_process()` L165 | Always checks all columns. Cannot switch modes. |
| 9 | Custom Defined mode | **No** | N/A | -- | No per-column selective validation. |
| 10 | Date validation | **No** | N/A | -- | No fast or strict date check. |
| 11 | Byte-length check | **No** | N/A | -- | No CHECK_STRING_BY_BYTE_LENGTH support. |
| 12 | GlobalMap stats | Yes | High | Base class `_update_stats()` | NB_LINE, NB_LINE_OK, NB_LINE_REJECT set correctly. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-SCC-001 | **P0** | **Type validation broken**: Engine maps only 4 types (id_Integer, id_String, id_Float, id_Date). Converter produces Python types (int, str, float, datetime). Type check always passes for converted jobs because types never match engine mapping. |
| ENG-SCC-002 | **P0** | **Type coercion writes to copy**: `iterrows()` returns copies, so coerced values in lines 194-206 are discarded. Valid rows retain original uncoerced values. |
| ENG-SCC-003 | **P1** | **No Custom Defined mode**: Engine always checks all schema columns. CUSTOMER/CHECK_ANOTHER/CHECKCOLS TABLE ignored. |
| ENG-SCC-004 | **P1** | **No date validation**: Neither FAST_DATE_CHECK nor STRICT_DATE_CHECK implemented. Date columns only checked for nullability. |
| ENG-SCC-005 | **P1** | **No SUB_STRING support**: Overlong strings always rejected, never truncated. |
| ENG-SCC-006 | **P1** | **ALL_EMPTY_ARE_NULL hardcoded**: Empty strings always treated as null. No toggle. |
| ENG-SCC-007 | **P1** | **No IGNORE_TIMEZONE**: Timezone always included in date validation (if date validation were working). |
| ENG-SCC-008 | **P2** | **Error code hardcoded to 8**: Talend uses different error codes per violation type. Engine uses 8 for all. |
| ENG-SCC-009 | **P2** | **Error message format differs**: Engine uses `col:error_type;` format vs Talend's more detailed messages. |
| ENG-SCC-010 | **P2** | **No byte-length check**: CHECK_STRING_BY_BYTE_LENGTH/CHARSET ignored. Always counts characters. |
| ENG-SCC-011 | **P3** | **No EMPTY_NULL_TABLE support**: Per-column empty-as-null selection not implemented. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Correct |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | Correct |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | Correct |
| `{id}_ERROR_MESSAGE` | Yes | No | -- | Not set by engine |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| -- | -- | -- | No converter bugs. Engine bugs documented in Section 5. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | Converter follows gold standard naming. No issues. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| -- | -- | -- | Converter fully compliant with CONVERTER_PATTERN.md and TEST_PATTERN.md. |

### 6.4 Debug Artifacts

Engine has 3x `print()` statements (lines 177, 185, 203) writing to stdout. These should use `logger.info()`. Not a converter issue.

### 6.5 Security

No concerns identified in the converter. Engine does not handle file paths or execute code.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Converter: `logger = logging.getLogger(__name__)` -- correct |
| Level usage | Engine uses appropriate info/debug/warning levels |
| Sensitive data | No sensitive data logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Not needed -- converter returns ComponentResult |
| Exception chaining | N/A |
| die_on_error handling | Not applicable (no DIE_ON_ERROR param in _java.xml) |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Fully typed in converter and engine |
| Parameter types | All params typed via _get_str/_get_bool return types |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No converter performance issues. Stateless XML-to-JSON transform. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A (converter is stateless) |
| Memory threshold | N/A |
| Large data handling | N/A for converter. Engine uses iterrows() (slow but functional). |

Engine performance note: `iterrows()` in `_process()` is 100-1000x slower than vectorized operations. This is an engine concern, not a converter concern.

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 46 | `tests/converters/talend_to_v1/components/test_schema_compliance_check.py` |
| Engine unit tests | 0 | None |
| Integration tests | Included | `tests/converters/talend_to_v1/test_integration.py` |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-SCC-001 | **P2** | No engine unit tests for SchemaComplianceCheck -- type validation, nullability, length, reject flow |

### 8.3 Recommended Test Cases

Engine tests needed:

- Happy path: valid rows pass through
- Nullability rejection: non-nullable column with null value
- Type validation: mismatched types
- Length validation: overlong strings rejected
- Empty input handling
- REJECT output structure (errorCode, errorMessage columns)
- Statistics (NB_LINE, NB_LINE_OK, NB_LINE_REJECT) accuracy

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 2 | **ENG-SCC-001**, **ENG-SCC-002** |
| P1 | 5 | **ENG-SCC-003**, **ENG-SCC-004**, **ENG-SCC-005**, **ENG-SCC-006**, **ENG-SCC-007** |
| P2 | 4 | **ENG-SCC-008**, **ENG-SCC-009**, **ENG-SCC-010**, **TEST-SCC-001** |
| P3 | 1 | **ENG-SCC-011** |
| **Total** | **12** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | All 8 superseded |
| Engine (ENG) | 11 | ENG-SCC-001 through ENG-SCC-011 |
| Bug (BUG) | 0 | -- |
| Naming (NAME) | 0 | -- |
| Standards (STD) | 0 | -- |
| Performance (PERF) | 0 | -- |
| Testing (TEST) | 1 | TEST-SCC-001 |

### Cross-Cutting Issues

Engine cross-cutting issues (base class bugs) apply to this component but are tracked centrally:

- `_update_global_map()` crash when globalMap set (base_component.py)
- `_execute_streaming` drops reject data
- `validate_schema` inverted nullable logic

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

1. **ENG-SCC-001 (P0)**: Fix type mapping to use Python types (int, str, float, datetime) instead of Talend types
2. **ENG-SCC-002 (P0)**: Replace iterrows() type coercion with vectorized approach that persists changes

### Short-term (Hardening)

1. **ENG-SCC-003 (P1)**: Implement Custom Defined mode (read CUSTOMER, CHECKCOLS from config)
2. **ENG-SCC-004 (P1)**: Add date validation (fast and strict modes)
3. **ENG-SCC-005 (P1)**: Implement SUB_STRING truncation
4. **ENG-SCC-006 (P1)**: Read ALL_EMPTY_ARE_NULL from config instead of hardcoding
5. **ENG-SCC-007 (P1)**: Implement IGNORE_TIMEZONE for date validation
6. **TEST-SCC-001 (P2)**: Add engine unit tests

### Long-term (Optimization)

1. **ENG-SCC-008-011 (P2-P3)**: Error code variety, message format, byte-length check, per-column empty-null

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Official Talend docs | [tSchemaComplianceCheck (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/validation/tschemacompliancecheck-standard-properties) | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | [tSchemaComplianceCheck_java.xml](https://github.com/nicosommi/talaxie-tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tSchemaComplianceCheck/tSchemaComplianceCheck_java.xml) | Component definition XML |
| Engine source | `src/v1/engine/components/transform/schema_compliance_check.py` | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/transform/schema_compliance_check.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_schema_compliance_check.py` | Test coverage analysis |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `base_component.py:_execute_streaming` | Streaming mode drops reject data |
| XCUT-003 | `base_component.py:validate_schema` | Inverted nullable logic |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after gold-standard rewrite (converter + tests + audit)*
