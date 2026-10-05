# 05 - The performance bar

Status: open
Type: grilling

## Question

When is a config key too slow to support? The rule is "refused if Polars
cannot do it natively, or only with a large slowdown". It needs a test that
anyone can apply to a v1 capability and reach the same verdict, because every
key-by-key ticket applies it dozens of times.

To settle:

- What "native" means. No Python callback is clear. May a supported key force
  an eager read or an extra collect? v2 as found reads the whole file eagerly
  when `footer_rows` is set, and collects at the source when `die_on_error`
  is false.
- What "large slowdown" means, and against what. The existing gate compares a
  component with hand-written Polars doing the same thing (within 10%), which
  any native implementation passes by construction. Is the baseline the same
  job without the key? A fixed budget per key? Memory as well as time?
- Who pays: a cost only when the key is used, versus a cost on every job
  because the key exists at all.
- How a verdict is measured and recorded so it can be reproduced: data size,
  machine, harness, and whether the measurement is stored with the declared
  key.
- Worked verdicts for a few known hard cases, to calibrate the bar: footer
  rows; a non-UTF-8 encoding; `die_on_error: false` at a source;
  case-insensitive unique keys; Map lookups that keep all matches.

Use the two Polars facts tickets
([delimited files](02-polars-facts-delimited-files.md),
[collection, streaming and Decimal](03-polars-facts-collection-streaming-decimal.md))
where they are resolved; this ticket does not wait for them.
