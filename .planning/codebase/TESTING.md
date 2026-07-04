# Testing Patterns

**Analysis Date:** 2026-04-14

## Test Framework

**Runner:**
- pytest (no version pinned -- no `requirements.txt` or `pyproject.toml` with deps)
- Config: No `pytest.ini`, `conftest.py`, or `pyproject.toml` [tool.pytest] section detected

**Assertion Library:**
- Plain `assert` statements (pytest native)
- `pytest.raises` for exception testing
- `pytest.mark.parametrize` for parameterized tests
- `pytest.fail()` for custom failure messages

**Run Commands:**
```bash
pytest                                    # Run all tests
pytest tests/converters/talend_to_v1/     # Run converter tests
pytest tests/converters/talend_to_v1/components/transform/test_filter_rows.py  # Single file
pytest -v                                 # Verbose output
pytest -k "TestFlowParsing"               # Run by class/test name
```

## Test File Organization

**Location:**
- Separate `tests/` directory mirroring `src/` structure
- `tests/converters/talend_to_v1/` mirrors `src/converters/talend_to_v1/`
- `tests/converters/talend_to_v1/components/transform/` mirrors `src/converters/talend_to_v1/components/transform/`
- Every `tests/` directory has an `__init__.py` file

**Naming:**
- Test files: `test_{module_name}.py` (e.g., `test_converter.py`, `test_filter_rows.py`, `test_xml_parser.py`)
- Test classes: `Test{Feature}` (e.g., `TestDefaults`, `TestParameterExtraction`, `TestSchema`)
- Test methods: `test_{specific_behavior}` (e.g., `test_logical_op_default_and`, `test_host_extracted`)

**Structure:**
```
tests/
├── __init__.py
├── converters/
│   ├── __init__.py
│   └── talend_to_v1/
│       ├── __init__.py
│       ├── test_base.py                    # Tests for ComponentConverter base class
│       ├── test_converter.py               # Tests for TalendToV1Converter orchestrator
│       ├── test_integration.py             # End-to-end integration tests
│       ├── test_registry.py                # Tests for ConverterRegistry
│       ├── test_trigger_mapper.py          # Tests for trigger mapping
│       ├── test_type_mapping.py            # Tests for type mapping
│       ├── test_validator.py               # Tests for validator
│       ├── test_xml_parser.py              # Tests for XML parser
│       ├── batch_convert.py                # Batch conversion utility (not a test)
│       └── components/
│           ├── __init__.py
│           ├── aggregate/
│           │   ├── test_aggregate_row.py
│           │   └── test_unique_row.py
│           ├── context/
│           │   └── test_context_load.py
│           ├── control/
│           │   ├── test_die.py
│           │   ├── test_loop.py
│           │   ├── test_parallelize.py
│           │   ├── test_postjob.py
│           │   ├── test_prejob.py
│           │   ├── test_run_job.py
│           │   ├── test_send_mail.py
│           │   ├── test_sleep.py
│           │   └── test_warn.py
│           ├── database/
│           │   ├── test_mssql_connection.py
│           │   ├── test_mssql_input.py
│           │   ├── test_oracle_bulk_exec.py
│           │   ├── test_oracle_close.py
│           │   ├── test_oracle_commit.py
│           │   ├── test_oracle_connection.py
│           │   ├── test_oracle_input.py
│           │   ├── test_oracle_output.py
│           │   ├── test_oracle_rollback.py
│           │   ├── test_oracle_row.py
│           │   └── test_oracle_sp.py
│           ├── file/
│           │   ├── test_file_archive.py ... test_set_global_var.py (22 files)
│           ├── iterate/
│           │   ├── test_flow_to_iterate.py
│           │   └── test_foreach.py
│           └── transform/
│               ├── test_aggregate_sorted_row.py ... test_xml_map.py (31 files)
├── talend_xml_samples/
│   └── converted_jsons/
│       └── *.json                          # Expected output JSON files for validation
```

**Test Coverage by Area:**
- ~93 test files total
- Converter component tests: ~75 files (one per component converter)
- Core module tests: ~8 files (converter, parser, registry, triggers, types, validator, base, integration)
- Engine component tests: 0 files (NO engine tests exist)
- Integration tests: 1 file (`test_integration.py`)

## Test Structure

**Suite Organization (converter component tests):**

Each converter component test file follows a strict, repeatable structure:

