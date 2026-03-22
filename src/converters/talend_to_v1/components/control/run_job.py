"""Converter for Talend tRunJob component.

Maps the tRunJob node to a v1 RunJobComponent.  The CONTEXTPARAMS TABLE
parameter is serialised by the XML parser as a flat list of
``{elementRef, value}`` dicts.  Each entry with ``elementRef`` and
``value`` becomes one ``{name, value}`` pair in ``context_params``.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tRunJob")
class RunJobConverter(ComponentConverter):
    """Convert a Talend tRunJob node into a v1 RunJobComponent."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Scalar parameters
        # ------------------------------------------------------------------
        process = self._get_str(node, "PROCESS", default="")
        context_name = self._get_str(node, "CONTEXT_NAME", default="Default")
        die_on_child_error = self._get_bool(
            node, "DIE_ON_CHILD_ERROR", default=True
        )
        print_parameter = self._get_bool(
            node, "PRINT_PARAMETER", default=False
        )

        # ------------------------------------------------------------------
        # CONTEXTPARAMS table parameter
        # ------------------------------------------------------------------
        context_params: List[Dict[str, str]] = []
        raw_params = self._get_param(node, "CONTEXTPARAMS", [])

        if isinstance(raw_params, list):
            for entry in raw_params:
                name = entry.get("elementRef", "")
                value = entry.get("value", "")
                if isinstance(value, str):
                    value = value.strip('"')
                if name:
                    context_params.append({"name": name, "value": value})
        else:
            warnings.append(
                "CONTEXTPARAMS param is not a list "
                "-- expected TABLE structure"
            )

        if not process:
            warnings.append(
                "PROCESS is empty -- RunJobComponent has no child job configured"
            )

        # ------------------------------------------------------------------
        # Build config
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            "process": process,
            "context_name": context_name,
            "die_on_child_error": die_on_child_error,
            "print_parameter": print_parameter,
            "context_params": context_params,
        }

        component = self._build_component_dict(
            node=node,
            type_name="RunJobComponent",
            config=config,
            # Utility component -- no data flow schema
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings)
