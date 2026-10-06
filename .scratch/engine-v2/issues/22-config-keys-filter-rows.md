# 22 - Config keys, key by key: filter rows

Status: resolved
Type: grilling
Blocked by: 05, 07, 08, 12

## Question

Walk every config key of v1's FilterRows and of v2's `filter_rows` as found,
and give each one of the five verdicts: same in both; v2's name kept with
v1's spelling as an alias; v2 adopts v1's name; the loader translates v1's
form; refused or ignored. The two are far apart: v1 has a structured list of
conditions, v2 as found has one expression string.

How to run it: bring a table of v1 key and default, v2 key and default as
found, what each does and a proposed verdict; the user confirms or changes it
row by row. Recover the purpose of each v2 rename before judging it. Apply
[The performance bar](05-performance-bar.md) and the defaults policy from
[Config-key declaration, aliases and the refusal report](07-config-key-declaration-and-refusal-report.md).

v1 keys (`agents/schemas/config-surfaces.md`): `conditions` (each with
`column`, `operator`, `function`, `value`), `logical_op`, `use_advanced`,
`advanced_cond`.

- Operators: `==`, `!=`, `>`, `<`, `>=`, `<=`, `MATCHES`, `CONTAINS`,
  `NOT_CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `IS_NULL`, `IS_NOT_NULL`,
  `LENGTH_LT`, `LENGTH_GT`. A verdict for each.
- Functions: none, `LOWER`, `UPPER`, `LOWER_FIRST`, `UPPER_FIRST`, `LENGTH`,
  `TRIM`, `LTRIM`, `RTRIM`, `ABS`, `LEFT(n)`, `RIGHT(n)`. A verdict for each.

v2 keys as found: `condition`, `reject_output`.

Also settle: how the value in a condition is typed against the column; what a
null does to a condition (as found, such rows reach neither output, finding
5); and how a reject flow in the job config turns the reject output on.

The verdict for `advanced_cond` waits for
[Expressions outside Map](17-expressions-outside-map.md); leave that row
pending if it is still open.

## Answer

Resolved 2026-10-06 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn. The full key list, generated from the
code, is the component's page under `docs/v2/components/`
(`.venv/bin/python scripts/gen_v2_docs.py`).

- `conditions[]` keep v1's vocabulary exactly: the fifteen operators, the
  functions (LOWER, UPPER, LOWER_FIRST, UPPER_FIRST, LENGTH, TRIM, LTRIM,
  RTRIM, ABS, LEFT(n), RIGHT(n)), and v1's rule that the value decides
  between a number and a text comparison. `logical_op` takes `&&`, `||`,
  `AND`, `OR`.
- The advanced condition is a Python expression: key `condition`, with v1's
  `advanced_cond` as an alias, read only when `use_advanced` is on. The Java
  code sample Talend stores in every filter does not refuse the job while
  `use_advanced` is off.
- Outputs: `main` (flow types flow, main, filter) and `reject`, with v1's
  `errorMessage`.
- Refused at load where v1 runs and gives an answer that is rarely meant: a
  condition on a column that does not exist, an unknown function, a date
  column compared with a number, a pattern with lookaround.
- 570 tests; the Java advanced condition of v1 is checked through the bridge.
