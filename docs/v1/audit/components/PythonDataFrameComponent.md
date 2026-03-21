# Audit Report: tPythonDataFrame / PythonDataFrameComponent

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter` (generic path -- no dedicated parser)
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tPythonDataFrame` (NOT a standard Talend component -- custom/proprietary to this project) |
| **V1 Engine Class** | `PythonDataFrameComponent` |
| **Engine File** | `src/v1/engine/components/transform/python_dataframe_component.py` (149 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` default fallthrough (line 385: `return config_raw`) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> NO dedicated `elif` branch; falls through to generic `parse_base_component()` |
| **Registry Aliases** | `PythonDataFrameComponent`, `PythonDataFrame`, `tPythonDataFrame` (registered in `src/v1/engine/engine.py` lines 136-138) |
| **Category** | Transform / Python Scripting |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/python_dataframe_component.py` | Engine implementation (149 lines) |
| `src/converters/complex_converter/component_parser.py` (line 64, lines 384-386) | Type mapping + generic parameter fallthrough |
| `src/converters/complex_converter/converter.py` (lines 216-382) | Dispatch -- no dedicated `elif` for `tPythonDataFrame`; uses generic `parse_base_component()` path |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/components/transform/__init__.py` | Package exports (line 18, line 47) |
| `src/v1/engine/components/transform/python_row_component.py` | Sibling component `PythonRowComponent` for comparison (has REJECT flow) |
| `src/v1/engine/components/transform/python_component.py` | Sibling component `PythonComponent` for comparison (one-time execution) |

### Talend Provenance

**Web search result** ([Talend Component Reference](https://www.talendbyexample.com/talend-component-reference.html), [Severus Snake GitHub](https://github.com/ottensa/severus-snake), [Talend Community - Python](https://community.talend.com/s/topic/0TO3p000000RXdAGAW/python?language=en_US)): `tPythonDataFrame` does NOT exist in standard Talend. Talend has no native Python scripting components. The community-created [Severus Snake](https://github.com/ottensa/severus-snake) provides Python integration but does not define `tPythonDataFrame`. This component is **entirely custom to this ETL engine project** -- it has no Talend equivalent and no Talend XML source jobs would ever contain a `tPythonDataFrame` node. It exists purely as a Pythonic alternative to `tJavaRow`/`tJava` for users writing V1 JSON configs by hand.

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 1 | 0 | No dedicated parser; raw config dump; `CODE` -> `python_code` key mismatch if Talend XML ever used |
| Engine Feature Parity | **Y** | 1 | 3 | 2 | 0 | No REJECT flow; `exec()` security; no output_columns warning for missing cols; no streaming-aware chunked exec |
| Code Quality | **Y** | 1 | 4 | 3 | 1 | Cross-cutting `_update_global_map()` crash; `exec()` with no sandboxing; missing `__builtins__` restriction; df copy overhead; `resolve_dict()` mangles `python_code`; routine name shadowing destroys namespace |
| Performance & Memory | **G** | 0 | 0 | 2 | 1 | `.copy()` on every call; HYBRID streaming mode calls `_process()` per chunk but user code may not be chunk-safe |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Component Feature Baseline

### What tPythonDataFrame Does

`PythonDataFrameComponent` executes arbitrary user-supplied Python code against the entire input DataFrame at once (vectorized operations). Unlike `PythonRowComponent` which iterates row by row, this component hands the full `pd.DataFrame` to user code, enabling efficient bulk transformations using pandas/numpy APIs. The user modifies the DataFrame in-place (variable `df` in namespace), and the component returns the modified DataFrame as output.

**Source**: Custom component -- no Talend documentation. Defined entirely in `src/v1/engine/components/transform/python_dataframe_component.py`.

**Component family**: Transform / Python Scripting (Custom)
**Available in**: V1 engine only (no Talend equivalent)
**Dependencies**: `pandas`, `numpy` (imported at module level)

### 3.1 Configuration Parameters

| # | Config Key | Type | Default | Required | Description |
|---|------------|------|---------|----------|-------------|
| 1 | `python_code` | String (Python source) | `''` | **Yes** | Python code to execute. Has access to `df`, `pd`, `np`, `context`, `globalMap`, `routines`, and common builtins. Must modify `df` in-place or reassign within the namespace. |
| 2 | `output_columns` | List[str] | `None` | No | List of column names to keep in output. If provided, only these columns appear in the output DataFrame. If `None`, all columns pass through. |

### 3.2 Execution Namespace

The following variables are available inside user-supplied `python_code`:

| Variable | Type | Description |
|----------|------|-------------|
| `df` | `pd.DataFrame` | The input DataFrame (a `.copy()` of input). User code modifies this. |
| `pd` | module | `pandas` library |
| `np` | module | `numpy` library |
| `context` | `Dict[str, Any]` | Flattened context variables from `ContextManager` (shallow copy -- mutable values shared with original; see SEC-PDC-002) |
| `globalMap` | `GlobalMap` | Global variable storage (live reference, not a copy) |
| `routines` | `Dict[str, Any]` | Python routines from `PythonRoutineManager` |
| `**python_routines` | unpacked | All routines available directly by name (e.g., `StringRoutine.format_name`) |
| `len`, `str`, `int`, `float`, `bool`, `sum`, `min`, `max` | builtins | Common Python builtins |

**NOT available**: `print`, `open`, `import`, `os`, `sys`, `datetime`, `__builtins__` (implicitly available via `exec()` -- see SEC-PDC-001).

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Input DataFrame from upstream component |
| `FLOW` (Main) | Output | Row > Main | Modified DataFrame after Python code execution |
| `REJECT` | Output | Row > Reject | **NOT IMPLEMENTED** -- errors crash the component or propagate up |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of input rows (from `_update_stats(rows_read=len(input_data))`) |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of output rows (from `_update_stats(rows_ok=len(output_df))`) |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Always 0 -- hardcoded in `_update_stats(rows_reject=0)` |
| `{id}_ERROR_MESSAGE` | String | On error | **NOT SET** -- errors propagate as exceptions |

### 3.5 Behavioral Notes

1. **DataFrame is copied before execution**: Line 75 creates `df = input_data.copy()`. User code modifies the copy, not the original. This is correct for data isolation but doubles memory usage.

2. **`exec()` is used for code execution**: Line 102 calls `exec(python_code, namespace)`. This executes arbitrary Python code with NO sandboxing. The full Python runtime is available including file I/O, network access, and system commands via `__builtins__`.

3. **Output DataFrame comes from namespace**: Line 105 reads `output_df = namespace['df']`. If user code reassigns `df` to a new DataFrame (e.g., `df = df.groupby(...).agg(...)`), the new DataFrame is picked up. If user code reassigns to a non-DataFrame, a crash will occur on `len(output_df.columns)` (line 123).

4. **`output_columns` filtering is lenient**: Lines 108-114 filter columns silently. If NONE of the specified columns exist, a warning is logged but the FULL unfiltered DataFrame is returned. This is a data integrity risk -- the caller expects filtered output but gets everything.

5. **No input validation on `python_code`**: The only check is `if not python_code:` (line 65). No syntax checking, no compilation step, no attempt to detect dangerous operations.

6. **Sibling comparison -- PythonRowComponent has REJECT flow**: `PythonRowComponent` (lines 105-111) catches per-row exceptions and routes them to a reject DataFrame with `errorCode` and `errorMessage`. `PythonDataFrameComponent` does NOT -- any exception in user code crashes the entire component.

7. **Empty/None input returns empty DataFrame**: Line 57 checks `if input_data is None or input_data.empty:` and returns `{'main': pd.DataFrame()}`. Statistics are not updated in this path -- `NB_LINE` remains 0.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter handles `tPythonDataFrame` through the **generic fallthrough path**:

1. `converter.py:_parse_component()` has NO `elif component_type == 'tPythonDataFrame'` branch (confirmed by examining lines 232-381)
2. `parse_base_component()` processes all `elementParameter` nodes into `config_raw` dict (lines 433-458)
3. `_map_component_parameters('tPythonDataFrame', config_raw)` has no matching case, falls to line 385: `return config_raw`
4. The raw XML parameter names are dumped directly into `config`

**Critical mismatch**: The engine expects `config['python_code']` (line 62) but the converter would output `config['CODE']` (the Talend XML parameter name). This means **Talend XML -> converter -> engine would fail** because the engine would see `python_code = ''` and raise `ValueError`.

However, since `tPythonDataFrame` is NOT a standard Talend component, no Talend XML would ever contain it. Jobs using this component are written as hand-crafted V1 JSON configs where the user directly specifies `python_code` and `output_columns`. The converter mapping exists only for type aliasing (`tPythonDataFrame` -> `PythonDataFrameComponent` on line 64 of `component_parser.py`).

| # | Expected Config Key | Converter Produces | Matches? | Notes |
|---|--------------------|--------------------|----------|-------|
| 1 | `python_code` | `CODE` (raw XML) | **No** | Engine expects `python_code`, converter dumps `CODE`. Would fail if Talend XML existed. |
| 2 | `output_columns` | Not extracted | **N/A** | No Talend XML parameter for this. User must specify in JSON config. |

**Summary**: The converter mapping is non-functional for XML-sourced jobs. Acceptable because `tPythonDataFrame` is custom and only used in hand-crafted JSON configs.

### 4.2 Schema Extraction

Schema is extracted generically in `parse_base_component()` (lines 475-508 of `component_parser.py`).

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types (`str`, `int`, etc.) |
| `nullable` | Yes | Boolean conversion from string |
| `key` | Yes | Boolean conversion from string |
| `length` | Yes | Integer conversion, only if attribute present |
| `precision` | Yes | Integer conversion, only if attribute present |
| `pattern` (date) | Yes | Java date pattern converted to Python strftime |

**Note**: Schema extraction is irrelevant for this component since `PythonDataFrameComponent._process()` does NOT call `validate_schema()`. The user's Python code is responsible for all type handling.

### 4.3 Expression Handling

- **Java expression marking**: `tPythonDataFrame` is NOT in the skip list (line 462: only `tMap`, `tJavaRow`, `tJava`). However, the `CODE` field IS in `skip_fields` (line 464), so the Python code itself won't be mangled with `{{java}}` markers.
- **Context variable wrapping**: `CODE` is excluded from context variable wrapping (line 449: `name not in ['CODE', 'IMPORT']`). Python code containing `context.` references won't be corrupted.
- **Overall**: The converter's expression handling correctly avoids corrupting the CODE field, but the key naming mismatch (CODE vs python_code) makes the entire converter path non-functional.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-PDC-001 | **P1** | **No dedicated parser method**: `tPythonDataFrame` uses the generic `_map_component_parameters()` fallthrough which dumps raw XML parameter names. There is no `parse_python_dataframe()` method. If this component were ever used in a Talend XML context, the `CODE` -> `python_code` key mismatch would cause immediate runtime failure. |
| CONV-PDC-002 | **P1** | **Not in converter dispatch**: `converter.py:_parse_component()` has no `elif component_type == 'tPythonDataFrame'` branch. Falls to generic path. Sibling `tJavaRow` HAS a dedicated branch (line 375). The Python counterpart should match. |
| CONV-PDC-003 | **P2** | **Java expression marking not skipped**: `tPythonDataFrame` is NOT in the component skip list on line 462 (`['tMap', 'tJavaRow', 'tJava']`). While `CODE` is in `skip_fields`, other parameters (e.g., a hypothetical `PYTHON_CODE` or `OUTPUT_COLUMNS`) would be subject to Java expression marking, which could corrupt them with `{{java}}` prefixes. Should add `tPythonDataFrame`, `tPythonRow`, and `tPython` to the skip list for defensive correctness. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|---------|-------------|----------|-----------------|-------|
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
| 11 | **REJECT flow** | **No** | N/A | -- | **No reject output. Any exception crashes the component.** |
| 12 | **Output type validation** | **No** | N/A | -- | **No check that `namespace['df']` is still a DataFrame after user code** |
| 13 | **Schema validation** | **No** | N/A | -- | **`validate_schema()` never called on output** |
| 14 | **User code compilation check** | **No** | N/A | -- | **No `compile()` before `exec()` -- syntax errors only caught at runtime** |
| 15 | **Streaming-aware execution** | **No** | N/A | -- | **HYBRID mode chunks data, but user code may assume full DataFrame** |

### 5.2 Behavioral Differences from Sibling Components

| ID | Priority | Description |
|----|----------|-------------|
| ENG-PDC-001 | **P0** | **No REJECT flow**: Unlike sibling `PythonRowComponent` (lines 105-111 of `python_row_component.py`) which catches per-row exceptions and routes them to a reject DataFrame with `errorCode` and `errorMessage`, `PythonDataFrameComponent` has NO error isolation. A single exception in user code (e.g., `KeyError` on a missing column) crashes the entire component. The catch on line 127 merely re-raises. For a component executing arbitrary user code, this is a critical reliability gap. |
| ENG-PDC-002 | **P1** | **`exec()` with no sandbox**: Line 102 calls `exec(python_code, namespace)` without restricting `__builtins__`. User code has full access to `import os`, `open()`, `subprocess`, `eval()`, `__import__()`, etc. While `PythonComponent` (sibling) also uses unrestricted `exec()`, that component explicitly imports `os`, `sys`, `datetime` into namespace. The inconsistency creates confusion about what is intentionally available. For production use with untrusted code, `__builtins__` should be restricted (e.g., `namespace['__builtins__'] = {}`). |
| ENG-PDC-003 | **P1** | **Silent output_columns fallthrough**: Lines 108-114: when `output_columns` is specified but NONE of the listed columns exist in the DataFrame, the code logs a warning but returns the FULL unfiltered DataFrame. This violates the principle of least surprise -- the caller explicitly requested column filtering and gets unfiltered output. Should either raise an error or return an empty DataFrame. |
| ENG-PDC-004 | **P1** | **No validation that `namespace['df']` remains a DataFrame**: Line 105 reads `output_df = namespace['df']`. If user code does `df = "not a dataframe"` or `del df`, the subsequent `len(output_df.columns)` on line 123 will crash with an unhelpful `AttributeError`. Should validate type before using. |
| ENG-PDC-005 | **P2** | **HYBRID streaming mode is unsafe for this component**: `BaseComponent._execute_streaming()` (line 262) chunks the input DataFrame and calls `_process()` per chunk. User code that assumes the full DataFrame (e.g., `df.groupby().agg()`, `df.sort_values()`, `df.drop_duplicates()`) will produce WRONG RESULTS when executed on individual chunks. This component should force `BATCH` mode or document the streaming limitation prominently. |
| ENG-PDC-006 | **P2** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur, the exception propagates but no error message is stored in globalMap for downstream reference. Sibling `PythonComponent` also has this gap. |

### 5.3 GlobalMap Variable Coverage

| Variable | Expected | V1 Sets? | How V1 Sets It | Notes |
|----------|----------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Reflects actual output row count (may differ from input if user code adds/removes rows) |
| `{id}_NB_LINE_REJECT` | Yes | **Hardcoded 0** | `_update_stats(rows_reject=0)` on line 121 | Always 0 -- no reject mechanism exists |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-PDC-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the loop variable is `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: Affects ALL components including `PythonDataFrameComponent`. Every successful execution of this component will crash in the statistics logging step if `global_map` is set. |
| BUG-PDC-002 | **P1** | `python_dataframe_component.py:108-114` | **Silent output_columns fallthrough returns full DataFrame**: When `output_columns=['col_a', 'col_b']` but the DataFrame has columns `['x', 'y', 'z']`, `available_cols` is `[]` (empty). The `if available_cols:` check fails, so no filtering occurs. The warning is logged but the FULL unfiltered DataFrame is returned. The caller expects only `col_a, col_b` but gets `x, y, z`. This is a **silent data integrity violation**. |
| BUG-PDC-003 | **P1** | `python_dataframe_component.py:105` | **No type check on `namespace['df']` after exec**: If user code reassigns `df` to a non-DataFrame value (e.g., `df = None`, `df = 42`, `df = df.values`), the subsequent `len(output_df.columns)` on line 123 will crash with `AttributeError: 'NoneType' object has no attribute 'columns'` (or similar). No defensive type check exists. |
| BUG-PDC-004 | **P1** | `src/v1/engine/base_component.py` (`resolve_dict()`) | **`resolve_dict()` mangles `python_code` before execution**: `resolve_dict()` skips `java_code` and `imports` but does NOT skip `python_code`. The Pattern 2 regex replaces `context.xxx` references inside user Python code before `exec()` runs. This means any Python code containing `context.some_var` as a dotted attribute access (e.g., `context.my_setting`) is subject to string-level substitution, silently corrupting user code if the context variable does not exist or resolves to an unexpected string representation. **CROSS-CUTTING**: Affects ALL Python components (`PythonDataFrameComponent`, `PythonRowComponent`, `PythonComponent`). |
| BUG-PDC-005 | **P1** | `python_dataframe_component.py:87-89` (namespace construction) | **Routine names from `**python_routines` can shadow critical namespace variables**: Routines are unpacked into the `exec()` namespace via `**python_routines`. If a routine is named `df`, `pd`, `np`, `context`, or `globalMap`, it overwrites the corresponding namespace entry, destroying DataFrame access, pandas/numpy access, or context/globalMap access. A routine named `df` would silently replace the input DataFrame with a routine object, causing immediate or deferred crashes in user code. No collision check exists. |
| BUG-PDC-006 | **P2** | `python_dataframe_component.py:57-59` | **Empty input path does not update stats**: When `input_data is None or input_data.empty`, the method returns early without calling `_update_stats()`. The stats remain at initial values (all zeros), which is technically correct, but `_update_global_map()` is still called by `BaseComponent.execute()` line 218. This is consistent with siblings but worth noting -- the base class always calls `_update_global_map()` regardless of early return. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-PDC-001 | **P3** | **`python_code` config key**: Not a Talend parameter name (no Talend equivalent exists). Consistent with sibling `PythonRowComponent` and `PythonComponent` which also use `python_code`. Naming is internally consistent. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-PDC-001 | **P2** | "Every component MUST have its own `parse_*` method" (STANDARDS.md) | Uses generic `_map_component_parameters()` fallthrough. No dedicated `parse_python_dataframe()` method exists in `component_parser.py`. While acceptable for a custom component unlikely to appear in Talend XML, it violates the stated standard. |
| STD-PDC-002 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | No `_validate_config()` method defined. Neither `PythonDataFrameComponent` nor its base class enforces validation. The only check is the inline `if not python_code:` on line 65. |
| STD-PDC-003 | **P2** | "Components SHOULD call `validate_schema()` on output" | `validate_schema()` is never called on the output DataFrame. User code is fully responsible for type correctness. This is arguably intentional (user code controls types), but differs from most other components. |

### 6.4 Debug Artifacts

No debug artifacts found. Code is clean.

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-PDC-001 | **P1** | **`exec()` with unrestricted `__builtins__`**: Line 102 calls `exec(python_code, namespace)`. Since `__builtins__` is NOT explicitly set in the namespace dict, Python provides the full builtins module. User code can execute `import os; os.system('rm -rf /')`, `open('/etc/passwd').read()`, `__import__('subprocess').call(...)`, etc. For trusted internal use, this is acceptable. For any scenario where `python_code` comes from user input, external configs, or converted Talend XML (where a malicious job designer could inject code), this is a **remote code execution vulnerability**. |
| SEC-PDC-002 | **P2** | **`globalMap` and `context` both expose live mutable state**: Line 86 passes `self.global_map` directly into the namespace. User code can call `globalMap.clear()`, wiping ALL component statistics and shared variables for the entire job. **Correction**: The original audit incorrectly stated that `context` is a safe copy via `_get_context_dict()`. While `_get_context_dict()` creates a new `dict`, it does NOT deep-copy mutable values (lists, dicts, objects) within the context. User code can mutate nested mutable values (e.g., `context['my_list'].append(...)`) and corrupt the original context state for downstream components. Both `globalMap` (live reference) and `context` (shallow copy with shared mutable values) can be corrupted by buggy user code. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `f"Component {self.id}:"` prefix -- correct |
| Level usage | INFO for processing start/complete, WARNING for no input and missing output_columns, ERROR for execution failure -- correct |
| Start/complete logging | `_process()` logs start (line 77) and completion (line 123) with row/column counts -- correct |
| Sensitive data | No sensitive data logged. **However**: Python code content is NOT logged, even at DEBUG level. This makes debugging failed user code difficult. Consider logging a truncated version at DEBUG. |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Exception types | Uses `ValueError` for missing python_code (line 66). Generic `Exception` catch for exec errors (line 127). No custom exception types. |
| Exception chaining | Line 129 uses bare `raise` (re-raise), which preserves the original traceback. Correct. |
| Error messages | Include component ID and error details (line 128). Good. |
| Graceful degradation | **NONE** -- any exception in user code crashes the component. No `die_on_error` flag. No REJECT flow. No partial results. This contrasts sharply with `PythonRowComponent` which catches per-row errors and continues. |
| No bare `except` | Except clause specifies `Exception` -- correct |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_process()` has return type `Dict[str, Any]`, parameter type `Optional[pd.DataFrame]` -- correct |
| `_get_context_dict()` | Return type `Dict[str, Any]` -- correct |
| Missing | No type hints on local variables (standard for Python). Acceptable. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-PDC-001 | **P2** | **`input_data.copy()` doubles memory**: Line 75 creates a full deep copy of the input DataFrame. For a 1GB DataFrame, this allocates an additional 1GB. The copy is necessary to prevent upstream mutation, but for read-only transformations (e.g., `df['new_col'] = df['old_col'] * 2`), a copy-on-write approach would be more efficient. Consider using `pd.option_context('mode.copy_on_write', True)` (pandas >= 2.0) or deferring the copy. |
| PERF-PDC-002 | **P2** | **HYBRID streaming mode produces incorrect results**: `BaseComponent._execute_streaming()` splits the DataFrame into chunks (default 100K rows) and calls `_process()` per chunk. User code that relies on the full DataFrame (aggregations, sorts, deduplication, window functions, groupby) will produce incorrect results. The component should either force BATCH mode or document that streaming is unsafe. |
| PERF-PDC-003 | **P3** | **`exec()` recompiles code on every call**: Each call to `_process()` (and each streaming chunk) recompiles the Python code string. For repeated invocations (streaming mode), pre-compiling with `compile(python_code, '<python_code>', 'exec')` and then `exec(compiled_code, namespace)` would avoid repeated parsing. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| DataFrame copy | `input_data.copy()` on line 75. Doubles memory. Necessary for isolation. |
| Memory threshold | Inherited from `BaseComponent`: `MEMORY_THRESHOLD_MB = 3072` (3GB). At this threshold, HYBRID switches to streaming, which is UNSAFE for this component. |
| Output column filtering | Line 112: `output_df = output_df[available_cols]` creates a view (no copy). Memory efficient. |
| Namespace cleanup | No explicit cleanup after `exec()`. The namespace dict and all objects created by user code persist until garbage collection. For long-running jobs with many iterations, this could accumulate memory. |

### 7.2 Streaming Mode Limitations

| Issue | Description |
|-------|-------------|
| Correctness | **CRITICAL**: HYBRID streaming splits the DataFrame and calls `_process()` per chunk. User code that assumes the full dataset (groupby, sort, dedup, rolling windows, joins within the same DataFrame) will produce WRONG RESULTS. |
| Stats accumulation | `_update_stats()` is called per `_process()` invocation, which correctly accumulates totals. |
| Namespace isolation | Each chunk gets a fresh namespace. User code that stores state across rows (e.g., `if 'counter' not in dir(): counter = 0`) will reset per chunk. |
| Recommendation | Override `_determine_execution_mode()` to always return `ExecutionMode.BATCH`, or override `_execute_streaming()` to concatenate chunks first. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `PythonDataFrameComponent` in v1 |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| V2 tests | **Yes** | `tests/v2/component/test_python_components.py` | V2-only tests exist but are **out of scope** for this v1 audit |

**Key finding**: The v1 engine has ZERO tests for this component. All 149 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic DataFrame transformation | P0 | `df['new'] = df['a'] + df['b']` on a simple DataFrame, verify new column exists with correct values |
| 2 | Empty input handling | P0 | Pass `None` and empty DataFrame, verify empty DataFrame returned with no error |
| 3 | Missing python_code | P0 | Config with no `python_code` key, verify `ValueError` raised with descriptive message |
| 4 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` in stats after execution |
| 5 | Python code runtime error | P0 | Code that raises `KeyError` (accessing nonexistent column), verify exception propagates with component ID in message |
| 6 | Syntax error in python_code | P0 | Malformed Python code, verify `SyntaxError` propagates cleanly |
| 7 | NaN handling | P0 | DataFrame with NaN values, verify user code can handle them (e.g., `df.fillna(0)`) |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Output columns filtering | P1 | Specify `output_columns=['a', 'b']` on DataFrame with `['a', 'b', 'c']`, verify only `a, b` in output |
| 9 | Output columns -- none match | P1 | Specify `output_columns=['x']` on DataFrame with `['a', 'b']`, verify behavior (currently returns full DF -- document or fix) |
| 10 | Context variable access | P1 | User code reads `context['my_var']`, verify correct value from ContextManager |
| 11 | GlobalMap write | P1 | User code calls `globalMap.put('key', 'value')`, verify value persists in global_map after execution |
| 12 | Python routines access | P1 | User code calls `routines.MyRoutine.my_method()`, verify correct return value |
| 13 | DataFrame reassignment | P1 | User code does `df = df[df['a'] > 0]` (reassignment, not in-place), verify filtered output |
| 14 | Row count changes | P1 | User code adds rows (`pd.concat`) or removes rows (`df.drop`), verify `NB_LINE_OK` reflects output count |
| 15 | Input data isolation | P1 | Verify original input DataFrame is NOT modified after component execution (`.copy()` works) |
| 16 | Empty string handling | P1 | DataFrame with empty strings `""`, verify user code can process them without confusion with NaN |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 17 | Large DataFrame (streaming boundary) | P2 | DataFrame near MEMORY_THRESHOLD_MB, verify BATCH mode produces correct results |
| 18 | User code deletes df | P2 | Code does `del df`, verify meaningful error message (currently crashes with NameError) |
| 19 | User code reassigns df to non-DataFrame | P2 | Code does `df = "hello"`, verify meaningful error message |
| 20 | Multiple namespace routines | P2 | Verify routines are accessible both as `routines.RoutineName` and directly as `RoutineName` |
| 21 | pd.cut / pd.merge / complex pandas ops | P2 | Verify complex pandas operations work correctly in the namespace |
| 22 | GlobalMap.clear() from user code | P2 | Document or prevent user code from wiping globalMap |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-PDC-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| ENG-PDC-001 | Engine | **No REJECT flow**: Unlike sibling `PythonRowComponent`, any exception in user code crashes the entire component. No error isolation, no partial results, no reject output. For a component executing arbitrary user code, this is a critical reliability gap. |
| TEST-PDC-001 | Testing | Zero v1 unit tests for this component. All 149 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-PDC-001 | Converter | No dedicated parser method -- uses generic fallthrough. `CODE` -> `python_code` key mismatch would fail if Talend XML existed. |
| CONV-PDC-002 | Converter | Not in converter dispatch (`converter.py`). No `elif` branch. Sibling `tJavaRow` has dedicated handling. |
| SEC-PDC-001 | Security | `exec()` with unrestricted `__builtins__` -- full system access available to user code. Remote code execution if python_code comes from untrusted source. |
| ENG-PDC-003 | Engine | Silent `output_columns` fallthrough: when no specified columns exist, full unfiltered DataFrame returned instead of error. Silent data integrity violation. |
| ENG-PDC-004 | Engine | No type validation on `namespace['df']` after `exec()`. User code can reassign `df` to non-DataFrame, causing cryptic `AttributeError`. |
| BUG-PDC-002 | Bug | Silent output_columns fallthrough returns full DataFrame when no specified columns match. Data integrity risk. |
| BUG-PDC-003 | Bug | No type check on `namespace['df']` after exec. Reassignment to non-DataFrame causes cryptic crash. |
| BUG-PDC-004 | Bug (Cross-Cutting) | `resolve_dict()` mangles `python_code` before execution. Skips `java_code`/`imports` but NOT `python_code`. Pattern 2 regex replaces `context.xxx` in user code. Affects all Python components. |
| BUG-PDC-005 | Bug | Routine names from `**python_routines` can shadow `df`/`pd`/`np`/`context`/`globalMap`. A routine named `df` destroys DataFrame access. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-PDC-003 | Converter | `tPythonDataFrame` not in Java expression marking skip list. Other params could be corrupted with `{{java}}` prefix. |
| ENG-PDC-005 | Engine | HYBRID streaming mode produces incorrect results for aggregation/sort/dedup user code. Component should force BATCH. |
| ENG-PDC-006 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap on error. |
| SEC-PDC-002 | Security | `globalMap` and `context` both expose live mutable state. `globalMap` is a live reference; `context` is a shallow copy that does NOT deep-copy mutable values. User code can corrupt both. |
| STD-PDC-001 | Standards | No dedicated `parse_python_dataframe()` converter method. Violates STANDARDS.md. |
| STD-PDC-002 | Standards | No `_validate_config()` method. Only inline check for empty `python_code`. |
| STD-PDC-003 | Standards | `validate_schema()` never called on output DataFrame. |
| PERF-PDC-001 | Performance | `input_data.copy()` doubles memory usage. Consider copy-on-write for pandas >= 2.0. |
| PERF-PDC-002 | Performance | HYBRID streaming mode is unsafe -- chunks produce incorrect results for whole-DataFrame operations. |
| BUG-PDC-006 | Bug | Empty input path does not call `_update_stats()`. Stats remain at initial zeros (technically correct but inconsistent with base class flow). |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| NAME-PDC-001 | Naming | `python_code` config key is internally consistent with siblings. No issue. |
| PERF-PDC-003 | Performance | `exec()` recompiles code on every call. Pre-compile with `compile()` for repeated invocations. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 1 bug (cross-cutting), 1 engine, 1 testing |
| P1 | 9 | 2 converter, 1 security, 2 engine, 4 bugs |
| P2 | 11 | 1 converter, 2 engine, 1 security, 3 standards, 2 performance, 1 bug |
| P3 | 2 | 1 naming, 1 performance |
| **Total** | **25** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-PDC-001): Change `value` to `stat_value` on `base_component.py` line 304, or remove the stale reference entirely. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Add error isolation / REJECT flow** (ENG-PDC-001): Wrap the `exec()` call in a try/except that captures the exception, stores the original input DataFrame as reject output with `errorCode='PYTHON_ERROR'` and `errorMessage=str(e)`, and returns `{'main': pd.DataFrame(), 'reject': reject_df}`. This matches sibling `PythonRowComponent`'s behavior. For DataFrame-level errors (as opposed to row-level), the entire input becomes the reject output. Example fix:
    ```python
    try:
        exec(python_code, namespace)
        output_df = namespace.get('df')
        if not isinstance(output_df, pd.DataFrame):
            raise TypeError(f"User code must leave 'df' as a DataFrame, got {type(output_df).__name__}")
    except Exception as e:
        logger.error(f"Component {self.id}: Error executing Python code: {e}")
        reject_df = input_data.copy()
        reject_df['errorCode'] = 'PYTHON_ERROR'
        reject_df['errorMessage'] = str(e)
        self._update_stats(rows_read=len(input_data), rows_ok=0, rows_reject=len(input_data))
        return {'main': pd.DataFrame(), 'reject': reject_df}
    ```

