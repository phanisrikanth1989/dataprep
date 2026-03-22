"""Tests for the FileListConverter (tFileList -> FileList)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_list import FileListConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tFileList_1",
               component_type="tFileList"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema={},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


class TestFileListConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tFileList") is FileListConverter

    def test_tfilelist_in_type_list(self):
        assert "tFileList" in REGISTRY.list_types()


class TestFileListConverterBasic:
    def test_basic_conversion(self):
        node = _make_node(params={
            "DIRECTORY": '"/data/input"',
            "LIST_MODE": "FILES",
            "INCLUDESUBDIR": "true",
            "CASE_SENSITIVE": "YES",
            "ERROR": "true",
            "GLOBEXPRESSIONS": "true",
            "FILES": [{"FILEMASK": "*.csv"}],
        })
        result = FileListConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "tFileList_1"
        assert comp["type"] == "FileList"
        assert comp["original_type"] == "tFileList"
        assert comp["position"] == {"x": 100, "y": 200}
        assert comp["config"]["directory"] == "/data/input"
        assert comp["config"]["list_mode"] == "FILES"
        assert comp["config"]["include_subdirs"] is True
        assert comp["config"]["case_sensitive"] == "YES"
        assert comp["config"]["error"] is True
        assert comp["config"]["glob_expressions"] is True
        assert comp["config"]["files"] == [{"filemask": "*.csv"}]
        assert comp["schema"] == {"input": [], "output": []}
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_defaults_when_params_missing(self):
        node = _make_node(params={})
        result = FileListConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["directory"] == ""
        assert cfg["list_mode"] == "FILES"
        assert cfg["include_subdirs"] is False
        assert cfg["case_sensitive"] == "YES"
        assert cfg["error"] is True
        assert cfg["glob_expressions"] is True
        assert cfg["files"] == []
        assert cfg["order_by_nothing"] is False
        assert cfg["order_by_filename"] is False
        assert cfg["order_by_filesize"] is False
        assert cfg["order_by_modifieddate"] is False
        assert cfg["order_action_asc"] is True
        assert cfg["order_action_desc"] is False
        assert cfg["exclude_file"] is False
        assert cfg["exclude_filemask"] == ""

    def test_empty_directory_produces_warning(self):
        node = _make_node(params={})
        result = FileListConverter().convert(node, [], {})

        assert len(result.warnings) == 1
        assert "DIRECTORY is empty" in result.warnings[0]

    def test_no_warning_when_directory_set(self):
        node = _make_node(params={"DIRECTORY": '"/tmp/files"'})
        result = FileListConverter().convert(node, [], {})

        assert result.warnings == []


class TestFileListConverterFilesTable:
    def test_multiple_file_masks(self):
        node = _make_node(params={
            "DIRECTORY": '"/data"',
            "FILES": [
                {"FILEMASK": "*.csv"},
                {"FILEMASK": "*.txt"},
                {"FILEMASK": "report_*.xlsx"},
            ],
        })
        result = FileListConverter().convert(node, [], {})

        assert result.component["config"]["files"] == [
            {"filemask": "*.csv"},
            {"filemask": "*.txt"},
            {"filemask": "report_*.xlsx"},
        ]

    def test_file_mask_with_value_key(self):
        """Handle entries using {value: ...} instead of {FILEMASK: ...}."""
        node = _make_node(params={
            "DIRECTORY": '"/data"',
            "FILES": [{"value": "*.parquet"}],
        })
        result = FileListConverter().convert(node, [], {})

        assert result.component["config"]["files"] == [{"filemask": "*.parquet"}]

    def test_file_mask_strips_quotes(self):
        node = _make_node(params={
            "DIRECTORY": '"/data"',
            "FILES": [{"FILEMASK": '"*.json"'}],
        })
        result = FileListConverter().convert(node, [], {})

        assert result.component["config"]["files"] == [{"filemask": "*.json"}]

    def test_file_mask_plain_string_entry(self):
        """Handle raw string entries in FILES list."""
        node = _make_node(params={
            "DIRECTORY": '"/data"',
            "FILES": ["*.log"],
        })
        result = FileListConverter().convert(node, [], {})

        assert result.component["config"]["files"] == [{"filemask": "*.log"}]

    def test_empty_files_list(self):
        node = _make_node(params={
            "DIRECTORY": '"/data"',
            "FILES": [],
        })
        result = FileListConverter().convert(node, [], {})

        assert result.component["config"]["files"] == []


class TestFileListConverterOrdering:
    def test_order_by_filename_asc(self):
        node = _make_node(params={
            "DIRECTORY": '"/data"',
            "ORDER_BY_FILENAME": "true",
            "ORDER_ACTION_ASC": "true",
            "ORDER_ACTION_DESC": "false",
        })
        result = FileListConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["order_by_filename"] is True
        assert cfg["order_action_asc"] is True
        assert cfg["order_action_desc"] is False

    def test_order_by_modifieddate_desc(self):
        node = _make_node(params={
            "DIRECTORY": '"/data"',
            "ORDER_BY_MODIFIEDDATE": "true",
            "ORDER_ACTION_ASC": "false",
            "ORDER_ACTION_DESC": "true",
        })
        result = FileListConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["order_by_modifieddate"] is True
        assert cfg["order_action_asc"] is False
        assert cfg["order_action_desc"] is True


class TestFileListConverterExclusion:
    def test_exclude_file_with_mask(self):
        node = _make_node(params={
            "DIRECTORY": '"/data"',
            "IFEXCLUDE": "true",
            "EXCLUDEFILEMASK": '"*.tmp"',
        })
        result = FileListConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["exclude_file"] is True
        assert cfg["exclude_filemask"] == "*.tmp"

    def test_exclude_disabled_by_default(self):
        node = _make_node(params={"DIRECTORY": '"/data"'})
        result = FileListConverter().convert(node, [], {})

        assert result.component["config"]["exclude_file"] is False
        assert result.component["config"]["exclude_filemask"] == ""


class TestFileListConverterSchema:
    def test_iterate_component_has_empty_schema(self):
        """tFileList is an iterate-style component with no data flow schema."""
        node = _make_node(params={"DIRECTORY": '"/tmp"'})
        result = FileListConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}
