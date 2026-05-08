"""FileInputMSXML engine component.

Talend equivalent: tFileInputMSXML

Reads an XML file and extracts rows by applying a root XPath loop query and
mapping child element text to output schema columns by column name.

Threshold-switched I/O via _xml_io; parser construction centralized;
recover=False (fix-source policy -- malformed XML routes to REJECT instead
of returning a silently recovered partial tree).

Config keys (all resolved by BaseComponent before _process is called):
    filename                  (str, required)              -- path to XML file
    root_loop_query           (str, required)              -- XPath selecting repeated elements
    encoding                  (str, default "ISO-8859-15") -- file encoding
    die_on_error              (bool, default False)        -- raise on node error vs REJECT
    trim_all                  (bool, default True)         -- strip whitespace from all values
    ignore_dtd                (bool, default False)        -- ignore DTD during parsing
    ignore_order              (bool, default False)        -- ignore element order (informational)
    check_date                (bool, default False)        -- validate date columns (stub)
    generation_mode           (str, default "DOM4J")       -- CLOSED_LIST (informational)
    schemas                   (list, default [])           -- sub-schema table (advanced)
    xml_streaming_threshold_mb (int, default 50)           -- DOM vs streaming size boundary (MB)
    tstatcatcher_stats        (bool, default False)        -- framework
    label                     (str, default "")            -- framework

GlobalMap variables set:
    NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()

Known limitation: multi-schema SCHEMAS TABLE with streaming path is not supported.
When the SCHEMAS table has more than one entry and the file exceeds the threshold,
the component logs a warning and falls back to DOM. Single-schema streaming is
fully supported.
"""
import logging
import os
from typing import Any, Dict, Optional

import pandas as pd
from lxml import etree

from . import _xml_io
from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)


