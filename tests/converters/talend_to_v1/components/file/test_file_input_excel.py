"""Tests for FileInputExcelConverter (tFileInputExcel -> FileInputExcel)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_excel import (
    FileInputExcelConverter,
    _parse_date_select,
    _parse_sheetlist,
    _parse_trim_select,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="tFileInputExcel_1",
               component_type="tFileInputExcel"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 256, "y": 128},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
            SchemaColumn(name="sale_date", type="id_Date", date_pattern="yyyy-MM-dd"),
        ]
    }


def _make_sheetlist_data(rows):
    """Generate SHEETLIST TABLE data with stride-2 (SHEETNAME, USE_REGEX).

    rows: list of tuples (sheetname, use_regex_str)
    """
    result = []
    for sheetname, use_regex in rows:
        result.append({"elementRef": "SHEETNAME", "value": sheetname})
        result.append({"elementRef": "USE_REGEX", "value": use_regex})
    return result


def _make_trim_select_data(rows):
    """Generate TRIMSELECT TABLE data with stride-2 (SCHEMA_COLUMN, TRIM).

    rows: list of tuples (column, trim_str)
    """
    result = []
    for column, trim in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": column})
        result.append({"elementRef": "TRIM", "value": trim})
    return result


def _make_date_select_data(rows):
    """Generate DATESELECT TABLE data with stride-3 (SCHEMA_COLUMN, CONVERTDATE, PATTERN).

    rows: list of tuples (column, convertdate_str, pattern_str)
    """
    result = []
    for column, convertdate, pattern in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": column})
        result.append({"elementRef": "CONVERTDATE", "value": convertdate})
        result.append({"elementRef": "PATTERN", "value": pattern})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tFileInputExcel") is FileInputExcelConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_version_2007_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["version_2007"] is False

    def test_filepath_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["filepath"] == ""

    def test_filepath_java_expression_marked(self):
        node = _make_node(params={"FILENAME": '"context.dir + \'/report.xlsx\'"'})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["filepath"].startswith("{{java}}")

    def test_password_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["password"] == ""

    def test_all_sheets_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["all_sheets"] is False

    def test_header_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["header"] == 0

    def test_footer_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["footer"] == 0

    def test_limit_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == ""

    def test_affect_each_sheet_default(self):
        """AFFECT_EACH_SHEET defaults to empty string (TEXT type)."""
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["affect_each_sheet"] == ""

    def test_first_column_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["first_column"] == 1

    def test_last_column_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["last_column"] == ""

    def test_die_on_error_default(self):
        """DIE_ON_ERROR defaults to False per _java.xml (NOT True)."""
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_advanced_separator_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."

    def test_trimall_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["trimall"] is False

    def test_convertdatetostring_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["convertdatetostring"] is False

    def test_encoding_default(self):
        """ENCODING defaults to ISO-8859-15 per _java.xml (NOT UTF-8)."""
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_read_real_value_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["read_real_value"] is False

    def test_stopread_on_emptyrow_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["stopread_on_emptyrow"] is False

    def test_novalidate_on_cell_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["novalidate_on_cell"] is False

    def test_suppress_warn_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["suppress_warn"] is False

    def test_generation_mode_default(self):
        """GENERATION_MODE defaults to USER_MODE per _java.xml (NOT EVENT_MODE)."""
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["generation_mode"] == "USER_MODE"

    def test_include_phoneticruns_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["include_phoneticruns"] is True

    def test_configure_inflation_ratio_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["configure_inflation_ratio"] is False

    def test_inflation_ratio_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["inflation_ratio"] == ""

    def test_sheetlist_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["sheetlist"] == []

    def test_trim_select_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["trim_select"] == []

    def test_date_select_default(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["date_select"] == []


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filepath_extracted(self):
        node = _make_node(params={"FILENAME": '"/data/report.xlsx"'})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["filepath"] == "/data/report.xlsx"

    def test_version_2007_true(self):
        node = _make_node(params={"VERSION_2007": "true"})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["version_2007"] is True

    def test_password_extracted(self):
        """PASSWORD is always cleared to empty string for security."""
        node = _make_node(params={"PASSWORD": '"secret"'})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["password"] == ""

    def test_all_sheets_true(self):
        node = _make_node(params={"ALL_SHEETS": "true"})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["all_sheets"] is True

    def test_header_extracted(self):
        node = _make_node(params={"HEADER": "5"})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["header"] == 5

    def test_footer_extracted(self):
        node = _make_node(params={"FOOTER": "2"})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["footer"] == 2

    def test_limit_extracted(self):
        node = _make_node(params={"LIMIT": '"500"'})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["limit"] == "500"

    def test_affect_each_sheet_extracted(self):
        """AFFECT_EACH_SHEET extracted as str (TEXT type)."""
        node = _make_node(params={"AFFECT_EACH_SHEET": '"true"'})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["affect_each_sheet"] == "true"

    def test_first_column_extracted(self):
        node = _make_node(params={"FIRST_COLUMN": "3"})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["first_column"] == 3

    def test_last_column_extracted(self):
        node = _make_node(params={"LAST_COLUMN": '"10"'})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["last_column"] == "10"

    def test_die_on_error_true(self):
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_generation_mode_event(self):
        node = _make_node(params={"GENERATION_MODE": '"EVENT_MODE"'})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["generation_mode"] == "EVENT_MODE"

    def test_generation_mode_stream(self):
        node = _make_node(params={"GENERATION_MODE": '"STREAM_MODE"'})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["generation_mode"] == "STREAM_MODE"

    def test_encoding_extracted(self):
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_int_params_from_quoted_strings(self):
        """Integer params handle quoted string values."""
        node = _make_node(params={"HEADER": '"5"', "FOOTER": '"2"', "FIRST_COLUMN": '"3"'})
        result = FileInputExcelConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["header"] == 5
        assert cfg["footer"] == 2
        assert cfg["first_column"] == 3

    def test_include_phoneticruns_false(self):
        node = _make_node(params={"INCLUDE_PHONETICRUNS": "false"})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["include_phoneticruns"] is False

    def test_configure_inflation_ratio_true(self):
        node = _make_node(params={"CONFIGURE_INFLATION_RATIO": "true"})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["configure_inflation_ratio"] is True

    def test_inflation_ratio_extracted(self):
        node = _make_node(params={"INFLATION_RATIO": '"0.01"'})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["inflation_ratio"] == "0.01"


class TestSheetlistTable:
    """Verify SHEETLIST TABLE parameter parsing."""

    def test_empty(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["sheetlist"] == []

    def test_parsed_flat(self):
        """SHEETLIST from flat elementRef/value pairs."""
        data = _make_sheetlist_data([
            ('"Sheet1"', "false"),
            ('"Data.*"', "true"),
        ])
        node = _make_node(params={"SHEETLIST": data})
        result = FileInputExcelConverter().convert(node, [], {})
        sheets = result.component["config"]["sheetlist"]
        assert len(sheets) == 2
        assert sheets[0] == {"sheetname": "Sheet1", "use_regex": False}
        assert sheets[1] == {"sheetname": "Data.*", "use_regex": True}

    def test_empty_list(self):
        node = _make_node(params={"SHEETLIST": []})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["sheetlist"] == []

    def test_incomplete_stride_skipped(self):
        """Incomplete trailing group should be ignored."""
        data = [{"elementRef": "SHEETNAME", "value": '"Sheet1"'}]
        assert len(_parse_sheetlist(data)) == 1


class TestTrimSelectTable:
    """Verify TRIMSELECT TABLE parameter parsing."""

    def test_empty(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["trim_select"] == []

    def test_parsed_flat(self):
        """TRIMSELECT from flat elementRef/value pairs."""
        data = _make_trim_select_data([
            ("col_a", "true"),
            ("col_b", "false"),
        ])
        node = _make_node(params={"TRIMSELECT": data})
        result = FileInputExcelConverter().convert(node, [], {})
        trims = result.component["config"]["trim_select"]
        assert len(trims) == 2
        assert trims[0] == {"column": "col_a", "trim": True}
        assert trims[1] == {"column": "col_b", "trim": False}

    def test_empty_list(self):
        node = _make_node(params={"TRIMSELECT": []})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["trim_select"] == []


class TestDateSelectTable:
    """Verify DATESELECT TABLE parameter parsing."""

    def test_empty(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["date_select"] == []

    def test_parsed_flat(self):
        """DATESELECT from flat elementRef/value pairs."""
        data = _make_date_select_data([
            ("created_at", "true", '"yyyy-MM-dd"'),
            ("updated_at", "false", '"MM/dd/yyyy"'),
        ])
        node = _make_node(params={"DATESELECT": data})
        result = FileInputExcelConverter().convert(node, [], {})
        dates = result.component["config"]["date_select"]
        assert len(dates) == 2
        assert dates[0] == {"column": "created_at", "convert_date": True, "pattern": "yyyy-MM-dd"}
        assert dates[1] == {"column": "updated_at", "convert_date": False, "pattern": "MM/dd/yyyy"}

    def test_empty_list(self):
        node = _make_node(params={"DATESELECT": []})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["date_select"] == []


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction (source component)."""

    def test_schema_extracted(self):
        node = _make_node(schema=_make_schema_columns())
        result = FileInputExcelConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]
        assert len(output_schema) == 3
        assert output_schema[0]["name"] == "id"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[1]["name"] == "name"
        assert output_schema[1]["length"] == 50
        assert output_schema[2]["name"] == "sale_date"
        assert output_schema[2]["date_pattern"] == "%Y-%m-%d"

    def test_input_schema_always_empty(self):
        """FileInputExcel is a source -- input schema must be empty."""
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """9 engine-gap params that engine does not read."""
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert len(result.needs_review) == 9

    def test_needs_review_severity(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FileInputExcelConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()

    def test_version_2007_needs_review(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("version_2007" in i for i in issues)

    def test_affect_each_sheet_needs_review(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("affect_each_sheet" in i for i in issues)

    def test_novalidate_on_cell_needs_review(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("novalidate_on_cell" in i for i in issues)

    def test_generation_mode_needs_review(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("generation_mode" in i for i in issues)

    def test_encoding_needs_review(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("encoding" in i for i in issues)

    def test_read_real_value_needs_review(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("read_real_value" in i for i in issues)

    def test_include_phoneticruns_needs_review(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("include_phoneticruns" in i for i in issues)

    def test_configure_inflation_ratio_needs_review(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("configure_inflation_ratio" in i for i in issues)

    def test_inflation_ratio_needs_review(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("inflation_ratio" in i for i in issues)


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = FileInputExcelConverter().convert(node, [], {})
        expected_keys = {
            # Core parameters
            "version_2007", "filepath", "password", "all_sheets",
            "sheetlist", "header", "footer", "limit",
            "affect_each_sheet", "first_column", "last_column",
            "die_on_error", "advanced_separator", "thousands_separator",
            "decimal_separator", "trimall", "trim_select",
            "convertdatetostring", "date_select", "encoding",
            "read_real_value", "stopread_on_emptyrow",
            "novalidate_on_cell", "suppress_warn",
            "generation_mode", "include_phoneticruns",
            "configure_inflation_ratio", "inflation_ratio",
            # Framework
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify component dict structure."""

    def test_top_level_keys(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys

    def test_type_is_FileInputExcel(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["type"] == "FileInputExcel"

    def test_original_type(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileInputExcel"

    def test_inputs_outputs_empty(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_result_type(self):
        node = _make_node()
        result = FileInputExcelConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_empty_filename_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={})
        result = FileInputExcelConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)


# ------------------------------------------------------------------
# Plan 14-11: TABLE-parser branch coverage (lines 83, 99, 123, 136, 164, 177, 182)
# ------------------------------------------------------------------


class TestSheetlistParserBranches:
    """Cover lines 83 (entry not dict) and 99 (USE_REGEX non-string fallback)."""

    def test_non_dict_entry_skipped(self):
        """A non-dict entry inside SHEETLIST raw is silently skipped (line 83)."""
        from src.converters.talend_to_v1.components.file.file_input_excel import (
            _parse_sheetlist,
        )
        raw = [
            {"elementRef": "SHEETNAME", "value": '"Sheet1"'},
            "not_a_dict",  # skipped
            {"elementRef": "USE_REGEX", "value": "true"},
        ]
        result = _parse_sheetlist(raw)
        assert len(result) == 1
        assert result[0]["sheetname"] == "Sheet1"
        assert result[0]["use_regex"] is True

    def test_use_regex_non_string_falls_back_to_bool(self):
        """USE_REGEX with non-string value uses bool() conversion (line 99)."""
        from src.converters.talend_to_v1.components.file.file_input_excel import (
            _parse_sheetlist,
        )
        raw = [
            {"elementRef": "SHEETNAME", "value": '"Sheet1"'},
            {"elementRef": "USE_REGEX", "value": 1},  # int, not str
        ]
        result = _parse_sheetlist(raw)
        assert len(result) == 1
        assert result[0]["use_regex"] is True

    def test_use_regex_non_string_zero_is_false(self):
        """USE_REGEX = 0 (int) -> bool(0) = False (line 99)."""
        from src.converters.talend_to_v1.components.file.file_input_excel import (
            _parse_sheetlist,
        )
        raw = [
            {"elementRef": "SHEETNAME", "value": '"Sheet1"'},
            {"elementRef": "USE_REGEX", "value": 0},
        ]
        result = _parse_sheetlist(raw)
        assert len(result) == 1
        assert result[0]["use_regex"] is False


class TestTrimSelectParserBranches:
    """Cover lines 123 (entry not dict) and 136 (TRIM non-string fallback)."""

    def test_non_dict_entry_skipped(self):
        """A non-dict entry in TRIMSELECT raw is silently skipped (line 123)."""
        from src.converters.talend_to_v1.components.file.file_input_excel import (
            _parse_trim_select,
        )
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": "col_a"},
            42,  # skipped
            {"elementRef": "TRIM", "value": "true"},
        ]
        result = _parse_trim_select(raw)
        assert len(result) == 1
        assert result[0]["column"] == "col_a"
        assert result[0]["trim"] is True

    def test_trim_non_string_falls_back_to_bool(self):
        """TRIM with non-string value uses bool() conversion (line 136)."""
        from src.converters.talend_to_v1.components.file.file_input_excel import (
            _parse_trim_select,
        )
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": "col_a"},
            {"elementRef": "TRIM", "value": True},  # bool, not str
        ]
        result = _parse_trim_select(raw)
        assert len(result) == 1
        assert result[0]["trim"] is True


class TestDateSelectParserBranches:
    """Cover lines 164 (entry not dict), 177 (CONVERTDATE non-string fallback),
    182 (PATTERN non-string fallback)."""

    def test_non_dict_entry_skipped(self):
        """A non-dict entry inside DATESELECT raw is silently skipped (line 164)."""
        from src.converters.talend_to_v1.components.file.file_input_excel import (
            _parse_date_select,
        )
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": "dt_col"},
            "not_a_dict",  # skipped
            {"elementRef": "CONVERTDATE", "value": "true"},
            {"elementRef": "PATTERN", "value": '"yyyy-MM-dd"'},
        ]
        result = _parse_date_select(raw)
        assert len(result) == 1
        assert result[0]["column"] == "dt_col"
        assert result[0]["convert_date"] is True
        assert result[0]["pattern"] == "yyyy-MM-dd"

    def test_convertdate_non_string_falls_back_to_bool(self):
        """CONVERTDATE with non-string value uses bool() conversion (line 177)."""
        from src.converters.talend_to_v1.components.file.file_input_excel import (
            _parse_date_select,
        )
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": "dt_col"},
            {"elementRef": "CONVERTDATE", "value": 1},  # int, not str
        ]
        result = _parse_date_select(raw)
        assert len(result) == 1
        assert result[0]["convert_date"] is True

    def test_pattern_non_string_falls_back_to_default(self):
        """PATTERN with non-string value falls back to default 'MM-dd-yyyy' (line 182)."""
        from src.converters.talend_to_v1.components.file.file_input_excel import (
            _parse_date_select,
        )
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": "dt_col"},
            {"elementRef": "PATTERN", "value": 42},  # int, not str
        ]
        result = _parse_date_select(raw)
        assert len(result) == 1
        assert result[0]["pattern"] == "MM-dd-yyyy"
