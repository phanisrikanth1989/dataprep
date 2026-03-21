# Audit Report: tSetGlobalVar / SetGlobalVar

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tSetGlobalVar` |
| **V1 Engine Class** | `SetGlobalVar` |
| **Engine File** | `src/v1/engine/components/file/set_global_var.py` (153 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tsetglobalvar()` (lines 2644-2736) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tSetGlobalVar':` (lines 367-368) |
| **Registry Aliases** | `SetGlobalVar`, `tSetGlobalVar` (registered in `src/v1/engine/engine.py` lines 89-90) |
| **Category** | Custom Code / Global Variable |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/set_global_var.py` | Engine implementation (153 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 2644-2736) | Three-tier fallback parser for VARIABLES table from Talend XML |
| `src/converters/complex_converter/converter.py` (lines 367-368) | Dispatch -- dedicated `elif` branch for `tSetGlobalVar` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for user-defined variables and component stats |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ComponentExecutionError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports (line 20: `from .set_global_var import SetGlobalVar`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 4 | 1 | Three-tier fallback parsing covers most XML structures; no `{{java}}` marking on values; no context variable wrapping; `CONNECTION_FORMAT` not extracted; Tier 3 skip list incomplete; greedy `strip('\"')` corrupts multi-quoted values |
| Engine Feature Parity | **Y** | 1 | 4 | 1 | 1 | Pass-through works; Java "new " execution has security gap; no `die_on_error` handling; no `NB_LINE` tracking for variables set; globalMap crash bug; `resolve_dict()` cannot reach VARIABLES list entries |
| Code Quality | **Y** | 2 | 2 | 2 | 1 | Cross-cutting base class bugs; `_validate_config()` dead code; no error handling per variable; unused pandas import |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | Lightweight component; no data processing. Minor: unnecessary pandas import |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tSetGlobalVar Does

`tSetGlobalVar` is a Custom Code family component that sets global variables in Talend's `globalMap`. It provides a GUI-based way to define key-value pairs that are stored in the job-wide `globalMap` HashMap, making them accessible to all downstream components via `globalMap.get("KEY")`. The component is commonly used to: (1) store constants for use throughout a job, (2) capture intermediate results from upstream processing, (3) set configuration parameters that downstream components reference, and (4) initialize counters or flags before looping constructs.

In Talend's generated Java code, each variable entry produces a `globalMap.put("KEY", VALUE)` statement. The VALUE can be any Java expression, including `new java.util.Date()`, `new Integer(42)`, string concatenations with context variables, or references to other globalMap entries. Since `globalMap` stores Java `Object` types, values can be of any type but require casting when retrieved (e.g., `(String)globalMap.get("myVar")`).

**Source**: [tSetGlobalVar Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/global-variable/tsetglobalvar-standard-properties), [Configuring tSetGlobalVar (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/global-variable/tsetglobalvar-tjava-configuring-tsetglobalvar-component-standard-component), [Configuring tSetGlobalVar (Talend 7.3)](https://help.talend.com/r/en-US/7.3/global-variable/tsetglobalvar-tjava-configuring-tsetglobalvar-component-standard-component)

**Component family**: Custom Code (Global Variable)
**Available in**: All Talend products (Standard).
**Required JARs**: None (pure Java code generation).

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Variables | `VARIABLES` | Table (KEY, VALUE) | Empty | **Core parameter**. Table with two columns: KEY (variable name as a string) and VALUE (any Java expression or literal). Each row defines one global variable. Multiple rows supported. |
| 3 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |
| 4 | Connection Format | `CONNECTION_FORMAT` | Dropdown | `row` | Connection format for linking to other components. Controls whether the component receives row or table data. |
| 5 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |

### 3.2 Advanced Settings

`tSetGlobalVar` has no advanced settings. It is a deliberately simple component.

### 3.3 VARIABLES Table Structure

The VARIABLES table is the core of this component. Each row contains:

| Column | XML Element | Type | Description |
|--------|-------------|------|-------------|
| KEY | `elementValue[@elementRef='KEY']` | String | The name of the global variable. Used as the key in `globalMap.put(KEY, VALUE)`. Must be a valid Java identifier string (typically quoted). |
| VALUE | `elementValue[@elementRef='VALUE']` | Java Expression | The value to store. Can be: a string literal (`"hello"`), a number (`42`), a Java constructor (`new java.util.Date()`), a context variable reference (`context.myVar`), a globalMap reference (`globalMap.get("otherKey")`), or any valid Java expression. |

**Talend XML representation**:
```xml
<elementParameter field="TABLE" name="VARIABLES">
  <elementValue elementRef="KEY" value="&quot;batch_id&quot;"/>
  <elementValue elementRef="VALUE" value="&quot;BATCH_001&quot;"/>
  <elementValue elementRef="KEY" value="&quot;process_date&quot;"/>
  <elementValue elementRef="VALUE" value="new java.util.Date()"/>
</elementParameter>
```

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input/Output | Row > Main | **Pass-through**. Input data is passed through unchanged. The component sets global variables but does not modify the data flow. Input is optional -- the component can operate as a standalone component triggered via OnSubjobOk. |
| `ITERATE` | Input | Iterate | When connected via an iterate link, the component executes once per iteration. Common pattern: `tFlowToIterate -> tSetGlobalVar` to capture each row's values as global variables. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Used for chaining subjobs. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| User-defined keys | Any (Object) | During execution | The primary purpose of this component. Each KEY/VALUE row produces a `globalMap.put(KEY, VALUE)` call. |
| `{id}_NB_LINE` | Integer | After execution | Total number of rows processed. For standalone operation, this is 0. When receiving input flow, it equals the number of input rows passed through. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully passed through. Equals `NB_LINE` (no reject mechanism). |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Always 0 (no reject mechanism for this component). |
| `{id}_ERROR_MESSAGE` | String | On error | Error message if the component fails during execution. |

### 3.6 Behavioral Notes

1. **Pass-through semantics**: `tSetGlobalVar` does NOT modify input data. Any input DataFrame/flow is returned unchanged as output. This is critical -- it is a side-effect-only component that writes to the globalMap.

2. **Execution order**: Variables are set in the order they appear in the VARIABLES table. Later variables can reference earlier ones via `globalMap.get()`, e.g., KEY=`"full_path"`, VALUE=`(String)globalMap.get("base_dir") + "/" + context.filename`.

3. **Variable overwrite**: If a KEY already exists in globalMap (e.g., set by a previous component), it is silently overwritten. There is no merge or append behavior.

4. **Type preservation**: In Talend, `globalMap` stores Java `Object` types. `new Integer(42)` stores an Integer, `"hello"` stores a String, `new java.util.Date()` stores a Date. Downstream components must cast the value to the correct type. In Python, the equivalent must preserve type information where possible.

5. **Context variable resolution**: VALUE expressions can reference context variables (e.g., `context.input_dir`). These are resolved at runtime by Talend's code generation, producing the actual context value in the `globalMap.put()` call.

6. **Iterate pattern**: When used with `tFlowToIterate`, the component executes once per iteration row. The LAST iteration's values overwrite previous ones. This is a common source of bugs when users expect all rows' values to be accumulated rather than overwritten.

7. **No schema**: `tSetGlobalVar` does not define or require an output schema. It passes through whatever schema its input connection provides. If there is no input, there is no schema.

8. **Standalone operation**: The component can operate without any input connection, triggered by a trigger (OnSubjobOk, OnComponentOk, RunIf). In this mode, it simply sets variables and produces no data output.

9. **globalMap scope**: Variables set by `tSetGlobalVar` persist for the entire job execution. They are available in all subsequent subjobs, not just the current one. This is Talend's `globalMap` which is job-scoped.

10. **Value types in practice**: Common VALUE patterns include:
    - String literals: `"BATCH_001"`
    - Integer literals: `42`, `0`
    - Java constructors: `new java.util.Date()`, `new java.text.SimpleDateFormat("yyyy-MM-dd").format(new java.util.Date())`
    - Context references: `context.batch_id`
    - globalMap references: `globalMap.get("tFileInputDelimited_1_NB_LINE")`
    - Concatenations: `"prefix_" + context.env + "_suffix"`
    - Ternary expressions: `context.mode.equals("prod") ? "PRODUCTION" : "TEST"`

---

## 4. Converter Audit

### 4.1 Parser Architecture

The converter uses a **dedicated `parse_tsetglobalvar()` method** in `component_parser.py` (lines 2644-2736). This method is dispatched from `converter.py` line 367-368:

```python
elif component_type == 'tSetGlobalVar':
    component = self.component_parser.parse_tsetglobalvar(node, component)
```

**Converter flow**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)` first
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict (lines 433-458)
3. Since `tSetGlobalVar` is NOT in `components_with_dedicated_parsers` list (line 421), the generic raw parameter processing runs
4. The generic path applies `mark_java_expression()` to all non-CODE/IMPORT string values in `config_raw` (lines 466-469)
5. `_map_component_parameters('tSetGlobalVar', config_raw)` is called, which falls through to `else: return config_raw` (lines 385-386), returning all raw params as-is
6. Back in `converter.py`, the dedicated `parse_tsetglobalvar()` method is called, which OVERRIDES `component['config']['VARIABLES']` with the structured variable list parsed from the XML table
7. The generic `config_raw` values (with `{{java}}` marks) remain in `component['config']`, but the VARIABLES list values are extracted separately by the dedicated parser WITHOUT `{{java}}` marking

### 4.2 Three-Tier Fallback Parsing

The `parse_tsetglobalvar()` method implements three parsing strategies, tried in sequence:

#### Tier 1: KEY/VALUE elementRef Pairs (Lines 2649-2689)

Parses the standard Talend VARIABLES table structure:
```xml
<elementParameter field="TABLE" name="VARIABLES">
  <elementValue elementRef="KEY" value="&quot;batch_id&quot;"/>
  <elementValue elementRef="VALUE" value="&quot;BATCH_001&quot;"/>
</elementParameter>
```

The parser uses XPath `.//elementParameter[@name="VARIABLES"]` to find the VARIABLES parameter, then iterates all `elementValue` children. It maintains `current_key` / `current_value` state:
- When `elementRef='KEY'` is found, if a previous key-value pair exists, it is saved first, then the new key is set
- When `elementRef='VALUE'` is found, the value is recorded and if a key exists, the pair is saved immediately
- After the loop, any remaining unpaired key-value pair is saved

**Known issue**: The double-save logic on lines 2664-2668 and 2676-2681 means each complete pair is saved TWICE if VALUE immediately follows KEY (once when VALUE completes the pair on line 2676-2681, and the pending-save check on lines 2664-2668 would NOT trigger because `current_key` was reset to None on line 2681). This logic is correct but fragile -- if the XML has KEY-KEY-VALUE ordering, the first KEY would be lost (overwritten by second KEY with `current_value` still None, so the save on line 2664 would not trigger since `current_value is None`).

#### Tier 2: TABLE/row/cell Structure (Lines 2692-2709)

Fallback for alternative XML structures:
```xml
<elementParameter name="VARIABLES">
  <TABLE>
    <row>
      <cell columnName="KEY" value="batch_id"/>
      <cell columnName="VALUE" value="BATCH_001"/>
    </row>
  </TABLE>
</elementParameter>
```

This tier handles column names: `KEY`, `NAME`, `VARIABLE_NAME` for the key, and `VALUE`, `VARIABLE_VALUE` for the value. The cell content can come from either `cell.text` or `cell.get('value', '')`.

#### Tier 3: Java Declaration Scan (Lines 2712-2726)

