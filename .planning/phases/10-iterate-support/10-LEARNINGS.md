---
phase: 10
phase_name: "iterate-support"
project: "DataPrep — Talend ETL Migration Engine"
generated: "2026-05-06"
counts:
  decisions: 12
  lessons: 8
  patterns: 13
  surprises: 11
missing_artifacts:
  - "10-UAT.md"
---

# Phase 10 Learnings: iterate-support

## Decisions

### Iterate loop driven by public API contract
The `Executor._execute_iterate_body` calls `iter_component.has_next_iteration()` + `iter_component.get_next_iteration_context()`. Direct `enumerate(iteration_iter)` is forbidden — it bypasses `current_iteration_index` advancement and the documented `_CURRENT_ITERATION` globalMap write (ITER-11).

**Rationale:** Discovered at verify-time that direct iteration left `current_iteration_index` at 0 and made `get_next_iteration_context` dead code despite passing unit tests on the method itself. The documented public contract is the only correct driver.
**Source:** 10-10-SUMMARY.md, 10-VERIFICATION.md

### Hook 8 (on_iteration_error) removed entirely
Removed `on_iteration_error` from `BaseIterateComponent` and the corresponding `except ComponentExecutionError` arm from `_execute_iterate_body`. The lifecycle is now 8 hooks, not 9.

**Rationale:** `_execute_component` swallows all exceptions and returns the string `"error"` — never re-raises. The except arm was unreachable. Threading exceptions out would have required a contract change across the entire engine. Removal is consistent with the existing errors-as-statuses architecture.
**Source:** 10-10-SUMMARY.md, 10-REVIEW.md (CR-03)

### iter_local_failed_bodies snapshot-and-diff for die_on_error
`_execute_iterate_body` snapshots `pre_iter_stats = dict(self.execution_stats)` before each iteration, computes `iter_local_failed_bodies` as a set diff after the body runs, and passes it to `_any_body_die_on_error`. The check now reads `die_on_error` directly from the component object, not from `execution_stats`.

**Rationale:** `execution_stats` is global and never cleared between iterations. A failure in iteration N left a stale `"error"` status that could spuriously trigger die_on_error in iteration N+1 even when the current iteration's failing component had `die_on_error=False`. Per-iteration diff isolates the decision.
**Source:** 10-10-SUMMARY.md, 10-REVIEW.md (CR-04)

### FileList sort race: deleted files stay in list with default 0/0.0
`_safe_stat_size` and `_safe_stat_mtime` static helpers wrap `p.stat()` in `try/except OSError` and return 0 / 0.0 on failure. Deleted files are NOT filtered from the sorted list — they stay in with the default key value.

**Rationale:** Talend semantics: skip-on-deletion happens at iteration time, not sort time. The fix only needs to prevent `FileNotFoundError` from crashing the sort; the iteration-time existence check filters actually-missing files.
**Source:** 10-11-SUMMARY.md, 10-REVIEW.md (CR-06)

### Bridge stderr drained continuously via background thread
`JavaBridge` now spawns a `java-stderr-drainer` daemon thread that reads JVM stderr line-by-line into a `collections.deque(maxlen=200)` under a `threading.Lock`. `_capture_java_stderr` reads the last 20 lines from the deque under the lock, replacing the prior blocking `select + stderr.read(65536)`.

**Rationale:** D-08-01: undrained JVM stderr accumulates in the OS pipe buffer. On Windows (4-8 KB buffer) the buffer fills after ~2 iterations of logback/JIT messages, blocking the JVM on its next stderr write and freezing all Py4J calls. Manifested as "iteration 3 doesn't finish" on Windows. Mac/Linux (64 KB) rarely hit it.
**Source:** Quick task 260506-lqq SUMMARY.md, manager-side Windows hang report

