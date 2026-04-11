"""Converter for Talend tMap component.

Multi-flow data mapping with lookup joins, variable definitions, and expression-based column mappings.
Most complex component in the v1 converter suite.

Config mapping (9 flat params + nodeData structure + framework):
  DIE_ON_ERROR -> die_on_error (bool, hidden, default True)
  ROWS_BUFFER_SIZE -> rows_buffer_size (str, default "2000000")
  CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL -> change_hash_and_equals_for_bigdecimal (bool, default True)
  --- nodeData (MapperData XML) ---
  inputTables -> config["inputs"] (main + lookups with join keys, matching modes)
  varTables -> config["variables"] (variable definitions)
  outputTables -> config["outputs"] (output tables with column mappings, reject flags)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

MAP param (EXTERNAL type) is a visual editor reference -- not extracted.

Engine reads: config['inputs']['main'], config['inputs']['lookups'], config['variables'],
config['outputs'], config.get('die_on_error', True).
Per D-74: output shape MUST match engine expectations. Document changes as needs_review 'output_shape_change'.
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
        "size_state": input_xml.get("sizeState", ""),
        "persistent": _attr_bool(input_xml, "persistent"),
        "activate_condensed_tool": _attr_bool(input_xml, "activateCondensedTool"),
        "activate_global_map": _attr_bool(input_xml, "activateGlobalMap"),
    }


def _parse_lookup(lookup_xml: Element) -> Dict[str, Any]:
    """Parse a single LOOKUP input table element."""
    lookup_name = lookup_xml.get("name", "")

    # Join keys: entries with a non-empty expression OR operator attribute
    join_keys: List[Dict[str, Any]] = []
    for col in lookup_xml.findall("./mapperTableEntries"):
        col_expression = col.get("expression", "").strip()
        col_operator = col.get("operator", "").strip()
        if col_expression or col_operator:
            join_keys.append({
                "lookup_column": col.get("name", ""),
                "expression": _java_expr(col_expression),
                "type": col.get("type", "id_String"),
                "nullable": _attr_bool(col, "nullable", default=True),
                "operator": col_operator,
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
        "size_state": lookup_xml.get("sizeState", ""),
        "persistent": _attr_bool(lookup_xml, "persistent"),
        "activate_condensed_tool": _attr_bool(lookup_xml, "activateCondensedTool"),
        "activate_global_map": _attr_bool(lookup_xml, "activateGlobalMap"),
    }


def _parse_variables(
    mapper_data: Element,
) -> tuple[List[Dict[str, Any]], str, str]:
    """Parse variable tables from MapperData.

    Returns:
        Tuple of (variables_list, var_table_name, var_table_size_state).
        Table-level attributes are returned separately so they can be
        stored at the config root without nesting inside the flat list.
    """
    variables: List[Dict[str, Any]] = []
    var_table_name = ""
    var_table_size_state = ""

    for var_table in mapper_data.findall("./varTables"):
        # Table-level attributes (first varTable wins if multiple exist)
        if not var_table_name:
            var_table_name = var_table.get("name", "Var")
            var_table_size_state = var_table.get("sizeState", "")

        for var_entry in var_table.findall("./mapperTableEntries"):
            var_name = var_entry.get("name", "")
            var_expression = var_entry.get("expression", "").strip()

            if var_name and var_expression:
                variables.append({
                    "name": var_name,
                    "expression": _java_expr(var_expression),
                    "type": var_entry.get("type", "id_String"),
                    "nullable": _attr_bool(var_entry, "nullable", default=True),
                })
    return variables, var_table_name, var_table_size_state


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

            # Parse length/precision as int, defaulting to -1 (sentinel for "not set")
            raw_length = col.get("length", "-1")
            try:
                col_length = int(raw_length)
            except (ValueError, TypeError):
                col_length = -1

            raw_precision = col.get("precision", "-1")
            try:
                col_precision = int(raw_precision)
            except (ValueError, TypeError):
                col_precision = -1

            columns.append({
                "name": col_name,
                "expression": _java_expr(col_expression),
                "type": col_type,
                "nullable": col_nullable,
                "operator": col.get("operator", ""),
                "length": col_length,
                "precision": col_precision,
                "pattern": col.get("pattern", ""),
            })

        outputs.append({
            "name": output_name,
            "is_reject": is_reject,
            "inner_join_reject": inner_join_reject,
            "filter": output_filter,
            "activate_filter": activate_filter,
            "columns": columns,
            "size_state": output_xml.get("sizeState", ""),
            "catch_output_reject": _attr_bool(output_xml, "activateCondensedTool"),
            "activate_global_map": _attr_bool(output_xml, "activateGlobalMap"),
        })
    return outputs


@REGISTRY.register("tMap")
class MapConverter(ComponentConverter):
    """Convert Talend tMap to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        mapper_data = _find_mapper_data(node.raw_xml)
        if mapper_data is None:
            warnings.append("No MapperData found in tMap node -- config will be empty")
            component = self._build_component_dict(
                node=node,
                type_name="Map",
                config={},
                schema={},
            )
            return ComponentResult(component=component, warnings=warnings)

        # ---- Parse input tables ----
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

        # ---- Parse variables ----
        variables_config, var_table_name, var_table_size_state = _parse_variables(mapper_data)

        # ---- Parse outputs ----
        outputs_config = _parse_outputs(mapper_data)

        # ---- Build config ----
        config: Dict[str, Any] = {
            "inputs": {
                "main": main_config,
                "lookups": lookups_config,
            },
            "variables": variables_config,
            "outputs": outputs_config,
        }

        # ---- 1. Core parameters ----
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", True)
        config["rows_buffer_size"] = self._get_str(node, "ROWS_BUFFER_SIZE", "2000000")
        config["change_hash_and_equals_for_bigdecimal"] = self._get_bool(
            node, "CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL", True
        )

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema ----
        schema: Dict[str, Any] = {}  # tMap uses empty schema -- multi-flow config drives routing

        # ---- 7. Engine gap needs_review entries ----
        _engine_gap_keys = [
            ("rows_buffer_size", "Engine does not read 'rows_buffer_size' -- no disk buffering support"),
            ("change_hash_and_equals_for_bigdecimal", "Engine does not handle BigDecimal hash/equals behavior"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="Map",
            config=config,
            schema=schema,
        )

        # Populate component.inputs and component.outputs for engine routing
        component["inputs"] = (
            [main_config["name"]]
            + [lk["name"] for lk in lookups_config]
        )
        component["outputs"] = [out["name"] for out in outputs_config]

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
