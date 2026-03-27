# V1 Engine Audit -- Summary Scorecard

## Overview

**Total components audited:** 54
**Total issues found (raw):** 2,015
**Estimated unique issues:** ~1,720-1,820 (after deducting cross-cutting duplicates)
**Overall assessment:** NOT PRODUCTION-READY. The v1 engine has systemic quality gaps across all 54 components. Cross-cutting base class bugs affect every component. Zero components have adequate test coverage. 18 components are rated RED (broken/blocks production), 35 are rated YELLOW (works partially with gaps), and 1 is rated RED/YELLOW (borderline). No component achieved an overall GREEN rating.

### Important Note on Issue Counts

The raw count of 2,015 includes **cross-cutting issues that are counted in every component report**. The same underlying bug appears as a separate issue ID in each affected report (e.g., `BUG-FID-001`, `BUG-FOD-001`, `BUG-MAP-001` are all the same `_update_global_map()` crash). This is intentional — each report is self-contained so developers working on a specific component see all issues relevant to them.

**Cross-cutting duplicates (~200-250 entries from ~15-20 unique bugs):**

| Cross-cutting Bug | Appears In | Unique Fix |
|---|---|---|
| `_update_global_map()` crash (base_component.py:304) | All 54 reports | 1 line fix |
| `GlobalMap.get()` broken signature (global_map.py:28) | All 54 reports | 1 line fix |
| Zero unit tests | All 54 reports | 1 systemic gap |
| `replace_in_config` literal `[i]` (base_component.py:174) | ~20 reports | 1 line fix |
| `_execute_streaming` drops reject data | ~15 reports | 1 method fix |
| `validate_schema` inverted nullable logic | ~10 reports | 1 condition fix |
| `self.config` mutation non-reentrant | ~10 reports | 1 pattern fix |
| `resolve_dict` corrupts `python_code` | ~5 reports | 1 skip-list addition |
| Converter `.find().get()` null-safety pattern | ~15 reports | 1 pattern fix per parser |

**Impact of fixing cross-cutting bugs:** Fixing just the top 5 cross-cutting bugs (~25 minutes of work) would resolve ~200+ issue entries across all reports simultaneously. This is the highest-leverage work available.

---

## Traffic Light Matrix

Score key: **R** = Red (broken/blocks production), **Y** = Yellow (works partially, gaps exist), **G** = Green (production-ready), **N/A** = Not applicable.

