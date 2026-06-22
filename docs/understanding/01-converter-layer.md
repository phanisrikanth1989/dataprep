# Converter Layer

The converter (`src/converters/talend_to_v1/`) is the front half of the DataPrep
migration engine. It turns a Talend `.item` XML job definition into a V1 engine
JSON config that the runtime (`src/v1/engine/`) executes. This document is the
durable reference for engineers extending the converter and raising its test
coverage to the 95% per-module floor.

Three properties dominate the design:

- **Partial success.** A single malformed component never aborts a whole job
  conversion. Failures degrade to an `_unsupported` placeholder plus a warning.
- **Parity-first, defer-the-rest.** The converter is the *Talend-faithful* side
  of the migration. Where the V1 engine cannot reproduce a Talend behavior, the
  converter still extracts the parameter and emits a structured `needs_review`
  entry rather than silently dropping it.
- **Out-of-band reporting.** Warnings, review items, and validation results are
  attached to the output dict (`_warnings`, `_needs_review`, `_validation`)
  instead of being raised.

> ASCII-only is a hard project rule across logging, comments, and generated
> output. Keep it in mind when adding converters.

---

## 1. Package map

| Module | Role | LOC |
| --- | --- | --- |
| `converter.py` | 12-step pipeline orchestrator (`TalendToV1Converter.convert_file`), `convert_job` wrapper, `__main__` CLI | 528 |
| `xml_parser.py` | ElementTree parser: `.item` XML -> `TalendJob` (context, nodes, connections, routines, libraries) | 356 |
| `expression_converter.py` | Static API: `detect_java_expression`, `mark_java_expression`, `convert` | 229 |
| `trigger_mapper.py` | `map_triggers`: Talend trigger types -> V1 PascalCase names, tPrejob special case, RunIf conditions | 99 |
| `validator.py` | Four-layer post-conversion validator -> `ValidationReport` | 324 |
| `type_mapping.py` | `TALEND_TO_PYTHON` dict + `convert_type()` (single source of truth) | 25 |
| `components/base.py` | Dataclasses + `ComponentConverter` ABC + shared helpers | 250 |
| `components/registry.py` | Decorator-based `ConverterRegistry` (`REGISTRY` singleton) | 39 |
| `components/__init__.py` | Imports every category package to trigger auto-registration | 12 |
| `__init__.py` | Public API: re-exports `TalendToV1Converter`, `convert_job` | 6 |

Component converters live under `components/{file,transform,database,control,aggregate,context,iterate}/`.

### Public interfaces

```text
TalendToV1Converter().convert_file(filepath) -> dict
convert_job(input_path, output_path=None) -> dict
python -m src.converters.talend_to_v1.converter <input.item> [output.json]

XmlParser().parse(filepath) -> TalendJob
ExpressionConverter.detect_java_expression(value) -> bool
ExpressionConverter.mark_java_expression(value) -> str
ExpressionConverter.convert(expression) -> str
map_triggers(connections, component_ids) -> TriggerResult
validate_config(config) -> ValidationReport
convert_type(talend_type) -> str
REGISTRY.register(*names) decorator / REGISTRY.get(name)
```

---

## 2. The 12-step pipeline

`TalendToV1Converter.convert_file()` (`converter.py:51`) is the spine. The
orchestrator instance holds almost no mutable state: an `XmlParser` and an
`ExpressionConverter`, with every per-step concern in static helper methods.

| Step | What happens | Where |
| --- | --- | --- |
| 1 | Parse `.item` XML into a `TalendJob` | `XmlParser.parse` |
| 2 | Convert context variables (type mapping done during parse) | `_convert_context` |
| 3 | Dispatch each node through `REGISTRY.get(component_type)` to a converter | loop at `converter.py:82` |
| 4 | Per-component try/except -> `_unsupported` placeholder + warning on failure | `converter.py:97-107` |
| 5 | Parse FLOW connections into flow dicts | `_parse_flows` |
| 6 | Append flow names to source `outputs` / target `inputs` | `_update_component_connections` |
| 6b | Propagate upstream output schemas into downstream input schemas | `_propagate_input_schemas` |
| 7-8 | Map triggers, filtered to existing component ids | `map_triggers` |
| 9 | DFS over a bidirectional flow graph to group subjobs | `_detect_subjobs` |
| 10 | Detect whether the job requires the Java bridge | `_detect_java_requirement` |
| 11 | Run the four-layer validator | `validate_config` |
| 12 | Assemble config (+ `java_config`, `_validation`, `_warnings`, `_needs_review`) and return | `convert_file` tail |

The doc string in `converter.py:54-66` enumerates these steps; the numbering is
slightly compressed there (step 8 is a no-op because `trigger_mapper` already
filters skipped components).

### 2.1 Data flow in detail

1. `XmlParser.parse` reads the file with ElementTree and builds a `TalendJob`.
   Context params and schema columns are type-mapped via `convert_type` during
   parse, scalar string values are quote-stripped, `tLibraryLoad` nodes are
   skipped (libraries are extracted separately), and `UNIQUE_NAME` becomes the
   `component_id`.
