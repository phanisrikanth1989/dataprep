# Codebase Structure

**Analysis Date:** 2026-04-14

## Directory Layout

```
dataprep/
├── src/                              # All source code
│   ├── converters/                   # Talend-to-V1 conversion subsystem
│   │   ├── complex_converter/        # Legacy converter (superseded)
│   │   │   ├── __init__.py
│   │   │   ├── converter.py          # ComplexTalendConverter class
│   │   │   ├── component_parser.py   # Legacy component parsing
│   │   │   └── expression_converter.py  # Legacy expression conversion
│   │   └── talend_to_v1/            # Current converter (primary)
│   │       ├── __init__.py
│   │       ├── converter.py          # TalendToV1Converter orchestrator
│   │       ├── xml_parser.py         # XML parsing into TalendJob
│   │       ├── expression_converter.py  # Java-to-Python expression handling
│   │       ├── trigger_mapper.py     # Trigger connection mapping
│   │       ├── type_mapping.py       # Talend-to-Python type map
│   │       ├── validator.py          # Post-conversion validation
│   │       └── components/           # Per-component converters
│   │           ├── __init__.py       # Auto-imports all category packages
│   │           ├── base.py           # ComponentConverter ABC, dataclasses
│   │           ├── registry.py       # Decorator-based ConverterRegistry
│   │           ├── aggregate/        # tAggregateRow, tUniqueRow
│   │           ├── context/          # tContextLoad
│   │           ├── control/          # tDie, tLoop, tRunJob, tSendMail, etc.
│   │           ├── database/         # tOracleConnection, tMSSqlInput, etc.
│   │           ├── file/             # tFileInputDelimited, tFileCopy, etc.
│   │           ├── iterate/          # tFlowToIterate, tForeach
│   │           └── transform/        # tMap, tFilterRow, tJavaRow, etc.
│   ├── v1/                           # V1 engine subsystem
│   │   ├── engine/                   # ETL execution engine
│   │   │   ├── __init__.py           # Exports ETLEngine
│   │   │   ├── engine.py             # ETLEngine class, COMPONENT_REGISTRY
│   │   │   ├── base_component.py     # BaseComponent ABC
│   │   │   ├── base_iterate_component.py  # BaseIterateComponent ABC
│   │   │   ├── global_map.py         # GlobalMap state store
│   │   │   ├── context_manager.py    # ContextManager for variable resolution
│   │   │   ├── trigger_manager.py    # TriggerManager for subjob orchestration
│   │   │   ├── java_bridge_manager.py  # JavaBridgeManager lifecycle
│   │   │   ├── python_routine_manager.py  # PythonRoutineManager loader
│   │   │   ├── exceptions.py         # Custom exception hierarchy
│   │   │   └── components/           # Engine component implementations
│   │   │       ├── aggregate/        # AggregateRow, UniqueRow
│   │   │       ├── context/          # ContextLoad
│   │   │       ├── control/          # Warn, Die, SleepComponent, SendMail
│   │   │       ├── file/             # FileInputDelimited, FileCopy, etc.
│   │   │       └── transform/        # Map, FilterRows, JavaRowComponent, etc.
│   │   └── java_bridge/              # Python-Java bridge via Py4J
│   │       ├── __init__.py
│   │       ├── bridge.py             # JavaBridge Python client
│   │       └── java/                 # Java server source
│   │           └── src/main/java/com/citi/gru/etl/
│   │               ├── JavaBridge.java   # Py4J gateway entry point
│   │               └── RowWrapper.java   # Row access wrapper
│   ├── python_routines/              # Custom Python routines
│   │   └── swift_transformer.py      # SWIFT message transformer routine
│   └── router/                       # UI registry data
│       ├── basic_ui_registry.json    # Minimal UI component registry
│       └── ui_registry.json          # Full UI component registry with connectors
├── tests/                            # Test suite (mirrors src/ structure)
│   ├── __init__.py
│   ├── converters/
│   │   ├── __init__.py
│   │   └── talend_to_v1/
│   │       ├── __init__.py
│   │       ├── batch_convert.py      # Batch conversion utility
│   │       ├── test_base.py          # Tests for ComponentConverter base
│   │       ├── test_converter.py     # Tests for TalendToV1Converter
│   │       ├── test_integration.py   # Integration tests
│   │       ├── test_registry.py      # Tests for ConverterRegistry
│   │       ├── test_trigger_mapper.py  # Tests for trigger mapping
│   │       ├── test_type_mapping.py  # Tests for type mapping
│   │       ├── test_validator.py     # Tests for validator
│   │       ├── test_xml_parser.py    # Tests for XML parser
│   │       └── components/           # Per-component converter tests
│   │           ├── aggregate/        # test_aggregate_row.py, test_unique_row.py
│   │           ├── context/          # test_context_load.py
│   │           ├── control/          # test_die.py, test_loop.py, etc.
│   │           ├── database/         # test_oracle_connection.py, etc.
│   │           ├── file/             # test_file_input_delimited.py, etc.
│   │           ├── iterate/          # test_flow_to_iterate.py, test_foreach.py
│   │           └── transform/        # test_map.py, test_filter_rows.py, etc.
│   └── talend_xml_samples/           # Test fixture XML and JSON files
│       └── converted_jsons/          # Expected conversion outputs
├── docs/                             # Documentation
│   ├── ARCHITECTURE.md               # System architecture overview
│   ├── v1/
│   │   ├── STANDARDS.md              # V1 standards
│   │   ├── standards/                # Detailed standards docs
│   │   │   ├── CONVERTER_PATTERN.md  # Converter implementation guide
│   │   │   ├── TEST_PATTERN.md       # Test implementation guide
│   │   │   └── ...
│   │   ├── audit/                    # Component audit reports
│   │   │   ├── SUMMARY_SCORECARD.md
│   │   │   ├── CROSS_CUTTING_ISSUES.md
│   │   │   └── components/           # Per-component audit docs
│   │   └── talend_to_v1_converter_guide.md
│   └── ...                           # Various guides and references
├── demos/                            # HTML UI demos (standalone)
│   ├── 1-glassmorphism-nodes.html
│   ├── 2-purple-dark-theme.html
│   ├── 3-rounded-pill-nodes.html
│   └── 4-command-palette.html
├── scripts/                          # Utility scripts
│   └── add_connectors.py            # Add connector metadata to UI registry
└── .gitignore                        # Git ignore rules
```