@REGISTRY.register("FileInputMSXML", "tFileInputMSXML")
class FileInputMSXML(BaseComponent):
    """Reads an XML file and produces rows by XPath loop extraction.

    The ``root_loop_query`` XPath selects repeated elements (the rows).
    For each element, output schema columns are populated by looking for
    child elements whose tag name matches the column name (case-sensitive).
    When ``trim_all=True``, all extracted string values are stripped.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Check key presence and container types only (Rule 12)."""
        if not self.config.get("filename"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'filename'"
            )
        if not self.config.get("root_loop_query"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'root_loop_query'"
            )
        for bool_key, default in (
            ("die_on_error", False),
            ("trim_all", True),
            ("ignore_dtd", False),
            ("ignore_order", False),
        ):
            val = self.config.get(bool_key, default)
            if not isinstance(val, bool):
                raise ConfigurationError(
                    f"[{self.id}] Config '{bool_key}' must be a boolean"
                )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Read XML file and extract rows.

        Args:
            input_data: Not used -- this is a file source component.

        Returns:
            Dict with ``main`` (extracted rows DataFrame) and
            ``reject`` (failed node rows DataFrame).
        """
        filepath = str(self.config.get("filename", "")).strip()
        root_loop_query = str(self.config.get("root_loop_query", "")).strip()
        encoding = str(self.config.get("encoding", "ISO-8859-15")).strip() or "ISO-8859-15"
        die_on_error = self.config.get("die_on_error", False)
        trim_all = self.config.get("trim_all", True)
        ignore_dtd = self.config.get("ignore_dtd", False)

        # Content checks (Rule 12: deferred to _process)
        if not filepath:
            raise FileOperationError(
                f"[{self.id}] Config 'filename' is empty"
            )
        if not os.path.exists(filepath):
            raise FileOperationError(
                f"[{self.id}] File not found: {filepath!r}"
            )

        # ---- output schema column names ----
        output_schema = getattr(self, "output_schema", None) or []
        col_names = [c["name"] for c in output_schema]

        # ---- threshold-switched parse: delegate to _xml_io ----
        threshold_mb = int(self.config.get("xml_streaming_threshold_mb", 50))
        size_mb = os.stat(filepath).st_size / (1024 * 1024)

        schemas = self.config.get("schemas", [])
        multi_schema = len(schemas) > 1

        # Streaming path requires a single loop tag extracted from the
        # root_loop_query. Multi-schema jobs declare multiple loop paths
        # and require the full DOM; fall back with a warning.
        if multi_schema:
            logger.warning(
                "[%s] Multiple SCHEMAS entries -- streaming path not supported; using DOM",
                self.id,
            )

        try:
            strategy, parsed = _xml_io.parse_xml_strategy(filepath, threshold_mb)
        except etree.XMLSyntaxError as exc:
            if die_on_error:
                raise FileOperationError(
                    f"[{self.id}] XML parse failed: {exc}"
                ) from exc
            reject_df = pd.DataFrame(
                [{"errorCode": "PARSE_ERROR", "errorMessage": str(exc)}]
            )
            self._update_stats(1, 0, 1)
            return {"main": pd.DataFrame(columns=col_names), "reject": reject_df}
        except (FileNotFoundError, OSError) as exc:
            raise FileOperationError(
                f"[{self.id}] Failed to read XML file {filepath!r}: {exc}"
            ) from exc

        _xml_io.log_strategy(self.id, strategy, size_mb, threshold_mb)

        if strategy == "dom" or multi_schema:
            # DOM path: parsed is etree._ElementTree
            if multi_schema and strategy == "stream":
                # Re-parse with DOM for multi-schema fallback
                try:
                    parsed = etree.parse(filepath, parser=_xml_io.secure_xml_parser())
                except etree.XMLSyntaxError as exc:
                    if die_on_error:
                        raise FileOperationError(
                            f"[{self.id}] XML parse failed: {exc}"
                        ) from exc
                    reject_df = pd.DataFrame(
                        [{"errorCode": "PARSE_ERROR", "errorMessage": str(exc)}]
                    )
                    self._update_stats(1, 0, 1)
                    return {"main": pd.DataFrame(columns=col_names), "reject": reject_df}
            try:
                root = parsed.getroot()
            except Exception as exc:
                raise FileOperationError(
                    f"[{self.id}] Failed to get XML root: {exc}"
                ) from exc
        else:
            # Streaming path: single-schema, file above threshold.
            # Extract the last path segment from root_loop_query as the loop tag.
            loop_tag = root_loop_query.rstrip("/").split("/")[-1]
            # Collect rows via iterparse; elements are cleared after yield
            # so all data must be consumed before advancing the generator.
            main_rows = []
            reject_rows = []
            for element in _xml_io.iterparse_loop_query(filepath, loop_tag):
                try:
                    out_row: dict = {}
                    for col_name in col_names:
                        children = element.findall(col_name)
                        if children:
                            text = children[0].text or ""
                        else:
                            result = element.xpath(f"./{col_name}/text()")
                            text = result[0] if result else ""
                        if trim_all and isinstance(text, str):
                            text = text.strip()
                        out_row[col_name] = text if text != "" else None
                    main_rows.append(out_row)
                except Exception as exc:
                    logger.warning("[%s] Node extraction failed (stream): %s", self.id, exc)
                    if die_on_error:
                        raise FileOperationError(
                            f"[{self.id}] Node extraction failed: {exc}"
                        ) from exc
                    reject_rows.append({"errorCode": "NODE_ERROR", "errorMessage": str(exc)})
            main_df = (
                pd.DataFrame(main_rows, columns=col_names)
                if main_rows
                else pd.DataFrame(columns=col_names)
            )
            reject_df = pd.DataFrame(reject_rows) if reject_rows else pd.DataFrame()
            rows_total = len(main_df) + len(reject_df)
            self._update_stats(rows_total, len(main_df), len(reject_df))
            logger.info(
                "[%s] done: file=%r ok=%d reject=%d",
                self.id,
                filepath,
                len(main_df),
                len(reject_df),
            )
            return {"main": main_df, "reject": reject_df}

        try:
            nodes = root.xpath(root_loop_query)
        except etree.XPathError as exc:
            raise FileOperationError(
                f"[{self.id}] Invalid root_loop_query {root_loop_query!r}: {exc}"
            ) from exc

        if not isinstance(nodes, list):
            nodes = [nodes] if nodes is not None else []

        main_rows: list = []
        reject_rows: list = []
        # (DOM path -- streaming path returns early above)

        for node in nodes:
            try:
                out_row: dict = {}
                for col_name in col_names:
                    # Try direct child tag match first
                    children = node.findall(col_name)
                    if children:
                        text = children[0].text or ""
                    else:
                        result = node.xpath(f"./{col_name}/text()")
                        text = result[0] if result else ""
                    if trim_all and isinstance(text, str):
                        text = text.strip()
                    out_row[col_name] = text if text != "" else None
                main_rows.append(out_row)
            except Exception as exc:
                logger.warning("[%s] Node extraction failed: %s", self.id, exc)
                if die_on_error:
                    raise FileOperationError(
                        f"[{self.id}] Node extraction failed: {exc}"
                    ) from exc
                reject_rows.append({"errorCode": "NODE_ERROR", "errorMessage": str(exc)})

        main_df = (
            pd.DataFrame(main_rows, columns=col_names)
            if main_rows
            else pd.DataFrame(columns=col_names)
        )
        reject_df = pd.DataFrame(reject_rows) if reject_rows else pd.DataFrame()

        rows_total = len(main_df) + len(reject_df)
        self._update_stats(rows_total, len(main_df), len(reject_df))
        logger.info(
            "[%s] done: file=%r ok=%d reject=%d",
            self.id,
            filepath,
            len(main_df),
            len(reject_df),
        )
        return {"main": main_df, "reject": reject_df}
