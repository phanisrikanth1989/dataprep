"""Engine component for Unite (tUnite).

Concatenates multiple input DataFrames into a single output using UNION ALL semantics.

Config keys consumed (0 unique + framework):
  tstatcatcher_stats  (bool, default False) -- framework
  label               (str, default "")     -- framework

Talend tUnite performs UNION ALL (vertical concat) only.
No merge, dedup, or sort features.
"""
import logging
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("Unite", "tUnite")
class Unite(BaseComponent):
    """tUnite engine implementation.

    Concatenates all input DataFrames vertically (UNION ALL).
    Mismatched schemas produce NaN fills for missing columns.
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        No config keys to validate -- Unite simply concatenates inputs.
        """
        logger.debug(f"[{self.id}] No config keys to validate (concat-only)")

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[Any] = None) -> dict:
        """Concatenate all input DataFrames.

        Args:
            input_data: Dict of DataFrames from OutputRouter (multi-input component).

        Returns:
            dict with 'main' (concatenated DataFrame) and 'reject' (None).
        """
        if input_data is None or not isinstance(input_data, dict) or not input_data:
            self._update_stats(0, 0, 0)
            return {"main": pd.DataFrame(), "reject": None}

        dfs = [
            df for df in input_data.values()
            if df is not None and isinstance(df, pd.DataFrame) and not df.empty
        ]

        if not dfs:
            self._update_stats(0, 0, 0)
            return {"main": pd.DataFrame(), "reject": None}

        combined = pd.concat(dfs, ignore_index=True, sort=False)
        total_input = sum(len(df) for df in dfs)

        self._update_stats(total_input, len(combined), 0)
        return {"main": combined, "reject": None}
