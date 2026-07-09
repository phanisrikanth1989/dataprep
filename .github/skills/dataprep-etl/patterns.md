# Flow patterns (pick the shape, then configure)

Common data-preparation shapes. The flow-designer picks the shape; the configurator fills
the config. These cover the curated node set -- you do NOT need to read engine source for them.

## Lookup-enrich (add columns from a reference file)
`source + lookup -> [tJoin | PyMap | tMap] -> ... -> FileOutputDelimited`.
- `tJoin`: one equality-key lookup, keeps the first lookup row per key -- the default choice.
- `PyMap` / `tMap`: several lookups, a join variable, or an expression-derived output column.
- `LEFT_OUTER_JOIN` keeps every source row (an unmatched row flows out with null lookup
  columns); `INNER_JOIN` drops misses. Keep the lookup key unique (`UNIQUE_MATCH` /
  `FIRST_MATCH`, or pre-dedup with `UniqueRow` / `AggregateRow`) so one source row maps to one.

## Validate a type/format, route failures to a reject (SchemaComplianceCheck)
`SchemaComplianceCheck` validates each row against the declared column types/formats --
INCLUDING a date format via a per-column `date_pattern` (e.g. `yyyy-MM-dd`) -- and routes rows
that FAIL to a separate REJECT output flow while passing rows continue on the main flow:

```
... -> SchemaComplianceCheck --main----> (rest of the pipeline)
                             --reject--> FileOutputDelimited (the rejected rows), if kept
```

Use it for a `schema_validate` rule that must ACT on bad rows (drop or route them). For a
plain type conformance with no reject action, a `ConvertType` cast -- or BaseComponent's own
output-schema coercion -- is enough; no extra node.

## Derive / cast in one vectorized pass (python_dataframe)
Place ONE `tPythonDataFrame` AFTER the join to collapse casts + derivations into a single
pass. It is single-input (cannot join) and unsandboxed (human-reviewed); pin
`execution_mode: "batch"` on it.

## Aggregate before sort
`AggregateRow` (pandas groupby) discards row order, so put `SortRow` LAST to fix the
downstream-facing output order (the oracle diff is order-insensitive, so a wrong final order
would otherwise ship undetected).
