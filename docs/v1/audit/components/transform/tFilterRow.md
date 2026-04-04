# Audit Report: tFilterRow / FilterRows

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFilterRow` (also `tFilterRows`) |
| **V1 Engine Class** | `FilterRows` |
| **Engine File** | `src/v1/engine/components/transform/filter_rows.py` (315 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/filter_rows.py` (121 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFilterRow")` + `@REGISTRY.register("tFilterRows")` stacked decorators |
| **Registry Aliases** | `tFilterRow`, `tFilterRows` |
| **Category** | Transform / Processing |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/filter_rows.py` | Engine implementation (315 lines) |
| `src/converters/talend_to_v1/components/transform/filter_rows.py` | Converter class (121 lines) |
| `tests/converters/talend_to_v1/components/test_filter_rows.py` | Converter tests (32 tests, 10 test classes) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 4/4 unique params + 2 framework extracted; phantoms removed (DIE_ON_ERROR, PREFILTER); stride-4 CONDITIONS parser |
| Engine Feature Parity | **Y** | 1 | 3 | 2 | 1 | eval() security risk; only 6/14+ Talend operators; no FUNCTION pre-transforms; string coercion |
| Code Quality | **G** | 0 | 0 | 0 | 0 | Converter follows gold standard pattern; clean, well-documented |
| Performance & Memory | **Y** | 0 | 1 | 1 | 0 | Row-by-row eval() in advanced mode; debug print loop |
| Testing | **Y** | 0 | 0 | 1 | 0 | 32 converter tests passing; no engine unit tests |

**Overall: YELLOW -- Converter is gold standard. Engine has eval() security risk and limited operator support.**

**Top Actions**:
1. Replace eval() with AST-based expression parser in engine advanced mode (P0 security)
2. Add engine support for Talend string operators (CONTAINS, MATCHES_REGEX, etc.)
3. Fix engine `.toList()` typo to `.tolist()` (crashes simple conditions mode)
4. Remove 17+ print() debug statements from engine
5. Add engine unit tests

---

## 3. Talend Feature Baseline

### What tFilterRow Does

tFilterRow filters incoming rows based on either simple column conditions or advanced Java expressions. In simple mode, each condition specifies a column, an optional pre-transform function (e.g., LENGTH, ABS_VALUE, TRIM), a comparison operator, and a reference value. Multiple conditions are combined with a logical operator (AND/OR). In advanced mode, a freeform Java expression replaces the conditions table.

tFilterRows is a variant that provides multiple reject outputs (one per condition group), whereas tFilterRow provides a single reject output.

**Source**: Talaxie GitHub _java.xml
**Component family**: Processing / Filter
**Available in**: Talend Open Studio, Talend Data Integration, all variants
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Logical Operator | `LOGICAL_OP` | CLOSED_LIST | `"AND"` | Combine conditions: AND (all must match) or OR (any must match) |
| 2 | Conditions | `CONDITIONS` | TABLE (stride-4) | `[]` | Filter conditions table with 4 fields per row |
| 2a | -- Input Column | `INPUT_COLUMN` | elementRef | -- | Column name to evaluate |
| 2b | -- Function | `FUNCTION` | elementRef | -- | Pre-transform function (EMPTY, LENGTH, ABS_VALUE, TRIM, etc.) |
| 2c | -- Operator | `OPERATOR` | elementRef | -- | Comparison operator (==, !=, <, >, <=, >=, CONTAINS, etc.) |
| 2d | -- Value | `RVALUE` | elementRef | -- | Reference value for comparison |
| 3 | Use Advanced | `USE_ADVANCED` | CHECK | `false` | Toggle advanced Java expression mode |
| 4 | Advanced Condition | `ADVANCED_COND` | MEMO_JAVA | `""` | Java expression for advanced filtering |

### 3.2 Framework Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 5 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Enable statistics collection |
| 6 | Label | `LABEL` | TEXT | `""` | Component label for display |

### 3.3 Phantom Parameters

The following parameters were found in the old converter but are NOT in the _java.xml definition:

| Parameter | Status | Notes |
|-----------|--------|-------|
| `DIE_ON_ERROR` | **PHANTOM** | Not in _java.xml. Was extracted by old converter. Removed. |
| `PREFILTER` (CONDITIONS column) | **PHANTOM** | Not a _java.xml elementRef in CONDITIONS TABLE. Was parsed as stride-5 column. Removed. |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input/Output | Row > Main | Input data rows; output contains accepted rows |
| `REJECT` | Output | Row > Reject | Rows that failed the filter condition |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on error |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows accepted |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows rejected |

### 3.6 Behavioral Notes

1. **LOGICAL_OP is CLOSED_LIST**: Values are `"AND"` or `"OR"` (string, not XML-escaped logical operators).
2. **CONDITIONS stride-4**: Each condition row in the TABLE has exactly 4 elementRef entries: INPUT_COLUMN, FUNCTION, OPERATOR, RVALUE. There is NO PREFILTER column.
3. **FUNCTION pre-transforms**: EMPTY means no function; LENGTH, ABS_VALUE, TRIM, etc. are applied before the comparison.
4. **Advanced mode**: When USE_ADVANCED=true, the CONDITIONS table is ignored and ADVANCED_COND Java expression is used instead.
5. **tFilterRows variant**: Same parameters but routes rejections to separate outputs per condition.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses the gold standard pattern with `_build_component_dict()`, stride-4 CONDITIONS table parser, and per-feature needs_review entries.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `LOGICAL_OP` | Yes | `logical_op` | _get_str, default "AND" |
| 2 | `CONDITIONS` (TABLE) | Yes | `conditions` | Stride-4 parser, list of {column, function, operator, value} dicts |
| 3 | `USE_ADVANCED` | Yes | `use_advanced` | _get_bool, default False |
| 4 | `ADVANCED_COND` | Yes | `advanced_cond` | _get_str, default "" |
| 5 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework, _get_bool, default False |
| 6 | `LABEL` | Yes | `label` | Framework, _get_str, default "" |

**Summary**: 4 of 4 unique parameters + 2 framework parameters extracted (100%).

### 4.2 Schema Extraction

Transform passthrough pattern: input schema == output schema (both populated from FLOW connector).

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | From SchemaColumn |
| `type` | Yes | Via convert_type() |
| `nullable` | Yes | Boolean |
| `key` | Yes | Boolean |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date conversion |
| `default` | No | Not supported in base class |

### 4.3 Expression Handling

Context variables in ADVANCED_COND are stored as-is (raw string). Resolution happens at engine runtime. TABLE values are stripped of surrounding quotes via `.strip('"')`.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FR-001 | ~~P1~~ | **FIXED** -- Phantom DIE_ON_ERROR removed (not in _java.xml) |
| CONV-FR-002 | ~~P1~~ | **FIXED** -- Phantom PREFILTER column removed from CONDITIONS TABLE (stride-5 -> stride-4) |
| CONV-FR-003 | ~~P1~~ | **FIXED** -- Config keys standardized (logical_operator -> logical_op, advanced_condition -> advanced_cond) |
| CONV-FR-004 | ~~P2~~ | **FIXED** -- Uses _build_component_dict with type_name="FilterRows" |
| CONV-FR-005 | ~~P2~~ | **FIXED** -- Stacked dual registration decorators for tFilterRow and tFilterRows |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | `conditions.function` | Engine does not support FUNCTION pre-transforms on conditions | engine_gap |
| 2 | `advanced_cond` | Engine uses eval() for advanced conditions -- security risk, limited operator support | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Simple conditions (==, !=, <, >, <=, >=) | **Yes** | Medium | `_evaluate_single_condition()` L245 | All comparisons use string coercion (`.astype(str)`) |
| 2 | Logical operator AND/OR | **Yes** | High | `_process_simple_conditions()` L199 | Correct mask combination |
| 3 | Advanced condition (Java expr) | **Partial** | Low | `_process_advanced_condition()` L179 | Uses Python `eval()` not Java; security risk |
| 4 | FUNCTION pre-transforms | **No** | N/A | -- | Not implemented; FUNCTION column ignored by engine |
| 5 | String operators (CONTAINS, MATCHES_REGEX, etc.) | **No** | N/A | -- | Only 6 numeric comparison operators supported |
| 6 | Reject output | **Yes** | High | `_process()` L159-160 | Proper mask inversion for reject rows |
| 7 | Statistics (NB_LINE, NB_LINE_OK, NB_LINE_REJECT) | **Yes** | High | `_update_stats()` L168 | Correct counts |
| 8 | Context variable resolution | **Yes** | Medium | `_evaluate_single_condition()` L261 | Via context_manager.resolve_string() |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FR-001 | **P0** | `eval()` in advanced mode executes arbitrary Python code -- Talend uses sandboxed Java expression evaluation |
| ENG-FR-002 | **P1** | Only 6 operators (==, !=, <, >, <=, >=) supported -- Talend has 14+ including CONTAINS, NOT_CONTAINS, STARTS_WITH, ENDS_WITH, MATCH_REGEX, MATCH_REGEX_CS |
| ENG-FR-003 | **P1** | FUNCTION pre-transforms (LENGTH, ABS_VALUE, TRIM, etc.) not implemented -- conditions always compare raw column values |
| ENG-FR-004 | **P1** | All comparisons use `.astype(str)` string coercion -- numeric ordering breaks (e.g., "9" > "10" in string comparison) |
| ENG-FR-005 | **P2** | Advanced condition strips `input_row.` prefix but Talend uses `row.` prefix -- expression translation incomplete |
| ENG-FR-006 | **P2** | `.toList()` typo on line 242 will crash when simple conditions are used (should be `.tolist()`) |
| ENG-FR-007 | **P3** | tFilterRows multi-reject-output routing not implemented |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Total rows processed |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | Accepted rows count |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | Rejected rows count |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FR-001 | **P0** | `filter_rows.py:242` | `.toList()` typo -- should be `.tolist()`. Crashes simple conditions mode. |
| BUG-FR-002 | **P1** | `filter_rows.py:276` | String coercion via `.astype(str)` for ALL comparisons including numeric -- "9" > "10" evaluates True |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FR-001 | **P2** | Engine reads `logical_operator` but converter now outputs `logical_op` -- engine config key mismatch |
| NAME-FR-002 | **P2** | Engine reads `advanced_condition` but converter outputs `advanced_cond` -- engine config key mismatch |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FR-001 | **P2** | "No print() in production code" | 17+ print() statements throughout engine file |
| STD-FR-002 | **P3** | "Use logger for all output" | Debug output mixed with logger calls |

### 6.4 Debug Artifacts

**CRITICAL**: The engine file contains 17+ `print()` statements scattered throughout production code:
- Lines 119, 121-123, 131-132, 144-145, 150, 165, 177, 194, 196, 218, 237, 242, 268, 272-273, 289, 299

These print statements output internal state, DataFrames, and per-row comparisons. They produce massive output on large datasets and must be removed or converted to `logger.debug()`.

### 6.5 Security

**CRITICAL: Code injection via eval()** -- See Section 11 Risk Assessment.

The engine uses bare `eval()` on line 195 to evaluate advanced condition expressions:
```python
mask = input_data.apply(lambda row: eval(expr, {}, row.to_dict()), axis=1)
```
No `__builtins__` restriction is applied. User-supplied expressions can execute arbitrary Python code including file I/O, network calls, and system commands.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Correct (`logging.getLogger(__name__)`) |
| Level usage | Mixed -- logger.debug/info/error used alongside print() statements |
| Sensitive data | Config values logged/printed including condition values |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | None -- raises generic Exception |
| Exception chaining | Not used |
| die_on_error handling | Not implemented (phantom param in old converter, engine has no support) |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | Good -- all methods have return types and parameter types |
| Parameter types | Good -- Dict[str, Any], pd.DataFrame, pd.Series used correctly |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FR-001 | **P1** | Advanced mode `eval()` row-by-row via `apply()` -- not vectorizable, O(n) Python calls |
| PERF-FR-002 | **P2** | Debug print loop on lines 298-299 iterates every row printing repr values -- O(n) I/O per condition |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Supported via base class chunked execution |
| Memory threshold | Good -- uses boolean mask for split, no full copy until final `.copy()` |
| Large data handling | Acceptable for simple mode; advanced mode eval() is slow on large datasets |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 32 | `tests/converters/talend_to_v1/components/test_filter_rows.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-FR-001 | **P2** | No engine unit tests for FilterRows class |

### 8.3 Recommended Test Cases

1. Engine: Simple conditions with numeric and string columns
2. Engine: Advanced mode with valid and malicious expressions
3. Engine: Reject output contains correct rows
4. Engine: Empty DataFrame input returns empty result
5. Engine: Unknown operator handling
6. Engine: Context variable resolution in condition values

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 1 | **ENG-FR-001** |
| P1 | 4 | **ENG-FR-002**, **ENG-FR-003**, **ENG-FR-004**, **PERF-FR-001** |
| P2 | 6 | **ENG-FR-005**, **ENG-FR-006**, **NAME-FR-001**, **NAME-FR-002**, **STD-FR-001**, **PERF-FR-002** |
| P3 | 2 | **ENG-FR-007**, **STD-FR-002** |
| **Total** | **13** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Converter (CONV) | 0 | All 5 fixed |
| Engine (ENG) | 7 | ENG-FR-001 through -007 |
| Bug (BUG) | 2 | BUG-FR-001, BUG-FR-002 |
| Naming (NAME) | 2 | NAME-FR-001, NAME-FR-002 |
| Standards (STD) | 2 | STD-FR-001, STD-FR-002 |
| Performance (PERF) | 2 | PERF-FR-001, PERF-FR-002 |
| Testing (TEST) | 1 | TEST-FR-001 |

Note: BUG-FR-001 overlaps with ENG-FR-006 (.toList() typo). BUG-FR-002 overlaps with ENG-FR-004 (string coercion). Counted once in summary to avoid inflation.

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken signature |
| XCUT-003 | All components | Zero engine unit tests |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Replace eval() with AST-based parser** (ENG-FR-001/P0) -- Critical security vulnerability; user expressions can execute arbitrary code
2. **Fix .toList() typo** (ENG-FR-006/BUG-FR-001) -- Crashes simple conditions mode

### Short-term (Hardening)

3. **Add string operator support** (ENG-FR-002) -- CONTAINS, MATCHES_REGEX, etc.
4. **Implement FUNCTION pre-transforms** (ENG-FR-003) -- LENGTH, ABS_VALUE, TRIM
5. **Fix string coercion** (ENG-FR-004/BUG-FR-002) -- Use proper type-aware comparisons
6. **Remove print() statements** (STD-FR-001) -- 17+ debug prints in production code
7. **Add engine unit tests** (TEST-FR-001)

### Long-term (Optimization)

8. **Implement tFilterRows multi-reject routing** (ENG-FR-007)
9. **Vectorize advanced condition evaluation** (PERF-FR-001)

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Code injection via eval()** | High | Critical | Advanced mode passes user expressions to bare `eval()` on engine line 195 with no `__builtins__` restriction. Any job using `use_advanced=True` can execute arbitrary Python code. Recommend replacing with `ast.literal_eval()` or a custom AST-based expression parser. |
| **Silent operator failures** | High | Medium | Engine only supports 6 comparison operators. Talend conditions using CONTAINS, MATCHES_REGEX, STARTS_WITH, ENDS_WITH silently evaluate to False (all rows rejected). No warning or error produced at runtime. |
| **FUNCTION column ignored** | Medium | Medium | The FUNCTION pre-transform column (LENGTH, ABS_VALUE, TRIM, etc.) is extracted by the converter but the engine ignores it entirely. Conditions that depend on pre-transforms will compare wrong values. |
| **Numeric ordering broken** | High | Medium | All comparisons use `.astype(str)` string coercion. Numeric comparisons like `value > 9` will incorrectly match "10" < "9" because string comparison is lexicographic. |
| **Debug output flood** | High | Low | 17+ print() statements produce massive output on large datasets, potentially filling logs and degrading I/O performance. One print loop iterates every row per condition. |

### High-Risk Job Patterns

- Jobs using `use_advanced=True` with ADVANCED_COND containing user-supplied input (code injection)
- Jobs with FUNCTION pre-transforms other than EMPTY (silently ignored)
- Jobs using string operators (CONTAINS, MATCHES_REGEX) -- silently reject all rows
- Jobs comparing numeric columns with inequality operators (<, >, <=, >=) -- string comparison breaks ordering

### Safe Usage Patterns

- Simple equality/inequality conditions on string columns
- `use_advanced=False` with basic operators (==, !=) on string data
- Static ADVANCED_COND expressions that don't accept external input

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub _java.xml | `https://github.com/Talaxie/tcommon-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tFilterRow/tFilterRow_java.xml` | Parameter definitions, defaults, CONDITIONS TABLE structure |
| Engine source | `src/v1/engine/components/transform/filter_rows.py` (315 lines) | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/transform/filter_rows.py` (121 lines) | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_filter_rows.py` (32 tests) | Test coverage analysis |

## Appendix B: Engine Config Key Mapping

| Converter Config Key | Engine Reads | Match? | Notes |
|---------------------|-------------|--------|-------|
| `logical_op` | `logical_operator` | No | Engine uses longer key name |
| `conditions` | `conditions` | Yes | Both use list of condition dicts |
| `use_advanced` | `use_advanced` | Yes | Boolean toggle |
| `advanced_cond` | `advanced_condition` | No | Engine uses longer key name |
| `tstatcatcher_stats` | -- | N/A | Framework param, not read by engine |
| `label` | -- | N/A | Framework param, not read by engine |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after full rewrite -- converter standardized to gold standard, phantom params removed, Section 11 Risk Assessment added*
