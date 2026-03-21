# Audit Report: tWarn / Warn

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tWarn` |
| **V1 Engine Class** | `Warn` |
| **Engine File** | `src/v1/engine/components/control/warn.py` (215 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (lines 252-258) |
| **Converter Dispatch** | `src/converters/complex_converter/component_parser.py` -> dedicated `elif component_type == 'tWarn'` branch within `_map_component_parameters()` |
| **Registry Aliases** | `Warn`, `tWarn` (registered in `src/v1/engine/engine.py` lines 173-174) |
| **Category** | Control / Logs & Errors |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/control/warn.py` | Engine implementation (215 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 252-258) | Parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/component_parser.py` (line 84) | Component type mapping: `'tWarn': 'Warn'` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE`, `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY` |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ConfigurationError`, `ComponentExecutionError`) |
| `src/v1/engine/components/control/__init__.py` | Package exports: `from .warn import Warn` |
| `src/v1/engine/components/control/die.py` | Sibling component `Die` (tDie) for comparison -- same architecture, terminates instead of continuing |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 1 | 2 | 0 | 3 of 3 core Talend params extracted (100% of documented properties); but MESSAGE expression handling incomplete; no tStatCatcher |
| Engine Feature Parity | **Y** | 1 | 3 | 2 | 1 | Core warn-and-continue works; missing globalMap variable name mismatch; narrow globalMap regex; no tLogCatcher integration; cross-cutting base class bugs |
| Code Quality | **Y** | 2 | 2 | 2 | 1 | Cross-cutting `_update_global_map()` and `GlobalMap.get()` bugs; `_validate_config()` dead code; narrow globalMap regex pattern |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | Pass-through component with negligible overhead; regex recompilation on every call |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tWarn Does

`tWarn` triggers a warning message that is typically caught by the `tLogCatcher` component for exhaustive logging. It provides a priority-rated message to the next component in the flow and -- critically -- does **not** stop job execution. This is the key difference from `tDie`, which terminates the job. `tWarn` is used for non-blocking notifications: signaling completion of a subjob, flagging data quality issues that need attention but are not fatal, or inserting audit trail entries into log pipelines.

The component acts as a **pass-through**: any input rows are forwarded unchanged to the output. The warning is a side-effect of the data flowing through the component, not a transformation of the data itself. When used with `tLogCatcher`, the warning message, code, and priority are captured as structured log records with fields for `moment`, `pid`, `project`, `job`, `context`, `priority`, `type`, `origin`, `message`, and `code`.

**Source**: [tWarn (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/twarn), [tWarn Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/logs-and-errors/twarn-standard-properties), [Using tDie, tWarn, and tLogCatcher for error handling (Talend 8.0)](https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-07/using-tdie-twarn-and-tlogcatcher-for-error-handling), [Configuring the Job for catching messages triggered by tWarn (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/twarn-tlogcatcher-tlogrow-trowgenerator-configuring-job-for-catching-messages-triggered-by-twarn-component-standard-component)

**Component family**: Logs & Errors (Control)
**Available in**: All Talend products (Standard Job framework)
**Required JARs**: None (no external library dependencies)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Warn Message | `MESSAGE` | Expression (String) | `""` | Warning message text to log. Supports context variables (`context.var`), globalMap references (`((String)globalMap.get("key"))`), and Java expressions. Free-form text that can include runtime-evaluated expressions. |
| 2 | Code | `CODE` | Integer | `0` | Numeric code level associated with the warning. Used for programmatic filtering in tLogCatcher. Can be any integer. Passed through to the `code` field in tLogCatcher output. |
| 3 | Priority | `PRIORITY` | Dropdown (Integer) | `4` (Warn) | Priority level for the warning message. Maps to Log4J-style levels. Available values: **1** = Trace, **2** = Debug, **3** = Info, **4** = Warn, **5** = Error, **6** = Fatal. Determines severity classification in tLogCatcher and log output. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 4 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used in production jobs. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Input data rows. Component acts as pass-through -- all input rows are forwarded unchanged to the output. |
| `FLOW` (Main) | Output | Row > Main | Same rows as input, passed through unchanged. The warning is a side-effect, not a transformation. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

**Usage restriction**: tWarn **cannot** be used as a start component. If an output component is connected to it, an input component must precede it. This means tWarn always requires a preceding component in the flow (it can be triggered via On Component OK / On Subjob OK triggers from a start component, or can receive data rows via a Row connection).

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_WARN_MESSAGES` | String | After execution | Returns the warning message text as a string. Accessible via `((String)globalMap.get("{id}_WARN_MESSAGES"))` in downstream components. |
| `{id}_WARN_CODE` | Integer | After execution | Returns the code level as an integer. |
| `{id}_WARN_PRIORITY` | Integer | After execution | Returns the priority level as an integer. |
| `{id}_ERROR_MESSAGE` | String | On error | Returns error messages if they occur. Only functions when "Die on error" is unchecked. |

**Note on variable naming**: Talend documentation specifies `WARN_MESSAGES` (plural), `WARN_CODE`, and `WARN_PRIORITY` as the standard global variable suffixes for tWarn. These differ from the simpler `MESSAGE`, `CODE`, `PRIORITY` suffixes used by tDie, creating an asymmetry between the two sibling components.

### 3.5 Behavioral Notes

1. **Pass-through semantics**: tWarn does NOT modify, filter, or transform input rows. Every row that enters the component exits unchanged. The warning is purely a side-effect -- it logs the message and stores details in globalMap, but the data flow is unaffected. This makes tWarn safe to insert anywhere in a pipeline without changing data behavior.

2. **Difference from tDie**: Both tWarn and tDie accept message, code, and priority parameters. Both store results in globalMap. Both are caught by tLogCatcher. The critical difference is that tDie **terminates** the job by raising an exception (with optional JVM exit), while tWarn **continues** execution. tDie uses priority=5 (error) as default; tWarn uses priority=4 (warn) as default. tDie also has an `exit_code` parameter that tWarn lacks.

3. **tLogCatcher integration**: When tLogCatcher has "Catch tWarn" enabled, it captures warning messages in a structured schema with 12 fields: `moment`, `pid`, `root_pid`, `father_pid`, `project`, `job`, `context`, `priority`, `type`, `origin`, `message`, and `code`. The `type` field distinguishes tWarn messages from tDie messages and Java exceptions. The `origin` field contains the component name (e.g., `tWarn_1`).

4. **Priority as integer**: The priority parameter is stored and transmitted as an integer (1-6), not as a string like "INFO" or "WARN". The dropdown in Talend Studio shows human-readable labels but stores the numeric value. Log4J mapping: 1=TRACE, 2=DEBUG, 3=INFO, 4=WARN, 5=ERROR, 6=FATAL.

5. **Message expression evaluation**: The message field supports full Java expression syntax at runtime. Common patterns include:
   - Context variables: `"Processing file: " + context.filename`
   - GlobalMap references: `"Processed " + ((Integer)globalMap.get("tFileInputDelimited_1_NB_LINE")) + " rows"`
   - String concatenation: `"Step " + context.step_name + " completed with code " + context.result_code`
   - Cast variants: `((String)globalMap.get("key"))`, `((Integer)globalMap.get("key"))`, `((Long)globalMap.get("key"))`

6. **Execution count**: When tWarn receives multiple rows via a Row connection, the warning is triggered once (not per row). The component processes the entire input batch and logs a single warning. The pass-through of rows is independent of the warning emission.

7. **No schema requirement**: tWarn does not define or require a schema. It passes through whatever schema the input provides. There is no schema editor for this component.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter has a **dedicated `elif` branch** for `tWarn` in `_map_component_parameters()` (component_parser.py lines 252-258). This is better than the generic fallback approach used by some components, though the branch is minimal (3 parameters).

**Converter flow**:
1. `converter.py` calls `component_parser.parse_base_component(node)`
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict
3. Detects `component_type == 'tWarn'` in component type mapping (line 84), maps to `'Warn'`
4. Calls `_map_component_parameters('tWarn', config_raw)` which enters the dedicated `elif` branch (line 253)
5. Returns mapped config with renamed keys: `message`, `code`, `priority`

```python
# component_parser.py lines 252-258
# Warn mapping
elif component_type == 'tWarn':
    return {
        'message': config_raw.get('MESSAGE', 'Warning'),
        'code': int(config_raw.get('CODE', '0')) if str(config_raw.get('CODE', '0')).isdigit() else 0,
        'priority': int(config_raw.get('PRIORITY', '4')) if str(config_raw.get('PRIORITY', '4')).isdigit() else 4
    }
```

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `MESSAGE` | Yes | `message` | 255 | Default `'Warning'` is reasonable. Expression/context variables in the value are handled by the generic `elementParameter` loop, not by this mapping. |
| 2 | `CODE` | Yes | `code` | 256 | Converted to int via `.isdigit()` check. Default `0` matches Talend. Rejects negative values and expressions (see issue). |
| 3 | `PRIORITY` | Yes | `priority` | 257 | Converted to int via `.isdigit()` check. Default `4` matches Talend (Warn level). Rejects non-numeric expressions. |
| 4 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |

**Summary**: 3 of 3 core runtime parameters extracted (100%). Only `TSTATCATCHER_STATS` is missing, which is cosmetic/metadata and has no runtime impact for this component.

### 4.2 Schema Extraction

tWarn has **no schema** in Talend. It is a pass-through component that forwards whatever input schema it receives. The converter correctly does not attempt to extract a schema for this component.

### 4.3 Expression Handling

**Context variable handling** (component_parser.py generic loop):
- `context.var` references in MESSAGE are detected during the generic `elementParameter` iteration
- If not a Java expression, they are wrapped as `${context.var}` for ContextManager resolution
- If a Java expression, they are marked with `{{java}}` prefix for Java bridge resolution

**Java expression handling**:
- MESSAGE values containing Java operators, method calls, globalMap references, or string concatenation are detected by `detect_java_expression()` and prefixed with `{{java}}`
- The engine's `BaseComponent._resolve_java_expressions()` resolves these at runtime via the Java bridge
- Example: `"Processed " + ((Integer)globalMap.get("NB_LINE")) + " rows"` would be marked as `{{java}}` and resolved by the Java bridge

