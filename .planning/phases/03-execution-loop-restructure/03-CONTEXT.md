# Phase 3: Execution Loop Restructure - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite the engine's execution orchestration so multi-subjob jobs execute with correct component ordering, proper data routing between components, correct trigger firing after subjob completion, and clear error detection for unreachable components. This phase decomposes the monolithic 370-line execution loop into focused, testable modules.

**Phase 1 vs Phase 3 boundary:** Phase 1 rewrote individual classes (BaseComponent, GlobalMap, ContextManager, TriggerManager). Phase 3 rewrites how they work together -- execution planning, component ordering, data routing, and the orchestration loop.

**Phase 3 vs Phase 10 boundary:** Phase 3 delivers `_execute_subjob()` as a callable building block. Phase 10 builds iterate support by calling `_execute_subjob()` in a loop per iteration item. Phase 3 removes the current dead iterate code.

</domain>

<decisions>
## Implementation Decisions

### Code Organization (5-File Split)
- **D-01:** Decompose engine.py into 5 focused modules:
  - `component_registry.py` -- Decorator-based auto-registration registry (matching converter pattern)
  - `execution_plan.py` -- DAG construction, topological sort, graph validation, subjob ordering, streaming metadata
  - `output_router.py` -- data_flows dict management, route component outputs, resolve component inputs, `_are_inputs_ready()`
  - `executor.py` -- `_execute_subjob()`, `_execute_component()`, error handling, trigger firing after subjob completion (the callable unit iterate will use in Phase 10)
  - `engine.py` -- Thin ETLEngine class: `__init__()` wires everything together, `execute()` delegates to plan/executor, `_cleanup()`, `run_job()`, CLI entry point

### Component Registry (Auto-Registration)
- **D-02:** Switch engine component registry from manually-maintained 125-line static dict to decorator-based auto-registration matching the converter pattern (`@REGISTRY.register('tFileInputDelimited')`). Removes coupled imports that caused ENG-04.
- **D-03:** Registration triggered via `__init__.py` imports -- same pattern as converter. `components/__init__.py` imports sub-packages, sub-package `__init__.py` imports component modules, import triggers decorator registration.
- **D-04:** Phase 3 creates the registry infrastructure but does NOT touch component files. Registry starts empty after Phase 3. Each component phase (4-11) adds `@REGISTRY.register()` decorators to its components as it rewrites them. Follows "each phase owns its own cleanup" rule.

### Execution Model (Static Plan)
- **D-05:** Build a full execution plan at init time (EXEC-03). ExecutionPlan constructs a DAG from components, flows, triggers, and subjobs. Topologically sort components within each subjob. Determine subjob execution order from the trigger graph. Execute in pre-computed order.
- **D-06:** Pre-execution graph validation (EXEC-07). ExecutionPlan.validate() checks for unreachable components and cycles before any component runs. Raises ConfigurationError with clear diagnostics listing which components are unreachable and why.
- **D-07:** Runtime stall detection as safety net. Even with pre-validation, keep runtime detection for edge cases the static analysis misses (e.g., conditional RunIf triggers that never fire). Raise error with diagnostic info, don't silently log a warning.
- **D-08:** RunIf triggers treated as conditional edges in the plan. Pre-validation does NOT flag RunIf-targeted subjobs as unreachable. Executor evaluates the RunIf condition at runtime -- fires the subjob if true, skips if false.

### Streaming
- **D-09:** Minimal streaming scope in Phase 3. Phase 1's BaseComponent already fixed reject collection in streaming mode (ENG-07/ENG-20). Phase 3 ensures the execution loop routes chunked/streamed results correctly through the DAG. Aggregate/sort streaming problems are Phase 6's concern.
- **D-10:** ExecutionPlan includes streaming awareness metadata. Components marked as "requires full data" (aggregate, sort) vs "streamable" (filter, map). This metadata doesn't change Phase 3 runtime behavior but gives Phase 6/10 a hook to optimize later.