2. Each node is dispatched through `REGISTRY.get(component_type)`. A found
   converter produces a `ComponentResult(component, warnings, needs_review)`; a
   missing converter or any raised exception yields an `_unsupported`
   placeholder (the exception path also appends a warning, logged with
   `exc_info`). Components accumulate into `components_list` and a
   `components_map` keyed by id.
3. `_parse_flows` turns FLOW/MAIN/REJECT/FILTER/UNIQUE/DUPLICATE/ITERATE
   connections into flow dicts (type lowercased). ITERATE parses
   `ENABLE_PARALLEL`/`NUMBER_PARALLEL` and emits an `engine_gap` `needs_review`
   when parallel is requested.
4. `_update_component_connections` appends flow names to `source.outputs` and
   `target.inputs`.
5. `_propagate_input_schemas` walks flows and copies the upstream
   `schema.output` (or per-connector `schema.outputs[TYPE]`, uppercase
   normalized) into the downstream `schema.input`, plus a per-flow
   `schema.inputs[flow_name]` map for multi-input components.
6. `map_triggers` builds trigger dicts filtered to existing component ids.
7. `_detect_subjobs` runs DFS over a *bidirectional* flow adjacency graph to
   group connected components (the bidirectional list is a deliberate WR-04 fix
   to avoid O(N*E) reverse-edge scans).
8. `_detect_java_requirement` scans component types against
   `_JAVA_COMPONENT_TYPES` and recursively searches config strings for
   `{{java}}` markers.
9. The config dict is assembled with `java_config`; `validate_config` attaches
   `_validation`; `_warnings` and `_needs_review` are attached if present.

The output dict is returned, and written to JSON if `output_path` is given.

### 2.2 Closed-world connector / trigger sets (extension hazard)

Two frozensets gate which connections survive:

```python
# converter.py:27
_FLOW_CONNECTOR_TYPES = frozenset({
    "FLOW", "MAIN", "REJECT", "FILTER",
    "UNIQUE", "DUPLICATE", "ITERATE",
})
```

```python
# trigger_mapper.py:14
_TRIGGER_TYPE_MAP = {
    "SUBJOB_OK": "OnSubjobOk",
    "SUBJOB_ERROR": "OnSubjobError",
    "COMPONENT_OK": "OnComponentOk",
    "COMPONENT_ERROR": "OnComponentError",
    "RUN_IF": "RunIf",
}
```

Both are closed-world: any connector type not in these sets is **silently
dropped** from flows/triggers. When adding components that introduce new
connector or trigger types, these sets must be extended or the connection
vanishes with no warning. (Open question flagged by the readers: the newer
Oracle/MSSQL/Pagination components register cleanly via `REGISTRY`, but should be
re-verified that they introduce no new connector/trigger type these sets miss.)

---

## 3. XML parsing (`xml_parser.py`)

`XmlParser.parse(filepath) -> TalendJob`. Behaviors that matter when writing
converters or test fixtures:

- Skips `tLibraryLoad` nodes (libraries are extracted into `TalendJob.libraries`
  separately).
- Pops `UNIQUE_NAME` to become `component_id`.
- Coerces `CHECK` params to `bool`.
- Collects `TABLE` params as `elementValue` lists of `{elementRef, value}` dicts.
- Strips `EXTERNAL` fields.
- **Quote handling:** scalar string params are quote-stripped during parse
  (`_parse_element_params` / `_parse_context` call `_strip_quotes`). TABLE
  *values* are left raw — the per-component TABLE parsers re-strip them.

`TalendJob` is the structured parse result: `job_name` (file stem), `job_type`,
`default_context`, `context`, `nodes`, `connections`, `routines`, `libraries`.

> Known smell: scalar values are quote-stripped twice (`_strip_quotes` in the
> parser, then again by `_get_str` in `base.py`). Harmless for typical inputs
> but obscures where canonicalization actually happens and can mis-handle
> legitimately quote-delimited literals. Converter unit tests build `TalendNode`
> fixtures directly with raw param dicts, so the parser-side pre-stripping is
> *not* exercised at the converter test layer.

---

## 4. Type mapping (`type_mapping.py`)

The single source of truth for Talend-type -> Python-type translation. Used by
`base._parse_schema` and throughout the converters at the point each `id_*` type
is emitted.

```python
TALEND_TO_PYTHON = {
    "id_String": "str",      "id_Integer": "int",     "id_Long": "int",
    "id_Double": "float",    "id_Float": "float",     "id_Boolean": "bool",
    "id_Date": "datetime",   "id_BigDecimal": "Decimal", "id_Object": "object",
    "id_Character": "str",   "id_Byte": "int",        "id_Short": "int",
}

def convert_type(talend_type: str) -> str:
    return TALEND_TO_PYTHON.get(talend_type, "str")  # unknown -> "str"
```

Unknown types default to `"str"`. The downstream engine and Java bridge work in
a fixed set of 7 Python type strings (`str`, `int`, `float`, `bool`, `datetime`,
`Decimal`, `object`), so this map is the contract boundary.

