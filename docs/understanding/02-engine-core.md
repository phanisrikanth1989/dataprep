# Engine Core & Services

This document is a deep dive on the **v1 execution engine** (`src/v1/engine/`): the
runtime that executes JSON job configs produced by the converter. It covers the
orchestration facade (`ETLEngine`), the decorator registry, plan building, the
execution loop, subjob/trigger orchestration, data-flow routing, the two component
base classes, and the four supporting services (`GlobalMap`, `ContextManager`,
`TriggerManager`, `PythonRoutineManager`) plus the exception hierarchy and the
3-phase expression resolution every component runs.

Audience: engineers extending this codebase and raising per-module test coverage to
the 95% floor. File references use `path:line` where a specific location matters.

> **CRITICAL (HEAD-of-branch regressions): the engine package does not import.**
> Two committed bugs (commit `0ad1ee0`) currently break the entire engine:
> 1. `src/v1/engine/engine.py:225-226` has a missing comma after
>    `trigger.get('condition')` before `output_id=...`, a hard `SyntaxError`.
>    `import src.v1.engine` raises `invalid syntax. Perhaps you forgot a comma?`.
> 2. `src/v1/engine/trigger_manager.py:142` defines `add_trigger` at module level
>    (indent 0) instead of inside `TriggerManager`. Every following method
>    (`register_subjob`, `set_component_status`, `should_fire_trigger`, ...) becomes
>    a local closure of that function, so `TriggerManager` has only `__init__` as a
>    real method and the whole trigger subsystem raises `AttributeError` at runtime.
>
> These are verified present in the current source. Any coverage/test work on the
> engine must fix these first; pytest collection fails on the `SyntaxError` because
> `conftest` imports `ETLEngine`. See [Known Critical Bugs](#known-critical-bugs).

---

## 1. Architecture at a Glance

The engine is a **facade delegating to focused collaborators**. `ETLEngine` wires up
shared services and three plan/execution objects, then hands control to the
`Executor`:

```
                       ETLEngine  (facade / wiring)
                           |
        +------------------+------------------+----------------------+
        |                  |                  |                      |
   ExecutionPlan      OutputRouter         Executor            Services:
   (DAG + topo sort)  (_data_flows dict)  (main loop)         GlobalMap
                                                              ContextManager
                                                              TriggerManager
                                                              JavaBridgeManager
                                                              PythonRoutineManager
                                                              Oracle/MSSql managers
                           |
                    COMPONENT_REGISTRY  --instantiates-->  BaseComponent subclasses
                                                           BaseIterateComponent subclasses
```

| Object | File | LOC | Responsibility |
| --- | --- | --- | --- |
| `ETLEngine` | `engine.py` | 316 | Load config, wire services, instantiate components, build plan/router/executor, expose `execute()`/`run_job()`/CLI, cleanup. |
| `Executor` | `executor.py` | 882 | Main execution loop; iterative subjob deque; topo component execution; iterate body driver; trigger firing; tDie halt; stall detection. |
| `ExecutionPlan` | `execution_plan.py` | 641 | DAG construction, per-subjob topo sort, subjob auto-detect, trigger edges, iterate body subgraphs, cycle/reachability validation. |
| `ComponentRegistry` | `component_registry.py` | 73 | Decorator name->class map (V1 PascalCase + Talend `t`-prefixed aliases). |
| `OutputRouter` | `output_router.py` | 395 | Owns `_data_flows`; routes outputs, resolves inputs, readiness checks, subjob-scoped flow cleanup. |
| `BaseComponent` | `base_component.py` | 1337 | Template-method lifecycle for every component; expression resolution; schema validation/coercion; stats. |
| `BaseIterateComponent` | `base_iterate_component.py` | 120 (one reader) / 428 (another) | Iterate-component base; 8-hook lifecycle driven externally by the Executor. |
| `GlobalMap` | `global_map.py` | 105 | Talend-style key/value + NB_LINE stats store. |
| `ContextManager` | `context_manager.py` | 410 | Typed context storage + recursive `${context.X}` resolution. |
| `TriggerManager` | `trigger_manager.py` | 401/507 | OnSubjobOk/OnComponentOk/RunIf flow control; sandboxed Java condition eval. |
| `PythonRoutineManager` | `python_routine_manager.py` | 241 | Dynamic load of user Python routines into component namespaces. |
| `exceptions.py` | `exceptions.py` | 61 | `ETLError` hierarchy. |

---

## 2. ETLEngine -- the Facade

`ETLEngine.__init__(job_config)` (`engine.py:33`) accepts a dict or a JSON path. It is
a wiring step that:

1. Loads the config (string path -> `json.load`).
2. Conditionally starts the **Java bridge** when `job_config['java_config']['enabled']`
   is true (`engine.py:44-58`); on failure it stops the half-started bridge and
   re-raises.
3. Conditionally constructs the **PythonRoutineManager**, **OracleConnectionManager**,
   and **MSSqlConnectionManager** (the latter two auto-detected from component types
   or an `*_config.enabled` flag).
4. Instantiates every component from `REGISTRY` and decorates it with `subjob_id`,
   `inputs`/`outputs`, per-flow schemas, and the shared services. Notably
   `output_schema` / `reject_schema` are **injected by the engine** (`engine.py:187-188`),
   not read from the component config.
5. Builds `ExecutionPlan`, `OutputRouter`, and `Executor`.

`execute()` delegates to `Executor.execute_job()` and decorates the returned stats
(status, timing, per-component, plus a `global_map` snapshot). `ETLEngine` implements
the **context-manager protocol** so `_cleanup()` (Java bridge stop, Oracle/MSSql close)
runs on success, exception, and `__del__`. The API layer relies on this:
`with ETLEngine(job_config) as engine:` guarantees JVM/DB teardown even when
`execute()` raises.

### Interfaces

```python
ETLEngine(job_config).execute() -> dict             # stats
run_job(job_config_path, context_overrides) -> dict # convenience wrapper
ETLEngine.set_context_variable(name, value)
ETLEngine.get_execution_stats()
# CLI:
python -m src.v1.engine.engine <job_config.json> --context_param KEY=VALUE
```

### Smells worth noting
- `component.is_subjob_start` is set on every component (`engine.py:152`) but never
  read anywhere -- subjob topology is driven entirely by `ExecutionPlan`. Dead
  metadata: wire it (e.g. validate entry points) or drop it.

---

## 3. COMPONENT_REGISTRY

A decorator-based map from type-name strings to component classes
(`component_registry.py`). It mirrors the converter's registry pattern:

- Populated at **import time** via side-effects from `components/__init__.py`
  (the engine imports `from . import components as _components` in `engine.py:20`).
- Each class registers under **both** its V1 PascalCase name and one or more Talend
  `t`-prefixed aliases, e.g. `@REGISTRY.register('Map', 'tMap')`,
  `@REGISTRY.register('UniqueRow', 'tUniqRow', 'tUniqueRow', 'tUnqRow')`.
- **Idempotent** re-registration is allowed; registering a *conflicting* class for an
  existing name raises.

```python
REGISTRY.register(*names)  # decorator
REGISTRY.get(name)         # class or None; ETLEngine calls REGISTRY.get(node.component_type)
```

This dual-key aliasing is the dispatch contract: the converter emits a `type` (often
the Talend name for unimplemented components, PascalCase for implemented ones) and the
engine resolves it here. A `type` that is not registered cannot be instantiated --
relevant to the converter's "keep `t`-prefix means unimplemented" convention and to
`tFileOutputPositional`, whose engine class exists but was historically **not** in
the registry.

---

## 4. ExecutionPlan -- DAG Construction & Validation

`ExecutionPlan(components, flows, triggers, subjobs)` is a **pure, pre-computed data
structure**: the DAG is built and validated **once**, independent of any running
engine, then executed. This separation lets you validate a config without executing it.

It produces:

| Output | Type | Meaning |
| --- | --- | --- |
| `SubjobPlan` | dataclass | `subjob_id` + topologically-ordered `component_ids` + `frozenset` `component_set` for O(1) membership. |
| `TriggerEdge` | dataclass | `from`/`to` component, `trigger_type`, `from`/`to` subjob, optional `condition`. Drives subjob-level trigger collection. |
| `StreamingMetadata` | dataclass | Per-component `requires_full_data`/`streamable` flags. |
| `initial_subjobs` | list | Subjobs with no inbound trigger; seed the execution deque. |

Construction details:
- **Topological sort** per subjob via `graphlib.TopologicalSorter`; `CycleError` ->
  validation failure.
- **Subjob auto-detection** via connected-components BFS over the flow graph when
  subjobs are not explicitly provided.
- **Iterate body subgraph extraction**: an iterate source's downstream body is pulled
  out as its own `SubjobPlan` re-executed per item.
- `validate()` checks reachability (no unreachable subjobs), cycles, and
  **nested-iterate depth** (max depth 1; nested iterate raises `ConfigurationError`,
  a documented Phase-10 parity gap).

### Streaming metadata is computed but unused
`StreamingMetadata.requires_full_data` is derived from `_REQUIRES_FULL_DATA_TYPES`
(`execution_plan.py:32`) for aggregate/sort/unique components, but **the Executor
never reads it**. Streaming vs full-data is actually decided in
`BaseComponent._select_mode` purely by `MEMORY_THRESHOLD_MB` (5120 MB,
`base_component.py:146`). This is a real correctness risk: a sort/aggregate over a
>5 GB frame could be auto-switched to per-chunk STREAMING by the memory heuristic
even though the plan marks it `requires_full_data=True`, producing wrong (per-chunk)
results. See [Open Questions](#open-questions).

### Key interfaces
```python
ExecutionPlan(...).validate()
.get_subjob_plan / .get_iterate_body_plan
.get_all_trigger_edges_from_subjob
.initial_subjobs / .component_to_subjob
```

---

## 5. Executor -- the Main Loop

`Executor.execute_job()` (`executor.py`) owns execution. The design is deliberately
**iterative (deque-based), not recursive**, to survive long trigger/subjob chains
without hitting Python's recursion limit (covered by
`TestIterativeTriggerFiring.test_long_trigger_chain_no_recursion_error`).

### 5.1 The loop

```
execute_job():
  queue = deque(execution_plan.initial_subjobs)         # seed (executor.py:117-141)
  while queue:
    subjob = queue.popleft()
    _execute_subjob_plan(subjob)                         # THE building block
    _collect_triggered_subjobs(...)  -> append to queue  # subjob-level triggers
  finalize streaming sinks
  detect stalls                                          # (executor.py:168-188)
  return stats
```

`_execute_subjob_plan` iterates the subjob's components in **topological order**,
calling `_execute_component` for each:

```
_execute_component(comp_id):
  input  = OutputRouter.get_input_data(comp_id)   # DataFrame OR dict[flow->DataFrame]
  result = component.execute(input)               # BaseComponent template
  OutputRouter.route_outputs(comp_id, result)     # map main/reject/iterate/named keys
  _fire_component_triggers(comp_id)               # OnComponentOk/Error/RunIf
```

After each component, OnComponentOk/Error/RunIf are evaluated; after each *subjob*,
OnSubjobOk/Error are evaluated. Newly triggered subjobs are appended to the deque.

### 5.2 Iterate body driver (Phase 10)

When a component is an iterate source, `_execute_iterate_body` re-runs the body
`SubjobPlan` once **per item**:

- Resets body components and discards them from `executed_components` each iteration
  (`executor.py:506-516`), so each iteration starts clean (relies on
  `BaseComponent.reset()` re-deriving config from `_original_config`).
- Drains per-iteration reject flows into a buffer (`OutputRouter.drain_reject_flows`)
  and, at the end, routes the accumulated rejects as the iterate **source's** reject
  output (decision D-D4).
- Iterate variables flow through `globalMap` (key `f"{id}_CURRENT_ITERATION"`), **not**
  through `_data_flows` -- iterate flows carry no data.
- WR-05 asserts and WR-06 mid-loop `ConfigurationError` handling guard against silent
  iterate failures.

### 5.3 tDie termination & stall detection

- **tDie**: `_execute_component` (`executor.py:664-685`) detects an `exit_code`
  attribute on the raised exception, its `.cause`, or `__cause__`, and sets
  `_job_terminated` to halt the whole job. Because `BaseComponent.execute` wraps every
  `_process` exception in a fresh `ComponentExecutionError(cause=e)`, detection relies
  on `exit_code` surviving **exactly one** wrap level -- a fragile 3-level walk
  (`e -> e.cause -> e.__cause__`); a double-wrap would downgrade a job-halt to an
  ordinary component error.
- **Stall detection** (`executor.py:168-188`): if components remain unexecuted with no
  way to get input, raise `ConfigurationError` naming the stuck components and their
  missing input flows. Correctly ordered **after** streaming-sink finalization (CR-01)
  so output files always close. Only flags components in *attempted* subjobs, avoiding
  false positives on conditional/untriggered subjobs.

---

## 6. OutputRouter & data_flows

`OutputRouter` owns the single `_data_flows` dict mapping **flow_name -> DataFrame**.

### Routing outputs
`route_outputs` maps a component's result dict keys (`main`/`reject`/`iterate`/named)
to downstream flow names via `_FLOW_TYPE_TO_RESULT_KEY` (`output_router.py:22-29`):

| flow_type | result key |
| --- | --- |
| `flow` | `main` |
| `reject` | `reject` |
| `filter` | `main` |
| `iterate` | `iterate` |
| `unique` | `main` (tUniqRow UNIQUE connector) |
| `duplicate` | `reject` (tUniqRow DUPLICATE connector) |

**Last-writer-wins** per flow name (`_data_flows[flow_name] = value`,
`output_router.py:134`). This is intended for the batch/chunk re-route case
(`test_route_multiple_chunks_last_wins`) but has **no guard against accidental flow
name collisions** from two distinct producers -- a converter bug emitting duplicate
flow names would surface as **silent data loss**, not an error.

### Resolving inputs
`get_input_data(comp_id)` returns a single `DataFrame` for single-input components and
`dict[flow_name -> DataFrame]` for multi-input components (Join, Unite, tMap).

### Readiness
`are_inputs_ready` correctly **skips iterate-type flows** (`output_router.py:196-202`):
iterate sources publish per-iteration variables to `globalMap`, not to `_data_flows`,
so treating an iterate edge as a required data flow would falsely block the body
consumers. This is the matching half of `route_outputs` mapping `iterate -> 'iterate'`.

### Cleanup with cross-subjob preservation
`clear_subjob_flows` frees internal flows after a subjob finishes but **preserves
cross-subjob flows whose consumers have not executed yet**. `drain_reject_flows`
buffers per-iteration rejects for the iterate driver.

```python
OutputRouter.route_outputs / get_input_data / are_inputs_ready
                / clear_subjob_flows / clear_partial_subjob_flows / drain_reject_flows
                / has_flow_data
```

---

## 7. BaseComponent -- the Template Method

`BaseComponent.execute(input_data)` (`base_component.py:204`) is the **fixed
lifecycle**. Subclasses implement only `_validate_config()` and `_process()`; they
**must not override `execute()`**.

### 7.1 The 8-step lifecycle

| Step | Action | Location |
| --- | --- | --- |
| 1 | Fresh `config = deepcopy(_original_config)` (ENG-09/ENG-21) | `:225` |
| 2 | `_validate_config()` -- structural/Rule-12 checks only | `:228` |
| 3 | `_resolve_expressions()` -- Java markers + context vars | `:231` |
| 4 | Read `die_on_error` from resolved config (default `True`) | `:234` |
| 5 | Count input rows for `NB_LINE` | `:237` |
| 6 | `_select_mode()` -- BATCH, or HYBRID -> STREAMING above 5120 MB | `:240` |
| 7 | `_execute_batch`/`_execute_streaming` -> subclass `_process()` | `:243-246` |
| 7b | `_enforce_schema_column_order` from `output_schema` | `:248` |
| 7c | `_apply_output_schema_validation` -- coerce types, precision, reject routing | `:250` |
| 8 | `_update_stats_from_result` + `_update_global_map` | `:253-254` |

`ConfigurationError` propagates as-is; any other exception is wrapped in
`ComponentExecutionError(self.id, str(e), cause=e)` (`:271-274`).

**Config immutability** is the core safety invariant: `_original_config` is deepcopied
at construction (`:180`) and never mutated; the working `config` is re-derived from it
at the start of every `execute()` (`:225`). This is what makes iterate re-execution
start from a clean, unresolved config every iteration.

### 7.2 The 3-phase expression resolution

`_resolve_expressions` (`base_component.py:319`) runs in a fixed order:

1. **Java `{{java}}` markers** (`_resolve_java_expressions`, `:339`) -- only when
   `self.java_bridge` is set. `_scan_config` recursively walks the config by dotted
   path collecting any string starting with `{{java}}` (marker stripped at offset 8,
   `:356-358`). It then syncs context + globalMap to the bridge,
   `execute_batch_one_time_expressions`, and writes results back into config by dotted
   path.
2. **Context variables** (`ContextManager.resolve_dict`, `:337`) -- substitutes
   `${context.X}` / bare `context.X` across nested dicts/lists, **skipping**
   `SKIP_RESOLUTION_KEYS = {python_code, java_code, imports}`
   (`context_manager.py:63`) so user code is never string-substituted (matching the
   "read context programmatically" contract).

(The "3-phase" framing: Java resolution + context resolution + the schema
validation/coercion phase that follows in step 7c. Steps 1-2 happen in
`_resolve_expressions`; the typed-validation phase happens in
`_apply_output_schema_validation`.)

### 7.3 Schema validation, coercion, and reject routing

After `_process`, the base class enforces column order from `output_schema`/`reject_schema`
(filling missing columns with type-correct empties via `_make_default_series`), then
`validate_schema` coerces types, applies decimal/float precision and
`treat_empty_as_null`, and either raises `DataValidationError` or routes violations to
the reject flow when `die_on_error=False`. Source components therefore **emit mostly
string data and defer typed validation** to this single chokepoint.

`_make_default_series` (`:722-775`) constructs `pd.Series` with explicit dtype (not
scalar broadcast), correctly preserving dtype on empty DataFrames and handling datetime
nullability via `pd.NaT` vs `pd.Timestamp(0)`.

### 7.4 Stats semantics (Talend parity)
`NB_LINE`/`NB_LINE_OK`/`NB_LINE_REJECT` follow Talend conventions:
**source** components (`input_rows == 0`) set `NB_LINE = main_count + reject_count`;
**transform** components set it from the input count (`:590-597`). Caveat: a transform
that legitimately receives 0 input rows is indistinguishable from a source and would
mis-count `NB_LINE` from its outputs.

### Interfaces
```python
BaseComponent.execute(input_data) -> dict      # final; do not override
.validate_schema(df, schema), .reset(), .get_stats(), .get_status(), .get_python_routines()
# subclass contract:
_validate_config() -> None    # raise ConfigurationError
_process(input_data) -> dict  # {'main', 'reject', ...named flows}
```

---

## 8. BaseIterateComponent

`BaseIterateComponent` (`base_iterate_component.py`) extends `BaseComponent` for
`tFileList`/`tFlowToIterate`/`tForeach`. It **overrides `execute()`** to *only* prime
the iterator state (it skips the data-pipeline steps); the **Executor owns the loop**
via an 8-hook lifecycle:

```
prepare / prepare_iterations / has_next_iteration / get_next_iteration_context
       / should_stop / before_iteration / set_iteration_globalmap / after_iteration / finalize
```

`get_next_iteration_context()` advances the index, calls `set_iteration_globalmap`,
and writes `f"{id}_CURRENT_ITERATION"` (the key matches Talaxie
`tFlowToIterate_main.javajet`). `update_iteration_stats` accumulates per-iteration
stats.

Re-execution safety: `execute()` rejects re-execution when status is `RUNNING` or
`SUCCESS` without an intervening `reset()` -- but **does not guard the `ERROR` state**,
so a second `execute()` after a failed iterate proceeds and rebuilds the iterator
buffer. Also note iterate `die_on_error` defaults to **False**
(`base_iterate_component.py:177`) whereas data components default **True**
(`base_component.py:234`) -- intentional but worth verifying against Talend.

---

## 9. Supporting Services

### 9.1 GlobalMap (`global_map.py`)
Talend-style dual store: a generic `_map` plus a `_component_stats` dict.
`put_component_stat` **overwrites** (does not accumulate) and mirrors into `_map` as
`<id>_<stat>` for backward compat. Convenience getters: `get_nb_line[_ok|_reject]`,
`reset_component`, `get_all`, `get_all_stats`, `clear`.

### 9.2 ContextManager (`context_manager.py`)
Typed context storage + recursive resolution. `_TYPE_CONVERTERS` maps Talend `id_*`
and Python type names to real callables; `id_Date` values are parsed to real
`datetime` objects so downstream `(Date)` casts in tMap work (`:22-44,87`).
`resolve_dict` returns a **new** dict, recursing into nested dicts/lists and skipping
`SKIP_RESOLUTION_KEYS`. `resolve_string` substitutes `str(value)` for resolved vars --
note a typed value (e.g. `id_Integer 5`, an `id_Date`) becomes its string form when
interpolated into a config string (`TriggerManager` deliberately uses `repr()` instead
to preserve types in `eval` contexts -- the asymmetry is worth a comment).

### 9.3 TriggerManager (`trigger_manager.py`)
Trigger registry + flow evaluator. Evaluates OnSubjobOk/Error, OnComponentOk/Error,
and RunIf with **sandboxed** Java-style condition eval (`eval` with `__builtins__={}`
and a whitelist of `int/str/float/bool/None/True/False`; globalMap refs and casts are
pre-resolved to literals). Parity highlights:
- `_check_subjob_ok` iterates the **whole subjob**, so OnSubjobOk fires only after
  **all** components reach ok status (fixes ENG-10).
- OnComponentOk fires per component; RunIf evaluates regardless of ok/error (D-08).
- `output_id` ordering replicates Talend's visual fan-out so a branch that writes
  globalMap fires before the branch that reads it.

> **Currently non-functional** due to the class-scoping bug at line 142 -- see
> [Known Critical Bugs](#known-critical-bugs). The `add_trigger` definition is correct
> in shape (signature, `output_id` handling) but is at the wrong indentation level.

The `eval()`-on-converted-Java-strings surface is acceptable for trusted converter
output; for externally-supplied job configs a literal-only AST evaluator
(`ast.literal_eval`-style with a comparison whitelist) would remove residual eval risk.

### 9.4 PythonRoutineManager (`python_routine_manager.py`)
Discovers and dynamically imports user routine `.py` files (top-level and one subdir
level) via `importlib`, exposing them through a `RoutineNamespace` for expression
access (`routines.DemoRoutine.method()`), mirroring Talend's Java-routines mechanism.

**Smell:** `_load_module` registers modules in **global `sys.modules`** under their
bare filename stem (`:145-167`). Two routine files with the same stem in different
subdirs -- or a stem colliding with an installed package -- will overwrite each
other / shadow real imports process-wide. Namespacing the module key (e.g. a sentinel
prefix) would make discovery collision-safe.

### 9.5 Exception hierarchy (`exceptions.py`)
Rooted at `ETLError`:

```
ETLError
 +- ConfigurationError
 +- DataValidationError
 +- ComponentExecutionError     (carries component_id, cause)
 +- FileOperationError
 +- JavaBridgeError
 +- ExpressionError
 +- TriggerEvaluationError       (carries trigger_type, condition, cause)
 +- SchemaError
```

`ComponentExecutionError` and `TriggerEvaluationError` carry contextual fields. The
engine uses **errors-as-status** in the Executor: `_execute_component` converts
exceptions to `'error'` status strings; tDie is signalled via the `exit_code`
attribute on the exception/cause chain rather than propagating.

---

## 10. End-to-End Data Flow

```
job config (dict | path)
  -> ETLEngine.__init__: wire services, instantiate components from REGISTRY,
       decorate with subjob_id/inputs/outputs/schemas
  -> ExecutionPlan: SubjobPlans (topo-sorted) + TriggerEdges + initial_subjobs
  -> Executor.execute_job:
       deque(initial_subjobs)
       for each subjob (popleft):
         for each component in topo order:
           input  = OutputRouter.get_input_data(comp_id)   # DF or dict[flow->DF]
           result = component.execute(input)               # 8-step template
           OutputRouter.route_outputs(...)                 # _FLOW_TYPE_TO_RESULT_KEY
           fire OnComponentOk/Error/RunIf -> queue cross-subjob targets
         OutputRouter.clear_subjob_flows(...)  (preserve cross-subjob)
         fire OnSubjobOk/Error -> append triggered subjobs
       finalize streaming sinks; detect stalls
  -> ETLEngine.execute: decorate stats + global_map snapshot
```

Iterate components branch into `_execute_iterate_body`, re-running the body SubjobPlan
per item, resetting body components and routing accumulated rejects as the iterate
source's reject output.

---

## 11. Patterns to Preserve

- **Facade + focused collaborators**: clean separation of plan-building vs execution
  vs routing; each is independently testable.
- **Template Method**: `BaseComponent.execute` is final; subclasses override only
  `_process`/`_validate_config`.
- **Decorator registry via import side-effects** (mirrors the converter registry).
- **Iterative deque** instead of recursion for trigger/subjob chains.
- **Pre-computed immutable plan**: DAG built and validated once, enabling validation
  without a running engine.
- **Errors-as-status**: exceptions become status strings; tDie via `exit_code` on the
  cause chain.
- **Hook/observer external loop**: `BaseIterateComponent` exposes 8 hooks; the Executor
  owns the loop.
- **Immutable config / re-derivation** for clean iterate re-execution.

---

## 12. Known Critical Bugs

| # | File:line | Severity | Description |
| --- | --- | --- | --- |
| 1 | `engine.py:225-226` | **high** | Missing comma after `trigger.get('condition')` before `output_id=...` -> `SyntaxError`. **Blocks the entire `src.v1.engine` package from importing**; fails pytest collection via conftest. |
| 2 | `trigger_manager.py:142` | **high** | `add_trigger` dedented to module level; all following methods become its local closures. `TriggerManager` has only `__init__` as a real method, so every Executor call (`set_component_status`/`get_triggered_components`/`should_fire_trigger`) raises `AttributeError`. The whole trigger subsystem (OnSubjobOk/OnComponentOk/RunIf) is dead. **Fix:** re-indent line 142+ to 4 spaces (method body to 8). |
| 3 | `output_router.py:134` | medium (risk) | `route_outputs` is last-writer-wins per flow name with no collision guard; duplicate flow names = silent data loss. |
| 4 | `execution_plan.py` / `base_component.py:146` | medium (risk) | `StreamingMetadata.requires_full_data` computed but never consumed; streaming decided purely by 5120 MB threshold -> aggregate/sort/unique over >5 GB can run per-chunk and produce wrong results. |
| 5 | `executor.py:664-685` | medium (risk) | tDie `exit_code` discovery walks exactly one wrap level (`e -> e.cause -> e.__cause__`); a double-wrap downgrades a job-halt to an ordinary error. A recursive cause-chain walk would be robust. |
| 6 | `python_routine_manager.py:145-167` | medium (smell) | Routine modules registered in global `sys.modules` by bare stem -> cross-routine / installed-package shadowing. |

Both #1 and #2 were introduced by the same commit `0ad1ee0` ("output_id enhancement")
and appear to have escaped CI -- a strong signal that the engine import path / trigger
tests were not being exercised.

---

## 13. Test Pointers (for the 95% coverage push)

Direct coverage lives under `tests/v1/engine/`:

| Area | Test files |
| --- | --- |
| Executor | `test_executor.py` (single/multi-subjob, trigger timing, RunIf, die_on_error, tDie halt, stall detection, data routing, cross-subjob preservation, iterative trigger chains, streaming-reset exception) |
| Execution plan | `test_execution_plan.py` (topo sort, ordering, reachability/cycle, streaming metadata, auto-detect, real configs) |
| Output router | `test_output_router.py`, `test_output_router_iterate.py` (routing, input resolution, readiness, cleanup/preservation, chunk last-wins, reject draining) |
| Registry | `test_component_registry.py` (registration/conflict) |
| Triggers | `test_trigger_manager.py` (line 246 calls `tm.add_trigger` -- currently raises `AttributeError` from bug #2) |
| Base/services | `test_base_component.py`, `test_global_map.py`, `test_context_manager.py`, `test_context_manager_id_date.py` |
| Iterate | `test_executor_iterate.py`, `test_execution_plan_iterate.py`, `tests/integration/test_iterate_e2e.py` |
| End-to-end | `test_engine.py`, `test_full_pipeline.py` |

**Coverage gaps to close:**
- No test exercising a sort/aggregate component crossing the 5120 MB threshold
  (the streaming-vs-`requires_full_data` mismatch, bug #4).
- No test for duplicate flow-name overwrite in `route_outputs` (bug #3).
- No dedicated test file for `python_routine_manager.py` or `exceptions.py`.
- `test_trigger_manager.py` and the engine import path are blocked by bugs #1/#2 --
  fixing those is a prerequisite for measuring any engine coverage at all.

Per `CLAUDE.md`, any change touching `{{java}}` resolution should add
`@pytest.mark.java` live-bridge tests; the Java-resolution path here is otherwise
unit-tested only.

---

## 14. Open Questions

1. Should `StreamingMetadata.requires_full_data` gate `BaseComponent._select_mode` so
   aggregate/sort/unique never switch to per-chunk streaming on large inputs? The
   plan-level flag is computed but unused today.
2. Is `is_subjob_start` (`engine.py:152`) meant to be consumed (validate/pick entry
   points), or is it vestigial metadata to remove?
3. tDie `exit_code` discovery assumes single-level wrapping. Is that guaranteed for all
   components, or should the walk be a full recursive cause-chain traversal?
4. Where do the newer Pagination and MSSQL components register/execute? They do not
   appear in this core's iterate/full-data/Oracle type sets, so confirm they need no
   `execution_plan`/`engine` wiring beyond the generic REGISTRY path.
5. Should `route_outputs` assert flow-name uniqueness and fail loudly instead of
   silently overwriting?
6. Was the iterate `die_on_error=False` default (vs `True` for data components)
   intended for Talend parity, or should iterate inherit the component's setting?
7. Are bugs #1/#2 genuine HEAD-of-branch regressions that escaped CI, or is CI not
   running the engine import / trigger-test path at all?
