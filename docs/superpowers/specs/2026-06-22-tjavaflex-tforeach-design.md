# Phase 3.0 Design: tJavaFlex (build) + tForeach (verify)

Status: DESIGN (plan-only; no implementation yet)
Date: 2026-06-22
Branch: claude/peaceful-gates-f1e530
Author: brainstormed with the user (superpowers:brainstorming)

## 1. Summary

Phase 3.0 delivers two component work items for the DataPrep Talend -> Python ETL
engine:

1. **tJavaFlex** -- a NEW transform component (converter + engine + Java bridge
   method) that runs user Java/Groovy code in three sections (START once,
   MAIN per row, END once) sharing one scope, with optional auto-propagation of
   input columns to the output.
2. **tForeach** -- VERIFY-ONLY. The component already exists and passes 45 tests
   with full Talend parity; this item only confirms parity, removes a stale
   `needs_review` marker, and adds edge-case tests. No behavior change.

Plus one documentation fix (CLAUDE.md stale registry note).

Parity with Talend is non-negotiable (project core value). The design is grounded
in the Talaxie codegen templates (`tJavaFlex_begin/main/end.javajet`), the Talend
docs, and the real sample job `tests/talend_xml_samples/Job_tJavaFlex_0.1.item`.

### Phase framing
- **Phase 3.0** = this work (tJavaFlex build + tForeach verify + CLAUDE.md fix).
- **Phase 3.1** = the 159 pre-existing failing tests (see
  `docs/understanding/08-coverage-and-tests.md`). Explicitly OUT OF SCOPE here, to
  keep blast radius small.

## 2. Goals / Non-goals

### Goals
- tJavaFlex produces output identical to Talend for the same job + input.
- START/MAIN/END share one scope: variables declared in START (e.g.
  `int totalCount = 0;`) are visible in MAIN (per row) and END.
- Auto-propagate (DATA_AUTO_PROPAGATE) copies same-named input columns to output,
  with version-correct timing (V4.0 before MAIN, V3.2 after MAIN).
- Reuse the proven Py4J + Arrow + RowWrapper + compiled-script machinery.
- New modules meet the 95% per-module coverage floor.

### Non-goals
- Multiple output flows from one tJavaFlex (single primary output only).
- A REJECT connector on tJavaFlex (Talend has none; errors propagate).
- Chunked execution of tJavaFlex (single-call; see decision D1).
- Any change to tForeach runtime behavior.
- Fixing the 159 failing tests (Phase 3.1).

## 3. Talend semantics (reference)

Sources: Talend docs (tJavaFlex; usage of tJava/tJavaRow/tJavaFlex), Talaxie
`tdi-studio-se` codegen templates, and `Job_tJavaFlex_0.1.item`.

tJavaFlex generates, per subjob:

```
<imports>
<CODE_START>                 // once, before the row loop
for (row : input rows) {
    // DATA_AUTO_PROPAGATE (V4.0): output_row.col = input_row.col  -- BEFORE user code
    <CODE_MAIN>              // per row: reads input row, writes output row
    // DATA_AUTO_PROPAGATE (V3.2): copies AFTER user code instead
}
<CODE_END>                   // once, after the row loop
```

- `input_row` placeholder resolves to the incoming connection name (e.g. `row1`);
  `output_row` resolves to the first DATA outgoing connection name (e.g. `row2`).
- START and END run exactly once; MAIN runs once per row.
- Output schema may add columns not present on input (e.g. `status`, `is_valid`).
- tJavaFlex has no native REJECT; validation patterns use an output flag column
  (`is_valid`/`error_reason`) then a downstream filter.

Sample params observed (`Job_tJavaFlex_0.1.item`): `CODE_START`, `CODE_MAIN`,
`CODE_END` (MEMO_JAVA), `DATA_AUTO_PROPAGATE` (CHECK, true), `Version_V4.0` (true),
`IMPORT` (MEMO_IMPORT), output `metadata` adds 4 columns over the input.

## 4. Architecture

### 4.1 Files

| Layer | File | New? | Role |
|---|---|---|---|
| Converter | `src/converters/talend_to_v1/components/transform/java_flex.py` | NEW | `@REGISTRY.register("tJavaFlex")` -> `JavaFlexConverter`; extract code/imports/auto-propagate/version/schema/row-names |
| Engine | `src/v1/engine/components/transform/java_flex.py` | NEW | `@REGISTRY.register("JavaFlex","tJavaFlex")` -> `JavaFlexComponent(CodeComponentMixin, BaseComponent)` |
| Script-gen | `src/v1/engine/components/transform/java_flex_script.py` | NEW | pure fn `build_script(...) -> str`; assembles the Groovy unit (mirrors `map_compiled_script.py`) |
| Python bridge | `src/v1/java_bridge/bridge.py` | EDIT | add `execute_java_flex(...)` |
| Java bridge | `.../com/citi/gru/etl/JavaBridge.java` | EDIT | add `executeJavaFlex(...)`; reuse `ArrowSerializer` + `RowWrapper` (jar rebuild) |
| Wiring | `src/v1/engine/components/transform/__init__.py` | EDIT | import `JavaFlexComponent` so the decorator fires |
| Wiring | `src/v1/engine/context_manager.py` | EDIT | add `code_start`, `code_main`, `code_end` to `SKIP_RESOLUTION_KEYS` |
| Docs | `CLAUDE.md` | EDIT | fix stale "COMPONENT_REGISTRY static dict" note -> decorator registry |
| Converter cleanup | `src/converters/talend_to_v1/components/iterate/foreach.py` | EDIT | remove stale "no engine implementation" `needs_review` |

