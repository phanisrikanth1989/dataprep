# Phase 7: Transform Group B -- Column, Join, Unite - Research

**Researched:** 2026-04-15
**Domain:** Engine component rewrites (tJoin, tFilterColumns, tUnite) -- pandas DataFrame operations
**Confidence:** HIGH

## Summary

Phase 7 rewrites three transform components following the Phase 6 pattern: tJoin gets a full rewrite (8 bugs including P0 data corruption), tFilterColumns gets a simplification from 205 lines to ~50 (schema-based column selection), and tUnite gets a simplification from 393 lines to ~50 (UNION-only concat). All three follow the ENGINE_COMPONENT_PATTERN.md blueprint with @REGISTRY.register decorator, _validate_config() raising ConfigurationError, and _process() returning dict with 'main' and optionally 'reject' keys.

The heavy lift is tJoin. The current implementation has systemic issues: case-insensitive join mutates original data (P0 corruption), null keys match via pandas NaN==NaN behavior (violates SQL semantics), reject computation uses a second merge (inefficient and buggy), config keys are UPPERCASE but converter outputs lowercase, and INCLUDE_LOOKUP/ERROR_MESSAGE features are missing. The rewrite reads converter keys directly (use_inner_join, join_key with {input_column, lookup_column} dicts), uses temp columns for case-insensitive matching, sentinel-based null pre-filtering, and computes reject from a single merge with indicator.

FilterColumns and Unite are straightforward. FilterColumns becomes: read output_schema column names, select those columns from input DataFrame. Unite becomes: collect all input DataFrames from dict, pd.concat with ignore_index=True.

**Primary recommendation:** Rewrite all three components from scratch following the Phase 6 pattern. tJoin is Plan 01 (heavy), FilterColumns + Unite + all tests are Plan 02 (light).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Full rewrite from scratch. 8 bugs including P0 data corruption + config key mismatches = systemic issues. Phase 6 rewrite pattern.
- **D-02:** Read converter keys directly: `use_inner_join` (bool), `join_key` (list of `{input_column, lookup_column}` dicts), `use_lookup_cols` (bool), `lookup_cols` (list of `{output_column, lookup_column}` dicts).
- **D-03:** Null join semantics: pre-filter null keys before merge. Replace NaN with sentinel, merge, filter sentinel matches. Talend/SQL behavior: null != null.
- **D-04:** Case-insensitive join: create lowercase temp columns for matching, keep originals intact. Drop temp columns after merge. No data corruption.
- **D-05:** Implement INCLUDE_LOOKUP toggle (JOIN-04): when `use_lookup_cols=false`, exclude lookup-only columns from output. When true, include specified `lookup_cols`.
- **D-06:** Implement ERROR_MESSAGE globalMap variable (JOIN-05): `{id}_ERROR_MESSAGE` set on join errors.
- **D-07:** Fix reject output: reject = main rows with no lookup match. Compute correctly without double merge.
- **D-08:** Populate reject schema from `schema.reject` config, add errorCode/errorMessage columns.
- **D-09:** Rewrite to schema-based filtering. Talend uses output schema as the column filter. Read `schema.output` column names and select those from input DataFrame. Remove `mode`, `columns`, `keep_row_order` config keys that aren't Talend params.
- **D-10:** ~50 lines replacing 205 lines. Trivial component: select columns from output schema, return filtered DataFrame.
- **D-11:** Simplify to UNION only. Talend tUnite only does concat. Remove MERGE mode, streaming mode, sort_output, remove_duplicates -- none are Talend features.
- **D-12:** Use _process() only, remove custom execute() override. Engine passes dict of DataFrames. Follow BaseComponent pattern.
- **D-13:** ~50 lines replacing 393 lines. Collect all input DataFrames, pd.concat with ignore_index=True.
- **D-14:** @REGISTRY.register decorator for all three: Join/tJoin, FilterColumns/tFilterColumns, Unite/tUnite.
- **D-15:** 2 plans: Plan 01 = tJoin rewrite (heavy), Plan 02 = FilterColumns + Unite rewrites + all tests.
- **D-16:** Test location: `tests/v1/engine/components/transform/test_join.py`, `test_filter_columns.py`, `test_unite.py`.
- **D-17:** Phase 6 test patterns: programmatic DataFrame creation, _DEFAULT_CONFIG, _make_component helpers, @pytest.mark.unit.
- **D-18:** Exhaustive coverage per requirement. Every JOIN/FCOL/UNIT requirement gets dedicated test cases.

