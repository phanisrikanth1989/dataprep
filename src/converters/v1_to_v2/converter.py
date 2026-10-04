"""Main V1-to-V2 config converter."""
from datetime import datetime, timezone
from typing import Any, Dict, List

from .component_mapper import map_component


# V1 Talend type IDs -> V2 simple type names (for context variables)
_CONTEXT_TYPE_MAP = {
    "id_String": "str",
    "id_Integer": "int",
    "id_Long": "int",
    "id_Float": "float",
    "id_Double": "float",
    "id_Boolean": "bool",
    "id_Date": "date",
    "id_BigDecimal": "str",
}


class V1ToV2Converter:
    """Convert a V1 engine JSON config to V2 format."""

    def __init__(self, v1_config: Dict[str, Any]) -> None:
        self._v1 = v1_config
        self._warnings: List[str] = []
        self._components_needing_review: List[str] = []
        self._expressions_needing_review: List[Dict[str, str]] = []

    def convert(self) -> Dict[str, Any]:
        """Run the full conversion and return a V2 config dict."""
        v2: Dict[str, Any] = {
            "name": self._v1.get("job_name", "unnamed_job"),
            "version": "2.0",
            "context": self._convert_context(),
            "components": self._convert_components(),
            "flows": self._convert_flows(),
        }

        self._warn_triggers()
        self._warn_java_config()

        v2["_conversion_metadata"] = {
            "source_version": "v1",
            "converted_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "warnings": self._warnings,
            "components_needing_review": self._components_needing_review,
            "expressions_needing_review": self._expressions_needing_review,
        }

        return v2

    def _convert_context(self) -> Dict[str, Any]:
        v1_context = self._v1.get("context", {})
        if not v1_context:
            return {}

        default_set = self._v1.get("default_context", "Default")
        context_set = v1_context.get(default_set, {})

        if not context_set and not any(
            isinstance(v, dict) and "value" not in v for v in v1_context.values()
        ):
            context_set = v1_context

        v2_context: Dict[str, Any] = {}
        for var_name, var_def in context_set.items():
            if not isinstance(var_def, dict):
                v2_context[var_name] = var_def
                continue

            v1_type = var_def.get("type", "id_String")
            v2_type = _CONTEXT_TYPE_MAP.get(v1_type, "str")

            v2_var: Dict[str, Any] = {
                "value": var_def.get("value"),
                "type": v2_type,
            }

            if "description" in var_def:
                v2_var["description"] = var_def["description"]

            v2_context[var_name] = v2_var

        return v2_context

    def _convert_components(self) -> List[Dict[str, Any]]:
        v2_components = []
        for v1_comp in self._v1.get("components", []):
            result = map_component(v1_comp)

            v2_components.append(result.component)
            self._warnings.extend(result.warnings)
            self._expressions_needing_review.extend(result.expressions_needing_review)

            if result.component.get("config", {}).get("_unsupported"):
                self._components_needing_review.append(result.component["id"])

        return v2_components

    def _convert_flows(self) -> List[Dict[str, Any]]:
        v2_flows = []
        for v1_flow in self._v1.get("flows", []):
            v2_flow: Dict[str, Any] = {
                "source": v1_flow.get("from", ""),
                "target": v1_flow.get("to", ""),
            }

            flow_type = v1_flow.get("type", "flow")

            if flow_type == "reject":
                v2_flow["output"] = "reject"
            elif flow_type == "filter":
                v2_flow["output"] = "unmatched"
            elif flow_type == "iterate":
                v2_flow["_unsupported"] = True
                self._warnings.append(
                    f"Flow '{v1_flow.get('name', '')}' is iterate type — "
                    f"unsupported in V2 (from {v1_flow.get('from')} to {v1_flow.get('to')})"
                )

            v2_flows.append(v2_flow)

        return v2_flows

    def _warn_triggers(self) -> None:
        for trigger in self._v1.get("triggers", []):
            t_type = trigger.get("type", "unknown")
            t_from = trigger.get("from", "?")
            t_to = trigger.get("to", "?")
            self._warnings.append(
                f"Trigger dropped: {t_type} from {t_from} to {t_to}"
            )

    def _warn_java_config(self) -> None:
        java_cfg = self._v1.get("java_config", {})
        if java_cfg.get("enabled"):
            routines = java_cfg.get("routines", [])
            self._warnings.append(
                f"java_config is enabled with routines {routines} — "
                f"V2 does not support Java execution"
            )
