"""Tests for AdvancedFileOutputXmlConverter (tAdvancedFileOutputXML -> tAdvancedFileOutputXML)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_output_xml import (
    AdvancedFileOutputXmlConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="xml_out_1",
               component_type="tAdvancedFileOutputXML"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
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


def _make_table_data(rows):
    """Generate TABLE data with stride-5 per row (PATH, COLUMN, VALUE, ATTRIBUTE, ORDER).

    rows: list of tuples (path, column, value, attribute, order)
    """
    result = []
    for row_values in rows:
        for field_name, value in zip(("PATH", "COLUMN", "VALUE", "ATTRIBUTE", "ORDER"), row_values):
            result.append({"elementRef": field_name, "value": value})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tAdvancedFileOutputXML") is AdvancedFileOutputXmlConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_filename_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_usestream_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["usestream"] is False

    def test_streamname_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["streamname"] == "outputStream"

    def test_root_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["root"] == []

    def test_group_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["group"] == []

    def test_loop_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["loop"] == []

    def test_map_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["map"] == ""

    def test_merge_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["merge"] is False

    def test_pretty_compact_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["pretty_compact"] is False

    def test_file_valid_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["file_valid"] is False

    def test_dtd_valid_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["dtd_valid"] is True

    def test_dtd_name_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["dtd_name"] == "Root"

    def test_dtd_systemid_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["dtd_systemid"] == "Talend.dtd"

    def test_xsl_valid_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["xsl_valid"] is False

    def test_xsl_type_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["xsl_type"] == "text/xsl"

    def test_xsl_href_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["xsl_href"] == "Talend.xsl"

    def test_split_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["split"] is False

    def test_split_every_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["split_every"] == "1000"

    def test_trim_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["trim"] is False

    def test_create_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["create"] is True

    def test_create_empty_element_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["create_empty_element"] is True

    def test_add_empty_attribute_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["add_empty_attribute"] is False

    def test_add_unmapped_attribute_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["add_unmapped_attribute"] is False

    def test_add_document_as_node_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["add_document_as_node"] is False

    def test_output_as_xsd_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["output_as_xsd"] is False

    def test_advanced_separator_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."

    def test_generation_mode_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["generation_mode"] == "DOM4J"

    def test_encoding_default(self):
        """CRITICAL: default is ISO-8859-15 per _java.xml (was UTF-8)."""
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_delete_empty_file_default(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["delete_empty_file"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filename_extracted(self):
        node = _make_node(params={"FILENAME": '"/data/output.xml"'})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "/data/output.xml"

    def test_encoding_custom(self):
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_root_single_entry(self):
        """ROOT TABLE with 1 entry -> [{path, column, value, attribute, order}]."""
        table_data = _make_table_data([
            ('"root"', '"id"', '"val1"', '"attr1"', '"1"'),
        ])
        node = _make_node(params={"ROOT": table_data})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        root = result.component["config"]["root"]
        assert len(root) == 1
        assert root[0]["path"] == "root"
        assert root[0]["column"] == "id"
        assert root[0]["value"] == "val1"
        assert root[0]["attribute"] == "attr1"
        assert root[0]["order"] == "1"

    def test_group_single_entry(self):
        """GROUP TABLE with 1 entry."""
        table_data = _make_table_data([
            ('"items"', '"name"', '""', '"type"', '"2"'),
        ])
        node = _make_node(params={"GROUP": table_data})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        group = result.component["config"]["group"]
        assert len(group) == 1
        assert group[0]["path"] == "items"
        assert group[0]["column"] == "name"
        assert group[0]["value"] == ""
        assert group[0]["attribute"] == "type"
        assert group[0]["order"] == "2"

    def test_loop_single_entry(self):
        """LOOP TABLE with 1 entry."""
        table_data = _make_table_data([
            ('"record"', '"data"', '"x"', '""', '"0"'),
        ])
        node = _make_node(params={"LOOP": table_data})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        loop = result.component["config"]["loop"]
        assert len(loop) == 1
        assert loop[0]["path"] == "record"
        assert loop[0]["column"] == "data"
        assert loop[0]["value"] == "x"
        assert loop[0]["attribute"] == ""
        assert loop[0]["order"] == "0"

    def test_root_multiple_entries(self):
        """ROOT TABLE with multiple entries."""
        table_data = _make_table_data([
            ('"root"', '"id"', '"v1"', '"a1"', '"1"'),
            ('"child"', '"name"', '"v2"', '"a2"', '"2"'),
        ])
        node = _make_node(params={"ROOT": table_data})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        root = result.component["config"]["root"]
        assert len(root) == 2
        assert root[0]["path"] == "root"
        assert root[1]["path"] == "child"

    def test_generation_mode_custom(self):
        """GENERATION_MODE as CLOSED_LIST with value 'NULL'."""
        node = _make_node(params={"GENERATION_MODE": '"NULL"'})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["generation_mode"] == "NULL"

    def test_split_every_extracted(self):
        node = _make_node(params={"SPLIT_EVERY": "500"})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["split_every"] == "500"

    def test_dtd_name_extracted(self):
        node = _make_node(params={"DTD_NAME": '"MyRoot"'})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["dtd_name"] == "MyRoot"

    def test_dtd_systemid_extracted(self):
        node = _make_node(params={"DTD_SYSTEMID": '"custom.dtd"'})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["dtd_systemid"] == "custom.dtd"

    def test_xsl_type_extracted(self):
        node = _make_node(params={"XSL_TYPE": '"text/xml"'})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["xsl_type"] == "text/xml"

    def test_xsl_href_extracted(self):
        node = _make_node(params={"XSL_HREF": '"style.xsl"'})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["xsl_href"] == "style.xsl"

    def test_thousands_separator_extracted(self):
        node = _make_node(params={"THOUSANDS_SEPARATOR": '"."'})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == "."

    def test_decimal_separator_extracted(self):
        node = _make_node(params={"DECIMAL_SEPARATOR": '","'})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == ","

    def test_table_incomplete_stride_skipped(self):
        """Incomplete trailing group (< 5 entries) should be ignored."""
        table_data = _make_table_data([
            ('"root"', '"id"', '"val1"', '"attr1"', '"1"'),
        ])
        # Add incomplete trailing entry
        table_data.append({"elementRef": "PATH", "value": '"partial"'})
        node = _make_node(params={"ROOT": table_data})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        root = result.component["config"]["root"]
        assert len(root) == 1


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for SINK component."""

    def test_schema_input_populated(self):
        """Schema input should contain parsed columns (SINK per D-55)."""
        node = _make_node(schema=_make_schema_columns())
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert len(schema["input"]) == 2
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][1]["name"] == "name"

    def test_schema_output_empty(self):
        """Schema output should be empty for SINK component."""
        node = _make_node(schema=_make_schema_columns())
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []

    def test_schema_empty_when_no_flow(self):
        """When no schema provided, both should be empty."""
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_single_consolidated_needs_review(self):
        """Exactly 1 entry per D-51 (no engine)."""
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_severity(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_no_add_blank_line(self):
        """ADD_BLANK_LINE_AFTER_DECLARATION is phantom (not in _java.xml)."""
        node = _make_node(params={"ADD_BLANK_LINE_AFTER_DECLARATION": "true"})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert "add_blank_line_after_declaration" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        expected_keys = {
            # Core params
            "filename", "usestream", "streamname",
            "root", "group", "loop", "map",
            "merge", "pretty_compact",
            # Validation params
            "file_valid", "dtd_valid", "dtd_name", "dtd_systemid",
            "xsl_valid", "xsl_type", "xsl_href",
            # Advanced params
            "split", "split_every", "trim",
            "create", "create_empty_element",
            "add_empty_attribute", "add_unmapped_attribute",
            "add_document_as_node", "output_as_xsd",
            "advanced_separator", "thousands_separator", "decimal_separator",
            "generation_mode", "encoding", "delete_empty_file",
            # Framework params
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify the overall component dict structure."""

    def test_has_type(self):
        """type_name = tAdvancedFileOutputXML (no-engine per D-43)."""
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["type"] == "tAdvancedFileOutputXML"

    def test_has_id(self):
        node = _make_node(component_id="my_xml_out")
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["id"] == "my_xml_out"

    def test_has_original_type(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["original_type"] == "tAdvancedFileOutputXML"

    def test_has_position(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 320, "y": 160}

    def test_has_config_key(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema_key(self):
        node = _make_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        assert "schema" in result.component
