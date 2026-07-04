# Audit Report: PythonComponent

> **Audited**: 2026-04-04
> **Reconciled**: 2026-05-11
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: N/A (engine-native component)
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Component Name** | `PythonComponent` |
| **V1 Engine Class** | `PythonComponent` |
| **Engine File** | `src/v1/engine/components/transform/python_component.py` (133 lines) |
| **Converter Parser** | N/A -- engine-native component, no Talend XML converter exists or is needed |
| **Converter Dispatch** | N/A |
| **Registry Aliases** | `PythonComponent`, `Python`, `tPython` (registered in `src/v1/engine/engine.py`) |
| **Category** | Transform / Custom Code |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/python_component.py` | Engine implementation (133 lines) |
| `src/v1/engine/base_component.py` | Base class: `execute()`, `_update_stats()`, `_update_global_map()`, `get_python_routines()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/python_routine_manager.py` | PythonRoutineManager: discovers, loads, and exposes `.py` routine files |
| `src/v1/engine/context_manager.py` | ContextManager: variable resolution, `get_all()`, `resolve_dict()` |
| `src/v1/engine/components/transform/__init__.py` | Package exports (exports `PythonComponent`) |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **N/A** | -- | -- | -- | -- | Engine-native component. No Talend XML converter exists or is applicable. |
| Engine Feature Parity | **Y** | 0 | 3 | 3 | 1 | No `die_on_error`; unrestricted `exec()`; no context sync-back; no REJECT flow |
| Code Quality | **R** | 2 | 4 | 4 | 1 | Cross-cutting `_update_global_map()` crash; `GlobalMap.get()` crash; `resolve_dict` corrupts `python_code`; error masking |
| Performance & Memory | **G** | 0 | 0 | 1 | 1 | Unnecessary `os`/`sys` import per execution; routine dict copied twice |
| Testing | **N/A** | -- | -- | -- | -- | No converter tests applicable. Engine tests are out of scope for this audit. |

**Overall: RED -- Cross-cutting base class bugs crash all execution when globalMap is set; `resolve_dict` silently corrupts `python_code` before `exec()`**

**Top Actions**:

1. Fix `_update_global_map()` crash (cross-cutting P0 -- fixes all components)
2. Fix `GlobalMap.get()` broken signature (cross-cutting P0 -- fixes all components)
3. Add `python_code` to `resolve_dict` skip list (P1 -- prevents code corruption)
4. Add `die_on_error` support (P1 -- graceful error handling)
5. Restrict `exec()` namespace (P1 -- defense-in-depth security)

---

## 3. Talend Feature Baseline

What is this component and what are its configuration parameters?

### What PythonComponent Does

`PythonComponent` is an **engine-native component** -- it is NOT a standard Talend Studio component. Unlike `tJava` and `tJavaRow`, which are first-class Talend components with official XML definitions, there is no official `tPython` component from Talend/Qlik. The v1 engine created `PythonComponent` as the Python analog of `JavaComponent` (tJava), allowing users to execute arbitrary one-time Python code within a job.

The component executes user-defined Python code **once per job execution** (not per row). It provides access to context variables, the GlobalMap, loaded Python routines, and common modules. Input data passes through unchanged -- the component is a side-effect-only processor for initialization, resource setup, globalMap variable assignment, and one-time calculations.

**Source**: Engine source code (`src/v1/engine/components/transform/python_component.py`)
**Component family**: Transform / Custom Code (analogous to tJava)
**Available in**: Custom v1 engine only; not a standard Talend component

### 3.1 Configuration Parameters (Engine Contract)

Since this is an engine-native component with no Talend XML specification, the configuration is defined by what the engine code reads from the v1 job JSON.

| # | Parameter | Config Key | Type | Default | Description |
| --- | ----------- | ------------ | ------ | --------- | ------------- |
| 1 | Python Code | `python_code` | STRING (multi-line) | `''` (empty) | **Mandatory**. Python code to execute once per job execution. Raises `ValueError` if empty/missing. |

**Note**: The engine reads only `python_code` from config. There is no `die_on_error`, `imports`, or other config parameter consumed. Unlike `JavaComponent` which reads `java_code` and `imports`, `PythonComponent` has a single config parameter.

### 3.2 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input/Output | Row > Main | Input data passes through unchanged after code execution. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when subjob fails. |

### 3.3 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total number of input rows (pass-through count). |
| `{id}_NB_LINE_OK` | Integer | After execution | Same as NB_LINE (all rows pass through). |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Always 0 (no reject mechanism). |

### 3.4 Behavioral Notes

1. **One-time execution**: The Python code executes ONCE per job run, not per row. This is the key distinction from `PythonRowComponent` (analogous to tJavaRow vs tJava).

2. **Pass-through behavior**: Input data flows through unchanged. The component is a side-effect-only processor -- it does not modify the DataFrame. User code can set globalMap variables, initialize resources, perform calculations, etc.

3. **Namespace exposure**: User code has access to `context` (flat dict copy), `globalMap` (live GlobalMap object), `routines` (loaded Python routine modules), plus common builtins (`pd`, `len`, `str`, `int`, `float`, `bool`, `print`, `sum`, `min`, `max`) and modules (`datetime`, `os`, `sys`).

4. **Engine-native**: Since this is not a standard Talend component, there is no official XML parameter schema. Jobs using PythonComponent are configured via v1 job JSON, not Talend `.item` XML conversion.

---

## 4. Converter Analysis

**N/A** -- This is an engine-native component. No Talend-to-v1 converter exists or is needed. The component is configured directly via v1 job JSON configuration, not through Talend XML conversion.

---

## 5. Converter Code Quality

**N/A per D-82** -- This is an engine-native component. No Talend-to-v1 converter exists or is applicable. Converter code quality assessment is not applicable.

---

## 6. Test Coverage

**N/A per D-82** -- No converter tests applicable. Engine tests are out of scope for this audit.

---

## 7. Configuration Comparison

Since PythonComponent is engine-native (no Talend XML source), this section compares what the engine code actually reads from config versus what is documented.

### 7.1 Engine Config Parameter Usage

| # | Config Key | Engine Reads? | Line | Default | Notes |
| --- | ----------- | --------------- | ------ | --------- | ------- |
| 1 | `python_code` | **Yes** | `_process()` line 58 | `''` | `self.config.get('python_code', '')` -- raises `ValueError` if empty |

### 7.2 Undocumented Engine Behaviors

| # | Behavior | Location | Impact |
| --- | ---------- | ---------- | -------- |
| 1 | `resolve_dict` processes `python_code` | `base_component.py:202` | Context variable pattern matching corrupts Python code containing `context.get(...)` etc. |
| 2 | `die_on_error` not consumed | `_process()` | All exceptions propagate unconditionally -- no graceful degradation |
| 3 | Input DataFrame not exposed to namespace | `_process()` lines 73-98 | User code cannot access or inspect input data |

---

## 8. Engine Gaps

### 8.1 Feature Implementation Status

| # | Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | --------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Execute one-time Python code | **Yes** | High | `_process()` line 101 | `exec(python_code, namespace)` |
| 2 | Pass-through input data | **Yes** | High | `_process()` lines 106-110 | Returns input unchanged or empty DF |
| 3 | Context variable access | **Yes** | Medium | `_get_context_dict()` lines 116-133 | Flattens context to dict. But `resolve_dict` corrupts `python_code` before execution (BUG-PC-007). |
| 4 | GlobalMap access | **Yes** | High | `_process()` line 75 | Live GlobalMap object passed. User code can `globalMap.put()` / `globalMap.get()`. |
| 5 | Python routine access | **Yes** | High | `_process()` lines 64, 77-78 | Both `routines` dict and unpacked routines (`**python_routines`) available. |
| 6 | Common builtins | **Yes** | Medium | `_process()` lines 79-90 | Explicit allowlist: `pd`, `len`, `str`, `int`, `float`, `bool`, `print`, `sum`, `min`, `max`. |
| 7 | Common modules | **Yes** | Medium | `_process()` lines 93-98 | `datetime`, `os`, `sys` imported and injected each execution. |
| 8 | Statistics tracking | **Yes** | Medium | `_process()` line 107 | Only tracks pass-through count. No error counting. |
| 9 | **Die on error** | **No** | N/A | -- | No `die_on_error` config check. Exceptions always propagate. |
| 10 | **REJECT flow** | **No** | N/A | -- | No reject output. Errors always raise exceptions. |
| 11 | **Data modification** | **No** | N/A | -- | DataFrame not exposed in namespace. Only `context`, `globalMap`, and `routines` are available. |
| 12 | **Context sync-back** | **No** | N/A | -- | Unlike `JavaComponent`, changes to `context` dict are lost (it is a copy). GlobalMap changes persist because the live object is passed. |
| 13 | **Namespace isolation** | **No** | N/A | -- | `exec()` runs with unrestricted namespace. User code can access `os.system()`, `sys.exit()`, etc. No sandboxing. |

### 8.2 Behavioral Issues

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-PC-001 | **P1** | **No `die_on_error` support**: The component always raises exceptions on failure. No config check for `die_on_error`, no fallback to return an empty DataFrame. When user code fails, the entire job crashes regardless of configuration. |
| ENG-PC-002 | **P1** | **No context sync-back**: `_get_context_dict()` creates a flat copy of context variables. If user code modifies `context['some_var'] = 'new_value'`, the change is lost because it modifies a local dict, not the ContextManager. `JavaComponent` explicitly syncs context back. |
| ENG-PC-003 | **P1** | **Unrestricted `exec()` with `os` and `sys`**: The namespace includes `os` and `sys` modules, enabling arbitrary filesystem access and process termination. `__builtins__` is NOT restricted. |
| ENG-PC-004 | **P2** | **No REJECT flow**: All exceptions propagate and crash the component. No mechanism to capture errors and route them to a reject output. |
| ENG-PC-005 | **P2** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur, the error message is not stored in globalMap for downstream error-handling triggers. |
| ENG-PC-006 | **P2** | **DataFrame not exposed to user code**: The namespace does not include the input DataFrame. User code cannot inspect or modify data. |
| ENG-PC-007 | **P3** | **No `numpy` in namespace**: `PythonDataFrameComponent` includes `np` (numpy); `PythonComponent` does not. Minor inconsistency. |

### 8.3 GlobalMap Variable Coverage

| Variable | Expected? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ----------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` | Set correctly via base class (when cross-cutting crash is fixed). |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Always equals NB_LINE (all rows pass through). |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Always 0 -- no reject mechanism. |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Not implemented. |

