"""Unpivot row: the columns that are not keys become rows of a name and a value."""
from __future__ import annotations

import logging
from typing import Dict, List

import polars as pl

from ...column_types import to_text
from ...errors import ConfigurationError
from ...job.keys import Key
from ...rows import hidden, visible
from ..base import Transform
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register
class UnpivotRow(Transform):
    """Hand on, for every column that is not a key, one row for each input row: the keys, the column's name, its value.

    The rows come out column by column, as in v1: every row's value of the
    first such column, then every row's value of the second. The value is
    the text of what the column holds. A row with no value is kept unless
    `include_empty_values` is off; text with nothing in it is a value.

    Each row carries the row number of the row it was made from.
    """

    names = ("unpivot_row", "UnpivotRow", "tUnpivotRow")
    keys = (
        Key("row_keys", type=list, required=True, doc="The columns kept beside every value."),
        Key("pivot_key", default="pivot_key", doc="The name of the column that holds the column names."),
        Key("pivot_value", default="pivot_value", doc="The name of the column that holds the values."),
        Key("include_empty_values", type=bool, default=True, doc="Whether a row with no value is kept."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether keys that cannot be used fail the job; off, the component hands on no rows."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        config = self.config
        types = frame.collect_schema()
        names, carried = visible(types.names()), hidden(types.names())
        keys: List[str] = [str(name) for name in config["row_keys"]]
        name_column, value_column = config["pivot_key"], config["pivot_value"]
        empty = frame.clear().select(
            [pl.col(name) for name in keys if name in names]
            + [pl.lit(None, dtype=pl.String).alias(name_column), pl.lit(None, dtype=pl.String).alias(value_column)]
            + carried
        )

        missing = [name for name in keys if name not in names]
        wrong = "names no column" if not keys else f"there is no column '{missing[0]}'" if missing else ""
        if wrong:
            if config["die_on_error"]:
                raise ConfigurationError(f"row_keys: {wrong}")
            logger.error(f"[{self.id}] row_keys: {wrong}; no rows are handed on")
            return {"main": empty}
        values = [name for name in names if name not in keys]
        if not values:
            return {"main": empty}

        as_text = frame.with_columns([to_text(pl.col(name), types[name]).alias(name) for name in values])
        made = as_text.unpivot(on=values, index=keys + carried, variable_name=name_column, value_name=value_column)
        if not config["include_empty_values"]:
            made = made.filter(pl.col(value_column).is_not_null())
        return {"main": made.select(keys + [name_column, value_column] + carried)}