### TalendConnection.params side-channel dict for connection-level attributes
`_parse_connections` populates a generic `params: Dict[str, str]` field with all elementParameter name/value pairs from each connection. `_parse_flows` reads `ENABLE_PARALLEL` and `NUMBER_PARALLEL` from this dict for ITERATE-typed connections.

**Rationale:** Avoids adding a new dedicated field per future connection property. Generic side-channel scales for any future ITERATE-level or other connection-level XML attributes.
**Source:** 10-05-SUMMARY.md

### ENABLE_PARALLEL emits engine_gap diagnostic, not implemented
When `ENABLE_PARALLEL=true` is detected on an ITERATE flow, the converter emits a needs_review entry of shape `{severity, component_id, message}` flagging the engine gap. No parallel execution is built — deferred to a future phase.

**Rationale:** D-J3 diagnostic. Parallel iterate execution requires non-trivial engine work (thread/process pool, isolation, ordering). Phase 10 covers extraction only.
**Source:** 10-05-SUMMARY.md, 10-CONTEXT.md (D-J3)

### Dual-key config helper (`_cfg(key_upper, key_lower, default)`)
`FileList` reads config via `self._cfg("DIRECTORY", "directory")` etc., checking the uppercase key first then falling back to lowercase.

**Rationale:** Existing engine tests use uppercase Talend-style keys (`DIRECTORY`, `LIST_MODE`); the talend_to_v1 converter produces lowercase snake_case (`directory`, `list_mode`). Without the helper, `file_list.py` raised `ConfigurationError` at e2e time when fed real converter output.
**Source:** 10-07-SUMMARY.md

### `_normalize_case_sensitive` uses `isinstance(bool)` first
The helper checks `isinstance(value, bool)` before any string-membership check.

**Rationale:** Prevents `True == 1` collision when checking against a frozenset like `{"yes", "true", "1"}` — Python booleans are instances of int, so `True in frozenset({1})` is True without the explicit guard.
**Source:** 10-03-SUMMARY.md

### `iter(())` default for `iteration_iter` (not None)
`BaseIterateComponent.__init__` initialises `self.iteration_iter = iter(())` (empty iterator), not `None`.

**Rationale:** Lets `prepare_iterations` overwrite it without None-guards in the executor's `has_next_iteration()` path. Type stays `Iterator[Any]` (D-A3).
**Source:** 10-01-SUMMARY.md

### `_parse_flows` returns `(flows, needs_review_entries)` tuple
Single function call returns both the parsed flow list and any diagnostic entries.

**Rationale:** One return path for both data and diagnostics. Avoids a separate accumulator parameter or class field. Existing `TestFlowParsing` tests were updated as a Rule 1 auto-fix.
**Source:** 10-05-SUMMARY.md

### 4-tier iterate logging with `DEFAULT_LOG_PER_ITER_THRESHOLD=50`
Per-iteration progress logs are throttled: emit every iteration up to threshold, then every Nth after. ASCII-only, prefix `[<component_id>]`. Configurable via `engine_config.iterate.log_per_iter_threshold`.

**Rationale:** D-H6 — keeps logs scannable during multi-thousand-iteration runs without losing visibility on small jobs. ASCII-only per CLAUDE.md (RHEL servers).
**Source:** 10-06-SUMMARY.md

---

## Lessons

### Per-plan tests passing in isolation does NOT prove integration
Plan 10-01 tested `BaseIterateComponent.has_next_iteration()` and `get_next_iteration_context()` — green. Plan 10-02 tested the executor's iterate loop — also green. But the executor used `enumerate(iteration_iter)` directly, never calling the public API methods. The bug surfaced only at phase-verification time (CR-02). Same pattern hit CR-03 (Hook 8 unreachable in production) and CR-04 (stale stats across iterations).

**Context:** "Generator self-evaluation blind spot" — verifying a component's contract in isolation and the consumer's behavior in isolation does NOT verify that the consumer actually invokes the documented contract. Future phases with cross-plan API contracts MUST add an integration assertion that the production code path invokes the documented public methods, not just that those methods work when called directly.
**Source:** 10-VERIFICATION.md, 10-REVIEW.md, 10-10-SUMMARY.md

