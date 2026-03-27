# Audit Report: tFileArchive / FileArchiveComponent

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
| **Talend Name** | `tFileArchive` |
| **V1 Engine Class** | `FileArchiveComponent` |
| **Engine File** | `src/v1/engine/components/file/file_archive.py` (193 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_archive.py` |
| **Converter Dispatch** | `talend_to_v1` registry-based dispatch via `REGISTRY["tFileArchive"]` |
| **Registry Aliases** | `FileArchiveComponent`, `tFileArchive` (registered in `src/v1/engine/engine.py` lines 68-69) |
| **Category** | File / Archive-Unarchive |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/file/file_archive.py` | Engine implementation (193 lines) |
| `src/converters/talend_to_v1/components/file/file_archive.py` | Dedicated `talend_to_v1` converter for tFileArchive |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`FileOperationError`, `ConfigurationError`) |
| `src/v1/engine/components/file/__init__.py` | Package exports -- `FileArchiveComponent` exported at line 1 and in `__all__` at line 25 |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | `talend_to_v1` dedicated parser extracts 20 params (20 config keys). All runtime params mapped. LEVEL corrected to enum (Best/Normal/Fast). OVERWRITE default corrected to true. DIE_ON_ERROR default corrected to false. 6 engine-gap warnings documented. |
| Engine Feature Parity | **Y** | 0 | 4 | 3 | 1 | Only ZIP format; no gzip/tar.gz; no encryption; no filemask; no globalMap ARCHIVE_FILEPATH/ARCHIVE_FILENAME; ZIP64 works by default but no user control |
| Code Quality | **Y** | 2 | 4 | 5 | 2 | Cross-cutting base class bugs; `_validate_config()` never called; `None` source/target causes TypeError; `compression_level` not mapped to Python zipfile levels; TOCTOU on makedirs; partial corrupt ZIP on failure; `include_subdirectories` default divergence; no custom exception usage |
| Performance & Memory | **G** | 0 | 0 | 1 | 2 | `zipfile.write()` uses 8192-byte chunks (constant memory); `os.walk()` builds full file tree in memory; no parallel compression |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFileArchive Does

`tFileArchive` creates a new compressed archive file from one or more files or folders. It supports ZIP, gzip, and tar.gz archive formats with configurable compression levels, file filtering via mask patterns, encryption (password protection with multiple methods), ZIP64 mode for large archives, and encoding options. The component is a standalone file-operation component that does not produce data flow output -- it creates physical archive files on disk.

