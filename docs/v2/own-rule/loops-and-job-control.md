# Loops and job control

The components that start a loop, and the ones that steer a job as a
whole.

Built to their own rule: what is written here is what they are held to,
not v1. ([What that means](README.md).) How a loop runs, whatever starts
it, is in [How a job runs](../how-a-job-runs.md#loops): one pass after
another, a pass that fails stops the loop, a cap on the items.

## Foreach

- Starts a loop over `values`: what its iterate link leads to runs once
  for each value, in the order written.
- In a pass the value is in globalMap as `<id>_CURRENT_VALUE`, and the
  number of the pass as `<id>_CURRENT_ITERATION`. The value is text, as
  in Talend: `007` stays `007`, and a value written as a number is the
  text of it.
- A value may name a context variable (`${context.x}`). It is put in
  when the component runs, before the first pass.
- No value, no pass. `<id>_NB_LINE` is how many values there are (v1's
  entry; Talend has none).
- `max_items` is the most values the loop may have (100,000 when not
  given).
