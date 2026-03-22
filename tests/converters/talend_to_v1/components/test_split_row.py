"""Tests for the SplitRowConverter (tSplitRow -> SplitRow)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.split_row import (
    SplitRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="split_1",
               component_type="tSplitRow"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 300, "y": 400},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="name", type="id_String", nullable=True),
            SchemaColumn(name="amount", type="id_Double", nullable=True),
        ]
    }


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------
class TestSplitRowRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tSplitRow") is SplitRowConverter


# ------------------------------------------------------------------
# Basic / happy-path
# ------------------------------------------------------------------
class TestSplitRowBasic:
    def test_single_mapping(self):
        node = _make_node(params={
            "COL_MAPPING": [
                {"elementRef": "SOURCE_COLUMN", "value": '"src_col"'},
                {"elementRef": "TARGET_COLUMN", "value": '"tgt_col"'},
            ],
            "CONNECTION_FORMAT": '"row"',
        })
        result = SplitRowConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "split_1"
        assert comp["type"] == "SplitRow"
        assert comp["original_type"] == "tSplitRow"
        assert comp["position"] == {"x": 300, "y": 400}
        cfg = comp["config"]
        assert cfg["col_mapping"] == [{"source": "src_col", "target": "tgt_col"}]
        assert cfg["connection_format"] == "row"
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_multiple_mappings(self):
        node = _make_node(params={
            "COL_MAPPING": [
                {"elementRef": "SOURCE_COLUMN", "value": '"col_a"'},
                {"elementRef": "TARGET_COLUMN", "value": '"out_a"'},
                {"elementRef": "SOURCE_COLUMN", "value": '"col_b"'},
                {"elementRef": "TARGET_COLUMN", "value": '"out_b"'},
                {"elementRef": "SOURCE_COLUMN", "value": '"col_c"'},
                {"elementRef": "TARGET_COLUMN", "value": '"out_c"'},
            ],
            "CONNECTION_FORMAT": '"row"',
        })
        result = SplitRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["col_mapping"] == [
            {"source": "col_a", "target": "out_a"},
            {"source": "col_b", "target": "out_b"},
            {"source": "col_c", "target": "out_c"},
        ]
        assert result.warnings == []

    def test_connection_format_default(self):
        """When CONNECTION_FORMAT is missing, it defaults to 'row'."""
        node = _make_node(params={
            "COL_MAPPING": [
                {"elementRef": "SOURCE_COLUMN", "value": '"s"'},
                {"elementRef": "TARGET_COLUMN", "value": '"t"'},
            ],
        })
        result = SplitRowConverter().convert(node, [], {})

        assert result.component["config"]["connection_format"] == "row"

    def test_connection_format_custom(self):
        """A non-default CONNECTION_FORMAT value is preserved."""
        node = _make_node(params={
            "COL_MAPPING": [
                {"elementRef": "SOURCE_COLUMN", "value": '"s"'},
                {"elementRef": "TARGET_COLUMN", "value": '"t"'},
            ],
            "CONNECTION_FORMAT": '"iterate"',
        })
        result = SplitRowConverter().convert(node, [], {})

        assert result.component["config"]["connection_format"] == "iterate"


# ------------------------------------------------------------------
# Empty and missing COL_MAPPING
# ------------------------------------------------------------------
class TestSplitRowEmptyAndMissing:
    def test_empty_col_mapping_list(self):
        node = _make_node(params={"COL_MAPPING": []})
        result = SplitRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["col_mapping"] == []
        assert any("No column mappings" in w for w in result.warnings)

    def test_missing_col_mapping_param(self):
        node = _make_node(params={})
        result = SplitRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["col_mapping"] == []
        assert any("No column mappings" in w for w in result.warnings)

    def test_col_mapping_not_a_list(self):
        """If COL_MAPPING is not a list (unexpected), produce a warning."""
        node = _make_node(params={"COL_MAPPING": "not_a_list"})
        result = SplitRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["col_mapping"] == []
        assert any("not a list" in w for w in result.warnings)


# ------------------------------------------------------------------
# Unpaired entries
# ------------------------------------------------------------------
class TestSplitRowUnpairedEntries:
    def test_source_without_target(self):
        """A trailing SOURCE_COLUMN with no TARGET_COLUMN should be skipped
        with a warning."""
        node = _make_node(params={
            "COL_MAPPING": [
                {"elementRef": "SOURCE_COLUMN", "value": '"good_src"'},
                {"elementRef": "TARGET_COLUMN", "value": '"good_tgt"'},
                {"elementRef": "SOURCE_COLUMN", "value": '"orphan_src"'},
            ],
        })
        result = SplitRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["col_mapping"] == [{"source": "good_src", "target": "good_tgt"}]
        assert any("orphan_src" in w for w in result.warnings)

    def test_target_without_source(self):
        """A TARGET_COLUMN without a preceding SOURCE_COLUMN is skipped
        with a warning."""
        node = _make_node(params={
            "COL_MAPPING": [
                {"elementRef": "TARGET_COLUMN", "value": '"lonely_tgt"'},
                {"elementRef": "SOURCE_COLUMN", "value": '"real_src"'},
                {"elementRef": "TARGET_COLUMN", "value": '"real_tgt"'},
            ],
        })
        result = SplitRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["col_mapping"] == [{"source": "real_src", "target": "real_tgt"}]
        assert any("no preceding SOURCE_COLUMN" in w for w in result.warnings)

    def test_consecutive_sources_without_targets(self):
        """Two consecutive SOURCE_COLUMNs: the first is skipped with a warning."""
        node = _make_node(params={
            "COL_MAPPING": [
                {"elementRef": "SOURCE_COLUMN", "value": '"first"'},
                {"elementRef": "SOURCE_COLUMN", "value": '"second"'},
                {"elementRef": "TARGET_COLUMN", "value": '"tgt"'},
            ],
        })
        result = SplitRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["col_mapping"] == [{"source": "second", "target": "tgt"}]
        assert any("first" in w and "no matching TARGET_COLUMN" in w
                    for w in result.warnings)

    def test_empty_source_or_target_skipped(self):
        """Pairs where source or target is empty after quote-stripping
        should be skipped with a warning."""
        node = _make_node(params={
            "COL_MAPPING": [
                {"elementRef": "SOURCE_COLUMN", "value": '""'},
                {"elementRef": "TARGET_COLUMN", "value": '"tgt"'},
                {"elementRef": "SOURCE_COLUMN", "value": '"src"'},
                {"elementRef": "TARGET_COLUMN", "value": '""'},
            ],
        })
        result = SplitRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["col_mapping"] == []
        assert any("Empty source or target" in w for w in result.warnings)


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------
class TestSplitRowSchema:
    def test_schema_passthrough(self):
        """SplitRow passes the schema through: input == output."""
        node = _make_node(
            params={
                "COL_MAPPING": [
                    {"elementRef": "SOURCE_COLUMN", "value": '"id"'},
                    {"elementRef": "TARGET_COLUMN", "value": '"out_id"'},
                ],
            },
            schema=_make_schema_columns(),
        )
        result = SplitRowConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][1]["name"] == "name"
        assert schema["input"][2]["name"] == "amount"

    def test_empty_schema(self):
        """When no FLOW schema is present, input and output are empty lists."""
        node = _make_node(params={})
        result = SplitRowConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}
