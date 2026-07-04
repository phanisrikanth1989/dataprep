---
phase: 01-infrastructure-bug-fixes-project-setup
reviewed: 2026-04-14T12:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - src/v1/engine/base_component.py
  - src/v1/engine/base_iterate_component.py
  - src/v1/engine/context_manager.py
  - src/v1/engine/engine.py
  - src/v1/engine/exceptions.py
  - src/v1/engine/global_map.py
  - src/v1/engine/trigger_manager.py
  - pyproject.toml
  - tests/v1/engine/conftest.py
  - tests/v1/engine/test_base_component.py
  - tests/v1/engine/test_context_manager.py
  - tests/v1/engine/test_global_map.py
  - tests/v1/engine/test_trigger_manager.py
  - docs/v1/standards/ENGINE_COMPONENT_PATTERN.md
  - docs/v1/standards/ENGINE_TEST_PATTERN.md
findings:
  critical: 3
  warning: 6
  info: 5
  total: 14
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-14T12:00:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

The infrastructure layer (base_component, context_manager, global_map, trigger_manager, exceptions) is well-designed with clear separation of concerns, proper use of the template method pattern, and good test coverage. The codebase shows evidence of deliberate bug fixes (ENG-03 through ENG-21) that address real production issues.

However, the review found 3 critical issues, 6 warnings, and 5 informational items. The most severe problem is a missing method call in `engine.py` that will cause an `AttributeError` at runtime during iterate component execution. There is also an absolute import in `trigger_manager.py` that will break when the module is loaded as a relative package, and a missing return path in the cast replacer function.

## Critical Issues

### CR-01: Missing method `update_iteration_stats` on BaseIterateComponent

**File:** `src/v1/engine/engine.py:739`
**Issue:** The engine calls `component.update_iteration_stats(iteration_stats)` on line 739, but this method does not exist on `BaseIterateComponent` or `BaseComponent`. This will raise `AttributeError` at runtime whenever an iterate component completes an iteration. The method is not defined anywhere in the codebase.
**Fix:**
Either add the method to `BaseIterateComponent`:
```python
# In src/v1/engine/base_iterate_component.py
def update_iteration_stats(self, iteration_stats: dict) -> None:
    """Accumulate stats from one iteration into component stats."""
    self.stats["NB_LINE"] += iteration_stats.get("NB_LINE", 0)
    self.stats["NB_LINE_OK"] += iteration_stats.get("NB_LINE_OK", 0)
    self.stats["NB_LINE_REJECT"] += iteration_stats.get("NB_LINE_REJECT", 0)
```
Or use the existing `_update_stats` method in `engine.py`:
```python
component._update_stats(
    rows_read=iteration_stats['NB_LINE'],
    rows_ok=iteration_stats['NB_LINE_OK'],
    rows_reject=iteration_stats['NB_LINE_REJECT'],
)
```

### CR-02: Absolute import in trigger_manager.py will fail under relative package loading

**File:** `src/v1/engine/trigger_manager.py:16`
**Issue:** Uses `from src.v1.engine.exceptions import TriggerEvaluationError` (absolute import from project root) while all other modules in the same package use relative imports (e.g., `from .exceptions import ...`). This inconsistency means `trigger_manager.py` will fail with `ModuleNotFoundError` when loaded via relative import (the standard execution path via `engine.py`), unless `src` is explicitly on `sys.path`. All sibling modules (`base_component.py`, `engine.py`, etc.) use relative imports consistently.
**Fix:**
```python
from .exceptions import TriggerEvaluationError
```

### CR-03: Missing return value in `_cast_replacer` exception handler

