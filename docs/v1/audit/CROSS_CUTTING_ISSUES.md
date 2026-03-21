# V1 Engine -- Cross-Cutting Issues Report

## Executive Summary

This document catalogs **engine-level bugs and systemic issues** that affect all or most components in the v1 ETL engine. These are not individual component defects; they are problems in the shared infrastructure that every component relies on: `base_component.py`, `engine.py`, `global_map.py`, `context_manager.py`, `trigger_manager.py`, `base_iterate_component.py`, the converter pipeline, and the exception hierarchy.

**Issue counts by severity:**

| Severity | Count | Description |
|----------|-------|-------------|
| P0 -- Critical | 7 | Engine crashes, data corruption, broken imports |
| P1 -- High | 9 | Incorrect behavior, masked errors, security holes |
| P2 -- Medium | 8 | Missing implementations, incomplete features |
| P3 -- Low | 6 | Code quality, minor inconsistencies |

**Overall engine health: NOT PRODUCTION-READY.** The engine cannot even be imported without error due to broken import chains (Section 1.4). Even if imports are fixed, every component execution will crash in `_update_global_map()` (Section 1.1), and the `GlobalMap.get()` method throws a `NameError` on every call (Section 1.2). These three issues alone block all execution.

**What blocks production:**
1. The engine module fails to import (`engine.py:40` -- broken aggregate imports).
2. Every component execution crashes at stats update (`base_component.py:304`).
3. Every `GlobalMap.get()` call raises `NameError` (`global_map.py:28`).
4. Context variable type conversion is broken for 10 of 16 mapped types (`context_manager.py:168-186`).
5. The trigger system's `!` replacement corrupts `!=` operators (`trigger_manager.py:228`).
6. Streaming mode silently drops reject data for every component (`base_component.py:270-271`).
7. The `replace_in_config` function uses literal `[i]` instead of `[{i}]`, breaking Java expression resolution in arrays (`base_component.py:174`).

---

## 1. Critical Engine Bugs (P0)

These bugs prevent the engine from functioning at all. Every one of them must be fixed before any job can execute successfully.

---

### 1.1 `_update_global_map()` Crash on Every Component Execution

**File:** `src/v1/engine/base_component.py`, line 304

**Description:**

The `_update_global_map()` method is called at the end of every successful and every failed component execution (lines 218 and 231). The method iterates over `self.stats` correctly on lines 301-302, but line 304 references two undefined variables `stat_name` and `value` inside an f-string:

```python
def _update_global_map(self) -> None:
    """Update global map with component statistics"""
    if self.global_map:
        for stat_name, stat_value in self.stats.items():
            self.global_map.put_component_stat(self.id, stat_name, stat_value)
        # Log the statistics for debugging
        logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} {stat_name}: {value}")
```

Line 304 references `{stat_name}` (which is the loop variable from line 301 -- still in scope as the last iteration value) and `{value}` (which is **never defined anywhere** in this method). The variable `stat_value` is defined in line 301, but `value` is not.

**Impact:**

- **Every single component execution crashes** with a `NameError: name 'value' is not defined`.
- This happens on BOTH the success path (line 218) and the error path (line 231).
- On the error path, the original exception is replaced by this `NameError`, meaning the real error message is permanently lost.
- On the success path, the component's result is never returned, making ALL downstream components receive no data.
- Because `_update_global_map()` is called inside `BaseComponent.execute()`, and `BaseIterateComponent.execute()` also calls it (line 72 of `base_iterate_component.py`), iterate components are equally affected.

**Root cause:** Typo -- `value` should be `stat_value`, and the f-string is likely leftover debug code that was not cleaned up.

**Recommended fix:**

Either fix the variable name:
```python
logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']}")
```
Or remove the trailing `{stat_name}: {value}` entirely since the preceding stats are already logged.

**Effort estimate:** 5 minutes.

---

### 1.2 `GlobalMap.get()` Broken Signature -- `NameError` on Every Call

**File:** `src/v1/engine/global_map.py`, lines 26-28

**Description:**

The `get()` method references a variable `default` that is not defined in its signature:

```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

The parameter `default` does not appear in the method signature `(self, key: str)`. This means **every call** to `GlobalMap.get()` raises `NameError: name 'default' is not defined`.

**Impact:**

- `GlobalMap.get()` is called from:
  - `get_component_stat()` at line 58 (fallback path): `self.get(key, default)` -- this also passes 2 arguments to a 1-argument method, which would raise `TypeError` even if the `NameError` were fixed.
  - `TriggerManager._evaluate_condition()` at lines 205 and 214.
  - `Die._resolve_global_map_variables()` at line 202 of `die.py`: `self.global_map.get(key, 0)` -- also passes 2 arguments.
  - `Warn._resolve_message_variables()` at line 181 of `warn.py`: `self.global_map.get(key, 0)` -- also passes 2 arguments.
  - Any component that accesses the global map for variable resolution.
- Every RunIf trigger evaluation fails, so conditional trigger flows never fire.
- Every tDie/tWarn message resolution that references globalMap variables fails.

**Root cause:** The `default` parameter was omitted from the method signature. The method body was written assuming a signature like `def get(self, key: str, default: Any = None)`.

**Recommended fix:**

```python
def get(self, key: str, default: Any = None) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

**Effort estimate:** 2 minutes.

---

### 1.3 `replace_in_config` Literal `[i]` Bug -- Java Expressions in Arrays Never Resolve

**File:** `src/v1/engine/base_component.py`, line 174

**Description:**

Inside `_resolve_java_expressions()`, the `scan_config` function (line 115) correctly builds paths for list items using f-string interpolation:

```python
# scan_config (line 115) -- CORRECT
scan_config(item, f"{path}[{i}]")
```

But the `replace_in_config` function (line 174) uses a literal string `[i]` instead of f-string interpolation `[{i}]`:

```python
# replace_in_config (line 174) -- WRONG
current_path = f"{path}[i]"    # Always produces "path[i]", never "path[0]", "path[1]", etc.
```

**Impact:**

- The `scan_config` function builds keys like `"mappings[0]"`, `"mappings[1]"`, etc.
- The `replace_in_config` function looks for keys like `"mappings[i]"` -- which never match.
- **No Java expression inside a list/array config value is ever replaced with its resolved value.**
- This affects tMap components with multiple mappings, tAggregateRow with multiple operations, tFilterRows with multiple conditions, and any other component whose config contains arrays with Java expressions.
- The component silently proceeds with the unresolved `{{java}}...` marker string as the actual value, which then causes incorrect behavior downstream (e.g., a filename might remain as the literal string `"{{java}}context.getOutputDir() + \"/output.csv\""` instead of the resolved path).

**Root cause:** Missing `{` and `}` around `i` in the f-string on line 174.

**Recommended fix:**

```python
current_path = f"{path}[{i}]"
```

**Effort estimate:** 2 minutes.

---

### 1.4 Broken Imports in `engine.py` -- Engine Module Cannot Be Loaded

**File:** `src/v1/engine/engine.py`, line 40

**Description:**

Line 40 imports from the `aggregate` package:

```python
from .components.aggregate import AggregateSortedRow, Denormalize, Normalize, Replicate
```

But the `aggregate/__init__.py` only exports `AggregateRow` and `UniqueRow`:

```python
# aggregate/__init__.py
from .aggregate_row import AggregateRow
from .unique_row import UniqueRow

__all__ = ["AggregateRow", "UniqueRow"]
```

The classes `AggregateSortedRow`, `Denormalize`, `Normalize`, and `Replicate` actually live in the `transform` package (confirmed by class definitions in `transform/aggregate_sorted_row.py`, `transform/denormalize.py`, `transform/normalize.py`, `transform/replicate.py`) and are already exported by `transform/__init__.py`.

**Impact:**

- **The entire engine module fails to import.** Any `from src.v1.engine import ETLEngine` or `from src.v1.engine.engine import ETLEngine` raises `ImportError`.
- This means no job can be created or executed.
- This is a total blocker.

**Root cause:** The four classes were placed in the `transform` directory but the import statement in `engine.py` was written (or moved) to import from `aggregate`.

**Recommended fix:**

Change line 40 from:
```python
from .components.aggregate import AggregateSortedRow, Denormalize, Normalize, Replicate
```
To:
```python
from .components.transform import AggregateSortedRow, Denormalize, Normalize, Replicate
```

Or remove line 40 entirely since these are already imported from `.components.transform` on lines 27-34 (though the existing transform imports would need a line added for any missing ones -- verification: `AggregateSortedRow` is on transform `__init__.py` line 3, `Denormalize` line 4, `Normalize` line 15, `Replicate` line 20 -- all present).

**Effort estimate:** 2 minutes.

---

### 1.5 `FileInputXML` Import Case Mismatch -- `FileInputXML` vs `FileInputXml`

**File:** `src/v1/engine/components/file/__init__.py`, line 10

**Description:**

The `file/__init__.py` imports:

```python
from .file_input_xml import FileInputXml   # lowercase 'ml'
```

But the actual class defined in `file_input_xml.py` line 212 is:

```python
class FileInputXML(BaseComponent):   # uppercase 'ML'
```

Meanwhile, `engine.py` line 21 imports:

```python
from .components.file import FileInputDelimited, FileOutputDelimited, FileInputPositional, FileInputXML
```

This attempts to import `FileInputXML` (uppercase) from the `file` package, but the package's `__init__.py` only exports `FileInputXml` (lowercase 'ml').

**Impact:**

- `engine.py` line 21 raises `ImportError: cannot import name 'FileInputXML' from 'src.v1.engine.components.file'`.
- This compounds with issue 1.4 to make the engine completely unimportable.
- Even if issue 1.4 were fixed, this would still prevent import.

**Root cause:** Inconsistent casing between `__init__.py` re-export name and the actual class name.

**Recommended fix:**

In `file/__init__.py` line 10, change:
```python
from .file_input_xml import FileInputXml
```
To:
```python
from .file_input_xml import FileInputXML
```

Also update `__all__` on line 33 from `'FileInputXml'` to `'FileInputXML'`.

**Effort estimate:** 2 minutes.

---

### 1.6 `ContextManager._convert_type()` Broken for 10 of 16 Mapped Types

**File:** `src/v1/engine/context_manager.py`, lines 162-194

**Description:**

The `_convert_type()` method uses a `type_mapping` dictionary where converters are stored as either:
- Lambda functions (e.g., `lambda v: str(v).lower() in ('true', '1', 'yes')`) -- these work.
- The actual built-in function reference `str` (lines 184-185) -- these work.
- **String literals** like `'str'`, `'int'`, `'float'`, `'Decimal'` -- these are **NOT callable**.

The code at line 191 then calls `converter(value)`:

```python
converter = type_mapping.get(value_type, str)   # may return the string 'str'
try:
    return converter(value)   # 'str'('hello') -> TypeError: 'str' object is not callable
```

**Broken type mappings (10 out of 16):**

| Key | Value | What happens when called |
|-----|-------|--------------------------|
| `'id_String'` | `'str'` (string literal) | `TypeError: 'str' object is not callable` |
| `'id_Integer'` | `'int'` (string literal) | `TypeError` |
| `'id_Long'` | `'int'` (string literal) | `TypeError` |
| `'id_Float'` | `'float'` (string literal) | `TypeError` |
| `'id_Double'` | `'float'` (string literal) | `TypeError` |
| `'id_Date'` | `'str'` (string literal) | `TypeError` |
| `'id_BigDecimal'` | `'Decimal'` (string literal) | `TypeError` |
| `'str'` | `'str'` (string literal) | `TypeError` |
| `'int'` | `'int'` (string literal) | `TypeError` |
| `'float'` | `'float'` (string literal) | `TypeError` |

