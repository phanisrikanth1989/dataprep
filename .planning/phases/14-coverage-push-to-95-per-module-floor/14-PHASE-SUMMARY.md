---
phase: 14
slug: coverage-push-to-95-per-module-floor
status: complete
completed: 2026-05-11
plans_complete: 12
plans_total: 12
follow_ons: ["14-06b gap closure", "COV-CJ-001 converter join.py extras"]
commits: ~110
overall_percent: 98.3
in_scope_modules: 181
requirements_complete: [TEST-11, TEST-12]
---

# Phase 14 -- Coverage Push to 95% per-module floor -- Phase Summary

> Retrospective per Phase 13 `13-PHASE-SUMMARY.md` format.
> Cross-references: `14-COVERAGE.md`, `14-coverage.json`, `14-VERIFICATION.md`, `14-CONTEXT.md`, `14-RESEARCH.md`, `14-VALIDATION.md`.

---

## Phase Outcome Summary

**Goal:** Lift every module under `src/v1/engine/` and `src/converters/` (excluding legacy `complex_converter/`) to a uniform >=95% line-coverage floor. Build shared pipeline-test infrastructure. Produce final `14-COVERAGE.md` + paste-runnable gate command. No new product features; pure stabilization.

**Result:** All 181 in-scope modules at >=95.0% line coverage; overall 98.3% (16746 / 17033 statements covered). 100 modules at perfect 100.0%; zero modules below floor. Gate command exits 0 from a clean working tree. Phase 13 baseline's 52 below-floor modules (plus 1 incidental converter join.py at 94.7% caught at closeout via COV-CJ-001) all lifted.

**Duration:** 2026-05-10 -- 2026-05-11 (Phase 13 closure to Phase 14 closeout). Approximately 110 commits across 12 plans + 1 gap-closure follow-on (14-06b) + 1 closeout extra (COV-CJ-001).

**Phase 14 is closed.** Next: Phase 15 (integration testing & performance).

---

## Plans Executed