| # | Component | Overall | Converter | Engine | Code Quality | Performance | Testing | P0 | P1 | P2 | P3 | Total |
|---|-----------|---------|-----------|--------|-------------|-------------|---------|----|----|----|----|-------|
| 1 | tFileInputDelimited | Y | G | Y | Y | G | R | 2 | 12 | 17 | 7 | 38 |
| 2 | tFileOutputDelimited | Y | G | Y | Y | G | R | 2 | 16 | 17 | 10 | 45 |
| 3 | tFileInputExcel | Y | G | Y | Y | G | R | 5 | 12 | 21 | 11 | 49 |
| 4 | tFileOutputExcel | Y | Y | Y | Y | Y | R | 4 | 14 | 19 | 7 | 44 |
| 5 | tFileInputJSON | Y | Y | Y | Y | G | R | 4 | 16 | 17 | 7 | 44 |
| 6 | tFileInputXML | R | Y | Y | R | Y | R | 4 | 21 | 22 | 7 | 54 |
| 7 | tFileInputPositional | R | Y | Y | R | G | R | 3 | 13 | 20 | 6 | 42 |
| 8 | tFileOutputPositional | R | Y | R | R | Y | R | 4 | 13 | 16 | 6 | 39 |
| 9 | tFileInputFullRow | Y | Y | Y | Y | Y | R | 4 | 16 | 15 | 10 | 45 |
| 10 | tFileInputRaw | Y | Y | Y | R | Y | R | 4 | 11 | 11 | 7 | 33 |
| 11 | tRowGenerator | R | Y | Y | R | Y | R | 5 | 14 | 12 | 6 | 37 |
| 12 | tFixedFlowInput | Y | Y | Y | Y | G | R | 4 | 15 | 14 | 7 | 40 |
| 13 | tFileArchive | Y | G | Y | Y | G | R | 2 | 8 | 17 | 9 | 36 |
| 14 | tFileUnarchive | Y | G | Y | Y | G | R | 2 | 12 | 14 | 3 | 31 |
| 15 | tFileCopy | Y | G | Y | Y | G | R | 2 | 9 | 15 | 6 | 32 |
| 16 | tFileDelete | Y | G | Y | Y | G | R | 2 | 10 | 11 | 6 | 29 |
| 17 | tFileExist | Y | Y | Y | Y | G | R | 6 | 11 | 7 | 3 | 27 |
| 18 | tFileProperties | Y | G | Y | Y | Y | R | 2 | 6 | 14 | 8 | 30 |
| 19 | tFileRowCount | Y | G | Y | Y | G | R | 2 | 10 | 11 | 7 | 30 |
| 20 | tFileTouch | Y | G | Y | Y | G | R | 2 | 5 | 5 | 7 | 19 |
| 21 | tFilterRow | R | G | R | R | Y | R | 5 | 18 | 19 | 6 | 48 |
| 22 | tFilterColumns | Y | Y | Y | Y | G | R | 3 | 14 | 8 | 6 | 31 |
| 23 | tSortRow | R | Y | Y | R | Y | R | 4 | 15 | 17 | 8 | 44 |
| 24 | tUniqueRow | Y | Y | Y | Y | G | R | 4 | 10 | 21 | 11 | 46 |
| 25 | tMap | Y | G | Y | Y | Y | R | 5 | 11 | 19 | 9 | 44 |
| 26 | tJoin | Y | Y | Y | Y | G | R | 6 | 12 | 13 | 5 | 36 |
| 27 | tNormalize | R | G | Y | R | R | R | 5 | 9 | 11 | 4 | 29 |
| 28 | tDenormalize | Y | Y | Y | Y | G | R | 3 | 9 | 9 | 7 | 28 |
| 29 | tReplicate | Y | G | Y | Y | Y | R | 4 | 4 | 10 | 5 | 23 |
| 30 | tLogRow | Y | Y | Y | Y | G | R | 3 | 10 | 19 | 9 | 41 |
| 31 | tUnite | R | Y | R | R | Y | R | 6 | 7 | 8 | 4 | 25 |
| 32 | tAggregateRow | Y | Y | Y | Y | G | R | 8 | 13 | 17 | 11 | 49 |
| 33 | tAggregateSortedRow | R | Y | R | Y | R | R | 5 | 18 | 18 | 5 | 46 |
| 34 | tExtractDelimitedFields | R | Y | Y | R | R | R | 5 | 13 | 14 | 7 | 39 |
| 35 | tExtractJSONFields | R | Y | Y | R | Y | R | 5 | 12 | 14 | 8 | 39 |
| 36 | tExtractXMLField | Y | Y | Y | Y | Y | R | 5 | 12 | 19 | 9 | 45 |
| 37 | tExtractPositionalFields | Y | Y | Y | Y | Y | R | 3 | 14 | 14 | 5 | 36 |
| 38 | tPivotToColumnsDelimited | R | Y | Y | R | Y | R | 7 | 15 | 22 | 6 | 50 |
| 39 | tUnpivotRow | R | R | Y | Y | Y | R | 6 | 14 | 18 | 7 | 45 |
| 40 | tSchemaComplianceCheck | R | R | R | R | R | R | 8 | 13 | 16 | 7 | 44 |
| 41 | tDie | Y | G | Y | Y | G | R | 3 | 8 | 13 | 3 | 27 |
| 42 | tWarn | Y | Y | Y | Y | G | R | 3 | 6 | 6 | 4 | 19 |
| 43 | tSleep | Y | Y | Y | Y | G | R | 3 | 7 | 4 | 4 | 18 |
| 44 | tSendMail | Y | Y | Y | Y | G | R | 3 | 17 | 16 | 7 | 43 |
| 45 | tContextLoad | R | Y | Y | R | G | R | 4 | 14 | 19 | 6 | 43 |
| 46 | tSetGlobalVar | Y | Y | Y | Y | G | R | 3 | 10 | 11 | 5 | 29 |
| 47 | tJava | Y | Y | Y | Y | R | R | 5 | 12 | 13 | 8 | 38 |
| 48 | tJavaRow | Y | Y | Y | Y | Y | R | 6 | 14 | 17 | 9 | 46 |
| 49 | tXMLMap | R | R | R | R | Y | R | 6 | 19 | 24 | 9 | 58 |
| 50 | PythonComponent | R | R | Y | R | G | R | 4 | 10 | 11 | 3 | 28 |
| 51 | PythonRowComponent | R | R | Y | Y | Y | R | 5 | 12 | 15 | 2 | 34 |
| 52 | PythonDataFrameComponent | Y | Y | Y | Y | G | R | 3 | 9 | 11 | 2 | 25 |
| 53 | SwiftTransformer | R/Y | R | Y | Y | Y | R | 5 | 7 | 17 | 8 | 37 |
| 54 | SwiftBlockFormatter | Y | N/A | Y | Y | Y | R | 3 | 10 | 16 | 9 | 38 |