## Directory Purposes

**`src/converters/talend_to_v1/`:**
- Purpose: Convert Talend `.item` XML files into V1 engine JSON configurations
- Contains: Orchestrator, XML parser, expression converter, trigger mapper, validator, type mapping, and per-component converter classes
- Key files: `converter.py` (main entry), `xml_parser.py` (parsing), `components/base.py` (ABC), `components/registry.py` (registration)

**`src/converters/talend_to_v1/components/`:**
- Purpose: Individual converter implementations for each Talend component type
- Contains: Python files named in `snake_case` matching the Talend component (e.g., `file_input_delimited.py` for `tFileInputDelimited`)
- Organization: Subdirectories by category: `aggregate/`, `context/`, `control/`, `database/`, `file/`, `iterate/`, `transform/`
- Each file exports one class decorated with `@REGISTRY.register("tComponentName")`

**`src/converters/complex_converter/`:**
- Purpose: Legacy converter implementation (predates `talend_to_v1`)
- Contains: `ComplexTalendConverter` class -- older, less modular approach
- Status: Superseded by `talend_to_v1` converter but still present in codebase

**`src/v1/engine/`:**
- Purpose: Core ETL execution engine
- Contains: `ETLEngine` class, base component ABCs, infrastructure services (GlobalMap, ContextManager, TriggerManager), exception hierarchy
- Key files: `engine.py` (orchestrator + registry), `base_component.py` (ABC), `base_iterate_component.py` (iterate ABC)

**`src/v1/engine/components/`:**
- Purpose: Engine component implementations that perform actual ETL operations
- Contains: Python files named in `snake_case` (e.g., `file_input_delimited.py`)
- Organization: Subdirectories by category: `aggregate/`, `context/`, `control/`, `file/`, `transform/`
- Note: No `database/` or `iterate/` subdirectories in engine components (database components are commented out in `engine.py`; iterate components like `FileList` exist in `file/`)

