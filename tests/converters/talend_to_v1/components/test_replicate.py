"""Tests for the ReplicateConverter (tReplicate -> Replicate)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.replicate import (
    ReplicateConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="replicate_1",
               component_type="tReplicate"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
        raw_xml=ET.Element("node"),
    )


def _sample_schema():
    """Return a FLOW schema with two columns for reuse across tests."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="name", type="id_String", nullable=True),
        ]
    }


# --------------------------------------------------------------------- #
#  Registration
# --------------------------------------------------------------------- #

class TestReplicateConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tReplicate") is ReplicateConverter


# --------------------------------------------------------------------- #
#  Basic conversion
# --------------------------------------------------------------------- #

class TestReplicateConverterBasic:
    def test_basic_conversion_with_defaults(self):
        node = _make_node(schema=_sample_schema())
        result = ReplicateConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "replicate_1"
        assert comp["type"] == "Replicate"
        assert comp["original_type"] == "tReplicate"
        assert comp["position"] == {"x": 320, "y": 160}
        assert comp["config"]["tstatcatcher_stats"] is False
        assert comp["config"]["label"] == ""
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_params_extracted(self):
        node = _make_node(
            params={
                "TSTATCATCHER_STATS": "true",
                "LABEL": '"replicate-step"',
            },
            schema=_sample_schema(),
        )
        result = ReplicateConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["tstatcatcher_stats"] is True
        assert cfg["label"] == "replicate-step"

    def test_no_warnings_on_valid_input(self):
        node = _make_node(schema=_sample_schema())
        result = ReplicateConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []


# --------------------------------------------------------------------- #
#  Schema handling
# --------------------------------------------------------------------- #

class TestReplicateConverterSchema:
    def test_schema_input_equals_output(self):
        """Replicate is a passthrough: input schema == output schema."""
        node = _make_node(schema=_sample_schema())
        result = ReplicateConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 2

    def test_schema_column_details(self):
        node = _make_node(schema=_sample_schema())
        result = ReplicateConverter().convert(node, [], {})

        cols = result.component["schema"]["input"]
        id_col = cols[0]
        name_col = cols[1]

        assert id_col["name"] == "id"
        assert id_col["nullable"] is False
        assert id_col["key"] is True

        assert name_col["name"] == "name"
        assert name_col["nullable"] is True
        assert name_col["key"] is False

    def test_empty_schema(self):
        node = _make_node(schema={})
        result = ReplicateConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}


# --------------------------------------------------------------------- #
#  Completeness
# --------------------------------------------------------------------- #

class TestCompleteness:
    def test_all_2_config_keys_present(self):
        node = _make_node(params={})
        result = ReplicateConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {"tstatcatcher_stats", "label"}
        assert set(cfg.keys()) == expected_keys

    def test_phantom_param_connection_format_removed(self):
        """connection_format is not a real Talend tReplicate param."""
        node = _make_node(params={})
        result = ReplicateConverter().convert(node, [], {})
        assert "connection_format" not in result.component["config"]
