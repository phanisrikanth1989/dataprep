# V1 Engine -- Cross-Cutting Issues Report

## Executive Summary

This document catalogs **engine-level bugs and systemic issues** that affect all or most components in the v1 ETL engine. These are not individual component defects; they are problems in the shared infrastructure that every component relies on: `base_component.py`, `engine.py`, `global_map.py`, `context_manager.py`, `trigger_manager.py`, `base_iterate_component.py`, the converter pipeline, and the exception hierarchy.

**Phase 15.1 reconciliation (2026-05-11):** Of the ~42 named H3 issues catalogued in Sections 1-7 (the actionable bug sections), approximately 28 are closed by Phases 1-14 (struck through with phase tags below). Approximately 14 remain live (marked `[STILL LIVE]`) -- primarily the informational design-quality observations in Sections 2, 4, and 5 where partial improvements were made but the systemic concern persists. The per-component XCUT-XXX references that previously inflated the cross-cutting count to "200-250" have been consolidated into the per-component audit docs (Phase 15.1 Wave 1 reconciliation); this document now reflects only the root cross-cutting issues enumerated here.

**Original issue counts by severity (as audited pre-Phase-1):**

| Severity | Count | Description |
| ---------- | ------- | ------------- |
| P0 -- Critical | 7 | Engine crashes, data corruption, broken imports |
| P1 -- High | 9 | Incorrect behavior, masked errors, security holes |
| P2 -- Medium | 8 | Missing implementations, incomplete features |
| P3 -- Low | 6 | Code quality, minor inconsistencies |

**Engine health as of Phase 15.1 (2026-05-11):** The P0 critical bugs in Section 1 (all 7) are fully resolved. The P0 trigger bugs (3.1, 3.2) are resolved. The most impactful streaming, context, and converter gaps have been fixed. The engine is production-ready for the 71 shipped components. The 20 non-shipped components (9 control, 8 Oracle/MSSql variants, 1 tFileOutputEBCDIC, 1 tForeach, 1 tHashOutput) are a roadmap-level decision deferred to Phase 16.

**What was blocking production (pre-Phase-1):**

1. The engine module failed to import (`engine.py:40` -- broken aggregate imports). **[RESOLVED in Phase 1 (ENG-04)]**
2. Every component execution crashed at stats update (`base_component.py:304`). **[RESOLVED in Phase 1 (ENG-01)]**
3. Every `GlobalMap.get()` call raised `NameError` (`global_map.py:28`). **[RESOLVED in Phase 1 (ENG-02)]**
4. Context variable type conversion was broken for 10 of 16 mapped types (`context_manager.py:168-186`). **[RESOLVED in Phase 1 (ENG-05)]**
5. The trigger system's `!` replacement corrupted `!=` operators (`trigger_manager.py:228`). **[RESOLVED in Phase 1 (ENG-06)]**
6. Streaming mode silently dropped reject data for every component (`base_component.py:270-271`). **[RESOLVED in Phase 1 (ENG-07)]**
7. The `replace_in_config` function used literal `[i]` instead of `[{i}]`, breaking Java expression resolution in arrays (`base_component.py:174`). **[RESOLVED in Phase 1 (ENG-03)]**

---

## 1. Critical Engine Bugs (P0)

These bugs prevented the engine from functioning at all. All 7 are now resolved.

---

### ~~1.1 `_update_global_map()` Crash on Every Component Execution~~ [RESOLVED in Phase 1 (ENG-01), commit b856f5f]

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

### ~~1.2 `GlobalMap.get()` Broken Signature -- `NameError` on Every Call~~ [RESOLVED in Phase 1 (ENG-02), commit 511dd8c]

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

### ~~1.3 `replace_in_config` Literal `[i]` Bug -- Java Expressions in Arrays Never Resolve~~ [RESOLVED in Phase 1 (ENG-03), commit b856f5f]

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

### ~~1.4 Broken Imports in `engine.py` -- Engine Module Cannot Be Loaded~~ [RESOLVED in Phase 1 (ENG-04), commit 3e5ffbd]

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

### ~~1.5 `FileInputXML` Import Case Mismatch -- `FileInputXML` vs `FileInputXml`~~ [RESOLVED in Phase 1 sweep, commit 3e5ffbd]

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

### ~~1.6 `ContextManager._convert_type()` Broken for 10 of 16 Mapped Types~~ [RESOLVED in Phase 1 (ENG-05), commit 6e0a89b]

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
| ----- | ------- | -------------------------- |
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
| ----- | ------- | ------------- |
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

### ~~1.7 `BaseComponent.__repr__()` Missing Opening Parenthesis~~ [RESOLVED in Phase 1 sweep, commit b856f5f]

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

### 2.1 What Happens When a Component Fails [STILL LIVE -- informational; error cascade resolved, but stall detection behavior remains]

Here is the complete execution trace when a component's `_process()` method raises an exception:

**Step 1: `_process()` raises**

Any component's `_process()` raises an exception (e.g., `FileNotFoundError`, `ValueError`, `ComponentExecutionError`).

**Step 2: `BaseComponent.execute()` catches (line 227)**

```python
except Exception as e:
    self.status = ComponentStatus.ERROR
    self.error_message = str(e)
    self.stats['EXECUTION_TIME'] = time.time() - start_time
    self._update_global_map()    # <-- THIS CRASHED (see Section 1.1 -- now fixed)
    logger.error(f"Component {self.id} execution failed: {e}")
    raise
```

**Step 3: `_update_global_map()` now works correctly** (Section 1.1 resolved Phase 1)

The NameError is gone. The stats are updated and the original exception re-raises cleanly.

**Step 4: The original exception propagates up**

The `raise` on the error path executes. The original exception propagates to `_execute_component()` in `engine.py`.

**Step 5: `_execute_component()` catches**

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

The exception does not have an `exit_code` attribute, so it falls through to the generic error handling. The component is marked as failed.

**Step 6: Trigger evaluation**

After `_execute_component()` returns `'error'`, the engine calls trigger evaluation. `GlobalMap.get()` now works correctly (Section 1.2 resolved Phase 1). However, triggers dependent on specific conditions may not fire if the error condition is not matched.

**Net result post-Phase-1:** Each component failure produces a clean, traceable error. The cascade of secondary failures from Sections 1.1 and 1.2 no longer occurs.

---

### 2.2 Job Status Determination [STILL LIVE -- stall-as-success behavior persists in executor.py]

**File:** `src/v1/engine/engine.py` (via `executor.py`)

The job status is determined by inspecting `failed_components`:

```python
'status': 'success' if not self.executor.failed_components else 'failed',
```

**Issues:**

1. **Status value inconsistency:** The success path returns `'success'` and the failure path returns `'failed'`, but the exception path returns `'error'`. Three different strings for two states. Talend uses `0` (success) and non-zero integers (failure).

2. **Stalled execution is reported as success:** If the execution loop breaks due to a stall (unexecuted components with an empty queue), the engine falls through to the stats calculation. If no components failed (they were just never executed), `failed_components` is empty, and the job is reported as `'success'` even though multiple components never ran.

3. **Partial execution masquerade:** If 10 out of 15 components execute successfully and 5 are stalled (never started), the status is `'success'` with `components_executed: 10`. The caller must compare `components_executed` against expected total to detect this -- the status alone is misleading.

**Recommended fix:**

- Add a `'stalled'` or `'partial'` status when unexecuted components remain.
- Use consistent status values across all return paths.
- Include `components_total` in the return dict so callers can verify completeness.

---

### 2.3 Exit Code Propagation [STILL LIVE -- exit code read from tDie but not propagated as process exit code in non-critical paths]

**File:** `src/v1/engine/components/control/die.py`; `src/v1/engine/engine.py`

**Description:**

The `Die` component sets `error.exit_code = exit_code` and the engine checks for it:

```python
if hasattr(e, 'exit_code'):
    raise e
```

This re-raise propagates to `execute()`. The `__main__` block of `engine.py` does call `sys.exit(1)` on failure:

```python
sys.exit(1)
```

However, this is a blanket exit code 1, not the specific `exit_code` set by the tDie component. The `JOB_EXIT_CODE` value stored in GlobalMap by tDie is never read back by the engine to set the process exit code.

**Impact:**

- `tDie` sets a custom exit code but the process always exits with code 1 (not the custom code).
- External orchestrators (cron, Airflow, CI/CD) that use specific exit codes to distinguish error categories will always see exit code 1.

**Recommended fix:**

In the `__main__` block, extract the exit code from the job result and use it:
```python
exit_code = stats.get('exit_code', 1 if stats.get('status') != 'success' else 0)
sys.exit(exit_code)
```

