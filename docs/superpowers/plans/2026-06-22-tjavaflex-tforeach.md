# tJavaFlex (build) + tForeach (verify) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a parity-correct `tJavaFlex` transform component (converter + engine + a new `executeJavaFlex` Java bridge method that runs START-once / MAIN-per-row / END-once in one shared scope), and verify/clean up the already-complete `tForeach`.

**Architecture:** Python assembles a single Groovy unit (`<imports><START> for(row){<auto-propagate><MAIN>} <END>`) via a pure `java_flex_script.build_script(...)`; the Java bridge compiles+runs it once over the whole DataFrame (Arrow in/out, RowWrapper field access, compiled-script cache) -- mirroring the proven tMap compiled-script + `execute_java_row` patterns. Single-call (no chunking) preserves cross-row START-var state.

**Tech Stack:** Python 3.12, pandas, pyarrow, Py4J; Java 11 (compiled with JDK 21) + Groovy 3.0.21 in the bridge; Maven; pytest (+ `@pytest.mark.java` live bridge).

**Design source:** `docs/superpowers/specs/2026-06-22-tjavaflex-tforeach-design.md`.

## Global Constraints

- Python 3.12+; pandas 3.0.1 (Copy-on-Write); pyarrow 15.0.2; py4j 0.10.9.7; Groovy 3.0.21. No new dependencies.
- Feature parity with Talend is non-negotiable; converter JSON format must stay backward-compatible.
- ASCII-only logging (no emoji/unicode) -- RHEL servers. Code bodies logged at DEBUG only, never INFO.
- Fix the source, no defensive fallbacks. Rewrite > patch for systemic issues.
- Any change touching `{{java}}`/tMap/bridge code MUST include `@pytest.mark.java` tests that hit the live bridge. Rebuild the jar after Java changes: `cd src/v1/java_bridge/java && mvn package -q`.
- New in-scope modules must reach >= 95% per-module line coverage (the Phase 14 gate). Run the gate from CLAUDE.md "Coverage Gate".
- Branch discipline: feature branch only (`claude/peaceful-gates-f1e530`); stage files by name; never `--no-verify`.
- Engine component registration is decorator-only (`@REGISTRY.register(...)` in `component_registry.py`); there is no static dict. Converter registration is decorator-only (`@REGISTRY.register("tX")`).
- OUT OF SCOPE: the 159 pre-existing failing tests (Phase 3.1). Do not fix them here. Do not let new work depend on them.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/v1/engine/components/transform/java_flex_script.py` | Create | Pure fn: assemble the Groovy unit from code sections + schema + flags. No bridge, no state. |
| `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java` | Modify | Add `executeJavaFlex(...)`: compile once, bind input/output RowWrappers, run, return Arrow. |
| `src/v1/java_bridge/bridge.py` | Modify | Add `execute_java_flex(...)`: Arrow serialize -> Java -> deserialize; `_call_java_with_sync`. |
| `src/v1/engine/components/transform/java_flex.py` | Create | `JavaFlexComponent(CodeComponentMixin, BaseComponent)`; `@REGISTRY.register("JavaFlex","tJavaFlex")`. |
| `src/v1/engine/components/transform/__init__.py` | Modify | Import `JavaFlexComponent` so the decorator fires. |
| `src/v1/engine/context_manager.py` | Modify | Add `code_start`,`code_main`,`code_end` to `SKIP_RESOLUTION_KEYS`. |
| `src/converters/talend_to_v1/components/transform/java_flex.py` | Create | `JavaFlexConverter`; `@REGISTRY.register("tJavaFlex")`; emit the config-key contract. |
| `src/converters/talend_to_v1/components/transform/__init__.py` | Verify | Ensure converter module import triggers registration (follow existing pattern). |
| `src/converters/talend_to_v1/components/iterate/foreach.py` | Modify | Remove the stale `needs_review` "no engine implementation" entry. |
| Java unit test under `src/v1/java_bridge/java/src/test/java/...` | Create | JUnit test for `executeJavaFlex`. |
| `tests/v1/engine/components/transform/test_java_flex_script.py` | Create | Unit tests for the script generator (no bridge). |
| `tests/v1/engine/components/transform/test_java_flex.py` | Create | Engine tests (`@pytest.mark.java` live bridge). |
| `tests/converters/talend_to_v1/components/transform/test_java_flex.py` | Create | Converter unit tests off the sample item. |
| `tests/v1/engine/components/transform/test_java_flex_e2e.py` | Create | E2E convert+run of `Job_tJavaFlex_0.1`. |
| `tests/.../iterate/test_foreach.py` (both engine + converter) | Modify | Edge-case tests; drop the needs_review assertion if any. |

Dependency order: Task 0 (confirm Java API) -> 1 (script-gen) -> 2 (Java bridge) -> 3 (Python bridge) -> 4 (engine component + wiring) -> 5 (converter) -> 6 (E2E) -> 7 (tForeach verify) -> 8 (coverage gate). CLAUDE.md fix already landed (commit `fb0f728`) -- not a task here.

---

### Task 0: Confirm Java bridge internals (investigation; no behavior change)

**Files:**
- Read: `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java` (`executeJavaRow`, `executeCompiledTMapChunked`, `executeTMapCompiled`, the compiled-script cache `compiledScriptClasses`)
- Read: `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/RowWrapper.java` (field get/set API)
- Read: `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/ArrowSerializer.java` (df<->Arrow; how an output schema is applied; Decimal128(38,18) note)
- Read: `src/v1/java_bridge/bridge.py:414-610` (`execute_java_row`) and `:783-1010` (compile/execute tMap chunked) for the Python-side Arrow + chunk + sync pattern

**Interfaces:**
- Produces (record these verbatim in the plan execution notes for later tasks):
  - `RowWrapper` read accessor (e.g. `row.get("col")` or property `row.col`) and write accessor (e.g. `row.set("col", v)` or `row.col = v`).
  - The `executeTMapCompiled` (JavaBridge.java:475-516) structure -- `groovyShell.parse(script)` ONCE, ONE shared `Binding`, `script.run()` ONCE with the loop INSIDE the Groovy body. THIS is the model for `executeJavaFlex` (NOT `executeJavaRow`, which parses fresh per call, binds singular `input_row`/`output_row`, and loops Java-side).
  - The `compiledScriptClasses` cache is componentId-keyed + tMap-only; `executeJavaRow` does NOT use it (parses fresh each call). `executeJavaFlex` should likewise parse fresh -- do NOT rely on that cache.
  - Input: `buildArrowRowWrapper`/`extractTypedValue` (JavaBridge.java:780-841) -> `List<RowWrapper> input`. Output is NEW code: pre-size N empty `RowWrapper`s on `outputSchema`, then after `run()` read each `wrapper.getOutputRow().get(col)` into `Object[]` columns keyed by `outputSchema` and call `ArrowSerializer.createOutputRootFromData(allocator, dataMap, outputSchema)`. There is NO existing List<RowWrapper>->Arrow path to copy.
  - The Py4J Base64 length-overflow guard pattern in `execute_java_row` (so `execute_java_flex` raises a clear error instead of silently truncating).

- [ ] **Step 1:** Read the four Java sources + the two bridge.py regions. In the plan notes, write the exact `RowWrapper` get/set/getOutputRow signatures, the `executeTMapCompiled` parse/Binding/run structure (the model), and the `buildArrowRowWrapper`/`extractTypedValue`/`createOutputRootFromData` signatures.
- [ ] **Step 2:** Confirm `compiledScriptClasses` is componentId-keyed + tMap-only and that `executeJavaRow` parses fresh each call; record that `executeJavaFlex` will parse fresh (no cache reliance) and that the output `List<RowWrapper>` -> Arrow serialization is new code with no template.
- [ ] **Step 3:** No code change. Deliverable: a short "Confirmed Java API" note appended to this plan file under Task 0, consumed by Tasks 2-3. Commit the note.

```bash
git add docs/superpowers/plans/2026-06-22-tjavaflex-tforeach.md
git commit -m "docs(plan): record confirmed Java bridge API for tJavaFlex"
```

## Confirmed Java API (Task 0)

All four source files verified. No plan assumptions turned out wrong.

### RowWrapper (RowWrapper.java)

- Read: `Object get(String columnName)` (line 50) -- checks outputRow first, then inputRow.
  Groovy syntax: `row.columnName` (propertyMissing line 114).
- Write: `void set(String columnName, Object value)` (line 63) -- writes to outputRow.
  Groovy syntax: `row.columnName = value` (propertyMissing line 123).
- Output: `Map<String, Object> getOutputRow()` (line 90).
- Load input: `void setInputRow(Map<String, Object> row)` (line 81).
- Reset output: `void reset()` (line 99) -- clears outputRow only.

### executeTMapCompiled -- THE model for executeJavaFlex (JavaBridge.java lines 475-516)

Signature: `Map<String, byte[]> executeTMapCompiled(String javaScript, byte[] arrowData,
  Map<String, List<String>> outputSchemas, Map<String, String> outputTypes,
  String mainTableName, List<String> lookupNames,
  Map<String, Object> contextVars, Map<String, Object> globalMapVars)`

Structure (parse-once / one-Binding / run-once):
1. Deserialize arrowData -> VectorSchemaRoot.
2. Build ONE Binding via `buildTMapBinding(inputRoot, rowCount, ...)` (line 500).
3. `GroovyShell shell = new GroovyShell(compileBinding); Script compiledScript = shell.parse(javaScript)` (lines 502-503).
4. `compiledScript.setBinding(compileBinding)` (line 504).
5. `Object scriptResult = compiledScript.run()` ONCE (line 507) -- the FOR LOOP lives INSIDE the Groovy body.
6. Cast result and convert outputs to Arrow.

This is the correct model: START/END code runs once outside the loop; the loop is Groovy-side.

### executeJavaRow -- NOT the model (JavaBridge.java lines 185-275)

- Compiles the script once (line 212), caches the CLASS, but creates a FRESH Script instance
  PER ROW via `scriptClass.getDeclaredConstructor().newInstance()` (line 224).
- The FOR LOOP is Java-side (lines 221-258). Each row gets a fresh Binding with singular
  `input_row`/`output_row` variables. Cross-row shared state is IMPOSSIBLE.
- Does NOT use `compiledScriptClasses` cache.
- Confirmed NOT the model for executeJavaFlex.

### compiledScriptClasses cache (JavaBridge.java lines 64-92)

- `ConcurrentHashMap<String, CachedTMapMeta>` keyed by componentId.
- Only populated by `compileTMapScript(...)` (line 562).
- Only consumed by `executeCompiledTMap(...)` and its alias `executeCompiledTMapChunked(...)`.
- Neither `executeJavaRow` nor `executeTMapCompiled` reads or writes this cache.
- Confirmed: tMap-only cache. executeJavaFlex MUST parse fresh (no cache reliance).

### buildArrowRowWrapper / extractTypedValue (JavaBridge.java)

`private RowWrapper buildArrowRowWrapper(VectorSchemaRoot root, int rowIndex, String tableName)` (line 821):
- Iterates FieldVectors, calls `extractTypedValue` for typed value, stores under plain name
  and under short name (strips `tableName.` prefix). Calls `wrapper.setInputRow(rowMap)`.

`private static Object extractTypedValue(FieldVector vec, int rowIndex)` (line 780):
- Null -> null. VarCharVector -> String, BigIntVector -> long, IntVector -> int,
  Float8Vector -> double, Float4Vector -> float, SmallIntVector -> short, TinyIntVector -> byte,
  BitVector -> boolean, TimeStampNanoVector -> Date (nanos/1_000_000), DecimalVector/Decimal256Vector -> BigDecimal,
  else -> raw.toString().

### ArrowSerializer.createOutputRootFromData (ArrowSerializer.java lines 113-151)

Signature: `public static VectorSchemaRoot createOutputRootFromData(
  BufferAllocator allocator, Map<String, Object[]> data, Map<String, String> schema)`

- Input is COLUMN-ORIENTED: Map of colName -> Object[rowCount].
- `schema` maps colName -> Python type string (str/int/float/bool/datetime/Decimal/object).
- Decimal uses precision=38, scale=18 by default.
- Caller must close the returned root.

### Output RowWrapper -> Arrow (NEW code -- no template)

No existing List<RowWrapper> -> Arrow output path in JavaBridge.java. For executeJavaFlex:
1. Pre-size N empty RowWrapper objects (1:1 with input rows).
2. Bind as `List<RowWrapper> output` in the Groovy Binding.
3. After `run()`: for each wrapper, call `wrapper.getOutputRow().get(colName)` to build
   per-column `Object[]` arrays.
4. Call `ArrowSerializer.createOutputRootFromData(allocator, columnData, outputSchema)`.

### Py4J overflow guard (bridge.py lines 39-44)

Constant: `_PY4J_BYTE_ARG_SAFE_LIMIT = 1_500_000_000` (line 44). Raw Arrow cap at 1.5 GB
keeps Base64-expanded payload (~2.0 GB) below the signed 32-bit int limit (~2.14 GB).

Pattern (execute_java_row, lines 545-595): pre-flight `len(arrow_bytes) > limit` -> halve range;
runtime `NegativeArraySizeException` or `py4j.Base64` in exception message -> same halve-and-retry;
single unsplittable row -> re-raise.

For executeJavaFlex (single-call): raise a clear error immediately if
`len(arrow_bytes) > _PY4J_BYTE_ARG_SAFE_LIMIT` -- do NOT chunk (START state would break).

### Note on executeCompiledTMapChunked

It is a backward-compat alias for `executeCompiledTMap` (JavaBridge.java lines 630-636).
The Python-side `execute_compiled_tmap_chunked` calls `executeCompiledTMap` on the Java side
(bridge.py line 972). This has no impact on executeJavaFlex design.

---

### Task 1: Script generator `java_flex_script.build_script`

**Files:**
- Create: `src/v1/engine/components/transform/java_flex_script.py`
- Test: `tests/v1/engine/components/transform/test_java_flex_script.py`

**Interfaces:**
- Produces:
  `build_script(*, code_start: str, code_main: str, code_end: str, input_cols: list[str], output_cols: list[str], input_row_name: str, output_row_name: str, auto_propagate: bool, propagate_timing: str) -> str`
  Returns a Groovy source string. Auto-propagate emits `<out>.<col> = <in>.<col>` for `col in [c for c in output_cols if c in set(input_cols)]`, placed before MAIN when `propagate_timing == "before"` else after. The loop var is `__i`; `input`/`output` are the bound `List<RowWrapper>` names (confirm exact names in Task 0; default `input`/`output`). `imports` are NOT added here (the engine prepends them).

- [ ] **Step 1: Write the failing test (timing + auto-propagate intersection)**

```python
# tests/v1/engine/components/transform/test_java_flex_script.py
from src.v1.engine.components.transform.java_flex_script import build_script


