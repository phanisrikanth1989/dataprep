# 75 - File input properties

Status: resolved
Type: task

## Question

Build v1's file input properties (`FileInputProperties`,
`tFileInputProperties`) on v2: the entries of a `.properties` or `.ini`
file as rows. Asked for on 2026-10-11 with the other 25.

## What is known

- Talend's component has a schema the job cannot change: `key` and
  `value`, and `section` for an ini file read whole; it hands on a row for
  every property (Talaxie `tdi-studio-se@639d5fd1f776`,
  `tFileInputProperties_java.xml` lines 35 to 53, and
  `tFileInputProperties_begin.javajet`: `java.util.Properties.load` for a
  properties file, ini4j for an ini file, with three ways to read one:
  every section, the names of the sections, one section).
- v1 (`src/v1/engine/components/file/file_input_properties.py`) does
  something else: one row, with a column for every property whose name is
  a column of the output schema. On the schema every converted job has
  (`key`, `value`) it writes one row of nothing, unless the file happens
  to hold properties named `key` and `value` (tried on 2026-10-12). It
  does not know the third way to read an ini file.
- v1's reading of a properties file is its own too: no escapes
  (`\t`, `\u00e9`), and a key ends at `=` or `:` only, where Java also
  ends it at a blank.

## Answer

Built on 2026-10-12 (`src/v2/components/file/file_input_properties.py`;
62 tests in `tests/v2/components/test_file_input_properties.py`, 58 of
them written and seen failing before any code, while the review of
ticket 77 ran).

- Decided here, without asking: v2 hands on Talend's rows (`key`,
  `value`, `section`), since that schema is fixed in Talend and v1's one
  wide row is empty on it. v1's row is kept for a job that declares other
  columns, and held against v1 there (three tests). Read in Talend's
  source, not run in Talend.
- A properties file is read by Java's own rules, written out in the
  component (`properties`) and held by 25 lines of file, one rule each.
  Not as Talend: the order of the rows, which is the file's.
- An ini file by plain rules; ini4j's source is not in Talaxie's
  repository and was not read.
- A reader like the others: it numbers its rows by the line of the
  property, a run can be for a few of them, the counts are said.
- Mutation check: 33 ways of breaking it, 31 caught at first and two
  after a test each.

## Corrected after review (ticket 84)

The reviewer ran 4,047 files through Java 17 and through the reader.

- A `\u` that is no four hex digits was read on; it fails the job, as it
  stops Java. A line of nothing but a backslash made an entry, or took a
  comment for a key. Two `\u` escapes that are one character together
  (how Java writes an emoji) failed the job.
- A section named twice was one section in one way of reading and two in
  the others; it is one.
- The README says now where v1's wide row is not v1's (ini files), and
  that a value that cannot be read as its column's type goes missing.
