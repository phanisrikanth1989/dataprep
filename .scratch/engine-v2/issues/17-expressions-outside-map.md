# 17 - Expressions outside Map

Status: open
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
