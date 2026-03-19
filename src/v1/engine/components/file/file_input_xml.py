"""
FileInputXML - Read XML files and extract data using XPath expressions.

Talend equivalent: tFileInputXML

This component reads XML files and extracts data based on loop queries and column mappings.
Supports namespace handling, parent navigation, and both tabular and XML passthrough modes.
"""
import logging
import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


# ----------------------------
# Helper: Extract node value
# ----------------------------
def extract_value(node_or_nodes) -> str:
    """
    Extract text value from XML node(s).

    Args:
        node_or_nodes: XML Element node or list of nodes

    Returns:
        Extracted text value as string
    """
    if not node_or_nodes:
        return ""
    if isinstance(node_or_nodes, list):
        if not node_or_nodes:
            return ""
        node = node_or_nodes[0]
    else:
        node = node_or_nodes

    if isinstance(node, ET.Element):
        txt = (node.text or "").strip()
        if txt:
            return txt
        if node.attrib:
            return " ".join(f"{k}={v}" for k, v in node.attrib.items())
        return ""
    else:
        return str(node_or_nodes)


# ----------------------------
# Helper: Namespace handling
# ----------------------------
def normalize_nsmaps(root: ET.Element) -> Dict[str, str]:
    """
    Extract namespace mapping from XML root element.

    Args:
        root: XML root element

    Returns:
        Dictionary mapping namespace prefix to URI
    """
    raw = root.tag
    if "}" in raw:
        uri = raw[raw.find("{") + 1 : raw.find("}")]
        return {"ns0": uri}
    return {}


# ----------------------------
# Helper: Prefix QName
# ----------------------------
def qualify_xpath(expr: str, ns_prefix: str) -> str:
    """
    Qualify XPath expression with namespace prefix.

    Args:
        expr: XPath expression to qualify
        ns_prefix: Namespace prefix to apply

    Returns:
        Qualified XPath expression
    """
    expr = (expr or "").strip()
    if not expr or not ns_prefix:
        return expr
    # Remove any leading slash
    if expr.startswith("/"):
        expr = expr[1:]
    # Split and prefix each element
    parts = [p for p in expr.split("/") if p]
    qualified = []
    for p in parts:
        if p in (".", "..") or p.startswith("@") or ":" in p:
            # Don't prefix navigation operators, attributes, or already qualified elements
            qualified.append(p)
        else:
            # Prefix element names with namespace
            qualified.append(f"{ns_prefix}:{p}")
    return "/".join(qualified)


# ----------------------------
# Helper: Manual parent navigation for ElementTree
# ----------------------------
def find_element_by_manual_navigation(start_node: ET.Element, xpath: str, ns_prefix: str, nsmap: dict, root: ET.Element) -> List[ET.Element]:
    """
    Manually navigate XML tree to handle .. parent navigation that ElementTree can't handle.

    Args:
        start_node: Starting XML element
        xpath: XPath expression with parent navigation
        ns_prefix: Namespace prefix
        nsmap: Namespace mapping
        root: Root XML element

    Returns:
        List of matching XML elements
    """
    if not xpath.startswith("../"):
        return []

    current = start_node
    path_parts = xpath.split("/")

    # Count how many levels to go up
    levels_up = 0
    remaining_path = []
    for part in path_parts:
        if part == "..":
            levels_up += 1
        elif part:  # Skip empty parts
            remaining_path.append(part)

    # Navigate up the required number of levels by finding parents
    for _ in range(levels_up):
        parent = find_parent_element(current, root)
        if parent is None:
            return []
        current = parent

    # Now search for the remaining path from current node
    if not remaining_path:
        return [current]

    # Qualify the remaining path
    qualified_parts = []
    for part in remaining_path:
        if ns_prefix and ":" not in part and not part.startswith("@"):
            qualified_parts.append(f"{ns_prefix}:{part}")
        else:
            qualified_parts.append(part)

    remaining_xpath = "/".join(qualified_parts)

    try:
        if ns_prefix and nsmap:
            return current.findall(remaining_xpath, namespaces=nsmap)
        else:
            return current.findall(remaining_xpath)
    except Exception:
        return []


def find_parent_element(target: ET.Element, root: ET.Element) -> Optional[ET.Element]:
    """
    Find parent of target element by traversing from root.

    Args:
        target: Target XML element
        root: Root XML element

    Returns:
        Parent element or None if not found
    """
    for elem in root.iter():
        for child in elem:
            if child is target:
                return elem
    return None


