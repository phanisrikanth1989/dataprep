# tRunJob Engine Component -- Design Spec

- Date: 2026-06-30
- Status: Reviewed (adversarial pass applied) -- pending user spec review
- Branch: feature/sync_repo_latest
- Author: brainstormed with Claude
- Scope: ONE engine component (tRunJob) + one supporting service + small additive engine changes

ASCII only (project logging/source/doc rule). All file:line citations were verified against the
real code by a parallel verification pass; the design then went through a 5-lens adversarial review
(22 findings, 15 survived independent refutation) whose corrections are folded in below.

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
             - whole_context, param_overrides = build parent-side context inputs
             - result = self.child_job_runner.run(process, whole_context, param_overrides, context_name)
             - write {id}_CHILD_RETURN_CODE (and {id}_CHILD_EXCEPTION_STACKTRACE on failure)
             - if result.return_code != 0 and die_on_child_error: raise (kills parent)
             - return {"main": None, "reject": None}

  ChildJobRunner.run(process_name, whole_context, param_overrides, context_name):
       1. resolve  <base_dir>/<process_name>.json  ->  resolved abspath (RunContext-aware)
       2. cycle check (resolved abspath in call_stack -> error) + depth check (new depth > max -> error)
       3. try:
              with ETLEngine(child_path, _run_context=child_ctx) as child:
                  seed child context (typed)  ->  stats = child.execute()
              map stats -> ChildResult(status, return_code, stacktrace)    # Section 7
          except Exception as e:                      # ctor / seeding / engine-raised failures
              return ChildResult("error", -1, format_stacktrace(e))        # Section 7.1
```

### 4.1 New file: `src/v1/engine/child_job_runner.py`

- `RunContext` (dataclass): `base_dir: str`, `jobs_dir: Optional[str]`, `call_stack: list[str]`,
  `depth: int`, `max_depth: int`.
- `ChildResult` (dataclass): `status: str`, `return_code: int`, `stacktrace: Optional[str]`.
- `ChildJobRunner`: holds a `RunContext`; method `run(process_name, whole_context, param_overrides,
  context_name) -> ChildResult` (two separate context dicts -- the runner owns the child-typed merge;
  see Section 6). Responsible for path resolution, cycle/depth guards, building the nested `ETLEngine`
  inside a try/except (Section 7.1), typed context seeding, executing, and mapping the result. The
  runner NEVER raises for child failures -- every failure (construction, seeding, run, tDie) becomes a
  `ChildResult` so the component's return-code/die model governs uniformly.

### 4.2 Engine changes (additive and backward-compatible)

Verified facts: the source path is currently discarded (`engine.py:33-40`); service handles are
attached to each component instance at `engine.py:182-201`; there is no existing job registry /
child loader / engine factory / call-stack anywhere in `src/v1/engine/`.

1. Store the source directory. Capture the path before `open()` at `engine.py:36-38`; store
   `self._job_dir = os.path.dirname(path)` (and `None` when constructed from an in-memory dict).
2. Add an optional ctor param `_run_context: Optional[RunContext] = None` to `ETLEngine.__init__`
   (`engine.py:33`). When None (root run), the engine builds a root `RunContext`
   (`base_dir=self._job_dir`, `jobs_dir=engine_config.get("jobs_dir")`,
   `call_stack=[resolved abspath of this job's own file, or job_name when dict-loaded]`, `depth=0`,
   `max_depth=engine_config.get("max_run_job_depth", 2)`). When provided (nested run), it uses it
   verbatim. The engine builds one `ChildJobRunner(run_context)` and injects it. Cycle detection keys
   on RESOLVED ABSOLUTE child-JSON paths, not job names (Section 9 / N2).
3. Inject `component.child_job_runner` in `_initialize_components()` at `engine.py:182-201`, using
   the same truthiness-guarded attribute-set pattern as `component.java_bridge` (`engine.py:195`).
4. Constructor rollback (resource-leak fix, B5). Wrap the post-JVM portion of `ETLEngine.__init__`
   (everything after the Java bridge starts: python/oracle/mssql managers, `_initialize_components()`,
   `execution_plan.validate()`) in a try/except that calls `self._cleanup()` before re-raising. Today
   only the JVM-start step self-cleans (`engine.py:52-56`); a later constructor raise leaves the JVM
   ORPHANED, because `with ETLEngine(...) as c` binds the name (and thus reaches `__exit__`) only
   AFTER the constructor returns. Runner-side cleanup CANNOT cover this (no object is bound on a ctor
   raise), so the rollback must live in `__init__`. This also hardens the existing root `run_job()`
   path. (`__exit__` itself is unchanged -- see below.)
