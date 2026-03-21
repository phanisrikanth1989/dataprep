# Audit Report: tJava / JavaComponent

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tJava` |
| **V1 Engine Class** | `JavaComponent` |
| **Engine File** | `src/v1/engine/components/transform/java_component.py` (110 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `_map_component_parameters()` (lines 332-346) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> NO dedicated `elif` branch for `tJava`; falls through to generic `parse_base_component()` + `_map_component_parameters()` |
| **Registry Aliases** | `JavaComponent`, `Java`, `tJava` (registered in `src/v1/engine/engine.py` lines 130-132) |
| **Category** | Transform / Custom Code |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/java_component.py` | Engine implementation (110 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 332-346) | Parameter mapping from Talend XML to v1 JSON -- `_map_component_parameters()` tJava branch |
| `src/converters/complex_converter/component_parser.py` (lines 420-472) | Generic `parse_base_component()` flow that tJava passes through |
| `src/converters/complex_converter/converter.py` (lines 310-382) | Dispatch -- NO dedicated `elif` for `tJava`; generic path used |
| `src/v1/engine/base_component.py` | Base class: `execute()`, `_resolve_java_expressions()`, `_update_stats()`, `_update_global_map()` |
| `src/v1/java_bridge/bridge.py` (lines 157-170) | `execute_one_time_expression()` -- the Java bridge method called by `JavaComponent._process()` |
| `src/v1/java_bridge/bridge.py` (lines 582-590) | `_sync_from_java()` -- syncs context and globalMap back from Java after execution |
| `src/v1/java_bridge/bridge.py` (lines 487-494) | `_convert_context_to_java()` and `_convert_globalmap_to_java()` -- serialization for Java bridge |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`JavaBridgeError`, `ConfigurationError`) |
| `src/v1/engine/engine.py` (lines 130-132) | Registry aliases for `JavaComponent`, `Java`, `tJava` |
| `src/v1/engine/components/transform/__init__.py` (line 10) | Package export: `from .java_component import JavaComponent` |
| `tests/v1/test_java_integration.py` | Integration test file -- tests `JavaRowComponent` but NOT `JavaComponent` directly |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 3 | 1 | 2 of 3 Talend params extracted (CODE, IMPORT); missing DIE_ON_ERROR; incomplete XML entity decoding; no dedicated converter dispatch |
| Engine Feature Parity | **Y** | 1 | 5 | 5 | 1 | globalMap stale-read consistency; no die_on_error support; no validate_config; double-sync issues; merge-update sync loses deletions; Py4J type conversion limitations |
| Code Quality | **Y** | 2 | 3 | 3 | 3 | Cross-cutting base class bugs; typo in code comment; bare re-raise without die_on_error handling; race condition on shared bridge |
| Performance & Memory | **R** | 1 | 0 | 1 | 1 | Groovy shell Metaspace leak (P0) in loops; minor sync optimization opportunities |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests for JavaComponent; zero dedicated integration tests |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tJava Does

`tJava` is a custom-code component in the Talend Custom Code family that enables users to embed personalized Java code directly within a Talend Job. It extends the functionality of a Talend Job by executing arbitrary Java commands. The code runs **exactly once** per subjob execution -- it is NOT per-row processing. This is the fundamental distinction from `tJavaRow` (per-row) and `tJavaFlex` (start-once/main-per-row/end-once hybrid).

