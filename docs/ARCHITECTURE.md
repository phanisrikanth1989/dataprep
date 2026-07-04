# DataPrep Architecture
*Last updated: 2026-05-11*

## Overview

DataPrep is a Python-based ETL execution engine that replaces Talend Open Studio for
1200+ production jobs. The system is split into two clearly separated layers:

1. **Converter** -- transforms Talend `.item` XML job definitions into JSON configurations.
2. **Engine** -- executes those JSON configurations, producing the same output rows that
   Talend would produce for the same inputs.

Each layer is internally organized around the same philosophy: an abstract base class
defines the contract, a decorator-based registry maps Talend component names to
concrete implementations, and each component type lives in its own module grouped
by category (file, transform, database, control, aggregate, context, iterate).

**Core Value:** Any Talend job using the target components must produce identical
results when run through the Python engine -- feature parity with Talend is
non-negotiable.

The converter side is clean and standardized. The engine side is the active surface
for ongoing reliability work; the architecture below reflects the current state of
`src/` as of 2026-05-11.

## System Diagram (ASCII)

```
+---------------------+     +----------------------+     +------------------------+
| Talend .item (XML)  | --> | XmlParser            | --> | TalendJob (dataclass)  |
+---------------------+     | xml_parser.py        |     +------------------------+
                            +----------------------+                 |
                                                                     v
                                                       +-----------------------------+
                                                       | TalendToV1Converter         |
                                                       | converter.py (12-step pipe) |
                                                       +-----------------------------+
                                                                     |
                                                                     v
                                                       +-----------------------------+
                                                       | ComponentConverter classes  |
                                                       | (Strategy + REGISTRY)       |
                                                       +-----------------------------+
                                                                     |
                                                                     v
                                                       +-----------------------------+
                                                       | V1 JSON config              |
                                                       +-----------------------------+
                                                                     |
+---------------------+     +----------------------+                 v
| CLI / programmatic  | --> | ETLEngine            | --> +-----------------------------+
| run_job(config)     |     | engine.py            |     | ExecutionPlan (subjobs +    |
+---------------------+     +----------------------+     | trigger edges)              |
                                     |                   +-----------------------------+
                                     v                                 |
                            +----------------------+                   v
                            | Executor             |    +-----------------------------+
                            | executor.py          | -> | REGISTRY.get(comp_type)     |
                            +----------------------+    | -> BaseComponent subclass   |
                                     |                  +-----------------------------+
                                     v                                 |
                            +----------------------+                   v
                            | OutputRouter         |    +-----------------------------+
                            | output_router.py     | <- | _process() returns          |
                            +----------------------+    | {main, reject, ...}         |
                                     |                  +-----------------------------+
                                     v
                            +----------------------+
                            | Output files / sinks |
                            +----------------------+
```

Cross-cutting services (GlobalMap, ContextManager, TriggerManager, JavaBridgeManager,
PythonRoutineManager, OracleConnectionManager) sit alongside the Executor and are
injected into components at construction.

## Layers

### XML Parsing

- **Purpose:** Parse Talend `.item` XML files into typed Python dataclasses.
- **Location:** `src/converters/talend_to_v1/xml_parser.py`.
- **Key types:** `XmlParser` class, `TalendJob` dataclass, plus `TalendNode`,
  `TalendConnection`, `SchemaColumn` dataclasses in
  `src/converters/talend_to_v1/components/base.py`.
- **Consumed by:** `TalendToV1Converter.convert_file()`.

### Component Converter

- **Purpose:** Convert one parsed Talend node into a V1 JSON component dictionary.
- **Location:** `src/converters/talend_to_v1/components/`.
- **Organization:** ~80 converter classes, one per Talend component type, grouped
  by category (file, transform, database, control, aggregate, context, iterate).
- **Contract:** Each subclass inherits `ComponentConverter`
  (`src/converters/talend_to_v1/components/base.py`) and implements
  `convert(node, connections, context) -> ComponentResult`.
- **Registration:** Decorator-based via
  `@REGISTRY.register("tFileInputDelimited")` on each class
  (`src/converters/talend_to_v1/components/registry.py`).

### Converter Orchestrator

- **Purpose:** Drive the 12-step conversion pipeline (parse, convert components,
  parse flows, propagate schemas, parse triggers, detect subjobs, detect Java
  requirement, validate, assemble JSON).
