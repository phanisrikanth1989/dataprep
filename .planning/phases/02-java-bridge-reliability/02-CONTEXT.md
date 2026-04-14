# Phase 2: Java Bridge Reliability - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the Python-Java bridge (Py4J + Apache Arrow) reliable for data type serialization, bidirectional context/globalMap sync, JVM lifecycle management, and JAR/library loading -- so all downstream components using Java expressions (tMap, tJava, tJavaRow, routines) can depend on correct bridge behavior.

**Approach: Full rewrite of both Python and Java sides.** The current bridge.py has structural issues (data inference instead of schema-driven serialization, inconsistent sync, print statements everywhere, no retry logic) and JavaBridge.java may contain unused code. Instead of patching 6 individual issues, rewrite both sides with a clean design that inherently avoids those bugs.

**Phase 1 dependency:** Phase 1 rewrites BaseComponent, GlobalMap, ContextManager, TriggerManager. This phase rewrites the bridge layer that sits alongside those infrastructure classes. The rewritten bridge must integrate cleanly with Phase 1's new infrastructure.

</domain>

<decisions>
## Implementation Decisions

### Rewrite Approach
- **D-01:** Full rewrite of both `bridge.py` (Python client) and `JavaBridge.java` + `RowWrapper.java` (Java server). Not patching existing code. Audit for unused code and remove it.
- **D-02:** The API surface (method signatures visible to engine components) should remain similar, but internals are rebuilt from scratch with schema-driven serialization, consistent sync, proper logging, and retry logic.
- **D-03:** `java_bridge_manager.py` disposition is Claude's discretion -- update or rewrite based on what research reveals about needed changes.

### Schema-Driven Serialization
- **D-04:** Every bridge method receives an explicit schema dict mapping column names to types. No data inference. No guessing from first non-null value. Schema is the single source of truth for Arrow type mapping.
- **D-05:** Research phase MUST audit what format converters produce for schema in JSON configs. That format becomes THE standard schema representation across the entire application. Bridge, engine components, and all downstream code use the same schema format. This has been a pain point -- one format, everywhere.
- **D-06:** The bridge handles the mapping from the standardized schema format to Arrow types. Components pass schema as-is from their config. Single source of truth for type mapping lives in the bridge.

### Java-Side Scope
- **D-07:** Full audit and rewrite of JavaBridge.java (42KB) and RowWrapper.java. Remove unused code, fix type handling on the Java side, match the new Python bridge API.
- **D-08:** Upgrade Py4J from 0.10.9.7 to 0.10.9.9 (retry-on-empty-response fix). Both Python package and Java dependency in pom.xml.
- **D-09:** Arrow stays at 15.0.2 on both sides. No Arrow version upgrade -- current version works, lower risk.
- **D-10:** Groovy stays at 3.0.21. No Groovy upgrade.

### Error Handling
- **D-11:** Fail fast with clear error. If the bridge fails (JVM crash, serialization error, timeout), raise a `JavaBridgeError` immediately. No silent fallback to Python-side expression handling. Components that need Java MUST have the bridge working.
- **D-12:** Context/globalMap sync must happen at EVERY bridge call site -- not just `execute_java_row()`. This is fixed by design in the rewrite (every method that calls Java syncs afterward).

### Logging
- **D-13:** ASCII-only logging throughout. No emojis, unicode symbols, or non-ASCII characters in any log messages. Production target is RHEL Linux servers. Use `[OK]`, `[ERROR]`, `[WARN]` text markers.
- **D-14:** Replace all `print()` statements with proper `logging.getLogger(__name__)` calls. Both Python and Java sides.

### Test Strategy
- **D-15:** Unit tests for Python-side logic (schema mapping, type conversion, retry logic) with mocked Py4J gateway. No JVM required for these.
- **D-16:** Integration tests that start a real JVM and round-trip data through the bridge end-to-end. Marked with `@pytest.mark.java` so they can be skipped on machines without JVM.
- **D-17:** Round-trip test coverage for 12 Talend data types: String, Integer, Long, Float, Double, BigDecimal, Date, Timestamp, Boolean, Byte, Short, Character. Skip byte[], List, Object, Document -- not needed for production jobs.
- **D-18:** Subsequent component phases (tMap, tJava, tJavaRow, etc.) will add their own bridge integration tests. Phase 2 tests cover the bridge infrastructure itself, not component-specific bridge usage.
- **D-19:** Java 21 is available on dev machine (OpenJDK 21.0.10 via Homebrew). Java 11 is the minimum target for production.

