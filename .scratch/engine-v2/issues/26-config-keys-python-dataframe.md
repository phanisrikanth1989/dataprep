# 26 - Config keys and code contract: python dataframe

Status: open
Type: grilling
Blocked by: 05, 07

## Question

Walk every config key of v1's PythonDataFrameComponent and of v2's
`python_dataframe` as found, give each one of the five verdicts, and settle
what the user's code is handed. This is the one place slow Python is allowed,
so the contract matters more than the keys.

How to run it: bring a table of v1 key and default, v2 key and default as
found, what each does and a proposed verdict; the user confirms or changes it
row by row. Apply [The performance bar](05-performance-bar.md) and the
defaults policy from
[Config-key declaration, aliases and the refusal report](07-config-key-declaration-and-refusal-report.md).

v1 (`src/v1/engine/components/transform/python_dataframe_component.py`,
`agents/schemas/python_dataframe.json`): keys `python_code`,
`output_columns`, `execution_mode`. The code receives a pandas DataFrame
named `df` and changes it in place. Its namespace: `df`, `pd`, `np`,
`context` (a flat dict), `globalMap`, `routines`.

v2 as found: keys `code`, `imports`, `use_pandas`. The code receives a Polars
DataFrame named `df` (pandas when `use_pandas` is set) and must assign
`output_df`. Its namespace: `df`, `context`, `pl`, `np`; a `routines`
namespace is documented but never connected.

To settle:

- For a v1 job config to run unchanged, the code has to see what it saw in
  v1: a pandas frame changed in place. Is that the contract, with Polars as
  an opt-in, or the reverse?
- What the conversion to and from pandas costs at this barrier, and whether
  that is acceptable for the one component whose purpose is to run Python.
- The namespace: which names exist, and how context and globalMap appear.
- How errors in user code are reported.
