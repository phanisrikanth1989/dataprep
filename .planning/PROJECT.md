# DataPrep — Talend ETL Migration Engine

## What This Is

A Python-based ETL execution engine that replaces Talend Open Studio for 1200+ production jobs. The system has two layers: a converter that transforms Talend `.item` XML job definitions into JSON configurations, and an engine that executes those JSON configs. The converter side is clean and standardized. The engine side works partially but has systemic quality gaps, missing features, and unreliable behavior that must be fixed before production use.

## Core Value

Any Talend job using the target components must produce identical results when run through the Python engine — feature parity with Talend is non-negotiable.

## Requirements

### Validated

- ✓ Converter pipeline (XML → JSON) for all 81 component types — existing (Python and swift componemts skipped for converter)
- ✓ Converter registry pattern with decorator-based auto-registration — existing
- ✓ Converter ABC (ComponentConverter) with standardized interface — existing
- ✓ Per-component converter tests with comprehensive coverage — existing
- ✓ Post-conversion validation (reference integrity, tMap, expressions, quality) — existing
- ✓ Expression converter for Java-to-Python transformation — existing
- ✓ Trigger mapper for subjob orchestration connections — existing
- ✓ Type mapping (Talend types → Python types) — existing
- ✓ UI registry with component metadata and connectors — existing

### Active

**Engine Core:**
- [x] Fix all cross-cutting P0-P3 bugs in base_component.py, global_map.py, context_manager.py, trigger_manager.py, engine.py *(Phase 1)*
- [x] Fix engine execution loop — subjob tracking, trigger firing, input dependency resolution, data flow routing *(Phase 3)*
- [x] Fix streaming mode — reject data silently dropped, chunk processing incomplete *(Phase 1)*
- [x] Standardize engine component template — BaseComponent pattern that becomes the blueprint for all components *(Phase 1)*
- [x] Replace all print() debug statements with proper logger usage across engine components *(Phase 1)*
- [x] Replace generic exceptions with custom exception hierarchy (ETLError, ConfigurationError, etc.) *(Phase 1)*
- [x] Discover and fix issues the audit reports missed *(Phase 1)*

**Target Components (Talend feature parity):**
- [x] tFileInputDelimited — full Talend feature parity (encoding, delimiters, headers, footers, schema, reject flow) *(Phase 4)*
- [x] tMap — full Talend feature parity (joins, expressions, filters, multiple inputs/outputs, reject, variables) *(Phase 5)*
- [x] tFileOutputDelimited — full Talend feature parity (encoding, delimiters, append, headers, schema) *(Phase 4)*
- [ ] tJava — full Talend feature parity (Java code execution, imports, context access)
- [ ] tJavaRow — full Talend feature parity (per-row Java execution, input/output column access)
- [ ] tContextLoad — full Talend feature parity (load context from flow, file, key-value parsing)
- [x] tAggregateRow — full rewrite with 12+ aggregation functions, Decimal precision, ignore_null, population_std_dev *(Phase 6)*
- [x] tSortRow — full rewrite with num/alpha/date sort types via pandas key=, simplified to batch-only *(Phase 6)*
- [x] tFilterRow — full rewrite with 15-operator function map (no eval), 8 FUNCTION pre-transforms *(Phase 6)*
- [x] tFilterColumns — full rewrite to schema-based filtering, 15 unit tests *(Phase 7)*
- [x] tJoin — full rewrite fixing P0 corruption, null semantics, reject, INCLUDE_LOOKUP, 35 unit tests *(Phase 7)*
- [x] tUnite — full rewrite to UNION-only concat, 18 unit tests *(Phase 7)*

**Python Equivalents:**
- [ ] python_component — Python equivalent of tJava, standardized alongside it
- [ ] python_row_component — Python equivalent of tJavaRow, standardized alongside it

**Java Bridge:** *(Validated in Phase 2)*
- [x] Fix data type serialization failures — schema-driven Arrow serialization for all 12 Talend types
- [x] Strengthen JAR/library loading — robust classpath management with Class.forName validation
- [x] Fix bidirectional context/globalMap sync — _call_java_with_sync at every call site

**Routines:**
- [ ] Java routines — custom utility functions callable from Java expressions (like Talend routine.jar)
- [ ] Python routines — custom utility functions callable from Python expressions and components