**Source**: [tFileArchive (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/archive-unarchive/tfilearchive), [tFileArchive Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/archive-unarchive/tfilearchive-standard-properties), [tFileArchive ESB 7.x (TalendSkill)](https://talendskill.com/talend-for-esb-docs/docs-7-x/tfilearchive-talend-open-studio-for-esb-document-7-x/)

**Component family**: Archive/Unarchive (File)
**Available in**: All Talend products (Standard)
**Required JARs**: `zip4j-*.jar` (when using Zip4j encryption methods)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Directory | `SOURCE` | Expression (String) | -- | **Required (for zip/tar.gz)**. Absolute path to the source directory containing the files to compress. Supports context variables and globalMap references. |
| 3 | Subdirectories | `SUB_DIRECTORY` | Boolean (CHECK) | `false` | Include subfolders and their files in the archive. Only applicable when archiving a directory in ZIP format. When unchecked, only top-level files in the source directory are archived. |
| 4 | Source File | `SOURCE_FILE` | Expression (String) | -- | **Required (for gzip)**. Individual file path to compress. Only visible/applicable when `ARCHIVE_FORMAT=gzip`. Replaces `Directory` field in gzip mode. |
| 5 | Archive File | `TARGET` | Expression (String) | -- | **Required**. Absolute path and filename for the destination archive file. Supports context variables and globalMap references. The file extension should match the archive format (.zip, .gz, .tar.gz). |
| 6 | Create Directory If Not Exist | `CREATE_DIRECTORY` | Boolean (CHECK) | `false` | Automatically create the destination directory if it does not exist. When unchecked, the component fails if the target directory is missing. |
| 7 | Archive Format | `ARCHIVE_FORMAT` | Dropdown (Enum) | `zip` | Format of the archive: `zip`, `gzip`, or `tar.gz`. Each format has different parameter visibility and behavior. |
| 8 | Compress Level | `LEVEL` | Dropdown (Enum) | `Normal` | Compression level applied to the archive. Options: `Best` (smallest file, slowest), `Normal` (balanced), `Fast` (no compression, fastest). Maps to `zipfile.ZIP_DEFLATED` levels 9/6/1 in Java. |
| 9 | All Files | `ALL_FILES` | Boolean (CHECK) | `true` | Include all files in the source directory. When unchecked, the `Filemask` field becomes visible to specify a file filter pattern. |
| 10 | Filemask | `FILEMASK` | String (regex) | -- | File filter pattern (regular expression or wildcard) to select specific files from the source directory. Only visible when `ALL_FILES=false`. Example: `.*\.csv` to archive only CSV files. |
| 11 | Encoding | `ENCODING` | Dropdown / Custom | Platform default | Character encoding for the archive. Compulsory when archiving database-related data. Only applicable to ZIP format. Options include UTF-8, ISO-8859-15, and custom values. |
| 12 | Overwrite Existing Archive | `OVERWRITE` | Boolean (CHECK) | `true` | Replace existing archive file at the target path. When unchecked and target exists, the component fails or skips depending on `DIE_ON_ERROR`. |
| 13 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `false` | Stop the entire job on error. When unchecked, the job continues even if the archive operation fails. |
| 14 | Encrypt Files | `ENCRYPT_FILES` | Boolean (CHECK) | `false` | Enable password protection for the archive. Only applicable to ZIP format. When enabled, `Encrypt method` and `Enter Password` fields become visible. |
| 15 | Encrypt Method | `ENCRYPT_METHOD` | Dropdown (Enum) | `Java Encrypt` | Encryption method: `Java Encrypt` (standard Java ZIP encryption), `Zip4j AES` (AES encryption via zip4j library), `Zip4j STANDARD` (standard ZIP encryption via zip4j). Only visible when `ENCRYPT_FILES=true`. |
| 16 | AES Key Strength | `AES_KEY_STRENGTH` | Dropdown (Enum) | `AES 256` | AES encryption key strength: `AES 128` or `AES 256`. Only visible when `ENCRYPT_METHOD=Zip4j AES`. |
| 17 | Enter Password | `PASSWORD` | Password (String) | -- | Encryption password entered via secure dialog. Only visible when `ENCRYPT_FILES=true`. |
| 18 | ZIP64 Mode | `ZIP64_MODE` | Dropdown (Enum) | `ASNEEDED` | ZIP64 extension mode: `ASNEEDED` (auto-detect based on file size), `ALWAYS` (force ZIP64), `NEVER` (disable ZIP64). Required when archive exceeds 4GB or contains 65,536+ files. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 19 | Use Sync Flush | `USE_SYNC_FLUSH` | Boolean (CHECK) | `false` | Flush the compressor before flushing the output stream. Only applicable to gzip and tar.gz formats. Ensures data is written immediately, useful for streaming scenarios. |
| 20 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 21 | Label | `LABEL` | String | -- | Text label for the component in Talend Studio designer canvas. No runtime impact. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input/Output | Row > Main | The component can accept incoming row data, but it does not process or transform it. Output is empty -- archive operation is file-based, not data-flow-based. |
| `REJECT` | Input/Output | Row > Reject | Available for connection but not meaningfully used -- the component produces files, not data rows. |
| `ITERATE` | Input/Output | Iterate | Enables iterative execution when used with iteration components like `tFlowToIterate` or `tFileList`. Common pattern: iterate over a list of directories and archive each one. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Used for chaining subjobs. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. More granular than SUBJOB_OK. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` | Input/Output (Trigger) | Trigger | Conditional trigger with a boolean expression. The target component only executes if the condition evaluates to true. |
| `SYNCHRONIZE` | Input (Trigger) | Trigger | Synchronizes execution with another subjob. The component waits until the triggering subjob completes. |
| `PARALLELIZE` | Input (Trigger) | Trigger | Enables parallel execution of this subjob alongside others. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_ARCHIVE_FILEPATH` | String | After execution | Full absolute path to the created archive file. Available for downstream components to reference the archive location. |
| `{id}_ARCHIVE_FILENAME` | String | After execution | Filename-only portion of the archive file (no directory path). Useful for logging and notifications. |
| `{id}_ERROR_MESSAGE` | String | On error | Error message if the archive operation failed. Available for reference in downstream error handling flows. |

**Note on NB_LINE**: Unlike data-flow components, `tFileArchive` does NOT produce `NB_LINE`, `NB_LINE_OK`, or `NB_LINE_REJECT` variables in standard Talend usage. The component operates on files, not rows. The v1 engine artificially sets `NB_LINE=1` to represent "one archive operation," which is a design choice that does not match Talend behavior.

### 3.5 Behavioral Notes

1. **Standalone component**: `tFileArchive` is designed to operate as a standalone component within jobs. It is not meant to be part of a data flow pipeline. It receives trigger connections (SUBJOB_OK, RUN_IF, etc.) but does not process row data.

2. **Archive format determines parameters**: The choice of `ARCHIVE_FORMAT` changes which parameters are visible and relevant:
   - **zip**: Uses `Directory`, `Subdirectories`, `All Files`, `Filemask`, `Encoding`, `Encrypt Files`, `ZIP64 Mode`
   - **gzip**: Uses `Source File` (single file only, not directory), `Use Sync Flush`
   - **tar.gz**: Uses `Directory`, `Subdirectories`, `All Files`, `Filemask`, `Use Sync Flush`

3. **gzip single-file limitation**: The gzip format can only compress a single file (not a directory). To archive multiple files with gzip, users typically first create a tar archive (via tar.gz) and then gzip it. The `Source File` parameter replaces the `Directory` parameter when gzip is selected.

4. **Compression levels**: The Talend compression levels map to Java's `Deflater` levels:
   - `Best` = `Deflater.BEST_COMPRESSION` (level 9) -- smallest file, slowest
   - `Normal` = `Deflater.DEFAULT_COMPRESSION` (level 6) -- balanced
   - `Fast` = `Deflater.NO_COMPRESSION` (level 0) -- no compression, fastest
   Note: Talend uses named levels (Best/Normal/Fast), NOT numeric 0-9 values.

5. **Encryption constraints**: Encrypted archives created with `tFileArchive` can ONLY be decompressed with `tFileUnarchive` -- standard archiving tools may not be able to open them, especially when using the `Java Encrypt` method. The `Zip4j AES` and `Zip4j STANDARD` methods produce more standard-compatible encrypted archives.

6. **ZIP64 mode**: Archives with more than 65,536 files or exceeding 4GB in total size require ZIP64 format. When `ZIP64_MODE=ASNEEDED`, Talend automatically detects whether ZIP64 is needed. When `ZIP64_MODE=NEVER` and the archive exceeds limits, the operation fails.

7. **Absolute paths required**: Both the source directory/file and the target archive path should use absolute paths. Relative paths can cause execution errors depending on the Talend runtime working directory.

8. **Empty source directory**: If the source directory exists but is empty (no files), the component creates an empty archive file. This is not an error condition.

9. **Filemask behavior**: When `ALL_FILES=false`, the `FILEMASK` parameter acts as a regular expression or wildcard filter on filenames within the source directory. Only files matching the mask are included in the archive.

10. **Overwrite behavior**: When `OVERWRITE=true` (default), any existing archive at the target path is silently replaced. When `OVERWRITE=false`, the component fails with an error (or continues silently if `DIE_ON_ERROR=false`).

11. **Create directory behavior**: When `CREATE_DIRECTORY=true`, the component creates any missing parent directories for the target archive path. When `false` (default), a missing target directory causes an error.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The `talend_to_v1` converter uses a dedicated parser (`src/converters/talend_to_v1/components/file/file_archive.py`) registered via `REGISTRY["tFileArchive"]`. The parser extracts all runtime parameters using safe `_get_str` / `_get_bool` helpers with null-safety and correct defaults.

**Converter flow**:
1. `talend_to_v1` registry dispatches to `file_archive.py` converter function
2. Extracts all runtime parameters using `_get_str()` and `_get_bool()` helpers (null-safe)
3. LEVEL corrected to enum labels (Best/Normal/Fast) instead of numeric values
4. OVERWRITE default corrected to `true`. DIE_ON_ERROR default corrected to `false`.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `SOURCE` | Yes | `source` | Null-safe extraction. |
| 2 | `TARGET` | Yes | `target` | Null-safe extraction. |
| 3 | `ARCHIVE_FORMAT` | Yes | `archive_format` | Default `zip`. |
| 4 | `SUB_DIRECTORY` | Yes | `include_subdirectories` | Boolean. Default `false`. |
| 5 | `OVERWRITE` | Yes | `overwrite` | Boolean. Default `true` -- matches Talend. |
| 6 | `LEVEL` | Yes | `compression_level` | Enum: `Best`/`Normal`/`Fast`. Default `Normal`. |
| 7 | `SOURCE_FILE` | Yes | `source_file` | For gzip mode. Engine-gap: gzip not yet implemented. |
| 8 | `CREATE_DIRECTORY` | Yes | `create_directory` | Boolean. Default `false`. |
| 9 | `ALL_FILES` | Yes | `all_files` | Boolean. Default `true`. Engine-gap: file filtering not yet implemented. |
| 10 | `FILEMASK` | Yes | `filemask` | String. Engine-gap: file filtering not yet implemented. |
| 11 | `ENCODING` | Yes | `encoding` | String. Default platform encoding. Engine-gap: encoding control not yet implemented. |
| 12 | `DIE_ON_ERROR` | Yes | `die_on_error` | Boolean. Default `false` -- matches Talend. |
| 13 | `ENCRYPT_FILES` | Yes | `encrypt_files` | Boolean. Default `false`. Engine-gap: encryption not yet implemented. |
| 14 | `ENCRYPT_METHOD` | Yes | `encrypt_method` | Enum. Engine-gap: encryption not yet implemented. |
| 15 | `AES_KEY_STRENGTH` | Yes | `aes_key_strength` | Enum. Engine-gap: encryption not yet implemented. |
| 16 | `PASSWORD` | Yes | `password` | String. Engine-gap: encryption not yet implemented. |
| 17 | `ZIP64_MODE` | Yes | `zip64_mode` | Enum. Default `ASNEEDED`. |
| 18 | `USE_SYNC_FLUSH` | Yes | `use_sync_flush` | Boolean. Default `false`. Engine-gap: not yet implemented. |
| 19 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Not needed at runtime. |
| 20 | `LABEL` | Yes | `label` | Not needed at runtime (cosmetic). |

**Summary**: 20 of 20 parameters extracted (100%). All runtime-relevant parameters correctly mapped. 6 engine-gap warnings documented for features not yet implemented in the engine.

> **Factual correction (2026-03-25)**: The original audit stated LEVEL was extracted as numeric string `'4'`. Talend uses named enum labels (`Best`/`Normal`/`Fast`), not numeric values. The `talend_to_v1` converter now extracts LEVEL as its enum label string.

### 4.2 Schema Extraction

Not applicable. `tFileArchive` is a file-operation component that does not process data rows or define an output schema. There is no FLOW or REJECT schema to extract.

### 4.3 Expression Handling

**Context variable handling**: The converter's `parse_tfilearchive()` extracts raw string values from XML. If the `SOURCE` or `TARGET` parameters contain context variables (e.g., `context.output_dir + "/backup.zip"`), they are stored as raw strings. The base class `execute()` method calls `context_manager.resolve_dict(self.config)` to resolve `${context.var}` patterns, but concatenated Java expressions (e.g., `context.output_dir + "/backup.zip"`) require the Java bridge.

**Java expression handling**: The base class `execute()` method calls `_resolve_java_expressions()` to resolve `{{java}}` markers. However, the converter's `parse_tfilearchive()` does NOT call `mark_java_expression()` on the extracted values. This means Java expressions in `SOURCE` or `TARGET` (very common in production Talend jobs) may not be properly detected and resolved.

**Known limitations**:
- The `parse_tfilearchive()` method does not invoke `mark_java_expression()` or `detect_java_expression()`. If the generic base `parse_base_component()` flow handles marking (because it processes all `elementParameter` nodes), these specific values extracted by `parse_tfilearchive()` may overwrite the marked versions with unmarked raw values.
- No validation that `source` or `target` expressions resolve to valid file paths after expression resolution.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FA-001 | ~~P1~~ | **FIXED (2026-03-25)**: `talend_to_v1` parser uses `_get_str()`/`_get_bool()` helpers with null-safety. No `AttributeError` risk. |
| CONV-FA-002 | ~~P1~~ | **FIXED (2026-03-25)**: `LEVEL` now extracted as enum label string (`Best`/`Normal`/`Fast`). Default `Normal`. |
| CONV-FA-003 | ~~P2~~ | **FIXED (2026-03-25)**: `OVERWRITE` default corrected to `true`, matching Talend. |
| CONV-FA-004 | ~~P2~~ | **FIXED (2026-03-25)**: `DIE_ON_ERROR` now extracted with default `false`, matching Talend. |
| CONV-FA-005 | ~~P2~~ | **FIXED (2026-03-25)**: `ALL_FILES` and `FILEMASK` now extracted. Engine-gap: file filtering not yet implemented in engine. |
| CONV-FA-006 | ~~P2~~ | **FIXED (2026-03-25)**: `ENCODING` now extracted. Engine-gap: encoding control not yet implemented in engine. |
| CONV-FA-007 | ~~P3~~ | **FIXED (2026-03-25)**: `ENCRYPT_FILES`, `ENCRYPT_METHOD`, `AES_KEY_STRENGTH`, `PASSWORD` now extracted. Engine-gap: encryption not yet implemented in engine. |
| CONV-FA-008 | ~~P3~~ | **FIXED (2026-03-25)**: `ZIP64_MODE` now extracted with default `ASNEEDED`. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Create ZIP archive from directory | **Yes** | High | `_process()` line 158-168 | Uses `zipfile.ZipFile` with `os.walk()`. Core functionality works. |
| 2 | Create ZIP archive from single file | **Yes** | High | `_process()` line 170-173 | Uses `archive.write(source, os.path.basename(source))`. Correct. |
| 3 | Include/exclude subdirectories | **Yes** | High | `_process()` line 162-163 | `dirs.clear()` when `include_subdirectories=False` prevents `os.walk()` from descending. Correct idiom. |
| 4 | Overwrite existing archive | **Yes** | High | `_process()` line 142-150 | Checks `os.path.exists(target) and not overwrite`. Correct. |
| 5 | Create target directory | **Partial** | Medium | `_process()` line 136-139 | Always creates directory with `os.makedirs()`. **Does not respect `CREATE_DIRECTORY` flag** -- Talend only creates when the flag is set. Engine unconditionally creates. |
| 6 | Die on error | **Yes** | Medium | `_process()` line 128-133, 185-193 | Implemented but **default differs from Talend** (engine defaults `True`, Talend defaults `false`). |
| 7 | Source path validation | **Yes** | High | `_process()` line 125-133 | `os.path.exists(source)` check with descriptive error. Correct. |
| 8 | Compression (ZIP_DEFLATED vs ZIP_STORED) | **Partial** | Low | `_process()` line 155 | Binary choice: `ZIP_DEFLATED` if level > 0, else `ZIP_STORED`. **Does not map numeric level to Python `compresslevel` parameter.** `zipfile.ZipFile` accepts a `compresslevel` parameter (0-9), but the engine ignores it. All non-zero levels produce identical compression. |
| 9 | Relative path preservation | **Yes** | High | `_process()` line 166 | `os.path.relpath(file_path, source)` preserves directory structure inside archive. Correct. |
| 10 | Statistics tracking | **Partial** | Low | `_process()` line 180 | Sets `NB_LINE=1, NB_LINE_OK=1, NB_LINE_REJECT=0` for success. **Talend does not set NB_LINE for file-operation components.** Artificial. |
| 11 | **gzip format** | **No** | N/A | -- | **Not implemented. Engine only supports ZIP. Talend supports gzip for single-file compression.** |
| 12 | **tar.gz format** | **No** | N/A | -- | **Not implemented. Talend supports tar.gz for directory compression with gzip.** |
| 13 | **File mask / filtering** | **No** | N/A | -- | **Not implemented. All files in source directory are always archived.** |
| 14 | **Encryption** | **No** | N/A | -- | **Not implemented. No password protection, no AES, no Java encryption.** |
| 15 | **ZIP64 mode** | **Partial** | High | -- | ZIP64 IS functionally enabled by default (`allowZip64=True` in Python's `zipfile`). Large archives work correctly. Only gap: no user control to force `ZIP64_MODE=NEVER`. |
| 16 | **Encoding** | **No** | N/A | -- | **Not implemented. No encoding control for archive file metadata.** |
| 17 | **`{id}_ARCHIVE_FILEPATH` globalMap** | **No** | N/A | -- | **Not set. Downstream components referencing the archive path via globalMap will get null.** |
| 18 | **`{id}_ARCHIVE_FILENAME` globalMap** | **No** | N/A | -- | **Not set.** |
| 19 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Error message not stored in globalMap.** |
| 20 | **Source File (gzip single-file mode)** | **No** | N/A | -- | **Not implemented. No `SOURCE_FILE` parameter for gzip mode.** |
| 21 | **Sync flush** | **No** | N/A | -- | **Not implemented. Only applicable to gzip/tar.gz which are not supported.** |
| 22 | **All Files toggle** | **No** | N/A | -- | **Not implemented. Always archives all files.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FA-001 | **P1** | **Only ZIP format supported**: Talend supports `zip`, `gzip`, and `tar.gz` archive formats. The v1 engine only supports `zip`. Jobs using gzip or tar.gz will hit the `NotImplementedError` on line 177: `"Archive format 'gzip' is not supported."` Python's standard library includes `tarfile` and `gzip` modules, so implementation is straightforward. |
| ENG-FA-002 | **P1** | **Compression level not actually applied**: The engine checks `compression_level > 0` to choose between `ZIP_DEFLATED` and `ZIP_STORED` (line 155), but does NOT pass the `compresslevel` parameter to `zipfile.ZipFile()`. Python's `zipfile.ZipFile` constructor accepts `compresslevel=N` (0-9) since Python 3.7. All non-zero compression levels produce identical output (default deflate). This means `compression_level=1` (fast) and `compression_level=9` (best) produce the same archive. |
| ENG-FA-003 | **P1** | **`{id}_ARCHIVE_FILEPATH` not set in globalMap**: This is the most commonly referenced globalMap variable for `tFileArchive`. Downstream components (e.g., `tSendMail` attaching the archive, `tFileCopy` moving it, `tLogRow` logging it) will receive null when referencing `((String)globalMap.get("tFileArchive_1_ARCHIVE_FILEPATH"))`. |
| ENG-FA-004 | **P1** | **`{id}_ARCHIVE_FILENAME` not set in globalMap**: Downstream references to the archive filename will fail. Common in email subject lines, log messages, and file management flows. |
| ENG-FA-005 | **P2** | **No file mask / filtering**: When `ALL_FILES=false` in Talend, only files matching the `FILEMASK` pattern are archived. The v1 engine always archives all files in the source directory. This can produce oversized archives containing unwanted files (e.g., temp files, logs, system files). |
| ENG-FA-006 | **P2** | **No encryption support**: Archives requiring password protection will be created without encryption. This is a security gap for jobs that archive sensitive data. |
| ENG-FA-007 | **P2** | **Target directory always created**: The engine unconditionally creates the target directory (line 139: `os.makedirs(target_dir)`). Talend only creates it when `CREATE_DIRECTORY=true`. This means the engine silently succeeds in cases where Talend would fail, potentially masking configuration errors. |
| ENG-FA-008 | **P3** | **No user control over ZIP64 mode**: ZIP64 IS functionally supported because Python's `zipfile` defaults to `allowZip64=True`. Large archives (>4GB, >65,536 files) work correctly out of the box. The gap is only the absence of `ZIP64_MODE=NEVER` support -- users cannot disable ZIP64 if Talend job specifies `NEVER`. This is a minor control gap, not a functional gap. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_ARCHIVE_FILEPATH` | Yes (official) | **No** | -- | **Not implemented.** Common downstream reference. |
| `{id}_ARCHIVE_FILENAME` | Yes (official) | **No** | -- | **Not implemented.** Common downstream reference. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | **Not implemented.** Error details lost. |
| `{id}_NB_LINE` | No (not official for file ops) | **Yes** | `_update_stats(1, 1, 0)` | V1-specific. Artificially set to 1. |
| `{id}_NB_LINE_OK` | No (not official for file ops) | **Yes** | Same mechanism | V1-specific. |
| `{id}_NB_LINE_REJECT` | No (not official for file ops) | **Yes** | Same mechanism | V1-specific. Always 0 on success. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FA-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FileArchiveComponent, since `_update_global_map()` is called after every component execution (via `execute()` line 218 and line 231 in exception handler). The exception handler path is particularly dangerous -- if the archive operation fails AND global_map is set, the `_update_global_map()` call on line 231 will raise `NameError`, masking the original archive error. |
| BUG-FA-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-FA-003 | **P1** | `src/v1/engine/components/file/file_archive.py:121` | **`compression_level` int() cast crashes on Talend named levels**: Line 121 does `compression_level = int(self.config.get('compression_level', self.DEFAULT_COMPRESSION_LEVEL))`. Talend XML stores compression levels as named strings like `"Normal"`, `"Best"`, or `"Fast"`. The `int()` cast will raise `ValueError` for any non-numeric string. Since the converter extracts `LEVEL` as a raw string (line 1672), and Talend uses named levels, this crash is likely in production for any job that sets a non-default compression level. |
| BUG-FA-004 | **P1** | `src/v1/engine/components/file/file_archive.py:155` | **`compresslevel` parameter not passed to `zipfile.ZipFile()`**: Line 155 calculates `compression = zipfile.ZIP_DEFLATED if compression_level > 0 else zipfile.ZIP_STORED`, but line 158 only passes `compression=compression`. The `compresslevel` parameter is never passed. Python `zipfile.ZipFile(target, 'w', compression=compression, compresslevel=N)` supports levels 0-9 since Python 3.7, but this code only distinguishes "any compression" from "no compression". All compressed archives are identical regardless of the configured level. |
| BUG-FA-005 | **P1** | `src/v1/engine/components/file/file_archive.py:66-95` | **`_validate_config()` is never called**: The method exists and contains validation logic for `source`, `target`, `archive_format`, and `compression_level`, but it is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Invalid configurations (missing source/target, unsupported format, out-of-range compression level) are not caught until they cause runtime errors deep in processing. |
| BUG-FA-006 | **P3** | `src/v1/engine/components/file/file_archive.py:185-193` | **Outer except block structure is fragile but double-counting does not manifest in practice**: ~~Previously claimed double `_update_stats()` calls corrupt stats.~~ On closer analysis: when `die_on_error=True`, the inner handlers (lines 128-129, 145-146) raise *before* calling `_update_stats()`, so the outer handler's `_update_stats(1, 0, 1)` is the only call -- no double-counting. When `die_on_error=False`, the inner handlers call `_update_stats()` and *return* (not raise), so the outer handler is never reached -- again no double-counting. The double-counting would only occur if an unexpected exception happens *after* an inner `_update_stats()` call but *before* the function returns (e.g., log formatting failure), which is a narrow latent risk, not a realistic bug. Downgraded from P1 to P3. |
| BUG-FA-007 | **P2** | `src/v1/engine/components/file/file_archive.py:174-177` | **Unsupported format raises `NotImplementedError` instead of custom exception**: Line 177 raises `NotImplementedError`, which is a Python built-in for abstract methods, not for unsupported features. Should use `ConfigurationError` from `exceptions.py` to match the project's exception hierarchy. The `NotImplementedError` is also not imported from the custom exceptions module -- it's the built-in Python exception. |
| BUG-FA-008 | **P2** | `src/v1/engine/components/file/file_archive.py:159-168` | **Empty source directory produces empty archive without warning**: When the source is an empty directory, `os.walk()` yields no files, `files_archived` remains 0, and the component creates an empty ZIP file. No warning is logged. The success log on line 181 reports `"0 files archived to {target}"`, but this could be confused with a legitimate empty directory. Talend creates an empty archive in this case too, but logging a warning would improve observability. |
| BUG-FA-009 | **P1** | `src/v1/engine/components/file/file_archive.py:116-117` | **`None` source/target causes `TypeError` not `FileNotFoundError`**: When `source` or `target` is not present in config, `self.config.get('source')` returns `None`. The subsequent `os.path.exists(None)` on line 125 raises `TypeError`, not `FileNotFoundError`. This bypasses the descriptive error handling on lines 125-133 and falls through to the generic outer except block, producing a confusing error message. `_validate_config()` would catch this, but it is dead code (never called -- see BUG-FA-005). |
| BUG-FA-010 | **P2** | `src/v1/engine/components/file/file_archive.py:136-139` | **TOCTOU race on `os.makedirs(target_dir)`**: Line 136 checks `if target_dir and not os.path.exists(target_dir)`, then line 139 calls `os.makedirs(target_dir)` without `exist_ok=True`. If another process creates the directory between the exists check and the makedirs call, `FileExistsError` is raised. Fix: use `os.makedirs(target_dir, exist_ok=True)` and remove the pre-check. |
| BUG-FA-011 | **P2** | `src/v1/engine/components/file/file_archive.py:158-173` | **Partial corrupt ZIP left on disk on failure**: When an exception occurs mid-write (e.g., I/O error partway through archiving files), the `zipfile.ZipFile` context manager closes the file, but the partially written archive remains on disk at the target path. No cleanup logic removes the corrupt partial archive. Downstream components or retry logic may encounter a corrupt ZIP. Should delete the partial file in the except handler or use a temporary file with atomic rename. |
| BUG-FA-012 | **P2** | `src/v1/engine/components/file/file_archive.py:119` | **`include_subdirectories` runtime default `True` differs from Talend default `false`**: Line 119 defaults to `self.config.get('include_subdirectories', True)`. Talend's `SUB_DIRECTORY` defaults to `false` (unchecked). This means jobs that omit the `SUB_DIRECTORY` parameter (relying on Talend default) will archive subdirectories when they should not, producing archives with unexpected extra files. This is a behavioral divergence, not just a docstring issue (cf. NAME-FA-001). |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FA-001 | **P2** | **`include_subdirectories` (v1) vs `SUB_DIRECTORY` (Talend)**: The v1 config key `include_subdirectories` is clearer and more descriptive than Talend's `SUB_DIRECTORY`. Acceptable naming divergence. However, the engine docstring (line 29) says `include_subdirectories (bool): Include subdirectories in archive. Default: True`, but the Talend default is `false` (unchecked). The docstring default does not match the Talend default, which could mislead developers. |
| NAME-FA-002 | **P3** | **`archive_format` (v1) vs `ARCHIVE_FORMAT` (Talend)**: Direct snake_case translation. Consistent. No issue. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FA-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists (lines 66-95) and correctly returns a list of error strings, but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-FA-002 | **P2** | "Use custom exceptions from `exceptions.py`" | `_process()` raises `FileNotFoundError` (line 129), `FileExistsError` (line 146), and `NotImplementedError` (line 177) -- all Python built-ins. Should use `FileOperationError` or `ConfigurationError` from `src/v1/engine/exceptions.py` for consistency with the project's exception hierarchy. The `exceptions.py` module defines `FileOperationError` specifically for file operation failures. |
| STD-FA-003 | **P3** | "Component docstring must document all config keys" | Docstring (lines 19-59) documents 7 config keys. Does not document `all_files`, `filemask`, `encoding`, `encrypt_files`, `encrypt_method`, `password`, `zip64_mode`. Understandable since these features are not implemented, but the docstring should note them as "not yet supported." |

### 6.4 Debug Artifacts

No debug artifacts, `print()` statements, or code generation comments found in `file_archive.py`. Clean.

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FA-001 | **P2** | **No path traversal protection on `source` or `target`**: Both `source` and `target` from config are used directly with `os.path.exists()`, `os.makedirs()`, and `zipfile.ZipFile()`. If config comes from untrusted sources, path traversal (`../../etc/passwd`) is possible. The `source` path is read (files are read and compressed), and `target` is a write path (archive is created). Write path traversal is particularly dangerous. Not a concern for Talend-converted jobs where config is trusted, but noted for defense-in-depth. |
| SEC-FA-002 | **P3** | **Symlink behavior is correct but undocumented**: ~~Previously claimed `os.walk()` follows symlinks by default -- this is incorrect.~~ `os.walk()` defaults to `followlinks=False`, meaning symlinks are NOT followed. The current code is safe. The only recommendation is to add an explicit `followlinks=False` parameter for documentation purposes, making the security-relevant default visible in the code. No functional issue. |

### 6.6 Logging Quality

The component has good logging throughout, following STANDARDS.md patterns:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start/complete, DEBUG for details, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 112) and completion with file count (line 181) -- correct |
| Sensitive data | No sensitive data logged -- correct. However, if encryption support is added, the password must NOT be logged. |
| No print statements | No `print()` calls -- correct |
| Files-archived count | Logs `files_archived` count in success message (line 181) -- excellent observability |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Does NOT use custom exceptions. Uses Python built-ins (`FileNotFoundError`, `FileExistsError`, `NotImplementedError`). Should use `FileOperationError` and `ConfigurationError`. |
| Exception chaining | Does NOT use `raise ... from e` pattern. The outer `except Exception as e` on line 185 uses bare `raise` (line 191), which is correct for re-raising, but internal error creation does not chain. |
| `die_on_error` handling | Two separate paths: source-not-found (line 128-133) and target-exists (line 142-150). Both correctly branch on `die_on_error`. The outer except block (line 185-193) also checks `die_on_error`, providing a catch-all fallback. |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID, file path, and error details -- correct |
| Graceful degradation | Returns empty DataFrame when `die_on_error=false` -- correct pattern |
| **Double stats update** | ~~Previously flagged as BUG~~. On closer analysis, the `die_on_error=True` path raises *before* `_update_stats()`, and the `die_on_error=False` path returns without reaching the outer handler. Double-counting does not manifest in realistic code paths. The outer except structure is fragile but functionally correct. See revised BUG-FA-006 (P3). |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_validate_config() -> List[str]` and `_process(...) -> Dict[str, Any]` have return type hints -- correct |
| Parameter types | `_process(self, input_data: Optional[pd.DataFrame] = None)` has parameter type hint -- correct |
| Missing type hints | Class constants `DEFAULT_COMPRESSION_LEVEL`, `DEFAULT_ARCHIVE_FORMAT`, `SUPPORTED_FORMATS` lack type annotations -- minor |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FA-001 | **P3** | **No explicit chunked streaming API used**: ~~Previously claimed that `zipfile.ZipFile.write()` reads the entire source file into memory. This is incorrect.~~ Python's `zipfile.write()` internally reads in 8192-byte chunks (`shutil.copyfileobj` semantics), so memory overhead is constant regardless of file size. The actual performance concern is limited to the overhead of Python-level I/O vs. a native implementation, which is negligible for most workloads. Downgraded from P1 to P3 -- no memory issue exists. |
| PERF-FA-002 | **P2** | **`os.walk()` builds complete file tree in memory**: For directories with millions of files, `os.walk()` stores the complete directory tree structure in memory. While this is the standard Python idiom and acceptable for most use cases, extremely large directory trees (millions of files) could consume significant memory. Python 3.12+ `os.walk()` is already lazy, but the `files` list for each directory is complete. |
| PERF-FA-003 | **P3** | **No parallel file compression**: Files are archived sequentially. For directories with many files, parallel compression could significantly reduce archive creation time. Low priority since `zipfile` does not natively support parallel writes, and the complexity of implementation outweighs the benefit for most use cases. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Not applicable -- this component does not process DataFrames. The base class streaming infrastructure is unused. |
| Large file handling | `zipfile.write()` reads in 8192-byte chunks internally. Memory overhead is constant. No large-file memory concern. |
| Directory enumeration | `os.walk()` is lazy (generator) for directory traversal, but file lists per directory are complete. |
| Archive size | No size limit checks. Archives exceeding 4GB without ZIP64 may produce corrupt files. |
| Temporary files | No temporary files created. Archive is written directly to target path. |

### 7.2 Edge Cases for Performance

| Scenario | Behavior | Risk |
|----------|----------|------|
| Empty source directory | Creates empty archive. Fast. | None |
| Source with 1 million files | `os.walk()` iterates all files sequentially. Slow but functional. | Medium -- could take hours for very large directories |
| Single 10GB file | `zipfile.write()` reads in 8192-byte chunks. Memory overhead is constant. | **Low** -- no `MemoryError` risk; I/O bound, not memory bound |
| Deeply nested directory (1000+ levels) | `os.walk()` handles recursion via iteration. No stack overflow. | None |
| Source directory on network share | `os.walk()` performance depends on network I/O. Each file read is a network call. | Medium -- very slow for many small files over network |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FileArchiveComponent` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter unit tests | **No** | -- | No tests for `parse_tfilearchive()` converter method |

**Key finding**: The v1 engine has ZERO tests for this component. All 193 lines of v1 engine code are completely unverified. The converter parser method (9 lines) is also untested.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic directory archive | P0 | Archive a directory with 3 files into a ZIP, verify ZIP contains all 3 files with correct contents |
| 2 | Single file archive | P0 | Archive a single file, verify ZIP contains the file with correct content and filename |
| 3 | Missing source + die_on_error=true | P0 | Should raise `FileNotFoundError` with descriptive message |
| 4 | Missing source + die_on_error=false | P0 | Should return empty DataFrame with stats (1, 0, 0) |
| 5 | Target exists + overwrite=false + die_on_error=true | P0 | Should raise `FileExistsError` |
| 6 | Target exists + overwrite=true | P0 | Should replace existing archive with new one |
| 7 | Statistics tracking | P0 | Verify `NB_LINE=1`, `NB_LINE_OK=1`, `NB_LINE_REJECT=0` are set correctly after successful execution |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Include subdirectories=true | P1 | Archive directory with nested subdirectories, verify all nested files are in ZIP |
| 9 | Include subdirectories=false | P1 | Archive directory with nested subdirectories, verify only top-level files are in ZIP |
| 10 | Target directory creation | P1 | Archive to a path where parent directories don't exist, verify directories are created |
| 11 | Empty source directory | P1 | Archive an empty directory, verify empty ZIP is created without error |
| 12 | Compression level 0 (ZIP_STORED) | P1 | Verify `compression_level=0` produces uncompressed ZIP (ZIP_STORED) |
| 13 | Compression level > 0 (ZIP_DEFLATED) | P1 | Verify `compression_level>0` produces compressed ZIP (ZIP_DEFLATED) |
| 14 | Context variable in source path | P1 | `${context.input_dir}` in source should resolve via context manager |
| 15 | Context variable in target path | P1 | `${context.output_dir}/backup.zip` in target should resolve via context manager |
| 16 | Named compression level (Normal/Best/Fast) | P1 | Verify engine handles Talend named levels without crashing (currently fails -- see BUG-FA-003) |
| 17 | Converter null-safety | P1 | Pass Talend XML with missing `SOURCE` parameter to `parse_tfilearchive()`, verify graceful error (currently crashes -- see CONV-FA-001) |
| 18 | Archive relative path preservation | P1 | Verify files in subdirectories maintain their relative paths inside the ZIP |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 19 | Very large file (>1GB) | P2 | Verify archiving a large file does not crash and produces valid ZIP |
| 20 | Many files (>1000) | P2 | Verify archiving a directory with many files works correctly |
| 21 | Unicode filenames | P2 | Verify files with non-ASCII names (Chinese, emoji, etc.) are correctly archived |
| 22 | Special characters in path | P2 | Verify source/target paths with spaces, parentheses, etc. work correctly |
| 23 | Symlink in source directory | P2 | Verify symlinks are handled correctly (not followed by default) |
| 24 | Concurrent archive operations | P2 | Multiple `FileArchiveComponent` instances archiving to different targets simultaneously |
| 25 | Source is a file, not directory | P2 | Verify `os.path.isdir()` correctly distinguishes file from directory and uses single-file path |
| 26 | Read-only target directory | P2 | Verify proper error when target directory is read-only |
| 27 | GlobalMap integration | P2 | Verify stats are written to globalMap after execution (currently blocked by BUG-FA-001/BUG-FA-002) |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FA-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. Particularly dangerous in the error handler path (line 231) where it masks the original error. |
| BUG-FA-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-FA-001 | Testing | Zero v1 unit tests for `FileArchiveComponent`. All 193 lines of engine code and 9 lines of converter code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FA-001 | Converter | **Null-safety crash on every `.find().get()` call**: All 6 extraction lines in `parse_tfilearchive()` use `node.find(...).get(...)` without null check. Missing XML parameter causes `AttributeError`. |
| CONV-FA-002 | Converter | **`LEVEL` extracted as numeric but Talend uses named levels**: Values like `"Normal"`, `"Best"`, `"Fast"` in XML will cause `ValueError` at `int()` cast in engine. |
| ENG-FA-001 | Engine | **Only ZIP format supported**: Talend supports `zip`, `gzip`, and `tar.gz`. Jobs using gzip or tar.gz raise `NotImplementedError`. Python `tarfile` and `gzip` modules available in stdlib. |
| ENG-FA-002 | Engine | **Compression level not actually applied**: `compresslevel` parameter not passed to `zipfile.ZipFile()`. All non-zero levels produce identical compression. |
| ENG-FA-003 | Engine | **`{id}_ARCHIVE_FILEPATH` not set in globalMap**: Most commonly referenced variable for this component. Downstream references get null. |
| ENG-FA-004 | Engine | **`{id}_ARCHIVE_FILENAME` not set in globalMap**: Downstream references to archive filename get null. |
| BUG-FA-003 | Bug | `compression_level` int() cast crashes on Talend named levels ("Normal", "Best", "Fast"). |
| BUG-FA-004 | Bug | `compresslevel` parameter not passed to `zipfile.ZipFile()`. Compression is binary (on/off), not graduated. |
| BUG-FA-005 | Bug | `_validate_config()` is dead code -- never called by any code path. 30 lines of unreachable validation. |
| BUG-FA-009 | Bug | `None` source/target causes `TypeError` not `FileNotFoundError`. `os.path.exists(None)` raises `TypeError`. `_validate_config()` is dead code so not caught early. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FA-003 | Converter | `OVERWRITE` default `'false'` differs from Talend default `true`. Jobs relying on Talend default will not overwrite existing archives. |
| CONV-FA-004 | Converter | `DIE_ON_ERROR` not extracted. Engine defaults to `True`, Talend defaults to `false`. Jobs expecting to continue past errors will halt. |
| CONV-FA-005 | Converter | `ALL_FILES` and `FILEMASK` not extracted. No file filtering. Jobs archiving subsets get all files. |
| CONV-FA-006 | Converter | `ENCODING` not extracted. Non-ASCII filenames may be garbled in archive. |
| ENG-FA-005 | Engine | No file mask / filtering. All files in source directory are always archived. |
| ENG-FA-006 | Engine | No encryption support. Security-sensitive archives created without protection. |
| ENG-FA-007 | Engine | Target directory unconditionally created. Talend only creates when `CREATE_DIRECTORY=true`. |
| BUG-FA-007 | Bug | Unsupported format raises `NotImplementedError` (Python abstract-method exception) instead of `ConfigurationError`. |
| BUG-FA-008 | Bug | Empty source directory produces empty archive without warning log. |
| BUG-FA-010 | Bug | TOCTOU on `os.makedirs(target_dir)` line 139 -- no `exist_ok=True`. Race condition if directory created between exists check and makedirs. |
| BUG-FA-011 | Bug | Partial corrupt ZIP left on disk when exception occurs mid-write. No cleanup of partially written archive on failure. |
| BUG-FA-012 | Bug | `include_subdirectories` runtime default `True` (line 119) differs from Talend default `false`. Behavioral divergence, not just docstring issue. |
| NAME-FA-001 | Naming | Engine docstring says `include_subdirectories` defaults to `True`, but Talend default is `false`. |
| STD-FA-001 | Standards | `_validate_config()` exists but is never called. Dead validation code. |
| STD-FA-002 | Standards | Uses Python built-in exceptions instead of custom `FileOperationError` / `ConfigurationError`. |
| SEC-FA-001 | Security | No path traversal protection on `source` or `target` config values. |
| PERF-FA-002 | Performance | `os.walk()` builds complete file lists per directory in memory. Millions of files could consume significant memory. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-FA-007 | Converter | `ENCRYPT_FILES` / `ENCRYPT_METHOD` / `PASSWORD` not extracted. No encryption support. |
| CONV-FA-008 | Converter | `ZIP64_MODE` not extracted. ZIP64 functionally works by default; gap is only `ZIP64_MODE=NEVER` support. |
| ENG-FA-008 | Engine | No user control over ZIP64 mode. ZIP64 IS functionally supported (`allowZip64=True` default). Gap is only `ZIP64_MODE=NEVER` support. |
| STD-FA-003 | Standards | Docstring does not document unimplemented config keys as "not yet supported." |
| SEC-FA-002 | Security | Symlink behavior is correct (`os.walk()` defaults to `followlinks=False`) but undocumented. Recommend explicit parameter for clarity. |
| PERF-FA-001 | Performance | ~~`zipfile.write()` loads entire file into memory~~ -- incorrect. Python reads in 8192-byte chunks. Constant memory overhead. No issue. Downgraded from P1. |
| PERF-FA-003 | Performance | No parallel file compression. Sequential archiving of many files. |
| BUG-FA-006 | Bug | Outer except block structure is fragile but double-counting does not manifest in realistic code paths. Downgraded from P1. |
| NAME-FA-002 | Naming | `archive_format` is clean snake_case of Talend `ARCHIVE_FORMAT`. Consistent. No issue. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 10 | 2 converter, 4 engine, 4 bugs (BUG-FA-003/004/005/009) |
| P2 | 17 | 4 converter, 3 engine, 5 bugs (BUG-FA-007/008/010/011/012), 1 naming, 2 standards, 1 security, 1 performance |
| P3 | 9 | 2 converter, 1 engine, 1 standards, 1 security, 2 performance (PERF-FA-001 downgraded, PERF-FA-003), 1 bug (BUG-FA-006 downgraded), 1 naming |
| **Total** | **39** | |

> **Changes from adversarial review**: +4 new bugs (BUG-FA-009 P1, BUG-FA-010 P2, BUG-FA-011 P2, BUG-FA-012 P2). BUG-FA-006 downgraded P1->P3 (double-counting does not manifest in realistic paths). PERF-FA-001 downgraded P1->P3 (`zipfile.write()` uses 8192-byte chunks, not full-file reads). ENG-FA-008 corrected (ZIP64 IS supported by default). SEC-FA-002 corrected (`os.walk` defaults to `followlinks=False`).

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FA-001): Change `value` to `stat_value` on `base_component.py` line 304. Alternatively, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FA-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-FA-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic directory archive, single file archive, missing source handling (both die_on_error modes), target-exists handling, overwrite behavior, and statistics tracking. Without these, no v1 engine behavior is verified.

4. **Add null checks to converter** (CONV-FA-001): Wrap each `.find().get()` call in `parse_tfilearchive()` with a null check:
   ```python
   source_node = node.find('.//elementParameter[@name="SOURCE"]')
   component['config']['source'] = source_node.get('value', '') if source_node is not None else ''
   ```
   Apply to all 6 extraction lines. **Impact**: Prevents converter crash on incomplete XML. **Risk**: Very low.

5. **Fix compression level mapping** (CONV-FA-002, BUG-FA-003): Add a mapping from Talend named levels to numeric values in either the converter or the engine:
   ```python
   LEVEL_MAP = {'Best': 9, 'Normal': 6, 'Fast': 0, 'best': 9, 'normal': 6, 'fast': 0}
   level_raw = self.config.get('compression_level', self.DEFAULT_COMPRESSION_LEVEL)
   compression_level = LEVEL_MAP.get(str(level_raw), int(level_raw) if str(level_raw).isdigit() else 6)
   ```
   **Impact**: Prevents `ValueError` crash. **Risk**: Low.

6. **Pass `compresslevel` to `zipfile.ZipFile()`** (BUG-FA-004, ENG-FA-002): Change line 158 from:
   ```python
   with zipfile.ZipFile(target, 'w', compression=compression) as archive:
   ```
   to:
   ```python
   with zipfile.ZipFile(target, 'w', compression=compression, compresslevel=compression_level) as archive:
   ```
   **Impact**: Compression level actually takes effect. **Risk**: Very low.

### Short-Term (Hardening)

7. **Set ARCHIVE_FILEPATH and ARCHIVE_FILENAME in globalMap** (ENG-FA-003, ENG-FA-004): After successful archive creation, add:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_ARCHIVE_FILEPATH", os.path.abspath(target))
       self.global_map.put(f"{self.id}_ARCHIVE_FILENAME", os.path.basename(target))
   ```
   Also set ERROR_MESSAGE on failure:
   ```python
   if self.global_map:
       self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))
   ```
   **Impact**: Enables downstream components to reference archive path/name. **Risk**: Very low.

8. **Add gzip and tar.gz support** (ENG-FA-001): Implement format dispatch:
   ```python
   if archive_format == 'zip':
       # existing ZIP logic
   elif archive_format == 'gzip':
       import gzip
       with open(source, 'rb') as f_in, gzip.open(target, 'wb', compresslevel=compression_level) as f_out:
           shutil.copyfileobj(f_in, f_out)
   elif archive_format in ('tar.gz', 'targz'):
       import tarfile
       with tarfile.open(target, 'w:gz') as tar:
           tar.add(source, arcname=os.path.basename(source))
   ```
   **Impact**: Full format parity with Talend. **Risk**: Medium (new code paths need testing).

9. **Extract `DIE_ON_ERROR` in converter** (CONV-FA-004): Add to `parse_tfilearchive()`:
   ```python
   die_node = node.find('.//elementParameter[@name="DIE_ON_ERROR"]')
   component['config']['die_on_error'] = die_node.get('value', 'false').lower() == 'true' if die_node is not None else False
   ```
   **Impact**: Correct error handling behavior. **Risk**: Very low.

10. **Fix OVERWRITE default** (CONV-FA-003): Change line 1671 default from `'false'` to `'true'` to match Talend default:
    ```python
    component['config']['overwrite'] = node.find('.//elementParameter[@name="OVERWRITE"]').get('value', 'true').lower() == 'true'
    ```
    **Impact**: Correct default behavior for overwrite. **Risk**: Very low.

11. **~~Fix double stats update~~ (BUG-FA-006 -- downgraded to P3)**: On closer analysis, the double-counting does not manifest in realistic code paths (see revised BUG-FA-006). The outer except block structure is fragile but functionally correct. Optional hardening: guard the outer handler's `_update_stats()` call:
    except Exception as e:
        if self.stats['NB_LINE'] == 0:  # Not yet counted
            self._update_stats(1, 0, 1)
    ```

