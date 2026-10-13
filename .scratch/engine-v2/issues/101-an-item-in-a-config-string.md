# 101 - An item in a config string

Status: resolved
Type: task

## Question

The first thing the engine has to learn for loops
([Loops and job control: the decisions](100-loops-and-job-control-the-decisions.md)):
to read a globalMap entry or a context variable in a config string,
alone or joined to text, as the converter leaves it.

## What is known

- The converter leaves a value Talend computed as Talend wrote it, less
  one pair of outer quotes, and marks what looks like Java with
  `{{java}}`: a reader's path in a loop arrives as
  `{{java}}((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`.
- v2 refused every value under the mark, and passed a value without it
  that names globalMap on as written: the path of a reader was then the
  text of the reference. What the file jobs leave in globalMap
  (`<id>_CURRENT_FILEPATH`, `<id>_ARCHIVE_FILEPATH`) could not be used
  by a plain config value at all.
- A die's and a warn's message and a fixed flow input's values read a
  reference their own way, with their own rule for an entry that is not
  there (0, or the text as written), as v1 has it.

## Answer

Built on 2026-10-12 (`src/v2/engine/references.py`; read in
`RunContext.resolve`; 50 tests in `tests/v2/unit/test_references.py`,
seen failing first).

- Read: `globalMap.get("key")` with or without a cast and Talend's
  brackets, `context.name`, text in double quotes, joined by `+`,
  brackets round the whole. One term is the value itself; a join is
  text. Anything else is not read.
- Under the mark such a value is no Java any more: the job loads, and
  the value is looked up when its component is built. An entry or a
  variable that is not there fails the component, by name. The check at
  load lets an entry pass that is not there yet, as it does for an
  expression.
- Without the mark, only a value that names a globalMap entry is read,
  and when its entry is not there it is left as written: no value that
  loaded before means something else now, and the three components
  that read references their own way see what they saw.
- **For the user's eye**: a converted job whose paths are written
  `context.dir + "/in.csv"` under the mark loaded only after a rewrite
  by hand; it loads as it is now. One loader test had that very value
  as its example of Java to refuse; it has real Java now.
- Mutation check: 20 ways of breaking it, 16 caught at first; three of
  the others got a test (text alone under the mark, a join without the
  mark, an entry missing under the mark), and one showed a part of a
  pattern that could never matter, which was taken out.
- Written up in `docs/v2/from-v1-to-v2.md`, "A value looked up while
  the job runs".
