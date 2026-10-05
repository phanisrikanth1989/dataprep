# 13 - Types, nulls and schemas

Status: resolved
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

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

- Schema column keys: `name`, `type`, `nullable`, `key`, `length`,
  `precision`, `date_pattern` (`pattern` as a spelling) are read; `default`,
  `comment`, `original_type` ignored. `length` and `key` change nothing, as
  in v1.
- Type names: v1's `str`, `int`, `float`, `bool`, `datetime`, `Decimal`,
  plus `date`, with `string`/`integer`/`decimal`/`id_String`... as
  spellings. An unknown type name is refused.
- Decimal is `pl.Decimal(38, precision)`, ten places when none is declared;
  text is rounded half up to the declared places as v1 does. Int is 64-bit.
  Floats are written as v1 writes them (Python repr).
- `date_pattern` is Python strftime, as v1's job configs carry it; a
  Java-style pattern is understood too.
- Missing values: text from a file is never missing; an empty field is
  missing for every other type except `bool` (false, as in v1); `NaN` text
  is missing for `float`. `nullable: false` is enforced: fatal with
  `die_on_error`, a rejected row without.
- Where v1's answer depends on the other values in a column, v2 gives each
  value the answer v1 gives in a clean column. Code: `src/v2/types.py`;
  evidence: `research/2026-10-05-v1-delimited-bytes.md`.
