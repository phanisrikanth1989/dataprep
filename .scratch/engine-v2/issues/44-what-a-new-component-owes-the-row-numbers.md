# 44 - What a new component owes the row numbers

Status: resolved
Type: task
Blocked by: 40, 41, 42, 43

## Question

Write down, for whoever adds a component to v2 after this (a person or an
AI), exactly what the component has to declare and what has to be built and
tested for it, so that a failure still names its row.

Asked for by the dev on 2026-10-07: "a separate ticket which documents
exactly how a future component should be configured and what all are the
things the AI should build then."

## To build

- The rule for each kind of component, in `docs/v2/writing-a-component.md`,
  which is what a builder reads: a source, a step that keeps its rows, one
  that makes several rows of one, one that makes one row of several, one
  that hands rows to code the engine cannot see into, a file output.
- How a user marks a key column, and what a job config needs for it.
- The list of what to build and what to test, in the order to do it, with
  the two components of tickets 42 and 43 as the worked examples.
- This ticket's answer holds the same list, so that it can be handed to an
  agent as it stands.

## Answer

Written on 2026-10-07. This is for **any component added to v2 from now
on**: a reader of any kind of source, a step of any kind, an output of any
kind. It is the list to hand to whoever builds it, a person or an AI. The
rules themselves are in `docs/v2/writing-a-component.md` ("Row numbers").

### 1. What the user configures

One thing, and it is there already: `"key": true` on a column of a source's
schema marks it as a key column (Talend's key flag converts to that). A new
component declares **no config key** for row numbers, and no job config
changes.

### 2. Find the kind of component you are building

Every component is one of these, or a mix; for a mix, do each part.

| Kind | Built already | Others it covers | What it must do |
|---|---|---|---|
| **Source**: reads rows from anywhere | delimited, positional, full row, Excel, JSON | XML, a database query, a queue, a fixed list of rows, a row generator | Number its records from 1 where it reads them, before dropping any. Hand on the number and the key copies with every output. Implement `locate` (table 3). |
| **Keeps its rows and all their columns** | filter rows, sort row, unique row, log row | sample, replace values | Nothing. The hidden columns pass. |
| **Picks or renames columns** | filter columns, the map's outputs | convert type, extract fields | Pick the hidden columns as well (`rows.hidden(names)`). |
| **One row becomes several** | normalize | unpivot, extract with a loop, replicate | Every row made carries the hidden columns of the row it came from. Free where one column is exploded; with Polars' `unpivot`, name them among the index columns. |
| **Several rows become one** | aggregate row | denormalize, pivot, aggregate sorted | Keep, for each source: the lowest row number, that row's key copies, and how many rows went in (`_carried` in `aggregate_row.py`). |
| **A lookup joined to a main input** | join, the map's lookups | any other join | Hand on the main input's hidden columns; drop the lookup's (`rows.without`). |
| **Several inputs one after another** | unite | merge | Nothing. Each row keeps its own source's number. |
| **Rows become columns** | none | transpose, pivot to columns | Say in the docstring what a row of the output stands for. If it stands for a group of input rows, do as "several rows become one". If for nothing, drop the hidden columns and say so. |
| **Hands rows to code the engine cannot see into** | Python dataframe | Python row, an outside program | Set `sees_hidden_columns = False`. What it hands on has no number; say so in the docstring. |
| **Reads columns by place, or treats all columns alike** | context load, log row's printing, unique row without keys | compare, checksum, schema check | Leave the hidden columns out (`rows.visible(names)`). |
| **Output of any kind** | delimited file output | Excel, XML, JSON, database outputs | Nothing: the engine drops the hidden columns before the output is handed its frame. |
| **Makes no rows** | none | die, warn, set variable, run job | Nothing. |

### 3. What `locate` says, by kind of source

`locate(number)` returns the words a person looking for the record would
use. Use the position the source's own tool shows.

| Source | What to say |
|---|---|
| Text file, one record a line | `line 7 of in.csv` (the number plus the header rows) |
| Text file where a record can span lines | `record 7 of in.csv`: the line cannot be vouched for |
| Workbook | `row 3 of sheet 'Q1' of book.xlsx` |
| JSON | `record 2 ($.orders[1]) of in.json` |
| XML | `record 2 (/orders/order[2], line 14) of in.xml` |
| Database query | `row 7 of the query of <component id>`; the key columns are what finds it |
| Queue or stream | the queue's own coordinates: topic, partition, offset |
| Rows the job makes itself | `row 7 of <component id>` |
| A file an iterate step picked | the path of that turn, as the reader resolved it |

### 4. If the component can fail on a row

Make the check count the failing rows, ask for `*first_of(bad)` in the same
frame, and end the message with `self.where(found)`. The job still fails
and writes nothing; the message gains the first row's place and key.

The value the message shows has to come from that same first row. Where
several columns can fail, take each one's value on the first failing row,
not each column's own first bad value (ticket 45 found a map naming one
row and showing another's value).

If the component goes on without the row instead (`die_on_error` off, or a
row it always turns away), it tells the log: `self.tell_dropped(rows,
wrong)` on that branch, with the rows it turned away and what is wrong with
each. The engine then warns once the subjob has finished, with the count
and the first row's place, unless a flow takes the reject output
([Say when rows are dropped for a fault](46-say-when-rows-are-dropped-for-a-fault.md)).
The engine does this itself for a missing value in a column that may not
hold one. It is not for rows the job turns away by its own logic.

A source that reads record by record in Python, as the JSON input does:
find out what v1 does with one record it cannot read. v1's JSON input
turns the record away and carries on; failing the job there is a fault.

### 5. If the component translates expressions

Call `self.check_conversions(frame, scope)` for every frame they run on.
The engine fails the job if you forget. A new function that can fail on a
row is built with `tr.fallible(what, value, made)`.

Check a conversion only on the rows v1 works the expression out for. If
the frame still holds rows the component has turned away (the map keeps
the rows an inner join missed, flagged), hand the translation a guard for
them. Test it with a turned-away row that holds a value no conversion can
read, on v1 too.

### 6. What to build, in this order

1. Read the guide and the v1 component. Run v1 on small inputs for every
   case you are unsure of: v1 is the answer key.
2. Answer-key tests first, failing: `tests/v2/components/test_<name>.py`.
3. The component: one file, every key the converter writes and v1 reads
   declared as supported, ignored or refused.
4. The row numbers, by table 2 (and table 3 for a source).
5. Sections 4 and 5 above, where they apply.
6. Row-number tests in `tests/v2/test_row_numbers.py` (section 7).
7. The whole of `tests/v2` and the coverage gate.
8. The docs (section 8).

### 7. Tests to write for the row numbers

- **A source**: a failure names the right place on every way the reader
  reads (a header, blank records, each of its read paths), and shows the
  key.
- **Any step that hands rows on**: a failure after it still names the
  source row (`chain(...)` in `tests/v2/test_row_numbers.py`). Once for
  each output it has: a reject output too, with and without a declared
  reject schema.
- **Two inputs**: a failure names the main input's row after a join or a
  lookup, and each row's own input after a unite.
- **Rows dropped for a fault**: the warning with its count and the first
  row's place; none when a flow takes the rejects, none when the component
  stops the job (`tests/v2/test_dropped_rows.py`).
- **Several rows become one**: the message says "the first of N rows that
  were combined".
- **Foreign code**: a failure after it no longer names a row.
- Nothing to write for "no hidden column in a file": every test that
  compares v2's files with v1's fails if one gets there.

### 8. Docs to update

`docs/v2/README.md`: the component in the list of components, its row in
the table of "Finding the row that failed", its differences from v1.
`CLAUDE.md`: the count of components.

### Worked examples

- A source: `src/v2/components/file/file_input_json.py`.
- One row becomes several: `src/v2/components/transform/normalize.py`,
  which had to do nothing.
- Several rows become one: `_carried` in
  `src/v2/components/aggregate/aggregate_row.py`.
- Picks columns: `projected` in
  `src/v2/components/transform/map_outputs.py`.