def test_auto_propagate_before_emits_matching_cols_before_main():
    src = build_script(
        code_start="int n=0;",
        code_main="row2.status = \"OK\";",
        code_end="System.out.println(n);",
        input_cols=["id", "name", "extra_in"],
        output_cols=["id", "name", "status"],
        input_row_name="row1",
        output_row_name="row2",
        auto_propagate=True,
        propagate_timing="before",
    )
    # START before the loop, END after it
    assert src.index("int n=0;") < src.index("for (")
    assert src.index("System.out.println(n);") > src.index("for (")
    # auto-propagate copies only id+name (intersection), NOT extra_in/status
    assert "row2.id = row1.id" in src
    assert "row2.name = row1.name" in src
    assert "row2.extra_in" not in src and "row2.status = row1.status" not in src
    # copies appear before the user MAIN line
    assert src.index("row2.name = row1.name") < src.index('row2.status = "OK";')


def test_auto_propagate_after_places_copies_after_main():
    src = build_script(
        code_start="", code_main='row2.status="OK";', code_end="",
        input_cols=["id"], output_cols=["id", "status"],
        input_row_name="row1", output_row_name="row2",
        auto_propagate=True, propagate_timing="after",
    )
    assert src.index('row2.status="OK";') < src.index("row2.id = row1.id")


