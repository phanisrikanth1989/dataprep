# 86 - Trace and only through the new components

Status: resolved
Type: task

## Question

Do `run.only` and `run.trace` work with the twenty-six components built
on 2026-10-11 and 12, and is that held by tests? Asked on 2026-10-12.

## What is known

- Both are the engine's: a component has them by keeping to its contract
  (hidden row numbers carried, outputs declared).
- Before this ticket the trace had tests for five of the twenty-six
  (the two file outputs, extract delimited fields, properties input, file
  row count). `only` and the naming of a failing row had more.
- A probe on 2026-10-12 ran nineteen of them for one picked row with a
  trace: all as they should.

## Answer

`tests/v2/test_trace_of_every_component.py`, 24 tests. Each runs one
component for one picked row and holds what the trace says: the rows of
every output as text, and the place each came from.

- Hand rows on (16 cases): replicate, sample row, split row, replace,
  convert type, unpivot row, denormalize, aggregate sorted row, schema
  compliance check, the four extract components (regex also for a row
  turned away), warn, set global var.
- Write a file (3): pivot to columns delimited, file output Excel, file
  output positional. The trace holds the row handed to them.
- Make their own rows (2): fixed flow input, row generator.
- Die (3): the trace ends at the die with its error; a die no picked row
  reaches stops nothing.

No code changed: nothing was found wrong. The tests pass as written, so
each kind was seen to fail by breaking the code: split row and unpivot
row without the hidden columns, and the regex reject code changed, each
failed its one case and no other.

Not here, having their own tests: properties input and file row count.
File exist, copy and delete take no rows; a traced run just runs them.
