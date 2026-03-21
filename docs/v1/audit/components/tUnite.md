# Audit Report: tUnite / Unite

## Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tUnite` |
| **V1 Engine Class** | `Unite` |
| **Engine File** | `src/v1/engine/components/transform/unite.py` |
| **Converter Parser** | `component_parser.py` -> `parse_unite()` (line ~891) |
| **Converter Parameter Mapping** | `component_parser.py` -> `_map_component_parameters()` (line ~230) |
| **Converter Dispatch** | `converter.py` -> `_parse_component()` (line ~246) |
| **Registry Aliases** | `Unite`, `tUnite` |
| **Category** | Transform / Processing |
| **Complexity** | Medium -- multi-input component with union/merge modes |

---

## Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 |
|-----------|-------|----|----|----|----|
| Converter Coverage | Y | 1 | 1 | 1 | 0 |
| Engine Feature Parity | R | 2 | 3 | 2 | 1 |
| Code Quality | R | 2 | 2 | 3 | 2 |
| Performance & Memory | Y | 0 | 1 | 2 | 1 |
| Testing | R | 1 | 1 | 0 | 0 |

---

## 1. Talend Feature Baseline

### What tUnite Does in Talend

The tUnite component centralizes data from various and heterogeneous sources by merging
multiple input data flows into a single output data flow, operating in the style of a SQL
`UNION ALL`. It is one of the fundamental data integration components for combining rows
from multiple upstream paths.

Key characteristics of the Talend tUnite component:

1. **UNION ALL semantics**: tUnite concatenates all input rows vertically. It does NOT
   remove duplicates -- it behaves like SQL `UNION ALL`, not `UNION`. If deduplication
   is needed, Talend users place a `tUniqRow` downstream.

2. **Schema must match**: All input connections must share the same schema -- same column
   names, same column order, same number of columns. Talend Studio enforces this by
   schema synchronization ("Sync columns") from the first input to all others and to
   the output.

3. **Merge order**: Input rows are concatenated in a deterministic order based on the
   merge order (1, 2, 3, ...) that is determined by the connection order in Talend
   Studio. Users can reassign merge order.

4. **Sequential only**: tUnite is explicitly for sequential flow only and does NOT
   support parallelization.

5. **Cannot exist in data flow loops**: tUnite cannot accept outputs from multiple
   branches of a tMap in the same subjob that would create a cyclical flow. Each input
   must come from an independent upstream path.

6. **Not startable**: tUnite requires one or more input components and at least one
   output component. It cannot start a data flow.

### Basic Settings (Talend Studio)

| Parameter | Talend Name | Type | Description |
|-----------|-------------|------|-------------|
| Schema | `SCHEMA` | Schema editor | Column definitions defining the common output schema |
| Edit Schema | — | Button | Opens schema editor; can sync from first input connection |

tUnite has minimal configuration. It is a "pass-through union" component. There is no
mode selector (UNION vs MERGE), no deduplication option, no sort option. The component
simply concatenates input flows in merge order.

### Advanced Settings (Talend Studio)

| Parameter | Talend Name | Type | Description |
|-----------|-------------|------|-------------|
| tStatCatcher Statistics | `STATCATCHER` | Boolean | Collect component-level log data for monitoring |

There are NO other advanced settings. tUnite is intentionally simple.

### Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `Row (Main)` | Input | Multiple inputs | One or more input main connections (numbered merge order 1, 2, 3...) |
| `Row (Main)` | Output | Single output | Single main output containing all concatenated rows |
| `On Component Ok` | Trigger | Output | Fires after successful completion |
| `On Component Error` | Trigger | Output | Fires on error |
| `Run If` | Trigger | Input/Output | Conditional execution |

**Important**: Talend tUnite does NOT have a REJECT output. All incoming rows are passed
through. There is no row-level filtering or validation.

### GlobalMap Variables Produced (Talend)

| Key | Type | Description |
|-----|------|-------------|
| `{id}_NB_LINE` | Integer | Total number of rows processed (sum of all input rows) |
| `{id}_ERROR_MESSAGE` | String | Error message if component fails (requires Die on error unchecked) |

**Note**: tUnite does NOT produce `{id}_NB_LINE_OK` or `{id}_NB_LINE_REJECT` as separate
variables because it does not reject rows. `NB_LINE` equals the total output.

### Talend Behavioral Notes

1. **Schema synchronization is mandatory**: If input schemas do not match the component
   schema, Talend Studio warns or prevents execution. In the generated Java code, columns
   are mapped positionally by schema definition.

2. **No duplicate removal**: tUnite is always UNION ALL. Talend documentation and community
   forums consistently state that deduplication requires a separate `tUniqRow` component.

3. **No MERGE/JOIN capability**: Talend tUnite does NOT support join operations. Join
   functionality is provided by `tMap` (lookup joins) or `tJoin` (key-based joins). The
   concept of "MERGE mode" does not exist in standard Talend tUnite.

4. **Column alignment is by position, not name**: In the generated Java code, Talend maps
   columns from each input to the output by position within the schema, not by column name.
   This means column names across inputs must be identical and in the same order.

5. **Null handling**: Null values from any input pass through unchanged. No coercion or
   default value substitution occurs.

6. **Empty input handling**: If an input connection has zero rows, it is simply skipped.
   The output contains rows from the non-empty inputs only.

7. **Data types preserved**: Since all inputs share the same schema, data types are
   identical across all inputs by definition. No type coercion is needed.

### References

