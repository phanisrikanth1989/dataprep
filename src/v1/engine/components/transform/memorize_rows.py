"""MemorizeRows engine component.

Talend equivalent: tMemorizeRows

Memorizes the last N rows passing through the component so that downstream
components can reference prior row values via globalMap variables. All input
rows pass through to the output unchanged -- this is a pure passthrough transform
with a side-effect of writing globalMap variables.

GlobalMap pattern published per row:
    {id}_{column}_{offset}   -- value of ``column`` from ``offset`` rows ago
                                (0-indexed: 0 = most recent memorized row,
                                 row_count-1 = oldest memorized row)

Config keys (resolved by BaseComponent before _process is called):
    row_count       (str, default "1")  -- number of prior rows to memorize;
                    TEXT type in Talend to allow context-var expressions like
                    ``context.rowCount``; coerced to int in _process()
    specify_cols    (list[dict], default [])
                    -- per-column memorization flags; each entry is
                    {"memorize_it": bool}; empty list means memorize ALL columns;
                    when non-empty, one entry per schema column in order

GlobalMap variables set:
    {id}_NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()
    {id}_{column}_{offset}   -- one entry per memorized column × offset
"""
import collections
import logging
from typing import Any, Deque, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("MemorizeRows", "tMemorizeRows")
class MemorizeRows(BaseComponent):
    """Passthrough transform that memorizes the last N rows in globalMap.

    All rows flow through to the main output unchanged. After processing the
    full DataFrame the last ``row_count`` rows are published to globalMap so
    that downstream expressions such as ``globalMap.get("myMem_value_0")``
    can reference prior values.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Check structural config -- key presence and container types only (Rule 12).

        Raises:
            ConfigurationError: If ``specify_cols`` is not a list.
        """
        specify_cols = self.config.get("specify_cols", [])
        if not isinstance(specify_cols, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'specify_cols' must be a list, "
                f"got {type(specify_cols).__name__!r}"
            )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Pass all rows through and publish the last N rows to globalMap.

        Args:
            input_data: Input DataFrame from upstream component.

        Returns:
            Dict with 'main' (all input rows, unchanged) and 'reject' None.

        Raises:
            ConfigurationError: If ``row_count`` cannot be converted to a
                positive integer.
        """
        if input_data is None or input_data.empty:
            self._update_stats(0, 0, 0)
            return {"main": pd.DataFrame(), "reject": None}

        # row_count is TEXT in Talend -- coerce to int here (Rule 12)
        raw_row_count = self.config.get("row_count", "1")
        try:
            row_count = int(raw_row_count)
            if row_count < 1:
                raise ValueError("must be >= 1")
        except (ValueError, TypeError):
            raise ConfigurationError(
                f"[{self.id}] Config 'row_count' must be a positive integer, "
                f"got: {raw_row_count!r}"
            )

        specify_cols: list = self.config.get("specify_cols", [])

        # Determine which columns to memorize
        all_columns = list(input_data.columns)
        if specify_cols:
            # One entry per schema column; memorize those with memorize_it=True
            columns_to_memorize = [
                col for col, entry in zip(all_columns, specify_cols)
                if entry.get("memorize_it", True)
            ]
        else:
            # Empty list -> memorize all columns
            columns_to_memorize = all_columns

        logger.info(
            "[%s] Memorizing last %d row(s) for %d column(s)",
            self.id, row_count, len(columns_to_memorize),
        )

        # Take the last row_count rows from the DataFrame
        tail_df = input_data.tail(row_count)

        # Publish globalMap variables
        # offset 0 = most recent row (last in tail_df),
        # offset 1 = second most recent, etc.
        tail_rows = list(tail_df.itertuples(index=False, name=None))
        col_indices = [all_columns.index(c) for c in columns_to_memorize]

        for offset in range(row_count):
            row_index = len(tail_rows) - 1 - offset  # most-recent first
            if row_index < 0:
                # Fewer rows than row_count; fill with None
                for col in columns_to_memorize:
                    self.global_map.put(f"{self.id}_{col}_{offset}", None)
            else:
                row_values = tail_rows[row_index]
                for ci, col in zip(col_indices, columns_to_memorize):
                    val = row_values[ci]
                    self.global_map.put(f"{self.id}_{col}_{offset}", val)
                    logger.debug(
                        "[%s] globalMap[%s_%s_%d] = %r",
                        self.id, self.id, col, offset, val,
                    )

        nb_line = len(input_data)
        logger.info("[%s] MemorizeRows complete: %d row(s) passed through", self.id, nb_line)

        self._update_stats(nb_line, nb_line, 0)
        return {"main": input_data.copy(), "reject": None}
