# Phase 2: Java Bridge Reliability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 02-java-bridge-reliability
**Areas discussed:** Rewrite vs fix-in-place, Schema-driven serialization API, Java-side scope, Test strategy, Error handling, Manager scope

---

## Rewrite vs Fix-in-Place

| Option | Description | Selected |
|--------|-------------|----------|
| Rewrite from scratch | Clean implementation with schema-driven serialization, consistent sync, proper logging, retry logic. API surface stays same, internals rebuilt. | |
| Targeted fixes only | Fix the 6 BRDG requirements in existing code. Faster but leaves print statements, structural inconsistencies. | |
| Rewrite both Python and Java | Full rewrite of bridge.py AND JavaBridge.java. Most thorough. | yes |

**User's choice:** Rewrite both Python and Java
**Notes:** User also specified: no emojis or non-ASCII characters in logging -- RHEL server compatibility requirement.

---

## Schema-Driven Serialization API

### Schema delivery mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Pass schema per call | Each bridge method receives explicit schema dict. Bridge converts types deterministically. No guessing. | yes |
| Bridge reads from component config | Bridge gets access to component's schema config. Reduces per-call boilerplate but couples bridge to config format. | |
| You decide | Claude picks cleanest API design. | |

**User's choice:** Pass schema per call

### Type mapping responsibility

| Option | Description | Selected |
|--------|-------------|----------|
| Bridge maps Talend types | Bridge knows Talend-to-Arrow mapping. Single source of truth. Components pass schema as-is. | |
| Components pre-map to Arrow | Components convert types before calling bridge. Spreads mapping logic. | |
| Standardize one format app-wide | Research converter output, establish one schema format across entire application. | yes |

**User's choice:** Standardize one schema format across entire application
**Notes:** User expressed this has been a major pain point. Wants research to audit converter output format and make that THE standard used everywhere -- bridge, engine, all downstream code.

---

## Java-Side Scope

### Rewrite scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full audit and rewrite | Audit JavaBridge.java and RowWrapper.java for unused code, type bugs, dead paths. Rewrite both. | yes |
| Rewrite only what Python touches | Only rewrite Java methods called by new Python bridge. Leave other code untouched. | |
| You decide | Claude determines minimum viable Java changes. | |

**User's choice:** Full audit and rewrite

### Dependency upgrades

| Option | Description | Selected |
|--------|-------------|----------|
| Upgrade both Py4J and Arrow | Py4J 0.10.9.7->0.10.9.9, Arrow 15.0.2->latest. | |
| Py4J only | Only upgrade Py4J for retry fix. Arrow stays at 15.0.2. | yes |
| You decide | Claude determines safest upgrade path. | |

**User's choice:** Py4J only

---

## Error Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Fail fast with clear error | Raise JavaBridgeError immediately on failure. No silent fallback. | yes |
| Graceful degradation | Log warning, fall back to Python-side handling where possible. | |
| You decide | Claude picks right error strategy. | |

**User's choice:** Fail fast with clear error

---

## Manager Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Update to match new bridge | Manager is already clean. Just update API compatibility. | |
| Rewrite alongside bridge | Rewrite for consistency. Add retry, health checks, better lifecycle. | |
| You decide | Claude decides based on research. | yes |

**User's choice:** You decide (Claude's discretion)

---

## Test Strategy

### Test approach

| Option | Description | Selected |
|--------|-------------|----------|
| Unit + integration | Unit tests with mocked Py4J + integration tests with real JVM. @pytest.mark.java marker. | yes |
| Integration only | Real JVM tests only. Bridge is inherently cross-process. | |
| Unit only | Mock Java side entirely. Fast but may diverge. | |

**User's choice:** Unit + integration

### Type coverage

| Option | Description | Selected |
|--------|-------------|----------|
| All 16 Talend types | Exhaustive round-trip for every Talend type. | |
| 12 types (skip byte[], List, Object, Document) | Covers all production-relevant types. | yes |
| Common types only | 8 types covering 90% of jobs. | |

**User's choice:** 12 types -- skip byte[], List, Object, Document
**Notes:** Subsequent component phases will add their own bridge testing. Java 21 available on dev machine.

---

## Claude's Discretion

- java_bridge_manager.py update vs rewrite
- Internal method design and data structures
- Retry logic specifics
- BRDG-06 compiled script synchronization approach
- BRDG-04 JAR/library loading approach

## Deferred Ideas

- Arrow version upgrade -- keep stable at 15.0.2
- Groovy version upgrade -- no pressing need
- byte[], List, Object, Document type support
- Database connection bridge support
