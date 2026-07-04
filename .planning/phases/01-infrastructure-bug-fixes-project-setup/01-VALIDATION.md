---
phase: 1
slug: infrastructure-bug-fixes-project-setup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pyproject.toml [tool.pytest.ini_options] (Wave 0 creates) |
| **Quick run command** | `pytest tests/v1/engine/ -m unit -x --tb=short` |
| **Full suite command** | `pytest tests/v1/engine/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/v1/engine/ -m unit -x --tb=short`
- **After every plan wave:** Run `pytest tests/v1/engine/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | 01 | 1 | ENG-15 | manual | `pip install -e .[dev] && pytest --collect-only` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | TEST-01 | manual | `pytest --co tests/v1/engine/` | ❌ W0 | ⬜ pending |
| TBD | 02 | 1 | ENG-02 | unit | `pytest tests/v1/engine/test_global_map.py -x` | ❌ W0 | ⬜ pending |
| TBD | 02 | 1 | ENG-05 | unit | `pytest tests/v1/engine/test_context_manager.py -x` | ❌ W0 | ⬜ pending |
| TBD | 02 | 1 | ENG-06 | unit | `pytest tests/v1/engine/test_trigger_manager.py -x` | ❌ W0 | ⬜ pending |
| TBD | 02 | 1 | ENG-18 | unit | `pytest tests/v1/engine/test_context_manager.py -x` | ❌ W0 | ⬜ pending |
| TBD | 03 | 2 | ENG-03 | unit | `pytest tests/v1/engine/test_base_component.py -x` | ❌ W0 | ⬜ pending |
| TBD | 03 | 2 | ENG-07/20 | unit | `pytest tests/v1/engine/test_base_component.py -x` | ❌ W0 | ⬜ pending |
| TBD | 03 | 2 | ENG-09/21 | unit | `pytest tests/v1/engine/test_base_component.py -x` | ❌ W0 | ⬜ pending |
| TBD | 03 | 2 | ENG-16 | unit | `pytest tests/v1/engine/test_base_component.py -x` | ❌ W0 | ⬜ pending |
| TBD | 03 | 2 | ENG-17 | unit | `pytest tests/v1/engine/test_base_component.py -x` | ❌ W0 | ⬜ pending |
| TBD | 03 | 2 | ENG-19 | unit | `pytest tests/v1/engine/test_base_component.py -x` | ❌ W0 | ⬜ pending |
| TBD | 04 | 2 | ENG-11 | manual | `grep -r 'print(' src/v1/engine/base_component.py src/v1/engine/global_map.py src/v1/engine/context_manager.py src/v1/engine/trigger_manager.py src/v1/engine/engine.py` | N/A | ⬜ pending |
| TBD | 04 | 2 | ENG-12 | unit | `pytest tests/v1/engine/ -x` | ❌ W0 | ⬜ pending |
| TBD | 05 | 3 | TEST-02 | unit | `pytest tests/v1/engine/ -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/v1/engine/__init__.py` — package marker
- [ ] `tests/v1/engine/conftest.py` — markers, basic fixtures
- [ ] `pyproject.toml` — with [tool.pytest.ini_options] and dependency groups

*Wave 0 is part of Plan 01 (Project Setup).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| No print() in infrastructure files | ENG-11 | Negative assertion (absence of pattern) | grep -r 'print(' in the 6 infrastructure files — must return empty |
| pyproject.toml valid and installable | ENG-15 | Build system validation | pip install -e .[dev] must succeed |
| ENGINE_COMPONENT_PATTERN.md exists and is complete | ENG-16 | Documentation quality | Manual review — must match CONVERTER_PATTERN.md style |
| ENGINE_TEST_PATTERN.md exists and is complete | TEST-01 | Documentation quality | Manual review — must match TEST_PATTERN.md style |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
