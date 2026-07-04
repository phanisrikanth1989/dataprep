# System Overview

> Audience: engineers extending DataPrep and raising per-module test coverage to a
> 95% floor. This document is the map of the whole system: what it is, how the
> pieces fit, and where to look next. Subsequent docs in `docs/understanding/`
> drill into individual subsystems.

ASCII-only is a hard project rule. Logs, comments, and docs must avoid non-ASCII
characters (em-dashes, smart quotes, emoji). Several findings in this codebase are
ASCII-rule violations in logging strings; keep that rule in mind when editing.

---

## 1. What DataPrep Is

DataPrep is a **Talend-to-Python ETL migration engine**. It takes a legacy Talend
Open Studio job (an XML `.item` file) and lets it run on a pure-Python runtime,
with feature parity to Talend's semantics. There are three major moving parts:

1. **Converter** (`src/converters/talend_to_v1/`) - parses Talend `.item` XML and
   emits a normalized JSON job config. It does NOT execute anything; it is a pure
   translation layer.
2. **Engine** (`src/v1/engine/`) - reads a JSON job config and executes it against
   pandas DataFrames, reproducing Talend's flow graph, subjob ordering, trigger
   firing, and per-component behavior.
3. **Java/Groovy bridge** (`src/v1/java_bridge/`) - a JVM subprocess (over Py4J +
   Apache Arrow) that runs legacy Talend Java/Groovy expressions that cannot be
   faithfully translated to Python, using a vendored copy of Talend's standard
   routine library.

A thin **FastAPI HTTP layer** (`api/`) wraps the engine for upload/run/poll plus
CRUD of Java/Python routine files.

The governing design constraint everywhere is **Talend parity**: trigger ordering,
schema propagation, NB_LINE statistics, reject-flow semantics, date/decimal
formatting, and expression evaluation are all built to match what Talend Studio
would have generated and run.

---

## 2. The End-to-End Pipeline

```
  Talend .item XML
        |
        v
  [ CONVERTER ]  src/converters/talend_to_v1/converter.py
   parse XML -> dispatch each node to a registered ComponentConverter
   wire flows + triggers -> propagate schemas -> detect subjobs
   detect Java requirement -> validate
        |
        v
  JSON job config  { components[], flows[], triggers[], subjobs[],
                     context, java_config, _validation, _warnings, _needs_review }
        |
        v
  [ ENGINE ]  src/v1/engine/engine.py (ETLEngine facade)
   instantiate components from COMPONENT_REGISTRY
   build ExecutionPlan (DAG + topo sort + subjob/trigger graph)
   Executor runs subjobs (iterative deque), routes data via OutputRouter,
   fires triggers via TriggerManager
        |                         |
        |                         +--> [ JAVA BRIDGE ]  Py4J + Arrow
        |                              {{java}} expressions, tMap/tJavaRow Groovy
        v
  Output files / DataFrames + execution stats + globalMap snapshot
```

There are **two independent registries**, one per layer, both decorator-based and
populated by import side effects:

| Layer | Registry | File | Maps |
|-------|----------|------|------|
| Converter | `REGISTRY` (ConverterRegistry) | `src/converters/talend_to_v1/components/registry.py` | Talend type name -> converter class |
| Engine | `REGISTRY` (ComponentRegistry) | `src/v1/engine/component_registry.py` | type name (V1 PascalCase + Talend `t`-prefixed alias) -> component class |

Both raise on duplicate/conflicting registration so accidental double-registration
surfaces at import time. To make a registry "see" a converter or component, its
module must be imported; the package `__init__.py` files do this for side effects
(`from . import components as _components  # noqa: F401`).

---

## 3. The Converter in Detail

Entry point: `TalendToV1Converter.convert_file(filepath)` in
`src/converters/talend_to_v1/converter.py`. A documented **12-step pipeline**:

