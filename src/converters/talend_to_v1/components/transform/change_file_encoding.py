"""Converter for Talend tChangeFileEncoding component.

Re-encodes a file from one character encoding to another. Operates on file
paths rather than data flow rows, so the schema is always empty (utility).

Config mapping (7 unique + 2 framework = 9 total):
  USE_INENCODING     -> use_inencoding     (bool, default False)
  INENCODING         -> inencoding         (str, default "ISO-8859-15")
  INFILE_NAME        -> infile_name        (str, default "")
  OUTFILE_NAME       -> outfile_name       (str, default "")
  ENCODING           -> encoding           (str, default "ISO-8859-15")
  BUFFERSIZE         -> buffersize         (str, default "8192")
  CREATE             -> create             (bool, default True)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

No v1 engine implementation exists -- single consolidated needs_review per D-84/D-27.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tChangeFileEncoding")
class ChangeFileEncodingConverter(ComponentConverter):
    """Convert Talend tChangeFileEncoding to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        """Convert a TalendNode into a v1 tChangeFileEncoding component dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["use_inencoding"] = self._get_bool(node, "USE_INENCODING", False)
        config["inencoding"] = self._get_str(node, "INENCODING", "ISO-8859-15")
        config["infile_name"] = self._get_str(node, "INFILE_NAME", "")
        config["outfile_name"] = self._get_str(node, "OUTFILE_NAME", "")
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["buffersize"] = self._get_str(node, "BUFFERSIZE", "8192")
        config["create"] = self._get_bool(node, "CREATE", True)

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema (utility component: no data flow) ----
        schema = {"input": [], "output": []}

        # ---- 7. Engine gap needs_review (single consolidated per D-84/D-27) ----
        needs_review.append({
            "issue": (
                "No v1 engine implementation exists for tChangeFileEncoding. "
                "Converter output is syntactically valid but cannot execute at runtime."
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tChangeFileEncoding",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
