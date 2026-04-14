# Architecture Research: Engine Execution Restructuring

**Domain:** Component-based ETL engine execution (Talend migration)
**Researched:** 2026-04-14
**Confidence:** HIGH (based on codebase analysis + Talend documentation + ETL orchestration patterns)

## Current State Analysis

The engine (`src/v1/engine/engine.py`) has a working but fragile architecture. The `execute()` method is a ~130-line monolithic loop that intermixes four distinct concerns:

1. **Subjob lifecycle** -- tracking which subjobs are active, detecting completion, activating triggered subjobs
2. **Component scheduling** -- determining which components can execute based on input readiness and subjob activation
3. **Data flow routing** -- storing component output DataFrames and wiring them to downstream inputs
4. **Iterate orchestration** -- re-executing downstream subjobs per iteration item

These concerns are tightly coupled inside a single `while` loop with nested helper closures. The iterate handling (`_execute_iterate_component`) duplicates significant logic from the main loop. The trigger manager has bugs around OnSubjobOk timing (fires per-component instead of waiting for full subjob completion in some paths).

### What Works

- Component registry pattern (static dict mapping types to classes)
- BaseComponent template method (`execute()` -> `_process()`)
- BaseIterateComponent abstraction (iterator pattern with `prepare_iterations`/`has_next_iteration`/`set_iteration_globalmap`)
- Infrastructure services (GlobalMap, ContextManager, TriggerManager) as separate classes
- JSON config structure with explicit flows, triggers, and subjobs sections

### What Does Not Work

- OnSubjobOk triggers fire prematurely (checked per-component, not per-subjob-completion)
- Iterate component execution duplicates the scheduling/flow-routing logic
- No iterate engine components exist (BaseIterateComponent is unused -- no tFlowToIterate, tFileList, tFileExist)
- Reject flow data is silently dropped in streaming mode
- Component re-execution during iterate clears `executed_components` set but not `data_flows` cleanly
- The `can_execute` closure captures mutable state by reference, making debugging difficult
- No separation between "build execution plan" and "run execution plan"

## Recommended Architecture

### System Overview

```
+--------------------------------------------------------------------+
|                         ETLEngine                                   |
|  (Orchestrator -- owns lifecycle, delegates execution)              |
+--------------------------------------------------------------------+
|                                                                     |
|  +-----------------------+    +-----------------------------+       |
|  |   ExecutionPlanner    |    |    SubjobExecutor           |       |
|  |                       |    |                             |       |
|  |  - Build DAG from     |    |  - Execute one subjob       |       |
|  |    flows/triggers     |    |  - Topological sort within  |       |
|  |  - Topological sort   |    |  - Manage data_flows scope  |       |
|  |    subjobs            |    |  - Handle iterate loops     |       |
|  |  - Identify initial   |    |  - Report completion status |       |
|  |    vs triggered       |    |                             |       |
|  +-----------+-----------+    +-------------+---------------+       |
|              |                              |                       |
|  +-----------v------------------------------v-----------+           |
|  |               ComponentExecutor                      |           |
|  |                                                      |           |
|  |  - Resolve expressions (Java, context)               |           |
|  |  - Gather input data from data_flows                 |           |
|  |  - Call component.execute()                          |           |
|  |  - Route outputs (main/reject/named) to data_flows   |           |
|  |  - Update stats and GlobalMap                        |           |
|  +------------------------------------------------------+           |
|                                                                     |
|  +-------------------+  +-------------------+  +-----------------+  |
|  |    GlobalMap       |  | ContextManager    |  | TriggerManager  |  |
|  |  (state store)     |  | (variable res.)   |  | (orchestration) |  |
|  +-------------------+  +-------------------+  +-----------------+  |
|                                                                     |
|  +--------------------------------------------------------------+   |
|  |                    Component Layer                            |   |
|  |  BaseComponent (template method)                             |   |
|  |  BaseIterateComponent (iterator pattern)                     |   |
|  |  50+ concrete components organized by category               |   |
|  +--------------------------------------------------------------+   |
+---------------------------------------------------------------------+
```

### Component Responsibilities

