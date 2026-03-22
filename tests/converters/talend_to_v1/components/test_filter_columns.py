"""Tests for tFilterColumns -> FilterColumns converter."""
import xml.etree.ElementTree as ET

import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.filter_columns import (
    FilterColumnsConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(
    flow_columns=None,
    params=None,
    component_id="tFilterColumns_1",
):
    """Create a TalendNode for tFilterColumns with the given FLOW schema columns."""
    schema = {}
    if flow_columns is not None:
        schema["FLOW"] = [
            SchemaColumn(name=c, type="id_String") if isinstance(c, str) else c
            for c in flow_columns
        ]
    return TalendNode(
        component_id=component_id,
        component_type="tFilterColumns",
        params=params or {},
        schema=schema,
        position={"x": 320, "y": 160},
        raw_xml=ET.Element("node"),
    )


def _convert(node, connections=None, context=None):
    """Helper to run the converter."""
    converter = FilterColumnsConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


class TestFilterColumnsRegistration:
    """Verify the converter is registered in the global registry."""

    def test_registered_for_tfiltercolumns(self):
        cls = REGISTRY.get("tFilterColumns")
        assert cls is FilterColumnsConverter


# ------------------------------------------------------------------
# Basic conversion
# ------------------------------------------------------------------


class TestFilterColumnsBasicConversion:
    """Test column extraction from FLOW schema and component structure."""

    def test_single_column(self):
        node = _make_node(flow_columns=["name"])
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tFilterColumns_1"
        assert comp["type"] == "FilterColumns"
        assert comp["original_type"] == "tFilterColumns"
        assert comp["position"] == {"x": 320, "y": 160}
        assert comp["config"]["columns"] == ["name"]
        assert result.warnings == []

    def test_multiple_columns(self):
        node = _make_node(flow_columns=["id", "name", "email", "status"])
        result = _convert(node)

        assert result.component["config"]["columns"] == [
            "id", "name", "email", "status",
        ]
        assert result.warnings == []

    def test_component_structure_has_required_keys(self):
        node = _make_node(flow_columns=["col_a"])
        result = _convert(node)
        comp = result.component
        assert set(comp.keys()) == {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_output_schema_matches_flow_columns(self):
        node = _make_node(flow_columns=["first_name", "last_name"])
        result = _convert(node)

        out_schema = result.component["schema"]["output"]
        assert len(out_schema) == 2
        assert out_schema[0]["name"] == "first_name"
        assert out_schema[1]["name"] == "last_name"

    def test_input_schema_is_empty(self):
        """FilterColumns does not specify an explicit input schema."""
        node = _make_node(flow_columns=["a", "b"])
        result = _convert(node)
        assert result.component["schema"]["input"] == []


# ------------------------------------------------------------------
# Empty / missing schema
# ------------------------------------------------------------------


class TestFilterColumnsEmptySchema:
    """Test behaviour when no columns are present."""

    def test_no_flow_schema_produces_warning(self):
        node = _make_node(flow_columns=None)
        result = _convert(node)

        assert result.component["config"]["columns"] == []
        assert any("No columns" in w for w in result.warnings)

    def test_empty_flow_schema_produces_warning(self):
        node = _make_node(flow_columns=[])
        result = _convert(node)

        assert result.component["config"]["columns"] == []
        assert any("No columns" in w for w in result.warnings)


# ------------------------------------------------------------------
# Column types are propagated in schema
# ------------------------------------------------------------------


class TestFilterColumnsSchemaTypes:
    """Ensure column metadata is properly converted into the output schema."""

    def test_typed_columns(self):
        cols = [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="amount", type="id_Double", precision=2),
            SchemaColumn(name="created", type="id_Date", date_pattern="yyyy-MM-dd"),
        ]
        node = _make_node(flow_columns=cols)
        result = _convert(node)

        out = result.component["schema"]["output"]
        assert out[0]["name"] == "id"
        assert out[0]["type"] == "int"
        assert out[0]["nullable"] is False
        assert out[0]["key"] is True

        assert out[1]["name"] == "amount"
        assert out[1]["type"] == "float"
        assert out[1]["precision"] == 2

        assert out[2]["name"] == "created"
        assert out[2]["type"] == "datetime"
        assert out[2]["date_pattern"] == "%Y-%m-%d"


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


class TestFilterColumnsEdgeCases:
    """Edge-case and miscellaneous tests."""

    def test_custom_component_id(self):
        node = _make_node(flow_columns=["x"], component_id="tFilterColumns_99")
        result = _convert(node)
        assert result.component["id"] == "tFilterColumns_99"

    def test_result_type_is_component_result(self):
        node = _make_node(flow_columns=["a"])
        result = _convert(node)
        assert isinstance(result, ComponentResult)

    def test_connections_do_not_affect_config(self):
        node = _make_node(flow_columns=["col"])
        conns = [
            TalendConnection(
                name="row1",
                source="tFilterColumns_1",
                target="tLogRow_1",
                connector_type="FLOW",
            ),
        ]
        result = _convert(node, connections=conns)
        assert result.component["config"]["columns"] == ["col"]

    def test_params_are_ignored(self):
        """tFilterColumns config comes from schema, not elementParameters."""
        node = _make_node(
            flow_columns=["real_col"],
            params={"COLUMNS": ["fake_col"], "MODE": "include"},
        )
        result = _convert(node)
        assert result.component["config"]["columns"] == ["real_col"]
        # No MODE or KEEP_ROW_ORDER keys should appear
        assert "mode" not in result.component["config"]
        assert "keep_row_order" not in result.component["config"]

    def test_column_order_preserved(self):
        """Column order in the FLOW schema must be preserved."""
        cols = ["z_col", "a_col", "m_col"]
        node = _make_node(flow_columns=cols)
        result = _convert(node)
        assert result.component["config"]["columns"] == cols
