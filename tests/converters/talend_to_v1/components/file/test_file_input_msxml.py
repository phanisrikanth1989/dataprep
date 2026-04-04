"""Tests for FileInputMSXMLConverter (tFileInputMSXML -> tFileInputMSXML, no engine).

No engine implementation exists for tFileInputMSXML.
Red scorecard per D-37, single consolidated needs_review per D-27.
"""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_msxml import (
    FileInputMSXMLConverter,
    _parse_schemas,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="tFileInputMSXML_1",
               component_type="tFileInputMSXML"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 160, "y": 320},
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


def _make_schemas_table(rows):
    """Generate SCHEMAS TABLE data with stride-3 per row.

    rows: list of tuples (loop_path, mapping, create_empty_row)
    """
    result = []
    for loop_path, mapping, create_empty_row in rows:
        result.append({"elementRef": "LOOP_PATH", "value": loop_path})
        result.append({"elementRef": "MAPPING", "value": mapping})
        result.append({"elementRef": "CREATE_EMPTY_ROW", "value": create_empty_row})
    return result


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tFileInputMSXML") is FileInputMSXMLConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_filename_default(self):
        """Default filename is empty string."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_root_loop_query_default(self):
        """Default root_loop_query is /mailbox/emails/email."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["root_loop_query"] == "/mailbox/emails/email"

    def test_ignore_order_default(self):
        """Default ignore_order is False."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["ignore_order"] is False

    def test_die_on_error_default(self):
        """Default die_on_error is False."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_trim_all_default(self):
        """Default trim_all is True per _java.xml (NOT False)."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["trim_all"] is True

    def test_check_date_default(self):
        """Default check_date is False."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["check_date"] is False

    def test_ignore_dtd_default(self):
        """Default ignore_dtd is False."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["ignore_dtd"] is False

    def test_generation_mode_default(self):
        """Default generation_mode is DOM4J."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["generation_mode"] == "DOM4J"

    def test_encoding_default(self):
        """Default encoding is ISO-8859-15 per _java.xml (NOT UTF-8)."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_schemas_default(self):
        """Default schemas is empty list."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["schemas"] == []


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filename_extracted(self):
        """FILENAME is quote-stripped."""
        node = _make_node(params={"FILENAME": '"/data/input.xml"'})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "/data/input.xml"

    def test_root_loop_query_extracted(self):
        """ROOT_LOOP_QUERY is quote-stripped."""
        node = _make_node(params={"ROOT_LOOP_QUERY": '"/root/items/item"'})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["root_loop_query"] == "/root/items/item"

    def test_ignore_order_true(self):
        """IGNORE_ORDER extracted as True."""
        node = _make_node(params={"IGNORE_ORDER": "true"})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["ignore_order"] is True

    def test_die_on_error_true(self):
        """DIE_ON_ERROR extracted as True."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_trim_all_false(self):
        """TRIMALL can be set to false."""
        node = _make_node(params={"TRIMALL": "false"})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["trim_all"] is False

    def test_check_date_true(self):
        """CHECK_DATE extracted as True."""
        node = _make_node(params={"CHECK_DATE": "true"})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["check_date"] is True

    def test_ignore_dtd_true(self):
        """IGNORE_DTD extracted as True."""
        node = _make_node(params={"IGNORE_DTD": "true"})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["ignore_dtd"] is True

    def test_generation_mode_sax(self):
        """GENERATION_MODE extracted as SAX."""
        node = _make_node(params={"GENERATION_MODE": '"SAX"'})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["generation_mode"] == "SAX"

    def test_encoding_extracted(self):
        """ENCODING extracted with quotes stripped."""
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"


class TestSchemasTable:
    """Verify SCHEMAS TABLE parameter parsing."""

    def test_schemas_empty_when_missing(self):
        """Missing SCHEMAS param returns empty list."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["schemas"] == []

    def test_schemas_parsed(self):
        """SCHEMAS TABLE with LOOP_PATH, MAPPING, CREATE_EMPTY_ROW entries."""
        table_data = _make_schemas_table([
            ('"/emails/email/subject"', '"subject"', "false"),
            ('"/emails/email/body"', '"body"', "true"),
        ])
        node = _make_node(params={"SCHEMAS": table_data})
        result = FileInputMSXMLConverter().convert(node, [], {})
        schemas = result.component["config"]["schemas"]
        assert len(schemas) == 2
        assert schemas[0] == {"loop_path": "/emails/email/subject", "mapping": "subject", "create_empty_row": False}
        assert schemas[1] == {"loop_path": "/emails/email/body", "mapping": "body", "create_empty_row": True}

    def test_schemas_incomplete_stride_skipped(self):
        """Incomplete trailing group (< 3 entries) is skipped."""
        table_data = _make_schemas_table([
            ('"/path1"', '"col1"', "false"),
        ])
        # Add one orphan entry (incomplete stride)
        table_data.append({"elementRef": "LOOP_PATH", "value": '"/orphan"'})
        node = _make_node(params={"SCHEMAS": table_data})
        result = FileInputMSXMLConverter().convert(node, [], {})
        schemas = result.component["config"]["schemas"]
        assert len(schemas) == 1

    def test_schemas_none_input(self):
        """None SCHEMAS param returns empty list."""
        assert _parse_schemas(None) == []

    def test_schemas_non_list_input(self):
        """Non-list SCHEMAS param returns empty list."""
        assert _parse_schemas("not_a_list") == []


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for source component."""

    def test_output_schema_extracted(self):
        """Source component populates output schema."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputMSXMLConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]
        assert len(output_schema) == 2
        assert output_schema[0]["name"] == "id"
        assert output_schema[0]["key"] is True
        assert output_schema[1]["name"] == "name"
        assert output_schema[1]["length"] == 50

    def test_input_schema_always_empty(self):
        """Source component always has empty input schema."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_empty_when_no_flow(self):
        """No FLOW schema results in empty output."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries -- single consolidated per D-37 (no engine)."""

    def test_single_consolidated_entry(self):
        """No-engine component has exactly 1 consolidated needs_review entry per D-37."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_no_engine_message(self):
        """The needs_review entry mentions no engine implementation."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        entry = result.needs_review[0]
        assert "no" in entry["issue"].lower() or "No" in entry["issue"]
        assert "engine" in entry["issue"].lower()

    def test_severity_engine_gap(self):
        """Severity is engine_gap."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_has_component_id(self):
        """Entry has correct component_id."""
        node = _make_node(component_id="test_comp")
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params must NOT appear in needs_review."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """All 9 unique + 2 framework config keys present."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputMSXMLConverter().convert(node, [], {})
        expected_keys = {
            "filename", "root_loop_query", "ignore_order", "schemas",
            "die_on_error", "trim_all", "check_date", "ignore_dtd",
            "generation_mode", "encoding",
            "tstatcatcher_stats", "label",
        }
        actual_config_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_config_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify _build_component_dict output structure."""

    def test_type_is_talend_name(self):
        """No-engine component uses Talend name per D-43."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["type"] == "tFileInputMSXML"

    def test_original_type(self):
        """original_type matches component_type."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileInputMSXML"

    def test_has_required_top_level_keys(self):
        """Output dict has all required top-level keys from _build_component_dict."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected_keys

    def test_component_id(self):
        """Component ID matches node."""
        node = _make_node(component_id="msxml_1")
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["id"] == "msxml_1"

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_not_old_type_name(self):
        """Must NOT use old type_name FileInputMSXMLComponent."""
        node = _make_node()
        result = FileInputMSXMLConverter().convert(node, [], {})
        assert result.component["type"] != "FileInputMSXMLComponent"
