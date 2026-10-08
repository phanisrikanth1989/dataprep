# 32 - Row count of every component in the log

Status: resolved
Type: task

## Question

The log says how many rows each output wrote and nothing about the
components before it. Let a run log the row counts of every component, as v1
does.

Asked for by the dev on 2026-10-06, during the review of the engine.

## What was decided

On request, not always. The dev chose this on 2026-10-06, after
[Each part of a subjob's plan runs once](31-each-part-of-a-plan-runs-once.md)
was parked.

- A switch on the command line turns the counts on for one run. Production
  support uses it when looking into a job; an ordinary run is as fast as
  today.
- The counts are exact and taken the way the engine already takes a count a
  trigger reads: a small count plan beside the job for each component.
- A run with the switch on is slower, about three times on the payments job.
  The help text and the README say so.

## What was measured

Payments scenario, 1,000,000 payments, three runs each:

| Way of counting | Exact | Time |
|---|---|---|
| None for components (today) | - | 2.0 s |
| A count plan beside the job for every component | yes | 5.9 s |
| A pass-through counter after every component | no | 2.0 s |

The pass-through counter is free but counts a row once for every time Polars
produces it, which in a job with several outputs is more than once: the
payments reader showed 4,000,000 for 1,000,000 rows. It is exact only with
the sharing that ticket 31 parked. Polars' own `profile()` gives the time of
each step, never its rows.

## To build

- A command-line switch, and the same for `run_job`.
- With it on, one line per component when its subjob has finished: rows in,
  rows on, rows rejected, by v1's rules for each component (`line_counts`: a
  map counts the rows of its outputs, a join its main input, a context load
  the variables it set).
- The same counts in globalMap as `<id>_NB_LINE`, `_NB_LINE_OK` and
  `_NB_LINE_REJECT`, and in the summary.
- No time per component: a subjob runs as one pass.

## Answer

Built on 2026-10-06.

- `python -m src.v2 job.json --row-counts`, and `run_job(..., row_counts=True)`
  from Python.
- With it, one INFO line for every component when its subjob has finished,
  in v1's words: `[format_check] NB_LINE:4000 OK:3920 REJECT:80`. The same
  numbers are in the summary under `counts`, in `JobResult.counts`, and in
  the globalMap as `<id>_NB_LINE`, `_NB_LINE_OK`, `_NB_LINE_REJECT`.
- A subjob that failed has no counts, and neither has one that never ran.
- Payments scenario, 1,000,000 payments: 2.0 s without, 6.2 s with.
- What is written does not change: the files of a counted run are the same
  bytes.

### Held against v1

v1 keeps the same three counts for every component it runs
(`component_stats`). They were compared on every job of the answer-key
tests, 2,316 of them, with a throwaway hook in the harness. What that found:

- **A count that was plainly wrong, 0 rows for 6 written.** Polars 1.44
  miscounts `select(pl.len())` over frames put one after another and then
  cut (`concat` under `slice` or `head`), which is the shape the full-row
  input builds for a file ending in a line end. The engine now counts by
  numbering the rows and taking the highest number. This was there before
  this ticket for any job that read such a count. Reproduction:
  `research/probes/probe_polars_count_of_a_cut_union.py`.
- **The full-row input's `NB_LINE`.** v1 counts every line the file splits
  into, the skipped ones too (header, footer, empty lines, lines past the
  limit). v2 counted the lines passed on. It now counts as v1 does.
- **One difference kept, in 9 of the 2,316 jobs.** Eleven of v1's sixteen
  component types here count their rows before v1 checks them against the
  declared schema. A row that check drops or moves to reject (a missing
  value in a column that may not hold one, `die_on_error` off) stays in
  v1's count of rows passed on. v2 counts the rows a component hands on, so
  its counts add up with what is written. In v1 the positional and Excel
  inputs never report a reject for that reason. Listed under "Differences
  from v1" in `docs/v2/README.md`. The dev was shown it on 2026-10-06 and
  kept it.

After the two corrections the same comparison shows those 9 jobs and
nothing else.

What stays in the suite: `tests/v2/test_row_counts_against_v1.py` (the
readers, the transforms and the map outputs the scenario does not use, and
the kept difference pinned), `tests/v2/test_scenario_payments.py` (all 24
components of the payments job, ten component types), and
`tests/v2/unit/test_row_counts.py` (the switch itself, and the cut union).