1. Parse XML into a `TalendJob` (`xml_parser.py`).
2. Convert context variables (type-mapped, quote-stripped).
3. Convert components via `REGISTRY.get(component_type)`.
4. Per-component error isolation (failures become `_unsupported` placeholders).
5. Parse flows from connections (`_parse_flows`).
6. Update component inputs/outputs from flows.
   - 6b. Propagate input schemas downstream (`_propagate_input_schemas`).
7. Map triggers (`trigger_mapper.py`).
8. Detect subjobs (DFS over a bidirectional flow adjacency graph).
9. Detect Java requirement (`_detect_java_requirement`).
10. Assemble config dict (with `java_config`).
11. Validate (`validator.py`, four layers).
12. Attach out-of-band channels and return / write JSON.

### Key converter abstractions

- **`XmlParser`** - ElementTree-based. Skips `tLibraryLoad` nodes, pops
  `UNIQUE_NAME` as `component_id`, coerces `CHECK` params to bool, collects
  `TABLE` params as raw `{elementRef, value}` lists, strips quotes from scalars.
- **`ComponentConverter`** (ABC, `components/base.py`) - every converter subclasses
  this. Provides typed param getters (`_get_str/_get_bool/_get_int/
  _get_int_or_context`), `_parse_schema`, `_convert_date_pattern`, `_incoming/
  _outgoing`, and `_build_component_dict`. Each `convert()` returns a
  `ComponentResult(component_dict, warnings, needs_review)`.
- **`ExpressionConverter`** (`expression_converter.py`) - static API:
  `detect_java_expression` (heuristic), `mark_java_expression` (prefix `{{java}}`),
  and `convert` (lossy Java-to-Python rewrite used only for RunIf conditions).
- **`validate_config`** (`validator.py`) - four layers: reference integrity, tMap
  rules, leftover-Java scan, conversion-quality markers. Returns a
  `ValidationReport`; `valid == (no errors)`.

### `needs_review` / parity gaps

Converters deliberately extract **every** Talend parameter, even those the engine
does not yet consume, and emit structured `needs_review` entries (severity
`engine_gap`) instead of silently dropping data. This is the auditable
parity-gap channel. The output config carries `_warnings`, `_needs_review`, and
`_validation` as top-level keys.

### Component coverage (converter side)

The converter has roughly 90+ component converters across categories:

| Category | Directory | Examples |
|----------|-----------|----------|
| File | `components/file/` | tFileInput/OutputDelimited, Excel, Positional, XML, JSON, archive, copy, delete, list, tFixedFlowInput, tSetGlobalVar |
| Transform | `components/transform/` | tMap, tXMLMap, tJoin, tFilterRow, tSortRow, tNormalize, tAggregateSortedRow, tJava/tJavaRow, tPython*, tExtract* |
| Database | `components/database/` | tOracleConnection/Input/Output/Row/SP/BulkExec/Commit/Rollback/Close, tMSSqlConnection/Input |
| Aggregate | `components/aggregate/` | tAggregateRow, tUniqueRow |
| Context | `components/context/` | tContextLoad |
| Control | `components/control/` | tDie, tWarn, tSleep, tRunJob, tSendMail, tPrejob, tPostjob, tParallelize, tLoop |
| Iterate | `components/iterate/` | tForeach, tFlowToIterate |

---

## 4. The Engine in Detail

Entry point: `ETLEngine(job_config).execute()` in `src/v1/engine/engine.py`.
`ETLEngine` is a thin **facade** that wires up services and delegates to three
focused collaborators:

- **`ExecutionPlan`** (`execution_plan.py`) - pure data structure. Builds
  per-subjob topologically-sorted `SubjobPlan`s (via `graphlib`), a `TriggerEdge`
  list, initial subjobs, iterate-body subgraphs, and streaming metadata.
  `validate()` checks reachability, cycles, and nested-iterate (depth limit 1).
- **`Executor`** (`executor.py`) - owns the main loop. Processes subjobs from an
  **iterative deque** (not recursion, to survive long trigger chains), runs each
  subjob's components in topological order, drives Phase-10 iterate bodies, and
  fires component/subjob triggers.
