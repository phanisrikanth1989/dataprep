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
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 1 TABLE param (VARIABLES with KEY/VALUE stride-2) + 2 framework params extracted; `_build_component_dict` pattern; 1 needs_review for engine key/shape mismatch |
| Engine Feature Parity | **Y** | 0 | 2 | 1 | 1 | Engine reads VARIABLES (uppercase) with {name, value} dicts; converter outputs variables (lowercase) with {key, value}; Java "new " eval works but no other expressions; no die_on_error |
| Code Quality | **Y** | 1 | 1 | 2 | 1 | Cross-cutting `_update_global_map()` crash (P0); `_validate_config()` dead code (P1); f-string in logger (P2); unused pandas import (P2); type annotation gap (P3) |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | Lightweight utility; no data processing. Unused pandas import adds overhead |
| Testing | **Y** | 0 | 0 | 1 | 0 | 23 converter tests across 9 test classes per gold standard; integration + regression guard passing; engine unit tests missing (P2) |

**Overall: Yellow -- Converter fully standardized (Green); engine has config key and dict shape mismatch documented via needs_review; engine/code quality gaps keep overall at Yellow**

**Top Actions:**

1. Fix `_update_global_map()` crash in base class (P0, cross-cutting)
2. Align engine config key `VARIABLES` with converter `variables` and dict shape {name, value} vs {key, value} (P1, engine gap)
3. Add die_on_error support to engine (P1, engine gap)
4. Add engine unit tests for SetGlobalVar (P2, testing gap)
5. Replace f-string in logger calls with % formatting (P2, code quality)

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
| 1 | Set globalMap variables | **Yes** | Medium | `_process()` line 89-148 | Sets variables via `self.global_map.put(name, value)`. Config key mismatch: reads `VARIABLES` (uppercase). |
| 2 | Java "new " evaluation | **Partial** | Medium | `_process()` line 115-131 | Only `new ` prefix expressions evaluated via Java bridge. Other Java expressions stored as raw strings. |
| 3 | Context variable resolution | **No** | N/A | N/A | Engine's `resolve_dict()` cannot reach values inside the VARIABLES list. Context references stored as raw strings. |
| 4 | Pass-through data flow | **Yes** | High | `_process()` line 148 | Returns `{"main": data}` unchanged. |
| 5 | NB_LINE tracking | **Partial** | Low | `_process()` line 144 | Always reports 0 via `_update_stats(0, 0, 0)`. Does not count variables set or rows passed through. |
| 6 | die_on_error support | **No** | N/A | N/A | No error handling per variable. If one variable fails, exception propagates. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-SGV-001 | **P1** | Engine reads `VARIABLES` (uppercase) with `{name, value}` dict shape. Converter outputs `variables` (lowercase) with `{key, value}` shape. Variables will not be found at runtime without engine alignment. |
| ENG-SGV-002 | **P1** | No die_on_error support. In Talend, individual variable evaluation failures can be caught. Engine lets exceptions propagate, potentially crashing the job. |
| ENG-SGV-003 | **P2** | `resolve_dict()` cannot reach values inside the VARIABLES list. Context variable references (e.g., `context.myVar`) in variable values are stored as raw strings instead of being resolved. |
| ENG-SGV-004 | **P3** | NB_LINE tracking always 0. Does not count the number of variables successfully set. |

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

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-SGV-001 | **P1** | Engine reads `VARIABLES` (uppercase) but converter outputs `variables` (lowercase). Config key casing inconsistency. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-SGV-001 | **P2** | "Use % formatting in logger calls" | Engine uses f-strings in `logger.info()` and `logger.debug()` calls (lines 102, 127, 131, 135, 139, 146). |
| STD-SGV-002 | **P2** | "Call `_validate_config()` before execution" | `_validate_config()` is defined (lines 59-87) but never called -- dead code. |

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

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-SGV-001 | **P3** | Unused `pandas` import adds unnecessary module load overhead. Component does not use pandas. |

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
| Converter unit tests | 23 | `tests/converters/talend_to_v1/components/test_set_global_var.py` |
| Engine unit tests | 0 | None |
| Integration tests | Pass | `tests/converters/talend_to_v1/test_integration.py` (regression guard) |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-SGV-001 | **P2** | No engine unit tests for SetGlobalVar. Engine behavior (Java evaluation, pass-through, globalMap setting) not directly tested. |

### 8.3 Recommended Test Cases

1. Engine: Set single variable and verify globalMap contains it.
2. Engine: Set multiple variables and verify all present in globalMap.
3. Engine: Pass-through data flow with input DataFrame.
4. Engine: Java "new " expression evaluation (requires Java bridge mock).
5. Engine: Error handling when variable setting fails.

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **BUG-SGV-001** |
| P1 | 2 | **ENG-SGV-001**, **ENG-SGV-002** |
| P2 | 4 | **ENG-SGV-003**, **STD-SGV-001**, **STD-SGV-002**, **TEST-SGV-001** |
| P3 | 2 | **ENG-SGV-004**, **PERF-SGV-001** |
| **Total** | **9** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 4 | ENG-SGV-001, ENG-SGV-002, ENG-SGV-003, ENG-SGV-004 |
| Bug (BUG) | 1 | BUG-SGV-001 |
| Naming (NAME) | 1 | NAME-SGV-001 |
| Standards (STD) | 2 | STD-SGV-001, STD-SGV-002 |
| Performance (PERF) | 1 | PERF-SGV-001 |
| Testing (TEST) | 1 | TEST-SGV-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set (BUG-SGV-001) |

---

## 10. Recommendations

### Immediate (Before Production)

1. **BUG-SGV-001 (P0)**: Fix `_update_global_map()` crash in `base_component.py` (cross-cutting -- fixes all components).

### Short-term (Hardening)

1. **ENG-SGV-001 (P1)**: Align engine to read `variables` (lowercase) with `{key, value}` dict shape, or adapt engine to accept both formats.
2. **ENG-SGV-002 (P1)**: Add per-variable error handling with die_on_error support.
3. **ENG-SGV-003 (P2)**: Enhance `resolve_dict()` to descend into list values for context variable resolution.
4. **STD-SGV-001 (P2)**: Replace f-strings with % formatting in logger calls.
5. **STD-SGV-002 (P2)**: Call `_validate_config()` from `execute()` or remove dead code.
6. **TEST-SGV-001 (P2)**: Add engine unit tests for SetGlobalVar.

### Long-term (Optimization)

1. **ENG-SGV-004 (P3)**: Track number of variables set in NB_LINE globalMap variable.
2. **PERF-SGV-001 (P3)**: Remove unused `pandas` import from engine file.

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
*Last updated: 2026-04-04 after gold standard converter rewrite (10-04)*
