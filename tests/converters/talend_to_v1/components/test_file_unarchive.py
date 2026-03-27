"""Tests for tFileUnarchive -> FileUnarchiveComponent converter."""
import xml.etree.ElementTree as ET

import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_unarchive import (
    FileUnarchiveConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tFileUnarchive_1"):
    """Create a TalendNode for tFileUnarchive with given params."""
    return TalendNode(
        component_id=component_id,
        component_type="tFileUnarchive",
        params=params or {},
        schema={},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _convert(node, connections=None, context=None):
    """Helper to run the converter."""
    converter = FileUnarchiveConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


class TestFileUnarchiveRegistration:
    """Verify the converter is registered in the global registry."""

    def test_registered_for_tfileunarchive(self):
        cls = REGISTRY.get("tFileUnarchive")
        assert cls is FileUnarchiveConverter


class TestFileUnarchiveBasicConversion:
    """Test basic parameter extraction and component structure."""

    def test_full_params(self):
        node = _make_node(params={
            "ZIPFILE": '"/data/archive.zip"',
            "DIRECTORY": '"/data/output"',
            "EXTRACTPATH": "true",
            "CHECKPASSWORD": "true",
            "PASSWORD": '"s3cret"',
            "DIE_ON_ERROR": "true",
        })
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tFileUnarchive_1"
        assert comp["type"] == "FileUnarchiveComponent"
        assert comp["original_type"] == "tFileUnarchive"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["zipfile"] == "/data/archive.zip"
        assert cfg["directory"] == "/data/output"
        assert cfg["extract_path"] is True
        assert cfg["need_password"] is True
        assert cfg["password"] == "s3cret"
        assert cfg["die_on_error"] is True
        assert result.warnings == []

    def test_component_structure_has_required_keys(self):
        node = _make_node(params={
            "ZIPFILE": '"/tmp/file.zip"',
            "DIRECTORY": '"/tmp/out"',
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


class TestFileUnarchiveDefaults:
    """Verify default values when parameters are missing."""

    def test_defaults_when_empty_params(self):
        node = _make_node(params={})
        result = _convert(node)
        cfg = result.component["config"]

        assert cfg["zipfile"] == ""
        assert cfg["directory"] == ""
        assert cfg["extract_path"] is False  # default
        assert cfg["need_password"] is False
        assert cfg["password"] == ""
        assert cfg["die_on_error"] is False

    def test_need_password_default_false(self):
        node = _make_node(params={
            "ZIPFILE": '"a.zip"',
            "DIRECTORY": '"/tmp"',
        })
        result = _convert(node)
        assert result.component["config"]["need_password"] is False

    def test_die_on_error_default_false(self):
        node = _make_node(params={
            "ZIPFILE": '"a.zip"',
            "DIRECTORY": '"/tmp"',
        })
        result = _convert(node)
        assert result.component["config"]["die_on_error"] is False


class TestFileUnarchiveWarnings:
    """Test that appropriate warnings are generated."""

    def test_warning_when_zipfile_empty(self):
        node = _make_node(params={"DIRECTORY": '"/out/"'})
        result = _convert(node)
        assert any("ZIPFILE" in w and "empty" in w for w in result.warnings)

    def test_warning_when_directory_empty(self):
        node = _make_node(params={"ZIPFILE": '"/data/archive.zip"'})
        result = _convert(node)
        assert any("DIRECTORY" in w and "empty" in w for w in result.warnings)

    def test_warning_when_need_password_true_but_password_empty(self):
        node = _make_node(params={
            "ZIPFILE": '"/data/archive.zip"',
            "DIRECTORY": '"/out"',
            "CHECKPASSWORD": "true",
        })
        result = _convert(node)
        assert any(
            "need_password" in w and "PASSWORD" in w
            for w in result.warnings
        )

    def test_no_warning_when_need_password_true_with_password(self):
        node = _make_node(params={
            "ZIPFILE": '"/data/archive.zip"',
            "DIRECTORY": '"/out"',
            "CHECKPASSWORD": "true",
            "PASSWORD": '"mypass"',
        })
        result = _convert(node)
        assert result.warnings == []

    def test_no_warnings_when_all_valid(self):
        node = _make_node(params={
            "ZIPFILE": '"/data/archive.zip"',
            "DIRECTORY": '"/out"',
        })
        result = _convert(node)
        assert result.warnings == []

    def test_multiple_warnings(self):
        """When both zipfile and directory are empty, both warnings appear."""
        node = _make_node(params={})
        result = _convert(node)
        assert len(result.warnings) >= 2


class TestFileUnarchiveBooleanParsing:
    """Test that boolean params handle various input formats."""

    def test_bool_true_string(self):
        node = _make_node(params={
            "ZIPFILE": '"f.zip"',
            "DIRECTORY": '"d"',
            "CHECKPASSWORD": "true",
            "PASSWORD": '"pw"',
        })
        result = _convert(node)
        assert result.component["config"]["need_password"] is True

    def test_bool_false_string(self):
        node = _make_node(params={
            "ZIPFILE": '"f.zip"',
            "DIRECTORY": '"d"',
            "DIE_ON_ERROR": "false",
        })
        result = _convert(node)
        assert result.component["config"]["die_on_error"] is False

    def test_bool_native_true(self):
        node = _make_node(params={
            "ZIPFILE": '"f.zip"',
            "DIRECTORY": '"d"',
            "DIE_ON_ERROR": True,
        })
        result = _convert(node)
        assert result.component["config"]["die_on_error"] is True

    def test_bool_string_one(self):
        node = _make_node(params={
            "ZIPFILE": '"f.zip"',
            "DIRECTORY": '"d"',
            "CHECKPASSWORD": "1",
            "PASSWORD": '"pw"',
        })
        result = _convert(node)
        assert result.component["config"]["need_password"] is True

    def test_bool_string_zero(self):
        node = _make_node(params={
            "ZIPFILE": '"f.zip"',
            "DIRECTORY": '"d"',
            "DIE_ON_ERROR": "0",
        })
        result = _convert(node)
        assert result.component["config"]["die_on_error"] is False


class TestFileUnarchiveEdgeCases:
    """Edge case tests."""

    def test_custom_component_id(self):
        node = _make_node(
            params={"ZIPFILE": '"a.zip"', "DIRECTORY": '"b"'},
            component_id="tFileUnarchive_99",
        )
        result = _convert(node)
        assert result.component["id"] == "tFileUnarchive_99"

    def test_unquoted_paths(self):
        """Params without surrounding quotes should still work."""
        node = _make_node(params={
            "ZIPFILE": "/data/archive.zip",
            "DIRECTORY": "/data/out/",
        })
        result = _convert(node)
        cfg = result.component["config"]
        assert cfg["zipfile"] == "/data/archive.zip"
        assert cfg["directory"] == "/data/out/"

    def test_connections_do_not_affect_config(self):
        node = _make_node(params={
            "ZIPFILE": '"f.zip"',
            "DIRECTORY": '"d/"',
        })
        conns = [
            TalendConnection(
                name="row1", source="tFileUnarchive_1", target="tLogRow_1",
                connector_type="FLOW",
            ),
        ]
        result = _convert(node, connections=conns)
        assert result.component["config"]["zipfile"] == "f.zip"

    def test_result_type_is_component_result(self):
        node = _make_node(params={
            "ZIPFILE": '"f.zip"',
            "DIRECTORY": '"d"',
        })
        result = _convert(node)
        assert isinstance(result, ComponentResult)

    def test_extract_path_defaults_to_false(self):
        """extract_path defaults to False when not specified (Talend default)."""
        node = _make_node(params={
            "ZIPFILE": '"f.zip"',
            "DIRECTORY": '"d"',
        })
        result = _convert(node)
        assert result.component["config"]["extract_path"] is False
        assert result.warnings == []


# ---------------------------------------------------------------------------
# New parameters
# ---------------------------------------------------------------------------

class TestNewParams:

    def test_rootname_default_false(self):
        node = _make_node(params={"ZIPFILE": '"f.zip"', "DIRECTORY": '"d"'})
        result = _convert(node)
        assert result.component["config"]["rootname"] is False

    def test_rootname_extracted(self):
        node = _make_node(params={
            "ZIPFILE": '"f.zip"', "DIRECTORY": '"d"',
            "ROOTNAME": "true",
        })
        result = _convert(node)
        assert result.component["config"]["rootname"] is True

    def test_integrity_default_false(self):
        node = _make_node(params={"ZIPFILE": '"f.zip"', "DIRECTORY": '"d"'})
        result = _convert(node)
        assert result.component["config"]["integrity"] is False

    def test_integrity_extracted(self):
        node = _make_node(params={
            "ZIPFILE": '"f.zip"', "DIRECTORY": '"d"',
            "INTEGRITY": "true",
        })
        result = _convert(node)
        assert result.component["config"]["integrity"] is True

    def test_decrypt_type_default_empty(self):
        node = _make_node(params={"ZIPFILE": '"f.zip"', "DIRECTORY": '"d"'})
        result = _convert(node)
        assert result.component["config"]["decrypt_type"] == ""

    def test_decrypt_type_extracted(self):
        node = _make_node(params={
            "ZIPFILE": '"f.zip"', "DIRECTORY": '"d"',
            "DECRYPT_TYPE": '"Zip4j Decrypt"',
        })
        result = _convert(node)
        assert result.component["config"]["decrypt_type"] == "Zip4j Decrypt"

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node(params={"ZIPFILE": '"f.zip"', "DIRECTORY": '"d"'})
        result = _convert(node)
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node(params={"ZIPFILE": '"f.zip"', "DIRECTORY": '"d"'})
        result = _convert(node)
        assert result.component["config"]["label"] == ""


# ---------------------------------------------------------------------------
# Engine-gap warnings
# ---------------------------------------------------------------------------

class TestEngineGapWarnings:

    def test_no_engine_warnings_for_defaults(self):
        node = _make_node(params={"ZIPFILE": '"f.zip"', "DIRECTORY": '"d"'})
        result = _convert(node)
        engine_warnings = [w for w in result.warnings if "engine" in w.lower()]
        assert engine_warnings == []

    def test_warning_when_integrity_enabled(self):
        node = _make_node(params={
            "ZIPFILE": '"f.zip"', "DIRECTORY": '"d"',
            "INTEGRITY": "true",
        })
        result = _convert(node)
        assert any("INTEGRITY" in w for w in result.warnings)

    def test_warning_when_rootname_enabled(self):
        node = _make_node(params={
            "ZIPFILE": '"f.zip"', "DIRECTORY": '"d"',
            "ROOTNAME": "true",
        })
        result = _convert(node)
        assert any("ROOTNAME" in w for w in result.warnings)

    def test_warning_when_decrypt_type_set(self):
        node = _make_node(params={
            "ZIPFILE": '"f.zip"', "DIRECTORY": '"d"',
            "DECRYPT_TYPE": '"Zip4j Decrypt"',
        })
        result = _convert(node)
        assert any("DECRYPT_TYPE" in w for w in result.warnings)

    def test_no_warning_when_decrypt_type_empty(self):
        node = _make_node(params={"ZIPFILE": '"f.zip"', "DIRECTORY": '"d"'})
        result = _convert(node)
        decrypt_warnings = [w for w in result.warnings if "DECRYPT_TYPE" in w]
        assert decrypt_warnings == []


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------

class TestCompleteness:

    def test_all_11_config_keys_present(self):
        node = _make_node(params={"ZIPFILE": '"f.zip"', "DIRECTORY": '"d"'})
        result = _convert(node)
        cfg = result.component["config"]
        expected_keys = {
            "zipfile", "directory", "extract_path",
            "need_password", "password", "die_on_error",
            "rootname", "integrity", "decrypt_type",
            "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected_keys
