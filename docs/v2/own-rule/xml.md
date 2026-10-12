# XML

The components that read and write XML.

Built to their own rule: what is written here is what they are held to,
not v1. ([What that means](README.md).)

What the readers share:

- **Nothing but the document is read.** No DTD is loaded and no entity a
  document declares is resolved, whatever the document says, and no key
  of a job changes that. An entity of the document's own that is used
  fails the job with its name: left alone it would lose a part of a
  value without a word. The five entities of XML (`&amp;` and the like)
  and a character given by its number are read as always. (Talend reads
  the DTD a document names unless "Ignore DTD file" is ticked, and so can
  be made to read another file.)
- **A document that is not well formed is no document.** It fails the
  job with the parser's line and column, and no row of it is handed on,
  also not the rows before the fault.
- **Memory follows the largest record, not the file.** The document is
  gone through once, a piece at a time. Rows are made when a record
  ends, and the record is then let go of with all that stands before
  it. Where a column looks above its record (`../../status`), rows are
  made when the element it looks into ends, so that all of it is there:
  what is held is then that element. (v1 holds a small document whole
  and reads a large one another way, which gives other rows for such a
  column. Talend holds the document whole.)
- The parser's own limits hold: 256 levels of nesting, 10 MB for one
  value. `large_values` lifts them for a feed that is trusted.
- **Names are matched by their local name**, whatever namespace they are
  in and whatever prefix a path has, so a job reads a document whichever
  prefixes its sender uses. A job that has to tell two namespaces apart
  gives `namespaces` (a prefix and what it stands for, v2's own key):
  paths are then read as XPath says, and a name without a prefix is in
  no namespace. `ignore_ns` is taken and has no effect.
- **What the document says of its own encoding decides**: its
  declaration, or a byte order mark. `encoding` is for a document that
  says nothing. (Talend reads every document in the job's encoding,
  whose default every converted job carries: a UTF-8 document that says
  so is then read wrongly, without an error.)

## XML file input

- One row for each record that `loop_query` finds in the file
  `filepath`. The path is the names from the root down to the record
  (`/orders/order/line`), with `*` for any name; or `//line` for a name
  at any depth, where a record inside a record is a record too. A
  condition in it (`[@type='x']`) refuses the job for now: a filter
  after the reader does the same.
- Each `mapping` entry finds one column's value from the record, by an
  XPath 1.0 path: `sku`, `@id`, `price/@currency`, `../status`,
  `../../@region`, `concat(../code, '-', sku)`. A column with no entry,
  or an entry with no path, is the child of the column's own name.
  Refused when the job loads: a path that starts at the root, one that
  climbs after it has gone down, one that climbs above the document, and
  the axes that look outside the record (`ancestor`, `preceding`,
  `following`, their siblings, `parent`): what they find would depend on
  how much of the document is in memory. After `//`, a column reads its
  record and the attributes of what is above it.
- What a path gives:

  | The path finds | The value |
  |---|---|
  | one element | all the text in it, in order |
  | an attribute, or a text | that text |
  | nothing | missing |
  | an element with nothing in it | empty text |
  | an element marked `xsi:nil="true"` | missing |
  | several nodes | the first; a warning says for which column, in how many records, and the first of them |
  | a number or a truth (`count(line)`, `qty > 1`) | as XPath writes it: `2`, `true` |

- `nodecheck` on an entry ("Get Nodes" in Talend) gives the node itself
  as XML text, and not the text in it. Without `namespaces` it carries
  no namespace. (v1 reads the key as "turn the record away when the
  value is empty", which is not what Talend means by it.)
- Values are text until they are read as the type their column
  declares, as for the delimited reader. A value that is none of that
  type fails the job and names the record:

  ```
  Schema/coercion failed for 1 row(s); first error: Column 'qty': could not convert string to float: 'ten'; the row is record 2 of in.xml, near line 2
  ```

  With `die_on_error` off such a row leaves by the reject output, with
  why in `errorCode` and `errorMessage`, or is dropped with a warning
  when no flow takes the rejects. A missing value in a column that may
  hold none is such a fault too.
- A row's place is its record's number among the records, from 1. The
  line is where its start tag is, as the parser counts lines: exact up
  to line 65,535 and near enough after, so it is given as a hint.
- `limit` is the most records read; none when it is empty, as in a
  converted job. The rest of the document is then not read, and so not
  checked.
- A file that is not there, a folder, a pipe or a device fails the job
  and is never opened. With `die_on_error` off the job goes on with no
  row and a warning after a document it cannot read.
- The rows wait in scratch files (in `V2_TEMP_DIR`, or the system's
  temporary folder) until the subjob has finished, so scratch space of
  about the size of the values read is needed. The document is gone
  through once, however often the engine reads the source.
- Tried here on a document of 600 MB with eleven columns, six of them
  looking above the record: 26 MB a second for the parser and the
  columns, with 1 MB of memory more than before it started, at 20 MB
  and at 200 MB alike; 23 MB a second for the whole job. (On a Mac; not
  yet on the servers.) What the engine holds of the rows after that is
  what it holds for any reader.
- Taken and without effect: `ignore_dtd` and `generation_mode` (v2 has
  one way of reading and reads no DTD), `check_date`, and
  `advanced_separator` with its two separators (numbers are read as the
  engine reads them). `use_separator` on refuses the job.
- Not built: a condition in the record path; a check of each record
  against an XSD.