---

## 5. The `ComponentConverter` ABC and registry

### 5.1 The contract (`components/base.py`)

Every component converter subclasses `ComponentConverter`:

```text
ComponentConverter.convert(node, connections, context) -> ComponentResult
```

The ABC supplies shared helpers so each `convert()` is a thin, consistent
mapping:

- Typed param getters: `_get_str`, `_get_bool`, `_get_int`,
  `_get_int_or_context` (preserves `context.VAR` references as raw strings for
  runtime resolution), `_get_param`.
- `_parse_schema(node, connector='FLOW')` -> list of column dicts (types via
  `convert_type`, date patterns via `_convert_date_pattern`).
- `_convert_date_pattern(java_pattern) -> strftime` (placeholder token
  substitution; see warnings in section 9).
- `_incoming` / `_outgoing` connection filters.
- `_build_component_dict(node, type_name, config, schema)` -> the uniform V1
  component dict `{id, type, original_type, position, config, schema, inputs, outputs}`.

Dataclasses: `SchemaColumn`, `TalendNode`, `TalendConnection`, `ComponentResult`.
`ComponentResult` bundles the component dict with `warnings[]` and
`needs_review[]` lists that bubble up to the orchestrator.

`TalendNode` carries `component_id`, `component_type`, a flat `params` dict, a
`schema` dict keyed by connector, `position`, and the `raw_xml` Element (the
latter is used only by the complex `tMap`/`tXMLMap` converters, which parse
nested `nodeData`/`MapperData` rather than the flat params dict).

### 5.2 The registry (`components/registry.py`)

```python
@REGISTRY.register("tFileInputDelimited")   # one or more Talend type names
class FileInputDelimitedConverter(ComponentConverter):
    def convert(self, node, connections, context): ...
```

`ConverterRegistry.register(*names)` is a class decorator that **raises
`ValueError` on duplicate registration** (`registry.py:20-24`), surfacing
accidental double-registration at import time. The orchestrator triggers
population via a side-effect import (`from . import components as _components`),
and each category `__init__.py` imports its modules so the decorators fire before
the registry is ever consulted.

> Registration import style is inconsistent across categories: `aggregate/` and
> `control/` import converter *classes*, while `database/`, `context/`, and
> `iterate/` import *modules*. Both trigger `@REGISTRY.register`; standardize on
> module imports with `noqa` when touching these files.

### 5.3 The convert() skeleton convention

Every converter follows the same numbered-section layout (highly consistent
across ~30+ converters):

```text
1. Core params  ->  2. Advanced params  ->  3. TABLE params
->  4. Framework params (tstatcatcher_stats, label) ALWAYS LAST
->  5. Schema (_parse_schema)  ->  6. needs_review (engine_gap) entries
->  7. _build_component_dict  ->  return ComponentResult
```

