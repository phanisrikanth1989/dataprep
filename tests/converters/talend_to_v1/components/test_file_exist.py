"""Tests for tFileExist -> FileExistComponent converter.

Tests cover:
- Config key rename: filename -> file_path (CRITICAL engine compatibility fix)
- New params: tstatcatcher_stats, label
- Unconditional engine-gap warning: EXISTS globalMap not set
- Empty/missing FILE_NAME warning
- Schema is empty (utility component)
- Component structure
- Registry
"""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_exist import (
    FileExistConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tFileExist_1"):
    """Create a minimal TalendNode for tFileExist testing."""
    return TalendNode(
        component_id=component_id,
        component_type="tFileExist",
        params=params or {},
        schema={},
        position={"x": 100, "y": 200},
    )


# ------------------------------------------------------------------
# Core conversion logic
# ------------------------------------------------------------------
class TestFileExistConverter:
    """Tests for FileExistConverter conversion logic."""

    def test_basic_conversion(self):
        """Full round-trip: quoted filename, all params set."""
        node = _make_node(params={
            "FILE_NAME": '"/data/test_file.txt"',
            "TSTATCATCHER_STATS": "true",
            "LABEL": '"check_file"',
        })
        result = FileExistConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "tFileExist_1"
        assert comp["type"] == "FileExistComponent"
        assert comp["original_type"] == "tFileExist"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["file_path"] == "/data/test_file.txt"
        assert "filename" not in cfg
        assert cfg["tstatcatcher_stats"] is True
        assert cfg["label"] == "check_file"

    def test_file_path_key_not_filename(self):
        """CRITICAL: Config key is 'file_path' (engine reads it), NOT 'filename'."""
        node = _make_node(params={"FILE_NAME": '"/data/test.txt"'})
        result = FileExistConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert "file_path" in cfg
        assert cfg["file_path"] == "/data/test.txt"
        assert "filename" not in cfg

    def test_defaults_when_params_missing(self):
        """Missing optional params fall back to correct defaults."""
        node = _make_node(params={"FILE_NAME": '"/data/file.txt"'})
        result = FileExistConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["tstatcatcher_stats"] is False
        assert cfg["label"] == ""

    def test_all_config_keys_present(self):
        """Exactly 3 config keys should be present: file_path, tstatcatcher_stats, label."""
        node = _make_node(params={"FILE_NAME": '"/data/file.txt"'})
        result = FileExistConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert set(cfg.keys()) == {"file_path", "tstatcatcher_stats", "label"}

    def test_filename_without_quotes(self):
        """Unquoted FILE_NAME param is accepted as-is."""
        node = _make_node(params={"FILE_NAME": "/opt/files/output.txt"})
        result = FileExistConverter().convert(node, [], {})
        assert result.component["config"]["file_path"] == "/opt/files/output.txt"

    def test_empty_filename_generates_warning(self):
        """Empty FILE_NAME generates a warning about runtime failure."""
        node = _make_node(params={"FILE_NAME": ""})
        result = FileExistConverter().convert(node, [], {})
        assert result.component["config"]["file_path"] == ""
        assert any("FILE_NAME is empty" in w for w in result.warnings)

    def test_missing_filename_generates_warning(self):
        """Missing FILE_NAME param generates a warning about runtime failure."""
        node = _make_node(params={})
        result = FileExistConverter().convert(node, [], {})
        assert result.component["config"]["file_path"] == ""
        assert any("FILE_NAME is empty" in w for w in result.warnings)

    def test_context_variable_in_filename(self):
        """Context variables in FILE_NAME are preserved as-is for engine resolution."""
        node = _make_node(params={"FILE_NAME": "context.input_path"})
        result = FileExistConverter().convert(node, [], {})
        assert result.component["config"]["file_path"] == "context.input_path"

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={"FILE_NAME": '"/data/test.txt"'})
        result = FileExistConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)


# ------------------------------------------------------------------
# Engine-gap warnings
# ------------------------------------------------------------------
class TestFileExistEngineGapWarnings:
    """Tests for engine-gap warnings."""

    def test_exists_globalmap_warning_always_present(self):
        """Unconditional warning about engine not setting EXISTS globalMap variable."""
        node = _make_node(params={"FILE_NAME": '"/data/test.txt"'})
        result = FileExistConverter().convert(node, [], {})
        exists_warnings = [w for w in result.warnings if "EXISTS" in w and "globalMap" in w]
        assert len(exists_warnings) == 1
        assert "tFileExist_1_EXISTS" in exists_warnings[0]
        assert "RunIf" in exists_warnings[0]

    def test_exists_warning_uses_component_id(self):
        """The EXISTS warning includes the actual component_id, not a generic placeholder."""
        node = _make_node(params={"FILE_NAME": '"/data/test.txt"'}, component_id="tFileExist_5")
        result = FileExistConverter().convert(node, [], {})
        exists_warnings = [w for w in result.warnings if "EXISTS" in w and "globalMap" in w]
        assert len(exists_warnings) == 1
        assert "tFileExist_5_EXISTS" in exists_warnings[0]

    def test_exists_warning_present_even_with_empty_filename(self):
        """EXISTS warning fires even when FILE_NAME is empty (both warnings present)."""
        node = _make_node(params={})
        result = FileExistConverter().convert(node, [], {})
        assert any("FILE_NAME is empty" in w for w in result.warnings)
        assert any("EXISTS" in w and "globalMap" in w for w in result.warnings)
        # Should have exactly 2 warnings: empty filename + EXISTS
        assert len(result.warnings) == 2


# ------------------------------------------------------------------
# Schema and structure
# ------------------------------------------------------------------
class TestFileExistSchema:
    """Tests for schema and component structure."""

    def test_schema_is_empty(self):
        """tFileExist is a utility component with no data flow schema."""
        node = _make_node(params={"FILE_NAME": '"/tmp/test"'})
        result = FileExistConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}

    def test_component_structure_has_io_lists(self):
        """Component has inputs and outputs as empty lists."""
        node = _make_node(params={"FILE_NAME": '"/tmp/test"'})
        result = FileExistConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"FILE_NAME": '"/tmp/test"'})
        result = FileExistConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert set(comp.keys()) == expected_keys


# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------
class TestFileExistRegistry:
    """Verify the converter is properly registered."""

    def test_registered_under_tfileexist(self):
        """Converter is registered under 'tFileExist'."""
        cls = REGISTRY.get("tFileExist")
        assert cls is FileExistConverter

    def test_tfileexist_in_type_list(self):
        """'tFileExist' appears in the registry type list."""
        assert "tFileExist" in REGISTRY.list_types()
