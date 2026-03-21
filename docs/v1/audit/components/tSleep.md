# Audit Report: tSleep / SleepComponent

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tSleep` |
| **V1 Engine Class** | `SleepComponent` |
| **Engine File** | `src/v1/engine/components/control/sleep.py` (169 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tsleep()` (lines 1099-1105) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> dedicated `elif component_type == 'tSleep'` branch (line 256-257) |
| **Registry Aliases** | `SleepComponent`, `tSleep` (registered in `src/v1/engine/engine.py` lines 177-178) |
| **Category** | Control / Orchestration |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/control/sleep.py` | Engine implementation (169 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 1099-1105) | Parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (line 256-257) | Dispatch -- dedicated `elif` for `tSleep` calls `parse_tsleep()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ConfigurationError`, `ComponentExecutionError`) |
| `src/v1/engine/components/control/__init__.py` | Package exports (`SleepComponent`) |
| `src/v1/engine/engine.py` (lines 42, 177-178) | Import and registry of `SleepComponent` under aliases `SleepComponent` and `tSleep` |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 0 | 2 | 1 of 4 Talend params extracted (25%); `PAUSE` extracted but `float()` crashes on context vars; `TSTATCATCHER_STATS`, `DIE_ON_ERROR`, `LABEL` missing; CONV-SLP-003 default mismatch downgraded to P3 (PAUSE always present in well-formed exports) |
| Engine Feature Parity | **Y** | 0 | 2 | 1 | 0 | Core sleep works; missing `{id}_ERROR_MESSAGE` globalMap; no `die_on_error` support; NB_LINE semantics questionable |
| Code Quality | **Y** | 2 | 3 | 2 | 0 | Cross-cutting base class bugs (`_update_global_map()` crash, `GlobalMap.get()` crash); converter `float()` crash on expressions; `float('inf')` blocks thread forever (BUG-SLP-004); double context resolution (BUG-SLP-005); `self.config` mutation breaks reentrancy (BUG-SLP-006) |
| Performance & Memory | **G** | 0 | 0 | 1 | 0 | Streaming mode causes redundant sleep; minor concern only |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tSleep Does

`tSleep` introduces a configurable delay (pause) in a Talend job's execution flow. It belongs to the Orchestration family and is used as a middle component to create a break/pause in the job before resuming execution. Common use cases include: rate limiting API calls, waiting for external systems to become available, introducing deliberate delays between subjobs for resource management, and creating timing gaps in iterative processing loops (e.g., polling with `tLoop` + `tSleep`).

**Source**: [tSleep (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/orchestration/tsleep), [tSleep Standard Properties (Talend 7.3)](https://help.qlik.com/talend/r/en-US/7.3/orchestration/tsleep-standard-properties), [tSleep Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/orchestration/tsleep-standard-properties)

**Component family**: Orchestration
**Available in**: All Talend products (Standard Job framework)
**Required JARs**: None (pure Java `Thread.sleep()` under the hood)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Pause (in second) | `PAUSE` | Integer/Expression | `1000` (milliseconds internally, displayed as seconds in UI) | **Mandatory**. Duration the job execution is paused for, specified in seconds in the UI. Internally, Talend generates `Thread.sleep(pause_value * 1000)` to convert seconds to milliseconds. The field accepts integer values and Java expressions (e.g., `context.delay`, `globalMap.get("sleep_time")`, arithmetic like `5 + 2`). The Talend default in the UI is 1 second. |

**Note on units**: The Talend Studio UI labels this field "Pause (in second)" and accepts a value in **seconds**. The generated Java code multiplies this by 1000 for `Thread.sleep()` which takes milliseconds. There is no separate "unit" selector -- the input is always seconds. Community discussions confirm that sub-second precision is not natively supported by the UI field (integer only), though workarounds using `tJava` with `Thread.sleep(milliseconds)` exist.

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 2 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input / Output | Row > Main | Data flows through tSleep unchanged. tSleep acts as a pass-through: it receives a data flow, pauses, then forwards the same data to the next component. |
| `ITERATE` | Input / Output | Iterate | Enables iterative processing. tSleep can receive iterate links (e.g., from `tLoop`, `tFileList`) and output iterate links. Common pattern: `tLoop` -> `tSleep` -> `tREST` for rate-limited API calls. |
| `REJECT` | Input | Row > Reject | tSleep can receive reject flows from upstream components. It does NOT generate reject rows itself. |
| `SUBJOB_OK` | Input / Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Used for chaining subjobs. tSleep can receive this trigger from upstream subjobs. |
| `SUBJOB_ERROR` | Input / Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. More granular than SUBJOB_OK. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` | Input / Output (Trigger) | Trigger | Conditional trigger with a boolean expression. The target component only executes if the condition evaluates to true. |
| `SYNCHRONIZE` | Input (Trigger) | Trigger | Synchronization trigger for parallel execution flows. |
| `PARALLELIZE` | Input (Trigger) | Trigger | Parallelization trigger from `tParallelize` component. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_ERROR_MESSAGE` | String | After (on error) | Error message generated when tSleep encounters an error. Only available when `Die on error` is unchecked (though tSleep has no explicit die_on_error UI parameter; this is the standard Talend error variable pattern). |

**Note on NB_LINE**: tSleep does NOT officially document `{id}_NB_LINE`, `{id}_NB_LINE_OK`, or `{id}_NB_LINE_REJECT` as global variables. As an Orchestration component (not a data processing component), it does not track row counts in the same way as input/output/transform components. The only documented global variable is `ERROR_MESSAGE`.

### 3.5 Behavioral Notes

1. **Pass-through component**: tSleep does not modify data flowing through it. Input data is forwarded unchanged to the output. It acts purely as a timing control mechanism.

2. **Thread blocking**: tSleep blocks the execution thread via Java's `Thread.sleep()`. During the sleep, no other components in the same subjob execute. Components in parallel subjobs (via `tParallelize`) are not affected.

3. **Integer seconds only**: The Talend UI accepts integer values for the pause duration. Sub-second precision is not natively supported. For millisecond-level control, users must use `tJava` with `Thread.sleep(milliseconds)`.

4. **Context variable support**: The Pause field accepts Talend expressions, including `context.variableName`, `globalMap.get("key")`, and arithmetic expressions. These are resolved at runtime by the Talend expression engine.

5. **Zero or negative values**: A pause value of 0 or less results in no actual sleep operation -- the component immediately passes through to the next component in the flow.

6. **Interrupt handling**: In Talend's Java runtime, `Thread.sleep()` can throw `InterruptedException`. The generated code catches this and either rethrows or continues depending on die_on_error configuration.

7. **No schema definition**: tSleep does not define its own output schema. It inherits the schema from its input connection and passes it through unchanged.

8. **Typical placement**: tSleep is most commonly placed:
   - Between subjobs connected by `OnSubjobOk` triggers
   - Inside iterate loops (`tLoop` / `tFileList` -> `tSleep` -> processing component)
   - Before components that require a delay (e.g., waiting for file availability)

9. **No DIE_ON_ERROR UI field**: Unlike most components, tSleep does not expose a `Die on error` checkbox in the Talend Studio UI. Since `Thread.sleep()` rarely fails (only on thread interruption), error handling is minimal. However, the standard `ERROR_MESSAGE` global variable is still available via the After-scope variable mechanism.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated `parse_tsleep()` method** in `component_parser.py` (lines 1099-1105). There IS a dedicated `elif component_type == 'tSleep'` branch in `converter.py:_parse_component()` (line 256-257). The component is also registered in the `TYPE_MAP` at line 89 as `'tSleep': 'SleepComponent'`.

**Converter flow**:
1. `converter.py:_parse_component()` matches `component_type == 'tSleep'` (line 256)
2. Calls `self.component_parser.parse_tsleep(node, component)` (line 257)
3. `parse_tsleep()` iterates `elementParameter[@name="PAUSE"]` nodes
4. Converts `PAUSE` value to `float` and stores as `pause_duration`
5. Returns component with updated config

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `PAUSE` | **Yes** | `pause_duration` | 1102-1103 | **BUG**: `float(param.get('value', '0'))` crashes on context variables (e.g., `context.delay`) and Java expressions (e.g., `5 + 2`) with `ValueError`. Should preserve as string for runtime resolution. |
| 2 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 3 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact) |
| 4 | `UNIQUE_NAME` | Implicit | `component_id` | base parser | Extracted by base parser as the component's unique identifier |

**Summary**: 1 of 4 parameters extracted (25%). However, tSleep is a simple component with only 1 runtime-relevant parameter (`PAUSE`). The critical issue is that the extraction of `PAUSE` is buggy for non-literal values.

### 4.2 Schema Extraction

Not applicable. tSleep does not define its own schema. It is a pass-through component that inherits the schema from its input connection. The converter does not extract any schema metadata for tSleep.

### 4.3 Expression Handling

**Context variable handling in `parse_tsleep()`**:
- The `float()` cast on line 1103 is applied BEFORE any context variable or Java expression resolution
- If `PAUSE` contains `context.delay`, `float("context.delay")` raises `ValueError` and crashes the converter
- The generic `parse_base_component()` method handles context variable detection (checking for `'context.' in value` and wrapping as `${context.var}`), but `parse_tsleep()` bypasses this by directly calling `float()` on the raw XML value
- Java expression marking (`mark_java_expression()`) happens AFTER the parser method returns, but by that time the `float()` cast has already occurred (or crashed)

**Critical gap**: The converter cannot handle the common Talend pattern of using `context.delay` or `globalMap.get("sleep_time")` as the PAUSE value. These expressions must be preserved as strings and resolved at runtime by the engine.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-SLP-001 | **P1** | **`float()` cast crashes on context variables and expressions**: `parse_tsleep()` line 1103 calls `float(param.get('value', '0'))`. If the Talend XML contains `PAUSE="context.delay"` or `PAUSE="(Integer)globalMap.get(\"tLoop_1_CURRENT_VALUE\")"` or any Java expression, `float()` raises `ValueError` and the entire conversion fails. The value should be preserved as a string (like `_map_component_parameters()` does for `LIMIT` in tFileInputDelimited) and resolved at runtime. |
| CONV-SLP-002 | **P1** | **Java expression marking bypassed**: Because `float()` is called before `mark_java_expression()` runs, Java expressions in the `PAUSE` field (e.g., `context.delay + 5`, `Integer.parseInt(globalMap.get("wait"))`) are never marked with `{{java}}` prefix. Even if `float()` did not crash, the expression would be stored as a number, losing the original expression. |
| CONV-SLP-003 | **P3** | **Default value mismatch**: `param.get('value', '0')` uses `'0'` as default. The Talend UI default for PAUSE is `1` second. If the XML attribute is missing (unlikely but possible), the converter produces a 0-second sleep instead of a 1-second sleep. Downgraded from P2: the PAUSE attribute is always present in well-formed Talend exports, making the default `'0'` fallback practically unreachable. |
| CONV-SLP-004 | **P3** | **`TSTATCATCHER_STATS` not extracted**: tStatCatcher statistics support unavailable. Low priority -- rarely used in production. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Sleep for configured duration | **Yes** | High | `_process()` line 117-118 | Uses `time.sleep(pause_duration)` -- correct |
| 2 | Pass-through data | **Yes** | High | `_process()` line 129 | Returns `input_data` unchanged or empty DataFrame if no input |
| 3 | Context variable in pause_duration | **Yes** | High | `_get_pause_duration()` line 156-157 | Uses `self.context_manager.resolve_string()` for `${context.var}` resolution |
| 4 | Numeric string conversion | **Yes** | High | `_get_pause_duration()` line 161 | `float(resolved_value)` handles `"5"`, `"1.5"`, etc. |
| 5 | Non-positive duration handling | **Yes** | High | `_process()` line 117-120 | Skips sleep for `<= 0`, logs debug message |
| 6 | Configuration validation | **Yes** | Medium | `_validate_config()` line 59-84, called from `_process()` line 103-108 | Validates type and parsability. **Notably: actually called**, unlike other components where `_validate_config()` is dead code |
| 7 | Error handling | **Yes** | Medium | `_process()` lines 131-136 | Catches `ConfigurationError` and generic `Exception`. Wraps in `ComponentExecutionError`. |
| 8 | Statistics tracking | **Partial** | Low | `_process()` line 126 | Always reports `(1, 1, 0)` -- semantically questionable for an Orchestration component. See ENG-SLP-002. |
| 9 | `{id}_ERROR_MESSAGE` globalMap | **No** | N/A | -- | Not implemented. Talend documents this as the sole global variable for tSleep. |
| 10 | Sub-second precision | **Yes** | High | `_get_pause_duration()` returns `float` | `time.sleep(0.5)` works in Python. Talend UI only supports integer seconds, but the engine accepts floats -- this is a feature enhancement. |
| 11 | Java expression in pause_duration | **Partial** | Low | Via `BaseComponent.execute()` line 197-198 | `_resolve_java_expressions()` resolves `{{java}}` markers BEFORE `_process()`. However, converter bug CONV-SLP-001 prevents expressions from reaching the engine. If manually set in JSON config, the Java bridge would resolve them. |
| 12 | Die on error | **No** | N/A | -- | Not implemented. tSleep always raises on error (ConfigurationError or ComponentExecutionError). No `die_on_error` flag to control graceful degradation. |
| 13 | Interrupt handling | **No** | N/A | -- | Python's `time.sleep()` can be interrupted by signals, but there is no explicit `KeyboardInterrupt` or signal handler. In CPython, `time.sleep()` is interruptible, but the component does not handle the interruption gracefully. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-SLP-001 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: Talend documents `ERROR_MESSAGE` as the sole After-scope global variable for tSleep. When an error occurs, the message should be stored in `globalMap` as `{id}_ERROR_MESSAGE` for downstream error handling. The engine does set `self.error_message` on the component instance (base_component.py line 229), but never writes it to `global_map`. Downstream components referencing `globalMap.get("tSleep_1_ERROR_MESSAGE")` will get None. |
| ENG-SLP-002 | **P1** | **NB_LINE always 1 -- semantically incorrect for Orchestration component**: The engine always calls `self._update_stats(1, 1, 0)` (line 126), treating each sleep as "1 line processed". Talend does not define `NB_LINE` for tSleep because it is not a data-processing component. While this does not cause runtime errors, it produces misleading statistics. If tSleep is in an iterate loop that runs 100 times, `NB_LINE` accumulates to 100, which has no meaningful interpretation. The base class `_update_global_map()` then writes `{id}_NB_LINE = 100` to globalMap, which could confuse downstream logic that checks `NB_LINE` to determine if data was processed. Should either report `(0, 0, 0)` or skip stats entirely for Orchestration components. |
| ENG-SLP-003 | **P2** | **No die_on_error support**: The engine always raises exceptions on error. Talend's standard `Die on error` pattern (continue job on error, set ERROR_MESSAGE) is not available. If a configuration error occurs (e.g., unparseable pause_duration context variable), the entire job fails instead of continuing to the next subjob. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | No (not documented for tSleep) | **Yes** | `_update_stats(1, 1, 0)` -> `_update_global_map()` -> `global_map.put_component_stat()` | V1 sets this but Talend does not define it for Orchestration components. Semantically misleading. |
| `{id}_NB_LINE_OK` | No (not documented for tSleep) | **Yes** | Same mechanism | Always 1. Same semantic concern. |
| `{id}_NB_LINE_REJECT` | No (not documented for tSleep) | **Yes** | Same mechanism | Always 0. Harmless but unnecessary. |
| `{id}_ERROR_MESSAGE` | **Yes** (official) | **No** | -- | **The only Talend-documented globalMap variable for tSleep is missing.** |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class `execute()` line 217 | V1-specific, not in Talend. Useful for monitoring sleep accuracy. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-SLP-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. The for loop completes all `.put_component_stat()` calls successfully, but then crashes on the log statement, which occurs AFTER the loop. This means stats ARE written to globalMap, but the method raises an exception, which propagates to `execute()`, where it is caught by the outer try/except (line 227-234), setting `self.status = ComponentStatus.ERROR` and re-raising. **Result**: Every SleepComponent execution with a non-None `global_map` will crash after completing the sleep and writing stats, but before returning success. **CROSS-CUTTING**: This bug affects ALL components, not just SleepComponent, since `_update_global_map()` is called after every component execution (via `execute()` line 218). |
| BUG-SLP-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. This means that any code calling `global_map.get("tSleep_1_ERROR_MESSAGE")` or similar will crash. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-SLP-003 | **P1** | `src/converters/complex_converter/component_parser.py:1103` | **`float()` cast crashes on context variables and Java expressions**: `parse_tsleep()` calls `float(param.get('value', '0'))` on the raw PAUSE XML value. If the Talend job uses `context.delay`, `globalMap.get("wait")`, or any expression (e.g., `5 + 2`), `float()` raises `ValueError` and the entire Talend-to-v1 conversion crashes. This is a common pattern in Talend jobs, especially when tSleep is used in iterate loops with variable pause durations. The converter should preserve the value as a string for runtime resolution, not cast to float. |
| BUG-SLP-004 | **P1** | `src/v1/engine/components/control/sleep.py` (`_validate_config()`) | **`float('inf')` blocks thread forever**: `_validate_config()` accepts `float('inf')` because it passes `isinstance(duration, float)` and `> 0` check. `time.sleep(float('inf'))` blocks the thread indefinitely with no timeout or upper-bound guard. Additionally, `float('nan')` passes the `isinstance` check but fails the `> 0` comparison silently (NaN comparisons always return False), causing the sleep to be skipped without any warning. Both special float values should be explicitly rejected during validation. |
| BUG-SLP-005 | **P1** | `src/v1/engine/base_component.py:202`, `src/v1/engine/components/control/sleep.py` (`_get_pause_duration()`) | **Double context resolution -- redundant and potentially destructive**: `execute()` calls `resolve_dict(self.config)` at `base_component.py:202`, which resolves all `${context.var}` patterns in config values. Then `_get_pause_duration()` calls `resolve_string()` again on the already-resolved value. This is redundant at best. At worst, if a resolved value happens to contain a substring matching `context.` (e.g., a file path like `/data/context.csv`), the second resolution pass can mangle it into an unintended substitution or corrupt the value entirely. |
| BUG-SLP-006 | **P2** | `src/v1/engine/base_component.py:202` | **`self.config` mutated by `execute()` -- non-reentrant**: `resolve_dict` replaces `self.config` with a resolved copy (`base_component.py:202`). In iterate loops with changing context values, the second execution resolves an already-resolved config instead of the original template. This means dynamic context variables (e.g., `${context.current_delay}` that changes per iteration) are frozen to the value from the first iteration. Additionally, config string values containing the literal substring `context.` (such as file paths) can be corrupted by the resolution pass. This affects all components, not just SleepComponent. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-SLP-001 | **P3** | **`pause_duration` (v1) vs `PAUSE` (Talend)**: The config key is `pause_duration` while Talend uses `PAUSE`. The STANDARDS.md convention for config keys is to use descriptive snake_case, so `pause_duration` is appropriate. The added `_duration` suffix adds clarity. No action needed. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-SLP-001 | **P2** | "`_validate_config()` should be called" (METHODOLOGY.md) | Unlike most other components where `_validate_config()` is dead code, SleepComponent DOES call it from `_process()` (line 103-108). This is **CORRECT** and demonstrates proper standards compliance. Other components should follow this pattern. |
| STD-SLP-002 | **P3** | "Module-level `logger = logging.getLogger(__name__)`" (STANDARDS.md) | Correct. Logger is set up at module level (line 15). |

### 6.4 Debug Artifacts

No debug artifacts, commented-out code, or `# ...existing code...` markers found in `sleep.py`. The code is clean.

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-SLP-001 | **P3** | **No upper bound on pause_duration**: A config value of `pause_duration: 999999` would block the execution thread for ~11.5 days. While not a traditional security vulnerability, in a production environment this could be used for resource exhaustion (denial of service). Consider adding a configurable maximum sleep duration (e.g., 3600 seconds = 1 hour) with a warning log when exceeded. Low priority since config comes from trusted Talend-converted jobs. |

