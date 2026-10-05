# 29 - Routines as Polars functions

Status: resolved
Type: grilling
Blocked by: 16

## Question

Python routines are allowed in v2 only as Polars functions: a routine takes
columns and returns a column, and is never called row by row (decided in
[Usage count of real v1 jobs](01-usage-count-of-real-v1-jobs.md)). What is
the contract?

- Where routine files live, how a job config names them, and how they are
  loaded and checked at load so a bad routine lands in the refusal report.
- How an expression calls one, and how the translator tells a routine call
  from a built-in.
- How the rule is enforced: what stops a routine from hiding a row-by-row
  callback.
- How a lookup-style routine is written. The Java routines being ported are
  mostly lookups and business rules, and a lookup is a join, not a
  column-to-column function.
- Whether v1's existing Python routines run unchanged, are refused, or need a
  rewrite, and what v2 as found does with routines marked vectorised.

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

- Files live in the folder a job config names in `python_config`
  (`enabled`, `routines_dir`, `routines`), as in v1, and are named as v1
  names them: `fee_rules.py` is `FeeRules`.
- An expression calls `routines.FeeRules.net(row1.amount)` or
  `FeeRules.net(row1.amount)`. A dotted name whose first part is a loaded
  routine module is a routine call; built-ins are looked up first.
- A routine gets Polars expressions (constants arrive as Python values) and
  must return a Polars expression. A result that holds a Python callback
  (`map_elements`) is refused, at load, in the refusal report; so are a
  folder that does not exist, a file that cannot be imported and a required
  routine that is missing.
- A lookup is a join: it belongs in a Map lookup or a join component, not in
  a routine.
- v1 routines written with plain operators work unchanged; ones using
  Python string methods or `if` on their arguments need a rewrite.
- Code: `src/v2/engine/routines.py`.
