"""Tests for the tMap converter."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from src.converters.talend_to_v2.components.base import (
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v2.components.registry import REGISTRY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flow_conn(name: str, source: str, target: str) -> TalendConnection:
    return TalendConnection(name=name, source=source, target=target, connector_type="FLOW")


def _reject_conn(name: str, source: str, target: str) -> TalendConnection:
    return TalendConnection(name=name, source=source, target=target, connector_type="REJECT")


def _make_tmap_node(
    component_id: str = "tMap_1",
    input_tables: list[dict] | None = None,
    var_tables: list[dict] | None = None,
    output_tables: list[dict] | None = None,
) -> TalendNode:
    """Build a TalendNode with raw_xml for a tMap component."""
    root = ET.Element("node", componentName="tMap")
    node_data = ET.SubElement(root, "nodeData", type="tMap")

    for table in (input_tables or []):
        attrs: dict[str, str] = {"name": table["name"]}
        if "matchingMode" in table:
            attrs["matchingMode"] = table["matchingMode"]
        if "innerJoin" in table:
            attrs["innerJoin"] = table["innerJoin"]
        if "lookupMode" in table:
            attrs["lookupMode"] = table["lookupMode"]
        if "activateExpressionFilter" in table:
            attrs["activateExpressionFilter"] = table["activateExpressionFilter"]
        if "expressionFilter" in table:
            attrs["expressionFilter"] = table["expressionFilter"]
        it = ET.SubElement(node_data, "inputTables", **attrs)
        for entry in table.get("entries", []):
            entry_attrs: dict[str, str] = {
                "name": entry["name"],
                "expression": entry.get("expression", ""),
            }
            if "operator" in entry:
                entry_attrs["operator"] = entry["operator"]
            if "type" in entry:
                entry_attrs["type"] = entry["type"]
            ET.SubElement(it, "mapperTableEntries", **entry_attrs)

    for table in (var_tables or []):
        vt = ET.SubElement(node_data, "varTables", name=table.get("name", "Var"))
        for entry in table.get("entries", []):
            ET.SubElement(
                vt,
                "mapperTableEntries",
                name=entry["name"],
                expression=entry.get("expression", ""),
                type=entry.get("type", "id_String"),
            )

    for table in (output_tables or []):
        attrs = {"name": table["name"]}
        if table.get("reject"):
            attrs["reject"] = "true"
        if table.get("rejectInnerJoin"):
            attrs["rejectInnerJoin"] = "true"
        if table.get("activateExpressionFilter"):
            attrs["activateExpressionFilter"] = "true"
        if table.get("expressionFilter"):
            attrs["expressionFilter"] = table["expressionFilter"]
        ot = ET.SubElement(node_data, "outputTables", **attrs)
        for entry in table.get("entries", []):
            ET.SubElement(
                ot,
                "mapperTableEntries",
                name=entry["name"],
                expression=entry.get("expression", ""),
                type=entry.get("type", "id_String"),
            )

    return TalendNode(
        component_id=component_id,
        component_type="tMap",
        params={},
        schema={},
        raw_xml=root,
    )


def _get_converter():
    from src.converters.talend_to_v2.components.map import TMapConverter

    return TMapConverter()


# ===========================================================================
# Sub-task 6a: Basic tMap with no lookups
# ===========================================================================


class TestMapBasic:
    """Basic tMap with no lookups."""

    def test_basic_passthrough(self) -> None:
        """tMap with one input, one output, simple column expressions."""
        node = _make_tmap_node(
            input_tables=[
                {
                    "name": "orders",
                    "matchingMode": "UNIQUE_MATCH",
                    "entries": [
                        {"name": "order_id", "type": "id_Integer"},
                        {"name": "amount", "type": "id_Double"},
                    ],
                }
            ],
            output_tables=[
                {
                    "name": "out1",
                    "entries": [
                        {"name": "order_id", "expression": "orders.order_id"},
                        {"name": "amount", "expression": "orders.amount"},
                    ],
                }
            ],
        )
        conns = [
            _flow_conn("orders", "tFileInput_1", "tMap_1"),
            _flow_conn("out1", "tMap_1", "tFileOutput_1"),
        ]
        result = _get_converter().convert(node, conns, {})
        comp = result.component

        assert comp["id"] == "tMap_1"
        assert comp["type"] == "map"
        assert comp["config"]["lookups"] == []
        assert comp["config"]["variables"] == []

        out = comp["config"]["outputs"][0]
        assert out["name"] == "out1"
        # Main edge prefix should be stripped
        assert out["columns"][0] == {"name": "order_id", "expression": "order_id"}
        assert out["columns"][1] == {"name": "amount", "expression": "amount"}

    def test_registered_in_registry(self) -> None:
        """tMap converter is accessible via REGISTRY."""
        # Force import to trigger registration
        import src.converters.talend_to_v2.components.map  # noqa: F401

        assert REGISTRY.get("tMap") is not None


# ===========================================================================
# Sub-task 6b: tMap with lookups
# ===========================================================================


class TestMapLookups:
    """tMap with lookups."""

    def test_join_key_extraction(self) -> None:
        """expression 'orders.product_id' with main_edge='orders'
        should produce main='product_id', lookup='product_id'."""
        node = _make_tmap_node(
            input_tables=[
                {
                    "name": "orders",
                    "entries": [
                        {"name": "order_id"},
                        {"name": "product_id"},
                    ],
                },
                {
                    "name": "products",
                    "matchingMode": "UNIQUE_MATCH",
                    "innerJoin": "false",
                    "entries": [
                        {
                            "name": "product_id",
                            "expression": "orders.product_id",
                            "operator": "==",
                        },
                        {"name": "product_name"},
                    ],
                },
            ],
            output_tables=[
                {
                    "name": "out1",
                    "entries": [
                        {"name": "order_id", "expression": "orders.order_id"},
                        {"name": "product_name", "expression": "products.product_name"},
                    ],
                }
            ],
        )
        conns = [
            _flow_conn("orders", "src1", "tMap_1"),
            _flow_conn("products", "src2", "tMap_1"),
            _flow_conn("out1", "tMap_1", "dst1"),
        ]
        result = _get_converter().convert(node, conns, {})
        lookups = result.component["config"]["lookups"]

        assert len(lookups) == 1
        lk = lookups[0]
        assert lk["name"] == "products"
        assert lk["join_type"] == "left"
        assert lk["matching_mode"] == "unique"
        assert lk["keys"] == [{"main": "product_id", "lookup": "product_id"}]

    def test_lookup_prefix_preserved_in_output(self) -> None:
        """'products.product_name' should stay as 'products.product_name'."""
        node = _make_tmap_node(
            input_tables=[
                {"name": "orders", "entries": [{"name": "order_id"}]},
                {
                    "name": "products",
                    "innerJoin": "false",
                    "entries": [
                        {"name": "product_id", "expression": "orders.order_id", "operator": "=="},
                        {"name": "product_name"},
                    ],
                },
            ],
            output_tables=[
                {
                    "name": "out1",
                    "entries": [
                        {"name": "pname", "expression": "products.product_name"},
                    ],
                }
            ],
        )
        conns = [
            _flow_conn("orders", "src1", "tMap_1"),
            _flow_conn("products", "src2", "tMap_1"),
            _flow_conn("out1", "tMap_1", "dst1"),
        ]
        result = _get_converter().convert(node, conns, {})
        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col["expression"] == "products.product_name"

    def test_multiple_lookups(self) -> None:
        """tMap with two lookup inputs."""
        node = _make_tmap_node(
            input_tables=[
                {"name": "orders", "entries": [{"name": "order_id"}, {"name": "cust_id"}]},
                {
                    "name": "products",
                    "innerJoin": "true",
                    "matchingMode": "UNIQUE_MATCH",
                    "entries": [
                        {"name": "product_id", "expression": "orders.order_id", "operator": "=="},
                        {"name": "product_name"},
                    ],
                },
                {
                    "name": "customers",
                    "innerJoin": "false",
                    "matchingMode": "ALL_ROWS",
                    "entries": [
                        {"name": "customer_id", "expression": "orders.cust_id", "operator": "=="},
                        {"name": "customer_name"},
                    ],
                },
            ],
            output_tables=[
                {
                    "name": "out1",
                    "entries": [
                        {"name": "order_id", "expression": "orders.order_id"},
                    ],
                }
            ],
        )
        conns = [
            _flow_conn("orders", "src1", "tMap_1"),
            _flow_conn("products", "src2", "tMap_1"),
            _flow_conn("customers", "src3", "tMap_1"),
            _flow_conn("out1", "tMap_1", "dst1"),
        ]
        result = _get_converter().convert(node, conns, {})
        lookups = result.component["config"]["lookups"]

        assert len(lookups) == 2
        assert lookups[0]["name"] == "products"
        assert lookups[0]["join_type"] == "inner"
        assert lookups[0]["matching_mode"] == "unique"
        assert lookups[1]["name"] == "customers"
        assert lookups[1]["join_type"] == "left"
        assert lookups[1]["matching_mode"] == "all"


# ===========================================================================
# Sub-task 6c: tMap with variables
# ===========================================================================


class TestMapVariables:
    """tMap with variables."""

    def test_var_expression_translated(self) -> None:
        """Variable expression 'orders.quantity * orders.unit_price' should become
        'quantity * unit_price'."""
        node = _make_tmap_node(
            input_tables=[
                {
                    "name": "orders",
                    "entries": [{"name": "quantity"}, {"name": "unit_price"}],
                }
            ],
            var_tables=[
                {
                    "name": "Var",
                    "entries": [
                        {
                            "name": "total_amount",
                            "expression": "orders.quantity * orders.unit_price",
                            "type": "id_Double",
                        }
                    ],
                }
            ],
            output_tables=[
                {
                    "name": "out1",
                    "entries": [
                        {"name": "total", "expression": "Var.total_amount"},
                    ],
                }
            ],
        )
        conns = [
            _flow_conn("orders", "src1", "tMap_1"),
            _flow_conn("out1", "tMap_1", "dst1"),
        ]
        result = _get_converter().convert(node, conns, {})
        variables = result.component["config"]["variables"]

        assert len(variables) == 1
        assert variables[0]["name"] == "total_amount"
        assert variables[0]["expression"] == "quantity * unit_price"

    def test_var_reference_in_output(self) -> None:
        """Output expression 'Var.total_amount' should become 'var.total_amount'."""
        node = _make_tmap_node(
            input_tables=[
                {"name": "orders", "entries": [{"name": "quantity"}]}
            ],
            var_tables=[
                {
                    "name": "Var",
                    "entries": [
                        {"name": "total_amount", "expression": "orders.quantity"},
                    ],
                }
            ],
            output_tables=[
                {
                    "name": "out1",
                    "entries": [
                        {"name": "total", "expression": "Var.total_amount"},
                    ],
                }
            ],
        )
        conns = [
            _flow_conn("orders", "src1", "tMap_1"),
            _flow_conn("out1", "tMap_1", "dst1"),
        ]
        result = _get_converter().convert(node, conns, {})
        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col["expression"] == "var.total_amount"


# ===========================================================================
# Sub-task 6d: Filters and reject outputs
# ===========================================================================


class TestMapFiltersAndRejects:
    """Filters and reject outputs."""

    def test_output_filter(self) -> None:
        """activateExpressionFilter=true with expressionFilter should create filter."""
        node = _make_tmap_node(
            input_tables=[
                {"name": "orders", "entries": [{"name": "status"}]}
            ],
            output_tables=[
                {
                    "name": "out1",
                    "activateExpressionFilter": "true",
                    "expressionFilter": "orders.status == 'ACTIVE'",
                    "entries": [
                        {"name": "status", "expression": "orders.status"},
                    ],
                }
            ],
        )
        conns = [
            _flow_conn("orders", "src1", "tMap_1"),
            _flow_conn("out1", "tMap_1", "dst1"),
        ]
        result = _get_converter().convert(node, conns, {})
        out = result.component["config"]["outputs"][0]
        # Filter should be present and main edge prefix stripped
        assert out["filter"] == "status == 'ACTIVE'"

    def test_reject_output(self) -> None:
        """outputTable with reject=true should be handled."""
        node = _make_tmap_node(
            input_tables=[
                {"name": "orders", "entries": [{"name": "order_id"}]},
                {
                    "name": "products",
                    "innerJoin": "true",
                    "entries": [
                        {"name": "pid", "expression": "orders.order_id", "operator": "=="},
                    ],
                },
            ],
            output_tables=[
                {
                    "name": "out1",
                    "entries": [
                        {"name": "order_id", "expression": "orders.order_id"},
                    ],
                },
                {
                    "name": "rejects",
                    "reject": True,
                    "rejectInnerJoin": True,
                    "entries": [
                        {"name": "order_id", "expression": "orders.order_id"},
                    ],
                },
            ],
        )
        conns = [
            _flow_conn("orders", "src1", "tMap_1"),
            _flow_conn("products", "src2", "tMap_1"),
            _flow_conn("out1", "tMap_1", "dst1"),
            _reject_conn("rejects", "tMap_1", "dst2"),
        ]
        result = _get_converter().convert(node, conns, {})
        outputs = result.component["config"]["outputs"]
        reject_outputs = [o for o in outputs if o.get("reject")]
        assert len(reject_outputs) == 1
        assert reject_outputs[0]["name"] == "rejects"

    def test_no_filter_when_inactive(self) -> None:
        """No filter attribute when activateExpressionFilter is absent or false."""
        node = _make_tmap_node(
            input_tables=[
                {"name": "orders", "entries": [{"name": "order_id"}]}
            ],
            output_tables=[
                {
                    "name": "out1",
                    "entries": [
                        {"name": "order_id", "expression": "orders.order_id"},
                    ],
                }
            ],
        )
        conns = [
            _flow_conn("orders", "src1", "tMap_1"),
            _flow_conn("out1", "tMap_1", "dst1"),
        ]
        result = _get_converter().convert(node, conns, {})
        out = result.component["config"]["outputs"][0]
        assert "filter" not in out


# ===========================================================================
# Sub-task 6e: Matching modes
# ===========================================================================


class TestMapMatchingModes:
    """Matching mode mapping."""

    @pytest.mark.parametrize(
        "talend_mode, expected",
        [
            ("UNIQUE_MATCH", "unique"),
            ("ALL_ROWS", "all"),
            ("FIRST_MATCH", "first"),
            ("LAST_MATCH", "last"),
        ],
    )
    def test_matching_mode_mapping(self, talend_mode: str, expected: str) -> None:
        node = _make_tmap_node(
            input_tables=[
                {"name": "main_in", "entries": [{"name": "id"}]},
                {
                    "name": "lookup_in",
                    "matchingMode": talend_mode,
                    "innerJoin": "false",
                    "entries": [
                        {"name": "id", "expression": "main_in.id", "operator": "=="},
                    ],
                },
            ],
            output_tables=[
                {
                    "name": "out1",
                    "entries": [
                        {"name": "id", "expression": "main_in.id"},
                    ],
                }
            ],
        )
        conns = [
            _flow_conn("main_in", "src1", "tMap_1"),
            _flow_conn("lookup_in", "src2", "tMap_1"),
            _flow_conn("out1", "tMap_1", "dst1"),
        ]
        result = _get_converter().convert(node, conns, {})
        assert result.component["config"]["lookups"][0]["matching_mode"] == expected


# ===========================================================================
# Sub-task 6f: Flow routing (critical bug fix)
# ===========================================================================


class TestMapFlowRouting:
    """Flow routing."""

    def _build_standard_scenario(self):
        """Build a standard scenario with main + lookup + 2 outputs + reject."""
        node = _make_tmap_node(
            input_tables=[
                {"name": "orders", "entries": [{"name": "order_id"}, {"name": "pid"}]},
                {
                    "name": "products",
                    "innerJoin": "true",
                    "entries": [
                        {"name": "product_id", "expression": "orders.pid", "operator": "=="},
                    ],
                },
            ],
            output_tables=[
                {
                    "name": "enriched",
                    "entries": [
                        {"name": "order_id", "expression": "orders.order_id"},
                    ],
                },
                {
                    "name": "rejects",
                    "reject": True,
                    "entries": [
                        {"name": "order_id", "expression": "orders.order_id"},
                    ],
                },
            ],
        )
        conns = [
            _flow_conn("orders", "src1", "tMap_1"),
            _flow_conn("products", "src2", "tMap_1"),
            _flow_conn("enriched", "tMap_1", "dst1"),
            _reject_conn("rejects", "tMap_1", "dst2"),
        ]
        return node, conns

    def test_main_input_flow(self) -> None:
        """Main input connection should generate flow with input='main'."""
        node, conns = self._build_standard_scenario()
        result = _get_converter().convert(node, conns, {})
        main_flows = [f for f in result.flows if f.get("input") == "main"]
        assert len(main_flows) == 1
        assert main_flows[0]["source"] == "src1"
        assert main_flows[0]["target"] == "tMap_1"

    def test_lookup_input_flow(self) -> None:
        """Lookup input connections should generate flows with input=lookup_name."""
        node, conns = self._build_standard_scenario()
        result = _get_converter().convert(node, conns, {})
        lookup_flows = [f for f in result.flows if f.get("input") == "products"]
        assert len(lookup_flows) == 1
        assert lookup_flows[0]["source"] == "src2"

    def test_output_flow_matching(self) -> None:
        """Output flows should match by outputTable name."""
        node, conns = self._build_standard_scenario()
        result = _get_converter().convert(node, conns, {})
        out_flows = [
            f for f in result.flows
            if f.get("source") == "tMap_1" and f.get("output") != "reject"
        ]
        assert len(out_flows) == 1
        assert out_flows[0]["name"] == "enriched"
        assert out_flows[0]["output"] == "enriched"

    def test_reject_flow(self) -> None:
        """Reject output should generate flow with output='reject'."""
        node, conns = self._build_standard_scenario()
        result = _get_converter().convert(node, conns, {})
        reject_flows = [f for f in result.flows if f.get("output") == "reject"]
        assert len(reject_flows) == 1
        assert reject_flows[0]["name"] == "rejects"


# ===========================================================================
# Sub-task 6g: Input filter
# ===========================================================================


class TestMapInputFilter:
    """Input table filter (expression filter on main input)."""

    def test_input_filter_generates_warning(self) -> None:
        """An input table with an expression filter should produce a needs_review."""
        node = _make_tmap_node(
            input_tables=[
                {
                    "name": "orders",
                    "activateExpressionFilter": "true",
                    "expressionFilter": '"COMPLETED".equals(orders.status)',
                    "entries": [{"name": "order_id"}, {"name": "status"}],
                }
            ],
            output_tables=[
                {
                    "name": "out1",
                    "entries": [
                        {"name": "order_id", "expression": "orders.order_id"},
                    ],
                }
            ],
        )
        conns = [
            _flow_conn("orders", "src1", "tMap_1"),
            _flow_conn("out1", "tMap_1", "dst1"),
        ]
        result = _get_converter().convert(node, conns, {})
        # Input filters are complex Java; should generate a needs_review item
        assert len(result.needs_review) >= 1
