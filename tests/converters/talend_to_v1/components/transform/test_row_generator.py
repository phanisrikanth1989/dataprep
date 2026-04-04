"""Tests for RowGeneratorConverter (tRowGenerator -> v1 RowGenerator config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.row_generator import (
    RowGeneratorConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="rg_1",
               component_type="tRowGenerator"):
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


def _make_values_data(rows):
    """Generate VALUES TABLE data with stride-2 (SCHEMA_COLUMN + ARRAY) per row.

    rows: list of tuples (schema_column, array_expr)
    """
    result = []
    for col_name, expr in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": col_name})
        result.append({"elementRef": "ARRAY", "value": expr})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tRowGenerator") is RowGeneratorConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_nb_rows_default(self):
        """NB_ROWS defaults to '100' (Talend XML default)."""
        node = _make_node()
        result = RowGeneratorConverter().convert(node, [], {})
        assert result.component["config"]["nb_rows"] == "100"

    def test_values_default_empty(self):
        """VALUES defaults to empty list when missing."""
        node = _make_node()
        result = RowGeneratorConverter().convert(node, [], {})
        assert result.component["config"]["values"] == []

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = RowGeneratorConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = RowGeneratorConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_nb_rows_custom(self):
        """NB_ROWS='"500"' -> "500"."""
        node = _make_node(params={"NB_ROWS": '"500"'})
        result = RowGeneratorConverter().convert(node, [], {})
        assert result.component["config"]["nb_rows"] == "500"

    def test_values_parsing(self):
        """VALUES TABLE with 2 entries -> [{schema_column, array}, ...]."""
        values_data = _make_values_data([
            ('"id"', '"sequence(1,1,1)"'),
            ('"name"', '"hello_world"'),
        ])
        node = _make_node(params={"VALUES": values_data})
        result = RowGeneratorConverter().convert(node, [], {})
        vals = result.component["config"]["values"]
        assert len(vals) == 2
        assert vals[0] == {"schema_column": "id", "array": "sequence(1,1,1)"}
        assert vals[1] == {"schema_column": "name", "array": "hello_world"}

    def test_values_single_entry(self):
        """VALUES TABLE with 1 entry -> single-element list."""
        values_data = _make_values_data([
            ('"col1"', '"constant_val"'),
        ])
        node = _make_node(params={"VALUES": values_data})
        result = RowGeneratorConverter().convert(node, [], {})
        vals = result.component["config"]["values"]
        assert len(vals) == 1
        assert vals[0] == {"schema_column": "col1", "array": "constant_val"}


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = RowGeneratorConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = RowGeneratorConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction -- SOURCE pattern (input=[], output=schema)."""

    def test_schema_source_pattern(self):
        """RowGenerator is a source: input==[], output has schema entries."""
        node = _make_node(schema=_make_schema_columns())
        result = RowGeneratorConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == []
        assert len(schema["output"]) == 2

    def test_schema_output_populated(self):
        """Output schema columns are correctly parsed from FLOW metadata."""
        node = _make_node(schema=_make_schema_columns())
        result = RowGeneratorConverter().convert(node, [], {})
        output = result.component["schema"]["output"]
        assert output[0]["name"] == "id"
        assert output[0]["key"] is True
        assert output[1]["name"] == "name"
        assert output[1]["length"] == 50

    def test_empty_schema_when_no_flow(self):
        """When no FLOW schema is present, output is empty list."""
        node = _make_node()
        result = RowGeneratorConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Per-feature needs_review for engine gaps."""
        node = _make_node()
        result = RowGeneratorConverter().convert(node, [], {})
        assert len(result.needs_review) > 0

    def test_needs_review_engine_gap_severity(self):
        """All entries have severity == 'engine_gap'."""
        node = _make_node()
        result = RowGeneratorConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = RowGeneratorConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = RowGeneratorConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """2 unique + 2 framework = 4 total config keys."""
        node = _make_node(schema=_make_schema_columns())
        result = RowGeneratorConverter().convert(node, [], {})
        expected_keys = {
            "nb_rows", "values",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"
        assert len(actual_keys) == 4, f"Expected 4 config keys (2 unique + 2 framework), got {len(actual_keys)}"


class TestComponentStructure:
    """Verify component wrapper structure."""

    def test_has_type(self):
        node = _make_node()
        result = RowGeneratorConverter().convert(node, [], {})
        assert result.component["type"] == "RowGenerator"

    def test_has_original_type(self):
        node = _make_node()
        result = RowGeneratorConverter().convert(node, [], {})
        assert result.component["original_type"] == "tRowGenerator"
