"""Converter for Talend tFileRowCount component.

Counts the number of rows in a file. Utility component -- no data flow schema.

Config mapping (4 unique + framework):
  FILENAME         -> filename         (str, default "")
  ROWSEPARATOR     -> row_separator    (str, default "\\n")
  IGNORE_EMPTY_ROW -> ignore_empty_row (bool, default False)
  ENCODING         -> encoding         (str, default "ISO-8859-15")
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileRowCount")
class FileRowCountConverter(ComponentConverter):
    """Convert Talend tFileRowCount to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["filename"] = self._get_str(node, "FILENAME", "")
        config["row_separator"] = self._get_str(node, "ROWSEPARATOR", "\\n")
        config["ignore_empty_row"] = self._get_bool(node, "IGNORE_EMPTY_ROW", False)
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema ----
        # Utility component -- no data flow schema
        schema = {"input": [], "output": []}

        # ---- 7. Engine gap needs_review entries ----
        needs_review.append({
            "issue": "Engine encoding default is 'UTF-8' but _java.xml default is 'ISO-8859-15'",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileRowCount",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