| Component | Responsibility | Current Location | Refactor Action |
|-----------|----------------|------------------|-----------------|
| ETLEngine | Job lifecycle, initialization, cleanup, top-level orchestration | `engine.py` | Keep, but extract execution logic out |
| ExecutionPlanner | Build execution plan: subjob ordering, initial vs triggered, DAG validation | Mixed into `execute()` | Extract as new class or module |
| SubjobExecutor | Execute all components within a single subjob in topological order | Mixed into `execute()` + `_execute_iterate_component()` | Extract as new class or methods |
| ComponentExecutor | Execute one component: input gathering, expression resolution, output routing | `_execute_component()` | Clean up, make output routing explicit |
| TriggerManager | Evaluate triggers, track subjob completion, fire downstream subjobs | `trigger_manager.py` | Fix OnSubjobOk semantics, add iterate awareness |
| GlobalMap | Key-value state store for component stats and inter-component variables | `global_map.py` | Fix `get()` signature bug, add scoped snapshots for iterate |
| ContextManager | Resolve `${context.var}` patterns in config strings | `context_manager.py` | Minor fixes only |
| BaseComponent | Template method for data-processing components | `base_component.py` | Stable, minor cleanup |
| BaseIterateComponent | Iterator pattern for loop-producing components | `base_iterate_component.py` | Stable, needs concrete implementations |

## Architectural Patterns

### Pattern 1: Subjob-Level Execution (Extract from Monolith)

**What:** Instead of one big loop that processes all components across all subjobs, split execution into two levels: (1) subjob scheduling and (2) intra-subjob component execution.

**When to use:** Any time the engine executes a job with multiple subjobs connected by triggers.

**Trade-offs:** Slightly more classes, but each is testable in isolation. The current monolithic loop is untestable because it requires a full job config to exercise any path.

**Example:**
```python
class ETLEngine:
    def execute(self) -> Dict[str, Any]:
        plan = self._build_execution_plan()

        for subjob_id in plan.initial_subjobs:
            self._execute_subjob(subjob_id)

        # Triggers may have activated more subjobs
        while plan.has_pending_triggered_subjobs():
            subjob_id = plan.next_triggered_subjob()
            self._execute_subjob(subjob_id)

    def _execute_subjob(self, subjob_id: str) -> str:
        """Execute all components in a subjob in topological order."""
        components = self._get_subjob_components_in_order(subjob_id)

        for comp_id in components:
            status = self._execute_component(comp_id)

            # Handle iterate: re-execute downstream subjob per item
            if isinstance(self.components[comp_id], BaseIterateComponent):
                self._handle_iterate(comp_id, self.components[comp_id])

        # Check triggers after subjob completion
        subjob_status = self._get_subjob_status(subjob_id)
        self._fire_subjob_triggers(subjob_id, subjob_status)
        return subjob_status
```

### Pattern 2: Topological Sort Within Subjobs

**What:** Components within a subjob form a DAG via their flow connections. Use Kahn's algorithm (BFS with in-degree tracking) to determine execution order, rather than the current "check all components repeatedly" approach.

**When to use:** Every subjob execution. The current approach re-scans all components after each execution, which is O(n^2) in the number of components.

**Trade-offs:** Requires building a dependency graph at plan time. Pays for itself in correctness (guaranteed to find the right order) and performance (single pass).

**Example:**
```python
def _get_subjob_components_in_order(self, subjob_id: str) -> List[str]:
    """Topological sort of components within a subjob using Kahn's algorithm."""
    subjob_comps = set(self.subjob_components[subjob_id])
    # Build adjacency and in-degree from flows
    in_degree = {c: 0 for c in subjob_comps}
    adj = {c: [] for c in subjob_comps}

    for flow in self.job_config.get('flows', []):
        src, dst = flow['from'], flow['to']
        if src in subjob_comps and dst in subjob_comps:
            adj[src].append(dst)
            in_degree[dst] += 1

    # BFS from zero in-degree nodes
    queue = deque(c for c, deg in in_degree.items() if deg == 0)
    order = []
    while queue:
        comp_id = queue.popleft()
        order.append(comp_id)
        for neighbor in adj[comp_id]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return order
```

### Pattern 3: Iterate as Subjob Re-execution

