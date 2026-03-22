"""Tests for the SwiftTransformerConverter (tSwiftDataTransformer -> SwiftTransformer)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.swift_transformer import (
    SwiftTransformerConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="swift_transformer_1",
               component_type="tSwiftDataTransformer"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 400, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _sample_schema():
    """Return a FLOW schema with typical SWIFT columns for reuse across tests."""
    return {
        "FLOW": [
            SchemaColumn(name="message_type", type="id_String", nullable=False, key=True),
            SchemaColumn(name="sender_bic", type="id_String", nullable=True),
            SchemaColumn(name="receiver_bic", type="id_String", nullable=True),
            SchemaColumn(name="transaction_ref", type="id_String", nullable=True),
        ]
    }


# --------------------------------------------------------------------- #
#  Registration
# --------------------------------------------------------------------- #

class TestSwiftTransformerConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tSwiftDataTransformer") is SwiftTransformerConverter


# --------------------------------------------------------------------- #
#  Type name correctness (CONV-NAME-004 / CONV-ST-001)
# --------------------------------------------------------------------- #

class TestSwiftTransformerTypeName:
    def test_type_is_swift_transformer_not_old_name(self):
        """The v1 engine type MUST be 'SwiftTransformer', not
        the old incorrect 'TSwiftDataTransformer'."""
        node = _make_node(schema=_sample_schema())
        result = SwiftTransformerConverter().convert(node, [], {})

        assert result.component["type"] == "SwiftTransformer"
        assert result.component["type"] != "TSwiftDataTransformer"


# --------------------------------------------------------------------- #
#  Basic conversion
# --------------------------------------------------------------------- #

class TestSwiftTransformerConverterBasic:
    def test_basic_conversion_with_defaults(self):
        node = _make_node(schema=_sample_schema())
        result = SwiftTransformerConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "swift_transformer_1"
        assert comp["type"] == "SwiftTransformer"
        assert comp["original_type"] == "tSwiftDataTransformer"
        assert comp["position"] == {"x": 400, "y": 200}
        assert comp["config"]["connection_format"] == "row"
        assert comp["config"]["die_on_error"] is True
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_explicit_connection_format(self):
        node = _make_node(
            params={"CONNECTION_FORMAT": '"row"'},
            schema=_sample_schema(),
        )
        result = SwiftTransformerConverter().convert(node, [], {})

        assert result.component["config"]["connection_format"] == "row"

    def test_config_file_param_forwarded(self):
        node = _make_node(
            params={"CONFIG_FILE": '"swift_mapping.yaml"'},
            schema=_sample_schema(),
        )
        result = SwiftTransformerConverter().convert(node, [], {})

        assert result.component["config"]["config_file"] == "swift_mapping.yaml"

    def test_config_file_absent_when_not_set(self):
        node = _make_node(params={}, schema=_sample_schema())
        result = SwiftTransformerConverter().convert(node, [], {})

        assert "config_file" not in result.component["config"]

    def test_die_on_error_defaults_true(self):
        node = _make_node(params={}, schema=_sample_schema())
        result = SwiftTransformerConverter().convert(node, [], {})

        assert result.component["config"]["die_on_error"] is True

    def test_die_on_error_false(self):
        node = _make_node(
            params={"DIE_ON_ERROR": "false"},
            schema=_sample_schema(),
        )
        result = SwiftTransformerConverter().convert(node, [], {})

        assert result.component["config"]["die_on_error"] is False

    def test_no_warnings_on_valid_input(self):
        node = _make_node(schema=_sample_schema())
        result = SwiftTransformerConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []


# --------------------------------------------------------------------- #
#  Schema handling
# --------------------------------------------------------------------- #

class TestSwiftTransformerConverterSchema:
    def test_schema_input_equals_output(self):
        """SwiftTransformer passes schema through: input == output."""
        node = _make_node(schema=_sample_schema())
        result = SwiftTransformerConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 4

    def test_schema_column_details(self):
        node = _make_node(schema=_sample_schema())
        result = SwiftTransformerConverter().convert(node, [], {})

        cols = result.component["schema"]["input"]
        msg_type_col = cols[0]
        sender_col = cols[1]

        assert msg_type_col["name"] == "message_type"
        assert msg_type_col["nullable"] is False
        assert msg_type_col["key"] is True

        assert sender_col["name"] == "sender_bic"
        assert sender_col["nullable"] is True
        assert sender_col["key"] is False

    def test_empty_schema(self):
        node = _make_node(schema={})
        result = SwiftTransformerConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}