Also include `exit_code` in the return dict from `execute()` when available.

**Effort estimate:** 10 minutes.

---

### 2.4 `die_on_error` Consistency Matrix [STILL LIVE -- engine-level enforcement now present via BaseComponent; per-component coverage improved but not universal]

The `die_on_error` config parameter controls whether a component should abort the job on error or silently continue. In Talend, most components default to `true`. Phase 1 added `die_on_error` as a first-class attribute on `BaseComponent` (defaulting to `True`), read from resolved config at each `execute()` call.

**Engine-Level Handling (post-Phase-1):**

`BaseComponent.execute()` reads `self.die_on_error = self.config.get("die_on_error", True)` at the start of each execution. Schema-violation routing uses `die_on_error` to decide whether to raise or route to reject. However, the executor still catches all exceptions and marks components as failed without re-raising unless `exit_code` is present (tDie pattern only).

**Component-Level Implementation:**

Components that implement `die_on_error` are documented in the per-component audit docs. Many components now handle it correctly via `BaseComponent.execute()` and `_apply_output_schema_validation()`. The legacy per-component ad-hoc checks have been largely superseded.

**Key remaining concern:**

The executor does not expose `die_on_error` as a first-class job-level abort mechanism for all components -- only tDie achieves a clean abort. All other components that fail with `die_on_error=True` are marked failed and execution continues to the next available component, which is inconsistent with Talend's behavior where `die_on_error=True` on a non-tDie component causes the subjob to error-out immediately.

**Recommended fix:**

Have the executor check `component.die_on_error` after catching a component exception, and re-raise as `ComponentExecutionError` with an exit code attribute when `die_on_error=True`.

**Effort estimate:** 2-4 hours.

---

## 3. Trigger System Issues

The trigger system (`trigger_manager.py`) manages the control flow between subjobs. It evaluates conditions and determines which components should execute next based on success/failure of preceding components.

---

### ~~3.1 No `((Boolean)...)` Regex -- Only `((Integer)...)` Is Handled~~ [RESOLVED in Phase 1 (ENG-06), commit bba3469]

**File:** `src/v1/engine/trigger_manager.py`, lines 200-208

**Description:**

The `_evaluate_condition()` method had a regex for `((Integer)globalMap.get("key"))`:

```python
pattern = r'\(\(Integer\)globalMap\.get\("([^"]+)"\)\)'
```

But Talend RunIf conditions frequently use other cast types:

- `((Boolean)globalMap.get("tFileExist_1_EXISTS"))` -- e.g., "run if file exists"
- `((String)globalMap.get("tFileInputDelimited_1_ERROR"))` -- e.g., "run if error message is set"
- `((Long)globalMap.get("tFileInputDelimited_1_NB_LINE"))` -- e.g., "run if rows > 0"

None of these were matched by the `((Integer)...)` regex. They passed through unmodified, which meant `((Boolean)globalMap.get("tFileExist_1_EXISTS"))` got to `eval()` as-is, causing a `SyntaxError` or `NameError` because `Boolean` is not defined in Python.

**Impact:**

- Any RunIf trigger that used a cast type other than `Integer` silently failed.
- The `except` clause at line 238 caught the error and returned `False`, meaning the trigger did NOT fire.
- This caused entire subjobs to be silently skipped -- a very hard-to-diagnose production issue.

**Recommended fix:**

Replace the single-type regex with a generic cast pattern:

```python
pattern = r'\(\((\w+)\)globalMap\.get\("([^"]+)"\)\)'
```

Then handle the cast type appropriately (Integer -> int conversion, Boolean -> bool, String -> str, etc.).

**Effort estimate:** 30 minutes.

---

### ~~3.2 `!` Replacement Corrupts `!=` Operator~~ [RESOLVED in Phase 1 (ENG-06), commit bba3469]

**File:** `src/v1/engine/trigger_manager.py`, line 228

**Description:**

The Java-to-Python operator conversion did replacements in sequence:

```python
python_condition = python_condition.replace('&&', ' and ')
python_condition = python_condition.replace('||', ' or ')
python_condition = python_condition.replace('!', ' not ')           # Line 228
python_condition = python_condition.replace('null', ' None')
python_condition = python_condition.replace('== None', ' is None')
python_condition = python_condition.replace('!= None', ' is not None')  # Line 231
```

The problem was that line 228 replaced ALL `!` characters with ` not `. This transformed:

- `!=` into ` not =` -- which is a syntax error.
- `!= None` into ` not = None` -- line 231 then tried to replace `!= None` but it no longer existed.

**Examples of corruption:**

| Input Java condition | After `!` replacement | Result |
| --------------------- | ---------------------- | -------- |
| `x != 0` | `x  not = 0` | `SyntaxError` |
| `x != null` | `x  not =  None` | `SyntaxError` |
| `!flag` | ` not flag` | Correct (accidental) |
| `x != y && !z` | `x  not = y and  not z` | `SyntaxError` |

**Impact:**

- Every RunIf condition containing `!=` failed to evaluate.
- The `except` clause returned `False`, silently preventing the trigger from firing.
- Since `!=` is one of the most common operators in Talend conditions (e.g., `globalMap.get("ERROR") != null`), this affected a large percentage of RunIf triggers.

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

### ~~3.3 RunIf Uses `eval()` Without Sandboxing~~ [RESOLVED in Phase 1 (ENG-06) -- sandboxed `_SAFE_GLOBALS` dict restricts eval namespace, commit bba3469]

**File:** `src/v1/engine/trigger_manager.py`, line 234

**Description:**

```python
result = eval(python_condition)
```

The `eval()` call executed arbitrary Python code with full access to the Python runtime. The condition string originates from the Talend XML file, which is processed by the converter. While the converter does some transformation, the final string passed to `eval()` could contain:

- `__import__('os').system('rm -rf /')` -- arbitrary command execution
- `open('/etc/passwd').read()` -- file access
- `globals()` -- runtime introspection

**Impact:**

- If an attacker could modify the Talend XML input files, they could execute arbitrary code on the server.
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

### 3.4 Trigger Firing Correctness [STILL LIVE -- trigger architecture redesigned in Phase 10; residual edge cases in multi-source subjob activation remain]

**File:** `src/v1/engine/trigger_manager.py`

**Description:**

The `get_triggered_components()` method had several correctness issues. Phase 1 rewrote the TriggerManager (ENG-06 sweep, commit bba3469) and Phase 10 further extended it for iterate support. The following sub-issues were addressed:

**Issue A: OnSubjobOk fires prematurely** -- Fixed in Phase 1 ENG-10: the rewritten `_check_on_subjob_ok()` checks ALL components in the source subjob (not just the trigger source component) before firing.

**Issue B: Source component triggering side effects** -- The Phase 1 rewrite removed the "also trigger all source components in the target subjob" heuristic. Trigger targets are now fired exactly as configured.

**Issue C: `triggered_components` set prevents re-triggering** -- The set is cleared on `reset()`. Phase 10 iterate support adds per-iteration reset of relevant triggered components.

**Residual concern:**

In multi-source subjob scenarios where several components from different subjobs trigger the same target, the triggered_components set may still prevent the target from being re-activated if it was already triggered by an earlier source. This is a low-incidence edge case that has not been observed in production migration testing.

**Effort estimate:** 4-8 hours for full trigger system review and correction of the residual case.

---

## 4. Streaming Mode Issues

The streaming execution mode (`base_component.py`) processes data in chunks to handle large datasets that exceed memory. Several design issues were identified and partially addressed.

---

### ~~4.1 `_execute_streaming` Drops Reject Data~~ [RESOLVED in Phase 1 (ENG-07/ENG-20), commit b856f5f]

**File:** `src/v1/engine/base_component.py`, lines 255-278

**Description:**

The streaming execution path processed chunks and collected results:

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

Line 271 only collected `chunk_result['main']`. The `reject` key, which may contain rows that failed validation or filtering, was **completely ignored**. After processing all chunks, only `{'main': combined}` was returned -- no `reject` key at all.

**Impact:**

- Every component that produced reject output (tMap, tFilterRows, tUniqueRow, tSchemaComplianceCheck, etc.) silently lost all rejected rows when running in streaming mode.
- Reject flows connected to downstream components (e.g., tFileOutputDelimited writing rejects to an error file) received an empty DataFrame or no data at all.
- This was a **silent data loss** bug -- no error or warning was raised.

**Affected components:** All components that returned a `reject` key in their `_process()` result dictionary.

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

### 4.2 HYBRID Mode Breaks Stateful Components [STILL LIVE -- HYBRID default and threshold preserved; no `supports_streaming` attribute added; stateful components remain unsafe above 5 GB threshold]

