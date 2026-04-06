# Audit Report: tPythonRow / PythonRowComponent

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: N/A (engine-native component, no Talend XML converter)
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | N/A (engine-native; analogous to `tPythonRow` / `tJavaRow`) |
| **V1 Engine Class** | `PythonRowComponent` |
| **Engine File** | `src/v1/engine/components/transform/python_row_component.py` (201 lines) |
| **Converter Parser** | N/A -- engine-native component, not converted from Talend XML |
| **Converter Dispatch** | N/A |
| **Registry Aliases** | `PythonRowComponent`, `PythonRow`, `tPythonRow` (registered in `src/v1/engine/engine.py`) |
| **Category** | Transform / Custom Code |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/python_row_component.py` | Engine implementation (201 lines) |
| `src/v1/engine/base_component.py` | Base class: `execute()`, `_update_stats()`, `_update_global_map()`, `validate_schema()`, `get_python_routines()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/context_manager.py` | ContextManager: variable resolution, `get_all()` |
| `src/v1/engine/python_routine_manager.py` | PythonRoutineManager: discovers, loads, and exposes `.py` routine files |
| `src/v1/engine/components/transform/__init__.py` | Package exports (line 19: `from .python_row_component import PythonRowComponent`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **N/A** | -- | -- | -- | -- | Engine-native component; no Talend XML converter per D-82 |
| Engine Feature Parity | **Y** | 1 | 3 | 4 | 1 | `exec()` security; no `die_on_error`; no auto-passthrough; NaN handling; no IMPORT support |
| Code Quality | **Y** | 2 | 3 | 5 | 1 | Cross-cutting base class bugs; `exec()` without `__builtins__` restriction; shared mutable context_dict; incomplete type mapping |
| Performance & Memory | **Y** | 0 | 1 | 2 | 0 | `iterrows()` anti-pattern; `exec()` re-parses per row; `row.to_dict()` per row |
| Testing | **N/A** | -- | -- | -- | -- | Engine-native component; no test standardization per D-82 |

**Overall: YELLOW -- Usable for trusted converted jobs with known limitations; exec() security and iterrows() performance are primary concerns**

### Score Key

- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended
- **N/A**: Not applicable to this component

---

## 3. Talend Feature Baseline

### What PythonRowComponent Does

`PythonRowComponent` is an **engine-native** per-row Python code execution component. It is the Python equivalent of `tJavaRow` -- executing user-supplied Python code once per input row. There is no standard Talend Studio `tPythonRow` component; this is a custom v1 engine extension.

The component receives each row from an upstream flow as an `input_row` dictionary, provides an empty `output_row` dictionary for the user to populate, and executes the user's Python code via `exec()`. The populated `output_row` is collected and assembled into the output DataFrame. Rows where user code raises an exception are routed to a reject flow with `errorCode` and `errorMessage` columns.

The behavioral baseline is derived from the analogous `tJavaRow` Talend component (which IS extensively documented) and the component's own engine contract. The v1 engine provides access to `context`, `globalMap`, and Python routines within the execution namespace.

**Source**: [tJavaRow input_row/output_row pattern](http://garpitmzn.blogspot.com/2014/11/using-tjavarow-inputrow-and-outputrow.html), [Severus Snake Python component for Talend (GitHub)](https://github.com/ottensa/severus-snake), [Talend Custom Code Components (TalendByExample)](https://www.talendbyexample.com/talend-custom-code-component-reference.html)
**Component family**: Transform / Custom Code (analogous to tJavaRow)
**Available in**: v1 engine only (engine-native)

### 3.1 Engine Configuration Parameters

| # | Parameter | Config Key | Type | Default | Description |
| --- | ----------- | ----------- | ------ | --------- | ------------- |
| 1 | Python Code | `python_code` | Multi-line string | `''` | **Mandatory**. Python code executed per row. Access to `input_row`, `output_row`, `context`, `globalMap`, `routines`. |
| 2 | Output Schema | `output_schema` | Dict[str, str] | `{}` | Optional column-name-to-type mapping for output validation. When provided, `_validate_output_row()` enforces type conversion. |

### 3.2 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Input rows from upstream. Each row presented as `input_row` dict. |
| `FLOW` (Main) | Output | Row > Main | Successfully transformed rows via `output_row`. |
| `REJECT` | Output | Row > Reject | Rows where Python code raised an exception. Appends `errorCode` and `errorMessage`. |

### 3.3 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total number of input rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully output via FLOW |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows sent to REJECT |

### 3.4 Behavioral Notes

1. **`input_row` / `output_row` pattern**: Each row is converted to a Python dict via `row.to_dict()`. User code reads `input_row` and populates `output_row`. The `output_row` starts empty (`{}`) each iteration -- there is no auto-passthrough of input columns.

2. **`globalMap` access**: User code can read/write globalMap directly. The object reference is shared across all rows, enabling cross-row state accumulation (counters, running totals).

3. **`context` access**: Context variables are flattened into a dict, accessible as `context['var_name']`. The dict is created once before the row loop and shared across all rows.

4. **`routines` access**: Python routines are available both as a `routines` dict and spread directly into the namespace (via `**python_routines`), enabling direct function calls.

5. **REJECT flow**: Rows where user code raises an exception are caught per-row and added to reject output with `errorCode='PYTHON_ERROR'` and `errorMessage=str(e)`.

6. **No `die_on_error`**: All errors are silently collected in reject. No option to halt execution on first error.

7. **No auto-passthrough**: Unlike tJavaRow's `MAP_TYPE=MAP` behavior, input columns are NOT auto-copied to output. User code must explicitly set every output column.

8. **Exec namespace**: The namespace includes `input_row`, `output_row`, `context`, `globalMap`, `routines`, spread routine functions, and explicit builtins (`len`, `str`, `int`, `float`, `bool`). Full `__builtins__` are also available (unrestricted).

---

## 4. Converter Analysis

**N/A** -- PythonRowComponent is an engine-native component. It is not converted from Talend XML. Job configurations are provided directly in v1 JSON format. No `talend_to_v1` converter exists or is needed for this component.

---

## 5. Converter Code Quality

**N/A per D-82** -- Engine-native component. No converter code to audit.

---

## 6. Test Coverage

**N/A per D-82** -- Engine-native component. Test standardization is out of scope for this audit.

---

## 7. Configuration Comparison

Since PythonRowComponent is engine-native, there is no Talend XML configuration to compare. The engine reads configuration directly from v1 job JSON.

### Engine Config Keys

| # | Config Key | Read By | Default | Usage |
| --- | ----------- | --------- | --------- | ------- |
| 1 | `python_code` | `_process()` line 51 | `''` | Mandatory. Raises `ValueError` if empty. |
| 2 | `output_schema` | `_process()` line 52 | `{}` | Optional. When non-empty, triggers `_validate_output_row()` per row. |

### Comparison with tJavaRow Engine

| Aspect | tJavaRow (v1) | PythonRowComponent (v1) | Gap |
| -------- | --------------- | ------------------------- | ----- |
| Row-by-row code execution | Yes (via Java bridge) | Yes (via `exec()`) | -- |
| `input_row` / `output_row` | Yes (Java bridge vars) | Yes (Python namespace dicts) | -- |
| `die_on_error` support | Via Java bridge error handling | **No** -- all errors collected | P1 |
| Auto-passthrough (MAP_TYPE) | Via Java bridge | **No** -- empty output_row | P1 |
| IMPORT / setup code | Via Java bridge imports | **No** -- no imports support | P2 |
| Code pre-compilation | N/A (Java bridge handles) | **No** -- `exec()` re-parses per row | P2 |
| Security sandboxing | JVM sandbox | **No** -- unrestricted `__builtins__` | P0 (security) |
| REJECT flow | Via Java bridge exceptions | Yes (per-row try/except) | -- |
| Statistics tracking | Via base class | Via base class | -- |

---

## 8. Engine Gaps

### 8.1 Security: `exec()` Without Sandboxing

**SEC-PRC-001 (P0)**: The `exec(python_code, namespace)` call on line 94 passes a namespace that does NOT restrict `__builtins__`. User code has access to `open()`, `__import__()`, `eval()`, `compile()`, and every built-in function. User code can:

- Read/write arbitrary files via `open()`
- Import arbitrary modules via `__import__()`
- Execute shell commands via `__import__('subprocess').run(...)`
- Access environment variables via `__import__('os').environ`
- Make network calls via `__import__('urllib.request').urlopen(...)`

While acceptable for trusted converted Talend jobs, this is a critical risk if config JSON could be tampered with or if untrusted users can define component configs.

### 8.2 Performance: `iterrows()` Anti-Pattern

**PERF-PRC-001 (P1)**: `for idx, row in input_data.iterrows()` on line 70 is the slowest way to iterate a pandas DataFrame. Each iteration creates a new Series object, copies data, and performs type inference. For 1M rows, this is orders of magnitude slower than vectorized operations or `itertuples()`. While row-by-row `exec()` inherently prevents vectorization, `itertuples()` is approximately 10x faster for the iteration itself.

### 8.3 Missing `die_on_error` Support

**ENG-PRC-002 (P1)**: The engine has no `die_on_error` parameter handling. All exceptions are caught per-row (line 105) and routed to reject. In the analogous tJavaRow, `DIE_ON_ERROR=true` (the default) stops the entire job on the first code error. The v1 engine always silently collects errors, which can mask critical bugs in user code.

### 8.4 No Auto-Passthrough of Input Columns

**ENG-PRC-003 (P1)**: The engine always starts with an empty `output_row = {}` (line 74). If user code does not explicitly set every output column, those columns are missing from the output DataFrame. In tJavaRow with `MAP_TYPE=MAP` (default), columns present in both input and output schemas that are not explicitly set are auto-copied. This silently drops data for common patterns like setting one new column while expecting all input columns to pass through.

### 8.5 NaN Values in `input_row` Not Handled

**ENG-PRC-004 (P1)**: When pandas DataFrame cells contain `NaN` (numeric columns) or `NaT` (date columns), these values are passed directly to `input_row` via `row.to_dict()`. Python code like `input_row['age'] + 1` produces `NaN` silently rather than raising an error. Talend's tJavaRow exposes null as Java `null`, which causes `NullPointerException` -- a more visible failure mode.

### 8.6 No `IMPORT` / Setup Code Support

**ENG-PRC-006 (P2)**: No support for import statements or setup code that runs once before the row loop. User code cannot `import pandas`, `import re`, `import json`, etc. Only the explicitly added builtins and routines are available in the namespace.

### 8.7 `{id}_ERROR_MESSAGE` Not Set in GlobalMap

**ENG-PRC-008 (P2)**: When errors occur, the error message is logged but not stored in globalMap for downstream reference.

### 8.8 Empty String vs NaN Handling Inconsistency

**ENG-PRC-007 (P2)**: Talend treats empty strings and null as distinct values. The v1 engine's pandas backend may have empty strings (via `keep_default_na=False` upstream) or `NaN` (without that flag), creating inconsistent behavior depending on which upstream component produced the data.

### 8.9 `globalMap.get()` Broken in User Code

**ENG-PRC-005 (P2)**: If user Python code calls `globalMap.get("key")`, it will hit the broken `GlobalMap.get()` method (global_map.py line 28) which references undefined `default` variable. This crashes with `NameError`. Cross-cutting bug.

### 8.10 `output_row` Rebinding Behavior

**ENG-PRC-009 (P3)**: Line 97 reads `output_row = namespace['output_row']`. Both mutation (`output_row['a'] = 1`) and rebinding (`output_row = {"a": 1}`) work correctly because the namespace dict is checked after exec. This is correct and more flexible than Talend.

---

## 9. Issues Summary

### 9.1 Engine Issues

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| SEC-PRC-001 | **P0** | `exec()` with unrestricted `__builtins__` -- arbitrary code execution |
| ENG-PRC-002 | **P1** | No `die_on_error` support -- all errors silently collected |
| ENG-PRC-003 | **P1** | No auto-passthrough of input columns -- silent data loss |
| ENG-PRC-004 | **P1** | NaN values in `input_row` propagate silently instead of raising errors |
| ENG-PRC-005 | **P2** | `globalMap.get()` broken in user code (cross-cutting GlobalMap bug) |
| ENG-PRC-006 | **P2** | No IMPORT / setup code support |
| ENG-PRC-007 | **P2** | Empty string vs NaN handling inconsistent |
| ENG-PRC-008 | **P2** | `{id}_ERROR_MESSAGE` not set in globalMap |
| ENG-PRC-009 | **P3** | `output_row` rebinding behavior should be documented |

### 9.2 Code Quality Issues

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| BUG-PRC-001 | **P0** | `_update_global_map()` references undefined variable `value` (CROSS-CUTTING, base_component.py:304) |
| BUG-PRC-002 | **P0** | `GlobalMap.get()` references undefined `default` parameter (CROSS-CUTTING, global_map.py:28) |
| BUG-PRC-003 | **P1** | `iterrows()` returns numpy types, not Python native types -- `isinstance(val, int)` fails |
| BUG-PRC-004 | **P1** | Namespace adds explicit builtins redundantly while `__builtins__` unrestricted -- misleading |
| BUG-PRC-009 | **P1** | Cross-row state leak via shared mutable `context_dict` -- diverges from Talend immutable context |
| BUG-PRC-005 | **P2** | `_validate_output_row()` silently drops extra columns not in schema |
| BUG-PRC-006 | **P2** | Type mapping incomplete -- missing Date, Long, BigDecimal, Short, Byte |
| BUG-PRC-007 | **P2** | `exec()` re-parses/compiles code string every row -- no `compile()` pre-compilation |
| BUG-PRC-010 | **P2** | `_update_global_map()` crash in error handler masks original exception (CROSS-CUTTING) |
| BUG-PRC-011 | **P2** | `globalMap` can be None -- user code calling `globalMap.put()` crashes with AttributeError |
| NAME-PRC-002 | **P3** | `PythonRowComponent` has `Component` suffix -- internally consistent within code-execution family |

### 9.3 Performance Issues

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| PERF-PRC-001 | **P1** | `iterrows()` anti-pattern -- approximately 10x slower than `itertuples()` |
| PERF-PRC-002 | **P2** | `exec()` re-parses code every row -- should use `compile()` |
| PERF-PRC-003 | **P2** | `row.to_dict()` creates new dict per row -- memory churn for wide DataFrames |

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 3 | SEC-PRC-001, BUG-PRC-001, BUG-PRC-002 |
| P1 | 7 | ENG-PRC-002, ENG-PRC-003, ENG-PRC-004, BUG-PRC-003, BUG-PRC-004, BUG-PRC-009, PERF-PRC-001 |
| P2 | 11 | ENG-PRC-005, ENG-PRC-006, ENG-PRC-007, ENG-PRC-008, BUG-PRC-005, BUG-PRC-006, BUG-PRC-007, BUG-PRC-010, BUG-PRC-011, PERF-PRC-002, PERF-PRC-003 |
| P3 | 2 | ENG-PRC-009, NAME-PRC-002 |
| **Total** | **23** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 8 | ENG-PRC-002 through ENG-PRC-009 |
| Security (SEC) | 1 | SEC-PRC-001 |
| Bug (BUG) | 9 | BUG-PRC-001 through BUG-PRC-011 |
| Performance (PERF) | 3 | PERF-PRC-001, PERF-PRC-002, PERF-PRC-003 |
| Naming (NAME) | 1 | NAME-PRC-002 |
| Converter (CONV) | 0 | N/A -- engine-native component |
| Standards (STD) | 0 | N/A -- engine-native component |
| Testing (TEST) | 0 | N/A per D-82 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| BUG-PRC-001 | `base_component.py:304` | `_update_global_map()` crash -- results lost after processing |
| BUG-PRC-002 | `global_map.py:28` | `GlobalMap.get()` crash -- user Python code calling `globalMap.get()` fails |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Restrict `__builtins__` in `exec()` namespace** (SEC-PRC-001): Set `namespace['__builtins__'] = {}` and explicitly add only safe builtins. For production use with untrusted configs, consider `RestrictedPython` or equivalent sandboxing.

2. **Fix cross-cutting `_update_global_map()` bug** (BUG-PRC-001): Change `value` to `stat_value` on `base_component.py` line 304. Fixes ALL components. Very low risk.

3. **Fix cross-cutting `GlobalMap.get()` bug** (BUG-PRC-002): Add `default: Any = None` parameter to the `get()` method signature. Fixes ALL components and user Python code. Very low risk.

### Short-Term (Hardening)

1. **Add `die_on_error` support** (ENG-PRC-002): Read `die_on_error` from config (default `True`). When `True`, re-raise first per-row exception. When `False`, use current reject-collection behavior.

2. **Implement auto-passthrough** (ENG-PRC-003): Pre-populate `output_row` with `input_row.copy()` before executing user code. Make conditional on `auto_passthrough` config flag (default `True`).

3. **Pre-compile Python code** (BUG-PRC-007, PERF-PRC-002): Before the row loop, call `compiled_code = compile(python_code, '<python_row>', 'exec')`. Inside the loop, use `exec(compiled_code, namespace)`.

4. **Replace `iterrows()` with `itertuples()`** (PERF-PRC-001): Approximately 10x faster iteration. Requires adapting `input_row` construction from namedtuple to dict.

5. **Handle NaN/None in `input_row`** (ENG-PRC-004): After `row.to_dict()`, replace `NaN`/`NaT` with `None`: `input_row = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}`.

6. **Add IMPORT / setup code support** (ENG-PRC-006): Accept `imports` config key. Execute once before row loop via `exec(imports, namespace)`.

7. **Fix shared mutable `context_dict`** (BUG-PRC-009): Create a fresh copy of context_dict per row, or document that mutations persist across rows.

### Long-Term (Optimization)

1. **Complete type mapping** (BUG-PRC-006): Add Date, Long, BigDecimal, Short, Byte to `_validate_output_row()` type mapping.

2. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-PRC-008): Store last error message in globalMap after processing.

3. **Optimize `row.to_dict()`** (PERF-PRC-003): For wide DataFrames, consider direct column access from Series rather than creating dict copies.

4. **Fix streaming mode reject loss**: Modify `_execute_streaming()` in `base_component.py` to collect reject DataFrames from each chunk.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Engine source | `src/v1/engine/components/transform/python_row_component.py` | Engine feature analysis (201 lines) |
| Base component | `src/v1/engine/base_component.py` | Cross-cutting bug analysis |
| GlobalMap | `src/v1/engine/global_map.py` | GlobalMap bug analysis |
| tJavaRow reference | [TalendByExample](http://garpitmzn.blogspot.com/2014/11/using-tjavarow-inputrow-and-outputrow.html) | Behavioral baseline |
| Severus Snake | [GitHub](https://github.com/ottensa/severus-snake) | Python component reference |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash -- undefined `value` variable. ALL processing results lost when globalMap is set. |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` crash -- undefined `default` parameter. User Python code calling `globalMap.get()` fails with NameError. |
| XCUT-003 | `base_component.py:267-278` | `_execute_streaming()` drops reject DataFrames -- only `main` collected in streaming mode. |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after gold-standard rewrite per D-82 (audit-only, Sections 5+6 N/A)*