---

## Rating Distribution

### Overall Component Ratings

| Rating | Count | Percentage |
|--------|-------|------------|
| **R** (Red -- blocks production) | 18 | 33.3% |
| **R/Y** (Borderline) | 1 | 1.9% |
| **Y** (Yellow -- partial, gaps exist) | 35 | 64.8% |
| **G** (Green -- production-ready) | 0 | 0.0% |

### Per-Dimension Rating Distribution

| Dimension | Red | Yellow | Green | N/A |
|-----------|-----|--------|-------|-----|
| Converter | 6 | 32 | 15 | 1 |
| Engine | 6 | 48 | 0 | 0 |
| Code Quality | 16 | 38 | 0 | 0 |
| Performance | 5 | 22 | 27 | 0 |
| Testing | 54 | 0 | 0 | 0 |

**Testing is universally Red**: Every single component has zero or near-zero test coverage.

---

## Priority Distribution

| Priority | Total Issues | Percentage | Description |
|----------|-------------|------------|-------------|
| **P0** (Critical) | 221 | 11.0% | Blocks production use or causes data corruption/silent failures |
| **P1** (Major) | 642 | 31.9% | Significant functional gap or behavioral divergence from Talend |
| **P2** (Moderate) | 794 | 39.4% | Missing feature, code quality concern, or non-standard practice |
| **P3** (Low) | 358 | 17.8% | Minor improvement, cosmetic issue, or rarely-used feature gap |
| **Total** | **2,015** | -- | -- |

---

## Most Critical Components (Ranked by P0 Count)

| Rank | Component | P0 | P1 | P2 | P3 | Total | Overall |
|------|-----------|----|----|----|----|-------|---------|
| 1 | tAggregateRow | 8 | 13 | 17 | 11 | 49 | Y |
| 2 | tSchemaComplianceCheck | 8 | 13 | 16 | 7 | 44 | R |
| 3 | tPivotToColumnsDelimited | 7 | 15 | 22 | 6 | 50 | R |
| 4 | tJavaRow | 6 | 14 | 17 | 9 | 46 | Y |
| 5 | tUnpivotRow | 6 | 14 | 18 | 7 | 45 | R |
| 6 | tJoin | 6 | 12 | 13 | 5 | 36 | Y |
| 7 | tFileExist | 6 | 11 | 7 | 3 | 27 | Y |
| 8 | tUnite | 6 | 7 | 8 | 4 | 25 | R |
| 9 | tMap | 5 | 11 | 19 | 9 | 44 | Y |
| 10 | tFilterRow | 5 | 18 | 19 | 6 | 48 | R |

---

## Cross-Cutting Issues Summary

The following issues were identified in virtually every component report and represent systemic bugs in the v1 engine infrastructure rather than component-specific problems:

1. **`_update_global_map()` crash (P0)**: The base class method `_update_global_map()` references an undefined variable, causing an `UnboundLocalError` at runtime whenever `global_map` is provided. Affects all 54 components.

2. **`GlobalMap.get()` broken signature (P0)**: The `GlobalMap.get()` method has an incorrect parameter signature that causes a crash when called with the expected arguments. Affects all components that interact with globalMap.