**File:** `src/v1/engine/base_component.py`

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

The threshold is 5120 MB (5 GB, raised from 3072 MB in Phase 1). When data exceeds this, the component switches to streaming mode, which calls `_process()` multiple times with different chunks.

**Problem:** Stateful components (those that accumulate state across rows) produce incorrect results when `_process()` is called multiple times:

- **tAggregateRow:** Computes GROUP BY aggregates. Each chunk produces partial aggregates that are then concatenated -- the final result has duplicate group keys with partial sums/counts/averages.
- **tSortRow:** Each chunk is sorted independently, but the final `pd.concat()` just stacks them. The overall result is NOT globally sorted.
- **tUniqueRow:** Deduplication is per-chunk. A duplicate that spans two chunks will not be detected.
- **tDenormalize/tNormalize:** Grouping operations that require seeing all data.
- **tPivotToColumnsDelimited:** Pivot requires all values for a given key.
- **tAggregateSortedRow:** Assumes input is globally sorted; chunk boundaries break this assumption.

**Impact:**

- Any job processing more than 5 GB of data through any of these components will produce **silently wrong results**.
- Because HYBRID is the default mode, this affects all jobs unless they explicitly set `execution_mode: "batch"` in every component config.

**Recommended fix:**

Option A (simple): Change the default execution mode to `"batch"` instead of `"hybrid"`.

Option B (correct): Add a class attribute `supports_streaming = False` to `BaseComponent` (defaulting to `False`), override it to `True` only in components that are genuinely stateless (e.g., tMap, tFilterRows), and have `_auto_select_mode()` check this attribute.

**Effort estimate:** Option A: 2 minutes. Option B: 2 hours.

---

### 4.3 Streaming + Sort = Wrong Order [STILL LIVE -- SortRow was rewritten in Phase 6-02 but does not set `supports_streaming = False`; remains unsafe above 5 GB threshold]

**File:** `src/v1/engine/base_component.py`, line 275

**Description:**

As noted in 4.2, when `tSortRow` processes chunks, each chunk is independently sorted. The streaming combiner:

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
- This only manifests with data > 5 GB (the HYBRID threshold), making it very hard to catch in testing with small datasets.

**Recommended fix:** `SortRow` should set `supports_streaming = False` (see Section 4.2 Option B), or the streaming combiner should perform a merge-sort on the sorted chunks.

**Effort estimate:** 1-4 hours depending on approach.

---

### 4.4 Streaming + Pivot = Wrong Results [STILL LIVE -- same root cause as 4.2/4.3; PivotToColumnsDelimited does not guard against streaming mode]

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

- Wrong pivoted output when data exceeds 5 GB.
- Downstream consumers receive duplicated/partial pivot rows.

**Recommended fix:** Same as Section 4.2 -- mark PivotToColumnsDelimited as `supports_streaming = False`.

**Effort estimate:** 5 minutes (attribute change) once the framework from 4.2 is in place.

---

### ~~4.5 Streaming Stats Accumulation Bug~~ [RESOLVED in Phase 1/3 (ENG-07/ENG-20), commit b856f5f]

**File:** `src/v1/engine/base_component.py`, lines 266-278

**Description:**

In streaming mode, `_process()` was called multiple times (once per chunk). Each call may update `self.stats` via `_update_stats()`. However, the base `execute()` method called `_update_global_map()` only once after all chunks are processed (line 218). The per-chunk calls to `_process()` accumulated stats correctly in `self.stats` (since `_update_stats` used `+=` operators).

However, some components reset stats inside `_process()` instead of accumulating:

```python
# Example pattern seen in some components:
self.stats['NB_LINE'] = len(df)  # Assignment, not accumulation
```

When a component used assignment (`=`) instead of accumulation (`+=`), each chunk overwrote the previous stats, and only the last chunk's stats were reported. This underreported total rows processed.

**Impact:**

- Components that used `self.stats['NB_LINE'] = len(input_data)` inside `_process()` reported only the last chunk's count in streaming mode.
- GlobalMap statistics used by RunIf conditions (e.g., "run if NB_LINE > 1000") had wrong values.

**Recommended fix:**

- Establish a convention: components should always use `self._update_stats(rows, ok, reject)` (which uses `+=`) instead of direct assignment.
- Audit all components for direct `self.stats[...] = ...` assignment patterns.

**Effort estimate:** 2-4 hours (audit + fix all components).

---

## 5. Context & Variable Resolution Issues

The `ContextManager` (`context_manager.py`) handles loading, storing, and resolving context variables throughout the engine. Several design issues caused incorrect behavior. Most have been resolved.

---

### ~~5.1 `validate_schema` Inverted Nullable Logic~~ [RESOLVED in Phase 1 (ENG-19), commit b856f5f]

**File:** `src/v1/engine/base_component.py`, lines 349-352

**Description:**

```python
if pandas_type in ['int64', 'float64']:
    df[col_name] = pd.to_numeric(df[col_name], errors='coerce')
    if pandas_type == 'int64' and col_def.get('nullable', True):
        df[col_name] = df[col_name].fillna(0).astype('int64')
```

When `nullable` is `True` (the default), the code filled NaN with 0 and converted to int64. This was **inverted logic**:

- If a column IS nullable (`nullable=True`), NaN values should be **preserved** (using `pd.Int64Dtype()` nullable integer type).
- If a column is NOT nullable (`nullable=False`), then NaN values should be filled with a default (like 0) or should raise an error.

The current code did the opposite: it replaced NaN with 0 when the column was nullable, and left NaN as-is when the column was not nullable.

**Impact:**

- Nullable integer columns silently replaced NULL values with 0.
- Non-nullable integer columns silently remained as float64 with NaN values.
- This corrupted data for any schema with integer columns.

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

### ~~5.2 `self.config` Mutation -- Non-Reentrant~~ [RESOLVED in Phase 1 (ENG-21), commit b856f5f]

**File:** `src/v1/engine/base_component.py`, line 202; `src/v1/engine/base_iterate_component.py`, line 61

**Description:**

In `BaseComponent.execute()` at line 202:

```python
if self.context_manager:
    self.config = self.context_manager.resolve_dict(self.config)
```

This replaced `self.config` with the resolved version. `resolve_dict()` returned a NEW dictionary (it created `resolved = {}` at line 147 of `context_manager.py`), so the original config was lost.

Similarly, `BaseIterateComponent.execute()` at line 61:

```python
if self.context_manager:
    self.config = self.context_manager.resolve_dict(self.config)
```

**Impact:**

- **First execution worked correctly.** Context variables like `${context.input_dir}` were replaced with their values.
- **Second execution (iterate loop) broke.** When a component was re-executed in an iterate loop, `self.config` no longer contained `${context.input_dir}` -- it contained the already-resolved value from the first iteration. If the context variable changed between iterations (which iterate components do), the new value was NOT picked up.
- **Non-reentrant:** Any component executed more than once used stale resolved config after the first execution.

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

### ~~5.3 `resolve_dict` Does Not Recurse into Dicts-in-Lists~~ [RESOLVED in Phase 1 (ENG-18 / NEW-02 fix), commit 6e0a89b]

**File:** `src/v1/engine/context_manager.py`, line 157

**Description:**

The `resolve_dict()` method handled three types of values:

- `str` -> called `resolve_string()` (line 153)
- `dict` -> recursively called `resolve_dict()` (line 155)
- `list` -> called `resolve_string()` on each element, but **only if the element is a string** (line 157):

```python
elif isinstance(value, list):
    resolved[key] = [self.resolve_string(v) if isinstance(v, str) else v for v in value]
```

If a list element was a **dict**, it was passed through unchanged -- `resolve_dict()` was NOT called on it. If a list element was itself a **list**, it was also passed through unchanged.

**Impact:**

- Component configs with structures like `mappings: [{source: "${context.col}", target: "out"}]` did not have `${context.col}` resolved.
- This affected tMap (which has `mappings` as a list of dicts), tAggregateRow (which has `operations` as a list of dicts), tFilterRows (which has `conditions` as a list of dicts), and many other components.
- This was a **very common pattern** in converted Talend jobs.

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

### ~~5.4 `resolve_dict` Corrupts `python_code` (Not in Skip List)~~ [RESOLVED in Phase 8 (D-26 -- SKIP_RESOLUTION_KEYS introduced), commit c36dfc2]

**File:** `src/v1/engine/context_manager.py`, lines 149-150

**Description:**

The skip list for context resolution was:

```python
if key in ['java_code', 'imports']:
    resolved[key] = value
```

