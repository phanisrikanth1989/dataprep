"""Converter for Talend tFileUnarchive -> v1 FileUnarchiveComponent.

Maps tFileUnarchive parameters to the v1 engine representation, including
zip file path, extraction directory, optional password protection, and
error handling settings.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileUnarchive")
class FileUnarchiveConverter(ComponentConverter):
    """Convert a Talend tFileUnarchive node into a v1 FileUnarchiveComponent."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # --- Extract config parameters ---
        zipfile = self._get_str(node, "ZIPFILE")
        directory = self._get_str(node, "DIRECTORY")
        extract_path = self._get_bool(node, "EXTRACTPATH", False)
        need_password = self._get_bool(node, "CHECKPASSWORD")
        password = self._get_str(node, "PASSWORD")
        die_on_error = self._get_bool(node, "DIE_ON_ERROR")

        # --- Validation warnings ---
        if not zipfile:
            warnings.append("ZIPFILE is empty — this is a required parameter")
        if not directory:
            warnings.append("DIRECTORY is empty — this is a required parameter")
        if need_password and not password:
            warnings.append(
                "need_password is true but PASSWORD is empty"
            )

        # --- Build config dict ---
        config: Dict[str, Any] = {
            "zipfile": zipfile,
            "directory": directory,
            "extract_path": extract_path,
            "need_password": need_password,
            "password": password,
            "die_on_error": die_on_error,
            # New params
            "rootname": self._get_bool(node, "ROOTNAME", False),
            "integrity": self._get_bool(node, "INTEGRITY", False),
            "decrypt_type": self._get_str(node, "DECRYPT_METHOD"),
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
        }

        # --- Engine-gap warnings ---
        if config["integrity"]:
            warnings.append(
                "INTEGRITY=true: engine does not check archive integrity "
                "before extraction"
            )
        if config["rootname"]:
            warnings.append(
                "ROOTNAME=true: engine does not create archive-named "
                "subdirectory during extraction"
            )
        if config["decrypt_type"]:
            warnings.append(
                f"DECRYPT_METHOD={config['decrypt_type']}: engine only supports "
                "basic zipfile password, not Zip4j"
            )

        component = self._build_component_dict(
            node=node,
            type_name="FileUnarchiveComponent",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
