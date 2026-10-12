# 111 - The XML reader and the XML file input

Status: resolved
Type: task

## Question

Build what four of the six XML components read with, and the XML file
input (`FileInputXML`, `tFileInputXML`) on it, to
[XML: the decisions](110-xml-the-decisions.md).

## What is known

- The converter writes `filepath`, `loop_query`, `mapping` (`column`,
  `xpath`, `nodecheck`), `limit` (empty when none), `die_on_error` (off
  unless ticked), `encoding`, and eight keys that tune Talend's parsers.
- The converted sample job
  (`tests/talend_xml_samples/converted_jsons/Job_tFileInputXML_0.1.json`)
  reads `/orders/order/items/item` with six of its ten columns looking
  two levels up, one of them at `status`, which stands after the items:
  the case a reader gets wrong when it makes a row as the item ends.

## Answer

Built on 2026-10-12: `src/v2/xml_reader.py` (57 tests in
`tests/v2/unit/test_xml_reader.py`) and
`src/v2/components/file/file_input_xml.py` (48 tests in
`tests/v2/components/test_file_input_xml.py`). Both test files were
seen failing first, for want of the module and of the component.

**The reader.**

- The parser's settings are one function, `settings()`, with no way in
  for a job: no entity resolved, no DTD loaded, no network, no recovery.
  A resolver that fails whatever asks for another file is always added;
  under these settings nothing asks.
- A record path is names (`RecordPath`), a column path is XPath 1.0 read
  once (`ColumnPath`), and both say what they refuse when the job loads.
- `Records` goes through the document with lxml's `iterparse`, asked
  only for the tags of the record and of the element a column climbs
  to. It makes rows when that element ends, and frees it with all that
  stands before it, at every level above (`_free`).
- How far a column climbs is read from its path: the longest run of
  `..` that starts a path inside it. A run that ends in an attribute
  and nothing more needs no waiting: a start tag is whole when it is
  read. A climb after a step down is refused, since where it ends
  cannot be read from the text.
- Where names are local, the snapshot's names are made local before the
  paths are asked, and prefixes are taken out of the paths. Only a
  document that declares a namespace pays for that.

**The component.**

- The document is gone through once in `read()`, into scratch files of
  Arrow IPC, 50,000 rows or 32 MB of text each, and Polars scans those.
  A second reading of the subjob scans them again and parses nothing.
- Values are typed as the delimited reader types its text, with its
  words for a value that does not fit.
- A record's line is kept in the scratch files and looked up only when
  a message needs it.

**Measured** (a Mac, lxml 6.1.1; not the servers): a document of 200 MB,
eleven columns, six of them two levels up.

| What | Speed | Memory over what the process had |
|---|---|---|
| parse and free, no column | 143 MB a second | 0 MB |
| the reader with its columns, first version | 12.9 MB a second | 1 MB |
| the same, after two changes | 26 MB a second | 1 MB |
| the whole job, to a delimited file | 23 MB a second | 352 MB |

The two changes: a value above a record is found once for all the
records under one element, and the text of an element with nothing but
text in it is read without a second path. The same memory at 20 MB and
at 200 MB.

**Found on the way, and not this ticket's**: the memory of the whole
job grows with the file (95 MB over at 20 MB, 352 at 200, 607 at 600).
It is not the reader, which holds 1 MB. A delimited file read and
written by the two oldest components of v2 does the same (253 MB over
for 60 MB, 686 for 300, 1,122 for 900). Three ways of writing the
scratch files were tried (Arrow IPC with and without compression,
Parquet) and one output alone: all the same. So it is how Polars'
streaming engine runs these plans on a machine with memory to spare,
and a question for the engine as a whole. **For the user's eye.**

**Left out, as decided**: a condition in the record path; an XSD.
Also not built: a per-record line beyond a hint.

## Mutation check

Sixty ways of breaking the reader and the component. Fifty-two were
caught at first. The eight others each got a test:

- The DTD loaded after all, and the resolver that refuses left out: the
  test of a document that asks for another file only looked at what came
  back. It now also notes whether anything was asked for, and a second
  test sets the parser as lxml has it by default and shows that the
  resolver alone still stops the read.
- A path from the root found deeper down too; a snapshot not freed; a
  namespace declaration kept on a node handed on as text; the document
  gone through again at a second reading (the test did not make the
  engine read twice; a run for picked rows does); `large_values` not
  handed on to the reader.

The full run after it: 6,871 tests pass, every module at 95% or more.