**Iterate Support:**
- [ ] tFlowToIterate — engine implementation with proper downstream subjob re-execution
- [ ] tFileList — iterate over files in directory
- [ ] tFileExist — iterate trigger based on file existence
- [ ] Engine execution loop iterate handling — proper re-execution of downstream subjobs per iteration item

**Oracle Components:**
- [ ] Verify current status of Oracle engine implementations
- [ ] Fix or implement Oracle connection, input, output, and related components

**Testing:**
- [ ] Engine unit tests for all target components (12 priority + iterate + Oracle)
- [ ] Engine unit tests for core infrastructure (GlobalMap, ContextManager, TriggerManager, JavaBridgeManager)
- [ ] Integration tests using real .item samples from tests/talend_xml_samples/

**Performance & Memory:**
- [ ] Streaming mode for large datasets — proper chunk processing without data loss
- [ ] Memory management for large DataFrames
- [ ] Performance optimization for row-by-row processing (PythonRowComponent, FilterRows eval)

**Converter & Report Updates:**
- [ ] Update converters for target components if any gaps found during engine work
- [ ] Update audit reports to reflect fixes

### Out of Scope

- Removing the legacy complex_converter — not blocking, defer to later cleanup
- Remaining ~74 engine components beyond the 12 targets — follow patterns from this milestone in future milestones
- UI job designer frontend — separate concern
- Distributed/parallel execution — single-threaded is fine for now
- Docker/container deployment — Linux server deployment, containerization later

## Context

- **Licensing urgency:** Talend licensing concerns are driving this migration — this is not optional work
- **1200+ jobs:** The system must eventually handle all production Talend jobs, but this milestone focuses on the foundational components that appear in most jobs
- **30% iterate dependency:** Roughly 30% of the 1200 jobs use iterate components (tFlowToIterate, tFileList, tFileExist), making iterate support critical
- **Converter is clean:** Previous GSD work (Phases 6-13) standardized all 81 converter components to Green status
- **Audit exists:** A comprehensive 86-component audit with 928 issues exists at docs/v1/audit/ — this is the primary reference for what needs fixing
- **Cross-cutting leverage:** Fixing ~15-20 unique cross-cutting bugs in base classes resolves ~200-250 of the 928 audit issues
- **Test fixtures available:** Talend XML samples at tests/talend_xml_samples/ and converted JSONs at tests/talend_xml_samples/converted_jsons/
- **Deployment target:** Linux servers with Python 3.10+ and JVM 11+

## Constraints

- **Tech stack**: Python 3.10+ engine, Java 11+ bridge via Py4J/Arrow — no framework changes
- **Compatibility**: Must produce identical output to Talend for the same input data and job configuration
- **Java bridge**: Must maintain Py4J + Arrow architecture — it works, just needs reliability fixes
- **No breaking changes**: Converter JSON format must remain compatible — engine changes cannot require re-conversion of existing JSONs
- **Existing patterns**: Engine component pattern must align with the established converter pattern philosophy (ABC + registry + per-component organization)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fix engine architecture (pragmatic refactor) | Engine execution loop is 140 lines of nested logic — fixing bugs in it is harder than cleaning it up. Refactor only what blocks component work. | ✓ Complete (Phase 3) — 5-file decomposition (component_registry, execution_plan, output_router, executor, engine.py), 98 tests, engine.py 868→259 lines |
| 12 priority components this milestone, all 86 for production | Fix 12 priority components + iterate + Oracle now. Remaining ~74 follow the established patterns in future milestones. All 86 needed for production readiness. | — Pending |
| Java Bridge before component work | Java expressions used throughout tMap and other components — bridge must be reliable before component hardening | ✓ Complete (Phase 2) — full rewrite both Python + Java, schema-driven serialization, 88 tests |
| Iterate support in this milestone | 30% of jobs use iterate — can't defer without blocking a third of production migration | — Pending |
| Leave legacy complex_converter | Not blocking production work, removing it is cleanup that can happen later | — Pending |
| Both unit and integration tests | Engine has zero tests today. Need unit tests for isolation + integration tests for confidence that converted jobs actually run. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-15 after Phase 5 completion*
