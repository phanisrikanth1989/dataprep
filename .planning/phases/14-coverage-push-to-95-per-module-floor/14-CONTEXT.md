# Phase 14: Coverage Push to 95% per-module floor — Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Lift every Phase 13–baselined module under `src/v1/engine/` and `src/converters/` to a **>=95% line-coverage floor** by writing real-behavior tests (mix of unit + multi-component pipeline tests). Replace `13-COVERAGE-BASELINE.md` with a final `14-COVERAGE.md` and document the paste-runnable gate command.

**In scope:**
- 53 modules currently below 95% across 10 subsystems (file / transform / aggregate / control / context / iterate / database / engine-core / converter-core / converter-components)
- New pipeline-test infrastructure: fixture loader for `tests/fixtures/jobs/*.json`, conftest helpers, JSON job templates that mirror converter output
- Synthetic SWIFT MT message generator (~800 stmts of SWIFT logic = the biggest single lift)
- Boundary-mock patterns for `smtplib` (send_mail) and `oracledb` (oracle_output, oracle_row)
- Final `14-COVERAGE.md` with per-module post-lift numbers (replaces `13-COVERAGE-BASELINE.md`)
- Documented paste-runnable gate command in CLAUDE.md and `14-COVERAGE.md`
- Two new requirement IDs for the coverage push (TEST-11 / TEST-12, planner to finalize labels)

**Out of scope (deferred):**
- **CI workflow file** (GitHub Actions / Jenkinsfile / pre-commit) — user-scoped out for Phase 14. Roadmap success criterion #2 ("CI gate enforces the 95% floor on every PR; below-threshold modules block merge") is amended: Phase 14 ships a "wired and reproducible" paste-runnable command (same pattern as Phase 13 D-E2). Operational CI lands in a future phase.
- Phase 15 work: real .item E2E + Talend output comparison (TEST-05/TEST-06)
- Phase 16 work: documentation sweep
- New components or features (pure stabilization of test surface)
- Branch coverage (line coverage only — Phase 13 D-E2 reasoning carries)
- Property-based testing (Hypothesis) — deferred; standard tests sufficient for 95% floor
- aiosmtpd in-process SMTP server fixtures — deferred; smtplib boundary mocks sufficient
- Real Oracle testcontainer integration (Phase 11 verification debt stays human-run)
- Removal of `complex_converter` modules (legacy, N/A for the gate)

</domain>

<decisions>
## Implementation Decisions

### Module scope universe (Area A)

- **D-A1: SWIFT engine modules in scope.** `swift_transformer.py` (7%) and `swift_block_formatter.py` (7%) — both registered in `engine/components/transform/__init__.py`. ~800 stmts combined of new test surface. Despite PROJECT.md noting "Python and swift componemts skipped for converter," the engine registers and ships them, so production safety requires the 95% bar.
- **D-A2: file_input_json (9%), file_input_raw (15%), python_dataframe_component (20%) all in scope.** Engine registers them; UI registry references them; no PROJECT.md exclusion. Full lift required.
- **D-A3: java_bridge_manager.py measured WITH `-m java` markers.** CI / gate command requires JVM 11+ in the executing environment. Aligns with project memory rule "test real bridge, not mocks" (project_test_real_bridge.md). Phase 02 verification debt naturally closes when the gate runs in an environment with JVM. Gate command: `pytest tests/ -m "not oracle" --cov=src/v1/engine --cov=src/converters ...` (excludes Oracle, includes Java).
- **D-A4: send_mail.py uses smtplib boundary mocking.** Mock `smtplib.SMTP` / `smtplib.SMTP_SSL` only; component-internal logic (config parsing, recipient handling, attachment construction, MIME building, error path translation) tested with real code paths. Standard outbound-transport pattern.
- **D-A5: SWIFT fixtures = synthetic per the SWIFT user-handbook spec.** Planner generates representative MT103 / MT202 / MT940 (and any other forms the engine code branches on) from the published SWIFT message structure. No production samples required. Synthetic fixtures must exercise every branch in `swift_transformer.py` and `swift_block_formatter.py`. If any code branch can't be hit with a synthetic message — flag as dead code and apply the standard "delete vs cover vs pragma" decision (see D-C5).
- **D-A6: Oracle modules use mocked `oracledb`.** `oracle_output.py` (94%) and `oracle_row.py` (90%) lift to 95% via mocked connection/cursor. Diverges from the "real bridge" stance for `java_bridge_manager` because (a) Phase 11 already paid the real-DB price (testcontainer suite is the verification path, not the coverage path), (b) Oracle live tests stay human-run via Phase 11 debt, (c) coverage gate stays env-independent for Oracle. The unit test surface mocks at the connector boundary; live integration stays in the `-m oracle` opt-in suite.

