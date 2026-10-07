# Writing a v2 component

A v2 component is one Python file that declares its config keys and builds a
lazy Polars plan. This page is the contract. Read `src/v2/CONTEXT.md` first
for the words used here (config key, alias, refusal report, answer key).

## The rules

1. **Lazy.** A component turns `pl.LazyFrame`s into `pl.LazyFrame`s. It
   never calls `collect`, `fetch`, `sink_*` (except a sink's `lazy=True`
   plan) or anything else that runs the data. The engine runs a whole subjob
   in one pass.
2. **Native Polars only.** No `map_elements`, `map_batches`, `apply`, no
   Python loop over rows. If Polars cannot express a config key natively,
   declare the key **refused** with the reason. The only components that run
   user Python are the Python components.
3. **v1 is the answer key.** For the same job config and input files, the
   output files must equal v1's byte for byte. Read the v1 component
   (`src/v1/engine/components/...`) before writing a line, and remember that
   v1's base class also acts on every component's output (see "What the
   engine does for you").
4. **Keep row order.** v1 keeps input order through every component. Pass
   `maintain_order=True` (or the join's `maintain_order="left"`) wherever
   Polars would otherwise be free to reorder.
5. **A bad row is data, not an exception.** Never let Polars raise on a row
   (`strict=False`, flag columns). A row that cannot be processed goes to the
   `reject` output when `die_on_error` is false; when it is true, count the
   bad rows with `self.check(...)` and fail with v1's message.
6. **Never call `.cache()`.** Polars finds frames that several outputs
   share by itself. An explicit `.cache()` looks like the way to make sure a
   file is read once, and on Polars 1.44 it writes wrong columns: a `select`
   or `drop` that sits between a cached frame and a frame with two readers
   is lost (reproduction in
   `.scratch/engine-v2/research/probes/probe_polars_cache_loses_projection.py`).
7. **Nothing undeclared.** Every config key the converter emits for the
   component, and every key v1's engine component reads, is declared:
   supported, ignored, or refused. An undeclared key refuses the job.
8. **ASCII only** in log messages and source. Log with
   `logger.info(f"[{self.id}] ...")`.
9. **A failure names its row.** Every row carries, unseen, the number it
   had in its source. A component must not lose it without saying so, and
   must not let it show. What that asks of each kind of component is in
   "Row numbers" below.

## Skeleton

```python
"""Sort row: order rows by one or more columns."""
from __future__ import annotations

from typing import Dict

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ..base import Transform
from ..registry import REGISTRY


@REGISTRY.register
class SortRow(Transform):
    """One sentence saying what it does."""

    names = ("sort_row", "SortRow", "tSortRow")       # v2's name first, then v1's
    keys = (
        Key("criteria", type=list, required=True, items=_CRITERION, doc="..."),
        Key("external", kind=Kind.IGNORED, type=object, doc="Talend's sort-on-disk switch."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        ...
        return {"main": frame.sort(...)}
```

Put the file in `src/v2/components/<category>/<name>.py` (`file`,
`transform`, `aggregate`, `context`). It is imported automatically; the
decorator registers it. Working examples: `transform/sort_row.py`,
`transform/filter_rows.py`, `file/file_input_delimited.py`,
`file/file_output_delimited.py`.

## The four kinds (`src/v2/components/base.py`)

| Kind | You write | Gets | Returns |
|---|---|---|---|
| `Source` | `read()` | nothing | `{port: LazyFrame}` |
| `Transform` | `build(inputs)` | `{flow name: LazyFrame}` in job-config flow order | `{port: LazyFrame}` |
| `Sink` | `write(frame)` | its one input | a `Write` |
| `Eager` | `run(inputs)` | `{flow name: DataFrame}` (real rows) | `{port: DataFrame}` |

- Inputs arrive in the order of the component's own `inputs` list in the job
  config (v1's rule: a join's first input is its main flow), and in
  job-config flow order where the list does not say.
- `Eager` is for components that truly need rows in hand (user Python, a
  tiny lookup that sets context). The engine collects its inputs, which
  holds them in memory. A `Transform` can decide per run: override
  `needs_rows()` and implement both `build` and `run`.
- Class attributes: `names`, `keys`, `outputs`, `min_inputs`, `max_inputs`
  (`None` = any number), `conforms`.
- `outputs` maps each output port to the v1 flow types that leave by it.
  Default `{"main": ("flow", "main")}`. A filter declares
  `{"main": ("flow", "main", "filter"), "reject": ("reject",)}`; v1's other
  flow types are `unique` and `duplicate`. Return a frame for every port you
  declare, even when it is empty (`frame.clear()`): v1 stalls a job whose
  wired reject flow got nothing, v2 writes the empty file.
- Named outputs (Map): override the classmethod
  `port_for(flow_type, flow_name, config)` to return the port a flow leaves
  by, and return frames under those port names.
- Inside a component: `self.id`, `self.config` (v2 names, defaults filled,
  context resolved), `self.schema` (declared output columns, a list of
  `Column`), `self.input_schema`, `self.spec.reject_schema`,
  `self.spec.input_schemas` (per incoming flow name), `self.context`,
  `self.global_map`, `self.run_context`.

## Checked at load

A job is checked before it runs: every subjob is built against empty frames
(`src/v2/engine/check.py`). `build` is called for real, so it must not touch
files or data. For the other kinds the engine does not call `read`, `write`
or `run`; it uses `declared_outputs()` (empty frames made from the declared
schema) instead. Two hooks let a component take part:

- `problems()` returns what is wrong with the config that the key
  declarations cannot say: keys that do not go together, a schema that is
  needed. Each entry reads `"<key>: <what is wrong>"`. It is called at load
  and again before the component runs, so `read`/`build`/`write` may assume
  it returned nothing.
- A component that sets context variables while the job runs declares
  `sets_context = True` on its class, so that a config naming a variable
  that does not exist yet is not refused at load.

## Config keys (`src/v2/job/keys.py`)

```python
Key("path", required=True, aliases=("filepath",), doc="The file to read.")
Key("header_rows", type=int, default=0, doc="Lines to skip at the top.")
Key("order", default="asc", choices=("asc", "desc"), doc="...")
Key("condition", type=EXPRESSION, default="", aliases=("advanced_cond",), doc="...")
Key("criteria", type=list, required=True, items=(Key("column", required=True), ...), doc="...")
Key("external", kind=Kind.IGNORED, type=object, doc="why it does not matter")
Key("uncompress", kind=Kind.REFUSED, type=bool, reason="compressed files are not read by v2", doc="...")
```

- **Naming.** There is no blanket rule. The v2 name is the documented one;
  every v1 spelling is an alias. Keep v1's name as the v2 name unless a
  clearer one is obviously better (`path` for `filepath`); when in doubt,
  keep v1's. A job config giving both spellings is refused automatically.
- **Supported** keys must behave as in v1, defaults included. Take the
  default from v1's engine component (what it does when the key is absent),
  not from the converter.
- **Ignored** means: accepted, no effect, and the result still equals v1's.
  Use it for keys v1 itself ignores and for Talend tuning knobs.
- **Refused** means: v2 will not run a job that uses it. Give the `reason`.
  A refused key is still accepted when its value means "off" (false, empty,
  zero, null, or anything listed in `off=`).
- `type`: `str`, `int`, `float`, `bool`, `list`, `dict`, `object` (anything),
  `EXPRESSION` (a Python expression) or `CODE` (a block of Python). Booleans
  and integers written as text (`"true"`, `"5"`) are accepted. `convert=`
  post-processes a value and refuses it by raising `ValueError`. It is not
  applied to `default`: write the default as the value the component sees.
- `label`, `tstatcatcher_stats`, `execution_mode`, `chunk_size` are accepted
  on every component already.
- Context references (`${context.x}`, `context.x`) in `str`/`int`/`bool`
  values are resolved before you see them. `EXPRESSION` and `CODE` values
  are never touched: the expression reads `context.x` itself.
- Java (`{{java}}...`) is refused by the loader before the component sees
  it. Nothing to do.

## Expressions (`src/v2/expressions`)

Expressions in a job config are Python, translated once to a Polars
expression:

```python
from ...expressions import translate

scope = self.row_scope(frame.collect_schema(), flow_name, "input_row")
keep = translate(self.config["condition"], scope)        # a pl.Expr
```

`row_scope(types, *names)` lets the expression write a column bare (`price`)
or after a row name (`row1.price`, `row1['price']`), and read `context.x`,
`globalMap.get("k")` and routines. For several rows at once (a main row and
joined lookups) build a `Scope` yourself: see `Scope.for_rows` in
`expressions/translate.py`. Translation errors are `ExpressionError`s with
the offending text; let them propagate.

What the language covers is listed in `expressions/functions.py`. If a v1
job needs a function that is missing, do not add it yourself: report it.

A conversion written in an expression (`int()`, `float()`, `strptime()`)
does not raise. It gives nothing where it fails, and the translation notes
those rows in the scope (`scope.failures`), counting only the rows Python
would work the conversion out for. After translating, hand the frame the
expressions run on to `self.check_conversions(frame, scope)`: it fails the
component with the expression, the value, how many rows failed and the
first one's place. The engine fails the job when a component translated a
conversion and did not check it, so one cannot go missing silently. A new
function that can fail on a row is built the same way, with
`tr.fallible(what, value, made)` (`_int` in `expressions/functions.py`).

## Types (`src/v2/types.py`)

Declared column types are `str`, `int`, `float`, `bool`, `datetime`, `date`,
`Decimal`. Helpers:

- `polars_type(column)`, `polars_schema(columns)`
- `from_text(text_expr, column) -> (value_expr, unreadable_expr)`: text to a
  typed value with v1's rules; use it in anything that reads text.
- `to_text(expr, dtype, declared_column_or_None)`: a value as v1's file
  outputs write it; use it in anything that writes or prints.
- `chrono_format(pattern, parsing=...)`: a job config's `date_pattern`
  (Python strftime) as the pattern Polars wants.

Missing values: a `str` read from a file is never missing (an empty field is
empty text); every other type reads an empty field as missing. Missing
values are written as empty fields.

## What the engine does for you

After `read`/`build`/`run`, for the `main` output, the engine applies v1's
base-class behaviour (`types.conform`), unless the class sets
`conforms = False`:

- declared columns first, in declared order; other columns kept after them;
- a declared column you did not produce is added (missing, or zero-like when
  not nullable);
- values of another kind are turned into the declared type (`str` is left
  alone, whole numbers declared `float` stay whole, text is parsed);
- `precision` rounds floats (half to even) and Decimals (half up);
- a missing value in a `nullable: false` column fails the component when
  `die_on_error` is true (the default the engine assumes when the component
  declares no such key) or sends the row to `reject` with `errorCode`
  `SCHEMA_VIOLATION` when it is false;
- columns named `errorCode` / `errorMessage` arriving on `main` are renamed
  `errorCode_user` / `errorMessage_user` (always, whatever `conforms` says).

So do not reorder or cast to the declared schema yourself. Do declare
`die_on_error` with v1's default for the component if v1 reads it.

Row counts: sinks set `<id>_NB_LINE`. `<id>_NB_LINE`, `_NB_LINE_OK` and
`_NB_LINE_REJECT` of other components are counted by the engine, when
something in the job reads them or when the run asks for the counts of
every component. Do not count rows yourself. Where v1's component counts
other rows than the default (every input for `NB_LINE`, the main output for
`_OK`, the reject output for `_REJECT`), say which frames add up to each
count in `line_counts`; `tests/v2/test_row_counts_against_v1.py` is where
the counts are held against v1's.

The engine does not count with `select(pl.len())`, and neither should
anything else that counts a frame it did not build: on Polars 1.44 that
gives a wrong number for frames put one after another and then cut
(`concat` under `slice` or `head`; reproduction in
`.scratch/engine-v2/research/probes/probe_polars_count_of_a_cut_union.py`).

## Row numbers: where a row came from (`src/v2/rows.py`)

Every source numbers its rows as it reads them, from 1. The number travels
with the row as a hidden column, with copies of the columns the source's
schema marks as key. When the engine finds a row it cannot go on with, the
failure's message ends with the row's place:
`; the row is line 4 of in.csv (id=3)`.

How a user asks for a key: `"key": true` on a column of the source's
schema, which is what Talend's key flag converts to. Nothing else is
configured, and a new component declares no config key for any of this.

The names: hidden columns start with `__v2_`, and no column of a job may.
`__v2_row:<source id>` is the number, `__v2_key:<source id>:<column>` the
copy of a key column, `__v2_rows:<source id>` how many rows of the source
were combined into this one.

What the engine does for every component: it drops the hidden columns
before a sink is handed its frame, leaves them out of the scope an
expression is translated in (`row_scope`), and out of debug lines. No file
ever holds one; every test that compares v2's files with v1's would fail if
one did.

What a component owes, by what it does with rows:

| The component | What it does about the hidden columns |
|---|---|
| reads a source | numbers its records and says where a number is (next list) |
| keeps its rows and hands on every column (a filter, a sort) | nothing: they pass |
| picks the columns it hands on (`select`) | picks `rows.hidden(names)` as well |
| makes several rows of one (normalize, unpivot) | nothing where it explodes a column, since the other columns repeat; otherwise every row made carries the hidden columns of the row it came from |
| makes one row of several (an aggregate, a pivot, a denormalize) | keeps, for each source, the lowest row number, that row's key copies, and how many rows went in: `_carried` in `aggregate_row.py` |
| joins a lookup to a main input | hands on the main input's; drops the lookup's (`rows.without`) |
| reads columns by their place, or treats every column alike (prints all, compares all) | leaves the hidden ones out (`rows.visible(names)`) |
| hands rows to code the engine cannot see into | sets `sees_hidden_columns = False`: the engine hands it frames without them, and what it hands on has lost them |

A source:

- numbers its records where it reads them, before it drops any (a blank
  line, a row a limit cuts), in the column `self.row_number`:
  `row_index_name=self.row_number, row_index_offset=1` on a Polars scan, or
  `with_row_index(self.row_number, offset=1)`. The number counts from the
  first record after what the reader's config skips at the top, so that
  `locate` can add the header rows back;
- hands on, with every output, that column and `self.key_copies()`, taken
  before a value is trimmed or typed: a key is shown as it stands in the
  source;
- implements `locate(number)`: the words a person looking for the record
  would use, ending in the path as the job gives it. `line 7 of in.csv`,
  `row 3 of sheet 'Q1' of book.xlsx`, `record 2 ($.orders[1]) of in.json`.
  Give the position the source's own tool shows (an editor's line, a
  sheet's row). Where that cannot be vouched for, as with a record that can
  span lines, give the record's number and call it a record.

A check that fails on rows names the first. Ask for the hidden columns of
the first failing row beside the count, and end the message with
`self.where(found)`:

```python
from ...rows import first_of

bad = frame.filter(flag)
self.check(
    bad.select(pl.len().alias("rows"), pl.col(name).first().alias("value"), *first_of(bad)),
    lambda found: f"... {found['value'].item()!r}{self.where(found)}" if found["rows"].item() else None,
)
```

## Asking about the data: `tap` and `check`

A component cannot look at rows while it builds. When it needs something
from the data, it asks, and the engine computes it in the same pass:

```python
self.tap(frame.head(100), self._print)            # a few rows, after the pass
self.check(
    frame.select(pl.col("__bad").sum()),
    lambda found: f"{found.item()} row(s) could not be read" if found.item() else None,
)
```

`check` fails the component (and no file of the subjob is put in place) when
its function returns a message. Keep tapped frames small: they are held in
memory. Values for `self.global_map` that depend on the data are set from a
tap.

## Sinks

`write(frame)` returns `Write(path, sink, append, ready, place, finish)`:
`sink(temp_path)` returns the lazy sink plan (`frame.sink_csv(temp_path,
..., lazy=True)`). The engine writes to a temporary file beside `path` and
counts the rows it hands you as they pass. When the whole subjob has
succeeded, it calls `ready(temp_path, rows)` for every file of the subjob,
and then `place(temp_path, rows)` for each, in the order the components
run.

Do in `ready` whatever the rows can still fail: putting the file in the
job's encoding, say. Do nothing in `place` but move bytes
(`files.put_in_place`). That is what lets a subjob that fails leave every
file as it was. See `file/file_output_delimited.py`.

## Tests

Tests come first (red, then green). Two kinds, both under
`tests/v2/components/test_<name>.py`:

**Answer-key tests** run the same job config on v1 and on v2 and compare the
files they write. They are the proof of parity; cover every supported key
and every supported value of it:

```python
from tests.v2.answer_key import assert_matches_v1

def job(config):
    return {
        "job_name": "sort", "default_context": "Default", "context": {"Default": {}},
        "components": [
            {"id": "in", "type": "FileInputDelimited",
             "config": {"filepath": "in.csv", "fieldseparator": ";", "header_rows": 1, "encoding": "UTF-8"},
             "schema": {"input": [], "output": COLUMNS}, "inputs": [], "outputs": ["row1"]},
            {"id": "sort", "type": "SortRow", "config": config,
             "schema": {"input": COLUMNS, "output": COLUMNS}, "inputs": ["row1"], "outputs": ["row2"]},
            {"id": "out", "type": "FileOutputDelimited",
             "config": {"filepath": "out.csv", "fieldseparator": ";", "include_header": True, "encoding": "UTF-8"},
             "schema": {"input": COLUMNS, "output": []}, "inputs": ["row2"], "outputs": []},
        ],
        "flows": [{"name": "row1", "from": "in", "to": "sort", "type": "flow"},
                  {"name": "row2", "from": "sort", "to": "out", "type": "flow"}],
        "triggers": [], "subjobs": {}, "java_config": {"enabled": False},
    }

def test_sorts_numbers_descending(tmp_path):
    assert_matches_v1(job({"criteria": [{"column": "n", "sort_type": "num", "order": "desc"}]}),
                      {"in.csv": b"n;s\n2;b\n10;a\n"}, tmp_path)
```

Write the job config in v1's shape with v1's key spellings: that is what
users have. Paths are relative; each engine runs in its own fresh folder.
Use data that exercises ties, missing values, mixed case, negative numbers
and empty input. Where v1's behaviour is a bug v2 should not copy (it
depends on what else is in the column, it crashes, it stalls), do not copy
it: test v2's behaviour directly and list the difference in your report.

**Unit tests** cover what an answer key cannot: refusals (a refused key, a
bad value), error messages, v2-only spellings. Build the job dict and call
`src.v2.run_job` / `src.v2.load_job`.

Run: `.venv/bin/python -m pytest tests/v2/components/test_<name>.py -o addopts="" -q -p no:cacheprovider`
and, before you finish, the whole of `tests/v2` the same way.

**Row-number tests** go in `tests/v2/test_row_numbers.py`, which has the
helpers (`chain`, `keyed`, `failed`). For a source: that a failure names the
right place on every way the reader reads (a header, blank records, each of
its read paths), and shows the key. For any other component: that a failure
after it still names the source row, or, for one that hands rows to foreign
code, that the row is no longer named.

Also add one test that the converter's own sample for the component loads:
take the component's `config` and `schema` from
`tests/talend_xml_samples/converted_jsons/Job_t<Name>_0.1.json` (when there
is one) and assert v2 accepts every key in it (Java expressions aside).

## Done means

- one file, declared keys with v1 aliases, docstrings;
- the row numbers kept, by the table in "Row numbers", and a test of it;
- answer-key tests for every supported key, unit tests for refusals;
- the whole `tests/v2` suite green;
- a short report: keys supported / ignored / refused (with reasons), every
  deliberate difference from v1, anything missing from the engine or the
  expression language that you needed.
