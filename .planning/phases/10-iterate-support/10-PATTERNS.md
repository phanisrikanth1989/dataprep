# Phase 10: Iterate Support - Pattern Map

**Mapped:** 2026-05-05
**Files analyzed:** 11 (5 new, 6 modified)
**Analogs found:** 11 / 11

Every new file Phase 10 creates has a strong analog in the existing tree. The most important
discovery is that the codebase has a written gold-standard
(`docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` + `ENGINE_TEST_PATTERN.md`) which IS the
contract. Below maps that contract onto the specific Phase 10 files plus engine-infra deltas.

---

## 1. Component File Analogs

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `src/v1/engine/components/iterate/__init__.py` | package registration | side-effect import | `src/v1/engine/components/file/__init__.py` | exact (utility-style package) |
| `src/v1/engine/components/iterate/flow_to_iterate.py` | iterate component, consumes input flow | request-response (DataFrame in, iterations out) | `src/v1/engine/components/file/file_exist.py` (trigger-only output shape) + `src/v1/engine/base_iterate_component.py` (parent class) | role-match (extends BaseIterateComponent, not BaseComponent) |
| `src/v1/engine/components/file/file_list.py` | iterate component, source (no input flow) | file-I/O + iteration | `src/v1/engine/components/file/file_exist.py` (path-resolution + globalMap puts) + `src/v1/engine/components/file/file_input_delimited.py` (file existence check + FileOperationError pattern) | role-match (extends BaseIterateComponent, not BaseComponent; no DataFrame output) |
| `src/v1/engine/base_iterate_component.py` (MODIFY) | abstract base | hooks + lifecycle | itself + `src/v1/engine/base_component.py` (template-method shape) | self (extending) |
| `src/v1/engine/executor.py` (ADD `_execute_iterate_body`) | execution method | nested subjob loop | existing `_execute_subjob` in same file (lines 173-243) | exact (same building blocks) |
| `src/v1/engine/execution_plan.py` (ADD body BFS, nested-iterate detection) | post-build graph step | BFS over edges | existing `_auto_detect_subjobs` (lines 196-234, BFS) + existing `validate` (lines 314-348, reachability BFS) | exact (BFS already in file) |
| `src/v1/engine/output_router.py` (ADD `drain_reject_flows` / partial-subjob clear) | flow-cleanup helper | mutates `_data_flows` | existing `clear_subjob_flows` (lines 207-262) | exact (drop-in cousin) |
| `src/converters/talend_to_v1/converter.py` (ADD `ENABLE_PARALLEL` extraction) | converter post-process | parsing connection params | existing `_parse_flows` (lines 219-239) | role-match (same flow-iteration site) |

---

## 2. Test File Analogs

| New Test File | Closest Analog | Why |
|---------------|----------------|-----|
| `tests/v1/engine/components/iterate/test_flow_to_iterate.py` | `tests/v1/engine/components/file/test_file_exist.py` | Same test scaffold (`_make_component` helper, registration test, validate-config tests, globalMap-vars tests, statistics tests). Use `pd.DataFrame` inputs instead of `tmp_path`. |
| `tests/v1/engine/components/file/test_file_list.py` | `tests/v1/engine/components/file/test_file_exist.py` | Same scaffold. Add `tmp_path`-driven fixtures for directory walking, glob/regex, sort, ERROR=true/false-with-zero-matches. |
| `tests/v1/engine/test_executor_iterate.py` | `tests/v1/engine/conftest.py::StubComponent` + any existing `tests/v1/engine/test_executor*.py` | Use `StubComponent` for body components per D-17. Mark Java-touching tests with `@pytest.mark.java` and request the session-scoped `java_bridge` fixture. |
| `tests/v1/engine/test_execution_plan_iterate.py` | existing `tests/v1/engine/test_execution_plan*.py` (same module) | Pure data-structure tests; no fixtures beyond raw config dicts. |
| `tests/v1/engine/test_output_router_iterate.py` | existing `tests/v1/engine/test_output_router*.py` | Reuse the same dict-config style. |
| `tests/converters/talend_to_v1/test_enable_parallel.py` | existing converter tests under `tests/converters/talend_to_v1/` | Same `convert_job` pattern; assert needs_review entry shape. |

---

## 3. Engine Infrastructure Analogs

### 3a. `Executor._execute_iterate_body(iterate_component, body_subjob_plan)`

**Analog:** `Executor._execute_subjob` (`src/v1/engine/executor.py:173-243`).

Copy the structure, replace the for-loop body with a per-iteration hook + body-component
loop. Reuse:

- `self._execute_component(comp_id)` per body component (line 205)
- `self.output_router.are_inputs_ready(comp_id)` safety net (line 195)
- `self._fire_component_triggers(comp_id, comp_result)` per body component (line 229)
- `self.output_router.clear_subjob_flows(...)` between iterations (line 236-238) -- but
  scoped to body components, hence the new `drain_reject_flows` / partial helper (Section 3c).
- `self._job_terminated` check (lines 121, 231) -- breaks out of iterate loop
- `BaseComponent.reset()` on every body component between iterations (D-I1)
- Remove `body_id` from `self.executed_components` set between iterations so re-execution
  is permitted (D-B3). This is the only NEW wiring this method adds.

**Skeleton to copy from `_execute_subjob` (lines 173-243):**

```python
def _execute_subjob(self, subjob_id: str) -> str:
    subjob_plan = self.execution_plan.get_subjob_plan(subjob_id)
    subjob_failed = False

    for comp_id in subjob_plan.component_ids:
        if comp_id not in self.components:
            logger.warning("Component %s not in components dict, skipping", comp_id)
            continue

        if not self.output_router.are_inputs_ready(comp_id):
            component = self.components[comp_id]
            if component.inputs:
                logger.warning("...inputs not ready...skipping", comp_id)
                continue

        comp_result = self._execute_component(comp_id)
        if comp_result == "error":
            component = self.components[comp_id]
            if component.die_on_error:
                # Mark remaining as skipped, break
                ...
                break
            else:
                subjob_failed = True
        self._fire_component_triggers(comp_id, comp_result)
        if self._job_terminated:
            return "error"

    self.output_router.clear_subjob_flows(
        subjob_plan.component_set, self.executed_components
    )
    self._executed_subjobs.add(subjob_id)
    return "error" if subjob_failed else "success"
```

The iterate-body version wraps this in: `prepare()` -> outer `for item in iter:` ->
`before_iteration` / `set_iteration_globalmap` hooks -> body-loop (above pattern) ->
`after_iteration` -> per-iter `output_router.drain_reject_flows + reset` -> `finalize()`.

### 3b. `ExecutionPlan` body-subgraph BFS + nested-iterate check

**Analog (BFS skeleton):** `ExecutionPlan._auto_detect_subjobs` (lines 196-234) and
`ExecutionPlan.validate` (lines 314-348).

Both already use `collections.deque` BFS over the flow / trigger graph. Body BFS is the
same shape, but seeded at the iterate edge target and expanded through BOTH FLOW edges and
trigger edges.

**Skeleton to copy from `_auto_detect_subjobs` (lines 213-228):**

```python
visited: set[str] = set()
group: list[str] = []
queue: deque[str] = deque([comp_id])

while queue:
    current = queue.popleft()
    if current in visited:
        continue
    visited.add(current)
    group.append(current)

    for flow in self._flows:
        if flow.get("from") == current and flow.get("to") not in visited:
            queue.append(flow["to"])
        elif flow.get("to") == current and flow.get("from") not in visited:
            queue.append(flow["from"])
```

For body BFS the seed is the iterate connection's target component, expansion follows ONLY
outgoing FLOW edges + outgoing trigger edges (NOT bidirectional). Stop conditions per D-B1.

**Nested-iterate detection (D-B4):** after building each body subgraph, check whether any
component in the subgraph has `is_iterate_component=True` (look up the registered class via
`REGISTRY.get(comp_type)` and inspect the class attribute). If so, raise
`ConfigurationError` listing both iterate IDs. The error format pattern lives in the same
file at `validate()` (lines 343-348):

```python
raise ConfigurationError(
    f"Unreachable subjobs detected: {sorted(unreachable)}. "
    f"These subjobs have no trigger path from any initial subjob "
    f"and are not RunIf targets."
)
```

Use the same shape: name the offending iterates, explain the limitation.

### 3c. `OutputRouter` partial-subjob clear / `drain_reject_flows`

**Analog:** `OutputRouter.clear_subjob_flows` (`src/v1/engine/output_router.py:207-262`).