**Working type mappings (6 out of 16):**

| Key | Value | Why it works |
|-----|-------|-------------|
| `'id_Boolean'` | `lambda v: ...` | Lambda is callable |
| `'bool'` | `lambda v: ...` | Lambda is callable |
| `'Decimal'` | `'Decimal'` (string literal) | **Also broken** -- `'Decimal'` is not callable |
| `'datetime'` | `str` (built-in) | `str` is callable |
| `'object'` | `str` (built-in) | `str` is callable |

Correction: only 4 mappings actually work (`id_Boolean`, `bool`, `datetime`, `object`). The `'Decimal'` mapping is also broken, making it 12 of 16 broken.

**Impact:**

- Every context variable with a type annotation (which is most of them, since the converter sets types from Talend XML) fails to convert.
- The `except (ValueError, TypeError)` at line 192 catches the error and returns the unconverted value, so the failure is **silent** -- only a warning is logged.
- This means all `id_Integer` context variables remain as strings, all `id_Float` context variables remain as strings, etc.
- Downstream comparisons like `context.threshold > 100` fail because `"100" > 100` raises `TypeError` in Python 3.
- Type-sensitive operations (arithmetic, date parsing, boolean checks) produce wrong results silently.

**Root cause:** The developer used string literals instead of actual function references for the type converters.

**Recommended fix:**

```python
type_mapping = {
    'id_String': str,
    'id_Integer': int,
    'id_Long': int,
    'id_Float': float,
    'id_Double': float,
    'id_Boolean': lambda v: str(v).lower() in ('true', '1', 'yes'),
    'id_Date': str,
    'id_BigDecimal': Decimal,
    'str': str,
    'int': int,
    'float': float,
    'bool': lambda v: str(v).lower() in ('true', '1', 'yes'),
    'Decimal': Decimal,
    'datetime': str,
    'object': str
}
```

**Effort estimate:** 10 minutes (change values + add test).

---

### 1.7 `BaseComponent.__repr__()` Missing Opening Parenthesis

**File:** `src/v1/engine/base_component.py`, line 382

**Description:**

```python
def __repr__(self) -> str:
    return f"{self.component_type} id={self.id} status={self.status.value})"
```

The f-string has a closing `)` but no opening `(`. The output is syntactically unbalanced: `Map id=tMap_1 status=success)`.

**Impact:**

- Cosmetic bug but it makes debugging output confusing.
- Any logging or exception message that calls `repr(component)` produces malformed output.

**Recommended fix:**

```python
return f"{self.component_type}(id={self.id} status={self.status.value})"
```

**Effort estimate:** 1 minute.

---

## 2. Engine Error Handling Flow

This section traces the full lifecycle of errors through the engine, from component failure to job status determination.

---

### 2.1 What Happens When a Component Fails

Here is the complete execution trace when a component's `_process()` method raises an exception:

**Step 1: `_process()` raises**

Any component's `_process()` raises an exception (e.g., `FileNotFoundError`, `ValueError`, `ComponentExecutionError`).

**Step 2: `BaseComponent.execute()` catches (line 227)**

```python
except Exception as e:
    self.status = ComponentStatus.ERROR
    self.error_message = str(e)
    self.stats['EXECUTION_TIME'] = time.time() - start_time
    self._update_global_map()    # <-- THIS CRASHES (see Section 1.1)
    logger.error(f"Component {self.id} execution failed: {e}")
    raise
```

**Step 3: `_update_global_map()` crashes with `NameError`** (Section 1.1)

The `_update_global_map()` method at line 304 references undefined variable `value`, raising `NameError`. This replaces the original exception.

**Step 4: The `NameError` propagates up**

The `raise` on line 234 never executes because `_update_global_map()` raised first. The `NameError` propagates to `_execute_component()` in `engine.py`.

**Step 5: `_execute_component()` catches (line 600)**

```python
except Exception as e:
    logger.error(f"Component {comp_id} failed: {str(e)}")
    if hasattr(e, 'exit_code'):
        raise e
    self.trigger_manager.set_component_status(comp_id, 'error')
    self.failed_components.add(comp_id)
    self.executed_components.add(comp_id)
    return 'error'
```

The `NameError` does not have an `exit_code` attribute, so it falls through to the generic error handling. The component is marked as failed, but the **original error message is lost** -- the log says `NameError: name 'value' is not defined` instead of the actual component error.

**Step 6: Trigger evaluation may also fail**

After `_execute_component()` returns `'error'`, the engine calls `trigger_manager.get_triggered_components(comp_id, 'error')`. If any `OnSubjobError` or `RunIf` triggers exist, the trigger evaluation calls `GlobalMap.get()`, which crashes with `NameError` (Section 1.2). This second crash is **unhandled** and propagates up to `execute()`, potentially terminating the entire job even though the engine intended to continue.

**Net result:** Every component failure causes a cascade of two additional bugs, and the original error is never reported.

---

### 2.2 Job Status Determination

**File:** `src/v1/engine/engine.py`, lines 501-511

The job status is determined at line 505:

```python
'status': 'success' if not self.failed_components else 'failed',
```

**Issues:**

1. **Status value inconsistency:** The success path returns `'success'` and the failure path returns `'failed'`, but the exception path (line 530) returns `'error'`. The consumer of this return value must handle three different strings for two states. Talend uses `0` (success) and non-zero integers (failure).

2. **Stalled execution is reported as success:** If the execution loop breaks due to a stall (line 460 -- `Execution stalled. Unexecuted components`), the engine falls through to the stats calculation at line 501. If no components failed (they were just never executed), `self.failed_components` is empty, and the job is reported as `'success'` even though multiple components never ran.

3. **Partial execution masquerade:** If 10 out of 15 components execute successfully and 5 are stalled (never started), the status is `'success'` with `components_executed: 10`. The caller must compare `components_executed` against expected total to detect this -- the status alone is misleading.

**Recommended fix:**

- Add a `'stalled'` or `'partial'` status when unexecuted components remain.
- Use consistent status values across all return paths.
- Include `components_total` in the return dict so callers can verify completeness.

---

### 2.3 Exit Code Propagation

**File:** `src/v1/engine/components/control/die.py`, line 174; `src/v1/engine/engine.py`, lines 604-607

**Description:**

The `Die` component sets `error.exit_code = exit_code` (die.py line 174) and the engine checks for it at engine.py line 605:

```python
if hasattr(e, 'exit_code'):
    raise e
```

This re-raise propagates to `execute()` which catches it at line 520 and returns a dict with `'status': 'error'`. The exit code is **never included in the return value** and **never used to set `sys.exit()`**.

In the `__main__` block of `engine.py` (lines 860-888), the process always exits with code 0 regardless of job outcome:

```python
stats = run_job(args.job_config, context_overrides)
print(json.dumps(stats, indent=2))
# No sys.exit(stats.get('exit_code', 0)) or similar
```

**Impact:**

- `tDie` sets an exit code but no caller ever reads it.
- The process always exits 0 (success) even when the job failed.
- External orchestrators (cron, Airflow, CI/CD) that depend on exit codes to detect failures will always see success.
- The `JOB_EXIT_CODE` value stored in GlobalMap (die.py line 158) is also never read by the engine.

**Recommended fix:**

In the `__main__` block, add:
```python
if stats.get('status') != 'success':
    sys.exit(stats.get('exit_code', 1))
```

Also include `exit_code` in the return dict from `execute()` when available.

**Effort estimate:** 10 minutes.

---

### 2.4 `die_on_error` Consistency Matrix

The `die_on_error` config parameter controls whether a component should abort the job on error or silently continue. In Talend, most components default to `true`. The following matrix shows the state of `die_on_error` handling across the engine and each category of components:

**Engine-Level Handling:**

The engine (`engine.py:600-620`) does NOT check `die_on_error`. When a component raises an exception, the engine always catches it and either:
- Re-raises (if `exit_code` attribute exists -- only tDie).
- Marks as failed and continues.

This means the engine has **implicit `die_on_error=false` behavior for all components** -- it always continues. The only way a component can abort the job is if it raises an exception with an `exit_code` attribute (tDie pattern), which is a non-standard mechanism.

**Component-Level Implementation:**

Components that **do** implement `die_on_error` (verified by grep):

| Component Category | Components with `die_on_error` | Implementation Correct | Default |
|-------------------|-------------------------------|----------------------|---------|
| File Input | `FileInputDelimited`, `FileInputExcel`, `FileInputPositional`, `FileInputFullRow`, `FileInputXML`, `FileInputRaw`, `FileInputJSON` | Yes | `True` |
| File Output | `FileOutputDelimited`, `FileOutputPositional`, `FileOutputExcel` | Yes -- check config and either raise or continue | `True` |
| Transform | `Map`, `Normalize`, `AggregateSortedRow`, `Replicate`, `ExtractDelimitedFields`, `ExtractJSONFields`, `ExtractPositionalFields`, `ExtractXMLField`, `SwiftBlockFormatter`, `SwiftTransformer`, `Join` | Yes | `True` |
| Control | `SendMailComponent` | Yes | `True` |
| Control | `Die` | Yes (always terminates) | N/A |
| Control | `SleepComponent` | Yes | `True` |

Components that **lack** `die_on_error` (verified by grep):

| Component Category | Components without `die_on_error` |
|-------------------|----------------------------------|
| Transform | `FilterRows`, `FilterColumns`, `SortRow`, `LogRow`, `RowGenerator`, `Denormalize`, `Unite`, `PivotToColumnsDelimited`, `UnpivotRow`, `SchemaComplianceCheck`, `XMLMap` |
| Aggregate | `AggregateRow`, `UniqueRow` |
| Context | `ContextLoad` |
| Python | `PythonComponent`, `PythonRowComponent`, `PythonDataFrameComponent` |
| Java | `JavaComponent`, `JavaRowComponent` |
| File Operations | `SetGlobalVar`, `FileExist`, `FileCopy`, `FileDelete`, `FileTouch`, `FileArchive`, `FileUnarchive`, `FileProperties`, `FileRowCount`, `FixedFlowInput` |
| Control | `Warn` |

**Key findings:**

1. Many components now implement `die_on_error`, including all File Input components, File Output components, and a significant number of Transform components. However, a large set of components still lack it.
2. The converter does NOT extract `die_on_error` from Talend XML for all component types, so components that do implement it may not always receive the setting from converted jobs.
3. The engine does not have a unified `die_on_error` enforcement mechanism. Each component must implement it independently, leading to inconsistency.
4. There is no way for the engine to know a component's `die_on_error` setting because it is buried in the component's `config` dict and not surfaced as a component attribute.
5. Components without `die_on_error` -- including `FilterRows`, `SortRow`, `AggregateRow`, `UniqueRow`, all Python/Java components, and most file-operation utilities -- will raise on error unconditionally with no way to suppress errors at the job level.

**Recommended fix:**

Add `die_on_error` as a first-class attribute on `BaseComponent`, defaulting to `True`. Have the engine check this attribute after catching a component exception, and either re-raise or continue accordingly. Remove the ad-hoc `die_on_error` checks from individual components.

**Effort estimate:** 2-4 hours.

---

## 3. Trigger System Issues

The trigger system (`trigger_manager.py`) manages the control flow between subjobs. It evaluates conditions and determines which components should execute next based on success/failure of preceding components.

