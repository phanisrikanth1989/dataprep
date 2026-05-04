# V1 Engine Audit -- Summary Scorecard

## Overview

**Total components audited:** 86
**Total issues found:** 924
**Overall assessment:** NOT PRODUCTION-READY. The v1 engine has systemic quality gaps across all 86 components. Cross-cutting base class bugs affect every component. 33 components are rated RED (engine missing or broken), 50 are rated YELLOW (converter standardized, engine gaps remain), and 3 are rated GREEN (fully functional for their scope). All 81 applicable converters are now Green following Phases 6-13 converter standardization.

Note: Converter standardization (Phases 6-13) is complete. All 81 applicable converters are Green. All 5 Python/Swift audit-only components have Converter=N/A and Testing=N/A per D-82/D-88. The issues below describe engine-level gaps that are out of scope for the converter enhancement milestone.

### Important Note on Issue Counts

The raw count of 928 includes **cross-cutting issues that are counted in every component report**. The same underlying bug appears as a separate issue ID in each affected report (e.g., `BUG-FID-001`, `BUG-FOD-001`, `BUG-MAP-001` are all the same `_update_global_map()` crash). This is intentional -- each report is self-contained so developers working on a specific component see all issues relevant to them.

**Cross-cutting duplicates (~200-250 entries from ~15-20 unique bugs):**

| Cross-cutting Bug | Appears In | Unique Fix |
| --- | --- | --- |
| `_update_global_map()` crash (base_component.py:304) | All with-engine reports | 1 line fix |
| `GlobalMap.get()` broken signature (global_map.py:28) | All with-engine reports | 1 line fix |
| Zero unit tests | All with-engine reports | 1 systemic gap |
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
| --- | ----------- | --------- | ----------- | -------- | ------------- | ------------- | --------- | ---- | ---- | ---- | ---- | ------- |
| 1 | tFileInputDelimited | Y | G | Y | Y | G | Y | 2 | 7 | 10 | 2 | 21 |
| 2 | tFileOutputDelimited | Y | G | Y | Y | G | Y | 1 | 4 | 8 | 1 | 14 |
| 3 | tFileInputExcel | G | G | Y | Y | G | Y | 2 | 5 | 5 | 3 | 15 |
| 4 | tFileOutputExcel | Y | G | Y | Y | Y | Y | 3 | 8 | 11 | 3 | 25 |
| 5 | tFileInputJSON | Y | G | Y | Y | G | Y | 2 | 7 | 9 | 3 | 21 |
| 6 | tFileInputXML | Y | G | Y | Y | Y | Y | 1 | 5 | 7 | 3 | 16 |
| 7 | tFileInputPositional | Y | G | Y | Y | G | G | 1 | 6 | 2 | 4 | 13 |
| 8 | tFileOutputPositional | G | G | G | G | G | G | 1 | 0 | 0 | 2 | 3 |
| 9 | tFileInputFullRow | G | G | G | G | G | G | 0 | 0 | 0 | 0 | 0 |
| 10 | tFileInputRaw | Y | G | Y | Y | Y | Y | 1 | 5 | 6 | 2 | 14 |
| 11 | tFixedFlowInput | G | G | G | G | G | G | 0 | 0 | 1 | 2 | 3 |
| 12 | tFileArchive | G | G | G | G | G | G | 0 | 0 | 0 | 1 | 1 |
| 13 | tFileUnarchive | G | G | G | G | G | G | 0 | 0 | 0 | 1 | 1 |
| 14 | tFileCopy | G | G | G | G | G | G | 0 | 0 | 0 | 0 | 0 |
| 15 | tFileDelete | G | G | G | G | G | G | 0 | 0 | 0 | 1 | 1 |
| 16 | tFileExist | G | G | G | G | G | G | 0 | 0 | 0 | 0 | 0 |
| 17 | tFileProperties | Y | G | Y | Y | Y | Y | 1 | 4 | 7 | 0 | 12 |
| 18 | tFileInputProperties | R | G | R | R | N/A | R | 2 | 0 | 0 | 0 | 2 |
| 19 | tFileInputMSXML | R | G | R | R | N/A | R | 3 | 0 | 0 | 0 | 3 |
| 20 | tAdvancedFileOutputXML | R | G | R | R | N/A | R | 3 | 0 | 0 | 0 | 3 |
| 21 | tFileList | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 22 | tFileOutputEBCDIC | R | G | R | R | N/A | R | 3 | 0 | 0 | 0 | 3 |
| 23 | tFileRowCount | G | G | G | G | G | G | 0 | 0 | 0 | 3 | 3 |
| 24 | tFileTouch | G | G | G | G | G | G | 0 | 0 | 0 | 0 | 0 |
| 25 | tSetGlobalVar | G | G | G | G | G | G | 0 | 0 | 0 | 0 | 0 |
| 26 | tFilterRow | Y | G | Y | G | Y | Y | 1 | 4 | 6 | 2 | 13 |
| 27 | tFilterColumns | Y | G | G | G | N/A | Y | 0 | 0 | 10 | 1 | 11 |
| 28 | tSortRow | Y | G | Y | G | Y | Y | 0 | 6 | 8 | 1 | 15 |
| 29 | tMap | Y | G | Y | Y | Y | Y | 3 | 8 | 12 | 3 | 26 |
| 30 | tJoin | Y | G | Y | Y | G | Y | 2 | 9 | 8 | 2 | 21 |
| 31 | tNormalize | Y | G | Y | G | G | G | 0 | 1 | 2 | 1 | 4 |
| 32 | tDenormalize | G | G | G | G | G | G | 0 | 0 | 2 | 2 | 4 |
| 33 | tReplicate | Y | G | G | G | N/A | Y | 0 | 0 | 6 | 0 | 6 |
| 34 | tLogRow | G | G | G | G | G | G | 0 | 0 | 1 | 0 | 1 |
| 35 | tUnite | G | G | G | G | G | G | 0 | 0 | 0 | 1 | 1 |
| 36 | tExtractDelimitedFields | Y | G | Y | R | R | Y | 4 | 8 | 9 | 2 | 23 |
| 37 | tExtractJSONFields | Y | G | Y | R | Y | Y | 3 | 6 | 6 | 2 | 17 |
| 38 | tExtractXMLField | Y | G | Y | Y | Y | Y | 3 | 6 | 7 | 3 | 19 |
| 39 | tExtractPositionalFields | Y | G | Y | Y | Y | Y | 2 | 11 | 9 | 1 | 23 |
| 40 | tPivotToColumnsDelimited | Y | G | Y | G | Y | G | 0 | 1 | 4 | 1 | 6 |
| 41 | tUnpivotRow | G | G | G | G | G | G | 0 | 0 | 0 | 0 | 0 |
| 42 | tSchemaComplianceCheck | Y | G | R | G | N/A | Y | 2 | 5 | 4 | 1 | 12 |
| 43 | tXMLMap | R | G | R | Y | Y | Y | 3 | 12 | 3 | 3 | 21 |
| 44 | tAggregateSortedRow | G | G | G | G | G | G | 0 | 0 | 0 | 0 | 0 |
| 45 | tRowGenerator | G | G | G | G | G | G | 0 | 0 | 0 | 1 | 1 |
| 46 | tSampleRow | G | G | G | G | N/A | G | 0 | 0 | 0 | 0 | 0 |
| 47 | tSplitRow | G | G | G | G | N/A | G | 0 | 0 | 0 | 0 | 0 |
| 48 | tReplace | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 49 | tConvertType | G | G | G | G | G | G | 0 | 0 | 0 | 1 | 1 |
| 50 | tExtractRegexFields | R | G | R | R | N/A | R | 3 | 0 | 0 | 0 | 3 |
| 51 | tHashOutput | R | G | R | R | N/A | R | 3 | 0 | 0 | 0 | 3 |
| 52 | tChangeFileEncoding | G | G | G | G | N/A | G | 0 | 0 | 0 | 0 | 0 |
| 53 | tMemorizeRows | G | G | G | G | G | G | 0 | 0 | 0 | 1 | 1 |
| 54 | tParseRecordSet | G | G | G | G | G | G | 0 | 0 | 0 | 1 | 1 |
| 55 | tJava | Y | G | Y | G | Y | Y | 1 | 2 | 5 | 2 | 10 |
| 56 | tJavaRow | Y | G | Y | G | Y | Y | 3 | 7 | 7 | 3 | 20 |
| 57 | PythonComponent | R | N/A | Y | R | G | N/A | 2 | 7 | 8 | 2 | 19 |
| 58 | PythonRowComponent | Y | N/A | Y | Y | Y | N/A | 3 | 7 | 11 | 2 | 23 |
| 59 | PythonDataFrameComponent | Y | N/A | Y | Y | G | N/A | 2 | 8 | 8 | 2 | 20 |
| 60 | SwiftTransformer | Y | N/A | Y | Y | Y | N/A | 3 | 7 | 17 | 6 | 33 |
| 61 | SwiftBlockFormatter | Y | N/A | Y | Y | Y | N/A | 3 | 10 | 16 | 9 | 38 |
| 62 | tAggregateRow | Y | G | G | G | G | R | 1 | 0 | 3 | 1 | 5 |
| 63 | tUniqueRow | Y | G | Y | G | G | G | 0 | 2 | 1 | 1 | 4 |
| 64 | tDie | Y | G | Y | Y | G | G | 1 | 4 | 5 | 3 | 13 |
| 65 | tWarn | Y | G | Y | Y | G | G | 2 | 2 | 3 | 2 | 9 |
| 66 | tSleep | G | G | Y | Y | G | G | 2 | 2 | 4 | 1 | 9 |
| 67 | tSendMail | Y | G | Y | Y | G | R | 1 | 7 | 8 | 4 | 20 |
| 68 | tLoop | R | G | R | R | N/A | R | 3 | 0 | 0 | 0 | 3 |
| 69 | tParallelize | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 70 | tPostjob | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 71 | tPrejob | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 72 | tRunJob | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 73 | tMSSqlConnection | R | G | R | R | N/A | R | 3 | 0 | 0 | 0 | 3 |
| 74 | tMSSqlInput | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 75 | tOracleBulkExec | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 76 | tOracleClose | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 77 | tOracleCommit | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 78 | tOracleConnection | R | G | R | R | N/A | R | 2 | 0 | 0 | 0 | 2 |
| 79 | tOracleInput | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 80 | tOracleOutput | R | G | R | R | N/A | R | 2 | 0 | 0 | 0 | 2 |
| 81 | tOracleRollback | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 82 | tOracleRow | R | G | R | R | N/A | R | 3 | 0 | 0 | 0 | 3 |
| 83 | tOracleSP | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 84 | tContextLoad | Y | G | Y | Y | Y | G | 1 | 6 | 5 | 1 | 13 |
| 85 | tFlowToIterate | R | G | R | R | N/A | R | 1 | 0 | 0 | 0 | 1 |
| 86 | tForeach | Y | G | R | G | N/A | G | 1 | 0 | 0 | 0 | 1 |