12. **Wire up `_validate_config()`** (BUG-FA-005): Add a call at the beginning of `_process()`:
    ```python
    errors = self._validate_config()
    if errors:
        error_msg = "; ".join(errors)
        logger.error(f"[{self.id}] Configuration errors: {error_msg}")
        if die_on_error:
            raise ConfigurationError(error_msg)
        else:
            self._update_stats(1, 0, 0)
            return {'main': pd.DataFrame()}
    ```

### Long-Term (Optimization)

13. **Add file mask / filtering** (ENG-FA-005, CONV-FA-005): Extract `ALL_FILES` and `FILEMASK` in converter. In engine, filter files during `os.walk()`:
    ```python
    import re
    filemask = self.config.get('filemask', None)
    all_files = self.config.get('all_files', True)
    for root, dirs, files in os.walk(source):
        if not include_subdirectories:
            dirs.clear()
        for file in files:
            if not all_files and filemask and not re.match(filemask, file):
                continue
            # archive file
    ```

14. **Add encryption support** (CONV-FA-007, ENG-FA-006): Use Python `pyminizip` or `pyzipper` library for AES encryption. Map Talend's three encryption methods to Python equivalents. Low priority unless specific jobs require encrypted archives.

15. **Add ZIP64 mode control** (CONV-FA-008, ENG-FA-008): ZIP64 is already functionally supported (Python defaults to `allowZip64=True`). For explicit control, extract Talend's `ZIP64_MODE` in the converter and map it:
    ```python
    allow_zip64 = zip64_mode != 'NEVER'  # ASNEEDED and ALWAYS both allow ZIP64
    ```
    This only matters for jobs that set `ZIP64_MODE=NEVER` to force classic ZIP format.

