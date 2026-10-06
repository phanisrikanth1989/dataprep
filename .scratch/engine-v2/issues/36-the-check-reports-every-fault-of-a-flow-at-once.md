# 36 - The check reports every fault of a flow at once

Status: resolved
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

## Answer

Built on 2026-10-06 (`src/v2/engine/check.py`; tests in
`tests/v2/unit/test_check.py`, and the payments job with the two faults
above in `tests/v2/test_scenario_payments.py`).

The job of this ticket now gets one report:

    Job 'payments_end_of_day_python' cannot run on v2: 2 problems.

    component format_check (FilterRows):
      - config: conditions[0]: there is no column 'debit_acount' to test

    component prepare (PyMap):
      - expression: outputs[0].columns[6].expression: `joined.amout`: joined has no column 'amout'; ...
        (checked against the columns 'format_check' declares, because 'format_check' has a fault of its own)

- A component for which a fault is reported hands on empty frames of the
  columns it declares, and the check goes on from there. That holds for a
  fault in its config (`problems()`) as for one that shows when it is built.
- A fault found past such a component ends in a note naming it. The note is
  there because a declared schema need not be all a component hands on:
  columns it does not declare pass through too, and those cannot be known
  while it is faulty. A job the converter wrote declares every column, and
  for it the note changes nothing.
- A source hands on every output it describes. Of any other component only
  the main output is handed on: what leaves by a reject output is declared
  nowhere.
- Left unchecked, as before: what follows a faulty component that declares
  no columns (a map: its outputs are in its config, and a column typed `str`
  there keeps whatever type its expression gives; a reader whose fault is
  that it has no schema), what follows a component whose config values
  cannot be read at all, and what follows a component that waits for a
  context value or a globalMap entry.
- One fault is one line: a component built on declared columns reports only
  what is wrong with itself.
