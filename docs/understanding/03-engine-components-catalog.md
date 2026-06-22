# Engine Components Catalog

This document is a reference catalog of every execution-engine component in
`src/v1/engine/components/`. The engine executes JSON job configs produced by the
Talend-to-V1 converter; each component class subclasses `BaseComponent` (or
`BaseIterateComponent` for iterate primitives), is registered in the central
`REGISTRY` under both a V1 name and one or more Talend `t`-prefixed aliases, and
returns a `{"main": DataFrame, "reject": DataFrame|None, ...named flows}` dict
that the engine's `OutputRouter` consumes.

The audience is engineers extending this codebase and raising per-module test
coverage to a 95% floor. Tables below give, for each component: the engine class,
source file, what it does, its Talend equivalent, and the most load-bearing
parity notes or known gaps. Bugs and risks flagged by the code-reader fleet are
called out inline and consolidated in a final section.

For the `tMap` engine specifically (the `map/` subpackage with config, joins,
script generation, bridge-sync, and reject routing), see the dedicated document
`docs/understanding/04-tmap-and-java-bridge.md` (or the `eng-tmap` subsystem). This catalog
covers only the thin orchestrator surface of `Map` and the pure-Python `PyMap`
analog; it does not duplicate the join-strategy and Groovy-codegen detail.

> ASCII-only is a hard project rule; all examples and tables below follow it.


## Contents