### Windows pipe buffers are ~10× smaller than Linux/macOS
Default OS pipe buffer: macOS/Linux ≈ 64 KB, Windows ≈ 4–8 KB. Any subprocess deadlock test that passes on Mac/Linux can still fail on Windows after far less accumulated stderr/stdout.

**Context:** D-08-01 was a known bridge bug (xfailed test in Phase 8) but never observed in CI or local testing because the pipe rarely filled in 64 KB. Manager's Windows machine surfaced it after 2 iterations of JVM logback/JIT output. Lesson: subprocess pipe handling MUST drain unconditionally; never rely on the OS buffer being "big enough."
**Source:** Quick task 260506-lqq, manager-side hang report

### Em-dash (`—`) is not double-dash (`--`) but should be normalised
User typed `/gsd-plan-phase 10 —gaps` (em-dash, U+2014). The shell does not interpret em-dash as a flag prefix. Must be normalised to `--gaps` based on context, not silently ignored.

**Context:** macOS auto-corrects `--` to `—` in some inputs. Future user-input parsers should accept both.
**Source:** Session log (this session)

### Converter and engine key conventions diverged silently
`talend_to_v1` produces lowercase snake_case keys (`directory`); engine components used uppercase Talend-style keys (`DIRECTORY`). No e2e test covered the join until Phase 10-07.

**Context:** Phase 7 / 8 components had uppercase tests but never ran the real converter. Lesson: every engine component plan should include an integration test that runs the converter→engine roundtrip on at least one real `.item` fixture.
**Source:** 10-07-SUMMARY.md

### Python 3 ABC enforcement blocks `object.__new__()` on abstract classes
`object.__new__(BaseIterateComponent)` raises `TypeError: Can't instantiate abstract class` even when bypassing `__init__`. Tests cannot construct ABCs without a concrete subclass.

**Context:** Phase 10-06 test bench needed a stub iterate component; tried `object.__new__` to avoid `__init__` side effects. Solution: define an inline concrete subclass `_ConcreteIter` with no-op abstract method implementations.
**Source:** 10-06-SUMMARY.md

### `bool` isinstance check before string membership prevents `True == 1` collision
Python booleans are `int` subclass; `True in frozenset({1, "yes"})` evaluates to True without an explicit `isinstance(value, bool)` guard.

**Context:** `_normalize_case_sensitive` returned wrong values when given `True` because the truthy frozenset contained both `1` and `"true"`. Always check bool first.
**Source:** 10-03-SUMMARY.md

### `ETLEngine.execute()` returns NB_LINE stats, not the full globalMap
The return value contains `get_all_stats()` (component-level NB_LINE/OK/REJECT counts), not the full `_map`. To assert custom globalMap keys (`_EXISTS`, `_FILENAME`, `row1.*`) post-execution, call `engine.global_map.get(key)` directly.

**Context:** Phase 10-08 tFileExist tests initially asserted on the return dict and got `None` for `_EXISTS`. Fixed by accessing the engine's `global_map` attribute.
**Source:** 10-08-SUMMARY.md

### `tPython __builtins__` whitelist does not restrict pandas internals
The tPython component restricts the user-code `__builtins__` namespace, but pandas calls CPython's built-in `open()` directly via its own internals — bypassing the whitelist. `pd.DataFrame.to_csv(path)` works inside a tPython component even when `open` is not whitelisted.

**Context:** Phase 10-08 marker-file pattern relied on this. Verified by running tests; no error raised.
**Source:** 10-08-SUMMARY.md

---

## Patterns

