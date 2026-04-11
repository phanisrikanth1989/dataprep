# Audit Report: tDie / Die

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
| **Talend Name** | `tDie` |
| **V1 Engine Class** | `Die` |
| **Engine File** | `src/v1/engine/components/control/die.py` (205 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/control/die.py` |
| **Converter Dispatch** | `@REGISTRY.register("tDie")` decorator-based dispatch |
| **Registry Aliases** | `Die`, `tDie` |
| **Category** | Control / Logs & Errors |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/control/die.py` | Engine implementation (205 lines) |
| `src/converters/talend_to_v1/components/control/die.py` | Converter class |
| `tests/converters/talend_to_v1/components/test_die.py` | Converter tests |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 6 of 6 Talend params extracted (100%); MESSAGE default "the end is near", CODE default "4", PRIORITY default "5" per _java.xml; 3 per-feature needs_review for engine gaps |
| Engine Feature Parity | **Y** | 0 | 3 | 2 | 1 | Message default mismatch; code default mismatch; EXIT_JVM not supported; phantom exit_code param; no tLogCatcher integration |
| Code Quality | **Y** | 1 | 1 | 1 | 1 | Cross-cutting `_update_global_map()` crash bug; `_validate_config()` dead code; narrow globalMap regex pattern; good logging |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | Terminates job immediately; regex recompilation on every call |
| Testing | **G** | 0 | 0 | 0 | 0 | Comprehensive converter tests covering all params, defaults, needs_review, phantom params |

**Overall: YELLOW -- Engine gaps and cross-cutting bugs prevent production readiness**

**Top Actions**:

1. Fix engine message default "Job execution stopped" to match Talend "the end is near"
2. Fix engine code default 1 to match Talend 4
3. Implement EXIT_JVM support in engine
4. Fix cross-cutting `_update_global_map()` crash bug
5. Add engine unit tests

---

## 3. Talend Feature Baseline

### What tDie Does

`tDie` throws an error and terminates the current job execution with a priority-rated message and error code. It is the hard-stop counterpart to `tWarn` -- while `tWarn` logs a message and continues, `tDie` kills the job immediately. The component is typically used in conjunction with `tLogCatcher` for structured error handling: `tLogCatcher` captures the die message, code, and priority in its structured output schema before the job terminates.

`tDie` cannot be used as a start component in a Talend job. It must be triggered by a preceding component via a Row connection or a trigger (On Component Ok, On Subjob Ok, Run If, etc.). Common use cases include: terminating a job when a critical file is missing, aborting on data quality violations that cannot be recovered, and enforcing business rules that must halt processing when violated.

**Important**: Error codes greater than 255 are incompatible with Linux exit codes. Linux truncates exit codes to 8 bits (0-255), so a die code of 500 would be reported as 244 (500 mod 256) by the operating system. Talend documentation explicitly warns about this limitation.

**Source**: [tDie (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tdie), [Using tDie, tWarn, and tLogCatcher for error handling (Talend 8.0)](https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-07/using-tdie-twarn-and-tlogcatcher-for-error-handling), [Talaxie GitHub tDie_java.xml](https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tDie/tDie_java.xml)
**Component family**: Logs & Errors (Control)
**Available in**: All Talend products (Standard Job framework)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Die Message | `MESSAGE` | TEXT (Expression) | `"the end is near"` | Error message to display when job terminates. Supports context variables, globalMap references, and Java expressions. |
| 2 | Code | `CODE` | TEXT (Integer) | `4` | Numeric error code associated with the die event. Used for programmatic filtering in tLogCatcher. Error codes >255 incompatible with Linux exit codes. |
| 3 | Priority | `PRIORITY` | CLOSED_LIST (Integer) | `5` (ERROR) | Priority level. Items: TRACE(1), DEBUG(2), INFO(3), WARNING(4), ERROR(5), FATAL(6). Same priority scale as tWarn but defaults to ERROR instead of WARNING. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 4 | Exit JVM | `EXIT_JVM` | CHECK (Boolean) | `false` | When true, calls `System.exit()` to terminate the entire JVM process rather than just raising an exception. Used for hard termination when exception-based shutdown is insufficient. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Optional input data rows. Rows are counted as rejected before job terminates. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Never fires -- component always terminates the job. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the die event is caught by tLogCatcher before termination. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Never fires -- component always raises an error. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when the component encounters an unexpected internal error. |

**Usage restriction**: tDie **cannot** be used as a start component. It must be preceded by another component in the flow or triggered via a trigger connection.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `DIE_MESSAGES` | String | After execution | The die message text. Note: plural "MESSAGES" (not "MESSAGE"). |
| `DIE_CODE` | Integer | After execution | The die error code. |
| `DIE_PRIORITY` | Integer | After execution | The die priority level. |
| `{id}_ERROR_MESSAGE` | String | After execution | Error message for this specific component instance. |

### 3.5 Behavioral Notes

1. **Job termination**: tDie always terminates the job. There is no "continue on error" mode. The component raises an exception that propagates up to the engine's top-level handler. This is fundamentally different from tWarn which continues execution.

2. **Priority defaults differ from tWarn**: tDie defaults to priority 5 (ERROR) while tWarn defaults to priority 4 (WARNING). This reflects their different severity levels -- dying is more severe than warning.

3. **EXIT_JVM behavior**: When `EXIT_JVM=true`, Talend calls `System.exit()` which terminates the entire JVM process immediately. This bypasses all finally blocks, tPostjob components, and tLogCatcher. Use with extreme caution -- it prevents graceful cleanup.

4. **Error codes and Linux**: Talend documentation warns that error codes >255 are incompatible with Linux exit codes. The JVM exit code is masked to 8 bits by the OS. A die code of 500 becomes 244 at the OS level.

5. **tLogCatcher integration**: When tLogCatcher has "Catch tDie" enabled, it captures the die message in a structured schema with fields for moment, pid, project, job, context, priority, type, origin, message, and code. The `type` field will be "tDie" to distinguish from tWarn messages.

6. **Message expression evaluation**: The MESSAGE field supports full Java expression syntax at runtime, including context variables (`context.var`), globalMap references (`((String)globalMap.get("key"))`), and string concatenation.

7. **Single execution**: Even if tDie receives multiple rows via a Row connection, it terminates on the first invocation. All input rows are counted as rejected in statistics.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a dedicated `DieConverter` class with `@REGISTRY.register("tDie")` decorator-based dispatch. It extracts all 4 unique parameters plus 2 framework parameters using the standard `_get_str` and `_get_bool` helpers from the `ComponentConverter` base class.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `MESSAGE` | Yes | `message` | Default `"the end is near"` per _java.xml |
| 2 | `CODE` | Yes | `code` | Default `"4"` per _java.xml. Extracted as string (TEXT field). |
| 3 | `PRIORITY` | Yes | `priority` | Default `"5"` per _java.xml. Extracted as string (CLOSED_LIST stores integer value). |
| 4 | `EXIT_JVM` | Yes | `exit_jvm` | Default `False` per _java.xml |
| 5 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, default `False` |
| 6 | `LABEL` | Yes | `label` | Framework param, default `""` |

**Summary**: 6 of 6 parameters extracted (100%).

### 4.2 Schema Extraction

tDie is a utility/control component -- it has no data flow schema. The converter correctly produces an empty schema: `{"input": [], "output": []}`.

### 4.3 Expression Handling

MESSAGE values containing context variables or Java expressions are passed through as strings. The engine resolves `${context.var}` via ContextManager and globalMap references via regex pattern matching at runtime.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No converter issues. All parameters correctly extracted with correct defaults. |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `message` | Engine default "Job execution stopped" differs from Talend default "the end is near" | engine_gap |
| 2 | `code` | Engine default 1 differs from Talend default 4 | engine_gap |
| 3 | `exit_jvm` | EXIT_JVM parameter not read by engine -- JVM exit behavior not supported | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Die message | **Yes** | Medium | `_process()` line 126 | Default "Job execution stopped" differs from Talend "the end is near" |
| 2 | Error code | **Yes** | Medium | `_process()` line 127 | Default 1 differs from Talend 4 |
| 3 | Priority logging | **Yes** | High | `_process()` lines 140-149 | Priority constants match Talend (1-6). Default 5 matches Talend ERROR. |
| 4 | EXIT_JVM | **No** | N/A | -- | Not implemented. Engine always raises exception, never calls sys.exit(). |
| 5 | Context variable resolution | **Yes** | High | `_process()` line 133 | Resolves `${context.var}` via ContextManager |
| 6 | GlobalMap variable resolution | **Partial** | Low | `_resolve_global_map_variables()` line 184 | Only handles `((Integer)globalMap.get("key"))` pattern -- misses String, Long, and other casts |
| 7 | Job termination | **Yes** | High | `_process()` line 170 | Always raises ComponentExecutionError |
| 8 | Exit code on exception | **Yes** | High | `_process()` line 174 | Attaches `exit_code` attribute to exception |
| 9 | GlobalMap storage | **Yes** | High | `_process()` lines 153-158 | Stores {id}_MESSAGE, {id}_CODE, {id}_PRIORITY, {id}_EXIT_CODE, JOB_ERROR_MESSAGE, JOB_EXIT_CODE |
| 10 | Statistics tracking | **Yes** | High | `_process()` lines 161-167 | Tracks NB_LINE, NB_LINE_OK=0, NB_LINE_REJECT |
| 11 | Phantom exit_code param | **N/A** | N/A | `_process()` line 129 | Engine reads `exit_code` config key (default 1) but this param does NOT exist in _java.xml. Phantom parameter. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-DIE-001 | **P1** | **Message default mismatch**: Engine uses `"Job execution stopped"` (line 126) but Talend _java.xml default is `"the end is near"`. When converter emits the Talend default, behavior matches. If config key is stripped, engine falls back to wrong default. |
| ENG-DIE-002 | **P1** | **Code default mismatch**: Engine uses `1` (line 127) but Talend _java.xml default is `4`. Same config-stripping risk as message. |
| ENG-DIE-003 | **P1** | **EXIT_JVM not supported**: Engine does not read EXIT_JVM config key. Talend's System.exit() behavior cannot be replicated. Jobs relying on JVM termination semantics will behave differently -- exception-based shutdown allows tPostjob and finally blocks to run. |
| ENG-DIE-004 | **P2** | **Phantom exit_code parameter**: Engine reads `exit_code` config key (line 129, default 1) but this parameter does NOT exist in tDie_java.xml. The converter correctly does not emit this key, so engine always uses its default. |
| ENG-DIE-005 | **P2** | **Narrow globalMap regex**: `_resolve_global_map_variables()` (line 198) only matches `((Integer)globalMap.get("key"))` pattern. Missing `((String)globalMap.get(...))`, `((Long)globalMap.get(...))`, and other cast variants commonly used in Talend message expressions. |
| ENG-DIE-006 | **P3** | **No tLogCatcher integration**: Die messages are logged but not captured in a structured format for tLogCatcher consumption. In Talend, tLogCatcher captures die events with moment, pid, project, job, context, priority, type, origin, message, and code fields. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_MESSAGE` | Yes | Yes | `_process()` line 153 | Matches Talend |
| `{id}_CODE` | Yes | Yes | `_process()` line 154 | Matches Talend |
| `{id}_PRIORITY` | Yes | Yes | `_process()` line 155 | Matches Talend |
| `{id}_EXIT_CODE` | No | Yes | `_process()` line 156 | Phantom -- Talend does not set this. Engine uses its own `exit_code` param which is not in _java.xml. |
| `JOB_ERROR_MESSAGE` | Yes | Yes | `_process()` line 157 | Matches Talend |
| `JOB_EXIT_CODE` | Yes | Yes | `_process()` line 158 | Uses phantom exit_code value |
| `DIE_MESSAGES` | Yes | **No** | -- | Talend sets `DIE_MESSAGES` (plural). Engine uses `{id}_MESSAGE` instead. |
| `DIE_CODE` | Yes | **No** | -- | Talend sets `DIE_CODE`. Engine uses `{id}_CODE` instead. |
| `DIE_PRIORITY` | Yes | **No** | -- | Talend sets `DIE_PRIORITY`. Engine uses `{id}_PRIORITY` instead. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-DIE-001 | **P0** | `base_component.py:298` | **CROSS-CUTTING**: `_update_global_map()` crashes ALL components when globalMap is set. Method calls `self.global_map.set()` but `GlobalMap` has `put()` not `set()`. |
| BUG-DIE-002 | **P1** | `die.py:198` | **Narrow globalMap regex**: Only handles `((Integer)globalMap.get("key"))`. Missing String, Long, Float, Double, Boolean cast variants. Messages with `((String)globalMap.get("key"))` will not be resolved. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-DIE-001 | **P2** | Engine reads `exit_code` config key that does not exist in _java.xml. This phantom parameter creates confusion about what config keys are expected. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-DIE-001 | **P3** | "`_validate_config()` should be called or removed" | `_validate_config()` (lines 67-107) is defined but never called. Dead code -- base class `execute()` does not call component-level validation. |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified. The component does not execute arbitrary code, access the filesystem, or make network calls.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- module-level `logger = logging.getLogger(__name__)` |
| Level usage | Good -- priority-based logging (info/warning/error/critical) matches the PRIORITY parameter |
| Sensitive data | No concern -- message content is user-controlled and intended for logging |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Good -- uses `ComponentExecutionError` with exit code attachment |
| Exception chaining | Good -- re-raises ComponentExecutionError, chains unexpected errors with `from e` |
| die_on_error handling | N/A -- tDie always terminates; there is no "continue on error" mode |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- all methods have return type annotations |
| Parameter types | Good -- `input_data: Optional[pd.DataFrame]`, `message: str` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-DIE-001 | **P3** | **Regex recompilation**: `_resolve_global_map_variables()` calls `re.sub()` with inline pattern on every invocation. Could be compiled once as a module-level constant. Minimal impact since component only executes once before terminating. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- component terminates job immediately |
| Memory threshold | N/A -- no data accumulation |
| Large data handling | N/A -- input data only counted, not processed |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 24+ | `tests/converters/talend_to_v1/components/test_die.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-DIE-001 | **P2** | No engine unit tests for Die component |
| TEST-DIE-002 | **P2** | No integration test for tDie + tLogCatcher interaction |

### 8.3 Recommended Test Cases

- Engine unit test: verify ComponentExecutionError raised with correct message and exit_code
- Engine unit test: verify globalMap variables set correctly
- Engine unit test: verify context variable resolution in message
- Engine unit test: verify priority-based logging (each level 1-6)
- Integration test: tDie triggered by condition, caught by tLogCatcher

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **BUG-DIE-001** |
| P1 | 4 | **ENG-DIE-001**, **ENG-DIE-002**, **ENG-DIE-003**, **BUG-DIE-002** |
| P2 | 5 | **ENG-DIE-004**, **ENG-DIE-005**, **NAME-DIE-001**, **TEST-DIE-001**, **TEST-DIE-002** |
| P3 | 3 | **ENG-DIE-006**, **STD-DIE-001**, **PERF-DIE-001** |
| **Total** | **13** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 6 | ENG-DIE-001 through ENG-DIE-006 |
| Bug (BUG) | 2 | BUG-DIE-001, BUG-DIE-002 |
| Naming (NAME) | 1 | NAME-DIE-001 |
| Standards (STD) | 1 | STD-DIE-001 |
| Performance (PERF) | 1 | PERF-DIE-001 |
| Testing (TEST) | 2 | TEST-DIE-001, TEST-DIE-002 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:298` | `_update_global_map()` crash when globalMap set -- affects Die's globalMap storage |

---

## 10. Recommendations

### Immediate (Before Production)

1. **BUG-DIE-001** (P0): Fix cross-cutting `_update_global_map()` crash in base_component.py
2. **ENG-DIE-001** (P1): Fix engine message default to "the end is near"
3. **ENG-DIE-002** (P1): Fix engine code default to 4
4. **ENG-DIE-003** (P1): Implement EXIT_JVM support or document as known limitation

### Short-term (Hardening)

1. **BUG-DIE-002** (P1): Expand globalMap regex to handle all cast variants
2. **ENG-DIE-004** (P2): Remove phantom exit_code parameter from engine
3. **ENG-DIE-005** (P2): Add missing Talend globalMap variables (DIE_MESSAGES, DIE_CODE, DIE_PRIORITY)
4. **TEST-DIE-001/002** (P2): Add engine unit tests and integration tests

### Long-term (Optimization)

1. **ENG-DIE-006** (P3): Implement tLogCatcher integration
2. **STD-DIE-001** (P3): Remove dead `_validate_config()` method
3. **PERF-DIE-001** (P3): Compile globalMap regex pattern once

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub tDie_java.xml | `<https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tDie/tDie_java.xml`> | Parameter definitions, defaults |
| Official Talend docs (tDie 8.0) | `<https://help.qlik.com/talend/en-US/components/8.0/logs-and-errors/tdie`> | Component behavior, usage |
| Error handling guide (Talend 8.0) | `<https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-07/using-tdie-twarn-and-tlogcatcher-for-error-handling`> | tDie + tLogCatcher interaction |
| Engine source | `src/v1/engine/components/control/die.py` (205 lines) | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/control/die.py` | Converter audit |
| Base component | `src/v1/engine/base_component.py` | Cross-cutting bug analysis |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:298` | `_update_global_map()` crash when globalMap set. Die stores 6 globalMap variables -- all would fail if base class method were called instead of direct `global_map.put()`. Currently Die uses direct `global_map.put()` calls (lines 153-158), bypassing the broken base class method. |
| XCUT-002 | `base_component.py` | `_validate_config()` dead code pattern. Die defines validation (lines 67-107) that is never called. |
| XCUT-003 | `global_map.py:28` | `GlobalMap.get()` broken method. Die uses `global_map.put()` directly which works correctly. |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after full rewrite per Phase 07 standardization*
