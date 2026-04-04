"""Tests for FileListConverter (tFileList -> tFileList, no engine)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import SchemaColumn, TalendNode
from src.converters.talend_to_v1.components.file.file_list import FileListConverter
from src.converters.talend_to_v1.components.registry import REGISTRY

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="tFileList_1",
               component_type="tFileList"):
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


def _make_files_data(rows):
    """Generate FILES TABLE data with stride-1: FILEMASK per row.

    rows: list of filemask strings
    """
    result = []
    for mask in rows:
        result.append({"elementRef": "FILEMASK", "value": mask})
    return result


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        """tFileList is registered in the converter registry."""
        assert REGISTRY.get("tFileList") is FileListConverter


class TestDefaults:
    """Verify all 15 unique parameters have correct defaults when no params provided."""

    def test_directory_default(self):
        """DIRECTORY defaults to empty string when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["directory"] == ""

    def test_list_mode_default(self):
        """LIST_MODE defaults to 'FILES' when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["list_mode"] == "FILES"

    def test_include_subdirs_default(self):
        """INCLUDSUBDIR (no E) defaults to False when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["include_subdirs"] is False

    def test_case_sensitive_default(self):
        """CASE_SENSITIVE defaults to 'YES' when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["case_sensitive"] == "YES"

    def test_error_default(self):
        """ERROR defaults to False (not True) per _java.xml."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["error"] is False

    def test_glob_expressions_default(self):
        """GLOBEXPRESSIONS defaults to True when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["glob_expressions"] is True

    def test_order_by_nothing_default(self):
        """ORDER_BY_NOTHING defaults to True (RADIO selected) when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["order_by_nothing"] is True

    def test_order_by_filename_default(self):
        """ORDER_BY_FILENAME defaults to False when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["order_by_filename"] is False

    def test_order_by_filesize_default(self):
        """ORDER_BY_FILESIZE defaults to False when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["order_by_filesize"] is False

    def test_order_by_modifieddate_default(self):
        """ORDER_BY_MODIFIEDDATE defaults to False when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["order_by_modifieddate"] is False

    def test_order_action_asc_default(self):
        """ORDER_ACTION_ASC defaults to True (RADIO selected) when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["order_action_asc"] is True

    def test_order_action_desc_default(self):
        """ORDER_ACTION_DESC defaults to False when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["order_action_desc"] is False

    def test_exclude_file_default(self):
        """IFEXCLUDE defaults to False when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["exclude_file"] is False

    def test_exclude_filemask_default(self):
        """EXCLUDEFILEMASK defaults to '*.txt' per _java.xml."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["exclude_filemask"] == "*.txt"

    def test_format_filepath_to_slash_default(self):
        """FORMAT_FILEPATH_TO_SLASH defaults to False when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["format_filepath_to_slash"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_directory_extracted(self):
        """DIRECTORY is extracted and unquoted."""
        node = _make_node(params={"DIRECTORY": '"/data/input"'})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["directory"] == "/data/input"

    def test_list_mode_directories(self):
        """LIST_MODE=DIRECTORIES is correctly extracted."""
        node = _make_node(params={"LIST_MODE": "DIRECTORIES"})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["list_mode"] == "DIRECTORIES"

    def test_include_subdirs_true(self):
        """INCLUDSUBDIR=true is correctly extracted via correct param name."""
        node = _make_node(params={"INCLUDSUBDIR": "true"})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["include_subdirs"] is True

    def test_case_sensitive_no(self):
        """CASE_SENSITIVE=NO is correctly extracted."""
        node = _make_node(params={"CASE_SENSITIVE": "NO"})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["case_sensitive"] == "NO"

    def test_error_true(self):
        """ERROR=true is correctly extracted."""
        node = _make_node(params={"ERROR": "true"})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["error"] is True

    def test_glob_expressions_false(self):
        """GLOBEXPRESSIONS=false is correctly extracted."""
        node = _make_node(params={"GLOBEXPRESSIONS": "false"})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["glob_expressions"] is False

    def test_order_by_filename_true(self):
        """ORDER_BY_FILENAME=true is correctly extracted."""
        node = _make_node(params={"ORDER_BY_FILENAME": "true"})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["order_by_filename"] is True

    def test_exclude_file_true(self):
        """IFEXCLUDE=true is correctly extracted."""
        node = _make_node(params={"IFEXCLUDE": "true"})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["exclude_file"] is True

    def test_exclude_filemask_extracted(self):
        """EXCLUDEFILEMASK is extracted and unquoted."""
        node = _make_node(params={"EXCLUDEFILEMASK": '"*.tmp"'})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["exclude_filemask"] == "*.tmp"

    def test_format_filepath_to_slash_true(self):
        """FORMAT_FILEPATH_TO_SLASH=true is correctly extracted."""
        node = _make_node(params={"FORMAT_FILEPATH_TO_SLASH": "true"})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["format_filepath_to_slash"] is True


class TestFilesTable:
    """Verify FILES TABLE parameter parsing with elementRef pattern."""

    def test_files_empty_when_missing(self):
        """No FILES param produces empty list."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["files"] == []

    def test_files_empty_list(self):
        """Empty FILES list produces empty list."""
        node = _make_node(params={"FILES": []})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["files"] == []

    def test_files_parsed_with_elementref(self):
        """FILES table entries with elementRef=FILEMASK are parsed correctly."""
        files_data = _make_files_data(['"*.csv"', '"*.txt"'])
        node = _make_node(params={"FILES": files_data})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["files"] == [
            {"filemask": "*.csv"},
            {"filemask": "*.txt"},
        ]

    def test_files_values_strip_quotes(self):
        """TABLE values like '"*.json"' are stripped to '*.json'."""
        files_data = _make_files_data(['"report_*.xlsx"'])
        node = _make_node(params={"FILES": files_data})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["files"] == [{"filemask": "report_*.xlsx"}]

    def test_files_non_dict_entries_skipped(self):
        """Non-dict entries in FILES list are skipped."""
        node = _make_node(params={"FILES": ["not_a_dict", 42]})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["files"] == []


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """TSTATCATCHER_STATS defaults to False when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS=true is correctly extracted."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """LABEL defaults to empty string when absent."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """LABEL with quotes is correctly extracted and unquoted."""
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestComponentStructure:
    """Verify standard component dict structure from _build_component_dict."""

    def test_has_id_at_top_level(self):
        """Component dict has 'id' at top level for orchestrator compatibility."""
        node = _make_node(component_id="tFileList_1")
        result = FileListConverter().convert(node, [], {})
        assert result.component["id"] == "tFileList_1"

    def test_type_is_tfilelist(self):
        """type_name is 'tFileList' per D-43 (no-engine uses Talend name)."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["type"] == "tFileList"

    def test_has_original_type(self):
        """Component dict has 'original_type' at top level."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileList"

    def test_has_position(self):
        """Component dict has 'position' at top level."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_has_config_dict(self):
        """Component dict has 'config' as a nested dict."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert isinstance(result.component["config"], dict)

    def test_has_inputs_outputs_lists(self):
        """Component dict has 'inputs' and 'outputs' as empty lists."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_schema_is_empty_dict(self):
        """Schema is {input: [], output: []} for iterate-style component."""
        node = _make_node(schema=_make_schema_columns())
        result = FileListConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review entry per D-37 (no-engine component)."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_severity(self):
        """All needs_review entries have severity 'engine_gap'."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries have the correct component id."""
        node = _make_node(component_id="test_comp")
        result = FileListConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileListConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """All 15 unique + 2 framework config keys exist in result.component['config']."""
        node = _make_node(schema=_make_schema_columns())
        result = FileListConverter().convert(node, [], {})
        expected_keys = {
            "directory", "list_mode", "include_subdirs", "case_sensitive",
            "error", "glob_expressions", "files",
            "order_by_nothing", "order_by_filename", "order_by_filesize",
            "order_by_modifieddate", "order_action_asc", "order_action_desc",
            "exclude_file", "exclude_filemask", "format_filepath_to_slash",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestPhantomParams:
    """Verify correct param name spelling from _java.xml."""

    def test_param_name_is_includsubdir_no_e(self):
        """Converter reads INCLUDSUBDIR (no E) not INCLUDESUBDIR per _java.xml spelling."""
        # Provide INCLUDSUBDIR (correct) -- should be extracted as True
        node = _make_node(params={"INCLUDSUBDIR": "true"})
        result = FileListConverter().convert(node, [], {})
        assert result.component["config"]["include_subdirs"] is True

    def test_wrong_param_name_not_extracted(self):
        """INCLUDESUBDIR (with E) should NOT affect include_subdirs -- wrong param name."""
        node = _make_node(params={"INCLUDESUBDIR": "true"})
        result = FileListConverter().convert(node, [], {})
        # Should be False (default) because INCLUDESUBDIR is wrong spelling
        assert result.component["config"]["include_subdirs"] is False


class TestWarnings:
    """Verify warning generation."""

    def test_empty_directory_produces_warning(self):
        """An empty DIRECTORY triggers a warning."""
        node = _make_node(params={})
        result = FileListConverter().convert(node, [], {})
        assert len(result.warnings) == 1
        assert "DIRECTORY" in result.warnings[0]

    def test_no_warning_when_directory_set(self):
        """A non-empty DIRECTORY produces no warning."""
        node = _make_node(params={"DIRECTORY": '"/tmp/files"'})
        result = FileListConverter().convert(node, [], {})
        assert result.warnings == []
