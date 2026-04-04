"""Tests for FileInputPositionalConverter (tFileInputPositional -> v1 FileInputPositional config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_positional import (
    FileInputPositionalConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="fip_1",
               component_type="tFileInputPositional"):
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
            SchemaColumn(name="created", type="id_Date", date_pattern="yyyy-MM-dd"),
        ]
    }


def _make_formats_data(rows):
    """Generate FORMATS TABLE data with stride-4 per row.

    rows: list of tuples (schema_column, size, padding_char, align)
    """
    result = []
    for schema_col, size, pad, align in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": schema_col})
        result.append({"elementRef": "SIZE", "value": size})
        result.append({"elementRef": "PADDING_CHAR", "value": pad})
        result.append({"elementRef": "ALIGN", "value": align})
    return result


def _make_trim_select_data(rows):
    """Generate TRIMSELECT TABLE data with stride-2 per row.

    rows: list of tuples (column, trim)
    """
    result = []
    for col, trim in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": col})
        result.append({"elementRef": "TRIM", "value": trim})
    return result


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        """tFileInputPositional maps to FileInputPositionalConverter in the registry."""
        assert REGISTRY.get("tFileInputPositional") is FileInputPositionalConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_filepath_default(self):
        """FILENAME defaults to empty string (config key 'filepath' per engine pattern)."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["filepath"] == ""

    def test_row_separator_default(self):
        """ROWSEPARATOR defaults to '\\n'."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["row_separator"] == "\\n"

    def test_advanced_option_default(self):
        """ADVANCED_OPTION defaults to False."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["advanced_option"] is False

    def test_pattern_default(self):
        """PATTERN defaults to '5,4,5' per _java.xml."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["pattern"] == "5,4,5"

    def test_pattern_units_default(self):
        """PATTERN_UNITS defaults to 'SYMBOLS'."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["pattern_units"] == "SYMBOLS"

    def test_remove_empty_row_default(self):
        """REMOVE_EMPTY_ROW defaults to True."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["remove_empty_row"] is True

    def test_uncompress_default(self):
        """UNCOMPRESS defaults to False."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["uncompress"] is False

    def test_die_on_error_default(self):
        """DIE_ON_ERROR defaults to False."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_header_rows_default(self):
        """HEADER defaults to 0."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["header_rows"] == 0

    def test_footer_rows_default(self):
        """FOOTER defaults to 0."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["footer_rows"] == 0

    def test_limit_default(self):
        """LIMIT defaults to empty string."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == ""

    def test_process_long_row_default(self):
        """PROCESS_LONG_ROW defaults to False."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["process_long_row"] is False

    def test_advanced_separator_default(self):
        """ADVANCED_SEPARATOR defaults to False."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        """THOUSANDS_SEPARATOR defaults to ','."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        """DECIMAL_SEPARATOR defaults to '.'."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."

    def test_trim_all_default(self):
        """TRIMALL defaults to True per _java.xml."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["trim_all"] is True

    def test_check_date_default(self):
        """CHECK_DATE defaults to False."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["check_date"] is False

    def test_encoding_default(self):
        """ENCODING defaults to 'ISO-8859-15' per _java.xml."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filepath_extracted(self):
        """Quoted FILENAME is extracted as 'filepath' config key."""
        node = _make_node(params={"FILENAME": '"/data/fixed_width.dat"'})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["filepath"] == "/data/fixed_width.dat"

    def test_row_separator_extracted(self):
        """Quoted ROWSEPARATOR is extracted with quotes stripped."""
        node = _make_node(params={"ROWSEPARATOR": '"\\r\\n"'})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["row_separator"] == "\\r\\n"

    def test_pattern_extracted(self):
        """Quoted PATTERN is extracted with quotes stripped."""
        node = _make_node(params={"PATTERN": '"10,20,30"'})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["pattern"] == "10,20,30"

    def test_pattern_units_extracted(self):
        """PATTERN_UNITS CLOSED_LIST value is extracted."""
        node = _make_node(params={"PATTERN_UNITS": '"BYTES"'})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["pattern_units"] == "BYTES"

    def test_advanced_option_true(self):
        """ADVANCED_OPTION 'true' is extracted as boolean True."""
        node = _make_node(params={"ADVANCED_OPTION": "true"})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["advanced_option"] is True

    def test_remove_empty_row_false(self):
        """REMOVE_EMPTY_ROW 'false' is extracted as boolean False."""
        node = _make_node(params={"REMOVE_EMPTY_ROW": "false"})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["remove_empty_row"] is False

    def test_trim_all_false(self):
        """TRIMALL 'false' is extracted as boolean False."""
        node = _make_node(params={"TRIMALL": "false"})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["trim_all"] is False

    def test_encoding_custom(self):
        """Quoted ENCODING value is extracted with quotes stripped."""
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_header_rows_extracted(self):
        """HEADER numeric value is extracted as int."""
        node = _make_node(params={"HEADER": "3"})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["header_rows"] == 3

    def test_footer_rows_extracted(self):
        """FOOTER numeric value is extracted as int."""
        node = _make_node(params={"FOOTER": "2"})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["footer_rows"] == 2

    def test_limit_extracted(self):
        """LIMIT is extracted as str for expression support."""
        node = _make_node(params={"LIMIT": '"500"'})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == "500"

    def test_die_on_error_true(self):
        """DIE_ON_ERROR 'true' is extracted as boolean True."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_process_long_row_true(self):
        """PROCESS_LONG_ROW 'true' is extracted as boolean True."""
        node = _make_node(params={"PROCESS_LONG_ROW": "true"})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["process_long_row"] is True

    def test_advanced_separator_true(self):
        """ADVANCED_SEPARATOR 'true' is extracted as boolean True."""
        node = _make_node(params={"ADVANCED_SEPARATOR": "true"})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is True

    def test_thousands_separator_custom(self):
        """Quoted THOUSANDS_SEPARATOR is extracted with quotes stripped."""
        node = _make_node(params={"THOUSANDS_SEPARATOR": '"."'})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == "."

    def test_decimal_separator_custom(self):
        """Quoted DECIMAL_SEPARATOR is extracted with quotes stripped."""
        node = _make_node(params={"DECIMAL_SEPARATOR": '","'})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == ","

    def test_check_date_true(self):
        """CHECK_DATE 'true' is extracted as boolean True."""
        node = _make_node(params={"CHECK_DATE": "true"})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["check_date"] is True

    def test_uncompress_true(self):
        """UNCOMPRESS 'true' is extracted as boolean True."""
        node = _make_node(params={"UNCOMPRESS": "true"})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["uncompress"] is True