### Claude's Discretion
- java_bridge_manager.py -- update vs rewrite based on needed changes
- Internal method design and data structures for the rewritten bridge
- Retry logic specifics (count, backoff, which failures trigger retry)
- BRDG-06 (compiled script synchronization) -- implementation approach determined during research
- BRDG-04 (JAR/library loading) -- robust classpath management approach determined during research

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Bridge Source Files (Primary Targets)
- `src/v1/java_bridge/bridge.py` -- Python bridge client (591 lines, full rewrite target)
- `src/v1/java_bridge/__init__.py` -- Bridge package init
- `src/v1/engine/java_bridge_manager.py` -- Bridge lifecycle manager (129 lines, update or rewrite)
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java` -- Java server (42KB, full rewrite target)
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/RowWrapper.java` -- Java row accessor (5KB, full rewrite target)
- `src/v1/java_bridge/java/pom.xml` -- Maven config (Py4J 0.10.9.7 -> 0.10.9.9, Arrow 15.0.2 stays)

### Cross-Cutting References
- `docs/v1/audit/CROSS_CUTTING_ISSUES.md` -- Audit issues including bridge-related bugs
- `.planning/REQUIREMENTS.md` -- BRDG-01 through BRDG-06 requirements for this phase
- `.planning/phases/01-infrastructure-bug-fixes-project-setup/01-CONTEXT.md` -- Phase 1 decisions (D-18 deferred bridge tests here)

### Schema Investigation (Research Phase)
- `src/converters/talend_to_v1/components/base.py` -- Converter base with `_parse_schema()` method
- `src/converters/talend_to_v1/type_mapping.py` -- Talend-to-Python type mapping
- `tests/talend_xml_samples/converted_jsons/` -- Sample converter output to audit schema format

### Standards
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` -- Phase 1 creates this; bridge must integrate with it
- `docs/v1/standards/ENGINE_TEST_PATTERN.md` -- Phase 1 creates this; bridge tests should follow it

</canonical_refs>

<code_context>
## Existing Code Insights

### What to Study (Not Reuse)
- Current `bridge.py` -- understand the full API surface (executeJavaRow, executeBatchOneTimeExpressions, executeTMapPreprocessing, executeTMapCompiled, compileTMapScript, executeCompiledTMapChunked, loadRoutine, validateLibraries). The rewrite must support all these operations with the same capabilities.
- Current `_build_arrow_schema()` -- understand why data-inference approach fails (all-null columns, mixed types, first-value-wins). The schema-driven replacement must handle all these edge cases.
- Current `_sync_from_java()` -- only called in `execute_java_row()`. The rewrite must sync after EVERY bridge call that could modify context/globalMap.
- Current `JavaBridge.java` -- understand the Java-side operations, Groovy compilation, Arrow IPC handling. Audit for dead code and unused methods.

### Established Patterns (Preserve)
- Py4J + Arrow IPC architecture -- the communication mechanism is correct, just needs reliability fixes
- One bridge instance per job via JavaBridgeManager -- isolation model is sound
- Dynamic port allocation via `socket.bind(('', 0))` -- prevents port conflicts
- Compile-once execute-many pattern for tMap (`compileTMapScript` + `executeCompiledTMap`) -- performance optimization to preserve

### Design Constraints for Rewrite
- Must integrate with Phase 1's rewritten BaseComponent (which calls bridge for `{{java}}` expression resolution)
- Must work with Phase 1's rewritten ContextManager and GlobalMap for sync operations
- Bridge context/globalMap dicts must stay in sync with engine-side GlobalMap and ContextManager
- Schema format standardization affects all downstream component phases -- get it right here

</code_context>

<specifics>
## Specific Ideas

- Schema format standardization is the highest-value decision in this phase -- research must be thorough about what converters produce and establish one format
- Hunt actively for unused code in JavaBridge.java during research -- don't just verify the 6 BRDG requirements
- The bridge serves tMap, tJava, tJavaRow, and routine loading -- all downstream phases depend on it being rock solid
- Consider what happens when the same bridge method is called many times in an iterate loop (re-entrance, state cleanup)

</specifics>

<deferred>
## Deferred Ideas

- Arrow version upgrade (15.0.2 -> newer) -- keep stable for now, upgrade in a future milestone if needed
- Groovy version upgrade -- no pressing need
- byte[], List, Object, Document type support in Arrow serialization -- not needed for current production jobs
- Database connection bridge support -- separate concern, Phase 11 (Oracle) may need bridge integration

</deferred>

---

*Phase: 02-java-bridge-reliability*
*Context gathered: 2026-04-14*
