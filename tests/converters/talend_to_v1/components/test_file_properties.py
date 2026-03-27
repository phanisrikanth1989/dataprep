"""Tests for tFileProperties -> FileProperties converter."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_properties import (
    FilePropertiesConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tFileProperties_1",
               component_type="tFileProperties"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema={},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


class TestFilePropertiesConverter:
    """Core conversion logic."""

    def test_basic_conversion(self):
        node = _make_node(params={
            "FILENAME": '"/tmp/data.csv"',
            "MD5": "true",
        })
        result = FilePropertiesConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "tFileProperties_1"
        assert comp["type"] == "FileProperties"
        assert comp["original_type"] == "tFileProperties"
        assert comp["config"]["filename"] == "/tmp/data.csv"
        assert comp["config"]["calculate_md5"] is True
        assert comp["position"] == {"x": 100, "y": 200}
        assert result.warnings == []

    def test_md5_false(self):
        node = _make_node(params={
            "FILENAME": '"/opt/files/report.txt"',
            "MD5": "false",
        })
        result = FilePropertiesConverter().convert(node, [], {})

        assert result.component["config"]["filename"] == "/opt/files/report.txt"
        assert result.component["config"]["calculate_md5"] is False
        assert result.warnings == []

    def test_md5_defaults_to_false_when_missing(self):
        node = _make_node(params={"FILENAME": '"/tmp/file.dat"'})
        result = FilePropertiesConverter().convert(node, [], {})

        assert result.component["config"]["calculate_md5"] is False
        assert result.warnings == []

    def test_empty_filename_generates_warning(self):
        node = _make_node(params={"FILENAME": "", "MD5": "true"})
        result = FilePropertiesConverter().convert(node, [], {})

        assert result.component["config"]["filename"] == ""
        assert len(result.warnings) == 1
        assert "FILENAME is empty" in result.warnings[0]

    def test_missing_filename_generates_warning(self):
        node = _make_node(params={})
        result = FilePropertiesConverter().convert(node, [], {})

        assert result.component["config"]["filename"] == ""
        assert result.component["config"]["calculate_md5"] is False
        assert len(result.warnings) == 1
        assert "FILENAME is empty" in result.warnings[0]

    def test_filename_without_quotes(self):
        node = _make_node(params={
            "FILENAME": "/var/log/app.log",
            "MD5": "true",
        })
        result = FilePropertiesConverter().convert(node, [], {})

        assert result.component["config"]["filename"] == "/var/log/app.log"

    def test_schema_is_empty(self):
        """tFileProperties is a utility component -- schema should be empty."""
        node = _make_node(params={"FILENAME": '"/tmp/test"'})
        result = FilePropertiesConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}

    def test_component_structure_has_io_lists(self):
        node = _make_node(params={"FILENAME": '"/tmp/test"'})
        result = FilePropertiesConverter().convert(node, [], {})

        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


class TestFilePropertiesRegistry:
    """Verify the converter is properly registered."""

    def test_registered_under_tfileproperties(self):
        cls = REGISTRY.get("tFileProperties")
        assert cls is FilePropertiesConverter

    def test_tfileproperties_in_type_list(self):
        assert "tFileProperties" in REGISTRY.list_types()


# ---------------------------------------------------------------------------
# New parameters
# ---------------------------------------------------------------------------

class TestNewParams:

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node(params={"FILENAME": '"/tmp/data.csv"'})
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_extracted(self):
        node = _make_node(params={
            "FILENAME": '"/tmp/data.csv"',
            "TSTATCATCHER_STATS": "true",
        })
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node(params={"FILENAME": '"/tmp/data.csv"'})
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={
            "FILENAME": '"/tmp/data.csv"',
            "LABEL": '"file_props_step"',
        })
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "file_props_step"


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------

class TestCompleteness:

    def test_all_4_config_keys_present(self):
        node = _make_node(params={"FILENAME": '"/tmp/data.csv"'})
        result = FilePropertiesConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "filename", "calculate_md5",
            "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected_keys