**What:** When an iterate component fires, it does not re-run the main execution loop. Instead, it calls `_execute_subjob()` for the downstream subjob once per iteration item, with proper state reset between iterations.

**When to use:** tFlowToIterate, tFileList, tFileExist -- any component connected via an `iterate` flow type.

**Trade-offs:** Requires careful state management -- data_flows for the downstream subjob must be cleared between iterations, but data_flows for other subjobs must be preserved.

**This is the critical architecture decision.** The current `_execute_iterate_component()` duplicates the scheduling loop and has bugs around state cleanup. The correct pattern is:

```python
def _handle_iterate(self, iterate_comp_id: str, component: BaseIterateComponent):
    """Re-execute downstream subjob for each iteration item."""
    target_subjob_id = self._find_iterate_target_subjob(iterate_comp_id)
    if not target_subjob_id:
        return

    while component.has_next_iteration():
        item = component.get_next_iteration_context()

        # Reset state for downstream subjob only
        self._reset_subjob_state(target_subjob_id)

        # Execute the downstream subjob
        status = self._execute_subjob(target_subjob_id)

        # Collect iteration stats
        component.update_iteration_stats(self._get_subjob_stats(target_subjob_id))

        # Fire triggers from downstream subjob (chained triggers)
        self._fire_subjob_triggers(target_subjob_id, status)

    component.finalize_iterations()

def _reset_subjob_state(self, subjob_id: str):
    """Clear execution state for a subjob so it can be re-executed."""
    for comp_id in self.subjob_components[subjob_id]:
        self.executed_components.discard(comp_id)
        self.failed_components.discard(comp_id)
        self.trigger_manager.triggered_components.discard(comp_id)

    # Clear data flows originating from this subjob
    for flow in self.job_config.get('flows', []):
        if flow['from'] in self.subjob_components[subjob_id]:
            self.data_flows.pop(flow['name'], None)
```

### Pattern 4: Explicit Output Routing

**What:** Replace the current inline flow-matching logic in `_execute_component()` with a dedicated output routing method that handles all flow types consistently.

**When to use:** After every component execution.

**Trade-offs:** Slightly more code, but fixes the reject-flow-dropped-in-streaming bug and makes the routing logic testable.

```python
def _route_component_outputs(self, comp_id: str, result: Dict[str, Any]):
    """Route component outputs to the correct data flow slots."""
    for flow in self.job_config.get('flows', []):
        if flow['from'] != comp_id:
            continue

        flow_type = flow.get('type', 'flow')
        flow_name = flow['name']

        if flow_type in ('flow', 'filter'):
            data = result.get('main')
        elif flow_type == 'reject':
            data = result.get('reject')
        elif flow_type == 'iterate':
            continue  # Iterate flows are handled by _handle_iterate
        else:
            data = result.get(flow_type) or result.get('main')

        if data is not None:
            self.data_flows[flow_name] = data
        else:
            logger.debug(f"No '{flow_type}' output from {comp_id} for flow {flow_name}")
```

## Data Flow

### Job Execution Flow

```
JSON Config
    |
    v
ETLEngine.__init__()
    |-- Load config
    |-- Initialize GlobalMap, ContextManager, TriggerManager
    |-- Start JavaBridgeManager (if java_config.enabled)
    |-- Instantiate components from COMPONENT_REGISTRY
    |-- Parse triggers (top-level + component-level)
    |-- Identify subjobs (from config or auto-detect via flow connectivity)
    |
    v
ETLEngine.execute()
    |
    v
Build Execution Plan
    |-- Classify subjobs: initial (no incoming triggers) vs triggered
    |-- Build intra-subjob component ordering (topological sort per subjob)
    |
    v
Execute Initial Subjobs (in order)
    |
    +-- For each initial subjob:
    |       |
    |       v
    |   _execute_subjob(subjob_id)
    |       |-- Topological sort components within subjob
    |       |-- For each component:
    |       |       |
    |       |       v
    |       |   _execute_component(comp_id)
    |       |       |-- Gather input data from data_flows
    |       |       |-- component.execute(input_data)
    |       |       |       |-- Resolve {{java}} expressions
    |       |       |       |-- Resolve ${context.var}
    |       |       |       |-- Call _process(input_data)
    |       |       |       |-- Return {main: DataFrame, reject: DataFrame, ...}
    |       |       |-- Route outputs to data_flows
    |       |       |-- Update GlobalMap stats
    |       |       |
    |       |       v
    |       |   If iterate component:
    |       |       |-- For each iteration item:
    |       |       |       |-- Set globalMap variables
    |       |       |       |-- Reset downstream subjob state
    |       |       |       |-- _execute_subjob(downstream_subjob_id)
    |       |       |       |-- Collect iteration stats
    |       |
    |       v
    |   After subjob completes:
    |       |-- Evaluate OnSubjobOk/OnSubjobError triggers
    |       |-- Activate triggered subjobs
    |
    v
Execute Triggered Subjobs (as they become active)
    |-- Same pattern as above, but only runs when trigger fires
    |
    v
Collect final stats, cleanup JavaBridge, return results
```

