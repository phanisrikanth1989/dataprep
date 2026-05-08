"""
XMLMap - XML mapping and transformation component with namespace handling.

Talend equivalent: XMLMap (standardized from tXMLMap)

This component processes XML data using XPath expressions to extract and transform data.
Supports namespace handling, looping elements, and expression-based field mapping.

Phase 12-05 audit fixes applied:
  BUG-XMP-003 (P0): Per-row loop replaces iloc[0,0] -- all input rows processed
  BUG-XMP-004 (P1): self.id no longer overwritten mid-_process
  BUG-XMP-006 (P1): Ancestor-fallback broadened search corrected
  BUG-XMP-014 (P1): split_steps preserves XPath predicates (bracket-balanced)
  ENG-XMP-003 (P1): REJECT flow added -- failed rows route to reject_df
  ENG-XMP-006 (P1): die_on_error honored at per-row error sites
  STD-XMP-001 (P1): All bare-print calls replaced with logger
  SEC-XMP-001 (P2): Parser construction delegated to _xml_io.secure_xml_parser
  BUG-XMP-015 (P2): lstrip('/') replaced with removeprefix('/') (Pitfall P-7)
  D-E1: Conditional warn-and-ignore for expression_filter/lookup/allInOne
  D-E2: Zero Java bridge imports (contract maintained per plan 12-05)
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from lxml import etree

from ..file import _xml_io
from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, DataValidationError

logger = logging.getLogger(__name__)

# Class constants
AXES = ("ancestor", "descendant", "self", "parent", "child", "following", "preceding")
DEFAULT_NAMESPACE_PREFIX = "ns0"
DEFAULT_LOOPING_ELEMENT = ""

# Error codes for REJECT output (S-3 pattern)
_ERR_NO_XML = "NO_XML"
_ERR_PARSE = "PARSE_ERROR"
_ERR_EVAL = "EVAL_ERROR"

# --------------------------------
# Helpers: namespaces + XPath
# --------------------------------

def normalize_nsmap(root: etree._Element) -> Dict[str, str]:
    """
    Normalize XML namespace map by handling default namespaces.

    Args:
        root: Root XML element

    Returns:
        Dictionary mapping namespace prefixes to URIs
    """
    nsmap = dict(root.nsmap or {})
    if None in nsmap:
        nsmap[DEFAULT_NAMESPACE_PREFIX] = nsmap.pop(None)
    nsmap = {k: v for k, v in nsmap.items() if k is not None}
    return nsmap


def split_steps(expr: str) -> List[str]:
    """
    Split XPath expression into individual steps, preserving bracket-delimited
    predicates (BUG-XMP-014 fix).

    The original implementation split on every '/' character which destroyed
    XPath predicates containing '/' (e.g. /a/b[@id='x']/c). This
    implementation walks the string character by character, tracking bracket
    depth so that '/' inside [...] is never treated as a segment boundary.

    Args:
        expr: XPath expression to split

    Returns:
        List of XPath steps (predicates intact)
    """
    expr = expr.strip()
    segments: List[str] = []
    buf: List[str] = []
    depth = 0
    i = 0
    n = len(expr)

    while i < n:
        ch = expr[i]

        # Track bracket depth -- do NOT split inside [...]
        if ch == "[":
            depth += 1
            buf.append(ch)
            i += 1
            continue

        if ch == "]":
            depth = max(depth - 1, 0)
            buf.append(ch)
            i += 1
            continue

        # Inside a predicate: consume literally
        if depth > 0:
            buf.append(ch)
            i += 1
            continue

        # Double-slash at depth 0: flush + emit '//' token
        if ch == "/" and i + 1 < n and expr[i + 1] == "/":
            if buf:
                segments.append("".join(buf))
                buf = []
            segments.append("//")
            i += 2
            continue

        # Single slash at depth 0: flush current segment
        if ch == "/":
            if buf:
                segments.append("".join(buf))
                buf = []
            i += 1
            continue

        # Axis shorthand (e.g. ancestor::): keep together with the node test
        if ch.isalpha() and depth == 0:
            j = i
            while j < n and (expr[j].isalnum() or expr[j] in ("_", "-")):
                j += 1
            if j + 1 < n and expr[j:j + 2] == "::":
                axis = expr[i:j]
                buf.append(f"{axis}::")
                i = j + 2
                k = i
                while k < n and (expr[k].isalnum() or expr[k] in ("_", "-")):
                    k += 1
                if k > i:
                    buf.append(expr[i:k])
                    i = k
                if buf:
                    segments.append("".join(buf))
                    buf = []
                continue

        buf.append(ch)
        i += 1

    if buf:
        segments.append("".join(buf))

    return [s for s in segments if s != ""]


def qualify_step(step: str, ns_prefix: str) -> str:
    """
    Qualify XPath step with namespace prefix if needed.

    Args:
        step: Individual XPath step
        ns_prefix: Namespace prefix to apply

    Returns:
        Qualified XPath step
    """
    s = step.strip()
    if not s:
        return s

    for ax in AXES:
        if s.startswith(ax + "::"):
            rest = s[len(ax) + 2:]
            if rest.startswith(ns_prefix + ":") or ":" in rest:
                return s
            if rest and rest[0] not in ("@", "*") and not rest.endswith("()"):
                if ns_prefix:
                    return f"{ax}::{ns_prefix}:{rest}"
                else:
                    return f"{ax}::{rest}"
            return s

    if s in (".", "..", "//"):
        return s
    if s.startswith("@") or s == "*" or "(" in s:
        return s
    if ":" in s:
        return s

    return f"{ns_prefix}:{s}"


def qualify_xpath(expr: str, ns_prefix: str) -> str:
    """
    Qualify complete XPath expression with namespace prefix.

    Args:
        expr: XPath expression to qualify
        ns_prefix: Namespace prefix to apply

    Returns:
        Fully qualified XPath expression
    """
    expr = expr.strip()
    if not expr:
        return expr

    steps = split_steps(expr)
    qualified: List[str] = []

    def glue(acc: List[str], nxt: str) -> List[str]:
        if not acc:
            acc.append(nxt)
            return acc
        if nxt == "//":
            acc.append("//")
            return acc
        if acc[-1] == "//":
            acc.append(nxt)
        else:
            acc.append("/")
            acc.append(nxt)
        return acc

    for step in steps:
        q = qualify_step(step, ns_prefix)
        qualified = glue(qualified, q)

    qexpr = "".join(qualified)
    qexpr = qexpr.replace("/ //", "//").replace("// /", "//")
    qexpr = qexpr.replace(f"{ns_prefix}:{ns_prefix}:", f"{ns_prefix}:")
    return qexpr


def choose_context(expr: str, loop_node: etree._Element, root: etree._Element) -> etree._Element:
    """
    Choose appropriate context element (root or loop node) for XPath evaluation.

    Args:
        expr: XPath expression to evaluate
        loop_node: Current loop context node
        root: Root XML element

    Returns:
        Appropriate context element for evaluation
    """
    e = expr.strip()

    # Case 1: Absolute/global expressions -> use ROOT
    if (
        e.startswith("/") or e.startswith("//") or
        e.startswith("ancestor::") or e.startswith("descendant::")
    ):
        logger.debug("choose_context -> ROOT (expr='%s')", expr)
        return root

    # Case 2: Relative expressions -> stay in loop context
    if (
        e.startswith("./") or e.startswith(".//") or
        e.startswith("./descendant::")
    ):
        # Handle relative ancestors smartly
        if e.startswith("./ancestor::"):
            parent = loop_node.getparent()
            logger.debug("choose_context parent -> '%s'", parent)
            # Only fall back to ROOT if no parent/ancestor exists
            if parent is None:
                logger.debug("choose_context -> ROOT (no parent, expr='%s')", expr)
                return root
            else:
                logger.debug("choose_context -> LOOP_NODE (expr='%s')", expr)
                return loop_node

        logger.debug("choose_context -> LOOP_NODE (expr='%s')", expr)
        return loop_node

    # Case 3: Default fallback -> loop context
    logger.debug("choose_context -> LOOP_NODE (expr='%s')", expr)
    return loop_node


def extract_value(node_or_nodes: Any) -> str:
    """
    Extract string value from XPath result nodes or values.

    Args:
        node_or_nodes: XPath result (element, list of elements, or value)

    Returns:
        Extracted string value
    """
    if isinstance(node_or_nodes, (str, int, float)):
        return str(node_or_nodes)
    if not node_or_nodes:
        return ""

    first = node_or_nodes[0]
    if isinstance(first, etree._Element):
        txt = (first.text or "").strip()
        if txt:
            return txt
        if first.attrib:
            return " ".join(f"{k}={v}" for k, v in first.attrib.items())
        return ""
    return str(first)


def _broaden_ancestor_if_empty(
    ctx: etree._Element, expr_q: str, nsmap: Dict[str, str]
) -> Any:
    """
    Broaden ancestor search if initial XPath evaluation returns empty results.

    BUG-XMP-006 fix: the original code used lstrip('/') which would also strip
    leading characters that happen to be '/' -- not just a single leading '/'.
    The broadened path is now built with removeprefix('/') (Pitfall P-7 fix /
    BUG-XMP-015) to ensure only a single leading '/' is stripped.

    Args:
        ctx: Context element for evaluation
        expr_q: Qualified XPath expression
        nsmap: Namespace mapping

    Returns:
        XPath evaluation result or None
    """
    try:
        res = ctx.xpath(expr_q, namespaces=nsmap)
    except Exception:
        return None  # Let caller handle

    if res:  # already found something
        return res

    # Only for the pattern starting with './ancestor::'
    if not expr_q.startswith("./ancestor::"):
        return res

    # BUG-XMP-015 fix: use removeprefix instead of lstrip (Pitfall P-7)
    tail = expr_q[len("./ancestor::"):]
    # removeprefix removes exactly one leading '/' if present; lstrip would
    # strip ALL leading slashes or any matching character from a string arg.
    broadened = "./ancestor::*//" + tail.removeprefix("/")
    try:
        res2 = ctx.xpath(broadened, namespaces=nsmap)
        return res2
    except Exception:
        return res  # fallback to original empty


# --------------------------------
# Component implementation
# --------------------------------

@REGISTRY.register("XMLMap", "tXMLMap")
class XMLMap(BaseComponent):
    """
    Performs XML mapping and transformation with advanced namespace handling.
    Equivalent to Talend's tXMLMap component.

    Configuration:
        looping_element (str): XPath expression for loop element. Default: ""
        output_schema (List[Dict]): Output column definitions. Required.
        expressions (Dict[str, str]): Column name to XPath expression mapping. Required.
        die_on_error (bool): Raise on per-row error vs route to REJECT. Default: True.
        keep_order_for_document (bool): Preserve input row order. Default: False.
        activate_expression_filter (bool): D-E1 -- warn and ignore. Default: False.
        connections (list): D-E1 -- inspected for LOOKUP flag, warn and ignore.
        output_trees (list): D-E1 -- inspected for allInOne flag, warn and ignore.

    Inputs:
        main: Input DataFrame with XML data (first column contains XML string)

    Outputs:
        main: Transformed DataFrame with extracted XML data
        reject: Rows that failed XML parse or evaluation

    Statistics:
        NB_LINE: Total input rows processed
        NB_LINE_OK: Successfully processed rows
        NB_LINE_REJECT: Rejected rows (parse/eval error)
    """

    # Class constants
    DEFAULT_COMPONENT_ID = "XMLMap"

    # Error codes (S-3 pattern, consistent with ExtractXMLField)
    _ERR_NO_XML = _ERR_NO_XML
    _ERR_PARSE = _ERR_PARSE
    _ERR_EVAL = _ERR_EVAL

    def _validate_config(self) -> None:
        """
        Validate component configuration (Rule 12: presence/type checks only).
        """
        config = self.config

        # output_schema or schema.output must be present
        output_schema = config.get("output_schema", []) or config.get("schema", {}).get("output", [])
        if not isinstance(output_schema, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'output_schema' must be a list"
            )

        # expressions must be a dict if present
        expressions = config.get("expressions", {})
        if not isinstance(expressions, dict):
            raise ConfigurationError(
                f"[{self.id}] Config 'expressions' must be a dictionary"
            )

        # looping_element must be a string if present
        looping_element = config.get("looping_element", "")
        if looping_element is not None and not isinstance(looping_element, str):
            raise ConfigurationError(
                f"[{self.id}] Config 'looping_element' must be a string"
            )

        # die_on_error must be a bool if present
        die_on_error = config.get("die_on_error", True)
        if not isinstance(die_on_error, bool):
            raise ConfigurationError(
                f"[{self.id}] Config 'die_on_error' must be a boolean"
            )

    # ------------------------------------------------------------------
    # D-E1 sub-feature detection helpers
    # ------------------------------------------------------------------

    def _has_lookup_connection(self) -> bool:
        """Return True when any connection entry has connector_name=='LOOKUP'."""
        connections = self.config.get("connections", []) or []
        for conn in connections:
            if isinstance(conn, dict):
                if conn.get("connector_name", "") == "LOOKUP":
                    return True
                # Also check the 'lookup' flag on input tree metadata
                if conn.get("lookup", False):
                    return True
        # Check input_trees for lookup=True flag
        input_trees = self.config.get("input_trees", []) or []
        for tree in input_trees:
            if isinstance(tree, dict) and tree.get("lookup", False):
                return True
        return False

    def _has_all_in_one_output(self) -> bool:
        """Return True when any output_tree has allInOne=True."""
        output_trees = self.config.get("output_trees", []) or []
        for tree in output_trees:
            if isinstance(tree, dict):
                val = tree.get("allInOne", False)
                if val in (True, "true", "True"):
                    return True
        return False

    # ------------------------------------------------------------------
    # Expression cleaning helpers
    # ------------------------------------------------------------------

    def _clean_expression(self, raw_expr: str) -> str:
        """
        Clean up malformed Talend expressions from JSON configuration.

        Handles various malformed expression patterns:
        - "./employee:/employees/employee/id]" -> "./id"
        - "[row1.employee:/employees/employee/name]" -> "./name"
        - "row1.field" -> "./field"

        Args:
            raw_expr: Raw expression string from JSON configuration

        Returns:
            Cleaned XPath expression suitable for XML processing
        """
        if not raw_expr or not isinstance(raw_expr, str):
            return ""

        cleaned = raw_expr.strip()

        # Remove leading/trailing brackets like [row1.employee:/employees/employee/id]
        if cleaned.startswith("[") and cleaned.endswith("]"):
            cleaned = cleaned[1:-1]

        # Handle complex malformed expressions like "./employee:/employees/employee/id"
        if ":" in cleaned and "/" in cleaned:
            # Extract field name from the path (last part after /)
            if "/" in cleaned:
                field_name = cleaned.split("/")[-1]
                # Remove any trailing brackets
                field_name = field_name.rstrip("]")
                return f"./{field_name}"

        # Handle dot notation like "row1.field_name"
        elif "." in cleaned and not cleaned.startswith("./"):
            parts = cleaned.split(".")
            if len(parts) >= 2:
                field_name = parts[-1]  # Take the last part (field name)
                # Remove any trailing brackets
                field_name = field_name.rstrip("]")
                return f"./{field_name}"

        # Handle already clean expressions starting with "./"
        elif cleaned.startswith("./"):
            # Remove any trailing brackets
            cleaned = cleaned.rstrip("]")
            return cleaned

        # Default: assume it's a direct field reference
        else:
            # Remove any trailing brackets
            cleaned = cleaned.rstrip("]")
            return f"./{cleaned}"

    def _clean_looping_element(self, raw_looping_element: str, root: etree._Element) -> str:
        """
        Clean up malformed looping element paths from JSON configuration.

        Analyzes the actual XML structure to determine the correct looping element path.
        Handles cases like "employees/employee" when the XML structure shows that
        "employee" is the repeating element under the root "employees".

        Args:
            raw_looping_element: Raw looping element string from JSON
            root: Parsed XML root element for structure analysis

        Returns:
            Cleaned looping element path suitable for XPath evaluation
        """
        if not raw_looping_element or not isinstance(raw_looping_element, str):
            return ""

        cleaned = raw_looping_element.strip()

        # Remove any brackets or quotes
        cleaned = cleaned.strip('[]"\'')

        # Handle common malformed patterns
        # Case 1: "employees/employee" when employees is the root
        if "/" in cleaned:
            parts = cleaned.split("/")
            if len(parts) == 2:
                root_name = parts[0]
                element_name = parts[1]

                # Check if the first part matches the root element name
                if root.tag == root_name or root.tag.endswith("}" + root_name):
                    # The first part is the root, so we only need the repeating element
                    return element_name
                else:
                    # Keep the full path if root doesn't match
                    return cleaned

        # Case 2: Already clean element name
        return cleaned

    # ------------------------------------------------------------------
    # REJECT helper (S-3 pattern, mirrors ExtractXMLField._make_reject_row)
    # ------------------------------------------------------------------

    @staticmethod
    def _make_reject_row(
        row: pd.Series, xml_string: Any, code: str, msg: str
    ) -> Dict[str, Any]:
        """Build a reject row dict with error detail columns.

        Args:
            row: The input row being processed.
            xml_string: The raw XML string (or None) that caused the error.
            code: Short error code (e.g. 'PARSE_ERROR', 'NO_XML').
            msg: Human-readable error message.

        Returns:
            Dict carrying all input columns plus errorXMLField, errorCode, errorMessage.
        """
        reject_row = {k: row.get(k, None) for k in row.index}
        reject_row["errorXMLField"] = xml_string
        reject_row["errorCode"] = code
        reject_row["errorMessage"] = msg
        return reject_row

    # ------------------------------------------------------------------
    # Per-document XML evaluation helper
    # ------------------------------------------------------------------

    def _evaluate_xml_for_row(
        self,
        root: etree._Element,
        output_schema: List[Dict[str, Any]],
        expressions: Dict[str, str],
        looping_element: str,
        ns_prefix: str,
        nsmap: Dict[str, str],
        component_id: str,
    ) -> List[Dict[str, Any]]:
        """Parse one XML document (root) and return a list of output row dicts.

        This method contains the existing tree-walking logic extracted from the
        former iloc[0,0]-based single-document code path. It is now called once
        per input row inside the per-row loop (_process).

        Args:
            root: Parsed lxml root element for this input row.
            output_schema: List of output column dicts with 'name' key.
            expressions: Column-name -> XPath mapping.
            looping_element: XPath fragment identifying loop nodes.
            ns_prefix: Namespace prefix to use (may be empty string).
            nsmap: Resolved namespace map.
            component_id: Component ID for log messages.

        Returns:
            List of dicts, one per loop node matched.
        """
        # Build Loop XPath expression
        if looping_element:
            if ":" in looping_element or not ns_prefix:
                loop_xpath = f".//{looping_element}"
            else:
                loop_xpath = f".//{ns_prefix}:{looping_element}"
        else:
            loop_xpath = "."

        # Qualify Loop XPath and find Loop nodes
        loop_xpath_q = qualify_xpath(loop_xpath, ns_prefix) if ns_prefix else loop_xpath
        logger.debug("[%s] Loop XPath (qualified): %s", component_id, loop_xpath_q)

        # Execute Loop XPath to find nodes
        loop_nodes = (
            root.xpath(loop_xpath_q, namespaces=nsmap) if ns_prefix
            else root.xpath(loop_xpath_q)
        ) if loop_xpath_q != "." else [root]

        logger.info("[%s] Found %d nodes for looping element", component_id, len(loop_nodes))

        if not loop_nodes:
            logger.warning(
                "[%s] No nodes found for looping element '%s'",
                component_id, looping_element,
            )
            return []

        # Process each loop node to extract data
        rows: List[Dict[str, Any]] = []

        for idx, loop_node in enumerate(loop_nodes):
            logger.debug("[%s] Processing node %d: tag=%s", component_id, idx, loop_node.tag)
            logger.debug(
                "[%s] Parent chain for node %d: %s",
                component_id, idx,
                [p.tag for p in loop_node.iterancestors()],
            )

            row: Dict[str, Any] = {}

            # Process each output column
            for col in output_schema:
                col_name = col["name"]
                raw_expr = expressions.get(col_name, "")
                expr_q = qualify_xpath(raw_expr, ns_prefix) if ns_prefix else raw_expr
                ctx = choose_context(raw_expr, loop_node, root)

                logger.debug(
                    "[%s] Node %d - Evaluating '%s': raw='%s' qualified='%s'",
                    component_id, idx, col_name, raw_expr, expr_q,
                )

                # Execute XPath expression with error handling
                try:
                    if ns_prefix:
                        result = ctx.xpath(expr_q, namespaces=nsmap)
                    else:
                        result = ctx.xpath(expr_q)
                except Exception as exc:
                    logger.error(
                        "[%s] Failed to extract '%s' with expr '%s': %s",
                        component_id, col_name, expr_q, exc,
                    )
                    row[col_name] = ""
                    continue

                # Apply fallback for unreachable ancestor elements (BUG-XMP-006)
                if (
                    (not result or (isinstance(result, list) and len(result) == 0))
                    and raw_expr.strip().startswith("./ancestor::")
                ):
                    tail = raw_expr.strip()[len("./ancestor::"):]
                    fb_expr = "//" + tail
                    fb_expr_q = qualify_xpath(fb_expr, ns_prefix) if ns_prefix else fb_expr
                    logger.debug(
                        "[%s] Fallback for '%s': trying '%s' from ROOT",
                        component_id, col_name, fb_expr_q,
                    )

                    try:
                        if ns_prefix:
                            result = root.xpath(fb_expr_q, namespaces=nsmap)
                        else:
                            result = root.xpath(fb_expr_q)
                    except Exception as fe:
                        logger.debug(
                            "[%s] Fallback XPath error for '%s': %s",
                            component_id, col_name, fe,
                        )
                        result = []

                # Apply scoping for multiple results
                if isinstance(result, list) and len(result) > 1:
                    parent = loop_node.getparent()
                    if parent is not None:
                        scoped = [r for r in result if isinstance(r, etree._Element) and parent in r.iterancestors()]
                        if scoped:
                            result = scoped

                # Extract final value
                value = extract_value(result)
                row[col_name] = value

                logger.debug(
                    "[%s] Node %d - Column '%s' extracted value: '%s'",
                    component_id, idx, col_name, value,
                )

            rows.append(row)
            logger.debug("[%s] Row ready idx=%d: %s", component_id, idx, row)

        return rows

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process XML data and extract values using XPath expressions.

        Iterates over all rows in input_data (BUG-XMP-003 fix: was iloc[0,0]).
        Routes per-row parse errors to reject_df per die_on_error setting
        (ENG-XMP-003 + ENG-XMP-006 fix).

        Args:
            input_data: Input DataFrame with XML data (may be None or empty)

        Returns:
            Dictionary containing:
                - 'main': Transformed DataFrame with extracted XML data
                - 'reject': DataFrame of rows that failed (errorCode + errorMessage)
        """
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning("[%s] Empty input received", self.id)
            return {"main": pd.DataFrame(), "reject": pd.DataFrame()}

        # BUG-XMP-004 fix: read component_id from self.id; do NOT overwrite self.id
        # from config. self.id is set by BaseComponent at construction and must not
        # be mutated during _process.
        component_id = self.id

        # Get configuration with defaults
        config = self.config

        # ---- D-E1 conditional warn-and-ignore ----
        if config.get("activate_expression_filter"):
            logger.warning("[%s] expression_filter (Java) is not implemented; ignoring (Phase 12 needs_review).", component_id)
        if self._has_lookup_connection():
            logger.warning("[%s] tXMLMap lookup/join is not implemented; ignoring (Phase 12 needs_review).", component_id)
        if self._has_all_in_one_output():
            logger.warning("[%s] tXMLMap Document output (allInOne) is not implemented; falling back to per-row (Phase 12 needs_review).", component_id)

        logger.info("[%s] Processing started: XML mapping transformation", component_id)

        # ---- Config extraction ----
        output_schema = (
            config.get("output_schema", []) or config.get("schema", {}).get("output", [])
        )
        expressions = config.get("expressions", {}) or {}
        looping_element = (
            config.get("looping_element", "") or
            config.get("config", {}).get("looping_element", "")
        )
        # tXMLMap default is die_on_error=True per Talaxie javajet
        die_on_error = config.get("die_on_error", True)

        # Clean up malformed expressions from JSON (fix corrupted Talend expressions)
        cleaned_expressions: Dict[str, str] = {}
        for col_name, raw_expr in expressions.items():
            cleaned_expr = self._clean_expression(raw_expr)
            cleaned_expressions[col_name] = cleaned_expr
            logger.debug("[%s] Expr cleanup: '%s' -> '%s'", component_id, raw_expr, cleaned_expr)
        expressions = cleaned_expressions

        # ---- Per-row loop (BUG-XMP-003 fix) ----
        main_rows: List[Dict[str, Any]] = []
        reject_rows: List[Dict[str, Any]] = []
        rows_total = 0
        rows_ok = 0
        rows_reject = 0

        # Determine which column carries the XML data (first column by convention)
        xml_col = input_data.columns[0]

        for _, row in input_data.iterrows():
            rows_total += 1
            xml_string = row.get(xml_col, None)

            # Null / empty check
            try:
                _na_check = pd.isna(xml_string)
                # pd.isna on a list/array returns array; use bool() to catch ambiguous truth
                is_null = bool(_na_check)
            except (TypeError, ValueError):
                is_null = False

            try:
                is_empty = xml_string == ""
            except (TypeError, ValueError):
                is_empty = False

            if is_null or is_empty:
                reject_rows.append(
                    self._make_reject_row(row, xml_string, _ERR_NO_XML, "No XML data")
                )
                rows_reject += 1
                continue

            # SEC-XMP-001: delegate parser construction to _xml_io.secure_xml_parser()
            try:
                parser = _xml_io.secure_xml_parser()
                root = etree.fromstring(
                    xml_string.encode("utf-8") if isinstance(xml_string, str) else xml_string,
                    parser=parser,
                )
            except (etree.XMLSyntaxError, TypeError, ValueError) as exc:
                logger.warning("[%s] XML parse failed: %s", component_id, exc)
                if die_on_error and isinstance(exc, etree.XMLSyntaxError):
                    raise DataValidationError(
                        f"[{component_id}] XML parse failed: {exc}"
                    ) from exc
                reject_rows.append(
                    self._make_reject_row(row, xml_string, _ERR_PARSE, str(exc))
                )
                rows_reject += 1
                continue

            # Normalize namespace mapping
            nsmap = normalize_nsmap(root)
            logger.debug("[%s] Raw nsmap from XML: %s", component_id, nsmap)

            # Determine namespace prefix strategy
            if None in nsmap:
                ns_prefix = DEFAULT_NAMESPACE_PREFIX
            elif len(nsmap) == 1 and any(k.strip().lower() == "xsi" for k in nsmap.keys()):
                ns_prefix = ""
                logger.debug(
                    "[%s] Only xsi namespace found -- treating as unqualified XML",
                    component_id,
                )
            elif nsmap:
                ns_prefix = next(iter(nsmap.keys()))
            else:
                ns_prefix = ""

            logger.debug("[%s] Final ns_prefix: '%s'", component_id, ns_prefix)

            # Clean looping element against the current document root
            if looping_element:
                cleaned_le = self._clean_looping_element(looping_element, root)
                logger.debug(
                    "[%s] Looping element cleanup: '%s' -> '%s'",
                    component_id, looping_element, cleaned_le,
                )
                eff_looping_element = cleaned_le
            else:
                eff_looping_element = looping_element

            # Evaluate the XML document for this row
            try:
                row_outputs = self._evaluate_xml_for_row(
                    root=root,
                    output_schema=output_schema,
                    expressions=expressions,
                    looping_element=eff_looping_element,
                    ns_prefix=ns_prefix,
                    nsmap=nsmap,
                    component_id=component_id,
                )
                for out_row in row_outputs:
                    main_rows.append(out_row)
                    rows_ok += 1
            except Exception as exc:
                logger.warning("[%s] XML evaluation failed for row: %s", component_id, exc)
                if die_on_error:
                    raise DataValidationError(
                        f"[{component_id}] XML evaluation failed for row: {exc}"
                    ) from exc
                reject_rows.append(
                    self._make_reject_row(row, xml_string, _ERR_EVAL, str(exc))
                )
                rows_reject += 1

        # ---- Build result DataFrames ----
        if main_rows:
            df = pd.DataFrame(main_rows)
            want_cols = [c["name"] for c in output_schema]
            for c in want_cols:
                if c not in df.columns:
                    df[c] = ""
            df = df[want_cols]
        else:
            want_cols = [c["name"] for c in output_schema]
            df = pd.DataFrame(columns=want_cols)

        reject_df = pd.DataFrame(reject_rows) if reject_rows else pd.DataFrame()

        # Stats
        self._update_stats(rows_total, rows_ok, rows_reject)

        logger.info(
            "[%s] done: rows=%d ok=%d reject=%d",
            component_id, rows_total, rows_ok, rows_reject,
        )

        return {"main": df, "reject": reject_df}

    def validate_config(self) -> bool:
        """
        Validate the component configuration.

        Returns:
            bool: True if configuration is valid, False otherwise

        Note:
            This method maintains backward compatibility. The preferred method
            is _validate_config() which raises ConfigurationError.
        """
        try:
            self._validate_config()
            logger.debug("[%s] Configuration validation passed", self.id)
            return True
        except ConfigurationError as exc:
            logger.error("[%s] Configuration error: %s", self.id, exc)
            return False
