# 100 - Loops and job control: the decisions

Status: resolved
Type: grilling

## Question

With
[How current tools loop and run child jobs](90-how-current-tools-loop-and-run-child-jobs.md)
in hand: what are file list, flow to iterate, foreach, run job, prejob,
postjob and sleep built to, and what does the engine have to learn
first? The user left the decisions to the agent (ticket 87); each one
that turns round something v1 does on purpose is marked **for the
user's eye**.

## Answer

Decided on 2026-10-12. The research's section 3 gives the options and
the grounds; this is what is taken from it.

### The engine learns three things, in this order

1. **To read an item in a config string.** A value may hold
   `((String)globalMap.get("key"))`, with or without the cast and the
   outer brackets and with or without the converter's `{{java}}` mark,
   alone or joined by `+` to text in quotes and to `context.x`. A lone
   reference gives the entry's own value, a join gives text. Read when
   the component is built, as context values are. Nothing else under
   `{{java}}` is read: that stays refused. This is a lookup and a join,
   not Java. It also makes what the file jobs leave in globalMap
   (`<id>_CURRENT_FILEPATH`, `<id>_ARCHIVE_FILEPATH`) usable by a later
   subjob, which it is not today.
2. **An iterate link.** It is no flow: the looping component and its
   body are different subjobs. When the looping component's subjob has
   finished, the engine takes its items one at a time, puts each item's
   entries in globalMap and runs the body: the target's subjob and
   whatever that sets off by triggers. A pass is a run of the body, with
   files of its own put in place at its end.
3. **Three phases**: what prejob sets off; everything else; what postjob
   sets off.

### The rules of a loop

- One pass at a time, in the looping component's order. The link's
  `enable_parallel` and `number_parallel` are taken and have no effect
  (said once in the log): Polars already uses every core inside a pass,
  and passes side by side would share globalMap.
- A pass that fails stops the loop: no later pass runs, and the looping
  component has failed, with the item named. "Go on and collect" is not
  built; it can be v2's own key later.
- A die in a body ends the job, as anywhere.
- No item: no pass, said in the log, and the component's own triggers
  fire.
- An item's entries are put before each pass, all of them, and stay as
  the last pass left them when the loop is over (Talend's own).
- A row count of a body's component in globalMap is that pass's; in the
  summary it is the sum over the passes.
- Loops inside loops are allowed.
- A cap, `max_items`, v2's own key, 100,000 when not given (Azure Data
  Factory's): more items than that fails the job before the first pass.
- Refused at load: more than one iterate link to one component; a
  trigger from outside a body into it; a body whose triggers lead back
  to its own loop.
- `run.only` and `run.trace` for a reader that a loop runs are refused
  for now, with the reason: which pass's rows are meant is not designed.

### The components

- **File list**: the research's table 3.5, with these choices. The
  folder that is not there fails the job. Regular files only. No link
  out of the folder, no walk into a linked folder. Names starting with
  a dot are left out unless the mask itself starts with one. "By
  default" is sorted by path, as in Talend; v1's is the file system's
  order. Masks are Talend's own pattern form; a regular expression is
  Python's, and one Python cannot read refuses the job. `error` on
  fails the job when no file is found.
- **Foreach** and **flow to iterate**: Talend's entries. The rows of a
  flow to iterate go to a scratch file in their subjob's one pass and
  are fed to the passes from it in pieces, so memory does not grow with
  them.
- **File unarchive** becomes the start of a loop over what it unpacked.
- **Run job**: the child runs in the parent's process, on v2. Its job
  config is found, loaded and checked when the parent is, its refusals
  under the run job's id, and a job that runs itself, directly or not,
  is refused. Parameters must be context variables the child declares.
  What comes back: `<id>_CHILD_RETURN_CODE` and
  `<id>_CHILD_EXCEPTION_STACKTRACE` (the child's one-line reason), and
  the child's summary inside the parent's. Dynamic jobs and "propagate
  child result" are refused.
- **Prejob, postjob**: markers with one trigger out.
  - **For the user's eye**: postjob runs after a failure and after a
    die, as in Talend and in every other tool read. v1 runs it only
    after success, on purpose, for a reason written nowhere. A step
    meant for success only belongs behind the main subjob's OnSubjobOk.
  - **For the user's eye**: when what prejob sets off fails, the main
    part is not run (and postjob is). Talend runs the main part all the
    same; Airflow does not, and a main part run on a set-up that failed
    fails later and less clearly.
- **Sleep**: stands alone; `pause_duration` in seconds; a value that is
  no number of zero or more fails the job (v1 warns and does not
  sleep). A flow through it is refused.

### Not built, and said so

- Passes side by side; "go on after a failed item".
- One read of many files by a reader (the sound form of "many files,
  one output"): it needs a row's number to say which file, and is a
  ticket of its own after this group.
- Clean-up when the job is stopped from outside (Ctrl-C, SIGTERM).
- tLoop and tParallelize, which v1 does not have either.