### Data Flow Between Components

```
Component A (source)                     Component B (consumer)
+-----------+                            +-----------+
|           |--[main]--> data_flows ---->|           |
| _process()|           {"row1": df}     | _process()|
|           |--[reject]-> data_flows --->|           |
+-----------+           {"row1_reject":  +-----------+
                          df_reject}

data_flows dict acts as the message bus:
  - Key: flow name from JSON config (e.g., "row1", "row2")
  - Value: pandas DataFrame
  - Single input: component gets DataFrame directly
  - Multiple inputs: component gets Dict[flow_name, DataFrame]
```

### State Management During Iterate

```
Iteration 1:                    Iteration 2:
+--------------------------+    +--------------------------+
| GlobalMap:               |    | GlobalMap:               |
|   row1.filepath = "a.csv"|    |   row1.filepath = "b.csv"|
|   tFTI_1_CURRENT = 0    |    |   tFTI_1_CURRENT = 1    |
+--------------------------+    +--------------------------+
         |                               |
         v                               v
  Execute downstream subjob       Execute downstream subjob
  (all components fresh)          (all components fresh)
         |                               |
         v                               v
  data_flows populated            data_flows populated
  stats collected                 stats collected
         |                               |
         v                               v
  Clear downstream state          Clear downstream state
  (executed_components,           (executed_components,
   data_flows for subjob)          data_flows for subjob)
```

## Recommended Project Structure

The engine already has a clean directory structure. The refactoring should not change the directory layout -- it should extract logic within `engine.py` into well-defined methods (or at most a helper module), not create a new package hierarchy.

```
src/v1/engine/
|-- engine.py                    # ETLEngine class (refactored, smaller execute())
|-- base_component.py            # BaseComponent ABC (stable)
|-- base_iterate_component.py    # BaseIterateComponent ABC (stable)
|-- global_map.py                # GlobalMap state store (minor fix)
|-- context_manager.py           # ContextManager (minor fix)
|-- trigger_manager.py           # TriggerManager (fix OnSubjobOk)
|-- java_bridge_manager.py       # JavaBridgeManager (stable)
|-- python_routine_manager.py    # PythonRoutineManager (stable)
|-- exceptions.py                # Exception hierarchy (stable)
|-- components/
|   |-- file/                    # File I/O components
|   |-- transform/               # Data transformation components
|   |-- aggregate/               # Aggregation components
|   |-- context/                 # Context management components
|   |-- control/                 # Flow control components (tDie, tWarn, tSleep)
|   +-- iterate/                 # NEW: Iterate components (tFlowToIterate, tFileList, tFileExist)
```

### Structure Rationale

- **No new packages for execution planner/executor:** The refactoring extracts methods within `ETLEngine`, not new classes. This is pragmatic -- the engine is not large enough to warrant a multi-class decomposition, and keeping it in one file makes the execution flow readable.
- **New `components/iterate/` directory:** Mirrors the converter's directory structure. Contains concrete implementations of `BaseIterateComponent`.
- **Infrastructure files unchanged:** GlobalMap, ContextManager, TriggerManager are already properly separated. They need bug fixes, not restructuring.

## Anti-Patterns

### Anti-Pattern 1: Monolithic Execution Loop