---

## Rating Distribution

### Overall Component Ratings

| Rating | Count | Percentage |
| -------- | ------- | ------------ |
| **R** (Red -- blocks production) | 33 | 38.4% |
| **Y** (Yellow -- partial, gaps exist) | 50 | 58.1% |
| **G** (Green -- production-ready) | 3 | 3.5% |

### Per-Dimension Rating Distribution

| Dimension | Red | Yellow | Green | N/A |
| ----------- | ----- | -------- | ------- | ----- |
| Converter | 0 | 0 | 81 | 5 |
| Engine | 34 | 49 | 3 | 0 |
| Code Quality | 34 | 36 | 16 | 0 |
| Performance | 2 | 26 | 23 | 35 |
| Testing | 33 | 42 | 6 | 5 |

**Converter is universally Green or N/A**: All 81 converter-applicable components have Converter=G following Phases 6-13 standardization. 5 Python/Swift audit-only components have Converter=N/A.

**Testing has improved significantly**: 42 components now have Testing=Y (converter tests Green, engine tests missing) compared to the original audit where all 55 had Testing=R. 6 components have Testing=G (comprehensive converter + some engine test coverage). 5 audit-only components have Testing=N/A.

---

## Priority Distribution

| Priority | Total Issues | Percentage | Description |
| ---------- | ------------- | ------------ | ------------- |
| **P0** (Critical) | 146 | 15.7% | Blocks production use or causes data corruption/silent failures |
| **P1** (Major) | 280 | 30.2% | Significant functional gap or behavioral divergence from Talend |
| **P2** (Moderate) | 380 | 41.1% | Missing feature, code quality concern, or non-standard practice |
| **P3** (Low) | 118 | 12.7% | Minor improvement, cosmetic issue, or rarely-used feature gap |
| **Total** | **924** | -- | -- |

---

## Most Critical Components (Ranked by P0 Count)

| Rank | Component | P0 | P1 | P2 | P3 | Total | Overall |
| ------ | ----------- | ---- | ---- | ---- | ---- | ------- | --------- |
| 1 | tExtractDelimitedFields | 4 | 8 | 9 | 2 | 23 | Y |
| 2 | tPivotToColumnsDelimited | 4 | 5 | 9 | 2 | 20 | Y |
| 3 | SwiftBlockFormatter | 3 | 10 | 16 | 9 | 38 | Y |
| 4 | SwiftTransformer | 3 | 7 | 17 | 6 | 33 | Y |
| 5 | tFileOutputExcel | 3 | 8 | 11 | 3 | 25 | Y |
| 6 | tMap | 3 | 8 | 12 | 3 | 26 | Y |
| 7 | PythonRowComponent | 3 | 7 | 11 | 2 | 23 | Y |
| 8 | tXMLMap | 3 | 12 | 3 | 3 | 21 | R |
| 9 | tJavaRow | 3 | 7 | 7 | 3 | 20 | Y |
| 10 | tExtractXMLField | 3 | 6 | 7 | 3 | 19 | Y |

---

## Cross-Cutting Issues Summary

The following issues were identified in virtually every component report and represent systemic bugs in the v1 engine infrastructure rather than component-specific problems:

1. **`_update_global_map()` crash (P0)**: The base class method `_update_global_map()` references an undefined variable, causing an `UnboundLocalError` at runtime whenever `global_map` is provided. Affects all with-engine components.

2. **`GlobalMap.get()` broken signature (P0)**: The `GlobalMap.get()` method has an incorrect parameter signature that causes a crash when called with the expected arguments. Affects all components that interact with globalMap.

3. **`_validate_config()` dead code (P1)**: The `_validate_config()` method is defined in most components but is never called by the base class `execute()` method. Configuration validation is completely bypassed at runtime.

4. **Zero engine test coverage (P0)**: Not a single engine component has meaningful unit or integration tests. Only converter tests exist (added in Phases 6-13). The engine itself is unverified.

5. **No custom exception usage (P2)**: Components use generic Python exceptions instead of the custom exception classes defined in the codebase (e.g., `ConfigurationError`, `FileOperationError`).

6. **`print()` instead of logger (P2)**: Multiple components use `print()` statements for debugging/logging instead of the Python `logging` module, making production log management impossible.

7. **No REJECT flow (P1)**: The vast majority of components do not implement the Talend REJECT output flow pattern, meaning errored rows are silently dropped rather than routed to an error-handling path.