16. **~~Add streaming for large files~~ (PERF-FA-001)**: No longer needed. Python's `zipfile.write()` already reads in 8192-byte chunks internally, so memory overhead is constant regardless of file size. The original claim that entire files are loaded into memory was incorrect. No code change required.

17. **Use custom exceptions** (STD-FA-002, BUG-FA-007): Replace `FileNotFoundError` with `FileOperationError`, `FileExistsError` with `FileOperationError`, and `NotImplementedError` with `ConfigurationError`.

18. **Add encoding support** (CONV-FA-006): Extract `ENCODING` in converter and use it in engine for archive metadata.

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 1665-1673
def parse_tfilearchive(self, node, component: Dict) -> Dict:
    """Parse tFileArchive specific configuration"""
    component['config']['source'] = node.find('.//elementParameter[@name="SOURCE"]').get('value', '')
    component['config']['target'] = node.find('.//elementParameter[@name="TARGET"]').get('value', '')
    component['config']['archive_format'] = node.find('.//elementParameter[@name="ARCHIVE_FORMAT"]').get('value', 'zip')
    component['config']['include_subdirectories'] = node.find('.//elementParameter[@name="SUB_DIRECTORY"]').get('value', 'false').lower() == 'true'
    component['config']['overwrite'] = node.find('.//elementParameter[@name="OVERWRITE"]').get('value', 'false').lower() == 'true'
    component['config']['compression_level'] = node.find('.//elementParameter[@name="LEVEL"]').get('value', '4')
    return component
