# Audit Report: tSetGlobalVar / SetGlobalVar

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report is scoped to the v1 engine exclusively

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tSetGlobalVar` |
| **V1 Engine Class** | `SetGlobalVar` |
| **Engine File** | `src/v1/engine/components/file/set_global_var.py` (153 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/set_global_var.py` (110 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tSetGlobalVar")` decorator-based dispatch |
| **Registry Aliases** | `tSetGlobalVar` |
| **Category** | Custom Code / Global Variable |
| **Complexity** | Low -- utility component with 1 TABLE parameter (VARIABLES), no data flow schema |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/set_global_var.py` | Engine implementation (153 lines) |
| `src/converters/talend_to_v1/components/file/set_global_var.py` | Converter class (110 lines) |
| `tests/converters/talend_to_v1/components/test_set_global_var.py` | Converter tests (23 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 1 TABLE param (VARIABLES with KEY/VALUE stride-2) + 2 framework params extracted; `_build_component_dict` pattern |
| Engine Feature Parity | **G** | 0 | 0 | 0 | 0 | Reads `variables` (lowercase) with {key,value} shape; fallback accepts VARIABLES/name/VALUE; die_on_error supported; pass-through correct; NB_LINE always 0 |
| Code Quality | **G** | 0 | 0 | 0 | 0 | `_validate_config()` raises ConfigurationError ✅; % logger formatting ✅; pandas import removed ✅; @REGISTRY.register() decorator ✅ |
| Performance & Memory | **G** | 0 | 0 | 0 | 0 | Lightweight utility; no data processing; unused pandas import removed |
| Testing | **G** | 0 | 0 | 0 | 0 | 23 converter tests across 9 test classes; 26 engine tests across 8 test classes |

**Overall: Green -- Engine fully aligned with converter output; all issues resolved (2026-05-01)**

**Top Actions:** None -- all issues resolved.

---

## 3. Talend Feature Baseline

### What tSetGlobalVar Does

`tSetGlobalVar` sets one or more global variables that can be accessed by other components in the job through the globalMap. This is the standard mechanism in Talend for passing values between subjobs -- a component sets a globalMap variable and a downstream component reads it using a `(String)globalMap.get("key")` expression.

The component has a single unique TABLE parameter (VARIABLES) that contains KEY/VALUE pairs. Each pair defines a variable name and its value. The value can be a literal string, a Java expression, a context variable reference, or a complex expression mixing all three. The component is a utility -- it does not consume or produce rows of data. When connected with an input flow, rows pass through unchanged.

**Source**: [tSetGlobalVar Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tsetglobalvar), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tSetGlobalVar/tSetGlobalVar_java.xml)
**Component family**: Custom Code / Global Variable
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Variables | `VARIABLES` | TABLE (KEY/VALUE stride-2) | `[]` (empty) | Table of key-value pairs. Each row has KEY (variable name) and VALUE (variable value). Values support Java expressions (e.g., `TalendDate.getDate()`) and context references (`context.myVar`). |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 2 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Enables collection of processing metadata for tStatCatcher. |
| 3 | Label | `LABEL` | TEXT | `""` | Text label for the component on the designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Optional input flow. Data passes through unchanged. |
| `FLOW` (Main) | Output | Row > Main | Optional output flow. Same data as input. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Number of rows processed (always 0 for this component since it sets variables, not rows). |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of successful rows (always 0). |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rejected rows (always 0). |
| User-defined keys | Any | After execution | Each KEY/VALUE pair in VARIABLES is set as `globalMap.put(key, value)`. |

### 3.5 Behavioral Notes

1. **VARIABLES TABLE structure**: The TABLE param uses stride-2 with elementRef names `KEY` and `VALUE`. Each consecutive pair of entries forms one variable definition.
2. **Value types**: In Talend Studio, values are Java expressions evaluated at runtime. Literal strings need quotes (`"hello"`), context references use `context.varName`, and Java calls like `TalendDate.getDate()` or `globalMap.get("key")` are evaluated by the Talend runtime.
3. **Java "new " pattern**: Values starting with `new ` (e.g., `new java.util.Date()`) are constructor calls evaluated by the Java runtime.
4. **Pass-through behavior**: When an input flow is connected, data rows pass through unchanged. The component only sets globalMap variables.
5. **NB_LINE always 0**: The component does not count data rows; globalMap statistics are always 0.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses the gold-standard pattern: module-level `_parse_variables()` function with stride-2 TABLE parsing, `_build_component_dict()` wrapper, and per-feature `needs_review` entries for engine gaps.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `VARIABLES` | Yes | `variables` | TABLE stride-2, KEY/VALUE elementRef -> list of {key, value} dicts |
| 2 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Boolean, default `false` |
| 3 | `LABEL` | Yes | `label` | String, default `""` |

**Summary**: 3 of 3 parameters extracted (100%).

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| N/A | N/A | Utility component -- no data flow schema. Schema is `{input: [], output: []}`. |

### 4.3 Expression Handling

Values in the VARIABLES TABLE are stored as-is after quote stripping. Java expressions, context variable references, and complex expressions are preserved in their raw form. The engine is responsible for evaluating them at runtime.

### 4.4 Converter Issues

None. Converter is fully standardized to gold standard pattern.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `variables` | Engine reads `VARIABLES` (uppercase) with `{name, value}` dicts but converter outputs `variables` (lowercase) with `{key, value}` dicts -- runtime mismatch until engine is aligned | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Set globalMap variables | **Yes** | High | `_process()` | Reads `variables` (lowercase) with `{key, value}`; falls back to `VARIABLES`/`name`/`VALUE` for backward compat. |
| 2 | Java / context expression resolution | **Yes** | High | BaseComponent step 3 | `_resolve_expressions()` resolves `{{java}}` markers and `${context.X}` before `_process()` is called. No bespoke heuristics needed. |
| 3 | Pass-through data flow | **Yes** | High | `_process()` | Returns `{"main": input_data}` unchanged. |
| 4 | NB_LINE tracking | **Yes** | High | `_process()` | Always 0 via `_update_stats(0,0,0)` -- matches Talend (utility component, not a row processor). |
| 5 | die_on_error support | **Yes** | High | `_process()` | Per-variable skip or raise depending on `die_on_error` flag. |

### 5.2 Behavioral Differences from Talend

All ENG-SGV issues resolved (2026-05-01). See engine fix note below.

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes (0) | Yes (0) | `_update_stats(0, 0, 0)` | Both always 0 |
| `{id}_NB_LINE_OK` | Yes (0) | Yes (0) | `_update_stats(0, 0, 0)` | Both always 0 |
| `{id}_NB_LINE_REJECT` | Yes (0) | Yes (0) | `_update_stats(0, 0, 0)` | Both always 0 |
| User-defined keys | Yes | Yes | `self.global_map.put(name, value)` | Works for literal strings and "new " expressions |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-SGV-001 | **P0** | `base_component.py:304` | **CROSS-CUTTING**: `_update_global_map()` crashes when globalMap is set. Affects all components. |

### 6.2 Naming Consistency

All NAME-SGV issues resolved (2026-05-01). Engine now reads `variables` (lowercase) with fallback.

### 6.3 Standards Compliance

All STD-SGV issues resolved (2026-05-01). All logger calls use `%` formatting; `_validate_config()` now raises `ConfigurationError` and is called by BaseComponent lifecycle.

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns specific to this component. The Java bridge evaluation for "new " prefix values is handled by the Java bridge with standard exception handling. Other Java expressions are stored as raw strings (no eval/exec).

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- module-level `logger = logging.getLogger(__name__)` |
| Level usage | Good -- info for operations, debug for per-variable detail, warning for failures |
| Sensitive data | Low risk -- variable names logged but values could contain sensitive data in debug mode |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | No custom exceptions -- relies on base class `ComponentExecutionError` |
| Exception chaining | Bare re-raise in outer try/except (line 152) -- loses traceback context |
| die_on_error handling | Not implemented -- all errors propagate |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- `_validate_config() -> List[str]`, `_process(data: Any) -> Dict[str, Any]` |
| Parameter types | Adequate -- standard typing imports used |

---

## 7. Performance & Memory

All PERF-SGV issues resolved (2026-05-01). Unused `pandas` import removed.

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- utility component, no data processing |
| Memory threshold | N/A -- no data buffering |
| Large data handling | N/A -- only sets globalMap variables |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 23 | `tests/converters/talend_to_v1/components/file/test_set_global_var.py` |
| Engine unit tests | 26 | `tests/v1/engine/components/file/test_set_global_var.py` |
| Integration tests | Pass | `tests/converters/talend_to_v1/test_integration.py` (regression guard) |

### 8.2 Engine Test Classes (26 tests)

| Class | Tests | Coverage |
| ------- | ------- | --------- |
| TestRegistration | 2 | Both aliases resolve to SetGlobalVar |
| TestValidateConfig | 5 | Missing key, wrong type, empty list, valid list, uppercase key |
| TestProcessSetsVariables | 4 | Single var, multiple vars, None value, empty list |
| TestLegacyKeyFallback | 3 | VARIABLES key, name field, VALUE field |
| TestPassThrough | 3 | DataFrame unchanged, None input, no mutation |
| TestStatistics | 4 | NB_LINE/OK/REJECT always 0, DataFrame input still 0 |
| TestDieOnError | 4 | Non-dict row raise/skip, missing name raise/skip |
| TestNoGlobalMap | 1 | Runs without global_map (no crash) |

### 8.3 Test Gaps

None -- all recommended cases covered.

---

## 9. Issues Summary

### By Priority (post engine fix 2026-05-01)

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | -- |
| P1 | 0 | -- |
| P2 | 0 | -- |
| P3 | 0 | -- |
| **Total** | **0** | All resolved |

### Cross-Cutting Issues

| Canonical ID | Location | Status |
| ------------- | ---------- | -------- |
| XCUT-001 | `base_component.py` | Resolved in BaseComponent refactor -- no longer affects this component |

---

## 10. Recommendations

All recommendations resolved by engine fix (2026-05-01). No outstanding actions.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Official Talend docs | [tSetGlobalVar Properties](https://help.qlik.com/talend/en-US/components/7.3/tsetglobalvar) | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | [tSetGlobalVar_java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tSetGlobalVar/tSetGlobalVar_java.xml) | Component definition XML, TABLE structure |
| Engine source | `src/v1/engine/components/file/set_global_var.py` | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/file/set_global_var.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_set_global_var.py` | Test coverage analysis |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- affects stats reporting |

---

*Report generated: 2026-04-04*
*Last updated: 2026-05-01 -- Engine rewritten. All 9 issues resolved. 26 engine tests added. Overall upgraded Y -> G.*
