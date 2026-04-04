"""Tests for UniteConverter (tUnite -> v1 Unite config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.unite import (
    UniteConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="un_1",
               component_type="tUnite"):
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
        assert REGISTRY.get("tUnite") is UniteConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = UniteConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = UniteConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = UniteConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = UniteConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for passthrough transform."""

    def test_schema_passthrough(self):
        """Transform passthrough: input schema == output schema."""
        node = _make_node(schema=_make_schema_columns())
        result = UniteConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]

    def test_schema_columns_populated(self):
        """Schema columns are populated when node has schema."""
        node = _make_node(schema=_make_schema_columns())
        result = UniteConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert len(schema["input"]) == 2
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][1]["name"] == "name"

    def test_empty_schema(self):
        """Empty schema produces empty input/output lists."""
        node = _make_node()
        result = UniteConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_empty_or_minimal(self):
        """needs_review should be empty -- engine defaults match Talend behavior."""
        node = _make_node()
        result = UniteConverter().convert(node, [], {})
        assert len(result.needs_review) == 0

    def test_no_warnings(self):
        """No warnings on default config."""
        node = _make_node()
        result = UniteConverter().convert(node, [], {})
        assert result.warnings == []


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Only 2 framework keys in config (no unique params)."""
        node = _make_node(schema=_make_schema_columns())
        result = UniteConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {"tstatcatcher_stats", "label"}
        assert set(cfg.keys()) == expected_keys


class TestComponentStructure:
    """Verify _build_component_dict output structure."""

    def test_has_type(self):
        node = _make_node()
        result = UniteConverter().convert(node, [], {})
        assert result.component["type"] == "Unite"

    def test_has_original_type(self):
        node = _make_node()
        result = UniteConverter().convert(node, [], {})
        assert result.component["original_type"] == "tUnite"

    def test_has_config(self):
        node = _make_node()
        result = UniteConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema(self):
        node = _make_node()
        result = UniteConverter().convert(node, [], {})
        assert "schema" in result.component

    def test_has_id(self):
        node = _make_node(component_id="un_1")
        result = UniteConverter().convert(node, [], {})
        assert result.component["id"] == "un_1"

    def test_has_position(self):
        node = _make_node()
        result = UniteConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_has_inputs_outputs(self):
        node = _make_node()
        result = UniteConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []
