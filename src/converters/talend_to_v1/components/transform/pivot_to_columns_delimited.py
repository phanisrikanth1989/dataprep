"""Converter for Talend tPivotToColumnsDelimited component.

tPivotToColumnsDelimited pivots rows into columns and writes the result to a
delimited file.  It groups rows by one or more group-by columns, pivots on a
named column, and aggregates values from another column using a specified
function (e.g. sum, count, avg).

Config mapping (16 _java.xml params + 2 framework params):
  PIVOT_COLUMN         -> pivot_column (str, default "")
  AGGREGATION_COLUMN   -> aggregation_column (str, default "")
  AGGREGATION_FUNCTION -> aggregation_function (str, CLOSED_LIST default "sum")
  GROUPBYS             -> groupbys (list of str via _parse_group_bys, TABLE stride-1)
  FILENAME             -> filename (str, default "")
  CREATE               -> create (bool, default True)
  ROWSEPARATOR         -> rowseparator (str, default "\\n")
  FIELDSEPARATOR       -> fieldseparator (str, default ";")
  ENCODING             -> encoding (str, default "ISO-8859-15")
  ADVANCED_SEPARATOR   -> advanced_separator (bool, default False)
  THOUSANDS_SEPARATOR  -> thousands_separator (str, default ",")
  DECIMAL_SEPARATOR    -> decimal_separator (str, default ".")
  CSV_OPTION           -> csv_option (bool, default False)
  ESCAPE_CHAR          -> escape_char (str, default '"')
  TEXT_ENCLOSURE       -> text_enclosure (str, default '"')
  DELETE_EMPTYFILE     -> delete_emptyfile (bool, default False)
  TSTATCATCHER_STATS   -> tstatcatcher_stats (bool, framework)
  LABEL                -> label (str, framework)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# TABLE parser functions (module-level, prefixed with underscore)
# ------------------------------------------------------------------


def _parse_group_bys(raw: Any) -> List[str]:
    """Parse the GROUPBYS TABLE parameter (stride-1).

    The table is stored as a list of dicts, each with a ``value`` key
    that holds a quoted column name.  Empty values after quote-stripping
    are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []

    result: List[str] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        val = entry.get("value", "").strip('"')
        if val:
            result.append(val)

    return result


@REGISTRY.register("tPivotToColumnsDelimited")
class PivotToColumnsDelimitedConverter(ComponentConverter):
    """Convert Talend tPivotToColumnsDelimited to v1 engine config."""

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
        config["pivot_column"] = self._get_str(node, "PIVOT_COLUMN")
        config["aggregation_column"] = self._get_str(node, "AGGREGATION_COLUMN")

        # ---- 2. CLOSED_LIST parameter ----
        config["aggregation_function"] = self._get_str(node, "AGGREGATION_FUNCTION", default="sum")

        # ---- 3. TABLE parameter ----
        raw_groupbys = node.params.get("GROUPBYS", [])
        if raw_groupbys and not isinstance(raw_groupbys, list):
            warnings.append("GROUPBYS param is not a list -- expected TABLE structure")
            config["groupbys"] = []
        else:
            config["groupbys"] = _parse_group_bys(raw_groupbys)

        # ---- 4. File output parameters ----
        config["filename"] = self._get_str(node, "FILENAME")
        config["create"] = self._get_bool(node, "CREATE", default=True)
        config["rowseparator"] = self._get_str(node, "ROWSEPARATOR", default="\\n")
        config["fieldseparator"] = self._get_str(node, "FIELDSEPARATOR", default=";")
        config["encoding"] = self._get_str(node, "ENCODING", default="ISO-8859-15")

        # ---- 5. Advanced parameters ----
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", default=False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", default=",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", default=".")
        config["csv_option"] = self._get_bool(node, "CSV_OPTION", default=False)
        config["escape_char"] = self._get_str(node, "ESCAPE_CHAR", default='"')
        config["text_enclosure"] = self._get_str(node, "TEXT_ENCLOSURE", default='"')
        config["delete_emptyfile"] = self._get_bool(node, "DELETE_EMPTYFILE", default=False)

        # ---- 6. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 7. Validation warnings ----
        if not config["pivot_column"]:
            warnings.append("PIVOT_COLUMN is empty -- pivot operation has no pivot column")
        if not config["aggregation_column"]:
            warnings.append("AGGREGATION_COLUMN is empty -- pivot has no aggregation target")
        if not config["filename"]:
            warnings.append("FILENAME is empty -- output file path is not defined")

        # ---- 8. Schema: transform -- input and output are the same parsed schema ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 9. Engine gap needs_review entries ----
        _engine_gap_keys = [
            ("advanced_separator", "engine does not read advanced_separator from config"),
            ("thousands_separator", "engine does not read thousands_separator from config"),
            ("decimal_separator", "engine does not read decimal_separator from config"),
            ("csv_option", "engine does not read csv_option from config"),
            ("escape_char", "engine does not read escape_char from config"),
            ("text_enclosure", "engine does not read text_enclosure from config"),
            ("delete_emptyfile", "engine does not read delete_emptyfile from config"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 10. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="PivotToColumnsDelimited",
            config=config,
            schema=schema,
        )

        # ---- 11. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
