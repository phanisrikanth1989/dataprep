# Differences from v1

v1 is the answer key: a job that runs on v2 writes the same files v1
writes, with the exceptions on these pages. Each is deliberate.

| Page | What is on it |
|---|---|
| [The engine and values](engine.md) | The engine, Values |
| [Sources and outputs](sources-and-outputs.md) | Delimited files, Positional input, Full-row input, Excel input, JSON input, Properties input, Fixed flow input, Row generator, Excel output, Positional output, Pivot to columns delimited |
| [Rows](rows.md) | Filter rows, Filter columns, Sort row, Unique row, Aggregate row, Aggregate sorted row, Join, Unite, Map, Normalize, Denormalize, Replicate, Sample row, Split row, Replace, Convert type, Unpivot row, Schema compliance check, Python dataframe, Log row |
| [Extracting fields](extracting-fields.md) | Extract delimited fields, Extract positional fields, Extract regex fields, Extract JSON fields |
| [Job control](job-control.md) | Context load, Die, Warn, Set global var |
| [File jobs](file-jobs.md) | File copy, File delete, File exist, File row count |

The components that are not held to v1 at all are under
[Components built to their own rule](../own-rule/README.md).
