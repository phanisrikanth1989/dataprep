---
phase: 03-execution-loop-restructure
reviewed: 2026-04-14T12:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - src/v1/engine/component_registry.py
  - src/v1/engine/execution_plan.py
  - src/v1/engine/output_router.py
  - src/v1/engine/executor.py
  - src/v1/engine/engine.py
  - src/v1/engine/__init__.py
  - tests/v1/engine/conftest.py
  - tests/v1/engine/test_component_registry.py
  - tests/v1/engine/test_execution_plan.py
  - tests/v1/engine/test_executor.py
  - tests/v1/engine/test_output_router.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-04-14T12:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 3 restructures the engine's execution loop by extracting three new modules: `ComponentRegistry` (decorator-based), `ExecutionPlan` (DAG construction and topological sort), `OutputRouter` (data flow routing), and `Executor` (subjob/component orchestration). The `engine.py` becomes a thin orchestrator delegating to these modules.

Overall code quality is high. The architecture cleanly separates concerns, uses appropriate data structures (deque for iterative trigger firing, TopologicalSorter for DAG ordering), and includes defensive checks (stall detection, cross-subjob flow safety, cycle detection). The test suite is thorough with good coverage of edge cases.

Key concerns: one critical bug where `die_on_error` is read from `_original_config` (pre-resolution) instead of the resolved `config`, which means context-variable-driven `die_on_error` settings will be silently ignored. There are also several warnings around error handling gaps in the engine initialization path and a subtle issue with the `_already_executed_subjobs` recomputation pattern.

## Critical Issues

### CR-01: die_on_error read from _original_config bypasses context resolution

**File:** `src/v1/engine/executor.py:207`
**Issue:** After a component fails, the executor reads `die_on_error` from `component._original_config.get("die_on_error", True)`. However, `_original_config` is the raw, unresolved configuration -- it has NOT been through context variable resolution or Java expression evaluation. If a job config uses `"die_on_error": "${context.stop_on_error}"`, this code will receive the string literal `"${context.stop_on_error}"` which is truthy, so die_on_error will always appear True regardless of the actual resolved value.

The `BaseComponent.execute()` method correctly resolves `die_on_error` from the resolved `self.config` (line 162 of base_component.py), but the executor bypasses this by accessing `_original_config` directly.

**Fix:**
```python
# In executor.py, line 207, change:
die_on_error = component._original_config.get("die_on_error", True)

# To:
die_on_error = component.die_on_error
```

The `component.die_on_error` attribute is set from the resolved config during `component.execute()` (base_component.py line 162), which has already been called before this check runs (line 202). This is the correct post-resolution value.

## Warnings

### WR-01: _already_executed_subjobs recomputed on every call without caching

**File:** `src/v1/engine/executor.py:436-458`
**Issue:** `_already_executed_subjobs()` iterates over ALL subjob IDs and checks every component's execution/skip status on every call. This method is called once per trigger edge evaluation in `_fire_component_triggers` (line 354) and once per edge in `_collect_triggered_subjobs` (line 385). For a job with N subjobs and M trigger edges, this creates O(N*M) iterations per subjob completion.

More importantly, the method reconstructs the set from scratch each time rather than maintaining it incrementally. While not a performance issue for typical job sizes (under 100 subjobs), the pattern is fragile -- if someone adds a call site inside a tight loop, it becomes a correctness concern because the set can change mid-iteration.

**Fix:** Track executed subjobs incrementally in `_execute_subjob`:
```python
# Add to __init__:
self._executed_subjobs: set[str] = set()

# At end of _execute_subjob, before return:
self._executed_subjobs.add(subjob_id)

# Replace _already_executed_subjobs() with:
def _already_executed_subjobs(self) -> set[str]:
    return self._executed_subjobs
```

### WR-02: Engine __init__ starts Java bridge but has no error handling for bridge failure

**File:** `src/v1/engine/engine.py:43-48`
**Issue:** If `JavaBridgeManager.start()` raises an exception, the engine's `__init__` fails without cleanup. The Java bridge process may be left in a partially started state. Since `__init__` hasn't completed, `__exit__` will never be called, so `_cleanup()` never runs.

```python
self.java_bridge_manager = JavaBridgeManager(enable=True, routines=routines, libraries=libraries)
self.java_bridge_manager.start()  # If this throws, no cleanup happens
```

**Fix:** Wrap the bridge start in a try/except that cleans up on failure:
```python
self.java_bridge_manager = JavaBridgeManager(enable=True, routines=routines, libraries=libraries)
try:
    self.java_bridge_manager.start()
except Exception:
    self.java_bridge_manager.stop()
    raise
```

### WR-03: _build_subjobs_dict returns empty dict treated as falsy, triggers unintended auto-detection

