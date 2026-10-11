# 79 - Warn

Status: resolved
Type: task

## Question

Build v1's warn (`Warn`, `tWarn`) on v2: a message is logged and the job
goes on. Asked for on 2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/control/warn.py`. It logs `Code <code>:
  <message>` at the level of `priority` (default 4, a warning; code 42),
  leaves `<id>_MESSAGE`, `_CODE` and `_PRIORITY` in globalMap, and hands
  the rows of a flow that leads to it on as they came. It logs once,
  whether rows arrive or not.
- Talend's is what is done for each row (`tWarn_main.javajet` at Talaxie
  639d5fd1f776): with a flow it speaks for every row and not at all when
  none arrives. Its names in globalMap are `<id>_WARN_MESSAGES`,
  `_WARN_CODE` and `_WARN_PRIORITY`.
- It is die's twin (ticket 78): the same message, code and priority.

## Answer

Built on 2026-10-12 (`src/v2/components/control/warn.py`; 17 tests in
`tests/v2/components/test_warn.py`, all written and seen failing first).

- Die's twin: it shares die's reading of a message, code and priority.
  Alone it is an action; in a flow it hands the rows on and asks, in the
  subjob's one pass, whether any came.
- In a flow it speaks once, and only when a row arrives: between v1 (once,
  always) and Talend (for every row). A line for each of a million rows
  is no use to anyone; the README says so.
- Mutation check: 10 ways of breaking it, each caught.

Not done: a warn with a flow out of it and none into it, which nothing
can feed; the engine says that it produced no output.