### Test strategy & pragma policy (Area C)

- **D-C1: Multi-component pipeline tests where they're the natural fit.** For modules where lifecycle / globalMap / trigger / routing semantics matter (file_input_*, file_output_*, iterate components, tMap variants, executor.py, base_component.py, base_iterate_component.py, trigger_manager.py, engine.py) write 2–5 small JSON-job pipeline tests per subsystem. Pure-pandas transforms (filter_rows, sort_row, aggregate_row, join, unite, denormalize, normalize, etc.) stay as direct `_process()` unit tests — no lifecycle dependency.
- **D-C2: Pipeline tests load fixture .json files from `tests/fixtures/jobs/`.** File format mirrors converter output (the format `ETLEngine` actually consumes in production). Test code reads the fixture via a conftest helper and runs it through `ETLEngine.execute()`. Pattern mirrors `tests/integration/test_iterate_e2e.py`. Naming convention: `tests/fixtures/jobs/{subsystem}/{behavior}.json` (e.g., `tests/fixtures/jobs/file/csv_with_header.json`).
- **D-C3: Pragma allowlist (narrow).** `# pragma: no cover` is allowed only on:
  - `if __name__ == "__main__":` blocks
  - `@abstractmethod`-decorated methods that raise `NotImplementedError`
  - `try: import optional_dep / except ImportError:` shims for optional dependencies (lxml, oracledb, openpyxl, etc.)
  Anything else is disallowed (logic branches, error paths, defensive guards on internal-only code). Reviewers reject pragmas outside the allowlist.
- **D-C4: Pure-pandas transforms — real-shape tests + targeted edge cases.** DataFrames must use realistic dtype mixes (object, StringDtype, Int64, datetime64, Decimal, float64) to surface pandas 3.0 / CoW behavior. Every error branch must be hit with malformed input that raises the documented custom exception (ETLError subclasses); tests assert exception type AND message-shape, not just `pytest.raises(Exception)`.
- **D-C5: Dead-code policy.** When a code branch can't be reached by any realistic test, prefer **delete the dead branch** over `# pragma: no cover` over invented test setup. Aligns with project memory "rewrite over patch" and "fix source, no fallbacks". Document each deletion in the relevant plan's SUMMARY.md so reviewers can re-litigate.

### Plan / wave structure & ordering (Area D)

