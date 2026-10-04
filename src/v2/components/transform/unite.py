"""Unite component for v2 engine.

Combines multiple input streams into one output using UNION ALL semantics.
Equivalent of Talend tUnite.

Config mapping:
  mode: str        -- 'all' (default) or 'distinct' (v2-only)
  align_schemas: bool -- switch to diagonal_relaxed concat (default False)
  inputs: list     -- selective input names (default: all provided)
"""
import logging
from enum import Enum
from typing import ClassVar, Dict, List

import polars as pl

from ..base import TransformComponent
from ..capabilities import FeatureSupport, Support
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


class UniteFeature(str, Enum):
    """Talend tUnite features mapped to v2 support levels (D-11)."""

    unite = "unite"
    mode_distinct = "mode_distinct"
    align_schemas = "align_schemas"
    inputs_selective = "inputs_selective"
    tstatcatcher_stats = "tstatcatcher_stats"
    label = "label"


@REGISTRY.register("unite")
class Unite(TransformComponent):
    """Combine multiple input streams into one output.

    Config:
        mode: str -- 'all' (keep all rows, default) or 'distinct'
            (remove duplicates after union).
        align_schemas: bool -- When False (default), uses strict
            vertical concat requiring identical schemas. When True,
            switches to diagonal_relaxed concat for schema union
            with null-fill.
        inputs: list -- Names of inputs to union. Defaults to all
            provided inputs.

    Example:
        {"mode": "all"}
        {"align_schemas": true, "inputs": ["left", "right"]}
    """

    SUPPORTED_FEATURES: ClassVar[Dict[str, FeatureSupport]] = {
        UniteFeature.unite: FeatureSupport(
            support=Support.FULL,
            note="Core UNION ALL semantics: all input rows combined into single output",
        ),
        UniteFeature.mode_distinct: FeatureSupport(
            support=Support.FULL,
            note="v2-only: remove duplicate rows after union via unique()",
        ),
        UniteFeature.align_schemas: FeatureSupport(
            support=Support.FULL,
            note="v2-only: switches to diagonal_relaxed concat for schema union + null-fill",
        ),
        UniteFeature.inputs_selective: FeatureSupport(
            support=Support.FULL,
            note="v2-only: pick which named inputs to include in the union",
        ),
        UniteFeature.tstatcatcher_stats: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="tStatCatcher is a v1/Talend concept; use Python logging instead",
        ),
        UniteFeature.label: FeatureSupport(
            support=Support.FULL,
            note="Component label for display/debugging",
        ),
    }

    def validate(self) -> List[str]:
        """Validate component configuration."""
        errors = []
        mode = self.config.get("mode", "all")
        if mode not in ("all", "distinct"):
            errors.append(f"Unite 'mode' must be 'all' or 'distinct', got '{mode}'")
        return errors

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        """Combine input streams into a single output via concat."""
        if not inputs:
            return {}

        input_names = self.config.get("inputs", list(inputs.keys()))
        mode = self.config.get("mode", "all")
        align_schemas = self.config.get("align_schemas", False)

        frames = []
        for name in input_names:
            if name in inputs:
                data = inputs[name]
                if isinstance(data, pl.DataFrame):
                    data = data.lazy()
                frames.append(data)
            else:
                logger.warning(
                    "Unite %s: configured input %r not found in provided inputs %s",
                    self.component_id, name, list(inputs.keys()),
                )

        if not frames:
            return {}

        if len(frames) == 1:
            result = frames[0]
        else:
            if align_schemas:
                result = pl.concat(frames, how="diagonal_relaxed")
            else:
                result = pl.concat(frames, how="vertical")

        if mode == "distinct":
            result = result.unique()

        return {"main": result}
