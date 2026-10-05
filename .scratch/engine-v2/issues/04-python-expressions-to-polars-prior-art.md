# 04 - Translating Python expressions to Polars: prior art and mapping

Status: open
Type: research

## Question

What already exists for turning Python-syntax expressions into Polars
expressions without running Python per row, and what does a faithful mapping
look like? Primary sources only; Polars facts stamped against the range this
repo pins (`polars>=1.38,<2.0`; 1.44.2 is installed).

Specifically:

1. Prior art, with links and licences: Polars' own machinery (the bytecode
   parser that suggests native expressions for `map_elements` lambdas,
   `pl.sql_expr` and `SQLContext`) and third-party approaches (AST-based
   translators, ibis, narwhals, others). For each: what it covers, how mature
   it is, and whether it is usable as a dependency or only as a reference.
   Adding any dependency is the user's decision, so report options, do not
   choose.
2. A mapping table from Python constructs to Polars expressions for what v1
   users write in PyMap (`src/v1/engine/components/transform/py_map.py`
   documents the namespace): attribute and item access on rows; arithmetic
   and comparison operators; `and` / `or` / `not`; conditional expressions;
   `in`; `is None`; string methods and slicing; `len`, `str`, `int`, `float`,
   `round`, `abs`, `min`, `max`; f-strings and `+` concatenation; `re`
   functions; `math` functions; `datetime` operations; `Decimal`.
3. For each mapped construct, where Polars' result differs from what Python
   gives row by row: None versus null propagation, `==` with None, integer
   division and modulo signs, division by zero, string plus number, rounding
   mode, truthiness, short-circuiting.
4. Constructs with no native Polars equivalent. These become refusals.

Feeds [Expression translator spike](15-expression-translator-spike.md) and
[Python expressions: what is allowed and how it reads](16-python-expressions-allowed.md).