### Claude's Discretion
- Internal method decomposition within tJoin
- Exact sentinel value strategy for null key handling
- How to handle the input mapping (main/lookup identification from dict of DataFrames)
- Edge case behavior for empty lookup DataFrames

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FCOL-01 | Add engine unit tests -- component is functionally Green but untested (P2) | Schema-based filtering pattern is trivial; tests validate column selection from output_schema |
| FCOL-02 | Verify mode and keep_row_order engine-only keys work correctly (P2) | D-09 removes these non-Talend keys; rewrite validates this implicitly |
| JOIN-01 | Fix case-insensitive join lowercase corruption -- join mutates original data (P0) | D-04: temp columns for case-insensitive matching, originals untouched |
| JOIN-02 | Fix left outer join incorrect reject output (P1) | D-07: single merge with indicator=True, reject = left_only rows |
| JOIN-03 | Fix reject schema never populated (P1) | D-08: read reject schema from engine-set attribute, add errorCode/errorMessage |
| JOIN-04 | Implement INCLUDE_LOOKUP toggle -- control whether lookup columns appear in output (P1) | D-05: use_lookup_cols/lookup_cols config keys from converter |
| JOIN-05 | Implement ERROR_MESSAGE globalMap variable (P1) | D-06: set {id}_ERROR_MESSAGE on join errors |
| JOIN-06 | Fix schema attribute mismatch dead code (P2) | Full rewrite eliminates dead code; reads converter keys directly |
| JOIN-07 | Fix double merge for reject computation -- optimize to single pass (P2) | D-07: single merge with indicator, reject from left_only mask |
| JOIN-08 | Fix null join semantics -- pandas merge matches NaN==NaN but Talend/SQL does not (P1) | D-03: sentinel-based null pre-filtering before merge |
| UNIT-01 | Add engine unit tests -- component is functionally Green but untested (P2) | UNION-only concat is trivial; tests validate multi-input concat |
| UNIT-02 | Verify union behavior with mismatched schemas (P2) | pd.concat handles mismatched schemas by filling missing with NaN |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 3.0.1 (installed) | DataFrame merge, concat, column selection | Core data transport for all engine components [VERIFIED: runtime check in prior phases] |
| numpy | (bundled with pandas) | NaN sentinel detection | Required for null-key pre-filtering [VERIFIED: already imported in base_component.py] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 (installed) | Unit test framework | All component tests [VERIFIED: pytest --version] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Sentinel NaN strategy | Drop NaN rows pre-merge | Sentinel preserves row count tracking; dropping loses count info |
| pd.merge indicator | Set difference for reject | Indicator is single-pass; set difference requires second operation |

No additional packages needed. All three components use only pandas operations already available.

## Architecture Patterns

### Component File Structure (Blueprint)
```
src/v1/engine/components/transform/
    join.py              # Full rewrite (~200-250 lines)
    filter_columns.py    # Full rewrite (~50 lines)
    unite.py             # Full rewrite (~50 lines)
```

### Pattern 1: Multi-Input Component via _process() Dict
**What:** Components receiving multiple inputs get a `Dict[str, DataFrame]` from OutputRouter.get_input_data(). [VERIFIED: output_router.py lines 150-169]
**When to use:** Join (main + lookup), Unite (input1 + input2 + ...)
**Critical detail:** OutputRouter returns a single DataFrame when len(inputs)==1, or a dict when len(inputs)>=2. Components receiving dicts must handle this in _process().