Framework params are appended last by convention (documented S-10). Defensive
`isinstance(list/dict)` guards precede every TABLE parse. Phantom params (params
not present in the component's `_java.xml`) are explicitly enumerated in
docstrings as REMOVED.

---

## 6. Expression conversion and `{{java}}` marking (`expression_converter.py`)

A stateless, all-static utility class. There are **two distinct paths** with
different philosophies, and the divergence between them is the single most
important correctness concern in the converter.

### 6.1 `detect_java_expression` + `mark_java_expression` (the safe path)

This is what file and transform converters use on path/value/array fields.
`detect_java_expression` applies aggressive regex heuristics (routine calls,
method calls, operators, casts, `globalMap`, comments) with false-positive
carve-outs for URLs, POSIX/UNC paths, negative numbers, and hyphenated IDs.
`mark_java_expression` prepends `{{java}}` so the engine defers evaluation to the
Java bridge (`expression_converter.py:206`). This is the design the rest of the
pipeline relies on: **do not interpret Java; tag it and let the bridge run it.**

> Known bug (medium): `detect_java_expression` treats `-` as a Java operator, so
> a hyphenated string that is not the specific 2-segment pattern
> `^[a-zA-Z0-9]+-[a-zA-Z0-9-]+$` (e.g. `a.b-c`, `_id-foo`) gets marked
> `{{java}}` and is needlessly round-tripped through the bridge. Aggressive by
> design, but worth a carve-out review — false markers can fail if the literal
> is not valid Java.

### 6.2 `convert` (the lossy path — RunIf conditions only)

`ExpressionConverter.convert(expression)` does direct Java-to-Python string
rewrites. It is used by `trigger_mapper.map_triggers` for RunIf conditions
(`trigger_mapper.py:83`) and **nowhere else**. This is a deliberate parity
divergence: instead of marking the condition `{{java}}` and deferring it, the
converter naively rewrites it.

The rewrites are lossy and have confirmed defects:

- **High-severity bug:** after the null-check regexes handle `!= null`, the
  blanket `expression.replace('!', ' not ')` (line 212) rewrites any surviving
  inequality such as `a != b` into `a  not = b`, which is invalid Python.
  Non-null inequality RunIf conditions therefore convert to broken expressions.
- `.equalsIgnoreCase(` -> `.lower() == str(` leaves an unbalanced expression.
- `.length()` -> `.__len__()` and `.contains(` -> ` in ` produce wrong operand
  ordering.
- `StringHandling.UPCASE(` / `DOWNCASE(` / `TRIM(` all collapse to `str(`,
  losing the upper/lower/strip semantics entirely.

For RunIf parity the readers recommend marking `{{java}}` (like the rest of the
pipeline) rather than relying on this rewriter. Until that changes, RunIf
conditions remain a silent-correctness hazard, and `map_triggers` already emits a
`needs_review` entry flagging them for manual review.

> The orchestrator constructs `self._expr_converter` in `__init__`
> (`converter.py:45`) but never uses it — component converters and
> `trigger_mapper` each instantiate their own. Dead member; remove or wire
> through.

---

## 7. Trigger mapping (`trigger_mapper.py`)

`map_triggers(connections, component_ids) -> TriggerResult`. It:

- Translates trigger connector types via `_TRIGGER_TYPE_MAP` to V1 PascalCase
  names.
- **Filters** to triggers where both source and target are in `component_ids`
  (so a trigger to a skipped/unsupported component is dropped with a debug log).
- **tPrejob special case:** forces *all* outgoing triggers from a `tPrejob`
  source to `OnComponentOk` (`trigger_mapper.py:70-72`) so the prejob runs
  first. This mirrors legacy `complex_converter` behavior (cited at
  `converter.py:428-434`).
- Extracts RunIf conditions via `ExpressionConverter.convert()` and attaches a
  `needs_review` entry (see section 6.2).

`TriggerResult` carries `triggers`, `warnings`, and `needs_review`.

---

## 8. Validation (`validator.py`)

`validate_config(config) -> ValidationReport`. Four layers run in sequence and
aggregate `ValidationIssue`s by severity. `valid == (error_count == 0)`; warnings
and infos do not fail validation.

| Layer | Function | Checks |
| --- | --- | --- |
| Reference integrity | `_validate_reference_integrity` | flow/trigger endpoints reference real components; flags orphans |
| tMap (Map) rules | `_validate_tmap` | Map-specific structural rules |
| Expression quality | `_validate_expressions` | scans for leftover Java method calls via `_JAVA_METHOD_PATTERN` |
| Conversion quality | `_validate_conversion_quality` | conversion-quality markers |

The leftover-Java scan uses a regex of Java method names
(`substring|equals|equalsIgnoreCase|indexOf|...`) to catch expressions that
should have been marked `{{java}}` or rewritten but slipped through as raw Java.

`ValidationReport` (`valid`, `issues`, `summary`) is attached to the output dict
as `_validation`.

> Risk (medium): the reference-integrity layer flags **every** component with no
> flow or trigger as an orphan warning. Legitimately standalone single-component
> jobs (a lone `tFixedFlowInput`, a single `tJava` prejob) produce noise warnings
> on otherwise-valid configs. There is no allowance for intentionally
> unconnected nodes.

---

## 9. Date-pattern conversion (`base._convert_date_pattern`)

Java `SimpleDateFormat` -> Python `strftime`. The implementation is a *good*
non-obvious design: it uses NUL-delimited placeholder tokens
(`Java token -> \x00i\x00 -> strftime`) to avoid overlapping-token corruption
between e.g. `MM` and `mm`, `ss` and `SSS`. A naive sequential replace would
corrupt these.

Two latent bugs to be aware of when extending:

- **Incomplete token table (high):** `_DATE_TOKENS` lacks `MMM`/`MMMM` (month
  name), `EEE`/`EEEE` (day name), and standalone single `d`/`M`/`D`/`u`/`z`/`Z`/`G`.
  Verified: `'EEE, d MMM yyyy'` -> `'EEE, d %mM %Y'` (MMM half-matched to `%m`
  leaving a stray `M`; `EEE` and single `d` left literal). Any schema column with
  a textual or single-letter Java date pattern silently yields a wrong/garbage
  Python pattern. These edge cases are almost certainly untested.
- **`SSS` vs `%f` (low):** `SSS` maps to `%f`, but Java `SSS` is milliseconds (3
  digits) while Python `%f` is microseconds (6 digits). Sub-second patterns are
  off by a factor of 1000 in width.

Note the related inconsistency in file_input_excel: schema-column date patterns
are converted to strftime via `_convert_date_pattern`, but `DATESELECT`
intentionally keeps Java patterns raw ("engine handles conversion internally").
Two contracts coexist; downstream must know which fields are pre-converted.

---

## 10. Component converter catalog

Component converters are registered by Talend type name and grouped into seven
categories. A recurring convention: **unimplemented** components (those with no
V1 engine class) keep the Talend `t` prefix as their emitted V1 `type` (e.g.
`tConvertType`, `tReplace`, `tMemorizeRows`), while implemented ones use clean
PascalCase (`Join`, `SortRow`, `Normalize`). This appears to be a deliberate
"unimplemented marker" but is undocumented and brittle if downstream code
dispatches on `type`.

Another convention: known parity gaps are encoded as structured `needs_review`
entries with a severity tag (`engine_gap`, `output_shape_change`,
`needs_review`) rather than dropped silently. Talend typos are preserved verbatim
as config keys to match `_java.xml` param names (`sub_directroy`,
`source_derectory`, `encording`, `auto_szie_setting`) — correct for round-trip
fidelity, a smell for engine authors.

### 10.1 File components (`components/file/`)

Converts `tFileInput*`/`tFileOutput*`/`tFile*` utilities plus `tFixedFlowInput`
and `tSetGlobalVar`. TABLE params (mappings, formats, sheet lists) are parsed
into lists of dicts. Path/stream/value fields are passed through
`mark_java_expression`.

| Talend type | Emitted type | Notes |
| --- | --- | --- |
| `tFileInputDelimited` | `FileInputDelimited` | 31 params; stride-2 TRIMSELECT/DECODE_COLS |
| `tFileInputExcel` | `FileInputExcel` | 30 params; sheetlist/trimselect/dateselect; clears password |
| `tFileInputPositional` | `FileInputPositional` | FORMATS/TRIMSELECT; `filepath` key |
| `tFileInputFullRow` | `FileInputFullRowComponent` | whole-row-as-string |
| `tFileInputJSON` | `FileInputJSON` | mode-dependent MAPPING selection |
| `tFileInputXML` | `FileInputXML` | stride-3 MAPPING; marks filepath as java |
| `tFileInputMSXML` | `tFileInputMSXML` (no engine) | SCHEMAS stride-3 |
| `tFileInputProperties` | `tFileInputProperties` (no engine) | `.properties`/`.ini` |
| `tFileInputRaw` | `FileInputRaw` | string/bytearray/inputstream modes |
| `tFileOutputDelimited` | `FileOutputDelimited` | marks streamname+filepath as java |
| `tFileOutputExcel` | `FileOutputExcel` | 16 engine_gap entries; preserves typo `SZIE` |
| `tFileOutputPositional` | `FileOutputPositional` | flags engine NOT in COMPONENT_REGISTRY |
| `tFileOutputXML` / `tAdvancedFileOutputXML` | `FileOutputXML` / (no engine) | stride-1/2/5 parsers |
| `tFileOutputEBCDIC` | `tFileOutputEBCDIC` (no engine) | enterprise-only, LOW confidence |
| `tFileArchive` | `FileArchiveComponent` | MASK stride-1; clears password |
| `tFileUnarchive` | `FileUnarchiveComponent` | **KEEPS password** (security inconsistency) |
| `tFileCopy` | `FileCopy` | copy/move/rename; 8 engine_gap |
| `tFileDelete` | `FileDelete` | file/folder/auto |
| `tFileExist` | `FileExistComponent` | `file_name` vs engine `file_path` |
| `tFileList` | `tFileList` (no engine) | iterate-style; FILES stride-1 |
| `tFileProperties` | `FileProperties` | metadata/MD5 |
| `tFileTouch` | `FileTouch` | `createdir` vs engine `create_directory` |
| `tFileRowCount` | `FileRowCount` | encoding default mismatch flagged |
| `tFixedFlowInput` | `FixedFlowInputComponent` | single/intable/inline; marks VALUES as java |
| `tSetGlobalVar` | `SetGlobalVar` | VARIABLES KEY/VALUE stride-2; marks VALUEs; `requires_java_bridge=True` |

File-component parity notes:

- Defaults are taken from each component's `_java.xml` (e.g. ENCODING default
  `ISO-8859-15` not UTF-8; `TRIMALL` default True for positional/MSXML).
