"""FileInputMSXML engine component.

Talend equivalent: tFileInputMSXML

Reads an XML file and extracts rows by applying a root XPath loop query and
mapping child element text to output schema columns by column name.

Config keys (all resolved by BaseComponent before _process is called):
    filename         (str, required)              -- path to XML file
    root_loop_query  (str, required)              -- XPath selecting repeated elements
    encoding         (str, default "ISO-8859-15") -- file encoding
    die_on_error     (bool, default False)        -- raise on node error vs REJECT
    trim_all         (bool, default True)         -- strip whitespace from all values
    ignore_dtd       (bool, default False)        -- ignore DTD during parsing
    ignore_order     (bool, default False)        -- ignore element order (informational)
    check_date       (bool, default False)        -- validate date columns (stub)
    generation_mode  (str, default "DOM4J")       -- CLOSED_LIST (informational)
    schemas          (list, default [])           -- sub-schema table (advanced)
    tstatcatcher_stats (bool, default False)      -- framework
    label            (str, default "")           -- framework

GlobalMap variables set:
    NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()
"""
import logging
import os
from typing import Any, Dict, Optional

import pandas as pd
from lxml import etree

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

        try:
            parser = etree.XMLParser(
                load_dtd=not ignore_dtd,
                no_network=True,
                recover=True,
                encoding=encoding,
            )
            tree = etree.parse(filepath, parser=parser)
            root = tree.getroot()
        except Exception as exc:
            raise FileOperationError(
                f"[{self.id}] Failed to parse XML file {filepath!r}: {exc}"
            ) from exc

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
