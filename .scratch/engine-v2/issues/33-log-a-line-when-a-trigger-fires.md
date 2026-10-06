# 33 - Log a line when a trigger fires

Status: resolved
Type: task

## Question

The log does not say why a subjob ran. In the payments scenario the reject
report runs because a `RunIf` on the reject count was true, and no line says
so. Log the triggers.

Asked for by the dev on 2026-10-06, during the review of the engine.

## To build

- One INFO line for every trigger that fires: its type, the component it
  leaves and the subjob it sets off.
- For a `RunIf`, the condition and what it came to, also when it came to
  false. A `RunIf` is judged twice, as in v1: when its own component is done
  and when the subjob is done. One line for each time it is judged, saying
  which.
- An `OnSubjobError` or `OnComponentError` that fires says so the same way.
- Plain ASCII, like every log line.

## Answer

Built on 2026-10-06 (`Runner._say` in `src/v2/engine/runner.py`, tests in
`tests/v2/unit/test_triggers.py`).

A trigger that fires, of any type but `RunIf`:

    [job] trigger OnSubjobOk from settings_in to payments_in fired: the subjob of payments_in is set off

A `RunIf`, each time it is judged:

    [job] trigger RunIf from in to after, judged when in was done: <condition> is false
    [job] trigger RunIf from in to after, judged when the subjob was done: <condition> is true: the subjob of after is set off

- A subjob has no name in v2, so it is named by the component the trigger
  points at; the "subjob starting" line that follows lists its components.
- A `RunIf` that is true the first time is not judged again, so it has one
  line. One that is false the first time has two.
- A trigger that does not fire has no line, except a `RunIf`. Neither has a
  trigger whose subjob was set off already by another one.
- The condition is written as one line of plain ASCII: line breaks become
  blanks and any other character is written as its escape.
- The line gives what the condition came to, not the values it read. That
  would be the next thing to add if support asks why a count was what it was.
