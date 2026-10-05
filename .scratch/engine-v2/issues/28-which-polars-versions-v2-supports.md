# 28 - Which Polars versions v2 supports

Status: open
Type: grilling

## Question

The repo pins `polars>=1.38,<2.0`, and Polars' behaviour changes inside that
range in ways the answer key can see. Which versions does v2 support and test
against?

Changes inside the range, from
[Polars facts: collection, streaming and Decimal](03-polars-facts-collection-streaming-decimal.md):

- Decimal `sum`: the result type widened in 1.40/1.41, and overflow wrapped
  silently before 1.44.0.
- Several outputs of one plan: the rule that keeps a shared part when a
  branch filter cannot be pushed into it is new in 1.43.0.
- The streaming engine was marked unstable until 1.41.0.
- 2.0 is in pre-release, makes streaming the default, and is outside the pin.

To settle:

- Which Polars version the target servers run, or can be given, and whether
  that can be held to one version. This is a fact the user supplies.
- One supported version, a narrow range, or the present range with tests at
  both ends.
- Which version the answer-key tests and the benchmarks run on.
- When and how the pin moves, 2.0 in particular.

Surfaced while resolving the research tickets; add any further in-range
changes they report.