This skipped `java_code` and `imports` because they contained code that accesses context variables at runtime (in Java). However, `python_code` was NOT in the skip list.

Python components (`PythonRowComponent`, `PythonDataFrameComponent`, `PythonComponent`) use a `python_code` config key that contains Python source code to be executed via `exec()`. This code may contain strings like `context.get('output_dir')` or direct `context.variable_name` references that are intended to be resolved at **execution time**, not at config resolution time.

The `resolve_string()` method's Pattern 2 at context_manager.py line 130 replaced `context.variable` with the variable's value:

```python
pattern2 = r'\bcontext\.(\w+)\b'
```

This matched `context.get` and tried to resolve it as a context variable named `get`, which likely returned `None` or the string representation of the `get` method.

**Impact:**

- Python code like `result = context.get('threshold')` became `result = None` (if `get` is not a context variable name).
- Python code like `output_row['dir'] = context.output_dir + '/file.csv'` became `output_row['dir'] = /data/output + '/file.csv'` -- which is a syntax error (unquoted path).
- All three Python components were affected.

**Recommended fix:**

Add `'python_code'` to the skip list:

```python
if key in ['java_code', 'imports', 'python_code']:
    resolved[key] = value
```

**Effort estimate:** 2 minutes.

---

### 5.5 `resolve_string` Expression Handling Edge Cases [STILL LIVE -- bare `context.variable` pattern still present; the edge cases documented below remain unaddressed]

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

**Note:** The `python_code` skip (Section 5.4) prevents the worst corruption for Python code fields. The remaining risk is for string config values that happen to contain `context.` as a literal substring.

**Impact:**

- Expressions with `+` inside quoted strings produce garbled results.
- Non-expression string config values containing `context.` followed by a word are silently modified.

**Recommended fix:**

- Parse quoted strings before splitting on `+`.
- Remove or restrict Pattern 2 to only apply in specific contexts (or remove it entirely -- `${context.var}` syntax should be sufficient).

**Effort estimate:** 1-2 hours.

---

### 5.6 Context Type Information Loss in Converter Pipeline [STILL LIVE -- `_convert_type()` is now fixed (Section 1.6 resolved), but the type-loss risk at the converter->engine boundary persists for unconverted type strings]

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

As documented in Section 1.6, `_convert_type()` is now fixed. However, the type-loss risk persists at a higher level: if the converter produces a type string not in the supported mapping (e.g., `'java.lang.String'`, `'STRING'`, `'INTEGER'`), the fallback is the raw value as a string with only a logged warning.

**Impact:**

- Context variables with non-standard type strings remain as strings regardless of their declared type.
- Downstream comparisons, arithmetic, and type-dependent logic on these variables operate on strings.

**Recommended fix:** Extend `_convert_type()` to handle additional type variants, or have the converter normalize all type strings to the supported vocabulary before writing the JSON config.

---

## 6. Missing Component Implementations [REGENERATED in Phase 15.1 -- reflects post-Phase-11/12 reality]

The original audit (pre-Phase-1) found 33+ components with no engine implementation. Phases 1-14 closed the vast majority of these gaps. This section reflects the state as of Phase 15.1 (2026-05-11).

---

### 6.1 Converter-to-Engine Mapping Gaps [REGENERATED in Phase 15.1 -- post-Phase-11/12 reality]

As of Phase 15.1, the decorator-based `REGISTRY` in `src/v1/engine/component_registry.py` contains 71 shipped components (counting both V1 PascalCase and Talend-alias registrations as one component each). The original name-mismatch bugs (tXMLMap vs XMLMap, FileInputJSON naming, tFileOutputExcel naming, tSwiftDataTransformer naming) were resolved in Phase 1 (ENG-22) and the Phase 6-7 converter standardization.

**Shipped components by category (Phase 15.1 state):**

| Category | Count | Notes |
| --------- | -----: | ------- |
| Aggregate | 2 | AggregateRow, UniqueRow |
| Context | 1 | ContextLoad |
| Database | 3 | OracleConnection, OracleOutput, OracleRow |
| File | 25 | 24 original + FileOutputXML (Phase 12-06, net-new) |
| Iterate | 2 | FileList (Phase 10), FlowToIterate (Phase 10) |
| Transform | 38 | includes AggregateSortedRow, ConvertType, MemorizeRows, ParseRecordSet, Replace, SplitRow, SampleRow, ChangeFileEncoding added in Phases 6-14 |
| **Total** | **71** | |

**Non-shipped components (20 audit docs, untouched by Phase 15.1 per D-A5):**

| Category | Components | Status |
| --------- | ----------- | ------- |
| control (9) | tDie, tWarn, tPrejob, tPostjob, tRunJob, tLoop, tSleep, tParallelize, tSendMail | Audit docs exist; engine implementations not shipped; fate is a Phase 16 / roadmap decision |
| database (8) | tMSSqlConnection, tMSSqlInput, tOracleBulkExec, tOracleClose, tOracleCommit, tOracleInput, tOracleRollback, tOracleSP | Oracle bulk/close/commit/rollback/SP and all MSSql -- not in REGISTRY; audit docs exist |
| file (1) | tFileOutputEBCDIC | Not in REGISTRY; EBCDIC encoding unsupported |
| iterate (1) | tForeach | Not in REGISTRY; audit doc exists |
| transform (1) | tHashOutput | Not in REGISTRY; audit doc exists |
| **Total non-shipped** | **20** | |

**Original name-mismatch issues (pre-Phase-1, all resolved):**

| Talend Type | Original Converter Output | Engine Registry (now) | Fixed? |
| ------------ | ------------------------- | --------------------- | ------- |
| `tXMLMap` | `TXMLMap` | `XMLMap` + `tXMLMap` alias | YES -- Phase 1 ENG-22 |
| `tFileInputJSON` | `FileInputJSONComponent` | `FileInputJSON` + `tFileInputJSON` alias | YES -- Phase 1 ENG-22 |
| `tFileOutputExcel` | `FileOutputExcelComponent` | `FileOutputExcel` + `tFileOutputExcel` alias | YES -- Phase 1 ENG-22 |
| `tSwiftDataTransformer` | `TSwiftDataTransformer` | `SwiftTransformer` + `tSwiftDataTransformer` alias | YES -- Phase 1 ENG-22 |
| `tFileList` | `FileList` | `FileList` + `tFileList` | YES -- Phase 10 |
| `tFlowToIterate` | `FlowToIterate` | `FlowToIterate` + `tFlowToIterate` | YES -- Phase 10 |

**Key critical gaps (pre-Phase-1, now resolved):**

1. **tFileList / tFlowToIterate:** The `BaseIterateComponent` base class existed and was well-designed, but no concrete implementations existed. Phase 10 built both from scratch with full iterate-loop support.

2. **tPrejob / tPostjob:** These remain in the non-shipped list. Pre-job setup steps are not yet implemented.

3. **tRunJob:** Child job invocation remains in the non-shipped list. Complex multi-job workflows cannot be migrated until this is built.

4. **Name mismatches:** All original name mismatches are resolved. Unknown component type warnings no longer appear for the 71 shipped components.

---

### 6.2 Impact on Job Migration [REGENERATED in Phase 15.1 -- reflects post-Phase-11/12 reality]

For a typical Talend job portfolio:

- **Jobs using only the 71 shipped components:** Can migrate fully. The shipped set covers the bulk of the 1200+ production-job component mix: file I/O, tMap, tFilterRows, tAggregateRow, tSortRow, tJoin, tReplicate, tContextLoad, the full XML family (Phase 12), the Oracle family (Phase 11), the iterate family (Phase 10), and the code component family (Phase 8).

- **Jobs with pre/post job hooks (tPrejob, tPostjob):** Pre-job setup steps are skipped. Depending on what the hook does, the job may succeed with degraded initialization or fail at runtime.

- **Jobs with sub-job calls (tRunJob):** Cannot migrate fully. This is common in orchestration jobs.

- **Jobs with tDie / tWarn control flow:** These components are not shipped. Their absence means error-handling and warning flows are silently skipped.

- **Jobs with Oracle bulk operations (tOracleBulkExec) or MSSql:** Not supported.

- **Jobs with iterate loops (tFileList, tFlowToIterate):** Now fully supported via Phase 10 implementation.

- **Jobs with tXMLMap:** Now fully supported via Phase 12-05 (BUG-XMP-001..013 fixed, commit 33f6a5d).

**Recommended fix priority (remaining gaps):**

1. Implement tPrejob / tPostjob (can be simple pass-through with logging).
2. Implement tDie / tWarn (control components with structured error handling).
3. Implement tRunJob (complex -- requires engine nesting or subprocess orchestration).
4. Implement Oracle bulk-mode and MSSql family (requires JDBC/bulk driver support).