- **`OutputRouter`** (`output_router.py`) - owns the `_data_flows` dict. Routes
  component outputs (`main`/`reject`/`iterate`/named keys) to downstream flows,
  resolves inputs, checks readiness (skipping iterate control-flow edges), and
  clears subjob flows with cross-subjob preservation. Last-writer-wins per flow
  name.

### Component lifecycle (Template Method)

Every executable component subclasses **`BaseComponent`** (`base_component.py`,
~1.3k LOC). `execute(input_data)` is a fixed lifecycle that subclasses must NOT
override; they implement only `_validate_config()` and `_process()`:

1. Re-derive working `config` fresh from an immutable `_original_config` deepcopy
   (so iterate re-execution always starts clean).
2. `_validate_config()` - structure-only checks ("Rule 12": defer content checks
   to `_process` so unresolved `${context.X}` refs do not crash validation).
3. `_resolve_expressions()` - the **3-phase expression resolution** (see Section 6).
4. Read `die_on_error`.
5. Count input rows for NB_LINE.
6. Select execution mode (BATCH / STREAMING / HYBRID).
7. Call subclass `_process()`.
   - 7b. Enforce output-schema column order.
   - 7c. Validate/coerce types, apply precision, route schema violations to reject
     (when `die_on_error=False`).
8. Roll up stats and push to `GlobalMap`.

Iterate components subclass **`BaseIterateComponent`** instead, which overrides
`execute()` to prime an iterator and exposes an 8-hook lifecycle
(`prepare_iterations`, `has_next_iteration`, `get_next_iteration_context`,
`should_stop`, `before/after_iteration`, `set_iteration_globalmap`, `finalize`)
that the `Executor` drives.

### Engine services

| Service | File | Responsibility |
|---------|------|----------------|
| `GlobalMap` | `global_map.py` | Talend-style key/value store + per-component NB_LINE/NB_LINE_OK/NB_LINE_REJECT stats |
| `ContextManager` | `context_manager.py` | Typed context-variable storage + recursive `${context.X}` resolution |
| `TriggerManager` | `trigger_manager.py` | OnSubjobOk/Error, OnComponentOk/Error, RunIf evaluation with sandboxed condition eval |
| `JavaBridgeManager` | `java_bridge_manager.py` | Per-job Java bridge lifecycle (free-port allocation, routine loading) |
| `PythonRoutineManager` | `python_routine_manager.py` | Dynamic loading of user Python routines into transform-component namespaces |
| `OracleConnectionManager` | `oracle_connection_manager.py` | Per-job live oracledb connections (thin mode) |
| `MSSqlConnectionManager` | `mssql_connection_manager.py` | Per-job live pyodbc connections |

---

## 5. The Java/Groovy Bridge

`src/v1/java_bridge/` executes legacy Talend Java/Groovy expressions that the
converter cannot translate. Flow:

1. The converter marks such expressions with a `{{java}}` prefix.
2. At runtime, `BaseComponent._resolve_expressions()` (Phase 1) detects `{{java}}`
   markers and routes them to the bridge.
3. The Python client (`bridge.py`) launches a JVM subprocess
   (`JavaBridge.java`) over Py4J, serializes DataFrames to **Apache Arrow** IPC
   byte buffers, runs Groovy scripts (row-by-row for tJavaRow, compile-once for
   tMap), and deserializes Arrow results back to pandas.
4. `context` and `globalMap` are synchronized bidirectionally at every call
   boundary so stateful Talend variables survive across components.

The bridge vendors Talend Open Studio 8.0.1's **standard routine library**
(`TalendDate`, `StringHandling`, `Mathematical`, etc.) verbatim, compiled into a
JAR, so expressions call the same helpers Talend generated. Type mapping is
constrained to **7 Python type strings** (`type_mapping.py`), validated at the
bridge boundary. Decimal precision/scale follows Talend's inverted convention
(length = total digits, precision = decimal places).

