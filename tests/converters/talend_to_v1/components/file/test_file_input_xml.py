"""Tests for FileInputXMLConverter (tFileInputXML -> v1 FileInputXML config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_xml import (
    FileInputXMLConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="fix_1",
               component_type="tFileInputXML"):
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


def _make_mapping_data(rows):
    """Generate MAPPING TABLE data with stride-3 (SCHEMA_COLUMN + QUERY + NODECHECK).

    rows: list of tuples (column_name, xpath_expression, nodecheck)
    """
    result = []
    for col, query, nodecheck in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": col})
        result.append({"elementRef": "QUERY", "value": query})
        result.append({"elementRef": "NODECHECK", "value": nodecheck})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        """tFileInputXML is registered in the converter registry."""
        assert REGISTRY.get("tFileInputXML") is FileInputXMLConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_filepath_default(self):
        """Default filepath is empty string."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["filepath"] == ""

    def test_loop_query_default(self):
        """Default loop_query is '/bills/bill/line'."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["loop_query"] == "/bills/bill/line"

    def test_limit_default(self):
        """Default limit is empty string."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == ""

    def test_die_on_error_default(self):
        """Default die_on_error is False."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_advanced_separator_default(self):
        """Default advanced_separator is False."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        """Default thousands_separator is ','."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        """Default decimal_separator is '.'."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."

    def test_ignore_ns_default(self):
        """Default ignore_ns is False."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["ignore_ns"] is False

    def test_ignore_dtd_default(self):
        """Default ignore_dtd is False."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["ignore_dtd"] is False

    def test_use_separator_default(self):
        """Default use_separator is False."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["use_separator"] is False

    def test_field_separator_default(self):
        """Default field_separator is ','."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["field_separator"] == ","

    def test_generation_mode_default(self):
        """Default generation_mode is 'Dom4j'."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["generation_mode"] == "Dom4j"

    def test_check_date_default(self):
        """Default check_date is False."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["check_date"] is False

    def test_encoding_default(self):
        """Default encoding is 'ISO-8859-15' per _java.xml."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filepath_extracted(self):
        """FILENAME is extracted to filepath config key."""
        node = _make_node(params={"FILENAME": '"/data/input.xml"'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["filepath"] == "/data/input.xml"

    def test_loop_query_extracted(self):
        """LOOP_QUERY is extracted."""
        node = _make_node(params={"LOOP_QUERY": '"/root/record"'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["loop_query"] == "/root/record"

    def test_limit_extracted(self):
        """LIMIT is extracted as string."""
        node = _make_node(params={"LIMIT": '"1000"'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == "1000"

    def test_die_on_error_true(self):
        """DIE_ON_ERROR=true is extracted correctly."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_encoding_extracted(self):
        """Custom ENCODING is extracted."""
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_ignore_ns_true(self):
        """IGNORE_NS=true is extracted correctly."""
        node = _make_node(params={"IGNORE_NS": "true"})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["ignore_ns"] is True

    def test_ignore_dtd_true(self):
        """IGNORE_DTD=true is extracted correctly."""
        node = _make_node(params={"IGNORE_DTD": "true"})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["ignore_dtd"] is True

    def test_generation_mode_sax(self):
        """GENERATION_MODE='SAX' is extracted."""
        node = _make_node(params={"GENERATION_MODE": '"SAX"'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["generation_mode"] == "SAX"

    def test_advanced_separator_true(self):
        """ADVANCED_SEPARATOR=true is extracted correctly."""
        node = _make_node(params={"ADVANCED_SEPARATOR": "true"})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is True

    def test_thousands_separator_extracted(self):
        """Custom THOUSANDS_SEPARATOR is extracted."""
        node = _make_node(params={"THOUSANDS_SEPARATOR": '"."'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == "."

    def test_decimal_separator_extracted(self):
        """Custom DECIMAL_SEPARATOR is extracted."""
        node = _make_node(params={"DECIMAL_SEPARATOR": '","'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == ","

    def test_check_date_true(self):
        """CHECK_DATE=true is extracted correctly."""
        node = _make_node(params={"CHECK_DATE": "true"})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["check_date"] is True

    def test_use_separator_true(self):
        """USE_SEPARATOR=true is extracted correctly."""
        node = _make_node(params={"USE_SEPARATOR": "true"})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["use_separator"] is True

    def test_field_separator_extracted(self):
        """Custom FIELD_SEPARATOR is extracted."""
        node = _make_node(params={"FIELD_SEPARATOR": '"|"'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["field_separator"] == "|"


class TestMappingTable:
    """Verify MAPPING TABLE parsing with stride-3 triplet format."""

    def test_mapping_empty_when_missing(self):
        """Missing MAPPING produces empty list."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    def test_mapping_empty_list(self):
        """Explicit empty MAPPING list produces empty list."""
        node = _make_node(params={"MAPPING": []})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    def test_mapping_parsed_triplet(self):
        """MAPPING triplet (SCHEMA_COLUMN + QUERY + NODECHECK) is parsed correctly."""
        mapping_data = _make_mapping_data([
            ('"order_id"', '"@id"', "false"),
            ('"customer"', '"customer/name"', "true"),
            ('"amount"', '"total/@value"', "false"),
        ])
        node = _make_node(params={"MAPPING": mapping_data})
        result = FileInputXMLConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]

        assert len(mapping) == 3
        assert mapping[0] == {"column": "order_id", "xpath": "@id", "nodecheck": False}
        assert mapping[1] == {"column": "customer", "xpath": "customer/name", "nodecheck": True}
        assert mapping[2] == {"column": "amount", "xpath": "total/@value", "nodecheck": False}

    def test_mapping_missing_nodecheck_defaults_false(self):
        """Missing NODECHECK defaults to False."""
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"col1"'},
            {"elementRef": "QUERY", "value": '"path1"'},
            {"elementRef": "SCHEMA_COLUMN", "value": '"col2"'},
            {"elementRef": "QUERY", "value": '"path2"'},
        ]
        node = _make_node(params={"MAPPING": raw})
        result = FileInputXMLConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]

        assert len(mapping) == 2
        assert mapping[0]["nodecheck"] is False
        assert mapping[1]["nodecheck"] is False

    def test_mapping_non_list_ignored(self):
        """Non-list MAPPING is treated as empty."""
        node = _make_node(params={"MAPPING": "not_a_list"})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["mapping"] == []

    def test_mapping_strips_quotes(self):
        """MAPPING values have surrounding quotes stripped."""
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"quoted_col"'},
            {"elementRef": "QUERY", "value": '"\"quoted/path\""'},
            {"elementRef": "NODECHECK", "value": "true"},
        ]
        node = _make_node(params={"MAPPING": raw})
        result = FileInputXMLConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]

        assert len(mapping) == 1
        assert mapping[0]["column"] == "quoted_col"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """Default tstatcatcher_stats is False."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS=true is extracted correctly."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """Default label is empty string."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """LABEL is extracted correctly."""
        node = _make_node(params={"LABEL": '"xml_reader"'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "xml_reader"


class TestSchema:
    """Verify schema extraction for source component."""

    def test_output_schema_parsed(self):
        """Schema columns are parsed into output schema."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputXMLConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 3
        assert output_schema[0]["name"] == "id"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[1]["name"] == "name"
        assert output_schema[1]["length"] == 100
        assert output_schema[2]["name"] == "created"
        assert output_schema[2]["date_pattern"] == "%Y-%m-%d %H:%M:%S"

    def test_input_schema_always_empty(self):
        """Source component input schema is always empty."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Converter emits per-feature needs_review entries for engine gaps."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        # generation_mode, advanced_separator, check_date, use_separator,
        # field_separator = 5 entries
        assert len(result.needs_review) == 5

    def test_needs_review_severity(self):
        """All needs_review entries have severity engine_gap."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries reference the component id."""
        node = _make_node(component_id="test_comp")
        result = FileInputXMLConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()

    def test_needs_review_keys(self):
        """Each needs_review entry has exactly 3 keys: issue, component, severity."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert set(entry.keys()) == {"issue", "component", "severity"}

    def test_generation_mode_in_needs_review(self):
        """generation_mode engine gap is documented."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("generation_mode" in i for i in issues)


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """All 17 config keys (15 unique + 2 framework) are present."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputXMLConverter().convert(node, [], {})
        expected_keys = {
            "filepath", "loop_query", "mapping", "limit", "die_on_error",
            "encoding", "ignore_ns", "ignore_dtd", "generation_mode",
            "advanced_separator", "thousands_separator", "decimal_separator",
            "check_date", "use_separator", "field_separator",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_no_extra_config_keys(self):
        """No unexpected config keys are present."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        expected_keys = {
            "filepath", "loop_query", "mapping", "limit", "die_on_error",
            "encoding", "ignore_ns", "ignore_dtd", "generation_mode",
            "advanced_separator", "thousands_separator", "decimal_separator",
            "check_date", "use_separator", "field_separator",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        extra = actual_keys - expected_keys
        assert not extra, f"Unexpected config keys: {extra}"


class TestComponentStructure:
    """Verify output dict has all required top-level keys."""

    def test_component_dict_structure(self):
        """Output has all required top-level keys from _build_component_dict."""
        node = _make_node(params={
            "FILENAME": '"f.xml"',
            "LOOP_QUERY": '"/root"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys

    def test_type_is_file_input_xml(self):
        """type field is 'FileInputXML' per D-43."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["type"] == "FileInputXML"

    def test_original_type_is_talend_name(self):
        """original_type preserves the Talend component name."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileInputXML"

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_inputs_outputs_empty(self):
        """Source component has empty inputs and outputs."""
        node = _make_node()
        result = FileInputXMLConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


class TestWarnings:
    """Verify warning generation for validation issues."""

    def test_empty_filename_warning(self):
        """Empty FILENAME triggers a warning."""
        node = _make_node(params={"LOOP_QUERY": '"/root"'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_empty_loop_query_warning(self):
        """Empty LOOP_QUERY triggers a warning."""
        node = _make_node(params={"FILENAME": '"/data/test.xml"', "LOOP_QUERY": '""'})
        result = FileInputXMLConverter().convert(node, [], {})
        assert any("LOOP_QUERY" in w for w in result.warnings)

    def test_no_warnings_with_valid_params(self):
        """Valid params produce no warnings."""
        node = _make_node(params={
            "FILENAME": '"/data/f.xml"',
            "LOOP_QUERY": '"/root"',
        })
        result = FileInputXMLConverter().convert(node, [], {})
        assert len(result.warnings) == 0
