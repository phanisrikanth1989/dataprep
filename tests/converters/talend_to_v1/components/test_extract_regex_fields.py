"""Tests for tExtractRegexFields -> ExtractRegexFields converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.extract_regex_fields import (
    ExtractRegexFieldsConverter,
)


def _make_node(params=None, schema=None, component_type="tExtractRegexFields"):
    return TalendNode(
        component_id=f"{component_type}_1",
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
    )


class TestExtractRegexFieldsConverter:
    """Tests for ExtractRegexFieldsConverter."""

    def test_basic_config(self):
        """Config params are extracted correctly."""
        node = _make_node(params={
            "REGEX": '"(\\\\d+)-(\\\\w+)"',
            "GROUP": "1",
            "DIE_ON_ERROR": "true",
        })
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "ExtractRegexFields"
        assert comp["original_type"] == "tExtractRegexFields"
        assert comp["id"] == "tExtractRegexFields_1"
        assert comp["position"] == {"x": 320, "y": 160}

        cfg = comp["config"]
        assert cfg["regex"] == "(\\\\d+)-(\\\\w+)"
        assert cfg["group"] == 1
        assert cfg["die_on_error"] is True

    def test_defaults_when_params_missing(self):
        """Missing params fall back to defaults and a warning is emitted."""
        node = _make_node(params={})
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["regex"] == ""
        assert cfg["group"] == 0
        assert cfg["die_on_error"] is False

        assert any("no effect" in w.lower() for w in result.warnings)

    def test_schema_input_output_match(self):
        """Input and output schemas are both derived from FLOW metadata."""
        node = _make_node(
            params={"REGEX": '".*"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="line", type="id_String", nullable=False),
                    SchemaColumn(name="group1", type="id_String", length=50),
                ],
            },
        )
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "line"
        assert schema["output"][0]["nullable"] is False
        assert schema["output"][1]["name"] == "group1"
        assert schema["output"][1]["length"] == 50
        assert "reject" not in schema

    def test_reject_schema_included_when_present(self):
        """Reject schema is included when REJECT metadata exists."""
        node = _make_node(
            params={"REGEX": '"^(\\\\d+)$"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="value", type="id_String"),
                ],
                "REJECT": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="value", type="id_String"),
                    SchemaColumn(name="errorMessage", type="id_String"),
                ],
            },
        )
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert "reject" in schema
        assert len(schema["reject"]) == 3
        assert schema["reject"][2]["name"] == "errorMessage"
        assert len(schema["input"]) == 2
        assert len(schema["output"]) == 2

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"REGEX": '"test"'})
        result = ExtractRegexFieldsConverter().convert(node, [], {})
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
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registry_registration(self):
        """The converter is registered under 'tExtractRegexFields'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY

        cls = REGISTRY.get("tExtractRegexFields")
        assert cls is ExtractRegexFieldsConverter

    def test_group_default_zero(self):
        """GROUP defaults to 0 when not specified."""
        node = _make_node(params={"REGEX": '"(a)(b)"'})
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["group"] == 0

    def test_die_on_error_false_string(self):
        """DIE_ON_ERROR 'false' string is parsed as False."""
        node = _make_node(params={
            "REGEX": '"x"',
            "DIE_ON_ERROR": "false",
        })
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_no_reject_schema_when_absent(self):
        """Schema dict has no 'reject' key when REJECT metadata is absent."""
        node = _make_node(
            params={"REGEX": '"(.*)"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="data", type="id_String"),
                ],
            },
        )
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert "reject" not in result.component["schema"]

    def test_empty_flow_schema(self):
        """Handles the case where FLOW has no columns."""
        node = _make_node(
            params={"REGEX": '".*"'},
            schema={"FLOW": []},
        )
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == []
        assert schema["output"] == []

    def test_no_warnings_when_regex_present(self):
        """No warnings emitted when REGEX has a value."""
        node = _make_node(params={"REGEX": '"\\\\d+"'})
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.warnings == []
