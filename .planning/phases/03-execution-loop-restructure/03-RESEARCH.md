# Phase 3: Execution Loop Restructure - Research

**Researched:** 2026-04-14
**Domain:** ETL engine execution orchestration, DAG construction, component routing, trigger management
**Confidence:** HIGH

## Summary

Phase 3 decomposes the monolithic 868-line `engine.py` into 5 focused modules: `component_registry.py`, `execution_plan.py`, `output_router.py`, `executor.py`, and a thin `engine.py`. The current engine has a single `execute()` method (lines 368-510) that inlines subjob tracking, BFS queue management, trigger firing, data routing, and stall detection. This monolith prevents independent testing, makes trigger timing bugs hard to isolate, and blocks Phase 10 iterate support since there is no reusable `_execute_subjob()` building block.

The rewrite builds on Phase 1 infrastructure (BaseComponent, TriggerManager, GlobalMap, ContextManager) which is already solid. The primary technical challenges are: (1) correctly modeling the Talend execution semantics where data flows within subjobs are row-pipelined but our Python engine uses DataFrame batches, (2) getting OnSubjobOk trigger timing right (fires only after ALL subjob components complete), and (3) pre-validation graph analysis that handles conditional RunIf edges without false-positive unreachable warnings.

**Primary recommendation:** Use Python 3.9+ stdlib `graphlib.TopologicalSorter` for DAG construction and topological sort within subjobs. Build ExecutionPlan as a pure data structure (no side effects) that can be validated independently, then pass it to Executor for runtime orchestration.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Decompose engine.py into 5 focused modules: `component_registry.py`, `execution_plan.py`, `output_router.py`, `executor.py`, `engine.py`
- **D-02:** Switch engine component registry from manually-maintained static dict to decorator-based auto-registration matching the converter pattern
- **D-03:** Registration triggered via `__init__.py` imports, same pattern as converter
- **D-04:** Phase 3 creates registry infrastructure but does NOT touch component files. Registry starts empty after Phase 3.
- **D-05:** Build full execution plan at init time. DAG from components, flows, triggers, subjobs. Topological sort within each subjob. Subjob execution order from trigger graph.
- **D-06:** Pre-execution graph validation checks for unreachable components and cycles before any component runs
- **D-07:** Runtime stall detection as safety net even with pre-validation
- **D-08:** RunIf triggers treated as conditional edges -- pre-validation does NOT flag RunIf-targeted subjobs as unreachable
- **D-09:** Minimal streaming scope -- ensure execution loop routes chunked/streamed results correctly
- **D-10:** ExecutionPlan includes streaming awareness metadata (requires_full_data vs streamable)
- **D-11:** Error behavior controlled by per-component die_on_error config
- **D-12:** Independent subjobs always continue on failure in unrelated subjobs
- **D-13:** tDie preserves special behavior -- raises ComponentExecutionError with exit_code to stop entire job
- **D-14:** Remove _execute_iterate_component() entirely (141 lines dead code)
- **D-15:** BaseIterateComponent class stays (Phase 1 rewrote it, Phase 10 uses it)
- **D-16:** Research data flow lifecycle (when data is freed after downstream consumers read it)
- **D-17:** StubComponent as permanent test fixture in conftest.py
- **D-18:** Each new module gets its own test file
- **D-19:** ~20 core test scenarios covering full orchestration behavior

### Claude's Discretion
- Internal class design and method signatures for ExecutionPlan, OutputRouter, Executor
- Exact topological sort algorithm choice
- How ExecutionPlan consumes the converter's subjobs dict vs auto-detection fallback
- Streaming metadata schema (what fields, how components declare capability)
- Whether `_initialize_components()` and `_initialize_triggers()` stay in engine.py or move to a factory

