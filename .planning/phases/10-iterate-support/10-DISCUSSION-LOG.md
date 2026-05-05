# Phase 10: Iterate Support - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `10-CONTEXT.md` -- this log preserves the conversation.

**Date:** 2026-05-05
**Phase:** 10-iterate-support
**Mode:** discuss (extensive, research-driven)

## Research Performed Before Asking Questions

### Talaxie GitHub _java.xml + .javajet templates fetched
- `tFlowToIterate_java.xml` -- 2 params, 6 connectors, 2 RETURN vars (NB_LINE AFTER, CURRENT_ITERATION FLOW)
- `tFlowToIterate_main.javajet` -- generated Java code; confirmed key pattern `globalMap.put("<inputRowName>.<col>", value)` and counter pattern `counter_<cid>++; globalMap.put("<cid>_CURRENT_ITERATION", counter_<cid>);`
- `tFileList_java.xml` -- 17 params (with INCLUDSUBDIR misspelling), 7 connectors, **5 RETURN vars only** (CURRENT_FILE, CURRENT_FILEPATH, CURRENT_FILEDIRECTORY, CURRENT_FILEEXTENSION, NB_FILE)
- `tFileList_begin.javajet` -- generated code: walking via FilenameFilter recursion, sorting via Collections.sort with 3 comparators, glob via Apache ORO globToPerl5, regex via Pattern.matches() (full-string match)

### Sample .item files read
- `tests/talend_xml_samples/Job_tFileList_0.1.item` -- ITERATE source: tFileList_1 with FILES=`batch*` glob; body uses `globalMap.get("tFileList_1_CURRENT_FILEPATH")`. Single `<subjob>` block confirms intra-subjob iterate.
- `tests/talend_xml_samples/Job_tFlowToIterate_0.1.item` -- DEFAULT_MAP=true; body uses `globalMap.get("row1.filepath")` and `globalMap.get("row1.filename")`. Confirms `<inputFlowName>.<col>` key pattern. Single `<subjob>` block.

### Internal docs scanned
- `.planning/ROADMAP.md` Phase 10 (15 requirements: ITER-01..11, EXEC-04..06, TEST-04)
- `.planning/REQUIREMENTS.md` (ITER + EXEC details)
- `.planning/STATE.md` (Phase 8 closed, Phase 10 next)
- `.planning/phases/09-tcontextload-routines/09-CONTEXT.md` (Phase 9 patterns, GREEN tFileExist remediation)
- `docs/v1/audit/components/iterate/tFlowToIterate.md`
- `docs/v1/audit/components/file/tFileList.md`
- `docs/v1/audit/components/file/tFileExist.md`
- `src/v1/engine/base_iterate_component.py`, `base_component.py`, `executor.py`, `output_router.py`, `execution_plan.py`, `trigger_manager.py`, `engine.py`

### Sample conversion verification
Ran `python -m src.converters.talend_to_v1.converter` on both .item files:
- Both convert cleanly to JSON
- tFlowToIterate JSON has `inputs: ['row1']` -- engine can read input flow connection name from `BaseComponent.inputs[0]`
- tFileList JSON has all 17 config keys including INCLUDSUBDIR misspelling preserved
- Both produce single `subjob_1` containing all components -- confirms intra-subjob iterate

### Critical findings vs prior assumptions
1. **tFlowToIterate DEFAULT_MAP key pattern uses INPUT FLOW CONNECTION NAME (e.g., `row1.filepath`), NOT component id.** Sample .item file confirmed: `globalMap.get("row1.filepath")`. Prior audit docs and base class implementations had wrong assumption.
2. **CURRENT_ITERATION (not CURRENT_ITERATE).** Talaxie source confirms `_CURRENT_ITERATION` is canonical. Existing `BaseIterateComponent.get_next_iteration_context()` uses wrong key.
3. **tFileList has 5 RETURN vars, NOT 7.** Audit doc invented `_LASTMODIFIED` and `_SIZE` -- they are NOT in Talaxie. Drop.
4. **ITERATE connections are INTRA-SUBJOB.** Both .item samples have single `<subjob>` block. Iterate body re-executes a subgraph WITHIN one subjob, not a separate downstream subjob.
5. **Iterate body extends across subjob boundaries via TRIGGER edges.** A body component's OnSubjobOk to a downstream subjob means that downstream subjob is part of the body and re-runs per iteration (Talend parity).

## Question Rounds

### Round 1: Base class shape and extensibility (4 questions, all answered)

| Question | User answer |
|---|---|
| Iteration item exposure | Iterator/generator + has_next() (Recommended) |
| Lifecycle hooks needed | All 4 selected: before_iteration, after_iteration, should_stop, on_iteration_error -- "think extensively for others if needed" |
| BaseIterateComponent inheritance | Sibling abstract class (later overridden by Round 8) |
| Iteration item identification | Typed dataclass per component (Recommended) |

Claude added 2 more hooks: `prepare()` (one-time pre-loop setup), `finalize()` (one-time post-loop teardown). Total 8 hooks.

### Round 2: Execution loop, body subgraph, triggers, nested (4 questions, all answered)

| Question | User answer |
|---|---|
| Body subgraph identification | FLOW-reachable BFS from iterate target (Recommended) |
| Iterate loop site | Method on Executor (Recommended) |
| Body component triggers | "needs to be thought through bro. when iterates happens from tFileList, each file in the folder could be processed through multiple subjobs. there could be one more round of iterate flow present inside" -- prompted Claude to revise Round 2 algorithm: body extends across trigger edges too |
| Nested iterate | Single-level in Phase 10, base supports nested for Phase 10.1 |

