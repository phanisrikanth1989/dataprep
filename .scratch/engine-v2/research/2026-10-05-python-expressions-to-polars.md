# Translating Python expressions to Polars: prior art and mapping (ticket 04)

Researched: 2026-10-05. Polars facts are stamped against **polars 1.44.2**
(tag `py-1.44.2`, uploaded to PyPI 2026-09-09, the latest stable release on the
research date; 2.0.0rc2 of 2026-09-20 exists as a pre-release and is outside
the repo pin `polars>=1.38,<2.0`). Where a fact was also checked at the low end
of the pin it says "1.38.0 source" (tag `py-1.38.0`; 1.38.0 itself is yanked on
PyPI, 1.38.1 is the lowest installable release). Python facts are stamped
against **Python 3.14** (docs.python.org/3.14); the repo requires 3.12+.

Sources: Polars source at those tags (github.com/pola-rs/polars); the installed
1.44.2 package's docstrings, which are the text docs.pola.rs/api/python/stable
serves (that tree is the whole 1.x line, there is no per-minor tree: its
version switcher lists only dev, 2 (pre-release), 1 (stable), 0.20, 0.19,
0.18); the Polars user guide; Polars release notes, pull requests and issues
on GitHub; the Python language reference and library docs; docs.rs for the
`regex` and `chrono` crates that the Polars docstrings point to; and for each
third-party project its own repository, documentation and PyPI metadata.
No blogs, no Stack Overflow.

Observations: every item marked "obs", and every row of the tables in
section 3, was run with the repo venv (`.venv/bin/python`: polars 1.44.2,
polars-runtime-32 1.44.2, CPython 3.14.6, pandas 3.0.5, numpy 2.5.2) on one
arm64 Mac. They are labelled "observed on polars 1.44.2, Python 3.14". They
show what that build does; they are not documented guarantees, nothing was run
on polars 1.38-1.43, and they are provisional for the target servers.

Shorthand used below:
- `pl-src:PATH#Lx` = https://github.com/pola-rs/polars/blob/py-1.44.2/PATH#Lx
- `pl-api:NAME` = https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.NAME.html
- `py-ref:ANCHOR` = https://docs.python.org/3.14/reference/expressions.html#ANCHOR
- `py-lib:PAGE#ANCHOR` = https://docs.python.org/3.14/library/PAGE.html#ANCHOR
- `obs` = observed on polars 1.44.2, Python 3.14 (see above)
- `N1`, `Z2`, `DT17` ... = row ids in the tables of section 3
- `c` = `pl.col` in every Polars expression shown

---

## Summary

1. No tool was found that turns Python expression text into faithful Polars expressions: Polars' own bytecode parser is private, takes one-column lambdas only, returns a suggestion string and maps `and`/`or`/`not` to `&`/`|`/`~` unchanged; polarify covers `if`/`else` only; `pl.sql_expr` parses SQL, not Python; ibis and narwhals do not read Python source (1.1, 1.2).
2. Evaluating the text once against `pl.col` objects is not enough: `and`, `or`, `not`, `if`-`else`, `in`, chained comparisons, `len`, `int`, `round`, string methods and `re` raise, while `x is None`, `str(x)` and f-strings silently return a constant and `np.sqrt(x)` silently inserts a Python callback; those constructs are visible only to an approach that inspects the code (syntax tree or bytecode) rather than runs it (1.1.1, 1.3, obs).
3. A faithful mapping needs each operand's declared type when the job loads: `+`, `len`, `in`, `x[i]`, `not`, `and`/`or` and bare truthiness each map to a different Polars expression per type (2, 3.7, 3.8).
4. Same on both sides, observed: `//` and `%` for every sign combination (int and float), `/`, `round(x)` without digits, literal string methods (`upper`, `lower`, `replace`, `startswith`, `split(sep)`, `strip(chars)`), `len`, and slices with constant bounds (3.3, 3.6, 3.13, 3.14).
5. None: Python raises per row, Polars yields null and carries on; `== None` is null for every row; `is None` maps exactly to `is_null()`, and `==` / `in` map exactly only through `eq_missing` / `is_in(nulls_equal=True)` (3.1, 3.2).
6. `&`, `|`, `~` are bitwise on integers, so `1 and 2` gives 0, `1 or 2` gives 3 and `not 0` gives -1 without any error; `not x` on a null boolean gives null where Python gives True, so a filter drops the row; exact forms exist through `when/then` and `fill_null` (3.7, 3.8).
7. Division by zero never raises in Polars except for Decimal: `/` gives inf or NaN and integer `//` and `%` give null; Int64 overflow wraps silently; an integer literal beyond Int64 silently turns the result null or Float64 (3.4, 3.11).
8. `round(x, n)` with n >= 1 differs in both directions (2.675, 0.35, 0.45, 0.005) although both sides say "half to even": Polars multiplies by 10^n and then rounds, Python rounds the exact binary value; Decimal rounding agrees (3.6).
9. Short-circuiting: `&` and `|` always evaluate both sides; `when/then/otherwise` evaluates both branches on all rows in 1.38-1.43 (source) and masks unselected rows only from 1.44.0, as a performance change the documentation does not promise, so guards like `int(s) if s.isdigit() else 0` are version-sensitive inside the pin (3.9).
10. Errors are per query, not per row, and the optimizer can remove them: a later filter pushed below a strict cast suppresses the cast's error; Polars' own list of data-dependent failures is short (strict cast, strptime, `list.get`, `replace_strict`) (3.9).
11. Polars reports only some bad expressions from the schema alone; several need a zero-row run and a few surface only on data (strict casts, an invalid strptime format, String to Boolean cast); branches of different types are silently cast to a common type, int with str to String (3.5, 3.20).
12. Regex is the Rust `regex` crate: no lookaround or backreferences, `$`, `\w` and `\s` differ, replacement groups are `${1}` not `\1`, and Polars silently treats a pattern without ASCII punctuation as a literal, which changes what `$` means in the replacement (3.15).
13. The v1 baseline is not plain Python: v1 PyMap hands numpy/pandas scalars to `eval` and a missing value is `nan` (even in a string column), not None, so "same as Python" and "same as v1 PyMap" are different targets (3.21).
14. Not established: behaviour on 1.38-1.43 by execution, what real PyMap expressions contain, what changes at Polars 2.0, and behaviour on the target servers (last section).

---

## 1. Prior art

### 1.1 Polars' own machinery

Polars has three relevant pieces. None is a Python-to-Polars translator.

#### 1.1.1 Operator overloading on `pl.Expr` ("evaluate the text once")

`pl.Expr` overloads the arithmetic, comparison and bitwise operators, so Python
code that uses only those builds an expression when it is run once with columns
in place of values. `pl.col` also allows attribute access: `pl.col.price` is
`col("price")` (obs); `pl.col['price']` raises `TypeError: 'Col' object is not
subscriptable` (obs, row V4).

What cannot be overloaded is fixed by Python, not Polars. `and`, `or`, `not`,
`if`-`else` and chained comparisons take the truth value of their operand:
"The expression x and y first evaluates x; if x is false, its value is
returned; otherwise, y is evaluated and the resulting value is returned" and
"x < y <= z is equivalent to x < y and y <= z" (`py-ref:boolean-operations`,
`py-ref:comparisons`). `Expr.__bool__` always raises
(`pl-src:py-polars/src/polars/expr/expr.py#L321-L332`), and its message is
itself a three-line mapping table: "instead of `pl.col('a') and pl.col('b')`,
use `pl.col('a') & pl.col('b')`", "instead of `pl.col('a') in [y, z]`, use
`pl.col('a').is_in([y, z])`", "instead of `max(pl.col('a'), pl.col('b'))`, use
`pl.max_horizontal(pl.col('a'), pl.col('b'))`".

What one `eval` of a PyMap-style expression returns when `row1.col` and
`row1['col']` are bound to `pl.col("col")` and `re`, `math`, `datetime`,
`Decimal`, `json`, `np` are in scope (obs):

| expression evaluated once | outcome |
|---|---|
| `row1.price * 1.05` | pl.Expr: `[(col("price")) * (dyn float: 1.05)]` |
| `row1['price'] * 1.05` | pl.Expr: `[(col("price")) * (dyn float: 1.05)]` |
| `abs(row1.a)` | pl.Expr: `col("a").abs()` |
| `row1.a > 5` | pl.Expr: `[(col("a")) > (dyn int: 5)]` |
| `row1.a == None` | pl.Expr: `[(col("a")) == (null)]` |
| `row1.a is None` | NOT an Expr -> bool: `False` |
| `row1.a is not None` | NOT an Expr -> bool: `True` |
| `row1.a > 5 and row1.b < 3` | raises TypeError: the truth value of an Expr is ambiguous |
| `not row1.flag` | raises TypeError: the truth value of an Expr is ambiguous |
| `(row1.a > 5) & (row1.b < 3)` | pl.Expr: `[([(col("a")) > (dyn int: 5)]) & ([(col("b")) < (dyn int: 3)])]` |
| `~row1.flag` | pl.Expr: `col("flag").not()` |
| `0 < row1.a < 10` | raises TypeError: the truth value of an Expr is ambiguous |
| `'x' if row1.a > 5 else 'y'` | raises TypeError: the truth value of an Expr is ambiguous |
| `row1.a in (1, 2, 3)` | raises TypeError: the truth value of an Expr is ambiguous |
| `'ab' in row1.s` | raises TypeError: argument of type 'Expr' is not a container or iterable |
| `row1.s + '-' + row1.t` | pl.Expr: `[([(col("s")) + ("-")]) + (col("t"))]` |
| `row1.s.upper()` | raises AttributeError: 'Expr' object has no attribute 'upper' |
| `row1.s[0:3]` | raises TypeError: 'Expr' object is not subscriptable |
| `len(row1.s)` | raises TypeError: object of type 'Expr' has no len() |
| `str(row1.a)` | NOT an Expr -> str: `'col("a")'` |
| `int(row1.s)` | raises TypeError: int() argument must be a string, a bytes-like object or a real number, not 'Expr' |
| `round(row1.a, 2)` | raises TypeError: type Expr doesn't define __round__ method |
| `min(row1.a, row1.b)` | raises TypeError: the truth value of an Expr is ambiguous |
| `f'{row1.s}-{row1.a}'` | NOT an Expr -> str: `'col("s")-col("a")'` |
| `re.sub(r'\s+', '_', row1.s)` | raises TypeError: expected string or bytes-like object, got 'Expr' |
| `math.sqrt(row1.a)` | raises TypeError: must be real number, not Expr |
| `np.sqrt(row1.a)` | pl.Expr: `col("a").python_udf()` |
| `row1.d.year` | raises AttributeError: 'Expr' object has no attribute 'year' |
| `row1.d + datetime.timedelta(days=1)` | pl.Expr: `[(col("d")) + (1d)]` |
| `Decimal(row1.s)` | raises TypeError: conversion from Expr to Decimal is not supported |
| `row1.a or 0` | raises TypeError: the truth value of an Expr is ambiguous |
| `[row1.a, row1.b]` | NOT an Expr -> list: `[<Expr ['col("a")'] at 0x...>, <Expr ['col("b")'] at 0x...>]` |
| `row1.s.str.to_uppercase()` | pl.Expr: `col("s").str.to_uppercase()` |

Three outcome classes, all obs:
- Builds an expression: arithmetic, comparisons, `abs`, `+` on strings, adding
  a `timedelta` or `Decimal` constant.
- Raises (loud): `and`, `or`, `not`, `if`-`else`, chained comparison, `in`,
  `min`/`max`, `bool`, `len`, `int`, `float`, `round`, string methods and
  slicing, `re.*`, `math.*`, `strptime`, `Decimal(x)`, `json.loads`.
