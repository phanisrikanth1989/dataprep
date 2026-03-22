"""Tests for tExtractPositionalFields -> ExtractPositionalFields converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.extract_positional_fields import (
    ExtractPositionalFieldsConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tExtractPositionalFields_1",
        component_type="tExtractPositionalFields",
        params=params or {},
        schema=schema or {},
        position={"x": 256, "y": 128},
    )


class TestExtractPositionalFieldsConverter:
    """Tests for ExtractPositionalFieldsConverter."""

    def test_basic_config(self):
        """All config params are extracted correctly with explicit values."""
        node = _make_node(params={
            "PATTERN": '"10,20,15,5"',
            "DIE_ON_ERROR": "true",
            "TRIM": "true",
            "ADVANCED_SEPARATOR": "true",
            "THOUSANDS_SEPARATOR": '"."',
            "DECIMAL_SEPARATOR": '","',
        })
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "ExtractPositionalFields"
        assert comp["original_type"] == "tExtractPositionalFields"
        assert comp["id"] == "tExtractPositionalFields_1"
        assert comp["position"] == {"x": 256, "y": 128}

        cfg = comp["config"]
        assert cfg["pattern"] == "10,20,15,5"
        assert cfg["die_on_error"] is True
        assert cfg["trim"] is True
        assert cfg["advanced_separator"] is True
        assert cfg["thousands_separator"] == "."
        assert cfg["decimal_separator"] == ","

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["pattern"] == ""
        assert cfg["die_on_error"] is False
        assert cfg["trim"] is False
        assert cfg["advanced_separator"] is False
        assert cfg["thousands_separator"] == ","
        assert cfg["decimal_separator"] == "."

    def test_empty_pattern_warning(self):
        """An empty PATTERN produces a warning."""
        node = _make_node(params={
            "PATTERN": '""',
        })
        result = ExtractPositionalFieldsConverter().convert(node, [], {})

        assert any("PATTERN" in w for w in result.warnings)
        assert result.component["config"]["pattern"] == ""

    def test_missing_pattern_warning(self):
        """A completely missing PATTERN also produces a warning."""
        node = _make_node(params={})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert any("PATTERN" in w for w in result.warnings)

    def test_boolean_params_are_bool_not_string(self):
        """Boolean params must be Python bools, not strings."""
        node = _make_node(params={
            "PATTERN": '"5,10"',
            "DIE_ON_ERROR": "false",
            "TRIM": "false",
            "ADVANCED_SEPARATOR": "false",
        })
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["die_on_error"] is False
        assert isinstance(cfg["die_on_error"], bool)
        assert cfg["trim"] is False
        assert isinstance(cfg["trim"], bool)
        assert cfg["advanced_separator"] is False
        assert isinstance(cfg["advanced_separator"], bool)

    def test_schema_passthrough(self):
        """Both input and output schema must match FLOW schema."""
        node = _make_node(
            params={"PATTERN": '"10,20"'},
            schema={
                "FLOW": [
                    SchemaColumn(
                        name="raw_line", type="id_String",
                        key=False, nullable=True, length=500,
                    ),
                    SchemaColumn(
                        name="field_a", type="id_String",
                        key=False, nullable=True, length=10,
                    ),
                    SchemaColumn(
                        name="field_b", type="id_Integer",
                        key=False, nullable=True, precision=0,
                    ),
                ]
            },
        )
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 3
        assert schema["output"][0]["name"] == "raw_line"
        assert schema["output"][0]["length"] == 500
        assert schema["output"][2]["name"] == "field_b"

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
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
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registration(self):
        """The converter is registered under 'tExtractPositionalFields'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tExtractPositionalFields")
        assert cls is ExtractPositionalFieldsConverter

    def test_no_warnings_with_valid_pattern(self):
        """No warnings when a valid pattern is provided."""
        node = _make_node(params={
            "PATTERN": '"10,20,15"',
        })
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert not result.warnings
