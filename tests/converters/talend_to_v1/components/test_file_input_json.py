"""Tests for tFileInputJSON -> FileInputJSON converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_json import (
    FileInputJSONConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tFileInputJSON_1",
        component_type="tFileInputJSON",
        params=params or {},
        schema=schema or {},
        position={"x": 120, "y": 340},
    )


class TestFileInputJSONConverter:
    """Tests for FileInputJSONConverter."""

    def test_type_name_is_file_input_json_not_component(self):
        """CONV-NAME-002: type must be 'FileInputJSON', NOT 'FileInputJSONComponent'."""
        node = _make_node(params={
            "FILENAME": '"/data/input.json"',
            "JSON_LOOP_QUERY": '"$.records"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "FileInputJSON"
        assert comp["type"] != "FileInputJSONComponent"
        assert comp["original_type"] == "tFileInputJSON"

    def test_basic_config(self):
        """Config params are extracted and quote-stripped correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/input.json"',
            "JSON_LOOP_QUERY": '"$.store.book[*]"',
            "MAPPING_JSONPATH": [
                {"elementRef": "title", "value": "$.title"},
                {"elementRef": "price", "value": "$.price"},
            ],
            "DIE_ON_ERROR": "true",
            "ENCODING": '"ISO-8859-1"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        comp = result.component

        assert comp["id"] == "tFileInputJSON_1"
        assert comp["type"] == "FileInputJSON"
        assert comp["position"] == {"x": 120, "y": 340}

        cfg = comp["config"]
        assert cfg["filename"] == "/data/input.json"
        assert cfg["json_loop_query"] == "$.store.book[*]"
        assert cfg["die_on_error"] is True
        assert cfg["encoding"] == "ISO-8859-1"
        assert len(cfg["mapping"]) == 2
        assert cfg["mapping"][0] == {"column": "title", "jsonpath": "$.title"}
        assert cfg["mapping"][1] == {"column": "price", "jsonpath": "$.price"}

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={
            "FILENAME": '"/data/file.json"',
            "JSON_LOOP_QUERY": '"$"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/file.json"
        assert cfg["json_loop_query"] == "$"
        assert cfg["mapping"] == []
        assert cfg["die_on_error"] is False
        assert cfg["encoding"] == "UTF-8"

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={})
        result = FileInputJSONConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_empty_json_loop_query_produces_warning(self):
        """An empty JSON_LOOP_QUERY triggers a warning."""
        node = _make_node(params={"FILENAME": '"/data/f.json"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert any("JSON_LOOP_QUERY" in w for w in result.warnings)

    def test_mapping_empty_when_no_table(self):
        """mapping is an empty list when MAPPING_JSONPATH is absent."""
        node = _make_node(params={
            "FILENAME": '"/data/f.json"',
            "JSON_LOOP_QUERY": '"$"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    def test_schema_parsed(self):
        """Schema columns are parsed into output schema dicts."""
        node = _make_node(
            params={
                "FILENAME": '"test.json"',
                "JSON_LOOP_QUERY": '"$.items[*]"',
            },
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", key=False, length=200),
                    SchemaColumn(
                        name="created",
                        type="id_Date",
                        date_pattern="yyyy-MM-dd HH:mm:ss",
                    ),
                ]
            },
        )
        result = FileInputJSONConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 3
        assert output_schema[0]["name"] == "id"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[1]["name"] == "name"
        assert output_schema[1]["length"] == 200
        assert output_schema[2]["name"] == "created"
        assert output_schema[2]["date_pattern"] == "%Y-%m-%d %H:%M:%S"

    def test_input_schema_always_empty(self):
        """FileInputJSON is a source — input schema must be empty."""
        node = _make_node(params={
            "FILENAME": '"x.json"',
            "JSON_LOOP_QUERY": '"$"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={"FILENAME": '"f.json"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"FILENAME": '"f.json"'})
        result = FileInputJSONConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_registry_lookup(self):
        """The converter is registered under 'tFileInputJSON'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFileInputJSON")
        assert cls is FileInputJSONConverter

    def test_boolean_die_on_error_from_string(self):
        """DIE_ON_ERROR handles string 'false' correctly."""
        node = _make_node(params={
            "FILENAME": '"data.json"',
            "JSON_LOOP_QUERY": '"$"',
            "DIE_ON_ERROR": "false",
        })
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False
