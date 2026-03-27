# Audit Report: tFileUnarchive / FileUnarchiveComponent

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW

> **Converter Update (2026-03-25)**: Converter section updated to reflect migration from `complex_converter` to `talend_to_v1`. All runtime params now extracted. See CONV-* issues below for status.

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFileUnarchive` |
| **V1 Engine Class** | `FileUnarchiveComponent` |
| **Engine File** | `src/v1/engine/components/file/file_unarchive.py` (181 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_unarchive.py` |
| **Converter Dispatch** | `talend_to_v1` registry-based dispatch via `REGISTRY["tFileUnarchive"]` |
| **Registry Aliases** | `FileUnarchiveComponent`, `tFileUnarchive` (registered in `src/v1/engine/engine.py` lines 70-71) |
| **Category** | File / Archive-Unarchive |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_unarchive.py` | Engine implementation (181 lines) |
| `src/converters/talend_to_v1/components/file/file_unarchive.py` | Dedicated `talend_to_v1` converter for tFileUnarchive |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports (line 16: `FileUnarchiveComponent`) |
| `src/v1/engine/components/file/file_archive.py` | Companion `FileArchiveComponent` for comparison |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | `talend_to_v1` dedicated parser extracts 11 params (11 config keys). All runtime params mapped. EXTRACTPATH default corrected to false. CHECKPASSWORD mapped to `integrity` (not `check_password`). NEED_PASSWORD mapped to `need_password`. USE_ARCHIVE_NAME mapped to `use_archive_name`. 3 engine-gap warnings documented. |
| Engine Feature Parity | **Y** | 0 | 5 | 2 | 1 | ZIP-only (no tar/gz/tgz); no CURRENT_FILE/CURRENT_FILEPATH globalMap; no archive name as root dir; no integrity check; `die_on_error` default mismatch |
| Code Quality | **Y** | 2 | 5 | 4 | 1 | Cross-cutting base class bugs; dead `_validate_config()`; zip slip vulnerability; symlink attack vector; TOCTOU race in makedirs; no `extract_path` boolean conversion; directory entries inflate file count |
| Performance & Memory | **G** | 0 | 0 | 1 | 0 | Large archive extraction blocks event loop; no progress reporting |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileUnarchive Does

`tFileUnarchive` extracts compressed archive files for subsequent processing within Talend jobs. It decompresses archive files in the following formats: `*.tar.gz`, `*.tgz`, `*.tar`, `*.gz`, and `*.zip`. The component takes an archive file path as input, extracts its contents to a specified directory, and optionally preserves the internal directory structure. It supports password-protected archives (using Java Decrypt or Zip4j Decrypt methods) and can use the archive file name as a root directory for extraction.

**Source**: [tFileUnarchive Standard Properties (Talend 7.3)](https://help.qlik.com/talend/r/en-US/7.3/archive-unarchive/tfileunarchive-standard-properties), [tFileUnarchive Overview (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/archive-unarchive/tfileunarchive), [tFileUnarchive Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/archive-unarchive/tfileunarchive-standard-properties)

**Component family**: Archive/Unarchive (File)
**Available in**: All Talend products (Standard Job framework)
**Required JARs**: None for standard ZIP; Zip4j library required for Zip4j Decrypt mode

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Archive file | `ZIPFILE` | Expression (String) | -- | **Mandatory**. Absolute file path to the archive to be extracted. Supports context variables, globalMap references, Java expressions. |
| 3 | Extraction directory | `DIRECTORY` | Expression (String) | -- | **Mandatory**. Absolute folder path where the extracted file(s) will be placed. Must use absolute paths to prevent errors. |
| 4 | Use archive file name as root directory | `USE_ARCHIVE_NAME` | Boolean (CHECK) | `false` | When checked, creates a folder named after the archive file (without extension) under the extraction directory. If the folder does not already exist, it is created automatically. For example, extracting `data.zip` to `/output` would create `/output/data/` and place files there. |
| 5 | Check the integrity before unzip | `CHECKPASSWORD` | Boolean (CHECK) | `false` | Validates archive integrity before extraction. Despite the XML parameter name `CHECKPASSWORD`, this is an integrity check, not a password check. Pre-extraction verification ensures the archive is not corrupted. |
| 6 | Extract file paths | `EXTRACTPATH` | Boolean (CHECK) | `false` | When checked, reproduces the file path structure that was zipped in the archive. Preserves the internal directory hierarchy during extraction. When unchecked, all files are extracted to the root of the extraction directory (flat extraction). |
| 7 | Need a password | `NEED_PASSWORD` | Boolean (CHECK) | `false` | Enables password protection handling. When checked, displays the Decrypt method and Password fields. |
| 8 | Decrypt method | `DECRYPT_TYPE` | Enum (Dropdown) | Java Decrypt | Selection between `Java Decrypt` and `Zip4j Decrypt` methods. Java Decrypt uses standard Java ZIP encryption. Zip4j Decrypt uses the Zip4j library for stronger AES encryption support. Only visible when "Need a password" is checked. |
| 9 | Password | `PASSWORD` | String (Password field) | -- | Decryption password for protected archives. Only visible when "Need a password" is checked. **Important**: Password-protected archives must originate from tFileArchive component for guaranteed compatibility. |
| 10 | Die on error | `DIE_ON_ERROR` | Boolean (CHECK) | `false` | Stop the entire job on extraction error. When unchecked, errors are logged but the job continues. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 11 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 12 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `ITERATE` | Output | Row > Iterate | Enables iterative processing of extracted files. Each extracted file triggers one iteration, making downstream components process each file individually. This is the primary output mechanism for tFileUnarchive. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Used for chaining subjobs. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. More granular than SUBJOB_OK. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. The target component only executes if the condition evaluates to true. |
| `ITERATE` | Input | Row > Iterate | Accepts iterate rows from upstream components (e.g., `tFileList`). Allows batch processing of multiple archives. |
| `SYNCHRONIZE` | Input (Trigger) | Trigger | Synchronization trigger for parallel execution control. |
| `PARALLELIZE` | Input (Trigger) | Trigger | Parallelization trigger for concurrent execution. |

**Note**: tFileUnarchive does NOT have a FLOW (Main) row output or a REJECT row output. It is a file-operation component, not a data-flow component. It communicates extracted file information via GlobalMap variables, not via row data.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_CURRENT_FILE` | String | During iteration (Flow) | Returns the current filename being extracted. Available during iterate link processing. Used to reference each extracted file in downstream components. |
| `{id}_CURRENT_FILEPATH` | String | During iteration (Flow) | Returns the full file path of the current file being extracted. Available during iterate link processing. This is the primary variable used by downstream components to access extracted files. |
| `{id}_NB_LINE` | Integer | After execution | Total number of extraction operations performed. For tFileUnarchive, this typically represents the number of files extracted from the archive. |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of successful extraction operations. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of failed extraction operations. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. Available for reference in downstream error handling flows. Only set when `DIE_ON_ERROR=false`. |

### 3.5 Behavioral Notes

1. **Supported archive formats**: Talend's tFileUnarchive supports five archive formats: `*.tar.gz`, `*.tgz`, `*.tar`, `*.gz`, and `*.zip`. The format is auto-detected from the file extension. This is significantly broader than the V1 engine which only supports ZIP.

2. **Password-protected archives**: Password-protected archives must originate from the tFileArchive component for guaranteed compatibility. Archives encrypted by third-party tools may fail or produce errors depending on the encryption method. Java Decrypt handles standard ZIP encryption. Zip4j Decrypt handles AES-256 encryption but requires the Zip4j library.

3. **USE_ARCHIVE_NAME behavior**: When enabled, the component strips the file extension from the archive name and creates a subdirectory with that name under the extraction directory. For example: extracting `/input/data.zip` to `/output/` creates `/output/data/` and extracts files into it. If the subdirectory already exists, files are extracted into the existing directory (potentially overwriting existing files with the same names).

4. **EXTRACTPATH behavior**: When `EXTRACTPATH=true`, the internal directory structure of the archive is preserved. When `EXTRACTPATH=false`, all files are extracted flat to the extraction directory, potentially causing name collisions if the archive contains files with the same name in different directories.

5. **ITERATE link behavior**: When tFileUnarchive is connected to a downstream component via an Iterate link, the component iterates over each extracted file. The `CURRENT_FILE` and `CURRENT_FILEPATH` variables are set for each iteration, allowing downstream components to process each extracted file individually. Without an Iterate link, the component simply extracts all files and completes.

6. **Integrity check**: The `CHECKPASSWORD` parameter (despite its misleading XML name) performs a pre-extraction integrity check on the archive. This validates that the archive is not corrupted before attempting extraction. If the integrity check fails, the component either throws an error (die_on_error=true) or logs a warning and continues (die_on_error=false).

7. **File overwrite**: Talend's tFileUnarchive silently overwrites existing files in the extraction directory if files with the same names already exist. There is no overwrite protection or confirmation mechanism.

8. **Large archives**: Community reports indicate that very large `tar.gz` files (multi-GB) may fail during extraction due to memory constraints. The Java-based extraction process reads the entire archive index into memory.

9. **Standalone vs. triggered**: tFileUnarchive can function as a standalone start component in a subjob, or it can be triggered by upstream components via iterate or trigger links. When used with tFileList as an upstream component, it can process multiple archives in sequence.

10. **ZIP path traversal (Zip Slip)**: Talend's Java-based extraction may be vulnerable to Zip Slip attacks if archives contain entries with `../` path components. This is a well-known vulnerability (CVE-2018-1263) in ZIP extraction libraries. The V1 engine shares this vulnerability.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The `talend_to_v1` converter uses a dedicated parser (`src/converters/talend_to_v1/components/file/file_unarchive.py`) registered via `REGISTRY["tFileUnarchive"]`. The parser extracts all runtime parameters using safe `_get_str` / `_get_bool` helpers with null-safety and correct defaults.

**Converter flow**:
1. `talend_to_v1` registry dispatches to `file_unarchive.py` converter function
2. Extracts all runtime parameters using `_get_str()` and `_get_bool()` helpers (null-safe)
3. EXTRACTPATH default corrected to `false` (matching Talend)
4. CHECKPASSWORD correctly mapped to `integrity` (check integrity, not password)
5. NEED_PASSWORD now extracted as `need_password`
6. USE_ARCHIVE_NAME now extracted as `use_archive_name`

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `ZIPFILE` | Yes | `zipfile` | Null-safe extraction. |
| 2 | `DIRECTORY` | Yes | `directory` | Null-safe extraction. |
| 3 | `EXTRACTPATH` | Yes | `extract_path` | Boolean. Default `false` -- matches Talend. |
| 4 | `CHECKPASSWORD` | Yes | `integrity` | Boolean. Renamed from `check_password` to `integrity` to match Talend semantics (integrity check, not password check). |
| 5 | `NEED_PASSWORD` | Yes | `need_password` | Boolean. Controls whether password fields are active. |
| 6 | `PASSWORD` | Yes | `password` | String. |
| 7 | `DIE_ON_ERROR` | Yes | `die_on_error` | Boolean. Default `false`. |
| 8 | `USE_ARCHIVE_NAME` | Yes | `use_archive_name` | Boolean. Engine-gap: not yet implemented in engine. |
| 9 | `DECRYPT_TYPE` | Yes | `decrypt_type` | Enum. Engine-gap: Zip4j Decrypt not yet implemented. |
| 10 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Not needed at runtime. |
| 11 | `LABEL` | Yes | `label` | Not needed at runtime (cosmetic). |

