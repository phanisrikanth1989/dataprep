# 29 - Routines as Polars functions

Status: open
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
