"""Tests for ConvertTypeConverter (tConvertType -> v1 tConvertType config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.convert_type import (
    ConvertTypeConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="ct_1",
               component_type="tConvertType"):
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


def _make_manualtable(rows):
    """Generate MANUALTABLE data with stride-2 per row.

    rows: list of tuples (input_column, output_column)
    """
    result = []
    for input_col, output_col in rows:
        result.append({"elementRef": "INPUT_COLUMN", "value": input_col})
        result.append({"elementRef": "OUTPUT_COLUMN", "value": output_col})
    return result


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tConvertType") is ConvertTypeConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_autocast_default_false(self):
        node = _make_node()
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["autocast"] is False

    def test_manualtable_default_empty(self):
        node = _make_node()
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["manualtable"] == []

    def test_emptytonull_default_false(self):
        node = _make_node()
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["emptytonull"] is False

    def test_dieonerror_default_false(self):
        node = _make_node()
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["dieonerror"] is False

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestManualTableParsing:
    """Verify MANUALTABLE TABLE parameter parsing."""

    def test_manualtable_single(self):
        """Single stride-2 group -> {input_column, output_column}."""
        table_data = _make_manualtable([("age", "Integer")])
        node = _make_node(params={"MANUALTABLE": table_data})
        result = ConvertTypeConverter().convert(node, [], {})
        mt = result.component["config"]["manualtable"]
        assert len(mt) == 1
        assert mt[0] == {"input_column": "age", "output_column": "Integer"}

    def test_manualtable_multiple(self):
        """4 elements -> 2 mapping dicts."""
        table_data = _make_manualtable([("age", "Integer"), ("salary", "Double")])
        node = _make_node(params={"MANUALTABLE": table_data})
        result = ConvertTypeConverter().convert(node, [], {})
        mt = result.component["config"]["manualtable"]
        assert len(mt) == 2
        assert mt[0] == {"input_column": "age", "output_column": "Integer"}
        assert mt[1] == {"input_column": "salary", "output_column": "Double"}

    def test_manualtable_empty(self):
        """Empty raw -> []."""
        node = _make_node(params={"MANUALTABLE": []})
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["manualtable"] == []


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_autocast_true(self):
        node = _make_node(params={"AUTOCAST": "true"})
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["autocast"] is True

    def test_emptytonull_true(self):
        node = _make_node(params={"EMPTYTONULL": "true"})
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["emptytonull"] is True

    def test_dieonerror_true(self):
        node = _make_node(params={"DIEONERROR": "true"})
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["dieonerror"] is True


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_passthrough(self):
        """ConvertType passes through schema: input == output."""
        node = _make_node(schema=_make_schema_columns())
        result = ConvertTypeConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][1]["name"] == "name"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review per D-27."""
        node = _make_node()
        result = ConvertTypeConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_no_engine(self):
        """needs_review mentions no engine implementation."""
        node = _make_node()
        result = ConvertTypeConverter().convert(node, [], {})
        assert "No v1 engine implementation" in result.needs_review[0]["issue"]

    def test_needs_review_severity(self):
        node = _make_node()
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = ConvertTypeConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = ConvertTypeConverter().convert(node, [], {})
        expected_keys = {
            "autocast", "manualtable", "emptytonull", "dieonerror",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify component dict structure."""

    def test_has_type(self):
        """type_name is tConvertType (no-engine)."""
        node = _make_node()
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["type"] == "tConvertType"

    def test_has_original_type(self):
        node = _make_node()
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["original_type"] == "tConvertType"
