---
phase: 08
slug: code-components
status: approved
nyquist_compliant: false
wave_0_complete: false
framework: pytest
created: 2026-04-29
revised: 2026-04-29
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python 3.10+ stdlib + project pinned) |
| **Config file** | `pyproject.toml` (pytest section -- verified by ENG-15 closed) |
| **Quick run command** | `python -m pytest tests/v1/engine/components/transform/test_python_component.py -x -q` |
| **Full suite command** | `python -m pytest tests/v1/engine/ -q` |
| **Java integration command** | `python -m pytest tests/v1/engine/components/transform/ -m java -q` |
| **Estimated runtime (unit, no -m java)** | ~6-10s for the 5 Phase 8 test files locally (per RESEARCH.md "Validation Architecture") |
| **Estimated runtime (with -m java)** | +5-15s for bridge boot + integration tests |

---

## Sampling Rate

- **After every task commit:** Run the directly-relevant `test_*.py` file with `-x -q` (fast fail).
- **After every plan wave:** Run `python -m pytest tests/v1/engine/components/transform/test_{java,python}*.py -q`.
- **Before `/gsd-verify-work`:** Full engine suite must be green; Java-marker tests gated on JAR present (`mvn package` once before run).
- **Max feedback latency (unit):** ~10 seconds.

---

## Per-Task Verification Map

Tasks named per `{phase}-{plan}-{task}` from the six plan files. "File Exists" reflects state at planning time -- all four `test_*.py` files for the code components are created BY the plans (Wave 0 gap).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | PYCO-03 | T-08-03 | Mixin `_get_context_dict` extracts context dict shape correctly; no AttributeError when context_manager is None | unit | `python -m pytest tests/v1/engine/components/transform/test_code_component_mixin.py -x -q` | NEW | pending |
| 08-01-02 | 01 | 1 | JAVA-01, JAVA-02, JAVA-03 | T-08-01..04 | JavaComponent registered via decorator + Talend alias; imports prepended with newline; bridge call uses `execute_one_time_expression`; no manual sync/stats; ASCII-only logging at DEBUG level for code body | unit + integration | `python -m pytest tests/v1/engine/components/transform/test_java_component.py -x -q -m "not java"` (unit) and `python -m pytest tests/v1/engine/components/transform/test_java_component.py -m java -q` (real bridge, gated to Plan 05) | NEW | pending |
| 08-02-01 | 02 | 2 | PYCO-01, PYCO-02 | T-08-05..08 | PythonComponent registered (incl. tPython aliases); D-11 namespace whitelist enforced (os/sys/subprocess/__import__/open/exec/eval/compile -> NameError -> ComponentExecutionError); whitelisted modules accessible (pd, np, datetime, json, re, math, Decimal); globalMap and context dict round-trip; no duplicate `_get_context_dict` (inherited from mixin) | unit | `python -m pytest tests/v1/engine/components/transform/test_python_component.py -x -q` | NEW | pending |
| 08-03-01 | 03 | 3 | JROW-01, JROW-02, JROW-03, JROW-04 | T-08-09..13 | JavaRowComponent registered (incl. tJavaRow); imports prepended; bridge exceptions propagate as ComponentExecutionError (NO REJECT -- matches Talend tJavaRow per Talaxie tJavaRow_java.xml + tJavaRow_main.javajet verification AND zero behavior change vs legacy java_row_component.py:96-98); mixin inheritance preserved; ASCII-only logs | unit + integration | `python -m pytest tests/v1/engine/components/transform/test_java_row_component.py -x -q -m "not java"` (unit) and `python -m pytest tests/v1/engine/components/transform/test_java_row_component.py -m java -q` (real bridge, gated to Plan 05) | NEW | pending |
| 08-04-01 | 04 | 3 | PYRO-01, PYRO-02, PYRO-03, PERF-02 | T-08-14..18 | PythonRowComponent registered (incl. tPythonRow); compile() called exactly once per execute() invocation (verified via monkeypatch); per-row REJECT routes offending row with appended `errorMessage` (str) column ONLY -- NO `errorCode` field per Talaxie tFilterRow_java.xml lines 43-47 (single id_String errorMessage column); legacy `errorCode='PYTHON_ERROR'` and revision-1 integer errorCode both dropped; die_on_error=True raises ComponentExecutionError with row index in message; D-11 namespace blocked names route to reject; `_validate_output_row` legacy helper deleted (Rule 11) | unit | `python -m pytest tests/v1/engine/components/transform/test_python_row_component.py -x -q` | NEW | pending |
| 08-05-01 | 05 | 4 | TEST-07 | T-08-19, T-08-20 | java_bridge session fixture wired; Java bridge JAR built and present; all `@pytest.mark.java` tests in test_java_component.py and test_java_row_component.py pass against a real running bridge (not mocks) per memory `feedback_test_real_bridge` | integration | `test -f src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar && python -m pytest tests/v1/engine/components/transform/test_java_component.py tests/v1/engine/components/transform/test_java_row_component.py -m java -q` | NEW (fixture) | pending |
| 08-05-02 | 05 | 4 | TEST-07 | — | Engine smoke tests verify all 4 components run end-to-end via ETLEngine (`REGISTRY.get` resolves all four class names + Talend aliases; no static-dict path remains in engine.py per current source); BaseComponent stats lifecycle works (NB_LINE_OK populated automatically) | integration | `python -m pytest tests/v1/engine/test_code_components_engine_smoke.py -q` | NEW | pending |
| 08-05-03 | 05 | 4 | TEST-07 | — | Human verifies the 6-step checkpoint (mvn build + Phase 8 unit suite + Phase 8 java integration suite + engine smoke + Phase 7.1/7.2 regression spot-check + grep gate sweep) on local Mac | manual (checkpoint:human-verify) | "approved" resume signal | NEW | pending |
| 08-06-01 | 06 | 5 | (closure) | — | Verify converter and bridge are untouched (`git log --since=2026-04-29 -- src/converters/` and `... -- src/v1/java_bridge/` empty); full Phase 8 unit suite green; no regressions on Phase 7.1/7.2 components | unit + integration | `python -m pytest tests/v1/engine/components/transform/test_code_component_mixin.py tests/v1/engine/components/transform/test_python_component.py tests/v1/engine/components/transform/test_python_row_component.py tests/v1/engine/components/transform/test_java_component.py tests/v1/engine/components/transform/test_java_row_component.py -m "not java" -q` | NEW | pending |
| 08-06-02 | 06 | 5 | (closure) | T-08-21 | PHASE-SUMMARY.md, ROADMAP, STATE updated; D-26 supersession recorded; revision 2 Talend parity claims correction documented (java_row NO REJECT, errorMessage-only schema for python_row, passthrough as DataPrep data-flow semantic); JROW-02 reinterpretation noted (no native REJECT in Talend tJavaRow; v1 satisfies JROW-02 by error propagation, full REJECT deferred as a future enhancement) | docs | `test -f .planning/phases/08-code-components/08-PHASE-SUMMARY.md && grep -c "D-26" .planning/phases/08-code-components/08-PHASE-SUMMARY.md && grep -c "Talend parity claims correction\|revision 2" .planning/phases/08-code-components/08-PHASE-SUMMARY.md` | NEW | pending |

