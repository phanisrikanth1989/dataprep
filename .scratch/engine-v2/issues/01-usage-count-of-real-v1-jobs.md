# 01 - Usage count of real v1 jobs

Status: resolved
Type: task

## Question

Which components, config keys and Java constructs do real v1 job configs
actually use? The 10-15 component set, and the order the expression work is
done in, should follow real usage. The only job configs in this repo are 37
converter fixtures (`tests/talend_xml_samples/converted_jsons/`), which
over-represent LogRow and single-component jobs.

The work, in two halves:

- Agent: write a small script that walks a folder of v1 job configs and prints
  aggregate counts only. Standard library only, Python 3.12, runs on Windows
  and RHEL. It counts:
  - component types: jobs using each, and instances;
  - per component type, which config keys appear and how often;
  - value distributions for a fixed allow-list of low-risk keys: `encoding`,
    `fieldseparator`, `row_separator`, `csv_option`, `header_rows`,
    `footer_rows`, `die_on_error`, `join_mode`, `matching_mode`,
    `lookup_mode`, aggregate `function`, filter `operator` and `function`,
    `sort_type`, `order`, `keep`;
  - flow types, trigger types, schema type names and date patterns;
  - `{{java}}` strings by component type and config key, and how many use
    each construct that needs rewriting: ternary, `.equals(`, `&&` / `||`,
    string methods, `StringHandling.` / `TalendDate.` / other routine calls,
    `globalMap`, casts, `null`.

  It must never print file paths, expressions, context values or any other
  job content: the output has to be safe to carry off the machine it runs on.
- Human: run it where the real v1 job configs live and paste the output into
  this ticket.

Resolved when the counts are recorded here. They feed
[Pin the component list](27-pin-the-component-list.md) and
[Python expressions: what is allowed and how it reads](16-python-expressions-allowed.md).

## Answer

Recorded 2026-10-05. Method changed: the script cannot be run inside the Citi
environment, so no counts exist. Everything below is the driving dev's stated
intent and recollection, given in conversation. Treat the usage statements as
recalled estimates, not measurements.

### The frame

The component set is not chosen by what v1 runs today. It is chosen to show
that v2 can be built and work as far as possible on a focused set; the rest
of v1's components are enhanced into v2 later.

### Component set wanted: 16

- Locked eight: delimited file input, delimited file output, filter rows,
  sort row, unique row, aggregate row, map, python dataframe.
- Added: Join, Unite, filter columns, LogRow, context load, Excel input,
  full-row input, positional input.
- Dropped for now: python row, python code, ConvertType,
  SchemaComplianceCheck, Replicate, Excel output, file list, flow to iterate,
  every database component.

Consequences:

- No iterate component is in the set, so iterate flows, loop bodies and
  nesting are not needed for the first set.
- Python dataframe is the one custom-code component: user code takes a Polars
  frame and returns one. There is no row-by-row and no flowless code block.
- Context load already exists in v2 as found
  (`src/v2/components/utility/context_load.py`); it is rebuilt like the rest.
- Positional input and Join have no v2 implementation as found; they are new
  builds.

### Expressions (recalled)

- In nearly every job: ternaries, `.equals(`, null checks, string methods,
  `StringHandling.*`, `TalendDate.*`.
- Casts: not used much.
- `globalMap`: minimal inside map; used widely inside the Java components
  (tJava and the like), which have no v2 counterpart.
- `TalendDate` formatting/parsing and `BigDecimal` arithmetic: in between,
  neither dominant nor rare.
- v1, like Talend, accepts a Java expression in any config key of any
  component. Which keys really carry one in practice is not known.

### Routines

- Custom Java routines are mostly lookups and business rules. They do not
  come to v2; the dev will have them rewritten as Python routines by hand.
- Python routines are allowed in v2 under one rule: a routine is a Polars
  function (takes columns, returns a column) and is never called row by row.

### Left open for later tickets

- Where the logic that lives in v1's Java components goes (globalMap writes,
  side effects), given that python code is not in the set.
- How a lookup-style routine is written as a Polars function, since a lookup
  is a join and not a column-to-column function.