```python
# Source: src/v1/engine/output_router.py lines 150-169 [VERIFIED: codebase]
def get_input_data(self, comp_id: str) -> Optional[Any]:
    inputs = self._component_inputs.get(comp_id, [])
    if not inputs:
        return None
    if len(inputs) == 1:
        return self._data_flows.get(inputs[0])
    return {flow_name: self._data_flows.get(flow_name) for flow_name in inputs}
```

**Implication for _process() signature:** For Join and Unite, _process() receives a dict of DataFrames, NOT a single DataFrame. The _process() type hint should be `Optional[dict]` for these components, but BaseComponent declares `Optional[pd.DataFrame]`. This is safe because Python doesn't enforce type hints at runtime, and the execute() -> _execute_batch() -> _process() chain just passes whatever get_input_data() returns.

### Pattern 2: Sentinel-Based Null Key Filtering (tJoin)
**What:** Replace NaN values in join key columns with a unique sentinel string before merge, then filter out sentinel-matched rows after merge. [ASSUMED -- strategy from D-03]
**When to use:** Every tJoin execution to enforce Talend/SQL null != null semantics.

```python
# Sentinel approach for null join keys [ASSUMED -- design pattern]
_NULL_SENTINEL = "__DATAPREP_NULL_SENTINEL__"

# Before merge: replace NaN in key columns with sentinel
main_keys_df[key_col] = main_keys_df[key_col].fillna(_NULL_SENTINEL)
lookup_keys_df[key_col] = lookup_keys_df[key_col].fillna(_NULL_SENTINEL)

# After merge: rows where ANY key was sentinel are treated as non-matches
sentinel_mask = False
for key_col in key_columns:
    sentinel_mask |= (merged[key_col] == _NULL_SENTINEL)

# These rows go to reject, not main output
```

**Verified behavior:** pandas merge matches NaN==NaN. [VERIFIED: runtime test confirmed NaN rows join in inner merge]

### Pattern 3: Temp Columns for Case-Insensitive Join (tJoin)
**What:** Create lowercase temporary columns for matching, perform merge on temp columns, then drop temps. Original data preserved. [ASSUMED -- strategy from D-04]
**When to use:** When case-insensitive join is needed (which is always in Talend tJoin -- there is no CASE_SENSITIVE param in Talend _java.xml).

```python
# Case-insensitive join via temp columns [ASSUMED -- design pattern]
_TEMP_PREFIX = "__ci_"

# Create temp lowercase columns on both sides
for main_col, lookup_col in zip(main_key_cols, lookup_key_cols):
    main_df[f"{_TEMP_PREFIX}{main_col}"] = main_df[main_col].astype(str).str.lower()
    lookup_df[f"{_TEMP_PREFIX}{lookup_col}"] = lookup_df[lookup_col].astype(str).str.lower()

# Merge on temp columns
merged = pd.merge(main_df, lookup_df,
    left_on=[f"{_TEMP_PREFIX}{c}" for c in main_key_cols],
    right_on=[f"{_TEMP_PREFIX}{c}" for c in lookup_key_cols],
    how=how, indicator=True)

# Drop temp columns
temp_cols = [c for c in merged.columns if c.startswith(_TEMP_PREFIX)]
merged.drop(columns=temp_cols, inplace=True)
```

### Pattern 4: Schema-Based Column Filtering (tFilterColumns)
**What:** Talend tFilterColumns uses the output schema as the column filter, not a separate mode/columns config. The engine sets `self.output_schema` from `comp_config.schema.output`. [VERIFIED: engine.py line 116, converter filter_columns.py line 44]
**When to use:** tFilterColumns -- the ONLY behavior this component needs.

```python
# Source: ENGINE_COMPONENT_PATTERN.md Rule 11 [VERIFIED: codebase]
# output_schema is set by engine from comp_config.schema.output
def _process(self, input_data=None) -> dict:
    if input_data is None or input_data.empty:
        return {"main": input_data, "reject": None}
    
    # output_schema is list[dict] with 'name' key per column
    schema_cols = [col["name"] for col in (self.output_schema or [])]
    if not schema_cols:
        return {"main": input_data, "reject": None}
    
    # Select only columns present in both schema and input
    available = [c for c in schema_cols if c in input_data.columns]
    return {"main": input_data[available].copy(), "reject": None}
```

