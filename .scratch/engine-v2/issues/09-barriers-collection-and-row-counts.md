# 09 - Barriers, collection and row counts

Status: open
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