class TestFormatsTable:
    """Verify FORMATS TABLE parameter parsing."""

    def test_formats_empty_when_missing(self):
        """FORMATS defaults to empty list when not present."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["formats"] == []

    def test_formats_parsed_correctly(self):
        """FORMATS TABLE with 3 rows is parsed into list of dicts."""
        fmt_data = _make_formats_data([
            ("id", "10", "' '", "'L'"),
            ("name", "50", "' '", "'R'"),
            ("city", "30", "'*'", "'C'"),
        ])
        node = _make_node(params={"FORMATS": fmt_data})
        result = FileInputPositionalConverter().convert(node, [], {})
        fmts = result.component["config"]["formats"]

        assert len(fmts) == 3
        assert fmts[0] == {"schema_column": "id", "size": "10", "padding_char": "' '", "align": "'L'"}
        assert fmts[1] == {"schema_column": "name", "size": "50", "padding_char": "' '", "align": "'R'"}
        assert fmts[2] == {"schema_column": "city", "size": "30", "padding_char": "'*'", "align": "'C'"}

    def test_formats_partial_entries(self):
        """FORMATS entries with only SCHEMA_COLUMN and SIZE still parse."""
        data = [
            {"elementRef": "SCHEMA_COLUMN", "value": "code"},
            {"elementRef": "SIZE", "value": "5"},
        ]
        node = _make_node(params={"FORMATS": data})
        result = FileInputPositionalConverter().convert(node, [], {})
        fmts = result.component["config"]["formats"]

        assert len(fmts) == 1
        assert fmts[0]["schema_column"] == "code"
        assert fmts[0]["size"] == "5"


class TestTrimSelectTable:
    """Verify TRIMSELECT TABLE parameter parsing."""

    def test_trim_select_empty_when_missing(self):
        """TRIMSELECT defaults to empty list when not present."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["trim_select"] == []

    def test_trim_select_parsed_correctly(self):
        """TRIMSELECT TABLE with 3 rows is parsed into list of dicts."""
        data = _make_trim_select_data([
            ("id", "true"),
            ("name", "false"),
            ("city", "true"),
        ])
        node = _make_node(params={"TRIMSELECT": data})
        result = FileInputPositionalConverter().convert(node, [], {})
        trims = result.component["config"]["trim_select"]

        assert len(trims) == 3
        assert trims[0] == {"column": "id", "trim": True}
        assert trims[1] == {"column": "name", "trim": False}
        assert trims[2] == {"column": "city", "trim": True}


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """TSTATCATCHER_STATS defaults to False."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS 'true' is extracted as boolean True."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """LABEL defaults to empty string."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """Quoted LABEL value is extracted with quotes stripped."""
        node = _make_node(params={"LABEL": '"positional_read"'})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "positional_read"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_is_dict_with_input_output(self):
        """Schema is a dict with 'input' and 'output' keys per D-41."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputPositionalConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert isinstance(schema, dict)
        assert "input" in schema
        assert "output" in schema

    def test_schema_input_empty(self):
        """FileInputPositional is a source component -- input schema is always empty."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_output_populated(self):
        """Output schema is populated when node has FLOW schema columns."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputPositionalConverter().convert(node, [], {})
        output = result.component["schema"]["output"]
        assert len(output) == 3
        assert output[0]["name"] == "id"
        assert output[0]["key"] is True
        assert output[0]["nullable"] is False
        assert output[1]["name"] == "name"
        assert output[1]["length"] == 50
        assert output[2]["name"] == "created"
        assert output[2]["date_pattern"] == "%Y-%m-%d"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps (per D-36: per-feature)."""

    def test_needs_review_count(self):
        """Needs_review entries cover engine gaps for key features."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        # At minimum: process_long_row, uncompress, advanced_separator, check_date,
        # trim_select, encoding, formats
        assert len(result.needs_review) >= 5

    def test_needs_review_process_long_row(self):
        """One needs_review entry mentions 'process_long_row'."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("process_long_row" in i for i in issues)

    def test_needs_review_uncompress(self):
        """One needs_review entry mentions 'uncompress'."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("uncompress" in i for i in issues)

    def test_needs_review_check_date(self):
        """One needs_review entry mentions 'check_date'."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("check_date" in i for i in issues)

    def test_needs_review_encoding(self):
        """One needs_review entry mentions 'encoding' engine default mismatch."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("encoding" in i for i in issues)

    def test_all_needs_review_are_engine_gap(self):
        """All needs_review entries have severity 'engine_gap'."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries include the component ID."""
        node = _make_node(component_id="fip_test")
        result = FileInputPositionalConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "fip_test"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify USE_BYTE is NOT extracted -- engine does not read it."""

    def test_use_byte_not_in_config(self):
        """USE_BYTE is excluded from config -- engine reads PATTERN_UNITS instead."""
        node = _make_node(params={"USE_BYTE": "true"})
        result = FileInputPositionalConverter().convert(node, [], {})
        assert "use_byte" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config dict contains all expected keys (18 unique + 2 framework)."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputPositionalConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "filepath", "row_separator", "pattern", "pattern_units",
            "advanced_option", "remove_empty_row", "trim_all", "encoding",
            "header_rows", "footer_rows", "limit", "die_on_error",
            "process_long_row", "advanced_separator", "thousands_separator",
            "decimal_separator", "check_date", "uncompress",
            "formats", "trim_select",
            "tstatcatcher_stats", "label",
        }
        missing = expected_keys - set(cfg.keys())
        assert not missing, f"Missing config keys: {missing}"

    def test_no_unexpected_keys(self):
        """Config dict does not contain phantom params like use_byte."""
        node = _make_node(params={"USE_BYTE": "true"})
        result = FileInputPositionalConverter().convert(node, [], {})
        cfg = result.component["config"]
        unexpected = {"use_byte"}
        found = unexpected & set(cfg.keys())
        assert not found, f"Unexpected config keys: {found}"


class TestComponentStructure:
    """Verify _build_component_dict output structure."""

    def test_has_id(self):
        """Component dict has 'id' matching node.component_id."""
        node = _make_node(component_id="fip_42")
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["id"] == "fip_42"

    def test_has_type(self):
        """Component dict has 'type' == 'FileInputPositional' (engine class name per D-43)."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["type"] == "FileInputPositional"

    def test_has_original_type(self):
        """Component dict has 'original_type' == 'tFileInputPositional'."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileInputPositional"

    def test_has_config(self):
        """Component dict has 'config' key."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema(self):
        """Component dict has 'schema' key."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert "schema" in result.component

    def test_has_position(self):
        """Component dict has 'position' key."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_has_inputs_outputs(self):
        """Component dict has 'inputs' and 'outputs' keys (empty lists)."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node()
        result = FileInputPositionalConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
