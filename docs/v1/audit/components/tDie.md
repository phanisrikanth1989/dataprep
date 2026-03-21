# Audit Report: tDie / Die

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tDie` |
| **V1 Engine Class** | `Die` |
| **Engine File** | `src/v1/engine/components/control/die.py` (205 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (lines 261-267) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> NO dedicated `elif` branch; falls through to generic `parse_base_component()` + `_map_component_parameters()` |
| **Registry Aliases** | `Die`, `tDie` (registered in `src/v1/engine/engine.py` lines 175-176) |
| **Category** | Control / Logs & Errors |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/control/die.py` | Engine implementation (205 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 83, 261-267) | Type alias mapping (line 83: `'tDie': 'Die'`) and parameter mapping from Talend XML to v1 JSON (lines 261-267) |
| `src/converters/complex_converter/converter.py` | Dispatch -- no dedicated `elif` for `tDie`; uses generic `parse_base_component()` path (line 226) |
| `src/v1/engine/base_component.py` | Base class: `execute()` (line 188), `_update_stats()` (line 306), `_update_global_map()` (line 298), `_resolve_java_expressions()` (line 100) |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY`, etc. -- has broken `get()` method (line 28) |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy: `ComponentExecutionError` (line 24), `ConfigurationError` (line 14) |
| `src/v1/engine/engine.py` (lines 600-620) | Engine-level handling of Die exception via `hasattr(e, 'exit_code')` check at line 605 |
| `src/v1/engine/engine.py` (lines 175-176) | Component registry: `'Die': Die, 'tDie': Die` |
| `src/v1/engine/engine.py` (lines 520-536) | Top-level exception handler in `execute()` that catches the re-raised Die exception |
| `src/v1/engine/engine.py` (lines 832-888) | `run_job()` function and `__main__` block -- neither propagates exit_code |
| `src/v1/engine/components/control/__init__.py` | Package exports: `Die` (line 2), `__all__` includes `Die` (line 6) |
| `src/v1/engine/components/control/warn.py` | Sister component `Warn` (214 lines) -- shared patterns for comparison |
| `src/v1/engine/context_manager.py` | `resolve_string()` (line 76) and `resolve_dict()` used for context variable resolution in messages |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 5 | 0 | 4 of 5 Talend basic params extracted (MESSAGE, CODE, PRIORITY, EXIT_CODE); missing EXIT_JVM; default value mismatches for CODE and PRIORITY; expression handling gaps |
| Engine Feature Parity | **Y** | 0 | 4 | 3 | 1 | No tLogCatcher integration; globalMap regex only handles `(Integer)` cast; context resolution order issue; no EXIT_JVM support; no tPostJob lifecycle |
| Code Quality | **Y** | 2 | 3 | 5 | 1 | Cross-cutting base class bugs in _update_global_map() and GlobalMap.get(); _validate_config never called; exit_code not propagated to process exit; monkey-patched exception attribute |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | Lightweight component; regex compiled on every call (negligible for once-per-job component) |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

### Score Justification

**Converter Coverage (G)**: The converter extracts 4 of 5 runtime-relevant parameters (80%). The missing `EXIT_JVM` parameter is important for production scheduler integration but does not block basic functionality. Default value mismatches for `CODE` (1 vs Talend's 0) and `PRIORITY` (5 vs Talend's 0) affect jobs that rely on defaults, but most production jobs explicitly set these values. The `.isdigit()` expression handling gap is a moderate concern for jobs using dynamic error codes.

**Engine Feature Parity (Y)**: The core die-and-terminate behavior works correctly. The component raises `ComponentExecutionError`, the engine detects it via `hasattr(e, 'exit_code')`, and the job stops. However, four P1 gaps prevent production readiness: (1) globalMap references in messages only resolve `(Integer)` casts, (2) no tLogCatcher means error messages cannot be captured in structured output, (3) no process exit code propagation breaks scheduler integration, and (4) no tPostJob execution breaks cleanup patterns.

**Code Quality (Y)**: Two cross-cutting P0 bugs (`_update_global_map()` undefined variable and `GlobalMap.get()` broken signature) will crash the component at runtime when `global_map` is provided. These bugs affect all components, not just Die, but they are particularly impactful for Die because the exception propagation path calls `_update_global_map()` in the error handler. The monkey-patched `exit_code` attribute on `ComponentExecutionError` is a code smell but functionally works for detection purposes.

**Performance & Memory (G)**: Die is inherently lightweight. It processes no data, creates no DataFrames, and terminates immediately. The only minor concern is the regex compiled on every call to `_resolve_global_map_variables()`, but since Die executes at most once per job, this is negligible.

**Testing (R)**: Zero tests exist for the v1 Die engine component. Not a single execution path is verified. The cross-cutting base class bugs suggest that no component in the v1 engine has been tested with a live `global_map` instance.

---

## 3. Talend Feature Baseline

### What tDie Does

`tDie` throws an error, triggers the `tLogCatcher` component for exhaustive logging, and then kills the Job. It is a job termination component used for controlled error handling -- when a condition is met that makes continued processing unsafe or meaningless, `tDie` provides a structured way to halt execution with a diagnostic message, error code, and severity level. Unlike `tWarn` (which logs and continues), `tDie` always terminates the job.

`tDie` belongs to the Logs & Errors component family in Talend. It is one of three closely related components:
- **tDie**: Logs a message and terminates the job (fatal)
- **tWarn**: Logs a message and continues execution (non-fatal)
- **tLogCatcher**: Captures messages from both tDie and tWarn into a structured schema row for downstream processing

When `tDie` fires, `tLogCatcher` captures the complete message metadata (type, origin, priority, message, code) into a structured schema row and routes it to downstream components (typically `tLogRow` or a file output) before the job halts. This enables diagnostic output even in fatal-error scenarios.

The typical usage pattern is:
1. An upstream component completes or fails
2. A trigger connection (OnSubjobOk, OnComponentError, If) activates `tDie`
3. `tDie` resolves its message expression, sets globalMap variables, and throws `TDieException`
4. `tLogCatcher` intercepts the exception, builds a 12-field schema row, and outputs it
5. `tLogCatcher`'s downstream components write the error record to a log file or database
6. `tPostJob` runs cleanup code (close connections, delete temp files)
7. The job process exits with the configured error code

**Source**: [tDie Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/logs-and-errors/tdie-standard-properties), [tDie (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tdie), [Using tDie, tWarn and tLogCatcher for error handling](https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-12/using-tdie-twarn-and-tlogcatcher-for-error-handling), [Configuring the Job for catching the message triggered by the tDie component](https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tdie-tlogcatcher-tjava-configuring-job-for-catching-message-triggered-by-tdie-component-standard-component), [tLogCatcher (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tlogcatcher)

**Component family**: Logs & Errors (Control)
**Available in**: All Talend products (Standard).
**Cannot be used as a start component**: Must be triggered via a connection (OnSubjobOk, OnComponentOk, If, Row Main, etc.) from an upstream component.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Die Message | `MESSAGE` | String (Expression) | `""` | The message to be displayed before the Job is killed. Supports context variables (`context.var`), globalMap references (`((Integer)globalMap.get("key"))`), Java expressions with string concatenation, and routine calls. This message is captured by `tLogCatcher` in the `message` field. The expression is evaluated at runtime -- not at compile time. |
| 2 | Error Code | `CODE` | Integer (Expression) | `0` | Error code number, as an integer. Values exceeding 255 cannot function as error codes on Linux (due to POSIX exit code range 0-255). Captured by `tLogCatcher` in the `code` field. When `EXIT_JVM=true`, this value becomes the process exit code visible to the calling shell or scheduler. Can contain Java expressions for dynamic error codes. |
| 3 | Priority | `PRIORITY` | Integer | `0` | Severity level, as an integer. In Talend, this is an open integer field -- the value is passed directly to `tLogCatcher`'s `priority` field. Common convention maps: 1=trace, 2=debug, 3=info, 4=warn, 5=error, 6=fatal. However, Talend does not enforce this range; any non-negative integer is accepted. The priority value is purely informational metadata -- the job always terminates regardless of what priority is set. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 4 | Exit JVM Immediately | `EXIT_JVM` | Boolean (CHECK) | `false` | When checked, forces immediate JVM termination via `System.exit(errorCode)`. Even with this option enabled, `tPostJob` code will execute before the JVM exits (Talend registers a shutdown hook). When unchecked, the `TDieException` propagates normally through the Talend runtime and `tLogCatcher` can intercept it. This option is critical for scheduler integration -- without it, the process exit code may not reflect the error code. |
| 5 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. When enabled, execution statistics (start time, end time, status) are sent to the tStatCatcher listener. Rarely used in production jobs. |

### 3.3 Connection Types

`tDie` cannot be a start component. It must receive a connection from an upstream component. This is enforced at design-time in Talend Studio.

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| Row (Main) | Input | Row > Main | Accepts data flow from upstream. When tDie receives data, it processes the die logic and terminates. The incoming rows are counted but not output. This is the least common input connection type for tDie -- triggers are more typical. |
| `SUBJOB_OK` | Input (Trigger) | Trigger > OnSubjobOk | tDie fires when the upstream subjob completes successfully. Common pattern: upstream subjob succeeds but a downstream validation condition (e.g., row count check) determines the job should terminate. |
| `SUBJOB_ERROR` | Input (Trigger) | Trigger > OnSubjobError | tDie fires on upstream subjob error. Common pattern: escalate subjob errors to job-level termination with a descriptive message. |
| `COMPONENT_OK` | Input (Trigger) | Trigger > OnComponentOk | tDie fires when a specific upstream component completes successfully. More granular than SUBJOB_OK -- fires immediately when the component finishes, not when the entire subjob is done. |
| `COMPONENT_ERROR` | Input (Trigger) | Trigger > OnComponentError | tDie fires when a specific upstream component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` (If) | Input (Trigger) | Trigger > RunIf | tDie fires when a boolean condition evaluates to true. **This is the most common trigger type for tDie.** Common patterns: `((Integer)globalMap.get("tRowGenerator_1_NB_LINE")) <= 0` (die if no rows were generated), `((String)globalMap.get("tFileList_1_CURRENT_FILE")) == null` (die if file not found). The condition is a Java boolean expression evaluated at runtime. |
| None | Output | -- | **tDie has no output connections.** The job terminates when tDie fires. There is no data flow output, no SUBJOB_OK trigger, no SUBJOB_ERROR trigger, no downstream processing of any kind. The only "output" is via `tLogCatcher` which intercepts the exception before termination. |

### 3.4 GlobalMap Variables

Talend's generated Java code sets these variables in `globalMap` when `tDie` executes:

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_DIE_MESSAGE` (a.k.a. `DIE_MESSAGES`) | String | After execution | The resolved die message string. Note: the official property in the After variable scope uses the name `DIE_MESSAGES` (plural). In generated Java code, the key is typically `tDie_1_DIE_MESSAGE`. |
| `{id}_DIE_CODE` | Integer | After execution | The error code value. Known issue in the Talend community: this value is sometimes `null` when accessed after tDie fires because the job has already terminated. It is reliably available only within the `tLogCatcher` processing flow. |
| `{id}_DIE_PRIORITY` | Integer | After execution | The priority level value. Same accessibility caveat as `DIE_CODE`. |
| `{id}_ERROR_MESSAGE` | String | On error | Error details string. This is the standard Talend error message variable set for all components when an error occurs. For tDie, it contains the formatted die message. |

**Important caveat**: Because `tDie` terminates the job, these After-scope globalMap variables are typically only accessible within `tLogCatcher` processing that runs as part of the die handling flow. They are NOT available in subsequent subjobs because no subsequent subjobs execute after tDie fires (except tPostJob). Attempting to access `((Integer)globalMap.get("tDie_1_DIE_CODE"))` in a component triggered after tDie will return `null` because the job has already stopped.

### 3.5 tLogCatcher Integration

When `tLogCatcher` has the "Catch tDie" checkbox enabled in its Basic settings, it captures the following predefined read-only schema row when `tDie` fires:

| tLogCatcher Field | Type | Value from tDie | Description |
|-------------------|------|-----------------|-------------|
| `moment` | Date | Timestamp | The exact time when the die message is caught by tLogCatcher. Format depends on the runtime locale. |
| `pid` | String | Process ID | The process ID of the current Job execution. In Talend, this is the JVM process ID. |
| `root_pid` | String | Root PID | Root process ID. For top-level jobs, equals `pid`. For child jobs (invoked via `tRunJob`), this is the PID of the root parent job. |
| `father_pid` | String | Father PID | Father process ID. For top-level jobs, equals `pid`. For child jobs, this is the PID of the immediate parent job. |
| `project` | String | Project name | The Talend project name from the workspace metadata. |
| `job` | String | Job name | The name of the currently executing job. |
| `context` | String | Context name | The context name used to run the Job (e.g., `Default`, `Production`, `Test`). |
| `priority` | Integer | Priority value | The priority value from tDie's Priority field. Passed as-is -- no mapping to severity names. |
| `type` | String | `"tDie"` | Identifies the source as a tDie component (vs `"tWarn"` for tWarn or `"Java Exception"` for uncaught exceptions). |
| `origin` | String | Component ID | The component name/ID that triggered the message (e.g., `tDie_1`). |
| `message` | String | Die message | The fully resolved die message text, after context variable and globalMap variable substitution. |
| `code` | Integer | Error code | The error code from tDie's Error Code field. |

This schema is **read-only** and **predefined** -- you cannot add or remove columns. The tLogCatcher output feeds into downstream components (typically `tLogRow` for console display or `tFileOutputDelimited` for log file writing). The downstream components execute as part of the die handling flow, before the job terminates.

### 3.6 Behavioral Notes

1. **Job termination mechanism**: In Talend's generated Java code, `tDie` throws a `TDieException` (a subclass of `TalendException`). The Talend runtime's main processing loop catches `TDieException` specifically, distinguishing it from other exception types (`TWarnException`, general `Exception`). The `tLogCatcher` component, if configured, intercepts the `TDieException` and extracts the message, code, and priority before the job terminates.

2. **EXIT_JVM=true behavior**: When Exit JVM is enabled, Talend calls `System.exit(errorCode)` after the die message is processed and tLogCatcher has captured the data. This forces immediate JVM termination. Even in this mode, `tPostJob` code executes first because Talend registers a JVM shutdown hook for tPostJob processing. The error code becomes the process exit code visible to the calling shell/scheduler (`$?` in bash, `%ERRORLEVEL%` in Windows). This is the recommended mode for production jobs integrated with schedulers.

3. **EXIT_JVM=false behavior**: The `TDieException` propagates through the normal exception handling chain. `tLogCatcher` can intercept it, process the message, and route it to output. The job exits with a non-zero status but does not call `System.exit()` directly. The process exit code depends on the Talend runtime's default error handling, which may or may not set a non-zero exit code.

4. **Error code range on Linux**: POSIX exit codes are 0-255 (8-bit unsigned). Error codes above 255 are truncated modulo 256 (e.g., code 256 becomes 0, code 257 becomes 1). The Talend documentation explicitly warns: "Values exceeding 255 cannot function as error codes on Linux." Code 0 technically means "success" in POSIX but is a valid error code in Talend's context -- however, using code 0 with tDie is misleading as the job is terminating in error. Best practice is to use codes 1-255 for tDie.

5. **Message expression evaluation**: The die message supports full Java expression evaluation at runtime. Examples:
   - String concatenation: `"Error in file: " + context.filename`
   - globalMap lookups: `"Processed " + ((Integer)globalMap.get("tRowGenerator_1_NB_LINE")) + " rows"`
   - Routine calls: `"Timestamp: " + TalendDate.getDate("yyyy-MM-dd HH:mm:ss")`
   - Conditional expressions: `context.severity.equals("HIGH") ? "CRITICAL: " + context.error_msg : "Warning: " + context.error_msg`
   - Mixed: `"Job " + jobName + " failed at step " + ((String)globalMap.get("current_step")) + " with code " + context.errorCode`

6. **Priority is informational only**: Unlike `tWarn` where priority might affect log routing decisions, `tDie`'s priority is purely metadata captured by `tLogCatcher`. The job always terminates regardless of priority level. There is no built-in mapping from integer to severity name -- the integer is stored as-is in the `priority` field of the tLogCatcher output. The 1-6 convention (trace/debug/info/warn/error/fatal) is a community convention, not a Talend-enforced standard.

7. **Cannot be a start component**: tDie must be triggered by an upstream connection. Placing tDie as the first component in a subjob with no incoming connections will cause a design-time validation warning in Talend Studio. The component has no way to self-activate.

8. **tLogCatcher execution order**: When tDie fires, tLogCatcher captures the message BEFORE the job terminates. The tLogCatcher's downstream components (e.g., writing to a log file) execute as part of the die handling flow. This ensures diagnostic output is preserved even in fatal scenarios. The execution order is: tDie fires -> TDieException thrown -> tLogCatcher catches exception -> tLogCatcher outputs schema row -> downstream components process the row -> job terminates.

9. **tPostJob always runs**: Even after tDie fires, the tPostJob section of the job always executes. Talend guarantees this via a JVM shutdown hook (for EXIT_JVM=true) or via the runtime's finally block (for EXIT_JVM=false). This allows cleanup code (closing database connections, deleting temporary files, sending notification emails) to run regardless of how the job terminates.

10. **Common usage patterns**:
    - **Validation gate**: `tRowGenerator -> (OnSubjobOk) -> tDie [condition: row_count == 0]` -- terminate if source produced no data
    - **Error escalation**: `tFileInputDelimited -> (OnComponentError) -> tDie` -- terminate with descriptive error if file read fails
    - **Conditional termination**: `tFlowToIterate -> (If: condition) -> tDie` -- terminate based on computed condition
    - **Error logging**: `tDie + tLogCatcher -> tFileOutputDelimited` -- capture structured error log before termination

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses the **deprecated generic parameter mapping approach** (`_map_component_parameters()` in `component_parser.py` lines 261-267) rather than a dedicated `parse_tdie()` method. There is NO dedicated `elif component_type == 'tDie'` branch in `converter.py:_parse_component()`. The component falls through to the generic `parse_base_component()` path at line 226 of `converter.py`.

**Converter flow (step by step)**:
1. `converter.py:_parse_component()` (line 216) receives the XML node for the tDie component
2. At line 226, calls `component_parser.parse_base_component(node)` which:
   a. Extracts `componentName` = `'tDie'` from the XML node
   b. Maps it to `'Die'` via `COMPONENT_TYPE_MAP` (line 83 of component_parser.py)
   c. Iterates all `elementParameter` child nodes, building a `config_raw` dict of name->value pairs
   d. Calls `_map_component_parameters('tDie', config_raw)` (line 472)
   e. This hits the `elif component_type == 'tDie'` branch at line 261
   f. Returns a mapped config dict with renamed keys and int conversions
3. Back in `converter.py:_parse_component()`, the component type-specific `elif` chain is checked (lines 232-285)
4. `tDie` has no dedicated `elif` branch, so none of the type-specific parsers are called
5. The generic base component result is used as-is
6. Schema is extracted generically from `<metadata>` nodes (if any -- tDie typically has none)

**Converter code** (component_parser.py lines 261-267):
```python
# Die mapping
elif component_type == 'tDie':
    return {
        'message': config_raw.get('MESSAGE', 'Job execution stopped'),
        'code': int(config_raw.get('CODE', '1')) if str(config_raw.get('CODE', '1')).isdigit() else 1,
        'priority': int(config_raw.get('PRIORITY', '5')) if str(config_raw.get('PRIORITY', '5')).isdigit() else 5,
        'exit_code': int(config_raw.get('EXIT_CODE', '1')) if str(config_raw.get('EXIT_CODE', '1')).isdigit() else 1
    }
