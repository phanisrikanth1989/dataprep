# 43 - Normalize

Status: resolved
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

## Answer

Built on 2026-10-07 (`src/v2/components/transform/normalize.py`; 21 tests
in `tests/v2/components/test_normalize.py`, against v1).

- Keys: `normalize_column`, `item_separator` (`itemseparator`), `trim`,
  `discard_trailing_empty_str`, `deduplicate`. `csv_option`,
  `text_enclosure`, `escape_char` and `die_on_error` are accepted and
  ignored, as in v1.
- v1's order is kept: the empty pieces a cell ends on are discarded, then
  each piece is trimmed, then repeats are left out.
- Text and numbers are split as their text. A column of dates is refused.
- Every row it makes carries the row number of the row it came from.

Corrected after review (ticket 45): trim strips what Python's `strip()`
strips; a separator of several characters is found from the left before
anything is discarded; a value that is not text is split as the text Python
writes for it.