3. **Create unit test suite** (TEST-PDC-001): Implement at minimum the 7 P0 test cases listed in Section 8.2.

### Short-Term (Hardening)

4. **Fix output_columns fallthrough** (BUG-PDC-002 / ENG-PDC-003): When `output_columns` is specified and no columns match, raise `ValueError` instead of silently returning the full DataFrame. Or return an empty DataFrame to honor the filtering intent.

5. **Add type check after exec** (BUG-PDC-003 / ENG-PDC-004): After `exec()`, validate `isinstance(namespace.get('df'), pd.DataFrame)` and raise a clear `TypeError` if not.

6. **Restrict `__builtins__` in exec namespace** (SEC-PDC-001): Add `namespace['__builtins__'] = {'len': len, 'str': str, 'int': int, 'float': float, 'bool': bool, 'sum': sum, 'min': min, 'max': max, 'range': range, 'enumerate': enumerate, 'zip': zip, 'map': map, 'filter': filter, 'sorted': sorted, 'reversed': reversed, 'list': list, 'dict': dict, 'set': set, 'tuple': tuple, 'print': print, 'isinstance': isinstance, 'type': type, 'hasattr': hasattr, 'getattr': getattr}` to provide a curated set of builtins without `__import__`, `open`, `eval`, `exec`, `compile`, etc.

