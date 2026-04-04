# Audit Report: tFileUnarchive / FileUnarchiveComponent

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report is scoped to the v1 engine exclusively

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileUnarchive` |
| **V1 Engine Class** | `FileUnarchiveComponent` |
| **Engine File** | `src/v1/engine/components/file/file_unarchive.py` (180 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_unarchive.py` (94 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileUnarchive")` decorator-based dispatch |
| **Registry Aliases** | `tFileUnarchive` |
| **Category** | File / Archive-Unarchive |
| **Complexity** | Medium -- 12 unique parameters, password/encryption support, encoding options |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_unarchive.py` | Engine implementation (180 lines) |
| `src/converters/talend_to_v1/components/file/file_unarchive.py` | Converter class (94 lines) |
| `tests/converters/talend_to_v1/components/test_file_unarchive.py` | Converter tests (41 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 12 unique + 2 framework params extracted; correct defaults (EXTRACTPATH=True); correct param names (CHECKPASSWORD, DECRYPT_METHOD); 3 advanced params added (PRINTOUT, USE_ENCODING, ENCORDING); `_build_component_dict` with type_name=FileUnarchiveComponent; 2 engine_gap needs_review |
| Engine Feature Parity | **Y** | 0 | 3 | 2 | 1 | ZIP-only (no tar/gz/tgz); config key mismatches (extract_path vs extractpath, check_password vs checkpassword); missing features (rootname, integrity, printout, use_encoding, encording, decrypt_method not consumed) |
| Code Quality | **Y** | 1 | 2 | 3 | 1 | Cross-cutting `_update_global_map()` crash (P0); dead `_validate_config()` (P1); zip slip vulnerability (P1); TOCTOU race in makedirs (P2); directory entries inflate file count (P2); no boolean conversion for extract_path (P2); unused typing import (P3) |
| Performance & Memory | **G** | 0 | 0 | 1 | 0 | Large archive extraction blocks event loop; no progress reporting |
| Testing | **Y** | 0 | 0 | 1 | 0 | 41 converter unit tests across 10 test classes per gold standard; integration + regression guard passing; engine unit tests missing (P2) |

**Overall: Yellow -- Converter fully standardized (Green); engine has config key mismatches and missing features documented via needs_review; engine/code quality gaps keep overall at Yellow**

**Top Actions:**
1. Fix `_update_global_map()` crash in base class (P0, cross-cutting)
2. Align engine config keys `extract_path`/`check_password` with converter `extractpath`/`checkpassword` (P1, engine gap)
3. Fix zip slip vulnerability in extraction path (P1, security)
4. Add engine unit tests for FileUnarchiveComponent (P2, testing gap)
5. Add support for tar/gz/tgz archive formats (P1, feature gap)

---

## 3. Talend Feature Baseline

### What tFileUnarchive Does

`tFileUnarchive` extracts compressed archive files for subsequent processing within Talend jobs. It decompresses archive files in the following formats: `*.tar.gz`, `*.tgz`, `*.tar`, `*.gz`, and `*.zip`. The component takes an archive file path as input, extracts its contents to a specified directory, and optionally preserves the internal directory structure. It supports password-protected archives using either Java Decrypt or Zip4j Decrypt methods.

The component is a utility component in the File/Archive-Unarchive family. It does not produce data rows -- instead, it performs file system operations and is typically chained via ITERATE connections to downstream file processing components. Advanced settings allow controlling output verbosity (PRINTOUT), character encoding for filenames (ENCORDING -- Talend's typo), and integrity checking before extraction.

**Source**: [tFileUnarchive Standard Properties (Talend 7.3)](https://help.qlik.com/talend/r/en-US/7.3/archive-unarchive/tfileunarchive-standard-properties), [tFileUnarchive Overview (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/archive-unarchive/tfileunarchive), [Talaxie GitHub _java.xml](https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tFileUnarchive/tFileUnarchive_java.xml)
**Component family**: File / Archive-Unarchive
**Available in**: All Talend products (Standard Job framework)
**Required JARs**: None for standard ZIP; Zip4j library required for Zip4j Decrypt mode

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Archive file | `ZIPFILE` | FILE | `""` | **Mandatory**. Absolute file path to the archive to be extracted. Supports context variables, globalMap references, Java expressions. |
| 2 | Extraction directory | `DIRECTORY` | DIRECTORY | `""` | **Mandatory**. Absolute folder path where the extracted file(s) will be placed. |
| 3 | Use archive name as root dir | `ROOTNAME` | CHECK | `false` | When checked, creates a folder named after the archive file (without extension) under the extraction directory. |
| 4 | Check integrity before unzip | `INTEGRITY` | CHECK | `false` | Validates archive integrity before extraction. Pre-extraction verification ensures the archive is not corrupted. |
| 5 | Extract file paths | `EXTRACTPATH` | CHECK | `true` | Reproduces the file path structure that was zipped in the archive. When unchecked, all files are extracted flat to the root of the extraction directory. **Note**: Default is `true` per _java.xml, not `false`. |
| 6 | Need a password | `CHECKPASSWORD` | CHECK | `false` | Enables password protection handling. When checked, displays the Decrypt method and Password fields. |
| 7 | Decrypt method | `DECRYPT_METHOD` | CLOSED_LIST | `ZIP4J_DECRYPT` | Selection between `ZIP4J_DECRYPT` and `JAVA_DECRYPT` methods. Only visible when CHECKPASSWORD is checked. |
| 8 | Password | `PASSWORD` | PASSWORD | `""` | Decryption password for protected archives. Only visible when CHECKPASSWORD is checked. |
| 9 | Die on error | `DIE_ON_ERROR` | CHECK | `false` | Stop the entire job on extraction error. When unchecked, errors are logged but the job continues. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 10 | Print out operations | `PRINTOUT` | CHECK | `false` | When checked, prints extraction operations to stdout. Useful for debugging. |
| 11 | Use custom encoding | `USE_ENCODING` | CHECK | `false` | When checked, enables custom character encoding for file names in the archive. |
| 12 | Encoding | `ENCORDING` | ENCODING_TYPE | `UTF-8` | Character encoding for file names. **Note**: The XML param name is `ENCORDING` -- this is Talend's typo (missing 'e' in "encoding"), preserved faithfully. Only visible when USE_ENCODING is checked. |
| 13 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Enables collection of processing metadata for tStatCatcher. |
| 14 | Label | `LABEL` | TEXT | `""` | Text label for the component on the designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `ITERATE` | Output | Row > Iterate | Enables iterative processing of extracted files. Each extracted file triggers one iteration. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Number of files extracted from the archive. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of files successfully extracted. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of files that failed extraction. |
| `{id}_CURRENT_FILE` | String | During ITERATE | Current file being extracted. |
| `{id}_CURRENT_FILEPATH` | String | During ITERATE | Full path of the current extracted file. |
| `{id}_ERROR_MESSAGE` | String | After error | Error message when extraction fails. |

### 3.5 Behavioral Notes

1. **EXTRACTPATH default is `true`** -- the old converter incorrectly used `false`. When EXTRACTPATH is true, the internal directory structure of the archive is preserved. When false, all files are flattened to the extraction root.
2. **CHECKPASSWORD** is the _java.xml param name for "Need a password" checkbox. Despite the name, it enables password handling, not integrity checking.
3. **ENCORDING** (not ENCODING) is Talend's typo in the _java.xml -- the misspelling is preserved faithfully in the converter config key.
4. **DECRYPT_METHOD** (not DECRYPT_TYPE) is the correct _java.xml param name. The old converter used `DECRYPT_TYPE` which is wrong.
5. **PRINTOUT**, **USE_ENCODING**, and **ENCORDING** are advanced settings that were missing from the old converter.
6. Password-protected archives require CHECKPASSWORD=true and a non-empty PASSWORD.
7. The component supports ZIP, tar.gz, tgz, tar, and gz formats in Talend, but the v1 engine only implements ZIP.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `@REGISTRY.register("tFileUnarchive")` decorator-based dispatch. All parameters are extracted via `_get_str()`, `_get_bool()` helpers from the base class. Config dict is wrapped using `_build_component_dict()` with `type_name="FileUnarchiveComponent"`.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `ZIPFILE` | Yes | `zipfile` | str, default `""` |
| 2 | `DIRECTORY` | Yes | `directory` | str, default `""` |
| 3 | `ROOTNAME` | Yes | `rootname` | bool, default `False` |
| 4 | `INTEGRITY` | Yes | `integrity` | bool, default `False` |
| 5 | `EXTRACTPATH` | Yes | `extractpath` | bool, default `True` (FIXED: was False) |
| 6 | `CHECKPASSWORD` | Yes | `checkpassword` | bool, default `False` (FIXED: was need_password) |
| 7 | `DECRYPT_METHOD` | Yes | `decrypt_method` | str, default `"ZIP4J_DECRYPT"` (FIXED: was decrypt_type) |
| 8 | `PASSWORD` | Yes | `password` | str, default `""` |
| 9 | `DIE_ON_ERROR` | Yes | `die_on_error` | bool, default `False` |
| 10 | `PRINTOUT` | Yes | `printout` | bool, default `False` (ADDED: was missing) |
| 11 | `USE_ENCODING` | Yes | `use_encoding` | bool, default `False` (ADDED: was missing) |
| 12 | `ENCORDING` | Yes | `encording` | str, default `"UTF-8"` (ADDED: Talend typo preserved) |
| 13 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, bool, default `False` |
| 14 | `LABEL` | Yes | `label` | Framework param, str, default `""` |

**Summary**: 14 of 14 parameters extracted (100%). All 12 unique + 2 framework params.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| N/A | N/A | Utility component -- no data flow schema. Schema is `{"input": [], "output": []}`. |

### 4.3 Expression Handling

String parameters (ZIPFILE, DIRECTORY, PASSWORD) pass through context variable and Java expression strings as-is. The v1 engine resolves them at runtime via `replace_in_config()`.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FUA-001 | ~~P1~~ | **FIXED** -- EXTRACTPATH default was `false`, corrected to `true` per _java.xml |
| CONV-FUA-002 | ~~P1~~ | **FIXED** -- Config key `need_password` renamed to `checkpassword` per _java.xml CHECKPASSWORD param |
| CONV-FUA-003 | ~~P1~~ | **FIXED** -- Config key `decrypt_type` renamed to `decrypt_method` per _java.xml DECRYPT_METHOD param |
| CONV-FUA-004 | ~~P1~~ | **FIXED** -- Added 3 missing advanced params: PRINTOUT, USE_ENCODING, ENCORDING |
| CONV-FUA-005 | ~~P2~~ | **FIXED** -- Config key `extract_path` renamed to `extractpath` per D-38 snake_case convention |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | `extractpath` | Engine reads `extract_path` but converter outputs `extractpath` per _java.xml param name EXTRACTPATH | engine_gap |
| 2 | `checkpassword` | Engine reads `check_password` but converter outputs `checkpassword` per _java.xml param name CHECKPASSWORD | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | ZIP extraction | **Yes** | High | `_process()` line 146 | Using Python `zipfile` module |
| 2 | tar/gz/tgz extraction | **No** | N/A | -- | Only ZIP supported; Talend supports tar, gz, tgz, tar.gz |
| 3 | Extract with paths (EXTRACTPATH) | **Yes** | High | `_process()` lines 153-162 | `extractall()` vs per-file `extract()` |
| 4 | Password protection | **Yes** | Medium | `_process()` lines 148-150 | Basic zipfile password only, no Zip4j AES support |
| 5 | Root dir (ROOTNAME) | **No** | N/A | -- | Not implemented; engine ignores rootname config |
| 6 | Integrity check (INTEGRITY) | **No** | N/A | -- | Not implemented; engine ignores integrity config |
| 7 | Die on error | **Yes** | High | `_process()` lines 124,176 | Re-raises or returns empty based on config |
| 8 | Output directory creation | **Yes** | High | `_process()` lines 139-140 | `os.makedirs()` |
| 9 | Print operations (PRINTOUT) | **No** | N/A | -- | Not implemented; engine ignores printout config |
| 10 | Custom encoding (USE_ENCODING/ENCORDING) | **No** | N/A | -- | Not implemented; engine ignores encoding config |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FUA-001 | **P1** | ZIP-only: engine does not support tar, gz, tgz, tar.gz formats |
| ENG-FUA-002 | **P1** | Config key mismatch: engine reads `extract_path`, converter outputs `extractpath` |
| ENG-FUA-003 | **P1** | Config key mismatch: engine reads `check_password`, converter outputs `checkpassword` |
| ENG-FUA-004 | **P2** | ROOTNAME not implemented -- engine does not create archive-named subdirectory |
| ENG-FUA-005 | **P2** | INTEGRITY not implemented -- engine does not validate archive integrity before extraction |
| ENG-FUA-006 | **P3** | PRINTOUT, USE_ENCODING, ENCORDING not consumed by engine (advanced features) |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Always 1 (represents one extraction op) |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | 1 if successful |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | 0 |
| `{id}_CURRENT_FILE` | Yes | No | -- | Missing: per-file tracking during ITERATE |
| `{id}_CURRENT_FILEPATH` | Yes | No | -- | Missing: per-file path tracking during ITERATE |
| `{id}_ERROR_MESSAGE` | Yes | No | -- | Missing: error message not stored in globalMap |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FUA-001 | **P0** | `base_component.py:304` | **CROSS-CUTTING**: `_update_global_map()` crash when globalMap is set -- affects ALL components |
| BUG-FUA-002 | **P1** | `file_unarchive.py:153-162` | Zip slip vulnerability: no path traversal check when extracting files with `extract_path=True` |
| BUG-FUA-003 | **P2** | `file_unarchive.py:139-140` | TOCTOU race: `os.path.exists()` check followed by `os.makedirs()` can race with concurrent processes |
| BUG-FUA-004 | **P2** | `file_unarchive.py:156` | Directory entries inflate file count: `len(archive.namelist())` counts directory entries as files |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FUA-001 | **P2** | Engine uses `check_password` but _java.xml param is `CHECKPASSWORD` (no underscore in compound) -- converter correctly outputs `checkpassword` |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FUA-001 | **P2** | "Logger should use % formatting" | Engine uses f-strings in logger calls (lines 115, 129, 130, etc.) |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

Zip slip vulnerability (BUG-FUA-002): When `extract_path=True`, the engine calls `archive.extractall()` which can write files outside the target directory if the archive contains entries with `../` path components. Mitigation: validate each entry's resolved path stays within the output directory before extraction.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Good -- `logging.getLogger(__name__)` at module level |
| Level usage | Good -- info for start/complete, debug for operations, error for failures |
| Sensitive data | **Warning** -- password appears in debug log if CHECKPASSWORD enabled (line 149: "Setting password for protected archive") |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `FileNotFoundError` and generic `Exception` |
| Exception chaining | No -- bare `raise` without `from` |
| die_on_error handling | Correct -- re-raises or returns empty based on config |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | Good -- all methods have return type hints |
| Parameter types | Good -- all parameters typed |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FUA-001 | **P2** | Large archive extraction blocks the event loop -- no async support or progress reporting |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | N/A -- file system operation, not data processing |
| Memory threshold | Good -- `zipfile.ZipFile` extracts file-by-file, no full-archive-in-memory |
| Large data handling | Acceptable -- disk I/O bound, not memory bound |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 41 | `tests/converters/talend_to_v1/components/test_file_unarchive.py` |
| Engine unit tests | 0 | None |
| Integration tests | Included | `tests/converters/talend_to_v1/test_integration.py` (regression guard) |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-FUA-001 | **P2** | No engine unit tests for FileUnarchiveComponent -- prevents Testing=Green per D-52 |

### 8.3 Recommended Test Cases

- Engine: basic ZIP extraction to temp directory
- Engine: password-protected ZIP extraction
- Engine: extract_path=True preserves directory structure
- Engine: extract_path=False flattens to root
- Engine: die_on_error=True raises on missing archive
- Engine: die_on_error=False returns empty on missing archive
- Engine: zip slip protection (archive with `../` entries)

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 1 | **BUG-FUA-001** |
| P1 | 2 | **ENG-FUA-001**, **BUG-FUA-002** |
| P2 | 7 | **ENG-FUA-004**, **ENG-FUA-005**, **BUG-FUA-003**, **BUG-FUA-004**, **NAME-FUA-001**, **STD-FUA-001**, **TEST-FUA-001** |
| P3 | 1 | **ENG-FUA-006** |
| **Total** | **11** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Converter (CONV) | 0 | All FIXED (CONV-FUA-001 through CONV-FUA-005) |
| Engine (ENG) | 4 | ENG-FUA-001, ENG-FUA-004, ENG-FUA-005, ENG-FUA-006 |
| Bug (BUG) | 3 | BUG-FUA-001, BUG-FUA-002, BUG-FUA-003, BUG-FUA-004 |
| Naming (NAME) | 1 | NAME-FUA-001 |
| Standards (STD) | 1 | STD-FUA-001 |
| Performance (PERF) | 1 | PERF-FUA-001 |
| Testing (TEST) | 1 | TEST-FUA-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap is set |

---

## 10. Recommendations

### Immediate (Before Production)

1. Fix `_update_global_map()` crash in base class (BUG-FUA-001, P0, cross-cutting)
2. Align engine config keys with converter output -- `extract_path` -> `extractpath`, `check_password` -> `checkpassword` (ENG-FUA-002, ENG-FUA-003, P1)
3. Fix zip slip vulnerability -- validate extracted file paths stay within output directory (BUG-FUA-002, P1)

### Short-term (Hardening)

4. Add tar/gz/tgz archive format support (ENG-FUA-001, P1)
5. Implement ROOTNAME (archive-named subdirectory) support (ENG-FUA-004, P2)
6. Implement INTEGRITY (pre-extraction validation) support (ENG-FUA-005, P2)
7. Add engine unit tests for FileUnarchiveComponent (TEST-FUA-001, P2)
8. Fix TOCTOU race in makedirs (BUG-FUA-003, P2)
9. Fix directory entry count inflation (BUG-FUA-004, P2)

### Long-term (Optimization)

10. Add PRINTOUT, USE_ENCODING, ENCORDING support (ENG-FUA-006, P3)

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Official Talend docs (7.3) | https://help.qlik.com/talend/r/en-US/7.3/archive-unarchive/tfileunarchive-standard-properties | Parameter definitions, defaults |
| Official Talend docs (8.0) | https://help.qlik.com/talend/en-US/components/8.0/archive-unarchive/tfileunarchive-standard-properties | Updated parameter definitions |
| Talaxie GitHub _java.xml | https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tFileUnarchive/tFileUnarchive_java.xml | Component definition XML -- source of truth |
| Engine source | `src/v1/engine/components/file/file_unarchive.py` | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/file/file_unarchive.py` | Converter audit |
| Test suite | `tests/converters/talend_to_v1/components/test_file_unarchive.py` | Test coverage analysis |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- affects stats reporting |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after v1.1 converter standardization (phase 10, plan 05)*
