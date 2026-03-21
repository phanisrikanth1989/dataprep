# Audit Report: tPython / PythonComponent

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tPython` (non-standard -- see Section 3) |
| **V1 Engine Class** | `PythonComponent` |
| **Engine File** | `src/v1/engine/components/transform/python_component.py` (134 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` falls through to `else` (line 384-386): returns raw `config_raw` unchanged |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> NO dedicated `elif` branch for `tPython`; falls through generic path after `parse_base_component()` |
| **Registry Aliases** | `PythonComponent`, `Python`, `tPython` (registered in `src/v1/engine/engine.py` lines 139-141) |
| **Category** | Transform / Custom Code |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/python_component.py` | Engine implementation (134 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 384-386) | Falls through to default `else` -- returns raw config |
| `src/converters/complex_converter/converter.py` (lines 216-382) | NO `elif` for `tPython`; no dedicated parser call |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()`, `get_python_routines()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/python_routine_manager.py` | PythonRoutineManager: discovers, loads, and exposes `.py` routine files |
| `src/v1/engine/context_manager.py` | ContextManager: variable resolution, `get_all()`, `resolve_dict()` |
| `src/v1/engine/components/transform/__init__.py` | Package exports (line 17: exports `PythonComponent`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **R** | 1 | 1 | 0 | 0 | `CODE` field explicitly SKIPPED during generic parsing; `python_code` never extracted; tPython has no dedicated parser and no `_map_component_parameters` branch |
| Engine Feature Parity | **Y** | 0 | 3 | 3 | 1 | No `die_on_error`; unrestricted `exec()`; no `__builtins__` restriction; no data modification; no REJECT flow |
| Code Quality | **R** | 2 | 4 | 4 | 1 | Cross-cutting `_update_global_map()` crash; `GlobalMap.get()` crash; `resolve_dict` corrupts `python_code` (BUG-PC-007); error masking (BUG-PC-008); `exec()` with full namespace; frame introspection escape (SEC-PC-003); duplicated `_get_context_dict()` |
| Performance & Memory | **G** | 0 | 0 | 1 | 0 | Unnecessary `os`/`sys` import per execution; otherwise lightweight |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests |

**Overall: RED -- Not production-ready; converter cannot extract code, cross-cutting crashes block all execution**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tPython Does (or Does Not Exist)

`tPython` is **NOT a standard Talend Studio component**. Unlike `tJava` and `tJavaRow`, which are first-class components shipped in all Talend distributions, there is no official `tPython` component from Talend/Qlik. The closest official mechanism is:

1. **Severus Snake** -- a community/third-party Talend Component Kit component that allows Python execution within Talend jobs. It requires JEP (Java Embedded Python) and provides `Python Home` and `Script` configuration properties.
2. **tSystem** -- can invoke Python scripts as external processes.
3. **Talend Cloud / Pipeline Designer** -- some newer Talend products offer Python processors, but these are not the classic Studio `tPython`.

**Source**: [Severus Snake (GitHub)](https://github.com/ottensa/severus-snake), [Talend Component Reference](https://www.talendbyexample.com/talend-component-reference.html)

The v1 engine's `PythonComponent` is therefore a **custom extension** analogous to `tJava` (the `JavaComponent`), but for Python code execution. Its docstring explicitly states: "This component mimics Talend's tJava functionality." Since there is no official Talend spec, the feature baseline is derived from the `tJava` component behavior and the component's own documented contract.

**Component family**: Transform / Custom Code (analogous to tJava)
**Available in**: Custom ETL-AGENT only; not a standard Talend component

### 3.1 Expected Parameters (Derived from tJava Analogy and Engine Contract)

| # | Parameter | Expected Config Key | Type | Default | Description |
|---|-----------|---------------------|------|---------|-------------|
| 1 | Python Code | `python_code` | CODE (multi-line string) | -- | **Mandatory**. Python code to execute once per job execution. Equivalent to tJava's `CODE` parameter. |
| 2 | Imports | `imports` | IMPORT (multi-line string) | `''` | Optional Python import statements. Analogous to tJava's `IMPORT` parameter. Not currently consumed by engine. |
| 3 | Die On Error | `die_on_error` | Boolean | `false` | Whether to stop the entire job on execution error. Standard across all Talend components. |

### 3.2 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input/Output | Row > Main | Input data passes through unchanged after code execution. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when subjob fails. |

### 3.3 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of input rows (pass-through count). |
| `{id}_NB_LINE_OK` | Integer | After execution | Same as NB_LINE (all rows pass through). |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Always 0 (no reject mechanism). |
| `{id}_ERROR_MESSAGE` | String | On error | Not implemented. Should store last error message. |

### 3.4 Behavioral Notes

1. **One-time execution**: The Python code executes ONCE per job run, not per row. This is the key distinction from `PythonRowComponent` (analogous to tJavaRow vs tJava).

2. **Pass-through behavior**: Input data flows through unchanged. The component is a side-effect-only processor -- it does not modify the DataFrame. User code can set globalMap variables, initialize resources, perform calculations, etc.

3. **Namespace exposure**: User code has access to `context` (flat dict), `globalMap` (live GlobalMap object), `routines` (loaded Python routine modules), plus common builtins and modules (`pd`, `datetime`, `os`, `sys`).

4. **No Talend XML spec**: Since tPython is not a standard Talend component, there is no official XML parameter schema. The converter must handle it as a custom component type, and jobs using tPython are either hand-crafted or from a Talend installation with the Severus Snake plugin.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter handles `tPython` through the **generic path** with a critical failure:

**Converter flow**:
1. `converter.py:_parse_component()` has NO `elif component_type == 'tPython'` branch (confirmed by searching all 382 lines of `_parse_component()`).
2. Falls through to `self.component_parser.parse_base_component(node)` (line 226).
3. `parse_base_component()` iterates `elementParameter` nodes (lines 434-458).
4. **Line 448-449**: `CODE` and `IMPORT` fields are **explicitly skipped** with the comment: `"Skip CODE and IMPORT fields - they contain raw Java code and are handled by component-specific parsers (tJava, tJavaRow)"`.
5. `_map_component_parameters('tPython', config_raw)` is called (line 472).
6. No `elif` matches `tPython` in `_map_component_parameters()`, so the `else` branch (line 384-386) returns `config_raw` as-is.
7. Result: `config_raw` contains all parameters EXCEPT `CODE` and `IMPORT`, which were skipped in step 4.

**The `python_code` field that the engine requires will NEVER be populated from a Talend XML conversion.** This is a complete converter failure for this component.

| # | Expected Parameter | Extracted? | V1 Config Key | Notes |
|---|-------------------|------------|---------------|-------|
| 1 | `CODE` | **No** | `python_code` | **Explicitly skipped** on line 448-449 of `component_parser.py`. The skip comment references tJava/tJavaRow but affects ALL components going through the generic path, including tPython. |
| 2 | `IMPORT` | **No** | `imports` | **Explicitly skipped** on same line. |
| 3 | `DIE_ON_ERROR` | **Yes** (if CHECK field) | `DIE_ON_ERROR` | Extracted as raw key name (not mapped to `die_on_error`). Engine does not read `DIE_ON_ERROR`. |
| 4 | `LABEL` | Yes | `LABEL` | Cosmetic, no runtime impact. |
| 5 | `UNIQUE_NAME` | Yes (component ID) | -- | Extracted in `parse_base_component()` lines 396-398. |

**Java expression marking**: Line 462 of `component_parser.py` skips Java expression marking for `tJavaRow` and `tJava` but does NOT skip `tPython`. If tPython's non-code config values happen to contain Java-like strings, they would be incorrectly marked with `{{java}}` prefix.

**Summary**: 0 of 2 required parameters extracted (0%). The component is **completely non-functional** when converted from Talend XML.

### 4.2 Schema Extraction

Schema is extracted generically in `parse_base_component()` (lines 474-508). For tPython, this provides FLOW and REJECT metadata schemas if present in the XML. However, since the component passes data through unchanged, the schema is only informational.

### 4.3 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-PC-001 | **P0** | **`CODE` field skipped -- `python_code` never extracted**: The generic `parse_base_component()` explicitly skips `CODE` and `IMPORT` parameters (line 448-449). Since tPython has no dedicated parser and no `_map_component_parameters` branch, the Python code is permanently lost during conversion. Any converted tPython component will have an empty config and raise `ValueError: 'python_code' is required` at runtime. |
| CONV-PC-002 | **P1** | **No dedicated parser method**: tPython uses the generic fallback path. Per STANDARDS.md, every component MUST have its own `parse_*` method. A dedicated `parse_tpython()` method should extract `CODE` as `python_code`, `IMPORT` as `imports`, decode XML entities (`&#xD;&#xA;` to `\n`), and handle `DIE_ON_ERROR`. The tJava parser (lines 332-346) is the exact template to follow. |
| CONV-PC-003 | **P1** | **No `elif` branch in `converter.py:_parse_component()`**: Unlike `tJavaRow` which has `elif component_type == 'tJavaRow': component = self.component_parser.parse_java_row(node, component)` (line 375-376), there is no corresponding branch for `tPython`. This must be added to invoke the dedicated parser. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|---------|-------------|----------|-----------------|-------|
| 1 | Execute one-time Python code | **Yes** | High | `_process()` line 101 | `exec(python_code, namespace)` |
| 2 | Pass-through input data | **Yes** | High | `_process()` lines 106-110 | Returns input unchanged or empty DF |
| 3 | Context variable access | **Yes** | Medium | `_get_context_dict()` lines 116-133 | Flattens context to dict. ~~CTX-PC-001 retracted~~ (no group collision risk). See BUG-PC-007 for `resolve_dict` corruption of `python_code` before execution. |
| 4 | GlobalMap access | **Yes** | High | `_process()` line 75 | Live GlobalMap object passed. User code can `globalMap.put()` / `globalMap.get()`. |
| 5 | Python routine access | **Yes** | High | `_process()` lines 64, 77-78 | Both `routines` dict and unpacked routines (`**python_routines`) available. |
| 6 | Common builtins | **Yes** | Medium | `_process()` lines 79-90 | Explicit allowlist: `pd`, `len`, `str`, `int`, `float`, `bool`, `print`, `sum`, `min`, `max`. |
| 7 | Common modules | **Yes** | Medium | `_process()` lines 93-98 | `datetime`, `os`, `sys` imported and injected each execution. |
| 8 | Statistics tracking | **Yes** | Medium | `_process()` line 107 | Only tracks pass-through count. No error counting. |
| 9 | **Die on error** | **No** | N/A | -- | **No `die_on_error` config check.** Exceptions always propagate. No graceful degradation. |
| 10 | **REJECT flow** | **No** | N/A | -- | **No reject output.** Errors always raise exceptions. |
| 11 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Not set on error.** |
| 12 | **Data modification** | **No** | N/A | -- | **User code cannot modify the DataFrame.** The DataFrame is not exposed in the namespace. Only `context`, `globalMap`, and `routines` are available. This differs from PythonDataFrameComponent which exposes `df`. |
| 13 | **Namespace isolation** | **No** | N/A | -- | **`exec()` runs with unrestricted namespace.** User code can access `os.system()`, `sys.exit()`, file operations, etc. No sandboxing. |
| 14 | **Context sync-back** | **No** | N/A | -- | **Unlike JavaComponent (lines 79-93), PythonComponent does not sync context or globalMap changes back.** If user code modifies the `context` dict, changes are lost (it is a copy). GlobalMap changes persist because the live object is passed. |

### 5.2 Comparison with JavaComponent (tJava Analog)

The `PythonComponent` is designed to be the Python analog of `JavaComponent`, but has significant behavioral gaps:

| Feature | JavaComponent | PythonComponent | Gap? |
|---------|---------------|-----------------|------|
| Code execution | Via Java bridge | Via `exec()` | Different mechanism, both functional |
| Context sync (pre-execution) | Syncs to Java bridge (lines 65-70) | Flattens to dict (line 67) | PythonComponent loses context structure |
| Context sync (post-execution) | Syncs back from Java (lines 81-87) | **No sync-back** | **Yes** -- context changes lost |
| GlobalMap sync (pre-execution) | Syncs to Java bridge (lines 72-74) | Passes live object (line 75) | PythonComponent is actually better -- live access |
| GlobalMap sync (post-execution) | Syncs back from Java (lines 90-93) | Live object -- no sync needed | PythonComponent is better |
| Error handling | Catches and re-raises (lines 107-109) | Catches and re-raises (lines 112-114) | Same behavior |
| Die on error | Not implemented | Not implemented | Same gap in both |
| Input data pass-through | Returns input unchanged (lines 101-105) | Returns input unchanged (lines 106-110) | Same |

### 5.3 Behavioral Differences

| ID | Priority | Description |
|----|----------|-------------|
| ENG-PC-001 | **P1** | **No `die_on_error` support**: The component always raises exceptions on failure. There is no config check for `die_on_error` and no fallback to return an empty DataFrame. The `config.get('die_on_error', ...)` pattern used by other components (e.g., `FileInputDelimited`) is absent. When user code fails, the entire job crashes regardless of configuration. |
| ENG-PC-002 | **P1** | **No context sync-back**: `_get_context_dict()` creates a flat copy of context variables. If user code modifies `context['some_var'] = 'new_value'`, the change is lost because it modifies a local dict, not the ContextManager. `JavaComponent` explicitly syncs context back (lines 84-87). `PythonComponent` should do the same. |
| ENG-PC-003 | **P1** | **Unrestricted `exec()` with `os` and `sys`**: The namespace includes `os` and `sys` modules, enabling arbitrary filesystem access (`os.remove()`, `os.system()`), process termination (`sys.exit()`), and other dangerous operations. While user code is trusted in converted Talend jobs, defense-in-depth requires at minimum restricting `__builtins__` or documenting the security boundary. |
| ENG-PC-004 | **P2** | **No REJECT flow**: All exceptions propagate and crash the component. No mechanism to capture errors and route them to a reject output. |
| ENG-PC-005 | **P2** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur, the error message is not stored in globalMap for downstream error-handling triggers. |
| ENG-PC-006 | **P2** | **DataFrame not exposed to user code**: The namespace does not include the input DataFrame. User code cannot inspect or modify data. While the docstring says "Execute one-time Python code (not row-based)", many tJava use cases access `input_row` data. The lack of `input_data` in the namespace limits utility. |
| ENG-PC-007 | **P3** | **No `numpy` in namespace**: `PythonDataFrameComponent` includes `np` (numpy) in its namespace; `PythonComponent` does not. Minor inconsistency between sibling components. |

### 5.4 GlobalMap Variable Coverage

| Variable | Expected? | V1 Sets? | How V1 Sets It | Notes |
|----------|-----------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class (when global_map crash is fixed). |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Always equals NB_LINE (all rows pass through). |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Always 0 -- no reject mechanism. |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Not implemented. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-PC-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the loop variable (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: Affects ALL components. This is the same bug as BUG-FID-001. |
| BUG-PC-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: Method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: This is the same bug as BUG-FID-002. |
| BUG-PC-003 | **P1** | `python_component.py:75` | **`globalMap` passed as live object but `GlobalMap.get()` is broken**: User code calling `globalMap.get('some_key')` will crash due to BUG-PC-002. While `globalMap.put()` works correctly, the asymmetry means user code can write but not read global variables. |
| BUG-PC-004 | **P1** | `python_component.py:78` | **`**python_routines` unpacking can shadow namespace keys**: If a loaded routine module has a name matching a namespace key (e.g., a routine named `print`, `str`, `len`, `pd`, `os`, `sys`, `context`, `globalMap`, `routines`), the `**python_routines` unpacking on line 78 will overwrite the corresponding namespace entry. The unpacking happens BEFORE the explicit namespace entries for `datetime`, `os`, `sys` (lines 94-98), so those three are safe. But `pd`, `len`, `str`, `int`, `float`, `bool`, `print`, `sum`, `min`, `max`, `context`, `globalMap`, and `routines` can all be shadowed by a routine with a matching name. |
| BUG-PC-007 | **P1** | `base_component.py:202`, `context_manager.py:130-137` | **`resolve_dict` silently corrupts `python_code` before execution.** `base_component.execute()` line 202 calls `self.context_manager.resolve_dict(self.config)`. `resolve_dict` (line 150 of `context_manager.py`) skips `java_code` and `imports` keys but does NOT skip `python_code`. The value is passed to `resolve_string()`, where Pattern 2 regex `\bcontext\.(\w+)\b` (line 130) matches legitimate Python expressions like `context.get(...)`, `context.update(...)`, `context.keys()`, etc. in the user code string and attempts substitution -- replacing them with context variable values or leaving corrupted fragments. **CROSS-CUTTING**: Affects `PythonRowComponent` and `PythonDataFrameComponent` too, since all three store user code under `python_code` and all go through the same `resolve_dict` path. |
| BUG-PC-008 | **P1** | `python_component.py:112-114` | **`_update_global_map()` crash in error handler masks original exception.** When user code raises an exception (e.g., `SyntaxError`, `ZeroDivisionError`), the `except` block on line 112 logs the error and re-raises. However, `_update_global_map()` is called in the `finally` or post-success path of `base_component.execute()` (line 218). If the globalMap bug (BUG-PC-001: undefined `value` variable) triggers during the error-handling unwind, the resulting `NameError` replaces the original exception. The user never sees the real error (e.g., their `SyntaxError`) and instead gets an opaque `NameError: name 'value' is not defined` from `base_component.py:304`. This makes debugging user code failures nearly impossible when `global_map` is configured. |

### 6.2 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-PC-001 | **P1** | **Unrestricted `exec()` with `os` and `sys` modules**: The execution namespace includes `os` and `sys` modules, and `__builtins__` is NOT restricted (no `'__builtins__': {}` in namespace dict). User code can execute arbitrary commands: `os.system('rm -rf /')`, `os.remove('/etc/passwd')`, `sys.exit(1)`, `__import__('subprocess').call(...)`. While user code is typically trusted in Talend-converted jobs, this is a defense-in-depth concern. At minimum, `__builtins__` should be restricted to a safe subset, and `os`/`sys` should be opt-in rather than default. |
| SEC-PC-002 | **P2** | **Namespace pollution via `exec()`**: After `exec(python_code, namespace)`, any variables, functions, or classes defined in user code persist in `namespace`. While the namespace is local to `_process()` and discarded after return, within the execution the user code has full access to modify any namespace entry, including overwriting `globalMap`, `context`, or `routines` references. |
| SEC-PC-003 | **P2** | **User code can access component internals via frame introspection.** User code running inside `exec()` can call `inspect.currentframe().f_back.f_locals['self']` (or equivalently `sys._getframe(1).f_locals['self']`) to obtain a reference to the `PythonComponent` instance. This bypasses the namespace boundary entirely, granting access to `self.config` (all configuration including secrets), `self.context_manager` (the live ContextManager, not the read-only copy), `self.global_map`, and `self.stats`. Since `inspect` is importable (unrestricted `__builtins__`) and `sys` is already in the namespace, this requires no special privileges. |

### 6.3 Code Duplication

| ID | Priority | Issue |
|----|----------|-------|
| DUP-PC-001 | **P2** | **`_get_context_dict()` duplicated across 3 components**: The identical method exists in `PythonComponent` (lines 116-133), `PythonRowComponent` (lines 132-149), and `PythonDataFrameComponent` (lines 131-148). All three have the exact same logic: iterate `context_manager.get_all()`, flatten nested `{value:..., type:...}` structures, handle simple flat structure. This should be extracted to a mixin class or to `BaseComponent`. |

### 6.4 Context Flattening Correctness

| ID | Priority | Issue |
|----|----------|-------|
| ~~CTX-PC-001~~ | ~~P2~~ | **RETRACTED -- Incorrect claim.** `ContextManager.get_all()` returns `self.context.copy()` (line 214 of `context_manager.py`), which is already a flat `Dict[str, Any]`. There are no nested context groups at runtime. The nested-dict handling in `_get_context_dict()` (lines 122-128: `if isinstance(value, dict) and 'value' in value`) is **dead code** -- it guards against a `{value:..., type:...}` structure that `get_all()` never produces. The original claim about group collisions between `Default` and `Production` was based on a misreading of the data model; context groups are resolved at load time, not at runtime. No key collision risk exists. |
| CTX-PC-002 | **P2** | **Context dict is read-only copy but not documented as such**: The `context_dict` passed to user code is a plain Python dict. User code can modify it (`context['new_var'] = 42`), but changes are not propagated back to the `ContextManager`. This is not documented in the component's docstring, which says "context: Context variables from ContextManager" without mentioning the read-only nature. Compare with `JavaComponent` which explicitly syncs context back (lines 84-87). |

### 6.5 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-PC-001 | **P3** | **Docstring references `tJava` but component is for Python**: Line 4 of `python_component.py` says "This component mimics Talend's tJava functionality" which is correct conceptually but the module docstring header says "tPython Component" which references a non-existent standard Talend component. The naming could confuse users into thinking tPython is a real Talend component. |

### 6.6 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-PC-001 | **P1** | "Every component MUST have its own `parse_*` method" (STANDARDS.md) | Uses generic fallback path. No dedicated parser exists. |
| STD-PC-002 | **P2** | "No `print()` statements" (STANDARDS.md) | `print` is injected into the user code namespace (line 86). While this does not affect the component code itself, user code using `print()` will bypass the logging infrastructure. |

### 6.7 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `Component {self.id}:` prefix -- correct |
| Level usage | INFO for start/success, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 70) and success (line 103) -- correct |
| Sensitive data | No sensitive data logged -- correct. However, user code is NOT logged, which is correct for security but makes debugging harder. |
| No print statements | No `print()` calls in component code -- correct |

### 6.8 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses generic `ValueError` for missing config (line 61). Does NOT use `ConfigurationError` from `exceptions.py`. |
| Exception chaining | No `raise ... from e` pattern -- bare `raise` on line 114 preserves original traceback, which is acceptable. |
| `die_on_error` handling | **NOT IMPLEMENTED**. All exceptions propagate unconditionally. |
| No bare `except` | `except Exception as e:` on line 112 -- correct |
| Error messages | Include component ID -- correct |
| Graceful degradation | **NONE**. No fallback to empty DataFrame on error. |

### 6.9 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_process()` has return type `Dict[str, Any]` -- correct |
| `_get_context_dict()` | Return type `Dict[str, Any]` -- correct |
| Missing type for `namespace` | The `namespace` dict (line 73) has no type annotation. Minor. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-PC-001 | **P2** | **`datetime`, `os`, `sys` imported inside `_process()` on every execution**: Lines 93-98 import three modules inside the method body. While Python caches imports after the first load, the `import` statement still incurs lookup overhead on each call. These should be module-level imports (they are already imported at module level or available). |
| PERF-PC-002 | **P3** | **`python_routines` copied twice**: `get_python_routines()` calls `self.python_routine_manager.get_all_routines()` which returns `.copy()` (line 150 of `python_routine_manager.py`). Then `**python_routines` unpacks the copy into namespace. For large routine sets, this is double allocation. Minor concern. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Not applicable -- component executes code once, not per-row. Streaming mode in base class would chunk input data but PythonComponent passes it through unchanged, so chunking has no benefit. |
| HYBRID mode interaction | **Potential issue**: If HYBRID mode is active and input data is large, `BaseComponent._execute_streaming()` will call `_process()` once per chunk. PythonComponent's one-time code will execute ONCE PER CHUNK, not once per job. This violates the "execute once" contract. The component should override `_execute_streaming()` to execute code once and then pass all chunks through. |
| Namespace cleanup | Namespace is local to `_process()` and garbage-collected on return. No memory leak concern. |

### 7.2 HYBRID Streaming Mode Bug

| ID | Priority | Issue |
|----|----------|-------|
| ENG-PC-008 | **P2** | **One-time code executes multiple times in streaming mode**: When `BaseComponent._execute_streaming()` is active (large input data with HYBRID mode), it calls `_process()` once per chunk (line 269 of `base_component.py`). PythonComponent's code executes inside `_process()`, so it runs N times (once per chunk) instead of once. This can cause duplicate globalMap writes, duplicate resource initialization, and incorrect behavior for code that expects single execution. `JavaComponent` has the same issue. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `PythonComponent` v1 engine |
| V1 engine integration tests | **No** | -- | No v1 integration tests found |
| V2 tests (out of scope) | Yes | `tests/v2/component/test_python_components.py` | V2 component tests exist but test the v2 `PythonCode` component, not v1 `PythonComponent`. |
| Converter tests (v1->v2) | Yes | `tests/converters/v1_to_v2/test_component_mapper.py:467-474` | Tests v1->v2 mapping for `tPython` type, but tests the mapper, not the converter XML extraction. |

**Key finding**: The v1 engine has ZERO tests for this component. All 134 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic code execution | P0 | Execute simple Python code (`x = 1 + 1`), verify no exception and correct pass-through of input data |
| 2 | Missing `python_code` config | P0 | Should raise `ValueError` with descriptive message including component ID |
| 3 | Empty `python_code` config | P0 | Should raise `ValueError` (empty string is falsy) |
| 4 | GlobalMap write | P0 | User code calls `globalMap.put('key', 'value')`. Verify value is retrievable after execution (requires BUG-PC-002 fix). |
| 5 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly in stats dict (requires BUG-PC-001 fix). |
| 6 | No input data | P0 | `input_data=None` should execute code and return empty DataFrame |
| 7 | Pass-through fidelity | P0 | Input DataFrame with NaN, empty strings, mixed types should pass through unchanged (same object identity or value equality) |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Context variable access | P1 | User code reads `context['var_name']`, verify correct value from ContextManager |
| 9 | Routine access | P1 | User code calls `routines.SomeRoutine.some_function()`, verify execution |
| 10 | Direct routine access | P1 | User code calls `SomeRoutine.some_function()` (via `**python_routines` unpacking), verify execution |
| 11 | Code with syntax error | P1 | User code `if True` (missing colon) should raise `SyntaxError` |
| 12 | Code with runtime error | P1 | User code `1/0` should raise `ZeroDivisionError` |
| 13 | Code with import statement | P1 | User code `import json; globalMap.put('test', json.dumps({'a': 1}))` should work |
| 14 | Pandas access | P1 | User code `df = pd.DataFrame({'a': [1,2,3]})` should work (pd is in namespace) |
| 15 | Datetime module access | P1 | User code `from datetime import datetime; globalMap.put('now', str(datetime.now()))` should work |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 16 | NaN in input data pass-through | P2 | DataFrame with NaN values should pass through without modification |
| 17 | Empty string in input data | P2 | DataFrame with empty strings should pass through without modification |
| 18 | Large DataFrame pass-through | P2 | Verify HYBRID mode does not cause multiple code executions (streaming mode bug) |
| 19 | Context modification does not persist | P2 | User code modifies `context['var'] = 'new'`, verify ContextManager is not affected |
| 20 | Routine name collision | P2 | Load a routine named `print`, verify it shadows the builtin `print` in namespace |
| 21 | Concurrent execution | P2 | Multiple PythonComponent instances executing simultaneously should not interfere |
| 22 | `exec()` namespace isolation | P2 | Variables defined in one PythonComponent execution should not leak to subsequent executions |

---

## 9. Edge Case Analysis

### Edge Case 1: NaN values in input DataFrame

| Aspect | Detail |
|--------|--------|
| **Expected** | NaN values pass through unchanged. |
| **V1** | `_process()` returns input_data directly (line 108). No modification. NaN preserved. |
| **Verdict** | CORRECT |

### Edge Case 2: Empty strings in input DataFrame

| Aspect | Detail |
|--------|--------|
| **Expected** | Empty strings pass through unchanged. |
| **V1** | Same pass-through. No string processing. |
| **Verdict** | CORRECT |

### Edge Case 3: HYBRID streaming mode with one-time code

| Aspect | Detail |
|--------|--------|
| **Expected** | Code executes once regardless of input size. |
| **V1** | `BaseComponent._execute_streaming()` calls `_process()` per chunk. Code executes N times. |
| **Verdict** | **BUG** -- see ENG-PC-008. |

### Edge Case 4: `_update_global_map()` crash

| Aspect | Detail |
|--------|--------|
| **Expected** | Stats stored in globalMap after execution. |
| **V1** | `_update_global_map()` crashes with `NameError` on `value` (line 304 of base_component.py). |
| **Verdict** | **BUG** -- see BUG-PC-001. Crashes every execution when globalMap is set. |

### Edge Case 5: `exec()` security -- arbitrary code execution

| Aspect | Detail |
|--------|--------|
| **Expected** | User code is sandboxed or at least documented as unrestricted. |
| **V1** | `exec(python_code, namespace)` with `os`, `sys`, and unrestricted `__builtins__`. User code can `os.system('...')`, `sys.exit()`, `__import__('subprocess')`, etc. |
| **Verdict** | **GAP** -- no sandboxing, no restriction. See SEC-PC-001. |

### Edge Case 6: Namespace pollution from routines

| Aspect | Detail |
|--------|--------|
| **Expected** | Routine names do not conflict with built-in namespace entries. |
| **V1** | `**python_routines` on line 78 is unpacked BEFORE `datetime`/`os`/`sys` (lines 94-98) but AFTER `pd`, `len`, `str`, etc. (lines 80-90). A routine named `pd` would shadow pandas. |
| **Verdict** | **BUG** -- see BUG-PC-004. No collision detection or warning. |

### Edge Case 7: Routine access when no PythonRoutineManager configured

| Aspect | Detail |
|--------|--------|
| **Expected** | Graceful fallback -- `routines` is empty dict, no error. |
| **V1** | `get_python_routines()` in base_component.py (lines 369-379) returns `{}` when `python_routine_manager` is None. `**{}` unpacking is safe. |
| **Verdict** | CORRECT |

### Edge Case 8: Context flattening with nested vs flat structure

| Aspect | Detail |
|--------|--------|
| **Expected** | Both nested (`{Default: {var: {value: "x", type: "str"}}}`) and flat (`{var: "x"}`) structures handled. |
| **V1** | `_get_context_dict()` handles both (lines 122-132). Nested dicts with `value` key are unwrapped; flat values pass through. |
| **Verdict** | CORRECT. ~~CTX-PC-001 retracted~~ -- `ContextManager.get_all()` returns a flat dict; no multi-group collision risk exists. The nested-dict handling in `_get_context_dict()` is dead code. |

### Edge Case 9: Error handling -- code raises exception

| Aspect | Detail |
|--------|--------|
| **Expected** | Exception logged and re-raised; globalMap updated with error message. |
| **V1** | Exception is logged (line 113) and re-raised (line 114). But `{id}_ERROR_MESSAGE` is NOT set in globalMap. |
| **Verdict** | PARTIAL -- logged but not stored in globalMap. |

### Edge Case 10: Input data is empty DataFrame (not None)

| Aspect | Detail |
|--------|--------|
| **Expected** | Code executes (it is one-time, not row-based). Empty DataFrame passes through. |
| **V1** | `input_data is not None` is True for empty DF. `len(input_data)` is 0. Stats: (0, 0, 0). Returns `{'main': input_data}`. Code still executes. |
| **Verdict** | CORRECT |

---

## 10. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| CONV-PC-001 | Converter | `CODE` field explicitly skipped during generic parsing -- `python_code` never extracted from Talend XML. Component is **completely non-functional** for converted jobs. |
| BUG-PC-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-PC-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-PC-001 | Testing | Zero v1 unit tests. All 134 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-PC-002 | Converter | No dedicated parser method -- uses generic fallback. Violates STANDARDS.md. Must create `parse_tpython()` mirroring the tJava parser (lines 332-346 of `component_parser.py`). |
| CONV-PC-003 | Converter | No `elif component_type == 'tPython'` branch in `converter.py:_parse_component()`. Must add to invoke dedicated parser. |
| ENG-PC-001 | Engine | No `die_on_error` support. Exceptions always propagate. No graceful degradation to empty DataFrame. |
| ENG-PC-002 | Engine | No context sync-back. Changes to `context` dict in user code are lost. Unlike JavaComponent which explicitly syncs context back. |
| ENG-PC-003 | Engine | Unrestricted `exec()` with `os` and `sys`. No `__builtins__` restriction. Arbitrary code execution possible. |
| BUG-PC-003 | Bug | `globalMap.get()` broken due to cross-cutting BUG-PC-002. User code can write but not read global variables. |
| BUG-PC-004 | Bug | `**python_routines` unpacking can shadow namespace keys (`pd`, `len`, `str`, `int`, `float`, `bool`, `print`, `sum`, `min`, `max`, `context`, `globalMap`, `routines`). |
| BUG-PC-007 | Bug (Cross-Cutting) | `resolve_dict` silently corrupts `python_code` before execution. Pattern 2 regex `\bcontext\.(\w+)\b` matches `context.get(...)` in user code and attempts substitution. Affects PythonRowComponent and PythonDataFrameComponent too. |
| BUG-PC-008 | Bug | `_update_global_map()` crash in error handler masks original exception. User never sees real error (e.g., SyntaxError) -- gets `NameError` instead. |
| STD-PC-001 | Standards | No dedicated converter parser method. Violates STANDARDS.md requirement for component-specific `parse_*` methods. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| ENG-PC-004 | Engine | No REJECT flow. All errors raise exceptions. |
| ENG-PC-005 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap on error. |
| ENG-PC-006 | Engine | DataFrame not exposed to user code namespace. Cannot inspect or modify data. |
| ENG-PC-008 | Engine | One-time code executes multiple times in HYBRID streaming mode due to per-chunk `_process()` calls. |
| SEC-PC-001 | Security | Unrestricted `exec()` with full `__builtins__`, `os`, and `sys`. No sandboxing. |
| SEC-PC-002 | Security | Namespace pollution -- user code can overwrite any namespace entry including `globalMap` and `context`. |
| DUP-PC-001 | Code Quality | `_get_context_dict()` duplicated identically across PythonComponent, PythonRowComponent, and PythonDataFrameComponent. |
| ~~CTX-PC-001~~ | ~~Correctness~~ | ~~RETRACTED.~~ `ContextManager.get_all()` returns a flat dict; nested-dict handling in `_get_context_dict()` is dead code. No group collision risk exists. See Section 6.4 for full correction. |
| CTX-PC-002 | Correctness | Context dict is read-only copy but not documented as such. User code modifications are silently lost. |
| SEC-PC-003 | Security | User code can access component internals via `inspect.currentframe().f_back.f_locals['self']`. Bypasses namespace boundary -- accesses config, context_manager, stats. |
| STD-PC-002 | Standards | `print` injected into user namespace bypasses logging infrastructure. |
| PERF-PC-001 | Performance | `datetime`, `os`, `sys` imported inside `_process()` on every execution instead of module-level. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| ENG-PC-007 | Engine | No `numpy` in namespace (inconsistent with PythonDataFrameComponent). |
| NAME-PC-001 | Naming | Docstring references `tPython` as if it were a standard Talend component; it is not. |
| PERF-PC-002 | Performance | `python_routines` dict copied twice (once in `get_all_routines()`, once via `**` unpacking). |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 4 | 1 converter, 2 bugs (cross-cutting), 1 testing |
| P1 | 10 | 2 converter, 3 engine, 4 bugs (incl. 1 cross-cutting), 1 standards |
| P2 | 11 | 3 engine, 3 security, 1 code quality, 1 correctness (1 retracted), 1 standards, 1 performance, 1 engine (streaming) |
| P3 | 3 | 1 engine, 1 naming, 1 performance |
| **Total** | **28** | (includes 1 retracted: ~~CTX-PC-001~~) |

---

## 11. Recommendations

### Immediate (Before Production)

1. **Create dedicated converter parser** (CONV-PC-001, CONV-PC-002, CONV-PC-003): This is the **highest priority fix** -- without it, the component is completely non-functional for converted jobs. Create a `parse_tpython()` method in `component_parser.py` that extracts `CODE` as `python_code` and `IMPORT` as `imports`, with XML entity decoding. Use the tJava parser (lines 332-346) as the exact template:

```python
# In component_parser.py, add to _map_component_parameters():
elif component_type == 'tPython':
    code = config_raw.get('CODE', '')
    code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
    imports = config_raw.get('IMPORT', '')
    imports = imports.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
    return {
        'python_code': code,
        'imports': imports,
        'die_on_error': config_raw.get('DIE_ON_ERROR', False)
    }
```

Then add `elif component_type == 'tPython': component = self.component_parser.parse_tpython(node, component)` in `converter.py:_parse_component()`.

**Also**: The `CODE`/`IMPORT` skip on line 448-449 of `component_parser.py` must be updated. Currently it skips these fields for ALL components going through the generic path. The skip comment says "handled by component-specific parsers (tJava, tJavaRow)" but tPython also needs them. Either add tPython to the `_map_component_parameters` branch (which reads from `config_raw` that already has `CODE` stripped) or change the approach to not strip `CODE` from `config_raw` for tPython.

2. **Fix `_update_global_map()` bug** (BUG-PC-001): Change `value` to `stat_value` on `base_component.py` line 304 or remove the stale reference. **Impact**: Fixes ALL components. **Risk**: Very low.

3. **Fix `GlobalMap.get()` bug** (BUG-PC-002): Add `default: Any = None` parameter to `get()` signature in `global_map.py` line 26. **Impact**: Fixes ALL components and user code calling `globalMap.get()`. **Risk**: Very low.

4. **Create unit test suite** (TEST-PC-001): Implement at minimum the 7 P0 test cases in Section 8.2.

### Short-Term (Hardening)

5. **Add `die_on_error` support** (ENG-PC-001): Check `self.config.get('die_on_error', False)` in the exception handler. When false, log the error, set `{id}_ERROR_MESSAGE` in globalMap, and return the input data unchanged (or empty DataFrame if no input).

6. **Implement context sync-back** (ENG-PC-002): After `exec()`, check if `namespace['context']` has been modified and sync changes back to `self.context_manager`. Follow the pattern from `JavaComponent` (lines 84-87).

7. **Fix routine name collision** (BUG-PC-004): Move `**python_routines` unpacking AFTER explicit namespace entries, or better yet, do not unpack routines directly into the namespace. Keep them only under the `routines` key and document that access pattern.

8. **Restrict `exec()` namespace** (SEC-PC-001): Set `namespace['__builtins__'] = {}` or a curated safe subset. Remove `os` and `sys` from the default namespace and make them opt-in via an `allow_system_access` config flag.

9. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-PC-005): In the exception handler, call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))` before re-raising.

10. **Extract `_get_context_dict()` to base class or mixin** (DUP-PC-001): Remove duplication across PythonComponent, PythonRowComponent, and PythonDataFrameComponent.

### Long-Term (Optimization)

11. **Handle HYBRID streaming mode** (ENG-PC-008): Override `_execute_streaming()` in PythonComponent to execute code once and then pass all chunks through unchanged.

12. **Expose input data in namespace** (ENG-PC-006): Add `input_data` (or `df`) to the namespace so user code can inspect the DataFrame. Document clearly that modifications to `df` will NOT affect the output (since the original `input_data` is returned).

13. **Add `numpy` to namespace** (ENG-PC-007): For consistency with PythonDataFrameComponent.

14. **Move module imports to module level** (PERF-PC-001): Move `datetime`, `os`, `sys` references to module-level constants rather than importing inside `_process()`.

---

## Appendix A: Converter Parameter Mapping Code

### Current State (Generic Fallback)

```python
# component_parser.py line 384-386
# Default - return raw config for unmapped components
else:
    return config_raw