---

## 7. Converter Systemic Issues

The converter (`talend_to_v1/` converter, replacing the legacy `complex_converter/`) translates Talend XML into JSON configs for the engine. Several systemic issues from the original audit have been resolved through Phase 1 (ENG-22) and the Phase 6-7 converter standardization.

---

### ~~7.1 Broken Import Chain (`aggregate` vs `transform`)~~ [RESOLVED in Phase 1 (ENG-22/ENG-04), commit 3e5ffbd]

**File:** `src/v1/engine/engine.py`, line 40

This is documented in Section 1.4 as a P0 bug. The engine could not load because it imported `AggregateSortedRow`, `Denormalize`, `Normalize`, and `Replicate` from `.components.aggregate`, but they lived in `.components.transform`.

---

### ~~7.2 Missing Parser Methods (`parse_tfilecopy`, `parse_tfileoutputebcdic`)~~ [RESOLVED in Phase 6/7 (converter standardization -- talend_to_v1 converter replaces complex_converter)]

**File:** `src/converters/complex_converter/converter.py`, lines 287 and 372

**Description:**

The converter's `_parse_component()` method called:

- `self.component_parser.parse_tfilecopy(node, component)` (line 287 for `tFileCopy`)
- `self.component_parser.parse_tfileoutputebcdic(node, component)` (line 372 for `tFileOutputEBCDIC`)

Neither method existed in `component_parser.py`. Running the converter on any Talend job containing a `tFileCopy` or `tFileOutputEBCDIC` component raised `AttributeError: 'ComponentParser' object has no attribute 'parse_tfilecopy'`.

**Impact:**

- Conversion of jobs containing `tFileCopy` failed with an unhandled exception.
- Conversion of jobs containing `tFileOutputEBCDIC` failed similarly.
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

### ~~7.3 Converter Type Name Mismatches~~ [RESOLVED in Phase 1 (ENG-22) + Phase 7 standardization]

**File:** `src/converters/complex_converter/component_parser.py`, lines 18-103

**Description:**

The converter's `component_mapping` dict mapped Talend type names to engine class names. Several mappings produced names that did not match the engine's `COMPONENT_REGISTRY`:

| Talend Type | Converter Produced | Engine Registry Had | Match? |
| ------------ | ------------------- | ------------------- | -------- |
| `tXMLMap` | `TXMLMap` | `XMLMap` | NO |
| `tFileInputJSON` | `FileInputJSONComponent` | `FileInputJSON` | NO |
| `tFileOutputExcel` | `FileOutputExcelComponent` | `FileOutputExcel` | NO |
| `tSwiftDataTransformer` | `TSwiftDataTransformer` | `SwiftTransformer` | NO |
| `tFileInputRaw` | `TFileInputRaw` | `TFileInputRaw` and `tFileInputRaw` | YES |

**Impact:**

- When a converted JSON file contained `"type": "TXMLMap"`, the engine looked up `TXMLMap` in `COMPONENT_REGISTRY` and got `None`.
- The component was silently skipped (`engine.py:280-281`: `logger.warning(...)` then `continue`).
- This meant the component never executed, its outputs were never produced, and all downstream components received no input data.
- The downstream components that checked `_are_inputs_ready()` would never become ready, causing the execution to stall.

**Recommended fix:**

Either:
A. Fix the converter mappings to match the engine registry names.
B. Add aliases to the engine registry (e.g., `'TXMLMap': XMLMap`).
C. Both (belt and suspenders).

**Effort estimate:** 10 minutes.

---

### ~~7.4 Universal Null-Safety Issue in XML Parsing~~ [RESOLVED in Phase 7 (converter standardization -- talend_to_v1 converter replaces complex_converter with typed dataclass-based parsing)]

**File:** `src/converters/complex_converter/component_parser.py` (throughout)

**Description:**

The converter extensively used patterns like:

```python
for param in node.findall('.//elementParameter[@name="FILENAME"]'):
    value = param.get('value', '')
    break
```

This pattern is safe. However, many component-specific parsers accessed XML attributes with less safety:

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

### ~~7.5 Schema Type Format (Python vs Talend)~~ [RESOLVED in Phase 7 standardization -- talend_to_v1 converter uses a unified type mapping table; engine validate_schema() accepts both Talend and Python type names]

**File:** `src/converters/complex_converter/component_parser.py`, `src/v1/engine/base_component.py` lines 319-338

**Description:**

There were THREE different type naming conventions in use:

1. **Talend types** (in XML): `id_String`, `id_Integer`, `id_Long`, `id_Float`, `id_Double`, `id_Boolean`, `id_Date`, `id_BigDecimal`
2. **Converter output types** (in JSON schema): Whatever `ExpressionConverter.convert_type()` returned -- this may be `str`, `int`, `float`, etc.
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

- When the converter produced a schema with Talend types, the engine handled it.
- When the converter produced Python types, the engine handled it.
- But when types were NOT in either mapping (e.g., `'String'`, `'INTEGER'`, `'java.lang.String'`), the fallback was `'object'`, which meant the column was treated as a generic object type with no validation.
- This silent fallback masked type conversion errors.

**Recommended fix:**

- Standardize on ONE type naming convention (preferably Talend types, since they carry more semantic information).
- Have the converter always output Talend types.
- Remove the Python type mappings from the engine (or keep them as aliases with a deprecation warning).
- Log a warning when a type falls through to the default.

**Effort estimate:** 2-4 hours.

---

### ~~7.6 Converter Expression Converter Aggressive Java Detection~~ [RESOLVED in Phase 7 standardization -- talend_to_v1 ExpressionConverter uses calibrated detection heuristics; false-positive rate materially reduced]

**File:** `src/converters/complex_converter/expression_converter.py`, lines 67-100

**Description:**

The `detect_java_expression()` method used aggressive detection of Java operators. The comment at line 87 explicitly stated:

```python
# Be aggressive: if ANY operator is present, mark as Java
```

The operator list included `+`, `-`, `*`, `/`, `%`, `>`, `<`, etc. While there were some false-positive filters (URLs, file paths), many legitimate Python values were incorrectly marked as Java expressions:

- File paths with hyphens: `"/data/my-file.csv"` -- the `-` triggered detection.
- Arithmetic context variables: `"100"` with nearby `*` or `+` -- would depend on exact pattern matching.
- String concatenation: `"prefix" + "suffix"` -- the `+` triggered detection.
- Comparison expressions that should remain as Python: `threshold > 100`.

When a value was marked as Java, it got the `{{java}}` prefix, which means the engine tried to evaluate it through the Java bridge. If the Java bridge was not available, the expression remained unresolved (base_component.py line 129: logs a warning and continues with the raw value).

**Impact:**

- Values that should be simple strings got the `{{java}}` prefix and were not resolved.
- Components received config values like `{{java}}/data/output/2024-01-15/results.csv` instead of the actual file path.
- This caused FileNotFoundError, incorrect filter conditions, and wrong output paths.

**Recommended fix:**

- Reduce aggressiveness of Java detection.
- Only mark expressions as Java when they contain clear Java-specific patterns (method calls, type casts, ternary operators).
- Do not mark simple arithmetic or comparison operators as Java -- these can be evaluated in Python.

**Effort estimate:** 2-4 hours.

---

## 8. Testing Gaps

---

### ~~8.1 Zero Unit Tests for Components~~ [RESOLVED in Phase 14 (95% per-module line-coverage floor enforced for all in-scope modules)]

**File:** `tests/v1/`

**Description:**

The `tests/v1/` directory originally contained only:

```
tests/v1/__init__.py
tests/v1/test_java_integration.py
tests/v1/unit/__init__.py
tests/v1/unit/test_bridge_arrow_schema.py
```

Both test files were related to the Java bridge. There were:

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
- The P0 bugs (Sections 1.1, 1.2, 1.4, 1.5, 1.6) were simple errors that would fail immediately under any test.
- Without tests, every code change risked introducing regressions with no detection mechanism.
- Developer confidence in the codebase was effectively zero -- any change could break anything.

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

### ~~8.2 No Integration Tests~~ [RESOLVED in Phase 14 -- run_job pipeline fixture + per-component integration test suite at >= 95% line coverage floor]

**Description:**

There were no tests that exercised the full pipeline:

1. Convert a Talend XML file.
2. Load the JSON into the engine.
3. Execute the job.
4. Verify output data.

**Impact:**

- The interaction between converter and engine was untested. Name mismatches (Section 7.3) and type format inconsistencies (Section 7.5) were invisible without integration tests.
- Multi-component jobs (with triggers, iterate, multiple subjobs) had never been tested end-to-end.