- **Location:** `src/converters/talend_to_v1/converter.py`.
- **Key types:** `TalendToV1Converter` class, top-level `convert_job()`
  convenience function at line 485.
- **Entry point:** `__main__` at line 516, runnable via
  `python -m src.converters.talend_to_v1.converter <input.item> [output.json]`.

### Engine Core

- **Purpose:** Load a V1 JSON config, build an execution plan, run components in
  order, and route outputs between flows.
- **Location:** `src/v1/engine/engine.py`.
- **Key types:**
  - `ETLEngine` -- thin orchestrator. Delegates planning to `ExecutionPlan`,
    execution to `Executor`, output routing to `OutputRouter`, and component
    lookup to `REGISTRY`.
  - `ExecutionPlan` (`src/v1/engine/execution_plan.py`) -- `SubjobPlan`,
    `TriggerEdge`, `StreamingMetadata`.
  - `Executor` (`src/v1/engine/executor.py`).
  - `OutputRouter` (`src/v1/engine/output_router.py`).
- **Entry point:** `__main__` at line 285, runnable via
  `python src/v1/engine/engine.py <job_config.json> [--context_param KEY=VALUE]`.

### Engine Component Layer

- **Purpose:** Implement individual ETL operations (file I/O, transforms,
  aggregations, joins, control flow).
- **Location:** `src/v1/engine/components/` organized by category:
  `aggregate/`, `context/`, `control/`, `database/`, `file/`, `iterate/`,
  `transform/`.
- **Contract:** Each subclass inherits `BaseComponent`
  (`src/v1/engine/base_component.py`) or `BaseIterateComponent`
  (`src/v1/engine/base_iterate_component.py`) and implements
  `_validate_config()` and `_process()`.
- **Registration:** `@REGISTRY.register("PascalName", "tTalendName")` on each class
  (`src/v1/engine/component_registry.py`). See the load-bearing
  Registry Discipline section below.

### Infrastructure Layer

Shared services injected into the engine and components:

- `GlobalMap` (`src/v1/engine/global_map.py`) -- Talend-compatible key-value store
  for stats (`NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT`) and inter-component variables.
- `ContextManager` (`src/v1/engine/context_manager.py`) -- resolves
  `${context.var}` and bare `context.var` patterns in configuration.
- `TriggerManager` (`src/v1/engine/trigger_manager.py`) -- evaluates trigger
  edges (OnSubjobOk, OnComponentOk, RunIf, etc.).
- `JavaBridgeManager` (`src/v1/engine/java_bridge_manager.py`) -- lifecycle
  manager for the Java/Groovy subprocess.
- `PythonRoutineManager` (`src/v1/engine/python_routine_manager.py`) -- loads and
  executes user-supplied Python routines.
- `OracleConnectionManager` (`src/v1/engine/oracle_connection_manager.py`) --
  pooled Oracle connections for database components.
- `exceptions.py` (`src/v1/engine/exceptions.py`) -- ETLError hierarchy.

### Java Bridge Layer

- **Purpose:** Execute legacy Talend Java/Groovy expressions and row-level
  transformations.
- **Python side:** `src/v1/java_bridge/bridge.py` (`JavaBridge` Py4J client,
  Apache Arrow IPC for DataFrame transfer).