### 8-hook iterate lifecycle in `BaseIterateComponent`
Eight explicit hooks (was 9; Hook 8 removed): `prepare_iterations`, `has_next_iteration`, `get_next_iteration_context`, `set_iteration_globalmap`, `update_iteration_stats`, `finalize_iterations`, `get_iter_key_info`, plus `prepare`/`process`/`finalize` from `BaseComponent`. Each hook is a single-responsibility callback the executor invokes in a fixed order.

**When to use:** Any new iterate-source component (Phase 12+) inherits this lifecycle; only `prepare_iterations` and `set_iteration_globalmap` are abstract — defaults handle the rest.
**Source:** 10-01-SUMMARY.md, 10-10-SUMMARY.md

### BFS from iterate-edge target to compute body subgraph
`ExecutionPlan._build_iterate_body_plan` walks FLOW + outbound trigger edges from the iterate connection's target component, stopping at cross-subjob boundaries. Result is a `SubjobPlan` representing the body to execute per iteration item.

**When to use:** Any control-flow construct that needs a "body" of components to be re-executed inside a loop. The frozenset `_ITERATE_TYPES` is the extension point for future iterate components.
**Source:** 10-02-SUMMARY.md

### Drain-and-accumulate per iteration for REJECT outputs
`OutputRouter.drain_reject_flows` drains reject-type flows from the body component set after each iteration into a per-iteration buffer; concat at loop end. Avoids overwriting reject data across iterations.

**When to use:** Any loop where downstream subjobs consume accumulated reject rows from the iterated body.
**Source:** 10-02-SUMMARY.md

### `_ITERATE_TYPES` frozenset as extension point
A module-level frozenset of registered iterate component type names (currently `{"FileList", "FlowToIterate"}` plus Talend aliases). New iterate components register here.

**When to use:** Adding any new iterate-source component. One-line change to enable executor handling.
**Source:** 10-02-SUMMARY.md

### `fnmatch.translate -> re.compile` + `re.fullmatch` for Java Pattern parity
For glob mode, translate the user's glob to a regex via `fnmatch.translate`, compile it, then match with `re.fullmatch` (not `re.match`). Mirrors Java's `Pattern.matcher().matches()` exact-match semantics.

**When to use:** Any component reading Talend's GLOBEXPRESSIONS=true field where matching must agree with Talend's Java implementation.
**Source:** 10-03-SUMMARY.md

### `FlowToIterateItem` typed dataclass for per-row iteration items
Per-row iteration items are wrapped in a typed dataclass with `(row_dict, index)` fields, not raw `(dict, int)` tuples.

**When to use:** Any iterate-source whose items have multiple structured fields the consumer needs to access by name. Improves readability and IDE support over tuples.
**Source:** 10-04-SUMMARY.md

### `pd.NA → None` coercion before `globalMap.put`
Before writing any pandas-derived value to globalMap, coerce `pd.NA` to `None` to avoid downstream TypeError when Java code reads via `globalMap.get`.

**When to use:** Anywhere DataFrame cell values flow into the Talend-compatible globalMap dict.
**Source:** 10-04-SUMMARY.md

### Mutation-based fixture testing
Read a real `.item` fixture into a string, apply targeted `str.replace()` mutations (e.g., flip `ENABLE_PARALLEL=false` → `true`), write to `tmp_path`, run the converter on the mutated copy.

**When to use:** Testing converter handling of XML attributes that don't appear in the canonical fixture but need coverage. Avoids fragile in-memory XML construction.
**Source:** 10-05-SUMMARY.md

### Background drainer thread + bounded ring buffer for subprocess streams
A daemon thread that reads stream lines into a `collections.deque(maxlen=N)` under a `threading.Lock`. Diagnostic readers pull the last K lines under the same lock.

**When to use:** Any subprocess where stream output must be drained continuously to prevent OS pipe buffer deadlock, but where you also want ring-buffer access to recent lines for error diagnostics.
**Source:** Quick task 260506-lqq

