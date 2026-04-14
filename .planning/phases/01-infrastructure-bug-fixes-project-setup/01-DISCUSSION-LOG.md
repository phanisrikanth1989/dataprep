# Phase 1: Infrastructure Bug Fixes & Project Setup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 01-infrastructure-bug-fixes-project-setup
**Areas discussed:** Migration scope, Component template, Test strategy, Build setup

---

## Migration Scope

### Print/Exception Migration Scope

| Option | Description | Selected |
|--------|-------------|----------|
| All files now | Fix all 79+ print statements and exception patterns in one pass. ~2-3 hours extra. | |
| Infrastructure only | Only fix base_component.py, global_map.py, context_manager.py, trigger_manager.py, engine.py, exceptions.py. | ✓ |
| Infrastructure + target 12 | Fix infrastructure plus the 12 priority component files. | |

**User's choice:** Infrastructure only
**Notes:** Later phases clean up their own component files.

### ENG-13 Config Key Alignment

| Option | Description | Selected |
|--------|-------------|----------|
| Normalization layer | Add key translation step in engine before component instantiation. | |
| Update each component | Modify each engine component to try both key names. | |
| You decide | Claude picks. | |

**User's choice:** Defer entirely — this is a per-component issue, not engine infrastructure. Fix when working on each component.

### ENG-14 Default Mismatches

| Option | Description | Selected |
|--------|-------------|----------|
| Defer to component phases | Same logic as ENG-13. | ✓ |
| Keep in Phase 1 | Fix default mismatches now. | |

**User's choice:** Defer to component phases

### ENG-17 REJECT Flow Routing

| Option | Description | Selected |
|--------|-------------|----------|
| Keep in Phase 1 | REJECT routing is engine infrastructure. | ✓ |
| Defer to Phase 3 | Execution loop restructure is Phase 3. | |

**User's choice:** Keep in Phase 1 — engine provides plumbing for all alternate flows (reject, duplicates, etc.). Components produce data on those flows in their phases.

### ENG-18 resolve_dict Corruption

| Option | Description | Selected |
|--------|-------------|----------|
| Fix in Phase 1 | Root cause in infrastructure code. | ✓ |
| Defer to Phase 8 | Fix when working on code components. | |

**User's choice:** Fix in Phase 1

### ENG-22 Converter Null-Safety

**User's choice:** Verify during research — user believes it may already be resolved.

### ENG-23 Bug Discovery

| Option | Description | Selected |
|--------|-------------|----------|
| Opportunistic | Fix bugs found while working on ENG-01-22. | |
| Dedicated pass | Review infrastructure files specifically. | ✓ |

**User's choice:** Research phase does dedicated verification of all ENG requirements AND actively hunts for additional bugs. This separates real issues from potential hallucinations in the audit.

### Deferred Item Tracking

**User's choice:** ENG-13 and ENG-14 stay in REQUIREMENTS.md as multi-phase requirements (like TEST-03). CONTEXT.md notes the deferral.

---

## Component Template

### Standardization Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Fix and document | Fix bugs, document the lifecycle in code comments. | |
| Comprehensive refactor | Explicit lifecycle hooks, reference implementation, clearer contract. | ✓ |
| You decide | Claude picks. | |

**User's choice:** Comprehensive refactor

### tMap Accommodation

| Option | Description | Selected |
|--------|-------------|----------|
| Accommodate in base | Design lifecycle flexible enough for tMap. | |
| Force conform in Phase 5 | Standard lifecycle, tMap refactors later. | |

**User's choice:** Design lifecycle as a proper contract but components can do things outside it if needed. Extensible, not rigid.

### _validate_config() Enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Abstract (required) | Every component must implement it. | ✓ |
| Optional with no-op default | Override if needed, skip if not. | |
| You decide | Claude decides. | |

**User's choice:** Abstract (required)

### Reference Implementation

| Option | Description | Selected |
|--------|-------------|----------|
| Reference implementation | Create example component showing full lifecycle. | |
| BaseComponent + docs only | Refactored base class + standards documentation. | ✓ |

**User's choice:** BaseComponent + docs. Create ENGINE_COMPONENT_PATTERN.md in docs/v1/standards/ — same style as CONVERTER_PATTERN.md. Referenced existing converter standards work.

