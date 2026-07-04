---
phase: "06"
plan: "02"
subsystem: engine-transform
tags: [sort-row, rewrite, talend-parity]
dependency_graph:
  requires: [base_component, component_registry, exceptions]
  provides: [SortRow engine component with full Talend feature parity]
  affects: [transform/__init__.py]
tech_stack:
  added: []
  patterns: [sort_type key function, frozenset allowlist validation]
key_files:
  created: []
  modified:
    - src/v1/engine/components/transform/sort_row.py
decisions:
  - "D-14: All 3 sort types (num, alpha, date) implemented via pandas sort_values key= parameter"
  - "D-15: External sort flag logged but ignored -- pandas sort_values handles all sizes"
  - "D-16: Removed engine-only config keys (na_position, case_sensitive, chunk_size)"
  - "D-17: No streaming mode -- sort always operates on full DataFrame"
metrics:
  duration: "4m"
  completed: "2026-04-15"
  tasks_completed: 1
  tasks_total: 1
---

# Phase 06 Plan 02: SortRow Rewrite Summary

Clean rewrite of SortRow engine component from 396 lines to 132 lines with per-column sort type support (num/alpha/date), allowlist validation, and full ENGINE_COMPONENT_PATTERN conformance.

## What Was Done

### Task 1: Rewrite SortRow engine component

Replaced the entire 396-line sort_row.py with a clean 132-line implementation:

- **Sort types**: num (pd.to_numeric coercion), date (pd.to_datetime coercion), alpha (default string comparison)
- **Multi-column sort**: Each criterion has independent column, sort_type, and order
- **Registration**: @REGISTRY.register("SortRow", "tSortRow") decorator
- **Validation**: _validate_config checks criteria structure, sort_type against _VALID_SORT_TYPES frozenset, order against _VALID_ORDERS frozenset
- **Config keys**: Only criteria (list[dict]) and external (bool) -- removed na_position, case_sensitive, chunk_size, max_memory_rows, sort_columns, sort_orders
- **Removed**: streaming mode, external sort via tempfile/parquet, _is_streaming helper, _process_streaming, _external_sort

**Commit:** 79cad36

### Requirements Addressed

| Requirement | Description | Status |
|-------------|-------------|--------|
| SORT-01 | Sort type distinction (num/alpha/date) | Fixed -- key= function with pd.to_numeric and pd.to_datetime |
| SORT-02 | Broken external sort | Fixed -- removed entirely, pandas sort_values handles all sizes |
| SORT-03 | Streaming mode defeats sorting | Fixed -- removed streaming mode, sort always on full DataFrame |
| SORT-04 | Engine-only config keys | Fixed -- removed na_position, case_sensitive, chunk_size |
| SORT-05 | ENGINE_COMPONENT_PATTERN conformance | Fixed -- full pattern compliance |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] output_schema attribute access**
- **Found during:** Task 1 verification
- **Issue:** BaseComponent does not set output_schema in __init__ (set by engine's _initialize_components), so direct `self.output_schema` access raises AttributeError when testing outside the engine
- **Fix:** Used `getattr(self, "output_schema", None)` instead of `self.output_schema`
- **Files modified:** src/v1/engine/components/transform/sort_row.py
- **Commit:** 79cad36

## Verification Results

1. Import succeeds without error
2. REGISTRY.get("SortRow") returns SortRow class
3. REGISTRY.get("tSortRow") returns SortRow class
4. No print() statements
5. No execute() override
6. File is 132 lines (under 150 limit, down from 396)
7. Numeric sort correctly orders 1, 2, 9, 10, 100 (not lexicographic 1, 10, 100, 2, 9)
8. Date sort correctly orders by date value
9. Multi-column sort works with mixed sort types
10. Config validation rejects invalid sort_type values

## Self-Check: PASSED

- [x] src/v1/engine/components/transform/sort_row.py exists (132 lines)
- [x] Commit 79cad36 exists in git log
