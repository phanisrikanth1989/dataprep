# 32 - Row count of every component in the log

Status: ready-for-agent
Type: task
Blocked by: 31

## Question

The log says how many rows each output wrote and nothing about the
components before it. Log the row counts of every component, as v1 does.

Asked for by the dev on 2026-10-06, during the review of the engine.

## What was decided

- Counts are always on, and taken by a counter in the plan that every row
  passes through, the way the engine already counts the rows it hands an
  output. Not by a count plan beside the job.
- That counter is only exact once each part of a plan runs once, which is
  [Each part of a subjob's plan runs once](31-each-part-of-a-plan-runs-once.md).
  This ticket waits for it.

## What was measured

Payments scenario, 1,000,000 payments, three runs each:

| Way of counting | Exact | Time |
|---|---|---|
| None for components (today) | - | 2.0 s |
| A count plan beside the job for every component | yes | 5.9 s |
| A pass-through counter after every component | no | 2.0 s |

- The counter has to let column pruning through and nothing else
  (`projection_pushdown=True, predicate_pushdown=False, slice_pushdown=False`);
  with the defaults the job took 2.2 to 2.3 s.
- Polars' own `profile()` gives the time of each step, never its rows.

## To build

- One line per component when its subjob has finished: rows in, rows on,
  rows rejected, by v1's rules for each component (`line_counts`: a map
  counts the rows of its outputs, a join its main input, a context load the
  variables it set).
- The same counts go to globalMap as `<id>_NB_LINE`, `_NB_LINE_OK` and
  `_NB_LINE_REJECT`, so a trigger that reads one needs no plan of its own.
- No time per component: a subjob runs as one pass.
