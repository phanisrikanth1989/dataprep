"""Converter for Talend tReplace component.

Performs search-and-replace operations on column values.

Config mapping (5 params + framework):
  SIMPLE_MODE    -> simple_mode    (bool, CHECK, default True)
  SUBSTITUTIONS  -> substitutions  (list of dicts, stride-7 TABLE)
    INPUT_COLUMN   -> input_column   (str)
    SEARCH_PATTERN -> search_pattern (str, default "default")
    REPLACE_STRING -> replace_string (str, default "default")
    WHOLE_WORD     -> whole_word     (bool, default True)  <-- CRITICAL: _java.xml says true
    CASE_SENSITIVE -> case_sensitive (bool, default False)
    USE_GLOB       -> use_glob      (bool, default False)
    COMMENT        -> comment       (str, default "")
  STRICT_MATCH   -> strict_match   (bool, CHECK, default True, SHOW="false")
  ADVANCED_MODE  -> advanced_mode  (bool, CHECK, default False)
  ADVANCED_SUBST -> advanced_subst (list of dicts, stride-4 TABLE)
    INPUT_COLUMN   -> input_column   (str)
    SEARCH_COLUMN  -> search_column  (str)
    REPLACE_COLUMN -> replace_column (str)
    COMMENT        -> comment       (str, default "")
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: CONNECTION_FORMAT (not in _java.xml)

No v1 engine implementation exists -- single consolidated needs_review per D-27.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_SUBST_FIELDS = ("INPUT_COLUMN", "SEARCH_PATTERN", "REPLACE_STRING", "WHOLE_WORD", "CASE_SENSITIVE", "USE_GLOB", "COMMENT")
_SUBST_GROUP_SIZE = len(_SUBST_FIELDS)  # 7

_ADV_SUBST_FIELDS = ("INPUT_COLUMN", "SEARCH_COLUMN", "REPLACE_COLUMN", "COMMENT")
_ADV_SUBST_GROUP_SIZE = len(_ADV_SUBST_FIELDS)  # 4


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_substitutions(raw: Any) -> List[Dict[str, Any]]:
    """Parse SUBSTITUTIONS TABLE into list of dicts.

    Each group of 7 consecutive elementRef entries maps to one row:
      INPUT_COLUMN   -> input_column   (str)
      SEARCH_PATTERN -> search_pattern (str, default "default")
      REPLACE_STRING -> replace_string (str, default "default")
      WHOLE_WORD     -> whole_word     (bool, default True)
      CASE_SENSITIVE -> case_sensitive (bool, default False)
      USE_GLOB       -> use_glob      (bool, default False)
      COMMENT        -> comment       (str, default "")

    Incomplete trailing groups (< 7 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _SUBST_GROUP_SIZE):
        group = raw[i: i + _SUBST_GROUP_SIZE]
        if len(group) < _SUBST_GROUP_SIZE:
            break
        row: Dict[str, Any] = {
            "input_column": "",
            "search_pattern": "default",
            "replace_string": "default",
            "whole_word": True,
            "case_sensitive": False,
            "use_glob": False,
            "comment": "",
        }
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "INPUT_COLUMN":
                row["input_column"] = val.strip('"')
            elif ref == "SEARCH_PATTERN":
                stripped = val.strip('"')
                if stripped:
                    row["search_pattern"] = stripped
            elif ref == "REPLACE_STRING":
                stripped = val.strip('"')
                if stripped:
                    row["replace_string"] = stripped
            elif ref == "WHOLE_WORD":
                if val:
                    row["whole_word"] = val.lower() in ("true", "1")
            elif ref == "CASE_SENSITIVE":
                if val:
                    row["case_sensitive"] = val.lower() in ("true", "1")
            elif ref == "USE_GLOB":
                if val:
                    row["use_glob"] = val.lower() in ("true", "1")
            elif ref == "COMMENT":
                row["comment"] = val.strip('"')
        if row:
            result.append(row)
    return result


def _parse_advanced_subst(raw: Any) -> List[Dict[str, Any]]:
    """Parse ADVANCED_SUBST TABLE into list of dicts.

    Each group of 4 consecutive elementRef entries maps to one row:
      INPUT_COLUMN   -> input_column   (str)
      SEARCH_COLUMN  -> search_column  (str)
      REPLACE_COLUMN -> replace_column (str)
      COMMENT        -> comment       (str, default "")

    Incomplete trailing groups (< 4 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _ADV_SUBST_GROUP_SIZE):
        group = raw[i: i + _ADV_SUBST_GROUP_SIZE]
        if len(group) < _ADV_SUBST_GROUP_SIZE:
            break
        row: Dict[str, Any] = {
            "input_column": "",
            "search_column": "",
            "replace_column": "",
            "comment": "",
        }
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "INPUT_COLUMN":
                row["input_column"] = val.strip('"')
            elif ref == "SEARCH_COLUMN":
                row["search_column"] = val.strip('"')
            elif ref == "REPLACE_COLUMN":
                row["replace_column"] = val.strip('"')
            elif ref == "COMMENT":
                row["comment"] = val.strip('"')
        if row:
            result.append(row)
    return result


@REGISTRY.register("tReplace")
class ReplaceConverter(ComponentConverter):
    """Convert Talend tReplace to v1 engine config."""

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
        config["simple_mode"] = self._get_bool(node, "SIMPLE_MODE", True)
        config["substitutions"] = _parse_substitutions(node.params.get("SUBSTITUTIONS"))
        config["strict_match"] = self._get_bool(node, "STRICT_MATCH", True)
        config["advanced_mode"] = self._get_bool(node, "ADVANCED_MODE", False)
        config["advanced_subst"] = _parse_advanced_subst(node.params.get("ADVANCED_SUBST"))

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Schema (transform passthrough) ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 4. Single consolidated needs_review per D-27 ----
        needs_review.append({
            "issue": "No v1 engine implementation for tReplace",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 5. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tReplace",
            config=config,
            schema=schema,
        )

        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
