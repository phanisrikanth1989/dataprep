# Engine v2 -- Wayfinder Map

Label: wayfinder:map

## Destination

A rebuilt v2 engine, built and passing: pure Python, Polars-fast, and able to
run v1 job configs for a chosen set of 10-15 components. It accepts v1's config
keys, takes expressions written in Python, and produces output equal to v1's.
Anything it cannot run at Polars speed it refuses at load, in one refusal
report. Done means the components are built and pass their answer-key tests,
not that they are designed.

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
  - Performance first, capability second. A v1 capability Polars cannot do
    natively, or only with a large slowdown, is refused, never emulated
    slowly.
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
    equals v1's. Polars speed has priority: where matching v1 would cost it,
    the key is refused. Deliberate differences, if any ever exist, go on a
    short written list.
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
- Component set: eight are locked -- delimited file input, delimited file
  output, filter rows, sort row, unique row, aggregate row, map, python
  dataframe. The tail is decided in
  [Pin the component list](issues/27-pin-the-component-list.md).
- Environment: run Python as `.venv/bin/python`. This Mac has polars 1.44.2
  and Python 3.14; the repo pins `polars>=1.38,<2.0` and Python 3.12+.
  Observations made here are provisional for the target servers until checked
  there. There is no JVM or bridge JAR on this Mac (as of 2026-10-04), so v1
  runs here only for Java-free job configs.
- Logs are ASCII only (repo rule).

## Decisions so far

<!-- one line per closed ticket -->

## Not yet specified

- The build. After the
  [Answer-key harness](issues/19-answer-key-harness.md): the job config loader
  with the refusal report, the engine core, a first slice (delimited file in,
  filter rows, sort row, delimited file out, assembled from repo fixtures),
  the expression translator, then each remaining component. How it is sliced
  into tickets waits on the decisions it implements. Rides along with it:
  bringing `src/v2` under the coverage gate, the benchmark harness in the new
  shape, generating doc pages from declared keys, deleting the `talend_to_v2`
  and `v1_to_v2` converters, and deleting or rewriting each `docs/v2` page
  when its subject is rebuilt.
- The tail of the component list: LogRow, filter columns, unite, python row,
  python code, context load, file list and flow to iterate, Excel and
  full-row input, and v1's ConvertType, Join and SchemaComplianceCheck. Each
  one that makes the list needs a key-by-key ticket and a build.
- Iterate, if it makes the list: iterate flows, loop bodies and nesting. The
  engine as found loses rows on fan-out inside a loop and double-runs nested
  loops (findings 6 and 7).
- Routines. v1 has Python routines; v2 as found calls them row by row unless
  they are marked vectorised, which collides with the no-callback rule.
  Whether routines exist in v2, and in what form, waits on the expression
  decisions and on what the usage count shows.
- The list of deliberate differences from v1: where it lives and what earns a
  place on it. Empty until a ticket puts something there.
- What a v1 user needs in hand to migrate a job (which Python is allowed, how
  to read a refusal report). It may fall out of the generated docs or need a
  page of its own.

## Out of scope

- Talend as a source for v2: no Talend-to-v2 conversion.
- Rewriting Java expressions into Python automatically: users do it by hand.
- Java in any form: no bridge, no Java routines.
- Emulating slowly what Polars cannot do natively: such capabilities are
  refused.
- Any change to `src/v1`.
- Harvesting the old v2 roadmap and audit backlog left behind in ETL-AIAgent.