### Deferred Ideas (OUT OF SCOPE)
- Component file updates with @REGISTRY.register() decorators -- Phase 4-11
- Iterate execution loop -- Phase 10
- Streaming optimization for aggregate/sort -- Phase 6
- Pipeline-style streaming -- future milestone
- Parallel execution of independent subjobs -- future milestone
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXEC-01 | Decompose monolithic execution loop into `_execute_subjob()` with topological sort | TopologicalSorter from graphlib stdlib; 5-file decomposition pattern with executor.py owning `_execute_subjob()` |
| EXEC-02 | Extract `_route_component_outputs()` for data flow routing between components | OutputRouter class managing data_flows dict; flow type mapping (flow/reject/filter/iterate) |
| EXEC-03 | Extract `_build_execution_plan()` for DAG construction and dependency resolution | ExecutionPlan class with graphlib DAG, pre-computed subjob order from trigger graph |
| EXEC-07 | Fix stall detection -- raise error instead of silent warning when components unreachable | Pre-validation in ExecutionPlan.validate() + runtime detection in Executor as safety net |
| PERF-01 | Fix streaming mode -- proper chunk processing without reject data loss | Phase 1 BaseComponent already fixed reject collection; Phase 3 ensures OutputRouter handles chunked results in routing |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python 3.10+ engine, no framework changes
- **No breaking changes**: Converter JSON format must remain compatible -- engine changes cannot require re-conversion
- **Naming**: `snake_case.py` for modules, `PascalCase` for classes, `snake_case` for functions
- **Logging**: `logger = logging.getLogger(__name__)` per module, `[{self.id}]` prefix, ASCII only
- **Error handling**: Custom exception hierarchy from `exceptions.py`, never generic Exception
- **Imports**: Relative imports within package
- **Testing**: pytest, `@pytest.mark.unit`, fresh fixtures per test, test through `execute()` lifecycle
- **No print()**: Use logger exclusively
- **GSD workflow**: Changes through GSD commands

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| graphlib | stdlib (3.9+) | TopologicalSorter for DAG construction and cycle detection | [VERIFIED: Python 3.12.12 runtime] Stdlib, no external dependency, raises CycleError on cycles |
| dataclasses | stdlib | ExecutionPlan, SubjobPlan data structures | Immutable-ish data containers matching project style (TalendNode, SchemaColumn precedent) |
| collections.deque | stdlib | BFS/queue for graph traversal in auto-detection fallback | Already used in current engine.py |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 | Test framework | [VERIFIED: runtime] All Phase 3 test files |
| pandas | 3.0.1 | DataFrame transport between components | [VERIFIED: project memory] Already installed, CoW enabled |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| graphlib.TopologicalSorter | networkx | Massive dependency for simple topo sort; graphlib is stdlib and sufficient |
| graphlib.TopologicalSorter | Custom Kahn's algorithm | Reinventing the wheel; graphlib handles cycle detection, incremental processing |
| dataclasses | TypedDict | dataclasses give methods and validation hooks; TypedDict is just a type hint |

**Installation:** No new dependencies required. All from stdlib.

## Architecture Patterns

### Recommended Project Structure

```
src/v1/engine/
    __init__.py              # Re-exports ETLEngine (update import path)
    engine.py                # Thin ETLEngine: __init__, execute() delegates, cleanup, CLI
    component_registry.py    # ComponentRegistry class (decorator-based, matches converter)
    execution_plan.py        # ExecutionPlan: DAG, topo sort, validation, subjob ordering
    output_router.py         # OutputRouter: data_flows management, route/resolve
    executor.py              # Executor: _execute_subjob(), _execute_component(), error handling
    base_component.py        # (Phase 1 -- unchanged)
    base_iterate_component.py # (Phase 1 -- unchanged)
    trigger_manager.py       # (Phase 1 -- unchanged)
    global_map.py            # (Phase 1 -- unchanged)
    context_manager.py       # (Phase 1 -- unchanged)
    exceptions.py            # (Phase 1 -- unchanged, may add StallDetectionError)
    java_bridge_manager.py   # (unchanged)
    python_routine_manager.py # (unchanged)
    components/              # (unchanged -- component files NOT touched in Phase 3)
        file/
        transform/
        aggregate/
        context/
        control/
```

### Pattern 1: Decorator-Based Component Registry (matches converter)

**What:** A singleton ComponentRegistry with `@register()` decorator, matching the existing converter pattern from `src/converters/talend_to_v1/components/registry.py`. [VERIFIED: source code read]

**When to use:** Always for engine component registration (replaces the 125-line static dict).

**Example:**

```python
# src/v1/engine/component_registry.py
"""Decorator-based engine component registry.

Matches the converter registry pattern from
src/converters/talend_to_v1/components/registry.py.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Type

if TYPE_CHECKING:
    from .base_component import BaseComponent

import logging

logger = logging.getLogger(__name__)


class ComponentRegistry:
    """Maps component type names to engine component classes.

    Supports both V1 names (PascalCase, no prefix) and Talend aliases
    (camelCase with 't' prefix). Both must map to the same class.
    """

    def __init__(self) -> None:
        self._components: dict[str, Type[BaseComponent]] = {}

    def register(self, *names: str):
        """Decorator to register a component class under one or more type names.

        Args:
            *names: One or more component type names (e.g., 'FileInputDelimited',
                'tFileInputDelimited').

        Returns:
            Decorator function.

        Raises:
            ValueError: If a name is already registered to a different class.
        """
        def decorator(cls: Type[BaseComponent]) -> Type[BaseComponent]:
            for name in names:
                if name in self._components:
                    raise ValueError(
                        f"Component type {name!r} already registered to "
                        f"{self._components[name].__name__}"
                    )
                self._components[name] = cls
            return cls
        return decorator

    def get(self, name: str) -> Optional[Type[BaseComponent]]:
        """Return the component class for name, or None if not registered."""
        return self._components.get(name)

    def list_types(self) -> list[str]:
        """Return sorted list of all registered component type names."""
        return sorted(self._components)

    def __len__(self) -> int:
        return len(self._components)

    def __contains__(self, name: str) -> bool:
        return name in self._components


REGISTRY = ComponentRegistry()
```

