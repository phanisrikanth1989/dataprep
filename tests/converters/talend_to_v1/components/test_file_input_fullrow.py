"""Tests for tFileInputFullRow -> FileInputFullRowComponent converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_fullrow import (
    FileInputFullRowConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tFileInputFullRow_1",
        component_type="tFileInputFullRow",
        params=params or {},
        schema=schema or {},
        position={"x": 120, "y": 240},
    )


class TestFileInputFullRowConverter:
    """Tests for FileInputFullRowConverter."""

    def test_basic_config_all_params(self):
        """All 12 config params are extracted correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/input.txt"',
            "ROWSEPARATOR": '"\\n"',
            "REMOVE_EMPTY_ROW": "false",
            "ENCODING": '"ISO-8859-1"',
            "LIMIT": '"500"',
            "HEADER": "3",
            "FOOTER": "2",
            "DIE_ON_ERROR": "false",
            "RANDOM": "true",
            "NB_RANDOM": "25",
            "TSTATCATCHER_STATS": "true",
            "LABEL": '"my_label"',
        })
        result = FileInputFullRowConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "FileInputFullRowComponent"
        assert comp["original_type"] == "tFileInputFullRow"
        assert comp["id"] == "tFileInputFullRow_1"
        assert comp["position"] == {"x": 120, "y": 240}

        cfg = comp["config"]
        assert cfg["filename"] == "/data/input.txt"
        assert cfg["row_separator"] == "\\n"
        assert cfg["remove_empty_row"] is False
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["limit"] == "500"
        assert cfg["header_rows"] == 3
        assert cfg["footer_rows"] == 2
        assert cfg["die_on_error"] is False
        assert cfg["random"] is True
        assert cfg["nb_random"] == 25
        assert cfg["tstatcatcher_stats"] is True
        assert cfg["label"] == "my_label"

    def test_defaults_when_params_missing(self):
        """Missing params fall back to correct Talend defaults."""
        node = _make_node(params={"FILENAME": '"/data/file.txt"'})
        result = FileInputFullRowConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/file.txt"
        assert cfg["row_separator"] == "\\n"
        assert cfg["remove_empty_row"] is True
        assert cfg["encoding"] == "ISO-8859-15"
        assert cfg["limit"] == ""
        assert cfg["header_rows"] == 0
        assert cfg["footer_rows"] == 0
        assert cfg["die_on_error"] is True
        assert cfg["random"] is False
        assert cfg["nb_random"] == 10
        assert cfg["tstatcatcher_stats"] is False
        assert cfg["label"] == ""

    def test_all_config_keys_present(self):
        """Exactly 12 config keys should be present."""
        node = _make_node(params={"FILENAME": '"/data/file.txt"'})
        result = FileInputFullRowConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected = {
            "filename", "row_separator", "remove_empty_row", "encoding", "limit",
            "header_rows", "footer_rows", "die_on_error", "random", "nb_random",
            "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected

    def test_limit_extracted_as_string(self):
        """LIMIT must be string type (engine calls .isdigit() on it)."""
        node = _make_node(params={
            "FILENAME": '"/data/file.txt"',
            "LIMIT": '"100"',
        })
        result = FileInputFullRowConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["limit"] == "100"
        assert isinstance(cfg["limit"], str)

    def test_limit_default_is_empty_string(self):
        """Default LIMIT is empty string (unlimited reading)."""
        node = _make_node(params={"FILENAME": '"/data/file.txt"'})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == ""

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_engine_gap_warning_header(self):
        """header_rows > 0 triggers engine-gap warning."""
        node = _make_node(params={
            "FILENAME": '"/data/file.txt"',
            "HEADER": "5",
        })
        result = FileInputFullRowConverter().convert(node, [], {})
        assert any("HEADER=5" in w for w in result.warnings)

    def test_engine_gap_warning_footer(self):
        """footer_rows > 0 triggers engine-gap warning."""
        node = _make_node(params={
            "FILENAME": '"/data/file.txt"',
            "FOOTER": "3",
        })
        result = FileInputFullRowConverter().convert(node, [], {})
        assert any("FOOTER=3" in w for w in result.warnings)

    def test_engine_gap_warning_random(self):
        """random=true triggers engine-gap warning."""
        node = _make_node(params={
            "FILENAME": '"/data/file.txt"',
            "RANDOM": "true",
        })
        result = FileInputFullRowConverter().convert(node, [], {})
        assert any("RANDOM=true" in w for w in result.warnings)

    def test_engine_gap_warning_column_name(self):
        """Schema column name != 'line' triggers warning."""
        node = _make_node(
            params={"FILENAME": '"/data/file.txt"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="data", type="id_String"),
                ]
            },
        )
        result = FileInputFullRowConverter().convert(node, [], {})
        assert any("hardcodes output column name" in w and "data" in w for w in result.warnings)

    def test_no_column_warning_for_default_schema(self):
        """Default schema column 'line' does NOT trigger column warning."""
        node = _make_node(
            params={"FILENAME": '"/data/file.txt"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="line", type="id_String"),
                ]
            },
        )
        result = FileInputFullRowConverter().convert(node, [], {})
        assert not any("hardcodes output column name" in w for w in result.warnings)

    def test_no_engine_warnings_on_defaults(self):
        """Defaults produce no engine-gap warnings."""
        node = _make_node(
            params={"FILENAME": '"/data/file.txt"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="line", type="id_String"),
                ]
            },
        )
        result = FileInputFullRowConverter().convert(node, [], {})
        assert len(result.warnings) == 0

    def test_schema_parsed(self):
        """Schema columns are parsed into output schema dicts."""
        node = _make_node(
            params={"FILENAME": '"test.txt"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="line", type="id_String", key=False, length=2000),
                    SchemaColumn(
                        name="timestamp",
                        type="id_Date",
                        date_pattern="yyyy-MM-dd HH:mm:ss",
                    ),
                ]
            },
        )
        result = FileInputFullRowConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 2
        assert output_schema[0]["name"] == "line"
        assert output_schema[0]["length"] == 2000
        assert output_schema[1]["name"] == "timestamp"
        assert output_schema[1]["date_pattern"] == "%Y-%m-%d %H:%M:%S"

    def test_input_schema_always_empty(self):
        """FileInputFullRow is a source -- input schema must be empty."""
        node = _make_node(params={"FILENAME": '"x.txt"'})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_boolean_params_from_strings(self):
        """Boolean params accept string representations."""
        node = _make_node(params={
            "FILENAME": '"data.txt"',
            "REMOVE_EMPTY_ROW": "false",
            "DIE_ON_ERROR": "false",
            "RANDOM": "1",
            "TSTATCATCHER_STATS": "true",
        })
        result = FileInputFullRowConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["remove_empty_row"] is False
        assert cfg["die_on_error"] is False
        assert cfg["random"] is True
        assert cfg["tstatcatcher_stats"] is True

    def test_int_params_from_quoted_strings(self):
        """Integer params handle quoted string values."""
        node = _make_node(params={
            "FILENAME": '"data.txt"',
            "HEADER": '"3"',
            "FOOTER": '"1"',
            "NB_RANDOM": '"50"',
        })
        result = FileInputFullRowConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["header_rows"] == 3
        assert cfg["footer_rows"] == 1
        assert cfg["nb_random"] == 50

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"FILENAME": '"f.txt"'})
        result = FileInputFullRowConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={"FILENAME": '"f.txt"'})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registry_lookup(self):
        """The converter is registered under 'tFileInputFullRow'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFileInputFullRow")
        assert cls is FileInputFullRowConverter
