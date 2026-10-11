# 54 - Sample row

Status: resolved
Type: task

## Question

Build v1's sample row (`SampleRow`, `tSampleRow`) on v2: rows picked by
their place in the flow. Asked for on 2026-10-11 with the other 25.

## Answer

Built on 2026-10-11 (`src/v2/components/transform/sample_row.py`; 15 tests
in `tests/v2/components/test_sample_row.py`, against v1).

- `range` is needed, as in v1: numbers and `first..last`, separated by
  commas. A range that cannot be read refuses the job at load (v1 fails
  when the component runs).
- The rows at the places go on; the others leave by the reject output, as
  they are (no error columns), in the order they came.
- Rows it does not pick are the job's own doing: nothing is said in the log.
- Row numbers pass. No difference from v1.

## Corrected after review (ticket 62)

- A number of the range is read as Python's `int()` reads it, which is how
  v1 reads it (`+3`, `1_0`). A range of nothing but commas picks no row, as
  in v1; an empty one and one that is no text refuse the job in words of
  their own.
- `die_on_error` is declared, as on every component of v1.
- Places are counted among the rows that arrive: in a run for a few picked
  rows of a reader, among those. The README says so.
