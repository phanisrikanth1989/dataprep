# Loops and job control: how current tools do it, and what follows for v2 (ticket 90)

Answers ticket 90 in `.scratch/engine-v2/issues/`: how current orchestration
and ETL tools run a piece of a pipeline once for each item, run a child
pipeline, run set-up and clean-up steps and wait, and what follows for v2's
file list, flow to iterate, foreach, run job, prejob, postjob and sleep.
Options with a recommendation each; nothing here is decided. Researched
2026-10-12.

## How to read this file

- Sources are primary only: each tool's own documentation, source code and
  release notes. A sourced statement ends with a tag in square brackets;
  section 6 resolves every tag to a URL and a version. Quotations are word
  for word; to keep the file plain ASCII a long dash in a source is written
  "-" and curly quotes are straight. A source's link markup is left out of
  a quotation; its emphasis marks (`*`, `_`) are kept. "L" numbers are
  lines of the file at the tag or commit named.
- "Reasoning:" marks what is mine, drawn from the sourced statements around
  it. "unconfirmed" marks what I did not find in a primary source I read.
  "not stated" means the page I read does not say.
- "Observed here" marks what was seen on this machine by reading a
  signature or docstring of an installed library, by calling a pure
  function, or by running the converter in memory on a sample (nothing was
  written). This machine is macOS with Python 3.14.6 and Polars 1.44.2;
  production is Python 3.12+ on RHEL, so every "observed here" is
  provisional until section 5 is done there.
- Nothing was benchmarked, no job was run, and Polars read no file.
- Stamps. v1, v2 and the converter: commit `c350cd5d` on
  `feature/engine-v2` (2026-10-12). The `file:line` references below were
  checked against that commit (`git show c350cd5d:<path>`). The branch moved on
  while this was written (`be2ee9da` by the end, which changed
  `src/v2/engine/runner.py` and `src/v2/components/base.py`), so the
  numbers may be a few lines off in the working tree. Talend: the code
  templates of Talend Open Studio as kept in `Talaxie/tdi-studio-se` at
  commit `639d5fd1f776` (2024-10-20), and Qlik's help pages as served on
  2026-10-12. Every other tool: the release named in section 6.

## 1. The ten findings that matter most

One sentence each; the detail and the full quotations are in section 2.

1. A converted loop job cannot load on v2 today: the iterate link is a
   refused flow type, its two parallel keys are unknown flow keys, and the
   body's path arrives as `{{java}}((String)globalMap.get("..."))`, refused
   as Java though it is only a lookup. (`src/v2/job/loader.py:484-486`,
   `:148-155`, `:387-391`; `src/converters/talend_to_v1/converter.py:249-258`;
   `.../components/file/file_input_delimited.py:136-140`; section 4)
2. In Talend the loop and its body are one subjob, the item is nothing but
   globalMap entries put before each pass, the file list is built whole
   first, and "By default" order is a sort by path, not the file system's
   order as v1 has it. [TL-FILELIST-BEGIN L300-303, L386-388, L411-435]
3. The orchestrators read give each item a unit of its own (a task
   instance, a child run), and where state is shared between passes they
   name it as the hazard: "SetVariable can't be used inside a ForEach
   activity that runs in parallel as the variables are global to the whole
   pipeline". [ADF-FOREACH] [KE2-LOOP] [TL-ITER-HEAD L81-99]
4. What a failed item does is the real choice, and the tools split three
   ways: stop (Step Functions inline, Argo, Talend), go on and collect
   (Prefect, Hop), tolerate up to a threshold (Step Functions distributed,
   default zero; Snowflake `SKIP_FILE_num`). [SFN-INLINE] [ARGO-DAG]
   [PF-CONC] [HOP-PEXEC] [SFN-DIST] [SF-COPY]
5. A cap on the number of items is normal (Airflow 1024 by default, Azure
   Data Factory 100,000, Step Functions inline 40 at once and 256 KiB), and
   a long list is fed from a file in batches, not held. [AF-MAP]
   [ADF-FOREACH] [SFN-MAP] [KE1-ITEM] [KE2-LOOP]
6. For "many files, same processing, one output" the engines do not loop:
   one read takes a list or a pattern and adds the file's name as a column,
   and Dagster calls a run for each part under a parallel engine "extra
   overhead". [PL-SIG] [DK-MULTI] [SP-FILEFORMAT] [SF-META] [DG-BACKFILL]
   [DG-DVP]