Last-resort fallback for non-standard configurations. Scans ALL `elementParameter` nodes (not just VARIABLES) looking for values containing `'java.util.'` or `'new '`. Skips `VARIABLES`, `UNIQUE_NAME`, and `CONNECTION_FORMAT` parameters.

**Serious concern**: This tier uses the parameter NAME as the variable name (line 2724: `'name': param_name`), which means the Talend XML parameter name (e.g., `MY_VAR`) becomes the globalMap key. This may or may not match the user's intent, depending on how the XML was structured. It also risks picking up unrelated parameters that happen to contain Java code.

### 4.3 Parameter Extraction

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `VARIABLES` (table) | **Yes** | `VARIABLES` (list of dicts) | 2649-2726 | Three-tier fallback. Each entry has `name` and `value` keys. |
| 2 | `CONNECTION_FORMAT` | **No** | -- | -- | Explicitly skipped in Tier 3 filter (line 2718), but never extracted as a config value. Other components extract this. |
| 3 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |
| 4 | `TSTATCATCHER_STATS` | No | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 5 | `LABEL` | No | -- | -- | Not extracted (cosmetic -- no runtime impact) |

**Summary**: 1 of 5 parameters extracted. However, only VARIABLES is runtime-relevant, so effective coverage of runtime parameters is 100% for the table structure but with critical quality gaps in value handling.

### 4.4 Expression Handling

**Critical gap**: The `parse_tsetglobalvar()` method does NOT call `mark_java_expression()` or `detect_java_expression()` on the parsed variable VALUES. This means:

1. Values like `context.batch_id + "_suffix"` are stored as raw strings without `{{java}}` marking
2. Values like `new java.util.Date()` are stored as raw strings without `{{java}}` marking
3. Simple context references like `context.myVar` are NOT wrapped with `${context.myVar}` for ContextManager resolution

The generic `parse_base_component()` DOES apply `mark_java_expression()` to `config_raw` values (lines 466-469), but the VARIABLES table values are extracted by the dedicated parser AFTER the generic processing. The dedicated parser extracts values directly from the XML `elementValue` nodes, bypassing the generic expression handling entirely.

Compare with how `parse_base_component()` handles expressions:
- Lines 449-456: Detects `context.` references and wraps them with `${...}` for ContextManager
- Lines 466-469: Marks Java expressions with `{{java}}` prefix for the Java bridge

Neither of these steps is performed on the VARIABLES values in `parse_tsetglobalvar()`.

**Consequence**: The engine's `_process()` method has its OWN ad-hoc Java expression detection (checking for `"new "` prefix), which partially compensates for the converter's missing `{{java}}` marking. But this engine-side detection is incomplete -- it only catches `"new "` prefixed values, missing concatenations, method calls, context references, and other Java expressions.

### 4.5 Value Stripping

Line 2660: `element_value = elem.get('value', '').strip('"')` strips outer double quotes from values. This is important because Talend XML stores string values with escaped quotes (e.g., `value="&quot;BATCH_001&quot;"`). However:

1. **Single quotes not stripped**: If a value uses single quotes (unusual but possible), they are preserved
2. **Inner quotes lost**: If a value is `"hello \"world\""`, the outer quotes are stripped but escaped inner quotes are NOT unescaped. The result would be `hello \"world\"` instead of `hello "world"`
3. **Non-string values affected**: Numeric values like `"42"` have their quotes stripped correctly to `42` (as a string). But `new java.util.Date()` would correctly have its quotes stripped since it would be stored as `value="new java.util.Date()"` (without outer quotes in the XML attribute)

### 4.6 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-SGV-001 | **P1** | **No `{{java}}` expression marking on VARIABLES values**: The dedicated `parse_tsetglobalvar()` method extracts values directly from XML without calling `mark_java_expression()`. Java expressions like `context.batch_id + "_suffix"`, `globalMap.get("key")`, `(String)globalMap.get("key") + "/path"` are stored as raw strings. The engine's `_resolve_java_expressions()` in `BaseComponent.execute()` will NOT detect or resolve these because they lack the `{{java}}` prefix. Only the engine's ad-hoc `"new "` detection catches a subset of Java expressions. |
| CONV-SGV-002 | **P1** | **No context variable wrapping for VARIABLES values**: Context references like `context.myVar` in variable VALUES are not wrapped with `${context.myVar}`. The `BaseComponent.execute()` method calls `context_manager.resolve_dict(self.config)` which recurses into nested dicts, but `resolve_dict()` does NOT recurse into dicts nested inside lists (context_manager.py:156-157). Since VARIABLES is a list of dicts, context references in variable values are DEFINITIVELY unreachable by the resolver -- bare `context.myVar` references will never be resolved at runtime. |
| CONV-SGV-003 | **P2** | **Tier 3 fallback uses param NAME as variable name**: When the three-tier fallback reaches Tier 3 (Java declaration scan), it uses the Talend XML parameter name as the globalMap key (line 2724). This may produce incorrect variable names for components where the parameter name differs from the intended globalMap key. |
| CONV-SGV-004 | **P2** | **`CONNECTION_FORMAT` not extracted**: While explicitly filtered out in Tier 3 (line 2718), `CONNECTION_FORMAT` is never extracted as a config value. Other components consistently extract this parameter. While `tSetGlobalVar` is typically used with `row` format, the missing extraction could cause issues if a job uses a different format. |
| CONV-SGV-005 | **P3** | **No validation of KEY format**: Variable KEYs are stored as-is after `.strip('"')`. No validation that the key is a valid identifier or non-empty string. An empty KEY after stripping (e.g., `value='""'`) would produce `name=''`, which the engine's `_process()` skips via `if var_name:` check, but the converter should warn about this. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Set global variables | **Yes** | Medium | `_process()` line 109-141 | Core loop iterates VARIABLES list and calls `global_map.put()`. Works for simple string values. |
| 2 | Pass-through input data | **Yes** | High | `_process()` line 148 | `return {"main": data}` passes input unchanged. Correct. |
| 3 | Java expression evaluation | **Partial** | Low | `_process()` lines 115-135 | Only detects `"new "` prefix. Misses concatenations, method calls, ternary, globalMap refs, context refs. |
| 4 | Multiple variables | **Yes** | High | `_process()` lines 109-141 | Iterates full list. Correct. |
| 5 | Variable overwrite | **Yes** | High | Via `global_map.put()` | HashMap semantics -- last write wins. Correct. |
| 6 | Statistics tracking | **Yes** | Medium | `_process()` line 144 | Always reports (0, 0, 0). Does not track number of variables set as NB_LINE. See behavioral difference. |
| 7 | Context variable in values | **Partial** | Low | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict(self.config)` does NOT recurse into dicts nested inside lists (context_manager.py:156-157). Since VARIABLES is a list of dicts, context references are definitively unreachable even if the converter wrapped values with `${...}`. |
| 8 | Java bridge for "new " values | **Yes** | Medium | `_process()` lines 115-135 | Checks `context_manager.get_java_bridge()`. Falls back to string if bridge unavailable. |
| 9 | Standalone operation (no input) | **Yes** | High | `_process()` line 89 | `data: Any = None` -- input is optional. Returns `{"main": data}` which returns `None` when no input. |
| 10 | Error handling per variable | **Partial** | Low | `_process()` lines 127-131 | Only catches Java bridge evaluation errors (logs warning, falls back to string). No per-variable error handling for globalMap.put() failures. |
| 11 | `{id}_NB_LINE` globalMap | **Yes** | Medium | Via `_update_stats(0, 0, 0)` + `_update_global_map()` | Always 0. Does not reflect variables set count. |
| 12 | `{id}_ERROR_MESSAGE` globalMap | **No** | N/A | -- | Not implemented. Error message stored in `self.error_message` but not pushed to globalMap. |
| 13 | Die on error | **No** | N/A | -- | No `die_on_error` config check. All exceptions propagate unconditionally via `raise` on line 152. |
| 14 | Iterate connection support | **Partial** | Medium | Via engine's iterate mechanism | Engine handles iterate connections externally. Component re-executes per iteration. Variables overwrite as expected. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-SGV-001 | **P0** | **`_update_global_map()` crash (cross-cutting)**: `base_component.py` line 304 references undefined variable `value` (should be `stat_value`). This `NameError` will crash EVERY component execution when `global_map` is not None, including `SetGlobalVar`. The variables ARE set correctly via `global_map.put()` in `_process()`, but the subsequent `_update_global_map()` call in `execute()` line 218 will crash, preventing the component from completing successfully. |
| ENG-SGV-002 | **P1** | **Incomplete Java expression support**: The engine only detects Java expressions starting with `"new "` (line 115-116). Common Talend tSetGlobalVar value patterns are NOT handled: (a) string concatenation: `"prefix_" + context.env`, (b) globalMap references: `(String)globalMap.get("key")`, (c) ternary expressions: `context.mode.equals("prod") ? "X" : "Y"`, (d) method calls: `String.valueOf(globalMap.get("count"))`, (e) arithmetic: `((Integer)globalMap.get("count")) + 1`. All of these are stored as raw strings in globalMap instead of being evaluated. |
| ENG-SGV-003 | **P1** | **No `die_on_error` support**: The component's `_process()` method has a single outer try/except that catches ALL exceptions and re-raises them (line 150-152). There is no `die_on_error` config check. In Talend, when `die_on_error=false`, the component would log the error and continue. In v1, ANY error (including a single variable evaluation failure) terminates the entire component execution. |
| ENG-SGV-004 | **P1** | **NB_LINE always 0**: `_update_stats(0, 0, 0)` is hardcoded on line 144. In Talend, when `tSetGlobalVar` receives input data via a flow connection, `NB_LINE` reflects the number of rows that passed through. The v1 implementation does not count input rows. This can break downstream logic that checks `NB_LINE` for flow monitoring. |
| ENG-SGV-005 | **P2** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When an error occurs, `self.error_message` is set by the base class (line 229 of `base_component.py`), but this value is NOT stored in globalMap as `{id}_ERROR_MESSAGE`. Downstream error handling flows cannot access the error message via globalMap. |
| ENG-SGV-006 | **P3** | **Misclassified in file package**: `SetGlobalVar` is located in `src/v1/engine/components/file/` and imported from the `file` package. In Talend, `tSetGlobalVar` belongs to the Custom Code family, not File. This is a cosmetic/organizational issue but makes the codebase harder to navigate. |

### 5.3 Java Expression Detection Deep Dive

The engine's ad-hoc Java detection on lines 115-117:

```python
if (isinstance(var_value, str) and
    var_value.strip().startswith("new ") and self.context_manager and
    hasattr(self.context_manager, "get_java_bridge")):