### Snapshot-and-diff for iteration-local state
Capture `pre_iter_stats = dict(self.execution_stats)` before the iteration runs; compute `iter_local_failed_bodies = {bid for bid, status in execution_stats.items() if status == "error" and pre_iter_stats.get(bid) != "error"}` after.

**When to use:** Any per-iteration decision that must isolate this iteration's events from cumulative global state. Cleaner than clearing the global dict, which has cross-subsystem side effects.
**Source:** 10-10-SUMMARY.md

### `(data, diagnostics)` tuple return for parser functions
Return both parsed data and accumulated diagnostic entries from a single function call as a tuple. Single return path for both.

**When to use:** Parser/extractor functions where diagnostics (warnings, gap markers) must travel with the data without a class field or output parameter.
**Source:** 10-05-SUMMARY.md

### Dual-key config reader for converter/engine compatibility
A `_cfg(key_upper, key_lower, default)` helper checks uppercase first, then lowercase fallback, then default.

**When to use:** Engine components whose tests use one casing convention but the live converter produces another. Keeps existing tests green during migration.
**Source:** 10-07-SUMMARY.md

### `try/except OSError` in sort-key lambdas with stable defaults
Wrap any `Path.stat()` call in a sort-key lambda with `try/except OSError`, returning a stable default (0, 0.0) on failure. The list keeps all entries; iteration-time checks filter the actually-missing files.

**When to use:** Any sort over filesystem paths where a TOCTOU race between enumeration and sort is possible. Matches Talend's iteration-time skip semantics.
**Source:** 10-11-SUMMARY.md

---

## Surprises

### Phase 10 reached `gaps_found` despite all 8 plans passing internal verification
First verification returned `status: gaps_found` with 3 gaps closing 6 BLOCKER findings (CR-01..CR-06), even though every plan's internal Self-Check was PASSED. Required gap-closure plans 10-09, 10-10, 10-11 + 6 review-fix WARNING fixes before the second verification reached `passed`.

**Impact:** Confirmed the value of phase-level verification independent of per-plan self-checks. Gap-closure cycle added ~40% of phase 10's commits but caught real production bugs that would have shipped.
**Source:** 10-VERIFICATION.md (initial), 10-VERIFICATION.md (re-verify), 10-REVIEW.md

### Hook 8 (`on_iteration_error`) was unreachable in production
Hook 8 had unit tests proving it fires when called directly. But `_execute_component` swallows all exceptions and returns the string `"error"` — never re-raises. The `except ComponentExecutionError` arm in `_execute_iterate_body` was dead code. Hook 8 only "worked" in tests because tests called it directly.

**Impact:** Lifecycle dropped from 9 hooks to 8. Two existing tests in `test_base_iterate_component.py` had to be updated as Rule 1 auto-fixes. Surfaced the deeper "errors-as-statuses" architecture in `_execute_component`.
**Source:** 10-REVIEW.md (CR-03), 10-10-SUMMARY.md

### `current_iteration_index` permanently stayed at 0 in production
Despite passing unit tests on `has_next_iteration` and `get_next_iteration_context`, the executor used `enumerate(iteration_iter)` directly, never calling either method. `current_iteration_index` never advanced past its initialised value. ITER-11's `_CURRENT_ITERATION` globalMap write logic was dead code in production.

**Impact:** Single most surprising defect of the phase. Caught by the 10-VERIFICATION.md goal-backward must_have analysis after all plans claimed completion.
**Source:** 10-VERIFICATION.md, 10-REVIEW.md (CR-02)

### Empty iterate (0 items) failed to fire OnSubjobOk
With 0 items the body components never executed, so `executed_components` was correctly empty. But the `trigger_manager` also had no record of the body components, so `_check_subjob_ok` couldn't fire OnSubjobOk. Required an explicit `trigger_manager.set_component_status(body_id, "success")` for body components with no prior status.

