# Phase 1: Infrastructure Bug Fixes & Project Setup - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix engine base classes and shared infrastructure so they're correct and stable. Any component built on top of BaseComponent, GlobalMap, ContextManager, and TriggerManager can trust their behavior. Create project build configuration and test infrastructure.

</domain>

<decisions>
## Implementation Decisions

### Migration Scope
- **D-01:** Print-to-logger (ENG-11) and exception hierarchy (ENG-12) migration covers infrastructure files ONLY: base_component.py, global_map.py, context_manager.py, trigger_manager.py, engine.py, exceptions.py. Later phases clean up their own component files.
- **D-02:** ENG-13 (config key alignment — fieldseparator vs delimiter) is deferred to component phases. It's a per-component issue spanning multiple phases, similar to TEST-03.
- **D-03:** ENG-14 (encoding/delimiter/header default mismatches) is deferred to component phases — same logic as ENG-13.
- **D-04:** ENG-17 (REJECT flow routing) stays in Phase 1. The engine provides the plumbing to route any named output flow (reject, duplicates, etc.) to the correct downstream component. Individual components are responsible for producing data on those flows in their respective phases.
- **D-05:** ENG-18 (resolve_dict corrupts python_code during context resolution) stays in Phase 1 — the root cause is in infrastructure code (ContextManager/BaseComponent), even though it manifests in Python components.
- **D-06:** ENG-22 (converter .find().get() null-safety) — verify during research phase whether already resolved. Skip if fixed.
- **D-07:** ENG-23 (discover additional bugs) — research phase must: (a) verify all ENG-01 through ENG-22 against actual code to separate real bugs from audit hallucinations, (b) actively hunt for additional bugs in infrastructure files, (c) report confirmed vs. hallucinated issues. Plan only covers verified + newly discovered bugs.

### Component Template (BaseComponent Refactor)
- **D-08:** Comprehensive refactor of BaseComponent with explicit lifecycle hooks (not just bug fixes). This sets the pattern for all 12+ target components in later phases.
- **D-09:** Lifecycle designed as a proper contract, but components can extend or override if needed. tMap and other complex components should be able to hook into the lifecycle without being forced into a rigid mold.
- **D-10:** `_validate_config()` becomes abstract and required — every component MUST implement it. Enforces discipline across all components.
- **D-11:** Create `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` — same prescriptive style as CONVERTER_PATTERN.md. Complete code template with numbered rules that every engine component must follow.
- **D-12:** Create `docs/v1/standards/ENGINE_TEST_PATTERN.md` — test pattern for engine component tests, mirroring TEST_PATTERN.md for converter tests.
- **D-13:** Leave AUDIT_REPORT_TEMPLATE.md as-is. Resolved edge-case checklist items become naturally obsolete.

### Test Strategy
- **D-14:** JavaBridgeManager tests are deferred to Phase 2 (Java Bridge Reliability). Phase 1 tests only cover Python-side infrastructure: GlobalMap, ContextManager, TriggerManager.
- **D-15:** In-memory DataFrames for test data. No file I/O fixtures in Phase 1 — real file fixtures come in Phase 4 (File I/O Components) and Phase 12 (Integration Testing).
- **D-16:** Pytest markers defined from the start: unit, integration, java, slow. Configured in pyproject.toml. Enables `pytest -m unit` for fast feedback.
- **D-17:** Minimal conftest.py — markers and basic pytest configuration only. Each test file creates its own fixtures explicitly. No shared fixture objects.
- **D-18:** Engine test location: `tests/v1/engine/` matching the source structure `src/v1/engine/`.
- **D-19:** Local pytest only — no CI configuration in Phase 1.
- **D-20:** Exhaustive test coverage for core infrastructure (GlobalMap, ContextManager, TriggerManager) — comprehensive edge cases including empty inputs, None/NaN values, type coercion, concurrent access patterns, large data. Not just happy paths.

### Build Setup
- **D-21:** Compatible dependency ranges in pyproject.toml (>=min,<next_major format). No exact pins in the project file.
- **D-22:** Optional dependency groups: core (pandas, numpy), java (pyarrow, py4j), dev (pytest). Install via `pip install -e .[dev,java]`.
- **D-23:** Pytest configuration in pyproject.toml under [tool.pytest.ini_options] — test paths, markers, default addopts. Single source of truth.
- **D-24:** Full project metadata in pyproject.toml — name, version, description, python_requires='>=3.10'.

