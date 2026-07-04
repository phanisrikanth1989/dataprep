---
phase: 9
slug: tcontextload-routines
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pyproject.toml |
| **Quick run command** | `python3 -m pytest tests/v1/engine/components/context/ tests/v1/engine/test_routine_loading.py -x -q` |
| **Full suite command** | `python3 -m pytest tests/v1/engine/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/v1/engine/components/context/ tests/v1/engine/test_routine_loading.py -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/v1/engine/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | CTXL-01 | — | N/A | unit | `python3 -m pytest tests/v1/engine/components/context/test_context_load.py::TestDieOnError -x` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | CTXL-02 | — | N/A | unit | `python3 -m pytest tests/v1/engine/components/context/test_context_load.py::TestLoadNewVariable -x` | ❌ W0 | ⬜ pending |
| 09-01-03 | 01 | 1 | CTXL-03 | — | N/A | unit | `python3 -m pytest tests/v1/engine/components/context/test_context_load.py::TestNotLoadOldVariable -x` | ❌ W0 | ⬜ pending |
| 09-01-04 | 01 | 1 | CTXL-04 | — | N/A | unit | `python3 -m pytest tests/v1/engine/components/context/test_context_load.py::TestTypePreservation -x` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 1 | ROUT-01 | — | N/A | unit+integration | `python3 -m pytest tests/v1/engine/test_routine_loading.py::TestJavaRoutines -x` | ❌ W0 | ⬜ pending |
| 09-02-02 | 02 | 1 | ROUT-02 | — | N/A | unit | `python3 -m pytest tests/v1/engine/test_routine_loading.py::TestPythonRoutines -x` | ❌ W0 | ⬜ pending |
| 09-02-03 | 02 | 1 | ROUT-03 | — | N/A | unit | `python3 -m pytest tests/v1/engine/test_routine_loading.py::TestRoutineDiscovery -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/v1/engine/components/context/test_context_load.py` — engine tests for tContextLoad rewrite (converter tests exist at different path)
- [ ] `tests/v1/engine/test_routine_loading.py` — tests for Java and Python routine loading enhancements
- [ ] `tests/v1/engine/components/context/__init__.py` — package init for test directory

*Existing infrastructure: pytest framework, pyproject.toml, existing test patterns from Phases 4-7*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Java routine callable from Groovy expression | ROUT-01 | Requires running JVM with bridge | Start bridge, load routine JAR, execute expression referencing routine method |

*All other behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
