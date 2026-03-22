"""Tests for tFileInputRaw -> TFileInputRaw converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_raw import (
    FileInputRawConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tFileInputRaw_1",
        component_type="tFileInputRaw",
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
    )


class TestFileInputRawConverter:
    """Tests for FileInputRawConverter."""

    def test_basic_config(self):
        """Config params are extracted and quote-stripped correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/raw_input.bin"',
            "AS_STRING": "false",
            "ENCODING": '"ISO-8859-1"',
            "DIE_ON_ERROR": "true",
        })
        result = FileInputRawConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "TFileInputRaw"
        assert comp["original_type"] == "tFileInputRaw"
        assert comp["id"] == "tFileInputRaw_1"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["filename"] == "/data/raw_input.bin"
        assert cfg["as_string"] is False
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["die_on_error"] is True

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={"FILENAME": '"/data/file.raw"'})
        result = FileInputRawConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/file.raw"
        assert cfg["as_string"] is True
        assert cfg["encoding"] == "UTF-8"
        assert cfg["die_on_error"] is False

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={})
        result = FileInputRawConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_schema_parsed(self):
        """Schema columns are parsed into output schema dicts."""
        node = _make_node(
            params={"FILENAME": '"test.raw"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="content", type="id_String", key=False, length=500),
                    SchemaColumn(name="line_num", type="id_Integer", key=True, nullable=False),
                ]
            },
        )
        result = FileInputRawConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 2
        assert output_schema[0]["name"] == "content"
        assert output_schema[0]["length"] == 500
        assert output_schema[1]["name"] == "line_num"
        assert output_schema[1]["key"] is True
        assert output_schema[1]["nullable"] is False

    def test_input_schema_always_empty(self):
        """FileInputRaw is a source — input schema must be empty."""
        node = _make_node(params={"FILENAME": '"x.raw"'})
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_boolean_params_from_strings(self):
        """Boolean params accept string representations."""
        node = _make_node(params={
            "FILENAME": '"data.raw"',
            "AS_STRING": "true",
            "DIE_ON_ERROR": "1",
        })
        result = FileInputRawConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["as_string"] is True
        assert cfg["die_on_error"] is True

    def test_boolean_params_from_native(self):
        """Boolean params accept native bool values."""
        node = _make_node(params={
            "FILENAME": '"data.raw"',
            "AS_STRING": False,
            "DIE_ON_ERROR": True,
        })
        result = FileInputRawConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["as_string"] is False
        assert cfg["die_on_error"] is True

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={"FILENAME": '"f.raw"'})
        result = FileInputRawConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"FILENAME": '"f.raw"'})
        result = FileInputRawConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_registry_lookup(self):
        """The converter is registered under 'tFileInputRaw'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFileInputRaw")
        assert cls is FileInputRawConverter

    def test_no_warnings_with_valid_filename(self):
        """No warnings when FILENAME is provided."""
        node = _make_node(params={"FILENAME": '"/valid/path.raw"'})
        result = FileInputRawConverter().convert(node, [], {})
        assert result.warnings == []
