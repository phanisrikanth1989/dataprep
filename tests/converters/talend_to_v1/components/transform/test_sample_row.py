"""Tests for SampleRowConverter (tSampleRow -> v1 tSampleRow config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.sample_row import (
    SampleRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="sr_1",
               component_type="tSampleRow"):
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
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tSampleRow") is SampleRowConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_range_default(self):
        """RANGE default is '1,5,10..20' per _java.xml DEFAULT element."""
        node = _make_node()
        result = SampleRowConverter().convert(node, [], {})
        assert result.component["config"]["range"] == "1,5,10..20"

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = SampleRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = SampleRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_range_custom(self):
        """RANGE='"1..100"' -> '1..100'."""
        node = _make_node(params={"RANGE": '"1..100"'})
        result = SampleRowConverter().convert(node, [], {})
        assert result.component["config"]["range"] == "1..100"

    def test_range_single_value(self):
        """RANGE='"5"' -> '5'."""
        node = _make_node(params={"RANGE": '"5"'})
        result = SampleRowConverter().convert(node, [], {})
        assert result.component["config"]["range"] == "5"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = SampleRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = SampleRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction (passthrough: input == output)."""

    def test_schema_passthrough(self):
        """tSampleRow is passthrough: input schema == output schema."""
        node = _make_node(schema=_make_schema_columns())
        result = SampleRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]

    def test_schema_columns_populated(self):
        """Schema columns are extracted from FLOW schema."""
        node = _make_node(schema=_make_schema_columns())
        result = SampleRowConverter().convert(node, [], {})
        cols = result.component["schema"]["input"]
        assert len(cols) == 2
        assert cols[0]["name"] == "id"
        assert cols[1]["name"] == "name"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review per D-27 (no engine)."""
        node = _make_node()
        result = SampleRowConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_engine_gap(self):
        node = _make_node()
        result = SampleRowConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_no_engine(self):
        node = _make_node()
        result = SampleRowConverter().convert(node, [], {})
        assert "No v1 engine implementation" in result.needs_review[0]["issue"]

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = SampleRowConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = SampleRowConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_connection_format_not_in_config(self):
        """CONNECTION_FORMAT is phantom -- NOT in _java.xml, must not appear in config."""
        node = _make_node(params={"CONNECTION_FORMAT": '"row"'})
        result = SampleRowConverter().convert(node, [], {})
        assert "connection_format" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config should have range + 2 framework keys."""
        node = _make_node(schema=_make_schema_columns())
        result = SampleRowConverter().convert(node, [], {})
        expected_keys = {"range", "tstatcatcher_stats", "label"}
        actual_config_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_config_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify component wrapper structure."""

    def test_has_type(self):
        """No-engine: type_name='tSampleRow' per D-43."""
        node = _make_node()
        result = SampleRowConverter().convert(node, [], {})
        assert result.component["type"] == "tSampleRow"

    def test_has_original_type(self):
        node = _make_node()
        result = SampleRowConverter().convert(node, [], {})
        assert result.component["original_type"] == "tSampleRow"
