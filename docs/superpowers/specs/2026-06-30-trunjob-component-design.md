# tRunJob Engine Component -- Design Spec

- Date: 2026-06-30
- Status: Approved (design) -- pending spec review
- Branch: feature/sync_repo_latest
- Author: brainstormed with Claude
- Scope: ONE engine component (tRunJob) + one supporting service + small additive engine changes

ASCII only (project logging/source/doc rule). All file:line citations were verified against the
real code by a parallel verification pass before this spec was written.

---

## 1. Summary

tRunJob lets a parent ETL job run ANOTHER whole job (a child job) to completion from inside a
component, then continue. It is the only component that re-enters the engine: every other component
transforms a DataFrame, while tRunJob loads and executes a separate job config.

The converter for tRunJob already exists and is frozen (`src/converters/talend_to_v1/components/
control/run_job.py`, 22 config keys), with an explicit `needs_review` marker: "No concrete engine
implementation for tRunJob." This spec fills that engine-side gap against the frozen config contract.

In the target production jobs, tRunJob is used for pure orchestration: a child job pre-validates or
enriches input and writes its result to an intermediate FILE or DB TABLE; the parent job then reads
that file/table with its own normal components, sequenced after tRunJob via OnSubjobOk/OnComponentOk.
The child-to-parent handoff is via file/DB, never via in-memory rows.

## 2. Goals / Non-goals

Goals (v1):
- Resolve a child job by name and run it in-process to completion before the parent continues.
- Pass context from parent to child (whole-context transmit + explicit per-variable overrides).
- Propagate child success/failure as a return code; optionally kill the parent on child failure.
- Be safe under recursion (cycle detection, max nesting depth) and under iteration (run per item).

Non-goals (v1, explicitly deferred):
- In-memory child-to-parent row propagation (`propagate_child_result` / tBufferOutput). OUT.
- Dynamic job selection (`use_dynamic_job` / `context_job`) and dynamic/file-loaded child context
  (`use_dynamic_context` / `dynamic_context` / `load_context_from_file`). Hard "not supported" error.
- Running the child in a separate OS process (`use_independent_process`) and any JVM/classpath
  settings. Consume-and-ignore (these are JVM concepts with no meaning in the Python engine).
- Arbitrary Java expressions inside `context_params` rows. v1 supports literals, context refs, and
  `globalMap.get("X")` only.

## 3. Constraints honored

- Converter JSON is FROZEN: tRunJob's engine class consumes the existing config keys; no
  re-conversion required. Engine resolution config lives in `engine_config` (engine-only), not in the
  component config.
- Engine component pattern: subclass `BaseComponent`, implement `_validate_config()` + `_process()`,
  register via decorator under both the Talend name and a V1 alias.
- ASCII-only logging with the `[{self.id}]` prefix. Custom `ETLError` exception hierarchy only.
- Fix-the-source, fail-loud: unsupported features raise a clear error, never silently do the wrong job.

---

## 4. Architecture

tRunJob stays a thin `BaseComponent`. The "run another job" mechanics live in a new service,
`ChildJobRunner`, so resolution + recursion + context seeding are unit-testable without the full
engine.

```
Parent ETLEngine
  - Executor calls RunJob.execute(None)              [tRunJob is a normal BaseComponent]
       - RunJob._process():
             - overrides = self._build_context_overrides()
             - result = self.child_job_runner.run(process, overrides, context_name)
             - write {id}_CHILD_RETURN_CODE (and {id}_CHILD_EXCEPTION_STACKTRACE on failure)
             - if result.return_code != 0 and die_on_child_error: raise (kills parent)
             - return {"main": None, "reject": None}

  ChildJobRunner.run(process_name, overrides, context_name):
       1. resolve  <base_dir>/<process_name>.json   (RunContext-aware)
       2. cycle check (process_name in call_stack -> error) + depth check (new depth > max -> error)
       3. with ETLEngine(child_path, _run_context=child_ctx) as child:
              seed child context (typed)  ->  stats = child.execute()
       4. map stats.status -> ChildResult(status, return_code, stacktrace)
```