### Pattern 5: UNION-Only Concat (tUnite)
**What:** Talend tUnite is strictly UNION ALL (vertical concat). No MERGE, no dedup, no sort. [VERIFIED: converter unite.py has no unique params, only framework params]
**When to use:** tUnite -- collect all DataFrames from input dict, pd.concat.

```python
# Source: pandas pd.concat docs [VERIFIED: pandas API]
def _process(self, input_data=None) -> dict:
    if not input_data or not isinstance(input_data, dict):
        return {"main": pd.DataFrame(), "reject": None}
    
    dfs = [df for df in input_data.values()
           if df is not None and isinstance(df, pd.DataFrame) and not df.empty]
    
    if not dfs:
        return {"main": pd.DataFrame(), "reject": None}
    
    combined = pd.concat(dfs, ignore_index=True, sort=False)
    return {"main": combined, "reject": None}
```

### Anti-Patterns to Avoid
- **Override execute():** The current unite.py overrides execute() -- this breaks BaseComponent lifecycle (config immutability, expression resolution, stats). D-12 mandates _process() only. [VERIFIED: ENGINE_COMPONENT_PATTERN.md Rule 4]
- **UPPERCASE config keys in engine:** Current join.py reads `USE_INNER_JOIN`, `JOIN_KEY`, `CASE_SENSITIVE` but converter outputs `use_inner_join`, `join_key`. D-02 mandates reading converter keys directly (lowercase). [VERIFIED: converter join.py lines 121-130]
- **Store state on self:** Current unite.py stores `self.input_data_map` on the instance -- this leaks between iterate re-executions. Rule 10 forbids this. [VERIFIED: ENGINE_COMPONENT_PATTERN.md Rule 10]
- **Second merge for reject:** Current join.py does two pd.merge calls (lines 258-284) -- one for the join, one for reject computation. Use indicator=True on a single merge. [VERIFIED: current join.py]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Case-insensitive matching | .str.lower() on original columns | Temp lowercase columns + merge on temps | Mutating originals corrupts data downstream (P0 bug JOIN-01) |
| Null key exclusion | NaN row filtering pre-merge | Sentinel replacement + post-merge filtering | Sentinel preserves row tracking; pre-filtering loses rows from stats |
| Reject computation | Second pd.merge with indicator | Single pd.merge with indicator=True | Double merge is O(2N); single merge with indicator is O(N) |
| Multi-input routing | Custom execute() with input mapping | Let BaseComponent.execute() -> _process(dict) | OutputRouter already returns dict for multi-input components |
| Column filtering | mode/columns config parsing | output_schema column names | Talend tFilterColumns has NO mode/columns params -- output schema IS the filter |

**Key insight:** Every bug in the current implementations stems from building custom solutions for problems already solved by pandas or BaseComponent. The rewrites are simpler because they delegate to the framework.

## Common Pitfalls

### Pitfall 1: NaN == NaN in pandas merge
**What goes wrong:** pandas merge matches NaN keys, but Talend/SQL treats NULL != NULL. Rows with null join keys get incorrectly joined.
**Why it happens:** pandas follows numpy NaN propagation rules, not SQL NULL semantics.
**How to avoid:** Replace NaN with unique sentinel string before merge, filter sentinel matches after merge.
**Warning signs:** Test with null keys in both main and lookup -- if they join, the bug is present.
**Verified:** Confirmed via runtime test -- pd.merge returns NaN-matched rows in inner join. [VERIFIED: runtime test]

### Pitfall 2: Case-insensitive join corrupts original data
**What goes wrong:** Applying .str.lower() to join key columns modifies the original DataFrame, causing downstream components to see corrupted (lowercased) data.
**Why it happens:** Even with .copy(), if you lower the key columns on the copy that goes into the merge, the merged output carries the lowercased values.
**How to avoid:** Create separate temp columns with `_TEMP_PREFIX`, merge on temps, drop temps after merge. Original columns remain untouched in the merged output.
**Warning signs:** Output DataFrame has lowercased values in join key columns when input had mixed case.

