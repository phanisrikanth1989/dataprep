# 51 - Rows an aggregate leaves out for a missing group value

Status: needs-triage
Type: grilling

## Question

An aggregate row leaves out every row that has no value in a group column.
The job ends in success and nothing says so. v1 does the same, so v2 follows
it. Should that stay, be told in the log, or change?

Found on 2026-10-07 by the review of
[Say when rows are dropped for a fault](46-say-when-rows-are-dropped-for-a-fault.md),
and then run again here. Ticketed only; for the dev to decide.

## What is known

- The case: file -> aggregate row (group by `dept`, sum of `amount`) ->
  file, with the rows `1;1`, `;2`, `1;3`, `;40`, `2;5`. Both engines write
  `1;4` and `2;5`. The two rows without a `dept` are in no group: 42 of the
  51 in `amount` are gone. No warning; with `--row-counts` the component
  shows NB_LINE 5, OK 2, REJECT 0.
- In v2 it is a filter before the grouping
  (`src/v2/components/aggregate/aggregate_row.py`, where the group keys are
  taken). In v1 it is what pandas does by default: `groupby` drops the rows
  whose key is missing (`src/v1/engine/components/aggregate/aggregate_row.py`,
  the `groupby` call).
- Not known: what Talend's tAggregateRow does with a missing group value.
  If it keeps those rows as a group of their own, v1 and v2 both write less
  than the Talend job did.
- The same kind of thing in a context load: a row with no key is skipped
  without a word, in v1 and in v2. That one loses a setting, not data.
- Telling it should cost little: the engine can now notice rows as they
  pass (ticket 46; 0.04 to 0.08 s at a million rows for a reader's rows,
  not measured for an aggregate).

## To settle

1. **What Talend does.** That decides whether this is a fault of v1's that
   v2 has copied, or the right answer.
2. **If it stays as it is: say it in the log**, as ticket 46 does for a row
   a reader could not read ("2 rows were dropped: no value in the group
   column 'dept'; the first is line 3 of in.csv"), or leave it silent.
3. **If Talend keeps the rows**: whether v2 should, which would make its
   files differ from v1's for such data.
