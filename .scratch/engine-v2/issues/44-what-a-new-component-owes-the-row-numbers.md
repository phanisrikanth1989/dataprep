# 44 - What a new component owes the row numbers

Status: ready-for-agent
Type: task
Blocked by: 40, 41, 42, 43

## Question

Write down, for whoever adds a component to v2 after this (a person or an
AI), exactly what the component has to declare and what has to be built and
tested for it, so that a failure still names its row.

Asked for by the dev on 2026-10-07: "a separate ticket which documents
exactly how a future component should be configured and what all are the
things the AI should build then."

## To build

- The rule for each kind of component, in `docs/v2/writing-a-component.md`,
  which is what a builder reads: a source, a step that keeps its rows, one
  that makes several rows of one, one that makes one row of several, one
  that hands rows to code the engine cannot see into, a file output.
- How a user marks a key column, and what a job config needs for it.
- The list of what to build and what to test, in the order to do it, with
  the two components of tickets 42 and 43 as the worked examples.
- This ticket's answer holds the same list, so that it can be handed to an
  agent as it stands.
