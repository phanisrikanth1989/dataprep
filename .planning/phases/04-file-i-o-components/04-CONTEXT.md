# Phase 4: File I/O Components - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite tFileInputDelimited and tFileOutputDelimited from scratch with full Talend feature parity, conforming to the ENGINE_COMPONENT_PATTERN.md blueprint from Phase 1, with decorator-based auto-registration from Phase 3. Both components are rewritten to read converter config keys directly (no mapping layer), with Talend-matching defaults. Engine unit tests with exhaustive coverage per requirement.

**Focus:** Talend feature parity first — not preserving current coded capability. Close as many Talend features as possible, leaving out only extreme edge cases.

**Phase 1/3 dependencies:** BaseComponent lifecycle, config snapshot/restore, GlobalMap, ContextManager, TriggerManager, decorator-based ComponentRegistry, OutputRouter for REJECT flow routing — all available from Phase 1 and Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Rewrite Approach
- **D-01:** Full rewrite from scratch for both components. Not patching the existing ~575-line FileInputDelimited or ~472-line FileOutputDelimited. Conform to ENGINE_COMPONENT_PATTERN.md blueprint.
- **D-02:** Add `@REGISTRY.register('tFileInputDelimited')` and `@REGISTRY.register('tFileOutputDelimited')` decorators per Phase 3 D-04.
- **D-03:** Focus on Talend feature parity based on audit reports and Talend _java.xml parameter definitions, not on what the current engine code happens to support.

### Config Key Alignment (ENG-13)
- **D-04:** Engine reads converter config keys directly — `fieldseparator` (not `delimiter`), `remove_empty_row` (not `remove_empty_rows`), `header_rows`, `footer_rows`, etc. No mapping layer, no dual-key support. Clean 1:1 match with converter output.
- **D-05:** Engine defaults match Talend defaults: `encoding='ISO-8859-15'`, `fieldseparator=';'`, `include_header=False`, `remove_empty_row=True`, `die_on_error=False`, `file_exist_exception=True`, `create_directory=True`.

### REJECT Flow (FILD-03)
- **D-06:** Three rejection triggers implemented:
  - Wrong field count (CHECK_FIELDS_NUM) — row has fewer/more fields than schema expects
  - Type conversion failure — field can't convert to schema type (e.g., 'abc' in Integer column)
  - Date pattern validation (CHECK_DATE) — date fields must match schema's date pattern exactly
- **D-07:** Reject row contains all original columns plus `errorCode` (string) and `errorMessage` (string) — matches Talend reject behavior. Downstream reject-connected components see the full row + why it failed.
- **D-08:** NB_LINE_REJECT globalMap variable tracks reject count accurately.

### tFileInputDelimited — In-Scope Features
- **D-09:** Core features: filepath, fieldseparator, row_separator, encoding (ISO-8859-15 default), header/footer skip, limit, remove_empty_row, text_enclosure, escape_char, trim_all, die_on_error, schema enforcement with type conversion, streaming mode for large files.
- **D-10:** CSV_OPTION toggle — when true, enables RFC4180 mode (quoted fields with embedded delimiters/newlines). When false, text_enclosure and escape_char have no effect. Current engine always applies quoting regardless — must fix.
- **D-11:** TRIMSELECT (per-column trim) — override trim_all with per-column trim settings from converter's trim_select array. Each entry has {column, trim} where trim is boolean.
- **D-12:** CHECK_FIELDS_NUM — validate each row has correct number of fields per schema. Rows with wrong count route to REJECT flow.
- **D-13:** CHECK_DATE — strict date format validation against schema patterns. Rows with invalid dates route to REJECT flow.
- **D-14:** csv_row_separator — separate row separator for CSV mode. When CSV_OPTION=true, use csv_row_separator instead of row_separator.
- **D-15:** globalMap variables: `{id}_FILENAME` (resolved file path, set before execution), `{id}_ENCODING` (resolved encoding, set before execution), `{id}_NB_LINE`, `{id}_NB_LINE_OK`, `{id}_NB_LINE_REJECT` (set after execution).