8. **`die_on_error` default mismatch (P1)**: Many components default `die_on_error` to `False`, whereas Talend defaults to `True`. This means the v1 engine silently swallows errors that Talend would surface.

See `CROSS_CUTTING_ISSUES.md` for the complete cross-cutting analysis.

---

## Component Categories

### File I/O Components (25)

| # | Component | Overall | P0 | P1 | P2 | P3 | Total |
| --- | ----------- | --------- | ---- | ---- | ---- | ---- | ------- |
| 1 | tFileInputDelimited | Y | 2 | 7 | 10 | 2 | 21 |
| 2 | tFileOutputDelimited | Y | 1 | 4 | 8 | 1 | 14 |
| 3 | tFileInputExcel | G | 2 | 5 | 5 | 3 | 15 |
| 4 | tFileOutputExcel | Y | 3 | 8 | 11 | 3 | 25 |
| 5 | tFileInputJSON | Y | 2 | 7 | 9 | 3 | 21 |
| 6 | tFileInputXML | Y | 1 | 5 | 7 | 3 | 16 |
| 7 | tFileInputPositional | Y | 1 | 6 | 2 | 4 | 13 |
| 8 | tFileOutputPositional | G | 1 | 0 | 0 | 2 | 3 |
| 9 | tFileInputFullRow | G | 0 | 0 | 0 | 0 | 0 |
| 10 | tFileInputRaw | Y | 1 | 5 | 6 | 2 | 14 |
| 11 | tFixedFlowInput | G | 0 | 0 | 1 | 2 | 3 |
| 12 | tFileArchive | G | 0 | 0 | 0 | 1 | 1 |
| 13 | tFileUnarchive | G | 0 | 0 | 0 | 1 | 1 |
| 14 | tFileCopy | G | 0 | 0 | 0 | 0 | 0 |
| 15 | tFileDelete | G | 0 | 0 | 0 | 1 | 1 |
| 16 | tFileExist | G | 0 | 0 | 0 | 0 | 0 |
| 17 | tFileProperties | Y | 1 | 4 | 7 | 0 | 12 |
| 18 | tFileRowCount | G | 0 | 0 | 0 | 3 | 3 |
| 19 | tFileTouch | G | 0 | 0 | 0 | 0 | 0 |
| 20 | tSetGlobalVar | G | 0 | 0 | 0 | 0 | 0 |
| 21 | tFileInputProperties | R | 2 | 0 | 0 | 0 | 2 |
| 22 | tFileInputMSXML | R | 3 | 0 | 0 | 0 | 3 |
| 23 | tAdvancedFileOutputXML | R | 3 | 0 | 0 | 0 | 3 |
| 24 | tFileList | R | 1 | 0 | 0 | 0 | 1 |
| 25 | tFileOutputEBCDIC | R | 3 | 0 | 0 | 0 | 3 |

