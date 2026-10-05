# 09 - Barriers, collection and row counts

Status: resolved
Type: grilling
Blocked by: 03, 08, 28

## Question

Lazy everywhere stays. What exactly happens at a barrier, and what row counts
can a lazy engine offer?

To settle:

- Which components are barriers, and why each one is.
- A component with several outputs: collected once for all of them, or once
  per output? As found, everything upstream runs again for each output.
- Sinks: collect and then write, or stream to disk. What the `streaming`
  setting means and whether it is a config key at all.
- Row counts. v1 publishes per-component counts (NB_LINE and friends) and
  users read them in trigger conditions and expressions. Which counts v2 can
  give at no extra cost, which it refuses, and what the job summary reports.
  As found, sinks report zero rows (finding 23).
- When component outputs are released from memory.
- Which component is named when a lazily read source turns out to hold bad
  data (finding 24). Hand this to
  [Errors and rejects](12-errors-and-rejects.md) if it belongs there.

Facts come from
[Polars facts: collection, streaming and Decimal](03-polars-facts-collection-streaming-decimal.md).
The counts decided here become globalMap entries in
[Context and globalMap](11-context-and-globalmap.md).

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

- Barriers are only the components that need rows in hand: context load and
  Python dataframe in pandas mode. Everything else stays lazy, log row
  included (it taps a few rows).
- A subjob is collected once: every file sink, every row count and every
  `tap`/`check` a component asked for go into one `pl.collect_all` on the
  streaming engine. Sinks stream to disk. There is no `streaming` config key;
  the engine is chosen by `V2_ENGINE` (default `streaming`).
- Row counts: a file output's `<id>_NB_LINE` is always set. Other
  components' `_NB_LINE`, `_NB_LINE_OK`, `_NB_LINE_REJECT` are counted only
  when a trigger condition or a config value names them. They are known when
  the subjob has finished.
- A failing lazy plan is blamed by recomputing each component's output in
  order until one fails; row problems are flagged, not raised, so most
  failures name their component directly.