### 8.4 Comparison with JavaComponent (tJava Analog)

| Feature | JavaComponent | PythonComponent | Gap? |
| --------- | --------------- | ----------------- | ------ |
| Code execution | Via Java bridge | Via `exec()` | Different mechanism, both functional |
| Context sync (pre) | Syncs to Java bridge | Flattens to dict | PythonComponent loses context structure |
| Context sync (post) | Syncs back from Java | **No sync-back** | **Yes** -- context changes lost |
| GlobalMap sync (pre) | Syncs to Java bridge | Passes live object | PythonComponent is better -- live access |
| GlobalMap sync (post) | Syncs back from Java | Live object -- no sync needed | PythonComponent is better |
| Error handling | Catches and re-raises | Catches and re-raises | Same behavior |
| Die on error | Not implemented | Not implemented | Same gap in both |
| Input data pass-through | Returns input unchanged | Returns input unchanged | Same |

---

## 9. Scoring

### Scoring Rationale

Per D-88, this engine-native component is scored on Audit Report quality, Code Quality, and Engine only. Converter and Testing are N/A.

| Dimension | Score | Rationale |
| ----------- | ------- | ----------- |
| Converter Coverage | **N/A** | Engine-native component -- no Talend XML converter |
| Engine Feature Parity | **Y** | Core functionality works (exec, pass-through, globalMap, routines). Missing die_on_error, context sync-back, namespace restriction. 3 P1 + 3 P2 + 1 P3 engine issues. |
| Code Quality | **R** | 2 cross-cutting P0 bugs (`_update_global_map()` crash, `GlobalMap.get()` crash) block all execution. `resolve_dict` corrupts `python_code` (P1). Error masking (P1). Unrestricted `exec()` (P1 security). |
| Performance & Memory | **G** | Lightweight component. Only minor issues: per-execution module import (P2), routine dict double copy (P3). |
| Testing | **N/A** | No converter tests applicable. Engine tests out of scope per D-82. |