**Summary**: 11 of 11 parameters extracted (100%). All runtime-relevant parameters correctly mapped. 3 engine-gap warnings documented.

> **Factual correction (2026-03-25)**: The original audit mapped `CHECKPASSWORD` to `check_password` (implying password checking). Despite its misleading Talend XML name, `CHECKPASSWORD` actually controls integrity checking, not password handling. The `talend_to_v1` converter maps it to `integrity`. The actual password flag is `NEED_PASSWORD`, now mapped to `need_password`. The original audit also referenced `USE_ARCHIVE_NAME` as the config key -- the Talend XML name is `USE_ARCHIVE_NAME`, mapped to `use_archive_name` (not `ROOTNAME` as in some documentation).

### 4.2 Schema Extraction

Schema extraction is not applicable for tFileUnarchive. This component is a file-operation component and does not produce a data flow with a defined schema. It does not have FLOW or REJECT connectors.

### 4.3 Expression Handling

**Context variable handling**: The `parse_tfileunarchive()` method does NOT mark Java expressions in the `ZIPFILE` or `DIRECTORY` values. The generic `parse_base_component()` expression handling runs before the dedicated parser, so expressions in these fields may be handled by the base parser's generic expression scanning. However, because `parse_tfileunarchive()` overwrites `component['config']['zipfile']` and `component['config']['directory']` with raw XML values, any expression marking done by the base parser for these fields is lost.

**Java expression handling**: The `ZIPFILE` and `DIRECTORY` values are not passed through `mark_java_expression()`. If these fields contain Java expressions (e.g., `context.archive_dir + "/data.zip"`), they will not be prefixed with `{{java}}` and will not be resolved at runtime by the Java bridge. This is a significant gap for jobs where archive paths are constructed dynamically.

**Password expression handling**: The `PASSWORD` value is extracted as-is. If the password contains a Java expression or context variable reference, it will not be resolved. This is an uncommon scenario but represents a gap.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FUA-001 | ~~P1~~ | **FIXED (2026-03-25)**: `talend_to_v1` parser uses `_get_str()`/`_get_bool()` helpers with null-safety. No `AttributeError` risk. |
| CONV-FUA-002 | ~~P1~~ | **FIXED (2026-03-25)**: `EXTRACTPATH` now extracted as boolean with default `false`, matching Talend. |
| CONV-FUA-003 | ~~P2~~ | **FIXED (2026-03-25)**: `USE_ARCHIVE_NAME` now extracted as `use_archive_name`. Engine-gap: feature not yet implemented in engine. |
| CONV-FUA-004 | ~~P2~~ | **FIXED (2026-03-25)**: `DECRYPT_TYPE` now extracted as `decrypt_type`. Engine-gap: Zip4j Decrypt not yet implemented in engine. |
| CONV-FUA-005 | ~~P3~~ | **FIXED (2026-03-25)**: `talend_to_v1` parser uses safe extraction helpers. Expression handling delegated to base infrastructure. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Extract ZIP archives | **Yes** | High | `_process()` line 146 | Uses Python `zipfile.ZipFile` -- solid core implementation |
| 2 | Extract tar archives | **No** | N/A | -- | **Python `tarfile` module available but not implemented. Talend supports `*.tar`.** |
| 3 | Extract tar.gz / tgz archives | **No** | N/A | -- | **Python `tarfile` with `'r:gz'` mode available but not implemented. Talend supports `*.tar.gz` and `*.tgz`.** |
| 4 | Extract gz archives | **No** | N/A | -- | **Python `gzip` module available but not implemented. Talend supports `*.gz`.** |
| 5 | Extraction directory creation | **Yes** | High | `_process()` line 140 | `os.makedirs(output_directory)` creates directory if it doesn't exist |
| 6 | Extract with directory structure | **Yes** | Medium | `_process()` line 155 | `archive.extractall(output_directory)` preserves directory structure. But `extract_path=false` path (lines 159-162) still preserves structure due to `archive.extract(file, output_directory)` -- see BUG-FUA-003 |
| 7 | Flat extraction (no paths) | **No** | N/A | -- | **The `extract_path=false` branch (lines 159-162) uses `archive.extract(file, output_directory)` which still preserves directory structure. Should use `archive.read(file)` + manual write to flatten.** |
| 8 | Password-protected ZIP | **Yes** | Medium | `_process()` line 150 | Uses `archive.setpassword(password.encode())`. Works for standard ZIP encryption only. |
| 9 | Zip4j Decrypt (AES-256) | **No** | N/A | -- | **Zip4j library not available in Python. Standard `zipfile` module does not support AES. Would need `pyzipper` or similar third-party library.** |
| 10 | Use archive name as root dir | **No** | N/A | -- | **`USE_ARCHIVE_NAME` not implemented. No logic to create archive-named subdirectory.** |
| 11 | Integrity check before unzip | **No** | N/A | -- | **No pre-extraction integrity validation. Python's `zipfile` detects corruption during extraction but not before.** |
| 12 | Die on error | **Yes** | High | `_process()` lines 130-135, 176-180 | Re-raises or returns empty DF based on `die_on_error` flag |
| 13 | File existence check | **Yes** | High | `_process()` line 127 | `os.path.exists(zipfile_path)` before extraction |
| 14 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` |
| 15 | Java expression support | **Partial** | Low | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers, but converter does not mark ZIPFILE/DIRECTORY expressions |
| 16 | Statistics tracking | **Yes** | Medium | `_process()` lines 134, 165, 173 | NB_LINE always 1 (one extraction operation). Does not track per-file counts. |
| 17 | `{id}_CURRENT_FILE` globalMap | **No** | N/A | -- | **Not implemented. Critical for iterate-link workflows.** |
| 18 | `{id}_CURRENT_FILEPATH` globalMap | **No** | N/A | -- | **Not implemented. Critical for iterate-link workflows.** |
| 19 | `{id}_ERROR_MESSAGE` globalMap | **No** | N/A | -- | **Not implemented. Error details not available downstream.** |
| 20 | Iterate output | **No** | N/A | -- | **No iterate output mechanism. Component extracts all files at once and returns empty DataFrame. No per-file iteration.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FUA-001 | **P1** | **ZIP-only support**: Talend supports five archive formats (`*.zip`, `*.tar`, `*.tar.gz`, `*.tgz`, `*.gz`), but the V1 engine only supports ZIP via Python's `zipfile` module. Any job processing tar, tar.gz, tgz, or gz archives will fail with `zipfile.BadZipFile` error. Python provides native support for all these formats via the `tarfile` and `gzip` standard library modules. This is a significant coverage gap since tar.gz is extremely common in Unix/Linux data pipelines. |
| ENG-FUA-002 | **P1** | **No `{id}_CURRENT_FILE` and `{id}_CURRENT_FILEPATH` globalMap variables**: These are flow-scope variables set during iterate-link processing. They are the primary mechanism for downstream components to access extracted files. Without them, tFileUnarchive connected via an Iterate link to a downstream component (e.g., tFileInputDelimited) cannot communicate which file to process. This makes the component non-functional in the most common Talend usage pattern: `tFileUnarchive -> (iterate) -> tFileInputDelimited`. |
| ENG-FUA-003 | **P1** | **No iterate output mechanism**: The component extracts all files at once and returns an empty DataFrame. There is no iteration over extracted files, no yielding of per-file results, and no integration with the engine's iterate link handling. In Talend, tFileUnarchive iterates over each extracted file, setting CURRENT_FILE/CURRENT_FILEPATH for each iteration. The V1 engine would need to implement `BaseIterateComponent` or similar to support this. |
| ENG-FUA-004 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur with `die_on_error=false`, the error message is not stored in globalMap for downstream reference. Error details are only logged, not propagated. |
| ENG-FUA-005 | **P2** | **No `USE_ARCHIVE_NAME` support**: Jobs relying on archive-named subdirectories will have incorrect extraction paths. Files will be placed directly in the extraction directory instead of under an archive-named subdirectory. |
| ENG-FUA-006 | **P2** | **No integrity check**: No pre-extraction validation of archive integrity. Corrupted archives will fail during extraction rather than being caught early. Python's `zipfile.ZipFile.testzip()` method could be used for this. |
| ENG-FUA-007 | **P3** | **NB_LINE always 1**: Statistics track one extraction operation rather than the number of files extracted. Talend's NB_LINE for this component represents the number of files processed. The V1 engine could use `len(archive.namelist())` for a more accurate count, which it already calculates as `files_extracted` but does not propagate to stats. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Always 1 (one extraction operation). Talend tracks per-file counts. |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | 1 if success, 0 if failure |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | Same mechanism | Always 0 or 1 on failure. Not file-granular. |
| `{id}_CURRENT_FILE` | Yes (Flow) | **No** | -- | **Not implemented. Critical for iterate workflows.** |
| `{id}_CURRENT_FILEPATH` | Yes (Flow) | **No** | -- | **Not implemented. Critical for iterate workflows.** |
| `{id}_ERROR_MESSAGE` | Yes (After) | **No** | -- | **Not implemented.** |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FUA-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileUnarchiveComponent, since `_update_global_map()` is called after every component execution (via `execute()` line 218). The entire v1 engine is non-functional when a global map is configured. |
| BUG-FUA-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FUA-003 | **P1** | `src/v1/engine/components/file/file_unarchive.py:159-162` | **Flat extraction (extract_path=false) still preserves directory structure**: The `else` branch for `extract_path=false` uses `archive.extract(file, output_directory)` which preserves the file's relative path within the archive, creating subdirectories. For true flat extraction, the code should read the file content with `archive.read(file)` and write it to the output directory using only the filename (not the full path). Example: `data/subdir/file.txt` in the archive should be extracted as `output_directory/file.txt`, not `output_directory/data/subdir/file.txt`. Currently both branches produce identical behavior. |
| BUG-FUA-004 | **P1** | `src/v1/engine/components/file/file_unarchive.py:148-149` | **Password only set when BOTH `check_password` AND `password` are truthy**: Line 148 checks `if check_password and password:`. Due to CONV-FUA-002, the `check_password` config maps to the Talend `CHECKPASSWORD` parameter (integrity check), not `NEED_PASSWORD` (actual password flag). This means the password is only applied when integrity check is enabled, which is not the correct semantic. Furthermore, if `NEED_PASSWORD=true` but `CHECKPASSWORD=false`, the password will never be set on the archive. |
| BUG-FUA-005 | **P1** | `src/v1/engine/components/file/file_unarchive.py:65-98` | **`_validate_config()` is never called**: The method exists and contains validation logic (checking `zipfile`, `directory`, `check_password`, `extract_path` types), but it is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Invalid configurations (missing zipfile, wrong types) are not caught until they cause runtime errors. |
| BUG-FUA-006 | **P2** | `src/v1/engine/components/file/file_unarchive.py:150` | **Password encoding assumes UTF-8**: `password.encode()` defaults to UTF-8 encoding. If the password contains non-ASCII characters and was originally encoded differently (e.g., the archive was created on a system using Latin-1), the password comparison will fail silently. Talend's Java-based implementation uses the platform default charset, which may differ from UTF-8 on Windows systems. |
| BUG-FUA-007 | **P2** | `src/v1/engine/components/file/file_unarchive.py:155` | **`extractall()` is vulnerable to Zip Slip attack (path traversal)**: `archive.extractall(output_directory)` does not validate that extracted file paths stay within the output directory. A malicious ZIP file containing entries like `../../../etc/cron.d/malicious` could write files outside the intended extraction directory. This is a well-known vulnerability (CVE-2018-1263, "Zip Slip"). Python's `zipfile` module does not provide built-in path traversal protection (note: the `filter` parameter added in Python 3.12 via PEP 706 applies to `tarfile.extractall()`, NOT `zipfile.extractall()`). The fix is to manually validate each entry's resolved path before extraction: `if not os.path.realpath(target_path).startswith(os.path.realpath(output_directory)):`. **Note**: This is also a concern in Talend's Java implementation, but it is particularly important for a Python implementation processing potentially untrusted archives. |
| BUG-FUA-008 | **P2** | `src/v1/engine/components/file/file_unarchive.py:134` | **Inconsistent stats on missing file with die_on_error=false**: When the archive file does not exist and `die_on_error=false`, the code calls `self._update_stats(1, 0, 1)` (line 134), setting `NB_LINE=1, NB_LINE_OK=0, NB_LINE_REJECT=1`. Then in the generic exception handler (line 173), if the FileNotFoundError propagates, `_update_stats(1, 0, 1)` is called AGAIN, doubling the stats to `NB_LINE=2, NB_LINE_OK=0, NB_LINE_REJECT=2`. However, since the code returns on line 135 before the exception handler, this specific double-counting only occurs for other exceptions. The explicit return prevents the issue for FileNotFoundError, but the pattern is fragile. |
| BUG-FUA-009 | **P1** | `src/v1/engine/engine.py:63` | **`die_on_error` default `True` contradicts Talend default `false`**: The engine defaults `die_on_error` to `True`, but Talend's default for `DIE_ON_ERROR` is `false`. Jobs that rely on Talend's default continue-on-error behavior will get unexpected fail-fast semantics instead, causing jobs to abort on the first error rather than logging and continuing. This is a silent behavioral divergence that changes job control flow. |
| BUG-FUA-010 | **P1** | `src/v1/engine/components/file/file_unarchive.py:138-140` | **`os.makedirs()` TOCTOU race condition**: The code checks `os.path.exists(output_directory)` then calls `os.makedirs(output_directory)`. Between the existence check and the creation call, another process or thread could create or remove the directory, causing either a `FileExistsError` or unexpected failure. Fix: replace with `os.makedirs(output_directory, exist_ok=True)` which atomically handles the exists-or-create logic. |
| BUG-FUA-011 | **P2** | `src/v1/engine/components/file/file_unarchive.py:155-162` | **`files_extracted` count includes directory entries from `namelist()`**: Both the `extract_path=true` branch (line 156: `len(archive.namelist())`) and the `extract_path=false` branch count directory entries (paths ending with `/`) as extracted files, inflating the reported count. Should filter to non-directory entries: `[f for f in archive.namelist() if not f.endswith('/')]`. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FUA-001 | **P3** | **Config key `zipfile` shadows Python's `zipfile` module**: The config parameter name `zipfile` (line 119: `zipfile_path = self.config.get('zipfile')`) collides with the imported `zipfile` module (line 8: `import zipfile`). The local variable `zipfile_path` avoids the collision, but if someone writes `self.config['zipfile']` in a context where the module name is expected, it creates confusion. Consider renaming to `archive_file` or `archive_path` to match the Talend parameter label "Archive file". |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FUA-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-FUA-002 | **P2** | "GlobalMap variables must match Talend patterns" | `CURRENT_FILE` and `CURRENT_FILEPATH` not set. These are the primary output mechanism for tFileUnarchive in Talend. |
| STD-FUA-003 | **P2** | "Component status must be updated" | The component relies entirely on `BaseComponent.execute()` for status updates. If `_process()` returns without error but the extraction produced warnings, the status is always SUCCESS with no nuance. |

### 6.4 Debug Artifacts

No debug artifacts or `print()` statements found. The code is clean in this regard.

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FUA-001 | **P1** | **Zip Slip vulnerability (path traversal)**: `archive.extractall(output_directory)` on line 155 and `archive.extract(file, output_directory)` on line 160 do not validate that extracted paths stay within the output directory. A crafted ZIP file could overwrite arbitrary files on the system. See BUG-FUA-007 for detailed analysis and fix. Note: Python's `zipfile` module has no built-in path traversal protection (the `filter` parameter added in Python 3.12 via PEP 706 applies to `tarfile.extractall()`, NOT `zipfile.extractall()`). Manual path validation is required. |
| SEC-FUA-002 | **P1** | **Symlink attack vector in ZIP extraction (lines 155, 160)**: Distinct from Zip Slip (path traversal). A malicious ZIP can contain symlink entries that point to sensitive locations (e.g., `/etc/shadow`). Subsequent entries in the archive write through the symlink, overwriting the target file. Python's `zipfile.extractall()` creates symlinks if the ZIP entry has Unix permissions set in `external_attr`. This is a separate attack vector from path traversal and requires its own mitigation: check for symlink entries before extraction and either skip them or validate their targets. |
| SEC-FUA-003 | **P2** | **Password logged in debug output**: Line 149 logs `"Setting password for protected archive"` which is safe, but if the overall config is logged elsewhere (e.g., by the engine's component registration), the plaintext password in `self.config['password']` may appear in logs. The password should be masked in any config dump. |
| SEC-FUA-004 | **P2** | **No path traversal protection on input paths**: `zipfile_path` and `output_directory` from config are used directly with `os.path.exists()` and `zipfile.ZipFile()`. If config comes from untrusted sources, path traversal (`../../etc/passwd`) on the archive path could read arbitrary files. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |

### 6.6 Logging Quality

The component has good logging throughout, following STANDARDS.md patterns:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones (lines 115, 166), DEBUG for details (lines 139, 144, 149, 154, 158, 162), ERROR for failures (lines 129, 172) -- correct |
| Start/complete logging | `_process()` logs start (line 115) and completion with file count (line 166-167) -- correct |
| Sensitive data | Password value not logged (only "Setting password for protected archive" message) -- correct |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses built-in `FileNotFoundError` (line 131). Does NOT use `FileOperationError` from `exceptions.py`. Inconsistent with the exception hierarchy. |
| Exception handling | Generic `except Exception as e` on line 171 catches all exceptions. Acceptable for a file operation component. |
| `die_on_error` handling | Two code paths: explicit FileNotFoundError (lines 130-135) and generic catch-all (lines 171-180). Both respect `die_on_error`. |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID and error details -- correct |
| Graceful degradation | Returns empty DataFrame when `die_on_error=false` -- correct |
| Missing: `zipfile.BadZipFile` handling | No specific handling for corrupt ZIP files. The generic `except Exception` catches it, but a specific handler could provide a better error message. |
| Missing: `RuntimeError` for password issues | Docstring mentions `RuntimeError` for missing passwords (line 113), but no code raises it. Password issues manifest as `RuntimeError` from the `zipfile` module itself. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_validate_config() -> List[str]`, `_process(...) -> Dict[str, Any]` -- correct |
| Parameter types | `input_data: Optional[pd.DataFrame] = None` -- correct |
| Return types | `Dict[str, Any]` return type annotated -- correct |
| Class constants | Typed via assignment (`DEFAULT_EXTRACT_PATH = True`) -- no explicit type annotations but types are clear from values |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FUA-001 | **P2** | **Large archive extraction blocks execution**: `archive.extractall()` on line 155 processes the entire archive synchronously. For multi-GB archives with thousands of files, this blocks the engine's execution thread for the duration of the extraction. There is no progress reporting, no chunked extraction, and no way to cancel the operation mid-extraction. For very large archives, this could cause the engine to appear unresponsive. Consider adding periodic logging of extraction progress (e.g., every 100 files). |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Archive reading | `zipfile.ZipFile` reads the central directory into memory but streams individual file extraction. Memory-efficient for archives with many small files. |
| Large file extraction | Individual large files within the archive are streamed to disk by `extractall()`. Not a memory concern. |
| Directory creation | `os.makedirs()` is a lightweight OS call. No memory concern. |
| Return value | Returns `pd.DataFrame()` (empty). Minimal memory overhead. |

