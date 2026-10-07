# 43 - Normalize

Status: ready-for-agent
Type: task
Blocked by: 40

## Question

Build v1's normalize (`Normalize`, `tNormalize`) on v2: one row whose cell
holds several values becomes one row for each value.

The dev asked on 2026-10-07 for normalize or unpivot, to try the row numbers
on a step that makes several rows out of one. Normalize was taken.

## What is known

- v1: `src/v1/engine/components/transform/normalize.py` (176 lines).
- The converter writes its config; a converted sample is in
  `tests/talend_xml_samples/converted_jsons/Job_tNormalize_0.1.json`.

## To build

- The component, every config key declared, held against v1.
- Each row it makes carries the number of the row it came from.
- The docs and the lists that count v2's components.
