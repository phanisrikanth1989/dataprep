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
        # Engine expects extract_path as bool (preserve directory structure)
        extract_path = self._get_bool(node, "EXTRACTPATH", True)
        check_password = self._get_bool(node, "CHECKPASSWORD")
        password = self._get_str(node, "PASSWORD")
        die_on_error = self._get_bool(node, "DIE_ON_ERROR")

        # --- Validation warnings ---
        if not zipfile:
            warnings.append("ZIPFILE is empty — this is a required parameter")
        if not directory:
            warnings.append("DIRECTORY is empty — this is a required parameter")
        if check_password and not password:
            warnings.append(
                "CHECKPASSWORD is true but PASSWORD is empty"
            )

        # --- Build config dict ---
        config: Dict[str, Any] = {
            "zipfile": zipfile,
            "directory": directory,
            "extract_path": extract_path,
            "check_password": check_password,
            "password": password,
            "die_on_error": die_on_error,
        }

        component = self._build_component_dict(
            node=node,
            type_name="FileUnarchiveComponent",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