Two helpers needed:

1. **`clear_partial_subjob_flows(body_component_ids, executed_components)`** -- exactly like
   `clear_subjob_flows` but parameterized on a SUBSET of subjob components (body only).
   Reuse the cross-subjob preservation logic verbatim (lines 240-258).
2. **`drain_reject_flows(body_component_ids) -> dict[str, pd.DataFrame]`** -- pull each body
   component's outgoing reject-typed flow data into a returned dict, then clear those flows.
   Iterate caller concatenates these into the iterate-component reject output (D-D4).

Existing `_FLOW_TYPE_TO_RESULT_KEY` (lines 22-29) already maps `"reject" -> "reject"`; use
`self._outgoing[comp_id]` filtered on `flow["type"] == "reject"` to find reject flows
emanating from body components.

### 3d. Converter `ENABLE_PARALLEL` extraction (D-J3)

**Analog:** `_parse_flows` (`src/converters/talend_to_v1/converter.py:219-239`).

This is the spot that already iterates `connections` and writes flow dicts. Extend it (or
add a sibling helper called from the same site) to:

- Detect `conn.connector_type == "ITERATE"`
- Read `ENABLE_PARALLEL` and `NUMBER_PARALLEL` element parameters from `conn` (the
  `TalendConnection` dataclass already exposes connection params; planner verifies exact
  attribute name)
- Write into the flow dict: `{type: 'iterate', enable_parallel: bool, number_parallel: int}`
- If `ENABLE_PARALLEL=true`, append a `needs_review` entry with severity `engine_gap`

The existing flow-dict shape (lines 232-237) is the literal copy target:

```python
flows.append({
    "name": conn.name or conn.source,
    "from": conn.source,
    "to": conn.target,
    "type": conn.connector_type.lower(),
})
```

Just add two more keys when type is `iterate`.

---

## 4. Decorator and Registration Patterns

### 4a. `@REGISTRY.register(...)` -- multi-alias contract

**Source:** `src/v1/engine/component_registry.py:29-55` and existing component usage.

```python
# src/v1/engine/components/file/file_exist.py:31
@REGISTRY.register("FileExistComponent", "FileExist", "tFileExist")
class FileExistComponent(BaseComponent):
    ...
```

```python
# src/v1/engine/components/file/file_input_delimited.py:76
@REGISTRY.register("FileInputDelimited", "tFileInputDelimited")
class FileInputDelimited(BaseComponent):
    ...
```

**Convention for Phase 10:**

```python
# src/v1/engine/components/iterate/flow_to_iterate.py
@REGISTRY.register("FlowToIterate", "tFlowToIterate")
class FlowToIterate(BaseIterateComponent):
    ...

# src/v1/engine/components/file/file_list.py
@REGISTRY.register("FileList", "tFileList")
class FileList(BaseIterateComponent):
    ...
```

PascalCase canonical name first, Talend `t`-prefixed alias second. Three-name registration
(like `FileExistComponent`) is only used when there is a legacy class-name back-compat
need; prefer two names for new components.

### 4b. Package `__init__.py` registration trigger

**Source:** `src/v1/engine/components/file/__init__.py` (full file, 52 lines) -- import every
module to fire the decorator + populate `__all__`.

```python
# src/v1/engine/components/file/__init__.py:6-7
from .file_exist import FileExistComponent
from .file_input_delimited import FileInputDelimited
...
__all__ = [
    'FileExistComponent',
    'FileInputDelimited',
    ...
]
```

**For new `iterate/__init__.py`:**

```python
"""Iterate engine components (tFlowToIterate, tFileList lives in file/)."""
from .flow_to_iterate import FlowToIterate

__all__ = [
    'FlowToIterate',
]
```

`FileList` registers via `src/v1/engine/components/file/__init__.py` (existing file gets
one new import line + one new `__all__` entry, identical to the FileExist pattern).

The new `iterate` package must also be wired into the parent
`src/v1/engine/components/__init__.py` (planner verifies exact line) so it is imported at
engine startup.

---

## 5. Logging Patterns (ASCII-only)

### 5a. Module-level logger

**Source:** every component, e.g. `file_exist.py:28`, `file_input_delimited.py:49`.

```python
import logging
logger = logging.getLogger(__name__)
```