### 7.2 Scalability Considerations

| Issue | Description |
|-------|-------------|
| Archive with millions of files | `archive.namelist()` on line 156 loads all file names into memory. For archives with millions of entries, this could consume significant memory. However, this is an extreme edge case. |
| Concurrent extraction | No locking or synchronization. Multiple `FileUnarchiveComponent` instances extracting to the same directory could cause race conditions and file overwrites. |
| Disk space checking | No pre-extraction check for available disk space. Extraction of a large archive to a nearly-full disk will fail mid-extraction, potentially leaving a partial extraction. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileUnarchiveComponent` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |

**Key finding**: The v1 engine has ZERO tests for this component. All 181 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic ZIP extraction | P0 | Create a ZIP archive with known files, extract via component, verify extracted files match originals in content and count |
| 2 | Missing archive file + die_on_error=true | P0 | Should raise `FileNotFoundError` with descriptive message |
| 3 | Missing archive file + die_on_error=false | P0 | Should return empty DataFrame with stats (1, 0, 1), should not raise |
| 4 | Extraction directory creation | P0 | Specify non-existent output directory, verify it is created automatically |
| 5 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly in stats dict after successful and failed extraction |
| 6 | Corrupt ZIP file | P0 | Provide a truncated/corrupt ZIP file, verify appropriate error handling with both die_on_error modes |
| 7 | Empty ZIP archive | P0 | Extract an empty ZIP archive (valid but containing no files), verify no error and correct stats |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Extract with directory structure (extract_path=true) | P1 | ZIP containing subdirectories, verify directory structure is preserved in extraction output |
| 9 | Flat extraction (extract_path=false) | P1 | ZIP containing subdirectories, verify files are extracted flat (no subdirectories). **Expected to fail** -- see BUG-FUA-003 |
| 10 | Password-protected ZIP | P1 | Create a password-protected ZIP, extract with correct password, verify success |
| 11 | Wrong password | P1 | Attempt extraction with incorrect password, verify appropriate error |
| 12 | Missing password for protected archive | P1 | Protected archive without password config, verify appropriate error |
| 13 | Context variable in archive path | P1 | `${context.archive_dir}/file.zip` should resolve via context manager |
| 14 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution |
| 15 | Archive path with spaces | P1 | Verify `/path with spaces/archive.zip` extracts correctly |
| 16 | Zip Slip protection | P1 | Create a malicious ZIP with `../` path entries, verify extraction is blocked or paths are sanitized |
| 17 | Large archive with many files | P1 | Archive with 1000+ files, verify all are extracted and `files_extracted` count is correct |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 18 | Existing extraction directory | P2 | Extract to a directory that already exists and contains files, verify extraction succeeds without deleting existing files |
| 19 | Read-only extraction directory | P2 | Extract to a read-only directory, verify appropriate error |
| 20 | Archive with symbolic links | P2 | ZIP containing symlinks, verify behavior (security implications) |
| 21 | Unicode filenames in archive | P2 | Archive containing files with Unicode names, verify correct extraction |
| 22 | Concurrent extraction | P2 | Two components extracting to same directory simultaneously, verify no corruption |
| 23 | Very long file paths in archive | P2 | Archive with deeply nested directories exceeding OS path limits |
| 24 | Overwrite existing files | P2 | Extract archive where files already exist in target, verify overwrite behavior |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FUA-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-FUA-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-FUA-001 | Testing | Zero v1 unit tests for this component. All 181 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FUA-001 | Converter | Unsafe `.find().get()` pattern crashes on missing XML elements. Every line in `parse_tfileunarchive()` is vulnerable to `AttributeError` if a parameter is absent. |
| CONV-FUA-002 | Converter | `EXTRACTPATH` extracted as string, not boolean. String `'false'` is truthy in Python, so `extract_path` will ALWAYS be treated as True. Flat extraction is impossible. |
| ENG-FUA-001 | Engine | ZIP-only support. Talend supports tar, tar.gz, tgz, gz. Python has native support via `tarfile` and `gzip` modules. |
| ENG-FUA-002 | Engine | No `CURRENT_FILE`/`CURRENT_FILEPATH` globalMap variables. These are the primary output mechanism for downstream iterate workflows. Component is non-functional for the most common Talend usage pattern. |
| ENG-FUA-003 | Engine | No iterate output mechanism. Component extracts all files at once with no per-file iteration. Cannot be used with iterate links. |
| ENG-FUA-004 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap. Error details not available downstream. |
| BUG-FUA-003 | Bug | Flat extraction (extract_path=false) still preserves directory structure. Both branches of the if/else produce identical behavior. |
| BUG-FUA-004 | Bug | Password only applied when `check_password` is true, but `check_password` maps to Talend's integrity check (`CHECKPASSWORD`), not the password flag (`NEED_PASSWORD`). |
| BUG-FUA-005 | Bug | `_validate_config()` is dead code -- never called by any code path. |
| BUG-FUA-009 | Bug (Engine) | `die_on_error` default `True` contradicts Talend default `false`. Jobs relying on Talend default continue-on-error behavior get fail-fast instead. |
| BUG-FUA-010 | Bug | `os.makedirs()` TOCTOU race condition (lines 138-140). Checks `os.path.exists()` then calls `os.makedirs()`. Fix: `os.makedirs(output_directory, exist_ok=True)`. |
| SEC-FUA-001 | Security | Zip Slip vulnerability. `extractall()` does not validate extracted paths stay within output directory. Malicious archives could overwrite arbitrary files. |
| SEC-FUA-002 | Security | Symlink attack vector in ZIP extraction. Malicious ZIP can contain symlink entries pointing to sensitive locations; subsequent entries write through the symlink. Distinct from Zip Slip. |
| TEST-FUA-002 | Testing | No integration test for this component in a multi-step v1 job (e.g., `tFileUnarchive -> tFileInputDelimited`). |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FUA-003 | Converter | `USE_ARCHIVE_NAME` not extracted. Archive-named subdirectory feature unavailable. |
| CONV-FUA-004 | Converter | `DECRYPT_TYPE` not extracted. Only standard Java Decrypt implicitly supported. AES-256 via Zip4j unavailable. |
| ENG-FUA-005 | Engine | No `USE_ARCHIVE_NAME` support. Jobs relying on archive-named subdirectories get incorrect extraction paths. |
| ENG-FUA-006 | Engine | No integrity check before extraction. Python's `zipfile.testzip()` could be used. |
| BUG-FUA-006 | Bug | Password encoding assumes UTF-8. May fail for non-ASCII passwords on non-UTF-8 systems. |
| BUG-FUA-007 | Bug | `extractall()` Zip Slip vulnerability (detailed in SEC-FUA-001). |
| BUG-FUA-008 | Bug | Fragile stats pattern -- double-counting possible in generic exception handler if explicit return is missed. |
| BUG-FUA-011 | Bug | `files_extracted` count includes directory entries from `namelist()`, inflating the reported count. |
| SEC-FUA-003 | Security | Password may appear in plaintext in config dump logs. Should be masked. |
| SEC-FUA-004 | Security | No path traversal protection on input paths (archive path, output directory). |
| STD-FUA-001 | Standards | `_validate_config()` exists but never called -- dead validation code. |
| STD-FUA-002 | Standards | GlobalMap variables `CURRENT_FILE`, `CURRENT_FILEPATH` not set -- violates Talend compatibility requirements. |
| STD-FUA-003 | Standards | Component status has no nuance -- always SUCCESS or ERROR, no WARNING state for partial success. |
| PERF-FUA-001 | Performance | Large archive extraction blocks execution with no progress reporting. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FUA-005 | Converter | No Java expression marking for ZIPFILE/DIRECTORY values. Dynamic paths via Java expressions not resolved. |
| ENG-FUA-007 | Engine | NB_LINE always 1 instead of tracking per-file count. Files_extracted already calculated but not propagated to stats. |
| NAME-FUA-001 | Naming | Config key `zipfile` shadows Python's `zipfile` module name. Could cause confusion. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 14 | 2 converter, 4 engine, 5 bugs, 2 security, 1 testing |
| P2 | 14 | 2 converter, 2 engine, 4 bugs, 2 security, 3 standards, 1 performance |
| P3 | 3 | 1 converter, 1 engine, 1 naming |
| **Total** | **34** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FUA-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FUA-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-FUA-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic ZIP extraction, missing file handling (both die_on_error modes), directory creation, statistics tracking, corrupt archive, and empty archive. Without these, no v1 engine behavior is verified.

4. **Fix Zip Slip vulnerability** (SEC-FUA-001): Add path validation before extraction. For each entry in the archive, verify the resolved path stays within the output directory. Note: Python's `zipfile` module has no built-in `filter` parameter for path safety (the `filter='data'` parameter added in Python 3.12 via PEP 706 applies only to `tarfile.extractall()`, NOT `zipfile`). Manual validation is required:
   ```python
   for member in archive.namelist():
       target_path = os.path.realpath(os.path.join(output_directory, member))
       if not target_path.startswith(os.path.realpath(output_directory) + os.sep):
           raise RuntimeError(f"Zip Slip detected: {member} would extract outside target directory")
   archive.extractall(output_directory)
   ```

### Short-Term (Hardening)

5. **Add tar/gz/tgz support** (ENG-FUA-001): Implement archive format detection based on file extension, then use the appropriate Python module:
   ```python
   import tarfile, gzip, shutil

   if zipfile_path.endswith('.zip'):
       # existing ZIP logic
   elif zipfile_path.endswith(('.tar.gz', '.tgz')):
       with tarfile.open(zipfile_path, 'r:gz') as tar:
           tar.extractall(output_directory)
   elif zipfile_path.endswith('.tar'):
       with tarfile.open(zipfile_path, 'r:') as tar:
           tar.extractall(output_directory)
   elif zipfile_path.endswith('.gz'):
       # Single-file gzip decompression
       output_file = os.path.join(output_directory, os.path.basename(zipfile_path[:-3]))
       with gzip.open(zipfile_path, 'rb') as f_in, open(output_file, 'wb') as f_out:
           shutil.copyfileobj(f_in, f_out)
   ```
   **Note**: `tarfile.extractall()` also has path traversal risks. Use the `filter='data'` parameter on Python 3.12+ (PEP 706 -- this filter is specific to `tarfile`, not `zipfile`) or validate paths manually.

6. **Implement `CURRENT_FILE` and `CURRENT_FILEPATH` globalMap variables** (ENG-FUA-002): After extraction, iterate over extracted files and set globalMap variables:
   ```python
   for member in archive.namelist():
       if self.global_map:
           self.global_map.put(f"{self.id}_CURRENT_FILE", os.path.basename(member))
           self.global_map.put(f"{self.id}_CURRENT_FILEPATH", os.path.join(output_directory, member))
   ```
   For proper iterate-link support, this needs integration with the engine's iteration mechanism (see recommendation 7).

7. **Implement iterate output support** (ENG-FUA-003): Refactor `FileUnarchiveComponent` to extend `BaseIterateComponent` (if available) or add iteration support. The component should yield per-file results, setting `CURRENT_FILE` and `CURRENT_FILEPATH` for each extracted file. This is the most complex change but is required for the most common Talend usage pattern.

8. **Fix `EXTRACTPATH` boolean conversion in converter** (CONV-FUA-002): Change line 1679 from:
   ```python
   component['config']['extract_path'] = node.find('.//elementParameter[@name="EXTRACTPATH"]').get('value', '')
   ```
   to:
   ```python
   component['config']['extract_path'] = node.find('.//elementParameter[@name="EXTRACTPATH"]').get('value', 'false').lower() == 'true'
   ```
   This matches the pattern used for `CHECKPASSWORD` and `DIE_ON_ERROR` on lines 1680 and 1682.

9. **Fix flat extraction behavior** (BUG-FUA-003): Replace the `extract_path=false` branch (lines 159-162) with proper flat extraction:
   ```python
   for file_info in archive.infolist():
       if not file_info.is_dir():
           # Extract to flat directory (filename only, no path)
           file_info.filename = os.path.basename(file_info.filename)
           archive.extract(file_info, output_directory)
           files_extracted += 1
   ```

10. **Add null-safe `.find().get()` pattern in converter** (CONV-FUA-001): Replace every `node.find(...).get(...)` call with a null-safe helper:
    ```python
    def _safe_get_param(self, node, param_name, default=''):
        elem = node.find(f'.//elementParameter[@name="{param_name}"]')
        return elem.get('value', default) if elem is not None else default
    ```
    Then use: `component['config']['zipfile'] = self._safe_get_param(node, 'ZIPFILE')`.

11. **Fix password semantic mapping** (BUG-FUA-004): Extract `NEED_PASSWORD` from XML and use it (instead of `CHECKPASSWORD`) as the condition for setting the archive password:
    ```python
    # In converter:
    component['config']['need_password'] = node.find('.//elementParameter[@name="NEED_PASSWORD"]').get('value', 'false').lower() == 'true'

    # In engine:
    need_password = self.config.get('need_password', False)
    if need_password and password:
        archive.setpassword(password.encode())
    ```

12. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-FUA-004): In exception handlers, store the error message:
    ```python
    except Exception as e:
        if self.global_map:
            self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
        # ... existing error handling
    ```

13. **Wire up `_validate_config()`** (BUG-FUA-005): Add a call to `_validate_config()` at the beginning of `_process()`, checking the returned error list and raising `ConfigurationError` or returning empty DataFrame based on `die_on_error`.

### Long-Term (Optimization)

14. **Add `USE_ARCHIVE_NAME` support** (ENG-FUA-005): If `use_archive_name` config is true, modify the output directory:
    ```python
    if self.config.get('use_archive_name', False):
        archive_name = os.path.splitext(os.path.basename(zipfile_path))[0]
        output_directory = os.path.join(output_directory, archive_name)
    ```

15. **Add integrity check** (ENG-FUA-006): Before extraction, call `archive.testzip()`:
    ```python
    if check_integrity:
        bad_file = archive.testzip()
        if bad_file:
            raise RuntimeError(f"Archive integrity check failed: corrupt file '{bad_file}'")
    ```

16. **Propagate files_extracted to NB_LINE** (ENG-FUA-007): Change `self._update_stats(1, 1, 0)` on line 165 to `self._update_stats(files_extracted, files_extracted, 0)` to reflect the actual number of files extracted, matching Talend's behavior.

17. **Add progress logging for large archives** (PERF-FUA-001): During extraction, log progress periodically:
    ```python
    total_files = len(archive.namelist())
    for i, file in enumerate(archive.namelist()):
        archive.extract(file, output_directory)
        if (i + 1) % 100 == 0:
            logger.info(f"[{self.id}] Extracted {i + 1}/{total_files} files...")
    ```

18. **Add Java expression marking in converter** (CONV-FUA-005): Mark ZIPFILE and DIRECTORY values for Java expression resolution:
    ```python
    component['config']['zipfile'] = self.expr_converter.mark_java_expression(
        self._safe_get_param(node, 'ZIPFILE'))
    component['config']['directory'] = self.expr_converter.mark_java_expression(
        self._safe_get_param(node, 'DIRECTORY'))
    ```

19. **Mask password in config dumps** (SEC-FUA-002): Add password masking in any config logging or serialization:
    ```python
    def _get_safe_config(self):
        """Return config with sensitive fields masked"""
        safe = self.config.copy()
        if 'password' in safe:
            safe['password'] = '***MASKED***'
        return safe
    ```

20. **Create integration test** (TEST-FUA-002): Build an end-to-end test exercising `tFileUnarchive -> tFileInputDelimited` in the v1 engine, verifying extraction, globalMap propagation, and iterate-link behavior.

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 1675-1683
def parse_tfileunarchive(self, node, component: Dict) -> Dict:
    """Parse tFileUnarchive specific configuration"""
    component['config']['zipfile'] = node.find('.//elementParameter[@name="ZIPFILE"]').get('value', '')
    component['config']['directory'] = node.find('.//elementParameter[@name="DIRECTORY"]').get('value', '')
    component['config']['extract_path'] = node.find('.//elementParameter[@name="EXTRACTPATH"]').get('value', '')
    component['config']['check_password'] = node.find('.//elementParameter[@name="CHECKPASSWORD"]').get('value', 'false').lower() == 'true'
    component['config']['password'] = node.find('.//elementParameter[@name="PASSWORD"]').get('value', '')
    component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'
    return component
```

