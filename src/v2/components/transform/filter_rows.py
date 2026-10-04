"""FilterRows component for v2 engine.

Filters rows based on a condition expression compiled by the v2 DSL.
Equivalent of Talend tFilterRow.

Config mapping:
  condition: str       -- v2 DSL expression evaluating to boolean
  reject_output: bool  -- emit rejected rows on "reject" output (default False)
"""
import logging
from enum import Enum
from typing import ClassVar, Dict, List

import polars as pl

from ..base import TransformComponent
from ..capabilities import FeatureSupport, Support
from ..registry import REGISTRY
from ...expressions import compile_expression

logger = logging.getLogger(__name__)


class FilterRowsFeature(str, Enum):
    """Talend tFilterRow features mapped to v2 support levels (D-01, D-05)."""

    logical_op = "logical_op"
    conditions = "conditions"
    condition = "condition"
    reject_output = "reject_output"
    use_advanced = "use_advanced"
    advanced_cond = "advanced_cond"

    # Framework params
    tstatcatcher_stats = "tstatcatcher_stats"
    label = "label"


@REGISTRY.register("filter_rows", "filter")
class FilterRows(TransformComponent):
    """Filter rows based on a condition expression.

    Applies a boolean condition to the input LazyFrame and emits
    matching rows on the "main" output.  When ``reject_output`` is
    enabled, unmatched rows are emitted on a "reject" output and the
    component becomes a barrier (forces materialization so the engine
    can split the two streams).

    Config:
        condition: str -- v2 DSL expression that evaluates to boolean
            (required).
        reject_output: bool -- when True, emit rejected rows on the
            "reject" output (default False).

    Example:
        {"condition": "amount > 100 && status == 'active'"}
        {"condition": "amount > 100", "reject_output": true}
    """

    SUPPORTED_FEATURES: ClassVar[Dict[str, FeatureSupport]] = {
        FilterRowsFeature.logical_op: FeatureSupport(
            support=Support.FULL,
            note="AND/OR joining of multiple conditions, compiled to && / || in v2 DSL",
        ),
        FilterRowsFeature.conditions: FeatureSupport(
            support=Support.FULL,
            note="Stride-4 CONDITIONS table (INPUT_COLUMN, FUNCTION, OPERATOR, RVALUE) with all common FUNCTION pre-transforms compiled to v2 DSL",
        ),
        FilterRowsFeature.condition: FeatureSupport(
            support=Support.FULL,
            note="v2-native single expression string (superset of Talend CONDITIONS)",
        ),
        FilterRowsFeature.reject_output: FeatureSupport(
            support=Support.FULL,
            note="Opt-in: emitted only when job wires a reject flow; triggers engine barrier materialization",
        ),
        FilterRowsFeature.use_advanced: FeatureSupport(
            support=Support.UNSUPPORTED,
            note="Freeform Java expressions cannot run in Polars. Rewrite as a v2 expression using supported DSL functions.",
        ),
        FilterRowsFeature.advanced_cond: FeatureSupport(
            support=Support.UNSUPPORTED,
            note="Freeform Java expressions cannot run in Polars. Rewrite as a v2 expression using supported DSL functions.",
        ),
        FilterRowsFeature.tstatcatcher_stats: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="tStatCatcher is a v1/Talend concept; use Python logging instead",
        ),
        FilterRowsFeature.label: FeatureSupport(
            support=Support.FULL,
            note="Component label for display/debugging",
        ),
    }

    def _post_init(self) -> None:
        """Cache the compiled filter expression so apply() avoids re-parsing."""
        condition = self.config.get("condition", "")
        if condition:
            self._expr: pl.Expr = compile_expression(
                condition, self.context, routine_registry=self.routine_registry
            )
        else:
            self._expr = None  # type: ignore[assignment]

    @property
    def is_barrier(self) -> bool:
        """FilterRows is a barrier when reject output is enabled (two outputs)."""
        return self.config.get("reject_output", False)

    def validate(self) -> List[str]:
        errors = []
        if "condition" not in self.config:
            errors.append("FilterRows requires 'condition' in config")
        return errors

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        data = inputs.get("main")
        if data is None:
            return {}

        # Ensure LazyFrame
        if isinstance(data, pl.DataFrame):
            data = data.lazy()

        expr = self._expr

        if self.config.get("reject_output", False):
            # Two outputs: matched and rejected
            return {
                "main": data.filter(expr),
                "reject": data.filter(~expr),
            }

        return {"main": data.filter(expr)}
