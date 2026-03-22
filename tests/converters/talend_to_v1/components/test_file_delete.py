"""Tests for the FileDeleteConverter (tFileDelete -> FileDelete)."""
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
            "FAILON": "true",
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
            "FAILON": "false",
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

        assert len(result.warnings) == 1
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
            "FAILON": "true",
        })
        result = FileDeleteConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []
