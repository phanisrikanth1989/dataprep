# Audit Report: tWarn / Warn

> **Audited**: 2026-04-03
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tWarn` |
| **V1 Engine Class** | `Warn` |
| **Engine File** | `src/v1/engine/components/control/warn.py` (214 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/control/warn.py` |
| **Converter Dispatch** | `@REGISTRY.register("tWarn")` decorator-based dispatch |
| **Registry Aliases** | `Warn`, `tWarn` |
| **Category** | Control / Logs & Errors |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/control/warn.py` | Engine implementation (214 lines) |
| `src/converters/talend_to_v1/components/control/warn.py` | Converter class |
| `tests/converters/talend_to_v1/components/test_warn.py` | Converter tests |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 3/3 unique params extracted (100%) plus 2 framework params. Per-feature needs_review for engine default mismatches (message, code). |
| Engine Feature Parity | **Y** | 0 | 2 | 2 | 1 | Core warn-and-continue works; engine defaults differ for message and code; missing Talend-standard globalMap variable names (WARN_MESSAGES, etc.); narrow globalMap regex pattern |
| Code Quality | **Y** | 2 | 1 | 1 | 1 | Cross-cutting `_update_global_map()` and `GlobalMap.get()` bugs; `_validate_config()` dead code; narrow globalMap regex pattern |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | Pass-through component with negligible overhead; regex recompilation on every call |
| Testing | **G** | 0 | 0 | 0 | 0 | Comprehensive converter test suite with all 9 required test classes |

**Overall: GREEN -- Converter production-ready. Engine has cross-cutting issues documented elsewhere.**

**Top Actions**:

1. Fix cross-cutting `_update_global_map()` crash (BUG-WRN-001, affects all components)
2. Fix cross-cutting `GlobalMap.get()` crash (BUG-WRN-002, affects all components)
3. Add Talend-standard globalMap variable names WARN_MESSAGES, WARN_CODE, WARN_PRIORITY (ENG-WRN-001)
4. Broaden globalMap regex to handle additional Java expression patterns (ENG-WRN-002)

---

## 3. Talend Feature Baseline

### What tWarn Does

`tWarn` logs a priority-rated warning message without stopping the job. It belongs to the Logs & Errors family and is typically used in conjunction with `tLogCatcher` to capture and forward warning messages to a logging output. Unlike `tDie`, which halts job execution, `tWarn` allows the job to continue running after emitting the warning.

Common use cases include: signaling non-fatal conditions during ETL processing (e.g., missing optional files, unexpected data values), providing diagnostic messages at configurable severity levels, and creating an audit trail of warnings that can be collected by `tLogCatcher` for centralized logging.

tWarn is a pass-through component: if it receives input data, it forwards the data unchanged to the next component. It does not modify, filter, or transform data. The warning message supports context variables and globalMap references for dynamic content.

**Source**: [tWarn Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/logs-errors/twarn-standard-properties), [Talaxie GitHub tWarn_java.xml](https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tWarn/tWarn_java.xml)
**Component family**: Logs & Errors
**Available in**: All Talend products (Standard Job framework)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Message | `MESSAGE` | TEXT | `"this is a warning"` | Warning message text. Supports context variables (`context.var`) and globalMap references. |
| 2 | Code | `CODE` | TEXT | `42` | Warning code number. Used for programmatic identification of warning types. |
| 3 | Priority | `PRIORITY` | CLOSED_LIST | `4` (WARNING) | Priority level for the warning. Items: TRACE(1), DEBUG(2), INFO(3), WARNING(4), ERROR(5), FATAL(6). |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 4 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Framework param. Capture processing metadata for tStatCatcher component. |
| 5 | Label | `LABEL` | TEXT | `""` | Framework param. User-defined label for the component instance. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input / Output | Row > Main | Data flows through tWarn unchanged. Pass-through component. |
| `ITERATE` | Input / Output | Iterate | Enables iterative processing. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this component fails. |
| `RUN_IF` | Input / Output (Trigger) | Trigger | Conditional trigger with boolean expression. |
| `SYNCHRONIZE` | Input (Trigger) | Trigger | Synchronization trigger for parallel execution flows. |
| `PARALLELIZE` | Input (Trigger) | Trigger | Parallelization trigger from tParallelize component. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `WARN_MESSAGES` | String | After execution | Warning message text (Talend-standard name). |
| `WARN_CODE` | Integer | After execution | Warning code (Talend-standard name). |
| `WARN_PRIORITY` | Integer | After execution | Warning priority (Talend-standard name). |
| `{id}_ERROR_MESSAGE` | String | After (on error) | Error message when tWarn encounters an error. Standard Talend error variable pattern. |

### 3.5 Behavioral Notes

1. **Pass-through component**: tWarn does not modify data flowing through it. Input data is forwarded unchanged to the output.
2. **tLogCatcher integration**: tWarn is designed to work with tLogCatcher. When tLogCatcher is present in the job, it captures the warning message, code, and priority for centralized logging.
3. **Priority levels**: The 6 priority levels map to standard Java logging levels: TRACE(1), DEBUG(2), INFO(3), WARNING(4), ERROR(5), FATAL(6). Default is WARNING(4).
4. **Context variable support**: The MESSAGE field accepts Talend expressions including `context.variableName` and `globalMap.get("key")`. These are resolved at runtime.
5. **Code field**: The CODE parameter is stored as TEXT in _java.xml (default "42") but is typically used as an integer. Talend generated Java code casts it to Integer.
6. **Cannot be start component**: tWarn requires at least one incoming connection (trigger or data) to execute.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a dedicated `WarnConverter` class registered via `@REGISTRY.register("tWarn")` in `src/converters/talend_to_v1/components/control/warn.py`. It extracts all 3 unique parameters plus 2 framework parameters.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `MESSAGE` | Yes | `message` | Default: `"this is a warning"` (matches _java.xml). Quotes stripped by `_get_str()`. |
| 2 | `CODE` | Yes | `code` | Default: `"42"` (matches _java.xml). Extracted as string to preserve expressions. |
| 3 | `PRIORITY` | Yes | `priority` | Default: `"4"` (matches _java.xml WARNING level). Extracted as string. |
| 4 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param. Default: `false`. |
| 5 | `LABEL` | Yes | `label` | Framework param. Default: `""`. |

**Summary**: 3 of 3 unique parameters extracted (100%), plus 2 framework params = 5 total config keys.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| Schema | Yes | `_parse_schema(node)` called. tWarn is a utility/pass-through component so schema is typically empty. |

### 4.3 Expression Handling

The converter preserves expression strings as-is (e.g., `context.msg`, `globalMap.get("key")`). Expression resolution is deferred to the engine at runtime. This is correct behavior -- the converter should not resolve expressions.

### 4.4 Converter Issues

No open converter issues.

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No converter issues identified. All 3 unique params + 2 framework params extracted with correct _java.xml defaults. |

### 4.5 Needs Review Entries

The converter emits per-feature needs_review entries for engine default mismatches:

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `message` | Engine default `"Warning"` differs from Talend default `"this is a warning"` | engine_gap |
| 2 | `code` | Engine default `0` differs from Talend default `42` | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Warning message logging | **Yes** | High | `_log_warning_message()` line 188 | Maps priority to Python logging levels. Correct mapping. |
| 2 | Priority levels (1-6) | **Yes** | High | `PRIORITY_NAMES` line 57, `_log_warning_message()` line 188 | All 6 levels supported with correct names. |
| 3 | Context variable resolution | **Yes** | Medium | `_resolve_message_variables()` line 164 | Resolves `${context.var}` via context_manager. |
| 4 | GlobalMap variable resolution | **Partial** | Low | `_resolve_message_variables()` line 176 | Only matches `((Integer)globalMap.get("key"))` pattern. Misses `(String)` and other cast patterns. |
| 5 | GlobalMap variable storage | **Partial** | Medium | `_store_warning_in_globalmap()` line 208 | Stores `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY`. Does NOT store Talend-standard `WARN_MESSAGES`, `WARN_CODE`, `WARN_PRIORITY`. |
| 6 | Pass-through data | **Yes** | High | `_process()` line 158 | Returns input data unchanged via `{'main': input_data}`. |
| 7 | Integer cast for code | **Yes** | High | `_process()` line 121 | `int(code)` with fallback to default 0 on ValueError/TypeError. |
| 8 | Statistics tracking | **Yes** | High | `_process()` lines 146-155 | NB_LINE, NB_LINE_OK, NB_LINE_REJECT tracked via `_update_stats()`. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-WRN-001 | **P1** | **Missing Talend-standard globalMap variables.** Engine stores `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY` but does NOT store Talend-standard `WARN_MESSAGES`, `WARN_CODE`, `WARN_PRIORITY`. Jobs that read these standard names via `globalMap.get("WARN_MESSAGES")` will get null/empty. |
| ENG-WRN-002 | **P1** | **Narrow globalMap regex pattern.** `_resolve_message_variables()` only matches `((Integer)globalMap.get("key"))` pattern (line 178). Misses `(String)globalMap.get("key")`, `(Long)globalMap.get("key")`, and bare `globalMap.get("key")` patterns used in Talend expressions. |
| ENG-WRN-003 | **P2** | **Engine default for message differs from Talend.** Engine defaults `message` to `"Warning"` (line 116) but Talend _java.xml default is `"this is a warning"`. When converter emits the Talend default, behavior matches. If config key is stripped, engine falls back to wrong default. |
| ENG-WRN-004 | **P2** | **Engine default for code differs from Talend.** Engine defaults `code` to `0` (line 117) but Talend _java.xml default is `42`. Same config-stripping risk as ENG-WRN-003. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_MESSAGE` | No (engine-specific) | Yes | `_store_warning_in_globalmap()` line 211 | Engine-specific naming convention |
| `{id}_CODE` | No (engine-specific) | Yes | `_store_warning_in_globalmap()` line 212 | Engine-specific naming convention |
| `{id}_PRIORITY` | No (engine-specific) | Yes | `_store_warning_in_globalmap()` line 213 | Engine-specific naming convention |
| `WARN_MESSAGES` | Yes | **No** | -- | Missing. Talend-standard variable name. |
| `WARN_CODE` | Yes | **No** | -- | Missing. Talend-standard variable name. |
| `WARN_PRIORITY` | Yes | **No** | -- | Missing. Talend-standard variable name. |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Missing. Standard Talend error variable. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-WRN-001 | **P0** | `base_component.py:_update_global_map()` | **CROSS-CUTTING**: `_update_global_map()` crashes when `globalMap` is set because it tries to call methods on `NB_LINE` etc. that may not exist. Affects ALL components that track stats. |
| BUG-WRN-002 | **P0** | `global_map.py:GlobalMap.get()` | **CROSS-CUTTING**: `GlobalMap.get()` crash when key not found and no default provided. Affects ALL components that read globalMap values. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-WRN-001 | **P2** | Engine class is `Warn` but `_process()` method documentation refers to it as a "monitoring/logging component". Naming is acceptable but the docstring could be more precise. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-WRN-001 | **P2** | "_validate_config() should be called or removed" | `_validate_config()` is defined (lines 59-96) but never called by the base class `execute()` method. Dead code that may mislead developers. |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified. tWarn only logs messages and passes through data. No file access, no network calls, no eval/exec.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- `logger = logging.getLogger(__name__)` at module level |
| Level usage | Good -- uses appropriate levels (debug/info/warning/error/critical) based on priority |
| Sensitive data | No concern -- logs user-configured message text, which is expected behavior |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Good -- raises `ComponentExecutionError` on failure (line 162) |
| Exception chaining | Good -- uses `from e` for exception chaining (line 162) |
| die_on_error handling | N/A -- tWarn does not have a die_on_error parameter |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- all methods have type hints |
| Parameter types | Good -- uses `Optional[pd.DataFrame]`, `Dict[str, Any]`, `List[str]` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-WRN-001 | **P3** | **Regex recompilation on every call.** `_resolve_message_variables()` compiles the globalMap regex pattern `r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'` on every invocation (line 178) instead of pre-compiling as a class or module constant. Negligible impact for tWarn since it executes once, but a minor optimization opportunity. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- tWarn is a pass-through component with no data transformation. Streaming mode would cause redundant warning logging per chunk but no data issues. |
| Memory threshold | N/A -- no data buffering |
| Large data handling | Good -- input data is passed through by reference (no copy), no memory amplification |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 25+ | `tests/converters/talend_to_v1/components/test_warn.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-WRN-001 | **P3** | No engine unit tests for `Warn._process()`, context variable resolution, or globalMap storage. Converter tests are comprehensive. Engine tests out of scope for converter standardization. |

### 8.3 Recommended Test Cases

Engine test cases (out of scope for converter standardization, documented for future):

- Happy path: message + code + priority logged correctly
- Context variable resolution in message
- GlobalMap variable resolution in message (Integer cast pattern)
- Invalid code/priority fallback to defaults
- Pass-through: input DataFrame returned unchanged
- Empty input: returns empty DataFrame
- Statistics tracking (NB_LINE, NB_LINE_OK, NB_LINE_REJECT)

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 2 | **BUG-WRN-001**, **BUG-WRN-002** |
| P1 | 2 | **ENG-WRN-001**, **ENG-WRN-002** |
| P2 | 3 | **ENG-WRN-003**, **ENG-WRN-004**, **STD-WRN-001** |
| P3 | 2 | **PERF-WRN-001**, **TEST-WRN-001** |
| **Total** | **9** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 4 | ENG-WRN-001, ENG-WRN-002, ENG-WRN-003, ENG-WRN-004 |
| Bug (BUG) | 2 | BUG-WRN-001, BUG-WRN-002 |
| Standards (STD) | 1 | STD-WRN-001 |
| Performance (PERF) | 1 | PERF-WRN-001 |
| Testing (TEST) | 1 | TEST-WRN-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| BUG-WRN-001 | `base_component.py:_update_global_map()` | `_update_global_map()` crash when globalMap is set. Affects statistics tracking in `_process()`. |
| BUG-WRN-002 | `global_map.py:GlobalMap.get()` | `GlobalMap.get()` crash on missing key. Affects `_resolve_message_variables()` globalMap lookups. |

---

## 10. Recommendations

### Immediate (Before Production)

1. **BUG-WRN-001** (P0): Fix cross-cutting `_update_global_map()` crash in `base_component.py`. Affects all components.
2. **BUG-WRN-002** (P0): Fix cross-cutting `GlobalMap.get()` crash in `global_map.py`. Affects all components.

### Short-term (Hardening)

1. **ENG-WRN-001** (P1): Add Talend-standard globalMap variable names (`WARN_MESSAGES`, `WARN_CODE`, `WARN_PRIORITY`) alongside existing `{id}_*` variables.
2. **ENG-WRN-002** (P1): Broaden globalMap regex in `_resolve_message_variables()` to handle `(String)`, `(Long)`, and bare `globalMap.get()` patterns.
3. **ENG-WRN-003** (P2): Update engine message default from `"Warning"` to `"this is a warning"` to match _java.xml.
4. **ENG-WRN-004** (P2): Update engine code default from `0` to `42` to match _java.xml.
5. **STD-WRN-001** (P2): Remove or call `_validate_config()` dead code.

### Long-term (Optimization)

1. **PERF-WRN-001** (P3): Pre-compile globalMap regex as module or class constant.
2. **TEST-WRN-001** (P3): Add engine unit tests for `Warn._process()`.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Official Talend docs | [tWarn Standard Properties](https://help.qlik.com/talend/en-US/components/7.3/logs-errors/twarn-standard-properties) | Parameter definitions, behavioral notes |
| Talaxie GitHub _java.xml | [tWarn_java.xml](https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tWarn/tWarn_java.xml) | Component definition XML, parameter defaults |
| Engine source | `src/v1/engine/components/control/warn.py` (214 lines) | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/control/warn.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_warn.py` | Testing coverage analysis |
| Base component | `src/v1/engine/base_component.py` | Cross-cutting bug analysis |
| GlobalMap | `src/v1/engine/global_map.py` | GlobalMap variable analysis |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| BUG-WRN-001 | `base_component.py:_update_global_map()` | `_update_global_map()` crash when globalMap is set. Affects statistics tracking. Shared with all v1 components. |
| BUG-WRN-002 | `global_map.py:GlobalMap.get()` | `GlobalMap.get()` crash on missing key. Affects globalMap lookups in message resolution. Shared with all v1 components. |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after full rewrite per D-12*
