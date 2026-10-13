# 112 - The XML writer and the XML file output

Status: resolved
Type: task

## Question

Build what three of the six XML components write with, and the XML file
output (`FileOutputXML`, `tFileOutputXML`) on it, to
[XML: the decisions](110-xml-the-decisions.md).

## What is known

- The converter writes `filename`, `row_tag`, `root_tags` (`name`),
  `mapping` (`column`, `as_attribute`), `use_dynamic_grouping`,
  `group_by` (`column`, `label`), `encoding`, `create`,
  `delete_empty_file`, `input_is_document`, `document_col`, `trim`,
  `split`, `split_every`, the flush keys and the number separators.
- Its reading of the table of columns was made against a job written by
  hand. Talend's own table has three items a column (`AS_ATTRIBUTE`, a
  tick "use schema column name", and `LABEL`), read in Talaxie's
  `tFileOutputXML_java.xml` at `639d5fd1f776`; the converter takes two
  and reads the tick as the column's name.
- Talend's template writes a group as an element named after the
  column, with the value in the attribute the group's label names, and
  starts an inner group anew with its outer one
  (`tFileOutputXML_main.javajet`).

## Answer

Built on 2026-10-12: `src/v2/xml_writer.py` and
`src/v2/components/file/file_output_xml.py` (52 tests in
`tests/v2/components/test_file_output_xml.py`, seen failing first for
want of the component).

- **A row is one line of text**, made by Polars expressions: the escaped
  values between their tags, the attributes in the start tag. The head
  (declaration, root tags) and the foot are two small frames set before
  and after the rows, so one sink writes the whole document in the
  subjob's pass.
- **Escaping** is one pass over each value (`str.replace_many`). Every
  test that writes a file reads it back with lxml; one feeds ten hard
  texts through elements and attributes in six encodings.
- **Groups** are found with `shift`: a group opens where its value, or
  that of a group around it, is not the row before's, and closes where
  the row after opens one. A test of more than a hundred thousand rows
  in two levels of groups holds the result against Python's own
  grouping.
- **A character XML cannot hold** is looked for in the pass and fails
  the subjob, naming the column and the row among the rows written. A
  sink is not told where a row came from, so it cannot name the line of
  the input.
- **The last reading** is by expat, which is in Python itself and keeps
  nothing: 271 MB a second here, against 149 for lxml freeing as it
  goes. Where expat does not know the encoding (one of more than one
  byte a character, such as Shift_JIS) lxml reads the file.
- `files.to_encoding` got `by_number`: a character the encoding lacks is
  written by its number.

**Measured** (a Mac): three million rows of eleven columns to a
document of 990 MB.

| What | Time | Rows a second |
|---|---|---|
| with the reading back by lxml | 11.6 s | 0.26 million |
| with the reading back by expat | 5.1 s | 0.60 million |

**Not built**: `split`; numbers with separators of the job's own.

**For the user's eye**: the converter's reading of this component's
table of columns does not fit what Talend exports. A real job will most
likely be refused with "there is no column 'true'". The converter is
not this work's; it is said here so that it is not found by a job.

## Mutation check

Thirty-eight ways of breaking the writer and the component. Thirty-three
were caught at first. The five others each got a test: the document
read back without lxml on the machine; the first of two rows with a
character XML cannot hold; the mark of a missing value declared once;
and a missing value as a group of its own, also where the rows start
with it.

The full run after it: 6,930 tests pass, every module at 95% or more.
