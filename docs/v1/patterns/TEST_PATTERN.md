# Gold Standard: Test Case Pattern

*Last updated: 2026-05-11*

> Reference: tests/converters/talend_to_v1/components/transform/test_schema_compliance_check.py (best example -- TABLE fixtures, comprehensive coverage)

Every converter test file MUST follow this structure and cover these categories.

---

## File Structure

```python
"""Tests for {ComponentName}Converter ({tComponentName} -> {EngineClassName})."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.{category}.{module} import (
    {ComponentName}Converter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="{abbrev}_1",
               component_type="{tComponentName}"):
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


# TABLE fixture helpers (only if component has TABLE params)
def _make_table_data(rows):
    """Generate TABLE data with stride-{N} per row.
    
    rows: list of tuples matching the TABLE fields
    """
    result = []
    for row_values in rows:
        for field_name, value in zip(("FIELD1", "FIELD2"), row_values):
            result.append({"elementRef": field_name, "value": value})
    return result


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("{tComponentName}") is {ComponentName}Converter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_{param1}_default(self):
        node = _make_node()
        result = {ComponentName}Converter().convert(node, [], {})
        assert result.component["{config_key}"] == {expected_default}

    def test_{param2}_default(self):
        # ... one test per parameter default


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_{param1}_extracted(self):
        node = _make_node(params={"{XML_PARAM}": "{value}"})
        result = {ComponentName}Converter().convert(node, [], {})
        assert result.component["{config_key}"] == {expected_value}

    def test_{param1}_alternative_value(self):
        # Test non-default values, edge cases


class TestTableParsing:
    """Verify TABLE parameter parsing (only if component has TABLEs)."""

    def test_table_parsed_correctly(self):
        table_data = _make_table_data([("val1", "val2")])
        node = _make_node(params={"{TABLE_NAME}": table_data})
        result = {ComponentName}Converter().convert(node, [], {})
        assert len(result.component["{table_key}"]) == 1
        assert result.component["{table_key}"][0]["field1"] == "val1"

    def test_table_empty_when_missing(self):
        node = _make_node()
        result = {ComponentName}Converter().convert(node, [], {})
        assert result.component["{table_key}"] == []

    def test_table_incomplete_stride_skipped(self):
        # Incomplete trailing group should be ignored


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = {ComponentName}Converter().convert(node, [], {})
        assert result.component["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = {ComponentName}Converter().convert(node, [], {})
        assert result.component["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = {ComponentName}Converter().convert(node, [], {})
        assert result.component["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = {ComponentName}Converter().convert(node, [], {})
        assert result.component["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_extracted(self):
        node = _make_node(schema=_make_schema_columns())
        result = {ComponentName}Converter().convert(node, [], {})
        assert "output_schema" in result.schema or result.schema == {}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        node = _make_node()
        result = {ComponentName}Converter().convert(node, [], {})
        assert len(result.needs_review) == {expected_count}

    def test_needs_review_severity(self):
        node = _make_node()
        result = {ComponentName}Converter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = {ComponentName}Converter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = {ComponentName}Converter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = {ComponentName}Converter().convert(node, [], {})
        expected_keys = {
            "{key1}", "{key2}", "{key3}",
            # ... all expected config keys
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component.keys())
        # Allow base keys (component_type, component_id, etc.)
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted (if applicable)."""

    def test_phantom_param_not_in_config(self):
        node = _make_node(params={"{PHANTOM_PARAM}": "true"})
        result = {ComponentName}Converter().convert(node, [], {})
        assert "{phantom_key}" not in result.component
```

---

## Rules

1. **One test class per concern** -- Registration, Defaults, Extraction, TABLE, Framework, Schema, NeedsReview, Completeness, PhantomParams
2. **`_make_node()` fixture** at module level -- always the same pattern with default params
3. **TABLE fixture helpers** for components with TABLE params -- `_make_table_data()` generates stride-correct data
4. **Every parameter gets at least 2 tests**: default value + extracted value
5. **Completeness test** asserts ALL expected config keys are present in output
6. **Phantom params test** asserts params NOT in _java.xml are NOT extracted (if component had phantom params removed)
7. **Framework param tests** always present -- tstatcatcher_stats and label
8. **NeedsReview tests** verify count, severity, component_id, and framework param exclusion
9. **No mocking** of the converter itself -- test the real `convert()` method
10. **Test class naming**: `Test{ComponentName}{Concern}` (e.g., `TestSleepConverterDefaults`)
11. **Fixtures use realistic data** -- SchemaColumn with proper types, TABLE data with proper stride
