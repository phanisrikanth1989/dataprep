"""Tests for tFileOutputPositional -> FileOutputPositional converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_output_positional import (
    FileOutputPositionalConverter,
)


def _make_node(params=None, schema=None, component_id="tFileOutputPositional_1"):
    """Build a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type="tFileOutputPositional",
        params=params or {},
        schema=schema or {},
        position={"x": 200, "y": 400},
    )


class TestFileOutputPositionalConverter:
    """Tests for FileOutputPositionalConverter."""

    def test_basic_config_params(self):
        """All config params are extracted and quote-stripped correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/output.pos"',
            "ROWSEPARATOR": '"\\r\\n"',
            "APPEND": "true",
            "INCLUDEHEADER": "true",
            "COMPRESS": "true",
            "ENCODING": '"ISO-8859-1"',
            "CREATE": "false",
            "FLUSHONROW": "true",
            "FLUSHONROW_NUM": "100",
            "DELETE_EMPTYFILE": "true",
            "DIE_ON_ERROR": "false",
            "FORMATS": [],
        })
        result = FileOutputPositionalConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "FileOutputPositional"
        assert comp["original_type"] == "tFileOutputPositional"
        assert comp["id"] == "tFileOutputPositional_1"
        assert comp["position"] == {"x": 200, "y": 400}

        cfg = comp["config"]
        assert cfg["filename"] == "/data/output.pos"
        assert cfg["row_separator"] == "\\r\\n"
        assert cfg["append"] is True
        assert cfg["include_header"] is True
        assert cfg["compress"] is True
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["create"] is False
        assert cfg["flush_on_row"] is True
        assert cfg["flush_on_row_num"] == 100
        assert cfg["delete_empty_file"] is True
        assert cfg["die_on_error"] is False
        assert cfg["formats"] == []

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={
            "FILENAME": '"/data/file.pos"',
        })
        result = FileOutputPositionalConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/file.pos"
        assert cfg["row_separator"] == "\\n"
        assert cfg["append"] is False
        assert cfg["include_header"] is False
        assert cfg["compress"] is False
        assert cfg["encoding"] == "UTF-8"
        assert cfg["create"] is True
        assert cfg["flush_on_row"] is False
        assert cfg["flush_on_row_num"] == 1
        assert cfg["delete_empty_file"] is False
        assert cfg["die_on_error"] is True
        assert cfg["formats"] == []

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_no_warning_when_filename_present(self):
        """No warning when FILENAME is provided."""
        node = _make_node(params={"FILENAME": '"/data/output.pos"'})
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert len(result.warnings) == 0

    def test_formats_table_parsing(self):
        """FORMATS TABLE param is parsed into a list of format dicts."""
        node = _make_node(params={
            "FILENAME": '"/data/output.pos"',
            "FORMATS": [
                {
                    "SCHEMA_COLUMN": "id",
                    "size": "10",
                    "padding_char": " ",
                    "align": "RIGHT",
                },
                {
                    "SCHEMA_COLUMN": "name",
                    "size": "30",
                    "padding_char": " ",
                    "align": "LEFT",
                },
                {
                    "SCHEMA_COLUMN": "amount",
                    "size": "15",
                    "padding_char": "0",
                    "align": "RIGHT",
                },
            ],
        })
        result = FileOutputPositionalConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert len(cfg["formats"]) == 3

        assert cfg["formats"][0]["schema_column"] == "id"
        assert cfg["formats"][0]["size"] == "10"
        assert cfg["formats"][0]["padding_char"] == " "
        assert cfg["formats"][0]["align"] == "RIGHT"

        assert cfg["formats"][1]["schema_column"] == "name"
        assert cfg["formats"][1]["size"] == "30"
        assert cfg["formats"][1]["align"] == "LEFT"

        assert cfg["formats"][2]["schema_column"] == "amount"
        assert cfg["formats"][2]["size"] == "15"
        assert cfg["formats"][2]["padding_char"] == "0"
        assert cfg["formats"][2]["align"] == "RIGHT"

    def test_formats_partial_entries(self):
        """FORMATS entries with only some fields still get parsed."""
        node = _make_node(params={
            "FILENAME": '"/data/output.pos"',
            "FORMATS": [
                {"SCHEMA_COLUMN": "code", "size": "5"},
            ],
        })
        result = FileOutputPositionalConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert len(cfg["formats"]) == 1
        assert cfg["formats"][0]["schema_column"] == "code"
        assert cfg["formats"][0]["size"] == "5"
        assert "padding_char" not in cfg["formats"][0]
        assert "align" not in cfg["formats"][0]

    def test_schema_parsed_into_input(self):
        """Schema columns appear under schema.input for this output component."""
        node = _make_node(
            params={"FILENAME": '"/data/output.pos"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
                    SchemaColumn(name="name", type="id_String", nullable=True, length=50),
                    SchemaColumn(
                        name="created",
                        type="id_Date",
                        date_pattern="yyyy-MM-dd",
                    ),
                ]
            },
        )
        result = FileOutputPositionalConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["output"] == []
        assert len(schema["input"]) == 3

        assert schema["input"][0]["name"] == "id"
        assert schema["input"][0]["type"] == "int"
        assert schema["input"][0]["nullable"] is False
        assert schema["input"][0]["key"] is True

        assert schema["input"][1]["name"] == "name"
        assert schema["input"][1]["type"] == "str"
        assert schema["input"][1]["length"] == 50

        assert schema["input"][2]["name"] == "created"
        assert schema["input"][2]["date_pattern"] == "%Y-%m-%d"

    def test_output_schema_always_empty(self):
        """FileOutputPositional is a sink — output schema must be empty."""
        node = _make_node(params={"FILENAME": '"/data/out.pos"'})
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"FILENAME": '"/data/out.pos"'})
        result = FileOutputPositionalConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={"FILENAME": '"/data/out.pos"'})
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registry_lookup(self):
        """The converter is registered under 'tFileOutputPositional'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFileOutputPositional")
        assert cls is FileOutputPositionalConverter

    def test_boolean_params_from_strings(self):
        """Boolean params accept various string representations."""
        node = _make_node(params={
            "FILENAME": '"/data/out.pos"',
            "APPEND": "true",
            "INCLUDEHEADER": "1",
            "COMPRESS": "false",
            "CREATE": "0",
            "FLUSHONROW": "true",
            "DELETE_EMPTYFILE": "false",
            "DIE_ON_ERROR": "true",
        })
        result = FileOutputPositionalConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["append"] is True
        assert cfg["include_header"] is True
        assert cfg["compress"] is False
        assert cfg["create"] is False
        assert cfg["flush_on_row"] is True
        assert cfg["delete_empty_file"] is False
        assert cfg["die_on_error"] is True

    def test_int_params_from_quoted_strings(self):
        """Integer params handle quoted string values."""
        node = _make_node(params={
            "FILENAME": '"/data/out.pos"',
            "FLUSHONROW_NUM": '"50"',
        })
        result = FileOutputPositionalConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["flush_on_row_num"] == 50
