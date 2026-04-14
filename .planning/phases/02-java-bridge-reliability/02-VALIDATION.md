---
phase: 2
slug: java-bridge-reliability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` (configured by Phase 1) |
| **Quick run command** | `pytest tests/v1/engine/test_bridge_type_mapping.py -x -m unit` |
| **Full suite command** | `pytest tests/v1/engine/ -x` |
| **Estimated runtime** | ~15 seconds (unit), ~60 seconds (with java integration) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/v1/engine/test_bridge_type_mapping.py tests/v1/engine/test_bridge_serialization.py -x -m unit`
- **After every plan wave:** Run `pytest tests/v1/engine/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | BRDG-01 | — | N/A | unit + integration | `pytest tests/v1/engine/test_bridge_type_mapping.py -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | BRDG-02 | — | Schema-driven conversion, no data inference | unit | `pytest tests/v1/engine/test_bridge_serialization.py -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | BRDG-03 | — | Sync at every call site | unit | `pytest tests/v1/engine/test_bridge_sync.py -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 1 | BRDG-04 | — | N/A | integration | `pytest tests/v1/engine/test_bridge_integration.py -x -m java` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 1 | BRDG-05 | — | N/A | integration | `pytest tests/v1/engine/test_bridge_integration.py -x -m java` | ❌ W0 | ⬜ pending |
| 02-01-06 | 01 | 1 | BRDG-06 | — | No synchronized bottleneck | unit + integration | `pytest tests/v1/engine/test_bridge_compilation.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/v1/engine/test_bridge_type_mapping.py` — covers BRDG-01, BRDG-02
- [ ] `tests/v1/engine/test_bridge_serialization.py` — covers BRDG-02
- [ ] `tests/v1/engine/test_bridge_sync.py` — covers BRDG-03
- [ ] `tests/v1/engine/test_bridge_compilation.py` — covers BRDG-06
- [ ] `tests/v1/engine/test_bridge_integration.py` — covers BRDG-04, BRDG-05 (requires @pytest.mark.java)
- [ ] Maven wrapper setup — required before Java-side integration tests can build the JAR

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| JVM lifecycle on RHEL | BRDG-05 | Dev machine is macOS, prod is RHEL | Verify bridge starts/stops cleanly on RHEL after deployment |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
