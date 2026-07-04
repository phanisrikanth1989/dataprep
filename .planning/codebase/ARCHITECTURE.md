# Architecture

**Analysis Date:** 2026-04-14

## Pattern Overview

**Overall:** Component-Based ETL Pipeline Engine with Converter Layer

This is a Talend-to-Python ETL migration system composed of two primary subsystems:
1. A **Converter** that transforms Talend `.item` XML job definitions into JSON configuration
2. An **Execution Engine** that reads JSON configurations and runs ETL jobs using a component-based architecture

**Key Characteristics:**
- Component registry pattern for both converter and engine layers
- Abstract base classes enforce consistent component interfaces
- DataFrame-centric data flow between engine components (pandas `pd.DataFrame`)
- Python-Java bridge for executing legacy Java/Groovy expressions (Py4J + Apache Arrow)
- Trigger-based orchestration between subjobs (OnSubjobOk, OnComponentOk, RunIf, etc.)
- Context variable system mirroring Talend's `context.*` and `globalMap` concepts

## Layers

**XML Parsing Layer (Converter Input):**
- Purpose: Parse Talend `.item` XML files into structured Python dataclasses
- Location: `src/converters/talend_to_v1/xml_parser.py`
- Contains: `XmlParser` class, `TalendJob` dataclass
- Depends on: `src/converters/talend_to_v1/components/base.py` (for `TalendNode`, `TalendConnection`, `SchemaColumn`)
- Used by: `TalendToV1Converter` in `src/converters/talend_to_v1/converter.py`

**Component Converter Layer:**
- Purpose: Convert parsed Talend nodes into V1 engine JSON component dicts
- Location: `src/converters/talend_to_v1/components/`
- Contains: ~80 converter classes, one per Talend component type, organized by category (file, transform, database, control, aggregate, context, iterate)
- Depends on: `ComponentConverter` ABC from `src/converters/talend_to_v1/components/base.py`, `REGISTRY` from `src/converters/talend_to_v1/components/registry.py`
- Used by: `TalendToV1Converter.convert_file()` in `src/converters/talend_to_v1/converter.py`

**Converter Orchestrator:**
- Purpose: Orchestrate the 12-step conversion pipeline (parse, convert components, parse flows, detect subjobs, validate, assemble)
- Location: `src/converters/talend_to_v1/converter.py`
- Contains: `TalendToV1Converter` class, `convert_job()` convenience function
- Depends on: XML parser, component converters, expression converter, trigger mapper, validator, type mapping
- Used by: CLI invocation, tests, batch conversion scripts

**Engine Core Layer:**
- Purpose: Execute ETL jobs from JSON configurations
- Location: `src/v1/engine/engine.py`
- Contains: `ETLEngine` class with component registry, execution loop, flow management
- Depends on: `GlobalMap`, `ContextManager`, `TriggerManager`, `BaseComponent`, `JavaBridgeManager`, `PythonRoutineManager`
- Used by: CLI invocation via `run_job()`, direct programmatic use

**Engine Component Layer:**
- Purpose: Implement individual ETL operations (file I/O, transforms, aggregations, etc.)
- Location: `src/v1/engine/components/`
- Contains: ~50 component classes organized by category (file, transform, aggregate, context, control)
- Depends on: `BaseComponent` from `src/v1/engine/base_component.py`, `BaseIterateComponent` from `src/v1/engine/base_iterate_component.py`
- Used by: `ETLEngine` via `COMPONENT_REGISTRY` lookup

**Infrastructure Layer:**
- Purpose: Shared services for state management, triggers, and cross-language execution
- Location: `src/v1/engine/` (top-level files)
- Contains: `GlobalMap`, `ContextManager`, `TriggerManager`, `JavaBridgeManager`, `PythonRoutineManager`, `exceptions.py`
- Used by: Engine core and all components

**Java Bridge Layer:**
- Purpose: Execute Java/Groovy expressions and row-level transformations via Py4J
- Location: `src/v1/java_bridge/`
- Contains: `JavaBridge` Python client (`bridge.py`), Java server (`java/src/main/java/com/citi/gru/etl/JavaBridge.java`, `RowWrapper.java`)
- Depends on: Py4J, Apache Arrow (for DataFrame transfer)
- Used by: `JavaBridgeManager`, engine components with `{{java}}` expressions

**Validation Layer:**
- Purpose: Post-conversion validation of generated JSON configs
- Location: `src/converters/talend_to_v1/validator.py`
- Contains: Reference integrity checks, tMap validation, expression quality checks, conversion quality markers
- Used by: `TalendToV1Converter.convert_file()` as step 11

