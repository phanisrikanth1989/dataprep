# Audit Report: tFileExist / FileExistComponent

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileExist` |
| **V1 Engine Class** | `FileExistComponent` |
| **Engine File** | `src/v1/engine/components/file/file_exist.py` (120 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tfileexist()` (lines 1691-1695) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tFileExist'` (line 290) |
| **Registry Aliases** | `FileExist`, `tFileExist`, `FileExistComponent` (registered in `src/v1/engine/engine.py` lines 84-86) |
| **Category** | File / Utility |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_exist.py` | Engine implementation (120 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 1691-1695) | Parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (line 290) | Dispatch -- dedicated `elif` branch for `tFileExist` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE`, `{id}_EXISTS`, etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports -- exports `FileExistComponent` (line 5) |
| `src/converters/complex_converter/component_parser.py` (line 33) | NAME_MAP: `'tFileExist': 'FileExistComponent'` |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 1 | 1 | 1 | 1 of 3 Talend params extracted (33%); only FILE_NAME; missing tStatCatcher (low priority) and advanced settings |
| Engine Feature Parity | **Y** | 1 | 4 | 2 | 0 | Missing globalMap EXISTS/FILENAME/ERROR_MESSAGE; returns dict not DataFrame; no status propagation |
| Code Quality | **Y** | 4 | 4 | 2 | 1 | Cross-cutting base class bugs; dead `_validate_config()`; return type mismatch; redundant validation; trigger_manager Boolean regex missing; `!`/`!=` replacement corruption; `global_map.get()` crash in trigger eval |
| Performance & Memory | **G** | 0 | 0 | 1 | 0 | HYBRID streaming mode crash for dict-returning components |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests |
| Security | **Y** | 0 | 1 | 0 | 1 | `eval()` on condition strings in trigger_manager.py; path traversal (low risk) |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileExist Does

`tFileExist` checks whether a specified file or directory exists at a given path and returns a boolean result. It is a **standalone utility component** (no input/output row flow) that belongs to the File family. The primary use case is conditional job routing: tFileExist checks if a file is present, then downstream components execute conditionally based on the `EXISTS` global variable via `Run If` trigger connections. Talend generates Java code that stores the result as `((Boolean)globalMap.get("tFileExist_1_EXISTS"))`, which is then used in conditional expressions.

