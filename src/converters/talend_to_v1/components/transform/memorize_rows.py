"""Converter for Talend tMemorizeRows component."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tMemorizeRows")
class MemorizeRowsConverter(ComponentConverter):
    """Convert a Talend tMemorizeRows node into a v1 MemorizeRows component.

    tMemorizeRows memorizes a configurable number of previous rows from the
    input stream so they can be referenced in downstream expressions.

    Parameters
    ----------
    ROW_COUNT : int
        Number of rows to memorize (default ``1``).
    RESET_ON_CONDITION : bool
        Whether to reset the memorized rows when a condition is met.
    CONDITION : str
        The reset condition expression (only relevant when
        ``RESET_ON_CONDITION`` is ``true``).
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        row_count = self._get_int(node, "ROW_COUNT", 1)
        reset_on_condition = self._get_bool(node, "RESET_ON_CONDITION", False)
        condition = self._get_str(node, "CONDITION", "")

        if row_count < 1:
            warnings.append(
                f"ROW_COUNT is {row_count}; expected a positive integer. "
                "Defaulting to 1."
            )
            row_count = 1

        config: Dict[str, Any] = {
            "row_count": row_count,
            "reset_on_condition": reset_on_condition,
            "condition": condition,
        }

        schema_cols = self._parse_schema(node)

        component = self._build_component_dict(
            node=node,
            type_name="MemorizeRows",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
