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
   "Expressions" below. One kind needs no rewriting: a value that is only
   a lookup and a join, such as the path of the file a loop is at. See
   "A value looked up while the job runs" below.
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

## A value looked up while the job runs

A config value may be a globalMap entry or a context variable, alone or
joined to text, as Talend writes it:

```
((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))
context.out_dir + "/" + ((String)globalMap.get("tFileList_1_CURRENT_FILE"))
```

- The terms: `globalMap.get("key")`, with or without a cast
  (`(String)`) and the brackets Talend puts round it; `context.name`;
  and text in double quotes. They are joined by `+`. Nothing else is
  read: a method call (`.substring(1)`), arithmetic or any other name
  is Java, and a job that holds one under the `{{java}}` mark is
  refused as before.
- One term alone is the value itself, with its type. Terms joined are
  text; an entry that holds nothing joins as nothing.
- The value is looked up when its component is built, which is when its
  subjob starts, or its pass in a loop. So an entry an earlier subjob
  left (`<id>_CURRENT_FILEPATH` of an unarchive, `<id>_ARCHIVE_FILEPATH`
  of an archive, `<id>_NB_LINE`) is seen, and one the same subjob sets
  is not there yet.
- Under the converter's `{{java}}` mark every such value is read, and an
  entry or a variable that is not there fails the component and names
  it. Without the mark only a value that names a globalMap entry is
  read this way, so that nothing that loaded before means something
  else now; and when its entry is not there the value is left as
  written.
- What is looked up is data, whatever it looks like: an entry of
  globalMap, and a context variable too, since a variable may hold what
  a file or another job handed over. A fixed flow input hands it on as
  it is (`00123` stays `00123`; only what is written in the job config
  itself is read as a number there), and a row generator takes it for
  the value and never for an expression: the name of a file is no
  Python, and is not run.
- This is for plain config values (a path, a name). An expression (a
  filter's condition, a map's column) is Python and reads
  `globalMap.get("key")` and `context.name` itself.

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