### 5b. INFO with `[{self.id}]` prefix

**Source:** `file_exist.py:74-94` (lifecycle events) and `file_input_delimited.py:149-152,
176-178` (warnings):

```python
# file_exist.py:74
logger.info("[%s] File existence check started: %s", self.id, file_path)

# file_exist.py:91-94
logger.info(
    "[%s] File existence check complete: %s '%s' exists=%s",
    self.id, check_type, file_path, file_exists,
)

# file_input_delimited.py:149-152
logger.warning(
    f"[{self.id}] {description} ('{flag}') is not yet "
    f"implemented. Config flag will be ignored."
)
```

**Both `%`-style and f-string-style coexist in engine code.** Per project conventions f-string
is engine-side norm; existing `file_exist.py` uses `%`-style. Either is acceptable; pick one
per file and stay consistent. Do NOT mix.

### 5c. ASCII-only enforcement (D-H7)

**Verified pattern:** `base_component.py:259-262` uses only ASCII colons and dashes:

```python
logger.info(
    f"[{self.id}] completed in {elapsed:.2f}s - "
    f"NB_LINE:{self.stats['NB_LINE']} OK:{self.stats['NB_LINE_OK']} "
    f"REJECT:{self.stats['NB_LINE_REJECT']}"
)
```

No emojis, no unicode arrows, no box-drawing. Phase 10 iterate logs (D-H1..H5) use the same
ASCII vocabulary: `|`, `:`, `--`, `/`, `<`, `>`. Stick to one separator style per format
string.

---

## 6. Method Ordering Conventions

### 6a. Component class layout (gold standard)

**Source:** `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` lines 11-117 + `file_exist.py`
+ `file_input_delimited.py`.

```python
"""Module docstring with full Config Mapping (Talend XML param -> v1 key)."""
import-block
logger = logging.getLogger(__name__)

# Module-level constants (UPPER_SNAKE_CASE for public, _UPPER for private)

@REGISTRY.register("Name", "tName")
class Name(BaseComponent):  # or BaseIterateComponent
    """Class docstring with Config keys: section."""

    # ------------------------------------------------------------------
    # Helpers (private, _resolve_xxx)         -- file_exist.py:42-51
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Lifecycle (or "Configuration Validation" / "Core Processing")
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        ...

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        ...

    # ------------------------------------------------------------------
    # Static Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _xxx(...) -> ...:
        ...
```

The ASCII separator banner (`# --- ... ---`) is a strong, repeated convention. Use it.

### 6b. Order: validate first, process second, helpers last

`file_exist.py` orders: `_resolve_file_path` (helper) -> `_validate_config` -> `_process`.
`file_input_delimited.py` and `aggregate_sorted_row.py` order:
`_validate_config` -> `_process` -> static helpers. Phase 10 should follow the latter
(validate -> process -> helpers) for consistency.

### 6c. Module docstring "Config keys consumed (N total)" block

**Source:** `file_input_delimited.py:1-33` (25 keys, exhaustive listing).

```
Config keys consumed (25 total):
  filepath           (str, required)          -- absolute file path
  fieldseparator     (str, default ";")       -- field delimiter character
  ...
```

Phase 10 components MUST have this block. tFileList = 17 keys (D-G1-G10), tFlowToIterate
= 2 keys + map_entries (D-F3, D-F4).

### 6d. globalMap variables block in module docstring

**Source:** `file_exist.py:11-14`.

```
GlobalMap variables (Talend parity):
    {id}_EXISTS    (bool)   - whether the path exists at check time
    {id}_FILENAME  (string) - resolved file path that was checked
```

Phase 10 mirrors this verbatim:

```
GlobalMap variables (Talend parity, per Talaxie tFileList_java.xml):
    {id}_CURRENT_FILE          (str)
    {id}_CURRENT_FILEPATH      (str)
    {id}_CURRENT_FILEDIRECTORY (str)
    {id}_CURRENT_FILEEXTENSION (str)
    {id}_NB_FILE               (int)
```

### 6e. Statistics block in module docstring

**Source:** `file_exist.py:15-19`.

```
Statistics:
    NB_LINE         = 1 (one existence check)
    NB_LINE_OK      = 1
    NB_LINE_REJECT  = 0
```

Phase 10 components describe iterate semantics (D-D1).

---