**Overall: RED** -- Cross-cutting P0 base class bugs crash the component whenever globalMap is set. The `resolve_dict` corruption silently mangles user Python code before execution.

### Issue Summary

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 2 | **BUG-PC-001**, **BUG-PC-002** |
| P1 | 7 | **ENG-PC-001**, **ENG-PC-002**, **ENG-PC-003**, **BUG-PC-003**, **BUG-PC-004**, **BUG-PC-007**, **BUG-PC-008** |
| P2 | 8 | **ENG-PC-004**, **ENG-PC-005**, **ENG-PC-006**, **ENG-PC-008**, **SEC-PC-002**, **DUP-PC-001**, **CTX-PC-002**, **PERF-PC-001** |
| P3 | 2 | **ENG-PC-007**, **PERF-PC-002** |
| **Total** | **19** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 7 | ENG-PC-001 through ENG-PC-008 (excluding ENG-PC-007 count error -- 7 total) |
| Bug (BUG) | 5 | BUG-PC-001, BUG-PC-002, BUG-PC-003, BUG-PC-004, BUG-PC-007, BUG-PC-008 |
| Security (SEC) | 1 | SEC-PC-002 |
| Code Quality (DUP/CTX) | 2 | DUP-PC-001, CTX-PC-002 |
| Performance (PERF) | 2 | PERF-PC-001, PERF-PC-002 |

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

