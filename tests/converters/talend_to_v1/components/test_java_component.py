"""Tests for tJava -> JavaComponent converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.java_component import (
    JavaComponentConverter,
    _decode_xml_linebreaks,
)


def _make_node(params=None, schema=None, component_type="tJava"):
    return TalendNode(
        component_id=f"{component_type}_1",
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
    )


class TestDecodeXmlLinebreaks:
    """Unit tests for the _decode_xml_linebreaks helper."""

    def test_crlf_entity(self):
        """&#xD;&#xA; is decoded to a single newline."""
        assert _decode_xml_linebreaks("line1&#xD;&#xA;line2") == "line1\nline2"

    def test_lf_entity(self):
        """&#xA; alone is decoded to newline."""
        assert _decode_xml_linebreaks("a&#xA;b") == "a\nb"

    def test_cr_entity(self):
        """&#xD; alone is decoded to newline."""
        assert _decode_xml_linebreaks("a&#xD;b") == "a\nb"

    def test_mixed_entities(self):
        """Mixed CRLF, LF, and CR entities are all decoded."""
        raw = "import foo;&#xD;&#xA;import bar;&#xA;import baz;&#xD;done"
        expected = "import foo;\nimport bar;\nimport baz;\ndone"
        assert _decode_xml_linebreaks(raw) == expected

    def test_no_entities(self):
        """Plain text without entities passes through unchanged."""
        assert _decode_xml_linebreaks("System.out.println()") == "System.out.println()"

    def test_empty_string(self):
        """Empty string stays empty."""
        assert _decode_xml_linebreaks("") == ""


class TestJavaComponentConverter:
    """Tests for JavaComponentConverter."""

    def test_basic_code_and_imports(self):
        """CODE and IMPORT params are decoded and placed in config."""
        node = _make_node(params={
            "CODE": 'System.out.println("hello");&#xD;&#xA;int x = 1;',
            "IMPORT": "import java.util.List;&#xA;import java.util.Map;",
        })
        result = JavaComponentConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "JavaComponent"
        assert comp["original_type"] == "tJava"
        assert comp["id"] == "tJava_1"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["java_code"] == 'System.out.println("hello");\nint x = 1;'
        assert cfg["imports"] == "import java.util.List;\nimport java.util.Map;"
        assert not result.warnings

    def test_empty_code_produces_warning(self):
        """When CODE is empty, a warning is emitted."""
        node = _make_node(params={"CODE": "", "IMPORT": ""})
        result = JavaComponentConverter().convert(node, [], {})

        assert any("empty" in w.lower() for w in result.warnings)
        assert result.component["config"]["java_code"] == ""

    def test_missing_params_defaults(self):
        """Missing CODE and IMPORT default to empty strings with a warning."""
        node = _make_node(params={})
        result = JavaComponentConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["java_code"] == ""
        assert cfg["imports"] == ""
        assert any("empty" in w.lower() for w in result.warnings)

    def test_code_with_only_cr_entities(self):
        """CODE with &#xD; (CR) entities decodes correctly."""
        node = _make_node(params={
            "CODE": "line1&#xD;line2&#xD;line3",
            "IMPORT": "",
        })
        result = JavaComponentConverter().convert(node, [], {})
        assert result.component["config"]["java_code"] == "line1\nline2\nline3"

    def test_schema_passthrough(self):
        """Schema is parsed and set as both input and output."""
        node = _make_node(
            params={"CODE": "// transform", "IMPORT": ""},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", length=100),
                    SchemaColumn(name="amount", type="id_Double", precision=2),
                ]
            },
        )
        result = JavaComponentConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 3
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][0]["key"] is True
        assert schema["output"][0]["nullable"] is False
        assert schema["output"][1]["name"] == "name"
        assert schema["output"][1]["length"] == 100
        assert schema["output"][2]["name"] == "amount"
        assert schema["output"][2]["precision"] == 2

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"CODE": "// noop"})
        result = JavaComponentConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = JavaComponentConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registry_registration(self):
        """The converter is registered under 'tJava'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tJava")
        assert cls is JavaComponentConverter

    def test_imports_only_no_code(self):
        """IMPORT is set but CODE is empty -- should still warn."""
        node = _make_node(params={
            "CODE": "",
            "IMPORT": "import java.util.Date;",
        })
        result = JavaComponentConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["java_code"] == ""
        assert cfg["imports"] == "import java.util.Date;"
        assert any("empty" in w.lower() for w in result.warnings)

    def test_multiline_code_with_crlf(self):
        """Multi-line CODE with CRLF entities is fully decoded."""
        raw_code = (
            "String name = row.getName();&#xD;&#xA;"
            "if (name != null) {&#xD;&#xA;"
            "    row.setName(name.trim());&#xD;&#xA;"
            "}"
        )
        node = _make_node(params={"CODE": raw_code, "IMPORT": ""})
        result = JavaComponentConverter().convert(node, [], {})

        expected = (
            "String name = row.getName();\n"
            "if (name != null) {\n"
            "    row.setName(name.trim());\n"
            "}"
        )
        assert result.component["config"]["java_code"] == expected
