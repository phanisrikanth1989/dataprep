"""Tests for tPython -> PythonComponent converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.python_component import (
    PythonComponentConverter,
    _decode_xml_linebreaks,
)


def _make_node(params=None, schema=None, component_type="tPython"):
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
        raw = "import os&#xD;&#xA;import sys&#xA;import re&#xD;done"
        expected = "import os\nimport sys\nimport re\ndone"
        assert _decode_xml_linebreaks(raw) == expected

    def test_no_entities(self):
        """Plain text without entities passes through unchanged."""
        assert _decode_xml_linebreaks("print('hello')") == "print('hello')"

    def test_empty_string(self):
        """Empty string stays empty."""
        assert _decode_xml_linebreaks("") == ""


class TestPythonComponentConverter:
    """Tests for PythonComponentConverter."""

    def test_basic_code_and_imports(self):
        """CODE and IMPORT params are decoded and placed in config."""
        node = _make_node(params={
            "CODE": 'x = row["name"].upper()&#xD;&#xA;row["name"] = x',
            "IMPORT": "import os&#xA;import sys",
        })
        result = PythonComponentConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "PythonComponent"
        assert comp["original_type"] == "tPython"
        assert comp["id"] == "tPython_1"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["python_code"] == 'x = row["name"].upper()\nrow["name"] = x'
        assert cfg["imports"] == "import os\nimport sys"
        assert not result.warnings

    def test_python_code_is_extracted_and_not_empty(self):
        """CONV-PC-001 regression: python_code MUST be extracted from CODE.

        The old converter never extracted this field. This test ensures that
        when CODE is supplied, python_code is populated and NOT empty.
        """
        node = _make_node(params={
            "CODE": "print('hello world')",
        })
        result = PythonComponentConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["python_code"] != "", "python_code must not be empty when CODE is provided"
        assert cfg["python_code"] == "print('hello world')"
        assert not result.warnings

    def test_empty_code_produces_warning(self):
        """When CODE is empty, a warning is emitted."""
        node = _make_node(params={"CODE": "", "IMPORT": ""})
        result = PythonComponentConverter().convert(node, [], {})

        assert any("empty" in w.lower() for w in result.warnings)
        assert result.component["config"]["python_code"] == ""

    def test_missing_params_defaults(self):
        """Missing CODE and IMPORT default to empty strings with a warning."""
        node = _make_node(params={})
        result = PythonComponentConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["python_code"] == ""
        assert cfg["imports"] == ""
        assert any("empty" in w.lower() for w in result.warnings)

    def test_code_with_quotes_preserved(self):
        """_get_param preserves quotes inside CODE (not stripped like _get_str).

        This is critical -- CODE may contain Python strings with quotes.
        """
        code_with_quotes = '"hello" + "world"'
        node = _make_node(params={"CODE": code_with_quotes})
        result = PythonComponentConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["python_code"] == '"hello" + "world"'

    def test_schema_passthrough(self):
        """Schema is parsed and set as both input and output."""
        node = _make_node(
            params={"CODE": "# transform", "IMPORT": ""},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", length=100),
                    SchemaColumn(name="amount", type="id_Double", precision=2),
                ]
            },
        )
        result = PythonComponentConverter().convert(node, [], {})
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
        node = _make_node(params={"CODE": "# noop"})
        result = PythonComponentConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = PythonComponentConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registry_registration(self):
        """The converter is registered under 'tPython'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tPython")
        assert cls is PythonComponentConverter

    def test_imports_only_no_code(self):
        """IMPORT is set but CODE is empty -- should still warn."""
        node = _make_node(params={
            "CODE": "",
            "IMPORT": "import pandas as pd",
        })
        result = PythonComponentConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["python_code"] == ""
        assert cfg["imports"] == "import pandas as pd"
        assert any("empty" in w.lower() for w in result.warnings)

    def test_multiline_code_with_crlf(self):
        """Multi-line CODE with CRLF entities is fully decoded."""
        raw_code = (
            "import pandas as pd&#xD;&#xA;"
            "df = pd.DataFrame(data)&#xD;&#xA;"
            "df = df.dropna()&#xD;&#xA;"
            "result = df.to_dict()"
        )
        node = _make_node(params={"CODE": raw_code, "IMPORT": ""})
        result = PythonComponentConverter().convert(node, [], {})

        expected = (
            "import pandas as pd\n"
            "df = pd.DataFrame(data)\n"
            "df = df.dropna()\n"
            "result = df.to_dict()"
        )
        assert result.component["config"]["python_code"] == expected