**Category summary:** 5 Red, 10 Yellow, 10 Green. Total issues: 196.
**Note:** tFileOutputPositional ENGINE FINALISED (2026-06-14, Phase 7.2-02): Full engine rewrite per MANUAL_COMPONENT_AUTHORING.md. @REGISTRY.register("FileOutputPositional", "tFileOutputPositional") added (P0 ENG-FOP-001 fixed). DEFAULT_ENCODING='ISO-8859-15', DEFAULT_INCLUDE_HEADER=False (defaults fixed). KEEP ALL/LEFT/MIDDLE/RIGHT implemented with _KEEP_ALIAS. CENTER/CENTRE alignment via _ALIGN_ALIAS. BUG-FOP-003 (append+compress mode) fixed. Vectorized _format_columns() (no iterrows, no string +=, schema_map built once). _validate_config() raises ConfigurationError (structural only), _process() does content validation. Both flushonrow/flush_on_row aliases supported via explicit None checks. 44 engine unit tests across 13 test classes. Overall Y→G, Engine Y→G, Code Y→G, Perf Y→G, Testing Y→G. Issues reduced 17→3.
**Note:** tFileInputPositional ENGINE HARDENED (2026-06-14, Phase 7.2-02): @REGISTRY.register("FileInputPositional", "tFileInputPositional") added. DEFAULT_ENCODING='ISO-8859-15', DEFAULT_REMOVE_EMPTY_ROW=True (singular), DEFAULT_TRIM_ALL=True, DEFAULT_DIE_ON_ERROR=False (all corrected). _validate_config() now raises ConfigurationError (was returning List[str]). BUG-FIP-002 fixed: advanced_separator now only applied to columns whose schema type is in _NUMERIC_TYPES. BUG-FIP-004 fixed: remove_empty_row replaces '' with pd.NA before dropna so empty-string rows after trim are also dropped. 35 engine unit tests across 13 test classes. Testing Y→G. Issues reduced 21→13.
**Note:** tFileInputRaw Converter upgraded to Green (2026-04-03): Audit rewritten per gold standard. All 6 unique + 2 framework params extracted with _build_component_dict. ISO-8859-15 default. 2 per-feature needs_review entries (as_bytearray, as_inputstream engine gaps). 35 converter tests across 8 test classes. Code Quality upgraded R->Y, Testing upgraded R->Y (converter tests Green but engine tests missing).
**Note:** tFileProperties Converter upgraded to Green (2026-04-03): Audit rewritten per gold standard. All 2 unique + 2 framework params extracted with _build_component_dict. Config keys filename/md5 (snake_case per D-38). 2 per-feature needs_review entries (engine reads uppercase FILENAME/MD5). 28 converter tests across 9 test classes. Testing upgraded R->Y (converter tests Green but engine tests missing).
**Note:** tFileInputProperties NEW audit created (2026-04-03): No engine implementation (Red overall per D-37). Converter rewritten: 3 missing params added (FILE_FORMAT, RETRIVE_MODE, SECTION_NAME), encoding default fixed (UTF-8->ISO-8859-15), phantom DIE_ON_ERROR removed. 5 unique + 2 framework params, 35 converter tests across 9 test classes. Single consolidated needs_review. Converter=G, Engine=R, Code Quality=R, Testing=R.
**Note:** tFileExist upgraded to Green (2026-04-04): Audit rewritten per gold standard. 1 unique param (FILE_NAME) + 2 framework params extracted with _build_component_dict. 1 needs_review (file_name vs file_path engine key mismatch). 25 converter tests across 8 test classes. Testing upgraded R->Y (converter tests Green but engine tests missing).
**Note:** tFileList NEW audit created (2026-04-03): No engine implementation (Red overall per D-37). Converter rewritten: INCLUDSUBDIR spelling fixed (no E), ERROR default fixed (True->False), FORMAT_FILEPATH_TO_SLASH added, type_name fixed to tFileList. 15 unique + 2 framework params, 51 converter tests across 11 test classes. Single consolidated needs_review. Converter=G, Engine=R, Code Quality=R, Testing=R.
**Note:** tFileInputMSXML NEW audit created (2026-04-03): No engine implementation (Red overall per D-37). Converter rewritten: 4 missing params added (IGNORE_ORDER, CHECK_DATE, IGNORE_DTD, GENERATION_MODE), defaults fixed (trim_all=True, encoding=ISO-8859-15). SCHEMAS TABLE stride-3 parser (LOOP_PATH, MAPPING, CREATE_EMPTY_ROW). 10 unique + 2 framework params, 44 converter tests across 10 test classes. Single consolidated needs_review. Converter=G, Engine=R, Code Quality=R, Testing=R.
**Note:** tFileInputFullRow upgraded to all-Green (2026-04-04): Engine fully rewritten per MANUAL_COMPONENT_AUTHORING.md. All features implemented (header_rows, footer_rows, random, nb_random). All bugs fixed (unicode_escape, strip(), limit=0, column name, encoding default). Converter engine_gap needs_review entries removed. 42 engine tests added (all PASS). ENG-FIFR-004 (REJECT) confirmed N/A per Talaxie _java.xml.
**Note:** tFixedFlowInput ENGINE REWRITTEN (2026-05-01): @REGISTRY.register("FixedFlowInputComponent", "tFixedFlowInput") added. `_validate_config()` fixed to raise ConfigurationError (not dead list-return). NB_LINE bug fixed (`_update_stats(row_count,row_count,0)`). values_config list-of-dicts format handled. intable key fixed (was intable_data). Separator normalization complete (\n,\t,\r,\|). eval() replaced with safe `_coerce_numeric()`. 34 engine unit tests across 8 classes (100% pass). Converter needs_review reduced 3->1 (intable/rows gaps resolved). Overall Y->G, issues reduced 20->3 (P0=0, P1=0, P2=1, P3=2).
**Note:** tFileOutputExcel ENGINE FIXED (2026-05-03): `date_pattern` output formatting implemented via `_apply_date_patterns()` (mirrors FileOutputDelimited pattern). Decimal/float precision implemented via `_build_col_formats()` + openpyxl `cell.number_format`. Column ordering now uses `input_schema` when `output_schema` is empty (correct sink pattern). 45 engine unit tests added across 15 test classes (TestDatePatternFormatting, TestDecimalPrecision, TestInputSchemaColumnOrdering + 12 existing classes). ENG-FOE-013/014/015 fixed; TEST-FOE-001 closed. P1 reduced 10→8, P2 reduced 13→11, Total reduced 29→25.
**Note:** tFileInputExcel upgraded to Green (2026-04-03): Audit REWRITTEN per gold standard with Section 11 Risk Assessment + Appendix C (Generation Mode Comparison) + Appendix D (Sheet Processing). 3 critical defaults fixed (DIE_ON_ERROR=True->False, ENCODING=UTF-8->ISO-8859-15, GENERATION_MODE=EVENT_MODE->USER_MODE). AFFECT_EACH_SHEET type fixed bool->str. 3 module-level TABLE parsers. 28 unique + 2 framework params (100%). 9 per-feature needs_review entries. 83 converter tests across 11 test classes. Testing upgraded R->Y (converter tests Green but engine tests missing).
**Note:** tFileRowCount ENGINE REWRITTEN (2026-05-01): Full engine rewrite. @REGISTRY.register("FileRowCount", "tFileRowCount") added (dual alias). `_validate_config()` raises ConfigurationError for missing/empty filename. row_separator implemented via `_count_rows()` helper with `_ESCAPE_MAP` normalisation. Encoding default corrected to ISO-8859-15. FileOperationError properly chained. GlobalMap writes outside try block. Returns {"main": None} (correct for utility component). DIE_ON_ERROR confirmed phantom (not in `_java.xml`). 42 engine unit tests across 9 classes (100% pass). Overall Y->G, issues reduced 19->3 (P0=0, P1=0, P2=0, P3=3).
**Note:** tFileRowCount audit rewritten (2026-04-04): Audit REWRITTEN per gold standard. Phantom DIE_ON_ERROR removed (not in `_java.xml`). ENCODING default ISO-8859-15 per `_java.xml`. 4 unique + 2 framework params extracted with `_build_component_dict`. 1 per-feature needs_review (encoding default mismatch). 26 converter tests across 9 test classes. Testing upgraded R->Y (converter tests Green but engine tests missing). Total issues reduced 30->19.
**Note:** tFileDelete Converter upgraded to Green (2026-04-04): Audit REWRITTEN per gold standard. FAILON default fixed (False->True per `_java.xml`). Phantom params removed (FAIL_ON_ERROR->FAILON, FOLDER_FILE_PATH->PATH). 6 unique + 2 framework params (100%). 5 per-feature needs_review entries. 31 converter tests across 10 test classes. Testing upgraded R->Y (converter tests Green but engine tests missing). Issues reduced 29->10.
**Note:** tFileExist ENGINE FIXED (2026-04-29): Engine rewritten. `_validate_config()` raises ConfigurationError. `{id}_EXISTS` and `{id}_FILENAME` globalMap vars set. Accepts file_name/file_path/FILE_NAME aliases. @REGISTRY.register all three aliases. %-formatting in logger. 14 engine tests across 8 classes. Overall G, issues reduced 6->0.
**Note:** tFileCopy ENGINE FIXED (2026-04-29): Engine rewritten. All 5 missing features implemented (enable_copy_directory, source_derectory, remove_file, failon, force_copy_delete). Config key mismatches resolved (filename/destination_rename/preserve_last_modified_time). `_validate_config()` raises. FileOperationError used. 17 engine tests across 9 classes. Overall Y->G, issues reduced 12->0.
**Note:** tFileDelete ENGINE FIXED (2026-04-29): Engine rewritten. All 5 config key mismatches resolved (failon, folder, folder_file, filename/directory/path per mode). Talend-parity globalMap vars set (DELETE_PATH, CURRENT_STATUS, ERROR_MESSAGE). recursive default True (matches Talend implicit recursive). `_validate_config()` raises. 18 engine tests across 9 classes. Overall Y->G, issues reduced 10->1 (P3: symlink handling).
**Note:** tFileTouch ENGINE FIXED (2026-04-29): Engine rewritten. createdir key mismatch resolved (engine now reads createdir with create_directory fallback). `_validate_config()` raises. `{id}_ERROR_MESSAGE` set on failure. FileOperationError replaces bare exceptions. 13 engine tests across 8 classes. Overall Y->G, issues reduced 7->0.
**Note:** tFileOutputEBCDIC NEW audit created (2026-04-04): No engine implementation (Red overall per D-51). Enterprise-only component -- `_java.xml` NOT available in open-source Talaxie repository. LOW confidence params. Converter rewritten: class renamed FileOutputEBCDICConverter->FileOutputEbcdicConverter, TSTATCATCHER_STATS and LABEL framework params added, die_on_error default fixed (True->False), config key renamed row_separator->rowseparator. 5 unique + 2 framework params, 28 converter tests across 9 test classes. Single consolidated needs_review. Converter=G, Engine=R, Code Quality=R, Testing=R.
**Note:** tAdvancedFileOutputXML NEW audit created (2026-04-04): No engine implementation (Red overall per D-51). Converter massively rewritten from 6 to 33 params: ROOT/GROUP/LOOP TABLE stride-5 parsers. 33 unique + 2 framework params, 66 converter tests across 10 test classes. Single consolidated needs_review. Converter=G, Engine=R, Code Quality=R, Testing=R.
**Note:** tRowGenerator ENGINE REWRITTEN (2026-05-01): Full engine rewrite. @REGISTRY.register("RowGenerator", "tRowGenerator") added. _validate_config() raises ConfigurationError for missing/non-list values. nb_rows default fixed 1->100 (Talend parity). Schema reads from self.output_schema (top-level, not config-nested). _eval_expr() module function with restricted eval namespace + Java bridge path for {{java}} expressions. StringHandling.SPACE/LEN pre-processing. 24 print() statements replaced with logger. All 6 ENG-RG issues resolved. 52 engine unit tests across 9 classes (100% pass). Overall Y->G, issues reduced 8->1 (P3: Java routine library).
**Note:** tRowGenerator REWRITTEN (2026-04-04): Audit REWRITTEN per gold standard. Converter rewritten with _build_component_dict, SOURCE schema pattern (input=[], output=schema), VALUES TABLE stride-2 parser at module level. 2 unique + 2 framework params (100%). 2 per-feature needs_review (nb_rows default mismatch, schema config path mismatch). 20 converter tests across 8 test classes. Converter=G, Code Quality=G, Testing=Y (no engine tests per D-73). Overall upgraded R->Y. Issues reduced 32->8.
**Note:** tSetGlobalVar Converter upgraded to Green (2026-04-04): VARIABLES TABLE stride-2 (KEY/VALUE) parser. Engine key/shape mismatch documented. 23 converter tests across 9 test classes.
**Note:** tSetGlobalVar ENGINE FIXED (2026-05-01): Engine fully rewritten. @REGISTRY.register("SetGlobalVar", "tSetGlobalVar") added. _validate_config() raises ConfigurationError (was dead-code returning List). Reads `variables` (lowercase, {key,value}) with fallback to VARIABLES/name/VALUE shapes. die_on_error per-variable skip/raise. Java bridge heuristic removed (BaseComponent resolves {{java}} before _process). % logger formatting. pandas import removed. 26 engine tests across 8 classes (100% pass). Overall Y->G, issues reduced 9->0.

