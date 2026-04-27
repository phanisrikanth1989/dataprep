"""Engine component for SampleRow (tSampleRow).

Selects specific rows from the input by 1-based positional index using a
Talend range specification string.  Matching rows go to ``main``; all other
rows go to ``reject``.

Range specification format (``range`` config key):
  Comma-separated parts.  Each part is either:
  - A single 1-based integer         e.g. ``"5"``      -> row 5
  - An inclusive range ``n..m``      e.g. ``"10..20"`` -> rows 10 through 20

  Full example: ``"1,5,10..20"`` -> rows 1, 5, 10, 11, …, 20.
  Row indices beyond the DataFrame length are silently ignored.

Config keys consumed (3 total):
    range              (str, default "1,5,10..20") -- Talend row selection spec
    tstatcatcher_stats (bool, default False)        -- framework
    label              (str, default "")            -- framework
"""
import logging
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Module-level helper
# ------------------------------------------------------------------

def _parse_range(range_str: str, component_id: str) -> set[int]:
    """Parse a Talend range specification into a set of 1-based row indices.

    Args:
        range_str: Talend range string, e.g. ``"1,5,10..20"``.
        component_id: Component ID used in error messages.

    Returns:
        Set of 1-based integer row indices.

    Raises:
        ConfigurationError: If any part of the range string is not a valid
            integer or ``n..m`` range, or if a range has ``n > m``.
    """
    indices: set[int] = set()
    parts = [p.strip() for p in range_str.split(",") if p.strip()]
    for part in parts:
        if ".." in part:
            halves = part.split("..")
            if len(halves) != 2:
                raise ConfigurationError(
                    f"[{component_id}] Invalid range part '{part}' in range '{range_str}'"
                )
            try:
                start = int(halves[0].strip())
                end = int(halves[1].strip())
            except ValueError:
                raise ConfigurationError(
                    f"[{component_id}] Non-integer bounds in range part '{part}'"
                )
            if start > end:
                raise ConfigurationError(
                    f"[{component_id}] Range start {start} > end {end} in part '{part}'"
                )
            if start < 1:
                raise ConfigurationError(
                    f"[{component_id}] Range start must be >= 1, got {start} in '{part}'"
                )
            indices.update(range(start, end + 1))
        else:
            try:
                idx = int(part)
            except ValueError:
                raise ConfigurationError(
                    f"[{component_id}] Non-integer row index '{part}' in range '{range_str}'"
                )
            if idx < 1:
                raise ConfigurationError(
                    f"[{component_id}] Row index must be >= 1, got {idx}"
                )
            indices.add(idx)
    return indices


@REGISTRY.register("SampleRow", "tSampleRow")
class SampleRow(BaseComponent):
    """tSampleRow engine implementation.

    Selects specific rows by 1-based positional index using a Talend range
    specification string.  Selected rows go to ``main``; the remaining rows
    go to ``reject``.

    Config keys:
        range: Comma-separated list of 1-based row indices and/or ``n..m``
            inclusive ranges.  Defaults to ``"1,5,10..20"``.
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        Called before every execute(). ``self.config`` contains a fresh
        deepcopy (context variables NOT yet resolved). Validates structural
        correctness only — the range string is parsed here to catch syntax
        errors early.

        Raises:
            ConfigurationError: If ``range`` is missing, not a string, or
                contains invalid syntax.
        """
        range_val = self.config.get("range")
        if range_val is None:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'range'"
            )
        if not isinstance(range_val, str):
            raise ConfigurationError(
                f"[{self.id}] Config 'range' must be a string, "
                f"got {type(range_val).__name__}"
            )
        if not range_val.strip():
            raise ConfigurationError(
                f"[{self.id}] Config 'range' must not be empty"
            )
        # Parse now to surface syntax errors before _process() is called
        _parse_range(range_val, self.id)

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Select rows by positional index using the range specification.

        Row indices are 1-based to match Talend convention.  Indices beyond
        the DataFrame length are silently ignored.  Original row order is
        preserved in both ``main`` and ``reject`` outputs.

        Args:
            input_data: Input DataFrame from upstream component.

        Returns:
            dict with keys:
                - ``main``: rows at the specified indices
                - ``reject``: all other rows (or empty DataFrame)
        """
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty or None input received")
            return {"main": pd.DataFrame(), "reject": pd.DataFrame()}

        range_str = self.config.get("range", "1,5,10..20")
        selected_indices = _parse_range(range_str, self.id)

        total_rows = len(input_data)
        # Convert 1-based indices to 0-based, discard out-of-range
        zero_based = sorted(i - 1 for i in selected_indices if 1 <= i <= total_rows)
        all_positions = set(range(total_rows))
        reject_positions = sorted(all_positions - set(zero_based))

        main_df = input_data.iloc[zero_based].reset_index(drop=True)
        reject_df = input_data.iloc[reject_positions].reset_index(drop=True)

        logger.info(
            f"[{self.id}] Selected {len(main_df)} row(s) from {total_rows} "
            f"using range '{range_str}'; {len(reject_df)} row(s) to reject"
        )
        return {"main": main_df, "reject": reject_df}