- **Security inconsistency (high risk):** `file_unarchive` carries `PASSWORD`
  into JSON (`config['password'] = self._get_str(node, 'PASSWORD', '')`),
  contradicting `file_archive` and `file_input_excel`, which hardcode
  `config['password'] = ''`. `file_output_excel` also keeps PASSWORD. The
  decrypt/encryption password leaks into the generated job config.
- **Config-key drift:** the path field is named inconsistently — `filename`
  (json/fullrow/raw/msxml/properties/output_excel/output_xml) vs `filepath`
  (delimited/positional/xml/output_delimited/output_positional). Engine consumers
  must special-case per component.
- **Inconsistent `{{java}}` marking:** delimited input/output and xml input mark
  their path/stream fields, but excel/json/raw and most utility components do
  not. A `FILENAME` containing a Java concat expression in `tFileOutputExcel`
  will not be tagged, and this gap is not captured by any `needs_review`.

### 10.2 Transform components (`components/transform/`)

Roughly 34 converters. `tMap` and `tXMLMap` are the two genuinely complex
members — they parse nested `nodeData`/`MapperData` XML from `raw_xml` rather
than the flat params dict.

| Talend type | Emitted type | Notes |
| --- | --- | --- |
| `tMap` | `Map` | parses MapperData -> inputs.main/lookups/variables/outputs + per-flow `schema.inputs`; `{{java}}` with CRLF collapse |
| `tXMLMap` | `XMLMap` | recursive input/output trees; EMF-path -> XPath; single/multi-loop XPath rewriting |
| `tJoin` | `Join` | JOIN_KEY/LOOKUP_COLS stride-2; **stale/incorrect needs_review** (see below) |
| `tFilterRow` / `tFilterRows` | `FilterRows` | stride-4 CONDITIONS; FUNCTION substring translation; FILTER/REJECT schema |
| `tSortRow` | `SortRow` | stride-3 CRITERIA; SORT=type/ORDER=direction |
| `tAggregateSortedRow` | `AggregateSortedRow` | stride-2 GROUPBYS + state-machine OPERATIONS (optional IGNORE_NULL) |
| `tNormalize` / `tDenormalize` | `Normalize` / `Denormalize` | escape/enclosure/merge engine gaps |
| `tLogRow` | `LogRow` | RADIO groups + stride-1 LENGTHS |
| `tJava` / `tJavaRow` | `JavaComponent` / `JavaRowComponent` | java_code/imports passthrough |
| `tPython` / `tPythonRow` / `tPythonDataFrame` | Python* | CODE/IMPORT; XML linebreak decode |
| `tExtractDelimitedFields` | `ExtractDelimitedFields` | `fieldseparator` vs engine `field_separator` |
| `tExtractJSONFields` | `ExtractJSONFields` | stride-4 XPath + stride-2 JSONPath |
| `tExtractPositionalFields` | `ExtractPositionalFields` | stride-4 FORMATS w/ ALIGN map |
| `tExtractRegexFields` | `tExtractRegexFields` (no engine) | REGEX double-backslash unescape |
| `tExtractXMLField` | `ExtractXMLField` | stride-3 MAPPING |
| `tFilterColumns` / `tReplicate` / `tUnite` | `FilterColumns` / `Replicate` / `Unite` | no unique params |
| `tReplace` | `tReplace` (no engine) | stride-7 SUBSTITUTIONS + stride-4 ADVANCED_SUBST |
| `tSplitRow` | `SplitRow` | COL_MAPPING repeated-elementRef row templates |
| `tUnpivotRow` | `UnpivotRow` | stride-1 ROW_KEYS; community component, MEDIUM confidence |
| `tPivotToColumnsDelimited` | `PivotToColumnsDelimited` | 16 params + stride-1 GROUPBYS |
| `tMemorizeRows` / `tSampleRow` / `tHashOutput` / `tParseRecordSet` | t-prefixed (no engine) | |
| `tSchemaComplianceCheck` | `SchemaComplianceCheck` | stride-5 CHECKCOLS + stride-2 EMPTY_NULL_TABLE |
| `tChangeFileEncoding` | `ChangeFileEncoding` | utility; docstring/code drift on engine status |
| `tRowGenerator` | `RowGenerator` | SOURCE (no input); VALUES ARRAY `{{java}}`; self-flags schema-path mismatch |
| `tConvertType` | `tConvertType` | stride-2 MANUALTABLE; emits "no engine" despite engine file existing |
| `tSwiftDataTransformer` | `SwiftTransformer` | minimal config_file/die_on_error |

