# 108 - Prejob and postjob

Status: resolved
Type: task

## Question

Build prejob and postjob (`Prejob`, `tPrejob`; `Postjob`, `tPostjob`) on
v2, and the three parts of a job they mark, to
[Loops and job control: the decisions](100-loops-and-job-control-the-decisions.md).

## What is known

- Both are marks: no setting, one trigger out, nothing in. The
  converter writes no key for them but the two every component has, and
  writes every trigger that leaves a prejob as OnComponentOk.
- Talend's generator runs every prejob, then every other start, then
  every postjob, each wrapped so that the next is reached whatever
  happened. v1 keeps the order and runs the postjob only when nothing
  failed.
- Of the tools read, all that say so run a clean-up after a failure
  (Talend, Airflow, Kestra, Argo, dbt), and Airflow does not run the
  work when its set-up failed.

## Answer

Built on 2026-10-12 (`src/v2/components/control/prejob.py` and
`postjob.py`, two actions that do nothing; the three parts in
`Runner._run_subjobs`; 14 tests in `tests/v2/unit/test_phases.py`, seen
failing first, and 9 in `tests/v2/components/test_prejob_postjob.py`).

- A component says which part of a job it marks the start of
  (`Component.part`). The engine sorts the subjobs nothing leads to into
  three lists by it and runs them one list after another.
- The clean-up always runs. The job itself runs only when the set-up
  finished; the log says when it is not run.
- The first failure stays the job's error. Every failure is in
  `failures`.
- A subjob runs once, whichever part sets it off.
- A trigger or an iterate link to a prejob or a postjob refuses the job.

**For the user's eye**, both decided in ticket 100 and built as decided:

- v1 runs the postjob only after success, on purpose. v2 runs it after
  a failure and after a die. A converted job whose postjob held a step
  for success only (a mail, an archive of the input) will now run that
  step after a failed run too.
- Talend and v1 run the job itself after a prejob that failed. v2 does
  not.

Not built: a clean-up when the job is stopped from outside.

The sample `tests/talend_xml_samples/Job_tPreJob_tPostJob_0.1.item`
names its components `tPreJob` and `tPostJob`, which are not Talend's
names; the converter does not know them and writes two placeholders. It
was left alone: the converter is not this work's.

Mutation check: fifteen ways of breaking it. One was no test of
anything (the broken code did not load). Of the fourteen others, all
were caught, one of them only after a test was added: a subjob that two
parts set off runs once.