Key cross-language concerns handled here: Py4J Base64 signed-int overflow on large
frames (chunking with halve-and-retry), Py4J sending Python `float` as Java
`Double` (explicit `java.lang.Float` wrapping for `id_Float`), and Groovy
Automatic Semicolon Insertion on multi-line expressions (CRLF collapse).

---

## 6. Cross-Cutting Concepts

### GlobalMap

Talend's `globalMap` is a process-wide key/value store. In DataPrep it is the
`GlobalMap` service. Components publish stats (`{id}_NB_LINE`, `_NB_LINE_OK`,
`_NB_LINE_REJECT`) and Talend RETURN variables (e.g. `{id}_CURRENT_ITERATION`,
`{id}_EXISTS`, `{id}_FILENAME`). It is synced into the Java bridge so Groovy code
can read/write the same variables. Note: it is **additive** end-to-end; once set,
a key cannot currently be deleted across the Python/Java boundary.

### ContextManager and context resolution

Context variables are Talend's parameterization mechanism (`context.dbHost`,
`${context.dbHost}`). `ContextManager` stores them with their Talend type
(`id_Integer`, `id_Date`, etc.) and resolves references recursively through nested
dicts/lists, skipping code fields (`python_code`, `java_code`, `imports`). Typed
values like `id_Date` are parsed to real `datetime` objects so downstream casts
behave like Talend.

### Triggers and subjobs

A **subjob** is a connected group of components linked by data flows. A **trigger**
is a control-flow edge between subjobs or components:

- `OnSubjobOk` - fires only after ALL components in the source subjob succeed.
- `OnComponentOk` / `OnComponentError` - fires per component.
- `RunIf` - fires when a (Java-style) condition evaluates true.
- `tDie` halts the entire job via an `exit_code` attribute on the raised exception.

The converter detects subjobs via DFS and maps Talend trigger types to V1
PascalCase names. The engine's `ExecutionPlan` builds the subjob/trigger graph;
`Executor` seeds a deque with initial subjobs and appends newly triggered subjobs
as it goes.

### 3-phase expression resolution

Inside `BaseComponent._resolve_expressions()`:

1. **Java markers** - `{{java}}`-prefixed values are sent to the Java bridge
   (context + globalMap synced first), evaluated, and results substituted back
   into config by dotted path.
2. **Context variables** - `${context.X}` / bare `context.X` substituted via
   `ContextManager.resolve_dict()`, everywhere except code fields
   (`SKIP_RESOLUTION_KEYS = {java_code, imports, python_code}`).
3. Config is then ready for `_process()`.

### ITERATE flows

ITERATE connections are control-flow edges that carry NO data; the iterate source
publishes per-iteration variables to `globalMap` (key `{id}_CURRENT_ITERATION`).
`OutputRouter.are_inputs_ready` skips iterate-type flows so iterate-body consumers
are not falsely blocked. Nested iteration is currently unsupported (depth = 1).

### Reject flows and `die_on_error`

Components return `{"main": df, "reject": df|None, ...named flows}`. When
`die_on_error=True`, a failing row/condition raises and (for tDie) halts the job;
when `False`, failures route to a `reject` DataFrame carrying `errorCode` /
`errorMessage` columns that mirror Talend reject schemas.

---

## 7. Tech Stack

| Concern | Technology |
|---------|-----------|
| Language (runtime) | Python 3.12+ |
| Data | pandas, numpy |
| XML parsing (converter) | `xml.etree.ElementTree` |
| XML parsing (engine) | lxml (hardened against XXE/billion-laughs in `_xml_io.py`) |
| Excel | openpyxl + xlrd |
| JSON path | jsonpath-ng |
| DAG / topo sort | `graphlib` (stdlib) |
| Java bridge transport | Py4J 0.10.9.9 + Apache Arrow 15.0.2 (pyarrow / arrow-java) |
| JVM-side scripting | Groovy 3.0.21, Java 11 |
| Bridge build | Maven (shade plugin -> `java-bridge-with-dependencies.jar`) |
| Oracle | python-oracledb (thin mode) |
| SQL Server | pyodbc |
| HTTP API | FastAPI + uvicorn (under the `api` optional-deps extra) |
| Tests / coverage | pytest, pytest-cov, pytest-xdist |

