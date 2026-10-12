# How a job runs

- Components joined by flows form a subjob. A subjob is built as one lazy
  Polars plan and run in a single pass: a file is read once however many
  outputs hang off it, and rows are streamed, not held.
- No file of a subjob is put in place unless the whole subjob succeeded.
  Each file is written beside its target. At the end every file is first
  put in its encoding, which is the last thing the rows can fail, and only
  then are the files moved in. A run that is stopped leaves no temporary
  file behind.
- Subjobs run in v1's order: those nothing triggers in job-config order,
  and what a subjob triggers right after it. `OnSubjobOk`, `OnSubjobError`,
  `OnComponentOk`, `OnComponentError` and `RunIf` are supported. Of the
  subjobs one subjob sets off, those of a component's own triggers
  (`OnComponentOk`, `RunIf`) come first, component by component, and those
  of `OnSubjobOk` with the last component; what fires together goes by
  `output_id`. After a failed subjob its error triggers fire and the other
  subjobs still run; the job's status is then `failed`.
- A `RunIf` is judged twice, as in v1: when its own component is done, on
  what globalMap holds by then (the count of a later component of the same
  subjob is not there yet), and once more when the subjob is done.
- Context values in config strings (`${context.x}` and v1's bare
  `context.x`) are resolved when each component is built, so a value loaded
  by a context load in an earlier subjob is seen. So is a globalMap entry
  an earlier subjob left, written as Talend writes it
  (`((String)globalMap.get("key"))`): see
  [A value looked up while the job runs](from-v1-to-v2.md#a-value-looked-up-while-the-job-runs).
- Row counts: every file output sets `<id>_NB_LINE` in the globalMap. The
  counts of other components (`_NB_LINE`, `_NB_LINE_OK`, `_NB_LINE_REJECT`)
  are taken only when something in the job reads them, or when the run asks
  for the counts of every component (`--row-counts`, or
  `run_job(..., row_counts=True)`). They follow v1's rules: rows read, rows
  passed on, rows rejected; a map counts the rows of its outputs, a join the
  rows of its main input, a full-row input every line of its file.
- After each component the engine makes its output match the declared
  schema, as v1 does: column order, columns nobody produced, types, decimal
  places, and columns that may not hold a missing value.


## Loops

An iterate link leads from a component that makes a list of items (a file
list, say) to the start of what is run for each of them. It is no flow: no
rows go by it, and its two ends are different subjobs.

- When the subjob of the looping component has finished, the engine takes
  its items one at a time, puts the item's entries in globalMap, and runs
  the body: the subjob the link leads to, and whatever that sets off by
  triggers. A pass is a run of the body. Its files are put in place when
  it ends, as for any subjob: an output that is to hold the rows of every
  pass appends.
- The item is read in a config value as Talend writes it
  (`((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`): see
  [A value looked up while the job runs](from-v1-to-v2.md#a-value-looked-up-while-the-job-runs).
  The number of the pass is `<id>_CURRENT_ITERATION`, from 1. The entries
  stay as the last pass left them when the loop is over.
- One pass at a time, in the order of the items. Talend can run passes
  side by side; v2 does not, and says so in the log when the job config
  asks for it. Polars already uses every core inside a pass, and passes
  side by side would share globalMap.
- A pass that fails stops the loop: no later pass runs, and the looping
  component has failed, with the item it stopped at. The error triggers
  inside the body fire in that pass, and those of the looping component
  after it. A die in a body ends the job.
- No item, no pass: the log says so, and the triggers of the looping
  component fire as after any loop.
- Items that cannot be read on (the file a long list is kept in was
  taken away while the loop ran) fail the looping component as a pass
  that failed does, with how many passes were run.
- A row count of a component in the body (`<id>_NB_LINE`) is, in
  globalMap, that of the pass. The summary has the sum over the passes,
  and under `loops`, for each looping component, its `items`, the
  `passes` that were run, and the `failed_item` when one failed.
- A loop may be in a loop.
- A loop has a cap: `max_items` on the looping component, 100,000 when
  not given. More items than that fail the job before the first pass.
- Refused when the job loads: an iterate link from a component that makes
  no list; two iterate links from one component, or to one; a link that
  leads into the middle of a subjob; a trigger from outside a body into
  it; a trigger from a body back to its own loop.
- Not built: a run for picked rows (`run.only`) of a reader that a loop
  runs is refused, since which pass's rows are meant has no answer yet.

## Set-up and clean-up

A job runs in three parts: what a prejob sets off, the job itself, and
what a postjob sets off. The two components do nothing themselves: each
marks where a part starts, and a trigger leads from it to the first
subjob of that part.

- The set-up runs first and the clean-up last, wherever the components
  are written in the job config. A job with neither is the middle part
  alone, as before.
- The clean-up runs whatever became of the job: after a failure, and
  after a die. That is what makes it a clean-up. A step meant only for a
  job that succeeded belongs behind the job's own subjob, on its
  OnSubjobOk trigger.
- When the set-up fails or ends in a die, the job itself is not run: the
  log says so. What it would have worked with is not there, and it would
  fail later and less clearly. The clean-up still runs.
- A clean-up that fails fails the job. When the job had failed before
  it, the job's error stays the first one, and both are in `failures`.
  A die in the clean-up ends the clean-up.
- A subjob runs once, whichever part sets it off.
- Refused when the job loads: a trigger or an iterate link that leads to
  a prejob or a postjob. Nothing leads to where a part starts.
- Not built: a clean-up when the job is stopped from outside (Ctrl-C,
  a kill).

Not as in v1 and not quite as in Talend:
[Prejob and Postjob](own-rule/loops-and-job-control.md#prejob).

## Types and missing values

Declared types are `str`, `int`, `float`, `bool`, `datetime`, `date` and
`Decimal`; `date_pattern` is a Python `strftime` pattern (a Java-style
pattern such as `yyyy-MM-dd` is understood too). A `Decimal` column holds
its declared `precision` places, or ten when none is declared. A column
declared `object`, which is what Talend's Object type converts to, is held
as text.

Text read from a file is never missing: an empty field is empty text. For
every other type an empty or blank field is a missing value, except `bool`,
where it is `false` as in v1. Missing values are written as empty fields.
