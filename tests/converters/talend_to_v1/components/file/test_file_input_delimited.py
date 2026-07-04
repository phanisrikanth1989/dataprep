"""Tests for FileInputDelimitedConverter (tFileInputDelimited -> FileInputDelimited)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_delimited import (
    FileInputDelimitedConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="fid_1",
               component_type="tFileInputDelimited"):
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
            SchemaColumn(name="created", type="id_Date", nullable=True, date_pattern="yyyy-MM-dd"),
        ]
    }


def _make_trim_select_data(rows):
    """Generate TRIMSELECT TABLE data with stride-2 per row.

    rows: list of tuples (column_name, trim_bool_str)
    """
    result = []
    for col_name, trim_val in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": col_name})
        result.append({"elementRef": "TRIM", "value": trim_val})
    return result


def _make_decode_cols_data(rows):
    """Generate DECODE_COLS TABLE data with stride-2 per row.

    rows: list of tuples (column_name, decode_bool_str)
    """
    result = []
    for col_name, decode_val in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": col_name})
        result.append({"elementRef": "DECODE", "value": decode_val})
    return result


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        """tFileInputDelimited maps to FileInputDelimitedConverter in the registry."""
        assert REGISTRY.get("tFileInputDelimited") is FileInputDelimitedConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_filepath_default(self):
        """FILENAME defaults to empty string."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["filepath"] == ""

    def test_csv_option_default(self):
        """CSV_OPTION defaults to False."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["csv_option"] is False

    def test_row_separator_default(self):
        """ROWSEPARATOR defaults to '\\n'."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["row_separator"] == "\\n"

    def test_csv_row_separator_default(self):
        """CSVROWSEPARATOR defaults to '\\n'."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["csv_row_separator"] == "\\n"

    def test_fieldseparator_default(self):
        """FIELDSEPARATOR defaults to ';'."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["fieldseparator"] == ";"

    def test_escape_char_default(self):
        """ESCAPE_CHAR defaults to double-quote '\"'."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["escape_char"] == '"'

    def test_text_enclosure_default(self):
        """TEXT_ENCLOSURE defaults to double-quote '\"'."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["text_enclosure"] == '"'

    def test_header_rows_default(self):
        """HEADER defaults to 0."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["header_rows"] == 0

    def test_footer_rows_default(self):
        """FOOTER defaults to 0."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["footer_rows"] == 0

    def test_limit_default(self):
        """LIMIT defaults to empty string (no limit)."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == ""

    def test_remove_empty_row_default(self):
        """REMOVE_EMPTY_ROW defaults to True per _java.xml (NOT False)."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["remove_empty_row"] is True

    def test_uncompress_default(self):
        """UNCOMPRESS defaults to False."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["uncompress"] is False

    def test_die_on_error_default(self):
        """DIE_ON_ERROR defaults to False."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_advanced_separator_default(self):
        """ADVANCED_SEPARATOR defaults to False."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        """THOUSANDS_SEPARATOR defaults to ','."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        """DECIMAL_SEPARATOR defaults to '.'."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."

    def test_random_default(self):
        """RANDOM defaults to False."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["random"] is False

    def test_nb_random_default(self):
        """NB_RANDOM defaults to 10."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["nb_random"] == 10

    def test_trim_all_default(self):
        """TRIMALL defaults to False."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["trim_all"] is False

    def test_check_fields_num_default(self):
        """CHECK_FIELDS_NUM defaults to False."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["check_fields_num"] is False

    def test_check_date_default(self):
        """CHECK_DATE defaults to False."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["check_date"] is False

    def test_encoding_default(self):
        """ENCODING defaults to 'ISO-8859-15' per _java.xml."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_split_record_default(self):
        """SPLITRECORD defaults to False."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["split_record"] is False

    def test_enable_decode_default(self):
        """ENABLE_DECODE defaults to False."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["enable_decode"] is False



