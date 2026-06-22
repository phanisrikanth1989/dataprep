# DataPrep — Talend ETL Migration Engine

A Python-based ETL execution engine that replaces Talend Open Studio for 1200+ production jobs. The system has two layers: a converter that transforms Talend `.item` XML job definitions into JSON configurations, and an engine that executes those JSON configs. The converter side is clean and standardized. The engine side works partially but has systemic quality gaps, missing features, and unreliable behavior that must be fixed before production use.

**Core value:** Any Talend job using the target components must produce identical results when run through the Python engine — feature parity with Talend is non-negotiable.

## Constraints

- **Tech stack**: Python 3.12+ engine, Java 11+ bridge via Py4J/Arrow — no framework changes
- **Compatibility**: Must produce identical output to Talend for the same input data and job configuration
- **Java bridge**: Must maintain Py4J + Arrow architecture — it works, just needs reliability fixes
- **No breaking changes**: Converter JSON format must remain compatible — engine changes cannot require re-conversion of existing JSONs
- **Existing patterns**: Engine component pattern must align with the established converter pattern philosophy (ABC + registry + per-component organization)

---

## Working with Claude

GSD is retired on this project. No `/gsd-*` commands, no mandatory planning artifacts, no phase docs going forward.

### Workflow

Lean on superpowers skills as the discipline. Invoke them when the trigger applies — don't pretend they don't exist for "small" changes.

- **Before any creative work** (new feature, component, refactor): invoke `superpowers:brainstorming` first. Then `superpowers:writing-plans` for multi-step tasks.
- **Implementation**: follow `superpowers:test-driven-development`. Red → green → refactor. Tests first for non-trivial features and bugfixes.
- **Before claiming done**: follow `superpowers:verification-before-completion`. Run the relevant tests / coverage gate. Evidence before assertions.
- **Debugging**: invoke `superpowers:systematic-debugging` before proposing fixes.

### Discussion before code

For non-trivial work, ask extensive questions and have a complete discussion **before** writing any code. Multi-component changes, base-class touches, new features, and anything in a gray area need 8+ rounds of focused gray-area questions, not one cursory presentation. Surface hidden assumptions proactively — don't silently lock them in.

Small fixes (typos, one-line bugs, doc tweaks) can go direct.

### Git operations

Auto-commits are fine — no need to ask before `git commit`. **Branch discipline is the rule:**

- **Never commit directly to `main`.** Always be on a feature branch. If the current branch is `main` (or any other protected/long-lived branch the user names), stop and ask before committing.
- Check `git status` / current branch before committing. If something looks off (detached HEAD, unexpected branch, dirty unrelated changes), pause and confirm.
- Stage files explicitly by name — avoid `git add -A` / `git add .` to keep stray files (env, credentials, large artifacts) out of commits.
- **Still confirm before** anything destructive or shared: `push`, `push --force`, branch delete, `reset --hard`, `rebase`, amending published commits, tag pushes, PR creation.
- Never skip hooks (`--no-verify`) unless the user explicitly says so. If a hook fails, fix the underlying issue and make a new commit — don't amend after a failed hook.

### `.planning/` directory

Deprecated. Treat as read-only history — useful for "what did phase N decide about X" lookups. **Do not write new entries.** The directory will be cleaned up at some point; don't depend on it.

### Project-specific quirks (from prior sessions)

- **ASCII-only logging.** No emojis or unicode in logs — RHEL servers need clean ASCII.
- **Fix the source, no defensive fallbacks.** If data is bad upstream, fix it there. Don't paper over it downstream.
- **Test the real Java bridge.** Mock-only tests gave false confidence for tMap. Include `@pytest.mark.java` tests that hit the live bridge for any change touching `{{java}}` resolution, tMap, or bridge code.
- **pandas 3.0.1 with CoW is installed** despite some older notes saying otherwise.
- **Rewrite > patch** for systemic issues. Don't bug-by-bug patch when the underlying design is wrong.

---

## Technology Stack

### Languages
- **Python 3.12+** — core converter logic, ETL engine, all business logic
- **Java 11** — Java/Groovy bridge for executing Talend Java expressions (`src/v1/java_bridge/java/`)
- **Groovy 3.0.21** — dynamic expression evaluation within the Java bridge
- **HTML/CSS/JS** — UI design demos (`demos/`)

