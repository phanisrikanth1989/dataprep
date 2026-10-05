# 15 - Expression translator spike

Status: open
Type: prototype
Blocked by: 04

## Question

How does "Python to write, Polars to run" behave on real expressions? Build a
rough translator that takes Python expressions as v1's PyMap accepts them and
produces Polars expressions, run it over a set of real-shaped expressions, and
compare each result with what v1's PyMap returns for the same rows.

It should let us see, and react to:

- which constructs translate cleanly and which do not;
- how a refusal reads when an expression cannot be translated;
- where results differ from v1: None, empty strings, division, string plus
  number;
- how a long expression reads in Python. The motivating case: today's
  `UPPER(TRIM(SUBSTRING(name, 0, 10)))` as `row1.name[:10].strip().upper()`.

Throwaway code, linked from this ticket. It is not the build. Start from
[Translating Python expressions to Polars: prior art and mapping](04-python-expressions-to-polars-prior-art.md),
and use the Java-construct tallies from
[Usage count of real v1 jobs](01-usage-count-of-real-v1-jobs.md) if they are
in.

Feeds
[Python expressions: what is allowed and how it reads](16-python-expressions-allowed.md).
