# 110 - XML: the decisions

Status: resolved
Type: grilling

## Question

With
[How current tools read and write XML](91-how-current-tools-read-and-write-xml.md)
in hand: what are XML file input, multi-schema XML input, XML file
output, advanced XML output, extract XML field and XML map built to? The
user left the decisions to the agent (ticket 87); each one that turns
round something Talend or v1 does is marked **for the user's eye**.

## Answer

Decided on 2026-10-12. The research's section 3 gives the options and
the grounds; this is what is taken from it, and where it is not taken.

### Tried again here before deciding

- On the installed lxml 6.1.1, a document read by `iterparse` with its
  default settings made the parser read another file through a parameter
  entity (the file was asked for, and its text came back as a value).
  With `resolve_entities=False` and no DTD loading, nothing was asked
  for in three ways of trying, and the entity stays in the tree as a
  node of its own (`xml/safety2.py` in the session's scratch folder).
  So the settings are right, and a value that holds an entity node has
  to fail: it would otherwise lose a part without a word.

### One reader for four components

- **The parser is set once and no key weakens it.** v2 opens the file
  itself; entities are not resolved; no DTD is loaded; no network; no
  recovery from a document that is not well formed. An entity the
  document declares itself fails the job with the entity's name.
  libxml2's own limits stay (256 levels, 10 MB a value); one key,
  `large_values`, lifts them for a trusted feed.
  **For the user's eye**: Talend reads the DTD a document names unless
  "Ignore DTD file" is ticked. v2 never reads one.
- **Memory follows the largest record, not the file.** Rows are made
  when a snapshot element ends, and it is then freed with all that stands
  before it. The snapshot is the record, or the ancestor a column climbs
  to (`../../status`). A column that only reads an ancestor's attribute
  (`../../@id`) needs no larger snapshot. One way of reading for every
  size of file: v1's two ways give other rows above its threshold.
- **The record path** is names from the root (`/orders/order/line`), with
  `*` for any name, or `//line` for a name anywhere. A predicate in it
  refuses the job for now, with the way round it (a filter after the
  reader). **A column path** is XPath 1.0 from the record. Refused: one
  that starts at the root, one that climbs anywhere but at its start,
  and the axes whose answer depends on what happens to be in memory
  (`preceding`, `following`, `ancestor`).
- **What a path gives**: one node, its text; none, a missing value; an
  empty element, empty text; `xsi:nil="true"`, a missing value; several
  nodes, the first, with a warning that says for how many records.
  "Get Nodes" (`nodecheck`) gives the node as XML text, which is
  Talend's meaning and not v1's.
- **Names are matched by their local name** unless the job gives
  `namespaces` (prefix to URI), v2's own key; with it, paths are read as
  XPath says. Not the research's finer rule (a name without a prefix by
  local name, one with a prefix by its binding): that needs every path
  rewritten, and a rewriter of XPath is one more thing to get wrong.
  `ignore_ns` is then taken and has no effect.
- **Encoding**: the document's own declaration or byte order mark
  decides; the job's `encoding` is used when it has neither.
  **For the user's eye**: Talend reads every document in the job's
  encoding, whose default (ISO-8859-15) every converted job carries
  whether anyone chose it or not; a UTF-8 document that says so is then
  read wrongly without an error.
- **Values are text** until the engine types them against the declared
  schema, as for the JSON input. A row whose value does not fit goes to
  the reject output or fails the job, as for any reader.
- **Rows reach Polars through a scratch file**: the document is parsed
  once, on the calling thread, into Arrow IPC batches, and Polars scans
  that. A second reading of the subjob costs nothing, and memory is one
  batch. Scratch space of about the size of the values read is needed.
- **A row's place** is its record's number, with the line of its start
  tag as a hint.

### One writer for three components

- The text of each row is made by Polars expressions and sunk as a line;
  the head and the foot are added when the pass is done. No Python in the
  pass.
- Escaping is written here and tested against lxml: every file a test
  writes is read back. A character XML cannot hold fails the job and
  names the row (Talend writes it, and leaves a file no parser reads).
  Element and attribute names are checked when the job loads. A
  character the encoding lacks is written as a numeric reference.
- Before the file is put in place it is read once by the reader: a
  writer written by hand earns that check.
- Groups open where a value differs from the row before and close where
  it differs from the row after, which is Talend's own rule. The rows of
  a group have to arrive together.

### The six

- **XML file input**: the reader, a main and a reject output.
- **Multi-schema XML input**: one pass, one scratch file an output.
  Which output an entry of `schemas` feeds is not in today's config: a
  new optional key names the flow; one entry and one output belong
  together; anything else refuses the job.
- **XML file output**: root tags nested in the order given (v1 writes
  only the first), a row element a row, columns as children or
  attributes, dynamic grouping. `create` makes the folder, which is
  Talend's meaning and not v1's. A missing value: a new key, `empty`
  (the default, as now), `omit` or `nil`.
- **Advanced XML output**: the three tables become one tree. Taken:
  Talend's four words for a node (`main`, `branch`, `attri`, `ns`) and
  the hand-made sample's two. Refused when on: `merge`, `output_as_xsd`,
  `usestream`, `add_document_as_node`.
- **Extract XML field**: the rows in hand, as extract JSON fields has
  them; each cell parsed whole with the reader's parser. Not the
  research's batch-by-batch way: the engine has no such kind of
  component yet, and one for both extracts is a ticket of its own.
  `limit` is the most rows of the whole flow (Talend's), not the most
  nodes of each row (v1's).
- **XML map**: what today's config can say rightly and no more: a
  document taken apart into rows, and flat rows mapped to flat rows.
  A lookup, a reject output, variables, a filter and a document as
  output refuse the job, each with its reason: the converter does not
  write what they need.

### Not built, and said so

- A check of each record against an XSD.
- A predicate in the record path.
- `split` (a file every so many rows), until the delimited output has
  it too.
- XPath beyond 1.0: nothing that streams offers it.

### What it asks of the project

- lxml in the `v2` extra, with a floor of 6.1.3, the first release with
  all three of its fixes for external entities. The settings above do
  not depend on it.
