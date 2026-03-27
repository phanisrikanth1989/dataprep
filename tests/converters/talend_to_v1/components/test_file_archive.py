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
        assert cfg["compression_level"] == "9"
        assert cfg["die_on_error"] is False  # default
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
        assert cfg["overwrite"] is True
        assert cfg["compression_level"] == "Normal"

    def test_archive_format_default_zip(self):
        """ARCHIVE_FORMAT defaults to 'zip' when not specified."""
        node = _make_node(params={
            "SOURCE": '"/data"',
            "TARGET": '"/data.zip"',
        })
        result = _convert(node)
        assert result.component["config"]["archive_format"] == "zip"

    def test_compression_level_default_normal(self):
        """LEVEL defaults to 'Normal' when not specified (Talend enum label)."""
        node = _make_node(params={
            "SOURCE": '"/data"',
            "TARGET": '"/data.zip"',
        })
        result = _convert(node)
        assert result.component["config"]["compression_level"] == "Normal"


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
        """LEVEL provided as a quoted string should stay as string."""
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "LEVEL": '"6"',
        })
        result = _convert(node)
        assert result.component["config"]["compression_level"] == "6"


# ---------------------------------------------------------------------------
# New parameters
# ---------------------------------------------------------------------------

class TestNewParams:

    def test_source_file_default_empty(self):
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        assert result.component["config"]["source_file"] == ""

    def test_source_file_extracted(self):
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "SOURCE_FILE": '"/data/input.gz"',
        })
        result = _convert(node)
        assert result.component["config"]["source_file"] == "/data/input.gz"

    def test_create_directory_default_false(self):
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        assert result.component["config"]["create_directory"] is False

    def test_all_files_default_true(self):
        """ALL_FILES defaults to True (unlike most booleans)."""
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        assert result.component["config"]["all_files"] is True

    def test_filemask_default_empty(self):
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        assert result.component["config"]["filemask"] == ""

    def test_encoding_default_empty(self):
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        assert result.component["config"]["encoding"] == ""

    def test_encrypt_files_default_false(self):
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        assert result.component["config"]["encrypt_files"] is False

    def test_encrypt_method_default_empty(self):
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        assert result.component["config"]["encrypt_method"] == ""

    def test_aes_key_strength_default_empty(self):
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        assert result.component["config"]["aes_key_strength"] == ""

    def test_password_default_empty(self):
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        assert result.component["config"]["password"] == ""

    def test_zip64_mode_default_empty(self):
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        assert result.component["config"]["zip64_mode"] == ""

    def test_use_sync_flush_default_false(self):
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        assert result.component["config"]["use_sync_flush"] is False

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        assert result.component["config"]["label"] == ""


# ---------------------------------------------------------------------------
# Engine-gap warnings
# ---------------------------------------------------------------------------

class TestEngineGapWarnings:

    def test_no_engine_warnings_for_defaults(self):
        """Default archive_format is zip, no encryption, no filemask."""
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        engine_warnings = [w for w in result.warnings if "engine" in w.lower()]
        assert engine_warnings == []

    def test_warning_when_non_zip_format(self):
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "ARCHIVE_FORMAT": '"tar.gz"',
        })
        result = _convert(node)
        assert any("ARCHIVE_FORMAT" in w for w in result.warnings)

    def test_warning_when_encrypt_files_enabled(self):
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "ENCRYPT_FILES": "true",
        })
        result = _convert(node)
        assert any("ENCRYPT_FILES" in w for w in result.warnings)

    def test_warning_when_filemask_set(self):
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "FILEMASK": '"*.csv"',
        })
        result = _convert(node)
        assert any("FILEMASK" in w for w in result.warnings)

    def test_warning_when_use_sync_flush_enabled(self):
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "USE_SYNC_FLUSH": "true",
        })
        result = _convert(node)
        assert any("USE_SYNC_FLUSH" in w for w in result.warnings)

    def test_warning_when_zip64_mode_non_default(self):
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "ZIP64_MODE": '"ALWAYS"',
        })
        result = _convert(node)
        assert any("ZIP64_MODE" in w for w in result.warnings)

    def test_no_warning_when_zip64_mode_asneeded(self):
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "ZIP64_MODE": '"ASNEEDED"',
        })
        result = _convert(node)
        zip64_warnings = [w for w in result.warnings if "ZIP64_MODE" in w]
        assert zip64_warnings == []

    def test_warning_when_create_directory_enabled(self):
        node = _make_node(params={
            "SOURCE": '"s"', "TARGET": '"t"',
            "CREATE_DIRECTORY": "true",
        })
        result = _convert(node)
        assert any("CREATE_DIRECTORY" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------

class TestCompleteness:

    def test_all_20_config_keys_present(self):
        node = _make_node(params={"SOURCE": '"s"', "TARGET": '"t"'})
        result = _convert(node)
        cfg = result.component["config"]
        expected_keys = {
            "source", "target", "archive_format", "include_subdirectories",
            "overwrite", "compression_level", "die_on_error",
            "source_file", "create_directory", "all_files", "filemask",
            "encoding", "encrypt_files", "encrypt_method", "aes_key_strength",
            "password", "zip64_mode", "use_sync_flush",
            "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected_keys