1. **Fix `_update_global_map()` crash** (BUG-PC-001): Change `value` to `stat_value` on `base_component.py` line 304. **CROSS-CUTTING** -- fixes all components. Risk: very low.

2. **Fix `GlobalMap.get()` crash** (BUG-PC-002): Add `default: Any = None` parameter to `get()` signature in `global_map.py` line 26. **CROSS-CUTTING** -- fixes all components and user code calling `globalMap.get()`. Risk: very low.

### Short-term (Hardening)

1. **Add `python_code` to `resolve_dict` skip list** (BUG-PC-007): In `context_manager.py`, add `python_code` to the skip list alongside `java_code` and `imports`. Prevents regex corruption of user Python code containing `context.get(...)` patterns.

2. **Add `die_on_error` support** (ENG-PC-001): Check `self.config.get('die_on_error', False)` in the exception handler. When false, log the error, set `{id}_ERROR_MESSAGE` in globalMap, and return input data unchanged.

3. **Implement context sync-back** (ENG-PC-002): After `exec()`, check if `namespace['context']` has been modified and sync changes back to `self.context_manager`. Follow the pattern from `JavaComponent`.

4. **Restrict `exec()` namespace** (ENG-PC-003): Set `namespace['__builtins__'] = {}` or a curated safe subset. Make `os`/`sys` opt-in rather than default.

5. **Fix routine name collision** (BUG-PC-004): Move `**python_routines` unpacking AFTER explicit namespace entries, or remove direct unpacking and keep routines only under the `routines` key.

6. **Extract `_get_context_dict()` to base class** (DUP-PC-001): Remove duplication across PythonComponent, PythonRowComponent, and PythonDataFrameComponent.

### Long-term (Optimization)

1. **Handle HYBRID streaming mode** (ENG-PC-008): Override `_execute_streaming()` to execute code once and then pass all chunks through unchanged.

2. **Expose input data in namespace** (ENG-PC-006): Add `input_data` to namespace for data inspection use cases.

3. **Move module imports to module level** (PERF-PC-001): Move `datetime`, `os`, `sys` references to module-level constants rather than importing inside `_process()`.

---

## Appendix A: Source References

| Source | Path | Used For |
| -------- | ------ | ---------- |
| Engine source | `src/v1/engine/components/transform/python_component.py` (133 lines) | Feature parity analysis, code quality review |
| Base component | `src/v1/engine/base_component.py` | Cross-cutting bug analysis, lifecycle understanding |
| GlobalMap | `src/v1/engine/global_map.py` | `get()` bug analysis |
| ContextManager | `src/v1/engine/context_manager.py` | `resolve_dict` corruption analysis |
| PythonRoutineManager | `src/v1/engine/python_routine_manager.py` | Routine loading behavior |
| Gold standard template | `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` | Report structure |
| Methodology | `docs/v1/standards/METHODOLOGY.md` | Scoring framework |