### Claude's Discretion
- Build backend choice (setuptools vs hatch vs other — leaning setuptools)
- Specific lifecycle hook names and design for the BaseComponent refactor
- ENG-22 disposition — pending verification during research phase
- Exact dependency version ranges based on current environment

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Cross-Cutting Bug Reference
- `docs/v1/audit/CROSS_CUTTING_ISSUES.md` — Canonical list of cross-cutting engine bugs. Many overlap with ENG-01 through ENG-10. Research must verify these against actual code.
- `docs/v1/audit/METHODOLOGY.md` — Audit methodology and mandatory edge-case checklist (NaN handling, empty DataFrame, config mutation, etc.)
- `docs/v1/audit/SUMMARY_SCORECARD.md` — Component-level traffic light scores

### Standards (Pattern Templates)
- `docs/v1/standards/CONVERTER_PATTERN.md` — Gold standard converter pattern. ENGINE_COMPONENT_PATTERN.md must match this quality and prescriptive style.
- `docs/v1/standards/TEST_PATTERN.md` — Gold standard converter test pattern. ENGINE_TEST_PATTERN.md must mirror this for engine tests.
- `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` — Audit report template (not modified in Phase 1, but referenced for context)

### Codebase Analysis
- `.planning/codebase/CONCERNS.md` — Known bugs, fragile areas, security considerations, performance bottlenecks
- `.planning/codebase/ARCHITECTURE.md` — System architecture, layers, data flow, key abstractions

### Infrastructure Source Files (Primary Targets)
- `src/v1/engine/base_component.py` — BaseComponent (ENG-01, ENG-03, ENG-07, ENG-08, ENG-09, ENG-16, ENG-17, ENG-18, ENG-19, ENG-20, ENG-21)
- `src/v1/engine/global_map.py` — GlobalMap (ENG-02)
- `src/v1/engine/context_manager.py` — ContextManager (ENG-05, ENG-18)
- `src/v1/engine/trigger_manager.py` — TriggerManager (ENG-06)
- `src/v1/engine/engine.py` — Engine core (ENG-04, ENG-17 routing)
- `src/v1/engine/exceptions.py` — Exception hierarchy (ENG-12)

### Requirements
- `.planning/REQUIREMENTS.md` — Full requirements list with ENG-01 through ENG-23, TEST-01, TEST-02 mapped to Phase 1

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Exception hierarchy already exists at `src/v1/engine/exceptions.py` — ETLError, ConfigurationError, DataValidationError, ComponentExecutionError, FileOperationError, JavaBridgeError, ExpressionError, SchemaError. Phase 1 wires this in properly.
- BaseIterateComponent at `src/v1/engine/base_iterate_component.py` — extends BaseComponent for iterate. Refactor must preserve this subclass relationship.
- Converter test infrastructure at `tests/converters/talend_to_v1/` — mature pattern with fixtures, per-concern test classes. Engine tests should match this quality.

### Established Patterns
- Converter uses decorator-based registry (`@REGISTRY.register("tComponentName")`). Engine uses static dict `COMPONENT_REGISTRY`. No change planned to engine registry pattern in Phase 1.
- Components use template method: `execute()` orchestrates, `_process()` is abstract. Refactor extends this with lifecycle hooks but preserves the core template method pattern.
- Module-level loggers via `logging.getLogger(__name__)` already used in most files. Phase 1 ensures consistency.

### Integration Points
- BaseComponent.execute() is called by ETLEngine._execute_component() — any lifecycle changes must remain compatible with the engine's execution loop.
- GlobalMap is shared state accessed by all components, ContextManager, and JavaBridgeManager — changes must be thread-safe conceptually even though execution is single-threaded (future-proofing for Phase 10 iterate).
- Config snapshot/restore (D-08, D-09) enables Phase 10 iterate re-execution — must be designed with that use case in mind.

</code_context>

<specifics>
## Specific Ideas

- ENGINE_COMPONENT_PATTERN.md should be directly usable by developers and AI agents — same prescriptive quality as CONVERTER_PATTERN.md with complete code template, numbered rules, and a reference section
- Standards docs live at `docs/v1/standards/` alongside existing converter standards
- Research phase must actively look for bugs beyond the audit list — don't just verify, discover
- ENG-13 and ENG-14 are cross-cutting requirements spanning multiple phases (like TEST-03) — they stay in REQUIREMENTS.md as multi-phase requirements

</specifics>

<deferred>
## Deferred Ideas

- ENG-13 (config key alignment) — defer to component phases (Phase 4+), per-component issue
- ENG-14 (encoding/delimiter/header defaults) — defer to component phases, same reasoning
- Print→logger in non-infrastructure component files — each phase cleans its own components
- Exception hierarchy migration in non-infrastructure component files — each phase handles its own
- CI configuration (GitHub Actions) — defer until test suite is substantial
- ENG-22 (converter null-safety) — verify during research, may already be resolved

</deferred>

---

*Phase: 01-infrastructure-bug-fixes-project-setup*
*Context gathered: 2026-04-14*