## Data Flow

**Conversion Pipeline (Talend XML to V1 JSON):**

1. `XmlParser.parse(filepath)` parses `.item` XML into `TalendJob` (nodes, connections, context, routines, libraries)
2. Context variables are mapped to Python types via `type_mapping.convert_type()`
3. Each `TalendNode` is looked up in `REGISTRY` -> converter class instantiated -> `converter.convert(node, connections, context)` returns `ComponentResult`
4. Connections with `FLOW`/`MAIN`/`REJECT`/`FILTER`/`ITERATE` types become flow dicts
5. Component inputs/outputs are updated from flows; input schemas propagated from upstream output schemas
6. Trigger connections (`SUBJOB_OK`, `COMPONENT_OK`, `RUN_IF`, etc.) are mapped via `trigger_mapper.map_triggers()`
7. Subjobs detected via DFS on flow adjacency graph
8. Java requirement detected by scanning for Java component types and `{{java}}` markers in config
9. `validator.validate_config()` runs 4 validation layers (reference integrity, tMap, expressions, conversion quality)
10. Final JSON config assembled with components, flows, triggers, subjobs, java_config, validation report

**Engine Execution Pipeline (V1 JSON to ETL Results):**

1. `ETLEngine.__init__(job_config)` loads JSON, initializes `GlobalMap`, `ContextManager`, `TriggerManager`
2. If `java_config.enabled`, `JavaBridgeManager` starts Java subprocess on dynamic port via Py4J
3. If `python_config.enabled`, `PythonRoutineManager` loads `.py` files from routines directory
4. Components instantiated from `COMPONENT_REGISTRY` dict mapping type names to classes
5. Triggers parsed from both top-level `triggers` array and component-level `triggers`
6. Subjobs identified by `subjob_id` or auto-detected via flow connectivity
7. Execution loop: BFS-style queue processes components when all inputs are ready and their subjob is active
8. Per-component execution: resolve `{{java}}` expressions -> resolve `${context.var}` -> auto-select batch/streaming mode -> call `_process()` -> store results in `data_flows` dict
9. After component completes, `TriggerManager.get_triggered_components()` activates downstream subjobs
10. Iterate components (`BaseIterateComponent`) re-execute downstream subjobs for each iteration item

**State Management:**
- `GlobalMap`: Talend-compatible key-value store for component stats (`NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT`) and inter-component variables
- `ContextManager`: Resolves `${context.var}` and `context.var` patterns in config strings, supports loading from files, type conversion
- `data_flows`: Engine-internal dict (`Dict[str, Any]`) keyed by flow name, stores DataFrames passed between components
- Java Bridge syncs context and globalMap bidirectionally via `_sync_from_java()`

## Key Abstractions

**BaseComponent (Engine):**
- Purpose: Abstract base for all engine components that process data
- Location: `src/v1/engine/base_component.py`
- Pattern: Template Method -- `execute()` handles mode selection, Java expression resolution, context resolution, then delegates to abstract `_process()` method
- Key interface: `_process(input_data: Optional[pd.DataFrame]) -> Dict[str, Any]` must return dict with `main` key (output DataFrame) and optional `reject`, `stats` keys
- Provides: `_update_stats()`, `validate_schema()`, `_update_global_map()`, execution mode auto-selection (batch/streaming/hybrid)

**BaseIterateComponent (Engine):**
- Purpose: Base for components that produce iterations (tFileList, tFlowToIterate, tForeach)
- Location: `src/v1/engine/base_iterate_component.py`
- Pattern: Iterator -- overrides `execute()` to prepare iteration items, provides `has_next_iteration()`, `get_next_iteration_context()`, `finalize_iterations()`
- Key abstract methods: `prepare_iterations()`, `set_iteration_globalmap(item)`

**ComponentConverter (Converter):**
- Purpose: Abstract base for all Talend-to-V1 component converters
- Location: `src/converters/talend_to_v1/components/base.py`
- Pattern: Strategy -- each converter encapsulates conversion logic for one Talend component type
- Key interface: `convert(node: TalendNode, connections: List[TalendConnection], context: Dict) -> ComponentResult`
- Provides: `_get_param()`, `_get_str()`, `_get_bool()`, `_get_int()`, `_parse_schema()`, `_build_component_dict()`, `_convert_date_pattern()`

