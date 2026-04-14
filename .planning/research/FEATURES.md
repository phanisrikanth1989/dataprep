# Feature Research: Talend Component Feature Matrix

**Domain:** ETL engine component feature parity (Talend Open Studio replacement)
**Researched:** 2026-04-14
**Confidence:** HIGH (sourced from Talend _java.xml definitions, official Qlik/Talend docs, converter source code, engine source code, and 86-component audit reports)

---

## Feature Landscape

This document maps every configuration option, data flow pattern, and behavioral nuance for the 9 target Talend components. Features are categorized by criticality: Table Stakes (jobs break without them), Differentiators (edge-case features some jobs depend on), and Anti-Features (Talend behaviors to deliberately NOT replicate).

---

## 1. tFileInputDelimited

### Table Stakes

| Feature | Why Expected | Complexity | Current Engine Status |
|---------|--------------|------------|----------------------|
| File path with context variable resolution | Every job uses `context.filepath` | LOW | WORKING -- context_manager.resolve_dict() handles `${context.var}` |
| Configurable field delimiter (`;`, `,`, `\t`, multi-char, regex) | Core function of the component | LOW | PARTIAL -- engine reads `delimiter` key but converter outputs `fieldseparator`; config key mismatch |
| Header row skipping (`HEADER` count) | Most files have headers | LOW | WORKING |
| Footer row skipping (`FOOTER` count) | Some files have footers/trailers | LOW | WORKING |
| Row limit (`LIMIT`) | Testing/sampling jobs | LOW | WORKING |
| Schema enforcement (column names, types from output schema) | Type safety across pipeline | MEDIUM | WORKING -- `_build_dtype_dict()` maps Talend types to pandas dtypes |
| Text enclosure / quoting (`TEXT_ENCLOSURE`, `ESCAPE_CHAR`) | CSV fields with embedded delimiters | LOW | WORKING -- `_configure_csv_params()` handles doublequote vs escape modes |
| Encoding support (`ENCODING`, default ISO-8859-15) | Non-UTF8 files common in European orgs | LOW | PARTIAL -- engine defaults to UTF-8 but Talend defaults to ISO-8859-15; mismatch causes mojibake |
| Die on error control (`DIE_ON_ERROR`) | Graceful error handling in production | LOW | WORKING |
| Remove empty rows (`REMOVE_EMPTY_ROW`, default true) | Talend removes empties by default | LOW | WORKING |
| MAIN output flow (DataFrame) | Core data output | LOW | WORKING |
| GlobalMap variables (`NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT`) | Downstream components reference row counts | MEDIUM | PARTIAL -- base class `_update_global_map()` has crash bug (P0 XCUT-001) |
| Trim all columns (`TRIMALL`) | Data cleansing | LOW | WORKING |
| Streaming mode for large files (>3GB auto-switch) | Production files can be very large | MEDIUM | WORKING -- hybrid mode auto-switches |

### Differentiators

| Feature | Value Proposition | Complexity | Current Engine Status |
|---------|-------------------|------------|----------------------|
| REJECT output flow | Captures rows that fail schema validation (wrong field count, bad date, type mismatch); downstream error handling | HIGH | MISSING -- no reject flow support at all |
| CSV mode (`CSV_OPTION`) with RFC4180 compliance | Proper handling of quoted fields with embedded newlines/delimiters | MEDIUM | MISSING -- engine has no explicit CSV toggle |
| CSV row separator (`CSVROWSEPARATOR`) | Separate row separator when CSV mode active | LOW | MISSING -- engine ignores this parameter |
| Per-column trim (`TRIMSELECT` TABLE) | Trim specific columns, not all | MEDIUM | MISSING -- converter extracts it but engine ignores |
| Check fields number (`CHECK_FIELDS_NUM`) | Validate each row has correct column count; reject malformed rows | MEDIUM | MISSING -- engine does not validate row field count |
| Check date (`CHECK_DATE`) | Strict date format validation against schema patterns | MEDIUM | MISSING -- engine does not validate dates |
| Advanced numeric separators (`ADVANCED_SEPARATOR`, `THOUSANDS_SEPARATOR`, `DECIMAL_SEPARATOR`) | European number formats (1.000,50 vs 1,000.50) | MEDIUM | PARTIAL -- engine applies to all string columns, not just numeric |
| Compressed file reading (`UNCOMPRESS`) | Read from ZIP archives directly | MEDIUM | MISSING |
| Random sampling (`RANDOM`, `NB_RANDOM`) | Statistical sampling of large files | LOW | MISSING |
| Split record / multi-line fields (`SPLITRECORD`) | Records that span multiple lines | MEDIUM | MISSING |
| Hex/octal decoding (`ENABLE_DECODE`, `DECODE_COLS` TABLE) | Parse hex/octal values in specific columns | LOW | MISSING |
| Single-string read mode (empty delimiter + row_separator) | Read XML/document files as single string | LOW | WORKING -- special case in `_process()` |
| `{id}_FILENAME` and `{id}_ENCODING` globalMap variables | Downstream components access resolved filepath | LOW | MISSING |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Default encoding ISO-8859-15 | Talend European heritage | Most modern data is UTF-8; ISO-8859-15 default causes confusion and encoding bugs for non-European users | Default to UTF-8 in engine, but honor the explicit encoding from converted config |
| Default delimiter `;` (semicolon) | Talend convention | Industry standard is comma; converter already outputs the actual configured value so the engine default does not matter if config is always populated | Always read delimiter from config, never rely on engine default |

---

## 2. tMap

### Table Stakes

| Feature | Why Expected | Complexity | Current Engine Status |
|---------|--------------|------------|----------------------|
| Main input flow processing | Every tMap has a main input | LOW | WORKING |
| Lookup join (one or more lookups) | Core tMap use case -- data enrichment | HIGH | WORKING -- pandas merge with sequential lookup support |
| Join modes: INNER_JOIN, LEFT_OUTER_JOIN | Controls whether unmatched rows are kept | MEDIUM | WORKING |
| Matching modes: UNIQUE_MATCH, FIRST_MATCH, LAST_MATCH, ALL_MATCHES | Controls deduplication of lookup results | MEDIUM | PARTIAL -- UNIQUE_MATCH uses `keep='last'` but Talend uses first-row semantics |
| Variable definitions (intermediate computed values) | Reusable expressions across outputs | MEDIUM | WORKING -- evaluated via Java bridge |
| Output column expressions (Java expressions) | Core transformation logic | HIGH | WORKING -- compiled Java scripts via bridge |
| Multiple named output flows | Route different transformations of same data | MEDIUM | WORKING |
| Output filters (expression-based row filtering per output) | Conditional output routing | MEDIUM | WORKING |
| Reject output (`reject=true` on output table) | Capture rows that fail transformations | MEDIUM | WORKING -- basic reject flag detection |
| Inner join reject output (`rejectInnerJoin=true`) | Capture rows with no lookup match | MEDIUM | PARTIAL -- not differentiated from generic reject (ENG-MAP-013) |
| Input expression filters (main and lookup) | Pre-filter data before joins | MEDIUM | WORKING |
| Context variable access in expressions | Dynamic behavior from job parameters | LOW | WORKING -- context synced to Java bridge |
| GlobalMap access in expressions | Cross-component data sharing | LOW | WORKING -- globalMap synced to Java bridge |
| Die on error control | Error handling strategy | LOW | WORKING |
| Simple column reference optimization (no Java bridge needed) | Performance for `row1.col` style mappings | LOW | WORKING -- `SIMPLE_COLUMN_PATTERN` regex |
| Cartesian join (context-only expressions) | Cross-join filtered by context values | MEDIUM | WORKING |
| Chained lookups (Lookup2 references Lookup1 columns) | Sequential enrichment pipelines | MEDIUM | WORKING -- `joined_lookups` tracking |
| `{id}_NB_LINE` globalMap variable | Row count tracking | LOW | PARTIAL -- base class crash bug |

### Differentiators

| Feature | Value Proposition | Complexity | Current Engine Status |
|---------|-------------------|------------|----------------------|
| RELOAD_AT_EACH_ROW lookup mode | Re-execute lookup query per main row; needed for parameterized DB lookups | HIGH | MISSING -- always LOAD_ONCE |
| RELOAD_AT_EACH_ROW with cache | Same as above but caches previously seen lookup data | HIGH | MISSING |
| Disk-based lookup caching (`STORE_ON_DISK`, `ROWS_BUFFER_SIZE`) | Handle lookup tables larger than available RAM | HIGH | MISSING |
| Parallel lookup loading (`LKUP_PARALLELIZE`) | Load multiple lookups concurrently | MEDIUM | MISSING |
| Catch output reject (`activateCondensedTool`) | Capture rows that fail output expression evaluation | MEDIUM | MISSING |
| Auto type conversion between join columns (`ENABLE_AUTO_CONVERT_TYPE`) | Automatic String-to-Integer etc. for join keys | MEDIUM | MISSING |
| BigDecimal hash/equals (`CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL`) | Correct join behavior for 1.0 vs 1.00 | MEDIUM | MISSING |
| Fuzzy matching: Levenshtein distance threshold | Approximate string joins | HIGH | MISSING |
| Fuzzy matching: Jaccard similarity threshold | Approximate string joins | HIGH | MISSING |
| GlobalMap access from input/output tables (`activateGlobalMap`) | Store matched data in globalMap for iterate access | MEDIUM | MISSING |
| Persistent lookup (`persistent` attribute) | Keep lookup data between invocations (iterate reuse) | MEDIUM | MISSING |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| LINK_STYLE visual parameter | Visual editor rendering | Pure UI concern, zero runtime impact | Not extracted by converter (correct) |
| MAP external editor reference | Opens visual mapper in Talend Studio | UI-only, no runtime semantics | Not extracted by converter (correct) |
| `rows_buffer_size` for disk caching | Talend uses disk buffering for huge lookups | Python/pandas has different memory model; disk caching should use Python-native approaches (memory-mapped files, dask) | If needed, implement using Python-native tooling, not Talend's buffer approach |

---

## 3. tFileOutputDelimited

### Table Stakes

| Feature | Why Expected | Complexity | Current Engine Status |
|---------|--------------|------------|----------------------|
| File path with context variable resolution | Every output job uses context-driven paths | LOW | WORKING |
| Configurable field delimiter | Core function | LOW | PARTIAL -- engine default `,` but Talend default `;`; config key mismatch (`delimiter` vs `fieldseparator`) |
| Include header row (`INCLUDEHEADER`, default false) | Column names in output | LOW | PARTIAL -- engine defaults to True but Talend defaults to False |
| Append mode (`APPEND`) | Add to existing files | LOW | WORKING |
| Encoding support (`ENCODING`, default ISO-8859-15) | Match input encoding | LOW | PARTIAL -- engine defaults UTF-8, Talend defaults ISO-8859-15 |
| Create directory if not exists (`CREATE`, default true) | Auto-create output paths | LOW | WORKING |
| Text enclosure / CSV quoting | Quote fields containing delimiters | LOW | WORKING |
| Row separator (`ROWSEPARATOR`) | Platform-specific line endings | LOW | WORKING |
| Delete empty file (`DELETE_EMPTYFILE`) | Clean up zero-row outputs | LOW | WORKING |
| Empty data behavior (write header-only file) | Talend creates header-only file for empty input | LOW | WORKING |
| Pass-through of input data (output = input for chaining) | Downstream components need the data | LOW | WORKING |
| Schema-based column filtering and ordering | Output only specified columns in order | LOW | WORKING -- `_apply_output_schema()` |
| GlobalMap variables (`NB_LINE`, `NB_LINE_OK`) | Row count tracking | LOW | PARTIAL -- base class crash bug |
| Streaming mode for large datasets | Production files can be very large | MEDIUM | WORKING |
| Die on error control | Error handling | LOW | WORKING |

### Differentiators

| Feature | Value Proposition | Complexity | Current Engine Status |
|---------|-------------------|------------|----------------------|
| File splitting (`SPLIT`, `SPLIT_EVERY`) | Split large outputs into N-row files | MEDIUM | MISSING |
| Compression to ZIP (`COMPRESS`) | Reduce output file size | MEDIUM | MISSING |
| Output stream mode (`USESTREAM`, `STREAMNAME`) | Write to Java OutputStream for chaining | HIGH | MISSING |
| File exist exception (`FILE_EXIST_EXCEPTION`, default true) | Prevent accidental overwrites | LOW | MISSING |
| Row mode / per-row flush (`ROW_MODE`) | Atomic writes for multi-threaded safety | LOW | MISSING |
| Flush on row (`FLUSHONROW`, `FLUSHONROW_NUM`) | Buffer flush control | LOW | MISSING |
| OS line separator (`OS_LINE_SEPARATOR_AS_ROW_SEPARATOR`) | Use platform-native line endings | LOW | MISSING |
| CSV row separator (`CSVROWSEPARATOR`) as CLOSED_LIST (LF/CR/CRLF) | CSV-mode specific line endings | LOW | MISSING |
| Advanced numeric separators for output formatting | European number format in output | MEDIUM | MISSING |
| `{id}_FILE_NAME` globalMap variable | Downstream access to output filepath | LOW | MISSING |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Default delimiter `;` and default encoding ISO-8859-15 | Talend European heritage | Same issue as input -- engine should always read from config | Ensure engine reads config values, not defaults |
| Default `INCLUDEHEADER=false` | Talend convention | Most modern data pipelines expect headers; but must honor Talend config for parity | Read from config, do not assume engine default |

---

## 4. tJava

### Table Stakes

| Feature | Why Expected | Complexity | Current Engine Status |
|---------|--------------|------------|----------------------|
| Execute Java code once (not per-row) | Core function -- initialization, calculations, globalMap setup | MEDIUM | WORKING -- `execute_one_time_expression()` via Java bridge |
| Context variable access (`context.get(key)`) | Read job parameters | LOW | WORKING -- context synced to bridge before execution |
| GlobalMap access (`globalMap.put(key, value)`, `globalMap.get(key)`) | Set/read cross-component variables | LOW | WORKING -- globalMap synced bidirectionally |
| Import statements (`IMPORT` param) | Java library usage | LOW | MISSING -- engine only reads `java_code`, ignores `imports` |
| Bidirectional context/globalMap sync after execution | Changes in Java visible to subsequent Python components | MEDIUM | WORKING -- `_sync_from_java()` after execution |
| Pass-through of input data (if present) | tJava in middle of flow passes data through | LOW | WORKING |
| Die on error (implicit) | Job stops on Java execution failure | LOW | WORKING -- exception propagation |

### Differentiators

| Feature | Value Proposition | Complexity | Current Engine Status |
|---------|-------------------|------------|----------------------|
| `tstatcatcher_stats` integration | Send component stats to stat catcher | LOW | MISSING -- framework param not used by engine |
| Custom label for logging | Identify component in logs | LOW | MISSING |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Direct System.out.println in Java code | Java debugging convention | Bypasses Python logging infrastructure; output goes to subprocess stdout | Redirect Java stdout to Python logger |

---

## 5. tJavaRow

### Table Stakes

| Feature | Why Expected | Complexity | Current Engine Status |
|---------|--------------|------------|----------------------|
| Execute Java code per row | Core function -- row-level transformations | HIGH | WORKING -- `execute_java_row()` via Java bridge |
| Input row access (`input_row.get("column")`) | Read current row values | LOW | WORKING -- DataFrame serialized to Java via Arrow |
| Output row setting (`output_row.set("column", value)`) | Set output column values | LOW | WORKING |
| Output schema definition | Define output columns and types | LOW | WORKING -- converter generates `output_schema` |
| Import statements (`IMPORT` param) | Java library usage | LOW | MISSING -- engine only reads `java_code`, converter adds to code but engine ignores `imports` config key |
| Context and globalMap access | Read/write job parameters and cross-component vars | LOW | WORKING -- synced before execution |
| Type conversion of output values | Match schema types | MEDIUM | WORKING -- Java bridge handles type mapping |
| Statistics tracking (`NB_LINE`, `NB_LINE_OK`) | Row count tracking | LOW | WORKING |

### Differentiators

| Feature | Value Proposition | Complexity | Current Engine Status |
|---------|-------------------|------------|----------------------|
| REJECT output flow for per-row errors | Capture rows where Java code threw an exception | MEDIUM | MISSING in Java path (present in Python equivalent) |
| Parallel row execution (IntStream.parallel()) | Performance on multi-core | MEDIUM | WORKING -- Java bridge uses parallel streams |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| None identified | -- | -- | -- |

---

## 6. tContextLoad

### Table Stakes

| Feature | Why Expected | Complexity | Current Engine Status |
|---------|--------------|------------|----------------------|
| Load context from input DataFrame (key/value columns) | Most common pattern: upstream component provides context data | MEDIUM | WORKING |
| Load context from properties file (key=value format) | File-based context loading | LOW | WORKING |
| Load context from CSV file (key/value/type columns) | Structured context files | LOW | WORKING |
| Preserve original type when reloading (`get_type(key)`) | Type-safe context variables | LOW | WORKING |
| Print operations logging (`PRINT_OPERATIONS`) | Debugging context loading | LOW | WORKING |
| Error if file not exists (`ERROR_IF_NOT_EXISTS`) | Fail-fast for missing config | LOW | WORKING |
| GlobalMap variable `{id}_NB_CONTEXT_LOADED` | Track how many variables loaded | LOW | WORKING |

### Differentiators

| Feature | Value Proposition | Complexity | Current Engine Status |
|---------|-------------------|------------|----------------------|
| Die on error control (`DIE_ON_ERROR`) | Continue despite errors | LOW | MISSING -- engine always raises on error |
| Load new variable policy (`LOAD_NEW_VARIABLE`: WARNING/ERROR/NO_WARNING) | Control behavior when flow contains keys not in job context | MEDIUM | MISSING -- engine loads all keys unconditionally |
| Not load old variable policy (`NOT_LOAD_OLD_VARIABLE`: WARNING/ERROR/NO_WARNING) | Control behavior when context key not in flow | MEDIUM | MISSING -- engine does not validate |
| Disable warnings/errors/info (`DISABLE_WARNINGS`, `DISABLE_ERROR`, `DISABLE_INFO`) | Message level filtering per component | LOW | MISSING -- engine has no per-component log filtering |
| Implicit context load (job-level `CONTEXTFILE`, `FORMAT`, `FIELDSEPARATOR`) | Load context automatically before job starts | HIGH | MISSING -- these are job-level settings, not component-level |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| None identified | -- | -- | -- |

---

## 7. tFlowToIterate

### Table Stakes

| Feature | Why Expected | Complexity | Current Engine Status |
|---------|--------------|------------|----------------------|
| Convert each input row to globalMap variables | Core function -- bridge between flow and iterate patterns | HIGH | MISSING -- no engine implementation exists |
| Default mapping mode (`DEFAULT_MAP=true`): store as `{flowName}.{columnName}` in globalMap | Automatic variable naming convention | MEDIUM | MISSING |
| Custom mapping mode (`DEFAULT_MAP=false`): user-defined key-value pairs from MAP TABLE | Explicit variable naming | MEDIUM | MISSING -- converter extracts `map_entries` but no engine |
| ITERATE output connector triggering downstream subjobs | Each row triggers one iteration of downstream components | HIGH | MISSING -- engine execution loop has no iterate re-execution logic |
| Row-by-row iteration (not batch) | Downstream sees one row at a time via globalMap, not a DataFrame | MEDIUM | MISSING |
| `{id}_CURRENT_ITERATE` globalMap variable | Track current iteration index | LOW | MISSING |

### Differentiators

| Feature | Value Proposition | Complexity | Current Engine Status |
|---------|-------------------|------------|----------------------|
| `tstatcatcher_stats` integration | Stats per iteration | LOW | MISSING |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| None identified | -- | -- | -- |

---

## 8. tFileList

### Table Stakes

| Feature | Why Expected | Complexity | Current Engine Status |
|---------|--------------|------------|----------------------|
| Iterate files in directory matching filemask pattern | Core function | MEDIUM | MISSING -- no engine implementation exists |
| Directory path with context variable resolution | Dynamic directory paths | LOW | MISSING |
| Glob expression filemask (`GLOBEXPRESSIONS=true`) | Standard file pattern matching (`*.csv`, `report_*.txt`) | MEDIUM | MISSING |
| Include subdirectories (`INCLUDSUBDIR`) | Recursive file processing | LOW | MISSING |
| List mode: FILES, DIRECTORIES, BOTH (`LIST_MODE`) | Control what gets listed | LOW | MISSING |
| ITERATE output connector | Each file triggers one iteration | HIGH | MISSING |
| `{id}_CURRENT_FILEPATH` globalMap variable | Downstream components access current file path | LOW | MISSING |
| `{id}_CURRENT_FILEDIRECTORY` globalMap variable | Current file's parent directory | LOW | MISSING |
| `{id}_CURRENT_FILEEXTENSION` globalMap variable | Current file's extension | LOW | MISSING |
| `{id}_CURRENT_FILENAME` globalMap variable (filename without path) | Just the filename | LOW | MISSING |
| `{id}_NB_FILE` globalMap variable | Total file count | LOW | MISSING |

### Differentiators

| Feature | Value Proposition | Complexity | Current Engine Status |
|---------|-------------------|------------|----------------------|
| Sort order: by filename, filesize, modified date (`ORDER_BY_*`) | Deterministic processing order | LOW | MISSING |
| Sort direction: ascending/descending (`ORDER_ACTION_ASC/DESC`) | Control order direction | LOW | MISSING |
| Case sensitivity control (`CASE_SENSITIVE`) | Platform-specific file matching | LOW | MISSING |
| File exclusion filter (`IFEXCLUDE`, `EXCLUDEFILEMASK`) | Skip specific patterns | LOW | MISSING |
| Error on empty directory (`ERROR`) | Fail-fast if no files found | LOW | MISSING |
| Format filepath to forward slash (`FORMAT_FILEPATH_TO_SLASH`) | Cross-platform path normalization | LOW | MISSING |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| None identified | -- | -- | -- |

---

## 9. tFileExist

### Table Stakes

| Feature | Why Expected | Complexity | Current Engine Status |
|---------|--------------|------------|----------------------|
| Check if file exists at path | Core function | LOW | WORKING |
| File path with context variable resolution | Dynamic paths | LOW | WORKING -- but config key mismatch: converter sends `file_name`, engine reads `file_path` |
| `{id}_EXISTS` globalMap variable (boolean) | Downstream conditional logic via RunIf triggers | LOW | PARTIAL -- engine returns `file_exists` in result dict but may not set globalMap properly |
| `{id}_FILENAME` globalMap variable | Access checked filepath | LOW | MISSING |
| Trigger connections (OnComponentOk, RunIf based on EXISTS) | Conditional execution based on file existence | MEDIUM | PARTIAL -- trigger infrastructure exists but RunIf condition evaluation has string replacement bugs |
| Directory existence check (`check_directory`) | Check for directories not just files | LOW | WORKING |

### Differentiators

| Feature | Value Proposition | Complexity | Current Engine Status |
|---------|-------------------|------------|----------------------|
| `tstatcatcher_stats` integration | Component-level stats | LOW | MISSING |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| None identified | -- | -- | -- |

---

## 10. Python Equivalents (python_component, python_row_component)

### Table Stakes

| Feature | Why Expected | Complexity | Current Engine Status |
|---------|--------------|------------|----------------------|
| Execute Python code once (`python_component`) | Java-free alternative to tJava | LOW | WORKING |
| Execute Python code per row (`python_row_component`) | Java-free alternative to tJavaRow | MEDIUM | WORKING |
| Context access via `context` dict | Read job parameters | LOW | WORKING |
| GlobalMap access via `globalMap` object | Cross-component data sharing | LOW | WORKING |
| Python routine access via `routines` dict | Custom utility functions | LOW | WORKING |
| REJECT output flow for per-row errors | Capture rows where Python code fails | MEDIUM | WORKING in PythonRowComponent -- `reject_rows` list |
| Output schema validation | Type enforcement | LOW | WORKING in PythonRowComponent -- `_validate_output_row()` |
| Pass-through of input data (python_component) | Data flows through unchanged | LOW | WORKING |

### Differentiators

| Feature | Value Proposition | Complexity | Current Engine Status |
|---------|-------------------|------------|----------------------|
| Compiled code execution (compile once, exec per row) | Performance: avoid re-parsing code per row | MEDIUM | MISSING -- `exec()` called per row with string code |
| `df.apply()` optimization path | Vectorized alternative to iterrows | MEDIUM | MISSING |
| Common module access (os, sys, datetime) | Full Python stdlib | LOW | WORKING in python_component; MISSING in python_row_component |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| `os` and `sys` in execution namespace | Full system access | Security risk -- arbitrary file/process operations from job config | Remove os/sys from namespace; provide specific safe functions instead |

---

## Feature Dependencies

```
Engine Infrastructure
    |
    +---> BaseComponent fix (_update_global_map crash, list index bug)
    |         |
    |         +---> All 9 components (table stakes globalMap variables)
    |
    +---> Config key alignment (fieldseparator -> delimiter)
    |         |
    |         +---> tFileInputDelimited
    |         +---> tFileOutputDelimited
    |
    +---> Java bridge reliability (import support, sync fixes)
    |         |
    |         +---> tJava (imports param)
    |         +---> tJavaRow (imports param)
    |         +---> tMap (expression evaluation)
    |
    +---> Iterate execution loop (re-execute downstream subjobs per iteration)
              |
              +---> tFlowToIterate (requires iterate loop)
              +---> tFileList (requires iterate loop)
              +---> tFileExist (triggers depend on iterate)

tMap
    +--requires--> Java bridge (expression evaluation)
    +--requires--> BaseComponent fix (globalMap)
    +--requires--> Context manager (variable resolution)

tFlowToIterate
    +--requires--> Iterate execution loop in engine
    +--requires--> GlobalMap (variable storage per iteration)

tFileList
    +--requires--> Iterate execution loop in engine
    +--requires--> GlobalMap (CURRENT_FILEPATH etc.)

tContextLoad
    +--requires--> Context manager (set/get with types)
    +--enhances--> All downstream components (context variables available)

REJECT flows
    +--requires--> Engine data routing (reject output alongside main)
    +--enhances--> tFileInputDelimited, tMap, tJavaRow, python_row_component
```

### Dependency Notes

- **Iterate execution loop is the biggest missing infrastructure piece.** tFlowToIterate, tFileList, and tFileExist all depend on the engine being able to re-execute downstream subjobs per iteration. This is not a component-level fix -- it is an engine execution loop change.
- **BaseComponent fixes are cross-cutting.** The `_update_global_map()` crash and `GlobalMap.get()` signature bug affect ALL components. Fix these first.
- **Config key alignment** (`fieldseparator` vs `delimiter`) is a one-line fix but affects correctness of every file I/O job.
- **tContextLoad enhances everything downstream** -- it must execute before components that reference context variables it loads.

---

## MVP Definition

### Launch With (must-fix for this milestone)

- [ ] **BaseComponent cross-cutting fixes** -- `_update_global_map()` crash, `GlobalMap.get()` signature, list index bug in `replace_in_config` -- blocks all components
- [ ] **tFileInputDelimited config key alignment** -- engine reads `delimiter` from `fieldseparator` config -- jobs produce wrong output without this
- [ ] **tFileInputDelimited encoding default alignment** -- honor ISO-8859-15 from config, not engine's UTF-8 default
- [ ] **tFileOutputDelimited config key and default alignment** -- delimiter, encoding, include_header defaults all wrong
- [ ] **tJava import support** -- prepend imports to java_code before execution
- [ ] **tJavaRow import support** -- same fix
- [ ] **tMap UNIQUE_MATCH semantics** -- fix to match Talend first-row behavior
- [ ] **tMap inner join reject differentiation** -- route to rejectInnerJoin outputs correctly
- [ ] **tContextLoad die_on_error support** -- honor the flag instead of always raising
- [ ] **tFlowToIterate engine implementation** -- core iterate support for 30% of jobs
- [ ] **tFileList engine implementation** -- file iteration for 30% of jobs
- [ ] **tFileExist config key alignment** -- `file_name` vs `file_path` mismatch
- [ ] **Iterate execution loop** -- engine must re-execute downstream subjobs per iteration
- [ ] **REJECT flow support in tFileInputDelimited** -- capture malformed rows

### Add After Validation (hardening)

- [ ] **tMap RELOAD_AT_EACH_ROW** -- needed for parameterized DB lookups, not common in file-only jobs
- [ ] **tMap catch_output_reject** -- expression evaluation error capture
- [ ] **tFileOutputDelimited file splitting** -- needed for large outputs
- [ ] **tFileOutputDelimited file_exist_exception** -- prevent accidental overwrites
- [ ] **tFileInputDelimited CHECK_FIELDS_NUM** -- row structure validation
- [ ] **tFileInputDelimited CHECK_DATE** -- date format validation
- [ ] **tContextLoad LOAD_NEW_VARIABLE / NOT_LOAD_OLD_VARIABLE policies** -- validation warnings
- [ ] **tFileList sort order options** -- deterministic file processing
- [ ] **Compiled code for python_row_component** -- performance optimization

### Future Consideration (v2+)

- [ ] **tMap fuzzy matching (Levenshtein/Jaccard)** -- rarely used, high complexity
- [ ] **tMap disk-based lookup caching** -- only needed for very large lookup tables
- [ ] **tMap parallel lookup loading** -- optimization, not correctness
- [ ] **tFileInputDelimited compressed file reading** -- uncommon use case
- [ ] **tFileInputDelimited random sampling** -- testing convenience, not production critical
- [ ] **tFileOutputDelimited compression** -- can be done externally
- [ ] **tFileOutputDelimited stream mode** -- Java OutputStream integration, rarely used in file-based jobs

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| BaseComponent cross-cutting fixes | HIGH | LOW | **P0** |
| Config key alignment (all file components) | HIGH | LOW | **P0** |
| Iterate execution loop | HIGH | HIGH | **P0** |
| tFlowToIterate engine implementation | HIGH | MEDIUM | **P0** |
| tFileList engine implementation | HIGH | MEDIUM | **P0** |
| tFileInputDelimited REJECT flow | HIGH | MEDIUM | **P1** |
| tJava/tJavaRow import support | HIGH | LOW | **P1** |
| tMap UNIQUE_MATCH fix | HIGH | LOW | **P1** |
| tMap inner join reject routing | MEDIUM | MEDIUM | **P1** |
| tContextLoad die_on_error | MEDIUM | LOW | **P1** |
| tFileExist config key fix | HIGH | LOW | **P1** |
| tFileExist globalMap variables (EXISTS, FILENAME) | MEDIUM | LOW | **P1** |
| tMap RELOAD_AT_EACH_ROW | MEDIUM | HIGH | **P2** |
| tMap catch_output_reject | MEDIUM | MEDIUM | **P2** |
| tFileOutputDelimited file splitting | MEDIUM | MEDIUM | **P2** |
| tFileInputDelimited CHECK_FIELDS_NUM | MEDIUM | MEDIUM | **P2** |
| tContextLoad variable policies | LOW | MEDIUM | **P2** |
| tFileList sort/exclude options | LOW | LOW | **P2** |
| python_row_component compile optimization | MEDIUM | MEDIUM | **P2** |
| tMap fuzzy matching | LOW | HIGH | **P3** |
| tMap disk-based lookup caching | LOW | HIGH | **P3** |
| Compressed file I/O | LOW | MEDIUM | **P3** |
| Random sampling | LOW | LOW | **P3** |

**Priority key:**
- P0: Blocks production jobs -- must fix in this milestone
- P1: Important for correctness/completeness -- should fix in this milestone
- P2: Edge cases some jobs depend on -- add when possible
- P3: Rarely used or can be worked around -- future consideration

---

## Data Flow Patterns

### Connector Types by Component

| Component | MAIN In | MAIN Out | REJECT Out | ITERATE Out | LOOKUP In | Trigger Out |
|-----------|---------|----------|------------|-------------|-----------|-------------|
| tFileInputDelimited | -- | Yes | Yes (missing) | -- | -- | SUBJOB_OK, SUBJOB_ERROR |
| tMap | Yes | Yes (multiple) | Yes | -- | Yes (multiple) | SUBJOB_OK, SUBJOB_ERROR |
| tFileOutputDelimited | Yes | Yes (pass-through) | -- | -- | -- | SUBJOB_OK, SUBJOB_ERROR |
| tJava | Yes (optional) | Yes (pass-through) | -- | -- | -- | SUBJOB_OK, SUBJOB_ERROR |
| tJavaRow | Yes | Yes | Yes (missing in Java) | -- | -- | SUBJOB_OK, SUBJOB_ERROR |
| tContextLoad | Yes (optional) | -- | -- | -- | -- | SUBJOB_OK, SUBJOB_ERROR |
| tFlowToIterate | Yes | -- | -- | Yes (missing) | -- | SUBJOB_OK, SUBJOB_ERROR |
| tFileList | -- | -- | -- | Yes (missing) | -- | SUBJOB_OK, SUBJOB_ERROR |
| tFileExist | -- | -- | -- | -- | -- | ON_COMPONENT_OK, ON_COMPONENT_ERROR, RUN_IF |

### Engine Execution Patterns

**Standard flow:** Component A (MAIN out) -> Component B (MAIN in) -> Component C (MAIN in)
- Engine routes DataFrame through components sequentially

**Multi-output flow:** tMap -> Output1 (MAIN), Output2 (MAIN), Reject (REJECT)
- Engine must route named DataFrames to correct downstream components

**Iterate flow:** tFileList (ITERATE out) -> tFileInputDelimited -> tFileOutputDelimited
- Engine must re-execute entire downstream subjob for each iteration
- GlobalMap variables change per iteration (CURRENT_FILEPATH etc.)

**Trigger flow:** tFileExist -> (RunIf: EXISTS==true) -> tFileInputDelimited
- Engine evaluates RunIf condition from globalMap, conditionally executes downstream

---

## Sources

- Talend _java.xml definitions (Talaxie GitHub) -- parameter names, types, defaults
- [tFileInputDelimited Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/delimited/tfileinputdelimited-standard-properties) -- official property docs
- [tFileOutputDelimited Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/delimited/tfileoutputdelimited-standard-properties) -- official property docs
- [tMap lookup models (Talend 8.0)](https://help.talend.com/en-US/components/8.0/tmap/tmap-lookup-models) -- LOAD_ONCE, RELOAD behavior
- [tFileExist Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/tfileexist/tfileexist-standard-properties) -- official property docs
- [tFlowToIterate Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/orchestration/tflowtoiterate) -- official docs
- [tFileList Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/tfilelist/tfilelist-standard-properties) -- official docs
- Converter source code: `src/converters/talend_to_v1/components/` -- all 9 component converters
- Engine source code: `src/v1/engine/components/` -- all existing engine implementations
- Audit reports: `docs/v1/audit/components/` -- 86-component audit with 928 issues
- Engine concerns: `.planning/codebase/CONCERNS.md` -- known bugs and gaps

---
*Feature research for: Talend ETL migration engine -- component feature matrix*
*Researched: 2026-04-14*
