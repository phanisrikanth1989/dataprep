"""Converter for Talend tContextLoad component.

Loads context variables from an incoming flow or implicit context file.

Config mapping (14 params total):
  CONTEXTFILE            -> filepath (str, default "")  [implicit context load, not in _java.xml]
  FORMAT                 -> format (str, default "")  [implicit context load, not in _java.xml]
  FIELDSEPARATOR         -> delimiter (str, default ";")  [implicit context load, not in _java.xml]
  CSV_SEPARATOR          -> csv_separator (str, default ";")  [implicit context load, not in _java.xml]
  PRINT_OPERATIONS       -> print_operations (bool, default False)
  DIEONERROR             -> die_on_error (bool, default False)  [fallback: DIE_ON_ERROR]
  ERROR_IF_NOT_EXISTS    -> error_if_not_exists (bool, default True)  [implicit context load]
  DISABLE_ERROR          -> disable_error (bool, default False)
  DISABLE_WARNINGS       -> disable_warnings (bool, default True)
  DISABLE_INFO           -> disable_info (bool, default True)
  LOAD_NEW_VARIABLE      -> load_new_variable (str, default "WARNING")
  NOT_LOAD_OLD_VARIABLE  -> not_load_old_variable (str, default "WARNING")
  TSTATCATCHER_STATS     -> tstatcatcher_stats (bool, default False)
  LABEL                  -> label (str, default "")
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tContextLoad")
class ContextLoadConverter(ComponentConverter):
    """Convert Talend tContextLoad to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        """Convert a TalendNode into a v1 ContextLoad component dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters (implicit context load params) ----
        filepath = self._get_str(node, "CONTEXTFILE")
        fmt = self._get_str(node, "FORMAT")
        delimiter = self._get_str(node, "FIELDSEPARATOR", default=";")
        csv_separator = self._get_str(node, "CSV_SEPARATOR", default=";")

        # ---- 2. CLOSED_LIST parameters ----
        load_new_variable = self._get_str(node, "LOAD_NEW_VARIABLE", default="WARNING")
        not_load_old_variable = self._get_str(node, "NOT_LOAD_OLD_VARIABLE", default="WARNING")

        # ---- 3. CHECK parameters ----
        print_operations = self._get_bool(node, "PRINT_OPERATIONS")
        error_if_not_exists = self._get_bool(node, "ERROR_IF_NOT_EXISTS", default=True)
        disable_error = self._get_bool(node, "DISABLE_ERROR")
        disable_warnings = self._get_bool(node, "DISABLE_WARNINGS", default=True)
        disable_info = self._get_bool(node, "DISABLE_INFO", default=True)

        # _java.xml canonical name is DIEONERROR (no underscore); .item exports may use DIE_ON_ERROR
        die_on_error = self._get_bool(node, "DIEONERROR")
        if not die_on_error and "DIEONERROR" not in node.params:
            die_on_error = self._get_bool(node, "DIE_ON_ERROR")

        config: Dict[str, Any] = {
            "filepath": filepath,
            "format": fmt,
            "delimiter": delimiter,
            "csv_separator": csv_separator,
            "print_operations": print_operations,
            "error_if_not_exists": error_if_not_exists,
            "die_on_error": die_on_error,
            "disable_error": disable_error,
            "disable_warnings": disable_warnings,
            "disable_info": disable_info,
            "load_new_variable": load_new_variable,
            "not_load_old_variable": not_load_old_variable,
        }

        # ---- 4. Warnings ----
        if not filepath:
            warnings.append(
                "CONTEXTFILE is empty -- context load requires a file path"
            )

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS")
        config["label"] = self._get_str(node, "LABEL")

        # ---- 6. Schema ----
        # Utility component -- no data flow schema
        schema: Dict[str, Any] = {"input": [], "output": []}

        # ---- 7. Engine gap needs_review entries (per-feature) ----
        _engine_gaps = [
            ("die_on_error", "Engine always raises on error; does not honor die_on_error=false to log and continue"),
            ("disable_warnings", "Engine has no warning-level message filtering; disable_warnings config key is ignored"),
            ("disable_error", "Engine has no error-level message filtering; disable_error config key is ignored"),
            ("disable_info", "Engine has no info-level message filtering; disable_info config key is ignored"),
            ("load_new_variable", "Engine does not validate unknown keys in incoming flow against job context"),
            ("not_load_old_variable", "Engine does not validate missing context keys against incoming flow"),
        ]
        for key, detail in _engine_gaps:
            needs_review.append({
                "issue": f"Engine does not read '{key}' from config -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 8. Return ----
        component = self._build_component_dict(
            node=node,
            type_name="ContextLoad",
            config=config,
            schema=schema,
        )
        return ComponentResult(component=component, warnings=warnings, needs_review=needs_review)
