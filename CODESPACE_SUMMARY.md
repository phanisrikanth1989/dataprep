# DataPrep Codespace - Complete Understanding

**Last Updated:** 2026-06-13  
**Project:** Talend ETL Migration Engine (Python 3.12+ with Java 11+ bridge)  
**Stats:** 211 source files, 258 test files, 469 total Python files

---

## 🎯 Mission

Replace Talend Open Studio for 1200+ production jobs with a Python-based ETL execution engine that produces **identical results** for the same input data and job configuration.

---

## 🏗️ Architecture at a Glance

### Two-Layer Design

1. **Converter Layer** (`src/converters/talend_to_v1/`)
   - Transforms Talend `.item` XML job definitions → JSON configs
   - 80+ converter component classes (one per Talend component type)
   - Decorator-based auto-registry: `@REGISTRY.register("tComponentName")`
   - Clean, standardized, production-ready

2. **Engine Layer** (`src/v1/engine/`)
   - Executes JSON configs produced by converter
   - 50+ engine component classes with registry
   - DataFrame-centric data flow (pandas)
   - Python-Java bridge for executing Talend Java/Groovy expressions
   - **Status:** Partially working; systemic quality gaps that must be fixed before production

### Data Flow

```
Talend .item XML
    ↓
XML Parser (xml_parser.py)
    ↓
Component Converters (registry pattern)
    ↓
Expression Converter (Java→Python, Java markers)
    ↓
Trigger Mapper (OnComponentOk, OnSubjobOk, etc.)
    ↓
Validator (reference integrity, expression quality)
    ↓
JSON Job Config
    ↓ [Engine Phase]
    ↓
ETLEngine (execution loop, flow management)
    ↓
Engine Components (registry lookup)
    ↓
BaseComponent._process() (abstract, DataFrame in/out)
    ↓
GlobalMap (Talend-compatible stats: NB_LINE, NB_LINE_OK, NB_LINE_REJECT)
    ↓
Output Routes (by flow name: 'main', 'reject', etc.)
    ↓
Results (DataFrames + execution stats)
```

---

## 📁 Directory Structure

### Source Layout: `src/`

```
src/
├── converters/                    # Converter layer
│   ├── complex_converter/         # Legacy (read-only)
│   └── talend_to_v1/              # Main converter
│       ├── components/            # 80+ converters by category
│       │   ├── aggregate/         # AggregateRow, UniqueRow
│       │   ├── context/           # ContextLoad, etc.
│       │   ├── control/           # Die, Loop, Parallelize, PreJob, PostJob, RunJob
│       │   ├── database/          # DB input/output converters
│       │   ├── file/              # File input/output (delimited, Excel, XML, etc.)
│       │   ├── iterate/           # tFileList, tFlowToIterate, tForeach
│       │   └── transform/         # tMap, tFilter, tSort, etc.
│       ├── base.py                # ComponentConverter ABC
│       ├── registry.py            # @REGISTRY.register() decorator
│       ├── converter.py           # TalendToV1Converter (orchestrator)
│       ├── xml_parser.py          # XmlParser, TalendJob dataclass
│       ├── expression_converter.py# Java→Python, {{java}} markers
│       ├── trigger_mapper.py      # Flow triggers
│       ├── validator.py           # Post-conversion validation
│       └── type_mapping.py        # Talend→Pandas type mapping
│
├── v1/                            # Engine layer (v1 = versioned engine)
│   ├── engine/                    # Core engine
│   │   ├── components/            # ~50 engine components by category
│   │   │   ├── aggregate/         # AggregateRow, UniqueRow
│   │   │   ├── context/           # ContextLoad, etc.
│   │   │   ├── control/           # Die, Subjob, Loop, etc.
│   │   │   ├── database/          # DB input/output components
│   │   │   ├── file/              # File input/output (delimited, Excel, XML, etc.)
│   │   │   ├── iterate/           # FileList, FlowToIterate, Foreach
│   │   │   └── transform/         # Map (with subdir), Filter, Sort, Python routines, etc.
│   │   ├── base_component.py      # BaseComponent ABC (Template Method)
│   │   ├── base_iterate_component.py  # BaseIterateComponent (Iterator pattern)
│   │   ├── component_registry.py  # COMPONENT_REGISTRY dict
│   │   ├── engine.py              # ETLEngine (orchestrator, flow manager)
│   │   ├── executor.py            # Execution loop, component dispatch
│   │   ├── execution_plan.py      # Execution planning (DAG, subjob detection)
│   │   ├── context_manager.py     # ${context.var} resolution
│   │   ├── global_map.py          # Talend-compatible stats store
│   │   ├── java_bridge_manager.py # Py4J + Arrow bridge lifecycle
│   │   ├── python_routine_manager.py  # Python routine execution
│   │   ├── oracle_connection_manager.py # Oracle DB connection pooling
│   │   ├── output_router.py       # Route outputs to data_flows (main/reject/etc.)
│   │   ├── iterate_logging.py     # Iterator state tracking
│   │   ├── exceptions.py          # ETLError hierarchy
│   │   └── __init__.py            # Exports only ETLEngine
│   │
│   └── java_bridge/               # Python-Java bridge
│       ├── bridge.py              # JavaBridge client (Py4J + Arrow)
│       ├── __init__.py
│       └── java/                  # Java server (Groovy expressions + tMap)
│           ├── pom.xml            # Maven build config
│           ├── src/main/java/     # Java bridge server
│           │   ├── com/citi/gru/etl/JavaBridge.java
│           │   ├── com/citi/gru/etl/RowWrapper.java
│           │   └── routines/system/  # Talend system routines (TalendString, etc.)
│           ├── src/test/java/     # Java tests
│           └── target/            # Maven build output (JAR at target/*.jar)
│
├── python_routines/               # Python routine definitions
├── router/                        # UI registry (ui_registry.json, basic_ui_registry.json)
└── __init__.py
```