---

### 3.1 No `((Boolean)...)` Regex -- Only `((Integer)...)` Is Handled

**File:** `src/v1/engine/trigger_manager.py`, lines 200-208

**Description:**

The `_evaluate_condition()` method has a regex for `((Integer)globalMap.get("key"))`:

```python
pattern = r'\(\(Integer\)globalMap\.get\("([^"]+)"\)\)'
```

But Talend RunIf conditions frequently use other cast types:

- `((Boolean)globalMap.get("tFileExist_1_EXISTS"))` -- e.g., "run if file exists"
- `((String)globalMap.get("tFileInputDelimited_1_ERROR"))` -- e.g., "run if error message is set"
- `((Long)globalMap.get("tFileInputDelimited_1_NB_LINE"))` -- e.g., "run if rows > 0"

None of these are matched by the `((Integer)...)` regex. They pass through unmodified, which means `((Boolean)globalMap.get("tFileExist_1_EXISTS"))` gets to `eval()` as-is, causing a `SyntaxError` or `NameError` because `Boolean` is not defined in Python.

**Impact:**

- Any RunIf trigger that uses a cast type other than `Integer` silently fails.
- The `except` clause at line 238 catches the error and returns `False`, meaning the trigger does NOT fire.
- This causes entire subjobs to be silently skipped -- a very hard-to-diagnose production issue.

**Recommended fix:**

Replace the single-type regex with a generic cast pattern:

```python
pattern = r'\(\((\w+)\)globalMap\.get\("([^"]+)"\)\)'
```

Then handle the cast type appropriately (Integer -> int conversion, Boolean -> bool, String -> str, etc.).

**Effort estimate:** 30 minutes.

---

### 3.2 `!` Replacement Corrupts `!=` Operator

**File:** `src/v1/engine/trigger_manager.py`, line 228

**Description:**

The Java-to-Python operator conversion does replacements in sequence:

```python
python_condition = python_condition.replace('&&', ' and ')
python_condition = python_condition.replace('||', ' or ')
python_condition = python_condition.replace('!', ' not ')           # Line 228
python_condition = python_condition.replace('null', ' None')
python_condition = python_condition.replace('== None', ' is None')
python_condition = python_condition.replace('!= None', ' is not None')  # Line 231
```

The problem is that line 228 replaces ALL `!` characters with ` not `. This transforms:
- `!=` into ` not =` -- which is a syntax error.
- `!= None` into ` not = None` -- line 231 then tries to replace `!= None` but it no longer exists.

**Examples of corruption:**

| Input Java condition | After `!` replacement | Result |
|---------------------|----------------------|--------|
| `x != 0` | `x  not = 0` | `SyntaxError` |
| `x != null` | `x  not =  None` | `SyntaxError` |
| `!flag` | ` not flag` | Correct (accidental) |
| `x != y && !z` | `x  not = y and  not z` | `SyntaxError` |

**Impact:**

- Every RunIf condition containing `!=` fails to evaluate.
- The `except` clause returns `False`, silently preventing the trigger from firing.
- Since `!=` is one of the most common operators in Talend conditions (e.g., `globalMap.get("ERROR") != null`), this affects a large percentage of RunIf triggers.

**Root cause:** The replacements should be done in order of decreasing length, or using regex with word boundaries. `!=` should be replaced before `!`.

**Recommended fix:**

```python
# Replace multi-character operators BEFORE single-character operators
python_condition = python_condition.replace('!=', ' != ')   # preserve !=
python_condition = python_condition.replace('&&', ' and ')
python_condition = python_condition.replace('||', ' or ')
# Only replace standalone ! (not part of !=)
import re
python_condition = re.sub(r'!(?!=)', ' not ', python_condition)
python_condition = python_condition.replace('null', 'None')
python_condition = python_condition.replace('== None', 'is None')
python_condition = python_condition.replace('!= None', 'is not None')
```

**Effort estimate:** 15 minutes.

---

### 3.3 RunIf Uses `eval()` Without Sandboxing

**File:** `src/v1/engine/trigger_manager.py`, line 234

**Description:**

```python
result = eval(python_condition)
```

The `eval()` call executes arbitrary Python code with full access to the Python runtime. The condition string originates from the Talend XML file, which is processed by the converter. While the converter does some transformation, the final string passed to `eval()` could contain:

- `__import__('os').system('rm -rf /')` -- arbitrary command execution
- `open('/etc/passwd').read()` -- file access
- `globals()` -- runtime introspection

**Impact:**

- If an attacker can modify the Talend XML input files, they can execute arbitrary code on the server.
- Even without malicious intent, a poorly-formed condition expression could have unintended side effects (e.g., calling a function that modifies state).
- This is a security vulnerability in any environment where the XML input files are not fully trusted.

**Recommended fix:**

Use `ast.literal_eval()` where possible, or build a simple expression evaluator that only supports comparison operators, logical operators, and literal values. Example:

```python
# Restricted evaluation with only allowed names
safe_globals = {"__builtins__": {}, "None": None, "True": True, "False": False}
result = eval(python_condition, safe_globals, {})
```

**Effort estimate:** 1-2 hours.

---

### 3.4 Trigger Firing Correctness

**File:** `src/v1/engine/trigger_manager.py`, lines 102-182

**Description:**

The `get_triggered_components()` method has several correctness issues:

**Issue A: OnSubjobOk fires prematurely**

At lines 121-125, for `ON_SUBJOB_OK` and `ON_SUBJOB_ERROR` triggers, the code checks if the completed component is in the same subjob as `from_component`:

```python
from_subjob = self.component_to_subjob.get(trigger.from_component)
if from_subjob != subjob_id:
    continue
```

But then at line 148, it checks the full subjob status:

```python
if subjob_id:
    subjob_status = self.get_subjob_status(subjob_id)
    if subjob_status == 'success':
        should_trigger = True
```

The problem is that `get_triggered_components()` is called after EACH component completes (engine.py line 484), so when the first component in a 3-component subjob succeeds, `get_subjob_status()` returns `'success'` only if ALL components are already `'success'`. This should be correct, BUT:

The trigger manager's `set_component_status()` is only called for components that have been executed. Components that haven't executed yet have no status entry, so `self.component_status.get(comp, 'pending')` returns `'pending'`. The `all(status == 'success' for status in statuses)` check at line 97 returns `False` for pending components, which is correct.

However, if a subjob has only ONE component (common for tPrejob, tPostjob, standalone tWarn), then the trigger fires correctly after that component completes. This is the common case and works.

**Issue B: Source component triggering side effects**

At lines 170-180, when a trigger fires, the code also triggers "source components" (components with no inputs) in the target subjob. This is intended to start the entire target subjob. However:

```python
source_comps = self.subjob_source_components[to_subjob_id]
for source_comp in source_comps:
    if source_comp != trigger.to_component and source_comp not in self.triggered_components:
        triggered.append(source_comp)
```

This adds ALL source components in the target subjob, which may include components that should NOT execute (e.g., a tRowGenerator in the same subjob that is not connected to the trigger target). In Talend, only the directly-connected target component and its downstream flow are executed.

**Issue C: `triggered_components` set prevents re-triggering**

At line 132, components that have been triggered are tracked and skipped:

```python
if trigger.to_component in self.triggered_components:
    continue
```

This set is never cleared between subjob executions (only `reset()` clears it, and `reset()` is not called during normal execution). If a component should be triggered multiple times (e.g., in a loop or from multiple error handlers), it will only fire once.

The iterate component handler in `engine.py` (lines 708-711) does clear individual components from `triggered_components`, but only for components within the iteration. Triggers that fire at the job level (e.g., OnSubjobOk from subjob A to subjob B) are permanently recorded.

**Impact:**

- Issue B: Incorrect components may execute in triggered subjobs.
- Issue C: Duplicate trigger targets are silently ignored, which may skip necessary executions.

**Effort estimate:** 4-8 hours for full trigger system review and correction.

---

## 4. Streaming Mode Issues

The streaming execution mode (`base_component.py` lines 255-278) processes data in chunks to handle large datasets that exceed memory. Several design issues affect correctness when streaming is enabled.

---

### 4.1 `_execute_streaming` Drops Reject Data

**File:** `src/v1/engine/base_component.py`, lines 255-278

**Description:**

The streaming execution path processes chunks and collects results:

```python
def _execute_streaming(self, input_data: Optional[Iterator]) -> Dict[str, Any]:
    # ...
    results = []
    for chunk in chunks:
        chunk_result = self._process(chunk)
        if chunk_result.get('main') is not None:
            results.append(chunk_result['main'])

    if results:
        combined = pd.concat(results, ignore_index=True)
        return {'main': combined}
    else:
        return {'main': pd.DataFrame()}
```

Line 271 only collects `chunk_result['main']`. The `reject` key, which may contain rows that failed validation or filtering, is **completely ignored**. After processing all chunks, only `{'main': combined}` is returned -- no `reject` key at all.

**Impact:**

- Every component that produces reject output (tMap, tFilterRows, tUniqueRow, tSchemaComplianceCheck, etc.) will silently lose all rejected rows when running in streaming mode.
- Reject flows connected to downstream components (e.g., tFileOutputDelimited writing rejects to an error file) will receive an empty DataFrame or no data at all.
- This is a **silent data loss** bug -- there is no error or warning.

**Affected components:** All components that return a `reject` key in their `_process()` result dictionary.

**Recommended fix:**

```python
results = []
rejects = []
for chunk in chunks:
    chunk_result = self._process(chunk)
    if chunk_result.get('main') is not None:
        results.append(chunk_result['main'])
    if chunk_result.get('reject') is not None:
        rejects.append(chunk_result['reject'])

combined_main = pd.concat(results, ignore_index=True) if results else pd.DataFrame()
combined_reject = pd.concat(rejects, ignore_index=True) if rejects else None

result = {'main': combined_main}
if combined_reject is not None:
    result['reject'] = combined_reject
return result
```

**Effort estimate:** 30 minutes.

---

### 4.2 HYBRID Mode Breaks Stateful Components

**File:** `src/v1/engine/base_component.py`, lines 89-98, 236-249

**Description:**

The HYBRID execution mode (`ExecutionMode.HYBRID`) auto-selects between batch and streaming based on data size:

```python
def _auto_select_mode(self, input_data: Any) -> ExecutionMode:
    if isinstance(input_data, pd.DataFrame):
        memory_usage_mb = input_data.memory_usage(deep=True).sum() / (1024 * 1024)
        if memory_usage_mb > self.MEMORY_THRESHOLD_MB:
            return ExecutionMode.STREAMING
    return ExecutionMode.BATCH
```

The threshold is 3072 MB (3 GB). When data exceeds this, the component switches to streaming mode, which calls `_process()` multiple times with different chunks.

**Problem:** Stateful components (those that accumulate state across rows) produce incorrect results when `_process()` is called multiple times:

- **tAggregateRow:** Computes GROUP BY aggregates. Each chunk produces partial aggregates that are then concatenated -- the final result has duplicate group keys with partial sums/counts/averages.
- **tSortRow:** Each chunk is sorted independently, but the final `pd.concat()` just stacks them. The overall result is NOT globally sorted.
- **tUniqueRow:** Deduplication is per-chunk. A duplicate that spans two chunks will not be detected.
- **tDenormalize/tNormalize:** Grouping operations that require seeing all data.
- **tPivotToColumnsDelimited:** Pivot requires all values for a given key.
- **tAggregateSortedRow:** Assumes input is globally sorted; chunk boundaries break this assumption.

