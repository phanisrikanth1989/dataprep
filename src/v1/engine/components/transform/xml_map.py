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
  D-E1: expression_filter evaluated natively in Python (Relational.ISNULL/ISNOTNULL)
  D-E2: Zero Java bridge imports (contract maintained per plan 12-05)
"""
import logging
import re
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

# Regex matching Talend javajet placeholder syntax: [flow.col:/absolute/xpath]
# These appear in expression_filter (and potentially expressions) and must be
# resolved to XPath values before the expression can be executed as Groovy.
_FILTER_PLACEHOLDER_RE = re.compile(r"\[[\w]+\.[\w]+:(/[^\]]+)\]")

# --------------------------------
# Helpers: namespaces + XPath
# --------------------------------

def normalize_nsmap(root: etree._Element) -> Dict[str, str]:
    """Build a merged namespace map from root AND all descendants (P-5 fix).

    CR-03 fix: the previous implementation only read root.nsmap, which misses
    namespace declarations made exclusively on descendant elements. In lxml,
    each element's nsmap contains only the namespaces visible at that node.
    Walking all descendants with root.iter() matches the ENG-FIX-004 fix
    applied in file_input_xml.py._build_nsmap.

    The default namespace (None key in lxml) is mapped to DEFAULT_NAMESPACE_PREFIX
    ("ns0") so XPath can reference it with a prefix. This key is excluded from
    the returned dict because lxml XPath does not allow None as a prefix.

    Args:
        root: Root XML element (or any element to start the walk from)

    Returns:
        Dictionary mapping namespace prefixes (str) to URIs. Never contains
        None as a key -- the default namespace is keyed as DEFAULT_NAMESPACE_PREFIX.
    """
    collected: Dict[str, str] = {}
    for el in root.iter():
        for k, v in (el.nsmap or {}).items():
            if k is None:
                # Default namespace: map to sentinel prefix for XPath use
                if DEFAULT_NAMESPACE_PREFIX not in collected:
                    collected[DEFAULT_NAMESPACE_PREFIX] = v
            elif k not in collected:
                collected[k] = v
    # Exclude None key (safety -- should not exist after the above logic)
    return {k: v for k, v in collected.items() if k is not None}


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

    def _resolve_expressions(self) -> None:
        """Pre-clean expression_filter before Java bridge resolution.

        Talend's expressionFilter uses [row.col:/xpath] DSL which is NOT valid
        Groovy.  Strip any ``{{java}}`` prefix so ``_resolve_java_expressions``
        does not attempt bridge execution and fail with a Groovy parse error.
        The engine evaluates the filter natively in ``_process``.
        """
        ef = self.config.get("expression_filter")
        if isinstance(ef, str) and ef.startswith("{{java}}"):
            self.config["expression_filter"] = ef[8:]
        super()._resolve_expressions()

    # ------------------------------------------------------------------
    # Expression-filter helpers
    # Two-step approach that works for ANY routine or compound expression:
    #   Step 1 — _substitute_xml_placeholders:
    #     Python/lxml resolves every [flow.col:/xpath] token in the filter
    #     string to a Groovy-safe literal ("text" or null), producing valid
    #     Groovy that the bridge can parse.
    #   Step 2 — _compute_filter_mask:
    #     All N resolved expressions (one per loop node) are sent to the Java
    #     bridge in a SINGLE batch call per XML document.  Costs O(1) bridge
    #     round-trips regardless of the number of loop nodes.  Falls back to
    #     _evaluate_groovy_filter_natively when no bridge is available.
    # ------------------------------------------------------------------

    @staticmethod
    def _substitute_xml_placeholders(
        expr: str,
        loop_node: Any,
        looping_element: str,
        ns_prefix: str,
        nsmap: Dict[str, str],
        component_id: str,
    ) -> str:
        """Replace ``[flow.col:/abs/xpath]`` tokens with Groovy-safe literals.

        Each token is evaluated as an XPath against ``loop_node``:

        * No result / empty text  → ``null``
        * Non-empty text          → ``"value"`` (double-quoted, special chars escaped)

        The result is syntactically valid Groovy for any surrounding expression
        (``Relational.ISNULL``, custom routines, compound boolean, etc.).

        Args:
            expr: Raw filter expression, e.g. ``Relational.ISNULL([r2.c:/A/B])``.
            loop_node: lxml element for the current loop iteration.
            looping_element: Loop element name; used to make XPaths relative.
            ns_prefix: Namespace prefix (empty string if none).
            nsmap: Namespace map.
            component_id: Component ID for debug logging.

        Returns:
            Valid Groovy expression with all ``[...]`` tokens substituted.
        """
        def _resolve(m: re.Match) -> str:  # type: ignore[type-arg]
            abs_xpath = m.group(1)
            rel_xpath = XMLMap._make_filter_relative_xpath(abs_xpath, looping_element)
            try:
                if ns_prefix:
                    text_vals = loop_node.xpath(
                        rel_xpath + "/text()", namespaces=nsmap
                    )
                    if not text_vals and "//" not in rel_xpath:
                        text_vals = loop_node.xpath(
                            f".//{rel_xpath}/text()", namespaces=nsmap
                        )
                else:
                    text_vals = loop_node.xpath(rel_xpath + "/text()")
                    if not text_vals and "//" not in rel_xpath:
                        text_vals = loop_node.xpath(f".//{rel_xpath}/text()")
            except Exception as xe:
                logger.debug(
                    "[%s] Placeholder XPath eval error ('%s'): %s",
                    component_id, rel_xpath, xe,
                )
                text_vals = []
            if not text_vals or not any(str(t).strip() for t in text_vals):
                return "null"
            val = str(text_vals[0]).replace("\\", "\\\\").replace('"', '\\"')
            return f'"{val}"'

        return _FILTER_PLACEHOLDER_RE.sub(_resolve, expr)

    def _compute_filter_mask(
        self,
        raw_filter: str,
        loop_nodes: List[Any],
        looping_element: str,
        ns_prefix: str,
        nsmap: Dict[str, str],
        component_id: str,
    ) -> List[bool]:
        """Return a boolean include-mask for every loop node in one bridge call.

        Step 1 — resolve ``[flow.col:/xpath]`` placeholders for every node via
        lxml XPath, producing N syntactically valid Groovy expressions.

        Step 2 — send all N expressions to the Java bridge in a **single** batch
        call (``execute_batch_one_time_expressions``).  This keeps bridge
        overhead at O(1) per XML document regardless of loop node count.
        A running Java bridge is required; if none is set all rows are included
        and a warning is logged.

        Args:
            raw_filter: Filter expression (``{{java}}`` already stripped).
            loop_nodes: All loop node elements found in this XML document.
            looping_element: Looping element name.
            ns_prefix: Namespace prefix.
            nsmap: Namespace map.
            component_id: Component ID for logging.

        Returns:
            List of booleans, one per loop node: ``True`` = include, ``False`` = exclude.
        """
        # Step 1: resolve placeholders for every node
        resolved: Dict[str, str] = {
            f"_f{i}": self._substitute_xml_placeholders(
                raw_filter, node, looping_element, ns_prefix, nsmap, component_id
            )
            for i, node in enumerate(loop_nodes)
        }
        logger.debug(
            "[%s] Filter resolved sample: %s", component_id,
            list(resolved.values())[:3],
        )

        # Step 2a: single batch Java call — all nodes in one round-trip
        if self.java_bridge:
            try:
                results = self.java_bridge.execute_batch_one_time_expressions(resolved)
                mask: List[bool] = []
                for i in range(len(loop_nodes)):
                    val = results.get(f"_f{i}")
                    if isinstance(val, str) and val.startswith("{{ERROR}}"):
                        logger.warning(
                            "[%s] Filter eval error for node %d: %s — including row",
                            component_id, i, val[9:],
                        )
                        mask.append(True)  # fail-open
                    else:
                        mask.append(bool(val))
                return mask
            except Exception as exc:
                logger.warning(
                    "[%s] Filter batch Java eval failed: %s — including all rows",
                    component_id, exc,
                )
                return [True] * len(loop_nodes)

        # No bridge — cannot evaluate; include all rows and warn
        logger.warning(
            "[%s] expression_filter requires a running Java bridge; "
            "including all rows (start the engine with java_config.enabled=true)",
            component_id,
        )
        return [True] * len(loop_nodes)

    @staticmethod
    def _make_filter_relative_xpath(abs_xpath: str, looping_element: str) -> str:
        """Convert an absolute Talend XPath to one relative to the loop node.

        Example::

            abs_xpath  = "/CMARGINSCM/RequiredMargins/RequiredMarginDetail/RequiredMarginComponent/MarginType"
            looping_element = "RequiredMarginDetail"
            → "RequiredMarginComponent/MarginType"

        If the looping element is not found in the path the full path (without
        the leading ``/``) is returned as a best-effort fallback.

        Args:
            abs_xpath: Absolute XPath extracted from the Talend expression.
            looping_element: Name of the element being looped over.

        Returns:
            Relative XPath string suitable for evaluation on a loop node.
        """
        path = "/".join(p for p in abs_xpath.split("/") if p)
        parts = path.split("/")
        for i, part in enumerate(parts):
            # Strip any namespace prefix for comparison
            local = part.split(":")[-1] if ":" in part else part
            if local == looping_element or part == looping_element:
                relative = "/".join(parts[i + 1 :])
                return relative if relative else "."
        # looping_element not found — return full path (best-effort)
        return path

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

        CR-02 fix: rstrip("]") removed from ALL branches. A trailing ']' on a
        valid XPath expression is a predicate closer (e.g. "./item[1]") and must
        NOT be stripped. The "[row1.employee:...]" pattern is fully handled by the
        startswith("[") and endswith("]") branch via cleaned[1:-1].

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
                return f"./{field_name}"

        # Handle dot notation like "row1.field_name"
        elif "." in cleaned and not cleaned.startswith("./"):
            parts = cleaned.split(".")
            if len(parts) >= 2:
                field_name = parts[-1]  # Take the last part (field name)
                return f"./{field_name}"

        # Handle already clean expressions starting with "./" -- return as-is
        elif cleaned.startswith("./"):
            return cleaned

        # Default: assume it's a direct field reference
        else:
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
    # Flat-to-flat mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_flow_column_expr(expr: str) -> Optional[tuple]:
        """Parse a 'flow.column' expression into (flow, column) tuple.

        Returns (flow, column) if expr is exactly 'flowname.columnname'
        (no slashes, no spaces). Returns None for XPath-style expressions.
        """
        if not expr or not isinstance(expr, str):
            return None
        expr = expr.strip()
        if "/" in expr or " " in expr:
            return None
        parts = expr.split(".")
        if len(parts) == 2 and parts[0] and parts[1]:
            return (parts[0], parts[1])
        return None

    def _build_flat_column_map(self) -> Optional[Dict[str, str]]:
        """Return {output_col: input_col} when ALL output_trees nodes use 'flow.col' expressions.

        Returns None if any node expression is XPath-style (contains '/' or
        does not match 'flow.column'), signalling that XML-parse mode is required.
        """
        output_trees = self.config.get("output_trees", []) or []
        if not output_trees:
            return None
        mapping: Dict[str, str] = {}
        for tree in output_trees:
            for node in tree.get("nodes", []):
                expr = node.get("expression", "")
                col_name = node.get("name", "")
                parsed = self._parse_flow_column_expr(expr)
                if parsed is None:
                    return None  # At least one XPath expr -- use XML path
                _, input_col = parsed
                mapping[col_name] = input_col
        return mapping if mapping else None

    def _process_flat(
        self,
        input_data: pd.DataFrame,
        flat_map: Dict[str, str],
        output_schema: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Direct column-to-column mapping when no XML parsing is needed.

        Used when all output_trees expressions are 'flow.column' references
        (e.g. 'row1.id'). Bypasses XML parsing entirely.
        """
        component_id = self.id
        rows_total = len(input_data)
        want_cols = [c["name"] for c in output_schema]
        result: Dict[str, Any] = {}
        for out_col in want_cols:
            in_col = flat_map.get(out_col, out_col)
            if in_col in input_data.columns:
                result[out_col] = input_data[in_col].tolist()
            elif out_col in input_data.columns:
                result[out_col] = input_data[out_col].tolist()
            else:
                result[out_col] = [None] * rows_total
        df = pd.DataFrame(result)
        self._update_stats(rows_total, rows_total, 0)
        logger.info(
            "[%s] done (flat): rows=%d ok=%d reject=0",
            component_id, rows_total, rows_total,
        )
        return {"main": df, "reject": pd.DataFrame()}

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
        expression_filter: str = "",
    ) -> List[Dict[str, Any]]:
        """Parse one XML document (root) and return a list of output row dicts.

        This method contains the existing tree-walking logic extracted from the
        former iloc[0,0]-based single-document code path. It is now called once
        per input row inside the per-row loop (_process).

        When ``expression_filter`` is non-empty, all ``[flow.col:/xpath]``
        placeholders are resolved via lxml XPath for every loop node, and the
        resulting Groovy expressions are evaluated in a **single** batch call to
        the Java bridge (or natively when no bridge is available).  This handles
        any routine or compound expression, not just ISNULL/ISNOTNULL.

        Args:
            root: Parsed lxml root element for this input row.
            output_schema: List of output column dicts with 'name' key.
            expressions: Column-name -> XPath mapping.
            looping_element: XPath fragment identifying loop nodes.
            ns_prefix: Namespace prefix to use (may be empty string).
            nsmap: Resolved namespace map.
            component_id: Component ID for log messages.
            expression_filter: Filter expression string (``{{java}}`` already
                stripped).  Empty string means no filter.

        Returns:
            List of dicts, one per loop node that passed the filter.
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

        # ---- Pre-compute filter mask (one batch Java call per document) ----
        # All [flow.col:/xpath] placeholders are resolved first, then the N
        # resulting Groovy expressions are sent to the bridge in a single call.
        include_mask: Optional[List[bool]] = None
        if expression_filter:
            include_mask = self._compute_filter_mask(
                expression_filter, loop_nodes, looping_element,
                ns_prefix, nsmap, component_id,
            )

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

            # ---- Apply expression_filter from pre-computed mask ----
            if include_mask is not None and not include_mask[idx]:
                logger.debug("[%s] Node %d filtered out by expression_filter", component_id, idx)
                continue

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

        # ---- D-E1 feature handling ----
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

        # ---- Expression-filter (D-E1) ----
        # expression_filter uses Talend DSL with [flow.col:/xpath] placeholders.
        # The {{java}} prefix was stripped by _resolve_expressions() if present.
        # _compute_filter_mask() resolves all placeholders via lxml XPath and
        # sends the resulting Groovy expressions to the Java bridge in one batch
        # call (or falls back to native Python for ISNULL/ISNOTNULL).
        expression_filter = ""
        if config.get("activate_expression_filter"):
            raw_filter = (config.get("expression_filter") or "").strip()
            if not raw_filter:
                logger.warning(
                    "[%s] expression_filter flag set but no filter expression provided; ignoring",
                    component_id,
                )
            else:
                expression_filter = raw_filter
                bridge_active = bool(self.java_bridge)
                logger.info(
                    "[%s] expression_filter active%s: %s",
                    component_id,
                    " (via Java bridge)" if bridge_active else " (WARNING: Java bridge not running — filter will be skipped)",
                    raw_filter,
                )

        # ---- Flat-to-flat early exit ----
        # When all output_trees expressions are 'flow.column' refs (e.g. 'row1.id'),
        # no XML parsing is needed -- map columns directly.
        flat_map = self._build_flat_column_map()
        if flat_map is not None:
            logger.info("[%s] flat-to-flat mode detected; skipping XML parse", component_id)
            return self._process_flat(input_data, flat_map, output_schema)

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

            # Determine namespace prefix strategy.
            # WR-01 fix: normalize_nsmap never returns None as a key (default namespace
            # is mapped to DEFAULT_NAMESPACE_PREFIX "ns0"). The old check
            # "if None in nsmap" was permanently False (dead code). Use the sentinel
            # key directly to detect when a default namespace was present.
            if DEFAULT_NAMESPACE_PREFIX in nsmap:
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
                    expression_filter=expression_filter,
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
