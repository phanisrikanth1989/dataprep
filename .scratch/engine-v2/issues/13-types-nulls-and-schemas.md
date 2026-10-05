# 13 - Types, nulls and schemas

Status: open
Type: grilling
Blocked by: 02, 03, 05, 28

## Question

What is a column's type in v2, and what are null and empty? Explicit schema,
never inferred, stays; this ticket settles everything inside that rule.

To settle:

- Schema column keys in v1 job configs: `name`, `type`, `nullable`, `key`,
  `length`, `precision`, `date_pattern`. A verdict for each under the
  five-verdict scheme.
- Type names. v1 writes `str`, `int`, `float`, `bool`, `datetime`, `Decimal`.
  v2 as found writes `string`, `integer`, `decimal` and also accepts Talend
  ids that silently degrade to strings (finding 18).
- Decimal. As found, decimal columns are strings and `TO_DECIMAL` is a float
  (finding 17). What v1 computes with is the answer key; does Polars' Decimal
  type meet it at speed?
- Integers and floats: widths, overflow, and how a float is written
  (`30200` versus `30200.0`).
- Dates: the dialect of `date_pattern` in v1 job configs, parsing and
  writing, date versus datetime.
- Null versus empty string. What v1 reads and writes for an empty field, per
  type, set against what Polars does (finding 19), including the text `NaN`.
- `nullable: false`: enforced, ignored or refused.

Facts come from the two Polars facts tickets
([delimited files](02-polars-facts-delimited-files.md),
[collection, streaming and Decimal](03-polars-facts-collection-streaming-decimal.md)).
