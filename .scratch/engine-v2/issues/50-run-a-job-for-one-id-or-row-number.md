# 50 - Run a job for one ID or row number

Status: needs-triage
Type: grilling

## Question

A failure names its row: "the row is line 654322 of /data/payments.csv
(txn_id=654321)". The natural next step is to run the job for that row
alone. How is the row picked (by the key column's value, by its number),
of which source, what does such a run do with everything else in the job,
and what does it write?

## What the dev asked (2026-10-07)

"Run by ID or row number: add the provision to run the job directly for a
particular ID or row number of the key column."

Ticketed only. To be grilled with the dev before anything is built.

## What is there today

- Every source numbers its rows as it reads them, and a schema column can
  be marked as key (`"key": true`). A failure, and since ticket 46 a
  warning of dropped rows, ends with the row's place and key
  ([How v2 points at the input row that failed a job](38-how-v2-points-at-the-input-row-that-failed-a-job.md)).
- The place is the source's own: a line of a text file (the row's number
  plus the header rows), "row 3 of sheet 'Q1'" of a workbook, "record 2
  ($.orders[1])" of a JSON document. A delimited file read with
  `csv_option` gives a record number and no line.
- The message names the file, not the reader component. Two components may
  read one file.
- Nothing picks rows today except a reader's own `limit` (the first N).
- Finding one row of a million by its key is one filtered read of the file:
  0.09 s (measured for ticket 38; larger files not measured). What the rest
  of a job costs on one row has not been measured; the lookup files would
  still be read whole.

## What a run for one row would be, to react to

```
python -m src.v2 job.json --only payments_in:txn_id=654321
python -m src.v2 job.json --only payments_in:line=654322
python -m src.v2 job.json --only payments_in:txn_id=654321,654400
```

Only the picked source is cut down to the picked rows, right where it is
read; the row keeps its own number, so messages still say "line 654322".
Every other source is read whole: a lookup needs all its rows.

What then differs from the full run, because it depends on the other rows:

| Step | In a run for one row |
|---|---|
| filter rows, filter columns, map, normalize, join to a lookup | the same as in the full run |
| unique row | the row is never a repeat, as its twin is not there |
| aggregate row | a group of this row alone |
| sort row | nothing to sort |
| row counts, and a `RunIf` that reads one | counts of one row |
| a later subjob that reads a file this one writes | reads what the run wrote, or nothing |

## To settle in the grilling

1. **What it is for.** Looking at one row (nothing of the job's real
   output is touched), or processing one row for real (its rows are written
   to the job's outputs, for a record that was dropped or fixed). The two
   want opposite answers to "what is written".
2. **What is written.** Nothing (the run says what it would write), the
   job's files under another folder, or the job's real files. Writing one
   row over a real output file would destroy it; appending is a third
   thing again.
3. **How the row is named.** By the key column's value, by any column's
   value, by the place as the message gives it (line, sheet row, record).
   The line is not the row's number: a source would have to turn its own
   words back into a number.
4. **Of which source.** The reader's component id, or the file as the
   message names it. When a job has one main source it could be left out,
   and a rule is needed for when it cannot.
5. **A small set.** Several ids, a range of lines, the first N rows. Where
   the limit is, and what is said past it.
6. **The picked source is a lookup.** Then every main row misses. Refuse,
   warn, or allow.
7. **Which subjobs run.** All, as the triggers say, or only the one the
   picked source is in together with what must run before it (a subjob that
   loads the context).
8. **The row is not there.** A key no row has, a line past the end: an
   error, and with which exit code.
9. **A key that is not unique.** Every row that has it is taken; said or
   not.
10. **Where it is asked for.** A flag as above, the job's JSON
    ([Run settings in the job's JSON](47-run-settings-in-the-jobs-json.md)),
    or both.

## Where I lean, to be argued with

- **For looking, first.** Processing one row for real is another feature
  with its own dangers (a row written twice, an aggregate of one row
  written as if it were the day's total), and should be asked for by name
  if it is wanted.
- **Write nothing by default**, and say what would have been written;
  write the files under another folder when asked (`--out-dir`), so that a
  one-row output can be looked at beside the real one.
- **Name the row by what the message shows**: the key's value
  (`txn_id=654321`), for any column of the source and not only one marked
  as key, and the place (`line=654322`). Both are in every failure
  message, so both should paste.
- **Name the source by its component id**, and when the name is wrong say
  which sources the job has.
- **A list of ids, at most a hundred or so**; ranges and "the first N"
  only if asked for.
- **Run the picked source's subjob and what has to run before it**; say
  which subjobs were left out. A later subjob would read files this run
  did not write.
- **A flag, not the JSON**: it changes with every run.

Related: [Single-record debug run](49-single-record-debug-run.md) shows
what each component did with the picked row; this ticket decides how the
row is picked and what such a run is.
