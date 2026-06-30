"""Converter for Talend tRunJob component.

Manages parent-child job execution with context variable passing,
dynamic job selection, and JVM configuration.

Config mapping (22 params total):
  USE_DYNAMIC_JOB          -> use_dynamic_job (bool, default False)
  CONTEXT_JOB              -> context_job (str, default "")
  PROCESS                  -> process (str, default "")
  CONTEXT_NAME             -> context_name (str, default "Default")
  USE_INDEPENDENT_PROCESS  -> use_independent_process (bool, default False)
  DIE_ON_CHILD_ERROR       -> die_on_child_error (bool, default True)
  TRANSMIT_WHOLE_CONTEXT   -> transmit_whole_context (bool, default False)
  CONTEXTPARAMS            -> context_params (list[dict], default [])
  PROPAGATE_CHILD_RESULT   -> propagate_child_result (bool, default False)
  PRINT_PARAMETER          -> print_parameter (bool, default False)
  TRANSMIT_ORIGINAL_CONTEXT -> transmit_original_context (bool, default True)
  USE_CHILD_JVM_SETTING    -> use_child_jvm_setting (bool, default True)
  USE_CUSTOM_JVM_SETTING   -> use_custom_jvm_setting (bool, default False)
  JVM_ARGUMENTS            -> jvm_arguments (list[dict], default [])
  USE_DYNAMIC_CONTEXT      -> use_dynamic_context (bool, default False)
  DYNAMIC_CONTEXT          -> dynamic_context (str, default "")
  USE_EXTRA_CLASSPATH      -> use_extra_classpath (bool, default False)
  EXTRA_CLASSPATH          -> extra_classpath (str, default "")
  LOAD_CONTEXT_FROM_FILE   -> load_context_from_file (bool, default False)
  SCHEMA                   -> schema (via _parse_schema)
  TSTATCATCHER_STATS       -> tstatcatcher_stats (bool, default False)
  LABEL                    -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_CONTEXTPARAMS_FIELDS = ("PARAM_NAME_COLUMN", "PARAM_VALUE_COLUMN")
_CONTEXTPARAMS_GROUP_SIZE = 2

_JVM_ARGUMENTS_FIELDS = ("ARGUMENT",)
_JVM_ARGUMENTS_GROUP_SIZE = 1


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_context_params(raw: Any) -> List[Dict[str, str]]:
    """Parse CONTEXTPARAMS TABLE into list of dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      PARAM_NAME_COLUMN   -> param_name (str, strip quotes)
      PARAM_VALUE_COLUMN  -> param_value (str, strip quotes)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _CONTEXTPARAMS_GROUP_SIZE):
        group = raw[i: i + _CONTEXTPARAMS_GROUP_SIZE]
        if len(group) < _CONTEXTPARAMS_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "PARAM_NAME_COLUMN":
                row["param_name"] = val.strip('"')
            elif ref == "PARAM_VALUE_COLUMN":
                row["param_value"] = val.strip('"')
        if row:
            result.append(row)
    return result


def _parse_jvm_arguments(raw: Any) -> List[Dict[str, str]]:
    """Parse JVM_ARGUMENTS TABLE into list of dicts.

    Each group of 1 consecutive elementRef entry maps to one row:
      ARGUMENT  -> argument (str, strip quotes)

    Incomplete trailing groups (< 1 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, str]] = []
    for i in range(0, len(raw), _JVM_ARGUMENTS_GROUP_SIZE):
        group = raw[i: i + _JVM_ARGUMENTS_GROUP_SIZE]
        if len(group) < _JVM_ARGUMENTS_GROUP_SIZE:
            break
        row: Dict[str, str] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "ARGUMENT":
                row["argument"] = val.strip('"')
        if row:
            result.append(row)
    return result


@REGISTRY.register("tRunJob")
class RunJobConverter(ComponentConverter):
    """Convert Talend tRunJob to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        params = node.params
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["use_dynamic_job"] = self._get_bool(node, "USE_DYNAMIC_JOB", False)
        config["context_job"] = self._get_str(node, "CONTEXT_JOB", "")
        config["process"] = self._get_str(node, "PROCESS", "")
        config["context_name"] = self._get_str(node, "CONTEXT_NAME", "Default")
        config["use_independent_process"] = self._get_bool(node, "USE_INDEPENDENT_PROCESS", False)
        config["die_on_child_error"] = self._get_bool(node, "DIE_ON_CHILD_ERROR", True)
        config["transmit_whole_context"] = self._get_bool(node, "TRANSMIT_WHOLE_CONTEXT", False)

        # ---- 2. TABLE parameters ----
        config["context_params"] = _parse_context_params(params.get("CONTEXTPARAMS", []))
        config["jvm_arguments"] = _parse_jvm_arguments(params.get("JVM_ARGUMENTS", []))

        # ---- 3. Advanced parameters ----
        config["propagate_child_result"] = self._get_bool(node, "PROPAGATE_CHILD_RESULT", False)
        config["print_parameter"] = self._get_bool(node, "PRINT_PARAMETER", False)
        config["transmit_original_context"] = self._get_bool(node, "TRANSMIT_ORIGINAL_CONTEXT", True)
        config["use_child_jvm_setting"] = self._get_bool(node, "USE_CHILD_JVM_SETTING", True)
        config["use_custom_jvm_setting"] = self._get_bool(node, "USE_CUSTOM_JVM_SETTING", False)
        config["use_dynamic_context"] = self._get_bool(node, "USE_DYNAMIC_CONTEXT", False)
        config["dynamic_context"] = self._get_str(node, "DYNAMIC_CONTEXT", "")
        config["use_extra_classpath"] = self._get_bool(node, "USE_EXTRA_CLASSPATH", False)
        config["extra_classpath"] = self._get_str(node, "EXTRA_CLASSPATH", "")
        config["load_context_from_file"] = self._get_bool(node, "LOAD_CONTEXT_FROM_FILE", False)

        # ---- 4. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 5. Return ----
        component = self._build_component_dict(
            node=node,
            type_name="tRunJob",
            config=config,
            schema={"input": [], "output": []},
        )
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