**File:** `src/v1/engine/engine.py:76-78`
**Issue:** When no components have `subjob_id` set, `_build_subjobs_dict()` returns `{}`. Line 78 passes `subjobs_dict or None`, which converts the empty dict to `None` since `{}` is falsy. This triggers `ExecutionPlan._auto_detect_subjobs()` instead of creating a plan with no subjobs. For jobs that genuinely have no subjob assignments, the auto-detection path runs BFS over all flows, which may produce different subjob groupings than expected.

```python
subjobs_dict = self._build_subjobs_dict()
self.execution_plan = ExecutionPlan(
    components_config, flows_config, triggers_config, subjobs_dict or None  # {} -> None
)
```

**Fix:** Only pass None when there are truly no components:
```python
self.execution_plan = ExecutionPlan(
    components_config, flows_config, triggers_config,
    subjobs_dict if subjobs_dict else None
)
```

Actually, the behavior is identical since `{}` is falsy. The real fix is to decide the semantic: if components have no `subjob_id` field, should auto-detection run? If yes, the current code is correct but the `or None` is misleading -- it should be explicit:
```python
self.execution_plan = ExecutionPlan(
    components_config, flows_config, triggers_config,
    subjobs_dict or None  # Empty dict means auto-detect
)
```
Add a comment documenting this intentional behavior so future readers don't "fix" it.

### WR-04: Executor._fire_component_triggers fires for failed components

**File:** `src/v1/engine/executor.py:225-226`
**Issue:** `_fire_component_triggers` is called after EVERY component execution, including after errors (line 225-226 is outside the `if comp_result == "error"` block). This is by design for OnComponentError triggers, but the method internally calls `trigger_manager.get_triggered_components()` which evaluates ALL trigger types including OnSubjobOk. If a failed component is the last one in a subjob and all others succeeded, `_check_subjob_ok` returns False (correctly), but `_check_subjob_error` returns True. The issue is that `get_triggered_components` marks triggered targets in `self.triggered_components` (idempotency set), so if `OnSubjobError` fires here, the same target won't fire again in `_collect_triggered_subjobs`. This dual-path trigger evaluation (per-component AND per-subjob) creates a subtle ordering dependency: whichever path evaluates first "wins" the idempotency check.

**Fix:** The executor's docstring says OnSubjobOk triggers fire ONLY in `_collect_triggered_subjobs`, but the code delegates to `trigger_manager.get_triggered_components()` which does not enforce that separation. Consider filtering the results in `_fire_component_triggers` to exclude OnSubjobOk/OnSubjobError types:
```python
def _fire_component_triggers(self, comp_id: str, comp_result: str) -> None:
    triggered = self.trigger_manager.get_triggered_components(comp_id)
    # Filter: only handle per-component triggers here, not subjob-level
    # (subjob-level handled in _collect_triggered_subjobs)
    ...
```
However, this requires understanding TriggerManager internals. A cleaner fix would be to pass a filter parameter to `get_triggered_components`.

## Info

### IN-01: Test file contains ~60 lines of commented-out reasoning that should be removed

**File:** `tests/v1/engine/test_execution_plan.py:228-335`
**Issue:** The `test_unreachable_subjob_raises` test method contains approximately 60 lines of inline comments that walk through the author's reasoning process for constructing an unreachable subjob scenario. While the final test is correct, the intermediate reasoning (multiple abandoned approaches) is noise that makes the test harder to read.

**Fix:** Keep only the final working test with a brief comment explaining why the scenario is unreachable:
```python
def test_unreachable_subjob_raises(self):
    """Subjobs forming a disconnected trigger cycle are unreachable -> ConfigurationError."""
    # s3 and s4 trigger each other but neither is initial or reachable from s1.
    plan_unreachable = _make_plan(
        components=[...],
        triggers=[...],
        subjobs={...},
    )
    with pytest.raises(ConfigurationError, match="[Uu]nreachable"):
        plan_unreachable.validate()
```

### IN-02: Module-level mutable state in test_executor.py

**File:** `tests/v1/engine/test_executor.py:38`
**Issue:** `_execution_order: list[str] = []` is a module-level mutable list used by `OrderTrackingComponent`. Tests reset it via `_execution_order = []` in the test method body (line 279), but this rebinds the local name -- it does not clear the module-level list. The `OrderTrackingComponent._process` appends to the module-level list via `_execution_order.append(self.id)`, but after the test rebinds `_execution_order`, the appends still go to the original list because `_process` closes over the module-level name.

Actually, upon closer inspection: the `global _execution_order` declaration on line 279 makes the rebinding work correctly at module scope. This is fragile but functional. Consider using a pytest fixture or class attribute instead for cleaner isolation.

**Fix:** Use `_execution_order.clear()` instead of rebinding to avoid potential confusion:
```python
_execution_order.clear()
```

### IN-03: Unused import in engine.py

**File:** `src/v1/engine/engine.py:7`
**Issue:** `import time` is imported but never used in `engine.py`. Timing is handled by `Executor._execute_component()` instead.

**Fix:** Remove the unused import:
```python
# Remove: import time
```

---

_Reviewed: 2026-04-14T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