### Round 3: Trigger semantics + stats roll-up (4 questions, partial)

| Question | User answer |
|---|---|
| Body component outbound triggers | Talend parity: trigger fires per iteration (Recommended) |
| Iterate-source outbound triggers | "i didn't understand the question or the flow here bro" -- Claude re-explained with diagram in Round 4 |
| Body-component stats reporting | Aggregate sum + per-iter list (Recommended) |
| Iterate component own stats | All 4: NB_LINE total, NB_LINE_OK successful, per-iter timing, REJECT accumulation |

### Round 4: Re-clarified trigger + reject + nested base + logging (4 questions, all answered)

Re-explained iterate-source triggers with ASCII diagram. User got it.

| Question | User answer |
|---|---|
| Iterate-source OnSubjobOk firing | Once, after all iterations complete (Recommended) |
| REJECT accumulation approach | Iterate component exposes a REJECT output flow (Recommended) |
| Nested-readiness in base | Iterate-stack-aware globalMap scope (Recommended) |
| Logging levels | All 4: start/end summary, per-iter line, DEBUG component traces, rate-limited progress |

### Round 5: Failure semantics (4 questions, all answered)

| Question | User answer |
|---|---|
| Body component failure | die_on_error decides per Talend semantics (Recommended) |
| Iterate-source failure | Honor iterate component's die_on_error config (Recommended) |
| tDie inside body | tDie immediately terminates entire job (Recommended) |
| Reject + globalMap on mid-iter failure | "research what talend does and do the same please" |

Researched via WebSearch + Talaxie source: Talend's row-by-row REJECT routing means rejects 1..N-1 are already at consumers when iter N fails (no in-memory loss). globalMap shows last-write state (no rollback). Locked the Recommended option.

### Round 6: tFileList specifics (4 questions, all answered)

| Question | User answer |
|---|---|
| Walking strategy | pathlib.Path.rglob (Recommended) |
| Regex semantics | re.fullmatch (Recommended) |
| ORDER_BY_NOTHING ordering | Talend parity: OS default order (no sort) |
| Misc semantics | All 4: CASE_SENSITIVE accept both forms, FORMAT_FILEPATH_TO_SLASH backslash replace, ERROR=true raises ComponentExecutionError, EXCLUDEFILEMASK applied AFTER inclusion |

### Round 7: tFlowToIterate specifics (4 questions, all answered)

| Question | User answer |
|---|---|
| DEFAULT_MAP key derivation | Read self.inputs[0] at iteration time (Recommended) |
| Counter semantics | 1-based, set BEFORE body runs (Recommended) |
| Per-row globalMap key persistence | Persist with last row's values (Recommended) |
| Input handling | "do same as talend bro. i wouldn't know the detail" |

Locked Talend parity: input non-None required (config-time validation), empty DataFrame = 0 iterations no error, iterate via df.to_dict('records'), defer streaming optimization.

### Round 8: Sibling-abstract refactor scope (4 questions, deferred to Claude)

User deferred all 4 sub-questions to Claude with "you decide bro. if you think sibling approach is bad, i am fine with it". Claude weighed:
- Pros of sibling: cleaner inheritance tree, removes is_iterate_component flag pattern
- Cons: 50+ existing components subclass BaseComponent, engine.py + executor.py touch points, extensive test re-runs, big Phase 10 scope addition
- Alternative: stay subclass, override execute() to skip data-pipeline steps, add lifecycle hooks -- 80% of conceptual win at 20% of cost

Recommended: stay subclass for Phase 10. User confirmed in Round 9.

### Round 9: Final loose-end tie-off (4 questions, all answered)

| Question | User answer |
|---|---|
| Confirm subclass approach | Yes, subclass for Phase 10 (Recommended) |
| Logging rate threshold | <= 50 iterations: per-iter line; > 50: every 10% (Recommended) |
| Converter ENABLE_PARALLEL | Converter extracts + adds engine_gap needs_review (Recommended) |
| tFileExist scope | Mark complete via verification only -- no code changes (Recommended) |

## Deferred Ideas Captured During Discussion

- Nested iterate execution -> Phase 10.1
- ENABLE_PARALLEL parallel iteration -> Phase 12+
- Sibling-abstract refactor -> Phase 10.5 or after 4+ iterate components ship
- tForeach / tLoop / tInfiniteLoop engines -> later phases
- Streaming-mode tFlowToIterate huge inputs -> Phase 12+
- tFileList _LASTMODIFIED / _SIZE vars -> NOT in Talaxie, drop. If Citi production needs them, surface in Phase 12.
- EXCLUDEFILEMASK as TABLE (multiple exclusions) -> Talaxie has it as TEXT (single); defer if users request

## Claude's Discretion Items

- Internal class structure of BaseIterateComponent execute() override
- Exact stats dataclass / dict shape for per-iteration timing
- pathlib walking optimization (generator vs list materialization)
- REJECT accumulation buffer strategy (in-memory list of DataFrames vs concat-on-flush)
- Test fixture design (existing StubComponent vs new IterateStubComponent)
- Helper-function vs method placement for body-subgraph BFS
- Exact format string for log messages
- iterate.log_per_iter_threshold config location (job-level vs engine-level)
- ASCII separator style consistency in log lines
