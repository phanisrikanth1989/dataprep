"""
Aggregate Component for v2 Engine.

Groups and aggregates data.
"""
import logging
from typing import Dict, List, Optional

import polars as pl

from ..base import TransformComponent
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("aggregate", "aggregate_rows")
class Aggregate(TransformComponent):
    """
    Group and aggregate data.

    Config options:
        group_by: list - Columns to group by (optional).
            Each element is a string (column name) or a dict with:
                input: str - Input column name (required)
                output: str - Output column name (default: same as input)
        aggregations: list - Aggregation definitions (required).
            Each element is a dict with:
                name: str - Output column name (required)
                function: str - Aggregate function (required)
                column: str - Column to aggregate (required for non-count functions)
                ignore_nulls: bool - Ignore null values (default: true)
                separator: str - Delimiter for list function (default: ",")
        maintain_order: bool - Preserve input row order in grouped output (default: false).
            Enables stable grouping. Slightly slower.

    Supported functions:
        sum, count, avg/mean, min, max, first, last,
        count_distinct/n_unique, std, var, median, list

    Example:
        {
            "group_by": ["customer_id", "product"],
            "aggregations": [
                {"name": "total_amount", "function": "sum", "column": "amount"},
                {"name": "order_count", "function": "count", "column": "*"},
                {"name": "avg_price", "function": "avg", "column": "unit_price"},
                {"name": "products", "function": "list", "column": "product_name", "separator": ";"}
            ]
        }

    Example with column renaming and maintain_order:
        {
            "group_by": [
                "region",
                {"input": "customer_id", "output": "cust_id"}
            ],
            "aggregations": [
                {"name": "total", "function": "sum", "column": "amount"},
                {"name": "first_name", "function": "first", "column": "name", "ignore_nulls": true}
            ],
            "maintain_order": true
        }
    """

    VALID_FUNCTIONS = {
        "sum", "count", "avg", "mean", "min", "max",
        "first", "last", "count_distinct", "n_unique",
        "std", "var", "median", "list",
    }

    def validate(self) -> List[str]:
        errors = []
        if "aggregations" not in self.config:
            errors.append("Aggregate requires 'aggregations' in config")
            return errors

        aggregations = self.config["aggregations"]
        if not isinstance(aggregations, list):
            errors.append("Aggregate 'aggregations' must be a list")
            return errors

        if len(aggregations) == 0:
            errors.append("Aggregate 'aggregations' must not be empty")
            return errors

        for i, agg in enumerate(aggregations):
            if not isinstance(agg, dict):
                errors.append(f"Aggregation at index {i} must be a dict")
                continue
            if "name" not in agg:
                errors.append(f"Aggregation at index {i} requires 'name'")
                continue
            if not isinstance(agg["name"], str):
                errors.append(f"Aggregation 'name' must be a string at index {i}")
                continue
            name = agg["name"]
            if "function" not in agg:
                errors.append(f"Aggregation at index {i} requires 'function'")
                continue
            if not isinstance(agg["function"], str):
                errors.append(f"Aggregation 'function' must be a string at index {i}")
                continue
            func = agg["function"].lower()
            if func not in self.VALID_FUNCTIONS:
                errors.append(
                    f"Aggregation '{name}' has unknown function '{func}'"
                )
            if func != "count" and "column" not in agg:
                errors.append(
                    f"Aggregation '{name}' requires 'column' for function '{func}'"
                )
            if "ignore_nulls" in agg and not isinstance(agg["ignore_nulls"], bool):
                errors.append(
                    f"Aggregation '{name}' has invalid ignore_nulls, must be boolean"
                )
            if "separator" in agg and not isinstance(agg["separator"], str):
                errors.append(
                    f"Aggregation '{name}' has invalid separator, must be a string"
                )

        if "group_by" in self.config:
            group_by = self.config["group_by"]
            if not isinstance(group_by, list):
                errors.append("Aggregate 'group_by' must be a list")
            else:
                for i, entry in enumerate(group_by):
                    if isinstance(entry, str):
                        continue
                    if not isinstance(entry, dict):
                        errors.append(f"Group by entry at index {i} must be a string or dict")
                        continue
                    if "input" not in entry:
                        errors.append(f"Group by entry at index {i} requires 'input'")

        if "maintain_order" in self.config and not isinstance(self.config["maintain_order"], bool):
            errors.append("Aggregate 'maintain_order' must be a boolean")

        return errors

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        data = inputs.get("main")
        if data is None:
            return {}

        if isinstance(data, pl.DataFrame):
            data = data.lazy()

        group_by_config = self.config.get("group_by", [])
        aggregations = self.config["aggregations"]
        maintain_order = self.config.get("maintain_order", False)

        # Parse group_by: extract column names for grouping
        group_by_cols = []
        rename_map = {}
        for entry in group_by_config:
            if isinstance(entry, str):
                group_by_cols.append(entry)
            elif isinstance(entry, dict):
                input_col = entry["input"]
                output_col = entry.get("output", input_col)
                group_by_cols.append(input_col)
                if output_col != input_col:
                    rename_map[input_col] = output_col

        # Build aggregation expressions
        agg_exprs = []
        for agg in aggregations:
            name = agg["name"]
            func = agg["function"].lower()
            column = agg.get("column", "*")
            ignore_nulls = agg.get("ignore_nulls", True)
            separator = agg.get("separator", ",")

            expr = self._build_agg_expr(func, column, name, ignore_nulls, separator)
            if expr is not None:
                agg_exprs.append(expr)

        # Apply grouping and aggregation
        if group_by_cols:
            result = data.group_by(group_by_cols, maintain_order=maintain_order).agg(agg_exprs)
        else:
            result = data.select(agg_exprs)

        # Apply group_by column renaming
        if rename_map:
            result = result.rename(rename_map)

        logger.debug(
            f"Aggregating with {len(agg_exprs)} functions, "
            f"group_by={group_by_cols}, maintain_order={maintain_order}"
        )

        return {"main": result}

    def _build_agg_expr(
        self, func: str, column: str, name: str,
        ignore_nulls: bool = True, separator: str = ","
    ) -> Optional[pl.Expr]:
        """Build a Polars aggregation expression."""
        # List function: concat values as delimited string
        if func == "list":
            if ignore_nulls:
                return (
                    pl.col(column).drop_nulls().cast(pl.Utf8)
                    .implode().list.join(separator).alias(name)
                )
            else:
                return (
                    pl.col(column).cast(pl.Utf8).fill_null("null")
                    .implode().list.join(separator).alias(name)
                )

        # Count: ignore_nulls controls whether to count all rows or non-null only
        if func == "count":
            if column == "*" or not ignore_nulls:
                return pl.len().alias(name)
            else:
                return pl.col(column).count().alias(name)

        # First/last: ignore_nulls controls whether to skip nulls
        if func == "first":
            if ignore_nulls:
                return pl.col(column).drop_nulls().first().alias(name)
            else:
                return pl.col(column).first().alias(name)

        if func == "last":
            if ignore_nulls:
                return pl.col(column).drop_nulls().last().alias(name)
            else:
                return pl.col(column).last().alias(name)

        # Standard aggregations (Polars ignores nulls by default for these)
        agg_map = {
            "sum": lambda c: pl.col(c).sum(),
            "avg": lambda c: pl.col(c).mean(),
            "mean": lambda c: pl.col(c).mean(),
            "min": lambda c: pl.col(c).min(),
            "max": lambda c: pl.col(c).max(),
            "count_distinct": lambda c: pl.col(c).n_unique(),
            "n_unique": lambda c: pl.col(c).n_unique(),
            "std": lambda c: pl.col(c).std(),
            "var": lambda c: pl.col(c).var(),
            "median": lambda c: pl.col(c).median(),
        }

        if func not in agg_map:
            raise ValueError(
                f"Unknown aggregation function: '{func}'. "
                f"Valid functions: {', '.join(sorted(self.VALID_FUNCTIONS))}"
            )

        return agg_map[func](column).alias(name)
