"""Tests for tJavaRow -> JavaRowComponent converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.java_row_component import (
    JavaRowComponentConverter,
    _decode_xml_linebreaks,
    _python_type_to_java,
)


def _make_node(params=None, schema=None, component_type="tJavaRow"):
    return TalendNode(
        component_id=f"{component_type}_1",
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
    )


class TestJavaRowComponentConverter:
    """Tests for JavaRowComponentConverter."""

    def test_basic_config(self):
        """CODE and IMPORT are extracted and decoded."""
        node = _make_node(params={
            "CODE": "output_row.name = input_row.name;&#xA;output_row.age = input_row.age + 1;",
            "IMPORT": "import java.util.Date;&#xA;import java.util.List;",
        })
        result = JavaRowComponentConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "JavaRowComponent"
        assert comp["original_type"] == "tJavaRow"
        assert comp["id"] == "tJavaRow_1"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["java_code"] == "output_row.name = input_row.name;\noutput_row.age = input_row.age + 1;"
        assert cfg["imports"] == "import java.util.Date;\nimport java.util.List;"

    def test_output_schema_built_from_flow(self):
        """output_schema maps column names to Java types from FLOW schema."""
        node = _make_node(
            params={
                "CODE": "// transform",
            },
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
        result = JavaRowComponentConverter().convert(node, [], {})
        output_schema = result.component["config"]["output_schema"]

        assert output_schema == {
            "name": "String",
            "age": "Integer",
            "salary": "Double",
            "active": "Boolean",
            "hire_date": "Date",
        }

    def test_output_schema_unknown_type_defaults_to_string(self):
        """Unknown Python types in the schema default to 'String' in output_schema."""
        node = _make_node(
            params={"CODE": "// pass"},
            schema={
                "FLOW": [
                    SchemaColumn(name="custom_col", type="id_UnknownType"),
                ]
            },
        )
        result = JavaRowComponentConverter().convert(node, [], {})
        output_schema = result.component["config"]["output_schema"]

        # convert_type maps unknown to "str", _python_type_to_java maps "str" to "String"
        assert output_schema["custom_col"] == "String"

    def test_empty_code_warning(self):
        """Empty CODE param produces a warning."""
        node = _make_node(params={})
        result = JavaRowComponentConverter().convert(node, [], {})

        assert any("CODE is empty" in w for w in result.warnings)
        assert result.component["config"]["java_code"] == ""

    def test_xml_linebreak_decoding_crlf(self):
        """CRLF entity pairs are decoded to single newlines."""
        node = _make_node(params={
            "CODE": "line1&#xD;&#xA;line2&#xD;&#xA;line3",
            "IMPORT": "",
        })
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["java_code"] == "line1\nline2\nline3"

    def test_schema_input_equals_output(self):
        """Both input and output schema are derived from FLOW and are equal."""
        node = _make_node(
            params={"CODE": "// transform"},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="value", type="id_String", length=100),
                ]
            },
        )
        result = JavaRowComponentConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][0]["key"] is True
        assert schema["output"][0]["nullable"] is False
        assert schema["output"][1]["name"] == "value"
        assert schema["output"][1]["length"] == 100

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={})
        result = JavaRowComponentConverter().convert(node, [], {})
        comp = result.component

        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = JavaRowComponentConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registry_registration(self):
        """The converter is registered under 'tJavaRow'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tJavaRow")
        assert cls is JavaRowComponentConverter

    def test_empty_schema_produces_empty_output_schema(self):
        """When there is no FLOW schema, output_schema is an empty dict."""
        node = _make_node(params={"CODE": "// no schema"})
        result = JavaRowComponentConverter().convert(node, [], {})
        assert result.component["config"]["output_schema"] == {}
        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []

    def test_decimal_and_object_types_in_output_schema(self):
        """Decimal and object Python types are mapped correctly in output_schema."""
        node = _make_node(
            params={"CODE": "// transform"},
            schema={
                "FLOW": [
                    SchemaColumn(name="amount", type="id_BigDecimal"),
                    SchemaColumn(name="payload", type="id_Object"),
                ]
            },
        )
        result = JavaRowComponentConverter().convert(node, [], {})
        output_schema = result.component["config"]["output_schema"]
        assert output_schema["amount"] == "BigDecimal"
        assert output_schema["payload"] == "Object"


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


class TestPythonTypeToJava:
    """Unit tests for the _python_type_to_java helper."""

    def test_str(self):
        assert _python_type_to_java("str") == "String"

    def test_int(self):
        assert _python_type_to_java("int") == "Integer"

    def test_float(self):
        assert _python_type_to_java("float") == "Double"

    def test_bool(self):
        assert _python_type_to_java("bool") == "Boolean"

    def test_datetime(self):
        assert _python_type_to_java("datetime") == "Date"

    def test_unknown_defaults_to_string(self):
        assert _python_type_to_java("SomeCustomType") == "String"
