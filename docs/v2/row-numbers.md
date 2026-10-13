# Row numbers: where a row came from

For whoever writes a component: how a failure comes to name the row of
the input it is about, and what a component does for that. The code is
`src/v2/rows.py`. The rest of the contract is in
[Writing a v2 component](writing-a-component.md); what a user sees of
it is in [Looking into a job](looking-into-a-job.md).

Every source numbers its rows as it reads them, from 1. The number travels
with the row as a hidden column, with copies of the columns the source's
schema marks as key. When the engine finds a row it cannot go on with, the
failure's message ends with the row's place:
`; the row is line 4 of in.csv (id=3)`.

How a user asks for a key: `"key": true` on a column of the source's
schema, which is what Talend's key flag converts to. Nothing else is
configured, and a new component declares no config key for any of this.

The names: hidden columns start with `__v2_`, and no column of a job may:
the check at load refuses a job in which a component declares or makes one.
`__v2_row:<source id>` is the number, `__v2_key:<source id>:<column>` the
copy of a key column, `__v2_rows:<source id>` how many rows were combined
into this one (rows as they reached the aggregate: after a normalize,
several of them come from one row of the source).

What the engine does for every component: it drops the hidden columns
before a sink is handed its frame, leaves them out of the scope an
expression is translated in (`row_scope`), and out of the columns a debug
line lists. The plan Polars prints at DEBUG is Polars' own text and does
name them. No file ever holds one; every test that compares v2's files with
v1's would fail if one did.

What a component owes, by what it does with rows:

| The component | What it does about the hidden columns |
|---|---|
| reads a source | numbers its records and says where a number is (next list) |
| keeps its rows and hands on every column (a filter, a sort) | nothing: they pass |
| picks the columns it hands on (`select`) | picks `rows.hidden(names)` as well |
| makes several rows of one (normalize, unpivot) | nothing where it explodes a column, since the other columns repeat; otherwise every row made carries the hidden columns of the row it came from |
| makes one row of several (an aggregate, a pivot, a denormalize) | keeps, for each source, the lowest row number, that row's key copies, and how many rows went in: `rows.combined(names)`, handed to the `group_by` that makes the rows |
| joins a lookup to a main input | hands on the main input's; drops the lookup's (`rows.without`) |
| reads columns by their place, or treats every column alike (prints all, compares all) | leaves the hidden ones out (`rows.visible(names)`) |
| hands rows to code the engine cannot see into | sets `sees_hidden_columns = False`: the engine hands it frames without them, and what it hands on has lost them |
| puts several inputs one after another (a unite) | nothing: each row keeps its own source's number |
| turns rows into columns (a transpose, a pivot) | says what a row of its output stands for: a group of input rows (then as "one row of several"), or nothing (then it drops them and says so) |
| writes an output of any kind | nothing: the engine drops them before the output is handed its frame |
| makes no rows | nothing |

This holds for every component added from now on, whatever it reads, does
or writes. The list to work through, with what `locate` says for each kind
of source, is in
`.scratch/engine-v2/issues/44-what-a-new-component-owes-the-row-numbers.md`.

A source:

- numbers its records where it reads them, before it drops any (a blank
  line, a row a limit cuts), in the column `self.row_number`:
  `row_index_name=self.row_number, row_index_offset=1` on a Polars scan, or
  `with_row_index(self.row_number, offset=1)`. The number counts from the
  first record after what the reader's config skips at the top, so that
  `locate` can add the header rows back;
- hands on, with every output (a reject output that declares its own
  columns too), that column and `self.key_copies()`. Take the copies where
  the reader first holds the column, before it trims or types text, so that
  a key is shown as close to the source as the reader has it. A column
  Polars parses itself is copied as parsed (`7` for `007`), and a positional
  field without its padding; its page says so;
- implements `locate(number)`: the words a person looking for the record
  would use, ending in the path as the job gives it. `line 7 of in.csv`,
  `row 3 of sheet 'Q1' of book.xlsx`, `record 2 ($.orders[1]) of in.json`.
  Give the position the source's own tool shows (an editor's line, a
  sheet's row). Where that cannot be vouched for, as with a record that can
  span lines, give the record's number and call it a record.

A run may be for a few rows of a source and no others (`run.only`), and may
list what every component did with them (`run.trace`). What that asks of a
component:

- A source keeps to the picked rows with `frame = self.picked(frame)`,
  called where it has numbered its rows and before it types or turns away
  any (after its own `limit`). It says what kind of place its rows have
  (`place_kind`: `lines`, `records` or `rows`), why (`place_why`, for the
  message when the wrong kind is asked for), and turns a place back into a
  row's number (`number_at`, the other way round from `locate`). Where
  Polars parses values for the whole file, it does not when `only_rows` is
  set (`_native` in `file_input_delimited.py`).
- Rows are picked by what a column holds, read the way the source reads the
  column. A source that reads a column's text in a way of its own (the
  positional reader takes a file's own number separators out) does it in
  `as_read(column, text)` and reads its own fields through it, so that the
  engine reads the value asked for, and the text of a row the source turned
  away, the same way.
- An output that can hold a row carries the row number. One that never can
  (the reject output of a reader that turns no row away) may go without.
- A component that looks things up in some of its inputs says which
  (`lookup_inputs`): the engine lists a component's rows when every input
  that is not a lookup comes from the picked rows.
- A sink gives the text its file holds for each column (`Write.as_text`),
  so that the list of what it was handed shows what the file holds.
- Nothing else. The engine takes the rows of such a flow in hand between
  two components and lists them, each value written as a file output that
  declares the component's columns would write it.

A check that fails on rows names the first. Ask for the hidden columns of
the first failing row beside the count, and end the message with
`self.where(found)`. The value shown has to come from that same row: where
several columns can fail, take each one's value on the first failing row
(`pl.when(flag).then(value).filter(any_flag).first()`), never each column's
own first bad value, which may stand on a later row.

```python
from ...rows import first_of

bad = frame.filter(flag)
self.check(
    bad.select(pl.len().alias("rows"), pl.col(name).first().alias("value"), *first_of(bad)),
    lambda found: f"... {found['value'].item()!r}{self.where(found)}" if found["rows"].item() else None,
)
```
