"""
XMLMap - XML mapping and transformation component with namespace handling.

Talend equivalent: XMLMap (standardized from tXMLMap)

This component processes XML data using XPath expressions to extract and transform data.
Supports namespace handling, looping elements, and expression-based field mapping.
"""
import logging
import pandas as pd
import lxml.etree as ET
from typing import Dict, Any, Optional, List

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)

# Class constants
AXES = ("ancestor", "descendant", "self", "parent", "child", "following", "preceding")
DEFAULT_NAMESPACE_PREFIX = "ns0"
DEFAULT_LOOPING_ELEMENT = ""

# --------------------------------
# Helpers: namespaces + XPath
# --------------------------------

def normalize_nsmap(root: ET._Element) -> Dict[str, str]:
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
    Split XPath expression into individual steps handling axes and operators.

    Args:
        expr: XPath expression to split

    Returns:
        List of XPath steps
    """
    expr = expr.strip()
    out: List[str] = []
    i = 0
    n = len(expr)
    buf = []

    def flush():
        if buf:
            out.append("".join(buf))
            buf.clear()

    while i < n:
        ch = expr[i]

        if ch == "/" and i + 1 < n and expr[i + 1] == "/":
            flush()
            out.append("//")
            i += 2
            continue

        if ch == "/":
            flush()
            i += 1
            continue

        if ch.isalpha():
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
                flush()
                continue

        buf.append(ch)
        i += 1

    flush()
    return [s for s in out if s != ""]


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
            rest = s[len(ax) + 2 :]
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
    qualified: list[str] = []

    def glue(acc: list[str], nxt: str):
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


def choose_context(expr: str, loop_node: ET.Element, root: ET.Element) -> ET.Element:
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
    # Includes "ancestor::" (global), "descendant::", "/", and "//"
    if (
        e.startswith("/") or e.startswith("//") or
        e.startswith("ancestor::") or e.startswith("descendant::")
    ):
        print(f"[DEBUG] choose_context -> ROOT (expr='{expr}')")
        return root

    # Case 2: Relative expressions -> stay in loop context
    if (
        e.startswith("./") or e.startswith(".//") or
        e.startswith("./descendant::")
    ):
        # Handle relative ancestors smartly
        if e.startswith("./ancestor::"):
            parent = loop_node.getparent()
            print(f"[DEBUG] Parent Vaue -> '{parent}')")
            # Only fall back to ROOT if no parent/ancestor exists
            if parent is None:
                print(f"[DEBUG] choose_context -> ROOT (no parent, expr='{expr}')")
                return root
            else:
                print(f"[DEBUG] choose_context -> LOOP_NODE (expr='{expr}')")
                return loop_node

        print(f"[DEBUG] choose_context -> LOOP_NODE (expr='{expr}')")
        return loop_node

    # Case 3: Default fallback -> loop context
    print(f"[DEBUG] choose_context -> LOOP_NODE (expr='{expr}')")
    return loop_node


def extract_value(node_or_nodes) -> str:
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
    if isinstance(first, ET._Element):
        txt = (first.text or "").strip()
        if txt:
            return txt
        if first.attrib:
            return " ".join(f"{k}={v}" for k, v in first.attrib.items())
        return ""
    return str(first)

def _broaden_ancestor_if_empty(ctx: ET._Element, expr_q: str, nsmap: Dict[str, str]):
    """
    Broaden ancestor search if initial XPath evaluation returns empty results.

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

    tail = expr_q[len("./ancestor::"):]
    # Make sure we don't accidentally start with a slash twice
    broadened = "./ancestor::*//" + tail.lstrip("/")
    try:
        res2 = ctx.xpath(broadened, namespaces=nsmap)
        return res2
    except Exception:
        return res  # fallback to original empty


# --------------------------------
# Component implementation
# --------------------------------