**Source**: [tJava Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/java-custom-code/tjava-standard-properties), [tJava Overview (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/java-custom-code/tjava), [Usage of tJava, tJavaRow and tJavaFlex (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/java-custom-code/usage-of-tjava-tjavarow-and-tjavaflex), [Differences between tJava, tJavaRow and tJavaFlex (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/java-custom-code/differences-between-tjava-tjavarow-and-tjavaflex)

**Component family**: Custom Code (Java)
**Available in**: All Talend products (Standard). Also available in Spark Batch, Spark Streaming variants.
**Required JARs**: None specific beyond the Talend runtime. User-specified JARs can be loaded via `tLibraryLoad`.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Code | `CODE` | MEMO_JAVA | `"// code"` (stub) | **Primary parameter.** Multi-line Java code editor. The code entered here is injected into the generated Talend Java class and executes exactly once when the subjob runs. Has full access to `globalMap`, `context` variables, all imported routines, and the complete Talend Java API. Supports all standard Java syntax, control flow, exception handling, and object instantiation. The code is placed in the "start" section of the generated subjob code. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 2 | Import | `IMPORT` | MEMO_IMPORT | `""` (empty) | Java import statements required by the code in the CODE field. Each import statement on its own line (e.g., `import java.util.HashMap;`). These imports are added to the top of the generated Java class file. Without proper imports, the CODE field cannot reference external classes. |
| 3 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |

### 3.3 Undocumented but Present Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 4 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `true` | Controls whether a runtime exception in the CODE block kills the entire job or allows the subjob error trigger to fire. When `true` (default), any uncaught exception propagates and terminates the job. When `false`, the exception is caught, the `ERROR_MESSAGE` global variable is set, and the `SUBJOB_ERROR` / `COMPONENT_ERROR` triggers fire. This parameter is commonly found in the Talend XML for tJava nodes even though it is not always prominently displayed in the Studio UI for this component. |
| 5 | Label | `LABEL` | String | `""` | Text label for the component on the Talend Studio designer canvas. No runtime impact. |
| 6 | Unique Name | `UNIQUE_NAME` | String | `"tJava_1"` | Auto-generated unique identifier. Used internally by Talend for code generation and connection routing. |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. The primary connection type for tJava -- used to chain subjobs sequentially. Most common usage pattern: `tJava -> OnSubjobOk -> [next subjob start component]`. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. Only fires when `DIE_ON_ERROR=false` or when the error occurs after the tJava code completes (in a downstream component of the same subjob). |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific tJava component completes execution successfully. More granular than SUBJOB_OK. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific tJava component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. The target component only executes if the condition evaluates to true. |
| `ITERATE` | Output | Iterate | Enables iterative execution when combined with iteration components like `tFlowToIterate`. Rarely used with tJava since the component has no data flow output. |

**Important**: tJava does **NOT** have FLOW (Main) or REJECT data flow connections. It is a standalone code execution block, not a data transformation component. Data is passed between subjobs via `globalMap` or `context` variables, not via row-level data flows. This is the key structural difference from `tJavaRow` which has both input and output FLOW connections.

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_ERROR_MESSAGE` | String | On error (After scope) | The error message generated by the component when an error occurs. Only available when `DIE_ON_ERROR=false` and an error occurred. Used for downstream error handling and logging. |

**Note on NB_LINE**: Unlike data flow components, `tJava` does NOT set `NB_LINE`, `NB_LINE_OK`, or `NB_LINE_REJECT` because it does not process rows. There is no data throughput to count. However, the Talend runtime does track `EXECUTION_TIME` internally.

**Note on user-set globalMap**: The primary purpose of `tJava` is to SET globalMap variables via `globalMap.put("key", value)` in the CODE block. These variables are then available to all downstream components in the same job. Common patterns include:
- `globalMap.put("start_time", new java.util.Date());`
- `globalMap.put("record_count", ((Integer) globalMap.get("tFileInputDelimited_1_NB_LINE")).intValue());`
- `globalMap.put("output_filename", context.base_dir + "/output_" + TalendDate.formatDate("yyyyMMdd", new java.util.Date()) + ".csv");`

### 3.6 Context Variable Access

In Talend, tJava code has direct access to context variables via the `context` object:
- **Read**: `String dir = context.output_dir;` or `String dir = (String) context.get("output_dir");`
- **Write**: `context.output_dir = "/new/path";` or `context.put("output_dir", "/new/path");`

Context variables written in a tJava block are immediately available to all subsequent components in the same job execution.

### 3.7 Routine Access

tJava code can call any loaded Talend routine (user-defined or system):
- **System routines**: `TalendDate.formatDate("yyyy-MM-dd", new java.util.Date())`
- **User routines**: `MyRoutine.transformValue(someString)` (if loaded via `tLibraryLoad` or project routines)

### 3.8 Behavioral Notes

1. **One-time execution**: tJava executes exactly once when the subjob starts. It is the FIRST component to run in its subjob. The code is placed in the "start" section of the generated Talend Java class. This is fundamentally different from `tJavaRow` which executes per-row.

2. **No data flow**: tJava does not have input or output data flow connections. It cannot receive rows from upstream components or send rows to downstream components. Data exchange happens exclusively through `globalMap` and `context` variables.

3. **Typically used as subjob start**: tJava is most commonly used as the first (and only) component in a subjob. Downstream subjobs are connected via `OnSubjobOk` triggers. This pattern is used for initialization, cleanup, logging, and conditional logic.

4. **PreJob / MainJob / PostJob context**: In Talend job design, tJava components can appear in any of these contexts:
   - **PreJob**: Initialization before main data processing (e.g., setting context variables, creating directories, logging job start)
   - **Main**: Between data processing subjobs (e.g., intermediate calculations, conditional branching)
   - **PostJob**: Cleanup after main data processing (e.g., logging job completion, sending notifications, archiving files)

5. **XML entity encoding**: In Talend XML (.item files), the CODE and IMPORT fields use XML entity encoding for special characters:
   - Line breaks: `&#xD;&#xA;` (CRLF), `&#xA;` (LF), `&#xD;` (CR)
   - Ampersand: `&amp;`
   - Less-than: `&lt;`
   - Greater-than: `&gt;`
   - Double-quote: `&quot;`
   - Apostrophe: `&apos;`

   These must be decoded back to their original characters before the Java code can be executed.

6. **Error handling**: When `DIE_ON_ERROR=true` (default), any uncaught Java exception kills the entire job. When `DIE_ON_ERROR=false`, the exception is caught, `ERROR_MESSAGE` is set, and `COMPONENT_ERROR`/`SUBJOB_ERROR` triggers fire. This allows error recovery flows.

7. **Generated code placement**: Talend inserts the tJava code directly into the generated Java class. The code has access to all class-level variables including `globalMap`, `context`, `log`, and all routine classes. The imports from the IMPORT field are added at the top of the generated class file.

8. **tJava vs tJavaRow summary**:

   | Aspect | tJava | tJavaRow |
   |--------|-------|----------|
   | Execution | Once per subjob | Once per input row |
   | Data flow | No input/output FLOW | Has input and output FLOW |
   | Primary use | Initialization, setup, globalMap manipulation | Data transformation, field-level computation |
   | Code placement | Start section of subjob | Main section (inside row iteration loop) |
   | Row access | No `input_row` / `output_row` | Has `input_row` and `output_row` |
   | Typical connections | OnSubjobOk, OnSubjobError | FLOW (Main), Reject |

9. **tJava vs tJavaFlex**: tJavaFlex provides three code sections (start, main, end) combining tJava's one-time execution with tJavaRow's per-row processing. tJavaFlex is the most flexible but also the most complex. tJava is preferred for pure one-time execution scenarios.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter handles `tJava` through the **generic `_map_component_parameters()` approach** in `component_parser.py` (lines 332-346). There is a dedicated `elif component_type == 'tJava'` branch within `_map_component_parameters()` that extracts CODE and IMPORT. However, there is **NO** dedicated `elif component_type == 'tJava'` branch in `converter.py:_parse_component()` (lines 310-382) -- tJava falls through to the generic `parse_base_component()` path, which eventually calls `_map_component_parameters()`.

**Converter flow**:
1. `converter.py:_parse_component()` receives a tJava XML node
2. No `elif component_type == 'tJava'` match in the dispatch chain (lines 310-380)
3. Falls through to the end of the `elif` chain, returning `component` with whatever `parse_base_component()` populated
4. `parse_base_component()` (lines 420-508) iterates all `elementParameter` nodes, builds `config_raw` dict
5. At line 462, tJava is explicitly listed in the skip list for Java expression marking: `if component_name not in ['tMap', 'tJavaRow', 'tJava']` -- this correctly prevents CODE/IMPORT from being treated as Java expressions
6. At line 472, calls `_map_component_parameters('tJava', config_raw)`
7. The `_map_component_parameters()` method has a dedicated `elif component_type == 'tJava'` branch at line 332

**The tJava-specific parameter mapping code (lines 332-346)**:
```python
# tJava mapping (similar to tJavaRow but for one-time execution)
elif component_type == 'tJava':
    # Decode the Java code (XML entities)
    code = config_raw.get('CODE', '')
    # Replace XML line break entities with actual newlines
    code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')

    # Decode imports
    imports = config_raw.get('IMPORT', '')
    imports = imports.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')

    return {
        'java_code': code,
        'imports': imports
    }
```

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `CODE` | **Yes** | `java_code` | 335 | Extracted from `config_raw`. XML line break entities (`&#xD;&#xA;`, `&#xA;`, `&#xD;`) decoded to `\n`. |
| 2 | `IMPORT` | **Yes** | `imports` | 340 | Same XML line break entity decoding as CODE. |
| 3 | `DIE_ON_ERROR` | **No** | -- | -- | **Not extracted. tJava has no die_on_error support in v1 config.** The engine raises unconditionally on error. |
| 4 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used). |
| 5 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact). |
| 6 | `UNIQUE_NAME` | **Yes** (implicit) | `component_id` | base_component | Extracted generically by `parse_base_component()` and used as the component's unique identifier. |

**Summary**: 2 of 3 runtime-relevant parameters extracted (67%). The critical missing parameter is `DIE_ON_ERROR`.

### 4.2 Schema Extraction

Schema extraction is handled generically by `parse_base_component()` (lines 474-508 of `component_parser.py`). However, tJava typically has **no schema** because it has no FLOW connections. In Talend XML, a tJava node rarely has `<metadata>` elements.

| Schema Aspect | Relevant? | Notes |
|---------------|-----------|-------|
| Output schema (FLOW) | **No** | tJava has no FLOW output -- no schema needed. |
| Reject schema | **No** | tJava has no REJECT output. |
| Input schema | **No** | tJava has no data flow input. |

The generic schema extraction code will harmlessly produce empty schema lists for tJava nodes. This is correct behavior.

### 4.3 Expression Handling

**CODE and IMPORT special handling** (component_parser.py lines 447-448, 462):
- Line 448: The generic parameter loop explicitly skips `CODE` and `IMPORT` fields for context variable wrapping: `elif name not in ['CODE', 'IMPORT'] and isinstance(value, str) and 'context.' in value`. This is **correct** -- CODE and IMPORT contain raw Java code where `context.` references are Java syntax, not v1 context variable references.
- Line 462: Java expression marking is skipped for `tJava`: `if component_name not in ['tMap', 'tJavaRow', 'tJava']`. This is **correct** -- the `{{java}}` marker system is for simple Java expressions in config values, not for multi-line Java code blocks.

**XML entity decoding** (lines 337, 341):
- Only line break entities are decoded: `&#xD;&#xA;` -> `\n`, `&#xA;` -> `\n`, `&#xD;` -> `\n`
- Other XML entities are **NOT decoded**: `&amp;`, `&lt;`, `&gt;`, `&quot;`, `&apos;`
- This is a significant gap because Java code commonly uses `&&` (logical AND) which is stored as `&amp;&amp;` in XML, and comparison operators `<`/`>` which are stored as `&lt;`/`&gt;`

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-JC-001 | **P1** | **Incomplete XML entity decoding**: Only line break entities (`&#xD;`, `&#xA;`) are decoded in CODE and IMPORT fields. Standard XML entities `&amp;` (ampersand), `&lt;` (less-than), `&gt;` (greater-than), `&quot;` (double-quote), and `&apos;` (apostrophe) are NOT decoded. Java code using `&&` (logical AND), `<`/`>` (comparisons), or string literals with quotes will be corrupted. For example, `if (count > 0 && flag)` is stored as `if (count &gt; 0 &amp;&amp; flag)` in XML, and the current converter would pass the entity-encoded version to the Java bridge, causing compilation errors. This affects both tJava and tJavaRow identically. **Note**: If the XML parser (e.g., `xml.etree.ElementTree`) handles entity decoding before the values reach `_map_component_parameters()`, this may not be an issue in practice -- but the converter's own `.replace()` chain suggests manual entity handling is expected. |
| CONV-JC-002 | **P1** | **`DIE_ON_ERROR` not extracted**: The converter does not extract the `DIE_ON_ERROR` parameter for tJava. In Talend, this controls whether a runtime exception kills the entire job or allows error triggers to fire. Without this, the v1 engine always propagates exceptions (equivalent to `DIE_ON_ERROR=true`), which prevents error recovery flows from working for tJava components with `DIE_ON_ERROR=false`. |
| CONV-JC-003 | **P2** | **No dedicated converter dispatch branch**: Unlike `tJavaRow` which has a dedicated `elif component_type == 'tJavaRow': component = self.component_parser.parse_java_row(node, component)` branch in `converter.py` line 375, `tJava` has no corresponding branch. It falls through to the generic `parse_base_component()` path. While the generic path does call `_map_component_parameters('tJava', ...)` which handles CODE/IMPORT extraction, the lack of a dedicated dispatch means tJava cannot benefit from specialized parsing logic (e.g., extracting connection types, validating CODE is non-empty). |
| CONV-JC-004 | **P2** | **`imports` config key not used by engine**: The converter extracts IMPORT into `config['imports']`, but the engine's `JavaComponent._process()` (line 47) only reads `config.get('java_code', '')`. The `imports` value is never accessed by the engine. In Talend, imports are added to the generated Java class file's import section. Without processing imports, code that references external classes (e.g., `import java.util.HashMap;`) will fail at execution time because the classes are not imported in the Java bridge execution context. |
| CONV-JC-005 | **P2** | **Identical code for tJava and tJavaRow parameter mapping**: The `_map_component_parameters()` branches for tJavaRow (lines 316-330) and tJava (lines 332-346) contain identical code -- same XML entity decoding, same config keys (`java_code`, `imports`). This violates DRY and means bug fixes must be applied to both branches. Should be refactored into a shared helper method. |
| CONV-JC-006 | **P3** | **No validation that CODE is non-empty**: The converter extracts `CODE` with a default of `''` (empty string). An empty CODE produces an empty `java_code` config value that the engine will reject at runtime with `ValueError`. The converter should warn or error during conversion if CODE is empty. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Execute Java code once | **Yes** | High | `_process()` line 77 | Calls `java_bridge.execute_one_time_expression(java_code)`. Core functionality works. |
| 2 | Access context variables in CODE | **Yes** | Medium | `_process()` lines 64-70 | Context synced from ContextManager to bridge before execution. Sync-back after execution (lines 84-87). |
| 3 | Access globalMap in CODE | **Partial** | Low | `_process()` lines 72-74 | GlobalMap synced to bridge's Python dict before execution, but `execute_one_time_expression()` does not push Python-side values to Java (no `putAll` call). globalMap IS bound on Java side via `this.globalMap` instance field (JavaBridge.java line 186), but `globalMap.get()` returns stale/missing values for keys set only on the Python side (e.g., upstream component stats). |
| 4 | Set globalMap variables in CODE | **Partial** | Medium | `_process()` lines 90-93 | Post-execution sync reads from `java_bridge.global_map` dict. `globalMap.put()` in Java code works because globalMap is bound via the instance field. Values put on the Java side sync back correctly. The gap is in reading Python-side keys (see #3). |
| 5 | Set context variables in CODE | **Yes** | Medium | `_process()` lines 84-87 | Post-execution sync reads `java_bridge.context` and writes back to ContextManager. However, relies on `_sync_from_java()` which calls Java-side `getContext()`. |
| 6 | IMPORT / external classes | **No** | N/A | -- | `config['imports']` is never read by `_process()`. External class imports are not added to the Java execution context. |
| 7 | Die on error | **No** | N/A | -- | No `die_on_error` config read. All exceptions propagate unconditionally (equivalent to `DIE_ON_ERROR=true` always). No error suppression or ERROR_MESSAGE globalMap variable. |
| 8 | ERROR_MESSAGE global variable | **No** | N/A | -- | Not set on error. Exception propagates, but `{id}_ERROR_MESSAGE` is never stored in globalMap. |
| 9 | SUBJOB_OK trigger | **Yes** | High | Via engine orchestration | Engine handles trigger connections after successful component execution. Not specific to JavaComponent. |
| 10 | SUBJOB_ERROR trigger | **Partial** | Low | Via engine orchestration | Engine handles error triggers, but since JavaComponent always propagates exceptions (no die_on_error=false support), the error may kill the job before triggers fire. |
| 11 | COMPONENT_OK trigger | **Yes** | High | Via engine orchestration | Same as SUBJOB_OK -- handled by engine infrastructure. |
| 12 | COMPONENT_ERROR trigger | **Partial** | Low | Via engine orchestration | Same limitation as SUBJOB_ERROR -- depends on die_on_error support. |
| 13 | RUN_IF conditional trigger | **Yes** | High | Via engine orchestration | Handled by engine infrastructure. Not specific to JavaComponent. |
| 14 | Pass-through of input data | **Yes** | High | `_process()` lines 101-105 | If input_data is provided (unusual for tJava), it is passed through unchanged. Returns empty DataFrame if no input. |
| 15 | Statistics tracking | **Yes** | Medium | `_process()` line 102 | Stats updated with input row count if input_data present. Returns 0/0/0 for no-input case (normal tJava). |
| 16 | tStatCatcher Statistics | **No** | N/A | -- | Not implemented. Low priority. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-JC-001 | **P0** | **globalMap stale-read data consistency**: `JavaComponent._process()` syncs globalMap to the bridge's Python dict (lines 72-74: `java_bridge.set_global_map(key, value)`), but the bridge method `execute_one_time_expression()` (bridge.py line 167-170) only passes `self._convert_context_to_java()` to the Java side. It does NOT call `self._convert_globalmap_to_java()`. **Note**: globalMap IS bound on the Java side via `this.globalMap` instance field (JavaBridge.java line 186). The Java-side `globalMap.put()` works and syncs back correctly. The bug is that `execute_one_time_expression` does not push Python-side globalMap values to Java (no `putAll` call), so `globalMap.get()` returns stale or missing values for keys set only on the Python side. This is the most critical functional gap because the primary purpose of tJava is to manipulate globalMap variables. **Contrast with `execute_java_row()`** (bridge.py lines 140-147) which correctly passes both context AND globalMap to Java via explicit `putAll`. |
| ENG-JC-002 | **P1** | **No die_on_error support**: `_process()` has a single `except Exception as e` block (lines 107-109) that logs and re-raises unconditionally. There is no `die_on_error` config check. In Talend, when `DIE_ON_ERROR=false`, the exception should be caught, `{id}_ERROR_MESSAGE` should be set in globalMap, and execution should continue (allowing COMPONENT_ERROR and SUBJOB_ERROR triggers to fire). Without this, tJava components with `DIE_ON_ERROR=false` behave as if `DIE_ON_ERROR=true`, potentially killing jobs that should recover from tJava errors. |
| ENG-JC-003 | **P1** | **IMPORT field ignored**: The `imports` config value is never read by `_process()`. Line 47 reads `java_code = self.config.get('java_code', '')` but there is no corresponding `imports = self.config.get('imports', '')`. In Talend, imports are placed at the top of the generated Java class, making external classes available. Without import support, tJava code using `HashMap`, `SimpleDateFormat`, or any non-`java.lang` class without fully qualified names will fail with "symbol not found" errors. The workaround is to use fully qualified class names in the CODE field (e.g., `java.util.HashMap map = new java.util.HashMap();`), but this is not Talend-compatible behavior. |
| ENG-JC-004 | **P1** | **Double sync of context is redundant**: `_process()` performs two syncs: (1) Lines 64-70 sync Python ContextManager to bridge's Python dict and then set on Java bridge, (2) Line 81 calls `java_bridge._sync_from_java()` which reads Java context into bridge's Python dict, (3) Lines 84-87 read bridge's Python dict back to ContextManager. However, `_sync_from_java()` is a **private method** (prefixed with `_`) of `JavaBridge` -- calling it from `JavaComponent` violates encapsulation. Additionally, the sync at line 81 may be premature for `execute_one_time_expression()` since that method does NOT call `_sync_from_java()` internally (unlike `execute_java_row()` which does at line 150). The sync behavior depends on whether the Java-side `executeOneTimeExpression` updates the context/globalMap Java objects in-place. |
| ENG-JC-005 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap on error**: When the Java code throws an exception (caught at line 107), the error is logged and re-raised, but `{id}_ERROR_MESSAGE` is never stored in globalMap. In Talend, this variable is always set when an error occurs, allowing downstream error handling flows to access the error details. |
| ENG-JC-006 | **P2** | **No validate_config method**: Unlike many other v1 components, `JavaComponent` does not implement a `_validate_config()` method. The only validation is the empty `java_code` check at line 49. Missing validations include: verifying `context_manager` has a Java bridge, verifying `java_code` is valid (basic syntax check), checking for `imports` presence. |
| ENG-JC-007 | **P2** | **Stats not meaningful for tJava**: When input_data is None (normal tJava case), `_update_stats()` is never called in `_process()`. The stats remain at initialization values (0, 0, 0). However, the base class `execute()` still calls `_update_global_map()` which writes these zero stats to globalMap as `{id}_NB_LINE=0`, `{id}_NB_LINE_OK=0`, `{id}_NB_LINE_REJECT=0`. In Talend, tJava does not set NB_LINE variables at all. The v1 engine sets them to 0, which is harmless but unnecessary overhead and potentially confusing in debugging. |
| ENG-JC-008 | **P2** | **Verbose logging exposes context and globalMap contents**: Lines 67, 70, 87, and 93 log the full contents of context and globalMap dictionaries at INFO level. This can expose sensitive data (passwords, connection strings, API keys) stored in context variables. In production environments, context variables frequently contain credentials. These should be logged at DEBUG level at most, with sensitive keys masked. |
| ENG-JC-009 | **P3** | **Typo in code comment**: Line 79 has a typo: `"Sync context and globalMap back from Java to Pyython"` -- "Pyython" should be "Python". Minor cosmetic issue. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | **No** (not applicable) | Yes (always 0) | Via `_update_global_map()` in base class | Unnecessary for tJava -- Talend does not set NB_LINE for this component type |
| `{id}_NB_LINE_OK` | **No** (not applicable) | Yes (always 0) | Same mechanism | Same as NB_LINE |
| `{id}_NB_LINE_REJECT` | **No** (not applicable) | Yes (always 0) | Same mechanism | Same as NB_LINE |
| `{id}_ERROR_MESSAGE` | **Yes** (on error) | **No** | -- | Not implemented. Critical gap for error handling flows. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class `execute()` | V1-specific, not in Talend standard |
| User-defined (via `globalMap.put()`) | **Yes** | **Partial** | `_sync_from_java()` -> `global_map.put()` | `globalMap.put()` works on Java side (instance field is bound). Values sync back to Python. However, `globalMap.get()` for Python-only keys returns stale/missing values (see ENG-JC-001). |

### 5.4 Bridge Method Analysis

The `execute_one_time_expression()` method in `bridge.py` (lines 157-170) is the core execution path for tJava:

```python
def execute_one_time_expression(self, expression: str) -> Any:
    return self.java_bridge.executeOneTimeExpression(
        expression,
        self._convert_context_to_java()
    )
```

**Critical observation**: This method passes only `self._convert_context_to_java()` to the Java side. Compare with other bridge methods:

| Bridge Method | Passes Context? | Passes GlobalMap? | Used By |
|---------------|-----------------|-------------------|---------|
| `execute_one_time_expression()` | Yes | **No** (not pushed via putAll*) | `JavaComponent` (tJava) |
| `execute_java_row()` | Yes | Yes | `JavaRowComponent` (tJavaRow) |
| `execute_batch_one_time_expressions()` | Yes | Yes | `BaseComponent._resolve_java_expressions()` |
| `execute_tmap_preprocessing()` | Yes | Yes | `Map` component |
| `execute_tmap_compiled()` | Yes | Yes | `Map` component |

The `execute_one_time_expression()` method is the ONLY bridge execution method that does not push Python-side globalMap values to Java. Note that globalMap IS bound on the Java side via `this.globalMap` instance field (JavaBridge.java line 186), so `globalMap.put()` in Java works. The bug is specifically that Python-side values are not pushed via `putAll`, so `globalMap.get()` returns stale/missing values for keys set only on the Python side. This method was likely designed for simple property expressions (where globalMap access is uncommon) and was then repurposed for tJava code blocks (where globalMap read access is a primary use case).

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-JC-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just JavaComponent, since `_update_global_map()` is called after every component execution (via `execute()` line 218). The crash occurs in the statistics logging line, so component execution completes but the post-execution stats update fails, potentially causing the entire component to appear as failed even though the Java code executed successfully. |
| BUG-JC-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` variable is not in the method signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one positional argument. **CROSS-CUTTING**: Affects all code using `global_map.get()`. For JavaComponent specifically, the post-execution globalMap sync at line 92 uses `global_map.put()` (which works), but any downstream component calling `global_map.get()` to read tJava-set variables will crash. |
| BUG-JC-003 | **P1** | `src/v1/java_bridge/bridge.py:167-170` | **`execute_one_time_expression()` does not push Python-side globalMap to Java**: As documented in ENG-JC-001, the bridge method only passes context to Java. The `JavaComponent._process()` syncs globalMap to `java_bridge.global_map` (lines 72-74), but this Python dict is never pushed to the Java-side `globalMap` instance field by `execute_one_time_expression()` (no `putAll` call). globalMap IS bound on the Java side via `this.globalMap` instance field (JavaBridge.java line 186), so `globalMap.put()` in Java works and syncs back. However, `globalMap.get()` returns stale/missing values for keys set only on the Python side (e.g., upstream component stats like `tFileInputDelimited_1_NB_LINE`). |
| BUG-JC-004 | **P1** | `src/v1/engine/components/transform/java_component.py:81` | **Calling private method `_sync_from_java()` from outside the class**: Line 81 calls `java_bridge._sync_from_java()` which is a private method of `JavaBridge`. This violates encapsulation and creates a fragile coupling. If `JavaBridge._sync_from_java()` is refactored or renamed, `JavaComponent` will break silently. Additionally, calling `_sync_from_java()` after `execute_one_time_expression()` may not work correctly because `executeOneTimeExpression` on the Java side may not update the context/globalMap Java objects in the same way that `executeJavaRow` does. The `_sync_from_java()` method was designed to be called after row-based execution, not one-time expression execution. |
| BUG-JC-005 | **P1** | `src/v1/engine/components/transform/java_component.py:49-51` | **`ValueError` raised instead of `ConfigurationError`**: When `java_code` is empty, the component raises `ValueError`. All other v1 components use the custom `ConfigurationError` exception for configuration issues. This inconsistency means error handling code that catches `ConfigurationError` will miss this case. The component should use `ConfigurationError` from `src/v1/engine/exceptions.py`. |
| BUG-JC-006 | **P1** | `src/v1/engine/components/transform/java_component.py:53-57` | **`RuntimeError` raised instead of `JavaBridgeError`**: When Java bridge is not available, the component raises `RuntimeError`. The custom `JavaBridgeError` exception exists in `exceptions.py` (line 38) specifically for Java bridge communication errors. Using `RuntimeError` bypasses the structured error hierarchy. |
| BUG-JC-007 | **P3** | `src/v1/engine/components/transform/java_component.py:104-105` | **Returns empty DataFrame for no-input case (correct for v1 contract)**: When `input_data is None` (normal tJava case), `_process()` returns `{'main': pd.DataFrame()}`. This is **correct behavior** for the v1 engine contract -- the engine expects result dicts to contain a `'main'` key, and other no-data components (like `tSetGlobalVar`) follow the same pattern. While a `{'main': None}` return would be more semantically precise for a component that produces no data, changing this would risk breaking engine assumptions. Downgraded from P2 -- no action needed. |
| BUG-JC-008 | **P0** | `src/v1/java_bridge/JavaBridge.java:198` | **Groovy shell Metaspace memory leak**: `JavaBridge.java` line 198 creates a new `GroovyShell` per `executeOneTimeExpression` call. Each `GroovyShell` instantiation creates a new classloader and dynamically generates a class. For tJava components executed inside loops (e.g., via `tLoop`/`tForeach`), this causes unbounded Metaspace growth because classloaders and their generated classes are never garbage-collected while the parent classloader is alive. Over hundreds or thousands of iterations, this will crash the JVM with `OutOfMemoryError: Metaspace`. The fix is to reuse a single `GroovyShell` instance (or at minimum, a single classloader) across calls, clearing script caches between invocations. |
| BUG-JC-009 | **P1** | `src/v1/java_bridge/bridge.py:582-590` | **`_sync_from_java()` does merge-update, not replace**: The `_sync_from_java()` method (bridge.py lines 582-590) uses `dict.update()` to merge Java-side context and globalMap back into the Python-side dicts. This is a merge (add/overwrite) operation, NOT a replace. Consequently, Java-side key deletions (e.g., `context.remove("key")`, `globalMap.remove("key")`) are invisible to Python -- the old values persist in the Python-side dicts. This is a behavioral divergence from Talend, where mutations including deletions are immediately visible to all code in the same JVM. Any tJava code that removes keys from context or globalMap will appear to succeed on the Java side but the deletions will be silently lost on sync-back. |
| BUG-JC-010 | **P2** | `src/v1/java_bridge/bridge.py` (Py4J layer) | **Py4J type conversion limitations for globalMap values**: When Java-side code puts non-primitive types into globalMap (e.g., `globalMap.put("ts", new java.util.Date())`), the Py4J sync-back does not convert them to native Python types. Java `Date` becomes a Py4J proxy object (not `datetime.datetime`), Java `ArrayList` becomes a `JavaList` wrapper (not `list`), and Java `BigDecimal` becomes a Py4J proxy (not `decimal.Decimal`). Downstream Python components that expect native Python types for globalMap values will break with `AttributeError` or type-check failures. This affects any tJava code that stores complex Java objects in globalMap or context. |
| BUG-JC-011 | **P2** | `src/v1/java_bridge/bridge.py` (shared instance) | **Race condition with shared JavaBridge**: If two `JavaComponent` instances execute concurrently (e.g., parallel subjobs via `tParallelize`), they overwrite each other's context and globalMap on the shared `JavaBridge` instance. The pre-execution sync (lines 64-74 of `java_component.py`) writes to `java_bridge.context` and `java_bridge.global_map` which are plain Python dicts with no synchronization. The Java-side `context.putAll()` is also not synchronized. This race condition can cause one component to execute with another component's context/globalMap values, leading to silent data corruption. The fix requires either per-component bridge instances or a locking mechanism around the sync-execute-sync lifecycle. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-JC-001 | **P2** | **Config key `java_code` vs Talend parameter `CODE`**: The converter maps `CODE` to `java_code`. This is consistent with the `tJavaRow` mapping (same key name). However, it differs from other components that use uppercase Talend parameter names directly (e.g., `DIE_ON_ERROR` in tJoin). The v1 engine uses snake_case config keys consistently for Java components, which is a reasonable convention. |
| NAME-JC-002 | **P3** | **Class name `JavaComponent` does not include "t" prefix**: The class is named `JavaComponent`, not `TJavaComponent`. This is consistent with all other v1 engine classes (e.g., `FileInputDelimited` not `TFileInputDelimited`). The Talend prefix `t` is handled via registry aliases. No action needed. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-JC-001 | **P2** | "Custom exceptions from `exceptions.py`" (METHODOLOGY.md) | `ValueError` (line 49-50) and `RuntimeError` (line 54-57) used instead of `ConfigurationError` and `JavaBridgeError`. See BUG-JC-005 and BUG-JC-006. |
| STD-JC-002 | **P2** | "No `print()` statements" (STANDARDS.md) | No `print()` statements in `java_component.py` itself. However, `bridge.py` lines 38, 45, 69, 94, 117 contain `print()` statements for startup diagnostics. These are not gated behind a debug flag. |
| STD-JC-003 | **P3** | "Private method access" (general Python convention) | `_process()` calls `java_bridge._sync_from_java()` (line 81), accessing a private method of another class. Should use a public API. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-JC-001 | **P2** | **Verbose INFO-level logging of context and globalMap contents**: Lines 67, 70, 87, and 93 log `ctx_all`, `java_bridge.context`, and `java_bridge.global_map` dictionaries at INFO level. In production, context variables often contain sensitive data (database passwords, API keys, file paths with credentials). These should be DEBUG level with sensitive key masking. Example: `logger.info(f"Component {self.id}: Syncing context to bridge: {ctx_all}")` exposes all context variable values. |
| DBG-JC-002 | **P3** | **Typo in comment**: Line 79: `"Sync context and globalMap back from Java to Pyython"` -- "Pyython" should be "Python". |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-JC-001 | **P2** | **Context and globalMap contents logged at INFO level**: As noted in DBG-JC-001, sensitive data in context variables (passwords, credentials, API keys) is logged in plaintext at INFO level. This creates a security risk in production environments where logs are stored, shipped to aggregation services, or viewed by operations teams who should not have access to credentials. |
| SEC-JC-002 | **P3** | **Arbitrary Java code execution**: By design, tJava executes arbitrary Java code. This is inherent to the component's purpose and cannot be mitigated without removing functionality. However, there is no sandboxing or code review mechanism in the v1 engine. If config comes from untrusted sources (unlikely for Talend-converted jobs, but noted for defense-in-depth), this is a code injection vector. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `Component {self.id}:` prefix pattern -- correct (though inconsistent with `[{self.id}]` pattern used by other components) |
| Level usage | **Issue**: INFO used for verbose debug data (context contents). Should be DEBUG for data, INFO for milestones only. |
| Start/complete logging | `_process()` logs start (line 62: "Executing one-time Java code") and success (line 95: "Java code executed successfully") -- correct |
| Sensitive data | **Issue**: Context and globalMap contents logged at INFO level (lines 67, 70, 87, 93). Security concern. |
| No print statements | No `print()` calls in `java_component.py` -- correct. (Bridge.py has prints, but that is a separate file.) |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | **Incorrect**: Uses `ValueError` and `RuntimeError` instead of `ConfigurationError` and `JavaBridgeError`. |
| Exception chaining | **Not used**: Line 109 uses `raise` (bare re-raise) which preserves the original traceback. This is acceptable for re-raising, but does not add context like `raise JavaBridgeError(...) from e` would. |
| `die_on_error` handling | **Missing**: No die_on_error support. All exceptions propagate unconditionally. |
| No bare `except` | Line 107: `except Exception as e` -- correct (not bare `except`). |
| Error messages | Line 108: `f"Component {self.id}: Java execution failed: {e}"` -- includes component ID and error. Good. |
| Graceful degradation | **Missing**: No graceful degradation on error. Always re-raises. Should return empty DataFrame when die_on_error=false. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_process()` has parameter and return type hints: `(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]` -- correct |
| Class-level imports | `from typing import Any, Dict, Optional` -- correct for the types used |
| Missing types | No type hint for `java_bridge` attribute in the class body (inherited from base class as `Any` type). Acceptable. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-JC-001 | **P2** | **Redundant context sync round-trip**: `_process()` performs a full context sync to Java before execution (lines 64-70), then a full sync back from Java after execution (lines 81-87). For tJava components that do not modify context variables, this is wasted overhead. However, since tJava's primary purpose includes context manipulation, the sync is necessary in the general case. The overhead is proportional to the number of context variables, not the data volume. For jobs with hundreds of context variables, this could add measurable latency. Consider lazy sync or dirty-flag tracking. |
| PERF-JC-002 | **P3** | **GlobalMap sync iterates all entries**: Lines 72-74 iterate all globalMap entries and sync each to the Java bridge's Python dict. For large globalMaps (hundreds of entries from prior component executions), this creates O(n) overhead on every tJava execution. Since Python-side values are not pushed to Java via putAll (BUG-JC-003), this sync to the bridge's Python dict is wasted work for the Java execution context. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Component footprint | Very lightweight -- only stores config dict and references to context_manager/global_map. No large data structures. |
| Java bridge memory | Java bridge is a shared resource across all Java-enabled components. Memory overhead is in the JVM process, not in Python. |
| Pass-through data | If input_data is provided (unusual for tJava), it is passed through by reference (no copy). Memory efficient. |
| Empty DataFrame return | Returns `pd.DataFrame()` for no-input case. Minimal memory overhead. |

### 7.2 Execution Performance Characteristics

| Aspect | Assessment |
|--------|------------|
| JVM startup | Not a JavaComponent concern -- JVM is started once by `JavaBridgeManager` at engine initialization. |
| Py4J serialization | Context variables serialized via Py4J auto_convert. Overhead depends on context size and types. Simple types (str, int, float) are fast. Complex types (nested dicts, large strings) can be slow. |
| Java code compilation | `executeOneTimeExpression` compiles and executes the Java code each time. For tJava components executed once per job, this is not a concern. For tJava in loops (via tLoop/tForeach), repeated compilation could be expensive. |
| Network overhead | Py4J uses TCP (default port 25333). Local-only communication, but still subject to socket overhead. Negligible for one-time execution. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests for `JavaComponent` | **No** | -- | Zero test files found for `JavaComponent` v1 engine component |
| V1 engine integration tests for `JavaComponent` | **No** | -- | `tests/v1/test_java_integration.py` exists but tests `JavaRowComponent`, not `JavaComponent` |
| V1 converter unit tests for tJava parsing | **No** | -- | No tests verify tJava parameter extraction in `_map_component_parameters()` |

**Key finding**: The v1 engine has ZERO tests for `JavaComponent`. All 110 lines of v1 engine code are completely unverified. The existing integration test file (`tests/v1/test_java_integration.py`) tests `JavaRowComponent` (tJavaRow) exclusively -- there is no test for `JavaComponent` (tJava) anywhere in the test suite.

### 8.2 Existing Related Tests

The file `tests/v1/test_java_integration.py` (269 lines) contains three tests:

| # | Test | Tests tJava? | Description |
|---|------|-------------|-------------|
| 1 | `test_basic_java_row()` | No | Tests `JavaRowComponent` with simple field transformations |
| 2 | `test_library_load_and_routine()` | No | Tests `tLibraryLoad` (currently commented out / deprecated) |
| 3 | `test_context_sync()` | No | Tests context variable sync with `JavaRowComponent`, not `JavaComponent` |

None of these tests exercise the `JavaComponent` class or the `execute_one_time_expression()` bridge method.

### 8.3 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic Java code execution | P0 | Create `JavaComponent` with simple Java code (e.g., `String s = "hello";`), verify execution completes without error and returns empty DataFrame |
| 2 | Context variable read in Java | P0 | Set context variables, execute tJava code that reads them (e.g., `String dir = (String) context.get("output_dir");`), verify no error |
| 3 | Context variable write in Java | P0 | Execute tJava code that sets a context variable (e.g., `context.put("result", "success");`), verify the value is synced back to Python ContextManager |
| 4 | GlobalMap read in Java | P0 | Set globalMap variables, execute tJava code that reads them (e.g., `globalMap.get("key")`). **This test will currently FAIL due to BUG-JC-003.** |
| 5 | GlobalMap write in Java | P0 | Execute tJava code that sets globalMap variables (e.g., `globalMap.put("start_time", new java.util.Date());`), verify values are synced back to Python GlobalMap. **This test will currently FAIL due to BUG-JC-003.** |
| 6 | Empty java_code raises error | P0 | Create JavaComponent with empty `java_code`, verify it raises ValueError (or ConfigurationError after fix) |
| 7 | No Java bridge raises error | P0 | Create JavaComponent without Java bridge enabled, verify it raises RuntimeError (or JavaBridgeError after fix) |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Die on error = true (exception propagates) | P1 | Execute Java code that throws an exception, verify exception propagates to caller |
| 9 | Die on error = false (exception caught) | P1 | Execute Java code that throws an exception with die_on_error=false, verify empty DataFrame returned and ERROR_MESSAGE set. **Requires ENG-JC-002 fix first.** |
| 10 | Import external class | P1 | Execute Java code using `HashMap` with `import java.util.HashMap;` in imports, verify execution succeeds. **Requires CONV-JC-004 fix first.** |
| 11 | Multi-line Java code | P1 | Execute complex multi-line Java code with loops, conditionals, try/catch, verify execution completes |
| 12 | Pass-through input data | P1 | Provide input DataFrame, verify it is returned unchanged in result['main'] with correct stats |
| 13 | Context and globalMap sync round-trip | P1 | Set context vars, execute tJava that modifies them, verify changes visible to subsequent component |
| 14 | XML entity encoded code | P1 | Provide Java code with XML entities (`&amp;&amp;`, `&lt;`, `&gt;`), verify correct execution. Tests entity decoding pipeline. |
| 15 | Sequential tJava execution | P1 | Execute two tJava components in sequence connected via OnSubjobOk, verify globalMap variables set by first are readable by second |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 16 | Large context sync | P2 | Set 500+ context variables, execute tJava, verify all values accessible and sync completes in reasonable time |
| 17 | Java code with Unicode | P2 | Execute Java code containing Unicode string literals (e.g., CJK characters), verify correct handling |
| 18 | Concurrent tJava execution | P2 | Two JavaComponent instances executing simultaneously on separate Java bridges, verify no cross-contamination |
| 19 | globalMap integration with stats | P2 | Verify that after tJava execution, globalMap contains `{id}_NB_LINE=0` etc. (base class behavior) |
| 20 | Java runtime exception types | P2 | Verify that different Java exception types (NullPointerException, ClassCastException, etc.) are properly propagated with meaningful error messages |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-JC-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-JC-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| ENG-JC-001 | Engine | **globalMap stale-read data consistency**: `execute_one_time_expression()` does not push Python-side globalMap values to Java (no `putAll` call). globalMap IS bound on Java side via `this.globalMap` instance field (JavaBridge.java line 186), so `globalMap.put()` works and syncs back. But `globalMap.get()` returns stale/missing values for keys set only on the Python side. This breaks the primary use case of tJava reading upstream component stats. |
| BUG-JC-008 | Bug | Groovy shell Metaspace memory leak. `JavaBridge.java` line 198 creates a new `GroovyShell` per `executeOneTimeExpression` call. Each creates a new classloader + dynamically generated class. For tJava in loops, this causes unbounded Metaspace growth that can crash the JVM with `OutOfMemoryError: Metaspace`. |
| TEST-JC-001 | Testing | Zero v1 unit tests for JavaComponent. All 110 lines of v1 engine code are completely unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-JC-001 | Converter | Incomplete XML entity decoding: only line breaks decoded; `&amp;`, `&lt;`, `&gt;`, `&quot;`, `&apos;` not decoded. Java code using `&&`, `<`, `>` will be corrupted. |
| CONV-JC-002 | Converter | `DIE_ON_ERROR` not extracted from Talend XML. Engine always propagates exceptions (equivalent to DIE_ON_ERROR=true). |
| ENG-JC-002 | Engine | No die_on_error support in engine. All exceptions propagate unconditionally. No graceful degradation. |
| ENG-JC-003 | Engine | IMPORT field ignored by engine. External class imports not added to Java execution context. Code using non-java.lang classes will fail. |
| ENG-JC-004 | Engine | Double sync of context uses private method `_sync_from_java()` from outside the class. Fragile coupling. |
| ENG-JC-005 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap on error. Error details not available to downstream components. |
| BUG-JC-003 | Bug | `execute_one_time_expression()` does not push Python-side globalMap to Java (no `putAll` call). globalMap IS bound on Java side, so `put()` works, but `get()` returns stale/missing values for Python-only keys. |
| BUG-JC-009 | Bug | `_sync_from_java()` does merge-update, not replace (bridge.py lines 582-590). Java-side key deletions (`context.remove()`, `globalMap.remove()`) are invisible to Python -- old values persist. Behavioral divergence from Talend. |
| BUG-JC-004 | Bug | Calling private method `java_bridge._sync_from_java()` from `JavaComponent` violates encapsulation. |
| BUG-JC-005 | Bug | `ValueError` raised instead of `ConfigurationError` for empty java_code. Inconsistent with exception hierarchy. |
| BUG-JC-006 | Bug | `RuntimeError` raised instead of `JavaBridgeError` for missing Java bridge. Inconsistent with exception hierarchy. |
| TEST-JC-002 | Testing | No integration test for JavaComponent in a multi-step v1 job (e.g., tJava -> OnSubjobOk -> tFileInputDelimited). |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-JC-003 | Converter | No dedicated converter dispatch branch for tJava in `converter.py`. Falls through to generic path. tJavaRow has a dedicated branch. |
| CONV-JC-004 | Converter | `imports` config key extracted but never used by engine. Dead config value. |
| CONV-JC-005 | Converter | Identical code for tJava and tJavaRow parameter mapping in `_map_component_parameters()`. DRY violation. |
| ENG-JC-006 | Engine | No `_validate_config()` method. Only validation is empty java_code check. |
| ENG-JC-007 | Engine | Stats (NB_LINE=0, etc.) written to globalMap unnecessarily. Talend tJava does not set NB_LINE. |
| ENG-JC-008 | Engine | Verbose INFO-level logging exposes context and globalMap contents. Security concern. |
| BUG-JC-010 | Bug | Py4J type conversion limitations for globalMap values. Java `Date` becomes Py4J proxy (not `datetime`), `ArrayList` becomes `JavaList` (not `list`). Downstream Python components expecting native types will break. |
| BUG-JC-011 | Bug | Race condition with shared JavaBridge. Concurrent JavaComponents overwrite each other's context/globalMap on the shared bridge instance. Java-side `context.putAll()` is not synchronized. |
| NAME-JC-001 | Naming | Config key `java_code` vs Talend parameter `CODE`. Consistent with tJavaRow but differs from other components. |
| STD-JC-001 | Standards | Uses `ValueError`/`RuntimeError` instead of custom exceptions from `exceptions.py`. |
| STD-JC-002 | Standards | `bridge.py` contains `print()` statements (lines 38, 45, 69, 94, 117) for startup diagnostics. |
| SEC-JC-001 | Security | Context and globalMap contents logged at INFO level. Exposes sensitive data. |
| PERF-JC-001 | Performance | Redundant context sync round-trip. Full sync even when context not modified. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-JC-006 | Converter | No validation that CODE is non-empty during conversion. Empty CODE only caught at engine runtime. |
| BUG-JC-007 | Bug | Returns empty DataFrame for no-input case. Correct for v1 engine contract (engine expects `'main'` key in result dict). No action needed. |
| ENG-JC-009 | Engine | Typo in comment: "Pyython" should be "Python" (line 79). |
| NAME-JC-002 | Naming | Class name `JavaComponent` lacks "t" prefix. Consistent with v1 naming convention. No action needed. |
| STD-JC-003 | Standards | Private method `_sync_from_java()` accessed from outside `JavaBridge` class. |
| SEC-JC-002 | Security | Arbitrary Java code execution by design. No sandboxing. Inherent to component purpose. |
| DBG-JC-002 | Debug | Typo in comment on line 79: "Pyython" instead of "Python". |
| PERF-JC-002 | Performance | GlobalMap sync iterates all entries but Python-side values are not pushed to Java via putAll (BUG-JC-003). The pre-execution sync to bridge's Python dict is wasted work for the Java execution. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 5 | 3 bugs (2 cross-cutting + 1 Metaspace leak), 1 engine, 1 testing |
| P1 | 12 | 2 converter, 4 engine, 5 bugs, 1 testing |
| P2 | 13 | 3 converter, 3 engine, 2 bugs, 1 naming, 2 standards, 1 security, 1 performance |
| P3 | 8 | 1 converter, 1 engine, 1 bug, 1 naming, 1 standards, 1 security, 1 debug, 1 performance |
| **Total** | **38** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `execute_one_time_expression()` to push Python-side globalMap to Java** (BUG-JC-003 / ENG-JC-001): Modify `bridge.py` line 167-170 to pass both context and globalMap to the Java side. The globalMap IS already bound on the Java side via `this.globalMap` instance field (JavaBridge.java line 186), so `globalMap.put()` works. The fix is to push Python-side values via `putAll` so that `globalMap.get()` can read keys set on the Python side. The fix should mirror how `execute_batch_one_time_expressions()` (line 185-189) passes both. Specifically, change:
   ```python
   def execute_one_time_expression(self, expression: str) -> Any:
       return self.java_bridge.executeOneTimeExpression(
           expression,
           self._convert_context_to_java()
       )
   ```
   to:
   ```python
   def execute_one_time_expression(self, expression: str) -> Any:
       return self.java_bridge.executeOneTimeExpression(
           expression,
           self._convert_context_to_java(),
           self._convert_globalmap_to_java()
       )
   ```
   **Note**: This requires a corresponding change to the Java-side `executeOneTimeExpression` method to accept the globalMap parameter and call `this.globalMap.putAll(globalMap)` before executing the expression. **Impact**: Fixes tJava's ability to read Python-side globalMap values (e.g., upstream component stats). **Risk**: Medium -- requires Java-side changes.

1a. **Fix Groovy shell Metaspace leak** (BUG-JC-008): Modify `JavaBridge.java` to reuse a single `GroovyShell` instance across `executeOneTimeExpression` calls instead of creating a new one per invocation. Clear the script cache between calls. Alternatively, use a `GroovyShell` pool with a shared parent classloader. **Impact**: Prevents JVM `OutOfMemoryError: Metaspace` crash for tJava in loops. **Risk**: Low -- the `GroovyShell` can be stored as an instance field and reused.

2. **Fix `_update_global_map()` bug** (BUG-JC-001): Change `value` to `stat_value` on `base_component.py` line 304. This is a one-character fix. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low.

3. **Fix `GlobalMap.get()` bug** (BUG-JC-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low.

4. **Create unit test suite** (TEST-JC-001): Implement at minimum the 7 P0 test cases listed in Section 8.3. These cover: basic execution, context read/write, globalMap read/write, empty code error, and missing bridge error. Without these, no v1 engine behavior for JavaComponent is verified. Tests 4 and 5 (globalMap) should be written as expected-failure tests until BUG-JC-003 is fixed, then converted to passing tests.

### Short-Term (Hardening)

5. **Add complete XML entity decoding** (CONV-JC-001): Add full XML entity decoding to the tJava (and tJavaRow) parameter mapping in `_map_component_parameters()`. After the line break replacements, add:
   ```python
   import html
   code = html.unescape(code)
   imports = html.unescape(imports)
   ```
   Python's `html.unescape()` handles all standard XML/HTML entities (`&amp;`, `&lt;`, `&gt;`, `&quot;`, `&apos;`, and numeric entities). **Alternatively**, verify that the XML parser (ElementTree) already decodes these entities before the values reach `_map_component_parameters()`. If so, the manual line break replacement may be the only needed decoding, and the line break entities may be a special case that ElementTree does not decode. **Impact**: Fixes Java code containing `&&`, `<`, `>` operators. **Risk**: Low.

6. **Extract and implement `DIE_ON_ERROR`** (CONV-JC-002 / ENG-JC-002): Add `die_on_error` extraction to the tJava parameter mapping:
   ```python
   return {
       'java_code': code,
       'imports': imports,
       'die_on_error': config_raw.get('DIE_ON_ERROR', True)
   }
   ```
   Then modify `_process()` to check `die_on_error` in the except block:
   ```python
   except Exception as e:
       die_on_error = self.config.get('die_on_error', True)
       logger.error(f"Component {self.id}: Java execution failed: {e}")
       if self.global_map:
           self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
       if die_on_error:
           raise
       else:
           return {'main': pd.DataFrame()}
   ```
   **Impact**: Enables error recovery flows for tJava. **Risk**: Low.

7. **Implement IMPORT processing** (ENG-JC-003 / CONV-JC-004): Modify `_process()` to read the `imports` config value and prepend it to the Java code before execution. The simplest approach:
   ```python
   imports = self.config.get('imports', '')
   if imports:
       java_code = imports + '\n' + java_code
   ```
   However, this may not work if `executeOneTimeExpression` wraps the code in a method body (imports must be at class level). The proper fix depends on how the Java-side `executeOneTimeExpression` processes the expression. May require adding a separate `imports` parameter to the Java bridge method. **Impact**: Enables tJava code using external classes. **Risk**: Medium -- depends on Java bridge implementation.

8. **Fix exception types** (BUG-JC-005 / BUG-JC-006): Replace `ValueError` with `ConfigurationError` and `RuntimeError` with `JavaBridgeError`:
   ```python
   from ...exceptions import ConfigurationError, JavaBridgeError

   if not java_code:
       raise ConfigurationError(f"Component {self.id}: 'java_code' is required")

   if not self.context_manager or not self.context_manager.is_java_enabled():
       raise JavaBridgeError(f"Component {self.id}: Java execution is not available.")
   ```
   **Impact**: Consistent with v1 exception hierarchy. **Risk**: Very low.

9. **Set `{id}_ERROR_MESSAGE` in globalMap on error** (ENG-JC-005): In the except block of `_process()`, add:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
   ```
   **Impact**: Enables downstream error handling to access error details. **Risk**: Very low.

10. **Replace private method call with public API** (BUG-JC-004): Replace `java_bridge._sync_from_java()` with a public method. Options:
    - Add a public `sync_from_java()` method to `JavaBridge` that delegates to `_sync_from_java()`
    - Or have `execute_one_time_expression()` call `_sync_from_java()` internally (like `execute_java_row()` does at line 150)
    The second option is cleaner -- the sync should happen inside the bridge method, not in the component. **Impact**: Cleaner encapsulation. **Risk**: Low.

### Long-Term (Optimization)

11. **Add dedicated converter dispatch for tJava** (CONV-JC-003): Add `elif component_type == 'tJava': component = self.component_parser.parse_java(node, component)` to the dispatch chain in `converter.py`. Create a dedicated `parse_java()` method in `component_parser.py` that handles CODE, IMPORT, DIE_ON_ERROR, and validates CODE is non-empty.

12. **Refactor duplicate tJava/tJavaRow mapping code** (CONV-JC-005): Extract the shared CODE/IMPORT extraction logic into a helper method:
    ```python
    def _extract_java_code_and_imports(self, config_raw):
        code = config_raw.get('CODE', '')
        code = html.unescape(code)
        imports = config_raw.get('IMPORT', '')
        imports = html.unescape(imports)
        return code, imports
    ```

13. **Reduce logging verbosity** (DBG-JC-001 / SEC-JC-001 / ENG-JC-008): Change INFO-level context/globalMap logging to DEBUG level. Add sensitive key masking for known credential patterns.

14. **Add `_validate_config()` method** (ENG-JC-006): Implement configuration validation:
    ```python
    def _validate_config(self) -> List[str]:
        errors = []
        if not self.config.get('java_code'):
            errors.append("'java_code' is required")
        return errors
    ```

15. **Create integration test** (TEST-JC-002): Build an end-to-end test exercising `tJava -> OnSubjobOk -> tFileInputDelimited` in the v1 engine, verifying context and globalMap propagation across the subjob boundary.

16. **Fix typo** (DBG-JC-002 / ENG-JC-009): Change "Pyython" to "Python" on line 79 of `java_component.py`.

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 332-346
# tJava mapping (similar to tJavaRow but for one-time execution)
elif component_type == 'tJava':
    # Decode the Java code (XML entities)
    code = config_raw.get('CODE', '')
    # Replace XML line break entities with actual newlines
    code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')

    # Decode imports
    imports = config_raw.get('IMPORT', '')
    imports = imports.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')

    return {
        'java_code': code,
        'imports': imports
    }
```

**Notes on this code**:
- Line 335: `config_raw.get('CODE', '')` extracts the CODE parameter from the XML-parsed dict. If CODE is missing, defaults to empty string.
- Lines 337: Three chained `.replace()` calls decode XML line break entities. Order matters: `&#xD;&#xA;` (CRLF) must be replaced before individual `&#xD;` (CR) and `&#xA;` (LF) to avoid double-replacement.
- Lines 340-341: Identical decoding for IMPORT field.
- Lines 343-346: Returns a dict with only `java_code` and `imports`. No `die_on_error`, no validation.
- **Missing entities**: `&amp;` (ampersand), `&lt;` (less-than), `&gt;` (greater-than), `&quot;` (double-quote), `&apos;` (apostrophe) are NOT decoded. This corrupts Java code using `&&`, `<`, `>` operators.
- **Identical to tJavaRow**: Lines 316-330 (tJavaRow) contain character-for-character identical code. DRY violation.

### Comparison with tJavaRow converter mapping (lines 316-330)

```python
# component_parser.py lines 316-330
# tJavaRow mapping
elif component_type == 'tJavaRow':
    # Decode the Java code (XML entities)
    code = config_raw.get('CODE', '')
    # Replace XML line break entities with actual newlines
    code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')

    # Decode imports
    imports = config_raw.get('IMPORT', '')
    imports = imports.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')

    return {
        'java_code': code,
        'imports': imports
    }
```

The two branches are **identical** except for the component type check and the comment text.

---

## Appendix B: Engine Class Structure

```
JavaComponent (BaseComponent)
    Inherited Constants:
        MEMORY_THRESHOLD_MB = 3072

    Methods:
        _process(input_data) -> Dict[str, Any]    # Main entry point (110 lines total in file)
            - Validates java_code is non-empty
            - Validates Java bridge is available
            - Syncs context Python -> Java bridge
            - Syncs globalMap Python -> Java bridge (but bridge doesn't push via putAll to Java)
            - Calls java_bridge.execute_one_time_expression(java_code)
            - Calls java_bridge._sync_from_java() (private method)
            - Syncs context Java bridge -> Python ContextManager
            - Syncs globalMap Java bridge -> Python GlobalMap
            - Passes through input_data or returns empty DataFrame

    Inherited Methods (from BaseComponent):
        execute(input_data) -> Dict[str, Any]      # Main lifecycle: resolve expressions -> resolve context -> determine mode -> _process() -> update stats
        _resolve_java_expressions() -> None         # Resolves {{java}} markers in config (not used by tJava since CODE/IMPORT skip marking)
        _update_stats(rows_read, rows_ok, rows_reject) -> None
        _update_global_map() -> None                # BUG: references undefined variable 'value'
        validate_schema(df, schema) -> DataFrame    # Not called by JavaComponent
        _determine_execution_mode() -> ExecutionMode
        _execute_batch(input_data) -> Dict[str, Any]
        _execute_streaming(input_data) -> Dict[str, Any]
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `CODE` | `java_code` | **Mapped** | -- |
| `IMPORT` | `imports` | **Mapped** (but not used by engine) | P1 (engine must use it) |
| `DIE_ON_ERROR` | -- | **Not Mapped** | P1 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (low priority) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `UNIQUE_NAME` | `component_id` (implicit) | **Mapped** (generic) | -- |

---

## Appendix D: Bridge Method Comparison

### execute_one_time_expression (used by tJava)

```python
# bridge.py lines 157-170
def execute_one_time_expression(self, expression: str) -> Any:
    """Execute a one-time Java expression (e.g., for component properties)"""
    return self.java_bridge.executeOneTimeExpression(
        expression,
        self._convert_context_to_java()
        # NOTE: Python-side globalMap NOT pushed via putAll (Java-side instance field IS bound)
    )
```

### execute_batch_one_time_expressions (used by BaseComponent._resolve_java_expressions)

```python
# bridge.py lines 172-189
def execute_batch_one_time_expressions(self, expressions: Dict[str, str]) -> Dict[str, Any]:
    """Execute multiple one-time Java expressions in batch (efficient)"""
    return self.java_bridge.executeBatchOneTimeExpressionsWithGlobalMap(
        expressions,
        self._convert_context_to_java(),
        self.global_map  # globalMap IS passed
    )
```

### execute_java_row (used by tJavaRow)

```python
# bridge.py lines 119-155
def execute_java_row(self, df: pd.DataFrame, java_code: str, output_schema: Dict[str, str]) -> pd.DataFrame:
    """Execute tJavaRow-style code block on DataFrame"""
    # ... Arrow serialization ...
    result_bytes = self.java_bridge.executeJavaRow(
        arrow_bytes,
        java_code,
        self._convert_schema_to_java(output_schema),
        self._convert_context_to_java(),
        self._convert_globalmap_to_java()  # globalMap IS passed
    )
    self._sync_from_java()  # Sync called internally
    # ... Arrow deserialization ...
```

**Key observation**: `execute_one_time_expression` is the ONLY bridge execution method that:
1. Does NOT push Python-side globalMap values to Java (no `putAll` call) -- note that globalMap IS bound on Java side via `this.globalMap` instance field, so `put()` works but `get()` for Python-only keys returns stale/missing values
2. Does NOT call `_sync_from_java()` internally

Both omissions are bugs for tJava's use case, where reading upstream component stats from globalMap is a primary use case.

---

## Appendix E: Detailed Code Analysis

### `JavaComponent._process()` (Lines 43-109)

The entire engine implementation of tJava is contained in a single method. Here is the complete execution flow:

**Phase 1: Validation (Lines 46-57)**
1. Read `java_code` from config (line 47)
2. If empty, raise ValueError (line 49-50) -- **should be ConfigurationError**
3. Check Java bridge availability via context_manager (line 53)
4. If not available, raise RuntimeError (line 54-57) -- **should be JavaBridgeError**
5. Get java_bridge reference from context_manager (line 59)

**Phase 2: Pre-execution Sync (Lines 61-74)**
6. Log start message at INFO level (line 62)
7. If context_manager exists, sync all context variables to java_bridge (lines 64-70):
   - Get all context vars: `ctx_all = self.context_manager.get_all()` (line 66)
   - Log full contents at INFO level (line 67) -- **security concern**
   - Iterate and set each on bridge: `java_bridge.set_context(key, value)` (lines 68-69)
   - Log bridge context after sync at INFO level (line 70) -- **security concern**
8. If global_map exists, sync all globalMap entries to java_bridge (lines 72-74):
   - Iterate all entries: `self.global_map.get_all().items()` (line 73)
   - Set each on bridge: `java_bridge.set_global_map(key, value)` (line 74)
   - **Note**: This sets on the bridge's Python-side dict, but `execute_one_time_expression()` does not push these values to Java via putAll (Java-side instance field IS bound, so put() works but get() for Python-only keys returns stale/missing values)

**Phase 3: Java Execution (Lines 76-81)**
9. Call `java_bridge.execute_one_time_expression(java_code)` (line 77)
   - Bridge calls `self.java_bridge.executeOneTimeExpression(expression, self._convert_context_to_java())`
   - Only context is pushed to Java; Python-side globalMap values are NOT pushed via putAll (globalMap IS bound on Java side via instance field)
   - Returns result value (or None)
10. Call `java_bridge._sync_from_java()` (line 81) -- **private method access**
    - Reads Java-side context and globalMap into bridge's Python dicts
    - Calls `self.java_bridge.getContext()` and `self.java_bridge.getGlobalMap()` on the Java side

**Phase 4: Post-execution Sync (Lines 83-93)**
11. If context_manager exists, sync context back from bridge to ContextManager (lines 84-87):
    - Iterate `java_bridge.context.items()` (line 85)
    - Set each on ContextManager: `self.context_manager.set(key, value)` (line 86)
    - Log synced values at INFO level (line 87) -- **security concern**
12. If global_map exists, sync globalMap back from bridge to GlobalMap (lines 90-93):
    - Iterate `java_bridge.global_map.items()` (line 91)
    - Set each on GlobalMap: `self.global_map.put(key, value)` (line 92)
    - Log synced values at INFO level (line 93) -- **security concern**

**Phase 5: Return (Lines 95-109)**
13. Log success at INFO level (line 95)
14. If result is not None, log at DEBUG level (line 97-98)
15. If input_data provided, update stats and return it (lines 101-103)
16. Else return empty DataFrame (lines 104-105)
17. On exception: log error, re-raise (lines 107-109) -- **no die_on_error check**

### Sync Architecture Diagram

```
Python Side                          Java Side (Py4J)
============                          ================

ContextManager                        JavaBridge.context (Java Map)
    |                                       ^
    | (1) get_all()                         |
    v                                       |
JavaComponent._process()                    |
    |                                       |
    | (2) set_context()                     |
    v                                       |
JavaBridge.context (Python dict)            |
    |                                       |
    | (3) _convert_context_to_java()        |
    +-------------------------------------->|
    |                                       |
    |   execute_one_time_expression()       |
    |                                       |
    |<-------(4) _sync_from_java()---------|
    |         (getContext())                 |
    v                                       |
JavaBridge.context (Python dict, updated)   |
    |                                       |
    | (5) context_manager.set()             |
    v                                       |
ContextManager (updated)                    |

GlobalMap                             JavaBridge.globalMap (Java Map)
    |                                       ^
    | (1) get_all()                         |
    v                                       |
JavaComponent._process()                    |
    |                                       |
    | (2) set_global_map()                  |
    v                                       |
JavaBridge.global_map (Python dict)         |
    |                                       |
    | (3) NOT PUSHED via putAll!     ------>X  <-- BUG: Python-side values not pushed to Java
    |                                       |
    |<-------(4) _sync_from_java()---------|
    |         (getGlobalMap())              |
    v                                       |
JavaBridge.global_map (Python dict)         |
    |   (merge-update: Java-side additions  |
    |    overwrite, but deletions lost)     |
    | (5) global_map.put()                  |
    v                                       |
GlobalMap (Java-side puts visible, but      |
          Python-only keys were stale on    |
          Java side; deletions lost)        |
```

**Critical issue in the diagram**: Step (3) for globalMap shows the data path is broken for the Python-to-Java direction. The Python-side globalMap is populated but never pushed to Java via `putAll`. Note that globalMap IS bound on the Java side via `this.globalMap` instance field (JavaBridge.java line 186), so `globalMap.put()` in Java code works. The bug is that `globalMap.get()` returns stale/missing values for keys set only on the Python side. After execution, `_sync_from_java()` reads the Java-side globalMap and does a merge-update (not replace), so Java-side deletions are invisible to Python (BUG-JC-009).

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty CODE parameter

| Aspect | Detail |
|--------|--------|
| **Talend** | Generates a no-op Java class. No error. The component executes with empty code body. |
| **V1** | Raises `ValueError("Component {id}: 'java_code' is required")` at line 49-50. |
| **Verdict** | BEHAVIORAL DIFFERENCE -- V1 is stricter than Talend. An empty tJava in Talend is a valid (if useless) component. In v1, it crashes. For production use, this is arguably better behavior (fail-fast on misconfiguration). |

### Edge Case 2: Java code with XML entity characters

| Aspect | Detail |
|--------|--------|
| **Talend** | XML parser decodes all entities before code reaches the Java compiler. `&amp;&amp;` becomes `&&`, `&lt;` becomes `<`, etc. |
| **V1** | Only line break entities decoded. `&amp;&amp;` remains as `&amp;&amp;` in the java_code string. If the XML parser (ElementTree) does not decode these, the Java code will contain literal `&amp;` strings which cause compilation errors. |
| **Verdict** | POTENTIAL GAP -- depends on whether ElementTree decodes entities before `_map_component_parameters()` receives the values. If ElementTree handles it, this is a non-issue. If not, Java code with comparisons and logical operators will fail. |

### Edge Case 3: tJava that sets globalMap variables

| Aspect | Detail |
|--------|--------|
| **Talend** | `globalMap.put("key", value)` works directly. Value is immediately available to all subsequent components. |
| **V1** | `globalMap.put("key", value)` in the Java code **works** because globalMap IS bound on the Java side via `this.globalMap` instance field (JavaBridge.java line 186). Values put on the Java side sync back to Python via `_sync_from_java()`. However, `globalMap.get("key")` for keys set only on the Python side (e.g., upstream component stats like `tFileInputDelimited_1_NB_LINE`) returns stale/missing values because Python-side values are not pushed to Java. |
| **Verdict** | **PARTIALLY BROKEN** -- `put()` works, but `get()` for Python-only keys fails. See ENG-JC-001. |

### Edge Case 4: tJava that reads context variables

| Aspect | Detail |
|--------|--------|
| **Talend** | `context.output_dir` or `context.get("output_dir")` reads the value directly. |
| **V1** | Context is synced to Java before execution (lines 64-70). If `_convert_context_to_java()` correctly serializes all types, this should work. However, complex types (Date, BigDecimal, custom objects) may not serialize correctly via Py4J. |
| **Verdict** | MOSTLY CORRECT for simple types (String, Integer, Double). Potential issues with complex types. |

### Edge Case 5: tJava that modifies context variables

| Aspect | Detail |
|--------|--------|
| **Talend** | `context.output_dir = "/new/path"` modifies the context immediately. All subsequent components see the new value. |
| **V1** | Context is synced back after execution (lines 84-87). If `_sync_from_java()` correctly reads the modified context, and the ContextManager is updated, subsequent components should see the new value. This is the path that HAS been designed to work (unlike globalMap). |
| **Verdict** | LIKELY CORRECT -- but untested (no unit tests exist). |

### Edge Case 6: tJava with DIE_ON_ERROR=false and runtime exception

| Aspect | Detail |
|--------|--------|
| **Talend** | Exception caught. `{id}_ERROR_MESSAGE` set. COMPONENT_ERROR/SUBJOB_ERROR triggers fire. Job continues. |
| **V1** | Exception propagates unconditionally (line 109: `raise`). No ERROR_MESSAGE set. Job likely terminates. |
| **Verdict** | **BROKEN** -- die_on_error=false not supported. See ENG-JC-002. |

### Edge Case 7: tJava with IMPORT statements

| Aspect | Detail |
|--------|--------|
| **Talend** | `import java.util.HashMap;` in IMPORT field makes `HashMap` class available in CODE. |
| **V1** | `imports` config value is never read by the engine. Java code must use fully qualified names (`java.util.HashMap`) or execution fails. |
| **Verdict** | PARTIAL -- workaround exists (fully qualified names) but not Talend-compatible. See ENG-JC-003. |

### Edge Case 8: tJava receiving input data (unusual)

| Aspect | Detail |
|--------|--------|
| **Talend** | tJava has no FLOW input connections. This cannot happen in standard Talend. |
| **V1** | If input_data is provided (via engine routing), it is passed through unchanged with stats updated. Defensive handling for an impossible Talend scenario. |
| **Verdict** | CORRECT defensive coding. Not a Talend scenario. |

### Edge Case 9: tJava in a tLoop/tForeach iteration

| Aspect | Detail |
|--------|--------|
| **Talend** | The tJava code executes once per iteration of the loop. Each iteration has fresh access to globalMap/context which may have been updated by loop variables. |
| **V1** | Each iteration creates a new `execute()` call. Context and globalMap are synced before each execution. `globalMap.put()` works on Java side, but `globalMap.get()` for Python-only keys (like loop variables set by tLoop) returns stale/missing values (BUG-JC-003). Additionally, each iteration creates a new `GroovyShell` with a new classloader and dynamically generated class (BUG-JC-008), causing unbounded Metaspace growth that will crash the JVM after hundreds or thousands of iterations. |
| **Verdict** | **BROKEN** for loops -- Metaspace leak (BUG-JC-008) will crash JVM. Also partially broken for globalMap read access (BUG-JC-003). Context access likely works. |

### Edge Case 10: tJava code with multi-line string literals

| Aspect | Detail |
|--------|--------|
| **Talend** | Java multi-line strings (Java 13+) or concatenated strings work normally. XML entity encoding handles embedded line breaks. |
| **V1** | Line break entities are decoded (`&#xD;&#xA;` -> `\n`). Multi-line Java code should work. However, if the Java code itself contains the literal string `&#xA;` (not as an XML entity but as a Java string value), the replacement would incorrectly decode it. This is extremely unlikely in practice. |
| **Verdict** | CORRECT for practical use cases. Theoretical edge case with literal entity strings. |

### Edge Case 11: globalMap sync overwrites Python-side data

| Aspect | Detail |
|--------|--------|
| **Talend** | globalMap is a single shared map. No sync issues. |
| **V1** | After tJava execution, `_sync_from_java()` reads the Java-side globalMap and writes it to the bridge's Python dict (line 589-590: `self.global_map.update(java_globalmap)`). Then lines 90-93 write bridge's dict entries to the Python GlobalMap. If the Java-side globalMap was never populated with Python data (due to BUG-JC-003), the sync-back may overwrite Python-side entries with empty/stale Java data. The `update()` method only adds/overwrites keys that exist in the source, so keys NOT in the Java-side map are preserved. However, any key that existed in both Python and Java (but was not updated on Java side) will be overwritten with the stale Java value. |
| **Verdict** | **POTENTIAL DATA LOSS** -- Python-side globalMap entries may be overwritten with stale Java-side values. This is a secondary consequence of BUG-JC-003. |

### Edge Case 12: Concurrent tJava components

| Aspect | Detail |
|--------|--------|
| **Talend** | Jobs are single-threaded by default. tJava components in the same job execute sequentially. tParallelize can run subjobs concurrently, but each has its own globalMap namespace. |
| **V1** | The Java bridge is a shared resource. Concurrent access to `java_bridge.context` and `java_bridge.global_map` dicts (which are plain Python dicts) is not thread-safe. If v1 engine supports parallel execution, race conditions can corrupt context and globalMap. See BUG-JC-011 for details. |
| **Verdict** | **BUG** if engine supports parallel execution (BUG-JC-011). Not an issue for sequential job execution. |

---

## Appendix G: Comparison with tJavaRow Implementation

Since `tJava` and `tJavaRow` are closely related, comparing their v1 implementations reveals design differences and potential improvements.

### Converter Comparison

| Aspect | tJava | tJavaRow |
|--------|-------|----------|
| `_map_component_parameters()` branch | Lines 332-346 | Lines 316-330 |
| Code identical? | Yes | Yes |
| Config keys produced | `java_code`, `imports` | `java_code`, `imports` |
| `converter.py` dispatch branch | **None** (generic path) | `elif component_type == 'tJavaRow': component = self.component_parser.parse_java_row(node, component)` (line 375) |
| Dedicated parser method | **None** | `parse_java_row(node, component)` (line 913) -- adds `output_schema` from FLOW metadata |
| Schema extraction | Generic (but tJava has no schema) | Dedicated method extracts FLOW schema for output |

**Key difference**: tJavaRow has BOTH a dispatch branch in `converter.py` AND a dedicated `parse_java_row()` method that extracts the output schema. tJava has neither -- it relies entirely on the generic path. Since tJava has no schema, the missing dedicated parser is less impactful than for tJavaRow, but the missing dispatch branch means the converter cannot add tJava-specific logic (like DIE_ON_ERROR extraction) without modifying the generic `_map_component_parameters()` method.

### Engine Comparison

| Aspect | `JavaComponent` (tJava) | `JavaRowComponent` (tJavaRow) |
|--------|------------------------|-------------------------------|
| File | `java_component.py` (110 lines) | `java_row_component.py` (size varies) |
| Bridge method | `execute_one_time_expression()` | `execute_java_row()` |
| Passes context to Java? | Yes | Yes |
| Pushes Python-side globalMap to Java? | **No** (not pushed via putAll; Java instance field IS bound) | Yes (via putAll) |
| Calls `_sync_from_java()` internally? | **No** (called externally from component) | Yes (called inside bridge method) |
| Handles IMPORT? | **No** | **No** (same gap) |
| Has die_on_error? | **No** | **No** (same gap) |
| Has output schema? | No (not needed) | Yes (for output row structure) |
| Input data handling | Pass-through or empty DF | Transforms each input row |
| Stats tracking | Minimal (0/0/0 for no-input) | Tracks NB_LINE per input row count |

### Bridge Method Comparison Summary

| Feature | `execute_one_time_expression` | `execute_java_row` | `execute_batch_one_time_expressions` |
|---------|-------------------------------|---------------------|--------------------------------------|
| Passes context | Yes | Yes | Yes |
| Pushes Python-side globalMap | **No** (instance field bound, but no putAll) | Yes | Yes |
| Passes data | No (code only) | Yes (Arrow bytes) | No (expressions only) |
| Internal sync | **No** | Yes | No |
| Return type | Any (single value) | pd.DataFrame | Dict[str, Any] |
| Used by | JavaComponent | JavaRowComponent | BaseComponent._resolve_java_expressions |

---

## Appendix H: Registry and Type Mapping

### Engine Registry (engine.py lines 130-132)

```python
'JavaComponent': JavaComponent,
'Java': JavaComponent,
'tJava': JavaComponent,
```

Three aliases are registered:
- `JavaComponent` -- the v1 class name (used in converted job configs)
- `Java` -- shortened alias
- `tJava` -- Talend component type name (used when Talend type is preserved in config)

### Converter Type Mapping (component_parser.py line 61)

```python
'tJava': 'JavaComponent',
```

The converter maps the Talend component type `tJava` to the v1 engine type `JavaComponent`. This mapping is used when building the component's `type` field in the v1 JSON config. The engine then looks up `JavaComponent` in its registry to instantiate the correct class.

### Java Requirement Detection (converter.py line 534)

```python
if component_type in ['tJavaRow', 'tJava', 'JavaRowComponent', 'JavaComponent', 'JavaRow', 'Java']:
    logger.info(f"Java required: Found {component_type} component")
    return True
```

The converter's `_requires_java()` method checks for tJava (and all its aliases) when determining whether the converted job requires Java bridge initialization. This correctly flags jobs containing tJava components.

---

## Appendix I: Complete Execution Flow (End-to-End)

### From Talend XML to V1 Execution

```
1. Talend XML (.item file)
   +-- <node componentName="tJava_1" ...>
   |   +-- <elementParameter field="MEMO_JAVA" name="CODE" value="globalMap.put(...);\n"/>
   |   +-- <elementParameter field="MEMO_IMPORT" name="IMPORT" value="import java.util.*;\n"/>
   |   +-- <elementParameter field="CHECK" name="DIE_ON_ERROR" value="true"/>
   |   +-- <elementParameter field="TEXT" name="UNIQUE_NAME" value="tJava_1"/>
   |
   v
2. complex_converter/converter.py: _parse_component()
   +-- component_type = 'tJava'
   +-- No matching elif branch found
   +-- Falls through to end of elif chain
   +-- parse_base_component() already called before dispatch
   |   +-- Iterates elementParameter nodes
   |   +-- Strips quotes from values
   |   +-- Converts CHECK fields to boolean
   |   +-- Skips CODE/IMPORT for context wrapping (line 449)
   |   +-- Skips tJava for java expression marking (line 462)
   |   +-- Calls _map_component_parameters('tJava', config_raw) (line 472)
   |       +-- elif component_type == 'tJava': (line 333)
   |       +-- Decodes line break entities in CODE
   |       +-- Decodes line break entities in IMPORT
   |       +-- Returns {'java_code': code, 'imports': imports}
   |       +-- NOTE: DIE_ON_ERROR in config_raw but NOT returned
   +-- Returns component dict
   |
   v
3. V1 JSON Config
   {
     "type": "JavaComponent",
     "id": "tJava_1",
     "config": {
       "java_code": "globalMap.put(...);\n",
       "imports": "import java.util.*;\n"
     },
     "schema": {},
     "connections": [...]
   }
   |
   v
4. v1/engine/engine.py: instantiates JavaComponent
   +-- Looks up 'JavaComponent' in registry -> JavaComponent class
   +-- Calls JavaComponent(component_id='tJava_1', config=..., global_map=..., context_manager=...)
   +-- BaseComponent.__init__() sets up stats, execution mode, etc.
   +-- Sets java_bridge from engine's JavaBridgeManager
   |
   v
5. BaseComponent.execute(input_data=None)
   +-- Step 1: _resolve_java_expressions() -- skipped (no {{java}} markers in java_code)
   +-- Step 2: context_manager.resolve_dict(config) -- resolves ${context.var} in config values
   |           NOTE: java_code may contain ${context.var} patterns that get resolved here
   |           This could corrupt Java code that uses $ for other purposes
   +-- Step 3: _execute_batch(None) -> _process(None)
   |   +-- Reads java_code from config
   |   +-- Validates non-empty
   |   +-- Validates Java bridge available
   |   +-- Syncs context to bridge
   |   +-- Syncs globalMap to bridge (but bridge won't push via putAll to Java)
   |   +-- Calls java_bridge.execute_one_time_expression(java_code)
   |   |   +-- Java side: compiles and executes code with context (Python-side globalMap not pushed via putAll)
   |   +-- Calls java_bridge._sync_from_java() -- reads Java state back
   |   +-- Syncs context back to ContextManager
   |   +-- Syncs globalMap back to GlobalMap (Java-side puts visible; merge-update loses deletions)
   |   +-- Returns {'main': pd.DataFrame()}
   +-- Step 4: _update_global_map() -- writes stats (0,0,0) to globalMap
   |   +-- BUG: crashes with NameError on line 304 (undefined 'value' variable)
   +-- Returns result with stats
```

### Context Variable Resolution Concern

In Step 5, `context_manager.resolve_dict(config)` is called on the ENTIRE config dict, including `java_code`. If the Java code contains strings like `${some_java_variable}`, the context manager may attempt to resolve them as context variable references. This could corrupt Java code that uses `${}` syntax for purposes other than Talend context references (e.g., Java string templates, Groovy GStrings).

However, in practice:
- Java does not use `${...}` syntax natively (Groovy does, but standard Java does not)
- Talend context references in Java code use `context.varname` syntax, not `${context.varname}`
- The converter wraps context refs in `${...}` for ContextManager resolution, but only for NON-CODE fields (line 449 skips CODE/IMPORT)

So this is unlikely to be an issue in practice, but the architecture allows for it if a future change modifies the context resolution logic.

---

## Appendix J: Related Component Audit Cross-References

| Related Component | Audit Report | Shared Issues |
|-------------------|-------------|---------------|
| `tJavaRow` / `JavaRowComponent` | `docs/v1/audit/components/tJavaRow.md` | Identical converter parameter mapping code (CONV-JC-005); same XML entity decoding gap (CONV-JC-001); IMPORT not used by engine (shared gap); cross-cutting base class bugs (BUG-JC-001, BUG-JC-002) |
| All components | -- | Cross-cutting bugs: `_update_global_map()` undefined variable (BUG-JC-001), `GlobalMap.get()` undefined parameter (BUG-JC-002) |

---

## Appendix K: Talend tJava Common Usage Patterns

This appendix documents the most common patterns for tJava usage in production Talend jobs, and how each pattern is supported (or not) by the v1 engine.

### Pattern 1: PreJob Initialization

**Talend pattern**: tJava at the start of a job (or in a PreJob section) to set up context variables, create directories, log job start times, or initialize resources.

```java
// Set start time for job duration tracking
globalMap.put("JOB_START_TIME", System.currentTimeMillis());

// Create output directory if not exists
java.io.File outputDir = new java.io.File(context.output_dir);
if (!outputDir.exists()) {
    outputDir.mkdirs();
    System.out.println("Created output directory: " + context.output_dir);
}

// Log job start
System.out.println("[" + TalendDate.formatDate("yyyy-MM-dd HH:mm:ss", new java.util.Date()) + "] Job started");
```

**V1 support**: PARTIALLY BROKEN -- `globalMap.put()` works (Java-side instance field is bound), but `globalMap.get()` for Python-only keys returns stale/missing values (ENG-JC-001). Context variable read works. `TalendDate` routine access depends on routine loading. `System.out.println()` may or may not work depending on Java bridge stdout handling. Additionally, if tJava is inside a loop, GroovyShell Metaspace leak (BUG-JC-008) will eventually crash the JVM.

### Pattern 2: Intermediate Calculations Between Subjobs

**Talend pattern**: tJava between two data processing subjobs to calculate aggregate values from globalMap statistics and store results for downstream use.

```java
// Read row counts from previous components
int inputRows = ((Integer) globalMap.get("tFileInputDelimited_1_NB_LINE")).intValue();
int outputRows = ((Integer) globalMap.get("tFileOutputDelimited_1_NB_LINE")).intValue();

// Calculate reject rate
double rejectRate = (inputRows > 0) ? ((double)(inputRows - outputRows) / inputRows) * 100.0 : 0.0;
globalMap.put("REJECT_RATE", rejectRate);

// Conditional logic based on reject rate
if (rejectRate > 10.0) {
    globalMap.put("QUALITY_FLAG", "WARNING");
} else {
    globalMap.put("QUALITY_FLAG", "OK");
}
```

**V1 support**: PARTIALLY BROKEN -- `globalMap.put()` works (Java-side instance field is bound), but `globalMap.get()` for Python-only keys (like `tFileInputDelimited_1_NB_LINE` and `tFileOutputDelimited_1_NB_LINE`) returns stale/missing values (ENG-JC-001). This is a very common production pattern and the inability to read upstream stats is a critical gap.

### Pattern 3: PostJob Cleanup and Notification

**Talend pattern**: tJava at the end of a job (or in a PostJob section) to archive files, send email notifications, or update status in a database.

```java
// Calculate job duration
long duration = System.currentTimeMillis() - ((Long) globalMap.get("JOB_START_TIME")).longValue();
String durationStr = String.format("%d min, %d sec",
    (duration / 1000) / 60,
    (duration / 1000) % 60);

// Log job completion
System.out.println("[" + TalendDate.formatDate("yyyy-MM-dd HH:mm:ss", new java.util.Date())
    + "] Job completed in " + durationStr);

// Archive output file
java.io.File output = new java.io.File((String) globalMap.get("OUTPUT_FILE_PATH"));
java.io.File archive = new java.io.File(context.archive_dir + "/" + output.getName());
output.renameTo(archive);
```

**V1 support**: PARTIALLY BROKEN -- `globalMap.get()` for Python-only keys (like `JOB_START_TIME` if set from Python or `OUTPUT_FILE_PATH` from upstream components) returns stale/missing values (ENG-JC-001). `globalMap.put()` works. File operations within Java code may work if the JVM has filesystem access.

### Pattern 4: Conditional Branching via globalMap

**Talend pattern**: tJava sets a flag in globalMap, then downstream components use Run_If triggers to conditionally execute based on that flag.

```java
// Check if input file exists
java.io.File inputFile = new java.io.File(context.input_file_path);
if (inputFile.exists() && inputFile.length() > 0) {
    globalMap.put("FILE_READY", true);
} else {
    globalMap.put("FILE_READY", false);
    System.out.println("WARNING: Input file not found or empty: " + context.input_file_path);
}
```

Then in the Talend job, a Run_If trigger with condition `((Boolean)globalMap.get("FILE_READY")).booleanValue()` controls whether the data processing subjob executes.

**V1 support**: PARTIALLY WORKING -- `globalMap.put()` works (Java-side instance field is bound), so flags set via `globalMap.put("FILE_READY", true)` will sync back to Python. However, context variable read (`context.input_file_path`) works. The conditional branching pattern should mostly work for this specific use case since it relies on `put()` not `get()` for Python-only keys.

### Pattern 5: Context Variable Calculation

**Talend pattern**: tJava calculates derived context variables from existing ones.

```java
// Build output filename from context variables
String timestamp = TalendDate.formatDate("yyyyMMdd_HHmmss", new java.util.Date());
context.output_file = context.output_dir + "/" + context.job_name + "_" + timestamp + ".csv";
```

**V1 support**: LIKELY WORKS -- Context read and write is synced correctly (ENG-JC-004 limitations aside). `TalendDate` routine access depends on routine loading. This is one of the few patterns that should work in the current implementation.

### Pattern 6: Error Handling with DIE_ON_ERROR=false

**Talend pattern**: tJava wrapped in an error handler that catches exceptions and sets error flags.

```java
try {
    // Risky operation
    java.net.URL url = new java.net.URL(context.api_endpoint);
    java.net.HttpURLConnection conn = (java.net.HttpURLConnection) url.openConnection();
    int responseCode = conn.getResponseCode();
    globalMap.put("API_STATUS", responseCode);
} catch (Exception e) {
    globalMap.put("API_STATUS", -1);
    globalMap.put("API_ERROR", e.getMessage());
    System.err.println("API call failed: " + e.getMessage());
}
```

With `DIE_ON_ERROR=false`, if the entire tJava code block throws an unhandled exception, the job continues via SUBJOB_ERROR trigger.

**V1 support**: PARTIALLY BROKEN -- `DIE_ON_ERROR` not supported (ENG-JC-002). `globalMap.put()` works (Java-side instance field is bound), so the internal try/catch pattern with `globalMap.put("API_STATUS", ...)` works. However, the outer `DIE_ON_ERROR=false` behavior is missing, so an unhandled exception from the tJava block will kill the job instead of firing SUBJOB_ERROR.

---

## Appendix L: Detailed Base Class Interaction Analysis

This appendix documents how `JavaComponent` interacts with `BaseComponent` lifecycle methods and where assumptions break down.

### BaseComponent.execute() Lifecycle

When `execute()` is called on a `JavaComponent` instance, the following lifecycle executes:

```
execute(input_data=None)
  |
  +-- (1) self.status = ComponentStatus.RUNNING
  |
  +-- (2) start_time = time.time()
  |
  +-- (3) if self.java_bridge: self._resolve_java_expressions()
  |       - Scans self.config for {{java}} markers
  |       - For tJava, CONFIG contains 'java_code' and 'imports'
  |       - Neither should have {{java}} markers (skipped by converter)
  |       - RISK: If java_code accidentally contains "{{java}}" as a literal
  |         string (e.g., in a comment), it would be incorrectly processed
  |
  +-- (4) if self.context_manager: self.config = self.context_manager.resolve_dict(self.config)
  |       - Scans ALL config values for ${context.var} patterns
  |       - INCLUDES java_code and imports values
  |       - RISK: If java_code contains "${" followed by "context.", the
  |         ContextManager will attempt to resolve it as a context reference
  |       - In practice, Talend Java code uses "context.var" not "${context.var}"
  |       - The converter skips wrapping context refs in CODE fields (line 449)
  |       - So this risk is minimal but not zero
  |
  +-- (5) mode = self._determine_execution_mode() -> HYBRID -> BATCH (no input data)
  |
  +-- (6) result = self._execute_batch(None) -> self._process(None)
  |       - This is where JavaComponent._process() runs
  |       - See Phase 1-5 in Appendix E for detailed flow
  |
  +-- (7) self.stats['EXECUTION_TIME'] = time.time() - start_time
  |
  +-- (8) self._update_global_map()
  |       - Iterates self.stats dict
  |       - Calls self.global_map.put_component_stat(self.id, stat_name, stat_value)
  |       - BUG: Log line references undefined 'value' variable (BUG-JC-001)
  |       - This will CRASH, causing the component to appear as failed
  |         even though _process() completed successfully
  |
  +-- (9) self.status = ComponentStatus.SUCCESS
  |       - NOTE: This line is AFTER _update_global_map()
  |       - If _update_global_map() crashes (BUG-JC-001), status remains RUNNING
  |       - The exception propagates from execute(), so the outer except catches it
  |
  +-- (10) result['stats'] = self.stats.copy()
  |
  +-- (11) return result
```

### Exception Flow

When an exception occurs anywhere in the lifecycle:

```
execute(input_data=None)
  |
  +-- try: [any step above]
  |
  +-- except Exception as e:
  |       +-- self.status = ComponentStatus.ERROR
  |       +-- self.error_message = str(e)
  |       +-- self.stats['EXECUTION_TIME'] = time.time() - start_time
  |       +-- self._update_global_map()  <-- BUG: will ALSO crash here
  |       +-- logger.error(f"Component {self.id} execution failed: {e}")
  |       +-- raise  <-- Re-raises the ORIGINAL exception
```

**Critical cascade**: If `_process()` succeeds but `_update_global_map()` crashes (BUG-JC-001), the exception handler calls `_update_global_map()` AGAIN (line 231), which will ALSO crash. The original NameError from line 304 is re-raised, hiding any information about what actually happened. The component's Java code executed successfully, but the job sees a NameError about an undefined variable `value`.

### Input Data Handling

For tJava, `input_data` is almost always `None`. However, the base class's `_execute_streaming()` method has logic for handling Iterator inputs:

```python
def _execute_streaming(self, input_data):
    if input_data is None:
        return self._process(None)
    if isinstance(input_data, pd.DataFrame):
        chunks = self._create_chunks(input_data)
    else:
        chunks = input_data
    results = []
    for chunk in chunks:
        chunk_result = self._process(chunk)
        if chunk_result.get('main') is not None:
            results.append(chunk_result['main'])
    if results:
        combined = pd.concat(results, ignore_index=True)
        return {'main': combined}
    else:
        return {'main': pd.DataFrame()}
```

If HYBRID mode somehow selected STREAMING (e.g., if input_data were a very large DataFrame), `_process()` would be called once per chunk. This would mean the tJava code executes MULTIPLE times -- once per chunk. This violates the one-time execution semantics of tJava. However, since tJava never receives input data in practice, this is a theoretical concern.

### Stats Initialization

`BaseComponent.__init__()` initializes stats to:
```python
self.stats = {
    'NB_LINE': 0,
    'NB_LINE_OK': 0,
    'NB_LINE_REJECT': 0,
    'NB_LINE_INSERT': 0,
    'NB_LINE_UPDATE': 0,
    'NB_LINE_DELETE': 0,
    'EXECUTION_TIME': 0.0
}
```

For tJava, all NB_LINE stats remain 0 (no data processed). Only EXECUTION_TIME is updated by the base class. These zero values are written to globalMap via `_update_global_map()`, creating entries like:
- `tJava_1_NB_LINE = 0`
- `tJava_1_NB_LINE_OK = 0`
- `tJava_1_NB_LINE_REJECT = 0`
- `tJava_1_NB_LINE_INSERT = 0`
- `tJava_1_NB_LINE_UPDATE = 0`
- `tJava_1_NB_LINE_DELETE = 0`
- `tJava_1_EXECUTION_TIME = 0.5` (example)

In Talend, tJava does NOT set these variables. The extra globalMap entries are harmless but pollute the namespace and can confuse debugging.

---

## Appendix M: Py4J Serialization Behavior for Context and GlobalMap

The Java bridge uses Py4J's `auto_convert=True` mode for type conversion between Python and Java. Understanding the serialization behavior is important for predicting which context/globalMap value types will survive the round-trip.

### Py4J Auto-Convert Type Mapping

| Python Type | Java Type | Round-trip Safe? | Notes |
|-------------|-----------|------------------|-------|
| `str` | `String` | Yes | Full Unicode support |
| `int` | `Integer` or `Long` | Yes | Python ints > 2^31 become Java Long |
| `float` | `Double` | Yes | IEEE 754 double precision |
| `bool` | `Boolean` | Yes | `True`/`False` -> `true`/`false` |
| `None` | `null` | Yes | Null handling consistent |
| `list` | `java.util.ArrayList` | **Partial** | Elements converted recursively. Nested types may not survive. |
| `dict` | `java.util.HashMap` | **Partial** | Keys must be strings for reliable conversion. Nested values converted recursively. |
| `datetime.datetime` | Not auto-converted | **No** | Py4J does not auto-convert Python datetime. Must be serialized as string or epoch. |
| `decimal.Decimal` | Not auto-converted | **No** | Py4J does not auto-convert Python Decimal. Must be serialized as string. |
| `bytes` | `byte[]` | **Partial** | May work but not guaranteed. |

### Implications for tJava

1. **Simple context variables** (String, Integer, Double): Work correctly in both directions.
2. **Date context variables**: If a Talend job has context variables of type `id_Date`, the Python ContextManager stores them as Python datetime objects. These will NOT be correctly serialized to Java by Py4J. The Java code will receive a Py4J proxy object instead of a `java.util.Date`.
3. **BigDecimal context variables**: Similar to dates -- Python `Decimal` objects are not auto-converted.
4. **List/Dict context variables**: Work for simple nested types but may fail for complex nested structures.

### Sync-Back Concerns

When `_sync_from_java()` reads values back from Java:
- Java `String` -> Python `str` (correct)
- Java `Integer`/`Long` -> Python `int` (correct)
- Java `Double` -> Python `float` (correct)
- Java `Boolean` -> Python `bool` (correct)
- Java `Date` -> Py4J proxy object (NOT a Python datetime)
- Java `ArrayList` -> Python `list` (elements converted recursively)
- Java `HashMap` -> Python `dict` (keys/values converted recursively)

If the tJava code creates a `java.util.Date` and puts it in globalMap, the Python-side will receive a Py4J proxy object, not a Python datetime. Downstream Python components expecting a datetime will fail.

### Recommendation

For maximum compatibility:
- Context variables should be serialized to/from strings at the Python-Java boundary
- Date values should be passed as ISO-8601 strings
- BigDecimal values should be passed as string representations
- Complex objects should be JSON-serialized

This serialization layer does not currently exist in the bridge.
