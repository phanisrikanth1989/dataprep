# Phase 3: Execution Loop Restructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 03-execution-loop-restructure
**Areas discussed:** Code organization, Execution model, Stall detection, Streaming scope, Component registry, Rewrite scope, Iterate handling, Error propagation, Test strategy, Assumptions surfacing

---

## Code Organization

| Option | Description | Selected |
|--------|-------------|----------|
| Separate modules | Extract into execution_plan.py, output_router.py, etc. Each independently testable. | |
| Methods in engine.py | Keep everything in engine.py, decompose into well-named private methods. | |
| Class-per-concern in engine.py | Classes within engine.py -- logical separation without separate files. | |

**User's choice:** Separate modules
**Notes:** User initially selected this. Later clarified that more files might be needed, leading to the 5-file split discussion.

---

## File Split (refined from Code Organization)

| Option | Description | Selected |
|--------|-------------|----------|
| 5 files | component_registry + execution_plan + output_router + executor + engine | ✓ |
| 4 files | No separate executor -- execution logic stays in engine.py | |
| 6 files | 5 files + component_factory for instantiation logic | |

**User's choice:** 5 files
**Notes:** User prompted this deeper discussion by asking "i thought there might be more files while splitting. no?" -- correctly identified that executor.py was a natural seam.

---

## Component Registry

| Option | Description | Selected |
|--------|-------------|----------|
| Match converter pattern | Decorator-based auto-registration, ComponentRegistry singleton | ✓ |
| Keep static dict | Move static dict to own file, keep manual entries | |
| Lazy loading dict | Dict with importlib lazy imports | |

**User's choice:** Match converter pattern (decorator-based auto-registration)
**Notes:** User raised this proactively: "will it stay in engine or will we be rewriting it to match the talend_to_v1 converter style bro?" -- showing preference for consistency between converter and engine patterns.

---

## Registration Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| __init__.py imports | Same as converter -- import triggers registration | ✓ |
| Directory scanning | Auto-discover and import all .py files | |

**User's choice:** __init__.py imports (matching converter pattern)

---

## Execution Model

| Option | Description | Selected |
|--------|-------------|----------|
| Static plan | Build DAG upfront, topo sort, validate, execute in order | ✓ |
| Dynamic queue (fixed) | Keep BFS approach, fix bugs | |
| Hybrid | Static plan for validation, dynamic queue for runtime | |

**User's choice:** Static plan
**Notes:** User initially asked "what is this question asking?" -- I explained how static plan naturally produces _execute_subjob() that iterate needs. User agreed once the iterate connection was clear.

---

## Stall Detection

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-execution validation | Fail before running if graph is broken | |
| Runtime detection | Detect stalls when queue empties mid-execution | |
| Both | Pre-validate + runtime safety net | ✓ |

**User's choice:** Both

---

## Streaming Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Fix reject drop only | Minimal -- just correct flow routing for chunks | |
| Fix + chunked flow routing | Redesign pipeline-style streaming | |
| Defer streaming entirely | Focus on batch correctness | |
| Minimal + streaming metadata | Fix routing + mark components as streamable/full-data | ✓ |

**User's choice:** Minimal + streaming metadata
**Notes:** User asked about aggregate/sort components in streaming mode. After explaining that streaming is per-component (BaseComponent handles it) and aggregate/sort problems belong in Phase 6, user chose to add streaming metadata to ExecutionPlan for future use.

---

## Rewrite Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full ETLEngine rewrite | Clean slate including __init__, registry, everything | ✓ |
| Execution-only rewrite | Only rewrite execution loop, keep init/registry | |
| Minimal surgical | Only rewrite execute() and _execute_component() | |

**User's choice:** Full ETLEngine rewrite (implicit from the 5-file split + registry change decisions)

---

## Iterate Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Remove entirely | Delete dead _execute_iterate_component() | ✓ |
| Keep as stub | NotImplementedError stub | |
| Rewrite for Phase 10 | Build iterate now using _execute_subjob() | |

**User's choice:** Remove entirely
**Notes:** No iterate components registered, code is dead. Phase 10 builds fresh on executor._execute_subjob().

---

## Error Propagation

| Option | Description | Selected |
|--------|-------------|----------|
| Fail subjob, continue others | Stop subjob on failure, continue independent subjobs | |
| Fail entire job | Any failure stops everything | |
| Component-level die_on_error | Respect per-component config | ✓ |

**User's choice:** Component-level die_on_error
**Notes:** User said "it will be based on what the component has configured for die on error or how the component is designed in talend when it comes."

---

## tDie Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve special behavior | tDie kills entire job with exit code | ✓ |
| Treat like any other failure | Same error propagation rules | |

**User's choice:** Preserve tDie behavior

---

## Registry Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Registry starts empty | Phase 3 creates infra, Phase 4-11 registers components | ✓ |
| Migrate existing components | Add decorators to existing broken component files now | |

**User's choice:** Registry starts empty

---

## RunIf Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Conditional edges in plan | Plan includes RunIf targets as conditionally reachable | ✓ |
| Claude's discretion | Let research figure it out | |

**User's choice:** Conditional edges in plan

---

## Data Flow Memory

| Option | Description | Selected |
|--------|-------------|----------|
| Free after all consumers read | Track consumer count, free when done | |
| Keep until subjob completes | Free all flows when subjob finishes | |
| Research Talend behavior | Match Talend's data lifecycle | ✓ |

**User's choice:** Research Talend's data lifecycle behavior first
**Notes:** User said "see how long talend keeps it to ensure we don't miss any case" -- deferred to research.

---

## Test Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Stub components + real infra | StubComponent fixture, real TriggerManager/GlobalMap | ✓ |
| Unit test each module | Separate tests with mocked deps | |
| Integration-only | Test through ETLEngine.execute() only | |

**User's choice:** Stub components + real infra
**Notes:** User asked whether StubComponent would be cleaned up later. Confirmed it's a permanent test fixture for orchestration tests -- real component tests are separate.

---

## Claude's Discretion

- Internal class design for ExecutionPlan, OutputRouter, Executor
- Topological sort algorithm choice
- Streaming metadata schema
- Whether _initialize_components/_initialize_triggers stay in engine.py or move

## Deferred Ideas

- Component file updates with @REGISTRY.register() -- Phase 4-11
- Iterate execution loop -- Phase 10
- Streaming optimization for aggregate/sort -- Phase 6
- Pipeline-style streaming -- future milestone
- Parallel subjob execution -- future milestone