**Impact:**

- Any job processing more than 3 GB of data through any of these components will produce **silently wrong results**.
- Because HYBRID is the default mode (line 91: `'hybrid'`), this affects all jobs unless they explicitly set `execution_mode: "batch"` in every component config.

**Recommended fix:**

Option A (simple): Change the default execution mode to `"batch"` instead of `"hybrid"`.

Option B (correct): Add a class attribute `supports_streaming = False` to `BaseComponent` (defaulting to `False`), override it to `True` only in components that are genuinely stateless (e.g., tMap, tFilterRows), and have `_auto_select_mode()` check this attribute.

**Effort estimate:** Option A: 2 minutes. Option B: 2 hours.

---

### 4.3 Streaming + Sort = Wrong Order

**File:** `src/v1/engine/base_component.py`, line 275

**Description:**

As noted in 4.2, when `tSortRow` processes chunks, each chunk is independently sorted. The streaming combiner at line 275:

```python
combined = pd.concat(results, ignore_index=True)
```

Simply stacks the sorted chunks. For example, sorting 1M rows ascending by `amount` with chunk_size=100K produces 10 sorted segments that are concatenated:

```
Chunk 1: [1, 5, 12, 20, ...]  (sorted within chunk)
Chunk 2: [3, 7, 15, 22, ...]  (sorted within chunk)
...
Combined: [1, 5, 12, 20, ..., 3, 7, 15, 22, ...]  (NOT globally sorted)
```

**Impact:**

- Any downstream component relying on sort order (e.g., tAggregateSortedRow, merge-join operations, windowed calculations) will produce wrong results.
- A tFileOutputDelimited writing the "sorted" data will write an incorrectly ordered file.
- This only manifests with data > 3 GB (the HYBRID threshold), making it very hard to catch in testing with small datasets.

**Recommended fix:** `SortRow` should set `supports_streaming = False` (see Section 4.2 Option B), or the streaming combiner should perform a merge-sort on the sorted chunks.

**Effort estimate:** 1-4 hours depending on approach.

---

### 4.4 Streaming + Pivot = Wrong Results

**File:** `src/v1/engine/base_component.py`, line 275

**Description:**

`tPivotToColumnsDelimited` transforms row data into columnar format by grouping on a key column. When run in streaming mode, each chunk is pivoted independently. If rows with the same key span multiple chunks, the pivot produces partial/duplicate rows for that key.

**Example:**

Input:
```
Key  | Category | Value
A    | X        | 1
A    | Y        | 2
B    | X        | 3
```

Correct pivot (batch): `A -> X=1, Y=2 | B -> X=3`

With chunks of 2 rows:
- Chunk 1 (rows 1-2): `A -> X=1, Y=2` (correct for A)
- Chunk 2 (row 3): `B -> X=3`
- Combined: correct (by luck)

But if chunk boundary falls differently:
- Chunk 1 (rows 1,3): `A -> X=1 | B -> X=3` (incomplete A)
- Chunk 2 (row 2): `A -> Y=2` (second partial A)
- Combined: TWO rows for A, each with only one value.

**Impact:**

- Wrong pivoted output when data exceeds 3 GB.
- Downstream consumers receive duplicated/partial pivot rows.

**Recommended fix:** Same as Section 4.2 -- mark PivotToColumnsDelimited as `supports_streaming = False`.

**Effort estimate:** 5 minutes (attribute change) once the framework from 4.2 is in place.

---

### 4.5 Streaming Stats Accumulation Bug

**File:** `src/v1/engine/base_component.py`, lines 266-278

**Description:**

In streaming mode, `_process()` is called multiple times (once per chunk). Each call may update `self.stats` via `_update_stats()`. However, the base `execute()` method calls `_update_global_map()` only once after all chunks are processed (line 218). The per-chunk calls to `_process()` accumulate stats correctly in `self.stats` (since `_update_stats` uses `+=` operators).

However, some components reset stats inside `_process()` instead of accumulating:

```python
# Example pattern seen in some components:
self.stats['NB_LINE'] = len(df)  # Assignment, not accumulation
```

When a component uses assignment (`=`) instead of accumulation (`+=`), each chunk overwrites the previous stats, and only the last chunk's stats are reported. This underreports total rows processed.

**Impact:**

- Components that use `self.stats['NB_LINE'] = len(input_data)` inside `_process()` will report only the last chunk's count in streaming mode.
- GlobalMap statistics used by RunIf conditions (e.g., "run if NB_LINE > 1000") may have wrong values.

**Recommended fix:**

- Establish a convention: components should always use `self._update_stats(rows, ok, reject)` (which uses `+=`) instead of direct assignment.
- Audit all components for direct `self.stats[...] = ...` assignment patterns.

**Effort estimate:** 2-4 hours (audit + fix all components).

---

## 5. Context & Variable Resolution Issues

The `ContextManager` (`context_manager.py`) handles loading, storing, and resolving context variables throughout the engine. Several design issues cause incorrect behavior.

---

### 5.1 `validate_schema` Inverted Nullable Logic

**File:** `src/v1/engine/base_component.py`, lines 349-352

**Description:**

```python
if pandas_type in ['int64', 'float64']:
    df[col_name] = pd.to_numeric(df[col_name], errors='coerce')
    if pandas_type == 'int64' and col_def.get('nullable', True):
        df[col_name] = df[col_name].fillna(0).astype('int64')
```

When `nullable` is `True` (the default), the code fills NaN with 0 and converts to int64. This is **inverted logic**:

- If a column IS nullable (`nullable=True`), NaN values should be **preserved** (using `pd.Int64Dtype()` nullable integer type).
- If a column is NOT nullable (`nullable=False`), then NaN values should be filled with a default (like 0) or should raise an error.

The current code does the opposite: it replaces NaN with 0 when the column is nullable, and leaves NaN as-is (keeping it as float64 since standard int64 cannot hold NaN) when the column is not nullable.

**Impact:**

- Nullable integer columns silently replace NULL values with 0.
- Non-nullable integer columns silently remain as float64 with NaN values.
- This corrupts data for any schema with integer columns.

**Recommended fix:**

```python
if pandas_type == 'int64':
    if col_def.get('nullable', True):
        # Nullable column: use pandas nullable integer type
        df[col_name] = df[col_name].astype('Int64')  # capital I = nullable
    else:
        # Non-nullable: fill NaN and convert
        df[col_name] = df[col_name].fillna(0).astype('int64')
```

**Effort estimate:** 15 minutes.

---

### 5.2 `self.config` Mutation -- Non-Reentrant

**File:** `src/v1/engine/base_component.py`, line 202; `src/v1/engine/base_iterate_component.py`, line 61

**Description:**

In `BaseComponent.execute()` at line 202:

```python
if self.context_manager:
    self.config = self.context_manager.resolve_dict(self.config)
```

This replaces `self.config` with the resolved version. `resolve_dict()` returns a NEW dictionary (it creates `resolved = {}` at line 147 of `context_manager.py`), so the original config is lost.

Similarly, `BaseIterateComponent.execute()` at line 61:

```python
if self.context_manager:
    self.config = self.context_manager.resolve_dict(self.config)
```

**Impact:**

- **First execution works correctly.** Context variables like `${context.input_dir}` are replaced with their values.
- **Second execution (iterate loop) breaks.** When a component is re-executed in an iterate loop (engine.py lines 676-683), `self.config` no longer contains `${context.input_dir}` -- it contains the already-resolved value from the first iteration. If the context variable has changed between iterations (which iterate components do -- they update globalMap variables), the new value is NOT picked up.
- **Non-reentrant:** Any component that is executed more than once (explicitly or via iterate loops) uses stale resolved config after the first execution.

**Recommended fix:**

Store the original config separately and always resolve from the original:

```python
# In __init__:
self._original_config = config  # preserve original

# In execute():
if self.context_manager:
    self.config = self.context_manager.resolve_dict(self._original_config)
```

**Effort estimate:** 15 minutes.

---

### 5.3 `resolve_dict` Does Not Recurse into Dicts-in-Lists

**File:** `src/v1/engine/context_manager.py`, line 157

**Description:**

The `resolve_dict()` method handles three types of values:
- `str` -> calls `resolve_string()` (line 153)
- `dict` -> recursively calls `resolve_dict()` (line 155)
- `list` -> calls `resolve_string()` on each element, but **only if the element is a string** (line 157):

```python
elif isinstance(value, list):
    resolved[key] = [self.resolve_string(v) if isinstance(v, str) else v for v in value]
```

If a list element is a **dict**, it is passed through unchanged -- `resolve_dict()` is NOT called on it. If a list element is itself a **list**, it is also passed through unchanged.

**Impact:**

- Component configs with structures like `mappings: [{source: "${context.col}", target: "out"}]` will not have `${context.col}` resolved.
- This affects tMap (which has `mappings` as a list of dicts), tAggregateRow (which has `operations` as a list of dicts), tFilterRows (which has `conditions` as a list of dicts), and many other components.
- This is a **very common pattern** in converted Talend jobs.

**Recommended fix:**

```python
elif isinstance(value, list):
    resolved_list = []
    for v in value:
        if isinstance(v, str):
            resolved_list.append(self.resolve_string(v))
        elif isinstance(v, dict):
            resolved_list.append(self.resolve_dict(v))
        elif isinstance(v, list):
            # Could recurse further, but at minimum handle one level
            resolved_list.append(v)
        else:
            resolved_list.append(v)
    resolved[key] = resolved_list
```

**Effort estimate:** 15 minutes.

---

### 5.4 `resolve_dict` Corrupts `python_code` (Not in Skip List)

**File:** `src/v1/engine/context_manager.py`, lines 149-150

**Description:**

The skip list for context resolution is:

```python
if key in ['java_code', 'imports']:
    resolved[key] = value
```

This skips `java_code` and `imports` because they contain code that accesses context variables at runtime (in Java). However, `python_code` is NOT in the skip list.

Python components (`PythonRowComponent`, `PythonDataFrameComponent`, `PythonComponent`) use a `python_code` config key that contains Python source code to be executed via `exec()`. This code may contain strings like `context.get('output_dir')` or direct `context.variable_name` references that are intended to be resolved at **execution time**, not at config resolution time.

The `resolve_string()` method's Pattern 2 at context_manager.py line 130 replaces `context.variable` with the variable's value:

```python
pattern2 = r'\bcontext\.(\w+)\b'
```

This matches `context.get` and tries to resolve it as a context variable named `get`, which likely returns `None` or the string representation of the `get` method.

**Impact:**

- Python code like `result = context.get('threshold')` becomes `result = None` (if `get` is not a context variable name).
- Python code like `output_row['dir'] = context.output_dir + '/file.csv'` becomes `output_row['dir'] = /data/output + '/file.csv'` -- which is a syntax error (unquoted path).
- All three Python components are affected.

**Recommended fix:**

Add `'python_code'` to the skip list:

```python
if key in ['java_code', 'imports', 'python_code']:
    resolved[key] = value
```

**Effort estimate:** 2 minutes.

---

### 5.5 `resolve_string` Expression Handling Edge Cases

**File:** `src/v1/engine/context_manager.py`, lines 76-139

**Description:**

The `resolve_string()` method has a special branch for expressions containing both `+` and `${context.`:

```python
if '+' in value and '${context.' in value:
    # Expression handling
    parts = []
    for part in value.split('+'):
        # ...
    return ''.join(parts)
```