```

**Notes on this code**:
- Line 1667-1672: All 6 lines use `node.find(...).get(...)` without null check. If `.find()` returns `None`, `.get()` causes `AttributeError`.
- Line 1671: Default `'false'` for `OVERWRITE` differs from Talend default `true`.
- Line 1672: Extracts `LEVEL` as numeric string `'4'`, but Talend uses named values (`"Normal"`, `"Best"`, `"Fast"`).
- No `DIE_ON_ERROR` extraction. Engine defaults to `True`, but Talend defaults to `false`.
- No extraction for `ALL_FILES`, `FILEMASK`, `ENCODING`, `ENCRYPT_FILES`, `ENCRYPT_METHOD`, `PASSWORD`, `ZIP64_MODE`, `SOURCE_FILE`, `CREATE_DIRECTORY`, `USE_SYNC_FLUSH`.

---

## Appendix B: Engine Class Structure

```
FileArchiveComponent (BaseComponent)
    Constants:
        DEFAULT_COMPRESSION_LEVEL = 4
        DEFAULT_ARCHIVE_FORMAT = 'zip'
        SUPPORTED_FORMATS = ['zip']

    Methods:
        _validate_config() -> List[str]          # DEAD CODE -- never called
        _process(input_data) -> Dict[str, Any]    # Main entry point -- archive creation logic

    Internal Flow (_process):
        1. Extract config with defaults (source, target, archive_format, include_subdirectories, overwrite, compression_level, die_on_error)
        2. Validate source exists (raise/return on missing)
        3. Create target directory if needed (always -- no CREATE_DIRECTORY flag check)
        4. Check target exists + overwrite flag (raise/return if exists and no overwrite)
        5. Create archive:
           - ZIP: zipfile.ZipFile with os.walk() for directories, single write for files
           - Other: raise NotImplementedError
        6. Update stats (1, 1, 0) on success
        7. Return {'main': pd.DataFrame()}
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `SOURCE` | `source` | Mapped | -- |
| `TARGET` | `target` | Mapped | -- |
| `ARCHIVE_FORMAT` | `archive_format` | Mapped | -- |
| `SUB_DIRECTORY` | `include_subdirectories` | Mapped | -- |
| `OVERWRITE` | `overwrite` | Mapped (wrong default) | P2 (fix default) |
| `LEVEL` | `compression_level` | Mapped (wrong format) | P1 (fix named levels) |
| `SOURCE_FILE` | `source_file` | **Not Mapped** | P1 (gzip mode) |
| `CREATE_DIRECTORY` | `create_directory` | **Not Mapped** | P2 |
| `ALL_FILES` | `all_files` | **Not Mapped** | P2 |
| `FILEMASK` | `filemask` | **Not Mapped** | P2 |
| `ENCODING` | `encoding` | **Not Mapped** | P2 |
| `DIE_ON_ERROR` | `die_on_error` | **Not Mapped** | P1 |
| `ENCRYPT_FILES` | `encrypt_files` | **Not Mapped** | P3 |
| `ENCRYPT_METHOD` | `encrypt_method` | **Not Mapped** | P3 |
| `AES_KEY_STRENGTH` | `aes_key_strength` | **Not Mapped** | P3 |
| `PASSWORD` | `password` | **Not Mapped** | P3 |
| `ZIP64_MODE` | `zip64_mode` | **Not Mapped** | P3 |
| `USE_SYNC_FLUSH` | `use_sync_flush` | **Not Mapped** | P3 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix D: Compression Level Mapping

### Talend Named Levels to Python zipfile

| Talend Level | Java Deflater Constant | Numeric Value | Python zipfile Equivalent |
|-------------|----------------------|---------------|---------------------------|
| `Best` | `Deflater.BEST_COMPRESSION` | 9 | `compresslevel=9` with `ZIP_DEFLATED` |
| `Normal` | `Deflater.DEFAULT_COMPRESSION` | 6 | `compresslevel=6` with `ZIP_DEFLATED` (Python default) |
| `Fast` (No compression) | `Deflater.NO_COMPRESSION` | 0 | `ZIP_STORED` (no compression) |

### Current V1 Engine Behavior

| `compression_level` config | Engine Behavior | Correct? |
|---------------------------|-----------------|----------|
| `0` | `ZIP_STORED` (no compression) | Correct |
| `1`-`9` | `ZIP_DEFLATED` (default compression level 6) | **Incorrect** -- all produce same output |
| `"Normal"` | `ValueError` crash at `int()` cast | **Bug** |
| `"Best"` | `ValueError` crash at `int()` cast | **Bug** |
| `"Fast"` | `ValueError` crash at `int()` cast | **Bug** |
| `None` (missing) | `DEFAULT_COMPRESSION_LEVEL=4` -> `ZIP_DEFLATED` (level 6) | Partially correct (uses level 6 instead of 4) |

---

## Appendix E: Detailed Code Analysis

### `_validate_config()` (Lines 66-95)

This method validates:
- `source` is present and non-empty (required) -- line 76
- `target` is present and non-empty (required) -- line 79
- `archive_format` is in `SUPPORTED_FORMATS` list -- line 83-85
- `compression_level` is a valid integer between 0 and 9 -- lines 87-93

**Not validated**: `include_subdirectories` type (should be bool), `overwrite` type (should be bool), `die_on_error` type (should be bool), `source` path existence (deferred to `_process()`), `target` parent directory writability.

**Critical**: This method is never called. Even if it were, no caller checks the returned error list or raises exceptions based on it. The validation is purely advisory, returning `List[str]`, but no code consumes the result.

### `_process()` (Lines 97-193)

The main processing method:
1. Log start (line 112)
2. Extract config values with defaults and type conversion (lines 116-122)
3. Validate source exists -- raise or return empty based on `die_on_error` (lines 124-133)
4. Create target directory if parent doesn't exist (lines 135-139)
5. Check target existence vs overwrite flag (lines 141-150)
6. Create archive based on format (lines 152-177):
   - ZIP: `zipfile.ZipFile` with `os.walk()` for directories, single `write()` for files
   - Other formats: `NotImplementedError`
7. Update stats (line 180) and log success (line 181)
8. Outer `except Exception as e` catches any unhandled error, logs it, updates stats, and re-raises or returns empty based on `die_on_error` (lines 185-193)

**Key code paths**:
- Success: `_update_stats(1, 1, 0)` -> return `{'main': pd.DataFrame()}`
- Source missing (die=True): raise `FileNotFoundError` (no `_update_stats` call before raise) -> outer `except` -> `_update_stats(1, 0, 1)` -> re-raise (correct, single stats call)
- Source missing (die=False): `_update_stats(1, 0, 0)` -> return `{'main': pd.DataFrame()}` (outer except not reached)
- Target exists (die=True): raise `FileExistsError` (no `_update_stats` call before raise) -> outer `except` -> `_update_stats(1, 0, 1)` -> re-raise (correct, single stats call)
- Target exists (die=False): `_update_stats(1, 0, 0)` -> return `{'main': pd.DataFrame()}`
- I/O error during archiving (die=True): outer `except` -> `_update_stats(1, 0, 1)` -> re-raise (correct)
- I/O error during archiving (die=False): outer `except` -> `_update_stats(1, 0, 1)` -> return `{'main': pd.DataFrame()}` (correct)

### ZIP Creation Logic (Lines 152-173)

```python
if archive_format == 'zip':
    compression = zipfile.ZIP_DEFLATED if compression_level > 0 else zipfile.ZIP_STORED

    with zipfile.ZipFile(target, 'w', compression=compression) as archive:
        if os.path.isdir(source):
            for root, dirs, files in os.walk(source):
                if not include_subdirectories:
                    dirs.clear()
                for file in files:
                    file_path = os.path.join(root, file)
                    archive_name = os.path.relpath(file_path, source)
                    archive.write(file_path, archive_name)
                    files_archived += 1
        else:
            archive.write(source, os.path.basename(source))
            files_archived = 1
```

**Analysis**:
- `dirs.clear()` on line 163 is the correct Python idiom for preventing `os.walk()` from descending into subdirectories. This modifies the list in-place, which `os.walk()` respects.
- `os.path.relpath(file_path, source)` on line 166 correctly computes the relative path for the archive entry name, preserving directory structure.
- `os.path.basename(source)` on line 172 for single files correctly uses just the filename without the directory path.
- `zipfile.ZipFile(target, 'w', compression=compression)` opens the archive for writing. The `'w'` mode truncates any existing file at `target`, which is correct since the overwrite check was already done.
- **Missing**: `compresslevel` parameter is not passed. `allowZip64` parameter is not explicitly set (Python default is `True`, which is correct).

---

## Appendix F: Edge Case Analysis

### NaN / None / Empty String Handling

| Scenario | Config Value | Engine Behavior | Risk |
|----------|-------------|-----------------|------|
| `source` is `None` | `self.config.get('source')` returns `None` | `os.path.exists(None)` raises `TypeError` | **P1** -- crashes engine (see BUG-FA-009) |
| `source` is `''` (empty string) | `self.config.get('source')` returns `''` | `os.path.exists('')` returns `False` | Handled by source validation (line 125) |
| `source` is `NaN` (float) | `self.config.get('source')` returns `NaN` | `os.path.exists(NaN)` raises `TypeError` | **P2** -- unlikely but unhandled |
| `target` is `None` | `self.config.get('target')` returns `None` | `os.path.dirname(None)` raises `TypeError` | **P1** -- crashes engine (see BUG-FA-009) |
| `target` is `''` (empty string) | `self.config.get('target')` returns `''` | `os.path.dirname('')` returns `''`, then `if target_dir` is `False`, skips makedirs | `zipfile.ZipFile('', 'w')` raises `FileNotFoundError` |
| `compression_level` is `None` | `int(None)` | `TypeError` | Handled by default `self.DEFAULT_COMPRESSION_LEVEL` in `.get()` |
| `compression_level` is `''` (empty string) | `int('')` | `ValueError` | **P2** -- unhandled |
| `compression_level` is `NaN` | `int(NaN)` | `ValueError` | **P2** -- unlikely but unhandled |
| `include_subdirectories` is not bool | `self.config.get(...)` returns string | Truthy check works for strings, but `'false'` (string) is truthy | **P2** -- converter handles bool conversion, but manual config could pass string |
| `archive_format` is `None` | Defaults to `'zip'` via `.get()` | Correct | None |
| `archive_format` is `''` (empty string) | Not in `SUPPORTED_FORMATS` | Hits `else` branch, raises `NotImplementedError` | Correct but wrong exception type |

### Empty Source Directory Behavior

When the source is an empty directory:
1. `os.path.exists(source)` returns `True` -- passes validation
2. `os.path.isdir(source)` returns `True` -- enters directory archiving path
3. `os.walk(source)` yields one tuple: `(source, [], [])` -- empty dirs and files
4. No files to archive, `files_archived` remains `0`
5. Empty ZIP file is created at `target`
6. Success log: `"0 files archived to {target}"`
7. `_update_stats(1, 1, 0)` -- reports success

**Assessment**: Behavior is correct (Talend also creates empty archives for empty directories), but a WARNING log would improve observability. Production operators seeing "0 files archived" may not realize the source was empty.

### Component Status Tracking

| Event | `self.status` Value | Set By |
|-------|---------------------|--------|
| Component created | `PENDING` | `BaseComponent.__init__()` line 86 |
| Execution starts | `RUNNING` | `execute()` line 192 |
| Successful completion | `SUCCESS` | `execute()` line 220 |
| Error occurs | `ERROR` | `execute()` line 228 |

**Note**: `_process()` does NOT update `self.status` directly. Status is managed entirely by the base class `execute()` method. This is correct -- `_process()` should focus on business logic, and `execute()` manages lifecycle.

### _update_global_map() Crash Scenario

When `global_map` is set (not None), the `_update_global_map()` method on `base_component.py:298-304` executes:

```python
def _update_global_map(self) -> None:
    if self.global_map:
        for stat_name, stat_value in self.stats.items():
            self.global_map.put_component_stat(self.id, stat_name, stat_value)
        logger.info(f"... {stat_name}: {value}")  # BUG: 'value' undefined
```

The `value` variable on line 304 is undefined. `stat_value` is the correct variable from the loop. This causes `NameError` on EVERY successful or failed execution when `global_map` is set.

**Impact on FileArchiveComponent**:
- Success path: `execute()` line 218 calls `_update_global_map()` -> `NameError` -> caught by `execute()` line 227 `except Exception` -> `self.status = ERROR` -> attempts `_update_global_map()` AGAIN on line 231 -> `NameError` again -> exception propagates up. **Archive file IS created** (it happened before the bug), but the component reports ERROR status.
- Error path: `execute()` line 231 calls `_update_global_map()` -> `NameError` -> masks the original archive error.

This cross-cutting bug means FileArchiveComponent (and ALL components) will always fail when `global_map` is set, regardless of whether the actual archive operation succeeded.

---

## Appendix G: Execution Flow Trace

### Successful Directory Archive (Happy Path)

```
1. Engine calls component.execute(input_data=None)
2. execute() sets self.status = RUNNING
3. execute() records start_time
4. execute() checks for java_bridge -> skips (None)
5. execute() checks for context_manager -> resolves ${context.var} in config
6. execute() determines mode = HYBRID -> _auto_select_mode(None) -> BATCH
7. execute() calls _execute_batch(None)
8. _execute_batch() calls _process(None)
9. _process() logs "[component_id] Archive processing started"
10. _process() extracts config:
    source = "/data/input"
    target = "/archives/backup.zip"
    archive_format = "zip"
    include_subdirectories = True
    overwrite = True
    compression_level = 4  (int cast -- can crash here)
    die_on_error = True
11. _process() checks os.path.exists(source) -> True
12. _process() checks target_dir exists, creates with os.makedirs() if needed
13. _process() checks target exists -> False (or True + overwrite=True -> proceed)
14. _process() opens zipfile.ZipFile(target, 'w', compression=ZIP_DEFLATED)
15. _process() iterates os.walk(source):
    For each (root, dirs, files):
        If not include_subdirectories: dirs.clear()
        For each file in files:
            file_path = os.path.join(root, file)
            archive_name = os.path.relpath(file_path, source)
            archive.write(file_path, archive_name)
            files_archived += 1
16. _process() calls _update_stats(1, 1, 0)
    -> stats = {NB_LINE: 1, NB_LINE_OK: 1, NB_LINE_REJECT: 0}
17. _process() logs "Archive processing complete: N files archived to /archives/backup.zip"
18. _process() returns {'main': pd.DataFrame()}
19. _execute_batch() returns the result
20. execute() updates stats['EXECUTION_TIME']
21. execute() calls _update_global_map()  <-- BUG: NameError on 'value'
22. [If global_map is None, step 21 is a no-op and continues]
23. execute() sets self.status = SUCCESS
24. execute() adds stats to result
25. execute() returns result dict
```

