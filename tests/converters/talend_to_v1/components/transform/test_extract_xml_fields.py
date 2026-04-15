"""Tests for ExtractXMLFieldConverter (tExtractXMLField -> v1 ExtractXMLField config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.extract_xml_fields import (
    ExtractXMLFieldConverter,
    _parse_mapping,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="exf_1",
               component_type="tExtractXMLField"):
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
            SchemaColumn(name="xml_data", type="id_String", nullable=True, key=False, length=2000),
            SchemaColumn(name="name", type="id_String", nullable=True, key=False, length=100),
        ]
    }


def _make_mapping_data(rows):
    """Generate MAPPING TABLE data with stride-2 per row (QUERY + NODECHECK).

    rows: list of tuples (query, nodecheck)
    BASED_ON_SCHEMA=true means SCHEMA_COLUMN is auto-populated from schema,
    so TABLE entries only contain QUERY and NODECHECK.
    """
    result = []
    for query, nodecheck in rows:
        result.append({"elementRef": "QUERY", "value": query})
        result.append({"elementRef": "NODECHECK", "value": nodecheck})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tExtractXMLField") is ExtractXMLFieldConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_xmlfield_default_empty(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["xmlfield"] == ""

    # use_items, loop_query_base removed in a943b5f (hidden Talend params)

    def test_loop_query_default(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["loop_query"] == "/bills/bill/line"

    def test_mapping_default_empty(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    def test_limit_default_empty(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == ""

    def test_die_on_error_default_false(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    # use_xml_field, xml_text, xml_prefix, schema_opt_num removed in a943b5f (hidden Talend params)

    def test_ignore_ns_default_false(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["ignore_ns"] is False

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_xmlfield_custom(self):
        node = _make_node(params={"XMLFIELD": '"xml_col"'})
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["xmlfield"] == "xml_col"

    def test_loop_query_custom(self):
        node = _make_node(params={"LOOP_QUERY": '"/root/items"'})
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["loop_query"] == "/root/items"

    def test_mapping_parsing(self):
        """MAPPING TABLE entries -> list of dicts with query and nodecheck."""
        mapping_data = _make_mapping_data([
            ('"name/text()"', "false"),
            ('"age/text()"', "true"),
        ])
        node = _make_node(params={"MAPPING": mapping_data})
        result = ExtractXMLFieldConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]
        assert len(mapping) == 2
        assert mapping[0] == {"query": "name/text()", "nodecheck": False}
        assert mapping[1] == {"query": "age/text()", "nodecheck": True}

    def test_limit_as_string(self):
        """LIMIT extracted as string for expression support."""
        node = _make_node(params={"LIMIT": '"1000"'})
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == "1000"

    # use_items, use_xml_field, loop_query_base, xml_text, xml_prefix,
    # schema_opt_num extraction tests removed in a943b5f (hidden Talend params)

    def test_ignore_ns_true(self):
        node = _make_node(params={"IGNORE_NS": "true"})
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["ignore_ns"] is True

    def test_die_on_error_true(self):
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True


class TestTableParsing:
    """Verify MAPPING TABLE parameter parsing (BASED_ON_SCHEMA=true, stride-2)."""

    def test_mapping_empty_when_missing(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    def test_mapping_single_row(self):
        mapping_data = _make_mapping_data([('"./name/text()"', "false")])
        node = _make_node(params={"MAPPING": mapping_data})
        result = ExtractXMLFieldConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]
        assert len(mapping) == 1
        assert mapping[0]["query"] == "./name/text()"
        assert mapping[0]["nodecheck"] is False

    def test_mapping_multiple_rows(self):
        mapping_data = _make_mapping_data([
            ('"@id"', "false"),
            ('"name/text()"', "false"),
            ('"value/text()"', "true"),
        ])
        node = _make_node(params={"MAPPING": mapping_data})
        result = ExtractXMLFieldConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]
        assert len(mapping) == 3
        assert mapping[2]["nodecheck"] is True

    def test_mapping_incomplete_stride_skipped(self):
        """Incomplete trailing group (< 2 entries) should be ignored."""
        entries = [
            {"elementRef": "QUERY", "value": '"xpath1"'},
            {"elementRef": "NODECHECK", "value": "false"},
            {"elementRef": "QUERY", "value": '"xpath2"'},
            # Missing NODECHECK -> incomplete group
        ]
        result = _parse_mapping(entries)
        assert len(result) == 1

    def test_mapping_none_input(self):
        assert _parse_mapping(None) == []

    def test_mapping_empty_list(self):
        assert _parse_mapping([]) == []

    def test_mapping_non_list(self):
        assert _parse_mapping("not a list") == []


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction (passthrough: input == output)."""

    def test_schema_passthrough(self):
        node = _make_node(schema=_make_schema_columns())
        result = ExtractXMLFieldConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "xml_data"
        assert schema["output"][1]["name"] == "name"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert len(result.needs_review) > 0

    def test_needs_review_engine_gap_severity(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = ExtractXMLFieldConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config dict has all 8 keys (6 unique + 2 framework).

        Keys removed in a943b5f: use_items, loop_query_base, use_xml_field,
        xml_text, xml_prefix, schema_opt_num
        """
        node = _make_node(schema=_make_schema_columns())
        result = ExtractXMLFieldConverter().convert(node, [], {})
        expected_keys = {
            "xmlfield", "loop_query",
            "mapping", "limit", "die_on_error", "ignore_ns",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify the component dict wrapper structure."""

    def test_has_type(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["type"] == "ExtractXMLField"

    def test_has_original_type(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["original_type"] == "tExtractXMLField"

    def test_has_id(self):
        node = _make_node(component_id="exf_1")
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["id"] == "exf_1"

    def test_has_position(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_wrapper_keys(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        expected = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected

    def test_result_type(self):
        node = _make_node()
        result = ExtractXMLFieldConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
