"""Tests for the FileTouchConverter (tFileTouch -> FileTouch)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_touch import FileTouchConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="touch_1",
               component_type="tFileTouch"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


class TestFileTouchConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tFileTouch") is FileTouchConverter


class TestFileTouchConverterBasic:
    def test_basic_conversion(self):
        node = _make_node(params={
            "FILENAME": '"/tmp/output.txt"',
            "CREATEDIR": "true",
        })
        result = FileTouchConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "touch_1"
        assert comp["type"] == "FileTouch"
        assert comp["original_type"] == "tFileTouch"
        assert comp["position"] == {"x": 100, "y": 200}
        assert comp["config"]["filename"] == "/tmp/output.txt"
        assert comp["config"]["create_directory"] is True
        assert comp["schema"]["input"] == []
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_create_directory_false(self):
        node = _make_node(params={
            "FILENAME": '"/data/file.csv"',
            "CREATEDIR": "false",
        })
        result = FileTouchConverter().convert(node, [], {})

        assert result.component["config"]["filename"] == "/data/file.csv"
        assert result.component["config"]["create_directory"] is False

    def test_defaults_when_params_missing(self):
        node = _make_node(params={})
        result = FileTouchConverter().convert(node, [], {})

        assert result.component["config"]["filename"] == ""
        assert result.component["config"]["create_directory"] is False

    def test_empty_filename_produces_warning(self):
        node = _make_node(params={})
        result = FileTouchConverter().convert(node, [], {})

        assert len(result.warnings) == 1
        assert "FILENAME" in result.warnings[0]


class TestFileTouchConverterSchema:
    def test_utility_component_has_empty_schema(self):
        """FileTouch is a utility component — no data flow schema."""
        node = _make_node(params={"FILENAME": '"x.txt"'})
        result = FileTouchConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}


class TestFileTouchConverterWarnings:
    def test_no_warnings_by_default(self):
        node = _make_node(params={
            "FILENAME": '"/tmp/test.txt"',
            "CREATEDIR": "true",
        })
        result = FileTouchConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []
