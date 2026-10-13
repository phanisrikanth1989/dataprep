# 80 - Set global var

Status: resolved
Type: task

## Question

Build v1's set global var (`SetGlobalVar`, `tSetGlobalVar`) on v2:
entries are put in globalMap, for a trigger's condition or a later
component to read. Asked for on 2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/file/set_global_var.py`. `variables` is a
  list of `key` and `value`. Alone, it puts each value under its key. With
  a flow leading to it, it hands the rows on, and a value written
  `row1.name` is the column `name` of the row: every row puts it, so the
  last row's value stays. v1 takes any word before the dot, and keeps the
  text when there is no such column.
- With a flow and no row, v1 puts the values as they are written, the
  text `row1.name` among them (tried on 2026-10-12). Talend's component
  is what is done for each row, like die and warn: no row, nothing put.
- In Talend and v1 a component further down the same flow reads, row by
  row, what this one has just put. v2 runs a subjob in one pass and
  cannot give that: the entries can be there only when the subjob is
  done.

## Answer

Built on 2026-10-12 (`src/v2/components/control/set_global_var.py`; 21
tests in `tests/v2/components/test_set_global_var.py`, 20 of them written
and seen failing before any code; what a later subjob reads is held
against v1's files).

- Alone it is an action and puts its entries when its turn comes. In a
  flow it hands the rows on and asks, in the subjob's one pass, for the
  columns of the last row it needs; the entries are put when the pass is
  done.
- What v2 cannot give is said and not papered over: a component of the
  same subjob that reads an entry would read the value from before. The
  engine hands every component the texts of its subjob's configs
  (`RunContext.subjob_texts`), and this one fails the job when another
  member names one of its keys in quotes. That is a search of text: a key
  put together in code is not seen.
- As Talend: nothing is put when no row arrives.
- Its row counts are none, as v1 counts.
- Mutation check: 16 ways of breaking it, 15 caught at first and one
  after a test.

Corrected the same day: the commit of this component (2fee4c2b) went in
with one test of the suite red, because the command that ran the suite
went on to commit whatever it said. The test was right: the converter
writes `requires_java_bridge` on this component and the key was not
declared, so every converted job with a set global var was refused. The
key is declared now; the suite is run and read before a commit.

## Corrected after review (ticket 84)

- A trigger that leaves a component before the set global var saw its
  entries too early; it is judged without them now, as in v1.
- The check for a reader in the same subjob took any quoted word for
  one. It looks for `globalMap.get("key")` and `globalMap["key"]` now.
- Wrong above: in v1 a component further down reads the last row's value,
  not each row's.
- `variables` or a key given as nothing refuse the job.