**Notes on this code**:
- Line 1677: `ZIPFILE` extracted as raw string. No Java expression marking.
- Line 1678: `DIRECTORY` extracted as raw string. No Java expression marking.
- Line 1679: `EXTRACTPATH` extracted as RAW STRING -- not converted to boolean. This is inconsistent with `CHECKPASSWORD` (line 1680) and `DIE_ON_ERROR` (line 1682) which are correctly converted via `.lower() == 'true'`. This bug means `extract_path` is always truthy (any non-empty string) in the engine.
- Line 1680: `CHECKPASSWORD` maps to integrity check, not password flag. The Talend parameter for the password feature is `NEED_PASSWORD`, which is not extracted.
- Line 1681: `PASSWORD` extracted as plaintext string. No encoding or security considerations.
- All lines use unsafe `.find().get()` pattern that crashes on missing XML elements.

**Comparison with `parse_tfilearchive()` (lines 1665-1673)**:
The companion `tFileArchive` parser extracts 7 parameters (`SOURCE`, `TARGET`, `ARCHIVE_FORMAT`, `SUB_DIRECTORY`, `OVERWRITE`, `LEVEL`) and has the same `.find().get()` vulnerability. It also only supports ZIP in the engine, despite extracting `ARCHIVE_FORMAT`.