```

This check has multiple issues:

1. **Only `"new "` prefix detected**: The check `var_value.strip().startswith("new ")` catches only Java constructor calls like `new java.util.Date()`, `new Integer(42)`, `new java.text.SimpleDateFormat(...)`. It misses ALL other Java expression types.

2. **Requires `context_manager` with `get_java_bridge`**: Even if the `"new "` pattern is detected, evaluation requires `self.context_manager` to exist AND have a `get_java_bridge` method. If context_manager is None (possible for standalone component execution), the value falls through to the string path without any warning that a Java expression was detected but not evaluated.

3. **`hasattr` check is fragile**: Using `hasattr(self.context_manager, "get_java_bridge")` couples the engine to a specific context_manager API. If the API changes, this silently falls through to string values.

4. **Fallback on Java bridge failure**: Lines 127-131 catch any exception from `java_bridge.execute_one_time_expression()` and fall back to storing the raw Java expression string. While this is safe from a crash perspective, it means `globalMap.get("process_date")` would return the string `"new java.util.Date()"` instead of an actual date object. Downstream components expecting a Date would break silently.

### 5.4 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| User-defined keys | Yes | **Yes** | `_process()` line 125/130/134/138 -> `global_map.put()` | Core functionality works for simple string values |
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats(0, 0, 0)` -> `_update_global_map()` | Always 0 -- does not count input rows or variables set |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Always 0 |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | Same mechanism | Always 0 (correct -- no reject mechanism) |
| `{id}_ERROR_MESSAGE` | Yes (on error) | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-SGV-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the loop variable (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just SetGlobalVar. The user-defined variables ARE set correctly in `_process()` before this crash occurs, but the component status transitions and stats reporting break. |
| BUG-SGV-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. Note: `SetGlobalVar._process()` only uses `global_map.put()`, so this bug does not directly affect variable setting, but it breaks any downstream component attempting to READ the variables via `global_map.get()`. |
| BUG-SGV-003 | **P1** | `src/v1/engine/components/file/set_global_var.py:59-87` | **`_validate_config()` is never called**: The method contains 28 lines of validation logic (checks VARIABLES is present, is a list, each entry is a dict with `name` and `value` fields). This method is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Missing VARIABLES config or malformed entries are only caught when they cause runtime errors in `_process()`. |
| BUG-SGV-004 | **P1** | `src/v1/engine/components/file/set_global_var.py:125` | **`global_map.put()` called without null-check on `self.global_map`**: Lines 125, 130, 134, 138 all call `self.global_map.put(var_name, ...)` but the method signature shows `global_map: Any = None` (base_component.py line 42). If `global_map` is None (e.g., component instantiated without a GlobalMap), these calls will raise `AttributeError: 'NoneType' object has no attribute 'put'`. The component's entire purpose is to set globalMap variables, so a None globalMap should be caught early with a clear error message. |
| BUG-SGV-005 | **P2** | `src/v1/engine/components/file/set_global_var.py:113` | **Empty `var_name` after `.get()` skipped silently**: `if var_name:` (line 113) skips entries where `name` is None, empty string, or any falsy value. While this prevents crashes, it silently drops variables without logging a warning. A variable with `name=""` could indicate a converter bug or malformed XML, and should be logged. |
| BUG-SGV-006 | **P2** | `src/v1/engine/components/file/set_global_var.py:111` | **NaN/None values stored in globalMap without conversion**: If `var_value` is None (when `"value"` key is missing from the variable dict), it is stored directly in globalMap as `None`. While `global_map.put()` accepts `Any`, Talend's globalMap stores Java `Object` types and does not store `null` for key-value pairs set by `tSetGlobalVar`. The converter's `.strip('"')` could also produce empty strings for values like `""`, which would be stored as empty strings -- matching Talend behavior for empty VALUE cells. |
| BUG-SGV-008 | **P1** | `src/v1/engine/context_manager.py:156-157` | **`resolve_dict()` does NOT recurse into dicts nested inside lists**: `context_manager.py` `resolve_dict()` iterates dict values and recurses into nested dicts, but does NOT recurse into dicts that are nested inside lists. VARIABLES is a list of dicts -- context references in variable values are definitively unreachable. This is confirmed, not speculative. Any `${context.var}` or bare `context.var` reference inside a VARIABLES entry will pass through unresolved regardless of converter wrapping. |
| BUG-SGV-009 | **P2** | `src/converters/complex_converter/component_parser.py:2718` | **Tier 3 skip list incomplete**: The Tier 3 Java declaration scan only skips `VARIABLES`, `UNIQUE_NAME`, and `CONNECTION_FORMAT` parameters. Standard parameters like `PROPERTY_TYPE` and `LABEL` with `'new '` in their value (e.g., a label text containing "new ") get picked up as spurious variables, polluting the VARIABLES list with non-variable entries. |
| BUG-SGV-010 | **P2** | `src/converters/complex_converter/component_parser.py:2660` | **Converter `strip('\"')` is greedy**: Python's `str.strip()` removes ALL occurrences of the specified characters from both ends, not just one pair of quotes. Multi-quoted values like `""value""` (which can occur in Talend XML with nested escaped quotes) get corrupted -- all leading and trailing quote characters are removed instead of stripping a single outer pair. Should use a single-pair strip pattern (e.g., regex or startswith/endswith check) instead. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-SGV-001 | **P2** | **Config key `VARIABLES` uses UPPER_CASE**: The VARIABLES config key (line 106: `self.config.get("VARIABLES", [])`) uses Talend-style UPPER_CASE. Other v1 components use snake_case for config keys (e.g., `header_rows`, `die_on_error`). The converter stores it as `VARIABLES` (line 2728), but STANDARDS.md conventions suggest snake_case for all config keys. |
| NAME-SGV-002 | **P2** | **Variable dict uses `name`/`value` instead of `key`/`value`**: The converter stores each variable as `{'name': ..., 'value': ...}` (lines 2666-2668). In Talend, the table columns are KEY and VALUE. Using `name` instead of `key` creates a semantic mismatch with the Talend data model. The engine's docstring (line 32) also uses `name`, so engine and converter are consistent with each other, but inconsistent with Talend. |
| NAME-SGV-003 | **P3** | **Component in `file` package**: `SetGlobalVar` is in `src/v1/engine/components/file/`. In Talend, it belongs to the Custom Code family. Should be in a `custom_code` or `misc` package. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-SGV-001 | **P1** | "`_validate_config()` must be called during initialization or execution" | Method exists (lines 59-87) but is never called. Dead code. 28 lines of unreachable validation logic. |
| STD-SGV-002 | **P2** | "Use snake_case for config keys" | `VARIABLES` config key uses UPPER_CASE. Should be `variables`. |
| STD-SGV-003 | **P3** | "No unused imports" | `import pandas as pd` on line 13 is never used in the module. The component does not process DataFrames -- it only sets globalMap variables and passes input through. |

### 6.4 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-SGV-001 | **P1** | **Arbitrary Java code execution via "new " prefix detection**: The engine evaluates ANY value starting with `"new "` as a Java expression via the Java bridge (line 124: `java_bridge.execute_one_time_expression(var_value)`). If the config comes from an untrusted source, this enables arbitrary code execution. For Talend-converted jobs where config is generated from trusted XML, this is acceptable. However, the `"new "` check is overly broad and could accidentally evaluate non-Java values that happen to start with "new " (e.g., `"new record created"` would be passed to the Java bridge). A more precise check (e.g., `"new "` followed by a qualified class name pattern) would reduce false positive risk. |
| SEC-SGV-002 | **P2** | **No input validation on variable names**: Variable names from the config are used directly as globalMap keys. If a malicious config sets a key like `tFileInputDelimited_1_NB_LINE`, it could overwrite statistics from other components, corrupting flow control logic. While this is unlikely in Talend-converted jobs, defense-in-depth suggests validating that user-defined keys do not collide with the `{component_id}_{STAT_NAME}` pattern used by `_update_global_map()`. |

### 6.5 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start (line 102) and completion (line 146), DEBUG for each variable set (lines 126, 131, 135, 139), WARNING for Java eval failure (line 128), ERROR for fatal failure (line 151) -- correct |
| Variable count logging | `variables_set` counter logged at INFO level on line 146 -- good |
| Sensitive data risk | **CONCERN**: DEBUG messages on lines 126, 131, 135, 139 log variable names and values: `f"Set global variable: {var_name} = {var_value}"`. If variables contain passwords, API keys, or other secrets (common in Talend jobs for DB connection strings), they will appear in logs. Line 126 mitigates this for Java-evaluated values by logging only the type: `f"Set global variable (evaluated): {var_name} = {type(evaluated_value)}"`. But lines 131, 135, 139 log the actual value. |
| No print statements | No `print()` calls -- correct |

### 6.6 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Does NOT use custom exceptions from `exceptions.py`. The docstring mentions `ComponentExecutionError` (line 100), but the code only uses generic `Exception` catching (line 150) and bare `raise` (line 152). |
| Exception chaining | No `raise ... from e` pattern. Line 152 uses bare `raise` which preserves the original exception but does not add context. |
| Per-variable error handling | Only for Java bridge evaluation (lines 127-131). No handling for `global_map.put()` failures or type conversion errors. |
| `die_on_error` handling | **Not implemented**. All exceptions propagate unconditionally. |
| No bare `except` | Uses `except Exception as e` (lines 127, 150) -- correct, not bare except |
| Error messages | Include component ID (line 151: `f"[{self.id}] Failed to set global variables: {e}"`) -- correct |
| Graceful degradation | Java bridge failure gracefully falls back to string value (line 130). But overall component failure propagates to caller with no recovery option. |
| Missing VARIABLES config | `self.config.get("VARIABLES", [])` on line 106 returns empty list, so no variables are set but no error either. The `_validate_config()` method would catch this, but it is never called. Component completes "successfully" with 0 variables set. |

### 6.7 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_validate_config(self) -> List[str]` and `_process(self, data: Any = None) -> Dict[str, Any]` -- correct |
| Parameter types | `data: Any = None` is appropriately flexible for pass-through semantics |
| Import coverage | `List`, `Optional`, `Dict`, `Any` imported from typing -- correct |
| Return type accuracy | `_process` returns `Dict[str, Any]` matching `{"main": data}` pattern -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-SGV-001 | **P3** | **Unused `import pandas as pd`**: Line 13 imports pandas but the module never uses it. This adds unnecessary import overhead (~150ms on first import in a process). While negligible for a single component, it demonstrates a code quality gap. The component only deals with scalar values and globalMap operations. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Data processing | None -- component does not process or copy data. Input is returned as-is (reference, not copy). |
| Variable storage | Variables stored as individual key-value pairs in globalMap's `_map` dict. Negligible memory overhead. |
| Pass-through efficiency | `return {"main": data}` returns a reference to the input data, not a copy. Correct for memory efficiency. |
| Java bridge overhead | `execute_one_time_expression()` may create a subprocess or JNI call for each Java expression. For components with many `"new "` prefixed variables, this could be slow. Consider batch evaluation. |

### 7.2 Scalability Considerations

| Scenario | Assessment |
|----------|------------|
| Many variables (100+) | Linear O(n) iteration. No performance concern. |
| Large input DataFrame pass-through | Zero overhead -- data is not inspected or copied. |
| Frequent re-execution (iterate loop) | Each iteration re-evaluates all variables. For "new " values, each triggers a Java bridge call. Could become a bottleneck in tight loops with many Java expressions. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `SetGlobalVar` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter unit tests | **No** | -- | No tests for `parse_tsetglobalvar()` method |

**Key finding**: The v1 engine has ZERO tests for this component. All 153 lines of v1 engine code and 93 lines of converter parser code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Set simple string variables | P0 | Create SetGlobalVar with `VARIABLES=[{"name":"k1","value":"v1"},{"name":"k2","value":"v2"}]`. Verify both variables are stored in globalMap with correct names and values. |
| 2 | Pass-through with DataFrame | P0 | Provide a DataFrame as input. Verify output `main` is the identical DataFrame (same id, not a copy). Verify globalMap variables are also set. |
| 3 | Pass-through with None input | P0 | Call `_process(None)`. Verify output is `{"main": None}`. Verify variables are still set in globalMap. |
| 4 | Empty VARIABLES list | P0 | Config with `VARIABLES=[]`. Verify component completes without error, returns `{"main": data}`, and sets 0 variables. |
| 5 | Missing VARIABLES config | P0 | Config with no VARIABLES key at all. Verify component completes without error using default `[]`. |
| 6 | globalMap.get() retrieval | P0 | After SetGlobalVar sets variables, verify `global_map.get("k1")` returns the correct value. (Currently blocked by BUG-SGV-002.) |
| 7 | Statistics tracking | P0 | Verify `stats['NB_LINE']`, `stats['NB_LINE_OK']`, `stats['NB_LINE_REJECT']` are all 0 after execution. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Java "new " expression with bridge | P1 | Set `value="new java.util.Date()"` with a mock Java bridge. Verify `java_bridge.execute_one_time_expression()` is called with the correct expression. Verify the evaluated result is stored in globalMap. |
| 9 | Java "new " fallback without bridge | P1 | Set `value="new java.util.Date()"` with NO Java bridge (context_manager=None). Verify the raw string `"new java.util.Date()"` is stored in globalMap. |
| 10 | Java bridge evaluation failure | P1 | Set `value="new InvalidClass()"` with a mock Java bridge that raises Exception. Verify the raw string is stored as fallback. Verify warning is logged. |
| 11 | Variable with empty name | P1 | VARIABLES entry with `{"name":"", "value":"v1"}`. Verify the entry is skipped (not stored in globalMap). Verify `variables_set` count does not include it. |
| 12 | Variable with None value | P1 | VARIABLES entry with `{"name":"k1"}` (no value key). Verify `None` is stored in globalMap. |
| 13 | Variable overwrite | P1 | Set `k1=v1`, then execute another SetGlobalVar with `k1=v2`. Verify globalMap has `k1=v2`. |
| 14 | Multiple variables execution order | P1 | Set variables `[a, b, c]` and verify they are all present in globalMap after execution. |
| 15 | GlobalMap None crash | P1 | Create SetGlobalVar with `global_map=None`. Execute with variables. Verify AttributeError with clear error message. |
| 16 | Context variable in value | P1 | Set `value="${context.batch_id}"` with a mock context_manager. Verify context resolution occurs. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 17 | Converter Tier 1 parsing | P2 | Provide a Talend XML node with standard KEY/VALUE elementRef structure. Verify `parse_tsetglobalvar()` extracts correct variable names and values. |
| 18 | Converter Tier 2 fallback | P2 | Provide a Talend XML node with TABLE/row/cell structure. Verify Tier 2 extracts correctly. |
| 19 | Converter Tier 3 fallback | P2 | Provide a Talend XML node with Java declarations in elementParameter values. Verify Tier 3 extracts correctly with param name as variable name. |
| 20 | Converter empty variables | P2 | Provide a Talend XML node with empty VARIABLES table. Verify warning is logged and empty list is stored. |
| 21 | _validate_config() correctness | P2 | Directly call `_validate_config()` with various malformed configs. Verify correct error messages are returned. (Blocked by dead code -- method is never called.) |
| 22 | Sensitive value logging | P2 | Set a variable with `name="db_password"` and `value="secret123"`. Verify DEBUG log does not expose the value (or that logging is appropriately gated). |
| 23 | NaN value handling | P2 | Set `value=float('nan')`. Verify it is stored in globalMap. Verify downstream `global_map.get()` returns NaN (not crash). |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-SGV-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. Variables are set correctly in `_process()`, but the subsequent stats update in `execute()` crashes. |
| BUG-SGV-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. Prevents any downstream component from reading variables set by `SetGlobalVar`. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-SGV-001 | Testing | Zero v1 unit tests. All 153 lines of engine code and 93 lines of converter parser code are unverified. The component's core purpose (setting globalMap variables) is never tested. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-SGV-001 | Converter | No `{{java}}` expression marking on VARIABLES values. Java expressions beyond `"new "` prefix are stored as raw strings. Engine's `_resolve_java_expressions()` cannot detect them. |
| CONV-SGV-002 | Converter | No context variable wrapping (`${...}`) for VARIABLES values. `resolve_dict()` does NOT recurse into dicts nested inside lists (context_manager.py:156-157). Since VARIABLES is a list of dicts, context references are DEFINITIVELY unreachable and will never be resolved at runtime. |
| ENG-SGV-002 | Engine | Incomplete Java expression support. Only `"new "` prefix detected. Misses concatenations, method calls, ternary, globalMap references, context references. |
| ENG-SGV-003 | Engine | No `die_on_error` support. All exceptions propagate unconditionally. Should support graceful degradation. |
| ENG-SGV-004 | Engine | NB_LINE always 0. Does not count input rows that pass through or variables set. May break downstream NB_LINE-based monitoring. |
| BUG-SGV-003 | Bug | `_validate_config()` is dead code -- never called by any code path. 28 lines of unreachable validation. |
| BUG-SGV-004 | Bug | `global_map.put()` called without null-check on `self.global_map`. If globalMap is None, AttributeError crashes component. |
| BUG-SGV-008 | Bug | `resolve_dict()` does NOT recurse into dicts nested inside lists (context_manager.py:156-157). VARIABLES is a list of dicts -- context references in variable values are definitively unreachable. Confirmed, not speculative. |
| SEC-SGV-001 | Security | Arbitrary Java code execution via `"new "` prefix detection with overly broad matching. Value `"new record created"` would be sent to Java bridge for evaluation. |
| STD-SGV-001 | Standards | `_validate_config()` exists but is never called. Dead validation code. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-SGV-003 | Converter | Tier 3 fallback uses parameter NAME as variable name. May produce incorrect globalMap keys. |
| CONV-SGV-004 | Converter | `CONNECTION_FORMAT` not extracted. Other components consistently extract this. |
| ENG-SGV-005 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap on error. Downstream error handlers cannot access error details. |
| BUG-SGV-005 | Bug | Empty `var_name` skipped silently without logging warning. May mask converter bugs. |
| BUG-SGV-006 | Bug | NaN/None values stored in globalMap without conversion or warning. |
| BUG-SGV-009 | Bug (Converter) | Tier 3 skip list incomplete (component_parser.py:2718). Only skips VARIABLES/UNIQUE_NAME/CONNECTION_FORMAT. Standard params like PROPERTY_TYPE, LABEL with `'new '` in value get picked up as spurious variables. |
| BUG-SGV-010 | Bug (Converter) | Converter `strip('\"')` is greedy (line 2660). Removes ALL quotes from both ends, not just one pair. Multi-quoted values like `""value""` get corrupted. |
| NAME-SGV-001 | Naming | Config key `VARIABLES` uses UPPER_CASE instead of snake_case convention. |
| NAME-SGV-002 | Naming | Variable dict uses `name`/`value` instead of Talend's `key`/`value`. Semantic mismatch. |
| SEC-SGV-002 | Security | No validation that user-defined variable names don't collide with `{id}_{STAT}` pattern. Could overwrite component statistics. |
| STD-SGV-002 | Standards | `VARIABLES` config key violates snake_case convention. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-SGV-005 | Converter | No validation of KEY format after `.strip('"')`. Empty keys pass through silently. |
| ENG-SGV-006 | Engine | Component misclassified in `file` package instead of `custom_code` or `misc`. |
| STD-SGV-003 | Standards | Unused `import pandas as pd`. Component does not use pandas. |
| PERF-SGV-001 | Performance | Unused pandas import adds ~150ms overhead on first import. |
| NAME-SGV-003 | Naming | Component in `file` package instead of `custom_code`. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 10 | 2 converter, 3 engine, 3 bugs (incl. context_manager resolve_dict), 1 security, 1 standards |
| P2 | 11 | 2 converter, 1 engine, 4 bugs, 2 naming, 1 security, 1 standards |
| P3 | 5 | 1 converter, 1 engine, 1 standards, 1 performance, 1 naming |
| **Total** | **29** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-SGV-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-SGV-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-SGV-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: simple string variables, pass-through with DataFrame, pass-through with None, empty VARIABLES list, missing VARIABLES config, globalMap retrieval, and statistics tracking. Without these, no v1 engine behavior is verified.

4. **Add globalMap null-check** (BUG-SGV-004): At the top of `_process()`, add:
   ```python
   if self.global_map is None:
       logger.error(f"[{self.id}] Cannot set global variables: globalMap is None")
       raise ComponentExecutionError(self.id, "globalMap is required for SetGlobalVar")
   ```

### Short-Term (Hardening)

5. **Add `{{java}}` marking in converter** (CONV-SGV-001): After parsing variables in `parse_tsetglobalvar()`, iterate the parsed variables list and call `self.expr_converter.mark_java_expression(value)` on each value. Also check for `context.` references and wrap with `${...}`. This aligns the dedicated parser with the generic expression handling in `parse_base_component()`.

6. **Improve engine Java expression detection** (ENG-SGV-002): Replace the ad-hoc `"new "` prefix check with a proper expression detection method. Check for `{{java}}` prefix (set by converter), context variable patterns, globalMap references, and common Java expression operators. Alternatively, remove the ad-hoc detection entirely and rely on the converter's `{{java}}` marking plus the base class `_resolve_java_expressions()` method, which already handles `{{java}}` markers correctly.

7. **Wire up `_validate_config()`** (BUG-SGV-003, STD-SGV-001): Add a call to `_validate_config()` at the beginning of `_process()`:
   ```python
   errors = self._validate_config()
   if errors:
       error_msg = "; ".join(errors)
       logger.error(f"[{self.id}] Configuration validation failed: {error_msg}")
       raise ConfigurationError(f"[{self.id}] {error_msg}")
   ```

8. **Add `die_on_error` support** (ENG-SGV-003): Wrap the per-variable processing in a try/except that checks `die_on_error`:
   ```python
   die_on_error = self.config.get('die_on_error', True)
   for variable in variables:
       try:
           # ... existing variable setting logic ...
       except Exception as e:
           if die_on_error:
               raise
           logger.warning(f"[{self.id}] Failed to set variable {var_name}: {e}")
   ```

9. **Fix NB_LINE tracking** (ENG-SGV-004): Count input rows if data is a DataFrame:
   ```python
   rows_processed = len(data) if isinstance(data, pd.DataFrame) else 0
   self._update_stats(rows_processed, rows_processed, 0)
   ```

10. **Add empty name warning** (BUG-SGV-005): When `var_name` is falsy, log a warning:
    ```python
    if not var_name:
        logger.warning(f"[{self.id}] Skipping variable at index {i}: name is empty or None")
        continue
    ```

11. **Tighten "new " detection** (SEC-SGV-001): Replace `var_value.strip().startswith("new ")` with a regex pattern that matches Java constructor calls: `re.match(r'^new\s+[a-zA-Z_][\w.]*\s*\(', var_value.strip())`. This prevents false positives like `"new record created"`.

### Long-Term (Optimization)

12. **Move to `custom_code` package** (ENG-SGV-006, NAME-SGV-003): Create `src/v1/engine/components/custom_code/` and move `set_global_var.py` there. Update imports in `engine.py` and `__init__.py`.

13. **Remove unused pandas import** (STD-SGV-003, PERF-SGV-001): Remove `import pandas as pd` from line 13. The component does not use pandas.

14. **Normalize config key to snake_case** (NAME-SGV-001, STD-SGV-002): Change converter to store as `variables` instead of `VARIABLES`. Update engine to read `self.config.get("variables", [])`. This aligns with other components' conventions.

15. **Add sensitive value masking** (logging concern): For DEBUG-level variable value logging, consider masking values whose names match patterns like `password`, `secret`, `key`, `token`, `credential`:
    ```python
    display_value = "***MASKED***" if any(s in var_name.lower() for s in ['password', 'secret', 'key', 'token']) else var_value
    logger.debug(f"[{self.id}] Set global variable: {var_name} = {display_value}")
    ```

16. **Implement `{id}_ERROR_MESSAGE` in globalMap** (ENG-SGV-005): In the base class `execute()` error handler (line 228-234), add:
    ```python
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
    ```

17. **Add stat name collision detection** (SEC-SGV-002): Before calling `global_map.put(var_name, ...)`, check if the key matches the component stats pattern:
    ```python
    import re
    if re.match(r'^[a-zA-Z]+_\d+_(NB_LINE|NB_LINE_OK|NB_LINE_REJECT|EXECUTION_TIME|ERROR_MESSAGE)$', var_name):
        logger.warning(f"[{self.id}] Variable name '{var_name}' may collide with component statistics keys")
    ```

---

## Appendix A: Converter Parser Code

```python
# component_parser.py lines 2644-2736
def parse_tsetglobalvar(self, node, component: Dict) -> Dict:
    """Parse tSetGlobalVar specific configuration"""
    variables = []

    # Tier 1: Parse VARIABLES table parameter - KEY/VALUE elementRef pairs
    for param in node.findall('.//elementParameter[@name="VARIABLES"]'):
        element_values = param.findall('.//elementValue')
        if element_values:
            current_key = None
            current_value = None
            for elem in element_values:
                element_ref = elem.get('elementRef', '')
                element_value = elem.get('value', '').strip('"')
                if element_ref == 'KEY':
                    if current_key is not None and current_value is not None:
                        variables.append({'name': current_key, 'value': current_value})
                    current_key = element_value
                    current_value = None
                elif element_ref == 'VALUE':
                    current_value = element_value
                    if current_key is not None:
                        variables.append({'name': current_key, 'value': current_value})
                        current_key = None
                        current_value = None
            if current_key is not None and current_value is not None:
                variables.append({'name': current_key, 'value': current_value})

    # Tier 2: Fallback TABLE/row/cell structure
    if not variables:
        for table in node.findall(".//elementParameter[@name='VARIABLES']/TABLE"):
            for row in table.findall("./row"):
                var_name = ""
                var_value = ""
                for cell in row.findall("./cell"):
                    column_name = cell.get('columnName', '')
                    if column_name in ['KEY', 'NAME', 'VARIABLE_NAME']:
                        var_name = cell.text or cell.get('value', '')
                    elif column_name in ['VALUE', 'VARIABLE_VALUE']:
                        var_value = cell.text or cell.get('value', '')
                if var_name:
                    variables.append({'name': var_name.strip('"'), 'value': var_value.strip('"')})

    # Tier 3: Fallback Java declaration scan
    if not variables:
        for param in node.findall('.//elementParameter'):
            param_name = param.get('name', '')
            param_value = param.get('value', '').strip('"')
            if param_name in ['VARIABLES', 'UNIQUE_NAME', 'CONNECTION_FORMAT']:
                continue
            if param_value and ('java.util.' in param_value or 'new ' in param_value):
                variables.append({'name': param_name, 'value': param_value})

    component['config']['VARIABLES'] = variables
    return component
```

**Notes on this code**:
- Line 2660: `.strip('"')` handles Talend's XML-escaped quote characters
- Line 2700: Tier 2 handles three different key column names: `KEY`, `NAME`, `VARIABLE_NAME` -- indicating different Talend versions or export formats
- Line 2722: Tier 3's Java detection (`'java.util.' in param_value or 'new ' in param_value`) is a heuristic that could match non-variable parameters
- Lines 2731-2734: Logging uses `[TSetGlobalVar]` prefix instead of `[{component_id}]` -- inconsistent with other parsers

---

## Appendix B: Engine Class Structure

```
SetGlobalVar (BaseComponent)
    Imports:
        logging, typing (Any, Dict, List, Optional)
        pandas as pd     # UNUSED -- should be removed
        BaseComponent

    Methods:
        _validate_config() -> List[str]          # DEAD CODE -- never called
        _process(data: Any = None) -> Dict[str, Any]   # Main entry point

    _process() flow:
        1. Log start
        2. Get VARIABLES from config (default [])
        3. For each variable:
           a. Get name and value
           b. If name is truthy:
              - If value starts with "new " AND context_manager has get_java_bridge:
                - Try Java bridge evaluation
                - On success: store evaluated result in globalMap
                - On failure: log warning, store raw string in globalMap
              - Else if no Java bridge:
                - Store raw string in globalMap
              - Else (not "new " prefix):
                - Store raw string in globalMap
              - Increment variables_set counter
        4. _update_stats(0, 0, 0)
        5. Log completion with variables_set count
        6. Return {"main": data}
        7. On any exception: log error, re-raise
```

---

## Appendix C: Complete Talend Parameter to V1 Config Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `VARIABLES` (table) | `VARIABLES` (list of dicts) | Mapped | -- |
| `CONNECTION_FORMAT` | -- | **Not Mapped** | P2 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix D: Base Class Interaction Analysis

### execute() Flow (base_component.py lines 188-234)

```
execute(input_data)
    1. Set status = RUNNING
    2. Record start_time
    3. If java_bridge: _resolve_java_expressions()     # Resolves {{java}} markers
    4. If context_manager: config = resolve_dict(config) # Resolves ${context.var}
    5. Determine execution mode (HYBRID -> auto-select)
    6. Execute based on mode (BATCH or STREAMING)
       -> Calls _process(input_data)                    # SetGlobalVar._process()
    7. Update EXECUTION_TIME stat
    8. _update_global_map()                              # CRASHES due to BUG-SGV-001
    9. Set status = SUCCESS
    10. Return result with stats
    ON ERROR:
    a. Set status = ERROR
    b. Set error_message
    c. Update EXECUTION_TIME
    d. _update_global_map()                              # ALSO CRASHES
    e. Log error
    f. Re-raise
```

**Critical observation**: Step 3 (`_resolve_java_expressions()`) resolves `{{java}}` markers in config BEFORE `_process()` is called. This means if the converter had properly marked variable values with `{{java}}`, they would be resolved by the base class before `_process()` even runs. The ad-hoc `"new "` detection in `_process()` would then be unnecessary -- it exists only because the converter does not mark these values.

### _update_global_map() Analysis (base_component.py lines 298-304)

```python
def _update_global_map(self) -> None:
    if self.global_map:
        for stat_name, stat_value in self.stats.items():
            self.global_map.put_component_stat(self.id, stat_name, stat_value)
        logger.info(f"... {stat_name}: {value}")  # BUG: 'value' is undefined
```

The `for` loop iterates `self.stats.items()`, binding `stat_name` and `stat_value`. The log statement after the loop references `{stat_name}` (valid -- retains last loop value) and `{value}` (INVALID -- undefined variable). This crashes with `NameError: name 'value' is not defined`.

**Impact on SetGlobalVar**: The user-defined variables are set correctly in `_process()` via `self.global_map.put()`. But after `_process()` returns, `execute()` calls `_update_global_map()` which crashes. This means:
1. Variables ARE stored in globalMap (correct)
2. Component statistics (NB_LINE, etc.) attempt to be stored but crash during logging
3. Component status is never set to SUCCESS (stays RUNNING)
4. The exception propagates up from `execute()`, making the component appear to have failed
5. If the caller catches the exception, the variables are actually available in globalMap despite the "failure"

### GlobalMap.get() Analysis (global_map.py lines 26-28)

```python
def get(self, key: str) -> Optional[Any]:
    return self._map.get(key, default)  # BUG: 'default' is undefined
```

**Impact on SetGlobalVar**: `SetGlobalVar._process()` only uses `self.global_map.put()`, which works correctly. But ANY downstream component trying to READ the variables via `global_map.get("key")` will crash. Additionally, `get_component_stat()` (line 58) calls `self.get(key, default)` with two arguments, but `get()` only accepts one positional argument, causing `TypeError`.

---

## Appendix E: Edge Case Analysis

### Edge Case 1: Empty VARIABLES list

| Aspect | Detail |
|--------|--------|
| **Talend** | No globalMap.put() calls generated. Component completes with NB_LINE=0. |
| **V1** | `self.config.get("VARIABLES", [])` returns `[]`. Loop body never executes. `_update_stats(0, 0, 0)` called. Returns `{"main": data}`. |
| **Verdict** | CORRECT (aside from BUG-SGV-001 crash in _update_global_map) |

### Edge Case 2: Missing VARIABLES config key

| Aspect | Detail |
|--------|--------|
| **Talend** | Would not occur in valid Talend XML. Component requires at least one variable row. |
| **V1** | `self.config.get("VARIABLES", [])` returns default `[]`. Same as Edge Case 1. No error. |
| **Verdict** | ACCEPTABLE -- graceful handling of missing config. Could benefit from warning log. |

### Edge Case 3: Variable with None value

| Aspect | Detail |
|--------|--------|
| **Talend** | A VALUE cell left empty in the GUI produces an empty string `""` in the XML. |
| **V1** | If converter produces `{"name": "k1"}` (no `value` key), `variable.get("value")` returns `None`. The `"new "` check (`isinstance(var_value, str)`) fails for None, so it falls to the `else` branch (line 136-138) and stores `None` in globalMap. |
| **Verdict** | PARTIAL -- Talend stores empty string, V1 stores None. Semantic difference. |

### Edge Case 4: Variable with empty string value

| Aspect | Detail |
|--------|--------|
| **Talend** | `globalMap.put("key", "")` stores an empty string. |
| **V1** | `variable.get("value")` returns `""`. The `"new "` check fails (empty string doesn't start with "new "). `global_map.put("key", "")` stores empty string. |
| **Verdict** | CORRECT |

### Edge Case 5: Variable value starting with "new " but not a Java expression

| Aspect | Detail |
|--------|--------|
| **Talend** | `globalMap.put("msg", "new record created")` stores the literal string. |
| **V1** | `"new record created".strip().startswith("new ")` is `True`. Engine sends `"new record created"` to Java bridge for evaluation, which will fail. Fallback stores the raw string. |
| **Verdict** | FUNCTIONAL but INEFFICIENT -- unnecessary Java bridge call and warning log for a non-Java value. SEC-SGV-001 covers this. |

### Edge Case 6: Variable value with context reference

| Aspect | Detail |
|--------|--------|
| **Talend** | `globalMap.put("path", context.input_dir)` evaluates the context variable. |
| **V1** | Converter does not wrap with `${...}`, so the value `context.input_dir` is stored as a raw string. Even if the converter wrapped as `${context.input_dir}`, `resolve_dict()` does NOT recurse into dicts nested inside lists (context_manager.py:156-157), so VARIABLES entries are definitively unreachable. |
| **Verdict** | GAP -- context references in VARIABLES values are definitively not resolved. CONV-SGV-002 covers this. |

### Edge Case 7: Variable value with globalMap reference

| Aspect | Detail |
|--------|--------|
| **Talend** | `globalMap.put("count_str", String.valueOf(globalMap.get("tFileInput_1_NB_LINE")))` evaluates the globalMap reference and stores the result. |
| **V1** | The expression is stored as a raw string `"String.valueOf(globalMap.get(\"tFileInput_1_NB_LINE\"))"`. Not evaluated because it does not start with `"new "`. |
| **Verdict** | GAP -- globalMap cross-references not evaluated. ENG-SGV-002 covers this. |

### Edge Case 8: NaN value in input DataFrame pass-through

| Aspect | Detail |
|--------|--------|
| **Talend** | Pass-through does not modify data. NaN values remain. |
| **V1** | `return {"main": data}` returns the DataFrame by reference. NaN values preserved unchanged. |
| **Verdict** | CORRECT |

### Edge Case 9: Large DataFrame pass-through

| Aspect | Detail |
|--------|--------|
| **Talend** | Pass-through with no processing overhead. |
| **V1** | `return {"main": data}` returns by reference. Zero copy overhead. |
| **Verdict** | CORRECT |

### Edge Case 10: globalMap is None

| Aspect | Detail |
|--------|--------|
| **Talend** | Not applicable -- globalMap is always available in Talend runtime. |
| **V1** | `self.global_map` is None. `self.global_map.put(var_name, ...)` raises `AttributeError: 'NoneType' object has no attribute 'put'`. Caught by outer except, logged, re-raised. |
| **Verdict** | GAP -- should fail fast with clear error message. BUG-SGV-004 covers this. |

### Edge Case 11: Variable name contains special characters

| Aspect | Detail |
|--------|--------|
| **Talend** | globalMap uses Java HashMap. Any string can be a key, including spaces, dots, unicode. |
| **V1** | Python dict also accepts any hashable string. `global_map.put("my.var", value)` works correctly. |
| **Verdict** | CORRECT |

### Edge Case 12: Concurrent execution (multiple SetGlobalVar in parallel subjobs)

| Aspect | Detail |
|--------|--------|
| **Talend** | globalMap is thread-safe in Talend (synchronized HashMap). Concurrent puts are safe. |
| **V1** | Python dict operations are GIL-protected for single operations. `global_map.put()` is safe for non-overlapping keys. For overlapping keys, last-write-wins (non-deterministic order). No explicit locking. |
| **Verdict** | ACCEPTABLE -- GIL provides basic thread safety. For deterministic behavior with overlapping keys, explicit ordering is needed. |

### Edge Case 13: Value is a Python expression (not Java)

| Aspect | Detail |
|--------|--------|
| **Talend** | N/A -- Talend only evaluates Java expressions. |
| **V1** | Python expressions are not evaluated. Stored as raw strings. This is correct behavior -- the component should not evaluate arbitrary expressions. |
| **Verdict** | CORRECT |

### Edge Case 14: Converter Tier 1 with KEY-KEY ordering (no VALUE between)

| Aspect | Detail |
|--------|--------|
| **Talend XML** | Unusual but possible: `<elementValue elementRef="KEY" value="k1"/><elementValue elementRef="KEY" value="k2"/><elementValue elementRef="VALUE" value="v2"/>` |
| **V1 Converter** | When second KEY is encountered, check `if current_key is not None and current_value is not None` fails because `current_value` is still None. First KEY (`k1`) is overwritten by second KEY (`k2`). Result: only `{name: "k2", value: "v2"}`. First variable is silently lost. |
| **Verdict** | GAP -- lost variable without warning. Edge case, unlikely in practice. |

### Edge Case 15: Converter Tier 1 with VALUE-VALUE ordering (no KEY between)

| Aspect | Detail |
|--------|--------|
| **Talend XML** | Malformed: `<elementValue elementRef="KEY" value="k1"/><elementValue elementRef="VALUE" value="v1"/><elementValue elementRef="VALUE" value="v2"/>` |
| **V1 Converter** | First KEY/VALUE pair saved correctly. Second VALUE: `current_key` is None (reset on line 2681), so `if current_key is not None` fails. `v2` is stored in `current_value` but never saved (no subsequent KEY to trigger save). |
| **Verdict** | ACCEPTABLE -- malformed XML handled gracefully (second value silently dropped). |

### Edge Case 16: Value containing escaped quotes

| Aspect | Detail |
|--------|--------|
| **Talend XML** | `<elementValue elementRef="VALUE" value="&quot;hello \&quot;world\&quot;&quot;"/>` -- a string with embedded quotes. |
| **V1 Converter** | `.strip('"')` on line 2660 strips outer quotes. Inner escaped quotes (`\"`) are preserved as-is. Result: `hello \"world\"`. The engine stores this raw string in globalMap. |
| **Talend** | Generated Java: `globalMap.put("key", "hello \"world\"")` -- inner quotes are escaped in Java source. At runtime, the string contains actual quote characters. |
| **Verdict** | PARTIAL -- V1 preserves escaped quote syntax as literal characters. May differ from Talend runtime behavior where Java unescapes them. |

### Edge Case 17: Value referencing another SetGlobalVar's variable

| Aspect | Detail |
|--------|--------|
| **Talend** | `VALUE = (String)globalMap.get("tSetGlobalVar_1_var1")` -- evaluates at runtime. The referenced variable must be set by a prior component. |
| **V1** | The expression is stored as the raw string `(String)globalMap.get("tSetGlobalVar_1_var1")`. Not evaluated because it does not start with `"new "` and has no `{{java}}` marking. The globalMap will contain the raw expression string, not the resolved value. |
| **Verdict** | GAP -- cross-variable references not evaluated. ENG-SGV-002 covers this. |

### Edge Case 18: Value with arithmetic expression

| Aspect | Detail |
|--------|--------|
| **Talend** | `VALUE = ((Integer)globalMap.get("count")) + 1` -- evaluates to an integer. |
| **V1** | Stored as raw string. Not detected as Java expression. |
| **Verdict** | GAP -- arithmetic expressions not evaluated. |

### Edge Case 19: Component executed multiple times in iterate loop

| Aspect | Detail |
|--------|--------|
| **Talend** | Each iteration re-evaluates all VALUE expressions. If VALUE references an iteration variable (e.g., `row1.id`), each iteration stores the current row's value, overwriting the previous. |
| **V1** | `_process()` is called each iteration via the engine's iterate mechanism. Each call iterates all VARIABLES and calls `global_map.put()`. Overwrite behavior is correct. However, `_update_stats(0, 0, 0)` is called each iteration, accumulating zeros -- never reflecting actual processing. |
| **Verdict** | PARTIAL -- overwrite behavior correct, but NB_LINE tracking incorrect across iterations. |

### Edge Case 20: Value is boolean `true`/`false` (CHECK field type in XML)

| Aspect | Detail |
|--------|--------|
| **Talend** | `globalMap.put("flag", true)` stores a Java `Boolean` object. |
| **V1 Converter** | If the parameter has `field="CHECK"`, `parse_base_component()` converts it to Python `bool` (line 446). But `parse_tsetglobalvar()` extracts values via `.get('value', '').strip('"')` which always produces strings. A boolean value `"true"` is stored as the string `"true"`, not as Python `True`. |
| **Verdict** | GAP -- type mismatch. Talend stores Boolean, V1 stores string "true". Downstream comparisons (`== True` vs `== "true"`) will fail. |

### Edge Case 21: Very long variable value (multi-KB string)

| Aspect | Detail |
|--------|--------|
| **Talend** | Java strings can be up to 2GB. No practical limit for globalMap values. |
| **V1** | Python strings have no practical limit. `global_map.put()` stores by reference. No copying overhead. |
| **Verdict** | CORRECT |

### Edge Case 22: Value is numeric literal without quotes

| Aspect | Detail |
|--------|--------|
| **Talend XML** | `<elementValue elementRef="VALUE" value="42"/>` -- numeric value without quotes. |
| **V1 Converter** | `.strip('"')` is a no-op (no quotes to strip). Value stored as string `"42"`. |
| **Talend** | Generated Java: `globalMap.put("count", 42)` stores an `int` (autoboxed to `Integer`). |
| **Verdict** | GAP -- Talend stores Integer, V1 stores string "42". Type mismatch for downstream numeric operations. |

---

## Appendix F: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `SetGlobalVar`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-SGV-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-SGV-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| BUG-SGV-003 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called. ALL components with validation logic have dead validation. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix G: Implementation Fix Guides

### Fix Guide: BUG-SGV-001 -- `_update_global_map()` undefined variable

**File**: `src/v1/engine/base_component.py`
**Line**: 304

**Current code (broken)**:
```python
logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} {stat_name}: {value}")
```

**Fix**:
```python
logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']}")
```

**Explanation**: `{value}` references an undefined variable (the loop variable is `stat_value`). The `{stat_name}` reference would show only the last loop iteration value, which is misleading. Best fix is to remove both stale references.

**Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

---

### Fix Guide: BUG-SGV-002 -- `GlobalMap.get()` undefined default

**File**: `src/v1/engine/global_map.py`
**Line**: 26-28

**Current code (broken)**:
```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

**Fix**:
```python
def get(self, key: str, default: Any = None) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

**Impact**: Fixes ALL components and any code calling `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

---

### Fix Guide: BUG-SGV-004 -- globalMap null-check

**File**: `src/v1/engine/components/file/set_global_var.py`
**Line**: Insert before line 106

**Current code**:
```python
try:
    variables = self.config.get("VARIABLES", [])
```

**Fix**:
```python
try:
    if self.global_map is None:
        logger.error(f"[{self.id}] Cannot set global variables: globalMap is not configured")
        raise ComponentExecutionError(
            self.id, "globalMap is required for SetGlobalVar component"
        )

    variables = self.config.get("VARIABLES", [])
```

**Impact**: Provides clear error message instead of cryptic `AttributeError`. **Risk**: Very low (only affects the None globalMap case which already crashes).

---

### Fix Guide: CONV-SGV-001 -- Add expression marking in converter

**File**: `src/converters/complex_converter/component_parser.py`
**Line**: Insert after line 2727 (before `component['config']['VARIABLES'] = variables`)

**Fix**:
```python
# Mark Java expressions and wrap context references in variable values
for var in variables:
    if isinstance(var.get('value'), str):
        value = var['value']
        # Check for context variable references
        if 'context.' in value:
            if not self.expr_converter.detect_java_expression(value):
                var['value'] = '${' + value + '}'
            else:
                var['value'] = self.expr_converter.mark_java_expression(value)
        else:
            var['value'] = self.expr_converter.mark_java_expression(value)
```

**Impact**: Enables proper Java expression resolution and context variable substitution for all variable values. **Risk**: Medium -- requires testing with real Talend XML to ensure expression marking does not over-mark simple string values.

---

### Fix Guide: ENG-SGV-003 -- Add die_on_error support

**File**: `src/v1/engine/components/file/set_global_var.py`
**Line**: Replace lines 104-152

**Fix**:
```python
try:
    if self.global_map is None:
        raise ComponentExecutionError(self.id, "globalMap is required")

    die_on_error = self.config.get('die_on_error', True)
    variables = self.config.get("VARIABLES", [])
    variables_set = 0
    errors = []

    for i, variable in enumerate(variables):
        var_name = variable.get("name")
        var_value = variable.get("value")

        if not var_name:
            logger.warning(f"[{self.id}] Skipping variable at index {i}: name is empty")
            continue

        try:
            # ... existing Java bridge / string logic ...
            variables_set += 1
        except Exception as e:
            if die_on_error:
                raise
            errors.append(f"{var_name}: {e}")
            logger.warning(f"[{self.id}] Failed to set variable {var_name}: {e}")

    # Track input rows for NB_LINE
    rows_processed = len(data) if isinstance(data, pd.DataFrame) else 0
    self._update_stats(rows_processed, rows_processed, 0)

    logger.info(f"[{self.id}] Global variables set: {variables_set} variables")
    if errors:
        logger.warning(f"[{self.id}] {len(errors)} variable(s) failed: {errors}")

    return {"main": data}

except Exception as e:
    logger.error(f"[{self.id}] Failed to set global variables: {e}")
    raise
```

**Impact**: Adds graceful error handling, NB_LINE tracking, and per-variable error reporting. **Risk**: Medium (changes control flow).

---

### Fix Guide: SEC-SGV-001 -- Tighten Java expression detection

**File**: `src/v1/engine/components/file/set_global_var.py`
**Line**: Replace lines 115-116

**Current code**:
```python
if (isinstance(var_value, str) and
    var_value.strip().startswith("new ") and self.context_manager and
    hasattr(self.context_manager, "get_java_bridge")):
```

**Fix**:
```python
import re
if (isinstance(var_value, str) and
    re.match(r'^new\s+[a-zA-Z_][\w.]*\s*\(', var_value.strip()) and
    self.context_manager and
    hasattr(self.context_manager, "get_java_bridge")):
```

**Explanation**: The regex `^new\s+[a-zA-Z_][\w.]*\s*\(` matches `"new "` followed by a valid Java class name (with optional package path) and an opening parenthesis. This prevents false positives like `"new record created"`.

**Impact**: Eliminates false positive Java bridge calls. **Risk**: Very low (strictly narrows the matching pattern).

---

## Appendix H: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs using Java expressions in VALUES (beyond "new " constructors) | **Critical** | Any job with concatenations, method calls, globalMap refs in VALUES | Must fix CONV-SGV-001 and ENG-SGV-002 to properly mark and resolve Java expressions |
| Jobs where downstream reads globalMap variables | **Critical** | Any job using `globalMap.get()` to read SetGlobalVar values | Must fix BUG-SGV-002 (GlobalMap.get() crash) |
| Any job using SetGlobalVar with globalMap enabled | **Critical** | All jobs with globalMap | Must fix BUG-SGV-001 (_update_global_map() crash) |
| Jobs using context variables in VALUES | **High** | Jobs with `context.var` in variable values | Must fix CONV-SGV-002 to wrap context refs |
| Jobs checking NB_LINE for flow monitoring | **Medium** | Jobs using `{id}_NB_LINE` from SetGlobalVar | Fix ENG-SGV-004 to track input row count |

### Medium-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs storing numeric values (e.g., `42`, `3.14`) | **Medium** | Any job expecting Integer/Float in globalMap | V1 stores as string. Downstream casting may fail or produce unexpected results. |
| Jobs storing boolean values (`true`/`false`) | **Medium** | Any job comparing globalMap values to boolean | V1 stores as string "true"/"false" instead of Python bool. `== True` comparisons will fail. |
| Jobs with `die_on_error=false` on SetGlobalVar | **Medium** | Jobs requiring graceful error handling | V1 propagates all exceptions unconditionally. Fix ENG-SGV-003. |
| Jobs using SetGlobalVar in iterate loops with row references | **Medium** | Jobs with `tFlowToIterate -> tSetGlobalVar` | Row field references in VALUES not evaluated. All iterations store the same raw expression string. |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs with only simple string literal VALUES | Low | Core functionality works correctly |
| Jobs using SetGlobalVar as standalone (no input) | Low | Pass-through with None works correctly |
| Jobs with `new java.util.Date()` or similar constructors | Low-Medium | Works when Java bridge is available; falls back to string otherwise |
| Jobs where SetGlobalVar has no downstream globalMap reads | Low | Variables are set but never read. No functional impact from BUG-SGV-002. |
| Jobs with only 1-2 variables | Low | Linear iteration. No performance concern. |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (cross-cutting BUG-SGV-001 and BUG-SGV-002). These block ALL component execution, not just SetGlobalVar.
2. **Phase 2**: Audit each target job's `tSetGlobalVar` configuration. Identify which VALUE patterns are used (simple strings, constructors, complex expressions, context refs).
3. **Phase 3**: For jobs with only simple string VALUES, migrate immediately after Phase 1 fixes.
4. **Phase 4**: Implement converter `{{java}}` marking (CONV-SGV-001) and context wrapping (CONV-SGV-002) for jobs with complex expressions.
5. **Phase 5**: Parallel-run migrated jobs against Talend originals. Verify globalMap contents match after each SetGlobalVar execution.

---

## Appendix I: Comparison with Other Variable-Setting Components

| Feature | tSetGlobalVar (V1) | tJava (V1) | tContextLoad (V1) |
|---------|---------------------|------------|---------------------|
| Set globalMap variables | **Yes** (dedicated) | Yes (via code) | No (sets context) |
| Java expression evaluation | Partial ("new " only) | Yes (full) | N/A |
| Pass-through data | **Yes** | **Yes** | N/A |
| Die on error | **No** | Yes | Yes |
| _validate_config() called | **No** (dead code) | N/A | Unknown |
| globalMap null-check | **No** | N/A | N/A |
| V1 Unit tests | **No** | **No** | **No** |
| Expression marking in converter | **No** | N/A | N/A |

**Observation**: The dead `_validate_config()` and lack of `die_on_error` support appear to be patterns shared across multiple v1 components. The missing expression marking in the converter is specific to `tSetGlobalVar` because it has a dedicated parser that bypasses the generic expression handling.

---

## Appendix J: Detailed Converter-to-Engine Data Flow

The following traces the complete path from Talend XML to runtime execution for a `tSetGlobalVar` component with two variables:

### Talend XML (Input)
```xml
<node componentName="tSetGlobalVar" componentVersion="0.101" offsetLabelX="0" offsetLabelY="0" posX="384" posY="192">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="tSetGlobalVar_1"/>
  <elementParameter field="TABLE" name="VARIABLES">
    <elementValue elementRef="KEY" value="&quot;batch_id&quot;"/>
    <elementValue elementRef="VALUE" value="&quot;BATCH_001&quot;"/>
    <elementValue elementRef="KEY" value="&quot;process_date&quot;"/>
    <elementValue elementRef="VALUE" value="new java.util.Date()"/>
  </elementParameter>
  <elementParameter field="TEXT" name="CONNECTION_FORMAT" value="row"/>
</node>
```

### Step 1: parse_base_component() processes raw parameters

```python
config_raw = {
    'CONNECTION_FORMAT': 'row',
    'VARIABLES': True  # or some value from the field="TABLE" attribute
}
# mark_java_expression() runs on config_raw values
# CONNECTION_FORMAT='row' is not marked (no Java expression)
# VARIABLES table is NOT parsed here -- only the elementParameter attribute
```

### Step 2: _map_component_parameters() falls through

```python
# component_type='tSetGlobalVar' hits the else branch
return config_raw  # Returns {'CONNECTION_FORMAT': 'row', ...}
```

### Step 3: parse_tsetglobalvar() extracts VARIABLES

```python
# Tier 1: Finds elementValue entries
# Extracts: [
#   {'name': 'batch_id', 'value': 'BATCH_001'},
#   {'name': 'process_date', 'value': 'new java.util.Date()'}
# ]
# Note: .strip('"') removes outer quotes from XML values
# Note: NO mark_java_expression() called on values
component['config']['VARIABLES'] = variables
```

### Step 4: Final v1 JSON config

```json
{
  "id": "tSetGlobalVar_1",
  "type": "SetGlobalVar",
  "config": {
    "CONNECTION_FORMAT": "row",
    "VARIABLES": [
      {"name": "batch_id", "value": "BATCH_001"},
      {"name": "process_date", "value": "new java.util.Date()"}
    ]
  }
}
```

### Step 5: Engine execution

1. `execute()` calls `_resolve_java_expressions()` -- scans config for `{{java}}` markers. Finds NONE (converter did not mark).
2. `execute()` calls `context_manager.resolve_dict(config)` -- resolves `${context.var}` patterns. Even if present, `resolve_dict()` does NOT recurse into dicts nested inside lists (BUG-SGV-008), so VARIABLES entries are unreachable.
3. `execute()` calls `_process(input_data)`
4. `_process()` iterates VARIABLES:
   - `batch_id`: value `"BATCH_001"` does not start with `"new "`. Stored as string in globalMap.
   - `process_date`: value `"new java.util.Date()"` DOES start with `"new "`. Java bridge is invoked. If successful, stores evaluated Date. If not, stores raw string.
5. `_update_stats(0, 0, 0)` -- all zeros
6. Returns `{"main": input_data}`
7. Back in `execute()`: `_update_global_map()` CRASHES (BUG-SGV-001)

---

## Appendix K: Recommended Dedicated Parser Improvement

The following is the recommended replacement for the `parse_tsetglobalvar()` method that addresses CONV-SGV-001 (missing expression marking) and CONV-SGV-002 (missing context wrapping):

```python
def parse_tsetglobalvar(self, node, component: Dict) -> Dict:
    """
    Parse tSetGlobalVar specific configuration from Talend XML node.

    Extracts the VARIABLES table using a three-tier fallback strategy:
    1. Standard KEY/VALUE elementRef pairs
    2. TABLE/row/cell structure (older Talend versions)
    3. Java declaration scan (non-standard configurations)

    After extraction, values are processed for:
    - Java expression marking ({{java}} prefix)
    - Context variable wrapping (${context.var})

    Talend Parameters:
        VARIABLES (table): KEY/VALUE pairs. Core parameter.
        CONNECTION_FORMAT (str): Connection format. Default "row".
    """
    variables = []

    # --- Tier 1, 2, 3 extraction (unchanged) ---
    # ... existing three-tier parsing ...

    # --- NEW: Expression processing on extracted values ---
    for var in variables:
        value = var.get('value', '')
        if isinstance(value, str) and value:
            # Check for context variable references
            if 'context.' in value:
                if not self.expr_converter.detect_java_expression(value):
                    # Simple context reference
                    var['value'] = '${' + value + '}'
                else:
                    # Java expression containing context reference
                    var['value'] = self.expr_converter.mark_java_expression(value)
            else:
                # Check for other Java expressions
                var['value'] = self.expr_converter.mark_java_expression(value)

    # Extract CONNECTION_FORMAT
    connection_format = 'row'
    for param in node.findall('.//elementParameter[@name="CONNECTION_FORMAT"]'):
        connection_format = param.get('value', 'row')
        break

    component['config']['VARIABLES'] = variables
    component['config']['connection_format'] = connection_format

    # Debug output
    if variables:
        self.logger.info(
            f"[{component.get('id', 'unknown')}] "
            f"Parsed {len(variables)} tSetGlobalVar variable(s)"
        )
    else:
        self.logger.warning(
            f"[{component.get('id', 'unknown')}] "
            f"No variables found in tSetGlobalVar component"
        )

    return component
```

**Key improvements**:
1. Expression marking applied to all variable values after extraction
2. Context variable wrapping for simple `context.` references
3. `CONNECTION_FORMAT` extracted (addresses CONV-SGV-004)
4. Log messages use component ID instead of hardcoded `[TSetGlobalVar]`
5. Values are checked for Java expressions using the same logic as `parse_base_component()`

---

## Appendix L: Complete Code Listing with Line-by-Line Annotations

### set_global_var.py (Engine)

| Lines | Description | Issues |
|-------|-------------|--------|
| 1-9 | Module docstring | Correct |
| 10-11 | Imports: logging, typing | Correct |
| 13 | `import pandas as pd` | **STD-SGV-003**: Unused import |
| 15 | `from ...base_component import BaseComponent` | Correct relative import |
| 17 | `logger = logging.getLogger(__name__)` | Correct module-level logger |
| 20-57 | Class docstring | Documents VARIABLES config, pass-through behavior, stats. Accurate. |
| 59-87 | `_validate_config()` | **BUG-SGV-003**: Never called. Logic is correct: checks VARIABLES presence, type, and entry structure. |
| 89-152 | `_process()` | Main logic. See detailed analysis in Appendix B. |
| 102 | `logger.info(f"[{self.id}] Setting global variables")` | Correct start logging |
| 106 | `self.config.get("VARIABLES", [])` | Safe default. **NAME-SGV-001**: UPPER_CASE key. |
| 107 | `variables_set = 0` | Counter for logging |
| 109-141 | Variable iteration loop | Core logic. See Edge Case Analysis. |
| 113 | `if var_name:` | **BUG-SGV-005**: No warning for falsy name. |
| 115-116 | `"new "` detection | **SEC-SGV-001**: Overly broad pattern. **ENG-SGV-002**: Misses other expression types. |
| 117 | `hasattr(self.context_manager, "get_java_bridge")` | Fragile API coupling |
| 120-131 | Java bridge evaluation with fallback | Correct try/except pattern for Java bridge |
| 125, 130, 134, 138 | `self.global_map.put(...)` | **BUG-SGV-004**: No null-check on global_map |
| 144 | `self._update_stats(0, 0, 0)` | **ENG-SGV-004**: Hardcoded zeros, should count input rows |
| 148 | `return {"main": data}` | Correct pass-through |
| 150-152 | Outer exception handler | **ENG-SGV-003**: No die_on_error support. Bare `raise`. |

### component_parser.py parse_tsetglobalvar() (Converter)

| Lines | Description | Issues |
|-------|-------------|--------|
| 2644-2645 | Method signature and docstring | Minimal docstring |
| 2646 | `variables = []` | Accumulator |
| 2649 | XPath: `.//elementParameter[@name="VARIABLES"]` | **Note**: Uses `.//` (descendant search) instead of `./` (direct child). Could match nested elements in complex XML. |
| 2651 | `param.findall('.//elementValue')` | Gets all elementValue descendants |
| 2653-2689 | **Tier 1**: KEY/VALUE pair parsing | Correct for standard format. See Edge Case 14-15 for ordering issues. |
| 2660 | `.strip('"')` | Handles Talend XML quoting |
| 2691-2709 | **Tier 2**: TABLE/row/cell fallback | Handles alternate XML structures. Accepts multiple column name variants. |
| 2711-2726 | **Tier 3**: Java declaration scan | **CONV-SGV-003**: Uses param NAME as variable name. Heuristic-based. |
| 2718 | Skip filter: `['VARIABLES', 'UNIQUE_NAME', 'CONNECTION_FORMAT']` | Correct exclusion list |
| 2722 | `'java.util.' in param_value or 'new ' in param_value` | Heuristic Java detection |
| 2728 | `component['config']['VARIABLES'] = variables` | Stores extracted variables. **CONV-SGV-001**: No expression marking. |
| 2730-2734 | Debug logging | Uses `[TSetGlobalVar]` prefix instead of component ID |

---

## Appendix M: _validate_config() Dead Code Analysis

The `_validate_config()` method (lines 59-87 of `set_global_var.py`) contains comprehensive validation logic that is never executed. Here is the complete analysis of what it validates and what would be caught if it were wired up:

### Validation Rules Implemented

| Rule | Lines | Check | Error Message |
|------|-------|-------|---------------|
| VARIABLES presence | 69-70 | `"VARIABLES" not in self.config` | `"Missing required config: 'VARIABLES'"` |
| VARIABLES is list | 73-74 | `not isinstance(variables, list)` | `"Config 'VARIABLES' must be a list"` |
| Entry is dict | 77-78 | `not isinstance(variable, dict)` | `"Variable at index {i} must be a dictionary"` |
| Entry has name | 81-82 | `"name" not in variable or not variable["name"]` | `"Variable at index {i} missing required 'name' field"` |
| Entry has value | 84-85 | `"value" not in variable` | `"Variable at index {i} missing required 'value' field"` |

### Validation Gaps (Not Checked)

| Missing Check | Description | Impact |
|---------------|-------------|--------|
| Name type | No check that `name` is a string | Dict or int name would cause TypeError in `global_map.put()` |
| Name whitespace | No check for leading/trailing whitespace | `" key "` would create a key that is hard to reference |
| Name collision | No check against component stat key pattern | Could overwrite NB_LINE etc. (SEC-SGV-002) |
| Value type | No check on value type | Non-serializable values could cause issues |
| Duplicate names | No check for duplicate names in the list | Last value wins silently |

### Why It Is Dead Code

The `_validate_config()` method follows the contract pattern defined in other v1 components (returns `List[str]` of error messages). However:

1. `BaseComponent.__init__()` does not call `_validate_config()` on any child class
2. `BaseComponent.execute()` does not call `_validate_config()` before `_process()`
3. `SetGlobalVar.__init__()` is not overridden (uses base class constructor)
4. `SetGlobalVar._process()` does not call `_validate_config()`

The base class defines `_validate_config()` as a conceptual contract but provides no enforcement mechanism. Each child component implements it (or not), and none are called. This is a cross-cutting architectural gap affecting ALL v1 components.

### Recommendation

Wire up validation by either:

**Option A**: Add to `BaseComponent.execute()` (recommended -- fixes all components):
```python
def execute(self, input_data=None):
    self.status = ComponentStatus.RUNNING
    # Validate configuration first
    if hasattr(self, '_validate_config'):
        errors = self._validate_config()
        if errors:
            error_msg = "; ".join(errors)
            raise ConfigurationError(f"[{self.id}] {error_msg}")
    # ... rest of execute() ...
```

**Option B**: Add to `SetGlobalVar._process()` (component-specific fix):
```python
def _process(self, data=None):
    errors = self._validate_config()
    if errors:
        raise ConfigurationError(f"[{self.id}] " + "; ".join(errors))
    # ... rest of _process() ...
```

---

## Appendix N: GlobalMap Integration Tracing

This appendix traces the complete lifecycle of a global variable from SetGlobalVar through to downstream consumption, highlighting all failure points.

### Success Path (With Bug Fixes Applied)

```
1. SetGlobalVar._process():
   -> global_map.put("batch_id", "BATCH_001")
   -> GlobalMap._map["batch_id"] = "BATCH_001"
   -> logger.debug("GlobalMap: Set batch_id = BATCH_001")

2. SetGlobalVar._process() returns:
   -> {"main": input_data}

3. BaseComponent.execute():
   -> _update_global_map()
   -> global_map.put_component_stat("tSetGlobalVar_1", "NB_LINE", 0)
   -> GlobalMap._map["tSetGlobalVar_1_NB_LINE"] = 0
   -> Component status = SUCCESS

4. Downstream component (e.g., tJava):
   -> global_map.get("batch_id")
   -> GlobalMap._map.get("batch_id", None)
   -> Returns "BATCH_001"
```

### Actual Path (With Current Bugs)

```
1. SetGlobalVar._process():
   -> global_map.put("batch_id", "BATCH_001")    # SUCCESS
   -> GlobalMap._map["batch_id"] = "BATCH_001"    # Variable IS stored

2. SetGlobalVar._process() returns:
   -> {"main": input_data}                         # SUCCESS

3. BaseComponent.execute():
   -> _update_global_map()
   -> for stat_name, stat_value in self.stats.items():
   ->     global_map.put_component_stat(...)        # SUCCESS for each stat
   -> logger.info(f"... {stat_name}: {value}")     # CRASH: NameError: 'value' undefined
   -> Exception propagates up
   -> Component status stays RUNNING (never reaches SUCCESS)
   -> execute() catches exception on line 227
   -> Sets status = ERROR
   -> Calls _update_global_map() AGAIN on line 231
   -> CRASHES AGAIN with same NameError
   -> Re-raises the original NameError

4. Downstream component (e.g., tJava):
   -> global_map.get("batch_id")
   -> return self._map.get(key, default)           # CRASH: NameError: 'default' undefined
   -> Variable is in the dict but CANNOT be retrieved
```

### Key Insight

The variable IS successfully stored in `GlobalMap._map` (step 1 succeeds). The crash in step 3 happens AFTER the put succeeds. And the crash in step 4 is a separate bug in `GlobalMap.get()`. If both bugs were fixed, the system would work correctly for simple string values.

### GlobalMap Internal State After SetGlobalVar (Before Crash)

```python
GlobalMap._map = {
    "batch_id": "BATCH_001",        # Set by SetGlobalVar._process()
    "process_date": "new java.util.Date()",  # Or evaluated Date if Java bridge worked
    # The following may or may not be set depending on how far _update_global_map() got:
    "tSetGlobalVar_1_NB_LINE": 0,
    "tSetGlobalVar_1_NB_LINE_OK": 0,
    "tSetGlobalVar_1_NB_LINE_REJECT": 0,
    # ... (crash may happen partway through stats iteration)
}
GlobalMap._component_stats = {
    "tSetGlobalVar_1": {
        "NB_LINE": 0,
        "NB_LINE_OK": 0,
        # ... (partial depending on crash timing)
    }
}
```

---

## Appendix O: Component Lifecycle Sequence Diagram

```
caller                  SetGlobalVar           BaseComponent          GlobalMap          JavaBridge
  |                         |                      |                     |                   |
  |-- execute(data) ------->|                      |                     |                   |
  |                         |-- status=RUNNING --->|                     |                   |
  |                         |                      |                     |                   |
  |                         |-- resolve_java() --->|                     |                   |
  |                         |   (scans for {{java}} markers)             |                   |
  |                         |   (finds NONE -- converter didn't mark)    |                   |
  |                         |<- (no changes) ------|                     |                   |
  |                         |                      |                     |                   |
  |                         |-- resolve_context -->|                     |                   |
  |                         |   (resolves ${context.var} in config)      |                   |
  |                         |<- (resolved config) -|                     |                   |
  |                         |                      |                     |                   |
  |                         |-- _process(data) --->|                     |                   |
  |                         |   for each variable:                       |                   |
  |                         |     if "new " prefix:                      |                   |
  |                         |       |-- get_java_bridge() ---------------------------------->|
  |                         |       |<- bridge ref ------------------------------------------|
  |                         |       |-- execute_one_time_expression(expr) ------------------>|
  |                         |       |<- evaluated_value ------------------------------------|
  |                         |       |-- put(name, evaluated) ----------->|                   |
  |                         |     else:                                  |                   |
  |                         |       |-- put(name, raw_string) --------->|                   |
  |                         |                      |                     |                   |
  |                         |   _update_stats(0,0,0)                     |                   |
  |                         |   return {"main": data}                    |                   |
  |                         |                      |                     |                   |
  |                         |-- _update_global_map() -->                 |                   |
  |                         |   for stat in stats:                       |                   |
  |                         |     put_component_stat(...) ------------->|                   |
  |                         |   logger.info(... {value})    CRASH!       |                   |
  |                         |                      |                     |                   |
  |<- NameError ------------|                      |                     |                   |
```

---

## Appendix P: Talend tSetGlobalVar Generated Java Code Reference

For reference, this is what Talend generates in Java for a `tSetGlobalVar` component with two variables. This helps understand the behavioral expectations:

```java
// tSetGlobalVar_1 - Main code
// KEY: "batch_id", VALUE: "BATCH_001"
globalMap.put("batch_id", "BATCH_001");

// KEY: "process_date", VALUE: new java.util.Date()
globalMap.put("process_date", new java.util.Date());

// Component statistics
globalMap.put("tSetGlobalVar_1_NB_LINE", 0);
globalMap.put("tSetGlobalVar_1_NB_LINE_OK", 0);
globalMap.put("tSetGlobalVar_1_NB_LINE_REJECT", 0);
```

**Key observations from the generated code**:
1. Each variable produces a single `globalMap.put()` call -- straightforward and direct
2. Values are embedded as Java expressions in the generated code -- they are COMPILED, not interpreted at runtime
3. Type information is preserved: `"BATCH_001"` is a String, `new java.util.Date()` is a Date
4. Statistics are always set to 0 for tSetGlobalVar (since it does not process data rows)
5. The generated code has no try/catch -- errors propagate to the subjob error handler

**Implication for V1**: The V1 engine should aim to produce identical globalMap state after execution. For simple strings, this works correctly. For Java expressions, the V1 engine's ad-hoc evaluation partially addresses constructors but misses other expression types.
