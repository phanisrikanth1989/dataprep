---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 05.4 complete (8/8 plans; verification report + phase summary committed)
last_updated: "2026-05-15T18:00:38.193Z"
last_activity: 2026-05-15 -- Phase 05.5 execution started
progress:
  total_phases: 24
  completed_phases: 22
  total_plans: 125
  completed_plans: 145
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-14)

**Core value:** Any Talend job using the target components must produce identical results when run through the Python engine
**Current focus:** Phase 05.5 — tmap-context-globalmap-bridge-sync

## Current Position

Phase: 05.5 (tmap-context-globalmap-bridge-sync) — EXECUTING
Plan: 1 of 8
Next: Phase 16 (Integration Testing & Performance, manager-led)
Status: Executing Phase 05.5
Last activity: 2026-05-15 -- Phase 05.5 execution started

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 70
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 7 | - | - |
| 02 | 4 | - | - |
| 03 | 4 | - | - |
| 04 | 3 | - | - |
| 05 | 3 | - | - |
| 05.1 | 2 | - | - |
| 05.2 | 2 | - | - |
| 06 | 4 | - | - |
| 07 | 2 | - | - |
| 09 | 2 | - | - |
| 07.1 | 8 | - | - |
| 07.2 | 4 | - | - |
| 08 | 6 | ~2.5h | ~25min |
| 10 | 11 | - | - |
| 11 | 7 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 12 P07 | 25 | 3 tasks | 6 files |
| Phase 12 P08 | 15 | 4 tasks | 5 files |
| Phase 12 total | ~200 | 8 plans, 6 waves | 6 components + _xml_io |
| Phase 13-test-stabilization-bridge-jar-rebuild P01 | 35 | 2 tasks | 5 files |
| Phase 14 P02 | 35 | 2 tasks | 2 files |
| Phase 14 P03 | 30 | 3 tasks | 2 files |
| Phase 14 P04 | 30 | 3 tasks | 2 files |
| Phase 14 P05 | 85 | 13 tasks | 16 files |
| Phase 14 P08 | 33 | 16 tasks | 17 commits / 12 test files modified + 3 fixtures + 1 source + 1 .gitignore |
| Phase 14 P07 | 120 | 7 tasks | 8 commits / 12 created + 3 modified (2 source + 1 file_input_raw); SWIFT 7% -> 97-98% on both modules |
| Phase 14 P09 | 55 | 9 tasks | 9 commits / 12 created + 4 modified (1 source + 3 tests + .gitignore); 4 file deep gaps lifted, BUG-FIJ-001/002 fixed |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Java bridge must be reliable BEFORE component work -- moved to Phase 2 so tMap, code components, and routines can depend on it
- Config mutation in BaseComponent blocks iterate -- must fix in Phase 1 (ENG-09, ENG-21) before Phase 10
- OnSubjobOk trigger timing fix (ENG-10) is prerequisite for execution loop restructure in Phase 3
- Transform components split: Group A (complex bugs) in Phase 6, Group B (lighter/Green) in Phase 7
- 30% of jobs need iterate support -- Phase 10 is high priority after execution loop
- Apache 2.0 redistribution sign-off accepted for vendored routines.system.* files (Phase 7.1)
- CR-07/WR-14/IN-01 byte-identical to upstream Talend OpenDAS -- DO NOT fix, Talend parity (Phase 7.1)
- MANUAL_COMPONENT_AUTHORING.md enforces Rule 11 contract -- Phase 8 plans must reference it for new components
- Phase 8 revision-2 Talend parity corrections (2026-04-29): java_row_component has NO REJECT (Talend tJavaRow has none either); python_row_component reject schema is errorMessage-only (no errorCode); D-29 one-shot passthrough is a DataPrep data-flow semantic, not a Talend feature; CONTEXT.md D-26 superseded -- code bodies are NOT context-resolved (SKIP_RESOLUTION_KEYS protection)
- Phase 8 sandbox honesty: D-11 Python namespace whitelist is hygienic, NOT adversarial-proof -- pure-Python bypass via __subclasses__/__mro__ accepted; trust boundary is internal Citi job authors
- [Phase ?]: Phase 14-02 BUG-AGG-001: list/list_object/union under ignore_null=False crashed on null-bearing input; root-cause fix via Series.fillna("null") + Java String.valueOf parity
- [Phase ?]: Phase 14-02 D-C5 deletions: _build_agg_func unknown-function fallback (silent default-to-sum) -> explicit ConfigurationError; _process column-ordering safety loop removed
- [Phase 14]: Plan 14-03 BUG-MAIL-001: send_mail.py attachment FileOperationError swallowed by outer except Exception block (rewrapped to ComponentExecutionError) -- root-cause fix via ``except ETLError: raise`` guard between attachment loop and SMTP-failure catch blocks; documented exception contract now reachable
- [Phase 14]: Plan 14-04 -- direct oracledb.DB_TYPE_* attribute lookup pattern (vs patched constants) for type-binding tests resilient to oracledb version churn; FakeDatabaseError stand-in for mid-batch driver error simulation when oracledb.DatabaseError can't be raised without a real connection
- [Phase 14]: Plan 14-05 BUG-EJF-001: extract_json_fields._is_null() only caught TypeError from bool(pd.isna(v)); pd.isna() on multi-element list returns ndarray whose bool() raises ValueError -- widened except to (TypeError, ValueError) per feedback_fix_source_no_fallbacks
- [Phase 14]: Plan 14-05 D-C5 deletions: 5 unreachable defensive branches across extract_positional_fields/extract_regex_fields/extract_delimited_fields (pd.isna try/except for non-scalar containers; main_df backfill loops where columns are guaranteed present by construction)
- [Phase 14]: Plan 14-08 STALE-FOD-001 D-C5: deleted unreachable `except Exception` catch-all wrapping `pd.to_datetime(errors='coerce')` in file_output_delimited._apply_date_patterns (pandas contracts NEVER to raise with errors='coerce')
- [Phase 14]: Plan 14-08 D-RULE3 (Rule 3 deviation): added .gitignore negation `!tests/fixtures/jobs/**/*.json` -- the project-wide *.json rule had silently swallowed every fixture committed under tests/fixtures/jobs/ (Plan 14-01 scaffolding had not added the negation)
- [Phase 14]: Plan 14-11 STALE-INT-001: deleted legacy tests/converters/talend_to_v1/test_integration.py (378 lines) -- imported absent src.converters.complex_converter, broke -n auto collection. Originally deferred from 14-01; absorbed into 14-11 scope.
- [Phase 14]: Plan 14-11 documented 4 defensive unreachable branches as D-C5 candidates kept in source (expression_converter.py:134, foreach.py:42, xml_map.py:252-256/317) -- 95% floor cleared without source-level cleanup; future cosmetic deletion phase can revisit.
- [Phase 14]: Plan 14-06 BUG-PDC-001: PythonDataFrameComponent was unregistered with REGISTRY despite being importable -- engine silently dropped any tPythonDataFrame component as 'Unknown component type' in production. Fixed via @REGISTRY.register('PythonDataFrameComponent', 'tPythonDataFrame'). Also replaced ValueError with ConfigurationError + wrapped exec() failures in ComponentExecutionError per CLAUDE.md ETLError hierarchy.
- [Phase 14]: Plan 14-06 BUG-PDC-002: PythonDataFrameComponent did not implement BaseComponent's abstract _validate_config method -- the class was instantiable only because no test had previously exercised the contract. Added Rule-12 minimal validator (key presence; content checked lazily in _process).
- [Phase 14]: Plan 14-06 D-C5 deletions in transform/join.py: 3 sets of unreachable defensive branches (post-keep_cols _merge/lookup-key drops at lines 270-285; lk_col+'_lookup' / out_col-passthrough branches at lines 241-258; except (ConfigurationError, DataValidationError) re-raise at line 316). All 60 existing test_join.py cases pass unchanged after deletion; coverage rose from 94.5% (post-tests, with dead branches) to 100%.
- [Phase 14]: Plan 14-06 PARTIAL LIFT for map.py (73.8% -> 83.1%): the remaining 147 missed lines fall predominantly inside Java-bridge-driven paths (_join_context_only 863-917, _join_cross_table 941-1021, _join_reload_per_row 1088-1212, _evaluate_outputs_compiled 1307-1418, _evaluate_with_bridge 1912-1955). Closing the 12-pct gap requires @pytest.mark.java live-bridge tests not landable in single-plan scope. Documented in 14-06-SUMMARY with concrete remediation paths for Plan 14-13 closeout.
- [Phase 14]: Plan 14-07 BUG-SWIFT-001/002/003: SwiftBlockFormatter + SwiftTransformer + FileInputRaw were unregistered with REGISTRY (engine silently dropped them as 'Unknown component type'); both Swift classes lacked the BaseComponent.abstract _validate_config (uninstantiable via ABC); raises used ValueError/RuntimeError instead of ETLError subclasses. Fixed via decorators + ConfigurationError-raising _validate_config + ETLError raises across all error paths.
- [Phase 14]: Plan 14-07 BUG-SWIFT-004: both Swift components' init helpers read self.config which BaseComponent leaves empty until execute(); switched to self._original_config per ENG-09/ENG-21 contract. Pattern reusable for any future component whose __init__ needs to inspect config.
- [Phase 14]: Plan 14-07 BUG-SWIFT-005: pipeline-job JSON fixtures used unsupported \\${VAR} ctx-var syntax; ContextManager only resolves \\${context.VAR}. Affected 3 swift JSON fixtures + transform_with_lookup.yaml.
- [Phase 14]: Plan 14-07 D-C5 deletion: duplicate `_load_lookup_files` definition in swift_transformer.py (first one was a stub orphaned by the second def shadowing it); consolidated to a single real implementation.
- [Phase 14]: Plan 14-07 documented 12 defensive dict-coercion branches in swift_block_formatter (lines 565-573, 578-584, 694, 722) as unreachable guards. 95% floor cleared at 97.2%; future cleanup phase can delete or pragma-allowlist them.
- [Phase 14]: Plan 14-07 documented 9 missed lines in swift_transformer (139, 301-302, 453, 577-579, 599, 784-785) as defensive in-method exception paths covering ETL upstream malformation; 95% floor cleared at 98.0%.
- [Phase 14]: Plan 14-09 BUG-FIJ-001/002: FileInputJSON not registered with REGISTRY + missing abstract _validate_config -- same dual-bug pattern as BUG-SWIFT-001/002 (14-07), BUG-PDC-001/002 (14-06), BUG-AGG-001 (14-02). Production tFileInputJSON jobs silently dropped as "Unknown component"; ABC instantiation refused. Fixed via @REGISTRY.register('FileInputJSON', 'tFileInputJSON') decorator + Rule-12 _validate_config raising ConfigurationError. Plan 14-13 closeout should add plan-checker grep for BaseComponent subclasses missing either invariant.
- [Phase 14]: Plan 14-09 D-RULE3 extension: .gitignore !tests/fixtures/data/**/*.json negation added so deep-gap JSON fixtures (sample_data.json, sample_jsonpath.json) land in git. Project-wide *.json rule otherwise silently swallows them. Mirrors Plan 14-08 D-RULE3 for tests/fixtures/jobs/.
- [Phase 14]: Plan 14-09 documented 15 unreached lines in file_input_excel.py as defensive guards that pass shape validation but trip pd.read_excel / xlrd in ways no realistic input could trigger; 95% floor cleared at 97.4%. Future cleanup phase can D-C5 delete or pragma-allowlist them.
- [Phase 14]: Plan 14-10 BUG-JVM-001: test_bridge_integration.py module-scoped 'bridge' fixture used JavaBridge() with default port=25333; under -n auto every xdist worker except the first failed on bind(). Fixed by switching to JavaBridgeManager() (dynamic free port via socket.bind('', 0)). Resolves Plan 14-01 deferral. All 31 bridge_integration tests pass under 10 parallel workers.
- [Phase 14]: Plan 14-10 lifted all 7 engine-core modules to >=95% (4 at 100%: trigger_manager, base_iterate_component, engine, executor 95.2%; base_component 97.1%, python_routine_manager 98.0%, java_bridge_manager 99.0% via @pytest.mark.java per D-A3). 3 new core/ pipeline fixtures (trigger_runif, multi_subjob, reject_routing). NEW test modules: test_engine.py + test_java_bridge_manager.py.
- [Phase 14]: Plan 14-10 confirmed map.py PARTIAL LIFT (83.06%) NOT closed as side effect: the 3 new core pipeline fixtures use FixedFlowInput/SetGlobalVar/FileInput/FileOutput only, do not exercise tMap. Plan 14-13 closeout MUST address either via Plan 14-06b (live-bridge tMap tests under @pytest.mark.java) or amend the per-module floor with documented carve-out for map.py.