```

**Comparison with tWarn converter** (component_parser.py lines 253-258):
```python
# Warn mapping
elif component_type == 'tWarn':
    return {
        'message': config_raw.get('MESSAGE', 'Warning'),
        'code': int(config_raw.get('CODE', '0')) if str(config_raw.get('CODE', '0')).isdigit() else 0,
        'priority': int(config_raw.get('PRIORITY', '4')) if str(config_raw.get('PRIORITY', '4')).isdigit() else 4
    }
```

Notable differences between the Die and Warn converters:
- Die has `exit_code` field; Warn does not (correct -- tWarn does not terminate the job)
- Die defaults `code=1`; Warn defaults `code=0` (Die should also default to 0 to match Talend)
- Die defaults `priority=5` (error); Warn defaults `priority=4` (warn) (reasonable convention but differs from Talend's 0 default for both)
- Die defaults `message='Job execution stopped'`; Warn defaults `message='Warning'` (both differ from Talend's empty string default)

### 4.2 Parameter Extraction Table

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `MESSAGE` | Yes | `message` | 263 | Default `'Job execution stopped'` -- Talend default is empty string `""`. Provides a more helpful default for jobs that omit explicit messages, but changes behavior for jobs relying on the Talend default empty string. |
| 2 | `CODE` | Yes | `code` | 264 | Converted via `.isdigit()` check. **Default `1` differs from Talend default `0`.** If a Talend job does not explicitly set the error code, the converted job will use code 1 instead of code 0. This may affect downstream error code checking logic. |
| 3 | `PRIORITY` | Yes | `priority` | 265 | Converted via `.isdigit()` check. **Default `5` differs from Talend default `0`.** V1 interprets 5 as "error" level and logs accordingly. Talend's default 0 has no special severity mapping. |
| 4 | `EXIT_CODE` | Yes | `exit_code` | 266 | Converted via `.isdigit()` check. Default `1` is reasonable. **Caution**: Standard Talend tDie XML does not have an `EXIT_CODE` parameter. Talend uses `CODE` for both the tLogCatcher error code AND the process exit code when `EXIT_JVM=true`. The v1 converter introduces a separate `exit_code` field that will always fall back to default `1` for real Talend XML exports, making the exit code non-configurable from the source XML. |
| 5 | `EXIT_JVM` | **No** | -- | -- | **Not extracted.** No `sys.exit()`-equivalent support in the v1 engine. When a Talend job has `EXIT_JVM=true`, the v1 engine will not set the process exit code. The Die exception propagates normally but the process exits with code 0. |
| 6 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used in production) |
| 7 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact; used only in Talend Studio designer canvas) |

**Summary**: 4 of 5 runtime-relevant parameters extracted (80%). Only `EXIT_JVM` is missing.

### 4.3 Schema Extraction

tDie does not define an output schema in Talend. It has no `<metadata>` child nodes in the Talend XML. The generic `parse_base_component()` schema extraction loop will find no schema columns, which is correct -- tDie produces no data output.

### 4.4 Expression Handling

**Context variable handling** (component_parser.py generic loop, lines 449-456):
- During the `parse_base_component()` scan of `elementParameter` nodes, the MESSAGE field value is examined
- Simple `context.var` references are detected by checking `'context.' in value`
- If the expression is NOT a Java expression (per `detect_java_expression()`), it is wrapped as `${context.var}` for ContextManager resolution at runtime
- If it IS a Java expression (detected by the presence of operators, method calls, etc.), it is left as-is for the Java expression marking step

**Java expression handling** (component_parser.py, lines 462-469):
- After raw parameter extraction, the `mark_java_expression()` method scans all non-CODE/IMPORT/UNIQUE_NAME string values in the config
- Values containing Java operators (`+`, `-`, `*`, `/`), method calls (`.get(`, `.equals(`), routine references (`TalendDate.`, `StringHandling.`), etc. are detected by `detect_java_expression()`
- Matched values are prefixed with `{{java}}` marker
- At runtime, the engine's `BaseComponent._resolve_java_expressions()` (base_component.py line 100) resolves these markers via the Java bridge

**How it works for tDie specifically**:
- The `MESSAGE` field is the primary candidate for expression handling. Examples:
  - `"Error in file: " + context.filename` -> detected as Java expression -> marked with `{{java}}` -> resolved by Java bridge at runtime
  - `context.error_message` -> detected as simple context reference -> wrapped as `${context.error_message}` -> resolved by ContextManager at runtime
  - `"Static error message"` -> no Java expression detected -> passed through as-is
- The `CODE` and `PRIORITY` fields are processed by `.isdigit()` BEFORE expression marking can occur (lines 264-265). This means:
  - `context.errorCode` -> `.isdigit()` returns False -> falls back to default `1` -> **expression silently lost**
  - `500` (string) -> `.isdigit()` returns True -> converted to int `500` -> correct
  - `"500"` (quoted string) -> `.isdigit()` returns True -> converted to int `500` -> correct

**Known limitations for tDie**:
1. The `.isdigit()` conversion on CODE, PRIORITY, and EXIT_CODE rejects negative numbers (e.g., `-1`), floating-point strings (e.g., `"3.14"`), and Java expressions (e.g., `context.errorCode + 100`). If `CODE` contains a context variable or expression, the value is silently replaced with the default.
2. The MESSAGE field supports both context variables and Java expressions, but the ordering of resolution matters: `BaseComponent.execute()` resolves context variables first (line 202), then `_resolve_java_expressions()` resolves Java markers (line 198). For messages that mix both, this works correctly. However, if a Java expression result contains `${context.var}`, it will NOT be resolved because Java resolution happens before context resolution in the `execute()` method (Java at line 198, context at line 202). Wait -- actually Java resolution is at line 198 and context resolution is at line 202, so Java resolves first. But Die's `_process()` additionally calls `context_manager.resolve_string()` (line 133), providing a second chance for context resolution. See ENG-DIE-005 for the double-resolution concern.

### 4.5 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-DIE-001 | **P2** | **Default CODE mismatch**: Converter defaults `CODE` to `1` (line 264), but Talend default is `0`. If a Talend job does not explicitly set the error code, the converter produces `1` instead of `0`. While both are integers, downstream error code checking logic (e.g., `if errorCode == 0 then ...`) will behave differently. In Talend, a tDie with no explicit code would show `0` in tLogCatcher; in v1, it would show `1`. This is a silent behavioral change that could affect error handling workflows. |
| CONV-DIE-002 | **P2** | **Default PRIORITY mismatch**: Converter defaults `PRIORITY` to `5` (line 265), but Talend default is `0`. In Talend, priority `0` has no special severity meaning and is simply stored as-is. In v1, priority `5` maps to `logger.error()` level, which changes the visible logging behavior. A Talend job that uses the default priority `0` would silently get elevated to "error" level logging in v1. This could flood error monitoring systems with false positives. |
| CONV-DIE-003 | **P2** | **EXIT_JVM not extracted**: The `EXIT_JVM` parameter is not extracted from the Talend XML. When a Talend job has `EXIT_JVM=true`, the v1 engine will not call `sys.exit()`. The job will terminate via exception but the process exit code will not be set to the error code value. This matters for scheduler integration (cron, Airflow, Jenkins, Control-M) and shell scripts that check `$?` or `%ERRORLEVEL%`. |
| CONV-DIE-004 | **P2** | **EXIT_CODE may not exist in Talend XML**: The converter reads `config_raw.get('EXIT_CODE', '1')` but standard Talend tDie XML does not have an `EXIT_CODE` elementParameter. Talend uses `CODE` for both the tLogCatcher error code and the process exit code (when EXIT_JVM=true). The v1 converter introduces a synthetic `exit_code` field that will always fall back to default `1` for real Talend XML exports. This means the `exit_code` in v1 is non-configurable from the source XML and always `1`, even if the Talend job set `CODE=42`. The engine should use `code` as the exit code (matching Talend behavior) unless `EXIT_CODE` is explicitly present. |
| CONV-DIE-005 | **P2** | **`.isdigit()` rejects expressions in CODE/PRIORITY/EXIT_CODE**: If these fields contain context variables (e.g., `context.errorCode`), Java expressions (e.g., `100 + context.offset`), or negative numbers (e.g., `-1`), `.isdigit()` returns False and the value falls back to the hardcoded default. The expression is silently lost. Should detect and preserve expression strings for runtime resolution, similar to how the MESSAGE field handles expressions. Example: `str(config_raw.get('CODE', '0')).isdigit()` evaluates `"context.errorCode".isdigit()` -> False -> falls back to `1`. The context variable is discarded without any warning or logging. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Die message display | **Yes** | High | `_process()` line 126 | Message retrieved from config with default `'Job execution stopped'`, logged at appropriate level before raising exception |
| 2 | Error code capture | **Yes** | Medium | `_process()` line 127 | Retrieved from config with default `1`. Stored in globalMap. Attached to exception message string but not extractable as an integer from the exception. |
| 3 | Priority-based logging | **Yes** | Medium | `_process()` lines 142-149 | Maps priority 1-6 to Python logging levels. However, levels 1-3 are all mapped to `logger.info()` (should distinguish trace/debug/info). See ENG-DIE-007. |
| 4 | Context variable resolution in message | **Yes** | High | `_process()` line 133 | Uses `context_manager.resolve_string()` which handles `${context.var}` and bare `context.var` patterns |
| 5 | globalMap variable resolution in message | **Partial** | Low | `_resolve_global_map_variables()` line 184 | Only handles `((Integer)globalMap.get("key"))` pattern with `\w+` key names. Missing all other cast types and uncast references. See ENG-DIE-001. |
| 6 | Job termination via exception | **Yes** | High | `_process()` lines 170-175 | Creates `ComponentExecutionError`, monkey-patches `exit_code` attribute, raises it. Correctly includes component ID, message, and exit code in the exception string. |
| 7 | Engine-level Die detection | **Yes** | Medium | `engine.py` lines 604-607 | `hasattr(e, 'exit_code')` check re-raises the exception, stopping the execution loop. Duck-typing approach is fragile (any exception with `exit_code` attr would trigger). |
| 8 | Top-level exception handling | **Yes** | Medium | `engine.py` lines 520-536 | `execute()` catches the re-raised exception, returns error dict. Does NOT extract `exit_code` from the exception. |
| 9 | GlobalMap variable storage | **Yes** | Medium | `_process()` lines 152-158 | Stores `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY`, `{id}_EXIT_CODE`, `JOB_ERROR_MESSAGE`, `JOB_EXIT_CODE`. Key names do not match Talend convention (see NAME-DIE-001). |
| 10 | Statistics tracking | **Yes** | High | `_process()` lines 161-167 | Correctly counts input rows as rejected: `NB_LINE=len(input_data)`, `NB_LINE_OK=0`, `NB_LINE_REJECT=len(input_data)`. Without input: `NB_LINE=1, NB_LINE_OK=0, NB_LINE_REJECT=1`. |
| 11 | Input data handling | **Yes** | High | `_process()` lines 161-167 | Handles both with-input (`input_data is not None and not input_data.empty`) and no-input (`else`) cases correctly |
| 12 | Java expression support in message | **Yes** | High | Via `BaseComponent._resolve_java_expressions()` line 100 | Java expressions marked with `{{java}}` prefix are resolved before `_process()` runs. Requires Java bridge to be configured. |
| 13 | **EXIT_JVM (System.exit)** | **No** | N/A | -- | **No `sys.exit()` call anywhere in the execution chain.** The Die exception propagates to `engine.execute()` which catches it and returns an error dict. The process exit code remains 0 (success) regardless of the configured exit_code. Schedulers and shell scripts checking `$?` will not detect the job failure. |
| 14 | **tLogCatcher integration** | **No** | N/A | -- | **No tLogCatcher component exists in the v1 engine.** Die messages are logged via Python's `logging` module but cannot be captured in a structured DataFrame for downstream processing. The standard Talend pattern `tDie -> tLogCatcher -> tFileOutputDelimited` is completely unsupported. Error messages are written to stderr/stdout but not to structured error log files. |
| 15 | **tPostJob execution after Die** | **No** | N/A | -- | **When Die raises ComponentExecutionError, engine._execute_component() re-raises it (line 607), engine.execute() catches it (line 520) and returns immediately.** Any tPostJob components in the job config are never executed. In Talend, tPostJob ALWAYS runs -- even after tDie fires. This breaks cleanup patterns: database connections are not closed, temporary files are not deleted, notification emails are not sent. |
| 16 | **Non-Integer globalMap casts** | **No** | N/A | -- | **Only `((Integer)globalMap.get("key"))` is handled.** `((String)globalMap.get("key"))`, `((Long)globalMap.get("key"))`, `((Float)globalMap.get("key"))`, `((Double)globalMap.get("key"))`, `((Object)globalMap.get("key"))`, and uncast `globalMap.get("key")` are all silently left as literal text in the resolved message. |
| 17 | **Error code as process exit code** | **No** | N/A | -- | **Talend uses the tDie CODE value as the process exit code when EXIT_JVM=true.** In v1, the `exit_code` config value is attached to the exception and stored in globalMap, but it is never used to set the actual process exit code via `sys.exit()`. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-DIE-001 | **P1** | **globalMap resolution only handles `(Integer)` cast**: The `_resolve_global_map_variables()` method (line 184-205 of die.py) uses the regex pattern `r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'`. This only matches the `(Integer)` cast. In Talend, die messages commonly reference other cast types: `((String)globalMap.get("error_details"))` for string values, `((Long)globalMap.get("total_records"))` for long integers, `((Float)globalMap.get("completion_pct"))` for floating point. All non-Integer casts are silently left as literal text in the resolved message. For example, a message like `"Failed after processing " + ((String)globalMap.get("tFileList_1_CURRENT_FILE"))` would resolve to `"Failed after processing ((String)globalMap.get("tFileList_1_CURRENT_FILE"))"` -- the globalMap reference appears as literal text in the error output. The sibling `Warn` component has the identical limitation (warn.py line 177). |
| ENG-DIE-002 | **P1** | **No tLogCatcher integration**: Talend's `tDie` is designed to work hand-in-hand with `tLogCatcher`. The die message, code, priority, and origin are captured into a structured 12-field schema row before the job terminates. This allows the error to be written to a log file, inserted into an audit database, sent via email, etc. V1 has no `tLogCatcher` component. The die message is logged via Python's `logging` module (which writes to stderr by default) but cannot be captured in a structured DataFrame for downstream processing. Any Talend job that uses the pattern `tDie -> tLogCatcher -> tFileOutputDelimited` (a very common error handling pattern) will lose the structured error logging capability in v1. |
| ENG-DIE-003 | **P1** | **No EXIT_JVM / sys.exit() support**: When Talend's `EXIT_JVM=true`, the JVM process exit code is set to the error code via `System.exit(errorCode)`. In v1, the Die exception propagates through `engine._execute_component()` (re-raised at line 607), reaches `engine.execute()` (caught at line 520), and results in a return dict with `status='error'`. The process exit code remains 0 (success). The entire exception propagation chain -- `_execute_component()`, `execute()`, `run_job()`, and `__main__` -- never calls `sys.exit()` with the exit code. Schedulers (cron, Airflow, Jenkins, Control-M) that check the process exit code (`$?` in bash) will see 0 and incorrectly report the job as successful. |
| ENG-DIE-004 | **P1** | **No tPostJob execution after Die**: In Talend, `tPostJob` components always execute, even after `tDie` fires. Talend guarantees this via a JVM shutdown hook (for EXIT_JVM=true) or via the runtime's finally block (for EXIT_JVM=false). In v1, when Die raises `ComponentExecutionError`, `engine._execute_component()` re-raises it at line 607 (bypassing the normal component completion path on lines 609-620), `engine.execute()` catches it at line 520 and returns immediately. The main execution loop (lines 452-498) is exited. Any tPostJob components, tPreJob components not yet executed, or any remaining components are abandoned. This breaks cleanup patterns: database connections are not closed, temporary files are not deleted, file handles are not released, notification emails are not sent. |
| ENG-DIE-005 | **P2** | **Double context resolution**: The Die component resolves context variables in the message twice: (1) via `BaseComponent.execute()` line 202 (`self.config = self.context_manager.resolve_dict(self.config)`) which resolves ALL config string values including the message, and (2) in `_process()` line 133 (`self.context_manager.resolve_string(message)`) which resolves the already-resolved message again. The second call is redundant but usually harmless -- `resolve_string()` on an already-resolved string is a no-op because `${context.var}` patterns have already been replaced. However, if a context variable resolves to a string containing `${context.other}` (e.g., `context.template = "Error: ${context.error_msg}"`), the second pass would attempt to resolve the embedded reference. In Talend, die messages are resolved only once. This creates a subtle behavioral difference for jobs using templated context variables. |
| ENG-DIE-006 | **P2** | **globalMap.get() default value of `0` for missing keys**: In `_resolve_global_map_variables()` line 202, the replacement function calls `self.global_map.get(key, 0)` for missing globalMap keys. This has two problems: (1) `GlobalMap.get()` does not accept a second argument (see BUG-DIE-002), so this will crash at runtime. (2) Even if the `get()` method were fixed, defaulting to `0` for a missing key silently masks configuration errors. In Talend, referencing a non-existent globalMap key via `((Integer)globalMap.get("missing_key"))` returns `null`, which would cause a NullPointerException if used in string concatenation, alerting the developer to the issue. In v1, the reference would silently resolve to `"0"`, producing a misleading message like `"Processed 0 rows"` instead of failing. |
| ENG-DIE-007 | **P2** | **Priority mapping differs from Talend/Warn for levels 1-3**: The engine maps priorities 1 (`PRIORITY_TRACE`), 2 (`PRIORITY_DEBUG`), and 3 (`PRIORITY_INFO`) all to `logger.info()` at line 142-143: `if priority <= self.PRIORITY_INFO: logger.info(log_message)`. In a correct mapping, priority 1 (trace) should map to `logger.debug()` with a "TRACE:" prefix, priority 2 (debug) should map to `logger.debug()`, and only priority 3 (info) should map to `logger.info()`. The sibling `Warn` component correctly distinguishes these three levels (warn.py lines 193-198): `if priority <= 1: logger.debug(f"TRACE: ...")` / `elif priority == 2: logger.debug(...)` / `elif priority == 3: logger.info(...)`. Die should match Warn's more correct mapping. |
| ENG-DIE-008 | **P3** | **`{id}_EXIT_CODE` globalMap variable is non-standard**: The Die component stores `{id}_EXIT_CODE` in globalMap (line 156). Talend's standard globalMap variables for tDie are `{id}_DIE_MESSAGE` (or `DIE_MESSAGES`), `{id}_DIE_CODE`, and `{id}_DIE_PRIORITY`. The `EXIT_CODE` variable is not a standard Talend variable. While the v1 engine also stores `JOB_EXIT_CODE` and `JOB_ERROR_MESSAGE` (useful non-standard extensions for v1-specific tooling), downstream components expecting Talend-standard variable names will not find them. This is a low-priority issue because tDie terminates the job, so downstream components rarely access these variables (only tLogCatcher and tPostJob would). |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | V1 Key Name | Notes |
|----------|-------------|----------|-------------|-------|
| `{id}_DIE_MESSAGE` (a.k.a. `DIE_MESSAGES`) | Yes | **Partial** | `{id}_MESSAGE` | V1 uses `_MESSAGE` suffix instead of Talend's `_DIE_MESSAGE` or `_DIE_MESSAGES`. Downstream code using `((String)globalMap.get("tDie_1_DIE_MESSAGE"))` will get null/None instead of the die message. |
| `{id}_DIE_CODE` | Yes | **Partial** | `{id}_CODE` | V1 uses `_CODE` suffix instead of Talend's `_DIE_CODE`. Same naming mismatch as above. |
| `{id}_DIE_PRIORITY` | Yes | **Partial** | `{id}_PRIORITY` | V1 uses `_PRIORITY` suffix instead of Talend's `_DIE_PRIORITY`. Same naming mismatch. |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Talend sets this standard error variable on component error. V1 does not set `{id}_ERROR_MESSAGE`. The closest equivalent is `JOB_ERROR_MESSAGE` (set at line 157), but the key name differs. |
| `{id}_EXIT_CODE` | No (non-standard) | **Yes** | `{id}_EXIT_CODE` | V1-specific, not present in Talend. Stores the configured exit code value. |
| `JOB_ERROR_MESSAGE` | No (non-standard) | **Yes** | `JOB_ERROR_MESSAGE` | V1-specific convenience variable. Stores the die message at a job-wide key, accessible by any component. Useful but non-standard -- no Talend equivalent. |
| `JOB_EXIT_CODE` | No (non-standard) | **Yes** | `JOB_EXIT_CODE` | V1-specific convenience variable. Stores the exit code at a job-wide key. Useful but non-standard. |
| `{id}_NB_LINE` | Yes (via base class) | **Yes** | `{id}_NB_LINE` | Set via `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()`. **Will crash at runtime due to BUG-DIE-001** (undefined `value` variable in the log statement on base_component.py line 304). |
| `{id}_NB_LINE_OK` | Yes (via base class) | **Yes** | `{id}_NB_LINE_OK` | Always 0 (correct for Die -- no successful output). Same crash issue as NB_LINE. |
| `{id}_NB_LINE_REJECT` | Yes (via base class) | **Yes** | `{id}_NB_LINE_REJECT` | Equals NB_LINE (all rows counted as rejected). Same crash issue. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | `{id}_EXECUTION_TIME` | V1-specific statistic from BaseComponent. Not present in Talend. Records wall-clock execution time in seconds. |

### 5.4 Exception Propagation Deep Dive

The Die component's exception propagation passes through four layers. Understanding each layer is critical for diagnosing issues:

**Layer 1: Die._process()** (die.py lines 170-175)
```python
error = ComponentExecutionError(
    self.id,
    f"Job terminated: {message} (exit code: {exit_code})"
)
error.exit_code = exit_code  # Monkey-patch: dynamically adds attribute
raise error
```
- Creates a `ComponentExecutionError` with the component ID and a formatted message
- Monkey-patches `exit_code` as a dynamic attribute (not in the class definition)
- Raises the exception

**Layer 2: BaseComponent.execute()** (base_component.py lines 227-234)
```python
except Exception as e:
    self.status = ComponentStatus.ERROR
    self.error_message = str(e)
    self.stats['EXECUTION_TIME'] = time.time() - start_time
    self._update_global_map()  # CRASHES: BUG-DIE-001 (undefined 'value')
    logger.error(f"Component {self.id} execution failed: {e}")
    raise
```
- Catches the exception
- Updates component status to ERROR
- Attempts to call `_update_global_map()` which CRASHES due to BUG-DIE-001
- If the crash were fixed, re-raises the original exception (preserving `exit_code` attribute)

**Layer 3: ETLEngine._execute_component()** (engine.py lines 600-607)
```python
except Exception as e:
    logger.error(f"Component {comp_id} failed: {str(e)}")
    if hasattr(e, 'exit_code'):
        raise e  # Die exception -- stop the job
    # Non-Die errors: update status and continue
    self.trigger_manager.set_component_status(comp_id, 'error')
    ...
```
- Catches the exception
- Checks for `exit_code` attribute (duck typing -- not `isinstance()` check)
- If present (Die exception), re-raises to stop the entire job
- If absent (non-Die error), marks the component as failed and continues execution

**Layer 4: ETLEngine.execute()** (engine.py lines 520-536)
```python
except Exception as e:
    logger.error(f"Job execution failed: {e}")
    self._cleanup()
    return {
        'job_name': self.job_name,
        'status': 'error',
        'error': str(e),
        ...
    }
```
- Catches the re-raised exception
- Logs the error
- Calls `_cleanup()` (for Java bridge, not for tPostJob)
- Returns a dict with `status='error'` and the error message as a string
- **DOES NOT** extract `exit_code` from the exception
- **DOES NOT** call `sys.exit()`
- **DOES NOT** execute tPostJob components

**Layer 5: run_job() and __main__** (engine.py lines 832-888)
- `run_job()` returns the stats dict from `engine.execute()` -- no exit code handling
- `__main__` prints the stats as JSON and exits normally -- process exit code is 0

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-DIE-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 reads `logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} {stat_name}: {value}")`. The for loop variable (line 301) is `stat_value`, not `value`. This causes `NameError: name 'value' is not defined` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components since `_update_global_map()` is called by `BaseComponent.execute()` line 218 (on success) and line 231 (on error). For Die specifically, the crash occurs in the error handler path (line 231) when the `ComponentExecutionError` propagates up from `_process()`. The crash in `_update_global_map()` replaces the original Die error with a `NameError`, potentially confusing error handling logic. |
| BUG-DIE-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature on line 26 is `def get(self, key: str) -> Optional[Any]` (one parameter: `key`), but the body on line 28 calls `self._map.get(key, default)` where `default` is not defined. This causes `NameError: name 'default' is not defined` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one, causing `TypeError: get() takes 2 positional arguments but 3 were given`. **CROSS-CUTTING**: Affects all code using `global_map.get()`. For Die specifically, `_resolve_global_map_variables()` line 202 calls `self.global_map.get(key, 0)` which passes two arguments to a one-argument method. This means ANY die message containing `((Integer)globalMap.get("..."))` will crash with `TypeError` at runtime, making globalMap variable resolution completely non-functional. |
| BUG-DIE-003 | **P1** | `src/v1/engine/components/control/die.py:198` | **globalMap regex only matches `(\w+)` key pattern**: The regex `r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'` uses `\w+` which matches only `[a-zA-Z0-9_]`. While this covers the vast majority of auto-generated Talend keys (e.g., `tRowGenerator_1_NB_LINE`, `tFileList_1_CURRENT_FILE`), manually set globalMap keys with dots (`my.custom.key`), hyphens (`my-custom-key`), or other non-word characters are silently ignored. The regex match fails, the expression is left as literal text, and no warning is logged. A more permissive pattern like `[^"]+` would match any key that does not contain a double-quote. |
| BUG-DIE-004 | **P1** | `src/v1/engine/components/control/die.py:67-107` | **`_validate_config()` is never called**: The method exists (40 lines of validation logic) but is never invoked by any code path. Not by `__init__()`, not by `_process()`, not by `BaseComponent.execute()`. The base class does not define a `_validate_config()` lifecycle hook. The method validates: `code` (must be int or int-string), `priority` (must be int 1-6), `exit_code` (must be int or int-string), `message` (must be string or None). Without this validation, invalid configurations like `priority=99`, `code="abc"`, or `exit_code="not_a_number"` are not caught until they cause runtime errors (or worse, silent misbehavior where `int("abc")` would be caught by the `try/except` in `_process()` and wrapped in a different exception type). |
| BUG-DIE-005 | **P1** | `src/v1/engine/engine.py:604-607` + `engine.py:520-536` + `engine.py:832-888` | **Die exit_code never propagated to process exit code**: The entire exit_code mechanism is inert. Tracing the path: (1) Die attaches `exit_code` to the exception at die.py:174. (2) Engine checks `hasattr(e, 'exit_code')` at engine.py:605 -- but only to decide whether to re-raise (it never reads the VALUE of `exit_code`). (3) `execute()` catches the exception at engine.py:520 and returns `{'status': 'error', 'error': str(e)}` -- it does NOT include `exit_code` in the return dict. (4) `run_job()` at engine.py:857 returns the stats dict unchanged. (5) `__main__` at engine.py:888 calls `print(json.dumps(stats))` and exits normally with code 0. The `exit_code` attribute is set, checked for existence, but its VALUE is never read, never included in the return dict, and never passed to `sys.exit()`. The process always exits with code 0 regardless of the Die component's configured exit code. |

### 6.2 _validate_config() Analysis

The dead `_validate_config()` method (lines 67-107) implements the following validation rules:

**What it validates**:
- `code` (lines 77-84): Must be an integer or a string that can be converted to int via `int()`. Accepts both `42` (int) and `"42"` (string). Rejects `"abc"`, `None`, `3.14` (float).
- `priority` (lines 86-91): Must be an integer between 1 and 6 inclusive. String digits are accepted (e.g., `"5"` is converted to `5` then range-checked). Values outside 1-6 produce an error message.
- `exit_code` (lines 93-100): Same validation as `code` -- must be int or int-string. No range check (POSIX 0-255 range not validated).
- `message` (lines 102-105): Must be a string or None. Rejects non-string types like integers, lists, dicts.

**What it does NOT validate** (even if it were called):
- `code` range: 0-255 for POSIX compatibility (codes > 255 are truncated modulo 256 on Linux)
- `priority` semantic validity: While it enforces 1-6, Talend allows any non-negative integer (0 is valid in Talend)
- `message` maximum length: No upper bound check (extremely long messages could cause logging issues)
- `exit_code` range: 0-255 for POSIX (same issue as `code`)
- Required fields: No field is marked as required -- all validations use `if 'field' in self.config`
- Type consistency between `code` and `exit_code`: Both should be integers, but they are validated independently

**How it would be invoked if wired up**:
The method returns `List[str]` (list of error messages). An empty list means valid. However, no calling code exists to check the list or raise exceptions from it. If wired up, the caller would need to:
1. Call `errors = self._validate_config()`
2. Check `if errors:`
3. Raise `ConfigurationError(self.id, f"Invalid configuration: {'; '.join(errors)}")`

### 6.3 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-DIE-001 | **P2** | **globalMap key naming differs from Talend**: V1 stores `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY` in globalMap (die.py lines 153-155). Talend stores `{id}_DIE_MESSAGE` (or `DIE_MESSAGES`), `{id}_DIE_CODE`, `{id}_DIE_PRIORITY`. The `DIE_` infix is part of Talend's standard naming convention for tDie component variables. Without this prefix, any downstream component or expression referencing `((String)globalMap.get("tDie_1_DIE_MESSAGE"))` will get null/None. This is particularly impactful for `tLogCatcher` replacement logic that might look for the standard Talend key names. The Warn component has the same issue -- it stores `{id}_MESSAGE` instead of `{id}_WARN_MESSAGE`. |
| NAME-DIE-002 | **P2** | **Priority constants pattern diverges from Warn**: Die uses class constants: `PRIORITY_TRACE = 1`, `PRIORITY_DEBUG = 2`, ..., `PRIORITY_FATAL = 6`. Warn uses a list and a dict: `VALID_PRIORITIES = [1, 2, 3, 4, 5, 6]`, `PRIORITY_NAMES = {1: 'trace', 2: 'debug', ...}`. Both represent the same conceptual mapping but with different code structures. This divergence makes maintenance harder -- if the priority mapping changes, both files must be updated independently. Should share a common constants module or base class mixin. |
| NAME-DIE-003 | **P2** | **Non-standard JOB_ERROR_MESSAGE and JOB_EXIT_CODE keys**: Die stores `JOB_ERROR_MESSAGE` and `JOB_EXIT_CODE` in globalMap (lines 157-158). These are not Talend-standard keys. While they are useful v1 extensions (providing job-level error information), any converted Talend logic referencing standard key names will not find them. The keys should be documented as v1-specific extensions. |

### 6.4 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-DIE-001 | **P2** | "`_validate_config()` returns `List[str]`" | Method exists and correctly returns `List[str]`, but is never called. The validation contract is technically met but functionally useless. Dead code provides false confidence that configurations are validated. |
| STD-DIE-002 | **P2** | "Every component MUST have its own `parse_*` method" | Uses deprecated `_map_component_parameters()` instead of a dedicated `parse_tdie()` method. However, for tDie's simple 4-parameter set, the `_map_component_parameters` approach covers all needed parameters except EXIT_JVM. A dedicated parser would only be needed to extract EXIT_JVM and handle expressions in CODE/PRIORITY fields. |

### 6.5 Debug Artifacts

No debug artifacts (stale comments, `# ...existing code...` markers, `print()` statements) were found in `die.py`. The code is clean of development residue.

### 6.6 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-DIE-001 | **P3** | **No message sanitization**: The die message is logged and stored in globalMap without sanitization. If the message contains sensitive data from context variables (e.g., `${context.db_password}`), it will appear in log output and globalMap. This is not a concern for Talend-converted jobs where messages are developer-controlled, but noted for defense-in-depth. |

### 6.7 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start (line 122), priority-based for die message (lines 142-149), ERROR for unexpected failures (line 181) -- mostly correct but trace/debug/info mapping is collapsed (see ENG-DIE-007) |
| Start/complete logging | `_process()` logs start at line 122 (`Processing started: terminating job execution`). No explicit "complete" log since the method always raises an exception, which is logged by the base class. Acceptable for a termination component. |
| Sensitive data | Die message content is logged, which could contain sensitive data from context variables. See SEC-DIE-001. |
| No print statements | No `print()` calls -- correct |
| Log message format consistency | All messages follow the `[{self.id}] Action: detail` pattern. Consistent with other components. |

### 6.8 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ComponentExecutionError` from `exceptions.py` -- correct. `ComponentExecutionError` takes `component_id`, `message`, and optional `cause` parameters. |
| Exception chaining | Line 182: `raise ComponentExecutionError(self.id, f"Die component failed: {e}", e) from e` -- correct `from e` chaining for unexpected errors |
| Re-raise pattern | Lines 177-179: `except ComponentExecutionError: raise` -- correctly re-raises the intentional termination exception without wrapping it in another exception. This preserves the monkey-patched `exit_code` attribute. |
| Exception attribute monkey-patching | Line 174: `error.exit_code = exit_code` -- dynamically adds `exit_code` to the `ComponentExecutionError` instance. This is a Python anti-pattern. `ComponentExecutionError` does not declare `exit_code` in its `__init__()` or class body. Any static type checker (mypy, pyright) would flag `error.exit_code` as an undefined attribute. Should be a constructor parameter or a dedicated `DieException` subclass. |
| Error messages | Include component ID (via `ComponentExecutionError.__init__`), message text, and exit code in the formatted string -- clear and diagnostic |
| Separation of concerns | The `try/except` structure (lines 124-182) correctly separates intentional `ComponentExecutionError` (re-raised at line 179) from unexpected exceptions (wrapped at line 182). This prevents unexpected errors from being treated as intentional die events. |

### 6.9 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints: `_validate_config() -> List[str]`, `_process(...) -> Dict[str, Any]`, `_resolve_global_map_variables(...) -> str` -- correct |
| Parameter types | `_process()` has `input_data: Optional[pd.DataFrame] = None` -- correct |
| Complex types | Uses `Dict[str, Any]`, `List[str]`, `Optional[pd.DataFrame]` from `typing` -- correct |
| Missing hints | No missing type hints detected. All public and private methods are annotated. |
| Class attributes | Priority constants are plain `int` assignments without type annotations -- acceptable for constants but could use `Final[int]` from `typing` for clarity |
| Import completeness | `from typing import Any, Dict, List, Optional` -- all used types are imported. `pd` imported from pandas. `re` imported for regex. |

### 6.10 Comparison with Warn (Sister Component)

Die and Warn share nearly identical patterns but have diverged in implementation details. This comparison highlights inconsistencies that should be unified:

| Aspect | Die (die.py) | Warn (warn.py) | Assessment |
|--------|-----|------|------------|
| Message resolution | Two separate steps: `context_manager.resolve_string()` (line 133) then `_resolve_global_map_variables()` (line 137) | Single method: `_resolve_message_variables()` (line 164) combining both | Warn's single-method approach is cleaner, more maintainable, and easier to test. Die should adopt the same pattern. |
| Priority mapping | All levels <= 3 mapped to `logger.info()` (line 142-143) | Separate handling for trace (debug+prefix), debug, info, warn, error, fatal (lines 193-204) | **Warn is more correct.** Die's collapsed mapping loses the distinction between trace, debug, and info. |
| globalMap key names | `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY`, `{id}_EXIT_CODE`, `JOB_ERROR_MESSAGE`, `JOB_EXIT_CODE` | `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY` | Die stores 6 variables; Warn stores 3. Both miss the Talend `DIE_`/`WARN_` prefix in key names. |
| globalMap regex | `r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'` (line 198) | Identical pattern (line 177) | Both have the same limitation (Integer-cast only). Should be shared code. |
| _validate_config | Present (lines 67-107), never called | Present (lines 59-96), never called | Both dead code. Same structural issue. |
| int conversion safety | `code` and `priority` read from config with `self.config.get()` and used directly -- no `int()` conversion in `_process()` | `code` and `priority` explicitly converted via `try: int(code) except: default` (lines 121-134) | **Warn is safer.** Die trusts that the converter produced ints, but config values could be strings (e.g., from JSON) or floats. Warn defensively converts. |
| Output behavior | Always raises `ComponentExecutionError` (no return value) | Returns `{'main': input_data}` (pass-through) | Correct behavioral difference -- Die terminates, Warn continues. |
| Error wrapping | Unexpected errors wrapped in `ComponentExecutionError` with cause | Same pattern | Consistent -- good. |
| Docstring completeness | Comprehensive class docstring (57 lines, lines 20-57) | Comprehensive class docstring (54 lines, lines 18-53) | Both excellent -- complete config description, inputs, outputs, statistics, example, notes. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-DIE-001 | **P3** | **Regex compiled on every call**: `_resolve_global_map_variables()` uses `re.sub(pattern, replace_func, message)` which compiles the regex pattern on every invocation. For a component that executes at most once per job and then terminates it, this is completely negligible. However, as a matter of code hygiene, the pattern could be pre-compiled as a class-level constant: `_GLOBAL_MAP_PATTERN = re.compile(r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)')`. This would also serve as documentation of the expected pattern. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Component weight | Very lightweight -- no DataFrames created, no large data structures allocated |
| Input handling | Input DataFrame (if any) is used only for `len()` count (line 162). It is never copied, transformed, or stored. The reference is not held beyond the `_update_stats()` call. |
| GlobalMap storage | Stores 6-8 small scalar values (strings and integers) -- negligible memory impact |
| Exception object | `ComponentExecutionError` is a small object with a string message and optional cause reference -- negligible |
| Regex overhead | Single `re.sub()` call on a typically short message string -- negligible |
| Logging overhead | Multiple `logger.info()` / `logger.error()` calls -- negligible for a once-per-job component |

**Overall**: Die is inherently lightweight. It processes no data, creates no DataFrames, performs no I/O (other than logging), and terminates immediately. Performance is not a concern for this component. The entire execution (config reading, message resolution, globalMap storage, stats update, exception creation) takes microseconds.

### 7.2 Execution Time Characteristics

| Phase | Operations | Estimated Time |
|-------|-----------|----------------|
| Config reading | 4x `dict.get()` | < 1 microsecond |
| Context resolution | `resolve_string()` with regex | < 100 microseconds |
| GlobalMap resolution | `re.sub()` with regex | < 100 microseconds |
| Logging | 2-3 `logger.*()` calls | < 1 millisecond |
| GlobalMap storage | 6-8 `global_map.put()` calls | < 100 microseconds |
| Stats update | `_update_stats()` call | < 10 microseconds |
| Exception creation | `ComponentExecutionError()` constructor | < 10 microseconds |
| **Total** | | **< 2 milliseconds** |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `Die` v1 engine component. Searched `tests/v1/`, `tests/v1/unit/`, `tests/v1/integration/`. |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests for Die in a multi-component job flow. |
| Converter unit tests | **No** | -- | No converter unit test verifies the `_map_component_parameters()` output for tDie. The existing converter test suite does not cover tDie parameter extraction. |
| Existing test references | **Minimal** | `tests/*/integration/test_die_on_error.py` | This tests `die_on_error` behavior in file input components, NOT the tDie/Die control component itself. Not relevant to the Die engine component. |

**Key finding**: The v1 engine has ZERO tests for this component. All 205 lines of v1 engine code are completely unverified. The cross-cutting base class bugs (BUG-DIE-001, BUG-DIE-002) strongly suggest that no component in the v1 engine has been tested with a live `global_map` instance -- these bugs would have been caught immediately by any test that provides a GlobalMap.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description | Validates |
|----|-----------|----------|-------------|-----------|
| 1 | Basic die with default config | P0 | Create Die component with empty config `{}`. Call `_process(None)`. Verify `ComponentExecutionError` is raised. Verify exception message contains "Job execution stopped" (default message). Verify `error.exit_code == 1` (default). | Core functionality, default behavior |
| 2 | Custom message, code, priority, exit_code | P0 | Config: `{'message': 'Custom error', 'code': 42, 'priority': 6, 'exit_code': 2}`. Call `_process(None)`. Verify exception message contains "Custom error". Verify `error.exit_code == 2`. Verify globalMap contains `{id}_CODE=42`, `{id}_PRIORITY=6`. | Config parameter handling, globalMap storage |
| 3 | Die with input DataFrame | P0 | Pass a 10-row DataFrame as `input_data`. Verify stats: `NB_LINE=10`, `NB_LINE_OK=0`, `NB_LINE_REJECT=10`. Verify exception is still raised. | Input handling, statistics |
| 4 | Die without input data (None) | P0 | Call with `input_data=None`. Verify stats: `NB_LINE=1`, `NB_LINE_OK=0`, `NB_LINE_REJECT=1`. | No-input behavior, statistics |
| 5 | Die with empty DataFrame | P0 | Call with `input_data=pd.DataFrame()`. Verify stats: `NB_LINE=1`, `NB_LINE_OK=0`, `NB_LINE_REJECT=1` (empty DF treated same as None). | Edge case: empty input |
| 6 | GlobalMap variable storage completeness | P0 | Provide a `GlobalMap` instance. Execute Die. After exception, verify all 8 expected globalMap keys: `{id}_MESSAGE`, `{id}_CODE`, `{id}_PRIORITY`, `{id}_EXIT_CODE`, `JOB_ERROR_MESSAGE`, `JOB_EXIT_CODE`, plus base-class stats `{id}_NB_LINE`, `{id}_NB_LINE_OK`, `{id}_NB_LINE_REJECT`. (Note: requires fixing BUG-DIE-001 and BUG-DIE-002 first.) | GlobalMap integration |
| 7 | Engine-level Die handling | P0 | Build a minimal job config with one Die component. Execute via `ETLEngine.execute()`. Verify returned dict has `status='error'`. Verify the error message contains the die message. Verify no components after Die executed. | Engine integration, job termination |

#### P1 -- Important

| # | Test Case | Priority | Description | Validates |
|----|-----------|----------|-------------|-----------|
| 8 | Context variable in message | P1 | Config: `{'message': '${context.error_details}'}`. Provide ContextManager with `error_details='file not found'`. Execute Die. Verify exception message contains "file not found". | Context variable resolution |
| 9 | globalMap variable in message (Integer cast) | P1 | Config: `{'message': 'Processed ((Integer)globalMap.get("row_count")) rows'}`. Provide GlobalMap with `row_count=500`. Execute Die. Verify exception message contains "Processed 500 rows". (Requires fixing BUG-DIE-002 first.) | globalMap resolution |
| 10 | globalMap variable in message (missing key) | P1 | Config: `{'message': 'Count: ((Integer)globalMap.get("missing_key"))'}`. Provide GlobalMap with no `missing_key`. Execute Die. Verify behavior (currently defaults to 0 -- verify this is intentional or document the gap). | Missing key handling |
| 11 | Priority logging levels | P1 | Execute Die with each priority 1-6 and verify the correct Python logging level is used: 1->debug(TRACE), 2->debug, 3->info, 4->warning, 5->error, 6->critical. (Currently 1-3 all map to info -- test documents the current incorrect behavior.) | Priority mapping |
| 12 | Invalid priority value | P1 | Config: `{'priority': 99}`. Execute Die. Verify component does not crash. Verify it logs at the fallback level (currently `critical` since `99 > 6`). | Edge case: out-of-range priority |
| 13 | Invalid code as string | P1 | Config: `{'code': 'abc'}`. Execute Die. Verify either: (a) `_validate_config()` catches it (if wired up), or (b) the component handles gracefully with a default. Currently, the `int()` conversion is only in the converter, not the engine -- the engine stores whatever was in config. | Type safety |
| 14 | Empty message | P1 | Config: `{'message': ''}`. Execute Die. Verify exception is raised with the empty message (not a fallback). Verify exception string is still meaningful: `"Job terminated:  (exit code: 1)"`. | Edge case: empty message |
| 15 | None message | P1 | Config: `{'message': None}`. Execute Die. Verify component handles None gracefully (the code checks `isinstance(message, str)` before resolving). | Edge case: null message |
| 16 | Die in multi-component job | P1 | Job config: `tRowGenerator -> (OnSubjobOk) -> tDie`. Execute via ETLEngine. Verify tRowGenerator executes successfully, tDie fires, job terminates with error status, and tRowGenerator's stats are preserved in the returned stats dict. | Multi-component integration |
| 17 | Die with OnComponentError trigger | P1 | Job config: `tFileInputDelimited (missing file, die_on_error=true) -> (OnComponentError) -> tDie`. Execute via ETLEngine. Verify the file component fails, the trigger activates tDie, and tDie fires. | Trigger integration |
| 18 | Java expression in message | P1 | Config with `{{java}}` prefix: `{'message': '{{java}}"Error at " + context.step'}`. Verify `_resolve_java_expressions()` is called before `_process()`. (Requires Java bridge mock or integration.) | Java expression support |
| 19 | exit_code attribute on exception | P1 | Execute Die with `exit_code=42`. Catch the `ComponentExecutionError`. Verify `hasattr(error, 'exit_code')` is True. Verify `error.exit_code == 42`. Verify `error.component_id` matches the Die component ID. | Exception attribute verification |

#### P2 -- Hardening

| # | Test Case | Priority | Description | Validates |
|----|-----------|----------|-------------|-----------|
| 20 | Multiple globalMap variables in message | P2 | Message with two `((Integer)globalMap.get("x"))` references. Verify both are resolved independently. | Multiple resolution |
| 21 | Non-Integer globalMap cast in message | P2 | Message with `((String)globalMap.get("key"))`. Verify the regex does NOT match and the expression is left as literal text. Document this as expected current behavior. | Negative test: unsupported cast |
| 22 | Very large exit_code | P2 | `exit_code=999`. Verify the value is stored in globalMap and attached to exception (even though > 255 is not POSIX-valid). | Edge case: large exit code |
| 23 | Zero exit_code | P2 | `exit_code=0`. Verify the exception still fires (0 is a valid exit code in the Die context, even though it means "success" in POSIX). | Edge case: zero exit code |
| 24 | Negative exit_code | P2 | `exit_code=-1`. Verify behavior (likely stored as-is since `_validate_config()` is not called). | Edge case: negative exit code |
| 25 | Die after iterate component | P2 | Job with `tFileList -> (iterate) -> subjob -> tDie`. Verify Die terminates the job mid-iteration. | Iteration interruption |
| 26 | Die with both context and globalMap vars in message | P2 | Message: `"Error processing ${context.filename}: ((Integer)globalMap.get("row_count")) rows failed"`. Verify both are resolved correctly. | Combined resolution |
| 27 | Die component ID in exception | P2 | Verify the `ComponentExecutionError` includes the component ID in both `error.component_id` attribute and the string representation `str(error)`. | Exception completeness |
| 28 | Stats not accumulated across calls | P2 | Call `_process()` twice (catching the first exception). Verify stats are accumulated (NB_LINE increases). This tests whether Die can be used in a retry pattern (unusual but possible). | Stats accumulation |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-DIE-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. For Die, crashes in the exception handler path, replacing the Die error with a NameError. |
| BUG-DIE-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. Die's `_resolve_global_map_variables()` calls `self.global_map.get(key, 0)` which passes 2 args to a 1-arg method, crashing globalMap resolution. |
| TEST-DIE-001 | Testing | Zero v1 unit tests for the Die component. All 205 lines of v1 engine code are unverified. Cross-cutting base class bugs prove no component has been tested with a live GlobalMap instance. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| ENG-DIE-001 | Engine | globalMap regex only handles `(Integer)` cast. `(String)`, `(Long)`, `(Float)`, and uncast `globalMap.get()` are silently left as literal text in the message. |
| ENG-DIE-002 | Engine | No tLogCatcher integration. Die messages cannot be captured in a structured DataFrame for downstream processing. Breaks `tDie -> tLogCatcher -> tFileOutputDelimited` pattern. |
| ENG-DIE-003 | Engine | No EXIT_JVM / `sys.exit()` support. Process exit code is always 0, breaking scheduler and shell integration for EXIT_JVM=true jobs. |
| ENG-DIE-004 | Engine | No tPostJob execution after Die. When Die fires, no cleanup code runs. Breaks connection closing, temp file deletion, notification patterns. |
| BUG-DIE-003 | Bug | globalMap regex `(\w+)` does not match keys with dots or hyphens. Custom globalMap keys with non-word characters are silently ignored. |
| BUG-DIE-004 | Bug | `_validate_config()` is dead code -- never called. 40 lines of unreachable validation. Invalid configs not caught until runtime. |
| BUG-DIE-005 | Bug | `exit_code` dynamically attached to exception is never used to set process exit code. `run_job()` and `__main__` both ignore it. The entire exit_code propagation mechanism is inert. |
| TEST-DIE-002 | Testing | No integration test for Die in a multi-component v1 job with triggers. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-DIE-001 | Converter | Default CODE mismatch: converter defaults to `1`, Talend defaults to `0`. |
| CONV-DIE-002 | Converter | Default PRIORITY mismatch: converter defaults to `5` (error), Talend defaults to `0`. |
| CONV-DIE-003 | Converter | EXIT_JVM parameter not extracted from Talend XML. |
| CONV-DIE-004 | Converter | EXIT_CODE field may not exist in standard Talend XML; always falls back to default `1`. Engine should use `code` as exit code. |
| CONV-DIE-005 | Converter | `.isdigit()` rejects expressions in CODE/PRIORITY/EXIT_CODE fields; expressions silently lost. |
| ENG-DIE-005 | Engine | Double context resolution: message resolved in `execute()` and again in `_process()`. Harmless for simple cases; edge case for templated variables. |
| ENG-DIE-006 | Engine | `globalMap.get(key, 0)` calls a broken method (BUG-DIE-002) and defaults missing keys to `0`, silently masking missing variable errors. |
| ENG-DIE-007 | Engine | Priority levels 1-3 (trace, debug, info) all mapped to `logger.info()`. Should distinguish each level. Warn component does this correctly. |
| NAME-DIE-001 | Naming | globalMap key names use `{id}_MESSAGE` instead of Talend's `{id}_DIE_MESSAGE`. Downstream references fail. |
| NAME-DIE-002 | Naming | Priority constants pattern differs from Warn: Die uses class constants, Warn uses dict. Should share common code. |
| NAME-DIE-003 | Naming | Non-standard `JOB_ERROR_MESSAGE` and `JOB_EXIT_CODE` keys in globalMap. Useful v1 extensions but not documented as non-standard. |
| STD-DIE-001 | Standards | `_validate_config()` exists but is never called. Dead validation code. |
| STD-DIE-002 | Standards | Uses deprecated `_map_component_parameters()` approach instead of dedicated `parse_tdie()` method. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| ENG-DIE-008 | Engine | `{id}_EXIT_CODE` is a non-standard globalMap variable not present in Talend. |
| PERF-DIE-001 | Performance | Regex compiled on every `_resolve_global_map_variables()` call. Negligible for a once-per-job component. |
| SEC-DIE-001 | Security | No message sanitization -- sensitive context variable values could appear in logs and globalMap. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 8 | 4 engine, 3 bugs, 1 testing |
| P2 | 13 | 5 converter, 3 engine, 3 naming, 2 standards |
| P3 | 3 | 1 engine, 1 performance, 1 security |
| **Total** | **27** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-DIE-001): Change `value` to `stat_value` on `base_component.py` line 304. The current line:
   ```python
   logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} {stat_name}: {value}")
   ```
   Should be:
   ```python
   logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']}")
   ```
   (Remove the stale `{stat_name}: {value}` suffix entirely -- the three main stats are already logged.)
   **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only). **Effort**: 1 line change.