- **D-D1: ~12 plans total, sliced by subsystem.** Per Phase 13 baseline grouping:
  1. **14-01: Pipeline-test infrastructure** — fixture loader, conftest helpers, JSON job templates, `tests/fixtures/jobs/` scaffolding. Prerequisite for any subsystem plan that needs pipeline tests.
  2. **14-02: engine.components.aggregate** — `aggregate_row.py` (79%) — single below-95 module; quick subsystem.
  3. **14-03: engine.components.control** — `send_mail.py` (60%) with smtplib boundary mocks.
  4. **14-04: engine.components.iterate / context** — currently both subsystems already at >=95% per baseline; this plan may be a quick "no regression" check or merged into 14-09.
  5. **14-05: engine.components.database** — `oracle_output.py` (94%), `oracle_row.py` (90%) with oracledb boundary mocks.
  6. **14-06: engine.components.transform (quick wins + medium gaps)** — replace, python_row_component, pivot, parse_record_set, row_generator, python_component, extract_*, convert_type, filter_rows. ~13 modules in 80–94% range.
  7. **14-07: engine.components.transform (deep gaps — non-SWIFT)** — `map.py` (77%), `join.py` (69%), `python_dataframe_component.py` (20%). Heavier lift; pipeline tests likely.
  8. **14-08: engine.components.transform (SWIFT)** — `swift_transformer.py` (7%) + `swift_block_formatter.py` (7%) + synthetic SWIFT MT generator. Largest single plan by stmt count.
  9. **14-09: engine.components.file (quick wins + medium gaps)** — file_list, file_unarchive, file_properties, file_copy, file_input_properties, fixed_flow_input, set_global_var, file_input_delimited, file_output_delimited, file_output_positional, file_input_positional, file_touch. ~12 modules.
  10. **14-10: engine.components.file (deep gaps)** — `file_output_excel.py` (69%), `file_input_excel.py` (29%), `file_input_json.py` (9%), `file_input_raw.py` (15%). Real fixture files (.xlsx, .csv, .json) required.
  11. **14-11: engine core** — `trigger_manager.py` (91%), `executor.py` (91%), `base_iterate_component.py` (88%), `base_component.py` (87%), `python_routine_manager.py` (82%), `engine.py` (81%), `java_bridge_manager.py` (59%). Pipeline tests + `-m java` tests for the bridge manager.
  12. **14-12: converters** — `converter.py` (94%), `expression_converter.py` (78%), `mssql_input.py` (81%), `xml_map.py` (93%), `replace.py` (94%), `aggregate_row.py` (91%), `foreach.py` (94%), `file_input_excel.py` (94%). All converter-side modules below 95%.
  13. **14-13: closeout** — measure final per-module coverage, write `14-COVERAGE.md`, update CLAUDE.md gate command, flip ROADMAP.md, update REQUIREMENTS.md (TEST-11/TEST-12), `14-VERIFICATION.md`, `14-PHASE-SUMMARY.md`.

  Planner may merge or split plans during planning; the constraint is "by subsystem, infra first, closeout last."