7. **Force BATCH mode** (ENG-PDC-005 / PERF-PDC-002): Override `_determine_execution_mode()` to always return `ExecutionMode.BATCH`:
    ```python
    def _determine_execution_mode(self) -> ExecutionMode:
        return ExecutionMode.BATCH
    ```

8. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-PDC-006): In the except block, call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`.

9. **Add converter dispatch branch** (CONV-PDC-001, CONV-PDC-002): Add dedicated `elif component_type in ['tPythonDataFrame', 'tPythonRow', 'tPython']:` in `converter.py` that extracts `CODE` -> `python_code` mapping (matching `tJavaRow`'s `CODE` -> `java_code` pattern).

### Long-Term (Optimization)

10. **Pre-compile user code** (PERF-PDC-003): Use `compiled = compile(python_code, f'<{self.id}_python_code>', 'exec')` once, then `exec(compiled, namespace)` for execution. This avoids recompilation if the component is called multiple times (e.g., in iteration loops).

11. **Consider copy-on-write** (PERF-PDC-001): For pandas >= 2.0, use `pd.option_context('mode.copy_on_write', True)` instead of explicit `.copy()` to defer copying until mutation occurs.

12. **Add code validation step**: Before `exec()`, call `compile(python_code, '<python_code>', 'exec')` to catch syntax errors early with a clear error message, before the namespace is set up.

13. **Add `_validate_config()` method** (STD-PDC-002): Validate that `python_code` is a non-empty string, `output_columns` is a list of strings (if present), and optionally that `python_code` compiles without syntax errors.

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py line 64 (type mapping only)
'tPythonDataFrame': 'PythonDataFrameComponent',

# component_parser.py lines 384-386 (fallthrough in _map_component_parameters)
# Default - return raw config for unmapped components
else:
    return config_raw
```