*Status legend: pending / green / red / flaky*

---

## Wave 0 Requirements

All four component test files are NEW (created by Plans 01-04). The shared `java_bridge` pytest fixture is created or verified by Plan 05 (Wave 4). Until Wave 0 (Plans 01-04) lands, `nyquist_compliant: false`.

- [ ] `tests/v1/engine/components/transform/test_code_component_mixin.py` — covers PYCO-03 (Plan 01)
- [ ] `tests/v1/engine/components/transform/test_java_component.py` — covers JAVA-01..03 (Plan 01)
- [ ] `tests/v1/engine/components/transform/test_python_component.py` — covers PYCO-01..03 (Plan 02)
- [ ] `tests/v1/engine/components/transform/test_java_row_component.py` — covers JROW-01..04 (Plan 03)
- [ ] `tests/v1/engine/components/transform/test_python_row_component.py` — covers PYRO-01..03 + PERF-02 (Plan 04)
- [ ] `tests/v1/engine/test_code_components_engine_smoke.py` — covers TEST-07 engine-level (Plan 05)
- [ ] `tests/v1/engine/conftest.py` — `java_bridge` session fixture wired/verified (Plan 05)
- [ ] `src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar` — `mvn package` artifact (Plan 05 Task 1)
- [ ] No new conftest needed beyond the `java_bridge` fixture; existing `tests/v1/engine/conftest.py` already provides GlobalMap/ContextManager helpers (verified by Phase 7.2 reuse).
- [ ] No framework install needed -- pytest already pinned via project deps.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Mac-local JAR build verification + full Phase 8 test surface green | TEST-07 | Java bridge requires JVM 11 + Maven 3.x + the developer's local toolchain; CI cross-platform verification deferred per Phase 7.1 carryover note | Plan 05 Task 3 (`checkpoint:human-verify`) -- six-step manual run: `mvn package` + Phase 8 unit suite + Phase 8 java integration + engine smoke + Phase 7.1/7.2 regression spot + grep gate sweep |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (the manual checkpoint in 08-05-03 is bracketed by automated verifies on either side)
- [x] Sampling continuity: no 3 consecutive tasks without an automated verify (every plan task has a `<verify><automated>` block; only 08-05-03 is a manual checkpoint, immediately preceded and followed by automated verification tasks)
- [x] Wave 0 covers all MISSING references (5 component test files + engine smoke test + java_bridge fixture)
- [x] No watch-mode flags in any sampling command
- [x] Feedback latency < 10s for unit suite per file; full suite < 30s
- [ ] `nyquist_compliant: true` -- to be set in frontmatter after Plans 01-04 land (test files created)

**Approval:** approved 2026-04-29 (revision 2, post Talaxie primary-source verification -- java_row REJECT dropped, errorCode dropped, passthrough framing corrected)
