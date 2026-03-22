"""Tests for tFileInputPositional -> FileInputPositional converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_positional import (
    FileInputPositionalConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tFileInputPositional_1",
        component_type="tFileInputPositional",
        params=params or {},
        schema=schema or {},
        position={"x": 160, "y": 320},
    )


class TestFileInputPositionalConverter:
    """Tests for FileInputPositionalConverter."""

    def test_basic_config_all_17_params(self):
        """All 17 config params are extracted and quote-stripped correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/fixed_width.dat"',
            "ROWSEPARATOR": '"\\n"',
            "PATTERN": '"5,10,15,20"',
            "PATTERN_UNITS": '"SYMBOLS"',
            "REMOVE_EMPTY_ROW": "true",
            "TRIMALL": "true",
            "ENCODING": '"ISO-8859-1"',
            "HEADER": "2",
            "FOOTER": "1",
            "LIMIT": "5000",
            "DIE_ON_ERROR": "true",
            "PROCESS_LONG_ROW": "true",
            "ADVANCED_SEPARATOR": "true",
            "THOUSANDS_SEPARATOR": '"."',
            "DECIMAL_SEPARATOR": '","',
            "CHECK_DATE": "true",
            "UNCOMPRESS": "true",
        })
        result = FileInputPositionalConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "FileInputPositional"
        assert comp["original_type"] == "tFileInputPositional"
        assert comp["id"] == "tFileInputPositional_1"
        assert comp["position"] == {"x": 160, "y": 320}

        cfg = comp["config"]
        assert cfg["filepath"] == "/data/fixed_width.dat"
        assert cfg["row_separator"] == "\\n"
        assert cfg["pattern"] == "5,10,15,20"
        assert cfg["pattern_units"] == "SYMBOLS"
        assert cfg["remove_empty_row"] is True
        assert cfg["trim_all"] is True
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["header_rows"] == 2
        assert cfg["footer_rows"] == 1
        assert cfg["limit"] == 5000
        assert cfg["die_on_error"] is True
        assert cfg["process_long_row"] is True
        assert cfg["advanced_separator"] is True
        assert cfg["thousands_separator"] == "."
        assert cfg["decimal_separator"] == ","
        assert cfg["check_date"] is True
        assert cfg["uncompress"] is True

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={
            "FILENAME": '"/data/file.dat"',
            "PATTERN": '"10,20"',
        })
        result = FileInputPositionalConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filepath"] == "/data/file.dat"
        assert cfg["row_separator"] == "\\n"
        assert cfg["pattern"] == "10,20"
        assert cfg["pattern_units"] == "SYMBOLS"
        assert cfg["remove_empty_row"] is False
        assert cfg["trim_all"] is False
        assert cfg["encoding"] == "UTF-8"
        assert cfg["header_rows"] == 0
        assert cfg["footer_rows"] == 0
        assert cfg["limit"] == 0
        assert cfg["die_on_error"] is False
        assert cfg["process_long_row"] is False
        assert cfg["advanced_separator"] is False
        assert cfg["thousands_separator"] == ","
        assert cfg["decimal_separator"] == "."
        assert cfg["check_date"] is False
        assert cfg["uncompress"] is False

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={"PATTERN": '"5,10"'})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_empty_pattern_produces_warning(self):
        """An empty PATTERN triggers a warning."""
        node = _make_node(params={"FILENAME": '"/data/file.dat"'})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert any("PATTERN" in w for w in result.warnings)

    def test_schema_parsed(self):
        """Schema columns are parsed into output schema dicts."""
        node = _make_node(
            params={
                "FILENAME": '"test.dat"',
                "PATTERN": '"5,10,8"',
            },
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", key=False, length=50),
                    SchemaColumn(
                        name="created",
                        type="id_Date",
                        date_pattern="yyyy-MM-dd",
                    ),
                ]
            },
        )
        result = FileInputPositionalConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 3
        assert output_schema[0]["name"] == "id"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[1]["name"] == "name"
        assert output_schema[1]["length"] == 50
        assert output_schema[2]["name"] == "created"
        assert output_schema[2]["date_pattern"] == "%Y-%m-%d"

    def test_input_schema_always_empty(self):
        """FileInputPositional is a source — input schema must be empty."""
        node = _make_node(params={
            "FILENAME": '"x.dat"',
            "PATTERN": '"5"',
        })
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_boolean_params_from_strings(self):
        """Boolean params accept string representations."""
        node = _make_node(params={
            "FILENAME": '"data.dat"',
            "PATTERN": '"10"',
            "REMOVE_EMPTY_ROW": "true",
            "TRIMALL": "1",
            "DIE_ON_ERROR": "false",
            "PROCESS_LONG_ROW": "true",
            "ADVANCED_SEPARATOR": "false",
            "CHECK_DATE": "1",
            "UNCOMPRESS": "false",
        })
        result = FileInputPositionalConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["remove_empty_row"] is True
        assert cfg["trim_all"] is True
        assert cfg["die_on_error"] is False
        assert cfg["process_long_row"] is True
        assert cfg["advanced_separator"] is False
        assert cfg["check_date"] is True
        assert cfg["uncompress"] is False

    def test_int_params_from_quoted_strings(self):
        """Integer params handle quoted string values."""
        node = _make_node(params={
            "FILENAME": '"data.dat"',
            "PATTERN": '"5,10"',
            "HEADER": '"3"',
            "FOOTER": '"1"',
            "LIMIT": '"250"',
        })
        result = FileInputPositionalConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["header_rows"] == 3
        assert cfg["footer_rows"] == 1
        assert cfg["limit"] == 250

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={
            "FILENAME": '"f.dat"',
            "PATTERN": '"5"',
        })
        result = FileInputPositionalConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={
            "FILENAME": '"f.dat"',
            "PATTERN": '"5"',
        })
        result = FileInputPositionalConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_registry_lookup(self):
        """The converter is registered under 'tFileInputPositional'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFileInputPositional")
        assert cls is FileInputPositionalConverter