### Roadmap Evolution

- Phase 05.1 inserted after Phase 5: Java Bridge tMap Fix (URGENT) -- Phase 2 rewrite broke RowWrapper Arrow type conversion and compiled tMap script execution. Must fix before Phase 6+.
- Phase 07.1 inserted after Phase 7: Manager Audit & BaseComponent Fixes (URGENT) -- Manager-commit audit (range 52dbada..f0f6351, 19 commits, 28 files) surfaced 48 in-scope regressions and gaps including BaseComponent crashes (CR-01, CR-02), Phase 4 file I/O regressions (CR-03, CR-06, CR-09), Phase 6 AggregateRow Talend-parity violations (CR-05), broken Java build on Mac/Linux (CR-04 pom.xml), and a not-production-ready new Normalize component. API findings (27) skipped per direction. See .planning/review/TRIAGE.md for the full triage matrix and .planning/review/manager-commits-REVIEW*.md for evidence. Must complete before Phase 8.
- Phase 07.2 inserted after Phase 7: validate-config bug sweep -- move pre-resolution content checks to _process across 11 components (URGENT)
- Phase 05.3 inserted after Phase 5: tMap Join Correctness, Marker Rule, and Filepath Expression (URGENT)
- Phase 05.5 inserted after Phase 05.4: tMap context/globalMap bridge sync + __errors__ Arrow round-trip — fix per-row Java eval context/globalMap propagation (12-test spike regression) and Java-side __errors__ serialization (URGENT)

