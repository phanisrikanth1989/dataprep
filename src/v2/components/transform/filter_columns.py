"""FilterColumns component for v2 engine.

Filters (selects or removes) columns from the input schema.
Equivalent of Talend tFilterColumns.

Config mapping:
  columns: list     -- column specs (str or {name, source} dicts)
  mode: str         -- "keep" (default) or "remove"
"""
import logging
from enum import Enum
from typing import Any, ClassVar, Dict, List

import polars as pl

from ..base import TransformComponent
from ..capabilities import FeatureSupport, Support
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


class FilterColumnsFeature(str, Enum):
    """Talend tFilterColumns features mapped to v2 support levels (D-01, D-05)."""

    columns = "columns"
    mode = "mode"  # REMOVE_OR_KEEP param: "keep" or "remove"

    # Framework params
    tstatcatcher_stats = "tstatcatcher_stats"
    label = "label"


@REGISTRY.register("filter_columns")
class FilterColumns(TransformComponent):
    """Select or remove columns from the data.

    Config:
        columns: list -- column names to keep (or remove if mode="remove").
            Each element can be a plain string or a dict
            with "name" and optional "source" for renaming.
        mode: str -- "keep" (default) or "remove". "keep" selects only
            the listed columns. "remove" drops the listed columns and
            keeps everything else.

    Example:
        {"columns": ["id", "name", "amount"]}
        {"columns": ["temp_col"], "mode": "remove"}
    """

    SUPPORTED_FEATURES: ClassVar[Dict[str, FeatureSupport]] = {
        FilterColumnsFeature.columns: FeatureSupport(
            support=Support.FULL,
            note="Column list with optional source->name rename mapping",
        ),
        FilterColumnsFeature.mode: FeatureSupport(
            support=Support.FULL,
            note="'keep' (default) selects listed columns; 'remove' drops them",
        ),
        FilterColumnsFeature.tstatcatcher_stats: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="tStatCatcher is a v1/Talend concept; use Python logging instead",
        ),
        FilterColumnsFeature.label: FeatureSupport(
            support=Support.FULL,
            note="Component label for display/debugging",
        ),
    }

    def validate(self) -> List[str]:
        errors = []
        if "columns" not in self.config:
            errors.append("FilterColumns requires 'columns' in config")
        mode = self.config.get("mode", "keep")
        if mode not in ("keep", "remove"):
            errors.append(f"FilterColumns 'mode' must be 'keep' or 'remove', got '{mode}'")
        return errors

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        data = inputs.get("main")
        if data is None:
            return {}

        if isinstance(data, pl.DataFrame):
            data = data.lazy()

        columns = self.config.get("columns", [])
        mode = self.config.get("mode", "keep")

        if mode == "remove":
            # Drop the listed columns, keep everything else
            drop_names = []
            for col in columns:
                if isinstance(col, str):
                    drop_names.append(col)
                else:
                    drop_names.append(col["name"])
            return {"main": data.drop(drop_names)}

        # mode == "keep": select only the listed columns
        select_exprs = []
        for col in columns:
            if isinstance(col, str):
                select_exprs.append(pl.col(col))
            else:
                source = col.get("source", col["name"])
                name = col["name"]
                select_exprs.append(pl.col(source).alias(name))

        return {"main": data.select(select_exprs)}