### 4.2 Registration (no static dict)
Confirmed: the engine resolves components via the decorator registry only
(`REGISTRY.get(comp_type)` at `engine.py:171`; `component_registry.py`). There is
NO `COMPONENT_REGISTRY` static dict in `src/v1/`. Registering tJavaFlex =
`@REGISTRY.register("JavaFlex","tJavaFlex")` + adding the import to the transform
`__init__.py`. (CLAUDE.md's claim of a static dict is stale and is fixed here.)

## 5. Config-key contract (converter -> engine)

The converter emits these JSON config keys; the engine consumes them.

| Talend param | Engine config key | Type | Default | Notes |
|---|---|---|---|---|
| `CODE_START` | `code_start` | str | `""` | runs once |
| `CODE_MAIN` | `code_main` | str | `""` | runs per row |
| `CODE_END` | `code_end` | str | `""` | runs once |
| `IMPORT` | `imports` | str | `""` | prepended to the unit |
| `DATA_AUTO_PROPAGATE` | `auto_propagate` | bool | `False` | copy same-named cols |
| `Version_V4.0` / `Version_V3_2` | `propagate_timing` | str | `"before"` | V4.0 -> `before`, V3.2 -> `after`; legacy V2.0 -> `before` |
| incoming FLOW connection label | `input_row_name` | str | `"row1"` | binds the input RowWrapper var |
| outgoing FLOW connection label | `output_row_name` | str | `"row2"` | binds the output RowWrapper var |
| output `metadata` (FLOW) | `output_schema` | list[{name,type,...}] | `[]` | may add columns |
| `TSTATCATCHER_STATS` | `tstatcatcher_stats` | bool | `False` | framework passthrough |
| `LABEL` | `label` | str | `""` | framework passthrough |

`code_start`/`code_main`/`code_end`/`imports` are added to
`ContextManager.SKIP_RESOLUTION_KEYS` so `${context.X}` is NOT substituted into
source; user code reads context via `globalMap` (matches tJavaRow, D-26).

## 6. Data flow & the generated script

1. Engine `JavaFlexComponent._process(input_data)`:
   - Build `input_schema` dict (from `schema_inputs_map` / `input_schema`, as
     `java_row_component.py` does) and normalize `output_schema` to `dict[str,str]`.
   - Call `java_flex_script.build_script(...)` to assemble the Groovy source
     (auto-propagate column matching = `input_cols & output_cols`, emitted as
     `row2.col = row1.col` before/after MAIN per `propagate_timing`).
   - Prepend `imports`; apply `groovy_escape_expression`.
   - Sync engine GlobalMap/Context into the bridge.
   - Call `self.java_bridge.execute_java_flex(df=input_data, script=..., output_schema=..., input_schema=...)`.
   - Sync GlobalMap/Context back from the bridge.
   - Return `{"main": out_df, "reject": None}`.
   - EMPTY/None input: still call the bridge (START/END must run once); the loop
     runs zero times; return an empty DataFrame with the output schema.

2. `bridge.execute_java_flex(...)`: serialize df -> Arrow, call Java
   `executeJavaFlex`, deserialize result -> DataFrame; wrapped by
   `_call_java_with_sync` for bidirectional context/globalMap sync (AP-8).

3. Java `executeJavaFlex(arrowData, script, outputSchema, inputSchema)`: compile
   the script once (compiled-script cache), bind `input` (List<RowWrapper>) and a
   pre-sized `output` (List<RowWrapper> on the output schema), run it (START,
   loop, END all in one scope), serialize `output` -> Arrow bytes.

> Cardinality: tJavaFlex is **1:1** -- the generated loop emits exactly one output
> row per input row (the standard Talend tJavaFlex shape), so `output` is pre-sized
> to `len(input)`. Row filtering/fan-out is a downstream concern, not tJavaFlex's.

The generated script (final shape):
```groovy
<imports>
<CODE_START>
for (int __i = 0; __i < input.size(); __i++) {
    RowWrapper row1 = input.get(__i)
    RowWrapper row2 = output.get(__i)
    // auto_propagate && timing == before:
    row2.<col> = row1.<col>   // for each col in (input_cols & output_cols)
    <CODE_MAIN>
    // auto_propagate && timing == after: (emit the copies here instead)
}
<CODE_END>
```

Row-var names (`row1`/`row2`) are templated from `input_row_name`/`output_row_name`.

## 7. Design decisions (confirmed with user)

- **D1 Single-call execution (no chunking).** tJavaFlex has cross-row state
  (START locals accumulate), so the loop must see all rows in one execution with
  one shared scope. We do NOT chunk (chunking would re-run START/END per chunk or
  require promoting user locals to persistent state, breaking parity). Trade-off:
  a Py4J Base64 payload ceiling (~GB scale) applies; for oversized DataFrames the
  bridge surfaces a clear error suggesting an upstream split. Parity-first.
- **D2 Empty-input still runs START/END.** Unlike tJavaRow (short-circuits empty
  input), tJavaFlex always invokes the bridge so START/END side effects occur.

## 8. Error handling

- No REJECT connector (Talend parity). Bridge compile/runtime errors are caught in
  `_process`, logged with the `[{id}]` prefix at ERROR, and re-raised as
  `ComponentExecutionError(self.id, msg, cause=e)`. The parent flow's
  `die_on_error` decides fatal-vs-continue (engine level).
- `_validate_config` (Rule 12, structural only): `code_start/code_main/code_end`
  are strings if present (all optional; all-empty is a legal no-op); `imports` str;
  `auto_propagate` bool; `propagate_timing in {"before","after"}`;
  `output_schema` dict|list. Java syntax validity is deferred to the bridge, which
  surfaces full compile diagnostics.
- ASCII-only logging; code bodies logged at DEBUG only, never INFO.

## 9. Testing strategy

- **Converter unit tests** (`tests/converters/.../transform/test_java_flex.py`):
  extraction of code sections, `imports`, `auto_propagate`, version ->
  `propagate_timing`, row-var names from connection labels, output schema,
  framework params. Fixture: `Job_tJavaFlex_0.1.item` (and `_make_node` helper).
- **Engine tests** (`tests/v1/engine/components/transform/test_java_flex.py`,
  `@pytest.mark.java` live bridge):
  - START runs once / END runs once (observable via a counter or globalMap).
  - Cross-row state: `totalCount` accumulates; END sees the final value.
  - MAIN per-row transform; output schema adds columns.
  - auto-propagate before (V4.0) vs after (V3.2).
  - Empty input: START/END run; zero MAIN iterations; empty output df w/ schema.
  - globalMap/context bidirectional sync.
  - Error propagation (bad Java -> ComponentExecutionError, no reject).
  - `imports` block respected.
- **Script-gen unit tests** (`test_java_flex_script.py`, no bridge): assembled
  Groovy text for before/after timing, auto-propagate column intersection, empty
  sections, row-name templating.
- **Java unit test**: `executeJavaFlex` in the Maven suite; jar rebuild required.
- **E2E**: convert + run `Job_tJavaFlex_0.1` (tFileInputDelimited -> tJavaFlex ->
  tFileOutputDelimited); assert output matches the sample's validation logic.
- **Coverage**: new modules (engine `java_flex.py`, converter `java_flex.py`,
  `java_flex_script.py`, bridge additions) to >= 95% line coverage; live-bridge
  tests are `@pytest.mark.java` (measured by the gate).

## 10. tForeach (verify-only)

- Confirm Talaxie parity: values are quoted literals; converter strips quotes;
  engine exposes `{cid}_CURRENT_VALUE` + `{cid}_CURRENT_ITERATION`. (Already true.)
- Remove the stale `needs_review` "No concrete engine implementation for tForeach"
  entry in `src/converters/talend_to_v1/components/iterate/foreach.py` (the engine
  impl exists and 45 tests pass).
- Add edge-case tests only if a coverage/parity gap is found (empty values list,
  single value, iteration-count globalMap). No runtime behavior change.

## 11. Open questions / risks

- **RowWrapper API**: confirm the exact get/set field-access methods and how a
  pre-sized output `List<RowWrapper>` is constructed on the output schema
  (read `RowWrapper.java` + `ArrowSerializer.java` at implementation).
- **JVM 64KB per-method bytecode limit**: a very large user MAIN block compiled as
  one method could exceed it. Unlike tMap (splittable expression lines), MAIN is
  opaque user code and cannot be auto-split. Mitigation: surface the JVM compile
  error clearly; document the limit. Rare in practice.
- **Legacy `Version_V2_0`**: timing default chosen as `before`; flag if a real
  V2.0 job appears.
- **Multiple DATA outputs**: out of scope; if a job has >1 tJavaFlex output flow,
  the converter emits a `needs_review` rather than silently dropping flows.

## 12. Execution note

Implementation is DEFERRED (plan-only). When executed: follow TDD (red->green),
include `@pytest.mark.java` live-bridge tests for anything touching the bridge,
rebuild the jar (`cd src/v1/java_bridge/java && mvn package -q`), and verify the
95% per-module gate before claiming done. Phase 3.1 (the 159 failures) remains a
separate, later effort.