### Pending Todos

None yet.

### Blockers/Concerns

Non-blocking human verification carried from Phase 7.1 (do when convenient, not gating downstream phases):

- Linux/RHEL `mvn package` build (only Darwin verified)
- tNormalize combined-flags vs golden Talend job output
- FileOutputDelimited datetime default format vs Talend reference

Phase 8 deferred (single item -- non-blocking for Phase 10):

- D-08-01 (`src/v1/java_bridge/bridge.py:_capture_java_stderr` blocks on `read(65536)`) -- xfail wraps the affected real-bridge test; component-layer JROW-02 contract fully verified by mock-bridge test. Fix requires a future BRDG-* phase. Details: `.planning/phases/08-code-components/deferred-items.md`

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260425-uid | Rule 11 cleanup + manual-component authoring guide | 2026-04-25 | e4e5881 | [260425-uid-fix-rule-11-contract-violations-stale-te](./quick/260425-uid-fix-rule-11-contract-violations-stale-te/) |
| 260429-hc2 | Cleanup manager commits 43762c8 + c9be184/0c4104d (rewrite tests + audit docs for Talend parity, supersede CR-06) | 2026-04-29 | dc264d3 | [260429-hc2-cleanup-of-manager-commits-43762c8-c9be1](./quick/260429-hc2-cleanup-of-manager-commits-43762c8-c9be1/) |
| 260506-lqq | Fix bridge stderr pipe-buffer deadlock (D-08-01) -- background drainer thread + bounded ring buffer | 2026-05-06 | f0caf8b | [260506-lqq-fix-bridge-stderr-pipe-buffer-deadlock-d](./quick/260506-lqq-fix-bridge-stderr-pipe-buffer-deadlock-d/) |

