# 42 - JSON file input

Status: resolved
Type: task
Blocked by: 40

## Question

Build v1's JSON file input (`FileInputJSON`, `tFileInputJSON`) on v2, to
the component contract in `docs/v2/writing-a-component.md`, and have it
number its records like every other source.

The dev asked on 2026-10-07 for a JSON or XML input, to try the row numbers
on a source that is not lines of text. JSON was taken; the XML input can
follow the same way.

## What is known

- v1: `src/v1/engine/components/file/file_input_json.py` (391 lines). The
  whole document is read, a JSONPath (`jsonpath_ng`) picks the records, and
  a JSONPath a column picks each value out of a record.
- The converter writes its config
  (`src/converters/talend_to_v1/components/file/file_input_json.py`); a
  converted sample is in `tests/talend_xml_samples/converted_jsons/`.

## To build

- The component, every config key declared (supported, ignored or refused),
  held against v1 on the same job config and bytes.
- A record's number is its place among the records the loop query finds,
  from 1; `locate` says "record 7 ($.users[6]) of in.json".
- The docs and the lists that count v2's components.

## Answer

Built on 2026-10-07 (`src/v2/components/file/file_input_json.py`; 31 tests
in `tests/v2/components/test_file_input_json.py`, most of them against v1).

- Read as v1 reads it: the document whole, the records and the values by
  JSONPath through `jsonpath_ng`, which the `v2` extra now names.
- A path that finds one value gives it; one that finds several, or holds
  `[*]` or `.*`, gives a JSON list; one that finds nothing gives `[]`. Lists
  and objects are handed on as JSON text, written as v1's `json.dumps`
  writes them. Every value is text until the engine fits it to the schema.
- Keys: `path` (`filename`), `json_loop_query`, `mapping`, `encoding`,
  `use_loop_as_root`, `die_on_error` are supported. `useurl` and a `schema`
  inside the config are refused. `read_by`, `loop_query`,
  `json_path_version`, `urlpath`, the separator keys and `check_date` are
  accepted and ignored, as v1 does not act on them.
- A row's number is its record's place among the records found;
  `locate` says "record 2 ($.orders[1]) of in.json".

Where it does not follow v1 (listed in `docs/v2/README.md`): one rule per
value where v1 lets pandas pick a type for the column; a path that is no
JSONPath refuses the job; a wired reject flow with nothing in it is written
empty.

Corrected after review (ticket 45): a record a path cannot be followed on
is turned away with `PARSE_ERROR`, as in v1, and no longer fails the job.

The converted sample (`Job_tFileInputJSON_0.1.json`) is refused only for
its JSONPaths, which are empty: the Talend job it came from reads by XPath.
