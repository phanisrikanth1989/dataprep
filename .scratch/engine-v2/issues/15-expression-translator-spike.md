# 15 - Expression translator spike

Status: resolved
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

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

Superseded by the build: the translator was built for real
(`src/v2/expressions`), tests first, rather than spiked. The motivating
case reads `row1.name[:10].strip().upper()`. What it refuses and how a
refusal reads is in the tests (`tests/v2/unit/test_expressions_*.py`).
