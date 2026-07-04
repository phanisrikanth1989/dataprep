"""Converter for Talend tFileInputProperties component.

Reads Java .properties or .ini files as key/value pairs.

Config mapping (7 params total):
  FILE_FORMAT        -> file_format        (str/CLOSED_LIST, default "PROPERTIES_FORMAT")
  RETRIVE_MODE       -> retrive_mode       (str/CLOSED_LIST, default "RETRIVE_BY_SECTION")
  SECTION_NAME       -> section_name       (str, default "section")
  FILENAME           -> filename           (str, default "")
  ENCODING           -> encoding           (str, default "ISO-8859-15")
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY
from ...expression_converter import ExpressionConverter

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputProperties")
class FileInputPropertiesConverter(ComponentConverter):
    """Convert Talend tFileInputProperties to v1 engine config."""

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
        config["file_format"] = self._get_str(node, "FILE_FORMAT", "PROPERTIES_FORMAT")
        config["retrive_mode"] = self._get_str(node, "RETRIVE_MODE", "RETRIVE_BY_SECTION")
        config["section_name"] = self._get_str(node, "SECTION_NAME", "section")
        config["filename"] = ExpressionConverter.mark_java_expression(
            self._get_str(node, "FILENAME", "")
        )
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Schema ----
        schema = {"input": [], "output": self._parse_schema(node)}

        # ---- 4. Engine gap needs_review entries ----
        # Single consolidated needs_review per D-37 (no engine)
        needs_review.append({
            "issue": "No v1 engine implementation exists for tFileInputProperties. All config keys are extracted for future engine support.",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 5. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tFileInputProperties",  # D-43: no-engine uses Talend name
            config=config,
            schema=schema,
        )

        # ---- 6. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