2. **Fix `GlobalMap.get()` bug** (BUG-DIE-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26:
   ```python
   def get(self, key: str, default: Any = None) -> Optional[Any]:
       """Retrieve a value from the global map"""
       return self._map.get(key, default)
   ```
   This fixes both direct `global_map.get(key)` calls (which now get `default=None`) and two-argument calls like Die's `self.global_map.get(key, 0)` and `get_component_stat()`'s `self.get(key, default)`.
   **Impact**: Fixes ALL components and all code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default). **Effort**: 1 line change.

3. **Create unit test suite** (TEST-DIE-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. Create file `tests/v1/unit/test_die.py`:
   - Test 1: Basic die with default config -> raises ComponentExecutionError
   - Test 2: Custom message/code/priority/exit_code -> correct exception and globalMap
   - Test 3: Die with 10-row DataFrame input -> NB_LINE=10, NB_LINE_OK=0, NB_LINE_REJECT=10
   - Test 4: Die with None input -> NB_LINE=1
   - Test 5: Die with empty DataFrame -> NB_LINE=1
   - Test 6: GlobalMap storage completeness (requires fix #1 and #2 first)
   - Test 7: Engine-level handling -> job returns status='error'
   **Effort**: ~200 lines of test code.

### Short-Term (Hardening)

4. **Expand globalMap regex to handle all cast types** (ENG-DIE-001): Replace the regex in both Die and Warn with:
   ```python
   _GLOBAL_MAP_PATTERN = re.compile(
       r'\(\((?:Integer|String|Long|Float|Double|Object)\)globalMap\.get\("([^"]+)"\)\)'
   )
   ```
   Also add a fallback pattern for uncast references:
   ```python
   _GLOBAL_MAP_UNCAST_PATTERN = re.compile(
       r'globalMap\.get\("([^"]+)"\)'
   )
   ```
   Extract this into a shared utility module (e.g., `src/v1/engine/utils/globalmap_resolver.py`) to avoid code duplication between Die and Warn. **Effort**: ~50 lines of shared code + updates to both components.

5. **Fix globalMap variable naming to match Talend** (NAME-DIE-001): Change die.py lines 153-155:
   ```python
   self.global_map.put(f"{self.id}_DIE_MESSAGE", message)
   self.global_map.put(f"{self.id}_DIE_CODE", code)
   self.global_map.put(f"{self.id}_DIE_PRIORITY", priority)
   ```
   Keep the non-standard `JOB_ERROR_MESSAGE` and `JOB_EXIT_CODE` as additional convenience variables. Apply the same fix to Warn (change `_MESSAGE` to `_WARN_MESSAGE`, etc.). **Effort**: 6 line changes across 2 files.

6. **Implement sys.exit() for EXIT_JVM mode** (ENG-DIE-003, BUG-DIE-005, CONV-DIE-003):
   - In converter: Extract `EXIT_JVM` parameter: `'exit_jvm': config_raw.get('EXIT_JVM', False)`
   - In engine: In `engine.execute()` exception handler (line 520), check for `exit_code`:
     ```python
     except Exception as e:
         if hasattr(e, 'exit_code'):
             exit_code = e.exit_code
             stats['exit_code'] = exit_code
         ...
     ```
   - In `__main__` (line 888): `sys.exit(stats.get('exit_code', 1 if stats.get('status') == 'error' else 0))`
   **Effort**: ~15 lines across 3 files.

7. **Fix priority mapping for levels 1-3** (ENG-DIE-007): Replace die.py lines 142-143:
   ```python
   if priority <= self.PRIORITY_INFO:
       logger.info(log_message)
   ```
   With the more granular mapping from Warn:
   ```python
   if priority <= 1:
       logger.debug(f"TRACE: {log_message}")
   elif priority == 2:
       logger.debug(log_message)
   elif priority == 3:
       logger.info(log_message)
   ```
   **Effort**: 4 lines changed.

8. **Wire up `_validate_config()`** (BUG-DIE-004): Add validation call at the beginning of `_process()`:
   ```python
   errors = self._validate_config()
   if errors:
       raise ConfigurationError(self.id, f"Invalid configuration: {'; '.join(errors)}")
   ```
   Also relax the priority validation from 1-6 to 0-6 (Talend allows 0). **Effort**: 5 lines.

9. **Fix converter defaults to match Talend** (CONV-DIE-001, CONV-DIE-002): In component_parser.py lines 264-265:
   ```python
   'code': int(config_raw.get('CODE', '0')) if str(config_raw.get('CODE', '0')).isdigit() else 0,
   'priority': int(config_raw.get('PRIORITY', '0')) if str(config_raw.get('PRIORITY', '0')).isdigit() else 0,
   ```
   **Effort**: 2 lines changed.

10. **Fix EXIT_CODE to default from CODE** (CONV-DIE-004): The exit code should default to the error code value, not a hardcoded `1`:
    ```python
    code_val = int(config_raw.get('CODE', '0')) if str(config_raw.get('CODE', '0')).isdigit() else 0
    return {
        'message': config_raw.get('MESSAGE', 'Job execution stopped'),
        'code': code_val,
        'priority': ...,
        'exit_code': int(config_raw.get('EXIT_CODE', str(code_val))) if str(config_raw.get('EXIT_CODE', str(code_val))).isdigit() else code_val
    }
    ```
    **Effort**: 5 lines changed.

### Long-Term (Feature Complete)

11. **Create dedicated `DieException` class**: Add to `exceptions.py`:
    ```python
    class DieException(ComponentExecutionError):
        def __init__(self, component_id: str, message: str, exit_code: int = 1):
            super().__init__(component_id, message)
            self.exit_code = exit_code
    ```
    Update Die component to raise `DieException` instead of monkey-patching `ComponentExecutionError`. Update engine to check `isinstance(e, DieException)` instead of `hasattr(e, 'exit_code')`. **Effort**: ~20 lines across 3 files.

12. **Implement tPostJob execution after Die** (ENG-DIE-004): In `engine.execute()`, when catching the Die exception, execute any tPostJob components before returning:
    ```python
    except Exception as e:
        if hasattr(e, 'exit_code'):
            # Execute tPostJob components before returning
            self._execute_postjob_components()
        ...
    ```
    This requires identifying tPostJob components in the job config and executing them even in the error path. **Effort**: ~50 lines in engine.py.

13. **Implement tLogCatcher** (ENG-DIE-002): Create a `LogCatcher` component that registers as a listener for Die/Warn events. When Die fires, LogCatcher captures a structured row with all 12 fields (moment, pid, root_pid, father_pid, project, job, context, priority, type, origin, message, code) and outputs it as a DataFrame. This enables the standard error-handling pattern. **Effort**: ~200 lines for the LogCatcher component + 50 lines for event registration in the engine.

14. **Handle expressions in CODE/PRIORITY** (CONV-DIE-005): In the converter, detect context variables and Java expressions in CODE, PRIORITY, and EXIT_CODE fields before applying `.isdigit()`. If an expression is detected, preserve it as a string for runtime resolution:
    ```python
    code_raw = config_raw.get('CODE', '0')
    if 'context.' in str(code_raw) or detect_java_expression(str(code_raw)):
        code = code_raw  # Preserve expression for runtime resolution
    elif str(code_raw).isdigit():
        code = int(code_raw)
    else:
        code = 0
    ```
    **Effort**: ~20 lines in converter.

15. **Refactor shared code between Die and Warn**: Extract common functionality into a shared module:
    - `src/v1/engine/components/control/log_component_base.py`: Base class with shared globalMap resolution regex, priority mapping, and variable storage
    - Both Die and Warn inherit from this base class
    - Priority constants, regex patterns, and resolution logic live in one place
    **Effort**: ~100 lines for the base class + refactoring both Die and Warn.

16. **Create integration test** (TEST-DIE-002): Build an end-to-end test exercising `tRowGenerator -> (OnSubjobOk) -> tDie` in the v1 engine:
    - Verify tRowGenerator produces rows
    - Verify OnSubjobOk trigger fires
    - Verify tDie receives the trigger
    - Verify tDie raises exception with correct message
    - Verify engine returns error status
    - Verify tRowGenerator's stats are preserved
    - Verify globalMap contains both tRowGenerator and tDie variables
    **Effort**: ~100 lines of test code.

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 261-267
# Die mapping
elif component_type == 'tDie':
    return {
        'message': config_raw.get('MESSAGE', 'Job execution stopped'),
        'code': int(config_raw.get('CODE', '1')) if str(config_raw.get('CODE', '1')).isdigit() else 1,
        'priority': int(config_raw.get('PRIORITY', '5')) if str(config_raw.get('PRIORITY', '5')).isdigit() else 5,
        'exit_code': int(config_raw.get('EXIT_CODE', '1')) if str(config_raw.get('EXIT_CODE', '1')).isdigit() else 1
    }
```

**Line-by-line analysis**:

- **Line 263** (`message`): `config_raw.get('MESSAGE', 'Job execution stopped')` -- reads the MESSAGE parameter with a helpful default. Talend's actual default is an empty string, but "Job execution stopped" is more diagnostic. The value is a raw string at this point -- context variables and Java expressions are handled later by the generic expression marking step and the engine's resolution logic.

- **Line 264** (`code`): `int(config_raw.get('CODE', '1')) if str(config_raw.get('CODE', '1')).isdigit() else 1` -- attempts to convert CODE to int. The `str()` wrapper handles both string and int inputs. The `.isdigit()` check prevents `int()` from raising on non-numeric strings. Default `'1'` differs from Talend's `'0'`. The `else 1` fallback means any non-digit CODE (including context variables like `context.errorCode`) silently becomes `1`.

- **Line 265** (`priority`): Same pattern as `code`. Default `'5'` maps to "error" severity in v1's convention. Talend default is `'0'`. The `else 5` fallback silently replaces any non-digit priority with 5.

- **Line 266** (`exit_code`): Same pattern. Reads from `EXIT_CODE` parameter which likely does not exist in standard Talend XML (Talend uses `CODE` for both purposes). Always falls back to `1` for real Talend exports. Should default to the `code` value instead.

**Comparison with Warn mapping** (lines 253-258):
```python
# Warn mapping
elif component_type == 'tWarn':
    return {
        'message': config_raw.get('MESSAGE', 'Warning'),
        'code': int(config_raw.get('CODE', '0')) if str(config_raw.get('CODE', '0')).isdigit() else 0,
        'priority': int(config_raw.get('PRIORITY', '4')) if str(config_raw.get('PRIORITY', '4')).isdigit() else 4
    }
```

Die and Warn use the exact same conversion pattern but with different defaults. The pattern could be refactored into a shared helper function:
```python
def _safe_int(config_raw, key, default):
    val = config_raw.get(key, str(default))
    return int(val) if str(val).isdigit() else default
```

---

## Appendix B: Engine Class Structure

```
Die (BaseComponent)
    Imports:
        logging, re, sys
        typing: Any, Dict, List, Optional
        pandas as pd
        BaseComponent (from ...base_component)
        ComponentExecutionError, ConfigurationError (from ...exceptions)

    Constants:
        PRIORITY_TRACE = 1
        PRIORITY_DEBUG = 2
        PRIORITY_INFO = 3
        PRIORITY_WARN = 4
        PRIORITY_ERROR = 5
        PRIORITY_FATAL = 6

    Methods:
        _validate_config() -> List[str]              # Lines 67-107. DEAD CODE -- never called.
        _process(input_data) -> Dict[str, Any]       # Lines 109-182. Main entry -- always raises.
        _resolve_global_map_variables(message) -> str # Lines 184-205. Regex-based resolution.

    Execution flow (detailed):
        1. BaseComponent.__init__() stores config, global_map, context_manager
        2. BaseComponent.execute() is called by ETLEngine._execute_component()
        3. execute() calls _resolve_java_expressions() if java_bridge present (line 198)
           - Scans config for {{java}} markers
           - Sends expressions to Java bridge for evaluation
           - Replaces markers with results
        4. execute() calls context_manager.resolve_dict(config) (line 202)
           - Recursively resolves ${context.var} in ALL config string values
           - MESSAGE is resolved here (first resolution)
        5. execute() calls _execute_batch() -> _process(input_data)
        6. _process() reads message, code, priority, exit_code from config (lines 126-129)
        7. _process() calls context_manager.resolve_string(message) (line 133)
           - MESSAGE resolved again (second, redundant resolution)
        8. _process() calls _resolve_global_map_variables(message) (line 137)
           - Regex replaces ((Integer)globalMap.get("key")) with values
           - Only (Integer) cast is handled
        9. _process() logs message at priority-appropriate level (lines 140-149)
       10. _process() stores 8 variables in globalMap (lines 152-158)
       11. _process() updates stats: NB_LINE, NB_LINE_OK=0, NB_LINE_REJECT (lines 161-167)
       12. _process() creates ComponentExecutionError (line 170-172)
       13. _process() monkey-patches error.exit_code = exit_code (line 174)
       14. _process() raises the exception (line 175)
       15. BaseComponent.execute() catches exception (line 227)
       16. execute() sets status=ERROR, calls _update_global_map() (CRASHES: BUG-DIE-001)
       17. execute() re-raises exception (line 234)
       18. ETLEngine._execute_component() catches exception (line 600)
       19. _execute_component() checks hasattr(e, 'exit_code') (line 605) -> True -> re-raises
       20. ETLEngine.execute() catches exception (line 520)
       21. execute() returns {'status': 'error', 'error': str(e), ...}
       22. exit_code VALUE is NEVER read or acted upon -- process exits with code 0
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Default (Talend) | Default (V1) | Priority to Fix |
|------------------|---------------|--------|------------------|--------------|-----------------|
| `MESSAGE` | `message` | Mapped | `""` (empty) | `"Job execution stopped"` | Low (v1 default is more helpful) |
| `CODE` | `code` | Mapped | `0` | `1` | P2 (fix to match Talend: `0`) |
| `PRIORITY` | `priority` | Mapped | `0` | `5` | P2 (fix to match Talend: `0`) |
| `EXIT_CODE` | `exit_code` | Mapped (synthetic) | N/A (not in Talend XML) | `1` | P2 (should default to `code` value) |
| `EXIT_JVM` | -- | **Not Mapped** | `false` | N/A | P2 (extract and support `sys.exit()`) |
| `TSTATCATCHER_STATS` | -- | Not needed | `false` | N/A | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | `""` | N/A | -- (cosmetic) |

---

## Appendix D: Exception Propagation Diagram

```
Die._process()
    |
    +-- raises ComponentExecutionError (exit_code=N monkey-patched)
    |
    v
BaseComponent.execute() [line 227: except Exception as e]
    |
    +-- self.status = ComponentStatus.ERROR
    +-- self.error_message = str(e)
    +-- self.stats['EXECUTION_TIME'] = elapsed
    +-- self._update_global_map()
    |       |
    |       +-- CRASHES with NameError('value') at line 304
    |       |   (because line 304 uses {value} but loop variable is stat_value)
    |       |
    |       +-- If crash were fixed: logs stats and stores in globalMap
    |
    +-- logger.error(f"Component {self.id} execution failed: {e}")
    +-- raise  (re-raises original ComponentExecutionError with exit_code attr)
    |
    v
ETLEngine._execute_component() [line 600: except Exception as e]
    |
    +-- logger.error(f"Component {comp_id} failed: {str(e)}")
    +-- hasattr(e, 'exit_code')?
    |       |
    |       +-- YES: raise e  (line 607 -- stop the job)
    |       +-- NO:  mark component as failed, continue execution
    |
    v (YES path)
ETLEngine.execute() [line 520: except Exception as e]
    |
    +-- logger.error(f"Job execution failed: {e}")
    +-- self._cleanup()  (cleans up Java bridge, NOT tPostJob)
    +-- return {
    |       'job_name': self.job_name,
    |       'status': 'error',
    |       'error': str(e),       # exit_code is in str(e) as text but NOT extractable
    |       'execution_time': ...,
    |       'components_executed': ...,
    |       'components_failed': ...,
    |       'component_stats': ...  # Die stats may be missing due to BUG-DIE-001
    |   }
    |
    +-- NOTE: e.exit_code is NEVER read here
    +-- NOTE: sys.exit() is NEVER called
    +-- NOTE: tPostJob components are NEVER executed
    |
    v
run_job() [line 857]
    |
    +-- return engine.execute()  (returns the dict -- no exit code handling)
    |
    v
__main__ [line 888]
    |
    +-- print(json.dumps(stats, indent=2))
    +-- (implicit exit with code 0)
    |
    v
PROCESS EXITS WITH CODE 0 (SUCCESS)
    -- exit_code value is LOST
    -- scheduler sees success
    -- shell $? == 0
```

---

## Appendix E: Comparison of Die vs Warn GlobalMap Variables

| Variable | Die Sets | Die Key Name | Warn Sets | Warn Key Name | Talend Standard Key |
|----------|----------|-------------|-----------|--------------|---------------------|
| Message | Yes | `{id}_MESSAGE` | Yes | `{id}_MESSAGE` | `{id}_DIE_MESSAGE` / `{id}_WARN_MESSAGE` |
| Code | Yes | `{id}_CODE` | Yes | `{id}_CODE` | `{id}_DIE_CODE` / `{id}_WARN_CODE` |
| Priority | Yes | `{id}_PRIORITY` | Yes | `{id}_PRIORITY` | `{id}_DIE_PRIORITY` / `{id}_WARN_PRIORITY` |
| Exit Code | Yes | `{id}_EXIT_CODE` | No | -- | N/A (non-standard) |
| Job Error Message | Yes | `JOB_ERROR_MESSAGE` | No | -- | N/A (non-standard) |
| Job Exit Code | Yes | `JOB_EXIT_CODE` | No | -- | N/A (non-standard) |
| NB_LINE | Yes (base) | `{id}_NB_LINE` | Yes (base) | `{id}_NB_LINE` | `{id}_NB_LINE` |
| NB_LINE_OK | Yes (base) | `{id}_NB_LINE_OK` | Yes (base) | `{id}_NB_LINE_OK` | `{id}_NB_LINE_OK` |
| NB_LINE_REJECT | Yes (base) | `{id}_NB_LINE_REJECT` | Yes (base) | `{id}_NB_LINE_REJECT` | `{id}_NB_LINE_REJECT` |

**Key observations**:
1. Both Die and Warn use the same incorrect `{id}_MESSAGE` pattern instead of `{id}_DIE_MESSAGE` / `{id}_WARN_MESSAGE`
2. Die stores 3 additional non-standard variables (`EXIT_CODE`, `JOB_ERROR_MESSAGE`, `JOB_EXIT_CODE`) that Warn does not
3. Base class stats (`NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT`) are stored identically for both, using the correct Talend naming
4. A fix should be applied to both components simultaneously to maintain consistency

---

## Appendix F: globalMap Resolution Regex Analysis

**Current pattern** (die.py line 198):
```python
pattern = r'\(\(Integer\)globalMap\.get\("(\w+)"\)\)'
```

**Regex breakdown**:
- `\(\(` -- literal `((`
- `Integer` -- literal cast type string
- `\)` -- literal `)`
- `globalMap\.get\(` -- literal `globalMap.get(`
- `"` -- literal opening quote
- `(\w+)` -- capture group: one or more word characters `[a-zA-Z0-9_]`
- `"` -- literal closing quote
- `\)\)` -- literal `))`

**What it matches**:
- `((Integer)globalMap.get("tRowGenerator_1_NB_LINE"))` -- YES (standard auto-generated key)
- `((Integer)globalMap.get("count"))` -- YES (simple key)
- `((Integer)globalMap.get("my_var_123"))` -- YES (alphanumeric with underscores)

**What it does NOT match** (all silently left as literal text):
- `((String)globalMap.get("key"))` -- NO (wrong cast type)
- `((Long)globalMap.get("key"))` -- NO (wrong cast type)
- `((Float)globalMap.get("key"))` -- NO (wrong cast type)
- `((Double)globalMap.get("key"))` -- NO (wrong cast type)
- `((Object)globalMap.get("key"))` -- NO (wrong cast type)
- `globalMap.get("key")` -- NO (no cast at all)
- `(String)globalMap.get("key")` -- NO (single parens around cast, non-standard)
- `((Integer)globalMap.get("my.dotted.key"))` -- NO (`\w+` excludes dots)
- `((Integer)globalMap.get("my-hyphen-key"))` -- NO (`\w+` excludes hyphens)
- `((Integer)globalMap.get("key with spaces"))` -- NO (`\w+` excludes spaces)

**Recommended replacement** (handles all cast types and permissive key names):
```python
# Match any standard Java-style cast with globalMap.get
_GLOBAL_MAP_CAST_PATTERN = re.compile(
    r'\(\((?:Integer|String|Long|Float|Double|Object)\)globalMap\.get\("([^"]+)"\)\)'
)

# Also match uncast globalMap.get (less common but possible)
_GLOBAL_MAP_UNCAST_PATTERN = re.compile(
    r'(?<!\()globalMap\.get\("([^"]+)"\)'
)
```

The `[^"]+` capture group matches any key that does not contain a double-quote, which is the only character that would break the globalMap.get() syntax. This covers dotted keys, hyphenated keys, and keys with spaces.

---

## Appendix G: Talend tDie Generated Java Code Pattern

Based on analysis of Talend-generated Java code and community documentation, the typical generated code for a tDie component follows this pattern:

```java
// Generated code for tDie_1
// (simplified from actual Talend output)

// Set globalMap variables
globalMap.put("tDie_1_DIE_MESSAGE", "Job execution stopped");
globalMap.put("tDie_1_DIE_CODE", 1);
globalMap.put("tDie_1_DIE_PRIORITY", 5);

// Throw the die exception
TDieException tDie_1_exception = new TDieException(
    "tDie_1",                    // component name (origin)
    "Job execution stopped",     // message
    1,                           // code
    5                            // priority
);

// If EXIT_JVM is checked:
// Runtime.getRuntime().addShutdownHook(new Thread() {
//     public void run() { /* tPostJob code */ }
// });
// System.exit(1);

// If EXIT_JVM is unchecked:
throw tDie_1_exception;
```

The `TDieException` is a subclass of `TalendException` which is a subclass of `Exception`. The Talend runtime's main processing loop catches `TalendException` and distinguishes:
- `TDieException` -> captured by tLogCatcher (if "Catch tDie" enabled), job terminates
- `TWarnException` -> captured by tLogCatcher (if "Catch tWarn" enabled), job continues
- General `Exception` -> captured by tLogCatcher (if "Catch Java Exception" enabled), behavior depends on die_on_error

**Key differences between Talend and v1**:
1. Talend uses a dedicated `TDieException` class; v1 uses monkey-patched `ComponentExecutionError`
2. Talend sets `tDie_1_DIE_MESSAGE` in globalMap; v1 sets `tDie_1_MESSAGE` (missing `DIE_` prefix)
3. Talend's `System.exit()` sets the process exit code; v1 never calls `sys.exit()`
4. Talend's tPostJob runs via shutdown hook; v1 has no tPostJob lifecycle
5. Talend's tLogCatcher intercepts the exception and builds a 12-field row; v1 has no tLogCatcher

---

## Appendix H: Die Component Full Source Code Walkthrough

### Lines 1-16: Module Setup
```python
"""Die - Stop job execution with error message and optional exit code.
Talend equivalent: tDie"""
import logging, re, sys
from typing import Any, Dict, List, Optional
import pandas as pd
from ...base_component import BaseComponent
from ...exceptions import ComponentExecutionError, ConfigurationError
logger = logging.getLogger(__name__)
```
- Standard imports. Note: `sys` is imported but never used (no `sys.exit()` call). `ConfigurationError` is imported but only used in the type hint context -- `_validate_config()` returns strings, not exceptions.

### Lines 19-57: Class Definition and Docstring
- Comprehensive docstring covering configuration, inputs, outputs, statistics, example, and notes
- Correctly documents the `${context.var}` and `((Integer)globalMap.get("key"))` patterns
- Notes that the component "always raises ComponentExecutionError to terminate job"

### Lines 59-65: Priority Constants
```python
PRIORITY_TRACE = 1
PRIORITY_DEBUG = 2
PRIORITY_INFO = 3
PRIORITY_WARN = 4
PRIORITY_ERROR = 5
PRIORITY_FATAL = 6
```
- Clean constant definitions. Used in `_process()` for logging level dispatch.
- Diverges from Warn's approach (list + dict) but functionally equivalent.

### Lines 67-107: _validate_config() (DEAD CODE)
- Validates code, priority (1-6), exit_code, message types
- Returns `List[str]` of error messages
- **Never called by any code path** -- see BUG-DIE-004

### Lines 109-182: _process() (Main Logic)
- **Lines 122**: Logs start message
- **Lines 126-129**: Reads config with defaults
- **Lines 132-133**: Context variable resolution (REDUNDANT -- already done by base class)
- **Lines 136-137**: globalMap variable resolution (BROKEN -- see BUG-DIE-002)
- **Lines 140-149**: Priority-based logging (IMPRECISE -- see ENG-DIE-007)
- **Lines 152-158**: GlobalMap storage (WRONG KEY NAMES -- see NAME-DIE-001)
- **Lines 161-167**: Statistics update (CORRECT -- all rows counted as rejected)
- **Lines 170-175**: Exception creation and raising (MONKEY-PATCHED exit_code)
- **Lines 177-179**: Re-raise handler for ComponentExecutionError
- **Lines 180-182**: Catch-all handler for unexpected errors

### Lines 184-205: _resolve_global_map_variables()
- Regex-based replacement of `((Integer)globalMap.get("key"))` patterns
- Only handles Integer cast (LIMITATION -- see ENG-DIE-001)
- Uses `\w+` for key matching (LIMITATION -- see BUG-DIE-003)
- Calls `self.global_map.get(key, 0)` which CRASHES due to BUG-DIE-002

---

## Appendix I: Edge Case Analysis

| # | Edge Case | Current Behavior | Expected Behavior | Risk |
|----|-----------|-----------------|-------------------|------|
| 1 | Message is None | `context_manager.resolve_string(None)` returns None. `_resolve_global_map_variables(None)` returns None (regex does not crash on None). Exception message: `"Job terminated: None (exit code: 1)"` | Should use default message or raise ConfigurationError | Low (unusual config) |
| 2 | Message is empty string | Exception message: `"Job terminated:  (exit code: 1)"` (double space before "(exit code"). Logged as empty string. | Acceptable but could add "(no message)" for clarity | Low |
| 3 | Message contains regex special chars | e.g., `"Error: count = ((Integer)globalMap.get("x"))"`. The `re.sub()` handles this correctly because the special chars are in the non-captured part. | No issue. | None |
| 4 | Code is 0 | Stored as `0` in globalMap. Exception message includes `"(exit code: 1)"` (exit_code is separate from code). | Correct. Code 0 is valid in Talend. | None |
| 5 | Code is > 255 | Stored as-is. `_validate_config()` does not check range (and is never called). Process exit code is never set anyway. | Should warn that code > 255 will be truncated on Linux. | Low |
| 6 | Priority is 0 | Maps to `logger.info()` (line 143: `if priority <= self.PRIORITY_INFO`). | Should log at a neutral level. Talend priority 0 has no special meaning. | Low |
| 7 | Priority is > 6 | Maps to `logger.critical()` (line 149: `else` branch). | Acceptable fallback. Could log a warning about non-standard priority. | None |
| 8 | Priority is negative | `int` comparison: `-1 <= 3` is True, so maps to `logger.info()`. | Should reject negative priority or log a warning. | Low |
| 9 | GlobalMap not set (None) | `_resolve_global_map_variables()` returns message unchanged (line 194: `if not self.global_map: return message`). Lines 152-158 are skipped (line 152: `if self.global_map:`). Stats stored in `self.stats` dict only (no globalMap). | Correct. Component works without globalMap. | None |
| 10 | Context manager not set (None) | `context_manager.resolve_string()` is skipped (line 132: `if self.context_manager and isinstance(message, str)`). Context variables in message remain as literal `${context.var}` text. | Correct. Component works without context manager. | None |
| 11 | Input DataFrame has 0 rows (empty) | `input_data.empty` is True. Falls to `else` branch (line 165). Stats: `NB_LINE=1, NB_LINE_OK=0, NB_LINE_REJECT=1`. | Correct. Empty DataFrame treated same as no input. | None |
| 12 | Input DataFrame has millions of rows | `len(input_data)` counted but DataFrame not processed. Stats: `NB_LINE=N, NB_LINE_OK=0, NB_LINE_REJECT=N`. No memory issue. | Correct. Only `len()` is called, not a copy/transform. | None |
| 13 | Message contains both context vars and globalMap refs | `${context.env}: ((Integer)globalMap.get("count")) rows` -> context resolved first by `resolve_string()`, then globalMap resolved by `_resolve_global_map_variables()`. Order is correct. | Correct ordering. Both resolved. | None |
| 14 | globalMap key does not exist | `self.global_map.get(key, 0)` would return 0 if the method worked. Currently CRASHES due to BUG-DIE-002. | Should return 0 (default) after bug fix. Silently masks missing key. | Medium (masked error) |
| 15 | Multiple Die components in same job | Each Die stores variables with its own `{id}` prefix. Only the first Die to execute will fire -- subsequent ones never reach because the job terminates. `JOB_ERROR_MESSAGE` and `JOB_EXIT_CODE` are overwritten by whichever Die fires first. | Correct. Only one Die can fire per job execution. | None |
| 16 | Die triggered by Row Main (data flow) | When Die receives a data flow (not a trigger), `_process()` is called with the DataFrame. The Die fires, counting all input rows as rejected, and raises exception. | Correct. Less common usage than triggers but supported. | None |
| 17 | Die triggered with no upstream data | When Die is triggered via OnSubjobOk or OnComponentOk, `_process()` is called with `input_data=None`. Stats: `NB_LINE=1`. | Correct. The "1" represents the die event itself. | None |
| 18 | Message with newlines | e.g., `"Line 1\nLine 2"`. Logged as-is (Python logging handles newlines). Stored in globalMap as-is. | Correct. Multi-line messages are valid. | None |
| 19 | Message with Unicode | e.g., `"Erreur: fichier introuvable"` with accented characters. Python strings handle Unicode natively. No encoding issue. | Correct. | None |
| 20 | globalMap.get returns non-string value | e.g., `globalMap.get("key")` returns an integer `500`. The `replace_func` calls `str(value)` -> `"500"`. Correctly converts to string for message substitution. | Correct. All types are str()-converted. | None |

---

## Appendix J: Detailed _process() Control Flow

The `_process()` method (die.py lines 109-182) follows a carefully structured control flow. This appendix traces every significant decision point.

```
_process(input_data: Optional[pd.DataFrame] = None)
    |
    +-- logger.info("[{id}] Processing started: terminating job execution")
    |
    +-- try:
    |       |
    |       +-- message = config.get('message', 'Job execution stopped')
    |       +-- code = config.get('code', 1)
    |       +-- priority = config.get('priority', PRIORITY_ERROR)  # = 5
    |       +-- exit_code = config.get('exit_code', 1)
    |       |
    |       +-- if context_manager AND message is str:
    |       |       message = context_manager.resolve_string(message)
    |       |       # Resolves ${context.var} patterns
    |       |       # REDUNDANT: already resolved by execute() at line 202
    |       |
    |       +-- if global_map AND message is str:
    |       |       message = _resolve_global_map_variables(message)
    |       |       # Resolves ((Integer)globalMap.get("key")) patterns
    |       |       # WILL CRASH if message contains globalMap refs (BUG-DIE-002)
    |       |
    |       +-- log_message = "[{id}] Code {code}: {message}"
    |       |
    |       +-- PRIORITY DISPATCH:
    |       |       if priority <= PRIORITY_INFO (3):
    |       |           logger.info(log_message)        # Handles 1, 2, 3 (IMPRECISE)
    |       |       elif priority == PRIORITY_WARN (4):
    |       |           logger.warning(log_message)
    |       |       elif priority == PRIORITY_ERROR (5):
    |       |           logger.error(log_message)
    |       |       else:  # 6+ (PRIORITY_FATAL or higher)
    |       |           logger.critical(log_message)
    |       |
    |       +-- if global_map:
    |       |       global_map.put("{id}_MESSAGE", message)
    |       |       global_map.put("{id}_CODE", code)
    |       |       global_map.put("{id}_PRIORITY", priority)
    |       |       global_map.put("{id}_EXIT_CODE", exit_code)
    |       |       global_map.put("JOB_ERROR_MESSAGE", message)
    |       |       global_map.put("JOB_EXIT_CODE", exit_code)
    |       |
    |       +-- STATS UPDATE:
    |       |       if input_data is not None AND not input_data.empty:
    |       |           rows = len(input_data)
    |       |           _update_stats(rows, 0, rows)     # All rows rejected
    |       |           logger.info("Processed {rows} rows before termination")
    |       |       else:
    |       |           _update_stats(1, 0, 1)            # Count as 1 execution
    |       |           logger.info("No input data - terminating job")
    |       |
    |       +-- EXCEPTION CREATION:
    |       |       error = ComponentExecutionError(
    |       |           self.id,
    |       |           f"Job terminated: {message} (exit code: {exit_code})"
    |       |       )
    |       |       error.exit_code = exit_code    # MONKEY-PATCH
    |       |       raise error
    |       |
    |       +-- except ComponentExecutionError:
    |       |       raise                           # Re-raise die exception
    |       |
    |       +-- except Exception as e:
    |               logger.error("Unexpected error during termination: {e}")
    |               raise ComponentExecutionError(
    |                   self.id, f"Die component failed: {e}", e
    |               ) from e
```

**Key observations from the control flow**:

1. **Config defaults are applied in _process(), not __init__()**: The defaults `message='Job execution stopped'`, `code=1`, `priority=5`, `exit_code=1` are applied each time `_process()` is called. If the component were somehow called multiple times (e.g., in a retry), the defaults would be re-applied. This is correct behavior -- Die should not cache config values.

2. **Context resolution is conditional on context_manager being set**: If no context manager is provided (e.g., in unit tests), context variables in the message remain as literal `${context.var}` text. This is acceptable for testing but could be surprising in production.

3. **GlobalMap resolution is conditional on global_map being set**: If no global_map is provided, `((Integer)globalMap.get("key"))` references remain as literal text. The component gracefully degrades without globalMap.

4. **Exception handling has two layers**: The inner `try/except` catches `ComponentExecutionError` (re-raises it) and generic `Exception` (wraps it). This ensures that:
   - The intentional die exception passes through unchanged
   - Any unexpected error (e.g., in message resolution) is wrapped with context
   - The `from e` chain preserves the original traceback

5. **Stats are updated BEFORE the exception is raised**: Lines 161-167 call `_update_stats()` before line 175 raises the exception. This ensures that even if the exception handler in the base class crashes (BUG-DIE-001), the stats have already been recorded in `self.stats` (though not in globalMap).

---

## Appendix K: Production Deployment Checklist

Before deploying the v1 Die component to production, the following items must be verified:

### Must Fix (P0)

- [ ] **BUG-DIE-001**: Fix `_update_global_map()` undefined variable `value` in base_component.py line 304
- [ ] **BUG-DIE-002**: Fix `GlobalMap.get()` missing `default` parameter in global_map.py line 26
- [ ] **TEST-DIE-001**: Create unit test suite with minimum 7 P0 test cases

### Should Fix (P1)

- [ ] **ENG-DIE-001**: Expand globalMap regex to handle all cast types (String, Long, Float, etc.)
- [ ] **ENG-DIE-003**: Implement `sys.exit(exit_code)` for process exit code propagation
- [ ] **ENG-DIE-004**: Implement tPostJob execution after Die fires
- [ ] **BUG-DIE-004**: Wire up `_validate_config()` to be called from `_process()`
- [ ] **BUG-DIE-005**: Propagate exit_code to `engine.execute()` return dict and `__main__`
- [ ] **NAME-DIE-001**: Fix globalMap key names to match Talend convention (add `DIE_` prefix)

### Recommended Fix (P2)

- [ ] **CONV-DIE-001**: Fix default CODE from 1 to 0
- [ ] **CONV-DIE-002**: Fix default PRIORITY from 5 to 0
- [ ] **CONV-DIE-003**: Extract EXIT_JVM parameter from Talend XML
- [ ] **CONV-DIE-004**: Default EXIT_CODE to CODE value instead of hardcoded 1
- [ ] **ENG-DIE-007**: Fix priority mapping for levels 1-3 to match Warn component

### Verification Steps

1. Run unit tests for Die component (once created)
2. Run all existing v1 engine tests to verify cross-cutting fixes do not regress
3. Execute a sample Talend job containing tDie through the full pipeline (convert -> execute)
4. Verify process exit code is non-zero when Die fires (after fix #6)
5. Verify globalMap contains correct key names (after fix #9)
6. Verify scheduler integration (cron/Airflow) correctly detects job failure (after fix #6)

---

## Appendix L: Related Component Audit Cross-References

| Component | Relationship to tDie | Audit Status | Key Dependencies |
|-----------|---------------------|--------------|------------------|
| **tWarn** | Sister component (logs and continues) | Not yet audited | Shares globalMap regex, priority mapping, message resolution patterns |
| **tLogCatcher** | Captures tDie messages into structured schema | Not implemented in v1 | Would require event listener architecture in engine |
| **tPostjob** | Cleanup code that runs after tDie | Partially implemented | Engine does not execute tPostJob after Die exception |
| **tRunJob** | Parent job that may call a child job containing tDie | Implemented | Die in child job should propagate to parent -- verify |
| **tSleep** | Sometimes used before tDie for delay | Implemented | No direct dependency |
| **tSendMail** | Sometimes triggered after tDie for notification | Implemented | Cannot execute after Die due to ENG-DIE-004 |
| **tJava** | Alternative to tDie using `throw new RuntimeException()` | Implemented | Different exception type -- not detected by `hasattr(e, 'exit_code')` |
| **BaseComponent** | Parent class providing execute(), _update_stats(), _update_global_map() | Audited (cross-cutting bugs found) | BUG-DIE-001 and BUG-DIE-002 originate here |
| **GlobalMap** | Storage for Die variables | Audited (broken get() method) | BUG-DIE-002 makes globalMap resolution non-functional |
| **ContextManager** | Resolves ${context.var} in messages | Not audited | Double resolution concern (ENG-DIE-005) |
| **ETLEngine** | Handles Die exception propagation | Audited (exit_code not propagated) | BUG-DIE-005 makes exit_code inert |

---

## Appendix M: Version History and Change Log

| Date | Version | Change |
|------|---------|--------|
| 2026-03-21 | 1.0 | Initial audit report created. Found 27 issues: 3 P0, 8 P1, 13 P2, 3 P3. |

**Audit methodology**: This report was produced by:
1. Reading the complete source code of `die.py` (205 lines), `warn.py` (214 lines for comparison), `base_component.py` (382 lines), `global_map.py` (87 lines), `exceptions.py` (51 lines), and `engine.py` (lines 42, 175-176, 394-536, 538-620, 832-888)
2. Reading the converter code in `component_parser.py` (lines 83, 253-267) and `converter.py` (lines 216-285)
3. Researching Talend tDie behavior via official documentation ([Talend 7.3](https://help.qlik.com/talend/en-US/components/7.3/logs-and-errors/tdie-standard-properties), [Talend 8.0](https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tdie)), community resources, and generated Java code analysis
4. Searching for existing tests (found zero v1 Die tests)
5. Comparing with the gold standard audit format from `tFileInputDelimited.md`
6. Cross-referencing with the sister component `tWarn` for consistency analysis

---

## Appendix N: Proposed Unit Test Code Skeleton

The following test skeleton covers the 7 P0 test cases and 12 P1 test cases identified in Section 8.2. It demonstrates the expected test patterns and serves as a specification for the test implementer.

```python
# tests/v1/unit/test_die.py
"""Unit tests for the Die component (tDie equivalent)."""
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from src.v1.engine.components.control.die import Die
from src.v1.engine.exceptions import ComponentExecutionError
from src.v1.engine.global_map import GlobalMap
# from src.v1.engine.context_manager import ContextManager  # For P1 tests


class TestDieP0:
    """P0 (Critical) test cases -- must pass before production."""

    def test_basic_die_with_default_config(self):
        """Test 1: Die with empty config raises ComponentExecutionError."""
        die = Die(component_id="tDie_1", config={})
        with pytest.raises(ComponentExecutionError) as exc_info:
            die._process(None)
        assert "Job execution stopped" in str(exc_info.value)
        assert hasattr(exc_info.value, 'exit_code')
        assert exc_info.value.exit_code == 1

    def test_custom_message_code_priority_exit_code(self):
        """Test 2: Die with custom config propagates all values correctly."""
        config = {
            'message': 'Custom error occurred',
            'code': 42,
            'priority': 6,
            'exit_code': 2
        }
        die = Die(component_id="tDie_1", config=config)
        with pytest.raises(ComponentExecutionError) as exc_info:
            die._process(None)
        assert "Custom error occurred" in str(exc_info.value)
        assert exc_info.value.exit_code == 2

    def test_die_with_input_dataframe(self):
        """Test 3: Die with 10-row input counts all rows as rejected."""
        die = Die(component_id="tDie_1", config={'message': 'Error'})
        input_df = pd.DataFrame({'col1': range(10)})
        with pytest.raises(ComponentExecutionError):
            die._process(input_df)
        assert die.stats['NB_LINE'] == 10
        assert die.stats['NB_LINE_OK'] == 0
        assert die.stats['NB_LINE_REJECT'] == 10

    def test_die_without_input_data(self):
        """Test 4: Die with None input counts as 1 execution."""
        die = Die(component_id="tDie_1", config={'message': 'Error'})
        with pytest.raises(ComponentExecutionError):
            die._process(None)
        assert die.stats['NB_LINE'] == 1
        assert die.stats['NB_LINE_OK'] == 0
        assert die.stats['NB_LINE_REJECT'] == 1

    def test_die_with_empty_dataframe(self):
        """Test 5: Die with empty DataFrame treated as no input."""
        die = Die(component_id="tDie_1", config={'message': 'Error'})
        with pytest.raises(ComponentExecutionError):
            die._process(pd.DataFrame())
        assert die.stats['NB_LINE'] == 1
        assert die.stats['NB_LINE_OK'] == 0
        assert die.stats['NB_LINE_REJECT'] == 1

    def test_globalmap_variable_storage(self):
        """Test 6: Die stores all expected variables in GlobalMap.
        NOTE: Requires BUG-DIE-001 and BUG-DIE-002 to be fixed first.
        """
        gm = GlobalMap()
        config = {
            'message': 'Test error',
            'code': 99,
            'priority': 5,
            'exit_code': 3
        }
        die = Die(component_id="tDie_1", config=config, global_map=gm)
        with pytest.raises(ComponentExecutionError):
            die._process(None)
        # Verify component-specific variables
        assert gm._map.get("tDie_1_MESSAGE") == "Test error"
        assert gm._map.get("tDie_1_CODE") == 99
        assert gm._map.get("tDie_1_PRIORITY") == 5
        assert gm._map.get("tDie_1_EXIT_CODE") == 3
        # Verify job-level variables
        assert gm._map.get("JOB_ERROR_MESSAGE") == "Test error"
        assert gm._map.get("JOB_EXIT_CODE") == 3

    def test_engine_level_die_handling(self):
        """Test 7: Engine returns error status when Die fires.
        This is an integration-level test using ETLEngine.
        """
        # Requires a minimal job config JSON with a single Die component
        # Implementation deferred to integration test suite
        pass


class TestDieP1:
    """P1 (Major) test cases -- important for reliability."""

    def test_context_variable_in_message(self):
        """Test 8: Context variables in message are resolved."""
        ctx = MagicMock()
        ctx.resolve_string.return_value = "file not found"
        config = {'message': '${context.error_details}'}
        die = Die(component_id="tDie_1", config=config, context_manager=ctx)
        with pytest.raises(ComponentExecutionError) as exc_info:
            die._process(None)
        assert "file not found" in str(exc_info.value)

    def test_globalmap_integer_variable_in_message(self):
        """Test 9: ((Integer)globalMap.get("key")) resolved in message.
        NOTE: Requires BUG-DIE-002 to be fixed first.
        """
        gm = GlobalMap()
        gm.put("row_count", 500)
        config = {'message': 'Processed ((Integer)globalMap.get("row_count")) rows'}
        die = Die(component_id="tDie_1", config=config, global_map=gm)
        with pytest.raises(ComponentExecutionError) as exc_info:
            die._process(None)
        assert "Processed 500 rows" in str(exc_info.value)

    def test_globalmap_missing_key_defaults_to_zero(self):
        """Test 10: Missing globalMap key defaults to 0.
        NOTE: Requires BUG-DIE-002 to be fixed first.
        """
        gm = GlobalMap()
        config = {'message': 'Count: ((Integer)globalMap.get("missing_key"))'}
        die = Die(component_id="tDie_1", config=config, global_map=gm)
        with pytest.raises(ComponentExecutionError) as exc_info:
            die._process(None)
        assert "Count: 0" in str(exc_info.value)

    def test_priority_logging_levels(self):
        """Test 11: Each priority maps to the correct logging level."""
        expected_levels = {
            1: 'debug',     # TRACE -> debug (currently mapped to info - BUG)
            2: 'debug',     # DEBUG -> debug (currently mapped to info - BUG)
            3: 'info',      # INFO -> info
            4: 'warning',   # WARN -> warning
            5: 'error',     # ERROR -> error
            6: 'critical',  # FATAL -> critical
        }
        for priority, expected_level in expected_levels.items():
            config = {'message': f'Priority {priority} test', 'priority': priority}
            die = Die(component_id="tDie_1", config=config)
            with pytest.raises(ComponentExecutionError):
                with patch('src.v1.engine.components.control.die.logger') as mock_logger:
                    die._process(None)
                    # Verify the correct log method was called
                    log_method = getattr(mock_logger, expected_level)
                    assert log_method.called, (
                        f"Priority {priority} should log at {expected_level}"
                    )

    def test_invalid_priority_value(self):
        """Test 12: Priority 99 does not crash the component."""
        config = {'message': 'High priority', 'priority': 99}
        die = Die(component_id="tDie_1", config=config)
        with pytest.raises(ComponentExecutionError):
            die._process(None)
        # Should not crash -- priority 99 > 6, maps to critical

    def test_empty_message(self):
        """Test 14: Empty message still raises exception."""
        config = {'message': ''}
        die = Die(component_id="tDie_1", config=config)
        with pytest.raises(ComponentExecutionError) as exc_info:
            die._process(None)
        assert "Job terminated" in str(exc_info.value)

    def test_none_message(self):
        """Test 15: None message handled gracefully."""
        config = {'message': None}
        die = Die(component_id="tDie_1", config=config)
        with pytest.raises(ComponentExecutionError):
            die._process(None)
        # Should not crash -- isinstance(None, str) is False, skip resolution

    def test_exit_code_attribute_on_exception(self):
        """Test 19: exit_code attribute is correctly attached."""
        config = {'exit_code': 42}
        die = Die(component_id="tDie_1", config=config)
        with pytest.raises(ComponentExecutionError) as exc_info:
            die._process(None)
        error = exc_info.value
        assert hasattr(error, 'exit_code')
        assert error.exit_code == 42
        assert error.component_id == "tDie_1"
```

**Notes on the test skeleton**:
- Tests that require BUG-DIE-001 or BUG-DIE-002 fixes are annotated with `NOTE:` comments
- Test 7 (engine-level) is deferred to the integration test suite since it requires a full ETLEngine setup
- Test 11 (priority logging) uses `unittest.mock.patch` to intercept logger calls
- Tests use `_process()` directly rather than `execute()` to isolate Die-specific logic from base class behavior
- For tests involving `execute()`, the base class bugs must be fixed first
- The `GlobalMap` instance is accessed via `gm._map` (internal dict) because `gm.get()` is broken (BUG-DIE-002)

---

## Appendix O: Talend Job Patterns Using tDie

### Pattern 1: Validation Gate
```
tRowGenerator_1 --[OnSubjobOk]--> tDie_1 (condition: NB_LINE == 0)
```
Die message: `"No rows generated by source. Job cannot continue."`
Use case: Terminate the job if a critical data source produces no rows.

### Pattern 2: Error Escalation
```
tFileInputDelimited_1 --[OnComponentError]--> tDie_1
```
Die message: `"Failed to read input file: " + ((String)globalMap.get("tFileInputDelimited_1_ERROR_MESSAGE"))`
Use case: Escalate file read errors to job-level termination with a descriptive message.

### Pattern 3: Conditional Termination with Logging
```
tDie_1 <--[If: condition]-- tFlowToIterate_1
    |
tLogCatcher_1 --[Row]--> tLogRow_1
    |
    +--> tFileOutputDelimited_1 (error log file)
```
Use case: Terminate based on a computed condition, capture the error in a structured log file.

### Pattern 4: Multi-Step Validation Pipeline
```
Step 1: tFileInputDelimited_1 --[OnSubjobOk]--> Step 2
Step 2: tRowCount_1 --[OnSubjobOk]--> Step 3
Step 3: tDie_1 (condition: row_count < threshold)
```
Die message: `"Row count " + ((Integer)globalMap.get("tRowCount_1_NB_LINE")) + " below threshold " + context.min_rows`
Use case: Multi-step validation with tDie as the final gate.

### Pattern 5: Child Job Failure Handling
```
Parent Job:
    tRunJob_1 (child job) --[OnComponentError]--> tDie_1

Child Job:
    tDie_1 (internal validation failure)
```
Use case: When a child job fails (including via its own tDie), the parent job's tDie escalates with additional context.

**How these patterns map to v1**:
- Pattern 1: Supported via trigger connections. Die component works correctly.
- Pattern 2: Supported if `ERROR_MESSAGE` globalMap variable is set by the file component. Currently, the globalMap regex only handles `(Integer)` cast, so `(String)` cast would NOT resolve (ENG-DIE-001).
- Pattern 3: NOT supported. No tLogCatcher in v1 (ENG-DIE-002).
- Pattern 4: Partially supported. Depends on globalMap resolution and context variable support.
- Pattern 5: Partially supported. Depends on tRunJob error propagation (not audited here).