---

## Appendix B: Engine Class Structure

```
FileUnarchiveComponent (BaseComponent)
    Constants:
        DEFAULT_EXTRACT_PATH = True
        DEFAULT_CHECK_PASSWORD = False
        DEFAULT_DIE_ON_ERROR = True

    Methods:
        _validate_config() -> List[str]          # DEAD CODE -- never called
        _process(input_data) -> Dict[str, Any]   # Main entry point

    Config Keys:
        zipfile (str):         Path to archive file. Required.
        directory (str):       Output directory for extraction. Required.
        extract_path (bool):   Preserve directory structure. Default True.
        check_password (bool): Enable password (actually integrity check). Default False.
        password (str):        Archive password. Default None.
        die_on_error (bool):   Fail on error. Default True.
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `ZIPFILE` | `zipfile` | Mapped | -- |
| `DIRECTORY` | `directory` | Mapped | -- |
| `EXTRACTPATH` | `extract_path` | Mapped (broken -- string not bool) | P1 fix |
| `CHECKPASSWORD` | `check_password` | Mapped (wrong semantic -- integrity, not password) | P1 fix |
| `PASSWORD` | `password` | Mapped | -- |
| `DIE_ON_ERROR` | `die_on_error` | Mapped | -- |
| `USE_ARCHIVE_NAME` | `use_archive_name` | **Not Mapped** | P2 |
| `NEED_PASSWORD` | `need_password` | **Not Mapped** | P1 |
| `DECRYPT_TYPE` | `decrypt_type` | **Not Mapped** | P2 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix D: Edge Case Analysis

### Edge Case 1: Empty ZIP archive

| Aspect | Detail |
|--------|--------|
| **Talend** | Extracts 0 files, no error. NB_LINE=0. |
| **V1** | `archive.extractall()` on empty ZIP succeeds. `files_extracted = len(archive.namelist()) = 0`. Stats (1, 1, 0) -- note NB_LINE=1, not 0. |
| **Verdict** | PARTIAL -- succeeds but NB_LINE differs (1 vs 0). |

### Edge Case 2: Archive with single file, no directories

| Aspect | Detail |
|--------|--------|
| **Talend** | Extracts file to extraction directory. CURRENT_FILEPATH set. |
| **V1** | `archive.extractall()` extracts correctly. CURRENT_FILEPATH not set. |
| **Verdict** | PARTIAL -- extraction works, GlobalMap not populated. |

### Edge Case 3: Archive containing empty directories

| Aspect | Detail |
|--------|--------|
| **Talend** | Empty directories are created in extraction path. |
| **V1** | `archive.extractall()` creates empty directories (ZIP stores directory entries). |
| **Verdict** | CORRECT |

### Edge Case 4: Archive path with context variable

| Aspect | Detail |
|--------|--------|
| **Talend** | Context variables resolved before extraction. |
| **V1** | `context_manager.resolve_dict()` resolves `${context.var}` patterns. BUT Java expressions in archive path not marked by converter, so `context.dir + "/file.zip"` fails. |
| **Verdict** | PARTIAL -- simple context variables work, Java expressions fail. |

### Edge Case 5: Archive path is NaN or None

| Aspect | Detail |
|--------|--------|
| **Talend** | Fails with clear error. |
| **V1** | `self.config.get('zipfile')` returns `None` or NaN. `os.path.exists(None)` raises `TypeError`. Generic `except Exception` catches it, stats updated, empty DF returned (die_on_error=false) or exception propagated (die_on_error=true). |
| **Verdict** | PARTIAL -- error is caught but the error message from `TypeError` is not user-friendly. Should check for None/NaN explicitly. |

### Edge Case 6: Archive path is empty string

| Aspect | Detail |
|--------|--------|
| **Talend** | Fails with "File not found" or "Empty path" error. |
| **V1** | `_validate_config()` would catch this with `if not self.config.get('zipfile')`, but `_validate_config()` is never called. In `_process()`, `zipfile_path = ''`, then `os.path.exists('')` returns `False`, then `FileNotFoundError` is raised. |
| **Verdict** | CORRECT (accidental) -- empty string is handled correctly by `os.path.exists('')` returning False. |

### Edge Case 7: Extraction directory is empty string

| Aspect | Detail |
|--------|--------|
| **Talend** | Fails with error about invalid directory. |
| **V1** | `output_directory = ''`. `os.path.exists('')` returns `False`. `os.makedirs('')` raises `FileNotFoundError`. Generic exception handler catches it. |
| **Verdict** | PARTIAL -- error is caught but message is confusing ("No such file or directory: ''"). |

### Edge Case 8: Extraction directory with trailing slash

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles correctly (Java File normalization). |
| **V1** | `os.path.exists('/output/')` and `os.makedirs('/output/')` both handle trailing slashes correctly. |
| **Verdict** | CORRECT |

### Edge Case 9: Password-protected archive without password config

| Aspect | Detail |
|--------|--------|
| **Talend** | Fails with password-required error. |
| **V1** | If `check_password=false` (which it is by default), password is never set. `archive.extractall()` on a password-protected ZIP raises `RuntimeError: File ... is encrypted, password required for extraction`. The generic exception handler catches it. |
| **Verdict** | CORRECT -- error is detected and handled. But the error path depends on the incorrect `check_password` semantic mapping. |

### Edge Case 10: ZIP file with special characters in filenames

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles via Java's Unicode support. |
| **V1** | Python's `zipfile` handles Unicode filenames (UTF-8 flag in ZIP). Legacy archives with non-UTF-8 filenames may produce mojibake. |
| **Verdict** | CORRECT for modern ZIPs. PARTIAL for legacy archives with non-UTF-8 names. |

### Edge Case 11: Zip Slip attack (path traversal in archive)

| Aspect | Detail |
|--------|--------|
| **Talend** | Potentially vulnerable (depends on Java version and configuration). |
| **V1** | VULNERABLE. `archive.extractall()` does not validate extracted paths. A ZIP entry named `../../etc/cron.d/malicious` would write to `/etc/cron.d/malicious` if the process has sufficient permissions. Python 3.12+ can mitigate with `filter='data'`. |
| **Verdict** | GAP -- security vulnerability present in both Talend and V1. |

### Edge Case 12: Archive larger than available disk space

| Aspect | Detail |
|--------|--------|
| **Talend** | Fails mid-extraction with disk space error. Partial files may remain. |
| **V1** | Same behavior. `archive.extractall()` writes files until disk is full, then raises `OSError`. Generic handler catches it. Partial extraction remains on disk. |
| **Verdict** | CORRECT (same behavior as Talend). No pre-check for disk space in either. |

### Edge Case 13: Archive file is actually not a ZIP (wrong extension)

| Aspect | Detail |
|--------|--------|
| **Talend** | Auto-detects format from file content/extension. May succeed with correct format. |
| **V1** | `zipfile.ZipFile()` raises `zipfile.BadZipFile` if the file is not a valid ZIP. Since the V1 engine only supports ZIP, non-ZIP archives will always fail. |
| **Verdict** | GAP -- V1 fails where Talend would succeed (for tar/gz files with .zip extension or vice versa). |

### Edge Case 14: Concurrent extractions to same directory

| Aspect | Detail |
|--------|--------|
| **Talend** | Depends on Java's file locking behavior. May produce race conditions. |
| **V1** | No locking or synchronization. Two extractions writing to the same directory could overwrite each other's files. `os.makedirs()` is race-safe on most operating systems. |
| **Verdict** | PARTIAL -- same risks as Talend. No protection in either system. |

### Edge Case 15: Archive with 0-byte files

| Aspect | Detail |
|--------|--------|
| **Talend** | Extracts 0-byte files correctly. |
| **V1** | `archive.extractall()` creates 0-byte files correctly. `files_extracted` counts them. |
| **Verdict** | CORRECT |

---

## Appendix E: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FileUnarchiveComponent`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FUA-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-FUA-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| BUG-FUA-005 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called. ALL components with validation logic have dead validation. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix F: Implementation Fix Guides

### Fix Guide: BUG-FUA-001 -- `_update_global_map()` undefined variable

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

### Fix Guide: BUG-FUA-002 -- `GlobalMap.get()` undefined default

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

### Fix Guide: CONV-FUA-002 -- `EXTRACTPATH` string-to-boolean conversion