**Note**: There is no dedicated parameter mapping for `tPythonDataFrame`. The raw XML parameters are dumped directly into config. Since this is a custom component that does not appear in Talend XML, this is a non-issue in practice.

---

## Appendix B: Engine Class Structure

```
PythonDataFrameComponent (BaseComponent)
    Config keys:
        python_code: str          # Python code to execute (required)
        output_columns: List[str] # Columns to keep in output (optional)

    Methods:
        _process(input_data) -> Dict[str, Any]    # Main entry point (149 lines total)
        _get_context_dict() -> Dict[str, Any]      # Flatten context for namespace

    Inherited from BaseComponent:
        execute(input_data) -> Dict[str, Any]      # Lifecycle: resolve expressions, select mode, call _process, update stats
        _update_stats(rows_read, rows_ok, rows_reject)  # Update NB_LINE, NB_LINE_OK, NB_LINE_REJECT
        _update_global_map()                       # Push stats to globalMap (BUGGY -- see BUG-PDC-001)
        validate_schema(df, schema)                # NOT CALLED by this component
        get_python_routines()                       # Get routines from PythonRoutineManager
```

---

## Appendix C: Comparison with Sibling Python Components

| Feature | PythonDataFrameComponent | PythonRowComponent | PythonComponent |
|---------|--------------------------|--------------------|-----------------|
| Processing model | Full DataFrame (vectorized) | Row-by-row (`iterrows()`) | One-time (no data processing) |
| Input data required? | Yes (returns empty if None) | Yes (returns empty if None) | No (passes through input) |
| User code variable | `df` (DataFrame) | `input_row` + `output_row` (dicts) | N/A (just runs code) |
| REJECT flow | **NO** | **YES** (errorCode, errorMessage) | **NO** |
| `pd` in namespace | Yes | No | Yes |
| `np` in namespace | Yes | No | No |
| `print` in namespace | No | No | Yes |
| `datetime`/`os`/`sys` in namespace | No (but accessible via `__builtins__`) | No | Yes (explicitly imported) |
| `sum`/`min`/`max` in namespace | Yes | No | Yes |
| Output schema validation | No | Yes (`_validate_output_row()`) | No |
| DataFrame copy | Yes (`input_data.copy()`) | N/A (row dicts) | No (passes through) |
| Error handling | Re-raise (crash) | Per-row catch (continue) | Re-raise (crash) |

