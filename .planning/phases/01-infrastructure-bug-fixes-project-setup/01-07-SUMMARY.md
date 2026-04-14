---
phase: "01"
plan: "07"
subsystem: documentation
tags: [standards, engine-pattern, test-pattern, gold-standard]
dependency_graph:
  requires: ["01-05", "01-06"]
  provides: ["ENGINE_COMPONENT_PATTERN", "ENGINE_TEST_PATTERN"]
  affects: ["all-future-engine-components"]
tech_stack:
  added: []
  patterns: ["template-method-lifecycle", "one-class-per-concern-testing"]
key_files:
  created:
    - docs/v1/standards/ENGINE_COMPONENT_PATTERN.md
    - docs/v1/standards/ENGINE_TEST_PATTERN.md
  modified: []
decisions:
  - "12 numbered rules for engine components covering lifecycle, config access, exceptions, logging, registration, and iterate safety"
  - "8 required test categories per component: Validation, Defaults, MainFlow, RejectFlow, EdgeCases, GlobalMapVariables, SchemaHandling, IterateReexecution"
  - "Test through execute() lifecycle, not _process() directly, to catch config resolution and stats bugs"
metrics:
  duration_seconds: 244
  completed: "2026-04-14T10:33:32Z"
---

# Phase 01 Plan 07: Engine Standards Documentation Summary

Prescriptive gold-standard docs for engine component implementation and testing, matching CONVERTER_PATTERN.md quality with 12 rules and 8 test categories referencing the rewritten BaseComponent API.

## What Was Done

### Task 1: Create ENGINE_COMPONENT_PATTERN.md (ee9b6ac)

Created `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` with:

- **Complete code template** showing the full structure of an engine component class extending BaseComponent
- **12 numbered rules** covering: class inheritance, _validate_config(), _process() return contract, never override execute(), config access timing, GlobalMap usage, custom exceptions, logging, COMPONENT_REGISTRY registration, iterate safety, schema validation, and module docstrings
- **Config access pattern** explaining the BaseComponent lifecycle: construction -> fresh deepcopy -> validate -> resolve -> process
- **REJECT flow pattern** showing how to route rejected rows with automatic stats tracking
- **GlobalMap variables pattern** with Talend naming conventions for all standard variable types
- **Anti-patterns section** with 6 anti-patterns: don't override execute(), don't read config in __init__, don't mutate _original_config, don't use print(), don't raise generic Exception, don't store state on self
- **Iterate component pattern** showing BaseIterateComponent usage with prepare_iterations() and set_iteration_globalmap()
- **BaseComponent API reference** documenting constructor, instance attributes, available methods, enums (ExecutionMode, ComponentStatus), and the complete exception hierarchy

### Task 2: Create ENGINE_TEST_PATTERN.md (d558341)

Created `docs/v1/standards/ENGINE_TEST_PATTERN.md` with:

- **Complete test file template** showing fixtures, test classes, and assertion patterns
- **8 required test categories**: TestValidation, TestDefaults, TestMainFlow, TestRejectFlow, TestEdgeCases, TestGlobalMapVariables, TestSchemaHandling, TestIterateReexecution
- **Fixture patterns**: _make_component() with fresh GlobalMap/ContextManager, _make_input_df() with realistic data, _DEFAULT_CONFIG constant
- **11 numbered rules** covering: one-class-per-concern, module-level fixtures, in-memory DataFrames, fresh state per test, test through execute(), pytest.mark.unit, file naming, no shared conftest, test both success and error, verify stats, iterate re-execution mandatory
- **Anti-patterns section** with 6 anti-patterns: don't test private methods, don't use shared mutable fixtures, don't skip edge cases, don't test only happy path, don't mock component under test, don't use file I/O in unit tests
- **Test directory structure** mirroring source layout
- **Coverage categories checklist** for pre-submission verification

## Deviations from Plan

None -- plan executed exactly as written.

## Self-Check: PASSED

- [x] docs/v1/standards/ENGINE_COMPONENT_PATTERN.md exists (614 lines)
- [x] docs/v1/standards/ENGINE_TEST_PATTERN.md exists (625 lines)
- [x] ENGINE_COMPONENT_PATTERN.md has 12 numbered rules (>= 10 required)
- [x] ENGINE_TEST_PATTERN.md has 15 test class examples (>= 5 required)
- [x] Both reference rewritten BaseComponent API (not old version)
- [x] Both match CONVERTER_PATTERN.md / TEST_PATTERN.md prescriptive style
- [x] Commit ee9b6ac found in git log
- [x] Commit d558341 found in git log