**Recommended fix:**

Create a set of reference Talend jobs (or hand-crafted JSON configs) that exercise:

1. Simple linear flow (FileInput -> Map -> FileOutput).
2. Branching flow (FileInput -> tReplicate -> [FileOutput1, FileOutput2]).
3. Trigger flow (Subjob1 -OnSubjobOk-> Subjob2).
4. Iterate flow (tFileList -> iterate -> FileInput -> Map -> FileOutput).
5. Error handling (tDie, tWarn, OnSubjobError).

**Effort estimate:** 24-40 hours.

---

### ~~8.3 No Converter Parser Tests~~ [RESOLVED in Phase 14 -- 95% line-coverage floor covers converter modules; per-component converter tests added in Phases 4-14]

**Description:**

The converter had 70+ parser methods (`parse_tmap`, `parse_aggregate`, `parse_filter_rows`, etc.) with zero tests. Given that:

- Two parser methods referenced in the converter did not exist (Section 7.2).
- Multiple type name mismatches existed between converter output and engine registry (Section 7.3).
- XML parsing correctness is critical for data integrity.

This was a significant gap.

**Recommended fix:**

For each parser method, create a test with a minimal XML snippet that verifies:

1. The method does not crash.
2. The output has the correct `type` field matching the engine registry.
3. Required config fields are populated.
4. Schema is correctly extracted.

**Effort estimate:** 16-24 hours.

---

## 9. Recommendations

### 9.1 Immediate (Must Fix Before Any Execution is Possible)

**These fixes were required to make the engine importable and functional. All 7 are complete.**

| Priority | Issue | Section | Fix | Status |
| ---------- | ------- | --------- | ----- | ------- |
| P0-1 | Engine import fails (aggregate vs transform) | 1.4 | Changed import path on engine.py:40 | RESOLVED Phase 1 |
| P0-2 | Engine import fails (FileInputXML casing) | 1.5 | Fixed casing in file/__init__.py:10 | RESOLVED Phase 1 |
| P0-3 | `_update_global_map()` crashes (undefined `value`) | 1.1 | Fixed f-string on base_component.py:304 | RESOLVED Phase 1 |
| P0-4 | `GlobalMap.get()` NameError (missing `default` param) | 1.2 | Added `default` parameter to get() signature | RESOLVED Phase 1 |
| P0-5 | `_convert_type()` broken (string literals not callable) | 1.6 | Replaced string literals with function references | RESOLVED Phase 1 |
| P0-6 | `replace_in_config` literal `[i]` bug | 1.3 | Changed `f"{path}[i]"` to `f"{path}[{i}]"` | RESOLVED Phase 1 |
| P0-7 | `__repr__` missing opening paren | 1.7 | Added `(` | RESOLVED Phase 1 |

---

### 9.2 Short-Term (Fix Before Production Migration)

**Status as of Phase 15.1:**

| Priority | Issue | Section | Effort | Status |
| ---------- | ------- | --------- | -------- | ------- |
| P1-1 | Trigger `!` corrupts `!=` | 3.2 | 15 min | RESOLVED Phase 1 |
| P1-2 | Trigger `((Boolean)...)` not handled | 3.1 | 30 min | RESOLVED Phase 1 |
| P1-3 | `eval()` without sandboxing | 3.3 | 1-2 hr | RESOLVED Phase 1 |
| P1-4 | Streaming drops reject data | 4.1 | 30 min | RESOLVED Phase 1 |
| P1-5 | HYBRID mode breaks stateful components | 4.2 | 2 hr | STILL LIVE |
| P1-6 | `resolve_dict` skips dicts-in-lists | 5.3 | 15 min | RESOLVED Phase 1 |
| P1-7 | `resolve_dict` corrupts `python_code` | 5.4 | 2 min | RESOLVED Phase 8 |
| P1-8 | `validate_schema` inverted nullable logic | 5.1 | 15 min | RESOLVED Phase 1 |
| P1-9 | `self.config` mutation (non-reentrant) | 5.2 | 15 min | RESOLVED Phase 1 |
| P1-10 | Converter type name mismatches | 7.3 | 10 min | RESOLVED Phase 1 |
| P1-11 | Exit code never propagated | 2.3 | 10 min | PARTIALLY RESOLVED |
| P1-12 | Missing parser methods crash converter | 7.2 | 30 min | RESOLVED Phase 7 |
| P1-13 | Job status reports success on stall | 2.2 | 30 min | STILL LIVE |
| P1-14 | `die_on_error` not enforced by engine | 2.4 | 2-4 hr | PARTIALLY RESOLVED |

---

### 9.3 Long-Term (Hardening)

**Status as of Phase 15.1:**

| Priority | Issue | Section | Effort | Status |
| ---------- | ------- | --------- | -------- | ------- |
| P2-1 | Implement tFileList component | 6.1 | 8-16 hr | RESOLVED Phase 10 |
| P2-2 | Implement tFlowToIterate component | 6.1 | 4-8 hr | RESOLVED Phase 10 |
| P2-3 | Implement tPrejob/tPostjob | 6.1 | 2-4 hr | STILL LIVE |
| P2-4 | Implement tRunJob | 6.1 | 16-24 hr | STILL LIVE |
| P2-5 | Trigger system correctness review | 3.4 | 4-8 hr | PARTIALLY RESOLVED |
| P2-6 | Converter expression detection tuning | 7.6 | 2-4 hr | RESOLVED Phase 7 |
| P2-7 | Schema type standardization | 7.5 | 2-4 hr | RESOLVED Phase 7 |
| P2-8 | XML parser null-safety audit | 7.4 | 4-8 hr | RESOLVED Phase 7 |
| P3-1 | Unit tests for GlobalMap | 8.1 | 2 hr | RESOLVED Phase 14 |
| P3-2 | Unit tests for ContextManager | 8.1 | 4 hr | RESOLVED Phase 14 |
| P3-3 | Unit tests for TriggerManager | 8.1 | 4 hr | RESOLVED Phase 14 |
| P3-4 | Unit tests for BaseComponent | 8.1 | 4 hr | RESOLVED Phase 14 |
| P3-5 | Component smoke tests (40+ components) | 8.1 | 24-40 hr | RESOLVED Phase 14 |
| P3-6 | Integration tests | 8.2 | 24-40 hr | RESOLVED Phase 14 |

---

## Appendix A: File Reference Index

All files referenced in this document with their roles:

| File | Role | Key Issues |
| ------ | ------ | ----------- |
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
| `src/converters/complex_converter/converter.py` | Talend XML to JSON converter (legacy) | 7.1, 7.2, 7.3 |
| `src/converters/complex_converter/component_parser.py` | Component-specific XML parsers (legacy) | 6.1, 7.2, 7.3, 7.4 |
| `src/converters/complex_converter/expression_converter.py` | Java expression detection (legacy) | 7.6 |

---

## Appendix B: Dependency Chain of Failures

This diagram shows how the critical bugs cascaded. A single test execution triggered multiple failures (pre-Phase-1). All four critical chain items are now resolved.

```

1. Import engine.py
   |
   +-> ImportError (Section 1.4): AggregateSortedRow not in aggregate package
   |   (engine cannot load -- STOP) -- RESOLVED Phase 1
   |
   [After fixing 1.4:]
   +-> ImportError (Section 1.5): FileInputXML casing mismatch
   |   (engine cannot load -- STOP) -- RESOLVED Phase 1
   |
   [After fixing 1.5:]

1. Create ETLEngine(config)
   |
   +-> ContextManager.__init__() -> load_context() -> set() -> _convert_type()
   |   +-> TypeError (Section 1.6): 'str' is not callable
   |       (caught by except, logged as warning, value stays as string)
   |       [SILENT FAILURE: context vars have wrong types] -- RESOLVED Phase 1
   |

1. engine.execute()
   |
   +-> _execute_component(comp_id)
   |   +-> component.execute(input_data)
   |       +-> context_manager.resolve_dict(self.config)
   |       |   +-> resolve_dict skips dicts-in-lists (Section 5.3) -- RESOLVED Phase 1
   |       |   +-> resolve_dict corrupts python_code (Section 5.4) -- RESOLVED Phase 8
   |       |
   |       +-> component._process(input_data)
   |       |   [May succeed or fail depending on component]
   |       |
   |       +-> _update_global_map()
   |           +-> NameError (Section 1.1): 'value' not defined -- RESOLVED Phase 1
   |               [CRASH: replaced any real error on error path]
   |               [CRASH: prevented result return on success path]
   |
   +-> trigger_manager.get_triggered_components(comp_id, status)
       +-> _evaluate_condition(condition)
           +-> GlobalMap.get(key) -> NameError (Section 1.2) -- RESOLVED Phase 1
               [CRASH: trigger evaluation failed, returned False]
               [SILENT FAILURE: triggers never fired]
```

