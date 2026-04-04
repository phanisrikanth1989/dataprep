"""Converter for Talend tJava component.

Executes user-defined Java code within the ETL pipeline.

Config mapping (2 unique params + framework):
  CODE    -> java_code  (str, MEMO_JAVA, default "")
  IMPORT  -> imports    (str, MEMO_IMPORT, default "")
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: DIE_ON_ERROR (not in _java.xml)

Engine reads: java_code from config.
Engine does NOT read: imports (engine_gap).
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tJava")
class JavaComponentConverter(ComponentConverter):
    """Convert Talend tJava to v1 engine config."""

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
        config["java_code"] = self._get_param(node, "CODE", "")
        config["imports"] = self._get_param(node, "IMPORT", "")

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Schema (passthrough for transform) ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 4. Engine gap needs_review entries ----
        needs_review.append({
            "issue": "Engine does not read 'imports' config key -- JavaComponent only reads 'java_code'",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 5. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="JavaComponent",
            config=config,
            schema=schema,
        )

        # ---- 6. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