## 7. What Phase 10 New Files Must NOT Do

### 7a. tFlowToIterate / tFileList must extend `BaseIterateComponent`, NOT `BaseComponent`

**Why:** `BaseIterateComponent.__init__` sets `self.is_iterate_component = True` (line 58),
which is the flag `Executor._execute_subjob` will branch on (per D-B2). Subclassing
`BaseComponent` directly will silently make the executor treat the component as a regular
data component.

```python
# CORRECT
from ...base_iterate_component import BaseIterateComponent
class FlowToIterate(BaseIterateComponent):
    ...

# WRONG (defeats iterate detection)
from ...base_component import BaseComponent
class FlowToIterate(BaseComponent):
    ...
```

### 7b. Iterate components must NOT override `execute()` themselves

`BaseIterateComponent.execute()` (or its Phase-10-extended override) handles the lifecycle.
Subclasses implement only the abstract hooks (`_validate_config`, `prepare_iterations`,
`set_iteration_globalmap`, optionally `prepare`, `before_iteration`, `after_iteration`,
`finalize`, `should_stop`, `on_iteration_error`).

This is the same prohibition as `BaseComponent` Rule 4
(`docs/v1/standards/ENGINE_COMPONENT_PATTERN.md:163-176`).

### 7c. `_validate_config()` must NOT do content checks (Phase 7.1 Rule 12 / D-L4)

**Right reference:** `aggregate_sorted_row.py:54-80`. It only checks container types
(`isinstance(operations, list)`, `isinstance(op, dict)`), NOT whether values resolve to
something sensible.

```python
# CORRECT (structural only)
def _validate_config(self) -> None:
    operations = self.config.get("operations", [])
    if not isinstance(operations, list):
        raise ConfigurationError(
            f"[{self.id}] 'operations' must be a list, got {type(operations).__name__}"
        )

# WRONG (content check on unresolved value)
def _validate_config(self) -> None:
    if not pathlib.Path(self.config["directory"]).exists():  # NO -- value may be ${context.X}
        raise ConfigurationError(...)
```

For Phase 10:
- tFileList: `_validate_config` checks DIRECTORY key presence + LIST_MODE / GLOBEXPRESSIONS
  / CASE_SENSITIVE / SORT enum membership. Directory existence is a `_process()` concern.
- tFlowToIterate: `_validate_config` checks DEFAULT_MAP is bool, MAP is list-of-dicts,
  `self.inputs` is non-empty (this is structural, set at engine init from JSON, NOT a
  resolved value). Per-row column existence is a `_process()` concern.

### 7d. Read config in `_process()`, never in `__init__`

**Right reference:** `file_input_delimited.py:127-144` (all 18 reads happen in `_process`).
**Wrong reference:** ENGINE_COMPONENT_PATTERN.md Rule 5 (lines 178-191) explicitly forbids
`__init__`-time config reads.

### 7e. Iterate components emit NO data flow output

tFileList and tFlowToIterate produce iteration items only. The `_process()` return shape
should be `{"main": None, "reject": None}` (or a placeholder DataFrame matching the
"iteration produced" shape -- D-A2 says skip output schema validation entirely). Do NOT
return `{"main": pd.DataFrame(...)}` thinking the iteration source has a data flow.

For iterate components the "output" is the body subjob re-execution + globalMap variable
puts via `set_iteration_globalmap`. The new
`BaseIterateComponent.execute()` override (D-A2) skips the data-pipeline lifecycle steps
that don't apply (output schema validation, REJECT routing, batch/streaming dispatch).

### 7f. Output_router additions must not break cross-subjob preservation

`clear_subjob_flows` (lines 240-258) preserves flows that have unexecuted cross-subjob
consumers (D-16 safety). The new `clear_partial_subjob_flows` MUST replicate this guard --
removing it would silently corrupt cross-subjob data flow when an iterate's body emits to a
component outside the iterate scope.

### 7g. ENABLE_PARALLEL extraction must not change non-iterate flow shape

Existing flow dict keys (`name`, `from`, `to`, `type`) are consumed by ExecutionPlan,
OutputRouter, and downstream tooling. Adding `enable_parallel` / `number_parallel` MUST be
gated to `type == 'iterate'` -- never write those keys onto FLOW / FILTER / REJECT flows or
existing engine code paths see unexpected keys.