def test_auto_propagate_off_emits_no_copies():
    src = build_script(
        code_start="", code_main="", code_end="",
        input_cols=["id"], output_cols=["id"],
        input_row_name="row1", output_row_name="row2",
        auto_propagate=False, propagate_timing="before",
    )
    assert "row1.id" not in src
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest -o addopts= tests/v1/engine/components/transform/test_java_flex_script.py -q`
Expected: FAIL (`ModuleNotFoundError` / `build_script` undefined).

- [ ] **Step 3: Implement `build_script`**

```python
# src/v1/engine/components/transform/java_flex_script.py
"""Pure Groovy-source assembly for tJavaFlex (no bridge, no state).

Builds one unit: <START> ; for-row loop with auto-propagate + <MAIN> ; <END>.
START vars are top-level script locals, visible in the loop and in END
(Talend one-scope parity). See the Phase 3.0 design spec, section 6.
"""
from __future__ import annotations


def _propagate_lines(input_cols: list[str], output_cols: list[str],
                     in_name: str, out_name: str) -> list[str]:
    in_set = set(input_cols)
    return [f"    {out_name}.{c} = {in_name}.{c};"
            for c in output_cols if c in in_set]


def build_script(*, code_start: str, code_main: str, code_end: str,
                 input_cols: list[str], output_cols: list[str],
                 input_row_name: str, output_row_name: str,
                 auto_propagate: bool, propagate_timing: str) -> str:
    """Assemble the tJavaFlex Groovy unit. See module docstring."""
    copies = _propagate_lines(input_cols, output_cols,
                              input_row_name, output_row_name) if auto_propagate else []
    before = copies if propagate_timing == "before" else []
    after = copies if propagate_timing == "after" else []
    lines: list[str] = []
    lines.append(code_start or "")
    lines.append("for (int __i = 0; __i < input.size(); __i++) {")
    # Groovy loop-locals via `def` (NOT bare assignment, which would leak into
    # the script Binding and risk colliding with the bound input/output names).
    # Spec sec 6 shows `RowWrapper row1 = ...` illustratively; `def` avoids
    # needing the RowWrapper type imported into the script scope.
    lines.append(f"    def {input_row_name} = input.get(__i);")
    lines.append(f"    def {output_row_name} = output.get(__i);")
    lines.extend(before)
    lines.append(code_main or "")
    lines.extend(after)
    lines.append("}")
    lines.append(code_end or "")
    return "\n".join(lines)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest -o addopts= tests/v1/engine/components/transform/test_java_flex_script.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/java_flex_script.py tests/v1/engine/components/transform/test_java_flex_script.py
