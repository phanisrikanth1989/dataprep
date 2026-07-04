# Phase 9: tContextLoad & Routines - Context

**Gathered:** 2026-04-15 (auto mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite tContextLoad engine component with full Talend feature parity (DIE_ON_ERROR, LOAD_NEW_VARIABLE/NOT_LOAD_OLD_VARIABLE policies, type preservation, message suppression flags). Make Java and Python routines discoverable and callable from expressions. Phase 2 Java bridge and Phase 8 code components are prerequisites.

**Converter:** tContextLoad converter (107 lines, Green status) is production-ready -- 14/14 params extracted with 6 engine_gap needs_review entries. No converter changes needed.

</domain>

<decisions>
## Implementation Decisions

### tContextLoad Rewrite Approach
- **D-01:** Full rewrite from scratch. Not patching existing context_load.py (348 lines). The existing engine ignores 6 of 12 config keys, has NaN-to-string bugs (BUG-CL-002/003), and uses slow iterrows() instead of vectorized ops. Conform to ENGINE_COMPONENT_PATTERN.md blueprint per Phase 1 D-16.
- **D-02:** Add `@REGISTRY.register('ContextLoad', 'tContextLoad')` decorator per Phase 3 D-04 registry pattern.
- **D-03:** Flow-based input is the primary mode for explicit tContextLoad. The component receives a DataFrame with `key` and `value` columns from an upstream component (typically tFileInputDelimited). File-based loading (CONTEXTFILE, FORMAT, FIELDSEPARATOR, CSV_SEPARATOR, ERROR_IF_NOT_EXISTS) is a job-level implicit context load feature, separate from the tContextLoad component itself. The converter confirms this: implicit params are NOT in _java.xml but appear in .item exports.
- **D-04:** Use vectorized pandas operations instead of row-by-row iterrows(). For DataFrame input: `df.set_index('key')['value'].to_dict()` pattern for bulk context loading. Preserves performance for large context flows.

### Variable Policy Behavior (CTXL-02, CTXL-03)
- **D-05:** Implement LOAD_NEW_VARIABLE validation: compare incoming flow keys against known context variable names (from ContextManager). For keys NOT in existing context, emit a message at the configured severity level (ERROR/WARNING/INFO). Severity is a CLOSED_LIST, not a boolean -- it controls the log level of the validation message.
- **D-06:** Implement NOT_LOAD_OLD_VARIABLE validation: compare existing context variable names against incoming flow keys. For context variables NOT present in the incoming flow, emit a message at the configured severity level. This detects when the flow doesn't supply all expected context values.
- **D-07:** DISABLE_ERROR, DISABLE_WARNINGS, DISABLE_INFO flags suppress messages at their respective levels. DISABLE_WARNINGS defaults to true (warnings suppressed by default -- counter-intuitive but matches Talend). DISABLE_INFO defaults to true. DISABLE_ERROR defaults to false. Validation messages are only emitted if NOT disabled at their level.

### DIE_ON_ERROR Behavior (CTXL-01)
- **D-08:** When die_on_error=true and a validation produces an ERROR-level message (that is not disabled), raise ComponentExecutionError to stop the job. When die_on_error=false, log the error and continue processing. This matches the standard Talend die_on_error pattern used across components.

### Type Preservation (CTXL-04)
- **D-09:** On context variable reload, preserve type information. Use ContextManager.get_type() to retrieve the original type of existing variables. When the incoming flow includes a `type` column, use that. When not, check existing type from ContextManager. Only fall back to id_String when neither source provides type info. Convert values through ContextManager._convert_type() to maintain type fidelity.

### Java Routine Loading (ROUT-01)
- **D-10:** Java routines are already partially supported: JavaBridgeManager.start() calls bridge.load_routine() for each class in java_config.routines. JavaBridge.java loadRoutine() uses Class.forName() and addRoutinesToBinding() makes routines accessible in Groovy scripts both as direct names and via routines namespace (routines.ClassName.method()). This phase validates and hardens this existing path.
- **D-11:** Add JAR auto-discovery: scan a configured directory (e.g., java_config.routines_dir or java_config.routine_jars) for .jar files and add them to the JVM classpath at bridge startup BEFORE calling loadRoutine(). Talend expects routine.jar and dependencies on classpath. Current bridge only uses the main java-bridge-with-dependencies.jar.
- **D-12:** Routine class names in java_config.routines should be fully-qualified (e.g., "routines.system.api.TalendString"). Engine validates they load successfully or fails fast with clear error message listing missing routines.

### Python Routine Loading (ROUT-02)
- **D-13:** PythonRoutineManager already exists and works for basic loading from a directory. Extend to support: (a) subdirectory scanning for organized routine packages, (b) making routines available as a namespace in python_component/python_row_component execution context.
- **D-14:** Python routines accessible via `routines.RoutineName.method()` pattern in Python expressions, mirroring the Java routine namespace pattern.

### Routine Auto-Discovery (ROUT-03)
- **D-15:** Job configs declare required routines in java_config.routines (Java) and python_config.routines (Python). Engine loads these at startup, fails fast if any are missing. No runtime discovery -- all routines must be declared and loadable at job start.
- **D-16:** The converter should eventually populate routine lists from Talend job metadata (routine imports in .item files). For now, routines are manually listed in job configs. Converter enhancement is deferred.

### Claude's Discretion
- Internal structure of tContextLoad rewrite (method decomposition, validation ordering)
- Exact vectorized pandas implementation for bulk context loading
- PythonRoutineManager internal refactoring for subdirectory support
- Error message formatting for validation messages
- Test organization and fixture design

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### tContextLoad
- `docs/v1/audit/components/context/tContextLoad.md` -- Full audit report with Talend feature baseline, engine gaps, and behavioral notes
- `src/converters/talend_to_v1/components/context/context_load.py` -- Converter source (107 lines, Green) showing all 14 extracted params and config key names
- `src/v1/engine/components/context/context_load.py` -- Current engine implementation (348 lines) to be rewritten

### Context Manager
- `src/v1/engine/context_manager.py` -- ContextManager with set(), get(), get_type(), _convert_type(), resolve_string(), and SKIP_RESOLUTION_KEYS

### Java Bridge & Routines
- `src/v1/java_bridge/bridge.py` -- Python bridge client, includes load_routine() method at line 537
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java` -- Java bridge server with loadRoutine(), addRoutinesToBinding(), loadedRoutines map
- `src/v1/engine/java_bridge_manager.py` -- JavaBridgeManager with routine loading at startup (lines 98-110)

### Python Routines
- `src/v1/engine/python_routine_manager.py` -- PythonRoutineManager (180 lines) with _load_routines(), get_routine(), _to_class_name()
- `src/python_routines/swift_transformer.py` -- Existing Python routine example

### Engine Integration
- `src/v1/engine/engine.py` -- Engine initialization showing java_config.routines and python_config loading patterns (lines 42-60)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ContextManager.set(key, value, value_type)` -- Already handles type conversion, stores type info in context_types dict
- `ContextManager.get_type(key)` -- Retrieves stored type for a variable, returns None if not set
- `JavaBridge.load_routine(class_name)` -- Loads Java routine via Class.forName(), adds to Groovy binding
- `JavaBridgeManager` -- Already orchestrates routine loading from java_config.routines list
- `PythonRoutineManager` -- Working basic implementation, loads .py files from directory
- `BaseComponent` pattern -- Template method with _process(), _validate_config(), used by all Phase 5-7 rewrites

### Established Patterns
- Full rewrite from scratch per ENGINE_COMPONENT_PATTERN.md (Phases 5, 6, 7 all followed this)
- @REGISTRY.register() decorator for engine component registration (Phase 3 D-04)
- Vectorized pandas operations over iterrows() (established in Phase 6-7 rewrites)
- ASCII-only logging with [OK]/[ERROR]/[WARN] markers (Phase 2 D-13)
- ComponentExecutionError for die_on_error failures

### Integration Points
- Engine._init_components() sets component.python_routine_manager (line 120-121)
- Engine.__init__() reads java_config.routines and python_config from job config (lines 42-60)
- tContextLoad writes to ContextManager.context dict -- all downstream components read from it
- Java bridge addRoutinesToBinding() makes routines available as both direct names and routines.* namespace

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches. Follow the established rewrite pattern from Phases 5-7. Research Talaxie GitHub for tContextLoad_begin.javajet and tContextLoad_main.javajet to verify exact Talend validation logic before implementing.

</specifics>

<deferred>
## Deferred Ideas

- Converter enhancement to auto-populate routine lists from Talend .item file metadata -- future phase
- Implicit context load at job level (CONTEXTFILE, FORMAT, FIELDSEPARATOR params) -- separate from tContextLoad component, could be its own enhancement
- Java routine hot-reload during job execution -- not needed for Talend parity

</deferred>

---

*Phase: 09-tcontextload-routines*
*Context gathered: 2026-04-15*