### Engine Test Pattern

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, create both | ENGINE_COMPONENT_PATTERN.md + ENGINE_TEST_PATTERN.md. | ✓ |
| Component pattern only | Pattern doc only, test patterns emerge organically. | |
| You decide | Claude decides. | |

**User's choice:** Create both docs under docs/v1/standards/

### Audit Template Update

| Option | Description | Selected |
|--------|-------------|----------|
| Update after Phase 1 | Refresh edge-case checklist post-refactor. | |
| Leave as-is | Audit template stays unchanged. | ✓ |

**User's choice:** Leave as-is

---

## Test Strategy

### Java Bridge Dependency

| Option | Description | Selected |
|--------|-------------|----------|
| Mock the bridge | Unit tests mock JavaBridgeManager. | |
| Require JVM | Tests start a real Java bridge. | |
| Skip bridge tests | Test only Python-side. Bridge tests in Phase 2. | ✓ |
| You decide | Claude picks. | |

**User's choice:** Mark bridge tests as Phase 2 so they can test against actual Java bridge.

### Test Data Approach

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory DataFrames | pd.DataFrame() fixtures. Fast, no file dependency. | ✓ |
| Both from start | Sample CSV files AND DataFrame fixtures. | |
| You decide | Claude picks. | |

**User's choice:** In-memory DataFrames

### Pytest Markers

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, markers from start | unit, integration, java, slow markers in conftest. | ✓ |
| No markers yet | Keep simple, add later. | |
| You decide | Claude decides. | |

**User's choice:** Markers from the start

### Shared Fixtures

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, shared fixtures | conftest provides GlobalMap, ContextManager, sample configs. | |
| Minimal conftest | Markers and pytest config only. Each test creates own fixtures. | ✓ |
| You decide | Claude designs as needed. | |

**User's choice:** Minimal conftest

### Test Location

| Option | Description | Selected |
|--------|-------------|----------|
| tests/engine/ | Mirror converter structure. | |
| tests/v1/engine/ | Match source structure src/v1/engine/. | ✓ |
| You decide | Claude picks. | |

**User's choice:** tests/v1/engine/

### CI Configuration

| Option | Description | Selected |
|--------|-------------|----------|
| Local pytest only | No CI config in Phase 1. | ✓ |
| Include basic CI | GitHub Actions workflow. | |
| You decide | Claude decides. | |

**User's choice:** Local pytest only

### Coverage Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Known bugs + happy paths | Regression tests + basic coverage. | |
| Exhaustive coverage | Comprehensive edge cases. | ✓ |
| You decide | Claude decides risk-based. | |

**User's choice:** Exhaustive coverage

---

## Build Setup

### Build Backend

| Option | Description | Selected |
|--------|-------------|----------|
| setuptools | Standard, minimal. | |
| hatch | Modern PEP-compliant. | |
| poetry | Dependency management + build. | |
| You decide | Claude picks. | ✓ |

**User's choice:** You decide (Claude's discretion)

### Dependency Pinning

| Option | Description | Selected |
|--------|-------------|----------|
| Compatible ranges | >=min,<next_major in pyproject.toml. | ✓ |
| Exact pins | Pin every dependency exactly. | |
| You decide | Claude picks. | |

**User's choice:** Compatible ranges

### Dependency Groups

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, with groups | core, java, dev optional groups. | ✓ |
| Single flat list | All dependencies in one list. | |
| You decide | Claude decides. | |

**User's choice:** Yes, with groups

### Pytest in pyproject.toml

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, configure in pyproject.toml | [tool.pytest.ini_options] section. | ✓ |
| Separate pytest.ini | Traditional separate file. | |
| You decide | Claude picks. | |

**User's choice:** In pyproject.toml

### Project Metadata

| Option | Description | Selected |
|--------|-------------|----------|
| Full metadata | name, version, description, python_requires. | ✓ |
| Dependencies only | Minimal build + deps. | |

**User's choice:** Full metadata

---

## Claude's Discretion

- Build backend choice (setuptools most likely)
- Specific lifecycle hook names/design for BaseComponent refactor
- ENG-22 disposition pending verification

## Deferred Ideas

- ENG-13 config key alignment — component phases
- ENG-14 default mismatches — component phases
- Print/exception cleanup in non-infrastructure files — each phase
- CI configuration — later when test suite is substantial
