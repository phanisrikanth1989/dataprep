# 107 - Sleep

Status: resolved
Type: task

## Question

Build sleep (`Sleep`, `SleepComponent`, `tSleep`) on v2, to
[Loops and job control: the decisions](100-loops-and-job-control-the-decisions.md).

## What is known

- The converter writes one key, `pause_duration`, as text, `"1"` when
  the job gave none. It writes the type as `SleepComponent`.
- Talend's is `Thread.sleep(<pause> * 1000)` in the component's main
  part: in a flow it waits for every row. v1 warns on a value that is no
  number and does not wait.
- The research
  ([How current tools loop and run child jobs](90-how-current-tools-loop-and-run-child-jobs.md),
  2.6) found that every tool keeps a plain wait, checks its value, and
  says a wait for something is another thing.

## Answer

Built on 2026-10-12 (`src/v2/components/control/sleep.py`, an action;
24 tests in `tests/v2/components/test_sleep.py`, seen failing first:
"component type 'Sleep' is not supported in v2").

- Seconds, whole or with a part; one when none is given. Not a number,
  less than nothing, or no finite number: refused at load, or the job
  fails when its turn comes if the value is from the context.
- Alone, by a trigger, or behind an iterate link, where it waits once
  for each pass. A flow to it is refused.
- A line in the log before and after. Ctrl-C ends it at once: the stop
  goes straight through the engine.
- No longest wait is set. A wait of a year by a slip of the hand is
  seen in the first log line, and no other tool read caps it lower than
  that either.
- Mutation check: ten ways of breaking it, nine caught at first. The
  tenth, saying it has waited before it has, got a test that hears the
  two lines and the wait in their order.
