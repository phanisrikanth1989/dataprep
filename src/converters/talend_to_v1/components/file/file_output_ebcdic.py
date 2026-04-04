"""Converter for Talend tFileOutputEBCDIC component.

Writes data to files using EBCDIC encoding (mainframe character sets).
Enterprise-only component -- _java.xml NOT available in open-source Talaxie repository.
Params are LOW confidence (extracted from existing converter code and Talend domain knowledge).

Config mapping (7 params total):
  FILENAME           -> filename           (str, default "")
  ENCODING           -> encoding           (str, default "Cp1047")  # EBCDIC codepage
  APPEND             -> append             (bool, default False)
  ROWSEPARATOR       -> rowseparator       (str, default "\\n")
  DIE_ON_ERROR       -> die_on_error       (bool, default False)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileOutputEBCDIC")
class FileOutputEbcdicConverter(ComponentConverter):
    """Convert Talend tFileOutputEBCDIC to v1 engine config."""

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
        config["encoding"] = self._get_str(node, "ENCODING", "Cp1047")
        config["append"] = self._get_bool(node, "APPEND", False)
        config["rowseparator"] = self._get_str(node, "ROWSEPARATOR", "\\n")
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Schema (SINK per D-55) ----
        schema = {"input": self._parse_schema(node), "output": []}

        # ---- 4. Engine gap needs_review entries ----
        # Single consolidated needs_review per D-51 (no engine)
        needs_review.append({
            "issue": (
                "No v1 engine implementation exists for tFileOutputEBCDIC. "
                "All converter output keys are informational only and cannot "
                "be consumed by the engine."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 5. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tFileOutputEBCDIC",  # D-43: no-engine uses Talend name
            config=config,
            schema=schema,
        )

        # ---- 6. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
