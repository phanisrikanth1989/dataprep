"""Converter for Talend tFileProperties component.

Extracts file metadata properties (path, size, modification time, MD5 hash).
Utility component with read-only predefined schema -- no data flow schema.

Config mapping (4 params total):
  FILENAME           -> filename           (str, default "")
  MD5                -> md5                (bool, default False)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileProperties")
class FilePropertiesConverter(ComponentConverter):
    """Convert Talend tFileProperties to v1 engine config."""

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
        config["md5"] = self._get_bool(node, "MD5", False)

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Schema (utility component -- no data flow) ----
        schema = {"input": [], "output": []}

        # ---- 4. Engine gap needs_review entries ----
        needs_review.append({
            "issue": "Engine reads 'FILENAME' (uppercase) but converter sends 'filename' (snake_case per D-38) -- config key mismatch",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        needs_review.append({
            "issue": "Engine reads 'MD5' (uppercase) but converter sends 'md5' (snake_case per D-38) -- config key mismatch",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 5. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileProperties",
            config=config,
            schema=schema,
        )

        # ---- 6. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
