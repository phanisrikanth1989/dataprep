# 115 - Extract XML field

Status: resolved
Type: task

## Question

Build extract XML field (`ExtractXMLField`, `tExtractXMLField`): the
records a path finds in the document a column holds, as rows, to
[XML: the decisions](110-xml-the-decisions.md).

## What is known

- The converter writes `xmlfield`, `loop_query`, `mapping`
  (`schema_column`, `query`, `nodecheck`), `limit`, `die_on_error` and
  `ignore_ns`. An older converted job (the sample in the repo) has
  entries with no `schema_column`, one for each output column in their
  order, and paths that start at the root (`/person/name`).
- Talend's rules, read in Talaxie's `tExtractXMLField` at
  `639d5fd1f776`:
  - A row whose field is null gives no row, and no reject.
  - The loop query is asked from the document; a column's query from
    the loop node, so one that starts at the root is followed from the
    root.
  - A column with no query is the input column of its name.
  - `limit` counts the rows of the whole flow.
  - A document that cannot be parsed, and a record whose value cannot
    be read as its column's type, go to the reject output with the
    whole field in `errorXMLField`. `errorCode` is in the reject
    schema and never set.
- v1 counts `limit` for each row's document on its own.

## Answer

Built on 2026-10-12:
`src/v2/components/transform/extract_xml_field.py` (60 tests in
`tests/v2/components/test_extract_xml_field.py`, the first 45 seen
failing first for want of the component; 62 in the end).

- **The reader got a second way in.** A document in a cell is parsed
  whole, by a parser set as the file reader's is: no DTD, no entity, no
  other file, the same limits. `xml_reader.path` reads any XPath 1.0:
  where all of a document is in memory, nothing is out of a path's
  reach. What a document is made ready with (no entity in it, names
  made local) is the same code for both.
- **The rows are in hand**, as for extract JSON fields: a document is
  read out of every row in Python. Values wait as text and are read as
  their columns' types by Polars, as the XML file input reads them.
- **What is turned away** is found in two places and put in the order
  of the rows: a document when it is parsed, a record when its values
  are read as their types.

### Decided on the way

- **A loop query that does not start at the root refuses the job.**
  Talend follows it from the document (`order/line` is `/order/line`),
  the library here from the root element (where it finds nothing). A
  converted job would have lost every row without a word. A function
  (`count(...)`) is let through and fails when the job runs: it finds
  what is no element.
- **`errorXMLField` of a record that is turned away is the record**,
  not the whole document: it is the one at fault, and a document with a
  thousand bad records is not held a thousand times.
- **A row with no document is no fault** (Talend's rule), so a job
  that is to die does not die of it. The log says how many there were.
  Empty text is no document, and is turned away.
- **The rows after `limit` are not read at all.** Talend still parses
  them, and can turn one away.
- `position()` and `last()` alone are no path here: the library has no
  place among others for the one node it is asked from. Said at load.
- The parser's own advice, "use XML_PARSE_HUGE option", is written as
  the job's key: "set `large_values` to read it". For the file input
  too.

**Measured** (a Mac): 600,000 records in 200,000 documents of 60 MB:
3.9 s, 150,000 records a second. A million records in 20,000
documents: 8.0 s.

**A slip found by measuring.** The first build took every input column
once for each record, the document among them: 2.3 GB for an input of
93 MB. Now only the columns that are handed on are taken, and values
are put into a frame every 50,000 records: 605 MB for the same input.

## Mutation check

Fifty-five ways of breaking the component and the reader's new parts.
Fifty-two were caught at first. Two of the others got a stronger test:
which entry is named when a column has three, and that values are put
into a frame in batches (a batch saves memory and changes no row, so
the test counts the frames). The third changes nothing that is
written: a text column read "as its type" is read as text.

One more, for a slip the list itself showed: the rows of a document
that cannot be read were counted by a frame that has no rows when no
column of it is taken. A test now calls the component with rows that
carry nothing of where they came from.

## How it was built

Tests first for the component as a whole. Written after their code,
with the mutation check standing in: the batches of values, the order
of what is turned away, a column named as a reason is, a column that a
path fills in a row whose document cannot be read, and the document
column looked for when the job runs.