**Issue A: Premature split on `+`**

The expression `${context.base_url} + "/api?a=1&b=2+3"` splits on ALL `+` characters, including the `+` inside the quoted string `"2+3"`. This produces incorrect parts.

**Issue B: Falls through to Pattern 2 for non-expression strings**

After the expression branch, the method applies Pattern 1 (`${context.variable}`) and Pattern 2 (`context.variable`) to ALL non-expression strings. Pattern 2 is overly broad:

```python
pattern2 = r'\bcontext\.(\w+)\b'
```

This matches any `context.XXX` in any string, including:
- Python code: `context.get('key')` -> resolves `get` as a variable name
- Error messages: `"Invalid context.param value"` -> resolves `param` as a variable name
- Documentation strings in config
- File paths containing `context.` as a directory name

**Impact:**

- Expressions with `+` inside quoted strings produce garbled results.
- Non-expression strings containing `context.` followed by a word are silently modified.

**Recommended fix:**

- Parse quoted strings before splitting on `+`.
- Remove or restrict Pattern 2 to only apply in specific contexts (or remove it entirely -- `${context.var}` syntax should be sufficient).

**Effort estimate:** 1-2 hours.

---

### 5.6 Context Type Information Loss in Converter Pipeline

**File:** `src/converters/complex_converter/converter.py`, lines 141-155; `src/v1/engine/context_manager.py`, lines 58-66

**Description:**

The converter extracts context variables with their Talend types and calls `ExpressionConverter.convert_type()` to map them to Python type names. The context dict produced looks like:

```json
{
  "Default": {
    "threshold": {"value": "100", "type": "int"},
    "input_dir": {"value": "/data/input", "type": "str"}
  }
}
```

The `ContextManager.set()` method receives these and calls `_convert_type()`:

```python
def set(self, key: str, value: Any, value_type: Optional[str] = None) -> None:
    if value_type:
        value = self._convert_type(value, value_type)
    self.context[key] = value
```

But as documented in Section 1.6, `_convert_type()` is broken for most types. The type string `'int'` maps to the string literal `'int'` in the type_mapping, which is not callable, so the conversion fails silently and the value remains a string.

**Impact:**

- Context variables remain as strings regardless of their declared type.
- This cascades through the entire engine: all comparisons, arithmetic, and type-dependent logic on context variables operate on strings.

**Recommended fix:** Fix `_convert_type()` as described in Section 1.6.

---

## 6. Missing Component Implementations

The converter (`component_parser.py` lines 18-103) maps Talend component types to engine class names. Several mapped names have no corresponding implementation in the engine.

---

### 6.1 Converter-to-Engine Mapping Gaps

The following table shows component types that the converter maps to class names that do NOT exist in the engine's `COMPONENT_REGISTRY` (engine.py lines 56-205):

| Talend Type | Converter Maps To | In Engine Registry? | Engine Class Exists? | Impact |
|------------|-------------------|--------------------|--------------------|--------|
| `tFileList` | `FileList` | No | No (only `BaseIterateComponent` base class) | Iterate components cannot execute |
| `tFlowToIterate` | `FlowToIterate` | No | No | Flow-to-iterate conversion impossible |
| `tRunJob` | `RunJobComponent` | No | No | Sub-job invocation impossible |
| `tPrejob` | `PrejobComponent` | No | No | Pre-job hooks do not execute |
| `tPostjob` | `PostjobComponent` | No | No | Post-job hooks do not execute |
| `tXMLMap` | `TXMLMap` | `XMLMap` (different name) | Yes (as `XMLMap`) | Name mismatch -- converter output does not match registry |
| `tFileInputMSXML` | `FileInputMSXMLComponent` | No | No | MS XML input unsupported |
| `tAdvancedFileOutputXML` | `AdvancedFileOutputXMLComponent` | No | No | Advanced XML output unsupported |
| `tFileInputJSON` (via legacy mapping) | `FileInputJSONComponent` | `FileInputJSON` (different name) | Yes (as `FileInputJSON`) | Name mismatch |
| `tFileOutputExcel` (via legacy mapping) | `FileOutputExcelComponent` | `FileOutputExcel` (different name) | Yes (as `FileOutputExcel`) | Name mismatch |
| `tSwiftDataTransformer` | `TSwiftDataTransformer` | `SwiftTransformer` (different name) | Yes (as `SwiftTransformer`) | Name mismatch |
| `tAggregateSortedRow` | `TAggregateSortedRow` | `TAggregateSortedRow` | Yes | Correct |
| `tFileInputRaw` | `TFileInputRaw` | `TFileInputRaw` | Yes | Correct |
| `tReplace` | (parsed but no mapping) | No | No | tReplace unsupported |
| `tParseRecordSet` | (parsed but no mapping) | No | No | tParseRecordSet unsupported |
| `tSplitRow` | (parsed but no mapping) | No | No | tSplitRow unsupported |
| `tSampleRow` | (parsed but no mapping) | No | No | tSampleRow unsupported |
| `tLoop` | (parsed but no mapping) | No | No | tLoop unsupported |
| `tConvertType` | (parsed but no mapping) | No | No | tConvertType unsupported |
| `tMemorizeRows` | (parsed but no mapping) | No | No | tMemorizeRows unsupported |
| `tParallelize` | (parsed but no mapping) | No | No | tParallelize unsupported |
| `tForeach` | (parsed but no mapping) | No | No | tForeach unsupported |
| `tChangeFileEncoding` | (parsed but no mapping) | No | No | Encoding change unsupported |
| `tHashOutput` | (parsed but no mapping) | No | No | Hash output unsupported |
| `tExtractRegexFields` | (parsed but no mapping) | No | No | Regex extraction unsupported |

**Key critical gaps:**

1. **tFileList / tFlowToIterate:** The `BaseIterateComponent` base class exists and is well-designed, but no concrete implementations exist. Any job with iterate loops will fail with "Unknown component type" at engine.py line 280.

2. **tPrejob / tPostjob:** These are essential Talend patterns for setup/teardown. Without them, initialization logic (e.g., creating directories, loading context from files, checking prerequisites) cannot execute.

3. **tRunJob:** Child job invocation is fundamental to Talend's job composition model. Without this, complex multi-job workflows cannot be migrated.

4. **Name mismatches (tXMLMap, tFileInputJSON, tFileOutputExcel, tSwiftDataTransformer):** The converter produces JSON with one class name, but the engine registry has a different name. When the engine tries to look up the converter's class name, it gets `None` and skips the component silently (engine.py line 280: `logger.warning(f"Unknown component type: {comp_type}")` then `continue`).

---

### 6.2 Impact on Job Migration

For a typical Talend job portfolio:

- **Jobs with iterate patterns (tFileList + downstream):** Cannot migrate. This is estimated at 30-50% of non-trivial jobs.
- **Jobs with pre/post job hooks:** Cannot migrate fully. Pre-job setup steps are skipped.
- **Jobs with sub-job calls (tRunJob):** Cannot migrate. This is common in orchestration jobs.
- **Jobs with tXMLMap:** Silently broken due to name mismatch. The component is skipped, and its downstream flow receives no data.

**Recommended fix priority:**
1. Fix name mismatches (5 minutes each, high impact).
2. Implement `FileList` (tFileList) -- most critical iterate component.
3. Implement `FlowToIterate` (tFlowToIterate) -- second most common.
4. Implement `PrejobComponent` and `PostjobComponent` (can be simple pass-through).
5. Implement `RunJobComponent` (complex -- requires engine nesting).

---

## 7. Converter Systemic Issues

The converter (`complex_converter/`) translates Talend XML into JSON configs for the engine. Several systemic issues affect all converted jobs.

---

### 7.1 Broken Import Chain (`aggregate` vs `transform`)

**File:** `src/v1/engine/engine.py`, line 40

This is documented in Section 1.4 as a P0 bug. The engine cannot load because it imports `AggregateSortedRow`, `Denormalize`, `Normalize`, and `Replicate` from `.components.aggregate`, but they live in `.components.transform`.

---

### 7.2 Missing Parser Methods (`parse_tfilecopy`, `parse_tfileoutputebcdic`)

**File:** `src/converters/complex_converter/converter.py`, lines 287 and 372

**Description:**

The converter's `_parse_component()` method calls:

- `self.component_parser.parse_tfilecopy(node, component)` (line 287 for `tFileCopy`)
- `self.component_parser.parse_tfileoutputebcdic(node, component)` (line 372 for `tFileOutputEBCDIC`)

Neither method exists in `component_parser.py`. Running the converter on any Talend job containing a `tFileCopy` or `tFileOutputEBCDIC` component will raise `AttributeError: 'ComponentParser' object has no attribute 'parse_tfilecopy'`.

**Impact:**

- Conversion of jobs containing `tFileCopy` fails with an unhandled exception.
- Conversion of jobs containing `tFileOutputEBCDIC` fails similarly.
- `tFileCopy` is a common component, making this a frequent issue.

**Recommended fix:**

Implement the missing methods, or fall back to `parse_base_component()` for now:

```python
elif component_type == 'tFileCopy':
    # TODO: implement specific parsing
    pass  # falls through to return base component

elif component_type == 'tFileOutputEBCDIC':
    # TODO: implement specific parsing
    pass
```

**Effort estimate:** 30 minutes per method (for proper implementation) or 2 minutes (for fallback).

---

### 7.3 Converter Type Name Mismatches

**File:** `src/converters/complex_converter/component_parser.py`, lines 18-103

**Description:**

The converter's `component_mapping` dict maps Talend type names to engine class names. Several mappings produce names that don't match the engine's `COMPONENT_REGISTRY`:

| Talend Type | Converter Produces | Engine Registry Has | Match? |
|------------|-------------------|-------------------|--------|
| `tXMLMap` | `TXMLMap` | `XMLMap` | NO |
| `tFileInputJSON` | `FileInputJSONComponent` | `FileInputJSON` | NO |
| `tFileOutputExcel` | `FileOutputExcelComponent` | `FileOutputExcel` | NO |
| `tSwiftDataTransformer` | `TSwiftDataTransformer` | `SwiftTransformer` | NO |
| `tFileInputRaw` | `TFileInputRaw` | `TFileInputRaw` and `tFileInputRaw` | YES |

**Impact:**

- When a converted JSON file contains `"type": "TXMLMap"`, the engine looks up `TXMLMap` in `COMPONENT_REGISTRY` and gets `None`.
- The component is silently skipped (`engine.py:280-281`: `logger.warning(...)` then `continue`).
- This means the component never executes, its outputs are never produced, and all downstream components receive no input data.
- The downstream components that check `_are_inputs_ready()` will never become ready, causing the execution to stall.

**Recommended fix:**

Either:
A. Fix the converter mappings to match the engine registry names.
B. Add aliases to the engine registry (e.g., `'TXMLMap': XMLMap`).
C. Both (belt and suspenders).

**Effort estimate:** 10 minutes.

---

### 7.4 Universal Null-Safety Issue in XML Parsing

**File:** `src/converters/complex_converter/component_parser.py` (throughout)

**Description:**

The converter extensively uses patterns like:

```python
for param in node.findall('.//elementParameter[@name="FILENAME"]'):
    value = param.get('value', '')
    break
```

This pattern is safe. However, many component-specific parsers access XML attributes with less safety:

```python
# Example from parse_base_component (approx line 388+):
component_type = node.get('componentName')
component_id = node.get('componentProperties', {}).get('uniqueName')
```

