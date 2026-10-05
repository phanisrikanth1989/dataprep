# 12 - Errors and rejects

Status: open
Type: grilling
Blocked by: 08

## Question

What happens when a row or a component fails?

To settle:

- `die_on_error`. v1 has a base default of true, but several components read
  their own key with a default of false (`agents/schemas/config-surfaces.md`
  calls it the dual-default landmine). Which default applies to each
  component is set by the answer key; settle how that is declared.
- Reject outputs: which components have one, which columns a rejected row
  carries (v1's names versus v2's `_error_message`), and how an error is
  detected. As found, an error is "this value became null", which also
  catches values that were legitimately null.
- Row conservation: every input row ends in exactly one output. As found,
  filter rows with a reject output drops rows whose condition is null
  (finding 5).
- Naming the failing component under lazy execution. As found, bad data in a
  source fails at the sink and the error names nothing (finding 24).
- Exception types (v1 has the `ETLError` family in
  `src/v1/engine/exceptions.py`) and what the job result contains.

Facts on when Polars raises come from
[Polars facts: collection, streaming and Decimal](03-polars-facts-collection-streaming-decimal.md).