**What people do:** Put all scheduling, execution, routing, and state management in a single loop with closures and mutable shared state.
**Why it is wrong:** Cannot test individual concerns. Bugs in trigger firing affect data routing. Adding iterate support requires duplicating the loop.
**Do this instead:** Extract `_execute_subjob()`, `_execute_component()`, and `_route_component_outputs()` as distinct methods with clear contracts. The main loop only handles subjob-level orchestration.

### Anti-Pattern 2: Checking All Components After Each Execution

**What people do:** After each component executes, re-scan all components to find newly ready ones (O(n^2)).
**Why it is wrong:** Slow for large jobs and makes execution order non-deterministic. The current `for pending_comp in self.components` scan at line 496 of engine.py is the worst offender.
**Do this instead:** Pre-compute topological order per subjob. Execute in order. The only dynamic scheduling needed is at the subjob level (trigger-based).

### Anti-Pattern 3: Duplicating Execution Logic for Iterate

**What people do:** Write a separate `_execute_iterate_component()` that reimplements the scheduling loop for iterate downstream execution.
**Why it is wrong:** Two copies of scheduling logic that must stay in sync. Bugs fixed in one are not fixed in the other. The current iterate handler at line 622 has its own flow-following logic, trigger checking, and state cleanup that diverges from the main loop.
**Do this instead:** Iterate handling should call `_execute_subjob()` -- the same method used by the main loop. The only iterate-specific logic is: set globalMap, reset downstream state, call execute_subjob, collect stats.

### Anti-Pattern 4: Trigger Evaluation on Every Component Completion

**What people do:** Check OnSubjobOk triggers after every component completes, using the component's status as the trigger input.
**Why it is wrong:** OnSubjobOk should only fire after ALL components in the subjob complete. Checking per-component can fire the trigger prematurely if a later component in the same subjob fails.
**Do this instead:** Only evaluate OnSubjobOk/OnSubjobError triggers after `_execute_subjob()` returns, using the subjob's aggregate status. OnComponentOk/OnComponentError triggers can still fire per-component.

### Anti-Pattern 5: Mutable Config During Execution

**What people do:** `context_manager.resolve_dict(self.config)` replaces `self.config` in-place during `BaseComponent.execute()`, which means a component cannot be re-executed with its original config (needed for iterate).
**Why it is wrong:** Iterate components need to re-execute downstream components with fresh config resolution (different globalMap values per iteration).
**Do this instead:** Resolve config into a local variable, not `self.config`. Or snapshot and restore config around iterate re-execution.

## Integration Points

### Internal Boundaries

| Boundary | Communication | Direction | Notes |
|----------|---------------|-----------|-------|
| ETLEngine <-> TriggerManager | Method calls | Engine asks "what fired?" after subjob completes | Fix: only ask after full subjob completion for OnSubjobOk |
| ETLEngine <-> Components | `component.execute(input_data)` | Engine provides input, component returns result dict | Stable interface, no changes needed |
| ETLEngine <-> data_flows | Dict read/write | Engine writes outputs, reads for next component's inputs | Key: flow names must match between JSON config and runtime |
| Components <-> GlobalMap | `global_map.put/get` | Bidirectional | Fix: `get()` has wrong signature (references undefined `default`) |
| Components <-> ContextManager | `context_manager.resolve_dict()` | Component reads resolved config | Fix: do not mutate `self.config` |
| Components <-> JavaBridge | `java_bridge.execute_batch_one_time_expressions()` | Component sends expressions, gets results | Stable, works via Py4J |
| BaseIterateComponent <-> ETLEngine | `has_next_iteration()`, `get_next_iteration_context()` | Engine drives iteration loop | Clean interface, just needs engine-side implementation |

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Java/JVM (Py4J) | Subprocess + gateway on dynamic port | Started by JavaBridgeManager, killed on cleanup. Arrow for DataFrame transfer. |
| File system | Direct I/O via pandas/open() | All file components read/write directly. No abstraction layer (appropriate for batch ETL). |
| Databases (future) | Connection components manage lifecycle | Currently commented out. Will need connection pooling and transaction management. |

## Scaling Considerations

