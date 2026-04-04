"""Converter for Talend tJavaRow component.

Executes user-defined Java code on each row within the ETL pipeline.

Config mapping (3 unique params + converter-generated + framework):
  CODE    -> java_code      (str, MEMO_JAVA, default "")
  IMPORT  -> imports         (str, MEMO_IMPORT, default "")
  SCHEMA  -> output_schema  (list, converter-generated from schema columns for engine)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: DIE_ON_ERROR (not in _java.xml)

Engine reads: java_code, output_schema from config.
Engine does NOT read: imports (engine_gap).
output_schema is not from _java.xml -- it is converter-generated for engine compatibility.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tJavaRow")
class JavaRowComponentConverter(ComponentConverter):
    """Convert Talend tJavaRow to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core MEMO parameters (via _get_param per Pitfall 6) ----
        config: Dict[str, Any] = {}
        config["java_code"] = self._get_param(node, "CODE", "")
        config["imports"] = self._get_param(node, "IMPORT", "")

        # ---- 2. Converter-generated output_schema for engine compatibility ----
        schema_cols = self._parse_schema(node)
        output_schema: List[Dict[str, str]] = []
        for col in schema_cols:
            output_schema.append({"name": col["name"], "type": col["type"]})
        config["output_schema"] = output_schema

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Schema (passthrough: input == output) ----
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 5. Engine gap needs_review entries ----
        _engine_gap_keys = [
            ("imports", "engine does not read 'imports' from config"),
            ("output_schema", "output_schema is converter-generated for engine compatibility, not from _java.xml"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine gap for '{key}' -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 6. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="JavaRowComponent",
            config=config,
            schema=schema,
        )

        # ---- 7. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
