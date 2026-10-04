"""Execution context for V2 engine."""
import re
import logging
from typing import Any, Dict, Optional

import polars as pl

logger = logging.getLogger(__name__)


class ExecutionContext:
    """
    Manages state during job execution.

    Responsibilities:
    - Store/retrieve component outputs (Dict[str, LazyFrame] per component)
    - Reference counting for memory management
    - Context variable resolution
    - Component stats collection
    """

    def __init__(self, context_vars: Optional[Dict[str, Any]] = None):
        self.context_vars = context_vars or {}
        self._outputs: Dict[str, Dict[str, pl.LazyFrame]] = {}  # comp_id -> {output_name -> LazyFrame}
        self._ref_counts: Dict[str, int] = {}
        self._component_stats: Dict[str, Dict[str, Any]] = {}

    def store_output(self, component_id: str, output_name: str, data: pl.LazyFrame) -> None:
        """Store a component's output."""
        if component_id not in self._outputs:
            self._outputs[component_id] = {}
        self._outputs[component_id][output_name] = data

    def get_output(self, component_id: str, output_name: str = "main") -> Optional[pl.LazyFrame]:
        """Retrieve a component's output by name."""
        comp_outputs = self._outputs.get(component_id)
        if comp_outputs is None:
            return None
        return comp_outputs.get(output_name)

    def set_ref_count(self, component_id: str, count: int) -> None:
        """Set the reference count for a component's outputs."""
        self._ref_counts[component_id] = count

    def decrement_ref(self, component_id: str) -> None:
        """Decrement ref count. Frees outputs when count reaches 0."""
        if component_id not in self._ref_counts:
            return
        self._ref_counts[component_id] -= 1
        if self._ref_counts[component_id] <= 0:
            if component_id in self._outputs:
                del self._outputs[component_id]
                logger.debug(f"Freed outputs for {component_id} (ref count reached 0)")

    def clear_stage(self, component_ids: set) -> None:
        """Free all outputs and ref counts for the given components.

        Called between stages to release memory. Preserves context_vars
        and component_stats (needed for job-level reporting).

        Args:
            component_ids: Set of component IDs to clear.
        """
        for comp_id in component_ids:
            if comp_id in self._outputs:
                del self._outputs[comp_id]
            if comp_id in self._ref_counts:
                del self._ref_counts[comp_id]
        if component_ids:
            logger.debug(
                f"Cleared stage intermediates for {len(component_ids)} components"
            )

    def get(self, var_name: str) -> Any:
        """Get a context variable value."""
        return self.context_vars.get(var_name)

    def resolve(self, value: Any) -> Any:
        """Resolve ${context.var} placeholders in a string."""
        if not isinstance(value, str) or "${context." not in value:
            return value

        def _replace(match):
            var_name = match.group(1)
            if var_name in self.context_vars:
                return str(self.context_vars[var_name])
            return match.group(0)

        return re.sub(r'\$\{context\.(\w+)\}', _replace, value)

    def record_component_stats(self, component_id: str, stats: Dict[str, Any]) -> None:
        """Record execution stats for a component."""
        self._component_stats[component_id] = stats

    def get_component_stats(self, component_id: str) -> Optional[Dict[str, Any]]:
        """Get stats for a specific component."""
        return self._component_stats.get(component_id)

    def get_execution_result(self) -> Dict[str, Any]:
        """Get the full execution result with all component stats."""
        return {
            "components": dict(self._component_stats),
        }
