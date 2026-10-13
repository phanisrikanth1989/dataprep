# 103 - Foreach

Status: resolved
Type: task

## Question

Build foreach (`Foreach`, `tForeach`) on v2: the first component that
starts a loop
([The iterate link](102-the-iterate-link.md),
[Loops and job control: the decisions](100-loops-and-job-control-the-decisions.md)).

## What is known

- The converter writes `values`, a list of text with each value's outer
  quotes taken off. Talend sets `<id>_CURRENT_VALUE` for a pass; v1 adds
  `<id>_CURRENT_ITERATION` and, at the end, `<id>_NB_LINE`.

## Answer

Built on 2026-10-12 (`src/v2/components/iterate/foreach.py`, an `Action`
that starts a loop; 16 tests in `tests/v2/components/test_foreach.py`
with real components in the body, seen failing first).

- The values are text, in the order written; one written as a number is
  the text of it. A context variable in a value is put in when the
  component runs, before the first pass.
- `<id>_CURRENT_VALUE` for a pass (and the engine's
  `<id>_CURRENT_ITERATION`); `<id>_NB_LINE` is how many values there
  are.
- `max_items`, the engine's cap.
- Mutation check: 9 ways of breaking it, 7 caught at first, the other
  two each got a test.
- The first component on the new page
  `docs/v2/own-rule/loops-and-job-control.md`.