### 4.1 New file: `src/v1/engine/child_job_runner.py`

- `RunContext` (dataclass): `base_dir: str`, `jobs_dir: Optional[str]`, `call_stack: list[str]`,
  `depth: int`, `max_depth: int`.
- `ChildResult` (dataclass): `status: str`, `return_code: int`, `stacktrace: Optional[str]`.
- `ChildJobRunner`: holds a `RunContext`; method `run(process_name, overrides, context_name) ->
  ChildResult`. Responsible for path resolution, cycle/depth guards, building the nested
  `ETLEngine`, typed context seeding, executing, and mapping the result.

### 4.2 Engine changes (3, additive and backward-compatible)

Verified facts: the source path is currently discarded (`engine.py:33-40`); service handles are
attached to each component instance at `engine.py:182-201`; there is no existing job registry /
child loader / engine factory / call-stack anywhere in `src/v1/engine/`.

1. Store the source directory. Capture the path before `open()` at `engine.py:36-38`; store
   `self._job_dir = os.path.dirname(path)` (and `None` when constructed from an in-memory dict).
2. Add an optional ctor param `_run_context: Optional[RunContext] = None` to `ETLEngine.__init__`
   (`engine.py:33`). When None (root run), the engine builds a root `RunContext`
   (`base_dir=self._job_dir`, `jobs_dir=engine_config.get("jobs_dir")`, `call_stack=[job_name]`,
   `depth=0`, `max_depth=engine_config.get("max_run_job_depth", 2)`). When provided (nested run),
   it uses it verbatim. The engine builds one `ChildJobRunner(run_context)` and injects it.
3. Inject `component.child_job_runner` in `_initialize_components()` at `engine.py:182-201`, using
   the same truthiness-guarded attribute-set pattern as `component.java_bridge` (`engine.py:195`).

`__exit__` already exists and returns False (propagates exceptions) -- do NOT add or change it
(`engine.py:302-309`). The `with ETLEngine(child) as c: c.execute()` pattern double-cleans, which is
idempotent (guarded in `java_bridge_manager.py:119-130`, `bridge.py:386-389`).

---

## 5. The component: `src/v1/engine/components/control/run_job.py`

Registered `@REGISTRY.register("RunJob", "tRunJob")`. The converter emits `"type": "tRunJob"`
(`run_job.py:162-167` -> `base.py:245-254`); engine resolution is exact-string `REGISTRY.get(type)`
(`engine.py:170-171`), so registration MUST include the literal `"tRunJob"`.

`_validate_config()` (runs on UN-resolved config, every execute):
- raise `ConfigurationError("[id] ...")` if `use_dynamic_job` or `use_dynamic_context` is true.
- raise `ConfigurationError("[id] ...")` if `process` is empty.
- WARN once (ASCII) if any consume-and-ignore key is set to a non-default value.

`_process(input_data=None) -> dict`:
1. `runner = getattr(self, "child_job_runner", None)`; if None -> `ConfigurationError`.
2. Build the two PARENT-side context inputs (Section 6): `whole_context` (the parent's current
   context as a `name -> value` dict, or `{}` if `transmit_whole_context` is false) and
   `param_overrides` (the resolved `context_params` as a `name -> value` dict).
3. `result = runner.run(process=self.config["process"], whole_context=whole_context,
   param_overrides=param_overrides, context_name=self.config.get("context_name", "Default"))`.
4. Persist to the PARENT globalMap BEFORE any raise (verified: the base class's post-`_process`
   stats/globalMap steps at `base_component.py:252-254` are skipped after a raise, so writes must be
   explicit here, mirroring tDie at `die.py:122-125`):
   - `self.global_map.put(f"{self.id}_CHILD_RETURN_CODE", int(result.return_code))`
   - if `result.stacktrace`: `self.global_map.put(f"{self.id}_CHILD_EXCEPTION_STACKTRACE", result.stacktrace)`