**Known limitations**:
- The `.isdigit()` check on CODE and PRIORITY (lines 256-257) rejects Java expressions and context variables. If CODE or PRIORITY contains `context.warn_code` or a Java expression, it falls through to the default value (0 or 4) instead of being passed for runtime resolution. This is acceptable for most jobs where CODE and PRIORITY are static integers, but fails for dynamic values.
- The MESSAGE default `'Warning'` differs from Talend's empty-string default, though this is a minor cosmetic difference.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-WRN-001 | **P1** | **CODE and PRIORITY expressions silently dropped**: The `.isdigit()` check on lines 256-257 means Java expressions like `context.warn_code` or `Integer.parseInt(context.code_str)` in CODE/PRIORITY fields are silently replaced with defaults (0 and 4). There is no warning logged. In Talend, these fields support full expression syntax. While most real-world jobs use static integers, dynamic code/priority values in parameterized jobs will produce wrong results. Should either pass through as string for runtime resolution or log a warning when non-integer values are encountered. |
| CONV-WRN-002 | **P2** | **MESSAGE default `'Warning'` differs from Talend default (empty string)**: Talend initializes the MESSAGE field as empty. The converter defaults to `'Warning'` (line 255). While this is a reasonable default for user experience, it creates a behavioral difference: a tWarn component with no explicit message in Talend produces an empty warning; the converter produces `"Warning"`. This may affect log parsing or monitoring that keys on specific message text. |
| CONV-WRN-003 | **P2** | **No validation of PRIORITY range during conversion**: The converter converts PRIORITY to an integer but does not check if it falls in the valid range [1-6]. A Talend job with `PRIORITY=99` would pass through as `99` and only be caught (silently corrected to 4) at engine runtime. Should validate during conversion and log a warning for out-of-range values. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Log warning message | **Yes** | High | `_log_warning_message()` line 188 | Maps priority to Python logging levels correctly |
| 2 | Pass-through input data | **Yes** | High | `_process()` line 158 | Returns input data unchanged |
| 3 | Priority mapping (1-6) | **Yes** | High | `PRIORITY_NAMES` dict line 57, `_log_warning_message()` line 188 | Correct mapping: 1=trace(debug), 2=debug, 3=info, 4=warn, 5=error, 6=fatal(critical) |
| 4 | Code parameter | **Yes** | High | `_process()` line 117 | Stored in globalMap and included in log message |
| 5 | Message variable resolution | **Partial** | Medium | `_resolve_message_variables()` line 164 | Context variables resolved; globalMap resolution limited to `((Integer)globalMap.get("key"))` pattern only (see ENG-WRN-002) |
| 6 | Store message in globalMap | **Partial** | Low | `_store_warning_in_globalmap()` line 208 | Stores as `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY` -- but Talend uses `{id}_WARN_MESSAGES`, `{id}_WARN_CODE`, `{id}_WARN_PRIORITY` (see ENG-WRN-001) |
| 7 | Continue execution (not die) | **Yes** | High | `_process()` returns normally | Does not raise exception on success, unlike Die component |
| 8 | Statistics tracking | **Yes** | High | `_update_stats()` line 149 | NB_LINE, NB_LINE_OK tracked; NB_LINE_REJECT always 0 (correct for pass-through) |
| 9 | Empty input handling | **Yes** | High | `_process()` line 152 | Handles None/empty input gracefully, logs warning with stats (1, 1, 0) |
| 10 | tLogCatcher integration | **No** | N/A | -- | No tLogCatcher component exists in v1 engine. Warning data is only available via globalMap and Python logging. |
| 11 | Expression evaluation in message | **Partial** | Medium | `_resolve_message_variables()` line 164 | Context variables (`${context.var}`) resolved. GlobalMap limited to one cast pattern. Java expressions handled by base class `_resolve_java_expressions()` before `_process()` is called. |
| 12 | `{id}_ERROR_MESSAGE` globalMap | **No** | N/A | -- | Not set on error. When an exception occurs in `_process()`, it is re-raised as `ComponentExecutionError` but the error message is not stored in globalMap. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-WRN-001 | **P1** | **GlobalMap variable names do not match Talend convention**: The engine stores warning details as `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY` (line 211-213), but Talend documentation specifies `{id}_WARN_MESSAGES` (plural), `{id}_WARN_CODE`, and `{id}_WARN_PRIORITY`. Downstream components or expressions referencing the Talend-standard variable names (e.g., `((String)globalMap.get("tWarn_1_WARN_MESSAGES"))`) will get null/None instead of the warning message. This is a silent data loss bug for any job that reads these variables downstream. |
| ENG-WRN-002 | **P1** | **GlobalMap variable resolution in messages only supports `((Integer)globalMap.get("key"))` pattern**: The regex pattern on line 177 is `r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'`. This only matches the `(Integer)` cast. Talend supports `(String)`, `(Long)`, `(Double)`, `(Float)`, `(Boolean)`, `(Object)`, and other cast types. A message containing `((String)globalMap.get("tWarn_1_WARN_MESSAGES"))` would NOT be resolved and would appear as literal text in the log output. The Die component (line 198) has the identical limitation. |
| ENG-WRN-003 | **P1** | **GlobalMap `.get()` method is broken (cross-cutting)**: `GlobalMap.get()` in `global_map.py` line 28 references an undefined `default` parameter: `return self._map.get(key, default)`. The method signature on line 26 is `def get(self, key: str) -> Optional[Any]` with no `default` parameter. This causes `NameError` on EVERY `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. This bug means `_resolve_message_variables()` will crash when it calls `self.global_map.get(key, 0)` on line 181 if ANY globalMap reference is present in the message. **This affects ALL components using globalMap.get().** |
| ENG-WRN-004 | **P2** | **No `(String)globalMap.get()` resolution for non-Integer casts**: The most common globalMap access pattern in Talend messages is `((String)globalMap.get("key"))` for string concatenation. This is completely unsupported by the regex. Only `((Integer)globalMap.get(...))` is matched. This means the majority of real-world globalMap references in warning messages will not be resolved. |
| ENG-WRN-005 | **P2** | **`_validate_config()` is dead code (cross-cutting pattern)**: The `_validate_config()` method (lines 59-96) is never called by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. This means invalid configurations (e.g., `priority='abc'`, `code='not_a_number'`) are not caught until runtime when `int()` conversion is attempted in `_process()`. While `_process()` has fallback logic for invalid values, the validation method's 38 lines are dead code. |
| ENG-WRN-006 | **P3** | **Priority 1 (trace) maps to `logger.debug()` with "TRACE:" prefix**: Python's `logging` module does not have a TRACE level. The engine maps priority=1 to `logger.debug(f"TRACE: {log_message}")` (line 194). This is a reasonable approximation but means trace-level messages are indistinguishable from debug-level messages in log level filtering. A custom TRACE level (e.g., `logging.addLevelName(5, "TRACE")`) would provide better fidelity. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | Talend Name | V1 Name | How V1 Sets It | Notes |
|----------|-------------|----------|-------------|---------|-----------------|-------|
| Warn message | Yes | **Yes (wrong name)** | `{id}_WARN_MESSAGES` | `{id}_MESSAGE` | `_store_warning_in_globalmap()` line 211 | **Name mismatch**: Talend uses `_WARN_MESSAGES` (plural), v1 uses `_MESSAGE` |
| Warn code | Yes | **Yes (wrong name)** | `{id}_WARN_CODE` | `{id}_CODE` | `_store_warning_in_globalmap()` line 212 | **Name mismatch**: Talend uses `_WARN_CODE`, v1 uses `_CODE` |
| Warn priority | Yes | **Yes (wrong name)** | `{id}_WARN_PRIORITY` | `{id}_PRIORITY` | `_store_warning_in_globalmap()` line 213 | **Name mismatch**: Talend uses `_WARN_PRIORITY`, v1 uses `_PRIORITY` |
| Error message | Yes | **No** | `{id}_ERROR_MESSAGE` | -- | -- | Not implemented |
| NB_LINE | Yes (via base) | **Yes** | `{id}_NB_LINE` | `{id}_NB_LINE` | `_update_stats()` -> `_update_global_map()` | Correct via base class mechanism |
| NB_LINE_OK | Yes (via base) | **Yes** | `{id}_NB_LINE_OK` | `{id}_NB_LINE_OK` | Same mechanism | Always equals NB_LINE (correct for pass-through) |
| NB_LINE_REJECT | Yes (via base) | **Yes** | `{id}_NB_LINE_REJECT` | `{id}_NB_LINE_REJECT` | Same mechanism | Always 0 (correct for pass-through) |
| Execution time | N/A (v1 only) | **Yes** | -- | `{id}_EXECUTION_TIME` | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-WRN-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the loop variable (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just Warn, since `_update_global_map()` is called by `execute()` (line 218) after every component execution. The Warn component will crash EVERY TIME it runs with a globalMap present. |
| BUG-WRN-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter does not exist in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects the Warn component's `_resolve_message_variables()` (line 181: `self.global_map.get(key, 0)`) and the base `_update_global_map()`. Any code path that calls `global_map.get()` will crash. |
| BUG-WRN-003 | **P1** | `src/v1/engine/components/control/warn.py:177` | **GlobalMap resolution regex only matches `(Integer)` cast**: The pattern `r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'` only matches `((Integer)globalMap.get("key"))`. It does NOT match: `((String)globalMap.get("key"))`, `((Long)globalMap.get("key"))`, `((Double)globalMap.get("key"))`, `((Object)globalMap.get("key"))`, or any other cast type. In real Talend jobs, `(String)` is the most common cast in message expressions. Unmatched references are left as literal text in the log output, producing messages like `"Processed ((String)globalMap.get("filename")) successfully"` instead of the resolved value. The Die component at `die.py:198` has the identical bug. |
| BUG-WRN-004 | **P1** | `src/v1/engine/components/control/warn.py:177` | **GlobalMap resolution regex only matches `\w+` keys (no dots or hyphens)**: The key pattern `(\w+)` only matches word characters `[a-zA-Z0-9_]`. Talend globalMap keys often contain dots (e.g., `row1.column1`) or component IDs with underscores (which work) but the pattern would fail for keys with special characters. The `\w+` restriction means keys like `"tFileInputDelimited_1.NB_LINE"` with dots would not be matched. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-WRN-001 | **P1** | **GlobalMap variable names do not match Talend convention**: Engine stores `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY` but Talend specifies `{id}_WARN_MESSAGES`, `{id}_WARN_CODE`, `{id}_WARN_PRIORITY`. This is not just a naming inconsistency -- it is a functional bug that breaks downstream variable access (see ENG-WRN-001). The Die component correctly uses `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY` without prefix, which is consistent with Talend's tDie behavior. The asymmetry exists in Talend itself (tDie uses `MESSAGE`, tWarn uses `WARN_MESSAGES`), but the v1 engine treats them identically. |
| NAME-WRN-002 | **P2** | **Class docstring says `NB_LINE_OK: Equal to NB_LINE (no rejection logic)` and `NB_LINE_REJECT: Always 0`**: These are accurate descriptions of pass-through behavior. No issue, just noting for clarity. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-WRN-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists (lines 59-96) and is well-implemented but is never called. Contract is technically met but functionally useless. Dead code. Same pattern as Die, FileInputDelimited, and other v1 components. |
| STD-WRN-002 | **P3** | "No `print()` statements" (STANDARDS.md) | No print statements in `warn.py`. Correct. |

### 6.4 Debug Artifacts

