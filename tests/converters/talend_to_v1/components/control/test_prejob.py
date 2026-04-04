"""Tests for PrejobConverter (tPrejob -> v1 prejob config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.prejob import PrejobConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="prejob_1",
               component_type="tPrejob"):
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
        assert REGISTRY.get("tPrejob") is PrejobConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = PrejobConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = PrejobConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = PrejobConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = PrejobConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = PrejobConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = PrejobConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = PrejobConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = PrejobConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_is_empty_control_pattern(self):
        """Control component has empty input/output schema (no data flow)."""
        node = _make_node()
        result = PrejobConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}

    def test_standard_structure_keys(self):
        """Component dict has standard top-level keys from _build_component_dict."""
        node = _make_node(component_id="prejob_1")
        result = PrejobConverter().convert(node, [], {})
        assert result.component["id"] == "prejob_1"
        assert result.component["type"] == "tPrejob"
        assert result.component["original_type"] == "tPrejob"
        assert result.component["position"] == {"x": 100, "y": 200}
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated entry per D-23."""
        node = _make_node()
        result = PrejobConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_is_engine_gap(self):
        node = _make_node()
        result = PrejobConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_message(self):
        node = _make_node()
        result = PrejobConverter().convert(node, [], {})
        assert "No concrete engine implementation for tPrejob" in result.needs_review[0]["issue"]

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = PrejobConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = PrejobConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = PrejobConverter().convert(node, [], {})
        expected_keys = {
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestPhantomParams:
    """No phantom params for tPrejob -- verify unknown params are ignored."""

    def test_unknown_params_ignored(self):
        """Extra params should not appear in the output config."""
        node = _make_node(params={"UNKNOWN_PARAM": "some_value", "ANOTHER": "42"})
        result = PrejobConverter().convert(node, [], {})
        assert "unknown_param" not in result.component["config"]
        assert "another" not in result.component["config"]
