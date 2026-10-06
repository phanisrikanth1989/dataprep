# 31 - Each part of a subjob's plan runs once

Status: needs-triage
Type: grilling

## Question

In a subjob with several outputs, Polars produces the rows of the shared
front of the plan more than once. How should the engine make each shared
part run once, safely?

Chosen by the dev on 2026-10-06, during the review of the engine, as the way
to exact row counts for every component
([Row count of every component in the log](32-row-count-of-every-component-in-the-log.md)).
It needs a design discussion with the dev before any code: it changes how the
engine runs a subjob.

## What is known

Measured on the payments scenario (`scenarios/payments`) at 1,000,000
payments, v2 on Polars 1.44.2, streaming engine:

- One pass-through counter on the payments reader alone saw 4,000,000 rows.
  The job took the same time with and without the counter, so the counter is
  not what causes it: the reader's rows are produced four times.
- A counter after every component saw the filter's and the unique row's rows
  three times, the join's and the first map's twice, the second map's once.
  The deeper a component sits before the outputs fan out, the more often it
  runs.
- The job takes 2.0 s like this. How much faster it is with sharing has not
  been measured.

Why it happens, and what has been ruled out:

- `pl.collect_all` shares a part two plans have in common one level deep.
  Where sharing nests (a reader feeding a filter with its reject wired,
  feeding a map with three outputs, feeding a sort read twice), the levels
  above are rerun.
- `LazyFrame.cache()` forces sharing. On Polars 1.44.2 it lost a select
  between a cached frame and a frame with two readers, and a sink wrote the
  wrong columns: `research/probes/probe_polars_cache_loses_projection.py`.
  `tests/v2/test_rules.py` forbids `.cache()` in v2 for that reason.

## Routes to weigh

- A later Polars: is the cache bug fixed there, or does `collect_all` share
  deeper? The supported range is `>=1.44,<2.0`
  ([Which Polars versions v2 supports](28-which-polars-versions-v2-supports.md)).
- Holding the rows in memory where a flow forks. Simple; costs memory in step
  with the rows, which is what v2 was built to avoid.
- Writing the rows to a scratch file where a flow forks and reading it back
  for each branch. Keeps memory flat; costs a write of wide rows.
- Shaping the plan so that it forks later or less: a component with two
  outputs hands on one flagged frame that is only split at the outputs.

## What any answer has to keep

- The answer-key tests: the same bytes as v1.
- Rows are streamed, not held, wherever they are today.
- A subjob that fails leaves every file as it was.