**File:** `src/v1/engine/trigger_manager.py:323-329`
**Issue:** The `except (ValueError, TypeError)` block in `_cast_replacer` has conditional `elif` chains for `int/float`, `bool`, and `str` converters, but no final `else` clause. If a future cast type is added to `_JAVA_CAST_MAP` that is not one of these four types, the function will implicitly return `None`, which `re.sub` will raise a `TypeError` on (cannot use `None` as a replacement string). While the current `_JAVA_CAST_MAP` only contains `int`, `float`, `bool`, and `str`, this is a latent bug waiting for a future maintainer to trigger.
**Fix:**
```python
except (ValueError, TypeError):
    if converter in (int, float):
        return "0"
    elif converter is bool:
        return "False"
    else:
        return repr(str(raw_value))
```

## Warnings

### WR-01: Unused variable `source_components` in `_identify_subjobs`

**File:** `src/v1/engine/engine.py:375-378`
**Issue:** The variable `source_components` is computed (list comprehension filtering components with no inputs) but never used. This suggests either incomplete implementation or dead code from a refactor. The variable is computed inside a loop for every subjob but the result is discarded.
**Fix:**
Remove the unused list comprehension:
```python
# Remove lines 375-378
# source_components = [
#     comp_id for comp_id in components
#     if not self.components[comp_id].inputs
# ]
```

### WR-02: `_resolve_global_map_refs` has redundant conditional branches

**File:** `src/v1/engine/trigger_manager.py:337-348`
**Issue:** The `_ref_replacer` function has three branches that all do the same thing (`return repr(value)`): `isinstance(value, str)`, `isinstance(value, bool)`, and the final `else`. While not a bug, this suggests copy-paste development and obscures the actual logic -- every non-None value is simply `repr()`'d.
**Fix:**
```python
def _ref_replacer(match: re.Match) -> str:
    key = match.group(1)
    value = self.global_map.get(key)
    if value is None:
        return "None"
    return repr(value)
```

### WR-03: `_cast_replacer` also has missing return for `None` case with unknown converter type

**File:** `src/v1/engine/trigger_manager.py:312-320`
**Issue:** Similar to CR-03 but in the `raw_value is None` branch: if a converter is not `int`, `float`, `bool`, or `str`, the code falls through without returning, and then tries `converter(raw_value)` which is `converter(None)`. This will likely raise an exception that is caught by the outer handler, but the control flow is unclear and fragile.
**Fix:**
Add a final else clause:
```python
if raw_value is None:
    if converter in (int, float):
        return "0"
    elif converter is bool:
        return "False"
    else:
        return '"None"'
```

### WR-04: `pyproject.toml` uses non-standard build backend path

**File:** `pyproject.toml:3`
**Issue:** The build backend is set to `setuptools.backends._legacy:_Backend`. This is a private, undocumented internal path. The standard setuptools build backend is `setuptools.build_meta`. Using a private API means this could break with any setuptools upgrade without warning.
**Fix:**
```toml
build-backend = "setuptools.build_meta"
```

### WR-05: `engine.py` swallows all exceptions at top level, masking fatal errors

**File:** `src/v1/engine/engine.py:531-547`
**Issue:** The `execute()` method catches a bare `Exception` at lines 531-547 and returns a dict with `status: 'error'` instead of propagating. This means critical errors like `MemoryError`, `KeyboardInterrupt` (though technically `BaseException`), or even bugs in the engine itself (e.g., `AttributeError` from CR-01) are silently converted to a status dict. The caller must check the return value's `status` field to detect failures -- if they forget, the failure is lost. At minimum, `ComponentExecutionError` with `exit_code` (the Die component pattern) should propagate.
**Fix:**
Re-raise exceptions that should not be caught, or at minimum log at ERROR level with traceback:
```python
except Exception as e:
    logger.error(f"Job execution failed: {e}", exc_info=True)
    # Consider: raise for non-recoverable errors
```

### WR-06: `_execute_iterate_component` recursive call to `_execute_component` can mask iterate errors