### Transform Components (36)

| # | Component | Overall | P0 | P1 | P2 | P3 | Total |
| --- | ----------- | --------- | ---- | ---- | ---- | ---- | ------- |
| 1 | tFilterRow | Y | 1 | 4 | 6 | 2 | 13 |
| 2 | tFilterColumns | Y | 0 | 0 | 10 | 1 | 11 |
| 3 | tSortRow | Y | 0 | 6 | 8 | 1 | 15 |
| 4 | tMap | Y | 3 | 8 | 12 | 3 | 26 |
| 5 | tJoin | Y | 2 | 9 | 8 | 2 | 21 |
| 6 | tNormalize | Y | 0 | 1 | 2 | 1 | 4 |
| 7 | tDenormalize | G | 0 | 0 | 2 | 2 | 4 |
| 8 | tReplicate | Y | 0 | 0 | 6 | 0 | 6 |
| 9 | tLogRow | G | 0 | 0 | 1 | 0 | 1 |
| 10 | tUnite | G | 0 | 0 | 0 | 1 | 1 |
| 11 | tExtractDelimitedFields | Y | 4 | 8 | 9 | 2 | 23 |
| 12 | tExtractJSONFields | Y | 3 | 6 | 6 | 2 | 17 |
| 13 | tExtractXMLField | Y | 3 | 6 | 7 | 3 | 19 |
| 14 | tExtractPositionalFields | Y | 2 | 11 | 9 | 1 | 23 |
| 15 | tPivotToColumnsDelimited | Y | 4 | 5 | 9 | 2 | 20 |
| 16 | tUnpivotRow | G | 0 | 0 | 0 | 0 | 0 |
| 17 | tSchemaComplianceCheck | Y | 2 | 5 | 4 | 1 | 12 |
| 18 | tXMLMap | R | 3 | 12 | 3 | 3 | 21 |
| 19 | tAggregateSortedRow | Y | 0 | 3 | 5 | 2 | 10 |
| 20 | tRowGenerator | G | 0 | 0 | 0 | 1 | 1 |
| 21 | tSampleRow | R | 3 | 0 | 0 | 0 | 3 |
| 22 | tSplitRow | R | 3 | 0 | 0 | 0 | 3 |
| 23 | tReplace | R | 1 | 0 | 0 | 0 | 1 |
| 24 | tConvertType | G | 0 | 0 | 0 | 1 | 1 |
| 25 | tExtractRegexFields | R | 3 | 0 | 0 | 0 | 3 |
| 26 | tHashOutput | R | 3 | 0 | 0 | 0 | 3 |
| 27 | tChangeFileEncoding | G | 0 | 0 | 0 | 0 | 0 |
| 28 | tMemorizeRows | G | 0 | 0 | 0 | 1 | 1 |
| 29 | tParseRecordSet | G | 0 | 0 | 0 | 1 | 1 |
| 30 | tJava | Y | 1 | 2 | 5 | 2 | 10 |
| 31 | tJavaRow | Y | 3 | 7 | 7 | 3 | 20 |
| 32 | PythonComponent | R | 2 | 7 | 8 | 2 | 19 |
| 33 | PythonRowComponent | Y | 3 | 7 | 11 | 2 | 23 |
| 34 | PythonDataFrameComponent | Y | 2 | 8 | 8 | 2 | 20 |
| 35 | SwiftTransformer | Y | 3 | 7 | 17 | 6 | 33 |
| 36 | SwiftBlockFormatter | Y | 3 | 10 | 16 | 9 | 38 |