- [Talend Unite Tutorial - TutorialGateway](https://www.tutorialgateway.org/talend-unite/)
- [tUnite - Talend Components Help (v8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/tunite)
- [tUnite Standard Properties (v8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/tunite-standard-properties)
- [tUnite Standard Properties - Talend Help](https://help.talend.com/en-US/components/8.0/orchestration/tunite-standard-properties)
- [tUnite Community Discussion - Schema Matching](https://community.qlik.com/t5/Talend-Studio/tUnite-work-within-the-Talend-job/td-p/2327962)
- [UNION ALL vs UNION Discussion](https://community.talend.com/t5/Design-and-Development/Union-all-and-union/td-p/43622)

---

## 2. Converter Audit

The converter has TWO code paths for tUnite, which itself is an issue:

1. **`_map_component_parameters()`** at line ~230 of `component_parser.py` -- a generic
   parameter mapper that extracts config from a `config_raw` dictionary.
2. **`parse_unite()`** at line ~891 of `component_parser.py` -- a dedicated parser method
   called from `converter.py` at line ~246.

The `_map_component_parameters()` path is invoked during base component parsing (line ~472
of `component_parser.py`), while `parse_unite()` is called afterward from `converter.py`.
This means both paths execute, with `parse_unite()` potentially overwriting values set by
`_map_component_parameters()`.

### Parameters Extracted by `_map_component_parameters()` (line ~230)

| Config Key | Source | Default | Notes |
|------------|--------|---------|-------|
| `mode` | `config_raw.get('MODE', 'UNION')` | `'UNION'` | **Not a Talend parameter** -- Talend tUnite has no MODE setting |
| `remove_duplicates` | `config_raw.get('REMOVE_DUPLICATES', False)` | `False` | **Not a Talend parameter** -- Talend tUnite does not deduplicate |
| `keep` | `config_raw.get('KEEP', 'first')` | `'first'` | **Not a Talend parameter** -- custom dedup keep strategy |
| `sort_output` | `config_raw.get('SORT_OUTPUT', False)` | `False` | **Not a Talend parameter** -- custom sort option |
| `sort_columns` | `config_raw.get('SORT_COLUMNS', [])` | `[]` | **Not a Talend parameter** -- custom sort columns |
| `merge_columns` | `config_raw.get('MERGE_COLUMNS', None)` | `None` | **Not a Talend parameter** -- custom merge join key |
| `merge_how` | `config_raw.get('MERGE_HOW', 'inner')` | `'inner'` | **Not a Talend parameter** -- custom merge join type |

**Critical observation**: NONE of these parameters correspond to actual Talend tUnite XML
parameters. They are all custom additions. The only standard Talend parameter for tUnite
is the schema (`SCHEMA`), which is handled by generic schema parsing.

### Parameters Extracted by `parse_unite()` (line ~891)

```python
def parse_unite(self, node, component: Dict) -> Dict:
    """Parse tUnite specific configuration"""
    # tUnite is simple - just combines inputs
    # Most configuration is done through connections

    # Check if there are any specific settings
    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '')

    if name == 'REMOVE_DUPLICATES':
        component['config']['remove_duplicates'] = value.lower() == 'true'
    elif name == 'MODE':
        # Some versions might have merge mode
        component['config']['mode'] = value.strip('"')

    # Default mode is UNION
    if 'mode' not in component['config']:
        component['config']['mode'] = 'UNION'

    return component
```

### Schema Extraction

| Attribute | Extracted? | Notes |
|-----------|-----------|-------|
| `name` | Yes | Via generic schema parsing in base component |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` |
| `nullable` | Yes | Standard extraction |
| `key` | Yes | Standard extraction |
| `length` | Yes | Standard extraction |
| `precision` | Yes | Standard extraction |
| `pattern` | Yes | Java date pattern -> Python strftime |

### Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-UNT-001 | **P0** | **Critical indentation bug in `parse_unite()`**: The `if name == 'REMOVE_DUPLICATES':` check at line 901 is OUTSIDE the `for` loop (lines 897-899). The loop iterates all `elementParameter` nodes but the condition checks only the LAST parameter's `name` and `value`. This means: (a) if the last XML parameter happens to be `REMOVE_DUPLICATES`, it works by accident; (b) if the last parameter is `MODE`, only that is captured; (c) if neither is last, both are silently ignored. The `if`/`elif` block must be indented inside the `for` loop. |
| CONV-UNT-002 | **P1** | **Dual code paths**: tUnite parameters are mapped in BOTH `_map_component_parameters()` (line ~230) AND `parse_unite()` (line ~891). The `_map_component_parameters()` path sets `mode`, `remove_duplicates`, `keep`, `sort_output`, `sort_columns`, `merge_columns`, and `merge_how` from `config_raw` -- but since Talend XML does not emit these parameters, they always get their defaults. Then `parse_unite()` runs and may overwrite `mode` and `remove_duplicates`. This dual-path is confusing and violates STANDARDS.md which says each component should have a single dedicated `parse_*` method. |
| CONV-UNT-003 | **P2** | **Fabricated parameters**: `_map_component_parameters()` extracts `MODE`, `REMOVE_DUPLICATES`, `KEEP`, `SORT_OUTPUT`, `SORT_COLUMNS`, `MERGE_COLUMNS`, and `MERGE_HOW` as if they were Talend XML parameters. None of these exist in standard Talend tUnite. This creates a misleading mapping that suggests Talend tUnite has these features. If a future developer reads the converter code, they will incorrectly believe Talend tUnite supports merge joins and sorting. |

---

## 3. Engine Feature Parity Audit

### Feature Implementation Status

| Talend Feature | Implemented? | Fidelity | Notes |
|----------------|-------------|----------|-------|
| UNION ALL (vertical concatenation) | Yes | Medium | Uses `pd.concat()` with `ignore_index=True, sort=False` -- functionally correct for UNION mode |
| Schema enforcement (all inputs same schema) | **No** | **N/A** | **No schema validation** -- inputs with different columns are silently concatenated, producing NaN-filled rows. Talend would reject schema mismatches at design time. |
| Merge order (deterministic input ordering) | Partial | Low | Input order depends on Python dict iteration order (insertion order in 3.7+), but there is no explicit merge_order parameter or validation |
| Multiple input handling | Yes | High | Engine `_get_input_data()` correctly returns a dict for multi-input components |
| Empty input handling | Yes | High | Empty/None inputs are skipped in both batch and streaming modes |
| GlobalMap `{id}_NB_LINE` | Partial | Low | Stats are set via `_update_stats()` but `execute()` override bypasses `_update_global_map()` from base class (see BUG-UNT-001) |
| GlobalMap `{id}_ERROR_MESSAGE` | **No** | **N/A** | Not set on error |
| tStatCatcher Statistics | **No** | **N/A** | Not implemented |
| Sequential-only enforcement | **No** | **N/A** | No check that component is not parallelized |

### Non-Talend Features Implemented (Custom Extensions)

The V1 Unite component implements several features that do NOT exist in Talend tUnite.
While these may be useful extensions, they represent a semantic mismatch that could
confuse developers migrating Talend jobs.

| Custom Feature | Config Key | Engine Behavior | Risk |
|----------------|------------|-----------------|------|
| **MERGE mode** | `mode: "MERGE"` | Performs `pd.merge()` (SQL JOIN) on inputs | **High** -- this is fundamentally different from Talend tUnite. Talend join is done via tMap or tJoin, not tUnite. If a converter bug or manual config sets `mode=MERGE`, the component will perform a JOIN instead of a UNION, producing completely wrong results. |
| **Duplicate removal** | `remove_duplicates: true` | `drop_duplicates(keep=...)` after concatenation | **Medium** -- Talend tUnite is always UNION ALL. Dedup is done by tUniqRow. This could mask data quality issues. |
| **Keep strategy** | `keep: "first"/"last"/false` | Controls which duplicate to keep | Low -- only relevant if `remove_duplicates` is true |
| **Output sorting** | `sort_output: true, sort_columns: [...]` | `sort_values()` after combination | Low -- Talend tUnite does not sort; sorting is done by tSortRow |
| **Merge columns** | `merge_columns: [...]` | Specifies join key columns for MERGE mode | **High** -- enables join behavior that does not exist in tUnite |
| **Merge strategy** | `merge_how: "inner"/"outer"/"left"/"right"/"cross"` | Controls join type for MERGE mode | **High** -- enables complex join semantics foreign to tUnite |

### Behavioral Differences from Talend

| ID | Priority | Difference |
|----|----------|------------|
| ENG-UNT-001 | **P0** | **`execute()` completely overrides `BaseComponent.execute()`**: Unite's `execute()` method (line 117) replaces the base class `execute()` entirely. The base class `execute()` performs critical operations: (1) resolving `{{java}}` expressions via `_resolve_java_expressions()`, (2) resolving `${context.var}` patterns via `context_manager.resolve_dict()`, (3) tracking execution time in `stats['EXECUTION_TIME']`, (4) calling `_update_global_map()` to push stats to GlobalMap, (5) setting `self.status` to `SUCCESS`/`ERROR`, (6) attaching `stats` to the result dict. Unite bypasses ALL of these. This means: Java expressions in config are never resolved; context variables are never substituted; execution time is never tracked; GlobalMap stats keys (`{id}_NB_LINE`, `{id}_NB_LINE_OK`, etc.) are never set via the standard mechanism; component status is never updated; and the `stats` key is never added to the result dictionary. This is a critical runtime bug that will cause downstream components referencing `globalMap.get("{id}_NB_LINE")` to get null. |
| ENG-UNT-002 | **P0** | **MERGE mode is not a Talend tUnite feature**: The engine implements a `MERGE` mode that performs `pd.merge()` (SQL JOIN) operations. This is semantically wrong for a tUnite replacement. Talend tUnite only does UNION ALL. If any job config (through converter bug or manual editing) sets `mode: "MERGE"`, the component will perform a JOIN instead of a UNION, producing completely incorrect results. The MERGE functionality belongs in `tJoin` or `tMap`, not `tUnite`. |
| ENG-UNT-003 | **P1** | **No schema validation**: Talend enforces that all inputs to tUnite share the same schema (same columns, same order, same types). The V1 engine performs NO validation. If inputs have different columns, `pd.concat()` with `sort=False` will produce a DataFrame with all columns from all inputs, filling missing values with NaN. This silent data corruption is dangerous in production. |
| ENG-UNT-004 | **P1** | **No merge order enforcement**: Talend tUnite has explicit merge order (1, 2, 3...) that determines which input's rows come first in the output. The V1 engine concatenates inputs in dictionary iteration order, which depends on the order inputs were added to `input_data_map`. There is no mechanism to specify or validate merge order. |
| ENG-UNT-005 | **P1** | **`{id}_ERROR_MESSAGE` GlobalMap variable not set**: Talend sets `{id}_ERROR_MESSAGE` when the component encounters an error. The V1 engine does not set this variable. |
| ENG-UNT-006 | **P2** | **Custom deduplication feature creates behavioral divergence**: The `remove_duplicates` option with `keep` strategy does not exist in Talend tUnite. If enabled (even accidentally), it changes the output row count compared to Talend, potentially breaking downstream processing. |
| ENG-UNT-007 | **P2** | **Custom sorting feature creates behavioral divergence**: The `sort_output` and `sort_columns` options do not exist in Talend tUnite. If enabled, output row order differs from Talend, which could affect downstream components that depend on input ordering. |
| ENG-UNT-008 | **P3** | **`NB_LINE_REJECT` always 0**: The docstring and implementation always set `NB_LINE_REJECT` to 0. This is correct for Talend tUnite (which has no reject flow), but the stat is still tracked unnecessarily. |

---

## 4. Code Quality Audit

### Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-UNT-001 | **P0** | `unite.py` lines 117-152 | **`execute()` bypasses base class lifecycle**: Unite overrides `execute()` but does not call `super().execute()` or replicate its critical steps. The base class `execute()` at `base_component.py:188-234` performs: (1) `self.status = ComponentStatus.RUNNING`, (2) Java expression resolution, (3) context variable resolution, (4) execution mode auto-selection, (5) execution time tracking, (6) `_update_global_map()`, (7) `self.status = ComponentStatus.SUCCESS/ERROR`, (8) `result['stats'] = self.stats.copy()`. Unite's override does NONE of these except logging. In particular, `_update_global_map()` is never called, so `{id}_NB_LINE`, `{id}_NB_LINE_OK`, and `{id}_NB_LINE_REJECT` are never pushed to the GlobalMap. Component status is never set (remains `PENDING` forever). Execution time is never tracked. Context variables in config keys like `${context.output_dir}` are never resolved. |
| BUG-UNT-002 | **P0** | `unite.py` lines 246-269 | **MERGE mode cross join on no common columns**: When `merge_columns` is not specified and inputs have no common columns, the code falls through to `pd.merge(how='cross')`. A cross join on two DataFrames of N and M rows produces N*M rows. With inputs of 10K and 10K rows, this produces 100 million rows, likely causing an OutOfMemoryError. While this only triggers in MERGE mode (which itself should not exist), the code path is live and can be reached through misconfiguration. |
| BUG-UNT-003 | **P1** | `unite.py` lines 246-251 | **MERGE mode suffix handling is lossy**: When merging with `suffixes=('', '_dup')`, duplicate column names from the right DataFrame get `_dup` appended. But on the NEXT merge iteration (when merging with the third input), the `_dup` columns from the previous merge are now regular columns. If the third input also has overlapping columns, a second set of `_dup` columns appears, and pandas may raise an error or produce `_dup_dup` suffixes. This is a compounding column name collision bug for 3+ input MERGE operations. |
| BUG-UNT-004 | **P1** | `unite.py` line 141 | **Single input `len()` call on non-DataFrame**: When `input_data` is not a dict and not None (line 138-141), the code calls `len(input_data)` in the log message at line 141. If `input_data` is a generator (which streaming mode could produce), `len()` will raise `TypeError`. This should check `isinstance(input_data, pd.DataFrame)` before calling `len()`. |

### Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-UNT-001 | **P2** | **Config key `mode` is ambiguous**: The config key `mode` is used to select between `UNION` and `MERGE` behavior. Since `MERGE` is not a Talend concept for tUnite, the naming is misleading. If custom join functionality is needed, it should be a separate component (e.g., `CustomMerge`) rather than overloading tUnite's semantics. |
| NAME-UNT-002 | **P2** | **`input_data_map` stored as instance variable**: The `input_data_map` attribute (line 78) is set during `execute()` and persists between calls. This is not thread-safe and violates the principle that component state should be reset between executions. STANDARDS.md uses `input_dfs` for multiple input DataFrames. |
| NAME-UNT-003 | **P3** | **`add_input()` public method naming**: The method `add_input()` at line 363 is a public method (no underscore prefix) that mutates component state. Per STANDARDS.md, methods that modify internal state should use underscore prefix unless they are part of the documented public API. |

### Standards Compliance

| ID | Priority | Issue |
|----|----------|-------|
| STD-UNT-001 | **P1** | **`execute()` override violates component lifecycle contract**: STANDARDS.md Section 6 ("Component Structure") specifies that components should implement `_process()` and only override `execute()` "if overriding base behavior." However, the override must still maintain the base class contract: Java expression resolution, context resolution, stat tracking, status updates, and global map updates. Unite's override breaks all of these contracts. The standard pattern is to call `super().execute()` which then calls `_process()`, or to replicate all base class steps in the override. |
| STD-UNT-002 | **P2** | **`_validate_config()` is never called**: Unite implements `_validate_config()` (line 80) and a public `validate_config()` wrapper (line 374), but neither is called from `execute()` or `_process_batch()`. Configuration errors like `mode="INVALID"` will not be caught until mid-processing when the mode check at line 272 raises `ValueError`. Per STANDARDS.md, config validation should happen at execution start. |
| STD-UNT-003 | **P2** | **`validate_config()` public wrapper is non-standard**: The public `validate_config()` method at line 374 returns `bool` rather than `List[str]`. This is inconsistent with the base class pattern where `_validate_config()` returns error messages. The public wrapper loses error detail by converting to boolean. |
| STD-UNT-004 | **P3** | **Module docstring mentions "streaming mode for large datasets"**: The module docstring at line 8 mentions streaming support, but streaming mode only supports UNION operations and silently falls back to batch for MERGE mode. This should be documented more explicitly in the class docstring. |

### Dead Code

| ID | Priority | Issue |
|----|----------|-------|
| DEAD-UNT-001 | **P3** | **`_process()` method is effectively dead code**: The `_process()` method at line 154 is only reachable if the base class `execute()` calls it (via `_execute_batch()`). But since Unite overrides `execute()`, the base class path is never taken. The only way `_process()` could be called is if external code directly calls `component._process(input_data)`, which is not the standard pattern. The method exists for "compatibility" per its docstring but is unreachable in practice. |

### Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-UNT-001 | **P2** | **`logger.info()` for routine operations**: Line 131 logs at INFO level for every execution start. Line 217 and 302-304 log full processing details at INFO level. For a component that may execute many times in an iterate loop, this produces excessive log output. STANDARDS.md recommends INFO for start/complete and DEBUG for intermediate details. The detailed configuration log at line 195-196 should be DEBUG. |

### Security

No security issues identified. The component operates on in-memory DataFrames only and
does not perform file I/O, execute user code, or access external systems.

---

## 5. Performance & Memory Audit

| ID | Priority | Issue |
|----|----------|-------|
| PERF-UNT-001 | **P1** | **`pd.concat()` creates a full copy of all input data**: At line 223, `pd.concat(dataframes, ignore_index=True, sort=False)` creates a new DataFrame that is a copy of all input rows combined. For N inputs of M rows each, this requires memory for N*M rows in ADDITION to the original N DataFrames still in memory. Peak memory usage is 2x the total input data. For large-scale jobs (millions of rows from multiple inputs), this can cause memory pressure. Consider using `pd.concat()` with `copy=False` for memory optimization, though this has implications for downstream mutation. |
| PERF-UNT-002 | **P2** | **MERGE mode with 3+ inputs is O(n^2) for overlapping columns**: In MERGE mode (lines 237-271), each merge operation iterates through `dataframes[1:]` and merges sequentially. For K inputs of N rows each with an inner join, the intermediate result size can grow or shrink unpredictably. With outer joins, intermediate results grow, and each subsequent merge operates on the increasingly large intermediate DataFrame. The time complexity approaches O(K * N * log(N)) for sorted merge joins, but with cross joins on no common columns, it becomes O(N^K) -- catastrophic for K >= 3. |
| PERF-UNT-003 | **P2** | **`drop_duplicates()` after concat is memory-intensive**: When `remove_duplicates=True` (line 276-279), the full concatenated DataFrame is first created, then deduplication runs. `drop_duplicates()` requires hashing all rows, which for wide DataFrames (50+ columns) is expensive. If this feature is retained, consider deduplicating per-input before concatenation to reduce peak memory. |
| PERF-UNT-004 | **P3** | **Streaming mode statistics are incremental but may overflow**: In `_process_streaming()` (line 346-347), `_update_stats()` is called per chunk. The `_update_stats()` method (base class line 306-310) uses `+=` accumulation. For very long-running streaming jobs with billions of rows, the integer counters will not overflow (Python ints are arbitrary precision), but the cumulative DEBUG logging at line 312 of the base class fires on every chunk, which is excessive. |

---

## 6. Testing Audit

| ID | Priority | Issue |
|----|----------|-------|
| TEST-UNT-001 | **P0** | **No unit tests for the `Unite` engine component**: There are no test files for `Unite` in the `tests/` directory. The `Glob` search for `*test*unite*` returned zero results. The only test mentioning `tUnite` is in `tests/converters/v1_to_v2/test_component_mapper.py` (line 478-482), which tests the V1-to-V2 component mapper, not the V1 engine component itself. |
| TEST-UNT-002 | **P1** | **Existing V1-to-V2 mapper test is minimal**: The test at `test_component_mapper.py:478-482` only checks that `tUnite` maps to type `"union"`. It does not test config transformation, schema handling, or any parameter mapping. It passes an empty config `{}`, so it does not exercise any parameter extraction. |

### Recommended Test Cases

| Test | Priority | Description |
|------|----------|-------------|
| Basic two-input UNION | P0 | Two DataFrames with identical schemas are concatenated. Verify row count = sum of inputs, column order preserved, no NaN values introduced. |
| Three-input UNION | P0 | Three DataFrames with identical schemas. Verify all rows present in correct order. |
| Single input passthrough | P0 | Single DataFrame input (not dict). Verify output equals input exactly. |
| Empty input handling | P0 | All inputs empty/None. Verify empty DataFrame returned, stats = 0. |
| Mixed empty and non-empty inputs | P0 | Some inputs empty, some with data. Verify only non-empty input rows in output. |
| Schema mismatch detection | P1 | Two inputs with different columns. Currently produces NaN -- test should document current behavior and flag for fix. |
| Dict input format | P1 | Input as `{'flow1': df1, 'flow2': df2}`. Verify correct handling. |
| Single DataFrame input (not dict) | P1 | Input as bare DataFrame (not wrapped in dict). Verify correct wrapping. |
| None input | P1 | Input is `None`. Verify warning logged and empty result returned. |
| GlobalMap stats verification | P0 | After execution, verify `{id}_NB_LINE`, `{id}_NB_LINE_OK`, `{id}_NB_LINE_REJECT` in GlobalMap. (This test will FAIL until BUG-UNT-001 is fixed.) |
| Context variable resolution in config | P1 | Config contains `${context.mode}`. Verify it is resolved. (This test will FAIL until BUG-UNT-001 is fixed.) |
| Streaming mode UNION | P1 | Verify streaming generator yields all input chunks correctly. |
| Streaming mode with MERGE fallback | P2 | Verify MERGE mode in streaming falls back to batch with warning. |
| Remove duplicates option | P2 | Enable `remove_duplicates=True`. Verify duplicates removed and stats correct. |
| Sort output option | P2 | Enable `sort_output=True, sort_columns=['col']`. Verify output sorted. |
| Large input performance | P2 | Two inputs of 1M rows each. Verify memory usage and execution time are reasonable. |
| MERGE mode basic (if retained) | P2 | Two inputs with shared columns, `mode=MERGE, merge_how=inner`. Verify join result. |
| MERGE mode no common columns | P2 | Two inputs with no common columns and no `merge_columns`. Verify cross join behavior (or ideally, error). |
| Config validation | P1 | Invalid mode value. Verify `_validate_config()` returns errors. |

---

## 7. Issues Summary

### All Issues by Priority

#### P0 -- Critical (6 issues)

| ID | Category | Summary |
|----|----------|---------|
| BUG-UNT-001 | Bug | `execute()` bypasses base class lifecycle -- no Java/context resolution, no GlobalMap updates, no status tracking, no execution time. This breaks downstream globalMap references and monitoring. |
| BUG-UNT-002 | Bug | MERGE mode cross join on no common columns can produce N*M rows, causing OutOfMemoryError |
| ENG-UNT-001 | Feature Gap | `execute()` override bypasses `_update_global_map()`, `_resolve_java_expressions()`, context resolution, status tracking -- all base class contract obligations |
| ENG-UNT-002 | Feature Gap | MERGE mode is not a Talend tUnite feature -- it implements JOIN semantics that belong in tJoin/tMap, creating risk of completely wrong results if triggered |
| CONV-UNT-001 | Converter Bug | Critical indentation bug in `parse_unite()` -- `if`/`elif` checks are outside the `for` loop, only checking the LAST XML parameter |
| TEST-UNT-001 | Testing | Zero unit tests for the Unite engine component |

#### P1 -- Major (7 issues)

| ID | Category | Summary |
|----|----------|---------|
| BUG-UNT-003 | Bug | MERGE mode suffix handling produces `_dup_dup` column name collisions for 3+ inputs |
| BUG-UNT-004 | Bug | `len(input_data)` on non-DataFrame input (e.g., generator) raises TypeError |
| ENG-UNT-003 | Feature Gap | No schema validation -- mismatched input schemas silently produce NaN-filled rows |
| ENG-UNT-004 | Feature Gap | No merge order enforcement -- input concatenation order is non-deterministic |
| ENG-UNT-005 | Feature Gap | `{id}_ERROR_MESSAGE` GlobalMap variable not set on error |
| CONV-UNT-002 | Converter | Dual code paths (`_map_component_parameters` and `parse_unite`) for the same component |
| STD-UNT-001 | Standards | `execute()` override violates component lifecycle contract from STANDARDS.md |
| TEST-UNT-002 | Testing | Existing V1-to-V2 mapper test is minimal (empty config, type check only) |
| PERF-UNT-001 | Performance | `pd.concat()` creates full copy, doubling peak memory for large inputs |

#### P2 -- Moderate (8 issues)

| ID | Category | Summary |
|----|----------|---------|
| ENG-UNT-006 | Feature Gap | Custom `remove_duplicates` feature diverges from Talend UNION ALL behavior |
| ENG-UNT-007 | Feature Gap | Custom `sort_output` feature diverges from Talend tUnite behavior |
| CONV-UNT-003 | Converter | `_map_component_parameters()` extracts fabricated parameters that do not exist in Talend XML |
| NAME-UNT-001 | Naming | Config key `mode` is ambiguous -- overloads tUnite with JOIN semantics |
| NAME-UNT-002 | Naming | `input_data_map` instance variable persists between executions, not thread-safe |
| STD-UNT-002 | Standards | `_validate_config()` is never called during execution |
| STD-UNT-003 | Standards | Public `validate_config()` returns bool, losing error detail |
| DBG-UNT-001 | Debug | INFO-level logging for routine operations -- should be DEBUG |
| PERF-UNT-002 | Performance | MERGE mode with 3+ inputs and outer joins has O(N^K) worst case |
| PERF-UNT-003 | Performance | `drop_duplicates()` after full concat is memory-intensive for wide DataFrames |

#### P3 -- Low (4 issues)

| ID | Category | Summary |
|----|----------|---------|
| ENG-UNT-008 | Feature Gap | `NB_LINE_REJECT` always 0 -- tracked unnecessarily |
| NAME-UNT-003 | Naming | `add_input()` public method should be prefixed with underscore |
| STD-UNT-004 | Standards | Module docstring streaming claim is not fully accurate |
| DEAD-UNT-001 | Dead Code | `_process()` method is unreachable due to `execute()` override |
| PERF-UNT-004 | Performance | Streaming mode per-chunk DEBUG logging may be excessive for long jobs |

---

## 8. Detailed Code Walkthrough

### 8.1 Class Definition and Constructor (Lines 18-78)

```python
class Unite(BaseComponent):
```

The class correctly inherits from `BaseComponent` and passes through all constructor
arguments. The only additional initialization is `self.input_data_map = {}` at line 78,
which stores the multi-input dictionary.

**Issue**: `input_data_map` is an instance variable that persists between `execute()` calls.
If a component is reused (e.g., in an iterate loop), stale data from the previous execution
could leak into the next execution. The map should be cleared at the start of each
`execute()` call (which it effectively is, since `execute()` reassigns it at lines 136/140/144).

### 8.2 Configuration Validation (Lines 80-115)

The `_validate_config()` method validates:
- `mode` is in `['UNION', 'MERGE']`
- `merge_how` is valid when mode is `MERGE`
- `remove_duplicates` is boolean
- `sort_output` is boolean
- `sort_columns` is a list

**Issues**:
1. Validation is never invoked (STD-UNT-002).
2. Validates parameters for MERGE mode, which should not exist in tUnite (ENG-UNT-002).
3. Does not validate that `sort_columns` contains valid column names (cannot be checked
   until input data is available, so this is acceptable).
4. Does not validate `keep` parameter values (`'first'`, `'last'`, `False`).

### 8.3 Execute Override (Lines 117-152)

This is the most critical section and the source of BUG-UNT-001.

```python
def execute(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
```

The method:
1. Logs processing start (line 131)
2. Routes input to `input_data_map` based on type (dict vs single vs None)
3. Dispatches to `_process_streaming()` or `_process_batch()`

What it does NOT do (that the base class does):
1. Set `self.status = ComponentStatus.RUNNING`
2. Call `_resolve_java_expressions()`
3. Call `context_manager.resolve_dict(self.config)`
4. Track execution time
5. Call `_update_global_map()`
6. Set `self.status = ComponentStatus.SUCCESS/ERROR`
7. Attach `result['stats']` to the return value
8. Handle exceptions with status/time tracking

### 8.4 Batch Processing (Lines 176-310)

The `_process_batch()` method is well-structured with good logging:

1. **Empty check** (lines 183-186): Returns empty DataFrame if no inputs. Correct.
2. **Config extraction** (lines 189-193): Gets all config values with defaults.
3. **Input collection** (lines 200-210): Iterates `input_data_map`, skips empty/None.
4. **UNION mode** (lines 220-223): `pd.concat(dataframes, ignore_index=True, sort=False)`.
   - `ignore_index=True` resets the index, which is correct.
   - `sort=False` preserves column order from the first DataFrame rather than
     alphabetically sorting columns, which matches Talend behavior.
5. **MERGE mode** (lines 225-271): Sequential `pd.merge()` operations.
   - See BUG-UNT-002 and BUG-UNT-003 for issues.
6. **Deduplication** (lines 276-280): `drop_duplicates(keep=keep)`. Correct pandas usage.
7. **Sorting** (lines 283-289): `sort_values()` with column validation. Correct.
8. **Stats update** (lines 292-293): Updates NB_LINE and NB_LINE_OK. Correct locally,
   but these never reach GlobalMap due to BUG-UNT-001.
9. **Custom GlobalMap entries** (lines 296-300): Sets `{id}_INPUT_COUNT`, `{id}_MODE`,
   `{id}_INPUT_ROWS`, `{id}_OUTPUT_ROWS`. These are non-standard and not part of the
   Talend GlobalMap contract.

### 8.5 Streaming Processing (Lines 312-361)

The streaming implementation:
1. Only supports UNION mode (line 324); MERGE falls back to batch (line 327).
2. Uses a generator function `stream_generator()` that yields chunks.
3. Handles both generator and DataFrame inputs via duck-typing.
4. Per-chunk stats are updated (line 347), but these are cumulative via `+=`.

**Issues**:
1. The `stream_generator()` calls `_update_stats()` per chunk, which is correct for
   incremental tracking but produces excessive logging.
2. If the generator is consumed lazily (as generators should be), the stats at the time
   `execute()` returns will be 0 because no chunks have been yielded yet. Stats only
   accumulate as the downstream component consumes the generator. This means the
   `_update_global_map()` call (if it existed) would report 0 rows even though data
   was generated.

### 8.6 Add Input Method (Lines 363-372)

```python
def add_input(self, input_name: str, data: Any) -> None:
```

This method allows external code to add inputs to the component before execution.
It is not used by the engine (which passes all inputs via `execute(input_data)`).
This appears to be designed for manual/programmatic usage outside the engine.

### 8.7 Validate Config Wrapper (Lines 374-393)

The `validate_config()` method wraps `_validate_config()` and returns boolean.
It is never called by the engine or by `execute()`.

---

## 9. Converter Code Walkthrough

### 9.1 `_map_component_parameters()` Path (Lines 230-239)

```python
elif component_type == 'tUnite':
    return {
        'mode': config_raw.get('MODE', 'UNION'),
        'remove_duplicates': config_raw.get('REMOVE_DUPLICATES', False),
        'keep': config_raw.get('KEEP', 'first'),
        'sort_output': config_raw.get('SORT_OUTPUT', False),
        'sort_columns': config_raw.get('SORT_COLUMNS', []),
        'merge_columns': config_raw.get('MERGE_COLUMNS', None),
        'merge_how': config_raw.get('MERGE_HOW', 'inner')
    }
```

This path extracts parameters from `config_raw`, which is built from Talend XML
`elementParameter` entries. Since Talend tUnite does NOT emit `MODE`, `REMOVE_DUPLICATES`,
`KEEP`, `SORT_OUTPUT`, `SORT_COLUMNS`, `MERGE_COLUMNS`, or `MERGE_HOW` parameters, all
values will always be their defaults. This entire block is effectively:

```python
return {
    'mode': 'UNION',
    'remove_duplicates': False,
    'keep': 'first',
    'sort_output': False,
    'sort_columns': [],
    'merge_columns': None,
    'merge_how': 'inner'
}
```

### 9.2 `parse_unite()` Path (Lines 891-911)

The critical indentation bug (CONV-UNT-001) in detail:

```python
def parse_unite(self, node, component: Dict) -> Dict:
    """Parse tUnite specific configuration"""
    # tUnite is simple - just combines inputs
    # Most configuration is done through connections

    # Check if there are any specific settings
    for param in node.findall('.//elementParameter'):
        name = param.get('name')          # <-- assigned in loop
        value = param.get('value', '')     # <-- assigned in loop
                                           # <-- loop body ends here (no processing!)

    if name == 'REMOVE_DUPLICATES':        # <-- OUTSIDE loop, checks LAST param only
        component['config']['remove_duplicates'] = value.lower() == 'true'
    elif name == 'MODE':
        component['config']['mode'] = value.strip('"')

    # Default mode is UNION
    if 'mode' not in component['config']:
        component['config']['mode'] = 'UNION'

    return component
```

The `for` loop at line 897 iterates all `elementParameter` nodes but the loop body only
assigns `name` and `value` -- it does not check them. The `if/elif` block at line 901 is
at the same indentation level as the `for` statement, making it run AFTER the loop
completes. At that point, `name` and `value` hold the values from the LAST parameter in
the XML. If the last parameter happens to be `REMOVE_DUPLICATES` or `MODE`, it will be
captured correctly by coincidence. Otherwise, both checks fail silently.

Additionally, if `node.findall('.//elementParameter')` returns an empty list, the loop
body never executes, and `name` is undefined. The `if name == 'REMOVE_DUPLICATES':` at
line 901 would then raise `NameError: name 'name' is not defined`.

**Corrected version** should be:

```python
def parse_unite(self, node, component: Dict) -> Dict:
    """Parse tUnite specific configuration"""
    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '')

        if name == 'REMOVE_DUPLICATES':
            component['config']['remove_duplicates'] = value.lower() == 'true'
        elif name == 'MODE':
            component['config']['mode'] = value.strip('"')

    if 'mode' not in component['config']:
        component['config']['mode'] = 'UNION'

    return component
```

---

## 10. Architecture Analysis

### 10.1 Multi-Input Component Pattern

The V1 engine handles multi-input components through a specific pattern in
`engine.py:_get_input_data()` (lines 779-795):

```python
def _get_input_data(self, comp_id: str) -> Optional[Any]:
    component = self.components[comp_id]
    if not component.inputs:
        return None
    if len(component.inputs) == 1:
        return self.data_flows.get(component.inputs[0])
    else:
        input_data = {}
        for input_flow in component.inputs:
            input_data[input_flow] = self.data_flows.get(input_flow)
        return input_data
```

This means:
- **Single input**: component receives a bare DataFrame.
- **Multiple inputs**: component receives a `Dict[str, DataFrame]` keyed by flow name.

Unite's `execute()` handles both cases (lines 134-144), which is correct. However, the
flow names used as dictionary keys are the flow connection names (e.g., `"row1"`, `"row2"`),
not merge order numbers. There is no mechanism to map flow names to merge order.

### 10.2 Relationship to Other Components

| Related Component | Talend | V1 | Relationship |
|-------------------|--------|-----|-------------|
| tUniqRow | Deduplication after union | UniqueRow | Should be used downstream for dedup, not built into Unite |
| tSortRow | Sort after union | SortRow | Should be used downstream for sorting, not built into Unite |
| tJoin | Key-based join | Join | The component that should handle MERGE/JOIN semantics |
| tMap | Complex mapping with lookups | Map | Another component for join operations |
| tReplicate | Copy single input to multiple outputs | Replicate | Inverse of Unite (1-to-many vs many-to-1) |

### 10.3 Design Decision: MERGE Mode

The inclusion of MERGE mode in Unite appears to be a design decision to consolidate
union and join operations into a single component. However, this creates several problems:

1. **Semantic confusion**: Developers migrating Talend jobs expect tUnite to ONLY do
   UNION ALL. Having a hidden MERGE mode that performs JOINs is surprising and dangerous.

2. **Converter risk**: If the converter ever incorrectly sets `mode: MERGE` (e.g., due
   to the indentation bug in `parse_unite()`), the component silently performs a JOIN
   instead of a UNION, producing completely wrong results with no warning.

3. **Testing burden**: MERGE mode doubles the test surface area for a component that
   in Talend is trivially simple.

4. **Maintenance burden**: Bug fixes and optimizations must consider both modes.

**Recommendation**: Remove MERGE mode from Unite entirely. If custom merge/join
functionality is needed outside of tMap and tJoin, create a dedicated component
(`CustomMerge` or similar) rather than overloading tUnite semantics.

---

## 11. Recommendations

### Immediate (Before Production) -- Must Fix

1. **Fix BUG-UNT-001**: Refactor `execute()` to call `super().execute()` or replicate
   all base class lifecycle steps. The recommended approach is to restructure Unite to
   use the standard `_process()` pattern:
   - Override `execute()` to handle multi-input dict -> call `_process_batch()` or
     `_process_streaming()` -- but ALSO call `_resolve_java_expressions()`,
     `context_manager.resolve_dict()`, `_update_global_map()`, set status, and track
     execution time.
   - Alternatively, move multi-input handling into a modified `_process()` method and
     let the base class `execute()` manage the lifecycle.

2. **Fix CONV-UNT-001**: Indent the `if`/`elif` block inside the `for` loop in
   `parse_unite()`. Also add a guard for the case where no elementParameters exist
   (empty loop -> undefined `name`).

3. **Remove or deprecate MERGE mode** (ENG-UNT-002): MERGE mode is not a Talend
   feature and creates significant risk. If it must be retained for non-Talend use
   cases, add a prominent warning log and consider moving it to a separate component.

4. **Create comprehensive unit tests** (TEST-UNT-001): Write tests for all P0 test
   cases listed in Section 6.

5. **Add schema validation** (ENG-UNT-003): Validate that all input DataFrames have
   matching column names and order. Log a warning or raise an error when schemas diverge.

### Short-Term (Hardening)

6. **Remove dual converter path** (CONV-UNT-002): Remove the tUnite case from
   `_map_component_parameters()` and consolidate all parsing into `parse_unite()`.

7. **Remove fabricated parameters** (CONV-UNT-003): Remove `REMOVE_DUPLICATES`, `KEEP`,
   `SORT_OUTPUT`, `SORT_COLUMNS`, `MERGE_COLUMNS`, `MERGE_HOW` from the parameter
   mapping since they are not Talend parameters.

8. **Call `_validate_config()` during execution** (STD-UNT-002): Add config validation
   at the start of `execute()` or `_process_batch()`.

9. **Fix `len()` on non-DataFrame** (BUG-UNT-004): Add type check before calling `len()`
   on `input_data` in the single-input path.

10. **Add merge order support** (ENG-UNT-004): Either accept a merge order config
    parameter or sort inputs by flow name to ensure deterministic ordering.

11. **Set `{id}_ERROR_MESSAGE`** (ENG-UNT-005): Set the error message GlobalMap variable
    in the exception handler.

### Long-Term (Optimization)

12. **Optimize `pd.concat()` memory** (PERF-UNT-001): Investigate `copy=False` parameter
    or chunked concatenation for very large inputs.

13. **Demote routine logging to DEBUG** (DBG-UNT-001): Change INFO logs for config
    details and intermediate steps to DEBUG level.

14. **Remove dead `_process()` method** (DEAD-UNT-001): Or restructure to use it via
    the standard base class pattern.

15. **Clean up naming** (NAME-UNT-001, NAME-UNT-002, NAME-UNT-003): Align with
    STANDARDS.md conventions.

---

## 12. Comparison Matrix: Talend tUnite vs V1 Unite

| Aspect | Talend tUnite | V1 Unite | Match? |
|--------|---------------|----------|--------|
| Primary operation | UNION ALL (concatenation) | UNION or MERGE (concat or join) | Partial -- UNION mode matches, MERGE mode is foreign |
| Duplicate handling | Keeps all duplicates | Optional dedup via `remove_duplicates` | No -- Talend always keeps dupes |
| Schema validation | Enforced at design time | None | No |
| Column alignment | By position per schema | By column name via `pd.concat` | No -- pandas uses name-based alignment |
| Merge order | Explicit 1, 2, 3... | Dict iteration order | No |
| Output sorting | None | Optional via `sort_output` | No -- Talend does not sort |
| Input count | 2+ required | 0+ accepted | Partial -- Talend requires at least 2 |
| Reject flow | None | None | Yes |
| GlobalMap NB_LINE | Set on completion | Not set (base class bypassed) | No |
| GlobalMap ERROR_MESSAGE | Set on error | Not set | No |
| tStatCatcher | Supported | Not supported | No |
| Streaming support | N/A (Java row-by-row) | Supported for UNION mode | N/A -- V1 extension |
| Sequential-only | Enforced | Not enforced | No |
| Data flow loop restriction | Enforced | Not enforced | No |

---

## 13. Risk Assessment for Production Migration

### High Risk Scenarios

1. **Jobs referencing `globalMap.get("{id}_NB_LINE")`**: Any downstream component or
   expression that reads the tUnite row count from GlobalMap will get `null`/`None`
   because BUG-UNT-001 prevents stats from being written to GlobalMap. This will cause
   NullPointerException equivalents in downstream Java expressions or incorrect
   conditional logic.

2. **Jobs with context variables in unite-related config**: If any config parameter
   contains `${context.var}` references (unlikely for tUnite since it has minimal config,
   but possible in custom extensions), they will not be resolved.

3. **Schema mismatches between inputs**: If upstream components produce DataFrames with
   slightly different column sets (e.g., one has an extra column from a tMap output),
   Unite will silently produce NaN-filled rows instead of raising an error. This produces
   wrong data that may propagate through the entire pipeline undetected.

4. **Accidental MERGE mode activation**: If a converter bug, manual edit, or
   misconfiguration sets `mode: MERGE`, the component performs a JOIN instead of a
   UNION, producing fundamentally wrong results.

### Medium Risk Scenarios

5. **Large-scale jobs with many inputs**: The memory doubling from `pd.concat()` may cause
   issues for jobs combining millions of rows from 5+ input sources.

6. **Jobs relying on specific row order**: If downstream processing depends on rows being
   in a specific order (e.g., first all rows from source A, then all from source B),
   the non-deterministic dict iteration order may produce different results across runs
   (though Python 3.7+ dicts maintain insertion order, the insertion order depends on
   engine execution order of upstream components).

### Low Risk Scenarios

7. **Simple two-input UNION with matching schemas**: The most common tUnite usage pattern
   (two inputs, same columns, no GlobalMap references downstream) will work correctly
   in UNION mode despite the bugs listed above.

---

## Appendix A: File Locations

| File | Path |
|------|------|
| Engine component | `src/v1/engine/components/transform/unite.py` |
| Base component | `src/v1/engine/base_component.py` |
| Engine orchestrator | `src/v1/engine/engine.py` |
| Converter parser | `src/converters/complex_converter/component_parser.py` |
| Converter dispatch | `src/converters/complex_converter/converter.py` |
| Transform __init__ | `src/v1/engine/components/transform/__init__.py` |
| V1-to-V2 mapper test | `tests/converters/v1_to_v2/test_component_mapper.py` |
| Standards document | `docs/v1/STANDARDS.md` |
| Audit methodology | `docs/v1/audit/METHODOLOGY.md` |

## Appendix B: Line-Level Issue Index

| Line(s) | File | Issue ID | Summary |
|----------|------|----------|---------|
| 117-152 | unite.py | BUG-UNT-001 | execute() bypasses base class lifecycle |
| 141 | unite.py | BUG-UNT-004 | len() on non-DataFrame may raise TypeError |
| 246-269 | unite.py | BUG-UNT-002 | Cross join on no common columns |
| 246-251 | unite.py | BUG-UNT-003 | _dup suffix compounding for 3+ inputs |
| 80-115 | unite.py | STD-UNT-002 | _validate_config() never called |
| 154-174 | unite.py | DEAD-UNT-001 | _process() unreachable |
| 374-393 | unite.py | STD-UNT-003 | validate_config() returns bool |
| 131, 195-196 | unite.py | DBG-UNT-001 | INFO-level logging for routine operations |
| 223 | unite.py | PERF-UNT-001 | pd.concat() full memory copy |
| 276-279 | unite.py | PERF-UNT-003 | drop_duplicates() after full concat |
| 891-911 | component_parser.py | CONV-UNT-001 | Indentation bug in parse_unite() |
| 230-239 | component_parser.py | CONV-UNT-002, CONV-UNT-003 | Dual path, fabricated params |
| 246-247 | converter.py | CONV-UNT-002 | Dispatch to parse_unite() |

## Appendix C: GlobalMap Variables Expected vs Actual

| Variable | Talend Sets? | V1 Sets? | Mechanism | Issue |
|----------|-------------|----------|-----------|-------|
| `{id}_NB_LINE` | Yes | No* | `_update_global_map()` in base class | BUG-UNT-001 -- base class method never called |
| `{id}_NB_LINE_OK` | No** | No* | `_update_global_map()` in base class | BUG-UNT-001 |
| `{id}_NB_LINE_REJECT` | No** | No* | `_update_global_map()` in base class | BUG-UNT-001 |
| `{id}_ERROR_MESSAGE` | Yes | No | Not implemented | ENG-UNT-005 |
| `{id}_INPUT_COUNT` | No | Yes*** | Custom code at line 297 | Non-standard |
| `{id}_MODE` | No | Yes*** | Custom code at line 298 | Non-standard |
| `{id}_INPUT_ROWS` | No | Yes*** | Custom code at line 299 | Non-standard |
| `{id}_OUTPUT_ROWS` | No | Yes*** | Custom code at line 300 | Non-standard |

\* Stats are tracked locally in `self.stats` via `_update_stats()` but never pushed to GlobalMap.
\** Talend tUnite only sets `NB_LINE` (total processed). `NB_LINE_OK` and `NB_LINE_REJECT` are not standard for tUnite.
\*** These custom variables ARE set directly via `self.global_map.put()` at lines 297-300, bypassing the standard `_update_global_map()` mechanism. They will work IF `self.global_map` is not None, but they are non-standard additions.

---

## Appendix D: Proposed Fix for BUG-UNT-001 (execute() Override)

The most impactful fix is restructuring `execute()` to preserve the base class lifecycle.
There are two approaches:

### Approach 1: Call super() with Pre-processing (Recommended)

Restructure `execute()` so that it converts multi-input dict into a format the base class
can work with, then delegates to `super().execute()`. This requires modifying `_process()`
to be the real workhorse.

```python
def execute(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
    """
    Override execute to handle multiple inputs while preserving
    the base class lifecycle (Java resolution, context resolution,
    stat tracking, GlobalMap updates, status management).
    """
    # Step 1: Pre-process input format before base class runs
    # Store multi-input data for later use by _process()
    if isinstance(input_data, dict):
        self.input_data_map = input_data
        logger.debug(f"[{self.id}] Received {len(input_data)} input streams: "
                     f"{list(input_data.keys())}")
    elif input_data is not None:
        if isinstance(input_data, pd.DataFrame):
            self.input_data_map = {'main': input_data}
            logger.debug(f"[{self.id}] Received single input stream "
                         f"with {len(input_data)} rows")
        else:
            self.input_data_map = {'main': input_data}
            logger.debug(f"[{self.id}] Received single input stream")
    else:
        logger.warning(f"[{self.id}] No input data provided")
        self.input_data_map = {}

    # Step 2: Delegate to base class execute(), which will:
    #   - Resolve Java expressions
    #   - Resolve context variables
    #   - Call _process() or _execute_streaming()
    #   - Track execution time
    #   - Update GlobalMap
    #   - Set component status
    #   - Attach stats to result
    return super().execute(input_data)


def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    Process all inputs in batch mode.
    Called by base class execute() via _execute_batch().

    Uses self.input_data_map which was populated in execute() override.
    """
    if not self.input_data_map:
        logger.warning(f"[{self.id}] No input data available for processing")
        self._update_stats(0, 0, 0)
        return {'main': pd.DataFrame()}

    # ... rest of current _process_batch() logic ...
```

This approach preserves full base class lifecycle while handling the multi-input requirement.

### Approach 2: Replicate Base Class Steps (Less Preferred)

Keep the `execute()` override but manually replicate all base class steps:

```python
def execute(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
    """
    Override execute to handle multiple inputs.
    Replicates base class lifecycle steps.
    """
    self.status = ComponentStatus.RUNNING
    start_time = time.time()

    try:
        # Step 1: Resolve Java expressions (base class step)
        if self.java_bridge:
            self._resolve_java_expressions()

        # Step 2: Resolve context variables (base class step)
        if self.context_manager:
            self.config = self.context_manager.resolve_dict(self.config)

        # Step 3: Handle different input formats
        if isinstance(input_data, dict):
            self.input_data_map = input_data
        elif input_data is not None:
            self.input_data_map = {'main': input_data}
        else:
            self.input_data_map = {}

        # Step 4: Process based on execution mode
        if self.execution_mode == ExecutionMode.STREAMING:
            result = self._process_streaming()
        else:
            result = self._process_batch()

        # Step 5: Track execution time (base class step)
        self.stats['EXECUTION_TIME'] = time.time() - start_time

        # Step 6: Update GlobalMap (base class step)
        self._update_global_map()

        # Step 7: Set status (base class step)
        self.status = ComponentStatus.SUCCESS

        # Step 8: Attach stats to result (base class step)
        result['stats'] = self.stats.copy()

        return result

    except Exception as e:
        self.status = ComponentStatus.ERROR
        self.error_message = str(e)
        self.stats['EXECUTION_TIME'] = time.time() - start_time
        self._update_global_map()

        # Set ERROR_MESSAGE in GlobalMap (Talend compatibility)
        if self.global_map:
            self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))

        logger.error(f"[{self.id}] Unite operation failed: {e}")
        raise
```

This approach is more explicit but risks diverging from the base class if new lifecycle
steps are added to `BaseComponent.execute()` in the future.

**Recommendation**: Use Approach 1. It is cleaner, DRY, and automatically picks up any
future base class enhancements.

---

## Appendix E: Proposed Fix for CONV-UNT-001 (Indentation Bug)

### Current Buggy Code

```python
def parse_unite(self, node, component: Dict) -> Dict:
    """Parse tUnite specific configuration"""
    # tUnite is simple - just combines inputs
    # Most configuration is done through connections

    # Check if there are any specific settings
    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '')

    if name == 'REMOVE_DUPLICATES':
        component['config']['remove_duplicates'] = value.lower() == 'true'
    elif name == 'MODE':
        # Some versions might have merge mode
        component['config']['mode'] = value.strip('"')

    # Default mode is UNION
    if 'mode' not in component['config']:
        component['config']['mode'] = 'UNION'

    return component
```

### Bug Analysis

The Python indentation makes the `if name == 'REMOVE_DUPLICATES':` block a sibling of
the `for` loop, not a child. The execution flow is:

1. `for param in ...`: iterates ALL elementParameter nodes
   - Each iteration ONLY assigns `name` and `value` (no processing)
2. After loop completes: `name` and `value` hold the LAST parameter's values
3. `if name == 'REMOVE_DUPLICATES':` checks ONLY the last parameter
4. `elif name == 'MODE':` checks ONLY the last parameter (if first condition was false)

This means:
- If a tUnite node has parameters `[UNIQUE_NAME, LABEL, REMOVE_DUPLICATES]` in that
  order, `REMOVE_DUPLICATES` happens to be last and IS correctly captured.
- If a tUnite node has parameters `[UNIQUE_NAME, REMOVE_DUPLICATES, LABEL]` in that
  order, the last is `LABEL`, and `REMOVE_DUPLICATES` is MISSED.
- If a tUnite node has NO elementParameter children, the loop never executes, `name` is
  undefined, and line 901 raises `NameError: name 'name' is not defined`.

### Proposed Fix

```python
def parse_unite(self, node, component: Dict) -> Dict:
    """
    Parse tUnite specific configuration.

    Talend Parameters:
        UNIQUE_NAME (str): Component identifier (handled by base parser)
        LABEL (str): Display label (handled by base parser)
        SCHEMA (str): Schema reference (handled by base parser)

    Note:
        Standard Talend tUnite has NO configurable parameters beyond
        schema and label. The REMOVE_DUPLICATES and MODE parameters
        below are non-standard extensions.
    """
    config = component.setdefault('config', {})

    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '')

        if name == 'REMOVE_DUPLICATES':
            config['remove_duplicates'] = value.lower() == 'true'
        elif name == 'MODE':
            config['mode'] = value.strip('"')

    # Default mode is UNION (matches Talend behavior)
    if 'mode' not in config:
        config['mode'] = 'UNION'

    return component
```

Key changes:
1. `if`/`elif` block is INDENTED inside the `for` loop (fixes the core bug)
2. Uses `component.setdefault('config', {})` for safety
3. No `NameError` risk when elementParameter list is empty
4. Added docstring documenting the actual Talend parameters

---

## Appendix F: Proposed Schema Validation

To address ENG-UNT-003 (no schema validation), add a validation step before concatenation:

```python
def _validate_input_schemas(self, dataframes: List[pd.DataFrame],
                             input_names: List[str]) -> None:
    """
    Validate that all input DataFrames have matching schemas.

    Talend tUnite requires all inputs to share the same schema
    (same columns, same order). This method enforces that requirement.

    Args:
        dataframes: List of input DataFrames to validate
        input_names: List of input names (for error messages)

    Raises:
        SchemaError: If schemas do not match

    Logs:
        WARNING for column order mismatches
        ERROR for missing/extra columns
    """
    if len(dataframes) < 2:
        return  # Nothing to validate with 0 or 1 inputs

    reference_columns = list(dataframes[0].columns)
    reference_name = input_names[0]

    for i, (df, name) in enumerate(zip(dataframes[1:], input_names[1:]), 1):
        current_columns = list(df.columns)

        # Check column count
        if len(current_columns) != len(reference_columns):
            logger.error(
                f"[{self.id}] Schema mismatch: input '{name}' has "
                f"{len(current_columns)} columns, but input "
                f"'{reference_name}' has {len(reference_columns)} columns"
            )
            missing = set(reference_columns) - set(current_columns)
            extra = set(current_columns) - set(reference_columns)
            if missing:
                logger.error(
                    f"[{self.id}] Missing columns in '{name}': "
                    f"{sorted(missing)}"
                )
            if extra:
                logger.error(
                    f"[{self.id}] Extra columns in '{name}': "
                    f"{sorted(extra)}"
                )
            raise SchemaError(
                f"[{self.id}] Input '{name}' schema does not match "
                f"reference input '{reference_name}': "
                f"expected {len(reference_columns)} columns, "
                f"got {len(current_columns)}"
            )

        # Check column names match
        if current_columns != reference_columns:
            # Check if same columns but different order
            if set(current_columns) == set(reference_columns):
                logger.warning(
                    f"[{self.id}] Column order mismatch: input '{name}' "
                    f"has columns in different order than '{reference_name}'. "
                    f"Reordering to match reference schema."
                )
                # Reorder to match reference (Talend uses positional alignment)
                dataframes[i] = df[reference_columns]
            else:
                missing = set(reference_columns) - set(current_columns)
                extra = set(current_columns) - set(reference_columns)
                logger.error(
                    f"[{self.id}] Column name mismatch: input '{name}' "
                    f"vs '{reference_name}'. "
                    f"Missing: {sorted(missing)}, Extra: {sorted(extra)}"
                )
                raise SchemaError(
                    f"[{self.id}] Input '{name}' column names do not "
                    f"match reference input '{reference_name}'"
                )

    logger.debug(
        f"[{self.id}] Schema validation passed: all {len(dataframes)} "
        f"inputs have matching schemas ({len(reference_columns)} columns)"
    )
```

This validation should be called in `_process_batch()` after collecting all DataFrames
and before the `pd.concat()` call:

```python
# In _process_batch(), after line 210:
if mode == 'UNION':
    # Validate schemas match before concatenation
    self._validate_input_schemas(
        dataframes,
        [name for name, data in self.input_data_map.items()
         if data is not None and not data.empty]
    )
    combined_df = pd.concat(dataframes, ignore_index=True, sort=False)
```

---

## Appendix G: Proposed Merge Order Support

To address ENG-UNT-004 (no merge order enforcement), implement deterministic ordering:

```python
def _order_inputs(self) -> List[Tuple[str, pd.DataFrame]]:
    """
    Order input DataFrames according to merge order.

    In Talend, tUnite has explicit merge order (1, 2, 3...) that
    determines the concatenation sequence. This method provides
    deterministic ordering based on:

    1. Explicit merge_order config (if provided)
    2. Alphabetical sort by input flow name (fallback)

    Returns:
        List of (input_name, DataFrame) tuples in merge order.
        Empty/None inputs are excluded.
    """
    merge_order = self.config.get('merge_order', None)

    # Filter out empty/None inputs
    valid_inputs = [
        (name, data)
        for name, data in self.input_data_map.items()
        if data is not None and not data.empty
    ]

    if not valid_inputs:
        return []

    if merge_order and isinstance(merge_order, list):
        # Explicit merge order provided
        ordered = []
        for name in merge_order:
            for input_name, data in valid_inputs:
                if input_name == name:
                    ordered.append((input_name, data))
                    break
            else:
                logger.warning(
                    f"[{self.id}] Merge order references '{name}' "
                    f"but no input with that name exists"
                )

        # Add any inputs not in merge_order at the end
        ordered_names = {name for name, _ in ordered}
        for input_name, data in valid_inputs:
            if input_name not in ordered_names:
                logger.warning(
                    f"[{self.id}] Input '{input_name}' not in merge_order, "
                    f"appending at end"
                )
                ordered.append((input_name, data))

        return ordered
    else:
        # Default: sort alphabetically by input name for determinism
        return sorted(valid_inputs, key=lambda x: x[0])
```

---

## Appendix H: Talend Generated Java Code Analysis

For reference, Talend generates Java code for tUnite that looks approximately like this
(simplified from decompiled Talend job output):

```java
// tUnite_1 - main code
// Input 1 (merge order 1): row1 from tFileInputDelimited_1
// Input 2 (merge order 2): row2 from tFileInputDelimited_2

// The generated code uses a common output row structure:
// tUnite_1Struct is the output schema
// row1Struct and row2Struct are the input schemas

// For merge order 1:
tUnite_1Struct output = new tUnite_1Struct();
output.id = row1.id;           // Positional mapping
output.name = row1.name;       // Positional mapping
output.amount = row1.amount;   // Positional mapping
// output is sent to the next component

// For merge order 2:
tUnite_1Struct output = new tUnite_1Struct();
output.id = row2.id;           // Positional mapping
output.name = row2.name;       // Positional mapping
output.amount = row2.amount;   // Positional mapping
// output is sent to the next component

// After all inputs processed:
globalMap.put("tUnite_1_NB_LINE", nb_line_tUnite_1);
```

Key observations from the generated Java code:

1. **No MERGE mode**: The generated code always concatenates. There is no join/merge logic.
2. **Positional mapping**: Columns are mapped by position, not by name. The output schema
   defines the column order, and each input maps its columns to the output in that order.
3. **Row-by-row processing**: Talend processes one row at a time, so there is no
   intermediate "concatenated DataFrame" in memory. Each input row is processed and
   immediately passed to the downstream component.
4. **NB_LINE counter**: A simple integer counter incremented for each row processed.
5. **No deduplication**: No duplicate removal logic exists in the generated code.
6. **No sorting**: No sort logic exists in the generated code.

This confirms that the V1 engine's MERGE mode, deduplication, and sorting are all
non-Talend additions.

---

## Appendix I: Impact Assessment on Existing Job Configurations

To determine how many existing converted jobs might be affected by these issues,
the following checks should be performed:

### Check 1: Jobs Using tUnite

Search converted job JSON files for components of type `Unite` or `tUnite`:

```bash
grep -rl '"type": "Unite"' jobs/ | wc -l
grep -rl '"type": "tUnite"' jobs/ | wc -l
```

### Check 2: Jobs With GlobalMap References to tUnite Stats

Search for expressions referencing tUnite NB_LINE in downstream components:

```bash
grep -r 'tUnite.*NB_LINE' jobs/
grep -r 'Unite.*NB_LINE' jobs/
```

Any matches indicate jobs that will fail or produce incorrect results due to BUG-UNT-001.

### Check 3: Jobs With MERGE Mode

Search for `mode: MERGE` or `"mode": "MERGE"` in Unite configurations:

```bash
grep -r '"mode".*"MERGE"' jobs/ | grep -i unite
```

Any matches indicate jobs at risk from ENG-UNT-002.

### Check 4: Jobs With Schema Mismatches

This requires runtime checking. For each job using Unite:
1. Run the job with validation logging enabled
2. Check for NaN values in Unite output that were not present in inputs
3. Check for column count differences between Unite inputs and outputs

### Check 5: Jobs With Context Variables

Search for `${context.` in Unite component configs:

```bash
grep -r 'context\.' jobs/ | grep -i unite
```

Any matches indicate jobs affected by the context variable resolution bypass.

---

## Appendix J: Test Implementation Skeleton

Below is a skeleton for the recommended unit test suite:

```python
"""
Tests for Unite (tUnite) component.

Tests cover:
- Basic UNION ALL behavior (matching Talend tUnite semantics)
- Multi-input handling
- Empty/None input handling
- Schema validation
- GlobalMap integration
- Statistics tracking
- Streaming mode
- Error conditions

Issue references: BUG-UNT-001, ENG-UNT-001, ENG-UNT-003, TEST-UNT-001
"""
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from src.v1.engine.components.transform.unite import Unite
from src.v1.engine.base_component import ComponentStatus


class TestUniteBasicUnion:
    """Test basic UNION ALL behavior - the core Talend tUnite functionality."""

    def setup_method(self):
        """Create a basic Unite component for testing."""
        self.config = {'mode': 'UNION'}
        self.global_map = MagicMock()
        self.component = Unite(
            component_id='tUnite_1',
            config=self.config,
            global_map=self.global_map
        )

    def test_two_identical_schema_inputs(self):
        """Two DataFrames with identical schemas should be concatenated."""
        df1 = pd.DataFrame({'id': [1, 2], 'name': ['A', 'B']})
        df2 = pd.DataFrame({'id': [3, 4], 'name': ['C', 'D']})

        input_data = {'flow1': df1, 'flow2': df2}
        result = self.component.execute(input_data)

        output = result['main']
        assert len(output) == 4
        assert list(output.columns) == ['id', 'name']
        assert output['id'].tolist() == [1, 2, 3, 4]
        assert output['name'].tolist() == ['A', 'B', 'C', 'D']

    def test_three_inputs(self):
        """Three DataFrames should all be concatenated in order."""
        df1 = pd.DataFrame({'x': [1]})
        df2 = pd.DataFrame({'x': [2]})
        df3 = pd.DataFrame({'x': [3]})

        input_data = {'flow1': df1, 'flow2': df2, 'flow3': df3}
        result = self.component.execute(input_data)

        output = result['main']
        assert len(output) == 3
        assert output['x'].tolist() == [1, 2, 3]

    def test_duplicates_kept(self):
        """UNION ALL keeps duplicate rows (Talend behavior)."""
        df1 = pd.DataFrame({'id': [1, 2], 'val': ['A', 'B']})
        df2 = pd.DataFrame({'id': [1, 2], 'val': ['A', 'B']})

        input_data = {'flow1': df1, 'flow2': df2}
        result = self.component.execute(input_data)

        output = result['main']
        assert len(output) == 4  # All 4 rows, including duplicates

    def test_single_input_dict(self):
        """Single input wrapped in dict should work."""
        df = pd.DataFrame({'id': [1, 2, 3]})
        input_data = {'main': df}
        result = self.component.execute(input_data)

        assert len(result['main']) == 3

    def test_single_input_bare_dataframe(self):
        """Single DataFrame (not dict) should be handled correctly."""
        df = pd.DataFrame({'id': [1, 2, 3]})
        result = self.component.execute(df)

        assert len(result['main']) == 3


class TestUniteEmptyInputs:
    """Test empty and None input handling."""

    def setup_method(self):
        self.config = {'mode': 'UNION'}
        self.component = Unite(
            component_id='tUnite_1',
            config=self.config
        )

    def test_none_input(self):
        """None input should return empty DataFrame."""
        result = self.component.execute(None)
        assert result['main'].empty

    def test_empty_dict(self):
        """Empty dict input should return empty DataFrame."""
        result = self.component.execute({})
        assert result['main'].empty

    def test_all_empty_dataframes(self):
        """All empty DataFrames should return empty result."""
        input_data = {
            'flow1': pd.DataFrame(),
            'flow2': pd.DataFrame()
        }
        result = self.component.execute(input_data)
        assert result['main'].empty

    def test_mixed_empty_and_nonempty(self):
        """Empty inputs should be skipped, non-empty retained."""
        df1 = pd.DataFrame({'x': [1, 2]})
        df2 = pd.DataFrame()
        df3 = pd.DataFrame({'x': [3]})

        input_data = {'flow1': df1, 'flow2': df2, 'flow3': df3}
        result = self.component.execute(input_data)

        assert len(result['main']) == 3
        assert result['main']['x'].tolist() == [1, 2, 3]

    def test_none_values_in_dict(self):
        """None values in input dict should be skipped."""
        df1 = pd.DataFrame({'x': [1]})
        input_data = {'flow1': df1, 'flow2': None}
        result = self.component.execute(input_data)

        assert len(result['main']) == 1


class TestUniteStatistics:
    """Test statistics tracking and GlobalMap integration."""

    def setup_method(self):
        self.config = {'mode': 'UNION'}
        self.global_map = MagicMock()
        self.global_map.put = MagicMock()
        self.global_map.put_component_stat = MagicMock()
        self.component = Unite(
            component_id='tUnite_1',
            config=self.config,
            global_map=self.global_map
        )

    def test_stats_correct_after_union(self):
        """NB_LINE should equal sum of input rows."""
        df1 = pd.DataFrame({'x': [1, 2, 3]})
        df2 = pd.DataFrame({'x': [4, 5]})

        input_data = {'flow1': df1, 'flow2': df2}
        self.component.execute(input_data)

        assert self.component.stats['NB_LINE'] == 5
        assert self.component.stats['NB_LINE_OK'] == 5
        assert self.component.stats['NB_LINE_REJECT'] == 0

    @pytest.mark.xfail(reason="BUG-UNT-001: execute() bypasses _update_global_map()")
    def test_globalmap_stats_set(self):
        """GlobalMap should have NB_LINE set after execution."""
        df1 = pd.DataFrame({'x': [1, 2]})
        input_data = {'flow1': df1}
        self.component.execute(input_data)

        # This assertion will FAIL until BUG-UNT-001 is fixed
        self.global_map.put_component_stat.assert_any_call(
            'tUnite_1', 'NB_LINE', 2
        )

    @pytest.mark.xfail(reason="BUG-UNT-001: execute() bypasses status tracking")
    def test_component_status_set(self):
        """Component status should be SUCCESS after execution."""
        df1 = pd.DataFrame({'x': [1]})
        self.component.execute({'flow1': df1})

        # This assertion will FAIL until BUG-UNT-001 is fixed
        assert self.component.status == ComponentStatus.SUCCESS


class TestUniteSchemaValidation:
    """Test schema matching behavior."""

    def setup_method(self):
        self.config = {'mode': 'UNION'}
        self.component = Unite(
            component_id='tUnite_1',
            config=self.config
        )

    def test_mismatched_columns_current_behavior(self):
        """
        Currently: mismatched columns produce NaN-filled rows (no validation).
        This documents the current behavior for ENG-UNT-003.
        """
        df1 = pd.DataFrame({'a': [1], 'b': [2]})
        df2 = pd.DataFrame({'a': [3], 'c': [4]})

        input_data = {'flow1': df1, 'flow2': df2}
        result = self.component.execute(input_data)

        output = result['main']
        assert len(output) == 2
        # Column 'b' has NaN for df2's row, 'c' has NaN for df1's row
        assert pd.isna(output.iloc[0]['c'])
        assert pd.isna(output.iloc[1]['b'])

    def test_different_column_count_current_behavior(self):
        """
        Currently: different column counts are silently accepted.
        Talend would reject this at design time.
        """
        df1 = pd.DataFrame({'a': [1], 'b': [2], 'c': [3]})
        df2 = pd.DataFrame({'a': [4], 'b': [5]})

        input_data = {'flow1': df1, 'flow2': df2}
        result = self.component.execute(input_data)

        output = result['main']
        assert len(output) == 2
        assert len(output.columns) == 3  # Union of all columns


class TestUniteConfigValidation:
    """Test configuration validation."""

    def test_valid_union_config(self):
        """Valid UNION config should pass validation."""
        config = {'mode': 'UNION'}
        component = Unite('test', config)
        assert component.validate_config() is True

    def test_invalid_mode(self):
        """Invalid mode should fail validation."""
        config = {'mode': 'INVALID'}
        component = Unite('test', config)
        assert component.validate_config() is False

    def test_invalid_remove_duplicates_type(self):
        """Non-boolean remove_duplicates should fail."""
        config = {'mode': 'UNION', 'remove_duplicates': 'yes'}
        component = Unite('test', config)
        assert component.validate_config() is False

    def test_default_config(self):
        """Empty config should use defaults and pass validation."""
        config = {}
        component = Unite('test', config)
        assert component.validate_config() is True


class TestUniteRemoveDuplicates:
    """Test the non-standard remove_duplicates feature."""

    def test_remove_duplicates_enabled(self):
        """With remove_duplicates=True, duplicate rows are removed."""
        config = {'mode': 'UNION', 'remove_duplicates': True}
        component = Unite('test', config)

        df1 = pd.DataFrame({'x': [1, 2]})
        df2 = pd.DataFrame({'x': [2, 3]})

        result = component.execute({'flow1': df1, 'flow2': df2})
        assert len(result['main']) == 3  # 1, 2, 3 (one duplicate removed)

    def test_remove_duplicates_keep_first(self):
        """Keep='first' retains first occurrence of duplicate."""
        config = {
            'mode': 'UNION',
            'remove_duplicates': True,
            'keep': 'first'
        }
        component = Unite('test', config)

        df1 = pd.DataFrame({'x': [1, 2], 'source': ['A', 'A']})
        df2 = pd.DataFrame({'x': [2, 3], 'source': ['B', 'B']})

        result = component.execute({'flow1': df1, 'flow2': df2})
        output = result['main']
        assert len(output) == 3
        # The duplicate row (x=2) should keep the 'A' source (first)
        row_x2 = output[output['x'] == 2].iloc[0]
        assert row_x2['source'] == 'A'


class TestUniteSortOutput:
    """Test the non-standard sort_output feature."""

    def test_sort_by_single_column(self):
        """Sort output by a single column."""
        config = {
            'mode': 'UNION',
            'sort_output': True,
            'sort_columns': ['x']
        }
        component = Unite('test', config)

        df1 = pd.DataFrame({'x': [3, 1]})
        df2 = pd.DataFrame({'x': [2, 4]})

        result = component.execute({'flow1': df1, 'flow2': df2})
        assert result['main']['x'].tolist() == [1, 2, 3, 4]

    def test_sort_by_nonexistent_column(self):
        """Sort by nonexistent column should be silently skipped."""
        config = {
            'mode': 'UNION',
            'sort_output': True,
            'sort_columns': ['nonexistent']
        }
        component = Unite('test', config)

        df1 = pd.DataFrame({'x': [2, 1]})
        result = component.execute({'flow1': df1})
        # Output should be unsorted (no valid sort columns)
        assert result['main']['x'].tolist() == [2, 1]


class TestUniteStreaming:
    """Test streaming mode behavior."""

    def test_streaming_union_yields_all_chunks(self):
        """Streaming mode should yield all input chunks."""
        config = {'mode': 'UNION', 'execution_mode': 'streaming'}
        component = Unite('test', config)

        df1 = pd.DataFrame({'x': [1, 2]})
        df2 = pd.DataFrame({'x': [3, 4]})

        result = component.execute({'flow1': df1, 'flow2': df2})

        # Result should be a generator
        chunks = list(result['main'])
        total_rows = sum(len(chunk) for chunk in chunks)
        assert total_rows == 4

    def test_streaming_merge_falls_back_to_batch(self):
        """MERGE mode in streaming should fall back to batch."""
        config = {'mode': 'MERGE', 'execution_mode': 'streaming'}
        component = Unite('test', config)

        df1 = pd.DataFrame({'x': [1], 'y': [10]})
        df2 = pd.DataFrame({'x': [1], 'z': [20]})

        result = component.execute({'flow1': df1, 'flow2': df2})

        # Should be a DataFrame (batch result), not a generator
        assert isinstance(result['main'], pd.DataFrame)
```

---

## Appendix K: Cross-Reference to Other Audit Reports

The following issues identified in this audit may also appear in or affect other
component audit reports:

| Issue | Affects | Why |
|-------|---------|-----|
| BUG-UNT-001 (execute() override bypasses base class) | Any component that overrides execute() | If other components follow the same override pattern, they will have the same lifecycle bypass. Check: `Join`, `Replicate`, and any other multi-input components. |
| CONV-UNT-001 (indentation bug) | Any parse_* method with similar loop structure | The for-loop-then-check pattern may be replicated in other parser methods. |
| ENG-UNT-003 (no schema validation) | Any multi-input component | If `Join` or other components also skip schema validation, similar silent data corruption can occur. |

### Components to Cross-Check

| Component | Reason to Check |
|-----------|-----------------|
| `Join` | Also handles multiple inputs; may have similar execute() override |
| `Replicate` | Inverse operation (1-to-many); may share patterns |
| `Map` | Complex multi-flow component; verify execute() lifecycle |
| `AggregateRow` | Transform component; verify base class compliance |

---

## Appendix L: Regression Test Checklist for Fixes

When implementing the recommended fixes, use this checklist to ensure no regressions:

### After Fixing BUG-UNT-001 (execute() lifecycle)

- [ ] Two-input UNION still produces correct concatenated output
- [ ] Three-input UNION still produces correct output
- [ ] Single DataFrame input (not dict) still works
- [ ] None input still returns empty DataFrame
- [ ] Empty dict input still returns empty DataFrame
- [ ] Mixed empty/non-empty inputs still skip empty correctly
- [ ] GlobalMap `{id}_NB_LINE` is now set correctly
- [ ] GlobalMap `{id}_NB_LINE_OK` is now set correctly
- [ ] Component status changes to `RUNNING` then `SUCCESS`
- [ ] Execution time is now tracked in `stats['EXECUTION_TIME']`
- [ ] `result['stats']` is now present in return value
- [ ] Java expressions in config (if any) are now resolved
- [ ] Context variables in config (if any) are now resolved
- [ ] Custom GlobalMap variables (`{id}_INPUT_COUNT`, etc.) still set
- [ ] Error handling still logs and raises correctly
- [ ] Error sets component status to `ERROR`

### After Fixing CONV-UNT-001 (parse_unite indentation)

- [ ] tUnite nodes with REMOVE_DUPLICATES parameter capture it correctly
- [ ] tUnite nodes with MODE parameter capture it correctly
- [ ] tUnite nodes with BOTH parameters capture both correctly
- [ ] tUnite nodes with NEITHER parameter default to mode='UNION'
- [ ] tUnite nodes with NO elementParameters do not raise NameError
- [ ] tUnite nodes with many other parameters (UNIQUE_NAME, LABEL, etc.)
      still correctly identify REMOVE_DUPLICATES and MODE among them

### After Removing MERGE Mode (if implemented)

- [ ] Config with `mode: 'UNION'` still works (no change)
- [ ] Config with `mode: 'MERGE'` raises clear error or warning
- [ ] Default config (no mode specified) still defaults to UNION
- [ ] No existing job JSON files reference `mode: 'MERGE'` for tUnite
- [ ] `_validate_config()` updated to reject MERGE mode
- [ ] Documentation updated to remove MERGE mode references

### After Adding Schema Validation

- [ ] Two inputs with identical schemas pass validation silently
- [ ] Two inputs with different column names raise SchemaError
- [ ] Two inputs with different column counts raise SchemaError
- [ ] Two inputs with same columns in different order get reordered with warning
- [ ] Single input bypasses validation (nothing to compare against)
- [ ] Empty inputs are excluded from validation
- [ ] Error messages include specific column names and input names
- [ ] Validation can be disabled via config if needed for backward compatibility