**File**: `src/converters/complex_converter/component_parser.py`
**Line**: 1679

**Current code (broken)**:
```python
component['config']['extract_path'] = node.find('.//elementParameter[@name="EXTRACTPATH"]').get('value', '')
```

**Fix**:
```python
component['config']['extract_path'] = node.find('.//elementParameter[@name="EXTRACTPATH"]').get('value', 'false').lower() == 'true'
```

**Explanation**: The current code stores a string like `'true'` or `'false'`. In Python, both are truthy (non-empty strings), so the engine always treats `extract_path` as True. The fix converts to a proper Python boolean, matching the pattern used for `CHECKPASSWORD` and `DIE_ON_ERROR` on adjacent lines.

**Impact**: Enables flat extraction when Talend jobs have `EXTRACTPATH=false`. **Risk**: Low.

---

### Fix Guide: BUG-FUA-003 -- Flat extraction implementation

**File**: `src/v1/engine/components/file/file_unarchive.py`
**Lines**: 158-162

**Current code (does not flatten)**:
```python
else:
    logger.debug(f"[{self.id}] Extracting files without directory structure")
    for file in archive.namelist():
        archive.extract(file, output_directory)
        files_extracted += 1
        logger.debug(f"[{self.id}] Extracted file: {file}")
```

**Fix**:
```python
else:
    logger.debug(f"[{self.id}] Extracting files without directory structure (flat)")
    for file_info in archive.infolist():
        if file_info.is_dir():
            continue  # Skip directory entries
        # Extract filename only, stripping any directory path
        filename = os.path.basename(file_info.filename)
        if not filename:
            continue  # Skip entries with no filename
        target_path = os.path.join(output_directory, filename)
        with archive.open(file_info) as source, open(target_path, 'wb') as target:
            import shutil
            shutil.copyfileobj(source, target)
        files_extracted += 1
        logger.debug(f"[{self.id}] Extracted file (flat): {filename}")
```

**Explanation**: The original code uses `archive.extract(file, output_directory)` which preserves the relative path. The fix reads file content and writes it using only the base filename, achieving true flat extraction.

**Impact**: Enables flat extraction mode. **Risk**: Low. May cause filename collisions if archive contains files with same name in different directories.

---

### Fix Guide: SEC-FUA-001 -- Zip Slip protection

**File**: `src/v1/engine/components/file/file_unarchive.py`
**Lines**: 152-162

**Add before extraction** (after `with zipfile.ZipFile(zipfile_path, 'r') as archive:`):
```python
# Validate all archive entries for path traversal (Zip Slip)
real_output = os.path.realpath(output_directory)
for member in archive.namelist():
    member_path = os.path.realpath(os.path.join(output_directory, member))
    if not member_path.startswith(real_output + os.sep) and member_path != real_output:
        error_msg = f"Zip Slip detected: archive entry '{member}' would extract outside target directory"
        logger.error(f"[{self.id}] {error_msg}")
        raise RuntimeError(error_msg)
```

**Impact**: Prevents arbitrary file write via crafted ZIP archives. **Risk**: Very low (only rejects malicious archives).

---

### Fix Guide: ENG-FUA-001 -- Multi-format archive support

**File**: `src/v1/engine/components/file/file_unarchive.py`

**Add new imports** at the top of the file:
```python
import tarfile
import gzip
import shutil
```

**Replace the extraction block** in `_process()` with format detection:
```python
# Detect archive format and extract
lower_path = zipfile_path.lower()
if lower_path.endswith('.zip'):
    files_extracted = self._extract_zip(zipfile_path, output_directory, extract_path, check_password, password)
elif lower_path.endswith(('.tar.gz', '.tgz')):
    files_extracted = self._extract_tar(zipfile_path, output_directory, 'r:gz')
elif lower_path.endswith('.tar'):
    files_extracted = self._extract_tar(zipfile_path, output_directory, 'r:')
elif lower_path.endswith('.gz'):
    files_extracted = self._extract_gzip(zipfile_path, output_directory)
else:
    raise RuntimeError(f"Unsupported archive format: {zipfile_path}")
```

**Add new helper methods**:
```python
def _extract_zip(self, path, output_dir, extract_path, check_password, password):
    # existing ZIP logic
    pass

def _extract_tar(self, path, output_dir, mode):
    with tarfile.open(path, mode) as tar:
        tar.extractall(output_dir, filter='data')  # Python 3.12+ for safety
        return len(tar.getmembers())

def _extract_gzip(self, path, output_dir):
    output_file = os.path.join(output_dir, os.path.basename(path[:-3]))
    with gzip.open(path, 'rb') as f_in, open(output_file, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    return 1
```

**Impact**: Enables extraction of all five Talend-supported archive formats. **Risk**: Medium (new code paths, needs thorough testing).

---

## Appendix G: Comparison with FileArchiveComponent

| Feature | FileUnarchiveComponent | FileArchiveComponent |
|---------|----------------------|---------------------|
| Core function | Extract archive to directory | Create archive from directory/file |
| ZIP support | Yes | Yes |
| tar/gz support | **No** | **No** (only ZIP in `SUPPORTED_FORMATS`) |
| Password support | Yes (standard ZIP only) | No (not implemented) |
| `die_on_error` | Yes | Yes |
| `_validate_config()` | Dead code (never called) | Dead code (never called) |
| GlobalMap variables | Missing CURRENT_FILE/FILEPATH | Not applicable (no iterate output) |
| Converter `.find().get()` safety | **Unsafe** (crashes on missing) | **Unsafe** (same pattern) |
| Overwrite protection | No (always overwrites) | Yes (`overwrite` config flag) |
| NB_LINE semantics | Always 1 | Always 1 |
| Lines of code | 181 | 194 |

**Observation**: Both archive components share the same structural issues: dead `_validate_config()`, unsafe converter patterns, ZIP-only support despite Talend supporting multiple formats, and cross-cutting base class bugs. A coordinated fix effort for both components would be efficient.

---

## Appendix H: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs extracting tar/gz/tgz archives | **Critical** | Any job using tFileUnarchive with non-ZIP archives | Must add tar/gz support before migrating |
| Jobs using iterate link to process extracted files | **Critical** | Any job with `tFileUnarchive -> (iterate) -> downstream` | Must implement CURRENT_FILE/CURRENT_FILEPATH and iterate output |
| Jobs with EXTRACTPATH=false (flat extraction) | **High** | Jobs requiring flat directory output | Must fix boolean conversion bug and flat extraction implementation |
| Jobs using password-protected archives | **High** | Jobs with NEED_PASSWORD=true | Must fix password semantic mapping (CHECKPASSWORD vs NEED_PASSWORD) |
| Jobs using USE_ARCHIVE_NAME | **Medium** | Jobs relying on archive-named subdirectories | Must implement USE_ARCHIVE_NAME support |
| Jobs using `{id}_ERROR_MESSAGE` downstream | **Medium** | Error handling flows checking ERROR_MESSAGE | Must set ERROR_MESSAGE in globalMap |
| Jobs with dynamic archive paths (Java expressions) | **Medium** | Jobs using context + string concatenation in paths | Must add Java expression marking in converter |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs using Zip4j Decrypt (AES-256) | Low | Uncommon -- most archives use standard ZIP encryption or no encryption |
| Jobs using tStatCatcher with tFileUnarchive | Low | tStatCatcher rarely used |
| Jobs relying on integrity check | Low | Pre-extraction integrity checks are optional safety net |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (cross-cutting). Run existing converted jobs to verify basic ZIP extraction functionality.
2. **Phase 2**: Audit each target job's Talend configuration. Identify which P1 features are used (tar/gz formats, iterate links, password protection, flat extraction).
3. **Phase 3**: Implement P1 features required by target jobs (multi-format support, iterate output, CURRENT_FILE/CURRENT_FILEPATH, boolean conversion fix, flat extraction fix).
4. **Phase 4**: Add Zip Slip protection (security-critical).
5. **Phase 5**: Parallel-run migrated jobs against Talend originals. Compare extraction output file-for-file (count, names, sizes, checksums).
6. **Phase 6**: Fix any differences found in parallel-run testing.

---

## Appendix I: Detailed `_process()` Flow Analysis

```
_process(input_data)
    |
    +-- Get config values (lines 119-124)
    |   zipfile_path, output_directory, extract_path,
    |   check_password, password, die_on_error
    |
    +-- Check archive exists (line 127)
    |   |
    |   +-- Not found + die_on_error=true -> raise FileNotFoundError
    |   +-- Not found + die_on_error=false -> stats(1,0,1), return empty DF
    |
    +-- Create output directory if needed (line 138-140)
    |   os.makedirs(output_directory)
    |
    +-- Open ZIP archive (line 146)
    |   zipfile.ZipFile(zipfile_path, 'r')
    |
    +-- Set password if check_password AND password (lines 148-150)
    |   BUG: check_password maps to integrity, not password flag
    |
    +-- Extract files (lines 152-162)
    |   |
    |   +-- extract_path=true -> extractall(output_directory)
    |   |   files_extracted = len(namelist())
    |   |
    |   +-- extract_path=false -> per-file extract()
    |       BUG: still preserves directory structure
    |
    +-- Update stats (line 165)
    |   _update_stats(1, 1, 0)
    |   NOTE: Always 1, not files_extracted
    |
    +-- Return empty DataFrame (line 169)
    |
    +-- Exception handler (lines 171-180)
        _update_stats(1, 0, 1)
        die_on_error=true -> re-raise
        die_on_error=false -> return empty DF
```

**Key observations**:
1. No CURRENT_FILE/CURRENT_FILEPATH setting anywhere in the flow
2. No ERROR_MESSAGE globalMap setting in exception handler
3. Password check condition is semantically incorrect
4. Stats always 1 regardless of file count
5. Both extract_path branches produce identical behavior
6. No Zip Slip validation before extraction
7. No format detection -- always assumes ZIP

---

## Appendix J: Converter Dispatch Chain

```
converter.py:_parse_component()
    |
    +-- Line 282: elif component_type == 'tFileUnarchive':
    |       component = self.component_parser.parse_tfileunarchive(node, component)
    |
    +-- parse_tfileunarchive(node, component)  [component_parser.py:1675-1683]
        |
        +-- Line 1677: zipfile = node.find('ZIPFILE').get('value', '')
        |   RISK: AttributeError if ZIPFILE element missing
        |
        +-- Line 1678: directory = node.find('DIRECTORY').get('value', '')
        |   RISK: AttributeError if DIRECTORY element missing
        |
        +-- Line 1679: extract_path = node.find('EXTRACTPATH').get('value', '')
        |   BUG: Raw string, not boolean. 'false' is truthy.
        |
        +-- Line 1680: check_password = boolean conversion of CHECKPASSWORD
        |   SEMANTIC: Maps to integrity check, not password flag
        |
        +-- Line 1681: password = node.find('PASSWORD').get('value', '')
        |   OK: Plaintext extraction (no expression handling)
        |
        +-- Line 1682: die_on_error = boolean conversion of DIE_ON_ERROR
        |   OK: Correct boolean conversion
        |
        +-- NOT EXTRACTED: USE_ARCHIVE_NAME, NEED_PASSWORD, DECRYPT_TYPE
        |
        +-- return component
```

---

## Appendix K: Detailed `_validate_config()` Analysis

### Current Dead Code (Lines 65-98)

