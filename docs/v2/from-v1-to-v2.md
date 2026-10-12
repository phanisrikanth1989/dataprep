# Taking a v1 job config to v2

1. Run `python -m src.v2 job.json --check`. The refusal report lists
   everything that stops the job, component by component. A component with
   a fault does not hide the faults of what it feeds: the check goes on
   down the flow with the columns the component declares, and a fault found
   that way says so. Three things are still left for a second look: what
   follows a faulty component that declares no columns (a map, for one, or
   a reader with no schema), what follows a component whose config values
   cannot be read at all, and what follows a component that waits for a
   value the job sets while it runs (a context variable a context load
   sets, a row count).
2. Rewrite every Java expression (`{{java}}...`) in Python. See
   "Expressions" below.
3. Replace or remove components v2 does not have: the ones it has are
   listed in [the README](README.md#the-components).
4. Deal with refused config keys: each refusal says why.

Everything else stays as it is. The job config keeps v1's shape and v1's
key spellings. Where v2 documents a clearer name (`path` for `filepath`),
v1's spelling is an alias and keeps working; a job config that gives both
spellings of one key is refused. Keys that only made sense to Talend or to
v1's engine (`subjobs`, `java_config`, `position`, tuning knobs) are
accepted and ignored.


## Expressions

Expressions are Python. Each one is translated once, when the job loads,
into a Polars expression that runs on whole columns. Nothing runs row by
row, and Python that has no Polars form is refused at load with the reason.

```python
row1.name[:10].strip().upper()
row1.amount * (1 + context.vat) if row1.country == "FR" else row1.amount
re.sub(r"\s+", "_", row1.label)
Var.total > globalMap.get("limit", 0)
```

- A column is `row1.price` or `row1['price']`; where a component has one
  input the column may also be written bare (`price`). Map variables are
  `Var.name`, context values `context.name`, globalMap entries
  `globalMap.get("name")`.
- Operators, `a if c else b`, `and` / `or` / `not`, `in`, `is None`,
  slicing, the usual string methods, `len`, `str`, `int`, `float`, `round`,
  `abs`, `min`, `max`, and parts of `re`, `math`, `datetime` and `Decimal`.
  The full list is in `src/v2/expressions/functions.py`.
- A missing value does not raise: arithmetic, text operations and ordering
  comparisons on a missing value give a missing value. `==` and `!=` treat a
  missing value as a value (`x == None` is true for a missing `x`), and
  conditions follow Python's truthiness.
- RunIf trigger conditions are read exactly as v1 reads them (Python, with
  `&&`, `||`, `!`, `null`, `true`, `false` and
  `((Integer)globalMap.get("key"))` casts rewritten first), so the
  conditions v1 job configs carry keep working.

### Routines

A job config's `python_config` (`enabled`, `routines_dir`, `routines`) names
a folder of Python files, loaded and named as v1 does: `fee_rules.py` is
`FeeRules`, called as `routines.FeeRules.net(row1.amount)` or
`FeeRules.net(row1.amount)`. In v2 a routine takes Polars expressions and
returns one, so it works on whole columns:

```python
import polars as pl

def net(amount, rate=0.2):
    return amount * (1 - rate)

def initials(name):
    return name.str.slice(0, 1).str.to_uppercase()
```

A routine that calls Python row by row (`map_elements`) is refused. A v1
routine written with plain operators often works unchanged; one that uses
Python string methods or `if` on its arguments has to be rewritten with
Polars expressions.
