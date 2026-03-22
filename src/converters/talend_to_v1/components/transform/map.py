"""Converter for tMap -> Map — the most complex Talend component.

tMap uses ``nodeData`` XML containing ``MapperData`` to define:
- Input tables (main + lookups with join keys and join modes)
- Variable tables (intermediate computed expressions)
- Output tables (with column mappings, filters, reject logic)

All Java expressions are prefixed with ``{{java}}`` for engine routing.
"""
import logging
from typing import Any, Dict, List, Optional
from xml.etree.ElementTree import Element

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# XSI namespace used for type detection in nodeData
_XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"


def _java_expr(expression: str) -> str:
    """Prefix a non-empty expression with the ``{{java}}`` marker."""
    if expression:
        return f"{{{{java}}}}{expression}"
    return ""


def _attr_bool(element: Element, name: str, default: bool = False) -> bool:
    """Read an XML attribute as a boolean (Talend uses 'true'/'false' strings)."""
    return element.get(name, str(default).lower()).lower() == "true"


def _find_mapper_data(raw_xml: Optional[Element]) -> Optional[Element]:
    """Locate the ``nodeData`` element carrying MapperData inside a node."""
    if raw_xml is None:
        return None

    # Primary path: nodeData with xsi:type containing 'MapperData'
    for node_data in raw_xml.findall(".//nodeData"):
        if "MapperData" in node_data.get(_XSI_TYPE, ""):
            return node_data

    # Fallback: direct <MapperData> child
    mapper = raw_xml.find(".//MapperData")
    return mapper


def _parse_input_main(input_xml: Element) -> Dict[str, Any]:
    """Parse the MAIN input table element."""
    name = input_xml.get("name", "")
    activate_filter = _attr_bool(input_xml, "activateExpressionFilter")

    main_filter = ""
    if activate_filter:
        main_filter = input_xml.get("expressionFilter", "").strip()

    return {
        "name": name,
        "filter": _java_expr(main_filter),
        "activate_filter": activate_filter,
        "matching_mode": input_xml.get("matchingMode", "UNIQUE_MATCH"),
        "lookup_mode": input_xml.get("lookupMode", "LOAD_ONCE"),
    }


def _parse_lookup(lookup_xml: Element) -> Dict[str, Any]:
    """Parse a single LOOKUP input table element."""
    lookup_name = lookup_xml.get("name", "")

    # Join keys: mapperTableEntries with a non-empty expression attribute
    join_keys: List[Dict[str, str]] = []
    for col in lookup_xml.findall("./mapperTableEntries"):
        col_expression = col.get("expression", "").strip()
        if col_expression:
            join_keys.append({
                "lookup_column": col.get("name", ""),
                "expression": _java_expr(col_expression),
            })

    # Filter
    activate_filter = _attr_bool(lookup_xml, "activateExpressionFilter")
    lookup_filter = ""
    if activate_filter:
        lookup_filter = lookup_xml.get("expressionFilter", "").strip()
        if lookup_filter:
            lookup_filter = _java_expr(lookup_filter)

    # Join mode: innerJoin=true -> INNER_JOIN, otherwise LEFT_OUTER_JOIN
    join_mode = (
        "INNER_JOIN"
        if _attr_bool(lookup_xml, "innerJoin")
        else "LEFT_OUTER_JOIN"
    )

    return {
        "name": lookup_name,
        "matching_mode": lookup_xml.get("matchingMode", "UNIQUE_MATCH"),
        "lookup_mode": lookup_xml.get("lookupMode", "LOAD_ONCE"),
        "filter": lookup_filter,
        "activate_filter": activate_filter,
        "join_keys": join_keys,
        "join_mode": join_mode,
    }


def _parse_variables(mapper_data: Element) -> List[Dict[str, Any]]:
    """Parse variable tables from MapperData."""
    variables: List[Dict[str, Any]] = []
    for var_table in mapper_data.findall("./varTables"):
        for var_entry in var_table.findall("./mapperTableEntries"):
            var_name = var_entry.get("name", "")
            var_expression = var_entry.get("expression", "").strip()

            if var_name and var_expression:
                variables.append({
                    "name": var_name,
                    "expression": _java_expr(var_expression),
                    "type": var_entry.get("type", "id_String"),
                })
    return variables


def _parse_outputs(mapper_data: Element) -> List[Dict[str, Any]]:
    """Parse output tables from MapperData."""
    outputs: List[Dict[str, Any]] = []
    for output_xml in mapper_data.findall("./outputTables"):
        output_name = output_xml.get("name", "")
        is_reject = _attr_bool(output_xml, "reject")
        inner_join_reject = _attr_bool(output_xml, "rejectInnerJoin")

        # Filter
        activate_filter = _attr_bool(output_xml, "activateExpressionFilter")
        output_filter = ""
        if activate_filter:
            output_filter = output_xml.get("expressionFilter", "").strip()
            if output_filter:
                output_filter = _java_expr(output_filter)

        # Columns
        columns: List[Dict[str, Any]] = []
        for col in output_xml.findall("./mapperTableEntries"):
            col_name = col.get("name", "")
            col_expression = col.get("expression", "").strip()
            col_type = col.get("type", "id_String")
            col_nullable = _attr_bool(col, "nullable", default=True)

            columns.append({
                "name": col_name,
                "expression": _java_expr(col_expression),
                "type": col_type,
                "nullable": col_nullable,
            })

        outputs.append({
            "name": output_name,
            "is_reject": is_reject,
            "inner_join_reject": inner_join_reject,
            "filter": output_filter,
            "activate_filter": activate_filter,
            "columns": columns,
        })
    return outputs


@REGISTRY.register("tMap")
class MapConverter(ComponentConverter):
    """Convert a Talend tMap node to the v1 Map component."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        mapper_data = _find_mapper_data(node.raw_xml)
        if mapper_data is None:
            warnings.append("No MapperData found in tMap node — config will be empty")
            component = self._build_component_dict(
                node=node,
                type_name="Map",
                config={},
                schema={},
            )
            return ComponentResult(component=component, warnings=warnings)

        # ── Phase 1: Parse input tables ──────────────────────────────
        input_tables_xml = mapper_data.findall(".//inputTables")

        if not input_tables_xml:
            warnings.append("No inputTables found in MapperData")
            component = self._build_component_dict(
                node=node,
                type_name="Map",
                config={},
                schema={},
            )
            return ComponentResult(component=component, warnings=warnings)

        # First input is always MAIN
        main_config = _parse_input_main(input_tables_xml[0])

        # Remaining inputs are LOOKUPS
        lookups_config = [_parse_lookup(lt) for lt in input_tables_xml[1:]]

        # ── Phase 2: Parse variables ─────────────────────────────────
        variables_config = _parse_variables(mapper_data)

        # ── Phase 3: Parse outputs ───────────────────────────────────
        outputs_config = _parse_outputs(mapper_data)

        # ── Build config ─────────────────────────────────────────────
        config: Dict[str, Any] = {
            "inputs": {
                "main": main_config,
                "lookups": lookups_config,
            },
            "variables": variables_config,
            "outputs": outputs_config,
        }

        # ── DIE_ON_ERROR ─────────────────────────────────────────────
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", True)
        config["die_on_error"] = die_on_error

        component = self._build_component_dict(
            node=node,
            type_name="Map",
            config=config,
            schema={},
        )

        # Populate component.inputs and component.outputs for engine routing
        component["inputs"] = (
            [main_config["name"]]
            + [lk["name"] for lk in lookups_config]
        )
        component["outputs"] = [out["name"] for out in outputs_config]

        return ComponentResult(component=component, warnings=warnings)
