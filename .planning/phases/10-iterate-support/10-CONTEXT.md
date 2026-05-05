# Phase 10: Iterate Support - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver tFlowToIterate engine component, tFileList engine component, and the engine iterate execution loop (body-subgraph identification, per-iteration lifecycle, REJECT accumulation, ASCII-only logging) with full Talend feature parity per Talaxie source. tFileExist is already remediated to GREEN by Phase 9 audit -- verify-only, no code change in Phase 10.

The base (BaseIterateComponent) must be designed so additional iterate components (tForeach, tLoop, tInfiniteLoop) plug in cleanly in later phases without touching engine internals.

**Deferred and explicitly out of scope:**
- Nested iterate execution -- base supports it, executor enforces depth=1 in Phase 10, lift to Phase 10.1
- ENABLE_PARALLEL parallel iteration -- sequential-only in Phase 10, defer to Phase 12+
- Sibling-abstract refactor (BaseComponent / BaseIterateComponent siblings of a shared root) -- defer until 4+ iterate components exist
- tForeach, tLoop, tInfiniteLoop concrete engines -- later phases
- Streaming-mode for very large tFlowToIterate inputs -- defer to Phase 12+

</domain>

<decisions>
## Implementation Decisions

### A. BaseIterateComponent shape (subclass approach)

- **D-A1:** BaseIterateComponent stays a SUBCLASS of BaseComponent for Phase 10. Sibling-abstract refactor deferred to Phase 10.5+ when iterate component count grows. Rationale: cosmetic gain vs. real cost (50+ existing components, engine.py / executor.py touch points).
- **D-A2:** Override `execute()` in BaseIterateComponent to skip data-pipeline lifecycle steps that don't apply to orchestration: output schema validation, REJECT routing, batch/streaming dispatch. Keep: validate_config, _resolve_expressions (iterate components may have Java in MAP entries), _update_global_map.
- **D-A3:** Replace `iteration_items: list[Any]` with `iteration_iter: Iterator[Any]`. `prepare_iterations()` returns an Iterator. Bounded components (tFileList, tFlowToIterate, tForeach, tLoop) yield from a list. tInfiniteLoop yields forever with `should_stop()` controlling exit. Future-proofs the base.
- **D-A4:** Each iterate component defines a typed dataclass for its iteration items. Phase 10 examples: `FileListItem(path: pathlib.Path, name: str, ext: str, parent: pathlib.Path)`, `FlowToIterateItem(row: dict[str, Any], index: int)`. `set_iteration_globalmap(item: ItemType)` accepts the typed item. Self-documenting, IDE-friendly, future components add their own dataclass.
- **D-A5:** Lifecycle hook order (subclasses override these, NOT execute()):
  1. `prepare()` -- one-time setup before iter loop (e.g., open dir handle, validate VALUES list)
  2. `prepare_iterations() -> Iterator[ItemType]` -- abstract, produces items
  3. (per item) `should_stop(item, index) -> bool` -- early termination hook
  4. (per item) `before_iteration(item, index)` -- pre-iter setup, log entry markers
  5. (per item) `set_iteration_globalmap(item)` -- abstract, push iter vars to globalMap
  6. (per item) [body subjob executes via Executor]
  7. (per item) `after_iteration(item, index, body_stats)` -- post-iter, stats roll-up
  8. (per item, on raise) `on_iteration_error(item, index, exc) -> bool` -- True swallows, False re-raises
  9. `finalize()` -- one-time teardown after loop, ensures `finalize_iterations()` runs even on early-stop
- **D-A6:** Iterate-stack-aware globalMap scope mechanism in place: each iterate component records its stack depth at start (`self._iterate_depth`). Phase 10 enforces depth = 1 (raises ConfigurationError on detected nesting via ExecutionPlan check). Phase 10.1 removes the depth check; the scope mechanism (e.g., scoped CURRENT_ITERATION keys per nesting level) is already wired.

### B. Iterate execution loop and body subgraph

