# Audit Report: tUnpivotRow / UnpivotRow

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD REWRITE
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tUnpivotRow` |
| **V1 Engine Class** | `UnpivotRow` |
| **Engine File** | `src/v1/engine/components/transform/unpivot_row.py` (234 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/unpivot_row.py` (89 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tUnpivotRow")` decorator-based dispatch |
| **Registry Aliases** | `UnpivotRow`, `tUnpivotRow` |
| **Category** | Processing / Transform |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/unpivot_row.py` | Engine implementation (234 lines) |
| `src/converters/talend_to_v1/components/transform/unpivot_row.py` | Converter class (89 lines) |
| `tests/converters/talend_to_v1/components/test_unpivot_row.py` | Converter tests (28 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 6/6 params extracted (100%). ROW_KEYS TABLE stride-1, INCLUDE_EMPTY_VALUES, pivot_key/pivot_value derived. 0 needs_review (engine reads all). Phantom params removed. |
| Engine Feature Parity | **Y** | 1 | 4 | 3 | 1 | Output schema pollution; no String coercion; no die_on_error; no reject flow; extra columns in output |
| Code Quality | **G** | 0 | 0 | 1 | 0 | Gold standard converter with _build_component_dict, passthrough schema, clean TABLE parsing |
| Performance & Memory | **Y** | 0 | 1 | 4 | 1 | Unnecessary full copy; redundant no-op filter; chained DataFrame copies; expensive sort |
| Testing | **Y** | 0 | 0 | 1 | 0 | 28 converter tests (Green); no engine unit tests (per D-89) |

**Overall: YELLOW -- Engine performance and feature gaps prevent Green; converter is gold standard**

**Top Actions**:

1. Fix output schema pollution -- extra columns from input appear in unpivoted output (P0)
2. Add String type coercion for pivot_value column (P1)
3. Add die_on_error parameter support (P1)
4. Add reject flow for error rows (P1)
5. Add engine unit tests

---

## 3. Talend Feature Baseline

### What tUnpivotRow Does

tUnpivotRow transforms wide-format data into long-format (tall) data by unpivoting columns into rows. Given a set of identifier columns (ROW_KEYS), all remaining columns are melted into key-value pairs. Each non-key column becomes a row with the column name in the `pivot_key` column and the cell value in the `pivot_value` column. The identifier columns are replicated across all output rows.

A typical use case is transforming a financial dataset where columns represent monthly values (Jan, Feb, Mar) into rows with a "month" key column and "amount" value column, while preserving identifier columns like account_id and currency.

This is a community component from the michimau/talend_components repository. The `_java.xml` definition file returns 404, so parameter documentation relies on the community source code and .item file exports. Confidence level: MEDIUM.

**Source**: [michimau/talend_components (GitHub)](https://github.com/michimau/talend_components), .item file exports
**Component family**: Processing / Transform
**Available in**: Talend Open Studio (community plugin), Talend Data Integration (community plugin)
**Required JARs**: None (community Java component)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | Schema editor | -- | Column definitions. Output schema has fixed columns `pivot_key` and `pivot_value` defined by the SCHEMA, plus the ROW_KEYS identifier columns. |
| 2 | Row Keys | `ROW_KEYS` | TABLE (stride-1, COLUMN) | `[]` | List of column names to preserve as identifier columns. TABLE entries use elementRef `COLUMN`. All other columns will be unpivoted. |
| 3 | Include Empty Values | `INCLUDE_EMPTY_VALUES` | CHECK | `true` | Whether to include output rows for cells with null/empty values. When false, null values are dropped from the unpivoted result. |

### 3.2 Derived Parameters

| # | Parameter | Config Key | Default | Description |
| --- | ----------- | ----------- | --------- | ------------- |
| 1 | Pivot Key Column Name | `pivot_key` | `"pivot_key"` | Name of the output column containing original column names. Fixed by the component's SCHEMA definition, not a user-editable parameter. |
| 2 | Pivot Value Column Name | `pivot_value` | `"pivot_value"` | Name of the output column containing cell values. Fixed by the component's SCHEMA definition, not a user-editable parameter. |

### 3.3 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| F1 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Capture processing metadata for tStatCatcher. |
| F2 | Label | `LABEL` | TEXT | `""` | User label for the component. |

### 3.4 Phantom Parameters (NOT in _java.xml / community source)

| Parameter | Source | Status |
| ----------- | -------- | -------- |
| `PIVOT_COLUMN` | Old converter only | **REMOVED** -- not a real component parameter; column names are derived from schema |
| `VALUE_COLUMN` | Old converter only | **REMOVED** -- not a real component parameter |
| `GROUP_BY_COLUMNS` | Old converter only | **REMOVED** -- ROW_KEYS is the correct parameter name |
| `DIE_ON_ERROR` | Engine code only | **REMOVED** -- not in community source |

### 3.5 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Input data to unpivot |
| `FLOW` (Main) | Output | Row > Main | Unpivoted rows with pivot_key, pivot_value, and row_key columns |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires on successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on error |

### 3.6 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total input rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Total output rows produced |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Always 0 (no reject flow) |

### 3.7 Behavioral Notes

1. **ROW_KEYS defines the pivot boundary**: Columns listed in ROW_KEYS are preserved as-is; all other columns become rows. If ROW_KEYS is empty, no identifier columns are preserved and the operation may fail.
2. **Output column names are fixed**: The pivot_key and pivot_value column names come from the component's SCHEMA definition, not from user configuration. They default to "pivot_key" and "pivot_value".
3. **INCLUDE_EMPTY_VALUES defaults to true**: Unlike many boolean params that default false, this defaults to true -- empty/null values produce output rows by default.
4. **Community component**: This is not a standard Talend component. The _java.xml file is not available from Talaxie GitHub (404). Parameter documentation is based on the community source code.
5. **All values coerced to String**: The pivot_value column contains string representations of all cell values regardless of original type.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `@REGISTRY.register("tUnpivotRow")` decorator-based dispatch and the `_build_component_dict` wrapper pattern. ROW_KEYS TABLE is parsed inline with stride-1 (COLUMN elementRef). The converter produces 0 needs_review entries because the engine reads all config params.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `ROW_KEYS` | Yes | `row_keys` | TABLE stride-1, COLUMN elementRef. Quote-stripped. Default `[]` |
| 2 | `INCLUDE_EMPTY_VALUES` | Yes | `include_empty_values` | CHECK. Default `True` |
| 3 | (derived) | Yes | `pivot_key` | Fixed `"pivot_key"` matching engine default |
| 4 | (derived) | Yes | `pivot_value` | Fixed `"pivot_value"` matching engine default |
| F1 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework. Default `False` |
| F2 | `LABEL` | Yes | `label` | Framework. Default `""` |

**Summary**: 6 of 6 parameters extracted (100%). 0 needs_review entries.

### 4.2 Schema Extraction

Transform passthrough pattern: input == output. Both populated from FLOW connector schema via `_parse_schema(node)`.

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | From SchemaColumn.name |
| `type` | Yes | Converted via `convert_type()` |
| `nullable` | Yes | Boolean |
| `key` | Yes | Boolean |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by base class |

### 4.3 Expression Handling

No special expression handling required. ROW_KEYS TABLE values are column names (not expressions). INCLUDE_EMPTY_VALUES is a boolean CHECK -- no expression support needed.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| ~~CONV-UPR-001~~ | ~~P1~~ | **SUPERSEDED** -- Old `parse_unpivot_row()` replaced by `talend_to_v1` converter |
| ~~CONV-UPR-002~~ | ~~P1~~ | **SUPERSEDED** -- Hardcoded business column names removed |
| ~~CONV-UPR-003~~ | ~~P0~~ | **SUPERSEDED** -- Missing INCLUDE_EMPTY_VALUES now extracted |
| ~~CONV-UPR-004~~ | ~~P1~~ | **SUPERSEDED** -- Config key mismatches fixed |

### 4.5 Needs Review Entries

None. The engine reads all 4 unique config params (`row_keys`, `pivot_key`, `pivot_value`, `include_empty_values`). Framework params are exempt from needs_review per convention.

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Unpivot (melt) operation | **Yes** | High | `_process()` line 152-164 | Uses pandas `melt()` -- correct behavior |
| 2 | ROW_KEYS identifier columns | **Yes** | High | `_process()` line 124 | `id_vars=row_keys` in melt |
| 3 | Include empty values filter | **Yes** | High | `_process()` line 196-200 | `dropna()` when `include_empty_values=False` |
| 4 | Custom pivot_key column name | **Yes** | High | `_process()` line 126 | `var_name=pivot_key_column` |
| 5 | Custom pivot_value column name | **Yes** | High | `_process()` line 127 | `value_name=pivot_value_column` |
| 6 | Empty input handling | **Yes** | Medium | `_process()` line 115-118 | Returns empty DataFrame but loses column schema |
| 7 | String type coercion | **No** | N/A | -- | Talend coerces all pivot_value to String; engine preserves original types |
| 8 | die_on_error | **No** | N/A | -- | Not implemented; always raises on error |
| 9 | Reject flow | **No** | N/A | -- | No reject output for error rows |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-UPR-001 | **P0** | **Output schema pollution**: Engine adds all original columns to output with None values (lines 190-193). Talend output contains only row_keys + pivot_key + pivot_value |
| ENG-UPR-002 | **P1** | **No String coercion**: Talend converts all pivot_value to String. Engine preserves original types (int, float, etc.) |
| ENG-UPR-003 | **P1** | **Missing die_on_error**: Engine always raises ValueError on invalid input. Should fall back to empty output when die_on_error=False |
| ENG-UPR-004 | **P1** | **Missing reject flow**: No REJECT output for error rows |
| ENG-UPR-005 | **P1** | **Column reordering**: Engine puts pivot_key, pivot_value first; Talend preserves schema order |
| ENG-UPR-006 | **P2** | **Empty DataFrame loses schema**: `pd.DataFrame()` returned for empty input loses column metadata |
| ENG-UPR-007 | **P2** | **_original_order column collision**: Temporary column `_original_order` could collide with input data column of same name |
| ENG-UPR-008 | **P2** | **Redundant filter**: Line 175 `isin(columns_to_unpivot)` is a no-op after melt -- melt only produces rows for value_vars |
| ENG-UPR-009 | **P3** | **Sort by column name**: Rows sorted by pivot_key within each original row -- Talend uses schema column order |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` line 204 | Input row count |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` line 204 | Output row count |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` line 204 | Always 0 |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-UPR-001 | **P2** | `unpivot_row.py:175` | **Redundant filter** -- `isin(columns_to_unpivot)` after melt is always true. No-op that wastes cycles. |

### 6.2 Naming Consistency

No naming issues found in the converter. Engine uses consistent naming.

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-UPR-001 | **P2** | "Use ConfigurationError not ValueError" | Engine raises `ValueError` instead of `ConfigurationError` for missing row_keys |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified. Component operates on in-memory DataFrames only.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- `logging.getLogger(__name__)` |
| Level usage | Good -- info for start/end, debug for config details, error for failures |
| Sensitive data | No sensitive data logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Uses ValueError -- should use ConfigurationError |
| Exception chaining | Good -- raises original exception |
| die_on_error handling | Missing -- always raises |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- typed parameters and return types |
| Parameter types | Good -- Dict, List, Optional typed |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-UPR-001 | **P1** | **Full copy of input**: `input_data.copy()` at line 158 duplicates entire DataFrame before melt. Could melt directly. |
| PERF-UPR-002 | **P2** | **Redundant sort**: Lines 167-168 sort by `_original_order` + `pivot_key_column`. Melt preserves row order -- sort is unnecessary overhead. |
| PERF-UPR-003 | **P2** | **Chained DataFrame copies**: Multiple filter/reorder operations create intermediate DataFrames. Could pipeline operations. |
| PERF-UPR-004 | **P2** | **No-op filter**: Line 175 filtering by `isin(columns_to_unpivot)` does nothing -- melt already limits to value_vars. |
| PERF-UPR-005 | **P3** | **Expensive column reordering**: Lines 179-181 rebuild column list for reorder. Minor overhead. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not streaming-safe -- HYBRID mode would break due to stateful unpivot across chunks |
| Memory threshold | 2x input memory due to full copy + melt output |
| Large data handling | Adequate for medium datasets; large datasets may hit memory limits |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 28 | `tests/converters/talend_to_v1/components/test_unpivot_row.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None (covered by regression guard) |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-UPR-001 | **P2** | No engine unit tests -- engine behavior, empty input, error paths untested. Converter tests are Green per D-89 but engine tests missing. |

### 8.3 Recommended Test Cases

- Engine: Basic unpivot with 3 columns, 2 row_keys
- Engine: include_empty_values=False filters null values
- Engine: Empty input returns empty DataFrame
- Engine: Missing row_key column raises appropriate error
- Engine: Single row_key, single value column (minimal case)
- Engine: All columns as row_keys (nothing to unpivot)

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **ENG-UPR-001** |
| P1 | 5 | **ENG-UPR-002**, **ENG-UPR-003**, **ENG-UPR-004**, **ENG-UPR-005**, **PERF-UPR-001** |
| P2 | 6 | **ENG-UPR-006**, **ENG-UPR-007**, **ENG-UPR-008**, **BUG-UPR-001**, **STD-UPR-001**, **PERF-UPR-002**, **PERF-UPR-003**, **PERF-UPR-004** |
| P3 | 2 | **ENG-UPR-009**, **PERF-UPR-005** |
| **Total** | **14** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | All superseded |
| Engine (ENG) | 9 | ENG-UPR-001 through ENG-UPR-009 |
| Bug (BUG) | 1 | BUG-UPR-001 |
| Standards (STD) | 1 | STD-UPR-001 |
| Performance (PERF) | 5 | PERF-UPR-001 through PERF-UPR-005 |
| Testing (TEST) | 1 | TEST-UPR-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `base_component.py:351` | `validate_schema` inverted nullable logic |

---

## 10. Recommendations

### Immediate (Before Production)

1. **ENG-UPR-001 (P0)**: Fix output schema pollution -- output should contain only row_keys + pivot_key + pivot_value columns, not all original columns

### Short-term (Hardening)

1. **ENG-UPR-002 (P1)**: Add String type coercion for pivot_value column
2. **ENG-UPR-003 (P1)**: Add die_on_error support -- fall back to empty output on error
3. **ENG-UPR-004 (P1)**: Add reject flow output
4. **ENG-UPR-005 (P1)**: Preserve Talend schema column order in output
5. **PERF-UPR-001 (P1)**: Remove unnecessary `input_data.copy()` -- melt directly

### Long-term (Optimization)

1. **PERF-UPR-002 (P2)**: Remove redundant sort operation
2. **STD-UPR-001 (P2)**: Use ConfigurationError instead of ValueError
3. **TEST-UPR-001 (P2)**: Add engine unit tests
4. **ENG-UPR-009 (P3)**: Align row sort order with Talend schema column order

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| michimau/talend_components | `<https://github.com/michimau/talend_components`> | Community component source code |
| .item file exports | Local Talend Studio exports | ROW_KEYS TABLE structure, parameter names |
| Engine source | `src/v1/engine/components/transform/unpivot_row.py` | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/transform/unpivot_row.py` | Converter audit |
| Converter tests | `tests/converters/talend_to_v1/components/test_unpivot_row.py` | Test coverage review |

## Appendix B: Engine Config Key Mapping

| Config Key | Engine Reads? | Engine Location | Notes |
| ------------ | -------------- | ----------------- | ------- |
| `row_keys` | Yes | `_process()` line 124 | Used as `id_vars` in melt |
| `pivot_key` | Yes | `_process()` line 125 | Used as `var_name` in melt |
| `pivot_value` | Yes | `_process()` line 126 | Used as `value_name` in melt |
| `include_empty_values` | Yes | `_process()` line 127 | Controls `dropna()` filter |
| `tstatcatcher_stats` | No | -- | Framework param -- base class handles |
| `label` | No | -- | Framework param -- base class handles |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after gold standard rewrite (Phase 13 Plan 04)*