5. Child-Executor fatal-failure signal (correct return codes, B3). Expose an explicit boolean, e.g.
   `job_aborted`, on the Executor/result: TRUE when `_job_terminated` (tDie/exit_code) OR any failed
   component had `die_on_error=true`; FALSE when the only failures were `die_on_error=false`
   components the job intentionally continued past. The runner maps the child to a non-zero return
   code only when this signal is true -- a bare `status == "failed"` is NOT sufficient (it is also set
   for tolerated `die_on_error=false` failures, which Talend treats as success / return 0).

`__exit__` already exists and returns False (propagates exceptions) -- do NOT add or change it
(`engine.py:302-309`). The `with ETLEngine(child) as c: c.execute()` pattern double-cleans on the
SUCCESS path, which is idempotent (guarded in `java_bridge_manager.py:119-130`, `bridge.py:386-389`).
Change 4 covers the CONSTRUCTION-failure path that `with`/`__exit__` cannot reach.

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
   The runner returns a `ChildResult` for ALL outcomes -- success, tDie, in-run engine error, AND
   child-construction failure (missing/bad child JSON, child JVM/plan failure). It does NOT raise (see
   Section 7 / 7.1), so steps 4-5 below govern every failure uniformly.
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
# Build the set of context var names the child defines across ALL its context groups, with a type
# token per name (the selected/default group's type wins). The child `context` block is keyed by
# context-GROUP name, so we must NOT gate on a single group == context_name (B1): that would silently
# drop every override when the child has no group literally named `context_name`.
ctx_block = child.job_config.get("context", {})              # {groupName: {var: {value, type}}}
ctx = self.config.get("context_name", "Default")
selected = ctx_block.get(ctx) or ctx_block.get(child.job_config.get("default_context", "Default"), {})
declared_types = {}                                          # name -> type token
for group in ctx_block.values():                             # union across all groups
    for name, meta in group.items():
        declared_types.setdefault(name, meta.get("type"))
for name, meta in selected.items():                          # selected/default group's type wins
    declared_types[name] = meta.get("type")

for source in (whole_context, param_overrides):             # param_overrides applied last (win)
    for name, value in source.items():
        if name in declared_types:
            child.context_manager.set(name, value, declared_types[name])  # coercing setter
        else:                                               # never silently drop -- WARN loudly
            logger.warning("[%s] context override '%s' not defined in child job; skipped",
                           self.id, name)
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
  matching by name across the child's declared vars; names the child defines nowhere are WARNED and
  skipped. ON = child receives the parent's current runtime values (Talend same-JVM parity). Note
  (N1): this passes only the immediate child's declared vars -- a parent var an intermediate child
  does not declare is NOT transitively passed to a grandchild (see Section 13).
- `context_params`: explicit per-variable overrides (applied last, so they win).

Type-coercion policy (N4): `ContextManager.set(name, value, type)` catches a coercion error, logs a
warning, and keeps the original (uncoerced) value (`context_manager.py`). This is the engine-wide
policy -- the SAME path the child uses to load its own typed defaults -- so seeding follows it
consistently rather than hard-failing only for tRunJob. A transmitted value that cannot coerce
(e.g. `"N/A"` into an `id_Integer` var) stays as the string, with a warning.

`context_params` value resolution (in the PARENT scope):
- literals -> as-is.
- `context.X` / `${context.X}` -> already substituted by `BaseComponent.execute()` step 3 BEFORE
  `_process` (verified: `resolve_dict` recurses lists, `context_manager.py:281-288`; so
  `config["context_params"][i]["param_value"]` arrives pre-resolved). Note substitution stringifies
  the value and the `context.X` token is gone from `self.config`, so the parent var NAME is not
  recoverable here (N6); tRunJob passes the stringified `param_value` into `param_overrides` and the
  runner re-types it via the child's declared type (above). A typed parent value, if ever needed,
  would have to come from `self._original_config`, not the resolved `self.config`.