### tFileOutputDelimited — In-Scope Features
- **D-16:** Core features: filepath, fieldseparator, row_separator, encoding (ISO-8859-15 default), include_header (default false), append mode, text_enclosure, escape_char, CSV_OPTION toggle, csv_row_separator, create_directory, delete_empty_file, die_on_error.
- **D-17:** FILE_EXIST_EXCEPTION (FOLD-05) — when `file_exist_exception=true` (default) and file already exists in non-append mode, raise FileOperationError. Prevents accidental overwrites.
- **D-18:** SPLIT / SPLIT_EVERY (FOLD-04) — split large outputs into multiple files based on row count threshold. Research phase must determine exact Talend split file naming convention.
- **D-19:** OS_LINE_SEPARATOR — when `os_line_separator=true`, use `os.linesep` instead of configured row_separator for platform-appropriate line endings.
- **D-20:** globalMap variables: `{id}_NB_LINE`, `{id}_NB_LINE_OK`, `{id}_NB_LINE_REJECT` (set after execution), `{id}_FILE_NAME` (FOLD-06, resolved output file path).

### Deferred to Future Work
- **D-21:** The following features are captured by the converter but not implemented in Phase 4. Engine should log a warning if the config flag is set but silently proceed:
  - UNCOMPRESS (compressed file reading)
  - COMPRESS (ZIP output writing)
  - RANDOM / NB_RANDOM (random line sampling)
  - ENABLE_DECODE / DECODE_COLS (hex/octal number decoding)
  - ADVANCED_SEPARATOR / THOUSANDS_SEPARATOR / DECIMAL_SEPARATOR (numeric formatting)
  - SPLIT_RECORD (multi-line fields)
  - USESTREAM / STREAMNAME (Java OutputStream — not applicable in Python)
  - ROW_MODE (per-row atomic flush)
  - FLUSHONROW / FLUSH_ROW_COUNT (buffer flush control)

### Test Strategy
- **D-22:** Tests use `tmp_path` for programmatic file creation (portable across OS, self-documenting). Small fixture directory at `tests/v1/engine/fixtures/file/` for cases that benefit from pre-built files (specific encodings, edge cases).
- **D-23:** All file paths constructed via `pathlib.Path` — no hardcoded OS-specific paths. Tests work on Linux, macOS, and Windows.
- **D-24:** Exhaustive test coverage per requirement. Every FILD/FOLD requirement gets a dedicated test class with happy path + edge cases. Target ~80-120 tests across both components.
- **D-25:** Include a few integration tests using real converter JSON output (e.g., `Job_tFileInputDelimited_0.1.json`) to verify converter + engine work together. Not full Phase 12 integration scope, just early confidence.
- **D-26:** Test location: `tests/v1/engine/components/file/test_file_input_delimited.py` and `test_file_output_delimited.py`, matching source structure.

### Claude's Discretion
- Internal method decomposition and helper design within each component
- Exact streaming threshold and chunk size (can follow BaseComponent defaults)
- How to handle the single-string read mode (empty delimiter/separator edge case)
- Talend split file naming convention (determined during research)
- Whether CSV_OPTION implementation uses Python's csv module, pandas csv params, or a hybrid

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Audit Reports (Primary Feature Reference)
- `docs/v1/audit/components/file/tFileInputDelimited.md` — Full Talend feature baseline (33 params), 21 engine issues, behavioral notes, config key comparison table (Appendix C)
- `docs/v1/audit/components/file/tFileOutputDelimited.md` — Full Talend feature baseline (27 params), 14 engine issues, behavioral notes, needs_review entries

