# 28 - Which Polars versions v2 supports

Status: open
Type: grilling

## Question

The repo pins `polars>=1.38,<2.0`, and Polars' behaviour changes inside that
range in ways the answer key can see. Which versions does v2 support and test
against?

Changes inside the range, from the three research tickets
([delimited files](02-polars-facts-delimited-files.md),
[collection, streaming and Decimal](03-polars-facts-collection-streaming-decimal.md),
[Python expressions](04-python-expressions-to-polars-prior-art.md)):

- `select(pl.len())` on a CSV scan returned wrong counts: with a filter on
  1.39.0 to 1.39.3 (fixed in 1.40.0), and with a slice on at least 1.40.1
  (fixed in 1.41.0).
- The CSV reader's `missing_utf8_is_empty_string` was renamed
  `empty_string_is_null`, with inverted meaning, in 1.43.0. The old name
  warns from then on and the new one does not exist before it.
- Casting String to Date with `cast` is deprecated from 1.42.0 and removed in
  2.0.

- Decimal `sum`: the result type widened in 1.40/1.41, and overflow wrapped
  silently before 1.44.0.
- Several outputs of one plan: the rule that keeps a shared part when a
  branch filter cannot be pushed into it is new in 1.43.0.
- The streaming engine was marked unstable until 1.41.0.
- `when/then` evaluated both branches on every row before 1.44.0 and masks
  the unselected rows only from 1.44.0. A guarded expression such as
  `int(s) if s.isdigit() else 0` therefore fails on 1.38 to 1.43 and works on
  1.44. Read from source for the older versions, observed on 1.44.2.
- NaN handling in `min_horizontal` / `max_horizontal` changed in 1.44.0.
- 1.38.0 itself is yanked on PyPI; 1.38.1 is the lowest installable release.
- 2.0 is in pre-release, makes streaming the default, and is outside the pin.

To settle:

- Which Polars version the target servers run, or can be given, and whether
  that can be held to one version. This is a fact the user supplies.
- One supported version, a narrow range, or the present range with tests at
  both ends.
- Which version the answer-key tests and the benchmarks run on.
- When and how the pin moves, 2.0 in particular.

Surfaced while resolving the research tickets. Each of their notes has a
table of what changed inside the range.
