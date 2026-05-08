"""tFileInputXML engine component.

Reads an XML file, applies a LOOP_QUERY XPath to identify repeating elements,
extracts MAPPING-defined columns per element, and returns a DataFrame.

Threshold-switched I/O (D-C2): files below xml_streaming_threshold_mb load via
DOM (etree.parse), files at/above stream via etree.iterparse with element
clearing. Secure parser flags (XXE / billion-laughs / no-network) per D-C4.
Per-element MAPPING evaluation with REJECT routing for failures (ENG-FIX-002).

Audit items closed:
    ENG-FIX-002: REJECT flow (reject_df with errorCode + errorMessage)
    ENG-FIX-003: Threshold-switched I/O via _xml_io helpers
    ENG-FIX-004: Namespace per-element walk (P-5 root-only bug)
    ENG-FIX-005: Explicit per-column dict, no silent zip() data loss
    ENG-FIX-006: Encoding honored via lxml XML decl handling
    ENG-FIX-007: LIMIT enforced (empty=unlimited, "0"=zero, N=cap)
    ENG-FIX-008: Bare @attr XPath on loop element resolved correctly
    STD-FIX-001: ConfigurationError / FileOperationError, no RuntimeError
    NEW-XML-001: lxml only, zero stdlib xml.etree references
    NEW-XML-002: Secure parser via _xml_io.secure_xml_parser()
    TEST-FIX-001: Companion test file test_file_input_xml.py
"""
import logging
import os
import re
from typing import Any, Dict, Iterator, List, Optional

import pandas as pd
from lxml import etree

from . import _xml_io
from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)


