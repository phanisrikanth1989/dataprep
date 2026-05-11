# Audit Report: PythonDataFrameComponent

> **Audited**: 2026-04-04
> **Reconciled**: 2026-05-11
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: N/A (engine-native component, no Talend XML converter)
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | N/A -- engine-native custom component (no Talend equivalent) |
| **V1 Engine Class** | `PythonDataFrameComponent` |
| **Engine File** | `src/v1/engine/components/transform/python_dataframe_component.py` (148 lines) |
| **Converter Parser** | N/A -- engine-native component, not converted from Talend XML |
| **Converter Dispatch** | N/A |
| **Registry Aliases** | `PythonDataFrameComponent`, `PythonDataFrame`, `tPythonDataFrame` (registered in `src/v1/engine/engine.py`) |
| **Category** | Transform / Custom Code (Python Scripting) |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/python_dataframe_component.py` | Engine implementation (148 lines) |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()`, `get_python_routines()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/python_routine_manager.py` | PythonRoutineManager: discovers, loads, and exposes `.py` routine files |
| `src/v1/engine/context_manager.py` | ContextManager: variable resolution, `get_all()` |
| `src/v1/engine/components/transform/__init__.py` | Package exports |

### Engine-Native Status

`PythonDataFrameComponent` is **entirely custom to this ETL engine project**. There is no `tPythonDataFrame` in standard Talend. Talend has no native Python scripting components. The community-created [Severus Snake](https://github.com/ottensa/severus-snake) provides Python integration but does not define `tPythonDataFrame`. This component exists purely as a Pythonic alternative to `tJava`/`tJavaRow` for users writing v1 JSON configs by hand.

Because this is engine-native with no Talend XML source, **Sections 4 (Converter Audit) and 8 (Testing) are N/A per D-82**. The focus of this audit is engine code quality, security, and feature analysis.

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **N/A** | -- | -- | -- | -- | Engine-native component; no Talend XML converter exists or is needed |
| Engine Feature Parity | **Y** | 1 | 3 | 2 | 0 | No REJECT flow; `exec()` without sandbox; silent output_columns fallthrough; no DataFrame type check after exec |
| Code Quality | **Y** | 1 | 4 | 4 | 1 | Cross-cutting `_update_global_map()` crash; `exec()` unsandboxed; routine name shadowing; `resolve_dict()` mangles python_code |
| Performance & Memory | **G** | 0 | 0 | 2 | 1 | `.copy()` doubles memory; HYBRID streaming unsafe for whole-DataFrame ops |
| Testing | **N/A** | -- | -- | -- | -- | Engine-native audit-only per D-82; no test standardization required |

**Overall: YELLOW -- Functional for trusted code execution but has security and reliability gaps**

**Top Actions**:

1. Fix cross-cutting `_update_global_map()` crash (BUG-PDC-001)
2. Add REJECT flow for error isolation (ENG-PDC-001)
3. Restrict `__builtins__` in exec namespace (SEC-PDC-001)
4. Fix silent output_columns fallthrough (ENG-PDC-003)
5. Add DataFrame type check after exec (ENG-PDC-004)

---

## 3. Talend Feature Baseline

What does this component do? (Engine-native -- no Talend equivalent exists.)

### What PythonDataFrameComponent Does

`PythonDataFrameComponent` executes arbitrary user-supplied Python code against the entire input DataFrame at once (vectorized operations). Unlike `PythonRowComponent` which iterates row by row, this component hands the full `pd.DataFrame` to user code, enabling efficient bulk transformations using pandas/numpy APIs. The user modifies the DataFrame in-place (variable `df` in namespace), and the component returns the modified DataFrame as output.

This is the most performant of the three Python scripting components (`PythonComponent`, `PythonRowComponent`, `PythonDataFrameComponent`) because it operates on the full DataFrame using vectorized pandas operations rather than row-by-row Python loops.

**Source**: Engine-native custom component -- no Talend documentation exists.
**Component family**: Transform / Custom Code (Python Scripting)
**Available in**: V1 engine only (no Talend equivalent)
**Required JARs**: None (pure Python -- requires `pandas` and `numpy`)

### 3.1 Configuration Parameters

| # | Config Key | Type | Default | Required | Description |
| --- | ------------ | ------ | --------- | ---------- | ------------- |
| 1 | `python_code` | String (Python source) | `''` | **Yes** | Python code to execute. Has access to `df`, `pd`, `np`, `context`, `globalMap`, `routines`, and common builtins. Must modify `df` in-place or reassign within the namespace. |
| 2 | `output_columns` | List[str] | `None` | No | List of column names to keep in output. If provided, only these columns appear in the output DataFrame. If `None`, all columns pass through. |

### 3.2 Execution Namespace

The following variables are available inside user-supplied `python_code`:

| Variable | Type | Description |
| ---------- | ------ | ------------- |
| `df` | `pd.DataFrame` | The input DataFrame (a `.copy()` of input). User code modifies this. |
| `pd` | module | `pandas` library |
| `np` | module | `numpy` library |
| `context` | `Dict[str, Any]` | Flattened context variables from `ContextManager` |
| `globalMap` | `GlobalMap` | Global variable storage (live reference, not a copy) |
| `routines` | `Dict[str, Any]` | Python routines from `PythonRoutineManager` |
| `**python_routines` | unpacked | All routines available directly by name (e.g., `StringRoutine.format_name`) |
| `len`, `str`, `int`, `float`, `bool`, `sum`, `min`, `max` | builtins | Common Python builtins |

**Not explicitly provided but accessible via `__builtins__`**: `print`, `open`, `import`, `os`, `sys`, `datetime`, `eval`, `exec`, `compile`, `__import__` -- this is a security concern (see SEC-PDC-001).

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Input DataFrame from upstream component |
| `FLOW` (Main) | Output | Row > Main | Modified DataFrame after Python code execution |
| `REJECT` | Output | Row > Reject | **NOT IMPLEMENTED** -- errors crash the component |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total number of input rows via `_update_stats(rows_read=...)` |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of output rows (may differ from input if user code adds/removes rows) |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Always 0 -- hardcoded, no reject mechanism exists |
| `{id}_ERROR_MESSAGE` | String | On error | **NOT SET** -- errors propagate as exceptions |

### 3.5 Behavioral Notes

1. **DataFrame is copied before execution**: Line 75 creates `df = input_data.copy()`. User code modifies the copy, not the original. This is correct for data isolation but doubles memory usage.

2. **`exec()` is used for code execution**: Line 102 calls `exec(python_code, namespace)`. This executes arbitrary Python code with NO sandboxing. The full Python runtime is available including file I/O, network access, and system commands via `__builtins__`.

3. **Output DataFrame comes from namespace**: Line 105 reads `output_df = namespace['df']`. If user code reassigns `df` to a new DataFrame (e.g., `df = df.groupby(...).agg(...)`), the new DataFrame is picked up. If user code reassigns to a non-DataFrame, a crash will occur on `len(output_df.columns)` (line 123).

4. **`output_columns` filtering is lenient**: Lines 108-114 filter columns silently. If NONE of the specified columns exist, a warning is logged but the FULL unfiltered DataFrame is returned. This is a data integrity risk.

5. **No input validation on `python_code`**: The only check is `if not python_code:` (line 65). No syntax checking, no compilation step, no attempt to detect dangerous operations.

6. **Sibling comparison**: `PythonRowComponent` has REJECT flow and per-row error handling. `PythonDataFrameComponent` does NOT -- any exception in user code crashes the entire component.

7. **Empty/None input returns empty DataFrame**: Line 57 checks `if input_data is None or input_data.empty:` and returns `{'main': pd.DataFrame()}`. Statistics are not updated in this path.

---

## 4. Converter Audit

**N/A** -- `PythonDataFrameComponent` is an engine-native custom component. No Talend XML converter exists or is needed. This component is only used in hand-crafted v1 JSON configs.

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement this component's intended behavior?

### 5.1 Feature Implementation Status

| # | Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | --------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Execute Python code on DataFrame | **Yes** | High | `_process()` line 102 | `exec(python_code, namespace)` -- correct core mechanism |
| 2 | DataFrame copy (isolation) | **Yes** | High | `_process()` line 75 | `input_data.copy()` prevents upstream mutation |
| 3 | pandas/numpy in namespace | **Yes** | High | `_process()` lines 83-84 | `pd` and `np` available |
| 4 | Context variables in namespace | **Yes** | High | `_process()` line 85, `_get_context_dict()` lines 131-148 | Flattened context dict |
| 5 | GlobalMap in namespace | **Yes** | High | `_process()` line 86 | Live reference to `self.global_map` |
| 6 | Python routines in namespace | **Yes** | High | `_process()` lines 87-89 | Both as `routines` dict and unpacked by name |
| 7 | Common builtins in namespace | **Yes** | High | `_process()` lines 91-99 | `len`, `str`, `int`, `float`, `bool`, `sum`, `min`, `max` |
| 8 | Output column filtering | **Yes** | Medium | `_process()` lines 108-114 | Silent fallthrough when no columns match (see ENG-PDC-003) |
| 9 | Statistics tracking | **Yes** | Medium | `_process()` lines 117-121 | `NB_LINE_REJECT` hardcoded to 0 |
| 10 | Empty input handling | **Yes** | High | `_process()` lines 57-59 | Returns empty DataFrame |
| 11 | **REJECT flow** | **No** | N/A | -- | No reject output. Any exception crashes the component. |
| 12 | **Output type validation** | **No** | N/A | -- | No check that `namespace['df']` is still a DataFrame after user code |
| 13 | **Schema validation** | **No** | N/A | -- | `validate_schema()` never called on output |
| 14 | **User code compilation check** | **No** | N/A | -- | No `compile()` before `exec()` -- syntax errors only caught at runtime |
| 15 | **Streaming-aware execution** | **No** | N/A | -- | HYBRID mode chunks data, but user code may assume full DataFrame |

### 5.2 Behavioral Differences

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-PDC-001 | **P0** | **No REJECT flow**: Unlike sibling `PythonRowComponent` which catches per-row exceptions and routes them to a reject DataFrame with `errorCode` and `errorMessage`, `PythonDataFrameComponent` has NO error isolation. A single exception in user code crashes the entire component. For a component executing arbitrary user code, this is a critical reliability gap. |
| ENG-PDC-002 | **P1** | **`exec()` with no sandbox**: Line 102 calls `exec(python_code, namespace)` without restricting `__builtins__`. User code has full access to `import os`, `open()`, `subprocess`, `eval()`, `__import__()`, etc. For production use with untrusted code, `__builtins__` should be restricted. |
| ENG-PDC-003 | **P1** | **Silent output_columns fallthrough**: Lines 108-114: when `output_columns` is specified but NONE of the listed columns exist in the DataFrame, the code logs a warning but returns the FULL unfiltered DataFrame. Silent data integrity violation. |
| ENG-PDC-004 | **P1** | **No validation that `namespace['df']` remains a DataFrame**: Line 105 reads `output_df = namespace['df']`. If user code does `df = "not a dataframe"` or `del df`, the subsequent `len(output_df.columns)` on line 123 will crash with an unhelpful `AttributeError`. |
| ENG-PDC-005 | **P2** | **HYBRID streaming mode is unsafe**: `BaseComponent._execute_streaming()` chunks the input DataFrame and calls `_process()` per chunk. User code that assumes the full DataFrame (groupby, sort, dedup) will produce WRONG RESULTS on individual chunks. Component should force BATCH mode. |
| ENG-PDC-006 | **P2** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur, the exception propagates but no error message is stored in globalMap for downstream reference. |

### 5.3 GlobalMap Variable Coverage

| Variable | Expected | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ---------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Correct via base class mechanism |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Reflects actual output row count |
| `{id}_NB_LINE_REJECT` | Yes | **Hardcoded 0** | `_update_stats(rows_reject=0)` line 121 | Always 0 -- no reject mechanism |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Not implemented |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-PDC-001 | **P0** | `base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement uses `{stat_name}: {value}` but the loop variable is `stat_value`, not `value`. Causes `NameError` when `global_map` is set. **CROSS-CUTTING**: Affects ALL components. |
| BUG-PDC-002 | **P1** | `python_dataframe_component.py:108-114` | **Silent output_columns fallthrough returns full DataFrame**: When `output_columns` is specified but no columns match, the full unfiltered DataFrame is returned. Caller expects filtered output. Silent data integrity violation. |
| BUG-PDC-003 | **P1** | `python_dataframe_component.py:105` | **No type check on `namespace['df']` after exec**: If user code reassigns `df` to a non-DataFrame value, the subsequent `len(output_df.columns)` crashes with unhelpful `AttributeError`. |
| BUG-PDC-004 | **P1** | `base_component.py` (`resolve_dict()`) | **`resolve_dict()` mangles `python_code` before execution**: Skips `java_code` and `imports` but NOT `python_code`. Pattern 2 regex replaces `context.xxx` references inside user Python code, silently corrupting it. **CROSS-CUTTING**: Affects all Python components. |
| BUG-PDC-005 | **P1** | `python_dataframe_component.py:87-89` | **Routine names from `**python_routines` can shadow critical namespace variables**: If a routine is named `df`, `pd`, `np`, `context`, or `globalMap`, it overwrites the corresponding namespace entry. No collision check exists. |
| BUG-PDC-006 | **P2** | `python_dataframe_component.py:57-59` | **Empty input path does not update stats**: When input is None or empty, method returns early without calling `_update_stats()`. Stats remain at initial zeros. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-PDC-001 | **P3** | **`python_code` config key**: Not a Talend parameter name (no Talend equivalent exists). Consistent with sibling `PythonRowComponent` and `PythonComponent`. Naming is internally consistent. No issue. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-PDC-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | No `_validate_config()` method defined. Only inline check for empty `python_code`. |
| STD-PDC-002 | **P2** | "Components SHOULD call `validate_schema()` on output" | `validate_schema()` is never called on the output DataFrame. User code is responsible for type correctness. |

### 6.4 Debug Artifacts

None found. Code is clean.

### 6.5 Security

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| SEC-PDC-001 | **P1** | **`exec()` with unrestricted `__builtins__`**: Line 102 calls `exec(python_code, namespace)` without restricting `__builtins__`. User code has full access to `import os`, `open()`, `subprocess`, `eval()`, `__import__()`, etc. For trusted internal use, this is acceptable. For any scenario where `python_code` comes from untrusted sources, this is a **remote code execution vulnerability**. |
| SEC-PDC-002 | **P2** | **`globalMap` and `context` expose live mutable state**: `globalMap` is a live reference -- user code can call `globalMap.clear()`, wiping ALL component statistics. `context` is a shallow copy via `_get_context_dict()` but does NOT deep-copy mutable values (lists, dicts). User code can mutate nested context values and corrupt state for downstream components. |

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Level usage | INFO for start/complete, WARNING for no input/missing columns, ERROR for execution failure -- correct |
| Sensitive data | No sensitive data logged. Python code content is NOT logged, even at DEBUG -- makes debugging difficult |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Exception types | `ValueError` for missing python_code (line 66). Generic `Exception` catch for exec errors (line 127). |
| Exception chaining | Line 129 uses bare `raise` (re-raise), preserving original traceback. Correct. |
| die_on_error handling | **Not implemented** -- all errors propagate unconditionally. No `die_on_error` config option. |
| Graceful degradation | **NONE** -- any exception crashes the component. No REJECT flow. No partial results. |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | `_process()` has `Dict[str, Any]` return type, `Optional[pd.DataFrame]` parameter -- correct |
| `_get_context_dict()` | Return type `Dict[str, Any]` -- correct |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-PDC-001 | **P2** | **`input_data.copy()` doubles memory**: Line 75 creates a full deep copy of the input DataFrame. For a 1GB DataFrame, this allocates an additional 1GB. Consider using pandas >= 2.0 copy-on-write. |
| PERF-PDC-002 | **P2** | **HYBRID streaming mode produces incorrect results**: `BaseComponent._execute_streaming()` splits DataFrame into chunks and calls `_process()` per chunk. User code relying on full DataFrame (aggregations, sorts, dedup) will produce wrong results. Component should force BATCH mode. |
| PERF-PDC-003 | **P3** | **`exec()` recompiles code on every call**: Each call to `_process()` recompiles the Python code string. Pre-compiling with `compile()` would avoid repeated parsing in streaming/iterate scenarios. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | HYBRID mode is UNSAFE -- user code may assume full DataFrame. Component should force BATCH. |
| Memory threshold | Inherited: `MEMORY_THRESHOLD_MB = 3072` (3GB). At this threshold, HYBRID switches to streaming, which is unsafe for this component. |
| Large data handling | `input_data.copy()` doubles memory. For large DataFrames, this is the bottleneck. |
| Namespace cleanup | No explicit cleanup after `exec()`. Objects created by user code persist until garbage collection. |

---

## 8. Testing

**N/A per D-82** -- Engine-native audit-only component. No test standardization required for this milestone.

**Current state**: Zero v1 unit tests exist for `PythonDataFrameComponent`. All 148 lines of engine code are unverified. Testing standardization is out of scope for D-82 audit-only treatment but remains a gap for future work.

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 2 | **BUG-PDC-001**, **ENG-PDC-001** |
| P1 | 8 | **SEC-PDC-001**, **ENG-PDC-002**, **ENG-PDC-003**, **ENG-PDC-004**, **BUG-PDC-002**, **BUG-PDC-003**, **BUG-PDC-004**, **BUG-PDC-005** |
| P2 | 8 | **ENG-PDC-005**, **ENG-PDC-006**, **SEC-PDC-002**, **STD-PDC-001**, **STD-PDC-002**, **PERF-PDC-001**, **PERF-PDC-002**, **BUG-PDC-006** |
| P3 | 2 | NAME-PDC-001, PERF-PDC-003 |
| **Total** | **20** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 6 | ENG-PDC-001 through ENG-PDC-006 |
| Bug (BUG) | 6 | BUG-PDC-001 through BUG-PDC-006 |
| Security (SEC) | 2 | SEC-PDC-001, SEC-PDC-002 |
| Standards (STD) | 2 | STD-PDC-001, STD-PDC-002 |
| Performance (PERF) | 3 | PERF-PDC-001 through PERF-PDC-003 |
| Naming (NAME) | 1 | NAME-PDC-001 |
| Converter (CONV) | 0 | N/A -- engine-native component |
| Testing (TEST) | 0 | N/A per D-82 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set (BUG-PDC-001) |
| XCUT-002 | `base_component.py` (`resolve_dict()`) | `resolve_dict()` corrupts `python_code` containing `context.xxx` (BUG-PDC-004) |

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-PDC-001): Change `value` to `stat_value` on `base_component.py` line 304. Cross-cutting fix for ALL components.

2. **Add error isolation / REJECT flow** (ENG-PDC-001): Wrap `exec()` in try/except, capture exception as reject output with `errorCode='PYTHON_ERROR'` and `errorMessage=str(e)`. Return `{'main': pd.DataFrame(), 'reject': reject_df}`. Matches sibling `PythonRowComponent`'s behavior.

### Short-term (Hardening)

1. **Restrict `__builtins__` in exec namespace** (SEC-PDC-001): Add `namespace['__builtins__'] = {...curated builtins...}` to provide safe builtins without `__import__`, `open`, `eval`, `exec`, `compile`.

2. **Fix output_columns fallthrough** (BUG-PDC-002 / ENG-PDC-003): When no specified columns exist, raise `ValueError` instead of silently returning the full DataFrame.

3. **Add type check after exec** (BUG-PDC-003 / ENG-PDC-004): Validate `isinstance(namespace.get('df'), pd.DataFrame)` and raise clear `TypeError` if not.

4. **Force BATCH mode** (ENG-PDC-005 / PERF-PDC-002): Override `_determine_execution_mode()` to always return `ExecutionMode.BATCH`.

5. **Add routine name collision check** (BUG-PDC-005): Before unpacking `**python_routines`, check for name collisions with reserved namespace keys (`df`, `pd`, `np`, `context`, `globalMap`).

6. **Add `resolve_dict()` skip for `python_code`** (BUG-PDC-004): Add `python_code` to the skip list alongside `java_code` and `imports`.

### Long-term (Optimization)

1. **Pre-compile user code** (PERF-PDC-003): Use `compile()` once, then `exec(compiled, namespace)` to avoid recompilation on repeated invocations.

2. **Consider copy-on-write** (PERF-PDC-001): For pandas >= 2.0, use `pd.option_context('mode.copy_on_write', True)` instead of explicit `.copy()`.

3. **Add `_validate_config()` method** (STD-PDC-001): Validate `python_code` is non-empty string, `output_columns` is list of strings if present.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Engine source | `src/v1/engine/components/transform/python_dataframe_component.py` | Primary engine analysis (148 lines) |
| Base component | `src/v1/engine/base_component.py` | Cross-cutting bug analysis, lifecycle |
| Sibling: PythonRowComponent | `src/v1/engine/components/transform/python_row_component.py` | REJECT flow comparison |
| Sibling: PythonComponent | `src/v1/engine/components/transform/python_component.py` | Namespace comparison |
| Severus Snake GitHub | `<https://github.com/ottensa/severus-snake`> | Confirmed no standard Talend tPythonDataFrame exists |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash -- NameError when `global_map` is set. Blocks stats writing for ALL components. |
| XCUT-002 | `base_component.py` (`resolve_dict()`) | `resolve_dict()` corrupts `python_code` containing `context.xxx` patterns before `exec()` runs. |

## Appendix C: Comparison with Sibling Python Components

| Feature | PythonDataFrameComponent | PythonRowComponent | PythonComponent |
| --------- | -------------------------- | -------------------- | ----------------- |
| Processing model | Full DataFrame (vectorized) | Row-by-row (`iterrows()`) | One-time (no data processing) |
| Input data required? | Yes (returns empty if None) | Yes (returns empty if None) | No (passes through input) |
| User code variable | `df` (DataFrame) | `input_row` + `output_row` (dicts) | N/A (just runs code) |
| REJECT flow | **NO** | **YES** (errorCode, errorMessage) | **NO** |
| `pd` in namespace | Yes | No | Yes |
| `np` in namespace | Yes | No | No |
| `print` in namespace | No | No | Yes |
| `sum`/`min`/`max` in namespace | Yes | No | Yes |
| Output schema validation | No | Yes (`_validate_output_row()`) | No |
| DataFrame copy | Yes (`input_data.copy()`) | N/A (row dicts) | No (passes through) |
| Error handling | Re-raise (crash) | Per-row catch (continue) | Re-raise (crash) |

**Key inconsistency**: `PythonRowComponent` has REJECT flow and per-row error handling, while `PythonDataFrameComponent` and `PythonComponent` do not. The namespace contents also vary across siblings.

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after gold-standard rewrite per D-82 (engine-native audit-only)*
