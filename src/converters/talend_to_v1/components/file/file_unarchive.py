"""Converter for Talend tFileUnarchive component.

Extracts files or directories from an archive (ZIP, tar.gz, tgz, tar, gz).

Config mapping (12 unique params + framework):
  ZIPFILE        -> zipfile        (str, default "")
  DIRECTORY      -> directory      (str, default "")
  ROOTNAME       -> rootname       (bool, default False)
  INTEGRITY      -> integrity      (bool, default False)
  EXTRACTPATH    -> extractpath    (bool, default True)
  CHECKPASSWORD  -> checkpassword  (bool, default False)
  DECRYPT_METHOD -> decrypt_method (str, default "ZIP4J_DECRYPT")
  PASSWORD       -> password       (str, default "")
  DIE_ON_ERROR   -> die_on_error   (bool, default False)
  PRINTOUT       -> printout       (bool, default False)
  USE_ENCODING   -> use_encoding   (bool, default False)
  ENCORDING      -> encording      (str, default "UTF-8")  # Talend's typo preserved
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileUnarchive")
class FileUnarchiveConverter(ComponentConverter):
    """Convert Talend tFileUnarchive to v1 engine config."""

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
        config["zipfile"] = self._get_str(node, "ZIPFILE", "")
        config["directory"] = self._get_str(node, "DIRECTORY", "")
        config["rootname"] = self._get_bool(node, "ROOTNAME", False)
        config["integrity"] = self._get_bool(node, "INTEGRITY", False)
        config["extractpath"] = self._get_bool(node, "EXTRACTPATH", True)  # CRITICAL: default True per _java.xml
        config["checkpassword"] = self._get_bool(node, "CHECKPASSWORD", False)
        config["decrypt_method"] = self._get_str(node, "DECRYPT_METHOD", "ZIP4J_DECRYPT")
        config["password"] = self._get_str(node, "PASSWORD", "")
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)

        # ---- 2. Advanced parameters ----
        config["printout"] = self._get_bool(node, "PRINTOUT", False)
        config["use_encoding"] = self._get_bool(node, "USE_ENCODING", False)
        config["encording"] = self._get_str(node, "ENCORDING", "UTF-8")  # Talend's typo preserved

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema ----
        # Utility component -- no data flow schema
        schema = {"input": [], "output": []}

        # ---- 7. Engine gap needs_review entries ----
        needs_review.append({
            "issue": "Engine reads 'extract_path' but converter outputs 'extractpath' per _java.xml param name EXTRACTPATH",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        needs_review.append({
            "issue": "Engine reads 'check_password' but converter outputs 'checkpassword' per _java.xml param name CHECKPASSWORD",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileUnarchiveComponent",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
