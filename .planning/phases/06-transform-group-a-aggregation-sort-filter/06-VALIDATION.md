---
phase: 6
slug: transform-group-a-aggregation-sort-filter
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `python -m pytest tests/v1/engine/components/aggregate/ tests/v1/engine/components/transform/ -x -q` |
| **Full suite command** | `python -m pytest tests/v1/engine/components/aggregate/ tests/v1/engine/components/transform/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/v1/engine/components/aggregate/ tests/v1/engine/components/transform/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/v1/engine/components/aggregate/ tests/v1/engine/components/transform/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | AGGR-01 | — | N/A | unit | `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py -x -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | AGGR-02 | — | N/A | unit | `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py -x -q` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | AGGR-03 | — | N/A | unit | `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py -x -q` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | SORT-01 | — | N/A | unit | `python -m pytest tests/v1/engine/components/transform/test_sort_row.py -x -q` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 1 | FROW-01 | — | Eval removed, no code injection | unit | `python -m pytest tests/v1/engine/components/transform/test_filter_rows.py -x -q` | ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 1 | FROW-02 | — | N/A | unit | `python -m pytest tests/v1/engine/components/transform/test_filter_rows.py -x -q` | ❌ W0 | ⬜ pending |
| 06-04-01 | 04 | 2 | TEST-08 | — | N/A | unit | `python -m pytest tests/v1/engine/components/ -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/v1/engine/components/aggregate/__init__.py` — package init
- [ ] `tests/v1/engine/components/aggregate/test_aggregate_row.py` — test stubs for AGGR-01 through AGGR-09
- [ ] `tests/v1/engine/components/transform/test_sort_row.py` — test stubs for SORT-01 through SORT-05
- [ ] `tests/v1/engine/components/transform/test_filter_rows.py` — test stubs for FROW-01 through FROW-07

*Test infrastructure (conftest.py, fixtures) established in Phase 4.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | — | — | — |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