### Engine Component Pattern (Blueprint)
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` — Gold standard pattern. Both components must conform to this structure.
- `docs/v1/standards/ENGINE_TEST_PATTERN.md` — Test pattern for engine component tests.

### Current Engine Source (Rewrite Targets)
- `src/v1/engine/components/file/file_input_delimited.py` — Current FileInputDelimited (574 lines, full rewrite)
- `src/v1/engine/components/file/file_output_delimited.py` — Current FileOutputDelimited (472 lines, full rewrite)

### Phase 1/3 Infrastructure (Build On)
- `src/v1/engine/base_component.py` — Rewritten BaseComponent with lifecycle, config snapshot/restore, validate_schema()
- `src/v1/engine/component_registry.py` — Decorator-based ComponentRegistry from Phase 3
- `src/v1/engine/output_router.py` — REJECT flow routing from Phase 3
- `src/v1/engine/exceptions.py` — Exception hierarchy (ConfigurationError, FileOperationError, DataValidationError)

### Converter Source (Config Key Reference)
- `src/converters/talend_to_v1/components/file/file_input_delimited.py` — Converter output format for tFileInputDelimited config keys
- `src/converters/talend_to_v1/components/file/file_output_delimited.py` — Converter output format for tFileOutputDelimited config keys

### Sample Converter Output
- `tests/talend_xml_samples/converted_jsons/Job_tFileInputDelimited_0.1.json` — Real converter output showing exact config key names and values

### Requirements
- `.planning/REQUIREMENTS.md` — FILD-01 through FILD-09, FOLD-01 through FOLD-06, TEST-03 mapped to Phase 4

### Prior Phase Context
- `.planning/phases/01-infrastructure-bug-fixes-project-setup/01-CONTEXT.md` — D-02/D-03 (config key alignment deferred to component phases), D-09 (accept breakage), D-15 (ENGINE_COMPONENT_PATTERN.md)
- `.planning/phases/03-execution-loop-restructure/03-CONTEXT.md` — D-04 (registry starts empty, each phase adds decorators)

</canonical_refs>

<code_context>
## Existing Code Insights

### What Gets Rewritten
- `file_input_delimited.py` (574 lines) — reads wrong config keys (`delimiter` vs `fieldseparator`), wrong defaults (UTF-8 vs ISO-8859-15), no REJECT flow, no CHECK_FIELDS_NUM, no CHECK_DATE, no CSV_OPTION toggle, no TRIMSELECT, missing globalMap vars, single-string DF creation bug
- `file_output_delimited.py` (472 lines) — reads wrong config keys, wrong defaults (include_header=True vs False, encoding=UTF-8 vs ISO-8859-15), no FILE_EXIST_EXCEPTION, no SPLIT, no OS_LINE_SEPARATOR, indentation bug in error handling, missing globalMap `{id}_FILE_NAME`

### What to Study (Not Reuse)
- Current `_read_batch()` and `_read_streaming()` — understand the pandas.read_csv() parameter patterns. The rewrite uses similar pandas APIs but with correct config keys and additional validation layers.
- Current `_post_process_dataframe()` — understand trim, fillna, BigDecimal conversion. Rewrite must add per-column TRIMSELECT and route type failures to reject.
- Current `_handle_empty_data()` in output — understand Talend's empty-file behavior (header-only file when include_header=true). Preserve this.
- Current `_configure_csv_params()` — understand quoting modes. Rewrite must gate this behind CSV_OPTION toggle.

### Established Patterns (From Phase 1/3)
- BaseComponent lifecycle: validate -> snapshot -> resolve -> process -> stats
- `_validate_config()` is abstract and required — both components must implement
- Config snapshot/restore for iterate re-execution — built into BaseComponent
- Decorator-based registry: `@REGISTRY.register('tComponentName')` triggers on import
- OutputRouter handles named flow routing (main, reject) between components

### Integration Points
- Both components register in ComponentRegistry via `@REGISTRY.register()` decorator
- FileInputDelimited produces `main` and `reject` output flows consumed by OutputRouter
- FileOutputDelimited reads from `main` input flow provided by OutputRouter
- Both set globalMap variables via `self.global_map[f"{self.id}_VARNAME"]` pattern
- Both use ContextManager for `${context.var}` resolution in filepath and other string configs

</code_context>

<specifics>
## Specific Ideas

- Focus on Talend feature parity based on audit reports and _java.xml, not on current engine capability
- The audit report Appendix C (config key comparison table) for tFileInputDelimited is the definitive reference for key alignment
- Research phase should check Talend's exact split file naming convention for SPLIT_EVERY output
- Research phase should verify the exact reject row schema Talend produces (errorCode values, errorMessage format)
- BUG-FID-002 (single-string DF bug) and BUG-FOD-002 (indentation bug) are inherently fixed by the rewrite — no separate fix needed

</specifics>

<deferred>
## Deferred Ideas

- UNCOMPRESS / COMPRESS — compressed file I/O (future work)
- RANDOM / NB_RANDOM — random line sampling (future work)
- ENABLE_DECODE / DECODE_COLS — hex/octal decoding (future work)
- ADVANCED_SEPARATOR / THOUSANDS_SEPARATOR / DECIMAL_SEPARATOR — numeric formatting (future work)
- SPLIT_RECORD — multi-line field support (future work)
- USESTREAM / ROW_MODE / FLUSHONROW — Java-specific buffer/stream concepts (future work)

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-file-i-o-components*
*Context gathered: 2026-04-15*
