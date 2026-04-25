"""Engine component for SortRow (tSortRow).

Sorts input rows by multiple columns with per-column sort type and order.

Config keys consumed (4 total):
  criteria    (list[dict], required)         -- sort criteria [{column, sort_type, order}]
  external    (bool, default False)          -- future hook (not implemented, logged)
  tstatcatcher_stats (bool, default False)   -- framework
  label       (str, default "")              -- framework
"""
import logging
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)

_VALID_SORT_TYPES = frozenset({"num", "alpha", "date"})
_VALID_ORDERS = frozenset({"asc", "desc"})


@REGISTRY.register("SortRow", "tSortRow")
class SortRow(BaseComponent):
    """tSortRow engine implementation.

    Sorts a DataFrame by one or more columns.  Each criterion specifies
    a column name, a sort type (num / alpha / date), and an order
    (asc / desc).  Numeric and date sort types coerce the column before
    comparison so that, e.g., 9 sorts before 10 for numeric data.
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        Raises:
            ConfigurationError: If configuration is invalid.
        """
        criteria = self.config.get("criteria", [])
        if not criteria or not isinstance(criteria, list):
            raise ConfigurationError(
                f"[{self.id}] 'criteria' must be a non-empty list"
            )
        for idx, crit in enumerate(criteria):
            if "column" not in crit:
                raise ConfigurationError(
                    f"[{self.id}] criteria[{idx}] missing required key 'column'"
                )
            st = crit.get("sort_type", "alpha")
            if st not in _VALID_SORT_TYPES:
                raise ConfigurationError(
                    f"[{self.id}] criteria[{idx}] invalid sort_type '{st}'. "
                    f"Must be one of: {sorted(_VALID_SORT_TYPES)}"
                )
            order = crit.get("order", "asc")
            if order not in _VALID_ORDERS:
                raise ConfigurationError(
                    f"[{self.id}] criteria[{idx}] invalid order '{order}'. "
                    f"Must be one of: {sorted(_VALID_ORDERS)}"
                )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Sort the input DataFrame by the configured criteria.

        Args:
            input_data: DataFrame from upstream component.

        Returns:
            dict with 'main' (sorted DataFrame) and 'reject' (None).
        """
        if input_data is None or input_data.empty:
            return {"main": pd.DataFrame(), "reject": None}

        criteria = self.config.get("criteria", [])

        if self.config.get("external", False):
            logger.info(
                f"[{self.id}] external=True noted "
                "(not implemented -- using pandas sort_values)"
            )

        # Keep only criteria whose columns exist in the input
        valid_criteria = [c for c in criteria if c["column"] in input_data.columns]
        if not valid_criteria:
            logger.warning(
                f"[{self.id}] No sort criteria columns found in input data, "
                "returning as-is"
            )
            return {"main": input_data.copy(), "reject": None}

        columns = [c["column"] for c in valid_criteria]
        ascending = [c.get("order", "asc") == "asc" for c in valid_criteria]
        sort_types = {c["column"]: c.get("sort_type", "alpha") for c in valid_criteria}

        def sort_key(col: pd.Series) -> pd.Series:
            st = sort_types.get(col.name, "alpha")
            if st == "num":
                return pd.to_numeric(col, errors="coerce")
            if st == "date":
                return pd.to_datetime(col, errors="coerce")
            return col  # alpha -- default string comparison

        result = input_data.sort_values(
            by=columns,
            ascending=ascending,
            key=sort_key,
            ignore_index=True,
            kind="stable",
            na_position="last",
        )

        rows = len(input_data)
        self._update_stats(rows, rows, 0)
        logger.info(
            f"[{self.id}] Sorted {rows} rows by {len(valid_criteria)} criteria"
        )

        return {"main": result, "reject": None}