- **Java side:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java`
  and `RowWrapper.java`.
- **Build artifact:** `src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar`
  (built via Maven; `pom.xml` declares Java 11 source/target).
- **Engagement:** `JavaBridgeManager` starts the JVM subprocess on a
  dynamically-allocated port (`socket.bind(('', 0))` in
  `src/v1/engine/java_bridge_manager.py`) when `java_config.enabled = true` in the
  job config; otherwise it stays cold and components fall back to pure Python.

## Key Abstractions

### `BaseComponent` (Template Method)

`src/v1/engine/base_component.py` line 115 declares the abstract base for every
data-processing component. The `execute()` method is final-by-convention
(subclasses MUST NOT override it). Its lifecycle is:

1. Fresh `config` from `_original_config` (deepcopy each call -- guarantees
   iterate re-execution starts clean per ENG-09/ENG-21).
2. `_validate_config()` -- abstract; raises `ConfigurationError`.
3. `_resolve_expressions()` -- Java `{{java}}` markers first, then context
   variables.
4. Read `die_on_error` from resolved config.
5. `_select_mode()` -- auto-select BATCH or STREAMING based on input size.
6. `_execute_batch()` or `_execute_streaming()` -- calls `_process()`.
7. `_enforce_schema_column_order()` then `_apply_output_schema_validation()`
   -- column ordering, type coercion, length/precision, reject routing.
8. `_update_stats_from_result()` + `_update_global_map()`.

`_process(input_data) -> dict` is the single hook for subclass logic. It must
return a dict with key `main` (output DataFrame) and may include `reject` plus
arbitrary named flow keys for multi-output components.

### `BaseIterateComponent` (Iterator)

`src/v1/engine/base_iterate_component.py` line 59 extends `BaseComponent` for
components that emit iterations (`tFileList`, `tFlowToIterate`, `tForeach`).
Subclasses implement `prepare_iterations()` (returns an `Iterator[Any]`) and
`set_iteration_globalmap(item)` to push per-iteration state into `GlobalMap`.

### `ComponentConverter` (Strategy)

`src/converters/talend_to_v1/components/base.py` declares the abstract base for
each Talend-to-V1 converter. Each subclass implements
`convert(node, connections, context) -> ComponentResult` and uses the
`_get_str()`, `_get_bool()`, `_get_int()`, `_parse_schema()`,
`_build_component_dict()`, `_convert_date_pattern()` helpers.

### `REGISTRY` (Decorator-Based, Both Sides)

Both layers use the same registration pattern:

- Engine: `REGISTRY` instance of `ComponentRegistry`
  (`src/v1/engine/component_registry.py` line 72). Decorator `@REGISTRY.register(...)`
  is defined at line 29 and accepts one or more names (e.g.,
  `@REGISTRY.register("FileInputDelimited", "tFileInputDelimited")`).
- Converter: `REGISTRY` instance of `ConverterRegistry`
  (`src/converters/talend_to_v1/components/registry.py`). Same decorator shape.

Registration fires when the `components/__init__.py` of each layer imports its
sub-packages, which triggers the decorators to populate the registry.

## Registry Discipline

This section documents a LOAD-BEARING invariant that Phase 14 surfaced repeatedly.
It is the single most important rule for anyone adding or modifying engine
components.

### The Live Registry

The engine `REGISTRY` lives in `src/v1/engine/component_registry.py` (decorator-
based, mirroring the converter side). It is imported into
`src/v1/engine/engine.py` at line 18:

```
from .component_registry import REGISTRY
```

Lookup happens at line 140 of `engine.py` via `REGISTRY.get(comp_type)`.

The previously-documented `ETLEngine.COMPONENT_REGISTRY` static-dict class
attribute NO LONGER EXISTS. Earlier maps in `.planning/codebase/` still describe
it as a static dict; that description is stale and was corrected in Phase 15.
The current source-of-truth pattern is decorator-based registration that mirrors
the converter side exactly.

### The Dual Invariant

Every `BaseComponent` subclass MUST satisfy BOTH of the following:

1. **Be decorated** with `@REGISTRY.register("PascalCaseName", "tTalendName")` --
   one decorator listing one or more aliases. PascalCase is the V1 internal name;
   the `t`-prefixed alias mirrors the Talend component name so converter output
   can lookup the engine class directly.
2. **Implement `_validate_config()`** raising `ConfigurationError` on missing
   required keys. The method is declared `@abstractmethod` on `BaseComponent`
   (line 280 of `base_component.py`) -- Python ABC machinery refuses to
   instantiate any subclass that fails to override it.

### Failure Modes (Why This Section Matters)

- **Missing decorator:** The engine logs `Unknown component type <name>` at
  runtime and silently drops the component from job execution. There is no
  startup-time membership check. A job with a typo-named component will run to
  completion but produce wrong output, with no exception raised. This is the
  most dangerous of the two failure modes because it is silent.
- **Missing `_validate_config`:** The class is uninstantiable. Python raises
  `TypeError: Can't instantiate abstract class ...` on `__init__`. This fails
  loudly the first time the engine tries to construct the component, so it is
  caught the moment the component is exercised by any test or live job.

### Phase 14 Evidence

Four bug pairs surfaced this exact failure shape during the Phase 14 coverage
push. Each pair was a `BaseComponent` subclass missing BOTH the decorator AND
`_validate_config()`. The class was importable but unusable; engine.py silently
dropped it as "Unknown component type" at production runtime:

