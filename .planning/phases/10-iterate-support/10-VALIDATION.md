---
phase: 10
slug: iterate-support
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-05
---

# Phase 10 -- Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing; runtime version detected at execution) |
| **Config file** | none -- pytest discovers via `tests/` dir convention; markers `java` registered via existing `tests/v1/engine/conftest.py` |
| **Quick run command** | `pytest tests/v1/engine/test_base_iterate_component.py tests/v1/engine/test_executor_iterate.py -x` |
| **Full suite command** | `pytest tests/v1/engine/ tests/integration/test_iterate_e2e.py tests/converters/talend_to_v1/test_iterate_connection_extraction.py` |
| **Java suite** | `pytest tests/integration/test_iterate_e2e.py -m java` (requires built JAR) |
| **Estimated runtime** | ~5s quick, ~30s full unit, ~60s with java integration |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/v1/engine/test_base_iterate_component.py tests/v1/engine/test_executor_iterate.py -x` (~5s)
- **After every plan wave:** Run `pytest tests/v1/engine/ tests/converters/talend_to_v1/test_iterate_connection_extraction.py -x` (~30s)
- **Before `/gsd-verify-work`:** Full suite incl. `@pytest.mark.java` integration must be green
- **Max feedback latency:** 30 seconds for sampled checks

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|---|---|---|---|---|---|
| EXEC-04 | Iterate loop executes body N times per item | unit | `pytest tests/v1/engine/test_executor_iterate.py::test_body_runs_per_item -x` | W0 | pending |
| EXEC-05 | BaseComponent.reset() called between iterations | unit | `pytest tests/v1/engine/test_executor_iterate.py::test_body_components_reset_between_iters -x` | W0 | pending |
| EXEC-06 | Body components see fresh _original_config per iteration | unit | `pytest tests/v1/engine/test_executor_iterate.py::test_body_config_freshness -x` | W0 | pending |
| ITER-01 | tFlowToIterate iterates each input row | unit | `pytest tests/v1/engine/components/iterate/test_flow_to_iterate.py::test_iterates_each_row -x` | W0 | pending |
| ITER-02 | DEFAULT_MAP=true sets `<flow>.<col>` keys | unit | `pytest tests/v1/engine/components/iterate/test_flow_to_iterate.py::test_default_map_keys -x` | W0 | pending |
| ITER-03 | Custom MAP uses entry['key']/entry['value'] | unit | `pytest tests/v1/engine/components/iterate/test_flow_to_iterate.py::test_custom_map_mode -x` | W0 | pending |
| ITER-04 | tFileList walks directory matching FILES masks | unit | `pytest tests/v1/engine/components/file/test_file_list.py::test_walks_files -x` | W0 | pending |
| ITER-05 | All 5 RETURN globalMap vars set per file | unit | `pytest tests/v1/engine/components/file/test_file_list.py::test_globalmap_return_vars -x` | W0 | pending |
| ITER-06 | INCLUDSUBDIR true recurses, false does not | unit | `pytest tests/v1/engine/components/file/test_file_list.py::test_recursive_walk -x` | W0 | pending |
| ITER-07 | All 4 sort orders + ASC/DESC applied | unit | `pytest tests/v1/engine/components/file/test_file_list.py::test_sort_variants -x` | W0 | pending |
| ITER-08 | tFileExist accepts file_name OR file_path | unit | `pytest tests/v1/engine/components/file/test_file_exist.py::test_accepts_both_keys` | EXISTS (verify only) | pending |
| ITER-09 | tFileExist sets _EXISTS, _FILENAME globalMap | unit | `pytest tests/v1/engine/components/file/test_file_exist.py::test_globalmap_vars` | EXISTS (verify only) | pending |
| ITER-10 | All iterate components in COMPONENT_REGISTRY | unit | `pytest tests/v1/engine/test_component_registry.py::test_iterate_components_registered -x` | W0 | pending |
| ITER-11 | tFlowToIterate sets _CURRENT_ITERATION (renamed from _CURRENT_ITERATE) | unit | `pytest tests/v1/engine/test_base_iterate_component.py::test_current_iteration_key_name -x` | W0 | pending |
| TEST-04 | Iterate components covered by unit tests with coverage gate >=90% on new files | unit | runs all of the above; coverage gate enforced in 10-07 | W0 | pending |
| TEST-04 (integ) | End-to-end .item -> JSON -> execute (both fixtures) | integration | `pytest tests/integration/test_iterate_e2e.py -m java` | W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/v1/engine/test_base_iterate_component.py` -- covers ITER-11, lifecycle hooks, iterator-based items, typed item dataclasses
- [ ] `tests/v1/engine/test_executor_iterate.py` -- covers EXEC-04, EXEC-05, EXEC-06, per-iter trigger firing, REJECT accumulation
- [ ] `tests/v1/engine/test_execution_plan_iterate.py` -- covers body subgraph BFS + nested-iterate detection
- [ ] `tests/v1/engine/test_output_router_iterate.py` -- covers `drain_reject_flows` helper
- [ ] `tests/v1/engine/components/file/test_file_list.py` -- covers ITER-04, ITER-05, ITER-06, ITER-07, ERROR=true 0-match, FORMAT_FILEPATH_TO_SLASH
- [ ] `tests/v1/engine/components/iterate/__init__.py` -- new test directory init
- [ ] `tests/v1/engine/components/iterate/test_flow_to_iterate.py` -- covers ITER-01, ITER-02, ITER-03, ITER-11, empty input, DEFAULT_MAP true/false branches
- [ ] `tests/converters/talend_to_v1/test_iterate_connection_extraction.py` -- covers ENABLE_PARALLEL/NUMBER_PARALLEL extraction + needs_review
- [ ] `tests/v1/engine/test_iterate_logging.py` -- covers logging tiers H1..H7, ASCII-only enforcement, threshold behavior
- [ ] `tests/integration/test_iterate_e2e.py` -- covers TEST-04 integration with both `.item` fixtures (`Job_tFileList_0.1.item`, `Job_tFlowToIterate_0.1.item`)
- [ ] Conftest extension: add `IterateStubComponent`, `make_iterate_job_config` to `tests/v1/engine/conftest.py`

*pytest framework already installed; no framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Talend Studio output byte-comparison | TEST-06 (Phase 12) | Requires Talend Studio license + manual job execution | Deferred to Phase 12 / TEST-06. Phase 10 verifies engine correctness against Talaxie source-of-truth, not against a Talend Studio reference run. |
| Production scale (10000+ files in tFileList) | (perf) | Memory pressure at scale; outside Phase 10 unit-test runtime budget | Performance test deferred to Phase 12+. |

*All in-scope Phase 10 behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s for sampled checks
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