### Pitfall 3: _process() receives dict, not DataFrame, for multi-input components
**What goes wrong:** Component expects `pd.DataFrame` but receives `dict[str, pd.DataFrame]` from OutputRouter for multi-input components.
**Why it happens:** OutputRouter.get_input_data() returns dict when component has >= 2 inputs. [VERIFIED: output_router.py lines 162-169]
**How to avoid:** For Join and Unite, _process() must handle dict input. Check `isinstance(input_data, dict)`. For Join, identify main vs lookup from flow names. For Unite, iterate all values.
**Warning signs:** `AttributeError: 'dict' object has no attribute 'empty'` at runtime.

### Pitfall 4: Reject schema not set as component attribute
**What goes wrong:** Trying to access `self.reject_schema` fails because the engine only sets `input_schema` and `output_schema` on components. [VERIFIED: engine.py lines 115-116]
**Why it happens:** Engine's _initialize_components() reads schema.input and schema.output but not schema.reject.
**How to avoid:** For Join reject handling (D-08), the component needs reject schema. Options: (a) read from the schema stored as a sibling of config in the job JSON -- but this isn't accessible from the component since only `config` dict is passed, OR (b) add `component.reject_schema = comp_config.get('schema', {}).get('reject', [])` in the engine's _initialize_components(). Option (b) is a one-line addition to engine.py and follows the same pattern as output_schema/input_schema.
**Warning signs:** AttributeError on self.reject_schema, or join reject output missing errorCode/errorMessage columns.

### Pitfall 5: pd.concat with mismatched columns fills with NaN
**What goes wrong:** When Unite concats DataFrames with different column sets, missing columns are filled with NaN. This is correct Talend behavior for UNION ALL.
**Why it happens:** pd.concat aligns on column names; missing columns get NaN.
**How to avoid:** This is actually correct behavior for Talend's tUnite. Just verify in tests that mismatched schemas produce the expected NaN fills. [VERIFIED: pandas concat docs]
**Warning signs:** None -- this is the desired behavior.

### Pitfall 6: __init__.py import must change for @REGISTRY.register
**What goes wrong:** Currently transform/__init__.py imports `from .join import Join` (bare class). After adding @REGISTRY.register, this import TRIGGERS registration. But the import needs to succeed -- if the new file has import errors, registration fails silently and the engine can't find the component.
**Why it happens:** Decorator-based registration happens at import time. Any ImportError in the module prevents registration.
**How to avoid:** Test imports explicitly in test_join.py: `assert REGISTRY.get("Join") is not None`. Ensure the __init__.py imports still work after rewrite.
**Warning signs:** Engine logs "Unknown component type: Join" at runtime.

### Pitfall 7: First-match deduplication for lookup (tJoin)
**What goes wrong:** Talend tJoin uses first-match semantics for lookup -- if multiple lookup rows match the same key, only the first is used.
**Why it happens:** Talend's default behavior mirrors SQL FIRST_VALUE or UNIQUE_MATCH.
**How to avoid:** Deduplicate lookup DataFrame on join keys with `drop_duplicates(subset=lookup_keys, keep='first')` before merging. The current implementation already does this (line 251), so the rewrite must preserve this behavior.
**Warning signs:** Joined output has more rows than the main input (row multiplication from duplicate lookup matches).

## Code Examples

### tJoin _process() Structure (Recommended)
```python
# Source: Design pattern from D-01 through D-08 and codebase analysis [VERIFIED: codebase + CONTEXT.md]
@REGISTRY.register("Join", "tJoin")
class Join(BaseComponent):
    """tJoin engine implementation."""

    def _validate_config(self) -> None:
        join_key = self.config.get("join_key", [])
        if not join_key or not isinstance(join_key, list):
            raise ConfigurationError(f"[{self.id}] 'join_key' must be a non-empty list")
        for i, mapping in enumerate(join_key):
            if "input_column" not in mapping:
                raise ConfigurationError(f"[{self.id}] join_key[{i}] missing 'input_column'")
            if "lookup_column" not in mapping:
                raise ConfigurationError(f"[{self.id}] join_key[{i}] missing 'lookup_column'")

    def _process(self, input_data=None) -> dict:
        # input_data is dict: {"flow_name_1": DataFrame, "flow_name_2": DataFrame}
        main_df, lookup_df = self._resolve_inputs(input_data)
        
        use_inner_join = self.config.get("use_inner_join", False)
        join_key = self.config.get("join_key", [])
        # ... sentinel null handling, temp columns, merge, reject ...
        
        return {"main": main_out, "reject": reject_out}
```

