# tRunJob Engine Component Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `tRunJob` engine component so a parent ETL job can run another whole job (a child job) in-process to completion, pass context to it, and propagate its success/failure.

**Architecture:** A thin `RunJob(BaseComponent)` delegates the "run another job" work to a new `ChildJobRunner` service. The runner resolves the child JSON by name relative to the running job's own folder, builds a nested `ETLEngine` with fresh/isolated services, seeds the child's context, executes it, and maps the outcome to a `ChildResult`. The component writes the return code to the parent globalMap and, when `die_on_child_error` is set, raises to kill the parent. Five small additive engine changes support this.

**Tech Stack:** Python 3.12+, pandas, the existing `src/v1/engine` machinery (`ETLEngine`, `BaseComponent`, `GlobalMap`, `ContextManager`, the `REGISTRY` decorator), pytest.

**Design spec:** `docs/superpowers/specs/2026-06-30-trunjob-component-design.md` (read it; this plan implements it).

## Global Constraints

- **ASCII only** in all source, logs, and docs. No emojis/smart quotes/em dashes (use `--`). Enforced by `tests/conftest.py::assert_ascii_logs`.
- **Engine component prefix:** every log line from the component starts `[{self.id}]`. Per-module `logger = logging.getLogger(__name__)`.
- **Custom exception hierarchy only:** raise `ConfigurationError` / `ComponentExecutionError` from `src/v1/engine/exceptions.py`. Never raise bare `Exception`/`ValueError`.
- **Converter JSON is FROZEN:** consume the existing 22 `tRunJob` config keys; do not require re-conversion. Engine-only resolution config lives under `job_config["engine_config"]`.
- **Component contract:** subclass `BaseComponent`; implement only `_validate_config()` and `_process()`. NEVER override `execute()`; NEVER call `self.validate_schema()` inside `_process()`.
- **`_process()` returns** a dict with key `"main"` (DataFrame or None), optionally `"reject"`. tRunJob returns `{"main": None, "reject": None}` (no data flow).
- **Register engine components under BOTH names:** `@REGISTRY.register("RunJob", "tRunJob")`. The converter emits `"type": "tRunJob"`, so the literal `"tRunJob"` MUST be present.
- **Parent-kill mechanism:** raise `ComponentExecutionError(self.id, msg)` then set `err.exit_code = <int>` as a dynamic attribute AFTER construction (it is NOT a ctor arg), then `raise err`. A `ConfigurationError` would NOT kill the job (no `exit_code`).
- **No mocked Java bridge / engine internals** (project anti-mock rule). Lightweight real stand-ins (a real `ContextManager`, a tiny fake `ChildJobRunner` for the component's own logic) are fine; the bridge/engine themselves are exercised for real.
- **Coverage gate:** new modules must clear the 95% per-module line floor (`scripts/check_per_module_coverage.py --floor 95`). Branch coverage is off.
- **Git:** small frequent commits on the current feature branch (`feature/sync_repo_latest`); never commit to `main`; stage files by name (no `git add -A`).

---

## File Structure

| File | Responsibility |
|---|---|
| `src/v1/engine/child_job_runner.py` (create) | `RunContext`, `ChildResult` dataclasses + `ChildJobRunner` service (resolution, cycle/depth guards, context seeding, nested-engine run, result mapping). |
| `src/v1/engine/components/control/run_job.py` (create) | `RunJob(BaseComponent)` -- config validation, parent-side context building, globalMap.get resolution, calling the runner, return-code writeback, die-on-error kill. |
| `src/v1/engine/executor.py` (modify) | Expose the `job_aborted` fatal-failure signal in the returned stats. |
| `src/v1/engine/engine.py` (modify) | Store `_job_path`/`_job_dir`; accept optional `_run_context`; build root `RunContext` + `ChildJobRunner`; inject `child_job_runner`; constructor rollback on post-JVM failure. |
| `src/v1/engine/components/control/__init__.py` (modify) | Import `RunJob` so the decorator fires. |
| `tests/v1/engine/test_child_job_runner.py` (create) | Unit/integration tests for the runner. |
| `tests/v1/engine/components/control/test_run_job.py` (create) | Unit tests for the component. |
| `tests/v1/engine/test_run_job_e2e.py` (create) | End-to-end: a parent job runs a child that writes a file. |
| `tests/v1/engine/test_executor_job_aborted.py` (create) | Tests for the `job_aborted` signal. |
| `src/converters/talend_to_v1/components/control/run_job.py` (modify, last) | Drop the now-closed `engine_gap` needs_review. |

---

## Task 1: Executor `job_aborted` fatal-failure signal

Adds a boolean to the stats `ETLEngine.execute()` returns so the runner can tell a FATAL child failure (tDie/exit, or a `die_on_error=true` component failure) from a TOLERATED one (`die_on_error=false` failures the job ran past). A bare `status == "failed"` is NOT enough (B3).

**Files:**
- Modify: `src/v1/engine/executor.py` (the stats dict built in `execute_job()` at `:180-186`)
- Test: `tests/v1/engine/test_executor_job_aborted.py`

**Interfaces:**
- Consumes: `self._job_terminated: bool` (`executor.py:86`), `self.failed_components: set[str]` (`:80`), `self.components: dict[str, BaseComponent]`.
- Produces: `execute()` return dict gains key `"job_aborted": bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/v1/engine/test_executor_job_aborted.py
import pytest
from src.v1.engine.engine import ETLEngine


def _run(components, **extra):
    cfg = {"job_name": "abort_probe", "components": components,
           "flows": [], "triggers": [], "subjobs": {}, "context": {"Default": {}}}
    cfg.update(extra)
    with ETLEngine(cfg) as engine:
        return engine.execute()


@pytest.mark.unit
def test_clean_success_is_not_aborted():
    stats = _run([{"id": "pre_1", "type": "tPrejob", "config": {}, "schema": {}}])
    assert stats["status"] == "success"
    assert stats["job_aborted"] is False


@pytest.mark.unit
def test_tdie_is_aborted():
    stats = _run([{"id": "die_1", "type": "tDie",
                   "config": {"message": "boom", "exit_code": 3}, "schema": {}}])
    assert stats["status"] == "error"
    assert stats["job_aborted"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/v1/engine/test_executor_job_aborted.py -v`
Expected: FAIL with `KeyError: 'job_aborted'` (the key does not exist yet). If `tDie`'s config keys differ, fix the `die_1` config to match `tests/v1/engine/components/control/test_die.py` before proceeding.

- [ ] **Step 3: Add the signal to the stats dict**

In `src/v1/engine/executor.py`, locate the stats dict (currently `:180-186`) and add the `job_aborted` computation immediately before it, then the new key:

```python
        # tRunJob (B3): distinguish a FATAL abort (tDie/exit, or a die_on_error=true
        # component failure) from TOLERATED die_on_error=false failures the job ran past.
        job_aborted = self._job_terminated or any(
            getattr(self.components.get(cid), "die_on_error", True)
            for cid in self.failed_components
        )

        stats = {
            "status": status,
            "execution_time": execution_time,
            "components_executed": len(self.executed_components),
            "components_failed": len(self.failed_components),
            "component_stats": self.execution_stats,
            "job_aborted": job_aborted,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/v1/engine/test_executor_job_aborted.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/executor.py tests/v1/engine/test_executor_job_aborted.py
git commit -m "feat(engine): expose job_aborted fatal-failure signal in execute() stats"
```

---

## Task 2: `RunContext` and `ChildResult` dataclasses

The data carriers the runner threads through nesting and returns.

**Files:**
- Create: `src/v1/engine/child_job_runner.py`
- Test: `tests/v1/engine/test_child_job_runner.py`

**Interfaces:**
- Produces:
  - `RunContext(base_dir: Optional[str], jobs_dir: Optional[str], call_stack: list[str], depth: int, max_depth: int = 2)`
  - `ChildResult(status: str, return_code: int, stacktrace: Optional[str] = None)`

- [ ] **Step 1: Write the failing test**

```python
# tests/v1/engine/test_child_job_runner.py
import pytest
from src.v1.engine.child_job_runner import RunContext, ChildResult


@pytest.mark.unit
def test_dataclass_defaults():
    rc = RunContext(base_dir="/d", jobs_dir=None, call_stack=["/d/a.json"], depth=0)
    assert rc.max_depth == 2
    res = ChildResult(status="success", return_code=0)
    assert res.stacktrace is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/v1/engine/test_child_job_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.v1.engine.child_job_runner'`.

- [ ] **Step 3: Create the module with the dataclasses**

```python
# src/v1/engine/child_job_runner.py
"""ChildJobRunner -- runs a child job (tRunJob) in-process as a nested ETLEngine.

See docs/superpowers/specs/2026-06-30-trunjob-component-design.md.
"""
from __future__ import annotations

import logging
import os
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class RunContext:
    """Recursion/resolution state threaded through nested tRunJob calls."""
    base_dir: Optional[str]
    jobs_dir: Optional[str]
    call_stack: List[str]
    depth: int
    max_depth: int = 2


@dataclass
class ChildResult:
    """Outcome of one child-job run."""
    status: str
    return_code: int
    stacktrace: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/v1/engine/test_child_job_runner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/child_job_runner.py tests/v1/engine/test_child_job_runner.py
git commit -m "feat(engine): add RunContext and ChildResult dataclasses"
```

---

## Task 3: `ChildJobRunner` resolution + cycle/depth guards

Path resolution (filename convention, relative to the running job's folder), cycle detection (by resolved abspath), and the depth guard. These are always-fatal pre-flight checks and raise `ConfigurationError` (they are NOT mapped into the die model).

**Files:**
- Modify: `src/v1/engine/child_job_runner.py`
- Test: `tests/v1/engine/test_child_job_runner.py`

**Interfaces:**
- Consumes: `RunContext`, `ConfigurationError`.
- Produces:
  - `ChildJobRunner(run_context: RunContext)`
  - `ChildJobRunner._resolve_path(process: str) -> str` (abspath of `<base>/<process>.json`; raises `ConfigurationError` if no base dir)
  - `ChildJobRunner._check_cycle_and_depth(child_path: str) -> None` (raises `ConfigurationError` on cycle or depth overflow)
  - `ChildJobRunner._child_run_context(child_path: str) -> RunContext`

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/v1/engine/test_child_job_runner.py
import os
from src.v1.engine.child_job_runner import ChildJobRunner
from src.v1.engine.exceptions import ConfigurationError


def _runner(base_dir=None, jobs_dir=None, call_stack=None, depth=0, max_depth=2):
    return ChildJobRunner(RunContext(base_dir=base_dir, jobs_dir=jobs_dir,
                                     call_stack=call_stack or [], depth=depth, max_depth=max_depth))


@pytest.mark.unit
def test_resolve_path_uses_base_dir(tmp_path):
    r = _runner(base_dir=str(tmp_path))
    assert r._resolve_path("Child") == os.path.join(str(tmp_path), "Child.json")


@pytest.mark.unit
def test_resolve_path_falls_back_to_jobs_dir(tmp_path):
    r = _runner(base_dir=None, jobs_dir=str(tmp_path))
    assert r._resolve_path("Child") == os.path.join(str(tmp_path), "Child.json")


@pytest.mark.unit
def test_resolve_path_no_base_raises():
    with pytest.raises(ConfigurationError):
        _runner(base_dir=None, jobs_dir=None)._resolve_path("Child")


@pytest.mark.unit
def test_cycle_detected_by_abspath(tmp_path):
    p = os.path.join(str(tmp_path), "A.json")
    r = _runner(base_dir=str(tmp_path), call_stack=[p])
    with pytest.raises(ConfigurationError, match="cycle"):
        r._check_cycle_and_depth(p)


@pytest.mark.unit
def test_depth_limit(tmp_path):
    r = _runner(base_dir=str(tmp_path), depth=2, max_depth=2)
    with pytest.raises(ConfigurationError, match="depth"):
        r._check_cycle_and_depth(os.path.join(str(tmp_path), "B.json"))


@pytest.mark.unit
def test_child_run_context_increments(tmp_path):
    p = os.path.join(str(tmp_path), "B.json")
    child = _runner(base_dir=str(tmp_path), call_stack=["/root/A.json"], depth=0)._child_run_context(p)
    assert child.depth == 1 and child.call_stack == ["/root/A.json", p]
    assert child.base_dir == str(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v1/engine/test_child_job_runner.py -k "resolve or cycle or depth or child_run_context" -v`
Expected: FAIL with `AttributeError: 'ChildJobRunner' object has no attribute ...` (class not defined yet).

- [ ] **Step 3: Add the `ChildJobRunner` class with resolution + guards**

Append to `src/v1/engine/child_job_runner.py`:

```python
class ChildJobRunner:
    """Resolves and runs a child job as a nested ETLEngine."""

    def __init__(self, run_context: RunContext) -> None:
        self.run_context = run_context

    def _resolve_path(self, process: str) -> str:
        base = self.run_context.base_dir or self.run_context.jobs_dir
        if not base:
            raise ConfigurationError(
                f"cannot resolve child job '{process}': engine started from an "
                f"in-memory config with no engine_config.jobs_dir"
            )
        return os.path.join(os.path.abspath(base), f"{process}.json")

    def _check_cycle_and_depth(self, child_path: str) -> None:
        if child_path in self.run_context.call_stack:
            chain = " -> ".join(self.run_context.call_stack + [child_path])
            raise ConfigurationError(f"tRunJob cycle detected: {chain}")
        if self.run_context.depth + 1 > self.run_context.max_depth:
            raise ConfigurationError(
                f"tRunJob nesting depth {self.run_context.depth + 1} exceeds "
                f"max_run_job_depth={self.run_context.max_depth}"
            )

    def _child_run_context(self, child_path: str) -> RunContext:
        return RunContext(
            base_dir=os.path.dirname(child_path),
            jobs_dir=self.run_context.jobs_dir,
            call_stack=self.run_context.call_stack + [child_path],
            depth=self.run_context.depth + 1,
            max_depth=self.run_context.max_depth,
        )
```

Note: `_resolve_path` returns `<abspath(base)>/<process>.json`; the test for `base_dir` passes `tmp_path` which is already absolute, so `abspath` is a no-op there.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/v1/engine/test_child_job_runner.py -k "resolve or cycle or depth or child_run_context" -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/child_job_runner.py tests/v1/engine/test_child_job_runner.py
git commit -m "feat(engine): ChildJobRunner path resolution + cycle/depth guards"
```

---

## Task 4: Engine wiring -- `_job_dir`, `_run_context`, build + inject `ChildJobRunner`

Engine changes 1-3. Make `ETLEngine` remember where it was loaded from, accept an inherited run context, build the root one, and inject the runner into every component.

**Files:**
- Modify: `src/v1/engine/engine.py` (`__init__` `:33-164`; injection block `:194-201`)
- Test: `tests/v1/engine/test_engine_run_context.py` (create)

**Interfaces:**
- Consumes: `RunContext`, `ChildJobRunner` (Task 2/3).
- Produces: `ETLEngine(job_config, _run_context=None)`; attributes `self._job_path`, `self._job_dir`, `self._run_context`, `self._child_job_runner`; every component gets `component.child_job_runner`.

- [ ] **Step 1: Write the failing test**

```python
# tests/v1/engine/test_engine_run_context.py
import json
import pytest
from src.v1.engine.engine import ETLEngine
from src.v1.engine.child_job_runner import RunContext


def _cfg():
    return {"job_name": "root", "components": [{"id": "pre_1", "type": "tPrejob",
            "config": {}, "schema": {}}], "flows": [], "triggers": [], "subjobs": {},
            "context": {"Default": {}}}


@pytest.mark.unit
def test_root_run_context_from_path(tmp_path):
    p = tmp_path / "root.json"
    p.write_text(json.dumps(_cfg()))
    eng = ETLEngine(str(p))
    assert eng._job_dir == str(tmp_path)
    assert eng._run_context.depth == 0
    assert eng._run_context.base_dir == str(tmp_path)
    assert eng.components["pre_1"].child_job_runner is eng._child_job_runner


@pytest.mark.unit
def test_dict_config_has_no_job_dir_but_has_runner():
    eng = ETLEngine(_cfg())
    assert eng._job_dir is None
    assert eng._child_job_runner is not None


@pytest.mark.unit
def test_inherited_run_context_is_used():
    rc = RunContext(base_dir="/d", jobs_dir=None, call_stack=["/d/root.json"], depth=1, max_depth=2)
    eng = ETLEngine(_cfg(), _run_context=rc)
    assert eng._run_context is rc
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/v1/engine/test_engine_run_context.py -v`
Expected: FAIL -- `TypeError: __init__() got an unexpected keyword argument '_run_context'` (and missing attributes).

- [ ] **Step 3a: Add imports and capture the source path**

In `src/v1/engine/engine.py`, add `import os` near the top imports, and add `from .child_job_runner import RunContext, ChildJobRunner` with the other `.` imports.

Change the constructor signature and the path-load block (`:33-40`):

```python
    def __init__(self, job_config: Dict[str, Any], _run_context=None):
        """Initialize ETL engine with job configuration."""
        # Load configuration (remember the source path so tRunJob can resolve siblings)
        self._job_path = None
        self._job_dir = None
        if isinstance(job_config, str):
            self._job_path = os.path.abspath(job_config)
            self._job_dir = os.path.dirname(self._job_path)
            with open(job_config, 'r') as f:
                self.job_config = json.load(f)
        else:
            self.job_config = job_config
```

- [ ] **Step 3b: Build the root `RunContext` + `ChildJobRunner`**

Immediately AFTER the `self.trigger_manager = TriggerManager(...)` line (currently `:132`) and BEFORE `self._initialize_components()` (`:135`), insert:

```python
        # tRunJob support: root RunContext (or the inherited one for a nested child) + the runner.
        engine_cfg = self.job_config.get("engine_config", {})
        if _run_context is not None:
            self._run_context = _run_context
        else:
            self._run_context = RunContext(
                base_dir=self._job_dir,
                jobs_dir=engine_cfg.get("jobs_dir"),
                call_stack=[self._job_path or self.job_name],
                depth=0,
                max_depth=int(engine_cfg.get("max_run_job_depth", 2)),
            )
        self._child_job_runner = ChildJobRunner(self._run_context)
```

- [ ] **Step 3c: Inject the runner into every component**

In `_initialize_components()`, after the `if self.mssql_manager:` block (`:200-201`) and before `self.components[comp_id] = component` (`:203`):

```python
            component.child_job_runner = self._child_job_runner
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/v1/engine/test_engine_run_context.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/engine.py tests/v1/engine/test_engine_run_context.py
git commit -m "feat(engine): store source dir, accept _run_context, inject child_job_runner"
```

---

## Task 5: Engine constructor rollback (no orphaned child JVM)

Engine change 4 (B5). If construction fails AFTER the JVM starts, `with ETLEngine(...)` never binds the object so `__exit__` never runs -- the JVM leaks. Wrap the post-JVM construction so `_cleanup()` runs on any failure.

**Files:**
- Modify: `src/v1/engine/engine.py` (`__init__`)
- Test: `tests/v1/engine/test_engine_ctor_rollback.py` (create)

**Interfaces:**
- Consumes: `self._cleanup()` (`engine.py:290-300`, idempotent).
- Produces: a constructor that calls `self._cleanup()` and re-raises on any post-JVM failure.

- [ ] **Step 1: Write the failing test**

A construction failure after the manager-None init is triggered by an invalid plan (an unknown trigger target makes `execution_plan.validate()` raise). We assert `_cleanup` is invoked. Java is not required, so we assert via a monkeypatched `_cleanup` spy.

```python
# tests/v1/engine/test_engine_ctor_rollback.py
import pytest
from src.v1.engine import engine as engine_mod
from src.v1.engine.engine import ETLEngine


@pytest.mark.unit
def test_cleanup_called_on_construction_failure(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(ETLEngine, "_cleanup", lambda self: calls.__setitem__("n", calls["n"] + 1))
    bad = {"job_name": "bad",
           "components": [{"id": "pre_1", "type": "tPrejob", "config": {}, "schema": {}}],
           # trigger to a non-existent component -> ExecutionPlan.validate() raises
           "triggers": [{"type": "OnSubjobOk", "from": "pre_1", "to": "ghost", "output_id": 0}],
           "flows": [], "subjobs": {}, "context": {"Default": {}}}
    with pytest.raises(Exception):
        ETLEngine(bad)
    assert calls["n"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/v1/engine/test_engine_ctor_rollback.py -v`
Expected: FAIL -- `_cleanup` is not called during construction yet (`assert calls["n"] >= 1` fails). If `validate()` does not raise on this input, change the test to point a flow `to` a non-existent component instead; confirm the chosen input raises during `ETLEngine(bad)` before fixing.

- [ ] **Step 3: Hoist manager `None`-init and wrap the post-JVM body**

In `__init__`, ensure these three lines sit BEFORE the post-JVM construction (move/duplicate them up next to the `self.java_bridge_manager = None` initialization near `:43`, so `_cleanup` is always safe to call):

```python
        self.python_routine_manager = None
        self.oracle_manager = None
        self.mssql_manager = None
```

Then wrap everything from just AFTER the Java-bridge init block (`:58`) to the END of `__init__` in a try/except:

```python
        # --- constructor rollback (B5): release the JVM/connections if any later
        #     construction step raises, since `with ETLEngine(...)` cannot reach __exit__
        #     when the constructor itself fails. ---
        try:
            # ... ALL existing construction below stays here, indented one level:
            #     python routine manager, oracle manager, mssql manager, core services,
            #     self._run_context / self._child_job_runner, _initialize_components(),
            #     _initialize_triggers(), ExecutionPlan(...).validate(), OutputRouter(...),
            #     Executor(...) ...
            ...
        except Exception:
            self._cleanup()
            raise
```

Indent the existing construction lines (everything after the bridge block through the `self.executor = Executor(...)` assignment) one level under this `try`. Remove the now-duplicated inline `self.oracle_manager = None` / `self.mssql_manager = None` / `self.python_routine_manager = None` assignments that you hoisted (do not leave them re-assigning to None mid-construction after a manager was built).

- [ ] **Step 4: Run test + the prior engine tests to verify**

Run: `python -m pytest tests/v1/engine/test_engine_ctor_rollback.py tests/v1/engine/test_engine_run_context.py tests/v1/engine/test_executor_job_aborted.py -v`
Expected: PASS (all). The rollback must not break the happy-path construction tests from Task 1/4.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/engine.py tests/v1/engine/test_engine_ctor_rollback.py
git commit -m "fix(engine): roll back (cleanup) on post-JVM constructor failure"
```

---

## Task 6: `ChildJobRunner._seed_context` (B1 typed context merge)

Apply parent overrides onto the child engine for EVERY variable the child defines in ANY of its context groups (not just the `context_name` group), with type coercion; warn (never silently drop) on undeclared names. This is the high-severity B1 fix.

**Files:**
- Modify: `src/v1/engine/child_job_runner.py`
- Test: `tests/v1/engine/test_child_job_runner.py`

**Interfaces:**
- Consumes: a child-like object exposing `.job_config` (dict) and `.context_manager` (a real `ContextManager`).
- Produces: `ChildJobRunner._seed_context(child, whole_context: dict, param_overrides: dict, context_name: str = "Default") -> None`.

- [ ] **Step 1: Write the failing test**

Uses a real `ContextManager` (no engine build needed) behind a `SimpleNamespace` child.

```python
# add to tests/v1/engine/test_child_job_runner.py
from types import SimpleNamespace
from src.v1.engine.context_manager import ContextManager


def _child_with_group(group_name, var, value="/default", vtype="id_String"):
    ctx_block = {group_name: {var: {"value": value, "type": vtype}}}
    return SimpleNamespace(
        job_config={"context": ctx_block, "default_context": group_name},
        context_manager=ContextManager(initial_context=ctx_block, default_context=group_name),
    )


@pytest.mark.unit
def test_seed_applies_param_overrides_despite_context_name_mismatch():
    # B1: child has only a PROD group; tRunJob context_name defaults to "Default".
    child = _child_with_group("PROD", "input_path")
    _runner()._seed_context(child, {}, {"input_path": "/runtime/today.csv"}, context_name="Default")
    assert child.context_manager.get("input_path") == "/runtime/today.csv"


@pytest.mark.unit
def test_seed_params_win_over_whole_context():
    child = _child_with_group("Default", "input_path")
    _runner()._seed_context(child, {"input_path": "/whole"}, {"input_path": "/param"}, "Default")
    assert child.context_manager.get("input_path") == "/param"


@pytest.mark.unit
def test_seed_warns_and_skips_undeclared(caplog):
    child = _child_with_group("Default", "input_path")
    _runner()._seed_context(child, {}, {"nope": "x"}, "Default")
    assert "nope" in caplog.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v1/engine/test_child_job_runner.py -k seed -v`
Expected: FAIL with `AttributeError: ... has no attribute '_seed_context'`.

- [ ] **Step 3: Add `_seed_context`**

Append to the `ChildJobRunner` class in `src/v1/engine/child_job_runner.py`:

```python
    def _seed_context(self, child: Any, whole_context: Dict[str, Any],
                      param_overrides: Dict[str, Any], context_name: str = "Default") -> None:
        # Build the set of names the child defines across ALL its context groups, with a type
        # token per name (the selected/default group's type wins). Do NOT gate on a single group
        # == context_name (B1): that silently drops overrides when the child has no such group.
        ctx_block = child.job_config.get("context", {}) or {}
        selected = ctx_block.get(context_name) or ctx_block.get(
            child.job_config.get("default_context", "Default"), {}) or {}
        declared_types: Dict[str, Any] = {}
        for group in ctx_block.values():
            if isinstance(group, dict):
                for name, meta in group.items():
                    declared_types.setdefault(name, (meta or {}).get("type"))
        for name, meta in selected.items():
            declared_types[name] = (meta or {}).get("type")

        for source in (whole_context, param_overrides):       # param_overrides last -> wins
            for name, value in source.items():
                if name in declared_types:
                    child.context_manager.set(name, value, declared_types[name])
                else:
                    logger.warning(
                        "[ChildJobRunner] context override '%s' not defined in child job; skipped",
                        name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/v1/engine/test_child_job_runner.py -k seed -v`
Expected: PASS (3 tests). If `ContextManager.get` returns the typed value differently, confirm `ContextManager.set(name, value, value_type)` and `.get(name)` against `src/v1/engine/context_manager.py` and adjust the assertions.

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/child_job_runner.py tests/v1/engine/test_child_job_runner.py
git commit -m "feat(engine): ChildJobRunner._seed_context applies overrides across all child groups (B1)"
```

---

## Task 7: `ChildJobRunner.run()` + `_map_result`

Run the child in-process inside a try/except so construction/seeding/run failures become a `ChildResult` (B4), and map the child's stats to a return code using `job_aborted` (B3). Cycle/depth raise (always fatal).

**Files:**
- Modify: `src/v1/engine/child_job_runner.py`
- Test: `tests/v1/engine/test_child_job_runner.py`

**Interfaces:**
- Consumes: `ETLEngine` (imported locally inside `run` to avoid a circular import), the executor `job_aborted` key (Task 1), `_resolve_path`/`_check_cycle_and_depth`/`_child_run_context`/`_seed_context`.
- Produces:
  - `ChildJobRunner.run(process: str, whole_context: dict, param_overrides: dict, context_name: str = "Default") -> ChildResult`
  - `ChildJobRunner._map_result(stats: dict) -> ChildResult` (staticmethod)

- [ ] **Step 1: Write the failing tests**

`_map_result` is pure (synthetic stats); `run` is exercised with real minimal child fixtures.

```python
# add to tests/v1/engine/test_child_job_runner.py
import json


@pytest.mark.unit
@pytest.mark.parametrize("stats,exp_code", [
    ({"status": "success", "job_aborted": False}, 0),
    ({"status": "error", "job_aborted": True}, -1),
    ({"status": "failed", "job_aborted": True}, -1),
    ({"status": "failed", "job_aborted": False}, 0),    # tolerated die_on_error=false failure
    ({"status": "error", "error": "boom"}, -1),         # engine raised inside execute()
])
def test_map_result(stats, exp_code):
    assert ChildJobRunner._map_result(stats).return_code == exp_code


def _write_child(dirpath, name, components):
    cfg = {"job_name": name, "components": components, "flows": [], "triggers": [],
           "subjobs": {}, "context": {"Default": {}}}
    path = os.path.join(str(dirpath), f"{name}.json")
    with open(path, "w") as f:
        json.dump(cfg, f)
    return path


@pytest.mark.unit
def test_run_success_child(tmp_path):
    _write_child(tmp_path, "Child", [{"id": "pre_1", "type": "tPrejob", "config": {}, "schema": {}}])
    res = _runner(base_dir=str(tmp_path)).run("Child", {}, {})
    assert res.return_code == 0 and res.status == "success"


@pytest.mark.unit
def test_run_missing_child_is_negative_one_not_raise(tmp_path):
    res = _runner(base_dir=str(tmp_path)).run("Nope", {}, {})
    assert res.return_code == -1 and res.stacktrace


@pytest.mark.unit
def test_run_cycle_raises(tmp_path):
    p = os.path.join(str(tmp_path), "Child.json")
    _write_child(tmp_path, "Child", [{"id": "pre_1", "type": "tPrejob", "config": {}, "schema": {}}])
    with pytest.raises(ConfigurationError, match="cycle"):
        _runner(base_dir=str(tmp_path), call_stack=[p]).run("Child", {}, {})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v1/engine/test_child_job_runner.py -k "map_result or run_" -v`
Expected: FAIL with `AttributeError: ... has no attribute 'run' / '_map_result'`.

- [ ] **Step 3: Add `run` and `_map_result`**

Append to the `ChildJobRunner` class:

```python
    def run(self, process: str, whole_context: Dict[str, Any],
            param_overrides: Dict[str, Any], context_name: str = "Default") -> ChildResult:
        from .engine import ETLEngine  # local import breaks the engine <-> runner cycle
        child_path = self._resolve_path(process)
        self._check_cycle_and_depth(child_path)            # cycle/depth: always-fatal, propagate
        child_ctx = self._child_run_context(child_path)
        try:
            if not os.path.isfile(child_path):
                raise ConfigurationError(f"child job file not found: {child_path}")
            with ETLEngine(child_path, _run_context=child_ctx) as child:
                self._seed_context(child, whole_context, param_overrides, context_name)
                stats = child.execute()
            return self._map_result(stats)
        except Exception as exc:                           # construction / seeding / run failures
            logger.error("[ChildJobRunner] child job '%s' failed: %s", process, exc)
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            return ChildResult(status="error", return_code=-1, stacktrace=tb)

    @staticmethod
    def _map_result(stats: Dict[str, Any]) -> ChildResult:
        if "error" in stats:                               # engine raised inside execute()
            return ChildResult("error", -1, str(stats.get("error")))
        if stats.get("status") == "success":
            return ChildResult("success", 0, None)
        if stats.get("job_aborted"):                       # tDie/exit OR die_on_error=true failure
            return ChildResult("error", -1, None)
        return ChildResult("completed_with_tolerated_errors", 0, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/v1/engine/test_child_job_runner.py -v`
Expected: PASS (all runner tests).

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/child_job_runner.py tests/v1/engine/test_child_job_runner.py
git commit -m "feat(engine): ChildJobRunner.run() + status mapping (B3/B4)"
```

---

## Task 8: `RunJob` component

The `BaseComponent` itself: validate config, build the two parent-side context dicts (including `globalMap.get(...)` resolution), call the runner, write the return code, and kill the parent on `die_on_child_error`. Register under both names.

**Files:**
- Create: `src/v1/engine/components/control/run_job.py`
- Modify: `src/v1/engine/components/control/__init__.py`
- Test: `tests/v1/engine/components/control/test_run_job.py`

**Interfaces:**
- Consumes: `BaseComponent`, `REGISTRY`, `ConfigurationError`, `ComponentExecutionError`, `ChildResult`, the injected `self.child_job_runner`, `self.context_manager.context` (dict of current parent values), `self.global_map`.
- Produces: `RunJob(BaseComponent)` registered as `"RunJob"` + `"tRunJob"`; writes `{id}_CHILD_RETURN_CODE` and (on failure) `{id}_CHILD_EXCEPTION_STACKTRACE` to the parent globalMap.

- [ ] **Step 1: Write the failing tests**

```python
# tests/v1/engine/components/control/test_run_job.py
import re
import pytest
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.child_job_runner import ChildResult
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError
from src.v1.engine.components.control.run_job import RunJob


class _FakeRunner:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, process, whole_context, param_overrides, context_name="Default"):
        self.calls.append((process, whole_context, param_overrides, context_name))
        return self.result


def _make(config, runner, gm=None, ctx=None):
    comp = RunJob("tRunJob_1", config, gm or GlobalMap(), ctx or ContextManager())
    comp.child_job_runner = runner
    return comp


@pytest.mark.unit
def test_registration():
    assert REGISTRY.get("tRunJob") is RunJob
    assert REGISTRY.get("RunJob") is RunJob


@pytest.mark.unit
def test_success_writes_zero_and_returns_none():
    gm = GlobalMap()
    comp = _make({"process": "Child", "die_on_child_error": True},
                 _FakeRunner(ChildResult("success", 0)), gm=gm)
    out = comp.execute(None)
    assert out == {"main": None, "reject": None}
    assert gm.get("tRunJob_1_CHILD_RETURN_CODE") == 0


@pytest.mark.unit
def test_die_on_child_error_kills_parent():
    comp = _make({"process": "Child", "die_on_child_error": True},
                 _FakeRunner(ChildResult("error", -1, "trace")))
    with pytest.raises(ComponentExecutionError) as ei:
        comp.execute(None)
    assert getattr(ei.value, "exit_code", None) == -1


@pytest.mark.unit
def test_die_off_continues_and_records_code():
    gm = GlobalMap()
    comp = _make({"process": "Child", "die_on_child_error": False},
                 _FakeRunner(ChildResult("error", -1, "trace")), gm=gm)
    out = comp.execute(None)
    assert out == {"main": None, "reject": None}
    assert gm.get("tRunJob_1_CHILD_RETURN_CODE") == -1
    assert gm.get("tRunJob_1_CHILD_EXCEPTION_STACKTRACE") == "trace"


@pytest.mark.unit
def test_globalmap_get_resolution_in_params():
    gm = GlobalMap()
    gm.put("tFileList_1_CURRENT_FILEPATH", "/data/today.csv")
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False, "context_params":
                  [{"param_name": "in_file",
                    "param_value": 'globalMap.get("tFileList_1_CURRENT_FILEPATH")'}]},
                 runner, gm=gm)
    comp.execute(None)
    _, _, param_overrides, _ = runner.calls[0]
    assert param_overrides == {"in_file": "/data/today.csv"}


@pytest.mark.unit
def test_validate_rejects_dynamic_job():
    comp = _make({"process": "Child", "use_dynamic_job": True},
                 _FakeRunner(ChildResult("success", 0)))
    with pytest.raises(ConfigurationError):
        comp.execute(None)


@pytest.mark.unit
def test_validate_rejects_empty_process():
    comp = _make({"process": ""}, _FakeRunner(ChildResult("success", 0)))
    with pytest.raises(ConfigurationError):
        comp.execute(None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/v1/engine/components/control/test_run_job.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.v1.engine.components.control.run_job'`.

- [ ] **Step 3: Implement the component**

```python
# src/v1/engine/components/control/run_job.py
"""Engine component for tRunJob -- run another whole job in-process.

See docs/superpowers/specs/2026-06-30-trunjob-component-design.md.
"""
import logging
import re
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ComponentExecutionError, ConfigurationError

logger = logging.getLogger(__name__)

# globalMap.get("KEY"), tolerating a Java cast wrapper e.g. ((String)globalMap.get("KEY"))
_GLOBALMAP_GET = re.compile(r'globalMap\.get\(\s*"([^"]+)"\s*\)')

# Keys that mean nothing in the Python engine; warn once if set to a non-default truthy value.
_IGNORED_IF_SET = (
    "use_independent_process", "print_parameter", "propagate_child_result",
    "use_custom_jvm_setting", "use_extra_classpath", "load_context_from_file",
)


@REGISTRY.register("RunJob", "tRunJob")
class RunJob(BaseComponent):
    """tRunJob -- orchestration component that runs a child job to completion."""

    def _validate_config(self) -> None:
        if self.config.get("use_dynamic_job"):
            raise ConfigurationError(f"[{self.id}] tRunJob: dynamic job (use_dynamic_job) not supported")
        if self.config.get("use_dynamic_context"):
            raise ConfigurationError(f"[{self.id}] tRunJob: dynamic context not supported")
        if not str(self.config.get("process", "")).strip():
            raise ConfigurationError(f"[{self.id}] tRunJob: no child job 'process' configured")
        for key in _IGNORED_IF_SET:
            if self.config.get(key):
                logger.warning("[%s] tRunJob: '%s' is set but not supported by the Python engine; ignored",
                               self.id, key)

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        runner = getattr(self, "child_job_runner", None)
        if runner is None:
            raise ConfigurationError(f"[{self.id}] tRunJob: child_job_runner not available")

        process = self.config["process"]
        whole_context = (dict(self.context_manager.context)
                         if self.config.get("transmit_whole_context") else {})
        param_overrides = self._build_param_overrides()
        context_name = self.config.get("context_name", "Default")

        result = runner.run(process, whole_context, param_overrides, context_name)

        # Persist BEFORE any raise (base post-_process steps are skipped after a raise).
        self.global_map.put(f"{self.id}_CHILD_RETURN_CODE", int(result.return_code))
        if result.stacktrace:
            self.global_map.put(f"{self.id}_CHILD_EXCEPTION_STACKTRACE", result.stacktrace)

        if result.return_code != 0 and self.config.get("die_on_child_error", True):
            logger.error("[%s] child job '%s' failed (rc=%s); terminating parent",
                         self.id, process, result.return_code)
            err = ComponentExecutionError(
                self.id, f"tRunJob child '{process}' failed (rc={result.return_code})")
            err.exit_code = result.return_code      # dynamic attr AFTER construction -> kills parent
            raise err

        logger.info("[%s] child job '%s' completed (rc=%s)", self.id, process, result.return_code)
        return {"main": None, "reject": None}

    def _build_param_overrides(self) -> Dict[str, Any]:
        overrides: Dict[str, Any] = {}
        for row in self.config.get("context_params", []) or []:
            name = row.get("param_name")
            if not name:
                continue
            overrides[name] = self._resolve_globalmap(row.get("param_value"))
        return overrides

    def _resolve_globalmap(self, raw: Any) -> Any:
        # context.X / ${context.X} are already resolved by BaseComponent.execute() before _process.
        # Resolve a globalMap.get("KEY") reference (optionally cast-wrapped) from the parent globalMap.
        if isinstance(raw, str):
            m = _GLOBALMAP_GET.search(raw)
            if m:
                return self.global_map.get(m.group(1))
        return raw
```

- [ ] **Step 4: Register the module**

In `src/v1/engine/components/control/__init__.py`, add an import so the decorator fires (match the existing style in that file, e.g.):

```python
from . import run_job  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/v1/engine/components/control/test_run_job.py -v`
Expected: PASS (7 tests). If `ContextManager` has no `.context` attribute, use the read-all accessor it exposes (confirm in `src/v1/engine/context_manager.py`) and adjust `whole_context`.

- [ ] **Step 6: Commit**

```bash
git add src/v1/engine/components/control/run_job.py src/v1/engine/components/control/__init__.py tests/v1/engine/components/control/test_run_job.py
git commit -m "feat(engine): add tRunJob (RunJob) component"
```

---

## Task 9: End-to-end -- parent runs a child that writes a file

Proves the whole path with REAL engines: a parent job whose tRunJob runs a child job that writes a file; assert the parent succeeds and the file exists.

**Files:**
- Test: `tests/v1/engine/test_run_job_e2e.py` (create)

**Interfaces:**
- Consumes: everything built above + real `tFixedFlowInput` / `tFileOutputDelimited` components.

- [ ] **Step 1: Write the failing test**

The child reads inline rows (`tFixedFlowInput`) and writes a CSV (`tFileOutputDelimited`); the parent runs the child via `tRunJob`. Confirm the two file components' config keys against an existing test (`tests/v1/engine/components/file/test_file_output_delimited.py`) and adjust the config dicts below to match before running.

```python
# tests/v1/engine/test_run_job_e2e.py
import json
import os
import pytest
from src.v1.engine.engine import ETLEngine


def _write(dirpath, name, cfg):
    cfg = {"job_name": name, "flows": [], "triggers": [], "subjobs": {},
           "context": {"Default": {}}, **cfg}
    path = os.path.join(str(dirpath), f"{name}.json")
    with open(path, "w") as f:
        json.dump(cfg, f)
    return path


@pytest.mark.integration
def test_parent_runs_child_that_writes_file(tmp_path):
    out_csv = os.path.join(str(tmp_path), "enriched.csv")

    # Child: FixedFlowInput -> FileOutputDelimited (writes out_csv).
    child_components = [
        {"id": "ffi_1", "type": "tFixedFlowInput",
         "config": {"values": [{"col": "id", "value": "1"}]},
         "schema": {"output": [{"name": "id", "type": "str"}]}, "outputs": ["row1"]},
        {"id": "fout_1", "type": "tFileOutputDelimited",
         "config": {"file_path": out_csv, "field_delimiter": ",", "include_header": True},
         "schema": {"input": [{"name": "id", "type": "str"}]}, "inputs": ["row1"]},
    ]
    _write(tmp_path, "Enrich", {"components": child_components,
           "flows": [{"name": "row1", "from": "ffi_1", "to": "fout_1", "type": "flow"}],
           "subjobs": {"subjob_1": ["ffi_1", "fout_1"]}})

    # Parent: a single tRunJob that runs "Enrich".
    parent_path = _write(tmp_path, "Parent", {"components": [
        {"id": "trun_1", "type": "tRunJob",
         "config": {"process": "Enrich", "die_on_child_error": True}, "schema": {}}]})

    with ETLEngine(parent_path) as engine:
        stats = engine.execute()

    assert stats["status"] == "success"
    assert os.path.isfile(out_csv)
    assert engine.global_map.get("trun_1_CHILD_RETURN_CODE") == 0
```

- [ ] **Step 2: Run test to verify it fails (then iterate config)**

Run: `python -m pytest tests/v1/engine/test_run_job_e2e.py -v`
Expected: initially FAIL. Iterate the child component config keys (`tFixedFlowInput`, `tFileOutputDelimited`) against their real engine classes / existing tests until the child writes `out_csv`. Do NOT change production code to make this pass -- only the fixture config.

- [ ] **Step 3: (No new production code)**

This task is integration-only; if it surfaces a real bug in Tasks 1-8, fix it in the relevant module with its own unit test, then return here.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/v1/engine/test_run_job_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/v1/engine/test_run_job_e2e.py
git commit -m "test(engine): end-to-end tRunJob parent runs child that writes a file"
```

---

## Task 10: Close the converter `engine_gap` needs_review

Now the engine implements tRunJob, drop the converter's advisory `engine_gap` entry. This is advisory metadata (`_needs_review`), not part of the frozen component config -- safe to change.

**Files:**
- Modify: `src/converters/talend_to_v1/components/control/run_job.py` (`:154-159`)
- Test: `tests/converters/talend_to_v1/components/control/test_run_job.py` (locate the existing test asserting `needs_review`; update it)

- [ ] **Step 1: Update the converter test to expect NO engine_gap entry**

Find the existing test that asserts the `engine_gap` needs_review (grep: `engine_gap` under `tests/converters/.../control/`). Change it to assert there is no `engine_gap` entry:

```python
@pytest.mark.unit
def test_no_engine_gap_now_that_engine_exists():
    result = RunJobConverter().convert(_make_node({}), [], {})
    assert all(nr.get("severity") != "engine_gap" for nr in result.needs_review)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/converters/talend_to_v1/components/control/test_run_job.py -k engine_gap -v`
Expected: FAIL (the converter still appends the `engine_gap` entry).

- [ ] **Step 3: Remove the needs_review append**

In `src/converters/talend_to_v1/components/control/run_job.py`, delete the block that appends the `engine_gap` entry (`:154-159`):

```python
        # ---- 5. Engine gap needs_review entries ----
        needs_review.append({
            "issue": "No concrete engine implementation for tRunJob. ...",
            "component": node.component_id,
            "severity": "engine_gap",
        })
```

- [ ] **Step 4: Run the converter test suite for this component**

Run: `python -m pytest tests/converters/talend_to_v1/components/control/test_run_job.py -v`
Expected: PASS (all). Fix any other test that asserted the removed entry.

- [ ] **Step 5: Commit**

```bash
git add src/converters/talend_to_v1/components/control/run_job.py tests/converters/talend_to_v1/components/control/test_run_job.py
git commit -m "chore(converter): drop tRunJob engine_gap needs_review (engine now implements it)"
```

---

## Final verification

- [ ] **Run the full new-test set**

Run:
```bash
python -m pytest tests/v1/engine/test_child_job_runner.py \
  tests/v1/engine/test_executor_job_aborted.py \
  tests/v1/engine/test_engine_run_context.py \
  tests/v1/engine/test_engine_ctor_rollback.py \
  tests/v1/engine/components/control/test_run_job.py \
  tests/v1/engine/test_run_job_e2e.py \
  tests/converters/talend_to_v1/components/control/test_run_job.py -v
```
Expected: all PASS.

- [ ] **Run the per-module coverage gate** (from `CLAUDE.md`)

Run:
```bash
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine --cov=src/converters \
  --cov-report=term-missing --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```
Expected: exit 0; `child_job_runner.py` and `components/control/run_job.py` at >= 95% line coverage. If a residual branch is uncovered, add a focused test (e.g. the `_resolve_globalmap` non-string path, the `child_job_runner is None` guard, the `transmit_whole_context` true path) rather than lowering the floor.

- [ ] **Confirm no regressions in the engine + converter suites**

Run: `python -m pytest tests/v1/engine tests/converters -q`
Expected: all PASS (no regressions from the engine `__init__`/executor edits).