Optional dependency extras (`pyproject.toml`): `dataprep[java|excel|oracle|xml|
yaml|json|api|dev|all]`. Note: FastAPI/uvicorn live under the `api` extra, so a
plain install will fail to import `api/app.py`.

---

## 8. Entry Points

### Converter CLI

```
python -m src.converters.talend_to_v1.converter <input.item> [output.json]
```

Also `convert_job(input_path, output_path=None) -> dict` and
`TalendToV1Converter().convert_file(filepath) -> dict`. A bulk harness
(`batch_convert.py`) runs over the sample `.item` files for regression.

### Engine CLI

```
python -m src.v1.engine.engine <job_config.json> --context_param KEY=VALUE
```

Also `ETLEngine(job_config).execute() -> stats` and
`run_job(job_config_path, context_overrides) -> stats`.

### HTTP API

Run with `uvicorn api.app:app`. Routers mount under:

| Route | Purpose |
|-------|---------|
| `GET /api/health` | Health check |
| `POST /api/jobs/upload` | Upload a `.json` job config (-> `job_id`) |
| `POST /api/jobs/{job_id}/run` | Run a persisted job (-> `run_id`, daemon thread) |
| `POST /api/jobs/run-inline` | Run a posted job config dict directly |
| `GET /api/jobs/runs/{run_id}` | Poll run status |
| `GET\|POST\|PUT\|DELETE /api/routines/java`, `.../python` | Routine file CRUD |
| `POST /api/routines/java/build` | Stream `mvn package` output over SSE |

> SECURITY: the API currently has no authentication, wide-open CORS, and a path-
> traversal exposure on `job_id`/`run_id`. `run-inline` and routine-file writes are
> effectively RCE-by-design for an untrusted caller. Treat the API as a
> localhost-only developer tool until hardened. See `docs/understanding` for the
> API-layer findings.

---

## 9. Data-Flow Story (Worked Example)

1. **Talend job** `LoadCustomers.item` defines `tFileInputDelimited ->
   tMap -> tFileOutputDelimited`, with a `tPrejob -> tJava` setup subjob and an
   `OnSubjobOk` trigger.
2. **Convert**: `XmlParser` builds a `TalendJob`. Each node dispatches to its
   converter, producing component dicts with `config`, `schema`, `inputs`,
   `outputs`. Flows become `{type: flow, name, source, target}` entries; schemas
   propagate from input to tMap to output. The tMap's Java expressions are marked
   `{{java}}`. Triggers map to PascalCase. Two subjobs are detected. `java_config`
   is enabled because tMap/tJava require Java. `validate_config` attaches
   `_validation`. Output is one JSON config.
3. **Plan**: `ETLEngine` instantiates components from `COMPONENT_REGISTRY`,
   injecting `output_schema`/`reject_schema`/`java_bridge`/`global_map`/
   `context_manager`. `ExecutionPlan` topo-sorts each subjob and builds the trigger
   graph; the prejob subjob is an initial subjob.
4. **Execute**: `Executor` pops the prejob subjob, runs tPrejob then tJava (which
   round-trips through the bridge), then the `OnSubjobOk` trigger queues the main
   subjob. The main subjob runs the input reader (-> `main` DataFrame), tMap
   (compiles a Groovy script, runs it chunked over the joined frame via the
   bridge, returns named outputs), and the output writer (serializes to disk,
   passes the original DataFrame through as `main`). `OutputRouter` moves data
   between them.
5. **Output**: the delimited file is written; `execute()` returns status, timing,
   per-component stats, and a `global_map` snapshot.