git commit -m "feat(java_flex): add Groovy script generator for tJavaFlex"
```

---

### Task 2: Java bridge `executeJavaFlex`

**Files:**
- Modify: `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java`
- Test: `src/v1/java_bridge/java/src/test/java/com/citi/gru/etl/JavaBridgeFlexTest.java` (create)

**Interfaces:**
- Produces: `public byte[] executeJavaFlex(byte[] arrowData, String script, java.util.Map<String,String> outputSchema, java.util.Map<String,String> inputSchema)`
  - Deserialize `arrowData` -> `List<RowWrapper> input` (using the Task 0 `ArrowSerializer` entry point).
  - Build `List<RowWrapper> output` of the SAME length, each pre-sized on `outputSchema` (1:1 cardinality). NEW code -- no template.
  - Model on `executeTMapCompiled` (Task 0): build ONE `Binding` with `input` (List<RowWrapper>), `output` (the pre-sized list), `globalMap`, `context`; `groovyShell.parse(script)` ONCE; `script.run()` ONCE (the for-loop lives inside the Groovy body, so START locals persist across rows and into END). Do NOT reuse `executeJavaRow`'s per-row fresh-Script pattern; do NOT use the componentId cache (parse fresh).
  - Serialize: read each `output` wrapper's `getOutputRow().get(col)` into `Object[]` columns keyed by `outputSchema`, then `ArrowSerializer.createOutputRootFromData(...)` -> Arrow bytes; return.

- [ ] **Step 1: Write the failing JUnit test**

```java
// JavaBridgeFlexTest.java -- start/main/end share scope; output 1:1
// Build a 2-row Arrow input (id:Integer, name:String), output schema
// (id:Integer, name:String, status:String, total:Integer).
// script:
//   "int n=0;\nfor(int __i=0;__i<input.size();__i++){\n" +
//   " row1=input.get(__i); row2=output.get(__i);\n" +
//   " row2.id=row1.id; row2.name=row1.name;\n" +
//   " n++; row2.status=\"OK\"; row2.total=n; }\n"
// assert: output row0.total==1, row1.total==2 (START var n shared across rows),
//         status=="OK", id/name propagated.
```
(Write the concrete JUnit using the project's existing ArrowSerializer test helpers; mirror an existing test in `src/v1/java_bridge/java/src/test/java/`.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd src/v1/java_bridge/java && mvn -q -Dtest=JavaBridgeFlexTest test`
Expected: compile error (`executeJavaFlex` not found) or test FAIL.

- [ ] **Step 3: Implement `executeJavaFlex`** in `JavaBridge.java` following the `executeTMapCompiled` structure (parse once, one Binding, run once): build `List<RowWrapper> input` via `buildArrowRowWrapper`/`extractTypedValue`; pre-size `List<RowWrapper> output` (N empty wrappers on `outputSchema`); bind `input`/`output`/`globalMap`/`context`; `groovyShell.parse(script)` then `run()` once; read each `output` wrapper's `getOutputRow()` into `Object[]` columns and call `ArrowSerializer.createOutputRootFromData(...)`. This output path is NEW code, not a copy of `executeJavaRow`.

- [ ] **Step 4: Run to verify pass + rebuild jar**

Run: `cd src/v1/java_bridge/java && mvn -q -Dtest=JavaBridgeFlexTest test && mvn package -q`
Expected: test PASS; `target/java-bridge-with-dependencies.jar` rebuilt.

- [ ] **Step 5: Commit**

```bash
git add src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java src/v1/java_bridge/java/src/test/java/com/citi/gru/etl/JavaBridgeFlexTest.java
git commit -m "feat(bridge-java): add executeJavaFlex (start/main/end one scope)"
```

---

### Task 3: Python bridge `execute_java_flex`

**Files:**
- Modify: `src/v1/java_bridge/bridge.py`
- Test: `tests/v1/java_bridge/test_execute_java_flex.py` (create; `@pytest.mark.java`)