### tFilterColumns _process() Structure (Recommended)
```python
# Source: D-09, D-10 and output_schema pattern from ENGINE_COMPONENT_PATTERN.md [VERIFIED: codebase]
@REGISTRY.register("FilterColumns", "tFilterColumns")
class FilterColumns(BaseComponent):
    """tFilterColumns engine implementation."""

    def _validate_config(self) -> None:
        pass  # No config keys to validate -- schema drives behavior

    def _process(self, input_data=None) -> dict:
        if input_data is None or (isinstance(input_data, pd.DataFrame) and input_data.empty):
            return {"main": input_data, "reject": None}
        schema_cols = [col["name"] for col in (self.output_schema or [])]
        if not schema_cols:
            return {"main": input_data, "reject": None}
        available = [c for c in schema_cols if c in input_data.columns]
        return {"main": input_data[available].copy(), "reject": None}
```

### tUnite _process() Structure (Recommended)
```python
# Source: D-11 through D-13 and OutputRouter multi-input pattern [VERIFIED: codebase]
@REGISTRY.register("Unite", "tUnite")
class Unite(BaseComponent):
    """tUnite engine implementation."""

    def _validate_config(self) -> None:
        pass  # No config keys to validate -- concat all inputs

    def _process(self, input_data=None) -> dict:
        if not input_data or not isinstance(input_data, dict):
            return {"main": pd.DataFrame(), "reject": None}
        dfs = [df for df in input_data.values()
               if df is not None and isinstance(df, pd.DataFrame) and not df.empty]
        if not dfs:
            return {"main": pd.DataFrame(), "reject": None}
        combined = pd.concat(dfs, ignore_index=True, sort=False)
        return {"main": combined, "reject": None}
```

