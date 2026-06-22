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
  - How `executeJavaRow` builds the Groovy `Binding`, where user code is spliced, and how the compiled-script cache key is computed.
  - How `ArrowSerializer` turns a `List<RowWrapper>` (output) + output schema into Arrow bytes, and input Arrow bytes into `List<RowWrapper>`.
  - The Py4J Base64 length-overflow guard pattern in `execute_java_row` (so `execute_java_flex` raises a clear error instead of silently truncating).

- [ ] **Step 1:** Read the four Java sources + the two bridge.py regions. In the plan notes, write the exact `RowWrapper` get/set signatures, the `Binding` variable names used by `executeJavaRow`, and the `ArrowSerializer` entry points.
- [ ] **Step 2:** Confirm whether the compiled-script cache (`compiledScriptClasses`, a `ConcurrentHashMap`) keys on source string; note the key so `executeJavaFlex` reuses it.
- [ ] **Step 3:** No code change. Deliverable: a short "Confirmed Java API" note appended to this plan file under Task 0, consumed by Tasks 2-3. Commit the note.

```bash
git add docs/superpowers/plans/2026-06-22-tjavaflex-tforeach.md
git commit -m "docs(plan): record confirmed Java bridge API for tJavaFlex"
```

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
    lines.append(f"    {input_row_name} = input.get(__i);")
    lines.append(f"    {output_row_name} = output.get(__i);")
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
  - Build `List<RowWrapper> output` of the SAME length, each on `outputSchema` (1:1 cardinality).
  - Bind `input`, `output`, `globalMap`, `context` into the Groovy `Binding` (reuse the `executeJavaRow` binding setup confirmed in Task 0). The user script declares START vars as top-level locals.
  - Compile via the existing compiled-script cache keyed on `script`; run once.
  - Serialize `output` -> Arrow bytes on `outputSchema`; return.

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

- [ ] **Step 3: Implement `executeJavaFlex`** in `JavaBridge.java`, reusing the confirmed (Task 0) ArrowSerializer + RowWrapper + compiled-script-cache calls. Bind `input`/`output`/`globalMap`/`context`; compile `script`; run; serialize `output`.

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
    out = java_bridge.bridge.execute_java_flex(
        df, script=script,
        output_schema={"id": "int", "name": "str", "total": "int"},
        input_schema={"id": "int", "name": "str"},
    )
    assert list(out["total"]) == [1, 2]   # START var shared across rows


@pytest.mark.java
def test_execute_java_flex_empty_input_runs_once(java_bridge):
    df = pd.DataFrame({"id": []})
    script = "globalMap.put(\"ran\", \"yes\");\nfor(int __i=0;__i<input.size();__i++){}\n"
    out = java_bridge.bridge.execute_java_flex(
        df, script=script, output_schema={"id": "int"}, input_schema={"id": "int"})
    assert out.empty and list(out.columns) == ["id"]
    assert java_bridge.bridge.global_map.get("ran") == "yes"
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
    comp.java_bridge = java_bridge.bridge
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
    gm = GlobalMap(); comp = _make(cfg, gm=gm); comp.java_bridge = java_bridge.bridge
    out = comp._process(pd.DataFrame({"id": []}))
    assert out["main"].empty and gm.get("ran") == "y"


def test_validate_config_rejects_bad_timing():
    with pytest.raises(Exception):
        _make({"propagate_timing": "sideways"})._validate_config()
