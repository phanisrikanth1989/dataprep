# Engine v2 -- Wayfinder Map

Label: wayfinder:map

## Destination

A rebuilt v2 engine, built and passing: pure Python, Polars-fast, and able to
run v1 job configs for a chosen set of 10-15 components. It accepts v1's config
keys, takes expressions written in Python, and produces output equal to v1's.
What it does not support it refuses at load, in one refusal report. Done
means the components are built and pass their answer-key tests, not that they
are designed.

## Notes

- This map carries execution: decision tickets first, then the build. The
  destination is a working engine, not a hand-off spec.
- Skills per ticket type. Decision tickets default to /grilling +
  /domain-modeling; engine terms land in `src/v2/CONTEXT.md` as they resolve
  (root `CONTEXT-MAP.md` lists the contexts). Build tickets (Type: task)
  follow the repo default: tests first (`superpowers:test-driven-development`)
  and evidence before claiming done
  (`superpowers:verification-before-completion`). Research tickets are
  resolved by a /research subagent, launched only on the user's explicit
  go-ahead and forbidden from spawning agents of its own.
- Starting evidence: [v2 engine as found](research/2026-10-05-v2-as-found.md)
  -- the rules v2 ran on, the component inventory, 26 verified findings (the
  tickets cite them by number) and the v1-versus-v2 vocabulary. Runnable
  reproductions are in `research/probes/`.
- Why this exists: v2 was designed to replace v1 outright. Six months on,
  people have adopted v1 and will not move wholesale, so v2 has to meet them:
  a user takes a v1 job config, removes the Java, rewrites the expressions in
  Python and runs it on v2.
- Rules that stay:
  - Performance first, capability second, but a config key users need is not
    dropped for being slower. Performance decides how a key is built: the
    fastest way Polars allows, paid for only by jobs that use the key.
    Whether a key stays is decided key by key in the component tickets, need
    against cost, and a refusal is made there with a reason
    ([The performance bar](issues/05-performance-bar.md)).
  - Lazy everywhere: components pass lazy frames and never collect; the engine
    collects only at barriers.
  - Explicit schema, never inferred.
  - No Python callbacks inside components; the python components are the one
    exception. The rule may be extended later if a real need appears.
  - Row errors go to a reject output when `die_on_error` is false.
  - Context doubles as globalMap.
  - Pure Python: nothing in Java anywhere in v2, no bridge.
- Rules replaced:
  - The custom expression language goes. Expressions are Python, translated
    once into Polars when the job loads and never run row by row. An
    expression that cannot be translated is refused; slow Python belongs in a
    python_row or python_dataframe component, where the cost is visible in
    the job.
  - Free-dict config goes. Each component declares its config keys as
    supported, ignored or refused. A refused or undeclared key stops the job
    at load, and the refusal report lists every problem in the job config in
    one pass.
- Compatibility with v1:
  - v1's job config is the reference. Talend is not.
  - No blanket naming rule. Every config key gets one of five verdicts in a
    key-by-key ticket: same in both; v2's name kept with v1's spelling as an
    alias; v2 adopts v1's name; the loader translates v1's form; refused or
    ignored. The purpose of each v2 rename is recovered before it is judged.
  - Aliases and translation happen once, at load. Components see one
    spelling. A job config that uses both spellings of one key is refused.
  - v1 is the answer key: for supported config keys, v2's output for a job
    equals v1's. Where matching v1 would cost speed, the component's ticket
    decides, need against cost. Deliberate differences, if any ever exist, go
    on a short written list.
- Build rules:
  - Rebuild clean inside `src/v2`, no second package: new loader, new core,
    new expression translator, then components one at a time. Each old module
    and its tests are deleted when the replacement lands. Polars logic worth
    keeping is reused. Nothing in production depends on today's v2.
  - `src/v1` is never modified. v2 adapts to v1, not the reverse.
  - A component is done when it has five things: its runtime (one file);
    its declared config keys with v1 aliases; answer-key tests (the same job
    run on v1 and v2, outputs diffed, with hand-written cases only for what
    v1 cannot express); a benchmark within 10% of hand-written Polars; and a
    doc page generated from the declared keys.
  - Tests first, and `src/v2` comes under the same 95% per-module coverage
    gate as v1.
- Component set: sixteen, fixed in
  [Pin the component list](issues/27-pin-the-component-list.md).
- How the open decisions were closed. On 2026-10-05 the dev stopped the
  question rounds and asked for the build: "make your own assumptions based
  on the answers I have given till now, and then go ahead and build the
  entire V2 ... when I test it out, then we can make changes". Every ticket
  resolved after [The performance bar](issues/05-performance-bar.md) is
  therefore an assumption recorded as built, not an answer the dev gave.
  Each says so, and each is open to change when the dev tests.