**Source**: [tFileExist Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tfileexist/tfileexist-standard-properties), [tFileExist Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tfileexist/tfileexist-standard-properties), [tFileExist ESB 7.x (Talend Skill)](https://talendskill.com/talend-for-esb-docs/docs-7-x/tfileexist-talend-open-studio-for-esb-document-7-x/), [tFileExist Community Discussion](https://community.talend.com/s/feed/0D53p00007vCpTMCA0?language=en_US)

**Component family**: File (Utility)
**Available in**: All Talend products (Standard Job framework)
**Required JARs**: None (pure Java file system calls)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | File name / Stream | `FILE_NAME` | Expression (String) | -- | **Mandatory**. Absolute file path to check for existence. Supports context variables, globalMap references, Java expressions. Talend documentation emphasizes: "use absolute path (instead of relative path) for this field to avoid possible errors." |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 3 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Used for chaining subjobs. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. More granular than SUBJOB_OK. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. The target component only executes if the condition evaluates to true. **This is the primary connection type for tFileExist** -- typically uses `((Boolean)globalMap.get("tFileExist_1_EXISTS"))` as the condition. |
| `ITERATE` | Input (Row) | Row | Enables iterative execution when used with iteration components like `tFileList`. Allows checking multiple files in a loop. |
| `RUN_IF` | Input (Trigger) | Trigger | Conditional trigger from upstream components. |
| `SUBJOB_OK` | Input (Trigger) | Trigger | Trigger from upstream subjob success. |
| `SUBJOB_ERROR` | Input (Trigger) | Trigger | Trigger from upstream subjob error. |
| `COMPONENT_OK` | Input (Trigger) | Trigger | Trigger from upstream component success. |
| `COMPONENT_ERROR` | Input (Trigger) | Trigger | Trigger from upstream component error. |
| `SYNCHRONIZE` | Input (Trigger) | Trigger | Synchronization trigger for parallel execution. |
| `PARALLELIZE` | Input (Trigger) | Trigger | Parallelization trigger for concurrent execution. |

**Important**: tFileExist has **NO row output connections** (no FLOW/Main, no REJECT). It is purely a trigger-based utility component. Data routing is done exclusively through trigger connections, typically via `Run If` with the `EXISTS` global variable.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_EXISTS` | Boolean | Flow (during execution) | **Primary output variable**. `true` if the specified file/path exists, `false` otherwise. Accessed in Run If conditions as `((Boolean)globalMap.get("tFileExist_1_EXISTS"))`. This is a **Flow variable** -- set during component execution, available immediately for Run If conditions on the same component. |
| `{id}_FILENAME` | String | After execution | The resolved file name/path that was checked. Available for reference in downstream components via globalMap. |
| `{id}_ERROR_MESSAGE` | String | On error | Error message if the component encountered an exception during execution. Only set when die on error is disabled (though tFileExist does not have an explicit die_on_error parameter -- errors are typically OS-level permission failures). |

**Critical behavioral note on `EXISTS`**: In Talend, `{id}_EXISTS` is a **Flow variable**, meaning it is set DURING the component's execution (not after). This allows `Run If` trigger conditions on the SAME component to reference the variable. For example, a `Run If` connection from `tFileExist_1` to `tMsgBox_1` can use the condition `!((Boolean)globalMap.get("tFileExist_1_EXISTS"))` to trigger the message box only when the file does NOT exist. The exclamation mark negates the boolean.

### 3.5 Behavioral Notes

1. **No data flow**: tFileExist does NOT produce rows. It is a pure utility/control component. Its output is exclusively through globalMap variables and trigger connections.

2. **File vs. Directory**: The Talend component checks `java.io.File.exists()`, which returns `true` for both files AND directories. There is no separate "check directory only" mode in the standard tFileExist component.

3. **Symbolic links**: Java's `File.exists()` follows symbolic links. If the symlink target does not exist, `exists()` returns `false`.

4. **Permission errors**: If the Java process lacks read permission for the parent directory, `File.exists()` returns `false` (not an error). This is a subtle behavioral difference from raising an exception.

5. **Run If pattern**: The canonical Talend usage pattern is:
   - `tFileExist_1` checks if a file exists
   - `Run If` connection to component A with condition `((Boolean)globalMap.get("tFileExist_1_EXISTS"))` (file exists)
   - `Run If` connection to component B with condition `!((Boolean)globalMap.get("tFileExist_1_EXISTS"))` (file does NOT exist -- note the `!` prefix)

6. **Empty path**: If the file path is empty or null, Talend throws a `NullPointerException` at runtime. There is no graceful handling for empty paths.

7. **Relative paths**: Talend documentation warns against relative paths. Relative paths resolve against the JVM's working directory, which may differ between Talend Studio and deployed jobs.

8. **Context variables in path**: File paths commonly contain context variables like `context.input_dir + "/data.csv"`. These are resolved via Java string concatenation before the existence check.

9. **Iterate compatibility**: When connected via an Iterate link from tFileList, tFileExist can check multiple files in a loop, with each iteration updating the `EXISTS` variable.

10. **No schema**: tFileExist has no output schema. It does not define columns or data types for output rows.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated parser method** (`parse_tfileexist()` in `component_parser.py` lines 1691-1695), dispatched from `converter.py` line 290 via `elif component_type == 'tFileExist'`. This is the correct approach per STANDARDS.md.

**Converter flow**:
1. `converter.py:_parse_component()` matches `component_type == 'tFileExist'` (line 290)
2. Calls `self.component_parser.parse_tfileexist(node, component)` (line 291)
3. Parser extracts `FILE_NAME` from XML `elementParameter` node
4. Strips surrounding quotes and stores in `component['config']['FILE_NAME']`

**Converter code** (component_parser.py lines 1691-1695):
```python
def parse_tfileexist(self, node, component: Dict) -> Dict:
    """Parse tFileExist specific configuration"""
    file_name = node.find('.//elementParameter[@name="FILE_NAME"]').get('value', '')
    component['config']['FILE_NAME'] = file_name.strip('"')
    return component
```

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `FILE_NAME` | **Yes** | `FILE_NAME` | 1693-1694 | Strips surrounding quotes via `.strip('"')`. Does NOT mark Java expressions. |
| 2 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 3 | `PROPERTY_TYPE` | **No** | -- | -- | Not needed (always Built-In in converted jobs) |

**Summary**: 1 of 3 parameters extracted (33%). However, only 1 parameter (FILE_NAME) is runtime-relevant, so functional coverage is higher.

### 4.2 Schema Extraction

Not applicable. tFileExist has no output schema -- it does not define rows or columns. The converter correctly does not attempt schema extraction.

### 4.3 Expression Handling

**Critical gap**: The converter does NOT call `mark_java_expression()` on the extracted `FILE_NAME` value. Compare with other converter parsers:

- `parse_tfiletouch()` (line 1687): Extracts `FILENAME` but also does NOT mark Java expressions
- `parse_tfileproperties()` (line 1699): Extracts `FILENAME` but also does NOT mark Java expressions

This means Java expressions in the file path (e.g., `context.input_dir + "/data.csv"`) will NOT be properly marked with the `{{java}}` prefix and will NOT be resolved by the Java bridge at runtime.

**Context variable handling**: Simple `context.var` references (without Java operators) are handled by the generic `parse_base_component()` context detection loop (lines 449-456). However, since `parse_tfileexist()` is a dedicated parser that bypasses the generic loop, context variables in `FILE_NAME` are NOT wrapped with `${context.var}` either. The converter relies on the engine's `context_manager.resolve_dict()` to handle `context.` references at runtime, but only if the value contains the literal string `context.` without Java operators.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FE-001 | **P1** | **No Java expression marking on FILE_NAME**: `parse_tfileexist()` does not call `self.expr_converter.mark_java_expression(file_name)` after extracting the value. Java expressions in the file path (e.g., `context.input_dir + "/data.csv"`, `TalendString.replaceSpecialCharForFilePath(...)`) will not be resolved at runtime. Compare: the proposed `parse_file_input_delimited()` in the gold standard marks FILENAME with `mark_java_expression()` (Appendix K, line 1227). |
| CONV-FE-002 | **P2** | **No context variable wrapping**: The dedicated parser does not detect or wrap `context.var` references in the file path. While `context_manager.resolve_dict()` handles simple `${context.var}` patterns at runtime, the converter never adds the `${...}` wrapper. This works only if the engine's context resolution handles bare `context.var` strings -- which it does NOT for concatenated expressions. |
| CONV-FE-003 | **P3** | **No `AttributeError` guard on `.find()`**: Line 1693 calls `node.find('.//elementParameter[@name="FILE_NAME"]').get('value', '')` without checking if `find()` returns `None`. If the XML node does not contain a `FILE_NAME` element parameter (e.g., malformed Talend XML), this will crash with `AttributeError: 'NoneType' object has no attribute 'get'`. Other parsers have the same pattern, but it is still a robustness gap. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Check file existence | **Yes** | High | `_process()` line 104 | Uses `os.path.exists(file_path)` -- matches Talend's `File.exists()` behavior for both files and directories |
| 2 | Check directory specifically | **Yes** | Medium | `_process()` line 101 | Uses `os.path.isdir(file_path)` when `check_directory=True`. **Not a standard Talend feature** -- V1 adds this as an extension. |
| 3 | Return existence status | **Yes** | Low | `_process()` line 110 | Returns `{'file_exists': file_exists}` dict inside `{'main': result}`. **Does NOT match Talend pattern** -- Talend sets `{id}_EXISTS` in globalMap as a boolean. V1 returns a dict, does not set globalMap. |
| 4 | `{id}_EXISTS` globalMap variable | **No** | N/A | -- | **Not implemented.** This is the PRIMARY output of tFileExist in Talend. Downstream `Run If` conditions reference `((Boolean)globalMap.get("tFileExist_1_EXISTS"))`. Without this, tFileExist is functionally useless for conditional routing. |
| 5 | `{id}_FILENAME` globalMap variable | **No** | N/A | -- | **Not implemented.** The resolved file path is not stored in globalMap for downstream reference. |
| 6 | `{id}_ERROR_MESSAGE` globalMap variable | **No** | N/A | -- | **Not implemented.** Error messages are not stored in globalMap. |
| 7 | Legacy `FILE_NAME` parameter support | **Yes** | High | `_process()` line 86 | Supports both `file_path` and `FILE_NAME` config keys via `self.config.get('file_path') or self.config.get('FILE_NAME')` |
| 8 | Statistics tracking | **Yes** | High | `_process()` line 108 | `_update_stats(1, 1, 0)` on success; `_update_stats(1, 0, 1)` on failure |
| 9 | Config validation | **Partial** | Medium | `_validate_config()` lines 45-69 | Validation method exists but is **never called** (dead code). `_process()` has its own inline validation (lines 93-96). |
| 10 | Trigger connection support | **Partial** | Medium | Via engine trigger system | The engine's `TriggerManager` handles trigger connections. However, `Run If` conditions that reference `{id}_EXISTS` will fail because the variable is never set in globalMap. |
| 11 | Context variable resolution | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` resolves `${context.var}` patterns before `_process()` |
| 12 | Java expression resolution | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers. But converter does not mark expressions (see CONV-FE-001). |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FE-001 | **P0** | **`{id}_EXISTS` not set in globalMap**: This is the **primary output** of tFileExist in Talend. Every downstream `Run If` condition that references `((Boolean)globalMap.get("tFileExist_1_EXISTS"))` will fail. Without this variable, the component cannot drive conditional job logic, which is its entire purpose. The component calculates the existence status (`file_exists` local variable on line 104) but never stores it in globalMap. |
| ENG-FE-002 | **P1** | **`{id}_FILENAME` not set in globalMap**: The resolved file path is not stored in globalMap. Downstream components that reference the filename for logging, audit trails, or conditional logic will get null/None. |
| ENG-FE-003 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When the component catches an exception (line 116), it logs the error and re-raises, but does not store the error message in globalMap. Downstream error-handling components cannot access the error details. |
| ENG-FE-004 | **P1** | **Returns dict instead of None/DataFrame for `main`**: `_process()` returns `{'main': {'file_exists': True/False}}` (line 120). The `main` value is a Python dict, not a DataFrame or None. The engine's `_execute_component()` method stores `result['main']` in `data_flows` for downstream flow connections (engine.py line 572). Since tFileExist has no row output in Talend, the `main` key should ideally be `None` (like tFileDelete returns `{'main': None, 'status': ...}`) or the component should store its output exclusively in globalMap. Storing a dict in `data_flows` may confuse downstream components that expect a DataFrame. |
| ENG-FE-005 | **P1** | **`check_directory` is a non-standard extension**: The engine supports `check_directory=True` for directory-only checking via `os.path.isdir()`. Standard Talend tFileExist does NOT have this option -- it always uses `File.exists()` which returns `true` for both files and directories. While this extension is harmless (defaults to `False`), it creates a behavioral surface that does not exist in Talend. If `check_directory=True` is set, a file at the path would return `False` (because it is not a directory), which differs from Talend's behavior. |
| ENG-FE-006 | **P2** | **Component status not propagated for trigger conditions**: While `BaseComponent` sets `self.status = ComponentStatus.SUCCESS` (line 220), the engine's `TriggerManager` receives `'success'` or `'error'` strings (engine.py line 593). The `Run If` condition evaluation needs access to globalMap variables, but `{id}_EXISTS` is never set. This means `Run If` conditions based on the existence check will always evaluate to null/undefined. |
| ENG-FE-007 | **P2** | **No path normalization**: The file path from config is used as-is with `os.path.exists()`. Talend normalizes paths via Java's `File` constructor (resolving `..`, `/./`, etc.). Python's `os.path.exists()` also resolves these, but there may be edge cases with trailing slashes or platform-specific path separators. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_EXISTS` | **Yes** (Flow variable) | **No** | -- | **CRITICAL GAP.** This is the primary output of the component. |
| `{id}_FILENAME` | **Yes** (After variable) | **No** | -- | Not implemented. Common in audit/logging patterns. |
| `{id}_ERROR_MESSAGE` | **Yes** (After variable) | **No** | -- | Not implemented. Needed for error-handling flows. |
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism. Always 1 (one existence check per execution). |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Set correctly. 1 on success, 0 on failure. |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | Same mechanism | Set correctly. 0 on success, 1 on failure. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FE-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileExistComponent, since `_update_global_map()` is called after every component execution (via `execute()` line 218 on success, line 231 on error). |
| BUG-FE-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FE-003 | **P1** | `src/v1/engine/components/file/file_exist.py:45-69, 93-96` | **`_validate_config()` is dead code -- never called**: The method contains 24 lines of comprehensive validation logic (checking for missing `file_path`, type validation, empty string check, `check_directory` type check), but it is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. Instead, `_process()` has its own inline validation (lines 93-96) that only checks `if not file_path` -- a subset of what `_validate_config()` covers. The `_validate_config()` also validates `isinstance(file_path, str)` and `file_path.strip()` which the inline check misses. |
| BUG-FE-004 | **P1** | `src/v1/engine/components/file/file_exist.py:86, 55` | **Duplicate `file_path` resolution**: Both `_validate_config()` (line 55) and `_process()` (line 86) independently resolve the file path with the same logic: `self.config.get('file_path') or self.config.get('FILE_NAME')`. This duplication means that even if `_validate_config()` were called, its resolved path would not be reused by `_process()`. If the config key naming changes, both locations must be updated. |
| BUG-FE-005 | **P1** | `src/v1/engine/components/file/file_exist.py:120` | **Returns dict in `main` key instead of DataFrame or None**: `_process()` returns `{'main': result}` where `result = {'file_exists': file_exists}` (a plain dict). The engine's `_execute_streaming()` method (base_component.py line 275) calls `pd.concat(results)` on the collected `main` values, which will crash with `TypeError` if the component runs in streaming mode and the `main` value is a dict. Additionally, the engine's `_execute_component()` stores `result['main']` in `data_flows` (engine.py line 572), potentially confusing downstream components that expect a DataFrame. Talend's tFileExist has NO row output -- its output is exclusively via globalMap. The `main` key should be `None`. |
| BUG-FE-006 | **P1** | `src/v1/engine/components/file/file_exist.py:91` | **`rows_processed = 1` set before validation**: The local variable `rows_processed` is initialized to 1 on line 91 before the `file_path` check on line 93. If validation fails and `ValueError` is raised (line 96), `rows_processed` is never used in `_update_stats()`. However, if the exception propagates up to `execute()` (base_component.py line 227-234), the stats remain at their initial zero values, which is correct. The variable initialization is premature but not functionally harmful. |
| BUG-FE-007 | **P0** | `src/v1/engine/trigger_manager.py:199-208` | **No `((Boolean)...)` regex in `_evaluate_condition()`**: The condition evaluation only has a regex pattern for `((Integer)globalMap.get(...))`. There is no corresponding pattern for `((Boolean)globalMap.get(...))`. tFileExist Run If conditions like `((Boolean)globalMap.get('tFileExist_1_EXISTS'))` will fail `eval()` with `NameError` on `'Boolean'`, silently returning `False`. Even if `{id}_EXISTS` is fixed (ENG-FE-001), trigger conditions will not work. **CROSS-CUTTING**: Affects ALL components that use Boolean-typed Run If conditions. |
| BUG-FE-008 | **P0** | `src/v1/engine/trigger_manager.py:228` | **`!` replacement corrupts `!=` operator in trigger conditions**: `replace('!', ' not ')` runs BEFORE `replace('!= None', ' is not None')` (line 231). Every `!=` in a condition string becomes ` not =` (invalid Python syntax). The `!= None` fix on line 231 is dead code because the `!=` has already been destroyed. **CROSS-CUTTING**: Affects ALL components with `!=` in Run If conditions, not just tFileExist. |
| BUG-FE-009 | **P1** | `src/v1/engine/trigger_manager.py:205, 215` | **`global_map.get()` crash actively triggered by `_evaluate_condition()`**: Lines 205 and 215 call `global_map.get()` which has the undefined `default` parameter bug (BUG-FE-002). Even if all tFileExist fixes are applied, trigger evaluation crashes with `NameError` before reaching `eval()`. This makes trigger conditions completely non-functional at runtime. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FE-001 | **P2** | **Config key mismatch: `FILE_NAME` (converter) vs `file_path` (engine default)**: The converter stores the Talend parameter as `FILE_NAME` (uppercase, matching Talend XML). The engine's `_process()` tries `self.config.get('file_path')` first, then falls back to `self.config.get('FILE_NAME')`. The `_validate_config()` uses the same dual-key pattern. While the fallback ensures both keys work, the primary key (`file_path`) is never set by the converter, meaning the fallback (`FILE_NAME`) is always used. This is inconsistent with other components where the converter maps to the engine's preferred key name (e.g., `FILENAME` -> `filepath` for tFileInputDelimited). |
| NAME-FE-002 | **P3** | **Class name includes 'Component' suffix**: `FileExistComponent` has a `Component` suffix while many other v1 components do not (e.g., `FileDelete`, `FileCopy`, `FileTouch`). The registry includes both `FileExist` and `FileExistComponent` aliases to handle this inconsistency. Not a functional issue. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FE-001 | **P1** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists and correctly returns `List[str]`, but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-FE-002 | **P2** | "Component output should be DataFrame or None in `main` key" (implied by base class and engine consumption) | Returns a plain dict `{'file_exists': bool}` in the `main` key. Base class `_execute_streaming()` will crash on `pd.concat()` with this type. Engine `_execute_component()` stores it in `data_flows`, which expects DataFrame. |
| STD-FE-003 | **P2** | "Set component-specific globalMap variables" (implied by Talend feature parity) | Does not set `{id}_EXISTS`, `{id}_FILENAME`, or `{id}_ERROR_MESSAGE` in globalMap. Only base class stats (`NB_LINE`, etc.) are set via `_update_global_map()`. |

### 6.4 Debug Artifacts

No debug artifacts found in `file_exist.py`. The code is clean of `print()` statements, `# TODO` comments, and generation artifacts.

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FE-001 | **P3** | **No path traversal protection**: `file_path` from config is used directly with `os.path.exists()` and `os.path.isdir()`. If config comes from untrusted sources, path traversal (`../../etc/passwd`) is possible. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. The existence check itself does not read file contents, but it does reveal whether paths exist on the filesystem. |
| SEC-FE-002 | **P1** | **`eval()` on condition strings from job config**: `trigger_manager.py` line 234 uses `eval()` on condition strings derived from job configuration. If job configs are modified, corrupted, or sourced from untrusted inputs, this enables arbitrary code execution. While Talend-converted configs are generally trusted, `eval()` on external strings is a well-known security anti-pattern. A safer alternative would be to use `ast.literal_eval()` or implement a restricted expression parser. |

### 6.6 Logging Quality

The component has good logging throughout, following STANDARDS.md patterns:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start/complete, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 89) and completion (line 112-113) -- correct |
| Sensitive data | No sensitive data logged -- correct. File paths are logged but are not typically sensitive. |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ValueError` for missing config (line 96). Does NOT use custom exceptions from `exceptions.py` (`ConfigurationError`, `FileOperationError`). Other components use custom exceptions -- inconsistency. |
| Exception chaining | Does NOT use `raise ... from e` pattern. Line 118 uses bare `raise` (re-raise), which preserves the original traceback. Acceptable but `raise ... from e` is preferred for clarity. |
| Error logging | `logger.error()` called before raising (line 95, 116) -- correct |
| Generic except handler | Line 115 catches `Exception` (not bare `except`) -- correct |
| Stats on error | `_update_stats(rows_processed, 0, 1)` called on error (line 117) -- correct |
| No silent failures | Errors are logged and re-raised -- correct |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_validate_config() -> List[str]` and `_process(input_data: Optional[Any]) -> Dict[str, Any]` -- correct |
| Parameter types | `input_data: Optional[Any]` -- correct for this component (does not use input data) |
| Complex types | Uses `Dict[str, Any]`, `List[str]`, `Optional[Any]` -- correct |
| Return type accuracy | `_process()` typed as `Dict[str, Any]` which is accurate. However, the `main` value being a dict (not DataFrame) is a semantic issue, not a type hint issue. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FE-001 | **P2** | **HYBRID streaming mode crash**: If the engine runs FileExistComponent in STREAMING mode (e.g., because hybrid mode selects streaming based on input data size from an upstream iterate component), `_execute_streaming()` in base_component.py (line 275) will call `pd.concat(results)` where `results` contains `{'file_exists': True}` dicts. This will crash with `TypeError`. The component should return `{'main': None}` instead of `{'main': dict}` to avoid this path, or the component should override `_execute_streaming()`. In practice, tFileExist receives `None` input (no data flow), so `_execute_streaming()` line 257-258 would short-circuit to `self._process(None)` -- but this depends on the engine never providing non-None input to this component. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Memory footprint | Negligible. The component performs a single `os.path.exists()` call and creates a small dict. No DataFrames, no file reading. |
| Streaming mode | Not applicable for this component. tFileExist does not process data rows. |
| Resource cleanup | No resources to clean up. `os.path.exists()` does not hold file handles. |

