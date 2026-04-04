# Audit Report: tSleep / SleepComponent

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
| **Talend Name** | `tSleep` |
| **V1 Engine Class** | `SleepComponent` |
| **Engine File** | `src/v1/engine/components/control/sleep.py` (168 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/control/sleep.py` |
| **Converter Dispatch** | `@REGISTRY.register("tSleep")` decorator-based dispatch |
| **Registry Aliases** | `SleepComponent`, `tSleep` |
| **Category** | Control / Orchestration |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/control/sleep.py` | Engine implementation (168 lines) |
| `src/converters/talend_to_v1/components/control/sleep.py` | Converter class |
| `tests/converters/talend_to_v1/components/test_sleep.py` | Converter tests |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 1/1 unique params extracted (100%) plus 2 framework params. No needs_review entries (engine fully supports pause_duration). |
| Engine Feature Parity | **Y** | 0 | 2 | 1 | 0 | Core sleep works; missing `{id}_ERROR_MESSAGE` globalMap variable; NB_LINE always 1 is semantically questionable for Orchestration component; no die_on_error support |
| Code Quality | **Y** | 2 | 2 | 1 | 1 | Cross-cutting base class bugs (_update_global_map crash, GlobalMap.get crash); float('inf') blocks forever; double context resolution in engine |
| Performance & Memory | **G** | 0 | 0 | 1 | 0 | Streaming mode causes redundant sleep; minor concern only |
| Testing | **G** | 0 | 0 | 0 | 0 | Comprehensive converter test suite with all 9 required test classes |

**Overall: GREEN -- Converter production-ready. Engine has cross-cutting issues documented elsewhere.**

**Top Actions**:
1. Fix cross-cutting `_update_global_map()` crash (BUG-SLP-001, affects all components)
2. Fix cross-cutting `GlobalMap.get()` crash (BUG-SLP-002, affects all components)
3. Implement `{id}_ERROR_MESSAGE` globalMap variable (ENG-SLP-001)
4. Address NB_LINE semantics for Orchestration components (ENG-SLP-002)

---

## 3. Talend Feature Baseline

### What tSleep Does

`tSleep` introduces a configurable delay (pause) in a Talend job's execution flow. It belongs to the Orchestration family and is used as a middle component to create a break/pause in the job before resuming execution. The pause duration is specified in seconds.

Common use cases include: rate limiting API calls, waiting for external systems to become available, introducing deliberate delays between subjobs for resource management, and creating timing gaps in iterative processing loops (e.g., polling with `tLoop` + `tSleep`).

tSleep is a pass-through component: it receives data, pauses for the configured duration, then forwards the same data unchanged to the next component. It does not modify, filter, or transform data in any way.

**Source**: [tSleep Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/orchestration/tsleep-standard-properties), [Talaxie GitHub tSleep_java.xml](https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tSleep/tSleep_java.xml)
**Component family**: Orchestration
**Available in**: All Talend products (Standard Job framework)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Pause (in second) | `PAUSE` | TEXT | `1` | Duration the job execution pauses for, in seconds. Accepts integer values, decimal values, and Talend expressions (e.g., `context.delay`, `globalMap.get("sleep_time")`). |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 2 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Framework param. Capture processing metadata for tStatCatcher component. |
| 3 | Label | `LABEL` | TEXT | `""` | Framework param. User-defined label for the component instance. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input / Output | Row > Main | Data flows through tSleep unchanged. Pass-through component. |
| `ITERATE` | Input / Output | Iterate | Enables iterative processing. Common pattern: `tLoop` -> `tSleep` -> processing component. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this component fails. |
| `RUN_IF` | Input / Output (Trigger) | Trigger | Conditional trigger with boolean expression. |
| `SYNCHRONIZE` | Input (Trigger) | Trigger | Synchronization trigger for parallel execution flows. |
| `PARALLELIZE` | Input (Trigger) | Trigger | Parallelization trigger from tParallelize component. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_ERROR_MESSAGE` | String | After (on error) | Error message when tSleep encounters an error. Standard Talend error variable pattern. |

### 3.5 Behavioral Notes

1. **Pass-through component**: tSleep does not modify data flowing through it. Input data is forwarded unchanged to the output.
2. **Thread blocking**: tSleep blocks the execution thread via Java's `Thread.sleep()`. During the sleep, no other components in the same subjob execute.
3. **Seconds unit**: The Talend UI labels this field "Pause (in second)" and the _java.xml default is `1` (one second). The generated Java code uses `Thread.sleep(pause * 1000)` to convert seconds to milliseconds.
4. **Context variable support**: The PAUSE field accepts Talend expressions including `context.variableName` and `globalMap.get("key")`. These are resolved at runtime.
5. **Zero or negative values**: A pause value of 0 or less results in no actual sleep operation.
6. **No schema definition**: tSleep does not define its own output schema. It inherits from its input connection.
7. **No DIE_ON_ERROR**: Unlike most components, tSleep does not expose a Die on error checkbox. The _java.xml has no DIE_ON_ERROR parameter.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a dedicated `SleepConverter` class registered via `@REGISTRY.register("tSleep")` in `src/converters/talend_to_v1/components/control/sleep.py`.

**Converter flow**:
1. Registry dispatches `tSleep` nodes to `SleepConverter.convert()`
2. Extracts `PAUSE` via `_get_str()` with default `"1"` (string, matching _java.xml default)
3. Extracts framework params: `TSTATCATCHER_STATS` (bool, default False), `LABEL` (str, default "")
4. Returns `ComponentResult` with config dict, warnings, and needs_review

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `PAUSE` | **Yes** | `pause_duration` | String, default "1". Engine handles float() conversion and context variable resolution at runtime. |
| 2 | `TSTATCATCHER_STATS` | **Yes** | `tstatcatcher_stats` | Framework param -- bool, default False |
| 3 | `LABEL` | **Yes** | `label` | Framework param -- str, default "" |

**Summary**: 1 of 1 unique parameters extracted (100%), plus 2 framework params = 3 total config keys.

### 4.2 Schema Extraction

tSleep is a pass-through/utility component. The converter extracts schema via `_parse_schema(node)` for any schema defined on the node, but tSleep typically has no schema of its own.

### 4.3 Expression Handling

PAUSE is stored as a string by the converter, preserving context variables (e.g., `context.delay`) and expressions for runtime resolution. The engine's `_get_pause_duration()` method handles `float()` conversion and context variable resolution via `context_manager.resolve_string()`.

### 4.4 Converter Issues

None. All issues from prior audit versions have been resolved by the full rewrite.

### 4.5 Needs Review Entries

None. The engine fully supports the `pause_duration` config key with context variable resolution, float conversion, and non-positive duration handling. Framework params (tstatcatcher_stats, label) are exempt from needs_review per project convention.

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Sleep for configured duration | **Yes** | High | `_process()` line 117 | Uses `time.sleep(pause_duration)` |
| 2 | Pass-through data | **Yes** | High | `_process()` line 129 | Returns input_data unchanged or empty DataFrame |
| 3 | Context variable resolution | **Yes** | High | `_get_pause_duration()` line 156-157 | Uses `context_manager.resolve_string()` for `${context.var}` |
| 4 | Numeric string conversion | **Yes** | High | `_get_pause_duration()` line 161 | `float(resolved_value)` handles "5", "1.5", etc. |
| 5 | Non-positive duration skip | **Yes** | High | `_process()` line 117-120 | Skips sleep for <= 0, logs debug message |
| 6 | Configuration validation | **Yes** | Medium | `_validate_config()` line 59-84 | Called from `_process()` line 103 -- actually called, unlike dead code in other components |
| 7 | Error handling | **Yes** | Medium | `_process()` lines 131-136 | Catches ConfigurationError and Exception, wraps in ComponentExecutionError |
| 8 | Statistics tracking | **Partial** | Low | `_process()` line 126 | Always reports (1, 1, 0). Semantically questionable for Orchestration component. |
| 9 | `{id}_ERROR_MESSAGE` globalMap | **No** | N/A | -- | Talend documents this as the sole global variable for tSleep. Not implemented. |
| 10 | Sub-second precision | **Yes** | High | `_get_pause_duration()` returns float | `time.sleep(0.5)` works. Engine accepts floats (enhancement over Talend's integer-only UI). |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-SLP-001 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: Talend documents `ERROR_MESSAGE` as the sole After-scope global variable. When an error occurs, the message should be stored in `globalMap` as `{id}_ERROR_MESSAGE`. The engine sets `self.error_message` on the component instance but never writes it to `global_map`. |
| ENG-SLP-002 | **P1** | **NB_LINE always 1 -- semantically questionable**: The engine always calls `_update_stats(1, 1, 0)`, treating each sleep as "1 line processed". Talend does not define NB_LINE for tSleep as it is an Orchestration component, not a data-processing component. In iterate loops, NB_LINE accumulates, producing misleading statistics. |
| ENG-SLP-003 | **P2** | **No die_on_error support**: The engine always raises on error. No graceful degradation option since tSleep has no die_on_error config. If pause_duration cannot be parsed, the job fails. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | No | **Yes** | `_update_stats(1, 1, 0)` -> `_update_global_map()` | V1 sets but Talend does not define for Orchestration components |
| `{id}_NB_LINE_OK` | No | **Yes** | Same mechanism | Always 1 |
| `{id}_NB_LINE_REJECT` | No | **Yes** | Same mechanism | Always 0 |
| `{id}_ERROR_MESSAGE` | **Yes** | **No** | -- | The only Talend-documented globalMap variable is missing |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-SLP-001 | **P0** | `base_component.py:304` | **CROSS-CUTTING: `_update_global_map()` references undefined variable `value`**. The log statement uses `{value}` but the loop variable is `stat_value`. Causes NameError at runtime when `global_map` is not None. Stats are written successfully before the crash. Affects ALL components. |
| BUG-SLP-002 | **P0** | `global_map.py:28` | **CROSS-CUTTING: `GlobalMap.get()` references undefined `default` parameter**. Method signature is `get(self, key: str)` but body calls `self._map.get(key, default)`. Causes NameError on every `.get()` call. Affects ALL components. |
| BUG-SLP-003 | **P1** | `sleep.py:_validate_config()` | **`float('inf')` blocks thread forever**: Validation accepts `float('inf')` because it passes `isinstance(duration, float)` check. `time.sleep(float('inf'))` blocks indefinitely. `float('nan')` also passes isinstance but silently skips sleep. |
| BUG-SLP-004 | **P1** | `base_component.py:202, sleep.py:_get_pause_duration()` | **Double context resolution**: `execute()` calls `resolve_dict(self.config)` then `_get_pause_duration()` calls `resolve_string()` again. Redundant at best, destructive at worst if resolved value contains `context.` substring. |
| BUG-SLP-005 | **P2** | `base_component.py:202` | **CROSS-CUTTING: `self.config` mutated by `execute()`**: `resolve_dict` replaces config with resolved copy. In iterate loops with changing context, second execution resolves already-resolved config. Dynamic context variables frozen to first iteration value. Affects ALL components. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-SLP-001 | **P3** | `pause_duration` (v1) vs `PAUSE` (Talend): Descriptive snake_case is correct per convention. No action needed. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-SLP-001 | **P2** | "`_validate_config()` should be called" | SleepComponent DOES call `_validate_config()` from `_process()`. This is CORRECT -- other components should follow this pattern. Not a violation. |

### 6.4 Debug Artifacts

None found. Code is clean.

### 6.5 Security

No concerns identified. Config comes from trusted Talend-converted jobs. Large pause values (e.g., 999999 seconds) could block threads but this is a resource concern, not a security vulnerability.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Level usage | INFO for start/sleep/complete, DEBUG for non-positive skip, WARNING for conversion failures, ERROR for failures -- correct |
| Sensitive data | No sensitive data logged -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError` and `ComponentExecutionError` -- correct |
| Exception chaining | Uses `raise ... from e` pattern -- correct |
| die_on_error handling | N/A -- tSleep has no die_on_error parameter |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()` has `input_data: Optional[pd.DataFrame] = None` -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-SLP-001 | **P2** | **Streaming mode causes redundant sleep**: When `execution_mode=HYBRID` and input exceeds `MEMORY_THRESHOLD_MB`, `_execute_streaming()` calls `_process()` per chunk. Each chunk triggers `time.sleep()`. A 5-second sleep with N chunks becomes 5*N seconds. Unlikely in practice since tSleep rarely receives large DataFrames. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | HYBRID mode causes redundant sleep per chunk (PERF-SLP-001) |
| Memory threshold | N/A -- tSleep does not hold data, passes through unchanged |
| Large data handling | Input DataFrame passed through by reference, no copies |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 9 classes | `tests/converters/talend_to_v1/components/test_sleep.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-SLP-001 | **P2** | No engine unit tests for SleepComponent |
| TEST-SLP-002 | **P2** | No integration tests for tSleep end-to-end flow |

### 8.3 Recommended Test Cases

- Engine test: context variable resolution in pause_duration
- Engine test: non-positive duration skips sleep
- Engine test: pass-through of input DataFrame
- Integration test: tSleep in iterate loop with variable delay

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 2 | **BUG-SLP-001**, **BUG-SLP-002** |
| P1 | 2 | **BUG-SLP-003**, **BUG-SLP-004** |
| P2 | 4 | **BUG-SLP-005**, **STD-SLP-001**, **ENG-SLP-003**, **PERF-SLP-001** |
| P3 | 1 | NAME-SLP-001 |
| **Total** | **9** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Bug (BUG) | 5 | BUG-SLP-001, BUG-SLP-002, BUG-SLP-003, BUG-SLP-004, BUG-SLP-005 |
| Engine (ENG) | 3 | ENG-SLP-001, ENG-SLP-002, ENG-SLP-003 |
| Naming (NAME) | 1 | NAME-SLP-001 |
| Standards (STD) | 1 | STD-SLP-001 |
| Performance (PERF) | 1 | PERF-SLP-001 |
| Testing (TEST) | 2 | TEST-SLP-001, TEST-SLP-002 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| BUG-SLP-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- affects all components |
| BUG-SLP-002 | `global_map.py:28` | `GlobalMap.get()` crash on undefined `default` param -- affects all components |
| BUG-SLP-005 | `base_component.py:202` | Config mutation in iterate loops -- affects all components |

---

## 10. Recommendations

### Immediate (Before Production)

- Fix `_update_global_map()` NameError (BUG-SLP-001) -- cross-cutting, blocks all components
- Fix `GlobalMap.get()` NameError (BUG-SLP-002) -- cross-cutting, blocks all components

### Short-term (Hardening)

- Guard against `float('inf')` and `float('nan')` in `_validate_config()` (BUG-SLP-003)
- Remove double context resolution in `_get_pause_duration()` (BUG-SLP-004)
- Implement `{id}_ERROR_MESSAGE` globalMap variable (ENG-SLP-001)
- Review NB_LINE semantics for Orchestration components (ENG-SLP-002)

### Long-term (Optimization)

- Add engine unit tests (TEST-SLP-001)
- Add integration tests (TEST-SLP-002)
- Consider streaming mode guard for Orchestration components (PERF-SLP-001)

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub _java.xml | `https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tSleep/tSleep_java.xml` | Parameter definitions, defaults |
| Official Talend docs (7.3) | `https://help.qlik.com/talend/en-US/components/7.3/orchestration/tsleep-standard-properties` | Behavioral notes, use cases |
| Engine source | `src/v1/engine/components/control/sleep.py` (168 lines) | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/control/sleep.py` | Converter audit |
| Base component | `src/v1/engine/base_component.py` | Cross-cutting bug analysis |
| GlobalMap | `src/v1/engine/global_map.py` | GlobalMap variable analysis |

## Appendix B: Cross-Cutting Issues

Issues shared with other components, referenced by canonical ID.

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` NameError crash when globalMap is set. Stats are written but method raises, causing component to report ERROR status. |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` NameError on `default` parameter. Any downstream code calling `global_map.get()` will crash. |
| XCUT-003 | `base_component.py:202` | `resolve_dict()` mutates `self.config`. In iterate loops, dynamic context variables frozen to first iteration value. |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after full rewrite per gold standard template*