### Phase 14 progress (2026-05-10) -- EXECUTING

- Plan 14-01 complete: pipeline-test infrastructure shipped
  - `tests/conftest.py` (root): `run_job_fixture`, `assert_ascii_logs`, `PipelineResult`, `FIXTURE_JOBS_ROOT`
  - `tests/fixtures/jobs/{file,transform,core,swift}/` + `tests/fixtures/data/` directory scaffolding (.gitkeep tracked)
  - `tests/fixtures/jobs/README.md` (JSON-job format + naming spec)
  - `scripts/check_per_module_coverage.py` (stdlib-only per-module 95% floor gate)
  - `pyproject.toml` `[tool.coverage.run|report|html|json]` blocks; explicit `pytest-cov>=7.0,<8` + `pytest-xdist>=3.8,<4` pins
  - `.gitignore`: `.coverage`, `.coverage.*`, `htmlcov/` added (Coverage artifacts section)
  - 5 commits (`145663c`, `d15de38`, `456e6da`, `541a805`, `4699a82`)
  - Smoke result: serial vs `-n auto` coverage equivalent (delta 0.00%) -- recorded in `14-PLAN-CHECK-NOTES.md`
  - Gate command verified: 52 modules below 95% (Phase 13 baseline expected ~53; off-by-one is `__init__` omit)
  - Pre-existing infrastructure issues surfaced (NOT regressions): `test_bridge_integration` xdist contention -> Plan 14-11; `test_integration.py` complex_converter ImportError -> Plan 14-12