**`src/v1/java_bridge/`:**
- Purpose: Python-Java interop for executing Java/Groovy expressions
- Contains: `bridge.py` (Python Py4J client), `java/` (Java Py4J server, Maven project)
- Dependencies: Py4J, Apache Arrow (for efficient DataFrame transfer)

**`src/python_routines/`:**
- Purpose: Custom Python routine modules loaded at runtime by `PythonRoutineManager`
- Contains: `.py` files that are auto-discovered and loaded as modules
- Current file: `swift_transformer.py` (SWIFT message processing)

**`src/router/`:**
- Purpose: UI component registry data for a visual job designer
- Contains: JSON files describing component metadata, categories, and connector ports
- Key files: `ui_registry.json` (full registry), `basic_ui_registry.json` (minimal)

**`tests/`:**
- Purpose: Test suite mirroring the converter source structure
- Contains: Unit tests for each converter component, integration tests, infrastructure tests
- Key files: `test_converter.py`, `test_integration.py`, `test_xml_parser.py`
- Note: Tests exist only for the converter layer (`tests/converters/`); no engine tests

**`tests/talend_xml_samples/`:**
- Purpose: Test fixtures -- Talend XML input files and expected JSON conversion outputs
- Contains: `converted_jsons/` with ~31 JSON files matching specific Talend component jobs

**`docs/`:**
- Purpose: Project documentation, standards, and audit reports
- Contains: Architecture docs, implementation guides, component audit reports
- Key subdirectory: `docs/v1/standards/` (CONVERTER_PATTERN.md, TEST_PATTERN.md)
- Key subdirectory: `docs/v1/audit/components/` (per-component audit reports)

**`demos/`:**
- Purpose: Standalone HTML demos for UI visualization concepts
- Contains: 4 HTML files demonstrating different node rendering styles
- Status: Prototype/exploratory -- not part of the core system

**`scripts/`:**
- Purpose: One-off utility scripts
- Contains: `add_connectors.py` -- adds connector metadata to UI registry JSON

## Key File Locations

**Entry Points:**
- `src/converters/talend_to_v1/converter.py`: Converter CLI and `convert_job()` function
- `src/v1/engine/engine.py`: Engine CLI and `run_job()` function

**Configuration:**
- `src/router/ui_registry.json`: UI component registry (240KB)
- `.gitignore`: Git ignore rules

**Core Logic - Converter:**
- `src/converters/talend_to_v1/converter.py`: 12-step conversion orchestrator
- `src/converters/talend_to_v1/xml_parser.py`: Talend XML parsing
- `src/converters/talend_to_v1/components/base.py`: Converter ABC + dataclasses
- `src/converters/talend_to_v1/components/registry.py`: Decorator-based registry
- `src/converters/talend_to_v1/expression_converter.py`: Java expression detection and conversion
- `src/converters/talend_to_v1/trigger_mapper.py`: Trigger connection mapping
- `src/converters/talend_to_v1/validator.py`: Post-conversion validation
- `src/converters/talend_to_v1/type_mapping.py`: Talend-to-Python type mapping (single source of truth)

**Core Logic - Engine:**
- `src/v1/engine/engine.py`: ETLEngine class with COMPONENT_REGISTRY and execution loop
- `src/v1/engine/base_component.py`: BaseComponent ABC (template method pattern)
- `src/v1/engine/base_iterate_component.py`: BaseIterateComponent ABC (iterator pattern)
- `src/v1/engine/global_map.py`: GlobalMap key-value store
- `src/v1/engine/context_manager.py`: Context variable resolution
- `src/v1/engine/trigger_manager.py`: Trigger/subjob orchestration
- `src/v1/engine/java_bridge_manager.py`: Java bridge lifecycle
- `src/v1/engine/python_routine_manager.py`: Python routine loading
- `src/v1/engine/exceptions.py`: Exception hierarchy
- `src/v1/java_bridge/bridge.py`: Py4J bridge client

**Testing:**
- `tests/converters/talend_to_v1/test_converter.py`: Converter orchestrator tests
- `tests/converters/talend_to_v1/test_integration.py`: End-to-end integration tests
- `tests/converters/talend_to_v1/test_xml_parser.py`: XML parser tests
- `tests/converters/talend_to_v1/components/`: Per-component converter tests

## Naming Conventions

