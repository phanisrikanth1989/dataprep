"""Tests for JavaRowComponentConverter (tJavaRow -> v1 JavaRowComponent config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.java_row_component import (
    JavaRowComponentConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="jrow_1",
               component_type="tJavaRow"):
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
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tJavaRow") is JavaRowComponentConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_java_code_default(self):
        node = _make_node()
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["java_code"] == ""

    def test_imports_default(self):
        node = _make_node()
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["imports"] == ""

    def test_output_schema_default_empty(self):
        """No schema columns -> output_schema is empty list."""
        node = _make_node()
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["output_schema"] == []

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_java_code_custom(self):
        """CODE with multiline Java code preserved."""
        code = "output_row.name = input_row.name;\noutput_row.age = input_row.age + 1;"
        node = _make_node(params={"CODE": code})
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["java_code"] == code

    def test_imports_custom(self):
        """IMPORT with custom import statements."""
        imports = "import java.util.Date;\nimport java.util.List;"
        node = _make_node(params={"IMPORT": imports})
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["imports"] == imports

    def test_output_schema_with_columns(self):
        """Schema columns produce output_schema list of dicts."""
        schema = _make_schema_columns()
        node = _make_node(params={}, schema=schema)
        result = JavaRowComponentConverter().convert(node, [], {})
        output_schema = result.component["config"]["output_schema"]
        assert isinstance(output_schema, list)
        assert len(output_schema) == 2
        # Each entry should be a dict with name and type
        names = [col["name"] for col in output_schema]
        assert "id" in names
        assert "name" in names


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_passthrough(self):
        """input schema == output schema for transform component."""
        schema = _make_schema_columns()
        node = _make_node(schema=schema)
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == result.component["schema"]["output"]
        assert len(result.component["schema"]["output"]) == 2


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Per-feature needs_review for engine gaps."""
        node = _make_node()
        result = JavaRowComponentConverter().convert(node, [], {})
        assert len(result.needs_review) >= 2

    def test_needs_review_engine_gap_severity(self):
        """All needs_review entries have severity engine_gap."""
        node = _make_node()
        result = JavaRowComponentConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = JavaRowComponentConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = JavaRowComponentConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_die_on_error_not_in_config(self):
        """DIE_ON_ERROR is phantom (not in _java.xml) -- must NOT be in config."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = JavaRowComponentConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config has exactly 5 keys: java_code, imports, output_schema + 2 framework."""
        schema = _make_schema_columns()
        node = _make_node(schema=schema)
        result = JavaRowComponentConverter().convert(node, [], {})
        expected_keys = {
            "java_code", "imports", "output_schema",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys
        assert not missing, f"Missing config keys: {missing}"
        assert not extra, f"Extra config keys: {extra}"


class TestComponentStructure:
    """Verify component dict structure."""

    def test_has_type(self):
        node = _make_node()
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["type"] == "JavaRowComponent"

    def test_has_original_type(self):
        node = _make_node()
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["original_type"] == "tJavaRow"

    def test_result_type(self):
        node = _make_node()
        result = JavaRowComponentConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_component_dict_keys(self):
        """Output dict has all required top-level keys."""
        node = _make_node()
        result = JavaRowComponentConverter().convert(node, [], {})
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected_keys