Transform parity/correctness notes:

- **TABLE parsing has two idioms.** Most converters use *fixed-stride* slicing
  (join stride-2, filter stride-4, replace stride-7). Where a trailing field is
  optional, a *state-machine flush-on-key* parser is used instead
  (`aggregate_sorted_row` OPERATIONS, `split_row` COL_MAPPING) so an absent
  `IGNORE_NULL` does not desynchronize the rows. The fixed-stride parsers
  silently drop a whole row if any expected `elementRef` is absent/reordered —
  a real risk for hand-edited or sparse `.item` TABLEs.
- **`tMap` is the parity-critical converter.** It emits
  `inputs.main`/`inputs.lookups`/`variables`/`outputs` plus per-flow
  `schema.inputs` (`map.py:348-353`) so the engine can build a complete
  declared-type map for the joined DataFrame, avoiding the Java-bridge strict
  boundary rejection. `_java_expr` collapses CRLF/CR/LF to a single space to dodge
  Groovy Automatic Semicolon Insertion on multi-line injected expressions.
- **`tJoin` carries factually wrong `needs_review` (bug).** Entries claim the
  engine reads UPPERCASE `USE_INNER_JOIN`/`JOIN_KEY` and `{main, lookup}` keys,
  but the engine (`src/v1/engine/components/transform/join.py`) reads lowercase
  `use_inner_join`/`join_key` with `{input_column, lookup_column}` — exactly what
  the converter emits. These entries describe a non-existent gap and should be
  deleted/corrected.
- **`tRowGenerator` self-claims a runtime break.** Its `needs_review`
  (`row_generator.py:127-134`) asserts the engine reads schema via
  `config['schema']['output']`, but `_build_component_dict` always nests schema
  at the *top level* of the component dict, never inside `config`. If accurate
  this is a live break for tRowGenerator output; warrants engine verification.
