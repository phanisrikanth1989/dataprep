"""Converter for Talend tFileExist component.

tFileExist is a utility component that checks whether a file or directory
exists at a specified path. It has no data flow (FLOW MAX_INPUT=0, MAX_OUTPUT=0)
and sets EXISTS (boolean) and FILENAME (string) globalMap variables.

Config mapping (3 params total):
  FILE_NAME          -> file_name          (str, default "")
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileExist")
class FileExistConverter(ComponentConverter):
    """Convert Talend tFileExist to v1 engine config."""

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
        config["file_name"] = self._get_str(node, "FILE_NAME", "")

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Schema ----
        # Utility component -- no data flow schema
        schema = {"input": [], "output": []}

        # ---- 4. Engine gap needs_review entries ----
        needs_review.append({
            "issue": "Converter sends 'file_name' (D-38 snake_case of FILE_NAME) but engine reads 'file_path' -- config key mismatch",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 5. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileExistComponent",
            config=config,
            schema=schema,
        )

        # ---- 6. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