### Test Layout: `tests/`

```
tests/
├── converters/                    # Converter tests
│   └── talend_to_v1/
│       └── components/            # Component converter tests (mirrors src structure)
├── v1/                            # Engine tests
│   ├── engine/
│   │   ├── components/            # Component execution tests (mirrors src structure)
│   │   └── fixtures/              # Reusable test data
│   └── java_bridge/               # Java bridge tests (requires JVM)
├── fixtures/                      # Shared test fixtures
│   ├── data/                      # CSV, Excel, XML test data
│   ├── jobs/                      # JSON job configs for testing
│   │   ├── core/
│   │   ├── file/
│   │   ├── swift/
│   │   └── transform/
│   └── swift/                     # SWIFT-specific test fixtures
├── talend_xml_samples/            # Talend .item XML samples + converted JSONs
├── integration/                   # Full end-to-end integration tests
└── docs/                          # Documentation tests
```

---

## 🔧 Key Entry Points

### CLI: Converter

```bash
python -m src.converters.talend_to_v1.converter input.item [output.json]
```

**Code:** `src/converters/talend_to_v1/converter.py:460-472`

### CLI: Engine

```bash
python src/v1/engine/engine.py job.json [--context_param KEY=VALUE]
```

**Code:** `src/v1/engine/engine.py:860-889`

### Programmatic: Converter

```python
from src.converters.talend_to_v1.converter import TalendToV1Converter
converter = TalendToV1Converter()
json_config = converter.convert_file("job.item")
```

### Programmatic: Engine

```python
from src.v1.engine import ETLEngine
engine = ETLEngine(java_enabled=True)
result = engine.run_job("job.json")
```

---

## 📦 Component Organization Pattern

Both converter and engine follow **registry + ABC** discipline:

### Converter Pattern

```
src/converters/talend_to_v1/components/
├── base.py (ComponentConverter ABC)
├── registry.py (ConverterRegistry + @register decorator)
└── [category]/
    ├── __init__.py (imports all, no @register needed)
    └── component_name.py
        class TComponentName(ComponentConverter):
            @REGISTRY.register("tComponentName")
            def convert(self, node: TalendNode, ...) -> ComponentResult:
                ...
```

**Registry Lookup:** `REGISTRY.get("tFileInputDelimited")`

### Engine Pattern

```
src/v1/engine/components/
├── base_component.py (BaseComponent ABC)
├── component_registry.py (COMPONENT_REGISTRY dict)
└── [category]/
    ├── __init__.py (__all__ lists public components)
    └── component_name.py
        class FileInputDelimited(BaseComponent):
            def _process(self, input_data: Optional[pd.DataFrame]) -> Dict[str, Any]:
                return {"main": df, "stats": {...}}
```

**Registry Lookup:** `COMPONENT_REGISTRY.get("FileInputDelimited")` or `COMPONENT_REGISTRY.get("tFileInputDelimited")`

---

## 🔄 Core Abstractions

### BaseComponent (Engine)

**File:** `src/v1/engine/base_component.py`

