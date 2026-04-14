# Technology Stack

**Analysis Date:** 2026-04-14

## Languages

**Primary:**
- Python 3.10+ - Core converter logic, ETL engine, all business logic (uses `set[str]` syntax requiring 3.10+)

**Secondary:**
- Java 11 - Java/Groovy bridge for executing Talend Java expressions (`src/v1/java_bridge/java/`)
- Groovy 3.0.21 - Dynamic expression evaluation within the Java bridge
- HTML/CSS/JS - UI design demos (`demos/`)

## Runtime

**Environment:**
- Python (CPython) - primary runtime for converter and engine
- JVM (Java 11+) - secondary runtime for Java bridge subprocess, started via `subprocess.Popen`

**Package Manager:**
- No `requirements.txt`, `pyproject.toml`, or `setup.py` detected. Dependencies are implicit.
- Maven (for Java bridge): `src/v1/java_bridge/java/pom.xml`
- No lockfile detected for Python dependencies

## Frameworks

**Core:**
- No web framework. This is a CLI/library-based ETL system.
- pandas (used heavily) - DataFrame-based data processing throughout the engine
- Apache Arrow (pyarrow) - High-performance data serialization for Python-Java bridge

**Testing:**
- pytest (inferred from `test_*.py` naming convention, `__init__.py` in test dirs)
- No `pytest.ini`, `setup.cfg`, or `pyproject.toml` test config detected

**Build/Dev:**
- Maven 3.x - Java bridge compilation (`src/v1/java_bridge/java/pom.xml`)
- No Python build system (setuptools, poetry, hatch, etc.)

## Key Dependencies

**Critical (Engine Runtime):**
- `pandas` - Core data processing framework. Every engine component inherits `BaseComponent` which uses `pd.DataFrame` as the data transport. Used in `src/v1/engine/base_component.py` and all component implementations.
- `pyarrow` (Apache Arrow) - Data serialization for Java bridge. Used in `src/v1/java_bridge/bridge.py` for efficient DataFrame transfer between Python and Java.
- `py4j` - Python-Java gateway communication. Used in `src/v1/java_bridge/bridge.py` to communicate with the JVM subprocess.

**Critical (Converter):**
- `xml.etree.ElementTree` (stdlib) - XML parsing for Talend `.item` files. Used in `src/converters/talend_to_v1/xml_parser.py`.
- `json` (stdlib) - JSON output serialization. Used in `src/converters/talend_to_v1/converter.py`.
- `re` (stdlib) - Expression conversion and pattern matching. Used in `src/converters/talend_to_v1/expression_converter.py`.

**Supporting (Engine Components):**
- `openpyxl` - Excel file reading/writing (.xlsx). Used in `src/v1/engine/components/file/file_input_excel.py` and `src/v1/engine/components/file/file_output_excel.py`.
- `xlrd` - Legacy Excel file reading (.xls). Used in `src/v1/engine/components/file/file_input_excel.py`.
- `lxml` - XML processing with XPath support. Used in `src/v1/engine/components/transform/extract_xml_fields.py` and `src/v1/engine/components/transform/xml_map.py`.
- `yaml` (PyYAML) - YAML config parsing for SWIFT transformer. Used in `src/v1/engine/components/transform/swift_transformer.py`, `src/v1/engine/components/transform/swift_block_formatter.py`, and `src/python_routines/swift_transformer.py`.
- `jsonpath_ng` - JSONPath expression evaluation. Used in `src/v1/engine/components/transform/extract_json_fields.py`.
- `numpy` - Numerical operations. Used in `src/v1/java_bridge/bridge.py` and `src/v1/engine/components/transform/python_dataframe_component.py`.

**Java Bridge Dependencies (Maven):**
- Apache Arrow `15.0.2` - Arrow vector/IPC for data transfer
- Groovy `3.0.21` - Dynamic script compilation and execution
- Py4J `0.10.9.7` - Gateway server for Python-Java communication

## Configuration

**Environment:**
- No `.env` files detected
- No environment variable configuration detected
- Context variables are passed via JSON job config files (not env vars)
- Java bridge port is dynamically allocated via `socket.bind(('', 0))` in `src/v1/engine/java_bridge_manager.py`

**Build:**
- `src/v1/java_bridge/java/pom.xml` - Maven POM for Java bridge JAR
- Java bridge artifact: `target/java-bridge-with-dependencies.jar`
- No Python build configuration files

**UI Registry:**
- `src/router/ui_registry.json` - Component metadata registry defining UI properties, connectors, and settings for each Talend component type
- `src/router/basic_ui_registry.json` - Simplified version of the UI registry

## Platform Requirements

**Development:**
- Python 3.10+ (uses `set[str]` type hint syntax without `from __future__ import annotations` in some modules)
- Java 11+ (for Java bridge, specified in `pom.xml` as `maven.compiler.source=11`)
- Maven 3.x (to build Java bridge JAR)

**Production:**
- Python 3.10+ with pandas, pyarrow, py4j, openpyxl, xlrd, lxml, pyyaml, jsonpath-ng, numpy
- JVM 11+ (only when `java_config.enabled=true` in job config)
- Compiled Java bridge JAR at `src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar`

**CLI Entry Points:**
- Converter: `python -m src.converters.talend_to_v1.converter <input.item> [output.json]` (see `src/converters/talend_to_v1/converter.py:460-472`)
- Engine: `python src/v1/engine/engine.py <job_config.json> [--context_param KEY=VALUE]` (see `src/v1/engine/engine.py:860-889`)

---

*Stack analysis: 2026-04-14*