@REGISTRY.register("FileInputXML", "tFileInputXML")
class FileInputXML(BaseComponent):
    """Read XML file -> DataFrame; threshold-switched DOM/streaming.

    Config keys (after converter mapping):
        filename (str): Path to the XML file.  Required.
        loop_query (str): XPath expression identifying the repeating element.  Required.
        mapping (list[dict]): Each entry has keys ``column`` (str), ``xpath`` (str),
            and optionally ``nodecheck`` (bool).
        limit (str): Row cap.  ``""`` = unlimited, ``"0"`` = no rows, ``"N"`` = cap at N.
        die_on_error (bool): Raise on failures.  Default False.
        encoding (str): XML encoding hint.  Default "ISO-8859-15".
        generation_mode (str): "DOM4J" or "SAX".  SAX is subsumed by threshold.
        ignore_ns (bool): Strip namespace prefixes from XPath.  Default False.
        ignore_dtd (bool): Ignore DTD declarations.  Default False.
        xml_streaming_threshold_mb (int): Size boundary.  Default 50.
        advanced_separator (bool): Enable advanced separators.  Default False.
        check_date (bool): Enable date checking.  Default False.
        use_separator (bool): Use separators.  Default False.
    """

    # ---- Error code constants (S-3 reject schema) ----
    _ERR_FILE_MISSING = "FILE_MISSING"
    _ERR_PARSE = "PARSE_ERROR"
    _ERR_XPATH = "XPATH_ERROR"
    _ERR_NODECHECK = "NODECHECK_FAIL"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Rule 12: presence + type checks only; content/file checks deferred to _process.

        Raises:
            ConfigurationError: If required keys are missing or typed incorrectly.
        """
        if not self.config.get("filename"):
            raise ConfigurationError(
                "[%s] Missing required config key 'filename'" % self.id
            )
        if not self.config.get("loop_query"):
            raise ConfigurationError(
                "[%s] Missing required config key 'loop_query'" % self.id
            )
        _bool_keys = (
            ("die_on_error", False),
            ("ignore_ns", False),
            ("ignore_dtd", False),
            ("advanced_separator", False),
            ("check_date", False),
            ("use_separator", False),
        )
        for bool_key, default in _bool_keys:
            val = self.config.get(bool_key, default)
            if not isinstance(val, bool):
                raise ConfigurationError(
                    "[%s] Config '%s' must be a boolean, got %r"
                    % (self.id, bool_key, type(val).__name__)
                )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Extract rows from an XML file.

        Args:
            input_data: Unused (source component).

        Returns:
            dict with keys ``main`` (DataFrame) and ``reject`` (DataFrame).

        Raises:
            ConfigurationError: If LIMIT value is not parseable.
            FileOperationError: If die_on_error=True and a file/parse/XPath error occurs.
        """
        filepath = self.config["filename"]
        loop_query = self.config["loop_query"]
        mapping = self.config.get("mapping") or []
        limit_raw = self.config.get("limit", "")
        die_on_error = self.config.get("die_on_error", False)
        ignore_ns = self.config.get("ignore_ns", False)
        threshold_mb = int(self.config.get("xml_streaming_threshold_mb", 50))

        # ---- LIMIT resolution (ENG-FIX-007) ----
        # ""  / None  -> unlimited (None)
        # "0"         -> 0 rows
        # "N"         -> cap at N rows
        limit: Optional[int]
        if limit_raw == "" or limit_raw is None:
            limit = None
        else:
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                raise ConfigurationError(
                    "[%s] LIMIT must be empty or a non-negative integer; got %r"
                    % (self.id, limit_raw)
                )

        # ---- File existence check (Rule 12: deferred from _validate_config) ----
        if not os.path.exists(filepath):
            if die_on_error:
                raise FileOperationError(
                    "[%s] XML file not found: %r" % (self.id, filepath)
                )
            return self._build_reject_only(
                self._ERR_FILE_MISSING, "file not found: %r" % filepath
            )

        # ---- Strategy decision + log (Pitfall P-4) ----
        size_mb = os.stat(filepath).st_size / (1024 * 1024)
        try:
            strategy, parsed = _xml_io.parse_xml_strategy(filepath, threshold_mb)
        except etree.XMLSyntaxError as exc:
            if die_on_error:
                raise FileOperationError(
                    "[%s] XML parse failed: %s" % (self.id, exc)
                ) from exc
            return self._build_reject_only(self._ERR_PARSE, str(exc))
        _xml_io.log_strategy(self.id, strategy, size_mb, threshold_mb)

        main_rows: List[Dict[str, Any]] = []
        reject_rows: List[Dict[str, Any]] = []

        if strategy == "dom":
            tree = parsed  # etree._ElementTree
            root = tree.getroot()
            # Pitfall P-5: walk descendants, not just root.nsmap
            nsmap = self._build_nsmap(root, ignore_ns)
            loop_xpath = self._normalize_loop_query(loop_query, ignore_ns)
            try:
                nodes = root.xpath(loop_xpath, namespaces=nsmap)
            except etree.XPathEvalError as exc:
                if die_on_error:
                    raise FileOperationError(
                        "[%s] LOOP_QUERY XPath invalid %r: %s" % (self.id, loop_query, exc)
                    ) from exc
                return self._build_reject_only(
                    self._ERR_XPATH, "loop_query: %s" % exc
                )
            for idx, node in enumerate(nodes):
                if limit is not None and idx >= limit:
                    break
                self._extract_node(
                    node, mapping, nsmap, main_rows, reject_rows, die_on_error
                )
        else:
            # ---- Streaming path ----
            # Derive tag name: last segment of loop_query, strip leading slashes and @
            loop_tag = loop_query.rstrip("/").split("/")[-1]
            # P-7: use removeprefix, not lstrip
            loop_tag = loop_tag.removeprefix("@")
            idx = 0
            for node in _xml_io.iterparse_loop_query(filepath, loop_tag):
                if limit is not None and idx >= limit:
                    break
                nsmap = self._build_nsmap(node, ignore_ns)
                self._extract_node(
                    node, mapping, nsmap, main_rows, reject_rows, die_on_error
                )
                idx += 1

        col_names = [m["column"] for m in mapping] if mapping else []
        main_df = (
            pd.DataFrame(main_rows, columns=col_names)
            if main_rows
            else pd.DataFrame(columns=col_names)
        )
        reject_df = pd.DataFrame(reject_rows) if reject_rows else pd.DataFrame()
        total = len(main_df) + len(reject_df)
        self._update_stats(total, len(main_df), len(reject_df))
        logger.info(
            "[%s] done: file=%r ok=%d reject=%d strategy=%s",
            self.id,
            filepath,
            len(main_df),
            len(reject_df),
            strategy,
        )
        return {"main": main_df, "reject": reject_df}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_nsmap(self, element: Any, ignore_ns: bool) -> Dict[str, str]:
        """Build a prefix->URI map by walking this element and all its descendants.

        ENG-FIX-004 / Pitfall P-5: the old code read only root.nsmap, which misses
        namespace declarations on child elements in multi-namespace documents.
        lxml exposes per-element nsmap; we collect them across the tree.

        Args:
            element: lxml element to start walking from.
            ignore_ns: If True, return an empty map (caller uses no-ns XPaths).

        Returns:
            Merged prefix->URI map, or {} when ignore_ns is True.
        """
        if ignore_ns:
            return {}
        collected: Dict[str, str] = {}
        try:
            for el in element.iter():
                for k, v in (el.nsmap or {}).items():
                    # Skip the default namespace (None key) -- lxml XPath needs a prefix
                    if k and k not in collected:
                        collected[k] = v
        except Exception:
            pass
        return collected

    def _normalize_loop_query(self, query: str, ignore_ns: bool) -> str:
        """Apply ignore_ns transform: strip namespace prefixes from XPath if requested.

        When ignore_ns=True, replaces "/prefix:tag" segments with
        "/*[local-name()='tag']" -- the XPath 1.0 equivalent of Talend's IGNORE_NS flag.

        Args:
            query: Raw LOOP_QUERY string from config.
            ignore_ns: Whether to strip namespace prefixes.

        Returns:
            Transformed (or unchanged) XPath string.
        """
        if not ignore_ns:
            return query
        return re.sub(r"/(\w+):(\w+)", r"/*[local-name()='\2']", query)

    def _extract_node(
        self,
        node: Any,
        mapping: List[Dict[str, Any]],
        nsmap: Dict[str, str],
        main_rows: List[Dict[str, Any]],
        reject_rows: List[Dict[str, Any]],
        die_on_error: bool,
    ) -> None:
        """Evaluate MAPPING per node; route to main or reject.

        ENG-FIX-005: uses an explicit per-column dict so missing columns yield None
        instead of being silently dropped by zip().
        ENG-FIX-002: REJECT rows carry errorCode + errorMessage.

        Args:
            node: lxml element (the loop node).
            mapping: List of {column, xpath, nodecheck} dicts.
            nsmap: Namespace prefix map for XPath evaluation.
            main_rows: Accumulator for successfully extracted rows.
            reject_rows: Accumulator for rejected rows.
            die_on_error: If True, raise instead of appending to reject_rows.
        """
        out_row: Dict[str, Any] = {}
        for m in mapping:
            col = m["column"]
            xpath_expr = m.get("xpath") or ""
            nodecheck = m.get("nodecheck", False)
            try:
                value = self._eval_mapping_xpath(node, xpath_expr, nsmap)
            except etree.XPathEvalError as exc:
                if die_on_error:
                    raise FileOperationError(
                        "[%s] MAPPING XPath %r invalid: %s" % (self.id, xpath_expr, exc)
                    ) from exc
                reject_rows.append({
                    "errorCode": self._ERR_XPATH,
                    "errorMessage": "%s: %s" % (xpath_expr, exc),
                })
                return
            if nodecheck and (value is None or value == ""):
                reject_rows.append({
                    "errorCode": self._ERR_NODECHECK,
                    "errorMessage": (
                        "nodecheck failed for column %r xpath %r" % (col, xpath_expr)
                    ),
                })
                return
            # ENG-FIX-005: explicit None for empty; no zip() truncation
            out_row[col] = value if value != "" else None
        main_rows.append(out_row)

    def _eval_mapping_xpath(self, node: Any, expr: str, nsmap: Dict[str, str]) -> Any:
        """Evaluate one MAPPING xpath expression against a loop node.

        Supports three forms:
            - "" (empty): returns element text content.
            - "@attr": ENG-FIX-008 -- bare attribute shorthand on the loop element.
            - "child/path": standard XPath evaluated via lxml.

        Args:
            node: lxml element (the current loop node).
            expr: XPath expression from the mapping entry.
            nsmap: Namespace prefix map.

        Returns:
            Extracted string value, or "" when nothing matched.

        Raises:
            etree.XPathEvalError: If the XPath expression is syntactically invalid.
        """
        if not expr:
            # Default: take element text
            return node.text or ""
        # ENG-FIX-008: bare @attr means "attribute on the loop element"
        if expr.startswith("@"):
            return node.get(expr[1:]) or ""
        try:
            results = node.xpath(expr, namespaces=nsmap)
        except etree.XPathEvalError:
            raise
        if not results:
            return ""
        first = results[0]
        if hasattr(first, "text"):
            # Element node
            return first.text or ""
        # Smart result (string, number, boolean from XPath functions)
        return str(first)

    def _build_reject_only(self, code: str, msg: str) -> Dict[str, Any]:
        """Return a result dict with empty main and a single-row reject DataFrame.

        Used for whole-file failures (file not found, parse error).

        Args:
            code: errorCode string.
            msg: errorMessage string.

        Returns:
            dict with ``main`` as an empty DataFrame and ``reject`` with one row.
        """
        reject_df = pd.DataFrame([{"errorCode": code, "errorMessage": msg}])
        self._update_stats(1, 0, 1)
        return {"main": pd.DataFrame(), "reject": reject_df}
