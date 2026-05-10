---
phase: 14
slug: coverage-push-to-95-per-module-floor
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-10
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-cov 7.0.0 + pytest-xdist 3.8.0 |
| **Config file** | `pyproject.toml` ([tool.pytest.ini_options], [tool.coverage.*] added in Plan 14-01) |
| **Quick run command** | `python -m pytest tests/ -m "not oracle" -n auto -q --tb=short` |
| **Full suite command** | `rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto --cov=src/v1/engine --cov=src/converters --cov-report=term-missing --cov-report=html --cov-report=json` |
| **Estimated runtime** | quick: ~30s parallel; full with cov: ~60-120s parallel |

---

## Sampling Rate

- **After every task commit:** Run quick run command on the touched test files only (e.g. `python -m pytest tests/v1/engine/components/file/test_file_input_excel.py -q`)
- **After every plan wave:** Run quick run command on the full suite (no coverage)
- **After every plan completes:** Run full suite command and verify per-module floor for the modules in scope of that plan
- **Before `/gsd-verify-work`:** Full suite green AND per-module floor enforcement script (Plan 14-01) reports zero violations
- **Max feedback latency:** 30s for per-task, 120s for full coverage run

---

## Per-Task Verification Map

> Populated by gsd-planner during plan generation. Each task in each PLAN.md gets a row mapping to the test files / fixtures it touches and the per-module floor target.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| (planner fills) | 14-NN | N | TEST-11 / TEST-12 | unit / pipeline / infra | (planner specifies) | ✅ / ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` (root) — shared fixtures: `run_job_fixture`, fixture-jobs path resolver, pandas-3.0 dtype helpers (Plan 14-01)
- [ ] `tests/fixtures/jobs/` — directory scaffolding + README documenting JSON-job format (Plan 14-01)
- [ ] `tests/fixtures/swift/` — synthetic SWIFT MT generator helpers (Plan 14-08; Wave 0 only the directory + skeleton)
- [ ] `pyproject.toml` `[tool.coverage.run]` + `[tool.coverage.report]` blocks (Plan 14-01)
- [ ] `pyproject.toml` dev extra: add `pytest-xdist>=3.8,<4` explicit declaration (researcher finding — currently installed but not pinned)
- [ ] `scripts/check_per_module_coverage.py` — ~40 LOC enforcement script parsing `coverage.json` (Plan 14-01)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live SMTP send for `send_mail.py` | (none — boundary mocked per D-A4) | N/A — smtplib mocked | N/A |
| Live Oracle DB write for `oracle_output.py` | (Phase 11 testcontainer suite via `-m oracle`) | Docker / testcontainer required (Phase 11 verification debt remains human-run) | `pytest -m oracle` against `gvenzl/oracle-free:23-slim-faststart` |
| JVM lifecycle for `java_bridge_manager.py` | TEST-11 | `-m java` requires JVM 11+ in env; gate command (D-A3) measures with `-m java` so this becomes automated when run on a JVM-equipped machine | `pytest -m java tests/v1/engine/test_java_bridge_manager.py` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (root conftest, fixture-jobs scaffolding, coverage tool config, xdist pin)
- [ ] No watch-mode flags (gate command is one-shot, not `pytest-watch`)
- [ ] Feedback latency < 120s for full cov run
- [ ] `nyquist_compliant: true` set in frontmatter after planner populates the per-task verification map

**Approval:** pending
