"""Tests for tFileExist → FileExistComponent converter."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_exist import FileExistConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tFileExist_1",
               component_type="tFileExist"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema={},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


class TestFileExistConverter:
    """Core conversion logic."""

    def test_basic_conversion(self):
        node = _make_node(params={"FILE_NAME": '"/tmp/data.csv"'})
        result = FileExistConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "tFileExist_1"
        assert comp["type"] == "FileExistComponent"
        assert comp["original_type"] == "tFileExist"
        assert comp["config"]["filename"] == "/tmp/data.csv"
        assert comp["position"] == {"x": 100, "y": 200}
        assert result.warnings == []

    def test_filename_without_quotes(self):
        node = _make_node(params={"FILE_NAME": "/opt/files/output.txt"})
        result = FileExistConverter().convert(node, [], {})

        assert result.component["config"]["filename"] == "/opt/files/output.txt"
        assert result.warnings == []

    def test_empty_filename_generates_warning(self):
        node = _make_node(params={"FILE_NAME": ""})
        result = FileExistConverter().convert(node, [], {})

        assert result.component["config"]["filename"] == ""
        assert len(result.warnings) == 1
        assert "FILE_NAME is empty" in result.warnings[0]

    def test_missing_filename_generates_warning(self):
        node = _make_node(params={})
        result = FileExistConverter().convert(node, [], {})

        assert result.component["config"]["filename"] == ""
        assert len(result.warnings) == 1
        assert "FILE_NAME is empty" in result.warnings[0]

    def test_schema_is_empty(self):
        """tFileExist has no schema — verify the output schema dict is empty."""
        node = _make_node(params={"FILE_NAME": '"/tmp/test"'})
        result = FileExistConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}

    def test_component_structure_has_io_lists(self):
        node = _make_node(params={"FILE_NAME": '"/tmp/test"'})
        result = FileExistConverter().convert(node, [], {})

        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


class TestFileExistRegistry:
    """Verify the converter is properly registered."""

    def test_registered_under_tfileexist(self):
        cls = REGISTRY.get("tFileExist")
        assert cls is FileExistConverter

    def test_tfileexist_in_type_list(self):
        assert "tFileExist" in REGISTRY.list_types()