### Error Propagation
- **D-11:** Error behavior controlled by per-component `die_on_error` config:
  - `die_on_error=True` (default): Component failure stops the subjob, remaining components in that subjob are skipped, OnSubjobError trigger fires if wired.
  - `die_on_error=False`: Component marked as failed, execution continues to next component in the subjob. Dependents that needed its output get skipped (their inputs aren't available).
- **D-12:** Independent subjobs always continue. A failure in Subjob A does not stop Subjob C if C has no dependency on A (no trigger chain between them).
- **D-13:** tDie preserves special behavior -- raises ComponentExecutionError with `exit_code` attribute. Executor catches this specifically and stops the entire job, not just the subjob. This matches Talend's intended tDie behavior.

### Iterate Handling
- **D-14:** Remove `_execute_iterate_component()` entirely (141 lines of dead code). No iterate components are registered in COMPONENT_REGISTRY today. Phase 10 builds iterate support fresh using executor.py's `_execute_subjob()` as its building block.
- **D-15:** BaseIterateComponent class (in base_iterate_component.py) stays -- Phase 1 rewrote it, Phase 10 uses it. Only the engine.py orchestration code for iterate is removed.

### Data Flow Memory Management
- **D-16:** Research phase must investigate how Talend manages data flow lifecycle -- when data is freed after downstream consumers read it. The implementation should match Talend's behavior to avoid edge cases. This is a research question, not a locked decision.

### Test Strategy
- **D-17:** StubComponent as permanent test fixture in `tests/v1/engine/conftest.py`. Extends BaseComponent with minimal `_validate_config()` and configurable `_process()` output. Tests execution orchestration without depending on real component implementations.
- **D-18:** Each new module gets its own test file: `test_execution_plan.py`, `test_output_router.py`, `test_executor.py`, `test_component_registry.py`. Tests use real TriggerManager/GlobalMap but StubComponents.
- **D-19:** ~20 core test scenarios covering: single/multi-subjob execution, trigger chains (OnSubjobOk, OnSubjobError, OnComponentOk, RunIf), stall detection (pre-validation + runtime), error propagation (die_on_error true/false), tDie kills job, data routing (main/reject/multi-output), graph validation (unreachable/cycles), registry registration and lookup.

### Claude's Discretion
- Internal class design and method signatures for ExecutionPlan, OutputRouter, Executor
- Exact topological sort algorithm choice
- How ExecutionPlan consumes the converter's `subjobs` dict vs auto-detection fallback
- Streaming metadata schema (what fields, how components declare their capability)
- Whether `_initialize_components()` and `_initialize_triggers()` stay in engine.py or move to a factory

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 3 Requirements
- `.planning/REQUIREMENTS.md` -- EXEC-01 through EXEC-03, EXEC-07, PERF-01 mapped to Phase 3

### Current Engine Source (Rewrite Targets)
- `src/v1/engine/engine.py` -- ETLEngine class with monolithic execution loop (full rewrite target)

### Phase 1 Infrastructure (Build On Top Of)
- `src/v1/engine/base_component.py` -- Rewritten BaseComponent with lifecycle, config snapshot/restore, streaming fix
- `src/v1/engine/base_iterate_component.py` -- Rewritten BaseIterateComponent (Phase 10 uses this)
- `src/v1/engine/trigger_manager.py` -- Rewritten TriggerManager with correct OnSubjobOk (checks ALL subjob components), safe condition eval
- `src/v1/engine/global_map.py` -- Rewritten GlobalMap
- `src/v1/engine/context_manager.py` -- Rewritten ContextManager with resolve_dict()
- `src/v1/engine/exceptions.py` -- Exception hierarchy (ETLError, ConfigurationError, ComponentExecutionError, etc.)

### Converter Pattern (Registry Reference)
- `src/converters/talend_to_v1/components/registry.py` -- Decorator-based ConverterRegistry. Engine's ComponentRegistry must match this pattern.
- `src/converters/talend_to_v1/components/__init__.py` -- How __init__.py imports trigger auto-registration

### Standards
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` -- Engine component pattern (Phase 1 created). Components rewritten in Phase 4-11 follow this.
- `docs/v1/standards/ENGINE_TEST_PATTERN.md` -- Engine test pattern (Phase 1 created). Phase 3 tests follow this.

### Prior Phase Context
- `.planning/phases/01-infrastructure-bug-fixes-project-setup/01-CONTEXT.md` -- Phase 1 decisions including D-09 (accept breakage), D-10 (Phase 1 vs Phase 3 boundary), D-14 (config snapshot for iterate)
- `.planning/phases/02-java-bridge-reliability/02-CONTEXT.md` -- Phase 2 decisions including bridge integration points

### Audit Reports
- `docs/v1/audit/CROSS_CUTTING_ISSUES.md` -- Engine-level bugs. Sections on execution loop fragility, trigger manager condition eval, error handling flow.
- `.planning/codebase/CONCERNS.md` -- Engine execution loop listed as fragile area. Performance bottlenecks. Missing iterate components.
- `.planning/codebase/ARCHITECTURE.md` -- Engine execution pipeline, data flow, key abstractions

### Sample Job Configs (Test Reference)
- `tests/talend_xml_samples/converted_jsons/Job_tContextLoad_0.1.json` -- Multi-subjob job with OnComponentOk trigger
- `tests/talend_xml_samples/converted_jsons/Job_tFileRowCount_0.1.json` -- Multi-subjob job with 2 OnSubjobOk triggers, 3 subjobs

</canonical_refs>

<code_context>
## Existing Code Insights

### What Gets Rewritten
- `engine.py` execute() (lines 368-510) -- monolithic 140-line execution loop with inline subjob tracking, BFS queue, trigger firing, data routing
- `engine.py` _execute_component() (lines 512-594) -- component execution + inline data routing (lines 543-559 with hardcoded flow type checks)
- `engine.py` _execute_iterate_component() (lines 596-737) -- 141 lines of dead code duplicating half the execution logic (no iterate components registered)
- `engine.py` _identify_subjobs() (lines 314-366) -- subjob detection via DFS
- `engine.py` _are_inputs_ready() / _get_input_data() (lines 739-769) -- input dependency checking
- `engine.py` COMPONENT_REGISTRY (lines 59-184) -- 125-line static dict with 20 lines of coupled imports

### What Phase 1 Already Fixed (Build On)
- BaseComponent: clean lifecycle (validate -> snapshot -> resolve -> process -> stats), config immutability, streaming collects all named flows
- TriggerManager: `_check_subjob_ok()` correctly checks ALL components in subjob (ENG-10 fixed), safe condition eval without `!` corruption (ENG-06 fixed)
- GlobalMap: proper `get()` with default parameter
- ContextManager: `resolve_dict()` handles nested dicts and lists correctly, skips code fields

### Established Patterns (Preserve)
- Template method pattern: `execute()` orchestrates, `_process()` is abstract -- preserved in BaseComponent rewrite
- Module-level loggers via `logging.getLogger(__name__)`
- Converter's decorator-based registry pattern -- engine's new ComponentRegistry matches this
- `__init__.py` import-triggered registration

### Integration Points
- ExecutionPlan consumes converter-output JSON structure: `components[]`, `flows[]`, `triggers[]`, `subjobs{}`
- Executor calls BaseComponent.execute() which handles the per-component lifecycle
- Executor calls TriggerManager.get_triggered_components() after subjob completion
- OutputRouter manages data_flows dict that components read from and write to
- JavaBridgeManager and PythonRoutineManager still wired in engine.py __init__

</code_context>

<specifics>
## Specific Ideas

- The 5-file split should make each module independently testable -- ExecutionPlan doesn't need a running engine, OutputRouter doesn't need real components
- `executor._execute_subjob(subjob_id)` is THE building block for Phase 10 iterate -- design its interface knowing it will be called in a loop
- Research must investigate Talend's data flow lifecycle (when data is freed) before deciding memory management strategy
- StubComponent in conftest.py should be flexible enough to simulate failures, multi-output, and configurable results for testing all execution scenarios

</specifics>

<deferred>
## Deferred Ideas

- Component file updates with @REGISTRY.register() decorators -- Phase 4-11 (each phase updates its own components)
- Iterate execution loop -- Phase 10 (builds on executor._execute_subjob())
- Streaming optimization for aggregate/sort components -- Phase 6
- Pipeline-style streaming (component B processes chunk 1 while A processes chunk 2) -- future milestone
- Parallel execution of independent subjobs -- future milestone (out of scope per PROJECT.md)

</deferred>

---

*Phase: 03-execution-loop-restructure*
*Context gathered: 2026-04-14*