- Silently wrong: `row1.a is None` is the Python constant `False` and
  `is not None` is `True`; `str(row1.a)` is the text `col("a")`, and f-strings
  and `%` formatting build text from it; `row1.a == None` is an expression that
  is null on every row (Polars warns: "Comparisons with None always result in
  null. Consider using `.is_null()` or `.is_not_null()`."); `np.sqrt(row1.a)`
  becomes `col("a").python_udf()`, a Python callback at run time; a list or
  tuple of columns stays a Python list or tuple.
- It also lets the Polars API through: `row1.s.str.to_uppercase()` and
  `row1.a.fill_null(0)` are accepted, so the accepted language would be
  "Python plus everything `pl.Expr` has".

numexpr is built this way (section 1.2).

#### 1.1.2 The bytecode parser behind `PolarsInefficientMapWarning`

`polars/_utils/udfs.py` (`pl-src:py-polars/src/polars/_utils/udfs.py`, 1,266
lines; the installed 1.44.2 file is byte-identical to the tag). When
`map_elements` is handed a simple function, `warn_on_inefficient_map`
(L1219-L1263) disassembles it with `dis.get_instructions` and, if every opcode
is recognised, emits a `PolarsInefficientMapWarning`
(https://docs.pola.rs/api/python/stable/reference/api/polars.exceptions.PolarsInefficientMapWarning.html)
whose text contains a suggested native expression.

Facts from the source:
- Private. The module is `polars._utils`; neither it nor `BytecodeParser` nor
  `warn_on_inefficient_map` appears in the API reference inventory (3,285
  entries). The public surface is the warning text.
- Output is text. `BytecodeParser.to_expression(col) -> str | None` (L507);
  obs: the return type is `str`, for example `'pl.col("c") + 1'`.
- One parameter only. `_get_param_name` returns None unless the function has
  exactly one parameter: "we do not parse/handle functions with > 1 params"
  (L412-L423). `map_target="frame"` raises `NotImplementedError` (L1235-L1237).
- One return only. Functions with more than one `RETURN_VALUE` are excluded
  (L473-L479), which excludes conditional expressions.
- Lookup tables: binary operators (L60-L73); unary `-`, `+` and `not` -> `~`
  (L101-L105); `and`/`or` jump opcodes -> `&`/`|` (L75-L90); `in`/`not in` ->
  `is_in` and `is` (L710-L719); subscript of a dict in the caller's scope ->
  `replace_strict` (L666-L667, L720-L726); 23 `math` functions (L120-L146);
  23 numpy functions (L150-L177); `int`/`float`/`str` -> `cast(pl.Int64 /
  Float64 / String)` and `abs` (L190-L195); 12 string and 10 temporal methods
  (L196-L221); 8 temporal attributes (L180-L189); `json.loads` ->
  `str.json_decode` and `datetime.strptime(x, CONST)` ->
  `str.to_datetime(format=...)` (L237-L292).
- For `str.replace` Polars itself emits `str.replace_all(old, new,
  literal=True)` (L1117-L1123).
- Tied to the Python version. Flags `_MIN_PY311`, `_MIN_PY312`, `_MIN_PY314`
  (L50-L52) select opcode handling per release (L74-L90, L1152-L1173). The
  Python docs say of bytecode: "No guarantees are made that bytecode will not
  be added, removed, or changed between versions of Python. Use of this module
  should not be considered to work across Python VMs or Python releases."
  (`py-lib:dis#module-dis`).

What it returned for PyMap-style one-column lambdas (obs; body shown is the
lambda body with `x` as the parameter):

| lambda body | BytecodeParser.to_expression('c') |
|---|---|
| `x + 1` | `pl.col("c") + 1` |
| `x > 5 and x < 10` | `(pl.col("c") > 5) & (pl.col("c") < 10)` |
| `5 < x < 10 (chained)` | None (can_attempt_rewrite() is False) |
| `not x` | `~pl.col("c")` |
| `x is None` | `pl.col("c") is None` |
| `x == None` | `pl.col("c") == None` |
| `x in (1, 2, 3)` | `pl.col("c").is_in((1, 2, 3))` |
| `'ab' in x` | `'ab'.is_in(pl.col("c"))` |
| `'a' if x > 1 else 'b'` | None (can_attempt_rewrite() is False) |
| `x or 0` | `pl.col("c") \| 0` |
| `len(x)` | None (can_attempt_rewrite() is False) |
| `round(x, 2)` | None (can_attempt_rewrite() is False) |
| `str(x)` | `pl.col("c").cast(pl.String)` |
| `int(x)` | `pl.col("c").cast(pl.Int64)` |
| `min(x, 5)` | None (can_attempt_rewrite() is False) |
| `f'{x}!'` | None (can_attempt_rewrite() is False) |
| `x.upper()` | `pl.col("c").str.to_uppercase()` |
| `x.strip().upper()` | `pl.col("c").str.strip_chars().str.to_uppercase()` |
| `x.replace('a', 'b')` | `pl.col("c").str.replace_all('a','b',literal=True)` |
| `x.startswith(('a', 'b'))` | `pl.col("c").str.contains(r'^(a\|b)')` |
| `x.split(',')` | None (can_attempt_rewrite() is False) |
| `x[1:3]` | None (rewrite attempted, no result) |
| `MAPPING[x]` | `pl.col("c").replace_strict(MAPPING)` |
| `re.sub(r'\s+', '_', x)` | None (can_attempt_rewrite() is False) |
| `math.sqrt(x)` | `pl.col("c").sqrt()` |
| `math.log(x, 2)` | None (can_attempt_rewrite() is False) |
| `json.loads(x)` | `pl.col("c").str.json_decode()` |
| `datetime.datetime.strptime(x, '%Y-%m-%d')` | `pl.col("c").str.to_datetime(format="%Y-%m-%d")` |
| `x.year` | `pl.col("c").dt.year()` |
| `x.weekday()` | None (can_attempt_rewrite() is False) |
| `x.isoweekday()` | `pl.col("c").dt.weekday()` |
| `x['a'] + x['b'] (row as dict)` | None (rewrite attempted, no result) |
| `x.a + x.b (row attr)` | None (can_attempt_rewrite() is False) |
| `two params: a + b` | None (can_attempt_rewrite() is False) |

Reading (obs): it is a hint generator, not a translator. Several hints are not
equivalent to the Python: `x is None` -> the text `pl.col("c") is None` (plain
`False` if evaluated), `'ab' in x` -> `'ab'.is_in(pl.col("c"))` (not valid),
`x or 0` -> `pl.col("c") | 0` (bitwise, section 3.8), `not x` ->
`~pl.col("c")` (section 3.7), `json.loads(x)` -> `str.json_decode()` (a
`TypeError` as written: `dtype` is required). A row with two columns
(`x.a + x.b`, `x['a'] + x['b']`) is not handled at all.

As an option: not usable as a dependency (private API, text output, one
column). Its lookup tables are a compact, Polars-maintained seed for section 2.

#### 1.1.3 `pl.sql_expr`, `SQLContext`, `pl.sql`

- `pl.sql_expr(sql: str | Sequence[str]) -> Expr | list[Expr]`: "Parse one or
  more SQL expressions to Polars expression(s)." (`pl-api:sql_expr`). Public;
  its 1.44.2 docstring carries no stability warning. `SQLContext`: "This
  functionality is considered **unstable**, although it is close to being
  considered stable."
  (https://docs.pola.rs/api/python/stable/reference/sql/python_api.html).
- Among the documented APIs it is the one that parses expression text written
  by a person (`Expr.deserialize` and `Expr.from_json` read serialised
  expressions), and the language is SQL. About 115 SQL function names are
  registered
  (`pl-src:crates/polars-sql/src/functions.rs#L806-L924`). A request to build
  an expression from the printed form of an expression was closed as not
  planned (https://github.com/pola-rs/polars/issues/20557, closed 2025-01-05).

What it returned on a small frame (a, b Int64; f Float64; s, t String; d Date;
p Boolean; four rows including a null and a zero) (obs):

| Python intent | SQL passed to pl.sql_expr | result on the frame |
|---|---|---|
| `row1.a * 1.05` | `a * 1.05` | Float64: [7.3500000000000005, -7.3500000000000005, None, 0.0] |
| `row1.a // row1.b` | `a // b` | Int64: [3, -4, None, None] |
| `row1.a ** 2` | `a ^ 2` | parse: SQLInterfaceError: operator BitwiseXor is not currently supported |
| `row1.a == 7 (python spelling)` | `a == 7` | Boolean: [True, False, None, False] |
| `row1.a == None` | `a = NULL` | Boolean: [None, None, None, None] |
| `row1.a > 0 and row1.b > 0` | `a > 0 AND b > 0` | Boolean: [True, False, None, False] |
| `'pos' if row1.a > 0 else 'neg'` | `CASE WHEN a > 0 THEN 'pos' ELSE 'neg' END` | String: ['pos', 'neg', 'neg', 'neg'] |
| `row1.s + '!'` | `s \|\| '!'` | String: ['Hello!', ' x !', None, '!'] |
| `f'{row1.s}-{row1.a}'` | `CONCAT(s, '-', a)` | String: ['Hello-7', ' x --7', '-', '-0'] |
| `row1.t.replace('.', '-')` | `REPLACE(t, '.', '-')` | String: ['a-b', '12', 'x', None] |
| `row1.s.find('l')` | `STRPOS(s, 'l')` | UInt32: [3, 0, 0, 0] |
| `re.search(r'^\d+$', row1.t)` | `t ~ '^\d+$'` | Boolean: [False, True, False, None] |
| `re.sub` | `REGEXP_REPLACE(t, '\d', '#')` | parse: SQLInterfaceError: unsupported function 'regexp_replace' |
| `int(row1.t) non-strict` | `TRY_CAST(t AS BIGINT)` | Int64: [None, 12, None, None] |
| `min(row1.a, row1.b)` | `LEAST(a, b)` | Int64: [2, -7, 2, 0] |
| `row1.d.year` | `EXTRACT(YEAR FROM d)` | Int32: [2024, 2024, None, 2021] |
| `lambda / python call` | `upper(s) if a > 0 else s` | parse: SQLInterfaceError: invalid expression (found unexpected token 'a') |
| `python method call` | `s.upper()` | parse: SQLInterfaceError: unsupported function 's' |
| `python f-string` | `f'{s}'` | Float64: [2.5, 0.125, None, -0.5] |
| `row1.a (qualified)` | `row1.a` | run: ColumnNotFoundError: unable to find column "row1"; valid columns: ["a", "b", "f", "s", "t", "d", "p"] |

Reading (obs): Python syntax is not accepted (conditional expression and
method call fail to parse), and `f'{s}'` is accepted but means "column f" and
returns its values. Semantics are SQL's and differ from both Python and the
`pl.Expr` forms of section 2 in places: `CONCAT` treats NULL as empty while
`||` propagates it; `STRPOS` is 1-based and 0 when absent; `REGEXP_REPLACE`
and `^` are not supported; a qualified name `row1.a` is read as table.column
and fails.

As an option: usable without a new dependency as a target one could emit
(Python syntax tree -> SQL text -> `pl.sql_expr`), at the price of a second
language's semantics in the middle; otherwise a reference.

Also in Polars: `Expr.meta.root_names()` lists the columns an expression
reads, `str(expr)` prints it, and `Expr.meta.serialize()` /
`pl.Expr.deserialize` round-trip it (obs; `pl-api:Expr.meta.root_names`,
`pl-api:Expr.meta.serialize`). Section 3.20 covers what Polars checks before
data arrives.

### 1.2 Third-party projects

Release dates and licences are from PyPI metadata and each repository on
2026-10-05.

| Project | What it does for this problem | Licence | Latest release | As a dependency / as a reference |
|---|---|---|---|---|
| polarify (github.com/Quantco/polarify) | `@polarify` reads a function's source with `ast` and rewrites `if`/`elif`/`else`, conditional expressions, assignments and `match` into `pl.when().then().otherwise()`; everything else is left to `pl.Expr` operator overloading. Chained comparisons raise "Polars can't handle chained comparisons"; any other expression node raises "Unsupported expression type" (`polarify/main.py`). README: "still in an early stage of development and doesn't support the full Python language"; unary `not` is listed as TODO. No handling of None, truthiness or types. | BSD-3-Clause | 0.2.1, 2025-05-15 (first 0.1.0 2023-07-30; 8 releases). Repo last pushed 2026-09-07, 145 stars, not archived | Dependency possible: pure Python, requires `polars<2,>=0.14.24`. It takes function definitions, not expression strings, and covers only the conditional part. Its 389-line `main.py` is a readable reference for lowering `if` to `when`. |
| polars-expr-transformer (github.com/Edwardvaneechoud/polars_expr_transformer) | `simple_function_to_expr('[price] * [quantity]')`: its own formula language (`[column]`, `if .. then .. else .. endif`, `concat(...)`); README: "Write simple, SQL-like expressions". Not Python syntax. | LICENSE file and GitHub: Apache-2.0; README badge: MIT; PyPI metadata: none declared | 0.6.4, 2026-10-01 (116 releases since 2024-05-14); 1 star | Dependency possible (`polars<2.0.0,>1.8.2`, `pydantic>=2.9.2`), but it is another custom language. Reference only for this ticket. |
| ibis-framework (github.com/ibis-project/ibis) | A dataframe expression API with "more than 20 backends" (README). The Polars backend translates ibis operation nodes to `pl.Expr` through a `translate` registry (139 registrations in `ibis/backends/polars/compiler.py` at 12.0.0). It does not read Python source: the user writes ibis expressions. Python UDFs on the Polars backend run through `map_batches` over Python lists (same file, L1419-L1451). Ibis also contains an `ast` visitor that translates a Python subset to JavaScript for BigQuery UDFs and raises `NotImplementedError` for unknown nodes (`ibis/backends/sql/compilers/bigquery/udf/core.py`). | Apache-2.0 | 12.0.0, 2026-02-07 | Dependency possible, bringing a second expression API plus sqlglot, parsy, toolz, atpublic, python-dateutil, typing-extensions, tzdata, and leaving the Python-text step unsolved. Reference for an operation-by-operation Polars mapping and for the visitor-with-refusal technique. |
| narwhals (github.com/narwhals-dev/narwhals) | "Extremely lightweight and extensible compatibility layer between dataframe libraries"; "Just use a subset of the Polars API" (README). Input is Polars-style expressions, output is pandas, PyArrow and others: the opposite direction. | MIT | 2.26.0, 2026-09-08 | Not applicable to this problem. |
| pandas `eval` / `query` (pandas.pydata.org/docs/user_guide/enhancingperf.html) | Python-syntax expression strings evaluated in vectorised form over pandas objects. Documented subset: arithmetic without shifts, comparisons including chained ones, `and`/`or`/`not`, list and tuple literals, attribute access, subscripts, a fixed list of math functions. Documented exclusions: "Function calls other than math functions", "is / is not operations", "if expressions", lambda, comprehensions, dict and set literals, generators, statements. Implemented as an `ast.NodeVisitor` with a deny list that raises `NotImplementedError("'X' nodes are not implemented")` (`pandas/core/computation/expr.py` at v3.0.6). | BSD-3-Clause | 3.0.6, 2026-09-17 | Reference only (targets pandas, not Polars). The closest precedent for a documented Python subset with refusal for the rest. |
| numexpr (github.com/pydata/numexpr) | Expression strings compiled for a vector VM over NumPy arrays. `stringToExpression` compiles the string and `eval`s it once with names bound to proxy nodes (`numexpr/necompiler.py` L286-L324 at v2.14.2): the "evaluate once" technique of 1.1.1. Its docs show the consequence: "Bitwise and logical operators (and, or, not, xor): &, \|, ~, ^", and conditionals are `where(bool, number1, number2)` (numexpr.readthedocs.io/en/latest/user_guide.html). | MIT | 2.14.2, 2026-07-18 | Reference only (NumPy, not Polars). |
| simpleeval, asteval, evalidate | Restricted evaluators/validators that walk the `ast` of an expression. They interpret on each evaluation; in simpleeval `and`/`or`/`if` use Python truthiness (`_eval_boolop`, `_eval_ifexp` in `simpleeval.py`), so they do not build Polars expressions. | MIT for all three (PyPI metadata) | simpleeval 1.0.8, 2026-09-12; asteval 1.0.10, 2026-08-21; evalidate 2.1.4, 2026-03-02 | Reference only (allow-list design). Used directly they would run Python per row. |
| RestrictedPython (github.com/zopefoundation/RestrictedPython) | "a defined subset of the Python language which allows to provide a program input into a trusted environment" (PyPI summary). A policy tool, not a translator. | ZPL-2.1 | 8.5, 2026-08-19; `requires_python <3.16,>=3.10` | Reference only. |
| Pony ORM (github.com/ponyorm/pony) | Decompiles bytecode back to a syntax tree before translating to SQL (`pony/orm/decompiling.py`, 1,384 lines with per-release branches `PY310` to `PY314`). Same technique family as 1.1.2. | Apache-2.0 | 0.7.20, 2026-08-09 (previous 0.7.19, 2024-08-27); `requires_python <3.15,>=3.10` | Reference only; shows the bytecode route being reworked for each Python release. |
| numba (numba.pydata.org) | Compiles Python functions to machine code; the Polars user guide shows it for fast UDFs through `map_batches` (docs.pola.rs/user-guide/expressions/user-defined-python-functions/). The result is an opaque function to Polars, not a native expression. | BSD (as declared on PyPI) | 0.68.0, 2026-09-30; status "4 - Beta"; needs llvmlite and `numpy<2.6` | Does not meet the "native Polars expression" rule; listed for completeness. |

Also looked at and set aside: siuba (last release 0.4.4, 2023-09-19, requires
`pandas<2.1.0`), pydiverse-transform (its own pipe API with a Polars backend),
sqlglot (SQL transpiler that ibis depends on).

The standard library's `ast` module is what every tree-based entry above
builds on. Two facts from its documentation matter for a translator that must
run on 3.12 through 3.14: "The abstract syntax itself might change with each
Python release", and the pre-3.8 node classes `ast.Num`, `ast.Str`,
`ast.Bytes`, `ast.NameConstant` and `ast.Ellipsis` "were removed in Python
3.14" in favour of `ast.Constant`, while `ast.TemplateStr` (t-strings) was
"Added in version 3.14" (`py-lib:ast#module-ast`, `py-lib:ast#ast.Constant`,
`py-lib:ast#ast.TemplateStr`). obs on 3.14.6: `ast.parse(text, mode="eval")`
rejects assignments, imports, loops and `;` with `SyntaxError`, and PyMap-style
constructs parse to `Attribute`, `Subscript`, `BinOp`, `UnaryOp`, `Compare`,
`BoolOp`, `IfExp`, `Call`, `JoinedStr`/`FormattedValue`, `Constant`, `Name`,
`Slice`, `Tuple`, `Dict`, and for the constructs of section 4 `ListComp`,
`Lambda`, `NamedExpr`.

### 1.3 The three techniques seen

| Technique | Who uses it | What the sources show |
|---|---|---|
| Evaluate the text once against proxy objects | `pl.Expr` operators (1.1.1), numexpr, the parts polarify leaves untouched | Cannot see `and`/`or`/`not`/`if`/`in`/`is`/calls on builtins; numexpr documents `&`, `\|`, `~` instead of the keywords |
| Walk the syntax tree, map known nodes, refuse the rest | pandas `eval`, ibis' Python-to-JavaScript UDF compiler, polarify for control flow | Each documents or encodes an explicit subset and raises on anything else |
| Decompile bytecode | Polars' `BytecodeParser`, Pony ORM | Per-Python-release branches in both; Python documents bytecode as unstable |

---

## 2. Mapping table

How to read it. "Polars expression" is the form that reproduced Python on the
inputs tested, when one exists; the shorter naive form and what it does
instead are in section 3 under the row ids given. `x`, `y`, `s`, `d` stand for
already-translated operands. "exact" means no difference was observed on the
inputs listed in section 3, not that the two are proven equal.

Three things hold for the whole table:
- The translator must know operand types. The same Python spelling maps to
  different Polars expressions for String, numeric, Boolean, temporal and list
  operands (`+`, `len`, `in`, `x[i]`, `%`, `not`, `and`, `or`, any bare value
  used as a condition). v2 has declared schemas, so the types exist at load.
- String constants must be wrapped in `pl.lit`. A bare Python `str` passed to
  `then`, `otherwise`, `is_between` and similar is read as a column name
  (`pl.when` docstring, Notes; row X13).
- None is the general exception. Unless a row says otherwise, a None operand
  raises in Python and gives null in Polars (section 3.1).

### 2.1 Names and literals

| Python | Polars expression | Notes |
|---|---|---|
| `row1.col`, `row1['col']` | `pl.col("col")` | V1-V3. `pl.col` has attribute access but no item access (V4). In v1 each lookup row (`row2.col`) is a separate dict keyed by the plain column name (`py_map.py` `_build_row_dicts`); how v2 names lookup columns after a join is a v2 matter. A computed key (`row1[row1.k]`) has no equivalent. |
| `Var.x`, `Var['x']` | the translated expression of variable `x`, inlined or placed in an earlier `with_columns` | v1 evaluates variables in order for each row (`py_map.py` `_evaluate_variables_py`). Not probed. |
| `context.X`, `context['X']`, `globalMap.get('k', d)` | `pl.lit(value)` fixed when translated | The value is baked in; the as-found research (finding 9) shows the old v2 compiler keeping a stale context value. No parameter-binding API was found (last section). |
| int, float, str, bool, None constants | `pl.lit(v)` | obs dtypes: `1` Int32, `2**31` Int64, `2**63` UInt64, `2**64` and `10**20` Int128, `10**40` InvalidOperationError, `1.5` Float64, `None` Null. Mixed with an Int64 column the small literals adapt (`c.i + 1` stays Int64); the large ones do not (O5, O6). |
| `Decimal('1.10')` | `pl.lit(Decimal('1.10'))` | obs dtype Decimal(38, 2): the scale is the number of digits written. `Decimal('NaN')` and `Decimal('Infinity')` panic (`PanicException`, obs); 39 significant digits: `TypeError` (obs). |
| `datetime.date(...)`, `datetime.datetime(...)`, `datetime.timedelta(...)`, `datetime.time(...)` with constant arguments | build the Python object once, then `pl.lit` | obs dtypes Date, Datetime[us], Duration[us], Time. |
| tuple or list of constants | a Python list passed to `is_in`, or `pl.lit([...])` | `pl.lit((1, 2))` is List(Int64) (obs). |

### 2.2 Arithmetic

| Python | Polars expression | Notes |
|---|---|---|
| `x + y`, `x - y`, `x * y` (numbers) | `x + y`, `x - y`, `x * y` | Exact for Float64 (IEEE on both sides) and for Int64 until overflow, where Polars wraps (O1, O2). int + bool works (X9). |
| `x / y` | `x / y` | Exact, always Float64 (M3), except a zero divisor: inf / NaN instead of `ZeroDivisionError` (Z1, Z4). |
| `x // y` | `x // y` | Exact for every sign combination, int and float (M1, M4, M6). Zero divisor: null for integers, inf / NaN for floats (Z2, Z5). |
| `x % y` (numbers) | `x % y` | Exact for every sign combination (M2, M5). Zero divisor: null / NaN (Z3, Z6). On a string, Python `%` is formatting (2.6). |
| `x ** y` | `x ** y` | int ** non-negative int: exact until overflow (O4). int ** negative int: the query fails where Python returns a float (O8, O9). Negative base with a fractional exponent: NaN where Python returns a complex number (O10). Decimal base: not supported (K8). |
| `-x`, `+x`, `abs(x)` | `-x`, `+x`, `x.abs()` | Exact; `abs(-2**63)` wraps (O3). |
| `x & y`, `x \| y`, `x ^ y`, `~x` on integers | the same operators | Exact (O13). `<<` and `>>` have no `Expr` operator (O11); `x * 2**n` (O12) and `x // 2**n` reproduce them until overflow. |
| `divmod(x, y)`, `pow(x, y, z)` | none | W8. Two-argument `pow(x, y)` is `x.pow(y)`. |

### 2.3 Comparison, identity, membership

| Python | Polars expression | Notes |
|---|---|---|
| `x == y`, `x != y` | `x.eq_missing(y)`, `x.ne_missing(y)` | Exact including None on either side (N7, N9, N11). Plain `==` / `!=` give null when either side is None (N6, N8, N10). str against int: Python False, Polars fails the query (X6). NaN: Q1, Q2. Decimal against float: K10. |
| `x < y`, `<=`, `>`, `>=` | the same operators | Exact for non-None, non-NaN operands of one type. None: null (N5). NaN sorts above everything in Polars (Q3). date against datetime: Polars compares, Python raises (DT27). |
| `a < x < b` | `(a < x) & (x < b)`, or `x.is_between(a, b, closed=...)` | B16, B17. |
| `x is None`, `x is not None` | `x.is_null()`, `x.is_not_null()` | Exact (E5, E6). NaN is not null (Q6). |
| `x == None`, `x != None` | `x.is_null()`, `x.is_not_null()` (or `eq_missing(None)`) | E1-E4. |
| `pd.isna(x)`, `pd.notna(x)` | Float: `x.is_null() \| x.is_nan()`; other types: `x.is_null()`; negated for `notna` | Q9, Q10. In v1 this, not `is None`, is the test that detects a missing value (3.21). |
| `x is True` | `x.eq_missing(True)` | E8. |
| `x in (a, b, c)` with constants | `x.is_in([a, b, c], nulls_equal=True)` | Exact including None on either side (N21, N23). Without `nulls_equal` a None `x` gives null (N20, N22). A list of mixed types fails when built (obs). |
| `x not in (a, b)` | `~x.is_in([a, b], nulls_equal=True)` | N25. |
| `sub in s` (strings) | `s.str.contains(sub, literal=True)` | Exact (S12, S14). The default is a regex match (S13). |
| `x in row1.xs` (list column), `x in {dict literal}` | `xs.list.contains(x)`, `x.is_in(list_of_keys)` | obs. |

### 2.4 Boolean operators and conditionals

These need a truthiness function truthy(x) chosen by the operand's type
(Python's rule: "the following values are interpreted as false: False, None,
numeric zero of all types, and empty strings and containers",
`py-ref:boolean-operations`):

| Operand type | truthy(x) | Rows |
|---|---|---|
| Boolean | `x.fill_null(False)` | T6 |
| Int, Float, Decimal | `(x != 0).fill_null(False)` | T4, T5 (NaN is true on both sides) |
| String | `(x != '').fill_null(False)` | T2 |
| Date, Datetime, Duration, List | not probed | Python: every date and datetime is true; `timedelta(0)` and `[]` are false |

| Python | Polars expression | Notes |
|---|---|---|
| `not x` | `~truthy(x)` | Exact (T8; T10 and T12 show the equivalent `(x == 0).fill_null(True)` and `(x == '').fill_null(True)`). Plain `~x`: null for None (T7), bitwise on integers (T9), fails on String and Float (T11). |
| `x and y` | as a value: `pl.when(truthy(x)).then(y).otherwise(x)`; where only truth matters: `truthy(x) & truthy(y)` | Exact (B2, B8). Plain `x & y` differs for (None, False) (B1) and is bitwise on integers (B7). Both operands must share one type. |
| `x or y` | as a value: `pl.when(truthy(x)).then(x).otherwise(y)`; where only truth matters: `truthy(x) \| truthy(y)` | Exact (B4, B10, B13). `x.fill_null(y)` covers None but not `''` or `0` (B12). |
| `a if cond else b` | `pl.when(truthy(cond)).then(a).otherwise(b)` | Exact for a bare value through truthy(), None included (T13, T17, T18). A None inside a comparison raises in Python and selects `b` in Polars (T19). Branches of different types are unified silently (X11, X12). |
| `bool(x)` | `truthy(x)` | `x.cast(pl.Boolean)` keeps null (T3) and fails for String (T1). |

### 2.5 Builtins

| Python | Polars expression | Notes |
|---|---|---|
| `len(s)` | `s.str.len_chars()`; list column: `xs.list.len()` | Exact (U15). `len_bytes` is not (U16). Result is UInt32. |
| `str(x)` | `x.cast(pl.String)` | Exact for integers and Decimal (C17, K16). Differs for floats below 1e-4 and NaN (C14, C15), booleans (C16), None (N17), datetimes with zero microseconds (DT12). |
| `int(x)` | Float: `x.cast(pl.Int64)`; String: `x.str.strip_chars().cast(pl.Int64)`; Decimal: `x.truncate(0).cast(pl.Int64)`; Boolean: `x.cast(pl.Int64)` | Float truncation agrees (C1). Strings: surrounding whitespace needs the strip (C4, C5); underscores (`'4_2'`) and values beyond Int64 are not covered (C4, C8). Decimal: the plain cast rounds half to even (C10, C11). Failures: C2, C3, C6. |
| `int(s, base)` | `s.str.to_integer(base=base)` | A `0x` prefix is not accepted (C7). |
| `float(x)` | `x.cast(pl.Float64)` | Strings with surrounding whitespace or underscores are not accepted (C12); `nan` / `inf` spellings agree (C13). |
| `round(x)` | `x.round().cast(pl.Int64)` | Exact on halves (R2). NaN and inf: R8. |
| `round(x, n)`, n >= 1 | `x.round(n)` | Not exact for Float64 (R4, R5). Decimal: values exact, scale kept (R9). n < 0: not supported (R7). |
| `min(a, b)`, `max(a, b)` | `pl.min_horizontal(a, b)`, `pl.max_horizontal(a, b)` | Exact without None or NaN. None is skipped, not raised (N26). NaN is skipped in 1.44.x (Q7, Q8); before 1.44.0 results with NaN were inconsistent (https://github.com/pola-rs/polars/issues/28682). `x.min()` is the column minimum (as-found finding 12). |
| `sum((a, b))`, `any((a, b))`, `all((a, b))` | `pl.sum_horizontal(a, b)`, `pl.any_horizontal(truthy(a), truthy(b))`, `pl.all_horizontal(truthy(a), truthy(b))` | None is skipped by `sum_horizontal` (N27). W6 agrees; W7 shows the null that `all_horizontal` (Kleene logic) returns when a None operand is not passed through truthy() first. |
| `{...}[x]`, `{...}.get(x, d)`, `{...}.get(x, x)` (dict literal) | `x.replace_strict(mapping)`, `x.replace_strict(mapping, default=d)`, `x.replace(mapping)` | W1-W4. A missing key fails the query where Python raises `KeyError` for that row (W2). |

### 2.6 Strings

| Python | Polars expression | Notes |
|---|---|---|
| `s + t` | `s + t` | Exact; None gives null (N12, N13). |
| `s + str(n)` | `s + n.cast(pl.String)` | X3. `s + n` fails on both sides (X1). |
| `f"{a}-{b}"`, `"{}-{}".format(a, b)`, `"%s-%s" % (a, b)` | `pl.format("{}-{}", a, b)` | Exact for strings and integers (U26, U34). Any None makes the result null (N15); `fill_null('None')` reproduces Python (N16). Floats and booleans follow the `str()` differences (U27, U28). Literal `{` `}` must be doubled. |
| f-string format specs | `:05d` -> `x.cast(pl.String).str.zfill(5)` (U31); `:>6` -> `.str.pad_start(6)` (U32) | `:.2f` has no exact form (U29, U30); `:,` has none (U33); `!r` / `!a`: none found. |
| `s.upper()`, `s.lower()` | `s.str.to_uppercase()`, `s.str.to_lowercase()` | Exact including sharp s and final sigma (S1, S2). Per single code point they agree on all but 28 of 1,112,064 (3.13). |
| `s.title()` | `s.str.to_titlecase()` | Exact on the ASCII cases including apostrophes and digits (S3); for 169 non-ASCII code points the first letter differs (3.13). |
| `s.capitalize()` | `s.str.head(1).str.to_uppercase() + s.str.slice(1).str.to_lowercase()` | S4. |
| `s.strip()`, `s.lstrip()`, `s.rstrip()` | `s.str.strip_chars()`, `.strip_chars_start()`, `.strip_chars_end()` | Exact except U+001C to U+001F, which Python strips and Polars keeps (S5, S7; exhaustive over all code points, 3.13). |
| `s.strip(chars)` | `s.str.strip_chars(chars)` | Exact; both treat the argument as a set (S6). |
| `s.removeprefix(p)`, `s.removesuffix(p)` | `s.str.strip_prefix(p)`, `s.str.strip_suffix(p)` | S8. |
| `s.startswith(p)`, `s.endswith(p)` | `s.str.starts_with(p)`, `s.str.ends_with(p)` | Exact (S9, S11). A tuple argument becomes `\|` of calls (S10). |
| `s.replace(old, new)` | `s.str.replace_all(old, new, literal=True)` | Exact (U2, U3). The default treats `old` as a regex (U1). With a count: `s.str.replace(old, new, literal=True, n=count)` (U4). `old` taken from a column: not supported ("dynamic pattern length in 'str.replace' expressions is not supported yet", `pl-src:crates/polars-expr/src/dispatch/strings.rs#L675-L677`; obs). |
| `s.find(sub)`, `s.index(sub)` | `s.str.find(sub, literal=True)` | Not exact: null instead of -1 or `ValueError`, and a byte offset instead of a character index (S15). |
| `s.count(sub)` | `s.str.count_matches(sub, literal=True)` | S16. |
| `s.split(sep)` | `s.str.split(sep)` | Exact (U5); List(String). |
| `s.split()` | `s.str.extract_all(r"\S+")` | U7. `split(' ')` is different (U6). |
| `s.split(sep)[i]` | `.list.get(i, null_on_oob=True)`, `.list.first()`, `.list.last()` | Out of range: null instead of `IndexError` (U9, U10); the default `list.get` fails the query (U8). |
| `sep.join([a, b])` | `pl.concat_str([a, b], separator=sep)`; list column: `xs.list.join(sep)` | U11. |
| `s.zfill(n)` | `s.str.zfill(n)` | Exact for ASCII including signs; pads by bytes for non-ASCII (U12). |
| `s.rjust(n, c)`, `s.ljust(n, c)` | `s.str.pad_start(n, c)`, `s.str.pad_end(n, c)` | Exact (U13, U14). |
| `s.isdecimal()` | `s.str.contains(r"^\d+$")` | Exact per code point (3.13). |
| `s.isalpha()`, `s.isalnum()` | `s.str.contains(r"^\p{L}+$")`, `s.str.contains(r"^[\p{L}\p{N}]+$")` | Exact per code point (S19; 3.13). |
| `s.isdigit()`, `s.isnumeric()`, `s.isspace()` | the forms `r"^\d+$"`, `r"^\p{N}+$"`, `r"^\s+$"` | Not exact: 128, 91 and 4 code points differ (S17, S18, S20; 3.13). Below U+0080 `isdigit` and `^\d+$` agree. |
| `s.isupper()`, `s.islower()` | none found | `s == s.str.to_uppercase()` is wrong for strings without letters (S21); `\p{Lu}` / `\p{Ll}` differ for 120 / 311 single characters (3.13). |
| `s[i]` | `s.str.slice(i, 1)` | Out of range: `''` instead of `IndexError` (U17, U18). |
| `s[a:b]`, `s[:n]`, `s[n:]`, `s[-n:]`, `s[:-n]` | `s.str.slice(a, b - a)`, `s.str.head(n)`, `s.str.slice(n)`, `s.str.tail(n)`, `s.str.head(-n)` | Exact for constant bounds with 0 <= a <= b (U19-U23); offsets count characters. Other sign mixes need composition; a negative length fails (obs). |
| `s[::-1]` | `s.str.reverse()` | U24. Other steps: none (U25). |
| `s * n` | `s.repeat_by(n).list.join("")` | X5; `s * n` itself fails (X4). |

### 2.7 `re`

"p2" is the pattern after checking it against the Rust dialect (section 3.15);
"r2" is the replacement with `\1` -> `${1}`, `\g<name>` -> `${name}` and a
literal `$` -> `$$`. That rewrite of `$` applies only when p2 contains ASCII
punctuation; otherwise Polars treats the pattern as a literal and inserts the
replacement unchanged (3.15).

| Python | Polars expression | Notes |
|---|---|---|
| `re.sub(p, r, s)` | `s.str.replace_all(p2, r2)` | P1, P2, P5, P7. Pitfalls: P3, P4, P6, P8, P9, P10. |
| `re.sub(p, r, s, count=n)` | `s.str.replace(p2, r2, n=n)` | P11. With a regex pattern only `n=1` is supported (P32); a pattern without ASCII punctuation allows any `n` (P33). |
| flags `re.I`, `re.M`, `re.S`, `re.X`, `re.A` | inline `(?i)`, `(?m)`, `(?s)`, `(?x)`, `(?-u:...)` | P12; the docstrings point to the regex crate's "grouping and flags". |
| `re.search(p, s)` used as a test | `s.str.contains(p2)` | P13. |
| `re.match(p, s)` used as a test | `s.str.contains("^(?:" + p2 + ")")` | P15; P14 shows why the group is needed. |
| `re.fullmatch(p, s)` used as a test | `s.str.contains("^(?:" + p2 + ")$")` | P16. |
| `re.search(p, s).group(n)` | `s.str.extract(p2, n)` | No match: null instead of `AttributeError` (P27). |
| `re.findall(p, s)` | `s.str.extract_all(p2)` | Exact only when `p` has no capture group (P25, P26). |
| `re.split(p, s)` | `s.str.split(p2, literal=False)` | Exact when `p` has no capture group (P29, P30); the default is a literal split (P28). |
| `re.escape(const)`, `re.compile(const)` | compute once when translating | `Expr.str.escape_regex()` exists for per-row values (obs). |
| a function as replacement, Match objects beyond `.group(n)` | none | P31. |

### 2.8 `math`

| Python | Polars expression | Notes |
|---|---|---|
| `math.floor(x)`, `math.ceil(x)`, `math.trunc(x)` | `x.floor().cast(pl.Int64)`, `x.ceil().cast(pl.Int64)`, `x.cast(pl.Int64)` | H2-H4. Without the cast the result stays Float64 (H1). |
| `math.sqrt`, `exp`, `log(x)`, `log(x, b)`, `log10`, `log1p`, `pow`, `sin`/`cos`/`tan`, `asin`/`acos`/`atan`, hyperbolic forms, `degrees`, `radians`, `cbrt`, `fabs` | `x.sqrt()`, `x.exp()`, `x.log()`, `x.log(b)`, `x.log10()`, `x.log1p()`, `x.pow(y)`, `x.sin()` ..., `x.arcsin()` ..., `x.degrees()`, `x.radians()`, `x.cbrt()`, `x.abs()` | Values agreed on the inputs tested except a last-digit difference in `log10` (H7). Domain and range errors become NaN / inf / -inf instead of `ValueError` / `OverflowError` (H5, H6, H9, H10). |
| `math.atan2(y, x)` | `pl.arctan2(y, x)` | H11. |
| `math.isnan`, `math.isinf`, `math.isfinite` | `x.is_nan()`, `x.is_infinite()`, `x.is_finite()` | H12. |
| `math.pi`, `math.e`, `math.tau`, `math.inf`, `math.nan` | the Python float, as a literal | |
| the rest of `math` | none | Listed in section 4. |

### 2.9 `datetime`

"fmt2" is the format after the directive changes noted.

| Python | Polars expression | Notes |
|---|---|---|
| `d.year`, `.month`, `.day`, `.hour`, `.minute`, `.second`, `.microsecond` | `d.dt.year()`, `.dt.month()`, ... | Exact (DT1); result dtypes are Int32 / Int8. |
| `d.weekday()` | `d.dt.weekday() - 1` | DT3. Without `- 1` the result is one higher (DT2). |
| `d.isoweekday()` | `d.dt.weekday()` | DT4. |
| `d.date()`, `d.time()` | `d.dt.date()`, `d.dt.time()` | DT5. |
| `d.replace(day=1)` | `d.dt.replace(day=1)` | DT6. An impossible date fails the query instead of raising for the row (obs). |
| `d.strftime(fmt)` | `d.dt.strftime(fmt2)` | `.%f` -> `%.6f` (DT8, DT9). Most other directives agreed on the values tested (DT7, DT10). `%Z` / `%z` fail on naive values and `%s` differs (obs). |
| `datetime.datetime.strptime(s, fmt)` | `s.str.to_datetime(fmt2)`; with `.date()`: `s.str.to_date(fmt2)`; with `.time()`: `s.str.to_time(fmt2)` | `.%f` -> `%.f` (DT15, DT16). Two-digit years pivot differently (DT17). Polars accepts leading whitespace and a short year that Python rejects (DT13). Failures: DT14. |
| `d.isoformat()`, `str(d)` | none exact | DT11, DT12. |
| `d2 - d1` | `d2 - d1` | Duration (DT18). |
| `(d2 - d1).days` | `(d2 - d1).dt.total_microseconds() // 86_400_000_000` | DT20. `dt.total_days()` truncates toward zero (DT19). |
| `(d2 - d1).total_seconds()` | `(d2 - d1).dt.total_seconds(fractional=True)` | DT22; the default returns Int64 (DT21). |
| `d + datetime.timedelta(days=n)` | `d + pl.duration(days=n)` | `n` may be a column (DT23, DT24). |
| `datetime.datetime(y, m, d)`, `datetime.date(y, m, d)` from columns | `pl.datetime(y, m, d)`, `pl.date(y, m, d)` | Invalid components fail the query (DT28, DT29). |
| `datetime.datetime.now()`, `datetime.date.today()` | `pl.lit(...)` fixed when translated | Python evaluates it for every row; a translated constant is one instant for the run. |
| `d.timestamp()`, `datetime.datetime.fromtimestamp(n)` | `d.dt.epoch("s")`, `pl.from_epoch(n)` | Not equivalent for naive values: Python uses the machine's local time zone ("Naive datetime instances are assumed to represent local time", `py-lib:datetime#datetime.datetime.timestamp`). obs on this Mac (UTC+05:30): results differ by 19,800 s. |

### 2.10 `Decimal`

| Python | Polars expression | Notes |
|---|---|---|
| `a + b`, `a - b`, `-a`, `abs(a)`, `a * int` | the same | Exact (K1, K5). |
| `a * b` | `a * b` | Not exact: the result keeps the larger input scale and is rounded to it (K2, K3, K13). |
| `a / b` | `a / b` | Not exact: same scale rule (K4, K12). A zero divisor fails the query (Z7). |
| `a // b`, `a % b`, `a ** n`, `a.sqrt()` | none (`sqrt` returns Float64) | K6, K7, K8, K20. |
| `Decimal(s)` | `s.str.strip_chars().cast(pl.Decimal(38, scale))` or `s.str.to_decimal(scale=scale)` | Needs a declared scale; extra digits are rounded away (K14). `str.to_decimal` is marked unstable in its docstring. |
| `round(a, n)`; `a.quantize(Decimal('0.1'), rounding=ROUND_HALF_EVEN / ROUND_HALF_UP / ROUND_DOWN)` | `a.round(n)`; `a.round(n, mode='half_away_from_zero')`; `a.truncate(n)` | Values exact, scale kept (R9, R10, R12). `mode='to_zero'` is in the docstring but rejected (R11). |
| `str(a)`, `float(a)`, `int(a)` | `a.cast(pl.String)`, `a.cast(pl.Float64)`, `a.truncate(0).cast(pl.Int64)` | K16, K17, C11. |
| `a + 1.5` (Decimal with float) | Python raises; Polars returns Float64 | K9. |
| `a == b`, `a < b` | the same operators | Exact for Decimal against Decimal or int (K11); Decimal against float differs (K10). |

### 2.11 The old v2 function table as a seed

Read from `src/v2/expressions/compiler.py` L282-L357 on `feature/engine-v2`.

- Carry over as they are: `upper`, `lower`, `trim`/`ltrim`/`rtrim`
  (`strip_chars*`), `length` (`len_chars`), `left`/`right` (`head`/`tail`),
  `lpad`/`rpad` (`pad_start`/`pad_end`), `starts_with`, `ends_with`, `split`,
  `regex_extract` (`str.extract`), `abs`, `floor`, `ceil`, `sqrt`, `pow`,
  `mod`, `log`, `exp`, `isnull`/`isnotnull`, `if` (`when/then/otherwise`),
  the `dt` extractors, `to_date`/`parse_date`/`format_date`, `date_add`.
- Carry over with a change: `replace` (L292) and `contains` (L297) call the
  regex forms without `literal=True` (U1, S13 show the effect); `min`/`max`
  (L353-L354) are column aggregates; `round` (L401-L406) is the float rounding
  of R4/R5; `date_diff` (L444-L448) uses `total_days()` (DT19); `substring`
  (L369-L376) is offset and length, not Python's start and stop.
- Not Python semantics: `to_string` (L329) and `concat` (L359-L367) turn null
  into `''`; `to_decimal` (L333) casts to Float64; `now` (L347) is fixed when
  compiled.

---

## 3. Where Polars differs from row-by-row Python (observed)

Method. Each row was run twice over the same input values: the Python text
was `eval`'d once per row with `row1` bound to a dict that also allows
attribute access (the shape of v1's `_Row`), with `re`, `math`, `datetime`,
`Decimal`, `json`, `pd` in scope and plain Python values as inputs; the Polars text
was `eval`'d once to a `pl.Expr` and run as
`pl.DataFrame(rows, schema).lazy().select(expr).collect()`. A Python exception
is shown by class name for its row only; a Polars failure aborts the whole
column and is shown as "query fails" (or "at build" when constructing the
expression raised). Both Polars engines were run (`engine="in-memory"` and
`engine="streaming"`): all 328 rows gave identical results. Last column:
`same` = identical per row (None and null count as the same); `type` = equal
values of a different type or scale; `DIFF` = a value or an outcome differs;
`both fail` = every Python row raises and the Polars query fails; `n/a` = no
Polars form found. Totals: 146 same, 8 type, 165 DIFF, 4 both fail, 5 n/a.
Label for every table in this section: observed on polars 1.44.2,
Python 3.14.

### 3.0 Row access

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| V1 | `row1.a + 1` | `pl.col('a') + 1` | a: 1; 2 | 2; 3 | 2; 3 [Int64] | same |
| V2 | `row1['a'] + 1` | `pl.col('a') + 1` | a: 1; 2 | 2; 3 | 2; 3 [Int64] | same |
| V3 | `row1.a + 1` | `pl.col.a + 1` | a: 1; 2 | 2; 3 | 2; 3 [Int64] | same |
| V4 | `row1['a'] + 1` | `pl.col['a'] + 1` | a: 1; 2 | 2; 3 | at build: TypeError | DIFF |

### 3.1 None versus null

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| N1 | `row1.a + 1` | `c.a + 1` | a: 1; None | 2; TypeError | 2; null [Int64] | DIFF |
| N2 | `row1.a * row1.b` | `c.a * c.b` | (a, b): (2, 3); (2, None); (None, None) | 6; TypeError; TypeError | 6; null; null [Int64] | DIFF |
| N3 | `-row1.a` | `-c.a` | a: 1; None | -1; TypeError | -1; null [Int64] | DIFF |
| N4 | `abs(row1.a)` | `c.a.abs()` | a: -1; None | 1; TypeError | 1; null [Int64] | DIFF |
| N5 | `row1.a < 5` | `c.a < 5` | a: 1; None | True; TypeError | True; null [Boolean] | DIFF |
| N6 | `row1.a == 5` | `c.a == 5` | a: 5; 1; None | True; False; False | True; False; null [Boolean] | DIFF |
| N7 | `row1.a == 5` | `c.a.eq_missing(5)` | a: 5; 1; None | True; False; False | True; False; False [Boolean] | same |
| N8 | `row1.a != 5` | `c.a != 5` | a: 5; 1; None | False; True; True | False; True; null [Boolean] | DIFF |
| N9 | `row1.a != 5` | `c.a.ne_missing(5)` | a: 5; 1; None | False; True; True | False; True; True [Boolean] | same |
| N10 | `row1.a == row1.b` | `c.a == c.b` | (a, b): (1, 1); (1, None); (None, None) | True; False; True | True; null; null [Boolean] | DIFF |
| N11 | `row1.a == row1.b` | `c.a.eq_missing(c.b)` | (a, b): (1, 1); (1, None); (None, None) | True; False; True | True; False; True [Boolean] | same |
| N12 | `row1.s + '-x'` | `c.s + '-x'` | s: 'ab'; None | 'ab-x'; TypeError | 'ab-x'; null [String] | DIFF |
| N13 | `row1.s + row1.t` | `c.s + c.t` | (s, t): ('ab', 'cd'); (None, 'cd') | 'abcd'; TypeError | 'abcd'; null [String] | DIFF |
| N14 | `row1.s + row1.t` | `pl.concat_str([c.s, c.t], ignore_nulls=True)` | (s, t): ('ab', 'cd'); (None, 'cd') | 'abcd'; TypeError | 'abcd'; 'cd' [String] | DIFF |
| N15 | `f'{row1.s}-{row1.t}'` | `pl.format('{}-{}', c.s, c.t)` | (s, t): ('ab', 'cd'); (None, 'cd') | 'ab-cd'; 'None-cd' | 'ab-cd'; null [String] | DIFF |
| N16 | `f'{row1.s}-{row1.t}'` | `pl.format('{}-{}', c.s.fill_null('None'), c.t.fill_null('None'))` | (s, t): ('ab', 'cd'); (None, 'cd') | 'ab-cd'; 'None-cd' | 'ab-cd'; 'None-cd' [String] | same |
| N17 | `str(row1.a)` | `c.a.cast(pl.String)` | a: 1; None | '1'; 'None' | '1'; null [String] | DIFF |
| N18 | `row1.s.upper()` | `c.s.str.to_uppercase()` | s: 'ab'; None | 'AB'; AttributeError | 'AB'; null [String] | DIFF |
| N19 | `len(row1.s)` | `c.s.str.len_chars()` | s: 'ab'; ''; None | 2; 0; TypeError | 2; 0; null [UInt32] | DIFF |
| N20 | `row1.a in (1, 2)` | `c.a.is_in([1, 2])` | a: 1; 3; None | True; False; False | True; False; null [Boolean] | DIFF |
| N21 | `row1.a in (1, 2)` | `c.a.is_in([1, 2], nulls_equal=True)` | a: 1; 3; None | True; False; False | True; False; False [Boolean] | same |
| N22 | `row1.a in (1, None)` | `c.a.is_in([1, None])` | a: 1; 3; None | True; False; True | True; False; null [Boolean] | DIFF |
| N23 | `row1.a in (1, None)` | `c.a.is_in([1, None], nulls_equal=True)` | a: 1; 3; None | True; False; True | True; False; True [Boolean] | same |
| N24 | `row1.a not in (1, 2)` | `~c.a.is_in([1, 2])` | a: 1; 3; None | False; True; True | False; True; null [Boolean] | DIFF |
| N25 | `row1.a not in (1, 2)` | `~c.a.is_in([1, 2], nulls_equal=True)` | a: 1; 3; None | False; True; True | False; True; True [Boolean] | same |
| N26 | `min(row1.a, row1.b)` | `pl.min_horizontal(c.a, c.b)` | (a, b): (1, 2); (None, 2) | 1; TypeError | 1; 2 [Int64] | DIFF |
| N27 | `sum((row1.a, row1.b))` | `pl.sum_horizontal(c.a, c.b)` | (a, b): (1, 2); (None, 2) | 3; TypeError | 3; 2 [Int64] | DIFF |

Reading. Python: "A default order comparison (<, >, <=, and >=) is not
provided; an attempt raises TypeError" (`py-ref:value-comparisons`), and the
same holds for arithmetic and method calls on None. Polars propagates null
through every operator and function shown and never raises for it. The exact
forms are documented: `eq_missing` is the "equality operator ... where
`None == None`. This differs from default `eq` where null values are
propagated" (`pl-api:Expr.eq_missing`); `is_in(..., nulls_equal=True)`: "treat
null as a distinct value. Null values will not propagate" (`pl-api:Expr.is_in`);
`pl.format`: "If any input expression evaluates to null for a row, the output
... is null for that row" (`pl-api:format`); `concat_str(ignore_nulls=...)`
(`pl-api:concat_str`). The horizontal functions skip nulls instead (N26, N27).
So Python-raises-per-row has no native counterpart: the choices observed are
"null" or "an exact value form".

### 3.2 `== None` versus `is None`

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| E1 | `row1.a == None` | `c.a == None` | a: 1; None | False; True | null; null [Boolean] | DIFF |
| E2 | `row1.a == None` | `c.a.eq_missing(None)` | a: 1; None | False; True | False; True [Boolean] | same |
| E3 | `row1.a != None` | `c.a != None` | a: 1; None | True; False | null; null [Boolean] | DIFF |
| E4 | `row1.a != None` | `c.a.ne_missing(None)` | a: 1; None | True; False | True; False [Boolean] | same |
| E5 | `row1.a is None` | `c.a.is_null()` | a: 1; None | False; True | False; True [Boolean] | same |
| E6 | `row1.a is not None` | `c.a.is_not_null()` | a: 1; None | True; False | True; False [Boolean] | same |
| E7 | `row1.p == True` | `c.p == True` | p: True; False; None | True; False; False | True; False; null [Boolean] | DIFF |
| E8 | `row1.p is True` | `c.p.eq_missing(True)` | p: True; False; None | True; False; False | True; False; False [Boolean] | same |

Reading. Polars warns at build time for `== None` ("Comparisons with None
always result in null. Consider using `.is_null()` or `.is_not_null()`", obs).
The old v2 language had the same defect (as-found finding 11).

### 3.3 Division and modulo with negative operands

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| M1 | `row1.a // row1.b` | `c.a // c.b` | (a, b): (7, 2); (-7, 2); (7, -2); (-7, -2) | 3; -4; -4; 3 | 3; -4; -4; 3 [Int64] | same |
| M2 | `row1.a % row1.b` | `c.a % c.b` | (a, b): (7, 2); (-7, 2); (7, -2); (-7, -2) | 1; 1; -1; -1 | 1; 1; -1; -1 [Int64] | same |
| M3 | `row1.a / row1.b` | `c.a / c.b` | (a, b): (7, 2); (-7, 2); (7, -2); (-7, -2) | 3.5; -3.5; -3.5; 3.5 | 3.5; -3.5; -3.5; 3.5 [Float64] | same |
| M4 | `row1.a // row1.b` | `c.a // c.b` | (a, b): (7.5, 2.0); (-7.5, 2.0); (7.5, -2.0); (-7.5, -2.0) | 3.0; -4.0; -4.0; 3.0 | 3.0; -4.0; -4.0; 3.0 [Float64] | same |
| M5 | `row1.a % row1.b` | `c.a % c.b` | (a, b): (7.5, 2.0); (-7.5, 2.0); (7.5, -2.0); (-7.5, -2.0) | 1.5; 0.5; -0.5; -1.5 | 1.5; 0.5; -0.5; -1.5 [Float64] | same |
| M6 | `row1.a // row1.b` | `c.a // c.b` | (a, b): (7, 2.0); (-7, 2.0) | 3.0; -4.0 | 3.0; -4.0 [Float64] | same |
| M7 | `int(row1.a / row1.b)` | `(c.a / c.b).cast(pl.Int64)` | (a, b): (7, 2); (-7, 2); (7, -2); (-7, -2) | 3; -3; -3; 3 | 3; -3; -3; 3 [Int64] | same |

Reading. No difference in sign for any combination. Python: "The modulo
operator always yields a result with the same sign as its second operand (or
zero)" and floor division is "mathematical division with the 'floor' function
applied to the result" (`py-ref:binary-arithmetic-operations`). The 1.44.2
docstrings of `Expr.floordiv` and `Expr.mod` do not state a sign rule, so the
Polars side is an observation.

### 3.4 Division by zero

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| Z1 | `row1.a / row1.b` | `c.a / c.b` | (a, b): (1, 0); (0, 0); (-1, 0) | ZeroDivisionError; ZeroDivisionError; ZeroDivisionError | inf; nan; -inf [Float64] | DIFF |
| Z2 | `row1.a // row1.b` | `c.a // c.b` | (a, b): (1, 0); (0, 0); (-1, 0) | ZeroDivisionError; ZeroDivisionError; ZeroDivisionError | null; null; null [Int64] | DIFF |
| Z3 | `row1.a % row1.b` | `c.a % c.b` | (a, b): (1, 0); (0, 0); (-1, 0) | ZeroDivisionError; ZeroDivisionError; ZeroDivisionError | null; null; null [Int64] | DIFF |
| Z4 | `row1.a / row1.b` | `c.a / c.b` | (a, b): (1.0, 0.0); (0.0, 0.0); (-1.0, 0.0) | ZeroDivisionError; ZeroDivisionError; ZeroDivisionError | inf; nan; -inf [Float64] | DIFF |
| Z5 | `row1.a // row1.b` | `c.a // c.b` | (a, b): (1.0, 0.0); (0.0, 0.0); (-1.0, 0.0) | ZeroDivisionError; ZeroDivisionError; ZeroDivisionError | inf; nan; -inf [Float64] | DIFF |
| Z6 | `row1.a % row1.b` | `c.a % c.b` | (a, b): (1.0, 0.0); (0.0, 0.0); (-1.0, 0.0) | ZeroDivisionError; ZeroDivisionError; ZeroDivisionError | nan; nan; nan [Float64] | DIFF |
| Z7 | `row1.a / row1.b` | `c.a / c.b` | (a, b): (D(1.00), D(0.00)) | DivisionByZero | query fails: ComputeError | both fail |
| Z8 | `row1.a / row1.b if row1.b != 0 else None` | `pl.when(c.b != 0).then(c.a / c.b)` | (a, b): (1, 0); (0, 0); (6, 3) | None; None; 2.0 | null; null; 2.0 [Float64] | same |

Reading. Python: "Division by zero raises the ZeroDivisionError exception"
(`py-ref:binary-arithmetic-operations`). Polars `/`: "Zero-division behaviour
follows IEEE-754: 0/0: Invalid operation - mathematically undefined, returns
NaN. n/0: On finite operands gives an exact infinite result, eg: +/-infinity"
(`pl-api:Expr.truediv`). Null for integer `//` and `%` is observed, not
documented in those docstrings. Decimal is the one case where Polars fails
(Z7: "division by zero Decimal"). A guard written as a conditional expression
works on both sides (Z8) because the unguarded value is inf, not an error.

### 3.5 String plus number and other mixed types

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| X1 | `row1.s + row1.i` | `c.s + c.i` | (s, i): ('n=', 7) | TypeError | query fails: InvalidOperationError | both fail |
| X2 | `'n=' + row1.i` | `pl.lit('n=') + c.i` | (s, i): ('n=', 7) | TypeError | query fails: InvalidOperationError | both fail |
| X3 | `row1.s + str(row1.i)` | `c.s + c.i.cast(pl.String)` | (s, i): ('n=', 7) | 'n=7' | 'n=7' [String] | same |
| X4 | `row1.s * 2` | `c.s * 2` | (s, i): ('n=', 7) | 'n=n=' | query fails: InvalidOperationError | DIFF |
| X5 | `row1.s * 2` | `c.s.repeat_by(2).list.join('')` | (s, i): ('n=', 7) | 'n=n=' | 'n=n=' [String] | same |
| X6 | `row1.s == row1.i` | `c.s == c.i` | (s, i): ('7', 7) | False | query fails: ComputeError | DIFF |
| X7 | `row1.s < row1.i` | `c.s < c.i` | (s, i): ('7', 7) | TypeError | query fails: ComputeError | both fail |
| X8 | `row1.i + row1.f` | `c.i + c.f` | (i, f): (1, 0.5) | 1.5 | 1.5 [Float64] | same |
| X9 | `row1.i + row1.p` | `c.i + c.p` | (i, p): (1, True) | 2 | 2 [Int64] | same |
| X10 | `row1.i == row1.f` | `c.i == c.f` | (i, f): (1, 1.0) | True | True [Boolean] | same |
| X11 | `row1.i if row1.i > 0 else 'N/A'` | `pl.when(c.i > 0).then(c.i).otherwise(pl.lit('N/A'))` | i: 5; -5 | 5; 'N/A' | '5'; 'N/A' [String] | DIFF |
| X12 | `row1.i if row1.i > 0 else 0.5` | `pl.when(c.i > 0).then(c.i).otherwise(0.5)` | i: 5; -5 | 5; 0.5 | 5.0; 0.5 [Float64] | type |
| X13 | `'a' if row1.i > 0 else 'b'` | `pl.when(c.i > 0).then('a').otherwise('b')` | i: 5; -5 | 'a'; 'b' | query fails: ColumnNotFoundError | DIFF |
| X14 | `'a' if row1.i > 0 else 'b'` | `pl.when(c.i > 0).then(pl.lit('a')).otherwise(pl.lit('b'))` | i: 5; -5 | 'a'; 'b' | 'a'; 'b' [String] | same |

Reading. `str + int` fails on both sides, but differently: Python per row,
Polars for the whole query when it is planned ("arithmetic on dtypes str and
i64 is not allowed ...; try an explicit cast first", obs). `str == int` is
False in Python and fails in Polars ("cannot compare string with numeric type",
obs). Conditional branches of different types do not fail: Polars casts both to
a common type, String for int and str (X11), Float64 for int and float (X12).
A bare `'a'` in `then` is a column name (X13); `pl.lit('a')` is the constant
(X14).

### 3.6 `round`

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| R1 | `round(row1.f)` | `c.f.round()` | f: 0.5; 1.5; 2.5; -0.5; -1.5; -2.5 | 0; 2; 2; 0; -2; -2 | 0.0; 2.0; 2.0; -0.0; -2.0; -2.0 [Float64] | type |
| R2 | `round(row1.f)` | `c.f.round().cast(pl.Int64)` | f: 0.5; 1.5; 2.5; -0.5; -1.5; -2.5 | 0; 2; 2; 0; -2; -2 | 0; 2; 2; 0; -2; -2 [Int64] | same |
| R3 | `round(row1.f)` | `c.f.round(0, mode='half_away_from_zero').cast(pl.Int64)` | f: 0.5; 1.5; 2.5; -0.5; -1.5; -2.5 | 0; 2; 2; 0; -2; -2 | 1; 2; 3; -1; -2; -3 [Int64] | DIFF |
| R4 | `round(row1.f, 2)` | `c.f.round(2)` | f: 0.125; 0.375; 2.675; 1.005; 1.115; 0.005 | 0.12; 0.38; 2.67; 1.0; 1.11; 0.01 | 0.12; 0.38; 2.68; 1.0; 1.12; 0.0 [Float64] | DIFF |
| R5 | `round(row1.f, 1)` | `c.f.round(1)` | f: 0.25; 0.35; 0.45; 0.05; 0.15 | 0.2; 0.3; 0.5; 0.1; 0.1 | 0.2; 0.4; 0.4; 0.0; 0.2 [Float64] | DIFF |
| R6 | `round(row1.f, 1)` | `c.f.round(1, mode='half_away_from_zero')` | f: 0.25; 0.35; 0.45; 0.05; 0.15 | 0.2; 0.3; 0.5; 0.1; 0.1 | 0.3; 0.4; 0.5; 0.1; 0.2 [Float64] | DIFF |
| R7 | `round(row1.i, -1)` | `c.i.round(-1)` | i: 15; 25; 35 | 20; 20; 40 | at build: OverflowError | DIFF |
| R8 | `round(row1.f)` | `c.f.round().cast(pl.Int64, strict=False)` | f: nan; inf; None | ValueError; OverflowError; TypeError | null; null; null [Int64] | DIFF |
| R9 | `round(row1.d, 1)` | `c.d.round(1)` | d: D(0.25); D(0.35); D(0.45); D(-0.25) | D(0.2); D(0.4); D(0.4); D(-0.2) | D(0.20); D(0.40); D(0.40); D(-0.20) [Decimal(38,2)] | type |
| R10 | `row1.d.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)` | `c.d.round(1, mode='half_away_from_zero')` | d: D(0.25); D(0.35); D(-0.25) | D(0.3); D(0.4); D(-0.3) | D(0.30); D(0.40); D(-0.30) [Decimal(38,2)] | type |
| R11 | `row1.d.quantize(Decimal('0.1'), rounding=ROUND_DOWN)` | `c.d.round(1, mode='to_zero')` | d: D(0.29); D(-0.29) | D(0.2); D(-0.2) | at build: ValueError | DIFF |
| R12 | `row1.d.quantize(Decimal('0.1'), rounding=ROUND_DOWN)` | `c.d.truncate(1)` | d: D(0.29); D(-0.29) | D(0.2); D(-0.2) | D(0.20); D(-0.20) [Decimal(38,2)] | type |

Reading. Python: "values are rounded to the closest multiple of 10 to the
power minus ndigits; if two multiples are equally close, rounding is done
toward the even choice ... The return value is an integer if ndigits is
omitted or None", with the note that "round(2.675, 2) gives 2.67 instead of
the expected 2.68. This is not a bug: it's a result of the fact that most
decimal fractions can't be represented exactly as a float"
(`py-lib:functions#round`). Polars: `round(decimals=0, mode='half_to_even')`
(`pl-api:Expr.round`; same default in the 1.38.0 source), implemented for
Float64 as `f64_op(val * multiplier) / multiplier` with
`multiplier = 10.0_f64.powi(decimals)`
(`pl-src:crates/polars-ops/src/series/ops/round.rs#L107-L115`). Multiplying
first turns values such as 2.675 and 0.35 into exact ties that Python never
sees, and the reverse for 0.45 and 0.005; hence R4 and R5 differ in both
directions. With no digits both sides agree (R1, R2). Decimal rounding is
integer arithmetic in Polars and agrees in value (R9, R10, R12). Two more
points: `decimals` is unsigned, so negative digits fail (R7), and the mode
`to_zero` appears in the 1.44.2 docstring but is rejected ("`mode` must be one
of {'half_to_even', 'half_away_from_zero'}, got to_zero", R11); `truncate`
does that job (R12; `Expr.truncate` is not in the 1.38.0 source).

### 3.7 Truthiness

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| T1 | `bool(row1.s)` | `c.s.cast(pl.Boolean)` | s: ''; 'a'; ' '; '0'; None | False; True; True; True; False | query fails: InvalidOperationError | DIFF |
| T2 | `bool(row1.s)` | `(c.s != '').fill_null(False)` | s: ''; 'a'; ' '; '0'; None | False; True; True; True; False | False; True; True; True; False [Boolean] | same |
| T3 | `bool(row1.i)` | `c.i.cast(pl.Boolean)` | i: 0; 1; -1; None | False; True; True; False | False; True; True; null [Boolean] | DIFF |
| T4 | `bool(row1.i)` | `(c.i != 0).fill_null(False)` | i: 0; 1; -1; None | False; True; True; False | False; True; True; False [Boolean] | same |
| T5 | `bool(row1.f)` | `(c.f != 0).fill_null(False)` | f: 0.0; 0.1; nan; None | False; True; True; False | False; True; True; False [Boolean] | same |
| T6 | `bool(row1.p)` | `c.p.fill_null(False)` | p: True; False; None | True; False; False | True; False; False [Boolean] | same |
| T7 | `not row1.p` | `~c.p` | p: True; False; None | False; True; True | False; True; null [Boolean] | DIFF |
| T8 | `not row1.p` | `~c.p.fill_null(False)` | p: True; False; None | False; True; True | False; True; True [Boolean] | same |
| T9 | `not row1.i` | `~c.i` | i: 0; 1; -1; None | True; False; False; True | -1; -2; 0; null [Int64] | DIFF |
| T10 | `not row1.i` | `(c.i == 0).fill_null(True)` | i: 0; 1; -1; None | True; False; False; True | True; False; False; True [Boolean] | same |
| T11 | `not row1.s` | `~c.s` | s: ''; 'a'; ' '; '0'; None | True; False; False; False; True | query fails: InvalidOperationError | DIFF |
| T12 | `not row1.s` | `(c.s == '').fill_null(True)` | s: ''; 'a'; ' '; '0'; None | True; False; False; False; True | True; False; False; False; True [Boolean] | same |
| T13 | `'y' if row1.p else 'n'` | `pl.when(c.p).then(pl.lit('y')).otherwise(pl.lit('n'))` | p: True; False; None | 'y'; 'n'; 'n' | 'y'; 'n'; 'n' [String] | same |
| T14 | `'y' if not row1.p else 'n'` | `pl.when(~c.p).then(pl.lit('y')).otherwise(pl.lit('n'))` | p: True; False; None | 'n'; 'y'; 'y' | 'n'; 'y'; 'n' [String] | DIFF |
| T15 | `'y' if not row1.p else 'n'` | `pl.when(~c.p.fill_null(False)).then(pl.lit('y')).otherwise(pl.lit('n'))` | p: True; False; None | 'n'; 'y'; 'y' | 'n'; 'y'; 'y' [String] | same |
| T16 | `'y' if row1.i else 'n'` | `pl.when(c.i).then(pl.lit('y')).otherwise(pl.lit('n'))` | i: 0; 1; -1; None | 'n'; 'y'; 'y'; 'n' | query fails: SchemaError | DIFF |
| T17 | `'y' if row1.i else 'n'` | `pl.when((c.i != 0).fill_null(False)).then(pl.lit('y')).otherwise(pl.lit('n'))` | i: 0; 1; -1; None | 'n'; 'y'; 'y'; 'n' | 'n'; 'y'; 'y'; 'n' [String] | same |
| T18 | `'y' if row1.s else 'n'` | `pl.when((c.s != '').fill_null(False)).then(pl.lit('y')).otherwise(pl.lit('n'))` | s: ''; 'a'; ' '; '0'; None | 'n'; 'y'; 'y'; 'y'; 'n' | 'n'; 'y'; 'y'; 'y'; 'n' [String] | same |
| T19 | `'y' if row1.i > 0 else 'n'` | `pl.when(c.i > 0).then(pl.lit('y')).otherwise(pl.lit('n'))` | i: 0; 1; -1; None | 'n'; 'y'; 'n'; TypeError | 'n'; 'y'; 'n'; 'n' [String] | DIFF |

Reading. `~` is documented as bitwise: `Expr.not_` is the "Method equivalent
of bitwise "not" operator `~expr`. This has the effect of negating logical
boolean expressions, but operates bitwise on integers" (docstring, 1.44.2), so
`not 0` becomes -1 (T9). A null condition counts as false in `when` (T13;
source comment "Nulls count as false",
`pl-src:crates/polars-expr/src/expressions/ternary.rs#L116`) and in `filter`
("Rows where the filter predicate does not evaluate to True are discarded
(this includes rows where the predicate evaluates as `null`)", `LazyFrame.filter`
docstring), which matches Python for a bare nullable boolean but not once
`not` is applied first (T7, T14): obs, `filter(~p)` on [True, False, None]
keeps one row where Python's `not p` keeps two.

### 3.8 `and` / `or`

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| B1 | `row1.p and row1.q` | `c.p & c.q` | (p, q): (True, True); (True, False); (True, None); (False, True); (False, False); (False, None); (None, True); (None, False); (None, None) | True; False; None; False; False; False; None; None; None | True; False; null; False; False; False; null; False; null [Boolean] | DIFF |
| B2 | `row1.p and row1.q` | `pl.when(c.p.fill_null(False)).then(c.q).otherwise(c.p)` | (p, q): (True, True); (True, False); (True, None); (False, True); (False, False); (False, None); (None, True); (None, False); (None, None) | True; False; None; False; False; False; None; None; None | True; False; null; False; False; False; null; null; null [Boolean] | same |
| B3 | `row1.p or row1.q` | `c.p \| c.q` | (p, q): (True, True); (True, False); (True, None); (False, True); (False, False); (False, None); (None, True); (None, False); (None, None) | True; True; True; True; False; None; True; False; None | True; True; True; True; False; null; True; null; null [Boolean] | DIFF |
| B4 | `row1.p or row1.q` | `pl.when(c.p.fill_null(False)).then(c.p).otherwise(c.q)` | (p, q): (True, True); (True, False); (True, None); (False, True); (False, False); (False, None); (None, True); (None, False); (None, None) | True; True; True; True; False; None; True; False; None | True; True; True; True; False; null; True; False; null [Boolean] | same |
| B5 | `not (row1.p or row1.q)` | `~(c.p \| c.q)` | (p, q): (True, True); (True, False); (True, None); (False, True); (False, False); (False, None); (None, True); (None, False); (None, None) | False; False; False; False; True; True; False; True; True | False; False; False; False; True; null; False; null; null [Boolean] | DIFF |
| B6 | `not (row1.p or row1.q)` | `~(c.p.fill_null(False) \| c.q.fill_null(False))` | (p, q): (True, True); (True, False); (True, None); (False, True); (False, False); (False, None); (None, True); (None, False); (None, None) | False; False; False; False; True; True; False; True; True | False; False; False; False; True; True; False; True; True [Boolean] | same |
| B7 | `row1.i and row1.j` | `c.i & c.j` | (i, j): (1, 2); (0, 2); (1, 0); (None, 2); (4, 3) | 2; 0; 0; None; 3 | 0; 0; 0; null; 0 [Int64] | DIFF |
| B8 | `row1.i and row1.j` | `pl.when((c.i != 0).fill_null(False)).then(c.j).otherwise(c.i)` | (i, j): (1, 2); (0, 2); (1, 0); (None, 2); (4, 3) | 2; 0; 0; None; 3 | 2; 0; 0; null; 3 [Int64] | same |
| B9 | `row1.i or row1.j` | `c.i \| c.j` | (i, j): (1, 2); (0, 2); (1, 0); (None, 2); (4, 3) | 1; 2; 1; 2; 4 | 3; 2; 1; null; 7 [Int64] | DIFF |
| B10 | `row1.i or row1.j` | `pl.when((c.i != 0).fill_null(False)).then(c.i).otherwise(c.j)` | (i, j): (1, 2); (0, 2); (1, 0); (None, 2); (4, 3) | 1; 2; 1; 2; 4 | 1; 2; 1; 2; 4 [Int64] | same |
| B11 | `row1.s or 'N/A'` | `c.s \| pl.lit('N/A')` | s: 'a'; ''; None | 'a'; 'N/A'; 'N/A' | query fails: InvalidOperationError | DIFF |
| B12 | `row1.s or 'N/A'` | `c.s.fill_null('N/A')` | s: 'a'; ''; None | 'a'; 'N/A'; 'N/A' | 'a'; ''; 'N/A' [String] | DIFF |
| B13 | `row1.s or 'N/A'` | `pl.when((c.s != '').fill_null(False)).then(c.s).otherwise(pl.lit('N/A'))` | s: 'a'; ''; None | 'a'; 'N/A'; 'N/A' | 'a'; 'N/A'; 'N/A' [String] | same |
| B14 | `row1.i > 0 and row1.j > 0` | `(c.i > 0) & (c.j > 0)` | (i, j): (1, 2); (0, 2); (1, 0); (None, 2); (4, 3) | True; False; False; TypeError; True | True; False; False; null; True [Boolean] | DIFF |
| B15 | `row1.i > 0 or row1.j > 0` | `(c.i > 0) \| (c.j > 0)` | (i, j): (1, 2); (0, 2); (1, 0); (None, 2); (4, 3) | True; True; True; TypeError; True | True; True; True; True; True [Boolean] | DIFF |
| B16 | `0 < row1.i < 10` | `(c.i > 0) & (c.i < 10)` | i: 5; 0; 10; None | True; False; False; TypeError | True; False; False; null [Boolean] | DIFF |
| B17 | `0 <= row1.i <= 10` | `c.i.is_between(0, 10)` | i: 5; 0; 10; 11 | True; True; True; False | True; True; True; False [Boolean] | same |

Reading. Python: "neither and nor or restrict the value and type they return
to False and True, but rather return the last evaluated argument"
(`py-ref:boolean-operations`). `&` and `|` are "bitwise ... operates bitwise on
integers" (`Expr.and_`, `Expr.or_` docstrings), so integers give wrong values
without an error (B7, B9) and strings fail (B11). On booleans `&` and `|`
follow Kleene logic and differ from Python only where a None meets the value
that decides the result (B1: (None, False); B3: (None, False)). The `when`
forms reproduce Python on every pair tested (B2, B4, B8, B10, B13).

### 3.9 Short-circuiting and guarded sub-expressions

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| G1 | `row1.i != 0 and 10 / row1.i > 1` | `(c.i != 0) & (10 / c.i > 1)` | i: 5; 0; 20 | True; False; False | True; False; False [Boolean] | same |
| G2 | `row1.i != 0 and 10 // row1.i > 1` | `(c.i != 0) & (10 // c.i > 1)` | i: 5; 0; 20 | True; False; False | True; False; False [Boolean] | same |
| G3 | `row1.s is not None and len(row1.s) > 1` | `c.s.is_not_null() & (c.s.str.len_chars() > 1)` | s: 'ab'; 'a'; None | True; False; False | True; False; False [Boolean] | same |
| G4 | `row1.s is None or row1.s.strip() == ''` | `c.s.is_null() \| (c.s.str.strip_chars() == '')` | s: 'ab'; ' '; None | False; True; True | False; True; True [Boolean] | same |
| G5 | `row1.s.isdigit() and int(row1.s) > 5` | `c.s.str.contains(r'^[0-9]+$') & (c.s.cast(pl.Int64) > 5)` | s: '12'; 'abc' | True; False | query fails: InvalidOperationError | DIFF |
| G6 | `row1.s.isdigit() and int(row1.s) > 5` | `c.s.str.contains(r'^[0-9]+$') & (c.s.cast(pl.Int64, strict=False) > 5)` | s: '12'; 'abc' | True; False | True; False [Boolean] | same |
| G7 | `row1.s.isdigit() and int(row1.s) > 5` | `pl.when(c.s.str.contains(r'^[0-9]+$')).then(c.s.cast(pl.Int64) > 5).otherwise(False)` | s: '12'; 'abc' | True; False | True; False [Boolean] | same |
| G8 | `int(row1.s) if row1.s.isdigit() else 0` | `pl.when(c.s.str.contains(r'^[0-9]+$')).then(c.s.cast(pl.Int64)).otherwise(0)` | s: '12'; 'abc' | 12; 0 | 12; 0 [Int64] | same |
| G9 | `row1.xs[2] if len(row1.xs) > 2 else None` | `pl.when(c.xs.list.len() > 2).then(c.xs.list.get(2))` | xs: [1, 2, 3]; [1] | 3; None | 3; null [Int64] | same |
| G10 | `row1.xs[2]` | `c.xs.list.get(2)` | xs: [1, 2, 3]; [1] | 3; IndexError | query fails: ComputeError | DIFF |
| G11 | `row1.xs[2]` | `c.xs.list.get(2, null_on_oob=True)` | xs: [1, 2, 3]; [1] | 3; IndexError | 3; null [Int64] | DIFF |

The same question across both engines, with a strict cast as the operation
that can fail (obs):

| # | Query shape (s = ['12', 'abc', '7'], k = [1, 0, 1]; digits = `str.contains('^[0-9]+$')`) | in-memory engine | streaming engine |
|---|---|---|---|
| SC1 | when(digits).then(s.cast(Int64)).otherwise(0) | ok {'o': [12, 0, 7]} | ok {'o': [12, 0, 7]} |
| SC2 | when(~digits).then(0).otherwise(s.cast(Int64)) | ok {'o': [12, 0, 7]} | ok {'o': [12, 0, 7]} |
| SC3 | digits & (s.cast(Int64) > 5)   [and-guard] | fails: InvalidOperationError | fails: InvalidOperationError |
| SC4 | ~digits \| (s.cast(Int64) > 5)  [or-guard] | fails: InvalidOperationError | fails: InvalidOperationError |
| SC5 | and-guard rewritten: when(digits).then(s.cast(Int64) > 5).otherwise(False) | ok {'o': [True, False, True]} | ok {'o': [True, False, True]} |
| SC6 | nested: when(k==1).then(when(digits).then(s.cast(Int64)).otherwise(-1)).otherwise(-2) | ok {'o': [12, -2, 7]} | ok {'o': [12, -2, 7]} |
| SC7 | literal-only fallible branch: when(k==1).then(lit('x').cast(Int64)).otherwise(0) | fails: InvalidOperationError | fails: InvalidOperationError |
| SC8 | literal-only fallible branch, predicate never true: when(k==9).then(lit('x').cast(Int64)).otherwise(0) | fails: InvalidOperationError | fails: InvalidOperationError |
| SC9 | branch reads a second column: when(digits).then(s.cast(Int64) + k).otherwise(0) | ok {'o': [13, 0, 8]} | ok {'o': [13, 0, 8]} |
| SC10 | non-elementwise branch: when(digits).then(s.cast(Int64).cum_sum()).otherwise(0) | fails: InvalidOperationError | fails: InvalidOperationError |
| SC11 | filter first, then cast: filter(digits).select(s.cast(Int64)) | ok {'o': [12, 7]} | ok {'o': [12, 7]} |
| SC12 | cast first, then filter on the same column: with_columns(n=s.cast(Int64)).filter(digits) | ok {'n': [12, 7]} | ok {'n': [12, 7]} |
| SC13 | cast first, then filter on another column: with_columns(n=s.cast(Int64)).filter(k == 1) | ok {'n': [12, 7]} | ok {'n': [12, 7]} |
| SC14 | on s = ['2024-01-02', '', 'junk']: when(s.str.len_chars() == 10).then(s.str.to_date('%Y-%m-%d')) | ok {'o': [2024-01-02, None, None]} | ok {'o': [2024-01-02, None, None]} |
| SC15 | on s = ['2024-01-02', '', 'junk']: s.str.to_date('%Y-%m-%d') unguarded | fails: InvalidOperationError | fails: InvalidOperationError |

Reading.
- `&` and `|` evaluate both sides (G5, SC3, SC4). A guard only "works" there
  when the guarded operation cannot fail in Polars (G1-G4: division by zero is
  inf or null, null inputs give null).
- `when/then/otherwise`. Documented: "Polars computes all expressions passed
  to `when-then-otherwise` in parallel and filters afterwards. This means each
  expression must be valid on its own, regardless of the conditions"
  (`pl.when` docstring, 1.44.2,
  `pl-src:py-polars/src/polars/functions/whenthen.py#L47-L51`). Implemented
  differently since 1.44.0: release notes, "Improve performance of
  when/then/otherwise by masking out unevaluated elements (#28498)"
  (https://github.com/pola-rs/polars/releases/tag/py-1.44.0); the pull request
  says "If the condition is always true or false it won't evaluate the other
  side" and "If a side is elementwise it will have irrelevant elements masked
  out to `null` before evaluating it"
  (https://github.com/pola-rs/polars/pull/28498). In the source the branch's
  input columns are nulled where the branch is not selected
  (`pl-src:crates/polars-expr/src/expressions/ternary.rs#L131-L150`), for
  branches that are elementwise and not a bare column or literal
  (`pl-src:crates/polars-expr/src/planner.rs#L469-L482`). At tags `py-1.38.0`
  through `py-1.43.2` the same file evaluates both branches on the unmodified
  frame (`let op_truthy = || self.truthy.evaluate(df, &state);`, L94-L97 at
  1.38.0). So G7, G8, G9, SC1, SC2, SC5, SC6, SC9, SC14 pass on 1.44.2 and, by
  the source, would fail on 1.38-1.43. Not covered even on 1.44.2: a branch
  without a column to mask (SC7, SC8) and a non-elementwise branch (SC10).
  The request for lazy branch evaluation is still open
  (https://github.com/pola-rs/polars/issues/17601).
- Which operations can fail on data. Polars' own classification
  (`pl-src:crates/polars-plan/src/plans/aexpr/mod.rs#L268-L328`, "Is the
  top-level expression fallible based on the data values"): `list.get` /
  `list.gather` / `arr.get` without `null_on_oob`, `replace_strict`,
  `str.strptime` when strict or with `ambiguous='raise'`, and strict `cast`.
  Others were seen to fail on data here (integer power with a negative
  exponent O8, `pl.date` with impossible components DT28, Decimal division by
  zero Z7, Decimal multiplication overflow K18), so that list is not complete.
- Errors depend on the plan. The same source says of these operations: "we
  push more predicates, but the expression may no longer error if the
  problematic rows are filtered out"
  (`pl-src:crates/polars-plan/src/plans/aexpr/properties/general.rs#L203-L210`),
  and `Expr.cast` documents `strict` as "Raise if cast is invalid on rows after
  predicates are pushed down". Observed: a strict cast followed by a filter does
  not fail (SC12, SC13); the plan printed for SC13 shows the filter below the
  cast.
- Every failure is for the whole query. Python's "this row raised" has no
  native counterpart; the non-strict forms give null for that row instead
  (G6, G11).

### 3.10 NaN

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| Q1 | `row1.f == row1.f` | `c.f == c.f` | f: 1.0; nan | True; False | True; True [Boolean] | DIFF |
| Q2 | `row1.f != row1.f` | `c.f != c.f` | f: 1.0; nan | False; True | False; False [Boolean] | DIFF |
| Q3 | `row1.f > 1` | `c.f > 1` | f: 2.0; nan | True; False | True; True [Boolean] | DIFF |
| Q4 | `row1.f < 1` | `c.f < 1` | f: 0.0; nan | True; False | True; False [Boolean] | same |
| Q5 | `math.isnan(row1.f)` | `c.f.is_nan()` | f: 1.0; nan; None | False; True; TypeError | False; True; null [Boolean] | DIFF |
| Q6 | `row1.f is None` | `c.f.is_null()` | f: 1.0; nan; None | False; False; True | False; False; True [Boolean] | same |
| Q7 | `min(row1.a, row1.b)` | `pl.min_horizontal(c.a, c.b)` | (a, b): (1.0, 2.0); (nan, 2.0); (2.0, nan) | 1.0; nan; 2.0 | 1.0; 2.0; 2.0 [Float64] | DIFF |
| Q8 | `max(row1.a, row1.b)` | `pl.max_horizontal(c.a, c.b)` | (a, b): (1.0, 2.0); (nan, 2.0); (2.0, nan) | 2.0; nan; 2.0 | 2.0; 2.0; 2.0 [Float64] | DIFF |
| Q9 | `pd.isna(row1.f)` | `c.f.is_null() \| c.f.is_nan()` | f: 1.0; nan; None | False; True; True | False; True; True [Boolean] | same |
| Q10 | `pd.isna(row1.s)` | `c.s.is_null()` | s: 'a'; None | False; True | False; True [Boolean] | same |

Reading. Polars: "Any NaN compares equal to any other NaN, and greater than
any non-NaN value"
(https://docs.pola.rs/user-guide/concepts/data-types-and-structures/#floating-point-numbers).
Python follows IEEE 754 (`x != x` is true for NaN, `py-ref:value-comparisons`).
NaN is not null on either side (Q6; user guide: "NaN values are considered to
be a type of floating point data and are not considered to be missing data in
Polars"). `min`/`max` with NaN depend on argument order in Python and skip NaN
in Polars 1.44.x (Q7, Q8); the fix is in the 1.44.0 notes ("Ignore nans in
(min|max)_horizontal (#28710)").

### 3.11 Integer range and powers

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| O1 | `row1.i + 1` | `c.i + 1` | i: 4611686018427387904; 9223372036854775807 | 4611686018427387905; 9223372036854775808 | 4611686018427387905; -9223372036854775808 [Int64] | DIFF |
| O2 | `row1.i * 2` | `c.i * 2` | i: 4611686018427387904; 9223372036854775807 | 9223372036854775808; 18446744073709551614 | -9223372036854775808; -2 [Int64] | DIFF |
| O3 | `abs(row1.i)` | `c.i.abs()` | i: -9223372036854775808 | 9223372036854775808 | -9223372036854775808 [Int64] | DIFF |
| O4 | `row1.i ** 2` | `c.i ** 2` | i: 3; 10000000000 | 9; 100000000000000000000 | 9; 7766279631452241920 [Int64] | DIFF |
| O5 | `row1.i * 10**20` | `c.i * 10**20` | i: 1 | 100000000000000000000 | null [Int64] | DIFF |
| O6 | `row1.i + 2**63` | `c.i + 2**63` | i: 1 | 9223372036854775809 | 9.223372036854776e+18 [Float64] | DIFF |
| O7 | `row1.i * 2` | `c.i.cast(pl.Int128) * 2` | i: 4611686018427387904; 9223372036854775807 | 9223372036854775808; 18446744073709551614 | 9223372036854775808; 18446744073709551614 [Int128] | same |
| O8 | `row1.i ** -1` | `c.i ** -1` | i: 2; 4 | 0.5; 0.25 | query fails: InvalidOperationError | DIFF |
| O9 | `row1.i ** row1.j` | `c.i ** c.j` | (i, j): (2, 3); (2, -1) | 8; 0.5 | query fails: InvalidOperationError | DIFF |
| O10 | `row1.i ** 0.5` | `c.i ** 0.5` | i: 4; -4 | 2.0; (1.2246467991473532e-16+2j) | 2.0; nan [Float64] | DIFF |
| O11 | `row1.i << 2` | `c.i << 2` | i: 3 | 12 | at build: TypeError | DIFF |
| O12 | `row1.i << 2` | `c.i * 2**2` | i: 3 | 12 | 12 [Int64] | same |
| O13 | `row1.i & 3` | `c.i & 3` | i: 6; -1 | 2; 3 | 2; 3 [Int64] | same |

Reading. Python: "Integers have unlimited precision"
(`py-lib:stdtypes#numeric-types-int-float-complex`). Int64 wraps without an
error (O1-O4). A Python integer constant that does not fit Int64 changes the
result type silently: all null for `* 10**20` (O5), Float64 for `+ 2**63`
(O6). Int128 exists and is exact for the cases tried (O7).

### 3.12 `int()`, `float()`, `str()`

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| C1 | `int(row1.f)` | `c.f.cast(pl.Int64)` | f: 4.9; -4.9; 0.5; -0.5 | 4; -4; 0; 0 | 4; -4; 0; 0 [Int64] | same |
| C2 | `int(row1.f)` | `c.f.cast(pl.Int64)` | f: 4.9; nan | 4; ValueError | query fails: InvalidOperationError | DIFF |
| C3 | `int(row1.f)` | `c.f.cast(pl.Int64, strict=False)` | f: 4.9; nan; inf; 1e+30 | 4; ValueError; OverflowError; 1000000000000000019884624838656 | 4; null; null; null [Int64] | DIFF |
| C4 | `int(row1.s)` | `c.s.cast(pl.Int64, strict=False)` | s: '42'; ' 42 '; '4_2'; '+42'; '042'; '4.0'; ''; 'abc' | 42; 42; 42; 42; 42; ValueError; ValueError; ValueError | 42; null; null; 42; 42; null; null; null [Int64] | DIFF |
| C5 | `int(row1.s)` | `c.s.str.strip_chars().cast(pl.Int64, strict=False)` | s: '42'; ' 42 '; '\t42\n' | 42; 42; 42 | 42; 42; 42 [Int64] | same |
| C6 | `int(row1.s)` | `c.s.cast(pl.Int64)` | s: '42'; 'abc' | 42; ValueError | query fails: InvalidOperationError | DIFF |
| C7 | `int(row1.s, 16)` | `c.s.str.to_integer(base=16, strict=False)` | s: 'ff'; '0xff'; 'zz' | 255; 255; ValueError | 255; null; null [Int64] | DIFF |
| C8 | `int(row1.s)` | `c.s.cast(pl.Int64, strict=False)` | s: '99999999999999999999' | 99999999999999999999 | null [Int64] | DIFF |
| C9 | `int(row1.p)` | `c.p.cast(pl.Int64)` | p: True; False | 1; 0 | 1; 0 [Int64] | same |
| C10 | `int(row1.d)` | `c.d.cast(pl.Int64)` | d: D(10.99); D(-10.99); D(2.50); D(3.50) | 10; -10; 2; 3 | 11; -11; 2; 4 [Int64] | DIFF |
| C11 | `int(row1.d)` | `c.d.truncate(0).cast(pl.Int64)` | d: D(10.99); D(-10.99); D(2.50); D(3.50) | 10; -10; 2; 3 | 10; -10; 2; 3 [Int64] | same |
| C12 | `float(row1.s)` | `c.s.cast(pl.Float64, strict=False)` | s: '1.5'; ' 1.5 '; '1e3'; '.5'; '1_0.5'; '1,5'; '' | 1.5; 1.5; 1000.0; 0.5; 10.5; ValueError; ValueError | 1.5; null; 1000.0; 0.5; null; null; null [Float64] | DIFF |
| C13 | `float(row1.s)` | `c.s.cast(pl.Float64, strict=False)` | s: 'nan'; 'inf'; '-inf'; 'Infinity' | nan; inf; -inf; inf | nan; inf; -inf; inf [Float64] | same |
| C14 | `str(row1.f)` | `c.f.cast(pl.String)` | f: 1.0; 0.1; 1234567.0; 1e+16; 0.0001; 1e-05; 1e-07 | '1.0'; '0.1'; '1234567.0'; '1e+16'; '0.0001'; '1e-05'; '1e-07' | '1.0'; '0.1'; '1234567.0'; '1e+16'; '0.0001'; '0.00001'; '1e-7' [String] | DIFF |
| C15 | `str(row1.f)` | `c.f.cast(pl.String)` | f: nan; inf; -0.0 | 'nan'; 'inf'; '-0.0' | 'NaN'; 'inf'; '-0.0' [String] | DIFF |
| C16 | `str(row1.p)` | `c.p.cast(pl.String)` | p: True; False | 'True'; 'False' | 'true'; 'false' [String] | DIFF |
| C17 | `str(row1.i)` | `c.i.cast(pl.String)` | i: 0; -5 | '0'; '-5' | '0'; '-5' [String] | same |

Reading. Python `int()`: "For floating-point numbers, this truncates towards
zero" and a string "can be preceded by + or - ..., have leading zeros, be
surrounded by whitespace, and have single underscores interspersed between
digits" (`py-lib:functions#int`); `float()` likewise strips whitespace and
allows underscores (`py-lib:functions#float`). Polars `cast`: "strict: Raise if
cast is invalid ... If `False`, invalid casts will produce null values"
(`pl-api:Expr.cast`). Float-to-int truncation agrees (C1); the string forms
are narrower in Polars (C4, C7, C12); Decimal-to-int rounds (C10). `str()` of
a float agrees except for small exponents and NaN (C14, C15); booleans print
lower-case (C16).

### 3.13 Strings: case, whitespace, search

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| S1 | `row1.s.upper()` | `c.s.str.to_uppercase()` | s: 'Hello'; 'stra\xdfe' | 'HELLO'; 'STRASSE' | 'HELLO'; 'STRASSE' [String] | same |
| S2 | `row1.s.lower()` | `c.s.str.to_lowercase()` | s: 'Hello'; '\u0391\u03a3' | 'hello'; '\u03b1\u03c2' | 'hello'; '\u03b1\u03c2' [String] | same |
| S3 | `row1.s.title()` | `c.s.str.to_titlecase()` | s: 'hello world'; "they're bill's"; 'a1b2 c3'; '\u01c6 x' | 'Hello World'; "They'Re Bill'S"; 'A1B2 C3'; '\u01c5 X' | 'Hello World'; "They'Re Bill'S"; 'A1B2 C3'; '\u01c4 X' [String] | DIFF |
| S4 | `row1.s.capitalize()` | `c.s.str.head(1).str.to_uppercase() + c.s.str.slice(1).str.to_lowercase()` | s: 'hello WORLD'; '' | 'Hello world'; '' | 'Hello world'; '' [String] | same |
| S5 | `row1.s.strip()` | `c.s.str.strip_chars()` | s: '  a b  '; '\t\na\r\n'; '\x1fa\x1f'; '\xa0a\xa0' | 'a b'; 'a'; 'a'; 'a' | 'a b'; 'a'; '\x1fa\x1f'; 'a' [String] | DIFF |
| S6 | `row1.s.strip('xy')` | `c.s.str.strip_chars('xy')` | s: 'xyaxyb yx' | 'axyb ' | 'axyb ' [String] | same |
| S7 | `row1.s.lstrip()` | `c.s.str.strip_chars_start()` | s: '  a  ' | 'a  ' | 'a  ' [String] | same |
| S8 | `row1.s.removeprefix('ab')` | `c.s.str.strip_prefix('ab')` | s: 'abab'; 'xab' | 'ab'; 'xab' | 'ab'; 'xab' [String] | same |
| S9 | `row1.s.startswith('He')` | `c.s.str.starts_with('He')` | s: 'Hello'; 'hello'; '' | True; False; False | True; False; False [Boolean] | same |
| S10 | `row1.s.startswith(('a', 'b'))` | `c.s.str.starts_with('a') \| c.s.str.starts_with('b')` | s: 'ax'; 'bx'; 'cx' | True; True; False | True; True; False [Boolean] | same |
| S11 | `row1.s.endswith('lo')` | `c.s.str.ends_with('lo')` | s: 'Hello'; 'help' | True; False | True; False [Boolean] | same |
| S12 | `'ell' in row1.s` | `c.s.str.contains('ell', literal=True)` | s: 'hello'; 'help' | True; False | True; False [Boolean] | same |
| S13 | `'.' in row1.s` | `c.s.str.contains('.')` | s: 'a.b'; 'ab' | True; False | True; True [Boolean] | DIFF |
| S14 | `'.' in row1.s` | `c.s.str.contains('.', literal=True)` | s: 'a.b'; 'ab' | True; False | True; False [Boolean] | same |
| S15 | `row1.s.find('l')` | `c.s.str.find('l', literal=True)` | s: 'hello'; 'xyz'; 'h\xe9llo' | 2; -1; 2 | 2; null; 3 [UInt32] | DIFF |
| S16 | `row1.s.count('l')` | `c.s.str.count_matches('l', literal=True)` | s: 'hello'; 'xyz' | 2; 0 | 2; 0 [UInt32] | same |
| S17 | `row1.s.isdigit()` | `c.s.str.contains(r'^[0-9]+$')` | s: '123'; ''; '12a'; '\u0663\u0664'; '\xb2' | True; False; False; True; True | True; False; False; False; False [Boolean] | DIFF |
| S18 | `row1.s.isdigit()` | `c.s.str.contains(r'^\d+$')` | s: '123'; ''; '12a'; '\u0663\u0664'; '\xb2' | True; False; False; True; True | True; False; False; True; False [Boolean] | DIFF |
| S19 | `row1.s.isalpha()` | `c.s.str.contains(r'^\p{L}+$')` | s: 'abc'; ''; 'ab1'; '\xe9' | True; False; False; True | True; False; False; True [Boolean] | same |
| S20 | `row1.s.isspace()` | `c.s.str.contains(r'^\s+$')` | s: ' \t'; ''; '\x1f' | True; False; True | True; False; False [Boolean] | DIFF |
| S21 | `row1.s.isupper()` | `c.s == c.s.str.to_uppercase()` | s: 'ABC'; 'AbC'; '123' | True; False; False | True; False; True [Boolean] | DIFF |

The same comparisons for one character at a time, over all 1,112,064 Unicode
scalar values (obs; this Python carries Unicode 16.0.0 data):

| Python test (one character) vs Polars form | true in Python | true in Polars | Python only | Polars only |
|---|---|---|---|---|
| `re.search(r'\d', ch)` vs `str.contains(r'\d')` | 760 | 760 | 0 | 0 |
| `re.search(r'\w', ch)` vs `str.contains(r'\w')` | 142940 | 144667 | 915 (e.g. U+00B2, U+00B3, U+00B9, U+00BC, U+00BD, U+00BE, U+09F4, U+09F5) | 2642 (e.g. U+0300, U+0301, U+0302, U+0303, U+0304, U+0305, U+0306, U+0307) |
| `re.search(r'\s', ch)` vs `str.contains(r'\s')` | 29 | 25 | 4 (e.g. U+001C, U+001D, U+001E, U+001F) | 0 |
| `ch.isdigit()` vs `str.contains(r'^\d+$')` | 888 | 760 | 128 (e.g. U+00B2, U+00B3, U+00B9, U+1369, U+136A, U+136B, U+136C, U+136D) | 0 |
| `ch.isdecimal()` vs `str.contains(r'^\d+$')` | 760 | 760 | 0 | 0 |
| `ch.isnumeric()` vs `str.contains(r'^\p{N}+$')` | 2002 | 1911 | 91 (e.g. U+3405, U+3483, U+382A, U+3B4D, U+4E00, U+4E03, U+4E07, U+4E09) | 0 |
| `ch.isalpha()` vs `str.contains(r'^\p{L}+$')` | 141028 | 141028 | 0 | 0 |
| `ch.isalnum()` vs `str.contains(r'^[\p{L}\p{N}]+$')` | 142939 | 142939 | 0 | 0 |
| `ch.isspace()` vs `str.contains(r'^\s+$')` | 29 | 25 | 4 (e.g. U+001C, U+001D, U+001E, U+001F) | 0 |
| `ch.isupper()` vs `str.contains(r'^\p{Lu}+$')` | 1978 | 1858 | 120 (e.g. U+2160, U+2161, U+2162, U+2163, U+2164, U+2165, U+2166, U+2167) | 0 |
| `ch.islower()` vs `str.contains(r'^\p{Ll}+$')` | 2569 | 2258 | 311 (e.g. U+00AA, U+00BA, U+02B0, U+02B1, U+02B2, U+02B3, U+02B4, U+02B5) | 0 |

Same sweep, single-character case mapping: `upper()` and `lower()` each differ
for 28 code points (in U+A7CE-U+A7D5 and U+16EA0-U+16ED3); Python leaves all of
them unchanged and Polars maps them, and 54 of the 56 code points involved are
unassigned in Python's Unicode 16.0.0 data. `title()` differs for 169 code
points, none below U+0080; in 163 of them Polars returns its uppercase form
where Python returns the titlecase form (U+00DF: `'Ss'` against `'SS'`). The
source agrees: `to_titlecase` lowercases the string and applies
`c.to_uppercase()` to the first character after each non-alphabetic one
(`pl-src:crates/polars-ops/src/chunked_array/strings/case.rs#L146-L154`).

Reading. `str.find`: Python returns "-1 if sub is not found"
(`py-lib:stdtypes#str.find`); Polars returns "the bytes offset of the first
substring matching a pattern. If the pattern is not found, returns None"
(`pl-api:Expr.str.find`), hence S15. `str.strip`: "Whitespace characters are
defined by str.isspace()" (`py-lib:stdtypes#str.strip`); the two sides differ
on exactly four characters, U+001C to U+001F (S5 and the sweep). `isdigit`:
"Digits include decimal characters and digits that need special handling, such
as the compatibility superscript digits" (`py-lib:stdtypes#str.isdigit`),
which `\d` does not include (S17, S18), while `isdecimal`, `isalpha` and
`isalnum` have exact regex forms. Search functions take a regex by default;
only `literal=True` matches Python's substring test (S13, S14).

### 3.14 Strings: replace, split, join, pad, length, slicing, formatting

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| U1 | `row1.s.replace('.', '-')` | `c.s.str.replace_all('.', '-')` | s: 'a.b.c' | 'a-b-c' | '-----' [String] | DIFF |
| U2 | `row1.s.replace('.', '-')` | `c.s.str.replace_all('.', '-', literal=True)` | s: 'a.b.c'; 'abc' | 'a-b-c'; 'abc' | 'a-b-c'; 'abc' [String] | same |
| U3 | `row1.s.replace('a', '$1')` | `c.s.str.replace_all('a', '$1', literal=True)` | s: 'banana' | 'b$1n$1n$1' | 'b$1n$1n$1' [String] | same |
| U4 | `row1.s.replace('a', 'x', 1)` | `c.s.str.replace('a', 'x', literal=True, n=1)` | s: 'banana' | 'bxnana' | 'bxnana' [String] | same |
| U5 | `row1.s.split(',')` | `c.s.str.split(',')` | s: 'a,b,,c'; ''; 'abc' | ['a', 'b', '', 'c']; ['']; ['abc'] | ['a', 'b', '', 'c']; ['']; ['abc'] [List(String)] | same |
| U6 | `row1.s.split()` | `c.s.str.split(' ')` | s: 'a  b c' | ['a', 'b', 'c'] | ['a', '', 'b', 'c'] [List(String)] | DIFF |
| U7 | `row1.s.split()` | `c.s.str.extract_all(r'\S+')` | s: 'a  b c'; ' a '; '' | ['a', 'b', 'c']; ['a']; [] | ['a', 'b', 'c']; ['a']; [] [List(String)] | same |
| U8 | `row1.s.split(',')[1]` | `c.s.str.split(',').list.get(1)` | s: 'a,b'; 'abc' | 'b'; IndexError | query fails: ComputeError | DIFF |
| U9 | `row1.s.split(',')[1]` | `c.s.str.split(',').list.get(1, null_on_oob=True)` | s: 'a,b'; 'abc' | 'b'; IndexError | 'b'; null [String] | DIFF |
| U10 | `row1.s.split(',')[-1]` | `c.s.str.split(',').list.last()` | s: 'a,b'; 'abc' | 'b'; 'abc' | 'b'; 'abc' [String] | same |
| U11 | `'-'.join([row1.s, row1.t])` | `pl.concat_str([c.s, c.t], separator='-')` | (s, t): ('a', 'b') | 'a-b' | 'a-b' [String] | same |
| U12 | `row1.s.zfill(5)` | `c.s.str.zfill(5)` | s: '42'; '-42'; '+42'; '123456'; '\xe9' | '00042'; '-0042'; '+0042'; '123456'; '0000\xe9' | '00042'; '-0042'; '+0042'; '123456'; '000\xe9' [String] | DIFF |
| U13 | `row1.s.rjust(5, '*')` | `c.s.str.pad_start(5, '*')` | s: 'ab'; 'abcdef'; '\xe9' | '***ab'; 'abcdef'; '****\xe9' | '***ab'; 'abcdef'; '****\xe9' [String] | same |
| U14 | `row1.s.ljust(5)` | `c.s.str.pad_end(5)` | s: 'ab' | 'ab   ' | 'ab   ' [String] | same |
| U15 | `len(row1.s)` | `c.s.str.len_chars()` | s: 'abc'; 'h\xe9llo'; '\U0001f600'; '' | 3; 5; 1; 0 | 3; 5; 1; 0 [UInt32] | same |
| U16 | `len(row1.s)` | `c.s.str.len_bytes()` | s: 'abc'; 'h\xe9llo'; '\U0001f600' | 3; 5; 1 | 3; 6; 4 [UInt32] | DIFF |
| U17 | `row1.s[0]` | `c.s.str.slice(0, 1)` | s: 'abc'; '\xe9x'; '' | 'a'; '\xe9'; IndexError | 'a'; '\xe9'; '' [String] | DIFF |
| U18 | `row1.s[-1]` | `c.s.str.tail(1)` | s: 'abc'; '' | 'c'; IndexError | 'c'; '' [String] | DIFF |
| U19 | `row1.s[1:3]` | `c.s.str.slice(1, 2)` | s: 'abcdef'; 'a'; 'h\xe9llo' | 'bc'; ''; '\xe9l' | 'bc'; ''; '\xe9l' [String] | same |
| U20 | `row1.s[:3]` | `c.s.str.head(3)` | s: 'abcdef'; 'a' | 'abc'; 'a' | 'abc'; 'a' [String] | same |
| U21 | `row1.s[3:]` | `c.s.str.slice(3)` | s: 'abcdef'; 'a' | 'def'; '' | 'def'; '' [String] | same |
| U22 | `row1.s[-3:]` | `c.s.str.tail(3)` | s: 'abcdef'; 'a' | 'def'; 'a' | 'def'; 'a' [String] | same |
| U23 | `row1.s[:-1]` | `c.s.str.head(-1)` | s: 'abcdef'; 'a'; '' | 'abcde'; ''; '' | 'abcde'; ''; '' [String] | same |
| U24 | `row1.s[::-1]` | `c.s.str.reverse()` | s: 'abc' | 'cba' | 'cba' [String] | same |
| U25 | `row1.s[::2]` | (none found) | s: 'abcdef' | 'ace' | - | n/a |
| U26 | `f'{row1.s}:{row1.i}'` | `pl.format('{}:{}', c.s, c.i)` | (s, i): ('a', 1) | 'a:1' | 'a:1' [String] | same |
| U27 | `f'{row1.f}'` | `pl.format('{}', c.f)` | f: 1.0; 0.5; 1e-07 | '1.0'; '0.5'; '1e-07' | '1.0'; '0.5'; '1e-7' [String] | DIFF |
| U28 | `f'{row1.p}'` | `pl.format('{}', c.p)` | p: True | 'True' | 'true' [String] | DIFF |
| U29 | `f'{row1.f:.2f}'` | `c.f.round(2).cast(pl.String)` | f: 1.5; 2.675; 0.005 | '1.50'; '2.67'; '0.01' | '1.5'; '2.68'; '0.0' [String] | DIFF |
| U30 | `f'{row1.f:.2f}'` | `c.f.cast(pl.Decimal(38, 2)).cast(pl.String)` | f: 1.5; 2.675; 0.005; -0.001 | '1.50'; '2.67'; '0.01'; '-0.00' | '1.50'; '2.68'; '0.00'; '0.00' [String] | DIFF |
| U31 | `f'{row1.i:05d}'` | `c.i.cast(pl.String).str.zfill(5)` | i: 42; -42; 123456 | '00042'; '-0042'; '123456' | '00042'; '-0042'; '123456' [String] | same |
| U32 | `f'{row1.i:>6}'` | `c.i.cast(pl.String).str.pad_start(6)` | i: 42; -42 | '    42'; '   -42' | '    42'; '   -42' [String] | same |
| U33 | `f'{row1.i:,}'` | (none found) | i: 1234567 | '1,234,567' | - | n/a |
| U34 | `'%s-%s' % (row1.s, row1.i)` | `pl.format('{}-{}', c.s, c.i)` | (s, i): ('a', 1) | 'a-1' | 'a-1' [String] | same |

Reading. `str.slice` and `str.len_chars` count Unicode scalar values, the same
unit as Python (`pl-api:Expr.str.slice`, `pl-api:Expr.str.len_chars`; U15,
U19). `zfill`: "intended for padding numeric strings. If your data contains
non-ASCII characters, use pad_start() instead" (`pl-api:Expr.str.zfill`; U12).
An out-of-range index is `''` or null in Polars and `IndexError` in Python
(U9, U17, U18). `f"{x:.2f}"` has no exact form: `round(2)` drops trailing
zeros and rounds differently (U29); going through Decimal keeps the zeros but
still rounds differently and loses the sign of negative zero (U30).

### 3.15 `re`

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| P1 | `re.sub(r'\s+', '_', row1.s)` | `c.s.str.replace_all(r'\s+', '_')` | s: 'a  b\tc'; 'abc' | 'a_b_c'; 'abc' | 'a_b_c'; 'abc' [String] | same |
| P2 | `re.sub(r'(\w+)@(\w+)', r'\2@\1', row1.s)` | `c.s.str.replace_all(r'(\w+)@(\w+)', '${2}@${1}')` | s: 'user@host' | 'host@user' | 'host@user' [String] | same |
| P3 | `re.sub(r'(\w+)@(\w+)', r'\2@\1', row1.s)` | `c.s.str.replace_all(r'(\w+)@(\w+)', r'\2@\1')` | s: 'user@host' | 'host@user' | '\\2@\\1' [String] | DIFF |
| P4 | `re.sub(r'(a)', r'\1x', row1.s)` | `c.s.str.replace_all(r'(a)', '$1x')` | s: 'ba' | 'bax' | 'b' [String] | DIFF |
| P5 | `re.sub(r'(a)', r'\1x', row1.s)` | `c.s.str.replace_all(r'(a)', '${1}x')` | s: 'ba' | 'bax' | 'bax' [String] | same |
| P6 | `re.sub('a+', 'cost $5', row1.s)` | `c.s.str.replace_all('a+', 'cost $5')` | s: 'ba' | 'bcost $5' | 'bcost ' [String] | DIFF |
| P7 | `re.sub('a+', 'cost $5', row1.s)` | `c.s.str.replace_all('a+', 'cost $$5')` | s: 'ba' | 'bcost $5' | 'bcost $5' [String] | same |
| P8 | `re.sub('a', 'cost $5', row1.s)` | `c.s.str.replace_all('a', 'cost $5')` | s: 'ba' | 'bcost $5' | 'bcost $5' [String] | same |
| P9 | `re.sub('a', 'cost $5', row1.s)` | `c.s.str.replace_all('a', 'cost $$5')` | s: 'ba' | 'bcost $5' | 'bcost $$5' [String] | DIFF |
| P10 | `re.sub('x*', '-', row1.s)` | `c.s.str.replace_all('x*', '-')` | s: 'abc'; 'axxb' | '-a-b-c-'; '-a--b-' | '-a-b-c-'; '-a-b-' [String] | DIFF |
| P11 | `re.sub('a', 'b', row1.s, count=1)` | `c.s.str.replace('a', 'b')` | s: 'banana' | 'bbnana' | 'bbnana' [String] | same |
| P12 | `re.sub('A', 'b', row1.s, flags=re.I)` | `c.s.str.replace_all('(?i)A', 'b')` | s: 'banana' | 'bbnbnb' | 'bbnbnb' [String] | same |
| P13 | `bool(re.search(r'\d+', row1.s))` | `c.s.str.contains(r'\d+')` | s: 'ab12'; 'abc'; '' | True; False; False | True; False; False [Boolean] | same |
| P14 | `bool(re.match(r'a\|b', row1.s))` | `c.s.str.contains(r'^a\|b')` | s: 'xb'; 'ax' | False; True | True; True [Boolean] | DIFF |
| P15 | `bool(re.match(r'a\|b', row1.s))` | `c.s.str.contains(r'^(?:a\|b)')` | s: 'xb'; 'ax' | False; True | False; True [Boolean] | same |
| P16 | `bool(re.fullmatch(r'\d+', row1.s))` | `c.s.str.contains(r'^(?:\d+)$')` | s: '12'; '12a'; '12\n'; '' | True; False; False; False | True; False; False; False [Boolean] | same |
| P17 | `bool(re.search(r'\d+$', row1.s))` | `c.s.str.contains(r'\d+$')` | s: 'a12'; 'a12\n' | True; True | True; False [Boolean] | DIFF |
| P18 | `bool(re.search(r'\w', row1.s))` | `c.s.str.contains(r'\w')` | s: '\xe9'; '\xb2'; '\u0e34'; '\u203f' | True; True; False; False | True; False; True; True [Boolean] | DIFF |
| P19 | `bool(re.search(r'\s', row1.s))` | `c.s.str.contains(r'\s')` | s: '\x1f'; '\xa0'; '\x0b' | True; True; True | False; True; True [Boolean] | DIFF |
| P20 | `bool(re.search(r'foo(?=bar)', row1.s))` | `c.s.str.contains(r'foo(?=bar)')` | s: 'foobar'; 'foobaz' | True; False | query fails: ComputeError | DIFF |
| P21 | `bool(re.search(r'(?<=a)b', row1.s))` | `c.s.str.contains(r'(?<=a)b')` | s: 'ab'; 'cb' | True; False | query fails: ComputeError | DIFF |
| P22 | `bool(re.search(r'(a)\1', row1.s))` | `c.s.str.contains(r'(a)\1')` | s: 'aa'; 'ab' | True; False | query fails: ComputeError | DIFF |
| P23 | `bool(re.search(r'ab\Z', row1.s))` | `c.s.str.contains(r'ab\Z')` | s: 'ab' | True | query fails: ComputeError | DIFF |
| P24 | `bool(re.search(r'a{,2}b', row1.s))` | `c.s.str.contains(r'a{,2}b')` | s: 'aab' | True | query fails: ComputeError | DIFF |
| P25 | `re.findall(r'\d+', row1.s)` | `c.s.str.extract_all(r'\d+')` | s: 'a1b22c'; 'abc' | ['1', '22']; [] | ['1', '22']; [] [List(String)] | same |
| P26 | `re.findall(r'(\d)\w', row1.s)` | `c.s.str.extract_all(r'(\d)\w')` | s: '1a2b' | ['1', '2'] | ['1a', '2b'] [List(String)] | DIFF |
| P27 | `re.search(r'(\d+)-(\d+)', row1.s).group(2)` | `c.s.str.extract(r'(\d+)-(\d+)', 2)` | s: 'x12-34y'; 'none' | '34'; AttributeError | '34'; null [String] | DIFF |
| P28 | `re.split(r'[,;]', row1.s)` | `c.s.str.split(r'[,;]')` | s: 'a,b;c' | ['a', 'b', 'c'] | ['a,b;c'] [List(String)] | DIFF |
| P29 | `re.split(r'[,;]', row1.s)` | `c.s.str.split(r'[,;]', literal=False)` | s: 'a,b;c'; 'abc'; ',a,' | ['a', 'b', 'c']; ['abc']; ['', 'a', ''] | ['a', 'b', 'c']; ['abc']; ['', 'a', ''] [List(String)] | same |
| P30 | `re.split(r'(,)', row1.s)` | `c.s.str.split(r'(,)', literal=False)` | s: 'a,b' | ['a', ',', 'b'] | ['a', 'b'] [List(String)] | DIFF |
| P31 | `re.sub(r'(a+)', lambda m: m.group(1).upper(), row1.s)` | (none found) | s: 'baab' | 'bAAb' | - | n/a |
| P32 | `re.sub('a+', 'b', row1.s, count=2)` | `c.s.str.replace('a+', 'b', n=2)` | s: 'baanaana' | 'bbnbna' | query fails: ComputeError | DIFF |
| P33 | `re.sub('a', 'b', row1.s, count=2)` | `c.s.str.replace('a', 'b', n=2)` | s: 'banana' | 'bbnbna' | 'bbnbna' [String] | same |

Reading. Polars patterns are those of the Rust `regex` crate (every `str`
docstring links https://docs.rs/regex/latest/regex/), whose syntax "lacks
several features that are not known how to implement efficiently. This
includes, but is not limited to, look-around and backreferences". Lookahead,
lookbehind, backreferences, `\Z` and `{,n}` fail when the query runs (P20-P24),
not when the expression is built. `$`: Python "Matches the end of the string
or just before the newline at the end of the string" (`py-lib:re#regular-expression-syntax`);
Rust matches only the very end (P17). Character classes (sweep in 3.13): `\d`
matches the same 760 code points on both sides, `\s` differs for 4, `\w`
differs for 3,557 (915 matched only by Python, 2,642 only by Polars; P18,
P19). Replacement text: Polars uses `$1`, `${1}`, `${name}` and "you should
escape [a literal `$`] by doubling it up as `$$`, or set `literal=True`"
(`pl-api:Expr.str.replace_all`). Not in the
documentation but in the source: a pattern is also treated as a literal when
it contains no ASCII punctuation (`literal || is_literal_pat(pat)`, with
`is_literal_pat` = `pat.chars().all(|c| !c.is_ascii_punctuation())`,
`pl-src:crates/polars-expr/src/dispatch/strings.rs#L609-L611`, `#L694-L699`),
and the replacement is then inserted unchanged. So for the pattern `a`, `$5`
stays `$5` and `$$5` stays `$$5` (P8, P9), while for `a+`, `$5` is an empty
group and `$$5` is `$5` (P6, P7). The same file limits a regex `replace` to one
replacement: "regex replacement with 'n > 1' not yet supported" (`#L632-L634`;
P32, P33). `re.findall` and `re.split` return capture groups when
the pattern has them; `extract_all` and `split` do not (P26, P30).

### 3.16 `math`

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| H1 | `math.floor(row1.f)` | `c.f.floor()` | f: 2.5; -2.5 | 2; -3 | 2.0; -3.0 [Float64] | type |
| H2 | `math.floor(row1.f)` | `c.f.floor().cast(pl.Int64)` | f: 2.5; -2.5 | 2; -3 | 2; -3 [Int64] | same |
| H3 | `math.ceil(row1.f)` | `c.f.ceil().cast(pl.Int64)` | f: 2.5; -2.5 | 3; -2 | 3; -2 [Int64] | same |
| H4 | `math.trunc(row1.f)` | `c.f.cast(pl.Int64)` | f: 2.5; -2.5 | 2; -2 | 2; -2 [Int64] | same |
| H5 | `math.sqrt(row1.f)` | `c.f.sqrt()` | f: 4.0; 2.0; -1.0 | 2.0; 1.4142135623730951; ValueError | 2.0; 1.4142135623730951; nan [Float64] | DIFF |
| H6 | `math.log(row1.f)` | `c.f.log()` | f: 1.0; 10.0; 0.0; -1.0 | 0.0; 2.302585092994046; ValueError; ValueError | 0.0; 2.302585092994046; -inf; nan [Float64] | DIFF |
| H7 | `math.log10(row1.f)` | `c.f.log10()` | f: 1000.0; 100.0; 1.0 | 3.0; 2.0; 0.0 | 2.9999999999999996; 2.0; 0.0 [Float64] | DIFF |
| H8 | `math.log(row1.f, 2)` | `c.f.log(2)` | f: 8.0; 3.0 | 3.0; 1.5849625007211563 | 3.0; 1.5849625007211563 [Float64] | same |
| H9 | `math.exp(row1.f)` | `c.f.exp()` | f: 1.0; 1000.0 | 2.718281828459045; OverflowError | 2.718281828459045; inf [Float64] | DIFF |
| H10 | `math.pow(row1.f, 0.5)` | `c.f.pow(0.5)` | f: 9.0; -4.0 | 3.0; ValueError | 3.0; nan [Float64] | DIFF |
| H11 | `math.atan2(row1.a, row1.b)` | `pl.arctan2(c.a, c.b)` | (a, b): (1.0, 1.0) | 0.7853981633974483 | 0.7853981633974483 [Float64] | same |
| H12 | `math.isnan(row1.f)` | `c.f.is_nan()` | f: nan; 1.0 | True; False | True; False [Boolean] | same |
| H13 | `math.copysign(row1.a, row1.b)` | `c.a.abs() * c.b.sign()` | (a, b): (3.0, -1.0); (3.0, 0.0) | -3.0; 3.0 | -3.0; 0.0 [Float64] | DIFF |
| H14 | `math.hypot(row1.a, row1.b)` | `(c.a ** 2 + c.b ** 2).sqrt()` | (a, b): (3.0, 4.0); (1e+200, 1e+200) | 5.0; 1.414213562373095e+200 | 5.0; inf [Float64] | DIFF |
| H15 | `math.gcd(row1.i, 12)` | (none found) | i: 18 | 6 | - | n/a |

Reading. `math.floor` and `math.ceil` return int in Python and Float64 in
Polars (H1). Domain errors do not raise in Polars (H5, H6, H9, H10). Results
are not guaranteed bit-identical: `log10(1000.0)` differs in the last digit
(H7), and the user guide says Polars "does not provide guarantees on the error
unless mentioned otherwise"
(https://docs.pola.rs/user-guide/concepts/data-types-and-structures/#floating-point-numbers).
`+`, `-`, `*`, `/` on Float64 gave identical bits in every case tried.

### 3.17 `datetime`

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| DT1 | `row1.d.year` | `c.d.dt.year()` | d: <2024-03-10 14:05:09.123456>; None | 2024; AttributeError | 2024; null [Int32] | DIFF |
| DT2 | `row1.d.weekday()` | `c.d.dt.weekday()` | d: <2024-03-10 14:05:09.123456>; <2024-03-11 00:00:00> | 6; 0 | 7; 1 [Int8] | DIFF |
| DT3 | `row1.d.weekday()` | `c.d.dt.weekday() - 1` | d: <2024-03-10 14:05:09.123456>; <2024-03-11 00:00:00> | 6; 0 | 6; 0 [Int8] | same |
| DT4 | `row1.d.isoweekday()` | `c.d.dt.weekday()` | d: <2024-03-10 14:05:09.123456>; <2024-03-11 00:00:00> | 7; 1 | 7; 1 [Int8] | same |
| DT5 | `row1.d.date()` | `c.d.dt.date()` | d: <2024-03-10 14:05:09.123456> | <2024-03-10> | <2024-03-10> [Date] | same |
| DT6 | `row1.d.replace(day=1)` | `c.d.dt.replace(day=1)` | d: <2024-03-10 14:05:09.123456> | <2024-03-01 14:05:09.123456> | <2024-03-01 14:05:09.123456> [Datetime[us]] | same |
| DT7 | `row1.d.strftime('%d/%m/%Y %H:%M:%S')` | `c.d.dt.strftime('%d/%m/%Y %H:%M:%S')` | d: <2024-03-10 14:05:09.123456> | '10/03/2024 14:05:09' | '10/03/2024 14:05:09' [String] | same |
| DT8 | `row1.d.strftime('%S.%f')` | `c.d.dt.strftime('%S.%f')` | d: <2024-03-10 14:05:09.123456> | '09.123456' | '09.123456000' [String] | DIFF |
| DT9 | `row1.d.strftime('%S.%f')` | `c.d.dt.strftime('%S%.6f')` | d: <2024-03-10 14:05:09.123456>; <2024-03-11 00:00:00> | '09.123456'; '00.000000' | '09.123456'; '00.000000' [String] | same |
| DT10 | `row1.d.strftime('%a %b %p %j')` | `c.d.dt.strftime('%a %b %p %j')` | d: <2024-03-10 14:05:09.123456> | 'Sun Mar PM 070' | 'Sun Mar PM 070' [String] | same |
| DT11 | `row1.d.isoformat()` | `c.d.dt.to_string('iso')` | d: <2024-03-10 14:05:09.123456>; <2024-03-11 00:00:00> | '2024-03-10T14:05:09.123456'; '2024-03-11T00:00:00' | '2024-03-10 14:05:09.123456'; '2024-03-11 00:00:00.000000' [String] | DIFF |
| DT12 | `str(row1.d)` | `c.d.cast(pl.String)` | d: <2024-03-10 14:05:09.123456>; <2024-03-11 00:00:00> | '2024-03-10 14:05:09.123456'; '2024-03-11 00:00:00' | '2024-03-10 14:05:09.123456'; '2024-03-11 00:00:00.000000' [String] | DIFF |
| DT13 | `datetime.datetime.strptime(row1.s, '%Y-%m-%d')` | `c.s.str.to_datetime('%Y-%m-%d', strict=False)` | s: '2024-03-10'; '2024-3-1'; ' 2024-03-10'; '24-03-10'; '2024-02-30'; '' | <2024-03-10 00:00:00>; <2024-03-01 00:00:00>; ValueError; ValueError; ValueError; ValueError | <2024-03-10 00:00:00>; <2024-03-01 00:00:00>; <2024-03-10 00:00:00>; <0024-03-10 00:00:00>; null; null [Datetime[us]] | DIFF |
| DT14 | `datetime.datetime.strptime(row1.s, '%Y-%m-%d')` | `c.s.str.to_datetime('%Y-%m-%d')` | s: '2024-03-10'; 'bad' | <2024-03-10 00:00:00>; ValueError | query fails: InvalidOperationError | DIFF |
| DT15 | `datetime.datetime.strptime(row1.s, '%H:%M:%S.%f').time()` | `c.s.str.to_time('%H:%M:%S.%f', strict=False)` | s: '14:05:09.123456'; '14:05:09.5' | <14:05:09.123456>; <14:05:09.500000> | <14:05:09.000123>; <14:05:09> [Time] | DIFF |
| DT16 | `datetime.datetime.strptime(row1.s, '%H:%M:%S.%f').time()` | `c.s.str.to_time('%H:%M:%S%.f', strict=False)` | s: '14:05:09.123456'; '14:05:09.5' | <14:05:09.123456>; <14:05:09.500000> | <14:05:09.123456>; <14:05:09.500000> [Time] | same |
| DT17 | `datetime.datetime.strptime(row1.s, '%y%m%d').date()` | `c.s.str.to_date('%y%m%d', strict=False)` | s: '690101'; '680101'; '700101' | <1969-01-01>; <2068-01-01>; <1970-01-01> | <2069-01-01>; <2068-01-01>; <1970-01-01> [Date] | DIFF |
| DT18 | `row1.a - row1.b` | `c.a - c.b` | (a, b): (<2024-03-10 12:00:00>, <2024-03-09 13:00:00>); (<2024-03-09 13:00:00>, <2024-03-10 12:00:00>) | td(23:00:00); td(-1 day, 1:00:00) | td(23:00:00); td(-1 day, 1:00:00) [Duration[us]] | same |
| DT19 | `(row1.a - row1.b).days` | `(c.a - c.b).dt.total_days()` | (a, b): (<2024-03-10 12:00:00>, <2024-03-09 13:00:00>); (<2024-03-09 13:00:00>, <2024-03-10 12:00:00>) | 0; -1 | 0; 0 [Int64] | DIFF |
| DT20 | `(row1.a - row1.b).days` | `(c.a - c.b).dt.total_microseconds() // 86_400_000_000` | (a, b): (<2024-03-10 12:00:00>, <2024-03-09 13:00:00>); (<2024-03-09 13:00:00>, <2024-03-10 12:00:00>) | 0; -1 | 0; -1 [Int64] | same |
| DT21 | `(row1.a - row1.b).total_seconds()` | `(c.a - c.b).dt.total_seconds()` | (a, b): (<2024-03-10 12:00:00>, <2024-03-09 13:00:00>) | 82800.0 | 82800 [Int64] | type |
| DT22 | `(row1.a - row1.b).total_seconds()` | `(c.a - c.b).dt.total_seconds(fractional=True)` | (a, b): (<2024-03-10 12:00:00>, <2024-03-09 13:00:00>) | 82800.0 | 82800.0 [Float64] | same |
| DT23 | `row1.a + datetime.timedelta(days=1)` | `c.a + pl.duration(days=1)` | a: <2024-03-10 12:00:00>; None | <2024-03-11 12:00:00>; TypeError | <2024-03-11 12:00:00>; null [Datetime[us]] | DIFF |
| DT24 | `row1.a + datetime.timedelta(days=row1.n)` | `c.a + pl.duration(days=c.n)` | (a, n): (<2024-03-10 12:00:00>, 2) | <2024-03-12 12:00:00> | <2024-03-12 12:00:00> [Datetime[us]] | same |
| DT25 | `row1.a > datetime.datetime(2024, 1, 1)` | `c.a > datetime.datetime(2024, 1, 1)` | a: <2024-03-10 12:00:00> | True | True [Boolean] | same |
| DT26 | `row1.d == row1.a` | `c.d == c.a` | (d, a): (<2024-03-10>, <2024-03-10 00:00:00>) | False | True [Boolean] | DIFF |
| DT27 | `row1.d < row1.a` | `c.d < c.a` | (d, a): (<2024-03-10>, <2024-03-10 01:00:00>) | TypeError | True [Boolean] | DIFF |
| DT28 | `datetime.date(row1.y, row1.m, 30)` | `pl.date(c.y, c.m, 30)` | (y, m): (2024, 4); (2024, 2) | <2024-04-30>; ValueError | query fails: ComputeError | DIFF |
| DT29 | `datetime.date(row1.y, row1.m, 30)` | `pl.date(c.y, c.m, 30)` | (y, m): (2024, 4) | <2024-04-30> | <2024-04-30> [Date] | same |

Reading. `weekday()`: Python "Monday is 0 and Sunday is 6"
(`py-lib:datetime#datetime.datetime.weekday`); Polars "Returns the ISO weekday
number where monday = 1 and sunday = 7" (`pl-api:Expr.dt.weekday`). Formats:
Polars uses chrono's directives (`pl-api:Expr.dt.strftime`), where "%f counts
the number of nanoseconds since the last whole second, while %.f is a fraction
of a second" and for `%y` "values greater or equal to 70 are interpreted as
being in the 20th century, values smaller than 70 in the 21st century"
(https://docs.rs/chrono/latest/chrono/format/strftime/index.html); Python's
`%f` is "Microsecond as a decimal number, zero-padded to 6 digits" and on
parsing "accepts from one to six digits and zero pads on the right"
(`py-lib:datetime#strftime-and-strptime-format-codes`). Hence DT8, DT15, DT17
(Python read `69` as 1969: obs). `isoformat()` prints microseconds only when
non-zero (`py-lib:datetime#datetime.datetime.isoformat`); Polars always prints
them and uses a space (DT11, DT12). `timedelta.days` is normalised so that a
negative difference of 23 hours is `-1 day, 1:00:00` (DT18, DT19).

### 3.18 `Decimal`

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| K1 | `row1.a + row1.b` | `c.a + c.b` | (a, b): (D(10.10), D(3.00)); (D(-0.05), D(0.30)) | D(13.10); D(0.25) | D(13.10); D(0.25) [Decimal(38,2)] | same |
| K2 | `row1.a * row1.b` | `c.a * c.b` | (a, b): (D(10.10), D(3.00)); (D(-0.05), D(0.30)) | D(30.3000); D(-0.0150) | D(30.30); D(-0.02) [Decimal(38,2)] | DIFF |
| K3 | `row1.a * Decimal('1.05')` | `c.a * Decimal('1.05')` | (a, b): (D(10.10), D(3.00)); (D(-0.05), D(0.30)) | D(10.6050); D(-0.0525) | D(10.60); D(-0.05) [Decimal(38,2)] | DIFF |
| K4 | `row1.a / row1.b` | `c.a / c.b` | (a, b): (D(10.10), D(3.00)); (D(-0.05), D(0.30)) | D(3.366666666666666666666666667); D(-0.1666666666666666666666666667) | D(3.37); D(-0.17) [Decimal(38,2)] | DIFF |
| K5 | `row1.a * 3` | `c.a * 3` | (a, b): (D(10.10), D(3.00)); (D(-0.05), D(0.30)) | D(30.30); D(-0.15) | D(30.30); D(-0.15) [Decimal(38,2)] | same |
| K6 | `row1.a // row1.b` | `c.a // c.b` | (a, b): (D(10.10), D(3.00)); (D(-0.05), D(0.30)) | D(3); D(-0) | query fails: InvalidOperationError | DIFF |
| K7 | `row1.a % row1.b` | `c.a % c.b` | (a, b): (D(10.10), D(3.00)); (D(-0.05), D(0.30)) | D(1.10); D(-0.05) | query fails: InvalidOperationError | DIFF |
| K8 | `row1.a ** 2` | `c.a ** 2` | (a, b): (D(10.10), D(3.00)); (D(-0.05), D(0.30)) | D(102.0100); D(0.0025) | query fails: InvalidOperationError | DIFF |
| K9 | `row1.a + 1.5` | `c.a + 1.5` | (a, b): (D(10.10), D(3.00)) | TypeError | 11.6 [Float64] | DIFF |
| K10 | `row1.a == 10.1` | `c.a == 10.1` | (a, b): (D(10.10), D(3.00)) | False | True [Boolean] | DIFF |
| K11 | `row1.a == Decimal('10.1')` | `c.a == Decimal('10.1')` | (a, b): (D(10.10), D(3.00)) | True | True [Boolean] | same |
| K12 | `Decimal('1') / Decimal('3')` | `pl.lit(Decimal('1')) / pl.lit(Decimal('3'))` | x: 1 | D(0.3333333333333333333333333333) | D(0) [Decimal(38,0)] | DIFF |
| K13 | `Decimal('1.10') * Decimal('1.10')` | `pl.lit(Decimal('1.10')) * pl.lit(Decimal('1.10'))` | x: 1 | D(1.2100) | D(1.21) [Decimal(38,2)] | type |
| K14 | `Decimal(row1.s)` | `c.s.cast(pl.Decimal(38, 2), strict=False)` | s: '10.10'; '10.105'; '10.115'; '1e2'; ' 1.5 '; 'abc' | D(10.10); D(10.105); D(10.115); D(1E+2); D(1.5); InvalidOperation | D(10.10); D(10.10); D(10.12); D(100.00); null; null [Decimal(38,2)] | DIFF |
| K15 | `Decimal(str(row1.f))` | `c.f.cast(pl.Decimal(38, 2))` | f: 10.1; 2.675; 0.005 | D(10.1); D(2.675); D(0.005) | D(10.10); D(2.68); D(0.00) [Decimal(38,2)] | DIFF |
| K16 | `str(row1.a)` | `c.a.cast(pl.String)` | a: D(10.10); D(-0.05) | '10.10'; '-0.05' | '10.10'; '-0.05' [String] | same |
| K17 | `float(row1.a)` | `c.a.cast(pl.Float64)` | a: D(10.10) | 10.1 | 10.1 [Float64] | same |
| K18 | `row1.a * row1.a` | `c.a * c.a` | a: D(12345678901234567890.12) | D(1.524157875323883675048681628E+38) | query fails: ComputeError | DIFF |
| K19 | `row1.a + row1.a` | `c.a + c.a` | a: D(99999999999999999999999999999999999.99) | D(2.000000000000000000000000000E+35) | D(199999999999999999999999999999999999.98) [Decimal(38,2)] | DIFF |
| K20 | `row1.a.sqrt()` | `c.a.sqrt()` | a: D(2.00) | D(1.414213562373095048801688724) | 1.4142135623730951 [Float64] | DIFF |

Reading. Python: default context "prec=28, rounding=ROUND_HALF_EVEN", exact
scale tracking, and mixing with float allowed only in the constructor and in
comparisons, where "Both conversion and comparisons are exact"
(`py-lib:decimal#decimal.FloatOperation`). Polars: "Decimal 128-bit type with
an optional precision and non-negative scale", precision at most 38
(https://docs.pola.rs/api/python/stable/reference/api/polars.datatypes.Decimal.html).
Observed: add and subtract are exact (K1) and exceed Python's 28 digits (K19);
multiply and divide keep the larger input scale and round to it (K2-K4), so
`Decimal('1') / Decimal('3')` is 0 (K12); `//`, `%`, `**` are not supported
(K6-K8); Decimal with float silently becomes Float64 (K9); overflow and
division by zero fail the query (K18, Z7). The rounding in these rows is half
to even by the source (`pl-src:crates/polars-compute/src/decimal.rs`):
multiplication "Computes round(l * r / 10^s), rounding to nearest even"
(L523-L526), division likewise (L553-L564), string parsing "Round-to-even"
(L714, L768), Decimal to integer through `div_128_pow10`, "rounding to nearest
even" (L249, L463-L466; row C10), and Float64 to Decimal as
`(x * POW10_F64[s]).round_ties_even()` under the comment "TODO: correctly
rounded result. This rounds multiple times." (L483-L493; row K15).

### 3.19 Dict-literal lookups and tuple builtins

| # | Python, per row | Polars expression (`c` = `pl.col`) | Inputs | Python result | Polars result | = |
|---|---|---|---|---|---|---|
| W1 | `{'A': 1, 'B': 2}[row1.s]` | `c.s.replace_strict({'A': 1, 'B': 2})` | s: 'A'; 'B' | 1; 2 | 1; 2 [Int64] | same |
| W2 | `{'A': 1, 'B': 2}[row1.s]` | `c.s.replace_strict({'A': 1, 'B': 2})` | s: 'A'; 'Z' | 1; KeyError | query fails: InvalidOperationError | DIFF |
| W3 | `{'A': 1, 'B': 2}.get(row1.s, 0)` | `c.s.replace_strict({'A': 1, 'B': 2}, default=0)` | s: 'A'; 'Z'; None | 1; 0; 0 | 1; 0; 0 [Int64] | same |
| W4 | `{'A': 'x'}.get(row1.s, row1.s)` | `c.s.replace({'A': 'x'})` | s: 'A'; 'Z'; None | 'x'; 'Z'; None | 'x'; 'Z'; null [String] | same |
| W5 | `max(row1.a, row1.b, 0)` | `pl.max_horizontal(c.a, c.b, 0)` | (a, b): (1, 2); (-1, -2) | 2; 0 | 2; 0 [Int64] | same |
| W6 | `any((row1.a, row1.b))` | `pl.any_horizontal(c.a != 0, c.b != 0)` | (a, b): (1, 0); (0, 0) | True; False | True; False [Boolean] | same |
| W7 | `all((row1.a, row1.b))` | `pl.all_horizontal(c.a != 0, c.b != 0)` | (a, b): (1, 0); (1, None) | False; False | False; null [Boolean] | DIFF |
| W8 | `divmod(row1.a, 2)` | (none found) | (a, b): (7, 0) | (3, 1) | - | n/a |
| W9 | `[x * 2 for x in (row1.a, row1.b)]` | `pl.concat_list(c.a * 2, c.b * 2)` | (a, b): (1, 2) | [2, 4] | [2, 4] [List(Int64)] | same |

### 3.20 What Polars reports before any data arrives

For "an expression that cannot be translated is refused" it matters which bad
expressions Polars itself reports from the declared schema. Schema: s String,
i Int64, f Float64, p Boolean, d Decimal(38, 2). Columns: building the
expression; `LazyFrame(schema).select(expr).collect_schema()` (no rows);
collecting that frame with zero rows; collecting one row
(s='abc', i=1, f=1.5, p=True, d=null). obs:

| expression | build | collect_schema() (no data) | collect on 0 rows | collect on 1 row |
|---|---|---|---|---|
| `c.s + c.i` | ok | InvalidOperationError | InvalidOperationError | InvalidOperationError |
| `c.s == c.i` | ok | ok (Boolean) | ComputeError | ComputeError |
| `c.s < c.i` | ok | ok (Boolean) | ComputeError | ComputeError |
| `~c.s` | ok | InvalidOperationError | InvalidOperationError | InvalidOperationError |
| `pl.when(c.i).then(1).otherwise(0)` | ok | ok (Int32) | SchemaError | SchemaError |
| `c.s \| pl.lit('x')` | ok | ok (String) | InvalidOperationError | InvalidOperationError |
| `c.i.str.to_uppercase()` | ok | ok (Int64) | SchemaError | SchemaError |
| `c.s.dt.year()` | ok | ok (Int32) | InvalidOperationError | InvalidOperationError |
| `c.missing + 1` | ok | ColumnNotFoundError | ColumnNotFoundError | ColumnNotFoundError |
| `c.s.str.contains('foo(?=bar)')` | ok | ok (Boolean) | ComputeError | ComputeError |
| `c.s.str.replace_all('(a', 'b')` | ok | ok (String) | ComputeError | ComputeError |
| `c.s.cast(pl.Int64)` | ok | ok (Int64) | ok Int64 | InvalidOperationError |
| `c.s.cast(pl.Boolean)` | ok | ok (Boolean) | ok Boolean | InvalidOperationError |
| `c.s.str.to_date('%Y-%m-%d')` | ok | ok (Date) | ok Date | InvalidOperationError |
| `c.s.str.to_date('%Q')` | ok | ok (Date) | ok Date | InvalidOperationError |
| `c.d // c.d` | ok | ok (Decimal(precision=38, scale=2)) | InvalidOperationError | InvalidOperationError |
| `c.i ** -1` | ok | ok (Int64) | InvalidOperationError | InvalidOperationError |
| `c.i.round(-1)` | OverflowError | - | - | - |
| `pl.when(c.p).then(c.i).otherwise(pl.lit('x'))` | ok | ok (String) | ok String | ok String |
| `c.i.is_in(['a'])` | ok | InvalidOperationError | InvalidOperationError | InvalidOperationError |
| `pl.lit('x').cast(pl.Int64)` | ok | InvalidOperationError | InvalidOperationError | InvalidOperationError |

Reading (obs). `collect_schema()` catches unknown columns, arithmetic between
String and Int, `~` on a String, a list of the wrong type in `is_in`, and a
bad cast of a constant. A zero-row collect additionally catches String
compared with Int, a non-boolean `when` condition, `|` on Strings, the `str`
or `dt` namespace on the wrong type, regex syntax errors, Decimal `//` and a
negative integer exponent. Only data reveals strict-cast and strptime
failures, an invalid strptime directive (`'%Q'`), and String to Boolean cast
("casting from Utf8View to Boolean not supported"). Branches of different
types are never reported (last-but-two row).

### 3.21 The v1 baseline is not plain Python

Section 3 compares against plain Python values, as the ticket asks. What v1
PyMap gives users today is different, because v1 builds each row from a pandas
frame. Output and variable expressions read `joined_df.iloc[row_idx]` and then
`row[col]` (`src/v1/engine/components/transform/py_map.py` L930, L1046, L1062,
and `iterrows()` at L865); filter expressions read `row.to_dict()` (L547).
Reproducing those two extractions without the engine
(observed on pandas 3.0.5, numpy 2.5.2, Python 3.14):

```text
-- output/variable expressions: values come from joined_df.iloc[row][col]
frame: mixed (int, float, str, datetime, Decimal, bool); dtypes = {'i': 'int64', 'f': 'float64', 's': 'str', 'd': 'datetime64[us]', 'dec': 'object', 'b': 'bool'}
  row 0: i=numpy.int64(np.int64(1)); f=numpy.float64(np.float64(1.5)); s=builtins.str('a'); d=pandas.Timestamp(Timestamp('2024-03-10 00:00:00')); dec=decimal.Decimal(Decimal('1.10')); b=numpy.bool(np.True_)
  row 1: i=numpy.int64(np.int64(2)); f=numpy.float64(np.float64(nan)); s=builtins.float(nan); d=pandas.api.typing.NaTType(NaT); dec=builtins.NoneType(None); b=numpy.bool(np.False_)
frame: all numeric (int, float); dtypes = {'i': 'int64', 'f': 'float64'}
  row 0: i=numpy.float64(np.float64(1.0)); f=numpy.float64(np.float64(1.5))
  row 1: i=numpy.float64(np.float64(2.0)); f=numpy.float64(np.float64(nan))
frame: all int; dtypes = {'i': 'int64', 'j': 'int64'}
  row 0: i=numpy.int64(np.int64(1)); j=numpy.int64(np.int64(3))
  row 1: i=numpy.int64(np.int64(2)); j=numpy.int64(np.int64(4))
consequences for expressions (values taken from the frames above):
  mixed row 1: f is None -> False
  mixed row 1: s is None -> False
  mixed row 1: pd.isna(f) -> True
  mixed row 1: f == f -> np.False_
  mixed row 1: f + 1 -> np.float64(nan)
  mixed row 1: bool(f) -> True
  mixed row 1: f or 0 -> np.float64(nan)
  mixed row 1: d is None -> False
  mixed row 1: s or 'N/A' -> nan
  all-numeric row 0: i (type) -> 'numpy.float64(np.float64(1.0))'
  all-numeric row 0: i / 0 -> np.float64(inf)
  all-numeric row 0: i // 0 -> np.float64(inf)
  all-int row 0: i / 0 -> np.float64(inf)
  all-int row 0: i // 0 -> np.int64(0)
  all-int row 0: i % 0 -> np.int64(0)
  all-int row 0: (2**62 as np.int64) * 4 -> np.int64(0)
  all-int row 0: round(i / 2) (type) -> 'builtins.int(0)'
  all-int row 0: str(i / 2) -> '0.5'
  all-int row 0: i == 1 (type) -> 'numpy.bool(np.True_)'

-- filter expressions: values come from row.to_dict()
frame: mixed
  i=builtins.int(1); f=builtins.float(1.5); s=builtins.str('a'); b=builtins.bool(True)
  i=builtins.int(2); f=builtins.float(nan); s=builtins.float(nan); b=builtins.bool(False)
frame: all numeric
  i=builtins.float(1.0); f=builtins.float(1.5)
  i=builtins.float(2.0); f=builtins.float(nan)
frame: all int
  i=builtins.int(1); j=builtins.int(3)
  i=builtins.int(2); j=builtins.int(4)
```

Reading (obs).
- In output and variable expressions the operands are numpy and pandas
  scalars (`np.int64`, `np.float64`, `np.bool`, `pd.Timestamp`), and in a
  frame whose columns are all numeric an integer arrives as `np.float64`.
- A missing value is `nan` for numbers and for strings, `NaT` for datetimes,
  and None only in an object column. So in v1 `row1.x is None` is False for a
  missing value, `row1.s or 'N/A'` is `nan`, and `bool(missing)` is True.
- numpy arithmetic applies: `x / 0` is `inf`, `np.int64(1) // 0` is 0,
  integer overflow wraps; none of these raise.
- In filter expressions the same values are plain `int` / `float` / `str`
  (but still `nan` when missing), so one PyMap evaluates the same text under
  two value models.
- When an expression does raise, v1 returns None for that cell if
  `die_on_error` is false (`_eval_expr`, L506-L517) and treats a raising
  filter as False (L554-L558, L945-L948).

---

## 4. Constructs with no native Polars equivalent

"None found" means: not in the 1.44.2 expression API (`Expr`, `Expr.str` with
49 methods, `Expr.dt` with 47, the `pl.*` functions) and not reproduced by a
composition in section 3. Items a composition does reproduce are in section 2,
not here.

Syntax:
- Statements of any kind (assignment, loops, `import`, `try`): outside
  expression syntax; `ast.parse(mode="eval")` rejects them (obs).
- Comprehensions and generator expressions over row values, `lambda`, the
  walrus operator, `await`/`yield`, starred arguments, t-strings. (A
  comprehension over a fixed tuple of columns can be unrolled; W9.)
- Calls on anything that is not a recognised name: arbitrary attribute and
  method access.

Python semantics:
- "This row raises": per-row `TypeError`, `ValueError`, `ZeroDivisionError`,
  `IndexError`, `KeyError`, `AttributeError`. Polars gives null or a
  whole-query failure (3.1, 3.4, 3.9).
- A value whose type varies by row (`x if c else 'N/A'` with numeric `x`): a
  column has one type; Polars casts silently (X11, X12).
- Integers beyond 128 bits and exact integer results beyond Int64 without an
  explicit wider type (3.11); complex results (O10).
- A conditional expression or `and`/`or` whose not-taken side would fail,
  on polars 1.38-1.43, and for the cases masking does not cover on 1.44.x
  (3.9).
- `datetime.now()` evaluated per row; `timestamp()` / `fromtimestamp()` on
  naive values, which depend on the machine's time zone (2.9).

Builtins from v1's allow-list (`_code_component_mixin.py`
`_SAFE_BUILTIN_NAMES`): `print`, `repr`, `type`, `isinstance` (the type is
fixed per column, so only its use as a missing-value test has a counterpart),
`dict`, `set`, `frozenset`, `tuple`, `list`, `map`, `filter`, `zip`,
`enumerate`, `range`, `sorted`, three-argument `pow`; `divmod` (W8).

Strings:
- Methods with no counterpart found: `casefold`, `center`, `encode`,
  `expandtabs`, `format_map`, `isascii`, `isidentifier`, `isprintable`,
  `istitle`, `maketrans`, `translate`, `partition`, `rpartition`, `rfind`,
  `rindex`, `splitlines`, `swapcase`; `split` / `rsplit` with `maxsplit` as a
  list (`str.splitn` returns a fixed-width Struct, obs).
- Methods with only an approximation: `isdigit`, `isnumeric`, `isspace` (128,
  91 and 4 code points differ), `isupper`, `islower` (no form found) (3.13);
  `find` / `index` as character positions (S15); `title` for 169 non-ASCII
  code points (3.13); `strip` for U+001C to U+001F (S5); `zfill` on non-ASCII
  text (U12).
- Slices with a step other than -1 (U25); `s[i]` raising when out of range.
- Format specs beyond zero-fill and width: `.2f` exactly (U29, U30), `,`
  grouping (U33), `!r` / `!a`, `%`-style specs other than `%s`.
- A per-row search or replace pattern taken from a column for `replace`
  (2.6).

`re`:
- Lookahead, lookbehind, backreferences, atomic groups, conditional groups,
  `\Z`, `{,n}`, `\N{...}` (P20-P24 and obs).
- A function as the replacement (P31); Match objects other than
  `.group(n)` of a search; `findall` / `split` with capture groups (P26, P30).
- Exact `$`, `\w`, `\s` behaviour on the characters where the dialects differ
  (P17-P19).

`math` (no `Expr` method, checked by name against `dir(math)`): `comb`,
`copysign`, `dist`, `erf`, `erfc`, `exp2`, `expm1`, `factorial`, `fma`,
`fmod`, `frexp`, `fsum`, `gamma`, `gcd`, `hypot`, `isclose`, `isqrt`, `lcm`,
`ldexp`, `lgamma`, `modf`, `nextafter`, `perm`, `prod`, `remainder`, `sumprod`,
`ulp`. Some can be composed but not exactly: `copysign` loses the sign of zero
(H13), `hypot` overflows (H14). Raising on a domain error is not available for
any `math` function (3.16).

`datetime`:
- `isoformat()` and `str()` exactly, because their shape depends on the value
  (DT11, DT12).
- `strftime` / `strptime` directives where chrono differs or fails: `%f`
  without rewriting, `%y` pivot, `%Z` / `%z` on naive values, `%s`,
  locale-dependent output (3.17, obs).
- `ctime`, `toordinal`, `fromordinal`, `fromisocalendar`, `timetuple` apart
  from its day of year (`dt.ordinal_day()`, obs), and `astimezone` /
  `utcoffset` / `tzname` / `dst` (time zones were not probed).

`Decimal`:
- `//`, `%`, `**` (K6-K8); exact multiplication and division scale (K2-K4,
  K12); precision beyond 38 digits; `Decimal('NaN')`, `Decimal('sNaN')` and
  `Decimal('Infinity')` (each panics as a literal, obs).
- Context operations and most methods of `decimal.Decimal` (56 public
  names): `quantize` with rounding modes other than half-even, half-up and
  down, `normalize`, `as_tuple`, `sqrt` / `ln` / `exp` as Decimal (K20),
  `to_eng_string`, `fma`, and the rest.
- Raising on Decimal with float (K9).

Namespace members of v1 PyMap with no general counterpart: `pd.*` and `np.*`
calls (a `pd.isna` test maps to `is_null()`, plus `is_nan()` for floats: Q9,
Q10), `json.loads` without a declared result type (`str.json_decode` has
required a `dtype` since 1.33.0, per its docstring),
`json.dumps` of arbitrary values, `globalMap` / `context` values that change
during the run (2.1).

---

## How the observations were produced

- Interpreter: the repo venv, `.venv/bin/python` (CPython 3.14.6, polars
  1.44.2 with polars-runtime-32 1.44.2, pandas 3.0.5, numpy 2.5.2). Nothing
  was installed or changed. Local time zone UTC+05:30.
- Section 3 tables: one script holding the 328 pairs of expression texts and
  inputs exactly as printed in the tables. The Python side is
  `eval(compile(text, "<py>", "eval"), {"row1": Row(values), "re": re,
  "math": math, "datetime": datetime, "Decimal": Decimal, "json": json,
  "pd": pd})` per row (plus `ROUND_HALF_UP`, `ROUND_HALF_EVEN`, `ROUND_DOWN`
  from `decimal`), where `Row` is a `dict` subclass with `__getattr__`; the Polars side is
  `eval(text, {"pl": pl, "c": pl.col, "Decimal": Decimal, "datetime":
  datetime, "math": math})` once, then
  `pl.DataFrame(rows, schema=schema, orient="row").lazy().select(expr.alias("out")).collect(engine=...)`.
  Values are printed with `ascii()`, so non-ASCII inputs appear as escapes
  (`'\xe9'` is U+00E9). The script was run once per engine and the two outputs
  were identical.
- An earlier, wider sweep of 540 pairs (the same harness) agreed between the
  two engines on all but six rows: five differed only in the count inside an
  error message, and one was the per-row `str.replace` pattern, which failed
  on the in-memory engine and passed on the streaming engine with two input
  rows.
- Tables in 1.1 and 3.20, the per-code-point table in 3.13 and the listing in
  3.21 come from separate short scripts that print exactly what is shown.
- Source facts were read from files fetched at the stated tags; PyPI facts
  from `https://pypi.org/pypi/<name>/json`; repository facts from the GitHub
  REST API and raw files, all on 2026-10-05.
- The scripts were kept under the system temp directory and are not part of
  this commit; every table row is sufficient to re-run its case.

---

## Could not establish

- That no other translator exists. The survey covered Polars itself, the
  projects the ticket names, and what searches of PyPI and GitHub turned up;
  an unlisted or private project cannot be ruled out.
- Behaviour on polars 1.38-1.43 by execution. Only 1.44.2 is installed and
  nothing may be installed. The `when/then` difference (3.9) and the
  `round` default were read from source at the tags; every table in section 3
  is 1.44.2 only.
- Whether the 1.44.0 masking of `when/then` branches is something Polars
  intends to keep. It shipped as a performance improvement, the docstring
  still says each branch must be valid on its own, and issue #17601 is open.
- What Polars 2.0 changes. 2.0.0rc2 exists; its docs tree
  (docs.pola.rs/api/python/version/2/) and migration guide were not read.
- Which constructs real v1 PyMap expressions use. The 37 fixture jobs contain
  no PyMap (as-found research), and ticket 01 counts real jobs. Sections 2
  and 4 follow the ticket's list and v1's namespace, not usage.
- Why `Expr.round(mode='to_zero')` is documented at 1.44.2 but rejected.
- A complete list of expression functions that can fail on data. Polars'
  own list has four families; four more were hit here (3.9).
- Context-dependent case mapping beyond the samples (only final sigma was
  tried), and how the per-code-point agreement of 3.13 changes with the
  Unicode tables of Python 3.12 and 3.13 (the sweep ran on 3.14's Unicode
  16.0.0). Why Polars maps the 28 code points Python leaves alone was not
  traced.
- Whether `math` functions other than `log10` differ in the last digit.
- Truthiness forms for Date, Datetime, Duration and List columns, and
  everything about time-zone-aware datetimes: not probed.
- Whether Polars has any way to bind a value into an expression after it is
  built (for context values that change during a run). None was found among
  the 3,285 entries of the API reference inventory; absence there is not
  proof.
- The licence that governs polars-expr-transformer: its LICENSE file is
  Apache-2.0, its README badge says MIT, its PyPI metadata declares none.
- Behaviour on the target servers. Everything observed is from one arm64 Mac.
