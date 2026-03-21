# Audit Report: tMap / Map

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tMap` |
| **V1 Engine Class** | `Map` |
| **Engine File** | `src/v1/engine/components/transform/map.py` (1164 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tmap()` (lines 511-681) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tMap':` (line 232-233) |
| **Registry Aliases** | `Map`, `tMap` (registered in `src/v1/engine/engine.py` lines 99-100) |
| **Category** | Transform / Processing |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/map.py` | Engine implementation (1164 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 511-681) | Dedicated `parse_tmap()` method -- parses MapperData XML into v1 JSON config |
| `src/converters/complex_converter/converter.py` (line 232-233) | Dispatch -- dedicated `elif` branch calling `parse_tmap()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/engine.py` (lines 779-795) | Multi-input routing: `_get_input_data()` returns dict for multi-input components |
| `src/v1/java_bridge/bridge.py` (lines 323-442) | Java bridge: `compile_tmap_script()`, `execute_compiled_tmap_chunked()`, `execute_tmap_preprocessing()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy |
| `src/v1/engine/components/transform/__init__.py` | Package exports |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 1 | 3 | 3 | 1 | Dedicated `parse_tmap()` exists; missing `DIE_ON_ERROR`, `STORE_ON_DISK`, `TEMP_DATA_DIR`, `catch_output_reject`; variable types converted but lost |
| Engine Feature Parity | **Y** | 1 | 6 | 5 | 2 | No RELOAD_AT_EACH_ROW; no store-temp-data; chunked parallel execution has race conditions; no catch_output_reject; UNIQUE_MATCH semantic deviation |
| Code Quality | **Y** | 3 | 4 | 6 | 3 | Cross-cutting base class bugs; `parse_base_component()` returns None for tMap; parallel forEach race condition; `print()` in bridge; inner join reject detection fragile |
| Performance & Memory | **Y** | 0 | 1 | 3 | 1 | Parallel stream execution is strong; but 50K chunk size is hard-coded; cartesian join has no size guard; Arrow serialization overhead |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tMap Does

`tMap` is the most powerful and most commonly used transformation component in Talend. It provides a graphical mapping editor for performing data transformations, lookups (joins), filtering, routing, and expression evaluation in a single component. It supports multiple inputs (one main + N lookups), multiple outputs (each with independent filters and reject settings), intermediate variable computation, and Java expression evaluation on every column. It is the equivalent of a SQL SELECT with JOINs, WHERE clauses, computed columns, and UNION ALL routing -- all in one component.

