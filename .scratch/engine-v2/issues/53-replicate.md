# 53 - Replicate

Status: resolved
Type: task

## Question

Build v1's replicate (`Replicate`, `tReplicate`) on v2: the same rows to
every flow that leaves.

One of the 26 components the dev asked for on 2026-10-11 ("take 20-30 more
components and build them in v2"; the list is the dev's to change, the
building is delegated end to end).

## Answer

Built on 2026-10-11 (`src/v2/components/transform/replicate.py`; 7 tests in
`tests/v2/components/test_replicate.py`, against v1).

- The engine already hands one output to every flow that leaves by it, and
  reads the rows once. The component hands its input on.
- `output_count` is accepted and ignored: the flows decide.
- Row numbers pass. No difference from v1.
