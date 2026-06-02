"""tForeach engine component -- iterates over a static list of values.

Converter JSON keys -> engine config keys (per Talaxie tForeach_java.xml):

    VALUES (TABLE: list[str])   -> values (list[str])
        Static list of string values to iterate. Each value is exposed via
        globalMap on its iteration. Quotes are already stripped by the
        converter (src/converters/talend_to_v1/components/iterate/foreach.py).

GlobalMap variables (Talend parity):
    {cid}_CURRENT_VALUE        -- current iteration value (str)
    {cid}_CURRENT_ITERATION    -- 1-based iter counter (written by base class)
    {cid}_NB_LINE              -- total iterations, set after finalize()

Statistics:
    NB_LINE        = len(values)
    NB_LINE_OK     = NB_LINE
    NB_LINE_REJECT = 0

tForeach is a source-style iterate component: it takes no input DataFrame and
produces no main DataFrame output. Each iteration triggers re-execution of the
body subjob via the engine's iterate loop (BaseIterateComponent contract).
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

import pandas as pd

from ...base_iterate_component import BaseIterateComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Typed item produced per iteration
# ------------------------------------------------------------------

@dataclass
class ForeachItem:
    """Typed item produced by Foreach per iteration.

    Attributes:
        value: Current string value from the configured values list.
        index: 1-based iteration counter.
    """
    value: str
    index: int


# ------------------------------------------------------------------
# Component
# ------------------------------------------------------------------

@REGISTRY.register("Foreach", "tForeach")
class Foreach(BaseIterateComponent):
    """tForeach engine component.

    Iterates over a static list of values, exposing the current value as
    ``{cid}_CURRENT_VALUE`` in globalMap before each body-subjob execution.

    See module docstring for full config-key reference, globalMap variable
    documentation, and statistics contract.
    """

    # ------------------------------------------------------------------
    # Structural validation (Phase 7.1 Rule 12)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate structural config correctness.

        Checks:
        - ``values`` is a list when present (absence defaults to []).
        - Every element of ``values`` is a string.

        Raises:
            ConfigurationError: If a structural constraint is violated.
        """
        values = self.config.get("values", [])
        if not isinstance(values, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'values' must be a list, "
                f"got {type(values).__name__!r}"
            )
        for i, val in enumerate(values):
            if not isinstance(val, str):
                raise ConfigurationError(
                    f"[{self.id}] Config 'values[{i}]' must be a string, "
                    f"got {type(val).__name__!r}"
                )

    # ------------------------------------------------------------------
    # Hook 2: produce iteration items
    # ------------------------------------------------------------------

    def prepare_iterations(
        self, input_data: Optional[pd.DataFrame] = None
    ) -> Iterator[ForeachItem]:
        """Materialise configured values into an iterator of ForeachItem.

        Args:
            input_data: Ignored. tForeach is a source iterate component.

        Returns:
            Bounded iterator of ForeachItem, one per configured value.
        """
        values: List[str] = list(self.config.get("values", []))
        self.total_iterations = len(values)

        logger.info(
            "[%s] tForeach iterating %d value(s)", self.id, self.total_iterations
        )

        items = [
            ForeachItem(value=val, index=idx)
            for idx, val in enumerate(values, start=1)
        ]
        return iter(items)

    # ------------------------------------------------------------------
    # Hook 5: write per-iteration globalMap entries
    # ------------------------------------------------------------------

    def set_iteration_globalmap(self, item: ForeachItem) -> None:
        """Push the current value into globalMap as ``{cid}_CURRENT_VALUE``.

        Args:
            item: ForeachItem for the current iteration.
        """
        if self.global_map is None:
            return
        self.global_map.put(f"{self.id}_CURRENT_VALUE", item.value)

    # ------------------------------------------------------------------
    # Logging hook (D-H3)
    # ------------------------------------------------------------------

    def get_iter_key_info(self, item: ForeachItem, index: int) -> str:
        """Return component-specific key info for per-iteration log lines.

        Args:
            item: ForeachItem for the current iteration.
            index: 1-based iteration index.

        Returns:
            "value=<repr>" string for use in iteration log lines.
        """
        return f"value={item.value!r}"

    # ------------------------------------------------------------------
    # Hook 9: finalize -- set NB_LINE stats
    # ------------------------------------------------------------------

    def finalize(self) -> None:
        """Set NB_LINE statistics after all iterations complete."""
        nb_line = max(self.total_iterations, 0)
        self.stats["NB_LINE"] = nb_line
        self.stats["NB_LINE_OK"] = nb_line
        self.stats["NB_LINE_REJECT"] = 0
        logger.info("[%s] tForeach finalized: NB_LINE=%d", self.id, nb_line)