**Source**: [tMap Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tmap/tmap-standard-properties), [tMap lookup models](https://help.qlik.com/talend/en-US/components/8.0/tmap/tmap-lookup-models), [Differences between Unique match, First match and All matches](https://help.qlik.com/talend/en-US/components/8.0/tmap/differences-between-unique-match-first-match-and-all-matches), [Component-specific settings for tMap (Job Script Reference)](https://help.talend.com/en-US/job-script-reference-guide/8.0/component-specific-settings-for-tmap)

**Component family**: Processing / Transformation
**Available in**: All Talend products (Standard). Also available in MapReduce (deprecated), Spark Batch, Spark Streaming variants.
**Required JARs**: None (built-in)

### 3.1 Basic Settings -- Map Editor

The tMap component's primary configuration is through the Map Editor, a graphical interface. The Map Editor defines:

| # | Section | Description |
|---|---------|-------------|
| 1 | **Input Tables** | One main input (always first) plus zero or more lookup inputs. Each input has columns from the upstream component's schema. |
| 2 | **Variable Table** | Zero or one variable table containing intermediate computed values. Variables can reference input columns and previously-defined variables. Evaluated top-to-bottom in order. |
| 3 | **Output Tables** | One or more output tables. Each has its own column mappings, filter, reject settings, and die-on-error configuration. |
| 4 | **Expressions** | Java expressions on every join key, variable, output column, and filter. Single-line Java expressions only. |

### 3.2 Input Tables Configuration

#### 3.2.1 Main Input

| # | Parameter | XML Attribute | Type | Default | Description |
|---|-----------|---------------|------|---------|-------------|
| 1 | Name | `name` | String | flow name | Name of the main input table. Matches the flow connection name from upstream. |
| 2 | Expression Filter | `expressionFilter` | Java expression | -- | Optional filter applied to main input rows BEFORE join. Rows not matching are excluded. |
| 3 | Activate Expression Filter | `activateExpressionFilter` | Boolean | `false` | Toggle for the main input filter. |
| 4 | Inner Join | N/A | N/A | N/A | Not applicable to main input (main is always the driving table). |

#### 3.2.2 Lookup Inputs

| # | Parameter | XML Attribute | Type | Default | Description |
|---|-----------|---------------|------|---------|-------------|
| 5 | Name | `name` | String | flow name | Name of the lookup table. Matches the flow connection name from the lookup source. |
| 6 | Lookup Mode | `lookupMode` | Enum | `LOAD_ONCE` | How the lookup data is loaded. Options: `LOAD_ONCE`, `RELOAD_AT_EACH_ROW`, `RELOAD_AT_EACH_ROW_CACHE`. |
| 7 | Matching Mode | `matchingMode` | Enum | `UNIQUE_MATCH` | How duplicate matches are handled. Options: `UNIQUE_MATCH` (last match), `FIRST_MATCH`, `LAST_MATCH`, `ALL_MATCHES`. |
| 8 | Inner Join | `innerJoin` | Boolean | `false` | If true, uses INNER JOIN (unmatched main rows excluded). If false, uses LEFT OUTER JOIN (unmatched main rows preserved with NULLs for lookup columns). |
| 9 | Expression Filter | `expressionFilter` | Java expression | -- | Optional filter applied to lookup table BEFORE join. |
| 10 | Activate Expression Filter | `activateExpressionFilter` | Boolean | `false` | Toggle for the lookup filter. |
| 11 | Join Keys | `mapperTableEntries[expression]` | Java expression per column | -- | For each lookup column with an `expression` attribute, the expression defines the join condition. The expression is evaluated against the main row (or accumulated joined row), and the result is matched against the lookup column value. |

#### 3.2.3 Lookup Modes -- Detailed Behavior

| Mode | Talend Behavior | Description |
|------|-----------------|-------------|
| `LOAD_ONCE` | Load ALL lookup rows into memory (or disk if `STORE_ON_DISK=true`) ONCE before processing any main row. Default and most efficient for static lookups. | The entire lookup dataset is read and indexed by join keys before the main flow starts. Each main row is matched against this pre-loaded index. |
| `RELOAD_AT_EACH_ROW` | Reload ALL lookup rows for EACH main row. | The lookup source is re-queried for every main row. Used when the lookup query depends on the current main row's values (e.g., parameterized SQL with `globalMap` references). Extremely expensive for large datasets. |
| `RELOAD_AT_EACH_ROW_CACHE` | Like `RELOAD_AT_EACH_ROW`, but caches previously loaded records. Only new/changed records are fetched. | Optimizes repeated lookups by maintaining an in-memory cache. Cannot be combined with `STORE_ON_DISK`. |

**Note on `LOAD_ONCE_SORTED`**: This is NOT a standard Talend lookup mode. Some community references mention sorted lookups, but the official Talend documentation (v7.3, v8.0) lists only the three modes above. Sorted input optimization is a different concept -- it relates to whether the main and lookup inputs are pre-sorted on join keys, which can improve merge-join performance, but this is handled at the job design level, not as a tMap lookup mode setting.

#### 3.2.4 Matching Modes -- Detailed Behavior

| Mode | Talend Behavior | Description |
|------|-----------------|-------------|
| `UNIQUE_MATCH` | **Keeps LAST match** from lookup. Despite the name suggesting uniqueness, when multiple lookup rows match the same join key, Talend keeps the LAST one encountered. This is the default. | Important: This is equivalent to `LAST_MATCH`, NOT a uniqueness constraint. If lookup data has duplicates on join keys, the last row wins. |
| `FIRST_MATCH` | Keeps FIRST match from lookup. | When multiple lookup rows match, only the first one encountered is used. More predictable than `UNIQUE_MATCH` when lookup order matters. |
| `LAST_MATCH` | Keeps LAST match from lookup. | Identical to `UNIQUE_MATCH` behavior. Explicitly named for clarity. |
| `ALL_MATCHES` | Keeps ALL matches from lookup. | When N lookup rows match one main row, N output rows are produced (one for each combination). This creates a Cartesian product for the matched rows. Output row count can exceed input row count. |

**Source**: [Differences between Unique match, First match and All matches (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tmap/differences-between-unique-match-first-match-and-all-matches)

### 3.3 Variable Table

| # | Parameter | XML Location | Type | Default | Description |
|---|-----------|-------------|------|---------|-------------|
| 12 | Variable Name | `varTables/mapperTableEntries@name` | String | -- | Name of the variable. Referenced in expressions as `Var.var_name`. |
| 13 | Variable Expression | `varTables/mapperTableEntries@expression` | Java expression | -- | Java expression computing the variable value. Can reference input columns (`main.col`, `lookup.col`) and previously-defined variables (`Var.other_var`). |
| 14 | Variable Type | `varTables/mapperTableEntries@type` | Talend type | `id_String` | Data type of the variable (e.g., `id_String`, `id_Integer`, `id_Date`). |

**Behavioral Notes**:
- Variables are evaluated TOP-TO-BOTTOM in the order they appear in the variable table.
- A variable can reference any variable defined ABOVE it, but NOT below it.
- Variables are evaluated AFTER the join is complete, so they can reference both main and lookup columns.
- Variables are stored in a `Var` map accessible by all output column expressions.
- Variables persist for the current row only -- they are re-evaluated for each row.

### 3.4 Output Tables

| # | Parameter | XML Attribute | Type | Default | Description |
|---|-----------|---------------|------|---------|-------------|
| 15 | Name | `name` | String | flow name | Name of the output table. Matches the downstream flow connection. |
| 16 | Is Reject | `reject` | Boolean | `false` | Marks this output as a reject output. Reject outputs receive rows that fail filters or inner join conditions. |
| 17 | Inner Join Reject | `rejectInnerJoin` | Boolean | `false` | When true, this output captures rows rejected by inner join operations (main rows with no lookup match). |
| 18 | Catch Output Reject | `activateCondensedTool` | Boolean | `false` | When true, this output captures rows rejected by the PREVIOUS output's filter expression. Allows chaining of filter-reject pairs. |
| 19 | Expression Filter | `expressionFilter` | Java expression | -- | Filter expression applied to output rows. Only rows matching this condition are included in this output. |
| 20 | Activate Expression Filter | `activateExpressionFilter` | Boolean | `false` | Toggle for the output filter. |
| 21 | Output Columns | `mapperTableEntries` | List | -- | Each column has `name`, `expression`, `type`, `nullable`. The expression maps input/lookup/variable data to output columns. |
| 22 | Die On Error | N/A (global) | Boolean | `true` | In Talend, this is a GLOBAL setting for the entire tMap component (not per-output). When true, expression errors cause job failure. When false, error rows are routed to reject output. |

### 3.5 Advanced Settings (Component-Level)

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 23 | Store Temp Data | `STORE_ON_DISK` | Boolean | `false` | Store lookup data on disk instead of memory. Useful for large lookups that exceed JVM heap. |
| 24 | Temp Data Directory | `TEMP_DATA_DIR` | String | -- | Directory path for temporary data files when `STORE_ON_DISK=true`. |
| 25 | Max Buffer Size | `MAX_BUFFER_SIZE` | Integer | `2000000` | Maximum number of rows per temporary file when storing to disk. |
| 26 | Die On Error | `DIE_ON_ERROR` | Boolean | `true` | Global die-on-error setting. When false, expression evaluation errors produce reject rows instead of stopping the job. |
| 27 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean | `false` | Capture processing metadata for tStatCatcher. |
| 28 | Label | `LABEL` | String | -- | Text label for the component in the designer canvas. No runtime impact. |

### 3.6 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | The primary input data flow. Exactly one main input required. This is the driving table for all lookups. |
| `FLOW` (Lookup) | Input | Row > Lookup | Zero or more lookup inputs. Each connects to a separate input table in the Map Editor. Order of lookup connections determines evaluation order. |
| `FLOW` (Output) | Output | Row > Main | One or more output data flows. Each corresponds to an output table in the Map Editor. Each output has independent column mappings, filters, and reject settings. |
| `REJECT` | Output | Row > Reject | Optional reject output. Receives rows that fail expression evaluation when `DIE_ON_ERROR=false`, or rows that fail inner join conditions when `rejectInnerJoin=true`. Includes `errorCode` and `errorMessage` columns. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.7 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of main input rows processed. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully output across ALL output tables combined. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows routed to reject output(s). |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. |

### 3.8 Expression Language

tMap expressions use single-line Java syntax with the following available references:

| Reference | Syntax | Example | Description |
|-----------|--------|---------|-------------|
| Main input column | `main_name.column_name` | `row1.customer_id` | Access a column from the main input by its table name prefix. |
| Lookup column | `lookup_name.column_name` | `customers.name` | Access a column from a joined lookup table. |
| Variable | `Var.variable_name` | `Var.full_name` | Access a variable defined in the Variable table. |
| Context variable | `context.var_name` | `context.region` | Access a job context variable. |
| GlobalMap | `((String)globalMap.get("key"))` | `((String)globalMap.get("tFileList_1_CURRENT_FILE"))` | Access a globalMap variable with type cast. |
| Talend routines | `RoutineName.method(args)` | `TalendDate.formatDate("yyyy-MM-dd", row1.date)` | Call Talend built-in or custom routine methods. |
| Java methods | Standard Java | `row1.name.toUpperCase()` | Any valid single-line Java expression. |
| Ternary operator | `condition ? value1 : value2` | `row1.age > 18 ? "adult" : "minor"` | Conditional expressions (workaround for no multi-line support). |
| String concatenation | `+` operator | `row1.first + " " + row1.last` | Concatenate strings. |
| Null checks | `== null` / `!= null` | `row1.name != null ? row1.name : ""` | Null handling is critical since lookup columns can be null on outer joins. |

### 3.9 Behavioral Notes

1. **Main input is the driving table**: All lookups are performed relative to the main input. The main input determines the base row count (before ALL_MATCHES expansion).

2. **Lookup order matters**: Lookups are evaluated sequentially. A later lookup can reference columns from an earlier lookup's result. This is "chained lookup" behavior.

3. **Variable computation order**: Variables are evaluated in the order they appear in the Variable table (top to bottom). A variable can reference variables above it but not below it. This is a strict dependency ordering.

4. **Output filter evaluation**: Each output table's filter is evaluated independently. A single input row can appear in zero, one, or multiple outputs depending on filter conditions.

5. **Reject routing**: There are two distinct reject mechanisms:
   - **Inner Join Reject** (`rejectInnerJoin=true`): Captures main rows that had NO matching lookup row during an INNER JOIN.
   - **Output Reject** (`reject=true`): Captures rows that fail expression evaluation when `DIE_ON_ERROR=false`.
   - **Catch Output Reject** (`activateCondensedTool=true`): Captures rows rejected by the PREVIOUS output's filter expression.

6. **UNIQUE_MATCH is LAST_MATCH**: Despite the name, `UNIQUE_MATCH` keeps the LAST matching lookup row, not the first. This is a common source of confusion.

7. **ALL_MATCHES creates row multiplication**: When a main row matches N lookup rows with ALL_MATCHES, N output rows are produced. This can dramatically increase output row count.

8. **LOAD_ONCE is default and preferred**: LOAD_ONCE loads the entire lookup into memory once. RELOAD_AT_EACH_ROW is only needed when the lookup query is parameterized by the current row's values.

9. **Store temp data on disk**: When enabled, lookup data is written to temporary files instead of being held entirely in memory. This allows processing of lookups larger than JVM heap size. Temporary files are cleaned up at subjob completion.

10. **Die on error is GLOBAL**: The `DIE_ON_ERROR` setting applies to the entire tMap component, not per-output. When false, expression errors for ANY output produce reject rows.

11. **Schema propagation**: In Talend Studio, schema changes in upstream components propagate through tMap. Output schemas are defined independently and do not automatically inherit from inputs.

12. **Null handling in joins**: When a lookup column used as a join key contains NULL, it does NOT match a NULL in the main input (SQL-like NULL behavior). This can cause unexpected inner join rejects.

13. **Expression limitations**: All tMap expressions must be single-line Java. For complex logic, use Talend routines (custom Java methods) or the ternary operator for conditionals.

14. **Multiple inner joins**: When multiple lookups use INNER_JOIN, the reject output may receive rows rejected by ANY of the inner joins. The reject output does not distinguish which join caused the rejection.

---

## 4. Converter Audit

### 4.1 Parser Method

The converter uses a **dedicated `parse_tmap()` method** in `component_parser.py` (lines 511-681). This is the correct approach per STANDARDS.md and is one of the most comprehensive parsers in the codebase at 170 lines.

**Converter flow**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)`
2. `parse_base_component()` has an explicit skip for tMap in `components_with_dedicated_parsers` (lines 420-430). The generic parameter extraction **NEVER runs** for tMap. `DIE_ON_ERROR` is never extracted in the first place.
3. `converter.py` then calls `component_parser.parse_tmap(node, component)` (line 233)
4. `parse_tmap()` finds the `<nodeData>` element with `MapperData` type
5. Parses `<inputTables>`, `<varTables>`, `<outputTables>` from the XML
6. Builds `component['config']` (line 667) -- but `DIE_ON_ERROR` is **not included** because it was never extracted by either the generic pass or `parse_tmap()` itself

### 4.2 Parameter Extraction

#### 4.2.1 Input Tables Extraction

| # | Talend XML Attribute | Extracted? | V1 Config Key | Parser Line | Notes |
|----|----------------------|------------|---------------|-------------|-------|
| 1 | `inputTables@name` | Yes | `inputs.main.name` / `inputs.lookups[].name` | 549, 569 | Correct extraction |
| 2 | `inputTables@activateExpressionFilter` | Yes | `inputs.main.activate_filter` / `inputs.lookups[].activate_filter` | 552, 597 | Boolean string comparison |
| 3 | `inputTables@expressionFilter` | Yes | `inputs.main.filter` / `inputs.lookups[].filter` | 553, 585 | Marked with `{{java}}` prefix |
| 4 | `inputTables@matchingMode` | Yes | `inputs.main.matching_mode` / `inputs.lookups[].matching_mode` | 562, 594 | Default: `UNIQUE_MATCH`. Also extracted for main input (not used) |
| 5 | `inputTables@lookupMode` | Yes | `inputs.main.lookup_mode` / `inputs.lookups[].lookup_mode` | 563, 595 | Default: `LOAD_ONCE`. **Extracted but NOT used by engine** |
| 6 | `inputTables@innerJoin` | Yes | `inputs.lookups[].join_mode` | 590 | Converted: `true` -> `INNER_JOIN`, `false` -> `LEFT_OUTER_JOIN` |
| 7 | `mapperTableEntries@expression` (join key) | Yes | `inputs.lookups[].join_keys[].expression` | 574-580 | Marked with `{{java}}` prefix. Only entries WITH expression are captured. |
| 8 | `mapperTableEntries@name` (join key column) | Yes | `inputs.lookups[].join_keys[].lookup_column` | 577 | Lookup column name for join |

#### 4.2.2 Variable Table Extraction

| # | Talend XML Attribute | Extracted? | V1 Config Key | Parser Line | Notes |
|----|----------------------|------------|---------------|-------------|-------|
| 9 | `varTables/mapperTableEntries@name` | Yes | `variables[].name` | 609 | Variable name |
| 10 | `varTables/mapperTableEntries@expression` | Yes | `variables[].expression` | 610 | Marked with `{{java}}` prefix |
| 11 | `varTables/mapperTableEntries@type` | Yes | `variables[].type` | 617 | **Kept in Talend format** (e.g., `id_String`) -- good |

**Note**: Line 611 calls `self.expr_converter.convert_type()` but the result is discarded -- the actual stored type on line 617 uses the raw Talend type. This is correct but the dead code on line 611 is wasteful.

#### 4.2.3 Output Table Extraction

| # | Talend XML Attribute | Extracted? | V1 Config Key | Parser Line | Notes |
|----|----------------------|------------|---------------|-------------|-------|
| 12 | `outputTables@name` | Yes | `outputs[].name` | 626 | Output name |
| 13 | `outputTables@reject` | Yes | `outputs[].is_reject` | 627 | Boolean conversion |
| 14 | `outputTables@rejectInnerJoin` | Yes | `outputs[].inner_join_reject` | 629 | Boolean conversion |
| 15 | `outputTables@activateExpressionFilter` | Yes | `outputs[].activate_filter` | 659 | Boolean conversion |
| 16 | `outputTables@expressionFilter` | Yes | `outputs[].filter` | 634 | Marked with `{{java}}` prefix |
| 17 | `mapperTableEntries@name` (column) | Yes | `outputs[].columns[].name` | 641 | Column name |
| 18 | `mapperTableEntries@expression` (column) | Yes | `outputs[].columns[].expression` | 642, 648 | Marked with `{{java}}` prefix |
| 19 | `mapperTableEntries@type` (column) | Yes | `outputs[].columns[].type` | 643 | **Kept in Talend format** -- good |
| 20 | `mapperTableEntries@nullable` (column) | Yes | `outputs[].columns[].nullable` | 644 | Boolean conversion |

#### 4.2.4 Missing Parameters

| # | Talend XML Name | Extracted? | Notes |
|----|-----------------|------------|-------|
| 21 | `DIE_ON_ERROR` (elementParameter) | **No** | **CRITICAL**: `parse_base_component()` has an explicit skip for tMap in `components_with_dedicated_parsers` (lines 420-430), so the generic parameter extraction never runs. `DIE_ON_ERROR` is never extracted in the first place. `parse_tmap()` also does not extract it. Engine defaults to `true` (line 867 of map.py). |
| 22 | `STORE_ON_DISK` | **No** | Not extracted. Engine has no disk-based lookup storage. |
| 23 | `TEMP_DATA_DIR` | **No** | Not extracted. No temp directory support. |
| 24 | `MAX_BUFFER_SIZE` | **No** | Not extracted. No buffer size configuration. |
| 25 | `activateCondensedTool` (catch output reject) | **No** | Not extracted. Engine does not support catch-output-reject chaining between outputs. |
| 26 | `TSTATCATCHER_STATS` | **No** | Not extracted (low priority -- tStatCatcher rarely used). |
| 27 | `LABEL` | **No** | Not extracted (cosmetic -- no runtime impact). |
| 28 | Lookup column entries WITHOUT expression | **No** | Lookup columns that are NOT join keys (no `expression` attribute) are not explicitly captured. The engine relies on prefixed column names from the pandas merge. This works but makes it implicit. |

**Summary**: 20 of 28 meaningful parameters extracted (71%). 5 runtime-relevant parameters are missing (`DIE_ON_ERROR` being the most critical).

### 4.3 Schema Extraction

Schema is NOT extracted from `<metadata>` nodes for tMap. Instead, `parse_tmap()` extracts output column definitions directly from the `<outputTables>/<mapperTableEntries>` XML elements. This is correct because tMap's output schemas are defined in the Map Editor, not in the metadata nodes.

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` (column) | Yes | From `mapperTableEntries@name` |
| `expression` (column) | Yes | From `mapperTableEntries@expression`, marked with `{{java}}` |
| `type` (column) | Yes | From `mapperTableEntries@type`, **kept in Talend format** (e.g., `id_String`) |
| `nullable` (column) | Yes | From `mapperTableEntries@nullable`, boolean conversion |
| `length` | **No** | Not extracted from output column definitions |
| `precision` | **No** | Not extracted from output column definitions |
| `pattern` (date) | **No** | Not extracted from output column definitions |
| `key` | **No** | Not extracted from output column definitions |
| `default` | **No** | Not extracted |
| `comment` | **No** | Not extracted (cosmetic) |

### 4.4 Expression Handling

**Java expression marking** (component_parser.py lines 574-580, 610-618, 640-652):
- ALL tMap expressions (join keys, variables, output columns, filters) are unconditionally prefixed with `{{java}}` marker
- This is correct for tMap since ALL its expressions are Java code (unlike other components where some values may be literals)
- The engine's `_strip_java_marker()` method removes this prefix before evaluation
- tMap is specifically excluded from the generic `mark_java_expression()` pass (line 462: `if component_name not in ['tMap', 'tJavaRow', 'tJava']`)

**Context variable handling**:
- Context variables in tMap expressions are resolved at runtime by the Java bridge
- The bridge receives flattened context variables via `set_context()` (map.py lines 384-399)
- Expressions like `context.region` are evaluated in Java where `context` is a bound variable

**Known limitations**:
- The `{{java}}` prefix is applied unconditionally to ALL expressions including empty ones (handled by engine: empty expressions become `null`)
- No validation that expressions reference valid column names or table names at conversion time
- Routine references (e.g., `TalendString.replaceAll()`) are not validated at conversion time

### 4.5 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-MAP-001 | **P0** | **`DIE_ON_ERROR` never extracted for tMap**: `parse_base_component()` has an explicit skip for tMap in `components_with_dedicated_parsers` (lines 420-430), so the generic parameter extraction never runs. `DIE_ON_ERROR` is never extracted in the first place. `parse_tmap()` also does not extract it. The engine then defaults to `die_on_error=True` (map.py line 867), which may differ from the Talend job's setting. Jobs with `DIE_ON_ERROR=false` will incorrectly die on expression errors instead of routing to reject. **Fix**: Add `'die_on_error': node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'true').lower() == 'true'` to the config built by `parse_tmap()` on line 667. |
| CONV-MAP-002 | **P1** | **`catch_output_reject` not extracted**: The `activateCondensedTool` attribute on output tables is not parsed. Talend uses this for output-level reject chaining: when Output A has a filter and Output B has `catch_output_reject=true`, rows rejected by Output A's filter are routed to Output B. Without this, the reject chaining logic is missing entirely. |
| CONV-MAP-003 | **P1** | **`STORE_ON_DISK` / `TEMP_DATA_DIR` / `MAX_BUFFER_SIZE` not extracted**: Engine cannot store lookup data on disk. Large lookups that exceed memory will cause OOM instead of graceful disk spillover. |
| CONV-MAP-004 | **P1** | **`lookup_mode` extracted but unused**: The converter correctly extracts `lookupMode` (line 595) but the engine ignores it entirely. The engine always behaves as `LOAD_ONCE`. Jobs using `RELOAD_AT_EACH_ROW` will silently produce wrong results because the lookup is not re-queried per main row. |
| CONV-MAP-005 | **P2** | **Dead code in variable type conversion**: Line 611 calls `self.expr_converter.convert_type()` but the result is not stored. The actual type on line 617 correctly uses the raw Talend type. The dead code wastes CPU cycles during conversion. |
| CONV-MAP-006 | **P2** | **`matching_mode` extracted for main input but meaningless**: Line 562 extracts `matchingMode` for the main input table. However, matching mode only applies to lookups, not the main input. This creates a misleading configuration value. |
| CONV-MAP-007 | **P2** | **Missing column `length`, `precision`, `pattern` extraction for output columns**: These schema attributes are not extracted from output column definitions. While the engine doesn't currently use them, they would be needed for strict type validation (e.g., Decimal precision, date format patterns). |
| CONV-MAP-008 | **P3** | **`TSTATCATCHER_STATS` not extracted**: Low priority -- tStatCatcher is rarely used in production. |

---

## 5. Engine Feature Parity

### 5.1 Architecture Overview

The `Map` class (1164 lines) implements a 4-phase execution pipeline:

```
Phase 1: Filter Lookups       -> _filter_lookups()
Phase 2: Filter Main & Join   -> _perform_lookups() with _perform_normal_join() / _perform_cartesian_join()
Phase 3: Apply Matching Mode   -> _apply_matching_mode()
Phase 4: Variables & Outputs   -> _evaluate_and_route_outputs() -> _evaluate_outputs_java()
```

The component uses a hybrid Python/Java approach:
- **Python (pandas)**: Join operations, matching mode deduplication, DataFrame manipulation
- **Java (via bridge)**: Expression evaluation, variable computation, output column mapping, filter evaluation

The Java execution uses a **compiled script approach**:
1. `_generate_tmap_compiled_script()` generates pure Java code with imports, parallel processing, variable evaluation, output routing, and reject handling
2. `java_bridge.compile_tmap_script()` compiles the script once
3. `java_bridge.execute_compiled_tmap_chunked()` executes on 50K-row chunks via Arrow serialization

### 5.2 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Main input processing | **Yes** | High | `_process()` line 125-126 | Main DataFrame extracted from inputs dict |
| 2 | Main input filter | **Yes** | High | `_process()` lines 135-169 | Both simple column refs and complex Java expressions supported |
| 3 | Multiple lookup inputs | **Yes** | High | `_perform_lookups()` line 447 | Sequential lookup evaluation with chained support |
| 4 | Lookup filter (pre-join) | **Yes** | High | `_filter_lookups()` lines 264-319 | Filters applied before join using Java bridge |
| 5 | Join: LEFT_OUTER_JOIN | **Yes** | High | `_perform_normal_join()` line 702 | pandas `how='left'` merge |
| 6 | Join: INNER_JOIN | **Yes** | High | `_perform_normal_join()` line 701 | pandas `how='inner'` merge |
| 7 | Matching: UNIQUE_MATCH | **Yes** | High | `_apply_matching_mode()` line 746-748 | Correctly uses `keep='last'` to match Talend behavior |
| 8 | Matching: FIRST_MATCH | **Yes** | High | `_apply_matching_mode()` line 750-752 | Uses `drop_duplicates(keep='first')` |
| 9 | Matching: LAST_MATCH | **Yes** | High | `_apply_matching_mode()` line 753-755 | Uses `drop_duplicates(keep='last')` |
| 10 | Matching: ALL_MATCHES | **Yes** | High | `_apply_matching_mode()` line 739 | No deduplication -- returns all rows |
| 11 | Variable table evaluation | **Yes** | High | `_generate_tmap_compiled_script()` lines 1004-1017 | Variables evaluated in order, stored in `Var` HashMap |
| 12 | Multiple outputs | **Yes** | High | `_generate_tmap_compiled_script()` lines 1019-1066 | Each output evaluated independently with own filter |
| 13 | Output filter expressions | **Yes** | High | `_generate_tmap_compiled_script()` lines 1033-1036 | Java `if` statement wrapping output column evaluation |
| 14 | Reject output (is_reject) | **Yes** | Medium | `_generate_tmap_compiled_script()` lines 1088-1126 | `matchedAny` flag routing. See issues below. |
| 15 | Inner join reject | **Yes** | Medium | `_perform_lookups()` lines 480-489, `_evaluate_and_route_outputs()` lines 782-815 | Unmatched main rows captured. See issues below. |
| 16 | Java expression evaluation | **Yes** | High | `_batch_evaluate_expressions()` lines 350-417 | Via Java bridge with context/globalMap sync |
| 17 | Cartesian join (context-only keys) | **Yes** | Medium | `_perform_cartesian_join()` lines 496-574 | Cross join with context-based filtering |
| 18 | Chained lookups | **Yes** | High | `_perform_normal_join()` line 605 | Join key expressions evaluated against accumulated joined_df |
| 19 | Context variable resolution | **Yes** | High | `execute()` line 65, `_evaluate_outputs_java()` lines 842-856 | Flattened context synced to Java bridge |
| 20 | GlobalMap integration | **Yes** | High | `_evaluate_outputs_java()` lines 858-860 | GlobalMap synced to/from Java bridge |
| 21 | Die on error (true) | **Yes** | High | `_generate_tmap_compiled_script()` lines 1070-1073 | Re-throws RuntimeException |
| 22 | Die on error (false) | **Yes** | Medium | `_generate_tmap_compiled_script()` lines 1074-1083 | Error tracked, row routed to reject. **But DIE_ON_ERROR config value is never extracted by converter** |
| 23 | Compiled script execution | **Yes** | High | `_evaluate_outputs_java()` lines 890-898 | Script compiled once, executed on chunks |
| 24 | Chunked execution | **Yes** | Medium | `execute_compiled_tmap_chunked()` line 370-442 | 50K row chunks. See issues below. |
| 25 | Simple column reference optimization | **Yes** | High | `_is_simple_column_ref()` line 220-222 | Regex-based detection to skip Java for simple `table.column` refs |
| 26 | Context-back-sync from Java | **Yes** | High | `_evaluate_outputs_java()` lines 919-930 | Context and globalMap synced back after execution |
| 27 | Empty expression handling | **Yes** | High | `_generate_tmap_compiled_script()` lines 1013, 1053-1054 | Empty expressions become `null` in Java |
| 28 | **Lookup mode: RELOAD_AT_EACH_ROW** | **No** | N/A | -- | **Not implemented. Engine always behaves as LOAD_ONCE. Lookup data is loaded once and never refreshed. Jobs using parameterized lookup queries will produce wrong results.** |
| 29 | **Lookup mode: RELOAD_AT_EACH_ROW_CACHE** | **No** | N/A | -- | **Not implemented. Same as above.** |
| 30 | **Store temp data on disk** | **No** | N/A | -- | **Not implemented. Large lookups may cause OOM.** |
| 31 | **Catch output reject** | **No** | N/A | -- | **Not implemented. Filter-reject chaining between outputs is not supported.** |
| 32 | **Per-output die on error** | **N/A** | N/A | -- | **Talend uses global die-on-error, not per-output. V1 matches this design.** |
| 33 | **REJECT flow with errorCode/errorMessage** | **No** | N/A | -- | **Reject output schema does not include standard `errorCode` and `errorMessage` columns.** |
| 34 | **Null-safe join key matching** | **Partial** | Medium | -- | **pandas merge treats NaN as non-matching by default. Talend also treats NULL join keys as non-matching. Behavior is aligned but not explicitly enforced.** |

### 5.3 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-MAP-001 | **P0** | **Inner join reject detection is fragile and may produce wrong results**: The inner join reject logic (lines 480-489) attempts to find unmatched rows by performing a second `left` merge between `prev_df` and `joined_df` with `indicator=True`. This approach is fundamentally flawed: (1) It relies on ALL columns matching between `prev_df` and `joined_df`, which may fail if column values changed during the join. (2) Duplicate rows in `prev_df` may produce false `left_only` indicators. (3) The merge uses no explicit key columns -- it compares ALL columns, which is expensive and fragile. Talend tracks inner join rejects during the join itself by checking which main rows had no match. |
| ENG-MAP-002 | **P1** | **RELOAD_AT_EACH_ROW not implemented**: The engine always uses LOAD_ONCE semantics regardless of the `lookup_mode` configuration. For jobs where the lookup query is parameterized by the current main row (e.g., `WHERE region = ? AND year = ?` with globalMap references), the lookup data is loaded once and never refreshed. This produces incorrect results for any job using `RELOAD_AT_EACH_ROW`. |
| ENG-MAP-003 | **P1** | **Catch output reject not implemented**: In Talend, when Output A has a filter and Output B has `catch_output_reject=true`, rows rejected by Output A's filter are routed to Output B. The v1 engine does not support this chaining. Rows rejected by one output's filter are simply lost. |
| ENG-MAP-004 | **P1** | **Parallel forEach introduces non-determinism and potential race conditions**: The generated Java script uses `IntStream.range(0, rowCount).parallel().forEach(...)` (line 983). While `AtomicInteger` counters prevent data corruption, the `Object[][] output_data = new Object[rowCount][num_cols]` arrays are indexed by `count.getAndIncrement()`, meaning output row order is non-deterministic. Talend processes rows sequentially with deterministic output order. For jobs where output row order matters (e.g., sorted data, sequential file writes, running totals), this produces different results. |
| ENG-MAP-005 | **P1** | **Variable evaluation in parallel is unsafe for stateful expressions**: Variables are evaluated inside the parallel forEach loop (lines 1004-1017). If variables have side effects or reference mutable shared state (e.g., `globalMap.put()`), concurrent evaluation produces race conditions. Talend evaluates variables sequentially per row. |
| ENG-MAP-006 | **P1** | **Die on error value never extracted by converter**: `parse_base_component()` skips generic parameter extraction for tMap (lines 420-430 of `component_parser.py`), and `parse_tmap()` does not extract `DIE_ON_ERROR` either. The engine defaults to `true` (line 867). Jobs explicitly configured with `DIE_ON_ERROR=false` will die on expression errors instead of routing to reject. This is the same root cause as CONV-MAP-001 but manifested at the engine level. |
| ENG-MAP-007 | **P2** | **Reject output does not include `errorCode` and `errorMessage` columns**: In Talend, reject outputs include `errorCode` (String) and `errorMessage` (String) columns. The v1 engine's reject output only contains the original data columns (from the `matchedAny=false` path in the generated script). Error details from `errorMap` are tracked but not added to the reject DataFrame. |
| ENG-MAP-008 | **P2** | **Cartesian join has no size guard**: `_perform_cartesian_join()` uses `joined_df.merge(lookup_df_prefixed, how='cross')` (line 570). If both DataFrames are large (e.g., 100K x 100K), this produces 10 billion rows, likely causing OOM. Talend has the same theoretical risk, but the explicit `STORE_ON_DISK` option provides mitigation. No size check or warning is emitted. |
| ENG-MAP-009 | **P2** | **Empty lookup table handling differs**: When a lookup table is empty after filtering (line 455-457), the engine skips the join entirely with a warning. In Talend with LEFT_OUTER_JOIN, all main rows would be preserved with NULL lookup columns. With INNER_JOIN, all main rows would be rejected. The skip behavior means main rows lose their lookup column placeholders. |
| ENG-MAP-010 | **P2** | **Column name collision on multiple lookups**: All lookup columns are prefixed with `{lookup_name}.{col_name}` (lines 564, 693). If two lookups have the same name (unlikely but possible in malformed configs), column names collide silently. Also, if a lookup column name contains a dot, the prefix creates ambiguous column references. |
| ENG-MAP-011 | **P2** | **Join key column search order may produce wrong match**: `_perform_normal_join()` tries multiple column name formats (lines 621-645): `table.column`, `column`, `table`, then fuzzy `startswith(column)`. The fuzzy `startswith` match on line 641 can match the wrong column (e.g., looking for `id` could match `id_name`, `id_type`, etc.). |
| ENG-MAP-012 | **P3** | **Matching mode applied globally, not per-join-key-combination**: `_apply_matching_mode()` deduplicates the entire lookup DataFrame on join key columns. In Talend, the matching mode applies per join key combination per main row. For ALL_MATCHES with multiple join keys, the behavior should be the same, but for UNIQUE_MATCH with partial key matches, there could be subtle differences. |
| ENG-MAP-013 | **P3** | **No `{id}_ERROR_MESSAGE` globalMap variable**: When expression evaluation errors occur with `die_on_error=false`, the error messages are tracked in `errorMap` within the Java script but not stored as a globalMap variable in the standard Talend format. |

### 5.4 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` via base class | Set as `rows_read` = len(main_df) |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Set as `total_output_rows` across all outputs. May not match Talend semantics (Talend counts main output only, not all outputs). |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Not explicitly tracked. `_update_stats()` is called with only `rows_read` and `rows_ok` (line 200-203). `NB_LINE_REJECT` defaults to 0 since base class initializes it to 0 and `rows_reject` is never passed. |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Not implemented |
| `{id}_ERROR_COUNT` | N/A | **Yes** | `_evaluate_outputs_java()` line 914 | V1-specific; error count stored when `die_on_error=false` |

### 5.5 Execution Flow Detail

#### Phase 1: Filter Lookups (`_filter_lookups()`, lines 264-319)

**Purpose**: Pre-filter lookup tables before joining to reduce join complexity.

**Step-by-step**:
1. Copies the `inputs` dict to `filtered_inputs` (line 279)
2. Iterates each lookup configuration from `lookups_config`
3. Checks if lookup has `activate_filter=true` AND a non-empty `filter` expression (line 289)
4. Strips `{{java}}` marker from filter expression (line 292)
5. **Simple column ref path** (line 297-303): If filter is `table.column` pattern, uses pandas boolean indexing `lookup_df[lookup_df[column] == True]`. **BUG**: Only works for boolean columns (see BUG-MAP-007).
6. **Complex expression path** (line 304-317): Calls `_batch_evaluate_expressions()` to evaluate filter via Java bridge. Creates boolean mask from result. Applies `fillna(False)` for NA safety (AT17854 fix).
7. Returns `filtered_inputs` with filtered DataFrames

**Code flow**:
```
_filter_lookups(inputs, lookups_config)
  for each lookup_config:
    if not activate_filter: skip
    filter_expr = strip_java_marker(lookup_config['filter'])
    if is_simple_column_ref(filter_expr):
      -> pandas boolean index (BUG: == True check)
    else:
      -> _batch_evaluate_expressions(lookup_df, {'filter': expr}, ...)
      -> apply boolean mask to lookup_df
  return filtered_inputs
```

**Issues**:
- The simple column filter path (line 301) compares `lookup_df[column] == True`, which only works for boolean columns. Non-boolean filter expressions that happen to be simple column references will silently produce wrong results (e.g., filtering where a string column equals True will exclude all rows).
- The `_batch_evaluate_expressions()` call passes the lookup name as `main_table_name` (line 309), which is technically wrong -- it should be the lookup name, not the main name. However, since the lookup filter only references lookup columns, this may not cause issues in practice.

#### Phase 2: Main Filter & Lookups (`_process()` lines 134-177, `_perform_lookups()` lines 419-494)

**Purpose**: Apply main input filter, then perform sequential lookup joins.

**Step 2a: Main input filter** (lines 135-169):
1. Checks `main_config.activate_filter` AND `main_config.filter` (line 135)
2. Strips `{{java}}` marker
3. **Simple column ref path**: Tries multiple column name formats (`table`, `table.column`, `column`) for the filter column
4. **Complex expression path**: Evaluates via Java bridge, applies boolean mask with `fillna(False)`
5. Creates a filtered copy of `main_df`

**Step 2b: Sequential lookup evaluation** (`_perform_lookups()`, lines 419-494):
1. Copies `main_df` to `joined_df` (line 443)
2. Initializes `joined_lookups = []` for chained lookup tracking (line 444)
3. Initializes empty `inner_join_rejects` DataFrame (line 445)
4. For each lookup configuration:
   a. Gets lookup DataFrame from filtered inputs
   b. Skips if lookup is None or empty (with warning)
   c. Checks if all join keys are context-only expressions
   d. If cartesian: calls `_perform_cartesian_join()`
   e. If normal: saves `prev_df = joined_df.copy()`, calls `_perform_normal_join()`
   f. For INNER_JOIN: attempts to detect unmatched rows (FRAGILE -- see ENG-MAP-001)
   g. Appends lookup name to `joined_lookups`

**Step 2c: Normal join** (`_perform_normal_join()`, lines 576-718):
1. Separates join key expressions into simple and complex
2. For simple expressions: looks up column values in `joined_df` using multiple format attempts
3. For complex expressions: evaluates via Java bridge (passing `joined_lookups` for chained context)
4. Creates temporary join key columns (`_join_{lookup_name}_{idx}`)
5. Applies matching mode to deduplicate lookup
6. Prefixes all lookup columns with `{lookup_name}.`
7. Performs pandas merge with appropriate `how` parameter
8. Cleans up temporary join key columns

**Step 2d: Cartesian join** (`_perform_cartesian_join()`, lines 496-574):
1. For each join key, evaluates the context-only expression via `execute_one_time_expression()`
2. Filters lookup table: `filtered_lookup = filtered_lookup[filtered_lookup[lookup_col] == filter_value]`
3. Prefixes all lookup columns with `{lookup_name}.`
4. Performs pandas cross join: `joined_df.merge(lookup_df_prefixed, how='cross')`

**Step 2e: Inner join reject tracking** (lines 480-489):
1. Only for `join_mode == 'INNER_JOIN'`
2. Performs a SECOND left merge: `prev_df.merge(joined_df, how='left', indicator=True)`
3. Rows with `_merge == 'left_only'` are considered inner join rejects
4. Appends to accumulated `inner_join_rejects` DataFrame

**Issues**:
- Inner join reject detection is fragile (see ENG-MAP-001). The second merge compares ALL columns, which is expensive and prone to false positives/negatives.
- Empty lookup handling differs from Talend (see ENG-MAP-009). Empty lookups are skipped entirely instead of adding NULL columns.
- The `prev_df.copy()` on line 474 doubles memory usage for every INNER_JOIN lookup.
- The `joined_lookups` list enables chained lookups, but the Java bridge must correctly resolve column references across multiple tables. This is handled by the `lookup_table_names` parameter in `execute_tmap_preprocessing()`.

#### Phase 3: Matching Mode (`_apply_matching_mode()`, lines 720-765)

**Purpose**: Deduplicate lookup DataFrame based on the configured matching mode.

**Step-by-step**:
1. If `ALL_MATCHES` or no join keys: returns lookup unchanged (line 739-741)
2. For `UNIQUE_MATCH`: `lookup_df.drop_duplicates(subset=join_keys, keep='last')` -- correctly matches Talend behavior where UNIQUE_MATCH = LAST_MATCH (line 748)
3. For `FIRST_MATCH`: `drop_duplicates(subset=join_keys, keep='first')` (line 752)
4. For `LAST_MATCH`: `drop_duplicates(subset=join_keys, keep='last')` (line 755)
5. Unknown modes: default to ALL_MATCHES with warning (line 757-759)
6. Logs deduplication effect if row count changed

**Design decision**: Matching mode is applied BEFORE the merge, by deduplicating the lookup DataFrame on join key columns. This is correct because:
- For FIRST/LAST/UNIQUE_MATCH, only one lookup row per key combination should participate in the join
- Deduplicating before merge is more efficient than deduplicating after merge (smaller DataFrame in merge)
- The `join_keys` parameter uses the original (non-prefixed) column names, which is correct since deduplication happens before prefixing

**Issues**:
- Applied globally on the entire lookup, not per-main-row. For typical use cases, this is equivalent, but for edge cases where the same lookup key has different values in different columns, there could be subtle differences.
- The `subset=join_keys` parameter uses the list of `right_on` column names (line 686-688). These are the original lookup column names before prefixing. This is correct.

#### Phase 4: Variables & Outputs (`_evaluate_and_route_outputs()`, lines 767-817, `_evaluate_outputs_java()`, lines 819-936)

**Purpose**: Evaluate intermediate variables, compute output column expressions, apply output filters, and route rows to output DataFrames.

**Step 4a: Java script generation** (`_generate_tmap_compiled_script()`, lines 938-1157):
1. Generates import statements (java.util, concurrent, stream, RowWrapper)
2. Allocates output arrays: `Object[][] output_data = new Object[rowCount][numCols]`
3. Creates `AtomicInteger` counters for each output
4. If die_on_error=false: allocates error tracking structures
5. Opens parallel stream: `IntStream.range(0, rowCount).parallel().forEach(i -> { ... })`
6. Creates `RowWrapper` instances for main and each lookup table
7. If any reject output exists: declares `boolean matchedAny = false`
8. Opens inner try-catch block
9. Evaluates variables in order: `Var.put("name", expression)`
10. For each non-reject output: evaluates filter (if any), evaluates all columns into temp array, commits to output array
11. Closes inner try-catch: die_on_error=true re-throws, die_on_error=false tracks error
12. For reject outputs (outside inner try-catch): if `!matchedAny`, evaluates reject column expressions, commits to reject array
13. Closes outer try-catch (always re-throws)
14. Constructs return value: `Map<String, Map<String, Object>>` with data arrays and counts

**Step 4b: Script compilation** (lines 891-898):
1. Calls `java_bridge.compile_tmap_script()` with:
   - component_id: unique identifier for caching
   - java_script: generated source code
   - output_schemas: `{output_name: [column_names]}`
   - output_types: `{output_name_colName: type_string}`
   - main_table_name: main input name
   - lookup_names: list of lookup names

**Step 4c: Chunked execution** (lines 900-905):
1. Calls `java_bridge.execute_compiled_tmap_chunked(component_id, joined_df, chunk_size=50000)`
2. Bridge chunks the DataFrame into 50K-row segments
3. Each chunk is serialized to Arrow, sent to JVM, executed, result serialized back
4. Chunk results are concatenated with `pd.concat(ignore_index=True)`

**Step 4d: Error handling** (lines 907-917):
1. If die_on_error=false, checks for `__errors__` key in results
2. Extracts error count and stores in globalMap as `{id}_ERROR_COUNT`
3. Logs warning if errors occurred

**Step 4e: Context/GlobalMap sync** (lines 919-930):
1. Calls `java_bridge._sync_from_java()` to get updated context and globalMap from JVM
2. Updates Python ContextManager with synced values
3. Updates Python GlobalMap with synced values

**Step 4f: Inner join reject handling** (`_evaluate_and_route_outputs()`, lines 782-815):
1. If `inner_join_rejects` is not empty:
2. For each output with `inner_join_reject=true`:
3. Optionally applies output filter to rejects
4. Evaluates output expressions for reject rows using the same Java script logic
5. Stores reject DataFrame in output_dfs

**Issues**:
- Parallel execution non-determinism (ENG-MAP-004): `IntStream.parallel()` means output row order is random
- Variable evaluation race conditions (ENG-MAP-005): `Var` HashMap is per-thread (correct), but `globalMap.put()` calls in expressions are not synchronized
- Hard-coded 50K chunk size (PERF-MAP-002): Not configurable
- Output array sizing (BUG-MAP-005): `Object[rowCount]` may be sparse when filters exclude rows
- Error indices are chunk-relative, not absolute: Error at chunk 2, row 5 is reported as row 5, not row 100005
- Inner join reject expression evaluation creates a SECOND Java script compilation/execution for the same expressions but different data. This doubles the Java overhead for reject processing.

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-MAP-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the loop variable is `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: Affects ALL components since `_update_global_map()` is called by `Map.execute()` on line 72. |
| BUG-MAP-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` variable does not exist. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-MAP-003 | **P1** | `src/v1/engine/components/transform/map.py:480-489` | **Inner join reject detection is fundamentally flawed**: The code uses `prev_df.merge(joined_df, how='left', indicator=True)` to find unmatched rows. This performs a merge on ALL columns, which: (1) fails if any column has NaN values (NaN != NaN in pandas merge), (2) is extremely expensive for wide DataFrames, (3) produces false positives/negatives when column values change during the join (e.g., due to type coercion by the merge). The correct approach is to track matched/unmatched main row indices during the merge itself using the `indicator` parameter of the primary merge. |
| BUG-MAP-004 | **P1** | `src/v1/engine/components/transform/map.py:983` | **Parallel stream execution makes output row order non-deterministic**: `IntStream.range(0, rowCount).parallel().forEach(...)` processes rows in arbitrary order. The `AtomicInteger` counters assign output array indices atomically, but the indices are NOT aligned with input row order. For example, input row 0 may get output index 47 while input row 47 gets output index 0. This breaks: (1) sorted data ordering, (2) running total/cumulative computations, (3) any downstream component expecting rows in input order. |
| BUG-MAP-005 | **P1** | `src/v1/engine/components/transform/map.py:970` | **Output array allocated at `rowCount` size but may be sparse**: `Object[][] output_data = new Object[rowCount][num_cols]` allocates an array sized for ALL input rows, but only `count.getAndIncrement()` rows are actually populated (when filters exclude rows). The Java-side code must handle the sparse array correctly during Arrow serialization. If the bridge reads the full `rowCount` entries, it includes null/empty rows. This depends on the Java `executeCompiledTMap` implementation reading only `count.get()` rows, which is assumed but not verified from the Python side. |
| BUG-MAP-006 | **P1** | `src/v1/engine/components/transform/map.py:1007` | **Variable Map is local to each parallel thread**: The generated script creates `Map<String, Object> Var = new HashMap<>()` inside the parallel forEach lambda. This is CORRECT for thread safety (each thread has its own Var map), but it means variables are NOT shared across rows. This matches Talend behavior (variables are per-row). However, if a variable expression references `globalMap.put()`, concurrent writes to globalMap could race. The script does not protect globalMap writes. |
| BUG-MAP-007 | **P2** | `src/v1/engine/components/transform/map.py:301` | **Simple lookup filter uses `== True` comparison**: The code `lookup_df[lookup_df[column] == True].copy()` only works for boolean columns. If the filter expression evaluates to a non-boolean column reference (e.g., a string column name), this comparison will exclude all rows. The filter should evaluate the expression to produce a boolean mask, not compare a column value to True. |
| BUG-MAP-008 | **P2** | `src/v1/engine/components/transform/map.py:641-643` | **Fuzzy column name matching uses `startswith(column)`**: When looking for a join key column, the fallback searches for columns starting with the column name. For example, searching for column `id` would match `id`, `id_name`, `id_type`, etc. The first match is used, which may be the wrong column. This should use exact matching or at minimum require a separator character after the column name. |
| BUG-MAP-009 | **P2** | `src/v1/java_bridge/bridge.py:390` | **`print()` statement in production code**: `print(f"Processing {total_rows} rows in chunks of {chunk_size}...")` on line 390, and `print(f"  Chunk {chunk_idx + 1}/{num_chunks}: ...")` on line 403, and `print(f"  Output '{output_name}': {len(output_dfs[output_name])} total rows")` on line 438. These are debug print statements that should use `logger.info()` instead. They bypass the logging framework and cannot be controlled by log level configuration. |
| BUG-MAP-010 | **P2** | `src/v1/engine/components/transform/map.py:200-203` | **`_update_stats()` does not track reject count**: `_update_stats(rows_read=len(main_df), rows_ok=total_output_rows)` never passes `rows_reject`. The base class defaults `NB_LINE_REJECT` to 0. Even when rows are routed to reject outputs, the reject count is not updated. This means `{id}_NB_LINE_REJECT` is always 0 in globalMap. |
| BUG-MAP-011 | **P3** | `src/v1/engine/components/transform/map.py:188-189` | **Commented-out debug code**: `# pd.set_option('display.max_rows', None)` and the following two lines are commented out but left in production code. Should be removed. |
| BUG-MAP-012 | **P3** | `src/v1/engine/components/transform/map.py:1077` | **Commented-out debug print in generated script**: `# lines.append("            System.err.println(...")` is commented out but the comment line itself is malformed with an unmatched closing paren and quote: `# lines.append("            System.err.println(\"[tMap Error] Row \" + i + \": \" + errorMsg);")")`. This is a syntax artifact that does not affect runtime but indicates hasty editing. |
| BUG-MAP-013 | **P0** | `src/converters/complex_converter/component_parser.py:428-509` | **`parse_base_component()` may return `None` for tMap**: The `return component` statement at line 509 of `component_parser.py` is indented inside the `else` block (lines 431-509). For tMap (which takes the `if` branch at line 428 via `components_with_dedicated_parsers`), execution falls through without a return statement, implicitly returning `None`. In `converter.py` line 227, `if not component:` catches `None` and silently skips the component. This makes all tMap components silently dropped during conversion, making the entire `parse_tmap()` function unreachable. **Fix**: Add `return component` at the function level after the if/else block. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-MAP-001 | **P2** | **`is_reject` vs `reject`**: The converter stores `is_reject` (line 656 of component_parser.py), but the Talend XML attribute is `reject`. The `is_` prefix is a reasonable Python convention but creates a naming gap from the source XML. |
| NAME-MAP-002 | **P2** | **`inner_join_reject` vs `rejectInnerJoin`**: The converter stores `inner_join_reject` (line 657), but the Talend XML attribute is `rejectInnerJoin`. The snake_case conversion is correct Python convention but the word order is reversed. |
| NAME-MAP-003 | **P3** | **`join_mode` derived from `innerJoin`**: The converter creates a synthetic `join_mode` field (`INNER_JOIN` / `LEFT_OUTER_JOIN`) from the boolean `innerJoin` attribute. This is a good abstraction but not directly traceable to the XML. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-MAP-001 | **P2** | "Variable types in Talend format" | Variable type is correctly kept as Talend format on line 617 (`id_String`), but line 611 also converts it to Python type via `convert_type()` and discards the result. Dead code. |
| STD-MAP-002 | **P2** | "`_validate_config()` returns `List[str]`" | `Map` class does not implement `_validate_config()`. There is no configuration validation before execution. Invalid configs (missing inputs, empty outputs) cause runtime errors deep in processing. |
| STD-MAP-003 | **P2** | "No `print()` statements" | `bridge.py` lines 390, 403, 438 contain `print()` statements in the tMap execution path. These bypass the logging framework. |
| STD-MAP-004 | **P3** | "Output type format uses Talend types" | Output column types are correctly kept in Talend format (line 643, 649 of parser; line 888 of engine). Good compliance. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-MAP-001 | **P3** | **Multiple commented-out debug statements in generated script**: Lines 1077, 1083, 1096, 1123 of map.py contain commented-out `lines.append("System.err.println(...)")` statements. These are artifacts from debugging the Java script generation. Should be removed for production clarity. |
| DBG-MAP-002 | **P3** | **Commented-out DataFrame logging**: Lines 188-189 contain `# pd.set_option(...)` and `# logger.info(...)` with `head().T` formatting. Development artifacts. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-MAP-001 | **P2** | **Generated Java script contains user-supplied expressions without sanitization**: `_generate_tmap_compiled_script()` directly injects user-supplied expressions into generated Java code (lines 1016, 1036, 1056). If a Talend job's expression contains malicious Java code (e.g., `Runtime.getRuntime().exec("rm -rf /")`), it would be executed in the Java bridge JVM. This is mitigated by the fact that tMap expressions come from Talend-converted jobs where expressions are trusted, but the lack of sandboxing is noted for defense-in-depth. |
| SEC-MAP-002 | **P3** | **No resource limits on generated Java scripts**: The generated script has no timeout, memory limit, or CPU limit. A malicious or poorly-written expression could cause infinite loops or excessive memory consumption in the JVM. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[Component {self.id}]` format -- correct (though not using `[{self.id}]` bracket prefix consistently) |
| Level usage | INFO for phase transitions and row counts, DEBUG for column-level details, WARNING for missing data/columns, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs processing start (line 132); `execute()` does not explicitly log start. Outputs logged at end (lines 205-210). |
| Sensitive data | No sensitive data logged. DataFrame contents logged at DEBUG level with `head(5)` only -- acceptable |
| Print statements | **3 `print()` calls in `bridge.py`** (lines 390, 403, 438) -- violates standards |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Does not define tMap-specific exceptions. Uses generic `RuntimeError` (lines 375-377, 832-833). Should use `ConfigurationError` or `ComponentError` from `exceptions.py`. |
| Exception chaining | Not used consistently. `raise` on line 88 re-raises without context. Inner `raise` in Java bridge calls may lose original stack. |
| Die on error handling | Two-level try-catch in generated script: inner catch handles expression errors (die_on_error logic), outer catch handles unexpected errors (always re-throws). Correct design. |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID and expression details -- good |
| Graceful degradation | Returns empty outputs on no input data (line 106) -- correct. Does NOT return empty outputs on expression errors when die_on_error=true -- correct (should fail). |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All major methods have return type hints -- correct |
| Parameter types | `_process()`, `_perform_lookups()`, `_evaluate_outputs_java()` all have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]`, `List[Dict]`, `Set` -- correct |
| Missing hints | `_generate_tmap_compiled_script()` return type `str` is correct. `_strip_java_marker()` return type `str` is correct. |

---

## 7. Performance & Memory

### 7.1 Performance Architecture

The Map component uses an optimized hybrid approach:

1. **Pandas for joins**: Vectorized merge operations leverage pandas C-optimized join algorithms. This is significantly faster than row-by-row join evaluation.

2. **Java for expressions**: Expression evaluation is compiled into Java bytecode and executed with `IntStream.parallel()`, leveraging multi-core parallelism.

3. **Compiled script**: The Java script is compiled ONCE and executed on multiple chunks, avoiding repeated compilation overhead.

4. **Arrow serialization**: Data transfer between Python and Java uses Apache Arrow, a zero-copy columnar format. This avoids row-by-row serialization costs.

5. **Chunked execution**: The 50K-row chunk size prevents exceeding the 2GB Arrow byte array limit.

### 7.2 Performance Issues

| ID | Priority | Issue |
|----|----------|-------|
| PERF-MAP-001 | **P1** | **Parallel stream execution trades correctness for speed**: The generated Java script uses `IntStream.range(0, rowCount).parallel().forEach(...)`. While this provides multi-core parallelism for expression evaluation, it introduces: (1) non-deterministic output order, (2) potential race conditions on shared state, (3) Thread pool contention with other parallel operations. For correctness-critical jobs, the parallel execution should be configurable or default to sequential. |
| PERF-MAP-002 | **P2** | **Hard-coded 50K chunk size**: `execute_compiled_tmap_chunked(chunk_size=50000)` on line 904 uses a fixed chunk size. This is not configurable and may be suboptimal for different data shapes: (1) Wide DataFrames with 100+ columns may exceed Arrow 2GB limit even at 50K rows. (2) Narrow DataFrames with few columns could safely use larger chunks for better throughput. (3) The chunk overhead (Arrow serialize, JVM call, Arrow deserialize) is ~10-50ms per chunk, so many small chunks add up. |
| PERF-MAP-003 | **P2** | **Arrow serialization overhead for every chunk**: Each chunk requires: Python DF -> Arrow Table -> Arrow bytes -> JVM -> Arrow bytes -> Arrow Table -> Python DF. For a 10M row job with 50K chunks, this is 200 serialization round trips. The overhead is approximately 10-50ms per chunk, so 2-10 seconds total for serialization alone. Consider larger chunk sizes for narrow DataFrames. |
| PERF-MAP-004 | **P2** | **Cartesian join has no size guard**: `joined_df.merge(lookup_df_prefixed, how='cross')` can produce M*N rows. If both sides are 100K rows, the result is 10B rows, consuming ~hundreds of GB of memory. There should be a configurable maximum cross-join size with a warning/error when exceeded. |
| PERF-MAP-005 | **P3** | **Inner join reject detection duplicates the join**: The inner join reject path (lines 480-489) performs a SECOND merge (`prev_df.merge(joined_df, how='left', indicator=True)`) to find unmatched rows. This doubles the join cost for inner joins. The correct approach is to use `indicator=True` on the PRIMARY merge and then split matched/unmatched rows in a single pass. |

### 7.3 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| DataFrame copies | Multiple `.copy()` calls throughout: `joined_df = main_df.copy()` (line 443), `prev_df = joined_df.copy()` (line 474), `lookup_df_prefixed = deduplicated_lookup_df.copy()` (line 692), `filtered_lookup = lookup_df.copy()` (line 527). These are necessary for correctness (avoid mutating originals) but double memory usage for large DataFrames. |
| Temporary columns | Join key columns (`_join_{lookup_name}_{idx}`) are added to `joined_df` and cleaned up after merge (line 716). Correct. |
| Chunk size | Fixed 50K rows per chunk. Reasonable for typical column counts (10-50). May need adjustment for very wide DataFrames. |
| Arrow serialization | Uses `_build_arrow_schema()` to correctly handle Decimal types. Avoids double-precision loss for BigDecimal columns. |
| No streaming mode | Unlike FileInputDelimited, Map does not have a streaming mode. The entire joined DataFrame must fit in memory before chunked Java execution. This is a limitation for very large join results. |
| Empty DataFrame handling | Returns empty DataFrames for outputs when no input data is available (line 106). Correct. |

### 7.4 Chunked Execution Edge Cases

| Issue | Description |
|-------|-------------|
| **Row order across chunks** | Rows are processed in chunk order (chunk 0 first, then chunk 1, etc.), preserving sequential chunk order. However, WITHIN each chunk, parallel execution makes row order non-deterministic. Net effect: partial ordering is preserved (rows from chunk 0 come before chunk 1), but within-chunk order is random. |
| **Variables across chunks** | Variables are per-row and do not carry state across rows or chunks. This is correct for Talend semantics. |
| **GlobalMap across chunks** | The bridge syncs context/globalMap AFTER all chunks complete (line 920). Changes to globalMap made by expressions in chunk 0 are NOT visible to chunk 1 during execution. If expressions rely on globalMap state modified by earlier rows, results may differ from Talend's sequential execution. |
| **Error accumulation** | Error tracking (`errorCount`, `errorMap`) is per-chunk in the generated script. The bridge combines results from all chunks, but error indices are chunk-relative, not absolute. If an error occurs in chunk 2 at row 5, it's reported as row 5, not row 100005 (assuming 50K chunk size). |
| **Output concatenation** | `pd.concat(df_list, ignore_index=True)` on bridge.py line 437 combines chunk results. `ignore_index=True` resets the index, which is correct. However, if output columns have different dtypes across chunks (e.g., first chunk has all nulls, second chunk has actual values), pandas may infer different dtypes, causing concat warnings or type coercion. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `Map` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests for tMap |
| V1 Java integration tests | Partial | `tests/v1/test_java_integration.py` | Tests Java bridge generally, not tMap specifically |

**Key finding**: The v1 engine has ZERO tests for this component. All 1164 lines of v1 engine code and the 170-line `parse_tmap()` converter method are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic 1-to-1 mapping | P0 | Main input with 3 columns, single output mapping all columns directly (`row1.col1`, `row1.col2`, `row1.col3`). Verify output matches input. |
| 2 | Single lookup LEFT_OUTER_JOIN | P0 | Main (10 rows) + lookup (5 rows) with left outer join on single key. Verify: 10 output rows, unmatched rows have NULL lookup columns. |
| 3 | Single lookup INNER_JOIN | P0 | Main (10 rows) + lookup (5 rows) with inner join on single key. Verify: only matching rows output, unmatched rows excluded. |
| 4 | Variable table evaluation | P0 | Define 3 variables: `var1 = row1.first + " " + row1.last`, `var2 = Var.var1.toUpperCase()`, `var3 = Var.var2.length()`. Verify all variables computed correctly and in order. |
| 5 | Output filter | P0 | Single output with filter `row1.age > 18`. Verify only rows matching filter are output. |
| 6 | Multiple outputs | P0 | Two outputs: Output1 with filter `row1.region == "EAST"`, Output2 with filter `row1.region == "WEST"`. Verify correct routing. |
| 7 | Empty input handling | P0 | Empty main input DataFrame. Verify empty output DataFrames returned without error. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Inner join reject output | P1 | Main + lookup with INNER_JOIN. Output1 is main output. Output2 has `inner_join_reject=true`. Verify: matched rows go to Output1, unmatched rows go to Output2. |
| 9 | UNIQUE_MATCH behavior | P1 | Lookup with duplicate keys (key=1 appears 3 times with values A, B, C). Main row joins on key=1. Verify UNIQUE_MATCH returns value C (LAST match). |
| 10 | FIRST_MATCH behavior | P1 | Same duplicate lookup. Verify FIRST_MATCH returns value A (first match). |
| 11 | ALL_MATCHES behavior | P1 | Same duplicate lookup. Verify ALL_MATCHES returns 3 output rows (one for each match). |
| 12 | Chained lookups | P1 | Lookup1 adds `customer_name`. Lookup2 joins on `lookup1.customer_name` to add `customer_region`. Verify Lookup2 can reference Lookup1's columns. |
| 13 | Context variables in expressions | P1 | Join key expression `context.region`. Verify context value is used for join matching. |
| 14 | Cartesian join | P1 | All join keys are context-only expressions. Verify cross join with context-based filtering produces correct results. |
| 15 | Die on error = true | P1 | Expression that causes NullPointerException. Verify job fails with descriptive error. |
| 16 | Die on error = false | P1 | Same error expression. Verify: error rows go to reject output, non-error rows go to main output. |
| 17 | Reject output (is_reject) | P1 | Output1 with filter, Output2 with `is_reject=true`. Verify rows failing Output1's filter go to Output2. |
| 18 | Multiple join keys | P1 | Join on two columns simultaneously. Verify both keys must match for the join to succeed. |
| 19 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` and `{id}_NB_LINE_OK` are set correctly in globalMap after execution. |
| 20 | Lookup filter (pre-join) | P1 | Lookup with filter `lookup.status == "active"`. Verify only active lookup rows participate in join. |
| 21 | Null handling in joins | P1 | Main row with NULL join key. Verify it does NOT match any lookup row (SQL NULL semantics). |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 22 | Large dataset (50K+ rows) | P2 | Verify chunked execution produces correct results across chunk boundaries. |
| 23 | Wide DataFrame (100+ columns) | P2 | Verify Arrow serialization handles wide DataFrames without exceeding limits. |
| 24 | Multiple inner joins | P2 | Two lookups both with INNER_JOIN. Verify reject output captures rows rejected by either join. |
| 25 | Empty lookup + LEFT_OUTER_JOIN | P2 | Lookup table is empty after filtering. Verify main rows preserved with NULL lookup columns. |
| 26 | Empty lookup + INNER_JOIN | P2 | Lookup table is empty. Verify all main rows rejected. |
| 27 | String concatenation expression | P2 | Output column: `row1.first + " " + lookup1.last`. Verify Java string concatenation works correctly. |
| 28 | Ternary expression | P2 | Output column: `row1.value != null ? row1.value : "default"`. Verify ternary operator evaluation. |
| 29 | Routine call expression | P2 | Output column: `TalendString.replaceAll(row1.name, "[^a-zA-Z]", "")`. Verify routine invocation works. |
| 30 | Row order preservation | P2 | Input rows in specific order. Verify output rows maintain same order (tests parallel execution issue). |
| 31 | Decimal precision in expressions | P2 | Output column: `new java.math.BigDecimal("123.456789012345")`. Verify precision preserved through Arrow roundtrip. |
| 32 | Date formatting expression | P2 | Output column: `TalendDate.formatDate("yyyy-MM-dd", row1.date)`. Verify date formatting works with loaded routines. |
| 33 | Multiple inner join rejects | P2 | Two lookups with INNER_JOIN. Verify reject output captures rows from BOTH rejections. |
| 34 | Variable referencing prior variable | P2 | `var1 = row1.a + row1.b`, `var2 = (String)Var.get("var1") + "_suffix"`. Verify ordered evaluation. |
| 35 | Concurrent tMap instances | P2 | Two tMap components in same job executing sequentially. Verify no state leakage between instances. |

#### P3 -- Edge Cases

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 36 | Lookup column name with dots | P3 | Lookup column named `address.city`. Verify no confusion with `lookupname.columnname` prefix pattern. |
| 37 | Very long expression | P3 | Expression with 500+ characters. Verify generated Java script compiles without issues. |
| 38 | Unicode in column values | P3 | Column values with CJK, emoji, RTL characters. Verify Arrow roundtrip preserves encoding. |
| 39 | Boolean filter column | P3 | Simple filter: `row1.is_active` (boolean column). Verify simple column ref path works for booleans. |
| 40 | Null in every lookup column | P3 | Left join where lookup returns all NULLs for unmatched rows. Verify NULL propagation. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-MAP-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-MAP-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| BUG-MAP-013 | Bug | `parse_base_component()` may return `None` for tMap. The `return component` at line 509 is inside the `else` block; tMap takes the `if` branch and falls through returning `None`. All tMap components are silently dropped during conversion, making `parse_tmap()` unreachable. |
| CONV-MAP-001 | Converter | `DIE_ON_ERROR` never extracted for tMap. `parse_base_component()` skips generic extraction for tMap, and `parse_tmap()` does not extract it either. Engine defaults to `true`, ignoring the Talend job's actual setting. Jobs with `DIE_ON_ERROR=false` will die on expression errors instead of routing to reject. |
| ENG-MAP-001 | Engine | Inner join reject detection is fundamentally flawed. Uses full-DataFrame left merge to find unmatched rows, which is expensive, fragile, and produces incorrect results when column values change during join or contain NaN. |
| TEST-MAP-001 | Testing | Zero v1 unit tests for the most complex component in the entire engine. All 1164 lines of engine code and 170 lines of converter code are completely unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-MAP-002 | Converter | `catch_output_reject` (`activateCondensedTool`) not extracted. Filter-reject chaining between outputs is missing. |
| CONV-MAP-003 | Converter | `STORE_ON_DISK` / `TEMP_DATA_DIR` / `MAX_BUFFER_SIZE` not extracted. Large lookups may cause OOM. |
| CONV-MAP-004 | Converter | `lookup_mode` extracted but ignored by engine. RELOAD_AT_EACH_ROW silently behaves as LOAD_ONCE. |
| ENG-MAP-002 | Engine | RELOAD_AT_EACH_ROW not implemented. Jobs with parameterized lookup queries produce wrong results. |
| ENG-MAP-003 | Engine | Catch output reject not implemented. Rows rejected by one output's filter are lost instead of being routed to the next output. |
| ENG-MAP-004 | Engine | Parallel `forEach` makes output row order non-deterministic. Breaks sorted data, running totals, and any order-dependent downstream processing. |
| ENG-MAP-005 | Engine | Variable evaluation in parallel is unsafe for stateful expressions (e.g., `globalMap.put()`). |
| ENG-MAP-006 | Engine | Die on error value never extracted by converter. Engine defaults to `true`, ignoring Talend job's actual setting. Same root cause as CONV-MAP-001. |
| BUG-MAP-003 | Bug | Inner join reject detection merges on ALL columns, which is expensive and produces incorrect results. |
| BUG-MAP-004 | Bug | Parallel stream execution makes output row order non-deterministic. |
| BUG-MAP-005 | Bug | Output array allocated at `rowCount` size but may be sparse. Depends on Java bridge reading only `count.get()` entries. |
| BUG-MAP-006 | Bug | Variable Map is local to parallel threads (correct), but globalMap writes in variable expressions race without synchronization. |
| PERF-MAP-001 | Performance | Parallel stream execution trades correctness for speed. Should be configurable. |
| TEST-MAP-002 | Testing | No integration test for tMap in a multi-step v1 job. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-MAP-005 | Converter | Dead code: `convert_type()` called on line 611 but result discarded. |
| CONV-MAP-006 | Converter | `matching_mode` extracted for main input but meaningless (only applies to lookups). |
| CONV-MAP-007 | Converter | Missing `length`, `precision`, `pattern` extraction for output columns. |
| ENG-MAP-007 | Engine | Reject output does not include `errorCode` and `errorMessage` columns. |
| ENG-MAP-008 | Engine | Cartesian join has no size guard. M*N row explosion can cause OOM. |
| ENG-MAP-009 | Engine | Empty lookup table handling differs from Talend. Skip behavior loses lookup column placeholders. |
| ENG-MAP-010 | Engine | Column name collision possible on multiple lookups with same name. |
| ENG-MAP-011 | Engine | Fuzzy `startswith(column)` matching for join key columns can match wrong column. |
| BUG-MAP-007 | Bug | Simple lookup filter uses `== True` comparison, only works for boolean columns. |
| BUG-MAP-008 | Bug | Fuzzy column name matching with `startswith(column)` can match wrong column. |
| BUG-MAP-009 | Bug | `print()` statements in `bridge.py` lines 390, 403, 438 bypass logging framework. |
| BUG-MAP-010 | Bug | `_update_stats()` does not track reject count. `NB_LINE_REJECT` always 0. |
| NAME-MAP-001 | Naming | `is_reject` vs Talend's `reject`. Python convention but naming gap. |
| NAME-MAP-002 | Naming | `inner_join_reject` vs Talend's `rejectInnerJoin`. Word order reversed. |
| STD-MAP-001 | Standards | Dead `convert_type()` call in variable parsing. |
| STD-MAP-002 | Standards | No `_validate_config()` implementation. Invalid configs cause runtime errors. |
| STD-MAP-003 | Standards | `print()` statements in bridge.py violate no-print standard. |
| SEC-MAP-001 | Security | Generated Java script injects user expressions without sanitization. |
| PERF-MAP-002 | Performance | Hard-coded 50K chunk size not configurable. |
| PERF-MAP-003 | Performance | Arrow serialization overhead per chunk (10-50ms * N chunks). |
| PERF-MAP-004 | Performance | Cartesian join has no size guard. |
| PERF-MAP-005 | Performance | Inner join reject detection doubles the join cost. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-MAP-008 | Converter | `TSTATCATCHER_STATS` not extracted (rarely used). |
| ENG-MAP-012 | Engine | Matching mode applied globally, not per-join-key-combination. Subtle difference for edge cases. |
| ENG-MAP-013 | Engine | No `{id}_ERROR_MESSAGE` globalMap variable. |
| NAME-MAP-003 | Naming | `join_mode` derived from `innerJoin`. Good abstraction but not directly traceable. |
| STD-MAP-004 | Standards | Output column types correctly kept in Talend format. Good compliance. (Positive finding.) |
| SEC-MAP-002 | Security | No resource limits on generated Java scripts. |
| BUG-MAP-011 | Bug | Commented-out debug code (pd.set_option). |
| BUG-MAP-012 | Bug | Commented-out System.err.println with malformed syntax in generated script. |
| DBG-MAP-001 | Debug | Multiple commented-out debug statements in generated Java script. |
| DBG-MAP-002 | Debug | Commented-out DataFrame logging in _process(). |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 6 | 3 bugs (2 cross-cutting + 1 converter/parser), 1 converter, 1 engine, 1 testing |
| P1 | 14 | 3 converter, 5 engine, 4 bugs, 1 performance, 1 testing |
| P2 | 21 | 3 converter, 5 engine, 4 bugs, 2 naming, 3 standards, 1 security, 3 performance |
| P3 | 10 | 1 converter, 2 engine, 2 bugs, 1 naming, 1 standards, 1 security, 2 debug |
| **Total** | **51** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-MAP-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, refactor the log line to use explicit stat references instead of the loop variable: `logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']}")`. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low.

2. **Fix `GlobalMap.get()` bug** (BUG-MAP-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()`. **Impact**: Fixes ALL components. **Risk**: Very low.

3. **Add `DIE_ON_ERROR` extraction to `parse_tmap()`** (CONV-MAP-001): `parse_base_component()` skips generic parameter extraction for tMap, so `DIE_ON_ERROR` is never extracted. Add the following to the config dict built on line 667:
   ```python
   die_on_error_elem = node.find('.//elementParameter[@name="DIE_ON_ERROR"]')
   die_on_error = die_on_error_elem.get('value', 'true').lower() == 'true' if die_on_error_elem is not None else True
   ```
   Then include `'die_on_error': die_on_error` in the config dict. **Impact**: Fixes incorrect die-on-error behavior for all tMap instances. **Risk**: Low.

4. **Fix `parse_base_component()` returning `None` for tMap** (BUG-MAP-013): The `return component` statement at line 509 is inside the `else` block. For tMap (which takes the `if` branch at line 428), execution falls through without a return, implicitly returning `None`. Add `return component` at the function level after the if/else block. **Impact**: Without this fix, all tMap components are silently dropped during conversion, making `parse_tmap()` unreachable. **Risk**: Very low.

5. **Fix inner join reject detection** (ENG-MAP-001, BUG-MAP-003): Replace the secondary merge approach with indicator-based tracking on the primary merge. In `_perform_normal_join()`, add `indicator=True` to the merge call (line 708). Then split the result:
   ```python
   result_df = joined_df.merge(lookup_df_prefixed, left_on=left_on, right_on=right_on_prefixed, how='left', indicator=True)
   inner_join_rejects = result_df[result_df['_merge'] == 'left_only'].drop(columns=['_merge']).copy()
   result_df = result_df[result_df['_merge'] != 'left_only'].drop(columns=['_merge'])
   ```
   Return rejects from `_perform_normal_join()` instead of detecting them after the fact. **Impact**: Fixes inner join reject correctness and eliminates the expensive secondary merge. **Risk**: Medium (requires refactoring the return value structure).

6. **Create unit test suite** (TEST-MAP-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic mapping, left/inner join, variable evaluation, output filter, multiple outputs, and empty input handling. **Impact**: Provides baseline verification for the most complex component. **Risk**: None.

### Short-Term (Hardening)

7. **Make parallel execution configurable** (ENG-MAP-004, BUG-MAP-004, PERF-MAP-001): Add a configuration option (e.g., `parallel_execution: true/false`) to control whether the generated Java script uses `IntStream.parallel()` or `IntStream.sequential()`. Default to sequential for correctness. Allow parallel for performance-critical jobs where row order does not matter. **Impact**: Fixes non-deterministic output ordering. **Risk**: Low (sequential is strictly safer).

8. **Extract `catch_output_reject`** (CONV-MAP-002): Parse the `activateCondensedTool` attribute from output table XML. Add `'catch_output_reject': output_xml.get('activateCondensedTool', 'false').lower() == 'true'` to the output config. Implement the chaining logic in the engine: when Output B has `catch_output_reject=true`, it receives rows that were excluded by the previous output's filter. **Impact**: Enables filter-reject chaining pattern. **Risk**: Medium (requires engine logic changes).

9. **Extract and validate `lookup_mode`** (CONV-MAP-004, ENG-MAP-002): The converter already extracts `lookup_mode`. Add engine validation: if `lookup_mode` is `RELOAD_AT_EACH_ROW` or `RELOAD_AT_EACH_ROW_CACHE`, log a WARNING that the mode is not supported and the lookup will behave as `LOAD_ONCE`. This at least makes the limitation visible. Full implementation of `RELOAD_AT_EACH_ROW` requires re-querying the lookup source per main row, which is a significant architectural change. **Impact**: Makes unsupported mode visible. **Risk**: Very low (warning only).

10. **Replace `print()` with `logger.info()`** (BUG-MAP-009, STD-MAP-003): Replace the three `print()` calls in `bridge.py` (lines 390, 403, 438) with `logger.info()` calls. This allows the output to be controlled by logging configuration. **Impact**: Improves production logging hygiene. **Risk**: Very low.

11. **Implement `_validate_config()`** (STD-MAP-002): Add configuration validation that checks:
    - `inputs.main` exists and has a `name`
    - Each lookup has at least one `join_key`
    - Each output has at least one `column`
    - Join key expressions are non-empty
    - Output column expressions are non-empty (or default to null)
    Call this at the beginning of `_process()`. **Impact**: Catches configuration errors early with descriptive messages. **Risk**: Low.

12. **Track reject count in `_update_stats()`** (BUG-MAP-010): After `_evaluate_and_route_outputs()` returns, calculate reject count as the sum of rows in reject-flagged outputs. Pass this to `_update_stats(rows_reject=reject_count)`. **Impact**: `NB_LINE_REJECT` globalMap variable becomes accurate. **Risk**: Low.

### Long-Term (Optimization)

13. **Implement store-temp-data-on-disk** (CONV-MAP-003): For large lookups, implement disk-based storage using a temporary SQLite database or memory-mapped file. When `STORE_ON_DISK=true`, write lookup data to disk after loading, and perform lookups via disk-based index. **Impact**: Enables processing of very large lookups without OOM. **Risk**: High (significant new infrastructure).

14. **Add cartesian join size guard** (ENG-MAP-008, PERF-MAP-004): Before performing a cross join, check `len(joined_df) * len(filtered_lookup)`. If the product exceeds a configurable threshold (e.g., 10 million rows), log a WARNING and optionally raise an error. **Impact**: Prevents accidental OOM from unbounded cross joins. **Risk**: Low.

15. **Fix empty lookup handling for LEFT_OUTER_JOIN** (ENG-MAP-009): When a lookup is empty and join mode is LEFT_OUTER_JOIN, instead of skipping the join, add NULL columns for all lookup columns. This preserves Talend behavior where unmatched rows have NULL lookup values. **Impact**: Correct behavior for empty lookups. **Risk**: Low.

16. **Make chunk size configurable** (PERF-MAP-002): Add `chunk_size` as a configurable parameter (via config or environment variable). Default to 50K but allow tuning for specific data shapes. **Impact**: Allows performance optimization. **Risk**: Very low.

17. **Add `errorCode` and `errorMessage` to reject output** (ENG-MAP-007): Modify the generated Java script to add two additional columns to reject output arrays. Populate `errorCode` with "EXPRESSION_ERROR" and `errorMessage` with the exception message from `errorMap`. **Impact**: Matches Talend reject schema. **Risk**: Medium.

18. **Implement RELOAD_AT_EACH_ROW** (ENG-MAP-002): This requires significant architectural changes. The current approach loads all lookups before processing. For RELOAD_AT_EACH_ROW, the lookup source must be re-queried per main row. Options: (a) For database lookups, execute parameterized SQL per row (requires database connection in the tMap component). (b) For file-based lookups, re-read the file per row (extremely expensive, rarely useful). (c) Hybrid: implement RELOAD_AT_EACH_ROW_CACHE first, which only re-queries when cache misses occur. **Impact**: Enables parameterized lookup pattern. **Risk**: High.

19. **Remove dead code and debug artifacts** (CONV-MAP-005, BUG-MAP-011, BUG-MAP-012, DBG-MAP-001, DBG-MAP-002): Remove the dead `convert_type()` call on line 611, commented-out debug code, and print statements. **Impact**: Cleaner codebase. **Risk**: Very low.

20. **Add security sandboxing for generated Java** (SEC-MAP-001): Consider running generated Java scripts in a sandboxed ClassLoader with restricted permissions (no file system access, no network access, no process execution). **Impact**: Defense-in-depth against malicious expressions. **Risk**: Medium.

21. **Create integration test** (TEST-MAP-002): Build an end-to-end test exercising `tFileInputDelimited -> tMap (with lookup) -> tFileOutputDelimited` in the v1 engine, verifying context resolution, Java bridge integration, globalMap propagation, and multi-output routing.

---

## 11. Risk Assessment

### 11.1 Production Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| GlobalMap.get() crash (BUG-MAP-002) | **Certain** | **High** -- crashes any component using globalMap.get() | Fix the method signature immediately |
| _update_global_map() crash (BUG-MAP-001) | **Certain** | **High** -- crashes any component after execution | Fix the variable reference immediately |
| DIE_ON_ERROR=false not working (CONV-MAP-001) | **High** (any job with explicit die_on_error setting) | **High** -- jobs crash instead of routing to reject | Add DIE_ON_ERROR extraction to parse_tmap() |
| Wrong results from RELOAD_AT_EACH_ROW (ENG-MAP-002) | **Medium** (depends on job design) | **High** -- silently wrong data | Add warning log; full implementation is complex |
| Non-deterministic output order (ENG-MAP-004) | **Certain** | **Medium** -- affects ordered data | Make parallel execution configurable |
| Inner join reject wrong results (ENG-MAP-001) | **Medium** (depends on data shape) | **High** -- wrong reject routing | Rewrite using indicator-based approach |
| Cartesian join OOM (ENG-MAP-008) | **Low** (requires specific job design) | **Critical** -- JVM/process crash | Add size guard with configurable limit |
| Arrow 2GB limit for wide DFs (PERF-MAP-002) | **Low** (requires 500+ columns) | **High** -- serialization failure | Make chunk size adaptive to column count |

### 11.2 Jobs Most at Risk

1. **Jobs with `DIE_ON_ERROR=false`**: Will incorrectly die on expression errors instead of routing to reject. This is the highest-risk scenario because it silently changes error handling behavior.

2. **Jobs using `RELOAD_AT_EACH_ROW`**: Will silently use stale lookup data. The first row's lookup data will be used for all subsequent rows. This produces subtly wrong results that may not be immediately obvious.

3. **Jobs requiring deterministic output order**: Any downstream component that depends on row ordering (e.g., `tFileOutputDelimited` with sorted output, running totals, sequential numbering) will produce different results due to parallel execution non-determinism.

4. **Jobs using `catch_output_reject`**: The filter-reject chaining pattern is completely missing. Rows rejected by one output's filter are lost instead of being routed to the next output.

5. **Jobs with multiple INNER_JOINs**: Inner join reject detection may produce wrong results, routing matched rows to reject or vice versa.

### 11.3 Safe Usage Patterns

The V1 tMap implementation is safe for the following patterns:
- Simple column pass-through mapping (no expressions)
- Single lookup with LEFT_OUTER_JOIN and LOAD_ONCE
- FIRST_MATCH / LAST_MATCH / ALL_MATCHES with LOAD_ONCE
- Single output with simple filter expressions
- Context variable references in expressions
- GlobalMap reads in expressions (not writes)
- Routine calls that are pure functions (no side effects)

---

## Appendix A: Converter `parse_tmap()` Code

```python
# component_parser.py lines 511-681
def parse_tmap(self, node, component: Dict) -> Dict:
    """
    Parse tMap specific configuration to match new JSON structure
    """
    # Look for nodeData element with MapperData type
    mapper_data = None
    for node_data in node.findall('.//nodeData'):
        if 'MapperData' in node_data.get('{http://www.w3.org/2001/XMLSchema-instance}type', ''):
            mapper_data = node_data
            break

    if not mapper_data:
        mapper_data = node.find('.//MapperData')

    if not mapper_data:
        return component

    # PHASE 1: Parse inputTables
    input_tables_xml = mapper_data.findall('.//inputTables')
    # First input is MAIN, rest are LOOKUPS
    main_input_xml = input_tables_xml[0]
    main_name = main_input_xml.get('name', '')
    # ... (filter, matching_mode, lookup_mode extraction)

    # Parse lookup join keys, filters, join_mode
    for lookup_xml in input_tables_xml[1:]:
        # ... (join_keys from mapperTableEntries with expression)
        join_mode = "INNER_JOIN" if innerJoin else "LEFT_OUTER_JOIN"

    # PHASE 2: Parse varTables
    for var_table in mapper_data.findall('./varTables'):
        for var_entry in var_table.findall('./mapperTableEntries'):
            # name, expression ({{java}} prefixed), type (Talend format)

    # PHASE 3: Parse outputTables
    for output_xml in mapper_data.findall('./outputTables'):
        # name, reject, rejectInnerJoin, filter, columns
        # Columns: name, expression ({{java}} prefixed), type (Talend format), nullable

    # Build final config -- OVERWRITES component['config']
    component['config'] = {
        'inputs': {'main': main_config, 'lookups': lookups_config},
        'variables': variables_config,
        'outputs': outputs_config
    }
    # NOTE: DIE_ON_ERROR is never extracted -- generic pass skips tMap, and parse_tmap() does not extract it
```

**Critical issue**: `parse_base_component()` has an explicit skip for tMap in `components_with_dedicated_parsers` (lines 420-430), so the generic parameter extraction never runs. `DIE_ON_ERROR` is never extracted in the first place, and `parse_tmap()` does not extract it either.

---

## Appendix B: Engine Class Structure

```
Map (BaseComponent)
    Constants:
        SIMPLE_COLUMN_PATTERN = re.compile(r'^([a-zA-Z_]...)$')

    Overridden Methods:
        execute(input_data)                     # Overrides base: skips Java expr resolution, handles context only
        _process(input_data)                    # Main 4-phase pipeline

    Private Helper Methods:
        _strip_java_marker(expression)          # Remove {{java}} prefix
        _is_simple_column_ref(expression)       # Regex check for table.column pattern
        _parse_column_ref(expression)           # Extract (table, column) tuple
        _is_context_only_expression(expression) # Check for context-only (no row refs)

    Phase 1:
        _filter_lookups(inputs, lookups_config) # Pre-filter lookup tables

    Phase 2:
        _get_input_dataframes()                 # Extract inputs from current_input_data
        _perform_lookups(main_df, inputs, ...)  # Sequential lookup evaluation
        _perform_cartesian_join(...)            # Cross join with context filtering
        _perform_normal_join(...)               # Pandas merge with chained support

    Phase 3:
        _apply_matching_mode(lookup_df, ...)    # Deduplicate lookup by matching mode

    Phase 4:
        _evaluate_and_route_outputs(...)        # Orchestrate variable/output evaluation
        _evaluate_outputs_java(...)             # Compiled Java script execution
        _generate_tmap_compiled_script(...)     # Java code generation (200+ lines)

    Phase 5:
        _batch_evaluate_expressions(...)        # Batch Java expression evaluation (for filters/join keys)

    Utility:
        _create_empty_outputs()                 # Empty DataFrame dict for all outputs
```

---

## Appendix C: Generated Java Script Structure

The `_generate_tmap_compiled_script()` method generates a Java script with the following structure:

```java
// Imports
import java.util.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;
import com.citi.gru.etl.RowWrapper;

// Output array allocation (one per output)
Object[][] output1_data = new Object[rowCount][numCols1];
AtomicInteger output1_count = new AtomicInteger(0);

// Error tracking (die_on_error=false only)
AtomicInteger errorCount = new AtomicInteger(0);
ConcurrentHashMap<Integer, String> errorMap = new ConcurrentHashMap<>();

// Parallel processing loop
IntStream.range(0, rowCount).parallel().forEach(i -> {
    try {
        // Create RowWrappers (one per input table)
        RowWrapper main = new RowWrapper(inputRoot, i, "main");
        RowWrapper lookup1 = new RowWrapper(inputRoot, i, "lookup1");

        boolean matchedAny = false;  // For reject routing

        try {
            // VARIABLES (evaluated in order)
            Map<String, Object> Var = new HashMap<>();
            Var.put("var1", main.col1 + " " + main.col2);
            Var.put("var2", ((String)Var.get("var1")).toUpperCase());

            // OUTPUT 1 (with filter)
            if (main.age > 18) {
                Object[] output1_tempRow = new Object[numCols1];
                output1_tempRow[0] = main.col1;
                output1_tempRow[1] = Var.get("var2");
                matchedAny = true;
                int idx = output1_count.getAndIncrement();
                output1_data[idx] = output1_tempRow;
            }

        } catch (Exception e) {
            // die_on_error=true: re-throw
            // die_on_error=false: track error, matchedAny stays false
        }

        // REJECT OUTPUT (outside inner try-catch)
        if (!matchedAny) {
            Object[] reject_tempRow = new Object[numColsReject];
            reject_tempRow[0] = main.col1;  // Original data
            int idx = reject_count.getAndIncrement();
            reject_data[idx] = reject_tempRow;
        }

    } catch (Exception outerE) {
        throw new RuntimeException("Error at row " + i + " (outer): " + outerE.getMessage(), outerE);
    }
});

// Return results
Map<String, Map<String, Object>> results = new HashMap<>();
// ... populate results map with data arrays and counts
return results;
```

**Key design decisions**:
1. **Parallel execution**: `IntStream.parallel()` for multi-core utilization
2. **Two-level exception handling**: Inner catch for expression errors (configurable), outer catch for infrastructure errors (always fatal)
3. **Atomic counters**: `AtomicInteger` for thread-safe output indexing
4. **Pre-sized arrays**: Output arrays allocated at `rowCount` size (may be sparse when filters exclude rows)
5. **RowWrapper abstraction**: Each input table gets a RowWrapper that knows its table name for column lookup
6. **matchedAny flag**: Tracks whether a row matched any non-reject output, used for reject routing

---

## Appendix D: Talend tMap Feature to V1 Implementation Cross-Reference

| Talend Feature | Converter Status | Engine Status | Priority to Fix |
|----------------|-----------------|---------------|-----------------|
| Main input | Extracted | Implemented | -- |
| Main input filter | Extracted | Implemented | -- |
| Lookup inputs (multiple) | Extracted | Implemented | -- |
| Lookup filter | Extracted | Implemented | -- |
| Join: LEFT_OUTER_JOIN | Extracted | Implemented | -- |
| Join: INNER_JOIN | Extracted | Implemented | -- |
| Matching: UNIQUE_MATCH | Extracted | Implemented (LAST match) | -- |
| Matching: FIRST_MATCH | Extracted | Implemented | -- |
| Matching: LAST_MATCH | Extracted | Implemented | -- |
| Matching: ALL_MATCHES | Extracted | Implemented | -- |
| Lookup mode: LOAD_ONCE | Extracted | Implemented (default) | -- |
| Lookup mode: RELOAD_AT_EACH_ROW | Extracted | **NOT Implemented** | P1 |
| Lookup mode: RELOAD_AT_EACH_ROW_CACHE | Extracted | **NOT Implemented** | P1 |
| Variable table | Extracted | Implemented | -- |
| Multiple outputs | Extracted | Implemented | -- |
| Output filter | Extracted | Implemented | -- |
| Output: is_reject | Extracted | Implemented | -- |
| Output: inner_join_reject | Extracted | Implemented (fragile) | P0 |
| Output: catch_output_reject | **NOT Extracted** | **NOT Implemented** | P1 |
| DIE_ON_ERROR | **Never extracted** | Implemented (wrong default) | P0 |
| Store temp data on disk | **NOT Extracted** | **NOT Implemented** | P1 |
| Temp data directory | **NOT Extracted** | **NOT Implemented** | P1 |
| Max buffer size | **NOT Extracted** | **NOT Implemented** | P2 |
| REJECT with errorCode/errorMessage | N/A | **NOT Implemented** | P2 |
| Cartesian join | Extracted (implicit) | Implemented | -- |
| Chained lookups | Extracted (implicit) | Implemented | -- |
| Context variables in expressions | Extracted | Implemented | -- |
| GlobalMap integration | Extracted | Implemented | -- |
| Routine calls in expressions | Extracted (pass-through) | Implemented (via Java bridge) | -- |
| tStatCatcher statistics | **NOT Extracted** | **NOT Implemented** | P3 |

---

## Appendix E: Java Bridge Interaction Detail

### E.1 Expression Evaluation via `_batch_evaluate_expressions()`

The `_batch_evaluate_expressions()` method (lines 350-417) is used for:
- Main input filter evaluation
- Lookup filter evaluation
- Complex join key evaluation

**Flow**:
1. Validates Java bridge is available (line 374)
2. Flattens context variables from nested dict to flat dict (lines 385-396)
3. Syncs flattened context to Java bridge via `set_context()` (lines 398-399)
4. Syncs globalMap to Java bridge via `set_global_map()` (lines 401-403)
5. Calls `java_bridge.execute_tmap_preprocessing()` with:
   - `df`: DataFrame to evaluate against
   - `expressions`: dict of `{expr_id: expression_string}`
   - `main_table_name`: name of the main input table
   - `lookup_table_names`: list of already-joined lookup names
6. Returns dict of `{expr_id: result_array}`

**Context flattening detail** (lines 385-396):
```python
# Input: {'default': {'region': {'value': 'EAST', 'type': 'id_String'}, ...}}
# Output: {'region': 'EAST', ...}
for context_name, context_vars in context_all.items():
    if isinstance(context_vars, dict):
        for var_name, var_info in context_vars.items():
            if isinstance(var_info, dict) and 'value' in var_info:
                flattened_context[var_name] = var_info['value']
            else:
                flattened_context[var_name] = var_info
```

**Issue**: The flattening logic handles two context structures: `{name: {value: ..., type: ...}}` and `{name: value}`. If context variables have duplicate names across different context groups (e.g., `default.region` and `job.region`), the last one wins silently.

### E.2 Compiled Script Execution Pipeline

The compiled script execution uses a two-step pipeline:

**Step 1: Compilation** (`compile_tmap_script()` in bridge.py lines 323-368):
1. Converts Python `output_schemas` dict to Java `Map<String, List<String>>` via Py4J `ListConverter`
2. Converts Python `lookup_names` list to Java `List<String>` via Py4J `ListConverter`
3. Calls `java_bridge.compileTMapScript()` on the JVM
4. Returns component_id as confirmation

**Step 2: Chunked Execution** (`execute_compiled_tmap_chunked()` in bridge.py lines 370-442):
1. Calculates number of chunks: `ceil(total_rows / chunk_size)`
2. For each chunk:
   a. Extracts chunk: `df.iloc[start_idx:end_idx]`
   b. Builds Arrow schema using `_build_arrow_schema()` -- handles Decimal types specially
   c. Serializes to Arrow IPC format: `pa.ipc.new_stream(sink, schema)`
   d. Gets raw bytes: `sink.getvalue().to_pybytes()`
   e. Calls `java_bridge.executeCompiledTMap(component_id, arrow_bytes, context, globalmap)`
   f. For each output in result_map:
      - Deserializes Arrow bytes: `pa.ipc.open_stream(pa.py_buffer(output_bytes))`
      - Converts to pandas: `result_table.to_pandas()`
      - Appends to accumulation list
3. Concatenates all chunks: `pd.concat(df_list, ignore_index=True)`

**Arrow schema handling** (`_build_arrow_schema()` in bridge.py lines 538-580):
- `object` dtype columns: inspects first non-null value to determine Arrow type
  - `Decimal` instance -> `pa.decimal128(precision, scale)` with inferred precision
  - `str` instance -> `pa.string()`
  - Other -> `pa.string()`
- `int` dtypes -> `pa.int64()`
- `float` dtypes -> `pa.float64()`
- `bool` dtype -> `pa.bool_()`
- `datetime64` -> `pa.timestamp('ns')`
- Fallback -> `pa.string()`

**Issue**: The Decimal precision/scale inference scans the entire column to find max precision. For large DataFrames, this is expensive. Also, if the first non-null value is a Decimal but later values are strings (due to mixed types), the Arrow schema will be wrong.

### E.3 Context and GlobalMap Synchronization

**Python-to-Java sync** (before execution):
- Context: `java_bridge.set_context(key, value)` for each flattened context variable
- GlobalMap: `java_bridge.set_global_map(key, value)` for each globalMap entry

**Java-to-Python sync** (after execution):
- `java_bridge._sync_from_java()` calls `java_bridge.getContext()` and `java_bridge.getGlobalMap()`
- Updates `java_bridge.context` and `java_bridge.global_map` Python dicts
- Then `_evaluate_outputs_java()` propagates to ContextManager and GlobalMap

**Issue**: The sync is bi-directional but NOT transactional. If the Java execution fails after modifying context/globalMap, the partial changes may or may not be synced back depending on where the exception occurs. The `_sync_from_java()` call is INSIDE the try block (line 920), so it runs on success only. On failure, context/globalMap changes from the partial execution are lost.

---

## Appendix F: Execution Flow Diagram

```
                    +-------------------+
                    |   Map.execute()   |
                    |  (override base)  |
                    +--------+----------+
                             |
                    1. Resolve context vars
                    2. Call _process()
                             |
                    +--------v----------+
                    |   _process()      |
                    +--------+----------+
                             |
          +------------------+------------------+
          |                  |                  |
   +------v------+   +------v------+   +------v------+
   |  Phase 1:   |   |  Phase 2:   |   |  Phase 4:   |
   |  Filter     |   |  Main filter|   |  Variables  |
   |  Lookups    |   |  + Lookups  |   |  + Outputs  |
   +------+------+   +------+------+   +------+------+
          |                  |                  |
   _filter_lookups()  _perform_lookups()  _evaluate_and_route_outputs()
          |                  |                  |
          |          +-------+-------+    +-----+------+
          |          |               |    |            |
          |   _perform_       _perform_   _evaluate_   Handle inner
          |   normal_join()   cartesian_  outputs_     join rejects
          |          |        join()      java()
          |          |                         |
          |   _apply_matching_           +-----+------+
          |   mode()                     |            |
          |                        _generate_    compile +
          |                        tmap_         execute
          |                        compiled_     chunked
          |                        script()
          |
   [Java bridge]                  [Java bridge]
   _batch_evaluate_               compile_tmap_script()
   expressions()                  execute_compiled_tmap_chunked()
```

---

## Appendix G: Data Flow Through tMap Engine

```
Input:
  main_df (N rows)  +  lookup1_df (M rows)  +  lookup2_df (K rows)
                           |                         |
                    Phase 1: Filter lookups
                           |                         |
                    lookup1_filtered (M' rows)  lookup2_filtered (K' rows)
                           |                         |
                    Phase 2: Main filter
                           |
                    main_filtered (N' rows)
                           |
                    Phase 2b: Join lookup1
                           |
                    joined_df = main_filtered.merge(lookup1, how=left/inner)
                    (N'' rows, with lookup1 columns prefixed)
                           |
                    Phase 2c: Join lookup2 (chained)
                           |
                    joined_df = joined_df.merge(lookup2, how=left/inner)
                    (N''' rows, with both lookup columns)
                           |
                    Phase 3: Track inner join rejects (if INNER_JOIN)
                           |
                    inner_join_rejects_df (unmatched main rows)
                           |
                    Phase 4: Variables + Outputs (Java)
                           |
              +------- Chunk 1 (0..50K) --------+
              |            ...                    |
              +------- Chunk N (last batch) -----+
                           |
              Per chunk: RowWrapper per table
                         Variables evaluated in order
                         Each output evaluated with filter
                         Reject routing via matchedAny flag
                           |
Output:
  output1_df  +  output2_df  +  reject_df  +  inner_join_reject_df
```

---

## Appendix H: Known Talend tMap Patterns and V1 Support Status

| Pattern | Description | V1 Supported? | Notes |
|---------|-------------|---------------|-------|
| Simple column pass-through | `output.col = input.col` | Yes | Optimized: simple column ref detection skips Java |
| Expression transformation | `output.full_name = input.first + " " + input.last` | Yes | Evaluated via Java bridge |
| Conditional mapping | `output.status = input.age >= 18 ? "adult" : "minor"` | Yes | Java ternary operator |
| Lookup enrichment | Left join to add lookup columns | Yes | pandas merge with `how='left'` |
| Lookup validation | Inner join to filter rows with valid references | Yes | pandas merge with `how='inner'` |
| Multi-lookup chaining | Lookup1 result used in Lookup2's join key | Yes | Sequential lookup evaluation |
| Filter routing | Multiple outputs with different filters | Yes | Generated Java if-statements |
| Reject capture | Inner join rejects routed to separate output | Partial | Detection logic is fragile (see ENG-MAP-001) |
| Error capture | Expression errors routed to reject | Yes (when die_on_error works) | Requires DIE_ON_ERROR fix (CONV-MAP-001) |
| Context-based cartesian | Join key is `context.var`, not row data | Yes | Cross join with context filtering |
| Null-safe expression | `input.col != null ? input.col.trim() : ""` | Yes | Java null handling |
| Routine call | `TalendDate.formatDate("yyyy-MM-dd", input.date)` | Yes | Via Java bridge routine loading |
| GlobalMap read | `((String)globalMap.get("tFileList_1_CURRENT_FILE"))` | Yes | GlobalMap synced to Java |
| GlobalMap write | `globalMap.put("key", value)` in variable | Partial | Race condition in parallel execution |
| Parameterized lookup | RELOAD_AT_EACH_ROW with dynamic query | **No** | Not implemented |
| Large lookup on disk | STORE_ON_DISK for memory-constrained lookups | **No** | Not implemented |
| Filter-reject chaining | catch_output_reject between outputs | **No** | Not implemented |

---

## Appendix I: Input Data Routing Analysis

### I.1 How tMap Receives Multiple Inputs

The V1 engine's `_get_input_data()` method (engine.py lines 779-795) handles multi-input components:

```python
def _get_input_data(self, comp_id: str) -> Optional[Any]:
    component = self.components[comp_id]
    if not component.inputs:
        return None
    if len(component.inputs) == 1:
        return self.data_flows.get(component.inputs[0])  # Single DF
    else:
        input_data = {}
        for input_flow in component.inputs:
            input_data[input_flow] = self.data_flows.get(input_flow)
        return input_data  # Dict of {flow_name: DF}
```

For tMap, `component.inputs` is populated by the converter as:
```python
component['inputs'] = [main_name] + [lookup['name'] for lookup in lookups_config]
```

This means `component.inputs` contains flow NAMES (e.g., `['row1', 'row2', 'row3']`), which are used as keys to look up DataFrames in `self.data_flows`.

**Critical dependency**: The flow names in `component.inputs` must EXACTLY match the keys in `self.data_flows`. The data flows are populated by upstream components during execution. If an upstream component stores its output under a different key (e.g., `tFileInputDelimited_1_main` instead of `row1`), the tMap will not find the input data.

### I.2 How tMap Outputs Are Routed

The engine's output routing (engine.py lines 566-585) handles tMap's multiple outputs:

```python
# Standard flow/reject routing
for flow in self.job_config.get('flows', []):
    if flow['from'] == comp_id:
        if flow['type'] == 'flow' and 'main' in result:
            self.data_flows[flow['name']] = result['main']
        elif flow['type'] == 'reject' and 'reject' in result:
            self.data_flows[flow['name']] = result['reject']

# Named outputs (tMap uses this path)
for key, value in result.items():
    if key not in ['main', 'reject', 'stats'] and value is not None:
        if key in component.outputs:
            self.data_flows[key] = value  # Store by output name
        else:
            self.data_flows[f"{comp_id}_{key}"] = value
```

tMap returns a dict like `{'output1': df1, 'output2': df2, 'reject_out': df3}`. Since the keys match `component.outputs` (set by converter), they are stored directly by output name.

**Critical dependency**: The output names in the tMap config must match the flow names expected by downstream components. If a downstream component looks for input `output1`, the tMap must produce an output named exactly `output1`.

### I.3 Flow Name Consistency Analysis

| Stage | Name Source | Example | Potential Mismatch |
|-------|-------------|---------|-------------------|
| Converter: input table name | XML `inputTables@name` | `row1` | Must match upstream output flow name |
| Converter: lookup table name | XML `inputTables@name` (2nd+) | `row2` | Must match lookup source flow name |
| Converter: output table name | XML `outputTables@name` | `out1` | Must match downstream input flow name |
| Engine: component.inputs | Set by converter | `['row1', 'row2']` | Must match data_flows keys |
| Engine: component.outputs | Set by converter | `['out1', 'reject1']` | Must match result dict keys |
| Engine: data_flows keys | Set by upstream execution | `'row1'` | Must match component.inputs |

**Risk**: If the Talend XML uses different naming conventions for flow connections versus table names inside the Map Editor, the converter may produce inconsistent names. This is a converter correctness concern that is difficult to test without real Talend XML samples.

---

## Appendix J: `execute()` Override Analysis

The `Map` class overrides `BaseComponent.execute()` (lines 48-88). This is significant because it is the ONLY transform component that does so. The override changes the execution lifecycle:

### J.1 Base Class `execute()` Flow (not used by Map)

```python
# BaseComponent.execute() typical flow:
1. Set status = RUNNING
2. Resolve {{java}} expressions in config via _resolve_java_expressions()
3. Resolve ${context.var} in config via context_manager.resolve_dict()
4. Call _process(input_data)
5. Update stats
6. Update globalMap
7. Set status = SUCCESS
```

### J.2 Map `execute()` Flow (overridden)

```python
# Map.execute() flow:
1. Set status = RUNNING
2. START TIME
3. Resolve ${context.var} ONLY (NO {{java}} resolution)  # <-- KEY DIFFERENCE
4. Call _process(input_data)
5. Update EXECUTION_TIME stat
6. Call _update_global_map()  # <-- Called directly, not via base class
7. Set status = SUCCESS
8. Add stats to result dict  # <-- Additional step
9. Return result
```

### J.3 Why the Override is Necessary

The base class's `_resolve_java_expressions()` would attempt to evaluate ALL config values containing `{{java}}` markers BEFORE `_process()` runs. For tMap, this would fail because:

1. **tMap expressions reference row data** (e.g., `row1.customer_id`). These expressions cannot be evaluated without the actual DataFrame rows, which are only available during `_process()`.

2. **tMap expressions reference variables** (e.g., `Var.full_name`). Variables are computed per-row during Phase 4 and are not available during config resolution.

3. **tMap expressions reference lookup data** (e.g., `lookup1.customer_name`). Lookup data is only available after Phase 2 joins.

If the base class `_resolve_java_expressions()` were called, it would try to evaluate expressions like `{{java}}row1.customer_id + " " + lookup1.name` without any row context, causing NullPointerException or "variable not found" errors.

### J.4 Override Implications

The override has several implications:

1. **Context resolution still happens** (line 65): Simple `${context.var}` references in config values are resolved. This handles cases like `context.region` used in filter expressions or as join key values.

2. **`_update_global_map()` is called directly** (line 72): The base class normally calls this in `execute()`, but since the override replaces `execute()`, it must call it explicitly. This means the cross-cutting bug (BUG-MAP-001) affects Map through this direct call.

3. **Stats are added to result** (line 77): The override adds `result['stats'] = self.stats.copy()` to the return value. This is different from the base class flow where stats are accessed separately via `get_stats()`. The engine's `_execute_component()` accesses stats via `component.get_stats()` (engine.py line 588), so this additional stats-in-result is redundant but harmless.

4. **No `validate_schema()` call**: The base class's `execute()` may call `validate_schema()` for output schema enforcement. Map's override skips this entirely. Output column types are defined in the tMap config but not validated against the output schema. Type mismatches between tMap output columns and the output schema are not detected.

5. **Error handling is simplified**: The override catches `Exception` and re-raises after logging and setting error state. It does not distinguish between `ConfigurationError` and other exceptions. All errors are treated uniformly.

### J.5 Correctness of the Override

The override is NECESSARY and CORRECT for the reasons stated. However, it should be documented why it exists (currently only a brief docstring on line 50-53). Future maintainers may not understand why Map overrides `execute()` when no other component does.

**Recommendation**: Add a detailed comment block explaining the override rationale, specifically that tMap expressions reference row data that is only available during `_process()`, making pre-resolution impossible.

---

## Appendix K: Complete Talend tMap XML Structure Reference

For reference, here is the XML structure that the converter's `parse_tmap()` method parses:

```xml
<node componentName="tMap" componentVersion="0.102" offsetLabelX="0" offsetLabelY="0"
      posX="448" posY="176">

  <!-- Standard component parameters -->
  <elementParameter field="CHECK" name="DIE_ON_ERROR" value="true"/>
  <elementParameter field="CHECK" name="STORE_ON_DISK" value="false"/>
  <elementParameter field="DIRECTORY" name="TEMP_DATA_DIR" value=""/>
  <elementParameter field="TEXT" name="MAX_BUFFER_SIZE" value="2000000"/>

  <!-- MapperData is the core configuration -->
  <nodeData xsi:type="process:MapperData">

    <!-- Input tables (first = main, rest = lookups) -->
    <inputTables name="row1" matchingMode="UNIQUE_MATCH" lookupMode="LOAD_ONCE"
                 activateExpressionFilter="false" expressionFilter="">
      <mapperTableEntries name="customer_id" type="id_Integer" nullable="false"/>
      <mapperTableEntries name="customer_name" type="id_String" nullable="true"/>
    </inputTables>

    <inputTables name="row2" matchingMode="ALL_MATCHES" lookupMode="LOAD_ONCE"
                 innerJoin="true" activateExpressionFilter="false">
      <!-- Join key: expression maps main column to lookup column -->
      <mapperTableEntries name="cust_id" type="id_Integer" nullable="false"
                          expression="row1.customer_id"/>
      <!-- Non-join column (no expression) -->
      <mapperTableEntries name="order_total" type="id_BigDecimal" nullable="true"/>
    </inputTables>

    <!-- Variable table -->
    <varTables name="Var">
      <mapperTableEntries name="full_name" type="id_String"
                          expression="row1.first_name + &quot; &quot; + row1.last_name"/>
      <mapperTableEntries name="upper_name" type="id_String"
                          expression="Var.full_name.toUpperCase()"/>
    </varTables>

    <!-- Output tables -->
    <outputTables name="out1" reject="false" rejectInnerJoin="false"
                  activateExpressionFilter="true"
                  expressionFilter="row1.age &gt; 18"
                  activateCondensedTool="false">
      <mapperTableEntries name="name" type="id_String"
                          expression="Var.full_name"/>
      <mapperTableEntries name="order_amount" type="id_BigDecimal"
                          expression="row2.order_total"/>
    </outputTables>

    <outputTables name="reject_out" reject="true" rejectInnerJoin="true"
                  activateExpressionFilter="false">
      <mapperTableEntries name="customer_id" type="id_Integer"
                          expression="row1.customer_id"/>
      <mapperTableEntries name="error_reason" type="id_String"
                          expression="&quot;No matching order&quot;"/>
    </outputTables>

  </nodeData>

  <!-- Metadata for each output (schema propagation) -->
  <metadata connector="FLOW" name="out1">
    <column name="name" type="id_String" nullable="true"/>
    <column name="order_amount" type="id_BigDecimal" nullable="true"
            precision="10" length="2"/>
  </metadata>

  <metadata connector="REJECT" name="reject_out">
    <column name="customer_id" type="id_Integer" nullable="false"/>
    <column name="error_reason" type="id_String" nullable="true"/>
  </metadata>

</node>
```

### K.1 Attributes Parsed by `parse_tmap()`

| XML Path | Attribute | Parsed? | V1 Config Location |
|----------|-----------|---------|-------------------|
| `nodeData` | `xsi:type` (contains "MapperData") | Yes | Used for element discovery |
| `inputTables` | `name` | Yes | `inputs.main.name` / `inputs.lookups[].name` |
| `inputTables` | `matchingMode` | Yes | `inputs.main.matching_mode` / `inputs.lookups[].matching_mode` |
| `inputTables` | `lookupMode` | Yes | `inputs.main.lookup_mode` / `inputs.lookups[].lookup_mode` |
| `inputTables` | `innerJoin` | Yes | `inputs.lookups[].join_mode` (derived) |
| `inputTables` | `activateExpressionFilter` | Yes | `inputs.*.activate_filter` |
| `inputTables` | `expressionFilter` | Yes | `inputs.*.filter` (with `{{java}}` prefix) |
| `inputTables/mapperTableEntries` | `name` | Yes | Join key `lookup_column` |
| `inputTables/mapperTableEntries` | `expression` | Yes | Join key `expression` (with `{{java}}` prefix) |
| `inputTables/mapperTableEntries` | `type` | **No** | Not extracted for join keys |
| `inputTables/mapperTableEntries` | `nullable` | **No** | Not extracted for join keys |
| `varTables` | `name` | **No** | Variable table name not stored (always "Var") |
| `varTables/mapperTableEntries` | `name` | Yes | `variables[].name` |
| `varTables/mapperTableEntries` | `expression` | Yes | `variables[].expression` (with `{{java}}` prefix) |
| `varTables/mapperTableEntries` | `type` | Yes | `variables[].type` (Talend format) |
| `outputTables` | `name` | Yes | `outputs[].name` |
| `outputTables` | `reject` | Yes | `outputs[].is_reject` |
| `outputTables` | `rejectInnerJoin` | Yes | `outputs[].inner_join_reject` |
| `outputTables` | `activateExpressionFilter` | Yes | `outputs[].activate_filter` |
| `outputTables` | `expressionFilter` | Yes | `outputs[].filter` (with `{{java}}` prefix) |
| `outputTables` | `activateCondensedTool` | **No** | **NOT PARSED** -- catch output reject missing |
| `outputTables/mapperTableEntries` | `name` | Yes | `outputs[].columns[].name` |
| `outputTables/mapperTableEntries` | `expression` | Yes | `outputs[].columns[].expression` |
| `outputTables/mapperTableEntries` | `type` | Yes | `outputs[].columns[].type` |
| `outputTables/mapperTableEntries` | `nullable` | Yes | `outputs[].columns[].nullable` |
| `outputTables/mapperTableEntries` | `length` | **No** | Not extracted |
| `outputTables/mapperTableEntries` | `precision` | **No** | Not extracted |
| `outputTables/mapperTableEntries` | `pattern` | **No** | Not extracted |
| `elementParameter[@name='DIE_ON_ERROR']` | `value` | **No** | Generic pass skips tMap; `parse_tmap()` does not extract it |
| `elementParameter[@name='STORE_ON_DISK']` | `value` | **No** | Not extracted |
| `elementParameter[@name='TEMP_DATA_DIR']` | `value` | **No** | Not extracted |
| `elementParameter[@name='MAX_BUFFER_SIZE']` | `value` | **No** | Not extracted |

---

## Appendix L: Recommended Code Changes

### L.1 Fix CONV-MAP-001: Add DIE_ON_ERROR extraction to parse_tmap()

**File**: `src/converters/complex_converter/component_parser.py`
**Location**: Inside `parse_tmap()`, before line 667

```python
# Add before the config assignment on line 667:
die_on_error_elem = node.find('.//elementParameter[@name="DIE_ON_ERROR"]')
if die_on_error_elem is not None:
    die_on_error = die_on_error_elem.get('value', 'true').lower() == 'true'
else:
    die_on_error = True  # Talend default

# Then include in the config dict:
component['config'] = {
    'inputs': {
        'main': main_config,
        'lookups': lookups_config
    },
    'variables': variables_config,
    'outputs': outputs_config,
    'die_on_error': die_on_error  # <-- ADD THIS
}
```

### L.2 Fix ENG-MAP-001: Inner Join Reject Detection

**File**: `src/v1/engine/components/transform/map.py`
**Location**: `_perform_normal_join()` method

Replace the current approach (secondary merge after the fact) with indicator-based detection on the primary merge:

```python
# In _perform_normal_join(), change the merge call:
if lookup_config.get('join_mode', 'LEFT_OUTER_JOIN') == 'INNER_JOIN':
    # Use left join with indicator to detect unmatched rows
    result_df = joined_df.merge(
        lookup_df_prefixed,
        left_on=left_on,
        right_on=right_on_prefixed,
        how='left',
        indicator=True
    )
    # Split matched and unmatched
    unmatched_mask = result_df['_merge'] == 'left_only'
    inner_join_rejects = result_df[unmatched_mask].drop(columns=['_merge']).copy()
    result_df = result_df[~unmatched_mask].drop(columns=['_merge'])
else:
    result_df = joined_df.merge(
        lookup_df_prefixed,
        left_on=left_on,
        right_on=right_on_prefixed,
        how='left'
    )
    inner_join_rejects = pd.DataFrame()

# Return both
return result_df, inner_join_rejects
```

This eliminates the secondary merge and correctly identifies unmatched rows.

### L.3 Fix ENG-MAP-004: Make Parallel Execution Configurable

**File**: `src/v1/engine/components/transform/map.py`
**Location**: `_generate_tmap_compiled_script()` method, line 983

```python
# Add config option:
parallel_execution = self.config.get('parallel_execution', False)  # Default to sequential for safety

# In script generation:
if parallel_execution:
    lines.append("IntStream.range(0, rowCount).parallel().forEach(i -> {")
else:
    lines.append("IntStream.range(0, rowCount).forEach(i -> {")
```

### L.4 Fix BUG-MAP-001: _update_global_map() Variable Reference

**File**: `src/v1/engine/base_component.py`
**Location**: Line 304

```python
# Change from:
logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} {stat_name}: {value}")

# Change to:
logger.info(f"Component {self.id}: Updated globalMap stats - NB_LINE:{self.stats.get('NB_LINE', 0)} NB_LINE_OK:{self.stats.get('NB_LINE_OK', 0)} NB_LINE_REJECT:{self.stats.get('NB_LINE_REJECT', 0)}")
```

### L.5 Fix BUG-MAP-002: GlobalMap.get() Signature

**File**: `src/v1/engine/global_map.py`
**Location**: Line 26-28

```python
# Change from:
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)

# Change to:
def get(self, key: str, default: Any = None) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

---

## Appendix M: Glossary

| Term | Definition |
|------|-----------|
| **Arrow** | Apache Arrow, a columnar in-memory data format. Used for efficient data transfer between Python and Java. |
| **Cartesian join** | A cross join that produces M*N rows from M main rows and N lookup rows. Used when join keys are context-only expressions. |
| **Chained lookup** | A lookup that references columns from a previous lookup's result. Requires sequential evaluation. |
| **Chunk** | A subset of rows processed together. The V1 engine uses 50K-row chunks for Java execution. |
| **Compiled script** | Java source code generated by `_generate_tmap_compiled_script()`, compiled once by the JVM, and executed on multiple chunks. |
| **Context variable** | A Talend job parameter accessible via `context.varName`. Synced from Python to Java before expression evaluation. |
| **DIE_ON_ERROR** | Talend setting controlling error behavior. When true, expression errors stop the job. When false, errors produce reject rows. |
| **ForkJoinPool** | Java's thread pool for parallel stream execution. Used when `IntStream.parallel()` is called. |
| **GlobalMap** | Talend's global key-value store for sharing data between components. Contains component statistics and user-defined values. |
| **Inner join reject** | Main rows that have no matching lookup row during an INNER JOIN. In Talend, these are routed to a reject output. |
| **LOAD_ONCE** | Default lookup mode. Loads all lookup data into memory once before processing main rows. |
| **Matching mode** | Controls which lookup row is used when multiple rows match the same join key. Options: UNIQUE_MATCH, FIRST_MATCH, LAST_MATCH, ALL_MATCHES. |
| **RELOAD_AT_EACH_ROW** | Lookup mode that re-queries the lookup source for each main row. Used for parameterized queries. NOT implemented in V1. |
| **RowWrapper** | Custom Java class that wraps Arrow data and provides column access by table name. Created per-row per-thread in the generated script. |
| **Simple column reference** | An expression of the form `table.column` with no operators or method calls. Detected by regex and resolved directly from the DataFrame without Java. |
| **Store temp data** | Talend option to write lookup data to disk instead of holding in memory. NOT implemented in V1. |
| **Variable table** | Intermediate computed values in tMap. Evaluated per-row in order. Stored in `Var` map accessible by output expressions. |

---

## Appendix N: Detailed Code Walkthrough -- `_generate_tmap_compiled_script()`

This is the most complex method in the entire engine (lines 938-1157, ~220 lines). It generates Java source code as a string that encodes the entire tMap evaluation logic. Understanding this method is critical for debugging tMap issues.

### N.1 Script Generation Line-by-Line

**Lines 959-963: Import statements**
```java
import java.util.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;
import com.citi.gru.etl.RowWrapper;
```
The `RowWrapper` class is a custom class provided by the Java bridge. It wraps the Arrow input data and provides column access by table name and column name. Each `RowWrapper` instance knows its row index and table name, allowing expressions like `main.customer_id` to resolve to the correct Arrow column.

**Lines 966-972: Output array allocation**
```java
Object[][] output1_data = new Object[rowCount][numCols];
AtomicInteger output1_count = new AtomicInteger(0);
```
Each output gets a pre-allocated 2D array sized for ALL input rows. This is a trade-off: allocating for all rows wastes memory when filters exclude many rows, but avoids the cost of dynamic resizing. The `AtomicInteger` counter tracks how many rows are actually populated.

**Issue**: If the output filter is highly selective (e.g., 1% of rows match), 99% of the array is wasted. For a 10M row input with 50 output columns, this wastes ~4GB of heap per output. The Java-side code must use `count.get()` (not `rowCount`) to determine the actual number of populated rows.

**Lines 975-979: Error tracking (die_on_error=false)**
```java
AtomicInteger errorCount = new AtomicInteger(0);
ConcurrentHashMap<Integer, String> errorMap = new ConcurrentHashMap<>();
```
Thread-safe error tracking for parallel execution. The `ConcurrentHashMap` maps row index to error message. This is only generated when `die_on_error=false`.

**Lines 982-983: Parallel processing loop**
```java
IntStream.range(0, rowCount).parallel().forEach(i -> {
```
This is the performance-critical decision. `parallel()` distributes rows across the ForkJoinPool, using as many threads as CPU cores. The lambda captures `inputRoot` (the Arrow data), output arrays, and counters.

**Lines 986-992: RowWrapper creation**
```java
RowWrapper main = new RowWrapper(inputRoot, i, "main");
RowWrapper lookup1 = new RowWrapper(inputRoot, i, "lookup1");
```
Each RowWrapper is created per-row per-thread. The `inputRoot` is the Arrow data structure. The row index `i` selects the specific row. The table name (`"main"`, `"lookup1"`) tells the RowWrapper which columns to expose. When an expression accesses `main.customer_id`, the RowWrapper looks for a column named `customer_id` or `main.customer_id` in the Arrow data.

**Lines 1004-1017: Variable evaluation**
```java
Map<String, Object> Var = new HashMap<>();
Var.put("var1", main.first + " " + main.last);
Var.put("var2", ((String)Var.get("var1")).toUpperCase());
```
Variables are evaluated in declaration order. Each `Var.put()` call stores the result, making it available for subsequent variable expressions. The `Var` map is local to the lambda (per-thread, per-row), ensuring thread safety.

**Issue**: The `Var.get()` returns `Object`, so expressions must cast explicitly (e.g., `(String)Var.get("var1")`). The generated code does NOT add casts -- it relies on the Talend expression already including the correct Java types. If a Talend expression references a variable without proper casting, the generated Java will throw a `ClassCastException`.

**Lines 1019-1066: Output column evaluation**
```java
// Non-reject outputs
if (filter_expression) {
    Object[] output1_tempRow = new Object[numCols];
    output1_tempRow[0] = main.col1;
    output1_tempRow[1] = Var.get("var2");
    // ... all columns evaluated into temp array
    matchedAny = true;
    int idx = output1_count.getAndIncrement();
    output1_data[idx] = output1_tempRow;
}
```

**Critical design**: All columns are evaluated into a `tempRow` array FIRST. Only if ALL columns succeed (no exception) is the row committed to the output. This is an atomic operation per output per row. If column 3 fails with a NullPointerException, columns 0-2 are discarded and the row is not added to the output.

**Issue**: The `getAndIncrement()` operation is atomic but the assignment `output1_data[idx] = output1_tempRow` is not synchronized with reads. In parallel execution, a reader (e.g., the Java bridge collecting results) could see a partially-assigned array slot. However, since the Java bridge only reads AFTER the parallel forEach completes, this is safe in practice.

**Lines 1068-1084: Exception handling**
```java
} catch (Exception e) {
    // die_on_error=true: throw new RuntimeException("Error at row " + i + ": " + msg, e);
    // die_on_error=false: errorCount.incrementAndGet(); errorMap.put(i, msg);
}
```

For die_on_error=true, any expression error terminates the entire parallel stream. The RuntimeException propagates through the ForkJoinPool and is eventually caught by the Python bridge.

For die_on_error=false, the error is tracked and the row's `matchedAny` remains false, routing it to the reject output.

**Lines 1088-1126: Reject output handling**
```java
if (!matchedAny) {
    Object[] reject_tempRow = new Object[numColsReject];
    reject_tempRow[0] = main.col1;
    // ... evaluate reject columns
    int idx = reject_count.getAndIncrement();
    reject_data[idx] = reject_tempRow;
}
```

Reject output evaluation is OUTSIDE the inner try-catch. This means:
1. If the expression evaluation succeeded but no non-reject output filter matched -> row goes to reject
2. If the expression evaluation failed (caught by inner catch) -> `matchedAny` is false -> row goes to reject
3. Reject column expressions could ALSO fail. If they do, the OUTER try-catch catches the exception and re-throws as RuntimeException (always fatal, even if die_on_error=false).

**Issue**: Reject column expressions can reference the same data as main output expressions. If main output expressions failed due to null data, reject expressions referencing the same data will also fail. This means that when die_on_error=false, an error row that should go to reject may instead cause a fatal outer exception if the reject expression also fails.

### N.2 Generated Script Size Estimation

For a typical tMap with:
- 3 lookups
- 10 variables
- 3 outputs (20 columns each)
- 1 reject output (10 columns)

The generated script is approximately:
- Imports: 4 lines
- Output arrays: 4 * 3 = 12 lines
- Error tracking: 3 lines
- Parallel loop start: 5 lines
- RowWrappers: 4 lines
- Variables: 10 lines
- Output 1 (with filter): 25 lines
- Output 2 (with filter): 25 lines
- Output 3 (no filter): 23 lines
- Inner catch: 6 lines
- Reject output: 15 lines
- Outer catch: 4 lines
- Result construction: 20 lines
- **Total: ~156 lines of Java code**

For a large tMap with 10 outputs and 50 variables, the script could be 500+ lines of generated Java.

---

## Appendix O: Edge Cases and Corner Cases

### O.1 NULL Handling

| Scenario | Talend Behavior | V1 Behavior | Match? |
|----------|-----------------|-------------|--------|
| NULL join key in main | Does NOT match any lookup row | pandas NaN does not match (NaN != NaN) | Yes (aligned by default) |
| NULL join key in lookup | Does NOT match any main row | Same as above | Yes |
| NULL in expression | NullPointerException (Java) | NullPointerException in generated Java script | Yes |
| NULL in output column | NULL value in output | Java `null` -> Arrow null -> pandas NaN/None | Yes (approximately) |
| NULL in variable | NULL stored in Var map | Java `null` stored in HashMap | Yes |

### O.2 Type Coercion

| Scenario | Talend Behavior | V1 Behavior | Match? |
|----------|-----------------|-------------|--------|
| String + Integer | Java string concatenation | Java string concatenation via RowWrapper | Yes |
| Integer / Integer | Java integer division (truncates) | Java integer division | Yes |
| String == null | Java null comparison | Java null comparison | Yes |
| BigDecimal arithmetic | Java BigDecimal methods | Depends on RowWrapper's type handling | Partial |
| Date formatting | TalendDate routines | Via loaded routine in Java bridge | Yes (if routine loaded) |

### O.3 Data Volume Edge Cases

| Scenario | Expected Behavior | V1 Risk |
|----------|-------------------|---------|
| 0 rows input | Empty outputs | Handled (line 128-130) |
| 1 row input | 1 row per output (if matches) | Works |
| 50000 rows (exact chunk size) | 1 chunk | Works |
| 50001 rows | 2 chunks (50000 + 1) | Chunk boundary handling correct |
| 10M rows | 200 chunks | Works but slow serialization |
| Very wide DF (500 columns) | May exceed Arrow 2GB per chunk | **RISK**: 50K rows * 500 cols could exceed limit |
| Cartesian: 100K x 100K | OOM | **RISK**: No size guard |
| Empty lookup + LEFT_OUTER | NULL columns added | **BUG**: Lookup skipped entirely |
| Empty lookup + INNER | All rows rejected | **BUG**: Lookup skipped, rows pass through |

### O.4 Expression Edge Cases

| Expression | Talend Behavior | V1 Behavior | Notes |
|-----------|-----------------|-------------|-------|
| Empty string `""` | Empty string output | Becomes `null` in generated Java | **Mismatch**: Empty expressions default to null (line 1013-1014) |
| `row1.col.toString()` | String conversion | Java toString() call | Works if RowWrapper returns correct type |
| `context.var + "_suffix"` | String concatenation | Java string concat with context value | Works |
| `((String)globalMap.get("key"))` | Cast + get | Java cast with synced globalMap | Works |
| `Var.x != null ? Var.x : "default"` | Ternary with null check | Java ternary evaluation | Works |
| `row1.col.equals("value")` | String equality | Java equals() on RowWrapper value | Works |
| `row1.col.matches("regex")` | Regex match | Java regex on RowWrapper value | Works |
| Multi-line expression | NOT SUPPORTED in Talend | NOT SUPPORTED in V1 | Both use single-line |
| `++counter` | Side effect on shared state | Race condition in parallel | **Mismatch** |

---
