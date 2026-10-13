# 71 - Review of row generator, Excel output and positional output

Status: resolved
Type: task

## Question

An independent, read-only reviewer ran the row generator, the Excel output
and the positional output (tickets 66, 68 and 69, as at commit c301fad2)
against v1, and the positional output against Talend's templates, on
inputs their tests did not cover. What did it find, and what is done about
each?

## What it found (2026-10-12)

Twenty-two findings; both engines were run on each, and the positional
output was read against Talend's templates line by line.

1. Positional output wrote one line for any number of rows when no entry
   of `formats` named a column that arrives; the Excel output counted no
   rows for a declared column that does not arrive.
2. A null `align` centred. 12. A null `padding_char` gave Polars' error.
3. Row generator: a true/false column that may not be missing was written
   empty, or failed the job.
4. Row generator: a table of values v1 and v2 read differently, dates not
   in their column's pattern first among them.
5. Positional `compress`: two things the template does that v2 does not.
6. A float that declares places is rounded before it is written.
7. Row separator escapes beyond `\n`, `\r`, `\t`.
8. Excel: a day of a `date` column was a date cell, v1 has text.
9. Excel widths are not always v1's numbers. 10. Columns under the sink's
   output schema. 11. A read-only file is replaced.
13. Excel errors in openpyxl's words, raised when the file is put in
    place. 14. File-system errors carry the engine's working file names.
15-19. Claims: what can fail late; when v1 fails to size; "nothing in
    reach but random"; `Write.as_text` missing on both outputs; two line
    numbers.
20-22. A test line that was always true; twelve ways of breaking the
    three that no test noticed; no test for 1, 2 and 12.

## Answer

Done on 2026-10-12, each fix with a test seen failing first.

Fixed: 1, 2, 3, 8, 12, 18, 20; of 4 the numbers and true/false read
across types and the dates; of 9 the Decimal of no places; of 13 the
first cell, too many columns and a full sheet (a column name with a
control character, and a chart named as the sheet, still fail in
openpyxl's words). 21 and 22: tests added; 29 ways of breaking the fixes
and the reviewer's twelve were tried, and each is caught or was found to
be code that did nothing and removed (`Write(append=)`, a check for
negative places the loader never lets through).

Said in the README and left as they are: the rest of 4, 5, 6, 7, the rest
of 9, 10. Claims corrected: 15, 16, 17, 19.

Not done, and not of these components alone:
- 11: a read-only file is replaced, because a file is put in place by
  moving the finished one over it. v1 fails there. Every v2 output has
  this.
- 14: the operating system's own words, with the engine's working file
  name in them, when the path is a folder or the folder cannot be
  written.
- `empty_leaves_none` on the two outputs is not held by a test.