5. If `result.return_code != 0` and `self.config.get("die_on_child_error", True)`:
   ```python
   err = ComponentExecutionError(self.id, f"child job '{process}' failed (rc={result.return_code})")
   err.exit_code = result.return_code     # dynamic attr set AFTER construction (NOT a ctor arg)
   raise err
   ```
   This is the verified parent-kill path: `ComponentExecutionError` (`exceptions.py:24-30`), with a
   post-set `exit_code` (precedent `die.py:127-132`); the Executor reads `exit_code` off the
   exception / `.cause` / `__cause__` (`executor.py:744-750`) and sets `_job_terminated`
   (`executor.py:751`). A `ConfigurationError` would be re-raised unwrapped without `exit_code`
   (`base_component.py:268-270`) and register as a non-fatal "failed" -- so it MUST be
   `ComponentExecutionError`.
6. Else return `{"main": None, "reject": None}` (no data flow; like tPrejob/tPostjob).

---

## 6. Context seeding and precedence

Responsibility split: the COMPONENT supplies parent-side values (it owns the parent
`context_manager` and `global_map`); the RUNNER owns the child-aware merge (it builds the child
engine, so it knows the child's variable names and declared types). The component passes two dicts --
`whole_context` (parent current values, or `{}` when `transmit_whole_context` is false) and
`param_overrides` (resolved `context_params`). The runner then applies them onto the freshly-built
child engine WITH TYPE COERCION, only for names the child defines, params last (so params win):

```python
ctx = self.config.get("context_name", "Default")             # active child context name
declared = child.job_config.get("context", {}).get(ctx, {})  # {name: {value, type}}
for source in (whole_context, param_overrides):              # param_overrides applied last
    for name, value in source.items():
        if name in declared:                                 # skip vars the child does not define
            child.context_manager.set(name, value, declared[name].get("type"))  # coercing setter
```

Verified: the ETLEngine wrapper `set_context_variable(name, value)` does NOT coerce
(`engine.py:271-277`); the coercing setter is `ContextManager.set(key, value, value_type=None)`
(`context_manager.py:178`) which only coerces when `value_type` is passed and creates-or-overrides
(no existence check). Supported type tokens: `id_String/Integer/Long/Short/Byte/Float/Double/Boolean/
Character/Date/BigDecimal/Object` plus python `str/int/float/bool/Decimal/datetime/object`
(`context_manager.py:75-101`). Only `id_Date` parses dates.

Precedence (last wins): child defaults < `transmit_whole_context` < `context_params`.
- child defaults: from the child JSON `context` block (built by the child ETLEngine's ContextManager).
- `transmit_whole_context` (if true): overlay the parent's CURRENT context values onto the child,
  matching by name; vars the child does not define are skipped. Talend-parity confirmed: ON = child
  receives the parent's current runtime values.
- `context_params`: explicit per-variable overrides.

`context_params` value resolution (in the PARENT scope):
- literals -> as-is.
- `context.X` / `${context.X}` -> already substituted by `BaseComponent.execute()` step 3 BEFORE
  `_process` (verified: `resolve_dict` recurses lists, `context_manager.py:281-288`; so
  `config["context_params"][i]["param_value"]` arrives pre-resolved). Note substitution stringifies;
  for a typed parent value read `self.context_manager.get(name)`.
- `globalMap.get("KEY")` and `((Type)globalMap.get("KEY"))` -> tRunJob resolves these ITSELF from
  `self.global_map` (verified: the context system never touches globalMap). A small regex extracts
  KEY (tolerating a Java cast wrapper) and reads `self.global_map.get(KEY)`.

Note on `context_name`: it selects the child's active context. v1 honors it where the child defines
that context; otherwise the child's own `default_context` is used. The explicit overrides above are
layered regardless, so the variables that matter are always set. (Active-context switching in the
child engine is a minor enhancement if needed.)

---

## 7. Error model and return codes

Verified: `ETLEngine.execute()` RETURNS a status dict; it does NOT raise for child failure or tDie.
tRunJob inspects the returned `status`, it does not wrap `child.execute()` in a try/except expecting
an exception (the only raised case is the rare "engine itself raised" shape).

Return dict (success): `{status:"success", execution_time, components_executed, components_failed,
component_stats, job_name, global_map}` (`executor.py:180-186` + `engine.py:249-255`).

Mapping `child status -> CHILD_RETURN_CODE`:

| Child outcome | execute() return | return_code |
|---|---|---|
| success | status == "success" | 0 |
| tDie terminated | status == "error" (has global_map) | tDie exit code if surfaced, else -1 |
| component failed | status == "failed" | -1 |
| engine itself raised | exception (has `error` key, no `global_map`) | -1, capture stacktrace |

"Child failed" (for `die_on_child_error`) = `return_code != 0` (i.e. status != "success" or a raised
exception). Talend parity: success = 0; child tDie = its exit code; any other child failure = -1.

`die_on_child_error`:
- true (converter default): raise `ComponentExecutionError` with `.exit_code` -> kills the parent job.
- false: keep the non-zero `CHILD_RETURN_CODE`, mark tRunJob successful, let the parent continue so a
  downstream RunIf can branch on `globalMap.get("tRunJob_1_CHILD_RETURN_CODE")`.

Open implementation detail (small): surfacing the EXACT child tDie exit code (vs a flat -1) may
require the child Executor to expose its captured `exit_code`. v1 may ship -1 for all failures; the
target jobs run `die_on_child_error=true`, where success/fail (not the precise code) is what matters.

---

## 8. globalMap writeback and isolation

- The child gets a fresh, isolated `GlobalMap` (verified per-engine instance, `engine.py:122`); its
  counters/vars do NOT leak into the parent.
- tRunJob writes exactly two keys into the PARENT globalMap: `{id}_CHILD_RETURN_CODE` (int) and, on
  failure, `{id}_CHILD_EXCEPTION_STACKTRACE` (str). Use plain `GlobalMap.put(key, value)`
  (`global_map.py:21-24`); read with `get(key, default)` (`global_map.py:26-28`).
- `CHILD_EXCEPTION_STACKTRACE` is a DataPrep extension (Talend surfaces the stacktrace via the
  tRunJob output schema, not globalMap). Documented as non-parity; harmless.

Reference (for the iterate-per-file pattern): tFileList publishes, per item, BEFORE the body runs
(`file_list.py:375-379`, set at `executor.py:468` before body at `:513`), each `{id}_`-prefixed:
`CURRENT_FILE` (filename), `CURRENT_FILEPATH`, `CURRENT_FILEDIRECTORY`, `CURRENT_FILEEXTENSION`
(no leading dot), `NB_FILE` (1-based), plus the iterate base `{id}_CURRENT_ITERATION`. There is NO
`CURRENT_FILENAME` key; a `context_param` must reference e.g.
`globalMap.get("tFileList_1_CURRENT_FILEPATH")`.

---

## 9. Recursion and iteration safety

- Cycle: if `process_name` is already in `call_stack`, raise `ConfigurationError("[id] cycle detected:
  A -> B -> A")`.
- Depth: `max_depth = 2` default (overridable via `engine_config.max_run_job_depth`). Counting: root
  job depth 0, child depth 1, grandchild depth 2. Block when the new child's depth would exceed
  `max_depth` (so parent -> child -> grandchild is allowed; deeper is a hard error).
- Each nested child is a fresh `ETLEngine` -> its own JVM (own ephemeral port via
  `socket.bind(('',0))`, `java_bridge_manager.py:140-151`) and own DB connections. At depth 2 with
  sequential children, at most parent + 1 child JVM coexist.
- Under iteration (tFileList -> iterate -> tRunJob): the Executor calls a body component's `execute()`
  once per item (`_execute_iterate_body`, `executor.py:407+`), with config deep-copied + re-resolved
  fresh each call, AFTER the iteration globalMap keys are set. So tRunJob picks up per-iteration
  `globalMap.get(...)` values automatically; no special handling needed.

---

## 10. Config key handling (all 22 frozen keys)

- Honored: `process`, `context_name`, `transmit_whole_context`, `context_params`, `die_on_child_error`.
- Consume-and-ignore (WARN once if non-default): `use_independent_process`, `print_parameter`,
  `propagate_child_result`, `transmit_original_context` (not a real Talend UI toggle -- internal
  codegen flag), `use_child_jvm_setting`, `use_custom_jvm_setting`, `jvm_arguments`,
  `use_extra_classpath`, `extra_classpath`, `load_context_from_file`, `tstatcatcher_stats`, `label`.
- Hard "not supported" error: `use_dynamic_job` / `context_job`, `use_dynamic_context` /
  `dynamic_context`.

---

## 11. Testing strategy

- Converter: `run_job.py` converter already exists and passes; confirm coverage and DROP its
  `engine_gap` needs_review entry now the gap is closed (advisory metadata only, not frozen config).
- Engine component unit: `tests/v1/engine/components/control/test_run_job.py`
  - registration under both "RunJob" and "tRunJob";
  - success path -> `CHILD_RETURN_CODE == 0`, returns `{"main": None, "reject": None}`;
  - die-on-error: child fails -> raises `ComponentExecutionError` with `.exit_code` set;
  - die-off: child fails -> non-zero `CHILD_RETURN_CODE`, tRunJob marked OK, no raise;
  - context precedence (defaults < whole-context < context_params) + typed coercion;
  - `globalMap.get("KEY")` and `((Type)globalMap.get("KEY"))` resolution in context_params;
  - `_validate_config` rejects `use_dynamic_job` / empty `process`.
- Service unit: `tests/v1/engine/test_child_job_runner.py` -- resolution by filename, missing-file
  error, cycle error, depth-2 limit, typed coercion -- using tiny fixture child JSONs in `tmp_path`.
- End-to-end: `tests/fixtures/jobs/control/` -- a parent JSON whose tRunJob runs a child that writes
  a file, then the parent reads it back; assert `status == "success"` (the real production pattern).
- No `@pytest.mark.java` required: tRunJob does not resolve `{{java}}` or touch the bridge directly.
- Coverage: new modules (`run_job.py`, `child_job_runner.py`) must clear the 95% per-module floor.

---

## 12. Files to create / change

Create:
- `src/v1/engine/child_job_runner.py` (RunContext, ChildResult, ChildJobRunner)
- `src/v1/engine/components/control/run_job.py` (RunJob component)
- `tests/v1/engine/components/control/test_run_job.py`
- `tests/v1/engine/test_child_job_runner.py`
- `tests/fixtures/jobs/control/` parent + child fixture JSONs

Change:
- `src/v1/engine/components/control/__init__.py` -- import RunJob so the decorator fires
- `src/v1/engine/engine.py` -- 3 additive changes (store `_job_dir`; optional `_run_context` ctor
  param + build root RunContext + ChildJobRunner; inject `component.child_job_runner`)
- `src/converters/talend_to_v1/components/control/run_job.py` -- optional: drop the `engine_gap`
  needs_review now the engine implementation exists

---

## 13. Known v1 parity gaps (documented, not silent)

- Arbitrary-Java `context_params` rows unsupported (literals + context refs + `globalMap.get` only).
- Exact child tDie exit-code passthrough may ship as flat -1 first.
- `CHILD_EXCEPTION_STACKTRACE` via globalMap is a DataPrep extension, not Talend behavior.
- Dynamic job, dynamic/file-loaded context, independent-process, and JVM settings unsupported.
- `context_name` active-context switching in the child is best-effort.