### 7h. Logging must stay ASCII (D-H7, project memory `feedback_ascii_logging`)

No emojis, no unicode arrows, no box-drawing. Verified clean reference: every existing log
line in the engine. Reviewers should grep PR diff for non-ASCII before merging.

---

## Shared Patterns

### Logger / module setup

**Source:** every component file (e.g., `file_exist.py:20-28`).
**Apply to:** every new file in Phase 10.

```python
import logging
from typing import Any, Dict, Optional

from ...base_component import BaseComponent          # or base_iterate_component
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)
```

### Error classes

**Source:** `src/v1/engine/exceptions.py` and `ENGINE_COMPONENT_PATTERN.md` lines 215-225.
**Apply to:** all new components.

| Phase 10 site | Exception |
|---------------|-----------|
| Missing config key | `ConfigurationError` |
| `inputs` empty for tFlowToIterate | `ConfigurationError` |
| Directory missing for tFileList ERROR=true | `FileOperationError` (or per D-G8 `ComponentExecutionError` with the Talend message format -- planner picks based on Talaxie) |
| 0 matches with ERROR=true | `ComponentExecutionError("No file found in directory: <dir>")` (D-G8 -- Talend RuntimeException parity) |
| Nested iterate detected | `ConfigurationError` (D-B4) |

NEVER raise generic `Exception`, `ValueError`, or `RuntimeError` (Rule 7).

### globalMap-guarded puts

**Source:** `file_exist.py:87-89` and `file_input_delimited.py:162-164`.
**Apply to:** every globalMap interaction in iterate components.

```python
if self.global_map:
    self.global_map.put(f"{self.id}_CURRENT_FILEPATH", str(path))
    self.global_map.put(f"{self.id}_NB_FILE", counter)
```

The guard is non-negotiable -- tests construct components without a `GlobalMap`.

### Test file scaffold

**Source:** `tests/v1/engine/components/file/test_file_exist.py` (full 127 lines).
**Apply to:** every new component test file.

Required test classes:
- `TestRegistration` -- assert `REGISTRY.get("Alias") is ComponentClass` for each registered name
- `TestValidateConfig` -- positive + negative cases
- `TestProcess<Behavior>` -- functional groups
- `TestGlobalMapVariables` -- assert each Talend-parity globalMap key is set
- `TestStatistics` -- assert NB_LINE / NB_LINE_OK / NB_LINE_REJECT shape

For iterate-specific behavior, also add:
- `TestPrepareIterations` -- iterator type, item count, item shape
- `TestSetIterationGlobalmap` -- per-item globalMap state
- `TestIterateLifecycle` -- prepare / before / after / finalize hook ordering (use a recording
  subclass)

Mark all unit tests `@pytest.mark.unit`. For executor + .item-driven integration tests use
the session-scoped `java_bridge` fixture from `tests/v1/engine/conftest.py` and
`@pytest.mark.java` (per D-L3 / Phase 5.1 lesson).

### `StubComponent` for executor / orchestration tests

**Source:** `tests/v1/engine/conftest.py:26-77`.
**Apply to:** Phase 10 executor iterate-loop tests, output_router partial-clear tests.

```python
def test_iterate_drains_body_rejects(stub_component_factory):
    body_comp = stub_component_factory(
        "body_1",
        config={"reject_data": [{"errorCode": "X", "errorMessage": "y"}]},
    )
    ...
```

Per D-17, do NOT roll a new fixture for body components when StubComponent suffices.

---

## No Analog Found

None. Every new file has a strong existing analog.

---

## Metadata

**Analog search scope:**
- `src/v1/engine/components/file/` (all)
- `src/v1/engine/components/transform/aggregate_sorted_row.py`
- `src/v1/engine/base_component.py`, `base_iterate_component.py`
- `src/v1/engine/executor.py`, `execution_plan.py`, `output_router.py`, `component_registry.py`
- `src/v1/engine/components/file/__init__.py` (package wiring)
- `tests/v1/engine/components/file/test_file_exist.py`
- `tests/v1/engine/conftest.py` (fixtures)
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md`, `ENGINE_TEST_PATTERN.md`
- `src/converters/talend_to_v1/converter.py:_parse_flows`

**Files scanned:** 14
**Pattern extraction date:** 2026-05-05

## PATTERNS COMPLETE