### Test Pattern (from Phase 6)
```python
# Source: tests/v1/engine/components/transform/test_sort_row.py [VERIFIED: codebase]
_DEFAULT_CONFIG = {
    "component_type": "Join",
    "use_inner_join": False,
    "join_key": [
        {"input_column": "id", "lookup_column": "ref_id"},
    ],
    "use_lookup_cols": False,
    "lookup_cols": [],
}

def _make_component(config=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    comp = Join(
        component_id="tJoin_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    # Set schemas as engine would
    comp.output_schema = [{"name": "id", "type": "str", "nullable": True}]
    comp.reject_schema = []  # Need engine to set this
    return comp
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| UPPERCASE config keys (JOIN_KEY, USE_INNER_JOIN) | lowercase converter keys (join_key, use_inner_join) | Phase 4/6 pattern | All Phase 7 components read lowercase keys directly |
| Override execute() for multi-input | _process() receives dict from OutputRouter | Phase 3 | Unite no longer needs execute() override |
| Manual input mapping in _process() | OutputRouter.get_input_data() returns named dict | Phase 3 | Join/Unite get named inputs automatically |
| Separate __init__.py __all__ registration | @REGISTRY.register decorator | Phase 3 | No manual registry maintenance |

**Deprecated/outdated:**
- UPPERCASE config keys: Converter outputs lowercase. Engine used to have a manual COMPONENT_REGISTRY dict with uppercase keys. Now all goes through REGISTRY with converter key names.
- execute() override for multi-input: BaseComponent.execute() -> _execute_batch() -> _process() already passes whatever OutputRouter provides. No need to intercept.

## Assumptions Log

> List all claims tagged [ASSUMED] in this research.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Sentinel string "__DATAPREP_NULL_SENTINEL__" won't collide with real data | Architecture Patterns, Pattern 2 | Unlikely -- sentinel is a 30-char internal string. Could use UUID if paranoid. |
| A2 | Temp column prefix "__ci_" won't collide with existing column names | Architecture Patterns, Pattern 3 | Very unlikely -- double underscore prefix is not a Talend pattern. |
| A3 | Talend tJoin always uses first-match for duplicate lookup keys | Pitfall 7 | MEDIUM -- tJoin docs say "unique match" but actual behavior is first-match. Tests will verify. |
| A4 | Talend tJoin has no CASE_SENSITIVE parameter in _java.xml | Architecture Patterns, Pattern 3 | MEDIUM -- converter removed it as phantom param. If wrong, it's a converter issue not engine. |

**If this table is empty:** Not applicable -- 4 assumptions listed above.

## Open Questions

1. **Reject schema access in tJoin**
   - What we know: Engine sets output_schema and input_schema but NOT reject_schema on components. The converter outputs schema.reject for tJoin. [VERIFIED: engine.py lines 115-116]
   - What's unclear: Should the engine be updated to also set reject_schema, or should the component read it from config?
   - Recommendation: Add one line to engine.py _initialize_components(): `component.reject_schema = comp_config.get('schema', {}).get('reject', [])`. This follows the existing pattern exactly. Include this as a task in Plan 01.

2. **Main vs lookup identification in input dict**
   - What we know: OutputRouter returns `{flow_name: DataFrame}` where flow names are the Talend flow names (e.g., "row1", "row2", "lookup_1"). The component's `self.inputs` list has these flow names in declared order.
   - What's unclear: How to reliably identify which input is "main" and which is "lookup". The converter sets `inputs: []` which gets populated by the engine from flows_config.
   - Recommendation: Use the component's `self.inputs` list (set by engine from comp_config.inputs). Convention: first input is main, second is lookup. Validate that exactly 2 inputs are present. This matches the current join.py approach (lines 179-188).

3. **CASE_SENSITIVE as a Talend parameter**
   - What we know: The converter's join.py header says "Phantom params REMOVED: CASE_SENSITIVE, DIE_ON_ERROR (not in _java.xml)". [VERIFIED: converter join.py line 14]
   - What's unclear: Whether the engine should still support case-sensitive vs case-insensitive, or always do case-insensitive (Talend default).
   - Recommendation: Talend tJoin is always case-sensitive by default (Java string equality is case-sensitive). Do NOT add case-insensitive logic unless explicitly configured. The converter doesn't output a case_sensitive flag, so the engine should default to case-sensitive matching. The temp-column approach from D-04 should only be activated when a future config flag requests it, OR if Talend actually outputs a flag for this. For now: case-sensitive matching is the default, no temp columns needed for the base case. Revisit D-04 if Talend evidence shows otherwise.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `python -m pytest tests/v1/engine/components/transform/test_join.py tests/v1/engine/components/transform/test_filter_columns.py tests/v1/engine/components/transform/test_unite.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FCOL-01 | FilterColumns unit tests | unit | `python -m pytest tests/v1/engine/components/transform/test_filter_columns.py -x` | -- Wave 0 |