**Category summary:** 11 Red, 25 Yellow, 0 Green. Total issues: 485.
**Note:** tUnite REWRITTEN (2026-04-04): Audit rewritten to gold standard. 0 unique params (SCHEMA only). Engine defaults compatible with Talend UNION ALL. 0 needs_review. Converter=G, Code Quality=G, Testing=Y, Overall=Y. Issues reduced 25->12.
**Note:** tUnite ENGINE FINALISED (2026-05-01): Engine rewritten to 71-line UNION-ALL-only implementation (MERGE/sort/dedup removed). 18 engine unit tests across 8 test classes. All P2 issues resolved. One P3 remains (PERF-UNI-001 pd.concat memory). Testing=G, Overall=G. Issues reduced 12->1.
**Note:** tDenormalize REWRITTEN (2026-04-04): Audit rewritten to gold standard. 2 phantom params removed (CONNECTION_FORMAT, NULL_AS_EMPTY). Stride-3 TABLE parser. 3 config keys (1 TABLE + 2 framework). 2 static + 1 conditional needs_review. 26 tests across 10 test classes. Converter=G, Code Quality=G, Testing=Y, Overall=Y. Issues reduced 28->9.
**Note:** tNormalize ENGINE HARDENED (2026-06-13): itemseparator key fix (ENG-NRM-001), Rule 12 violations removed from `_validate_config`, phantom die_on_error removed (ENG-NRM-004), discard_trailing_empty_str confirmed trailing-only (ENG-NRM-003). 25 engine unit tests added across 5 test classes. Performance=R→G (vectorized .str.split+.explode). Testing=Y→G. Issues reduced 10→4 (1 open P1: ENG-NRM-002 CSV escape/enclosure).
**Note:** tDenormalize ENGINE REWRITTEN (2026-06-13): @REGISTRY.register added (ENG-DNR-001 P0 fixed), merge flag implemented with first-seen dedup (ENG-DNR-002 P1 fixed), groupby(dropna=False) preserves null-key rows (ENG-DNR-003 P1 fixed). _validate_config returns None per Rule 12. No double validation. No manual _update_stats. 41 engine unit tests across 11 test classes. Engine=Y→G, Testing=Y→G, Overall=Y→G. Issues reduced 9→4.
**Note:** tUniqueRow Converter upgraded Y->G (2026-04-02): CASE_SENSITIVE extracted, change_hash_and_equals_for_bigdecimal extracted, tstatcatcher_stats and label added. 7 config keys, 25 tests, 2 conditional needs_review entries.
**Note:** tLogRow ENGINE REWRITTEN (2026-05-01): Engine fully rewritten per MANUAL_COMPONENT_AUTHORING.md. All 16 config keys implemented: basic/table/vertical modes, print_colnames, print_unique_name, use_fixed_length+lengths, TITLE_PRINT radio group. Default mismatches fixed (basic_mode=True, print_header=False). All output via logger.info(). @REGISTRY.register both names. Rule 12 compliant _validate_config(). 66 engine tests across 15 test classes. Overall Y→G, Engine Y→G, Testing Y→G. Issues reduced 9→1 (PERF-LR-001 iterrows, acceptable).
**Note:** tExtractJSONFields REWRITTEN (2026-04-04): Audit rewritten to gold standard with Section 11 Risk Assessment. Dual-TABLE parsing added. 15 config keys. 9 per-feature needs_review. 45 tests across 8 test classes. Converter=G, Testing=Y, Overall=Y. Issues reduced 39->17.
**Note:** tExtractXMLField REWRITTEN (2026-04-04): Audit rewritten to gold standard with Section 11 Risk Assessment. 6 hidden params added. MAPPING TABLE stride-2. 14 config keys. 7 per-feature needs_review. 50 tests across 10 test classes. Converter=G, Code Quality=Y, Testing=Y, Overall=Y. Issues reduced 45->19.
**Note:** tUnpivotRow REWRITTEN (2026-04-04): Full gold standard rewrite. Community component (MEDIUM confidence). 4 unique + 2 framework params (100%). 0 needs_review. 28 converter tests across 10 test classes. Converter=G, Code Quality=G, Testing=Y, Overall=Y. Issues reduced 45->14.
**Note:** tUnpivotRow ENGINE FINALISED (2026-05-02): Engine fully rewritten per MANUAL_COMPONENT_AUTHORING.md. @REGISTRY.register added. _validate_config() returns None, raises ConfigurationError (Rules 2,7,12). P0 schema pollution fixed (output = row_keys + pivot_key + pivot_value only). String coercion via null-safe .map(). die_on_error supported. reject key always returned. No input copy, no temp column, no redundant sort, no no-op filter. 29 engine unit tests across 5 test classes. Overall Y->G, Engine Y->G, Perf Y->G, Testing Y->G. Issues reduced 14->0.
**Note:** tAggregateSortedRow ENGINE FINALISED (2026-05-02): Engine fully rewritten per MANUAL_COMPONENT_AUTHORING.md. 413-line implementation replaced with ~240-line clean implementation. @REGISTRY.register("AggregateSortedRow", "tAggregateSortedRow") added. _validate_config() raises ConfigurationError (Rules 2,7,12). Delegates to _build_agg_func/_SUPPORTED_FUNCTIONS from aggregate_row.py (zero duplication). Config format aligned to converter output (groupbys as list-of-dicts). IGNORE_NULL wired per operation (ENG-ASR-001 fixed). Group-by column renaming supported (ENG-ASR-003 fixed). Single-pass pd.NamedAgg (PERF-ASR-002 fixed). Decimal precision for avg/mean (ENG-ASR-006 fixed). BUG-ASR-001 (empty group_bys ValueError) fixed. 43 engine unit tests across 6 test classes. Overall Y->G. Issues reduced 10->0.
**Note:** tExtractDelimitedFields REWRITTEN (2026-04-04): Audit rewritten to gold standard. SCHEMA_OPT_NUM added. Config key renamed fieldseparator per D-38. 13 config keys. 2 per-feature needs_review. 42 tests across 9 test classes. Testing upgraded R->Y. Overall R->Y. Issues reduced 39->23.
**Note:** tExtractPositionalFields Testing upgraded R->Y (2026-04-04): Gold-standard test rewrite with 49 tests across 10 test classes. Needs_review corrected from 8 to 6. Audit report rewritten with 10 sections + 2 appendices.
**Note:** tJoin REWRITTEN (2026-04-04): Audit REWRITTEN per gold standard with Section 11 Risk Assessment. Phantom CASE_SENSITIVE/DIE_ON_ERROR removed. USE_LOOKUP_COLS/LOOKUP_COLS TABLE added. 4 unique + 2 framework params (100%). 4 per-feature needs_review. 26 converter tests across 10 test classes. Testing upgraded R->Y. Issues reduced 36->21.
**Note:** tMap REWRITTEN (2026-04-04): Audit REWRITTEN per gold standard with Section 11 Risk Assessment + Appendix C MapperData XML reference. 9 unique + 2 framework params (100%). 9 per-feature needs_review entries. Multi-flow nodeData parsing preserved per D-74. 56 converter tests across 11 test classes. Testing upgraded R->Y. Issues reduced 44->26.
**Note:** tPivotToColumnsDelimited gold-standard rewrite (2026-04-04): Full converter+test+audit rewrite. D-38 config keys. 51 converter tests across 8 test classes. Audit rewritten with Section 11 Risk Assessment. Overall R->Y, Testing R->Y. 18 config keys, 7 needs_review.
**Note:** tSchemaComplianceCheck Converter upgraded R->G (2026-04-02): CHECK_ALL/ALL_EMPTY_ARE_NULL defaults fixed, CHECKCOLS TABLE stride-5 parser, 7 new params added. 15 config keys, 29 tests, 12 needs_review.
**Note:** tReplace NEW audit created (2026-04-04): No engine implementation (Red overall). WHOLE_WORD default fixed (False->True). ADVANCED_SUBST stride-4 TABLE parser added. 30 converter tests across 10 test classes.
**Note:** tExtractRegexFields NEW audit created (2026-04-04): No engine implementation (Red overall). Phantom GROUP removed, FIELD and CHECK_FIELDS_NUM added. 24 converter tests across 10 test classes.
**Note:** tChangeFileEncoding ENGINE FINALISED (2026-05-02): Engine implemented from scratch per MANUAL_COMPONENT_AUTHORING.md. Chunked file re-encoding with configurable buffer, source/target charset, create flag, and errors='replace' on both read and write sides. locale.getpreferredencoding() used when use_inencoding=False. @REGISTRY.register("ChangeFileEncoding", "tChangeFileEncoding"). _validate_config() raises ConfigurationError per Rules 2,7,12. buffersize coercion deferred to _process (Rule 12). Returns empty DataFrame + reject=None (file utility, no rows). type_name updated to "ChangeFileEncoding" (D-43 reversed). 29 engine unit tests across 6 test classes. Converter tests updated (needs_review cleared, type assertion updated). Overall R->G. Issues reduced 3->0.
**Note:** tMemorizeRows NEW audit created (2026-04-04): No engine implementation (Red overall). Phantom RESET_ON_CONDITION and CONDITION removed. SPECIFY_COLS TABLE parsing added. 34 converter tests across 10 test classes.
**Note:** tJava gold-standard rewrite (2026-04-04): Phantom DIE_ON_ERROR removed. 4 config keys, 20 tests in 10 classes, 1 needs_review. Converter=G, Code Quality=G, Testing=Y, Overall=Y.
**Note:** tJavaRow gold-standard rewrite (2026-04-04): Phantom DIE_ON_ERROR removed, output_schema as list. 5 config keys, 22 tests, 2 needs_review. Converter=G, Code Quality=G, Testing=Y, Overall=Y.
**Note:** PythonRowComponent audit rewrite (2026-04-04): Gold-standard audit per D-82 (audit-only). Sections 5+6 N/A. Converter=N/A, Testing=N/A, Overall=Y. 23 issues.
**Note:** PythonComponent audit rewrite (2026-04-04): Gold-standard audit per D-82 (audit-only). Sections 4-6 N/A. Converter=N/A, Testing=N/A, Overall=R. 19 issues (reduced 28->19).
**Note:** PythonDataFrameComponent audit rewrite (2026-04-04): Gold-standard audit per D-82 (audit-only). Sections 4+8 N/A. Converter=N/A, Testing=N/A, Overall=Y. 20 issues (reduced 25->20).
**Note:** SwiftTransformer REWRITTEN (2026-04-04): Audit-only gold standard rewrite with Section 11 Risk Assessment (11 risks). Converter=N/A, Testing=N/A per D-82/D-88. Overall=Y. 33 total issues.
**Note:** SwiftBlockFormatter REWRITTEN (2026-04-04): Audit REWRITTEN to gold standard per D-82 with Section 11 Risk Assessment. Engine-native custom SWIFT message parser. Converter=N/A, Testing=N/A per D-88. Overall=Y. 38 total issues.
**Note:** tHashOutput NEW audit created (2026-04-04): No engine implementation (Red overall). 8 unique params. 42 converter tests across 9 test classes.
**Note:** tParseRecordSet NEW audit created (2026-04-04): No engine implementation (Red overall). ATTRIBUTE_TABLE stride-1 VALUE parser. 30 converter tests across 10 test classes.
**Note:** tSampleRow NEW audit created (2026-04-04): No engine implementation (Red overall). RANGE default '1,5,10..20'. 19 converter tests across 9 test classes.
**Note:** tSplitRow NEW audit created (2026-04-04): No engine implementation (Red overall). COL_MAPPING stride-2 TABLE. 24 converter tests across 10 test classes.
**Note:** tConvertType NEW audit created (2026-04-04): No engine implementation (Red overall). 4 unique + 2 framework params. 24 converter tests.
**Note:** tAggregateSortedRow REWRITTEN (2026-04-04): Audit REWRITTEN per gold standard with Section 11 Risk Assessment. GROUPBYS stride-2, OPERATIONS stride-4 state-machine parser. 1 static + 2 conditional needs_review. 31 converter tests across 9 test classes. Converter=G, Code Quality=G, Testing=Y. Issues reduced 46->10.
**Note:** tFilterColumns audit rewritten (2026-04-04): Passthrough schema (input==output). 2 per-feature needs_review for engine-only keys. 23 converter tests across 7 test classes. Converter=G, Code Quality=G, Testing=Y. Issues reduced 31->11.

