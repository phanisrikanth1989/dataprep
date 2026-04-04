"""Converter for Talend tFileInputFullRow component.

Reads each row of a file as a single string value. Each row becomes one output
record with a single column containing the full row text.

Config mapping (10 params total):
  FILENAME           -> filename           (str, default "")
  ROWSEPARATOR       -> row_separator      (str, default "\\n")
  HEADER             -> header_rows        (int, default 0)
  FOOTER             -> footer_rows        (int, default 0)
  LIMIT              -> limit              (str, default "")
  REMOVE_EMPTY_ROW   -> remove_empty_row   (bool, default True)
  ENCODING           -> encoding           (str, default "ISO-8859-15")
  RANDOM             -> random             (bool, default False)
  NB_RANDOM          -> nb_random          (int, default 10)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputFullRow")
class FileInputFullRowConverter(ComponentConverter):
    """Convert Talend tFileInputFullRow to v1 engine config."""

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
        config["header_rows"] = self._get_int(node, "HEADER", 0)
        config["footer_rows"] = self._get_int(node, "FOOTER", 0)
        config["limit"] = self._get_str(node, "LIMIT", "")
        config["remove_empty_row"] = self._get_bool(node, "REMOVE_EMPTY_ROW", True)
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["random"] = self._get_bool(node, "RANDOM", False)
        config["nb_random"] = self._get_int(node, "NB_RANDOM", 10)

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Warnings ----
        if not config["filename"]:
            warnings.append("FILENAME is empty -- this is a required parameter")

        # ---- 4. Schema ----
        schema_cols = self._parse_schema(node)
        schema = {"input": [], "output": schema_cols}

        # ---- 5. Engine gap needs_review entries (per D-36: per-feature) ----
        _engine_gap_keys = [
            ("header_rows", "engine does not support skipping header rows"),
            ("footer_rows", "engine does not support skipping footer rows"),
            ("random", "engine does not support random line extraction"),
            ("nb_random", "engine does not support random line count"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 6. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileInputFullRowComponent",
            config=config,
            schema=schema,
        )

        # ---- 7. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
