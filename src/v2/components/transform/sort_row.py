"""SortRow component for v2 engine.

Sorts rows by one or more columns with per-column direction and null positioning.
Equivalent of Talend tSortRow.

Config mapping:
  columns: list[dict]   -- sort column definitions (required)
  nulls_last: bool      -- default null positioning for all columns (default false)
  maintain_order: bool   -- preserve input order for equal-valued rows (default false)
"""
import logging
from enum import Enum
from typing import ClassVar, Dict, List

import polars as pl

from ..base import TransformComponent
from ..capabilities import FeatureSupport, Support
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


class SortRowFeature(str, Enum):
    """Talend tSortRow features mapped to v2 support levels."""

    criteria = "criteria"
    order = "order"
    label = "label"
    nulls_last = "nulls_last"
    maintain_order = "maintain_order"
    external = "external"
    tempfile = "tempfile"
    createdir = "createdir"
    external_sort_buffersize = "external_sort_buffersize"
    tstatcatcher_stats = "tstatcatcher_stats"
    sort_type = "sort_type"


@REGISTRY.register("sort_row")
class SortRow(TransformComponent):
    """Sort rows by one or more columns.

    Applies Polars ``LazyFrame.sort()`` with per-column direction and null
    positioning.  Stays lazy (not a barrier) -- the Polars optimizer decides
    when to materialize.

    Config:
        columns: list[dict] -- sort column definitions (required).
            Each dict must have:
                name: str -- column name to sort by (required)
                order: str -- "asc" or "desc" (default: "asc")
                nulls_last: bool -- place nulls after non-null values
                    (default: component-level nulls_last)
        nulls_last: bool -- default null positioning for all columns
            (default: false)
        maintain_order: bool -- preserve input order for equal-valued rows
            (default: false). Enables stable sort. Slightly slower and
            disables streaming optimization.

    Example:
        {"columns": [
            {"name": "date", "order": "desc"},
            {"name": "amount", "order": "asc", "nulls_last": true}
        ]}

    Example with component-level options:
        {
            "columns": [{"name": "category"}, {"name": "amount", "order": "desc"}],
            "nulls_last": true,
            "maintain_order": true
        }
    """

    SUPPORTED_FEATURES: ClassVar[Dict[str, FeatureSupport]] = {
        SortRowFeature.criteria: FeatureSupport(
            support=Support.FULL,
            note="Multi-column sort via Polars LazyFrame.sort() with by, descending, nulls_last parameters",
        ),
        SortRowFeature.order: FeatureSupport(
            support=Support.FULL,
            note="Per-column ASC/DESC mapped to Polars descending parameter",
        ),
        SortRowFeature.label: FeatureSupport(
            support=Support.FULL,
            note="Component label for display/debugging",
        ),
        SortRowFeature.nulls_last: FeatureSupport(
            support=Support.FULL,
            note="v2-native per-column null positioning via Polars nulls_last parameter",
        ),
        SortRowFeature.maintain_order: FeatureSupport(
            support=Support.FULL,
            note=(
                "Stable sort via Polars maintain_order parameter. Default false (unstable). "
                "Converter emits true for converted Talend jobs"
            ),
        ),
        SortRowFeature.external: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="JVM-specific memory management. Polars handles large dataset sorting natively via lazy execution",
        ),
        SortRowFeature.tempfile: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="Only relevant with EXTERNAL=true. Polars handles large dataset sorting natively",
        ),
        SortRowFeature.createdir: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="Only relevant with EXTERNAL=true. Polars handles large dataset sorting natively",
        ),
        SortRowFeature.external_sort_buffersize: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="Only relevant with EXTERNAL=true. Polars handles large dataset sorting natively",
        ),
        SortRowFeature.tstatcatcher_stats: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="tStatCatcher is a v1/Talend concept; use Python logging instead",
        ),
        SortRowFeature.sort_type: FeatureSupport(
            support=Support.NOT_PLANNED,
            note=(
                "Polars uses column dtype for comparison semantics "
                "(Int64 numerically, Utf8 lexicographically, Date chronologically). No equivalent needed"
            ),
        ),
    }

    def validate(self) -> List[str]:
        errors = []
        if "columns" not in self.config:
            errors.append("SortRow requires 'columns' in config")
            return errors

        columns = self.config["columns"]
        if not isinstance(columns, list):
            errors.append("SortRow 'columns' must be a list")
            return errors

        if len(columns) == 0:
            errors.append("SortRow 'columns' must not be empty")
            return errors

        for i, col in enumerate(columns):
            if not isinstance(col, dict):
                errors.append(f"SortRow column at index {i} must be a dict")
                continue
            if "name" not in col:
                errors.append(f"SortRow column at index {i} requires 'name'")
                continue
            if not isinstance(col["name"], str):
                errors.append(f"SortRow column 'name' must be a string at index {i}")
                continue
            name = col["name"]
            if "order" in col:
                order_val = col["order"]
                if not isinstance(order_val, str) or order_val.lower() not in ("asc", "desc"):
                    errors.append(
                        f"SortRow column '{name}' has invalid order '{order_val}', "
                        f"must be 'asc' or 'desc'"
                    )
            if "nulls_last" in col and not isinstance(col["nulls_last"], bool):
                errors.append(
                    f"SortRow column '{name}' has invalid nulls_last, must be boolean"
                )

        if "nulls_last" in self.config and not isinstance(self.config["nulls_last"], bool):
            errors.append("SortRow 'nulls_last' must be a boolean")
        if "maintain_order" in self.config and not isinstance(self.config["maintain_order"], bool):
            errors.append("SortRow 'maintain_order' must be a boolean")

        return errors

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        data = inputs.get("main")
        if data is None:
            return {}

        # Ensure LazyFrame
        if isinstance(data, pl.DataFrame):
            data = data.lazy()

        columns = self.config.get("columns", [])
        default_nulls_last = self.config.get("nulls_last", False)
        maintain_order = self.config.get("maintain_order", False)

        sort_cols = []
        descending = []
        nulls_last = []

        for col in columns:
            sort_cols.append(col["name"])
            if "order" in col:
                descending.append(col["order"].lower() == "desc")
            else:
                descending.append(False)
            nulls_last.append(col.get("nulls_last", default_nulls_last))

        result = data.sort(
            sort_cols,
            descending=descending,
            nulls_last=nulls_last,
            maintain_order=maintain_order,
        )

        logger.debug(
            f"SortRow applied: columns={sort_cols}, descending={descending}, "
            f"nulls_last={nulls_last}, maintain_order={maintain_order}"
        )
        return {"main": result}