```

`tPython` hits this `else` branch because there is no `elif component_type == 'tPython'` case. The returned `config_raw` is missing `CODE` and `IMPORT` fields because they were skipped on line 448-449.

### Recommended Fix

```python
# Add to _map_component_parameters() after tJava branch (line 346):
elif component_type == 'tPython':
    code = config_raw.get('CODE', '')
    code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
    imports = config_raw.get('IMPORT', '')
    imports = imports.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
    return {
        'python_code': code,
        'imports': imports,
        'die_on_error': config_raw.get('DIE_ON_ERROR', False)
    }
```

**Critical note**: This fix alone is insufficient because `CODE` and `IMPORT` are stripped from `config_raw` before `_map_component_parameters()` is called (line 448-449). The fix must also update line 448 to NOT skip CODE/IMPORT for tPython:

```python
# Line 448-449 change from:
elif name not in ['CODE', 'IMPORT'] and isinstance(value, str) and 'context.' in value:
# To:
elif name not in ['CODE', 'IMPORT'] and isinstance(value, str) and 'context.' in value:
```

Actually, the issue is that `config_raw[name] = value` on line 458 DOES store CODE/IMPORT. The skip on line 449 only affects the context-wrapping logic (the `elif` is part of the `if field == 'CHECK'` / `elif` chain). On closer inspection, `CODE` and `IMPORT` ARE stored in `config_raw` -- they just bypass the context-variable wrapping. The real problem is that `_map_component_parameters` returns `config_raw` as-is (with `CODE` key, not `python_code` key), and the engine expects `python_code`. The fix in `_map_component_parameters` correctly maps `CODE` to `python_code`.

---

## Appendix B: Engine Class Structure

```
PythonComponent (BaseComponent)
    Methods:
        _process(input_data) -> Dict[str, Any]    # Main entry: exec() user code, pass-through data
        _get_context_dict() -> Dict[str, Any]      # Flatten context to plain dict

    Inherited from BaseComponent:
        execute(input_data) -> Dict[str, Any]      # Lifecycle: resolve Java exprs, context, mode select
        _update_stats(rows_read, rows_ok, rows_reject)  # Accumulate stats
        _update_global_map()                       # Store stats in globalMap (BUGGY)
        get_python_routines() -> Dict[str, Any]    # Get loaded Python routines
        validate_schema(df, schema) -> DataFrame   # Not used by PythonComponent
        _auto_select_mode(input_data) -> ExecutionMode  # HYBRID mode selection
        _execute_batch(input_data) -> Dict         # Calls _process()
        _execute_streaming(input_data) -> Dict     # Calls _process() per chunk (BUG for one-time code)