No debug artifacts found. The code is clean of generation comments, TODO markers, and temporary code.

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-WRN-001 | **P3** | **Message content logged without sanitization**: The resolved message is logged directly via `logger.warning()` / `logger.error()` / `logger.critical()`. If the message contains user-supplied data (from context variables or globalMap), it could include log injection content (newlines, control characters). Not a concern for Talend-converted jobs where context values come from trusted sources, but noted for defense-in-depth. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones, DEBUG for details, WARNING/ERROR/CRITICAL for priorities -- correct |
| Start/complete logging | `_process()` logs start (line 112) and complete (lines 150, 155) -- correct |
| Sensitive data | No sensitive data logged (message content is intentionally logged as that is the component's purpose) -- correct |
| No print statements | No `print()` calls -- correct |
| Priority-based logging | `_log_warning_message()` correctly maps Talend priority 1-6 to Python logging levels (debug, debug, info, warning, error, critical) -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError` and `ComponentExecutionError` from `exceptions.py` -- correct |
| Exception chaining | Uses `raise ComponentExecutionError(self.id, ..., e) from e` pattern on line 162 -- correct |
| No bare `except` | Main try/except catches `Exception` (line 160) -- correct |
| Error messages | Include component ID and error details -- correct |
| Graceful degradation | Invalid code/priority values silently default to 0/4 with warning log -- acceptable for a logging component |
| Pass-through on error | If the component itself errors, it raises `ComponentExecutionError`. This is appropriate since the component should not silently swallow its own errors. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()` has `Optional[pd.DataFrame]` -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]`, `List[str]` -- correct |
| Class attributes | `VALID_PRIORITIES` typed as list literal, `PRIORITY_NAMES` typed as dict literal -- acceptable |

### 6.9 Code Structure Comparison with Die

The Warn component closely mirrors the Die component (`die.py`), sharing the same architecture for message resolution, globalMap storage, and priority handling. Key structural differences:

| Aspect | Warn | Die |
|--------|------|-----|
| Terminates job | No (returns normally) | Yes (raises `ComponentExecutionError`) |
| Default priority | 4 (warn) | 5 (error) |
| Extra parameters | None | `exit_code` |
| Stats pattern | (rows, rows, 0) -- all OK | (rows, 0, rows) -- all rejected |
| GlobalMap extras | None | `JOB_ERROR_MESSAGE`, `JOB_EXIT_CODE`, `{id}_EXIT_CODE` |
| GlobalMap resolution | Inline method `_resolve_message_variables()` | Separate method `_resolve_global_map_variables()` |

**Note**: Both components have the same `((Integer)globalMap.get(...))` limitation in their regex patterns. A shared utility method would be better than duplicated code.

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-WRN-001 | **P3** | **Regex recompiled on every execution**: `_resolve_message_variables()` calls `re.sub(pattern, ...)` with a string pattern on line 184, which recompiles the regex on every invocation. For a component that may be called thousands of times in an iteration loop, this adds unnecessary overhead. Should use `re.compile()` at class level and reuse the compiled pattern. Impact is minimal since the regex is simple and Python caches recent compilations, but it violates best practices. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Pass-through pattern | Component returns the same DataFrame reference (`input_data` on line 158), not a copy. This is memory-efficient -- no duplication of large DataFrames. |
| Empty input handling | Returns `pd.DataFrame()` (empty) when no input, not None. Consistent with engine expectations. |
| GlobalMap storage | Stores only 3 small values (message string, code int, priority int) per execution. Negligible memory impact. |
| Streaming mode | Inherited from base class. For streaming mode, each chunk is passed through individually. Works correctly. |

### 7.2 Overhead Assessment

The Warn component is a near-zero-overhead pass-through. The only computational work is:
1. Config value extraction (dictionary lookups)
2. Message variable resolution (regex sub, only if globalMap references present)
3. Python logger call (one call per execution)
4. GlobalMap storage (three `.put()` calls)
5. Stats update (three additions)

For a typical execution, this adds less than 1ms of overhead regardless of input DataFrame size, since the data is passed through by reference without any row-level processing.

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `Warn` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found involving `Warn` |
| Converter unit tests | **No** | -- | No tests for `tWarn` parameter mapping in component_parser.py |

**Key finding**: The v1 engine has ZERO tests for this component. All 215 lines of v1 engine code are completely unverified. No test file exists anywhere in the `tests/` directory for this component.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic warning with defaults | P0 | Create Warn with default config (`{}`), execute with no input, verify: (a) no exception raised, (b) returns `{'main': empty_df}`, (c) stats are (1, 1, 0), (d) logger.warning called with "Warning" message |
| 2 | Pass-through with DataFrame | P0 | Create Warn, execute with 100-row DataFrame, verify: (a) output DataFrame is identical to input (same rows, columns, values), (b) stats are (100, 100, 0), (c) warning logged once (not 100 times) |
| 3 | GlobalMap variable storage | P0 | Create Warn with `message="test msg"`, `code=42`, `priority=3`, execute with globalMap, verify globalMap contains correct keys and values. **Must verify BOTH current v1 names (`{id}_MESSAGE`) AND expected Talend names (`{id}_WARN_MESSAGES`) to document the gap.** |
| 4 | Priority mapping to log levels | P0 | Execute Warn with each priority 1-6, verify the correct Python logging method is called: 1->debug, 2->debug, 3->info, 4->warning, 5->error, 6->critical |
| 5 | Does not terminate job | P0 | Execute Warn followed by another component in sequence, verify second component also executes (confirming Warn does not raise exception, unlike Die) |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 6 | Context variable resolution in message | P1 | Message `"Processing ${context.filename}"` with context `{'filename': 'data.csv'}`, verify resolved message is `"Processing data.csv"` |
| 7 | GlobalMap variable resolution in message | P1 | Message containing `((Integer)globalMap.get("count"))` with globalMap `{"count": 42}`, verify resolved message contains `"42"` |
| 8 | Invalid priority falls back to default | P1 | Config `priority='invalid'`, verify falls back to 4 (warn) with warning logged |
| 9 | Invalid code falls back to default | P1 | Config `code='abc'`, verify falls back to 0 with warning logged |
| 10 | Empty DataFrame input | P1 | Execute with `pd.DataFrame()` (empty), verify returns empty DataFrame, stats (1, 1, 0), warning logged |
| 11 | String code/priority converted to int | P1 | Config `code='42'`, `priority='3'`, verify converted to integers 42 and 3 |
| 12 | Out-of-range priority | P1 | Config `priority=99`, verify falls back to 4 (warn) with warning |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 13 | `(String)globalMap.get()` not resolved | P2 | Message containing `((String)globalMap.get("key"))`, verify it is NOT resolved (documents known limitation) |
| 14 | Multiple globalMap references in one message | P2 | Message with two `((Integer)globalMap.get(...))` references, verify both resolved |
| 15 | Message with no variables | P2 | Plain string message with no `${context}` or `globalMap` references, verify passed through unchanged |
| 16 | Converter parameter mapping | P2 | Unit test for `_map_component_parameters('tWarn', {...})` with various inputs, verify output dict structure |
| 17 | Converter with expression in CODE | P2 | `config_raw = {'CODE': 'context.code'}`, verify converter falls back to default 0 (documents limitation) |
| 18 | Streaming mode pass-through | P2 | Execute in streaming mode with chunked input, verify all chunks pass through correctly |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-WRN-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. Prevents Warn from completing execution in any real pipeline with globalMap. |
| BUG-WRN-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. Prevents message variable resolution and downstream variable access. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-WRN-001 | Testing | Zero v1 unit tests for the Warn component. All 215 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-WRN-001 | Converter | CODE and PRIORITY expressions silently dropped by `.isdigit()` check. Dynamic values from context variables or Java expressions fall back to defaults without warning. |
| ENG-WRN-001 | Engine | GlobalMap variable names do not match Talend convention: engine uses `{id}_MESSAGE` / `{id}_CODE` / `{id}_PRIORITY`, Talend specifies `{id}_WARN_MESSAGES` / `{id}_WARN_CODE` / `{id}_WARN_PRIORITY`. Downstream references to Talend-standard names return null. |
| ENG-WRN-002 | Engine | GlobalMap variable resolution only supports `((Integer)globalMap.get(...))` pattern. `(String)`, `(Long)`, `(Double)`, `(Object)` casts are not resolved. Most real-world globalMap references in messages use `(String)` cast. |
| ENG-WRN-003 | Engine (Cross-Cutting) | `GlobalMap.get()` is broken -- undefined `default` parameter causes `NameError`. Affects `_resolve_message_variables()` and all globalMap access. Same as BUG-WRN-002 but tracked separately for engine parity. |
| BUG-WRN-003 | Bug | GlobalMap regex only matches `(Integer)` cast -- most common `(String)` cast is silently ignored, leaving literal Java expression text in log messages. |
| BUG-WRN-004 | Bug | GlobalMap regex key pattern `\w+` does not match keys containing dots, which are common in Talend (e.g., `row1.column1`). |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-WRN-002 | Converter | MESSAGE default `'Warning'` differs from Talend default (empty string). Minor behavioral difference. |
| CONV-WRN-003 | Converter | No validation of PRIORITY range [1-6] during conversion. Out-of-range values pass through to engine. |
| ENG-WRN-004 | Engine | No `(String)globalMap.get()` resolution. The most common cast type in Talend message expressions is unsupported. |
| ENG-WRN-005 | Engine | `_validate_config()` is dead code -- 38 lines of validation logic that is never called. Cross-cutting pattern across all v1 components. |
| NAME-WRN-001 | Naming | GlobalMap variable name mismatch with Talend convention (tracked primarily under ENG-WRN-001 as functional bug). |
| STD-WRN-001 | Standards | `_validate_config()` exists but is never invoked. Dead validation code. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| ENG-WRN-006 | Engine | Priority 1 (trace) maps to `logger.debug()` since Python has no TRACE level. Minor fidelity gap. |
| PERF-WRN-001 | Performance | Regex recompiled on every execution instead of using `re.compile()` at class level. Negligible impact. |
| SEC-WRN-001 | Security | Message content logged without sanitization. Low risk for Talend-converted jobs. |
| STD-WRN-002 | Standards | No print statements -- correct. No issue. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 6 | 1 converter, 3 engine, 2 bugs |
| P2 | 6 | 2 converter, 2 engine, 1 naming, 1 standards |
| P3 | 4 | 1 engine, 1 performance, 1 security, 1 standards |
| **Total** | **19** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-WRN-001): Change `value` to `stat_value` on `base_component.py` line 304. The current line is:
   ```python
   logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} {stat_name}: {value}")
   ```
   Remove the trailing `{stat_name}: {value}` reference entirely since the three main stats are already included in the message. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-WRN-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26:
   ```python
   def get(self, key: str, default: Any = None) -> Optional[Any]:
       return self._map.get(key, default)
   ```
   **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-WRN-001): Implement at minimum the 5 P0 test cases listed in Section 8.2. These cover: default execution, pass-through behavior, globalMap storage, priority mapping, and non-termination verification. Without these, the component's core contract (warn but do not die) is unverified.

### Short-Term (Hardening)

4. **Fix globalMap variable names to match Talend convention** (ENG-WRN-001): In `_store_warning_in_globalmap()` (line 208-214), change:
   ```python
   self.global_map.put(f"{self.id}_MESSAGE", message)
   self.global_map.put(f"{self.id}_CODE", code)
   self.global_map.put(f"{self.id}_PRIORITY", priority)
   ```
   to:
   ```python
   self.global_map.put(f"{self.id}_WARN_MESSAGES", message)
   self.global_map.put(f"{self.id}_WARN_CODE", code)
   self.global_map.put(f"{self.id}_WARN_PRIORITY", priority)
   # Also set legacy names for backward compatibility
   self.global_map.put(f"{self.id}_MESSAGE", message)
   self.global_map.put(f"{self.id}_CODE", code)
   self.global_map.put(f"{self.id}_PRIORITY", priority)
   ```
   Setting both Talend-standard and legacy names ensures backward compatibility while fixing the Talend convention gap. **Impact**: Fixes downstream globalMap access for any job using standard Talend variable names. **Risk**: Low (additive change).

5. **Expand globalMap resolution regex to support all cast types** (ENG-WRN-002, BUG-WRN-003): Replace the narrow regex pattern on line 177 with a generic pattern that matches any Java cast:
   ```python
   pattern = r'\(\((\w+)\)globalMap\.get\("([^"]+)"\)\)'
   ```
   This matches `((String)globalMap.get("key"))`, `((Integer)globalMap.get("key"))`, `((Long)globalMap.get("key.with.dots"))`, etc. The key group should be `[^"]+` instead of `\w+` to support keys with dots and hyphens. Apply the same fix to `die.py:198` since it has the identical bug. Consider extracting the regex into a shared utility method in `base_component.py` to avoid code duplication between Warn and Die.

6. **Wire up `_validate_config()`** (ENG-WRN-005): Add a call to `_validate_config()` at the beginning of `_process()`:
   ```python
   errors = self._validate_config()
   if errors:
       logger.warning(f"[{self.id}] Configuration warnings: {errors}")
   ```
   For a logging component, validation errors should be warnings (not exceptions) since invalid config should not prevent pass-through of data.

7. **Set `{id}_ERROR_MESSAGE` in globalMap on error**: In the except block of `_process()` (line 160-162), add:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
   ```

### Long-Term (Optimization)

8. **Pre-compile globalMap regex** (PERF-WRN-001): Move the regex compilation to a class-level constant:
   ```python
   _GLOBALMAP_PATTERN = re.compile(r'\(\((\w+)\)globalMap\.get\("([^"]+)"\)\)')
   ```
   Use `self._GLOBALMAP_PATTERN.sub(replace_func, message)` in `_resolve_message_variables()`.

9. **Add converter validation for PRIORITY range** (CONV-WRN-003): After converting PRIORITY to int in `_map_component_parameters()`, validate `1 <= priority <= 6` and log a warning for out-of-range values.

10. **Improve converter expression handling for CODE/PRIORITY** (CONV-WRN-001): Instead of silently defaulting non-numeric CODE/PRIORITY values, pass them through as strings and let the engine resolve them at runtime (via context manager or Java bridge). This enables dynamic code/priority values from parameterized jobs.

11. **Implement tLogCatcher** (future): The full tWarn/tDie/tLogCatcher triad is a common Talend error handling pattern. Without tLogCatcher, warning data is only available via globalMap and Python logging. Implementing tLogCatcher would enable structured log capture with the 12-field schema (moment, pid, root_pid, father_pid, project, job, context, priority, type, origin, message, code).

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 252-258
# Warn mapping
elif component_type == 'tWarn':
    return {
        'message': config_raw.get('MESSAGE', 'Warning'),
        'code': int(config_raw.get('CODE', '0')) if str(config_raw.get('CODE', '0')).isdigit() else 0,
        'priority': int(config_raw.get('PRIORITY', '4')) if str(config_raw.get('PRIORITY', '4')).isdigit() else 4
    }
```

**Notes on this code**:
- Line 255: Default `'Warning'` differs from Talend's empty default. This is a cosmetic difference.
- Line 256: `.isdigit()` rejects negative numbers and Java expressions. If CODE contains a context variable like `context.warn_code`, it silently falls to default 0.
- Line 257: Same `.isdigit()` limitation for PRIORITY. Dynamic priority values are silently replaced with default 4.
- The `str()` wrapping in `str(config_raw.get('CODE', '0')).isdigit()` correctly handles cases where the value is already an integer (not just string), preventing `AttributeError` on `int.isdigit()`.

---

## Appendix B: Engine Class Structure

```
Warn (BaseComponent)
    Constants:
        VALID_PRIORITIES = [1, 2, 3, 4, 5, 6]
        PRIORITY_NAMES = {1: 'trace', 2: 'debug', 3: 'info', 4: 'warn', 5: 'error', 6: 'fatal'}

    Methods:
        _validate_config() -> List[str]                    # DEAD CODE -- never called
        _process(input_data) -> Dict[str, Any]             # Main entry point: log warning, pass through data
        _resolve_message_variables(message) -> str          # Resolve ${context.var} and globalMap references
        _log_warning_message(message, code, priority)       # Map priority to Python logging level and log
        _store_warning_in_globalmap(message, code, priority) # Store warning details in globalMap
```

### Method Call Flow

```
BaseComponent.execute(input_data)
    |
    +-- _resolve_java_expressions()      # Resolve {{java}} markers in config (base class)
    +-- context_manager.resolve_dict()    # Resolve ${context.var} in config (base class)
    +-- _auto_select_mode(input_data)     # Determine batch vs streaming (base class)
    +-- _execute_batch(input_data)        # Delegates to _process() (base class)
    |       |
    |       +-- Warn._process(input_data)
    |               |
    |               +-- config.get('message', 'Warning')          # Extract config
    |               +-- config.get('code', 0)                     # Extract config
    |               +-- config.get('priority', 4)                 # Extract config
    |               +-- int(code), int(priority)                  # Convert with fallbacks
    |               +-- _resolve_message_variables(message)       # Resolve variables
    |               |       +-- context_manager.resolve_string()  # ${context.var}
    |               |       +-- re.sub(globalMap pattern)         # ((Integer)globalMap.get("key"))
    |               +-- _log_warning_message(msg, code, pri)      # Log at appropriate level
    |               +-- _store_warning_in_globalmap(msg, code, pri) # Store in globalMap
    |               +-- _update_stats(rows, rows, 0)              # Update NB_LINE stats
    |               +-- return {'main': input_data}               # Pass through unchanged
    |
    +-- _update_global_map()             # Store stats in globalMap (base class) [BUGGY: line 304]
    +-- return result with stats
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `MESSAGE` | `message` | Mapped | -- |
| `CODE` | `code` | Mapped | -- |
| `PRIORITY` | `priority` | Mapped | -- |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |

---

## Appendix D: Priority Level Mapping

### Talend Priority to V1 Python Logging

| Talend Priority | Talend Label | V1 Python Level | Python Method | Notes |
|-----------------|-------------|-----------------|---------------|-------|
| 1 | Trace | DEBUG (10) | `logger.debug(f"TRACE: {msg}")` | Python has no TRACE level; prefixed with "TRACE:" to distinguish from debug |
| 2 | Debug | DEBUG (10) | `logger.debug(msg)` | Direct mapping |
| 3 | Info | INFO (20) | `logger.info(msg)` | Direct mapping |
| 4 | Warn | WARNING (30) | `logger.warning(msg)` | Direct mapping; **default priority** |
| 5 | Error | ERROR (40) | `logger.error(msg)` | Direct mapping |
| 6 | Fatal | CRITICAL (50) | `logger.critical(msg)` | Python CRITICAL is closest to Java FATAL |

### Log4J to Python Level Mapping Accuracy

The mapping is correct for priorities 2-6. Priority 1 (Trace) has a minor fidelity gap because Python's standard `logging` module does not include a TRACE level. The v1 implementation uses DEBUG with a "TRACE:" prefix, which is a reasonable approximation but means:
- `logging.getLogger().setLevel(logging.DEBUG)` will show both trace and debug messages
- There is no way to filter trace messages independently of debug messages
- Log analysis tools that filter by level will treat trace and debug identically

A custom TRACE level could be added with `logging.addLevelName(5, "TRACE")` and `logger.log(5, msg)`, but this is a minor enhancement with limited practical impact.

---

## Appendix E: Detailed Code Analysis

### `_validate_config()` (Lines 59-96)

This method validates:
- `message` is a string (if present)
- `code` is an integer or integer-parseable string (if present)
- `priority` is an integer or integer-parseable string (if present)
- `priority` falls within `VALID_PRIORITIES` [1-6] (if present and is an integer)

**Not validated**: No required fields (all have defaults). The method is purely advisory.

**Critical**: This method is never called. Even if it were, it returns a list of error strings but no caller checks the list. The `_process()` method has its own inline validation with silent fallbacks (lines 121-134), making `_validate_config()` redundant.

### `_process()` (Lines 98-162)

The main processing method:
1. Extract config values with defaults: `message='Warning'`, `code=0`, `priority=4`
2. Convert `code` to int with fallback to 0 on ValueError/TypeError (lines 121-125)
3. Convert `priority` to int with validation against VALID_PRIORITIES, fallback to 4 (lines 127-134)
4. Resolve context and globalMap variables in message (line 137)
5. Log the warning at the appropriate Python level (line 140)
6. Store warning details in globalMap (line 143)
7. Update statistics: pass-through pattern (rows_in, rows_in, 0) or (1, 1, 0) for no input
8. Return `{'main': input_data}` -- pass through unchanged

The method is wrapped in a single try/except that catches all exceptions and re-raises as `ComponentExecutionError`. This is appropriate for a component that should not silently fail.

### `_resolve_message_variables()` (Lines 164-186)

Variable resolution in two phases:
1. **Context variables**: Delegates to `context_manager.resolve_string()` which handles `${context.var}` syntax
2. **GlobalMap variables**: Uses `re.sub()` with pattern `r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'`

**Limitations**:
- Only matches `(Integer)` cast, not `(String)`, `(Long)`, `(Double)`, etc.
- Key pattern `\w+` excludes dots, hyphens, and other special characters
- Default value for unresolved keys is hardcoded to `0` (line 181), which is wrong for string-typed variables
- No error handling for malformed globalMap references (e.g., missing closing parenthesis)

### `_log_warning_message()` (Lines 188-206)

Maps priority to Python logging level and logs with component ID and code:
- Priority 1 (trace): `logger.debug(f"TRACE: {msg}")`
- Priority 2 (debug): `logger.debug(msg)`
- Priority 3 (info): `logger.info(msg)`
- Priority 4 (warn): `logger.warning(msg)` -- default
- Priority 5 (error): `logger.error(msg)`
- Priority 6+ (fatal): `logger.critical(msg)`

Also logs a debug message with the priority name for traceability.

### `_store_warning_in_globalmap()` (Lines 208-214)

Stores three values in globalMap:
- `{self.id}_MESSAGE` -- resolved warning message text
- `{self.id}_CODE` -- warning code integer
- `{self.id}_PRIORITY` -- priority integer

**Issue**: Variable names do not match Talend convention (`WARN_MESSAGES`, `WARN_CODE`, `WARN_PRIORITY`). See ENG-WRN-001.

---

## Appendix F: Comparison with Die Component

Since Warn and Die are sibling components in the same `control` package, a detailed comparison highlights design consistency and gaps:

| Feature | Warn (`warn.py`) | Die (`die.py`) | Match? |
|---------|-------------------|----------------|--------|
| Lines of code | 215 | 206 | Similar |
| Base class | `BaseComponent` | `BaseComponent` | Yes |
| Config: message | `config.get('message', 'Warning')` | `config.get('message', 'Job execution stopped')` | Consistent pattern |
| Config: code | `config.get('code', 0)` | `config.get('code', 1)` | Different defaults (0 vs 1) -- matches Talend |
| Config: priority | `config.get('priority', 4)` | `config.get('priority', 5)` | Different defaults (warn vs error) -- matches Talend |
| Config: exit_code | N/A | `config.get('exit_code', 1)` | Die-only -- correct |
| Context resolution | `context_manager.resolve_string()` | `context_manager.resolve_string()` | Yes |
| GlobalMap resolution | Inline `_resolve_message_variables()` | Separate `_resolve_global_map_variables()` | **Inconsistent method organization** |
| GlobalMap regex | `r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'` | `r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'` | **Identical bug** -- only matches Integer |
| GlobalMap storage names | `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY` | `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY`, `{id}_EXIT_CODE` | **Warn uses wrong names** (should be `WARN_MESSAGES` etc.) |
| Job-level globalMap | None | `JOB_ERROR_MESSAGE`, `JOB_EXIT_CODE` | Die-only -- correct |
| Stats pattern | `(rows, rows, 0)` -- all pass through | `(rows, 0, rows)` -- all rejected | Correct for each |
| Terminates job | No (returns normally) | Yes (raises `ComponentExecutionError`) | Correct |
| Priority constants | Dict `PRIORITY_NAMES` + list `VALID_PRIORITIES` | Individual constants `PRIORITY_TRACE` through `PRIORITY_FATAL` | **Inconsistent constant style** |
| `_validate_config()` | Present, never called | Present, never called | **Both dead code** |

**Recommendation**: Extract shared logic (message resolution, globalMap storage, priority mapping) into a mixin or base method in `BaseComponent` to reduce duplication and ensure consistent bug fixes.

---

## Appendix G: GlobalMap Variable Resolution Deep Dive

### Current Implementation

The `_resolve_message_variables()` method on lines 164-186 performs variable resolution in two distinct phases:

**Phase 1: Context Variables**

```python
if self.context_manager:
    resolved_message = self.context_manager.resolve_string(resolved_message)
```

This delegates to the ContextManager's `resolve_string()` method, which handles the `${context.var}` syntax. The ContextManager performs a regex-based search-and-replace, finding all `${context.XXX}` patterns and substituting the corresponding context variable values. This works correctly for:
- Simple references: `${context.filename}` -> `"data.csv"`
- Nested in text: `"Processing ${context.filename} at ${context.timestamp}"` -> `"Processing data.csv at 2024-01-15"`
- Missing variables: `${context.undefined}` -> left as-is (no error raised)

The context resolution happens AFTER the base class `execute()` method has already called `context_manager.resolve_dict(self.config)` on line 202 of `base_component.py`. This means context variables in the `message` config field may already be resolved before `_process()` is called. However, the double resolution is harmless -- if the variable was already resolved, the pattern `${context.var}` will not be present and no substitution occurs. The second pass in `_resolve_message_variables()` acts as a safety net for any variables that were missed by the dict-level resolution.

**Phase 2: GlobalMap Variables**

```python
if self.global_map:
    pattern = r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'

    def replace_globalmap(match):
        key = match.group(1)
        value = self.global_map.get(key, 0)
        return str(value)

    resolved_message = re.sub(pattern, replace_globalmap, resolved_message)
```

This uses `re.sub()` with an inline replacement function. For each match of the `((Integer)globalMap.get("key"))` pattern, it:
1. Extracts the key name from the capture group
2. Calls `self.global_map.get(key, 0)` to retrieve the value (BUG: will crash -- see BUG-WRN-002)
3. Converts the value to string via `str(value)`
4. Returns the string as the replacement

### What Talend Actually Supports

In Talend, the message field is a Java expression that is evaluated at runtime by the JVM. This means ANY valid Java expression can appear in the message, including:

**Cast patterns** (all missing except Integer in v1):
- `((String)globalMap.get("tWarn_1_WARN_MESSAGES"))` -- String cast
- `((Integer)globalMap.get("tFileInputDelimited_1_NB_LINE"))` -- Integer cast (ONLY one supported)
- `((Long)globalMap.get("tFileInputDelimited_1_NB_LINE"))` -- Long cast
- `((Double)globalMap.get("tMap_1_NB_LINE"))` -- Double cast
- `((Float)globalMap.get("some_float_var"))` -- Float cast
- `((Boolean)globalMap.get("some_flag"))` -- Boolean cast
- `((Object)globalMap.get("generic_var"))` -- Object cast (returns Object, toString() used implicitly)
- `((java.math.BigDecimal)globalMap.get("amount"))` -- BigDecimal cast with full package path
- `((java.util.Date)globalMap.get("start_time"))` -- Date cast with full package path

**String concatenation**:
- `"Processed " + ((Integer)globalMap.get("count")) + " rows"`
- `"File: " + context.filename + " completed"`
- `"Step " + String.valueOf(context.step_number)`

**Method calls on globalMap values**:
- `((String)globalMap.get("message")).toUpperCase()`
- `((String)globalMap.get("path")).replace("\\", "/")`
- `String.valueOf(((Integer)globalMap.get("count")))`

**Ternary expressions**:
- `((Integer)globalMap.get("count")) > 0 ? "Success" : "Empty"`

**Talend routine calls**:
- `TalendDate.getCurrentDate()` in the message
- `StringHandling.UPCASE(context.status)`

The v1 engine's regex approach can only handle the simplest case: a standalone `((Integer)globalMap.get("simple_key"))` pattern with no surrounding Java syntax, no method chaining, and no non-word characters in the key. For all other cases, the Java bridge (via `_resolve_java_expressions()` in the base class) would need to handle the entire message as a Java expression.

### Resolution Order and Interaction

The full resolution chain for a tWarn message in the v1 engine is:

1. **Java expression resolution** (base class `execute()` line 198): If the MESSAGE config value starts with `{{java}}`, the ENTIRE value is sent to the Java bridge for evaluation. This handles ALL Java expression syntax correctly, including string concatenation, method calls, globalMap access, and routine calls. After resolution, the `{{java}}` prefix is removed and the config value is replaced with the Java bridge result.

2. **Context dict resolution** (base class `execute()` line 202): `context_manager.resolve_dict(self.config)` resolves all `${context.var}` patterns in all string values in the config dict.

3. **Message-specific context resolution** (`_resolve_message_variables()` line 172): A second pass of context variable resolution on the message string. Redundant if step 2 already resolved all variables, but harmless.

4. **Message-specific globalMap resolution** (`_resolve_message_variables()` line 176): Regex-based replacement of `((Integer)globalMap.get("key"))` patterns. Only runs if the message was NOT a `{{java}}` expression (since that would have been fully resolved in step 1).

**Key insight**: If the converter correctly marks complex message expressions as `{{java}}`, the Java bridge in step 1 handles them completely and correctly. The regex-based globalMap resolution in step 4 is only needed for simple cases where the message contains a bare globalMap reference that was NOT marked as a Java expression. This is a narrow use case in practice -- most messages with globalMap references also contain string concatenation operators, which would trigger the `detect_java_expression()` heuristic in the converter and result in `{{java}}` marking.

**Gap**: If the Java bridge is not available (no `java_bridge` set on the component), step 1 is skipped, and the regex in step 4 is the only fallback. In this case, the narrow regex is a significant limitation.

### Recommended Fix

Replace the narrow regex with a generic pattern that handles all cast types and key formats:

```python
# Current (buggy):
pattern = r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'

# Recommended fix:
pattern = r'\(\(([A-Za-z._]+)\)globalMap\.get\("([^"]+)"\)\)'
```

The improved pattern:
- Captures the cast type as group 1 (allows dots for package paths like `java.math.BigDecimal`)
- Captures the key as group 2 (allows any character except double-quote)
- Handles all standard Talend cast patterns

The replacement function should also handle the default value more intelligently:

```python
def replace_globalmap(match):
    cast_type = match.group(1)
    key = match.group(2)
    value = self.global_map.get(key)
    if value is None:
        # Default based on cast type
        if cast_type in ('Integer', 'Long', 'Short', 'Byte'):
            return '0'
        elif cast_type in ('Float', 'Double', 'java.math.BigDecimal'):
            return '0.0'
        elif cast_type == 'Boolean':
            return 'false'
        else:
            return ''  # String and Object default to empty string
    return str(value)
```

---

## Appendix H: Base Class Interaction Analysis

### `BaseComponent.execute()` Lifecycle (Lines 188-234)

The Warn component inherits the full `execute()` lifecycle from `BaseComponent`. Understanding this lifecycle is critical for identifying where bugs and limitations affect the Warn component specifically.

**Step-by-step execution flow**:

```
execute(input_data)                            # base_component.py line 188
  |
  +-- self.status = ComponentStatus.RUNNING    # line 192
  +-- start_time = time.time()                 # line 193
  |
  +-- Step 1: Java expression resolution       # lines 196-198
  |   if self.java_bridge:
  |       self._resolve_java_expressions()
  |   - Scans self.config recursively for {{java}} prefixed values
  |   - Collects all Java expressions
  |   - Syncs context variables to Java bridge
  |   - Syncs globalMap variables to Java bridge
  |   - Executes all expressions in batch via Java bridge
  |   - Replaces config values with resolved results
  |   - For Warn: resolves MESSAGE, CODE, PRIORITY if marked as {{java}}
  |
  +-- Step 2: Context variable resolution      # lines 200-202
  |   if self.context_manager:
  |       self.config = self.context_manager.resolve_dict(self.config)
  |   - Resolves ${context.var} patterns in ALL config string values
  |   - For Warn: resolves ${context.var} in message, code, priority
  |   - NOTE: Replaces self.config entirely with a new dict
  |
  +-- Step 3: Execution mode selection         # lines 204-208
  |   if self.execution_mode == ExecutionMode.HYBRID:
  |       mode = self._auto_select_mode(input_data)
  |   - Checks input_data memory usage against MEMORY_THRESHOLD_MB (3072 MB)
  |   - For Warn: almost always BATCH (pass-through has negligible memory impact)
  |
  +-- Step 4: Execute component                # lines 210-214
  |   if mode == ExecutionMode.STREAMING:
  |       result = self._execute_streaming(input_data)
  |   else:
  |       result = self._execute_batch(input_data)
  |   - _execute_batch() simply calls self._process(input_data)
  |   - _execute_streaming() chunks the DataFrame and calls _process() per chunk
  |   - For Warn: _process() logs warning and returns {'main': input_data}
  |
  +-- Step 5: Update statistics                # lines 216-218
  |   self.stats['EXECUTION_TIME'] = time.time() - start_time
  |   self._update_global_map()
  |   >>> BUG: _update_global_map() line 304 references undefined 'value'
  |   >>> This will crash with NameError for ALL components
  |
  +-- Step 6: Set success status               # line 220
  |   self.status = ComponentStatus.SUCCESS
  |
  +-- Step 7: Add stats to result              # lines 222-223
  |   result['stats'] = self.stats.copy()
  |
  +-- return result                            # line 225
```

**Error handling path** (lines 227-234):
```
  except Exception as e:
      self.status = ComponentStatus.ERROR
      self.error_message = str(e)
      self.stats['EXECUTION_TIME'] = time.time() - start_time
      self._update_global_map()    # Also calls the buggy method
      logger.error(f"Component {self.id} execution failed: {e}")
      raise
```

**Key observations for Warn**:
1. The `_update_global_map()` bug on line 304 will cause `NameError` AFTER `_process()` completes successfully. This means the warning IS logged and stored in globalMap via `_store_warning_in_globalmap()`, but then the base class crashes when trying to log the statistics. The result is that the Warn component appears to fail even though its core logic succeeded.
2. The error handling path ALSO calls `_update_global_map()`, which will cause a secondary `NameError`. This means any exception from Warn (including the bug above) will trigger another crash in the error handler, potentially masking the original error.
3. Context resolution (step 2) happens BEFORE `_process()`, so `${context.var}` patterns in the message config are already resolved by the time `_resolve_message_variables()` runs. The second resolution pass in `_resolve_message_variables()` is redundant for context variables but provides a safety net.

### `BaseComponent._update_global_map()` (Lines 298-304)

```python
def _update_global_map(self) -> None:
    """Update global map with component statistics"""
    if self.global_map:
        for stat_name, stat_value in self.stats.items():
            self.global_map.put_component_stat(self.id, stat_name, stat_value)
        # Log the statistics for debugging
        logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} {stat_name}: {value}")
```

**Bug analysis**: Line 304 references `{value}` which is undefined. The loop variable on line 301 is `stat_value`, not `value`. At the time line 304 executes, the loop has finished so `stat_name` holds the last key from `self.stats.items()` (which is `'EXECUTION_TIME'`), but `value` does not exist in any scope.

**Fix options**:
1. Change `{value}` to `{stat_value}` -- but `stat_name` at this point is stale (last loop iteration value)
2. Remove the `{stat_name}: {value}` portion entirely since the three main stats are already explicitly logged
3. Move the log statement inside the loop (but this would log for every stat, which is verbose)

**Recommended fix**: Remove the trailing `{stat_name}: {value}` reference:
```python
logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']}")
```

### `BaseComponent._update_stats()` (Lines 306-312)

```python
def _update_stats(self, rows_read:int=0, rows_ok:int=0, rows_reject:int=0) -> None:
    """Helper to update statistics """
    self.stats['NB_LINE'] += rows_read
    self.stats['NB_LINE_OK'] += rows_ok
    self.stats['NB_LINE_REJECT'] += rows_reject
    logger.debug(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']}")
```

This method works correctly. The Warn component calls it with `(rows_in, rows_out, 0)` for pass-through behavior, which is correct. The `+=` accumulation pattern supports streaming mode where `_process()` may be called multiple times for chunks.

**Warn-specific behavior**:
- With input data: `_update_stats(len(input_data), len(input_data), 0)` -- all rows pass through
- Without input data: `_update_stats(1, 1, 0)` -- counts the warning operation itself as one "row"

The "1 row for no input" pattern matches the Talend behavior where tWarn is counted as processing one event even when there are no data rows flowing through it.

### `GlobalMap.get()` Bug (global_map.py Lines 26-28)

```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

**Bug analysis**: The method signature declares only one parameter `key`, but the body references `default` which is not defined. This causes `NameError: name 'default' is not defined` on EVERY call to `GlobalMap.get()`.

**Impact on Warn component**:
1. `_resolve_message_variables()` line 181: `self.global_map.get(key, 0)` -- calls `get()` with two arguments. Even if the signature accepted two arguments, the `get()` method only takes one. This would raise `TypeError: get() takes 2 positional arguments but 3 were given`.
2. `_store_warning_in_globalmap()` uses `self.global_map.put()` which works correctly (no bug in `put()`).
3. The base class `_update_global_map()` uses `self.global_map.put_component_stat()` which calls `self.put()` internally. The `put()` method works correctly.

**Double failure mode**: If a message contains a globalMap reference, `_resolve_message_variables()` will crash with `TypeError` (too many arguments to `get()`). Even without globalMap references in the message, `_update_global_map()` will crash with `NameError` (undefined `value` variable in the log statement).

**Fix**:
```python
def get(self, key: str, default: Any = None) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

### `GlobalMap.get_component_stat()` Bug (global_map.py Lines 51-58)

```python
def get_component_stat(self, component_id: str, stat_name: str, default: int = 0) -> int:
    if component_id in self._component_stats:
        return self._component_stats[component_id].get(stat_name, default)
    key = f"{component_id}_{stat_name}"
    return self.get(key, default)
```

Line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one (the `key` parameter). This would raise `TypeError`. This method is called by convenience methods like `get_nb_line()`, `get_nb_line_ok()`, and `get_nb_line_reject()`.

**Impact on Warn**: The Warn component does not directly call `get_component_stat()`, but downstream components or the engine may call it to read Warn's statistics. The fix for `GlobalMap.get()` (adding `default` parameter) also fixes this issue.

---

## Appendix I: Context Manager Integration

### How Context Variables Reach the Warn Component

Context variables flow through the system in a three-stage pipeline:

**Stage 1: Context loading** -- The engine loads context variables from a context file (e.g., `context.properties`) or command-line arguments via the `ContextManager`. Variables are stored as key-value pairs: `{'filename': 'data.csv', 'env': 'prod', 'batch_id': '12345'}`.

**Stage 2: Config resolution** -- When `execute()` calls `self.context_manager.resolve_dict(self.config)` (line 202), ALL string values in the config dict are scanned for `${context.XXX}` patterns. For the Warn component, this resolves patterns in:
- `config['message']` -- e.g., `"Processing ${context.filename}"` becomes `"Processing data.csv"`
- `config['code']` -- unlikely to contain context variables, but possible
- `config['priority']` -- unlikely to contain context variables, but possible

**Stage 3: Message-level resolution** -- `_resolve_message_variables()` performs a second pass of context resolution on the message string via `self.context_manager.resolve_string(resolved_message)`. This is redundant with Stage 2 for the `message` config field but provides a safety net.

### Context Variable Patterns in tWarn Messages

Common patterns seen in real Talend jobs:

| Pattern | Example | Resolved Value |
|---------|---------|----------------|
| Simple reference | `"Processing ${context.filename}"` | `"Processing data.csv"` |
| Multiple references | `"Job ${context.job_name} in ${context.env}"` | `"Job ETL_001 in prod"` |
| Nested in path | `"Error in ${context.input_dir}/${context.filename}"` | `"Error in /data/input/data.csv"` |
| With globalMap | `"${context.step} processed ((Integer)globalMap.get(\"count\")) rows"` | Partially resolved -- context part resolved, globalMap part requires separate resolution |
| In code field | `${context.error_code}` | Resolved to string, then `int()` conversion in `_process()` |

### Edge Cases

1. **Undefined context variable**: If `${context.undefined_var}` is in the message and the context does not contain `undefined_var`, the ContextManager leaves the pattern as-is. The literal text `${context.undefined_var}` appears in the log output. No error is raised. This matches Talend behavior where undefined context variables result in empty strings or null.

2. **Context variable with special characters**: If a context variable value contains regex metacharacters (e.g., `context.path = "C:\Users\data"`), the ContextManager's `resolve_string()` handles this correctly because it uses string replacement, not regex substitution. However, if the resolved value contains `${context.another_var}`, there is a risk of recursive resolution. The ContextManager should (and likely does) perform only one pass of resolution.

3. **Context variable in CODE/PRIORITY fields**: If `config['code'] = '${context.warn_code}'` and `context.warn_code = '42'`, the context resolution in Stage 2 resolves it to `'42'`. Then `_process()` calls `int(code)` on line 121, which succeeds. However, if the converter's `.isdigit()` check (line 256) already rejected the expression and defaulted to `0`, the context variable is lost. This depends on whether the converter runs BEFORE or AFTER context resolution -- since the converter runs at conversion time (not runtime), context variables are NOT resolved during conversion. Therefore, the converter sees `'${context.warn_code}'`, `.isdigit()` returns False, and the value defaults to `0`. **The context variable is silently lost.** This is a real bug for parameterized jobs.

---

## Appendix J: Pass-Through Behavior Analysis

### Definition of Pass-Through

The Warn component implements a strict pass-through pattern: the input DataFrame is returned as the output DataFrame without any modification. This means:

1. **Same object reference**: `_process()` returns `{'main': input_data}` (line 158), passing the same Python object reference. No copy is made. This is memory-efficient but means any downstream mutation of the DataFrame would also affect the "original" input.

2. **No column changes**: The output has exactly the same columns as the input, in the same order.

3. **No row changes**: No rows are added, removed, or reordered. The output row count equals the input row count.

4. **No value changes**: No cell values are modified. No type conversions, no NaN filling, no trimming.

5. **No schema enforcement**: Unlike FileInputDelimited which calls `validate_schema()`, Warn does NOT validate or enforce any schema on the pass-through data. Whatever comes in goes out, regardless of types or constraints.

### Pass-Through in Talend vs V1

In Talend, tWarn is a true pass-through component. The generated Java code for tWarn simply copies input rows to the output flow while logging the warning message. The schema of the output flow is identical to the schema of the input flow.

The v1 implementation correctly replicates this behavior. However, there is a subtle difference in streaming mode:

**Batch mode**: Input DataFrame is returned by reference. Zero overhead.

**Streaming mode**: The base class `_execute_streaming()` (lines 255-278) processes input in chunks:
```python
for chunk in chunks:
    chunk_result = self._process(chunk)
    if chunk_result.get('main') is not None:
        results.append(chunk_result['main'])
combined = pd.concat(results, ignore_index=True)
return {'main': combined}
```

For each chunk, `_process()` returns the chunk unchanged. But then `pd.concat(results, ignore_index=True)` creates a NEW DataFrame from all chunks. This means:
- A new DataFrame object is created (memory allocation)
- `ignore_index=True` resets the index, losing any original index values
- The column dtypes may be inferred from the concatenation, potentially changing nullable types

This is generally not an issue for the Warn component since it is a logging component, but it is worth noting that streaming mode does NOT preserve the exact same object reference as batch mode.

### Statistics Accuracy

The Warn component's statistics tracking is straightforward for pass-through:

| Scenario | NB_LINE | NB_LINE_OK | NB_LINE_REJECT | Notes |
|----------|---------|------------|----------------|-------|
| 100-row input | 100 | 100 | 0 | All rows pass through |
| Empty DataFrame input | 1 | 1 | 0 | Counts warning operation as 1 |
| None input | 1 | 1 | 0 | Counts warning operation as 1 |
| 0-row non-empty input | 1 | 1 | 0 | `input_data.empty` is True for 0-row DF |

The "1 for no/empty input" pattern is consistent with Talend, where tWarn is counted as processing one event even when no data rows flow through. This is correct behavior.

### Comparison with Other Pass-Through Components

| Component | Pass-Through? | Modifies Data? | Returns Same Reference? |
|-----------|--------------|----------------|------------------------|
| Warn | Yes | No | Yes (batch) / No (streaming) |
| Die | N/A (terminates) | N/A | N/A |
| LogRow | Yes (with side-effect) | No | Depends on implementation |
| Replicate | Fan-out (1-to-N) | No | Returns copies |
| FilterRows | Partial pass-through | Removes rows | No (new filtered DF) |

Warn is the simplest pass-through component: no schema enforcement, no filtering, no copying, just forward the reference.

---

## Appendix K: tLogCatcher Integration Gap Analysis

### What tLogCatcher Does

In Talend, `tLogCatcher` is the counterpart to `tWarn` and `tDie`. It catches warnings, errors, and Java exceptions, producing a structured output schema with 12 fields:

| Field | Type | Description |
|-------|------|-------------|
| `moment` | Date | Timestamp when the message was captured |
| `pid` | String | Process ID of the Job |
| `root_pid` | String | Root process ID |
| `father_pid` | String | Father process ID |
| `project` | String | Project name |
| `job` | String | Job name |
| `context` | String | Context used to run the Job |
| `priority` | Integer | Message priority level (1-6) |
| `type` | String | Message type: `"tWarn"`, `"tDie"`, or `"Java Exception"` |
| `origin` | String | Name of the triggering component (e.g., `"tWarn_1"`) |
| `message` | String | Message content/text |
| `code` | Integer | Error code level |

The `tLogCatcher` component has three configurable catch options:
1. **Catch Java Exception**: Catches runtime Java exceptions
2. **Catch tDie**: Catches messages from tDie components
3. **Catch tWarn**: Catches messages from tWarn components

### Why This Matters for tWarn

In a typical Talend error handling pattern, the flow is:

```
[Data Processing Subjob]
    |
    +-- OnSubjobOK --> tWarn_1 ("Processing completed successfully")
    +-- OnSubjobError --> tDie_1 ("Processing failed: " + error)

[Error Handling Subjob]
    tLogCatcher_1 (Catch tWarn + Catch tDie)
        |
        +-- tLogRow_1 (display to console)
        +-- tFileOutputDelimited_1 (write to audit log file)
```

Without tLogCatcher in the v1 engine, the structured audit trail is lost. Warning messages are only available through:
1. Python logging output (unstructured text)
2. GlobalMap variables (`{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY`)

### V1 Engine Impact

The absence of tLogCatcher means:
- **No structured log capture**: The 12-field schema (moment, pid, project, job, context, priority, type, origin, message, code, root_pid, father_pid) cannot be produced
- **No log file output**: Warning messages cannot be routed to a dedicated audit log file via the standard Talend pattern
- **No distinction between tWarn and tDie messages**: Both produce similar globalMap entries, and without the `type` field from tLogCatcher, downstream logic cannot distinguish warnings from fatal errors
- **No process ID tracking**: The `pid`, `root_pid`, and `father_pid` fields are not available, which breaks audit trail lineage

**Workaround**: Jobs that use tLogCatcher can be partially replicated by:
1. Reading the globalMap variables `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY` after tWarn execution
2. Manually constructing a log record in a downstream Python component
3. Writing the log record to a file using tFileOutputDelimited

This workaround is fragile and does not support the automatic catching behavior of tLogCatcher (which captures ALL warnings and errors across the entire job, not just from specific components).

### Priority Ranking

Implementing tLogCatcher is a **P2** improvement for the v1 engine. While many jobs use tLogCatcher for audit logging, the core warning functionality works without it. Jobs that critically depend on tLogCatcher for error routing would need to be redesigned to use Python logging or manual globalMap reads.

---

## Appendix L: Converter Expression Edge Cases

### Expression Handling in Component Parser

The converter's `_map_component_parameters()` for tWarn (lines 252-258) handles three parameters. The expression handling for each has distinct behaviors:

**MESSAGE parameter** (line 255):
```python
'message': config_raw.get('MESSAGE', 'Warning')
```

The MESSAGE value from `config_raw` has already been processed by the generic `elementParameter` loop in `parse_base_component()`. During that loop:
- If the value contains `context.` and is NOT detected as a Java expression, it is wrapped as `${context.var}`
- If the value IS detected as a Java expression (contains `+`, method calls, `globalMap`, etc.), it is marked with `{{java}}` prefix
- The `_map_component_parameters()` simply passes through whatever the generic loop produced

**Example transformation chain for MESSAGE**:

| Talend XML Value | After Generic Loop | After `_map_component_parameters()` | After Engine Resolution |
|------------------|-------------------|------------------------------------|-----------------------|
| `"Simple warning"` | `"Simple warning"` | `"Simple warning"` | `"Simple warning"` |
| `context.warn_msg` | `"${context.warn_msg}"` | `"${context.warn_msg}"` | `"Production warning"` (if context.warn_msg = "Production warning") |
| `"Count: " + ((Integer)globalMap.get("count"))` | `"{{java}}\"Count: \" + ((Integer)globalMap.get(\"count\"))"` | `"{{java}}\"Count: \" + ((Integer)globalMap.get(\"count\"))"` | `"Count: 42"` (via Java bridge) |
| `((Integer)globalMap.get("count"))` | Depends on `detect_java_expression()` | May or may not be `{{java}}` marked | Resolved by Java bridge if marked, or by regex if not |

**CODE parameter** (line 256):
```python
'code': int(config_raw.get('CODE', '0')) if str(config_raw.get('CODE', '0')).isdigit() else 0
```

The `.isdigit()` check happens AFTER the generic loop. If the generic loop marked the value as `{{java}}` (e.g., `"{{java}}context.code + 1"`), the `str(...)` wrapping converts it to `"{{java}}context.code + 1"`, `.isdigit()` returns False, and the value defaults to `0`. The Java expression is lost.

If the generic loop resolved a simple context variable (e.g., `"${context.code}"` -> `"${context.code}"`), `.isdigit()` returns False (because `$` is not a digit), and the value defaults to `0`. The context variable is lost.

Only purely numeric values pass through: `"42"` -> `42`, `"0"` -> `0`, `"100"` -> `100`.

**PRIORITY parameter** (line 257):
Same behavior as CODE. Only purely numeric values pass through.

### Negative Number Handling

The `.isdigit()` check rejects negative numbers:
- `"-1"` -> `.isdigit()` returns False -> defaults to 0 (CODE) or 4 (PRIORITY)
- `"-1"` is not a valid Talend priority (range is 1-6), so this is acceptable for PRIORITY
- For CODE, negative values are valid in Talend but silently rejected by the converter

### Expression Detection False Positives

The converter's `detect_java_expression()` heuristic may mark simple message strings as Java expressions if they contain:
- `+` sign (triggers concatenation detection): `"Warning: data quality issues (+5 failures)"` would be marked as `{{java}}`
- `/` character (triggers division detection): `"File: /data/input/file.csv"` -- mitigated by path detection logic but edge cases exist
- Parentheses (triggers method call detection): `"Warning (see documentation)"` could be falsely marked
- `.` followed by word characters (triggers method call detection): `"Error in module.submodule"` could be falsely marked

For the MESSAGE parameter, false positive `{{java}}` marking is relatively harmless if the Java bridge is available -- the Java bridge will evaluate the string literal and return it unchanged. However, if the Java bridge is NOT available, the `{{java}}` prefix is left in the config, and the message will contain literal `{{java}}` text in the log output.

### Recommended Converter Improvements

1. **Pass through CODE and PRIORITY as strings for runtime resolution**: Instead of defaulting non-numeric values to constants, pass them through:
```python
'code': config_raw.get('CODE', '0'),
'priority': config_raw.get('PRIORITY', '4')
```
Let the engine's `_process()` handle int conversion at runtime, after context and Java expression resolution.

2. **Add converter-time validation warning**: When CODE or PRIORITY contains a non-numeric value, log a warning during conversion so users know the value was defaulted.

3. **Handle negative CODE values**: Change `.isdigit()` to a try/except `int()` pattern:
```python
try:
    code_value = int(config_raw.get('CODE', '0'))
except (ValueError, TypeError):
    code_value = config_raw.get('CODE', '0')  # Pass through for runtime resolution
```

---

## Appendix M: Cross-Cutting Bug Impact Matrix

The Warn component is affected by two cross-cutting bugs that impact ALL v1 engine components. This appendix documents the specific impact on Warn and the interaction between the bugs.

### Bug Interaction Diagram

```
Warn._process(input_data)
    |
    +-- _resolve_message_variables(message)
    |       |
    |       +-- re.sub(pattern, replace_globalmap, resolved_message)
    |       |       |
    |       |       +-- replace_globalmap(match)
    |       |               |
    |       |               +-- self.global_map.get(key, 0)
    |       |                       |
    |       |                       +-- >>> TypeError: get() takes 2 positional
    |       |                           >>> arguments but 3 were given
    |       |                           >>> (BUG-WRN-002: get() signature missing 'default')
    |       |
    |       +-- [CRASH if message contains globalMap reference]
    |
    +-- [If no globalMap reference in message, _process() completes normally]
    |
    +-- return {'main': input_data}

BaseComponent.execute()
    |
    +-- result = self._process(input_data)  # May succeed
    |
    +-- self._update_global_map()
    |       |
    |       +-- for stat_name, stat_value in self.stats.items():
    |       |       self.global_map.put_component_stat(...)  # Works fine
    |       |
    |       +-- logger.info(f"... {stat_name}: {value}")
    |               |
    |               +-- >>> NameError: name 'value' is not defined
    |                   >>> (BUG-WRN-001: 'value' should be 'stat_value')
    |
    +-- [CRASH: NameError in _update_global_map()]
    |
    +-- except Exception as e:
    |       |
    |       +-- self._update_global_map()
    |       |       |
    |       |       +-- >>> NameError again (same bug in error handler)
    |       |
    |       +-- [SECONDARY CRASH in error handler]
    |       +-- raise  # Re-raises the NameError, not the original error
```

### Impact Assessment by Scenario

| Scenario | GlobalMap Present? | GlobalMap Ref in Message? | BUG-WRN-001 Triggered? | BUG-WRN-002 Triggered? | Outcome |
|----------|-------------------|--------------------------|------------------------|------------------------|---------|
| Basic warning, no globalMap | No | No | No (guarded by `if self.global_map`) | No | SUCCESS: Warning logged, stats updated, data passed through |
| Basic warning, with globalMap | Yes | No | **Yes** | No | CRASH: NameError in `_update_global_map()` after warning logged. Data NOT returned. |
| GlobalMap ref in message, no globalMap | No | Yes (not resolved) | No | No | SUCCESS: GlobalMap ref left as literal text. Warning logged with unresolved ref. |
| GlobalMap ref in message, with globalMap | Yes | Yes | Not reached (earlier crash) | **Yes** | CRASH: TypeError in `_resolve_message_variables()`. Warning NOT logged. |
| GlobalMap ref but via Java bridge | Yes | Yes (resolved by Java) | **Yes** | No (Java bridge resolves before regex) | CRASH: NameError in `_update_global_map()` after warning logged via Java bridge. |

**Key finding**: The Warn component can ONLY complete successfully when no GlobalMap is present. In any real pipeline with a GlobalMap (which is virtually all production jobs), the component will crash with `NameError` on every execution due to BUG-WRN-001.

### Fix Priority

Both bugs MUST be fixed before any production use of the v1 engine, not just the Warn component. The fixes are simple and low-risk:

1. **BUG-WRN-001** (`base_component.py:304`): Remove `{stat_name}: {value}` from the log message. One-line change. Zero risk.
2. **BUG-WRN-002** (`global_map.py:26`): Add `default: Any = None` to the `get()` method signature. One-line change. Zero risk.

---

## Appendix N: Component Registration and Discovery

### Engine Registration

The Warn component is registered in the engine's component type map (`engine.py` lines 173-174):

```python
# Control components
'Warn': Warn,
'tWarn': Warn,
```

Both the Talend name (`tWarn`) and the v1 name (`Warn`) are registered as aliases for the same class. This means job configurations can use either name to reference the component.

### Import Chain

```
engine.py
    |
    +-- from .components.control import Warn
            |
            +-- components/control/__init__.py
                    |
                    +-- from .warn import Warn
                            |
                            +-- components/control/warn.py
                                    |
                                    +-- class Warn(BaseComponent)
```

### Package Structure

```
src/v1/engine/
    components/
        control/
            __init__.py     # Exports: Warn, Die, SleepComponent, SendMailComponent
            warn.py         # Warn class (215 lines)
            die.py          # Die class (206 lines) -- sibling component
            sleep.py        # SleepComponent class
            send_mail.py    # SendMailComponent class
```

The `__init__.py` exports are correct:
```python
from .warn import Warn
from .die import Die
from .sleep import SleepComponent
from .send_mail import SendMailComponent

__all__ = ['Warn', 'Die']
__all__.append('SleepComponent')
__all__.append('SendMailComponent')
```

Note: The `__all__` list initialization style is inconsistent -- `Warn` and `Die` are in the initial list literal, while `SleepComponent` and `SendMailComponent` are appended. This is a minor style issue with no functional impact.

### Converter Type Mapping

The converter maps `tWarn` to `Warn` in two places:

1. **Component type mapping** (component_parser.py line 84):
```python
'tWarn': 'Warn',
```
This tells the converter to output `"type": "Warn"` in the v1 JSON config when it encounters a `tWarn` component in the Talend XML.

2. **Parameter mapping** (component_parser.py line 253):
```python
elif component_type == 'tWarn':
```
This enters the dedicated parameter extraction branch.

### Discovery Process

When the v1 engine loads a job configuration JSON, it:
1. Reads the `"type"` field of each component definition
2. Looks up the type in the `COMPONENT_MAP` dictionary
3. Instantiates the corresponding class with the component's config

For a tWarn component, the JSON might look like:
```json
{
    "id": "tWarn_1",
    "type": "Warn",
    "config": {
        "message": "Processing completed",
        "code": 0,
        "priority": 4
    }
}
```

The engine finds `"Warn"` in the map, instantiates `Warn(component_id="tWarn_1", config={...}, global_map=..., context_manager=...)`, and the component is ready for execution.

---

## Appendix O: Real-World Usage Patterns

### Common Talend Patterns Using tWarn

Based on analysis of Talend documentation and community examples, tWarn is typically used in the following patterns:

**Pattern 1: Subjob Completion Notification**
```
tFileInputDelimited_1 --> tMap_1 --> tFileOutputDelimited_1
                                         |
                                    OnSubjobOK
                                         |
                                    tWarn_1 (message: "Export completed", priority: 3/Info)
                                         |
                                    tLogCatcher_1
                                         |
                                    tLogRow_1
```

In this pattern, tWarn fires after the entire subjob completes successfully. The warning is informational (priority=3, Info level) and is caught by tLogCatcher for structured logging.

**Pattern 2: Data Quality Warning**
```
tFileInputDelimited_1 --> tFilterRow_1 --> tWarn_1 (message: "Filtered records found")
                              |                        |
                              +-- (REJECT) --> tFileOutputDelimited_2 (rejected rows file)
                              |
                              +-- (FLOW) --> tFileOutputDelimited_1 (good rows file)
```

In this pattern, tWarn is placed in the flow after filtering to alert that some records were filtered. The warning does not stop processing.

**Pattern 3: Conditional Warning with RunIf**
```
tFileInputDelimited_1 --> tFlowToIterate_1
                              |
                         RunIf (((Integer)globalMap.get("NB_LINE")) > 10000)
                              |
                         tWarn_1 (message: "Large file detected: " + ((Integer)globalMap.get("NB_LINE")) + " rows")
```

In this pattern, tWarn is triggered conditionally based on a RunIf expression. The warning message includes a globalMap reference to report the actual row count.

**Pattern 4: Error Handling with tDie/tWarn/tLogCatcher**
```
[Main Processing Subjob]
    tFileInputDelimited_1 --> tMap_1 --> tFileOutputDelimited_1
        |
        +-- OnSubjobOK --> tWarn_1 (priority: 3, message: "Success")
        +-- OnSubjobError --> tDie_1 (priority: 6, message: "Fatal: " + errorMsg)

[Logging Subjob]
    tLogCatcher_1 (Catch tWarn + Catch tDie)
        |
        +-- tMap_2 (enrich with timestamp, job name)
        |
        +-- tFileOutputDelimited_2 (audit log)
```

This is the canonical error handling pattern. tWarn handles success/info notifications; tDie handles fatal errors. Both are caught by tLogCatcher for unified audit logging.

### V1 Engine Compatibility with These Patterns

| Pattern | V1 Compatible? | Notes |
|---------|---------------|-------|
| Subjob Completion Notification | **Partial** | tWarn works; tLogCatcher not available; OnSubjobOK triggers depend on engine trigger support |
| Data Quality Warning | **Yes** | tWarn in flow works correctly; pass-through behavior preserved |
| Conditional Warning with RunIf | **Partial** | tWarn works; RunIf trigger support depends on engine trigger implementation; globalMap reference in message limited to `(Integer)` cast |
| Error Handling with tDie/tWarn/tLogCatcher | **Partial** | tWarn and tDie work individually; tLogCatcher not available; unified audit logging not possible |

### Message Template Examples

| Talend Message | V1 Engine Result | Issues |
|----------------|-----------------|--------|
| `"Processing completed"` | `"Processing completed"` | None -- works correctly |
| `"File: " + context.filename` | Depends on converter marking | If marked `{{java}}`: resolved by Java bridge. If not: unresolved. |
| `context.warn_message` | `"${context.warn_message}"` -> resolved by ContextManager | Works correctly |
| `"Row count: " + ((Integer)globalMap.get("tFileInputDelimited_1_NB_LINE"))` | Depends on converter marking | If marked `{{java}}`: resolved by Java bridge. If not: only `(Integer)` part resolved by regex. |
| `((String)globalMap.get("previous_result"))` | NOT resolved by regex | **Bug**: Only `(Integer)` cast supported. `(String)` cast left as literal text. |
| `TalendDate.getCurrentDate() + " - Warning"` | Must be `{{java}}` for resolution | Requires Java bridge; no Python fallback for Talend routines |

---

## Appendix P: Regression Risk Assessment

### What Could Break if Fixes Are Applied

This appendix documents the regression risk for each recommended fix, to help prioritize implementation.

**Fix 1: `_update_global_map()` -- Remove `{value}` reference**

| Aspect | Assessment |
|--------|------------|
| Change scope | `base_component.py` line 304 (cross-cutting) |
| Components affected | ALL v1 components |
| Current behavior | Crashes with NameError when globalMap is present |
| Fixed behavior | Logs stats without crash |
| Regression risk | **Zero** -- the current code never works when globalMap is present, so fixing it cannot break anything |
| Backward compatibility | Full -- only changes a log message format |

**Fix 2: `GlobalMap.get()` -- Add `default` parameter**

| Aspect | Assessment |
|--------|------------|
| Change scope | `global_map.py` line 26 (cross-cutting) |
| Components affected | ALL code calling `global_map.get()` |
| Current behavior | Crashes with NameError on every call |
| Fixed behavior | Returns value or default |
| Regression risk | **Zero** -- the current code never works, so fixing it cannot break anything |
| Backward compatibility | Full -- adds optional parameter with default None |

**Fix 3: GlobalMap variable names (WARN_MESSAGES etc.)**

| Aspect | Assessment |
|--------|------------|
| Change scope | `warn.py` lines 211-213 |
| Components affected | Warn component only |
| Current behavior | Stores as `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY` |
| Fixed behavior | Stores as BOTH Talend names and legacy names |
| Regression risk | **Very low** -- additive change that stores additional keys. Existing code reading `{id}_MESSAGE` still works. |
| Backward compatibility | Full -- both old and new names are set |

**Fix 4: Expand globalMap regex**

| Aspect | Assessment |
|--------|------------|
| Change scope | `warn.py` line 177 and `die.py` line 198 |
| Components affected | Warn and Die components |
| Current behavior | Only matches `(Integer)` cast |
| Fixed behavior | Matches all cast types |
| Regression risk | **Low** -- the expanded regex is a superset of the current regex, so all currently-matched patterns still match. New patterns that were previously unmatched will now be resolved. |
| Backward compatibility | Full -- all existing behavior preserved, new behavior added |

**Fix 5: Wire up `_validate_config()`**

| Aspect | Assessment |
|--------|------------|
| Change scope | `warn.py` (add call in `_process()`) |
| Components affected | Warn component only |
| Current behavior | No validation; invalid config silently defaults |
| Fixed behavior | Validation warnings logged; same defaulting behavior |
| Regression risk | **Very low** -- validation returns warnings but does not raise exceptions. Existing behavior preserved. |
| Backward compatibility | Full -- adding warnings does not change data flow |

### Overall Risk Summary

All recommended fixes are low-risk, additive changes. The cross-cutting fixes (1 and 2) have zero regression risk because the current code is completely broken (crashes on every execution with a globalMap). The Warn-specific fixes (3, 4, 5) are additive and backward-compatible.

---

## Appendix Q: Line-by-Line Code Walkthrough

### `warn.py` Complete Walkthrough

**Lines 1-14: Module header and imports**
```python
"""
Warn - Log warning message and continue execution.
Talend equivalent: tWarn
"""
import pandas as pd
from typing import Dict, Any, Optional, List
import logging
import re

from ...base_component import BaseComponent
from ...exceptions import ConfigurationError, ComponentExecutionError

logger = logging.getLogger(__name__)
```
- Module docstring correctly identifies the Talend equivalent
- Imports are appropriate and minimal: pandas for DataFrame handling, typing for type hints, logging for output, re for regex
- Relative imports from the base package are correct
- Module-level logger follows the `__name__` convention (resolves to `src.v1.engine.components.control.warn`)
- **Note**: `ConfigurationError` is imported but never used in the code. It could be used in `_validate_config()` if that method were activated. Dead import.

**Lines 17-53: Class definition and docstring**
```python
class Warn(BaseComponent):
    """..."""
```
- Inherits from `BaseComponent`, which provides `execute()`, `_update_stats()`, `_update_global_map()`, `validate_schema()`
- Docstring is comprehensive: describes purpose, configuration, inputs, outputs, statistics, and notes
- Documents all three config parameters with defaults
- Documents context variable and globalMap support
- Documents pass-through behavior
- Example configuration is valid JSON

**Lines 55-57: Class constants**
```python
VALID_PRIORITIES = [1, 2, 3, 4, 5, 6]
PRIORITY_NAMES = {1: 'trace', 2: 'debug', 3: 'info', 4: 'warn', 5: 'error', 6: 'fatal'}
```
- `VALID_PRIORITIES` is a list of integers for membership testing
- `PRIORITY_NAMES` maps integer priorities to human-readable names
- These constants are used by `_validate_config()` and `_log_warning_message()`
- **Contrast with Die**: The Die component uses individual constants (`PRIORITY_TRACE = 1`, etc.) instead of a dict. This inconsistency suggests the two components were authored independently.

**Lines 59-96: `_validate_config()`**
- Validates `message` is a string (if present)
- Validates `code` is an integer or digit string (if present)
- Validates `priority` is an integer or digit string (if present)
- Validates `priority` is in `VALID_PRIORITIES` range
- Returns list of error strings
- **DEAD CODE**: Never called by any code path. The `_process()` method has its own inline validation.

**Lines 98-162: `_process()`**
- Line 112: Logs processing start at INFO level
- Lines 116-118: Extracts config with defaults: `message='Warning'`, `code=0`, `priority=4`
- Lines 121-125: Converts code to int with try/except fallback to 0
- Lines 127-134: Converts priority to int with validation and fallback to 4
- Line 137: Resolves message variables (context + globalMap)
- Line 140: Logs warning at appropriate level
- Line 143: Stores warning in globalMap
- Lines 146-155: Updates statistics (pass-through pattern)
- Line 158: Returns `{'main': input_data}` (pass-through)
- Lines 160-162: Exception handler wraps in ComponentExecutionError

**Lines 164-186: `_resolve_message_variables()`**
- Line 166: Type guard for non-string messages
- Lines 172-173: Context variable resolution via ContextManager
- Lines 176-184: GlobalMap variable resolution via regex
  - Pattern: `r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'`
  - Only matches `(Integer)` cast (BUG-WRN-003)
  - Key pattern `\w+` excludes dots (BUG-WRN-004)
  - Default value hardcoded to 0 (incorrect for non-integer types)

**Lines 188-206: `_log_warning_message()`**
- Line 190: Formats log message with component ID and code
- Line 191: Looks up priority name from PRIORITY_NAMES dict
- Lines 193-204: Switch on priority level, calls appropriate logger method
- Line 206: Debug-level log with priority name for traceability

**Lines 208-214: `_store_warning_in_globalmap()`**
- Line 210: Guard for None globalMap
- Lines 211-213: Stores message, code, priority with `{self.id}_` prefix
  - Uses `_MESSAGE` not `_WARN_MESSAGES` (ENG-WRN-001)
  - Uses `_CODE` not `_WARN_CODE` (ENG-WRN-001)
  - Uses `_PRIORITY` not `_WARN_PRIORITY` (ENG-WRN-001)
- Line 214: Debug-level confirmation log

### Method Complexity Assessment

| Method | Lines | Cyclomatic Complexity | Assessment |
|--------|-------|----------------------|------------|
| `_validate_config()` | 38 | 8 (multiple if/elif branches) | Moderate -- but dead code |
| `_process()` | 65 | 6 (try/except, if/else for input) | Low-moderate -- straightforward |
| `_resolve_message_variables()` | 23 | 4 (if guards, regex sub) | Low |
| `_log_warning_message()` | 19 | 5 (priority switch) | Low |
| `_store_warning_in_globalmap()` | 7 | 1 (if guard) | Trivial |

Total class complexity is low, appropriate for a simple logging/pass-through component.