**Key inconsistency**: `PythonRowComponent` has REJECT flow and per-row error handling, while `PythonDataFrameComponent` and `PythonComponent` do not. The namespace contents also vary across siblings (some have `print`, `os`, `sys`; others don't). This creates a confusing developer experience.

---

## Appendix D: Edge Case Analysis

### Edge Case 1: Empty DataFrame input

| Aspect | Detail |
|--------|--------|
| **Expected** | Return empty DataFrame, NB_LINE=0 |
| **Actual** | Line 57: `input_data.empty` -> returns `{'main': pd.DataFrame()}`. Stats not updated (remain 0). |
| **Verdict** | CORRECT |

### Edge Case 2: NaN values in DataFrame

| Aspect | Detail |
|--------|--------|
| **Expected** | User code can handle NaN via pandas operations (`fillna`, `dropna`, etc.) |
| **Actual** | NaN values pass through to user code unmodified. `pd` and `np` are available for NaN handling. |
| **Verdict** | CORRECT (user responsibility) |

### Edge Case 3: Empty strings in DataFrame

| Aspect | Detail |
|--------|--------|
| **Expected** | Empty strings `""` are distinct from NaN and should not be confused |
| **Actual** | No automatic NaN-to-empty-string conversion (unlike `FileInputDelimited`'s `_post_process_dataframe()`). Empty strings pass through as-is. |
| **Verdict** | CORRECT |

### Edge Case 4: User code reassigns df

| Aspect | Detail |
|--------|--------|
| **Expected** | New DataFrame should be picked up from namespace |
| **Actual** | Line 105: `output_df = namespace['df']`. If user does `df = df[df['a'] > 0]`, the filtered DataFrame is used. Correct. |
| **Verdict** | CORRECT |

### Edge Case 5: User code deletes df

| Aspect | Detail |
|--------|--------|
| **Expected** | Clear error message |
| **Actual** | `namespace['df']` returns... actually `namespace.get('df')` is NOT used -- it's `namespace['df']` on line 105, which raises `KeyError: 'df'`. The except block on line 127 catches it and re-raises. Error message includes component ID. |
| **Verdict** | ACCEPTABLE (error propagates, but message could be clearer) |

### Edge Case 6: User code adds rows to df

| Aspect | Detail |
|--------|--------|
| **Expected** | Output should have more rows than input; NB_LINE_OK should reflect output count |
| **Actual** | `rows_ok=len(output_df)` on line 120. Correctly counts output rows regardless of input count. |
| **Verdict** | CORRECT |

### Edge Case 7: User code produces empty df

| Aspect | Detail |
|--------|--------|
| **Expected** | Empty DataFrame returned, NB_LINE_OK=0 |
| **Actual** | `output_df = namespace['df']` where df is empty. `len(output_df)` = 0. Stats: `rows_ok=0`. Correct. |
| **Verdict** | CORRECT |

### Edge Case 8: output_columns with duplicate column names

| Aspect | Detail |
|--------|--------|
| **Expected** | Deduplicate or handle gracefully |
| **Actual** | `available_cols = [col for col in output_columns if col in output_df.columns]` preserves duplicates. `output_df[available_cols]` with duplicates creates duplicate columns. Pandas behavior. |
| **Verdict** | GAP -- no deduplication of output_columns |

### Edge Case 9: HYBRID mode with groupby in user code

| Aspect | Detail |
|--------|--------|
| **Expected** | Correct aggregation over full dataset |
| **Actual** | HYBRID chunks DataFrame. Each chunk's `df.groupby().agg()` produces partial results. Final `pd.concat()` of partial aggregations is WRONG. |
| **Verdict** | **BUG** -- streaming mode produces incorrect results for aggregation-type user code |

### Edge Case 10: exec() security -- import os

| Aspect | Detail |
|--------|--------|
| **Expected** | Restricted (production) or unrestricted (trusted env) |
| **Actual** | `exec()` without `__builtins__` restriction. User code CAN do `import os; os.system('whoami')`. Full system access. |
| **Verdict** | **RISK** -- acceptable for trusted environments, dangerous otherwise |

---

## Appendix E: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `PythonDataFrameComponent`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-PDC-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| N/A | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `.get()` call. `get_component_stat()` on line 58 passes two args to single-arg `get()`. |
| N/A | **P2** | `base_component.py` | HYBRID streaming mode (`_execute_streaming`) is unsafe for components whose `_process()` expects the full DataFrame. Affects `PythonDataFrameComponent`, potentially others with aggregation logic. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix F: Detailed Code Analysis

### `_process()` (Lines 54-129)

The main processing method, line by line:

```
Lines 54-59: Entry guard
    - Signature: _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]
    - If input_data is None or empty, logs warning and returns {'main': pd.DataFrame()}
    - Statistics NOT updated in this early-return path (stats remain at initial zeros)
    - The warning message includes self.id for traceability

Lines 61-66: Config extraction
    - python_code = self.config.get('python_code', '')  -- defaults to empty string
    - output_columns = self.config.get('output_columns', None)  -- defaults to None (keep all)
    - If python_code is empty/falsy, raises ValueError with component ID
    - No validation on output_columns type (could be string, list, dict, etc.)

Lines 68-72: Preparation
    - python_routines = self.get_python_routines()  -- from BaseComponent, returns {} if no manager
    - context_dict = self._get_context_dict()  -- flattened context variables
    - Both calls are safe (return empty dict on None manager)

Lines 74-77: DataFrame copy and logging
    - df = input_data.copy()  -- DEEP COPY. This is the most expensive operation for large DataFrames.
    - The copy prevents mutation of the upstream component's output.
    - If upstream passes a view (e.g., from column selection), .copy() materializes it.
    - Memory impact: doubles the DataFrame's memory footprint.
    - Logs row count at INFO level.

Lines 79-99: Namespace construction
    - 'df': The copied DataFrame. User code modifies this.
    - 'pd': pandas module. Allows user code to use pd.concat(), pd.merge(), pd.cut(), etc.
    - 'np': numpy module. Allows user code to use np.where(), np.inf, np.nan, etc.
    - 'context': Flat dict of context variables. SHALLOW copy only (new dict, but mutable values are NOT deep-copied -- see SEC-PDC-002).
    - 'globalMap': LIVE REFERENCE to self.global_map. User can read AND write.
    - 'routines': Dict mapping routine names to routine objects.
    - **python_routines: Unpacked routines for direct access (e.g., StringRoutine.format_name).
    - Common builtins: len, str, int, float, bool, sum, min, max.
    - NOTABLY MISSING: print, open, range, enumerate, zip, map, filter, sorted, list, dict, set, tuple.
    - However, __builtins__ is NOT restricted, so ALL of these are accessible implicitly.

Line 102: Code execution
    - exec(python_code, namespace)
    - This is the core operation. The Python code string is compiled and executed.
    - The namespace dict serves as both globals and locals for the exec'd code.
    - Any exception propagates out of exec() to the except block on line 127.
    - Side effects: namespace may be modified (new variables, modified df, globalMap writes).

Lines 104-114: Output extraction and column filtering
    - output_df = namespace['df']  -- reads the (potentially modified) DataFrame from namespace
    - If user code did `df = df.groupby(...)`, namespace['df'] is the new DataFrame
    - If user code did `del df`, this raises KeyError
    - If user code did `df = None`, output_df is None and subsequent operations crash
    - output_columns filtering (lines 108-114):
        * Only applied when output_columns is truthy (not None, not empty list)
        * available_cols: intersection of requested columns with actual DataFrame columns
        * If available_cols is non-empty: filter to those columns only
        * If available_cols is empty: log WARNING but return FULL DataFrame (BUG-PDC-002)
        * No deduplication of column names in output_columns

Lines 116-121: Statistics update
    - rows_read = len(input_data)  -- original input count (before copy, before user code)
    - rows_ok = len(output_df)  -- output count (may differ from input)
    - rows_reject = 0  -- ALWAYS zero. No reject mechanism.
    - _update_stats() accumulates into self.stats (NB_LINE, NB_LINE_OK, NB_LINE_REJECT)

Lines 123-125: Logging and return
    - Logs output row count and column count at INFO level
    - Returns {'main': output_df}
    - No 'reject' key in result dict
    - No 'stats' key (added by BaseComponent.execute() after _process() returns)

Lines 127-129: Error handling
    - Catches all exceptions
    - Logs error with component ID and exception message
    - Re-raises the original exception (preserving traceback)
    - No error isolation, no partial results, no reject output
    - No globalMap error message storage
```

### `_get_context_dict()` (Lines 131-148)

Flattens the hierarchical context structure into a simple key-value dictionary:

```
Lines 131-148: Context flattening
    - If no context_manager, returns empty dict
    - context_all = self.context_manager.get_all()  -- returns all contexts
    - Two nesting levels handled:
      1. Nested: {Default: {home_location: {value: "US", type: "str"}}}
         -> context_dict['home_location'] = "US"  (extracts 'value' key)
      2. Simple: {home_location: "US"}
         -> context_dict['home_location'] = "US"  (uses as-is)
    - Note: Unlike PythonRowComponent and PythonComponent, this method does NOT
      have the `elif context_vars is not None:` guard for simple structure.
      PythonRowComponent line 146 checks `elif context_vars is not None:`.
      PythonDataFrameComponent line 146 checks `else:` (no None guard).
      This means if context_vars is None, it would be stored as context_dict[context_name] = None,
      while siblings would skip it. MINOR INCONSISTENCY.
```

### BaseComponent.execute() integration (base_component.py lines 188-234)

The lifecycle that wraps `_process()`:

```
1. Set status to RUNNING (line 192)
2. Record start_time (line 193)
3. If java_bridge exists, resolve {{java}} expressions in config (line 198)
4. If context_manager exists, resolve ${context.var} references in config (line 202)
5. Determine execution mode: BATCH/STREAMING/HYBRID (lines 205-208)
6. Execute:
   - STREAMING: split into chunks, call _process() per chunk, concat results (lines 261-278)
   - BATCH: call _process() directly (line 253)
7. Record EXECUTION_TIME stat (line 217)
8. Call _update_global_map() (line 218)  -- THIS IS WHERE BUG-PDC-001 CRASHES
9. Set status to SUCCESS (line 220)
10. Add stats to result dict (line 223)
11. Return result (line 225)
```

**Key observation**: Step 4 resolves `${context.var}` in ALL config values including `python_code`. This means if user code contains literal text like `"${context.something}"`, the context_manager will attempt to resolve it BEFORE the code is executed. This could corrupt Python code that contains dollar-sign syntax (e.g., f-strings, template strings, regex patterns). In practice, this is unlikely but theoretically possible.

---

## Appendix G: Implementation Fix Guides

### Fix Guide: BUG-PDC-001 -- `_update_global_map()` undefined variable

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

**Explanation**: `{value}` references an undefined variable (the for loop variable on line 301 is `stat_value`, not `value`). The `{stat_name}` reference would show only the last loop iteration value, which is misleading. Best fix is to remove both stale references and just log the three main stats.

**Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

---

### Fix Guide: GlobalMap.get() undefined default (Cross-Cutting)

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

**Impact**: Fixes ALL components and any code using `global_map.get()`. Also fixes `get_component_stat()` on line 58 which calls `self.get(key, default)` with two arguments. **Risk**: Very low (adds optional parameter with backward-compatible default).

---

### Fix Guide: ENG-PDC-001 -- Implementing REJECT flow

**File**: `src/v1/engine/components/transform/python_dataframe_component.py`

**Step 1**: Replace the try/except block (lines 79-129) with error-capturing logic:

```python
try:
    # Create execution namespace
    namespace = {
        'df': df,
        'pd': pd,
        'np': np,
        'context': context_dict,
        'globalMap': self.global_map,
        'routines': python_routines,
        # Add routines directly for easier access
        **python_routines,
        # Common functions
        'len': len,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'sum': sum,
        'min': min,
        'max': max,
    }

    # Execute user's Python code
    exec(python_code, namespace)

    # Get the modified DataFrame -- with type validation
    output_df = namespace.get('df')
    if not isinstance(output_df, pd.DataFrame):
        raise TypeError(
            f"User code must leave 'df' as a DataFrame, "
            f"got {type(output_df).__name__}"
        )

    # Filter columns if specified
    if output_columns:
        available_cols = [col for col in output_columns if col in output_df.columns]
        if available_cols:
            output_df = output_df[available_cols]
        else:
            raise ValueError(
                f"None of the specified output_columns {output_columns} "
                f"exist in DataFrame. Available columns: {list(output_df.columns)}"
            )

    # Update statistics
    self._update_stats(
        rows_read=len(input_data),
        rows_ok=len(output_df),
        rows_reject=0
    )

    logger.info(
        f"Component {self.id}: Processed DataFrame successfully: "
        f"{len(output_df)} rows, {len(output_df.columns)} columns"
    )

    return {'main': output_df}

except Exception as e:
    logger.error(f"Component {self.id}: Error executing Python code: {e}")

    # Build reject DataFrame from original input
    reject_df = input_data.copy()
    reject_df['errorCode'] = 'PYTHON_ERROR'
    reject_df['errorMessage'] = str(e)

    # Store error in globalMap
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))

    # Update statistics
    self._update_stats(
        rows_read=len(input_data),
        rows_ok=0,
        rows_reject=len(input_data)
    )

    # Check die_on_error config (default True for backward compat)
    die_on_error = self.config.get('die_on_error', True)
    if die_on_error:
        raise

    return {'main': pd.DataFrame(), 'reject': reject_df}
```

**Impact**: Adds REJECT flow matching sibling `PythonRowComponent`. Adds type validation on `namespace['df']`. Fixes `output_columns` fallthrough. Adds `die_on_error` support.

---

### Fix Guide: ENG-PDC-005 -- Force BATCH mode

**File**: `src/v1/engine/components/transform/python_dataframe_component.py`

**Add method** after line 20 (class definition):

```python
def _determine_execution_mode(self):
    """PythonDataFrame always uses BATCH mode.

    Streaming/HYBRID mode would chunk the DataFrame and call _process()
    per chunk, which is incorrect for user code that assumes the full
    DataFrame (groupby, sort, dedup, window functions, etc.).
    """
    from ...base_component import ExecutionMode
    return ExecutionMode.BATCH
```

**Impact**: Prevents HYBRID mode from silently producing incorrect results when user code performs whole-DataFrame operations. **Risk**: Low -- removes a mode that was never correct for this component.

---

### Fix Guide: SEC-PDC-001 -- Restrict __builtins__

**File**: `src/v1/engine/components/transform/python_dataframe_component.py`

**Modify the namespace construction** (lines 81-99):

```python
# Create execution namespace with restricted builtins
safe_builtins = {
    # Type constructors
    'len': len, 'str': str, 'int': int, 'float': float, 'bool': bool,
    'list': list, 'dict': dict, 'set': set, 'tuple': tuple, 'bytes': bytes,
    # Iteration helpers
    'range': range, 'enumerate': enumerate, 'zip': zip,
    'map': map, 'filter': filter, 'sorted': sorted, 'reversed': reversed,
    # Math
    'sum': sum, 'min': min, 'max': max, 'abs': abs, 'round': round,
    'pow': pow, 'divmod': divmod,
    # Introspection (needed for pandas operations)
    'isinstance': isinstance, 'issubclass': issubclass,
    'type': type, 'hasattr': hasattr, 'getattr': getattr, 'setattr': setattr,
    'callable': callable, 'id': id, 'hash': hash, 'repr': repr,
    # Other safe builtins
    'print': print, 'format': format, 'chr': chr, 'ord': ord,
    'any': any, 'all': all, 'iter': iter, 'next': next,
    'slice': slice, 'property': property, 'staticmethod': staticmethod,
    'classmethod': classmethod, 'super': super,
    # String/object
    'ValueError': ValueError, 'TypeError': TypeError,
    'KeyError': KeyError, 'IndexError': IndexError,
    'AttributeError': AttributeError, 'RuntimeError': RuntimeError,
    'StopIteration': StopIteration, 'Exception': Exception,
    'True': True, 'False': False, 'None': None,
}

namespace = {
    '__builtins__': safe_builtins,
    'df': df,
    'pd': pd,
    'np': np,
    'context': context_dict,
    'globalMap': self.global_map,
    'routines': python_routines,
    **python_routines,
}
```

**Impact**: Prevents user code from accessing `__import__`, `open`, `eval`, `exec`, `compile`, `globals`, `locals`, `vars`, `dir`, `input`, `breakpoint`, `exit`, `quit`. User code CAN still access pandas and numpy, which provide file I/O capabilities (e.g., `pd.read_csv('/etc/passwd')`). Full sandboxing would require restricting pandas/numpy, which is impractical. This fix addresses the most common attack vectors.

**Risk**: Medium -- some legitimate user code may break if it uses `import` statements. Mitigation: allow `import` for specific whitelisted modules, or make the restriction configurable via a `sandbox` config flag.

---

### Fix Guide: BUG-PDC-002 -- Fix output_columns fallthrough

**File**: `src/v1/engine/components/transform/python_dataframe_component.py`
**Lines**: 108-114

**Current code (buggy)**:
```python
if output_columns:
    # Keep only specified columns
    available_cols = [col for col in output_columns if col in output_df.columns]
    if available_cols:
        output_df = output_df[available_cols]
    else:
        logger.warning(f"Component {self.id}: None of the specified output_columns exist in DataFrame")
```

**Fix (Option A -- Raise error)**:
```python
if output_columns:
    # Keep only specified columns
    available_cols = [col for col in output_columns if col in output_df.columns]
    missing_cols = [col for col in output_columns if col not in output_df.columns]
    if missing_cols:
        logger.warning(
            f"Component {self.id}: output_columns not found in DataFrame: {missing_cols}. "
            f"Available: {list(output_df.columns)}"
        )
    if available_cols:
        output_df = output_df[available_cols]
    else:
        raise ValueError(
            f"Component {self.id}: None of the specified output_columns "
            f"{output_columns} exist in DataFrame. "
            f"Available columns: {list(output_df.columns)}"
        )
```

**Fix (Option B -- Return empty DataFrame)**:
```python
if output_columns:
    available_cols = [col for col in output_columns if col in output_df.columns]
    if available_cols:
        output_df = output_df[available_cols]
    else:
        logger.warning(
            f"Component {self.id}: None of the specified output_columns exist. "
            f"Requested: {output_columns}, Available: {list(output_df.columns)}. "
            f"Returning empty DataFrame."
        )
        output_df = pd.DataFrame(columns=output_columns)
```

**Recommendation**: Option A (raise error) is safer. Option B matches the "lenient" philosophy of returning empty data on failure.

---

### Fix Guide: BUG-PDC-003 -- Type check after exec

**File**: `src/v1/engine/components/transform/python_dataframe_component.py`
**Line**: 105

**Current code**:
```python
# Get the modified DataFrame
output_df = namespace['df']
```

**Fix**:
```python
# Get the modified DataFrame -- validate type
output_df = namespace.get('df')
if output_df is None:
    raise ValueError(
        f"Component {self.id}: 'df' variable is None after code execution. "
        f"User code must not delete or set df to None."
    )
if not isinstance(output_df, pd.DataFrame):
    raise TypeError(
        f"Component {self.id}: 'df' must remain a DataFrame after code execution, "
        f"but got {type(output_df).__name__}. "
        f"Ensure your code modifies df in-place or reassigns it to a new DataFrame."
    )
```

**Impact**: Converts cryptic `AttributeError: 'NoneType' object has no attribute 'columns'` into a clear, actionable error message with component ID and guidance.

---

## Appendix H: Context Variable Resolution Risk

### Problem

`BaseComponent.execute()` line 202 calls `self.config = self.context_manager.resolve_dict(self.config)`. This resolves `${context.var}` patterns in ALL config values, including `python_code`. If user-supplied Python code contains literal `${...}` patterns (e.g., in f-strings, regex patterns, shell command templates), they will be modified or cause errors.

### Example

```python
# User's python_code:
df['pattern'] = df['text'].str.extract(r'${prefix}(\d+)')
```

After context resolution, `${prefix}` would be replaced with the context variable value (or cause an error if `prefix` is not a context variable). The user intended it as a regex pattern, not a context reference.

### Risk Assessment

**Low** in practice. Most Python code uses `{...}` in f-strings (which requires `f"..."` prefix, not present in plain strings), and regex patterns rarely use `${...}` syntax. However, the risk is non-zero and should be documented.

### Mitigation Options

1. **Document the limitation**: Warn users that `${context.var}` in python_code will be resolved.
2. **Escape mechanism**: Support `$${...}` as an escape for literal `${...}`.
3. **Skip resolution for python_code**: Modify `BaseComponent.execute()` to skip context resolution for the `python_code` key specifically. The component already provides `context` in the namespace, so users can access context variables directly.

---

## Appendix I: Namespace Injection Risk Analysis

### Direct namespace pollution

The `**python_routines` unpacking on line 89 spreads routine names into the top-level namespace. If a routine is named `pd`, `np`, `df`, `context`, `globalMap`, `len`, `str`, etc., it would **shadow the built-in namespace variables**.

Example: If `python_routines = {'pd': SomePdRoutine, 'len': SomeLenRoutine}`, then:
- `namespace['pd']` would be `SomePdRoutine`, NOT `pandas`
- `namespace['len']` would be `SomeLenRoutine`, NOT the built-in `len`

The order of dict construction matters. Python dict literal `{..., **python_routines, 'len': len, ...}` would be overwritten by `'len': len` ONLY if `'len': len` comes AFTER `**python_routines`. Let's verify the order:

```python
namespace = {
    'df': df,           # line 82
    'pd': pd,           # line 83  <-- COULD be shadowed by **python_routines
    'np': np,           # line 84  <-- COULD be shadowed by **python_routines
    'context': context_dict,  # line 85
    'globalMap': self.global_map,  # line 86
    'routines': python_routines,   # line 87
    **python_routines,  # line 89  <-- UNPACKED HERE. Overwrites anything above if keys match.
    'len': len,         # line 92  <-- Overwrites **python_routines['len'] if it existed
    'str': str,         # line 93  <-- Overwrites **python_routines['str'] if it existed
    ...
}
```

**Conclusion**: Routines named `df`, `pd`, `np`, `context`, `globalMap`, or `routines` would shadow those critical variables. Routines named `len`, `str`, `int`, `float`, `bool`, `sum`, `min`, `max` would NOT shadow (they come after the unpack). However, routines with any other name that collides with user code variables would inject unexpected values.

### Risk Assessment

**Medium**. Routine names are typically descriptive (e.g., `StringRoutine`, `DateRoutine`) and unlikely to collide with `pd`, `np`, or `df`. But the architecture allows it, and there is no validation or warning.

### Mitigation

Move `**python_routines` AFTER all explicit namespace entries, or remove it entirely and require users to access routines via the `routines` dict:

```python
# Before (current):
namespace = {
    'pd': pd,
    **python_routines,  # could shadow pd
    'len': len,
}

# After (safe):
namespace = {
    'pd': pd,
    'len': len,
}
# Add routines last, with collision check
for name, routine in python_routines.items():
    if name not in namespace:
        namespace[name] = routine
    else:
        logger.warning(
            f"Component {self.id}: Routine '{name}' would shadow built-in "
            f"namespace variable. Access it via routines['{name}'] instead."
        )
```

---

## Appendix J: Comparison with tJavaRow Converter Handling

The sibling Java component `tJavaRow` has a dedicated converter path that `tPythonDataFrame` lacks. This appendix documents the gap.

### tJavaRow converter handling

1. **Dedicated `elif` in `converter.py`** (line 375):
   ```python
   elif component_type == 'tJavaRow':
       component = self.component_parser.parse_java_row(node, component)
   ```

2. **Dedicated `_map_component_parameters` case** (lines 317-330):
   ```python
   elif component_type == 'tJavaRow':
       code = config_raw.get('CODE', '')
       code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
       imports = config_raw.get('IMPORT', '')
       imports = imports.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
       return {
           'java_code': code,
           'imports': imports
       }
   ```

3. **Dedicated `parse_java_row()` method** (component_parser.py line 913):
   - Builds output_schema from FLOW metadata
   - Maps Python types back to Java type names
   - Constructs a proper component config dict

### What tPythonDataFrame should have (but lacks)

```python
# In converter.py _parse_component():
elif component_type in ['tPythonDataFrame', 'tPythonRow', 'tPython']:
    # Python components use CODE parameter like Java components
    pass  # Falls through to generic path which handles CODE via _map_component_parameters

# In component_parser.py _map_component_parameters():
elif component_type == 'tPythonDataFrame':
    code = config_raw.get('CODE', '')
    code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
    return {
        'python_code': code,
        'output_columns': config_raw.get('OUTPUT_COLUMNS', None)
    }
```

### Why this matters

Currently, if someone adds a `tPythonDataFrame` node to Talend XML (via a custom component definition), the converter would:
1. Extract the CODE parameter into `config_raw['CODE']`
2. Fall through to `return config_raw` (line 385)
3. Store `config['CODE'] = 'user python code'`
4. The engine would read `self.config.get('python_code', '')` and get `''`
5. The engine would raise `ValueError: 'python_code' is required`

This is a **complete failure** of the converter-to-engine pipeline for this component type.

---

## Appendix K: Java Expression Marking Skip List Gap

### Current skip list (component_parser.py line 462)

```python
if component_name not in ['tMap', 'tJavaRow', 'tJava']:
```

### What should be in the skip list

```python
if component_name not in ['tMap', 'tJavaRow', 'tJava', 'tPythonRow', 'tPython', 'tPythonDataFrame']:
```

### Why this matters

The Java expression marking logic (lines 466-469) scans all non-CODE/IMPORT string values and marks them with `{{java}}` if they look like Java expressions. For Python components, this is incorrect because:

1. Python expressions use different syntax than Java
2. Python components don't have a Java bridge to resolve `{{java}}` markers
3. The markers would corrupt config values, potentially breaking the component

### Current mitigation

The `CODE` field is in `skip_fields` (line 464), so the Python code itself is NOT marked. Other fields (e.g., any custom parameters) would be subject to marking. Since `tPythonDataFrame` currently only uses `python_code` and `output_columns`, and `output_columns` is unlikely to look like a Java expression, the practical risk is low. However, the skip list should be updated for defensive correctness.

---

## Appendix L: `_get_context_dict()` Inconsistency

### Comparison across Python components

| Component | `_get_context_dict()` line | None guard | Behavior |
|-----------|--------------------------|------------|----------|
| `PythonDataFrameComponent` | 131-148 | **NO** (`else:` on line 146) | If `context_vars` is `None`, stores `context_dict[context_name] = None` |
| `PythonRowComponent` | 132-149 | **YES** (`elif context_vars is not None:` on line 146) | If `context_vars` is `None`, skips the entry |
| `PythonComponent` | 116-133 | **YES** (`elif context_vars is not None:` on line 130) | If `context_vars` is `None`, skips the entry |

### Impact

If a context group has a `None` value (e.g., `context_all = {'Default': {...}, 'empty_group': None}`), `PythonDataFrameComponent` would include `context_dict['empty_group'] = None`, while siblings would skip it. This is a minor inconsistency that could cause unexpected `None` values in user code's `context` dict.

### Fix

Change line 146 of `python_dataframe_component.py` from:
```python
else:
    # Simple flat structure: {home_location: "US"}
    context_dict[context_name] = context_vars
```
to:
```python
elif context_vars is not None:
    # Simple flat structure: {home_location: "US"}
    context_dict[context_name] = context_vars
```

---

## Appendix M: Complete Code Listing with Annotations

```python
"""                                                          # Line 1
PythonDataFrame component - Execute Python code on entire DataFrame
                                                             # Line 3
This component provides vectorized DataFrame operations:
- Executes custom Python code on the full DataFrame          # Line 5
- Allows transformations that would be tedious with standard operations
- Access to pandas operations, context, globalMap, and Python routines
- Useful for bulk transformations and aggregations           # Line 8
"""

from typing import Any, Dict, Optional                       # Line 11
import pandas as pd                                          # NOTE: Module-level import
import numpy as np                                           # NOTE: Module-level import
import logging
from ...base_component import BaseComponent                  # Line 15

logger = logging.getLogger(__name__)                         # Line 17


class PythonDataFrameComponent(BaseComponent):               # Line 20
    """
    Execute Python code on entire DataFrame (vectorized operations)
    ...docstring omitted for brevity...
    """

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Execute Python code on DataFrame"""                # Line 55

        if input_data is None or input_data.empty:            # GUARD: Early return
            logger.warning(f"Component {self.id}: No input data")
            return {'main': pd.DataFrame()}                   # NOTE: No _update_stats() call
                                                              # Line 60
        # Get configuration
        python_code = self.config.get('python_code', '')      # KEY: Must match converter output
        output_columns = self.config.get('output_columns', None)

        if not python_code:                                   # VALIDATION: Only check
            raise ValueError(f"Component {self.id}: 'python_code' is required")

        # Get Python routines
        python_routines = self.get_python_routines()           # From BaseComponent

        # Get context as flat dict
        context_dict = self._get_context_dict()                # Line 72

        # Copy input DataFrame to avoid modifying original
        df = input_data.copy()                                 # PERF: Doubles memory

        logger.info(f"Component {self.id}: Processing DataFrame with {len(df)} rows using Python code")

        try:
            # Create execution namespace
            namespace = {                                      # Line 81
                'df': df,                                      # DataFrame to modify
                'pd': pd,                                      # pandas module
                'np': np,                                      # numpy module
                'context': context_dict,                       # READ-ONLY copy
                'globalMap': self.global_map,                   # LIVE reference (RISK)
                'routines': python_routines,                   # Routines dict
                # Add routines directly for easier access
                **python_routines,                             # RISK: Could shadow pd/np/df
                # Common functions
                'len': len,                                    # Overrides any routine named 'len'
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'sum': sum,
                'min': min,
                'max': max,
            }                                                  # NOTE: __builtins__ NOT restricted

            # Execute user's Python code
            exec(python_code, namespace)                       # SEC: Arbitrary code execution

            # Get the modified DataFrame
            output_df = namespace['df']                        # BUG: No type check

            # Filter columns if specified
            if output_columns:                                 # Line 108
                # Keep only specified columns
                available_cols = [col for col in output_columns if col in output_df.columns]
                if available_cols:
                    output_df = output_df[available_cols]
                else:
                    logger.warning(f"Component {self.id}: None of the specified output_columns exist in DataFrame")
                    # BUG: Falls through -- returns FULL unfiltered DataFrame

            # Update statistics
            self._update_stats(                                # Line 117
                rows_read=len(input_data),                     # Original input count
                rows_ok=len(output_df),                        # Output count (may differ)
                rows_reject=0                                  # ALWAYS 0 -- no reject
            )

            logger.info(f"Component {self.id}: Processed DataFrame successfully: {len(output_df)} rows, {len(output_df.columns)} columns")

            return {'main': output_df}                         # No 'reject' key

        except Exception as e:                                 # Line 127
            logger.error(f"Component {self.id}: Error executing Python code: {e}")
            raise                                              # Re-raise -- no error isolation

    def _get_context_dict(self) -> Dict[str, Any]:             # Line 131
        """Get context variables as a flat dictionary"""
        context_dict = {}
        if self.context_manager:
            context_all = self.context_manager.get_all()
            # Flatten context structure
            for context_name, context_vars in context_all.items():
                if isinstance(context_vars, dict):
                    # Nested structure
                    for var_name, var_info in context_vars.items():
                        if isinstance(var_info, dict) and 'value' in var_info:
                            context_dict[var_name] = var_info['value']
                        else:
                            context_dict[var_name] = var_info
                else:                                          # BUG: Missing None guard
                    # Simple flat structure: {home_location: "US"}
                    context_dict[context_name] = context_vars   # Could store None
        return context_dict                                    # Line 148
```

---

## Appendix N: Recommended V1 JSON Config Examples

Since `tPythonDataFrame` is a custom component used only in hand-crafted V1 JSON configs, the following examples document correct usage patterns.

### Example 1: Basic column transformation

```json
{
    "id": "tPythonDataFrame_1",
    "type": "PythonDataFrameComponent",
    "config": {
        "python_code": "df['full_name'] = df['first_name'] + ' ' + df['last_name']\ndf['name_length'] = df['full_name'].str.len()"
    },
    "inputs": ["row1"],
    "outputs": ["row2"],
    "schema": {
        "input": [
            {"name": "first_name", "type": "str"},
            {"name": "last_name", "type": "str"}
        ],
        "output": [
            {"name": "first_name", "type": "str"},
            {"name": "last_name", "type": "str"},
            {"name": "full_name", "type": "str"},
            {"name": "name_length", "type": "int"}
        ]
    }
}
```

### Example 2: With output column filtering

```json
{
    "id": "tPythonDataFrame_2",
    "type": "PythonDataFrameComponent",
    "config": {
        "python_code": "df['total'] = df['qty'] * df['price']\ndf['tax'] = df['total'] * 0.08",
        "output_columns": ["total", "tax"]
    },
    "inputs": ["row1"],
    "outputs": ["row2"]
}
```

### Example 3: Using context variables

```json
{
    "id": "tPythonDataFrame_3",
    "type": "PythonDataFrameComponent",
    "config": {
        "python_code": "threshold = context.get('min_threshold', 0)\ndf = df[df['value'] > threshold]"
    },
    "inputs": ["row1"],
    "outputs": ["row2"]
}
```

### Example 4: Using globalMap

```json
{
    "id": "tPythonDataFrame_4",
    "type": "PythonDataFrameComponent",
    "config": {
        "python_code": "globalMap.put('total_records', len(df))\ndf['batch_id'] = globalMap.get('batch_id') if globalMap.contains('batch_id') else 'unknown'"
    },
    "inputs": ["row1"],
    "outputs": ["row2"]
}
```

### Example 5: Using numpy and pandas together

```json
{
    "id": "tPythonDataFrame_5",
    "type": "PythonDataFrameComponent",
    "config": {
        "python_code": "df['age_group'] = pd.cut(df['age'], bins=[0, 18, 65, np.inf], labels=['child', 'adult', 'senior'])\ndf['log_income'] = np.log1p(df['income'])"
    },
    "inputs": ["row1"],
    "outputs": ["row2"]
}
```

### Anti-pattern: Avoid streaming-incompatible operations

The following code works in BATCH mode but would produce WRONG results if HYBRID mode triggered streaming:

```json
{
    "id": "tPythonDataFrame_BAD",
    "type": "PythonDataFrameComponent",
    "config": {
        "python_code": "df = df.drop_duplicates(subset=['id'])\ndf['rank'] = df['score'].rank()",
        "execution_mode": "batch"
    },
    "inputs": ["row1"],
    "outputs": ["row2"]
}
```

**Note**: Explicitly set `"execution_mode": "batch"` to prevent HYBRID from chunking the data. Until ENG-PDC-005 is fixed (force BATCH mode), this is the recommended workaround.

---

## Appendix O: GlobalMap.get() Bug Impact on PythonDataFrameComponent

### The bug

`GlobalMap.get()` (global_map.py line 28) references undefined variable `default`:

```python
def get(self, key: str) -> Optional[Any]:
    return self._map.get(key, default)  # 'default' is undefined!
```

### Impact on PythonDataFrameComponent

User code in `python_code` that calls `globalMap.get('some_key')` will crash with `NameError: name 'default' is not defined`. This is especially impactful because:

1. The component exposes `globalMap` as a live reference in the namespace
2. User code is expected to call `globalMap.get()` for reading shared variables
3. The error appears to come from USER code (inside exec), making it hard to diagnose

### Workaround for users

Until the bug is fixed, users should use:
```python
# Instead of:
value = globalMap.get('my_key')  # CRASHES

# Use:
value = globalMap._map.get('my_key', None)  # Works but accesses private attribute

# Or check with contains first:
if globalMap.contains('my_key'):
    value = globalMap._map['my_key']
else:
    value = None
```

### Note on `globalMap.put()`

`globalMap.put()` (line 21-23) works correctly. Only `get()` is broken. So writing to globalMap from user code is safe.

---

## Appendix P: Execution Flow Diagram

```
ETLEngine.execute()
    |
    v
ETLEngine._execute_component(comp_id)
    |
    v
BaseComponent.execute(input_data)
    |
    +-- 1. _resolve_java_expressions()     [if java_bridge]
    +-- 2. context_manager.resolve_dict()   [if context_manager]
    |       WARNING: Resolves ${...} in python_code string!
    +-- 3. _auto_select_mode(input_data)    [if HYBRID]
    |       Returns BATCH or STREAMING based on memory usage
    |
    +-- [BATCH path] -------------------------+
    |   _execute_batch(input_data)            |
    |       |                                 |
    |       v                                 |
    |   PythonDataFrameComponent._process()   |
    |       |                                 |
    |       +-- Guard: None/empty input       |
    |       +-- Extract config                |
    |       +-- Get routines + context        |
    |       +-- df = input_data.copy()        |
    |       +-- Build namespace               |
    |       +-- exec(python_code, namespace)  |
    |       +-- output_df = namespace['df']   |
    |       +-- Filter output_columns         |
    |       +-- _update_stats()               |
    |       +-- return {'main': output_df}    |
    |                                         |
    +-- [STREAMING path] --------------------+
    |   _execute_streaming(input_data)       |
    |       |                                |
    |       v                                |
    |   _create_chunks(input_data)           |
    |       |                                |
    |       v                                |
    |   for chunk in chunks:                 |
    |       _process(chunk)  <-- WRONG!      |
    |       User code sees partial data      |
    |       Aggregations produce bad results |
    |   pd.concat(results)                   |
    |                                        |
    +----------------------------------------+
    |
    +-- 4. _update_global_map()  <-- CRASHES (BUG-PDC-001)
    +-- 5. Set status SUCCESS
    +-- 6. Return result with stats
```

---

## Appendix Q: Risk Matrix

| Risk | Likelihood | Impact | Severity | Mitigation |
|------|-----------|--------|----------|------------|
| `_update_global_map()` crash (BUG-PDC-001) | **Certain** (100%) | **High** -- crashes every execution | **P0** | Fix undefined variable `value` -> `stat_value` |
| `GlobalMap.get()` crash (cross-cutting) | **High** (any `get()` call) | **High** -- crashes user code | **P0** | Add `default` parameter to `get()` signature |
| No REJECT flow (ENG-PDC-001) | **Medium** (depends on user code quality) | **High** -- entire component fails on any error | **P0** | Add try/except with reject DataFrame |
| `exec()` security (SEC-PDC-001) | **Low** (trusted environments) | **Critical** -- full system access | **P1** | Restrict `__builtins__` |
| Silent output_columns fallthrough (BUG-PDC-002) | **Medium** (wrong column names in config) | **High** -- silent data corruption | **P1** | Raise error when no columns match |
| HYBRID streaming (ENG-PDC-005) | **Low** (only for >3GB DataFrames) | **High** -- silently wrong results | **P2** | Force BATCH mode |
| Namespace collision from routines | **Very Low** (unlikely routine names) | **Medium** -- shadowed variables | **P3** | Add collision check before unpacking |
| Context resolution in python_code | **Very Low** (rare `${...}` in Python) | **Medium** -- corrupted code | **P3** | Document limitation |
| Zero tests (TEST-PDC-001) | **Certain** (100%) | **High** -- no verification of any behavior | **P0** | Create test suite |
