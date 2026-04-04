"""Converter for Talend tFileTouch component.

Creates empty files or touches existing files to update timestamps.

Config mapping (2 params + framework):
  FILENAME   -> filename   (str, default "")
  CREATEDIR  -> createdir  (bool, default False)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileTouch")
class FileTouchConverter(ComponentConverter):
    """Convert Talend tFileTouch to v1 engine config."""

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
        config["createdir"] = self._get_bool(node, "CREATEDIR", False)

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema ----
        # Utility component -- no data flow schema
        schema = {"input": [], "output": []}

        # ---- 7. Engine gap needs_review entries ----
        needs_review.append({
            "issue": "Engine reads 'create_directory' but converter outputs 'createdir' per _java.xml param name CREATEDIR",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileTouch",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
