# 113 - Advanced XML output

Status: resolved
Type: task

## Question

Build the advanced XML output (`AdvancedFileOutputXML`,
`tAdvancedFileOutputXML`) on the XML writer, to
[XML: the decisions](110-xml-the-decisions.md).

## What is known

- The converter writes three tables, `root`, `group` and `loop`, each
  row with `path`, `column`, `value`, `attribute` and `order`, and
  thirty more keys. Its reading was made against a job written by hand.
- Talend's rules, read in Talaxie's `tAdvancedFileOutputXML` at
  `639d5fd1f776` (the skeleton, and the three templates):
  - The tables are gone through in order. An element's parent is found
    by walking up from the element before it to the one whose path is
    the row's path less its last name. An `attri` or `ns` row belongs
    to the element before it. `main` marks the element a table is about.
  - A row with no `order` gets its number among all the rows.
  - A fixed `value` is written only where the row names no column.
  - An attribute whose column holds nothing is left out, or written
    empty with "add empty attribute". One with no column and no value
    is written empty only with "add unmapped attribute".
  - With "create empty element" off, an element is written where one of
    the columns in it is not null, or something in it has a fixed
    value. An empty text is not null, and is written.
  - A group starts anew where one of its values is not the row
    before's, and when a group around it does. Its values are its
    attributes' columns and its own column, or else those of the
    elements in it.
  - The root, and what stands in it before and after the rows, is built
    once, from the first row.
  - The stylesheet line is written without its closing `?`.

## Answer

Built on 2026-10-12:
`src/v2/components/file/advanced_file_output_xml.py` (65 tests in
`tests/v2/components/test_advanced_file_output_xml.py`).

- **The tree is built once, at load**, and what is wrong with it is said
  then: a table that names no element, a path that leads nowhere, a
  second root or loop element, a name that is no name, a prefix nobody
  declares, an attribute given twice, a group that does not stand above
  the loop element.
- **A row is one line of text**, as in the XML file output. For each
  element the loop stands in, the line has what that element writes
  before the rows where it starts, and what it writes after them where
  it ends. Starts and ends are found with `shift`, so the pass stays
  one pass and nothing is held.
- **Texts that are the same for every row are joined before any row is
  read** (`</who><amount>` is one piece). That made it a little faster
  than the XML file output.
- **No row**: the root is written when the file is made ready, from a
  frame of one row that holds nothing.

### Where it is not Talend, and why

| What | Talend | v2 | Why |
|---|---|---|---|
| The parent of an element | found by walking up from the element before | the last element written with that path | The same wherever Talend finds one. Where Talend finds none it stops with a null pointer; v2 finds the element or says which path leads nowhere. |
| What stands after the rows | the first row's values | the last row's | A count that runs with the rows ends as the total. |
| A group's values | its attributes and its own column, or else what is in it | every column it holds beside the rows | Talend's group can show the first row's value for rows that have another. |
| A row whose columns all hold nothing, "create empty element" off | no loop element | an empty loop element | One element for each row: the count of the run and the count of the file agree. |
| "add unmapped attribute" with "create empty element" off | no effect | written | Two keys, each does what it says. |
| Elements beside each other | as the tables list them, `order` only placing the next table's element | by `order` | The same for a table Talend's editor wrote. A job made by hand can say the order. |
| The stylesheet line | no closing `?` | closed | Talend's is not XML. |

### What was decided on the way

- **The fixed value is not a default.** First drawn as "the value where
  the column holds none". Dropped when Talend's source was read: the
  column wins there, and a delimited reader hands an empty text for an
  empty field, so the default would not have stood where a reader of
  the docs expects it. A default is a job for a map before the output.
- **Nothing to say means missing, not empty.** First drawn as "no text
  and no attribute". Dropped for Talend's rule: a missing value and an
  empty text stay two things in the document, as they are in the rows
  and in the XML file output's `missing`.
- A namespace from a column refuses the job: a namespace is the same
  for every row. A prefix that starts with `xml` refuses the job.
- A fixed text that holds a character XML cannot hold is not looked for
  at load. The reading back finds it, and the job fails with no file
  put in place.

**Measured** (a Mac): three million rows of eleven columns, one group,
elements before and after the rows, to a document of 1,015 MB: 4.7 s,
0.65 million rows a second, the reading back included. The XML file
output on the same rows: 5.5 s.

**Not built**: `merge`, `output_as_xsd`, `usestream`,
`add_document_as_node`, `split`, numbers with separators of the job's
own. Each refuses the job when on.

**For the user's eye**: the converter has not been tried on a table
Talend itself exported. If it reads one wrongly, the job is refused by
what the table then says, not by a wrong file.

## How it was built

- The first thirty-five tests were written before the component and
  seen failing for want of it. Six more were written before the rules
  they hold (the fixed value, nothing to say, no row under a group).
- Written after their code, with the mutation check standing in for
  the failing run: a second loop element, an attribute and a namespace
  given twice, a column that is not there where no schema is declared,
  the fixed texts read back, `order` as a number.
- Two rules were drawn, built against, and then changed (above). Their
  tests were rewritten to the new rule before the code was.

## Mutation check

A hundred ways of breaking the component and the writer. Ninety-six
were caught at first. Of the four others, three were code that could
not be reached (a value of `None`, which the loader turns into the
key's default before a component sees it; the attributes of an
attribute) and went. The fourth got a test, here and for the XML file
output: the engine is told rightly whether a file is left when no row
arrives.

The five that the XML file output's ticket had to add tests for were
run again after its check moved to the writer: all caught.
