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

## Tried on 2026-10-06

All on Polars 1.44.2, streaming engine, an Apple M4 with 16 GB. The try-out
is kept as `research/2026-10-06-sharing-try-out.patch`; it was not merged.

### It can be done with `cache()` and a guard behind it

- Why plain `cache()` went wrong: Polars merges two caches into one and drops
  a plain `select` or `drop` that sits between them. `pl.explain_all` shows
  both outputs reading the first cache, the dropped column included.
- The guard: a pass-through node the optimizer can move nothing through,
  placed between the cache and whatever reads it. Two caches can then never
  sit with only a `select` between them.
- `research/probes/probe_cache_with_a_guard.py`: five shapes, with Polars'
  own sharing on and off. Plain `cache()` writes wrong columns in three of
  them; the guarded one is right in all. A guard placed before the cache
  instead of behind it is wrong in one shape.
- `research/probes/probe_nested_outputs_run_once.py`: a model of the payments
  job's nested outputs. Unmarked, the reader's rows are produced five times;
  marked, every part runs once and the files are the same.

### In the engine

The try-out marks the frame two outputs are built from in filter rows, unique
row, join, map, the delimited and positional readers and the engine's own
schema split, and any output two flows read. A frame with one reader is left
alone.

- The whole of `tests/v2` passes with it, by default, with
  `V2_ENGINE=in-memory` and with `V2_SAFE_READ=1`. The one test that fails is
  the rule that forbids `cache()`.
- The payments scenario, middle of three runs, files identical byte for byte:

  | Payments | Today | Shared |
  |---|---|---|
  | 1,000,000 | 2.1 s, 2.0 GB | 1.3 s, 2.3 GB |
  | 5,000,000 | 11.8 s, 5.6 GB | 7.2 s, 6.0 GB |

- A guard that lets column pruning through was no faster (1.2 s and 7.6 s).
- With sharing on, a pass-through counter after every component saw every row
  exactly once: twelve counts checked against the true ones.

### What it costs

Rows that one reader has taken and another has not yet are held in memory.

- Usually little: 0.3 to 0.4 GB on the payments job.
- In the awkward shape, a flow that is both the rows and, added up, their own
  lookup: 5,000,000 payments took 4.2 s and 5.3 GB shared, against 7.3 s and
  3.9 GB today. That memory grows with the file.
- It is not always faster: two outputs of a file read as plain text, one of
  them sorted, took 4.9 s shared against 3.5 s today.
- On the in-memory engine sharing changes nothing: the same files, no gain.

### Not verified

- Files beyond 6,000,000 rows, where the memory matters most.
- The RHEL servers, and any Polars but 1.44.2. The guard leans on how this
  version plans a query.
- Polars' documentation says of `cache()` only that it caches the result at
  that node, and that the optimizer usually does better.

### Left to decide

- On by default, or asked for; and a size above which the engine goes back to
  today's way, which keeps memory flat.
- The rule "never call `.cache()`" in the guide and in `tests/v2/test_rules.py`
  becomes "only through the engine's own helper".
