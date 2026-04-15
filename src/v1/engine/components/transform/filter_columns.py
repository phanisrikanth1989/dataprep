"""Engine component for FilterColumns (tFilterColumns).

Selects columns from the input DataFrame based on the output schema.
Column filtering is driven by output_schema (set by engine from schema.output).

Config keys consumed (0 unique + framework):
  tstatcatcher_stats  (bool, default False) -- framework
  label               (str, default "")     -- framework

No config keys needed -- output schema IS the column filter.
"""
import logging
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("FilterColumns", "tFilterColumns")
class FilterColumns(BaseComponent):
    """tFilterColumns engine implementation.

    Selects columns from the input DataFrame based on the output schema.
    Columns listed in output_schema are kept; all others are dropped.
    All rows pass through -- this is a column filter, not a row filter.
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        No config keys to validate -- column filtering is driven entirely
        by output_schema set by the engine.
        """
        logger.debug(f"[{self.id}] No config keys to validate (schema-driven)")

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Filter columns based on output_schema.

        Args:
            input_data: Input DataFrame from upstream component.

        Returns:
            dict with 'main' (filtered DataFrame) and 'reject' (None).
        """
        if input_data is None or (isinstance(input_data, pd.DataFrame) and input_data.empty):
            self._update_stats(0, 0, 0)
            return {"main": input_data, "reject": None}

        # If no output schema, passthrough
        if not self.output_schema:
            self._update_stats(len(input_data), len(input_data), 0)
            return {"main": input_data, "reject": None}

        schema_cols = [col["name"] for col in self.output_schema]
        available = [c for c in schema_cols if c in input_data.columns]

        if available != schema_cols:
            missing = [c for c in schema_cols if c not in input_data.columns]
            logger.warning(f"[{self.id}] Schema columns not in input: {missing}")

        result_df = input_data[available].copy()

        self._update_stats(len(input_data), len(input_data), 0)
        return {"main": result_df, "reject": None}