### 6.6 Logging Quality

The component has good logging throughout:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start/sleep/complete, DEBUG for non-positive skip, WARNING for conversion failures, ERROR for processing failures -- correct |
| Start/complete logging | `_process()` logs "Processing started" (line 100), "Sleeping for X seconds" (line 114), "Sleep completed" (line 123) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |
| Duration logging | Logs the actual pause_duration value before sleeping -- useful for debugging timing issues |
| Conversion warnings | `_get_pause_duration()` logs warning when value cannot be converted to float (line 163, 167) -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError` and `ComponentExecutionError` from `exceptions.py` -- correct |
| Exception chaining | Uses `raise ComponentExecutionError(...) from e` pattern (line 136) -- correct |
| ConfigurationError passthrough | `except ConfigurationError: raise` preserves the original error without double-wrapping (line 131-133) -- correct |
| No bare `except` | All except clauses specify `ConfigurationError` or `Exception` -- correct |
| Error messages | Include component ID and descriptive context -- correct |
| Graceful degradation for parse failure | `_get_pause_duration()` returns `0.0` on unparseable values instead of crashing (line 164) -- correct, but logs only at WARNING level |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints (`List[str]`, `Dict[str, Any]`, `float`) -- correct |
| Parameter types | `_process()` has `input_data: Optional[pd.DataFrame] = None` -- correct |
| Return types | `_validate_config() -> List[str]`, `_get_pause_duration() -> float` -- correct |

### 6.9 Code Structure Quality

| Aspect | Assessment |
|--------|------------|
| Single Responsibility | `_process()` orchestrates, `_get_pause_duration()` handles conversion, `_validate_config()` validates -- correct separation |
| Method length | `_process()` is 37 lines, `_get_pause_duration()` is 31 lines, `_validate_config()` is 25 lines -- all within reasonable bounds |
| Docstrings | All three methods have comprehensive docstrings with Args, Returns, Raises sections -- correct |
| Class docstring | 37-line class docstring with configuration, inputs, outputs, statistics, examples, and notes -- exemplary |
| Default handling | `self.config.get('pause_duration', 0)` provides sensible default -- correct |
| Type coercion robustness | Handles `int`, `float`, `str`, and other types gracefully in `_get_pause_duration()` -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-SLP-001 | **P2** | **Streaming mode causes redundant sleep execution**: When `execution_mode=HYBRID` and input data exceeds `MEMORY_THRESHOLD_MB` (3GB), `BaseComponent._execute_streaming()` (base_component.py lines 255-278) splits the input DataFrame into chunks and calls `_process()` for EACH chunk. Since `_process()` calls `time.sleep()`, the component will sleep N times (once per chunk) instead of once. For a 6GB DataFrame with 100K chunk_size, this could mean hundreds of redundant sleeps. A 5-second sleep becomes a minutes-long pause. This is unlikely in practice since tSleep rarely receives large DataFrames, but it is architecturally incorrect. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Inherited from `BaseComponent`. Works but causes redundant sleep (see PERF-SLP-001). |
| Memory allocation | No additional memory allocation beyond input pass-through. `pd.DataFrame()` created only when `input_data is None` (line 129). |
| Pass-through efficiency | Returns `input_data` directly (no copy). Memory efficient. |
| No intermediate DataFrames | No data transformation, so no intermediate copies. |

### 7.2 Thread Safety

| Aspect | Assessment |
|--------|------------|
| `time.sleep()` | Thread-safe. Blocks only the calling thread. Other threads continue executing. |
| Config access | `self.config` is read-only during `_process()`. No thread safety concern. |
| Stats update | `_update_stats()` modifies `self.stats` dict. Not thread-safe if multiple threads call `execute()` on the same instance. However, Talend components are designed for single-thread execution per instance. |
| Context manager | `self.context_manager.resolve_string()` is called if available. Thread safety depends on ContextManager implementation. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `SleepComponent` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found for tSleep |
| Converter unit tests | **No** | -- | No dedicated test for `parse_tsleep()` |

**Key finding**: The v1 engine has ZERO tests for this component. All 169 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic sleep with numeric duration | P0 | Configure `pause_duration=0.01` (10ms), verify execution completes in approximately 10ms +/- tolerance, verify status is SUCCESS |
| 2 | Zero duration (no sleep) | P0 | Configure `pause_duration=0`, verify no actual sleep occurs (execution < 1ms), verify "Skipping sleep" debug log emitted |
| 3 | Negative duration (no sleep) | P0 | Configure `pause_duration=-5`, verify no actual sleep occurs, verify debug log |
| 4 | Pass-through with DataFrame | P0 | Provide input DataFrame, verify output `main` is identical (same object reference), verify no data modification |
| 5 | No input (None) | P0 | Call with `input_data=None`, verify output is empty DataFrame with correct type |
| 6 | Statistics tracking | P0 | Verify `NB_LINE=1`, `NB_LINE_OK=1`, `NB_LINE_REJECT=0` after execution |
| 7 | GlobalMap integration | P0 | Provide a `global_map`, verify `{id}_NB_LINE` etc. are set correctly (after fixing BUG-SLP-001/002) |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Context variable resolution | P1 | Configure `pause_duration="${context.delay}"`, set context `delay=0.01`, verify sleep occurs for resolved duration |
| 9 | Numeric string duration | P1 | Configure `pause_duration="2.5"` (string), verify conversion to 2.5 float and correct sleep duration |
| 10 | Invalid string duration | P1 | Configure `pause_duration="not_a_number"`, verify warning logged and 0.0 default used |
| 11 | Unresolvable context variable | P1 | Configure `pause_duration="${context.missing}"` without setting context, verify graceful fallback to 0.0 with warning |
| 12 | Configuration validation error | P1 | Configure `pause_duration=[1, 2, 3]` (list type), verify `ConfigurationError` raised |
| 13 | ComponentExecutionError wrapping | P1 | Mock `time.sleep()` to raise `OSError`, verify `ComponentExecutionError` is raised with original exception chained |
| 14 | Execution status tracking | P1 | Verify `status` transitions: PENDING -> RUNNING -> SUCCESS (or ERROR on failure) |
| 15 | Float precision (sub-second) | P1 | Configure `pause_duration=0.001` (1ms), verify `time.sleep(0.001)` is called |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 16 | Large DataFrame pass-through | P2 | Verify tSleep passes through a 100K-row DataFrame unchanged without memory duplication |
| 17 | Empty DataFrame pass-through | P2 | Provide empty DataFrame (`pd.DataFrame()`), verify it passes through unchanged |
| 18 | DataFrame with NaN values | P2 | Provide DataFrame containing NaN, None, empty strings. Verify all values pass through unchanged (no NaN coercion) |
| 19 | Streaming mode with chunks | P2 | Set `execution_mode='streaming'` with chunked input, verify sleep executes (note: will sleep per chunk -- document this behavior) |
| 20 | Concurrent execution | P2 | Two SleepComponent instances sleeping simultaneously, verify both complete independently |
| 21 | Java expression resolution | P2 | Set `pause_duration="{{java}}context.delay + 1"` with Java bridge, verify resolution and correct sleep |
| 22 | Very large pause_duration | P2 | Configure `pause_duration=0.01`, verify no crash. Then verify behavior documentation for extremely large values. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-SLP-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. The sleep completes but the component reports ERROR status. |
| BUG-SLP-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-SLP-001 | Testing | Zero v1 unit tests for SleepComponent. All 169 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-SLP-001 | Converter | `float()` cast in `parse_tsleep()` crashes on context variables and Java expressions. The most common tSleep usage pattern (variable pause duration) cannot be converted. |
| CONV-SLP-002 | Converter | Java expression marking bypassed because `float()` is called before `mark_java_expression()` runs. Expressions are lost even if they happen to be numeric. |
| ENG-SLP-001 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap -- the ONLY Talend-documented global variable for tSleep is missing. |
| ENG-SLP-002 | Engine | `NB_LINE` always 1 -- semantically incorrect for Orchestration component. Accumulates misleadingly in iterate loops. Talend does not define `NB_LINE` for tSleep. |
| BUG-SLP-003 | Bug (Converter) | `float()` cast in `parse_tsleep()` line 1103 crashes on non-numeric PAUSE values (context vars, expressions). Converter fails entirely. |
| BUG-SLP-004 | Bug (Engine) | `float('inf')` blocks thread forever. `_validate_config()` accepts `float('inf')` (passes `isinstance(duration, float)` and `> 0` check). `time.sleep(float('inf'))` blocks indefinitely with no timeout. Also `float('nan')` passes isinstance but fails `> 0` silently. |
| BUG-SLP-005 | Bug (Engine/Cross-Cutting) | Double context resolution. `execute()` calls `resolve_dict(self.config)` at `base_component.py:202`, then `_get_pause_duration()` calls `resolve_string()` again on already-resolved value. Redundant at best, can mangle values containing `context.` substring. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| ENG-SLP-003 | Engine | No `die_on_error` support. Errors always raise exceptions. No graceful degradation with `ERROR_MESSAGE` globalMap variable. |
| PERF-SLP-001 | Performance | Streaming mode causes redundant sleep execution per chunk. Unlikely in practice but architecturally incorrect. |
| STD-SLP-001 | Standards | `_validate_config()` IS called (line 103-108) -- this is CORRECT and exemplary. Noted as positive finding. Other components should follow this pattern. |
| BUG-SLP-006 | Bug (Engine/Cross-Cutting) | `self.config` mutated by `execute()` -- non-reentrant. `resolve_dict` replaces config with resolved copy (`base_component.py:202`). In iterate loops with changing context, second execution resolves already-resolved config. File paths containing `context.` substring get corrupted. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-SLP-003 | Converter | Default value `'0'` differs from Talend default `1` second. Missing PAUSE attribute produces 0-second sleep instead of 1-second sleep. Downgraded from P2: the PAUSE attribute is always present in well-formed Talend exports, making the default `'0'` fallback practically unreachable. |
| CONV-SLP-004 | Converter | `TSTATCATCHER_STATS` not extracted. Low priority -- rarely used. |
| NAME-SLP-001 | Naming | `pause_duration` vs Talend `PAUSE` -- intentional, follows STANDARDS.md snake_case convention. No action needed. |
| SEC-SLP-001 | Security | No upper bound on `pause_duration`. Could block thread indefinitely with very large values. Low risk from trusted config. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 7 | 2 converter, 2 engine, 3 bugs (1 converter, 1 engine, 1 engine/cross-cutting) |
| P2 | 4 | 1 engine, 1 performance, 1 standards (positive), 1 bug (engine/cross-cutting) |
| P3 | 4 | 1 converter (downgraded from P2), 1 converter, 1 naming, 1 security |
| **Total** | **18** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-SLP-001): Change `value` to `stat_value` on `base_component.py` line 304, or better yet, remove the stale `{stat_name}: {value}` reference entirely and log only the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-SLP-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-SLP-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic sleep, zero/negative duration, pass-through, None input, statistics, and globalMap integration. The component is simple enough that all 22 test cases could be implemented quickly.

4. **Fix converter `float()` crash** (CONV-SLP-001 / BUG-SLP-003): Replace `float(param.get('value', '0'))` with logic that preserves string values for runtime resolution:

```python
def parse_tsleep(self, node, component: Dict) -> Dict:
    """Parse tSleep specific configuration"""
    for param in node.findall('./elementParameter[@name="PAUSE"]'):
        raw_value = param.get('value', '1')  # Talend default is 1 second
        try:
            # Try numeric conversion for literal values
            component['config']['pause_duration'] = float(raw_value)
        except (ValueError, TypeError):
            # Preserve as string for context variable / expression resolution
            component['config']['pause_duration'] = raw_value
    return component
