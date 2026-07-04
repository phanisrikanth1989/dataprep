---
phase: 05-tmap-component
fixed_at: 2026-04-15T00:54:09Z
review_path: .planning/phases/05-tmap-component/05-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 5: Code Review Fix Report

**Fixed at:** 2026-04-15T00:54:09Z
**Source review:** .planning/phases/05-tmap-component/05-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8
- Fixed: 8
- Skipped: 0

## Fixed Issues

### CR-01: Cross-table join inner reject tracking uses wrong index space

**Files modified:** `src/v1/engine/components/transform/map.py`
**Commit:** 154bd05
**Status:** fixed: requires human verification
**Applied fix:** Replaced index-based reject detection with a column-value merge approach. After the cross join, `matched` has a new RangeIndex that does not correspond to `joined_df`'s index. The fix uses `joined_df.merge(matched_main_rows.assign(__matched__=True), on=main_cols, how="left")` to correctly identify unmatched main rows by comparing actual column values. Also removed the unused `matched_main_idx` variable (IN-01).

### WR-01: Dead code -- "numeric to str" auto-conversion branches are unreachable

**Files modified:** `src/v1/engine/components/transform/map.py`
**Commit:** acb751a
**Applied fix:** Removed the unreachable `numeric -> str` elif branches (lines 1757-1764 in original) that were shadowed by the identical `str -> numeric` conditions above them. Added a clarifying comment explaining the strategy: str-to-numeric conversion always wins, matching Talend BigDecimal coercion semantics. The `int <-> float` branches remain untouched.

### WR-02: _is_context_only_expression double-strips java marker

**Files modified:** `src/v1/engine/components/transform/map.py`
**Commit:** 5e5e623
**Applied fix:** Replaced `self._strip_java_marker(expr).strip()` with `expr.strip()` since the caller `_classify_join_type` already strips the java marker before passing the expression. Added inline comment documenting this contract.

### WR-03: RELOAD_AT_EACH_ROW double-prefixes lookup columns

**Files modified:** `src/v1/engine/components/transform/map.py`
**Commit:** 4161ef9
**Applied fix:** Replaced `lookup_prefixed = self._prefix_lookup_columns(lookup_df, lookup_name)` (which copied the entire DataFrame just to extract column names) with a lightweight list comprehension `lookup_prefixed_cols` that computes the prefixed column names directly. Updated the empty-result fallback at the end of the method to use the new list variable.

### WR-04: _route_catch_output_rejects mutates shared error_df

**Files modified:** `src/v1/engine/components/transform/map.py`
**Commit:** 2f779a4
**Applied fix:** Added `output_df = error_df.copy()` before mutating the DataFrame (adding `errorMessage` column). Each output now receives its own independent copy, preventing shared-reference mutation across multiple catch_output_reject outputs.

### IN-01: Unused variable matched_main_idx

**Files modified:** `src/v1/engine/components/transform/map.py`
**Commit:** 154bd05 (included in CR-01 fix)
**Applied fix:** The unused `matched_main_idx` assignment was removed as part of the CR-01 fix, which replaced the entire inner join reject tracking block with a correct merge-based approach.

### IN-02: Regex compiled on every call in _is_context_only_expression

**Files modified:** `src/v1/engine/components/transform/map.py`
**Commit:** 9ee6db8
**Applied fix:** Extracted the inline `re.compile(...)` call to a module-level constant `_ROW_REF_PATTERN`, consistent with the existing `_SIMPLE_COLUMN_RE` pattern. Updated `_is_context_only_expression` to reference the pre-compiled constant.

### IN-03: Integration test hardcoded path may not exist in all environments

**Files modified:** `tests/v1/engine/components/transform/test_map_integration.py`
**Commit:** fbbb8d6
**Applied fix:** Added `_SAMPLE_EXISTS = _SAMPLE_JSON.exists()` flag and a module-level `pytestmark = pytest.mark.skipif(not _SAMPLE_EXISTS, reason="Sample JSON not found")` so all tests in the module are gracefully skipped when the sample JSON file is absent, rather than failing with FileNotFoundError.

---

_Fixed: 2026-04-15T00:54:09Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
