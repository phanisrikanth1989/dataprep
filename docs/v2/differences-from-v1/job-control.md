# Job control

The components that steer a job and hold no rows of their own.

Where v2 differs from v1, each on purpose. v1 is the answer key for
everything else these components do. ([The other pages](README.md).)

## Context load

- The flow's `key` and `value` columns are checked even when it has no
  rows. v1 checks once a row arrives.
- A policy other than ERROR, WARNING, INFO or NO_WARNING is refused at load.

## Die

- It stops the whole job, as in v1 and Talend: no trigger fires after it
  and no subjob follows, also not one nothing triggers. Any other failure
  fails its own subjob and lets the job go on.
- Set off by a trigger, it stops the job with v1's words.
- With a flow leading to it, it stops the job when a row arrives and not
  otherwise, as in Talend, and names the first such row. v1 stops the job
  whether a row arrives or not, so a die behind a filter's rejects stops
  every run.
- Talend's names are left in globalMap beside v1's (`<id>_DIE_MESSAGE`,
  `_DIE_MESSAGES`, `_DIE_CODE`, `_DIE_PRIORITY`).
- The exit code is said in the message and left in globalMap; the command
  line ends with 1 for any job that failed, as for every failure. (v1
  does not end with it either.)
- `exit_jvm` refuses the job: there is no JVM to exit.

## Warn

- One that is to hand rows on with no flow leading to it refuses the job.
  v1 hands on no rows.
- Set off by a trigger, it logs its message as in v1. A message of
  priority 4 or more goes to stderr, like every warning: a job that warns
  is no clean run by that measure, which is what a warning is for.
- With a flow leading to it, it hands the rows on and speaks once when a
  row arrives, and not at all when none does. v1 speaks once either way;
  Talend speaks for every row.
- Talend's names are left in globalMap beside v1's (`<id>_WARN_MESSAGES`,
  `_WARN_CODE`, `_WARN_PRIORITY`).

## Set global var

- With a flow leading to it, the entries are put when the subjob is done:
  v2 runs a subjob in one pass. A later subjob and a trigger's condition
  read them, as in v1; a trigger that leaves a component before it is
  judged without them, as in v1. A component of the same subjob that
  reads one of them (`globalMap.get("key")` or `globalMap["key"]` in its
  config) fails the job before anything is written: v1 runs the
  components of a subjob one after the other, so what follows this one
  there reads the last row's value, and Talend's reads each row's. Such a
  job has to be cut in two subjobs. A key put together in code is not
  seen by that check.
- One that is to hand rows on with no flow leading to it refuses the job.
  v1 hands on no rows.
- Nothing is put when no row arrives, as in Talend. v1 puts the values as
  they are written, the text `row1.name` among them.
- A value is a column of the row when it is written `<flow>.<column>`
  with the name of the flow that leads to the component. v1 takes any
  word before the dot.
- An entry with no key refuses the job. v1 fails when it comes to it, or
  passes over it with `die_on_error` off.
- A value that is a Java expression refuses the job, as everywhere.