```

### Short-Term (Hardening)

5. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-SLP-001): In the `except Exception as e` block of `_process()` (line 134-136), before raising, store the error message:

```python
except Exception as e:
    logger.error(f"[{self.id}] Processing failed: {e}")
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
    raise ComponentExecutionError(self.id, f"Sleep operation failed: {e}", e) from e
```

Also set it in the `except ConfigurationError` block for configuration errors. This is the ONLY Talend-documented global variable for tSleep.

6. **Fix NB_LINE semantics** (ENG-SLP-002): Change `_update_stats(1, 1, 0)` to `_update_stats(0, 0, 0)` since tSleep is an Orchestration component, not a data processing component. Alternatively, skip the `_update_stats()` call entirely and let the base class defaults (all zeros) stand. This prevents misleading `NB_LINE` accumulation in iterate loops.

7. **Add `die_on_error` support** (ENG-SLP-003): Extract `die_on_error` from config, and when set to False, catch errors in `_process()`, set `ERROR_MESSAGE` in globalMap, log the error, and return `{'main': input_data or pd.DataFrame()}` instead of raising.

8. **Fix converter default to match Talend** (CONV-SLP-003): Change `param.get('value', '0')` to `param.get('value', '1')` to match Talend's default of 1 second.

### Long-Term (Optimization)

9. **Override `_execute_streaming()` to avoid redundant sleep** (PERF-SLP-001): Add a `_execute_streaming()` override in SleepComponent that sleeps once and then passes all chunks through:

```python
def _execute_streaming(self, input_data):
    """Override to sleep only once regardless of chunk count"""
    # Sleep once
    self._process(None)  # Triggers the sleep
    # Then pass through all chunks without sleeping again
    if isinstance(input_data, pd.DataFrame):
        return {'main': input_data}
    # ... handle iterator case
