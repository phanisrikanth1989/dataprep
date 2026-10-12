# 102 - The iterate link

Status: resolved
Type: task

## Question

The second thing the engine has to learn for loops
([Loops and job control: the decisions](100-loops-and-job-control-the-decisions.md)):
an iterate link, and running what it leads to once for each item.

## What is known

- The loader refused an iterate flow ("iterate flows are not supported
  in v2"), and the two keys the converter writes on one
  (`enable_parallel`, `number_parallel`) as unknown.
- The runner ran every subjob once (`if index in done: continue`), and
  built a subjob anew each time it ran one, with config values resolved
  then: running a subjob again with other values was already what the
  code did.

## Answer

Built on 2026-10-12 (25 tests in `tests/v2/unit/test_iterate.py`, with
stand-in components, seen failing first; the engine's other tests
unchanged and passing).

- **The job model** has `Iterate` links beside flows and triggers
  (`src/v2/job/model.py`). `graph.bodies` says what each loop runs: the
  subjob its link leads to, and every subjob that one sets off by a
  trigger or by a link of its own.
- **The loader** keeps an iterate flow as a link, and refuses one from a
  component that starts no loop, a second one from or to a component,
  one into the middle of a subjob, a trigger from outside a body into
  it, and one from a body back to its own loop.
- **A looping component** sets `loops = True` and hands its items to the
  engine with `loop_over` while it runs: how the log names each, and the
  globalMap entries of its pass. Items may be made as their passes come
  (`count=`), for a list too long to hold.
- **The runner**: what was its one walk over the subjobs is `_drain`,
  which runs some subjobs and whatever they set off, each once. The job
  is one drain; each pass of a loop is a drain over the body. That is
  all a pass is, so triggers, error triggers, a die and a loop inside a
  loop work in a body as they do anywhere.
- A pass that fails stops the loop, and the looping component has
  failed: `its loop stopped at item 2 of 3 (b): in failed: <why>`. The
  job's `error` stays the first failure, which is the body's.
- Before each pass what a source of the body made for the pass before
  (`RunContext.made`) is dropped.
- `<id>_NB_LINE` of an output in globalMap is what its subjob wrote in
  this run of it, which in a loop is the pass's; it was the sum over
  runs, which for a job without loops is the same number. The summary's
  `rows` and `counts` are sums over the passes.
- The summary has `loops`: for each looping component its `items`,
  `passes`, and `failed_item`.
- A run for picked rows of a reader inside a loop is refused, with the
  reason.
- Mutation check: 38 ways of breaking it, 34 caught at first; three of
  the others got a test (the count left in globalMap after the loop, a
  cap of none, items made one at a time), one was no valid mutant.

Written up in `docs/v2/how-a-job-runs.md` ("Loops") and, for whoever
writes a looping component, in `docs/v2/writing-a-component.md`.

Not here: the looping components themselves (file list, foreach, flow to
iterate, the unarchive), prejob and postjob, run job, sleep.