### Failed Archive (Source Missing, die_on_error=True)

```
1-9. Same as happy path
10. _process() extracts config (source = "/nonexistent/path")
11. _process() checks os.path.exists(source) -> False
12. _process() logs error "[id] Source path does not exist: /nonexistent/path"
13. _process() checks die_on_error = True
14. _process() raises FileNotFoundError("Source path does not exist: /nonexistent/path")
    -- NOTE: _update_stats(1, 0, 0) is NOT called for die_on_error=True path (line 128-129 raise immediately)
    -- WAIT: Actually line 128 checks die_on_error, and if True, raises on line 129.
    -- Lines 131-133 are the else branch (die_on_error=False).
    -- So for die_on_error=True, no _update_stats() call before the raise.
15. Exception propagates to outer except (line 185)
16. Outer except logs error
17. Outer except calls _update_stats(1, 0, 1)
    -> stats = {NB_LINE: 1, NB_LINE_OK: 0, NB_LINE_REJECT: 1}
18. Outer except checks die_on_error=True -> re-raises
19. Exception propagates to execute()'s except (line 227)
20. execute() sets self.status = ERROR
21. execute() stores error_message
22. execute() calls _update_global_map()  <-- BUG: NameError
23. execute() re-raises original exception (or NameError masks it)
```

**Correction to BUG-FA-006**: Upon closer inspection, the die_on_error=True path for source-missing does NOT call `_update_stats()` before raising. Only the die_on_error=False path calls `_update_stats(1, 0, 0)`. So the double-counting only occurs in the die_on_error=False path where the inner handler returns (not raises) -- and in that case, the outer except is NOT triggered. The double-counting actually occurs ONLY when an unexpected exception happens AFTER the inner `_update_stats` call but BEFORE the function returns. For example, if `_update_stats()` itself throws, or if line 181 (log formatting) throws. This narrows the bug but does not eliminate it -- it's a latent race condition.

### Failed Archive (Source Missing, die_on_error=False)

```
1-9. Same as happy path
10. _process() extracts config (source = "/nonexistent/path")
11. _process() checks os.path.exists(source) -> False
12. _process() logs error, logs warning
13. _process() checks die_on_error = False
14. _process() calls _update_stats(1, 0, 0)
    -> stats = {NB_LINE: 1, NB_LINE_OK: 0, NB_LINE_REJECT: 0}
15. _process() returns {'main': pd.DataFrame()}
16. _execute_batch() returns the result
17. execute() updates stats['EXECUTION_TIME']
18. execute() calls _update_global_map()  <-- BUG: NameError if global_map is set
19. execute() sets self.status = SUCCESS  (misleading -- operation failed but returned gracefully)
20. execute() returns result with stats
```

**Key observation**: When `die_on_error=False` and the source is missing, the component status is set to `SUCCESS` (line 220) because no exception was raised. This is technically correct (the component completed execution without exception), but semantically misleading. The stats show `NB_LINE_OK=0`, which is the correct signal that nothing was archived.

---

## Appendix H: Talend Behavior vs V1 Behavior Comparison Matrix

### Archive Format Behavior

| Scenario | Talend Behavior | V1 Behavior | Match? |
|----------|----------------|-------------|--------|
| Archive directory as ZIP | Creates ZIP with all files | Creates ZIP with all files | Yes |
| Archive directory as gzip | Error: gzip requires single file. Uses `SOURCE_FILE` instead. | `NotImplementedError` crash | No -- different error |
| Archive directory as tar.gz | Creates tar.gz with all files (supports subdirectories) | `NotImplementedError` crash | **No** |
| Archive single file as ZIP | Creates ZIP with single entry | Creates ZIP with single entry (basename only) | Yes |
| Archive single file as gzip | Creates .gz compressed file | `NotImplementedError` crash | **No** |
| Archive single file as tar.gz | Creates tar.gz with single entry | `NotImplementedError` crash | **No** |

### Compression Level Behavior

| Scenario | Talend Behavior | V1 Behavior | Match? |
|----------|----------------|-------------|--------|
| `LEVEL=Best` | Maximum compression (level 9) | `ValueError` crash | **No** |
| `LEVEL=Normal` | Default compression (level 6) | `ValueError` crash | **No** |
| `LEVEL=Fast` | No compression (level 0) | `ValueError` crash | **No** |
| `LEVEL` not set | Normal (level 6) | `DEFAULT_COMPRESSION_LEVEL=4` -> ZIP_DEFLATED (Python default 6) | Partial -- different default |
| Numeric level 0 | No compression | ZIP_STORED | Yes |
| Numeric level 1-9 | Graduated compression | ZIP_DEFLATED (default compression) | **No** -- all levels identical |

### Error Handling Behavior

| Scenario | Talend Behavior | V1 Behavior | Match? |
|----------|----------------|-------------|--------|
| Source missing, die=true | Job fails with error message | `FileNotFoundError` raised | Yes |
| Source missing, die=false | Job continues, no archive created | Returns empty DF, logs warning | Yes |
| Target exists, overwrite=true | Replaces existing archive | Replaces existing archive | Yes |
| Target exists, overwrite=false, die=true | Job fails | `FileExistsError` raised | Yes |
| Target exists, overwrite=false, die=false | Job continues, skips archive | Returns empty DF, logs warning | Yes |
| Unsupported format | Error in Talend Studio validation | `NotImplementedError` at runtime | Partial -- different timing |
| I/O error during archiving | Error based on die_on_error | Exception or empty DF based on die_on_error | Yes |

### GlobalMap Variable Behavior

| Variable | Talend Sets? | V1 Sets? | Match? |
|----------|-------------|----------|--------|
| `{id}_ARCHIVE_FILEPATH` | Yes -- full path to archive | No | **No** |
| `{id}_ARCHIVE_FILENAME` | Yes -- filename only | No | **No** |
| `{id}_ERROR_MESSAGE` | Yes -- error details | No | **No** |
| `{id}_NB_LINE` | No (not a data-flow component) | Yes (artificially set to 1) | **No** -- V1 adds non-Talend variable |
| `{id}_NB_LINE_OK` | No | Yes | **No** |
| `{id}_NB_LINE_REJECT` | No | Yes | **No** |
| `{id}_EXECUTION_TIME` | No | Yes (v1-specific) | N/A |

### File Selection Behavior

| Scenario | Talend Behavior | V1 Behavior | Match? |
|----------|----------------|-------------|--------|
| All files in directory | Archives all files | Archives all files | Yes |
| Filemask `.*\.csv` | Only CSV files archived | All files archived (no filter) | **No** |
| Filemask `report_.*` | Only matching files archived | All files archived | **No** |
| Include subdirectories=true | Recursively includes all nested files | Recursively includes all nested files | Yes |
| Include subdirectories=false | Only top-level files | Only top-level files (dirs.clear()) | Yes |
| Hidden files (e.g., `.gitignore`) | Included unless filemask excludes | Always included | Correct (matches ALL_FILES=true default) |
| Empty subdirectory | Empty directory entry in ZIP | **Not included** -- `os.walk()` only processes files, not empty dirs | **No** |

### Encryption Behavior

| Scenario | Talend Behavior | V1 Behavior | Match? |
|----------|----------------|-------------|--------|
| No encryption | Normal ZIP | Normal ZIP | Yes |
| Java Encrypt | Password-protected ZIP (Java-specific) | Not supported | **No** |
| Zip4j AES 256 | AES-256 encrypted ZIP | Not supported | **No** |
| Zip4j AES 128 | AES-128 encrypted ZIP | Not supported | **No** |
| Zip4j STANDARD | Standard ZIP encryption | Not supported | **No** |

---

## Appendix I: Converter Expression Handling Deep Dive

### How Talend XML Stores tFileArchive Parameters

In a Talend export XML, `tFileArchive` parameters appear as `elementParameter` nodes inside the component's `node` element:

```xml
<node componentName="tFileArchive" componentVersion="0.102" offsetLabelX="0" offsetLabelY="0" posX="352" posY="272">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="tFileArchive_1"/>
  <elementParameter field="DIRECTORY" name="SOURCE" value="context.inputDir + &quot;/data&quot;"/>
  <elementParameter field="FILE" name="TARGET" value="context.outputDir + &quot;/backup.zip&quot;"/>
  <elementParameter field="CLOSED_LIST" name="ARCHIVE_FORMAT" value="zip"/>
  <elementParameter field="CHECK" name="SUB_DIRECTORY" value="true"/>
  <elementParameter field="CHECK" name="OVERWRITE" value="true"/>
  <elementParameter field="CLOSED_LIST" name="LEVEL" value="Normal"/>
  <elementParameter field="CHECK" name="DIE_ON_ERROR" value="false"/>
  <elementParameter field="CHECK" name="ALL_FILES" value="true"/>
  <elementParameter field="TEXT" name="FILEMASK" value=""/>
  <elementParameter field="ENCODING_TYPE" name="ENCODING" value="UTF-8"/>
  <elementParameter field="CHECK" name="ENCRYPT_FILES" value="false"/>
  <elementParameter field="CLOSED_LIST" name="ZIP64_MODE" value="ASNEEDED"/>
</node>
```

### Converter Extraction Analysis

The `parse_tfilearchive()` method (lines 1665-1673) extracts parameters using XPath queries:

```python
node.find('.//elementParameter[@name="SOURCE"]').get('value', '')
```

This XPath query searches for ANY descendant `elementParameter` node with `name="SOURCE"`. The `.//` prefix means it searches all descendants, not just direct children. This is correct but slightly over-broad -- a direct child search (`./elementParameter[@name="SOURCE"]`) would be more precise and faster.

### Expression Types in tFileArchive

| Parameter | Likely Expression Type | Example Value in XML | Converter Handling |
|-----------|----------------------|---------------------|--------------------|
| `SOURCE` | Java expression with context vars | `context.inputDir + "/data"` | Extracted as raw string. No `{{java}}` marking. |
| `SOURCE` | Simple context variable | `context.inputDir` | Extracted as raw string. Base class `resolve_dict()` may handle `${context.var}` patterns. |
| `SOURCE` | Literal path | `"/data/input"` | Extracted as raw string with quotes. |
| `TARGET` | Java expression | `context.outputDir + "/backup_" + TalendDate.getDate("yyyyMMdd") + ".zip"` | Extracted as raw string. Java date routine NOT resolved. |
| `TARGET` | GlobalMap reference | `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH")) + ".zip"` | Extracted as raw string. GlobalMap reference NOT resolved. |
| `LEVEL` | Named enum | `"Normal"` | Extracted as `"Normal"`. Engine `int()` cast crashes. |
| `ARCHIVE_FORMAT` | Named enum | `"zip"` / `"gzip"` / `"tar.gz"` | Extracted as raw string. Only `"zip"` supported by engine. |

### Java Expression Resolution Gap

The converter's `parse_tfilearchive()` does NOT call the expression marking infrastructure (`mark_java_expression()`, `detect_java_expression()`, etc.). This means:

1. **Simple context variables** (`context.inputDir`): The base class `parse_base_component()` normally handles these by detecting `'context.' in value` and wrapping as `${context.var}`. But since `parse_tfilearchive()` is called INSTEAD of (not in addition to) `parse_base_component()`, context variables in `SOURCE` and `TARGET` may not be wrapped correctly.

2. **Java expressions** (`context.inputDir + "/data"`): The `mark_java_expression()` method is NOT called on these values. The base class `execute()` method calls `_resolve_java_expressions()` which looks for `{{java}}` prefixes, but since no values are marked, nothing is resolved.

3. **GlobalMap references** (`(String)globalMap.get("...")`): Not handled at all.

4. **Routine calls** (`TalendDate.getDate("yyyyMMdd")`): Not handled at all.

**Impact**: Any `tFileArchive` job where `SOURCE` or `TARGET` contains a Java expression (very common -- e.g., building archive paths with dates or context variables) will pass the raw Java expression string to `os.path.exists()`, which will always return `False`, causing the component to fail with "Source path does not exist: context.inputDir + \"/data\"".

**Mitigation**: The base class `execute()` method calls `self.context_manager.resolve_dict(self.config)` on line 202, which handles `${context.var}` patterns. If the converter wraps simple context variables correctly, those will resolve. But concatenated expressions and Java method calls will NOT resolve.

---

## Appendix J: Cross-Component Interaction Patterns

### Common Talend Patterns Using tFileArchive

#### Pattern 1: Archive After Data Processing

```
tFileInputDelimited -> tMap -> tFileOutputDelimited -> (OnSubjobOk) -> tFileArchive -> (OnSubjobOk) -> tSendMail
```

In this pattern, `tFileArchive` is triggered after a data processing subjob completes. It archives the output files, then triggers an email notification. The email often references `{id}_ARCHIVE_FILEPATH` to attach or link to the archive.

**V1 gaps**: `{id}_ARCHIVE_FILEPATH` not set in globalMap, so the email step cannot reference the archive path.

#### Pattern 2: Archive with File Iteration

```
tFileList -> (Iterate) -> tFileArchive
```