### Runtime
- Python (CPython) — primary runtime for converter and engine
- JVM (Java 11+) — secondary runtime for Java bridge subprocess, started via `subprocess.Popen`
- Maven (for Java bridge): `src/v1/java_bridge/java/pom.xml`
- No `requirements.txt`, `pyproject.toml` (for deps), or `setup.py`. Dependencies are implicit. No Python lockfile.

### Frameworks & Tooling
- No web framework. This is a CLI/library-based ETL system.
- `pandas` (used heavily) — DataFrame-based data processing throughout the engine
- `pyarrow` — high-performance data serialization for Python-Java bridge
- `pytest` (inferred from `test_*.py` naming, `__init__.py` in test dirs). No `pytest.ini`/`setup.cfg` test config.
- Maven 3.x — Java bridge compilation
- No Python build system (setuptools, poetry, hatch, etc.)
- No automated formatter or linter configured

### Key Dependencies
- `pandas` — core data processing framework. Every engine component inherits `BaseComponent` which uses `pd.DataFrame` as the data transport. See `src/v1/engine/base_component.py`.
- `pyarrow` (Apache Arrow `15.0.2`) — data serialization for Java bridge. See `src/v1/java_bridge/bridge.py`.
- `py4j` (`0.10.9.7`) — Python-Java gateway communication. See `src/v1/java_bridge/bridge.py`.
- `xml.etree.ElementTree` (stdlib) — XML parsing for Talend `.item` files. See `src/converters/talend_to_v1/xml_parser.py`.
- `json`, `re` (stdlib) — JSON output, expression conversion / pattern matching.
- `openpyxl` — `.xlsx` read/write. See `src/v1/engine/components/file/file_input_excel.py`, `file_output_excel.py`.
- `xlrd` — legacy `.xls` reading.
- `lxml` — XML processing with XPath. See `extract_xml_fields.py`, `xml_map.py`.
- `PyYAML` — YAML config parsing for SWIFT transformer.
- `jsonpath_ng` — JSONPath expression evaluation. See `extract_json_fields.py`.
- `numpy` — numerical operations. See `bridge.py`, `python_dataframe_component.py`.
- Groovy `3.0.21` — dynamic script compilation in the Java bridge.

### Configuration
- No `.env` files. No env-var configuration.
- Context variables are passed via JSON job config files (not env vars).
- Java bridge port dynamically allocated via `socket.bind(('', 0))` in `src/v1/engine/java_bridge_manager.py`.
- Java bridge artifact: `src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar`.
- `src/router/ui_registry.json` — component metadata registry for UI rendering. `src/router/basic_ui_registry.json` is the simplified variant.

### Platform Requirements
- Python 3.12+ with pandas, pyarrow, py4j, openpyxl, xlrd, lxml, pyyaml, jsonpath-ng, numpy
- JVM 11+ (only when `java_config.enabled=true` in job config)
- Maven 3.x to (re)build the Java bridge JAR
- Compiled Java bridge JAR present at the path above

### Entry Points (CLI)
- Converter: `python -m src.converters.talend_to_v1.converter <input.item> [output.json]` (see `src/converters/talend_to_v1/converter.py:460-472`)
- Engine: `python src/v1/engine/engine.py <job_config.json> [--context_param KEY=VALUE]` (see `src/v1/engine/engine.py:860-889`)

---

## Conventions

### Naming
- `snake_case.py` for all Python modules: `filter_rows.py`, `file_input_delimited.py`, `aggregate_row.py`
- Tests: `test_<source_name>.py`
- `snake_case` for functions, methods, variables. Private members prefixed with single underscore.
- Static helpers prefixed `_`: `_get_str()`, `_get_bool()`, `_get_int()`, `_parse_schema()`.
- Module-level private helpers prefixed `_`: `_safe_int()`, `_parse_conditions()`.
- Constants `UPPER_SNAKE_CASE`: `REGISTRY`, `DEFAULT_DELIMITER`, `MEMORY_THRESHOLD_MB`.
- Private module-level constants prefixed `_`: `_FLOW_CONNECTOR_TYPES`, `_JAVA_COMPONENT_TYPES`, `_DATE_TOKENS`, `_SKIP_FIELDS`.
- `PascalCase` for classes, dataclasses, enums. Enum members `UPPER_SNAKE_CASE`: `ExecutionMode.BATCH`, `ComponentStatus.SUCCESS`.
- Exception classes end with `Error`: `ETLError`, `ConfigurationError`, `FileOperationError`.
- Type hints from `typing`: `Dict[str, Any]`, `List[str]`, `Optional[int]`.