- `globalMap.get("KEY")` and `((Type)globalMap.get("KEY"))` -> tRunJob resolves these ITSELF from
  `self.global_map` (verified: the context system never touches globalMap). A small regex extracts
  KEY (tolerating a Java cast wrapper) and reads `self.global_map.get(KEY)`.

Note on `context_name` (B1): it selects which of the child's context GROUPS supplies type tokens (and
the child's own default values for vars nobody overrides), via the fallback chain
`context_name -> child default_context -> union of all groups` shown in the code above. Crucially, the
explicit `transmit_whole_context` and `context_params` overrides are applied for EVERY variable the
child defines in ANY group, regardless of which group `context_name` selects -- so a child exported
with only an environment-named group (e.g. `PROD`, no `Default`) STILL receives its parent seeding.
This matches Talend, which always applies the Context Param table independent of active-context
selection.

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
| success (incl. only tolerated `die_on_error=false` rejects) | status == "success" | 0 |
| tDie / exit terminated | status == "error", `job_aborted` true | tDie exit code if surfaced, else -1 |
| a `die_on_error=true` component failed | status == "failed", `job_aborted` true | -1 |
| only `die_on_error=false` components failed (ran to completion) | status == "failed", `job_aborted` false | 0 |
| engine raised mid-run (stall, uncaught) | exception (has `error` key, no `global_map`) | -1, stacktrace |
| child CONSTRUCTION failed (missing/bad JSON, JVM/plan) | exception from `ETLEngine(...)` ctor | -1, stacktrace (S7.1) |

"Child failed" (for `die_on_child_error`) = `return_code != 0`, driven by the child Executor's
`job_aborted` signal (Section 4.2 change 5), NOT a bare `status == "failed"` (B3). A child that ran to
completion while tolerating `die_on_error=false` component errors returns 0 -- Talend parity: such a
child still writes its output and the parent continues. A child terminated by tDie/exit, or one where
a `die_on_error=true` component failed, returns non-zero. Code value parity: success = 0; child tDie =
its exit code; any other fatal child failure = -1.

`die_on_child_error`:
- true (converter default): raise `ComponentExecutionError` with `.exit_code` -> kills the parent job.
- false: keep the non-zero `CHILD_RETURN_CODE`, mark tRunJob successful, let the parent continue so a
  downstream RunIf can branch on `globalMap.get("tRunJob_1_CHILD_RETURN_CODE")`.

Open implementation detail (small): surfacing the EXACT child tDie exit code (vs a flat -1) may
require the child Executor to expose its captured `exit_code`. v1 may ship -1 for all failures; the
target jobs run `die_on_child_error=true`, where success/fail (not the precise code) is what matters.

### 7.1 Child construction / load failures (B4)

`ETLEngine.__init__` does fallible work (file open, `json.load`, JVM start, `execution_plan.validate()`)
at the `with ETLEngine(child_path) as child:` step, BEFORE `child.execute()`. The runner therefore
wraps construction + context seeding + execute in one try/except (Section 4 diagram step 3) and maps
ANY escaping exception to `ChildResult("error", -1, stacktrace)`. This keeps the entire failure
surface inside the return-code/die model: the component's step-4 globalMap writeback and step-5
`die_on_child_error` governance run uniformly, so a missing child JSON or a failed child JVM with
`die_on_child_error=true` STILL kills the parent (as Talend would), instead of escaping as an
`exit_code`-less exception that the base class re-wraps into a non-fatal "failed".

Policy note (deliberate, fail-loud where it matters): a missing / malformed child JSON or an invalid
child plan is a DEPLOYMENT error, not a data error. It is always surfaced -- `rc=-1` plus a clear
ASCII stacktrace in `CHILD_EXCEPTION_STACKTRACE` -- and is therefore subject to `die_on_child_error`.
Under `die_on_child_error=true` it kills the parent (correct). Under `die_on_child_error=false` it is
logged loudly and the parent continues with `CHILD_RETURN_CODE=-1` for a downstream RunIf to branch
on. We do NOT silently swallow deployment errors; the loud log + non-zero code IS the signal.

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