```python
"""Tests for {ConverterName} ({talend_type} -> v1 {engine_type} config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult, SchemaColumn, TalendConnection, TalendNode,
)
from src.converters.talend_to_v1.components.{category}.{module} import {ConverterClass}
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="default_id",
               component_type="tComponentName"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )

def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
        ]
    }


# ------------------------------------------------------------------
# Test Classes (standard sections)
# ------------------------------------------------------------------

class TestRegistration:
    """Verify component is registered correctly."""
    def test_registered_as_xxx(self):
        assert REGISTRY.get("tXxx") is XxxConverter

class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""
    def test_param_name_default_value(self):
        node = _make_node()
        result = XxxConverter().convert(node, [], {})
        assert result.component["config"]["param_name"] == expected_default

class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""
    def test_param_extracted(self):
        node = _make_node(params={"TALEND_PARAM": '"value"'})
        result = XxxConverter().convert(node, [], {})
        assert result.component["config"]["v1_param"] == "value"

class TestSchema:
    """Verify schema extraction."""

class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

class TestCompleteness:
    """Verify all expected config keys are present."""

class TestComponentStructure:
    """Verify component dict structure."""
```

**Core module tests (orchestrator, parser, etc.):**

```python
"""Tests for talend_to_v1.converter -- TalendToV1Converter orchestrator."""

# Helpers (module-level functions)
def _make_node(...): ...
def _make_connection(...): ...
def _make_job(...): ...
def _write_item(xml_text: str) -> str: ...

# Test classes grouped by feature
class TestUnsupportedFallback: ...
class TestFlowParsing: ...
class TestComponentConnectionsUpdate: ...
class TestSubjobDetection: ...
class TestJavaDetectionByType: ...
class TestFullPipeline: ...
```

**Patterns:**
- Each test class focuses on one aspect (registration, defaults, extraction, schema, review, completeness, structure)
- Helper functions (`_make_node`, `_make_schema_columns`) defined at module level, not as fixtures
- No `setUp`/`tearDown` -- pytest style with plain test methods
- Tests for temp files use `try/finally` with `os.unlink()` for cleanup

## Mocking

**Framework:** `unittest.mock` (`patch`, `MagicMock`)

**Patterns:**

```python
from unittest.mock import patch, MagicMock

# Pattern 1: Patch object methods
with patch.object(converter, "_parser") as mock_parser:
    mock_parser.parse.return_value = job
    config = converter.convert_file("dummy.item")

# Pattern 2: Patch registry lookup
with patch.object(REGISTRY, "get", return_value=_BrokenConverter):
    config = converter.convert_file("dummy.item")

# Pattern 3: Multiple patches via context managers
with patch.object(converter, "_parser") as mock_parser, \
     patch.object(REGISTRY, "get", return_value=_BrokenConverter):
    mock_parser.parse.return_value = job
    config = converter.convert_file("dummy.item")
```

**What to Mock:**
- XML parser when testing converter orchestration logic
- Registry lookups when testing error handling paths
- File system (via temp files, not mocks) for XML parsing tests

**What NOT to Mock:**
- Component converter `convert()` methods -- test them directly
- Dataclass constructors (`TalendNode`, `TalendConnection`) -- construct real instances
- Registry registration -- test with real `ConverterRegistry` instances

## Fixtures and Factories

**Test Data:**

Factory functions at module level (NOT pytest fixtures):

```python
# Standard node factory
def _make_node(params=None, schema=None, component_id="test_1",
               component_type="tTest"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 0, "y": 0},
        raw_xml=ET.Element("node"),
    )

# Standard schema factory
def _make_schema_columns():
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
        ]
    }

# Connection factory
def _make_connection(name, source, target, connector_type="FLOW", condition=None):
    return TalendConnection(name=name, source=source, target=target,
                            connector_type=connector_type, condition=condition)

# Job factory
def _make_job(job_name="TestJob", nodes=None, connections=None, ...):
    return TalendJob(job_name=job_name, ...)

# XML temp file writer
def _write_item(xml_text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".item")
    os.write(fd, textwrap.dedent(xml_text).encode("utf-8"))
    os.close(fd)
    return path
```

**pytest Fixtures (used sparingly):**

```python
# Integration test fixtures
@pytest.fixture
def new_converter():
    return TalendToV1Converter()

# Caching fixture for expensive operations
_CONVERTED_CACHE: Dict[str, Dict[str, Any]] = {}

def _convert_cached(path: Path) -> Dict[str, Any]:
    key = str(path)
    if key not in _CONVERTED_CACHE:
        _CONVERTED_CACHE[key] = TalendToV1Converter().convert_file(key)
    return _CONVERTED_CACHE[key]
```