**File:** `src/v1/engine/engine.py:694`
**Issue:** Inside `_execute_iterate_component`, the method calls `self._execute_component(current_comp_id)` recursively. If that inner component is itself an iterate component (nested iteration), and `_execute_component` checks `isinstance(component, BaseIterateComponent) and result.get('iterate')`, this could lead to unexpected recursive iteration behavior. More importantly, the inner `_execute_component` catches all exceptions (line 611) and returns `'error'` string, but `_execute_iterate_component` also catches exceptions (line 760). The double exception handling makes error propagation paths complex and hard to reason about.
**Fix:**
This is an architectural concern. Consider extracting the iterate loop into a dedicated method that does not re-enter `_execute_component`, or add a guard against nested iterate execution.

## Info

### IN-01: Commented-out database component imports and registry entries

**File:** `src/v1/engine/engine.py:39-41, 193-215`
**Issue:** Large blocks of commented-out code for database components (OracleConnection, OracleClose, OracleInput, etc.). While understandable during phased development, this adds visual noise and makes it harder to scan the registry.
**Fix:** Remove commented-out entries and track them in the roadmap/planning docs instead. When database components are implemented, add them back.

### IN-02: `engine.py` COMPONENT_REGISTRY defined at class level referencing potentially undefined names

**File:** `src/v1/engine/engine.py:67-216`
**Issue:** The `COMPONENT_REGISTRY` dict is defined as a class attribute and references all component classes directly. When component imports fail (lines 24-51), `_COMPONENT_IMPORTS_AVAILABLE` is set to `False`, but `ETLEngine` class definition still references the imported names (e.g., `FileInputDelimited`). If the import failed, this class definition will raise `NameError`. The try/except only guards the imports, not the class body. This is acknowledged in the code comment ("These WILL break until each component is rewritten") but it means the entire `ETLEngine` class is unusable when any component import fails.
**Fix:** Consider using a lazy registry pattern or conditional dict construction guarded by `_COMPONENT_IMPORTS_AVAILABLE`.

### IN-03: `engine.py` sets `logging.basicConfig` at module import time

**File:** `src/v1/engine/engine.py:54`
**Issue:** `logging.basicConfig(level=logging.INFO)` is called at module level, meaning importing the engine module configures the root logger. This can interfere with application-level logging configuration, especially in test environments or when the engine is used as a library.
**Fix:** Move `logging.basicConfig()` into the `__main__` block (line 871) or into `run_job()`.

### IN-04: `_validate_config` in BaseIterateComponent is abstract but `_process` is concrete

**File:** `src/v1/engine/base_iterate_component.py:64-85`
**Issue:** `BaseIterateComponent` implements `_process()` (satisfying the BaseComponent abstract requirement) but `_validate_config()` remains abstract from BaseComponent. The docstring for `_process()` says "The engine's iterate loop consumes them" but the iterate lifecycle doc in `ENGINE_COMPONENT_PATTERN.md` line 539 says "Do NOT implement `_process()`" for iterate components. This is consistent -- `BaseIterateComponent` provides `_process()` so subclasses do not need to. However, subclasses still must implement `_validate_config()`, which is correct but could benefit from a brief note in the class docstring.
**Fix:** Add to the BaseIterateComponent class docstring: "Subclasses must implement `_validate_config()`, `prepare_iterations()`, and `set_iteration_globalmap()`. Do NOT override `_process()`."

### IN-05: Test file `test_trigger_manager.py` imports use absolute path matching production code

**File:** `tests/v1/engine/test_trigger_manager.py:7-9`
**Issue:** Test imports use `from src.v1.engine.trigger_manager import ...` which is the standard absolute import pattern for tests. However, the production `trigger_manager.py` uses `from src.v1.engine.exceptions import TriggerEvaluationError` (absolute) while all other production modules use relative imports. The test works because tests always run with `src` on the path. This is informational context supporting CR-02.
**Fix:** No action needed on the test file -- this is informational context for CR-02.

---

_Reviewed: 2026-04-14T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