- **`tConvertType`/`tChangeFileEncoding` docstring drift.** Both emit "no engine
  implementation" `needs_review`/docstrings, yet engine files
  (`convert_type.py`, `change_file_encoding.py`) exist. The `t`-prefixed type for
  `tConvertType` may also cause dispatch to miss the engine class. Reconcile.
- `tXMLMap` XPath rewriting avoids `ancestor::` by inferring the loop element's
  full path and emitting `../` relative traversal (handles `tFileInputXML`
  serializing only the matched subtree). Uses `str.removeprefix()` (D-76) instead
  of `lstrip()` to avoid character-class stripping bugs.

### 10.3 Database components (`components/database/`)

Eleven converters: full Oracle support plus a minimal SQL Server pair. Most are
newer additions that plug in purely via the registry.

| Talend type(s) | Converter | Notes |
| --- | --- | --- |
| `tOracleConnection`, `tDBConnection` | OracleConnectionConverter | 28 params; SID/Service/RAC/OCI/Wallet |
| `tOracleInput` | OracleInputConverter | `_parse_convert_xmltype` + `_parse_trim_column` |
| `tOracleOutput` | OracleOutputConverter | TABLESCHEMA -> `schema_db` (CR-01) |
| `tOracleRow` | OracleRowConverter | `_parse_prepared_params` with WR-03/WR-04 validation |
| `tOracleSP` | OracleSPConverter | stride-6 `_parse_sp_args` |
| `tOracleBulkExec` | OracleBulkExecConverter | SQL*Loader, 40 params; `_parse_options_table` |
| `tOracleClose`/`tOracleCommit`/`tOracleRollback` | (3 converters) | 3-4 params each |
| `tMSSqlConnection` | MSSqlConnectionConverter | 18 params; `_extract_password` strips `enc:` |
| `tMSSqlInput` | MSSqlInputConverter | DB_SCHEMA -> `schema_db`; `_parse_trim_column` (duplicated) |

Database parity/correctness notes:

- **`tDBConnection` is forced to Oracle (risk, medium).** It shares
  `OracleConnectionConverter` and is unconditionally given Oracle defaults
  (`CONNECTION_TYPE=ORACLE_SID`, port 1521, `ORACLE_18`, `jdbc:oracle:thin`).
  A generic/non-Oracle `tDBConnection` job is silently converted with Oracle
  semantics and **no** `needs_review` flagging the assumption.
- **Best-in-subsystem input validation:** `oracle_row._parse_prepared_params`
  drops incomplete bind groups (WR-03) and rejects non-numeric / `< 1`
  `parameter_index` (WR-04), piping human-readable warnings into
  `ComponentResult.warnings` instead of letting the engine crash on
  `int('abc')`. Worth replicating.
- **Duplicated parsers:** `_parse_trim_column` is duplicated across
  `oracle_input.py` and `mssql_input.py`; the same KEY/VALUE stride-2 parsing is
  re-implemented in `flow_to_iterate` and `send_mail`. A shared
  `base._parse_table(raw, fields)` would remove ~6 near-identical parsers.
- Canonical-key remapping aligns divergent Talend param names (`TABLESCHEMA`,
  `DB_SCHEMA`) onto a single engine key (`schema_db`).

### 10.4 Control components (`components/control/`)

Nine converters with `__all__`.

| Talend type | Converter | Notes |
| --- | --- | --- |
| `tDie` | DieConverter | message/code/priority/exit_jvm; defaults `the end is near`/`4`/`5`; 3 engine gaps |
| `tWarn` | WarnConverter | defines `_PRIORITY_ITEMS` (declared but unused dead constant) |
| `tLoop` | LoopConverter | mutually exclusive FORLOOP/WHILELOOP radios |
| `tSleep` | SleepConverter | `pause_duration` only; no engine-gap entries |
| `tParallelize` | ParallelizeConverter | params inferred from docs (no `_java.xml`) |
| `tPrejob` / `tPostjob` | (2 converters) | 0 unique params |
| `tRunJob` | RunJobConverter | 22 params; `_parse_context_params` + `_parse_jvm_arguments` |
| `tSendMail` | SendMailConverter | 29 params; attachments/headers/configs; AUTH_MODE/NEED_AUTH compat; 12 engine gaps |

### 10.5 Aggregate components (`components/aggregate/`)

| Talend type(s) | Converter | Notes |
| --- | --- | --- |
| `tAggregateRow` | AggregateRowConverter | `_FUNCTION_MAP` normalization; state-machine OPERATIONS; stride-2 GROUPBYS |
| `tUniqueRow` / `tUniqRow` / `tUnqRow` | UniqueRowConverter | stride-3 UNIQUE_KEY; per-column -> global `case_sensitive` derivation |

- Lossy aggregate mappings are documented: `distinct -> count_distinct`
  (CONV-AGG-001), `std_dev -> std` (CONV-AGG-002). Unknown functions pass
  through lowercased with a warning.
- **Inaccurate parity warning (bug, medium):** `_normalise_function` maps
  `union -> union` (passthrough), but the emitted warning text says "no engine
  equivalent ... will fall back to sum"; the converter never produces `sum`, and
  an in-file comment claims union is "now implemented in engine." The map, the
  warning, and the comment contradict each other; reconcile.
