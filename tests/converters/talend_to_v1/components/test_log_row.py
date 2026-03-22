"""Tests for the LogRowConverter (tLogRow -> LogRow)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.log_row import (
    LogRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="log_row_1",
               component_type="tLogRow"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 400, "y": 200},
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

class TestLogRowConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tLogRow") is LogRowConverter


# --------------------------------------------------------------------- #
#  Basic conversion
# --------------------------------------------------------------------- #

class TestLogRowConverterBasic:
    def test_basic_conversion_with_defaults(self):
        node = _make_node(schema=_sample_schema())
        result = LogRowConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "log_row_1"
        assert comp["type"] == "LogRow"
        assert comp["original_type"] == "tLogRow"
        assert comp["position"] == {"x": 400, "y": 200}
        assert comp["config"]["basic_mode"] is False
        assert comp["config"]["table_print"] is False
        assert comp["config"]["vertical"] is False
        assert comp["config"]["print_header"] is False
        assert comp["config"]["print_unique_name"] is False
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_all_params_true(self):
        node = _make_node(
            params={
                "BASIC_MODE": "true",
                "TABLE_PRINT": "true",
                "VERTICAL": "true",
                "PRINT_HEADER": "true",
                "PRINT_UNIQUE_NAME": "true",
            },
            schema=_sample_schema(),
        )
        result = LogRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["basic_mode"] is True
        assert cfg["table_print"] is True
        assert cfg["vertical"] is True
        assert cfg["print_header"] is True
        assert cfg["print_unique_name"] is True

    def test_mixed_params(self):
        node = _make_node(
            params={
                "BASIC_MODE": "true",
                "TABLE_PRINT": "false",
                "PRINT_HEADER": "true",
            },
            schema=_sample_schema(),
        )
        result = LogRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["basic_mode"] is True
        assert cfg["table_print"] is False
        assert cfg["vertical"] is False        # default
        assert cfg["print_header"] is True
        assert cfg["print_unique_name"] is False  # default

    def test_no_params_uses_defaults(self):
        node = _make_node(params={})
        result = LogRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["basic_mode"] is False
        assert cfg["table_print"] is False
        assert cfg["vertical"] is False
        assert cfg["print_header"] is False
        assert cfg["print_unique_name"] is False

    def test_no_warnings_on_valid_input(self):
        node = _make_node(schema=_sample_schema())
        result = LogRowConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []


# --------------------------------------------------------------------- #
#  Schema handling
# --------------------------------------------------------------------- #

class TestLogRowConverterSchema:
    def test_schema_input_equals_output(self):
        """LogRow is a passthrough: input schema == output schema."""
        node = _make_node(schema=_sample_schema())
        result = LogRowConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 2

    def test_schema_column_details(self):
        node = _make_node(schema=_sample_schema())
        result = LogRowConverter().convert(node, [], {})

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
        result = LogRowConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}


# --------------------------------------------------------------------- #
#  Boolean parameter edge cases
# --------------------------------------------------------------------- #

class TestLogRowConverterBooleanEdgeCases:
    def test_boolean_native_true(self):
        node = _make_node(params={"BASIC_MODE": True}, schema=_sample_schema())
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["basic_mode"] is True

    def test_boolean_string_1(self):
        node = _make_node(params={"BASIC_MODE": "1"}, schema=_sample_schema())
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["basic_mode"] is True

    def test_boolean_string_0(self):
        node = _make_node(params={"BASIC_MODE": "0"}, schema=_sample_schema())
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["basic_mode"] is False
