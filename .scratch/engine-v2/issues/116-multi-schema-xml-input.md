# 116 - Multi-schema XML input

Status: resolved
Type: task

## Question

Build the multi-schema XML input (`FileInputMSXML`, `tFileInputMSXML`):
one document, its records of several kinds each to a flow of their own,
to [XML: the decisions](110-xml-the-decisions.md).

## What is known

- Talend's rules, read in Talaxie's `tFileInputMSXML` at `639d5fd1f776`:
  - `ROOT_LOOP_QUERY` finds the elements the records stand in. Each row
    of `SCHEMAS` has four items: the schema (the flow it feeds), a loop
    path from a root element, the mapping, and "create empty row".
  - The mapping is one text of paths with commas between, one for each
    column of the flow in their order. It is taken apart at the commas
    outside square brackets, so a function with a comma in it cannot
    be written there.
  - A record all of whose values are nil, empty or missing gives no
    row, unless empty rows are asked for.
  - "Trim all" is on by default. There is no reject output.
  - With "ignore order" off, the children of a root element are gone
    through in the order of the document and each is handed to the
    flow whose loop path is its name.
- The converter reads three of the four items (not the schema), and
  writes one schema for the component. v1's component reads one kind of
  record only, by the names of the columns.

## Answer

Built on 2026-10-12: `src/v2/components/file/file_input_msxml.py` (61
tests in `tests/v2/components/test_file_input_msxml.py`, 38 of them
seen failing first for want of the component).

- **The config says what today's cannot.** Each entry of `schemas` has
  a `flow` and its `columns` (v2's own keys). One entry alone needs
  neither, which is the shape a converted job has: it loads as it is.
- **One walk for all the kinds.** `xml_reader.Several` goes through the
  document once and hands back each record with its kind. The reader
  for one kind (`Records`) is now the case of one of it; the XML file
  input reads as fast as before (23 MB a second before and after).
- **What is read is let go of, unless something above still reads it.**
  A record of one flow may hold the records of another: the inner ones
  stay until the outer one has been read. Asked only where one kind's
  path can stand in another's, so one kind alone pays nothing for it.
- **A component may now say columns of its own.** The keys of a
  schema's column moved from the loader to `job/columns.py`, where a
  component can reach them.
- A text of paths is taken apart at the commas outside the brackets of
  a function and outside quotes: what Talend takes apart rightly is
  taken apart the same, and a function may be written too.

### Decided on the way

- **No reject output**, as in Talend. The rows of the flows have
  different columns, and one output could hold them only as text of
  their records. A row that cannot be read fails the job, or is
  dropped with a warning that names the first.
- **An entry's own columns win** over the component's schema, with no
  refusal: a job fixed by hand keeps what the converter left there.
- **`ignore_order` has no effect.** Talend's order is the order rows of
  different flows are handed on in, one by one. A flow here is a set of
  rows of its own; each keeps the order of the document.

**Measured** (a Mac): a document of 100 MB, two kinds (124,000 orders,
and the 497,000 items in them) in one pass: 4.5 s, 22 MB a second.

## A fault found in the XML file input on the way

**A record whose number or date was not there lost its row.** Not
turned away: gone, with no warning. The check "was text there that
could not be read" answered "unknown" for a text that is not there at
all, and a row with that answer was neither among the rows read nor
among those turned away. A delimited file has empty text for an empty
field, never nothing, so no reader before the XML one could ask it.

Found when the first test of empty rows here kept one row of four.
Fixed at its source (`column_types.unreadable` answers yes or no), with
a test in the file input and one for the check itself. Ticket 111's
tests and its mutation check missed it: no test there had a record
without its number.

It was in the tree for some hours and was never pushed.

## Mutation check

Sixty-five ways of breaking the component, the walk of several kinds
and the check of text that is not there. Fifty were caught at first:
the tests of this component were looser than they should have been.
Of the fifteen others:

- **Three showed code that did nothing, and it went**: counting square
  brackets when a text of paths is taken apart (XPath has a comma only
  in a function's brackets and in quotes, which are counted), a second
  check that an entry had nothing wrong, and a guard for the missing
  library that the engine already has.
- **Ten got a stronger test**: a flow where several entries name none;
  an entry with no columns beside a component that has a schema; a
  function and a text in quotes written without Talend's quotes; that a
  flow nobody reads is not looked for; that the document is gone
  through once when the engine reads the source twice; the batches,
  counted exactly; two kinds that both wait for what is above them; a
  kind that waits beside one that does not; several nodes in a second
  kind.
- **Two change nothing that is written**: they make the question
  "may one kind's path stand in another's" say yes more often, which
  costs time and no row.

All twelve that could be caught were run again, and were.

## How it was built

Tests first for the component as a whole. Written after their code,
with the mutation check standing in: the batches, a run for a few
records, the key of a flow in a message, the encodings, and six of the
refusals.

**For the user's eye**: a run for rows picked by what a column holds
(`run.only.where`) is refused for a reader of several flows, with
"its columns are: none". Right, and not helpful; rows of such a reader
are picked by their `records`.
