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

What the writers share:

- **No tree is built.** The text of a row is made by Polars and written
  as one line, so memory does not follow the size of the output, and
  nothing of Python is in the pass. (Talend's default builds the whole
  document in memory.)
- **Whatever a value holds is read back as it was.** `&`, `<` and `>`
  are escaped, and so are the quote and the tab in an attribute. A line
  end inside a value is written by its number (`&#10;`, `&#13;`): a row
  stays one line, and a carriage return is read back as one, where a
  parser turns a bare one into a line feed.
- **A character the encoding lacks is written by its number** (`&#8364;`
  for a euro sign in ISO-8859-1), so nothing is lost and the write does
  not fail. The declaration names the job's `encoding`.
- **A character XML cannot hold fails the job** and names the column and
  the row: a control character such as `\x01`. (Talend writes it, and
  leaves a file no parser reads.)
- **A name that is no name refuses the job**: a tag with a blank in it, a
  column whose name starts with a digit. (Talend checks none.)
- **The file is read once before it is put in place**, as a reader would
  read it. A document that is not well formed fails the job and leaves
  the file that was there. A writer written by hand earns that check; it
  takes about as long again as the writing.

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

## XML file output

- The rows are written to the file `filename` as one document: its
  declaration, the `root_tags` one inside the other in the order given
  (`root` when none is given), and a `row_tag` element for each row, on
  a line of its own. (v1 writes the first root tag only.)

  ```
  <?xml version="1.0" encoding="UTF-8"?>
  <orders>
  <order id="1"><name>ann</name><amount>10.50</amount></order>
  </orders>
  ```

