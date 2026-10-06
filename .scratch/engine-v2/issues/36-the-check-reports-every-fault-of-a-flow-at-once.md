# 36 - The check reports every fault of a flow at once

Status: ready-for-agent
Type: task

## Question

A job with two faults on the same flow is refused twice: the first report
names only the first fault, and the second fault shows once the first is
corrected. Make the check report both in one go.

Found on 2026-10-06, while showing the dev a refused job; the dev asked for
the ticket.

## What is known

The payments scenario's job with two faults put in:

- the filter rows `format_check` tests a column that is not there
  (`debit_acount`);
- the map `prepare`, further down the same flow, names a column that is not
  there (`joined.amout`).

`python -m src.v2 job.json --check` reported one problem, the filter's. With
the filter corrected it reported one problem again, the map's.

Why: `check_job` builds each subjob against empty frames, component by
component. A component that cannot be built hands nothing on, and every
component fed by it is skipped (`engine/check.py`: "left unchecked, together
with what it feeds").

Faults in config keys do not have this gap: the loader reports all of them
in one report (an unknown key, a Java expression and an unknown component
type came out together).

## To build

- When a component cannot be built, carry on down the flow with empty frames
  of the columns it declares (`declared_outputs()`), so that what it feeds is
  still checked.
- Where it declares no columns, what it feeds stays unchecked, as today; a
  guess at its columns would report faults that are not there.
- A component that waits for a value a context load sets is still not judged,
  and neither is what it feeds.
- One fault must stay one line in the report: a component fed by a faulty
  one must not repeat its fault.
