---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 14 Plan 11 complete -- 8 converter modules lifted to >=97% (5 at 100%, 2 at 98%+, 1 at 97.2%); STALE-INT-001 legacy complex_converter import resolved; 9 commits
last_updated: "2026-05-11T20:30:00Z"
last_activity: 2026-05-11
progress:
  total_phases: 20
  completed_phases: 18
  total_plans: 87
  completed_plans: 92
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-14)

**Core value:** Any Talend job using the target components must produce identical results when run through the Python engine
**Current focus:** Phase 14 — coverage-push-to-95-per-module-floor

## Current Position

Phase: 14 (coverage-push-to-95-per-module-floor) — EXECUTING
Plan: 12 of 13 (9 of 13 complete -- Plan 14-11 lands; Plans 14-06 / 14-07 / 14-09 / 14-10 / 14-12 / 14-13 still pending)
Next: Phase 14 Plan 06 (transform deep gaps non-SWIFT) OR Plan 14-09 (file deep gaps: excel/json/raw)
Status: Ready to execute
Last activity: 2026-05-11

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

### Roadmap Evolution

- Phase 05.1 inserted after Phase 5: Java Bridge tMap Fix (URGENT) -- Phase 2 rewrite broke RowWrapper Arrow type conversion and compiled tMap script execution. Must fix before Phase 6+.
- Phase 07.1 inserted after Phase 7: Manager Audit & BaseComponent Fixes (URGENT) -- Manager-commit audit (range 52dbada..f0f6351, 19 commits, 28 files) surfaced 48 in-scope regressions and gaps including BaseComponent crashes (CR-01, CR-02), Phase 4 file I/O regressions (CR-03, CR-06, CR-09), Phase 6 AggregateRow Talend-parity violations (CR-05), broken Java build on Mac/Linux (CR-04 pom.xml), and a not-production-ready new Normalize component. API findings (27) skipped per direction. See .planning/review/TRIAGE.md for the full triage matrix and .planning/review/manager-commits-REVIEW*.md for evidence. Must complete before Phase 8.
- Phase 07.2 inserted after Phase 7: validate-config bug sweep -- move pre-resolution content checks to _process across 11 components (URGENT)

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
- Plans 14-06..14-07, 14-09..14-10, 14-12..14-13: pending. Next is Plan 14-06 (transform deep gaps non-SWIFT: map.py 77%, join.py 69%, python_dataframe_component.py 20%, log_row 94.4% spillover from 14-11) OR Plan 14-09 (file deep gaps: excel/json/raw).

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

Last session: 2026-05-11T20:30:00Z
Stopped at: Phase 14 Plan 11 complete -- 8 converter-side modules lifted to >=97.2% (5 at 100%, 2 at 98%+, 1 at 97.2%); STALE-INT-001 legacy complex_converter import resolved; 9 commits
Resume with: /gsd-execute-phase 14 (continue with Plan 14-06 transform deep gaps non-SWIFT, or Plan 14-09 file deep gaps excel/json/raw)