### 7.2 Thread Safety

| Aspect | Assessment |
|--------|------------|
| Shared state | No shared mutable state. Each `FileExistComponent` instance has its own `config`, `stats`, and `status`. |
| File system calls | `os.path.exists()` and `os.path.isdir()` are thread-safe (they are stateless system calls). |
| GlobalMap access | If `global_map` were shared between threads, `_update_global_map()` (via base class) could have race conditions on `put_component_stat()`. However, the current v1 engine is single-threaded. |
| Verdict | Thread-safe for the current single-threaded engine. Minor concern if engine becomes multi-threaded. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileExistComponent` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter unit tests | **No** | -- | No tests for `parse_tfileexist()` |

**Key finding**: The v1 engine has ZERO tests for this component. All 120 lines of v1 engine code and 5 lines of converter code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | File exists | P0 | Check an existing file, verify `file_exists=True` in result and `{id}_EXISTS=True` in globalMap |
| 2 | File does not exist | P0 | Check a non-existent file, verify `file_exists=False` in result and `{id}_EXISTS=False` in globalMap |
| 3 | Directory exists | P0 | Check an existing directory (with `check_directory=False`), verify `file_exists=True` (matches Talend -- `File.exists()` returns true for directories) |
| 4 | Missing file_path config | P0 | Provide empty config, verify `ValueError` is raised with descriptive message |
| 5 | Statistics tracking | P0 | Execute with valid file path, verify `NB_LINE=1`, `NB_LINE_OK=1`, `NB_LINE_REJECT=0` in stats |
| 6 | GlobalMap integration | P0 | Execute with `global_map` provided, verify `{id}_NB_LINE=1` etc. are set in globalMap |
| 7 | Run If condition pattern | P0 | Simulate a `Run If` condition using `((Boolean)globalMap.get("{id}_EXISTS"))`, verify it evaluates correctly |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Check directory mode | P1 | Set `check_directory=True`, check a file (not directory), verify returns `False` |
| 9 | Check directory mode with directory | P1 | Set `check_directory=True`, check existing directory, verify returns `True` |
| 10 | Legacy FILE_NAME parameter | P1 | Use `FILE_NAME` key in config instead of `file_path`, verify it works |
| 11 | Context variable in path | P1 | Use `${context.input_dir}/file.txt` as file path, verify context resolution |
| 12 | Java expression in path | P1 | Use `{{java}}context.dir + "/file.txt"` as file path, verify Java bridge resolution |
| 13 | Symbolic link exists | P1 | Check a symbolic link pointing to an existing file, verify `True` |
| 14 | Symbolic link broken | P1 | Check a symbolic link pointing to a deleted file, verify `False` |
| 15 | Empty string file_path | P1 | Set `file_path` to `""`, verify `ValueError` is raised |
| 16 | FILENAME globalMap variable | P1 | After execution, verify `{id}_FILENAME` is set in globalMap with the resolved path |
| 17 | Error handling | P1 | Simulate OS-level error (e.g., permission denied), verify exception is raised and logged |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 18 | Path with spaces | P2 | Check file at `/path/with spaces/file.txt`, verify correct behavior |
| 19 | Path with special characters | P2 | Check file at path containing unicode characters |
| 20 | Relative path | P2 | Check a relative path, verify it resolves correctly |
| 21 | Whitespace-only file_path | P2 | Set `file_path` to `"   "`, verify `ValueError` or `False` |
| 22 | Very long path | P2 | Check a path exceeding OS limits, verify graceful error |
| 23 | Path traversal | P2 | Check `../../etc/passwd`, verify correct boolean result (does not read file) |
| 24 | Concurrent execution | P2 | Multiple `FileExistComponent` instances checking different files simultaneously |
| 25 | NaN in config | P2 | Set `file_path` to `float('nan')` via code, verify type validation catches it |
| 26 | Empty DataFrame input | P2 | Pass an empty DataFrame as `input_data`, verify it is ignored and existence check proceeds normally |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FE-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-FE-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| BUG-FE-007 | Bug (Cross-Cutting) | No `((Boolean)...)` regex in `trigger_manager._evaluate_condition()` (trigger_manager.py:199-208). Only `((Integer)...)` pattern exists. tFileExist Run If conditions like `((Boolean)globalMap.get('tFileExist_1_EXISTS'))` will fail `eval()` with `NameError` on `'Boolean'`, silently returning `False`. Even if `{id}_EXISTS` is fixed (ENG-FE-001), trigger conditions will not work. |
| BUG-FE-008 | Bug (Cross-Cutting) | `!` replacement corrupts `!=` operator in trigger conditions (trigger_manager.py:228). `replace('!', ' not ')` runs BEFORE `replace('!= None', ' is not None ')`. Every `!=` becomes ` not =` (invalid syntax). The `!= None` fix on line 231 is dead code. Cross-cutting: affects ALL components with `!=` in Run If conditions. |
| ENG-FE-001 | Engine | **`{id}_EXISTS` not set in globalMap.** This is the PRIMARY output of tFileExist. Without it, Run If conditions cannot evaluate, making the component functionally useless for conditional job routing. |
| TEST-FE-001 | Testing | Zero v1 unit tests for this component. All 120 lines of engine code and 5 lines of converter code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FE-001 | Converter | No Java expression marking on `FILE_NAME`. Java expressions in file path will not be resolved at runtime. |
| ENG-FE-002 | Engine | `{id}_FILENAME` globalMap variable not set. Downstream references get null. |
| ENG-FE-003 | Engine | `{id}_ERROR_MESSAGE` globalMap variable not set. Error details not available downstream. |
| ENG-FE-004 | Engine | Returns dict in `main` key instead of None/DataFrame. Violates engine contract, may crash streaming mode. |
| ENG-FE-005 | Engine | `check_directory` is a non-standard Talend extension. Could cause behavioral divergence if set to `True`. |
| BUG-FE-003 | Bug | `_validate_config()` is dead code (never called). 24 lines of comprehensive validation logic unreachable. `_process()` has weaker inline validation. |
| BUG-FE-004 | Bug | Duplicate file_path resolution in both `_validate_config()` and `_process()`. DRY violation; maintenance hazard. |
| BUG-FE-005 | Bug | Returns dict in `main` key. `_execute_streaming()` in base class will crash with `pd.concat()` on dict values. |
| BUG-FE-009 | Bug (Cross-Cutting) | `global_map.get()` crash actively triggered by `trigger_manager._evaluate_condition()` at lines 205 and 215. Even if all tFileExist fixes applied, trigger evaluation crashes before reaching `eval()`. |
| SEC-FE-002 | Security | `trigger_manager.py` line 234 uses `eval()` on condition strings from job config. Arbitrary code execution if configs are modified or corrupted. |
| TEST-FE-002 | Testing | No integration test verifying tFileExist -> Run If -> downstream component conditional execution. |

### P2 -- Moderate

| ID | Priority | Category | Summary |
|----|----------|----------|---------|
| CONV-FE-002 | P2 | Converter | No context variable wrapping. Bare `context.var` references in file path not wrapped with `${...}`. |
| ENG-FE-006 | P2 | Engine | Component status not propagated for trigger condition evaluation. `Run If` conditions based on `{id}_EXISTS` will fail. |
| ENG-FE-007 | P2 | Engine | No path normalization. Edge cases with `..`, `/./ `, trailing slashes may differ from Talend. |
| NAME-FE-001 | P2 | Naming | Config key mismatch: converter writes `FILE_NAME`, engine defaults to `file_path`. Fallback works but is inconsistent. |
| STD-FE-002 | P2 | Standards | Returns dict in `main` key instead of DataFrame/None. Violates implicit engine contract. |
| STD-FE-003 | P2 | Standards | Does not set component-specific globalMap variables (`EXISTS`, `FILENAME`, `ERROR_MESSAGE`). |
| PERF-FE-001 | P2 | Performance | HYBRID streaming mode could crash if this component receives non-None input. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FE-003 | Converter | No `AttributeError` guard on `.find()` for `FILE_NAME` element. Crash on malformed XML. |
| NAME-FE-002 | Naming | Class name `FileExistComponent` has `Component` suffix inconsistent with `FileDelete`, `FileCopy`, `FileTouch`. |
| SEC-FE-001 | Security | No path traversal protection. File path from config used directly. Low risk for Talend-converted jobs. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 6 | 4 bugs (cross-cutting), 1 engine, 1 testing |
| P1 | 11 | 1 converter, 4 engine, 4 bugs, 1 security, 1 testing |
| P2 | 7 | 1 converter, 2 engine, 1 naming, 2 standards, 1 performance |
| P3 | 3 | 1 converter, 1 naming, 1 security |
| **Total** | **27** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FE-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FE-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Set `{id}_EXISTS` in globalMap** (ENG-FE-001): After computing `file_exists` on line 104, add:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_EXISTS", file_exists)
   ```
   This is the single most critical fix for this component. Without it, tFileExist cannot drive conditional job logic. **Impact**: Enables all Run If conditions based on file existence. **Risk**: Very low.

