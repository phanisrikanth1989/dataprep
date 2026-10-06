# Pointing at the input row that failed a job (ticket 37)

Answers ticket 37 in `.scratch/engine-v2/issues/`: how other engines report the
record that failed, what Polars gives to build on, and what "where" means for
inputs that are not lines of text. Options, no decision. Researched 2026-10-06.

## In short

1. None of the tools read for this note says where in the input a row came
   from when it fails in a later step (a conversion inside an expression, a
   join): the position is known only where the row is read, the row-by-row
   tools (Talend, Integration Services) can at most hand the failing row on,
   and the columnar engines (Spark, DuckDB, Polars) name only the bad value.
2. At that place the well-documented loaders agree on what to give: the
   file, a record or line number, often a byte position, the column, the bad
   value and the raw record, and they keep them in a table or file of
   rejected records and not only in the error text.
3. Talend gives less than its messages suggest: the "Line: N" on a rejected
   row is a count of rows read so far and not a line of the file, and with
   "die on error" the message has no line at all.
4. Polars does not say which row failed in any release up to 2.0.0, which
   came out on the day of this research: a failed conversion lists up to ten
   bad values and a count, and a failed CSV read gives a byte position that
   is counted from the start of a chunk, not of the file, when the streaming
   engine reads.
5. A request for file line numbers is open in the Polars tracker without an
   answer, and an earlier one was closed with the explanation that the
   parallel reader does not know the line.
6. Polars does give the pieces to build on: a row number and a file-name
   column added while a file is read, and conversions that turn a bad value
   into a missing one instead of stopping, which is how v2's readers already
   find their rejects.
7. So wherever v2 finds the bad row itself (a reader's rejects, a missing
   value where none is allowed, text a map cannot read as a number) it could
   name the row in the same pass at no measured cost, while for a failure
   Polars raises in the middle of a pass a second look at the data is needed
   on every Polars version.
8. A row number carried through the whole plan costs almost nothing to
   compute but touches every component: it passes a filter and a sort
   unchanged, needs a rule at a join and a union, and is lost by an
   aggregate and by user Python that builds a new table.
9. "Line" is the wrong word for the general case: a quoted field can span
   lines, a workbook has sheets and cells, and JSON and XML have paths, which
   is why Snowflake reports a row number, the line the row starts on and the
   line of the error as three separate numbers.
10. A published shape that covers every kind of input exists: the SARIF
    standard splits a location into a physical part (file plus line and
    column, or a byte position) and a logical part (a path such as a JSON
    Pointer or an XPath), and the W3C model for CSV keeps a row's number
    apart from its position in the source file.
11. For a very wide row the others show the failed column and its value, add
    identifying columns only where the user names them, and send the whole
    record to the store of rejects; several cap or leave out the value,
    whereas v2 today writes the bad value uncapped into the log and the
    summary.
12. Talend hands the error on to later steps through globalMap
    (`<id>_ERROR_MESSAGE`) and tLogCatcher; v2 sets no such entry today.

## How to read this file

Sources are primary only: each tool's own documentation, source code and
release notes, statements by its maintainers in its own tracker, and
published standards (IETF, W3C, OASIS). No blogs, no question-and-answer
sites, no summaries.

Two kinds of statement are kept apart:

- A sourced statement ends with its source in square brackets.
- A statement that starts with "Reasoning:" is mine, drawn from the sourced
  statements around it. It is not a finding.

Nothing was run for this note: no snippet, no benchmark. Where an earlier
note in this folder observed something on Polars 1.44.2, that note is cited
and the word "observed" is kept.

Quotations are word for word. To keep the file plain ASCII a long dash in a
source is written "-", and "..." marks words left out.

What each fact is stamped against:

- v2: commit `99344233` on `feature/engine-v2` (2026-10-06). Line numbers of
  `src/v2` move; they are right for that commit.
- Polars: `py-1.44.2` (installed; released 2026-09-09), `py-2.0.0` (released
  2026-10-06T11:52Z; outside this repo's pin `>=1.44,<2.0`), and `main` at
  commit `a3e0097fd1` (2026-10-06). Release dates:
  https://github.com/pola-rs/polars/releases
- Talend: Qlik's help pages for Talend 8.0 as served on 2026-10-06, and the
  code templates of Talend Open Studio as kept in `Talaxie/tdi-studio-se` at
  commit `639d5fd1f7` (2024-10-20). Talend's own repository
  (`github.com/Talend/tdi-studio-se`) answered "Not Found" on 2026-10-06;
  see "Not verified".
- Apache Spark 4.2.0 (what `docs/latest` served on 2026-10-06; source tag
  `v4.2.0`). DuckDB: `docs/current` on 2026-10-06 and source tag `v1.5.6`
  (released 2026-09-28). PostgreSQL 18 (what `docs/current` served) and
  branch `REL_18_STABLE` at commit `95d9604471` (2026-10-06). Apache Kafka
  source tag `4.1.0`.
- Snowflake, Amazon Redshift, BigQuery, Databricks, dbt, Great Expectations
  and SQL Server: the vendor's pages as served on 2026-10-06; they carry no
  version.
- Installed in this repo's `.venv` and read there: polars 1.44.2 with
  `polars_runtime_32`, pandas 3.0.5, pyarrow 25.0.0, fastexcel 0.21.0.

Shorthand (links to tags and commits do not move):

- `v2:` = `src/v2/` in this repo at commit `99344233`
- `venv:` = `.venv/lib/python3.14/site-packages/` in this repo
- `pl44:` = https://github.com/pola-rs/polars/blob/py-1.44.2/
- `pl20:` = https://github.com/pola-rs/polars/blob/py-2.0.0/
- `#N` = https://github.com/pola-rs/polars/issues/N (pull requests redirect)
- `tal:` = https://github.com/Talaxie/tdi-studio-se/blob/639d5fd1f7/main/plugins/
- `talc:` = `tal:org.talend.designer.components.localprovider/components/`
- `qlik:` = https://help.qlik.com/talend/en-US/
- `spark:` = https://spark.apache.org/docs/4.2.0/
- `sparksrc:` = https://github.com/apache/spark/blob/v4.2.0/
- `duck:` = https://duckdb.org/docs/current/
- `ducksrc:` = https://github.com/duckdb/duckdb/blob/v1.5.6/
- `pg:` = https://www.postgresql.org/docs/18/
- `pgsrc:` = https://github.com/postgres/postgres/blob/95d9604471/
- `snow:` = https://docs.snowflake.com/en/
- `redshift:` = https://docs.aws.amazon.com/redshift/latest/dg/
- `bq:` = https://cloud.google.com/bigquery/docs/
- `kafka:` = https://github.com/apache/kafka/blob/4.1.0/connect/runtime/src/main/java/org/apache/kafka/connect/runtime/
- `rfcN` = https://www.rfc-editor.org/rfc/rfcN.txt
- `note-csv` = `.scratch/engine-v2/research/2026-10-05-polars-delimited-files.md`
- `note-run` = `.scratch/engine-v2/research/2026-10-05-polars-collection-streaming-decimal.md`

---

## 1. How other engines report the record that failed

Each tool below was read for four things: what it shows, where it puts it,
what the location is counted in, and what limit or cost its own pages or
code state. The table in "Comparison" puts them side by side.

### 1.1 Talend, the tool this project replaces

What the documentation says:

- Delimited reader, "Die on error": "Select the checkbox to stop the
  execution of the Job when an error occurs. Clear the checkbox to skip any
  rows on error and complete the process for error-free rows. When errors
  are skipped, you can collect the rows on error using a Row > Reject link."
  [`qlik:components/8.0/delimited/tfileinputdelimited-standard-properties`,
  Basic settings]
- The same component has two global variables, "NB_LINE: the number of rows
  processed" and "ERROR_MESSAGE: the error message generated by the
  component when an error occurs. This is an After variable and it returns a
  string." Neither holds a line or a record number. [same page, Global
  Variables]
- "Check each row structure against schema ... If not consistent, an error
  message will be displayed on the console." [same page, Advanced settings]
- A Rejects connection "gathers the data that does NOT match the filter or
  are not valid for the expected output. This connection allows you to track
  the data that could not be processed for any reason (wrong type, undefined
  null value, etc.). On some components, this connection is enabled when the
  Die on error option is deactivated."
  [`qlik:studio-user-guide/8.0-R2026-09/row-connection`, "Rejects"]
- tMap, with Die on error cleared: "A new table called ErrorReject appears
  in the output area of the Map Editor. This output table automatically
  comprises two columns: errorMessage and errorStackTrace ... You can also
  drag and drop columns from the input tables to this error reject output
  table." [`qlik:studio-user-guide/8.0-R2026-02/handling-errors`]
- tLogCatcher has a fixed schema: moment, pid, root_pid, father_pid,
  project, job, context, priority, type, origin ("the name of the component
  that triggers the message"), message, code; and three switches, Catch Java
  Exception, Catch tDie and Catch tWarn. It has no field for a file, a line,
  a record or a column. [`qlik:components/8.0/logs-and-errors/tlogcatcher`,
  Basic settings]

What the generated Java does (code templates):

- A field that cannot be parsed raises `RuntimeException(String.format(
  "Couldn't parse value for column '%s' in '%s', value is '%s'. Details:
  %s", ...))` with the column, the flow name, the text and the cause, and
  puts the cause's message in globalMap under `<id>_ERROR_MESSAGE`.
  [`talc:tFileInputDelimited/tFileInputDelimited_begin.javajet#L332-L335`]
- The row's catch block: with die on error, `throw(e)`. Otherwise it logs
  `"<id> - " + e.getMessage()` at error level when log4j is on; with a
  reject link it makes a reject row, copies the main row's columns into it
  and sets `errorMessage = e.getMessage() + " - Line: " + tos_count_<id>`;
  with no reject link it prints the message on standard error and drops the
  row. [same file, `#L628-L659`]
- `tos_count_<id>` is declared as `int ... = 0` when a component begins and
  is increased by one at the end of every pass through the component's main
  part.
  [`tal:org.talend.designer.codegen/jet_stub/component_part_header.javajet#L340`;
  `tal:org.talend.designer.codegen/jet_stub/component_part_footer.javajet#L615-L617`]
- The reader object knows a row number of its own (`getRowNumber()`). The
  templates use it for a debug log line and, when the file is done, for
  `NB_LINE`; they do not put it in the reject message. [same reader
  template, `#L694`;
  `talc:tFileInputDelimited/tFileInputDelimited_end.javajet#L52-L81`]
- The positional, JSON (both read modes) and XML readers append the same
  `" - Line: " + tos_count_<id>`.
  [`talc:tFileInputPositional/tFileInputPositional_begin.javajet#L1072`;
  `talc:tFileInputJSON/jsonpath.javajet#L269`;
  `talc:tFileInputJSON/xpath.javajet#L544`;
  `talc:tFileInputXML/tFileInputXML_begin.javajet#L1072`]
- The Excel reader appends more: `" - Line: " + tos_count + " column: " +
  <column name> + " (No. " + <sheet column number> + ")"`; a cell that is
  not a date in a date column raises "The cell format is not Date in ( Row.
  N and ColumnNum. M )". Neither text holds the sheet's name.
  [`talc:tFileInputExcel/tFileInputExcel_begin.javajet#L515`, `#L602-L633`]
