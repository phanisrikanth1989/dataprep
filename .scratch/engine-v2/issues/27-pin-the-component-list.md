# 27 - Pin the component list

Status: open
Type: grilling
Blocked by: 01, 05

## Question

Which components make up the 10-15? Eight are locked: delimited file input,
delimited file output, filter rows, sort row, unique row, aggregate row, map,
python dataframe. Decide the rest from two things: what real v1 jobs use
([Usage count of real v1 jobs](01-usage-count-of-real-v1-jobs.md)) and what
Polars can do natively at speed ([The performance bar](05-performance-bar.md)).

Candidates known today:

- LogRow: the most common component in the fixture job configs, and v2 has
  no equivalent. Printing rows forces a collect.
- Filter columns, unite: in v2 as found, on the old standard.
- Python row, python code: in v2 as found.
- Context load: in v2 as found.
- File list and flow to iterate: in v2 as found, with defects (findings 6 to
  8). Choosing either brings iterate flows into scope.
- Excel input, full-row input: in v2 as found.
- v1's ConvertType, Join, SchemaComplianceCheck: curated for ETL Studio, not
  in v2.
- Whatever else the count shows is widely used.

For each component chosen, add a key-by-key ticket and a build. If iterate
comes in, add its semantics ticket. Also decide what happens to components v2
has today that are not chosen (parquet output exists only in v2).
