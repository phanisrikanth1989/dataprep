"""Tests for tChangeFileEncoding -> ChangeFileEncoding converter."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.change_file_encoding import (
    ChangeFileEncodingConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tChangeFileEncoding_1"):
    """Create a TalendNode for tChangeFileEncoding with given params."""
    return TalendNode(
        component_id=component_id,
        component_type="tChangeFileEncoding",
        params=params or {},
        schema={},
        position={"x": 256, "y": 128},
        raw_xml=ET.Element("node"),
    )


def _convert(node, connections=None, context=None):
    """Helper to run the converter."""
    converter = ChangeFileEncodingConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


# --------------------------------------------------------------------- #
#  Registration
# --------------------------------------------------------------------- #

class TestChangeFileEncodingRegistration:
    """Verify the converter is registered in the global registry."""

    def test_registered_for_tchangefileencoding(self):
        cls = REGISTRY.get("tChangeFileEncoding")
        assert cls is ChangeFileEncodingConverter


# --------------------------------------------------------------------- #
#  Basic conversion
# --------------------------------------------------------------------- #

class TestChangeFileEncodingBasicConversion:
    """Test basic parameter extraction and component structure."""

    def test_full_params(self):
        node = _make_node(params={
            "INFILE_NAME": '"/data/input/report.csv"',
            "OUTFILE_NAME": '"/data/output/report_utf8.csv"',
            "USE_INENCODING": "true",
            "INENCODING": '"ISO-8859-1"',
            "ENCODING": '"UTF-8"',
            "BUFFERSIZE": "16384",
            "CREATE": "true",
        })
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tChangeFileEncoding_1"
        assert comp["type"] == "ChangeFileEncoding"
        assert comp["original_type"] == "tChangeFileEncoding"
        assert comp["position"] == {"x": 256, "y": 128}

        cfg = comp["config"]
        assert cfg["infile"] == "/data/input/report.csv"
        assert cfg["outfile"] == "/data/output/report_utf8.csv"
        assert cfg["use_inencoding"] is True
        assert cfg["inencoding"] == "ISO-8859-1"
        assert cfg["outencoding"] == "UTF-8"
        assert cfg["buffer_size"] == 16384
        assert cfg["create"] is True
        assert result.warnings == []

    def test_component_structure_has_required_keys(self):
        node = _make_node(params={
            "INFILE_NAME": '"/in/file.txt"',
            "OUTFILE_NAME": '"/out/file.txt"',
            "ENCODING": '"UTF-8"',
        })
        result = _convert(node)
        comp = result.component
        assert set(comp.keys()) == {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert comp["schema"] == {"input": [], "output": []}

    def test_result_type_is_component_result(self):
        node = _make_node(params={
            "INFILE_NAME": '"/in/f.txt"',
            "OUTFILE_NAME": '"/out/f.txt"',
            "ENCODING": '"UTF-8"',
        })
        result = _convert(node)
        assert isinstance(result, ComponentResult)


# --------------------------------------------------------------------- #
#  Defaults
# --------------------------------------------------------------------- #

class TestChangeFileEncodingDefaults:
    """Verify default values when parameters are missing."""

    def test_defaults_when_empty_params(self):
        node = _make_node(params={})
        result = _convert(node)
        cfg = result.component["config"]

        assert cfg["infile"] == ""
        assert cfg["outfile"] == ""
        assert cfg["use_inencoding"] is False
        assert cfg["inencoding"] == ""
        assert cfg["outencoding"] == ""
        assert cfg["buffer_size"] == 8192
        assert cfg["create"] is False

    def test_buffer_size_default_8192(self):
        """BUFFERSIZE defaults to 8192 when not specified."""
        node = _make_node(params={
            "INFILE_NAME": '"a.txt"',
            "OUTFILE_NAME": '"b.txt"',
            "ENCODING": '"UTF-8"',
        })
        result = _convert(node)
        assert result.component["config"]["buffer_size"] == 8192

    def test_use_inencoding_default_false(self):
        """USE_INENCODING defaults to False when not specified."""
        node = _make_node(params={
            "INFILE_NAME": '"a.txt"',
            "OUTFILE_NAME": '"b.txt"',
            "ENCODING": '"UTF-8"',
        })
        result = _convert(node)
        assert result.component["config"]["use_inencoding"] is False

    def test_create_default_false(self):
        """CREATE defaults to False when not specified."""
        node = _make_node(params={
            "INFILE_NAME": '"a.txt"',
            "OUTFILE_NAME": '"b.txt"',
            "ENCODING": '"UTF-8"',
        })
        result = _convert(node)
        assert result.component["config"]["create"] is False


# --------------------------------------------------------------------- #
#  Warnings
# --------------------------------------------------------------------- #

class TestChangeFileEncodingWarnings:
    """Test that appropriate warnings are generated."""

    def test_warning_when_infile_empty(self):
        node = _make_node(params={
            "OUTFILE_NAME": '"/out/f.txt"',
            "ENCODING": '"UTF-8"',
        })
        result = _convert(node)
        assert any("INFILE_NAME" in w and "empty" in w for w in result.warnings)

    def test_warning_when_outfile_empty(self):
        node = _make_node(params={
            "INFILE_NAME": '"/in/f.txt"',
            "ENCODING": '"UTF-8"',
        })
        result = _convert(node)
        assert any("OUTFILE_NAME" in w and "empty" in w for w in result.warnings)

    def test_warning_when_outencoding_empty(self):
        node = _make_node(params={
            "INFILE_NAME": '"/in/f.txt"',
            "OUTFILE_NAME": '"/out/f.txt"',
        })
        result = _convert(node)
        assert any("ENCODING" in w and "empty" in w for w in result.warnings)

    def test_warning_when_use_inencoding_true_but_inencoding_empty(self):
        node = _make_node(params={
            "INFILE_NAME": '"/in/f.txt"',
            "OUTFILE_NAME": '"/out/f.txt"',
            "ENCODING": '"UTF-8"',
            "USE_INENCODING": "true",
        })
        result = _convert(node)
        assert any(
            "USE_INENCODING" in w and "INENCODING" in w
            for w in result.warnings
        )

    def test_no_warning_when_use_inencoding_true_with_inencoding(self):
        node = _make_node(params={
            "INFILE_NAME": '"/in/f.txt"',
            "OUTFILE_NAME": '"/out/f.txt"',
            "ENCODING": '"UTF-8"',
            "USE_INENCODING": "true",
            "INENCODING": '"ISO-8859-1"',
        })
        result = _convert(node)
        assert result.warnings == []

    def test_no_warnings_when_all_valid(self):
        node = _make_node(params={
            "INFILE_NAME": '"/in/f.txt"',
            "OUTFILE_NAME": '"/out/f.txt"',
            "ENCODING": '"UTF-8"',
        })
        result = _convert(node)
        assert result.warnings == []

    def test_multiple_warnings(self):
        """When all required fields are empty, multiple warnings appear."""
        node = _make_node(params={})
        result = _convert(node)
        assert len(result.warnings) >= 3


# --------------------------------------------------------------------- #
#  Boolean parsing
# --------------------------------------------------------------------- #

class TestChangeFileEncodingBooleanParsing:
    """Test that boolean params handle various input formats."""

    def test_bool_true_string(self):
        node = _make_node(params={
            "INFILE_NAME": '"f"',
            "OUTFILE_NAME": '"o"',
            "ENCODING": '"UTF-8"',
            "CREATE": "true",
        })
        result = _convert(node)
        assert result.component["config"]["create"] is True

    def test_bool_false_string(self):
        node = _make_node(params={
            "INFILE_NAME": '"f"',
            "OUTFILE_NAME": '"o"',
            "ENCODING": '"UTF-8"',
            "CREATE": "false",
        })
        result = _convert(node)
        assert result.component["config"]["create"] is False

    def test_bool_native_true(self):
        node = _make_node(params={
            "INFILE_NAME": '"f"',
            "OUTFILE_NAME": '"o"',
            "ENCODING": '"UTF-8"',
            "USE_INENCODING": True,
            "INENCODING": '"Latin1"',
        })
        result = _convert(node)
        assert result.component["config"]["use_inencoding"] is True

    def test_bool_string_one(self):
        node = _make_node(params={
            "INFILE_NAME": '"f"',
            "OUTFILE_NAME": '"o"',
            "ENCODING": '"UTF-8"',
            "CREATE": "1",
        })
        result = _convert(node)
        assert result.component["config"]["create"] is True

    def test_bool_string_zero(self):
        node = _make_node(params={
            "INFILE_NAME": '"f"',
            "OUTFILE_NAME": '"o"',
            "ENCODING": '"UTF-8"',
            "USE_INENCODING": "0",
        })
        result = _convert(node)
        assert result.component["config"]["use_inencoding"] is False


# --------------------------------------------------------------------- #
#  Integer parsing
# --------------------------------------------------------------------- #

class TestChangeFileEncodingIntegerParsing:
    """Test that integer params handle various input formats."""

    def test_int_as_string(self):
        node = _make_node(params={
            "INFILE_NAME": '"f"',
            "OUTFILE_NAME": '"o"',
            "ENCODING": '"UTF-8"',
            "BUFFERSIZE": "32768",
        })
        result = _convert(node)
        assert result.component["config"]["buffer_size"] == 32768

    def test_int_as_native(self):
        node = _make_node(params={
            "INFILE_NAME": '"f"',
            "OUTFILE_NAME": '"o"',
            "ENCODING": '"UTF-8"',
            "BUFFERSIZE": 4096,
        })
        result = _convert(node)
        assert result.component["config"]["buffer_size"] == 4096

    def test_int_non_numeric_falls_back_to_default(self):
        node = _make_node(params={
            "INFILE_NAME": '"f"',
            "OUTFILE_NAME": '"o"',
            "ENCODING": '"UTF-8"',
            "BUFFERSIZE": "not_a_number",
        })
        result = _convert(node)
        assert result.component["config"]["buffer_size"] == 8192

    def test_int_quoted_string(self):
        node = _make_node(params={
            "INFILE_NAME": '"f"',
            "OUTFILE_NAME": '"o"',
            "ENCODING": '"UTF-8"',
            "BUFFERSIZE": '"2048"',
        })
        result = _convert(node)
        assert result.component["config"]["buffer_size"] == 2048


# --------------------------------------------------------------------- #
#  Edge cases
# --------------------------------------------------------------------- #

class TestChangeFileEncodingEdgeCases:
    """Edge case tests."""

    def test_custom_component_id(self):
        node = _make_node(
            params={
                "INFILE_NAME": '"a"',
                "OUTFILE_NAME": '"b"',
                "ENCODING": '"UTF-8"',
            },
            component_id="tChangeFileEncoding_99",
        )
        result = _convert(node)
        assert result.component["id"] == "tChangeFileEncoding_99"

    def test_unquoted_paths(self):
        """Params without surrounding quotes should still work."""
        node = _make_node(params={
            "INFILE_NAME": "/data/input.txt",
            "OUTFILE_NAME": "/data/output.txt",
            "ENCODING": "UTF-8",
        })
        result = _convert(node)
        cfg = result.component["config"]
        assert cfg["infile"] == "/data/input.txt"
        assert cfg["outfile"] == "/data/output.txt"
        assert cfg["outencoding"] == "UTF-8"

    def test_connections_do_not_affect_config(self):
        node = _make_node(params={
            "INFILE_NAME": '"f.txt"',
            "OUTFILE_NAME": '"o.txt"',
            "ENCODING": '"UTF-8"',
        })
        conns = [
            TalendConnection(
                name="row1",
                source="tChangeFileEncoding_1",
                target="tLogRow_1",
                connector_type="FLOW",
            ),
        ]
        result = _convert(node, connections=conns)
        assert result.component["config"]["infile"] == "f.txt"

    def test_utility_schema_always_empty(self):
        """Regardless of params, schema should always be empty (utility component)."""
        node = _make_node(params={
            "INFILE_NAME": '"f.txt"',
            "OUTFILE_NAME": '"o.txt"',
            "ENCODING": '"UTF-8"',
            "USE_INENCODING": "true",
            "INENCODING": '"Shift_JIS"',
            "BUFFERSIZE": "65536",
            "CREATE": "true",
        })
        result = _convert(node)
        assert result.component["schema"] == {"input": [], "output": []}
