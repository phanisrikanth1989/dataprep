"""Tests for tFileCopy -> FileCopy converter."""
import xml.etree.ElementTree as ET

import pytest

from src.converters.talend_to_v1.components.base import (
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_copy import FileCopyConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tFileCopy_1"):
    """Create a TalendNode for tFileCopy with given params."""
    return TalendNode(
        component_id=component_id,
        component_type="tFileCopy",
        params=params or {},
        schema={},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _convert(node, connections=None, context=None):
    """Helper to run the converter."""
    converter = FileCopyConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


class TestFileCopyRegistration:
    """Verify the converter is registered in the global registry."""

    def test_registered_for_tfilecopy(self):
        cls = REGISTRY.get("tFileCopy")
        assert cls is FileCopyConverter


class TestFileCopyBasicConversion:
    """Test basic parameter extraction and component structure."""

    def test_full_params(self):
        node = _make_node(params={
            "FILENAME": '"/data/input/report.csv"',
            "DESTINATION": '"/data/output/"',
            "RENAME": "true",
            "DESTINATION_RENAME": '"report_backup.csv"',
            "REPLACE_FILE": "true",
            "CREATE_DIRECTORY": "true",
            "PRESERVE_LAST_MODIFIED_TIME": "true",
            "REMOVE_SOURCE_FILE": "true",
            "COPY_DIRECTORY": "false",
        })
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tFileCopy_1"
        assert comp["type"] == "FileCopy"
        assert comp["original_type"] == "tFileCopy"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["source"] == "/data/input/report.csv"
        assert cfg["destination"] == "/data/output/"
        assert cfg["rename"] is True
        assert cfg["new_name"] == "report_backup.csv"
        assert cfg["replace_file"] is True
        assert cfg["create_directory"] is True
        assert cfg["preserve_last_modified"] is True
        assert cfg["remove_source_file"] is True
        assert cfg["copy_directory"] is False
        assert result.warnings == []

    def test_component_structure_has_required_keys(self):
        node = _make_node(params={
            "FILENAME": '"/src/file.txt"',
            "DESTINATION": '"/dst/"',
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


class TestFileCopyDefaults:
    """Verify default values when parameters are missing."""

    def test_defaults_when_empty_params(self):
        node = _make_node(params={})
        result = _convert(node)
        cfg = result.component["config"]

        assert cfg["source"] == ""
        assert cfg["destination"] == ""
        assert cfg["rename"] is False
        assert cfg["new_name"] == ""
        assert cfg["replace_file"] is True
        assert cfg["create_directory"] is True
        assert cfg["preserve_last_modified"] is False
        assert cfg["remove_source_file"] is False
        assert cfg["copy_directory"] is False

    def test_replace_file_default_true(self):
        """REPLACE_FILE defaults to True when not specified."""
        node = _make_node(params={"FILENAME": '"a.txt"', "DESTINATION": '"/tmp/"'})
        result = _convert(node)
        assert result.component["config"]["replace_file"] is True

    def test_create_directory_default_true(self):
        """CREATE_DIRECTORY defaults to True when not specified."""
        node = _make_node(params={"FILENAME": '"a.txt"', "DESTINATION": '"/tmp/"'})
        result = _convert(node)
        assert result.component["config"]["create_directory"] is True

    def test_remove_source_file_default_false(self):
        """REMOVE_SOURCE_FILE defaults to False (was missing in old code per audit)."""
        node = _make_node(params={"FILENAME": '"a.txt"', "DESTINATION": '"/tmp/"'})
        result = _convert(node)
        assert result.component["config"]["remove_source_file"] is False

    def test_copy_directory_default_false(self):
        """COPY_DIRECTORY defaults to False (was missing in old code per audit)."""
        node = _make_node(params={"FILENAME": '"a.txt"', "DESTINATION": '"/tmp/"'})
        result = _convert(node)
        assert result.component["config"]["copy_directory"] is False


class TestFileCopyWarnings:
    """Test that appropriate warnings are generated."""

    def test_warning_when_source_empty(self):
        node = _make_node(params={"DESTINATION": '"/out/"'})
        result = _convert(node)
        assert any("FILENAME" in w and "empty" in w for w in result.warnings)

    def test_warning_when_destination_empty(self):
        node = _make_node(params={"FILENAME": '"/in/file.txt"'})
        result = _convert(node)
        assert any("DESTINATION" in w and "empty" in w for w in result.warnings)

    def test_warning_when_rename_true_but_no_new_name(self):
        node = _make_node(params={
            "FILENAME": '"/in/file.txt"',
            "DESTINATION": '"/out/"',
            "RENAME": "true",
        })
        result = _convert(node)
        assert any("RENAME" in w and "DESTINATION_RENAME" in w for w in result.warnings)

    def test_no_warning_when_rename_true_with_new_name(self):
        node = _make_node(params={
            "FILENAME": '"/in/file.txt"',
            "DESTINATION": '"/out/"',
            "RENAME": "true",
            "DESTINATION_RENAME": '"new_file.txt"',
        })
        result = _convert(node)
        assert result.warnings == []

    def test_no_warnings_when_all_valid(self):
        node = _make_node(params={
            "FILENAME": '"/in/file.txt"',
            "DESTINATION": '"/out/"',
        })
        result = _convert(node)
        assert result.warnings == []

    def test_multiple_warnings(self):
        """When both source and destination are empty, both warnings appear."""
        node = _make_node(params={})
        result = _convert(node)
        assert len(result.warnings) >= 2


class TestFileCopyBooleanParsing:
    """Test that boolean params handle various input formats."""

    def test_bool_true_string(self):
        node = _make_node(params={
            "FILENAME": '"f"',
            "DESTINATION": '"d"',
            "RENAME": "true",
        })
        result = _convert(node)
        assert result.component["config"]["rename"] is True

    def test_bool_false_string(self):
        node = _make_node(params={
            "FILENAME": '"f"',
            "DESTINATION": '"d"',
            "RENAME": "false",
        })
        result = _convert(node)
        assert result.component["config"]["rename"] is False

    def test_bool_native_true(self):
        node = _make_node(params={
            "FILENAME": '"f"',
            "DESTINATION": '"d"',
            "COPY_DIRECTORY": True,
        })
        result = _convert(node)
        assert result.component["config"]["copy_directory"] is True

    def test_bool_string_one(self):
        node = _make_node(params={
            "FILENAME": '"f"',
            "DESTINATION": '"d"',
            "REMOVE_SOURCE_FILE": "1",
        })
        result = _convert(node)
        assert result.component["config"]["remove_source_file"] is True

    def test_bool_string_zero(self):
        node = _make_node(params={
            "FILENAME": '"f"',
            "DESTINATION": '"d"',
            "PRESERVE_LAST_MODIFIED_TIME": "0",
        })
        result = _convert(node)
        assert result.component["config"]["preserve_last_modified"] is False


class TestFileCopyEdgeCases:
    """Edge case and audit-specific tests."""

    def test_custom_component_id(self):
        node = _make_node(
            params={"FILENAME": '"a"', "DESTINATION": '"b"'},
            component_id="tFileCopy_42",
        )
        result = _convert(node)
        assert result.component["id"] == "tFileCopy_42"

    def test_unquoted_paths(self):
        """Params without surrounding quotes should still work."""
        node = _make_node(params={
            "FILENAME": "/data/file.txt",
            "DESTINATION": "/data/out/",
        })
        result = _convert(node)
        cfg = result.component["config"]
        assert cfg["source"] == "/data/file.txt"
        assert cfg["destination"] == "/data/out/"

    def test_connections_do_not_affect_config(self):
        node = _make_node(params={
            "FILENAME": '"f.txt"',
            "DESTINATION": '"d/"',
        })
        conns = [
            TalendConnection(
                name="row1", source="tFileCopy_1", target="tLogRow_1",
                connector_type="FLOW",
            ),
        ]
        result = _convert(node, connections=conns)
        assert result.component["config"]["source"] == "f.txt"

    def test_result_type_is_component_result(self):
        node = _make_node(params={
            "FILENAME": '"f"',
            "DESTINATION": '"d"',
        })
        result = _convert(node)
        from src.converters.talend_to_v1.components.base import ComponentResult
        assert isinstance(result, ComponentResult)
