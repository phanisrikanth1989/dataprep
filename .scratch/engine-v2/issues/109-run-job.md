# 109 - Run job

Status: resolved
Type: task

## Question

Build run job (`RunJob`, `tRunJob`) on v2, to
[Loops and job control: the decisions](100-loops-and-job-control-the-decisions.md).

## What is known

- The converter writes nineteen keys. Those that matter: `process` (the
  child's name, with no version), `context_name`, `die_on_child_error`,
  `transmit_whole_context` and `context_params` (name and value). The
  rest tune a JVM or print.
- A converted job config is named after its job and the job's version
  (`child_0.1.json`); v1 takes `<process>.json` beside the parent, else
  the highest `<process>_<M.m>.json`
  (`src/v1/engine/child_job_runner.py:50-112`).
- v1 finds the child when its turn comes, guards against a job running
  itself by a depth of two, and ends the whole parent when a child
  fails. Talend names the child's class in the parent's code, so a child
  that is not there fails the build.
- Of the tools read, Kestra refuses a cycle when a flow loads, and
  Kestra and Azure Data Factory have a child declare what it takes.

## Answer

Built on 2026-10-12 (`src/v2/components/control/run_job.py`, an action;
the loader finds and loads children, `engine.load_job` checks them,
`Runner._run_child` runs one; 42 tests in
`tests/v2/components/test_run_job.py`, seen failing first: "component
type 'RunJob' is not supported in v2").

- **Known at load.** The loader finds the child by v1's rule, loads it
  with a loader of its own, and keeps it in `Job.children` under the
  step's id. The engine then checks it as it checks the parent. Every
  refusal of a child is in the parent's report under the step:
  `component run (RunJob), its job 'child': component in (...)`. The
  files of the jobs that are being loaded are handed down, and a child
  that is among them is refused with the chain
  (`parent.json -> child.json -> parent.json`).
- **Declared inputs.** A name in `context_params` has to be a context
  variable of the child: checked at load. A value is typed as the child
  declares it, whichever way it is given. With the whole context, the
  child gets the parent's variables that it declares and no other: a
  child behaves under a parent as it does alone.
- **A run of its own.** `Runner._run_child` runs the child on a runner
  of its own, with the child's context laid under what it is given.
  Nothing of the child reaches the parent but the return code, the
  reason and the summary.
- **A failed child** fails the step, as any step fails; or the parent
  goes on when `die_on_child_error` is off.
- **A name, not a path.** `process` with a slash is refused: the child
  is looked for beside the parent and nowhere else.
- The child's own `run` block is not looked at. A run for picked rows
  of the parent runs its children whole.
- `engine_config.max_run_job_depth` (v1's) is not read: with cycles
  refused at load there is nothing for a depth to guard.

Not built: rows handed from child to parent (`propagate_child_result`);
a job named when it runs (`use_dynamic_job`); a child in a process of
its own.

The sample `tests/talend_xml_samples/Job_tRunJob_Parent_0.1.item` is no
well-formed XML and no converted run job exists in the samples; the
tests write their own job configs with the keys the converter writes.

Tests written after their code (said because the rule is the other way
round): a child given only what it declares, a child whose job config
cannot be read, and the child's own `run` block. The mutation check
below stands in for seeing them fail.

## Mutation check

Forty-six ways of breaking it, across the loader, the engine, the runner
and the component. Forty-five were caught at first. The last, a failed
child counted as a row that went through, got a test.
