"""Converter for the Talend tMap component."""
from __future__ import annotations

from typing import Any, Dict, List
from xml.etree.ElementTree import Element

from .base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from .registry import REGISTRY
from ..expression_translator import EdgeContext, translate_expression

# Talend matching mode -> V2 matching mode
_MATCHING_MODES: Dict[str, str] = {
    "UNIQUE_MATCH": "unique",
    "ALL_ROWS": "all",
    "FIRST_MATCH": "first",
    "LAST_MATCH": "last",
}

_MAIN_CONN_TYPES = {"FLOW", "MAIN", "LOOKUP"}
_DATA_CONN_TYPES = {"FLOW", "MAIN", "LOOKUP", "REJECT", "FILTER"}


@REGISTRY.register("tMap")
class TMapConverter(ComponentConverter):
    """Converts Talend tMap to V2 map component."""

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        node_data = self._find_node_data(node)
        if node_data is None:
            return ComponentResult(
                component={"id": node.component_id, "type": "map", "config": {}},
                warnings=[f"{node.component_id}: no <nodeData> found in tMap XML"],
            )

        # ---- Parse input tables ----
        input_tables = list(node_data.iter("inputTables"))
        if not input_tables:
            return ComponentResult(
                component={"id": node.component_id, "type": "map", "config": {}},
                warnings=[f"{node.component_id}: no inputTables in tMap"],
            )

        main_table = input_tables[0]
        main_edge = main_table.get("name", "")
        lookup_tables = input_tables[1:]

        # Build edge context
        lookup_edges = {lt.get("name", ""): lt.get("name", "") for lt in lookup_tables}
        edge_ctx = EdgeContext(main_edge=main_edge, lookup_edges=lookup_edges)

        # ---- Check for input filters (needs review) ----
        for it in input_tables:
            if it.get("activateExpressionFilter") == "true":
                filter_expr = it.get("expressionFilter", "")
                needs_review.append({
                    "component": node.component_id,
                    "issue": "input_table_filter",
                    "table": it.get("name", ""),
                    "expression": filter_expr,
                    "message": (
                        f"Input table '{it.get('name', '')}' has an expression filter "
                        f"that may need manual translation: {filter_expr}"
                    ),
                })

        # ---- Parse lookups ----
        lookups = self._parse_lookups(lookup_tables, main_edge)

        # ---- Parse variables ----
        variables = self._parse_variables(node_data, edge_ctx, needs_review, node.component_id)

        # ---- Parse outputs ----
        outputs = self._parse_outputs(node_data, edge_ctx, needs_review, node.component_id)

        # ---- Build flows ----
        flows = self._build_tmap_flows(node, connections, main_edge, lookup_edges, outputs)

        config: Dict[str, Any] = {
            "lookups": lookups,
            "variables": variables,
            "outputs": outputs,
        }

        return ComponentResult(
            component={
                "id": node.component_id,
                "type": "map",
                "config": config,
            },
            flows=flows,
            warnings=warnings,
            needs_review=needs_review,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_node_data(node: TalendNode) -> Element | None:
        """Find the <nodeData> element inside the raw_xml."""
        if node.raw_xml is None:
            return None
        # Direct child
        nd = node.raw_xml.find("nodeData")
        if nd is not None:
            return nd
        # Sometimes nested differently — search all descendants
        for elem in node.raw_xml.iter("nodeData"):
            return elem
        return None

    @staticmethod
    def _parse_lookups(
        lookup_tables: list[Element],
        main_edge: str,
    ) -> List[Dict[str, Any]]:
        """Parse lookup inputTables into V2 lookup config."""
        lookups: List[Dict[str, Any]] = []
        for lt in lookup_tables:
            name = lt.get("name", "")
            inner_join = lt.get("innerJoin", "false").lower() == "true"
            join_type = "inner" if inner_join else "left"
            matching_mode = _MATCHING_MODES.get(
                lt.get("matchingMode", "UNIQUE_MATCH"), "unique"
            )

            # Extract join keys: entries with an 'operator' attribute OR
            # entries whose expression references the main input table
            main_prefix = f"{main_edge}."
            keys: List[Dict[str, str]] = []
            for entry in lt.findall("mapperTableEntries"):
                expr = (entry.get("expression") or "").strip()
                operator = entry.get("operator")
                if operator or expr.startswith(main_prefix):
                    lookup_col = entry.get("name", "")
                    main_col = _strip_prefix(expr, main_edge)
                    keys.append({"main": main_col, "lookup": lookup_col})

            lookups.append({
                "name": name,
                "matching_mode": matching_mode,
                "join_type": join_type,
                "keys": keys,
            })
        return lookups

    @staticmethod
    def _parse_variables(
        node_data: Element,
        edge_ctx: EdgeContext,
        needs_review: List[Dict[str, Any]],
        component_id: str,
    ) -> List[Dict[str, str]]:
        """Parse varTables into V2 variable config."""
        variables: List[Dict[str, str]] = []
        for vt in node_data.findall("varTables"):
            for entry in vt.findall("mapperTableEntries"):
                name = entry.get("name", "")
                expr = entry.get("expression", "").strip()
                result = translate_expression(expr, edge_ctx)
                variables.append({
                    "name": name,
                    "expression": result.expression,
                })
                if result.needs_review:
                    needs_review.append({
                        "component": component_id,
                        "issue": "expression_needs_review",
                        "variable": name,
                        "expression": expr,
                        "reason": result.review_reason,
                    })
        return variables

    @staticmethod
    def _parse_outputs(
        node_data: Element,
        edge_ctx: EdgeContext,
        needs_review: List[Dict[str, Any]],
        component_id: str,
    ) -> List[Dict[str, Any]]:
        """Parse outputTables into V2 output config."""
        outputs: List[Dict[str, Any]] = []
        for ot in node_data.findall("outputTables"):
            name = ot.get("name", "")
            is_reject = ot.get("reject", "false").lower() == "true"

            columns: List[Dict[str, str]] = []
            for entry in ot.findall("mapperTableEntries"):
                col_name = entry.get("name", "")
                expr = entry.get("expression", "").strip()
                result = translate_expression(expr, edge_ctx)
                col_dict: Dict[str, str] = {
                    "name": col_name,
                    "expression": result.expression,
                }
                columns.append(col_dict)
                if result.needs_review:
                    needs_review.append({
                        "component": component_id,
                        "issue": "expression_needs_review",
                        "output": name,
                        "column": col_name,
                        "expression": expr,
                        "reason": result.review_reason,
                    })

            output_dict: Dict[str, Any] = {
                "name": name,
                "columns": columns,
            }

            if is_reject:
                output_dict["reject"] = True

            # Output filter
            if ot.get("activateExpressionFilter", "false").lower() == "true":
                filter_expr = ot.get("expressionFilter", "").strip()
                if filter_expr:
                    filter_result = translate_expression(filter_expr, edge_ctx)
                    output_dict["filter"] = filter_result.expression
                    if filter_result.needs_review:
                        needs_review.append({
                            "component": component_id,
                            "issue": "filter_needs_review",
                            "output": name,
                            "expression": filter_expr,
                            "reason": filter_result.review_reason,
                        })

            outputs.append(output_dict)
        return outputs

    @staticmethod
    def _build_tmap_flows(
        node: TalendNode,
        connections: list[TalendConnection],
        main_edge: str,
        lookup_edges: Dict[str, str],
        outputs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build flow dicts with tMap-specific input/output routing."""
        flows: List[Dict[str, Any]] = []

        # Build name sets for matching
        output_names = {o["name"] for o in outputs}
        reject_names = {o["name"] for o in outputs if o.get("reject")}

        # Incoming connections
        for conn in connections:
            if conn.target != node.component_id:
                continue
            if conn.connector_type not in _MAIN_CONN_TYPES:
                continue

            flow: Dict[str, Any] = {
                "name": conn.name,
                "source": conn.source,
                "target": conn.target,
            }

            # Match connection name to input table
            if conn.name == main_edge:
                flow["input"] = "main"
            elif conn.name in lookup_edges:
                flow["input"] = conn.name
            else:
                # Fallback: first incoming = main, rest = lookup by order
                flow["input"] = conn.name

            flows.append(flow)

        # Outgoing connections (only data flows, not triggers)
        for conn in connections:
            if conn.source != node.component_id:
                continue
            if conn.connector_type not in _DATA_CONN_TYPES:
                continue

            flow = {
                "name": conn.name,
                "source": conn.source,
                "target": conn.target,
            }

            if conn.connector_type == "REJECT" or conn.name in reject_names:
                flow["output"] = "reject"
            elif conn.name in output_names:
                flow["output"] = conn.name
            else:
                flow["output"] = conn.name

            flows.append(flow)

        return flows


def _strip_prefix(expr: str, prefix: str) -> str:
    """Strip 'prefix.' from the start of an expression, returning the column name.

    e.g. _strip_prefix('orders.product_id', 'orders') -> 'product_id'
    """
    expected = f"{prefix}."
    if expr.startswith(expected):
        return expr[len(expected):]
    return expr