## Appendix B: Engine Config Parameter Mapping

### Config Parameters Read by Engine

| Config Key | Engine Method | Line | Default | Required? | Notes |
| ----------- | --------------- | ------ | --------- | ----------- | ------- |
| `python_code` | `_process()` | 58 | `''` | **Yes** | Raises `ValueError` if empty. Subject to `resolve_dict` corruption (BUG-PC-007). |

### Execution Namespace Contents

| Entry | Type | Source | Shadowable by Routine? |
| ------- | ------ | -------- | ------------------------ |
| `context` | `Dict[str, Any]` | `_get_context_dict()` | **Yes** |
| `globalMap` | `GlobalMap` | `self.global_map` | **Yes** |
| `routines` | `Dict[str, module]` | `get_python_routines()` | **Yes** |
| (each routine by name) | `module` | `**python_routines` unpacking | N/A (these ARE the routines) |
| `pd` | `module` (pandas) | Direct injection | **Yes** |
| `len`, `str`, `int`, `float`, `bool` | builtins | Direct injection | **Yes** |
| `print`, `sum`, `min`, `max` | builtins | Direct injection | **Yes** |
| `datetime` | `module` | Imported in `_process()` | No (set after `**python_routines`) |
| `os` | `module` | Imported in `_process()` | No (set after `**python_routines`) |
| `sys` | `module` | Imported in `_process()` | No (set after `**python_routines`) |
| `__builtins__` | `dict` (full) | Python default for `exec()` | N/A |

### Bug Details

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-PC-001 | **P0** | `base_component.py:304` | **CROSS-CUTTING**: `_update_global_map()` references undefined variable `value` (should be `stat_value`). Crashes ALL components when `global_map` is set. |
| BUG-PC-002 | **P0** | `global_map.py:28` | **CROSS-CUTTING**: `GlobalMap.get()` references undefined `default` parameter. Crashes on any `globalMap.get()` call. |
| BUG-PC-003 | **P1** | `python_component.py:75` | `globalMap` passed as live object but `GlobalMap.get()` is broken (BUG-PC-002). User code can write but not read global variables. |
| BUG-PC-004 | **P1** | `python_component.py:78` | `**python_routines` unpacking can shadow namespace keys (`pd`, `context`, `globalMap`, `routines`, builtins). |
| BUG-PC-007 | **P1** | `base_component.py:202`, `context_manager.py:130-137` | **CROSS-CUTTING**: `resolve_dict` skips `java_code`/`imports` but NOT `python_code`. Pattern 2 regex `\bcontext\.(\w+)\b` corrupts `context.get(...)` in user code. Affects all Python* components. |
| BUG-PC-008 | **P1** | `python_component.py:112-114` | `_update_global_map()` crash in error handler masks original exception. User sees `NameError` instead of their real error. |
| ENG-PC-008 | **P2** | `base_component.py` | One-time code executes multiple times in HYBRID streaming mode due to per-chunk `_process()` calls. |
| SEC-PC-002 | **P2** | `python_component.py:101` | Namespace pollution -- user code can overwrite any namespace entry including `globalMap` and `context`. |
| DUP-PC-001 | **P2** | Three Python components | `_get_context_dict()` duplicated identically across PythonComponent, PythonRowComponent, PythonDataFrameComponent. |
| CTX-PC-002 | **P2** | `python_component.py` | Context dict is read-only copy but not documented as such. User modifications silently lost. |
| PERF-PC-001 | **P2** | `python_component.py:93-98` | `datetime`, `os`, `sys` imported inside `_process()` on every execution instead of module-level. |
| PERF-PC-002 | **P3** | `python_component.py:64,78` | `python_routines` dict copied twice (once in `get_all_routines()`, once via `**` unpacking). |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after gold standard rewrite per D-82 (audit-only, Sections 5+6 N/A)*
