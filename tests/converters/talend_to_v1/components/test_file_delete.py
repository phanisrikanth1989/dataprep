"""Tests for the FileDeleteConverter (tFileDelete -> FileDelete)."""
import pytest
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_delete import FileDeleteConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="delete_1",
               component_type="tFileDelete"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


class TestFileDeleteConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tFileDelete") is FileDeleteConverter


class TestFileDeleteConverterBasic:
    def test_basic_conversion(self):
        node = _make_node(params={
            "FILENAME": '"/tmp/old_data.csv"',
            "FAIL_ON_ERROR": "true",
        })
        result = FileDeleteConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "delete_1"
        assert comp["type"] == "FileDelete"
        assert comp["original_type"] == "tFileDelete"
        assert comp["position"] == {"x": 100, "y": 200}
        assert comp["config"]["filename"] == "/tmp/old_data.csv"
        assert comp["config"]["fail_on_error"] is True
        assert comp["schema"]["input"] == []
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_fail_on_error_false(self):
        node = _make_node(params={
            "FILENAME": '"/data/temp.log"',
            "FAIL_ON_ERROR": "false",
        })
        result = FileDeleteConverter().convert(node, [], {})

        assert result.component["config"]["filename"] == "/data/temp.log"
        assert result.component["config"]["fail_on_error"] is False

    def test_defaults_when_params_missing(self):
        node = _make_node(params={})
        result = FileDeleteConverter().convert(node, [], {})

        assert result.component["config"]["filename"] == ""
        assert result.component["config"]["fail_on_error"] is False

    def test_empty_filename_produces_warning(self):
        node = _make_node(params={})
        result = FileDeleteConverter().convert(node, [], {})

        assert any("FILENAME" in w for w in result.warnings)
        assert "FILENAME" in result.warnings[0]


class TestFileDeleteConverterSchema:
    def test_utility_component_has_empty_schema(self):
        """FileDelete is a utility component — no data flow schema."""
        node = _make_node(params={"FILENAME": '"/tmp/x.txt"'})
        result = FileDeleteConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}


class TestFileDeleteConverterWarnings:
    def test_no_warnings_when_filename_provided(self):
        node = _make_node(params={
            "FILENAME": '"/tmp/test.txt"',
            "FAIL_ON_ERROR": "true",
        })
        result = FileDeleteConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []


# ---------------------------------------------------------------------------
# New parameters
# ---------------------------------------------------------------------------

class TestNewParams:

    def test_folder_default_false(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["folder"] is False

    def test_folder_extracted(self):
        node = _make_node(params={"FOLDER": True})
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["folder"] is True

    def test_folder_file_default_false(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["folder_file"] is False

    def test_folder_file_extracted(self):
        node = _make_node(params={"FOLDER_FILE": True})
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["folder_file"] is True

    def test_directory_default_empty(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["directory"] == ""

    def test_directory_extracted(self):
        node = _make_node(params={"DIRECTORY": '"/data/archive"'})
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["directory"] == "/data/archive"

    def test_folder_file_path_default_empty(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["folder_file_path"] == ""

    def test_folder_file_path_extracted(self):
        node = _make_node(params={"FOLDER_FILE_PATH": '"/data/cleanup"'})
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["folder_file_path"] == "/data/cleanup"

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


# ---------------------------------------------------------------------------
# Engine-gap warnings
# ---------------------------------------------------------------------------

class TestEngineGapWarnings:

    def test_no_engine_warnings_for_defaults(self):
        node = _make_node(params={"FILENAME": '"/tmp/test.txt"'})
        result = FileDeleteConverter().convert(node, [], {})
        engine_warnings = [w for w in result.warnings if "engine" in w.lower()]
        assert engine_warnings == []

    def test_warning_when_folder_enabled(self):
        node = _make_node(params={"FILENAME": '"/tmp/test"', "FOLDER": True})
        result = FileDeleteConverter().convert(node, [], {})
        assert any("FOLDER" in w for w in result.warnings)

    def test_warning_when_folder_file_enabled(self):
        node = _make_node(params={"FILENAME": '"/tmp/test"', "FOLDER_FILE": True})
        result = FileDeleteConverter().convert(node, [], {})
        assert any("FOLDER_FILE" in w for w in result.warnings)

    def test_no_warning_when_folder_disabled(self):
        node = _make_node(params={"FILENAME": '"/tmp/test.txt"', "FOLDER": False})
        result = FileDeleteConverter().convert(node, [], {})
        engine_warnings = [w for w in result.warnings if "engine" in w.lower()]
        assert engine_warnings == []


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------

class TestCompleteness:

    def test_all_8_config_keys_present(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "filename", "fail_on_error",
            "folder", "folder_file", "directory", "folder_file_path",
            "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected_keys