```

Alternatively, since tSleep is a pass-through component, simply override `_auto_select_mode()` to always return `BATCH`.

10. **Add maximum duration guard** (SEC-SLP-001): Add a configurable `MAX_SLEEP_SECONDS` constant (e.g., 3600) and log a warning when `pause_duration > MAX_SLEEP_SECONDS`. Do not clamp the value (to maintain Talend compatibility), but alert operators.

11. **Propagate `_validate_config()` pattern to other components** (STD-SLP-001): SleepComponent correctly calls `_validate_config()` from `_process()`. This pattern should be propagated to all other components where `_validate_config()` exists but is never called (e.g., `FileInputDelimited`, `FileOutputDelimited`, etc.).

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 1099-1105
def parse_tsleep(self, node, component: Dict) -> Dict:
    """Parse tSleep specific configuration"""
    # Extract the pause duration
    for param in node.findall('./elementParameter[@name="PAUSE"]'):
        component['config']['pause_duration'] = float(param.get('value', '0'))

    return component
```

**Notes on this code**:
- Line 1103: `float(param.get('value', '0'))` crashes on non-numeric values (context variables, Java expressions). This is the most critical converter bug.
- The `for` loop iterates `elementParameter[@name="PAUSE"]` nodes. In practice, there should be exactly one such node. If none exist, the `for` loop body never executes and `pause_duration` is never set in config, relying on the engine's default of `0`.
- Default `'0'` differs from Talend default of `1` second.
- No handling of `TSTATCATCHER_STATS`, `DIE_ON_ERROR`, or `LABEL` parameters.

---

## Appendix B: Engine Class Structure

```
SleepComponent (BaseComponent)
    Constants:
        (none -- uses base class defaults)

    Methods (own):
        _validate_config() -> List[str]          # CALLED from _process() -- working validation
        _process(input_data) -> Dict[str, Any]    # Main entry point -- sleep + pass-through
        _get_pause_duration() -> float            # Safe duration extraction with context resolution

    Inherited from BaseComponent:
        execute(input_data) -> Dict[str, Any]     # Lifecycle: Java expr -> context -> mode select -> _process() -> stats -> globalMap
        _determine_execution_mode() -> ExecutionMode
        _resolve_java_expressions() -> None
        _auto_select_mode(input_data) -> ExecutionMode
        _execute_batch(input_data) -> Dict        # Calls _process()
        _execute_streaming(input_data) -> Dict    # Chunked -- causes redundant sleep
        _create_chunks(df) -> Iterator[DataFrame]
        _update_stats(read, ok, reject) -> None
        _update_global_map() -> None              # BUG: references undefined 'value'
        validate_schema(df, schema) -> DataFrame
        get_status() -> ComponentStatus
        get_stats() -> Dict
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `PAUSE` | `pause_duration` | **Mapped (buggy)** | P1 -- fix `float()` crash |
| `TSTATCATCHER_STATS` | -- | Not Mapped | P3 (rarely used) |
| `DIE_ON_ERROR` | -- | Not Mapped | P2 (implicit in Talend; no UI field for tSleep but standard pattern) |
| `LABEL` | -- | Not Mapped | -- (cosmetic, no runtime impact) |
| `UNIQUE_NAME` | `component_id` | Mapped (base parser) | -- |

---

## Appendix D: Execution Flow Trace

### Normal execution (happy path)

```
1. Engine calls SleepComponent.execute(input_data=DataFrame)
2. execute() sets status = RUNNING, records start_time
3. execute() calls _resolve_java_expressions()  -- resolves {{java}} markers if java_bridge present
4. execute() calls context_manager.resolve_dict(self.config)  -- resolves ${context.var} in ALL config values
5. execute() calls _auto_select_mode(input_data)  -- returns BATCH (unless input > 3GB)
6. execute() calls _execute_batch(input_data)
7. _execute_batch() calls _process(input_data)
8. _process() calls _validate_config()  -- checks pause_duration type/parsability
9. _process() calls _get_pause_duration()  -- extracts and converts to float
10. _get_pause_duration() checks self.config['pause_duration'] type:
    - If int/float: returns float(value)
    - If str: calls context_manager.resolve_string() if available, then float()
    - If other type or unparseable: returns 0.0 with WARNING log
11. _process() logs "Sleeping for X seconds"
12. _process() calls time.sleep(X) if X > 0
13. _process() calls _update_stats(1, 1, 0)
14. _process() returns {'main': input_data}  (or empty DataFrame if input was None)
15. execute() records EXECUTION_TIME
16. execute() calls _update_global_map()  -- BUG: crashes on undefined 'value'
17. (If bug fixed) execute() sets status = SUCCESS, returns result with stats
```

### Error execution (exception path)

```
1-8. Same as above
9. _process() calls _get_pause_duration() -- returns 0.0 on parse failure (graceful)
   OR: _validate_config() returns errors -> ConfigurationError raised
10. If ConfigurationError: re-raised without wrapping
11. If other Exception: wrapped in ComponentExecutionError with 'from e' chaining
12. execute() catches exception:
    - Sets status = ERROR
    - Sets error_message = str(e)
    - Records EXECUTION_TIME
    - Calls _update_global_map()  -- BUG: crashes again, masking original error
    - Re-raises original exception
