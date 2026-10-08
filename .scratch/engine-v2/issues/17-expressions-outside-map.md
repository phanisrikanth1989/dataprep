# 17 - Expressions outside Map

Status: resolved
Type: grilling
Blocked by: 16

## Question

Where else does a job config compute something, and is it the same expression
language there? v2 as found has three syntaxes: the expression language, a
separate grammar for trigger conditions, and `${context.x}` substitution in
config strings.

To settle:

- Filter rows. v1 has structured `conditions` (an operator and function
  vocabulary) and an advanced condition that accepts Java only. Is the
  advanced condition a Python expression in v2?
- Trigger conditions (RunIf). v1 evaluates them as Python; v2 as found has
  its own mini-language (finding 16).
- Config values. `${context.x}` substitution, and v1's bare `context.x`
  substitution, in strings such as file paths. May a config value be a full
  expression?
- One language in two positions: per row (translated into Polars) and once
  per job (evaluated when the value is needed). What is allowed in each.

Builds on
[Python expressions: what is allowed and how it reads](16-python-expressions-allowed.md).

## Answer

Resolved 2026-10-05 by assumption. The dev stopped the question rounds and
asked for the build ("make your own assumptions based on the answers I have
given till now, and then go ahead and build the entire V2 ... when I test it
out, then we can make changes"). What follows is what was built. Each point
is a default the dev can overturn.

- Filter rows: the structured `conditions` keep v1's operator and function
  vocabulary; the advanced condition is a Python expression in v2 (key
  `condition`, v1's `advanced_cond` as an alias).
- RunIf conditions keep v1's own dialect exactly (Python with the Java
  left-overs the converter leaves, values substituted in first), because v1
  job configs carry them and v1 runs them without Java. Code:
  `src/v2/engine/conditions.py`, checked against v1's trigger manager.
- Config values are not expressions. They take `${context.x}` and v1's bare
  `context.x`, nothing more.
