# Audit Report: tContextLoad / ContextLoad

> **Audited**: 2026-04-03
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tContextLoad` |
| **V1 Engine Class** | `ContextLoad` |
| **Engine File** | `src/v1/engine/components/context/context_load.py` (348 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/context/context_load.py` (107 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tContextLoad")` decorator-based dispatch |
| **Registry Aliases** | `tContextLoad` |
| **Category** | Context / Misc |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/context/context_load.py` | Engine implementation (348 lines) |
| `src/converters/talend_to_v1/components/context/context_load.py` | Converter class (107 lines) |
| `tests/converters/talend_to_v1/components/test_context_load.py` | Converter tests |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |
| `src/v1/engine/context_manager.py` | ContextManager for context variable storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 14 of 14 params extracted (100%). 6 needs_review entries for engine gaps. DIEONERROR fallback logic. All _java.xml params covered. |
| Engine Feature Parity | **Y** | 0 | 3 | 2 | 1 | Engine reads 6 of 12 config keys. Does not read die_on_error, disable_warnings, disable_error, disable_info, load_new_variable, not_load_old_variable. No warning-level validation. |
| Code Quality | **Y** | 1 | 2 | 2 | 1 | Cross-cutting `_update_global_map()` crash (P0). Row-by-row iterrows() in DataFrame/CSV processing. No `_validate_config()` call. |
| Performance & Memory | **Y** | 0 | 1 | 1 | 0 | Row-by-row iterrows() for DataFrame and CSV input. No streaming support for large context files. |
| Testing | **G** | 0 | 0 | 0 | 0 | Comprehensive converter test suite with 9 test classes per TEST_PATTERN.md. No engine unit tests. |

**Overall: YELLOW -- Converter is production-ready (Green). Engine has significant gaps: 6 config keys are ignored, no warning-level validation, cross-cutting base class bugs.**

**Top Actions**:
1. Engine: Read and honor `die_on_error` config key (ENG-CL-001)
2. Engine: Implement `load_new_variable` / `not_load_old_variable` warning validation (ENG-CL-002, ENG-CL-003)
3. Engine: Read and honor `disable_warnings` / `disable_error` / `disable_info` config keys (ENG-CL-004, ENG-CL-005, ENG-CL-006)
4. Engine: Fix cross-cutting `_update_global_map()` crash (BUG-CL-001)
5. Engine: Replace row-by-row iterrows() with vectorized operations (PERF-CL-001)

---

## 3. Talend Feature Baseline

### What tContextLoad Does

`tContextLoad` modifies dynamically the values of the active context at runtime. It receives an input flow containing key-value pairs (typically from a file reader like `tFileInputDelimited`, a database input like `tMySqlInput`, or any upstream component producing rows with `key` and `value` columns) and overrides the current context variable values with the values from the incoming flow.

The component performs two validation controls:
1. **LOAD_NEW_VARIABLE**: Controls behavior when the incoming flow contains variables NOT defined in the job context (unknown keys). Can emit ERROR, WARNING, or INFO level messages.
2. **NOT_LOAD_OLD_VARIABLE**: Controls behavior when context variables defined in the job are NOT present in the incoming flow (missing keys). Can emit ERROR, WARNING, or INFO level messages.

These validations are controlled by the DISABLE_ERROR, DISABLE_WARNINGS, and DISABLE_INFO flags which selectively suppress message levels. The component also supports an implicit context loading mechanism at the job level, which uses CONTEXTFILE, FORMAT, FIELDSEPARATOR, and CSV_SEPARATOR parameters -- these are NOT defined in the _java.xml but appear in .item file exports.

**Source**: Talaxie GitHub tdi-studio-se repository (_java.xml), Talend official documentation
**Component family**: Misc (Context)
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in component)

### 3.1 Basic Settings (from _java.xml)

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | key/value columns | Read-only schema with `key` (String) and `value` (String) columns |
| 2 | Load New Variable | `LOAD_NEW_VARIABLE` | CLOSED_LIST | `WARNING` | Behavior when incoming flow has variables not in job context. Items: ERROR, WARNING, INFO |
| 3 | Not Load Old Variable | `NOT_LOAD_OLD_VARIABLE` | CLOSED_LIST | `WARNING` | Behavior when job context has variables not in incoming flow. Items: ERROR, WARNING, INFO |
| 4 | Print Operations | `PRINT_OPERATIONS` | CHECK | `false` | Log each context variable assignment. Dynamic settings enabled. |
| 5 | Disable Error | `DISABLE_ERROR` | CHECK | `false` | Suppress ERROR-level validation messages |
| 6 | Disable Warnings | `DISABLE_WARNINGS` | CHECK | `true` | Suppress WARNING-level validation messages. Note: default is `true` (warnings suppressed by default). |
| 7 | Disable Info | `DISABLE_INFO` | CHECK | `true` | Suppress INFO-level validation messages. Note: default is `true` (info suppressed by default). |
| 8 | Die On Error | `DIEONERROR` | CHECK | `false` | Stop entire job on error. Note: XML name has NO underscore. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| F1 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Capture processing metadata for tStatCatcher. Framework param. |
| F2 | Label | `LABEL` | TEXT | `""` | Designer canvas label. No runtime impact. Framework param. |

### 3.3 Implicit Context Load Parameters (NOT in _java.xml)

These parameters are NOT defined in the tContextLoad `_java.xml`. They come from Talend's Implicit Context Load feature, configured at the job level. The converter extracts them from .item file exports where they appear as component parameters when implicit context loading is enabled.

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| IC1 | Context File | `CONTEXTFILE` | TEXT | `""` | Path to context file for implicit loading |
| IC2 | Format | `FORMAT` | TEXT | `""` | File format (properties, csv) |
| IC3 | Field Separator | `FIELDSEPARATOR` | TEXT | `";"` | Key-value delimiter for file-based loading |
| IC4 | CSV Separator | `CSV_SEPARATOR` | TEXT | `";"` | Separator for CSV format |
| IC5 | Error If Not Exists | `ERROR_IF_NOT_EXISTS` | CHECK | `true` | Raise error if context file not found |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` | Input | Row > Main | Incoming key-value pairs to load as context variables |
| `FLOW` | Output | Row > Main | Pass-through of loaded data |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful context loading |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on context loading failure |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Component-level success |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Component-level error |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_CONTEXT_LOADED` | Integer | After execution | Number of context variables loaded |

### 3.6 Behavioral Notes

1. **DIEONERROR has no underscore** in the _java.xml name. The converter checks both `DIEONERROR` and `DIE_ON_ERROR` (fallback) because .item exports may use either form.
2. **DISABLE_WARNINGS defaults to `true`** (not `false`), meaning warnings are suppressed by default. This is counter-intuitive.
3. **DISABLE_INFO defaults to `true`** -- info messages also suppressed by default.
4. **DISABLE_ERROR defaults to `false`** -- error messages are shown by default.
5. **LOAD_NEW_VARIABLE and NOT_LOAD_OLD_VARIABLE** are CLOSED_LIST types with items ERROR, WARNING, INFO -- they control the severity level of validation messages, not boolean flags.
6. **Implicit context load params** (CONTEXTFILE, FORMAT, FIELDSEPARATOR, CSV_SEPARATOR, ERROR_IF_NOT_EXISTS) are NOT in _java.xml but appear in .item exports when the job uses Talend's Implicit Context Load feature.
7. **Schema is read-only** with fixed `key` and `value` columns -- utility component, no data flow schema transformation.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter is implemented as `ContextLoadConverter` in `src/converters/talend_to_v1/components/context/context_load.py`. It uses `@REGISTRY.register("tContextLoad")` for dispatch. All parameter extraction uses the base class helpers (`_get_str`, `_get_bool`).

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `CONTEXTFILE` | Yes | `filepath` | Implicit context load param. Default `""`. |
| 2 | `FORMAT` | Yes | `format` | Implicit context load param. Default `""`. |
| 3 | `FIELDSEPARATOR` | Yes | `delimiter` | Implicit context load param. Default `";"`. |
| 4 | `CSV_SEPARATOR` | Yes | `csv_separator` | Implicit context load param. Default `";"`. |
| 5 | `PRINT_OPERATIONS` | Yes | `print_operations` | Default `false`. |
| 6 | `ERROR_IF_NOT_EXISTS` | Yes | `error_if_not_exists` | Implicit context load param. Default `true`. |
| 7 | `DIEONERROR` | Yes | `die_on_error` | Primary: `DIEONERROR` (canonical _java.xml name, no underscore). Fallback: `DIE_ON_ERROR` (.item variant). Default `false`. |
| 8 | `DISABLE_ERROR` | Yes | `disable_error` | Default `false`. |
| 9 | `DISABLE_WARNINGS` | Yes | `disable_warnings` | Default `true` (per _java.xml). |
| 10 | `DISABLE_INFO` | Yes | `disable_info` | Default `true` (per _java.xml). |
| 11 | `LOAD_NEW_VARIABLE` | Yes | `load_new_variable` | CLOSED_LIST. Default `"WARNING"`. |
| 12 | `NOT_LOAD_OLD_VARIABLE` | Yes | `not_load_old_variable` | CLOSED_LIST. Default `"WARNING"`. |
| 13 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param. Default `false`. |
| 14 | `LABEL` | Yes | `label` | Framework param. Default `""`. |

**Summary**: 14 of 14 parameters extracted (100%).

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| Schema | N/A | Utility component -- schema is hardcoded as `{"input": [], "output": []}`. tContextLoad has a fixed key/value schema, not a dynamic one. |

### 4.3 Expression Handling

The converter uses `_get_str()` which strips surrounding quotes from string values. Context variable expressions (`context.var`) and Java expressions (`{{java}}`) in parameter values are preserved as-is for runtime resolution by the engine.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No open converter issues. All previous CONV-CL issues resolved. |

### 4.5 Needs Review Entries

The converter emits 6 needs_review entries for config keys that the engine does not read:

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | `die_on_error` | Engine always raises on error; does not honor `die_on_error=false` to log and continue | engine_gap |
| 2 | `disable_warnings` | Engine has no warning-level message filtering; config key is ignored | engine_gap |
| 3 | `disable_error` | Engine has no error-level message filtering; config key is ignored | engine_gap |
| 4 | `disable_info` | Engine has no info-level message filtering; config key is ignored | engine_gap |
| 5 | `load_new_variable` | Engine does not validate unknown keys in incoming flow against job context | engine_gap |
| 6 | `not_load_old_variable` | Engine does not validate missing context keys against incoming flow | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Load from properties file | **Yes** | Medium | `_load_properties_context()` line 246 | Works but delimiter default is `=` (Talend default is `;`). No `!` comment prefix support. |
| 2 | Load from CSV file | **Yes** | Medium | `_load_csv_context()` line 203 | Uses pandas `read_csv()`. Requires `key`/`value` columns. |
| 3 | Load from DataFrame input | **Yes** | High | `_process_dataframe_input()` line 106 | Processes incoming flow rows with key/value columns. |
| 4 | Print operations | **Yes** | High | Lines 141, 239, 285 | Logs via `logger.info()` when `print_operations=True`. |
| 5 | Error if not exists | **Yes** | High | `_process_file_input()` line 179 | Raises `FileNotFoundError` or logs warning. |
| 6 | Die on error | **No** | N/A | Not implemented | Engine does not read `die_on_error` from config. Errors always raise. |
| 7 | Disable warnings | **No** | N/A | Not implemented | Engine does not read `disable_warnings` from config. |
| 8 | Disable error | **No** | N/A | Not implemented | Engine does not read `disable_error` from config. |
| 9 | Disable info | **No** | N/A | Not implemented | Engine does not read `disable_info` from config. |
| 10 | Load new variable validation | **No** | N/A | Not implemented | Engine does not validate unknown keys in input. |
| 11 | Not load old variable validation | **No** | N/A | Not implemented | Engine does not validate missing context keys. |
| 12 | Type preservation from context | **Yes** | Medium | `_determine_value_type()` line 294 | Uses existing context type or `type` column, defaults to `id_String`. Medium because NaN in `type` column is not handled (returns NaN instead of fallback). |
| 13 | Quote stripping in properties | **Yes** | High | `_clean_value()` line 319 | Removes surrounding single/double quotes. |
| 14 | Context variable update via ContextManager | **Yes** | High | `self.context_manager.set()` throughout | Core functionality works correctly. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-CL-001 | **P1** | Engine does not read `die_on_error` from config. Errors always raise exceptions rather than being controlled by this flag. In Talend, `die_on_error=false` would log the error and continue. |
| ENG-CL-002 | **P1** | Engine does not implement `load_new_variable` validation. Talend checks incoming keys against job context and reports unknown variables at the configured level (ERROR/WARNING/INFO). |
| ENG-CL-003 | **P1** | Engine does not implement `not_load_old_variable` validation. Talend checks job context variables against incoming flow and reports missing variables. |
| ENG-CL-004 | **P2** | Engine does not read `disable_warnings` from config. Warning messages cannot be selectively suppressed. |
| ENG-CL-005 | **P2** | Engine does not read `disable_error` / `disable_info` from config. Error and info messages cannot be selectively suppressed. |
| ENG-CL-006 | **P3** | Engine default mismatches vs Talend: (1) Properties delimiter defaults to `=` in engine but `;` in _java.xml. (2) CSV separator defaults to `,` in engine but `;` in _java.xml. Both mismatches only matter when these values are not explicitly set in config. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_CONTEXT_LOADED` | Yes | Yes | `self.global_map.put()` in `_update_component_stats()` line 347 | Matches Talend behavior. |
| `{id}_NB_LINE` | Unknown | Partial | Via `_update_stats()` in base class | May not be set due to `_update_global_map()` crash. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-CL-001 | **P0** | `base_component.py:304` | CROSS-CUTTING: `_update_global_map()` references undefined `value` variable. Crashes ALL components when globalMap is set. Results lost, status stuck at RUNNING. |
| BUG-CL-002 | **P1** | `context_load.py:129-131` | Row-by-row `iterrows()` in `_process_dataframe_input()` stringifies all values via `str(row['value'])`. NaN values become `"nan"` string, silently corrupting context variables. Should use `pd.isna()` check. |
| BUG-CL-003 | **P1** | `context_load.py:227-229` | Same NaN-to-string issue in `_load_csv_context()`. `str(row['value'])` converts NaN to `"nan"`. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-CL-001 | **P2** | Engine class docstring says `ContextLoad Component` (OK), but file variable naming uses `file_format` internally while config key is `format`. Minor inconsistency. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-CL-001 | **P2** | "No print statements in production code" | Uses f-strings in logger calls (acceptable) but debug logging at line 120 logs full DataFrame `{input_data}` which may be huge. |

### 6.4 Debug Artifacts

None found. All logging uses `logger` module properly.

### 6.5 Security

No concerns identified. File paths come from config (not user input). No `eval()` or `exec()` usage.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Correct: `logger = logging.getLogger(__name__)` at module level |
| Level usage | Good: `debug` for verbose, `info` for operations, `warning` for missing files, `error` for exceptions |
| Sensitive data | **Caution**: `print_operations` logs context variable values which may contain passwords. This matches Talend behavior but should be noted. |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ValueError` and `FileNotFoundError` -- standard Python exceptions |
| Exception chaining | `_process_file_input()` re-raises original exception after logging (line 200-201). No chaining via `from`. |
| die_on_error handling | **Not implemented** -- engine always raises on error regardless of config |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have full type annotations |
| Parameter types | Complete with `Optional`, `Dict`, `Any` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-CL-001 | **P1** | `_process_dataframe_input()` and `_load_csv_context()` use row-by-row `iterrows()` for processing. For large DataFrames/CSV files with many context variables, this is O(n) with high constant factor. Should use vectorized pandas operations (`df.set_index('key')['value'].to_dict()`). |
| PERF-CL-002 | **P2** | `_load_csv_context()` reads entire CSV into memory via `pd.read_csv()`. For very large context files this could be memory-intensive, though context files are typically small. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Not applicable -- context files are typically small |
| Memory threshold | No threshold configured. Full file loaded into memory. |
| Large data handling | Adequate for typical context files (< 1000 variables). Would struggle with millions of rows due to iterrows(). |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 9 classes | `tests/converters/talend_to_v1/components/test_context_load.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| -- | -- | Converter tests are comprehensive per TEST_PATTERN.md. No open test gaps for converter. |

### 8.3 Recommended Test Cases

Engine tests (not converter -- converter tests are complete):
- Happy path: Load from properties file with key=value pairs
- Happy path: Load from CSV file with key,value columns
- Happy path: Load from DataFrame input
- Edge case: Empty DataFrame (0 rows)
- Edge case: NaN values in key/value columns
- Edge case: File not found with error_if_not_exists=True and False
- Edge case: Properties file with comments (#, //)
- Error path: Missing key/value columns in DataFrame
- Error path: Missing key/value columns in CSV

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 1 | **BUG-CL-001** |
| P1 | 6 | **ENG-CL-001**, **ENG-CL-002**, **ENG-CL-003**, **BUG-CL-002**, **BUG-CL-003**, **PERF-CL-001** |
| P2 | 5 | **ENG-CL-004**, **ENG-CL-005**, **NAME-CL-001**, **STD-CL-001**, **PERF-CL-002** |
| P3 | 1 | **ENG-CL-006** |
| **Total** | **13** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Engine (ENG) | 6 | ENG-CL-001, ENG-CL-002, ENG-CL-003, ENG-CL-004, ENG-CL-005, ENG-CL-006 |
| Bug (BUG) | 3 | BUG-CL-001, BUG-CL-002, BUG-CL-003 |
| Naming (NAME) | 1 | NAME-CL-001 |
| Standards (STD) | 1 | STD-CL-001 |
| Performance (PERF) | 2 | PERF-CL-001, PERF-CL-002 |

### Cross-Cutting Issues

BUG-CL-001 is the cross-cutting `_update_global_map()` crash that affects ALL v1 engine components. It is tracked canonically in `docs/v1/audit/CROSS_CUTTING_ISSUES.md`.

---

## 10. Recommendations

### Immediate (Before Production)

1. **BUG-CL-001 (P0)**: Fix `_update_global_map()` undefined `value` variable in `base_component.py:304`. This is cross-cutting and blocks ALL components.

### Short-term (Hardening)

2. **ENG-CL-001 (P1)**: Implement `die_on_error` config reading in engine. When `false`, catch exceptions and log rather than re-raising.
3. **ENG-CL-002 (P1)**: Implement `load_new_variable` validation -- compare incoming keys against job context variables.
4. **ENG-CL-003 (P1)**: Implement `not_load_old_variable` validation -- compare job context variables against incoming keys.
5. **BUG-CL-002/003 (P1)**: Add `pd.isna()` checks before stringifying values in `iterrows()` loops.
6. **PERF-CL-001 (P1)**: Replace `iterrows()` with vectorized pandas operations for DataFrame/CSV processing.

### Long-term (Optimization)

7. **ENG-CL-004/005 (P2)**: Implement disable_warnings/disable_error/disable_info filtering.
8. **ENG-CL-006 (P3)**: Align default delimiter between engine and Talend.
9. Add engine unit tests for ContextLoad component.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub _java.xml | `https://github.com/Talaxie/tdi-studio-se/` (tContextLoad_java.xml) | Parameter definitions, defaults, types |
| Engine source | `src/v1/engine/components/context/context_load.py` | Feature parity analysis (348 lines) |
| Converter source | `src/converters/talend_to_v1/components/context/context_load.py` | Converter audit (107 lines) |
| Test source | `tests/converters/talend_to_v1/components/test_context_load.py` | Test coverage analysis |
| Base class | `src/v1/engine/base_component.py` | Cross-cutting bug analysis |
| Context manager | `src/v1/engine/context_manager.py` | Context variable storage analysis |
| METHODOLOGY.md | `docs/v1/standards/METHODOLOGY.md` | Scoring framework, edge-case checklist |
| AUDIT_REPORT_TEMPLATE.md | `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` | Report structure |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- ContextLoad's `_update_component_stats()` calls `_update_stats()` which triggers the crash, losing the `NB_CONTEXT_LOADED` stat. |
| XCUT-002 | `base_component.py:351` | `validate_schema` inverted nullable logic -- not directly applicable since ContextLoad uses hardcoded empty schema, but would affect any future schema validation. |
| XCUT-003 | `base_component.py:267-278` | `_execute_streaming` drops reject DataFrames -- ContextLoad returns only `main` so no reject data lost, but streaming mode could lose stats. |

### Edge-Case Checklist Results

| Check | Result | Details |
|-------|--------|---------|
| NaN handling | **FAIL** | `str(row['value'])` converts NaN to `"nan"` string (BUG-CL-002, BUG-CL-003) |
| Empty strings in config keys | PASS | `filepath=""` handled with explicit check and warning |
| Empty DataFrame input (0 rows) | PASS | Returns `{'main': pd.DataFrame()}` without error |
| HYBRID streaming mode | N/A | ContextLoad is not typically used in streaming mode |
| `_update_global_map()` crash | **FAIL** | Cross-cutting P0 bug (BUG-CL-001) |
| Type demotion through iterrows | **FAIL** | `iterrows()` may demote Decimal/datetime types during value processing |
| `validate_schema` nullable logic | N/A | ContextLoad uses hardcoded empty schema |
| `_validate_config()` called | PASS (N/A) | ContextLoad does not define `_validate_config()` |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after full rewrite per D-12*
