"""Tests for AdvancedFileOutputXmlConverter (tAdvancedFileOutputXML) and
FileOutputXMLConverter (tFileOutputXML). Phase 12-06 adds TestFileOutputXMLSimple.
"""
import xml.etree.ElementTree as ET

import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_output_xml import (
    AdvancedFileOutputXmlConverter,
    FileOutputXMLConverter,
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


# ==================================================================
# TestFileOutputXMLSimple -- Phase 12-06
# Tests for the new FileOutputXMLConverter (simple/flat tFileOutputXML)
# ==================================================================


def _make_simple_node(params=None, schema=None, component_id="fo_xml_1"):
    """Create a TalendNode for simple tFileOutputXML testing."""
    return TalendNode(
        component_id=component_id,
        component_type="tFileOutputXML",
        params=params or {},
        schema=schema or {},
        position={"x": 200, "y": 100},
        raw_xml=ET.Element("node"),
    )


def _make_simple_schema():
    """Return a sample FLOW schema for simple tFileOutputXML testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_String", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
        ]
    }


def _make_mapping_data(rows):
    """Generate MAPPING TABLE data (stride-2: SCHEMA_COLUMN_NAME, AS_ATTRIBUTE).

    Args:
        rows: List of (column_name, as_attribute_str) tuples.
    """
    result = []
    for col_name, as_attr in rows:
        result.append({"elementRef": "SCHEMA_COLUMN_NAME", "value": col_name})
        result.append({"elementRef": "AS_ATTRIBUTE", "value": as_attr})
    return result


def _make_root_tags_data(names):
    """Generate ROOT_TAGS TABLE data (stride-1: VALUE)."""
    return [{"elementRef": "VALUE", "value": f'"{name}"'} for name in names]


def _make_groupby_data(rows):
    """Generate GROUP_BY TABLE data (stride-2: COLUMN, LABEL)."""
    result = []
    for col, label in rows:
        result.append({"elementRef": "COLUMN", "value": col})
        result.append({"elementRef": "LABEL", "value": label})
    return result


@pytest.mark.unit
class TestFileOutputXMLSimple:
    """Tests for the new FileOutputXMLConverter (Phase 12-06).

    Per D-D1: each parameter gets at least one positive test.
    Existing AdvancedFileOutputXmlConverter tests above are untouched.
    """

    def test_registered(self):
        """Test 1: REGISTRY.get('tFileOutputXML') resolves to FileOutputXMLConverter."""
        assert REGISTRY.get("tFileOutputXML") is FileOutputXMLConverter

    def test_filename_extracted(self):
        """Test 2: FILENAME param maps to config['filename']."""
        node = _make_simple_node(params={"FILENAME": '"out.xml"'})
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "out.xml"

    def test_row_tag_default(self):
        """Test 3a: ROW_TAG defaults to 'row'."""
        node = _make_simple_node()
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["row_tag"] == "row"

    def test_row_tag_override(self):
        """Test 3b: ROW_TAG explicit override honored."""
        node = _make_simple_node(params={"ROW_TAG": '"record"'})
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["row_tag"] == "record"

    def test_encoding_default_iso(self):
        """Test 4: ENCODING defaults to ISO-8859-15 (NOT UTF-8)."""
        node = _make_simple_node()
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_split_every_default(self):
        """Test 5a: SPLIT_EVERY defaults to '1000' (string)."""
        node = _make_simple_node()
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["split_every"] == "1000"

    def test_split_default_false(self):
        """Test 5b: SPLIT defaults to False."""
        node = _make_simple_node()
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["split"] is False

    def test_create_default_true(self):
        """Test 6: CREATE defaults to True (Talend default = overwrite)."""
        node = _make_simple_node()
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["create"] is True

    def test_mapping_parsed_as_attribute_true(self):
        """Test 7a: MAPPING TABLE parses to list[{column, as_attribute}]; AS_ATTRIBUTE='true' -> True."""
        mapping_data = _make_mapping_data([("id", "true"), ("name", "false")])
        node = _make_simple_node(params={"MAPPING": mapping_data})
        result = FileOutputXMLConverter().convert(node, [], {})
        mapping = result.component["config"]["mapping"]
        assert len(mapping) == 2
        assert mapping[0]["column"] == "id"
        assert mapping[0]["as_attribute"] is True
        assert mapping[1]["column"] == "name"
        assert mapping[1]["as_attribute"] is False

    def test_root_tags_parsed(self):
        """Test 8: ROOT_TAGS TABLE parses to list of {name: str} dicts."""
        root_data = _make_root_tags_data(["wrapper"])
        node = _make_simple_node(params={"ROOT_TAGS": root_data})
        result = FileOutputXMLConverter().convert(node, [], {})
        root_tags = result.component["config"]["root_tags"]
        assert len(root_tags) == 1
        assert root_tags[0]["name"] == "wrapper"

    def test_groupby_parsed(self):
        """Test 9: GROUP_BY TABLE parses to list[{column, label}]."""
        groupby_data = _make_groupby_data([("country", "Country")])
        node = _make_simple_node(params={"GROUP_BY": groupby_data})
        result = FileOutputXMLConverter().convert(node, [], {})
        group_by = result.component["config"]["group_by"]
        assert len(group_by) == 1
        assert group_by[0]["column"] == "country"
        assert group_by[0]["label"] == "Country"

    def test_input_is_document_extracted(self):
        """Test 10a: INPUT_IS_DOCUMENT=true extracted correctly."""
        node = _make_simple_node(params={"INPUT_IS_DOCUMENT": "true"})
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["input_is_document"] is True

    def test_document_col_extracted(self):
        """Test 10b: DOCUMENT_COL extracted."""
        node = _make_simple_node(params={"DOCUMENT_COL": '"doc"'})
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["document_col"] == "doc"

    def test_flushonrow_extracted(self):
        """Test 11a: FLUSHONROW=true extracted correctly."""
        node = _make_simple_node(params={"FLUSHONROW": "true"})
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["flushonrow"] is True

    def test_flushonrow_num_extracted(self):
        """Test 11b: FLUSHONROW_NUM extracted as string."""
        node = _make_simple_node(params={"FLUSHONROW_NUM": "5"})
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["flushonrow_num"] == "5"

    def test_tstatcatcher_stats_extracted(self):
        """Test 12: TSTATCATCHER_STATS extracted as bool framework param."""
        node = _make_simple_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        """Test 13: LABEL extracted as str framework param."""
        node = _make_simple_node(params={"LABEL": '"my_label"'})
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"

    def test_schema_input_populated_output_empty(self):
        """Test 14: Schema input populated; output empty (sink semantics S-5)."""
        node = _make_simple_node(schema=_make_simple_schema())
        result = FileOutputXMLConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert len(schema["input"]) == 2
        assert schema["output"] == []

    def test_warnings_and_needs_review_empty(self):
        """Test 15: warnings and needs_review are empty for simple FileOutputXMLConverter."""
        node = _make_simple_node(params={"FILENAME": '"out.xml"'})
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.warnings == []
        assert result.needs_review == []

    def test_type_name_is_file_output_xml(self):
        """Component type should map to engine class 'FileOutputXML'."""
        node = _make_simple_node()
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["type"] == "FileOutputXML"

    def test_all_core_config_keys_present(self):
        """All 18 javajet + 2 framework config keys must be present."""
        node = _make_simple_node(schema=_make_simple_schema())
        result = FileOutputXMLConverter().convert(node, [], {})
        expected_keys = {
            "filename", "input_is_document", "document_col", "row_tag",
            "root_tags", "mapping", "use_dynamic_grouping", "group_by",
            "flushonrow", "flushonrow_num", "encoding", "split", "split_every",
            "create", "trim", "advanced_separator", "thousands_separator",
            "decimal_separator", "delete_empty_file",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_delete_empty_file_default_false(self):
        """DELETE_EMPTYFILE defaults to False."""
        node = _make_simple_node()
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["delete_empty_file"] is False

    def test_trim_default_false(self):
        """TRIM defaults to False."""
        node = _make_simple_node()
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["trim"] is False

    def test_advanced_separator_default_false(self):
        """ADVANCED_SEPARATOR defaults to False."""
        node = _make_simple_node()
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        """THOUSANDS_SEPARATOR defaults to ','."""
        node = _make_simple_node()
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        """DECIMAL_SEPARATOR defaults to '.'."""
        node = _make_simple_node()
        result = FileOutputXMLConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."


# ==================================================================
# TestAdvancedFileOutputXmlConverterConditionalNeedsReview -- Phase 12-07
# D-E1 lock-in: the 6 deferred sub-features each emit needs_review when active.
# ==================================================================


def _make_advanced_node(params=None, component_id="xml_adv_1"):
    """Create a TalendNode for AdvancedFileOutputXmlConverter D-E1 testing.

    Accepts params dict with uppercase keys that map to node.params directly
    (matching the _get_bool / _get_str converter helper expectations).
    """
    return TalendNode(
        component_id=component_id,
        component_type="tAdvancedFileOutputXML",
        params=params or {},
        schema={},
        position={"x": 320, "y": 160},
        raw_xml=__import__("xml.etree.ElementTree", fromlist=["Element"]).Element("node"),
    )


@pytest.mark.unit
class TestAdvancedFileOutputXmlConverterConditionalNeedsReview:
    """D-E1 lock-in (Phase 12-07): the 6 deferred sub-features each emit needs_review.

    Each test verifies that the conditional needs_review block fires (or does NOT fire)
    based on the relevant config flags. The baseline engine_gap entry is always present,
    so counts are baseline + conditional_count.
    """

    def test_dtd_validation_emitted_when_both_flags_true(self):
        """Test 1: file_valid=True AND dtd_valid=True -> dtd_validation needs_review."""
        node = _make_advanced_node(params={"FILE_VALID": "true", "DTD_VALID": "true"})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        entries = [e for e in result.needs_review if e.get("feature") == "dtd_validation"]
        assert len(entries) == 1

    def test_dtd_validation_not_emitted_when_file_valid_false(self):
        """Test 2: file_valid=False -> NO dtd_validation entry (both flags must be true)."""
        node = _make_advanced_node(params={"FILE_VALID": "false", "DTD_VALID": "true"})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        entries = [e for e in result.needs_review if e.get("feature") == "dtd_validation"]
        assert len(entries) == 0

    def test_xsl_validation_emitted_when_both_flags_true(self):
        """Test 3: file_valid=True AND xsl_valid=True -> xsl_validation needs_review."""
        node = _make_advanced_node(params={"FILE_VALID": "true", "XSL_VALID": "true"})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        entries = [e for e in result.needs_review if e.get("feature") == "xsl_validation"]
        assert len(entries) == 1

    def test_xsl_validation_not_emitted_when_file_valid_false(self):
        """Test 4: file_valid=False -> NO xsl_validation entry."""
        node = _make_advanced_node(params={"FILE_VALID": "false", "XSL_VALID": "true"})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        entries = [e for e in result.needs_review if e.get("feature") == "xsl_validation"]
        assert len(entries) == 0

    def test_output_as_xsd_emitted_when_true(self):
        """Test 5: output_as_xsd=True -> output_as_xsd needs_review."""
        node = _make_advanced_node(params={"OUTPUT_AS_XSD": "true"})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        entries = [e for e in result.needs_review if e.get("feature") == "output_as_xsd"]
        assert len(entries) == 1

    def test_add_document_as_node_emitted_when_true(self):
        """Test 6: add_document_as_node=True -> add_document_as_node needs_review."""
        node = _make_advanced_node(params={"ADD_DOCUMENT_AS_NODE": "true"})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        entries = [e for e in result.needs_review if e.get("feature") == "add_document_as_node"]
        assert len(entries) == 1

    def test_add_unmapped_attribute_emitted_when_true(self):
        """Test 7: add_unmapped_attribute=True -> add_unmapped_attribute needs_review."""
        node = _make_advanced_node(params={"ADD_UNMAPPED_ATTRIBUTE": "true"})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        entries = [e for e in result.needs_review if e.get("feature") == "add_unmapped_attribute"]
        assert len(entries) == 1

    def test_merge_emitted_when_true(self):
        """Test 8: merge=True -> merge needs_review."""
        node = _make_advanced_node(params={"MERGE": "true"})
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        entries = [e for e in result.needs_review if e.get("feature") == "merge"]
        assert len(entries) == 1

    def test_no_conditional_entries_when_no_flags_set(self):
        """Test 9 (partial): no conditional D-E1 entries when all flags are at defaults."""
        node = _make_advanced_node()
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        conditional_entries = [e for e in result.needs_review if e.get("feature")]
        assert len(conditional_entries) == 0

    def test_all_six_entries_when_all_flags_set(self):
        """Test 10: all 6 flags set -> exactly 6 conditional needs_review entries."""
        node = _make_advanced_node(params={
            "FILE_VALID": "true",
            "DTD_VALID": "true",
            "XSL_VALID": "true",
            "OUTPUT_AS_XSD": "true",
            "ADD_DOCUMENT_AS_NODE": "true",
            "ADD_UNMAPPED_ATTRIBUTE": "true",
            "MERGE": "true",
        })
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        conditional_entries = [e for e in result.needs_review if e.get("feature")]
        assert len(conditional_entries) == 6

    def test_each_entry_has_phase_key(self):
        """Test 11: every D-E1 needs_review entry has 'phase' == '12'."""
        node = _make_advanced_node(params={
            "FILE_VALID": "true",
            "DTD_VALID": "true",
        })
        result = AdvancedFileOutputXmlConverter().convert(node, [], {})
        for entry in result.needs_review:
            if entry.get("feature"):
                assert entry.get("phase") == "12"