| Plan | Outcome | Commit Count (approx) | Key Lifts |
|------|---------|----------------------:|-----------|
| 14-01 | Pipeline-test infrastructure | 5 | root `tests/conftest.py`, `tests/fixtures/jobs/` scaffolding, `scripts/check_per_module_coverage.py`, pyproject `[tool.coverage.*]` blocks, `pytest-xdist>=3.8,<4` pin |
| 14-02 | engine.components.aggregate | 2 | `aggregate_row.py` 79% -> 100% (BUG-AGG-001 root-cause + D-C5 deletion) |
| 14-03 | engine.components.control | 3 | `send_mail.py` 60% -> 100% (BUG-MAIL-001 attachment ETLError swallowing) |
| 14-04 | engine.components.database | 2 | `oracle_output.py` 94.1% -> 99.5%, `oracle_row.py` 90.3% -> 100% (mocked oracledb per D-A6) |
| 14-05 | transform quick wins | 12 | 12 modules 80-94% -> 100% (BUG-EJF-001 fix; 5 D-C5 deletions) |
| 14-06 | transform deep gaps non-SWIFT | 9 | `join.py` 69% -> 100%, `python_dataframe_component.py` 20% -> 100%, `log_row.py` 97% -> 100% (BUG-PDC-001/002 + 3 D-C5 sets in join.py); `map.py` PARTIAL 73.8% -> 83.1% |
| 14-06b | gap-closure follow-on | 2 | `map.py` 79.6% -> 95.85% via 26 unit tests + 16 `@pytest.mark.java` tests in NEW `test_map_bridge.py` (no source changes) |
| 14-07 | SWIFT | 8 | `swift_transformer.py` 7% -> 98.0%, `swift_block_formatter.py` 7% -> 97.2% (synthetic MT generator + 5 BUG-SWIFT-001..005 fixes + D-C5 duplicate `_load_lookup_files` deletion) |
| 14-08 | file quick wins | 17 | 12 modules 81-94% -> >=99.5% (STALE-FOD-001 D-C5 deletion resolving Phase 13 baseline's single pre-existing pragma; D-RULE3 `.gitignore` negation for fixture JSONs) |
| 14-09 | file deep gaps | 9 | `file_output_excel.py` 69% -> 100%, `file_input_excel.py` 29% -> 97.4%, `file_input_json.py` 9% -> 100%, `file_input_raw.py` 15% -> 100% (BUG-FIJ-001/002 root-cause fixes; 12 binary/text + 3 pipeline fixtures) |
| 14-10 | engine core | 11 | 7 modules incl. `java_bridge_manager.py` 52.5% -> 99.0% via `@pytest.mark.java` per D-A3; resolved Plan 14-01 `test_bridge_integration` JVM-contention via BUG-JVM-001 |
| 14-11 | converters | 9 | 8 modules 78-97% -> >=97.2% (STALE-INT-001 legacy `complex_converter` test removal; expression_converter 77.8% -> 98.9%, mssql_input 81% -> 100%) |
| COV-CJ-001 | converter `join.py` extras | 1 | Incidental cleanup: converter `join.py` 94.7% -> 100% caught at closeout review |
| 14-12 | closeout | 8 | `14-COVERAGE.md`, `14-coverage.json`, `14-VERIFICATION.md`, `14-PHASE-SUMMARY.md`, CLAUDE.md gate update, REQUIREMENTS.md TEST-11/12 -> Complete, ROADMAP.md Phase 14 SC#2 D-E1 wording + 12/12 Complete, STATE.md Phase 14 entry |

**Plans count:** 12 of 12 (plus 14-06b follow-on + COV-CJ-001 incidental). All Plan 14-NN tasks ship green.

---

## What Worked

### D-C1 / D-C2 pipeline-test infrastructure scaled cleanly

Plan 14-01's `run_job_fixture` + `tests/fixtures/jobs/{subsystem}/{behavior}.json` pattern composed every downstream lifecycle-sensitive module: file I/O, iterate, trigger, executor, base_component, multi-subjob orchestration. 14 JSON fixtures covered 6 subsystems with zero infrastructure churn after Plan 14-01 landed. Reuses the existing `tests/integration/test_iterate_e2e.py` pattern, so converter-team contributors had a familiar shape.

### Existing test patterns scaled

The transform quick-wins (Plan 14-05) and file quick-wins (Plan 14-08) cleared 24 modules to 100% line coverage with mostly direct `_process()` unit-test patterns. The `pytest.raises(<SpecificError>)` style from Phase 13 D-B2 onward worked uniformly. pandas 3.0.1 CoW behavior surfaced 1 real bug (BUG-EJF-001 `_is_null` widening) which was fixed source-side; no test-side workarounds.

### SWIFT synthetic generator is reusable

`tests/fixtures/swift/synthetic.py` exposes `build_block_*` + `build_mt_message` + 3 happy-path MT message builders + 1 malformed message. Plan 14-07 used it to take `swift_transformer.py` from 7% to 98.0% and `swift_block_formatter.py` from 7% to 97.2% without any real Talend production samples. Phase 15 can reuse the generator if real Talend SWIFT job-parity tests are added.

### `@pytest.mark.java` + JavaBridgeManager dynamic-port pattern unblocked bridge coverage

D-A3's call to measure `java_bridge_manager.py` with `-m java` markers (rather than mock) paid off in Plan 14-10 (52.5% -> 99.0%) and Plan 14-06b (map.py bridge-driven paths 84.9% -> 95.85%). The BUG-JVM-001 switch from `JavaBridge()` default port to `JavaBridgeManager()` dynamic free port also retroactively resolved Plan 14-01's deferred `test_bridge_integration` `-n auto` contention. One change unblocked 31 pre-existing bridge integration tests AND the new bridge-coverage tests.

### Pragma allowlist via `[tool.coverage.report] exclude_also` -- not inline pragmas

D-C3's narrow allowlist (`__main__`, `@abstractmethod`, `raise NotImplementedError`) is enforced via regex `exclude_also` in `pyproject.toml`. The result: zero `# pragma: no cover` annotations in scope. Future PRs that add an inline pragma stick out as a visible diff line that reviewers can challenge -- no "allowlist drift" possible without an explicit pyproject change. This was simpler than a custom coverage plugin and is exactly what the project-rule "no defensive shims" expects of policy enforcement.

### Plan parallelization paid off

Wave 1 plans (14-02 / 14-03 / 14-04 / 14-05 / 14-08 / 14-11) ran independently after Plan 14-01 shipped. The 12-plan / 3-wave structure (D-D1, D-D2) avoided executor-context blowup; deep gaps (14-06 / 14-07 / 14-09 / 14-10) only landed once quick-win patterns were proven.

---

## What Was Hard

### SWIFT MT branch coverage iteration (Plan 14-07)

The synthetic MT generator went through ~5 shape revisions during Plan 14-07. Each revision required regenerating fixture YAML and re-running the `swift_*` coverage. Net cost: half a wave of iteration before the generator stabilized. Locked Q3 (planner discretion on shape) was the right call -- predicting the shape up front would have required reading every `swift_*` source path first, which would have ballooned the planning phase.

### `java_bridge_manager.py` retry-branch test approach (RESEARCH §A6)

Hitting the "Address already in use" retry path in `java_bridge_manager.py` required monkey-patching `JavaBridge.start` to seed the error condition. Acceptable per RESEARCH §A6, but discoverable only mid-execution. Plan 14-10 documented the pattern; future contributors testing retry-style code in similarly-shaped modules can copy it.

### Locked Q4: `coverage.json` size in the repo

`coverage.json` is 830 KB. Committing it per phase (locked Q4) trades repo size for diffability of historical floors. The decision still holds, but a future operational-CI phase should either:
- emit a smaller JSON (e.g. just the per-module summaries, not the per-line maps), OR
- commit only the summary JSON to the phase dir and keep the full per-line maps as a build artifact.

### The dual-bug `BaseComponent` subclass pattern

Four bug pairs in Phase 14 (BUG-PDC-001/002, BUG-SWIFT-001/002, BUG-FIJ-001/002, plus the 14-07 SWIFT subset) showed the same shape: a `BaseComponent` subclass missing both `@REGISTRY.register` AND abstract `_validate_config`. The class was importable but unusable; engine.py silently dropped it as "Unknown component type" at production runtime. Three plans surfaced this independently before Plan 14-12's audit. Plan-checker observation for the future: a grep for `class .+\(BaseComponent\):` minus a registered decorator OR minus a `_validate_config` definition would catch this systematically.

### pandas 3.0 CoW one-off (BUG-EJF-001)

`pd.isna()` on a multi-element list raises `ValueError` (not `TypeError`) under pandas 3.0 / CoW. The `_is_null` `except TypeError:` catch was too narrow. The fix was 1 character (widen to tuple) but the surface area where similar patterns exist (every `pd.isna` try/except in the engine) is large; future contributors must remember pandas 3.0 has more failure modes than pandas 2.x.

---

## Lessons Learned

### D-A3 (live bridge) vs D-A6 (mocked Oracle) asymmetry was the right call

Live `-m java` measurement for `java_bridge_manager.py` paid off twice (Plan 14-10 lift + Plan 14-06b bridge-path closure for `map.py`). Mocked oracledb for `oracle_output.py`/`oracle_row.py` kept the gate command env-independent without sacrificing meaningful coverage -- Phase 11's testcontainer suite (opt-in via `-m oracle`) remains the live verification path. The decision applied the right rule (`project_test_real_bridge.md`) where it pays off, and accepted the engineering trade-off where it doesn't.

### Pipeline tests are essential for lifecycle modules

`base_component.py`, `base_iterate_component.py`, `executor.py`, `engine.py`, `trigger_manager.py` -- none could have hit >=95% via direct unit tests. The 3 new core pipeline fixtures (trigger_runif / multi_subjob / reject_routing) carried each of these from 80-91% baseline to >=95%. The fixture-jobs pattern is reusable for Phase 15 integration tests.

### Pragma allowlist via pyproject is enforceable without a custom plugin

D-C3 was originally framed as "narrow allowlist of inline pragmas." In execution we discovered the allowlist could be expressed entirely as `exclude_also` regexes against the source code shape (not inline pragma annotations). This is simpler, more visible in diff review, and harder to bypass.

### "Fix source, no fallbacks" continued to find production bugs

11 BUG-* root-cause patches landed during Phase 14 -- 10 of them in source code that compiled and "looked correct" but had subtle production breakage. Coverage-driven testing surfaced bugs that integration testing would have missed (because the bugs were either registration-time class issues or per-row exception-handling issues that only show up under specific data shapes). The project rule paid for itself.

### Module-count drift is normal; trust the gate script

Phase 14 in-scope module count (181) differs from Phase 13 baseline (198). Reason: `[tool.coverage.run] omit = ["*/__init__.py"]` excludes `__init__.py` files, which were counted in Phase 13 because the baseline command didn't yet have the pyproject omit blocks. Both numbers are correct for their respective definitions; future phases must check `coverage.json` for the canonical universe, not historical docs.

### "Extensive questions for complex phases" pre-locked the right decisions

Phase 14 discuss-phase took 14 rounds across A/C/D questions. Locks Q2 (iterate/context merge), Q4 (coverage.json commit), and Q5 (rm -f .coverage* prefix) were all decisions discovered mid-discussion that would have caused mid-execution rework if defaulted. The cost of front-loading was 2-3 extra discussion rounds; the value was zero mid-execution decision unwinds.

---

## Final State

### REQUIREMENTS.md
- TEST-11: Complete (per-module >=95% lifted + verified + regression guard + D-C3 enforcement)
- TEST-12: Complete (paste-runnable gate command + `scripts/check_per_module_coverage.py` + `14-COVERAGE.md` replaces `13-COVERAGE-BASELINE.md`)
- Traceability table: both rows show "Phase 14 / Complete"
- Footer: "Last updated: 2026-05-11 after Phase 14 closure (TEST-11, TEST-12 marked Complete)"

### ROADMAP.md
- Phase 14 line: marked `[x]`, completed 2026-05-11, wording reflects D-E1 amendment (paste-runnable gate, not CI workflow)
- Phase 14 SC#1..SC#4: all annotated DONE with evidence
- Plan-progress table: 12/12 plans complete; 14-12 row added with closeout summary
- Progress table: Phase 14 row shows `12/12 | Complete | 2026-05-11`

### STATE.md
- `status: idle`; `stopped_at` points to Plan 14-12 closeout
- Current Position: Phase 14 COMPLETE; next = Phase 15
- New `### Phase 14 closed (2026-05-11)` retrospective subsection
- Session Continuity: resume signal -> `/gsd-discuss-phase 15`

### CLAUDE.md
- §Coverage section rewritten with locked Q4/Q5 gate command form
- Notes: JVM 11+ requirement (D-A3), Oracle opt-in (D-A6), pyproject as source of truth (D-C3, D-E4), no `--cov-branch` (D-E2 carryover)
- Points readers to `14-COVERAGE.md` (replaces 13 baseline) and `14-coverage.json`

### `.planning/phases/14-coverage-push-to-95-per-module-floor/`
- `14-COVERAGE.md` -- final per-module table (181 modules, all PASS)
- `14-coverage.json` -- machine-readable acceptance artifact (locked Q4)
- `14-VERIFICATION.md` -- acceptance evidence, gate output, no-regression check, D-C3/D-C5 logs, fixture inventories
- `14-PHASE-SUMMARY.md` -- this file
- All 12 plan files + 14-06b summary + intermediate planning docs

### `.gitignore`
- `!.planning/phases/**/*coverage.json` negation added (D-RULE3 extension; otherwise the project-wide `*.json` rule swallows the committed artifact)

---

## Handoff Notes for Phase 15

Phase 15 (integration testing & performance) builds directly on Phase 14:

1. **Pipeline-test infra is the foundation.** `tests/conftest.py` `run_job_fixture` + `tests/fixtures/jobs/{subsystem}/{behavior}.json` is exactly the shape Phase 15 needs for TEST-05 (real .item E2E) and TEST-06 (Talend output comparison). Phase 15 should extend rather than reinvent: add an `e2e/` subsystem dir, mirror the JSON format, add a comparator fixture.

2. **SWIFT generator is reusable.** If Phase 15 includes real Talend SWIFT job-parity tests, `tests/fixtures/swift/synthetic.py` already provides MT103/MT202/MT940 + malformed-message builders. The generator is test-only; production SWIFT data is not required.

3. **`@pytest.mark.java` is the right pattern for live-bridge tests.** Phase 14's BUG-JVM-001 resolution (dynamic-port via `JavaBridgeManager`) is the canonical pattern for parallel-safe bridge fixtures. Phase 15 should use it directly when adding tMap E2E tests against real .item samples.

4. **PERF-03 / PERF-04** (tMap Python-side expression handling + FilterRows compiled expression) can land any time without coverage regression risk -- the 95% floor is well above the minimum for both modules and there's headroom for refactor-driven test churn.

5. **`coverage.json` size watch.** If repo size becomes a concern, the locked Q4 commit-per-phase pattern may be revisited; consider a smaller summary-only JSON or build-artifact-only emission.

6. **TEST-09 / TEST-10 from Phase 13 are the regression baseline.** No xfail markers added in Phase 14; that contract stays. Future phases must continue to fix or delete unstable tests, never xfail.

7. **Future operational CI phase (currently un-numbered)** will turn the paste-runnable gate command into a real CI gate. The script (`scripts/check_per_module_coverage.py`) is already the right shape -- it just needs to be invoked from a CI workflow file with JVM 11+ provisioned. The 14-COVERAGE.md command is paste-runnable today; the CI phase only needs to wrap it.

---

## Acknowledgements

- Phase 13 (test-stabilization-bridge-jar-rebuild) provided the green test surface that Phase 14 built on. Without Phase 13's 6832-passing baseline, Phase 14 would have spent its first wave on test-fixing rather than coverage-lifting.
- Phase 12's pyproject-toml + `[tool.pytest.ini_options]` markers (`unit`, `integration`, `java`, `oracle`, `slow`) made D-A3 / D-A6 / D-D4 marker-based gate construction possible.

---

*Phase 14 retrospective -- captured 2026-05-11 -- ready for sign-off*
