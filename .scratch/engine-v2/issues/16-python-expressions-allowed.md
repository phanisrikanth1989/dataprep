# 16 - Python expressions: what is allowed and how it reads

Status: open
Type: grilling
Blocked by: 15

## Question

Define the expression language. Settled already: expressions are Python,
translated once into Polars when the job loads, never run row by row, and an
expression that cannot be translated is refused. Open: exactly which Python,
and how it reads.

To settle:

- References: `row1.col` and `row1['col']`, variables (`Var.x`), context,
  globalMap, and bare column names where a component has one input.
- The allowed Python: operators; conditional expressions; `and` / `or` /
  `not`; `in`; `is None`; slicing; string methods; built-ins; `re`, `math`,
  `datetime`, `Decimal`. Everything else is refused with a message that says
  what to do instead.
- Results against the answer key. Where Polars' result differs from the
  row-by-row Python v1 runs (None propagation, an error on one row): match
  it, refuse the construct, or put it on the list of deliberate differences.
- Long expressions: named intermediate steps (Map variables) and anything
  else that keeps a long expression readable. Deeply nested calls that were
  hard to follow are why the old language is going.
- Whether a marked escape into a raw Polars expression exists.
- Result types and casts.
- The fate of the old tokenizer, parser, compiler and function list.

Evidence comes from
[Expression translator spike](15-expression-translator-spike.md) and, if in,
[Usage count of real v1 jobs](01-usage-count-of-real-v1-jobs.md). Findings 10
to 16 in [v2 engine as found](../research/2026-10-05-v2-as-found.md#verified-findings)
describe what the old language got wrong.