- `tUniqueRow` collapses Talend per-column case sensitivity into a single global
  flag (conservative True on mixed inputs) — a documented gap.

### 10.6 Context components (`components/context/`)

| Talend type | Converter | Notes |
| --- | --- | --- |
| `tContextLoad` | ContextLoadConverter | DIEONERROR/DIE_ON_ERROR fallback; 6 per-feature engine-gap entries |

### 10.7 Iterate components (`components/iterate/`)

| Talend type | Converter | Notes |
| --- | --- | --- |
| `tForeach` | ForeachConverter | stride-1 VALUES table |
| `tFlowToIterate` | FlowToIterateConverter | stride-2 MAP table gated on `default_map` |

- ITERATE parallelism is parsed and preserved in the flow dict but flagged
  `engine_gap` because the engine runs sequentially (correct results, slower).

---

## 11. Patterns worth preserving

- **Side-effect package import** to trigger decorator auto-registration before
  the registry is consulted.
- **Decorator registry with fail-fast duplicate detection** at import time.
- **Defensive per-component try/except** converting any failure into an
  `_unsupported` placeholder so one bad node never aborts a job. Combined with
  the `_warnings`/`_needs_review`/`_validation` out-of-band channels this yields
  a partial-success model well-suited to bulk migration.
- **Static-method-only utility classes** and static pipeline-step helpers — the
  orchestrator instance holds almost no mutable state.
- **Placeholder-based token substitution** in `_convert_date_pattern`.
- **Bidirectional adjacency list** for subjob DFS (WR-04).
- **Back-compat dual-write** of `schema.input` (legacy) and
  `schema.inputs[flow_name]` (per-connector) for multi-input components
  (ENG-CR-04).
- **Structured `needs_review`** entries (`engine_gap` / `output_shape_change`)
  instead of silently dropping unconsumed params.

---

## 12. Test layout and coverage targets

Converter unit tests mirror the source tree under
`tests/converters/talend_to_v1/`:

- Pipeline/core: `test_converter.py` (orchestrator, `TalendJob`/`TalendNode`
  fixtures, REGISTRY mocking), `test_xml_parser.py`, `test_expression_converter.py`
  (raises `expression_converter` coverage to >=95%; covers detect/mark/convert),
  `test_trigger_mapper.py`, `test_validator.py`, `test_type_mapping.py`,
  `test_registry.py`, `test_base.py`, `test_iterate_connection_extraction.py`.
- Components: one `test_*.py` per converter under
  `tests/converters/talend_to_v1/components/{file,transform,database,control,aggregate,context,iterate}/`.

The module-level `_parse_*` TABLE parsers are private but unit-tested directly,
and the `tMap`/`tXMLMap` `nodeData` parsing is the highest-value unit to assert
on (group boundaries, incomplete trailing groups, `{{java}}` marking, XPath loop
rewriting). `batch_convert.py` is a bulk-conversion harness over the sample
`.item` files (commits de8eae0 / 464d2f9 added Talend XML + JSON samples), useful
for regression.

### Known coverage gaps (for the 95% push)

- `test_expression_converter` covers `convert()` rewrites but likely does **not**
  assert a surviving `!=` (non-null) RunIf condition — the broken path appears
  untested (section 6.2).
- `_convert_date_pattern` edge cases (`MMM`/`EEE`, `SSS` width) are almost
  certainly untested given the bugs in section 9.
- No converter-level test file was seen for several file utilities
  (`file_copy`/`file_delete`/`file_exist`/`file_list`/`file_properties`/
  `file_touch`/`file_row_count`/`file_unarchive`).
- No converter test for the `union`-function warning text or a non-Oracle
  `tDBConnection` scenario.
- Per `CLAUDE.md`: any change touching `{{java}}` resolution should add
  `@pytest.mark.java` live-bridge tests; the converter-side detection here is
  unit-tested only.

---

## 13. Open questions for extenders

1. Should RunIf conditions be marked `{{java}}` and deferred to the bridge
   (consistent with the rest of the pipeline) instead of passing through the
   lossy `ExpressionConverter.convert()` rewriter?
2. Do the newer Oracle/MSSQL/Pagination components introduce any connector or
   trigger type that `_FLOW_CONNECTOR_TYPES` / `_TRIGGER_TYPE_MAP` do not cover?
   Those frozensets are closed-world and silently drop unknowns.
3. Should `file_unarchive` (and `file_output_excel`) blank PASSWORD like
   `file_archive`/`file_input_excel`? Confirm the security policy: never persist
   any password, or only encryption passwords?
4. Are the `tConvertType`/`tChangeFileEncoding` "no engine" claims stale now that
   engine files exist, and does the `t`-prefixed `tConvertType` type cause
   dispatch to miss the engine class?
5. Is the `filename`-vs-`filepath` config-key split deliberate (matching each
   engine getter) or accidental drift the engine works around?
6. Can the orphan-component warning be relaxed to avoid false positives on valid
   single-component subjobs without breaking any downstream engine code?