### Aggregate Components (2)

| # | Component | Overall | P0 | P1 | P2 | P3 | Total |
| --- | ----------- | --------- | ---- | ---- | ---- | ---- | ------- |
| 1 | tAggregateRow | Y | 1 | 0 | 3 | 1 | 5 |
| 2 | tUniqueRow | Y | 0 | 2 | 1 | 1 | 4 |

**Category summary:** 0 Red, 2 Yellow, 0 Green. Total issues: 21.
**Note:** tAggregateRow RE-AUDITED (2026-04-29): Engine fully rewritten since 2026-04-04 audit. All four P0/P1 functional bugs (ENG-AGG-001..004) RESOLVED. Single-pass `pd.NamedAgg` aggregation; output_column rename; per-op ignore_null; list returns delimited string; list_object/union/population_std_dev all implemented; USE_FINANCIAL_PRECISION wired through Decimal helpers in both grouped and global modes. Engine=G, Code Quality=G, Performance=G. Overall remains Y because Testing=R (zero engine unit tests -- only remaining production blocker). Issues reduced 18->5. Stale converter needs_review entries also removed.
**Note:** tUniqueRow RE-VERIFIED (2026-04-29): Engine unchanged since original audit; all findings still valid. Per-column case sensitivity, IS_VIRTUAL_COMPONENT, BigDecimal hash normalization, and ONLY_ONCE_EACH_DUPLICATED_KEY remain real engine gaps.
**Note:** tUniqueRow ENGINE HARDENED (2026-05-01): @REGISTRY.register added (4 aliases), execute() override removed (Rule 4 fix), _validate_config() contract fixed (returns None), key_columns parsing fixed (dict-list), per-column case sensitivity implemented, temp column collision fixed (__uniq_ci_ prefix), UNIQUE/DUPLICATE routing fixed (output_router.py updated). 35 engine tests across 8 test classes. Code Quality=Y->G, Perf=Y->G, Testing=G. 2 P1 remain (IS_VIRTUAL, BigDecimal). Issues reduced 16->4.

### Control Components (9)

| # | Component | Overall | P0 | P1 | P2 | P3 | Total |
| --- | ----------- | --------- | ---- | ---- | ---- | ---- | ------- |
| 1 | tDie | Y | 1 | 4 | 5 | 3 | 13 |
| 2 | tWarn | Y | 2 | 2 | 3 | 2 | 9 |
| 3 | tSleep | G | 2 | 2 | 4 | 1 | 9 |
| 4 | tSendMail | Y | 1 | 7 | 8 | 4 | 20 |
| 5 | tLoop | R | 3 | 0 | 0 | 0 | 3 |
| 6 | tParallelize | R | 1 | 0 | 0 | 0 | 1 |
| 7 | tPostjob | R | 1 | 0 | 0 | 0 | 1 |
| 8 | tPrejob | R | 1 | 0 | 0 | 0 | 1 |
| 9 | tRunJob | R | 1 | 0 | 0 | 0 | 1 |

**Category summary:** 5 Red, 3 Yellow, 1 Green. Total issues: 58.
**Note:** tWarn Converter upgraded Y->G (2026-04-02): MESSAGE default fixed, CODE default fixed, 2 missing params added. 5 config keys, 15 tests.
**Note:** tSleep Converter upgraded Y->G (2026-04-02): New converter with framework params. 3 config keys, 14 tests. No needs_review entries.
**Note:** tSendMail Converter upgraded Y->G (2026-04-02): 12 new params added, 3 TABLE parsers. 29 config keys, 42 tests, 11 needs_review.
**Note:** tLoop NEW audit created (2026-04-03): No engine implementation (Red overall). FORLOOP/WHILELOOP radio model. 11 config keys, converter tests across 9 test classes.
**Note:** tParallelize NEW audit created (2026-04-03): No engine implementation (Red overall). MEDIUM confidence params. 5 config keys, converter tests across 9 test classes.
**Note:** tPostjob NEW audit created (2026-04-03): No engine implementation (Red overall). Framework-only params. 2 config keys.
**Note:** tPrejob NEW audit created (2026-04-03): No engine implementation (Red overall). Framework-only params. 2 config keys.
**Note:** tRunJob NEW audit created (2026-04-03): No engine implementation (Red overall). 20 unique params including 2 TABLE params (CONTEXTPARAMS stride-2, JVM_ARGUMENTS stride-1). 22 config keys, converter tests across 9 test classes.

### Database Components (11)

| # | Component | Overall | P0 | P1 | P2 | P3 | Total |
| --- | ----------- | --------- | ---- | ---- | ---- | ---- | ------- |
| 1 | tMSSqlConnection | R | 3 | 0 | 0 | 0 | 3 |
| 2 | tMSSqlInput | R | 1 | 0 | 0 | 0 | 1 |
| 3 | tOracleBulkExec | R | 1 | 0 | 0 | 0 | 1 |
| 4 | tOracleClose | R | 1 | 0 | 0 | 0 | 1 |
| 5 | tOracleCommit | R | 1 | 0 | 0 | 0 | 1 |
| 6 | tOracleConnection | R | 2 | 0 | 0 | 0 | 2 |
| 7 | tOracleInput | R | 1 | 0 | 0 | 0 | 1 |
| 8 | tOracleOutput | R | 2 | 0 | 0 | 0 | 2 |
| 9 | tOracleRollback | R | 1 | 0 | 0 | 0 | 1 |
| 10 | tOracleRow | R | 3 | 0 | 0 | 0 | 3 |
| 11 | tOracleSP | R | 1 | 0 | 0 | 0 | 1 |

