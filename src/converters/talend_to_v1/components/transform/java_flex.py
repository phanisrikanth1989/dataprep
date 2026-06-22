"""Converter for Talend tJavaFlex component.

Executes user-defined Java code split across three phases: start (once before
the main loop), main (once per row), and end (once after the loop).

Config mapping (unique params + converter-generated + framework):
  CODE_START           -> code_start          (str, MEMO_JAVA, default "")
  CODE_MAIN            -> code_main           (str, MEMO_JAVA, default "")
  CODE_END             -> code_end            (str, MEMO_JAVA, default "")
  IMPORT               -> imports             (str, MEMO_IMPORT, default "")
  DATA_AUTO_PROPAGATE  -> auto_propagate      (bool, default False)
  Version_V4.0         -> propagate_timing    "before" when true
  Version_V3_2         -> propagate_timing    "after" when true (and V4.0 false)
  --- derived from connections ---
  incoming FLOW .name  -> input_row_name      (str, default "row1")
  outgoing FLOW .name  -> output_row_name     (str, default "row2")
  --- framework ---
  TSTATCATCHER_STATS   -> tstatcatcher_stats  (bool, default False)
  LABEL                -> label               (str, default "")

Schema:
  input  -> [] (empty; filled in by _propagate_input_schemas in converter.py)
  output -> columns from the node FLOW metadata (9-col output)

Multiple output DATA flows -> appends a needs_review entry.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tJavaFlex")
class JavaFlexConverter(ComponentConverter):
    """Convert Talend tJavaFlex to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core MEMO code section parameters ----
        config: Dict[str, Any] = {}
        config["code_start"] = self._get_param(node, "CODE_START", "")
        config["code_main"] = self._get_param(node, "CODE_MAIN", "")
        config["code_end"] = self._get_param(node, "CODE_END", "")
        config["imports"] = self._get_param(node, "IMPORT", "")

        # ---- 2. Auto-propagate and propagate_timing ----
        config["auto_propagate"] = self._get_bool(node, "DATA_AUTO_PROPAGATE", False)

        v4 = self._get_bool(node, "Version_V4.0", False)
        v3_2 = self._get_bool(node, "Version_V3_2", False)
        if v4:
            config["propagate_timing"] = "before"
        elif v3_2:
            config["propagate_timing"] = "after"
        else:
            config["propagate_timing"] = "before"

        # ---- 3. Row names derived from FLOW connections ----
        incoming_flows = [
            c for c in self._incoming(node, connections) if c.connector_type == "FLOW"
        ]
        outgoing_flows = [
            c for c in self._outgoing(node, connections) if c.connector_type == "FLOW"
        ]

        config["input_row_name"] = incoming_flows[0].name if incoming_flows else "row1"
        config["output_row_name"] = outgoing_flows[0].name if outgoing_flows else "row2"

        # ---- 4. Multiple output flows: flag for review ----
        if len(outgoing_flows) > 1:
            needs_review.append({
                "issue": (
                    f"tJavaFlex '{node.component_id}' has {len(outgoing_flows)} output "
                    "FLOW connections -- only the first is mapped; additional flows "
                    "require manual review."
                ),
                "component": node.component_id,
                "severity": "multi_output",
            })

        # ---- 5. Framework parameters (ALWAYS LAST in config) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema: input=[] (propagation fills it), output=node FLOW cols ----
        output_schema = self._parse_schema(node, connector="FLOW")
        schema: Dict[str, Any] = {
            "input": [],
            "output": output_schema,
        }

        # ---- 7. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="JavaFlexComponent",
            config=config,
            schema=schema,
        )

        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