```python
def _validate_config(self) -> List[str]:
    errors = []

    # Required fields
    if not self.config.get('zipfile'):
        errors.append("Missing required config: 'zipfile'")

    if not self.config.get('directory'):
        errors.append("Missing required config: 'directory'")

    # Optional field validation
    zipfile_path = self.config.get('zipfile')
    if zipfile_path and not isinstance(zipfile_path, str):
        errors.append("Config 'zipfile' must be a string path")

    directory = self.config.get('directory')
    if directory and not isinstance(directory, str):
        errors.append("Config 'directory' must be a string path")

    check_password = self.config.get('check_password', self.DEFAULT_CHECK_PASSWORD)
    if not isinstance(check_password, bool):
        errors.append("Config 'check_password' must be a boolean")

    extract_path = self.config.get('extract_path', self.DEFAULT_EXTRACT_PATH)
    if not isinstance(extract_path, bool):
        errors.append("Config 'extract_path' must be a boolean")

    return errors
```

**Analysis**:

1. **Never invoked**: Neither `__init__()`, `execute()`, nor `_process()` call `_validate_config()`. The base class `BaseComponent` does not call it either. There is no lifecycle hook that invokes validation. All 33 lines of validation logic are completely dead code.

2. **Would catch CONV-FUA-002**: If the validation were active, line 94-96 checks `isinstance(extract_path, bool)`. Since the converter provides a string (not a boolean), this check would fail and produce the error message `"Config 'extract_path' must be a boolean"`. This demonstrates that the developer who wrote the validation was aware that `extract_path` should be boolean, but the converter team did not match this expectation.

3. **Does not validate `password`**: The validation method checks `zipfile`, `directory`, `check_password`, and `extract_path`, but does NOT validate the `password` field. If `check_password=true` but `password` is empty or None, the validation would not catch this inconsistency.

4. **Does not validate `die_on_error`**: The `die_on_error` config value is not validated for type correctness. If the converter provides a string `'true'` instead of boolean `True`, the validation would not catch it. However, this is not currently a problem since `DIE_ON_ERROR` is correctly converted to boolean in the converter.

5. **Error list never checked**: Even if `_validate_config()` were called, it returns a `List[str]` of error messages. No caller checks this list or raises exceptions based on it. To be functional, the calling code would need:
   ```python
   errors = self._validate_config()
   if errors:
       error_msg = '; '.join(errors)
       if self.config.get('die_on_error', True):
           raise ConfigurationError(error_msg)
       else:
           logger.warning(f"[{self.id}] Validation warnings: {error_msg}")
           return {'main': pd.DataFrame()}
   ```

6. **Comparison with FileArchiveComponent**: The companion `FileArchiveComponent._validate_config()` (file_archive.py lines 66-95) validates `source`, `target`, `archive_format`, and `compression_level`. It is also dead code (never called). Both archive components have the same structural issue.

**Recommendation**: Wire up `_validate_config()` as the first step in `_process()`, or integrate validation into the `BaseComponent.execute()` lifecycle as a standard pre-processing step. Since ALL components with `_validate_config()` methods share this dead-code problem, the fix should be applied at the base class level.

---

## Appendix L: Password Handling Deep Dive

### How Password Protection Works in Talend

1. **tFileArchive creates encrypted ZIP**: When creating an archive with tFileArchive and password protection enabled, Talend uses either Java's built-in ZIP encryption (ZipOutputStream with CryptoEntry) or the Zip4j library for AES-256 encryption.

2. **tFileUnarchive decrypts**: The decrypt method must match the encryption method:
   - **Java Decrypt**: Standard PKWARE encryption. Weak (known vulnerable to known-plaintext attacks). This is the default mode.
   - **Zip4j Decrypt**: AES-128 or AES-256 encryption via the Zip4j library. Stronger but requires the Zip4j JAR in the classpath.

3. **Third-party archives**: Talend documentation explicitly states that "password-protected archives must originate from tFileArchive component." Archives encrypted by other tools (WinZip, 7-Zip, etc.) may use different encryption standards and may not be compatible.

### How Password Protection Works in V1 Engine

1. **Python's `zipfile` module**: The `setpassword()` method (line 150) sets the password for reading ZIP files encrypted with the legacy PKWARE encryption (also known as "traditional" or "weak" encryption).

2. **Password encoding**: `password.encode()` on line 150 converts the password string to bytes using UTF-8 encoding. This is required by Python's `zipfile.setpassword()` which accepts `bytes`.

3. **Limitation**: Python's `zipfile` module does NOT support AES encryption (neither AES-128 nor AES-256). This means:
   - Archives encrypted with Zip4j AES mode will fail with a `RuntimeError` or produce corrupted output.
   - Only archives using standard PKWARE encryption can be decrypted.
   - To support AES, a third-party library like `pyzipper` or `pyminizip` would be needed.

4. **Password encoding edge case**: If the archive was created on a Windows system with a non-UTF-8 default charset (e.g., Windows-1252), and the password contains non-ASCII characters (e.g., accented characters in European languages), the UTF-8 encoding of the password may not match the encoding used when the archive was created. This would cause silent decryption failure with an unhelpful error message like "Bad password for file."

5. **Empty password vs. no password**: If `password=''` (empty string), line 148's condition `if check_password and password:` evaluates to `False` (empty string is falsy). This means an empty password string is treated as "no password," which is correct behavior since ZIP encryption requires a non-empty password.

### Semantic Confusion: CHECKPASSWORD vs. NEED_PASSWORD

The current implementation has a semantic mapping error:

| Talend Parameter | XML Name | Actual Meaning | V1 Config Key | V1 Engine Usage |
|------------------|----------|---------------|---------------|-----------------|
| "Check integrity before unzip" | `CHECKPASSWORD` | Pre-extraction integrity validation | `check_password` | Used as password flag (wrong) |
| "Need a password" | `NEED_PASSWORD` | Enable password protection | Not extracted | Not available |

This means:
- If a Talend job has `CHECKPASSWORD=true` (integrity check) but `NEED_PASSWORD=false` (no password), the V1 engine will try to set a password on the archive when it should not.
- If a Talend job has `CHECKPASSWORD=false` (no integrity check) but `NEED_PASSWORD=true` (password required), the V1 engine will NOT set the password when it should.
- The only scenario where this works correctly is when both are true or both are false.

---

## Appendix M: Archive Format Detection Strategy

### Current Implementation (ZIP-only)

The V1 engine makes no attempt to detect the archive format. Line 146 unconditionally opens the file as a ZIP:
```python
with zipfile.ZipFile(zipfile_path, 'r') as archive:
```

If the file is not a valid ZIP (e.g., it is a tar.gz), this raises `zipfile.BadZipFile`.

### Proposed Multi-Format Detection

The recommended approach is to detect the format from the file extension, matching Talend's behavior:

| Extension(s) | Format | Python Module | Open Mode |
|--------------|--------|---------------|-----------|
| `.zip` | ZIP | `zipfile` | `zipfile.ZipFile(path, 'r')` |
| `.tar.gz`, `.tgz` | Gzipped TAR | `tarfile` | `tarfile.open(path, 'r:gz')` |
| `.tar` | TAR (uncompressed) | `tarfile` | `tarfile.open(path, 'r:')` |
| `.gz` | Gzip (single file) | `gzip` + `shutil` | `gzip.open(path, 'rb')` |

**Edge cases for format detection**:

1. **Double extensions**: `.tar.gz` should be detected as gzipped TAR, not just gzip. The check for `.tar.gz` must come before the check for `.gz`.

2. **Case sensitivity**: File extensions should be compared case-insensitively. `DATA.TAR.GZ` should be treated as tar.gz.

3. **No extension**: Files without extensions should either fail with a descriptive error or attempt magic-byte detection:
   - ZIP magic bytes: `PK\x03\x04` (first 4 bytes)
   - Gzip magic bytes: `\x1f\x8b` (first 2 bytes)
   - TAR magic bytes: `ustar` at offset 257

4. **Wrong extension**: A file named `archive.zip` that is actually a tar.gz should be handled gracefully. The initial format detection will fail, and the error message should suggest the file may have the wrong extension.

5. **Talend behavior**: Talend's Java implementation auto-detects the format based on file extension in most cases. Some Talend versions also check magic bytes as a fallback.

### Python Module Availability

All required modules are in the Python standard library:
- `zipfile` -- included since Python 2.x
- `tarfile` -- included since Python 2.x
- `gzip` -- included since Python 2.x
- `shutil` -- included since Python 2.x

No third-party dependencies are needed for basic multi-format support.

### Tar-Specific Security Considerations

The `tarfile` module has its own path traversal vulnerabilities, separate from the ZIP Zip Slip issue:
- TAR archives can contain absolute paths (`/etc/passwd`)
- TAR archives can contain `..` components (`../../etc/passwd`)
- TAR archives can contain symbolic links pointing outside the extraction directory

Python 3.12+ added the `filter` parameter to `tarfile.extractall()`:
- `filter='data'`: Strips absolute paths, `..` components, and symbolic links. Recommended for untrusted archives.
- `filter='fully_trusted'`: No filtering. Only for trusted archives.
- `filter=None` (default in 3.12+): Produces deprecation warning and uses legacy behavior.

For Python < 3.12, manual validation of each TAR entry is required before extraction.

---

## Appendix N: Base Component `_update_global_map()` Impact on FileUnarchiveComponent

The `_update_global_map()` method in `base_component.py` (lines 298-304) is called after every component execution:

```python
def _update_global_map(self) -> None:
    """Update global map with component statistics"""
    if self.global_map:
        for stat_name, stat_value in self.stats.items():
            self.global_map.put_component_stat(self.id, stat_name, stat_value)
        # Log the statistics for debugging
        logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} "
                     f"NB_LINE_OK:{self.stats['NB_LINE_OK']} "
                     f"NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} "
                     f"{stat_name}: {value}")  # BUG: 'value' is undefined
```

**Bug analysis** (BUG-FUA-001):
- The for loop variable is `stat_value` (line 301), but the log statement references `value` (line 304)
- `stat_name` on line 304 references the loop variable from line 301, which will have the value from the LAST iteration of the for loop (i.e., `EXECUTION_TIME` since that is the last key in the `stats` dict)
- `value` is completely undefined in this scope, causing `NameError`
- This method is called from `execute()` (line 218) after EVERY component execution
- Since `self.global_map` is set by the engine during component instantiation, this bug will crash ANY component that runs in a job with a global map configured

**Call chain for FileUnarchiveComponent**:
1. `ETLEngine._execute_component()` calls `component.execute(input_data)`
2. `BaseComponent.execute()` calls `self._update_global_map()` on line 218 (success path) or line 231 (error path)
3. `_update_global_map()` crashes with `NameError: name 'value' is not defined`
4. The `NameError` is caught by the `except Exception as e` in `execute()` line 227
5. `self.status` is set to `ComponentStatus.ERROR`
6. `self._update_global_map()` is called AGAIN on line 231 (error path), causing ANOTHER `NameError`
7. This second `NameError` propagates up unhandled, crashing the engine

**Severity**: This is the highest-severity bug in the v1 engine. It prevents ANY component from completing execution when a global map is present. The fix is trivial but the impact is total.

**Special impact on FileUnarchiveComponent**: Since tFileUnarchive is often used as the first component in a subjob (start component), a crash in `_update_global_map()` means:
- No extraction occurs (or extraction occurs but stats crash the component before it can report success)
- Downstream components in the subjob never execute
- SUBJOB_OK trigger never fires
- The entire extraction-and-process workflow fails