```

- [ ] **Step 2: Run to verify fail** -- `python -m pytest -o addopts= tests/v1/engine/components/transform/test_java_flex.py -q` -> FAIL (import).
- [ ] **Step 3: Implement `JavaFlexComponent`** modeled on `java_row_component.py`: `_validate_config` (structural: strings optional; `auto_propagate` bool; `propagate_timing in {"before","after"}`; `output_schema` dict|list); `_process`: normalize schemas, `build_script(...)`, prepend `imports`, `groovy_escape_expression`, sync globalMap/context in, `self.java_bridge.execute_java_flex(...)`, sync back, return `{"main", "reject": None}` (always call bridge, even empty input). Add the import to `__init__.py` and the three keys to `SKIP_RESOLUTION_KEYS`.
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
- Produces: `JavaFlexConverter` registered as `tJavaFlex`. Emits the config-key contract from spec section 5: `code_start/code_main/code_end` (from `CODE_START/CODE_MAIN/CODE_END`), `imports` (`IMPORT`), `auto_propagate` (`DATA_AUTO_PROPAGATE`), `propagate_timing` (V4.0->`before`, V3.2->`after`, else `before`), `input_row_name`/`output_row_name` (incoming/outgoing FLOW connection labels, defaults `row1`/`row2`), `output_schema` (output FLOW metadata), `tstatcatcher_stats`, `label`. Multiple output flows -> append a `needs_review` entry.

- [ ] **Step 1: Write failing tests** off the real sample `tests/talend_xml_samples/Job_tJavaFlex_0.1.item` (parse via the existing `_make_node`/test helpers used by `test_java_row_component.py`):

```python
# assert converter extracts:
#   config["code_start"] contains "int totalCount = 0;"
#   config["code_main"] contains "row2.customer_id = customerId;"
#   config["code_end"] contains "Total records"
#   config["auto_propagate"] is True
#   config["propagate_timing"] == "before"   # Version_V4.0 true
#   config["imports"] startswith "//import"
#   output_schema has the 4 added columns (status, processed_time, error_reason, is_valid)
```

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

- [ ] **Step 1:** If any existing test asserts the `needs_review` "no engine implementation" entry, update it to assert it is ABSENT. Add edge tests if missing: empty values list -> zero iterations; single value -> `CURRENT_VALUE` set + `CURRENT_ITERATION==1`.
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

- [ ] **Step 1:** Run the per-module gate scoped to the new files:

```bash
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine --cov=src/converters --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

- [ ] **Step 2:** For any new module below 95%, add targeted tests (e.g. `_validate_config` error branches, `propagate_timing=="after"`, multi-output `needs_review`). Do NOT chase coverage on the 159 pre-existing failures (Phase 3.1) -- they are unrelated and out of scope; confirm the new modules themselves are >= 95%.
- [ ] **Step 3: Commit** any added coverage tests (`test(java_flex): cover validation + timing branches`).

---

## Self-Review

**Spec coverage:** START/MAIN/END one-scope (Tasks 1-4), auto-propagate timing (Task 1), single-call D1 (Task 3 no-chunk), empty-input D2 (Tasks 3-4), no-REJECT (Task 4 returns `reject=None`), config-key contract (Task 5), SKIP_RESOLUTION_KEYS (Task 4), registration-without-static-dict (Tasks 4-5), 1:1 output (Task 2), E2E (Task 6), tForeach verify (Task 7), 95% floor (Task 8), CLAUDE.md fix (done, `fb0f728`). No spec section is unaddressed.

**Placeholder scan:** Java method bodies in Tasks 2-3 are intentionally specified-not-typed because their exact `RowWrapper`/`ArrowSerializer` calls are confirmed in Task 0 (an explicit investigation task with a recorded deliverable), not invented. All Python and all test code is concrete. No "TBD/handle edge cases/similar to Task N".

**Type consistency:** `build_script(...)` signature (Task 1) matches its caller in Task 4; `execute_java_flex(df, *, script, output_schema, input_schema)` (Task 3) matches its caller in Task 4 and the Java `executeJavaFlex(arrowData, script, outputSchema, inputSchema)` (Task 2); row-var names flow converter (Task 5) -> engine config -> `build_script` (Task 1) consistently.

## Notes / risks (carried from spec)
- Confirm `RowWrapper` get/set + `ArrowSerializer` entry points in Task 0 before Tasks 2-3.
- JVM 64KB per-method bytecode limit for very large MAIN blocks: surface the compile error clearly; document. Rare.
- Legacy `Version_V2_0` timing defaults to `before`.
