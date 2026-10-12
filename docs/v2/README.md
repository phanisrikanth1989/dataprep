# The v2 engine

v2 runs v1 job configs on Polars. It is pure Python: no Java, no bridge.
What v2 cannot run it refuses before anything starts, in one report.

For most of its components v1 is the answer key: a job that runs on v2
writes the same files v1 writes, with the exceptions listed under
[Differences from v1](differences-from-v1/README.md). The components added
since 2026-10-12 are [built to their own rule](own-rule/README.md) and held
to what is written of them there.

```bash
python -m src.v2 job.json            # run a job
python -m src.v2 job.json --check    # load and check only; run nothing
```

## Where to read what

| To | Read |
|---|---|
| run a job, set how it runs, read its log | [Running a job](running-a-job.md) |
| find the row a job failed on, run a job for a few rows, see what every component did with them | [Looking into a job](looking-into-a-job.md) |
| take a v1 job config to v2, write its expressions in Python | [Taking a v1 job config to v2](from-v1-to-v2.md) |
| know how a job runs, and how types and missing values are held | [How a job runs](how-a-job-runs.md) |
| see where v2 differs from v1 | [Differences from v1](differences-from-v1/README.md) |
| see what a component built to its own rule does | [Components built to their own rule](own-rule/README.md) |
| add or change a component | [Writing a v2 component](writing-a-component.md) |
| have a component's failures name the row of the input | [Row numbers](row-numbers.md) |
| look up a word used on these pages | [`src/v2/CONTEXT.md`](../../src/v2/CONTEXT.md) |

One page per component, with every config key, is generated from the code
and not kept in the repo: `.venv/bin/python scripts/gen_v2_docs.py` writes
`docs/v2/components/`.

## The components