**Location:**
- Factory functions defined in each test file (duplicated pattern, not shared)
- No shared `conftest.py` files exist
- Test data XML samples in `tests/talend_xml_samples/`
- Expected JSON outputs in `tests/talend_xml_samples/converted_jsons/`

## Coverage

**Requirements:** None enforced. No coverage tooling configured.

**View Coverage:**
```bash
pytest --cov=src --cov-report=html    # If pytest-cov is installed
```

## Test Types

**Unit Tests:**
- Comprise the bulk of tests (~90+ files)
- Test individual converter components in isolation
- Each test creates a `TalendNode` with specific params and asserts on the converted output
- No external dependencies (no DB, no filesystem reads beyond temp files)
- Tests verify: defaults, parameter extraction, schema parsing, registration, structure completeness

**Integration Tests:**
- `tests/converters/talend_to_v1/test_integration.py` -- end-to-end conversion of real `.item` XML files
- Tests against sample `.item` files in `sample_jobs/` directory
- Verifies: smoke conversion, component coverage (no unsupported), validation passes, structural checks
- Includes backwards compatibility tests comparing new converter output with old `ComplexTalendConverter`
- Uses `@pytest.mark.parametrize` over all `.item` files for parameterized smoke testing

**E2E Tests:**
- Not present. No tests exist for the engine execution (`src/v1/engine/`) module.

## Common Patterns

**Parameterized Testing:**
```python
@pytest.mark.parametrize("java_type", [
    "tJavaRow", "tJava", "JavaRowComponent",
    "JavaComponent", "JavaRow", "Java",
])
def test_java_component_type_detected(self, java_type: str):
    components = [{"id": "comp1", "type": java_type, "config": {}}]
    assert TalendToV1Converter._detect_java_requirement(components) is True

# Parametrize over all sample files
@pytest.mark.parametrize("item_path", _ITEM_FILES, ids=lambda p: p.name)
def test_converts_without_error(self, item_path):
    result = _convert_cached(item_path)
    assert isinstance(result, dict)
```

**Default Value Testing:**
```python
class TestDefaults:
    def test_logical_op_default_and(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["logical_op"] == "AND"

    def test_conditions_default_empty(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["conditions"] == []
```

**Completeness Testing:**
```python
class TestCompleteness:
    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = XxxConverter().convert(node, [], {})
        expected_keys = {"param_a", "param_b", "tstatcatcher_stats", "label"}
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"
```

**Error Testing:**
```python
def test_duplicate_raises():
    reg = ConverterRegistry()
    @reg.register("tFoo")
    class First: pass

    with pytest.raises(ValueError):
        @reg.register("tFoo")
        class Second: pass
```

**Temp File Cleanup:**
```python
def test_convert_job_returns_config(self):
    xml = _job_xml('<node ...>...</node>')
    path = _write_item(xml)
    try:
        config = convert_job(path)
        assert config["job_name"] is not None
    finally:
        os.unlink(path)
```

**Autouse Fixture for Class State:**
```python
class TestComplexTMapStructure:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.result = _convert_cached(_COMPLEX_TMAP)

    def test_has_components(self):
        assert len(self.result["components"]) > 0
```

## Conventions for Writing New Tests

**For a new converter component:**
1. Create `tests/converters/talend_to_v1/components/{category}/test_{component}.py`
2. Add `__init__.py` to the directory if missing
3. Define `_make_node()` and `_make_schema_columns()` factory functions
4. Include these test classes in order:
   - `TestRegistration` -- verify `REGISTRY.get("tXxx")` returns the converter class
   - `TestDefaults` -- one test per config parameter with default node
   - `TestParameterExtraction` -- one test per parameter showing extraction from params dict
   - `TestSchema` -- verify input/output schema extraction (source vs transform vs sink pattern)
   - `TestNeedsReview` -- verify engine gap entries have correct severity and component ID
   - `TestCompleteness` -- verify all expected config keys are present
   - `TestComponentStructure` -- verify top-level dict keys and `ComponentResult` type

**For a new engine component:**
- No existing pattern. Engine has zero tests. When creating, test the `_process()` method with pandas DataFrames.

---

*Testing analysis: 2026-04-14*