- Plan 14-02 complete (2026-05-10): aggregate_row 79% -> >=95%; BUG-AGG-001 fix; D-C5 deletions; 2 commits.
- Plan 14-03 complete (2026-05-10): send_mail 60.2% -> 100.0%; BUG-MAIL-001 fix (attachment ETLError swallowed by outer except); 3 commits (`1c24b76`, `6b2b05c`, `d46907f`); per-module gate PASS for control subsystem (4/4 modules >=95%).
- Plan 14-04 complete (2026-05-10): oracle_output 94.1% -> 99.5%, oracle_row 90.3% -> 100.0%; no source changes; 2 commits (`d54b5c1`, `43d0b54`); per-module gate PASS for database subsystem (3/3 modules >=95%); Phase 11 testcontainer suite still gracefully skips at collection-time when testcontainers not installed.
- Plan 14-05 complete (2026-05-10): 12 transform modules lifted to 100.0% (replace, python_row_component, pivot_to_columns_delimited, parse_record_set, row_generator, python_component, extract_positional_fields, extract_regex_fields, convert_type, extract_json_fields, extract_delimited_fields, filter_rows -- baseline 80-94% all the way to 100% line coverage). 12 commits (`81315d0` -> `e5e696e`). BUG-EJF-001 source fix in extract_json_fields._is_null. 5 D-C5 dead-code deletions (3 pd.isna try/except, 2 main_df backfill loops). 1256 transform tests pass under -n auto. Per-module gate PASS for the 12 in-scope modules. Other transform modules (map, join, python_dataframe_component, swift_*) still below 95% as expected; closed by Plans 14-06 / 14-07.
- Plan 14-08 complete (2026-05-11): 12 file/* modules lifted from 81-94% to >=99.5% (10 at 100.0%, file_input_delimited 99.5%, file_output_positional 99.6%). 17 commits (`7733ee1` D-RULE3 unignore -> `2a0775b` final lift). STALE-FOD-001 D-C5 deletion (file_output_delimited.py:364 unreachable date-coerce catch-all). 3 new pipeline fixtures under `tests/fixtures/jobs/file/`. D-RULE3 .gitignore unblock for `!tests/fixtures/jobs/**/*.json` (Rule 3 deviation -- the project-wide *.json rule was silently ignoring every fixture). 1182 file tests pass under -n auto. Per-module gate PASS for the 12 in-scope modules; the 4 deep-gap modules (file_input_excel, file_input_json, file_input_raw, file_output_excel) remain below 95% per plan scope and are closed by Plan 14-09.
- Plan 14-11 complete (2026-05-11): 8 converter-side modules lifted from 78-97% to >=97.2% (5 at 100.0%, expression_converter 98.9%, xml_map 98.1%, foreach 97.2%). 9 commits (`a2a897c` STALE-INT-001 -> `a5465cc` mssql_input). STALE-INT-001 deletion of legacy tests/converters/talend_to_v1/test_integration.py (importing absent src.converters.complex_converter -- a deferred-from-14-01 issue). New test module tests/converters/talend_to_v1/test_expression_converter.py (65 tests). 4 defensive unreachable lines documented as D-C5 candidates kept in source. Per-module gate PASS for the 8 in-scope modules; 2 out-of-scope transform modules (log_row 94.4%, join 94.7%) remain below 95% and are tracked for Plan 14-06.
- Plan 14-06 complete (2026-05-11): 3 of 4 transform deep-gap modules at 100% line coverage (join.py 69.2%->100%, python_dataframe_component.py 19.6%->100%, log_row.py 96.7%->100%). map.py PARTIAL lift 73.8%->83.1% (147 missed lines remain, all in Java-bridge-driven paths: _join_context_only / _join_cross_table / _join_reload_per_row / _evaluate_outputs_compiled / _evaluate_with_bridge -- require @pytest.mark.java live-bridge tests). 9 commits (`8dac42c` BUG-PDC-001 -> `16556db` COV-MAP-001). 2 BUG-PDC source fixes: BUG-PDC-001 (PythonDataFrameComponent unregistered with REGISTRY -- engine.py silently dropped it as 'Unknown component type' in production!) + BUG-PDC-002 (missing abstract _validate_config). 1 D-C5 source cleanup: 3 sets of unreachable defensive branches deleted from join.py (_merge / lookup-key drops post-keep_cols filter, lk_col + '_lookup' / out_col-passthrough branches, ConfigurationError/DataValidationError re-raise). 2 new pipeline fixtures (transform/map_with_lookup.json, transform/join_with_reject.json) + 4 pipeline tests (D-C1) using run_job_fixture. map.py 95% gap deferred to Plan 14-13 closeout (either spawn 14-06b live-bridge sweep, fold into 14-13, or amend the per-module floor with documented carve-out).
- Plan 14-09 complete (2026-05-11): 4 file deep-gap modules lifted from 9-69% to >=97.4% (3 at 100%, file_input_excel.py at 97.4%). 9 commits (`709cd33` INFRA-FX-004 -> `e9c2cbe` COV-FIR-001). 2 BUG-FIJ source fixes (registration + abstract method). 7 real binary/text fixtures + 3 pipeline-job fixtures committed. .gitignore D-RULE3 negation extended to tests/fixtures/data/**/*.json. 1402 tests pass under -n auto across file/ + integration/. Per-module gate PASS for all 26 file modules at 95% floor.
- Plan 14-10 complete (2026-05-11): all 7 engine-core modules lifted to >=95% (4 at 100%: trigger_manager 91.3% -> 100%, base_iterate_component 90.7% -> 100%, engine 88.6% -> 100%, executor 91.0% -> 95.2%; base_component 80.7% -> 97.1%, python_routine_manager 81.6% -> 98.0%, java_bridge_manager 52.5% -> 99.0% under @pytest.mark.java per D-A3). 11 commits (`0e62be6` INFRA-CORE-001 -> `bb2a81d` BUG-JVM-001). 3 new core/* pipeline fixtures (trigger_runif, multi_subjob, reject_routing). NEW test modules: test_engine.py (18 tests) + test_java_bridge_manager.py (16 @pytest.mark.java tests). Resolved Plan 14-01 deferred JVM contention in test_bridge_integration.py by switching the module-scoped 'bridge' fixture from JavaBridge() (default port 25333) to JavaBridgeManager() (dynamic free port). All 31 bridge_integration tests now pass under -n auto with 10 workers. Per-plan gate exits 0 for the 7 in-scope modules; map.py remains at 83.06% (out-of-scope, Plan 14-06 deferral unchanged because core fixtures don't exercise tMap).
- Plan 14-06b complete (2026-05-11): Plan 14-06 PARTIAL LIFT deferred gap RESOLVED. map.py 79.6% -> 95.85% via two-phase test addition: (1) TestPlan1406bUnitGapClosure (26 unit tests appended to test_map.py) covering branches reachable without a JVM (84.9% interim), and (2) NEW tests/v1/engine/components/transform/test_map_bridge.py (16 @pytest.mark.java tests using session-scoped java_bridge fixture from tests/v1/engine/conftest.py) covering _evaluate_outputs_compiled, _join_context_only, _join_cross_table, _join_reload_per_row deeper paths, _evaluate_with_bridge edges. 2 commits (`64ef401` unit lift, `7a1faf9` bridge lift). No source changes; pure test addition. Per-module gate now reports map.py PASS at 95.85%.
- COV-CJ-001 (2026-05-11): converter join.py 94.7% -> 100% via 1 test addition (`d661c1f`); incidental cleanup before closeout.
- Plan 14-12 complete (2026-05-11): closeout shipped. 8 commits: chore(14-12) INFRA-CLOSE-001 commit 14-coverage.json (+ .gitignore D-RULE3 negation for .planning/phases/**/*coverage.json); docs(14-12) DOC-COV-001 14-COVERAGE.md; docs(14-12) DOC-CLAUDE-001 CLAUDE.md coverage section update; docs(14-12) DOC-REQ-001 TEST-11/TEST-12 -> Complete; docs(14-12) DOC-ROAD-001 ROADMAP Phase 14 SC#2 D-E1 wording + 12/12 Complete; docs(14-12) DOC-STATE-001 STATE.md Phase 14 -> complete; docs(14-12) DOC-VER-001 14-VERIFICATION.md acceptance evidence; docs(14-12) DOC-SUMMARY-001 14-PHASE-SUMMARY.md retrospective. Final gate command exits 0 with `PASS: all 181 in-scope modules at >= 95.0% line coverage`; overall 98.3% (16746/17033 stmts); 100 modules at perfect 100.0%; no-regression check confirms all Phase 13 PASS modules still PASS; iterate/context per locked Q2 merge both PASS; zero inline `# pragma: no cover` annotations in scope (D-C3 enforced via pyproject exclude_also). Phase 14 closed.