- When an exception ends a job, the generated `TalendException` puts
  `<component>_ERROR_MESSAGE` in globalMap, prints "Exception in component
  <id> (<job>)" and the stack trace on standard error, calls the component's
  error method (which sets off the error triggers), and gives every
  tLogCatcher that catches Java exceptions the entry `("Java Exception",
  <component>, 6, <exception class> + ":" + <message>, 1)`.
  [`tal:org.talend.designer.codegen/jet_stub/header.javajet#L679-L726`]

Reasoning: "Line" in a Talend reject message is therefore the number of
rows the component had already handled when this one failed. It starts at
0, and header lines and the extra lines of a field that holds line breaks
are not in it. It is not the line number an editor shows.

Reasoning: with die on error the exception's text names the column, the flow
and the value but no line. The " - Line: " part is added only to the reject
row's `errorMessage`, on the branch die on error does not take.

Reasoning: the reject row Talend builds is the row as far as it had been
parsed (a copy of the main row's fields), not the raw line of the file. The
Excel template shows the copy column by column (`#L616-L620`).

What v1 (the stand-in for Talend here) does: its delimited reader writes
"- Line: {line_num}" with `line_num = start + row_idx + 1`, the place of the
row among the rows pandas read, counted from 1, and only on the path that
checks rows one by one (field count, date check); the faster path writes
"Column 'x': <error>" with no line.
[`src/v1/engine/components/file/file_input_delimited.py#L772-L774`, `#L887`,
`#L911-L915`, `#L949-L953`, `#L969-L973`]

### 1.2 Apache Spark, and what Databricks adds

- Three parse modes for CSV and JSON. PERMISSIVE (the default): "when it
  meets a corrupted record, puts the malformed string into a field
  configured by columnNameOfCorruptRecord, and sets malformed fields to
  null. To keep corrupt records, an user can set a string type field named
  columnNameOfCorruptRecord in an user-defined schema. If a schema does not
  have the field, it drops corrupt records during parsing." DROPMALFORMED:
  "ignores the whole corrupted records." FAILFAST: "throws an exception when
  it meets corrupted records." [`spark:sql-data-sources-csv.html`, option
  `mode`; `spark:sql-data-sources-json.html`, option `mode`]
- For CSV, "A record with less/more tokens than schema is not a corrupted
  record to CSV." [`spark:sql-data-sources-csv.html`, option `mode`]
- Stated limit: "Note that Spark tries to parse only required columns in CSV
  under column pruning. Therefore, corrupt records can be different based on
  required set of fields." [same]
- Stated limit: "Since Spark 2.3, the queries from raw JSON/CSV files are
  disallowed when the referenced columns only include the internal corrupt
  record column ... Instead, you can cache or save the parsed results and
  then send the same query." [`spark:sql-migration-guide.html`]
- The error texts: MALFORMED_RECORD_IN_PARSING, "Malformed records are
  detected in record parsing: <badRecord>. Parse Mode: <failFastMode>.";
  under it CANNOT_PARSE_STRING_AS_DATATYPE, "Cannot parse the value
  <fieldValue> of the field <fieldName> as target spark data type
  <targetType> from the input type <inputType>."; FAILED_READ_FILE,
  "Encountered error while reading file <path>."; and for a cast in a later
  expression CAST_INVALID_INPUT, "The value <expression> of the type
  <sourceType> cannot be cast to <targetType> because it is malformed. ...
  Use try_cast to tolerate malformed input and return NULL instead." None
  of these templates has a place for a line or a row number.
  [`spark:sql-error-conditions.html`]
- Every file format has a `_metadata` struct with `file_path`, `file_name`,
  `file_size`, `file_block_start`, `file_block_length` and
  `file_modification_time`. The Parquet format adds `row_index`; a search of
  Spark's source on 2026-10-06 (default branch) found no other format that
  defines such a field. "NOTE: Extractors are lazy, invoked only if the
  query actually selects their column at runtime."
  [`sparksrc:sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/FileFormat.scala#L203-L279`;
  `sparksrc:sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/parquet/ParquetFileFormat.scala#L434-L447`]