**ConverterRegistry:**
- Purpose: Maps Talend component type names (e.g., `"tFileInputDelimited"`) to converter classes
- Location: `src/converters/talend_to_v1/components/registry.py`
- Pattern: Decorator-based registry -- `@REGISTRY.register("tDie")` decorates converter classes for auto-registration on import
- Singleton: `REGISTRY = ConverterRegistry()` at module level

**COMPONENT_REGISTRY (Engine):**
- Purpose: Maps component type names (both V1 and Talend aliases) to engine component classes
- Location: `src/v1/engine/engine.py` (class attribute of `ETLEngine`)
- Pattern: Static dict -- manually maintained, maps both camelCase (`FileInputDelimited`) and Talend (`tFileInputDelimited`) names

## Entry Points

**Converter CLI:**
- Location: `src/converters/talend_to_v1/converter.py` (line 460, `__main__` block)
- Triggers: `python -m src.converters.talend_to_v1.converter <input.item> [output.json]`
- Responsibilities: Convert a single Talend XML file to V1 JSON config

**Engine CLI:**
- Location: `src/v1/engine/engine.py` (line 860, `__main__` block)
- Triggers: `python src/v1/engine/engine.py <job_config.json> [--context_param KEY=VALUE]`
- Responsibilities: Execute an ETL job from JSON config with optional context overrides

**Convenience Functions:**
- `convert_job(input_path, output_path)` in `src/converters/talend_to_v1/converter.py` -- convert and optionally write JSON
- `run_job(job_config_path, context_overrides)` in `src/v1/engine/engine.py` -- load, configure, and execute a job

**Legacy Converter:**
- Location: `src/converters/complex_converter/converter.py`
- Contains: `ComplexTalendConverter` -- older converter implementation (superseded by `talend_to_v1`)

**Batch Conversion Script:**
- Location: `tests/converters/talend_to_v1/batch_convert.py`
- Purpose: Batch-convert multiple Talend XML files for testing

**UI Registry Script:**
- Location: `scripts/add_connectors.py`
- Purpose: Add connector metadata to `src/router/ui_registry.json` for UI rendering

## Error Handling

**Strategy:** Exception hierarchy rooted at `ETLError`, with component-level error containment and configurable fail-fast behavior

**Patterns:**
- Custom exception hierarchy in `src/v1/engine/exceptions.py`: `ETLError` -> `ConfigurationError`, `DataValidationError`, `ComponentExecutionError`, `FileOperationError`, `JavaBridgeError`, `ExpressionError`, `SchemaError`
- `ComponentExecutionError` carries `component_id` and optional `cause` for structured error reporting
- Engine catches component exceptions in `_execute_component()`, marks component as failed, records error in `execution_stats`, and continues to next component (unless `Die` component raises with `exit_code`)
- `Die` component raises `ComponentExecutionError` with `exit_code` attribute to force job termination
- Components support `die_on_error` config flag to control whether errors are fatal or produce empty DataFrames
- Converter layer wraps each component conversion in try/except, falls back to `_unsupported()` placeholder on error with warnings
- Java bridge errors caught and logged; Java execution disabled gracefully if bridge fails to start

## Cross-Cutting Concerns

**Logging:**
- Standard Python `logging` module throughout
- Module-level loggers via `logging.getLogger(__name__)`
- Engine components use `[{self.id}]` prefix in log messages for traceability
- Log levels used consistently: DEBUG for data details, INFO for lifecycle events, WARNING for degraded operation, ERROR for failures

**Validation:**
- Converter-side: 4-layer post-conversion validation (reference integrity, tMap rules, expression quality, conversion quality)
- Engine-side: Schema validation via `BaseComponent.validate_schema()` with Talend-to-pandas type mapping
- Component-level: `_validate_config()` method pattern (not enforced by ABC, implemented voluntarily)

**Expression Resolution:**
- Three-phase resolution in engine: (1) `{{java}}` markers resolved via Java bridge batch execution, (2) `${context.var}` resolved by `ContextManager.resolve_dict()`, (3) `context.var` bare references resolved by regex substitution
- Converter-side: `ExpressionConverter.detect_java_expression()` aggressively marks Java/Groovy patterns with `{{java}}` prefix for deferred execution
- `ExpressionConverter.convert()` handles simpler Java-to-Python transformations (string methods, null checks, operators)

**Authentication/Security:**
- Not applicable -- this is a batch ETL system, not a web service
- Database credentials expected in context variables (connection components commented out)

---

*Architecture analysis: 2026-04-14*