**Category summary:** 11 Red, 0 Yellow, 0 Green. Total issues: 17.
All database components are RED because no engine implementation exists. Converters are all Green -- they correctly extract all parameters from _java.xml for future engine support. Issue counts are low because the only open issues are P0 engine-missing entries.
**Note:** tMSSqlConnection NEW audit created (2026-04-03): 16 unique + 2 framework params extracted. Encrypted password handling. Port 1433 default.
**Note:** tMSSqlInput NEW audit created (2026-04-03): 20 params extracted. DB_SCHEMA->schema_db mapping. PROPERTIES non-empty default 'noDatetimeStringSync=true'.
**Note:** tOracleClose NEW audit created (2026-04-03): 1 unique param (CONNECTION) + 2 framework params. Simplest database component.
**Note:** tOracleCommit NEW audit created (2026-04-03): 2 unique params (CONNECTION, CLOSE). CLOSE default=True.
**Note:** tOracleRollback NEW audit created (2026-04-03): 2 unique params (CONNECTION, CLOSE). Phantom CONNECTION_FORMAT removed.
**Note:** tOracleConnection NEW audit created (2026-04-03): 28 unique params extracted. Dual registration (tOracleConnection + tDBConnection). SSL, TNS, RAC, shared connection support.
**Note:** tOracleInput NEW audit created (2026-04-03): 28 params extracted. CONVERT_XMLTYPE TABLE, TRIM_COLUMN TABLE, cursor params, NLS support.
**Note:** tOracleOutput NEW audit created (2026-04-03): 26 params extracted. All _java.xml params mapped to snake_case.
**Note:** tOracleRow NEW audit created (2026-04-03): 26 unique params extracted. Full connection, query, prepared statement, and datasource support.
**Note:** tOracleSP NEW audit created (2026-04-03): 23 unique params extracted. SP_ARGS stride-6 TABLE. IS_FUNCTION and RETURN support.
**Note:** tOracleBulkExec NEW audit created (2026-04-03): 38 unique params extracted (most of any database component). All SQL*Loader, NLS, and encoding params.

### Context Components (1)

| # | Component | Overall | P0 | P1 | P2 | P3 | Total |
| --- | ----------- | --------- | ---- | ---- | ---- | ---- | ------- |
| 1 | tContextLoad | Y | 1 | 6 | 5 | 1 | 13 |

**Category summary:** 0 Red, 1 Yellow, 0 Green. Total issues: 13.
**Note:** tContextLoad Converter upgraded Y->G (2026-04-02): 4 new params added (load_new_variable, not_load_old_variable, disable_error, disable_info), DISABLE_WARNINGS default fixed to True, DIEONERROR fallback, framework params. 14 config keys, 31 tests, 6 needs_review entries.

### Iterate Components (2)

| # | Component | Overall | P0 | P1 | P2 | P3 | Total |
| --- | ----------- | --------- | ---- | ---- | ---- | ---- | ------- |
| 1 | tFlowToIterate | R | 1 | 0 | 0 | 0 | 1 |
| 2 | tForeach | Y | 1 | 0 | 0 | 0 | 1 |

**Category summary:** 1 Red, 1 Yellow, 0 Green. Total issues: 2.
**Note:** tFlowToIterate NEW audit created (2026-04-03): No engine implementation (Red overall). 5 config keys extracted. DEFAULT_MAP and MAP (KEY/VALUE) TABLE parsed. 21 converter tests across 9 test classes.
**Note:** tForeach NEW audit created (2026-04-03): No engine implementation but Converter=G, Code Quality=G, Testing=G. VALUES TABLE parsed. 4 config keys. Overall=Y (engine missing keeps it from Green).

---

## Key Findings

### 1. Cross-cutting base class crash (`_update_global_map()`) blocks ALL with-engine components at runtime when globalMap is present

Every with-engine component inherits from `BaseComponent`, which has a P0 bug in `_update_global_map()` that references an undefined variable. This single bug renders the entire engine unreliable when `global_map` is passed to any component.

### 2. Zero engine test coverage across the entire engine

All with-engine components have zero engine unit tests. Only converter tests exist (added comprehensively in Phases 6-13). The engine itself is unverified. Testing=Y for most components reflects converter-test-only coverage.

### 3. All 81 converters are now Green following Phases 6-13 standardization

Every converter-applicable component has been rewritten to the gold standard pattern (CONVERTER_PATTERN.md) with comprehensive tests (TEST_PATTERN.md). All parameters are extracted from _java.xml source of truth. Engine gaps are documented as needs_review entries.

### 4. 33 components are RED due to missing engine implementations

All 11 database components, 5 control components (tLoop, tParallelize, tPostjob, tPrejob, tRunJob), 1 iterate component (tFlowToIterate), and 16 transform/file components have no engine implementation. Their converters are Green but they cannot execute.

### 5. Security vulnerabilities in code execution components

Multiple components use `exec()` or `eval()` without sandboxing: PythonComponent, PythonRowComponent, PythonDataFrameComponent, tFilterRow (advanced mode), and tSetGlobalVar. No `__builtins__` restriction is applied. (Note: tFixedFlowInput `eval()` was removed 2026-05-01.)

### 6. No REJECT flow implementation across the engine

Virtually no component implements the Talend REJECT output flow pattern. Error rows are silently dropped rather than being routed to error-handling paths. This is a fundamental behavioral gap compared to Talend.

### 7. `iterrows()` anti-pattern causes 100-1000x performance degradation

Multiple components (~~tNormalize -- FIXED 2026-06-13~~, tSchemaComplianceCheck, tExtractDelimitedFields, tExtractXMLField, tExtractJSONFields, tExtractPositionalFields, PythonRowComponent) use the `iterrows()` anti-pattern instead of vectorized pandas operations.

### 8. NaN/None handling is inconsistent and data-corrupting

Across the engine, there is no consistent strategy for handling NaN, None, and empty strings. Multiple components silently convert between these values, causing data corruption. The `fillna("")` pattern in several output components converts legitimate null values to empty strings.

### 9. Streaming mode is unreliable

The HYBRID streaming mode in the base class has bugs that cause incorrect results in ordering-sensitive components (e.g., tSortRow). Several components skip or lose data when streaming mode is active.

### 10. tXMLMap engine remains RED despite converter standardization (21 issues, 3 P0)

The tXMLMap converter is now GREEN (standardized in Phase 12). However, the engine still has critical issues: only first row processed (data loss), no lookup/join support, and cross-cutting base class bugs.

---

## Production Readiness Assessment

### Verdict: NOT PRODUCTION-READY

Note: Converter standardization (Phases 6-13) is complete. All 81 applicable converters are Green. The issues below describe engine-level gaps that are out of scope for this milestone.

The v1 engine cannot be deployed to production in its current state. The assessment is based on three blocking factors:

1. **Systemic infrastructure bugs**: The cross-cutting `_update_global_map()` and `GlobalMap.get()` crashes affect every with-engine component. These must be fixed in the base class before any component can function reliably with globalMap.

2. **Zero engine test coverage**: No engine component has any meaningful test verification. Converter tests are now comprehensive (added in Phases 6-13), but engine execution paths remain unverified. Deploying untested engine code to production is unacceptable for an ETL system where data integrity is paramount.

3. **146 P0 (Critical) issues**: There are 146 issues classified as P0 across 86 components. These include engine-missing entries for 33 components, crashes, data corruption, and silent failures.

### Minimum Fix List for Production Viability

The following represents the absolute minimum set of fixes required before production deployment could be considered:

**Phase 1 -- Infrastructure (blocks everything else):**

- Fix `_update_global_map()` undefined variable crash in `BaseComponent`
- Fix `GlobalMap.get()` parameter signature
- Wire `_validate_config()` into `BaseComponent.execute()` lifecycle
- Establish unit test framework and add base class tests

**Phase 2 -- P0 Fixes (86 components, ~146 issues):**

- All P0 issues must be resolved. P0 issues include engine-missing (33 components), crashes, data corruption, and silent failures.

**Phase 3 -- P1 Fixes for Core Components (~282 issues across all components):**

- At minimum, the 20 most-used components must have their P1 issues resolved. P1 issues include missing Talend features and behavioral divergences that cause incorrect results.

**Phase 4 -- Engine Test Coverage:**

- Every with-engine component must have at minimum: (a) unit tests for the happy path, (b) unit tests for error paths, (c) integration tests with the converter output format.

**Estimated effort**: The minimum fix list represents approximately 10-16 weeks of focused engineering effort for a team of 3-4 developers, assuming familiarity with both the Talend baseline and the v1 codebase. The 33 engine-missing components require new implementations.
