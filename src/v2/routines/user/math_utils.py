"""
MathUtils - Vectorized math utility functions for v2 engine.

All functions are Tier 1 (vectorized) operating on pl.Series
for maximum performance via map_batches instead of map_elements.

Each function declares:
  _vectorized = True     -> use map_batches (column-level, not row-level)
  _return_dtype          -> explicit Polars dtype for lazy mode compatibility
"""
import polars as pl


def percentage(amount: pl.Series, total: pl.Series) -> pl.Series:
    """
    Calculate percentage: (amount / total) * 100.

    Returns null where total is 0 or null.
    """
    df = pl.DataFrame({"a": amount, "t": total})
    return df.select(
        (pl.col("a")
         / pl.when(pl.col("t") == 0).then(None).otherwise(pl.col("t"))
         * 100).round(2)
    ).to_series()

percentage._vectorized = True
percentage._return_dtype = pl.Float64


def clamp(value: pl.Series, low: pl.Series, high: pl.Series) -> pl.Series:
    """
    Clamp values to [low, high] range.
    """
    df = pl.DataFrame({"v": value, "lo": low, "hi": high})
    return df.select(
        pl.when(pl.col("v") < pl.col("lo")).then(pl.col("lo"))
        .when(pl.col("v") > pl.col("hi")).then(pl.col("hi"))
        .otherwise(pl.col("v"))
    ).to_series()

clamp._vectorized = True
clamp._return_dtype = pl.Float64


def margin(revenue: pl.Series, cost: pl.Series) -> pl.Series:
    """
    Calculate profit margin: ((revenue - cost) / revenue) * 100.

    Returns null where revenue is 0 or null.
    """
    df = pl.DataFrame({"r": revenue, "c": cost})
    return df.select(
        ((pl.col("r") - pl.col("c"))
         / pl.when(pl.col("r") == 0).then(None).otherwise(pl.col("r"))
         * 100).round(2)
    ).to_series()

margin._vectorized = True
margin._return_dtype = pl.Float64
