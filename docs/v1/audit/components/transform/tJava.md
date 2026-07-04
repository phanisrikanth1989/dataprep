# Audit Report: tJava / JavaComponent

> **Audited**: 2026-04-04
> **Reconciled**: 2026-05-11
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
| **Talend Name** | `tJava` |
| **V1 Engine Class** | `JavaComponent` |
| **Engine File** | `src/v1/engine/components/transform/java_component.py` (109 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/java_component.py` (65 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tJava")` decorator-based dispatch |
| **Registry Aliases** | `JavaComponent`, `tJava` |
| **Category** | Transform / Custom Code (Java bridge) |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/java_component.py` | Engine implementation (109 lines) |
| `src/converters/talend_to_v1/components/transform/java_component.py` | Converter class (65 lines) |
| `tests/converters/talend_to_v1/components/test_java_component.py` | Converter tests (20 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 2 of 2 _java.xml params extracted (100%). Phantom DIE_ON_ERROR removed. 1 needs_review entry (imports engine gap). |
| Engine Feature Parity | **Y** | 1 | 2 | 2 | 1 | Engine reads java_code only; no imports support; no error handling toggle; globalMap stale-read; Groovy Metaspace leak |
| Code Quality | **G** | 0 | 0 | 2 | 1 | Clean converter with _build_component_dict wrapper, proper docstring, correct defaults. Engine has minor issues. |
| Performance & Memory | **Y** | 1 | 0 | 1 | 0 | Groovy shell Metaspace leak (P0) in loops; bridge sync overhead |
| Testing | **Y** | 0 | 0 | 1 | 0 | 20 converter tests covering all test classes per TEST_PATTERN.md. No engine unit tests (per D-89, Testing=Yellow). |

**Overall: YELLOW -- Converter is gold-standard Green; engine gaps and missing engine tests hold overall to Yellow**

**Top Actions**:

1. Add engine unit tests for JavaComponent
2. Fix Groovy Metaspace leak in bridge execution loops
3. Implement imports config reading in engine

---

## 3. Talend Feature Baseline

### What tJava Does

`tJava` is a custom-code component in the Talend Custom Code family that enables users to embed personalized Java code directly within a Talend Job. It extends the functionality of a Talend Job by executing arbitrary Java commands. The code runs **exactly once** per subjob execution -- it is NOT per-row processing. This is the fundamental distinction from `tJavaRow` (per-row) and `tJavaFlex` (start-once/main-per-row/end-once hybrid).

The component is commonly used for initialization tasks (setting global variables, preparing resources), one-time calculations, and invoking external APIs or services from within a Talend job. Users write Java code in a multi-line editor with full access to `globalMap`, `context` variables, and all imported routines.

**Source**: [tJava Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/java-custom-code/tjava-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tJava/tJava_java.xml)
**Component family**: Custom Code (Java)
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in). User-specified JARs can be loaded via `tLibraryLoad`.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Code | `CODE` | MEMO_JAVA | sample code | Multi-line Java code editor. Code executes exactly once per subjob run. Has full access to `globalMap`, `context` variables, and imported routines. |
| 2 | Import | `IMPORT` | MEMO_IMPORT | comment | Java import statements for the CODE field. Each import on its own line. Added to top of generated Java class. |

### 3.2 Advanced Settings

None -- tJava has no advanced settings beyond the framework params.

### 3.3 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 3 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Capture processing metadata for tStatCatcher. |
| 4 | Label | `LABEL` | TEXT | `""` | Display label on designer canvas. No runtime impact. |

### 3.4 Phantom Parameters (NOT in _java.xml)

| Parameter | Status | Notes |
| ----------- | -------- | ------- |
| `DIE_ON_ERROR` | **REMOVED** | Not present in _java.xml. Was incorrectly extracted in prior converter version. Commonly found in .item exports as a framework-injected param, but not part of the tJava component definition. |

### 3.5 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input/Output | Row > Main | Pass-through data flow. tJava acts as a transform: input schema equals output schema. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when subjob completes successfully. Most common connection type. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when subjob fails. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when component fails. |

### 3.6 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Number of rows processed (pass-through count) |

### 3.7 Behavioral Notes

1. CODE is MEMO_JAVA type -- multi-line Java code stored as-is without interpretation by the converter.
2. IMPORT is MEMO_IMPORT type -- import statements stored as-is.
3. Only 2 unique params in _java.xml (CODE, IMPORT) -- one of the simplest component definitions.
4. Java code runs exactly once, not per-row. For per-row processing, use tJavaRow.
5. The component requires Java bridge to be enabled at runtime.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `@REGISTRY.register("tJava")` decorator for dispatch and `_build_component_dict()` for output wrapping. CODE and IMPORT are extracted via `_get_param()` (not `_get_str()`) to preserve MEMO field content including quotes and special characters. Framework params use standard `_get_bool()` and `_get_str()`.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `CODE` | Yes | `java_code` | Via `_get_param()`, default `""`. MEMO_JAVA type preserved as string. |
| 2 | `IMPORT` | Yes | `imports` | Via `_get_param()`, default `""`. MEMO_IMPORT type preserved as string. |
| 3 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, default `False` |
| 4 | `LABEL` | Yes | `label` | Framework param, default `""` |
| -- | `DIE_ON_ERROR` | **Removed** | -- | Phantom param (not in _java.xml). Was incorrectly extracted in prior version. |

**Summary**: 2 of 2 unique _java.xml parameters extracted (100%). Plus 2 framework params. 1 phantom param removed.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | |
| `key` | Yes | |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by base class |

Schema is passthrough: `input == output` (transform component).

### 4.3 Expression Handling

CODE and IMPORT are stored as raw strings without expression interpretation per D-85. Context variable references (`context.var`) and Java expressions within CODE are preserved as-is -- they are meaningful only at engine runtime when the Java bridge executes the code.

### 4.4 Converter Issues

None. Converter is gold-standard compliant.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `imports` | Engine does not read 'imports' config key -- JavaComponent only reads 'java_code' | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Execute Java code once | **Yes** | High | `_process()` line 43-109 | Uses Java bridge `execute_one_time_expression()` |
| 2 | Import statements | **No** | N/A | -- | Engine does not read `imports` config key. Imports must be handled in bridge setup. |
| 3 | Context variable access | **Yes** | Medium | `_process()` lines 64-69 | Syncs context to bridge before execution |
| 4 | GlobalMap access | **Yes** | Medium | `_process()` lines 72-74 | Syncs globalMap to bridge before execution |
| 5 | Bidirectional sync | **Yes** | Medium | `_process()` lines 76-93 | Syncs context and globalMap back from Java after execution |
| 6 | Pass-through data | **Yes** | High | `_process()` lines 101-105 | Input data returned unchanged |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-JC-001 | **P0** | Groovy Metaspace leak: `execute_one_time_expression()` creates a new Groovy shell per execution. In loop scenarios, this leaks Metaspace memory. |
| ENG-JC-002 | **P1** | Engine does not read `imports` config key. Java imports must be pre-loaded in bridge initialization or included inline in CODE. |
| ENG-JC-003 | **P1** | No `die_on_error` behavior -- any exception propagates unconditionally. Talend's `DIE_ON_ERROR=false` allows error triggers to fire. |
| ENG-JC-004 | **P2** | Context/globalMap sync is merge-update only -- keys deleted in Java are not removed from Python side. |
| ENG-JC-005 | **P2** | Bridge `_sync_from_java()` called after execution may read stale values if Java code modifies shared state asynchronously. |
| ENG-JC-006 | **P3** | Stats tracking (`_update_stats`) only tracks pass-through row counts, not Java execution metrics. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Partial | Via `_update_stats()` | Only set when input_data is not None |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-JC-001 | **P2** | `java_component.py:79` | Typo in comment: "Pyython" (extra y). Cosmetic only. |
| BUG-JC-002 | **P2** | `java_component.py:81` | `_sync_from_java()` called via private method access (`java_bridge._sync_from_java()`). Should use public API. |

### 6.2 Naming Consistency

No naming issues found. `JavaComponent` follows project conventions.

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-JC-001 | **P3** | "No f-string in logger calls" | Multiple f-string logger calls (lines 62, 68-69, 87, 93, 96, 98). Should use lazy formatting. |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

Java code execution via bridge is inherently a security concern, but this is by design (tJava's purpose is arbitrary code execution). No additional security issues beyond the expected code injection surface.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Correct: `logging.getLogger(__name__)` |
| Level usage | Appropriate: info for operations, debug for results, error for failures |
| Sensitive data | Minor concern: context variables logged at info level (line 68) |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Uses `ValueError` and `RuntimeError` appropriately |
| Exception chaining | Bare `raise` in except block preserves chain |
| die_on_error handling | Not implemented -- all errors propagate |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Complete: `_process()` has full type hints |
| Parameter types | Complete: `Optional[pd.DataFrame]` and `Dict[str, Any]` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-JC-001 | **P0** | Groovy Metaspace leak: Each `execute_one_time_expression()` call may create a new Groovy shell, leaking PermGen/Metaspace in loop-heavy jobs. |
| PERF-JC-002 | **P2** | Bridge sync overhead: Full context and globalMap serialization before and after each execution, even when no Java-side changes occurred. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- tJava executes once, not per-chunk |
| Memory threshold | No threshold -- Java code can consume arbitrary memory |
| Large data handling | Pass-through only; data not copied for Java execution |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 20 | `tests/converters/talend_to_v1/components/test_java_component.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None dedicated to JavaComponent |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-JC-001 | **P2** | No engine unit tests for JavaComponent `_process()` method. Per D-89, Testing=Yellow until engine tests added. |

### 8.3 Recommended Test Cases

- Engine: Test `_process()` with mock Java bridge (happy path)
- Engine: Test `_process()` with empty java_code (should raise ValueError)
- Engine: Test `_process()` without Java bridge enabled (should raise RuntimeError)
- Engine: Test context/globalMap sync round-trip
- Engine: Test pass-through of input DataFrame

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **ENG-JC-001** (Metaspace leak) |
| P1 | 2 | **ENG-JC-002** (imports not read), **ENG-JC-003** (no die_on_error) |
| P2 | 5 | **ENG-JC-004**, **ENG-JC-005**, **BUG-JC-001**, **BUG-JC-002**, **TEST-JC-001** |
| P3 | 2 | **ENG-JC-006**, **STD-JC-001** |
| **Total** | **10** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 6 | ENG-JC-001 through ENG-JC-006 |
| Bug (BUG) | 2 | BUG-JC-001, BUG-JC-002 |
| Naming (NAME) | 0 | -- |
| Standards (STD) | 1 | STD-JC-001 |
| Performance (PERF) | 2 | PERF-JC-001, PERF-JC-002 |
| Testing (TEST) | 1 | TEST-JC-001 |

Note: PERF-JC-001 and ENG-JC-001 reference the same Metaspace leak from different dimensions (performance vs feature parity). Unique issues: 10.

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken signature |

---

## 10. Recommendations

### Immediate (Before Production)

1. **ENG-JC-001 / PERF-JC-001**: Fix Groovy Metaspace leak by reusing Groovy shells or adding shell pool.

### Short-term (Hardening)

1. **ENG-JC-002**: Implement imports reading in engine (parse import statements, add to bridge class loader).
2. **ENG-JC-003**: Add die_on_error handling (catch exceptions, set ERROR_MESSAGE global, fire error triggers).
3. **TEST-JC-001**: Add engine unit tests for JavaComponent.

### Long-term (Optimization)

1. **ENG-JC-004/005**: Improve bridge sync to handle key deletions and avoid stale reads.
2. **STD-JC-001**: Replace f-string logger calls with lazy formatting.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `<https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tJava/tJava_java.xml`> | Component definition, parameter list, defaults |
| Official Talend docs | `<https://help.qlik.com/talend/en-US/components/7.3/java-custom-code/tjava-standard-properties`> | Parameter descriptions, behavioral notes |
| Engine source | `src/v1/engine/components/transform/java_component.py` | Feature parity analysis (109 lines) |
| Converter source | `src/converters/talend_to_v1/components/transform/java_component.py` | Converter audit (65 lines) |
| Test source | `tests/converters/talend_to_v1/components/test_java_component.py` | Test coverage analysis (20 tests) |

## Appendix B: Engine Config Key Mapping

| Config Key | Engine Reads? | Engine Method | Notes |
| ----------- | -------------- | --------------- | ------- |
| `java_code` | Yes | `_process()` line 47 | `self.config.get('java_code', '')` |
| `imports` | **No** | -- | Engine gap: imports not read from config |
| `tstatcatcher_stats` | No | -- | Framework param, handled by orchestrator |
| `label` | No | -- | Display-only param |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after Phase 13 Plan 02 gold-standard rewrite*
