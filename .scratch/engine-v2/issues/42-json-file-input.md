# 42 - JSON file input

Status: ready-for-agent
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