The `node.get('componentProperties', {})` idiom does NOT work with `xml.etree.ElementTree` -- `Element.get()` retrieves XML attributes, not child elements. If `componentProperties` is a child element, `findall()` or `find()` should be used. If it's an attribute, `.get()` is correct but the `{}` default is wrong (Element.get returns a string, not a dict).

While this pattern does not cause a crash (it returns `None` which is handled), it indicates a systematic confusion between XML attributes and child elements that could cause incorrect parsing.

**Impact:**

- Potential for `NoneType` errors in parser methods.
- Incorrect default values when attributes are missing.
- Silent data loss when expected XML structures are not found.

**Recommended fix:** Audit all parser methods for correct XML access patterns. Use `find()` for child elements and `get()` for attributes.

**Effort estimate:** 4-8 hours.

---

### 7.5 Schema Type Format (Python vs Talend)

**File:** `src/converters/complex_converter/component_parser.py`, `src/v1/engine/base_component.py` lines 319-338

**Description:**

There are THREE different type naming conventions in use:

1. **Talend types** (in XML): `id_String`, `id_Integer`, `id_Long`, `id_Float`, `id_Double`, `id_Boolean`, `id_Date`, `id_BigDecimal`
2. **Converter output types** (in JSON schema): Whatever `ExpressionConverter.convert_type()` returns -- this may be `str`, `int`, `float`, etc.
3. **Engine type mapping** (in `validate_schema()`): Accepts BOTH Talend types (`id_String`) and Python types (`str`, `int`, etc.)

The converter's `ExpressionConverter.convert_type()` converts Talend types to Python names. But some converter code paths pass through Talend types directly (when the schema is copied from XML metadata without type conversion).

The engine's `validate_schema()` at base_component.py lines 320-338 has mappings for both, which is correct, but creates ambiguity:

```python
type_mapping = {
    'id_String': 'object',
    'id_Integer': 'int64',
    # ...
    'str': 'object',
    'int': 'int64',
    # ...
}
```

**Impact:**

- When the converter produces a schema with Talend types, the engine handles it.
- When the converter produces Python types, the engine handles it.
- But when types are NOT in either mapping (e.g., `'String'`, `'INTEGER'`, `'java.lang.String'`), the fallback is `'object'`, which means the column is treated as a generic object type with no validation.
- This silent fallback masks type conversion errors.

**Recommended fix:**

- Standardize on ONE type naming convention (preferably Talend types, since they carry more semantic information).
- Have the converter always output Talend types.
- Remove the Python type mappings from the engine (or keep them as aliases with a deprecation warning).
- Log a warning when a type falls through to the default.

**Effort estimate:** 2-4 hours.

---

### 7.6 Converter Expression Converter Aggressive Java Detection

**File:** `src/converters/complex_converter/expression_converter.py`, lines 67-100

**Description:**

The `detect_java_expression()` method uses aggressive detection of Java operators. The comment at line 87 explicitly states:

```python
# Be aggressive: if ANY operator is present, mark as Java
```

The operator list includes `+`, `-`, `*`, `/`, `%`, `>`, `<`, etc. While there are some false-positive filters (URLs, file paths), many legitimate Python values will be incorrectly marked as Java expressions:

- File paths with hyphens: `"/data/my-file.csv"` -- the `-` triggers detection.
- Arithmetic context variables: `"100"` with nearby `*` or `+` -- would depend on exact pattern matching.
- String concatenation: `"prefix" + "suffix"` -- the `+` triggers detection.
- Comparison expressions that should remain as Python: `threshold > 100`.

When a value is marked as Java, it gets the `{{java}}` prefix, which means the engine will try to evaluate it through the Java bridge. If the Java bridge is not available, the expression remains unresolved (base_component.py line 129: logs a warning and continues with the raw value).

**Impact:**

- Values that should be simple strings get the `{{java}}` prefix and are not resolved.
- Components receive config values like `{{java}}/data/output/2024-01-15/results.csv` instead of the actual file path.
- This causes FileNotFoundError, incorrect filter conditions, and wrong output paths.

**Recommended fix:**

- Reduce aggressiveness of Java detection.
- Only mark expressions as Java when they contain clear Java-specific patterns (method calls, type casts, ternary operators).
- Do not mark simple arithmetic or comparison operators as Java -- these can be evaluated in Python.

**Effort estimate:** 2-4 hours.

---

## 8. Testing Gaps

---

### 8.1 Zero Unit Tests for Components

**File:** `tests/v1/`

**Description:**

The `tests/v1/` directory contains only:

```
tests/v1/__init__.py
tests/v1/test_java_integration.py
tests/v1/unit/__init__.py
tests/v1/unit/test_bridge_arrow_schema.py
```

Both test files are related to the Java bridge. There are:

- **0 tests** for any of the 40+ engine components (FileInputDelimited, Map, FilterRows, AggregateRow, etc.).
- **0 tests** for `BaseComponent.execute()` and its execution modes.
- **0 tests** for `GlobalMap` (the `get()` NameError would be caught by any test).
- **0 tests** for `ContextManager` (the `_convert_type()` bug would be caught by any test).
- **0 tests** for `TriggerManager` (the `!` -> `not` corruption would be caught by any test).
- **0 tests** for `BaseIterateComponent`.
- **0 tests** for the engine's `execute()` method.
- **0 tests** for any streaming mode behavior.

**Impact:**

- Every bug documented in this report could have been caught by basic unit tests.
- The P0 bugs (Sections 1.1, 1.2, 1.4, 1.5, 1.6) are simple errors that would fail immediately under any test.
- Without tests, every code change risks introducing regressions with no detection mechanism.
- Developer confidence in the codebase is effectively zero -- any change could break anything.

**Recommended fix:**

Priority test targets (ordered by impact):

1. `GlobalMap` -- test `get()`, `put()`, `get_component_stat()` with defaults.
2. `ContextManager` -- test `_convert_type()` for all 16 type mappings, `resolve_string()`, `resolve_dict()` with nested structures.
3. `BaseComponent.execute()` -- test success path, error path, streaming mode, hybrid mode.
4. `TriggerManager._evaluate_condition()` -- test all operator replacements, especially `!=`.
5. `BaseComponent._update_global_map()` -- test that it doesn't crash.
6. Component smoke tests -- for each component, test with minimal valid input.

**Effort estimate:** 40-80 hours for comprehensive test suite.

---

### 8.2 No Integration Tests

**Description:**

There are no tests that exercise the full pipeline:
1. Convert a Talend XML file.
2. Load the JSON into the engine.
3. Execute the job.
4. Verify output data.

**Impact:**

- The interaction between converter and engine is untested. Name mismatches (Section 7.3) and type format inconsistencies (Section 7.5) are invisible without integration tests.
- Multi-component jobs (with triggers, iterate, multiple subjobs) have never been tested end-to-end.

**Recommended fix:**

Create a set of reference Talend jobs (or hand-crafted JSON configs) that exercise:
1. Simple linear flow (FileInput -> Map -> FileOutput).
2. Branching flow (FileInput -> tReplicate -> [FileOutput1, FileOutput2]).
3. Trigger flow (Subjob1 -OnSubjobOk-> Subjob2).
4. Iterate flow (tFileList -> iterate -> FileInput -> Map -> FileOutput).
5. Error handling (tDie, tWarn, OnSubjobError).

**Effort estimate:** 24-40 hours.

---

### 8.3 No Converter Parser Tests

**Description:**

The converter has 70+ parser methods (`parse_tmap`, `parse_aggregate`, `parse_filter_rows`, etc.) with zero tests. Given that:
- Two parser methods referenced in the converter don't exist (Section 7.2).
- Multiple type name mismatches exist between converter output and engine registry (Section 7.3).
- XML parsing correctness is critical for data integrity.

This is a significant gap.

**Recommended fix:**

For each parser method, create a test with a minimal XML snippet that verifies:
1. The method doesn't crash.
2. The output has the correct `type` field matching the engine registry.
3. Required config fields are populated.
4. Schema is correctly extracted.

**Effort estimate:** 16-24 hours.

---

## 9. Recommendations

### 9.1 Immediate (Must Fix Before Any Execution is Possible)

These fixes are required to make the engine importable and functional. Without them, no job can execute.

| Priority | Issue | Section | Fix | Effort |
|----------|-------|---------|-----|--------|
| P0-1 | Engine import fails (aggregate vs transform) | 1.4 | Change import path on engine.py:40 | 2 min |
| P0-2 | Engine import fails (FileInputXML casing) | 1.5 | Fix casing in file/__init__.py:10 | 2 min |
| P0-3 | `_update_global_map()` crashes (undefined `value`) | 1.1 | Fix f-string on base_component.py:304 | 5 min |
| P0-4 | `GlobalMap.get()` NameError (missing `default` param) | 1.2 | Add `default` parameter to get() signature | 2 min |
| P0-5 | `_convert_type()` broken (string literals not callable) | 1.6 | Replace string literals with function references | 10 min |
| P0-6 | `replace_in_config` literal `[i]` bug | 1.3 | Change `f"{path}[i]"` to `f"{path}[{i}]"` | 2 min |
| P0-7 | `__repr__` missing opening paren | 1.7 | Add `(` | 1 min |

**Total effort: approximately 25 minutes.** These are all trivial fixes but they completely block all functionality.

---

### 9.2 Short-Term (Fix Before Production Migration)

These fixes address correctness issues that cause wrong results, silent data loss, or security vulnerabilities.

| Priority | Issue | Section | Effort |
|----------|-------|---------|--------|
| P1-1 | Trigger `!` corrupts `!=` | 3.2 | 15 min |
| P1-2 | Trigger `((Boolean)...)` not handled | 3.1 | 30 min |
| P1-3 | `eval()` without sandboxing | 3.3 | 1-2 hr |
| P1-4 | Streaming drops reject data | 4.1 | 30 min |
| P1-5 | HYBRID mode breaks stateful components | 4.2 | 2 hr |
| P1-6 | `resolve_dict` skips dicts-in-lists | 5.3 | 15 min |
| P1-7 | `resolve_dict` corrupts `python_code` | 5.4 | 2 min |
| P1-8 | `validate_schema` inverted nullable logic | 5.1 | 15 min |
| P1-9 | `self.config` mutation (non-reentrant) | 5.2 | 15 min |
| P1-10 | Converter type name mismatches | 7.3 | 10 min |
| P1-11 | Exit code never propagated | 2.3 | 10 min |
| P1-12 | Missing parser methods crash converter | 7.2 | 30 min |
| P1-13 | Job status reports success on stall | 2.2 | 30 min |
| P1-14 | `die_on_error` not enforced by engine | 2.4 | 2-4 hr |

**Total effort: approximately 8-12 hours.**

---

### 9.3 Long-Term (Hardening)

These address architecture-level issues and the testing gap.

| Priority | Issue | Section | Effort |
|----------|-------|---------|--------|
| P2-1 | Implement tFileList component | 6.1 | 8-16 hr |
| P2-2 | Implement tFlowToIterate component | 6.1 | 4-8 hr |
| P2-3 | Implement tPrejob/tPostjob | 6.1 | 2-4 hr |
| P2-4 | Implement tRunJob | 6.1 | 16-24 hr |
| P2-5 | Trigger system correctness review | 3.4 | 4-8 hr |
| P2-6 | Converter expression detection tuning | 7.6 | 2-4 hr |
| P2-7 | Schema type standardization | 7.5 | 2-4 hr |
| P2-8 | XML parser null-safety audit | 7.4 | 4-8 hr |
| P3-1 | Unit tests for GlobalMap | 8.1 | 2 hr |
| P3-2 | Unit tests for ContextManager | 8.1 | 4 hr |
| P3-3 | Unit tests for TriggerManager | 8.1 | 4 hr |
| P3-4 | Unit tests for BaseComponent | 8.1 | 4 hr |
| P3-5 | Component smoke tests (40+ components) | 8.1 | 24-40 hr |
| P3-6 | Integration tests | 8.2 | 24-40 hr |