- Cycle (N2): cycle detection keys on the RESOLVED ABSOLUTE PATH of each child JSON (not the job name
  or file stem). If the child's resolved abspath is already in `call_stack`, raise
  `ConfigurationError("[id] cycle detected: A -> B -> A")`. Abspaths avoid the namespace mismatch
  between the root seed (a job's own file) and appended entries (resolved child files); `job_name`
  lives inside the JSON and need not equal the file stem, so it must NOT be the cycle key.
- Depth: `max_depth = 2` default (overridable via `engine_config.max_run_job_depth`). Counting: root
  job depth 0, child depth 1, grandchild depth 2. Block when the new child's depth would exceed
  `max_depth` (so parent -> child -> grandchild is allowed; deeper is a hard error). The depth guard
  is the PRIMARY recursion backstop: even if a cycle ever evaded path-matching, recursion stays
  bounded by `max_depth` -- it degrades to a "max depth exceeded" error, never runaway recursion.
- Resource accounting (N3): each nested child is a fresh `ETLEngine` -> its own JVM (own ephemeral
  port via `socket.bind(('',0))`, `java_bridge_manager.py:140-151`) and own DB connections. Because
  each ancestor's `execute()` stays on the stack while its descendant runs, PEAK concurrent live
  engines (and JVMs / Oracle-MSSql connection sets when enabled at each level) = nesting depth + 1 --
  UP TO 3 at the default `max_depth=2` (root + child + grandchild). Sibling fan-out still peaks at 2
  (each child is torn down before the next sibling starts). Capacity planning must size host JVM heap
  and DB pools for `(max_run_job_depth + 1)` live engines per concurrently running root job.
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
  - tolerated failure (B3): child with only a `die_on_error=false` failure that completes -> rc 0,
    tRunJob does NOT raise even with `die_on_child_error=true`;
  - context precedence (defaults < whole-context < context_params) + typed coercion;
  - `globalMap.get("KEY")` and `((Type)globalMap.get("KEY"))` resolution in context_params;
  - `_validate_config` rejects `use_dynamic_job` / empty `process`.
- Service unit: `tests/v1/engine/test_child_job_runner.py` -- using tiny REAL fixture child JSONs in
  `tmp_path` (no mocked runner, per the project anti-mock rule):
  - resolution by filename; missing-file -> `ChildResult(rc=-1)` (NOT an escaping exception);
  - cycle error keyed by resolved abspath (incl. a root-returning A -> B -> A) and depth-2 limit;
  - typed coercion of overrides;
  - context_name MISMATCH (B1): child whose only context group is non-`Default`, tRunJob
    `context_name` defaulting to `Default` -> assert `context_params` STILL seed the child;
  - status mapping: a child that runs tDie -> non-zero rc; a child whose engine raises
    (stall/ConfigurationError) -> rc=-1 with stacktrace captured;
  - construction failure after JVM start leaves NO orphaned JVM/managers (B5);
  - transitive whole-context behavior matches the N1 decision recorded in Section 13.
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
- `src/v1/engine/engine.py` -- additive changes (store `_job_dir`; optional `_run_context` ctor param
  + build root RunContext + ChildJobRunner; inject `component.child_job_runner`; constructor rollback
  on post-JVM construction failure -- B5)
- `src/v1/engine/executor.py` -- expose the `job_aborted` fatal-failure signal (B3)
- `src/converters/talend_to_v1/components/control/run_job.py` -- optional: drop the `engine_gap`
  needs_review now the engine implementation exists

---

## 13. Known v1 parity gaps (documented, not silent)

- Arbitrary-Java `context_params` rows unsupported (literals + context refs + `globalMap.get` only).
- Exact child tDie exit-code passthrough may ship as flat -1 first.
- `CHILD_EXCEPTION_STACKTRACE` via globalMap is a DataPrep extension, not Talend behavior.
- Dynamic job, dynamic/file-loaded context, independent-process, and JVM settings unsupported.
- `transmit_whole_context` carries only the IMMEDIATE child's declared variables; a parent variable
  that an intermediate child does not itself declare is NOT passed through to a grandchild (Talend's
  putAll would carry it). Acceptable for the shallow nesting in scope (depth mostly 1); revisit if
  deep pass-through chains appear (N1).
- Context type-coercion failures during seeding are logged and the original value is kept (engine-wide
  ContextManager policy), not hard-failed (N4).
- `context_name` selects the child's active context GROUP for type tokens / default values via the
  fallback chain (Section 6); explicit overrides apply regardless of the selection.
