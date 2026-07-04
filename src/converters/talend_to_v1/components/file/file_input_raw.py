"""Converter for Talend tFileInputRaw component.

Reads raw file content as a single field (string, bytearray, or stream).

Config mapping (8 params total):
  FILENAME           -> filename           (str, default "")
  AS_STRING          -> as_string          (bool, default True)
  AS_BYTEARRAY       -> as_bytearray       (bool, default False)
  AS_INPUTSTREAM     -> as_inputstream     (bool, default False)
  ENCODING           -> encoding           (str, default "ISO-8859-15")
  DIE_ON_ERROR       -> die_on_error       (bool, default False)
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


@REGISTRY.register("tFileInputRaw")
class FileInputRawConverter(ComponentConverter):
    """Convert Talend tFileInputRaw to v1 FileInputRaw config."""

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
        config["filename"] = ExpressionConverter.mark_java_expression(
            self._get_str(node, "FILENAME", "")
        )
        config["as_string"] = self._get_bool(node, "AS_STRING", True)
        config["as_bytearray"] = self._get_bool(node, "AS_BYTEARRAY", False)
        config["as_inputstream"] = self._get_bool(node, "AS_INPUTSTREAM", False)
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema ----
        schema = {"input": [], "output": self._parse_schema(node)}

        # ---- 7. Engine gap needs_review entries ----
        _engine_gap_keys = [
            ("as_bytearray", "always reads as string or binary based on as_string only"),
            ("as_inputstream", "no streaming cursor support; loads full file"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileInputRaw",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
