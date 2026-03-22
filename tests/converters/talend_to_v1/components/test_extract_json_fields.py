"""Tests for tExtractJSONFields -> ExtractJSONFields converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.extract_json_fields import (
    ExtractJSONFieldsConverter,
    _parse_mapping,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tExtractJSONFields_1",
        component_type="tExtractJSONFields",
        params=params or {},
        schema=schema or {},
        position={"x": 400, "y": 200},
    )


class TestExtractJSONFieldsConverter:
    """Tests for ExtractJSONFieldsConverter."""

    def test_basic_config(self):
        """All config params are extracted correctly with explicit values."""
        node = _make_node(params={
            "READ_BY": '"JSONPATH"',
            "JSON_PATH_VERSION": '"2_1_0"',
            "LOOP_QUERY": '"$.records[*]"',
            "DIE_ON_ERROR": "true",
            "ENCODING": '"ISO-8859-1"',
            "USE_LOOP_AS_ROOT": "true",
            "SPLIT_LIST": "true",
            "JSONFIELD": '"payload"',
            "MAPPING_4_JSONPATH": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"name"'},
                {"elementRef": "JSON_PATH_QUERY", "value": '"$.name"'},
                {"elementRef": "SCHEMA_COLUMN", "value": '"age"'},
                {"elementRef": "JSON_PATH_QUERY", "value": '"$.age"'},
            ],
        })
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "ExtractJSONFields"
        assert comp["original_type"] == "tExtractJSONFields"
        assert comp["id"] == "tExtractJSONFields_1"
        assert comp["position"] == {"x": 400, "y": 200}

        cfg = comp["config"]
        assert cfg["read_by"] == "JSONPATH"
        assert cfg["json_path_version"] == "2_1_0"
        assert cfg["loop_query"] == "$.records[*]"
        assert cfg["die_on_error"] is True
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["use_loop_as_root"] is True
        assert cfg["split_list"] is True
        assert cfg["json_field"] == "payload"

        assert len(cfg["mapping"]) == 2
        assert cfg["mapping"][0] == {"schema_column": "name", "query": "$.name"}
        assert cfg["mapping"][1] == {"schema_column": "age", "query": "$.age"}

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults (CONV-EJF-007)."""
        node = _make_node(params={})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["read_by"] == "JSONPATH"
        assert cfg["json_path_version"] == "2_1_0"
        assert cfg["loop_query"] == ""
        assert cfg["die_on_error"] is False
        assert cfg["encoding"] == "UTF-8"
        assert cfg["use_loop_as_root"] is False
        assert cfg["split_list"] is False
        assert cfg["json_field"] == ""
        assert cfg["mapping"] == []

    def test_fallback_to_json_loop_query(self):
        """CONV-EJF-003: Falls back to JSON_LOOP_QUERY when LOOP_QUERY is absent."""
        node = _make_node(params={
            "JSON_LOOP_QUERY": '"$.items[*]"',
        })
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["loop_query"] == "$.items[*]"

    def test_loop_query_prefers_primary_name(self):
        """When both LOOP_QUERY and JSON_LOOP_QUERY exist, LOOP_QUERY wins."""
        node = _make_node(params={
            "LOOP_QUERY": '"$.primary[*]"',
            "JSON_LOOP_QUERY": '"$.fallback[*]"',
        })
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["loop_query"] == "$.primary[*]"

    def test_boolean_params_are_bool_not_string(self):
        """CONV-EJF-005: boolean params must be Python bools, not strings."""
        node = _make_node(params={
            "DIE_ON_ERROR": "false",
            "USE_LOOP_AS_ROOT": "false",
            "SPLIT_LIST": "false",
        })
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["die_on_error"] is False
        assert isinstance(cfg["die_on_error"], bool)
        assert cfg["use_loop_as_root"] is False
        assert isinstance(cfg["use_loop_as_root"], bool)
        assert cfg["split_list"] is False
        assert isinstance(cfg["split_list"], bool)

    def test_schema_passthrough(self):
        """CONV-EJF-006: both input and output schema must match FLOW schema."""
        node = _make_node(
            params={"LOOP_QUERY": '"$"'},
            schema={
                "FLOW": [
                    SchemaColumn(
                        name="json_payload", type="id_String",
                        key=False, nullable=True, length=4000,
                    ),
                    SchemaColumn(
                        name="extracted_name", type="id_String",
                        key=False, nullable=True, length=200,
                    ),
                    SchemaColumn(
                        name="extracted_amount", type="id_Double",
                        key=False, nullable=True, precision=2,
                    ),
                ]
            },
        )
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 3
        assert schema["output"][0]["name"] == "json_payload"
        assert schema["output"][0]["length"] == 4000
        assert schema["output"][2]["name"] == "extracted_amount"
        assert schema["output"][2]["precision"] == 2

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registration(self):
        """The converter is registered under 'tExtractJSONFields'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tExtractJSONFields")
        assert cls is ExtractJSONFieldsConverter

    def test_empty_loop_query_warning(self):
        """An empty LOOP_QUERY produces a warning."""
        node = _make_node(params={})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert any("LOOP_QUERY" in w for w in result.warnings)

    def test_empty_mapping_warning(self):
        """An empty MAPPING_4_JSONPATH produces a warning."""
        node = _make_node(params={"LOOP_QUERY": '"$"'})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert any("MAPPING_4_JSONPATH" in w for w in result.warnings)


class TestParseMapping:
    """Tests for the _parse_mapping helper (CONV-EJF-002)."""

    def test_elementref_based_parsing(self):
        """Mapping entries are parsed by elementRef, not positional index."""
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"col_a"'},
            {"elementRef": "JSON_PATH_QUERY", "value": '"$.a"'},
        ]
        result = _parse_mapping(raw)
        assert result == [{"schema_column": "col_a", "query": "$.a"}]

    def test_reversed_elementref_order(self):
        """Handles entries where JSON_PATH_QUERY comes before SCHEMA_COLUMN."""
        raw = [
            {"elementRef": "JSON_PATH_QUERY", "value": '"$.x"'},
            {"elementRef": "SCHEMA_COLUMN", "value": '"col_x"'},
        ]
        result = _parse_mapping(raw)
        assert result == [{"schema_column": "col_x", "query": "$.x"}]

    def test_multiple_mapping_rows(self):
        """Multiple mapping groups are parsed correctly."""
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"name"'},
            {"elementRef": "JSON_PATH_QUERY", "value": '"$.name"'},
            {"elementRef": "SCHEMA_COLUMN", "value": '"city"'},
            {"elementRef": "JSON_PATH_QUERY", "value": '"$.address.city"'},
            {"elementRef": "SCHEMA_COLUMN", "value": '"zip"'},
            {"elementRef": "JSON_PATH_QUERY", "value": '"$.address.zip"'},
        ]
        result = _parse_mapping(raw)
        assert len(result) == 3
        assert result[0] == {"schema_column": "name", "query": "$.name"}
        assert result[1] == {"schema_column": "city", "query": "$.address.city"}
        assert result[2] == {"schema_column": "zip", "query": "$.address.zip"}

    def test_empty_and_none_input(self):
        """None and empty list return empty mapping."""
        assert _parse_mapping(None) == []
        assert _parse_mapping([]) == []
        assert _parse_mapping("not a list") == []

    def test_incomplete_group_skipped(self):
        """An incomplete trailing group (odd number of entries) is skipped."""
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"name"'},
            {"elementRef": "JSON_PATH_QUERY", "value": '"$.name"'},
            {"elementRef": "SCHEMA_COLUMN", "value": '"orphan"'},
        ]
        result = _parse_mapping(raw)
        assert len(result) == 1
        assert result[0]["schema_column"] == "name"

    def test_quote_stripping(self):
        """Surrounding quotes are stripped from both schema_column and query."""
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"my_col"'},
            {"elementRef": "JSON_PATH_QUERY", "value": '"$.data.value"'},
        ]
        result = _parse_mapping(raw)
        assert result[0]["schema_column"] == "my_col"
        assert result[0]["query"] == "$.data.value"

    def test_no_quotes_unaffected(self):
        """Values without quotes are returned as-is."""
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": "col_plain"},
            {"elementRef": "JSON_PATH_QUERY", "value": "$.plain"},
        ]
        result = _parse_mapping(raw)
        assert result[0]["schema_column"] == "col_plain"
        assert result[0]["query"] == "$.plain"