- Databricks on the same column: it "is a hidden column, and is available
  for all input file formats. To include the _metadata column in the
  returned DataFrame, you must explicitly select it in the read query where
  you specify the source."
  [https://docs.databricks.com/aws/en/ingestion/file-metadata-column]
- Spark's row id is not a row number: "The generated ID is guaranteed to be
  monotonically increasing and unique, but not consecutive." "The function
  is non-deterministic because its result depends on partition IDs."
  [`spark:api/python/reference/pyspark.sql/api/pyspark.sql.functions.monotonically_increasing_id.html`]
- Databricks `badRecordsPath`: "the specified path records exceptions for
  bad records or files encountered during data loading." The exception file
  is JSON under `<path>/<time the reader was made>/bad_records/` and
  "contains the bad record, the path of the file containing the record, and
  the exception/reason message." Stated limits: "It is non-transactional and
  can lead to inconsistent results." "Transient errors are treated as
  failures." [https://docs.databricks.com/aws/en/ingestion/bad-records]

### 1.3 DuckDB

- By default the first error stops the read with a message of three blocks.
  The first: "CSV Error on Line: 5648 / Original Line: Pedro,The 90s / Error
  when converting column "birth_date". date field value out of range: "The
  90s", expected format is (DD-MM-YYYY)". The second lists possible
  solutions, the third the reader's options and whether each was detected
  or set. [`duck:data/csv/reading_faulty_csv_files.html`, "Anatomy of a CSV
  Error"]
- `ignore_errors`: "rows containing data that would otherwise cause the CSV
  parser to generate an error will be ignored." [same page, "Using the
  ignore_errors Option"]
- `store_rejects = true`: "any errors in the file will be skipped and stored
  in the default rejects temporary tables." There are two. `reject_scans`
  has one row per scan and file: scan_id, file_id, file_path, delimiter,
  quote, escape, newline_delimiter, skip_rows, has_header, columns,
  date_format, timestamp_format, user_arguments. `reject_errors` has one row
  per error: scan_id, file_id, `line` ("Line number, from the CSV File,
  where the error occurred."), `line_byte_position` ("Byte Position of the
  start of the line, where the error occurred."), `byte_position` ("Byte
  Position where the error occurred."), column_idx, column_name, error_type,
  `csv_line` ("The original CSV line."), error_message. "if a line has
  multiple errors, multiple entries will be stored for the same line, one
  for each error." [same page, "Retrieving Faulty CSV Lines", "Reject
  Scans", "Reject Errors", "Parameters"]
- `rejects_limit`: "Upper limit on the number of faulty records from a CSV
  file that will be recorded in the rejects table. 0 is used when no limit
  should be applied." [same page, "Parameters"]
- Stated limits: a line may be at most 2,097,152 bytes by default ("LINE
  SIZE OVER MAXIMUM"); and "the CSV Parser is affected by the projection
  pushdown optimization. Hence, if we were to select only the name column,
  both rows would be considered valid, as the casting error on the age would
  never occur." [same page, "Structural Errors" and "Using the ignore_errors
  Option"]
- What the line number costs, from the code. Every batch of the parallel
  read reports how many lines it held ("Object that holds information on how
  many lines each csv batch read"). An error whose earlier batches have not
  all reported is kept, not thrown ("We store this error, we can't throw it
  now, or we are ignoring it"). The line is the lines of all earlier batches
  plus the lines before the error in its own batch, counted from 1. When
  several errors are kept, the one on the lowest line is thrown.
  [`ducksrc:src/include/duckdb/execution/operator/csv_scanner/csv_error.hpp#L27-L28`;
  `ducksrc:src/execution/operator/csv_scanner/util/csv_error.cpp#L22-L36`,
  `#L61-L70`, `#L616-L636`]
- A `filename` argument "can be used to add an extra filename column to the
  result that indicates which row came from which file". `file_row_number`
  is an option of the Parquet reader; the name does not occur on the CSV,
  JSON and multiple-files pages.
  [`duck:data/multiple_files/overview.html`, "Filename";
  `duck:data/parquet/overview.html`; `duck:data/csv/overview.html`;
  `duck:data/json/loading_json.html`]
- Away from the CSV reader a failed cast names the value and nothing else
  ("Conversion Error: Could not convert string 'abc' to INT32"). The `TRY`
  expression "ensures that errors caused by the input rows in the child
  (scalar) expression result in NULL for those rows, instead of causing the
  query to throw an error"; it "cannot be used in combination with a
  volatile function, an aggregate function, or a scalar subquery."
  [`duck:sql/expressions/try.html`]

### 1.4 PostgreSQL COPY

- A failed COPY carries a context line: `COPY <table>, line <N>, column
  <name>: "<value>"`; for a missing value `... column <name>: null input`;
  for a fault of the whole line `COPY <table>, line <N>: "<line>"`.
  [`pgsrc:src/backend/commands/copyfrom.c#L254-L325`]
- The value or line shown is cut at 100 bytes and "..." is added: "Make sure
  we don't print an unreasonable amount of COPY data in a message."
  [same file, `#L327-L356`, `MAX_COPY_DATA_DISPLAY`]
- The line counter is raised for a line break inside a quoted field, and the
  code says of it: "Updating the line count for embedded CR and/or LF chars
  is necessarily a little fragile - this test is probably about the best we
  can do. (XXX it's arguable whether we should do this at all --- is
  cur_lineno a physical or logical count?)"
  [`pgsrc:src/backend/commands/copyfromparse.c#L1355-L1361`]
- `ON_ERROR`: "An error_action value of stop means fail the command, while
  ignore means discard the input row and continue with the next one. The
  default is stop." "The ignore option is applicable only for COPY FROM when
  the FORMAT is text or csv." It covers "an error converting a column's
  input value into its data type" only. [`pg:sql-copy.html`, ON_ERROR]
- "A NOTICE message containing the ignored row count is emitted at the end
  of the COPY FROM if at least one row was discarded. When LOG_VERBOSITY
  option is set to verbose, a NOTICE message containing the line of the
  input file and the column name whose input conversion has failed is
  emitted for each discarded row." [same, ON_ERROR and LOG_VERBOSITY]
- The per-row notice reads `skipping row due to data type incompatibility at
  line N for column "name": "value"`, the value cut the same way.
  [`pgsrc:src/backend/commands/copyfromparse.c#L1054-L1066`]
- `REJECT_LIMIT`: "Specifies the maximum number of errors tolerated ... If
  the input causes more errors than the specified value, the COPY command
  fails, even with ON_ERROR set to ignore." [`pg:sql-copy.html`,
  REJECT_LIMIT]
- Of the three options read (ON_ERROR, REJECT_LIMIT, LOG_VERBOSITY) none
  names a table or file that keeps the discarded rows; they are reported in
  messages. [`pg:sql-copy.html`, the three options]

### 1.5 Snowflake

- A load answers with one row per file: FILE, STATUS, ROWS_PARSED,
  ROWS_LOADED, ERROR_LIMIT, ERRORS_SEEN, FIRST_ERROR, FIRST_ERROR_LINE
  ("Line number of the first error"), FIRST_ERROR_CHARACTER ("Position of
  the first error character"), FIRST_ERROR_COLUMN_NAME.
  [`snow:sql-reference/sql/copy-into-table`, "Output"]
- `ON_ERROR` is one of CONTINUE, SKIP_FILE, SKIP_FILE_<num>,
  'SKIP_FILE_<num>%', ABORT_STATEMENT. Under CONTINUE "The COPY statement
  returns an error message for a maximum of one error found per data file
  ... To view all the errors in the data files, use the VALIDATION_MODE
  parameter or query the VALIDATE function." "The SKIP_FILE action buffers
  an entire file whether errors are found or not. For this reason, SKIP_FILE
  is slower than either CONTINUE or ABORT_STATEMENT." [same page, "ON_ERROR"]
- `VALIDATION_MODE = RETURN_ERRORS` loads nothing and "Returns all errors
  (parsing, conversion, etc.) across all files specified in the COPY
  statement." Its columns: ERROR, FILE, LINE, CHARACTER, BYTE_OFFSET,
  CATEGORY, CODE, SQL_STATE, COLUMN_NAME, ROW_NUMBER, ROW_START_LINE. The
  column is written with its table and its position, as in
  `"MYTABLE"["QUOTA":3]`. [same page, "VALIDATION_MODE" and the example
  "Validating staged files"]
- `VALIDATE(<table>, JOB_ID => '<query id>' or '_last')`: "Validates the
  files loaded in a past execution of the COPY INTO <table> command and
  returns all the errors encountered during the load, rather than just the
  first error." Stated limits: "The validation returns no results for COPY
  statements that specify ON_ERROR = ABORT_STATEMENT (default value)."
  "Validation fails if: SELECT statements are used to transform data during
  a COPY INTO <table> operation." It also fails when "The copy history
  metadata has expired", and files removed since the load "are reported as
  missing". [`snow:sql-reference/functions/validate`, "Usage notes"]
- Its result has the columns above and REJECTED_RECORD, the record as it
  stands in the file; the tutorial saves it with `CREATE OR REPLACE TABLE
  save_copy_errors AS SELECT * FROM TABLE(VALIDATE(...))`.
  [`snow:user-guide/tutorials/data-load-internal-tutorial`, the step that
  resolves load errors]
- Columns a query of staged files can ask for by name: METADATA$FILENAME,
  METADATA$FILE_ROW_NUMBER ("Row number for each record in the staged data
  file."), METADATA$FILE_CONTENT_KEY ("Checksum of the staged data file the
  current row belongs to."), METADATA$FILE_LAST_MODIFIED,
  METADATA$START_SCAN_TIME. [`snow:user-guide/querying-metadata`]
- Records that span lines and reading in parallel do not go together:
  "Snowflake supports parallel scanning of these CSV files when MULTI_LINE
  is set to FALSE, COMPRESSION is set to NONE, and ON_ERROR is set to
  ABORT_STATEMENT or CONTINUE." [`snow:sql-reference/sql/copy-into-table`,
  usage note on large uncompressed CSV files]

### 1.6 Amazon Redshift

- Every load error is a row of the system table STL_LOAD_ERRORS: `filename`
  character(256) ("Complete path to the input file for the load."),
  `line_number` ("Line number in the load file with the error. For COPY from
  JSON, the line number of the last line of the JSON object with the
  error."), `colname` character(127), `type`, `col_length`, `position`
  ("Position of the error in the field."), `raw_line` character(1024) ("Raw
  load data that contains the error. Multibyte characters in the load data
  are replaced with a period."), `raw_field_value` char(1024) ("The
  pre-parsing value for the field "colname" that lead to the parsing
  error."), `err_code`, `err_reason` character(100).
  [`redshift:r_STL_LOAD_ERRORS.html`, "Table columns"]
- When a file is split to be loaded in parallel: `is_partial` says so, and
  `start_offset` is "the offset value of the split (in bytes). If the line
  number in the file is unknown, the line number is -1." [same]
- Who may read it: "STL_LOAD_ERRORS is visible to all users. Superusers can
  see all rows; regular users can see only their own data." [same]
- How long it is kept: "STL system views retain seven days of log history."
  [`redshift:c_intro_STL_tables.html`]
- `MAXERROR`: "If the load returns the error_count number of errors or
  greater, the load fails ... The MAXERROR default value is 0 and the limit
  is 100000. The actual number of errors reported might be greater than the
  specified MAXERROR because of the parallel nature of Amazon Redshift."
  [`redshift:copy-parameters-data-load.html`, MAXERROR]
- `NOLOAD`: "Checks the validity of the data file without actually loading
  the data ... much faster than loading the data because it only parses the
  files." [same page, NOLOAD]

### 1.7 BigQuery

- "If there's a problem parsing your CSV files, then the load job's errors
  resource is populated with the error details. Generally, these errors
  identify the start of the problematic line with a byte offset." The
  example reads "Error detected while parsing row starting at position:
  1405. Error: Data between close quote character (") and field separator.
  File: gs://my-bucket/mytable.csv", and the page shows how to print the
  bytes from 1405 on. [`bq:loading-data-cloud-storage-csv`, "Troubleshoot
  parsing errors"]
- For a compressed file "the reported byte offset refers to the location in
  the uncompressed file." [same, "Compressed CSV files"]
- `--max_bad_records`: "the maximum number of bad records allowed before the
  entire job fails. The default value is 0. At most, five errors of any type
  are returned regardless of the --max_bad_records value." [same page, the
  `bq load` flags]
- The job's `status.errors[]` holds "The first errors encountered during the
  running of the job. The final message includes the number of errors that
  caused the process to stop." Each entry has `reason`, `location`
  ("Specifies where the error occurred, if present."), `message`.
  [`bq:reference/rest/v2/Job`, JobStatus; `bq:reference/rest/v2/ErrorProto`]
- A file with quoted line breaks cannot be split: "Input CSV files are not
  splittable and at least one of the files is larger than the maximum
  allowed size." [`bq:loading-data-cloud-storage-csv`, "Troubleshoot quota
  errors"]

### 1.8 pandas and pyarrow

- pandas `on_bad_lines`: "Specifies what to do upon encountering a bad line
  (a line with too many fields)": `'error'`, `'warn'` ("raise a warning when
  a bad line is encountered and skip that line"), `'skip'`, or a callable
  that is handed the fields of the bad line as a list of text, with
  `engine='python'`. [`venv:pandas/io/parsers/readers.py#L697-L723`;
  https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html]
- The message is built as `f"Expected {col_len} fields in line {row_num +
  1}, saw {actual_len}"`, and a skipped line is warned as `f"Skipping line
  {row_num}: {msg}\n"`.
  [`venv:pandas/io/parsers/python_parser.py#L963-L972`, `#L1224-L1227`]
- pyarrow's CSV reader hands a handler one `InvalidRow` for "each CSV row
  that fails parsing (because of a mismatching number of columns)":
  `expected_columns`, `actual_columns`, `number` ("The physical row number
  if known, otherwise None."), `text` ("The contents of the row."). The code
  beside it: "A negative row number means undetermined (because of parallel
  reading)". [`venv:pyarrow/_csv.pyx#L49-L75`, `#L377-L381`]

### 1.9 SQL Server: BULK INSERT and Integration Services

- `ERRORFILE` "Specifies the file used to collect rows that have formatting
  errors and can't be converted to an OLE DB rowset. These rows are copied
  into this error file from the data file "as is."" "An error occurs if the
  file already exists. Additionally, a control file with the extension
  .ERROR.txt is created, which references each row in the error file and
  provides error diagnostics."
  [https://learn.microsoft.com/en-us/sql/t-sql/statements/bulk-insert-transact-sql?view=sql-server-ver17,
  ERRORFILE]
- `MAXERRORS`: "Each row that can't be imported by the bulk-import operation
  is ignored and counted as one error. If max_errors isn't specified, the
  default is 10." [same page, MAXERRORS]
- Integration Services, an ETL tool of Talend's kind, lets each column be
  set to Fail Component, Ignore Failure or Redirect Row. "In addition to the
  data columns, the error output includes the ErrorCode and ErrorColumn
  columns. The ErrorCode column identifies the error and the ErrorColumn
  contains the lineage identifier of the error column." "Under some
  circumstances, the value of the ErrorColumn column is set to zero. This
  occurs when the error condition affects the entire row instead of a single
  column." No row number is added.
  [https://learn.microsoft.com/en-us/sql/integration-services/data-flow/error-handling-in-data?view=sql-server-ver17]

### 1.10 dbt and Great Expectations (checks on data already loaded)

- dbt: "Data tests return a set of failing records." "Data tests return one
  row for each failure. The columns in your test's SQL select statement are
  the columns you see when you debug failures."
  [https://docs.getdbt.com/docs/build/data-tests]
- dbt `store_failures`: "saves all records (up to limit) that failed the
  test. Failures are saved in a new table with the name of the test. A
  test's results will always replace previous failures for the same test,
  even if that test results in no failures. By default, store_failures uses
  a schema named {{ profile.schema }}_dbt_test__audit".
  [https://docs.getdbt.com/reference/resource-configs/store_failures]
- dbt `limit`: "Limit the number of failures that will be returned by a test
  query. We recommend using this config when working with large datasets and
  storing failures in the database."
  [https://docs.getdbt.com/reference/resource-configs/limit]
- Great Expectations has four levels of detail, BOOLEAN_ONLY, BASIC, SUMMARY
  (the default) and COMPLETE, and these switches:
  `unexpected_index_column_names` ("Takes a list to define the column(s)
  that will be used to identify unexpected results returned. For example,
  primary key (PK) column(s) or other columns with unique identifiers.");
  `partial_unexpected_count` (how many failing values are listed; "Up to 20
  values by default"); `include_unexpected_rows` ("returns up to 200 entire
  rows that violate the Expectation (default is False)");
  `exclude_unexpected_values` ("Setting this value to True suppresses values
  from the output to only have indices (default is False)"); and
  `unexpected_index_query` ("A query that can be used to retrieve all
  unexpected values (SQL and Spark), or the full list of unexpected indices
  (Pandas).").
  [https://docs.greatexpectations.io/docs/core/trigger_actions_based_on_results/choose_a_result_format/]

### 1.11 Kafka Connect (a record that is not in a file)

- `errors.tolerance`: "'none' is the default value and signals that any
  error will result in an immediate connector task failure; 'all' changes
  the behavior to skip over problematic records."
  [`kafka:ConnectorConfig.java#L192-L193`]
- `errors.log.include.messages`: "Whether to include in the log the Connect
  record that resulted in a failure. For sink records, the topic, partition,
  offset, and timestamp will be logged ... This is 'false' by default, which
  will prevent record keys, values, and headers from being written to log
  files." [`kafka:ConnectorConfig.java#L204-L208`]
- A failed record can be sent to a topic of its own with headers that say
  where it came from and what failed: `__connect.errors.` followed by
  `topic`, `partition`, `offset`, `connector.name`, `task.id`, `stage`,
  `class.name`, `exception.class.name`, `exception.message`,
  `exception.stacktrace`. The headers are off unless asked for.
  [`kafka:SinkConnectorConfig.java#L58-L73`;
  `kafka:errors/DeadLetterQueueReporter.java#L59-L69`]

### 1.12 What they have in common

Reasoning: every location above is produced by the code that reads the
record. The cast errors read for the engines that also run expressions
(Spark's CAST_INVALID_INPUT, DuckDB's "Conversion Error", Polars' cast
failure in section 2.2) name the value and the types and no row. What those
engines offer for a later step is a way not to raise (`try_cast`, `TRY`, a
non-strict cast), after which the failing rows are ordinary rows that a
filter can pick, with whatever columns they carry. The row-by-row tools
hand the failing row itself to an error output (Talend's ErrorReject,
Integration Services' error output), with its columns and no position.

Reasoning: the readers that work in parallel all meet the same wall, and
each says so in its own words. DuckDB waits until every earlier batch has
counted its lines. Redshift writes -1 for the line and gives the byte
offset of the split. pyarrow gives no row number. BigQuery and Polars give
a byte position. Snowflake reads in parallel only when no record spans
lines. A true line number has a cost, and four of the six do not pay it.

Reasoning: two families of "whole row" exist. Loaders keep the raw record
as one piece of text (Spark, DuckDB, Snowflake, Redshift up to 1,024
characters, SQL Server, Databricks). Row-by-row ETL tools keep the parsed
columns plus two error columns (Talend, Integration Services). v2's reject
output is of the second family, with the fields as text.

---

## 2. Polars

### 2.1 Releases after 1.44.2

- [2026-10-06] After `py-1.44.2` (2026-09-09) the releases are
  `py-2.0.0-rc.2` (2026-09-20, pre-release) and `py-2.0.0` (2026-10-06);
  `py-2.0.0-rc.1` (2026-09-02) came before 1.44.2. There is no later 1.x
  release. [https://github.com/pola-rs/polars/releases]
- [2.0.0] The release notes of py-2.0.0 were read in full, those of the two
  release candidates were searched for error, row, line, offset, position,
  cast, parse, strict and reject. No entry says that a failed parse or cast
  now reports a row, a line or a file.
  [https://github.com/pola-rs/polars/releases/tag/py-2.0.0;
  https://github.com/pola-rs/polars/releases/tag/py-2.0.0-rc.2;
  https://github.com/pola-rs/polars/releases/tag/py-2.0.0-rc.1]
- [2.0.0] The nearest entry is "Raise on ragged rows instead of silently
  dropping values (#29658)". It is about building a frame from Python rows,
  not about files, and its new error does name a row: "ShapeError: row at
  index 1 has length 4 (expected 1)". [#29658, description]
- [2.0.0] The cast failure message is built as in 1.44.2 (same text, same
  arguments), the CSV message still gives a byte offset, and the streaming
  CSV reader still passes 0 as the offset of a chunk.
  [`pl20:crates/polars-core/src/utils/series.rs#L67-L125`;
  `pl20:crates/polars-io/src/csv/read/parser.rs#L1169-L1188`;
  `pl20:crates/polars-stream/src/nodes/io_sources/csv/chunk_reader.rs#L83`]
- [main a3e0097fd1] The cast failure message is unchanged on `main`.
  [https://github.com/pola-rs/polars/blob/a3e0097fd1/crates/polars-core/src/utils/series.rs#L67-L125]
- [1.44.2 to 2.0.0] `scan_csv` loses `cache`, `rechunk`, `retries` and
  `file_cache_ttl`, gains an unstable `extra_columns` ("Configuration for
  behavior when extra columns outside of the defined schema are encountered
  in the data"), and keeps `row_index_name`, `row_index_offset`,
  `ignore_errors` and `include_file_paths` with the same words. Nothing for
  a source line number was added. `scan_lines` is unchanged and still
  marked unstable. [`pl44:py-polars/src/polars/io/csv/functions.py` against
  `pl20:py-polars/src/polars/io/csv/functions.py`, `def scan_csv`;
  `pl20:py-polars/src/polars/io/lines.py`]

### 2.2 What a Polars error says today

- [1.44.2] A failed cast: "conversion from `{}` to `{}` failed in column
  '{}' for {} out of {} values: {}{}", filled with the two types, the name
  of the column being cast, the number of failures, the length of the
  column handed to the cast, and a list of at most ten failing values; with
  more than ten, "Did not show all failed cases as there were too many." The
  positions of the failures are worked out (`idxs`) and used only to pick
  those values. [`pl44:crates/polars-core/src/utils/series.rs#L50-L94`]
- Reasoning: "1 out of 1065 values" in the ticket's example is therefore
  the size of the batch the streaming engine was casting, not of the file.
- [1.44.2] A field the CSV reader cannot parse: "could not parse `{}` as
  dtype `{}` at column '{}' (column number {})", then "The current offset in
  the file is {} bytes.", then advice, then the original error. The field is
  put in the text whole, twice.
  [`pl44:crates/polars-io/src/csv/read/parser.rs#L1165-L1190`]
- [1.44.2] That offset is the offset of the piece being parsed plus the
  place of the field in it. The streaming CSV reader passes 0 for the
  piece's offset, so under the streaming engine the number is counted from
  the start of a chunk.
  [`pl44:crates/polars-io/src/csv/read/read_impl.rs#L548-L598`;
  `pl44:crates/polars-stream/src/nodes/io_sources/csv/chunk_reader.rs#L77-L89`]
- [1.44.2, observed] `note-csv` saw the same: 379,440 bytes for a failure on
  the last line of a 9.5 MB file read with `scan_csv`. [`note-csv`, 5c]
- [1.44.2] The streaming reader does know where each chunk starts in rows
  ("Position of this chunk relative to the start of the file according to
  CountLines"), hands that to the chunk reader, and uses it in one message
  only: "CSV malformed: expected {} rows, actual {} rows, in chunk starting
  at row_offset {}, length {}".
  [`pl44:crates/polars-stream/src/nodes/io_sources/csv/line_batch_source.rs#L23-L24`;
  `pl44:crates/polars-stream/src/nodes/io_sources/csv/mod.rs#L428-L433`;
  `pl44:crates/polars-stream/src/nodes/io_sources/csv/chunk_reader.rs#L94-L107`]
- [1.44.2] A quoted field that never closes: "invalid csv file ... Field
  `{}` is not properly escaped.", again with the whole field. An open report
  says the field can then be the rest of the file and floods the terminal;
  no maintainer has answered it.
  [`pl44:crates/polars-io/src/csv/read/builder.rs#L220`; #23840, open,
  labelled "needs triage"]
- [1.44.2] Line-by-line JSON: "error parsing line: {}" and "cannot parse
  '{}' ({}) as {:?}", the value and its type; no line number and no column
  name. [`pl44:crates/polars-io/src/ndjson/core.rs#L186`;
  `pl44:crates/polars-io/src/ndjson/buffer.rs#L177`]

### 2.3 What the tracker holds

- #18363, "read_csv failure: provide line number not just column and bytes
  on parse failure": closed on 2024-08-26 after this answer from a
  maintainer (alexander-beedie, collaborator): "Parallelising the reads (as
  we do) means that the code raising the error doesn't actually _know_ what
  the line number is - in order to work it out it would have to keep track
  of every chunk that has already been processed _and_ every chunk
  currently being processed, wait for any/all extant chunks to successfully
  finish parsing, and then synchronise this information. Knowing the byte
  offset is directly tied to how the chunks are distributed into the
  processing pool, so that information _is_ available." [#18363]
- #28051, "Include source file line numbers when reading CSVs with
  `read_csv`, `scan_csv`": open since 2026-06-23, labelled enhancement, no
  comment. It asks for a column holding each row's line in the file, since
  "after polars skips the header and comments, we have no way of mapping the
  row index back to the original file." [#28051]
- #10120, "convert/cast/parse: improve error messages and improve api":
  open since 2023-07-27; asks for one wording for every conversion error
  with the count, the column and the values. No maintainer has taken it up
  in its two comments. [#10120]
- #8145, on `ignore_errors`: open. Two maintainers, 2023-04-11. ritchie46
  (member): "If you want more opinionated the dtype conversion you can cast
  them later. We shouldn't push compute into the IO readers." ghuls
  (collaborator): "It might be better to get rid of `ignore_errors`
  altogether as I haven't found much use of it, but is more likely to
  corrupt your data." [#8145]
- #13768: open, priority low. `ignore_errors=True` does not get past a line
  that is not JSON at all; the documented meaning is "Return `Null` if
  parsing fails because of schema mismatches." [#13768;
  `venv:polars/io/ndjson.py#L284-L285`]
- #27956: an open pull request from outside the team, "Add field name as
  error context for json decode methods"; not merged. [#27956]
- #15096: open since 2024-03-16, asks for a column saying which side each
  joined row came from; no maintainer comment. [#15096]

### 2.4 What Polars offers to build on (1.44.2)

- A row number at the scan. `scan_csv`, `scan_ndjson` and `scan_lines` take
  `row_index_name` ("If not None, this will insert a row index column with
  the given name into the DataFrame.") and `row_index_offset`.
  [`venv:polars/io/csv/functions.py#L1283-L1287`;
  `venv:polars/io/ndjson.py#L279-L283`; `venv:polars/io/lines.py#L168-L172`]
- [observed] Put right after a CSV scan, the number is made inside the scan
  itself and counts the data rows after the skipped rows and the header; a
  blank line is a row and is counted. [`note-csv`, 5f and section 4, "Blank
  lines"]
- `LazyFrame.with_row_index`: "Using this function can have a negative
  effect on query performance. This may, for instance, block predicate
  pushdown optimization." "The resulting column does not have any special
  properties. It is a regular column of type `UInt32` (or `UInt64` in
  `polars[rt64]`)." [`venv:polars/lazyframe/frame.py#L7483-L7504`]
- The installed runtime is the 32-bit one (`polars_runtime_32`), and its
  limit is spelled out in the error it raises: "{} produces {} rows which is
  more than maximum allowed pow(2, 32)-1 rows; consider compiling with
  bigidx feature (pip install polars[rt64])". The streaming CSV reader
  raises it for a file with more rows than that.
  [`pl44:crates/polars-error/src/lib.rs#L515-L522`;
  `pl44:crates/polars-stream/src/nodes/io_sources/csv/mod.rs#L492-L493`]
- `pl.row_index()` exists since 1.32.0 and is marked unstable.
  [`venv:polars/functions/lazy.py#L2825-L2839`]
- A file-name column: `include_file_paths`, "Include the path of the source
  file(s) as a column with this name", on `scan_csv`, `scan_ndjson` and
  `scan_lines`. [`venv:polars/io/csv/functions.py#L1343-L1344`;
  `venv:polars/io/ndjson.py#L320-L321`; `venv:polars/io/lines.py#L197-L198`]
- `scan_lines` (one text column, one row a line) is marked unstable: "It may
  be changed at any point without it being considered a breaking change."
  v2's by-line reader is built on it. [`venv:polars/io/lines.py#L154-L156`;
  `v2:components/file/file_input_delimited.py#L267`]
- Not raising. `ignore_errors` on a CSV scan: "Try to keep reading lines if
  some lines yield errors. First try `infer_schema=False` to read all
  columns as `pl.String` to check which values might cause an issue." A
  non-strict cast gives a missing value where a strict one raises. Neither
  says which rows it touched. [`venv:polars/io/csv/functions.py#L1239-L1242`;
  `note-run`, 6.3]
- A strict cast raises "on rows after predicates are pushed down": whether a
  bad value fails a job depends on what the plan filters first. [`note-run`,
  6.3, quoting the `Expr.cast` docstring]
- Rows in batches. `LazyFrame.sink_batches` calls a function "for every
  ready batch" and stops early when it returns True; `collect_batches`
  returns the batches one by one. Both are marked unstable and both say
  "This method is much slower than native sinks. Only use it if you cannot
  implement your logic otherwise."
  [`venv:polars/lazyframe/frame.py#L4264-L4289`, `#L4333-L4366`]

### 2.5 What v2 does today

- One pass per subjob. When it fails and the readers were on the fast path,
  the subjob is read again with the tolerant reader. Otherwise, if the pass
  took at most 60 seconds, each component's output is computed again in
  order until one fails, and that component is blamed; the reason is Polars'
  text with its advice and its plan cut off, in ASCII, with no limit on
  length. [`v2:engine/runner.py#L40`, `#L490-L525`, `#L580-L593`,
  `#L731-L742`]
- The delimited reader reads every field as text, parses it without
  raising, and flags a row whose text was there and could not be read. The
  flagged rows are the reject output, each field as text with `errorCode`
  and `errorMessage`; with `die_on_error` a check counts them and takes the
  first message: "Schema/coercion failed for N row(s); first error: ...".
  [`v2:components/file/file_input_delimited.py#L304-L347`, `#L401-L403`;
  `v2:types.py#L117-L149`]
- It numbers rows only when it splits the lines itself, after blank lines
  and empty rows are dropped, and uses the number in one message: "Field
  count mismatch: expected W, got F - Line: N". A value that cannot be read
  gets "Column 'x': could not convert string to ...: 'value'", with no
  number. [`v2:components/file/file_input_delimited.py#L187-L189`,
  `#L360-L370`, `#L388-L398`]
- Two more checks of the engine's own run in the pass and take a count and
  a first value: a missing value in a column that may not hold one, and text
  a map output cannot read as its declared type.
  [`v2:engine/runner.py#L445-L471`, `#L666-L671`;
  `v2:components/transform/map_outputs.py#L148-L168`]
- A map expression that fails on a row is not one of them: "An expression
  that fails on a row fails the component, whatever `die_on_error` says ...
  Rows are not sent to a catch output." [`docs/v2/README.md`, "Map"]
- The Excel reader makes a row number for each sheet and knows the sheet's
  name; both are dropped before its output, and `<id>_CURRENT_SHEET` holds
  the last sheet read. "cells that cannot be read go missing and are never
  rejected." [`v2:components/file/file_input_excel.py#L199`, `#L245-L248`,
  `#L275`; `docs/v2/README.md`, "Excel input"]
- A failure reaches three places: an ERROR line `[job] failed at <id>:
  <reason>`, the summary keys `error`, `failed_component` and `failures`,
  and the result object. [`v2:engine/runner.py#L286-L291`;
  `v2:cli.py#L133-L140`]
- No `<id>_ERROR_MESSAGE` is put in globalMap: the text `ERROR_MESSAGE`
  occurs nowhere in `src/v2`, and the README says so for the join. [a search
  of `src/v2` for `ERROR_MESSAGE` at commit `99344233` finds nothing;
  `docs/v2/README.md`, "Join"]
- A schema column has a `key` flag ("Whether the column is part of the
  key."). The converter writes it, v2 loads it, and no v2 component reads
  it. [`src/converters/talend_to_v1/components/base.py#L181`;
  `v2:job/model.py#L35-L44`; `v2:job/loader.py#L115`]

---

## 3. Tag or search

### 3.1 What the other engines' pages say about row identity

- Where a position exists it is asked for at the read and belongs to the
  reader: Spark's `_metadata` (in Databricks' words, "you must explicitly
  select it in the read query where you specify the source"), Snowflake's
  METADATA$ columns ("Metadata columns can only be queried by name"),
  DuckDB's `filename`, Polars' `row_index_name`. [sections 1.2, 1.3, 1.5,
  2.4]
- Snowflake's own way of listing every error stops working once the load
  transforms the data: "Validation fails if: SELECT statements are used to
  transform data during a COPY INTO <table> operation."
  [`snow:sql-reference/functions/validate`, "Usage notes"]
- Which rows fail depends on the plan, in three engines' own words: DuckDB
  ("the casting error on the age would never occur"), Spark ("corrupt
  records can be different based on required set of fields"), Polars
  ("Raise if cast is invalid on rows after predicates are pushed down"). v2
  says the same of itself: "An output column nothing in the job reads is
  never worked out, so an expression there that would fail on a row does
  not fail the job." [sections 1.2, 1.3, 2.4; `docs/v2/README.md`, "Map"]
- The one page found that speaks of "row-level lineage" is Delta Lake's row
  tracking, and it means a row of one stored table: "Row IDs provide rows
  with an identifier that is unique within the table. A row keeps the same
  ID whenever it is modified using a MERGE or UPDATE statement." The ids
  live in "hidden metadata columns in the data files", "may increase the
  size of the table", and "must be manually selected".
  [https://docs.delta.io/delta-row-tracking/]
- The data-quality tools identify a failing row by its own values, not by a
  position: Great Expectations by the columns the user lists in
  `unexpected_index_column_names`, dbt by "The columns in your test's SQL
  select statement". [section 1.10]
- Nothing was found, in any page or file read for section 1, about carrying
  a source position through a join or an aggregate. [my reading of the
  sources of section 1; see "Not verified"]

### 3.2 Tag: what it costs in principle

- Measured already: numbering the rows of 1,000,000 by 45 while reading
  took 0.15 s with and without. [ticket 37, "What is known"]
- Reasoning: the number costs 4 bytes a row on the installed runtime
  (UInt32, section 2.4) wherever rows are held: a sort, the lookup side of
  a join, a group-by, rows handed to user Python. On a pass that only
  streams, it is one more column among the forty-five.
- Reasoning: Polars leaves out a column nothing reads, so a carried number
  costs only on the plans that end in something that uses it: a reject
  output, a check. The plan that writes the main output does not pay unless
  the number is written.
- Reasoning: the real cost is in the components. Every place that lists
  columns by name has to decide about the hidden one, and several places
  take every column there is (3.3). A hidden column that reaches an output
  file changes the file, and then v2 no longer writes what v1 writes.
- Reasoning: a number alone is not an identity once two inputs meet. It
  needs the input beside it (which reader, which file, which sheet).
- Reasoning: a tag does not make Polars name the row. Its messages print
  the failing values and nothing else of the row (2.2). A tag helps where v2
  detects the row itself, and it turns a later search into one filter.

### 3.3 What happens to a carried number, operation by operation

What v2 builds is sourced; the right-hand column is reasoning.

| Operation | What v2 builds | Reasoning: a carried number |
|---|---|---|
| Filter (filter rows, unique row, a reader's main and reject) | a flag column, two filters, every column kept [`v2:components/transform/filter_rows.py#L138`; `v2:components/aggregate/unique_row.py#L100`] | survives; each row keeps its own |
| Sort | `frame.sort(..., maintain_order=True)` [`v2:components/transform/sort_row.py#L76`] | survives; the order changes, the number does not |
| Matching the declared schema | "Declared columns come first, in declared order; other columns follow" [`v2:types.py#L301`, `#L342-L349`] | survives, and so reaches whatever comes next |
| File output | writes every column of the frame it is handed [`v2:components/file/file_output_delimited.py#L121-L127`] | would be written to the file unless dropped first |
| Log row | prints every column [`v2:components/transform/log_row.py#L77`] | would be printed unless dropped first |
| Filter columns | `frame.select(kept)`, the declared columns [`v2:components/transform/filter_columns.py#L41`] | dropped unless added to the list |
| Map | each output selects its declared columns; a lookup is joined on the left, and a lookup that may match several rows repeats the main row [`v2:components/transform/map_outputs.py#L147`; `v2:components/transform/map_joins.py#L86-L89`] | dropped unless added; one main row can become several rows with the same number; the lookup's rows have numbers of their own |
| Join | the lookup is cut to one row a key, joined on the left, and the output lists the main columns and the fetched ones [`v2:components/transform/join.py#L86-L102`] | the main row's number survives if it is in the list; the lookup's is not fetched |
| Unite | `pl.concat(prepared, how="diagonal_relaxed")` [`v2:components/transform/unite.py#L48`] | survives, but two inputs both have a row 7: the number needs its input beside it |
| Aggregate | `group_by(keys, maintain_order=True).agg(...)`, then the group columns and the results [`v2:components/aggregate/aggregate_row.py#L196-L197`] | lost: many rows become one; at most a summary can be kept (the lowest number, how many) |
| Python dataframe | the code is handed every column as a pandas frame, and the output is what the code leaves [`v2:components/transform/python_dataframe.py#L117`, `#L147-L153`, `#L235`] | visible to user code; survives only if the code keeps the column and the rows; a frame the code builds has none |

### 3.4 Search: what it costs in principle

- Measured already: rerunning the whole job on halves found line 654,322 of
  1,000,000 in 20 runs and 50 s; rerunning only the failing part was not
  measured. [ticket 37, "What is known"]
- Reasoning: halving needs about log2(rows) runs, 20 for a million and 30
  for a thousand million. A text file has no index, so a run that starts at
  row k still has to find k line ends first; the later runs are cheaper in
  parsing but not free.
- Reasoning: a search costs nothing on a job that succeeds, which is the
  case the performance rule protects. It costs on the job that failed, and
  v2 already spends there: the search for the component at fault, which is
  skipped after a pass of more than 60 seconds (2.5).
- Reasoning: a search reads the input a second time. It finds nothing if
  the file changed in between, and it is not possible where a component
  already acted on rows; v2 knows which subjobs those are, because it uses
  the same test before it reads a file twice (`v2:engine/runner.py#L297-L336`).
- What the loaders document is not halving but a second pass that only
  checks: Snowflake's `VALIDATION_MODE` and `VALIDATE` ("returns all the
  errors encountered during the load, rather than just the first error"),
  Redshift's `NOLOAD` ("much faster than loading the data because it only
  parses the files"). [sections 1.5, 1.6]
- Reasoning: three ways to search with fewer runs than halving, none tried.
  (a) Rerun only the blamed component's part of the plan. (b) One pass over
  the blamed component's input in batches, with a row number put on at the
  reader, the component's work done batch by batch, and the halving done in
  memory inside the one batch that fails. (c) One pass that filters the
  blamed component's input on the bad values Polars printed, where the
  column they came from is an input column.

### 3.5 Between the two: failures as data

- The engines that run expressions each have a form that does not raise:
  Spark's `try_cast` ("to tolerate malformed input and return NULL
  instead"), DuckDB's `TRY` and `TRY_CAST`, Polars' `strict=False`.
  [sections 1.2, 1.3, 2.4]
- v2's readers already work this way: parse without raising, then flag the
  row whose text was there and gave no value. [`v2:types.py#L117-L149`]
- Reasoning: if every operation that can fail on a row were built that way,
  the failing rows would be known in the first pass, as flagged rows, and a
  carried number would say where they came from. The price is in the
  expression translator, which would have to know every operation that can
  fail and build a flag for each. See option D.

---

## 4. What "where" means for each kind of input

### 4.1 A text file: a record is not always a line

- The CSV format allows a line break inside a field: "Fields containing
  line breaks (CRLF), double quotes, and commas should be enclosed in
  double-quotes." [`rfc4180`, section 2, rule 6]
- Snowflake answers with three numbers, ROW_NUMBER, ROW_START_LINE and LINE,
  and two finer ones, CHARACTER and BYTE_OFFSET. [section 1.5]
- DuckDB gives the line, the byte position of the start of that line and the
  byte position of the error. [section 1.3]
- PostgreSQL counts the lines inside a quoted field as lines and doubts the
  choice in its own code ("is cur_lineno a physical or logical count?").
  [section 1.4]
- Redshift names the last line of a JSON object, and -1 with a byte offset
  when it does not know the line. [section 1.6]
- BigQuery gives the byte position where the row starts, in the
  uncompressed data. [section 1.7]
- Talend and v1 write "Line" for a count of rows. [section 1.1]
- The W3C model for CSV has both numbers for a row and says why. "number -
  the position of the row amongst the rows for the table, starting from 1."
  "source number - the position of the row in the original url of the
  table, starting from 1, or null." A comment prefix or skipped blank rows
  "may mean that the source numbers of rows are different from their
  numbers"; header rows or skipped rows "will mean that the source numbers
  of rows will be different from their numbers". The source number is there
  so that a reference into the file can be rebuilt: "This enables
  implementations to retain provenance between the table model and the
  original file." The parsing steps raise the source number once for each
  row read, not for each line.
  [https://www.w3.org/TR/tabular-data-model/ (W3C Recommendation, 17
  December 2015), sections 4.4 "Rows", 8 "Parsing Tabular Data" and 8.2.1
  "Simple Example"]

What bears on this in v2:

- A file that is not UTF-8 and holds more than ASCII is read through a
  UTF-8 copy. [`docs/v2/README.md`, "Running a job"]
- Reasoning: a byte position in that copy is not a byte position in the
  file the support person opens. Record numbers, line numbers and character
  counts are the same in both.
- Header rows, a footer, a limit and dropped blank or empty rows all sit
  between the file and the rows a reader hands on.
  [`v2:components/file/file_input_delimited.py#L163-L193`, `#L227-L291`]
- Reasoning: for a file read without enclosures a record is a line, and the
  line is the scan's row number plus the header rows plus one, as long as
  the number is taken before any row is dropped (blank lines are rows to
  the scan, 2.4). With `csv_option` a record can span lines; Polars gives
  the record's number only, and the line has to be found another way.

### 4.2 A workbook: a sheet and a row, or a cell

- Excel's own notation: "By default, Excel uses the A1 reference style,
  which refers to columns with letters (A through XFD, for a total of 16,384
  columns) and refers to rows with numbers (1 through 1,048,576) ... B2
  refers to the cell at the intersection of column B and row 2." "The
  exclamation point (!) separates the worksheet reference from the cell
  range reference".
  [https://support.microsoft.com/en-us/office/overview-of-formulas-in-excel-ecfdc708-9162-49e8-b993-c311f47ca173,
  "The A1 reference style"]
- Talend's Excel reader names a row count, the column's name and the
  sheet's column number, and no sheet. [section 1.1]
- The library v2 reads workbooks with can list the cells it could not read:
  `to_arrow_with_errors` "Stores the positions of any values that cannot be
  parsed as the specified type and were therefore converted to None", each
  as a `CellError` with `position`, `row_offset`, `offset_position` and
  `detail`. It needs pyarrow. [`venv:fastexcel/__init__.py#L110-L125`;
  `venv:fastexcel/_fastexcel.pyi#L70-L84`]
- The same library on skipped rows: "row indices are relative to data rows,
  not the sheet!", and `skip_rows=None` with no header row "skips empty rows
  at beginning". v2 passes `header_row=None, skip_rows=0`.
  [`venv:fastexcel/__init__.py#L352-L370`;
  `v2:components/file/file_input_excel.py#L269-L272`]
- Reasoning: with those two settings the place of a row in the frame should
  be its row in the sheet less one, which would make "sheet name, row
  number" exact. That is read from the docstring, not tried.

### 4.3 JSON and XML: a record is a place in a tree

- JSON Pointer "defines a string syntax for identifying a specific value
  within a JavaScript Object Notation (JSON) document": tokens after `/`, an
  array element by "the zero-based index", `~0` and `~1` for `~` and `/`
  inside a name, the empty text for the whole document. [`rfc6901`, abstract
  and sections 3 to 5]
- "XPath is a language for addressing parts of an XML document";
  `/doc/chapter[5]/section[2]` "selects the second section of the fifth
  chapter of the doc". Positions count from 1.
  [https://www.w3.org/TR/xpath-10/ (W3C Recommendation, 16 November 1999),
  abstract and section 2.5]
- Talend's JSON and XML readers name the record by the same row count as
  its text readers. [section 1.1]
- Redshift names "the line number of the last line of the JSON object with
  the error". Spark keeps the whole malformed text. Polars' line-by-line
  JSON error gives the value and no place. [sections 1.6, 1.2, 2.2]
- A record that is not in a file has coordinates of its own kind: Kafka
  Connect names it by topic, partition and offset. [section 1.11]

### 4.4 Published ways of naming a location

| Standard | What it names | Counted from | Status |
|---|---|---|---|
| RFC 5147 | a position or a range of lines or characters in a plain text: `#line=10,20` ("identifies lines 11 to 20"), `#char=100`; optional `length=` and `md5=` "to detect changes in the resource" | 0 (positions lie between lines) | IETF Standards Track, April 2008 [`rfc5147`, sections 2, 2.3 and 5] |
| RFC 7111 | a record, a column or a field of a CSV: `#row=4`, `#col=2`, `#cell=4,1` | 1; in its example the header is row 1 | IETF Informational, January 2014 [`rfc7111`, sections 2 and 4.2] |
| W3C tabular data model | a row's `number` and its `source number`; the same pair for columns | 1 | W3C Recommendation, 2015 [link in 4.1] |
| RFC 6901 | a value in a JSON document: `/foo/0` | 0 for array elements | IETF Standards Track, April 2013 [`rfc6901`, sections 3 to 5] |
| XPath 1.0 | a node in an XML document: `/doc/chapter[5]/section[2]` | 1 | W3C Recommendation, 1999 [link in 4.3] |
| Excel A1 style | a cell on a sheet: the sheet's name, `!`, then the cell (`B2`) | 1 for rows, A for columns | product documentation [link in 4.2] |
| SARIF 2.1.0 | any of the above, in one object | lines from 1, bytes from 0 | OASIS Standard, 27 March 2020 [below] |

SARIF is the format static-analysis tools report their findings in. Its
location object is the only one read here that was made to cover text,
binary and tree-shaped inputs at once:

- A location object holds a physical location, a logical location, both
  or, "in rare circumstances, neither".
  [https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.html,
  section 3.28.1]
- The physical part is the artifact (a URI) and a region. A region is a
  text region (`startLine`, `startColumn`, `endLine`, `endColumn`, or
  `charOffset` and `charLength`), a binary region (`byteOffset`,
  `byteLength`), or both: "For regions in binary artifacts, a region object
  SHALL define a binary region and SHALL NOT define a text region."
  `startLine` is "a positive integer"; `byteOffset` is "zero-based". [same,
  sections 3.29 and 3.30.1 to 3.30.12]
- A region may carry a `snippet`, "the portion of the artifact specified by
  the region object", which "allows a SARIF viewer to present the contents
  of the region even if the artifact from which it was taken is not
  available." [same, section 3.30.13]
- The logical part is a name, a fully qualified name and a kind. The kinds
  include "element", "attribute" and "text" for XML and "object", "array",
  "property" and "value" for JSON. The standard's own examples write the
  XML ones as paths (`/orders/order[1]/@number`) and the JSON ones as JSON
  Pointers (`/orders/0/productIds/1`), "although this is not required".
  [same, section 3.33.7 and its two examples]

### 4.5 One shape a reader could fill in

Reasoning, from the sources above; a sketch to argue with, not a design.
Every tool that names a location well gives the same four layers, and each
kind of input fills the third in its own way:

| Layer | What it holds | Delimited or positional text | Workbook | JSON | XML | Who does it this way |
|---|---|---|---|---|---|---|
| Source | which input: the reader's id, the path as the job gave it; a size, a time or a checksum where "which version of the file" matters | file | file | file | file | Snowflake (FILE, file content key), Spark (`_metadata`), RFC 5147 (`md5=`) |
| Record | the record's number among the records of that source, from 1; the same meaning for every reader | n-th record | n-th row read | n-th record | n-th record | W3C `source number`, Snowflake ROW_NUMBER, RFC 7111 `row=` |
| Position | where an editor or a tool finds it; the reader's own notation | line (and the last line when it spans several); a character offset | sheet and row, or `Sheet!B7` | a JSON Pointer | an XPath | Snowflake ROW_START_LINE and LINE, DuckDB `line`, Excel A1, RFC 6901, XPath, SARIF region and logical location |
| Field | the column's name and its place in the row; the value, cut to a length | name, number, value | name, sheet column, value | name, value | name, value | Snowflake `"T"["QUOTA":3]`, DuckDB `column_idx` and `column_name`, Talend's Excel message, PostgreSQL's 100 bytes |

Reasoning: the record number is the part every reader, present or future,
can always give, and the only part a carried tag has to hold. The position
can be worked out from it by the reader that made it, at the moment it is
needed. A reader for a database or a queue would fill the position with a
key or with topic, partition and offset.

Reasoning: byte offsets are what the parallel readers give because they
have them for free (1.12). They are the weakest part for v2: not stable
across the UTF-8 copy (4.1), and not what a support person can type into an
editor.

---

## 5. What to show of a very wide row

What the others show of the row:

- The column, by name and by place. Snowflake: `"MYTABLE"["QUOTA":3]`.
  DuckDB: `column_idx` and `column_name`. Redshift: `colname`, `type`,
  `col_length` and the position of the error inside the field. Polars' CSV
  message: "at column '{}' (column number {})". Talend's Excel message:
  "column: <name> (No. <n>)". Integration Services: the id of the column,
  or zero when "the error condition affects the entire row". [sections 1.5,
  1.3, 1.6, 2.2, 1.1, 1.9]
- The value. PostgreSQL cuts it at 100 bytes. Redshift keeps 1,024
  characters of it. Polars lists up to ten values, each whole. [sections
  1.4, 1.6, 2.2]
- Columns that identify the row. Only the data-quality tools have a setting
  for it: Great Expectations' `unexpected_index_column_names`, "For example,
  primary key (PK) column(s) or other columns with unique identifiers".
  Talend's tMap lets the designer drag chosen input columns into the error
  output. The loaders have nothing of the kind: they give the raw record or
  only the failed value. [sections 1.10, 1.1, 1.3 to 1.7]
- The whole row. As one piece of raw text: Spark's corrupt-record column,
  DuckDB's `csv_line`, Snowflake's REJECTED_RECORD, Redshift's `raw_line`
  (1,024 characters, "Multibyte characters in the load data are replaced
  with a period"), SQL Server's error file ("as is"), Databricks' exception
  file. As parsed columns: Talend's reject flow and Integration Services'
  error output. In the error text itself only three put the record: DuckDB
  ("Original Line"), Spark (`<badRecord>`) and, cut to 100 bytes and only
  for a fault of the whole line, PostgreSQL. [sections 1.2, 1.3, 1.4, 1.5,
  1.6, 1.9, 1.1]
- How many. BigQuery returns "At most, five errors". DuckDB has
  `rejects_limit`. Great Expectations lists 20 values and at most 200 rows.
  dbt has `limit`. SQL Server stops at 10 errors by default, PostgreSQL at
  `REJECT_LIMIT`, Redshift at `MAXERROR`. [sections 1.7, 1.3, 1.10, 1.9,
  1.4, 1.6]

What they do about sensitive data in error output:

- Kafka Connect logs no record content unless asked: the default "will
  prevent record keys, values, and headers from being written to log
  files." [section 1.11]
- Great Expectations can report places without values:
  `exclude_unexpected_values` leaves "only ... indices". It can also hand
  back a query for the failing rows in place of the rows. [section 1.10]
- Redshift limits who can read the stored errors ("regular users can see
  only their own data") and keeps them seven days. dbt writes failing rows
  into a schema of their own, which needs its own permission. [sections
  1.6, 1.10]
- PostgreSQL's 100-byte cut is made so as not to "print an unreasonable
  amount of COPY data in a message". [section 1.4]
- Polars has no cap and no switch: the failing values, and for CSV the
  whole field, are in the message. [section 2.2]

What v2 has for this today:

- The bad value goes into the ERROR log line and into the summary's `error`
  and `failures`, as long as Polars or the reader made it.
  [`v2:engine/runner.py#L286-L291`, `#L731-L742`; `v2:cli.py#L133-L140`]
- A wired reject output holds the whole row, every field as text, however
  wide. [`v2:components/file/file_input_delimited.py#L341-L344`]
- A subjob that fails writes none of its files, its reject file included:
  "A subjob is all or nothing: when one of its components fails, none of its
  files is written." [`docs/v2/README.md`, "Differences from v1", "The
  engine"]
- Key columns are marked in the schema and unused. [section 2.5]

Reasoning: for a row of a hundred columns the sources point one way. The
message carries the location, the one column and its value cut to a length,
and the key columns when the schema marks any. The whole row belongs in a
store of rejects with the same access rights as the data, not in a log. A
log often travels further than the data it describes, and the one tool
that talks about it (Kafka Connect) leaves record content out by default.

Reasoning: v2's all-or-nothing rule means the job's own reject file cannot
be that store on the run that fails. Whatever holds the failing rows of a
failed subjob has to be written by the engine, outside the subjob's files.

---

## 6. Where to report it

Where the others put it:

| Place | Who | What their pages say |
|---|---|---|
| The error text | Polars, Spark (FAILFAST), DuckDB (default), PostgreSQL (default), pandas, Talend (die on error) | one error, the first; DuckDB adds the line and the raw line, PostgreSQL the line, column and 100 bytes of value [1.3, 1.4] |
| The log | PostgreSQL (`LOG_VERBOSITY verbose`: one NOTICE a discarded row), Talend (`log.error`, or standard error with no reject link), pandas (`'warn'`), Kafka Connect (`errors.log.enable`, off by default) | a line a row; record content only on request in Kafka Connect [1.4, 1.1, 1.8, 1.11] |
| A store of rejects | DuckDB (two temporary tables), Snowflake (`VALIDATE`, saved to a table by the user), Redshift (system table, seven days), SQL Server (error file and a control file beside it), Databricks (JSON files under a folder named by time), dbt (a table a test, replaced each run), Kafka Connect (a topic), Talend and Integration Services (a flow to any output) | location columns beside the raw or parsed record; a limit on how many in most [1.3, 1.5, 1.6, 1.9, 1.2, 1.10, 1.11, 1.1] |
| A column in the data | Spark (corrupt-record column, `_metadata`), Snowflake (METADATA$ columns), DuckDB (`filename`), Polars (row index, file path) | asked for at the read [1.2, 1.5, 1.3, 2.4] |
| The result of the run | Snowflake (one row a file with the first error's line, character and column), BigQuery (`status.errors[]`, the first errors, five at most), PostgreSQL (a count of discarded rows), Great Expectations (the result of each check) | the first error and a count, not every error [1.5, 1.7, 1.4, 1.10] |
| Something a later step reads | Talend (`<id>_ERROR_MESSAGE` in globalMap, the tLogCatcher flow, error triggers), Snowflake (`VALIDATE(..., JOB_ID => '_last')`), Kafka Connect (the topic and its headers) | the message, and in Talend the component; no row in Talend's [1.1, 1.5, 1.11] |

What Talend gives a later step, in detail:

- `<id>_ERROR_MESSAGE` is set when a row fails and again when an exception
  ends the job; it is documented as "the error message generated by the
  component when an error occurs. This is an After variable ...". [section
  1.1]
- tLogCatcher's row has `origin` (the component) and `message`, nothing
  else about the place. [section 1.1]

What v2 has today, place by place:

- Log: one ERROR line a failed subjob, on standard error.
  [`v2:engine/runner.py#L286-L287`; `docs/v2/README.md`, "Running a job"]
- Summary: `error` (the first reason), `failed_component`, `failures`
  (component id to reason), all as text. [`v2:cli.py#L133-L140`]
- A file of errors: none made by the engine; a reject output where the job
  wires one, and only when the subjob succeeds. [section 5]
- globalMap: row counts, `<id>_FILENAME`, `<id>_ENCODING`,
  `<id>_CURRENT_SHEET`; nothing about an error.
  [`v2:components/file/file_input_delimited.py#L168-L169`;
  `v2:components/file/file_input_excel.py#L199`; section 2.5]

Reasoning: the four places want different amounts. A log line wants one
line of plain ASCII: component, source, record and position, column, value
cut short. The summary can hold the same as fields, so that nothing has to
be picked out of a sentence; today its `failures` are sentences. A file of
errors is the one place for many errors and for whole rows. globalMap wants
single values under fixed names that a trigger condition or a later
subjob's config can read; Talend's one name is `<id>_ERROR_MESSAGE`.

Reasoning: text added to `errorMessage`, or columns added to a reject
output, change the bytes of a reject file. v1 is the answer key for those
bytes, so either would be a deliberate difference from v1 and belongs on
that list in `docs/v2/README.md`, unless it is only done where the job's
reject schema declares a column for it.

---

## Comparison

"Line" is the tool's own word; the third column says what it counts.

| Engine | What it shows | Where it puts it | Counted in | Documented cost or limit |
|---|---|---|---|---|
| Talend (reject link) | the row's parsed columns, `errorCode`, `errorMessage` ending " - Line: N"; Excel adds the column's name and number | a reject flow to any output; globalMap `<id>_ERROR_MESSAGE` | rows already handled, from 0 (reasoned from the templates) | only with die on error off; no file line; no sheet name |
| Talend (die on error) | component, column, flow, value, stack trace | standard error; tLogCatcher (`origin`, `message`); globalMap | - | no line, no record |
| v1 | "- Line: N" on the row-by-row path only | `errorMessage` of the reject row | rows pandas read, from 1 | not on the fast path |
| v2 today | component, column, value, a count of rows | ERROR log line; summary `error` and `failures` | a row count on one message (field count) | value uncapped; no row; nothing in globalMap |
| Polars 1.44.2 and 2.0.0 | cast: types, column, up to 10 values, count in the batch; CSV: field, type, column name and number, byte offset | the exception text | bytes, from the chunk's start under streaming | no row or line; request #28051 open, #18363 closed |
| Spark 4.2.0 | the whole malformed record; file path; field and value | exception (FAILFAST), or a text column in the data (PERMISSIVE); `_metadata` on request | no line; a row index for Parquet | which records are corrupt depends on the columns read; the column cannot be queried alone |
| Databricks | bad record, file path, reason | JSON files under `badRecordsPath/<time>/bad_records/` | none | "non-transactional and can lead to inconsistent results" |
| DuckDB | line, byte position of the line and of the error, column index and name, error type, raw line, message | exception; or two temporary tables with `store_rejects` | file lines from 1; bytes | the error waits for earlier batches to count lines; 2,097,152 bytes a line; pushdown changes which rows fail |
| PostgreSQL 18 | table, line, column, value | error context; with `ON_ERROR ignore` a NOTICE a row and a final count | file lines, a quoted line break counted | value cut at 100 bytes; text and csv only; conversion errors only; no store of rejects among the options read |
| Snowflake | file, line, character, byte offset, column with its position, row number, line the row starts on, raw record | one row a file in the COPY result; all errors from `VALIDATION_MODE` or `VALIDATE` | rows, lines, characters and bytes | nothing for the default ABORT_STATEMENT; fails if the load transforms; one error a file otherwise; parallel only without multi-line records |
| Redshift | file, line, column, type, position in the field, raw line, raw value, code, reason | system table STL_LOAD_ERRORS | file lines; -1 and a byte offset for a split file | raw line and value 1,024 characters, reason 100; kept seven days; rows visible to their user |
| BigQuery | file, byte position of the row's start, message | the job's `status.errors[]` | bytes of the uncompressed data | five errors at most; quoted line breaks stop splitting |
| pandas | the line, and the field counts expected and seen | exception, warning, or a callable | lines | too many fields only; the callable needs the Python engine |
| pyarrow | expected and actual column counts, row number, row text | a callable | rows | no number under parallel reading |
| SQL Server BULK INSERT | the rows "as is", and a control file with diagnostics | `ERRORFILE` and `<file>.ERROR.txt` | - | 10 errors by default; fails if the error file exists |
| Integration Services | the row's columns, `ErrorCode`, `ErrorColumn` | an error output | - | no row number; column 0 for a whole-row error |
| dbt | the failing rows, the columns the test selects | a table a test in an audit schema | - | replaced on every run; `limit` |
| Great Expectations | values, counts, key columns, up to 200 rows, or a query | the result of the check | the user's key columns | 20 values by default; values can be left out |
| Kafka Connect | topic, partition, offset, stage, exception | headers on a record in a topic of its own; the log on request | the queue's own coordinates | off by default; record content not logged by default |

---

## Options for v2

Four ways, from least to most change. They are not exclusive: A is inside
B, C can be added to A or B, D needs B. All of it is reasoning from the
sections above; nothing here was tried, and the owner decides.

Three things are the same under every option and are set out in sections
4.5, 5 and 6: the shape of a location, how much of a row to show, and
which of the four places receive it.

### Option A - Readers number their records and report with the number

Each reader numbers its records as it reads and uses the number in its own
rejects and its own failure message. Nothing travels past the reader.

- Gives support staff: for every row a reader rejects or fails on (text
  that is not the declared type, a wrong field count, a missing value where
  none is allowed), the file, the record number and, for text read without
  enclosures, the line; the column and the value are there already. That is
  the first example in the ticket ("could not convert string to Decimal:
  '12x.50'"). It is more than Talend gives with die on error, and a true
  line where Talend gives a count (1.1).
- Costs: nothing measured at read time (ticket 37). The change stays inside
  the readers and the three checks that already take a count and a first
  message in the pass (2.5). Reject rows that gain a number differ from
  v1's (section 6).
- Does not cover: a failure after the reader, which is the ticket's second
  example (a map expression); the line of a record in a file read with
  `csv_option`; a broken enclosure, where Polars fails the whole read (2.2);
  Excel cells, which today "go missing and are never rejected" (2.5).

### Option B - The record number travels with the row

The number, with the id of its source, is a hidden column that components
pass on and sinks drop.

- Gives support staff: everything in A, and the source record for whatever
  v2 itself detects further down: a missing value after a join or a map,
  text a map output cannot read, any row on any reject output. After a
  join, the main row's record; after an aggregate, at most "first record
  and how many".
- Costs: 4 bytes a row where rows are held, and nothing on plans that do
  not use it (3.2). A rule for every component in the table of 3.3, with
  the base class and about eight components touched; sinks, log row and
  user Python must not see it or must be told. The 32-bit row limit of the
  installed runtime applies to the number as to everything else (2.4).
- Does not cover: an error Polars raises. Its text prints values only, so
  the number is in the row and not in the message (2.2). Rows that come
  from no input (constants, aggregates). User Python that builds a new
  frame.

### Option C - Look again, only after a failure

Nothing is added to a pass that succeeds. When a pass fails with an error
Polars raised, the engine looks for the row before it reports.

- Gives support staff: the record behind the ticket's second example, on
  any Polars version, at the price of a longer wait on a job that has
  already failed.
- Costs: measured for the crudest form only: 20 runs and 50 s for 1,000,000
  rows, whole job rerun (ticket 37). The forms in 3.4 (rerun the failing
  part; one pass in batches; one filter on the printed value) are not
  measured. Batches lean on two Polars functions marked unstable and "much
  slower than native sinks" (2.4). A budget like the 60 seconds the engine
  already gives the search for the component would be needed for the
  largest files.
- Does not cover: a subjob that cannot be read twice (a component that
  already acted on rows); an input that changed between the two reads; a
  failure with no single row behind it (a file that is missing, an output
  encoding that cannot write a character); a pass too long to repeat.

### Option D - A row that fails is a flagged row, not an exception

Every operation that can fail on a row is built in its non-raising form
with a flag beside it, the way the readers already parse text (3.5). A
failing row is then known in the first pass and can fail the component with
its location, or leave by a catch output.

- Gives support staff: the row, the column and the value for a failed
  expression, in the same pass, with no second read; and what the engine's
  map lists as left unbuilt on purpose, "routing rows whose expression
  failed to a catch output" (`.scratch/engine-v2/map.md`, "Not yet
  specified"), which is Talend's ErrorReject (1.1).
- Costs: the expression translator has to know every operation that can
  fail and make a flag for each, and tell "missing because the input was
  missing" from "missing because it failed" every time; the readers' rule
  for that exists (`v2:types.py#L141-L149`). More expressions in every plan
  that uses such an operation. It needs B, or the flagged row has no
  location once it is past the reader.
- Does not cover: user Python in a Python dataframe; errors Polars raises
  that are not about one row; anything the translator does not know can
  fail, which would still raise as today.

---

## Needs a try-out

Each of these can only be settled by running something on this engine.

1. Numbering at the scan on the real sizes. The "nothing measurable" figure
   is 1,000,000 rows of 45 columns on this Mac. Files of 30 to 100 GB, the
   RHEL servers, and the by-line path (`scan_lines`, then a row index) are
   unmeasured.
2. Whether the scan's row number is the record's true place under the
   streaming engine in every reader path v2 has: with a header, a footer
   cut by a count, a limit, and blank lines. `note-csv` observed it for a
   plain scan and for `.tail(2)` only.
3. Whether "scan row number plus header rows plus one" is the line an
   editor shows, for files without enclosures, including a file in
   ISO-8859-15 read through its UTF-8 copy and a file ending without a line
   break.
4. From a record number to a line in a file with enclosures, after the
   fact: how long one walk through a 1 GB and a 100 GB file takes to find
   record N and count the lines before it, and with what tool.
5. The three shorter searches of 3.4 against the 20 runs and 50 s already
   measured, and whether the search for the row can share its pass with the
   search for the component that v2 already makes.
6. Whether `sink_batches` and `collect_batches` keep rows in order and stop
   early on 1.44.2 under the streaming engine, and what they cost against a
   native sink.
7. What the bad values in Polars' cast message allow: how often the column
   it names is a column of the blamed component's input, so that one filter
   finds the rows.
8. Which operations the expression translator emits can raise on a row at
   all (strict casts, strict date parsing, others), listed by running each
   on a bad value. Option D stands or falls with that list.
9. A hidden column through each component of 3.3 on a real job: that every
   output file stays byte for byte what v1 writes, and what a sort and a
   join of the largest inputs cost in memory with 4 more bytes a row.
10. fastexcel: whether a row's place in the frame is its row in the sheet
    with `header_row=None, skip_rows=0` when the sheet starts with empty
    rows, what `CellError.position` counts from, and what
    `to_arrow_with_errors` costs.
11. The row counts of the largest real inputs against the 4,294,967,295
    rows the installed 32-bit runtime allows.
12. How long a message gets on a real wide file: one error line with the
    location, the column, the value and the key columns of a 100-column
    row, and the size of a file of errors when a few thousand rows fail.

---

## Not verified

Looked for and not confirmed from a primary source, or confirmed only in
part.

- Talend's own repository. `github.com/Talend/tdi-studio-se` answered "Not
  Found" on 2026-10-06 and the Talend organisation no longer lists it. The
  templates were read in `Talaxie/tdi-studio-se` at commit `639d5fd1f7`, a
  fork whose parent is `DeiLinkEtl/tdi-studio-se`. That the templates of
  the Talend 8.0 that Citi runs are the same was not verified.
- What "Line: N" counts in a running Talend job. It is reasoned from two
  templates (declared 0 at the start, raised at the end of each main part),
  not seen in the output of a job. Whether a rejected row raises the
  counter, and whether rows dropped as empty do, was not traced.
- What a Talend job prints when die on error stops it. Read from the
  templates, not from a run.
- Spark's `_metadata` column in Apache's own documentation. It is not on
  the six data-source pages of the 4.2.0 documentation that were searched
  (overview, generic options, load and save, CSV, JSON, text); the fields
  are from Spark's source and from Databricks' page.
- That no page read for section 1 speaks of carrying a source position
  through a join or an aggregate. That is the absence of a finding in the
  pages listed here, not a search of each tool's whole documentation.
- Snowflake: how long "The copy history metadata" lasts before `VALIDATE`
  stops working; the page that states it was not read.
- PostgreSQL: whether another part of the COPY page, beyond the three
  options read, offers a place to keep discarded rows.
- BigQuery: "At most, five errors" is written on the `bq load` flag; whether
  the same cap holds for the job's `status.errors[]` through the API was
  not confirmed.
- DuckDB: which release `docs/current` described on 2026-10-06 (the page
  carries no version; the latest tag was v1.5.6), and whether the rejects
  tables keep the line when a line is longer than the maximum.
- pandas: how its default (C) reader counts a line when a quoted field
  holds a line break. Only the Python reader's message was read.
- Polars: whether a raised exception carries anything but its text. The
  Python classes come from the compiled module
  (`venv:polars/exceptions.py#L1-L60`); no attribute was looked for.
- Polars: that the CSV byte offset is counted from the chunk in every path
  of the streaming engine. The code passes 0 and `note-csv` observed one
  case; nothing was run here.
- Polars: what the streaming engine counts as a "row" for a chunk's row
  offset when a quoted field holds a line break.
- Polars tracker: the searches were by keyword ("line number" csv; "row
  number"; cast error "row index"; ignore_errors rows; ndjson parse error
  line; "source row"; rejected or bad or invalid rows) on 2026-10-06. An
  issue worded otherwise can have been missed.
- fastexcel: what `position`, `row_offset` and `offset_position` of a
  `CellError` mean exactly; only their names and types are in the installed
  stub.
- Research papers on row provenance in dataflow engines were not read; they
  are not a tool's own documentation.