```

---

## Appendix C: Namespace Contents

The following entries are available in the `exec()` namespace for user code:

| Entry | Type | Source | Shadowable by Routine? |
|-------|------|--------|------------------------|
| `context` | `Dict[str, Any]` | `_get_context_dict()` | **Yes** |
| `globalMap` | `GlobalMap` | `self.global_map` | **Yes** |
| `routines` | `Dict[str, module]` | `get_python_routines()` | **Yes** |
| (each routine by name) | `module` | `**python_routines` unpacking | N/A (these ARE the routines) |
| `pd` | `module` (pandas) | Direct injection | **Yes** |
| `len` | `builtin_function_or_method` | Direct injection | **Yes** |
| `str` | `type` | Direct injection | **Yes** |
| `int` | `type` | Direct injection | **Yes** |
| `float` | `type` | Direct injection | **Yes** |
| `bool` | `type` | Direct injection | **Yes** |
| `print` | `builtin_function_or_method` | Direct injection | **Yes** |
| `sum` | `builtin_function_or_method` | Direct injection | **Yes** |
| `min` | `builtin_function_or_method` | Direct injection | **Yes** |
| `max` | `builtin_function_or_method` | Direct injection | **Yes** |
| `datetime` | `module` | Imported in `_process()` | No (set after `**python_routines`) |
| `os` | `module` | Imported in `_process()` | No (set after `**python_routines`) |
| `sys` | `module` | Imported in `_process()` | No (set after `**python_routines`) |
| `__builtins__` | `dict` (full) | Python default for `exec()` | N/A |

**Note**: When `exec(code, namespace)` is called with an explicit namespace dict, Python automatically adds `__builtins__` if not present. Since the namespace does NOT set `__builtins__: {}`, the FULL set of Python builtins is available, including `__import__`, `eval`, `compile`, `open`, `getattr`, `setattr`, etc.

---

## Appendix D: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `PythonComponent`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-PC-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components when `global_map` is set. |
| BUG-PC-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| DUP-PC-001 | **P2** | `python_component.py`, `python_row_component.py`, `python_dataframe_component.py` | Identical `_get_context_dict()` method duplicated across all three Python components. Should be extracted to base class or mixin. |
| ENG-PC-008 | **P2** | `base_component.py` | `_execute_streaming()` calls `_process()` per chunk. One-time components (PythonComponent, JavaComponent) execute their code multiple times when streaming is active. Both should override `_execute_streaming()`. |
| BUG-PC-007 | **P1** | `base_component.py:202`, `context_manager.py:130-137` | `resolve_dict` skips `java_code`/`imports` but NOT `python_code`. Pattern 2 regex `\bcontext\.(\w+)\b` corrupts user Python code containing `context.get(...)` etc. Affects PythonComponent, PythonRowComponent, PythonDataFrameComponent. |

These should be tracked in a cross-cutting issues report as well.
