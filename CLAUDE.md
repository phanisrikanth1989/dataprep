<!-- GSD:project-start source:PROJECT.md -->
## Project

**DataPrep — Talend ETL Migration Engine**

A Python-based ETL execution engine that replaces Talend Open Studio for 1200+ production jobs. The system has two layers: a converter that transforms Talend `.item` XML job definitions into JSON configurations, and an engine that executes those JSON configs. The converter side is clean and standardized. The engine side works partially but has systemic quality gaps, missing features, and unreliable behavior that must be fixed before production use.

**Core Value:** Any Talend job using the target components must produce identical results when run through the Python engine — feature parity with Talend is non-negotiable.

### Constraints

- **Tech stack**: Python 3.10+ engine, Java 11+ bridge via Py4J/Arrow — no framework changes
- **Compatibility**: Must produce identical output to Talend for the same input data and job configuration
- **Java bridge**: Must maintain Py4J + Arrow architecture — it works, just needs reliability fixes
- **No breaking changes**: Converter JSON format must remain compatible — engine changes cannot require re-conversion of existing JSONs
- **Existing patterns**: Engine component pattern must align with the established converter pattern philosophy (ABC + registry + per-component organization)
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.10+ - Core converter logic, ETL engine, all business logic (uses `set[str]` syntax requiring 3.10+)
- Java 11 - Java/Groovy bridge for executing Talend Java expressions (`src/v1/java_bridge/java/`)
- Groovy 3.0.21 - Dynamic expression evaluation within the Java bridge
- HTML/CSS/JS - UI design demos (`demos/`)
## Runtime
- Python (CPython) - primary runtime for converter and engine
- JVM (Java 11+) - secondary runtime for Java bridge subprocess, started via `subprocess.Popen`
- No `requirements.txt`, `pyproject.toml`, or `setup.py` detected. Dependencies are implicit.
- Maven (for Java bridge): `src/v1/java_bridge/java/pom.xml`
- No lockfile detected for Python dependencies
## Frameworks
- No web framework. This is a CLI/library-based ETL system.
- pandas (used heavily) - DataFrame-based data processing throughout the engine
- Apache Arrow (pyarrow) - High-performance data serialization for Python-Java bridge
- pytest (inferred from `test_*.py` naming convention, `__init__.py` in test dirs)
- No `pytest.ini`, `setup.cfg`, or `pyproject.toml` test config detected
- Maven 3.x - Java bridge compilation (`src/v1/java_bridge/java/pom.xml`)
- No Python build system (setuptools, poetry, hatch, etc.)
## Key Dependencies
- `pandas` - Core data processing framework. Every engine component inherits `BaseComponent` which uses `pd.DataFrame` as the data transport. Used in `src/v1/engine/base_component.py` and all component implementations.
- `pyarrow` (Apache Arrow) - Data serialization for Java bridge. Used in `src/v1/java_bridge/bridge.py` for efficient DataFrame transfer between Python and Java.
- `py4j` - Python-Java gateway communication. Used in `src/v1/java_bridge/bridge.py` to communicate with the JVM subprocess.
- `xml.etree.ElementTree` (stdlib) - XML parsing for Talend `.item` files. Used in `src/converters/talend_to_v1/xml_parser.py`.
- `json` (stdlib) - JSON output serialization. Used in `src/converters/talend_to_v1/converter.py`.
- `re` (stdlib) - Expression conversion and pattern matching. Used in `src/converters/talend_to_v1/expression_converter.py`.
- `openpyxl` - Excel file reading/writing (.xlsx). Used in `src/v1/engine/components/file/file_input_excel.py` and `src/v1/engine/components/file/file_output_excel.py`.
- `xlrd` - Legacy Excel file reading (.xls). Used in `src/v1/engine/components/file/file_input_excel.py`.
- `lxml` - XML processing with XPath support. Used in `src/v1/engine/components/transform/extract_xml_fields.py` and `src/v1/engine/components/transform/xml_map.py`.
- `yaml` (PyYAML) - YAML config parsing for SWIFT transformer. Used in `src/v1/engine/components/transform/swift_transformer.py`, `src/v1/engine/components/transform/swift_block_formatter.py`, and `src/python_routines/swift_transformer.py`.
- `jsonpath_ng` - JSONPath expression evaluation. Used in `src/v1/engine/components/transform/extract_json_fields.py`.
- `numpy` - Numerical operations. Used in `src/v1/java_bridge/bridge.py` and `src/v1/engine/components/transform/python_dataframe_component.py`.
- Apache Arrow `15.0.2` - Arrow vector/IPC for data transfer
- Groovy `3.0.21` - Dynamic script compilation and execution
- Py4J `0.10.9.7` - Gateway server for Python-Java communication
## Configuration
- No `.env` files detected
- No environment variable configuration detected
- Context variables are passed via JSON job config files (not env vars)
- Java bridge port is dynamically allocated via `socket.bind(('', 0))` in `src/v1/engine/java_bridge_manager.py`
- `src/v1/java_bridge/java/pom.xml` - Maven POM for Java bridge JAR
- Java bridge artifact: `target/java-bridge-with-dependencies.jar`
- No Python build configuration files
- `src/router/ui_registry.json` - Component metadata registry defining UI properties, connectors, and settings for each Talend component type
- `src/router/basic_ui_registry.json` - Simplified version of the UI registry
## Platform Requirements
- Python 3.10+ (uses `set[str]` type hint syntax without `from __future__ import annotations` in some modules)
- Java 11+ (for Java bridge, specified in `pom.xml` as `maven.compiler.source=11`)
- Maven 3.x (to build Java bridge JAR)
- Python 3.10+ with pandas, pyarrow, py4j, openpyxl, xlrd, lxml, pyyaml, jsonpath-ng, numpy
- JVM 11+ (only when `java_config.enabled=true` in job config)
- Compiled Java bridge JAR at `src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar`
- Converter: `python -m src.converters.talend_to_v1.converter <input.item> [output.json]` (see `src/converters/talend_to_v1/converter.py:460-472`)
- Engine: `python src/v1/engine/engine.py <job_config.json> [--context_param KEY=VALUE]` (see `src/v1/engine/engine.py:860-889`)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Use `snake_case.py` for all Python modules: `filter_rows.py`, `file_input_delimited.py`, `aggregate_row.py`
- Test files: prefix with `test_` matching the source file name: `test_filter_rows.py`, `test_converter.py`
- Package init files: `__init__.py` in every directory to mark packages
- Use `snake_case` for all functions and methods: `convert_file()`, `_parse_flows()`, `_get_input_data()`
- Private methods prefixed with single underscore: `_process()`, `_validate_config()`, `_execute_component()`
- Static helper methods prefixed with single underscore: `_get_str()`, `_get_bool()`, `_get_int()`, `_parse_schema()`
- Module-level private helpers prefixed with single underscore: `_safe_int()`, `_parse_conditions()`
- Use `snake_case` for all variables: `component_id`, `flow_name`, `job_config`
- Constants use `UPPER_SNAKE_CASE`: `REGISTRY`, `COMPONENT_REGISTRY`, `DEFAULT_DELIMITER`, `MEMORY_THRESHOLD_MB`
- Private module-level constants prefixed with underscore: `_FLOW_CONNECTOR_TYPES`, `_JAVA_COMPONENT_TYPES`, `_DATE_TOKENS`, `_SKIP_FIELDS`
- Use `PascalCase` for all classes: `TalendToV1Converter`, `ComponentConverter`, `FilterRowsConverter`, `ETLEngine`
- Dataclasses follow same pattern: `SchemaColumn`, `TalendNode`, `TalendConnection`, `ComponentResult`
- Enums use `PascalCase` with `UPPER_SNAKE_CASE` members: `ExecutionMode.BATCH`, `ComponentStatus.SUCCESS`
- Exception classes end with `Error`: `ETLError`, `ConfigurationError`, `FileOperationError`
- Use `PascalCase` for type aliases (rare -- mostly inline typing)
- Type hints follow standard `typing` module: `Dict[str, Any]`, `List[str]`, `Optional[int]`
## Code Style
- No automated formatter configured (no `.prettierrc`, `pyproject.toml`, `ruff.toml`, `.flake8` found)
- Indentation: 4 spaces (Python standard)
- Line length: no enforced limit, but lines generally stay under 120 characters
- String quotes: double quotes preferred for strings, single quotes used occasionally in engine code
- No linter configuration detected
- `# noqa: F401` used for intentional unused imports (e.g., `src/converters/talend_to_v1/converter.py` line 23)
- `from __future__ import annotations` used consistently in converter module files
## Import Organization
- Use `from __future__ import annotations` at the top of converter module files
- Relative imports within a package: `from ..type_mapping import convert_type`, `from ...base_component import BaseComponent`
- Absolute imports from project root in tests: `from src.converters.talend_to_v1.converter import TalendToV1Converter`
- `TYPE_CHECKING` guard for circular imports: see `src/converters/talend_to_v1/components/registry.py`
- None configured. All imports use full dotted paths from `src/`.
## Error Handling
- Errors during component conversion are caught at the orchestrator level (`src/converters/talend_to_v1/converter.py` lines 97-107)
- Failed conversions produce an `_unsupported` placeholder instead of crashing
- Warnings accumulated as `List[str]` in `ComponentResult.warnings`
- Review items accumulated as `List[Dict[str, Any]]` in `ComponentResult.needs_review`
- Custom exception hierarchy rooted at `ETLError` (`src/v1/engine/exceptions.py`)
- Exceptions: `ConfigurationError`, `DataValidationError`, `ComponentExecutionError`, `FileOperationError`, `JavaBridgeError`, `ExpressionError`, `SchemaError`
- `ComponentExecutionError` includes `component_id` and `cause` attributes
- Components raise specific exceptions (`ConfigurationError`, `FileOperationError`) from `_process()`
- Engine catches exceptions in `_execute_component()` and tracks `failed_components`
- Post-conversion validation via `validate_config()` in `src/converters/talend_to_v1/validator.py`
- Uses `ValidationIssue` dataclass with `severity` ("error" / "warning" / "info")
- Returns `ValidationReport` with `valid: bool`, `issues: List[ValidationIssue]`, `summary: str`
## Logging
- Each module gets its own logger: `logger = logging.getLogger(__name__)`
- Converter module uses `%`-style formatting with `logger.info()`: `logger.info("Parsed job '%s' with %d nodes", ...)`
- Engine module uses f-strings with `logger.info()`: `logger.info(f"Component {comp_id} completed")`
- Log levels:
- Engine has `logging.basicConfig(level=logging.INFO)` at module level in `src/v1/engine/engine.py`
## Comments
- Section separators for logical groups within a class: `# ---- 1. Core parameters ----`
- ASCII art dividers between method groups: `# ------------------------------------------------------------------`
- Inline comments for non-obvious logic: `# Skip tLibraryLoad -- libraries are extracted separately`
- Config mapping headers at top of converter modules (docstring at file level)
- Converter module: One-line or reStructuredText-style docstrings with `Parameters` / `Returns` sections
- Engine module: Google-style docstrings with `Args:` / `Returns:` / `Raises:` sections
- All classes and public methods should have docstrings
- Use triple double-quotes: `"""Docstring."""`
## Function Design
- Methods average 20-50 lines; larger methods (like `_process()`) can reach 100+ lines
- Static helper methods are preferred over free functions
- Use `self` methods for core logic, `@staticmethod` for pure utilities
- Node data passed as typed dataclass (`TalendNode`) not raw dicts
- Default parameter values provided via helper methods: `_get_str(node, "NAME", "default")`
- Converter `convert()` returns `ComponentResult` dataclass (component dict + warnings + needs_review)
- Engine `_process()` returns `Dict[str, Any]` with keys `'main'`, `'reject'`, `'stats'`
- Engine `execute()` returns execution statistics dict
## Module Design
- `__init__.py` files import and re-export public classes
- `__all__` lists used in engine component packages: `src/v1/engine/components/transform/__init__.py`
- Converter components use decorator-based auto-registration (no `__all__` needed)
- `src/converters/talend_to_v1/components/__init__.py` imports all sub-packages to trigger auto-registration
- `src/v1/engine/components/transform/__init__.py` imports all component classes with `__all__`
- `src/v1/engine/__init__.py` exports only `ETLEngine`
## Dataclass Usage
## Constants
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Component registry pattern for both converter and engine layers
- Abstract base classes enforce consistent component interfaces
- DataFrame-centric data flow between engine components (pandas `pd.DataFrame`)
- Python-Java bridge for executing legacy Java/Groovy expressions (Py4J + Apache Arrow)
- Trigger-based orchestration between subjobs (OnSubjobOk, OnComponentOk, RunIf, etc.)
- Context variable system mirroring Talend's `context.*` and `globalMap` concepts
## Layers
- Purpose: Parse Talend `.item` XML files into structured Python dataclasses
- Location: `src/converters/talend_to_v1/xml_parser.py`
- Contains: `XmlParser` class, `TalendJob` dataclass
- Depends on: `src/converters/talend_to_v1/components/base.py` (for `TalendNode`, `TalendConnection`, `SchemaColumn`)
- Used by: `TalendToV1Converter` in `src/converters/talend_to_v1/converter.py`
- Purpose: Convert parsed Talend nodes into V1 engine JSON component dicts
- Location: `src/converters/talend_to_v1/components/`
- Contains: ~80 converter classes, one per Talend component type, organized by category (file, transform, database, control, aggregate, context, iterate)
- Depends on: `ComponentConverter` ABC from `src/converters/talend_to_v1/components/base.py`, `REGISTRY` from `src/converters/talend_to_v1/components/registry.py`
- Used by: `TalendToV1Converter.convert_file()` in `src/converters/talend_to_v1/converter.py`
- Purpose: Orchestrate the 12-step conversion pipeline (parse, convert components, parse flows, detect subjobs, validate, assemble)
- Location: `src/converters/talend_to_v1/converter.py`
- Contains: `TalendToV1Converter` class, `convert_job()` convenience function
- Depends on: XML parser, component converters, expression converter, trigger mapper, validator, type mapping
- Used by: CLI invocation, tests, batch conversion scripts
- Purpose: Execute ETL jobs from JSON configurations
- Location: `src/v1/engine/engine.py`
- Contains: `ETLEngine` class with component registry, execution loop, flow management
- Depends on: `GlobalMap`, `ContextManager`, `TriggerManager`, `BaseComponent`, `JavaBridgeManager`, `PythonRoutineManager`
- Used by: CLI invocation via `run_job()`, direct programmatic use
- Purpose: Implement individual ETL operations (file I/O, transforms, aggregations, etc.)
- Location: `src/v1/engine/components/`
- Contains: ~50 component classes organized by category (file, transform, aggregate, context, control)
- Depends on: `BaseComponent` from `src/v1/engine/base_component.py`, `BaseIterateComponent` from `src/v1/engine/base_iterate_component.py`
- Used by: `ETLEngine` via `COMPONENT_REGISTRY` lookup
- Purpose: Shared services for state management, triggers, and cross-language execution
- Location: `src/v1/engine/` (top-level files)
- Contains: `GlobalMap`, `ContextManager`, `TriggerManager`, `JavaBridgeManager`, `PythonRoutineManager`, `exceptions.py`
- Used by: Engine core and all components
- Purpose: Execute Java/Groovy expressions and row-level transformations via Py4J
- Location: `src/v1/java_bridge/`
- Contains: `JavaBridge` Python client (`bridge.py`), Java server (`java/src/main/java/com/citi/gru/etl/JavaBridge.java`, `RowWrapper.java`)
- Depends on: Py4J, Apache Arrow (for DataFrame transfer)
- Used by: `JavaBridgeManager`, engine components with `{{java}}` expressions
- Purpose: Post-conversion validation of generated JSON configs
- Location: `src/converters/talend_to_v1/validator.py`
- Contains: Reference integrity checks, tMap validation, expression quality checks, conversion quality markers
- Used by: `TalendToV1Converter.convert_file()` as step 11
## Data Flow
- `GlobalMap`: Talend-compatible key-value store for component stats (`NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT`) and inter-component variables
- `ContextManager`: Resolves `${context.var}` and `context.var` patterns in config strings, supports loading from files, type conversion
- `data_flows`: Engine-internal dict (`Dict[str, Any]`) keyed by flow name, stores DataFrames passed between components
- Java Bridge syncs context and globalMap bidirectionally via `_sync_from_java()`
## Key Abstractions
- Purpose: Abstract base for all engine components that process data
- Location: `src/v1/engine/base_component.py`
- Pattern: Template Method -- `execute()` handles mode selection, Java expression resolution, context resolution, then delegates to abstract `_process()` method
- Key interface: `_process(input_data: Optional[pd.DataFrame]) -> Dict[str, Any]` must return dict with `main` key (output DataFrame) and optional `reject`, `stats` keys
- Provides: `_update_stats()`, `validate_schema()`, `_update_global_map()`, execution mode auto-selection (batch/streaming/hybrid)
- Purpose: Base for components that produce iterations (tFileList, tFlowToIterate, tForeach)
- Location: `src/v1/engine/base_iterate_component.py`
- Pattern: Iterator -- overrides `execute()` to prepare iteration items, provides `has_next_iteration()`, `get_next_iteration_context()`, `finalize_iterations()`
- Key abstract methods: `prepare_iterations()`, `set_iteration_globalmap(item)`
- Purpose: Abstract base for all Talend-to-V1 component converters
- Location: `src/converters/talend_to_v1/components/base.py`
- Pattern: Strategy -- each converter encapsulates conversion logic for one Talend component type
- Key interface: `convert(node: TalendNode, connections: List[TalendConnection], context: Dict) -> ComponentResult`
- Provides: `_get_param()`, `_get_str()`, `_get_bool()`, `_get_int()`, `_parse_schema()`, `_build_component_dict()`, `_convert_date_pattern()`
- Purpose: Maps Talend component type names (e.g., `"tFileInputDelimited"`) to converter classes
- Location: `src/converters/talend_to_v1/components/registry.py`
- Pattern: Decorator-based registry -- `@REGISTRY.register("tDie")` decorates converter classes for auto-registration on import
- Singleton: `REGISTRY = ConverterRegistry()` at module level
- Purpose: Maps component type names (both V1 and Talend aliases) to engine component classes
- Location: `src/v1/engine/engine.py` (class attribute of `ETLEngine`)
- Pattern: Static dict -- manually maintained, maps both camelCase (`FileInputDelimited`) and Talend (`tFileInputDelimited`) names
## Entry Points
- Location: `src/converters/talend_to_v1/converter.py` (line 460, `__main__` block)
- Triggers: `python -m src.converters.talend_to_v1.converter <input.item> [output.json]`
- Responsibilities: Convert a single Talend XML file to V1 JSON config
- Location: `src/v1/engine/engine.py` (line 860, `__main__` block)
- Triggers: `python src/v1/engine/engine.py <job_config.json> [--context_param KEY=VALUE]`
- Responsibilities: Execute an ETL job from JSON config with optional context overrides
- `convert_job(input_path, output_path)` in `src/converters/talend_to_v1/converter.py` -- convert and optionally write JSON
- `run_job(job_config_path, context_overrides)` in `src/v1/engine/engine.py` -- load, configure, and execute a job
- Location: `src/converters/complex_converter/converter.py`
- Contains: `ComplexTalendConverter` -- older converter implementation (superseded by `talend_to_v1`)
- Location: `tests/converters/talend_to_v1/batch_convert.py`
- Purpose: Batch-convert multiple Talend XML files for testing
- Location: `scripts/add_connectors.py`
- Purpose: Add connector metadata to `src/router/ui_registry.json` for UI rendering
## Error Handling
- Custom exception hierarchy in `src/v1/engine/exceptions.py`: `ETLError` -> `ConfigurationError`, `DataValidationError`, `ComponentExecutionError`, `FileOperationError`, `JavaBridgeError`, `ExpressionError`, `SchemaError`
- `ComponentExecutionError` carries `component_id` and optional `cause` for structured error reporting
- Engine catches component exceptions in `_execute_component()`, marks component as failed, records error in `execution_stats`, and continues to next component (unless `Die` component raises with `exit_code`)
- `Die` component raises `ComponentExecutionError` with `exit_code` attribute to force job termination
- Components support `die_on_error` config flag to control whether errors are fatal or produce empty DataFrames
- Converter layer wraps each component conversion in try/except, falls back to `_unsupported()` placeholder on error with warnings
- Java bridge errors caught and logged; Java execution disabled gracefully if bridge fails to start
## Cross-Cutting Concerns
- Standard Python `logging` module throughout
- Module-level loggers via `logging.getLogger(__name__)`
- Engine components use `[{self.id}]` prefix in log messages for traceability
- Log levels used consistently: DEBUG for data details, INFO for lifecycle events, WARNING for degraded operation, ERROR for failures
- Converter-side: 4-layer post-conversion validation (reference integrity, tMap rules, expression quality, conversion quality)
- Engine-side: Schema validation via `BaseComponent.validate_schema()` with Talend-to-pandas type mapping
- Component-level: `_validate_config()` method pattern (not enforced by ABC, implemented voluntarily)
- Three-phase resolution in engine: (1) `{{java}}` markers resolved via Java bridge batch execution, (2) `${context.var}` resolved by `ContextManager.resolve_dict()`, (3) `context.var` bare references resolved by regex substitution
- Converter-side: `ExpressionConverter.detect_java_expression()` aggressively marks Java/Groovy patterns with `{{java}}` prefix for deferred execution
- `ExpressionConverter.convert()` handles simpler Java-to-Python transformations (string methods, null checks, operators)
- Not applicable -- this is a batch ETL system, not a web service
- Database credentials expected in context variables (connection components commented out)
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
