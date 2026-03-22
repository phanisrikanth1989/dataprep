"""Tests for tFileArchive -> FileArchive converter."""
import xml.etree.ElementTree as ET

import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_archive import (
    FileArchiveConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tFileArchive_1"):
    """Create a TalendNode for tFileArchive with given params."""
    return TalendNode(
        component_id=component_id,
        component_type="tFileArchive",
        params=params or {},
        schema={},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _convert(node, connections=None, context=None):
    """Helper to run the converter."""
    converter = FileArchiveConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


class TestFileArchiveRegistration:
    """Verify the converter is registered in the global registry."""

    def test_registered_for_tfilearchive(self):
        cls = REGISTRY.get("tFileArchive")
        assert cls is FileArchiveConverter


class TestFileArchiveBasicConversion:
    """Test basic parameter extraction and component structure."""

    def test_full_params(self):
        node = _make_node(params={
            "SOURCE": '"/data/input/reports"',
            "TARGET": '"/data/output/reports.zip"',
            "ARCHIVE_FORMAT": '"zip"',
            "SUB_DIRECTORY": "true",
            "OVERWRITE": "true",
            "LEVEL": "9",
        })
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tFileArchive_1"
        assert comp["type"] == "FileArchiveComponent"
        assert comp["original_type"] == "tFileArchive"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["source"] == "/data/input/reports"
        assert cfg["target"] == "/data/output/reports.zip"
        assert cfg["archive_format"] == "zip"
        assert cfg["include_subdirectories"] is True
        assert cfg["overwrite"] is True
        assert cfg["compression_level"] == 9
        assert cfg["die_on_error"] is True  # default
        assert result.warnings == []

    def test_component_structure_has_required_keys(self):
        node = _make_node(params={
            "SOURCE": '"/src/dir"',
            "TARGET": '"/dst/archive.tar.gz"',
        })
        result = _convert(node)
        comp = result.component
        assert set(comp.keys()) == {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert comp["schema"] == {"input": [], "output": []}

    def test_result_type_is_component_result(self):
        node = _make_node(params={
            "SOURCE": '"/src"',
            "TARGET": '"/dst.zip"',
        })
        result = _convert(node)
        assert isinstance(result, ComponentResult)


class TestFileArchiveDefaults:
    """Verify default values when parameters are missing."""

    def test_defaults_when_empty_params(self):
        node = _make_node(params={})
        result = _convert(node)
        cfg = result.component["config"]

        assert cfg["source"] == ""
        assert cfg["target"] == ""
        assert cfg["archive_format"] == "zip"
        assert cfg["include_subdirectories"] is False
        assert cfg["overwrite"] is False
        assert cfg["compression_level"] == 4

    def test_archive_format_default_zip(self):
        """ARCHIVE_FORMAT defaults to 'zip' when not specified."""
        node = _make_node(params={
            "SOURCE": '"/data"',
            "TARGET": '"/data.zip"',
        })
        result = _convert(node)
        assert result.component["config"]["archive_format"] == "zip"

    def test_compression_level_default_4(self):
        """LEVEL defaults to 4 when not specified."""
        node = _make_node(params={
            "SOURCE": '"/data"',
            "TARGET": '"/data.zip"',
        })
        result = _convert(node)
        assert result.component["config"]["compression_level"] == 4


class TestFileArchiveWarnings:
    """Test that appropriate warnings are generated."""

    def test_warning_when_source_empty(self):
        node = _make_node(params={"TARGET": '"/out/archive.zip"'})
        result = _convert(node)
        assert any("SOURCE" in w and "empty" in w for w in result.warnings)

    def test_warning_when_target_empty(self):
        node = _make_node(params={"SOURCE": '"/in/folder"'})
        result = _convert(node)
        assert any("TARGET" in w and "empty" in w for w in result.warnings)

    def test_multiple_warnings_when_both_empty(self):
        """When both source and target are empty, both warnings appear."""
        node = _make_node(params={})
        result = _convert(node)
        assert len(result.warnings) >= 2

    def test_no_warnings_when_all_valid(self):
        node = _make_node(params={
            "SOURCE": '"/in/folder"',
            "TARGET": '"/out/archive.zip"',
        })
        result = _convert(node)
        assert result.warnings == []


class TestFileArchiveBooleanParsing:
    """Test that boolean params handle various input formats."""

    def test_bool_true_string(self):
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "SUB_DIRECTORY": "true",
        })
        result = _convert(node)
        assert result.component["config"]["include_subdirectories"] is True

    def test_bool_false_string(self):
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "OVERWRITE": "false",
        })
        result = _convert(node)
        assert result.component["config"]["overwrite"] is False

    def test_bool_native_true(self):
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "SUB_DIRECTORY": True,
        })
        result = _convert(node)
        assert result.component["config"]["include_subdirectories"] is True

    def test_bool_string_one(self):
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "OVERWRITE": "1",
        })
        result = _convert(node)
        assert result.component["config"]["overwrite"] is True

    def test_bool_string_zero(self):
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "SUB_DIRECTORY": "0",
        })
        result = _convert(node)
        assert result.component["config"]["include_subdirectories"] is False


class TestFileArchiveEdgeCases:
    """Edge case tests."""

    def test_custom_component_id(self):
        node = _make_node(
            params={"SOURCE": '"a"', "TARGET": '"b"'},
            component_id="tFileArchive_42",
        )
        result = _convert(node)
        assert result.component["id"] == "tFileArchive_42"

    def test_unquoted_paths(self):
        """Params without surrounding quotes should still work."""
        node = _make_node(params={
            "SOURCE": "/data/input",
            "TARGET": "/data/output.zip",
        })
        result = _convert(node)
        cfg = result.component["config"]
        assert cfg["source"] == "/data/input"
        assert cfg["target"] == "/data/output.zip"

    def test_tar_gz_format(self):
        """Non-default archive format is extracted correctly."""
        node = _make_node(params={
            "SOURCE": '"/data"',
            "TARGET": '"/data.tar.gz"',
            "ARCHIVE_FORMAT": '"tar.gz"',
        })
        result = _convert(node)
        assert result.component["config"]["archive_format"] == "tar.gz"

    def test_connections_do_not_affect_config(self):
        node = _make_node(params={
            "SOURCE": '"/src"',
            "TARGET": '"/dst.zip"',
        })
        conns = [
            TalendConnection(
                name="row1", source="tFileArchive_1", target="tLogRow_1",
                connector_type="FLOW",
            ),
        ]
        result = _convert(node, connections=conns)
        assert result.component["config"]["source"] == "/src"

    def test_compression_level_as_string(self):
        """LEVEL provided as a quoted string should parse to int."""
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "LEVEL": '"6"',
        })
        result = _convert(node)
        assert result.component["config"]["compression_level"] == 6
