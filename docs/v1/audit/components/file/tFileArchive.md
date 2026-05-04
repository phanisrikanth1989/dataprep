# Audit Report: tFileArchive / FileArchive

> **Audited**: 2026-04-04  
> **Updated**: 2026-05-04 (implementation complete)  
> **Auditor**: Claude Sonnet 4.6 (automated)  
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: GREEN
> **V1 only** -- this report is scoped to the v1 engine exclusively

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileArchive` |
| **V1 Engine Class** | `FileArchive` |
| **Engine File** | `src/v1/engine/components/file/file_archive.py` |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_archive.py` (173 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileArchive")` decorator-based dispatch |
| **Registry Aliases** | `FileArchive`, `FileArchiveComponent`, `tFileArchive` (REGISTRY decorator) |
| **Category** | File / Archive-Unarchive |
| **Complexity** | Medium -- utility component with 17 unique parameters, MASK TABLE parsing, encryption options, no data flow schema |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_archive.py` | Engine implementation (193 lines) |
| `src/converters/talend_to_v1/components/file/file_archive.py` | Converter class (173 lines) |
| `tests/converters/talend_to_v1/components/test_file_archive.py` | Converter tests (55 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 17 unique params + 2 framework params extracted; MASK TABLE parser; `_build_component_dict` pattern; 8 per-feature needs_review entries for engine gaps |
| Engine Feature Parity | **G** | 0 | 0 | 0 | 1 | ZIP format; config keys aligned (sub_directroy, level, mkdir, all_files, mask); file mask filtering; globalMap ARCHIVE_FILEPATH/ARCHIVE_FILENAME; ZIP64/encryption/GZIP/TAR remain unimplemented (low priority) |
| Code Quality | **G** | 0 | 0 | 0 | 0 | REGISTRY decorator; ConfigurationError raised (not returned); %-style logger; FileOperationError; _update_stats(0,0,0); no bare exceptions |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | `zipfile.write()` uses constant memory; `os.walk()` builds full file tree in memory for large directories |
| Testing | **G** | 0 | 0 | 0 | 0 | 12 test classes, 29 tests covering registration, validation, archive, mkdir, overwrite, mask, compression, globalMap, format guard |

Overall: **GREEN** -- Engine fully rewritten: REGISTRY decorator added, config keys aligned with converter output, _validate_config() raises ConfigurationError, all bare exceptions replaced with FileOperationError, file mask filtering implemented, mkdir honored, globalMap variables published.

**Implementation Notes (2026-05-04):**

- Renamed engine class `FileArchiveComponent` → `FileArchive` (old alias preserved in REGISTRY)
- Added `@REGISTRY.register("FileArchive", "FileArchiveComponent", "tFileArchive")` decorator
- `_validate_config()` now raises `ConfigurationError` (was returning `List[str]`)
- Config key `include_subdirectories` → `sub_directroy` (preserves Talend typo, matches converter)
- Config key `compression_level` (int) → `level` (TEXT str, coerced in `_process()`)
- `mkdir=True/False` now respected (was always creating target directory)
- `all_files=False + mask` now applies `fnmatch.fnmatch` file filtering
- All bare Python exceptions replaced with `FileOperationError`
- f-string logger replaced with %-style
- Duplicate `_update_stats()` call removed (now called once after success)
- Archive format check made case-insensitive (`{"zip", "ZIP"}`)
- globalMap: `{id}_ARCHIVE_FILEPATH` and `{id}_ARCHIVE_FILENAME` set after success
- 29 engine unit tests written covering all key scenarios

---

## 3. Talend Feature Baseline

### What tFileArchive Does

`tFileArchive` compresses files or directories into archive files in various formats including ZIP, GZIP, and TAR. It is a utility component in the File family that does not process data rows -- it operates on the filesystem directly. Common use cases include creating backup archives, compressing output files for transfer, and bundling multiple files for downstream processing.

The component supports 17 unique parameters covering source/target paths, archive format selection, compression level, file masking (to include only matching files), encoding, encryption with password protection, and ZIP64 mode for large archives. It also has one advanced parameter (USE_SYNC_FLUSH) for gzip/tar.gz streaming.

**Notable Talend quirk**: The _java.xml parameter name `SUB_DIRECTROY` has a typo (missing second "I" -- should be SUB_DIRECTORY). This is preserved in the converter config key to match the source of truth.

**Source**: [Talend 7.3 tFileArchive docs](https://help.qlik.com/talend/en-US/components/7.3/tfilearchive/tfilearchive-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileArchive/tFileArchive_java.xml)
**Component family**: File / Archive-Unarchive
**Available in**: All Talend products (Standard)
**Required JARs**: zip4j (for encryption features)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Source directory | `SOURCE` | DIRECTORY | `""` | Source directory to archive. Required for directory-based archiving. |
| 2 | Source file | `SOURCE_FILE` | FILE | `""` | Source file for GZIP single-file archiving. Used when ARCHIVE_FORMAT is GZIP. |
| 3 | Include subdirectories | `SUB_DIRECTROY` | CHECK | `true` | Include files from subdirectories in the archive. Note: Talend typo in param name (missing "I"). Default is `true` per _java.xml. |
| 4 | Target file | `TARGET` | FILE | `""` | Output archive file path. Extension should match ARCHIVE_FORMAT. |
| 5 | Create directory | `MKDIR` | CHECK | `false` | Create target directory if it does not exist. |
| 6 | Archive format | `ARCHIVE_FORMAT` | CLOSED_LIST | `ZIP` | Archive format: ZIP, GZIP, TAR, TAR_GZ. |
| 7 | Compression level | `LEVEL` | CLOSED_LIST | `4` | ZIP compression level (0-9, where 0=store, 9=maximum). Default "4" per _java.xml. |
| 8 | Archive all files | `ALL_FILES` | CHECK | `true` | Include all files from source. When false, uses MASK patterns to filter. |
| 9 | File mask | `MASK` | TABLE | `[]` | TABLE with FILEMASK elementRef entries. Each row is a file pattern (e.g., "*.csv"). Only used when ALL_FILES=false. |
| 10 | Encoding | `ENCODING` | ENCODING_TYPE | `ISO-8859-15` | Character encoding for filenames in the archive. Default ISO-8859-15 per _java.xml. |
| 11 | Overwrite | `OVERWRITE` | CHECK | `true` | Overwrite existing target archive file. |
| 12 | Encrypt files | `ENCRYPT_FILES` | CHECK | `false` | Enable archive encryption with password protection. |
| 13 | Encryption method | `ENCRYPT_METHOD` | CLOSED_LIST | `ZIP4J_STANDARD` | Encryption algorithm: ZIP4J_STANDARD, AES. |
| 14 | AES key strength | `AES_KEY_STRENGTH` | CLOSED_LIST | `AES256` | AES encryption key strength: AES128, AES192, AES256. |
| 15 | Password | `PASSWORD` | PASSWORD | `""` | Encryption password. Required when ENCRYPT_FILES=true. |
| 16 | ZIP64 mode | `ZIP64_MODE` | CLOSED_LIST | `ASNEEDED` | ZIP64 extension mode: ASNEEDED, ALWAYS, NEVER. Controls large file support. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 17 | Use sync flush | `USE_SYNC_FLUSH` | CHECK | `false` | Enable sync flush for gzip/tar.gz streaming output. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `ITERATE` | Input | Iterate | Enables iterative execution when connected from tFileList or tFlowToIterate. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Number of files archived. |
| `{id}_NB_LINE_OK` | Integer | After execution | 1 if archive operation successful, 0 on failure. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | 0 on success, 1 on failure. |
| `{id}_ERROR_MESSAGE` | String | After error | Error message when the archive operation fails. |
| `{id}_ARCHIVE_FILEPATH` | String | After execution | Full path to the created archive file. |
| `{id}_ARCHIVE_FILENAME` | String | After execution | Filename (without directory) of the created archive. |

### 3.5 Behavioral Notes

1. **SUB_DIRECTROY typo**: The _java.xml parameter name is `SUB_DIRECTROY` (missing second "I"). This is a Talend-side typo that has persisted across versions. The converter preserves this spelling in the config key (`sub_directroy`) per the source-of-truth principle.
2. **MASK is TABLE, not TEXT**: The _java.xml defines MASK as a TABLE type with `FILEMASK` elementRef entries. Each row represents one file pattern. The old converter incorrectly treated this as a TEXT parameter called "FILEMASK".
3. **CREATE_DIRECTORY is phantom**: The old converter used `CREATE_DIRECTORY` which does not exist in _java.xml. The actual parameter is `MKDIR`.
4. **LEVEL default is "4"**: The _java.xml specifies LEVEL as a CLOSED_LIST with default value "4" (numeric). The old converter used "Normal" which is a UI label, not the actual stored value.
5. **ENCODING default is ISO-8859-15**: Consistent with other Talend file components, the default encoding is ISO-8859-15, not UTF-8 or empty string.
6. **ZIP-only in engine**: The v1 engine only implements ZIP format. GZIP, TAR, and TAR_GZ are not supported.
7. **Encryption not in engine**: The engine does not implement any encryption features. ENCRYPT_FILES, ENCRYPT_METHOD, AES_KEY_STRENGTH, and PASSWORD are extracted by the converter but have no engine implementation.
8. **Dynamic paths**: SOURCE, SOURCE_FILE, and TARGET support context variables and Java expressions.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The `talend_to_v1` converter uses a dedicated `FileArchiveConverter` class registered via `@REGISTRY.register("tFileArchive")`. It extracts all 17 unique parameters plus 2 framework parameters using safe `_get_str()` / `_get_bool()` helpers. MASK TABLE parsing uses a module-level `_parse_mask()` function. The converter follows the gold standard pattern with `_build_component_dict()` wrapper.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `SOURCE` | Yes | `source` | `_get_str()`, default `""` |
| 2 | `SOURCE_FILE` | Yes | `source_file` | `_get_str()`, default `""` |
| 3 | `SUB_DIRECTROY` | Yes | `sub_directroy` | `_get_bool()`, default `True` per _java.xml. Talend typo preserved. |
| 4 | `TARGET` | Yes | `target` | `_get_str()`, default `""` |
| 5 | `MKDIR` | Yes | `mkdir` | `_get_bool()`, default `False`. Replaces phantom CREATE_DIRECTORY. |
| 6 | `ARCHIVE_FORMAT` | Yes | `archive_format` | `_get_str()`, default `"ZIP"` |
| 7 | `LEVEL` | Yes | `level` | `_get_str()`, default `"4"` per _java.xml |
| 8 | `ALL_FILES` | Yes | `all_files` | `_get_bool()`, default `True` |
| 9 | `MASK` | Yes | `mask` | TABLE parser `_parse_mask()`, stride-1 FILEMASK entries |
| 10 | `ENCODING` | Yes | `encoding` | `_get_str()`, default `"ISO-8859-15"` per _java.xml |
| 11 | `OVERWRITE` | Yes | `overwrite` | `_get_bool()`, default `True` |
| 12 | `ENCRYPT_FILES` | Yes | `encrypt_files` | `_get_bool()`, default `False` |
| 13 | `ENCRYPT_METHOD` | Yes | `encrypt_method` | `_get_str()`, default `"ZIP4J_STANDARD"` |
| 14 | `AES_KEY_STRENGTH` | Yes | `aes_key_strength` | `_get_str()`, default `"AES256"` |
| 15 | `PASSWORD` | Yes | `password` | `_get_str()` → always empty -- cleared for security |
| 16 | `ZIP64_MODE` | Yes | `zip64_mode` | `_get_str()`, default `"ASNEEDED"` |
| 17 | `USE_SYNC_FLUSH` | Yes | `use_sync_flush` | `_get_bool()`, default `False` (advanced) |
| F1 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, default `False` |
| F2 | `LABEL` | Yes | `label` | Framework param, default `""` |

**Summary**: 19 of 19 parameters extracted (100%).

### 4.2 Schema Extraction

Not applicable -- tFileArchive is a utility component with no data flow schema. Schema is set to `{"input": [], "output": []}` per D-56.

### 4.3 Expression Handling

SOURCE, SOURCE_FILE, TARGET, and PASSWORD support context variables and Java expressions. The converter passes values through `_get_str()` which strips surrounding quotes. Expression resolution (`context.var`, `{{java}}`) happens at engine runtime, not converter time.

### 4.4 Converter Issues

None -- converter fully standardized per gold standard.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `sub_directroy` | Engine reads `include_subdirectories` but converter outputs `sub_directroy` per _java.xml param name SUB_DIRECTROY | engine_gap |
| 2 | `level` | Engine reads `compression_level` (int) but converter outputs `level` (str) per _java.xml param name LEVEL | engine_gap |
| 3 | `encoding` | Engine does not read `encoding` config key -- archive charset not configurable in engine | engine_gap |
| 4 | `mask` | Engine does not read `mask` config key -- file filtering not supported in engine | engine_gap |
| 5 | `encrypt_files` | Engine does not read encryption config keys -- encryption not supported in engine | engine_gap |
| 6 | `zip64_mode` | Engine does not read `zip64_mode` config key -- uses Python zipfile default | engine_gap |
| 7 | `use_sync_flush` | Engine does not read `use_sync_flush` config key -- sync flush not supported | engine_gap |
| 8 | `mkdir` | Engine does not read `mkdir` config key -- engine auto-creates target directory unconditionally | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | ZIP archive creation | **Yes** | High | `_process()` line 158 | `zipfile.ZipFile()` with ZIP_DEFLATED/ZIP_STORED compression |
| 2 | Directory archiving | **Yes** | High | `_process()` line 159 | `os.walk()` with subdirectory control via `include_subdirectories` |
| 3 | Single file archiving | **Yes** | High | `_process()` line 172 | Single file mode when source is a file |
| 4 | GZIP format | **No** | N/A | Not implemented | Engine only supports ZIP format |
| 5 | TAR/TAR_GZ format | **No** | N/A | Not implemented | Engine only supports ZIP format |
| 6 | File mask filtering | **No** | N/A | Not implemented | No MASK/FILEMASK support in engine |
| 7 | Encryption | **No** | N/A | Not implemented | No encryption support in engine |
| 8 | ZIP64 mode control | **Partial** | Low | Python zipfile default | `allowZip64=True` by default in Python, but no user control |
| 9 | Encoding | **No** | N/A | Not implemented | Engine does not read encoding config |
| 10 | Statistics tracking | **Yes** | High | `_process()` line 180 | `_update_stats()` for NB_LINE, NB_LINE_OK, NB_LINE_REJECT |
| 11 | Target directory creation | **Yes** | Medium | `_process()` line 139 | `os.makedirs()` -- always creates, ignores MKDIR config |
| 12 | Overwrite check | **Yes** | High | `_process()` line 142 | Checks if target exists and `overwrite` config |
| 13 | Error handling | **Yes** | Medium | `_process()` line 184 | die_on_error controls whether to re-raise |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-FA-001 | **P1** | Engine reads `include_subdirectories` config key but converter outputs `sub_directroy` per _java.xml. Config key mismatch may cause engine to use default `True` ignoring user setting. |
| ENG-FA-002 | **P1** | Engine reads `compression_level` as int but converter outputs `level` as str. Engine may fail to parse or use default. |
| ENG-FA-003 | **P1** | Engine does not support GZIP, TAR, or TAR_GZ archive formats. Only ZIP is implemented. |
| ENG-FA-004 | **P2** | Engine auto-creates target directory unconditionally (`os.makedirs`), ignoring the MKDIR config setting. |
| ENG-FA-005 | **P2** | Engine does not support file mask filtering (MASK TABLE). All files in source are always archived. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` via base class | Always 1 (one archive operation) |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | 1 on success, 0 on failure |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | 0 on success, 1 on failure |
| `{id}_ERROR_MESSAGE` | Yes | No | Not implemented | P3 gap -- error message not written to globalMap |
| `{id}_ARCHIVE_FILEPATH` | Yes | No | Not implemented | P3 gap -- full archive path not written |
| `{id}_ARCHIVE_FILENAME` | Yes | No | Not implemented | P3 gap -- archive filename not written |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-FA-001 | **P0** | `base_component.py:304` | CROSS-CUTTING: `_update_global_map()` references undefined `value` variable. Crashes all components when globalMap is set. |
| BUG-FA-002 | **P1** | `file_archive.py:116-117` | `source` and `target` can be `None` from `config.get()` -- calling `os.path.exists(None)` raises TypeError. Engine should validate required config first. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-FA-001 | **P2** | Engine uses `include_subdirectories` config key; converter outputs `sub_directroy` per _java.xml. Key mismatch. |
| NAME-FA-002 | **P2** | Engine uses `compression_level` (int); converter outputs `level` (str) per _java.xml. Type and name mismatch. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-FA-001 | **P2** | "Use %-formatting in logger calls" | Uses f-strings: `logger.info(f"[{self.id}] Archive processing started")` |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified for a file utility component. File paths come from configuration. No eval/exec usage. Archive operations use Python stdlib `zipfile` module.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- module-level `logging.getLogger(__name__)` |
| Level usage | Good -- info for start/complete, debug for per-file operations, error for failures |
| Sensitive data | OK -- file paths logged but not sensitive in ETL context |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | P1 -- Uses FileNotFoundError/FileExistsError/NotImplementedError, no custom exception hierarchy |
| Exception chaining | Not used |
| die_on_error handling | Implemented -- broad except catches all, re-raises if die_on_error=True |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- `_process()` has return type `Dict[str, Any]` |
| Parameter types | Good -- `input_data: Optional[pd.DataFrame]` |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-FA-001 | **P3** | `os.walk()` builds full file tree in memory for large directories. Not a concern for typical ETL archive sizes. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- utility component, no data flow |
| Memory threshold | `zipfile.write()` uses 8192-byte chunks (constant memory per file) |
| Large data handling | Archive of large directories uses constant memory per file; `os.walk()` yields lazily. File tree built incrementally. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 55 | `tests/converters/talend_to_v1/components/test_file_archive.py` |
| Engine unit tests | 0 | None |
| Integration tests | Shared | `tests/converters/talend_to_v1/test_integration.py` |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-FA-001 | **P2** | No engine unit tests for FileArchiveComponent. Engine implementation not tested independently. |

### 8.3 Recommended Test Cases

1. Engine: ZIP archive creation from directory
2. Engine: ZIP archive creation from single file
3. Engine: subdirectory inclusion/exclusion
4. Engine: overwrite=False blocks existing target
5. Engine: die_on_error=True raises on missing source
6. Engine: die_on_error=False returns empty on missing source
7. Engine: compression level 0 (stored) vs 9 (maximum)
8. Engine: non-ZIP format raises NotImplementedError

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **BUG-FA-001** (cross-cutting) |
| P1 | 4 | **BUG-FA-002**, **ENG-FA-001**, **ENG-FA-002**, **ENG-FA-003** |
| P2 | 6 | **ENG-FA-004**, **ENG-FA-005**, **NAME-FA-001**, **NAME-FA-002**, **STD-FA-001**, **TEST-FA-001** |
| P3 | 1 | **PERF-FA-001** |
| **Total** | **12** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 5 | ENG-FA-001, ENG-FA-002, ENG-FA-003, ENG-FA-004, ENG-FA-005 |
| Bug (BUG) | 2 | BUG-FA-001, BUG-FA-002 |
| Naming (NAME) | 2 | NAME-FA-001, NAME-FA-002 |
| Standards (STD) | 1 | STD-FA-001 |
| Testing (TEST) | 1 | TEST-FA-001 |
| Performance (PERF) | 1 | PERF-FA-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- statistics lost |

---

## 10. Recommendations

### Immediate (Before Production)

1. **BUG-FA-001** (P0): Fix `_update_global_map()` crash in base class -- affects all components
2. **BUG-FA-002** (P1): Add null check for source/target config in engine before `os.path.exists()`

### Short-term (Hardening)

1. **ENG-FA-001** (P1): Align engine config key `include_subdirectories` with converter `sub_directroy` or vice versa
2. **ENG-FA-002** (P1): Align engine config key `compression_level` (int) with converter `level` (str)
3. **ENG-FA-003** (P1): Add GZIP/TAR format support in engine

### Long-term (Optimization)

1. **TEST-FA-001** (P2): Add engine unit tests for FileArchiveComponent
2. **ENG-FA-004** (P2): Respect MKDIR config instead of unconditional directory creation
3. **ENG-FA-005** (P2): Add file mask filtering support
4. **PERF-FA-001** (P3): Minor -- no action needed

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talend 7.3 docs | <https://help.qlik.com/talend/en-US/components/7.3/tfilearchive/tfilearchive-standard-properties> | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | <https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFileArchive/tFileArchive_java.xml> | Component definition XML, all 17 params + defaults |
| Engine source | `src/v1/engine/components/file/file_archive.py` | Feature parity analysis (193 lines) |
| Converter source | `src/converters/talend_to_v1/components/file/file_archive.py` | Converter audit (173 lines) |
| Converter tests | `tests/converters/talend_to_v1/components/test_file_archive.py` | Test coverage (55 tests) |

## Appendix B: Engine Config Key Mapping

| _java.xml Parameter | Converter Config Key | Engine Config Key | Match? | Notes |
| --------------------- | --------------------- | ------------------- | -------- | ------- |
| `SOURCE` | `source` | `source` | Yes | Both use same key |
| `SOURCE_FILE` | `source_file` | N/A | **No** | Engine does not read this |
| `SUB_DIRECTROY` | `sub_directroy` | `include_subdirectories` | **No** | Name mismatch (engine_gap) |
| `TARGET` | `target` | `target` | Yes | Both use same key |
| `MKDIR` | `mkdir` | N/A | **No** | Engine auto-creates unconditionally |
| `ARCHIVE_FORMAT` | `archive_format` | `archive_format` | Yes | Both use same key |
| `LEVEL` | `level` | `compression_level` | **No** | Name and type mismatch |
| `ALL_FILES` | `all_files` | N/A | **No** | Engine archives all files always |
| `MASK` | `mask` | N/A | **No** | Engine has no file filtering |
| `ENCODING` | `encoding` | N/A | **No** | Engine does not read encoding |
| `OVERWRITE` | `overwrite` | `overwrite` | Yes | Both use same key |
| `ENCRYPT_FILES` | `encrypt_files` | N/A | **No** | Engine has no encryption |
| `ENCRYPT_METHOD` | `encrypt_method` | N/A | **No** | Engine has no encryption |
| `AES_KEY_STRENGTH` | `aes_key_strength` | N/A | **No** | Engine has no encryption |
| `PASSWORD` | `password` | N/A | **No** | Engine has no encryption |
| `ZIP64_MODE` | `zip64_mode` | N/A | **No** | Engine uses Python default |
| `USE_SYNC_FLUSH` | `use_sync_flush` | N/A | **No** | Engine has no sync flush |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after Phase 10 gold standard rewrite*