- Environment: run Python as `.venv/bin/python`. This Mac has polars 1.44.2
  and Python 3.14; the repo pins `polars>=1.44,<2.0` for v2 and Python 3.12+.
  Observations made here are provisional for the target servers until checked
  there. A JDK 17 and the bridge JAR are on this Mac since 2026-10-05
  (`PATH="/opt/homebrew/opt/openjdk@17/bin:$PATH"`), so v1 job configs with
  Java can serve as answer keys here.
- Polars trap found while building: never call `.cache()`. On 1.44.2 a
  `select`/`drop` between an explicitly cached frame and a frame with two
  readers is lost and a sink writes the dropped column
  (`research/probes/probe_polars_cache_loses_projection.py`).
- Data and servers, as the dev recalls them (2026-10-05, not measured): input
  files are typically 500 MB to 1 GB, the largest are 30 to 100 GB, and the
  servers have about 500 GB of memory.
- Logs are ASCII only (repo rule).

## Decisions so far

<!-- one line per closed ticket -->

- [Usage count of real v1 jobs](issues/01-usage-count-of-real-v1-jobs.md) --
  no counts (the script cannot run inside Citi); recorded instead the dev's
  intent and recollection: a 16-component set with no iterate and no
  database, the Java constructs users will hit, and Python routines allowed
  as Polars functions only.

- [03 - Polars facts: collection, streaming and Decimal](issues/03-polars-facts-collection-streaming-decimal.md)
  -- two collects re-run a shared upstream, and `collect_all` shares it only
  when the optimizer keeps the cache (main + reject as `filter(c)` /
  `filter(~c)` reads the source twice; a computed flag column reads it once);
  `write_csv` is `sink_csv` underneath, sinks return no row count, and a
  count can ride the sink's own pass on the streaming engine; `pl.Decimal` is
  stable but `*` and `/` round to the operands' scale (`1.25 * 1.25 = 1.56`),
  unlike Python's Decimal; errors surface at collect and name a column, not a
  component; a join keeps left order in memory but not on streaming;
  behaviour changes inside the pinned range, which graduated to
  [Which Polars versions v2 supports](issues/28-which-polars-versions-v2-supports.md).
- [04 - Translating Python expressions to Polars: prior art and mapping](issues/04-python-expressions-to-polars-prior-art.md)
  -- no existing tool does it, and evaluating the text once against `pl.col`
  objects fails or is silently wrong, so the translator walks the syntax tree
  and refuses what it does not know (as pandas `eval` does); a faithful
  mapping needs operand types at load; `//`, `%` and plain string methods
  agree with Python, while None, keyword logic on integers, division by
  zero, `round` with digits and regex dialect do not; `when/then` guards work
  only from polars 1.44.0; v1's PyMap is not plain Python (a missing value
  is `nan`), so "same as Python" and "same as v1" are different targets.
- [02 - Polars facts: reading and writing delimited files](issues/02-polars-facts-delimited-files.md)
  -- the lazy reader takes UTF-8 only, and reading ISO-8859-15 means an
  eager Python decode at about 5 times the time; separator and quote are one
  byte each and there is no escape character; an empty field is null for
  every type and `""` is an empty string only for String; no lazy footer
  skip; too few fields are padded silently and a lone quote gives a wrong
  row count; floats are written as `30200.0`; no thousands separators; zip
  is unsupported; row counts on CSV scans were wrong on polars 1.39 and
  1.40.
- [05 - The performance bar](issues/05-performance-bar.md) -- there is no
  blanket test: a config key is not dropped for being slower. Performance
  decides how a key is built (the fastest way Polars allows, paid for only by
  jobs that use it); whether a key stays is decided key by key in the
  component tickets, need against cost. Footer rows stays. The hard cases
  were measured: the figures are in the ticket and the scripts in
  `research/probes/`.

- [Job file shape, key by key](issues/06-job-file-shape-key-by-key.md) --
  v1's shape is read as it is; v2 names are extra spellings; converter
  metadata is ignored; a `{{java}}` string is refused where it stands.
