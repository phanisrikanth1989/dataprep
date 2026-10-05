# 10 - Subjobs, triggers and what happens after a failure

Status: open
Type: grilling
Blocked by: 08

## Question

How are subjobs ordered and connected, and what does the engine do when one
fails? v1 job configs list `subjobs` and connect them with triggers:
`{type, from, to}` with types OnSubjobOk, OnComponentOk, OnSubjobError,
OnComponentError and RunIf (which carries a condition). v2 as found derives
subjobs from the flows and has `on_success`, `on_failure` and `conditional`.

To settle:

- Verdicts for the trigger keys and trigger types under the five-verdict
  scheme.
- `subjobs` in the job config: read, checked against the grouping the engine
  derives from flows, or ignored.
- OnComponentOk versus OnSubjobOk. v2 as found treats both as "after the
  whole subjob". What v1 does is the answer key.
- After a failure with no handler. As found, v2 keeps running independent
  subjobs and reports an error at the end (finding 25). What v1 does is the
  answer key. Job status and what the process exits with.
- The order of subjobs that have no trigger between them. As found it is
  alphabetical by component id, which decides whether a context load runs
  before the components that need it (finding 9).
- RunIf conditions are expressions. Their language is settled in
  [Expressions outside Map](17-expressions-outside-map.md); here, only when a
  condition is evaluated and against which values.
