# 90 - How current tools loop and run child jobs

Status: resolved
Type: research

## Question

Before v2 gets file list, flow to iterate, foreach, run job, prejob,
postjob and sleep: how do current orchestration and ETL tools run a piece
of a pipeline once for each item, run a child pipeline, and run set-up
and clean-up steps, and what follows for v2's design? Findings, each with
its source, in `research/2026-10-12-loops-and-job-control.md`.

## Answer

Researched on 2026-10-12 by a research agent, read-only and barred from
starting others, as the map's notes ask:
[Loops and job control](../research/2026-10-12-loops-and-job-control.md)
(1,239 lines; every statement with its source, Talend's templates read
at Talaxie `639d5fd1f776`, the other tools from their own documentation).

Checked by the agent that asked, before relying on it: the loader's
refusal of iterate flows (`src/v2/job/loader.py`), the two keys the
converter writes on an iterate flow (`converter.py`), and v1's own
comment that its postjob runs only after success, "a deliberate
divergence from Talend's always-run cleanup semantics"
(`src/v1/engine/components/control/postjob.py`). All three are as the
file says.

What it found that matters most:

- A converted loop job cannot load on v2 today for three reasons: the
  iterate link is a refused flow type; its two keys for running passes
  side by side are unknown; and the body reads its item as
  `{{java}}((String)globalMap.get("..."))`, refused as Java though it
  is only a lookup.
- In every tool read, a pass is a unit of its own, a list of items has
  a cap, and what a failed item does is one of three things (stop, go
  on and collect, tolerate up to a number).
- For "many files, the same processing, one output" the engines do not
  loop: one read takes a list of files.
- Clean-up runs after a failure in every tool that says, Talend among
  them; v1 alone skips postjob then.
- Talend's file list, "by default", is sorted by path; v1's is in the
  file system's order.

What is built to it is decided in
[Loops and job control: the decisions](100-loops-and-job-control-the-decisions.md).
