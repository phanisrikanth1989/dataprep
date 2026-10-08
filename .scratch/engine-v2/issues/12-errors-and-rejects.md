# 12 - Errors and rejects

Status: resolved
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

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

- `die_on_error` is a declared key per component with v1's default for that
  component (false for the file inputs, true where v1's component says so);
  where a component declares none, the engine assumes true, as v1's base
  class does.
- Rejected rows carry the row's columns plus `errorCode` and `errorMessage`
  (v1's names). A row is unreadable when its text was there and could not be
  read, never because a value is missing.
- Every input row leaves by exactly one output: main and reject are two
  filters on one flag column.
- A component with a reject output always produces it, empty if need be.
- Errors: `JobRefusedError` (with the report), and a `JobResult` carrying
  `status`, `error`, `failed_component`, `failures`, `rows`, `global_map`,
  `context`; `raise_for_status()` raises `JobFailedError`.