### Phase 05.4 closed (2026-05-15)

- 8 plans, 5 waves
- Goal: restore tMap reject-routing fidelity (3 reject mechanisms) + Groovy-safety audit + reject-path fragmentation cleanup. Regression introduced by Phase 5 "rewrite from scratch" commit `9ab8120`; both `origin/main` and Talaxie codegen got it right; current branch was the outlier.
- 11/11 SPEC.md acceptance criteria PASS per `05.4-VERIFICATION.md` (with 6 strict-xfail tests pinning two documented compiled-path deferrals)
- Key deliverables:
  - `_evaluate_output_columns_py` shared helper extracted (D-01)
  - `_route_inner_join_rejects` rewritten with `_NullRow` sentinel for partial-match binding (R1, R5, R7)
  - `is_reject` filter-reject routing in `_evaluate_outputs_py` + `_apply_output_filter` rewritten (R2)
  - `_route_catch_output_rejects` rewritten with D-06 reserved-column policy (R3)
  - `_groovy_escape_expression` helper + 10 retrofitted embed sites in `_build_compiled_script` (R6)
  - Per-reject-output method emission in compiled script + Option A dual-invocation dispatch (D-09)
  - 5 new test files (60+ tests) + e2e fixture `Job_05_4_inner_reject.item` (D-08)
  - D-10 assertion strengthening at 4 sites in `test_map_bridge.py`
  - 05.4-GROOVY-AUDIT.md enumerating Groovy-vs-Java parsing differences
- Coverage: map.py 88.3% (Phase 05.3 baseline) -> 88.7% (improved by +0.4pp; SPEC R11 met). py_map.py 81.1% -> 80.6% (pre-existing below floor, not introduced by 05.4). No new below-floor modules.
- Test counts: full suite 8231 passed, 5 skipped, 7 xfailed under -n auto. Phase 05.4 java-marked subset: 48 passed, 6 xfailed (all strict, all documented).
- Requirements: R1-R7 met. MAP-02 and MAP-05 in REQUIREMENTS.md were already Complete at Phase 5 close; Phase 05.4 fixes a regression in their implementation without changing the requirement status.
- Deferred items (3, all documented):
  - Compiled-path active-mode filter-reject (4 strict-xfail tests; requires `_build_compiled_script` to emit filter-reject inside `rejectMode=false` row loop)
  - Compiled-path D-06 enforcement (2 strict-xfail tests; requires Java bridge to unpack `__errors__` row data back to Python)
  - Cross-table predicate boolean-vs-key-value quirk (inline pinned; pre-existing semantic mismatch, out of scope)
- Plus pre-deferred: 4 other fragmentation sites in join-construction code; Phase 05.3 D-07 empty-lookup nullable=false.
- Phase 16 handoff: real Talend end-to-end runs + output diffs + tMap/tFilterRow perf refactor (manager-led, requires Talend Open Studio).

### Phase 15.1 closed (2026-05-11)

