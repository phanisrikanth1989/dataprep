---
phase: 3
slug: execution-loop-restructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (installed via pyproject.toml in Phase 1) |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `python -m pytest tests/v1/engine/ -x -q` |
| **Full suite command** | `python -m pytest tests/v1/engine/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/v1/engine/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/v1/engine/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| Populated during planning | | | EXEC-01 | unit | `pytest tests/v1/engine/test_executor.py -v` | pending |
| Populated during planning | | | EXEC-02 | unit | `pytest tests/v1/engine/test_output_router.py -v` | pending |
| Populated during planning | | | EXEC-03 | unit | `pytest tests/v1/engine/test_execution_plan.py -v` | pending |
| Populated during planning | | | EXEC-07 | unit | `pytest tests/v1/engine/test_execution_plan.py -v` | pending |
| Populated during planning | | | PERF-01 | unit | `pytest tests/v1/engine/test_executor.py -v` | pending |

*Status: pending -- will be populated during plan execution*

---

## Wave 0 Requirements

- [ ] `tests/v1/engine/conftest.py` -- StubComponent fixture and test helpers
- [ ] `tests/v1/engine/__init__.py` -- package init

*Existing Phase 1 test infrastructure (pyproject.toml, markers) covers framework requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
