# Phase 10: Iterate Support - Research

**Researched:** 2026-05-05
**Domain:** Engine orchestration / iterate execution loop / file-system iteration / DataFrame-row iteration
**Confidence:** HIGH (Talaxie source verified, all engine internals read at file:line, sample .item fixtures confirmed)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

All A-K decisions in `10-CONTEXT.md` are LOCKED. Highlights for the planner -- the planner must honor these verbatim, not re-litigate:

- **D-A1..A6:** BaseIterateComponent stays a SUBCLASS of BaseComponent for Phase 10 (no sibling-abstract refactor). Override `execute()` to skip data-pipeline lifecycle steps (output schema validation, REJECT routing, batch/streaming dispatch). Keep validate_config + _resolve_expressions + _update_global_map. Iterator/generator-based items (`iteration_iter: Iterator[ItemType]`). Typed dataclasses per component (`FileListItem`, `FlowToIterateItem`). 9-hook lifecycle (prepare, prepare_iterations, should_stop, before_iteration, set_iteration_globalmap, [body], after_iteration, on_iteration_error, finalize). Iterate-stack-aware globalMap scope mechanism in place; depth=1 enforced in Phase 10.
- **D-B1..B4:** Iterate body subgraph = transitive closure starting at the iterate edge target, following BOTH FLOW and outbound trigger edges. Stops at: triggers ON the iterate source itself, components reachable from outside the iterate scope. Lives in ExecutionPlan as a post-build step. Iterate loop = `Executor._execute_iterate_body()` reusing `_execute_subjob` for body. Nested-iterate detection in ExecutionPlan raises `ConfigurationError`.
- **D-C1..C3:** Body component triggers fire per iteration. Triggers OUT OF the iterate SOURCE itself fire EXACTLY ONCE after all iterations complete. Empty iterate (0 items) STILL fires SUBJOB_OK.
- **D-D1..D4:** Iterate own stats: `NB_LINE` = total iterations attempted, `NB_LINE_OK` = clean iterations, `NB_LINE_REJECT` = iterations with body errors. tFileList ALSO sets `NB_FILE`. Per-iteration timing accumulated. Body-component aggregate stats = sum + per-iter list. globalMap last-write-wins (`{body_id}_NB_LINE` = last iteration's value). REJECT accumulation flow: concat per-iteration rejects into one DataFrame at iterate completion.
- **D-E1..E6:** die_on_error decides; tDie kills entire job; mid-iter rejects flushed; ERROR=true with 0 matches raises ComponentExecutionError matching Talend's "No file found in directory: ..." parity.
- **D-F1..F7:** tFlowToIterate: input MUST be non-None DataFrame, `df.to_dict('records')` iteration, DEFAULT_MAP key = `<self.inputs[0]>.<col>`, CURRENT_ITERATION 1-based BEFORE body, fix existing `_CURRENT_ITERATE` -> `_CURRENT_ITERATION` typo.
- **D-G1..G10:** tFileList: 5 RETURN vars only (NO _LASTMODIFIED/_SIZE), pathlib walking, fnmatch.translate + re.fullmatch with re.IGNORECASE, ERROR=true 0-match raises, FORMAT_FILEPATH_TO_SLASH normalization.
- **D-H1..H7:** ASCII-only logging, 4-tier (start/end summary, per-iter for total<=50, rate-limited 10% for >50, DEBUG body traces), `iterate.log_per_iter_threshold` configurable (default 50).
- **D-I1..I4:** `BaseComponent.reset()` and `_original_config` deepcopy give EXEC-05/EXEC-06 essentially "for free" -- no new code in Phase 10 for these. Java bridge per-call sync handles iterate Java expression updates without changes. May need partial-subjob clear helper on OutputRouter.
- **D-J1..J4:** Converter changes: ENABLE_PARALLEL/NUMBER_PARALLEL extraction with needs_review entry severity=`engine_gap`. Other converters unchanged.
- **D-K1..K3:** tFileExist verify-only, no code changes.
- **D-L1..L4:** Recommended 8 sub-phase split (10-01..10-08). All new components conform to ENGINE_COMPONENT_PATTERN.md. Every phase plan ends with `@pytest.mark.java` integration test where Java is involved. Phase 7.1 Rule 12 (content checks in `_process`, NOT `_validate_config`).

### Claude's Discretion

- Internal class structure of BaseIterateComponent execute() override
- Exact stats dataclass / dict shape for per-iteration timing
- Internal pathlib walking optimization (generator vs list materialization)
- REJECT accumulation buffer strategy (in-memory list of DataFrames vs concat-on-flush)
- Test fixture design (existing StubComponent vs new IterateStubComponent)
- Helper-function vs method placement for body-subgraph BFS algorithm
- Exact format string for log messages (D-H1..H5 are the spec; minor wording is discretion)
- Whether `iterate.log_per_iter_threshold` config goes in job-level config or engine-level constants
- ASCII separator characters in log lines (`|`, `--`, `:`)

### Deferred Ideas (OUT OF SCOPE)

- Nested iterate execution (Phase 10.1)
- ENABLE_PARALLEL parallel iteration (Phase 12+)
- Sibling-abstract refactor (Phase 10.5+)
- tForeach, tLoop, tInfiniteLoop concrete engines (later phases)
- Streaming-mode for huge tFlowToIterate inputs (Phase 12+)
- tFileList globalMap _LASTMODIFIED / _SIZE vars (audit invented; not in Talaxie)
- EXCLUDEFILEMASK as TABLE (Talaxie has it as TEXT)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXEC-04 | Implement iterate execution -- `_handle_iterate()` calling `_execute_subjob()` per iteration item | Section 4 (concrete pseudocode for `Executor._execute_iterate_body`); Section 2 (insertion point in `executor.py:188-242`) |
| EXEC-05 | Implement `BaseComponent.reset()` for state cleanup between iterate re-executions | Section 2 (`base_component.py:1336-1346` already exists; D-I1 says no new code -- iterate loop calls existing method) |
| EXEC-06 | Implement config snapshot/restore for components re-executed in iterate loops | Section 2 (`base_component.py:225` `copy.deepcopy(self._original_config)` already runs every `execute()`; D-I2 says no new code) |
| ITER-01 | Implement tFlowToIterate engine component | Section 8 (df.to_dict('records') pattern); Section 6 (Talaxie _end.javajet confirms NB_LINE finalization) |
| ITER-02 | tFlowToIterate DEFAULT_MAP=true: store as `{flowName}.{columnName}` | D-F3; engine reads `self.inputs[0]` (`engine.py:120`) |
| ITER-03 | tFlowToIterate custom MAP mode: user-defined key-value pairs | D-F4; entry['key'] verbatim, entry['value'] = column |
| ITER-04 | Implement tFileList engine component | D-G1..G10; Section 6 (Talaxie _end.javajet confirms ERROR=true RuntimeException) |
| ITER-05 | tFileList globalMap variables (5 RETURN vars per Talaxie _java.xml) | D-G1; Talaxie verified -- _LASTMODIFIED/_SIZE NOT present |
| ITER-06 | tFileList INCLUDSUBDIR (note misspelling preserved) | D-G2 (rglob recursive, iterdir non-recursive) |
| ITER-07 | tFileList sort order options | D-G6 (ORDER_BY_NOTHING, ORDER_BY_FILENAME, ORDER_BY_FILESIZE, ORDER_BY_MODIFIEDDATE; ORDER_ACTION_DESC reverses) |
| ITER-08 | tFileExist file_name vs file_path config key | Already implemented (`file_exist.py:44-51`); verify-only |
| ITER-09 | tFileExist `{id}_EXISTS` and `{id}_FILENAME` globalMap vars | Already implemented (`file_exist.py:87-89`); verify-only |
| ITER-10 | Register all iterate components in `COMPONENT_REGISTRY` | Existing decorator pattern (`@REGISTRY.register("FileList", "tFileList")`) |
| ITER-11 | `{id}_CURRENT_ITERATE` globalMap variable | D-F7 RENAMES this to `_CURRENT_ITERATION` to match Talaxie source. Existing typo at `base_iterate_component.py:150` is the bug being fixed. |
| TEST-04 | Engine unit tests for iterate components | Section 11 (test strategy); Section 12 (validation architecture); .item fixtures verified to exist |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Tech stack:** Python 3.10+ engine; pandas (`set[str]` syntax used). pandas runtime is **3.0.1** (verified via `python3 -c "import pandas as pd; print(pd.__version__)"`) -- has CoW and Arrow strings.
- **Talend feature parity:** Non-negotiable. Engine must produce identical results to Talend for the same input. Talaxie .javajet is the source of truth.
- **No converter changes** beyond ENABLE_PARALLEL extraction. JSON contract preserved.
- **ASCII-only logging:** No emojis, no unicode arrows, no box-drawing characters. RHEL servers consume the logs (project memory `feedback_ascii_logging`).
- **Real Java bridge tests:** `@pytest.mark.java` for any test with Java expressions inside iterate bodies (Phase 5.1 lesson `feedback_test_real_bridge`).
- **Phase 7.1 Rule 12:** Content checks in `_process()`, NOT in `_validate_config()` (`_validate_config` runs BEFORE context resolution).
- **No defensive fallbacks** (project memory `feedback_fix_source_no_fallbacks`): if iterate input is malformed, fail loudly. Don't silently route empty DataFrames.
- **GSD workflow:** All edits go through GSD commands.

---

## 1. Executive Summary

The planner must absorb these ten facts before sequencing tasks:

1. **Three production files to extend, two new files to create.** The iterate loop hooks into `Executor._execute_subjob()` (`executor.py:188`), the body subgraph is built in `ExecutionPlan` post-construction, and REJECT accumulation lives between Executor and OutputRouter. New files: `src/v1/engine/components/iterate/__init__.py`, `flow_to_iterate.py`, and `src/v1/engine/components/file/file_list.py`.

2. **EXEC-05 and EXEC-06 are 90% pre-built.** `BaseComponent.reset()` exists at `base_component.py:1336`, and `copy.deepcopy(self._original_config)` runs on every `execute()` call at line 225. Phase 10 only WIRES these into the iterate loop -- it does NOT implement them.

3. **The existing BaseIterateComponent at `base_iterate_component.py` has a CRITICAL BUG** (D-F7 -- line 150): it sets `f"{self.id}_CURRENT_ITERATE"` but the Talaxie canonical key is `_CURRENT_ITERATION`. The skeleton ALSO uses `iteration_items: list` instead of an iterator (D-A3), and `prepare_iterations` returns `list[Any]` instead of `Iterator[ItemType]`. Sub-phase 10-01 must rewrite this skeleton.

4. **`Executor._execute_subjob()` is documented as the iterate building block** (`executor.py:170-172` literally says: "This is THE building block that Phase 10 iterate support will call in a loop per iteration item."). The hook point is just before line 188's `for comp_id in subjob_plan.component_ids:`. When the component is iterate-typed, route to `_execute_iterate_body(iter_comp, body_plan)` which internally calls `_execute_subjob(virtual_body_plan)` per iteration.

5. **Iterate is FLOW-typed, not trigger-typed.** `OutputRouter` already has `"iterate": "iterate"` in its `_FLOW_TYPE_TO_RESULT_KEY` map (`output_router.py:26`). `TriggerManager` does NOT need a new TriggerType. The body subgraph BFS follows FLOW + outbound triggers (D-B1) but the iterate edge itself is a flow.

6. **Body subgraph is intra-subjob in production** -- both Phase 10 .item fixtures produce ONE subjob_1 containing iterate source + body. The body subgraph is therefore a SUBSET of the existing SubjobPlan's component_ids, identified by BFS from the iterate edge target. ExecutionPlan needs a new method `get_iterate_body_plan(iter_component_id) -> SubjobPlan` (virtual SubjobPlan with topologically-sorted body component IDs).

7. **OutputRouter.clear_subjob_flows() supports partial-subjob clear with one tweak.** It currently iterates `for comp_id in subjob_component_ids:` (`output_router.py:230`). Passing the body's component subset works AS-IS for clearing body flows -- but the cross-subjob preservation logic uses `executed_components` to decide preservation. The subtle issue: between iterations, body components ARE in `executed_components` for that iteration but should be removed before next iteration. The iterate loop must remove body components from `executed_components` AFTER the partial clear (D-B3 says exactly this).

8. **REJECT accumulation strategy = drain-between-iterations.** After each body `_execute_subjob` returns, the iterate loop drains any DataFrames sitting in REJECT-typed flows owned by body components, appends them to an in-memory list of DataFrames, then `clear_flow(reject_flow_name)` is called BEFORE next iteration. At iterate completion, `pd.concat(reject_buffers, ignore_index=True)` produces the iterate component's `result["reject"]`. This requires a new helper on OutputRouter to drain the reject flows by name (or by component); see Section 5 for design.

9. **The two .item fixtures produce a single subjob_1 each** (verified via `Job_tFileList_0.1.item` and `Job_tFlowToIterate_0.1.item`). Both already encode `ENABLE_PARALLEL=false` and `NUMBER_PARALLEL=2` in their ITERATE connection elementParameters (lines 277-278 and 342-343 respectively). The converter change (D-J3) is to read these and write them into the flow dict; the engine ignores them in Phase 10 with a warning logged via the `needs_review` mechanism.

10. **Talaxie `tForeach_java.xml` (forward reference) confirms the lifecycle hooks generalize.** tForeach has CONNECTOR FLOW (max_input=0, max_output=0) + ITERATE (max_output=1) + standard subjob/component triggers. RETURN is `CURRENT_VALUE` (id_String, FLOW availability). The 9-hook lifecycle (D-A5) plus typed `IterateItem` dataclass design (D-A4) accommodates `ForeachItem(value: str, index: int)` cleanly without base-class changes -- proven by extension fit.

**Primary recommendation:** Sequence sub-phases as 10-01 (base) -> 10-02 (executor + plan + reject infra) -> 10-03 (tFileList) -> 10-04 (tFlowToIterate) -> 10-05 (converter ENABLE_PARALLEL) -> 10-06 (logging) -> 10-07 (integration tests with .item fixtures + `@pytest.mark.java`) -> 10-08 (tFileExist verify). Each unit-test sub-phase uses `StubComponent` from `tests/v1/engine/conftest.py:26` for body simulation; integration tests use the real fixtures.

---

## 2. Architectural Responsibility Map

| Capability | Primary Owner | Secondary | Rationale |
|------------|--------------|-----------|-----------|
| Iterate item production (file walk, row iteration) | Iterate component (`tFileList`, `tFlowToIterate`) | BaseIterateComponent | Component-specific data extraction belongs in component; base provides lifecycle skeleton. |
| Iterate lifecycle hooks (prepare/before/after/finalize) | BaseIterateComponent | -- | Generic lifecycle -- subclasses override hooks. |
| Body subgraph identification | ExecutionPlan | -- | Pure-data graph computation, no runtime state. Pre-built, validated, reused per execution. |
| Iterate execution loop (call body N times) | Executor (`_execute_iterate_body`) | OutputRouter, BaseComponent.reset | Orchestrator owns loop control, delegates routing/cleanup to existing services. |
| Per-iteration globalMap setup | Iterate component (`set_iteration_globalmap`) | GlobalMap | Component knows the variable names; GlobalMap stores. |
| Body component reset between iterations | Executor calls `BaseComponent.reset()` | BaseComponent | Reset is a per-component concern; orchestrator triggers it on the body subset. |
| Inter-iteration data flow cleanup | OutputRouter (`clear_subjob_flows` / new partial helper) | Executor | Flow cleanup is OutputRouter's job; orchestrator passes body subset. |
| REJECT accumulation across iterations | Executor (drains per-iter, concats at end) | OutputRouter | Drain helper on OutputRouter; concat lives in the iterate loop method. |
| Trigger evaluation across iterate boundary | TriggerManager (unchanged) | Executor | Existing TriggerManager works as-is; Executor decides per-iter vs after-all firing. |
| ENABLE_PARALLEL extraction | Converter (`_parse_flows`) | -- | Converter's job to surface XML config. Engine ignores in Phase 10. |
| Validation that iterate not nested (Phase 10 only) | ExecutionPlan post-build | Executor (raises) | Static graph property; computable at plan-build time. |

---

## 3. Existing Code to Extend (file:line references)

### 3.1 BaseIterateComponent (`src/v1/engine/base_iterate_component.py`)

The current skeleton (202 lines) has 4 issues to fix in 10-01:

| Line | Current | Fix |
|------|---------|-----|
| 59 | `self.iteration_items: list[Any] = []` | Replace with `self.iteration_iter: Iterator[Any] = iter(())` (D-A3) |
| 80 | `self.iteration_items = self.prepare_iterations(input_data)` | Materialize from iterator: `self.iteration_iter = self.prepare_iterations(input_data)`; do NOT pre-materialize the list (allows tInfiniteLoop in future) |
| 95 | `def prepare_iterations(...) -> list[Any]:` | `-> Iterator[Any]:` (D-A3) |
| 150 | `f"{self.id}_CURRENT_ITERATE"` | `f"{self.id}_CURRENT_ITERATION"` (D-F7) |
| (new) | -- | Add `prepare`, `should_stop`, `before_iteration`, `after_iteration`, `on_iteration_error`, `finalize` hooks (D-A5) |
| (new) | -- | Override `execute()` to skip data-pipeline lifecycle steps (D-A2) |
| (new) | -- | Add `_iterate_depth: int = 0` field for nesting scope (D-A6) |

The current `_process()` at line 67-88 is wrong for Phase 10 -- iterate components must NOT use the BaseComponent template. The new design overrides `execute()` directly.

### 3.2 BaseComponent template (`src/v1/engine/base_component.py`)

| Line | Step | What iterate skips |
|------|------|---------------------|
| 219 | RUNNING status -- KEEP | -- |
| 225 | `copy.deepcopy(self._original_config)` -- KEEP (gives EXEC-06 for free) | -- |
| 228 | `_validate_config()` -- KEEP | -- |
| 231 | `_resolve_expressions()` -- KEEP (iterate may have Java in MAP entries) | -- |
| 234 | `die_on_error` read -- KEEP | -- |
| 237 | `_count_input_rows` -- SKIP (iterate's NB_LINE = total iterations, not input rows; tFlowToIterate sets it itself) | YES |
| 240-250 | `_select_mode` + `_execute_batch/streaming` + schema enforcement -- SKIP | YES |
| 253 | `_update_stats_from_result` -- SKIP (iterate's stats roll-up is custom) | YES |
| 254 | `_update_global_map()` -- KEEP | -- |
| 256-266 | SUCCESS + return -- KEEP (modified: return `{"main": None, "reject": <accumulated>, "iterate": <iter_marker>}`) | -- |

The override structure: BaseIterateComponent.execute() is its own template-method that runs validate_config, resolve_expressions, prepare hook, prepare_iterations, then RETURNS (after marking `iteration_iter` ready). The Executor's `_execute_iterate_body` then drives the loop. This mirrors the current contract -- the Executor was already calling `component.execute()` first, then querying `is_iterate_component`.

### 3.3 Executor (`src/v1/engine/executor.py`)

**Insertion point for iterate loop:** `_execute_subjob()` at lines 188-242. Current loop iterates `subjob_plan.component_ids`. Add detection of iterate components:

```python
# After line 205 (after _execute_component returns 'success' for iterate)
component = self.components[comp_id]
if getattr(component, "is_iterate_component", False):
    body_plan = self.execution_plan.get_iterate_body_plan(comp_id)
    self._execute_iterate_body(component, body_plan)
    # Mark body components as completed for trigger evaluation,
    # then SKIP them in the outer subjob loop
    for body_id in body_plan.component_ids:
        self.executed_components.add(body_id)
```

The iterate-source's outbound triggers (OnSubjobOk etc.) fire EXACTLY ONCE -- they're already handled by `_collect_triggered_subjobs` at the end of `_execute_subjob`. No change to firing logic at line 232 -- that path already fires once per subjob.

The body-component triggers fire per iteration (D-C1) -- this is automatic because `_fire_component_triggers` is called inside `_execute_iterate_body` -> `_execute_subjob(body_plan)` -> per-component trigger firing.

### 3.4 ExecutionPlan (`src/v1/engine/execution_plan.py`)

**Insertion point for body-subgraph BFS:** Constructor at line 117 ends with cross-subjob flow detection. ADD step 8: identify iterate body subgraphs.

```python
# ---- 8. Identify iterate body subgraphs (Phase 10) ----
self._iterate_body_plans: dict[str, SubjobPlan] = {}
for comp_id, comp_config in self._components.items():
    if comp_config.get("type") in {"FlowToIterate", "tFlowToIterate", "FileList", "tFileList"}:
        self._iterate_body_plans[comp_id] = self._build_iterate_body_plan(comp_id)

# ---- 9. Detect nested iterate (Phase 10 only -- raises) ----
self._detect_nested_iterate()
```

Need a registry of "iterate types" -- pull from `BaseIterateComponent` subclass registration. Cleaner: move the type set to ExecutionPlan as `_ITERATE_TYPES: frozenset[str] = frozenset({"FlowToIterate", "tFlowToIterate", "FileList", "tFileList"})` and document that future iterate components add here.

**Public method:** `get_iterate_body_plan(iter_component_id: str) -> SubjobPlan`.

### 3.5 OutputRouter (`src/v1/engine/output_router.py`)

`clear_subjob_flows(component_set, executed_components)` works with arbitrary component sets -- just pass the body subset. The cross-subjob preservation logic correctly preserves flows that downstream subjobs haven't consumed yet (`output_router.py:240-252`).

**New helper needed:** `drain_reject_flows(component_set: set[str]) -> dict[str, pd.DataFrame]` that returns and clears all reject-type flows whose `from` is in `component_set`. The iterate loop calls this between iterations to accumulate body REJECT data. Existing `clear_flow(flow_name)` at line 197 supports the per-flow clear after drain.

### 3.6 ComponentRegistry (`src/v1/engine/component_registry.py`)

Existing decorator pattern works as-is (line 29). New components register:
- `@REGISTRY.register("FlowToIterate", "tFlowToIterate")`
- `@REGISTRY.register("FileList", "tFileList")`

`src/v1/engine/components/iterate/__init__.py` (new) imports both modules to trigger registration. `src/v1/engine/components/__init__.py:6` adds `from . import iterate`.

### 3.7 engine.py inputs/outputs wiring

`engine.py:120` reads `comp_config.get('inputs', [])` into `component.inputs`. tFlowToIterate accesses `self.inputs[0]` for DEFAULT_MAP key prefix (D-F3). Already wired. No change.

### 3.8 Converter `_parse_flows` (`src/converters/talend_to_v1/converter.py:220-239`)

Currently parses connections of FLOW/MAIN/REJECT/FILTER/UNIQUE/DUPLICATE/ITERATE types into flow dicts with `{name, from, to, type}`. The function does NOT currently access elementParameter children of the connection.

**Extension point:** Need to plumb elementParameter access. Two options:
1. Modify `xml_parser._parse_connections()` (lines 238-273) to read `ENABLE_PARALLEL` and `NUMBER_PARALLEL` into a new `params: dict[str, str]` field on TalendConnection.
2. Re-walk the XML in the converter (less clean).

**Recommended:** Option 1. Extend `TalendConnection` dataclass in `src/converters/talend_to_v1/components/base.py:36-42` with `params: dict[str, str] = field(default_factory=dict)`. Update `_parse_connections` to populate it from elementParameter loop already at lines 254-261. Then `_parse_flows` reads `conn.params.get("ENABLE_PARALLEL")` and `conn.params.get("NUMBER_PARALLEL")` for ITERATE-type connections.

---

## 4. Body Subgraph BFS Algorithm (concrete pseudocode)

**Goal:** Given the iterate edge `(src, tgt)`, identify the body component set so the executor can re-run those components per iteration. The iterate-source's OWN subjob_id is unchanged (D-J4 confirms intra-subjob iterate).

**Inputs:**
- `iter_component_id: str` (the iterate source, e.g., `tFileList_1`)
- `flows: list[dict]` (all flows from job config)
- `triggers: list[TriggerEdge]` (already built)
- `component_to_subjob: dict[str, str]`

**Outputs:**
- `SubjobPlan` (virtual) with body components topologically sorted

**Algorithm:**

```python
def _build_iterate_body_plan(self, iter_component_id: str) -> SubjobPlan:
    # 1. Find the iterate edge target(s). An iterate component may have
    #    multiple ITERATE-typed outgoing flows (rare in production but allowed).
    iterate_targets: list[str] = [
        f["to"] for f in self._flows
        if f["from"] == iter_component_id and f.get("type") == "iterate"
    ]
    if not iterate_targets:
        # No body -- iterate fires triggers but does no body work.
        # Return empty SubjobPlan; loop runs N times with empty body.
        return SubjobPlan(
            subjob_id=f"{iter_component_id}_body",
            component_ids=[],
            component_set=frozenset(),
        )

    # 2. BFS from each iterate target, following FLOW + outbound trigger edges.
    body: set[str] = set()
    queue: deque[str] = deque(iterate_targets)
    own_subjob = self._component_to_subjob[iter_component_id]

    # Components reachable from outside the iterate scope = "external entry" set
    # (must be excluded -- they have an independent execution path)
    external_entries = self._compute_external_entries(iter_component_id, iterate_targets)

    while queue:
        current = queue.popleft()
        if current in body:
            continue
        if current == iter_component_id:
            # Reached iterate source via cycle -- skip (cycle would be an error
            # but it's possible via triggers; we don't recurse into source)
            continue
        if current in external_entries:
            # Not part of body -- has independent path
            continue
        if self._component_to_subjob.get(current) != own_subjob:
            # Cross-subjob -- not body (different subjob)
            continue

        body.add(current)

        # Follow outbound FLOW edges
        for f in self._flows:
            if f["from"] == current and f.get("type") != "iterate":
                queue.append(f["to"])

        # Follow outbound trigger edges (OnComponentOk, OnComponentError,
        # RunIf to component, OnSubjobOk on a component)
        for edge in self._trigger_edges:
            if edge.from_component == current:
                # Triggers FROM iterate source itself fire after-all (D-C2);
                # skip them. Triggers from BODY components are followed
                # (their targets are part of body if reachable).
                queue.append(edge.to_component)

    # 3. Detect cycle back to iterate source via triggers (error per spec)
    for edge in self._trigger_edges:
        if edge.from_component in body and edge.to_component == iter_component_id:
            raise ConfigurationError(
                f"Iterate component '{iter_component_id}' has a trigger cycle: "
                f"body component '{edge.from_component}' points back to iterate source "
                f"via {edge.trigger_type}. This is not supported."
            )

    # 4. Topologically sort body using existing _build_subjob_plan logic
    return self._topo_sort_body(iter_component_id, body)

def _compute_external_entries(self, iter_component_id, iterate_targets):
    """Components in own_subjob that have inbound flows/triggers from
    OUTSIDE the iterate's reachable closure. These are excluded from body."""
    # In Phase 10's intra-subjob model, external entries are rare. The
    # canonical case: an iterate body component that is ALSO a downstream
    # consumer of the iterate-source's parent flow chain. Empirically,
    # the two .item fixtures have no external entries.
    return set()
```

**Stop conditions explicitly handled:**
- (a) Triggers ON the iterate source itself: `if edge.from_component in body and edge.to_component == iter_component_id` raises.
- (b) Cross-subjob components: `if self._component_to_subjob.get(current) != own_subjob` skipped.
- (c) Reaching iterate source: `if current == iter_component_id` skipped.

**Nested iterate detection (D-B4):** AFTER all body plans are built, scan each body for any iterate component. If found, raise:

```python
def _detect_nested_iterate(self):
    for iter_id, body_plan in self._iterate_body_plans.items():
        for body_id in body_plan.component_set:
            if self._components.get(body_id, {}).get("type") in _ITERATE_TYPES:
                raise ConfigurationError(
                    f"Nested iterate detected: '{iter_id}' contains '{body_id}' "
                    f"in its body. Phase 10 does not support nested iterate. "
                    f"This restriction will be lifted in Phase 10.1."
                )
```

---

## 5. Iterate Execution Loop (concrete pseudocode for `Executor._execute_iterate_body`)

```python
def _execute_iterate_body(
    self,
    iter_component: BaseIterateComponent,
    body_plan: SubjobPlan,
) -> None:
    """Run the body subgraph once per iteration item produced by the iterate
    component. Updates iter_component.stats with cumulative + per-iter timing.
    Accumulates body REJECT flows into iter_component.reject_buffer.
    """
    cid = iter_component.id
    # iter_component.execute() has already run -- prepare()/_validate_config/
    # _resolve_expressions/prepare_iterations are done. iteration_iter is ready.

    body_component_set = body_plan.component_set
    reject_buffer: list[pd.DataFrame] = []

    iter_count_attempted = 0
    iter_count_ok = 0
    iter_count_err = 0
    iter_times: list[float] = []
    iter_start_total = time.time()

    # Scope mechanism: track depth (D-A6)
    iter_component._iterate_depth = self._current_iterate_depth + 1
    self._current_iterate_depth += 1
    try:
        # Iterate-start log (D-H1, ASCII-only)
        # Estimate total only if iterator is bounded (sized); otherwise -1
        total_hint = iter_component.total_iterations  # set by prepare_iterations for bounded cases
        logger.info(
            "[%s] Starting iterate: %d items, %d components in body",
            cid, total_hint, len(body_plan.component_ids),
        )

        for index, item in enumerate(iter_component.iteration_iter, start=1):
            # Hook: should_stop (D-A5.3) -- early termination
            if iter_component.should_stop(item, index):
                break

            # Hook: before_iteration (D-A5.4)
            iter_component.before_iteration(item, index)

            # Set CURRENT_ITERATION before body runs (D-F5)
            self.global_map.put(f"{cid}_CURRENT_ITERATION", index)

            # Hook: set_iteration_globalmap (D-A5.5) -- pushes iter vars
            iter_component.set_iteration_globalmap(item)

            # Per-iteration logging (D-H3 / D-H4)
            self._log_iteration_progress(iter_component, index, total_hint)

            # Run the body subjob (REUSES existing _execute_subjob)
            t0 = time.time()
            iter_count_attempted += 1
            body_failed = False
            try:
                # CRITICAL: _execute_subjob expects subjob_id to lookup from
                # ExecutionPlan. We need a variant that takes a SubjobPlan
                # directly, OR we register the body_plan into a synthetic
                # subjob_id. Recommended: add `_execute_subjob_plan(plan)`
                # that takes the plan directly, and have `_execute_subjob(id)`
                # delegate to it. Pure refactor, no behavior change.
                body_result = self._execute_subjob_plan(body_plan)
                if body_result == "error":
                    body_failed = True
            except ComponentExecutionError as e:
                if getattr(e, "exit_code", None) is not None:
                    # tDie inside body -> kill entire job (D-E5)
                    raise  # propagate; execute_job sees _job_terminated
                body_failed = True
                # Hook: on_iteration_error (D-A5.8)
                if not iter_component.on_iteration_error(item, index, e):
                    raise

            iter_time = time.time() - t0
            iter_times.append(iter_time)

            # Drain body REJECT flows for this iteration
            iter_rejects = self.output_router.drain_reject_flows(body_component_set)
            for rej_df in iter_rejects.values():
                if rej_df is not None and not rej_df.empty:
                    reject_buffer.append(rej_df)

            # Hook: after_iteration (D-A5.7)
            iter_component.after_iteration(
                item, index, body_stats=self._snapshot_body_stats(body_plan)
            )

            # Roll up body-component stats into engine.execution_stats per D-D3
            self._rollup_body_stats(body_plan, index)

            if body_failed:
                iter_count_err += 1
            else:
                iter_count_ok += 1

            # Reset body components for next iteration (EXEC-05; D-I1)
            for body_id in body_plan.component_ids:
                if body_id in self.components:
                    self.components[body_id].reset()
                # Remove from executed_components so they re-execute next iter
                self.executed_components.discard(body_id)

            # Clear body data flows (preserving any cross-subjob consumers)
            self.output_router.clear_subjob_flows(
                body_component_set, self.executed_components
            )

            # Check for tDie termination
            if self._job_terminated:
                break

        # Hook: finalize (D-A5.9)
        iter_component.finalize()

    finally:
        self._current_iterate_depth -= 1

    # Iterate-end log (D-H2)
    total_elapsed = time.time() - iter_start_total
    logger.info(
        "[%s] Iterate complete: %d OK, %d errors, total elapsed=%.2fs",
        cid, iter_count_ok, iter_count_err, total_elapsed,
    )

    # Build iterate component's final stats (D-D1, D-D2)
    iter_component.stats["NB_LINE"] = iter_count_attempted
    iter_component.stats["NB_LINE_OK"] = iter_count_ok
    iter_component.stats["NB_LINE_REJECT"] = iter_count_err
    if iter_times:
        iter_component.stats["total_iter_time"] = sum(iter_times)
        iter_component.stats["avg_iter_time"] = sum(iter_times) / len(iter_times)
        iter_component.stats["slowest_iter_time"] = max(iter_times)
        iter_component.stats["fastest_iter_time"] = min(iter_times)
        iter_component.stats["slowest_iter_index"] = iter_times.index(max(iter_times)) + 1
        iter_component.stats["fastest_iter_index"] = iter_times.index(min(iter_times)) + 1

    # Concat REJECT buffer and route as iterate component's reject output
    if reject_buffer:
        accumulated_reject = pd.concat(reject_buffer, ignore_index=True)
        # Route via OutputRouter (the iterate's reject output flow, if defined)
        self.output_router.route_outputs(cid, {"reject": accumulated_reject})

    # Update globalMap (NB_LINE etc.)
    iter_component._update_global_map()
    # Mark iterate-source completed; trigger firing happens in caller
    self.executed_components.add(cid)
```

**Key subtleties:**

- **`_execute_subjob_plan(plan)` refactor:** Current `_execute_subjob(id)` looks up the SubjobPlan via `self.execution_plan.get_subjob_plan(subjob_id)`. Refactor: extract the loop body into `_execute_subjob_plan(plan)` and have `_execute_subjob(id)` call it. This lets the iterate loop pass a virtual body plan directly.
- **Trigger firing per iteration:** `_fire_component_triggers` is called inside `_execute_subjob_plan` for every body component. Per D-C1, body component triggers fire per iteration -- this is automatic and correct.
- **OnSubjobOk for body subjob:** If the body subjob ITSELF has OnSubjobOk on it (rare with intra-subjob iterate), it would fire after each iteration. Check: in Phase 10's intra-subjob model, the body is part of the parent subjob, so OnSubjobOk fires once after the parent subjob completes (which is once after iterate completes). This matches D-C2. No special handling needed.
- **_count_input_rows in BaseIterateComponent:** The override should NOT call this. tFlowToIterate sets NB_LINE = `len(input_data)` directly in `prepare_iterations`. tFileList sets NB_LINE / NB_FILE = matched files count.

---

## 6. REJECT Accumulation Design

**Buffer strategy:** In-memory `list[pd.DataFrame]`, concat once at the end.

**Why list-of-DFs vs running concat:** `pd.concat` is O(n) per call -- repeated concat would be O(N^2) total. List append + single final concat is O(N).

**Memory profile:** Each iteration's body produces typically 0-100 reject rows. For 10,000 iterations with avg 10 reject rows, total = 100,000 rows in memory at concat. At ~200 bytes/row this is ~20 MB. Acceptable for Phase 10. If a future workload has very large rejects, defer to a streaming flush in Phase 12+.

**Schema (D-D4):** Union (column-wise) of all body components' reject schemas. `pd.concat(buffers, ignore_index=True)` does this naturally -- pandas pads missing columns with NaN. If multiple body components have DIFFERENT reject schemas, the consumer must handle the union DataFrame; document this in the iterate component's docstring.

**Routing:** The iterate component declares `reject` in its outputs (config `outputs: ["..."]`). When the iterate loop concats and calls `self.output_router.route_outputs(cid, {"reject": df})`, the existing routing logic (`output_router.py:118-130`) routes via the flow with `type="reject"` whose `from=cid`. Downstream consumers (e.g., a tFileOutputDelimited capturing rejects) see this flow normally.

**Drain helper to add to OutputRouter:**

```python
def drain_reject_flows(self, component_ids: set[str]) -> dict[str, pd.DataFrame]:
    """Drain all reject-type outgoing flows from the given component set.
    Returns dict[flow_name, DataFrame] and removes the flows from data_flows.
    Used by the iterate loop to accumulate body REJECT data per iteration.
    """
    drained: dict[str, pd.DataFrame] = {}
    for comp_id in component_ids:
        for flow in self._outgoing.get(comp_id, []):
            if flow.get("type") != "reject":
                continue
            flow_name = flow["name"]
            if flow_name in self._data_flows:
                drained[flow_name] = self._data_flows.pop(flow_name)
    return drained
```

---

## 7. Talaxie .javajet Findings

### 7.1 `tFileList_end.javajet` (HIGH confidence -- fetched 2026-05-05)

```jsp
}                                            // close iteration loop
globalMap.put("<%=cid%>_NB_FILE", NB_FILE<%=cid%>);
<%-- if log4j active: log.info("<%=cid%> - File or directory count : " + NB_FILE<%=cid%>); --%>
<% if (ERROR) { %>
if (NB_FILE<%=cid%> == 0) throw new RuntimeException("No file found in directory " + directory_<%=cid%>);
<% } %>
```

**Implications:**
- `NB_FILE` is set unconditionally (even if 0). D-G1 already says set to 0 when no matches.
- ERROR=true RuntimeException only raises AFTER counting (file count = 0). Engine parity: `if ERROR and not files: raise ComponentExecutionError(self.id, f"No file found in directory: {directory}")`. Note the message is `"No file found in directory <dir>"` (Talend uses no colon, but `:` is acceptable for parity per D-G8 which already specifies `"No file found in directory: <directory>"` -- the colon is a parity-acceptable variation).

### 7.2 `tFlowToIterate_end.javajet` (HIGH confidence -- fetched 2026-05-05)

```jsp
globalMap.put("<%=node.getUniqueName() %>_NB_LINE", nb_line_<%=node.getUniqueName() %>);
```

**Implications:**
- Single line. NB_LINE finalization happens AFTER the iteration loop completes (loop closure is in _main.javajet, not _end.javajet).
- Engine parity: After all iterations, set `globalMap.put(f"{cid}_NB_LINE", iter_count_attempted)` -- this is already covered by `BaseComponent._update_global_map()` at finalize (since `self.stats["NB_LINE"] = iter_count_attempted`).
- NO cleanup logic. NO close-brace cleanup beyond the loop boundary.

### 7.3 `tForeach_java.xml` (HIGH confidence -- fetched 2026-05-05) -- forward reference

| Property | Value |
|----------|-------|
| Parameters | `VALUES` (TABLE) -- single column ITEM=VALUE |
| Connectors | FLOW (max_in=0, max_out=0), ITERATE (max_out=1), SUBJOB_OK, SUBJOB_ERROR, COMPONENT_OK, COMPONENT_ERROR, RUN_IF |
| Returns | `CURRENT_VALUE` (id_String, FLOW availability) |

**Implications for base-class design (validates D-A4):**
- The 9-hook lifecycle (D-A5) accommodates tForeach trivially: `prepare_iterations` yields each VALUE row; `set_iteration_globalmap(item)` does `globalMap.put(f"{cid}_CURRENT_VALUE", item.value)`.
- Typed dataclass: `ForeachItem(value: str, index: int)` -- one field, simple.
- No FLOW input (max_input=0) -- matches `input_data is None` semantics; iterate base-class must allow `prepare_iterations(None)`.
- Confirms the typed-item-dataclass abstraction (D-A4) generalizes -- planner can claim the design is future-proof for tForeach without extra changes.

### 7.4 Already-fetched (from CONTEXT.md, HIGH confidence)

- `tFlowToIterate_java.xml`: 2 params (DEFAULT_MAP, MAP), 6 connectors, 2 RETURN vars (NB_LINE AFTER, CURRENT_ITERATION FLOW).
- `tFlowToIterate_main.javajet`: confirms `globalMap.put("<inputRowName>.<col>", value)` pattern for DEFAULT_MAP=true and `globalMap.put(<KEY>, <inputRowName>.<VALUE>)` for DEFAULT_MAP=false.
- `tFileList_java.xml`: 17 params (incl. INCLUDSUBDIR misspelling), 7 connectors, 5 RETURN vars (CURRENT_FILE, CURRENT_FILEPATH, CURRENT_FILEDIRECTORY, CURRENT_FILEEXTENSION, NB_FILE).
- `tFileList_begin.javajet`: walking + sorting + glob/regex matching reference.

---

## 8. Pandas DataFrame Iteration Patterns

**Runtime confirmed pandas 3.0.1 (CoW + Arrow strings).**

### Comparison

| Method | Speed | Type fidelity | NaN handling | Recommendation |
|--------|-------|---------------|--------------|----------------|
| `df.to_dict('records')` | Materializes upfront; fast lookup | Native Python types (int -> int, float -> float, NaN -> nan); pandas timestamps preserved | NaN stays as float('nan') | **CHOSEN for tFlowToIterate (D-F2)** -- closest to Talend per-row Java semantics |
| `df.itertuples(index=False, name=None)` | Fastest; tuple-based | Preserves dtypes; named-tuple variant slower | NaN preserved | Better perf but tuple positional access. Use if perf becomes a concern in Phase 12+. |
| `df.iterrows()` | Slowest; Series-based | Returns Series (loses dtype on heterogeneous DataFrame) | NaN preserved | AVOID -- many existing engine components use this; no need to change for Phase 10. |

**Why `to_dict('records')` for tFlowToIterate:**
1. Talend's generated code does `<inputRowName>.get("col")` per row -- dict-style access is the natural mirror.
2. DEFAULT_MAP=true iterates over column names per row: `for col, value in row.items()` -- dict-records gives this directly.
3. Loss of pandas-specific dtypes (e.g., Int64 nullable -> int) is acceptable; Python is dynamic.

### Edge cases

- **Empty DataFrame (zero rows):** `pd.DataFrame().to_dict('records')` returns `[]`. Iterate count = 0. D-F1 says no error. The 9-hook lifecycle still calls `prepare()` and `finalize()`; `should_stop` and per-iter hooks never fire.
- **NaN in row dict:** `{'col': nan}` (float). Subscribed by user code as NaN -- the iteration target consumer (e.g., tFileInputDelimited reading via `globalMap.get("row1.filepath")`) gets NaN. Engine sets globalMap as-is; downstream Java/Python expressions deal with NaN.
- **Mixed dtypes:** `to_dict('records')` does no type coercion. A column of `Int64` becomes Python int (or pd.NA for nulls -- caution: pd.NA in globalMap may break Java bridge type-detection). RECOMMEND: in tFlowToIterate `_process`, convert pd.NA to None before `globalMap.put`. Confirm via `@pytest.mark.java` test in 10-04.
- **Non-string column names:** D-F3 specifies the key as `f"{self.inputs[0]}.{col}"`. If `col` is int (e.g., positional column), str(col) is the safe coercion. ADD: `f"{self.inputs[0]}.{str(col)}"` defensively.

### tFileList iteration

`pathlib.Path(directory).iterdir()` returns a generator. `rglob('*')` returns a generator. Both are lazy by default, but for SORT to work the iterate component must materialize to a list FIRST, then sort, then iterate. Memory note: 10,000 files = ~10,000 Path objects = ~5 MB. Acceptable.

For 100,000+ files (D-G2 deferred memory concern), Phase 12 streaming optimization would chunk-walk and merge-sort. Phase 10 materializes.

---

## 9. Converter Changes (ENABLE_PARALLEL extraction)

### Where the change goes

**File 1:** `src/converters/talend_to_v1/components/base.py:36-42` (TalendConnection dataclass)

```python
@dataclass
class TalendConnection:
    """A connection (edge) between two Talend components."""
    name: str
    source: str
    target: str
    connector_type: str
    condition: Optional[str] = None
    params: Dict[str, str] = field(default_factory=dict)  # NEW
```

**File 2:** `src/converters/talend_to_v1/xml_parser.py:238-273` (_parse_connections)

In the elementParameter loop already at lines 254-261, ALSO collect arbitrary parameters into a dict:

```python
params: Dict[str, str] = {}
for ep in conn_elem.findall("elementParameter"):
    ep_name = ep.get("name", "")
    ep_value = ep.get("value", "")
    if ep_name == "UNIQUE_NAME":
        name = self._strip_quotes(ep_value or label)
    elif ep_name == "CONDITION":
        if ep_value:
            condition = ep_value
    else:
        # Capture all OTHER params (ENABLE_PARALLEL, NUMBER_PARALLEL, ...)
        params[ep_name] = self._strip_quotes(ep_value)
```

**File 3:** `src/converters/talend_to_v1/converter.py:220-239` (_parse_flows)

```python
@staticmethod
def _parse_flows(connections):
    flows = []
    needs_review_entries = []  # NEW: collect engine_gap warnings
    for conn in connections:
        if conn.connector_type not in _FLOW_CONNECTOR_TYPES:
            continue
        if not conn.source or not conn.target:
            continue
        flow = {
            "name": conn.name or conn.source,
            "from": conn.source,
            "to": conn.target,
            "type": conn.connector_type.lower(),
        }
        # NEW: ITERATE-specific extras
        if conn.connector_type == "ITERATE":
            enable_parallel = conn.params.get("ENABLE_PARALLEL", "false").lower() == "true"
            number_parallel = int(conn.params.get("NUMBER_PARALLEL", "0") or "0")
            flow["enable_parallel"] = enable_parallel
            flow["number_parallel"] = number_parallel
            if enable_parallel:
                needs_review_entries.append({
                    "severity": "engine_gap",
                    "component_id": conn.source,
                    "message": (
                        f"Parallel iteration is configured (NUMBER_PARALLEL={number_parallel}) "
                        "but Phase 10 engine runs sequentially -- results correct but slower. "
                        "Defer to Phase 12+ for parallel."
                    ),
                })
        flows.append(flow)
    return flows, needs_review_entries  # signature changes
```

**Caller update:** `convert_file` consumes `_parse_flows` and currently expects a list. Update to unpack the tuple and append `needs_review_entries` to the existing `result.needs_review` accumulator.

**Tests:** Converter unit test in 10-05 verifies:
1. ENABLE_PARALLEL=false -> flow has `enable_parallel=False`, no needs_review entry.
2. ENABLE_PARALLEL=true -> flow has `enable_parallel=True`, needs_review entry present with severity=engine_gap.
3. Non-ITERATE flows have no extra keys (regression -- don't pollute FLOW/REJECT flow dicts).

---

## 10. Risks, Edge Cases, Gotchas

### 10.1 Already mitigated by D-* decisions

- Nested iterate (D-B4 -- ExecutionPlan rejects)
- ENABLE_PARALLEL ignored sequentially (D-J3 -- needs_review surfaces)
- Empty input (D-F1 -- 0 iterations, OnSubjobOk fires)
- ERROR=true 0 matches (D-G8 -- raises with parity message)
- ASCII-only logging (D-H7)
- Phase 7.1 Rule 12 (D-L4)

### 10.2 Need explicit attention from the planner

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Subjob with iterate but no FLOW-downstream from target** -- the body is just the iterate target alone | Body BFS produces a single-component body; loop runs target N times. This is valid. | Test case in 10-02 covers single-component body. |
| **Iterate target has multiple inbound triggers** | Body BFS could include components from outside the iterate scope | Already handled by `external_entries` check; verify via test. |
| **DataFrame columns with non-string names in DEFAULT_MAP** | `f"{flow}.{col}"` may break if col is int | Coerce to str: `f"{flow}.{str(col)}"` |
| **pd.NA in row dict pushed to globalMap** | Java bridge type-detection may fail on pandas-specific NA | Convert pd.NA -> None before put. Add `@pytest.mark.java` test in 10-04. |
| **Java bridge sync timing per iteration** | If Java bridge caches globalMap state, per-iter changes might not propagate | Phase 2 sync-after-every-call (`bridge.py`) handles this. Confirm via integration test (`Job_tFlowToIterate_0.1.item` uses Java in tMap). |
| **`output_router.clear_subjob_flows` removes parent-subjob flows when given body subset** | If body subset and parent subjob coincide, parent's pre-iterate flows get wiped | D-J4 confirms intra-subjob iterate. Body subset is a STRICT SUBSET of parent subjob (excludes iterate source itself). The iterate source's outgoing flow (`type=iterate`) is NOT cleared because `iterate_source` is not in body subset. Verify via unit test in 10-02. |
| **`executed_components.discard(body_id)` between iterations** | If a body component is ALSO consumed by an external (non-body) subjob, removing it from executed_components could cause re-execution there | D-J4 + D-B1 limit body to intra-subjob; cross-subjob body isn't in scope. Document in code comment. |
| **tFileList directory contains 100,000+ files** | Memory pressure on materialized list for sort | Deferred to Phase 12 streaming. Document in component docstring. |
| **Concurrent file modifications during walk** | pathlib.rglob may yield partially-resolved paths or skip new files | Deterministic-snapshot semantics not guaranteed. Document as "OS behavior; Talend has same caveat." |
| **ORDER_BY_NOTHING=true means OS-default order** | Tests must NOT assert specific file order in this mode | D-G6 explicit; tests in 10-03 use ORDER_BY_FILENAME for determinism. |
| **fnmatch case-insensitivity uses re.IGNORECASE** | `fnmatch.translate` produces a regex; pass to `re.compile(..., re.IGNORECASE)` | D-G4 explicit. Verify via test. |
| **Existing `BaseIterateComponent._process` returns `{"main": input_data, "reject": None}`** | After override of `execute()`, _process becomes dead code | Remove _process override entirely; iterate components don't go through BaseComponent template. |

### 10.3 Hidden assumptions to surface

- **Assumption:** ITERATE flow type is intra-subjob in production Citi jobs. If a Citi job has ITERATE crossing subjob boundaries, body BFS as described won't find body components. **Mitigation:** Phase 12 integration test against Citi production .item samples will surface; Phase 10 documents the assumption explicitly.
- **Assumption:** `_execute_subjob` can safely re-execute the same components. Already confirmed by Phase 1 D-09 (BaseComponent re-executable via `_original_config` deepcopy).

---

## 11. Test Strategy and Fixtures

### 11.1 Existing fixtures

- **`StubComponent`** (`tests/v1/engine/conftest.py:26`): Configurable test stub for BaseComponent. Accepts `output_data`, `reject_data`, `should_fail`, `fail_message`. **Usable for body components in 10-02 unit tests** -- can simulate per-iteration body that produces N rows or fails.
- **`make_stub_component(comp_id, config, global_map, context_manager)`** factory at `conftest.py:79`.
- **`make_job_config(components, flows, triggers, subjobs)`** at `conftest.py:111`.
- **Session-scoped `java_bridge` fixture** at `conftest.py:201` -- starts real JVM via `JavaBridgeManager`. Used by `@pytest.mark.java` tests. Symlinks JAR for worktree support.

### 11.2 New fixtures to add (in 10-01 / 10-02)

- **`IterateStubComponent`**: Subclass of BaseIterateComponent for testing the executor iterate loop without depending on real tFileList/tFlowToIterate. Config keys: `items: list[Any]` (raw items to yield), `globalmap_key_prefix: str` (e.g., "TEST_") for set_iteration_globalmap. Returns a typed `StubIterateItem(value: Any, index: int)` dataclass. Lives in `tests/v1/engine/conftest.py` alongside StubComponent.
- **`make_iterate_job_config(iter_id, body_components, items, ...)`** factory: builds a complete job config with iterate source + body components + ITERATE flow. Reduces test boilerplate.

### 11.3 Test file layout (per ENGINE_TEST_PATTERN.md)

| Sub-phase | Test files |
|-----------|-----------|
| 10-01 | `tests/v1/engine/test_base_iterate_component.py` -- 9 hooks, iterator-based items, typed dataclass, depth scope, `_CURRENT_ITERATION` rename |
| 10-02 | `tests/v1/engine/test_executor_iterate.py` -- iterate loop, body BFS via ExecutionPlan, REJECT accumulation, nested-iterate detection, single-component body, multi-component body, body trigger firing per iter, source trigger firing once, tDie inside body terminates, die_on_error=false continues |
| 10-02 | `tests/v1/engine/test_execution_plan_iterate.py` -- body subgraph BFS algorithm tests (cycle detection, external entries, intra-subjob constraint) |
| 10-02 | `tests/v1/engine/test_output_router_iterate.py` -- `drain_reject_flows`, partial-subjob clear semantics |
| 10-03 | `tests/v1/engine/components/file/test_file_list.py` -- glob/regex modes, INCLUDSUBDIR true/false, all sort variants, ERROR=true/false 0-match, FORMAT_FILEPATH_TO_SLASH, all 5 globalMap RETURN vars set |
| 10-04 | `tests/v1/engine/components/iterate/test_flow_to_iterate.py` -- empty input, multi-row, DEFAULT_MAP=true, DEFAULT_MAP=false with MAP entries, CURRENT_ITERATION 1-based ordering, last-row globalMap persistence |
| 10-05 | `tests/converters/talend_to_v1/test_iterate_connection_extraction.py` -- ENABLE_PARALLEL=true/false, needs_review entries, regression on FLOW/REJECT |
| 10-06 | `tests/v1/engine/test_iterate_logging.py` -- ASCII-only assertion, threshold-based behavior switch, rate-limited 10% progress, DEBUG body traces |
| 10-07 | `tests/integration/test_iterate_e2e.py` -- convert + execute `Job_tFileList_0.1.item` end-to-end, convert + execute `Job_tFlowToIterate_0.1.item` end-to-end. **Both with `@pytest.mark.java`** because tMap is in body. Compare output to expected fixture files. |
| 10-08 | `tests/integration/test_file_exist_e2e.py` -- if not already covered, add tFileExist + RUN_IF + downstream subjob test using a real .item sample |

### 11.4 Critical test patterns

- **`@pytest.mark.java` everywhere body has Java expressions** (Phase 5.1 lesson). Both Phase 10 .item fixtures use tMap in body -> all integration tests need real bridge.
- **ASCII-only log assertion:** `assert all(ord(c) < 128 for c in caplog.text)` after iterate log capture.
- **Per-iter timing assertion:** Stats dict has `total_iter_time`, `avg_iter_time`, etc. (D-D2).
- **Reject accumulation assertion:** Body fails iter 1 with 5 rejects, succeeds iter 2-3 with 0 rejects, fails iter 4 with 3 rejects -> iterate's `result["reject"]` has 8 rows.
- **Trigger-firing assertions (D-C1, D-C2):** Body's OnComponentOk fires 3 times (3 iters). Iterate-source's OnSubjobOk fires once.

---

## 12. Validation Architecture (for Nyquist VALIDATION.md)

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing; no version pinned in repo, runtime version detected at execution) |
| Config file | none -- pytest discovers via `tests/` dir convention; markers `java` registered via existing conftest in `tests/v1/engine/conftest.py` |
| Quick run command | `pytest tests/v1/engine/test_base_iterate_component.py -x` |
| Body BFS quick check | `pytest tests/v1/engine/test_execution_plan_iterate.py::test_body_bfs_intra_subjob -x` |
| Full suite command | `pytest tests/v1/engine/ tests/integration/test_iterate_e2e.py tests/converters/talend_to_v1/test_iterate_connection_extraction.py` |
| Java suite | `pytest tests/integration/test_iterate_e2e.py -m java` (requires built JAR) |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXEC-04 | Iterate loop executes body N times per iteration item | unit | `pytest tests/v1/engine/test_executor_iterate.py::test_body_runs_per_item -x` | Wave 0 |
| EXEC-05 | BaseComponent.reset() called between iterations | unit | `pytest tests/v1/engine/test_executor_iterate.py::test_body_components_reset_between_iters -x` | Wave 0 |
| EXEC-06 | Body components see fresh _original_config per iteration | unit | `pytest tests/v1/engine/test_executor_iterate.py::test_body_config_freshness -x` | Wave 0 |
| ITER-01 | tFlowToIterate iterates input rows | unit | `pytest tests/v1/engine/components/iterate/test_flow_to_iterate.py::test_iterates_each_row -x` | Wave 0 |
| ITER-02 | DEFAULT_MAP=true sets `<flow>.<col>` keys | unit | `pytest tests/v1/engine/components/iterate/test_flow_to_iterate.py::test_default_map_keys -x` | Wave 0 |
| ITER-03 | Custom MAP uses entry['key']/entry['value'] | unit | `pytest tests/v1/engine/components/iterate/test_flow_to_iterate.py::test_custom_map_mode -x` | Wave 0 |
| ITER-04 | tFileList walks directory | unit | `pytest tests/v1/engine/components/file/test_file_list.py::test_walks_files -x` | Wave 0 |
| ITER-05 | All 5 RETURN vars set per file | unit | `pytest tests/v1/engine/components/file/test_file_list.py::test_globalmap_return_vars -x` | Wave 0 |
| ITER-06 | INCLUDSUBDIR true recurses, false does not | unit | `pytest tests/v1/engine/components/file/test_file_list.py::test_recursive_walk -x` | Wave 0 |
| ITER-07 | All sort orders applied correctly | unit | `pytest tests/v1/engine/components/file/test_file_list.py::test_sort_variants -x` | Wave 0 |
| ITER-08 | tFileExist accepts file_name OR file_path | unit | `pytest tests/v1/engine/components/file/test_file_exist.py::test_accepts_both_keys` (verify exists) | EXISTS (verify only) |
| ITER-09 | tFileExist sets _EXISTS, _FILENAME | unit | `pytest tests/v1/engine/components/file/test_file_exist.py::test_globalmap_vars` (verify exists) | EXISTS (verify only) |
| ITER-10 | All iterate components in REGISTRY | unit | `pytest tests/v1/engine/test_component_registry.py::test_iterate_components_registered -x` | Wave 0 |
| ITER-11 | tFlowToIterate sets _CURRENT_ITERATION (renamed from _CURRENT_ITERATE) | unit | `pytest tests/v1/engine/test_base_iterate_component.py::test_current_iteration_key_name -x` | Wave 0 |
| TEST-04 | Iterate components covered by unit tests | unit | runs all of the above; coverage gate >=90% on new files | Wave 0 |
| TEST-04 (integ) | End-to-end .item -> JSON -> execute | integration | `pytest tests/integration/test_iterate_e2e.py -m java` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/v1/engine/test_base_iterate_component.py tests/v1/engine/test_executor_iterate.py -x` (~5s)
- **Per wave merge:** Full unit + converter suite: `pytest tests/v1/engine/ tests/converters/talend_to_v1/test_iterate_connection_extraction.py -x` (~30s)
- **Phase gate:** Full suite including `@pytest.mark.java` integration before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/v1/engine/test_base_iterate_component.py` -- covers ITER-11, lifecycle hooks
- [ ] `tests/v1/engine/test_executor_iterate.py` -- covers EXEC-04, EXEC-05, EXEC-06
- [ ] `tests/v1/engine/test_execution_plan_iterate.py` -- covers body BFS + nested-iterate detection
- [ ] `tests/v1/engine/test_output_router_iterate.py` -- covers `drain_reject_flows`
- [ ] `tests/v1/engine/components/file/test_file_list.py` -- covers ITER-04..07
- [ ] `tests/v1/engine/components/iterate/__init__.py` (test dir init)
- [ ] `tests/v1/engine/components/iterate/test_flow_to_iterate.py` -- covers ITER-01..03, ITER-11
- [ ] `tests/converters/talend_to_v1/test_iterate_connection_extraction.py` -- covers ENABLE_PARALLEL
- [ ] `tests/v1/engine/test_iterate_logging.py` -- covers D-H1..H7
- [ ] `tests/integration/test_iterate_e2e.py` -- covers TEST-04 integration with both .item fixtures
- [ ] Conftest extension: add `IterateStubComponent`, `make_iterate_job_config` to `tests/v1/engine/conftest.py`

No framework install needed -- pytest already in use.

### Talend parity verification (for TEST-04 + future TEST-06)

**Available now (Phase 10):**
- Both `Job_tFileList_0.1.item` and `Job_tFlowToIterate_0.1.item` fixtures exist (verified 294 + 367 lines).
- Each fixture's expected output is the converter JSON (snapshot-tested) + the executed engine result.

**Not yet available (deferred to TEST-06 in Phase 12):**
- Golden-file comparison against actual Talend Studio runs of the same .item files.
- Phase 10 integration tests assert: (a) job converts cleanly, (b) job executes without error, (c) iterate counters and globalMap values match Talaxie-derived expectations, (d) output file row count matches expectation.
- Phase 10 does NOT byte-compare engine output to a Talend Studio reference. That's TEST-06 / Phase 12.

---

## 13. Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All engine code | Yes | 3.10+ (CLAUDE.md verified) | -- |
| pandas | DataFrame iteration in tFlowToIterate | Yes | 3.0.1 (verified) | -- |
| pytest | Tests | Yes | (runtime detected) | -- |
| Java bridge JAR | `@pytest.mark.java` integration tests | Conditional | -- | Tests skip via existing conftest fixture if JAR not built |
| Maven (mvn) | Java bridge build | Yes (per CLAUDE.md tech stack) | 3.x | -- |
| pathlib | tFileList walk | stdlib | -- | -- |
| fnmatch | tFileList glob mode | stdlib | -- | -- |
| re | tFileList regex mode | stdlib | -- | -- |

**No missing dependencies.** All required tooling is already installed and working in prior phases.

---

## 14. Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `tForeach` will use the same lifecycle as Phase 10 base (ASSUMED, based on _java.xml RETURN inspection) | 7.3 | Medium -- if tForeach needs additional hooks (e.g., post-loop cleanup of VALUES table), base may need extension in Phase 11+. Not a Phase 10 blocker. |
| A2 | tFileList `CURRENT_FILEEXTENSION` has no leading dot (matches Java File.getName + lastIndexOf convention) | D-G1 (CONTEXT.md notes "to be confirmed in plan-phase research") | Low -- engine implementation can do `path.suffix.lstrip('.')`. Plan-phase research can confirm by inspecting tFileList_begin.javajet logic. |
| A3 | `ENABLE_PARALLEL` and `NUMBER_PARALLEL` are the ONLY ITERATE-specific connection params worth surfacing | 9 | Low -- if other params exist, _parse_connections still captures them all into `params` dict. The needs_review entry is specific to ENABLE_PARALLEL, but plan-phase can scan more values. |
| A4 | `to_dict('records')` correctly handles pandas-3 Arrow string dtypes | 8 | Low -- pandas 3.0 Arrow strings convert to Python str. If type fidelity issue surfaces, swap to itertuples in 10-04 unit tests as the canary. |
| A5 | Body subgraph for both Phase 10 .item fixtures is the FULL subjob minus the iterate source | 4, 10 | Low -- both .item samples have a single subjob_1 with iterate as the source. BFS finds all the rest. Confirmed by reading both fixture connection lists. |
| A6 | tDie inside iterate body propagates correctly via existing `_job_terminated` flag | 5 | Low -- existing executor.py:298-316 handles tDie. Phase 10 just needs to detect `_job_terminated` after each body call and break the iterate loop. |

---

## 15. Open Questions

1. **CURRENT_FILEEXTENSION leading-dot semantics.**
   - What we know: tFileList_java.xml lists `CURRENT_FILEEXTENSION` as a RETURN var.
   - What's unclear: Does Talaxie generate `.java` or `java` from a `report.java` file?
   - Recommendation: Plan-phase fetches `tFileList_begin.javajet` (already cited in CONTEXT.md) and inspects the substring extraction. If unable to verify, default to `path.suffix.lstrip('.')` (no leading dot) and add a note in the engine docstring marking this as a deviation candidate. Cover both cases in unit tests with explicit assertion documentation.

2. **REJECT schema when body has multiple reject-emitting components.**
   - What we know: D-D4 says union (column-wise).
   - What's unclear: If two body components both have `reject` outputs, are their rejects merged into ONE iterate `reject` flow, or kept separate?
   - Recommendation: Phase 10 merges into ONE iterate `reject` flow (simplest; matches the iterate component declaring a single `reject` output). Document; revisit if production .item samples need split.

3. **Iterate component's own outputs declaration.**
   - What we know: tFileList and tFlowToIterate emit ITERATE-typed flow + REJECT (when accumulated).
   - What's unclear: Should the engine component's `outputs` config include both `iterate_flow_name` and `reject_flow_name`?
   - Recommendation: Yes -- the converter writes both into `outputs: ["iter_flow_name", "reject_flow_name"]`. Engine validates in plan-phase. Confirm against converter output in 10-05 test.

---

## 16. Validation Architecture Quick Reference

> Already covered in Section 12. Summary inline for the planner:

- Test framework: pytest (no install needed).
- Sampling: per-task quick run (~5s), per-wave full unit suite (~30s), phase-gate full incl. `@pytest.mark.java` (longer; requires JAR).
- Wave 0 gap list in Section 12.4 -- planner translates each into a test-creation task.
- TEST-06 (Talend output golden-file) is OUT OF SCOPE for Phase 10; deferred to Phase 12.

---

## Sources

### Primary (HIGH confidence)
- `/Users/aarun/Workspace/Projects/dataprep/.planning/phases/10-iterate-support/10-CONTEXT.md` -- All A-K user decisions
- `/Users/aarun/Workspace/Projects/dataprep/src/v1/engine/base_iterate_component.py` -- Existing skeleton with bug at line 150
- `/Users/aarun/Workspace/Projects/dataprep/src/v1/engine/base_component.py:204-275, 1336-1346` -- Template method, reset
- `/Users/aarun/Workspace/Projects/dataprep/src/v1/engine/executor.py:85-167, 173-243` -- execute_job + _execute_subjob
- `/Users/aarun/Workspace/Projects/dataprep/src/v1/engine/execution_plan.py:111-191, 392-404` -- ExecutionPlan constructor + get_subjob_plan
- `/Users/aarun/Workspace/Projects/dataprep/src/v1/engine/output_router.py:22-30, 197-263` -- Flow type map, clear_subjob_flows
- `/Users/aarun/Workspace/Projects/dataprep/src/v1/engine/engine.py:120` -- inputs/outputs wiring
- `/Users/aarun/Workspace/Projects/dataprep/src/v1/engine/component_registry.py:29-55` -- decorator pattern
- `/Users/aarun/Workspace/Projects/dataprep/src/v1/engine/components/file/file_exist.py` -- already-Green reference
- `/Users/aarun/Workspace/Projects/dataprep/src/converters/talend_to_v1/components/base.py:36-42` -- TalendConnection dataclass
- `/Users/aarun/Workspace/Projects/dataprep/src/converters/talend_to_v1/xml_parser.py:238-273` -- _parse_connections
- `/Users/aarun/Workspace/Projects/dataprep/src/converters/talend_to_v1/converter.py:27-30, 220-239` -- flow connector types, _parse_flows
- `/Users/aarun/Workspace/Projects/dataprep/tests/v1/engine/conftest.py` -- StubComponent + java_bridge fixture
- `/Users/aarun/Workspace/Projects/dataprep/tests/talend_xml_samples/Job_tFileList_0.1.item:276-278` -- ITERATE connection ENABLE_PARALLEL XML
- `/Users/aarun/Workspace/Projects/dataprep/tests/talend_xml_samples/Job_tFlowToIterate_0.1.item:341-343` -- ITERATE connection ENABLE_PARALLEL XML
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/.../tFileList/tFileList_end.javajet` -- ERROR=true RuntimeException pattern (fetched 2026-05-05)
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/.../tFlowToIterate/tFlowToIterate_end.javajet` -- NB_LINE finalization (fetched 2026-05-05)
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/.../tForeach/tForeach_java.xml` -- forward reference (fetched 2026-05-05)

### Secondary (MEDIUM confidence)
- pandas 3.0.1 detected via `python3 -c "import pandas; print(pandas.__version__)"` runtime probe.
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` -- gold-standard structure (file head verified).

### Tertiary (LOW confidence)
- None used.

---

## Metadata

**Confidence breakdown:**
- Existing code references: HIGH -- every file:line cited was read in this session.
- Body BFS algorithm: HIGH -- algorithm derived from explicit D-B1 spec; pseudocode mirrors existing topological-sort + BFS infrastructure in ExecutionPlan.
- Iterate loop pseudocode: HIGH -- maps directly to existing `_execute_subjob`; only the new `_execute_subjob_plan` extraction is a refactor (no behavior change).
- REJECT accumulation: MEDIUM -- design is sound but `drain_reject_flows` is a new helper; integration test in 10-07 will validate.
- Talaxie .javajet findings: HIGH -- fetched directly from upstream master branch.
- Pandas iteration patterns: HIGH -- industry-standard tradeoff analysis.
- Converter changes: HIGH -- exact insertion points identified.
- Risks: HIGH -- enumerated from code reading and CONTEXT.md.
- Test strategy: HIGH -- existing fixtures inspected; new fixtures designed against existing conftest patterns.

**Research date:** 2026-05-05
**Valid until:** 2026-06-05 (30 days; engine internals are stable, Talaxie source is master-branch ref but unlikely to change for these legacy components)

## RESEARCH COMPLETE