---

## Appendix O: GlobalMap.get() Impact Analysis

The `GlobalMap.get()` method in `global_map.py` (lines 26-28) has a complementary bug:

```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)  # BUG: 'default' not in signature
```

**Bug analysis** (BUG-FUA-002):
- `default` is referenced in the body (line 28) but is not a parameter in the method signature (line 26)
- The method signature only accepts `key: str`
- Any call to `global_map.get("some_key")` will crash with `NameError: name 'default' is not defined`

**Cascading impact**:
- `get_component_stat()` (line 51-58) calls `self.get(key, default)` with TWO arguments, but `get()` only accepts ONE positional argument. This would cause `TypeError: get() takes 2 positional arguments but 3 were given`
- `get_nb_line()`, `get_nb_line_ok()`, `get_nb_line_reject()` all call `get_component_stat()` which calls `get()` with two args
- Any downstream component trying to read `{id}_NB_LINE` via `global_map.get()` will crash

**FileUnarchiveComponent-specific impact**: If a downstream component after tFileUnarchive tries to read extraction statistics via:
```python
files_extracted = global_map.get(f"tFileUnarchive_1_NB_LINE")
```
This will crash with `NameError`, even though `put_component_stat()` successfully stored the value (since `put()` works correctly -- it does not call `get()`).

**Fix**: Add `default: Any = None` to the `get()` method signature. This fixes both the `NameError` (direct calls) and the `TypeError` (two-argument calls from `get_component_stat()`).

---

## Appendix P: Detailed Comparison of extract_path=true vs extract_path=false Behavior

### Expected Behavior (Talend)

Given a ZIP archive with the following structure:
```
data/
data/subdir/
data/subdir/file1.txt
data/file2.txt
```

**EXTRACTPATH=true** (preserve structure):
```
/output/data/
/output/data/subdir/
/output/data/subdir/file1.txt
/output/data/file2.txt
```

**EXTRACTPATH=false** (flat extraction):
```
/output/file1.txt
/output/file2.txt
```

### Actual Behavior (V1 Engine)

**extract_path=true** (line 155):
```python
archive.extractall(output_directory)
```
Result: `/output/data/subdir/file1.txt`, `/output/data/file2.txt` -- CORRECT

**extract_path=false** (lines 159-162):
```python
for file in archive.namelist():
    archive.extract(file, output_directory)
```
Result: `/output/data/subdir/file1.txt`, `/output/data/file2.txt` -- WRONG (same as true)

The `archive.extract(member, path)` method extracts the member to `path/member`, preserving the relative path. It does NOT flatten the extraction. To achieve flat extraction, the code must:
1. Read the file content from the archive
2. Determine only the filename (strip directory path)
3. Write the content to the output directory with just the filename

### Additional Complication: CONV-FUA-002

Even if the flat extraction code were correct, it would never execute because:
1. The converter extracts `EXTRACTPATH` as a raw string (line 1679)
2. A string `'false'` is truthy in Python
3. The engine's condition `if extract_path:` (line 153) always takes the True branch
4. The flat extraction code (lines 158-162) is effectively dead code

To make flat extraction work, BOTH bugs must be fixed:
1. CONV-FUA-002: Convert `EXTRACTPATH` to boolean in converter
2. BUG-FUA-003: Implement actual flat extraction logic

### Name Collision Risk in Flat Extraction

When implementing flat extraction, a new edge case emerges: if the archive contains files with the same name in different directories (e.g., `dir1/config.xml` and `dir2/config.xml`), flat extraction would overwrite one with the other. Talend handles this by appending a numeric suffix (e.g., `config.xml`, `config_1.xml`). The V1 implementation should document this behavior or implement a similar collision-avoidance strategy.

---

## Appendix Q: Source References

- [tFileUnarchive Overview (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/archive-unarchive/tfileunarchive) -- Component overview, supported formats, family classification.
- [tFileUnarchive Standard Properties (Talend 7.3)](https://help.qlik.com/talend/r/en-US/7.3/archive-unarchive/tfileunarchive-standard-properties) -- Detailed properties, GlobalMap variables, connection types.
- [tFileUnarchive Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/archive-unarchive/tfileunarchive-standard-properties) -- Updated 8.0 documentation.
- [tFileUnarchive Properties (Talend 6.3)](https://help.talend.com/reader/wDRBNUuxk629sNcI0dNYaA/tqPnzEwm2DOSNLDQ~fEWwg) -- Legacy documentation for reference.
- [tFileUnarchive tar.gz issue (Talend Community)](https://community.talend.com/t5/Migration-Configuration-and/The-tFileUnarchive-component-fails-to-extract-large-tar-gz-files/ta-p/44091) -- Community report on large tar.gz extraction failures.
- [tFileUnarchive tar.gz error (Qlik Community)](https://community.qlik.com/t5/Talend-Studio/tFileUnarchive-error-with-tar-gz-worked-fine-before/td-p/2299622) -- tar.gz compatibility issues across Talend versions.
- [Comparing unzipped files (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/archive-unarchive/tfileunarchive-tfilecompare-tfileoutputdelimited-tfilecompare-tfileoutputdelimited-comparing-unzipped-files-standard-component) -- Usage scenario combining tFileUnarchive with tFileCompare.
- [Zip Slip Vulnerability (Snyk)](https://security.snyk.io/research/zip-slip-vulnerability) -- CVE-2018-1263 Zip Slip attack reference.
- [Python zipfile documentation](https://docs.python.org/3/library/zipfile.html) -- Python standard library zipfile module reference.
- [Python tarfile documentation](https://docs.python.org/3/library/tarfile.html) -- Python standard library tarfile module reference.
- [Unzipping files in remote machine (Talend Community)](https://community.talend.com/t5/Design-and-Development/resolved-To-unzip-the-zip-files-in-remote-machine/m-p/74728) -- Community discussion on remote unarchive scenarios.
- [tFileUnarchive ESB Docs (Talend Skill)](https://talendskill.com/talend-for-esb-docs/docs-5-x/tfileunarchive-docs-for-esb-5-x/) -- ESB variant documentation with additional context.

---

## Appendix R: Common Talend Usage Patterns for tFileUnarchive

### Pattern 1: Extract and Process Files (Most Common)

```
tFileUnarchive_1 --(iterate)--> tFileInputDelimited_1 --(main)--> tMap_1 --(main)--> tFileOutputDelimited_1
```

**How it works in Talend**:
1. tFileUnarchive extracts the archive to a temporary directory
2. For each extracted file, the iterate link triggers downstream components
3. tFileInputDelimited reads the current file via `((String)globalMap.get("tFileUnarchive_1_CURRENT_FILEPATH"))`
4. The data flows through tMap and tFileOutputDelimited

**V1 engine gap**: This pattern is completely non-functional because:
- No iterate output mechanism (ENG-FUA-003)
- No CURRENT_FILEPATH globalMap variable (ENG-FUA-002)
- tFileInputDelimited cannot access the extracted file path

**Workaround in V1**: A manual workaround would be to:
1. Run FileUnarchiveComponent first
2. Manually list extracted files with a separate component
3. Feed file paths to FileInputDelimited
This is fragile and does not match Talend behavior.

### Pattern 2: Extract with Archive Name Directory

```
tFileList_1 --(iterate)--> tFileUnarchive_1 (USE_ARCHIVE_NAME=true) --(subjob_ok)--> tLogRow_1
```

**How it works in Talend**:
1. tFileList iterates over archive files in a directory
2. Each archive is extracted to a subdirectory named after the archive
3. This prevents file name collisions between different archives

**V1 engine gap**: `USE_ARCHIVE_NAME` is not extracted or implemented (CONV-FUA-003, ENG-FUA-005). All archives extract to the same flat directory, potentially causing file overwrites.

### Pattern 3: Password-Protected Archive Processing

```
tFileUnarchive_1 (NEED_PASSWORD=true, PASSWORD=context.archive_pwd) --(iterate)--> tFileInputDelimited_1
```

**How it works in Talend**:
1. Password is provided via context variable
2. tFileUnarchive decrypts and extracts the archive
3. Extracted files are processed downstream

**V1 engine gap**: Password semantic mapping is incorrect (BUG-FUA-004). The password flag maps to `CHECKPASSWORD` (integrity) instead of `NEED_PASSWORD`. If `CHECKPASSWORD=false` (default), the password is never set regardless of `NEED_PASSWORD`.

### Pattern 4: Conditional Extraction with Error Handling

```
tFileExist_1 --(run_if: true)--> tFileUnarchive_1 (DIE_ON_ERROR=false)
                                       |
                                       +--(component_ok)--> tLogRow_1 ("Extraction succeeded")
                                       +--(component_error)--> tWarn_1 (globalMap.get("tFileUnarchive_1_ERROR_MESSAGE"))
```

**How it works in Talend**:
1. tFileExist checks if the archive exists
2. If exists, tFileUnarchive extracts with error handling
3. On success, log the result
4. On failure, warn with the error message from globalMap

**V1 engine gap**: `ERROR_MESSAGE` globalMap variable is not set (ENG-FUA-004). The warning component would receive null instead of the error details.

---

## Appendix S: Iterate Output Implementation Guide

The most impactful missing feature is iterate output support. Here is a detailed implementation guide.

### Current Architecture

`FileUnarchiveComponent` extends `BaseComponent`, which does not have iterate output support. The `BaseIterateComponent` class exists in the engine but is used for components that PRODUCE iteration (like `tFileList`).

### Proposed Implementation

**Option A: Extend BaseIterateComponent**

```python
class FileUnarchiveComponent(BaseIterateComponent):
    def _iterate(self) -> Iterator[Dict[str, Any]]:
        """Yield per-file extraction results for iterate link processing"""
        # ... extraction logic ...
        for member in archive.namelist():
            if not member.endswith('/'):  # Skip directory entries
                extracted_path = os.path.join(output_directory, member)
                yield {
                    'CURRENT_FILE': os.path.basename(member),
                    'CURRENT_FILEPATH': extracted_path,
                }
```

**Option B: Set GlobalMap Variables After Extraction**

If iterate support is too complex to add immediately, a simpler approach sets the GlobalMap variables after extraction completes:

```python
# After extractall():
extracted_files = [f for f in archive.namelist() if not f.endswith('/')]
if extracted_files:
    # Set variables for the last file (non-iterate mode)
    last_file = extracted_files[-1]
    if self.global_map:
        self.global_map.put(f"{self.id}_CURRENT_FILE", os.path.basename(last_file))
        self.global_map.put(f"{self.id}_CURRENT_FILEPATH",
                           os.path.join(output_directory, last_file))
```

This provides partial compatibility (variables are set for the last extracted file) but does not support per-file iteration.

**Option C: Return File List in Output**

A V1-specific approach could return the list of extracted files as a DataFrame:

```python
file_records = []
for member in archive.namelist():
    if not member.endswith('/'):
        file_records.append({
            'filename': os.path.basename(member),
            'filepath': os.path.join(output_directory, member),
            'size': archive.getinfo(member).file_size,
        })
return {'main': pd.DataFrame(file_records)}
```

This deviates from Talend behavior (which returns empty for main) but provides extracted file information for downstream processing without requiring iterate link support.

### Recommendation

Implement Option B as an immediate fix (simple, low-risk) and Option A as a longer-term solution once the iterate link infrastructure is verified.