- 12 plans, 3 waves (per-component Wave 1, cross-cutting Wave 2, closeout Wave 3), ~79 commits total
- 66 per-component audit docs reconciled (aggregate 2, context 1, iterate 1, database 3, file 24, transform 35)
- 1 net-new audit doc authored: docs/v1/audit/components/file/tFileOutputXML.md (D-A4)
- 3 cross-cutting docs regenerated with section shape preserved: SUMMARY_SCORECARD.md (36G/29Y/2R shipped), CROSS_CUTTING_ISSUES.md (28 struck/14 STILL LIVE), METHODOLOGY.md (Talaxie-diff 8-step workflow)
- 20 non-shipped audit docs intentionally untouched per D-A5 (control x9, database x8, file x1, iterate x1, transform x1)
- Phase 14 coverage gate confirmed clean at phase close: PASS: all 181 in-scope modules at >= 95.0% line coverage (zero src/ modifications, D-E1)
- [NEW IN 15.1] findings backlog: 14 findings including ENG-WR-005 (tFileOutputXML no REJECT, P1), ENG-NRM-001 (tNormalize key mismatch, P2), FL-GAP-001 (tFileList missing globalMap vars, P2)
- 9 cross-cutting STILL LIVE items enumerated: streaming stateful-component gaps (4.2-4.4), error-handling gaps (2.2-2.4), context edge cases (5.5-5.6), trigger edge case (3.4)
- Constraints honored: D-A1 (shipped-only), D-A5 (non-shipped untouched), D-C1 (strike-through with phase tag), D-C4 (ASCII-only), D-C5 (Reconciled header), D-C6 (atomic commits), D-D1 (section-shape-preserving), D-D2 (cross-cutting last), D-E1 (doc-only), D-E2 (coverage gate), D-E6 (manual checkpoint)
- REQUIREMENTS.md: DOCS-03 added and marked Complete (v1 requirement count 129 -> 130)
- Phase 16 handoff: real Talend end-to-end runs + output diffs + tMap/tFilterRow perf refactor (manager-led, requires Talend Open Studio)

### Phase 15 closed (2026-05-11)

- 10 plans, 4 waves (0/1/2/3), ~30 commits total
- 22 top-level docs/ files deleted; 4 canonical docs at docs/ root; root README.md added
- 4 standards-zone files dropped (STANDARDS, METHODOLOGY, AUDIT_REPORT_TEMPLATE, NEXT_MILESTONE_GUIDE; 2187 lines removed)
- 7 standards-zone files patched (TBD placeholder removed, Phase 14 pipeline-test pattern added, Rule 13 registry+abstract added, BaseComponent-Info gaps disambiguated, talend_to_v1_converter_guide swept)
- Folder rename: docs/v1/standards/ -> docs/v1/patterns/ (history-preserving `git mv`)
- File move: docs/v1/BaseComponent-Info.md -> docs/v1/patterns/BaseComponent-Info.md
- talend_to_v1_converter_guide.md retained at docs/v1/ per planner D.7
- 15-VERIFICATION.md + 15-PHASE-SUMMARY.md committed
- REQUIREMENTS.md: DOCS-01 + DOCS-02 marked Complete (v1 requirement count 127 -> 129)
- Doc-only phase per D-E3: zero src/ modifications; Phase 14 coverage gate still PASS at 95% per-module floor (181 in-scope modules, overall 98.3%)
- Constraints honored: D-A4 (audit/ untouched), D-B4 (CLAUDE.md untouched), D-C1 (ASCII-only), D-C2 (Last-updated header on every new/edited doc), D-E1 (atomic commits), D-E2 (verify-before-claim), D-E3 (doc-only)
- Phase 15.1 handoff: broken-cross-reference inventory enumerated in 15-07-SUMMARY.md (~25 unique audit/ files de-duplicated across 4 dropped docs; 23 audit/ files still reference docs/v1/standards/ path post-rename per 15-09-SUMMARY.md). Researcher's ~84 estimate corrected by ground-truth grep.

### Phase 14 closed (2026-05-11)