3. **`_validate_config()` dead code (P1)**: The `_validate_config()` method is defined in most components but is never called by the base class `execute()` method. Configuration validation is completely bypassed at runtime.

4. **Zero test coverage (P0)**: Not a single component in the v1 engine has meaningful unit or integration tests. The entire engine is unverified.

5. **No custom exception usage (P2)**: Components use generic Python exceptions instead of the custom exception classes defined in the codebase (e.g., `ConfigurationError`, `FileOperationError`).

6. **`print()` instead of logger (P2)**: Multiple components use `print()` statements for debugging/logging instead of the Python `logging` module, making production log management impossible.

7. **No REJECT flow (P1)**: The vast majority of components do not implement the Talend REJECT output flow pattern, meaning errored rows are silently dropped rather than routed to an error-handling path.

8. **`die_on_error` default mismatch (P1)**: Many components default `die_on_error` to `False`, whereas Talend defaults to `True`. This means the v1 engine silently swallows errors that Talend would surface.

See `CROSS_CUTTING_ISSUES.md` for the complete cross-cutting analysis (to be created as a companion document).

---

## Component Categories

### File I/O Components (20)

| # | Component | Overall | P0 | P1 | P2 | P3 | Total |
|---|-----------|---------|----|----|----|----|-------|
| 1 | tFileInputDelimited | Y | 2 | 12 | 17 | 7 | 38 |
| 2 | tFileOutputDelimited | Y | 2 | 16 | 17 | 10 | 45 |
| 3 | tFileInputExcel | Y | 5 | 12 | 21 | 11 | 49 |
| 4 | tFileOutputExcel | Y | 4 | 14 | 19 | 7 | 44 |
| 5 | tFileInputJSON | Y | 4 | 16 | 17 | 7 | 44 |
| 6 | tFileInputXML | R | 4 | 21 | 22 | 7 | 54 |
| 7 | tFileInputPositional | R | 3 | 13 | 20 | 6 | 42 |
| 8 | tFileOutputPositional | R | 4 | 13 | 16 | 6 | 39 |
| 9 | tFileInputFullRow | Y | 4 | 16 | 15 | 10 | 45 |
| 10 | tFileInputRaw | Y | 4 | 11 | 11 | 7 | 33 |
| 11 | tRowGenerator | R | 5 | 14 | 12 | 6 | 37 |
| 12 | tFixedFlowInput | Y | 4 | 15 | 14 | 7 | 40 |
| 13 | tFileArchive | Y | 2 | 8 | 17 | 9 | 36 |
| 14 | tFileUnarchive | Y | 2 | 12 | 14 | 3 | 31 |
| 15 | tFileCopy | Y | 2 | 9 | 15 | 6 | 32 |
| 16 | tFileDelete | Y | 2 | 10 | 11 | 6 | 29 |
| 17 | tFileExist | Y | 6 | 11 | 7 | 3 | 27 |
| 18 | tFileProperties | Y | 2 | 6 | 14 | 8 | 30 |
| 19 | tFileRowCount | Y | 2 | 10 | 11 | 7 | 30 |
| 20 | tFileTouch | Y | 2 | 5 | 5 | 7 | 19 |

**Category summary:** 4 Red, 16 Yellow, 0 Green. Total issues: 744.

### Transform Components (21)

