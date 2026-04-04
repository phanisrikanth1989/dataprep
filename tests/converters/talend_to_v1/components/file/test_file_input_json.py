"""Tests for FileInputJSONConverter (tFileInputJSON -> v1 FileInputJSON config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_json import (
    FileInputJSONConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="fij_1",
               component_type="tFileInputJSON"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=100),
            SchemaColumn(
                name="created",
                type="id_Date",
                date_pattern="yyyy-MM-dd HH:mm:ss",
            ),
        ]
    }


def _make_mapping_jsonpath(rows):
    """Generate MAPPING_JSONPATH TABLE data with stride-2 (SCHEMA_COLUMN + QUERY).

    rows: list of tuples (column_name, jsonpath_expression)
    """
    result = []
    for col, query in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": col})
        result.append({"elementRef": "QUERY", "value": query})
    return result


def _make_mapping_xpath(rows):
    """Generate MAPPINGXPATH TABLE data with stride-3 (SCHEMA_COLUMN + QUERY + NODECHECK).

    rows: list of tuples (column_name, query, nodecheck_str)
    """
    result = []
    for col, query, nodecheck in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": col})
        result.append({"elementRef": "QUERY", "value": query})
        result.append({"elementRef": "NODECHECK", "value": nodecheck})
    return result


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        """tFileInputJSON maps to FileInputJSONConverter in the registry."""
        assert REGISTRY.get("tFileInputJSON") is FileInputJSONConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_read_by_default(self):
        """READ_BY defaults to 'JSONPATH' per _java.xml."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["read_by"] == "JSONPATH"

    def test_json_path_version_default(self):
        """JSON_PATH_VERSION defaults to '2_1_0' per _java.xml."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["json_path_version"] == "2_1_0"

    def test_useurl_default(self):
        """USEURL defaults to False per _java.xml."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["useurl"] is False

    def test_urlpath_default(self):
        """URLPATH defaults to empty string."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["urlpath"] == ""

    def test_filename_default(self):
        """FILENAME defaults to empty string."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_loop_query_default(self):
        """LOOP_QUERY defaults to '/bills/bill/line' per _java.xml."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["loop_query"] == "/bills/bill/line"

    def test_json_loop_query_default(self):
        """JSON_LOOP_QUERY defaults to '$.bills.bill.line[*]' per _java.xml."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["json_loop_query"] == "$.bills.bill.line[*]"

    def test_die_on_error_default(self):
        """DIE_ON_ERROR defaults to False per _java.xml."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_advanced_separator_default(self):
        """ADVANCED_SEPARATOR defaults to False per _java.xml."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        """THOUSANDS_SEPARATOR defaults to ',' per _java.xml."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        """DECIMAL_SEPARATOR defaults to '.' per _java.xml."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."

    def test_check_date_default(self):
        """CHECK_DATE defaults to False per _java.xml."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["check_date"] is False

    def test_use_loop_as_root_default(self):
        """USE_LOOP_AS_ROOT defaults to True per _java.xml."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["use_loop_as_root"] is True

    def test_encoding_default(self):
        """ENCODING defaults to 'UTF-8' per _java.xml (correct for this component)."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_read_by_xpath(self):
        """READ_BY 'XPATH' is extracted correctly."""
        node = _make_node(params={"READ_BY": '"XPATH"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["read_by"] == "XPATH"

    def test_read_by_no_loop(self):
        """READ_BY 'JSONPATH_WITHOUTPUT_LOOP' is extracted correctly."""
        node = _make_node(params={"READ_BY": '"JSONPATH_WITHOUTPUT_LOOP"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["read_by"] == "JSONPATH_WITHOUTPUT_LOOP"

    def test_json_path_version_extracted(self):
        """Quoted JSON_PATH_VERSION value is extracted with quotes stripped."""
        node = _make_node(params={"JSON_PATH_VERSION": '"1_1_0"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["json_path_version"] == "1_1_0"

    def test_useurl_true(self):
        """USEURL 'true' is extracted as boolean True."""
        node = _make_node(params={"USEURL": "true"})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["useurl"] is True

    def test_urlpath_extracted(self):
        """Quoted URLPATH is extracted with quotes stripped."""
        node = _make_node(params={"URLPATH": '"http://api.example.com/data.json"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["urlpath"] == "http://api.example.com/data.json"

    def test_filename_extracted(self):
        """Quoted FILENAME value is extracted with quotes stripped."""
        node = _make_node(params={"FILENAME": '"/data/input.json"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "/data/input.json"

    def test_loop_query_extracted(self):
        """Quoted LOOP_QUERY value is extracted with quotes stripped."""
        node = _make_node(params={"LOOP_QUERY": '"/data/items/item"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["loop_query"] == "/data/items/item"

    def test_json_loop_query_extracted(self):
        """Quoted JSON_LOOP_QUERY value is extracted with quotes stripped."""
        node = _make_node(params={"JSON_LOOP_QUERY": '"$.store.book[*]"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["json_loop_query"] == "$.store.book[*]"

    def test_die_on_error_true(self):
        """DIE_ON_ERROR 'true' is extracted as boolean True."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_advanced_separator_true(self):
        """ADVANCED_SEPARATOR 'true' is extracted as boolean True."""
        node = _make_node(params={"ADVANCED_SEPARATOR": "true"})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is True

    def test_thousands_separator_extracted(self):
        """Quoted THOUSANDS_SEPARATOR value is extracted."""
        node = _make_node(params={"THOUSANDS_SEPARATOR": '"."'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == "."

    def test_decimal_separator_extracted(self):
        """Quoted DECIMAL_SEPARATOR value is extracted."""
        node = _make_node(params={"DECIMAL_SEPARATOR": '","'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == ","

    def test_check_date_true(self):
        """CHECK_DATE 'true' is extracted as boolean True."""
        node = _make_node(params={"CHECK_DATE": "true"})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["check_date"] is True

    def test_use_loop_as_root_false(self):
        """USE_LOOP_AS_ROOT 'false' is extracted as boolean False."""
        node = _make_node(params={"USE_LOOP_AS_ROOT": "false"})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["use_loop_as_root"] is False

    def test_encoding_custom(self):
        """Quoted ENCODING value is extracted with quotes stripped."""
        node = _make_node(params={"ENCODING": '"ISO-8859-1"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-1"


class TestMappingTables:
    """Verify MAPPING TABLE parsing for all three read modes."""

    # -- JSONPATH mode (MAPPING_JSONPATH) --

    def test_mapping_jsonpath_parsed(self):
        """JSONPATH mode extracts MAPPING_JSONPATH with SCHEMA_COLUMN/QUERY pairs."""
        table = _make_mapping_jsonpath([
            ("id", '"$.id"'),
            ("name", '"$.name"'),
            ("email", '"$.contact.email"'),
        ])
        node = _make_node(params={
            "READ_BY": '"JSONPATH"',
            "MAPPING_JSONPATH": table,
        })
        result = FileInputJSONConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]

        assert len(mapping) == 3
        assert mapping[0] == {"column": "id", "jsonpath": "$.id"}
        assert mapping[1] == {"column": "name", "jsonpath": "$.name"}
        assert mapping[2] == {"column": "email", "jsonpath": "$.contact.email"}

    def test_mapping_jsonpath_empty(self):
        """Empty MAPPING_JSONPATH results in empty mapping list."""
        node = _make_node(params={"READ_BY": '"JSONPATH"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    # -- XPATH mode (MAPPINGXPATH) --

    def test_mapping_xpath_parsed(self):
        """XPATH mode extracts MAPPINGXPATH with SCHEMA_COLUMN/QUERY/NODECHECK triplets."""
        table = _make_mapping_xpath([
            ("id", '"@id"', "false"),
            ("content", '"."', "true"),
        ])
        node = _make_node(params={
            "READ_BY": '"XPATH"',
            "MAPPINGXPATH": table,
        })
        result = FileInputJSONConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]

        assert len(mapping) == 2
        assert mapping[0] == {"column": "id", "jsonpath": "@id", "nodecheck": False}
        assert mapping[1] == {"column": "content", "jsonpath": ".", "nodecheck": True}

    def test_mapping_xpath_empty(self):
        """Empty MAPPINGXPATH results in empty mapping list."""
        node = _make_node(params={"READ_BY": '"XPATH"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    # -- JSONPATH_WITHOUTPUT_LOOP mode (MAPPING) --

    def test_mapping_no_loop_parsed(self):
        """JSONPATH_WITHOUTPUT_LOOP mode extracts MAPPING table."""
        table = _make_mapping_jsonpath([
            ("id", '"$.id"'),
            ("name", '"$.first_name"'),
        ])
        node = _make_node(params={
            "READ_BY": '"JSONPATH_WITHOUTPUT_LOOP"',
            "MAPPING": table,
        })
        result = FileInputJSONConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]

        assert len(mapping) == 2
        assert mapping[0] == {"column": "id", "jsonpath": "$.id"}
        assert mapping[1] == {"column": "name", "jsonpath": "$.first_name"}

    def test_mapping_no_loop_empty(self):
        """Empty MAPPING results in empty mapping list."""
        node = _make_node(params={"READ_BY": '"JSONPATH_WITHOUTPUT_LOOP"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    # -- Edge cases --

    def test_mapping_partial_entries(self):
        """Trailing SCHEMA_COLUMN without QUERY gets empty jsonpath."""
        table = [
            {"elementRef": "SCHEMA_COLUMN", "value": "complete"},
            {"elementRef": "QUERY", "value": '"$.complete"'},
            {"elementRef": "SCHEMA_COLUMN", "value": "orphan"},
        ]
        node = _make_node(params={
            "READ_BY": '"JSONPATH"',
            "MAPPING_JSONPATH": table,
        })
        result = FileInputJSONConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]
        assert len(mapping) == 2
        assert mapping[0] == {"column": "complete", "jsonpath": "$.complete"}
        assert mapping[1] == {"column": "orphan", "jsonpath": ""}

    def test_mapping_non_list_returns_empty(self):
        """Non-list mapping value returns empty list."""
        node = _make_node(params={
            "READ_BY": '"JSONPATH"',
            "MAPPING_JSONPATH": "invalid",
        })
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """TSTATCATCHER_STATS defaults to False."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS 'true' is extracted as boolean True."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """LABEL defaults to empty string."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """Quoted LABEL value is extracted with quotes stripped."""
        node = _make_node(params={"LABEL": '"json_reader"'})
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "json_reader"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_is_dict_with_input_output(self):
        """Schema is a dict with 'input' and 'output' keys per D-41."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputJSONConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert isinstance(schema, dict)
        assert "input" in schema
        assert "output" in schema

    def test_schema_input_empty(self):
        """FileInputJSON is a source component -- input schema is always empty."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_output_populated(self):
        """Output schema is populated when node has FLOW schema columns."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputJSONConverter().convert(node, [], {})
        output = result.component["schema"]["output"]
        assert len(output) == 3
        assert output[0]["name"] == "id"
        assert output[0]["key"] is True
        assert output[0]["nullable"] is False
        assert output[1]["name"] == "name"
        assert output[1]["length"] == 100
        assert output[2]["name"] == "created"
        assert output[2]["date_pattern"] == "%Y-%m-%d %H:%M:%S"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps (per D-36: per-feature)."""

    def test_needs_review_count(self):
        """At least 3 needs_review entries for engine gaps."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert len(result.needs_review) >= 3

    def test_needs_review_loop_query(self):
        """One needs_review entry mentions 'loop_query'."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("loop_query" in i for i in issues)

    def test_needs_review_json_path_version(self):
        """One needs_review entry mentions 'json_path_version'."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("json_path_version" in i for i in issues)

    def test_needs_review_use_loop_as_root(self):
        """One needs_review entry mentions 'use_loop_as_root'."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("use_loop_as_root" in i for i in issues)

    def test_all_needs_review_are_engine_gap(self):
        """All needs_review entries have severity 'engine_gap'."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries include the component ID."""
        node = _make_node(component_id="fij_test")
        result = FileInputJSONConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "fij_test"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config dict contains all 17 expected keys (15 unique + 2 framework)."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputJSONConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "read_by", "json_path_version", "useurl", "urlpath",
            "filename", "loop_query", "json_loop_query",
            "mapping", "die_on_error", "advanced_separator",
            "thousands_separator", "decimal_separator", "check_date",
            "use_loop_as_root", "encoding",
            "tstatcatcher_stats", "label",
        }
        missing = expected_keys - set(cfg.keys())
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify _build_component_dict output structure."""

    def test_has_id(self):
        """Component dict has 'id' matching node.component_id."""
        node = _make_node(component_id="fij_42")
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["id"] == "fij_42"

    def test_has_type(self):
        """Component dict has 'type' == 'FileInputJSON' (engine class name per D-43)."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["type"] == "FileInputJSON"

    def test_has_original_type(self):
        """Component dict has 'original_type' == 'tFileInputJSON'."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileInputJSON"

    def test_has_config(self):
        """Component dict has 'config' key."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema(self):
        """Component dict has 'schema' key."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert "schema" in result.component

    def test_has_position(self):
        """Component dict has 'position' key."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_has_inputs_outputs(self):
        """Component dict has 'inputs' and 'outputs' keys (empty lists)."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node()
        result = FileInputJSONConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