- **D-B1:** Iterate body subgraph algorithm = transitive closure starting at the iterate edge target, following BOTH FLOW edges AND outbound trigger edges (OnSubjobOk, OnComponentOk, RunIf, OnComponentError, OnSubjobError) from any visited component. Stops at: triggers ON the iterate source itself (those are after-loop) AND components reachable from outside the iterate scope (independent execution path). Lives in ExecutionPlan as a post-build step.
- **D-B2:** Iterate loop lives as a method on `Executor`: `_execute_iterate_body(iterate_component, body_subjob_plan)`. Triggered when `_execute_subjob` encounters a component with `is_iterate_component=True`. Reuses existing `_execute_subjob` machinery for body execution.
- **D-B3:** Per iteration: hooks (D-A5 order) -> body subjob runs via existing `_execute_subjob(body_subjob_plan)` -> `BaseComponent.reset()` called on every body component (clears stats / status / globalMap component scope) -> `output_router.clear_subjob_flows(body_components, executed_components)` -> remove body components from `executed_components` set so they re-execute next iter.
- **D-B4:** Phase 10 detects nested iterate during ExecutionPlan build (an iterate component reachable in another iterate's body subgraph) and raises ConfigurationError with a clear message naming the nested iterates. Phase 10.1 lifts this check.

### C. Trigger semantics across the iterate boundary

- **D-C1:** A BODY component's outbound trigger fires per iteration (Talend parity). If the trigger points to another body subjob, that subjob re-runs per iteration (already in body). If it points OUTSIDE the body, the external subjob fires N times (once per iter). This matches Talend's row-by-row generated code semantics.
- **D-C2:** Triggers OUT OF the iterate SOURCE itself (e.g., OnSubjobOk on tFileList) fire EXACTLY ONCE after all iterations complete. State at firing: cumulative iterate stats, last iteration's globalMap values. Empty iterate (0 items) STILL fires SUBJOB_OK -- the subjob is considered "completed successfully" with 0 iterations.
- **D-C3:** Per-component-trigger contract within body: OnComponentOk fires per successful body-component execution per iteration; OnComponentError fires per failed body-component execution per iteration; OnSubjobOk on a body subjob fires per successful body subjob per iteration; OnSubjobError on a body subjob fires per failed body subjob per iteration. Matches Talend exactly.

### D. Stats roll-up

- **D-D1:** Iterate component own stats: `NB_LINE` = total iterations attempted (tFlowToIterate: input rows; tFileList: matched files). `NB_LINE_OK` = iterations completed without any body-component error. `NB_LINE_REJECT` = iterations with at least one body error. tFileList ALSO sets `NB_FILE` alias (Talend convention).
- **D-D2:** Per-iteration timing accumulated on iterate component: `total_iter_time`, `avg_iter_time`, `slowest_iter_index`, `fastest_iter_index`, `slowest_iter_time`, `fastest_iter_time`. Exposed via the component's stats dict for production diagnostics.
- **D-D3:** Body-component stats in engine `execution_stats[body_id]` = `{NB_LINE: sum, NB_LINE_OK: sum, NB_LINE_REJECT: sum, execution_time: sum, iterations: [{NB_LINE, NB_LINE_OK, NB_LINE_REJECT, execution_time, iter_index}, ...]}`. Sum is primary; iterations list is drill-down for debugging. globalMap `{body_id}_NB_LINE` shows the LAST iteration's value (Talend HashMap last-write-wins parity).
- **D-D4:** REJECT flow accumulation: iterate component exposes a `reject` output flow. Body-component rejects are captured per iteration and concatenated into one DataFrame at iterate completion. Schema = body component's reject schema. If multiple body components have reject schemas, union (column-wise). Downstream FLOW connection on the iterate's `reject` output works exactly like any other reject -- routes to whatever component (tLogRow, tFileOutputDelimited, etc.).

### E. Failure semantics

- **D-E1:** Body component fails with `die_on_error=true` -> entire job dies (existing engine behavior preserved). Iterate stops mid-loop, exception propagates to Executor's job termination path.
- **D-E2:** Body component fails with `die_on_error=false` -> log error at ERROR level (ASCII-only), mark iteration as failed (`NB_LINE_REJECT++` on iterate component), continue to iteration N+1.
- **D-E3:** Iterate component itself fails (tFileList directory missing, tFlowToIterate None input) -> honors the iterate component's own `die_on_error` config. `die_on_error=true` -> ComponentExecutionError propagates. `die_on_error=false` -> log error, set NB_LINE / NB_FILE = 0, fire OnSubjobError.
- **D-E4:** tFileList ERROR=true with 0 matches -> raise ComponentExecutionError with message matching Talend's "No file found in directory: ..." (parity with Talend RuntimeException). ERROR=false with 0 matches -> log warning, NB_FILE=0, no iterations, OnSubjobOk fires (subjob succeeded with 0 work).
- **D-E5:** tDie inside iterate body terminates entire job immediately (existing tDie behavior: raises ComponentExecutionError with `exit_code`, executor sets `_job_terminated=True`). Iterate loop checks `_job_terminated` after each body component executes; if true, breaks out and propagates up.
- **D-E6:** On body-component die_on_error=true failure mid-iterate (Talend research confirmed): accumulated rejects from iterations 1..N-1 ARE still routed to the iterate's REJECT output (Talend routes row-by-row, rejects already at consumers). globalMap reflects last-write state (no rollback). Iterate stats: NB_LINE = N (attempted), NB_LINE_OK = N-1, NB_LINE_REJECT = 1 at the iteration component level. `ETLEngine.execute()` return value retains accumulated stats for forensics.

### F. tFlowToIterate engine

- **D-F1:** Input MUST be a non-None DataFrame. `_validate_config` raises ConfigurationError if `self.inputs` is empty (no input flow connection). At runtime, None input_data also raises. Empty DataFrame (zero rows) is OK -> 0 iterations, no error.
- **D-F2:** Iterate via `df.to_dict('records')` -- materializes input flow into a list of row-dicts. Closest to Talend's per-row Java semantics, simple, dtype loss is acceptable (Python is dynamic). Defer streaming-mode optimization (chunked DataFrame iteration) to Phase 12+.
- **D-F3:** DEFAULT_MAP=true: for each input row, for each column in the row, `globalMap.put(f'{self.inputs[0]}.{col}', value)`. Reads input flow connection name from `BaseComponent.inputs[0]` (already wired by `engine.py:120`). ConfigurationError at validate if `self.inputs` is empty. Matches Talaxie pattern `globalMap.put("<inputRowName>.<columnLabel>", value)` and confirmed by .item sample using `globalMap.get("row1.filepath")`.
- **D-F4:** DEFAULT_MAP=false: for each row, for each entry in `config.map_entries`, `globalMap.put(entry['key'], row[entry['value']])`. KEY is user-defined raw string with NO prefix added (entry['key'] is used verbatim); VALUE is the column name from input row. Matches Talaxie pattern `globalMap.put(<%= line.get("KEY") %>, <%=inputRowName %>.<%= line.get("VALUE") %>)`.
- **D-F5:** Counter semantics: 1-based, set BEFORE body runs. Internal counter `0 -> 1 -> 2 -> ... -> N`. Per iteration: counter++, then `globalMap.put(f'{self.id}_CURRENT_ITERATION', counter)`, THEN body executes. Body components reading globalMap see 1, 2, 3, ... N. NB_LINE set AFTER all iterations = total rows. Matches Talaxie code: `counter_<cid>++; globalMap.put("<cid>_CURRENT_ITERATION", counter_<cid>);`.
- **D-F6:** After iterate completes, all per-row globalMap keys (e.g., `row1.filepath`, `row1.filename`, `row1.dept` from the .item sample) PERSIST with the last row's values. Talend HashMap semantics -- keys retained until job ends. Components after the iterate source's SUBJOB_OK trigger can read these last-row values.
- **D-F7:** Fix existing `BaseIterateComponent.get_next_iteration_context`: rename `_CURRENT_ITERATE` key to `_CURRENT_ITERATION`. Talaxie source confirms `_CURRENT_ITERATION` is the canonical key. Existing code is wrong.

### G. tFileList engine

- **D-G1:** GlobalMap RETURN variables (5 only, per Talaxie tFileList_java.xml): `{cid}_CURRENT_FILE` (filename only), `{cid}_CURRENT_FILEPATH` (absolute path), `{cid}_CURRENT_FILEDIRECTORY` (parent directory), `{cid}_CURRENT_FILEEXTENSION` (extension, no leading dot to match Java File.getName / lastIndexOf convention -- to be confirmed in plan-phase research), `{cid}_NB_FILE` (1-based counter during iter; equals total at end). Drop the audit doc's invented `_LASTMODIFIED` and `_SIZE` -- they are NOT in Talaxie source.
- **D-G2:** Walking strategy: `pathlib.Path(directory).iterdir()` non-recursive (INCLUDSUBDIR=false), `pathlib.Path(directory).rglob('*')` recursive (INCLUDSUBDIR=true). Modern, type-safe, single-line per mode.
- **D-G3:** LIST_MODE filter: `FILES` -> `path.is_file()`, `DIRECTORIES` -> `path.is_dir()`, `BOTH` -> any.
- **D-G4:** Glob mode (GLOBEXPRESSIONS=true): `fnmatch.translate(mask)` -> compiled `re.fullmatch` with `re.IGNORECASE` flag when CASE_SENSITIVE is falsy. Multiple FILES masks combined OR-wise -- a file matches if ANY mask matches.
- **D-G5:** Regex mode (GLOBEXPRESSIONS=false): `re.fullmatch` directly (Java's `Pattern.matcher(s).matches()` is full-string match -- equivalent is re.fullmatch, NOT re.search or re.match). `re.IGNORECASE` flag when CASE_SENSITIVE is falsy.
- **D-G6:** Sort: ORDER_BY_NOTHING=true -> Talend parity, OS-default order from pathlib (non-deterministic across filesystems -- accepted as the parity choice). ORDER_BY_FILENAME -> stable sort by `path.name`. ORDER_BY_FILESIZE -> stable sort by `path.stat().st_size`. ORDER_BY_MODIFIEDDATE -> stable sort by `path.stat().st_mtime`. ORDER_ACTION_DESC reverses any sort. Tie-breaking left to Python sort stability (insertion order preserved for equal keys).
- **D-G7:** IFEXCLUDE=true: apply EXCLUDEFILEMASK in the SAME mode (glob/regex) and SAME case-sensitivity as inclusion masks, AFTER inclusion filter. Files matching EXCLUDEFILEMASK are removed. EXCLUDEFILEMASK is a single TEXT pattern (not a TABLE) -- only one exclusion supported per Talaxie.
- **D-G8:** ERROR=true with 0 matches: raise `ComponentExecutionError` with message format `"No file found in directory: <directory>"` (parity with Talend RuntimeException). ERROR=false with 0 matches: log WARNING, NB_FILE=0, no iterations, no exception.
- **D-G9:** CASE_SENSITIVE normalization: engine accepts both Talaxie strings (`"YES"`/`"NO"`) and boolean-like strings from .item exports (`"true"`/`"false"`) and Python booleans. Truthy = case-sensitive when value in `{'YES', 'yes', True, 'true'}`. Falsy when value in `{'NO', 'no', False, 'false'}`. Other values -> ConfigurationError.
- **D-G10:** FORMAT_FILEPATH_TO_SLASH=true: replace `\` with `/` in `CURRENT_FILE`, `CURRENT_FILEPATH`, `CURRENT_FILEDIRECTORY` values BEFORE setting in globalMap. Cross-platform job parity.

### H. Logging (ASCII-only, no emojis or unicode)

- **D-H1:** Iterate start log (INFO): `[<cid>] Starting iterate: <N> items, <M> components in body`
- **D-H2:** Iterate end log (INFO): `[<cid>] Iterate complete: <N_ok> OK, <N_err> errors, total elapsed=<T.TT>s`
- **D-H3:** Per-iteration boundary line (INFO) when `total <= iterate.log_per_iter_threshold` (default 50): `[<cid>] Iteration <K>/<N>: <key_info> | iter_time=<T.TT>s`. `key_info` is component-specific: tFileList -> `file=<CURRENT_FILEPATH>`; tFlowToIterate -> `row_index=<K>`.
- **D-H4:** Rate-limited progress line (INFO) when `total > threshold`: every 10% of total iterations, log `[<cid>] <K>/<N> iterations complete (<P>%, eta <T.T>s)`. ETA computed from rolling avg of completed iter times.
- **D-H5:** DEBUG per-body-component traces (per iteration): `[<cid>.iter=<K>] <body_id>: NB_LINE=<L> NB_REJECT=<R>`.
- **D-H6:** Threshold configurable via engine config key `iterate.log_per_iter_threshold` (int, default 50).
- **D-H7:** All log messages strictly ASCII -- no emojis, no unicode arrows, no box-drawing characters. RHEL production servers require clean ASCII per project memory.

### I. State management (mostly free from existing infrastructure)

- **D-I1:** `BaseComponent.reset()` (already exists at `base_component.py:1336`) called on every body component between iterations. Clears stats, status, globalMap component scope. No new code needed.
- **D-I2:** Config snapshot/restore: NO new code. `_original_config` deepcopy at every `execute()` call (`base_component.py:225`) gives per-iteration freshness automatically. EXEC-06 satisfied "for free" by existing Phase 1 infrastructure.
- **D-I3:** Java bridge sync: NO new code. Phase 2's per-call sync (`bridge.py` sync-after-every-call pattern) handles per-iteration globalMap updates flowing into Java expressions.
- **D-I4:** data_flows lifecycle between iterations: `output_router.clear_subjob_flows(body_components, executed_components)` (already exists in `output_router.py`) called between iterations. Body components removed from `executed_components` set so they re-execute next iter. Verify this works for partial subjob (not full subjob clear) -- may need a new helper.

### J. Converter changes

- **D-J1:** tFlowToIterate converter: GREEN, no changes needed. Existing converter writes `inputs: ['row1']` and schema in JSON, which the engine reads via `BaseComponent.inputs[0]` already wired by `engine.py:120`.
- **D-J2:** tFileList converter: GREEN, all 17 config keys + INCLUDSUBDIR misspelling preserved. Engine handles CASE_SENSITIVE normalization (D-G9). No converter change.
- **D-J3:** ITERATE connection ENABLE_PARALLEL extraction (NEW): converter reads `ENABLE_PARALLEL` and `NUMBER_PARALLEL` from the `<connection>` element of any ITERATE-typed connection. Writes into the flow dict: `{type: 'iterate', enable_parallel: bool, number_parallel: int}`. If `ENABLE_PARALLEL=true`, adds a needs_review entry severity=`engine_gap` with message `"Parallel iteration is configured (NUMBER_PARALLEL=<N>) but Phase 10 engine runs sequentially -- results correct but slower. Defer to Phase 12+ for parallel."`.
- **D-J4:** Subjob structure: existing single-subjob output is correct. Both .item samples produce a single `subjob_1` containing all components, confirming intra-subjob iterate. No converter change.

### K. tFileExist (verify-only, no code changes)

- **D-K1:** tFileExist is already remediated to GREEN by Phase 9 audit (`docs/v1/audit/components/file/tFileExist.md` re-audit dated 2026-04-29). All P0/P1 issues resolved. No engine code changes in Phase 10.
- **D-K2:** Phase 10 verification confirms ITER-08 (file_name vs file_path config key handling -- both accepted) and ITER-09 (`{id}_EXISTS` and `{id}_FILENAME` globalMap variables -- both set). Both already implemented per audit.
- **D-K3:** Add at least one tFileExist integration test using a real .item sample where tFileExist is followed by RUN_IF -> downstream subjob, validating the file-existence-driven branching.

### L. Phase 10 sub-phase plan (anticipatory -- planner finalizes)

- **D-L1:** Recommended sub-phase split (planner may adjust):
  - **10-01:** BaseIterateComponent enhancements -- 6 lifecycle hooks, iterator-based items (D-A3), typed item dataclasses (D-A4), execute() override skipping data steps (D-A2), iterate-stack scope mechanism (D-A6), CURRENT_ITERATE -> CURRENT_ITERATION fix (D-F7). Unit tests.
  - **10-02:** Executor iterate loop (`_execute_iterate_body`) + ExecutionPlan body-subgraph BFS (D-B1) + REJECT accumulation infrastructure (D-D4) + nested-iterate detection check (D-B4). Unit tests using StubComponent fixtures.
  - **10-03:** tFileList engine component (`src/v1/engine/components/file/file_list.py`) per ENGINE_COMPONENT_PATTERN.md. All 16 _java.xml params + 5 globalMap vars. Unit tests covering glob/regex modes, INCLUDSUBDIR, sort variants, ERROR=true/false 0-match, FORMAT_FILEPATH_TO_SLASH.
  - **10-04:** tFlowToIterate engine component (`src/v1/engine/components/iterate/flow_to_iterate.py` -- new `iterate/` engine package) per ENGINE_COMPONENT_PATTERN.md. DEFAULT_MAP=true and DEFAULT_MAP=false branches. Unit tests covering empty input, multi-row input, MAP table entries.
  - **10-05:** Converter ENABLE_PARALLEL extraction + needs_review (D-J3). Converter unit tests.
  - **10-06:** Logging infrastructure (D-H1..H7) + `iterate.log_per_iter_threshold` engine config key. Unit tests for log format and rate-limit threshold.
  - **10-07:** Integration tests with real .item samples: convert + execute end-to-end for `Job_tFileList_0.1.item` (tFileList -> tFileInputDelimited -> tMap -> tFileOutputDelimited APPEND=true) and `Job_tFlowToIterate_0.1.item` (tFileInputDelimited -> tFlowToIterate -> tFileInputDelimited -> tMap -> tFileOutputDelimited). Use `@pytest.mark.java` for tMap expressions (Phase 5.1 lesson -- mocks lie).
  - **10-08:** tFileExist verification + integration test (D-K3). No code change to tFileExist itself.
- **D-L2:** All new engine components conform to ENGINE_COMPONENT_PATTERN.md gold standard (carryover from Phase 1 D-16). All new tests conform to ENGINE_TEST_PATTERN.md.
- **D-L3:** Each sub-phase plan ends with at least one `@pytest.mark.java` integration test where Java expressions are involved (Phase 5.1 lesson).
- **D-L4:** Phase 7.1 Rule 12 carryover: content checks belong in `_process()`, NOT `_validate_config()`. Iterate components' `_validate_config` only validates structural correctness (required keys, valid enum values), never resolved values.

### Claude's Discretion

- Internal class structure of BaseIterateComponent execute() override (method decomposition, hook invocation order details)
- Exact stats dataclass / dict shape for per-iteration timing
- Internal pathlib walking optimization (e.g., generator vs list materialization for very large directories -- choose pragmatic default)
- REJECT accumulation buffer strategy (in-memory list of DataFrames vs concat-on-flush -- choose based on memory profile)
- Test fixture design (existing StubComponent vs new IterateStubComponent)
- Helper-function vs method placement for body-subgraph BFS algorithm
- Exact format string for log messages (D-H1..H5 are the spec; minor wording is discretion)
- Whether `iterate.log_per_iter_threshold` config goes in job-level config or engine-level constants
- ASCII separator characters in log lines (e.g., `|`, `--`, `:`) -- pick one style and stay consistent

### Folded Todos

None for this phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Talaxie source of truth (Talend feature baseline)
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tFlowToIterate/tFlowToIterate_java.xml` -- tFlowToIterate _java.xml: 2 params (DEFAULT_MAP, MAP), 6 connectors, 2 RETURN vars (NB_LINE AFTER, CURRENT_ITERATION FLOW)
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tFlowToIterate/tFlowToIterate_main.javajet` -- generated Java code for tFlowToIterate; confirms `globalMap.put("<inputRowName>.<col>", value)` key pattern
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tFileList/tFileList_java.xml` -- tFileList _java.xml: 17 params (incl. INCLUDSUBDIR misspelling), 7 connectors, 5 RETURN vars (CURRENT_FILE, CURRENT_FILEPATH, CURRENT_FILEDIRECTORY, CURRENT_FILEEXTENSION, NB_FILE)
- `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tFileList/tFileList_begin.javajet` -- generated code for tFileList: walking + sorting + glob/regex matching reference

### Sample Talend jobs (integration test fixtures)
- `tests/talend_xml_samples/Job_tFileList_0.1.item` -- tFileList iterate flow with tFileInputDelimited reading via `globalMap.get("tFileList_1_CURRENT_FILEPATH")` -> tMap -> tFileOutputDelimited APPEND=true
- `tests/talend_xml_samples/Job_tFlowToIterate_0.1.item` -- tFileInputDelimited -> tFlowToIterate -> tFileInputDelimited reading via `globalMap.get("row1.filepath")` -> tMap (also reads `row1.filename`, `row1.dept`) -> tFileOutputDelimited

### Internal audit reports
- `docs/v1/audit/components/iterate/tFlowToIterate.md` -- existing audit; converter status Green, engine gap P0
- `docs/v1/audit/components/iterate/tForeach.md` -- forward reference for future iterate components
- `docs/v1/audit/components/file/tFileList.md` -- audit notes audit invented _LASTMODIFIED / _SIZE vars NOT in Talaxie -- ignore those, follow Talaxie's 5 vars instead (D-G1)
- `docs/v1/audit/components/file/tFileExist.md` -- shows tFileExist remediated GREEN by Phase 9 (D-K1)

### Project standards
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` -- gold-standard structure for new engine components (D-L2)
- `docs/v1/standards/ENGINE_TEST_PATTERN.md` -- engine test structure
- `docs/v1/standards/CONVERTER_PATTERN.md` -- converter structure rules (for D-J3 ENABLE_PARALLEL extraction)
- `docs/v1/standards/TEST_PATTERN.md` -- general test layout
- `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` -- includes Phase 7.1 Rule 12 (content checks in _process, not _validate_config) -- D-L4

### Engine infrastructure to extend
- `src/v1/engine/base_iterate_component.py` -- existing skeleton, extend per D-A1..A6, fix `_CURRENT_ITERATE` -> `_CURRENT_ITERATION` (D-F7)
- `src/v1/engine/base_component.py` -- existing reset() at line 1336 (D-I1), _original_config deepcopy at line 225 (D-I2). No changes; iterate components subclass it.
- `src/v1/engine/executor.py` -- extend with `_execute_iterate_body()` (D-B2), wire iterate detection at `_execute_subjob` step
- `src/v1/engine/execution_plan.py` -- extend with body-subgraph BFS (D-B1) and nested-iterate detection (D-B4)
- `src/v1/engine/output_router.py` -- existing `clear_subjob_flows()` (D-I4) and "iterate" flow type. May need a `clear_partial_subjob_flows()` helper for body-only clear.
- `src/v1/engine/trigger_manager.py` -- NO new TriggerType. ITERATE is a flow connection, not a trigger.
- `src/v1/engine/component_registry.py` -- iterate components register via existing `@REGISTRY.register("FileList", "tFileList")` decorator pattern

### Engine components
- `src/v1/engine/components/file/file_exist.py` -- existing GREEN implementation, no changes (D-K1)
- `src/v1/engine/components/file/file_list.py` -- TO BE CREATED per D-G1..G10
- `src/v1/engine/components/iterate/flow_to_iterate.py` -- TO BE CREATED in NEW `iterate/` engine package, per D-F1..F7
- `src/v1/engine/components/iterate/__init__.py` -- TO BE CREATED to register the iterate package

### Converter source
- `src/converters/talend_to_v1/components/iterate/flow_to_iterate.py` -- existing converter (Green); no changes (D-J1)
- `src/converters/talend_to_v1/components/file/file_list.py` -- existing converter (Green); no changes (D-J2)
- `src/converters/talend_to_v1/components/file/file_exist.py` -- existing converter (Green); no changes
- `src/converters/talend_to_v1/converter.py` -- iterate-connection ENABLE_PARALLEL / NUMBER_PARALLEL extraction (D-J3) lives in connection-handling code (likely `_parse_flows` or equivalent); planner identifies exact location

### Prior phase carryovers
- Phase 1 D-16 -- All engine components conform to ENGINE_COMPONENT_PATTERN.md
- Phase 1 -- BaseComponent.reset() and _original_config deepcopy give EXEC-05 + EXEC-06 essentially for free (D-I1, D-I2)
- Phase 2 -- Java bridge per-call sync handles iterate Java expression updates without new code (D-I3)
- Phase 3 D-04 -- @REGISTRY.register decorator with PascalCase + Talend aliases
- Phase 5.1 -- Always include `@pytest.mark.java` integration tests; mocks lie (D-L3)
- Phase 7.1 Rule 12 -- Content checks belong in `_process`, not `_validate_config` (D-L4)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- **`BaseComponent.reset()`** (`base_component.py:1336`) -- already implemented per Phase 1; clears stats, status, globalMap component scope. Phase 10 calls between iterations on body components (D-I1).
- **`BaseComponent._original_config`** deepcopy at every `execute()` (`base_component.py:225`) -- gives per-iteration config freshness automatically. EXEC-06 satisfied "for free" (D-I2).
- **`BaseIterateComponent`** skeleton (`base_iterate_component.py`) -- has `prepare_iterations` / `set_iteration_globalmap` abstracts, `has_next_iteration` / `get_next_iteration_context` query methods, `update_iteration_stats` / `finalize_iterations` lifecycle. Extend per D-A1..A6.
- **`Executor._execute_subjob()`** (`executor.py:173`) -- explicitly documented as "THE building block Phase 10 iterate support will call in a loop per iteration item." Reused by `_execute_iterate_body` (D-B2).
- **`OutputRouter.clear_subjob_flows()`** (`output_router.py`) -- already used for inter-subjob cleanup. Reused for between-iteration cleanup (D-I4); may need a partial-subjob variant for body-only clear.
- **`OutputRouter` "iterate" flow type** (`output_router.py:26`) -- already maps `"iterate": "iterate"`. ITERATE is a flow type, not a new trigger.
- **`engine.py:120`** wires `component.inputs = comp_config.get('inputs', [])` from JSON -- gives tFlowToIterate access to the input flow connection name (D-F3).
- **`@REGISTRY.register("FileList", "tFileList")`** decorator pattern from Phase 3 D-04 -- new iterate components register identically.
- **`tFileExist` engine** (`src/v1/engine/components/file/file_exist.py`) -- already GREEN, used as a reference for trigger-only utility components. No changes (D-K1).

### Established patterns (constraints)
- **ENGINE_COMPONENT_PATTERN.md** gold standard: every new engine component follows the structure (module docstring with full Config Mapping, `@REGISTRY.register` with multiple aliases, `_validate_config` raises ConfigurationError, `_process` returns `{main, reject, stats}` dict).
- **Phase 7.1 Rule 12:** Content checks (e.g., glob mask validity, file existence) belong in `_process`, NOT `_validate_config`. `_validate_config` runs BEFORE context resolution, so it cannot trust resolved values.
- **ASCII-only logging** (project memory): no emojis, no unicode arrows, no box-drawing. RHEL servers consume logs that must stay ASCII.
- **`@pytest.mark.java` integration tests** (Phase 5.1 lesson): mocks of the Java bridge gave false confidence for tMap. Every iterate phase test that involves Java expressions inside body components must include a real-bridge test.
- **Single subjob per .item file** (confirmed empirically): both Phase 10 .item samples produce one `subjob_1`. ITERATE is intra-subjob -- iterate source and target live in the same subjob block (D-J4).

### Integration points
- **ExecutionPlan.build()** in `execution_plan.py` -- add post-build step to identify iterate body subgraphs (D-B1) and detect nested iterate (D-B4).
- **Executor._execute_subjob()** -- branch when encountering `is_iterate_component=True` to call `_execute_iterate_body()` (D-B2). After iterate completes, continue with subjob's remaining components (which should typically be none if the iterate body covers everything FLOW-downstream).
- **Executor._fire_component_triggers()** -- iterate component's outbound triggers fire ONCE after `_execute_iterate_body` returns (D-C2). Body component triggers fire per iteration (D-C1).
- **Trigger evaluation** -- `TriggerManager` unchanged. ITERATE is not a trigger; existing trigger types (OnSubjobOk etc.) work as-is across the iterate boundary.
- **OutputRouter.route_outputs()** -- iterate component's `reject` output (D-D4) routes through existing OutputRouter mechanism once accumulated.
- **Java bridge sync** (`bridge.py`) -- per-call sync from Phase 2 handles per-iteration globalMap updates without changes (D-I3).

</code_context>

<specifics>
## Specific Ideas

- "Build the base in such a way that other [iterate] components can be easily plugged in" -- 6 lifecycle hooks (D-A5), iterator-based item flow (D-A3), typed item dataclasses (D-A4), iterate-stack-aware globalMap scope (D-A6) ALL pay forward to tForeach, tLoop, tInfiniteLoop, tForeachWithStat in later phases.
- "Subjobs properly work" -- D-B1 body subgraph follows BOTH FLOW edges AND outbound trigger edges so multi-subjob iterate bodies (the common production pattern) work correctly. D-C1, D-C2, D-C3 spell out trigger semantics across the iterate boundary.
- "Stats properly captured" -- D-D1..D4 cover iterate-component own stats, per-iteration timing, body-component aggregate + drill-down stats, and REJECT accumulation. globalMap last-write-wins matches Talend.
- "Logging is taken care of" -- D-H1..H7 cover iterate start/end summary, per-iter line for small iterates, rate-limited progress for large iterates, DEBUG body traces, configurable threshold, ASCII-only enforcement.
- The two .item samples (Job_tFileList_0.1, Job_tFlowToIterate_0.1) ARE the integration test fixtures. The conversion produces clean JSON; integration testing converts + executes end-to-end and compares output to expected (D-L1.10-07).

</specifics>

<deferred>
## Deferred Ideas

- **Nested iterate execution** -- base supports it via iterate-stack scope (D-A6); executor enforces depth=1 in Phase 10 via ExecutionPlan check (D-B4). Lift in Phase 10.1.
- **ENABLE_PARALLEL parallel iteration** -- converter extracts and warns (D-J3), engine runs sequentially. Defer to Phase 12+.
- **Sibling-abstract refactor** (BaseComponent + BaseIterateComponent siblings of AbstractEngineComponent) -- defer until 4+ iterate components exist (likely Phase 10.5 or after Phase 12 when tForeach / tLoop ship).
- **tForeach, tLoop, tInfiniteLoop concrete engines** -- later phases. Phase 10 base supports them.
- **Streaming-mode for huge tFlowToIterate inputs** -- df.to_dict('records') materializes; defer chunked-iteration optimization to Phase 12+.
- **tFileList globalMap _LASTMODIFIED / _SIZE vars** -- the audit doc invented these; Talaxie does NOT have them. Drop. If Citi production has Talend customizations adding these, surface in Phase 12 integration testing and add as engine extension (with clear docstring noting deviation).
- **EXCLUDEFILEMASK as TABLE** -- Talaxie has it as TEXT (single mask). If users need multiple exclusions, defer to a later request.

### Reviewed Todos (not folded)
None reviewed.

</deferred>

---

*Phase: 10-iterate-support*
*Context gathered: 2026-05-05*