# ----------------------------
# Helper: Context decision
# ----------------------------
def choose_context(expr_q: str, loop_node: ET.Element, root: ET.Element) -> ET.Element:
    """
    Choose appropriate context node for XPath evaluation.

    Args:
        expr_q: Qualified XPath expression
        loop_node: Current loop node
        root: Root XML element

    Returns:
        Context node for XPath evaluation
    """
    # Only use root context for absolute paths starting with /
    if expr_q.startswith("/"):
        return root
    # All relative paths (including ../... paths) should use loop node context
    return loop_node


# ================================================================
# Component: FileInputXML  (Talend-like extraction)
# ================================================================
class FileInputXML(BaseComponent):
    """
    Reads XML files and extracts data using XPath expressions.

    This component provides XML file reading capabilities with support for:
    - XPath-based data extraction
    - Namespace handling
    - Parent navigation (../)
    - Loop queries for repetitive elements
    - Both tabular and XML passthrough modes

    Configuration:
        filepath (str): Path to XML file. Also supports FILENAME. Required.
        loop_query (str): XPath expression for loop elements. Also supports LOOP_QUERY.
        mapping (list): Column to XPath mappings for data extraction.
        encoding (str): File encoding. Default: 'UTF-8'
        die_on_error (bool): Fail on error. Default: True
        ignore_ns (bool): Ignore namespaces. Default: False
        ignore_dtd (bool): Ignore DTD. Default: False
        limit (int): Maximum number of elements to process. Optional.

    Inputs:
        main: Optional input DataFrame (not used for file reading)

    Outputs:
        main: DataFrame with extracted XML data

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Successful rows extracted
        NB_LINE_REJECT: Rejected rows (always 0)

    Example configuration:
        {
            "filepath": "/data/orders.xml",
            "loop_query": "//order",
            "mapping": [
                {"column": "SCHEMA_COLUMN", "xpath": "id"},
                {"column": "QUERY", "xpath": "@id"}
            ],
            "encoding": "UTF-8"
        }

    Notes:
        - Supports both 'filepath' and 'FILENAME' config keys
        - Supports both 'loop_query' and 'LOOP_QUERY' config keys
        - Automatically detects XML passthrough mode vs tabular mode
        - Handles namespace prefixing automatically
    """

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check required filepath
        filepath = self.config.get("filepath") or self.config.get("FILENAME")
        if not filepath:
            errors.append("Missing required config: 'filepath' or 'FILENAME'")

        # Validate encoding if provided
        encoding = self.config.get('encoding')
        if encoding and not isinstance(encoding, str):
            errors.append("Config 'encoding' must be a string")

        # Validate limit if provided
        limit = self.config.get('limit')
        if limit is not None:
            try:
                int(limit)
            except (ValueError, TypeError):
                errors.append("Config 'limit' must be an integer")

        # Validate mapping if provided
        mapping = self.config.get('mapping')
        if mapping is not None and not isinstance(mapping, list):
            errors.append("Config 'mapping' must be a list")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        # Handle empty input gracefully
        if input_data is not None and not input_data.empty:
            logger.debug(f"[{self.id}] Input data received but not used for XML file reading")

        # Get configuration parameters
        filepath = self.config.get("filepath") or self.config.get("FILENAME")
        loop_query = self.config.get("loop_query") or self.config.get("LOOP_QUERY") or ""
        if isinstance(loop_query, str) and loop_query.startswith('"') and loop_query.endswith('"'):
            loop_query = loop_query[1:-1]
        mapping = self.config.get("mapping") or []
        encoding = self.config.get('encoding', 'UTF-8')
        die_on_error = self.config.get('die_on_error', True)
        ignore_ns = self.config.get('ignore_ns', False)
        ignore_dtd = self.config.get('ignore_dtd', False)
        limit = self.config.get('limit', None)

        # Try to get schema from component level first, then fallback to config
        if hasattr(self, 'output_schema') and self.output_schema:
            output_schema = self.output_schema
        else:
            output_schema = self.config.get("schema", {}).get("output", [])

        logger.debug(f"[{self.id}] Output schema from config: {output_schema}")
        logger.debug(f"[{self.id}] Config keys: {list(self.config.keys())}")

        # Validate required parameters
        if not filepath:
            raise ValueError(f"Component {self.id}: XML file path not provided.")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Component {self.id}: XML file does not exist: {filepath}")

        logger.info(f"[{self.id}] Reading XML from: {filepath}")
        logger.debug(f"[{self.id}] Loop XPath: {loop_query}")

        # Determine processing mode
        explicit_mode = self.config.get('mode')
        if explicit_mode == 'xml_passthrough':
            mode = "xml_passthrough"
        elif len(output_schema) == 1:
            # Single column output suggests XMLMap workflow - use passthrough mode
            mode = "xml_passthrough"
        else:
            mode = "tabular"
        logger.info(f"[{self.id}] Processing mode: {mode} (explicit_mode: {explicit_mode})")

        try:
            if mode == "xml_passthrough":
                logger.info(f"[{self.id}] Processing started: XML passthrough mode")
                data = self._parse_xml_passthrough(filepath, encoding, ignore_ns, ignore_dtd, limit, output_schema)
                rows_out = len(data)
                logger.info(f"[{self.id}] Processing complete: {rows_out} XML elements extracted")
                self._update_stats(rows_out, rows_out, 0)
                return {'main': data}
            else:
                logger.info(f"[{self.id}] Processing started: tabular extraction mode")
                rows = self._parse_xml(
                    filepath=filepath,
                    loop_query=loop_query,
                    mapping=mapping,
                    output_schema=output_schema,
                )
                df = pd.DataFrame(rows)
                rows_out = len(df)
                logger.info(f"[{self.id}] Processing complete: {rows_out} rows extracted")
                logger.debug(f"[{self.id}] Columns: {list(df.columns)}")
                self._update_stats(rows_out, rows_out, 0)
                return {"main": df}

        except Exception as e:
            logger.error(f"[{self.id}] Failed to process XML file {filepath}: {str(e)}")
            if die_on_error:
                raise RuntimeError(f"Error processing XML file {filepath}: {str(e)}") from e
            else:
                logger.warning(f"[{self.id}] Returning empty result due to error (die_on_error=False)")
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

    # -------------------------------------------------------
    # MAIN PARSE FUNCTION (Talend-like behavior)
    # -------------------------------------------------------
    def _parse_xml(
        self,
        filepath: str,
        loop_query: str,
        mapping: List[Dict[str, str]],
        output_schema: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Parse XML file using Talend-like behavior with XPath expressions.

        Args:
            filepath: Path to XML file
            loop_query: XPath expression for loop elements
            mapping: Column to XPath mappings
            output_schema: Output schema definition

        Returns:
            List of dictionaries representing extracted rows
        """

        tree = ET.parse(filepath)
        root = tree.getroot()

        # Namespace detection
        nsmap = normalize_nsmaps(root)
        ns_prefix = list(nsmap.keys())[0] if nsmap else ""

        logger.debug(f"[{self.id}] Namespace map detected: {nsmap}")

        # Loop XPath qualification
        loop_query_clean = loop_query.strip().strip("'").strip('"')
        if loop_query_clean.startswith("/"):
            loop_query_clean = loop_query_clean[1:]
        # Get the local name of the root element (without namespace)
        root_tag = root.tag
        if '}' in root_tag:
            root_local = root_tag.split('}', 1)[1]
        else:
            root_local = root_tag

        # If the XPath starts with the root element, remove it
        if loop_query_clean.startswith(f"{root_local}/"):
            loop_query_clean = loop_query_clean[len(root_local) + 1:]
        if not loop_query_clean.startswith(".//"):
            loop_query_clean = ".//" + loop_query_clean
        # Remove the .// before qualifying, then add it back
        if loop_query_clean.startswith(".//"):
            base = ".//"
            loop_query_clean = loop_query_clean[3:]
        else:
            base = ""
        loop_xpath_q = base + qualify_xpath(loop_query_clean, ns_prefix)
        logger.debug(f"[{self.id}] Qualified loop XPath: {loop_xpath_q}")


        # Find loop nodes
        try:
            if ns_prefix:
                loop_nodes = root.findall(loop_xpath_q, namespaces=nsmap)
            else:
                loop_nodes = root.findall(loop_xpath_q)
        except Exception as e:
            logger.warning(f"[{self.id}] Failed to find loop nodes with XPath '{loop_xpath_q}': {e}")
            loop_nodes = []

        logger.info(f"[{self.id}] Loop nodes found: {len(loop_nodes)}")

        # Collect SCHEMA_COLUMN entries
        schema_xpaths = []
        logger.debug(f"[{self.id}] Raw mapping entries: {len(mapping)}")
        for i, m in enumerate(mapping):
            logger.debug(f"[{self.id}] Mapping {i}: column='{m.get('column')}', xpath='{m.get('xpath')}'")
        i = 0
        while i < len(mapping):
            if (i < len(mapping) and mapping[i].get("column") == "SCHEMA_COLUMN" and
                i+1 < len(mapping) and mapping[i+1].get("column") == "QUERY"):

                # Use the QUERY xpath instead of SCHEMA_COLUMN xpath
                xpath_raw = mapping[i+1].get("xpath", "")
                xpath_clean = xpath_raw.strip().strip("'").strip('"')
                schema_xpaths.append(xpath_clean)
                logger.debug(f"[{self.id}] Found QUERY xpath: '{xpath_raw}' -> cleaned: '{xpath_clean}'")
                i += 3  # Skip to next group (SCHEMA_COLUMN, QUERY, NODECHECK)
            else:
                i += 1

        # Create column order from schema list
        schema_order = [col["name"] for col in output_schema]
        logger.debug(f"[{self.id}] Schema order: {schema_order}")
        logger.debug(f"[{self.id}] Schema XPaths collected: {schema_xpaths}")
        logger.debug(f"[{self.id}] Schema order count: {len(schema_order)}, XPaths count: {len(schema_xpaths)}")

        rows: List[Dict[str, Any]] = []

        # ---------------------------------
        # Iterate through loop nodes
        # ---------------------------------
        for idx, node in enumerate(loop_nodes):
            logger.debug(f"[{self.id}] Processing loop node {idx}")
            row = {}

            for col_name, raw_xpath in zip(schema_order, schema_xpaths):
                logger.debug(f"[{self.id}] Processing column '{col_name}' with xpath '{raw_xpath}'")
                raw_xpath = raw_xpath.strip().strip("'").strip('"')

                # Handle parent navigation XPaths manually due to ElementTree limitation
                if raw_xpath.startswith("../"):
                    logger.debug(f"[{self.id}] Using manual navigation for parent xpath: {raw_xpath}")
                    result = find_element_by_manual_navigation(node, raw_xpath, ns_prefix, nsmap, root)
                    logger.debug(f"[{self.id}] Manual navigation result for '{col_name}': {len(result)} nodes found")
                else:
                    expr_q = qualify_xpath(raw_xpath, ns_prefix)
                    logger.debug(f"[{self.id}] Qualified xpath: '{expr_q}'")
                    ctx = choose_context(expr_q, node, root)
                    logger.debug(f"[{self.id}] Context chosen: {ctx.tag if hasattr(ctx, 'tag') else 'unknown'}")

                    try:
                        if ns_prefix:
                            result = ctx.findall(expr_q, namespaces=nsmap)
                        else:
                            result = ctx.findall(expr_q)
                        logger.debug(f"[{self.id}] XPath result for '{col_name}': {len(result)} nodes found")
                        if result:
                            logger.debug(f"[{self.id}] First result node: {result[0].tag if hasattr(result[0], 'tag') else 'not element'}")
                    except Exception as e:
                        result = []
                        logger.debug(f"[{self.id}] XPath error for '{col_name}': {e}")

                val = extract_value(result)
                logger.debug(f"[{self.id}] Extracted value for '{col_name}': '{val}'")
                row[col_name] = val

            rows.append(row)
            logger.debug(f"[{self.id}] Row {idx} completed: {row}")

        return rows


    def _parse_xml_passthrough(self, filepath: str, encoding: str, ignore_ns: bool, ignore_dtd: bool, limit: Optional[int], output_schema: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Parse the XML file and return raw XML content for XMLMap processing.

        Args:
            filepath: Path to XML file
            encoding: File encoding
            ignore_ns: Whether to ignore namespaces
            ignore_dtd: Whether to ignore DTD
            limit: Maximum number of elements to process
            output_schema: Output schema definition

        Returns:
            DataFrame with raw XML content
        """
        import xml.etree.ElementTree as ET

        # Parse XML file
        parser = ET.XMLParser(encoding=encoding)
        if ignore_dtd:
            parser.entity = {}

        tree = ET.parse(filepath, parser=parser)
        root = tree.getroot()

        logger.debug(f"[{self.id}] Parsed root tag: {root.tag}")

        # For XMLMap workflows, we want to pass the entire XML content as a single string
        # Get the full XML content
        with open(filepath, 'r', encoding=encoding) as f:
            xml_content = f.read()

        logger.info(f"[{self.id}] XML content length: {len(xml_content)} characters")

        # Create a single row with the XML content
        # Use the column name from the output schema
        col_name = output_schema[0]["name"] if output_schema else "xml_content"
        rows = [{col_name: xml_content}]

        logger.debug(f"[{self.id}] Created 1 row with XML content")
        return pd.DataFrame(rows)