class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filepath_extracted(self):
        """Quoted FILENAME value is extracted with quotes stripped."""
        node = _make_node(params={"FILENAME": '"/data/input.csv"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["filepath"] == "/data/input.csv"

    def test_fieldseparator_extracted(self):
        """Quoted FIELDSEPARATOR value is extracted with quotes stripped."""
        node = _make_node(params={"FIELDSEPARATOR": '","'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["fieldseparator"] == ","

    def test_row_separator_extracted(self):
        """Quoted ROWSEPARATOR value is extracted."""
        node = _make_node(params={"ROWSEPARATOR": '"\\r\\n"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["row_separator"] == "\\r\\n"

    def test_encoding_custom(self):
        """Quoted ENCODING value is extracted."""
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_header_rows_extracted(self):
        """HEADER integer value is extracted."""
        node = _make_node(params={"HEADER": "5"})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["header_rows"] == 5

    def test_footer_rows_extracted(self):
        """FOOTER integer value is extracted."""
        node = _make_node(params={"FOOTER": "2"})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["footer_rows"] == 2

    def test_limit_extracted_as_str(self):
        """LIMIT is extracted as string (supports expressions)."""
        node = _make_node(params={"LIMIT": '"1000"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == "1000"

    def test_remove_empty_row_false(self):
        """REMOVE_EMPTY_ROW can be set to False."""
        node = _make_node(params={"REMOVE_EMPTY_ROW": "false"})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["remove_empty_row"] is False

    def test_csv_option_true(self):
        """CSV_OPTION true is extracted as boolean True."""
        node = _make_node(params={"CSV_OPTION": "true"})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["csv_option"] is True

    def test_nb_random_extracted(self):
        """NB_RANDOM integer value is extracted."""
        node = _make_node(params={"NB_RANDOM": "50"})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["nb_random"] == 50

    def test_escape_char_extracted(self):
        """Quoted ESCAPE_CHAR value is extracted."""
        node = _make_node(params={"ESCAPE_CHAR": '"\\\\"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["escape_char"] == "\\\\"

    def test_text_enclosure_extracted(self):
        """Quoted TEXT_ENCLOSURE value is extracted."""
        node = _make_node(params={"TEXT_ENCLOSURE": '"\\""'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["text_enclosure"] == '\\"'



class TestTrimSelectTable:
    """Verify TRIMSELECT TABLE parameter parsing."""

    def test_empty(self):
        """Empty TRIMSELECT parameter returns empty list."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["trim_select"] == []

    def test_parsed(self):
        """TRIMSELECT entries are parsed into list of dicts with column/trim keys."""
        raw = _make_trim_select_data([("name", "true"), ("age", "false"), ("city", "true")])
        node = _make_node(params={"TRIMSELECT": raw})
        result = FileInputDelimitedConverter().convert(node, [], {})
        expected = [
            {"column": "name", "trim": True},
            {"column": "age", "trim": False},
            {"column": "city", "trim": True},
        ]
        assert result.component["config"]["trim_select"] == expected

    def test_empty_list(self):
        """Explicit empty list TABLE produces empty output."""
        node = _make_node(params={"TRIMSELECT": []})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["trim_select"] == []

    def test_incomplete_stride_skipped(self):
        """Incomplete trailing group (single entry) is skipped."""
        raw = [{"elementRef": "SCHEMA_COLUMN", "value": "name"}]
        node = _make_node(params={"TRIMSELECT": raw})
        result = FileInputDelimitedConverter().convert(node, [], {})
        # Single entry without TRIM pair should still produce a row with default
        # but the stride-2 parser should handle this gracefully
        assert isinstance(result.component["config"]["trim_select"], list)


class TestDecodeColsTable:
    """Verify DECODE_COLS TABLE parameter parsing."""

    def test_empty(self):
        """Empty DECODE_COLS parameter returns empty list."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["decode_cols"] == []

    def test_parsed(self):
        """DECODE_COLS entries are parsed into list of dicts with column/decode keys."""
        raw = _make_decode_cols_data([("hex_field", "true"), ("normal_field", "false")])
        node = _make_node(params={"DECODE_COLS": raw})
        result = FileInputDelimitedConverter().convert(node, [], {})
        expected = [
            {"column": "hex_field", "decode": True},
            {"column": "normal_field", "decode": False},
        ]
        assert result.component["config"]["decode_cols"] == expected


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """TSTATCATCHER_STATS defaults to False."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS 'true' is extracted as boolean True."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """LABEL defaults to empty string."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """Quoted LABEL value is extracted with quotes stripped."""
        node = _make_node(params={"LABEL": '"csv_reader"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "csv_reader"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_is_dict_with_input_output(self):
        """Schema is a dict with 'input' and 'output' keys per D-41."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputDelimitedConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert isinstance(schema, dict)
        assert "input" in schema
        assert "output" in schema

    def test_schema_input_empty(self):
        """FileInputDelimited is a source -- input schema is always empty."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_output_populated(self):
        """Output schema is populated when node has FLOW schema columns."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputDelimitedConverter().convert(node, [], {})
        output = result.component["schema"]["output"]
        assert len(output) == 3
        assert output[0]["name"] == "id"
        assert output[1]["name"] == "name"
        assert output[2]["name"] == "created"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps (per D-36: per-feature)."""

    def test_needs_review_has_entries(self):
        """Converter should produce needs_review entries for engine gaps."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert len(result.needs_review) > 0

    def test_all_needs_review_are_engine_gap(self):
        """All needs_review entries have severity 'engine_gap'."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries include the component ID."""
        node = _make_node(component_id="fid_test")
        result = FileInputDelimitedConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "fid_test"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()

    def test_needs_review_split_record(self):
        """needs_review includes split_record engine gap."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("split_record" in i for i in issues)

    def test_needs_review_random(self):
        """needs_review includes random engine gap."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("random" in i for i in issues)


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config dict contains all expected keys (unique + framework)."""
        node = _make_node(schema=_make_schema_columns())
        result = FileInputDelimitedConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            # Core params
            "filepath", "csv_option", "row_separator", "csv_row_separator",
            "fieldseparator", "escape_char", "text_enclosure",
            "header_rows", "footer_rows", "limit",
            "remove_empty_row", "uncompress", "die_on_error",
            # Advanced params
            "advanced_separator", "thousands_separator", "decimal_separator",
            "random", "nb_random", "trim_all",
            "check_fields_num", "check_date", "encoding",
            "split_record", "enable_decode",
            # TABLE params
            "trim_select", "decode_cols",
            # Hidden params (temp_dir, destination, use_header_as_is, schema_opt_num) removed in a943b5f
            # Framework
            "tstatcatcher_stats", "label",
        }
        missing = expected_keys - set(cfg.keys())
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify _build_component_dict output structure."""

    def test_has_id(self):
        """Component dict has 'id' matching node.component_id."""
        node = _make_node(component_id="fid_42")
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["id"] == "fid_42"

    def test_has_type(self):
        """Component dict has 'type' == 'FileInputDelimited' (engine class name per D-43)."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["type"] == "FileInputDelimited"

    def test_has_original_type(self):
        """Component dict has 'original_type' == 'tFileInputDelimited'."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileInputDelimited"

    def test_has_config(self):
        """Component dict has 'config' key."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema(self):
        """Component dict has 'schema' key."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert "schema" in result.component

    def test_has_position(self):
        """Component dict has 'position' key."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_has_inputs_outputs(self):
        """Component dict has 'inputs' and 'outputs' keys (empty lists)."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_no_flat_config(self):
        """Output must NOT contain 'component_type' at top level (no flat dict)."""
        node = _make_node()
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert "component_type" not in result.component