```python
class BaseComponent(ABC):
    def execute(self, input_data: Optional[pd.DataFrame], context: Dict) -> Dict[str, Any]:
        # 1. Resolve {{java}} expressions via JavaBridgeManager
        # 2. Resolve ${context.var} via ContextManager
        # 3. Auto-select execution mode (batch/streaming/hybrid)
        # 4. Call abstract _process()
        # 5. Update global_map with stats
        
    @abstractmethod
    def _process(self, input_data: Optional[pd.DataFrame]) -> Dict[str, Any]:
        # Must return dict with 'main' key (DataFrame)
        # Optional 'reject' key, 'stats' dict
```

**Key Methods:**
- `_update_global_map()` — set NB_LINE, NB_LINE_OK, NB_LINE_REJECT
- `_update_stats()` — track component execution stats
- `validate_schema()` — verify input matches expected schema

### BaseIterateComponent (Engine)

**File:** `src/v1/engine/base_iterate_component.py`

Iterator pattern for components with loops (tFileList, tFlowToIterate, tForeach).

```python
class BaseIterateComponent(BaseComponent):
    def prepare_iterations(self) -> List[Dict]:  # abstract
    def has_next_iteration(self) -> bool:
    def get_next_iteration_context(self) -> Dict:
    def finalize_iterations(self) -> None:  # abstract
```

### ComponentConverter (Converter)

**File:** `src/converters/talend_to_v1/components/base.py`

Strategy pattern — one instance per Talend component type.

```python
class ComponentConverter(ABC):
    @abstractmethod
    def convert(self, node: TalendNode, connections: List[TalendConnection], context: Dict) -> ComponentResult:
        # Returns ComponentResult(component_dict, warnings, needs_review)
        
    # Helper methods:
    _get_str(node, "PARAM", "default")
    _get_bool(node, "PARAM", False)
    _parse_schema()
    _convert_date_pattern()
```

---

## 🌍 Global State & Context

### GlobalMap
**File:** `src/v1/engine/global_map.py`

Talend-compatible key-value store for inter-component variables and stats:
- `NB_LINE` — input row count
- `NB_LINE_OK` — successfully processed rows
- `NB_LINE_REJECT` — rejected rows

### ContextManager
**File:** `src/v1/engine/context_manager.py`

Resolves `${context.var}` and `context.var` patterns:
- File loading (JSON, YAML, properties)
- Type coercion
- Default value fallback

### TriggerManager
**File:** `src/v1/engine/execution_plan.py`

Orchestrates flow triggers:
- `OnComponentOk` — fire subjob if component succeeds
- `OnSubjobOk` — fire next subjob if previous succeeds
- `RunIf` — conditional execution

---

## ☕ Java Bridge Architecture

**Files:**
- Python client: `src/v1/java_bridge/bridge.py`
- Java server: `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java`
- Manager: `src/v1/engine/java_bridge_manager.py`

### Flow

1. **Startup:** `JavaBridgeManager.start()` spawns JVM subprocess, loads compiled JAR
2. **Sync Context:** Python context + globalMap → Java via `_sync_to_java()`
3. **Batch Execution:** Engine batches `{{java}}` expressions, sends to Java bridge
4. **Arrow Serialization:** Row data transferred as Apache Arrow binary
5. **Sync Back:** Java updates context/globalMap → Python via `_sync_from_java()`

### Key Classes
- `JavaBridge` — Py4J gateway
- `RowWrapper` — Arrow-backed row representation in Java
- `ExpressionConverter` — detects & marks `{{java}}` patterns

---

## 🧪 Testing Structure

### Test Markers (pytest)

- `@pytest.mark.unit` — Fast, no I/O
- `@pytest.mark.integration` — File I/O, full pipelines
- `@pytest.mark.java` — Requires JVM (included in gate)
- `@pytest.mark.oracle` — Requires Oracle testcontainer (opt-in, excluded from gate)
- `@pytest.mark.slow` — >5 seconds

### Coverage Gate