**Interfaces:**
- Consumes: `JavaBridge.executeJavaFlex(...)` (Task 2).
- Produces: `JavaBridge.execute_java_flex(self, df: pd.DataFrame, *, script: str, output_schema: dict[str,str], input_schema: dict[str,str] | None = None) -> pd.DataFrame`
  - Mirror `execute_java_row`: serialize `df` -> Arrow bytes; call `self.gateway...executeJavaFlex(...)`; deserialize result -> DataFrame on `output_schema`.
  - Empty `df`: still call the bridge (START/END must run); return an empty DataFrame with `output_schema` columns.
  - Wrap the call in `_call_java_with_sync` for bidirectional context/globalMap sync.
  - On Py4J payload overflow, raise a clear error (per Task 0 guard) -- do NOT silently chunk (tJavaFlex is single-call).

- [ ] **Step 1: Write the failing live-bridge test**

```python
# tests/v1/java_bridge/test_execute_java_flex.py
import pandas as pd
import pytest


@pytest.mark.java
def test_execute_java_flex_shares_start_var_across_rows(java_bridge):
    df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
    script = (
        "int n=0;\n"
        "for (int __i=0; __i<input.size(); __i++){\n"
        " row1=input.get(__i); row2=output.get(__i);\n"
        " row2.id=row1.id; row2.name=row1.name;\n"
        " n++; row2.total=n; }\n"
    )
    out = java_bridge.execute_java_flex(
        df, script=script,
        output_schema={"id": "int", "name": "str", "total": "int"},
        input_schema={"id": "int", "name": "str"},
    )
    assert list(out["total"]) == [1, 2]   # START var shared across rows


@pytest.mark.java
def test_execute_java_flex_empty_input_runs_once(java_bridge):
    df = pd.DataFrame({"id": []})
    script = "globalMap.put(\"ran\", \"yes\");\nfor(int __i=0;__i<input.size();__i++){}\n"
    out = java_bridge.execute_java_flex(
        df, script=script, output_schema={"id": "int"}, input_schema={"id": "int"})
    assert out.empty and list(out.columns) == ["id"]
    assert java_bridge.global_map.get("ran") == "yes"
```
(Use the session `java_bridge` fixture from `tests/v1/java_bridge/conftest.py`; adjust the accessor to match how other java tests reach the bridge object.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest -o addopts= -m java tests/v1/java_bridge/test_execute_java_flex.py -q`
Expected: FAIL (`AttributeError: execute_java_flex`).

- [ ] **Step 3: Implement `execute_java_flex`** in `bridge.py`, mirroring `execute_java_row` (Arrow serialize, `_call_java_with_sync`, deserialize) minus chunking; empty-input still calls the bridge.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest -o addopts= -m java tests/v1/java_bridge/test_execute_java_flex.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/v1/java_bridge/bridge.py tests/v1/java_bridge/test_execute_java_flex.py
git commit -m "feat(bridge-py): add execute_java_flex wrapper"
```

---

### Task 4: Engine `JavaFlexComponent` + wiring

**Files:**
- Create: `src/v1/engine/components/transform/java_flex.py`
- Modify: `src/v1/engine/components/transform/__init__.py` (import `JavaFlexComponent`)
- Modify: `src/v1/engine/context_manager.py` (add `code_start`,`code_main`,`code_end` to `SKIP_RESOLUTION_KEYS`)
- Test: `tests/v1/engine/components/transform/test_java_flex.py` (`@pytest.mark.java`)

**Interfaces:**
- Consumes: `java_flex_script.build_script` (Task 1), `JavaBridge.execute_java_flex` (Task 3), `CodeComponentMixin` (existing).
- Produces: `JavaFlexComponent` registered as `("JavaFlex","tJavaFlex")`. Config keys: `code_start`,`code_main`,`code_end`,`imports`,`auto_propagate`,`propagate_timing`,`input_row_name`,`output_row_name`,`output_schema`,`tstatcatcher_stats`,`label`. `_process` returns `{"main": df, "reject": None}`.

- [ ] **Step 1: Write failing tests** (cross-row state, output schema add, empty-input runs START/END, error propagation, auto-propagate). Concrete cases:

```python
# tests/v1/engine/components/transform/test_java_flex.py
import pandas as pd
import pytest
from src.v1.engine.components.transform.java_flex import JavaFlexComponent
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ComponentExecutionError


def _make(cfg, gm=None, cm=None):
    c = JavaFlexComponent("tJavaFlex_1", cfg, gm or GlobalMap(), cm or ContextManager())
    c.config = dict(cfg)            # mirror engine deepcopy (direct-construction footgun)
    return c


@pytest.mark.java
def test_main_and_start_end_once(java_bridge):
    cfg = {
        "code_start": "int n=0;",
        "code_main": "n++; row2.id=row1.id; row2.total=n;",
        "code_end": "globalMap.put(\"final\", n);",
        "auto_propagate": False, "propagate_timing": "before",
        "input_row_name": "row1", "output_row_name": "row2",
        "output_schema": [{"name": "id", "type": "int"}, {"name": "total", "type": "int"}],
    }
    gm = GlobalMap()
    comp = _make(cfg, gm=gm)
    comp.java_bridge = java_bridge
    out = comp._process(pd.DataFrame({"id": [10, 20, 30]}))
    assert list(out["main"]["total"]) == [1, 2, 3]
    assert out["reject"] is None
    assert gm.get("final") == 3


@pytest.mark.java
def test_empty_input_still_runs_start_end(java_bridge):
    cfg = {"code_start": "globalMap.put(\"ran\",\"y\");", "code_main": "", "code_end": "",
           "auto_propagate": False, "propagate_timing": "before",
           "input_row_name": "row1", "output_row_name": "row2",
           "output_schema": [{"name": "id", "type": "int"}]}
    gm = GlobalMap(); comp = _make(cfg, gm=gm); comp.java_bridge = java_bridge
    out = comp._process(pd.DataFrame({"id": []}))
    assert out["main"].empty and gm.get("ran") == "y"


@pytest.mark.java
def test_auto_propagate_copies_matching_input_cols(java_bridge):
    cfg = {"code_start": "", "code_main": "", "code_end": "",
           "auto_propagate": True, "propagate_timing": "before",
           "input_row_name": "row1", "output_row_name": "row2",
           "output_schema": [{"name": "id", "type": "int"}, {"name": "name", "type": "str"}]}
    comp = _make(cfg); comp.java_bridge = java_bridge
    # input_cols come from schema_inputs_map (engine wires this from schema.inputs);
    # set it directly since we bypass ETLEngine here.
    comp.schema_inputs_map = {"row1": [{"name": "id", "type": "int"},
                                       {"name": "name", "type": "str"}]}
    out = comp._process(pd.DataFrame({"id": [1], "name": ["a"]}))
    # MAIN is empty -> values arrive ONLY via auto-propagate
    assert out["main"].iloc[0]["id"] == 1 and out["main"].iloc[0]["name"] == "a"


def test_validate_config_rejects_bad_timing():
    with pytest.raises(Exception):
        _make({"propagate_timing": "sideways"})._validate_config()
```

- [ ] **Step 2: Run to verify fail** -- `python -m pytest -o addopts= tests/v1/engine/components/transform/test_java_flex.py -q` -> FAIL (import).
- [ ] **Step 3: Implement `JavaFlexComponent`** modeled on `java_row_component.py`: `_validate_config` (structural: strings optional; `auto_propagate` bool; `propagate_timing in {"before","after"}`; `output_schema` dict|list); `_process`: derive `output_cols` from `config['output_schema']` (like tJavaRow at java_row_component.py:198 -- NOT `self.output_schema`) and `input_cols` from `schema_inputs_map`/`input_schema` (java_row_component.py:222-235), pass BOTH to `build_script(...)` so auto-propagate copies the upstream same-named cols; prepend `imports`, `groovy_escape_expression`, sync globalMap/context in, `self.java_bridge.execute_java_flex(...)`, sync back, return `{"main", "reject": None}` (always call bridge, even empty input). Add the import to `__init__.py` and the three keys to `SKIP_RESOLUTION_KEYS`.
- [ ] **Step 4: Run to verify pass** -- both unit (`-o addopts=`) and `-m java` selections PASS.
- [ ] **Step 5: Commit**

```bash
git add src/v1/engine/components/transform/java_flex.py src/v1/engine/components/transform/__init__.py src/v1/engine/context_manager.py tests/v1/engine/components/transform/test_java_flex.py
git commit -m "feat(engine): add JavaFlexComponent (tJavaFlex)"
```

---

### Task 5: Converter `JavaFlexConverter`

**Files:**
- Create: `src/converters/talend_to_v1/components/transform/java_flex.py`
- Verify/Modify: `src/converters/talend_to_v1/components/transform/__init__.py` (registration import, following the existing convention)
- Test: `tests/converters/talend_to_v1/components/transform/test_java_flex.py`

**Interfaces:**
- Produces: `JavaFlexConverter` registered as `tJavaFlex`. Emits the config-key contract from spec section 5: `code_start/code_main/code_end` (from `CODE_START/CODE_MAIN/CODE_END`), `imports` (`IMPORT`), `auto_propagate` (`DATA_AUTO_PROPAGATE`), `propagate_timing` (V4.0->`before`, V3.2->`after`, else `before`), `input_row_name`/`output_row_name` (from the incoming/outgoing FLOW connection `.name` -- the XML `label` attribute is stored in `TalendConnection.name`, there is NO `.label` field; read via the base `_incoming`/`_outgoing` helpers, base.py:219/226; defaults `row1`/`row2`), `tstatcatcher_stats`, `label`. Multiple output flows -> append a `needs_review` entry.
  - SCHEMA: emit `schema={'input': [], 'output': <node FLOW cols>}`. The `'input'` key MUST be present (even as `[]`) so the converter's `_propagate_input_schemas` (converter.py:367) fills it from the UPSTREAM 5-col output. The tJavaFlex node's own FLOW metadata is the 9-col OUTPUT, so do NOT use it as `schema.input`; the engine reads `output_schema` from `config['output_schema']` and `input_cols` from `schema_inputs_map`/`input_schema`. If `schema.input` is omitted, auto-propagate emits zero copies and the E2E passthrough breaks.

- [ ] **Step 1: Write failing tests** that parse the REAL sample via `XmlParser` (NOT `_make_node` -- inline params would make the extraction assertions tautological, proving nothing about XML decoding / version-timing / connection row-name derivation). Reserve `_make_node` only for synthetic edge cases.

```python
# tests/converters/talend_to_v1/components/transform/test_java_flex.py
from src.converters.talend_to_v1.xml_parser import XmlParser
from src.converters.talend_to_v1.components.transform.java_flex import JavaFlexConverter


def _node_and_conns():
    job = XmlParser().parse("tests/talend_xml_samples/Job_tJavaFlex_0.1.item")
    node = next(n for n in job.nodes if n.component_type == "tJavaFlex")
    return node, job.connections


def test_extracts_code_sections_and_flags():
    node, conns = _node_and_conns()
    cfg = JavaFlexConverter().convert(node, conns, {}).component["config"]
    assert "int totalCount = 0;" in cfg["code_start"]
    assert "row2.customer_id = customerId;" in cfg["code_main"]
    assert "Total records" in cfg["code_end"]
    assert cfg["auto_propagate"] is True
    assert cfg["propagate_timing"] == "before"      # Version_V4.0 true
    assert cfg["imports"].startswith("//import")


def test_derives_row_names_from_connections():        # the NEW, untested logic
    node, conns = _node_and_conns()
    cfg = JavaFlexConverter().convert(node, conns, {}).component["config"]
    assert cfg["input_row_name"] == "row1"            # incoming FLOW .name
    assert cfg["output_row_name"] == "row2"           # outgoing FLOW .name


def test_output_schema_adds_columns_and_input_key_present():
    node, conns = _node_and_conns()
    comp = JavaFlexConverter().convert(node, conns, {}).component
    out_names = [c["name"] for c in comp["schema"]["output"]]
    for added in ("status", "processed_time", "error_reason", "is_valid"):
        assert added in out_names
    assert "input" in comp["schema"]                  # MUST exist for propagation
```
(Confirm the exact `XmlParser` API, `job.nodes`/`job.connections` attribute names, and the `component['config']`/`component['schema']` shape against an existing converter test that parses a real `.item` before finalizing.)

- [ ] **Step 2: Run to verify fail** -> FAIL (no converter).
- [ ] **Step 3: Implement `JavaFlexConverter`** modeled on the tJavaRow converter; map params per the contract; derive row names from connections; build the component dict with input/output schema; emit `needs_review` only for >1 output flow.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit**

```bash
git add src/converters/talend_to_v1/components/transform/java_flex.py src/converters/talend_to_v1/components/transform/__init__.py tests/converters/talend_to_v1/components/transform/test_java_flex.py
git commit -m "feat(converter): add tJavaFlex converter"
```

---

### Task 6: End-to-end (convert + run the sample job)

**Files:**
- Test: `tests/v1/engine/components/transform/test_java_flex_e2e.py` (`@pytest.mark.java`)
- Input: `tests/talend_xml_samples/Job_tJavaFlex_0.1.item`

**Interfaces:** Consumes the full converter pipeline + `ETLEngine` + the live bridge.

- [ ] **Step 1: Write the failing E2E test:** convert the sample item to JSON (`convert_job`), run via `ETLEngine` with `java_config.enabled=True` on a small input CSV matching the schema (`customer_id,name,email,amount,order_date`), assert the output rows carry `status`/`is_valid`/`error_reason`/`processed_time` per the sample's MAIN logic (valid row -> `is_valid=True`, uppercased name, lowercased email; invalid email -> `is_valid=False`, `status="INVALID"`).
- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3:** Fix any integration gaps surfaced (schema wiring, row-name binding) -- no new feature code beyond reconciling Tasks 1-5.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** (`test(e2e): tJavaFlex sample job round-trip`).

---

### Task 7: tForeach verify-only cleanup

**Files:**
- Modify: `src/converters/talend_to_v1/components/iterate/foreach.py` (remove stale `needs_review`)
- Test: `tests/converters/talend_to_v1/components/iterate/test_foreach.py`, `tests/v1/engine/components/iterate/test_foreach.py`

**Interfaces:** No runtime behavior change.

- [ ] **Step 1:** Rewrite ALL THREE existing needs_review tests in `tests/converters/talend_to_v1/components/iterate/test_foreach.py` -- removing the converter's single needs_review entry makes the list empty, which HARD-FAILS `test_needs_review_present` and makes the two `for entry in result.needs_review:` loop tests pass VACUOUSLY (zero iterations, no assertion):
  - `test_needs_review_present` (~line 190): change to assert `result.needs_review == []`.
  - `test_needs_review_severity_engine_gap` (~196) and `test_needs_review_has_component_id` (~203): DELETE (they only made sense for the engine-gap entry), or repoint at a real remaining assertion -- do NOT leave bare `for ... assert` loops over an empty list.
  Also add (if missing) engine edge tests: empty values list -> zero iterations; single value -> `CURRENT_VALUE` set + `CURRENT_ITERATION == 1`.
- [ ] **Step 2: Run to verify the new/updated tests fail** (needs_review still present).
- [ ] **Step 3:** Remove the `needs_review.append({...})` block in `foreach.py` (the converter's "no concrete engine implementation" entry).
- [ ] **Step 4: Run both tForeach suites -- all green.**

```bash
python -m pytest -o addopts= tests/v1/engine/components/iterate/test_foreach.py tests/converters/talend_to_v1/components/iterate/test_foreach.py -q
```

- [ ] **Step 5: Commit** (`fix(converter): drop stale tForeach needs_review; add edge tests`).

---

### Task 8: Coverage gate for the new modules

**Files:** all new modules from Tasks 1-5.

- [ ] **Step 1:** Check coverage for the NEW modules. The whole-repo gate CANNOT be used as-is: with 159 pre-existing failures pytest exits non-zero (a literal `&&` would skip the gate), and `check_per_module_coverage.py` is whole-repo with no path filter so it would (correctly) FAIL on the 9 pre-existing below-floor modules. So decouple from pytest's exit and scope to the new files:

```bash
# coverage.json is written during pytest teardown regardless of failures; `; true`
# keeps the shell going. Then assert ONLY the new modules' percent_covered >= 95.
rm -f .coverage* coverage.json
python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine --cov=src/converters --cov-report=json ; true
python - <<'PY'
import json
NEW = [
  "src/v1/engine/components/transform/java_flex.py",
  "src/v1/engine/components/transform/java_flex_script.py",
  "src/converters/talend_to_v1/components/transform/java_flex.py",
]
files = json.load(open("coverage.json"))["files"]
bad = []
for p in NEW:
    rec = files.get(p)
    if rec is None:
        bad.append((p, "NOT MEASURED -- module never imported (gate blind spot)")); continue
    s = rec["summary"]; print(f"{s['percent_covered']:6.1f}%  {p}  (missing {s['missing_lines']})")
    if s["percent_covered"] < 95.0:
        bad.append((p, f"{s['percent_covered']:.1f}% < 95%"))
if bad:
    print("FAIL (new modules):"); [print("  -", p, "::", why) for p, why in bad]; raise SystemExit(1)
print("PASS: all new tJavaFlex modules >= 95%")
PY
```

- [ ] **Step 2:** For any new module below 95% (per the scoped check), add targeted tests (`_validate_config` error branches, `propagate_timing=="after"`, multi-output `needs_review`, empty-input path, the bridge-missing error). Do NOT touch the 159 pre-existing failures or the 9 pre-existing below-floor modules -- the whole-repo gate stays red until Phase 3.1; this task only proves the NEW modules clear the floor. (Also eyeball `bridge.py`'s coverage to confirm `execute_java_flex` did not regress the shared module.)
- [ ] **Step 3: Commit** any added coverage tests (`test(java_flex): cover validation + timing branches`).

---

## Self-Review

**Spec coverage:** START/MAIN/END one-scope (Tasks 1-4), auto-propagate timing (Task 1), single-call D1 (Task 3 no-chunk), empty-input D2 (Tasks 3-4), no-REJECT (Task 4 returns `reject=None`), config-key contract (Task 5), SKIP_RESOLUTION_KEYS (Task 4), registration-without-static-dict (Tasks 4-5), 1:1 output (Task 2), E2E (Task 6), tForeach verify (Task 7), 95% floor (Task 8), CLAUDE.md fix (done, `fb0f728`). No spec section is unaddressed.

**Placeholder scan:** Java method bodies in Tasks 2-3 are intentionally specified-not-typed because their exact `RowWrapper`/`ArrowSerializer` calls are confirmed in Task 0 (an explicit investigation task with a recorded deliverable), not invented. All Python and all test code is concrete. No "TBD/handle edge cases/similar to Task N".

**Type consistency:** `build_script(...)` signature (Task 1) matches its caller in Task 4; `execute_java_flex(df, *, script, output_schema, input_schema)` (Task 3) matches its caller in Task 4 and the Java `executeJavaFlex(arrowData, script, outputSchema, inputSchema)` (Task 2); row-var names flow converter (Task 5) -> engine config -> `build_script` (Task 1) consistently.

## Notes / risks (carried from spec)
- Confirm `RowWrapper` get/set/getOutputRow + `buildArrowRowWrapper`/`createOutputRootFromData` entry points in Task 0 before Tasks 2-3.
- JVM 64KB per-method bytecode limit for very large MAIN blocks: surface the compile error clearly; document. Rare.
- Legacy `Version_V2_0` timing defaults to `before`.
- Minor (add when convenient): a Task 2/Task 4 test with a REAL (non-comment) `import` (e.g. `import java.text.SimpleDateFormat;` + short name in CODE_START) to prove imports prepended above CODE_START compile as a Groovy script. The sample's IMPORT is a comment and CODE_START uses FQNs, so the sample itself does not exercise this; the same prepend mechanism is already proven for tJavaRow (`test_imports_compiles_real_bridge`).

## Code-review revisions (2026-06-22)

Applied after a multi-agent adversarial review of this plan (grounded in the real code). 2 critical + 5 important findings fixed:

- **[critical] Task 8 gate unexecutable** -- `&&` short-circuited on the 159-failure red suite, and the gate script is whole-repo (fails on 9 pre-existing below-floor modules). Replaced with a decoupled run (`; true`) + an inline `coverage.json` check scoped to the NEW modules only.
- **[critical] `java_bridge` fixture has no `.bridge`** -- the fixture yields the `JavaBridge` directly. Fixed every test snippet: `java_bridge.execute_java_flex(...)`, `java_bridge.global_map`, `comp.java_bridge = java_bridge`.
- **[important] Task 2 "reuse executeJavaRow" was wrong** -- `executeJavaRow` is per-row (singular vars, Java-side loop). Re-scoped Task 0/Task 2 to the `executeTMapCompiled` model (parse-once / one-Binding / run-once) and flagged the `List<RowWrapper>` output construction + Arrow serialization as NEW code (helpers: `buildArrowRowWrapper`/`extractTypedValue`/`getOutputRow`/`createOutputRootFromData`); no componentId-cache reliance (parse fresh).
- **[important] converter must keep `schema.input`** -- the tJavaFlex node's FLOW metadata is the 9-col OUTPUT; emit `schema={'input':[],'output':...}` so propagation fills input from the upstream 5 cols, else auto-propagate copies nothing. Documented `output_cols`<-config / `input_cols`<-schema_inputs_map in Task 4 + added an auto-propagate engine test.
- **[important] converter row-name derivation** -- `TalendConnection` has no `.label` (it's `.name`); read via `_incoming`/`_outgoing`. Added `input_row_name`/`output_row_name` assertions.
- **[important] converter tests were tautological** -- switched Task 5 tests to parse the real `.item` via `XmlParser` (not `_make_node`).
- **[important] Task 7 needs_review churn** -- explicitly rewrite all 3 needs_review tests (assert empty; delete the 2 now-vacuous loop tests).

Refuted on verification (NOT changed): "no one-scope precedent exists" (false -- `executeTMapCompiled` is exactly that); auto-propagate "read-after-write hazard" (false -- `row1`/`row2` are separate wrappers); the imports/cache-key "break" (false -- cache is componentId-keyed and unused by the row path; spec/plan agree imports go first). A minor row-var hygiene nit from that thread WAS applied (loop vars emitted as `def` locals, not bare Binding assignments).