**Files:**
- `snake_case.py`: All Python source files (e.g., `file_input_delimited.py`, `context_manager.py`)
- `test_snake_case.py`: All test files prefixed with `test_` (e.g., `test_file_input_delimited.py`)
- Converter component files match the Talend component name in snake_case (e.g., `tFileInputDelimited` -> `file_input_delimited.py`)
- Engine component files match the V1 component name in snake_case (e.g., `FileInputDelimited` -> `file_input_delimited.py`)

**Directories:**
- `snake_case/`: All directories use lowercase with underscores (e.g., `talend_to_v1/`, `java_bridge/`)
- Category subdirectories under `components/`: `aggregate/`, `context/`, `control/`, `database/`, `file/`, `iterate/`, `transform/`

**Classes:**
- `PascalCase`: All classes (e.g., `FileInputDelimited`, `TalendToV1Converter`, `DieConverter`)
- Engine components: Named after the V1 type (e.g., `FileInputDelimited`, `Map`, `FilterRows`)
- Converter components: Named as `{ComponentName}Converter` (e.g., `DieConverter`, `FileInputDelimitedConverter`)

**Registry Keys:**
- Engine `COMPONENT_REGISTRY`: Maps both `PascalCase` V1 names (e.g., `"FileInputDelimited"`) and Talend `tCamelCase` names (e.g., `"tFileInputDelimited"`) to the same class
- Converter `REGISTRY`: Uses `@REGISTRY.register("tComponentName")` with Talend names (e.g., `"tDie"`, `"tFileInputDelimited"`)

## Where to Add New Code

**New Engine Component:**
1. Create `src/v1/engine/components/{category}/{component_name}.py`
2. Class extends `BaseComponent` (or `BaseIterateComponent` for iterate components)
3. Implement `_process(self, input_data) -> Dict[str, Any]` returning `{'main': df}`
4. Add import to `src/v1/engine/components/{category}/__init__.py`
5. Add import to `src/v1/engine/engine.py` (top-level imports section)
6. Add entries to `ETLEngine.COMPONENT_REGISTRY` dict in `src/v1/engine/engine.py` (both V1 name and Talend `tName` alias)

**New Converter Component:**
1. Create `src/converters/talend_to_v1/components/{category}/{component_name}.py`
2. Class extends `ComponentConverter` from `..base`
3. Decorate with `@REGISTRY.register("tComponentName")`
4. Implement `convert(self, node, connections, context) -> ComponentResult`
5. Add import to `src/converters/talend_to_v1/components/{category}/__init__.py` (for auto-registration on import)
6. Create test at `tests/converters/talend_to_v1/components/{category}/test_{component_name}.py`

**New Infrastructure Service:**
- Add to `src/v1/engine/` as a new module
- Wire into `ETLEngine.__init__()` and component initialization

**New Python Routine:**
- Add `.py` file to `src/python_routines/`
- Auto-discovered by `PythonRoutineManager` -- no registration needed
- Accessible via `self.get_python_routines()` in engine components

**New Test:**
- Tests mirror `src/converters/` structure under `tests/converters/`
- File name: `test_{module_name}.py`
- Ensure `__init__.py` exists in each test directory

**New Exception Type:**
- Add to `src/v1/engine/exceptions.py`
- Extend `ETLError` base class

## Special Directories

**`src/router/`:**
- Purpose: JSON data files for a visual UI job designer (not code)
- Generated: Partially -- `scripts/add_connectors.py` adds connector metadata
- Committed: Yes

**`tests/talend_xml_samples/`:**
- Purpose: Test fixture data -- Talend XML inputs and expected JSON outputs
- Generated: Manually created from real Talend exports
- Committed: Yes

**`demos/`:**
- Purpose: Standalone HTML prototypes for UI concepts
- Generated: No
- Committed: Yes

**`src/v1/java_bridge/java/`:**
- Purpose: Java source and Maven project for Py4J server
- Generated: `target/` directory is generated by Maven build
- Committed: Source yes, `target/` excluded
- Build artifact: `java-bridge-with-dependencies.jar` expected at `target/java-bridge-with-dependencies.jar`

**`__pycache__/`:**
- Purpose: Python bytecode cache
- Generated: Yes (automatically by Python)
- Committed: No (in `.gitignore`)

---

*Structure analysis: 2026-04-14*
