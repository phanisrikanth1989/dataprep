"""Tests for ExtractJSONFieldsConverter (tExtractJSONFields -> v1 ExtractJSONFields config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.extract_json_fields import (
    ExtractJSONFieldsConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="ejf_1",
               component_type="tExtractJSONFields"):
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
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
        ]
    }


def _make_mapping_jsonpath_data(rows):
    """Generate MAPPING_4_JSONPATH TABLE data with stride-2 per row.

    rows: list of tuples (schema_column, query)
    """
    result = []
    for schema_col, query in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": schema_col})
        result.append({"elementRef": "QUERY", "value": query})
    return result


def _make_mapping_xpath_data(rows):
    """Generate MAPPING TABLE data with stride-3 per row.

    rows: list of tuples (query, nodecheck, isarray)
    """
    result = []
    for query, nodecheck, isarray in rows:
        result.append({"elementRef": "QUERY", "value": query})
        result.append({"elementRef": "NODECHECK", "value": nodecheck})
        result.append({"elementRef": "ISARRAY", "value": isarray})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tExtractJSONFields") is ExtractJSONFieldsConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_read_by_default(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["read_by"] == "JSONPATH"

    def test_json_path_version_default(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["json_path_version"] == "2_1_0"

    def test_jsonfield_default_empty(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["jsonfield"] == ""

    def test_loop_query_default(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["loop_query"] == "/bills/bill/line"

    def test_json_loop_query_default(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["json_loop_query"] == "$.bills.bill.line[*]"

    def test_mapping_default_empty(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    def test_mapping_4_jsonpath_default_empty(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["mapping_4_jsonpath"] == []

    def test_die_on_error_default_false(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_schema_opt_num_default(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["schema_opt_num"] == "100"

    def test_encoding_default(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_use_loop_as_root_default_true(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["use_loop_as_root"] is True

    def test_split_list_default_true(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["split_list"] is True

    def test_jdk_version_default(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["jdk_version"] == "JDK_8"

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_jsonfield_custom(self):
        node = _make_node(params={"JSONFIELD": '"json_col"'})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["jsonfield"] == "json_col"

    def test_read_by_xpath(self):
        node = _make_node(params={"READ_BY": '"XPATH"'})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["read_by"] == "XPATH"

    def test_loop_query_custom(self):
        node = _make_node(params={"LOOP_QUERY": '"//records/record"'})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["loop_query"] == "//records/record"

    def test_json_loop_query_custom(self):
        node = _make_node(params={"JSON_LOOP_QUERY": '"$.records[*]"'})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["json_loop_query"] == "$.records[*]"

    def test_encoding_custom(self):
        node = _make_node(params={"ENCODING": '"ISO-8859-1"'})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-1"

    def test_die_on_error_true(self):
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_use_loop_as_root_false(self):
        node = _make_node(params={"USE_LOOP_AS_ROOT": "false"})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["use_loop_as_root"] is False

    def test_split_list_false(self):
        node = _make_node(params={"SPLIT_LIST": "false"})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["split_list"] is False

    def test_jdk_version_custom(self):
        node = _make_node(params={"JDK_VERSION": '"JDK_11"'})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["jdk_version"] == "JDK_11"

    def test_schema_opt_num_custom(self):
        node = _make_node(params={"SCHEMA_OPT_NUM": '"50"'})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["schema_opt_num"] == "50"

    def test_mapping_jsonpath_parsing(self):
        """MAPPING_4_JSONPATH TABLE entries parsed into list of dicts with query."""
        table_data = _make_mapping_jsonpath_data([
            ('"name"', '"$.name"'),
            ('"age"', '"$.age"'),
        ])
        node = _make_node(params={"MAPPING_4_JSONPATH": table_data})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        m = result.component["config"]["mapping_4_jsonpath"]
        assert len(m) == 2
        assert m[0]["schema_column"] == "name"
        assert m[0]["query"] == "$.name"
        assert m[1]["schema_column"] == "age"
        assert m[1]["query"] == "$.age"

    def test_mapping_xpath_parsing(self):
        """MAPPING TABLE entries (XPath mode) parsed into list of dicts with query, nodecheck, isarray."""
        table_data = _make_mapping_xpath_data([
            ('"//name"', "true", "false"),
            ('"//items"', "false", "true"),
        ])
        node = _make_node(params={"MAPPING": table_data})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        m = result.component["config"]["mapping"]
        assert len(m) == 2
        assert m[0]["query"] == "//name"
        assert m[0]["nodecheck"] is True
        assert m[0]["isarray"] is False
        assert m[1]["query"] == "//items"
        assert m[1]["nodecheck"] is False
        assert m[1]["isarray"] is True

    def test_mapping_xpath_empty_when_missing(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    def test_mapping_jsonpath_empty_when_missing(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["mapping_4_jsonpath"] == []

    def test_mapping_xpath_incomplete_stride_skipped(self):
        """Incomplete trailing group in XPath MAPPING is skipped."""
        table_data = [
            {"elementRef": "QUERY", "value": '"//name"'},
            {"elementRef": "NODECHECK", "value": "true"},
            {"elementRef": "ISARRAY", "value": "false"},
            {"elementRef": "QUERY", "value": '"//orphan"'},
        ]
        node = _make_node(params={"MAPPING": table_data})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert len(result.component["config"]["mapping"]) == 1

    def test_mapping_jsonpath_legacy_json_path_query(self):
        """Backward-compat: JSON_PATH_QUERY elementRef accepted in MAPPING_4_JSONPATH."""
        table_data = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"col_a"'},
            {"elementRef": "JSON_PATH_QUERY", "value": '"$.a"'},
        ]
        node = _make_node(params={"MAPPING_4_JSONPATH": table_data})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert len(result.component["config"]["mapping_4_jsonpath"]) == 1
        assert result.component["config"]["mapping_4_jsonpath"][0]["query"] == "$.a"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema passthrough for transform component."""

    def test_schema_passthrough(self):
        """Both input and output schema must match FLOW schema."""
        node = _make_node(schema=_make_schema_columns())
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][1]["name"] == "name"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert len(result.needs_review) >= 1

    def test_needs_review_engine_gap_severity(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config must have 13 unique + 2 framework = 15 config keys."""
        node = _make_node(schema=_make_schema_columns())
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        expected_keys = {
            "read_by", "json_path_version", "jsonfield", "loop_query",
            "json_loop_query", "mapping", "mapping_4_jsonpath", "die_on_error",
            "schema_opt_num", "encoding", "use_loop_as_root", "split_list",
            "jdk_version",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"
        assert len(result.component["config"]) == 15


class TestComponentStructure:
    """Verify component wrapper structure."""

    def test_has_type(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["type"] == "ExtractJSONFields"

    def test_has_original_type(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["original_type"] == "tExtractJSONFields"

    def test_has_id(self):
        node = _make_node(component_id="ejf_1")
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert result.component["id"] == "ejf_1"

    def test_wrapper_keys(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected_keys

    def test_result_type(self):
        node = _make_node()
        result = ExtractJSONFieldsConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
