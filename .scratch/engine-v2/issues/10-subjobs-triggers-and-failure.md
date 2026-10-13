# 10 - Subjobs, triggers and what happens after a failure

Status: resolved
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

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

- Trigger keys: `type`, `from` / `to` (also `from_component` /
  `to_component`, `source` / `target`), `condition`, `output_id` (order among
  a subjob's triggers). Types: v1's five, plus v2's `on_success`,
  `on_failure`, `conditional` as spellings.
- `subjobs` and `subjob_id` are ignored; subjobs come from the flows, as
  v1's converter output assumes.
- Order is v1's: untriggered subjobs in job-config order, what a subjob
  triggers right after it, depth first, each subjob once.
- A subjob is one pass, so "component ok" and "subjob ok" coincide:
  OnComponentOk fires when the subjob finished; OnComponentError fires for
  the component the failure is blamed on; RunIf is evaluated after the
  subjob, failed or not.
- After a failure the other subjobs still run (v1 and Talend do the same);
  the job's status is `failed` and the process exits 1. A RunIf condition
  that cannot be evaluated stops the job.
- Refused at load: a trigger inside one subjob, triggers that form a loop.