1. [Shared component contract](#1-shared-component-contract)
2. [File INPUT (source) components](#2-file-input-source-components)
3. [File OUTPUT + filesystem ops](#3-file-output--filesystem-ops)
4. [Transform: extract / parse / field ops](#4-transform-extract--parse--field-ops)
5. [Transform: code / python / java + flow ops](#5-transform-code--python--java--flow-ops)
6. [Aggregate components](#6-aggregate-components)
7. [Context components](#7-context-components)
8. [Control components](#8-control-components)
9. [Iterate components](#9-iterate-components)
10. [Cross-cutting bugs, risks, and coverage gaps](#10-cross-cutting-bugs-risks-and-coverage-gaps)


## 1. Shared component contract

Every component obeys the same `BaseComponent.execute()` template (see
`src/v1/engine/base_component.py`). Understanding this lifecycle is essential
before reading the per-component tables, because most "where does X happen"
questions resolve to the base class, not the component.

| Step | What happens | Where |
| --- | --- | --- |
| 1 | `config` re-derived fresh from a deepcopied `_original_config` (immutable; clean per iterate re-exec) | `base_component.py` |
| 2 | `_validate_config()` runs STRUCTURE-only checks (Rule 12: presence/shape; no content checks) | component |
| 3 | `_resolve_expressions()` resolves `{{java}}` markers via the Java bridge, then `${context.X}`/bare `context.X` substitution everywhere except `python_code`/`java_code`/`imports` (`SKIP_RESOLUTION_KEYS`) | base + bridge |
| 4 | `die_on_error` read | base |
| 5 | input rows counted for `NB_LINE` | base |
| 6 | mode selected: config override, else `HYBRID` auto-switch to `STREAMING` above `MEMORY_THRESHOLD_MB` (5120 MB) | base |
| 7 | `_process(input_data)` -> `{main, reject, ...}` (the per-component logic) | component |
| 7b/7c | output schema column order enforced; type coercion + precision + `treat_empty_as_null`; schema violations route to reject when `die_on_error=False` | base |
| 8 | stats (`NB_LINE`/`NB_LINE_OK`/`NB_LINE_REJECT`) pushed to `GlobalMap` | base |

Key consequences for extenders:

- **Components emit mostly string data and defer typed validation** to the base
  class. Type coercion, length, nullability, and reject routing are a single
  source of truth in `validate_schema`/`_apply_output_schema_validation`.
- **"Rule 12"**: content checks (file existence, LIMIT parsing, enum membership)
  belong in `_process`, run after context-var resolution, so an unresolved
  `${context.X}` reference never crashes validation.
- `output_schema`/`reject_schema`/`java_bridge`/`context_manager`/`global_map`
  are INJECTED by the engine (`engine.py`), not read from config.
- Registration uses `@REGISTRY.register("V1Name", "tTalendName", ...)`; the
  converter emits the V1 name as the component `type`, but Talend aliases let a
  raw Talend type also dispatch.

> Two engine-wide blockers were flagged at doc-lock time: a `SyntaxError` at
> `engine.py:225` (missing comma in an `add_trigger` call) that prevents the
> `src.v1.engine` package from importing, and a class-scoping indentation bug in
> `trigger_manager.py` that makes the trigger subsystem non-functional. These are
> not component bugs but they block running ANY component test that imports the
> engine. See section 10.


## 2. File INPUT (source) components

Source components receive `input_data=None` (except `SetGlobalVar`, which passes
a flow through), read an external file/stream, and emit a pandas DataFrame.
Delimited/positional/full-row read everything as `string` dtype with
`keep_default_na=False` to preserve Talend semantics; the base class then coerces
types. Default encoding is ISO-8859-15 (Talend default), not UTF-8.

| Engine class | File (`src/v1/engine/components/file/`) | What it does | Talend equivalent | Parity notes / gaps |
| --- | --- | --- | --- | --- |
| `FileInputDelimited` | `file_input_delimited.py` | Most feature-complete reader: standard (pandas) + RFC4180 `csv.reader` modes, non-standard row-separator manual split, schema alignment, per-column/global trim, two-tier (vectorized fast path / chunked per-row) validation with `TYPE_CONVERSION`/`FIELD_COUNT`/`DATE_FORMAT` reject codes | tFileInputDelimited | LIMIT halts reading (pushes `nrows` when no footer); silently truncates extra / pads missing columns positionally; `csv_option` multi-char delimiter truncates to first char. Strong, parity-aware design. RISK: non-printable scrub regex `[^\x20-\x7E\t\n\r]` replaces ALL non-ASCII (incl. valid Latin-1 accents) with space |
| `FileInputExcel` | `file_input_excel.py` | xls (xlrd) + xlsx (openpyxl) via `pd.read_excel`; per-column converter closures, regex/partial sheet matching, all-sheets concat, column-range, header/footer/limit, trim. Largest file in the dir (~1069 LOC) | tFileInputExcel | BUG: streaming path is dead code (`self.chunk_size` never defined; `execution_mode` never assigned by engine), so large `.xlsx` always loads fully into memory (silent OOM risk). `_apply_date_conversion` has an implicit-`None`-return footgun |
| `FileInputPositional` | `file_input_positional.py` | Fixed-width via `pd.read_fwf`, widths from pattern; non-printable scrub, `trim_all`, empty-row removal, advanced numeric separators, `check_date` coerce, BigDecimal conversion | tFileInputPositional | GAP: ignores `trim_select` entirely (only `trim_all`, default True), so all string columns are trimmed unless explicitly disabled -- diverges from Talend per-column TRIMSELECT. No reject flow (`rejected` always 0); `check_date` uses `errors='coerce'` (silent NaT) |
| `FileInputFullRowComponent` | `file_input_fullrow.py` | One row per line into a single-column DataFrame; custom row-separator decode, header/footer skip, strict empty-line removal, LIMIT, random sampling, default column name `line` | tFileInputFullRow | `remove_empty_row` tests `line == ''` strictly (whitespace-only kept); `limit == '0'` treated as unlimited |
| `FileInputJSON` | `file_input_json.py` | jsonpath-ng loop query + column mapping; file or URL; normalizes Talend `SCHEMA_COLUMN`/`QUERY` mapping; per-element type conversion; `PARSE_ERROR` reject rows; list/dict serialized to JSON strings | tFileInputJSON | RISK: `urlopen` has no scheme allowlist/timeout/size cap (SSRF/hang). Has dead `validate_config()` (list) alongside `_validate_config()` (raises) that DISAGREE on required `mapping`. `use_loop_as_root` default differs converter(True)/engine(False) |
| `FileInputXML` | `file_input_xml.py` | `loop_query` XPath + per-column mapping xpath, threshold-switched DOM/iterparse, `ignore_ns`, document-passing modes, REJECT with `XPATH`/`PARSE`/`NODECHECK`/`FILE_MISSING` codes | tFileInputXML | Uses config key `filepath` (NOT `filename`); module docstring is misleading on this. Secure parse via shared `_xml_io` |
| `FileInputMSXML` | `file_input_msxml.py` | `root_loop_query` selects rows, output columns matched to child tag names; threshold DOM/streaming; `PARSE_ERROR`/`NODE_ERROR` reject codes | tFileInputMSXML | GAP: multi-schema + large-file streaming unsupported (documented DOM fallback with warning) |
| `FileInputProperties` | `file_input_properties.py` | Parses Java `.properties` (key=value/key:value, continuations, comments) or `.ini` (configparser); maps keys to schema columns by name; `RETRIVE_BY_SECTION` vs `RETRIVE_ALL` | tFileInputProperties | No engine-side reject flow; schema column names are authoritative key set |
| `FileInputRaw` | `file_input_raw.py` | Reads whole file into a single-row DataFrame `content` column (str or bytes); `NB_LINE` always 1 | tFileInputRaw | SMELL: `_validate_config` returns a `List[str]` instead of raising, so a missing `filename` is NOT caught at validation -- `_process` calls `open(None)` and fails late. `debug_content()` logs file content at INFO level on every read |
| `FixedFlowInputComponent` | `fixed_flow_input.py` | Static row generator (single-template / inline-table / inline-content modes); no file I/O; Java-escape separator decode, context/globalMap resolution, eval-free numeric coercion | tFixedFlowInput | SMELL: raises `ConfigurationError(self.id, message)` (2 positional args) so `str()` renders a tuple, breaking the `[id] message` log convention |
| `SetGlobalVar` | `set_global_var.py` | Per-row globalMap variable setter from a KEY/VALUE table; resolves Talend row-field refs (`flowname.column`); passes input through unchanged; numpy scalar normalization for Py4J | tSetGlobalVar | Pass-through component (the only "input" file component that consumes a flow) |

Shared XML helpers live in `_xml_io.py`: `secure_xml_parser` (XXE / billion-laughs
/ no-network hardened), `parse_xml_strategy` (size-threshold DOM vs stream),
`iterparse_loop_query` (memory-correct element clearing + sibling pruning,
try/finally on `GeneratorExit`). This module is flagged GOOD for security posture.


## 3. File OUTPUT + filesystem ops

Output writers serialize an upstream DataFrame to disk while preserving Talend
`tFileOutput*` formatting. They are pass-through sinks: formatting happens on a
`.copy()` and the ORIGINAL DataFrame is returned as `main` so downstream
sinks/triggers keep flowing (EXCEPT Excel, which returns `main=None`). Filesystem
utilities ignore `input_data`, perform an OS operation, publish Talend-parity
`globalMap` RETURN variables, and return a status dict / one-row DataFrame /
empty frame.

### 3a. Output writers

| Engine class | File (`src/v1/engine/components/file/`) | What it does | Talend equivalent | Parity notes / gaps |
| --- | --- | --- | --- | --- |
| `FileOutputDelimited` | `file_output_delimited.py` | CSV/raw delimited writer: three write paths (`csv.writer` QUOTE_ALL, pandas `to_csv` QUOTE_NONE single-char, manual raw multi-char); split; header-on-first-write; date/decimal/boolean formatting; Java-expr filepath resolution; streaming append | tFileOutputDelimited | ISO-8859-15 default; `csv_option` multi-char delimiter truncates to first char; non-CSV uses `escapechar=None` for raw concat; booleans lowercased. SMELL: `os_line_separator` (default True) checked first, silently overriding `csvrowseparator`/`row_separator` |
| `FileOutputExcel` | `file_output_excel.py` | openpyxl workbook/sheet writer with append, ghost-row detection (`_last_data_row`), `FIRST_CELL_X/Y` positioning, auto-size, decimal number formats | tFileOutputExcel | Returns `{'main': None}` (breaks pass-through). Append uses a heuristic last-data-row scan rather than Talend's exact model. GOOD: ghost `max_row=1` defense prevents duplicate-header/row-shift on append |
| `FileOutputPositional` | `file_output_positional.py` | Fixed-width writer with vectorized per-column ALIGN/KEEP/pad, gzip compress, flush-on-row, streaming append | tFileOutputPositional | KEEP ALL/LEFT/MIDDLE/RIGHT + L/R/C alignment with alias normalization. RISK: append + compress produces a multi-member gzip (valid but some readers mishandle). NOTE: converter flags this engine class was NOT in `COMPONENT_REGISTRY` at converter-doc time -- re-verify it is registered |
| `FileOutputXML` | `file_output_xml.py` | Flat XML via `etree.xmlfile` incremental API, attribute/element mapping, document passthrough, split, streaming context held on `self` | tFileOutputXML | IMPROVEMENT: column names used directly as XML tags (`xf.element(col)`) without sanitization -- a space/invalid char raises mid-stream after partial write. Doc claims dual-name registration but only `tFileOutputXML` is a registry key |
| `AdvancedFileOutputXML` | `file_output_advanced_xml.py` | Hierarchical ROOT/GROUP/LOOP TABLE-driven XML via incremental writer; pandas groupby per GROUP; nested incremental contexts | tAdvancedFileOutputXML | GAP: 6 features warn-and-ignore (D-E1): DTD/XSL validation, `OUTPUT_AS_XSD`, `ADD_DOCUMENT_AS_NODE`, `ADD_UNMAPPED_ATTRIBUTE`, MERGE (merge silently overwrites). Thousands/decimal separators deferred |

### 3b. Filesystem utilities

| Engine class | File (`src/v1/engine/components/file/`) | What it does | Talend equivalent | Parity notes / gaps |
| --- | --- | --- | --- | --- |
| `FileArchive` / `FileArchiveComponent` | `file_archive.py` | ZIP creation from file/dir with mask filter, compression level, overwrite/mkdir guards | tFileArchive | GAP: only ZIP (tar/gzip Talend formats unsupported). BUG/RISK: with `sub_directroy=False`, directory members use `relpath(file, source)` so the source folder name is dropped from the archive root -- confirm vs Talend, which preserves the selected folder as root |
| `FileUnarchive` / `FileUnarchiveComponent` | `file_unarchive.py` | ZIP extraction with zip-slip protection, flatten/preserve paths, password, rootname strip | tFileUnarchive | GOOD: robust zip-slip protection (resolved abspath checked against `abs_output + os.sep` and equality before any write, handling `/out` vs `/output` prefix collision). NOTE: converter side leaks PASSWORD into JSON (security inconsistency on the converter, not here) |
| `FileCopy` | `file_copy.py` | file/dir copy with rename, replace, move-semantics (`remove_file`), timestamp preserve, FAILON | tFileCopy | SMELL: file-mode + `create_directory=True` calls `os.makedirs(destination)` treating the whole destination as a dir. BUG: directory copy bypasses the friendly `replace_file` pre-check (gated on `not is_directory_copy`), surfacing raw `copytree` FileExistsError |
| `FileDelete` | `file_delete.py` | file/folder/auto-detect delete with recursive option, FAILON | tFileDelete | SMELL: a missing path is a soft reject (`deleted=False`, `rows_reject=1`) regardless of `failon` (which only fires on OSError) -- confirm Talend FAILON-on-missing semantics |
| `FileExist` / `FileExistComponent` | `file_exist.py` | Existence check publishing `{id}_EXISTS` / `{id}_FILENAME` to globalMap | tFileExist | Converter emits `file_name`; engine expects `file_path` (documented key-name mismatch) |
| `FileList` | `file_list.py` | `BaseIterateComponent`: directory walk with glob/regex masks, exclusion, sort; yields `FileListItem`; writes 5 Talend RETURN vars per iteration | tFileList | GOOD: regex masks use `re.fullmatch` (mirrors Java `Pattern.matches`); mask compilation hoisted out of the per-file loop (O(N_masks) not O(N_files*N_masks)); `CURRENT_FILEEXTENSION` strips leading dot; `ORDER_BY_NOTHING` preserves OS order; `ERROR=true` raises on 0 matches |
| `FileProperties` | `file_properties.py` | Single `os.stat` metadata extraction + optional MD5; emits one-row DataFrame | tFileProperties | Converter key-name mismatches (`filename`/`md5` vs `FILENAME`/`MD5`) documented as engine_gap |
| `FileRowCount` | `file_row_count.py` | Counts file rows with configurable separator/encoding; publishes `{id}_COUNT` | tFileRowCount | Encoding default mismatch (engine UTF-8 vs Talend ISO-8859-15) flagged by converter |
| `FileTouch` | `file_touch.py` | Create/refresh file mtime, optional dir creation, FAILON | tFileTouch | Converter emits `createdir`; engine expects `create_directory` (documented mismatch) |

Filesystem utilities deliberately preserve some Talend XML param-name typos as
config keys for round-trip fidelity (`sub_directroy`, `source_derectory`,
`encording`); helper accessors (`_cfg`/`_get_bool`/`_get_str`) accept uppercase
Talend keys, lowercase converter keys, and legacy aliases.


## 4. Transform: extract / parse / field ops

Row/field reshaping and validation. Each returns `{"main", "reject"}` with the
goal of behavioral parity with the matching Talend `tXxx`, including reject-flow
semantics. The shared "position-based extraction" convention: extracted columns
are the `output_schema` columns NOT already present in the input DataFrame,
filled in schema order (names irrelevant).

| Engine class | File (`src/v1/engine/components/transform/`) | What it does | Talend equivalent | Parity notes / gaps |
| --- | --- | --- | --- | --- |
| `ExtractDelimitedFields` | `extract_delimited_fields.py` | Position-based split of one column into output-schema columns; advanced numeric separator normalization; `check_fields_num` reject | tExtractDelimitedFields | Converter `fieldseparator` vs engine `field_separator` key mismatch documented |
| `ExtractJSONFields` | `extract_json_fields.py` | JSONPath loop + per-column mapping; JSONPATH/XPATH mode dispatch (XPATH best-effort JSONPath, warned); reject on null/parse | tExtractJSONFields | Returns 0 rows on empty loop match (no root fallback). RISK: multi-match values serialized with `json.dumps` (array string) rather than first/last scalar -- needs Talend parity test on ambiguous queries |
| `ExtractPositionalFields` | `extract_positional_fields.py` | Fixed-width slicing by comma-separated widths; BOM strip; `check_fields_num` on line length | tExtractPositionalFields | Pattern default mismatch + unread keys flagged by converter |
| `ExtractRegexFields` | `extract_regex_fields.py` | Regex capture groups mapped by position; Java double-backslash unescape; `NO_MATCH` reject | tExtractRegexFields | SMELL: blanket `replace('\\\\', '\\')` can corrupt legitimately escaped backslashes. Converter keeps `t`-prefix type (no-engine marker convention) -- but engine DOES implement it; reconcile |
| `ExtractXMLField` | `extract_xml_fields.py` | Secure lxml parse, XPath `loop_query` iteration, per-column XPath mapping, nodecheck, namespace stripping, limit | tExtractXMLField | GOOD: reuses `_xml_io.secure_xml_parser` (`recover=False` fails loud -> reject). `limit=0` means read nothing vs `None`=unlimited |
| `ParseRecordSet` | `parse_record_set.py` | Expands a list-of-dicts (or JSON-string) column into rows, projecting `attribute_table` keys | tParseRecordSet | Converter keeps `t`-prefix (claims no engine) but engine exists; reconcile |
| `SchemaComplianceCheck` | `schema_compliance_check.py` | Vectorized nullability/type/length/date checks; violations to reject with `errorCode=8` and semicolon-joined `errorMessage` | tSchemaComplianceCheck | BUG: non-ASCII em-dash (U+2014) inside `logger` calls (lines 179, 196, 249, 331) violates ASCII-only rule. GAP: defers `customer`/`sub_string`/`fast_date_check`/`ignore_timezone` (warn-and-ignore). `bool` check accepts `{true,false,1,0,yes,no,''}` |
| `ConvertType` | `convert_type.py` | `AUTOCAST` + `MANUALTABLE` type coercion with per-row reject routing; `emptytonull` | tConvertType | BUG: MANUALTABLE with `in_col != out_col` leaves the ORIGINAL column in output (relies on schema projection to drop it). SMELL: per-row `_coerce_series` on single-element Series is O(n) slow vs a vectorized coerce-with-mask. Converter claims "no engine" but engine exists |
| `FilterColumns` | `filter_columns.py` | Schema-driven column projection; passthrough rows | tFilterColumns | `mode`/`keep_row_order` are engine-only keys; converter documents them |
| `FilterRows` | `filter_rows.py` | 15-operator vectorized simple filter + FUNCTION pre-transforms; advanced Java-expression filter via Java bridge; reject `errorMessage` | tFilterRow / tFilterRows | GOOD: advanced-filter bridge integration wraps `id_Float` in `java.lang.Float` (defeats Py4J float->Double); symmetric pop+restore keeps config immutable. BUG (low): dead/contradictory empty-input branch builds an unused `errorMessage` column then returns `reject=None` |
| `Replace` | `replace.py` | Simple (regex from glob/word/case + `strict_match`) and advanced (regex-pattern-in-`search_column`) search-and-replace | tReplace | SMELL: simple mode `.astype(str)` turns NaN/None into literal `'nan'`/`'None'`. Advanced `SEARCH_COLUMN`/`REPLACE_COLUMN` are regex/replacement literals, NOT column refs (despite XML tag names). NOTE: no dedicated engine test file found (coverage gap) |
| `SplitRow` | `split_row.py` | Row fan-out via `col_mapping` groups; resolves `flow.col` / quoted / numeric / literal expressions | tSplitRow | `_resolve_expression` handles the 4 expression shapes |
| `Denormalize` | `denormalize.py` | groupby non-target columns, concatenate target columns per delimiter; optional merge-dedup, `null_as_empty` | tDenormalize | `dropna=False` keeps null-key groups (Talend parity). Converter notes merge-flag/default mismatches |
| `Normalize` | `normalize.py` | Split one column on literal separator, explode to rows; discard-trailing -> trim -> dedupe order | tNormalize | GOOD: `discard_trailing_empty_str` strips only TRAILING empties via `_strip_trailing_empties` (mirrors Talaxie `lastNoEmptyIndex_`). GAP: engine strips ALL empties, not just trailing, when discard off; `escape_char`/`text_enclosure` unread |
| `UnpivotRow` | `unpivot_row.py` | Melt non-key columns into `pivot_key`/`pivot_value` pairs; String-coerce values; optional empty drop | tUnpivotRow | Community component, MEDIUM confidence |
| `PivotToColumnsDelimited` | `pivot_to_columns_delimited.py` | `pivot_table` by groupbys with aggfunc, restore first-seen column order, write delimited file + return main | tPivotToColumnsDelimited | Restores first-appearance column order (pivot_table sorts alphabetically); renders whole-number floats as ints (Talend convention). GAP: `advanced_separator`/`thousands`/`decimal`/`csv_option`/`escape_char`/`text_enclosure` not implemented |


## 5. Transform: code / python / java + flow ops

Four families: code-execution (Java bridge or Python `exec`), flow ops, the
pure-Python `PyMap` and `XMLMap`, and the SWIFT MT pipeline. The four code
components share `CodeComponentMixin` (`_code_component_mixin.py`) for
`_get_context_dict` and the D-11 hardened exec namespace (`_build_safe_builtins`
whitelist; `__import__`/`open`/`exec`/`eval`/`os`/`sys` deliberately absent).

### 5a. Code execution

| Engine class | File (`src/v1/engine/components/transform/`) | What it does | Talend equivalent | Parity notes / gaps |
| --- | --- | --- | --- | --- |
| `JavaComponent` | `java_component.py` | One-shot Java/Groovy execution via Py4J bridge; bidirectional context/globalMap sync; input passthrough (D-29) | tJava | Passthrough is a DataPrep data-flow semantic, not literal Talend. SMELL: ~7-line comment inaccurately describes `groovy_escape_expression` (which only escapes `$` in double-quoted strings) |
| `JavaRowComponent` | `java_row_component.py` | Per-row Java execution; compile-once on Java side; chunked Arrow transfer; NO reject (Talend parity); re-raises wrapped | tJavaRow | Verified against `tJavaRow_java.xml`: correctly has no reject and re-raises per-row errors |
| `PythonComponent` | `python_component.py` | One-shot Python `exec` in D-11 whitelisted namespace; passthrough | tPython / tPythonComponent | Dual namespace exposure (flat spread + nested `routines` dict) for converted-Talend backward-compat |
| `PythonRowComponent` | `python_row_component.py` | Per-row `exec`; compile-once (PERF-02); `errorMessage`-only reject schema; `die_on_error` gate | tPythonRow | Reject is a documented DataPrep extension with Talend-aligned `errorMessage`-only schema (`tFilterRow_java.xml`) |
| `PythonDataFrameComponent` | `python_dataframe_component.py` | Vectorized `exec` over full df; legacy-style | tPythonDataFrame | RISK: does NOT use the mixin or D-11 hardened namespace -- inherits real `__builtins__` (incl. `__import__`/`open`/`eval`). Re-implements `_get_context_dict` locally. No engine test seen (coverage gap) |

### 5b. Flow ops

| Engine class | File | What it does | Talend equivalent | Parity notes / gaps |
| --- | --- | --- | --- | --- |
| `Join` | `join.py` | Single-pass pandas `merge` with null-sentinel handling, inner/left-outer, first-match dedup, reject schema | tJoin | GOOD: `_NULL_SENTINEL` replace-then-reclassify makes null keys never match (SQL/Talend). Emits `join_key=[{input_column,lookup_column}]` matching engine reads. (Converter `needs_review` claiming UPPERCASE/`{main,lookup}` keys is STALE/wrong) |
| `Unite` | `unite.py` | UNION ALL vertical concat of all input flows | tUnite | Engine defaults match Talend UNION ALL |
| `Replicate` | `replicate.py` | Copies input to `main` + `output_1..N` flows | tReplicate | `output_count`/`die_on_error` are engine-only keys |
| `SortRow` | `sort_row.py` | Multi-column stable sort with per-column num/alpha/date key coercion | tSortRow | Converter documents `SORT`=type / `ORDER`=direction fix; external-sort gaps |
| `SampleRow` | `sample_row.py` | 1-based positional row selection via Talend range spec; main/reject split | tSampleRow | Converter keeps `t`-prefix (no-engine marker) but engine exists |
| `RowGenerator` | `row_generator.py` | Source: per-row expression eval (restricted `eval` + StringHandling shims + `{{java}}` re-fire per row); reject on error | tRowGenerator | GOOD: per-row `{{java}}` re-fire fixes "same random value on every row". SMELL: typo'd expression silently becomes a literal string (broad fallback masks bugs). Converter self-flags a schema-path mismatch -- verify engine reads output schema |
| `MemorizeRows` | `memorize_rows.py` | Passthrough writing last-N-row values to globalMap as `{id}_{col}_{offset}` | tMemorizeRows | Converter keeps `t`-prefix but engine exists |
| `AggregateSortedRow` | `aggregate_sorted_row.py` | Delegates to `AggregateRow` helpers; insertion-order groupby (`sort=False`) | tAggregateSortedRow | pandas groupby makes the "sorted input streaming" distinction a no-op; reuses `_SUPPORTED_FUNCTIONS`/`_build_agg_func` |
| `LogRow` | `log_row.py` | Passthrough logger: basic/table/vertical modes, all output via `logger.info` (ASCII) | tLogRow | GAP: `print_content_with_log4j=False` (System.out) deferred. Many display options unread |
| `Pagination` | `pagination.py` | BRAND NEW: 3-pass statement pagination (string-sort + page, per-page D/C aggregate, running balance) broadcast onto 1:1 `main` + `detail` flow; optional sign/abs/multipage derived columns | tPagination (non-standard) | RISK: sorts ALL keys as plain strings, no numeric option (intentional but a foot-gun). BUG: non-numeric amount/OPBAL raises uncaught `decimal.InvalidOperation`; no try/except in `_process`, so a dirty cell aborts the whole job regardless of `die_on_error`. No exact Talend contract to verify against |
| `ChangeFileEncoding` | `change_file_encoding.py` | OS-level chunked file re-encode; no data flow | tChangeFileEncoding | Utility (empty schema). Converter docstring/code drift on engine-impl status (engine exists) |
| `PyMap` | `py_map.py` | Pure-Python tMap analog: pandas joins (UNIQUE/FIRST/LAST/ALL, LOAD_ONCE/RELOAD), variables, output expressions, reject routing, size guards; `eval` in safe namespace with `_Row`/`_ContextView`/`_GlobalMapView` views | (tMap variant) | IMPROVEMENT: `RELOAD_AT_EACH_ROW` is O(n*m) `iterrows` + per-row `eval`, only soft-warned >10k x 10k. See the tMap doc for full join detail |
| `XMLMap` | `xml_map.py` | tXMLMap: lxml XPath extraction, namespace normalization, multi-loop cross-product, `expression_filter` via batch Java bridge, per-row REJECT | tXMLMap | GOOD: bracket-depth `split_steps` tokenizer preserves predicates. RISK: `expression_filter` fail-OPENS (includes all rows) when Java bridge unavailable -- documented native `ISNULL`/`ISNOTNULL` evaluator is absent. GAP: lookup/join connections and Document (allInOne) output log-and-ignore |

### 5c. SWIFT pipeline

| Engine class | File | What it does | Talend equivalent | Parity notes / gaps |
| --- | --- | --- | --- | --- |
| `SwiftBlockFormatter` | `swift_block_formatter.py` | Parse SWIFT MT blocks 1-5, layout-driven block4 field extraction, 61/86 pairing, pipe-delimited DataFrame | tSwiftBlockFormatter (non-standard) | SMELL: calls `logger.setLevel(logging.DEBUG)` on the module logger every execution -- a process-global side effect that floods logs (no reset) |
| `SwiftTransformer` | `swift_transformer.py` | YAML/JSON-config field mapping (direct/constant/parsed/calculated/transformation/python_expression), multi-tier lookups, MT940 balance/movement parsing | tSwiftDataTransformer (non-standard) | RISK (HIGH): `_evaluate_python_expression` exposes `__import__` inside `__builtins__`, so a crafted config `python_expression` can run arbitrary code -- contradicts the locked-down D-11 namespaces. Config loaded from context-resolved paths widens the trust surface. SMELL: `_init_transformer_config`/`_ensure_config_loaded` duplicate ~25 lines |

> NOTE: `src/v1/engine/components/transform/swift_transformer.py` (the engine
> component) is a DIFFERENT file from the same-named standalone CLI at
> `src/python_routines/swift_transformer.py`. They coincidentally share the class
> name `SwiftTransformer`; the CLI is not on the engine execution path.


## 6. Aggregate components

| Engine class | File (`src/v1/engine/components/aggregate/`) | What it does | Talend equivalent | Parity notes / gaps |
| --- | --- | --- | --- | --- |
| `AggregateRow` | `aggregate_row.py` | Group-by + global aggregation; 15 functions; optional Decimal financial-precision path; `_build_agg_func` factory raises on unknown function | tAggregateRow | BUG (HIGH): global (no-group-by) aggregation with `first`/`last` crashes -- `_global_aggregation` calls `getattr(series, "first")()` but pandas Series has no `.first()`/`.last()` (only GroupBy does) -> AttributeError. PARITY: `count` pinned to non-null count regardless of `ignore_null` (WR-10); `groupby(sort=False)` preserves first-seen order (WR-11); replicates Java `ArrayList.toString()` for `list_object` and `String.valueOf(null)=="null"` (BUG-AGG-001). `median` falls back to float (warn-once). Lossy mappings: `distinct->count_distinct`, `std_dev->std` |
| `UniqueRow` | `unique_row.py` | Split input into `unique`(main) / `duplicate`(reject) with per-column case sensitivity | tUniqRow / tUniqueRow / tUnqRow | GOOD: case-insensitive temp columns built lazily only when a key is case-insensitive AND string-typed; original casing retained in output. GAP: only a single global `case_sensitive` flag (Talend allows per-column; converter conservatively collapses to True on mixed). Always keeps FIRST occurrence (converter pins `keep="first"`); `keep="last"`/`False` branches reachable only via hand-written configs and would break Talend parity |


## 7. Context components

| Engine class | File (`src/v1/engine/components/context/`) | What it does | Talend equivalent | Parity notes / gaps |
| --- | --- | --- | --- | --- |
| `ContextLoad` | `context_load.py` | Loads context vars at runtime from a key/value(/type) DataFrame; three-phase (snapshot/load/validate); `LOAD_NEW`/`NOT_LOAD_OLD` policies; writes `{id}_NB_LINE`/`KEY_NOT_INCONTEXT`/`KEY_NOT_LOADED` globalMap vars; returns empty `main` | tContextLoad | Loads ALL incoming pairs unconditionally; policies (`DISABLE_*`, `LOAD_NEW`/`NOT_LOAD_OLD`) only gate warning/error messages (matches Talend advisory behavior). Has a `test_context_load_red.py` TDD red file |


## 8. Control components

Control components drive flow rather than data. `Die` always raises to terminate
the job. `Warn`/`Sleep` are pass-through. `Warn` and `Die` share module-level
helpers `_resolve_globalmap_vars` and `_log_at_priority` (copy-pasted across both
files, not a shared util).

| Engine class | File (`src/v1/engine/components/control/`) | What it does | Talend equivalent | Parity notes / gaps |
| --- | --- | --- | --- | --- |
| `Die` | `die.py` | Always raises `ComponentExecutionError` (with an `exit_code` attribute) to terminate; resolves `((Type)globalMap.get("k"))` patterns in message; logs at priority | tDie | SMELL: `exit_code` is dead/decoupled config -- the converter never emits it (only Talend `CODE` and `exit_jvm`), so every `tDie` reports exit code 1 regardless of `CODE`; `exit_jvm` accepted but a no-op. tDie halts the entire job via the executor's `exit_code` discovery |
| `Warn` | `warn.py` | Priority-rated log + globalMap message; pass-through | tWarn | Converter defines a `_PRIORITY_ITEMS` map that is dead (priority emitted as raw string code). Default code `42` (Talend) |
| `Sleep` | `sleep.py` | Pause then pass-through; finite/positive-duration guards | SleepComponent / tSleep | `pause_duration` only; no engine-gap entries (engine fully supports it) |
| `SendMailComponent` | `send_mail.py` | SMTP send with SSL/STARTTLS/auth/attachments; message builder + sender | tSendMail | SMELL: breaks the `_validate_config` contract -- it RETURNS a `List[str]` and never raises, so the lifecycle validation gate is a no-op; validation only fires because `_process` manually re-calls it. Also carries a dead `validate_config()` (bool) never called in `src/v1`. 12 engine-gap keys documented on the converter side |


## 9. Iterate components

Iterate components extend `BaseIterateComponent` (`base_iterate_component.py`),
which overrides `execute()` to prime an iterator and exposes an 8-hook lifecycle
(`prepare_iterations` / `set_iteration_globalmap` / `finalize` / etc.) that the
`Executor` drives per-iteration. ITERATE flows are control-flow edges that carry
no data; per-iteration variables go through `globalMap` (key
`{id}_CURRENT_ITERATION`). `FileList` (section 3b) is also a `BaseIterateComponent`.

| Engine class | File (`src/v1/engine/components/iterate/`) | What it does | Talend equivalent | Parity notes / gaps |
| --- | --- | --- | --- | --- |
| `FlowToIterate` | `flow_to_iterate.py` | Per-row globalMap puts driving body re-execution; key prefix is the upstream FLOW name (`{inputFlow}.{col}` per Talaxie javajet) | tFlowToIterate | BUG: `pd.NA`->None coercion incomplete -- `set_iteration_globalmap` uses `value is pd.NA`, but `to_dict('records')` on float64/object columns yields `float('nan')` not `pd.NA`, so a bare NaN is pushed to globalMap (and to the Java bridge) instead of None. Fix: use `pd.isna(value)` |
| `Foreach` | `foreach.py` | Iterate a static value list; sets `{cid}_CURRENT_VALUE` | tForeach | Produces typed `ForeachItem` dataclass with 1-based index |

> Both `Foreach` and `FlowToIterate` set `NB_LINE` directly on `self.stats` in
> `finalize()`, while `BaseIterateComponent.update_iteration_stats` also
> accumulates body `NB_LINE` across iterations. Confirm the Executor does not
> double-count (finalize overwrite vs accumulation order) when raising coverage.
> Iterate `die_on_error` defaults to `False` (`base_iterate_component.py`) whereas
> data components default `True` (`base_component.py`) -- intentional but worth
> verifying against Talend per-component defaults.


## 10. Cross-cutting bugs, risks, and coverage gaps

This section consolidates the highest-impact findings an extender should know
before touching these components or raising coverage. Severity is from the
code-reader fleet; "engine blocker" items prevent the package from importing or
running at all.

### Engine blockers (fix first; they hide everything else)

| Severity | File | Issue |
| --- | --- | --- |
| HIGH (blocker) | `src/v1/engine/engine.py:225-226` | `SyntaxError`: missing comma before `output_id=` in the `add_trigger()` call. Prevents `import src.v1.engine`, so pytest collection of any engine test fails. |
| HIGH (blocker) | `src/v1/engine/trigger_manager.py` | Class-scoping bug: `add_trigger` defined at module level (indent 0) so all subsequent methods become its local closures; `TriggerManager` has ONLY `__init__` as a method. Every Executor `set_component_status`/`get_triggered_components`/`should_fire_trigger` call raises `AttributeError` -- the entire OnSubjobOk/OnComponentOk/RunIf subsystem is non-functional. |

### Component correctness bugs

| Severity | Component / File | Issue |
| --- | --- | --- |
| HIGH | `AggregateRow` (`aggregate_row.py`) | Global (no-group-by) `first`/`last` crashes with AttributeError (Series has no `.first()`/`.last()`). |
| MEDIUM | `FlowToIterate` (`flow_to_iterate.py`) | Incomplete `pd.NA`->None coercion pushes raw NaN to globalMap/Java bridge for the common float/object null case. |
| MEDIUM | `ConvertType` (`convert_type.py`) | MANUALTABLE rename leaves the original input column in output; correctness depends on downstream schema projection. |
| MEDIUM | `Pagination` (`pagination.py`) | Non-numeric amount/OPBAL raises uncaught `decimal.InvalidOperation`, aborting the whole job regardless of `die_on_error`. |
| MEDIUM | `SchemaComplianceCheck` (`schema_compliance_check.py`) | Non-ASCII em-dash in `logger` calls violates the ASCII-only rule. |
| MEDIUM (Excel) | `FileInputExcel` (`file_input_excel.py`) | Streaming path is dead code (`self.chunk_size` undefined; `execution_mode` never set); large `.xlsx` always loads fully (OOM risk). |
| LOW | `FixedFlowInputComponent` (`fixed_flow_input.py`) | `ConfigurationError(self.id, message)` 2-arg call renders a tuple, breaking log-prefix convention. |
| LOW | `FileCopy` (`file_copy.py`) | Directory copy bypasses the friendly `replace_file` pre-check; raw `copytree` FileExistsError surfaces. |

### Security risks

| Severity | Component / File | Issue |
| --- | --- | --- |
| HIGH | `SwiftTransformer` (`swift_transformer.py`) | `python_expression` eval exposes `__import__` -> arbitrary code execution from config files. Should reuse `_build_safe_builtins`. |
| MEDIUM | `PythonDataFrameComponent` (`python_dataframe_component.py`) | Uses full real `__builtins__` (incl. `__import__`/`open`/`eval`) instead of the D-11 hardened namespace. |
| MEDIUM | `XMLMap` (`xml_map.py`) | `expression_filter` fail-OPENS (includes all rows) when the Java bridge is unavailable -- wrong row counts with no error. |
| LOW | `FileInputJSON` (`file_input_json.py`) | `urlopen` with no scheme allowlist / timeout / size cap (SSRF + hang). |

### Coverage gaps to close for the 95% floor

- No dedicated engine test file for `Replace` (`test_replace.py` not found) despite every other transform component having one.
- No engine test for `PythonDataFrameComponent`.
- `Pagination` lacks a non-numeric-amount/OPBAL test (the `InvalidOperation` crash path is uncovered).
- `FlowToIterate` tests likely use Int64/string extension dtypes; a plain float/object null column is needed to expose the NaN-vs-`pd.NA` gap.
- `AggregateRow` global path with `first`/`last` appears uncovered (the bug survives).
- `FileInputPositional` `trim_select` is ignored by the engine; `FileInputRaw._validate_config` return-vs-raise contract; the non-printable scrub mangling valid Latin-1 chars.
- `XMLMap` `expression_filter` no-bridge fail-open behavior should be asserted.
- File utility converters without engine-side counterparts in scope: confirm coverage of `FileCopy`/`FileDelete`/`FileExist`/`FileProperties`/`FileTouch`/`FileRowCount`/`FileUnarchive`.

### Test layout

Engine unit tests mirror the source tree under
`tests/v1/engine/components/{file,transform,aggregate,context,control,iterate,database}/`
with one `test_*.py` per component. Converter-side tests mirror under
`tests/converters/talend_to_v1/components/`. End-to-end/integration suites live
in `tests/integration/` and `tests/v1/engine/` (e.g. `test_full_pipeline.py`,
`test_iterate_e2e.py`). Java-bridge-dependent tests should carry
`@pytest.mark.java`; Oracle tests carry `@pytest.mark.oracle` (excluded from the
default coverage gate command).
