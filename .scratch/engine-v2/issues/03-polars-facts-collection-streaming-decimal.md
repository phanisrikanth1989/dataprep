# 03 - Polars facts: collection, streaming and Decimal

Status: open
Type: research

## Question

What does Polars guarantee about collecting, streaming, ordering, errors and
decimals? Primary sources only, stamped against the range this repo pins
(`polars>=1.38,<2.0`; 1.44.2 is installed), with the version noted wherever
behaviour changed inside that range.

Specifically:

1. Collecting several outputs of one plan: `pl.collect_all`, common-subplan
   elimination, cache nodes; whether two separate `.collect()` calls on frames
   that share an upstream re-read the source.
2. The streaming engine: its status across the pinned range, how it is
   selected (`engine="streaming"`), which operations fall back to in-memory,
   and how sorts, joins, group-bys and unique behave under it.
3. Sinks: `sink_csv` and `sink_parquet` -- streaming behaviour, option parity
   with `write_csv` / `write_parquet`, and writing several sinks from one plan
   in one pass.
4. Row counts without a second pass: whether a collect or a sink can report
   how many rows passed through; the cost of counting on a shared plan.
5. Decimal: the status of `pl.Decimal` across the pinned range (stable or
   not, precision and scale limits, arithmetic, aggregation, rounding mode,
   casting from strings, CSV read and write), compared with Python's
   `decimal.Decimal`.
6. Errors in lazy plans: when cast and parse errors surface; whether the
   failing source or column can be identified from the exception; what
   `strict=False` does.
7. Order: which operations keep row order (joins, `group_by`, `unique`,
   `concat`, the streaming engine) and which need `maintain_order`.

Feeds [Barriers, collection and row counts](09-barriers-collection-and-row-counts.md),
[Types, nulls and schemas](13-types-nulls-and-schemas.md),
[The performance bar](05-performance-bar.md) and
[Errors and rejects](12-errors-and-rejects.md).
