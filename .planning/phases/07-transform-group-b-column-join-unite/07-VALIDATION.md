---
phase: 7
slug: transform-group-b-column-join-unite
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/v1/engine/components/transform/test_join.py tests/v1/engine/components/transform/test_filter_columns.py tests/v1/engine/components/transform/test_unite.py -x -q` |
| **Full suite command** | `python -m pytest tests/v1/engine/components/transform/test_join.py tests/v1/engine/components/transform/test_filter_columns.py tests/v1/engine/components/transform/test_unite.py -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | JOIN-01 | — | N/A | unit | `python -m pytest tests/v1/engine/components/transform/test_join.py -x -q` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 1 | FCOL-01 | — | N/A | unit | `python -m pytest tests/v1/engine/components/transform/test_filter_columns.py -x -q` | ❌ W0 | ⬜ pending |
| 07-02-02 | 02 | 1 | UNIT-01 | — | N/A | unit | `python -m pytest tests/v1/engine/components/transform/test_unite.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/v1/engine/components/transform/test_join.py` — test stubs for JOIN-01 through JOIN-08
- [ ] `tests/v1/engine/components/transform/test_filter_columns.py` — test stubs for FCOL-01, FCOL-02
- [ ] `tests/v1/engine/components/transform/test_unite.py` — test stubs for UNIT-01, UNIT-02

*Test infrastructure (conftest.py, fixtures) established in Phase 4.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
