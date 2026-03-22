"""Converter for tOracleInput -> OracleInput."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tOracleInput")
class OracleInputConverter(ComponentConverter):
    """Convert a Talend tOracleInput node to v1 OracleInput."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "host": self._get_str(node, "HOST"),
            "port": self._get_int(node, "PORT", 1521),
            "dbname": self._get_str(node, "DBNAME"),
            "user": self._get_str(node, "USER"),
            "password": self._get_str(node, "PASSWORD"),
            "query": self._get_str(node, "QUERY"),
        }

        # Warn on missing mandatory parameters
        if not config["host"]:
            warnings.append("HOST is empty — this is a required parameter")
        if not config["dbname"]:
            warnings.append("DBNAME is empty — this is a required parameter")
        if not config["query"]:
            warnings.append("QUERY is empty — this is a required parameter")

        component = self._build_component_dict(
            node=node,
            type_name="OracleInput",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        return ComponentResult(component=component, warnings=warnings)