- A column is an element in the row, named after the column. An entry
  of `mapping` makes it an attribute of the row (`as_attribute`) or
  gives it another name (`label`, v2's own key). Attributes and elements
  each keep the order of the columns. A value is written as the
  delimited output writes it: a date by its pattern, a decimal with its
  places.
- `missing` (v2's own key) says what is written for a value that is
  missing:

  | `missing` | An element | An attribute |
  |---|---|---|
  | `empty` (when not given) | `<name></name>` | `name=""` |
  | `omit` | nothing | nothing |
  | `nil` | `<name xsi:nil="true"/>` | nothing |

  `empty` is what the readers of a converted job were built against.
  `omit` is the one a reader can tell from empty text, and the better
  choice for a job written anew.
- With `use_dynamic_grouping`, the rows that follow each other with the
  same value in a `group_by` column stand in one element. It is named
  after the column and holds the value in the attribute `label` (`name`
  when not given, as in Talend); the column is then not in the row. A
  second entry makes groups inside the groups; an inner group starts
  anew when its outer one does. The rows of a group have to arrive
  together: a value that comes back later starts a second group. A job
  that cannot promise that sorts first.
- No row gives a document with nothing in its root. With
  `delete_empty_file` it gives no file, and one of an earlier run is
  taken away.
- `create` makes the folder of the file when it is not there, as in
  Talend. (v1 reads the key as leave to write over a file.)
- With `input_is_document`, the column `document_col` holds a whole
  document and the file is that document, under the job's own
  declaration; `trim` takes the white space around it away. There has
  to be one row: Talend writes every row's document into the one file,
  which is a document only when there is one.
- It leaves the path in `<id>_FILE_NAME`.
- Tried here on three million rows of eleven columns: 0.6 million rows
  a second, a document of 990 MB, the reading back included. (On a Mac;
  not yet on the servers.)
- Refused when on: `split` (a file every so many rows), and
  `advanced_separator` (numbers written with separators of the job's
  own). `flushonrow` and `flushonrow_num` are taken and have no effect.
- A converted job: the converter reads the output's table of columns
  from a job made by hand, and what Talend itself exports there is
  another shape. An entry of `mapping` that names no column refuses the
  job and says so.

## Advanced XML output

- The rows are written to the file `filename` as one document whose
  shape the job draws as a tree, in three tables:

  | Table | Its elements are written |
  |---|---|
  | `root` | once |
  | `group` | once for each run of rows that share its values |
  | `loop` | once for each row |

  A row of a table is one of four things, which `attribute` says:
  `main`, the element the table is about; `branch`, any other element;
  `attri`, an attribute of the element before it; `ns`, a namespace of
  the element before it. An element is given by its full `path`
  (`/sales/region/sale`), an attribute by its name, a namespace by its
  prefix.

  ```
  root:  /sales              main
         made                attri   value "by v2"
  group: /sales/region       main
         name                attri   column region
  loop:  /sales/region/sale  main
         id                  attri   column id
         /sales/region/sale/who      column name
  ```

  ```
  <?xml version="1.0" encoding="UTF-8"?>
  <sales made="by v2">
  <region name="north">
  <sale id="1"><who>ann</who></sale>
  <sale id="2"><who>bob</who></sale>
  </region>
  <region name="south">
  <sale id="4"><who>cy</who></sale>
  </region>
  </sales>
  ```

- An element or an attribute holds the value of its `column`, written
  as the delimited output writes it, or its fixed `value` where it
  names no column. Where it names both, the column is written, as in
  Talend. `trim` takes the white space around a column's value away.
- An element stands in the element its path names: the last one
  written with that path. Elements beside each other are written by
  their `order`, a whole number; one with none has its place in the
  tables for it (the first row of `root` is 1, and so on through
  `group` and `loop`), as in Talend.
- **Groups.** A group's element is opened where a value it holds is not
  the row before's, and closed where the row after opens one. What it
  holds is its own column, its attributes, and what stands in it beside
  the rows. A second `main` in `group` is a group inside the first; it
  starts anew when the outer one does. A missing value is a value of
  its own. The rows of a group have to arrive together: a value that
  comes back later starts a second group, so a job that cannot promise
  that sorts first. (Talend looks at fewer of these values: an element
  of a group that holds a column of its own is not asked for what
  stands in it, and its group can then show the values of its first row
  for rows that have others.)
- What stands before the rows in the document has the values of the
  first row, and what stands after them those of the last: a count that
  runs with the rows ends as the total. (Talend writes both with the
  first row's.)
- **Nothing to write.** These three say what is done with it:

  | Key | When not given | What it does |
  |---|---|---|
  | `create_empty_element` | on | Off: an element with nothing to say is left out |
  | `add_empty_attribute` | off | On: an attribute whose column holds no value is written, `name=""` |
  | `add_unmapped_attribute` | off | On: an attribute with no column and no fixed value is written, `name=""` |

  An element has nothing to say where no column in it holds a value
  (its own, its attributes', those of the elements in it) and nothing
  in it is fixed. An empty text is a value: it is written, as
  `<who></who>`. The loop element and the elements it stands in are
  always written, so the document has one loop element for each row.
  (Talend leaves out a row whose columns all hold nothing.)
- **Namespaces.** A row with `ns` declares a prefix on the element
  before it; its `value` is what the prefix stands for, and a row with
  no prefix declares the namespace of names that have none. A name may
  then carry the prefix (`s:sale`). A prefix that is declared on no
  element at or above the name refuses the job. `xml:` needs no
  declaring. A row with no `value` declares nothing, as in Talend.
- No row gives the root with what stands in it up to the first group,
  with nothing for a column's value. With `delete_empty_file` it gives
  no file, and one of an earlier run is taken away.
- With `file_valid`, one line follows the declaration: `<!DOCTYPE
  dtd_name SYSTEM "dtd_systemid">` with `dtd_valid`, or else
  `<?xml-stylesheet type="xsl_type" href="xsl_href"?>` with
  `xsl_valid`. The line is written; nothing is checked against what it
  names.
- `create` makes the folder of the file when it is not there. It
  leaves the path in `<id>_FILE_NAME`.
- Tried here on three million rows of eleven columns, with a group and
  elements before and after the rows: 0.65 million rows a second, a
  document of 1,015 MB, the reading back included. (On a Mac; not yet
  on the servers.)
- Refused when on: `merge` (rows added to a document that is there),
  `output_as_xsd`, `usestream`, `add_document_as_node` (a column that
  holds a document put in as elements), `split` and
  `advanced_separator`. `pretty_compact` and `generation_mode` are
  taken and have no effect: the document is written a row a line, and
  no tree is built whichever way Talend was to build it.
- A table of bare names, as a job made by hand has it (`sales`, not
  `/sales`, and `true` for an attribute), is read too: the first
  element of a table is the one it is about, and the others stand in
  it.
- A converted job: the converter reads the three tables from a job
  made by hand, and has not been tried on what Talend itself exports.
  A table that names no element, or an element whose path leads
  nowhere, refuses the job and says so.