---

## 10. Glossary of Talend Terms

| Term | Meaning in DataPrep |
|------|---------------------|
| `.item` | Talend's XML job definition file; the converter's input. |
| Component (`tXxx`) | A node in a Talend job (e.g. `tFileInputDelimited`, `tMap`). Each has a converter (XML->JSON) and usually an engine class (JSON->execution). |
| elementParameter | A flat scalar config field in the `.item` XML. |
| TABLE param | A repeating multi-row parameter (mappings, formats), parsed by stride or state-machine helpers into lists of dicts. |
| Flow / connection | A data edge between components (FLOW/MAIN/REJECT/FILTER/UNIQUE/DUPLICATE/ITERATE). |
| Trigger | A control-flow edge (OnSubjobOk, OnComponentOk/Error, RunIf). |
| Subjob | A connected group of components linked by data flows; the unit of OnSubjobOk evaluation. |
| tMap | Talend's central join/transform component; the most complex converter and engine module (`components/transform/map/`). |
| globalMap | Process-wide key/value + stats store (`GlobalMap`). |
| context variable | Job parameter (`context.X` / `${context.X}`), typed and resolved by `ContextManager`. |
| RunIf | A conditional trigger whose Java-style condition is evaluated at runtime. |
| tDie / tWarn | Control components: tDie halts the job; tWarn logs at a priority. |
| tPrejob / tPostjob | Subjob brackets that run before/after the main job; tPrejob triggers are forced to OnComponentOk so it runs first. |
| NB_LINE / NB_LINE_OK / NB_LINE_REJECT | Talend row-count stats published per component to globalMap. |
| routine | A reusable code library: Java routines (vendored Talend `TalendDate` etc.) or Python routines (user `.py` modules loaded by `PythonRoutineManager`). |
| `{{java}}` marker | Converter-emitted prefix flagging an expression for deferred evaluation by the Java bridge. |
| reject flow | The error/failed-row output channel (`errorCode`/`errorMessage`), gated by `die_on_error`. |
| iterate flow | A control-flow edge carrying no data; drives per-iteration body re-execution via globalMap. |

---

## 11. Where to Go Next

- **Testing posture**: the project enforces a **95% per-module line-coverage floor**
  via `scripts/check_per_module_coverage.py` (no global `fail_under`, so a
  well-covered module cannot mask an under-covered one). Coverage scope is
  `src/v1/engine` and `src/converters`. Run the gate command documented in
  `CLAUDE.md`. The coverage gate measures only modules imported during the test
  run, so newly added modules with no test silently escape the floor - add tests
  AND confirm the module appears in `coverage.json`.

- **Known high-severity issues to be aware of when extending** (full detail in the
  per-subsystem docs):
  - `src/v1/engine/trigger_manager.py` - a class-scoping (indentation) bug that
    moves all methods after `__init__` to module scope, breaking the trigger
    subsystem at runtime.
  - `src/v1/engine/engine.py` (around line 225) - a missing-comma SyntaxError in
    the `add_trigger` call that blocks importing the engine package.
  - `src/v1/engine/components/database/oracle_output.py` - `NameError`
    (`IDENTIFIER_RE` vs `_IDENTIFIER_RE`) and a renamed-method
    (`qualified_table` vs `_qualified_table`) breakage on every DDL/DML path.
  - `src/v1/java_bridge/java/.../JavaBridge.java` - shared mutable
    `context`/`globalMap` HashMaps are not thread-safe (latent until concurrent
    dispatch is introduced); Decimal output is hardcoded to scale 18.

  Verify these against current `HEAD` before relying on this list; some may have
  been introduced or fixed after the source readings that produced this overview.

- **Parity gaps are documented in-band**: search converter output for
  `_needs_review` entries (severity `engine_gap`) and read inline `D-XX` / `WR-XX`
  / `CR-XX` decision references in the source for the rationale behind non-obvious
  parity choices.