| Bug ID            | Component                | Plan  | Notes                                                |
| ----------------- | ------------------------ | ----- | ---------------------------------------------------- |
| BUG-PDC-001/002   | `PythonDataFrameComponent` | 14-06 | Coverage push from 20% to 100% surfaced the gap.   |
| BUG-SWIFT-001/002 | `SwiftTransformer`       | 14-07 | Pair of fixes; component went 7% to 98.0%.           |
| BUG-SWIFT-003/004/005 | `SwiftBlockFormatter` | 14-07 | Same shape, surfaced when 7% to 97.2% lift.          |
| BUG-FIJ-001/002   | `FileInputJSON`          | 14-09 | Root-cause fix; 9% to 100% coverage.                 |

Three independent plans (14-06, 14-07, 14-09) hit the same failure shape before
Plan 14-12 audited the pattern explicitly. Reference:
`.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md`.

### Why No Startup Audit Yet

Phase 14 considered adding a startup-time audit that walks the
`BaseComponent` subclass tree and asserts each subclass is registered. The
proposal was deferred (see `15-CONTEXT.md` "Deferred Ideas"). For now the
invariant is enforced by:

1. Manual review during code authoring.
2. `docs/CONTRIBUTING.md` Rule 5 (added by plan 15-04).
3. Coverage push exercising every component, which makes "Unknown component
   type" surface in test logs.

A future plan may add the automated audit; until then this section is the
canonical statement of the rule.

## Data Flow

### Conversion Pipeline (12 Steps)

Driven by `TalendToV1Converter.convert_file()` in
`src/converters/talend_to_v1/converter.py`:

1. Parse XML (`XmlParser`).
2. Convert context variables (type mapping already applied by parser).
3-4. Convert components (with try/except wrapping each; failures yield an
   `_unsupported` placeholder plus warnings).
5. Parse flows from connections.
6. Update component inputs/outputs from flows.
6b. Propagate input schemas from upstream output schemas.
7-8. Parse triggers (`trigger_mapper` filters skipped components).
9. Detect subjobs.
10. Detect Java requirement (sets `java_config.enabled`).
11. Validate (`validator.py` -- reference integrity, tMap rules, expression
    quality, conversion quality).
12. Assemble final JSON dictionary.

### Engine Execution Pipeline

Driven by `ETLEngine.execute()` in `src/v1/engine/engine.py`, delegating to
`Executor` (`src/v1/engine/executor.py`):

1. Load JSON config; apply context overrides.
2. Initialize `GlobalMap`, `ContextManager`, `TriggerManager`.
3. Start `JavaBridgeManager` if `java_config.enabled` is true.
4. Build `ExecutionPlan` -- subjobs, trigger edges, streaming metadata.
5. Instantiate components via `REGISTRY.get(comp_type)`.
6. For each subjob, run components in topological order through the
   `Executor`.
7. Each component runs the `BaseComponent.execute()` lifecycle (8 steps above).
8. `OutputRouter` routes each named flow in the `_process()` return dict to the
   downstream component's input.
9. `TriggerManager` evaluates inter-subjob trigger edges (OnSubjobOk, RunIf).
10. After all subjobs, shutdown Java bridge, return execution stats.

## State Management

- **`GlobalMap`** -- Talend-compatible key-value store. Components write
  `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT`, and any user-defined variables.
  Read access is uniform across components.
- **`ContextManager`** -- resolves three patterns at execute time:
  1. `${context.var}` (Talend explicit syntax).
  2. Bare `context.var` (Talend implicit syntax).
  3. Nested dicts and list-of-dicts (`resolve_dict()` was rewritten in ENG-03 to
     fix a literal `[i]` substitution bug).
- **`data_flows`** -- engine-internal `Dict[str, Any]` keyed by flow name.
  Holds the DataFrames passed between components within a subjob.
- **Java Bridge sync** -- when Java is enabled, the bridge mirrors `GlobalMap`
  and `context` bidirectionally through `_sync_from_java()` so Groovy
  expressions see and update the same state.

## Error Handling Strategy

The exception hierarchy lives in `src/v1/engine/exceptions.py`:

```
ETLError
  +-- ConfigurationError
  +-- DataValidationError
  +-- ComponentExecutionError       (carries component_id and optional cause)
  +-- FileOperationError
  +-- JavaBridgeError
  +-- ExpressionError
  +-- TriggerEvaluationError
  +-- SchemaError
```

Routing rules:

- Components raise `ConfigurationError`, `FileOperationError`, etc. from inside
  `_process()`. `BaseComponent.execute()` wraps any non-ETLError exception in
  `ComponentExecutionError(component_id, cause=...)` before re-raising.
