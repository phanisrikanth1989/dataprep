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
  by a context load in an earlier subjob is seen.
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


## Types and missing values

Declared types are `str`, `int`, `float`, `bool`, `datetime`, `date` and
`Decimal`; `date_pattern` is a Python `strftime` pattern (a Java-style
pattern such as `yyyy-MM-dd` is understood too). A `Decimal` column holds
its declared `precision` places, or ten when none is declared.

Text read from a file is never missing: an empty field is empty text. For
every other type an empty or blank field is a missing value, except `bool`,
where it is `false` as in v1. Missing values are written as empty fields.
