"""Converter for Talend tSortRow to v2 SortRow component.

Parses the CRITERIA TABLE (stride-3: COLNAME, SORT, ORDER) and builds
the v2 sort config.  CRITICAL: the SORT field is the data-type
(NUM/ALPHA/DATE), NOT the direction.  The ORDER field is the direction
(ASC/DESC).  Historical converters had these inverted.

Config mapping:
  CRITERIA.COLNAME -> columns[].name
  CRITERIA.ORDER   -> columns[].order (asc/desc) -- direction
  CRITERIA.SORT    -> dropped (Polars uses column dtype)
  EXTERNAL, TEMPFILE, CREATEDIR, EXTERNAL_SORT_BUFFERSIZE -> warnings (NOT_PLANNED)
  TSTATCATCHER_STATS -> warning (NOT_PLANNED)
  LABEL            -> label (metadata)

Null positioning:
  Talend tSortRow has no native null-positioning control.  The converter
  does NOT emit nulls_last; the v2 runtime default (false) applies.
  Users can add per-column nulls_last in v2-native configs.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY as CONVERTER_REGISTRY
from ..utils import _parse_table_rows

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

# CRITERIA TABLE field names (stride-3)
_CRITERIA_FIELDS = ("COLNAME", "SORT", "ORDER")

# NOT_PLANNED parameters -- grouped warning for external sort params
_EXTERNAL_SORT_PARAMS = frozenset({"EXTERNAL", "TEMPFILE", "CREATEDIR", "EXTERNAL_SORT_BUFFERSIZE"})

_NOT_PLANNED_PARAMS = {
    "TSTATCATCHER_STATS": "TSTATCATCHER_STATS is NOT_PLANNED in v2 -- use Python logging instead.",
}


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _strip_talend_quotes(value: str) -> str:
    """Strip surrounding double-quotes from Talend XML parameter values."""
    return value.strip('"')


# ------------------------------------------------------------------
# Converter class
# ------------------------------------------------------------------


@CONVERTER_REGISTRY.register("tSortRow")
class SortRowConverter(ComponentConverter):
    """Convert Talend tSortRow to v2 sort_row config.

    CRITICAL: SORT field = data-type (NUM/ALPHA/DATE), ORDER field = direction
    (ASC/DESC).  The SORT field is dropped; Polars handles type-aware sorting
    natively via column dtype.
    """

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        """Convert a TalendNode into a v2 SortRow component dict."""
        warnings: List[str] = []

        # ---- 1. Parse CRITERIA TABLE (stride-3: COLNAME, SORT, ORDER) ----
        raw_criteria = node.params.get("CRITERIA", [])
        parsed = _parse_table_rows(raw_criteria)

        columns: List[Dict[str, Any]] = []
        for row in parsed:
            colname = _strip_talend_quotes(row.get("COLNAME", ""))
            # ORDER is the direction (ASC/DESC) -- CRITICAL: not SORT
            order = _strip_talend_quotes(row.get("ORDER", "ASC")).lower()
            if order not in ("asc", "desc"):
                order = "asc"
            # SORT is the data-type (NUM/ALPHA/DATE) -- dropped per D-02/D-04
            columns.append({"name": colname, "order": order})

        # ---- 2. Build config ----
        config: Dict[str, Any] = {
            "columns": columns,
            "maintain_order": True,  # Talend sort is always stable (D-10)
        }

        # ---- 3. Check EXTERNAL sort params (D-11 through D-14) ----
        external_val = node.params.get("EXTERNAL", "")
        if isinstance(external_val, str):
            external_active = _strip_talend_quotes(external_val).lower() == "true"
        else:
            external_active = bool(external_val)

        has_external_params = external_active or any(
            node.params.get(p) for p in _EXTERNAL_SORT_PARAMS - {"EXTERNAL"}
        )
        if has_external_params:
            warnings.append(
                "Features EXTERNAL, TEMPFILE, CREATEDIR, EXTERNAL_SORT_BUFFERSIZE are "
                "NOT_PLANNED in v2. Polars handles large dataset sorting natively via "
                "lazy execution -- no manual external sort needed."
            )

        # ---- 4. Check TSTATCATCHER_STATS (D-15) ----
        tstat_val = node.params.get("TSTATCATCHER_STATS", "")
        if isinstance(tstat_val, str):
            tstat_active = _strip_talend_quotes(tstat_val).lower() == "true"
        else:
            tstat_active = bool(tstat_val)
        if tstat_active:
            warnings.append(_NOT_PLANNED_PARAMS["TSTATCATCHER_STATS"])

        # ---- 5. Extract LABEL (D-08) ----
        label_val = node.params.get("LABEL", "")
        if label_val:
            config["label"] = _strip_talend_quotes(str(label_val))

        # ---- 6. Build component dict ----
        component = {
            "id": node.component_id,
            "type": "sort_row",
            "config": config,
        }

        # ---- 7. Build flows ----
        flows = self._build_simple_flows(node, connections)

        return ComponentResult(
            component=component,
            flows=flows,
            warnings=warnings,
            needs_review=[],
        )
