---
phase: 5
slug: tmap-component
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml ([tool.pytest.ini_options]) |
| **Quick run command** | `python -m pytest tests/v1/engine/components/transform/test_map.py -x -q` |
| **Full suite command** | `python -m pytest tests/v1/engine/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/v1/engine/components/transform/test_map.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/v1/engine/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | MAP-01 | — | N/A | unit | `pytest tests/v1/engine/components/transform/test_map.py -k unique_match` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MAP-02 | — | N/A | unit | `pytest tests/v1/engine/components/transform/test_map.py -k reject_inner_join` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MAP-03 | — | N/A | unit | `pytest tests/v1/engine/components/transform/test_map.py -k null_join` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MAP-04 | — | N/A | unit | `pytest tests/v1/engine/components/transform/test_map.py -k lifecycle` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MAP-05 | — | N/A | unit | `pytest tests/v1/engine/components/transform/test_map.py -k catch_output` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MAP-06 | — | N/A | unit | `pytest tests/v1/engine/components/transform/test_map.py -k auto_convert` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MAP-07 | — | N/A | unit | `pytest tests/v1/engine/components/transform/test_map.py -k nb_line` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MAP-08 | — | N/A | unit | `pytest tests/v1/engine/components/transform/test_map.py -k reload_each_row` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TEST-03 | — | N/A | unit | `pytest tests/v1/engine/components/transform/test_map.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/v1/engine/components/transform/test_map.py` — test file for tMap component
- [ ] Test fixtures for multi-input setup (main + lookup DataFrames)
- [ ] Mock Java bridge fixture for unit tests (no JVM required)

*Existing pytest infrastructure from Phase 1 covers framework setup.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Java bridge integration | MAP-04 | Requires JVM | Run with `@pytest.mark.java` marker and JVM available |

*All other behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