**Command:**
```bash
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

**Requirements:**
- **95% per-module line-coverage floor** (Phase 14 locked 2026-05-11)
- JVM 11+ on PATH for `-m java` tests
- Oracle tests opt-in via `-m oracle` (excluded from gate)
- Branch coverage disabled

---

## 📚 Dependencies

### Core (required)
- `pandas>=2.0,<4` — DataFrame processing
- `numpy>=1.24,<3` — Numerical ops

### Optional by Feature
- **java**: `pyarrow>=15.0,<24`, `py4j>=0.10.9,<0.11`
- **excel**: `openpyxl>=3.1,<4`, `xlrd>=2.0,<3`
- **oracle**: `oracledb>=2.5,<4`
- **xml**: `lxml>=4.9,<7`
- **yaml**: `PyYAML>=6.0,<7`
- **json**: `jsonpath-ng>=1.5,<2`
- **api**: `fastapi`, `uvicorn`, `python-multipart`
- **dev**: `pytest`, `pytest-cov`, `pytest-xdist`, `testcontainers`

### Build
- Maven 3.x (for Java bridge JAR)
- Python 3.12+

---

## 🚨 Error Handling Hierarchy

**Base:** `src/v1/engine/exceptions.py`

```
ETLError (root)
├── ConfigurationError (invalid job config)
├── DataValidationError (schema/type mismatch)
├── ComponentExecutionError (component failure, includes component_id)
├── FileOperationError (file I/O)
├── JavaBridgeError (Java bridge lifecycle/execution)
├── ExpressionError (expression evaluation)
└── SchemaError (type system)
```

**Engine Behavior:**
- `ComponentExecutionError` caught in `_execute_component()`
- Component marked failed, error recorded in `execution_stats`
- Execution continues (unless `die_on_error=True`)
- `Die` component can force termination with `exit_code`

---

## 💡 Converter Pipeline (12 Steps)

**File:** `src/converters/talend_to_v1/converter.py`

1. **Parse XML** → `TalendJob` dataclass
2. **Convert Components** → component dicts via registry
3. **Parse Flows** → detect connections between components
4. **Detect Subjobs** → group components by triggers
5. **Map Triggers** → OnComponentOk, OnSubjobOk, etc.
6. **Convert Expressions** → Java→Python, mark `{{java}}`
7. **Validate References** → check component existence
8. **Validate tMap Rules** → schema, expression quality
9. **Validate Expressions** → detect unsupported patterns
10. **Check Conversion Quality** → warnings + `needs_review` markers
11. **Validate Result** → run post-conversion validator
12. **Assemble JSON** → final job config dict

**Output:** `ComponentResult(component_dict, warnings: List[str], needs_review: bool)`

---

## 🎛️ Execution Modes

Engines can run in three modes (auto-selected or explicit):

1. **Batch** — entire input DataFrame processed at once
2. **Streaming** — row-by-row processing (memory-efficient)
3. **Hybrid** — batch processing + iterator for loops

---

## 🐛 Known Quality Gaps

Per CLAUDE.md:
- Converter side: **clean, standardized**
- Engine side: **partial, systemic gaps remain**
  - Missing features
  - Unreliable behavior
  - Quality issues must be fixed before production

---

## 📖 Key Conventions

### Naming

- **Python modules:** `snake_case.py` (e.g., `file_input_delimited.py`)
- **Classes:** `PascalCase` (e.g., `FileInputDelimited`)
- **Functions/methods:** `snake_case` (private: `_prefix`)
- **Constants:** `UPPER_SNAKE_CASE` (private: `_PREFIX`)
- **Enum members:** `UPPER_SNAKE_CASE` (e.g., `ExecutionMode.BATCH`)
- **Exceptions:** `*Error` suffix (e.g., `ETLError`, `ComponentExecutionError`)

### Code Style

- 4-space indent
- Lines under 120 chars (not enforced)
- Double quotes for strings
- Type hints from `typing` module
- Module-level loggers: `logger = logging.getLogger(__name__)`
- ASCII-only — no emojis/unicode in logs (RHEL servers)

### Imports

- Relative within packages: `from ..base_component import BaseComponent`
- Absolute in tests: `from src.v1.engine import ETLEngine`
- `TYPE_CHECKING` guard for circular imports

### Docstrings

- Converter modules: reStructuredText style (Parameters / Returns)
- Engine modules: Google style (Args: / Returns: / Raises:)
- Triple double-quotes: `"""..."""`
- All public methods + classes should have docstrings

---

## 📋 File Counts Summary

- **Source files:** 211 Python modules
- **Test files:** 258 Python modules
- **Total:** 469 Python files
- **Converter components:** ~80
- **Engine components:** ~50
- **Key entry points:** 2 (converter CLI, engine CLI)

---

## 🔗 Cross-References

| Topic | Files |
|-------|-------|
| Architecture overview | `docs/ARCHITECTURE.md` |
| Component reference | `docs/COMPONENT_REFERENCE.md` |
| Contributing rules | `docs/CONTRIBUTING.md` |
| Deployment guide | `docs/DEPLOYMENT.md` |
| Component patterns | `docs/v1/patterns/` |
| Phase 14 coverage | `.planning/phases/14-*/` |
| Java bridge test status | `tests/v1/java_bridge/` |

---

**This document is a living reference. Update when architecture changes, new patterns emerge, or significant refactoring occurs.**