**Impact:** Auto-fixed in 10-02 during test_empty_iterate_fires_subjob_ok. Talend semantic was the implicit contract — executor had to be taught to honour it.
**Source:** 10-02-SUMMARY.md

### Mac stress test: 1000 iterations in 23.37s, slowest=iter#1, fastest=iter#918
After the bridge fix, a 1000-iteration tFlowToIterate stress run produced a flat per-iteration profile: avg 0.023s, fastest 0.013s (iter #918, JIT fully warm), slowest 0.39s (iter #1, JVM warmup). No degradation curve = no buffer-fill problem.

**Impact:** Strong evidence that the stderr drainer fix is correct. If the deadlock were still latent, expected iteration time to grow as cumulative stderr filled the pipe; instead time decreased and stabilised.
**Source:** Session log (this session, post-fix stress test)

### Windows iteration-3 hang was NOT a Phase 10 bug
The manager-side "iteration 3 doesn't finish" was a pre-existing bridge-layer bug (D-08-01) from Phase 8, deferred as out-of-scope. Phase 10's iterate work surfaced it on Windows because tFlowToIterate produces enough JVM stderr per iteration to fill the 4-8 KB pipe buffer in 2-3 calls. Mac/Linux (64 KB) never observed it.

**Impact:** Not a Phase 10 regression. Triggered Quick task 260506-lqq with a 1-file fix (background stderr drainer). Validates the deferred-items list as a real risk register.
**Source:** Manager log image, Quick task 260506-lqq SUMMARY.md, Phase 8 deferred-items.md

### `ComponentStatus.FAILED` does not exist
`BaseIterateComponent.execute()` initially used `ComponentStatus.FAILED` — but the enum only has `SUCCESS` and `ERROR`. Caught by Python's enum lookup at the test execution boundary.

**Impact:** Rule 1 auto-fix in 10-01. Surfaced that the `ComponentStatus` enum is `{SUCCESS, ERROR}`, not `{SUCCESS, FAILED}`. Worth a `grep` audit — other components may have the same typo.
**Source:** 10-01-SUMMARY.md

### `python -m src.v1.engine.engine` works on Windows out of the box
The manager's Windows run with `python -m src.v1.engine.engine` produced clean log output for iterations 1 and 2 — proving the engine itself, the converter, and the basic Java bridge handshake work on Windows without modification. The hang was purely the stderr-buffer deadlock.

**Impact:** Cross-platform parity is in better shape than feared. No path-handling, encoding, or concurrency bugs surfaced — only the pipe buffer.
**Source:** Manager log image

### `_parse_flows` signature change forced 4 test updates
Changing `_parse_flows` to return `(flows, needs_review_entries)` caused 4 existing `TestFlowParsing` tests in `test_converter.py` to break with tuple-unpacking errors. All updated as Rule 1 auto-fixes.

**Impact:** Confirmed the existing test suite catches signature changes; no silent test-rot. Tuple-return pattern is now used cleanly.
**Source:** 10-05-SUMMARY.md

### `pd.DataFrame([{'fired': True}]).to_csv(path)` works inside `tPython` despite `__builtins__` whitelist
The Python routine component restricts user code's `__builtins__`, but pandas reaches CPython's built-in `open` through its own internals, bypassing the whitelist.

**Impact:** Surprising but useful — marker-file patterns inside tPython work without elevation. Worth documenting as a security boundary clarification (whitelist is on user code, not on imported libraries).
**Source:** 10-08-SUMMARY.md

### Object dataclass + `__new__()` patterns blocked by Python 3 ABC enforcement
Python 3 ABCs raise `TypeError: Can't instantiate abstract class` even when bypassing `__init__` via `object.__new__(cls)`. Test patterns that worked in Python 2 / unbenched ABCs do not transfer.

**Impact:** Phase 10-06 test bench rewrote to use an inline concrete subclass `_ConcreteIter`. Pattern documented for future iterate-component tests.
**Source:** 10-06-SUMMARY.md