class XMLMap(BaseComponent):
    """
    Performs XML mapping and transformation with advanced namespace handling.
    Equivalent to Talend's tXMLMap component.

    Configuration:
        looping_element (str): XPath expression for loop element. Default: ""
        output_schema (List[Dict]): Output column definitions. Required.
        expressions (Dict[str, str]): Column name to XPath expression mapping. Required.
        id (str): Component identifier. Default: "XMLMap"

    Inputs:
        main: Input DataFrame with XML data (first column contains XML string)

    Outputs:
        main: Transformed DataFrame with extracted XML data

    Statistics:
        NB_LINE: Total rows processed (output rows)
        NB_LINE_OK: Successfully processed rows
        NB_LINE_REJECT: Always 0 (no rows rejected)

    Example:
        config = {
            "looping_element": "Record",
            "output_schema": [
                {"name": "id", "type": "id_String"},
                {"name": "name", "type": "id_String"}
            ],
            "expressions": {
                "id": "./id/text()",
                "name": "./name/text()"
            }
        }

    Notes:
        - Handles default namespaces (xmlns="...") and prefixed namespaces automatically
        - Supports relative paths (./), ancestor paths (./ancestor::), absolute (/) and descendant (//) paths
        - Evaluates attribute access (@attr), functions (text(), position()), and wildcards (*)
        - Row generation driven by looping_element; each loop node yields one row
        - Intelligent context selection between root and loop node based on XPath pattern
        - Fallback mechanisms for unreachable ancestor elements
        - Preserves all existing XML processing logic and namespace handling
    """

    # Class constants
    DEFAULT_COMPONENT_ID = "XMLMap"

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Get configuration
        config = getattr(self, "config", {})

        # Validate output_schema
        output_schema = config.get("output_schema", []) or config.get("schema", {}).get("output", [])
        if not output_schema:
            errors.append("Missing required config: 'output_schema' or 'schema.output'")
        elif not isinstance(output_schema, list):
            errors.append("Config 'output_schema' must be a list")
        else:
            for i, col in enumerate(output_schema):
                if not isinstance(col, dict):
                    errors.append(f"Output schema column {i} must be a dictionary")
                    continue
                if 'name' not in col:
                    errors.append(f"Output schema column {i}: missing required field 'name'")
                elif not isinstance(col['name'], str):
                    errors.append(f"Output schema column {i}: 'name' must be a string")

        # Validate expressions
        expressions = config.get("expressions", {})
        if not isinstance(expressions, dict):
            errors.append("Config 'expressions' must be a dictionary")

        # Validate looping_element if present
        looping_element = config.get("looping_element", "") or config.get("config", {}).get("looping_element", "")
        if looping_element is not None and not isinstance(looping_element, str):
            errors.append("Config 'looping_element' must be a string")

        return errors

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
        if cleaned.startswith('[') and cleaned.endswith(']'):
            cleaned = cleaned[1:-1]

        # Handle complex malformed expressions like "./employee:/employees/employee/id"
        if ':' in cleaned and '/' in cleaned:
            # Extract field name from the path (last part after /)
            if '/' in cleaned:
                field_name = cleaned.split('/')[-1]
                # Remove any trailing brackets
                field_name = field_name.rstrip(']')
                return f"./{field_name}"

        # Handle dot notation like "row1.field_name"
        elif '.' in cleaned and not cleaned.startswith('./'):
            parts = cleaned.split('.')
            if len(parts) >= 2:
                field_name = parts[-1]  # Take the last part (field name)
                # Remove any trailing brackets
                field_name = field_name.rstrip(']')
                return f"./{field_name}"

        # Handle already clean expressions starting with "./"
        elif cleaned.startswith('./'):
            # Remove any trailing brackets
            cleaned = cleaned.rstrip(']')
            return cleaned

        # Default: assume it's a direct field reference
        else:
            # Remove any trailing brackets
            cleaned = cleaned.rstrip(']')
            return f"./{cleaned}"

    def _clean_looping_element(self, raw_looping_element: str, root: ET.Element) -> str:
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
        if '/' in cleaned:
            parts = cleaned.split('/')
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

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process XML data and extract values using XPath expressions.

        Args:
            input_data: Input DataFrame with XML data (may be None or empty)

        Returns:
            Dictionary containing:
                - 'main': Transformed DataFrame with extracted XML data

        Raises:
            No exceptions raised - all parsing errors are handled gracefully
        """
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            return {"main": pd.DataFrame()}

        # Get configuration with defaults
        config = getattr(self, "config", {})
        self.id = config.get("id", self.DEFAULT_COMPONENT_ID)

        logger.info(f"[{self.id}] Processing started: XML mapping transformation")
        print(f"[XMLMap] Processing started")
        print(f"\n>>> [XMLMap] STARTED --- Component ID: {self.id}", flush=True)

        # Extract XML string from first column
        xml_col = input_data.columns[0]
        xml_string = str(input_data.iloc[0, 0] or "")
        logger.debug(f"[{self.id}] XML input length: {len(xml_string)} characters")
        print(f">>> [XMLMap] XML input length: {len(xml_string)} characters", flush=True)

        # Parse XML with error handling
        try:
            root = ET.fromstring(xml_string.encode("utf-8"))
            logger.debug(f"[{self.id}] XML parsed successfully")
            print(">>> [XMLMap] XML parsed successfully", flush=True)
        except Exception as e:
            logger.error(f"[{self.id}] Failed to parse XML: {e}")
            print(f"[XMLMap ERROR] Failed to parse XML: {e}", flush=True)
            return {"main": pd.DataFrame()}

        # Normalize namespace mapping
        nsmap = normalize_nsmap(root)
        logger.debug(f"[{self.id}] Raw nsmap from XML: {nsmap}")
        print(f"[DEBUG] Raw nsmap from XML: {nsmap}")

        # Determine namespace prefix strategy
        if None in nsmap:
            # Case 1: Default namespace -> remap to ns0
            ns_prefix = DEFAULT_NAMESPACE_PREFIX
            logger.debug(f"[{self.id}] Default namespace found, using prefix '{DEFAULT_NAMESPACE_PREFIX}'")
            print(f"[DEBUG] Default namespace found, using prefix 'ns0'")
        elif len(nsmap) == 1 and any(k.strip().lower() == "xsi" for k in nsmap.keys()):
            # Case 2: Schema-only (xsi) -> treat tags as unqualified
            ns_prefix = ""
            logger.debug(f"[{self.id}] Only schema namespace (xsi) found - treating as unqualified XML")
            print(f"[DEBUG] only schema namespace (xsi) found - treating as unqualified XML")
            print(f"[DEBUG fix] reset ns_prefix -> empty (no namespace qualification for elements)")
        elif nsmap:
            # Case 3: Named prefix exists (abc, ns1, etc.)
            ns_prefix = next(iter(nsmap.keys()))
            logger.debug(f"[{self.id}] Using existing prefix from XML: '{ns_prefix}'")
            print(f"[DEBUG] Using existing prefix from XML: '{ns_prefix}'")
        else:
            # Case 4: No namespaces at all
            ns_prefix = ""
            logger.debug(f"[{self.id}] No namespaces detected - using unqualified paths")
            print(f"[DEBUG] No namespaces detected - using unqualified paths")

        logger.debug(f"[{self.id}] Final normalized nsmap: {nsmap}")
        logger.debug(f"[{self.id}] Final ns_prefix: '{ns_prefix}'")
        print(f"[DEBUG] Final normalized nsmap: {nsmap}")
        print(f"[DEBUG] Final ns_prefix: '{ns_prefix}'")

        # Get configuration values
        output_schema = config.get("output_schema", []) or config.get("schema", {}).get("output", [])
        expressions = config.get("expressions", {}) or {}
        looping_element = config.get("looping_element", "") or config.get("config", {}).get("looping_element", "")

        # Clean up malformed expressions from JSON (fix corrupted Talend expressions)
        cleaned_expressions = {}
        for col_name, raw_expr in expressions.items():
            cleaned_expr = self._clean_expression(raw_expr)
            cleaned_expressions[col_name] = cleaned_expr
            print(f"[XMLMap CLEANUP] {col_name}: '{raw_expr}' -> '{cleaned_expr}'", flush=True)

        expressions = cleaned_expressions

        # Clean up looping element as well (handle malformed looping elements)
        if looping_element:
            cleaned_looping_element = self._clean_looping_element(looping_element, root)
            print(f"[XMLMap CLEANUP] Looping element: '{looping_element}' -> '{cleaned_looping_element}'", flush=True)
            looping_element = cleaned_looping_element

        logger.debug(f"[{self.id}] Looping element: '{looping_element}'")
        logger.debug(f"[{self.id}] Output schema columns: {len(output_schema)}")
        logger.debug(f"[{self.id}] Expression mappings: {len(expressions)}")
        print(f">>> [XMLMap] Looping element: {looping_element}", flush=True)
        print(f">>> [XMLMap] Cleaned expressions: {expressions}", flush=True)

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
        logger.debug(f"[{self.id}] Loop XPath (qualified): {loop_xpath_q}")
        print(f">>[XMLMap loop] Loop XPath(qualified): {loop_xpath_q}", flush=True)

        # Execute Loop XPath to find nodes
        loop_nodes = (
            root.xpath(loop_xpath_q, namespaces=nsmap) if ns_prefix
            else root.xpath(loop_xpath_q)
        ) if loop_xpath_q != "." else [root]

        logger.info(f"[{self.id}] Found {len(loop_nodes)} nodes for looping element")
        print(f">>> [XMLMap] Loop XPath: {loop_xpath_q}", flush=True)
        print(f">>> [XMLMap] Found {len(loop_nodes)} nodes for looping element", flush=True)

        if not loop_nodes:
            logger.warning(f"[{self.id}] No nodes found for looping element '{looping_element}'")
            print(f">>> [XMLMap WARN] No nodes found for looping element '{looping_element}'", flush=True)
            return {"main": pd.DataFrame(columns=[col["name"] for col in output_schema])}

        # Process each loop node to extract data
        rows: List[Dict[str, Any]] = []

        for idx, loop_node in enumerate(loop_nodes):
            logger.debug(f"[{self.id}] Processing node {idx}: tag={loop_node.tag}")
            print(f"[TRACE] ===== LOOP Start idx={idx}, tag={loop_node.tag} =====", flush=True)
            print(f">>> [XMLMap] Processing node index: {idx}: tag={loop_node.tag}", flush=True)
            print(f"[TRACE] Parent chain for this loop_node: {[p.tag for p in loop_node.iterancestors()]}", flush=True)

            row: Dict[str, Any] = {}

            # Process each output column
            for col in output_schema:
                col_name = col["name"]
                raw_expr = expressions.get(col_name, "")
                expr_q = qualify_xpath(raw_expr, ns_prefix) if ns_prefix else raw_expr
                ctx = choose_context(raw_expr, loop_node, root)

                logger.debug(f"[{self.id}] Node {idx} - Evaluating column '{col_name}' with expr '{raw_expr}' -> '{expr_q}'")
                print(f"[DEBUG] Evaluating column '{col_name}' with raw_expr '{raw_expr}' with qualified_expr '{expr_q}'", flush=True)
                print(f"[TRACE]     column: {col_name}", flush=True)
                print(f"[TRACE]     raw_expr={raw_expr}", flush=True)
                print(f"[TRACE]     ctx={ctx.tag}, expr_q={expr_q}", flush=True)

                # Execute XPath expression with error handling
                try:
                    if ns_prefix:
                        result = ctx.xpath(expr_q, namespaces=nsmap)
                    else:
                        result = ctx.xpath(expr_q)
                    print(f"[TRACE] Result length={len(result) if isinstance(result, list) else 1} " f"for {col_name}, sample={[str(r)[:50] for r in (result if isinstance(result, list) else [result])[:2]]}", flush=True)

                except Exception as e:
                    logger.error(f"[{self.id}] Failed to extract '{col_name}' with expr '{expr_q}': {e}")
                    print(f"[XMLMap ERROR] Failed column '{col_name}' with expr '{expr_q}': {e}", flush=True)
                    row[col_name] = ""
                    continue

                # Apply fallback for unreachable ancestor elements
                if (
                    (not result or (isinstance(result, list) and len(result) == 0))
                    and raw_expr.strip().startswith("./ancestor::")
                ):
                    tail = raw_expr.strip()[len("./ancestor::"):]
                    fb_expr = f"//{tail}"
                    fb_expr_q = qualify_xpath(fb_expr, ns_prefix) if ns_prefix else fb_expr
                    logger.debug(f"[{self.id}] Applying fallback for '{col_name}': trying '{fb_expr_q}' from ROOT")
                    print(f"[DEBUG] Fallback for '{col_name}': trying '{fb_expr_q}' from ROOT", flush=True)

                    try:
                        if ns_prefix:
                            result = root.xpath(fb_expr_q, namespaces=nsmap)
                        else:
                            result = root.xpath(fb_expr_q)
                    except Exception as fe:
                        logger.debug(f"[{self.id}] Fallback XPath error for '{col_name}': {fe}")
                        print(f"[TRACE] Fallback XPath error for '{col_name}': {fe}", flush=True)
                        result = []

                # Apply scoping for multiple results
                if isinstance(result, list) and len(result) > 1:
                    parent = loop_node.getparent()
                    if parent is not None:
                        scoped = [r for r in result if isinstance(r, ET._Element) and parent in r.iterancestors()]
                        if scoped:
                            result = scoped

                # Extract final value
                value = extract_value(result)
                row[col_name] = value

                logger.debug(f"[{self.id}] Node {idx} - Column '{col_name}' extracted value: '{value}'")

            rows.append(row)
            print(f"[TRACE] Row ready idx={idx}, row={row}", flush=True)
            print(f"[TRACE] ---- Loop end idx={idx} ----", flush=True)

            # Log sample rows for debugging
            if idx < 3:
                logger.debug(f"[{self.id}] Sample mapped row {idx}: {row}")

        # Create DataFrame from extracted rows
        logger.debug(f"[{self.id}] Creating DataFrame from {len(rows)} extracted rows")
        print(f"[GUARD] loop_nodes: {len(loop_nodes)} | output_schema columns: {len(output_schema)}", flush=True)
        print(f"[GUARD] rows collected: {len(rows)} (expected = {len(loop_nodes)})", flush=True)

        if len(rows) != len(loop_nodes):
            logger.warning(f"[{self.id}] Row count mismatch: collected {len(rows)}, expected {len(loop_nodes)}")
            print(f"[GUARD WARN] row count mismatch", flush=True)

        # Build final DataFrame with proper column order
        df = pd.DataFrame(rows)
        want_cols = [c["name"] for c in output_schema]
        for c in want_cols:
            if c not in df.columns:
                df[c] = ""
        df = df[want_cols]

        # Calculate and update statistics
        rows_out = len(df)
        self._update_stats(rows_out, rows_out, 0)

        logger.info(f"[{self.id}] Processing complete: extracted {rows_out} rows from XML")
        logger.debug(f"[{self.id}] Final DataFrame shape: {df.shape}")
        logger.debug(f"[{self.id}] Final DataFrame preview:\n{df.head(3).to_string(index=False)}")
        print(f">>> [XMLMap] Final DataFrame shape: {df.shape}", flush=True)
        print(f">>> [XMLMap] COMPLETED --- Component ID: {self.id}\n", flush=True)
        print(f"[TRACE SUMMARY] loop_nodes={len(loop_nodes)}, rows_appended={len(rows)}", flush=True)

        return {"main": df}

    def validate_config(self) -> bool:
        """
        Validate the component configuration.

        Returns:
            bool: True if configuration is valid, False otherwise

        Note:
            This method maintains backward compatibility. The preferred method
            is _validate_config() which returns detailed error messages.
        """
        errors = self._validate_config()

        if errors:
            for error in errors:
                logger.error(f"[{self.id}] Configuration error: {error}")
            return False

        logger.debug(f"[{self.id}] Configuration validation passed")
        return True
