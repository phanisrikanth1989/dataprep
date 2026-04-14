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

- **After every task commit:** Run `pytest tests/v1/engine/test_bridge_type_mapping.py tests/v1/engine/test_bridge.py -x -m unit`
- **After every plan wave:** Run `pytest tests/v1/engine/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | BRDG-01, BRDG-02 | — | Schema-driven, no data inference | grep | inline grep checks (Wave 1 creates code, not tests) | N/A | ⬜ pending |
| 02-01-02 | 01 | 1 | BRDG-03 | — | Sync at every call site | grep | inline grep checks (Wave 1 creates code, not tests) | N/A | ⬜ pending |
| 02-02-01 | 02 | 1 | BRDG-04, BRDG-05 | — | N/A | grep | inline grep checks (pom.xml version, class existence) | N/A | ⬜ pending |
| 02-02-02 | 02 | 1 | BRDG-06 | — | No synchronized bottleneck | grep | inline grep checks (class caching pattern) | N/A | ⬜ pending |
| 02-03-01 | 03 | 2 | BRDG-01, BRDG-02 | — | Schema-driven types | unit | `pytest tests/v1/engine/test_bridge_type_mapping.py -x -m unit` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 2 | BRDG-02, BRDG-03 | — | Sync + serialization | unit | `pytest tests/v1/engine/test_bridge.py -x -m unit` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 3 | BRDG-04, BRDG-05 | — | N/A | integration | `pytest tests/v1/engine/test_bridge_integration.py -x -m java` | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 3 | BRDG-01, BRDG-06 | — | 12-type round-trip | integration | `pytest tests/v1/engine/test_bridge_integration.py -x -m java` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/v1/engine/test_bridge_type_mapping.py` — covers BRDG-01, BRDG-02 (created in Plan 03)
- [ ] `tests/v1/engine/test_bridge.py` — covers BRDG-02, BRDG-03 (created in Plan 03)
- [ ] `tests/converters/talend_to_v1/components/transform/test_map_types.py` — covers D-05a converter fix (created in Plan 03)
- [ ] `tests/v1/engine/test_bridge_integration.py` — covers BRDG-04, BRDG-05, BRDG-06 (created in Plan 04, requires @pytest.mark.java)
- [ ] Maven installation — `brew install maven` required before Java-side JAR rebuild

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
