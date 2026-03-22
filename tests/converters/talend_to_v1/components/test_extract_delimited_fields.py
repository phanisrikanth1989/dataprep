"""Tests for tExtractDelimitedFields -> ExtractDelimitedFields converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.extract_delimited_fields import (
    ExtractDelimitedFieldsConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tExtractDelimitedFields_1",
        component_type="tExtractDelimitedFields",
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
    )


class TestExtractDelimitedFieldsConverter:
    """Tests for ExtractDelimitedFieldsConverter."""

    def test_basic_config(self):
        """All config params are extracted correctly with explicit values."""
        node = _make_node(params={
            "FIELDSEPARATOR": '","',
            "ROWSEPARATOR": '"\\n"',
            "ADVANCED_SEPARATOR": "true",
            "THOUSANDS_SEPARATOR": '"."',
            "DECIMAL_SEPARATOR": '","',
            "TRIMALL": "true",
            "REMOVE_EMPTY_ROW": "true",
            "DIE_ON_ERROR": "true",
        })
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "ExtractDelimitedFields"
        assert comp["original_type"] == "tExtractDelimitedFields"
        assert comp["id"] == "tExtractDelimitedFields_1"
        assert comp["position"] == {"x": 320, "y": 160}

        cfg = comp["config"]
        assert cfg["field_separator"] == ","
        assert cfg["row_separator"] == "\\n"
        assert cfg["advanced_separator"] is True
        assert cfg["thousands_separator"] == "."
        assert cfg["decimal_separator"] == ","
        assert cfg["trim_all"] is True
        assert cfg["remove_empty_row"] is True
        assert cfg["die_on_error"] is True

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["field_separator"] == ";"
        assert cfg["row_separator"] == "\\n"
        assert cfg["advanced_separator"] is False
        assert cfg["thousands_separator"] == ","
        assert cfg["decimal_separator"] == "."
        assert cfg["trim_all"] is False
        assert cfg["remove_empty_row"] is False
        assert cfg["die_on_error"] is False
        # No warnings when using defaults (field_separator ";" is not empty)
        assert not result.warnings

    def test_empty_field_separator_warning(self):
        """An empty FIELDSEPARATOR produces a warning (CONV-EDF-002)."""
        node = _make_node(params={
            "FIELDSEPARATOR": '""',
        })
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})

        assert any("FIELDSEPARATOR" in w for w in result.warnings)
        assert result.component["config"]["field_separator"] == ""

    def test_boolean_params_are_bool_not_string(self):
        """CONV-EDF-004/006: boolean params must be Python bools, not strings."""
        node = _make_node(params={
            "ADVANCED_SEPARATOR": "false",
            "TRIMALL": "false",
            "REMOVE_EMPTY_ROW": "false",
            "DIE_ON_ERROR": "false",
        })
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["advanced_separator"] is False
        assert isinstance(cfg["advanced_separator"], bool)
        assert cfg["trim_all"] is False
        assert isinstance(cfg["trim_all"], bool)
        assert cfg["remove_empty_row"] is False
        assert isinstance(cfg["remove_empty_row"], bool)
        assert cfg["die_on_error"] is False
        assert isinstance(cfg["die_on_error"], bool)

    def test_schema_passthrough(self):
        """CONV-EDF-005: both input and output schema must match FLOW schema."""
        node = _make_node(
            params={"FIELDSEPARATOR": '";"'},
            schema={
                "FLOW": [
                    SchemaColumn(
                        name="raw_line", type="id_String",
                        key=False, nullable=True, length=500,
                    ),
                    SchemaColumn(
                        name="col1", type="id_String",
                        key=False, nullable=True, length=100,
                    ),
                    SchemaColumn(
                        name="amount", type="id_Double",
                        key=False, nullable=True, precision=2,
                    ),
                ]
            },
        )
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 3
        assert schema["output"][0]["name"] == "raw_line"
        assert schema["output"][0]["length"] == 500
        assert schema["output"][2]["name"] == "amount"
        assert schema["output"][2]["precision"] == 2

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registration(self):
        """The converter is registered under 'tExtractDelimitedFields'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tExtractDelimitedFields")
        assert cls is ExtractDelimitedFieldsConverter

    def test_die_on_error_defaults_false(self):
        """CONV-EDF-006: die_on_error defaults to False when not provided."""
        node = _make_node(params={})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_pipe_separator(self):
        """Pipe character as field separator is handled correctly."""
        node = _make_node(params={
            "FIELDSEPARATOR": '"|"',
        })
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["field_separator"] == "|"
