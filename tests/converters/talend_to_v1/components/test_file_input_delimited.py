"""Tests for tFileInputDelimited -> FileInputDelimited converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_delimited import (
    FileInputDelimitedConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tFileInputDelimited_1",
        component_type="tFileInputDelimited",
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
    )


class TestFileInputDelimitedConverter:
    """Tests for FileInputDelimitedConverter."""

    def test_basic_config(self):
        """Config params are extracted and quote-stripped correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/input.csv"',
            "FIELDSEPARATOR": '","',
            "ROWSEPARATOR": '"\\n"',
            "HEADER": "1",
            "FOOTER": "0",
            "LIMIT": "1000",
            "ENCODING": '"UTF-8"',
            "TEXT_ENCLOSURE": '"\\""',
            "ESCAPE_CHAR": '"\\\\"',
            "REMOVE_EMPTY_ROW": "true",
            "TRIMALL": "false",
            "DIE_ON_ERROR": True,
        })
        result = FileInputDelimitedConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "FileInputDelimited"
        assert comp["original_type"] == "tFileInputDelimited"
        assert comp["id"] == "tFileInputDelimited_1"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["filepath"] == "/data/input.csv"
        assert cfg["delimiter"] == ","
        assert cfg["row_separator"] == "\\n"
        assert cfg["header_rows"] == 1
        assert cfg["footer_rows"] == 0
        assert cfg["limit"] == 1000
        assert cfg["encoding"] == "UTF-8"
        assert cfg["text_enclosure"] == '\\"'
        assert cfg["escape_char"] == "\\\\"
        assert cfg["remove_empty_rows"] is True
        assert cfg["trim_all"] is False
        assert cfg["die_on_error"] is True

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={"FILENAME": '"/data/file.csv"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filepath"] == "/data/file.csv"
        assert cfg["delimiter"] == ","
        assert cfg["row_separator"] == "\\n"
        assert cfg["header_rows"] == 0
        assert cfg["footer_rows"] == 0
        assert cfg["limit"] == 0
        assert cfg["encoding"] == "UTF-8"
        assert cfg["text_enclosure"] == ""
        assert cfg["escape_char"] == ""
        assert cfg["remove_empty_rows"] is False
        assert cfg["trim_all"] is False
        assert cfg["die_on_error"] is False

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_schema_parsed(self):
        """Schema columns are parsed into output schema dicts."""
        node = _make_node(
            params={"FILENAME": '"test.csv"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", key=False, length=100),
                    SchemaColumn(
                        name="created",
                        type="id_Date",
                        date_pattern="yyyy-MM-dd",
                    ),
                ]
            },
        )
        result = FileInputDelimitedConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 3
        assert output_schema[0]["name"] == "id"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[1]["name"] == "name"
        assert output_schema[1]["length"] == 100
        assert output_schema[2]["name"] == "created"
        # date_pattern should be converted from Java to Python format
        assert output_schema[2]["date_pattern"] == "%Y-%m-%d"

    def test_input_schema_always_empty(self):
        """FileInputDelimited is a source — input schema must be empty."""
        node = _make_node(params={"FILENAME": '"x.csv"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_boolean_params_from_strings(self):
        """Boolean params accept string representations."""
        node = _make_node(params={
            "FILENAME": '"data.csv"',
            "REMOVE_EMPTY_ROW": "true",
            "TRIMALL": "1",
            "DIE_ON_ERROR": "false",
        })
        result = FileInputDelimitedConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["remove_empty_rows"] is True
        assert cfg["trim_all"] is True
        assert cfg["die_on_error"] is False

    def test_int_params_from_quoted_strings(self):
        """Integer params handle quoted string values."""
        node = _make_node(params={
            "FILENAME": '"data.csv"',
            "HEADER": '"5"',
            "FOOTER": '"2"',
            "LIMIT": '"500"',
        })
        result = FileInputDelimitedConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["header_rows"] == 5
        assert cfg["footer_rows"] == 2
        assert cfg["limit"] == 500

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={"FILENAME": '"f.csv"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"FILENAME": '"f.csv"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_registry_lookup(self):
        """The converter is registered under 'tFileInputDelimited'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFileInputDelimited")
        assert cls is FileInputDelimitedConverter
