"""Tests for tFileInputRaw -> FileInputRaw converter."""
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

    def test_basic_config_all_params(self):
        """All 8 config params are extracted correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/raw_input.bin"',
            "AS_STRING": "false",
            "AS_BYTEARRAY": "true",
            "AS_INPUTSTREAM": "false",
            "ENCODING": '"ISO-8859-1"',
            "DIE_ON_ERROR": "true",
            "TSTATCATCHER_STATS": "true",
            "LABEL": '"raw_label"',
        })
        result = FileInputRawConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "FileInputRaw"
        assert comp["original_type"] == "tFileInputRaw"
        assert comp["id"] == "tFileInputRaw_1"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["filename"] == "/data/raw_input.bin"
        assert cfg["as_string"] is False
        assert cfg["as_bytearray"] is True
        assert cfg["as_inputstream"] is False
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["die_on_error"] is True
        assert cfg["tstatcatcher_stats"] is True
        assert cfg["label"] == "raw_label"

    def test_defaults_when_params_missing(self):
        """Missing params fall back to correct Talend defaults."""
        node = _make_node(params={"FILENAME": '"/data/file.raw"'})
        result = FileInputRawConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/file.raw"
        assert cfg["as_string"] is True
        assert cfg["as_bytearray"] is False
        assert cfg["as_inputstream"] is False
        assert cfg["encoding"] == "ISO-8859-15"
        assert cfg["die_on_error"] is False
        assert cfg["tstatcatcher_stats"] is False
        assert cfg["label"] == ""

    def test_all_config_keys_present(self):
        """Exactly 8 config keys should be present."""
        node = _make_node(params={"FILENAME": '"/data/file.raw"'})
        result = FileInputRawConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected = {
            "filename", "as_string", "as_bytearray", "as_inputstream",
            "encoding", "die_on_error", "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected

    def test_type_name_is_fileinputraw(self):
        """Type name should be FileInputRaw (not TFileInputRaw)."""
        node = _make_node(params={"FILENAME": '"/data/file.raw"'})
        result = FileInputRawConverter().convert(node, [], {})
        assert result.component["type"] == "FileInputRaw"

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={})
        result = FileInputRawConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_engine_gap_warning_stream_mode(self):
        """as_inputstream=true triggers engine-gap warning."""
        node = _make_node(params={
            "FILENAME": '"/data/file.raw"',
            "AS_INPUTSTREAM": "true",
        })
        result = FileInputRawConverter().convert(node, [], {})
        assert any("AS_INPUTSTREAM=true" in w for w in result.warnings)
        assert any("bytearray" in w for w in result.warnings)

    def test_no_stream_warning_on_default(self):
        """as_string=true (default) produces no stream mode warning."""
        node = _make_node(params={"FILENAME": '"/data/file.raw"'})
        result = FileInputRawConverter().convert(node, [], {})
        assert not any("AS_INPUTSTREAM" in w for w in result.warnings)

    def test_no_warnings_with_valid_filename(self):
        """No warnings when FILENAME is provided and defaults used."""
        node = _make_node(params={"FILENAME": '"/valid/path.raw"'})
        result = FileInputRawConverter().convert(node, [], {})
        assert result.warnings == []

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
            "AS_BYTEARRAY": "false",
            "AS_INPUTSTREAM": "false",
            "DIE_ON_ERROR": "1",
            "TSTATCATCHER_STATS": "true",
        })
        result = FileInputRawConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["as_string"] is True
        assert cfg["as_bytearray"] is False
        assert cfg["as_inputstream"] is False
        assert cfg["die_on_error"] is True
        assert cfg["tstatcatcher_stats"] is True

    def test_boolean_params_from_native(self):
        """Boolean params accept native bool values."""
        node = _make_node(params={
            "FILENAME": '"data.raw"',
            "AS_STRING": False,
            "AS_BYTEARRAY": True,
            "DIE_ON_ERROR": True,
        })
        result = FileInputRawConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["as_string"] is False
        assert cfg["as_bytearray"] is True
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