| FCOL-02 | Remove engine-only keys (mode, keep_row_order) | unit | Same as above -- verify no config keys needed | -- Wave 0 |
| JOIN-01 | Case-insensitive join preserves original data | unit | `python -m pytest tests/v1/engine/components/transform/test_join.py -x -k case_insensitive` | -- Wave 0 |
| JOIN-02 | Left outer join correct reject output | unit | `python -m pytest tests/v1/engine/components/transform/test_join.py -x -k reject` | -- Wave 0 |
| JOIN-03 | Reject schema populated with errorCode/errorMessage | unit | `python -m pytest tests/v1/engine/components/transform/test_join.py -x -k reject_schema` | -- Wave 0 |
| JOIN-04 | INCLUDE_LOOKUP toggle controls lookup columns in output | unit | `python -m pytest tests/v1/engine/components/transform/test_join.py -x -k lookup_cols` | -- Wave 0 |
| JOIN-05 | ERROR_MESSAGE globalMap variable set on errors | unit | `python -m pytest tests/v1/engine/components/transform/test_join.py -x -k error_message` | -- Wave 0 |
| JOIN-06 | No dead code (full rewrite eliminates) | unit | Verified by clean rewrite -- no test needed |
| JOIN-07 | Single-pass merge (no double merge) | unit | `python -m pytest tests/v1/engine/components/transform/test_join.py -x -k single_pass` | -- Wave 0 |
| JOIN-08 | Null keys do not match (Talend/SQL semantics) | unit | `python -m pytest tests/v1/engine/components/transform/test_join.py -x -k null` | -- Wave 0 |
| UNIT-01 | Unite unit tests | unit | `python -m pytest tests/v1/engine/components/transform/test_unite.py -x` | -- Wave 0 |
| UNIT-02 | Mismatched schema union behavior | unit | `python -m pytest tests/v1/engine/components/transform/test_unite.py -x -k mismatched` | -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/v1/engine/components/transform/test_join.py tests/v1/engine/components/transform/test_filter_columns.py tests/v1/engine/components/transform/test_unite.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/v1/engine/components/transform/test_join.py` -- covers JOIN-01 through JOIN-08
- [ ] `tests/v1/engine/components/transform/test_filter_columns.py` -- covers FCOL-01, FCOL-02
- [ ] `tests/v1/engine/components/transform/test_unite.py` -- covers UNIT-01, UNIT-02
- [ ] `tests/v1/engine/components/transform/__init__.py` -- already exists

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python 3.10+ engine -- no framework changes
- **Compatibility**: Must produce identical output to Talend for same input data and job config
- **No breaking changes**: Converter JSON format must remain compatible
- **Existing patterns**: Engine component pattern must align with ABC + registry + per-component organization
- **Error handling**: Custom exception hierarchy (ConfigurationError, DataValidationError, etc.) -- no generic exceptions
- **Naming**: snake_case for files/functions, PascalCase for classes, UPPER_SNAKE_CASE for constants
- **Logging**: logging.getLogger(__name__), no print(), no emojis/unicode (ASCII-only for RHEL)
- **Imports**: Relative within package (from ...base_component import BaseComponent)
- **Docstrings**: Google-style with Args:/Returns:/Raises: sections for engine code
- **Config keys**: Engine reads converter keys directly (lowercase) -- established in Phase 4/6

## Sources

### Primary (HIGH confidence)
- `src/v1/engine/base_component.py` -- BaseComponent lifecycle, _process() contract, stats
- `src/v1/engine/component_registry.py` -- REGISTRY decorator pattern
- `src/v1/engine/output_router.py` -- Multi-input routing (lines 150-169)
- `src/v1/engine/engine.py` -- _initialize_components() schema setting (lines 95-124)
- `src/converters/talend_to_v1/components/transform/join.py` -- Converter output keys for tJoin
- `src/converters/talend_to_v1/components/transform/filter_columns.py` -- Converter output keys for tFilterColumns
- `src/converters/talend_to_v1/components/transform/unite.py` -- Converter output keys for tUnite
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` -- Component blueprint (12 rules)
- `src/v1/engine/components/transform/filter_rows.py` -- Phase 6 rewrite reference
- `src/v1/engine/components/transform/sort_row.py` -- Phase 6 rewrite reference
- `tests/v1/engine/components/transform/test_sort_row.py` -- Phase 6 test pattern reference
- `tests/v1/engine/components/transform/test_filter_rows.py` -- Phase 6 test pattern reference

### Secondary (MEDIUM confidence)
- Runtime pandas merge NaN test -- confirmed NaN==NaN matching behavior

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pandas/pytest already in use, no new dependencies
- Architecture: HIGH -- OutputRouter multi-input pattern verified in codebase, Phase 6 patterns established
- Pitfalls: HIGH -- NaN merge behavior verified at runtime, case-insensitive corruption is the P0 bug motivating the rewrite

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable -- internal codebase patterns don't change externally)