- [Config-key declaration and the refusal report](issues/07-config-key-declaration-and-refusal-report.md)
  -- one `Key(...)` declaration per config key drives loading, aliases,
  defaults (v1's), refusals and the doc page; the job is also built against
  empty frames at load, and `--check` prints the report alone.
- [Flows and ports](issues/08-flows-and-ports.md) -- v1's `{name, from, to,
  type}` flows; a component declares which flow types leave by which output;
  inputs arrive in the order of the component's own `inputs` list, as in v1.
- [Barriers, collection and row counts](issues/09-barriers-collection-and-row-counts.md)
  -- one `collect_all` per subjob on the streaming engine; only components
  that need rows in hand are barriers; a file output always reports its rows,
  other counts are taken when something reads them.
- [Subjobs, triggers and what happens after a failure](issues/10-subjobs-triggers-and-failure.md)
  -- v1's subjob order and its five trigger types; a failed subjob fires its
  error triggers, the others still run, the job ends `failed` with exit 1.
- [Context and globalMap](issues/11-context-and-globalmap.md) -- values typed
  as v1 types them and resolved when each component is built; `${context.x}`
  and bare `context.x`; globalMap spelled `globalMap.get("k")`.
- [Errors and rejects](issues/12-errors-and-rejects.md) -- `die_on_error`
  per component with v1's default; rejected rows carry `errorCode` and
  `errorMessage`; every row leaves by exactly one output; a reject output
  always exists.
- [Types, nulls and schemas](issues/13-types-nulls-and-schemas.md) -- v1's
  type names plus `date`; Decimal is a real decimal; text from a file is
  never missing; one rule per type where v1's answer depends on the rest of
  the column.
- [Encoding: ISO-8859-15](issues/14-encoding-iso-8859-15.md) -- any encoding
  Python knows, read and written through UTF-8 only when the file holds more
  than ASCII.
- [Expression translator spike](issues/15-expression-translator-spike.md) --
  superseded: the translator was built, tests first.
- [Python expressions: what is allowed](issues/16-python-expressions-allowed.md)
  -- Python's meaning made total (a missing value propagates, never raises);
  the allowed functions are the tables in `src/v2/expressions/functions.py`.
- [Expressions outside Map](issues/17-expressions-outside-map.md) -- filter
  rows takes a Python expression; RunIf keeps v1's own dialect exactly;
  config values take context references only.
- [How a job is run on v2](issues/18-how-a-job-is-run-on-v2.md) --
  `python -m src.v2 job.json [--context_param K=V] [--check]`; exit 0, 1 or 2.
- [Answer-key harness](issues/19-answer-key-harness.md) -- built:
  `tests/v2/answer_key`.
- [Pin the component list](issues/27-pin-the-component-list.md) -- the
  sixteen the dev listed; no iterate, no database.
- [Which Polars versions v2 supports](issues/28-which-polars-versions-v2-supports.md)
  -- `polars>=1.44,<2.0`, tested on 1.44.2.
- [Routines as Polars functions](issues/29-routines-as-polars-functions.md)
  -- loaded and named as in v1 from `python_config`; a routine takes and
  returns Polars expressions; a row-by-row one is refused at load.

- [Config keys: delimited file input](issues/20-config-keys-delimited-file-input.md)
  -- every key the converter emits is declared; fields are read as text and
  typed by expressions, so a bad field is a rejected row; numbers go through
  Polars' own parser first, with the tolerant reader as fallback.
- [Config keys: delimited file output](issues/21-config-keys-delimited-file-output.md)
  -- v1's formatting per declared column and v1's rules for existing files,
  appending and empty outputs; `split` is refused.
- [Config keys: filter rows](issues/22-config-keys-filter-rows.md) -- v1's
  operators and functions; the advanced condition is a Python expression.
- [Config keys: sort row and unique row](issues/23-config-keys-sort-row-and-unique-row.md)
  -- as v1, with v1's row counts.
- [Config keys: aggregate row](issues/24-config-keys-aggregate-row.md) --
  v1's fifteen functions, exact sums and averages.
- [Config keys: map](issues/25-config-keys-map.md) -- one component for Map,
  tMap and PyMap; Python expressions; lookups reloaded per row are refused.
- [Config keys: python dataframe](issues/26-config-keys-python-dataframe.md)
  -- pandas by default as in v1, or a Polars lazy frame that keeps the
  component lazy.
- [Each part of a subjob's plan runs once](issues/31-each-part-of-a-plan-runs-once.md)
  -- parked: `cache()` with a guard behind it does it and was about 40% faster
  on the payments job, but it holds more memory and leans on one Polars
  version; not built.
- [Log to stdout, warnings and errors to stderr](issues/35-log-to-stdout-warnings-and-errors-to-stderr.md)
  -- INFO and DEBUG lines on stdout, warnings and errors on stderr; the JSON
  summary last on stdout, and in a file with `--summary FILE`.
- [Log a line when a trigger fires](issues/33-log-a-line-when-a-trigger-fires.md)
  -- one INFO line for every trigger that fires, and for a `RunIf` one each
  time it is judged, with its condition and what it came to.
- [A debug level for the log](issues/34-a-debug-level-for-the-log.md)
  -- DEBUG adds each component's config and output columns, how a delimited
  reader reads numbers and why, each subjob's plans, each output's temporary
  file and encoding; nothing of it is put together at INFO.
- [Row count of every component in the log](issues/32-row-count-of-every-component-in-the-log.md)
  -- on request (`--row-counts`): one line a component in v1's words, the
  counts v1's except where v1 counts a row its schema check then drops; the
  run takes about three times as long.
- [The check reports every fault of a flow at once](issues/36-the-check-reports-every-fault-of-a-flow-at-once.md)
  -- the check goes on past a faulty component with the columns it declares,
  and a fault found that way says so; nothing is guessed where no columns
  are declared.
- [How to point at the input row that failed a job](issues/37-how-to-point-at-the-input-row-that-failed-a-job.md)
  -- research: no tool names the input row of a failure in a later step, and
  Polars names none at all; a reader can name its own rows for nothing, and
  a failure Polars raises needs a second look at the data.
- [How v2 points at the input row that failed a job](issues/38-how-v2-points-at-the-input-row-that-failed-a-job.md)
  -- every source numbers its rows, the number travels hidden with the row
  and is named, with the key column's value, in the log line of a failure;
  conversions in expressions are checked by the engine so that the row is
  in hand.
- [Every source numbers its rows](issues/40-every-source-numbers-its-rows.md)
  -- built: the four readers number their rows, the number travels hidden
  and is never written, and three kinds of failure end with "the row is
  line 4 of in.csv (id=3)".
- [Conversions in expressions are checked by the engine](issues/41-conversions-in-expressions-are-checked-by-the-engine.md)
  -- built: `int()`, `float()` and `strptime()` no longer raise; the engine
  counts the rows they fail on, by Python's rules, and names the first.
- [A conversion guarded by `and` or `or` fails on v2 and not on v1](issues/39-a-conversion-guarded-by-and-or-or-fails-on-v2.md)
  -- corrected with ticket 41.
- [JSON file input](issues/42-json-file-input.md) -- built against v1; a
  failure names "record 2 ($.orders[1]) of in.json".
- [Normalize](issues/43-normalize.md) -- built against v1; every row it
  makes carries the number of the row it came from.
- [Review of the row numbers build](issues/45-review-of-the-row-numbers-build.md)
  -- a second reader found faults in tickets 40 to 43; each was reproduced
  as a failing test (on v1 too) and fixed, and what it taught is in ticket
  44 and the guide.
- [What a new component owes the row numbers](issues/44-what-a-new-component-owes-the-row-numbers.md)
  -- for any component added from now on: the rules are in
  `docs/v2/writing-a-component.md`, and the ticket is the list to hand a
  builder, by kind of component and by kind of source.

## Not yet specified

The destination is reached: the engine and its components (sixteen at
first, eighteen since 2026-10-07) are built
and pass their answer-key tests. What is left is for the dev to test and
decide, not fog on the way there.

- What the dev finds when testing real jobs. Every decision since
  [The performance bar](issues/05-performance-bar.md) was an assumption; the
  list of deliberate differences from v1 in `docs/v2/README.md` is the place
  to start disagreeing.
- Left unbuilt on purpose, each refused at load with its reason: `split` on
  delimited output; row separators other than `\n`, `\r\n`, `\r` on
  delimited input; Map lookups reloaded for each row; routing rows whose
  expression failed to a catch output.
- Known cost: where the outputs of a subjob nest, Polars produces the rows of
  the shared front of the plan once for each level. The payments scenario's
  job reads its payments file four times. The cure was tried and parked
  ([Each part of a subjob's plan runs once](issues/31-each-part-of-a-plan-runs-once.md)).
- Parked by the dev as the next enhancement: a lookup by regular
  expressions kept in a file
  ([Pattern lookup from a file](issues/30-pattern-lookup-from-a-file.md)).
- Left for later from
  [How v2 points at the input row that failed a job](issues/38-how-v2-points-at-the-input-row-that-failed-a-job.md).
  After user Python the row number
  is gone; where the result still has the source's key column, the row can
  be found again by one filtered read of the source (0.09 s for a million
  rows). For an error Polars still raises by itself, the row can be found by
  running the failed component's part of the plan on halves of the file (2.1
  s for a million rows, 13.1 s for five million; probe in
  `research/probes/probe_look_again_for_the_failed_row.py`).
- The XML file input and unpivot, the other two the dev named with tickets 42
  and 43, are not built.
- Not verified here: any Polars version other than 1.44.2, the target RHEL
  servers, and files beyond a few hundred MB (the dev's largest are 30 to
  100 GB).

## Out of scope

- Talend as a source for v2: no Talend-to-v2 conversion.
- Rewriting Java expressions into Python automatically: users do it by hand.
- Java in any form: no bridge, no Java routines.
- A blanket performance test for config keys: verdicts are made key by key in
  the component tickets
  ([The performance bar](issues/05-performance-bar.md)).
- Any change to `src/v1`.
- Harvesting the old v2 roadmap and audit backlog left behind in ETL-AIAgent.
