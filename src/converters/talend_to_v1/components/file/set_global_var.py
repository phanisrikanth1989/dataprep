"""Converter for Talend tSetGlobalVar component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tSetGlobalVar")
class SetGlobalVarConverter(ComponentConverter):
    """Convert a Talend tSetGlobalVar node into a v1 SetGlobalVar component.

    The VARIABLES TABLE param contains interleaved KEY/VALUE elementValue
    entries.  Each KEY/VALUE pair is collected into a ``{name, value}`` dict.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # Parse VARIABLES table.
        # XmlParser stores TABLE params as lists of {elementRef, value} dicts.
        # Entries come in KEY/VALUE pairs.
        variables: List[Dict[str, str]] = []
        raw_vars = self._get_param(node, "VARIABLES", [])

        if isinstance(raw_vars, list):
            current_key: str | None = None
            for entry in raw_vars:
                ref = entry.get("elementRef", "")
                val = entry.get("value", "").strip('"')
                if ref == "KEY":
                    # If we already had a KEY without a VALUE, emit a warning
                    if current_key is not None:
                        warnings.append(
                            f"KEY '{current_key}' has no matching VALUE — skipped"
                        )
                    current_key = val
                elif ref == "VALUE":
                    if current_key is not None:
                        variables.append({"name": current_key, "value": val})
                        current_key = None
                    else:
                        warnings.append(
                            f"VALUE '{val}' has no preceding KEY — skipped"
                        )

            # Handle trailing KEY with no VALUE
            if current_key is not None:
                warnings.append(
                    f"KEY '{current_key}' has no matching VALUE — skipped"
                )
        else:
            warnings.append(
                "VARIABLES param is not a list — expected TABLE structure"
            )

        if not variables:
            warnings.append("No variables defined — component will have no effect")

        config: Dict[str, Any] = {
            "variables": variables,
        }

        component = self._build_component_dict(
            node=node,
            type_name="SetGlobalVar",
            config=config,
            # Utility component — no data flow schema
            schema={"input": [], "output": []},
        )
        return ComponentResult(component=component, warnings=warnings)
