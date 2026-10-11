# 60 - Aggregate sorted row

Status: resolved
Type: task

## Question

Build v1's aggregate sorted row (`AggregateSortedRow`,
`tAggregateSortedRow`) on v2: an aggregate for rows that arrive sorted by
their group columns. Asked for on 2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/transform/aggregate_sorted_row.py`. It
  uses its ordinary aggregate's functions and groups the whole input
  (`groupby`), so rows that are not sorted are grouped all the same. It
  drops the rows that miss a group value, as its ordinary aggregate does
  (ticket 51). `row_count` is accepted and not read. Operations are needed.
- Talend, read in its source (Talaxie `tdi-studio-se` at 639d5fd1f776,
  `components/tAggregateSortedRow/tAggregateSortedRow_main.javajet`, lines
  85 to 319): each row's group values are compared with those of the row
  before (`sameGroup`). A row that differs ends the group and starts a new
  one. Two missing values are the same value (lines 301 to 310). So rows
  that are not sorted give one group for each run of rows that agree, and
  the same group value can come out several times.
- On rows that are sorted, as the component asks, v1 and Talend agree.

## Answer

Built on 2026-10-11 (`src/v2/components/aggregate/aggregate_sorted_row.py`;
23 tests in `tests/v2/components/test_aggregate_sorted_row.py`; tests
written and seen failing first).

Decided, from Talend's source: a group is a run of rows that agree in the
group columns. On sorted rows, which is what the component is for, v2
writes what v1 writes, and that is held against v1 for every function. On
rows that are not sorted v2 does as Talend does and differs from v1; the
README says so under "Differences from v1". This is my call on one
component, by the rule of ticket 51 (the same as Talend comes first); it
was not run on Talend itself, and the dev can turn it back by having
`_grouped_by` return the group columns alone.

- It is the aggregate row with another answer to "what is a group": the
  aggregate got a small hook for it (`_grouped_by`), and nothing else of
  it changed.
- Keys: those of the aggregate row, and `row_count`, accepted and not
  read, as in v1. Operations are needed, as in v1.
- Rows that miss a group value are a group where they stand, as in Talend.
- A group names the first of its rows in a failure (a test in
  `tests/v2/test_row_numbers.py`).