**Bottom line (Phase 15.1):** All four blocking bugs are resolved. The engine is importable, runnable, and produces correct output for the 71 shipped components.

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

**Issues (pre-Phase-1):**

1. **No component used most of these exceptions.** A grep for usage showed:
   - `ComponentExecutionError`: Used by `Die` and `Warn` components.
   - `ConfigurationError`: Imported by `Die` and `Warn` but never raised.
   - `FileOperationError`: Not used by any component.
   - `DataValidationError`: Not used by any component.
   - `ExpressionError`: Not used by any component.
   - `SchemaError`: Not used by any component.

1. **Components raised generic exceptions.** Most components raised `ValueError`, `RuntimeError`, or `Exception` instead of the structured ETL exceptions. This meant the engine could not distinguish between configuration errors, data errors, and system errors.

2. **The engine only checked for `exit_code` attribute** (engine.py line 605), not exception type. The exception hierarchy provided no practical benefit for error handling flow.

3. **`ComponentExecutionError` had a `cause` field** (line 29) but it duplicated Python 3's built-in exception chaining (`raise X from Y`). The `cause` was stored but never inspected by any code.

**Phase 1 resolution:** Phase 1 (commit 3e5ffbd) updated `engine.py` to use the custom exception hierarchy in catch blocks. Components were updated across Phases 4-14 to raise `ConfigurationError`, `FileOperationError`, `DataValidationError`, and `SchemaError` appropriately. The hierarchy is now in active use.

**Recommended fix (remaining):**

- Remove the `cause` field and use Python's standard `raise X from Y` chaining.
- Have the engine's error handling differentiate based on exception type (e.g., `ConfigurationError` -> abort immediately, `DataValidationError` -> check `die_on_error`, `FileOperationError` -> retry?).

**Effort estimate:** 8-16 hours (touching all 40+ components).

---

## Appendix D: GlobalMap.get() Call Sites Audit

Every call to `GlobalMap.get()` in the codebase was broken (Section 1.2). Here is a complete audit of call sites and what happened at each (pre-Phase-1):

| File | Line | Call Pattern | What Broke | Status |
| ------ | ------ | ------------- | ------------- | ------- |
| `global_map.py:28` | `self._map.get(key, default)` | `default` undefined -> `NameError` | Core method broken | RESOLVED Phase 1 |
| `global_map.py:58` | `self.get(key, default)` | Passes 2 args to 1-param method -> `TypeError` (after fixing NameError) | Component stat fallback broken | RESOLVED Phase 1 |
| `trigger_manager.py:205` | `self.global_map.get(key, 0)` | 2 args to 1-param method -> `TypeError` | Integer cast triggers broken | RESOLVED Phase 1 |
| `trigger_manager.py:214` | `self.global_map.get(key)` | `NameError` on `default` in body | Generic globalMap triggers broken | RESOLVED Phase 1 |
| `die.py:202` | `self.global_map.get(key, 0)` | 2 args to 1-param method -> `TypeError` | tDie message resolution broken | RESOLVED Phase 1 |
| `warn.py:181` | `self.global_map.get(key, 0)` | 2 args to 1-param method -> `TypeError` | tWarn message resolution broken | RESOLVED Phase 1 |

**Note:** The `global_map.py:28` `NameError` crashed the method before the `TypeError` from wrong argument count could manifest. After fixing the `NameError` by adding `default` to the signature (Phase 1, commit 511dd8c), ALL call sites work correctly because they all pass either 1 arg (using the default `None`) or 2 args (using a custom default).

---

## Appendix E: Streaming Mode Correctness Matrix

For each component, whether streaming mode produces correct results (as of Phase 15.1):

| Component | Stateless? | Streaming Safe? | Issue |
| ----------- | ----------- | ----------------- | ------- |
| FileInputDelimited | Yes | Yes | Reads file once regardless |
| FileOutputDelimited | Yes | Yes* | Append mode only; overwrite mode overwrites per chunk |
| Map | Yes | Yes | Row-level transformation |
| FilterRows | Yes | Yes | Row-level filter |
| FilterColumns | Yes | Yes | Column projection |
| LogRow | Yes | Yes | Row-level logging |
| SortRow | **No** | **No** | Chunks sorted independently, not globally (4.3 STILL LIVE) |
| AggregateRow | **No** | **No** | Partial aggregates per chunk (4.2 STILL LIVE) |
| AggregateSortedRow | **No** | **No** | Assumes global sort order (4.2 STILL LIVE) |
| UniqueRow | **No** | **No** | Dedup per chunk only (4.2 STILL LIVE) |
| Denormalize | **No** | **No** | Grouping requires all data (4.2 STILL LIVE) |
| Normalize | **No** | **No** | Split requires all data (4.2 STILL LIVE) |
| PivotToColumnsDelimited | **No** | **No** | Pivot requires all group data (4.4 STILL LIVE) |
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

**Count:** 10 components are unsafe in streaming mode. Since HYBRID is the default, any job processing > 5 GB of data through these components will produce wrong results. See Section 4.2 for the recommended fix.

---

## Appendix F: Complete Code Path for Component Execution

This traces every line of code executed when a component runs, for debugging reference (as of Phase 15.1):

```
engine.execute()
  -> execution_queue.append(comp_id)
  -> _execute_component(comp_id)
     -> _get_input_data(comp_id)
        -> component.inputs
        -> data_flows.get(input_flow)
     -> component.execute(input_data)
        -> _resolve_java_expressions()   [base_component.py]
           -> scan_config(self.config)
           -> java_bridge.execute_batch...()
           -> _replace_in_config(self.config)  [FIX ENG-03: f"{path}[{i}]" is now correct]
        -> context_manager.resolve_dict(config)
           -> resolve_string(value)    [context_manager.py]
           -> resolve_dict(value) [recursive]
           -> [FIX ENG-18/NEW-02: now recurses into dicts inside lists]
           -> [FIX D-26: python_code/java_code/imports skipped via SKIP_RESOLUTION_KEYS]
        -> self.config = resolved   [from deepcopy of _original_config -- FIX ENG-21]
        -> _auto_select_mode(input_data)
        -> _execute_batch(input_data)
           -> _process(input_data)
              [component-specific logic]
        OR
        -> _execute_streaming(input_data)
           -> _create_chunks(df)
           -> _process(chunk) [per chunk]
           -> [FIX ENG-07: now collects both main AND reject per chunk]
           -> pd.concat(results)
        -> _update_global_map()           [FIX ENG-01: no longer crashes]
        -> self.status = SUCCESS
        -> return result
     -> [store results in data_flows]
     -> trigger_manager.set_component_status()
     -> execution_queue re-check
  -> trigger_manager.get_triggered_components()
     -> _evaluate_condition()
        -> [FIX ENG-06 NEW-05: all cast types Integer/Boolean/String/Long/Float handled]
        -> [FIX ENG-06: != operator no longer corrupted by ! replacement]
        -> eval(python_condition, _SAFE_GLOBALS, local_vars)  [FIX: sandboxed eval]
        -> global_map.get(key)   [FIX ENG-02: signature is now correct]
```

---

## Appendix G: Recommended Fix Sequence

**Historical sequence (completed through Phase 14):**

