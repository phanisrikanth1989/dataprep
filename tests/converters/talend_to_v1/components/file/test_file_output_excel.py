"""Tests for FileOutputExcelConverter (tFileOutputExcel -> v1 FileOutputExcel config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_output_excel import (
    FileOutputExcelConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="foe_1",
               component_type="tFileOutputExcel"):
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
    """Return a sample FLOW schema for testing sink component."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
            SchemaColumn(name="amount", type="id_Double", precision=2),
        ]
    }


def _make_auto_szie_data(rows):
    """Generate AUTO_SZIE_SETTING TABLE data with stride-1 per row.

    rows: list of str column names
    """
    result = []
    for col_name in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": f'"{col_name}"'})
    return result


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tFileOutputExcel") is FileOutputExcelConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_version_2007_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["version_2007"] is False

    def test_usestream_default(self):
        """CRITICAL: was MISSING from old converter."""
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["usestream"] is False

    def test_streamname_default(self):
        """CRITICAL: was MISSING from old converter."""
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["streamname"] == "outputStream"

    def test_filename_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_sheetname_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["sheetname"] == "Sheet1"

    def test_includeheader_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["includeheader"] is False

    def test_append_file_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["append_file"] is False

    def test_append_sheet_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["append_sheet"] is False

    def test_first_cell_y_absolute_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["first_cell_y_absolute"] is False

    def test_first_cell_x_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["first_cell_x"] == "0"

    def test_first_cell_y_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["first_cell_y"] == "0"

    def test_keep_cell_formating_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["keep_cell_formating"] is False

    def test_font_default(self):
        """CRITICAL: was 'Arial' in old converter, _java.xml says 'NONE'."""
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["font"] == "NONE"

    def test_is_all_auto_szie_default(self):
        """Talend typo: IS_ALL_AUTO_SZIE (not SIZE). Was phantom AUTO_SIZE_SETTING."""
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["is_all_auto_szie"] is False

    def test_auto_szie_setting_default(self):
        """TABLE param, Talend typo: AUTO_SZIE_SETTING."""
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["auto_szie_setting"] == []

    def test_protect_file_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["protect_file"] is False

    def test_password_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["password"] == ""

    def test_create_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["create"] is True

    def test_flushonrow_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["flushonrow"] is False

    def test_flushonrow_num_default(self):
        """CRITICAL: was 1000 in old converter, _java.xml says 100."""
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["flushonrow_num"] == "100"

    def test_advanced_separator_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."

    def test_truncate_exceeding_characters_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["truncate_exceeding_characters"] is False

    def test_encoding_default(self):
        """CRITICAL: was 'UTF-8' in old converter, _java.xml says 'ISO-8859-15'."""
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_delete_empty_file_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["delete_empty_file"] is False

    def test_recalculate_formula_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["recalculate_formula"] is False

    def test_streaming_append_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["streaming_append"] is False

    def test_use_shared_strings_table_default(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["use_shared_strings_table"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_font_custom(self):
        node = _make_node(params={"FONT": '"Arial"'})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["font"] == "Arial"

    def test_encoding_custom(self):
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_flushonrow_num_custom(self):
        node = _make_node(params={"FLUSHONROW_NUM": '"500"'})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["flushonrow_num"] == "500"

    def test_is_all_auto_szie_true(self):
        node = _make_node(params={"IS_ALL_AUTO_SZIE": "true"})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["is_all_auto_szie"] is True

    def test_usestream_true(self):
        node = _make_node(params={"USESTREAM": "true"})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["usestream"] is True

    def test_streamname_custom(self):
        node = _make_node(params={"STREAMNAME": '"myStream"'})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["streamname"] == "myStream"

    def test_filename_custom(self):
        node = _make_node(params={"FILENAME": '"/data/report.xlsx"'})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "/data/report.xlsx"

    def test_sheetname_custom(self):
        node = _make_node(params={"SHEETNAME": '"DataSheet"'})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["sheetname"] == "DataSheet"

    def test_version_2007_true(self):
        node = _make_node(params={"VERSION_2007": "true"})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["version_2007"] is True

    def test_create_false(self):
        node = _make_node(params={"CREATE": "false"})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["create"] is False

    def test_flushonrow_true(self):
        node = _make_node(params={"FLUSHONROW": "true"})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["flushonrow"] is True

    def test_password_custom(self):
        node = _make_node(params={"PASSWORD": '"secret123"'})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["password"] == "secret123"


class TestTableParsing:
    """Verify AUTO_SZIE_SETTING TABLE parameter parsing."""

    def test_auto_szie_setting_parsed(self):
        table_data = _make_auto_szie_data(["col1", "col2"])
        node = _make_node(params={"AUTO_SZIE_SETTING": table_data})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert len(result.component["config"]["auto_szie_setting"]) == 2
        assert result.component["config"]["auto_szie_setting"][0] == "col1"
        assert result.component["config"]["auto_szie_setting"][1] == "col2"

    def test_auto_szie_setting_empty_when_missing(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["auto_szie_setting"] == []


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for sink component (D-55)."""

    def test_schema_input_populated(self):
        """Sink component: schema input has columns from FLOW."""
        node = _make_node(schema=_make_schema_columns())
        result = FileOutputExcelConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][0]["key"] is True
        assert schema["input"][1]["name"] == "name"
        assert schema["input"][1]["length"] == 50
        assert schema["input"][2]["name"] == "amount"
        assert schema["input"][2]["precision"] == 2

    def test_schema_output_empty(self):
        """Sink component: schema output always empty."""
        node = _make_node(schema=_make_schema_columns())
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert len(result.needs_review) > 0

    def test_all_needs_review_are_engine_gap(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FileOutputExcelConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_no_auto_size_setting_key(self):
        """Phantom: old converter used AUTO_SIZE_SETTING, actual _java.xml is IS_ALL_AUTO_SZIE."""
        node = _make_node(params={"AUTO_SIZE_SETTING": "true"})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert "auto_size_setting" not in result.component["config"]
        assert "auto_size_all" not in result.component["config"]

    def test_no_custom_flush_buffer_key(self):
        """Phantom: old converter had CUSTOM_FLUSH_BUFFER, actual _java.xml uses FLUSHONROW."""
        node = _make_node(params={"CUSTOM_FLUSH_BUFFER": "true"})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert "custom_flush_buffer" not in result.component["config"]

    def test_no_die_on_error_key(self):
        """Phantom: DIE_ON_ERROR not in _java.xml for tFileOutputExcel."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]

    def test_no_create_directory_key(self):
        """Phantom: old converter used 'create_directory', actual _java.xml param is CREATE."""
        node = _make_node(params={"CREATE": "true"})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert "create_directory" not in result.component["config"]

    def test_no_keep_cell_formatting_key(self):
        """Phantom: old converter used 'keep_cell_formatting' (with second T), actual is keep_cell_formating (Talend spelling)."""
        node = _make_node(params={"KEEP_CELL_FORMATING": "true"})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert "keep_cell_formatting" not in result.component["config"]
        assert "keep_cell_formating" in result.component["config"]

    def test_no_flush_on_row_key(self):
        """Phantom: old converter used 'flush_on_row', actual _java.xml param is FLUSHONROW_NUM -> flushonrow_num."""
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert "flush_on_row" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = FileOutputExcelConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            # Core params (29 unique)
            "version_2007", "usestream", "streamname",
            "filename", "sheetname", "includeheader",
            "append_file", "append_sheet",
            "first_cell_y_absolute", "first_cell_x", "first_cell_y",
            "keep_cell_formating", "font",
            "is_all_auto_szie", "auto_szie_setting",
            "protect_file", "password",
            "create", "flushonrow", "flushonrow_num",
            "advanced_separator", "thousands_separator", "decimal_separator",
            "truncate_exceeding_characters",
            "encoding", "delete_empty_file", "recalculate_formula",
            "streaming_append", "use_shared_strings_table",
            # Framework (2)
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(cfg.keys())
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys
        assert not missing, f"Missing config keys: {missing}"
        assert not extra, f"Extra config keys: {extra}"


class TestComponentStructure:
    """Verify component wrapper structure from _build_component_dict."""

    def test_has_type(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["type"] == "FileOutputExcel"

    def test_has_id(self):
        node = _make_node(component_id="my_excel_out")
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["id"] == "my_excel_out"

    def test_has_original_type(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileOutputExcel"

    def test_has_position(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_wrapper_keys(self):
        node = _make_node()
        result = FileOutputExcelConverter().convert(node, [], {})
        assert set(result.component.keys()) == {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
