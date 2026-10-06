# 33 - Log a line when a trigger fires

Status: ready-for-agent
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
