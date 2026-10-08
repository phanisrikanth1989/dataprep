# 16 - Python expressions: what is allowed and how it reads

Status: resolved
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
- The baseline. v1's PyMap is not plain Python: it hands pandas rows to
  `eval`, and a missing value arrives as `nan`, even in a string column, not
  as `None`. Is the answer key for an expression what Python would do, or
  what v1's PyMap does?
- Results against the answer key. Where Polars' result differs from the
  row-by-row Python v1 runs (None propagation, an error on one row, `round`
  with digits, keyword logic on integers): match it, refuse the construct,
  or put it on the list of deliberate differences.
- Types at load. A faithful translation needs each operand's declared type
  when the job loads, because `+`, `len`, `in`, `not` and `and` / `or` map
  differently per type. Where those types come from for every reference:
  schema columns, lookup columns, variables, context.
- Long expressions: named intermediate steps (Map variables) and anything
  else that keeps a long expression readable. Deeply nested calls that were
  hard to follow are why the old language is going.
- Whether a marked escape into a raw Polars expression exists.
- Result types and casts.
- The fate of the old tokenizer, parser, compiler and function list.

Evidence comes from
[Translating Python expressions to Polars: prior art and mapping](04-python-expressions-to-polars-prior-art.md)
(the mapping table and the table of differences),
[Expression translator spike](15-expression-translator-spike.md) and, if in,
[Usage count of real v1 jobs](01-usage-count-of-real-v1-jobs.md). Findings 10
to 16 in [v2 engine as found](../research/2026-10-05-v2-as-found.md#verified-findings)
describe what the old language got wrong.

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

- References: `row1.col`, `row1['col']`, bare `col` where there is one
  input, `Var.x`, `context.x`, `globalMap.get("k"[, default])`.
- Allowed: arithmetic and comparison operators, `a if c else b`, `and` /
  `or` / `not`, `in`, `is None`, slicing, f-strings, the string methods and
  built-ins listed in `src/v2/expressions/functions.py`, parts of `re`,
  `math`, `datetime`, `Decimal`, and routines. Anything else is refused at
  load with what to write instead where there is a known hint (Java
  left-overs such as `&&`, `null`, `.equals`).
- The baseline is Python's meaning, made total: a missing value propagates
  instead of raising; `==` / `!=` treat a missing value as a value;
  truthiness follows the operand's type. Mixed text and number operands are
  refused rather than guessed.
- Operand types come from the frame's schema at translation time.
- Long expressions: Map variables (`Var.name`), each able to use the ones
  before it.
