# 03 - Polars facts: collection, streaming and Decimal

Status: resolved
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

## Answer

Resolved 2026-10-05 by a research agent. The full note, every claim cited:
[Polars facts: collection, streaming, sinks, row counts, Decimal, errors, order](../research/2026-10-05-polars-collection-streaming-decimal.md)
(also on the throwaway branch `research/polars-collection-streaming-decimal`,
commit `61d57a5a`). Facts are read at both ends of the pin, tags `py-1.38.0`
and `py-1.44.2`. Only 1.44.2 was run, on one Mac, so everything the note marks
Observed is provisional for the target servers.

The gist, by sub-question:

1. Several outputs of one plan. Two `.collect()` calls each re-run the shared
   upstream, and `.cache()` does not carry across collects. `pl.collect_all`
   runs its frames as one plan, but sharing is the optimizer's choice. Main
   and reject written as `filter(c)` / `filter(~c)` on a shared scan read the
   source twice on 1.44.2, even with `.cache()`. Filtering on a computed flag
   column, or a shared part ending in `with_row_index`, `group_by` or
   `unique`, reads it once. The rule that keeps the shared part is new in
   1.43.0.
2. Streaming. `collect()` defaults to the in-memory engine across the pin;
   sinks default to streaming. Streaming was marked unstable until 1.41.0. A
   full sort always materialises its input; some group-bys,
   `unique(keep="last", maintain_order=True)` and validated joins fall back
   to in-memory per node. There is no supported out-of-core sort, group-by or
   join.
3. Sinks. `write_csv` / `write_parquet` are thin wrappers over `sink_csv` /
   `sink_parquet`, with the same options and byte-identical CSV. Several lazy
   sinks share one source pass only under
   `collect_all(..., engine="streaming")`; the default engine reads the
   source once per sink.
4. Row counts. Sinks return `None` and `sink_csv` has no rows-written hook.
   Counting in the sink's own pass works by collecting the lazy sink and
   `select(pl.len())` together on the streaming engine, at no measurable
   cost. `lazy=True` on sinks is marked unstable.
5. Decimal. `pl.Decimal` is stable since 1.35.0 (128-bit, precision up to 38,
   fixed scale), so the "Polars doesn't have Decimal" comment in v2 is out of
   date. But `*` and `/` round half-to-even to the operands' scale:
   `1.25 * 1.25 = 1.56` and `1 / 3 = 0.33`, where Python's `Decimal` gives
   `1.5625` and 28 digits. `sum` changed inside the pin: its type widened in
   1.40/1.41 and overflow wrapped silently before 1.44.0. `mean` is Float64,
   Decimal with a float gives Float64, and `//`, `%` and `**` are
   unsupported.
6. Errors. Cast and parse errors surface only when the collect or sink runs.
   The exception is a message naming the column, not the file, row or
   component, and whether a strict cast raises can depend on predicate
   pushdown. A sink that fails part-way leaves a partial file (observed; no
   source covers it).
7. Order. `group_by` and `unique` need `maintain_order=True`. A join without
   it kept left order on the in-memory engine but not on streaming.
   `pl.union` interleaves on streaming; `pl.concat` does not.

Re-checked independently on polars 1.44.2 before the note was accepted
(scripts not kept): the Decimal results and types in 5; `sink_csv` returning
`None`, byte-identical `write_csv` / `sink_csv` output and counting beside a
lazy sink in 3 and 4; the join-order difference in 7; and, with `explain_all`
on a CSV scan, the shared-plan cases in 1.

Could not establish (the note's last section has the detail): the behaviour
of releases between the two ends of the pin, other than by reading tags and
release notes; any general row-order guarantee for the streaming engine;
whether the partial file after a failed sink is a contract; a supported row
count from `sink_csv`; memory bounds for streaming group-by and join.

Surfaced: Polars' behaviour changes inside the pinned range in ways the
answer key can see. Which versions v2 supports is now its own ticket,
[Which Polars versions v2 supports](28-which-polars-versions-v2-supports.md).