| # | Component | Overall | P0 | P1 | P2 | P3 | Total |
|---|-----------|---------|----|----|----|----|-------|
| 1 | tFilterRow | R | 5 | 18 | 19 | 6 | 48 |
| 2 | tFilterColumns | Y | 3 | 14 | 8 | 6 | 31 |
| 3 | tSortRow | R | 4 | 15 | 17 | 8 | 44 |
| 4 | tUniqueRow | Y | 4 | 10 | 21 | 11 | 46 |
| 5 | tMap | Y | 5 | 11 | 19 | 9 | 44 |
| 6 | tJoin | Y | 6 | 12 | 13 | 5 | 36 |
| 7 | tNormalize | R | 5 | 9 | 11 | 4 | 29 |
| 8 | tDenormalize | Y | 3 | 9 | 9 | 7 | 28 |
| 9 | tReplicate | Y | 4 | 4 | 10 | 5 | 23 |
| 10 | tLogRow | Y | 3 | 10 | 19 | 9 | 41 |
| 11 | tUnite | R | 6 | 7 | 8 | 4 | 25 |
| 12 | tExtractDelimitedFields | R | 5 | 13 | 14 | 7 | 39 |
| 13 | tExtractJSONFields | R | 5 | 12 | 14 | 8 | 39 |
| 14 | tExtractXMLField | Y | 5 | 12 | 19 | 9 | 45 |
| 15 | tExtractPositionalFields | Y | 3 | 14 | 14 | 5 | 36 |
| 16 | tPivotToColumnsDelimited | R | 7 | 15 | 22 | 6 | 50 |
| 17 | tUnpivotRow | R | 6 | 14 | 18 | 7 | 45 |
| 18 | tSchemaComplianceCheck | R | 8 | 13 | 16 | 7 | 44 |
| 19 | tXMLMap | R | 6 | 19 | 24 | 9 | 58 |
| 20 | SwiftTransformer | R/Y | 5 | 7 | 17 | 8 | 37 |
| 21 | SwiftBlockFormatter | Y | 3 | 10 | 16 | 9 | 38 |

**Category summary:** 10 Red (incl. 1 R/Y), 11 Yellow, 0 Green. Total issues: 826.

### Aggregate Components (2)

| # | Component | Overall | P0 | P1 | P2 | P3 | Total |
|---|-----------|---------|----|----|----|----|-------|
| 1 | tAggregateRow | Y | 8 | 13 | 17 | 11 | 49 |
| 2 | tAggregateSortedRow | R | 5 | 18 | 18 | 5 | 46 |

**Category summary:** 1 Red, 1 Yellow, 0 Green. Total issues: 95.

### Control Components (5)

| # | Component | Overall | P0 | P1 | P2 | P3 | Total |
|---|-----------|---------|----|----|----|----|-------|
| 1 | tDie | Y | 3 | 8 | 13 | 3 | 27 |
| 2 | tWarn | Y | 3 | 6 | 6 | 4 | 19 |
| 3 | tSleep | Y | 3 | 7 | 4 | 4 | 18 |
| 4 | tSendMail | Y | 3 | 17 | 16 | 7 | 43 |
| 5 | tSetGlobalVar | Y | 3 | 10 | 11 | 5 | 29 |

**Category summary:** 0 Red, 5 Yellow, 0 Green. Total issues: 136.

### Context Components (1)

| # | Component | Overall | P0 | P1 | P2 | P3 | Total |
|---|-----------|---------|----|----|----|----|-------|
| 1 | tContextLoad | R | 4 | 14 | 19 | 6 | 43 |

**Category summary:** 1 Red, 0 Yellow, 0 Green. Total issues: 43.

### Custom Code Components (5)

| # | Component | Overall | P0 | P1 | P2 | P3 | Total |
|---|-----------|---------|----|----|----|----|-------|
| 1 | tJava | Y | 5 | 12 | 13 | 8 | 38 |
| 2 | tJavaRow | Y | 6 | 14 | 17 | 9 | 46 |
| 3 | PythonComponent | R | 4 | 10 | 11 | 3 | 28 |
| 4 | PythonRowComponent | R | 5 | 12 | 15 | 2 | 34 |
| 5 | PythonDataFrameComponent | Y | 3 | 9 | 11 | 2 | 25 |

**Category summary:** 2 Red, 3 Yellow, 0 Green. Total issues: 171.

---

## Key Findings

### 1. Cross-cutting base class crash (`_update_global_map()`) blocks ALL components at runtime when globalMap is present
Every component inherits from `BaseComponent`, which has a P0 bug in `_update_global_map()` that references an undefined variable. This single bug renders the entire engine unreliable when `global_map` is passed to any component.

### 2. Zero test coverage across the entire engine
All 54 components have Testing rated RED. There are effectively zero unit tests and zero integration tests for the v1 engine. No execution path in any component has been verified. This is the single largest risk factor for production deployment.