```

---

## Appendix E: Detailed Code Analysis

### `_validate_config()` (Lines 59-84)

This method validates:
- If `pause_duration` key exists in config (optional -- absence is valid, defaults to 0)
- If value is a string:
  - Checks if it looks like a context variable (`${...}`) -- these are valid
  - If not a context variable, tries `float()` conversion
  - If `float()` fails, adds error message
- If value is not a string and not int/float, adds error message
- Returns list of error strings (empty list = valid)

**Strength**: Correctly handles the common case where context variables have already been resolved by `BaseComponent.execute()` before `_process()` is called. At the point `_validate_config()` runs, `${context.var}` should already be resolved to a numeric string or number.

**Weakness**: If context resolution fails silently (returns the unresolved `${context.var}` string), `_validate_config()` treats it as a valid context variable (because it starts with `${` and ends with `}`), allowing it through. Then `_get_pause_duration()` tries `float("${context.var}")` which fails, and returns 0.0. The validation and the execution path have different failure modes for unresolved context variables.

### `_process()` (Lines 86-136)

The main processing method:
1. Log start message
2. Call `_validate_config()` and raise `ConfigurationError` if errors
3. Call `_get_pause_duration()` for safe float extraction
4. Log sleep duration
5. Call `time.sleep()` if duration > 0, else log skip
6. Log completion
7. Call `_update_stats(1, 1, 0)`
8. Return `{'main': input_data or pd.DataFrame()}`
9. Catch `ConfigurationError` and re-raise
10. Catch generic `Exception`, log, wrap in `ComponentExecutionError`, raise

### `_get_pause_duration()` (Lines 138-168)

Robust duration extraction with three branches:
1. **Already numeric** (int/float): Return `float(value)` directly
2. **String**: Attempt context resolution via `context_manager.resolve_string()`, then `float()` conversion. On failure, warn and return 0.0.
3. **Other type** (list, dict, None, etc.): Warn and return 0.0.

**Design choice**: This method NEVER raises an exception. It always returns a valid float. This is intentional -- sleep with 0 duration is harmless (just a pass-through), so defaulting to 0 on parse failure is a safe degradation.

**Interaction with BaseComponent.execute()**: The `execute()` method (base_component.py line 200-202) calls `self.context_manager.resolve_dict(self.config)` BEFORE calling `_process()`. This means by the time `_get_pause_duration()` runs, `${context.var}` references in `self.config['pause_duration']` should already be resolved to their actual values. The `context_manager.resolve_string()` call on line 157 is a secondary resolution -- it handles the case where `resolve_dict()` did not fully resolve the value (e.g., nested expressions or partial resolution).

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty config (no pause_duration key)

| Aspect | Detail |
|--------|--------|
| **Talend** | Uses default of 1 second. |
| **V1** | `self.config.get('pause_duration', 0)` returns `0`. No sleep occurs. |
| **Verdict** | **GAP** -- V1 defaults to 0 seconds, Talend defaults to 1 second. See CONV-SLP-003. |

### Edge Case 2: pause_duration = 0

| Aspect | Detail |
|--------|--------|
| **Talend** | `Thread.sleep(0)` returns immediately. |
| **V1** | `if pause_duration > 0: time.sleep(...)` -- skips sleep. Logs debug message. |
| **Verdict** | **CORRECT** -- both return immediately. |

### Edge Case 3: pause_duration = negative number

| Aspect | Detail |
|--------|--------|
| **Talend** | `Thread.sleep(-1000)` throws `IllegalArgumentException`. Caught by error handler. |
| **V1** | `if pause_duration > 0: time.sleep(...)` -- skips sleep. No error. |
| **Verdict** | **BEHAVIORAL DIFFERENCE** -- Talend errors, V1 silently succeeds. V1 behavior is arguably more robust. |

### Edge Case 4: pause_duration = NaN (float('nan'))

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- Java does not have NaN as a sleep duration. |
| **V1** | `float('nan') > 0` evaluates to `False` (NaN comparisons always False). Sleep is skipped. No error, no warning. |
| **Verdict** | **SILENT SKIP** -- NaN falls through the `> 0` check silently. Should log a warning. |

### Edge Case 5: pause_duration = empty string ""

| Aspect | Detail |
|--------|--------|
| **Talend** | Empty PAUSE field defaults to the Talend default (1 second). |
| **V1** | `_get_pause_duration()` calls `float("")` which raises `ValueError`. Caught on line 162-163, returns 0.0 with warning. |
| **Verdict** | **PARTIAL** -- V1 handles gracefully but defaults to 0 (no sleep) instead of Talend's 1 second default. |

### Edge Case 6: Context variable resolving to non-numeric value

| Aspect | Detail |
|--------|--------|
| **Talend** | Expression engine would throw a type error. Job fails or error is handled based on die_on_error. |
| **V1** | `_get_pause_duration()` tries `float(resolved_value)`, catches `ValueError`, returns 0.0 with warning log. |
| **Verdict** | **CORRECT DEGRADATION** -- V1 degrades gracefully instead of crashing. |

### Edge Case 7: Input DataFrame is empty (`pd.DataFrame()`)

| Aspect | Detail |
|--------|--------|
| **Talend** | tSleep passes empty flow through. Sleep occurs regardless. |
| **V1** | `input_data` is an empty DataFrame (truthy in pandas). `input_data is not None` is True, so it is returned unchanged. Sleep occurs. |
| **Verdict** | **CORRECT** |

### Edge Case 8: Input DataFrame contains NaN values

| Aspect | Detail |
|--------|--------|
| **Talend** | tSleep does not modify data. NaN values pass through unchanged. |
| **V1** | `_process()` returns `input_data` directly (line 129). No data transformation. NaN values are untouched. |
| **Verdict** | **CORRECT** |

### Edge Case 9: HYBRID streaming mode with large DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | tSleep sleeps once regardless of data size. |
| **V1** | If input > 3GB, `_auto_select_mode()` returns STREAMING. `_execute_streaming()` chunks the DataFrame and calls `_process()` per chunk. Each chunk triggers a sleep. |
| **Verdict** | **GAP** -- Multiple redundant sleeps. See PERF-SLP-001. |

### Edge Case 10: global_map is None

| Aspect | Detail |
|--------|--------|
| **Talend** | globalMap is always available in Talend runtime. |
| **V1** | `_update_global_map()` checks `if self.global_map:` (line 300). If None, stats are not written to globalMap. No crash. |
| **Verdict** | **CORRECT** -- graceful handling of missing globalMap. |

### Edge Case 11: global_map is not None (BUG-SLP-001 impact)

| Aspect | Detail |
|--------|--------|
| **Talend** | Global variables set correctly. |
| **V1** | `_update_global_map()` writes all stats via `put_component_stat()` (lines 301-302), then crashes on line 304 due to undefined `value` variable. The stats ARE written successfully before the crash. However, the exception propagates to `execute()`, which sets status to ERROR and re-raises. |
| **Verdict** | **CRASH** -- Sleep succeeds, stats are written, but component reports ERROR. Cross-cutting bug. |

### Edge Case 12: ComponentStatus transitions

| Aspect | Detail |
|--------|--------|
| **Talend** | Component status managed by Talend runtime. |
| **V1** | PENDING (init) -> RUNNING (execute line 192) -> SUCCESS (line 220) or ERROR (line 228). Due to BUG-SLP-001, status is always ERROR when globalMap is present, even on successful sleep. |
| **Verdict** | **BUG** -- Status incorrectly set to ERROR on successful execution. |

### Edge Case 13: _validate_config() with already-resolved context variable

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- expression resolution is part of generated Java code. |
| **V1** | `BaseComponent.execute()` calls `context_manager.resolve_dict()` before `_process()`. By the time `_validate_config()` runs, `pause_duration` should be `"5.0"` (string) or `5.0` (float), not `"${context.delay}"`. `_validate_config()` correctly validates these resolved forms. |
| **Verdict** | **CORRECT** -- The execution order (context resolution before validation) is correct. |

### Edge Case 14: Thread interruption during sleep

| Aspect | Detail |
|--------|--------|
| **Talend** | Java `Thread.sleep()` throws `InterruptedException`. Caught and handled. |
| **V1** | Python `time.sleep()` can be interrupted by signals (`KeyboardInterrupt`). The outer `except Exception as e` in `_process()` catches it and wraps in `ComponentExecutionError`. However, `KeyboardInterrupt` does NOT inherit from `Exception` in Python 3, so it would propagate uncaught to `execute()`, where the `except Exception as e` also would NOT catch it. |
| **Verdict** | **GAP** -- `KeyboardInterrupt` (Ctrl+C) during sleep would bypass all error handling and crash the engine. While this is standard Python behavior, adding explicit `except KeyboardInterrupt` could enable graceful shutdown. |

### Edge Case 15: pause_duration as boolean

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- PAUSE field is typed as integer. |
| **V1** | `isinstance(True, (int, float))` is `True` in Python (bool is a subclass of int). So `True` -> `float(True)` -> `1.0`. Component sleeps for 1 second. `False` -> `0.0`. No sleep. |
| **Verdict** | **UNEXPECTED BUT HARMLESS** -- Boolean values are silently accepted. `True` = 1 second sleep, `False` = no sleep. No validation catches this because `isinstance(True, (int, float))` passes the check on line 81. |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `SleepComponent`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-SLP-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components when `global_map` is set. |
| BUG-SLP-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-SLP-001 -- `_update_global_map()` undefined variable

**File**: `src/v1/engine/base_component.py`
**Line**: 304

**Current code (broken)**:
```python
logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} {stat_name}: {value}")
```

**Fix**:
```python
logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']}")
```

**Explanation**: `{value}` references an undefined variable (the loop variable is `stat_value`). The `{stat_name}` reference would show only the last loop iteration value, which is misleading. Best fix is to remove both stale references.

**Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

---

### Fix Guide: BUG-SLP-002 -- `GlobalMap.get()` undefined default

**File**: `src/v1/engine/global_map.py`
**Line**: 26-28

**Current code (broken)**:
```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

**Fix**:
```python
def get(self, key: str, default: Any = None) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

**Impact**: Fixes ALL components and any code calling `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

---

### Fix Guide: BUG-SLP-003 / CONV-SLP-001 -- Converter `float()` crash

**File**: `src/converters/complex_converter/component_parser.py`
**Lines**: 1099-1105

**Current code (broken for expressions)**:
```python
def parse_tsleep(self, node, component: Dict) -> Dict:
    """Parse tSleep specific configuration"""
    # Extract the pause duration
    for param in node.findall('./elementParameter[@name="PAUSE"]'):
        component['config']['pause_duration'] = float(param.get('value', '0'))

    return component
```

**Fix**:
```python
def parse_tsleep(self, node, component: Dict) -> Dict:
    """Parse tSleep specific configuration"""
    # Extract the pause duration
    for param in node.findall('./elementParameter[@name="PAUSE"]'):
        raw_value = param.get('value', '1')  # Talend default is 1 second
        try:
            component['config']['pause_duration'] = float(raw_value)
        except (ValueError, TypeError):
            # Preserve as string for context variable / expression resolution at runtime
            component['config']['pause_duration'] = raw_value

    return component
```

**Explanation**: The original code crashes on any non-numeric PAUSE value. The fix tries numeric conversion first for efficiency, but falls back to string preservation for expressions and context variables. The default is changed from `'0'` to `'1'` to match Talend's default.

