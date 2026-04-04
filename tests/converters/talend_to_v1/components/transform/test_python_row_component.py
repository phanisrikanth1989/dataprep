"""Tests for tPythonRow -> PythonRowComponent converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.python_row_component import (
    PythonRowComponentConverter,
    _decode_xml_linebreaks,
)


def _make_node(params=None, schema=None, component_type="tPythonRow"):
    return TalendNode(
        component_id=f"{component_type}_1",
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
    )


class TestPythonRowComponentConverter:
    """Tests for PythonRowComponentConverter."""

    def test_basic_config(self):
        """CODE is extracted under python_code and decoded; die_on_error defaults True."""
        node = _make_node(params={
            "CODE": "output_row['name'] = input_row['name'].upper()&#xA;output_row['age'] = input_row['age'] + 1",
        })
        result = PythonRowComponentConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "PythonRowComponent"
        assert comp["original_type"] == "tPythonRow"
        assert comp["id"] == "tPythonRow_1"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["python_code"] == (
            "output_row['name'] = input_row['name'].upper()\n"
            "output_row['age'] = input_row['age'] + 1"
        )
        # CONV-PRC-001: key must be python_code, not CODE
        assert "CODE" not in cfg
        # CONV-PRC-005: die_on_error defaults to True
        assert cfg["die_on_error"] is True

    def test_die_on_error_false(self):
        """DIE_ON_ERROR='false' is mapped to die_on_error=False."""
        node = _make_node(params={
            "CODE": "pass",
            "DIE_ON_ERROR": "false",
        })
        result = PythonRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_die_on_error_true_string(self):
        """DIE_ON_ERROR='true' is mapped to die_on_error=True."""
        node = _make_node(params={
            "CODE": "pass",
            "DIE_ON_ERROR": "true",
        })
        result = PythonRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_output_schema_built_from_flow(self):
        """output_schema is a list of {name, type} dicts derived from FLOW schema."""
        node = _make_node(
            params={"CODE": "# transform"},
            schema={
                "FLOW": [
                    SchemaColumn(name="name", type="id_String"),
                    SchemaColumn(name="age", type="id_Integer"),
                    SchemaColumn(name="salary", type="id_Double"),
                    SchemaColumn(name="active", type="id_Boolean"),
                    SchemaColumn(name="hire_date", type="id_Date"),
                ]
            },
        )
        result = PythonRowComponentConverter().convert(node, [], {})
        output_schema = result.component["config"]["output_schema"]

        assert output_schema == [
            {"name": "name", "type": "str"},
            {"name": "age", "type": "int"},
            {"name": "salary", "type": "float"},
            {"name": "active", "type": "bool"},
            {"name": "hire_date", "type": "datetime"},
        ]

    def test_empty_code_warning(self):
        """Empty CODE param produces a warning."""
        node = _make_node(params={})
        result = PythonRowComponentConverter().convert(node, [], {})

        assert any("CODE is empty" in w for w in result.warnings)
        assert result.component["config"]["python_code"] == ""

    def test_schema_input_equals_output(self):
        """Both input and output schema are derived from FLOW and are equal."""
        node = _make_node(
            params={"CODE": "# transform"},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="value", type="id_String", length=100),
                ]
            },
        )
        result = PythonRowComponentConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][0]["key"] is True
        assert schema["output"][0]["nullable"] is False
        assert schema["output"][1]["name"] == "value"
        assert schema["output"][1]["length"] == 100

    def test_empty_schema_produces_empty_output_schema(self):
        """When there is no FLOW schema, output_schema is an empty list."""
        node = _make_node(params={"CODE": "# no schema"})
        result = PythonRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["output_schema"] == []
        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={})
        result = PythonRowComponentConverter().convert(node, [], {})
        comp = result.component

        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = PythonRowComponentConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registry_registration(self):
        """The converter is registered under 'tPythonRow'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tPythonRow")
        assert cls is PythonRowComponentConverter

    def test_xml_linebreak_decoding_crlf(self):
        """CRLF entity pairs are decoded to single newlines."""
        node = _make_node(params={
            "CODE": "line1&#xD;&#xA;line2&#xD;&#xA;line3",
        })
        result = PythonRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["python_code"] == "line1\nline2\nline3"

    def test_unknown_type_in_output_schema(self):
        """Unknown Talend types default to 'str' in the output_schema."""
        node = _make_node(
            params={"CODE": "# pass"},
            schema={
                "FLOW": [
                    SchemaColumn(name="custom_col", type="id_UnknownType"),
                ]
            },
        )
        result = PythonRowComponentConverter().convert(node, [], {})
        output_schema = result.component["config"]["output_schema"]
        assert output_schema == [{"name": "custom_col", "type": "str"}]


class TestDecodeXmlLinebreaks:
    """Unit tests for the _decode_xml_linebreaks helper."""

    def test_crlf(self):
        assert _decode_xml_linebreaks("a&#xD;&#xA;b") == "a\nb"

    def test_lf_only(self):
        assert _decode_xml_linebreaks("a&#xA;b") == "a\nb"

    def test_cr_only(self):
        assert _decode_xml_linebreaks("a&#xD;b") == "a\nb"

    def test_no_entities(self):
        assert _decode_xml_linebreaks("plain text") == "plain text"

    def test_empty(self):
        assert _decode_xml_linebreaks("") == ""
