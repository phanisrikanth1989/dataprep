"""Tests for JavaComponentConverter (tJava -> v1 JavaComponent config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.java_component import (
    JavaComponentConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="java_1", component_type="tJava"):
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
        assert REGISTRY.get("tJava") is JavaComponentConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_java_code_default(self):
        """java_code defaults to empty string when CODE param is missing."""
        node = _make_node()
        result = JavaComponentConverter().convert(node, [], {})
        assert result.component["config"]["java_code"] == ""

    def test_imports_default(self):
        """imports defaults to empty string when IMPORT param is missing."""
        node = _make_node()
        result = JavaComponentConverter().convert(node, [], {})
        assert result.component["config"]["imports"] == ""

    def test_tstatcatcher_stats_default_false(self):
        """tstatcatcher_stats defaults to False."""
        node = _make_node()
        result = JavaComponentConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        """label defaults to empty string."""
        node = _make_node()
        result = JavaComponentConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_java_code_custom(self):
        """CODE with multiline Java code preserved as string."""
        code = 'System.out.println("hello");\nint x = 1;'
        node = _make_node(params={"CODE": code})
        result = JavaComponentConverter().convert(node, [], {})
        assert result.component["config"]["java_code"] == code

    def test_imports_custom(self):
        """IMPORT with custom import statements preserved."""
        imports = "import java.util.List;\nimport java.util.Map;"
        node = _make_node(params={"IMPORT": imports})
        result = JavaComponentConverter().convert(node, [], {})
        assert result.component["config"]["imports"] == imports


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        """tstatcatcher_stats is True when TSTATCATCHER_STATS='true'."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = JavaComponentConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        """label is extracted correctly when LABEL is set."""
        node = _make_node(params={"LABEL": '"java-step"'})
        result = JavaComponentConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "java-step"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_passthrough(self):
        """Schema input == output for transform component."""
        node = _make_node(schema=_make_schema_columns())
        result = JavaComponentConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][1]["name"] == "name"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """needs_review has per-feature entries for engine gaps."""
        node = _make_node()
        result = JavaComponentConverter().convert(node, [], {})
        assert len(result.needs_review) >= 1

    def test_needs_review_engine_gap_severity(self):
        """All needs_review entries have severity 'engine_gap'."""
        node = _make_node()
        result = JavaComponentConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """needs_review entries contain the correct component_id."""
        node = _make_node(component_id="test_comp")
        result = JavaComponentConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = JavaComponentConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_die_on_error_not_in_config(self):
        """DIE_ON_ERROR is phantom (not in _java.xml) -- must NOT appear in config."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = JavaComponentConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config has exactly 4 keys: 2 unique + 2 framework."""
        node = _make_node(schema=_make_schema_columns())
        result = JavaComponentConverter().convert(node, [], {})
        expected_keys = {
            "java_code", "imports",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        assert actual_keys == expected_keys, f"Expected {expected_keys}, got {actual_keys}"


class TestComponentStructure:
    """Verify the component dict structure from _build_component_dict."""

    def test_has_type(self):
        """Component type is 'JavaComponent'."""
        node = _make_node()
        result = JavaComponentConverter().convert(node, [], {})
        assert result.component["type"] == "JavaComponent"

    def test_has_original_type(self):
        """original_type is 'tJava'."""
        node = _make_node()
        result = JavaComponentConverter().convert(node, [], {})
        assert result.component["original_type"] == "tJava"

    def test_has_all_top_level_keys(self):
        """Output dict has all required top-level keys from _build_component_dict."""
        node = _make_node()
        result = JavaComponentConverter().convert(node, [], {})
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected_keys

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node()
        result = JavaComponentConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
