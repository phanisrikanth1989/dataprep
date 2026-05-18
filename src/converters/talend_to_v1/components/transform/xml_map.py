"""Converter for Talend tXMLMap component.

XML-based data mapping with tree structures, connections, and expression links.
Second most complex component -- recursive XML tree parsing of nodeData.

Config mapping (2 flat params + nodeData structure + framework):
  DIE_ON_ERROR              -> die_on_error              (bool, hidden, default True)
  KEEP_ORDER_FOR_DOCUMENT   -> keep_order_for_document   (bool, default False)
  --- nodeData (XML tree structures) ---
  inputTrees   -> parsed into input tree definitions with recursive children
  outputTrees  -> parsed into output tree definitions
  connections  -> source-to-target expression links
  varTables    -> variable table definitions
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

MAP param (EXTERNAL) is visual editor reference -- not extracted.
CONNECTION_FORMAT: Verified phantom -- not in _java.xml, removed.

Engine reads ONLY: config.get("output_schema"), config.get("expressions"),
config.get("looping_element"). Everything else stored for fidelity.

IMPORTANT per D-76: NO lstrip() calls. Use str.removeprefix() for safe prefix removal.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from xml.etree.ElementTree import Element

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY
from ...type_mapping import convert_type

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_nested_children(element: Element) -> List[Dict[str, Any]]:
    """Recursively parse ``<children>`` elements from a tXMLMap tree node."""
    children: List[Dict[str, Any]] = []
    for child in element.findall("./children"):
        child_data: Dict[str, Any] = {
            "name": child.get("name", ""),
            "type": convert_type(child.get("type", "id_String")),
            "xpath": child.get("xpath", ""),
            "nodeType": child.get("nodeType", ""),
            "loop": child.get("loop", "").lower() == "true",
            "main": child.get("main", "").lower() == "true",
            "outgoingConnections": child.get("outgoingConnections", ""),
            "children": _parse_nested_children(child),
        }
        children.append(child_data)
    return children


def _parse_input_trees(node_data: Element) -> List[Dict[str, Any]]:
    """Parse all ``<inputTrees>`` from the nodeData element."""
    input_trees: List[Dict[str, Any]] = []
    for input_tree in node_data.findall("./inputTrees"):
        tree_data: Dict[str, Any] = {
            "name": input_tree.get("name", ""),
            "matchingMode": input_tree.get("matchingMode", "ALL_ROWS"),
            "lookupMode": input_tree.get("lookupMode", "LOAD_ONCE"),
            "lookup": input_tree.get("lookup", "false").lower() == "true",
            "activateGlobalMap": input_tree.get("activateGlobalMap", "false").lower() == "true",
            "nodes": [],
        }
        for tree_node in input_tree.findall("./nodes"):
            node_info: Dict[str, Any] = {
                "name": tree_node.get("name", ""),
                "expression": tree_node.get("expression", ""),
                "type": convert_type(tree_node.get("type", "id_Document")),
                "xpath": tree_node.get("xpath", ""),
                "children": _parse_nested_children(tree_node),
            }
            tree_data["nodes"].append(node_info)
        input_trees.append(tree_data)
    return input_trees


def _parse_output_trees(node_data: Element) -> List[Dict[str, Any]]:
    """Parse all ``<outputTrees>`` from the nodeData element."""
    output_trees: List[Dict[str, Any]] = []
    for output_tree in node_data.findall("./outputTrees"):
        tree_data: Dict[str, Any] = {
            "name": output_tree.get("name", ""),
            "expressionFilter": output_tree.get("expressionFilter", ""),
            "activateExpressionFilter": (
                output_tree.get("activateExpressionFilter", "false").lower() == "true"
            ),
            "allInOne": output_tree.get("allInOne", "false").lower() == "true",
            "nodes": [],
        }
        for tree_node in output_tree.findall("./nodes"):
            node_info: Dict[str, Any] = {
                "name": tree_node.get("name", ""),
                "expression": tree_node.get("expression", ""),
                "type": convert_type(tree_node.get("type", "id_String")),
                "xpath": tree_node.get("xpath", ""),
                "children": _parse_nested_children(tree_node),
            }
            tree_data["nodes"].append(node_info)
        output_trees.append(tree_data)
    return output_trees


def _parse_connections(node_data: Element) -> List[Dict[str, str]]:
    """Parse ``<connections>`` elements from nodeData."""
    connections: List[Dict[str, str]] = []
    for conn in node_data.findall("./connections"):
        connections.append({
            "source": conn.get("source", ""),
            "target": conn.get("target", ""),
            "sourceExpression": conn.get("sourceExpression", ""),
        })
    return connections


def _parse_var_tables(node_data: Element) -> List[Dict[str, Any]]:
    """Parse ``<varTables>`` from the nodeData element for fidelity."""
    var_tables: List[Dict[str, Any]] = []
    for var_table in node_data.findall("./varTables"):
        var_tables.append({
            "name": var_table.get("name", ""),
            "minimized": var_table.get("minimized", "false").lower() == "true",
        })
    return var_tables


def _build_input_tree_node_map(
    input_trees: List[Dict[str, Any]],
) -> Dict[str, Tuple[str, str, Dict[str, Any]]]:
    """Build a path-indexed map of all nodes in the input trees.

    Keys are paths like ``inputTrees.0/@nodes.0/@children.1`` which mirror the
    connection source/target references used by Talend.

    Returns:
        Mapping from path -> (name, nodeType, node_dict).
    """
    node_map: Dict[str, Tuple[str, str, Dict[str, Any]]] = {}

    def _walk(children: List[Dict[str, Any]], prefix: str) -> None:
        for idx, child in enumerate(children):
            child_path = f"{prefix}/@children.{idx}"
            name = child.get("name", "")
            node_type = child.get("nodeType", "")
            node_map[child_path] = (name, node_type, child)
            _walk(child.get("children", []), child_path)

    for tree_idx, tree in enumerate(input_trees):
        for node_idx, tree_node in enumerate(tree.get("nodes", [])):
            root_path = f"inputTrees.{tree_idx}/@nodes.{node_idx}"
            name = tree_node.get("name", "")
            node_type = tree_node.get("type", "")
            node_map[root_path] = (name, node_type, tree_node)
            _walk(tree_node.get("children", []), root_path)

    return node_map


def _build_expressions(
    connections: List[Dict[str, str]],
    input_tree_node_map: Dict[str, Tuple[str, str, Dict[str, Any]]],
    output_col_map: Dict[int, str],
) -> Dict[str, str]:
    """Build a mapping of output column name -> XPath from connection data."""
    expressions: Dict[str, str] = {}

    for conn in connections:
        target = conn.get("target", "")
        source = conn.get("source", "")

        # Extract output column index from the target path
        m = re.search(r"outputTrees\.0/@nodes\.(\d+)", target)
        if not m:
            continue

        out_idx = int(m.group(1))
        out_col = output_col_map.get(out_idx)
        if not out_col:
            continue

        # Walk the source path to build an XPath expression
        path_parts = re.findall(r"(@nodes\.\d+|@children\.\d+)", source)
        full_path = "inputTrees.0"
        xpath_parts: List[str] = []
        node_types: List[str] = []

        for part in path_parts:
            full_path += f"/{part}"
            node_info = input_tree_node_map.get(full_path)
            if node_info:
                name, node_type, _ = node_info
                if name and name not in ["newColumn"]:
                    xpath_parts.append(name)
                    node_types.append(node_type)

        # Build the final XPath string
        if xpath_parts:
            if node_types and node_types[-1] == "ATTRIBUT":
                attribute_name = xpath_parts.pop() if xpath_parts else ""
                if xpath_parts:
                    xpath = "./" + "/".join(xpath_parts) + "/@" + attribute_name
                else:
                    xpath = "./@" + attribute_name
            else:
                xpath = "./" + "/".join(xpath_parts) if xpath_parts else "."
        else:
            xpath = "."

        expressions[out_col] = xpath
        logger.debug("Mapped connection: %s -> %s (from %s -> %s)", out_col, xpath, source, target)

    return expressions


def _detect_looping_element(
    raw_xml: Optional[Element],
    input_tree_node_map: Dict[str, Tuple[str, str, Dict[str, Any]]],
) -> str:
    """Detect the looping element from children with loop=true.

    Falls back to:
    1. ``<children loop="true">`` anywhere in raw_xml
    2. ``elementParameter`` named LOOPING_ELEMENT
    3. The deepest node in the input tree
    """
    looping_element: Optional[str] = None

    # Strategy 1: find children with loop="true" in the raw XML
    if raw_xml is not None:
        for child in raw_xml.iter("children"):
            if child.get("loop", "").lower() == "true" and child.get("name"):
                looping_element = child.get("name")
                break

    # Strategy 2: check elementParameter named LOOPING_ELEMENT
    if not looping_element and raw_xml is not None:
        for param in raw_xml.findall("elementParameter"):
            if param.get("name", "").upper() == "LOOPING_ELEMENT":
                looping_element = (param.get("value") or "").strip()
                break

    # Normalize to plain string
    if isinstance(looping_element, (list, tuple, dict)):
        if isinstance(looping_element, dict):
            looping_element = str(next(iter(looping_element.values()), ""))
        else:
            looping_element = str(looping_element[0])
    looping_element = str(looping_element or "").strip()

    logger.debug("Normalized looping_element: '%s'", looping_element)

    # Strategy 3: auto-detect from deepest node in input tree
    if not looping_element and input_tree_node_map:
        max_depth = 0
        for path, (name, _node_type, _node_dict) in input_tree_node_map.items():
            depth = path.count("/")
            if depth > max_depth:
                max_depth = depth
                looping_element = name

    return looping_element or ""


def _rewrite_expressions_for_loop(
    expressions: Dict[str, str],
    looping_element: str,
) -> Dict[str, str]:
    """Rewrite XPath expressions relative to the looping element.

    Fields inside the loop become relative paths (e.g. ``./city``).
    Fields outside the loop use ``../`` relative traversal whenever the
    loop element's full path can be inferred from the inside-loop expressions.
    This avoids ``ancestor::`` notation which breaks when the XML document root
    is the loop-query matched element (e.g. tFileInputXML serialises only the
    matched ``<employee>`` subtree, making ``ancestor::company`` invalid).

    Fallback: if no inside-loop expression exists the loop element path cannot
    be inferred and ``ancestor::`` notation is used as before.

    Per D-76: uses str.removeprefix() instead of lstrip() for safe prefix removal.
    """
    if not looping_element:
        return expressions

    loop_name = looping_element.strip()
    logger.debug("Rewriting XPaths relative to looping element '%s'", loop_name)

    def _norm_parts(xpath: str) -> List[str]:
        s = xpath.strip().removeprefix("./").removeprefix("/")
        return [p.strip("/") for p in s.split("/") if p.strip("/")]

    # Infer the full path to the loop element from any inside-loop expression.
    # E.g. xpath "./company/employee/addresses/address/type" with loop_name
    # "address" -> loop_full_parts = ["company", "employee", "addresses", "address"].
    loop_full_parts: List[str] = []
    for xpath in expressions.values():
        if not xpath:
            continue
        parts = _norm_parts(xpath)
        for i, p in enumerate(parts):
            if p.lower() == loop_name.lower():
                loop_full_parts = parts[: i + 1]
                break
        if loop_full_parts:
            break

    rewritten: Dict[str, str] = {}
    for out_col, xpath in expressions.items():
        if not xpath:
            rewritten[out_col] = xpath
            continue

        field_parts = _norm_parts(xpath)
        in_loop = any(p.lower() == loop_name.lower() for p in field_parts)

        if in_loop:
            loop_index = next(
                (i for i, p in enumerate(field_parts) if p.lower() == loop_name.lower()),
                None,
            )
            if loop_index is not None:
                rel_parts = field_parts[loop_index + 1:]
                if rel_parts:
                    new_xpath = "./" + "/".join(rel_parts)
                else:
                    new_xpath = f"./{loop_name}"
            else:
                new_xpath = "./" + "/".join(field_parts)
            logger.debug("Field %s inside loop: %s", out_col, new_xpath)
        elif loop_full_parts:
            # Compute the relative path: find the common prefix between the
            # loop element's path and the field path, then navigate up with ../
            # and down to the target.  This works regardless of the document root.
            common_len = 0
            for lp, fp in zip(loop_full_parts, field_parts):
                if lp.lower() == fp.lower():
                    common_len += 1
                else:
                    break
            levels_up = len(loop_full_parts) - common_len
            down_parts = field_parts[common_len:]
            rel_parts = [".."] * levels_up + down_parts
            new_xpath = "./" + "/".join(rel_parts) if rel_parts else "."
            logger.debug("Field %s outside loop (relative): %s", out_col, new_xpath)
        else:
            # Fallback: no inside-loop expression to infer the loop path from.
            new_xpath = "./ancestor::" + "/".join(field_parts)
            logger.debug("Field %s outside loop (ancestor fallback): %s", out_col, new_xpath)

        rewritten[out_col] = new_xpath

    return rewritten


def _parse_output_schema_from_xml(
    raw_xml: Optional[Element],
) -> List[Dict[str, Any]]:
    """Parse the output schema from ``<metadata connector="FLOW">`` in raw XML."""
    output_schema: List[Dict[str, Any]] = []
    if raw_xml is None:
        return output_schema

    for metadata_node in raw_xml.findall('./metadata[@connector="FLOW"]'):
        for column in metadata_node.findall("./column"):
            output_schema.append({
                "name": column.get("name", ""),
                "type": convert_type(column.get("type", "id_String")),
                "nullable": column.get("nullable", "true").lower() == "true",
                "key": column.get("key", "false").lower() == "true",
                "length": int(column.get("length", -1)),
                "precision": int(column.get("precision", -1)),
            })
    return output_schema


# ---------------------------------------------------------------------------
# Converter
# ---------------------------------------------------------------------------


@REGISTRY.register("tXMLMap")
class XMLMapConverter(ComponentConverter):
    """Convert a Talend tXMLMap node into a v1 XMLMap component.

    Unlike simpler converters, tXMLMap requires direct access to the raw XML
    ``<node>`` element because the tree mapping configuration is stored in a
    ``<nodeData>`` child that is not surfaced through the flat params dict.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Basic parameters from the params dict
        # ------------------------------------------------------------------
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", default=True)
        keep_order_for_document = self._get_bool(node, "KEEP_ORDER_FOR_DOCUMENT", default=False)

        # Framework parameters
        tstatcatcher_stats = self._get_bool(node, "TSTATCATCHER_STATS", False)
        label = self._get_str(node, "LABEL")

        # ------------------------------------------------------------------
        # raw_xml guard
        # ------------------------------------------------------------------
        raw_xml = node.raw_xml
        if raw_xml is None:
            warnings.append(
                "raw_xml is None -- cannot parse nodeData; "
                "input_trees, output_trees, connections will be empty"
            )

        # ------------------------------------------------------------------
        # Parse nodeData for trees and connections
        # ------------------------------------------------------------------
        node_data: Optional[Element] = (
            raw_xml.find("./nodeData") if raw_xml is not None else None
        )

        if node_data is not None:
            input_trees = _parse_input_trees(node_data)
            output_trees = _parse_output_trees(node_data)
            xml_connections = _parse_connections(node_data)
            var_tables = _parse_var_tables(node_data)
        else:
            input_trees = []
            output_trees = []
            xml_connections = []
            var_tables = []
            if raw_xml is not None:
                warnings.append(
                    "nodeData element not found in raw_xml"
                )

        # ------------------------------------------------------------------
        # Output schema from FLOW metadata
        # ------------------------------------------------------------------
        output_schema = _parse_output_schema_from_xml(raw_xml)

        # ------------------------------------------------------------------
        # Expression filter from the first output tree
        # ------------------------------------------------------------------
        expression_filter: Optional[str] = None
        activate_expression_filter = False
        if output_trees:
            first_tree = output_trees[0]
            expression_filter = first_tree.get("expressionFilter", "")
            activate_expression_filter = first_tree.get(
                "activateExpressionFilter", False
            )
            # Prefix with {{java}} for engine routing (consistent with map.py)
            if activate_expression_filter and expression_filter:
                expression_filter = f"{{{{java}}}}{expression_filter}"

        # ------------------------------------------------------------------
        # Build expressions from connections
        # ------------------------------------------------------------------
        input_tree_node_map = _build_input_tree_node_map(input_trees)
        output_col_map = {i: col["name"] for i, col in enumerate(output_schema)}

        expressions = _build_expressions(
            xml_connections, input_tree_node_map, output_col_map
        )

        # ------------------------------------------------------------------
        # Detect looping element
        # ------------------------------------------------------------------
        looping_element = _detect_looping_element(raw_xml, input_tree_node_map)

        # ------------------------------------------------------------------
        # XPath rewriting based on looping element
        # ------------------------------------------------------------------
        expressions = _rewrite_expressions_for_loop(expressions, looping_element)
        logger.debug("Final expressions: %s", expressions)

        # ------------------------------------------------------------------
        # Build config (snake_case keys per D-38)
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            # Flat params
            "die_on_error": die_on_error,
            "keep_order_for_document": keep_order_for_document,
            # nodeData tree structures (snake_case per D-38)
            "input_trees": input_trees,
            "output_trees": output_trees,
            "connections": xml_connections,
            "var_tables": var_tables,
            # Derived from tree structures -- engine reads these 3
            "output_schema": output_schema,
            "expressions": expressions,
            "looping_element": looping_element,
            # Expression filter from first output tree
            "expression_filter": expression_filter,
            "activate_expression_filter": activate_expression_filter,
            # Framework parameters
            "tstatcatcher_stats": tstatcatcher_stats,
            "label": label,
        }

        # ----------------------------------------------------------------
        # Engine gap needs_review entries (per D-24/D-71)
        # ----------------------------------------------------------------
        needs_review: List[Dict[str, Any]] = []

        # Engine only reads: looping_element, output_schema, expressions
        # Everything else stored in config is an engine gap
        _engine_gap_keys = [
            ("die_on_error", "errors are silently swallowed regardless of setting"),
            ("keep_order_for_document", "document ordering is not enforced by engine"),
            ("input_trees", "input tree metadata stored but not used by engine"),
            ("output_trees", "output tree metadata stored but not used by engine"),
            ("connections", "connection metadata stored but not used by engine"),
            ("var_tables", "variable tables not supported by engine"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # Output shape change entries per D-74
        _output_shape_entries = [
            ("allInOne", "allInOne output mode not supported -- engine outputs flat rows only"),
            ("lookup", "lookup/join input trees not supported by engine"),
        ]
        for key, detail in _output_shape_entries:
            needs_review.append({
                "issue": f"Output shape affected: '{key}' -- {detail}",
                "component": node.component_id,
                "severity": "output_shape_change",
            })

        # ---- D-E1 conditional needs_review (Phase 12 lock-in) ----
        # These are emitted ONLY when the specific sub-feature flag is active in
        # this Talend node. The engine logs a warning at runtime and ignores the
        # sub-feature (warn-and-ignore contract). See 12-01-AUDIT.md D-E1 table.

        has_lookup = any(
            tree.get("lookup", False) for tree in input_trees
        )
        if has_lookup:
            needs_review.append({
                "feature": "lookup_join",
                "reason": (
                    "tXMLMap lookup/join (LOOKUP input trees) is not implemented by the "
                    "Phase 12 engine. The engine logs a warning and ignores the lookup. "
                    "Tracked for Phase 12.1."
                ),
                "phase": "12",
                "component": node.component_id,
                "severity": "output_shape_change",
            })

        has_all_in_one = any(
            tree.get("allInOne", False) for tree in output_trees
        )
        if has_all_in_one:
            needs_review.append({
                "feature": "all_in_one_document_output",
                "reason": (
                    "tXMLMap Document (allInOne) output mode is not implemented by the "
                    "Phase 12 engine. The engine logs a warning and falls back to per-row "
                    "emission. Tracked for Phase 12.1."
                ),
                "phase": "12",
                "component": node.component_id,
                "severity": "output_shape_change",
            })

        # ------------------------------------------------------------------
        # Schema
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)
        schema: Dict[str, Any] = {
            "input": schema_cols,
            "output": output_schema if output_schema else schema_cols,
        }

        component = self._build_component_dict(
            node=node,
            type_name="XMLMap",
            config=config,
            schema=schema,
        )

        return ComponentResult(component=component, warnings=warnings, needs_review=needs_review)