In this pattern, `tFileList` iterates over directories and `tFileArchive` archives each directory. The `SOURCE` parameter typically uses `((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))`.

**V1 gaps**: GlobalMap reference in `SOURCE` not resolved (Java expression handling gap).

#### Pattern 3: Archive with Date-Based Naming

```
tFileArchive  (TARGET = context.archiveDir + "/backup_" + TalendDate.getDate("yyyyMMdd") + ".zip")
```

**V1 gaps**: `TalendDate.getDate()` is a Java routine call that requires the Java bridge. Not marked as `{{java}}` by converter, so not resolved.

#### Pattern 4: Conditional Archive with tFileExist

```
tFileExist -> (RunIf: exists) -> tFileArchive
```

**V1 support**: This pattern works at the trigger level if the engine supports `RunIf` triggers. The archive operation itself works for basic ZIP operations.

### Downstream Component Dependencies on GlobalMap

| Downstream Component | GlobalMap Variable Used | Purpose | Impact of Missing Variable |
|---------------------|----------------------|---------|---------------------------|
| `tSendMail` | `{id}_ARCHIVE_FILEPATH` | Email attachment path | Email sent without attachment or with wrong path |
| `tLogRow` / `tJava` | `{id}_ARCHIVE_FILEPATH` | Audit logging | Log message contains null/empty |
| `tFileCopy` | `{id}_ARCHIVE_FILEPATH` | Copy archive to secondary location | Copy fails -- no source path |
| `tFileExist` | `{id}_ARCHIVE_FILEPATH` | Verify archive was created | Verification fails |
| `tJava` (custom) | `{id}_ARCHIVE_FILENAME` | Parse/use filename in custom logic | `NullPointerException` equivalent |
| `tWarn` / `tDie` | `{id}_ERROR_MESSAGE` | Error handling decisions | Error details lost |

---

## Appendix K: Comparison with tFileUnarchive Implementation

The v1 engine also implements `tFileUnarchive` as `FileUnarchiveComponent`. Comparing the two sibling components reveals consistency issues:

### Converter Comparison

| Aspect | `parse_tfilearchive()` | `parse_tfileunarchive()` |
|--------|----------------------|-------------------------|
| Null checks on `.find()` | None | None (same bug) |
| Parameters extracted | 6 of 18+ | 5 of ~12 |
| DIE_ON_ERROR extracted | No | No |
| Expression marking | No | No |

### Engine Comparison

| Feature | FileArchiveComponent | FileUnarchiveComponent |
|---------|---------------------|----------------------|
| Lines of code | 193 | ~200 (estimated) |
| Formats supported | ZIP only | ZIP only (likely) |
| `_validate_config()` called | No (dead code) | Unknown |
| Custom exceptions used | No (built-in only) | Unknown |
| GlobalMap variables set | NB_LINE only (artificial) | Unknown |
| Compression level handling | Binary (on/off) | N/A (decompression) |

**Recommendation**: Both components should be fixed simultaneously since they share the same converter pattern bugs (null-safety, expression handling) and likely the same engine pattern bugs.

---

## Appendix L: Production Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Converter crash on missing XML param | **High** -- Talend XML often omits default-valued params | **High** -- converter fails, entire job conversion blocked | Add null checks to all `.find().get()` calls |
| Named compression level crash | **Medium** -- only if job explicitly sets level | **High** -- runtime crash after archive file partially created | Add level name-to-number mapping |
| GlobalMap crash (cross-cutting) | **High** -- any job using globalMap | **Critical** -- ALL components fail; masks real errors | Fix `_update_global_map()` variable name |
| gzip/tar.gz format crash | **Medium** -- depends on job portfolio | **High** -- `NotImplementedError` at runtime | Implement gzip and tar.gz support |
| Missing ARCHIVE_FILEPATH | **High** -- most downstream patterns use it | **Medium** -- downstream components get null | Set variable after archive creation |
| Large file MemoryError | **Low** -- only for multi-GB individual files | **High** -- OOM crash | Implement streaming write |
| Wrong overwrite default | **Medium** -- depends on Talend job defaults | **Medium** -- unexpected FileExistsError | Fix converter default to `true` |
| Wrong die_on_error default | **High** -- many Talend jobs use default `false` | **High** -- jobs halt instead of continuing | Extract DIE_ON_ERROR in converter |

### Jobs Most Likely to Fail

1. **Jobs with Java expressions in SOURCE/TARGET**: Any job using `context.var + "/path"` or `TalendDate.getDate()` in source or target paths. These are the majority of production Talend jobs.

2. **Jobs using gzip or tar.gz**: Any job configured with `ARCHIVE_FORMAT=gzip` or `ARCHIVE_FORMAT=tar.gz`. These will crash with `NotImplementedError`.

3. **Jobs with filemask filtering**: Jobs that archive only specific files from a directory will archive ALL files instead, producing incorrect and potentially oversized archives.

4. **Jobs with encryption**: Security-sensitive jobs requiring password-protected archives will produce unencrypted archives, which is a data security risk.

5. **Jobs with downstream globalMap references**: Any job where subsequent components reference `{id}_ARCHIVE_FILEPATH` or `{id}_ARCHIVE_FILENAME` will fail or produce incorrect results.

### Jobs Most Likely to Succeed

1. **Simple ZIP archive of entire directory**: `SOURCE=/data/input`, `TARGET=/data/output.zip`, default compression, no filemask, no encryption.

2. **Simple ZIP archive of single file**: Same as above but source is a file, not directory.

3. **Jobs with literal (non-expression) paths**: Jobs where SOURCE and TARGET are hardcoded absolute paths without context variables or Java expressions.

---

## Appendix M: Recommended Implementation Priority

### Sprint 1: Critical Fixes (Estimated: 2-3 days)

| # | Task | Files Modified | Effort | Impact |
|---|------|---------------|--------|--------|
| 1 | Fix `_update_global_map()` `value` -> `stat_value` | `base_component.py` | 5 min | Unblocks ALL components |
| 2 | Fix `GlobalMap.get()` add `default` parameter | `global_map.py` | 5 min | Unblocks ALL GlobalMap usage |
| 3 | Add null checks to `parse_tfilearchive()` | `component_parser.py` | 30 min | Prevents converter crash |
| 4 | Add compression level name mapping | `file_archive.py` | 30 min | Prevents runtime crash |
| 5 | Pass `compresslevel` to `zipfile.ZipFile()` | `file_archive.py` | 5 min | Enables actual compression levels |
| 6 | Set ARCHIVE_FILEPATH/FILENAME in globalMap | `file_archive.py` | 15 min | Enables downstream references |
| 7 | Wire up `_validate_config()` | `file_archive.py` | 30 min | Catches config errors early |
| 8 | Write P0 unit tests (7 tests) | New test file | 2 hours | Validates all fixes |

### Sprint 2: Feature Parity (Estimated: 3-5 days)

| # | Task | Files Modified | Effort | Impact |
|---|------|---------------|--------|--------|
| 9 | Add gzip support | `file_archive.py` | 2 hours | Format parity |
| 10 | Add tar.gz support | `file_archive.py` | 2 hours | Format parity |
| 11 | Add file mask filtering | `file_archive.py`, `component_parser.py` | 2 hours | File selection parity |
| 12 | Extract DIE_ON_ERROR in converter | `component_parser.py` | 15 min | Correct error handling |
| 13 | Fix OVERWRITE default in converter | `component_parser.py` | 5 min | Correct default behavior |
| 14 | Add Java expression marking for SOURCE/TARGET | `component_parser.py` | 1 hour | Expression resolution |
| 15 | Write P1 unit tests (11 tests) | Test file | 3 hours | Validates new features |

### Sprint 3: Hardening (Estimated: 2-3 days)

| # | Task | Files Modified | Effort | Impact |
|---|------|---------------|--------|--------|
| 16 | Add encoding support | `file_archive.py`, `component_parser.py` | 1 hour | Non-ASCII filename support |
| 17 | Add ZIP64 explicit control | `file_archive.py`, `component_parser.py` | 1 hour | Large archive support |
| 18 | Fix double stats update | `file_archive.py` | 30 min | Correct stats |
| 19 | Use custom exceptions | `file_archive.py` | 30 min | Exception hierarchy consistency |
| 20 | Add streaming for large files | `file_archive.py` | 2 hours | Memory safety |
| 21 | Add CREATE_DIRECTORY flag | `file_archive.py`, `component_parser.py` | 30 min | Correct directory creation |
| 22 | Write P2 unit tests (9 tests) | Test file | 2 hours | Edge case coverage |
| 23 | Add encryption support (Zip4j) | `file_archive.py`, `component_parser.py` | 4 hours | Security feature |

---

## Appendix N: Line-by-Line Code Review of `_process()`

### Lines 112-122: Config Extraction

```python
logger.info(f"[{self.id}] Archive processing started")

try:
    source = self.config.get('source')          # Can be None
    target = self.config.get('target')          # Can be None
    archive_format = self.config.get('archive_format', self.DEFAULT_ARCHIVE_FORMAT)  # Defaults to 'zip'
    include_subdirectories = self.config.get('include_subdirectories', True)  # Default True != Talend False
    overwrite = self.config.get('overwrite', True)           # Default True matches Talend
    compression_level = int(self.config.get('compression_level', self.DEFAULT_COMPRESSION_LEVEL))  # int() crash risk
    die_on_error = self.config.get('die_on_error', True)     # Default True != Talend False
```

**Issues identified**:
- Line 116: `source` can be `None` if not in config. No guard before `os.path.exists(source)` on line 125. `os.path.exists(None)` raises `TypeError`.
- Line 117: Same issue for `target`. `os.path.dirname(None)` on line 136 raises `TypeError`.
- Line 119: `include_subdirectories` defaults to `True`, but Talend defaults to `false`. Docstring matches engine default, not Talend default.
- Line 121: `int()` cast on `compression_level`. If config contains `"Normal"` (Talend named level), `int("Normal")` raises `ValueError`. If config contains `None` (missing), `self.DEFAULT_COMPRESSION_LEVEL` (4) is used, which works.
- Line 122: `die_on_error` defaults to `True`, but Talend defaults to `false`. Converter does not extract this parameter, so this default always applies.

### Lines 124-133: Source Validation

```python
if not os.path.exists(source):
    error_msg = f"Source path does not exist: {source}"
    logger.error(f"[{self.id}] {error_msg}")
    if die_on_error:
        raise FileNotFoundError(error_msg)
    else:
        logger.warning(f"[{self.id}] Continuing with error, returning empty result")
        self._update_stats(1, 0, 0)
        return {'main': pd.DataFrame()}
```

**Issues**:
- Line 125: `os.path.exists(source)` -- if `source` is `None`, raises `TypeError`. If `source` is `NaN` (float), raises `TypeError`. If `source` is `''`, returns `False` (handled correctly).
- Line 129: Raises `FileNotFoundError` (built-in) instead of `FileOperationError` (custom).
- Line 132: `_update_stats(1, 0, 0)` -- sets `NB_LINE=1, NB_LINE_OK=0, NB_LINE_REJECT=0`. The 0 for `NB_LINE_REJECT` is technically wrong since the operation failed. Should be `_update_stats(1, 0, 1)` for consistency with the outer handler.

### Lines 135-139: Target Directory Creation

```python
target_dir = os.path.dirname(target)
if target_dir and not os.path.exists(target_dir):
    logger.debug(f"[{self.id}] Creating target directory: {target_dir}")
    os.makedirs(target_dir)
```

**Issues**:
- Line 136: `os.path.dirname(target)` -- if `target` is `None`, raises `TypeError`.
- Line 137: `if target_dir` -- correctly handles empty string case (when target is just a filename without directory).
- Line 139: `os.makedirs(target_dir)` -- no `exist_ok=True` parameter. If another process creates the directory between the `os.path.exists()` check and the `os.makedirs()` call, a race condition causes `FileExistsError`. Should use `os.makedirs(target_dir, exist_ok=True)`.
- No `CREATE_DIRECTORY` flag check -- always creates directory unconditionally.

### Lines 141-150: Target Existence Check

```python
if os.path.exists(target) and not overwrite:
    error_msg = f"Target archive already exists: {target}"
    logger.error(f"[{self.id}] {error_msg}")
    if die_on_error:
        raise FileExistsError(error_msg)
    else:
        logger.warning(f"[{self.id}] Skipping archive creation, target exists")
        self._update_stats(1, 0, 0)
        return {'main': pd.DataFrame()}
```

**Issues**:
- Line 146: Raises `FileExistsError` (built-in) instead of `FileOperationError` (custom).
- Line 149: Same `_update_stats(1, 0, 0)` pattern with 0 for reject. Should arguably be `_update_stats(1, 0, 1)`.
- TOCTOU race condition: between `os.path.exists(target)` (line 142) and `zipfile.ZipFile(target, 'w')` (line 158), another process could create or delete the file. Low risk for typical ETL workloads.

### Lines 152-173: Archive Creation

```python
files_archived = 0
if archive_format == 'zip':
    compression = zipfile.ZIP_DEFLATED if compression_level > 0 else zipfile.ZIP_STORED
    logger.debug(f"[{self.id}] Creating ZIP archive with compression level {compression_level}")

    with zipfile.ZipFile(target, 'w', compression=compression) as archive:
        if os.path.isdir(source):
            for root, dirs, files in os.walk(source):
                if not include_subdirectories:
                    dirs.clear()
                for file in files:
                    file_path = os.path.join(root, file)
                    archive_name = os.path.relpath(file_path, source)
                    archive.write(file_path, archive_name)
                    files_archived += 1
                    logger.debug(f"[{self.id}] Added file: {archive_name}")
        else:
            archive.write(source, os.path.basename(source))
            files_archived = 1
else:
    error_msg = f"Archive format '{archive_format}' is not supported. Supported formats: {self.SUPPORTED_FORMATS}"
    logger.error(f"[{self.id}] {error_msg}")
    raise NotImplementedError(error_msg)
```