| Concern | At 10 jobs/day | At 100 jobs/day | At 1000 jobs/day |
|---------|----------------|-----------------|-------------------|
| Execution time | Single-threaded fine | Single-threaded fine | Consider parallel subjob execution |
| Memory | DataFrame-at-a-time OK | Streaming mode for large files | Need memory profiling per job |
| JVM startup | ~2s per job with Java | Negligible | Consider persistent JVM pool |
| Error recovery | Manual re-run | Need job-level checkpointing | Need component-level checkpointing |

### Scaling Priorities

1. **First bottleneck:** Large DataFrames in memory. The streaming mode exists but has bugs (reject data dropped). Fix streaming before optimizing.
2. **Second bottleneck:** JVM cold start for Java expressions. Not a problem until job volume is very high. A persistent JVM gateway could eliminate this.

## Build Order (Dependencies Between Components)

The refactoring has clear dependencies that dictate build order:

```
Phase 1: Fix infrastructure bugs
    GlobalMap.get() signature fix
    TriggerManager OnSubjobOk timing fix
    BaseComponent config mutation fix
         |
         v
Phase 2: Extract execution methods from monolithic loop
    _execute_subjob() with topological sort
    _route_component_outputs() for explicit routing
    _build_execution_plan() for initial vs triggered classification
    (Test: existing jobs still produce same results)
         |
         v
Phase 3: Implement iterate execution pattern
    _handle_iterate() calling _execute_subjob()
    _reset_subjob_state() for clean re-execution
    (Depends on: _execute_subjob being extracted)
         |
         v
Phase 4: Implement concrete iterate components
    tFlowToIterate engine component
    tFileList engine component
    tFileExist engine component
    Register in COMPONENT_REGISTRY
    Add to components/iterate/ directory
    (Depends on: iterate execution pattern working)
         |
         v
Phase 5: Fix streaming mode and reject flows
    Fix reject data routing in streaming mode
    Fix chunk processing data loss
    (Can be done in parallel with Phase 4)
```

**Critical path:** Phases 1-2-3-4 are sequential. Phase 5 is independent.

**Phase ordering rationale:**
- Infrastructure bugs must be fixed first because the extraction in Phase 2 will bake current behavior into new methods -- fixing bugs after extraction means fixing them in two places.
- Extraction (Phase 2) must precede iterate (Phase 3) because the iterate pattern depends on calling `_execute_subjob()` as a reusable method.
- Concrete iterate components (Phase 4) cannot work until the engine knows how to handle iterate execution (Phase 3).
- Streaming fixes (Phase 5) are independent because they affect `BaseComponent._execute_streaming()` and output routing, not the subjob/trigger orchestration.

## Sources

- Talend Studio documentation on trigger connections: https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-06/trigger-connections-for-job
- Talend tFlowToIterate component documentation: https://help.qlik.com/talend/en-US/components/7.3/orchestration/tflowtoiterate
- Talend community on OnSubjobOk vs OnComponentOk semantics: https://community.talend.com/s/article/What-is-the-difference-between-OnSubjobOK-and-OnComponentOK-D3hS6
- Graph theory modeling of ETL workflows (topological sort): https://medium.com/@devendra631995/graph-theory-based-modeling-of-etl-workflows-for-dependency-resolution-and-optimization-using-d94fc60777de
- Topological sorting in ETL processes: https://d-one.ai/documents/Topological-sorting-and-the-ETL-process-Joonas-Asikainen-D1-Solutions-Zuerich.pdf
- Talend job design patterns and best practices: https://www.talend.com/resources/talend-job-design-patterns-and-best-practices-part-1/
- Extract method refactoring pattern: https://refactoring.guru/extract-method
- ETL error handling best practices: https://pyquesthub.com/mastering-etl-error-handling-best-practices-for-data-engineers
- Codebase analysis: `src/v1/engine/engine.py`, `src/v1/engine/base_component.py`, `src/v1/engine/base_iterate_component.py`, `src/v1/engine/trigger_manager.py`, `src/v1/engine/global_map.py`, `src/v1/engine/context_manager.py`

---
*Architecture research for: DataPrep ETL Engine Execution Restructuring*
*Researched: 2026-04-14*
