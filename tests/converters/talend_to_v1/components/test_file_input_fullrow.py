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

    def test_basic_config(self):
        """Config params are extracted and quote-stripped correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/input.txt"',
            "ROWSEPARATOR": '"\\n"',
            "REMOVE_EMPTY_ROW": "true",
            "ENCODING": '"UTF-8"',
            "LIMIT": "500",
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
        assert cfg["remove_empty_row"] is True
        assert cfg["encoding"] == "UTF-8"
        assert cfg["limit"] == 500

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={"FILENAME": '"/data/file.txt"'})
        result = FileInputFullRowConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/file.txt"
        assert cfg["row_separator"] == "\\n"
        assert cfg["remove_empty_row"] is False
        assert cfg["encoding"] == "UTF-8"
        assert cfg["limit"] == 0

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={})
        result = FileInputFullRowConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

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

    def test_boolean_params_from_strings(self):
        """Boolean params accept string representations."""
        node = _make_node(params={
            "FILENAME": '"data.txt"',
            "REMOVE_EMPTY_ROW": "1",
        })
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["remove_empty_row"] is True

        node2 = _make_node(params={
            "FILENAME": '"data.txt"',
            "REMOVE_EMPTY_ROW": "false",
        })
        result2 = FileInputFullRowConverter().convert(node2, [], {})
        assert result2.component["config"]["remove_empty_row"] is False

    def test_int_limit_from_quoted_string(self):
        """Integer LIMIT param handles quoted string values."""
        node = _make_node(params={
            "FILENAME": '"data.txt"',
            "LIMIT": '"1000"',
        })
        result = FileInputFullRowConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == 1000

    def test_registry_lookup(self):
        """The converter is registered under 'tFileInputFullRow'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFileInputFullRow")
        assert cls is FileInputFullRowConverter
