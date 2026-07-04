"""Engine component for Replicate (tReplicate).

Passes input data to multiple output flows unchanged. Each outgoing
flow connection receives an independent copy of the input DataFrame.
The engine's output router handles delivery to all downstream components.

Config keys consumed (3 total):
    output_count       (int, default 2)    -- number of named output_N flows in result (1-10)
    tstatcatcher_stats (bool, default False) -- framework
    label              (str, default "")   -- framework
"""
import logging
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("Replicate", "tReplicate")
class Replicate(BaseComponent):
    """tReplicate engine implementation.

    Passes input data to multiple output flows unchanged. The engine's
    output router routes ``main`` to all downstream 'flow' connections.

    Config keys:
        output_count: Number of named output_N flows included in the result
            dict in addition to ``main`` (1–10, default 2).
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        Called before every execute(). ``self.config`` contains a fresh
        deepcopy (context variables NOT yet resolved). Validates structural
        correctness only.

        Raises:
            ConfigurationError: If output_count is not an integer or outside
                the allowed range 1–10.
        """
        output_count = self.config.get("output_count", 2)
        if not isinstance(output_count, int):
            raise ConfigurationError(
                f"[{self.id}] Config 'output_count' must be an integer, "
                f"got {type(output_count).__name__}"
            )
        if output_count < 1:
            raise ConfigurationError(
                f"[{self.id}] Config 'output_count' must be at least 1, got {output_count}"
            )
        if output_count > 10:
            raise ConfigurationError(
                f"[{self.id}] Config 'output_count' cannot exceed 10, got {output_count}"
            )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Pass input data to all output flows unchanged.

        Args:
            input_data: Input DataFrame from upstream component.

        Returns:
            dict with keys:
                - ``main``: copy of input_data (or empty DataFrame)
                - ``output_1`` ... ``output_N``: additional copies when
                  output_count > 1 (for named-flow routing)
        """
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty or None input received")
            return {"main": pd.DataFrame()}

        output_count = self.config.get("output_count", 2)
        rows_in = len(input_data)
        logger.info(f"[{self.id}] Replicating {rows_in} rows to {output_count} output(s)")

        result: dict = {"main": input_data.copy()}
        for i in range(1, output_count + 1):
            result[f"output_{i}"] = input_data.copy()

        logger.debug(f"[{self.id}] Produced {len(result)} output keys")
        return result