7. One read of many files is one unit: dropping one bad file and keeping
   the rest costs memory (Snowflake's `SKIP_FILE` "buffers an entire file")
   or correctness (Spark keeps "the contents that have been read"), and
   Polars 1.44.2 has no way to skip a file and leaves empty files out of a
   pattern without a word. [SF-COPY] [SP-GENERIC] [PL-SIG] [PL-PATHS]
8. Only the writer can say reliably that a file is finished ("files must be
   atomically placed in the given directory"); what a reader can do
   (unchanged size, a done-file, a minimum age) is a fallback, and Talend
   has it in tWaitForFile, not in tFileList. [SP-STREAM] [CAMEL-FILE]
   [HOP-WAITFILE] [TL-WAITFILE-BEGIN L293-312]
9. Clean-up runs after a failure in every tool whose pages say (Talend,
   Airflow, Kestra, Argo, dbt), in Talend after a tDie too unless "Exit the
   JVM immediately" is ticked; v1 alone skips postjob then, for a reason
   nobody wrote down; and Talend, unlike Airflow, runs the main part after
   a failed prejob. [TL-FOOTER L1101-1111, L1260-1270]
   [TL-FOOTER-SKEL L13-57] [QL-PREPOST] [TL-DIE-MAIN L75-112] [AF-SETUP]
   (`src/v1/engine/executor.py:227-243`)
10. A child job in Talend runs in the parent's process by default, takes
    its parameters as text and gives back a return code; current tools add
    declared inputs and outputs and refuse a cycle before anything runs
    ("any cycle makes the flow invalid"), which v2's one refusal report can
    do for the whole tree. [TL-RUNJOB-MAIN L567-631] [KE-SUBDOC]

## 2. Findings by question

### 2.1 Running a piece of a pipeline once for each item (question 1)

Order, concurrency, failure, an empty list:

| Tool (version) | Order of the items | How many at once | When one item fails | Empty list |
|---|---|---|---|---|
| Airflow dynamic task mapping (3.3.2) | copies carry an integer index; for a cross product "the order of expansion is not guaranteed" [AF-MAP] | all copies are scheduled together; `max_active_tis_per_dag` and `max_active_tis_per_dagrun` cap them [AF-MAP] [AF-OP] | each copy is a task instance with retries of its own; what follows goes by trigger rules (default `all_success`); a Dag's `fail_fast` "Fails currently running tasks when task in Dag fails" [AF-OP] [AF-DAG] | "no new tasks will be created and the mapped task will be marked as SKIPPED" [AF-MAP] |
| Dagster dynamic outputs (1.13.26) | not stated; each copy has a `mapping_key` [DG-DYN] | the run executor's `max_concurrent`; the multiprocess executor defaults to `multiprocessing.cpu_count()` [DG-EXEC] | "Failed sub-pipelines can be retried independently" [DG-FAN]; whether the others go on: not stated | not stated |
| Dagster partitions (1.13.26) | a run for each partition ("Dagster will launch N separate runs"), or one run over a range with `BackfillPolicy` `single_run` [DG-BACKFILL] | the run queue | per run | not applicable |
| Prefect `.map` (3.8.8) | the futures come back as a list in input order [PF-CONC] | the flow's task runner; default `ThreadPoolTaskRunner`, sized by `max_workers` [PF-RUN] | the author's code decides: `.result()` raises, or `wait()` and each future's `.state` "to run concurrent work to completion, even if some tasks fail" [PF-CONC] | not stated |
| Kestra ForEach (1.3.42) | with `concurrencyLimit` 1 "only one task group runs at a time, in order" [KE1-FOREACH] | `concurrencyLimit`, default 1; 0 is no limit [KE1-FOREACH] | "By default, a failed task stops all downstream tasks"; `allowFailure` lets the run go on and end in WARNING [KE-ERRORS] | not stated |
| Kestra ForEachItem (1.3.42) | by batch number | one subflow run for each batch | `transmitFailed` (default true) fails the parent "if the subflow execution fails or is killed", only with `wait`; on restart, `RETRY_FAILED` restarts the failed subflow runs only [KE1-ITEM] | not stated |
| Kestra Loop (2.0.5, whose source tree no longer holds ForEach and ForEachItem) | 1 is "in order" | `concurrencyLimit`, default 0: "all task groups run in parallel" (the default was 1 in ForEach) [KE2-LOOP] | `transmitFailed` (default true): "fail the current task if any loop iteration fails or is killed"; `breakWhen` stops new passes on a condition [KE2-LOOP] | not stated |
| Azure Data Factory ForEach (page of 2026-08-04) | in sequence when `isSequential` is true | parallel by default; `batchCount` default 20, at most 50 [ADF-FOREACH] | not stated on the page | not stated |
| Step Functions Map, inline | with `MaxConcurrency` 1, "Items in the array are processed in the order of their appearance in the input" [SFN-INLINE] | default 0 is no limit, and the mode "supports up to 40 concurrent iterations" [SFN-MAP] [SFN-INLINE] | "the failure of any iteration causes the Map state to fail. All iterations stop when the Map state fails." [SFN-INLINE] | not stated |
| Step Functions Map, distributed | not stated | up to 10,000 child runs; `MaxConcurrency` [SFN-DIST] | `ToleratedFailurePercentage` or `ToleratedFailureCount`; default zero, "the workflow fails if any one of its child workflow executions fails or times out"; at 100 it never fails [SFN-DIST] | not stated |
| Argo Workflows (4.1.5) | not stated | parallel ("once for each item in parallel"); `parallelism` on a workflow or template restricts it [ARGO-LOOPS] [ARGO-SYNC] | "By default, DAGs fail fast: when one task fails, no new tasks will be scheduled."; with `failFast` false "all branches will run to completion" [ARGO-DAG] | not stated |
| Apache Hop Pipeline Executor (2.19.0-rc1; "similar to the Workflow Executor transform, but works with pipelines") | the stream's row order: one run for each row, or for each group of rows | "You can launch multiple copies of the transform to run in parallel" [HOP-PEXEC] | each run gives a result row (`ExecutionResult`, `ExecutionNrErrors`...); the page advises to "at least check if there have been any issues in one of your child pipelines" [HOP-PEXEC] | no row, no run (inferred) |
| Apache Hop Repeat action | one after another, until a variable is set or an End repeat action runs, which "leaves a flag in the parent workflow to signal it can stop repeating at the next opportunity" [HOP-REPEAT] [HOP-REPEND] | one | not stated | not applicable |
| Talend iterate link, as generated | the list's order (file list: sorted, see 2.3); rows as they arrive | one at a time, unless the link has "Enable parallel execution": `new TalendThreadPool(<NUMBER_PARALLEL>)` [TL-COMP-HEAD L62] | in sequence: the exception leaves the loop and fails the subjob (inferred from the templates, see below); in parallel: `talendThreadPool.stopAllWorkers()`, and the exception is thrown again once the pool has been waited for [TL-ITER-FOOT L65-84] [TL-COMP-FOOT L533-550] | file list: no pass, and an error only when "Generate Error if no file found" is ticked [TL-FILELIST-END L25-27] |

How the item is handed over, what identifies a pass, retries, limits, results:

| Tool | How the item reaches the body | What identifies a pass | Retries | Limit on the number of items | How results are gathered |
|---|---|---|---|---|---|
| Airflow | a keyword argument given to `expand()`, constants to `partial()`; "it is only possible to map against a dict, a list, or one of those types stored in XCom" [AF-MAP] | the index; `map_index_template` gives it a name shown in place of "0" and "1" [AF-MAP] | per copy: `retries`, `retry_delay` (default 300 s), `retry_exponential_backoff`, `max_retry_delay` [AF-OP] | `[core] max_map_length`, default 1024; a longer list makes the task that returned it fail [AF-MAP] | the next task gets a "lazy sequence" over every copy's value; `list(values)` loads them all [AF-MAP] |
| Dagster dynamic outputs | the value of each `DynamicOutput`, passed on by `.map` [DG-DYN] | the `mapping_key` [DG-DYN] | an op's `RetryPolicy` with `Backoff` and `Jitter`; `Failure(allow_retries=False)` for what a retry cannot mend [DG-RETRY] | none stated; for partitions "limiting the number of partitions for each asset to 100,000 or fewer" [DG-PART] | `.collect()`: "The dependent op will receive a list containing all the values" [DG-DYN] |
| Prefect | a function argument; `unmapped()` for a constant that is itself a list [PF-CONC] | a task run for each element | `retries`, `retry_delay_seconds` (a list, or `exponential_backoff`), `retry_jitter_factor`, `retry_condition_fn` [PF-RETRY] | none stated; "Using .map can create many task instances very quickly, which might exceed your resource availability" [PF-RUN] | a list of futures; `futures.result()` [PF-CONC] |
| Kestra ForEach 1.3 | `{{ taskrun.value }}` and `{{ taskrun.iteration }}`; `parent.taskrun.value` from a nested loop [KE1-FOREACH] | a task run for each value | not read | none stated; "For large fan-out, consider triggering subflows per item for better scaling" [KE1-FOREACH] | not read |
| Kestra ForEachItem 1.3 | the items are a file in Kestra's storage, split into batches (`rows` default 1, or `bytes`, or `partitions`); the body is a subflow, given the batch file's address as `taskrun.items` [KE1-ITEM] | a subflow run for each batch | `restartBehavior` on restart | the list is a file, never a value in memory | counters for each state, "updated in real-time"; `numberOfBatches`; `uri` of "the file gathering outputs from each subflow execution" [KE1-ITEM] |
| Kestra Loop 2.0 | `item.value`, `item.index`, `item.key`; `item.parent.value` from a nested loop; a storage address gives "one iteration per line", read a batch at a time [KE2-LOOP] | a sub-execution for each pass | not read | none stated | `iterationCount`, `terminatedIterations` for each state, and `outputs`: only what the loop declares ("to access any loop iteration task outputs outside of the loop, you need to define `outputs`"); `fetchType` `STORE` writes them to storage [KE2-LOOP] |
| Azure Data Factory | `@item()` [ADF-FOREACH] | not stated | not read | "a maximum of 100,000 items"; "You can't nest a ForEach loop inside another ForEach loop (or an Until loop)" [ADF-FOREACH] | "utilize Variables and Append Variable activity", but not in parallel (finding 3) [ADF-FOREACH] |
| Step Functions inline | `ItemSelector`, with `$$.Map.Item.Value` [SFN-INLINE] | events in the parent's history | "the retry policy applies to all Map state iterations, instead of only failed iterations" [SFN-INLINE] | "a limit of 256 KiB on the input payload size and 25,000 entries in the execution event history" [SFN-MAP] | "the output of the Map state is a JSON array, where each item is the output of an iteration" [SFN-INLINE] |
| Step Functions distributed | `ItemReader`: a JSON array, a JSON or CSV file in S3, a list of S3 objects, an S3 inventory; `ItemBatcher` hands a batch to each child [SFN-MAP] [SFN-DIST] | a child run with a history of its own; a "Map Run" resource; metrics [SFN-MAP] | "The retry policy applies to all the child workflow executions and not just the failed execution"; a retry "creates a new Map Run" [SFN-DIST] | "millions of data items" [SFN-MAP] | `ResultWriter`: "exports executions with the same status to their respective files" in S3 [SFN-DIST] |
| Argo | `{{item}}` or `{{item.key}}`; the list from `withItems`, `withSequence`, or `withParam`, a JSON array an earlier step made [ARGO-LOOPS] | a node for each item | `retryStrategy`: `limit`, `retryPolicy` (default `OnFailure`), `backoff` with `duration`, `factor`, `maxDuration` [ARGO-RETRY] | the workflow object, each node's status included, "must be under 1MB"; beyond that it is compressed or kept in an SQL database [ARGO-OFFLOAD] | "The output of all iterations can be accessed as a JSON array, once the loop is done." [ARGO-LOOPS] |
| Hop Pipeline Executor | parameters mapped from fields of the row; "You can pass *parameters and variables* downstream only."; "Row grouping" by a count, a field's value or a time [HOP-PEXEC] | a result row for each run | none stated | none | the execution-result fields; or "result rows after execution", "a rowset that was copied to memory by the child pipeline" [HOP-PEXEC] |
| Talend | `globalMap.put("<id>_CURRENT_FILE", ...)` and the like before each pass; the body reads `((String)globalMap.get("<id>_CURRENT_FILEPATH"))` [TL-FILELIST-BEGIN L430-435] | none but a log line and the link's `exec<N>` statistic | none | none; the whole list is held as `java.util.List<java.io.File>` [TL-FILELIST-BEGIN L300] | none; the last pass's values stay in globalMap |

What the sources say outright, where a design choice hangs on it:

- No nesting, by choice. Airflow: "It is not currently permitted to do task
  mapping nested inside a mapped task group. While the technical aspect of
  this feature is not particularly difficult, we have decided to
  intentionally omit this feature since it adds considerable UI
  complexities". [AF-MAP] Azure Data Factory sends a nested loop to a child
  pipeline. [ADF-FOREACH] Kestra and Argo nest. [KE2-LOOP] [ARGO-SYNC]
- A pass's own unit of work. Airflow on a mapped group of tasks: "the first
  `replace_defaults` would be able to run before
  `convert_to_yaml("data2.json")` is done, and does not need to care about
  whether it succeeds or not" ("depth-first execution"). [AF-MAP]
- What a per-item run costs. Dagster: "Use Dagster dynamic outputs when:
  Each item takes 5+ minutes to process (overhead is negligible)" and "Use
  Python parallelism when: Each item takes seconds to minutes to process".
  [DG-DVP] Prefect: "too many small tasks might create overhead". [PF-RUN]
- Shared state. Prefect: "the default `ThreadPoolTaskRunner` runs each task
  in a separate thread, which means that any global state must be
  threadsafe." [PF-RUN] Azure Data Factory, on parallel passes that write:
  "If the concurrent iterations are writing concurrently to the exact same
  file, this approach most likely causes an error." [ADF-FOREACH]
- The list as data. Hop has no step that loops over files: its Get File
  Names transform puts "The information about the retrieved files ... as
  rows onto the stream" (name, path, size, modified time and more), and a
  pipeline is then run "once for every result row from a previous
  pipeline", or by the executor once for each row. [HOP-GETFILES]
  [HOP-PIPE] [HOP-PEXEC]

Talend's iterate link, from its templates:

- The body is code inside the loop. `tFileList_begin` ends with the loop
  open (`for (int i_<cid> = 0; ...){`, L411) and `tFileList_end` begins by
  closing it (L18); the components the link leads to are generated between
  the two. The loop sits inside the subjob's one try block, which turns any
  exception into a `TalendException` and throws it on (`subprocess_footer`
  L221-254). So in sequence the first failing pass ends the loop and the
  subjob. (Inferred from the templates, not run.) [TL-FILELIST-BEGIN]
  [TL-FILELIST-END] [TL-SUBFOOTER]
- A trigger that leaves the looping component is generated in that
  component's end part, after the loop is closed; with a parallel link the
  pool is waited for first (`mtp_<target>.waitForEndOfQueue()`).
  [TL-COMP-FOOT L462-474] A trigger that leaves a component of the body is
  generated inside the loop, so it fires in every pass (inferred).
- "A component can be the target of only one Iterate connection. The
  Iterate connection is mainly to be connected to the start component of a
  flow (in a subJob)." [QL-ITER]
- Loops nest: tFileList, tForeach, tLoop, tRunJob and tSleep each accept an
  iterate link coming in (`CTYPE="ITERATE" MAX_INPUT="1"`); tFlowToIterate
  does not (`MAX_INPUT="0"`) but takes a flow, so it can stand at the end
  of a body. [TL-FILELIST-XML L19] [TL-FOREACH-XML L27] [TL-RUNJOB-XML L31]
  [TL-SLEEP-XML L29] [TL-F2I-XML L30-31] (tLoop: `tLoop_java.xml` L28 of
  the same commit)
- The parallel option. "Select the Enable parallel execution check box and
  set the number of executions to be carried out in parallel." [QL-PARITER]
  Each pass becomes a thread handed a copy of globalMap; its `put` writes
  both the copy and the job's map (`super.put(key, value); return
  <job>.this.globalMap.put(key, value);`); a failing pass calls
  `talendThreadPool.setErrorThread(this); talendThreadPool.stopAllWorkers();`.
  [TL-ITER-HEAD L81-99, L168-175] [TL-ITER-FOOT L82-84] [TL-ITER-FOOT
  L125-126] Of its other parallel option, on database outputs, the help
  says "when parallel execution is enabled, it is not possible to use
  global variables to retrieve return values in a subJob" [QL-PARWRITE];
  whether it means the same of a parallel iterate link: unconfirmed.

| Talend component | What it puts in globalMap for each pass | What it leaves at the end | Source |
|---|---|---|---|
| tFileList | `<id>_CURRENT_FILE` (name), `<id>_CURRENT_FILEPATH` (absolute path), `<id>_CURRENT_FILEDIRECTORY` (parent), `<id>_CURRENT_FILEEXTENSION` (after the last "." of a file's name, else ""), `<id>_NB_FILE` (count so far) | `<id>_NB_FILE` (total) | [TL-FILELIST-BEGIN L415-435] [TL-FILELIST-END L19] |
| tFlowToIterate, default map | `<flow name>.<column>` for every column of the incoming flow, with the row's typed value; `<id>_CURRENT_ITERATION` | `<id>_NB_LINE` | [TL-F2I-MAIN L37-50, L65-68] [TL-F2I-END L12] |
| tFlowToIterate, own map | `<KEY>` = the row's `<VALUE>` column, for each line of the table; `<id>_CURRENT_ITERATION` | `<id>_NB_LINE` | [TL-F2I-MAIN L52-61] |
| tForeach | `<id>_CURRENT_VALUE`; each value is a Java expression, held as `Object` | nothing | [TL-FOREACH-BEGIN L24-37] [TL-FOREACH-XML L51-53] |

### 2.2 Many files, the same processing, one output (question 2)

| Engine (version) | Many files in one read | The file as a column | Files that differ | Order | One bad file | Files read before |
|---|---|---|---|---|---|---|
| Polars (1.44.2, installed) | `scan_csv`, `scan_ndjson`, `scan_lines` take a list of paths; `scan_csv` and `scan_lines` have `glob=True` by default; a folder is walked [PL-SIG] [PL-PATHS] | `include_file_paths`: "Include the path of the source file(s) as a column with this name." [PL-SIG] | "all files are read separately and concatenated" [PL-MULTI]; `scan_csv(missing_columns=)` "insert" or "raise" and `infer_schema_files` are both marked unstable [PL-SIG] | a list keeps its order; what one pattern or folder expands to is sorted by path (`sort_unstable`) [PL-PATHS L548-608] | `ignore_errors`: "Try to keep reading lines if some lines yield errors" - rows, not files [PL-SIG]; a file-level skip: none found | nothing |
| DuckDB (docs of v1.5.6) | "either the glob syntax, or by providing a list of files to read"; a list of patterns too [DK-MULTI] | `filename = true`, or a name for the column [DK-MULTI] | "By default, DuckDB reads the schema of the first file provided, and then unifies columns in subsequent files by column position"; `union_by_name` fills the gaps with NULL and "increases memory consumption" [DK-SCHEMA] | not stated | "the scanner will immediately stop the scanning process and throw the error"; `ignore_errors` skips rows; `store_rejects` keeps them in tables with `file_id`, `file_path`, `line` [DK-FAULTY] | nothing |
| Spark (4.2.0) | paths, patterns, folders; `pathGlobFilter`; `recursiveFileLookup` (default false); `modifiedBefore` and `modifiedAfter` [SP-GENERIC] | the hidden `_metadata` struct: `file_path`, `file_name`, `file_size`, `file_block_start`, `file_block_length`, `file_modification_time` [SP-FILEFORMAT L247-279] | not read | streaming file source: "Files will be processed in the order of file modification time" [SP-STREAM] | `ignoreCorruptFiles`: "the Spark jobs will continue to run when encountering corrupted files and the contents that have been read will still be returned"; `ignoreMissingFiles` for a file deleted after the listing [SP-GENERIC] | streaming: a checkpoint; `maxFileAge` (default 1 week); `cleanSource` `archive` or `delete`, "best effort" [SP-STREAM] |
| Databricks Auto Loader (page of 2026-09-11) | a folder, watched | `_metadata`, "a hidden column ... available for all input file formats" [DBX-META] | formats without types are read as strings; modes `addNewColumns` (fail, then go on with the new schema at restart), `rescue` (new columns go to a rescued-data column), `failOnNewColumns`, `none` ("the default when you provide a schema") [DBX-SCHEMA] | not read | by mode | "their metadata is persisted in a scalable key-value store (RocksDB) in the checkpoint location ... This key-value store ensures that data is processed exactly once." [DBX-AL] |
| Snowflake `COPY INTO` (page fetched 2026-10-12) | `PATTERN`: "A regular expression pattern string ... specifying the file names and/or paths to match"; `FILES`: at most 1000 names [SF-COPY] | `METADATA$FILENAME`, `METADATA$FILE_ROW_NUMBER`, `METADATA$FILE_CONTENT_KEY`, `METADATA$FILE_LAST_MODIFIED`, `METADATA$START_SCAN_TIME` [SF-META] [SF-COPY] | not read | not stated | `ON_ERROR`: `CONTINUE`, `SKIP_FILE`, `SKIP_FILE_num`, `'SKIP_FILE_num%'`, `ABORT_STATEMENT` (the default for bulk loads) [SF-COPY] | load metadata for each table (name, size, ETag, rows parsed, time of the last load, errors) that "expires after 64 days"; a loaded file is ignored unless `FORCE` [SF-LOAD] [SF-COPY] |

What the sources add:

- The case for one read. Polars: "To read multiple files into a single
  `DataFrame`, we can use globbing patterns" and "Polars will try to
  parallelize the reading"; and for files that need not be one table, "you
  can also build a query plan for each file and execute them in parallel on
  the Polars thread pool." [PL-MULTI] Dagster: "if you're using a
  parallel-processing engine like Spark and Snowflake, you often don't need
  Dagster to help with parallelism, so splitting up the backfill into
  multiple runs just adds extra overhead." [DG-BACKFILL]
- No match. DuckDB: "If a glob pattern does not match any files, the read
  functions raise an error", while its `glob()` function "returns an empty
  result instead of raising an error when nothing matches". [DK-MULTI]
- What Polars 1.44.2 does with a pattern, from its source (not run here).
  For each path given, in the order given: a folder is walked through all
  its subfolders, a pattern is expanded with the Rust `glob` crate, any
  other path is taken as it is; from a folder or a pattern only entries
  that are not folders and have `md.len() > 0` are kept, so a zero-length
  file is left out; each path's own expansion is then sorted. A single
  folder holding two file extensions is an error. [PL-PATHS L548-625]
  Entries are judged by `path.metadata()`, and Rust's `metadata` "will
  traverse symbolic links to query information about the destination
  file" [RUST-META], so links are followed (section 5, item 6).
  v2's readers pass `glob=False` today
  (`src/v2/components/file/file_input_delimited.py:277`, `:301`).
- Skipping a whole file costs memory or correctness. Snowflake: "The
  SKIP_FILE action buffers an entire file whether errors are found or not.
  For this reason, SKIP_FILE is slower than either CONTINUE or
  ABORT_STATEMENT." [SF-COPY] Spark's `ignoreCorruptFiles` returns the part
  of the bad file that was read (quoted in the table).
- A ledger is keyed by path, by path and size, or by content, and it ages.
  Auto Loader: "normally ingests each file only once based on its file
  path"; when a file is appended to or overwritten it "cannot guarantee
  which file version will be processed", and "Databricks recommends using
  Auto Loader to ingest immutable files only". [DBX-FAQ] Snowflake: a file
  is loaded again when it is modified and staged again, "which generates a
  new checksum"; the metadata "expires after 64 days" and a file whose
  status is then unknown is skipped unless `LOAD_UNCERTAIN_FILES`.
  [SF-COPY] [SF-LOAD] Camel: "Camel uses the absolute file name as the
  idempotent key", or an expression such as the name and the size; the
  default store is "a memory based LRUCache that holds 1000 entries".
  [CAMEL-FILE] [CAMEL-JSON]
- The way without a ledger is to move or delete what was read, and it is
  best effort everywhere. Spark `cleanSource`: "Both delete and move
  actions are best effort. Failing to delete or move files will not fail
  the streaming query." [SP-STREAM] Snowflake `PURGE`: "If the purge
  operation fails for any reason, no error is returned currently."
  [SF-COPY] Camel has `move`, `moveFailed` ("to move files into a .error
  subdirectory") and `delete`. [CAMEL-JSON]
- Exactly once needs the ledger and the output to change in one step. Auto
  Loader claims it "when writing data into Delta Lake". [DBX-AL] Spark's
  file sink is marked "Yes (exactly-once)" in its table of sinks. [SP-STREAM]
  Reasoning: with plain files the commit is a rename, so a ledger kept
  beside the data is at-least-once or at-most-once, depending on which of
  the two is written first.
- Parallel loads of the same file. Snowflake: "Snowflake sets a load status
  in the table metadata for the data files referenced in the statement.
  This prevents parallel COPY statements from loading the same files".
  [SF-LOAD]

### 2.3 Finding the files (question 3)

| Concern | What the sources show |
|---|---|
| Pattern or regular expression | Both are in use, and they are different languages. Python: shell-style wildcards "are not the same as regular expressions" [PY-FNMATCH]. Snowflake's `PATTERN` is a regular expression over names and paths [SF-COPY]; Hop's wildcards are regular expressions ("a RegEx with something like `.*\.dat$`") [HOP-GETFILES]; Camel has both: `include` and `exclude` are regular expressions, `antInclude` and `antExclude` are path patterns [CAMEL-JSON]. Talend has a switch, labelled "Use Glob Expressions as Filemask (Unchecked means Perl5 Regex Expressions)" in `tFileList_messages.properties`, default on [TL-FILELIST-XML L55-57]. |
| The pattern dialect | Talend turns a mask into a regular expression with Jakarta ORO (`GlobCompiler.globToPerl5(mask, DEFAULT_MASK)`) and matches the whole file name with `java.util.regex` (`matches()`), never the path [TL-FILELIST-BEGIN L202-204, L253-255]. ORO: `*` any run of characters, `?` one, `[...]` a class, negated when it starts with `!` or `^`, and a backslash "escapes" a special character [ORO-GLOB]. Python's `fnmatch` has `[!seq]` only and no escape ("For a literal match, wrap the meta-characters in brackets") [PY-FNMATCH]. Observed here: `fnmatch.translate('[^a]*.csv')` gives `(?s:[\^a].*\.csv)\z`, a literal `^`, and `fnmatch.translate('a\*b')` a literal backslash. v1 uses `fnmatch.translate` (`src/v1/engine/components/file/file_list.py:468-473`). |
| Case | Talend: "Case Sensitive" Yes or No, a flag on the compiled expression [TL-FILELIST-BEGIN L257-265]; in Java that flag alone folds ASCII only: "By default, case-insensitive matching assumes that only characters in the US-ASCII charset are being matched." [JAVA-PATTERN] Python: `fnmatch.fnmatch` case-normalises "using os.path.normcase()", which changes nothing on POSIX (observed here: `fnmatch('A.CSV', '*.csv')` is False); `Path.glob(case_sensitive=)` exists from 3.12 [PY-FNMATCH] [PY-PATHLIB312]. Camel's `include` is "case in-sensitive" always [CAMEL-JSON]. |
| Subfolders | Off by default in Talend (`INCLUDSUBDIR` false), Spark (`recursiveFileLookup` false) and Camel (`recursive` false; `maxDepth`, `minDepth`) [TL-FILELIST-XML L40-42] [SP-GENERIC] [CAMEL-JSON]. Talend matches the mask against the name at every depth, and in "Directories" mode goes down into every folder whether it matched or not [TL-FILELIST-BEGIN L306-343]. |
| Sort orders | Talend: "By default", by name, by size, by modified date, each up or down [TL-FILELIST-XML L65-86]. Spark's streaming source: by modification time, `latestFirst` to turn it round [SP-STREAM]. Camel: `sortBy` "Supports nested sorts, so you can have a sort by file name and as a 2nd group sort by modified date", or `shuffle` [CAMEL-JSON]. |
| A stable order | The system gives none. Python: `os.scandir` yields "in arbitrary order"; `glob` "results are returned in arbitrary order" and "Whether or not the results are sorted depends on the file system"; `Path.glob` (3.14 page): "The paths are returned in no particular order. If you need a specific order, sort the results." [PY-OS] [PY-GLOB] [PY-PATHLIB314] Java: "There is no guarantee that the name strings in the resulting array will appear in any specific order" [JAVA-FILE]. The C library's `glob()` sorts by locale: "in sort order as defined by the current setting of the LC_COLLATE category" [POSIX-GLOB]. Talend's "By default" is `java.util.Collections.sort(list)` over `java.io.File`, which "Compares two abstract pathnames lexicographically ... On UNIX systems, alphabetic case is significant" [TL-FILELIST-BEGIN L386-388] [JAVA-FILE]; "Order action" is not applied to it. Its help words it "alphabetical order, by folder then file" [QL-FILELIST73]: help and source differ, and the source is what runs. By name, Talend puts folders before files going up and compares names with `String.compareTo`; by size and by date a tie goes by name; two entries with the same name in different folders are left as listed [TL-FILELIST-BEGIN L29-199]. The help says that by name "in the event of identical file names then modified date takes precedence" [QL-FILELIST73]; the source does not do that. Dates are coarse: "some file systems use time stamps in units of seconds" [JAVA-FILE]. Observed here: Python's `sorted()` puts `B.csv`, `Z.csv`, `_x.csv` before `a10.csv`, `a2.csv`, `b.csv`. |
| Include and exclude | Talend: any number of masks, a name passes when one matches; "Use Exclude Filemask" then takes out names matching any mask of a list split on commas ("File types in this field should be quoted with double quotation marks and seperated by comma") [TL-FILELIST-BEGIN L246-250, L275-293] [QL-FILELIST73]. v1 takes the exclude text as one mask (`src/v1/engine/components/file/file_list.py:316-323`). Camel: "If both antInclude and antExclude are used, antExclude takes precedence" [CAMEL-JSON]. Hop: an inclusion and an exclusion expression for each folder [HOP-GETFILES]. |
| Files or folders | Talend: Files, Directories, Both; "Files" means anything that is not a folder (`!file.isDirectory()`), so a pipe or a broken link counts [TL-FILELIST-BEGIN L350-366]. Hop: "All files and folders", "Files only", "Folders only" [HOP-GETFILES]. Polars keeps what is not a folder and not empty [PL-PATHS]. |
| Hidden names | Python `glob`: "files beginning with a dot (.) can only be matched by patterns that also start with a dot, unlike fnmatch.fnmatch() or pathlib.Path.glob()" [PY-GLOB]. Spark's listing drops "everything that starts with _ and ." (two metadata names apart) and "everything that ends with `._COPYING_`, because this is a intermediate state of file" [SP-HIDDEN L345-357]. Polars' `scan_parquet` has `hidden_file_prefix` (unstable) [PL-SIG]. Talend has no such rule: `*` becomes `.*` and matches a dot name. |
| Files still being written | Finding 8, and the table below. |
| Links and loops | Python `os.walk`: "By default, walk() will not walk down into symbolic links that resolve to directories", and with `followlinks` "can lead to infinite recursion if a link points to a parent directory of itself. walk() does not keep track of the directories it visited already." [PY-OS] `glob`: "Broken symlinks are included in the results"; `**` matches "symbolic links to directories" [PY-GLOB]. `Path.glob` from 3.13 "follows symlinks except when expanding" the `**` wildcard, unless `recurse_symlinks` is set [PY-PATHLIB314]. Camel: "With `jailStartingDirectory` enabled (the default) ... The consumer skips a file, or with `recursive=true` a directory, that is a link resolving outside the starting directory (logged at WARN the first time)" [CAMEL-FILE]. Talend walks with `java.io.File` and follows whatever it meets; its only guard is a set of absolute paths, which a loop of links never repeats (inferred) [TL-FILELIST-BEGIN L300-343]. |
| Errors while listing | `Path.glob`: "Any OSError exceptions raised from scanning the filesystem are suppressed. This includes PermissionError when accessing directories without read permission." (3.14 page; 3.12: "Subsequent OSError exceptions from scanning directories are suppressed.") [PY-PATHLIB314] [PY-PATHLIB312] A folder that cannot be read then looks empty. Talend: a folder that is not there gives no pass and no error (the `null` that `listFiles` returns is never looked at) unless "Generate Error if no file found" is ticked [TL-FILELIST-BEGIN L308, L346] [TL-FILELIST-END L25-27]. Camel has `startingDirectoryMustExist` [CAMEL-JSON]. |
| Very large folders | Python: "Using scandir() instead of listdir() can significantly increase the performance of code that also needs file type or file attribute information", but `os.DirEntry.stat()` "always requires a system call on Unix", which sorting by size or date needs for every entry [PY-OS]; the `**` pattern "in large directory trees may consume an inordinate amount of time" [PY-GLOB]. Camel: with `maxMessagesPerPoll` "the File and FTP components will limit before any sorting. For example if you have 100000 files and use maxMessagesPerPoll=500, then only the first 500 files will be picked up, and then sorted"; to sort first costs "higher memory usage as all file details are in memory" [CAMEL-JSON]. Snowflake: "try to avoid applying patterns that filter on a large number of files" [SF-COPY]. Auto Loader: "You can use Auto Loader to process billions of files to migrate or backfill a table." [DBX-AL] |
| The list is a snapshot | Talend builds the whole list, then loops [TL-FILELIST-BEGIN L300-411]. Python: "If a file is removed from or added to the directory after creating the iterator, whether an entry for that file be included is unspecified." [PY-OS] Spark's `ignoreMissingFiles` is for "the deleted file under directory after you construct the `DataFrame`" [SP-GENERIC]. |

Telling a finished file from one being written:

| Way | Who | What the source says |
|---|---|---|
| The writer moves the finished file in | Spark, Camel, Hop | finding 8 |
| The writer uses a temporary name, then renames | Camel `tempPrefix` ("write the file using a temporary name and then, after the write is complete, rename it to the real name"); rsync (a temporary file "in the same directory as the associated destination file"; that its name starts with a dot and ends in a random suffix is inferred from what the page says of `--temp-dir`, where names "will not be prefixed with an extra dot, though they will still have a random suffix added"); v2 itself (`.<name>.<component>.v2tmp<pid>`, `src/v2/engine/runner.py:980-988`) | [CAMEL-JSON] [RSYNC] |
| The reader leaves out such names | Spark (names starting `_` or `.`, ending `._COPYING_`); Python `glob` (dot names) | [SP-HIDDEN] [PY-GLOB] |
| A marker file says "done" | Camel `doneFileName`: "Camel will only consume files if a done file exists" | [CAMEL-JSON] |
| Size and time unchanged over an interval | Camel `readLock=changed` ("Will at least use 1 sec to determine this"; `readLockCheckInterval` 1000 ms, "may be too fast if the producer is very slow writing the file"; after `readLockTimeout` the file is skipped until the next poll); Hop "File size check" ("will only continue if the file size hasn't changed the last check"); Talend tWaitForFile "Wait for file to be released" (off Windows: the modified time read twice, `INTERVAL_CHECK` ms apart, default 500) | [CAMEL-JSON] [HOP-WAITFILE] [TL-WAITFILE-BEGIN L305-311] [TL-WAITFILE-XML L130-131] |
| A minimum age | Camel `readLockMinAge` ("to require the file is at last 5 minutes old"); Spark `modifiedBefore` | [CAMEL-JSON] [SP-GENERIC] |
| Probing for a lock | Camel `fileLock` and `rename`; Hop "tries to determine if a file is locked by another process by trying to move the file to itself"; Talend on Windows renames and renames back | [CAMEL-JSON] [HOP-LOCKED] [TL-WAITFILE-BEGIN L296-303] |

Camel's warning stands over the last three: "the JDK File IO API is a bit
limited in detecting whether another application is currently
writing/copying a file. And the implementation can be different depending on
the OS platform as well." [CAMEL-FILE]

### 2.4 Child pipelines (question 4)

| Tool | Parameters in | Values out | A failed child | Where it runs | Cycles | Seen as | Stopping it |
|---|---|---|---|---|---|---|---|
| Airflow `TriggerDagRunOperator` (3.3.2) | `conf`; the Dag's id may be a template [AF-TRIG] | none in the operator's parameters | only with `wait_for_completion` (default False): `failed_states` (default failed) fail the task, `allowed_states` (default success) let it pass [AF-TRIG] | a Dag run of its own | not stated | a run of its own, linked from the task | not stated |
| Airflow TaskGroup (in place of SubDAG) | none: the tasks are the parent's own | the tasks' own | as any task | "Tasks in TaskGroups live on the same original DAG, and honor all the DAG settings and pool configurations" [AF-2.10] | not applicable | one Dag | with the Dag |
| Dagster nested graph (1.13.26) | sub-graph inputs; config "under a key with the name of that sub-graph" [DG-NEST] | sub-graph outputs | as any op | the same run; "Dagster supports arbitrary levels of nesting" [DG-NEST] | not applicable (a definition, not a call) | one job | with the run |
| Prefect nested flow (3.8.8) | arguments | the return value | the exception reaches the parent | the parent's process; "Nested flow runs block execution of the parent flow run until completion"; a task runner of its own [PF-FLOW] | not stated | "a full representation of the nested flow run in the backend as if it had been called separately", joined to the parent by a task run [PF-FLOW] | "A nested flow run cannot be cancelled without cancelling its parent flow run." [PF-FLOW] |
| Prefect `run_deployment` | `parameters`; `job_variables` [PF-DEPLOY] | the flow run object | the caller looks at its state | infrastructure of its own; `timeout=0` "returns immediately" [PF-DEPLOY] | not stated | "treated as a subflow of the parent flow in the UI" unless `as_subflow=False` [PF-DEPLOY] | on its own; a signal, then after "a grace period (default of 30 seconds), the infrastructure is killed" [PF-CANCEL] |
| Kestra Subflow (2.0.5) | `inputs`; the called flow declares each with a type (as in the example flows of [KE1-ITEM] and [KE2-LOOP]) [KE2-SUB] | the called flow's declared outputs, with `executionId` and `state` [KE2-SUB] | `transmitFailed` (default true), only with `wait` (default true) [KE2-SUB] | "Starts a separate execution" [KE2-SUB] | "Recursive flows are not supported. A flow cannot call itself directly or indirectly - any cycle makes the flow invalid" [KE-SUBDOC] | an execution of its own; `inheritLabels` | not stated; "If the parent restarts, previously started subflows are restarted too" [KE2-SUB] |
| Azure Data Factory Execute Pipeline (2026-08-04) | `parameters` [ADF-EXEC] | "pipeline return value, a dictionary of key value pairs", at most 4 MB, read as `@activity('Execute Pipeline1').output.pipelineReturnValue.keyName`; "The Pipeline will fail if the key referenced is missing" [ADF-RETURN] | not stated on the page | a pipeline run of its own; `waitOnCompletion` (default true) [ADF-EXEC] | not stated | a run of its own | not stated |
| Hop Pipeline Executor, Pipeline action (2.19.0-rc1) | parameters and variables, "downstream only"; "Parameters do not automatically flow through a Repeat Action" [HOP-PEXEC] [HOP-REPEAT] | result rows ("Copy rows to result"), result file names [HOP-PEXEC] | fields of the result row [HOP-PEXEC] | by the run configuration | not stated | a log file for each repeat, if asked [HOP-REPEAT] | not stated |
| Talend tRunJob | the whole context and a table of name and value [TL-RUNJOB-MAIN L435-559] | `<id>_CHILD_RETURN_CODE`, `<id>_CHILD_EXCEPTION_STACKTRACE`; rows of a tBufferOutput [TL-RUNJOB-MAIN L605-612, L646-702] | "Die on child error", default on [TL-RUNJOB-XML L83-85] | the parent's process, unless "Use an independent process to run subjob" [TL-RUNJOB-MAIN L567-598, L703-813] | none in the templates | the child's own log lines | with the parent; an independent process is destroyed on `ThreadDeath` [TL-RUNJOB-MAIN L793-800] |

Why Airflow removed SubDAGs. Airflow 2.10: "SubDAG is deprecated hence
TaskGroup is always the preferred choice", because "The SubDagOperator
starts a BackfillJob, which ignores existing parallelism configurations
potentially oversubscribing the worker environment", "SubDAGs have their own
DAG attributes. When the SubDAG DAG attributes are inconsistent with its
parent DAG, unexpected behavior can occur", "Unable to see the "full" DAG in
one view", and "SubDAGs introduces all sorts of edge cases and caveats".
[AF-2.10] Airflow 3.0 lists "SubDAGs" among removed features, replaced by
"Task Groups". [AF-3.0] Reasoning: what was removed is a child with a
scheduler and settings of its own inside the parent; what stayed is either
the parent's own tasks under a name (TaskGroup) or a wholly separate run
(TriggerDagRunOperator). Nothing in between.

Checking the whole tree before anything runs. Kestra makes a cycle "invalid"
(quoted above). Hop warns that a child named by a field of the data "will be
initialized at runtime and not during the initialization phase as usual".
[HOP-PEXEC] Talend's generated code names the child's class (`<childJob>
childJob_<cid> = new <childJob>();`), so a child that is not there fails the
build, not the run; a "dynamic job" may only be one of a list fixed at
design time ("The child job named ... is not in the job list"). [TL-RUNJOB-MAIN
L135-141, L569]

Talend's tRunJob in full:

- In the parent's process: `childJob.runJob(args)` is a call; the return
  code is the child's error code, else 1 when its status is "failure", else
  0; with "Die on child error" a failure throws `RuntimeException("Child
  job running failed.\n" + ...)`, which fails the parent's subjob like any
  component. [TL-RUNJOB-MAIN L598-630]
- Parameters. "Transmit whole context" adds every variable of the parent as
  `--context_param <name>=<value>`; then each line of the table adds one,
  the value being a Java expression; the typed values travel beside the
  text in `parentContextMap` when "Transmit original context" is on (the
  default). [TL-RUNJOB-MAIN L435-518, L521-559, L592-594] "The values
  defined here will be used during the child Job execution even if Transmit
  whole context is selected." [QL-RUNJOB]
- Nothing comes back but the return code, the stack trace and, with
  "Propagate the child result to the output schema", the rows the child put
  in a tBufferOutput, which arrive as a `String[][]` held in memory.
  [TL-RUNJOB-MAIN L598, L646-676]
- Of "Use an independent process to run subJob" the help says: "This helps
  in solving issues related to memory limits." [QL-RUNJOB] The child is
  then a command (`Runtime.exec`), its output is copied to the parent's,
  its exit code is the return code, and "when tRunJob runs in an
  independent process, it can't extract datas from tBufferOutput of child
  job". [TL-RUNJOB-MAIN L776-813, L831]
- Of "Use dynamic job": "An independent process will be used to run the
  subJob." [QL-RUNJOB] [TL-RUNJOB-MAIN L135-136]
- The help now limits it: "The tRunJob component is supported with
  limitations ... it is recommended to change your Job Design to use
  Joblets instead", said of services and routes; "For DI and non-ESB use
  cases, it is still a valuable component and has support." [QL-RUNJOB]
- In a loop with the parallel option the context is copied for each thread
  ("copy context to local for mutilthread"). [TL-ITER-HEAD L180-193]

### 2.5 Set-up and clean-up (question 5)

| Tool | The construct | When clean-up runs | When clean-up fails | When set-up fails | What clean-up can see |
|---|---|---|---|---|---|
| Airflow (3.3.2) | setup and teardown tasks | "A teardown task will run if its setup was successful, even if its work tasks failed. But it will skip if the setup was skipped."; also when the run is set to failed or success by hand, "to ensure resources will be cleaned-up" [AF-SETUP] | "By default, teardown tasks are ignored for the purpose of evaluating Dag run state."; `on_failure_fail_dagrun=True` makes it count [AF-SETUP] | "If a setup fails or is skipped, the work tasks which depend them will be marked ask failures or skips." (as written); "If all of a teardown's setups were skipped or failed, those states will propagate to the teardown." [AF-SETUP] | not stated |
| dbt (docs of 2026-10-09) | `on-run-start` and `on-run-end` for a run; `pre-hook` and `post-hook` for a model | `on-run-end` runs at the end of build, compile, docs generate, run, seed, snapshot or test; the page's own example shows it running after a model ended in ERROR [DBT-RUN] [DBT-END] | not stated | not stated | "The `results` variable contains a list of Result objects with one element per resource that executed" [DBT-END] |
| Kestra | `errors`; `finally` (from 0.21.0); `afterExecution` (from 0.22.0) | `finally`: "tasks that always run at the end of a flow - whether the execution succeeds, fails, or is killed" [KE-FINALLY] | `afterExecution`: "Errors inside an `afterExecution` block do not change the final execution state." [KE-AFTER]; `finally`: not stated | not applicable | `finally` "cannot see the terminal state" (the execution is still RUNNING); `afterExecution` "sees `SUCCESS`, `FAILED`, or `WARNING`" [KE-AFTER] |
| Dagster (1.13.26) | a resource's `setup_for_execution` and `teardown_after_execution`, or a context manager; op hooks | "Once a resource is no longer needed"; "once per run, per process"; after a failed op: not stated [DG-RES] | not stated | not stated | hooks are for one op's success or failure: "The hook does not track job-scoped events" [DG-HOOK] |
| Argo (4.1.5) | an exit handler | "a template that *always* executes, irrespective of success or failure, at the end of the workflow" [ARGO-EXIT] | not read | not applicable | not read |
| Talend | tPrejob and tPostjob | after the main part whatever happened in it; see below | the postjob's subjob fails like any other (inferred) | the main part runs all the same; see below | globalMap; `<start>_SUBPROCESS_STATE` is -1 for a subjob that failed [TL-FOOTER-SKEL L38] |
| v1 | Prejob and Postjob markers | only when no component failed and no die ended the job (`src/v1/engine/executor.py:235-243`) | - | the main part still runs (no gate found in `executor.py:222-270`) | - |

dbt's hooks for one model: "`pre-hook`: executed _before_ a model, seed or
snapshot is built." and "`post-hook`: executed _after_ a model, seed or
snapshot is built." [DBT-RUN] Where the database has transactions, "by
default hooks are executed inside of the same transaction as your model
being created", and `before_begin` and `after_commit` take one outside, for
instance for an audit record at the start of a run that you "do not want
... rolled back if the model creation fails". Order: hooks of
packages first, then those of `dbt_project.yml`, then the model's own,
each group in the order written. [DBT-HOOK] Whether a post-hook runs after
its model failed: not stated.

Talend's tPrejob and tPostjob, exactly, from the template that generates a
job's main method:

1. The order is fixed in the generator: the implicit context load, then
   every tPrejob, then every other start component, then every tPostjob.
   [TL-FOOTER L1093-1111, L1156-1257, L1260-1270]
2. Each of those calls is wrapped alike: `try { errorCode = null;
   <start>Process(globalMap); if(!"failure".equals(status)) { status =
   "end"; } } catch (TalendException e_<start>) {
   globalMap.put("<start>_SUBPROCESS_STATE", -1);
   e_<start>.printStackTrace(); }` (line breaks left out). [TL-FOOTER-SKEL
   L5-40] So the postjob call is reached whatever the main part did, and
   so is the main part whatever the prejob did.
3. After tDie: tDie sets the status and the error code and throws
   (`throw e_<cid>;` of a `TDieException`), unless "Exit the JVM
   immediately" is ticked (default off), in which case it calls
   `System.exit(<code>)` and nothing more runs. [TL-DIE-MAIN L50-63,
   L75-112] The thrown exception is caught by its subjob, wrapped and
   thrown on, and caught again by the wrapper of point 2. [TL-SUBFOOTER
   L221-254] So after a tDie without that tick: what was chained behind the
   dying subjob does not run (the chain is nested calls, [TL-SUBFOOTER
   L211]); the error triggers of that subjob do (`<component>_error` is
   called for a `TDieException` too, [TL-HEADER L696-703, L862-889, L949]);
   the other start components of the main part do; and tPostjob does.
   (Read from the templates, not run.)
4. Not reached: after `System.exit`, and after a `java.lang.Error` in the
   single-thread form, whose wrapper catches `TalendException` only
   (inferred from [TL-FOOTER-SKEL L30-55]).
5. Both components have no setting and one way out, "On Component Ok"
   (`CTYPE="COMPONENT_OK" MAX_OUTPUT="1" MAX_INPUT="0"`); the header says
   `SINGLETON="true"` (its meaning: unconfirmed). [TL-PREJOB-XML L4-21]
   [TL-POSTJOB-XML L4-21]
6. The help agrees and adds one limit: "A key feature of these components
   is that they are always guaranteed to be executed, even if the main data
   Job fails. Therefore, they are very useful for setup and teardown
   actions for a given Job."; "they cannot be part of a multi-thread
   execution"; a post-job is for "Any task required to be executed, even if
   the preceding Job or subJobs failed." [QL-PREPOST]

### 2.6 Waiting (question 6)

Why a fixed sleep is discouraged, in the sources' words:

- It holds a place while doing nothing. Airflow: "Standard Operators and
  Sensors take up a full *worker slot* for the entire time they are
  running, even if they are idle. For example, if you only have 100 worker
  slots available to run tasks, and you have 100 Dags waiting on a sensor
  that's currently running but idle, then you *cannot run anything else*".
  [AF-DEFER]
- Its length is a guess. Playwright marks its wait for a set time
  "Discouraged": "Never wait for timeout in production. Tests that wait for
  time are inherently flaky." and "Use signals such as network events,
  selectors becoming visible and others instead." [PW] (a testing tool; the
  reason carries over). Camel says of its own one-second default that it "may be
  too fast if the producer is very slow writing the file"; Hop that "A
  check cycle time of 30 or 60 seconds seems to be a good trade-off".
  [CAMEL-JSON] [HOP-WAITFILE]
- Equal waits come back together. Amazon: "If all the failed calls back off
  to the same time, they cause contention or overload again when they are
  retried. Our solution is jitter." [AWS-BL] Google: "Always use randomized
  exponential backoff when scheduling retries." [SRE] Prefect: "Adding
  jitter to the retry delays avoids multiple tasks introducing load to
  external systems by failing and retrying at the exact same cadence."
  [PF-RETRY]

What replaces it:

| In place of a sleep | Who | What it has |
|---|---|---|
| A wait for a condition, with an interval and an end | Airflow sensors: "all they do is wait until something happens, and then *succeed* ... Or, in the case when that thing does _not_ happen within the configured timeout, *fails*" | `poke_interval`; `timeout` ("measured from the first execution attempt, not per poke"); `soft_fail` (skipped, not failed, at the timeout); `exponential_backoff` with `max_wait` [AF-SENSOR] |
| The same, in ETL tools | Hop "Wait for file" ("can either wait indefinitely for the file or it can time out after a certain time"; "Success on timeout"; "File size check"); Talend tWaitForFile (`WAIT` seconds between looks, "Max. number of iterations (infinite loop if empty)", "Wait for file to be released"; the labels are from `tWaitForFile_messages.properties`) | [HOP-WAITFILE] [TL-WAITFILE-XML L35-40] |
| A wait that holds nothing | Airflow deferrable operators: "an operator can suspend itself and free up the worker ... by *deferring*"; sensors in `reschedule` mode | [AF-DEFER] [AF-SENSOR] |
| A retry with growing, capped, scattered waits | Airflow `retry_exponential_backoff`, `max_retry_delay`; Dagster `Backoff` and `Jitter`; Prefect `exponential_backoff` and `retry_jitter_factor`; Argo `backoff` with `factor` and `maxDuration` | [AF-OP] [DG-RETRY] [PF-RETRY] [ARGO-RETRY] |

Amazon on the cap: "To avoid retrying for too long, implementations
typically cap their backoff to a maximum value." And on what a retry may
repeat: "A timeout or failure doesn't necessarily mean that side effects
haven't happened." [AWS-BL]

The plain sleep steps that exist all the same:

| Tool | Step | The value | Notes |
|---|---|---|---|
| Talend | tSleep | `PAUSE`, "1" by default, a Java expression in seconds | generated as `Thread.sleep((<pause>)*1000);` in the component's main part: in a flow it sleeps for every row; it also takes an iterate link [TL-SLEEP-MAIN L12-14] [TL-SLEEP-XML L27-40] |
| Kestra (2.0.5) | Sleep | an ISO-8601 duration, at least 1 ms ("must be a positive duration") | "Useful for backoff, pacing, or demo timing." [KE2-SLEEP] |
| Kestra | Pause | `pauseDuration`, or until resumed by hand | "If no pauseDuration and no timeout are configured, the execution will never end until it's manually resumed" [KE2-PAUSE] |
| Step Functions | Wait | "either a relative time, specified in seconds from when the state begins, or an absolute end time, specified as a timestamp"; `Seconds` from 0 to 99,999,999; "exactly one of" four fields | at most one year in a Standard workflow [SFN-WAIT] |
| Azure Data Factory | Wait | `waitTimeInSeconds` | [ADF-WAIT] |
| Hop | Repeat's "Delay in seconds" between repeats | seconds | [HOP-REPEAT] |
| Airflow | `TimeDeltaSensor`: "Wait for a specified time duration" | a sensor, so with the modes above | [AF-SENSOR] |

What a plain sleep should still offer. Reasoning, each point from a source
above: a value that is checked (Kestra refuses what is not positive; Step
Functions bounds it); a way to wait until a time of day as well as for a
length of time (Step Functions); an end that an operator can bring about
(Kestra's resume; in Python, "If the sleep is interrupted by a signal and no
exception is raised by the signal handler, the sleep is restarted with a
recomputed timeout", so it ends early only when the handler raises, as the
default handler for Ctrl-C does [PY-TIME] [PY-SIGNAL]); a line in the log at
both ends; and no pretence of being a wait for something. A length of time
is measured on a clock that "cannot go backwards" and "is not affected by
system clock updates" (`time.monotonic`), and "may be longer than requested
by an arbitrary amount". [PY-TIME]

## 3. What follows for v2 (question 7)

Everything in this section is reasoning from section 2 and from v2's code,
except where a source is named.

### 3.1 What bounds the options: v2 as it stands (commit `c350cd5d`)

- A subjob is the components joined by flows (`src/v2/job/graph.py:36-57`).
  `Runner._run_subjob` builds and runs one (`src/v2/engine/runner.py:382-434`),
  making new component instances and resolving their config strings each
  time it is called (`runner.py:711-728`; `docs/v2/how-a-job-runs.md`:
  "Context values in config strings ... are resolved when each component is
  built"). Running a subjob again with other values is therefore what the
  code already does; it does so today for the read-again
  (`runner.py:419-430`).
- The runner lets each subjob run once: `if index in done: continue`
  (`runner.py:253-255`).
- Config strings resolve context references only
  (`src/v2/engine/context.py:103-120`). A value that names `globalMap` is
  passed through unjudged at load (`src/v2/job/keys.py:27`, `:190-193`) and
  is never resolved at run. Several places read a globalMap reference with
  a pattern of their own (`engine/conditions.py:27-28`,
  `components/control/die.py:19`, `components/file/fixed_flow_input.py:20`
  among them); `die.py`'s takes a key of word characters only, so not
  `row1.filepath`.
- Files are put in place at the end of each run of a subjob, `append`
  included (`runner.py:838-879`). A sink's rows add up over runs, and
  `<id>_NB_LINE` is set to the sum (`runner.py:869-870`).
- Failures are kept by component id, the first reason only
  (`runner.py:370-376`).
- A die ends the job at once: "No trigger fires and no subjob follows"
  (`runner.py:259-263`).
- Ctrl-C unwinds and removes temporary files (`runner.py:456-459`). No
  handler for SIGTERM was found in `src/v2` (section 5, item 14).
- Temporary files are named `.<name>.<component>.v2tmp<pid>` beside their
  target (`runner.py:980-988`; by `be2ee9da` the same code is `temp_beside`
  in `src/v2/files.py`).
- The check at load builds every subjob on empty frames and lets pass a
  globalMap entry that is not there yet (`src/v2/engine/check.py:87-95`).
- An `Action` takes and hands on no rows and is a subjob of its own; an
  `Eager` component holds its input rows in memory
  (`src/v2/components/base.py:632-672`).

### 3.2 Reading the item: the first thing to build

A body reads its item in config strings. Three shapes are in converted job
configs (section 4.3):

1. `{{java}}((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`: what
   the converter writes today for a reader's or a delimited output's path.
2. The same without the mark: older conversions, and every key a converter
   does not mark (file copy, file delete, run job's parameters...).
3. Either of them joined to text: `context.outDir + "/" +
   ((String)globalMap.get("tFileList_1_CURRENT_FILE"))`. Not in the
   samples; the usual Talend way to name an output after its input
   (unconfirmed for the 1200 jobs: section 5, item 16).

| Option | What it is | For | Against |
|---|---|---|---|
| R1 | Leave `{{java}}` refused; a job is edited by hand to `${globalMap.key}` or the like | nothing new to read | no converted loop job loads: the one rule of ticket 87 that binds |
| R2 | One reader in the engine for an "item reference": an optional `{{java}}` mark, then nothing but `((Type)globalMap.get("k"))`, `(Type)globalMap.get("k")`, `globalMap.get("k")`, `context.x`, and text in double quotes, joined by `+`. A lone reference gives the entry's own value; a join gives text. Anything else under `{{java}}` stays refused, as now | converted jobs load; no Java is run, it is a lookup and a join; `conditions.py` already reads the same shapes for a RunIf; v1 has the lone form for run job's parameters (`src/v1/engine/components/control/run_job.py:22-26`) | a small language to own; where `resolve` replaces a bare `context.x` "wherever they stand" today, a value with `+` in it would start to mean a join |
| R3 | R2, and also Java string methods (`.substring`, `.replace`...) | more jobs load | that is running Java expressions, which v2 does not |

Recommendation: R2, in `RunContext.resolve`, for every config string of
every component, judged at load where it can be (the shape) and at run
where it must be (the entry). It is the one place; the private patterns of
3.1 can then go. Limit it to values that hold `globalMap` or the
`{{java}}` mark, so that no value that loads today changes its meaning.

### 3.3 Running the body once for each item: the options

| Option | What it is | For | Against |
|---|---|---|---|
| A. A pass is a run of the body | The iterate link is not a flow: the loader keeps it apart, so the looping component and the body fall into different subjobs. When the looping component's subjob has finished, the runner takes its items one at a time, puts the item's entries in globalMap and runs the body (its subjob and what that sets off) as it runs any subjob. Files of a pass are put in place at the end of the pass | converted jobs mean what they meant; any component can be in a body (a reader, an action, a run job, another loop); a pass has an identity, a status and files of its own, as in every tool of 2.1; little new machinery: a subjob run is already repeatable (3.1) | a plan, a pass over the data and a placing of files for each item: a fixed cost for each pass (not measured: section 5, item 9); "one output from many files" needs `append`, so a failure at file k leaves the first k-1 files' rows in the output; what a pass leaves in globalMap is seen by the next |
| B. A, with files put in place only when the loop ends | every pass writes beside its target; all are placed at the end | the loop is all or nothing | a body that acts on what it wrote (copy, archive or delete after writing) breaks, and an action already done cannot be undone; N temporary files held; no meaning for "go on after a failed item" |
| C. The engine joins the passes into one plan | when the body is nothing but source, transforms and sinks, build it once for each item without running it, put the items' frames one after another for each sink, run one pass | one pass, all or nothing, Polars works on several files at once | two ways to run one job config, which must never differ; a plan that grows with the items; "which item failed" and the meaning of globalMap after the loop to be invented; safe for a narrow shape only |
| D. One read of many files, asked for | a reader is given several files (v2's own keys) and reads them as one; no loop in the job | one unit, one pass, plain meaning; what every engine in 2.2 does | a converted job does not use it until someone edits it |

Recommendation: A, and D beside it as the reader's own ability (3.7), both
on the same code for finding files. Not B, not C. A is what makes a
converted job load and mean something; D is the sound form of the common
case; C buys speed with a second code path for the same config, the kind of
thing this engine exists to be rid of. If item 9 of section 5 shows that a
pass costs enough to matter for jobs that exist, the answer is to offer D
for them, not to build C.

### 3.4 The rules of a loop under option A

| Matter | Recommendation | Grounds |
|---|---|---|
| The unit | A pass: its files are whole and in place, or none of that pass's are. The loop is not a unit | 2.1: every tool; v2's own rule for a subjob |
| Order | The component's order, one pass at a time | finding 3; "the same input gives the same output" (ticket 87) |
| `enable_parallel`, `number_parallel` | Accepted and without effect; one INFO line says the passes run in order | Polars already uses every core inside a pass (Dagster's sentence in 2.2); Talend's own parallel passes share globalMap; `RunContext` is one run's state (`context.py:17-62`) |
| A failed pass | Stop: no later pass runs, the looping component has failed, with the item named; its subjob's error triggers fire as for any failure. A second policy, "go on", may be offered as v2's own key: every item is tried and the component fails at the end when any failed, listing them | sequential loops stop in Talend, Step Functions inline and Argo; "go on" is asked for where it exists (Prefect, `failFast: false`, tolerated counts) |
| A die in a body | Ends the job, as today | `runner.py:259-263` |
| No item | No pass; one INFO line; the count entry is 0; the component's own triggers fire. With `error` on: fail with Talend's words, "No file found in directory <dir>" | [TL-FILELIST-END L25-27]; Airflow marks it skipped, not failed |
| The item's entries | Put before each pass, all of them, a missing value as None (never the last pass's value); left as they are after the loop, as Talend leaves them | [TL-FILELIST-BEGIN L431-435] |
| Row counts of a body's components | In globalMap: this pass's (Talend's meaning, and what a RunIf inside the body needs). In the summary: the sum, as now | today the entry is the sum over runs (`runner.py:869-870`); to be decided |
| What says what happened | Log: one INFO line at the start of a pass (`[tFileList_1] item 3 of 12: /data/in/b.csv`) and one at the end of the loop (items, ok, failed, seconds). Summary: for each loop its counts, and the failed items with their reasons, up to a fixed number. globalMap: `<id>_NB_FILE` or `<id>_NB_LINE`, and `<id>_ERROR_MESSAGE` | "it says what it did" (ticket 87); Step Functions and Kestra give counts for each state and put the detail in a file |
| Loops inside loops | Allowed: a body that holds a looping component runs it as any other | Talend, Kestra and Argo nest; the entries are keyed by component id, so nothing collides |
| A cap | `max_items`, v2's own key: more items than that fails the job before the first pass and says how many there were. A generous default (Azure Data Factory's 100,000 is one precedent, Airflow's 1024 another) | finding 5; a wrong folder with subfolders on |
| What is checked at load | A component is the target of one iterate link at most; a trigger does not lead into a body from outside it; a body's triggers do not lead back to its loop. Each refused with its reason | [QL-ITER]; v2 refuses loops of flows and of triggers today (`loader.py:310-314`, `:537-568`) |
| `--only` and `--trace` | By a column's value: applied in every pass. By a place (a line): refused for a reader inside a body until a way to name the file exists | `runner.py:642-709`; not designed here |

### 3.5 File list

| Matter | Talend (source) | v1 | Recommended for v2 | Why |
|---|---|---|---|---|
| Masks, pattern form | ORO: `*`, `?`, `[...]` negated by `!` or `^`, backslash escapes; the whole name must match | `fnmatch.translate` | a translator of its own with ORO's four rules | a converted mask keeps its meaning (`[^0-9]*` is one that changes under `fnmatch`); a page of code |
| Masks, regular-expression form | `java.util.regex` | Python `re` | Python `re.fullmatch`; a mask `re` cannot compile refuses the job at load and says where | observed here: `re` refuses `\p{Alpha}`, `\Q..\E`, `(?<n>..)` and a flag in mid-pattern, and compiles `[a-z&&[^aeiou]]` to mean something else (with a FutureWarning) |
| No mask | every name | every name | every name | same |
| Exclude | a list split on commas | one mask | a list split on commas | [TL-FILELIST-BEGIN L278] |
| Case | a flag; ASCII only in Java | `re.IGNORECASE` | `re.IGNORECASE`; say that names beyond ASCII fold too | simple; rare |
| Subfolders | every depth; follows links | `rglob("*")` | a walk with `os.scandir` that does not go down into a link to a folder | no loop of links can form; "nothing is read ... through a link out of the folder named" (ticket 87); errors are not swallowed as `Path.glob` swallows them |
| A link to a file | followed | followed | listed when it leads to a file inside the folder named; otherwise left out with a WARNING | Camel's default (`jailStartingDirectory`) |
| "Files" | anything that is not a folder | `is_file()` | regular files | a pipe would hang a reader |
| Dot names | matched if the mask matches | same | left out unless the mask itself starts with a dot; v2's own temporary names left out always | the shell's rule and Python's; rsync's and v2's unfinished files are dot names; Spark does the same |
| "By default" order | sorted by path | the file system's order | sorted by path, by code point | Talend's own behaviour on UNIX, and the only order that is the same twice |
| By name, size, date | folders first going up; ties by name, then as listed | by the one key, folders and files alike; ties as listed | as Talend, and a last tie by path | the same list twice |
| Down with "By default" | not applied | not applied | not applied | Talend |
| A folder that is not there | no pass, no word | no pass, a warning | fail; so does a folder that cannot be read | a mount that is missing must not look like a quiet day |
| No name matches | no pass; `error` makes it fail | same | same | Talend's own switch |
| When the list is made | once, before the first pass | once | once; a file gone by its pass fails that pass | a snapshot is what can be reasoned about |
| A file still arriving | nothing | nothing | `min_age_seconds`, v2's own key, default 0: a file modified less than that long ago is left out, counted and said | Camel `readLockMinAge`, Spark `modifiedBefore`; it waits for nothing |
| The directory, when relative | from the working folder | resolved | from the folder the job was started in, as every v2 path | `docs/v2/running-a-job.md` |
| `format_filepath_to_slash` | backslash to slash | same | accepted, no effect | on Linux a backslash is a character of a name |
| Entries for a pass | five (2.1) | those, `<id>_CURRENT_ITERATION`, counts | Talend's five, and v1's `<id>_CURRENT_ITERATION` | both kinds of job config exist |

### 3.6 Flow to iterate and foreach

Flow to iterate is the one loop whose list is data, so it is the one that
can be as long as a file. Talend runs the body while the row is being read
[TL-F2I-MAIN]; v1 takes every row into memory first
(`src/v1/engine/components/iterate/flow_to_iterate.py:148`).

| Option | What it is | For | Against |
|---|---|---|---|
| F1 | An `Eager` component: the rows in hand, a pass for each | least code | memory grows with the rows: against ticket 87's first rule |
| F2 | A sink: the engine writes its input to a scratch file in the subjob's one pass; the passes are then fed from that file a batch at a time | memory is one batch whatever the length; the subjob that fed it is finished, its files in place, before the first pass | a scratch file; a reader for it |
| F3 | F2 with the cap of 3.4 | a loop of a million passes is stopped with a reason before it starts | a number to choose |

Recommendation: F3. Kestra and Step Functions feed long lists from a file in
batches (finding 5); and a loop over every row of a large table is, in an
engine that joins, a join written as a loop, which the refusal can say.

- Entries, as Talend: with `default_map`, `<flow name>.<column>` for every
  column of the incoming flow; otherwise `key` and `value` of each line of
  `map_entries`; `<id>_CURRENT_ITERATION`, from 1; `<id>_NB_LINE` at the
  end. Values keep their type; a missing one is None.
- Foreach: `values` in the order written, each read for item references
  (3.2) when its pass starts; `<id>_CURRENT_VALUE`, and v1's
  `<id>_CURRENT_ITERATION` and `<id>_NB_LINE`. A value that was a Java
  expression in Talend has lost its outer quotes in conversion
  (`src/converters/talend_to_v1/components/iterate/foreach.py:49`); what
  the reader of 3.2 cannot take is refused.

### 3.7 One read of many files

For a reader (delimited first), v2's own keys that give it a set of files in
place of one, found by the same code as the file list's, in the same order,
under the same rules.

- How: v2's reader already works file by file: header, footer and limit are
  counted in one file (`src/v2/components/file/file_input_delimited.py:283-306`),
  a file in another encoding is read through a copy (`:175`), rows are
  numbered in their file (`:279-280`). So build the reader's plan once for
  each file and put the frames one after another (`pl.concat`), not one
  `scan_csv` over a list, where `skip_rows`, `n_rows` and the row number
  would have to mean something across files (section 5, item 2).
- What it gives: one subjob, one pass, all or nothing; a column with the
  file's path if the job asks for one (`include_file_paths`, or a literal
  for each file's frame).
- What it needs from the engine: a row's hidden number has to say which
  file, so that a failure still reads "line 7 of b.csv"
  (`src/v2/rows.py:102-128`, `Source.locate`); and the row count that goes
  wrong over a `concat` under `slice` on Polars 1.44 is already worked
  round (`runner.py:954-964`).
- What it does not give: a bad file fails the read. Keeping the good files
  and dropping the bad one is the loop's job (finding 7).
- Not recommended: handing Polars a pattern. Its expansion leaves out
  empty files, follows links and has its own dialect [PL-PATHS]; v2 would
  then have two answers to "which files".
- A ledger of files already read: not recommended now. No engine in 2.2
  keeps one without a store that commits with the output; moving or
  deleting a file after a pass is already a job's own doing with v2's file
  copy and file delete; and the people who run these jobs clear and back up
  files themselves. If it is wanted later, the key is the path and the
  size or a checksum, as in Camel and Snowflake.

### 3.8 Run job

| Matter | Options | Recommendation | Why |
|---|---|---|---|
| Where the child runs | (a) in the parent's process, a `Runner` and a `RunContext` of its own; (b) a new process through the command line | (a). `use_independent_process` accepted and without effect | Talend's default and v1's; Talend's reason for (b) was the JVM's memory limit, and v2's memory does not grow with the data; (b) puts parameters on a command line, where they can be seen; for its independent process Talend has "Load context parameters from file", which writes them to a temporary file instead [QL-RUNJOB] (that this is its reason: inferred) |
| When the child is found | (a) at run, as v1 (`src/v1/engine/child_job_runner.py:210-246`); (b) at load | (b): the child's job config is found, loaded and checked when the parent is; its refusals are in the parent's report, under the run job's id | "refuses at load whatever it cannot run"; Kestra and Talend know the child before a run; a loop that runs a child N times loads it once |
| Which file | v1's rule: `<process>.json` in the parent's folder, else the highest `<process>_<M.m>.json` there; `engine_config.jobs_dir` stands in for that folder when the parent was not read from a file (`src/v1/engine/child_job_runner.py:50-112`; `src/v1/engine/engine.py:137-146`) | the same | the converter names a job after its item file, version included (`src/converters/talend_to_v1/xml_parser.py:63`), and tRunJob names the job without it |
| Cycles | (a) a depth limit at run (v1: `max_run_job_depth`, default 2); (b) refused at load | (b): the jobs form a tree at load or the parent is refused; no depth limit is then needed | Kestra |
| `use_dynamic_job`, `use_dynamic_context` | refuse; or allow where the name is known at load | refuse when on, with the reason | v1 refuses both (`src/v1/engine/components/control/run_job.py:40-43`); the child must be known at load |
| Parameters | (a) pass anything, as Talend; (b) what the child declares | (b). `context_params`: each `param_name` must be a context variable of the child, else refused at load; its value is text read for item references (3.2), then typed as the child declares it. `transmit_whole_context`: the parent's variables that the child declares. Later wins: the child's own value, the whole context, the table | Kestra's and Azure Data Factory's declared inputs; a mistyped name is found before the run; the order is Talend's [QL-RUNJOB] |
| What comes back | (a) nothing but the code; (b) a declared set of values | (a): `<id>_CHILD_RETURN_CODE` (0; else the child's die code, else 1), `<id>_CHILD_EXCEPTION_STACKTRACE` (the child's one-line reason: v2 shows no stack), `<id>_ERROR_MESSAGE`, and the child's summary inside the parent's. The child's context and globalMap do not reach the parent | the names a converted RunIf reads; Hop: "downstream only"; (b) can come when a job needs it |
| `propagate_child_result` | refuse; or build a buffer | refuse when on | it needs tBufferOutput, which v2 has not, and Talend holds those rows in memory |
| A failed child | `die_on_child_error` on (default): the run job fails with the child's reason, as any component fails. Off: a WARNING, the entries above, and the parent goes on | as the converter writes it | [TL-RUNJOB-MAIN L614-630]; v1 ends the whole parent instead (`src/v1/engine/components/control/run_job.py:69-75`), which Talend does not |
| A flow into or out of it | Talend allows one in and one out [TL-RUNJOB-XML L30], and its code is in the component's main part, so it runs for each row (inferred); v1 runs once and ignores the rows (`src/v1/engine/components/control/run_job.py:51-78`) | refuse the flow, and say to use flow to iterate | v2's rule for an action; a per-row run inside a streaming pass has no meaning |
| The JVM keys, `print_parameter`, `transmit_original_context` | - | accepted, without effect | they tune a JVM or print; typed values are passed as they are |
| Stopping | - | Ctrl-C unwinds child and parent alike, each discarding its temporary files | one process (`runner.py:456-459`) |

### 3.9 Prejob and postjob

Both are markers: an action that does nothing and has one trigger out.

| Matter | Options | Recommendation | Why |
|---|---|---|---|
| Order | - | three phases: what the prejob markers set off; the other subjobs nothing triggers, as today; what the postjob markers set off | [TL-FOOTER]; v1 does the same (`src/v1/engine/execution_plan.py:178-201`) |
| Set-up failed | (a) go on, as Talend; (b) do not run the main phase | (b), and say in the log that it was not run and why | Airflow: "If a setup fails or is skipped, the work tasks which depend them will be marked ask failures or skips"; a main part run on a set-up that failed fails later and less clearly |
| Clean-up after a failure | (a) skip, as v1; (b) run | (b): postjob runs when the main phase failed, when the prejob failed, and after a die | every source in 2.5 that says (Talend, Airflow, Kestra, Argo, dbt); a clean-up that runs only after success is not one |
| Clean-up failed | (a) ignore, as Airflow by default; (b) count it | (b): it is in `failures` and the job has failed, but the job's `error` stays the first failure | what was not cleaned up is still there, so say it; never let the later error hide the first |
| A die in the postjob | - | ends the postjob | as anywhere |
| Stopped from outside | (a) no clean-up; (b) clean-up on Ctrl-C or SIGTERM | (a) first; (b) is a question (3.12) | Kestra and Airflow do run it; v2 has no SIGTERM handling yet. Prefect gives such a run an end state of its own, CRASHED: "interrupted by an OS signal such as a `KeyboardInterrupt` or an unexpected `SIGTERM`" [PF-STATE], which the summary could say too |

v1 skips postjob after any failure, "a deliberate divergence from Talend's
always-run cleanup semantics, chosen for this engine"
(`src/v1/engine/components/control/postjob.py:15-17`). Why is written
nowhere I could find. If postjob was used for steps meant for success only
(a mail, an archive of the input), those belong behind the main subjob's
OnSubjobOk. Ask before turning it round.

### 3.10 Sleep

- An action that stands alone: reached by a trigger or an iterate link. A
  flow through it is refused at load: Talend sleeps for every row there
  [TL-SLEEP-MAIN], and a pause for each row has no place in one streaming
  pass.
- `pause_duration`: seconds, whole or decimal, or an item reference read
  when its turn comes. Not a finite number of zero or more: the job fails
  and says so, at load when it is written out, at run when it is a
  reference. v1 warns and does not sleep
  (`src/v1/engine/components/control/sleep.py:59-71`), which lets a typing
  mistake pass for a pause.
- One INFO line before ("sleeping 30 s") and one after. Ctrl-C ends it at
  once [PY-TIME] [PY-SIGNAL].
- It is not a wait for anything. The usual reason for a sleep in a job, a
  file that is still arriving, is met by `min_age_seconds` (3.5) or by a
  wait-for-file with an interval, an end and a stated outcome at the end
  (2.6). That component (tWaitForFile) is not among the seven.

### 3.11 Where a recommendation departs from Talend, and why it is better for long use

| # | Talend | Recommended | Why |
|---|---|---|---|
| 1 | A folder that is not there gives no pass and no error | The job fails | an unattended job that finds no folder has not done its work |
| 2 | A mask matches dot names | Dot names are left out unless the mask starts with a dot | unfinished files carry dot names; the shell's rule |
| 3 | Links are followed anywhere; subfolders through links too | No link out of the folder; no walk into a linked folder | safe by default; no loop of links |
| 4 | "Files" is anything not a folder | Regular files | a pipe or a device is not a file to read |
| 5 | Regular-expression masks are Java's | Python's; what does not compile is refused | no Java; a clear refusal beats a wrong match |
| 6 | Passes may run in parallel, sharing globalMap | Passes run in order | the same result twice; the engine is parallel inside a pass |
| 7 | A pass has no name; nothing lists what failed | Every pass is logged and counted; failed items are in the summary | "it says what it did" |
| 8 | Flow to iterate runs as rows arrive, without limit | Rows go to a scratch file; passes are fed in batches; a cap | memory that does not grow; a runaway loop is stopped with a reason |
| 9 | A failed prejob does not stop the main part | It does | the main part needs its set-up |
| 10 | A child gets any parameter; a missing child is a build error; cycles are not checked | Parameters must be declared by the child; the tree is loaded and checked first; a cycle refuses the job | mistakes are found before a run |
| 11 | "Propagate the child result", dynamic job | Refused | rows held in memory; a child not known at load |
| 12 | tSleep in a flow sleeps for each row | A sleep stands alone; a flow through it is refused | a pause for each row has no place in one streaming pass |

Not departures from Talend, but from v1: the order "By default" (sorted by
path), postjob after a failure and after a die, the exclude list split on
commas, a failed child that fails its subjob and not the whole parent, and
a pause that is not a number failing the job (in Talend the value is Java
code, so it would not compile: inferred; v1 warns and does not sleep).

### 3.12 Questions to settle before building

1. Why does v1 skip postjob after a failure, and may v2 turn that round?
2. Is "go on after a failed item" wanted in the first build, or stop only?
3. The default of `max_items`.
4. Dot names left out by default: acceptable for converted jobs?
5. A folder that is not there fails the job: acceptable, given jobs that
   poll a folder which may not exist yet?
6. The row count of a body's component in globalMap: this pass's, or the
   sum as today?
7. Which of a child's `run` settings hold when it runs as a child
   (`summary_file` above all)?
8. Should postjob run when the job is stopped from outside, and should v2
   catch SIGTERM at all?
9. `--only` by a place in a file, inside a loop.

## 4. Compatibility facts

### 4.1 The iterate link in a job config

- It is written among the flows. `_FLOW_CONNECTOR_TYPES` holds `"ITERATE"`
  (`src/converters/talend_to_v1/converter.py:27-30`), and a flow is
  `{"name": <UNIQUE_NAME or label, else the source's id>, "from": <id>,
  "to": <id>, "type": "iterate"}` (`converter.py:242-247`; the name is read
  at `src/converters/talend_to_v1/xml_parser.py:257-264`).
- Two more keys on an iterate flow, since the converter learned them:
  `"enable_parallel"` (true when the link's `ENABLE_PARALLEL` is "true")
  and `"number_parallel"` (the link's `NUMBER_PARALLEL` as a whole number,
  0 when it cannot be read) (`converter.py:249-258`). Observed here: the
  samples convert to `"enable_parallel": false, "number_parallel": 2`
  (tFileList, tFlowToIterate, tForeach) and `0` (tLoop). With parallel on,
  a `_needs_review` entry is added (`converter.py:259-269`).
- Older conversions lack the two keys: the checked-in
  `tests/talend_xml_samples/converted_jsons/Job_tFileList_0.1.json:332-337`
  has `name`, `from`, `to`, `type` only. Both shapes must load.
- The flow's name is added to the source's `outputs` and the target's
  `inputs` (`converter.py:280-295`), and the target's schema gets
  `"inputs": {"iterate1": []}` and `"input": []`
  (`converter.py:321-386`; `Job_tFileList_0.1.json:155-161`).
- `subjobs` lists the looping component and its body as one subjob, because
  it is derived from every flow, iterate included (`converter.py:393-441`;
  `Job_tFileList_0.1.json:352-359`). v2 does not read `subjobs`
  (`src/v2/job/loader.py:116`).
- v2 today: `"iterate flows are not supported in v2"`
  (`loader.py:484-486`); `enable_parallel` and `number_parallel` are not
  among the flow keys (`loader.py:148-155`), so each is an "unknown config
  key" (`src/v2/job/keys.py:122-126`); and were the link kept as a flow, a
  source would be refused for taking an input (`loader.py:570-579`).
- Triggers are as for any component: `{"type", "from", "to", "output_id"}`
  and `"condition"` for a RunIf
  (`src/converters/talend_to_v1/trigger_mapper.py:74-84`); connections of
  any other kind (Talend's Synchronize and Parallelize among them) are
  dropped by both passes without a word (`converter.py:237-238`,
  `trigger_mapper.py:50-51`).

### 4.2 The keys the converter writes, and what v1's engine reads

Every component is wrapped as `{"id", "type", "original_type", "position",
"config", "schema", "inputs", "outputs"}`
(`src/converters/talend_to_v1/components/base.py:238-254`), here always with
`"schema": {"input": [], "output": []}`; every config ends with
`tstatcatcher_stats` (bool) and `label` (text), which v2 accepts on any
component (`src/v2/components/base.py:34-40`).

In this section a path that starts `conv/` is under
`src/converters/talend_to_v1/components/`, and one that starts `v1/` is
under `src/v1/engine/components/`. In each table the "Converter" column
gives lines of the converter's file and the last column lines of v1's file,
both named above the table.

File list. Type written: `tFileList` (`conv/file/file_list.py:122`). v1
knows `FileList`, `tFileList` (`v1/file/file_list.py:105`).

| Key | Talend parameter | Written as | Converter (`conv/file/file_list.py`) | v1's engine reads (`v1/file/file_list.py`) |
|---|---|---|---|---|
| `directory` | `DIRECTORY` | text, "" when absent (then a warning, L114-117) | L83 | `DIRECTORY`, else `directory` (L224) |
| `list_mode` | `LIST_MODE` | `FILES`, `DIRECTORIES` or `BOTH`; default `FILES` | L84 | `LIST_MODE`, `list_mode` (L238) |
| `include_subdirs` | `INCLUDSUBDIR` | bool, false | L86 | `INCLUDSUBDIR`, `include_subdirs` (L237) |
| `case_sensitive` | `CASE_SENSITIVE` | text, `YES` or `NO`; default `YES`; a sample has `"false"` (`Job_tFileList_0.1.json:26`) | L87 | `CASE_SENSITIVE`, `case_sensitive`; takes `YES`, `NO`, `yes`, `no`, `true`, `false`, `True`, `False` and booleans (L78-79, L233, L442-452) |
| `error` | `ERROR` | bool, false | L88 | `ERROR`, `error` (L262) |
| `glob_expressions` | `GLOBEXPRESSIONS` | bool, true | L89 | `GLOBEXPRESSIONS`, `glob_expressions`, else `USE_GLOB` (L227-231) |
| `files` | `FILES` (table of `FILEMASK`) | list of `{"filemask": <text, outer quotes stripped>}` | L92 (L47-65) | `FILES`, `files`; each entry `FILEMASK` or `filemask` (L225, L270-274) |
| `order_by_nothing` | `ORDER_BY_NOTHING` | bool, true | L95 | not read (it is what is left) |
| `order_by_filename` | `ORDER_BY_FILENAME` | bool, false | L96 | `ORDER_BY_FILENAME`, `order_by_filename` (L244) |
| `order_by_filesize` | `ORDER_BY_FILESIZE` | bool, false | L97 | `ORDER_BY_FILESIZE`, `order_by_filesize` (L246) |
| `order_by_modifieddate` | `ORDER_BY_MODIFIEDDATE` | bool, false | L98 | `ORDER_BY_MODIFIEDDATE`, `order_by_modifieddate` (L248) |
| `order_action_asc` | `ORDER_ACTION_ASC` | bool, true | L101 | not read |
| `order_action_desc` | `ORDER_ACTION_DESC` | bool, false | L102 | `ORDER_ACTION_DESC`, `order_action_desc` (L257) |
| `exclude_file` | `IFEXCLUDE` | bool, false | L105 | `IFEXCLUDE`, `exclude_file` (L263) |
| `exclude_filemask` | `EXCLUDEFILEMASK` | text, `*.txt` by default | L106 | `EXCLUDEFILEMASK`, `exclude_filemask` (L264) |
| `format_filepath_to_slash` | `FORMAT_FILEPATH_TO_SLASH` | bool, false | L107 | `FORMAT_FILEPATH_TO_SLASH`, `format_filepath_to_slash` (L265-267) |

v1 also reads, though the converter never writes them: `ORDER_BY` /
`order_by` (`ORDER_BY_NOTHING`, `ORDER_BY_FILENAME`, `ORDER_BY_FILESIZE`,
`ORDER_BY_MODIFIEDDATE`; `v1/file/file_list.py:241`) and `ORDER_ACTION` /
`order_action` (`ORDER_ACTION_ASC`, `ORDER_ACTION_DESC`; `:254`), and
`die_on_error` (`src/v1/engine/base_iterate_component.py:177`). Every
file-list config carries a `_needs_review` note that there is "No concrete
engine implementation" (`conv/file/file_list.py:129-133`), which is no
longer true of v1.

Flow to iterate. Type written: `tFlowToIterate`
(`conv/iterate/flow_to_iterate.py:92`). v1 knows `FlowToIterate`,
`tFlowToIterate` (`v1/iterate/flow_to_iterate.py:65`).

| Key | Talend parameter | Written as | Converter (`conv/iterate/flow_to_iterate.py`) | v1's engine reads (`v1/iterate/flow_to_iterate.py`) |
|---|---|---|---|---|
| `default_map` | `DEFAULT_MAP` | bool, true | L76-77 | `default_map`, which must be a bool (L101-106) |
| `map_entries` | `MAP` (table of `KEY`, `VALUE`) | list of `{"key": <text>, "value": <column>}`, outer quotes stripped; always `[]` when `default_map` is true | L80-83 (L29-57) | `map_entries`, each `key` and `value` (L206-209) |

The prefix of the default entries is the name of the incoming flow: v1 takes
the first of the component's `inputs` (`v1/iterate/flow_to_iterate.py:198`).
This config too carries a `_needs_review` note
(`conv/iterate/flow_to_iterate.py:98-102`).

Foreach. Type written: `tForeach` (`conv/iterate/foreach.py:80`). v1 knows
`Foreach`, `tForeach` (`v1/iterate/foreach.py:57`).

| Key | Talend parameter | Written as | Converter (`conv/iterate/foreach.py`) | v1's engine reads (`v1/iterate/foreach.py`) |
|---|---|---|---|---|
| `values` | `VALUES` (table of `VALUE`) | list of text, each with outer quotes stripped (L49) | L71 | `values`, every item a string (L82-93, L110) |

Run job. Type written: `tRunJob` (`conv/control/run_job.py:157`). v1 knows
`RunJob`, `tRunJob` (`v1/control/run_job.py:35`).

| Key | Talend parameter | Written as | Converter (`conv/control/run_job.py`) | v1's engine (`v1/control/run_job.py`) |
|---|---|---|---|---|
| `use_dynamic_job` | `USE_DYNAMIC_JOB` | bool, false | L126 | true is refused (L40-41) |
| `context_job` | `CONTEXT_JOB` | text, "" | L127 | not read |
| `process` | `PROCESS` | text, "": the child's name, no version | L128 | required (L44-45, L56) |
| `context_name` | `CONTEXT_NAME` | text, `Default` | L129 | read, default `Default` (L60) |
| `use_independent_process` | `USE_INDEPENDENT_PROCESS` | bool, false | L130 | a warning when true (L29-32, L46-49) |
| `die_on_child_error` | `DIE_ON_CHILD_ERROR` | bool, true | L131 | read, default true (L69) |
| `transmit_whole_context` | `TRANSMIT_WHOLE_CONTEXT` | bool, false | L132 | read (L57-58) |
| `context_params` | `CONTEXTPARAMS` (table of `PARAM_NAME_COLUMN`, `PARAM_VALUE_COLUMN`) | list of `{"param_name", "param_value"}`, outer quotes stripped | L135 (L51-79) | read; a value may be one `globalMap.get("K")`, bare or cast, never joined to text (L22-26, L80-101) |
| `jvm_arguments` | `JVM_ARGUMENTS` (table of `ARGUMENT`) | list of `{"argument"}` | L136 (L82-107) | not read |
| `propagate_child_result` | `PROPAGATE_CHILD_RESULT` | bool, false | L139 | a warning when true (L29-32) |
| `print_parameter` | `PRINT_PARAMETER` | bool, false | L140 | a warning when true (L29-32) |
| `transmit_original_context` | `TRANSMIT_ORIGINAL_CONTEXT` | bool, true | L141 | not read |
| `use_child_jvm_setting` | `USE_CHILD_JVM_SETTING` | bool, true | L142 | not read |
| `use_custom_jvm_setting` | `USE_CUSTOM_JVM_SETTING` | bool, false | L143 | a warning when true (L29-32) |
| `use_dynamic_context` | `USE_DYNAMIC_CONTEXT` | bool, false | L144 | true is refused (L42-43) |
| `dynamic_context` | `DYNAMIC_CONTEXT` | text, "" | L145 | not read |
| `use_extra_classpath` | `USE_EXTRA_CLASSPATH` | bool, false | L146 | a warning when true (L29-32) |
| `extra_classpath` | `EXTRA_CLASSPATH` | text, "" | L147 | not read |
| `load_context_from_file` | `LOAD_CONTEXT_FROM_FILE` | bool, false | L148 | a warning when true (L29-32) |

- `context_name` is Talend's `CONTEXT_NAME`, which its definition shows for
  a dynamic job only; the context chosen for a fixed child is another
  parameter (`PROCESS_TYPE_CONTEXT`, [TL-RUNJOB-MAIN L51] [TL-RUNJOB-XML
  L69-73]) that the converter does not read. So `context_name` will mostly
  be `Default` (inferred).
- v1 puts `<id>_CHILD_RETURN_CODE` and `<id>_CHILD_EXCEPTION_STACKTRACE`
  (`v1/control/run_job.py:65-67`).
- v1 also reads, from the top of the job config, `engine_config.jobs_dir`
  and `engine_config.max_run_job_depth` (default 2)
  (`src/v1/engine/engine.py:137-146`), and
  `engine_config.iterate.log_per_iter_threshold` (default 50; `:168-173`,
  `src/v1/engine/iterate_logging.py:19`). The converter writes none of
  them; v2 accepts `engine_config` and reads nothing in it
  (`src/v2/job/loader.py:126`).

Prejob and postjob. Types written: `tPrejob` (`conv/control/prejob.py:50`),
`tPostjob` (`conv/control/postjob.py:53`); no key but the two every
component has. v1 knows `Prejob`, `tPrejob` and `Postjob`, `tPostjob`
(`v1/control/prejob.py:34`, `v1/control/postjob.py:39`). Each config
carries a `_needs_review` note (`conv/control/prejob.py:41-45`,
`conv/control/postjob.py:41-48`). Every trigger leaving a component whose
id starts with `tPrejob` is written as `OnComponentOk`, whatever it was
(`src/converters/talend_to_v1/trigger_mapper.py:67-72`).

Sleep. Type written: `SleepComponent` (`conv/control/sleep.py:45`). v1
knows `Sleep`, `SleepComponent`, `tSleep` (`v1/control/sleep.py:24`).

| Key | Talend parameter | Written as | Converter (`conv/control/sleep.py`) | v1's engine reads (`v1/control/sleep.py`) |
|---|---|---|---|---|
| `pause_duration` | `PAUSE` | text, `"1"` by default | L35 | `pause_duration`, a number or text (L45, L58) |

Not among the seven, written by the same folder: `tLoop` with `for_loop`,
`while_loop`, `from_value`, `to_value`, `step`, `increase`, `declaration`,
`condition`, `iteration` (`conv/control/loop.py:45-57`, `:73`), which also
leaves by an iterate link; `tParallelize` with `wait_for`, `sleeptime`,
`die_on_error` (`conv/control/parallelize.py:41-43`, `:60`). v1 has
neither; v2 refuses an unknown type (`src/v2/job/loader.py:392-394`).

### 4.3 How a body names the item

| Shape | Where | Seen in |
|---|---|---|
| `{{java}}((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))` | the `filepath` of a reader and of a delimited output, which the converter marks (`conv/file/file_input_delimited.py:136-140`, `conv/file/file_output_delimited.py:62-71`) | observed here, converting `Job_tFileList_0.1.item` and `Job_tFlowToIterate_0.1.item` (`{{java}}((String)globalMap.get("row1.filepath"))`) |
| `{{java}}(String)globalMap.get("tForeach_1_CURRENT_VALUE")` | the same, where the job wrote one pair of brackets | observed here, converting `Job_tForEach_0.1.item` |
| `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`, unmarked | conversions made before the mark; and keys of converters that do not mark | `tests/talend_xml_samples/converted_jsons/Job_tFileList_0.1.json:64` |

Paths starting `conv/` are as in 4.2. Converters under `conv/file/` that
call `mark_java_expression`: delimited, positional, full row, Excel, JSON,
XML, MSXML, raw and properties inputs, delimited output, file row count,
fixed flow input, set global var; under `conv/transform/`, row generator.
Those that do not: file list, file copy, file delete, file exist, file
touch, file archive, file unarchive, file properties, the Excel,
positional, XML and EBCDIC outputs, and run job. (From a search for the
call on 2026-10-12.) A string parameter keeps its text as written in
Talend, less one pair of outer quotes
(`src/converters/talend_to_v1/components/base.py:88-97`), so a joined
expression arrives whole.

A key from flow to iterate has a dot in it (`row1.filepath`).

### 4.4 Names in globalMap that a converted job may read

`<id>_CURRENT_FILE`, `<id>_CURRENT_FILEPATH`, `<id>_CURRENT_FILEDIRECTORY`,
`<id>_CURRENT_FILEEXTENSION`, `<id>_NB_FILE` [TL-FILELIST-XML L113-119];
`<flow>.<column>` or the job's own keys, `<id>_CURRENT_ITERATION`,
`<id>_NB_LINE` [TL-F2I-XML L64-67]; `<id>_CURRENT_VALUE` [TL-FOREACH-XML
L51-53]; `<id>_CHILD_RETURN_CODE`, `<id>_CHILD_EXCEPTION_STACKTRACE`
[TL-RUNJOB-XML L157-160]; none for tPrejob, tPostjob and tSleep. v1 adds
`<id>_CURRENT_ITERATION` to every looping component
(`src/v1/engine/base_iterate_component.py:328-332`) and the three row
counts.

### 4.5 The samples in the repository

- `tests/talend_xml_samples/Job_tPreJob_tPostJob_0.1.item` names its
  components `tPreJob` and `tPostJob` (L105, L154). Talend's names are
  `tPrejob` and `tPostjob` (the folders in Talaxie; the generator compares
  with those spellings, [TL-FOOTER L1063-1069]), and those are what the
  converter knows (`conv/control/prejob.py:18`,
  `conv/control/postjob.py:18`). Observed here: the sample converts to two
  placeholders with `"_unsupported": true` and an empty config
  (`src/converters/talend_to_v1/converter.py:201-214`), and the trigger
  rule for `tPrejob` ids does not see `tPreJob_1`.
- `tests/talend_xml_samples/Job_tRunJob_Parent_0.1.item` is not well-formed
  XML (observed here: "mismatched tag: line 100, column 2"), and its
  parameter table uses `PARAM_NAME` and `PARAM_VALUE` where Talend and the
  converter have `PARAM_NAME_COLUMN` and `PARAM_VALUE_COLUMN`
  ([TL-RUNJOB-XML L97-98]; `conv/control/run_job.py:73-76`). No converted
  run job exists in the samples.
- There is no sample of tSleep.
- The loop samples all write one output with `"append": true` and
  `"include_header": true` (`Job_tFileList_0.1.json:273-274`): the "many
  files, one output" case of question 2, done by a loop.

## 5. To verify by experiment

On this machine first; items marked (target) need the RHEL servers and
Python 3.12 before they are relied on.

1. Polars, a list of files: do rows come out in the list's order from
   `pl.scan_csv([a, b, c], glob=False, ...)` under the streaming engine,
   through `collect_all` and through `sink_csv`, with v2's arguments
   (`has_header=False`, `schema=`, `row_index_name=`)?
2. Polars, a list of files: are `skip_rows`, `n_rows` and the row index
   counted in each file or over all of them?
3. Polars: `pl.concat` of N one-file plans (v2's reader, with header,
   footer and limit in each): order kept under streaming? Memory flat for
   10, 100, 1000 files? Time to build and optimise the plan against N? Are
   all files open at once (`ulimit -n`)?
4. Polars: `include_file_paths`: the path as given, or made absolute? Its
   cost on a wide file.
5. Polars, inside a list or a `concat`: a file that is missing, unreadable,
   empty, or short of fields. Which error, and does it name the file? Does
   `raise_if_empty=False` cover an empty file in the middle?
6. Polars: confirm from a run that a pattern leaves out zero-length files
   and follows links, as its source reads [PL-PATHS]; and that v2 never
   passes `glob=True`.
7. Polars 1.44: does the row count of `runner.py:954-964` hold over files
   put one after another, and is the lost projection around `cache()` (see
   `docs/v2/writing-a-component.md`) still avoided there?
8. v2: run one body subjob 1,000 and 10,000 times in one process: does
   memory grow (`RunContext.made`, `put_by`, Polars' own)? Are scratch
   files gone after each pass?
9. v2: the fixed cost of one pass for a small body (reader, map, writer) on
   a file of a few rows, against the same files read once through
   `concat`. This decides how much option D matters (3.3).
10. Listing: `os.scandir` over a folder of 100,000 and of 1,000,000
    entries: time and memory to list, to `stat` each and to sort by date.
    (target: on the file systems the jobs use; over NFS if they do.)
11. Listing: with `os.scandir` and `is_dir(follow_symlinks=False)`: a link
    to a folder, a loop of links, a broken link, a link to a file outside
    the folder, a pipe. (target)
12. A file being written: how fine are modification times on the target
    file systems, and over NFS how late do size and time show (attribute
    caching)? A minimum age has to be longer than that. (target)
13. Masks: run Talend's glob rules [ORO-GLOB] and Python's `fnmatch` over
    the same names for `[^a]*`, `a\*b`, `*.CSV` with case off, a name with
    a line break. Observed here already: `fnmatch.translate` keeps `^` and
    the backslash literal.
14. Signals: `kill -TERM` of a v2 job that is writing: are
    `.name.id.v2tmp<pid>` files left? (No handler was found in `src/v2`.)
    With a handler that raises: are they removed, and does a sleep end?
15. Regular-expression masks: collect those of the real jobs
    (`glob_expressions` false) and compile each with `re` on Python 3.12.
    Observed here on 3.14.6: `\p{Alpha}`, `\Q..\E`, `(?<n>..)` and a flag
    in mid-pattern are refused; `\z` is taken, which 3.12 may not take.
    (target)
16. The real jobs: count the shapes in which a body names its item (4.3):
    alone, marked or not; joined to text; with a Java method. And count the
    foreach values that are not plain text. This sizes 3.2.
17. The real jobs: how many loops are "list, read, write with append" and
    nothing else (candidates for 3.7), how many act on files in the body,
    how many nest, how many set `enable_parallel`.
18. A child in the parent's process: a `Runner` inside a `Runner`: log
    levels (`logging_from` counts its users, `src/v2/engine/__init__.py:183-209`),
    the summary inside the summary, memory after the child has run 1,000
    times in a loop.
19. Talend, if a doubt remains (the templates were read, not run): that
    tPostjob runs after a tDie without "Exit the JVM immediately"; that the
    main part runs after a failed prejob; that "By default" order is by
    path. One small job each, on Talend 8 or Talaxie.

## 6. Sources

All fetched 2026-10-12. GitHub sources are at the tag or commit shown.

Talend (Talaxie `tdi-studio-se` at `639d5fd1f776`, 2024-10-20; base
`https://github.com/Talaxie/tdi-studio-se/blob/639d5fd1f776/main/plugins/`):

- [TL-FILELIST-XML], [TL-FILELIST-BEGIN], [TL-FILELIST-END]:
  `org.talend.designer.components.localprovider/components/tFileList/tFileList_java.xml`,
  `tFileList_begin.javajet`, `tFileList_end.javajet`
- [TL-F2I-XML], [TL-F2I-MAIN], [TL-F2I-END]: `.../components/tFlowToIterate/tFlowToIterate_java.xml`,
  `_main.javajet`, `_end.javajet`
- [TL-FOREACH-XML], [TL-FOREACH-BEGIN]: `.../components/tForeach/tForeach_java.xml`, `_begin.javajet`
- [TL-RUNJOB-XML], [TL-RUNJOB-MAIN]: `.../components/tRunJob/tRunJob_java.xml`, `_main.javajet`
- [TL-PREJOB-XML], [TL-POSTJOB-XML]: `.../components/tPrejob/tPrejob_java.xml`,
  `.../components/tPostjob/tPostjob_java.xml`
- [TL-SLEEP-XML], [TL-SLEEP-MAIN]: `.../components/tSleep/tSleep_java.xml`, `_main.javajet`
- [TL-DIE-MAIN]: `.../components/tDie/tDie_main.javajet` (and `tDie_java.xml` L63-65)
- [TL-WAITFILE-XML], [TL-WAITFILE-BEGIN]: `.../components/tWaitForFile/tWaitForFile_java.xml`, `_begin.javajet`
- Named in the text without a tag, same commit: `.../components/tLoop/tLoop_java.xml`,
  `.../components/tFileList/tFileList_messages.properties`,
  `.../components/tWaitForFile/tWaitForFile_messages.properties`
- [TL-FOOTER], [TL-FOOTER-SKEL], [TL-HEADER], [TL-SUBFOOTER], [TL-ITER-HEAD],
  [TL-ITER-FOOT], [TL-COMP-HEAD], [TL-COMP-FOOT]:
  `org.talend.designer.codegen/jet_stub/footer.javajet`, `footer_java.skeleton`,
  `header.javajet`, `subprocess_footer.javajet`, `iterate_subprocess_header.javajet`,
  `iterate_subprocess_footer.javajet`, `component_part_header.javajet`,
  `component_part_footer.javajet`

Talend help (Qlik):

- [QL-PREPOST] https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-08/using-tprejob-and-tpostjob-components (last updated 5/18/2026)
- [QL-RUNJOB] https://help.qlik.com/talend/en-US/components/8.0/orchestration/trunjob-standard-properties (last updated 9/30/2026)
- [QL-ITER] https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-08/iterate-connection (last updated 5/18/2026)
- [QL-PARITER] https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-08/launching-parallel-iterations-to-read-data (last updated 5/18/2026)
- [QL-PARWRITE] https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2025-11/writing-data-in-parallel (last updated 6/1/2026)
- [QL-FILELIST73] https://help.qlik.com/talend/en-US/components/7.3/tfilelist/tfilelist-standard-properties (last updated 2/11/2026; the 8.0 address of the same page sent me to another page that day)

Apache Airflow (`https://github.com/apache/airflow/blob/<tag>/`):

- [AF-MAP] 3.3.2 `airflow-core/docs/authoring-and-scheduling/dynamic-task-mapping.rst`
- [AF-SETUP] 3.3.2 `airflow-core/docs/howto/setup-and-teardown.rst`
- [AF-SENSOR] 3.3.2 `airflow-core/docs/core-concepts/sensors.rst`
- [AF-DEFER] 3.3.2 `airflow-core/docs/authoring-and-scheduling/deferring.rst`
- [AF-OP] 3.3.2 `task-sdk/src/airflow/sdk/bases/operator.py` (parameter docs, L697-822)
- [AF-DAG] 3.3.2 `task-sdk/src/airflow/sdk/definitions/dag.py` (L422-424)
- [AF-TRIG] 3.3.2 `providers/standard/src/airflow/providers/standard/operators/trigger_dagrun.py` (L124-163)
- [AF-2.10] 2.10.5 `docs/apache-airflow/core-concepts/dags.rst` (TaskGroups L538-546; SubDAGs L684-770)
- [AF-3.0] 3.0.0 `RELEASE_NOTES.rst` ("Deprecated and Removed Features")

Dagster (`https://github.com/dagster-io/dagster/blob/1.13.26/docs/docs/`):

- [DG-DYN] `guides/build/ops/dynamic-graphs.md`; [DG-NEST] `guides/build/ops/nesting-graphs.md`;
  [DG-HOOK] `guides/build/ops/op-hooks.md`; [DG-RETRY] `guides/build/ops/op-retries.md`
- [DG-PART] `guides/build/partitions-and-backfills/partitioning-assets.md`;
  [DG-BACKFILL] `guides/build/partitions-and-backfills/backfilling-data.md`
- [DG-DVP] `examples/best-practices/dynamic-vs-parallel.md`; [DG-FAN] `examples/best-practices/dynamic-fanout.md`
- [DG-EXEC] `guides/operate/managing-concurrency/run-executor-limits.md`
- [DG-RES] `guides/build/external-resources/managing-resource-state.md`

Prefect (`https://github.com/PrefectHQ/prefect/blob/3.8.8/docs/v3/`):

- [PF-RUN] `concepts/task-runners.mdx`; [PF-FLOW] `concepts/flows.mdx`; [PF-STATE] `concepts/states.mdx`
- [PF-CONC] `how-to-guides/workflows/run-work-concurrently.mdx`; [PF-RETRY] `how-to-guides/workflows/retries.mdx`
- [PF-DEPLOY] `how-to-guides/deployments/run-deployments.mdx`; [PF-CANCEL] `advanced/cancel-workflows.mdx`

Kestra:

- [KE1-FOREACH], [KE1-ITEM] `https://github.com/kestra-io/kestra/blob/v1.3.42/core/src/main/java/io/kestra/plugin/core/flow/ForEach.java`, `ForEachItem.java`
- [KE2-LOOP], [KE2-SUB], [KE2-SLEEP], [KE2-PAUSE] `https://github.com/kestra-io/kestra/blob/v2.0.5/core/src/main/java/io/kestra/plugin/core/flow/Loop.java`, `Subflow.java`, `Sleep.java`, `Pause.java` (ForEach and ForEachItem are not in the v2.0.5 tree; `OnChildFailureInterface.java` there has CONTINUE, CANCEL, FAIL)
- [KE-FINALLY], [KE-AFTER], [KE-ERRORS], [KE-SUBDOC] `https://github.com/kestra-io/docs/blob/45dc8dbe3c4d/src/contents/docs/05.workflow-components/19.finally/index.md`, `20.afterexecution/index.md`, `11.errors/index.md`, `10.subflows/index.md` (2026-10-09)

Azure Data Factory (Microsoft Learn, each "Last updated on 2026-08-04"):

- [ADF-FOREACH] https://learn.microsoft.com/en-us/azure/data-factory/control-flow-for-each-activity
- [ADF-EXEC] https://learn.microsoft.com/en-us/azure/data-factory/control-flow-execute-pipeline-activity
- [ADF-RETURN] https://learn.microsoft.com/en-us/azure/data-factory/tutorial-pipeline-return-value
- [ADF-WAIT] https://learn.microsoft.com/en-us/azure/data-factory/control-flow-wait-activity

AWS Step Functions (developer guide, "latest"):

- [SFN-MAP] https://docs.aws.amazon.com/step-functions/latest/dg/state-map.html
- [SFN-INLINE] https://docs.aws.amazon.com/step-functions/latest/dg/state-map-inline.html
- [SFN-DIST] https://docs.aws.amazon.com/step-functions/latest/dg/state-map-distributed.html
- [SFN-WAIT] https://docs.aws.amazon.com/step-functions/latest/dg/state-wait.html

Argo Workflows (`https://github.com/argoproj/argo-workflows/blob/v4.1.5/docs/`):

- [ARGO-LOOPS] `walk-through/loops.md`; [ARGO-DAG] `walk-through/dag.md`; [ARGO-EXIT] `walk-through/exit-handlers.md`;
  [ARGO-RETRY] `walk-through/retrying-failed-or-errored-steps.md`; [ARGO-SYNC] `synchronization.md`;
  [ARGO-OFFLOAD] `offloading-large-workflows.md`

Apache Hop (`https://github.com/apache/hop/blob/2.19.0-rc1/docs/hop-user-manual/modules/ROOT/pages/`):

- [HOP-PEXEC] `pipeline/transforms/pipeline-executor.adoc`; [HOP-GETFILES] `pipeline/transforms/getfilenames.adoc`;
  [HOP-LOCKED] `pipeline/transforms/checkfilelocked.adoc`
- [HOP-REPEAT] `workflow/actions/repeat.adoc`; [HOP-REPEND] `workflow/actions/repeat-end.adoc`;
  [HOP-PIPE] `workflow/actions/pipeline.adoc`; [HOP-WAITFILE] `workflow/actions/waitforfile.adoc`

Polars:

- [PL-SIG] the installed package, 1.44.2: `inspect.signature` and docstrings of `scan_csv`, `scan_ndjson`, `scan_lines`, `scan_parquet`, `concat` (observed here)
- [PL-PATHS] https://github.com/pola-rs/polars/blob/py-1.44.2/crates/polars-io/src/path_utils/mod.rs (`expand_paths_hive`)
- [PL-MULTI] https://github.com/pola-rs/polars/blob/py-1.44.2/docs/source/user-guide/io/multiple.md

DuckDB (`https://github.com/duckdb/duckdb-web/blob/e0a2861b9856/docs/current/`, 2026-10-10; DuckDB v1.5.6 was the latest release):

- [DK-MULTI] `data/multiple_files/overview.md`; [DK-SCHEMA] `data/multiple_files/combining_schemas.md`;
  [DK-FAULTY] `data/csv/reading_faulty_csv_files.md`

Apache Spark (`https://github.com/apache/spark/blob/v4.2.0/`):

- [SP-GENERIC] `docs/sql-data-sources-generic-options.md`
- [SP-STREAM] `docs/streaming/apis-on-dataframes-and-datasets.md` (file source L37, L61-96; sinks table L2156-2170)
- [SP-FILEFORMAT] `sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/FileFormat.scala`
- [SP-HIDDEN] `core/src/main/scala/org/apache/spark/util/HadoopFSUtils.scala`

Databricks (each "Last updated on Sep 11, 2026"):

- [DBX-AL] https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/
- [DBX-FAQ] https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/faq
- [DBX-SCHEMA] https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema
- [DBX-META] https://docs.databricks.com/aws/en/ingestion/file-metadata-column

Snowflake:

- [SF-COPY] https://docs.snowflake.com/en/sql-reference/sql/copy-into-table
- [SF-LOAD] https://docs.snowflake.com/en/user-guide/data-load-considerations-load
- [SF-META] https://docs.snowflake.com/en/user-guide/querying-metadata

Python, Java, POSIX:

- [PY-GLOB] https://docs.python.org/3.12/library/glob.html; [PY-FNMATCH] https://docs.python.org/3.12/library/fnmatch.html;
  [PY-OS] https://docs.python.org/3.12/library/os.html (`os.scandir`, `os.walk`);
  [PY-PATHLIB312] https://docs.python.org/3.12/library/pathlib.html; [PY-PATHLIB314] https://docs.python.org/3.14/library/pathlib.html;
  [PY-TIME] https://docs.python.org/3.12/library/time.html; [PY-SIGNAL] https://docs.python.org/3.12/library/signal.html
- [JAVA-FILE] https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/io/File.html;
  [JAVA-PATTERN] https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/util/regex/Pattern.html
- [ORO-GLOB] https://svn.apache.org/repos/asf/jakarta/oro/trunk/src/java/org/apache/oro/text/GlobCompiler.java (the class comment; Talend ships `oro-2.0.8.jar`, [TL-FILELIST-XML L109])
- [POSIX-GLOB] https://pubs.opengroup.org/onlinepubs/9799919799/functions/glob.html (POSIX.1-2024)
- [RUST-META] https://doc.rust-lang.org/std/fs/fn.metadata.html

Others:

- [CAMEL-FILE] https://github.com/apache/camel/blob/camel-4.23.0/components/camel-file/src/main/docs/file-component.adoc
- [CAMEL-JSON] https://github.com/apache/camel/blob/camel-4.23.0/components/camel-file/src/generated/resources/META-INF/org/apache/camel/component/file/file.json (the option descriptions)
- [RSYNC] https://github.com/RsyncProject/rsync/blob/v3.5.1/rsync.1.md (`--temp-dir`)
- [DBT-RUN], [DBT-HOOK], [DBT-END] `https://github.com/dbt-labs/docs.getdbt.com/blob/47f33bcc1c3d/website/docs/reference/project-configs/on-run-start-on-run-end.md` (with `docs/build/hooks-operations.md`), `.../reference/resource-configs/pre-hook-post-hook.md`, `.../reference/dbt-jinja-functions/on-run-end-context.md` (2026-10-09)
- [AWS-BL] https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/
- [SRE] https://sre.google/sre-book/addressing-cascading-failures/
- [PW] https://playwright.dev/docs/api/class-page (`page.waitForTimeout`)

Not used for any claim: the answers of a search tool and of a fetching tool
that summarise pages. Their wording is not the source's; every quotation
above was read in the page or file itself.