4. **Create unit test suite** (TEST-FE-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: file exists, file does not exist, directory exists, missing config, statistics tracking, globalMap integration, and Run If condition pattern.

### Short-Term (Hardening)

5. **Set `{id}_FILENAME` and `{id}_ERROR_MESSAGE` in globalMap** (ENG-FE-002, ENG-FE-003): After resolving `file_path` in `_process()`, call `self.global_map.put(f"{self.id}_FILENAME", file_path)`. In the error handler (line 116), call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`.

6. **Change return value to `None` for `main`** (ENG-FE-004, BUG-FE-005): Change `return {'main': result}` (line 120) to:
   ```python
   return {'main': None, 'file_exists': file_exists}
   ```
   This aligns with tFileDelete's pattern (`return {'main': None, 'status': ...}`) and prevents streaming mode crashes. The `file_exists` value is available in the result dict for engine-level access, while the primary output goes through globalMap.

7. **Add Java expression marking in converter** (CONV-FE-001): Update `parse_tfileexist()` to mark the file name:
   ```python
   def parse_tfileexist(self, node, component: Dict) -> Dict:
       """Parse tFileExist specific configuration"""
       file_name_node = node.find('.//elementParameter[@name="FILE_NAME"]')
       if file_name_node is not None:
           file_name = file_name_node.get('value', '')
           file_name = file_name.strip('"')
           component['config']['file_path'] = self.expr_converter.mark_java_expression(file_name)
       return component
   ```
   Note: Also changes the config key from `FILE_NAME` to `file_path` to match the engine's primary key.

8. **Wire up `_validate_config()`** (BUG-FE-003): Add a call to `_validate_config()` at the beginning of `_process()`:
   ```python
   def _process(self, input_data=None):
       config_errors = self._validate_config()
       if config_errors:
           error_msg = "; ".join(config_errors)
           logger.error(f"[{self.id}] Configuration validation failed: {error_msg}")
           raise ValueError(f"[{self.id}] {error_msg}")
       # ...rest of _process()
   ```
   Then remove the duplicate inline validation on lines 93-96.

### Long-Term (Optimization)

9. **Normalize config key in converter** (NAME-FE-001): Change the converter to write `file_path` instead of `FILE_NAME`:
   ```python
   component['config']['file_path'] = file_name.strip('"')
   ```
   Then simplify `_process()` to only check `self.config.get('file_path')` without the `FILE_NAME` fallback. This eliminates the dual-key pattern and simplifies maintenance.

10. **Add integration test for Run If pattern** (TEST-FE-002): Build an end-to-end test exercising `tFileExist_1 -> (Run If: EXISTS==true) -> tFileInputDelimited_1` in the v1 engine, verifying that the conditional execution works correctly.

11. **Use custom exceptions** (code quality): Replace `ValueError` with `ConfigurationError` from `exceptions.py` for config validation failures. This aligns with other components' error handling patterns.

12. **Remove `check_directory` extension or document it** (ENG-FE-005): Either remove the non-standard `check_directory` parameter or document it clearly as a v1 extension that does not exist in Talend. If retained, ensure the converter never sets it (it currently does not).

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 1691-1695
def parse_tfileexist(self, node, component: Dict) -> Dict:
    """Parse tFileExist specific configuration"""
    file_name = node.find('.//elementParameter[@name="FILE_NAME"]').get('value', '')
    component['config']['FILE_NAME'] = file_name.strip('"')
    return component
```

**Notes on this code**:
- Line 1693: `node.find(...)` can return `None` if the XML element is missing. No guard against `AttributeError`.
- Line 1694: `strip('"')` removes surrounding quotes. Correct for Talend XML where values are often wrapped in `&quot;...&quot;`.
- The config key `FILE_NAME` is uppercase and matches the Talend XML parameter name, but differs from the engine's preferred `file_path` key. The engine handles this via fallback logic.
- No `mark_java_expression()` call -- Java expressions in the file path will not be resolved.
- No context variable detection or wrapping -- bare `context.var` references are not handled.

**Comparison with other utility component parsers**:

| Parser | Config Key | Java Expr Marking | Context Wrapping | None Guard |
|--------|-----------|-------------------|------------------|------------|
| `parse_tfileexist()` | `FILE_NAME` | No | No | No |
| `parse_tfiletouch()` | `filename` | No | No | No |
| `parse_tfileproperties()` | `FILENAME` | No | No | No |
| `parse_tfile_row_count()` | `filename` | No | No | No |

**Observation**: ALL utility file component parsers share the same gaps: no Java expression marking, no context variable wrapping, and no None guard on `.find()`. This is a systemic pattern, not specific to tFileExist.

---

## Appendix B: Engine Class Structure

```
FileExistComponent (BaseComponent)
    Configuration:
        file_path (str): Path to check. Required.
        FILE_NAME (str): Legacy alias for file_path.
        check_directory (bool): Check for directory specifically. Default: False. Non-standard extension.

    Methods:
        _validate_config() -> List[str]          # DEAD CODE -- never called
        _process(input_data) -> Dict[str, Any]   # Main entry point

    Inherited from BaseComponent:
        execute(input_data) -> Dict[str, Any]    # Orchestrates execution lifecycle
        _update_stats(rows, ok, reject) -> None  # Statistics accumulation
        _update_global_map() -> None             # GlobalMap stat propagation
        _resolve_java_expressions() -> None      # Java bridge expression resolution
        _auto_select_mode(input_data) -> Mode    # HYBRID mode selection
        _execute_batch(input_data) -> Dict       # Delegates to _process()
        _execute_streaming(input_data) -> Dict   # Chunks + pd.concat (CRASH RISK for dict return)
        validate_schema(df, schema) -> DataFrame # Schema validation (not used by this component)
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `FILE_NAME` | `FILE_NAME` (converter) / `file_path` (engine primary) | Mapped | -- (key normalization needed) |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix D: Detailed `_validate_config()` Analysis

The `_validate_config()` method (lines 45-69) validates:

```python
def _validate_config(self) -> List[str]:
    errors = []

    # Check for either new or legacy parameter
    file_path = self.config.get('file_path') or self.config.get('FILE_NAME')

    if not file_path:
        errors.append("Missing required config: 'file_path' (or legacy 'FILE_NAME')")
    elif not isinstance(file_path, str):
        errors.append("Config 'file_path' must be a string")
    elif not file_path.strip():
        errors.append("Config 'file_path' cannot be empty")

    # Optional field validation
    if 'check_directory' in self.config:
        if not isinstance(self.config['check_directory'], bool):
            errors.append("Config 'check_directory' must be a boolean")

    return errors
```

**Validations performed** (5 checks):
1. `file_path` is present (either `file_path` or `FILE_NAME` key)
2. `file_path` is not empty/None/False
3. `file_path` is a string (type check)
4. `file_path` is not whitespace-only (`.strip()` check)
5. `check_directory` is boolean (if present)

**Validations in `_process()` inline code** (1 check):
1. `file_path` is not empty/None/False (`if not file_path`)

**Gap**: The inline validation in `_process()` misses:
- Type check (`isinstance(file_path, str)`)
- Whitespace-only check (`file_path.strip()`)
- `check_directory` type validation

If `file_path` were set to a non-string value (e.g., `123`), the inline validation would pass (`if not 123` evaluates to `False` since `123` is truthy), and `os.path.exists(123)` would raise `TypeError: expected str, bytes or os.PathLike object, not int`. The `_validate_config()` method would catch this case with its `isinstance` check.

---

## Appendix E: Edge Case Analysis

### Edge Case 1: File exists

| Aspect | Detail |
|--------|--------|
| **Talend** | `{id}_EXISTS = true` in globalMap. Run If condition `((Boolean)globalMap.get("{id}_EXISTS"))` evaluates to `true`. |
| **V1** | `os.path.exists(file_path)` returns `True`. Result dict `{'file_exists': True}`. GlobalMap NOT updated with `{id}_EXISTS`. |
| **Verdict** | PARTIAL -- existence check is correct, but globalMap variable not set. |

### Edge Case 2: File does not exist

| Aspect | Detail |
|--------|--------|
| **Talend** | `{id}_EXISTS = false` in globalMap. Run If condition evaluates to `false`. |
| **V1** | `os.path.exists(file_path)` returns `False`. Result dict `{'file_exists': False}`. GlobalMap NOT updated. |
| **Verdict** | PARTIAL -- existence check is correct, but globalMap variable not set. |

### Edge Case 3: Directory exists (check_directory=False)

| Aspect | Detail |
|--------|--------|
| **Talend** | `File.exists()` returns `true` for directories. `{id}_EXISTS = true`. |
| **V1** | `os.path.exists(dir_path)` returns `True` (same as Talend). |
| **Verdict** | CORRECT |

### Edge Case 4: Directory exists (check_directory=True)

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- Talend does not have `check_directory` mode. |
| **V1** | `os.path.isdir(dir_path)` returns `True`. |
| **Verdict** | N/A -- non-standard extension. |

### Edge Case 5: File path is a directory (check_directory=True)

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- Talend does not have `check_directory` mode. `File.exists()` would return `true`. |
| **V1** | Wait -- this checks if a directory exists, not if the path is a directory. If `file_path="/some/dir"` and that dir exists, `os.path.isdir()` returns `True`. If `file_path="/some/file.txt"` (a file, not directory), `os.path.isdir()` returns `False` even though the file exists. |
| **Verdict** | **BEHAVIORAL DIVERGENCE from Talend** if `check_directory=True` is set. Talend would return `true` (file exists), V1 returns `False` (not a directory). |

### Edge Case 6: Empty string file path

| Aspect | Detail |
|--------|--------|
| **Talend** | Throws `NullPointerException` (empty string creates `File("")` which has undefined behavior). |
| **V1** | `if not file_path:` catches empty string. Raises `ValueError`. |
| **Verdict** | CORRECT -- V1 handles empty string more gracefully than Talend. |

### Edge Case 7: None file path

| Aspect | Detail |
|--------|--------|
| **Talend** | Throws `NullPointerException`. |
| **V1** | `self.config.get('file_path') or self.config.get('FILE_NAME')` returns `None`. `if not None:` is `True`. Raises `ValueError`. |
| **Verdict** | CORRECT |

### Edge Case 8: Whitespace-only file path

| Aspect | Detail |
|--------|--------|
| **Talend** | `File("   ").exists()` returns `false` (no file named with spaces only). |
| **V1** | `if not file_path:` evaluates `"   "` as truthy (non-empty string). Passes to `os.path.exists("   ")` which returns `False`. |
| **Verdict** | CORRECT -- both return false/False. However, `_validate_config()` would catch this with `file_path.strip()` check if it were called. |

### Edge Case 9: File path with context variable

| Aspect | Detail |
|--------|--------|
| **Talend** | Java resolves `context.input_dir + "/data.csv"` before the check. |
| **V1** | If converter marked it with `{{java}}`, Java bridge resolves it. If not (current state -- see CONV-FE-001), the raw expression string is passed to `os.path.exists()`, which will return `False` for a string like `context.input_dir + "/data.csv"`. Simple `${context.var}` patterns are resolved by `context_manager.resolve_dict()`. |
| **Verdict** | **GAP for Java expressions** -- complex expressions not resolved. Simple context vars work. |

### Edge Case 10: Symbolic link to existing target

| Aspect | Detail |
|--------|--------|
| **Talend** | `File.exists()` follows symlinks. Returns `true` if target exists. |
| **V1** | `os.path.exists()` follows symlinks. Returns `True` if target exists. |
| **Verdict** | CORRECT |

### Edge Case 11: Broken symbolic link

| Aspect | Detail |
|--------|--------|
| **Talend** | `File.exists()` follows symlinks. Returns `false` if target is missing. |
| **V1** | `os.path.exists()` returns `False` for broken symlinks. |
| **Verdict** | CORRECT |

### Edge Case 12: Permission denied on parent directory

| Aspect | Detail |
|--------|--------|
| **Talend** | `File.exists()` returns `false` (not an error). |
| **V1** | `os.path.exists()` returns `False` on permission denied. No error raised. |
| **Verdict** | CORRECT |

### Edge Case 13: NaN in config

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- Java does not have NaN in strings. |
| **V1** | If `file_path = float('nan')`, the inline `if not file_path:` evaluates `nan` as truthy. `os.path.exists(nan)` raises `TypeError`. The generic `except Exception` on line 115 catches this, logs the error, and re-raises. |
| **Verdict** | PARTIAL -- error is caught but message is not descriptive. `_validate_config()` would catch this with `isinstance(file_path, str)` if it were called. |

### Edge Case 14: Empty DataFrame as input

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- tFileExist does not accept row input. |
| **V1** | `_process()` declares `input_data: Optional[Any] = None` but never uses `input_data`. Any input is silently ignored. The existence check proceeds normally. |
| **Verdict** | CORRECT -- input is correctly ignored. |

### Edge Case 15: HYBRID streaming mode with non-None input

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- tFileExist does not accept row input. |
| **V1** | If the engine provides a DataFrame as input (e.g., from an upstream iterate component), `_auto_select_mode()` may select STREAMING mode for large DataFrames (> 3GB). `_execute_streaming()` would chunk the input and call `_process()` per chunk, collecting results. `pd.concat(results)` would crash because `result['main']` is a dict, not a DataFrame. |
| **Verdict** | **CRASH** -- streaming mode incompatible with dict return type. See PERF-FE-001. |

### Edge Case 16: File path with trailing slash

| Aspect | Detail |
|--------|--------|
| **Talend** | `new File("/data/input.csv/").exists()` -- Java normalizes the trailing slash. Returns the same as without trailing slash. |
| **V1** | `os.path.exists("/data/input.csv/")` -- Python also normalizes trailing slashes for files. Returns `True` if the file exists. |
| **Verdict** | CORRECT |

### Edge Case 17: File path with double slashes

| Aspect | Detail |
|--------|--------|
| **Talend** | `new File("/data//input.csv").exists()` -- Java normalizes double slashes. |
| **V1** | `os.path.exists("/data//input.csv")` -- Python also normalizes double slashes. |
| **Verdict** | CORRECT |

### Edge Case 18: File path with `..` components

| Aspect | Detail |
|--------|--------|
| **Talend** | `new File("/data/subdir/../input.csv").exists()` -- Java resolves `..` components. |
| **V1** | `os.path.exists("/data/subdir/../input.csv")` -- Python also resolves `..` components. |
| **Verdict** | CORRECT |

### Edge Case 19: Network path (UNC on Windows)

| Aspect | Detail |
|--------|--------|
| **Talend** | `new File("\\\\server\\share\\file.txt").exists()` -- Java handles UNC paths on Windows. |
| **V1** | `os.path.exists("\\\\server\\share\\file.txt")` -- Python handles UNC paths on Windows. On macOS/Linux, UNC paths are treated as local paths and will return `False`. |
| **Verdict** | CORRECT on Windows. N/A on macOS/Linux (UNC not applicable). |

### Edge Case 20: File being written by another process

| Aspect | Detail |
|--------|--------|
| **Talend** | `File.exists()` returns `true` even if the file is locked/being written. Existence check is atomic. |
| **V1** | `os.path.exists()` returns `True` even if the file is locked/being written. Same behavior. |
| **Verdict** | CORRECT |

### Edge Case 21: Race condition -- file deleted between check and use

| Aspect | Detail |
|--------|--------|
| **Talend** | TOCTOU (time-of-check-time-of-use) race: file may be deleted between `tFileExist` check and `tFileInputDelimited` read. Talend does not handle this. |
| **V1** | Same TOCTOU risk. `os.path.exists()` returns `True`, but file may be deleted before next component reads it. Not a V1-specific issue. |
| **Verdict** | CORRECT (same behavior as Talend -- both have TOCTOU vulnerability). |

### Edge Case 22: `file_path` config key takes precedence over `FILE_NAME`

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- only `FILE_NAME` parameter exists. |
| **V1** | `self.config.get('file_path') or self.config.get('FILE_NAME')` uses Python's `or` short-circuit. If `file_path` is set to an empty string (`""`), it is falsy, so `FILE_NAME` is used. If `file_path` is set to a non-empty value, `FILE_NAME` is ignored even if it differs. |
| **Verdict** | Acceptable. The `or` pattern means empty-string `file_path` correctly falls back to `FILE_NAME`. But if both are non-empty and different, `file_path` silently wins. This is unlikely in practice since the converter only sets `FILE_NAME`. |

### Edge Case 23: Config with `file_path = 0` (integer zero)

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- Java typing prevents this. |
| **V1** | `self.config.get('file_path') or self.config.get('FILE_NAME')`: Integer `0` is falsy, so falls through to `FILE_NAME`. If `FILE_NAME` is also not set, `file_path` resolves to `None`. If `FILE_NAME` is set, that value is used. The inline `if not file_path:` check would not catch this if `FILE_NAME` provides a valid string. However, `os.path.exists(0)` would raise `TypeError`. The `_validate_config()` `isinstance(file_path, str)` check would catch this -- if it were called. |
| **Verdict** | **PARTIAL GAP** -- type validation is dead code. Would be caught by `_validate_config()` if wired up. |

---

## Appendix F: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileExistComponent`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FE-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-FE-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| BUG-FE-003 | **P1** | `base_component.py` / multiple | `_validate_config()` is defined in many child components but never called by base class. Components with validation logic have dead validation. FileExistComponent, FileInputDelimited, FileDelete, FileArchive, FileUnarchive, FileOutputDelimited, FileOutputPositional, and many others are affected. A few components (SleepComponent, FileInputFullRowComponent, SendMailComponent, FileInputExcel) DO call `_validate_config()` from their `_process()` methods, but this is inconsistent. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix G: Implementation Fix Guides

### Fix Guide: ENG-FE-001 -- Set `{id}_EXISTS` in globalMap

**File**: `src/v1/engine/components/file/file_exist.py`
**Lines**: 107-113 (after existence check, before return)

**Current code (missing globalMap update)**:
```python
# Update statistics - existence checks always succeed as operations
self._update_stats(rows_processed, 1, 0)

result = {'file_exists': file_exists}

logger.info(f"[{self.id}] File existence check complete: "
            f"{check_type} '{file_path}' exists={file_exists}")
```

**Fix**:
```python
# Update statistics - existence checks always succeed as operations
self._update_stats(rows_processed, 1, 0)

# Set Talend-compatible globalMap variables
if self.global_map:
    self.global_map.put(f"{self.id}_EXISTS", file_exists)
    self.global_map.put(f"{self.id}_FILENAME", file_path)

result = {'file_exists': file_exists}

logger.info(f"[{self.id}] File existence check complete: "
            f"{check_type} '{file_path}' exists={file_exists}")
```

**And in the error handler** (after line 117):
```python
except Exception as e:
    logger.error(f"[{self.id}] File existence check failed: {e}")
    self._update_stats(rows_processed, 0, 1)
    if self.global_map:
        self.global_map.put(f"{self.id}_EXISTS", False)
        self.global_map.put(f"{self.id}_FILENAME", file_path)
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
    raise
```

**Impact**: Enables ALL Run If conditions based on file existence. Enables downstream globalMap references to filename and error messages. **Risk**: Very low (additive change; no existing behavior modified).

---

### Fix Guide: ENG-FE-004 -- Change return to None for main

**File**: `src/v1/engine/components/file/file_exist.py`
**Line**: 120

**Current code**:
```python
return {'main': result}
```

**Fix**:
```python
return {'main': None}
```

**Explanation**: tFileExist has no row output in Talend. The existence result should be communicated exclusively through globalMap variables (after implementing Fix ENG-FE-001). Returning `None` for `main` prevents the engine from storing a dict in `data_flows` and prevents the streaming mode crash. This aligns with `FileDelete`'s pattern: `return {'main': None, 'status': status_message}`.

**Impact**: Prevents streaming mode crash. Aligns with Talend behavior (no row output). **Risk**: Low. Any code that currently reads `result['main']['file_exists']` must switch to reading `global_map.get(f"{id}_EXISTS")` instead.

---

### Fix Guide: BUG-FE-001 -- `_update_global_map()` undefined variable

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

### Fix Guide: BUG-FE-002 -- `GlobalMap.get()` undefined default

**File**: `src/v1/engine/global_map.py`
**Lines**: 26-28

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

### Fix Guide: CONV-FE-001 -- Add Java expression marking

**File**: `src/converters/complex_converter/component_parser.py`
**Lines**: 1691-1695

**Current code**:
```python
def parse_tfileexist(self, node, component: Dict) -> Dict:
    """Parse tFileExist specific configuration"""
    file_name = node.find('.//elementParameter[@name="FILE_NAME"]').get('value', '')
    component['config']['FILE_NAME'] = file_name.strip('"')
    return component
```

**Fix**:
```python
def parse_tfileexist(self, node, component: Dict) -> Dict:
    """Parse tFileExist specific configuration"""
    file_name_node = node.find('.//elementParameter[@name="FILE_NAME"]')
    if file_name_node is not None:
        file_name = file_name_node.get('value', '')
        file_name = file_name.strip('"')
        component['config']['file_path'] = self.expr_converter.mark_java_expression(file_name)
    else:
        component['config']['file_path'] = ''
    return component
```

**Key improvements**:
1. Adds `None` guard on `.find()` result (fixes CONV-FE-003)
2. Marks Java expressions via `mark_java_expression()` (fixes CONV-FE-001)
3. Changes config key from `FILE_NAME` to `file_path` (fixes NAME-FE-001)

**Impact**: Enables Java expression resolution in file paths. **Risk**: Low. Requires engine `_process()` to be updated to use `file_path` as the primary config key (already the case).

---

### Fix Guide: BUG-FE-003 -- Wire up `_validate_config()`

**File**: `src/v1/engine/components/file/file_exist.py`

**Add at the beginning of `_process()`** (before line 86):
```python
def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
    config_errors = self._validate_config()
    if config_errors:
        error_msg = "; ".join(config_errors)
        logger.error(f"[{self.id}] Configuration validation failed: {error_msg}")
        raise ValueError(f"[{self.id}] {error_msg}")

    # Support both new and legacy parameter names for backward compatibility
    file_path = self.config.get('file_path') or self.config.get('FILE_NAME')
    # ...rest of _process()
```

**Remove the duplicate inline validation** (lines 93-96):
```python
# REMOVE:
if not file_path:
    error_msg = "Missing required config: 'file_path' (or legacy 'FILE_NAME')"
    logger.error(f"[{self.id}] {error_msg}")
    raise ValueError(f"[{self.id}] {error_msg}")
```

**Impact**: Activates comprehensive config validation (type checks, whitespace checks, check_directory type). **Risk**: Low. May surface previously silent config errors.

---

## Appendix H: Comparison with Other File Utility Components

| Feature | tFileExist (V1) | tFileDelete (V1) | tFileCopy (V1) | tFileTouch (V1) | tFileProperties (V1) | tFileRowCount (V1) |
|---------|-----------------|-------------------|-----------------|-----------------|----------------------|---------------------|
| Basic operation | Yes | Yes | Yes | Yes | Yes | Yes |
| Returns DataFrame in `main` | **No (dict)** | No (None) | **Yes (dict)** | **Yes (dict)** | Yes (DataFrame) | **Yes (dict)** |
| `_validate_config()` defined | Yes | Yes | No | No | Yes | Yes |
| `_validate_config()` called | **No** | **No** | N/A | N/A | **No** | **No** |
| Sets component-specific globalMap vars | **No** | **No** | **No** | **No** | **No** | **No** |
| Uses custom exceptions | **No** | Yes (FileOperationError) | No | No | Yes (FileOperationError) | No |
| V1 Unit tests | **No** | **No** | **No** | **No** | **No** | **No** |
| Converter marks Java expressions | **No** | **No** | **No** | **No** | **No** | **No** |

**Observations**:
1. The `_validate_config()` dead code pattern is endemic across ALL file utility components. Only a few components (SleepComponent, FileInputFullRowComponent, SendMailComponent, FileInputExcel) actually call it.
2. NO file utility component sets component-specific globalMap variables (EXISTS, FILENAME, etc.). This is a systemic architectural gap.
3. Return type inconsistency: some return `None` for `main`, some return dicts, some return DataFrames. There is no consistent pattern.
4. NO file utility component has v1 unit tests. Testing gap is systemic.
5. NO utility component converter marks Java expressions. This is a systemic converter gap.

---

## Appendix I: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs using Run If with `{id}_EXISTS` | **Critical** | ANY job using tFileExist for conditional routing | Must implement `{id}_EXISTS` globalMap variable (Fix ENG-FE-001) |
| Jobs with Java expressions in file path | **High** | Jobs using `context.dir + "/file.csv"` or routine calls in FILE_NAME | Must add Java expression marking in converter (Fix CONV-FE-001) |
| Jobs referencing `{id}_FILENAME` downstream | **Medium** | Jobs with audit/logging using resolved filename | Must set `{id}_FILENAME` in globalMap |
| Jobs with tFileExist in iterate loops | **Medium** | Jobs using tFileList -> tFileExist pattern | Verify iterate variable resolution works |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs using tFileExist with simple static paths | Low | `os.path.exists()` works correctly for simple paths |
| Jobs using only OnSubjobOk/OnComponentOk triggers | Low | Trigger connections work through engine's TriggerManager |
| Jobs with `check_directory` not set | Low | Default `False` matches Talend behavior |
| Jobs using context variables (simple `${context.var}`) | Low | `context_manager.resolve_dict()` handles these |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (BUG-FE-001, BUG-FE-002 cross-cutting; ENG-FE-001 for EXISTS variable). These are blockers for ANY job using tFileExist.
2. **Phase 2**: Add Java expression marking in converter (CONV-FE-001). Test with jobs that have expressions in FILE_NAME.
3. **Phase 3**: Change return type to `None` for `main` (ENG-FE-004). Audit all code that reads `result['main']` from tFileExist.
4. **Phase 4**: Create unit and integration tests. Verify Run If conditional logic works end-to-end.
5. **Phase 5**: Parallel-run migrated jobs against Talend originals. Verify conditional routing matches.

---

## Appendix J: Talend Generated Java Code Pattern

For reference, Talend generates the following Java code for a tFileExist component named `tFileExist_1` checking file `/data/input.csv`:

```java
// tFileExist_1 begin
java.io.File file_tFileExist_1 = new java.io.File("/data/input.csv");
globalMap.put("tFileExist_1_EXISTS", file_tFileExist_1.exists());
globalMap.put("tFileExist_1_FILENAME", file_tFileExist_1.getAbsolutePath());
// tFileExist_1 end
```

The generated code:
1. Creates a `java.io.File` object from the configured path
2. Calls `exists()` and stores the boolean result in globalMap as `{id}_EXISTS`
3. Calls `getAbsolutePath()` and stores the resolved path as `{id}_FILENAME`

A downstream `Run If` connection from `tFileExist_1` to another component would generate:

```java
// Run If condition
if (((Boolean)globalMap.get("tFileExist_1_EXISTS"))) {
    // Execute downstream component
}
```

Or for the negated case (file does NOT exist):

```java
if (!((Boolean)globalMap.get("tFileExist_1_EXISTS"))) {
    // Execute downstream component
}
```

This is the pattern that the v1 engine must replicate to achieve feature parity. The `EXISTS` variable must be set BEFORE trigger evaluation occurs.

---

## Appendix K: Complete Recommended Engine Implementation

The following is the recommended rewrite of `file_exist.py` that addresses all identified issues:

```python
"""
tFileExist component - Checks if a file exists at a specified path

Talend equivalent: tFileExist
"""

import os
from typing import Dict, Any, List, Optional
import logging

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class FileExistComponent(BaseComponent):
    """
    Checks if a file or directory exists at the specified path.

    Configuration:
        file_path (str): Path to the file or directory to check. Required.
            Also accepts legacy 'FILE_NAME' parameter for backward compatibility.

    Inputs:
        None: This component does not process input data

    Outputs:
        main: None (no row output -- tFileExist is a utility component)

    GlobalMap Variables Set:
        {id}_EXISTS (bool): Whether the specified path exists
        {id}_FILENAME (str): The resolved file path that was checked
        {id}_ERROR_MESSAGE (str): Error message if check failed

    Statistics:
        NB_LINE: Number of existence checks performed (always 1)
        NB_LINE_OK: Number of successful checks
        NB_LINE_REJECT: Number of failed checks

    Example configuration:
    {
        "file_path": "/path/to/file.txt"
    }
    """

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        file_path = self.config.get('file_path') or self.config.get('FILE_NAME')

        if not file_path:
            errors.append("Missing required config: 'file_path' (or legacy 'FILE_NAME')")
        elif not isinstance(file_path, str):
            errors.append("Config 'file_path' must be a string")
        elif not file_path.strip():
            errors.append("Config 'file_path' cannot be empty or whitespace-only")

        return errors

    def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
        """
        Check if the file or directory exists.

        Args:
            input_data: Not used for this component

        Returns:
            Dictionary containing:
                - 'main': None (no row output)

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Validate configuration
        config_errors = self._validate_config()
        if config_errors:
            error_msg = "; ".join(config_errors)
            logger.error(f"[{self.id}] Configuration validation failed: {error_msg}")
            raise ValueError(f"[{self.id}] {error_msg}")

        file_path = self.config.get('file_path') or self.config.get('FILE_NAME')

        logger.info(f"[{self.id}] File existence check started: {file_path}")

        try:
            file_exists = os.path.exists(file_path)

            # Set Talend-compatible globalMap variables
            if self.global_map:
                self.global_map.put(f"{self.id}_EXISTS", file_exists)
                self.global_map.put(f"{self.id}_FILENAME", file_path)

            self._update_stats(1, 1, 0)

            logger.info(f"[{self.id}] File existence check complete: "
                        f"'{file_path}' exists={file_exists}")

        except Exception as e:
            logger.error(f"[{self.id}] File existence check failed: {e}")
            self._update_stats(1, 0, 1)
            if self.global_map:
                self.global_map.put(f"{self.id}_EXISTS", False)
                self.global_map.put(f"{self.id}_FILENAME", file_path)
                self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
            raise

        return {'main': None}
```

**Key changes from current implementation**:
1. Calls `_validate_config()` from `_process()` (fixes BUG-FE-003)
2. Removes duplicate inline validation (fixes BUG-FE-004)
3. Sets `{id}_EXISTS`, `{id}_FILENAME`, `{id}_ERROR_MESSAGE` in globalMap (fixes ENG-FE-001, ENG-FE-002, ENG-FE-003)
4. Returns `{'main': None}` instead of `{'main': dict}` (fixes ENG-FE-004, BUG-FE-005)
5. Removes non-standard `check_directory` parameter (fixes ENG-FE-005)
6. Updates docstring to document globalMap variables

---

## Appendix L: Base Component `_update_global_map()` Detailed Analysis

The `_update_global_map()` method in `base_component.py` (lines 298-304) is critical because it propagates component statistics to the global map after every execution:

```python
def _update_global_map(self) -> None:
    """Update global map with component statistics"""
    if self.global_map:
        for stat_name, stat_value in self.stats.items():
            self.global_map.put_component_stat(self.id, stat_name, stat_value)
        # Log the statistics for debugging
        logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} "
                     f"NB_LINE_OK:{self.stats['NB_LINE_OK']} "
                     f"NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} "
                     f"{stat_name}: {value}")  # BUG: 'value' is undefined
```

**Bug analysis** (BUG-FE-001):
- The for loop variable is `stat_value` (line 301), but the log statement references `value` (line 304)
- `stat_name` on line 304 references the loop variable from line 301, which will have the value from the LAST iteration of the for loop (i.e., `EXECUTION_TIME` since that is the last key in the `stats` dict)
- `value` is completely undefined in this scope, causing `NameError`
- This method is called from `execute()` (line 218) after EVERY component execution
- Since `self.global_map` is set by the engine during component instantiation, this bug will crash ANY component that runs in a job with a global map configured

**Call chain for FileExistComponent**:
1. `ETLEngine._execute_component()` calls `component.execute(None)` (FileExistComponent receives no input data)
2. `BaseComponent.execute()` calls `self._process(None)` via `_execute_batch()` (line 214)
3. `_process()` performs existence check, calls `self._update_stats(1, 1, 0)`, returns `{'main': result}`
4. `execute()` sets `self.stats['EXECUTION_TIME']` (line 217)
5. `execute()` calls `self._update_global_map()` (line 218)
6. `_update_global_map()` iterates `self.stats.items()`, successfully calls `put_component_stat()` for all stats
7. **CRASH**: Log statement on line 304 references `{value}` which is undefined -> `NameError`
8. Exception propagates to `execute()` line 227 -> caught -> `self.status = ComponentStatus.ERROR`
9. `execute()` calls `self._update_global_map()` AGAIN on line 231 (error path) -> **SECOND CRASH**
10. Second NameError propagates uncaught from `execute()` -> component appears to have failed

**Severity**: This is the highest-severity bug in the v1 engine. It prevents ANY component from completing execution when a global map is present. The fix is trivial (see Appendix G) but the impact is universal.

**Important note**: The stats ARE successfully stored in globalMap (via `put_component_stat()` in the for loop on lines 301-302) BEFORE the log statement crashes. The crash happens on the LOG line, not the data storage line. This means the globalMap data is correct; only the logging is broken. However, the `NameError` exception still causes the entire `execute()` method to fail.

---

## Appendix M: `GlobalMap.get()` Detailed Analysis

The `GlobalMap.get()` method in `global_map.py` (lines 26-28) has a complementary bug:

```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)  # BUG: 'default' not in signature
```

**Bug analysis** (BUG-FE-002):
- `default` is referenced in the body (line 28) but is not a parameter in the method signature (line 26)
- The method signature only accepts `key: str`
- Any call to `global_map.get("some_key")` will crash with `NameError: name 'default' is not defined`

**Cascading impact on FileExistComponent**:
- After implementing Fix ENG-FE-001 (setting `{id}_EXISTS` in globalMap), downstream components would call `global_map.get("tFileExist_1_EXISTS")` to read the value
- This `get()` call would crash with `NameError` due to the undefined `default` parameter
- `get_component_stat()` (line 51-58) calls `self.get(key, default)` with TWO arguments, but `get()` only accepts ONE positional argument. This would cause `TypeError: get() takes 2 positional arguments but 3 were given`
- `get_nb_line()`, `get_nb_line_ok()`, `get_nb_line_reject()` all call `get_component_stat()` which calls `get()` with two args

**Fix**: Add `default: Any = None` to the `get()` method signature. This fixes both the `NameError` (direct calls) and the `TypeError` (two-argument calls from `get_component_stat()`).

**Workaround**: While `get()` is broken, `global_map.put()` works correctly (it does not call `get()`). The `put()` method (lines 21-24) simply sets `self._map[key] = value`. So data CAN be stored in globalMap; it just cannot be reliably retrieved via the `get()` method. Direct access to `global_map._map[key]` would work but is a violation of encapsulation.

---

## Appendix N: Engine Component Execution Flow for FileExistComponent

This appendix traces the complete execution flow for a typical tFileExist component in a v1 engine job.

### Step 1: Component Instantiation

```
ETLEngine._setup_components() ->
    component_config = job['components'][i]  # e.g., {"id": "tFileExist_1", "type": "FileExistComponent", "config": {"FILE_NAME": "/data/input.csv"}}
    component_class = COMPONENT_REGISTRY['FileExistComponent']  # = FileExistComponent
    component = FileExistComponent(
        component_id="tFileExist_1",
        config={"FILE_NAME": "/data/input.csv"},
        global_map=self.global_map,
        context_manager=self.context_manager
    )
    # BaseComponent.__init__() sets:
    #   self.id = "tFileExist_1"
    #   self.config = {"FILE_NAME": "/data/input.csv"}
    #   self.execution_mode = ExecutionMode.HYBRID
    #   self.status = ComponentStatus.PENDING
    #   self.stats = {'NB_LINE': 0, 'NB_LINE_OK': 0, 'NB_LINE_REJECT': 0, ...}
```

### Step 2: Component Execution

```
ETLEngine._execute_component("tFileExist_1") ->
    input_data = self._get_input_data("tFileExist_1")  # Returns None (no incoming flows)
    result = component.execute(None)
```

### Step 3: BaseComponent.execute() Lifecycle

```
BaseComponent.execute(None) ->
    self.status = ComponentStatus.RUNNING
    start_time = time.time()

    # Step 1: Resolve Java expressions ({{java}} markers)
    if self.java_bridge:
        self._resolve_java_expressions()  # Scans config for {{java}} prefix

    # Step 2: Resolve context variables (${context.var})
    if self.context_manager:
        self.config = self.context_manager.resolve_dict(self.config)
        # e.g., {"FILE_NAME": "/data/input.csv"} -> no change if no context vars

    # Step 3: Determine execution mode
    # HYBRID mode -> _auto_select_mode(None) -> BATCH (None input -> always BATCH)

    # Step 4: Execute in batch mode
    result = self._execute_batch(None)
        -> return self._process(None)
```

### Step 4: FileExistComponent._process()

```
FileExistComponent._process(None) ->
    file_path = self.config.get('file_path') or self.config.get('FILE_NAME')
    # file_path = "/data/input.csv"

    check_directory = self.config.get('check_directory', False)
    # check_directory = False

    # Inline validation
    if not file_path:  # False -- file_path is truthy
        pass

    # Existence check
    file_exists = os.path.exists("/data/input.csv")  # True or False

    # Stats update
    self._update_stats(1, 1, 0)
    # self.stats = {'NB_LINE': 1, 'NB_LINE_OK': 1, 'NB_LINE_REJECT': 0, ...}

    result = {'file_exists': file_exists}

    return {'main': result}
    # Returns {'main': {'file_exists': True}}
```

### Step 5: Post-execution in execute()

```
    # Back in execute():
    self.stats['EXECUTION_TIME'] = time.time() - start_time

    self._update_global_map()
    # CRASH: NameError on line 304 (see BUG-FE-001)

    # If BUG-FE-001 were fixed:
    self.status = ComponentStatus.SUCCESS
    result['stats'] = self.stats.copy()
    return result
    # Returns {'main': {'file_exists': True}, 'stats': {'NB_LINE': 1, ...}}
```

### Step 6: Engine stores result

```
    # Back in _execute_component():
    for flow in self.job_config.get('flows', []):
        if flow['from'] == 'tFileExist_1':
            if flow['type'] == 'flow' and 'main' in result:
                self.data_flows[flow['name']] = result['main']
                # Stores {'file_exists': True} as a flow -- NOT a DataFrame
                # This will confuse downstream components expecting DataFrame

    self.trigger_manager.set_component_status('tFileExist_1', 'success')
    # Triggers On Component Ok, On Subjob Ok
    # Run If conditions evaluate -- but {id}_EXISTS not in globalMap (see ENG-FE-001)
```

### What SHOULD Happen (After All Fixes)

After implementing fixes ENG-FE-001, ENG-FE-004, BUG-FE-001, and BUG-FE-002:

1. `_process()` sets `global_map.put("tFileExist_1_EXISTS", True)` and `global_map.put("tFileExist_1_FILENAME", "/data/input.csv")`
2. `_process()` returns `{'main': None}` (no row output)
3. `_update_global_map()` propagates stats without crashing
4. Engine stores `None` in data_flows (no downstream data to pass)
5. TriggerManager evaluates Run If conditions, which can now read `global_map.get("tFileExist_1_EXISTS")` -> `True`
6. Downstream components execute conditionally based on the EXISTS value

---

## Appendix O: Detailed Converter Expression Handling for tFileExist

### How Context Variables Should Flow Through the Converter

When a Talend job contains `context.input_dir` in the `FILE_NAME` parameter, the following transformation chain should occur (but currently does not for tFileExist):

1. **Talend XML**: `<elementParameter name="FILE_NAME" value="&quot;/data/&quot;+context.input_dir+&quot;/input.csv&quot;" />`

2. **After XML parse**: `"/data/"+context.input_dir+"/input.csv"` (Python XML parser decodes `&quot;`)

3. **In `parse_tfileexist()` (current behavior)**:
   - Calls `file_name.strip('"')` which strips the outer quotes
   - Result: `/data/"+context.input_dir+"/input.csv` (incomplete stripping -- only leading/trailing quotes removed)
   - Stores as `FILE_NAME` in config
   - **No Java expression marking** -- the `+` operators are not detected

4. **At engine runtime** (`BaseComponent.execute()`):
   - `_resolve_java_expressions()` scans for `{{java}}` prefix -- NOT found (converter did not mark it)
   - `context_manager.resolve_dict()` scans for `${context.var}` patterns -- NOT found (converter did not wrap it)
   - The raw string `/data/"+context.input_dir+"/input.csv` is passed to `os.path.exists()`
   - Returns `False` (path does not exist because it is a literal string, not resolved)

5. **What SHOULD happen** (after CONV-FE-001 fix):
   - `parse_tfileexist()` calls `mark_java_expression(file_name)` after stripping quotes
   - `mark_java_expression()` detects the `+` operator and prefixes with `{{java}}`
   - At runtime, `_resolve_java_expressions()` detects the `{{java}}` prefix
   - Sends to Java bridge for evaluation
   - Java bridge resolves `context.input_dir` and concatenates strings
   - Result: `/data/inputs/input.csv` (example)
   - `os.path.exists("/data/inputs/input.csv")` returns correct result

### Simple Context Variable Pattern

For the simpler case where the file path is just `context.filepath` (no operators):

1. **Talend XML**: `<elementParameter name="FILE_NAME" value="context.filepath" />`

2. **In `parse_tfileexist()` (current behavior)**:
   - `strip('"')` has no effect (no surrounding quotes)
   - Stores `context.filepath` as `FILE_NAME`

3. **At engine runtime**:
   - `context_manager.resolve_dict()` scans for `context.` in string values
   - If the ContextManager implementation resolves bare `context.var` patterns (without `${...}` wrapper), this works
   - If it only resolves `${context.var}` patterns, this fails silently

**Risk assessment**: The behavior depends on the ContextManager implementation. Testing is required to verify whether bare `context.var` strings are resolved.

---

## Appendix P: Comparison of Return Types Across File Components

This appendix documents the inconsistent return type patterns across v1 file components, which is the root cause of BUG-FE-005 and PERF-FE-001.

| Component | Returns for `main` | Type | Consistent with Talend? |
|-----------|-------------------|------|------------------------|
| `FileExistComponent` | `{'file_exists': bool}` | dict | **No** -- Talend has no row output |
| `FileDelete` | `None` | NoneType | **Yes** -- Talend has no row output |
| `FileCopy` | `{'source': str, 'destination': str, 'status': str}` | dict | **No** -- Talend has no row output |
| `FileTouch` | `{'status': str, 'message': str}` | dict | **No** -- Talend has no row output |
| `FileProperties` | DataFrame | DataFrame | **Yes** -- Talend outputs property data as rows |
| `FileRowCount` | `{'row_count': int}` | dict | **No** -- Talend sets NB_LINE in globalMap, no row output |
| `FileInputDelimited` | DataFrame | DataFrame | **Yes** -- Talend outputs data rows |
| `FileOutputDelimited` | DataFrame (passthrough) | DataFrame | **Yes** -- Talend passes through input data |

**Pattern analysis**:
- **Utility components** (no Talend row output): FileDelete correctly returns `None`. FileExist, FileCopy, FileTouch, FileRowCount incorrectly return dicts.
- **I/O components** (Talend row output): FileInputDelimited, FileOutputDelimited, FileProperties correctly return DataFrames.

**Recommendation**: All utility components that have no Talend row output should return `{'main': None}`. Component-specific data (existence status, copy status, row count) should be stored in globalMap variables, matching Talend's behavior.

### Impact on Engine Execution

When `result['main']` is a dict (not DataFrame or None), the engine's `_execute_component()` on line 571-572 stores it in `data_flows`:

```python
if flow['type'] == 'flow' and 'main' in result and result['main'] is not None:
    self.data_flows[flow['name']] = result['main']
```

Since `result['main'] = {'file_exists': True}` is not `None`, it passes the check and gets stored in `data_flows`. If a downstream component reads this flow expecting a DataFrame:

```python
input_data = self.data_flows.get(flow_name)
# input_data = {'file_exists': True}  -- a dict, not DataFrame
# Downstream component calls input_data.columns -> AttributeError
```

In practice, tFileExist typically has no downstream flow connections (only trigger connections), so this issue rarely manifests. But it is an architectural violation that should be fixed.

---

## Appendix Q: Source References

- [tFileExist Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tfileexist/tfileexist-standard-properties) -- Official Talend documentation for Basic and Advanced Settings, connection types, and global variables.
- [tFileExist Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tfileexist/tfileexist-standard-properties) -- Talend 8.0 documentation.
- [tFileExist Overview (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tfileexist) -- Component overview, family, and framework support.
- [tFileExist Scenario (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tfileexist/tfileexist-scenario) -- Usage scenario with tFileInputDelimited and tMsgBox.
- [tFileExist ESB 7.x (Talend Skill)](https://talendskill.com/talend-for-esb-docs/docs-7-x/tfileexist-talend-open-studio-for-esb-document-7-x/) -- ESB documentation with global variable details.
- [tFileExist ESB 6.x (Talend Skill)](https://talendskill.com/talend-for-esb-docs/docs-6-x/tfileexist-docs-for-esb-6-x/) -- Earlier ESB documentation.
- [tFileExist Community Discussion -- EXISTS variable](https://community.talend.com/s/feed/0D53p00007vCpTMCA0?language=en_US) -- Community discussion on `((Boolean)globalMap.get("tFileExist_1_EXISTS"))` pattern.
- [tFileExist for Multiple Files (Community)](https://community.talend.com/t5/Design-and-Development/resolved-tFileExist-for-multiple-files/m-p/59934) -- Community discussion on using tFileExist with iteration.
- [Checking for File Presence (Talend 8.0 Scenario)](https://help.qlik.com/talend/en-US/components/8.0/tfileexist/tfileexist-tfileinputdelimited-tfileoutputdelimited-tmsgbox-checking-for-presence-of-file-and-creating-it-if-it-does-not-exist-standard-component-this) -- Step-by-step scenario for file existence checking and conditional creation.