**Issues**:
- Line 155: `compression_level > 0` -- binary decision. Does not pass `compresslevel=N` to `ZipFile`.
- Line 158: `zipfile.ZipFile(target, 'w', compression=compression)` -- missing `compresslevel` parameter.
- Line 162: `if not include_subdirectories: dirs.clear()` -- correct idiom.
- Line 167: `archive.write(file_path, archive_name)` -- internally reads in 8192-byte chunks. Memory overhead is constant regardless of file size.
- Line 169: DEBUG log for each file added. For directories with thousands of files, this produces thousands of debug log lines. Consider logging every 100th file or only at INFO level for totals.
- Line 172: `archive.write(source, os.path.basename(source))` -- correct single-file handling.
- Line 177: `raise NotImplementedError(error_msg)` -- wrong exception type.
- No empty directory entries are added to the archive. Talend may or may not add empty directory entries depending on the Java implementation.

### Lines 179-193: Completion and Error Handling

```python
self._update_stats(1, 1, 0)
logger.info(f"[{self.id}] Archive processing complete: {files_archived} files archived to {target}")
return {'main': pd.DataFrame()}

except Exception as e:
    logger.error(f"[{self.id}] Archive processing failed: {e}")
    self._update_stats(1, 0, 1)
    if self.config.get('die_on_error', True):
        raise
    else:
        return {'main': pd.DataFrame()}
```

**Issues**:
- Line 180: `_update_stats(1, 1, 0)` -- success path. Correct.
- Line 183: Returns `{'main': pd.DataFrame()}` -- empty DataFrame, correct for file-operation component.
- Line 187: `_update_stats(1, 0, 1)` -- error path. But if inner handlers already called `_update_stats(1, 0, 0)` (for die_on_error=False), the stats accumulate: `NB_LINE=2`. This is the double-counting bug.
- Line 190: `self.config.get('die_on_error', True)` -- re-reads config. Should use the `die_on_error` local variable from line 122 for consistency. If expression resolution changed the config between lines 122 and 190, this could produce different results (extremely unlikely but possible).
- Line 191: `raise` -- re-raises the original exception. Correct usage of bare `raise`.
- Line 193: Returns `{'main': pd.DataFrame()}` -- graceful degradation. Correct.

---

## Appendix O: Detailed Test Plan

### Test Infrastructure Requirements

| Requirement | Description |
|-------------|-------------|
| Test framework | `pytest` |
| Temporary directories | `pytest`'s `tmp_path` fixture for isolated file system operations |
| Test fixtures | Pre-populated directories with known files for repeatable archive tests |
| Assertions | `zipfile.ZipFile.namelist()` for verifying archive contents; `zipfile.ZipFile.read()` for content verification |
| Cleanup | Automatic via `tmp_path` (pytest handles cleanup) |

### P0 Test Case Details

#### TC-FA-001: Basic Directory Archive

```
Setup:
  - Create temp directory with 3 files: a.txt (10 bytes), b.csv (50 bytes), c.json (30 bytes)
Config:
  - source: temp_dir_path
  - target: temp_output/archive.zip
  - archive_format: zip
  - include_subdirectories: True
  - overwrite: True
  - compression_level: 4
Execute:
  - component.execute(None)
Assertions:
  - Return dict has 'main' key with empty DataFrame
  - archive.zip exists at target path
  - ZIP contains exactly 3 entries: a.txt, b.csv, c.json
  - Content of each entry matches original file content (byte-for-byte)
  - stats['NB_LINE'] == 1
  - stats['NB_LINE_OK'] == 1
  - stats['NB_LINE_REJECT'] == 0
  - component.status == ComponentStatus.SUCCESS
```

#### TC-FA-002: Single File Archive

```
Setup:
  - Create temp file: data.csv (100 bytes)
Config:
  - source: data.csv path
  - target: temp_output/data.zip
Execute:
  - component.execute(None)
Assertions:
  - ZIP contains exactly 1 entry: data.csv (basename only, no directory path)
  - Content matches original
```

#### TC-FA-003: Missing Source with die_on_error=True

```
Config:
  - source: /nonexistent/path/to/dir
  - target: temp_output/archive.zip
  - die_on_error: True
Execute:
  - Expect FileNotFoundError raised
Assertions:
  - Exception message contains "Source path does not exist"
  - archive.zip does NOT exist (not created)
  - component.status == ComponentStatus.ERROR
```

#### TC-FA-004: Missing Source with die_on_error=False

```
Config:
  - source: /nonexistent/path/to/dir
  - target: temp_output/archive.zip
  - die_on_error: False
Execute:
  - component.execute(None) -- no exception
Assertions:
  - Return dict has 'main' key with empty DataFrame
  - archive.zip does NOT exist
  - stats['NB_LINE'] == 1
  - stats['NB_LINE_OK'] == 0
```

#### TC-FA-005: Target Exists with overwrite=False and die_on_error=True

```
Setup:
  - Create temp source directory with files
  - Create existing archive.zip at target path
Config:
  - source: temp_dir
  - target: existing_archive.zip
  - overwrite: False
  - die_on_error: True
Execute:
  - Expect FileExistsError raised
Assertions:
  - Original archive.zip unchanged (not overwritten)
  - Exception message contains "Target archive already exists"
```

#### TC-FA-006: Target Exists with overwrite=True

```
Setup:
  - Create temp source directory with files
  - Create existing old_archive.zip at target path (with different contents)
Config:
  - source: temp_dir
  - target: old_archive.zip
  - overwrite: True
Execute:
  - component.execute(None)
Assertions:
  - archive.zip contains NEW files from source (not old contents)
  - stats['NB_LINE_OK'] == 1
```

#### TC-FA-007: Statistics Tracking

```
Setup:
  - Create temp directory with 5 files
Config:
  - source: temp_dir
  - target: archive.zip
Execute:
  - result = component.execute(None)
Assertions:
  - result['stats']['NB_LINE'] == 1
  - result['stats']['NB_LINE_OK'] == 1
  - result['stats']['NB_LINE_REJECT'] == 0
  - result['stats']['EXECUTION_TIME'] > 0
```

### P1 Test Case Details

#### TC-FA-008: Include Subdirectories True

```
Setup:
  - Create directory structure:
    root/
      file1.txt
      subdir1/
        file2.txt
        subsubdir/
          file3.txt
      subdir2/
        file4.txt
Config:
  - source: root
  - include_subdirectories: True
Execute:
  - component.execute(None)
Assertions:
  - ZIP contains 4 entries: file1.txt, subdir1/file2.txt, subdir1/subsubdir/file3.txt, subdir2/file4.txt
  - Directory structure is preserved in archive
```

#### TC-FA-009: Include Subdirectories False

```
Setup:
  - Same directory structure as TC-FA-008
Config:
  - source: root
  - include_subdirectories: False
Execute:
  - component.execute(None)
Assertions:
  - ZIP contains exactly 1 entry: file1.txt
  - No subdir files included
```

#### TC-FA-010: Target Directory Creation

```
Config:
  - source: temp_dir (exists, has files)
  - target: /nonexistent/deep/nested/dir/archive.zip (parent dirs don't exist)
Execute:
  - component.execute(None)
Assertions:
  - Directory /nonexistent/deep/nested/dir/ was created
  - archive.zip exists at target path
```

#### TC-FA-011: Empty Source Directory

```
Setup:
  - Create empty temp directory
Config:
  - source: empty_dir
  - target: archive.zip
Execute:
  - component.execute(None)
Assertions:
  - archive.zip exists and is a valid (empty) ZIP file
  - ZIP contains 0 entries
  - stats['NB_LINE_OK'] == 1 (operation succeeded)
```

### Regression Tests for Specific Bugs

#### TC-FA-REG-001: Compression Level "Normal" (BUG-FA-003)

```
Config:
  - compression_level: "Normal"
Expected (current): ValueError crash
Expected (after fix): Level mapped to 6, archive created with compresslevel=6
```

#### TC-FA-REG-002: Double Stats Update (BUG-FA-006)

```
Config:
  - source: /nonexistent
  - die_on_error: True
Expected (current): stats['NB_LINE'] may be 2 (double-counted)
Expected (after fix): stats['NB_LINE'] == 1
```

#### TC-FA-REG-003: None Source (Edge Case)

```
Config:
  - source: None (not set in config)
Expected (current): TypeError from os.path.exists(None)
Expected (after fix): ConfigurationError with message "Missing required config: 'source'"
```

#### TC-FA-REG-004: GlobalMap Integration

```
Setup:
  - Create GlobalMap instance
  - Create component with global_map=gm
Config:
  - source: temp_dir, target: archive.zip
Expected (current): NameError from _update_global_map() (BUG-FA-001)
Expected (after fix): GlobalMap contains {id}_ARCHIVE_FILEPATH, {id}_ARCHIVE_FILENAME
```

---

## Appendix P: Talend XML Sample and Conversion Walkthrough

### Sample Talend XML for tFileArchive

```xml
<node componentName="tFileArchive" componentVersion="0.102"
      offsetLabelX="0" offsetLabelY="0" posX="352" posY="272">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="tFileArchive_1"/>
  <elementParameter field="DIRECTORY" name="SOURCE"
    value="context.inputDir + &quot;/processed_data&quot;"/>
  <elementParameter field="FILE" name="TARGET"
    value="context.archiveDir + &quot;/backup_&quot; + TalendDate.getDate(&quot;yyyyMMdd&quot;) + &quot;.zip&quot;"/>
  <elementParameter field="CLOSED_LIST" name="ARCHIVE_FORMAT" value="zip"/>
  <elementParameter field="CHECK" name="SUB_DIRECTORY" value="true"/>
  <elementParameter field="CHECK" name="ALL_FILES" value="false"/>
  <elementParameter field="TEXT" name="FILEMASK" value=".*\.csv"/>
  <elementParameter field="CHECK" name="OVERWRITE" value="true"/>
  <elementParameter field="CLOSED_LIST" name="LEVEL" value="Best"/>
  <elementParameter field="CHECK" name="DIE_ON_ERROR" value="false"/>
  <elementParameter field="CHECK" name="ENCRYPT_FILES" value="true"/>
  <elementParameter field="CLOSED_LIST" name="ENCRYPT_METHOD" value="Zip4j AES"/>
  <elementParameter field="CLOSED_LIST" name="AES_KEY_STRENGTH" value="AES 256"/>
  <elementParameter field="PASSWORD" name="PASSWORD" value="encrypted:abc123"/>
  <elementParameter field="CLOSED_LIST" name="ZIP64_MODE" value="ASNEEDED"/>
  <elementParameter field="ENCODING_TYPE" name="ENCODING" value="UTF-8"/>
  <elementParameter field="CHECK" name="CREATE_DIRECTORY" value="true"/>
</node>
```

### Current Converter Output

```json
{
  "id": "tFileArchive_1",
  "type": "FileArchiveComponent",
  "config": {
    "source": "context.inputDir + \"/processed_data\"",
    "target": "context.archiveDir + \"/backup_\" + TalendDate.getDate(\"yyyyMMdd\") + \".zip\"",
    "archive_format": "zip",
    "include_subdirectories": true,
    "overwrite": true,
    "compression_level": "Best"
  }
}
```

### What Is Missing from Converter Output

| Parameter | Talend XML Value | Converter Extracts? | Impact |
|-----------|-----------------|---------------------|--------|
| `ALL_FILES` | `false` | No | All files archived instead of filtered subset |
| `FILEMASK` | `.*\.csv` | No | CSV-only filter lost |
| `DIE_ON_ERROR` | `false` | No | Engine defaults to `True` -- jobs halt instead of continuing |
| `ENCRYPT_FILES` | `true` | No | Archive created without encryption |
| `ENCRYPT_METHOD` | `Zip4j AES` | No | AES encryption lost |
| `AES_KEY_STRENGTH` | `AES 256` | No | AES-256 key strength lost |
| `PASSWORD` | `encrypted:abc123` | No | Password protection lost |
| `ZIP64_MODE` | `ASNEEDED` | No | Large archive support lost |
| `ENCODING` | `UTF-8` | No | Encoding control lost |
| `CREATE_DIRECTORY` | `true` | No | Engine always creates (matches this case by accident) |
| `LEVEL` | `Best` | Yes (as "Best") | Engine crashes on `int("Best")` |

### What Should Happen (Ideal Converter Output)

```json
{
  "id": "tFileArchive_1",
  "type": "FileArchiveComponent",
  "config": {
    "source": "{{java}}context.inputDir + \"/processed_data\"",
    "target": "{{java}}context.archiveDir + \"/backup_\" + TalendDate.getDate(\"yyyyMMdd\") + \".zip\"",
    "archive_format": "zip",
    "include_subdirectories": true,
    "overwrite": true,
    "compression_level": 9,
    "die_on_error": false,
    "all_files": false,
    "filemask": ".*\\.csv",
    "encoding": "UTF-8",
    "encrypt_files": true,
    "encrypt_method": "Zip4j AES",
    "aes_key_strength": "AES 256",
    "password": "abc123",
    "zip64_mode": "ASNEEDED",
    "create_directory": true
  }
}
```

### Key Differences

1. **`source` and `target`**: Should be prefixed with `{{java}}` marker so the Java bridge resolves `context.inputDir + "/processed_data"` and `TalendDate.getDate("yyyyMMdd")` at runtime.
2. **`compression_level`**: Should be converted from Talend named level `"Best"` to numeric `9`.
3. **`die_on_error`**: Should be extracted and set to `false`.
4. **All missing parameters**: Should be extracted from XML and included in config.
5. **`password`**: Should be decrypted from Talend's encrypted storage format (if applicable).