- **D-D2: Plan order = Infra → Quick wins → Medium → Deep gaps → Closeout.** Plan 14-01 (infra) blocks every multi-component plan. Quick wins (14-02, 14-04, parts of 14-06, 14-09, 14-12) build momentum and shake out fixture issues with low-risk modules. Medium gaps next. Deep gaps (14-08 SWIFT, 14-10 Excel/JSON/raw, 14-11 core including java_bridge_manager) last when patterns are mature. Plan-checker enforces this order via `Depends on:` annotations.
- **D-D3: Uniform 95% floor — no module drops below 95%.** All 198 in-scope modules (53 below + 145 at-or-above) must end at >=95%. Phase 14 closeout fails if any current PASS regresses below 95%. Future phases inherit the same uniform rule.
- **D-D4 (Claude's call): pytest-xdist `-n auto` + `@pytest.mark.slow` for tests >5s.** pytest-xdist already in deps (dev extra). pytest-cov 7 + xdist combine cleanly. The gate command becomes `pytest tests/ -m "not oracle" -n auto --cov=src/v1/engine --cov=src/converters --cov-report=term-missing --cov-report=html`. Coverage stays priority — never trade coverage of a real production path for runtime savings. Tests >5s get the existing `slow` marker (pyproject already has it) so devs can opt out for fast feedback loops, but the gate command runs the full set.

### Roadmap / requirements adjustments

- **D-E1: Roadmap SC#2 amended.** Replace "CI gate enforces the 95% floor on every PR; below-threshold modules block merge" with "Paste-runnable gate command documented in `14-COVERAGE.md` and CLAUDE.md; running the command verifies the 95% floor." This mirrors Phase 13 D-E2's stance. Operational CI gets a future phase.
- **D-E2: Two new requirement IDs.** Planner adds **TEST-11** (coverage push to 95% per-module floor) and **TEST-12** (paste-runnable gate command + COVERAGE.md). Exact text TBD by planner; both flip to `Complete` at phase closeout.
- **D-E3: COVERAGE.md replaces COVERAGE-BASELINE.md.** Final per-module table lives in `.planning/phases/14-coverage-push-to-95-per-module-floor/14-COVERAGE.md`. Phase 13's baseline file stays archived in its own phase dir for diff/audit purposes.
- **D-E4: Coverage tool config in pyproject.toml.** Add `[tool.coverage.run]` (source = src/v1/engine, src/converters; omit = src/converters/complex_converter) and `[tool.coverage.report]` (fail_under is NOT set globally — per-module gate is enforced via the documented command + final table). Branch coverage stays off.

### Claude's Discretion

- Plan / wave decomposition fine-tuning (planner may merge 14-04 into 14-09, or split 14-08 into per-SWIFT-component plans, etc.)
- Specific fixture file names and JSON job shapes
- Exact TEST-11 / TEST-12 wording (subject to user review at planner gate)
- The pytest invocation flag set in the documented gate command (default markers, additional `-q`/`-v` toggles, etc.)
- STALE-test cleanup if encountered: apply Phase 13 D-D1 pattern (delete tests for engine-implemented features, log under STALE-NN in plan summaries)
- Whether `python_dataframe_component.py` (20%) needs synthetic DataFrame fixtures or if existing test patterns scale up cleanly

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 13 handoff (the explicit predecessor — REQUIRED reading)
- `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-COVERAGE-BASELINE.md` — Per-module floor table (the source of truth for Phase 14 lift targets); reproducible measurement command; lift target count summary; notable low-coverage list
- `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-CONTEXT.md` — D-D1 STALE policy, D-E1 baseline scope, D-E2 documented-command pattern that Phase 14 follows
- `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-PHASE-SUMMARY.md` — Phase 13 retrospective + final state
- `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-VERIFICATION.md` — Phase 13 acceptance evidence

### Project & Architecture
- `.planning/PROJECT.md` — Core value (Talend feature parity); SWIFT note ("Python and swift componemts skipped for converter") informs D-A1
- `.planning/REQUIREMENTS.md` §"Testing" — TEST-09 / TEST-10 already complete; TEST-11 / TEST-12 to be added during planning
- `.planning/ROADMAP.md` §"Phase 14" — Goal, success criteria (SC#2 amended per D-E1)
- `.planning/codebase/ARCHITECTURE.md` — Component pattern (ABC + registry + per-component organization); BaseComponent lifecycle that pipeline tests exercise
- `.planning/codebase/CONVENTIONS.md` — snake_case, ASCII-only logs, custom exceptions (ETLError hierarchy that test assertions verify)
- `.planning/codebase/TESTING.md` — pytest discovery, opt-in `-m java` / `-m oracle` markers, existing fixture conventions
- `CLAUDE.md` §"Coverage" — Existing documented coverage command; gets updated at closeout to include `-m "not oracle"` and `-n auto`

### Pipeline-test pattern reference
- `tests/integration/test_iterate_e2e.py` — Reference for ETLEngine.execute()-driven integration tests; the shape Plan 14-01 generalizes into reusable infrastructure
- `tests/conftest.py` (and any subsystem conftest files) — Existing fixture conventions to mirror

### pyproject markers / config
- `pyproject.toml` §`[tool.pytest.ini_options]` — Existing markers (unit, integration, java, oracle, slow, coverage); D-D4 adds `-n auto` to the documented gate command, doesn't change pyproject
- `pyproject.toml` §`[project.optional-dependencies]` — `dev = ["pytest>=8.0,<10", "testcontainers>=4"]`; pytest-xdist in deps via the broader test stack

### Per-subsystem code-targets (the lift universe)
- `src/v1/engine/components/file/` — 16 modules below 95% (file_input_excel.py 29%, file_input_json.py 9%, file_input_raw.py 15%, file_output_excel.py 69% are the deep gaps)
- `src/v1/engine/components/transform/` — 17 modules below 95% (swift_transformer.py 7%, swift_block_formatter.py 7%, python_dataframe_component.py 20%, map.py 77%, join.py 69% are the deep gaps)
- `src/v1/engine/components/aggregate/` — `aggregate_row.py` (79%)
- `src/v1/engine/components/control/` — `send_mail.py` (60%)
- `src/v1/engine/components/database/` — `oracle_output.py` (94%), `oracle_row.py` (90%)
- `src/v1/engine/` (core) — `java_bridge_manager.py` (59%), `engine.py` (81%), `python_routine_manager.py` (82%), `base_component.py` (87%), `base_iterate_component.py` (88%), `executor.py` (91%), `trigger_manager.py` (91%)
- `src/converters/talend_to_v1/` (core) — `expression_converter.py` (78%), `converter.py` (94%)
- `src/converters/talend_to_v1/components/` — 5 modules below 95%: `mssql_input.py` (81%), `xml_map.py` (93%), `replace.py` (94%), `aggregate_row.py` (91%), `foreach.py` (94%), `file_input_excel.py` (94%)

### Project memory rules that apply (non-overridable)
- **test real bridge, not mocks** (project_test_real_bridge.md) — drove D-A3 (java_bridge_manager measured with `-m java`); justified D-A6's narrow exception for Oracle (Phase 11 testcontainer suite IS the real bar)
- **rewrite over patch** + **fix source, no fallbacks** — drives D-C5 (delete dead branches over pragma-or-fake-test)
- **ASCII-only logging** — applies to any test fixtures or harness output added in this phase
- **extensive questions for complex phases** — discuss-phase used 14+ questions across A/C/D before locking decisions
- **pandas 3.0.1 with CoW** — drives D-C4 (real-shape DataFrames with StringDtype must be in test fixtures)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`tests/integration/test_iterate_e2e.py` pattern** — Already runs JSON job configs through `ETLEngine.execute()`. Plan 14-01 generalizes this into a `pipeline_runner` fixture / helper that any subsystem plan can pull in.
- **Phase 13 STALE deletion pattern (D-D1)** — Delete obsolete `NeedsReview` tests when engine implements the feature. Phase 14 may surface more STALE candidates during the lift.
- **Phase 13 D-B1 pattern: `getattr(self, "input_schema", None) or []`** — Established defensive read for engine-set attributes. Tests can rely on this contract.
- **`@pytest.mark.java` opt-in marker** — Already in pyproject; tests that exercise JVM lifecycle code use this. D-A3 expands the gate measurement to include this marker.
- **`@pytest.mark.slow` marker** — Already in pyproject; D-D4 uses this for tests >5s.
- **Existing converter test fixtures** under `tests/converters/talend_to_v1/components/` — Many components have rich existing test patterns; Phase 14 lift extends rather than reinvents.

### Established Patterns
- **BaseComponent lifecycle** — `execute()` (template method) → `_process()` (abstract). Pipeline tests exercise the full template; unit tests can call `_process()` directly. D-C1 chooses the right one per module.
- **Custom exception hierarchy** — `ETLError` → `ConfigurationError`, `DataValidationError`, `ComponentExecutionError`, `FileOperationError`, `JavaBridgeError`, `ExpressionError`, `SchemaError`. D-C4 requires tests to assert exception type, not just `pytest.raises(Exception)`.
- **Three-phase config resolution** in engine: `{{java}}` markers → `${context.var}` → bare `context.var`. Pipeline tests for components that consume java/context expressions must verify resolution order.
- **GlobalMap stat propagation** — `{id}_NB_LINE`, `{id}_NB_LINE_OK`, `{id}_NB_LINE_REJECT` (and component-specific keys like `_FILENAME`, `_NB_FILE`). D-C1's pipeline tests assert these on globalMap after execute.
- **pyproject pinned ranges** — pandas>=2.0,<4 (runtime is 3.0.1 with CoW); pyarrow>=15.0,<24; py4j>=0.10.9,<0.11; lxml>=4.9,<7. Tests must assume current pinned versions.

### Integration Points
- Test infrastructure (Plan 14-01) integrates with the existing `tests/conftest.py` — pipeline runner becomes a `pytest.fixture(scope="function")` callable from any test module.
- Coverage measurement integrates with the existing `pytest --cov=...` invocation in Phase 13's baseline doc — D-E4 adds tool-level config to pyproject.toml; the documented command stays paste-runnable.
- SWIFT synthetic generator (Plan 14-08) is a test helper, not engine code — lives under `tests/fixtures/swift/` (or similar) and exposes a function that returns valid MT-shaped strings.
- COVERAGE.md (Plan 14-13) integrates with CLAUDE.md's existing Coverage section — same command format, updated to reflect `-m "not oracle"` + `-n auto`.

### Triage ground truth (verified deep-research, not hypothesis)
- **53 below-95 modules total** (excluding legacy `complex_converter`):
  - Engine components: 38 (file 16, transform 17, aggregate 1, control 1, database 2, iterate 0, context 0, plus core 7)
  - Converter core: 2
  - Converter components: 6
- **8 deep gaps (<50%)**: swift_transformer 7%, swift_block_formatter 7%, file_input_json 9%, file_input_raw 15%, python_dataframe_component 20%, file_input_excel 29%, java_bridge_manager 59%, send_mail 60%
- **~25 quick wins (90-94%)**: 1–4 missed lines per module
- **~20 medium gaps (60-89%)**: tens of missed lines per module
- **145 modules at >=95%** (no-regress only)

</code_context>

<specifics>
## Specific Ideas

- **No CI workflow file in Phase 14.** User explicitly scoped this out mid-discussion. Replacement: paste-runnable gate command (Phase 13 D-E2 pattern). Future phase will land actual CI.
- **Multi-component testing baked into Phase 14.** User raised "we have to think about multi component or project wise testing as well" — folded into D-C1/D-C2. Pipeline tests via ETLEngine.execute() are the natural fit for lifecycle-dependent modules; pure-pandas transforms stay unit-test.
- **SWIFT decision is decisive.** User picked full inclusion despite PROJECT.md "skipped" note + zero existing engine tests. ~800 stmts of new test surface; synthetic MT generator is the enabling work.
- **Oracle vs Java asymmetry is intentional.** Java bridge measures real (D-A3); Oracle measures mocked (D-A6). User's call. Reasoning: Phase 11 testcontainer suite covers Oracle real-DB verification; java_bridge_manager has no equivalent fall-through.
- **Coverage > runtime.** Phase 14 never trades real-production-path test coverage for faster suite. pytest-xdist is the optimization lever.
- **Uniform 95% floor.** No tiered exemptions for modules currently at 100%. Catches regressions in Phase 14 itself and in future phases.

</specifics>

<deferred>
## Deferred Ideas

- **CI workflow file (GitHub Actions / Jenkinsfile / pre-commit)** — Operational CI lands in a future phase. Phase 14 ships the paste-runnable command instead.
- **aiosmtpd-based local SMTP server** for send_mail integration tests — D-A4 went with smtplib boundary mocks; aiosmtpd is a viable upgrade if a future operational phase wants live SMTP coverage.
- **Hypothesis property-based testing** — Considered but deferred; standard tests sufficient for 95% floor. Could land in a future quality phase.
- **Real Oracle testcontainer in the gate command** — Phase 11 verification debt; stays human-run via the `-m oracle` opt-in suite. A future operational phase (when Docker is in CI) flips this to gate measurement.
- **Branch coverage** — Off in Phase 14. A future quality phase may layer it on top of line coverage.
- **`complex_converter` removal** — Legacy modules at 5-11%; explicit N/A for Phase 14. A future cleanup phase deletes them or moves them.
- **TEST-05, TEST-06 (Phase 15)** — Real .item E2E + Talend output comparison. Builds on Phase 14's pipeline-test infrastructure but executes real samples.
- **PERF-02, PERF-03, PERF-04 (Phase 15)** — Performance work; out of stabilization scope.
- **Documentation sweep (Phase 16)** — README / contributing / coverage-runbook. Consumes Phase 14's COVERAGE.md output.
- **Architectural fixes surfaced during the lift** — If tests reveal real bugs (à la Phase 13 D-B1 through D-B4), patch the source per the existing pattern. Major architectural changes (e.g., schema-everywhere refactor) defer to their own phase.

</deferred>

---

*Phase: 14-coverage-push-to-95-per-module-floor*
*Context gathered: 2026-05-10*
