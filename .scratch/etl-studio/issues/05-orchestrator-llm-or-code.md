# 05 - Orchestrator: LLM-driven or deterministic?

Status: open
Type: grilling
Blocked by: 04

## Question

Is the pipeline driver an LLM agent or a deterministic state machine with LLM
calls only inside the specialists?

Recorded leaning from charting: LLM-driven (user). Stress-test it:

- What decisions does the driver actually make that need a model, given the
  topology from ticket 04?
- Cost and latency per run (credits are ample -- ~20k available, 100-500 per
  run acceptable -- so this is about reliability more than money).
- Failure modes: a wandering driver vs a rigid one when the human steers
  mid-run.
- What each choice does to replay/rehearsal determinism for the demo.
