"""Converter for Talend tSchemaComplianceCheck component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tSchemaComplianceCheck")
class SchemaComplianceCheckConverter(ComponentConverter):
    """Convert a Talend tSchemaComplianceCheck node into a v1 SchemaComplianceCheck.

    tSchemaComplianceCheck validates incoming rows against a schema definition,
    checking types, lengths, nullability, and date formats.  The schema is
    extracted from the FLOW metadata, and four boolean flags control the
    checking behaviour.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Parse schema from FLOW metadata (uses converted Python types)
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)

        if not schema_cols:
            warnings.append(
                "No FLOW schema columns found — compliance check has no "
                "schema to validate against"
            )

        # Build config-level schema list with the subset of fields the
        # compliance checker needs: name, type, nullable, length.
        config_schema: List[Dict[str, Any]] = []
        for col in schema_cols:
            entry: Dict[str, Any] = {
                "name": col["name"],
                "type": col["type"],
                "nullable": col["nullable"],
            }
            if "length" in col:
                entry["length"] = col["length"]
            config_schema.append(entry)

        # ------------------------------------------------------------------
        # Boolean configuration flags
        # ------------------------------------------------------------------
        check_all = self._get_bool(node, "CHECK_ALL", default=False)
        sub_string = self._get_bool(node, "SUB_STRING", default=False)
        strict_date_check = self._get_bool(node, "STRICT_DATE_CHECK", default=False)
        all_empty_are_null = self._get_bool(node, "ALL_EMPTY_ARE_NULL", default=False)

        config: Dict[str, Any] = {
            "schema": config_schema,
            "check_all": check_all,
            "sub_string": sub_string,
            "strict_date_check": strict_date_check,
            "all_empty_are_null": all_empty_are_null,
        }

        # ------------------------------------------------------------------
        # Transform schema: input == output (passthrough from FLOW)
        # ------------------------------------------------------------------
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="SchemaComplianceCheck",
            config=config,
            schema=schema,
        )

        return ComponentResult(component=component, warnings=warnings)
