"""FlowToIterate component for V2 engine."""
import logging
from typing import Dict

import polars as pl

from ..base import PythonComponent
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("flow_to_iterate")
class FlowToIterate(PythonComponent):
    """
    Convert data flow rows to iteration contexts.

    Each row becomes one iteration. The engine runs the downstream
    sub-pipeline once per row, injecting row values into context.

    Config:
        columns: list - Optional column names to include (default: all)
    """

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        data = inputs.get("main")
        if data is None:
            return {"__iterations__": []}

        # Collect -- this is a barrier
        if isinstance(data, pl.LazyFrame):
            df = data.collect()
        elif isinstance(data, pl.DataFrame):
            df = data
        else:
            return {"__iterations__": []}

        # Filter columns if specified
        columns = self.config.get("columns")
        if columns:
            df = df.select(columns)

        # Convert each row to an iteration context dict
        iterations = []
        for row in df.to_dicts():
            ctx = {}
            for col, val in row.items():
                ctx[f"{self.component_id}_{col}"] = val
            iterations.append(ctx)

        logger.info(f"FlowToIterate prepared {len(iterations)} iterations")

        return {"__iterations__": iterations}