### Code Style
- 4-space indent. Lines generally under 120 characters (not enforced).
- Double quotes preferred for strings.
- `# noqa: F401` for intentional unused imports.
- `from __future__ import annotations` used consistently in converter module files.

### Imports
- Relative imports within a package: `from ..type_mapping import convert_type`, `from ...base_component import BaseComponent`.
- Absolute imports from project root in tests: `from src.converters.talend_to_v1.converter import TalendToV1Converter`.
- `TYPE_CHECKING` guard for circular imports — see `src/converters/talend_to_v1/components/registry.py`.

### Error Handling
- Converter: errors during component conversion caught at the orchestrator level (`src/converters/talend_to_v1/converter.py:97-107`). Failed conversions produce an `_unsupported` placeholder instead of crashing. Warnings accumulated as `List[str]` in `ComponentResult.warnings`; review items in `ComponentResult.needs_review`.
- Engine: custom exception hierarchy rooted at `ETLError` (`src/v1/engine/exceptions.py`) — `ConfigurationError`, `DataValidationError`, `ComponentExecutionError`, `FileOperationError`, `JavaBridgeError`, `ExpressionError`, `SchemaError`. `ComponentExecutionError` includes `component_id` and `cause`. Components raise specific exceptions from `_process()`; engine catches in `_execute_component()` and tracks `failed_components`.
- Post-conversion validation: `validate_config()` in `src/converters/talend_to_v1/validator.py`. Uses `ValidationIssue` dataclass with `severity` (`error`/`warning`/`info`). Returns `ValidationReport` with `valid`, `issues`, `summary`.

### Logging
- Per-module logger: `logger = logging.getLogger(__name__)`.
- Converter uses `%`-style formatting: `logger.info("Parsed job '%s' with %d nodes", ...)`.
- Engine uses f-strings: `logger.info(f"Component {comp_id} completed")`.
- Engine components prefix log messages with `[{self.id}]` for traceability.
- Levels: DEBUG for data details, INFO for lifecycle, WARNING for degraded operation, ERROR for failures.
- ASCII-only — no emojis/unicode.

### Comments & Docstrings
- Section separators: `# ---- 1. Core parameters ----`
- ASCII dividers between method groups: `# ------------------------------------------------------------------`
- Inline comments only for non-obvious logic.
- Converter modules: reStructuredText-style docstrings with `Parameters` / `Returns`.
- Engine modules: Google-style docstrings with `Args:` / `Returns:` / `Raises:`.
- Triple double-quotes: `"""..."""`. All classes and public methods should have docstrings.

### Function & Module Design
- Methods average 20-50 lines; `_process()` can reach 100+.
- Static helpers preferred over free functions. `self` for core logic, `@staticmethod` for pure utilities.
- Node data passed as typed dataclass (`TalendNode`), not raw dicts.
- Default parameter values via helpers: `_get_str(node, "NAME", "default")`.
- Converter `convert()` returns `ComponentResult` dataclass (component dict + warnings + needs_review).
- Engine `_process()` returns `Dict[str, Any]` with `'main'`, optional `'reject'`, `'stats'`.
- Engine `execute()` returns execution statistics dict.
- `__init__.py` files import and re-export public classes. `__all__` lists used in engine component packages. Converter components use decorator-based auto-registration (no `__all__` needed). `src/v1/engine/__init__.py` exports only `ETLEngine`.

---

## Coverage Gate

Paste-runnable Phase 14 gate command (95% per-module line-coverage floor). Run from project root:

```bash
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

Expected outcome:
- Exit 0 with final stdout line `PASS: all 181 in-scope modules at >= 95.0% line coverage`
- `htmlcov/index.html` regenerated (`htmlcov/` is gitignored)
- `coverage.json` regenerated (consumed by the per-module gate script)

Notes:
- Requires JVM 11+ on PATH — `-m java` tests are measured (includes `java_bridge_manager.py` and tMap live-bridge coverage).
- Oracle live tests stay opt-in via `-m oracle` and are excluded from the gate; the testcontainer suite is the verification path.
- `[tool.coverage.run]` and `[tool.coverage.report]` in `pyproject.toml` are the source of truth for in-scope modules (`*/__init__.py` omitted, legacy `complex_converter/` omitted) and the pragma allowlist (`__main__`, `@abstractmethod`, `raise NotImplementedError`).
- `rm -f .coverage*` prefix is required — stale `.coverage.*` shards from interrupted xdist runs otherwise pollute the JSON report.
- Branch coverage stays off.

Phase 14 locked the final per-module table on 2026-05-11. Historical per-module post-lift table lives at `.planning/phases/14-coverage-push-to-95-per-module-floor/14-COVERAGE.md`; `14-coverage.json` is committed as the machine-readable acceptance artifact.

---

## Architecture

### Pattern Overview
- Component registry pattern for both converter and engine layers
- Abstract base classes enforce consistent component interfaces
- DataFrame-centric data flow between engine components (pandas `pd.DataFrame`)
- Python-Java bridge for executing legacy Java/Groovy expressions (Py4J + Apache Arrow)
- Trigger-based orchestration between subjobs (OnSubjobOk, OnComponentOk, RunIf, etc.)
- Context variable system mirroring Talend's `context.*` and `globalMap` concepts

### Layers

**XML parser** — `src/converters/talend_to_v1/xml_parser.py`. Parses Talend `.item` XML into structured Python dataclasses. Contains `XmlParser` class, `TalendJob` dataclass. Depends on `src/converters/talend_to_v1/components/base.py` (`TalendNode`, `TalendConnection`, `SchemaColumn`). Used by `TalendToV1Converter`.

**Converter components** — `src/converters/talend_to_v1/components/`. ~80 converter classes, one per Talend component type, organized by category (file, transform, database, control, aggregate, context, iterate). Inherit `ComponentConverter` ABC from `base.py`; auto-register via `REGISTRY` from `registry.py`. Used by `TalendToV1Converter.convert_file()`.

**Converter orchestrator** — `src/converters/talend_to_v1/converter.py`. `TalendToV1Converter` class plus `convert_job()` convenience function. Orchestrates the 12-step pipeline: parse, convert components, parse flows, detect subjobs, validate, assemble. Depends on XML parser, component converters, expression converter, trigger mapper, validator, type mapping.

**Engine core** — `src/v1/engine/engine.py`. `ETLEngine` with component registry, execution loop, flow management. Depends on `GlobalMap`, `ContextManager`, `TriggerManager`, `BaseComponent`, `JavaBridgeManager`, `PythonRoutineManager`. Used via `run_job()` CLI or programmatically.

**Engine components** — `src/v1/engine/components/`. ~50 component classes by category (file, transform, aggregate, context, control). Inherit `BaseComponent` from `base_component.py` or `BaseIterateComponent` from `base_iterate_component.py`. Looked up by `ETLEngine` via the decorator `REGISTRY` (`src/v1/engine/component_registry.py`).

**Engine services** — `src/v1/engine/` (top-level files). `GlobalMap`, `ContextManager`, `TriggerManager`, `JavaBridgeManager`, `PythonRoutineManager`, `exceptions.py`. Used by engine core and all components.

**Java bridge** — `src/v1/java_bridge/`. `JavaBridge` Python client (`bridge.py`), Java server (`java/src/main/java/com/citi/gru/etl/JavaBridge.java`, `RowWrapper.java`). Executes Java/Groovy expressions and row-level transformations via Py4J + Arrow. Used by `JavaBridgeManager` and engine components with `{{java}}` expressions.

**Validator** — `src/converters/talend_to_v1/validator.py`. Post-conversion JSON validation: reference integrity, tMap rules, expression quality, conversion quality markers. Used by `TalendToV1Converter.convert_file()` as step 11.

### Data Flow
- `GlobalMap` — Talend-compatible key-value store for component stats (`NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT`) and inter-component variables.
- `ContextManager` — resolves `${context.var}` and `context.var` patterns in config strings; supports file loading and type conversion.
- `data_flows` — engine-internal `Dict[str, Any]` keyed by flow name; stores DataFrames passed between components.
- Java bridge syncs context and globalMap bidirectionally via `_sync_from_java()`.

### Key Abstractions

**`BaseComponent`** — `src/v1/engine/base_component.py`. Template Method pattern. `execute()` handles mode selection, Java expression resolution, context resolution, then delegates to abstract `_process(input_data: Optional[pd.DataFrame]) -> Dict[str, Any]` (must return dict with `main` key, optional `reject`, `stats`). Provides `_update_stats()`, `validate_schema()`, `_update_global_map()`, execution mode auto-selection (batch/streaming/hybrid).

**`BaseIterateComponent`** — `src/v1/engine/base_iterate_component.py`. Iterator pattern for tFileList, tFlowToIterate, tForeach. Overrides `execute()`; provides `has_next_iteration()`, `get_next_iteration_context()`, `finalize_iterations()`. Abstract: `prepare_iterations()`, `set_iteration_globalmap(item)`.

**`ComponentConverter`** — `src/converters/talend_to_v1/components/base.py`. Strategy pattern — one converter per Talend component type. Interface: `convert(node: TalendNode, connections: List[TalendConnection], context: Dict) -> ComponentResult`. Provides `_get_param()`, `_get_str()`, `_get_bool()`, `_get_int()`, `_parse_schema()`, `_build_component_dict()`, `_convert_date_pattern()`.

**`REGISTRY`** (converter) — `src/converters/talend_to_v1/components/registry.py`. Decorator-based: `@REGISTRY.register("tDie")`. Singleton `REGISTRY = ConverterRegistry()`.

**`REGISTRY`** (engine) — decorator-based `ComponentRegistry` singleton in `src/v1/engine/component_registry.py` (mirrors the converter registry). Components self-register via `@REGISTRY.register("FileInputDelimited", "tFileInputDelimited")` (both the camelCase and Talend `t`-prefixed names map to the same class); registration fires through `__init__.py` imports. `ETLEngine._initialize_components()` resolves classes via `REGISTRY.get(comp_type)` (`engine.py:171`). There is no static `COMPONENT_REGISTRY` dict — only two small special-case type groupings (`oracle_component_types`, `mssql_component_types`) in `engine.py` for DB-connection routing.

### Error Handling (system-wide)
- `ETLError` → `ConfigurationError`, `DataValidationError`, `ComponentExecutionError`, `FileOperationError`, `JavaBridgeError`, `ExpressionError`, `SchemaError`.
- `ComponentExecutionError` carries `component_id` and optional `cause`.
- `_execute_component()` catches, marks component failed, records error in `execution_stats`, continues — unless a `Die` component raises with `exit_code` to force termination.
- `die_on_error` config flag controls whether errors are fatal or produce empty DataFrames per component.
- Converter wraps each conversion in try/except and falls back to `_unsupported()` placeholder with warnings.
- Java bridge errors caught and logged; Java execution disabled gracefully if bridge fails to start.

### Cross-Cutting Concerns
- Standard Python `logging` throughout. Module-level loggers via `logging.getLogger(__name__)`.
- Engine components prefix `[{self.id}]` for traceability.
- Three-phase expression resolution in engine: (1) `{{java}}` markers via Java bridge batch execution, (2) `${context.var}` via `ContextManager.resolve_dict()`, (3) bare `context.var` references via regex substitution.
- Converter-side: `ExpressionConverter.detect_java_expression()` aggressively marks Java/Groovy patterns with `{{java}}` for deferred execution. `ExpressionConverter.convert()` handles simpler Java-to-Python transformations (string methods, null checks, operators).
- Converter validation: 4-layer (reference integrity, tMap rules, expression quality, conversion quality). Engine validation: `BaseComponent.validate_schema()` with Talend-to-pandas type mapping. Component-level `_validate_config()` is a voluntary pattern (not enforced by the ABC).
- Database credentials expected in context variables (connection components commented out).
- Batch ETL system, not a web service — no auth/session/middleware concerns.