**Total effort: approximately 100-170 hours.**

---

## Appendix A: File Reference Index

All files referenced in this document with their roles:

| File | Role | Key Issues |
|------|------|-----------|
| `src/v1/engine/base_component.py` | Base class for all components | 1.1, 1.3, 1.7, 4.1, 4.2, 4.5, 5.1, 5.2 |
| `src/v1/engine/engine.py` | Job orchestrator | 1.4, 1.5, 2.1-2.4 |
| `src/v1/engine/global_map.py` | Global variable storage | 1.2 |
| `src/v1/engine/context_manager.py` | Context variable resolution | 1.6, 5.3, 5.4, 5.5, 5.6 |
| `src/v1/engine/trigger_manager.py` | Trigger/control flow management | 3.1, 3.2, 3.3, 3.4 |
| `src/v1/engine/base_iterate_component.py` | Base class for iterate components | 5.2 |
| `src/v1/engine/exceptions.py` | Exception hierarchy | (no direct bugs) |
| `src/v1/engine/components/file/__init__.py` | File component exports | 1.5 |
| `src/v1/engine/components/aggregate/__init__.py` | Aggregate component exports | 1.4 |
| `src/v1/engine/components/transform/__init__.py` | Transform component exports | 1.4 |
| `src/v1/engine/components/control/die.py` | tDie implementation | 2.3 |
| `src/v1/engine/components/control/warn.py` | tWarn implementation | 1.2 |
| `src/converters/complex_converter/converter.py` | Talend XML to JSON converter | 7.1, 7.2, 7.3 |
| `src/converters/complex_converter/component_parser.py` | Component-specific XML parsers | 6.1, 7.2, 7.3, 7.4 |
| `src/converters/complex_converter/expression_converter.py` | Java expression detection | 7.6 |

---

## Appendix B: Dependency Chain of Failures

This diagram shows how the critical bugs cascade. A single test execution triggers multiple failures:

```
1. Import engine.py
   |
   +-> ImportError (Section 1.4): AggregateSortedRow not in aggregate package
   |   (engine cannot load -- STOP)
   |
   [After fixing 1.4:]
   +-> ImportError (Section 1.5): FileInputXML casing mismatch
   |   (engine cannot load -- STOP)
   |
   [After fixing 1.5:]
2. Create ETLEngine(config)
   |
   +-> ContextManager.__init__() -> load_context() -> set() -> _convert_type()
   |   +-> TypeError (Section 1.6): 'str' is not callable
   |       (caught by except, logged as warning, value stays as string)
   |       [SILENT FAILURE: context vars have wrong types]
   |
3. engine.execute()
   |
   +-> _execute_component(comp_id)
   |   +-> component.execute(input_data)
   |       +-> context_manager.resolve_dict(self.config)
   |       |   +-> resolve_dict skips dicts-in-lists (Section 5.3)
   |       |       [SILENT FAILURE: some config values unresolved]
   |       |   +-> resolve_dict corrupts python_code (Section 5.4)
   |       |       [SILENT FAILURE: python code mangled]
   |       |
   |       +-> component._process(input_data)
   |       |   [May succeed or fail depending on component]
   |       |
   |       +-> _update_global_map()
   |           +-> NameError (Section 1.1): 'value' not defined
   |               [CRASH: replaces any real error on error path]
   |               [CRASH: prevents result return on success path]
   |
   +-> trigger_manager.get_triggered_components(comp_id, status)
       +-> _evaluate_condition(condition)
           +-> GlobalMap.get(key) -> NameError (Section 1.2): 'default' not defined
               [CRASH: trigger evaluation fails, returns False]
               [SILENT FAILURE: triggers never fire]
```

**Bottom line:** Even after fixing the import errors (Sections 1.4 and 1.5), every component execution still crashes at `_update_global_map()` (Section 1.1), and every trigger evaluation crashes at `GlobalMap.get()` (Section 1.2). These four bugs must be fixed together as a minimum viable fix.

---

## Appendix C: Exception Hierarchy Analysis

**File:** `src/v1/engine/exceptions.py`

The exception hierarchy is:

```
Exception
  +-> ETLError (base)
        +-> ConfigurationError
        +-> DataValidationError
        +-> ComponentExecutionError (has component_id, cause)
        +-> FileOperationError
        +-> JavaBridgeError
        +-> ExpressionError
        +-> SchemaError
```

**Issues:**

1. **No component uses most of these exceptions.** A grep for usage shows:
   - `ComponentExecutionError`: Used by `Die` and `Warn` components.
   - `ConfigurationError`: Imported by `Die` and `Warn` but never raised.
   - `FileOperationError`: Not used by any component.
   - `DataValidationError`: Not used by any component.
   - `ExpressionError`: Not used by any component.
   - `SchemaError`: Not used by any component.

2. **Components raise generic exceptions.** Most components raise `ValueError`, `RuntimeError`, or `Exception` instead of the structured ETL exceptions. This means the engine cannot distinguish between configuration errors, data errors, and system errors.

3. **The engine only checks for `exit_code` attribute** (engine.py line 605), not exception type. The exception hierarchy provides no practical benefit for error handling flow.

4. **`ComponentExecutionError` has a `cause` field** (line 29) but it duplicates Python 3's built-in exception chaining (`raise X from Y`). The `cause` is stored but never inspected by any code.

**Recommended fix:**

- Adopt the exception hierarchy across all components.
- Have the engine's error handling differentiate based on exception type (e.g., `ConfigurationError` -> abort immediately, `DataValidationError` -> check `die_on_error`, `FileOperationError` -> retry?).
- Remove the `cause` field and use Python's standard `raise X from Y` chaining.

**Effort estimate:** 8-16 hours (touching all 40+ components).

---

## Appendix D: GlobalMap.get() Call Sites Audit

Every call to `GlobalMap.get()` in the codebase is broken (Section 1.2). Here is a complete audit of call sites and what happens at each:

| File | Line | Call Pattern | What Breaks |
|------|------|-------------|-------------|
| `global_map.py:28` | `self._map.get(key, default)` | `default` undefined -> `NameError` | Core method broken |
| `global_map.py:58` | `self.get(key, default)` | Passes 2 args to 1-param method -> `TypeError` (after fixing NameError) | Component stat fallback broken |
| `trigger_manager.py:205` | `self.global_map.get(key, 0)` | 2 args to 1-param method -> `TypeError` | Integer cast triggers broken |
| `trigger_manager.py:214` | `self.global_map.get(key)` | `NameError` on `default` in body | Generic globalMap triggers broken |
| `die.py:202` | `self.global_map.get(key, 0)` | 2 args to 1-param method -> `TypeError` | tDie message resolution broken |
| `warn.py:181` | `self.global_map.get(key, 0)` | 2 args to 1-param method -> `TypeError` | tWarn message resolution broken |

**Note:** The `global_map.py:28` `NameError` crashes the method before the `TypeError` from wrong argument count can manifest. After fixing the `NameError` by adding `default` to the signature, ALL call sites will work correctly because they all pass either 1 arg (using the default `None`) or 2 args (using a custom default).

---

## Appendix E: Streaming Mode Correctness Matrix

For each component, whether streaming mode produces correct results:

| Component | Stateless? | Streaming Safe? | Issue |
|-----------|-----------|-----------------|-------|
| FileInputDelimited | Yes | Yes | Reads file once regardless |
| FileOutputDelimited | Yes | Yes* | Append mode only; overwrite mode overwrites per chunk |
| Map | Yes | Yes | Row-level transformation |
| FilterRows | Yes | Yes | Row-level filter |
| FilterColumns | Yes | Yes | Column projection |
| LogRow | Yes | Yes | Row-level logging |
| SortRow | **No** | **No** | Chunks sorted independently, not globally |
| AggregateRow | **No** | **No** | Partial aggregates per chunk |
| AggregateSortedRow | **No** | **No** | Assumes global sort order |
| UniqueRow | **No** | **No** | Dedup per chunk only |
| Denormalize | **No** | **No** | Grouping requires all data |
| Normalize | **No** | **No** | Split requires all data |
| PivotToColumnsDelimited | **No** | **No** | Pivot requires all group data |
| UnpivotRow | Yes | Yes | Row-level transformation |
| Join | **No** | **No** | Join requires all lookup data |
| Unite | **Maybe** | **Maybe** | Depends on union mode |
| Replicate | Yes | Yes | Row-level copy |
| ExtractDelimitedFields | Yes | Yes | Row-level extraction |
| ExtractJSONFields | Yes | Yes | Row-level extraction |
| ExtractPositionalFields | Yes | Yes | Row-level extraction |
| ExtractXMLField | Yes | Yes | Row-level extraction |
| SchemaComplianceCheck | Yes | Yes | Row-level validation |
| RowGenerator | N/A | N/A | No input data |
| JavaRowComponent | Yes | Yes | Row-level transformation |
| JavaComponent | Depends | Depends | Custom code |
| PythonRowComponent | Yes | Yes | Row-level transformation |
| PythonComponent | Depends | Depends | Custom code |
| PythonDataFrameComponent | Depends | Depends | Custom code |
| SwiftBlockFormatter | Depends | Depends | Block-level formatting |
| SwiftTransformer | Yes | Yes | Row-level transformation |
| ContextLoad | N/A | N/A | No data transformation |
| Warn | Yes | Yes | Pass-through |
| Die | N/A | N/A | Terminates job |
| SleepComponent | N/A | N/A | No data transformation |
| SendMailComponent | Yes | Yes | No data transformation |

**Count:** 10 components are unsafe in streaming mode. Since HYBRID is the default, any job processing > 3GB of data through these components will produce wrong results.

---

## Appendix F: Complete Code Path for Component Execution

This traces every line of code executed when a component runs, for debugging reference:

```
engine.execute()                                    [engine.py:394]
  -> execution_queue.append(comp_id)                [engine.py:450]
  -> _execute_component(comp_id)                    [engine.py:471 -> 538]
     -> _get_input_data(comp_id)                    [engine.py:554 -> 779]
        -> component.inputs                         [engine.py:783]
        -> data_flows.get(input_flow)               [engine.py:789]
     -> component.execute(input_data)               [engine.py:558 -> base_component.py:188]
        -> _resolve_java_expressions()              [base_component.py:198 -> 100]
           -> scan_config(self.config)              [base_component.py:122]
           -> java_bridge.execute_batch...()        [base_component.py:149]
           -> replace_in_config(self.config)        [base_component.py:184]
              -> BUG: f"{path}[i]" (Section 1.3)   [base_component.py:174]
        -> context_manager.resolve_dict(config)     [base_component.py:202]
           -> resolve_string(value)                 [context_manager.py:153]
           -> resolve_dict(value) [recursive]       [context_manager.py:155]
           -> BUG: skips dicts-in-lists (5.3)       [context_manager.py:157]
           -> BUG: corrupts python_code (5.4)       [context_manager.py:152]
        -> self.config = resolved                   [base_component.py:202]
           -> BUG: config mutation (5.2)
        -> _auto_select_mode(input_data)            [base_component.py:206 -> 236]
        -> _execute_batch(input_data)               [base_component.py:214 -> 251]
           -> _process(input_data)                  [base_component.py:253]
              [component-specific logic]
        OR
        -> _execute_streaming(input_data)           [base_component.py:212 -> 255]
           -> _create_chunks(df)                    [base_component.py:262 -> 280]
           -> _process(chunk) [per chunk]           [base_component.py:269]
           -> BUG: drops rejects (4.1)              [base_component.py:270-271]
           -> pd.concat(results)                    [base_component.py:275]
        -> _update_global_map()                     [base_component.py:218 -> 298]
           -> global_map.put_component_stat()       [base_component.py:302]
           -> BUG: NameError on 'value' (1.1)       [base_component.py:304]
        -> self.status = SUCCESS                    [base_component.py:220]
        -> return result                            [base_component.py:225]
     -> [store results in data_flows]               [engine.py:569-585]
     -> trigger_manager.set_component_status()      [engine.py:593]
     -> execution_queue re-check                    [engine.py:496-498]
  -> trigger_manager.get_triggered_components()     [engine.py:484]
     -> _evaluate_condition()                       [trigger_manager.py:162 -> 184]
        -> BUG: only ((Integer)...) handled (3.1)   [trigger_manager.py:201]
        -> BUG: ! corrupts != (3.2)                 [trigger_manager.py:228]
        -> BUG: eval() unsandboxed (3.3)            [trigger_manager.py:234]
        -> global_map.get()                         [trigger_manager.py:205,214]
           -> BUG: NameError (1.2)                  [global_map.py:28]
```

---

## Appendix G: Recommended Fix Sequence

To avoid dependency issues, fixes should be applied in this order:

```
Phase 1: Make engine importable (5 minutes)
  1. Fix engine.py:40 import (Section 1.4)
  2. Fix file/__init__.py:10 casing (Section 1.5)

Phase 2: Make engine runnable (15 minutes)
  3. Fix global_map.py:26-28 get() signature (Section 1.2)
  4. Fix base_component.py:304 _update_global_map() (Section 1.1)
  5. Fix base_component.py:174 replace_in_config [i] (Section 1.3)
  6. Fix base_component.py:382 __repr__ (Section 1.7)

Phase 3: Make engine correct (2-4 hours)
  7. Fix context_manager.py:168-186 _convert_type() (Section 1.6)
  8. Fix trigger_manager.py:228 ! replacement (Section 3.2)
  9. Fix trigger_manager.py:201 cast type regex (Section 3.1)
  10. Fix context_manager.py:157 resolve_dict recursion (Section 5.3)
  11. Fix context_manager.py:150 python_code skip (Section 5.4)
  12. Fix base_component.py:351 nullable logic (Section 5.1)
  13. Fix base_component.py:202 config mutation (Section 5.2)

Phase 4: Fix converter pipeline (1-2 hours)
  14. Fix converter type name mismatches (Section 7.3)
  15. Add missing parser methods (Section 7.2)

Phase 5: Streaming mode safety (2 hours)
  16. Change default execution mode to batch (Section 4.2)
  17. Fix streaming reject data loss (Section 4.1)

Phase 6: Security and correctness (2-4 hours)
  18. Sandbox eval() in triggers (Section 3.3)
  19. Fix exit code propagation (Section 2.3)
  20. Add die_on_error to engine (Section 2.4)

Phase 7: Add tests (40-80 hours)
  21-30. Unit tests per Section 8.1

Phase 8: Implement missing components (30-50 hours)
  31-35. Missing components per Section 6.1
```

---

## Appendix H: Engine Initialization Sequence Analysis

The `ETLEngine.__init__()` method (engine.py lines 207-268) performs the following steps during initialization. Issues at each step are noted.

```
ETLEngine.__init__(job_config)
  |
  1. Load configuration (lines 215-219)
  |   -> If string path, opens file and parses JSON
  |   -> If dict, uses directly
  |   -> ISSUE: No validation of JSON structure. Missing 'components' key
  |     causes KeyError later, not during init.
  |
  2. Initialize Java Bridge Manager (lines 222-233)
  |   -> Checks java_config.enabled
  |   -> Creates JavaBridgeManager with routines and libraries
  |   -> Calls start() which finds a free port and launches JVM
  |   -> ISSUE: If JVM fails to start, the error propagates but
  |     no cleanup is performed on partially-initialized engine.
  |
  3. Initialize Python Routine Manager (lines 236-244)
  |   -> Checks python_config.enabled
  |   -> Creates PythonRoutineManager with routines directory
  |   -> ISSUE: If directory does not exist, only logs warning.
  |     Components that reference routines will fail later at runtime.
  |
  4. Initialize core components (lines 247-254)
  |   -> Creates GlobalMap (line 248)
  |   -> Creates ContextManager with initial_context (line 249-253)
  |     -> ContextManager.load_context() calls set() for each var
  |       -> set() calls _convert_type() which is broken (Section 1.6)
  |       -> SILENT FAILURE: types not converted, values remain strings
  |   -> Creates TriggerManager with GlobalMap reference (line 254)
  |
  5. Initialize components (line 266 -> _initialize_components)
  |   -> For each component config:
  |     -> Look up class in COMPONENT_REGISTRY (line 277)
  |       -> ISSUE: Unknown types silently skipped (line 280-281)
  |     -> Create instance with config, global_map, context_manager
  |     -> Set java_bridge reference (line 301)
  |     -> Set python_routine_manager reference (line 305)
  |   -> ISSUE: Components get direct reference to java_bridge_manager.bridge,
  |     which may be None if bridge failed to start. Components check this
  |     but the check is in _resolve_java_expressions(), not in _process().
  |
  6. Initialize triggers (line 267 -> _initialize_triggers)
  |   -> Loads from top-level 'triggers' array
  |   -> Also loads from per-component 'triggers'
  |   -> ISSUE: Duplicate triggers possible if both sources define same trigger
  |
  7. Identify subjobs (line 268 -> _identify_subjobs)
     -> Groups by subjob_id if provided
     -> Falls back to auto-detection via connectivity
     -> Registers with trigger manager
     -> ISSUE: Auto-detection uses BFS on flows only, ignoring trigger
       connections. Two components connected only by triggers are placed
       in separate subjobs, which may cause premature OnSubjobOk firing
       (because the subjob is "complete" when its single component finishes,
       even though a trigger should chain to additional work).
```

**Key architectural issue:** The initialization does not validate the completeness of the job configuration. Missing components (referenced in flows but not in the components list), dangling flows (from/to components that don't exist), and orphaned triggers are not detected during init. They manifest as runtime failures that are hard to diagnose.

**Recommended fix:** Add a validation step after initialization that checks:
1. All flow endpoints reference existing components.
2. All trigger endpoints reference existing components.
3. All component input flow names correspond to flows defined in the flows section.
4. No circular dependencies exist (except intentional iterate loops).

---

## Appendix I: ContextManager.resolve_string() Full Edge Case Analysis

The `resolve_string()` method (context_manager.py lines 76-139) handles several patterns. Here is an exhaustive analysis of edge cases:

**Pattern: Expression with `+` concatenation**

| Input | Expected Output | Actual Output | Correct? |
|-------|----------------|---------------|----------|
| `${context.dir} + "/file.csv"` | `/data/output/file.csv` | `/data/output/file.csv` | Yes |
| `${context.a} + ${context.b}` | `valueA + valueB` (concat) | `valueAvalueB` | Depends on intent |
| `"prefix" + ${context.x} + "suffix"` | `prefixVALsuffix` | `prefixVALsuffix` | Yes |
| `${context.a} + "+" + ${context.b}` | `A+B` | Breaks -- splits on literal `+` inside quotes | **No** |
| `${context.num} + 1` | Depends on type | `"42" + "1"` = `"421"` (string concat) | **No** -- should be 43 |
| `"no context here" + "but has plus"` | `no context herebut has plus` | `no context herebut has plus` | Yes (but odd) |

**Pattern: `${context.variable}` substitution**

| Input | Expected Output | Actual Output | Correct? |
|-------|----------------|---------------|----------|
| `${context.dir}` | `/data/output` | `/data/output` | Yes |
| `${context.missing}` | `${context.missing}` (unresolved) | `${context.missing}` | Yes (intentional) |
| `prefix_${context.env}_suffix` | `prefix_PROD_suffix` | `prefix_PROD_suffix` | Yes |
| `${context.a}${context.b}` | `AB` | `AB` | Yes |
| `${context.}` | No match (regex needs `\w+`) | `${context.}` | Correct (no match) |

**Pattern: `context.variable` bare substitution**

| Input | Expected Output | Actual Output | Correct? |
|-------|----------------|---------------|----------|
| `context.dir` | `/data/output` | `/data/output` | Yes |
| `context.get('x')` | Should NOT resolve | Tries to resolve `get` as variable name | **No** |
| `my_context.thing` | Should NOT resolve | Does NOT resolve (`\b` prevents match) | Yes |
| `the context.variable is` | Should NOT resolve? | Resolves `variable` | **Ambiguous** |

**Key finding:** The bare `context.variable` pattern (Pattern 2) is too aggressive and should be restricted or removed. It creates false positives in Python code, error messages, and documentation strings embedded in config values.

---

## Appendix J: Engine Execute Loop Termination Conditions

The main execution loop in `engine.execute()` (engine.py lines 452-499) has two termination conditions:

```python
while execution_queue or len(self.executed_components) < len(self.components):
```

**Condition 1: Queue is empty AND all components executed**

This is the normal termination. All components have been processed.

**Condition 2: Queue is empty AND NOT all components executed (stall)**

At lines 455-460:
```python
if not execution_queue:
    unexecuted = set(self.components.keys()) - self.executed_components
    if unexecuted:
        logger.warning(f"Execution stalled. Unexecuted components: {unexecuted}")
        break
```

**Stall scenarios:**

1. **Missing trigger chain:** Component A triggers Component B, but A fails. The trigger manager returns no triggered components for the error case (unless an OnSubjobError or OnComponentError trigger exists). Component B and its downstream are never started.

2. **Circular dependency:** If flows form a cycle (A -> B -> C -> A), all three components are waiting for input from each other. None can start. The stall detection catches this but does not explain the cause.

3. **Missing flow data:** If a component's input flow is never populated (because the upstream component was skipped due to unknown type, or because the flow name doesn't match), the component never becomes ready.

4. **Incorrect subjob activation:** If a subjob should be activated by a trigger but the trigger evaluation fails (due to GlobalMap.get() NameError -- Section 1.2), the subjob never activates, and its components are never queued.

**Stall detection issue:** The break at line 460 exits the outer while loop but does NOT set `self.failed_components`. The status calculation at line 505 sees an empty `failed_components` set and reports `'success'`. This is incorrect -- a stalled job should be reported as failed or incomplete.

**Recommended fix:**

After the stall break, add:
```python
break
# After the loop:
if len(self.executed_components) < len(self.components):
    unexecuted = set(self.components.keys()) - self.executed_components
    logger.error(f"Job stalled with {len(unexecuted)} unexecuted components: {unexecuted}")
    # Mark unexecuted components as failed
    for comp_id in unexecuted:
        self.failed_components.add(comp_id)
```

---

*Report generated from code analysis of the v1 engine codebase. All line numbers reference the code as of the audit date. File paths are relative to `src/v1/engine/` unless otherwise specified.*
