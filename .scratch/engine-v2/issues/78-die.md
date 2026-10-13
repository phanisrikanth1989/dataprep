# 78 - Die

Status: resolved
Type: task

## Question

Build v1's die (`Die`, `tDie`) on v2: the job is stopped with a message.
Asked for on 2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/control/die.py`. It logs `Code <code>:
  <message>` at the level of `priority` (1 and 2 debug, 3 info, 4
  warning, 5 error, 6 critical), leaves the message, code, priority and
  exit code in globalMap (`<id>_MESSAGE`, `_CODE`, `_PRIORITY`,
  `_EXIT_CODE`, and `JOB_ERROR_MESSAGE`, `JOB_EXIT_CODE`), and fails with
  `Job terminated by tDie: <message> (exit code: <n>)`. A
  `((Integer)globalMap.get("key"))` in the message is that entry, 0 when
  there is none.
- It stands alone, set off by a trigger, or a flow leads to it. With a
  flow v1 stops the job whether a row arrives or not (tried on
  2026-10-12). Talend stops it when a row arrives and not otherwise: the
  component's code is what is done for each row
  (`tDie_main.javajet` at Talaxie 639d5fd1f776; its connectors allow one
  flow in). A filter's reject output led to a die means "stop if a row is
  turned away", which v1's reading breaks.
- Talend's own names in globalMap are `<id>_DIE_MESSAGE`,
  `_DIE_MESSAGES`, `_DIE_CODE` and `_DIE_PRIORITY`.

## Answer

Built on 2026-10-12 (`src/v2/components/control/die.py`; 24 tests in
`tests/v2/components/test_die.py`, 22 of them written and seen failing
before any code).

- Set off by a trigger it is an `Action`; with a flow leading to it the
  engine builds it as a transform, and it asks, in the subjob's one pass,
  whether a row arrived. The engine learned that an action may stand in a
  flow (three lines of the runner and the check).
- Decided from Talend's source: in a flow it stops the job only when a
  row arrives. v1 stops it always.
- v1's message, log line and globalMap names; Talend's names beside
  them.
- Mutation check: 19 ways of breaking it and the engine's lines, 18
  caught at first and one after a test.

Not done: ending the command line with the die's own exit code.

## Corrected after review (ticket 84)

- A die did not stop the job: it failed its own subjob and the job went
  on. "Stops the job as in v1" above was false. It ends the job now: no
  trigger fires, no subjob follows.
- Its message keeps its own characters in the failure's text (as
  escapes); `die_on_error` is taken.