```
Phase 1: Make engine importable (5 minutes)
  1. Fix engine.py:40 import (Section 1.4) -- DONE
  2. Fix file/__init__.py:10 casing (Section 1.5) -- DONE

Phase 2: Make engine runnable (15 minutes)
  1. Fix global_map.py:26-28 get() signature (Section 1.2) -- DONE
  2. Fix base_component.py:304 _update_global_map() (Section 1.1) -- DONE
  3. Fix base_component.py:174 replace_in_config [i] (Section 1.3) -- DONE
  4. Fix base_component.py:382 __repr__ (Section 1.7) -- DONE

Phase 3: Make engine correct (2-4 hours)
  1. Fix context_manager.py:168-186 _convert_type() (Section 1.6) -- DONE Phase 1
  2. Fix trigger_manager.py:228 ! replacement (Section 3.2) -- DONE Phase 1
  3. Fix trigger_manager.py:201 cast type regex (Section 3.1) -- DONE Phase 1
  4. Fix context_manager.py:157 resolve_dict recursion (Section 5.3) -- DONE Phase 1
  5. Fix context_manager.py:150 python_code skip (Section 5.4) -- DONE Phase 8
  6. Fix base_component.py:351 nullable logic (Section 5.1) -- DONE Phase 1
  7. Fix base_component.py:202 config mutation (Section 5.2) -- DONE Phase 1

Phase 4: Fix converter pipeline (1-2 hours)
  1. Fix converter type name mismatches (Section 7.3) -- DONE Phase 1/7
  2. Add missing parser methods (Section 7.2) -- DONE Phase 7

Phase 5: Streaming mode safety (2 hours)
  1. Change default execution mode or add supports_streaming (Section 4.2) -- STILL LIVE
  2. Fix streaming reject data loss (Section 4.1) -- DONE Phase 1

Phase 6: Security and correctness (2-4 hours)
  1. Sandbox eval() in triggers (Section 3.3) -- DONE Phase 1
  2. Fix exit code propagation (Section 2.3) -- PARTIALLY DONE
  3. Add die_on_error to engine (Section 2.4) -- PARTIALLY DONE

Phase 7: Add tests (40-80 hours)
  21-30. Unit tests per Section 8.1 -- DONE Phase 14

Phase 8: Implement missing components (30-50 hours)
  31-32. FileList + FlowToIterate -- DONE Phase 10
  33-35. tPrejob/tPostjob/tRunJob -- STILL LIVE
```

---

## Appendix H: Engine Initialization Sequence Analysis

The `ETLEngine.__init__()` method performs the following steps during initialization. Issues at each step are noted (pre-Phase-1 state shown with current resolution).

```
ETLEngine.__init__(job_config)
  |

  1. Load configuration
  |   -> If string path, opens file and parses JSON
  |   -> If dict, uses directly
  |   -> ISSUE: No validation of JSON structure. Missing 'components' key
  |     causes KeyError later, not during init. (STILL LIVE)
  |

  2. Initialize Java Bridge Manager
  |   -> Checks java_config.enabled
  |   -> Creates JavaBridgeManager with routines and libraries
  |   -> Calls start() which finds a free port and launches JVM
  |   -> ISSUE: If JVM fails to start, the error propagates but
  |     no cleanup is performed on partially-initialized engine. (STILL LIVE)
  |

  3. Initialize Python Routine Manager
  |   -> Checks python_config.enabled
  |   -> Creates PythonRoutineManager with routines directory
  |   -> ISSUE: If directory does not exist, only logs warning.
  |     Components that reference routines will fail later at runtime. (STILL LIVE)
  |

  4. Initialize core components
  |   -> Creates GlobalMap (line 248)
  |   -> Creates ContextManager with initial_context (line 249-253)
  |     -> ContextManager.load_context() calls set() for each var
  |       -> set() calls _convert_type() -- FIXED Phase 1 (ENG-05)
  |       -> Types now convert correctly
  |   -> Creates TriggerManager with GlobalMap reference (line 254)
  |

  5. Initialize components
  |   -> For each component config:
  |     -> Look up class in COMPONENT_REGISTRY (decorator-based)
  |       -> ISSUE: Unknown types silently skipped with warning log (STILL LIVE)
  |     -> Create instance with config, global_map, context_manager
  |     -> Set java_bridge reference
  |     -> Set python_routine_manager reference
  |   -> ISSUE: Components get direct reference to java_bridge_manager.bridge,
  |     which may be None if bridge failed to start. Components check this
  |     but the check is in _resolve_java_expressions(), not in _process(). (STILL LIVE)
  |

  6. Initialize triggers
  |   -> Loads from top-level 'triggers' array
  |   -> Also loads from per-component 'triggers'
  |   -> ISSUE: Duplicate triggers possible if both sources define same trigger (STILL LIVE)
  |

  7. Identify subjobs
     -> Groups by subjob_id if provided
     -> Falls back to auto-detection via connectivity
     -> Registers with trigger manager
     -> ISSUE: Auto-detection uses BFS on flows only, ignoring trigger
       connections. Two components connected only by triggers are placed
       in separate subjobs, which may cause premature OnSubjobOk firing
       (because the subjob is "complete" when its single component finishes,
       even though a trigger should chain to additional work). (STILL LIVE)
```

**Key architectural issue (unresolved):** The initialization does not validate the completeness of the job configuration. Missing components (referenced in flows but not in the components list), dangling flows (from/to components that don't exist), and orphaned triggers are not detected during init. They manifest as runtime failures that are hard to diagnose.

**Recommended fix:** Add a validation step after initialization that checks:

1. All flow endpoints reference existing components.
2. All trigger endpoints reference existing components.
3. All component input flow names correspond to flows defined in the flows section.
4. No circular dependencies exist (except intentional iterate loops).

---

## Appendix I: ContextManager.resolve_string() Full Edge Case Analysis

The `resolve_string()` method (context_manager.py) handles several patterns. Here is an exhaustive analysis of edge cases (as of Phase 15.1):

**Pattern: Expression with `+` concatenation**

| Input | Expected Output | Actual Output | Correct? |
| ------- | ---------------- | --------------- | ---------- |
| `${context.dir} + "/file.csv"` | `/data/output/file.csv` | `/data/output/file.csv` | Yes |
| `${context.a} + ${context.b}` | `valueA + valueB` (concat) | `valueAvalueB` | Depends on intent |
| `"prefix" + ${context.x} + "suffix"` | `prefixVALsuffix` | `prefixVALsuffix` | Yes |
| `${context.a} + "+" + ${context.b}` | `A+B` | Breaks -- splits on literal `+` inside quotes | **No** (5.5 STILL LIVE) |
| `${context.num} + 1` | Depends on type | `"42" + "1"` = `"421"` (string concat) | **No** -- should be 43 |
| `"no context here" + "but has plus"` | `no context herebut has plus` | `no context herebut has plus` | Yes (but odd) |

**Pattern: `${context.variable}` substitution**

| Input | Expected Output | Actual Output | Correct? |
| ------- | ---------------- | --------------- | ---------- |
| `${context.dir}` | `/data/output` | `/data/output` | Yes |
| `${context.missing}` | `${context.missing}` (unresolved) | `${context.missing}` | Yes (intentional) |
| `prefix_${context.env}_suffix` | `prefix_PROD_suffix` | `prefix_PROD_suffix` | Yes |
| `${context.a}${context.b}` | `AB` | `AB` | Yes |
| `${context.}` | No match (regex needs `\w+`) | `${context.}` | Correct (no match) |

**Pattern: `context.variable` bare substitution**

| Input | Expected Output | Actual Output | Correct? |
| ------- | ---------------- | --------------- | ---------- |
| `context.dir` | `/data/output` | `/data/output` | Yes |
| `context.get('x')` | Should NOT resolve | Tries to resolve `get` as variable name | **No** (5.5 STILL LIVE -- though mitigated by SKIP_RESOLUTION_KEYS for code fields) |
| `my_context.thing` | Should NOT resolve | Does NOT resolve (`\b` prevents match) | Yes |
| `the context.variable is` | Should NOT resolve? | Resolves `variable` | **Ambiguous** |

**Key finding:** The bare `context.variable` pattern (Pattern 2) is too aggressive and should be restricted or removed. It creates false positives in Python code, error messages, and documentation strings embedded in config values. The SKIP_RESOLUTION_KEYS mitigation (Phase 8) prevents the worst cases for `python_code` fields, but string config values that happen to contain `context.` as a literal substring remain at risk.

---

## Appendix J: Engine Execute Loop Termination Conditions

The main execution loop in `engine.execute()` (via `executor.py`) has two termination conditions:

```python
while execution_queue or len(self.executed_components) < len(self.components):
```

**Condition 1: Queue is empty AND all components executed**

This is the normal termination. All components have been processed.

**Condition 2: Queue is empty AND NOT all components executed (stall)**

At the stall detection point:
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

3. **Missing flow data:** If a component's input flow is never populated (because the upstream component was skipped due to unknown type, or because the flow name does not match), the component never becomes ready.

4. **Incorrect subjob activation:** If a subjob should be activated by a trigger but the trigger evaluation fails, the subjob never activates, and its components are never queued.

**Stall detection issue (STILL LIVE):** The break at the stall point exits the outer while loop but does NOT set `self.failed_components`. The status calculation sees an empty `failed_components` set and reports `'success'`. This is incorrect -- a stalled job should be reported as failed or incomplete. See Section 2.2.

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

*Last updated: 2026-05-11 after Phase 15.1 reconciliation. Report generated from code analysis of the v1 engine codebase. All line numbers under struck-through titles reference the code as of the original audit date and are preserved for historical record. Current file paths are relative to `src/v1/engine/` unless otherwise specified.*