| Component | Type in a job config | What is written of it |
|---|---|---|
| Advanced XML output (tAdvancedFileOutputXML) | `advanced_file_output_xml` | [Own rule: XML](own-rule/xml.md#advanced-xml-output) |
| Aggregate row (tAggregateRow) | `aggregate_row` | [Differences from v1: Rows](differences-from-v1/rows.md#aggregate-row) |
| Aggregate sorted row (tAggregateSortedRow) | `aggregate_sorted_row` | [Differences from v1: Rows](differences-from-v1/rows.md#aggregate-sorted-row) |
| Change file encoding (tChangeFileEncoding) | `change_file_encoding` | [Own rule: File jobs](own-rule/file-jobs.md#change-file-encoding) |
| Context load (tContextLoad) | `context_load` | [Differences from v1: Job control](differences-from-v1/job-control.md#context-load) |
| Convert type (tConvertType) | `convert_type` | [Differences from v1: Rows](differences-from-v1/rows.md#convert-type) |
| Delimited input (tFileInputDelimited) | `file_input_delimited` | [Differences from v1: Sources and outputs](differences-from-v1/sources-and-outputs.md#delimited-files) |
| Delimited output (tFileOutputDelimited) | `file_output_delimited` | [Differences from v1: Sources and outputs](differences-from-v1/sources-and-outputs.md#delimited-files) |
| Denormalize (tDenormalize) | `denormalize` | [Differences from v1: Rows](differences-from-v1/rows.md#denormalize) |
| Die (tDie) | `die` | [Differences from v1: Job control](differences-from-v1/job-control.md#die) |
| Excel input (tFileInputExcel) | `file_input_excel` | [Differences from v1: Sources and outputs](differences-from-v1/sources-and-outputs.md#excel-input) |
| Excel output (tFileOutputExcel) | `file_output_excel` | [Differences from v1: Sources and outputs](differences-from-v1/sources-and-outputs.md#excel-output) |
| Extract delimited fields (tExtractDelimitedFields) | `extract_delimited_fields` | [Differences from v1: Extracting fields](differences-from-v1/extracting-fields.md#extract-delimited-fields) |
| Extract JSON fields (tExtractJSONFields) | `extract_json_fields` | [Differences from v1: Extracting fields](differences-from-v1/extracting-fields.md#extract-json-fields) |
| Extract positional fields (tExtractPositionalFields) | `extract_positional_fields` | [Differences from v1: Extracting fields](differences-from-v1/extracting-fields.md#extract-positional-fields) |
| Extract regex fields (tExtractRegexFields) | `extract_regex_fields` | [Differences from v1: Extracting fields](differences-from-v1/extracting-fields.md#extract-regex-fields) |
| Extract XML field (tExtractXMLField) | `extract_xml_field` | [Own rule: XML](own-rule/xml.md#extract-xml-field) |
| File archive (tFileArchive) | `file_archive` | [Own rule: File jobs](own-rule/file-jobs.md#file-archive) |
| File copy (tFileCopy) | `file_copy` | [Differences from v1: File jobs](differences-from-v1/file-jobs.md#file-copy) |
| File delete (tFileDelete) | `file_delete` | [Differences from v1: File jobs](differences-from-v1/file-jobs.md#file-delete) |
| File exist (tFileExist) | `file_exist` | [Differences from v1: File jobs](differences-from-v1/file-jobs.md#file-exist) |
| File list (tFileList) | `file_list` | [Own rule: Loops and job control](own-rule/loops-and-job-control.md#file-list) |
| File properties (tFileProperties) | `file_properties` | [Own rule: File jobs](own-rule/file-jobs.md#file-properties) |
| File row count (tFileRowCount) | `file_row_count` | [Differences from v1: File jobs](differences-from-v1/file-jobs.md#file-row-count) |
| File touch (tFileTouch) | `file_touch` | [Own rule: File jobs](own-rule/file-jobs.md#file-touch) |
| File unarchive (tFileUnarchive) | `file_unarchive` | [Own rule: File jobs](own-rule/file-jobs.md#file-unarchive) |
| Filter columns (tFilterColumns) | `filter_columns` | [Differences from v1: Rows](differences-from-v1/rows.md#filter-columns) |
| Filter rows (tFilterRow) | `filter_rows` | [Differences from v1: Rows](differences-from-v1/rows.md#filter-rows) |
| Fixed flow input: rows written in the job config (tFixedFlowInput) | `fixed_flow_input` | [Differences from v1: Sources and outputs](differences-from-v1/sources-and-outputs.md#fixed-flow-input) |
| Flow to iterate (tFlowToIterate) | `flow_to_iterate` | [Own rule: Loops and job control](own-rule/loops-and-job-control.md#flow-to-iterate) |
| Foreach (tForeach) | `foreach` | [Own rule: Loops and job control](own-rule/loops-and-job-control.md#foreach) |
| Full-row input (tFileInputFullRow) | `file_input_full_row` | [Differences from v1: Sources and outputs](differences-from-v1/sources-and-outputs.md#full-row-input) |
| Join (tJoin) | `join` | [Differences from v1: Rows](differences-from-v1/rows.md#join) |
| JSON input (tFileInputJSON) | `file_input_json` | [Differences from v1: Sources and outputs](differences-from-v1/sources-and-outputs.md#json-input) |
| Log row (tLogRow) | `log_row` | [Differences from v1: Rows](differences-from-v1/rows.md#log-row) |
| Map (tMap) | `map` | [Differences from v1: Rows](differences-from-v1/rows.md#map) |
| Multi-schema XML input (tFileInputMSXML) | `file_input_msxml` | [Own rule: XML](own-rule/xml.md#multi-schema-xml-input) |
| Normalize (tNormalize) | `normalize` | [Differences from v1: Rows](differences-from-v1/rows.md#normalize) |
| Pivot to columns delimited: an output (tPivotToColumnsDelimited) | `pivot_to_columns_delimited` | [Differences from v1: Sources and outputs](differences-from-v1/sources-and-outputs.md#pivot-to-columns-delimited) |
| Positional input (tFileInputPositional) | `file_input_positional` | [Differences from v1: Sources and outputs](differences-from-v1/sources-and-outputs.md#positional-input) |
| Positional output (tFileOutputPositional) | `file_output_positional` | [Differences from v1: Sources and outputs](differences-from-v1/sources-and-outputs.md#positional-output) |
| Postjob (tPostjob) | `postjob` | [Own rule: Loops and job control](own-rule/loops-and-job-control.md#postjob) |
| Prejob (tPrejob) | `prejob` | [Own rule: Loops and job control](own-rule/loops-and-job-control.md#prejob) |
| Properties input: a properties or an ini file (tFileInputProperties) | `file_input_properties` | [Differences from v1: Sources and outputs](differences-from-v1/sources-and-outputs.md#properties-input) |
| Python dataframe (tPythonDataFrame) | `python_dataframe` | [Differences from v1: Rows](differences-from-v1/rows.md#python-dataframe) |
| Raw file input (tFileInputRaw) | `file_input_raw` | [Own rule: File jobs](own-rule/file-jobs.md#raw-file-input) |
| Replace (tReplace) | `replace` | [Differences from v1: Rows](differences-from-v1/rows.md#replace) |
| Replicate (tReplicate) | `replicate` | [Differences from v1: Rows](differences-from-v1/rows.md#replicate) |
| Row generator: rows made from expressions (tRowGenerator) | `row_generator` | [Differences from v1: Sources and outputs](differences-from-v1/sources-and-outputs.md#row-generator) |
| Run job (tRunJob) | `run_job` | [Own rule: Loops and job control](own-rule/loops-and-job-control.md#run-job) |
| Sample row (tSampleRow) | `sample_row` | [Differences from v1: Rows](differences-from-v1/rows.md#sample-row) |
| Schema compliance check (tSchemaComplianceCheck) | `schema_compliance_check` | [Differences from v1: Rows](differences-from-v1/rows.md#schema-compliance-check) |
| Set global var (tSetGlobalVar) | `set_global_var` | [Differences from v1: Job control](differences-from-v1/job-control.md#set-global-var) |
| Sleep (tSleep) | `sleep` | [Own rule: Loops and job control](own-rule/loops-and-job-control.md#sleep) |
| Sort row (tSortRow) | `sort_row` | [Differences from v1: Rows](differences-from-v1/rows.md#sort-row) |
| Split row (tSplitRow) | `split_row` | [Differences from v1: Rows](differences-from-v1/rows.md#split-row) |
| Unique row (tUniqRow) | `unique_row` | [Differences from v1: Rows](differences-from-v1/rows.md#unique-row) |
| Unite (tUnite) | `unite` | [Differences from v1: Rows](differences-from-v1/rows.md#unite) |
| Unpivot row (tUnpivotRow) | `unpivot_row` | [Differences from v1: Rows](differences-from-v1/rows.md#unpivot-row) |
| Warn (tWarn) | `warn` | [Differences from v1: Job control](differences-from-v1/job-control.md#warn) |
| XML file input (tFileInputXML) | `file_input_xml` | [Own rule: XML](own-rule/xml.md#xml-file-input) |
| XML file output (tFileOutputXML) | `file_output_xml` | [Own rule: XML](own-rule/xml.md#xml-file-output) |