- The `die_on_error` config flag (defaults to True; see line 192 of
  `base_component.py`) controls whether errors are fatal or whether the
  offending rows are routed to the reject flow with `errorCode` and
  `errorMessage` columns populated.
- Schema violations on the `main` output flow (G-05/D-11) are routed to reject
  with `errorCode = SCHEMA_VIOLATION` when `die_on_error` is False.
- The `Die` component (`src/v1/engine/components/control/die.py`) raises
  `ComponentExecutionError` with an attached `exit_code` to force whole-job
  termination regardless of `die_on_error` semantics elsewhere.
- The converter wraps each component conversion in try/except and falls back to
  an `_unsupported` placeholder with warnings, so a single converter bug never
  fails the whole conversion.

Post-conversion validation: `src/converters/talend_to_v1/validator.py` produces
`ValidationReport(valid, issues, summary)` with `ValidationIssue.severity` in
`{"error", "warning", "info"}`.

## Cross-Cutting Concerns

### Logging

- Standard `logging` module; each module owns
  `logger = logging.getLogger(__name__)`.
- Engine components prefix messages with `[{self.id}]` for traceability.
- ASCII-only log content per project convention (RHEL servers).
- Levels: DEBUG for data details, INFO for lifecycle events, WARNING for
  degraded operation, ERROR for failures.
- The engine sets `logging.basicConfig(level=logging.INFO)` at module level in
  `engine.py`.

### Validation

- **Converter side (4-layer post-conversion):** reference integrity, tMap rules,
  expression quality, conversion quality markers -- all in `validator.py`.
- **Engine side:** `BaseComponent.validate_schema()` runs in lifecycle step 7c
  using a Talend-to-pandas type mapping with nullable-aware coercion.
- **Component side:** `_validate_config()` (abstract) is the per-component
  required-key gate; see Registry Discipline above.

### Expression Resolution

A three-phase resolution chain runs at engine execute time:

1. `{{java}}` markers -- batched through `JavaBridgeManager` and evaluated by
   the Groovy interpreter on the JVM side.
2. `${context.var}` -- resolved by `ContextManager.resolve_dict()`.
3. Bare `context.var` -- resolved via regex substitution.

On the converter side, `ExpressionConverter.detect_java_expression()` in
`src/converters/talend_to_v1/expression_converter.py` aggressively marks
Java/Groovy patterns with the `{{java}}` prefix for deferred execution.
`ExpressionConverter.convert()` performs simpler Java-to-Python rewrites
(string methods, null checks, operators).

### Runtime Shape

This is a batch ETL system -- not a web service. There is no auth layer, no
session management, and no request lifecycle. Database credentials are supplied
via context variables in the job config rather than environment variables.

## Entry Points

### Converter CLI

```
python -m src.converters.talend_to_v1.converter <input.item> [output.json]
```

`__main__` block at `src/converters/talend_to_v1/converter.py` line 516.
Top-level `convert_job(input_path, output_path)` at line 485 is the
programmatic entry point.

### Engine CLI

```
python src/v1/engine/engine.py <job_config.json> [--context_param KEY=VALUE]
```

`__main__` block at `src/v1/engine/engine.py` line 285. The top-level
`run_job(job_config_path, context_overrides)` is the programmatic entry point.

### Programmatic Use

```python
from src.converters.talend_to_v1.converter import convert_job
from src.v1.engine.engine import run_job

config = convert_job("job.item", "job.json")
stats = run_job("job.json", context_overrides={"DB_HOST": "prod-db"})
```

### Helper Scripts

- `tests/converters/talend_to_v1/batch_convert.py` -- batch-converts many
  Talend XML files for testing.
- `scripts/add_connectors.py` -- adds connector metadata to
  `src/router/ui_registry.json` for UI rendering.

## See Also

- `docs/COMPONENT_REFERENCE.md` -- per-component inventory and supported
  options (plan 15-03).
- `docs/CONTRIBUTING.md` -- authoring conventions, including Rule 5 on
  registry discipline (plan 15-04).
- `docs/DEPLOYMENT.md` -- runtime requirements, JVM provisioning, Maven build
  for the Java bridge (plan 15-05).
- `docs/v1/patterns/` -- design patterns used inside the engine (post-rename
  location reached via wave-2 reorganization).
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-PHASE-SUMMARY.md`
  -- source of the Phase 14 Lessons Learned that motivated the Registry
  Discipline section above.