**Impact**: Enables conversion of Talend jobs using context variables or expressions in tSleep PAUSE field. **Risk**: Low (the engine's `_get_pause_duration()` already handles string values correctly).

---

### Fix Guide: ENG-SLP-001 -- Setting ERROR_MESSAGE in globalMap

**File**: `src/v1/engine/components/control/sleep.py`
**Lines**: 131-136

**Current code**:
```python
except ConfigurationError:
    # Re-raise configuration errors as-is
    raise
except Exception as e:
    logger.error(f"[{self.id}] Processing failed: {e}")
    raise ComponentExecutionError(self.id, f"Sleep operation failed: {e}", e) from e
```

**Fix**:
```python
except ConfigurationError as e:
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
    raise
except Exception as e:
    logger.error(f"[{self.id}] Processing failed: {e}")
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
    raise ComponentExecutionError(self.id, f"Sleep operation failed: {e}", e) from e
```

**Impact**: Makes the only Talend-documented globalMap variable available for downstream error handling. **Risk**: Very low (only adds globalMap writes in error paths).

---

### Fix Guide: ENG-SLP-002 -- NB_LINE semantics

**File**: `src/v1/engine/components/control/sleep.py`
**Line**: 126

**Current code**:
```python
# Update statistics (always count as 1 operation)
self._update_stats(1, 1, 0)
```

**Fix (Option A -- zero stats)**:
```python
# Orchestration component -- no data processing stats
self._update_stats(0, 0, 0)
```

**Fix (Option B -- skip stats entirely)**:
```python
# Orchestration component -- no data processing to track
# Stats remain at default (0, 0, 0) from __init__
```

**Impact**: Prevents misleading NB_LINE accumulation. **Risk**: Very low -- no downstream code should depend on tSleep NB_LINE values.

---

## Appendix I: Comparison with Other Control/Orchestration Components

| Feature | tSleep (V1) | tDie (V1) | tWarn (V1) | tSendMail (V1) |
|---------|-------------|-----------|------------|----------------|
| Pass-through data | Yes | No (terminates) | Yes | No (action-only) |
| Modifies data | No | N/A | No | N/A |
| Has own schema | No | No | No | No |
| `_validate_config()` called | **Yes** | Unknown | Unknown | Unknown |
| NB_LINE tracking | Yes (always 1) | Unknown | Unknown | Unknown |
| ERROR_MESSAGE globalMap | **No** | Unknown | Unknown | Unknown |
| Die on error support | **No** | N/A (component IS die) | Unknown | Unknown |
| Context variable support | Yes (pause_duration) | Unknown | Unknown | Unknown |
| V1 Unit tests | **No** | **No** | **No** | **No** |
| Converter `float()` bug | **Yes** | N/A | N/A | N/A |

---

## Appendix J: Talend Generated Java Code Pattern

For reference, Talend generates approximately the following Java code for tSleep:

```java
// tSleep_1 - start
int tos_count_tSleep_1 = 0;
try {
    long sleepTime_tSleep_1 = (long)(1000 * pause_value);  // pause_value from PAUSE parameter
    if (sleepTime_tSleep_1 > 0) {
        Thread.sleep(sleepTime_tSleep_1);
    }
} catch (InterruptedException e_tSleep_1) {
    // Handle interruption
    if (e_tSleep_1 instanceof RuntimeException) {
        throw (RuntimeException) e_tSleep_1;
    }
}
// tSleep_1 - end
```

**Key observations**:
1. Talend multiplies PAUSE by 1000 to convert seconds to milliseconds for `Thread.sleep()`.
2. V1 uses `time.sleep(seconds)` which takes seconds directly -- correct unit handling.
3. Talend wraps in try/catch for `InterruptedException`. V1 has no explicit interrupt handling.
4. Talend uses `long` cast -- V1 uses `float`, allowing sub-second precision.

---

## Appendix K: Runtime Behavior Verification Checklist

Use this checklist to verify SleepComponent behavior after fixes are applied:

- [ ] Basic sleep: 1-second sleep completes in ~1 second (+/- 50ms tolerance)
- [ ] Zero sleep: No blocking, immediate return
- [ ] Negative sleep: No blocking, immediate return, debug log emitted
- [ ] Context variable: `${context.delay}` resolves correctly
- [ ] Numeric string: `"5"` converts to 5.0 seconds
- [ ] Invalid string: `"abc"` defaults to 0.0 with warning
- [ ] Pass-through: Input DataFrame returned identical (same object)
- [ ] None input: Empty DataFrame returned
- [ ] Empty DataFrame: Passes through unchanged
- [ ] NaN in data: Passes through unchanged
- [ ] GlobalMap stats: Written correctly (after BUG-SLP-001 fix)
- [ ] GlobalMap get: Works correctly (after BUG-SLP-002 fix)
- [ ] ERROR_MESSAGE: Set on error (after ENG-SLP-001 fix)
- [ ] Status transitions: PENDING -> RUNNING -> SUCCESS
- [ ] Converter: Context variable PAUSE preserved as string (after CONV-SLP-001 fix)
- [ ] Converter: Java expression PAUSE preserved as string (after CONV-SLP-002 fix)

---

## Appendix L: BaseComponent Lifecycle Impact on SleepComponent

### Full `execute()` Method Trace for SleepComponent

The `BaseComponent.execute()` method (base_component.py lines 188-234) is the entry point called by the v1 engine for every component. Understanding this lifecycle is critical for SleepComponent because several steps interact with the sleep behavior in non-obvious ways.

```
BaseComponent.execute(input_data)
    |
    +-- [1] self.status = ComponentStatus.RUNNING        (line 192)
    |       Sets status immediately. If engine checks status mid-execution,
    |       it will see RUNNING during the sleep.
    |
    +-- [2] start_time = time.time()                     (line 193)
    |       Records wall-clock time BEFORE Java/context resolution.
    |       EXECUTION_TIME will include resolution overhead + sleep time.
    |
    +-- [3] if self.java_bridge:                         (line 197)
    |       _resolve_java_expressions()                  (line 198)
    |       Resolves {{java}} markers in self.config BEFORE _process().
    |       For tSleep, this resolves expressions like:
    |         {{java}}context.delay + 5  ->  10
    |         {{java}}(Integer)globalMap.get("wait")  ->  30
    |       The resolved value replaces the original in self.config.
    |       After this step, self.config['pause_duration'] should be
    |       a resolved value (number or numeric string), not an expression.
    |
    +-- [4] if self.context_manager:                     (line 201)
    |       self.config = context_manager.resolve_dict() (line 202)
    |       Resolves ${context.var} patterns in ALL config values.
    |       For tSleep: ${context.delay} -> "5" (or whatever the context value is)
    |       This happens AFTER Java expression resolution, so Java-resolved
    |       values are NOT re-processed (they are already numbers/strings
    |       without ${} markers).
    |
    +-- [5] _auto_select_mode(input_data)                (line 206)
    |       For tSleep with no input or small input: returns BATCH.
    |       For tSleep with >3GB input: returns STREAMING (problematic).
    |       tSleep should ALWAYS use BATCH regardless of input size.
    |
    +-- [6] _execute_batch(input_data)                   (line 214)
    |       |
    |       +-- _process(input_data)                     (line 253)
    |           |
    |           +-- _validate_config()                   (line 103-108)
    |           +-- _get_pause_duration()                (line 111)
    |           +-- time.sleep(duration)                 (line 118)
    |           +-- _update_stats(1, 1, 0)               (line 126)
    |           +-- return {'main': input_data}           (line 129)
    |
    +-- [7] self.stats['EXECUTION_TIME'] = elapsed       (line 217)
    |       Records total time including Java/context resolution + sleep.
    |       For a 5-second sleep, EXECUTION_TIME will be ~5.0xx seconds.
    |
    +-- [8] _update_global_map()                         (line 218)
    |       Writes all stats to globalMap.
    |       BUG: crashes on undefined 'value' variable (line 304).
    |       Stats ARE written before crash (lines 301-302 complete).
    |
    +-- [9] self.status = ComponentStatus.SUCCESS         (line 220)
    |       NEVER REACHED due to BUG-SLP-001.
    |       Status remains at RUNNING, then set to ERROR in except block.
    |
    +-- [10] result['stats'] = self.stats.copy()         (line 223)
    |        NEVER REACHED due to BUG-SLP-001.
    |
    +-- [11] return result                               (line 225)
            NEVER REACHED due to BUG-SLP-001.
```

### Impact Summary: BUG-SLP-001 Cascade

The `_update_global_map()` crash on line 304 has a cascading effect:

1. `time.sleep()` completes successfully -- the actual sleep happens.
2. `_update_stats(1, 1, 0)` completes successfully -- stats dict is updated.
3. `_update_global_map()` starts, writes all stats to globalMap via `put_component_stat()`.
4. `_update_global_map()` crashes on the log statement (line 304) with `NameError: name 'value' is not defined`.
5. The `NameError` propagates to `execute()`, caught by `except Exception as e` (line 227).
6. `self.status = ComponentStatus.ERROR` is set (line 228).
7. `self.error_message = "name 'value' is not defined"` is set (line 229).
8. `_update_global_map()` is called AGAIN (line 231) -- but this time it crashes AGAIN with the same `NameError`.
9. The second `NameError` propagates, caught by the same `except Exception as e` block... but wait, we are ALREADY in the except block.
10. Actually, the second `_update_global_map()` call on line 231 would also crash, and this exception would NOT be caught (it is raised inside the except block, after the try/except scope).
11. The `NameError` from the second `_update_global_map()` call propagates up to the engine.

**Net result**: Every SleepComponent execution with a non-None globalMap raises `NameError` to the engine, despite the sleep having completed successfully. The engine will see this as a component failure.

### Impact on Other Components

This same cascade applies to ALL v1 components that inherit from `BaseComponent` and have `global_map` set. Every component will appear to fail after completing its actual work, because `_update_global_map()` always crashes.

---

## Appendix M: Context Variable Resolution Deep Dive

### Resolution Order

The context variable resolution for tSleep's `pause_duration` happens in multiple stages:

```
Stage 1: Converter (compile-time)
    Talend XML: <elementParameter name="PAUSE" value="context.delay"/>
    parse_tsleep(): float("context.delay")  -> CRASH (ValueError)

    If fixed per Fix Guide BUG-SLP-003:
    parse_tsleep(): float("context.delay") fails -> preserve "context.delay" as string
    V1 JSON config: {"pause_duration": "context.delay"}

Stage 2: Java Expression Marking (compile-time, after parse_tsleep)
    mark_java_expression() scans config values for Java patterns
    "context.delay" contains "context." -> detected as Java expression
    Marked as: {"pause_duration": "{{java}}context.delay"}

    OR if context. prefix is handled specially:
    Wrapped as: {"pause_duration": "${context.delay}"}

Stage 3: Java Bridge Resolution (runtime, execute() line 197-198)
    If marked as {{java}}:
    _resolve_java_expressions() sends "context.delay" to Java bridge
    Java bridge evaluates, returns numeric value (e.g., 5)
    Config updated: {"pause_duration": 5}

    If not marked as {{java}} (e.g., no Java bridge):
    Stays as "{{java}}context.delay" or "${context.delay}"

Stage 4: Context Manager Resolution (runtime, execute() line 201-202)
    context_manager.resolve_dict(self.config) processes ${context.var} patterns
    "${context.delay}" -> "5" (resolved from context)
    Config updated: {"pause_duration": "5"}

    If already resolved to 5 (int) by Java bridge:
    No change (int values are not processed by resolve_dict)

Stage 5: _get_pause_duration() (runtime, _process() line 111)
    If value is int/float: return float(value)  -> 5.0
    If value is "5" (string): float("5")  -> 5.0
    If value is "${context.delay}" (unresolved): float("${context.delay}")  -> ValueError
        -> context_manager.resolve_string("${context.delay}")  -> "5"
        -> float("5")  -> 5.0
    If value is "context.delay" (no markers): float("context.delay")  -> ValueError
        -> context_manager.resolve_string("context.delay")  -> "context.delay" (no ${} wrapper)
        -> float("context.delay")  -> ValueError
        -> return 0.0 with warning
```

### Failure Scenarios

| Scenario | Stage | Outcome |
|----------|-------|---------|
| Literal `5` in Talend XML | 1 (converter) | `float("5")` succeeds. `pause_duration=5.0`. Works correctly. |
| `context.delay` in Talend XML (current code) | 1 (converter) | `float("context.delay")` CRASHES. Converter fails entirely. |
| `context.delay` in Talend XML (fixed code) | 2 (marking) | Preserved as string. Marked as `{{java}}` or `${context.}`. Resolved at runtime. Works. |
| `globalMap.get("wait")` in Talend XML (current code) | 1 (converter) | `float("globalMap.get(\"wait\")")` CRASHES. Converter fails entirely. |
| `globalMap.get("wait")` in Talend XML (fixed code) | 2 (marking) | Preserved as string. Marked as `{{java}}`. Resolved by Java bridge. Works if bridge available. |
| `5 + context.delay` in Talend XML (current code) | 1 (converter) | `float("5 + context.delay")` CRASHES. |
| `5 + context.delay` in Talend XML (fixed code) | 3 (Java bridge) | Resolved by Java bridge. Returns numeric result. Works. |
| No PAUSE attribute in XML | 1 (converter) | Default `'0'` (current) or `'1'` (fixed). `float()` succeeds. |
| Empty PAUSE value `""` | 5 (engine) | `float("")` -> ValueError -> 0.0 default with warning. |

---

## Appendix N: Detailed Converter Dispatch Analysis

### How tSleep Reaches `parse_tsleep()`

The full converter dispatch chain for tSleep is:

```
1. converter.py: convert(talend_xml_path)
       Parses the .item XML file
       Iterates <node> elements

2. converter.py: _parse_component(node)
       Extracts componentName attribute from XML node
       e.g., componentName="tSleep"

3. converter.py line 256-257:
       elif component_type == 'tSleep':
           component = self.component_parser.parse_tsleep(node, component)

       At this point, `component` already has:
       - component['id'] = UNIQUE_NAME (e.g., "tSleep_1")
       - component['type'] = TYPE_MAP.get('tSleep') = 'SleepComponent'
       - component['config'] = {}  (empty, to be populated by parser)
       - component['metadata'] = {}

4. component_parser.py: parse_tsleep(node, component)
       Finds elementParameter[@name="PAUSE"] nodes
       Extracts value attribute
       Stores as component['config']['pause_duration']
       Returns component

5. Back in converter.py: _parse_component(node)
       Calls mark_java_expression(component) for Java expression detection
       Returns fully-parsed component
```

### TYPE_MAP Registration

```python
# component_parser.py line 89
'tSleep': 'SleepComponent',
```

This maps the Talend component name `tSleep` to the v1 engine class name `SleepComponent`. The engine then uses this class name to look up the actual class in its registry:

```python
# engine.py lines 177-178
'SleepComponent': SleepComponent,
'tSleep': SleepComponent,
```

Both aliases resolve to the same `SleepComponent` class, allowing both the Talend name (`tSleep`) and the v1 name (`SleepComponent`) to be used in job configurations.

### parse_tsleep() vs Other Parsers

Compared to other parser methods in `component_parser.py`:

| Parser | Lines | Parameters Extracted | Data Validation | Expression Handling |
|--------|-------|---------------------|-----------------|---------------------|
| `parse_tsleep()` | 7 | 1 (`PAUSE`) | `float()` cast (crashes on expressions) | None (bypassed) |
| `parse_tprejob()` | 3 | 0 | N/A | N/A |
| `parse_tpostjob()` | 3 | 0 | N/A | N/A |
| `parse_trunjob()` | ~30 | 5+ | String preservation | Expression-aware |
| `parse_tsendmail()` | ~40 | 8+ | String preservation | Expression-aware |
| `parse_base_component()` | ~80 | All generic | `isdigit()` for ints | Context variable detection |

`parse_tsleep()` is among the simplest parsers but is also one of the few with a crash bug due to premature type casting. Most other parsers preserve values as strings and let the engine handle conversion.

---

## Appendix O: Talend tSleep Usage Patterns

### Pattern 1: Simple Delay Between Subjobs

```
tFileInputDelimited_1 --> [OnSubjobOk] --> tSleep_1 --> [OnSubjobOk] --> tFileOutputDelimited_1
```

**Purpose**: Wait for external system to become ready, e.g., after writing a control file, wait 5 seconds for another process to pick it up.

**tSleep config**: `PAUSE=5` (5 seconds)

**V1 compatibility**: Works correctly when PAUSE is a literal integer.

### Pattern 2: Rate-Limited API Calls in Loop

```
tLoop_1 --> [Iterate] --> tSleep_1 --> [OnComponentOk] --> tREST_1
```

**Purpose**: Call an API N times with a delay between calls to avoid rate limiting.

**tSleep config**: `PAUSE=context.api_delay` (context variable)

**V1 compatibility**: FAILS -- converter crashes on context variable (CONV-SLP-001).

### Pattern 3: Variable Delay in Iterate

```
tFileList_1 --> [Iterate] --> tSleep_1 --> [OnComponentOk] --> tFileInputDelimited_1
```

**Purpose**: Process files one at a time with a configurable delay.

**tSleep config**: `PAUSE=(Integer)globalMap.get("tLoop_1_CURRENT_VALUE")` (globalMap expression)

**V1 compatibility**: FAILS -- converter crashes on Java expression (CONV-SLP-001).

### Pattern 4: Polling with Retry

```
tLoop_1 --> [Iterate] --> tSleep_1 --> [OnComponentOk] --> tFileExist_1 --> [Run If] --> tFileInputDelimited_1
```

**Purpose**: Poll for file existence every N seconds until it appears.

**tSleep config**: `PAUSE=context.poll_interval`

**V1 compatibility**: FAILS -- converter crashes (CONV-SLP-001). Even if fixed, the tLoop/tFileExist combination may not be fully supported in v1.

### Pattern 5: tSleep as Subjob Start

```
tSleep_1 --> [OnSubjobOk] --> tLogRow_1
```

**Purpose**: tSleep as the first component in a subjob, introducing a delay before the subjob starts processing.

**tSleep config**: `PAUSE=10`

**V1 compatibility**: Works correctly when PAUSE is a literal integer and tSleep has no input data (receives None).

### Pattern 6: tSleep with Data Pass-Through

```
tFileInputDelimited_1 --> [Main] --> tSleep_1 --> [Main] --> tFileOutputDelimited_1
```

**Purpose**: Introduce a delay in a data flow without modifying data.

**tSleep config**: `PAUSE=2`

**V1 compatibility**: Works correctly. Data passes through unchanged. Sleep occurs once in batch mode. **Caution**: If input data exceeds 3GB and execution_mode=HYBRID, streaming mode causes redundant sleep per chunk (PERF-SLP-001).

---

## Appendix P: Comparison with Python time.sleep() vs Java Thread.sleep()

| Aspect | Python `time.sleep()` | Java `Thread.sleep()` |
|--------|----------------------|----------------------|
| **Unit** | Seconds (float) | Milliseconds (long) |
| **Sub-second** | Yes (`time.sleep(0.001)` = 1ms) | Yes (`Thread.sleep(1)` = 1ms) |
| **Precision** | Platform-dependent; typically ~1-15ms on most OS | Platform-dependent; typically ~1-15ms on most OS |
| **Negative value** | Raises `ValueError` in Python 3.11+ | Throws `IllegalArgumentException` |
| **Zero value** | Returns immediately | Returns immediately (may yield CPU) |
| **Interrupt** | `KeyboardInterrupt` (not caught by `except Exception`) | `InterruptedException` (checked exception, must be caught) |
| **Thread behavior** | Blocks calling thread only | Blocks calling thread only |
| **Signal handling** | Can be interrupted by signals | Can be interrupted by `Thread.interrupt()` |
| **GIL interaction** | Releases GIL during sleep | N/A (no GIL in Java) |

**V1 behavioral note**: Python `time.sleep()` releases the GIL (Global Interpreter Lock) during sleep. This means other Python threads CAN execute during the sleep period. In a multi-threaded v1 engine, this is desirable -- sleeping in one thread does not block others. Java's `Thread.sleep()` similarly only blocks the calling thread.

**V1 version note**: Starting from Python 3.11, `time.sleep()` with a negative value raises `ValueError`. Earlier Python versions may behave differently. The v1 engine's `if pause_duration > 0` check prevents negative values from reaching `time.sleep()`, which is correct defensive coding.

---

## Appendix Q: SleepComponent Unit Test Template

The following test template covers all P0 and P1 test cases. Can be used as a starting point for TEST-SLP-001:

```python
"""
Unit tests for SleepComponent (tSleep equivalent)

Test file: tests/v1/unit/test_sleep_component.py
"""
import time
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from src.v1.engine.components.control.sleep import SleepComponent
from src.v1.engine.exceptions import ConfigurationError, ComponentExecutionError
from src.v1.engine.global_map import GlobalMap


class TestSleepComponentBasic:
    """P0: Basic functionality tests"""

    def test_basic_sleep_with_numeric_duration(self):
        """Verify sleep occurs for configured duration"""
        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": 0.01}
        )
        start = time.time()
        result = component._process()
        elapsed = time.time() - start
        assert elapsed >= 0.01
        assert 'main' in result

    def test_zero_duration_no_sleep(self):
        """Verify no sleep occurs for zero duration"""
        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": 0}
        )
        start = time.time()
        result = component._process()
        elapsed = time.time() - start
        assert elapsed < 0.1  # Should be near-instant
        assert 'main' in result

    def test_negative_duration_no_sleep(self):
        """Verify no sleep occurs for negative duration"""
        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": -5}
        )
        start = time.time()
        result = component._process()
        elapsed = time.time() - start
        assert elapsed < 0.1

    def test_passthrough_with_dataframe(self):
        """Verify input DataFrame is returned unchanged"""
        input_df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": 0}
        )
        result = component._process(input_df)
        assert result['main'] is input_df  # Same object reference

    def test_none_input_returns_empty_dataframe(self):
        """Verify None input produces empty DataFrame"""
        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": 0}
        )
        result = component._process(None)
        assert isinstance(result['main'], pd.DataFrame)
        assert result['main'].empty

    def test_statistics_tracking(self):
        """Verify NB_LINE, NB_LINE_OK, NB_LINE_REJECT after execution"""
        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": 0}
        )
        component._process()
        assert component.stats['NB_LINE'] == 1
        assert component.stats['NB_LINE_OK'] == 1
        assert component.stats['NB_LINE_REJECT'] == 0

    def test_globalmap_integration(self):
        """Verify stats are written to globalMap"""
        global_map = GlobalMap()
        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": 0},
            global_map=global_map
        )
        # NOTE: This test will fail until BUG-SLP-001 and BUG-SLP-002 are fixed
        # component.execute()
        # assert global_map.get("tSleep_1_NB_LINE") == 1


class TestSleepComponentP1:
    """P1: Important functionality tests"""

    def test_context_variable_resolution(self):
        """Verify ${context.delay} resolves correctly"""
        mock_ctx = MagicMock()
        mock_ctx.resolve_string.return_value = "0.01"
        mock_ctx.resolve_dict.return_value = {"pause_duration": "${context.delay}"}

        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": "${context.delay}"},
            context_manager=mock_ctx
        )
        result = component._process()
        assert 'main' in result

    def test_numeric_string_duration(self):
        """Verify string '2.5' converts to 2.5 float"""
        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": "0.01"}
        )
        duration = component._get_pause_duration()
        assert duration == 0.01

    def test_invalid_string_duration_defaults_to_zero(self):
        """Verify non-numeric string defaults to 0.0"""
        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": "not_a_number"}
        )
        duration = component._get_pause_duration()
        assert duration == 0.0

    def test_configuration_error_on_invalid_type(self):
        """Verify ConfigurationError raised for list type"""
        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": [1, 2, 3]}
        )
        with pytest.raises(ConfigurationError):
            component._process()

    def test_component_execution_error_wrapping(self):
        """Verify exceptions are wrapped in ComponentExecutionError"""
        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": 0.01}
        )
        with patch('time.sleep', side_effect=OSError("mock error")):
            with pytest.raises(ComponentExecutionError) as exc_info:
                component._process()
            assert "Sleep operation failed" in str(exc_info.value)

    def test_status_transitions(self):
        """Verify PENDING -> RUNNING -> SUCCESS status transitions"""
        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": 0}
        )
        from src.v1.engine.base_component import ComponentStatus
        assert component.status == ComponentStatus.PENDING
        # NOTE: Full status test requires execute() which needs BUG-SLP-001 fix

    def test_float_precision_subsecond(self):
        """Verify sub-second precision works"""
        component = SleepComponent(
            component_id="tSleep_1",
            config={"pause_duration": 0.001}
        )
        with patch('time.sleep') as mock_sleep:
            component._process()
            mock_sleep.assert_called_once_with(0.001)

    def test_empty_config_defaults_to_zero(self):
        """Verify missing pause_duration defaults to 0"""
        component = SleepComponent(
            component_id="tSleep_1",
            config={}
        )
        duration = component._get_pause_duration()
        assert duration == 0.0
```

**Notes on test template**:
- Tests use `_process()` directly instead of `execute()` to avoid BUG-SLP-001/002 crashes
- GlobalMap integration test is commented out until cross-cutting bugs are fixed
- `time.sleep()` is mocked in precision tests to avoid actual delays
- Context manager is mocked to isolate SleepComponent behavior

---

## Appendix R: Engine Registration Verification

### Import Chain

```
src/v1/engine/engine.py
    line 42: from .components.control import Warn, Die, SleepComponent

src/v1/engine/components/control/__init__.py
    line 3: from .sleep import SleepComponent
    line 7: __all__.append('SleepComponent')

src/v1/engine/components/control/sleep.py
    line 18: class SleepComponent(BaseComponent)
```

### Registry Entries

```python
# engine.py lines 177-178
'SleepComponent': SleepComponent,  # V1 class name
'tSleep': SleepComponent,          # Talend component name
```

Both registry entries point to the same class. This allows job configurations to use either the Talend name (`tSleep`) or the v1 name (`SleepComponent`) when specifying component types.

### Converter TYPE_MAP Entry

```python
# component_parser.py line 89
'tSleep': 'SleepComponent',
```

When the converter parses a Talend XML and encounters a `tSleep` node, it maps it to `SleepComponent` in the output JSON. The engine then looks up `SleepComponent` in its registry to instantiate the correct class.

---

## Appendix S: Detailed _validate_config() Analysis

### Method Source (lines 59-84)

```python
def _validate_config(self) -> List[str]:
    errors = []
    if 'pause_duration' in self.config:
        duration = self.config['pause_duration']
        if isinstance(duration, str):
            if not (duration.strip().startswith('${') and duration.strip().endswith('}')):
                try:
                    float(duration)
                except (ValueError, TypeError):
                    errors.append("Config 'pause_duration' must be a number, context variable, or numeric string")
            elif not isinstance(duration, (int, float)):
                errors.append("Config 'pause_duration' must be a number or context variable")
    return errors
```

### Logic Table

| Config Value | Type Check | Context Var Check | Float Parse | Result |
|-------------|------------|-------------------|-------------|--------|
| `5` | int -> passes isinstance(int, float) | N/A | N/A | VALID (no error) |
| `5.5` | float -> passes isinstance(int, float) | N/A | N/A | VALID |
| `"5"` | str -> enters string branch | Not `${...}` | `float("5")` succeeds | VALID |
| `"5.5"` | str | Not `${...}` | `float("5.5")` succeeds | VALID |
| `"${context.delay}"` | str | Starts with `${`, ends with `}` | Skipped | VALID (assumed context var) |
| `"abc"` | str | Not `${...}` | `float("abc")` fails | INVALID (error added) |
| `"{{java}}5+2"` | str | Not `${...}` | `float("{{java}}5+2")` fails | INVALID -- but this is a Java expression that should be valid! |
| `True` | bool -> isinstance(True, (int, float)) is True | N/A | N/A | VALID (unexpected but harmless) |
| `None` | NoneType -> fails isinstance check | N/A | N/A | Hmm... see below |
| `[1, 2]` | list -> fails isinstance check | N/A | N/A | INVALID (error added) |
| (missing key) | `'pause_duration' not in self.config` | N/A | N/A | VALID (key is optional) |

### Bug: `None` value handling

If `pause_duration` is explicitly set to `None`:
- `isinstance(None, str)` is False
- The `elif not isinstance(duration, (int, float))` on line 81 catches it
- Error message: "Config 'pause_duration' must be a number or context variable"

However, there is a subtle indentation issue in the original code. The `elif` on line 81 is at the same level as `if isinstance(duration, str)` (line 73), making it a sibling branch. This means it correctly handles non-string, non-numeric types.

### Bug: `{{java}}` expression validation

When Java expressions have been marked but not yet resolved (e.g., `"{{java}}context.delay + 5"`), the validation sees a string that:
1. Does not start with `${` -> not a context variable
2. `float("{{java}}context.delay + 5")` fails -> error added

This means `_validate_config()` will REJECT valid Java expressions. However, in practice this is not a problem because:
- `_resolve_java_expressions()` runs BEFORE `_process()` in `execute()` (step 3 in lifecycle)
- By the time `_validate_config()` runs (inside `_process()`), the `{{java}}` marker should already be resolved to a numeric value
- If the Java bridge is not available, the `{{java}}` marker remains, and `_validate_config()` correctly rejects it

This is actually CORRECT behavior -- if a Java expression cannot be resolved, it should be treated as an invalid configuration.

---

## Appendix T: Comparison with tSleep in Other ETL Tools

| Feature | Talend tSleep | Informatica SleepTask | SSIS SQL Wait | V1 SleepComponent |
|---------|---------------|----------------------|---------------|---------------------|
| Unit | Seconds (UI) / ms (code) | Seconds | Seconds | Seconds (float) |
| Sub-second | No (integer only) | No | No | Yes (float support) |
| Expression support | Yes (Java expressions) | Yes (parameter expressions) | Yes (SSIS expressions) | Partial (context vars yes, Java expressions blocked by converter bug) |
| Pass-through data | Yes | N/A (control flow) | N/A (control flow) | Yes |
| Die on error | Implicit (InterruptedException) | Yes | Yes | No |
| GlobalMap / Variables | ERROR_MESSAGE only | Task-level variables | Package variables | NB_LINE/NB_LINE_OK/NB_LINE_REJECT (incorrect for orchestration) |
| Thread blocking | Yes (current thread) | Yes (current thread) | Yes (current thread) | Yes (current thread) |
| Max duration | Limited by Java long | Configurable | No limit | No limit (Python float max) |

---

## Appendix U: Risk Assessment for Production Deployment

### Low Risk (Can deploy now)

| Scenario | Risk | Mitigation |
|----------|------|------------|
| tSleep with literal integer PAUSE | Low | Works correctly. Converter handles `float("5")` fine. |
| tSleep with no input data (trigger-only) | Low | `input_data=None` -> returns empty DataFrame. Works. |
| tSleep in simple subjob chain | Low | OnSubjobOk trigger works. Sleep occurs. |

### Medium Risk (Deploy with caution)

| Scenario | Risk | Mitigation |
|----------|------|------------|
| tSleep with globalMap enabled | Medium | BUG-SLP-001 will crash after successful sleep. Stats ARE written to globalMap before crash. Downstream may work but status will be ERROR. Fix BUG-SLP-001 before deploying. |
| tSleep in data flow (Main connection) | Medium | Data passes through but PERF-SLP-001 could cause redundant sleep in streaming mode. Unlikely to hit 3GB threshold for typical tSleep usage. |

### High Risk (Do not deploy without fix)

| Scenario | Risk | Mitigation |
|----------|------|------------|
| tSleep with context variable PAUSE | High | Converter crashes entirely (CONV-SLP-001). Job cannot be converted. Must fix converter before deploying. |
| tSleep with Java expression PAUSE | High | Same converter crash. Cannot convert. |
| tSleep in iterate loop with variable delay | High | Most common advanced pattern. Converter crash blocks all such jobs. |
| Any component with globalMap | High | BUG-SLP-001/002 are cross-cutting. ALL components crash when globalMap is enabled. |
