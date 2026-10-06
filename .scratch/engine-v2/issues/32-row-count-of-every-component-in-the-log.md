# 32 - Row count of every component in the log

Status: ready-for-agent
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
