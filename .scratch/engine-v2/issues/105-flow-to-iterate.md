# 105 - Flow to iterate

Status: resolved
Type: task

## Question

Build flow to iterate (`FlowToIterate`, `tFlowToIterate`) on v2, to
[Loops and job control: the decisions](100-loops-and-job-control-the-decisions.md):
the one loop whose list is data, and so the one that can be as long as
a file.

## What is known

- The converter writes `default_map` and `map_entries`. Talend puts
  `<flow>.<column>` for every column, or the job's own entries, and
  runs the body while the row is being read; v1 takes every row into
  memory first.
- There is a converted sample job
  (`tests/talend_xml_samples/converted_jsons/Job_tFlowToIterate_0.1.json`):
  a file of file names, a loop over its rows, a reader of the file each
  row names, a map, one output.

## Answer

Built on 2026-10-12 (`src/v2/components/iterate/flow_to_iterate.py`, a
sink that starts a loop; 21 tests in
`tests/v2/components/test_flow_to_iterate.py`, seen failing first).

- The rows go to a scratch file (Arrow IPC) in their subjob's one pass,
  as any output's rows go to its file. When the subjob has finished the
  passes are fed from it 10,000 rows at a time. Tried here on three
  million rows: a piece of 10,000 from two million rows in takes 3 ms,
  so reading far into the file costs no more than reading its start.
- Values keep their type: a Decimal is a Decimal in globalMap, a date a
  date.
- The engine learned two things for it: a component is told the names
  of the flows that reach it (`arriving`), and a loop's items may come
  with something to do when they are needed no more (`done`), which the
  engine does however the loop ended, and at the end of a run for items
  nothing looped over.
- The scratch file's name holds a name of the run's own
  (`RunContext.token`), so that two runs in one process do not share
  one. The first version named it by the component's id alone; the
  mutation check showed the tests could not tell a file left behind,
  since every test left the same name. They watch the file itself now.
- The converted sample job runs once its map's five Java expressions
  are written in Python.
- Mutation check: 12 ways of breaking it, 9 caught at first; the three
  others each got a test (the number of a row beyond the first piece,
  the scratch file put away, a row taken only when its pass is due).
- The full run then showed two paths no test reached (an entry for a
  column the flow turns out not to have, where no column is declared;
  a scratch file already gone when the loop is over). Each got a test
  after its code, which is the wrong order; breaking the code on purpose
  showed both tests fail without it.
- It is the one component that reads rows back and walks them, and is
  named for it in the two lists of `tests/v2/test_rules.py`: a row is
  what a pass is run for.