### 3. tXMLMap is the most broken component (58 issues, 6 P0)
The tXMLMap component has the highest total issue count. It has RED ratings across Converter, Engine, and Code Quality dimensions. The converter crashes at runtime due to an `lstrip` bug, and the engine only processes the first row of XML input.

### 4. tSchemaComplianceCheck is RED across all 5 dimensions
This is the only component with every dimension rated RED. Type validation is broken end-to-end, supporting only 4 of 12 Talend types. The `iterrows()` implementation is 100-1000x slower than vectorized alternatives.

### 5. Security vulnerabilities in code execution components
Multiple components use `exec()` or `eval()` without sandboxing: PythonComponent, PythonRowComponent, PythonDataFrameComponent, tFixedFlowInput, tFilterRow (advanced mode), and tSetGlobalVar. No `__builtins__` restriction is applied.

### 6. Converter crashes block 3 components entirely
PythonComponent, PythonRowComponent, and SwiftTransformer have converter-level crashes (P0) that prevent the component from being instantiated at all. These components cannot process any job until the converter is fixed. (tFileCopy and tFileRowCount converter crashes have been fixed.)

### 7. No REJECT flow implementation across the engine
Virtually no component implements the Talend REJECT output flow pattern. Error rows are silently dropped rather than being routed to error-handling paths. This is a fundamental behavioral gap compared to Talend.

### 8. `iterrows()` anti-pattern causes 100-1000x performance degradation
Multiple components (tNormalize, tSchemaComplianceCheck, tExtractDelimitedFields, tExtractXMLField, tExtractJSONFields, tExtractPositionalFields, PythonRowComponent) use the `iterrows()` anti-pattern instead of vectorized pandas operations. This causes catastrophic performance degradation on large datasets.

### 9. NaN/None handling is inconsistent and data-corrupting
Across the engine, there is no consistent strategy for handling NaN, None, and empty strings. Multiple components silently convert between these values, causing data corruption. The `fillna("")` pattern in several output components converts legitimate null values to empty strings.

### 10. Streaming mode is unreliable
The HYBRID streaming mode in the base class has bugs that cause incorrect results in ordering-sensitive components (e.g., tSortRow). Several components skip or lose data when streaming mode is active (tPivotToColumnsDelimited, tExtractDelimitedFields).

---

## Production Readiness Assessment

### Verdict: NOT PRODUCTION-READY

The v1 engine cannot be deployed to production in its current state. The assessment is based on three blocking factors:

1. **Systemic infrastructure bugs**: The cross-cutting `_update_global_map()` and `GlobalMap.get()` crashes affect every component. These must be fixed in the base class before any component can function reliably with globalMap.

2. **Zero test coverage**: No component has any meaningful test verification. Deploying untested code to production is unacceptable for an ETL engine where data integrity is paramount.

3. **221 P0 (Critical) issues**: There are 221 issues classified as P0 across 54 components, averaging 4.1 critical bugs per component. These include crashes, data corruption, and silent failures.

### Minimum Fix List for Production Viability

The following represents the absolute minimum set of fixes required before production deployment could be considered:

**Phase 1 -- Infrastructure (blocks everything else):**
- Fix `_update_global_map()` undefined variable crash in `BaseComponent`
- Fix `GlobalMap.get()` parameter signature
- Wire `_validate_config()` into `BaseComponent.execute()` lifecycle
- Establish unit test framework and add base class tests

**Phase 2 -- P0 Fixes (54 components, ~234 issues):**
- All P0 issues must be resolved. P0 issues include crashes, data corruption, and silent failures that make the engine unreliable.

**Phase 3 -- P1 Fixes for Core Components (~120 issues in top-20 components):**
- At minimum, the 20 most-used components must have their P1 issues resolved. P1 issues include missing Talend features and behavioral divergences that cause incorrect results.

**Phase 4 -- Test Coverage:**
- Every component must have at minimum: (a) unit tests for the happy path, (b) unit tests for error paths, (c) integration tests with the converter output format.

**Estimated effort**: The minimum fix list represents approximately 8-12 weeks of focused engineering effort for a team of 3-4 developers, assuming familiarity with both the Talend baseline and the v1 codebase.
