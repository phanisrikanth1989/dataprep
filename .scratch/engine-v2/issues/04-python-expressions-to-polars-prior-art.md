# 04 - Translating Python expressions to Polars: prior art and mapping

Status: resolved
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

## Answer

Resolved 2026-10-05 by a research agent. The full note, every claim cited or
labelled as an observation:
[Translating Python expressions to Polars: prior art and mapping](../research/2026-10-05-python-expressions-to-polars.md)
(written on a throwaway research branch, since deleted; this copy is the
record). Its section 3 is 328 Python/Polars pairs run both ways on polars
1.44.2 and Python 3.14.6 on one Mac: provisional for the target servers, and
nothing was run on polars 1.38 to 1.43.

The gist, by part:

1. Prior art. No tool turns Python expression text into faithful Polars
   expressions. Polars' own bytecode parser is private, handles one-column
   lambdas and returns a suggestion string. `pl.sql_expr` parses SQL.
   polarify (BSD-3, last release 2025-05) rewrites `if` / `else` only. ibis
   and narwhals do not read Python source. The closest precedents for "a
   documented Python subset, refuse the rest" are pandas `eval` and ibis'
   UDF compiler, both walking the syntax tree with the standard library's
   `ast`. Evaluating the text once against `pl.col` objects is not an
   option: `and`, `or`, `not`, `if`, `in`, `len`, `int`, `round` and string
   methods raise, while `is None`, `str()` and f-strings silently return a
   constant and `np.sqrt` silently inserts a Python callback.
2. Mapping. The note's section 2 maps names, arithmetic, comparison, boolean
   logic, conditionals, builtins, string methods, `re`, `math`, `datetime`
   and `Decimal` to Polars expressions. A faithful mapping needs each
   operand's declared type when the job loads: `+`, `len`, `in`, indexing,
   `not`, `and` / `or` and bare truthiness each map differently per type.
3. Where results differ from row-by-row Python.
   - Same on both sides: `//` and `%` for every sign, `/`, `round(x)`
     without digits, literal string methods, `len`, constant slices.
   - None: Python raises per row, Polars yields null and carries on.
     `== None` is null for every row; `is None` maps exactly to `is_null()`.
   - `&`, `|`, `~` are bitwise on integers: `1 and 2` becomes 0, `1 or 2`
     becomes 3, `not 0` becomes -1, with no error.
   - Division by zero gives inf, NaN or null instead of raising; Int64
     overflow wraps silently.
   - `round(x, n)` with digits differs in both directions: `2.675` to two
     places is `2.68` against Python's `2.67`; `0.45` to one place is `0.4`
     against `0.5`.
   - Short-circuiting. `&` and `|` always evaluate both sides. `when/then`
     evaluated both branches on all rows before 1.44.0 (read from source)
     and masks the unselected rows only from 1.44.0, so a guard like
     `int(s) if s.isdigit() else 0` is version-sensitive inside the pin.
   - Errors are per query, not per row, and predicate pushdown can remove
     one.
   - Regex is Rust's dialect: no lookaround or backreferences, replacement
     groups are `${1}` not `\1`, and a pattern with no ASCII punctuation is
     silently treated as a literal.
   - Branches of different types are silently cast to a common type.
4. No native equivalent, so refused: statements, comprehensions, `lambda`,
   calls on unrecognised names, "this one row raises", a value whose type
   varies by row, and the rest of the note's section 4.

One finding changes a question rather than answering it: v1's PyMap is not a
plain-Python baseline. It hands pandas rows to `eval`, and a missing value
arrives as `nan`, even in a string column, not as `None`. "Same as Python"
and "same as v1's PyMap" are different targets; the choice now sits in
[Python expressions: what is allowed and how it reads](16-python-expressions-allowed.md).

Re-checked independently on polars 1.44.2 before the note was accepted
(scripts not kept): the evaluate-once failures in 1; the `//` and `%` signs,
the bitwise results, division by zero, the `round` differences, the regex
replacement and literal-pattern behaviour and a guarded cast inside
`when/then` in 3; and, on pandas 3.0.5, that a missing string reaches a v1
row as `nan`.

Could not establish: behaviour on polars 1.38 to 1.43 by execution; which
constructs real PyMap expressions use (that is
[Usage count of real v1 jobs](01-usage-count-of-real-v1-jobs.md)); what
Polars 2.0 changes; whether the 1.44 masking is meant to stay.

Surfaced for
[Which Polars versions v2 supports](28-which-polars-versions-v2-supports.md):
two more in-range changes, both in 1.44.0 -- `when/then` masking, and NaN
handling in `min_horizontal` / `max_horizontal`.
