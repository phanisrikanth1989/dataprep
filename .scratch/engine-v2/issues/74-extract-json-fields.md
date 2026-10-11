# 74 - Extract JSON fields

Status: resolved
Type: task

## Question

Build v1's extract JSON fields (`ExtractJSONFields`,
`tExtractJSONFields`) on v2: one column holds a JSON document, and paths
into it become columns, a row for every item a loop path finds. Asked for
on 2026-10-11 with the other 25.

## What is known

- v1: `src/v1/engine/components/transform/extract_json_fields.py`, on
  jsonpath-ng, row by row. With `read_by` JSONPATH it reads
  `json_loop_query` and `mapping_4_jsonpath` (`schema_column`, `query`).
  With `read_by` XPATH it reads `loop_query` and `mapping` and tries them
  as JSONPath, which they are not: on the converter's own sample it writes
  rows with nothing in them.
- Tried on v1 (2026-10-12, 20 small jobs): a row for each item the loop
  path finds, none where it finds none; a path that finds nothing gives
  empty text, one value gives the value, several give them as a JSON list,
  an object or a list is written as JSON; an entry with no path takes the
  input column of the same name; only the columns of the mapping are
  written. A source that is missing leaves by the reject output
  (`NO_JSON`), one that is no JSON too (`PARSE_ERROR`, an empty text among
  them), each with the text in `errorJSONField`; under `die_on_error` they
  fail the job. A path that cannot be read gives empty text for every row,
  a loop path that cannot be read is passed over, and a `jsonfield` that is
  no column is taken for the first column.

## Answer

Built on 2026-10-12 (`src/v2/components/transform/extract_json_fields.py`;
34 tests in `tests/v2/components/test_extract_json_fields.py`, 29 of them
written and seen failing before any code; held against v1 byte for byte
but for one that says why not).

- JSON is read out of every row in Python, with jsonpath-ng as in v1, so
  the component takes its rows in hand (the engine collects them for it)
  and is named in `tests/v2/test_rules.py` among those that may walk rows.
  Every row it hands on carries the row number of the row its document
  came from.
- Its values are made a frame by `column_types.held_frame`, as the rows a
  config writes are; that function learned to read dates by their
  column's pattern alone, which is how v1 reads them here.
- v1's codes and messages in the reject output, `errorJSONField` among
  its columns.
- Refused where v1 goes on with nothing: `read_by` XPATH, a path that
  cannot be read, a `jsonfield` that is no column. Each in the README.
- Row counts are held against v1's (rows read, items handed on, rows
  turned away); a run can be for a few rows, and the trace names where
  each item came from.
- Mutation check: 26 ways of breaking it, 21 caught at first and the
  other five after a test each.

Not built: `read_by` XPATH (Talend reads JSON as XML there).