**Source:** Modeled directly on `src/converters/talend_to_v1/components/registry.py` [VERIFIED: source code read]

### Pattern 2: ExecutionPlan as Pure Data Structure

**What:** Build execution plan at init time as an immutable-ish data structure. No side effects during construction. Validation as a separate method. [ASSUMED -- design choice within Claude's discretion]

**When to use:** At engine initialization, before any component executes.

**Example:**

```python
# src/v1/engine/execution_plan.py
"""Execution plan: DAG construction, topological sort, graph validation."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from graphlib import TopologicalSorter, CycleError

from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class SubjobPlan:
    """Pre-computed execution plan for a single subjob."""
    subjob_id: str
    component_ids: list[str]           # Topologically sorted execution order
    component_set: set[str]            # For O(1) membership checks
    start_component: str | None = None  # is_subjob_start component


@dataclass
class StreamingMetadata:
    """Streaming capability metadata for a component."""
    component_id: str
    requires_full_data: bool = False    # True for aggregate, sort
    streamable: bool = True             # True for filter, map, most transforms


class ExecutionPlan:
    """Pre-computed execution plan for a job.

    Constructed from job config at init time. Contains:
    - Topologically sorted component order within each subjob
    - Subjob execution order (from trigger graph)
    - Initial (non-triggered) subjobs
    - Streaming metadata per component
    """

    def __init__(self, components, flows, triggers, subjobs):
        # Build internal DAG and compute order
        ...

    def validate(self) -> None:
        """Pre-execution validation.

        Checks:
        - No cycles in component dependency graph
        - No unreachable components (except RunIf-conditional targets)
        - All flow references resolve to existing components

        Raises:
            ConfigurationError: With diagnostic listing unreachable/cyclic components.
        """
        ...

    @property
    def initial_subjobs(self) -> list[str]:
        """Subjob IDs not targeted by any trigger -- execute first."""
        ...

    def get_subjob_plan(self, subjob_id: str) -> SubjobPlan:
        """Get pre-computed execution plan for a subjob."""
        ...

    def get_triggered_subjobs(self, trigger_type: str, source_subjob: str) -> list[str]:
        """Get subjob IDs triggered by completion of source_subjob."""
        ...
```

### Pattern 3: OutputRouter for Data Flow Management

**What:** Encapsulates the `data_flows` dict and all routing logic -- mapping component outputs to named flows, resolving component inputs from flows. [ASSUMED -- design choice within Claude's discretion]

**When to use:** Replaces the inline routing in `_execute_component()` (lines 542-559) and `_get_input_data()` / `_are_inputs_ready()` (lines 739-769).

**Example:**

```python
# src/v1/engine/output_router.py
"""Output routing: manage data flows between components."""
from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class OutputRouter:
    """Manages data flow routing between components.

    Owns the data_flows dict. Routes component outputs to named flows
    based on the flows config. Resolves component inputs from upstream
    flow names.
    """

    def __init__(self, flows_config: list[dict]):
        self._flows_config = flows_config
        self._data_flows: dict[str, Any] = {}
        # Pre-compute lookup structures
        self._outgoing: dict[str, list[dict]] = {}  # comp_id -> [flow configs]
        self._incoming: dict[str, list[str]] = {}    # comp_id -> [flow names]
        for flow in flows_config:
            self._outgoing.setdefault(flow["from"], []).append(flow)
            self._incoming.setdefault(flow["to"], []).append(flow["name"])

    def route_outputs(self, comp_id: str, result: dict) -> None:
        """Route component outputs to named flows based on flows config.

        Maps result keys to flow names:
        - flow type 'flow' -> result['main']
        - flow type 'reject' -> result['reject']
        - flow type 'filter' -> result['main']
        - flow type 'iterate' -> result.get('iterate')
        - Named outputs matching component.outputs -> stored by key
        """
        ...

    def get_input_data(self, comp_id: str) -> Optional[Any]:
        """Get input data for a component from upstream flows.

        Single input: return DataFrame directly.
        Multiple inputs: return dict keyed by flow name.
        No inputs: return None.
        """
        ...

    def are_inputs_ready(self, comp_id: str) -> bool:
        """Check if all required inputs for a component are available."""
        ...

    def clear_flow(self, flow_name: str) -> None:
        """Remove a flow's data (for iterate cleanup between iterations)."""
        ...

    def clear_subjob_flows(self, subjob_component_ids: set[str]) -> None:
        """Clear all outgoing flows from a set of components."""
        ...
```

### Pattern 4: Executor with Reusable _execute_subjob()

**What:** The Executor class owns subjob and component execution. `_execute_subjob()` is designed as Phase 10's building block -- it will be called in a loop per iteration item. [ASSUMED -- design choice within Claude's discretion, informed by D-01]

**Example:**

```python
# src/v1/engine/executor.py
"""Executor: subjob and component execution with error handling."""
from __future__ import annotations

import logging
import time

from .base_component import BaseComponent, ComponentStatus
from .base_iterate_component import BaseIterateComponent
from .exceptions import ComponentExecutionError, ConfigurationError

logger = logging.getLogger(__name__)


class Executor:
    """Executes subjobs and components according to the execution plan.

    Owns the main execution loop. Uses ExecutionPlan for ordering,
    OutputRouter for data routing, TriggerManager for inter-subjob flow.
    """

    def __init__(self, components, execution_plan, output_router,
                 trigger_manager, global_map):
        ...

    def execute_job(self) -> dict:
        """Execute the full job: initial subjobs, then triggered subjobs.

        Returns:
            Execution statistics dict.
        """
        ...

    def _execute_subjob(self, subjob_id: str) -> str:
        """Execute all components in a subjob in topological order.

        THIS IS THE BUILDING BLOCK for Phase 10 iterate support.
        Phase 10 will call this in a loop per iteration item.

        Returns:
            'success' or 'error' for the subjob as a whole.
        """
        ...

    def _execute_component(self, comp_id: str) -> str:
        """Execute a single component.

        Handles:
        - Input data retrieval via OutputRouter
        - BaseComponent.execute() call
        - Output routing via OutputRouter
        - Error propagation based on die_on_error
        - tDie special behavior (exit_code -> stop entire job)

        Returns:
            'success' or 'error'.
        """
        ...
```

### Anti-Patterns to Avoid

- **Inline BFS queue for execution order:** The current engine uses `deque` with dynamic re-checks of all components after every execution. Replace with pre-computed topological order from ExecutionPlan.
- **Trigger checking on every component completion:** Current code calls `get_triggered_components()` after every component, even within a subjob. OnSubjobOk should only be checked after the entire subjob completes.
- **Monolithic try/except around entire execute():** Break into per-subjob and per-component error boundaries.
- **Mixing graph construction with execution:** Keep ExecutionPlan as pure computation, Executor as side-effect-driven.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Topological sort | Custom DFS-based topo sort | `graphlib.TopologicalSorter` | [VERIFIED: Python 3.12 stdlib] Handles cycles (CycleError), incremental nodes, static_order() for simple case |
| Cycle detection | Custom visited-set cycle finder | `graphlib.CycleError` | [VERIFIED: tested in this session] Automatic with TopologicalSorter, includes cycle path in error message |
| Component registry pattern | Another static dict | Decorator-based registry matching converter pattern | [VERIFIED: converter registry works at 80+ components] Pattern proven, eliminates coupled imports |
| Subjob auto-detection | New BFS algorithm | Existing `_find_connected_components()` logic (adapted) | [VERIFIED: engine.py lines 346-366] Current logic is correct for flow-based grouping, just needs to be moved |

**Key insight:** The stdlib `graphlib.TopologicalSorter` gives us exactly what we need: cycle detection via CycleError, deterministic ordering via `static_order()`, and a clean API. No need for networkx or custom algorithms.

## Common Pitfalls

### Pitfall 1: OnSubjobOk Trigger Timing Regression

**What goes wrong:** Trigger fires after individual component completion instead of after all subjob components complete.
**Why it happens:** The current code calls `get_triggered_components()` inside the component loop, not after the subjob loop. Phase 1 fixed the TriggerManager's `_check_subjob_ok()` to check ALL subjob components, but the calling code in engine.py still checks on every component.
**How to avoid:** Executor must call `get_triggered_components()` ONLY after `_execute_subjob()` completes all components. The TriggerManager's `_check_subjob_ok()` correctly verifies all components, but it must not be called prematurely.
**Warning signs:** Test where subjob has 3 components -- triggered subjob starts before component 3 completes.

### Pitfall 2: RunIf False Positives in Pre-Validation

**What goes wrong:** Pre-validation marks RunIf-targeted subjobs as unreachable, but they are conditionally reachable.
**Why it happens:** Static analysis cannot know if a RunIf condition will be true at runtime.
**How to avoid:** D-08 is explicit: treat RunIf edges as conditional. Pre-validation must NOT flag RunIf targets as unreachable. At runtime, Executor evaluates the condition -- fires if true, skips (without error) if false.
**Warning signs:** Jobs with RunIf triggers raise ConfigurationError during plan validation.

### Pitfall 3: Data Flow Reference Counting for Memory

**What goes wrong:** DataFrames held in `data_flows` indefinitely, memory grows with job complexity.
**Why it happens:** No mechanism to free data after all downstream consumers have read it.
**How to avoid:** OutputRouter can track consumer count per flow. When all consumers of a flow have executed, clear the flow data. But this is an optimization -- for Phase 3, keeping all flows until subjob completion is safe since Talend keeps data in memory for the duration of the subjob. [ASSUMED -- based on Talend's behavior where data flows within a subjob are kept until the subjob completes]
**Warning signs:** Memory growth on large multi-component subjobs.

### Pitfall 4: tDie Error Propagation Across Boundaries

**What goes wrong:** tDie raises ComponentExecutionError which gets caught at the subjob level, only stopping that subjob instead of the whole job.
**Why it happens:** Normal errors stop the subjob. tDie must stop the entire job (D-13).
**How to avoid:** Executor._execute_component() checks for `exit_code` attribute on the exception and re-raises to the job level. Do NOT catch tDie errors at the subjob level.
**Warning signs:** Test with tDie in middle of multi-subjob job -- subsequent subjobs should NOT execute.

### Pitfall 5: Component Import Failure at Engine Init

**What goes wrong:** After Phase 3 removes the static registry and creates an empty decorator-based registry, the engine starts with zero registered components.
**Why it happens:** D-04 says Phase 3 does NOT touch component files. Components register themselves in Phases 4-11.
**How to avoid:** Accept that after Phase 3, the engine has no usable components. Tests use StubComponent. Integration tests are deferred to Phase 4+. The old import block (lines 22-47) is removed entirely.
**Warning signs:** Forgetting that `REGISTRY.get('tFileInputDelimited')` returns None until Phase 4 rewrites that component.

### Pitfall 6: Circular Import Between engine.py and component_registry.py

**What goes wrong:** `engine.py` imports from `component_registry.py`, which needs `BaseComponent` type hints.
**Why it happens:** Registry type-checks against BaseComponent, engine imports from registry.
**How to avoid:** Use `TYPE_CHECKING` guard in `component_registry.py` (same pattern as converter registry). Only import BaseComponent for type hints, not at runtime.
**Warning signs:** ImportError at module load time.

### Pitfall 7: OnComponentOk vs OnSubjobOk Check Point

**What goes wrong:** OnComponentOk triggers are not checked after each component in the subjob, only after the subjob completes.
**Why it happens:** Moving trigger checks to after-subjob for OnSubjobOk could accidentally delay OnComponentOk.
**How to avoid:** Differentiate trigger check timing: OnComponentOk/OnComponentError are checked after each component. OnSubjobOk/OnSubjobError are checked after all subjob components complete. The current TriggerManager handles this correctly in `should_fire_trigger()` -- the executor just needs to call `get_triggered_components()` at the right times.
**Warning signs:** Test with OnComponentOk trigger between subjobs -- target should fire after source component, not after source subjob.

## Data Flow Lifecycle Research (D-16)

### How Talend Manages Data Flow Lifecycle

Talend generates Java code that processes data row-by-row in a pipeline within a subjob. When component A connects to component B via a "main" flow, the generated code is essentially a while loop: read row from A, pass to B, repeat. There is no intermediate DataFrame stored between components -- it is a streaming pipeline. [CITED: https://www.talend.com/resources/talend-job-design-patterns-and-best-practices-part-2/]

However, some components (tMap lookup, tSortRow, tAggregateRow) must buffer all input before producing output. Talend loads these into memory (or disk for tMap with STORE_ON_DISK). [CITED: https://www.talend.com/resources/talend-job-design-patterns-and-best-practices-part-4/]

### Implications for Python Engine

Our Python engine uses DataFrames (batch mode) rather than row-by-row streaming. This means:

1. **Within a subjob:** All component outputs are stored as DataFrames in `data_flows` until the subjob completes. This is safe and matches Talend's behavior for buffered components.

2. **Between subjobs:** Data does not flow via data_flows. Subjobs communicate via triggers and globalMap variables. Once a subjob completes, its internal data flows can be freed.

3. **Recommendation for Phase 3:** Clear subjob data flows after subjob completion (when all downstream consumers in that subjob have executed). This is a simple optimization:
   - After `_execute_subjob()` returns, call `output_router.clear_subjob_flows(subjob_component_ids)`
   - Exception: flows that cross subjob boundaries (rare, but possible with OnComponentOk)

4. **Consumer counting is deferred:** Full reference-counting (free a flow as soon as its last consumer has read it) is an optimization for Phase 6 (streaming) or later. Phase 3 uses the simpler "clear on subjob completion" approach.

[ASSUMED -- based on Talend documentation about row-by-row pipeline execution model and the fact that our engine uses DataFrame batches instead]

## Code Examples

### TopologicalSorter Usage for Subjob Component Ordering

```python
# Source: Python 3.12 stdlib graphlib [VERIFIED: tested in this session]
from graphlib import TopologicalSorter, CycleError

def build_subjob_order(component_ids: set[str], flows: list[dict]) -> list[str]:
    """Topologically sort components within a subjob using flow dependencies.

    Args:
        component_ids: Set of component IDs in this subjob.
        flows: List of flow config dicts from job config.

    Returns:
        List of component IDs in execution order (dependencies first).

    Raises:
        ConfigurationError: If a cycle is detected.
    """
    ts = TopologicalSorter()
    for comp_id in component_ids:
        ts.add(comp_id)  # Ensure all components are in the graph

    for flow in flows:
        from_id = flow["from"]
        to_id = flow["to"]
        # Only add edges within this subjob
        if from_id in component_ids and to_id in component_ids:
            # to_id depends on from_id (from must run before to)
            ts.add(to_id, from_id)

    try:
        return list(ts.static_order())
    except CycleError as e:
        raise ConfigurationError(
            f"Cycle detected in subjob component graph: {e.args[1]}"
        ) from e
```

### Subjob Order from Trigger Graph

```python
# Source: Custom logic based on job config trigger structure [ASSUMED]
def build_subjob_order(subjobs: dict[str, list[str]], triggers: list[dict],
                        component_to_subjob: dict[str, str]) -> list[str]:
    """Determine subjob execution order from trigger graph.

    Returns:
        List of subjob IDs that are not triggered (initial subjobs).
        Other subjobs execute when their triggers fire.
    """
    triggered_subjobs = set()
    for trigger in triggers:
        to_comp = trigger.get("to_component") or trigger.get("to")
        to_subjob = component_to_subjob.get(to_comp)
        if to_subjob:
            triggered_subjobs.add(to_subjob)

    initial_subjobs = [sid for sid in subjobs if sid not in triggered_subjobs]
    return initial_subjobs
```

### StubComponent for Testing

```python
# Source: Custom test fixture pattern [ASSUMED]
# tests/v1/engine/conftest.py
import pandas as pd
from src.v1.engine.base_component import BaseComponent


class StubComponent(BaseComponent):
    """Test-only component for execution orchestration tests.

    Configurable output via config keys:
    - 'output_data': list of dicts for main output DataFrame
    - 'reject_data': list of dicts for reject output DataFrame
    - 'should_fail': bool -- if True, _process raises ComponentExecutionError
    - 'fail_message': str -- error message when should_fail is True
    - 'named_outputs': dict[str, list[dict]] -- additional named output flows
    """

    def _validate_config(self) -> None:
        """No required keys for stub."""
        pass

    def _process(self, input_data=None) -> dict:
        """Return configurable output."""
        if self.config.get("should_fail", False):
            raise Exception(self.config.get("fail_message", "StubComponent failure"))

        result = {}

        # Main output
        output_data = self.config.get("output_data")
        if output_data is not None:
            result["main"] = pd.DataFrame(output_data)
        elif input_data is not None:
            result["main"] = input_data
        else:
            result["main"] = pd.DataFrame()

        # Reject output
        reject_data = self.config.get("reject_data")
        if reject_data is not None:
            result["reject"] = pd.DataFrame(reject_data)

        # Named outputs
        for name, data in self.config.get("named_outputs", {}).items():
            result[name] = pd.DataFrame(data)

        return result
```

### Pre-Validation Graph Check

```python
# Source: Custom validation logic [ASSUMED]
def validate_graph(subjob_plans, trigger_edges, runif_targets):
    """Validate execution graph for unreachable components and cycles.

    Args:
        subjob_plans: Dict of subjob_id -> SubjobPlan (already topo-sorted)
        trigger_edges: List of (from_subjob, to_subjob, trigger_type) tuples
        runif_targets: Set of subjob_ids targeted by RunIf triggers

    Raises:
        ConfigurationError: With diagnostics listing problems.
    """
    # Find all reachable subjobs from initial subjobs
    initial = {sid for sid in subjob_plans if not any(
        to_sj == sid for _, to_sj, _ in trigger_edges
    )}
    reachable = set(initial)
    queue = list(initial)
    while queue:
        current = queue.pop(0)
        for from_sj, to_sj, _ in trigger_edges:
            if from_sj == current and to_sj not in reachable:
                reachable.add(to_sj)
                queue.append(to_sj)

    # Check unreachable (excluding RunIf targets which are conditional)
    unreachable = set(subjob_plans.keys()) - reachable - runif_targets
    if unreachable:
        raise ConfigurationError(
            f"Unreachable subjobs detected: {unreachable}. "
            f"These subjobs have no trigger path from any initial subjob."
        )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual static dict registry (125 lines) | Decorator-based auto-registration | Phase 3 (now) | Eliminates coupled imports that caused ENG-04, matches converter pattern |
| BFS queue with dynamic re-check | Pre-computed topological order | Phase 3 (now) | Deterministic execution, no O(n^2) re-scanning |
| Silent warning on stall | ConfigurationError with diagnostics | Phase 3 (now) | Fails fast with actionable error message |
| Monolithic engine.py (868 lines) | 5-file decomposition | Phase 3 (now) | Each module independently testable |
| Custom topo sort | stdlib graphlib.TopologicalSorter | Python 3.9+ (2020) | No reason to hand-roll when stdlib provides it |

**Deprecated/outdated:**
- `_execute_iterate_component()` (lines 596-737): 141 lines of dead code, no iterate components registered. Removed per D-14.
- `_COMPONENT_IMPORTS_AVAILABLE` flag: Removed along with the try/except import block. New registry starts empty.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Talend keeps data in memory for the duration of the subjob, freeing after subjob completes | Data Flow Lifecycle | If Talend frees data earlier (per-consumer), Phase 3's "clear on subjob completion" uses more memory than Talend does for complex subjobs |
| A2 | Flows never cross subjob boundaries (data only crosses via triggers/globalMap) | Data Flow Lifecycle | If cross-subjob data flows exist, clearing on subjob completion would lose data needed by downstream subjobs |
| A3 | OnComponentOk triggers can fire between subjobs (triggering a component in a different subjob) | Pitfall 7 | If OnComponentOk is always within a subjob, the differentiated check timing is unnecessary complexity |
| A4 | Phase 3 executor._execute_subjob() interface will be stable enough for Phase 10 iterate to call without changes | Architecture Pattern 4 | If Phase 10 needs a different interface, executor will need refactoring |

## Open Questions

1. **Cross-subjob OnComponentOk triggers**
   - What we know: OnSubjobOk clearly crosses subjob boundaries (from subjob A to subjob B). OnComponentOk is shown in sample configs triggering between subjobs (Job_tContextLoad: OnComponentOk from tContextLoad_1 to tJava_1 across subjobs).
   - What's unclear: When OnComponentOk fires between subjobs, should the target subjob be "activated" immediately or queued? Current code activates the target subjob immediately.
   - Recommendation: Keep current behavior -- activate target subjob immediately when OnComponentOk fires. The executor should check OnComponentOk after each component AND check OnSubjobOk/OnSubjobError after each subjob.

2. **Subjob auto-detection fallback vs explicit subjobs**
   - What we know: Converter outputs explicit `subjobs` dict in JSON configs. The current engine has auto-detection fallback when no subjobs are defined.
   - What's unclear: Are there real job configs without explicit subjobs?
   - Recommendation: Support both paths. ExecutionPlan should consume explicit `subjobs` from config when present, fall back to auto-detection (existing BFS grouping logic) when absent. This maintains backward compatibility.

3. **Flow types beyond main/reject/filter**
   - What we know: Current code handles `flow`, `reject`, and `filter` types. JSON configs also have `iterate` type.
   - What's unclear: Are there other flow types in the converter output? What about `lookup` flows for tMap?
   - Recommendation: OutputRouter should handle the 4 known types (flow, reject, filter, iterate) and log a warning for unknown types. tMap lookup flows are handled internally by the tMap component, not by the engine routing layer.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | Engine runtime | Yes | 3.12.12 | -- |
| graphlib (stdlib) | ExecutionPlan topo sort | Yes | stdlib | -- |
| pytest | Testing | Yes | 9.0.2 | -- |
| pandas | DataFrame transport | Yes | 3.0.1 | -- |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | None -- see Wave 0 |
| Quick run command | `python -m pytest tests/v1/engine/test_execution_plan.py tests/v1/engine/test_output_router.py tests/v1/engine/test_executor.py tests/v1/engine/test_component_registry.py -x -q` |
| Full suite command | `python -m pytest tests/v1/engine/ -x -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXEC-01 | Subjob executes with topological order | unit | `python -m pytest tests/v1/engine/test_executor.py -x -q` | No (Wave 0) |
| EXEC-02 | Data routes correctly (main/reject/iterate) | unit | `python -m pytest tests/v1/engine/test_output_router.py -x -q` | No (Wave 0) |
| EXEC-03 | DAG construction and dependency resolution | unit | `python -m pytest tests/v1/engine/test_execution_plan.py -x -q` | No (Wave 0) |
| EXEC-07 | Stall detection raises error with diagnostics | unit | `python -m pytest tests/v1/engine/test_execution_plan.py::TestValidation -x -q` | No (Wave 0) |
| PERF-01 | Streaming chunks route without data loss | unit | `python -m pytest tests/v1/engine/test_output_router.py::TestStreamingRouting -x -q` | No (Wave 0) |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/v1/engine/test_execution_plan.py tests/v1/engine/test_output_router.py tests/v1/engine/test_executor.py tests/v1/engine/test_component_registry.py -x -q`
- **Per wave merge:** `python -m pytest tests/v1/engine/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/v1/engine/test_execution_plan.py` -- covers EXEC-03, EXEC-07
- [ ] `tests/v1/engine/test_output_router.py` -- covers EXEC-02, PERF-01
- [ ] `tests/v1/engine/test_executor.py` -- covers EXEC-01
- [ ] `tests/v1/engine/test_component_registry.py` -- covers D-02
- [ ] `tests/v1/engine/conftest.py` -- StubComponent fixture (D-17), update existing minimal conftest

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A -- batch ETL system |
| V3 Session Management | No | N/A -- no sessions |
| V4 Access Control | No | N/A -- no user access control |
| V5 Input Validation | Yes | ConfigurationError on invalid config; ExecutionPlan.validate() on graph structure |
| V6 Cryptography | No | N/A -- no crypto operations |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed job config causes infinite loop | Denial of Service | Pre-validation with cycle detection via TopologicalSorter; runtime stall detection with timeout |
| Registry name collision allows component substitution | Spoofing | ComponentRegistry.register() raises ValueError on duplicate names |
| RunIf condition injection | Tampering | TriggerManager already uses sandboxed eval with restricted globals (Phase 1 fix) |

## Sources

### Primary (HIGH confidence)
- `src/v1/engine/engine.py` -- Current engine implementation (868 lines), read in full
- `src/v1/engine/base_component.py` -- Phase 1 rewritten BaseComponent, read in full
- `src/v1/engine/trigger_manager.py` -- Phase 1 rewritten TriggerManager, read in full
- `src/v1/engine/global_map.py` -- Phase 1 rewritten GlobalMap, read in full
- `src/v1/engine/context_manager.py` -- Phase 1 rewritten ContextManager, read in full
- `src/v1/engine/base_iterate_component.py` -- Phase 1 rewritten BaseIterateComponent, read in full
- `src/v1/engine/exceptions.py` -- Exception hierarchy, read in full
- `src/converters/talend_to_v1/components/registry.py` -- Decorator-based registry pattern (converter), read in full
- `src/converters/talend_to_v1/components/__init__.py` -- Import-triggered auto-registration pattern, read in full
- Python 3.12 `graphlib.TopologicalSorter` -- Tested in session, API verified
- `tests/talend_xml_samples/converted_jsons/Job_tFileRowCount_0.1.json` -- Multi-subjob config, read in full
- `tests/talend_xml_samples/converted_jsons/Job_tContextLoad_0.1.json` -- OnComponentOk trigger config, read in full

### Secondary (MEDIUM confidence)
- [Talend Job Design Patterns Part 2](https://www.talend.com/resources/talend-job-design-patterns-and-best-practices-part-2/) -- Subjob execution model, data flow lifecycle
- [Talend Job Design Patterns Part 4](https://www.talend.com/resources/talend-job-design-patterns-and-best-practices-part-4/) -- Memory management, lookup models
- [Talend Community Forum: Subjob execution order](http://www.talendforge.org/forum/viewtopic.php?pid=55154) -- Unconnected subjob ordering is non-deterministic

### Tertiary (LOW confidence)
- None -- all claims verified against source code or official Talend docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib, verified in runtime
- Architecture: HIGH -- 5-file split is locked decision, patterns verified against converter codebase
- Pitfalls: HIGH -- identified from reading actual engine.py code and Phase 1 fix history
- Data flow lifecycle: MEDIUM -- based on Talend docs and inference, not direct Talend source code

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (stable domain, no external dependencies changing)