- 12 plans + 14-06b follow-on + COV-CJ-001 incidental; ~88 commits
- 181 in-scope modules at >=95.0% line coverage; overall 98.3% (16746/17033 stmts); 100 modules at 100.0%; zero modules below floor
- Key artifacts: 14-COVERAGE.md (final per-module table), 14-coverage.json (machine-readable acceptance artifact, locked Q4), 14-VERIFICATION.md, 14-PHASE-SUMMARY.md, scripts/check_per_module_coverage.py, tests/conftest.py root, tests/fixtures/jobs/ + tests/fixtures/swift/ + tests/fixtures/data/
- Key decisions: D-A1 SWIFT engine in scope; D-A3 java_bridge_manager measured WITH `-m java`; D-A4 send_mail boundary mocks; D-A6 Oracle mocks (testcontainer suite stays opt-in via `-m oracle`); D-C1 multi-component pipeline tests for lifecycle modules; D-C2 fixture-jobs JSON format mirrors converter output; D-C3 pragma allowlist enforced via pyproject exclude_also regexes; D-C5 dead-code deletion preferred over pragma; D-D1 12-plan subsystem split; D-D3 uniform 95% floor; D-D4 pytest-xdist `-n auto` for parallelism; D-E1 paste-runnable gate command (operational CI deferred); D-E3 13-COVERAGE-BASELINE.md stays archived; D-E4 pyproject coverage config blocks; locked Q2 iterate/context modules already >=95% so 14-04 merged into 14-12 no-regression check; locked Q4 commit `14-coverage.json` per phase; locked Q5 `rm -f .coverage*` prefix required to avoid stale shard contamination
- 8 deep-gap modules closed (<50% baseline): SWIFT 7%->97-98%, file_input_json 9%->100%, python_dataframe_component 20%->100%, file_input_excel 29%->97.4%, file_input_raw 15%->100%, java_bridge_manager 59%->99%, send_mail 60%->100%, file_output_excel 69%->100%
- Bug fixes during the lift (root-cause source patches; project rule "fix source, no fallbacks"): BUG-AGG-001 (aggregate_row null-bearing list/list_object/union crash), BUG-MAIL-001 (send_mail attachment ETLError swallowed by outer except), BUG-EJF-001 (extract_json_fields _is_null TypeError-only catch), BUG-PDC-001/002 (PythonDataFrameComponent unregistered + missing abstract _validate_config), BUG-SWIFT-001..005 (5 fixes: both Swift components unregistered + abstract method + ValueError->ETLError + __init__ reading empty self.config), BUG-FIJ-001/002 (FileInputJSON unregistered + abstract method), BUG-JVM-001 (test_bridge_integration JavaBridge() default-port contention under -n auto -- switched to JavaBridgeManager() dynamic free port), BUG-CONV-001 source patch carrying in from Phase 13 lineage
- 12+ D-C5 dead-code deletions across 14-02, 14-05, 14-06, 14-07, 14-08
- 2 STALE deletions: STALE-INT-001 (legacy tests/converters/talend_to_v1/test_integration.py importing absent complex_converter), STALE-FOD-001 (unreachable except Exception in file_output_delimited._apply_date_patterns)
- D-RULE3 .gitignore negations added across the phase: !tests/fixtures/jobs/**/*.json (14-08), !tests/fixtures/data/**/*.json (14-09), !.planning/phases/**/*coverage.json (14-12)
- Requirements TEST-11 and TEST-12 marked Complete
- No-regression check: all Phase 13 PASS modules still PASS; iterate/context per locked Q2 merge both >=95%

### Phase 13 closed (2026-05-10)

- 9 plans, 5 waves
- 4 CODE-CHANGE root-cause patches: BUG-BRDG-001 (Groovy script generation), BUG-BRDG-002 (BaseComponent.reset() GlobalMap wipe), BUG-BRDG-003 (executor finalization over-reset), BUG-EXC-001 (FileOutputExcel defensive read), BUG-UNIQ-001 (unique_row pandas 3.0 StringDtype), BUG-CT-001 (convert_type MANUALTABLE numeric fallback), BUG-FL-001 (file_list NB_FILE finalize put)
- 2 TEST-CHANGE updates: aggregate_row NeedsReview count (>= 3 -> >= 1), regex_custom storage convention (double- to single-backslash)
- 10 STALE deletions: NeedsReview tests for engine-implemented features across 3 converter test files
- Java bridge JAR rebuilt from May 5/8 manager source (executeOneTimeExpression signature aligned)
- Test suite: 6832 passed, 26 skipped, 1 xfailed, 0 failed
- Per-module coverage baseline recorded in 13-COVERAGE-BASELINE.md (75% overall, 145/198 modules >= 95%)
- 53 modules below 95% handed off to Phase 14 as lift targets
- Requirements TEST-09 and TEST-10 added and marked Complete

### Phase 12 closed (2026-05-08)

- 8 plans, 6 waves
- 4 input components hardened: tFileInputXML (lxml migration), tFileInputMSXML (build-from-scratch), tExtractXMLField (harden + secure parser), tXMLMap (heavy fix incl. BUG-XMP-003)
- 2 output components built: tFileOutputXML (simple/flat), tAdvancedFileOutputXML (hierarchical)
- 12 conditional needs_review entries on the converter (D-E1 lock-in)
- Per-module 95%+ line coverage achieved (97% overall, all 7 modules >= 95%)
- 8 E2E tests (6 per-component + 2 D-E1 warn baseline), all pass
- Java bridge unchanged per D-E2 (JAR rebuild deferred to Phase 13)
- 43 OPEN audit items from 12-01-AUDIT.md closed across plans 12-03..12-07

## Session Continuity

Last session: 2026-05-15T14:30:00.000Z
Stopped at: Phase 05.4 complete (8/8 plans; verification report + phase summary committed)
Resume with: Phase 16 (Integration Testing & Performance, manager-led) requires Talend Open Studio access and is out of GSD-executor scope. For follow-up work on the documented Phase 05.4 deferrals (compiled-path active-mode filter-reject; compiled-path D-06 reserved-column enforcement; cross-table boolean predicate; remaining 4 fragmentation sites; Phase 05.3 D-07 empty-lookup nullable=false), spin up new phases per /gsd-init-phase.
