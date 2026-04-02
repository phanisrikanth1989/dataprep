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

    def test_type_name_is_file_input_json(self):
        """Type must be 'FileInputJSON', NOT 'FileInputJSONComponent'."""
        node = _make_node(params={
            "FILENAME": '"/data/input.json"',
            "JSON_LOOP_QUERY": '"$.records"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["type"] == "FileInputJSON"

    def test_basic_config_all_params(self):
        """All 17 config params are extracted correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/input.json"',
            "JSON_LOOP_QUERY": '"$.store.book[*]"',
            "LOOP_QUERY": '"/store/book"',
            "READ_BY": '"JSONPATH"',
            "JSON_PATH_VERSION": '"2_1_0"',
            "MAPPING_JSONPATH": [
                {"elementRef": "SCHEMA_COLUMN", "value": "title"},
                {"elementRef": "QUERY", "value": '"$.title"'},
                {"elementRef": "SCHEMA_COLUMN", "value": "price"},
                {"elementRef": "QUERY", "value": '"$.price"'},
            ],
            "USEURL": "false",
            "URLPATH": '"http://example.com/api"',
            "USE_LOOP_AS_ROOT": "true",
            "DIE_ON_ERROR": "true",
            "ENCODING": '"ISO-8859-1"',
            "ADVANCED_SEPARATOR": "true",
            "THOUSANDS_SEPARATOR": '"."',
            "DECIMAL_SEPARATOR": '","',
            "CHECK_DATE": "true",
            "TSTATCATCHER_STATS": "true",
            "LABEL": '"json_reader"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/input.json"
        assert cfg["json_loop_query"] == "$.store.book[*]"
        assert cfg["loop_query"] == "/store/book"
        assert cfg["read_by"] == "JSONPATH"
        assert cfg["json_path_version"] == "2_1_0"
        assert len(cfg["mapping"]) == 2
        assert cfg["mapping"][0] == {"column": "title", "jsonpath": "$.title"}
        assert cfg["mapping"][1] == {"column": "price", "jsonpath": "$.price"}
        assert cfg["useurl"] is False
        assert cfg["urlpath"] == "http://example.com/api"
        assert cfg["use_loop_as_root"] is True
        assert cfg["die_on_error"] is True
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["advanced_separator"] is True
        assert cfg["thousands_separator"] == "."
        assert cfg["decimal_separator"] == ","
        assert cfg["check_date"] is True
        assert cfg["tstatcatcher_stats"] is True
        assert cfg["label"] == "json_reader"

    def test_defaults_when_params_missing(self):
        """Missing params fall back to correct defaults."""
        node = _make_node(params={
            "FILENAME": '"/data/file.json"',
            "JSON_LOOP_QUERY": '"$"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/file.json"
        assert cfg["json_loop_query"] == "$"
        assert cfg["loop_query"] == ""
        assert cfg["read_by"] == "JSONPATH"
        assert cfg["json_path_version"] == "2_1_0"
        assert cfg["mapping"] == []
        assert cfg["useurl"] is False
        assert cfg["urlpath"] == ""
        assert cfg["use_loop_as_root"] is True
        assert cfg["die_on_error"] is False
        assert cfg["encoding"] == "UTF-8"
        assert cfg["advanced_separator"] is False
        assert cfg["thousands_separator"] == ","
        assert cfg["decimal_separator"] == "."
        assert cfg["check_date"] is False
        assert cfg["tstatcatcher_stats"] is False
        assert cfg["label"] == ""

    def test_all_config_keys_present(self):
        """Exactly 17 config keys should be present."""
        node = _make_node(params={
            "FILENAME": '"/data/file.json"',
            "JSON_LOOP_QUERY": '"$"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected = {
            "filename", "json_loop_query", "loop_query", "read_by",
            "json_path_version", "mapping", "useurl", "urlpath",
            "use_loop_as_root", "die_on_error", "encoding",
            "advanced_separator", "thousands_separator", "decimal_separator",
            "check_date", "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected

    def test_mapping_jsonpath_mode(self):
        """JSONPATH mode extracts MAPPING_JSONPATH with alternating SCHEMA_COLUMN/QUERY pairs."""
        node = _make_node(params={
            "FILENAME": '"/data/file.json"',
            "JSON_LOOP_QUERY": '"$.items[*]"',
            "READ_BY": '"JSONPATH"',
            "MAPPING_JSONPATH": [
                {"elementRef": "SCHEMA_COLUMN", "value": "id"},
                {"elementRef": "QUERY", "value": '"$.id"'},
                {"elementRef": "SCHEMA_COLUMN", "value": "name"},
                {"elementRef": "QUERY", "value": '"$.name"'},
                {"elementRef": "SCHEMA_COLUMN", "value": "email"},
                {"elementRef": "QUERY", "value": '"$.contact.email"'},
            ],
        })
        result = FileInputJSONConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]

        assert len(mapping) == 3
        assert mapping[0] == {"column": "id", "jsonpath": "$.id"}
        assert mapping[1] == {"column": "name", "jsonpath": "$.name"}
        assert mapping[2] == {"column": "email", "jsonpath": "$.contact.email"}
        # No nodecheck in JSONPATH mode
        assert "nodecheck" not in mapping[0]

    def test_mapping_xpath_mode(self):
        """XPATH mode extracts MAPPINGXPATH with SCHEMA_COLUMN/QUERY/NODECHECK triplets."""
        node = _make_node(params={
            "FILENAME": '"/data/file.json"',
            "LOOP_QUERY": '"/data/item"',
            "READ_BY": '"XPATH"',
            "MAPPINGXPATH": [
                {"elementRef": "SCHEMA_COLUMN", "value": "id"},
                {"elementRef": "QUERY", "value": '"@id"'},
                {"elementRef": "NODECHECK", "value": "false"},
                {"elementRef": "SCHEMA_COLUMN", "value": "content"},
                {"elementRef": "QUERY", "value": '"."'},
                {"elementRef": "NODECHECK", "value": "true"},
            ],
        })
        result = FileInputJSONConverter().convert(node, [], {})
        cfg = result.component["config"]
        mapping = cfg["mapping"]

        assert cfg["read_by"] == "XPATH"
        assert cfg["loop_query"] == "/data/item"
        assert len(mapping) == 2
        assert mapping[0] == {"column": "id", "jsonpath": "@id", "nodecheck": False}
        assert mapping[1] == {"column": "content", "jsonpath": ".", "nodecheck": True}
        # JSON_LOOP_QUERY warning should NOT fire in XPATH mode (uses LOOP_QUERY instead)
        assert not any("JSON_LOOP_QUERY" in w for w in result.warnings)

    def test_mapping_no_loop_mode(self):
        """JSONPATH_WITHOUTPUT_LOOP mode extracts MAPPING table."""
        node = _make_node(params={
            "FILENAME": '"/data/file.json"',
            "READ_BY": '"JSONPATH_WITHOUTPUT_LOOP"',
            "MAPPING": [
                {"elementRef": "SCHEMA_COLUMN", "value": "id"},
                {"elementRef": "QUERY", "value": '"$.id"'},
                {"elementRef": "SCHEMA_COLUMN", "value": "name"},
                {"elementRef": "QUERY", "value": '"$.first_name"'},
            ],
        })
        result = FileInputJSONConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]

        assert len(mapping) == 2
        assert mapping[0] == {"column": "id", "jsonpath": "$.id"}
        assert mapping[1] == {"column": "name", "jsonpath": "$.first_name"}
        assert "nodecheck" not in mapping[0]

    def test_mapping_partial_entries(self):
        """Trailing SCHEMA_COLUMN without QUERY gets empty jsonpath."""
        node = _make_node(params={
            "FILENAME": '"/data/file.json"',
            "JSON_LOOP_QUERY": '"$"',
            "MAPPING_JSONPATH": [
                {"elementRef": "SCHEMA_COLUMN", "value": "complete"},
                {"elementRef": "QUERY", "value": '"$.complete"'},
                {"elementRef": "SCHEMA_COLUMN", "value": "orphan"},
            ],
        })
        result = FileInputJSONConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]

        assert len(mapping) == 2
        assert mapping[0] == {"column": "complete", "jsonpath": "$.complete"}
        assert mapping[1] == {"column": "orphan", "jsonpath": ""}

    def test_mapping_empty_when_no_table(self):
        """mapping is an empty list when the active table is absent."""
        node = _make_node(params={
            "FILENAME": '"/data/f.json"',
            "JSON_LOOP_QUERY": '"$"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={})
        result = FileInputJSONConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_empty_json_loop_query_produces_warning(self):
        """An empty JSON_LOOP_QUERY triggers a warning in JSONPATH mode."""
        node = _make_node(params={"FILENAME": '"/data/f.json"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert any("JSON_LOOP_QUERY" in w for w in result.warnings)

    def test_no_loop_query_warning_in_no_loop_mode(self):
        """JSONPATH_WITHOUTPUT_LOOP mode does NOT warn about empty loop query."""
        node = _make_node(params={
            "FILENAME": '"/data/f.json"',
            "READ_BY": '"JSONPATH_WITHOUTPUT_LOOP"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        assert not any("JSON_LOOP_QUERY" in w for w in result.warnings)

    def test_engine_gap_warning_xpath_mode(self):
        """READ_BY=XPATH triggers engine-gap warning."""
        node = _make_node(params={
            "FILENAME": '"/data/f.json"',
            "READ_BY": '"XPATH"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        assert any("READ_BY=XPATH" in w for w in result.warnings)

    def test_engine_gap_warning_no_loop_mode(self):
        """READ_BY=JSONPATH_WITHOUTPUT_LOOP triggers engine-gap warning."""
        node = _make_node(params={
            "FILENAME": '"/data/f.json"',
            "READ_BY": '"JSONPATH_WITHOUTPUT_LOOP"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        assert any("JSONPATH_WITHOUTPUT_LOOP" in w for w in result.warnings)

    def test_engine_gap_warning_check_date(self):
        """CHECK_DATE=true triggers engine-gap warning."""
        node = _make_node(params={
            "FILENAME": '"/data/f.json"',
            "JSON_LOOP_QUERY": '"$"',
            "CHECK_DATE": "true",
        })
        result = FileInputJSONConverter().convert(node, [], {})
        assert any("CHECK_DATE=true" in w for w in result.warnings)

    def test_engine_gap_warning_useurl(self):
        """USEURL=true triggers engine-gap warning."""
        node = _make_node(params={
            "FILENAME": '"/data/f.json"',
            "JSON_LOOP_QUERY": '"$"',
            "USEURL": "true",
        })
        result = FileInputJSONConverter().convert(node, [], {})
        assert any("USEURL=true" in w for w in result.warnings)

    def test_no_engine_warnings_on_defaults(self):
        """Defaults produce no engine-gap warnings."""
        node = _make_node(params={
            "FILENAME": '"/data/f.json"',
            "JSON_LOOP_QUERY": '"$"',
        })
        result = FileInputJSONConverter().convert(node, [], {})
        assert len(result.warnings) == 0

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

    def test_boolean_params_from_strings(self):
        """Boolean params accept string representations."""
        node = _make_node(params={
            "FILENAME": '"data.json"',
            "JSON_LOOP_QUERY": '"$"',
            "DIE_ON_ERROR": "false",
            "USEURL": "false",
            "USE_LOOP_AS_ROOT": "false",
            "ADVANCED_SEPARATOR": "1",
            "CHECK_DATE": "true",
            "TSTATCATCHER_STATS": "true",
        })
        result = FileInputJSONConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["die_on_error"] is False
        assert cfg["useurl"] is False
        assert cfg["use_loop_as_root"] is False
        assert cfg["advanced_separator"] is True
        assert cfg["check_date"] is True
        assert cfg["tstatcatcher_stats"] is True

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
