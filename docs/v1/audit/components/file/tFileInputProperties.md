# Audit Report: tFileInputProperties / FileInputProperties

> **Audited**: 2026-04-03
> **Reconciled**: 2026-05-11
> **Auditor**: Claude Opus 4.6 (automated)
> **Reconciler**: Claude Sonnet 4.6 (automated, Phase 15.1-04)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report covers the v1 engine exclusively

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFileInputProperties` |
| **V1 Engine Class** | `FileInputProperties` (built Phase 14-08 incidental) |
| **Engine File** | `src/v1/engine/components/file/file_input_properties.py` (182 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/file_input_properties.py` (72 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFileInputProperties")` decorator-based dispatch |
| **Registry Aliases** | `FileInputProperties`, `tFileInputProperties` |
| **Category** | File / Input |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/file_input_properties.py` | Engine implementation `FileInputProperties` (182 lines, Phase 14-08) |
| `src/converters/talend_to_v1/components/file/file_input_properties.py` | Converter class `FileInputPropertiesConverter` (72 lines) |
| `tests/v1/engine/components/file/test_file_input_properties.py` | Engine tests (17 tests, 6 classes) |
| `tests/converters/talend_to_v1/components/test_file_input_properties.py` | Converter tests (35 tests across 9 classes) |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()`, `_build_component_dict()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 5 of 5 unique config keys extracted (100%); FILE_FORMAT, RETRIVE_MODE, SECTION_NAME, FILENAME, ENCODING; 1 phantom param (DIE_ON_ERROR) removed; needs_review entry for engine gap; module docstring follows CONVERTER_PATTERN.md |
| Engine Feature Parity | **G** | 0 | 0 | 1 | 0 | Engine built Phase 14-08 (182 lines). .properties and .ini formats implemented. [NEW IN 15.1] XML_FORMAT mode support not confirmed -- needs validation. |
| Code Quality | **G** | 0 | 0 | 0 | 0 | Engine follows BaseComponent pattern. _validate_config() checks required filename. |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | File read into memory; acceptable for properties files which are small by design. |
| Testing | **G** | 0 | 0 | 0 | 0 | 35 converter tests + 17 engine tests (6 classes). >= 95% per-module line coverage floor (Phase 14). |

Overall: GREEN -- Engine implemented Phase 14-08, converter GREEN from prior rewrite, Phase 14 coverage floor met.

**Resolved actions**:

1. ~~Implement concrete FileInputProperties engine class (P0 -- blocks production use)~~ [RESOLVED in Phase 14-08]
2. ~~TEST-FIP-001 (P0): Add engine unit tests~~ [RESOLVED in Phase 14-08 -- 17 engine tests added]

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tFileInputProperties Does

`tFileInputProperties` reads Java `.properties` files, `.ini` files, or XML configuration files and outputs their key/value pairs as rows. Each key/value pair from the file becomes one output row with columns as defined by the schema.

The component supports three file formats via the `FILE_FORMAT` parameter: standard Java `.properties` format (`PROPERTIES_FORMAT`), Windows `.ini` section-based format (when using `RETRIVE_BY_SECTION`), and XML properties format (`XML_FORMAT`). When reading `.ini` files by section, the `SECTION_NAME` parameter specifies which section to extract. Alternatively, `RETRIVE_BY_KEY` mode reads all keys regardless of section.

This is a source component with no input flow -- it reads directly from a file and produces output rows. The component is commonly used to load configuration values from property files into the job's data flow, enabling dynamic configuration of downstream components.

**Source**: Talaxie GitHub tdi-studio-se repository (`tFileInputProperties_java.xml`)
**Component family**: File / Input
**Available in**: All Talend product variants (Open Studio, Enterprise)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Defines output columns. Typically `key` (String) and `value` (String). |
| 2 | File Format | `FILE_FORMAT` | CLOSED_LIST | `"PROPERTIES_FORMAT"` | File format to parse. Options: `PROPERTIES_FORMAT` (standard .properties), `XML_FORMAT` (XML properties). Determines how the file is parsed. |
| 3 | Retrieve Mode | `RETRIVE_MODE` | CLOSED_LIST | `"RETRIVE_BY_SECTION"` | How to retrieve values. Options: `RETRIVE_BY_SECTION` (read specific section), `RETRIVE_BY_KEY` (read by key name). Note: Talend uses `RETRIVE` spelling (not `RETRIEVE`). |
| 4 | Section Name | `SECTION_NAME` | TEXT | `"section"` | Section name to read when RETRIVE_MODE is RETRIVE_BY_SECTION. Only relevant for .ini-style files with `[section]` headers. |
| 5 | File Name | `FILENAME` | FILE | `""` | Path to the properties/ini/XML file to read. |
| 6 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding for file reading. Note: Default is ISO-8859-15, NOT UTF-8. |

### 3.2 Advanced Settings

No advanced settings defined in _java.xml for tFileInputProperties.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Output | Row > Main | Output data flow containing key/value pairs from the properties file |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after component completes successfully |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires after component completes |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires if component encounters an error |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution of downstream |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total number of key/value pairs read from the file |

### 3.5 Behavioral Notes

1. **Encoding default is ISO-8859-15**: The _java.xml ENCODING default is `"ISO-8859-15"`, consistent with most Talend file input components. The prior converter incorrectly defaulted to UTF-8.
2. **`RETRIVE` spelling**: Talend uses `RETRIVE` (not `RETRIEVE`) in both the XML name and the enum values. This is a known Talend naming quirk that must be preserved in config keys.
3. **DIE_ON_ERROR is phantom**: The prior converter extracted `DIE_ON_ERROR` but this parameter does NOT exist in the `tFileInputProperties_java.xml` definition. It was a phantom param and has been removed.
4. **FILE_FORMAT affects RETRIVE_MODE visibility**: When FILE_FORMAT is `XML_FORMAT`, the RETRIVE_MODE and SECTION_NAME parameters may not be relevant since XML properties files do not have sections.
5. **Source component**: tFileInputProperties is a source component with no input connections. Output schema is user-defined (typically key/value columns).

### 3.6 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| F1 | tStatCatcher Stats | `TSTATCATCHER_STATS` | CHECK | `false` | Enable statistics collection for tStatCatcher |
| F2 | Label | `LABEL` | TEXT | `""` | User-defined label for the component instance |

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The converter (`FileInputPropertiesConverter`) uses the `ComponentConverter` base class helpers (`_get_str`, `_get_bool`) to extract parameters from the TalendNode params dict. All 5 unique parameters plus 2 framework parameters are extracted. The phantom `DIE_ON_ERROR` parameter has been removed.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `FILE_FORMAT` | Yes | `file_format` | CLOSED_LIST -> str, default "PROPERTIES_FORMAT". Extracted via `_get_str()`. |
| 2 | `RETRIVE_MODE` | Yes | `retrive_mode` | CLOSED_LIST -> str, default "RETRIVE_BY_SECTION". Extracted via `_get_str()`. |
| 3 | `SECTION_NAME` | Yes | `section_name` | TEXT -> str, default "section". Extracted via `_get_str()`. |
| 4 | `FILENAME` | Yes | `filename` | FILE -> str, default "". Extracted via `_get_str()`. |
| 5 | `ENCODING` | Yes | `encoding` | ENCODING_TYPE -> str, default "ISO-8859-15". Fixed from prior UTF-8 default. Extracted via `_get_str()`. |
| F1 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | CHECK -> bool, default False. Framework param extracted last per convention. |
| F2 | `LABEL` | Yes | `label` | TEXT -> str, default "". Framework param extracted last per convention. |

**Phantom params removed**: `DIE_ON_ERROR` -- not present in `tFileInputProperties_java.xml`.

**Summary**: 5 of 5 unique _java.xml parameters extracted (100%). Plus 2 framework params. 1 phantom param removed.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` base class method |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | Boolean |
| `key` | Yes | Boolean |
| `length` | Yes | Only included when >= 0 |
| `precision` | Yes | Only included when >= 0 |
| `pattern` | Yes | Java date pattern converted to Python strftime |
| `default` | No | Not extracted by `_parse_schema()` base method |

Schema direction: Source component pattern -- `{"input": [], "output": self._parse_schema(node)}`.

### 4.3 Expression Handling

No expression handling is needed for tFileInputProperties. The `_get_str()` helper strips surrounding quotes from scalar parameter values. Context variable expressions (e.g., `context.filename`) are passed through as-is for runtime resolution.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| CONV-FIP-001 | ~~P1~~ | **FIXED** -- FILE_FORMAT parameter now extracted (was missing) |
| CONV-FIP-002 | ~~P1~~ | **FIXED** -- RETRIVE_MODE parameter now extracted (was missing) |
| CONV-FIP-003 | ~~P1~~ | **FIXED** -- SECTION_NAME parameter now extracted (was missing) |
| CONV-FIP-004 | ~~P1~~ | **FIXED** -- ENCODING default corrected from UTF-8 to ISO-8859-15 per _java.xml |
| CONV-FIP-005 | ~~P2~~ | **FIXED** -- Phantom DIE_ON_ERROR removed (not in _java.xml) |
| CONV-FIP-006 | ~~P2~~ | **FIXED** -- tstatcatcher_stats framework param now extracted |
| CONV-FIP-007 | ~~P2~~ | **FIXED** -- label framework param now extracted |
| CONV-FIP-008 | ~~P2~~ | **FIXED** -- Module docstring follows CONVERTER_PATTERN.md with Config mapping block |
| CONV-FIP-009 | ~~P2~~ | **FIXED** -- _build_component_dict() used per D-40 (was already in use but type_name corrected) |
| CONV-FIP-010 | ~~P2~~ | **FIXED** -- type_name set to "tFileInputProperties" per D-43 (no-engine uses Talend name) |

### 4.5 Needs Review Entries

The converter emits a single component-level needs_review entry (not per-key, since the entire engine is absent):

| # | Scope | Reason | Severity |
| --- | ------- | -------- | ---------- |
| 1 | Component-level | No v1 engine implementation exists for tFileInputProperties. All config keys are extracted for future engine support. | engine_gap |

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

Engine built Phase 14-08. Core .properties and .ini formats implemented.

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Read .properties files | **Yes** | High | `file_input_properties.py:_process()` | Standard key=value format with configparser |
| 2 | Read .ini files by section | **Yes** | High | `file_input_properties.py:_process()` | RETRIVE_BY_SECTION reads named section |
| 3 | Read XML properties files | **Partial** | Unknown | `file_input_properties.py` | [NEW IN 15.1] XML_FORMAT mode not confirmed in engine implementation |
| 4 | RETRIVE_BY_KEY mode | **Yes** | High | `file_input_properties.py:_process()` | Reads all keys across sections |
| 5 | RETRIVE_BY_SECTION mode | **Yes** | High | `file_input_properties.py:_process()` | Reads keys from named SECTION_NAME |
| 6 | Character encoding support | **Yes** | High | `file_input_properties.py` | ENCODING param passed to file open |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ~~ENG-FIP-001~~ | ~~P0~~ | ~~No FileInputProperties engine class exists. Jobs using tFileInputProperties cannot execute in the v1 engine.~~ [RESOLVED in Phase 14-08] |
| ~~TEST-FIP-001~~ | ~~P0~~ | ~~No engine unit tests (no engine exists).~~ [RESOLVED in Phase 14-08 -- 17 engine tests added] |
| [NEW IN 15.1] ENG-FIP-002 | P2 | XML_FORMAT mode support in engine needs validation against Talaxie _java.xml behavior |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` in BaseComponent | Set to number of key/value pairs read |

---

## 6. Code Quality

How well-written is the converter code?

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| -- | -- | -- | No bugs found in the converter code. Logic is correct for what it implements. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No naming issues. All config keys follow snake_case convention per D-38. `retrive_mode` preserves the Talend `RETRIVE` spelling (intentional). |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| -- | -- | -- | No violations. Converter follows CONVERTER_PATTERN.md in full: module docstring, parameter order, framework params last, _build_component_dict, needs_review format. |

### 6.4 Debug Artifacts

None found. No print statements, hardcoded paths, or TODO comments.

### 6.5 Security

No concerns identified. The converter only reads XML parameter data and produces config dicts. No file I/O, eval, or injection surface.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- `logger = logging.getLogger(__name__)` at module level |
| Level usage | N/A -- logger not used in the converter (appropriate for simple component) |
| Sensitive data | No concerns |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Good -- no exceptions raised per convention (converters never raise) |
| Exception chaining | N/A |
| die_on_error handling | N/A -- tFileInputProperties has no die_on_error parameter in _java.xml |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- `convert()` fully typed with return type `ComponentResult` |
| Parameter types | Good -- all parameters typed in method signature |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No performance or memory concerns. The converter is lightweight with simple parameter extraction. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- no engine implementation to assess |
| Memory threshold | N/A |
| Large data handling | N/A -- converter only extracts config params |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 35 | `tests/converters/talend_to_v1/components/test_file_input_properties.py` |
| Engine unit tests | 17 | `tests/v1/engine/components/file/test_file_input_properties.py` (6 classes -- Phase 14-08) |
| Integration tests | 0 | None |

Phase 14 >= 95% per-module line coverage floor applies to `src/v1/engine/components/file/file_input_properties.py`.

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| ~~TEST-FIP-001~~ | ~~P0~~ | ~~No engine unit tests (no engine exists).~~ [RESOLVED Phase 14-08 -- 17 engine tests added] |
| [NEW IN 15.1] TEST-FIP-002 | P2 | No test for XML_FORMAT mode (ENG-FIP-002 companion) |

### 8.3 Recommended Test Cases

All recommended converter test cases are implemented:

- **TestRegistration**: Registry lookup verified
- **TestDefaults**: All 5 unique + 2 framework params tested for defaults
- **TestParameterExtraction**: All params tested with non-default values
- **TestFrameworkParams**: tstatcatcher_stats and label tested
- **TestSchema**: Source component output schema verified
- **TestNeedsReview**: Single consolidated entry, severity, component_id, framework param exclusion
- **TestCompleteness**: All 7 config keys present, no extra keys
- **TestPhantomParams**: DIE_ON_ERROR not in output
- **TestComponentStructure**: type, original_type, id, position, top-level keys, inputs/outputs

Engine test cases needed after engine implementation:

1. Read standard .properties file (key=value format)
2. Read .ini file by section ([section] headers)
3. Read XML properties file
4. RETRIVE_BY_KEY vs RETRIVE_BY_SECTION modes
5. ISO-8859-15 encoding with special characters
6. Empty file handling
7. Missing file error handling
8. NB_LINE globalMap variable

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 (2 fixed) | ~~ENG-FIP-001~~ [RESOLVED Phase 14-08], ~~TEST-FIP-001~~ [RESOLVED Phase 14-08] |
| P1 | 0 (4 fixed) | ~~CONV-FIP-001~~, ~~CONV-FIP-002~~, ~~CONV-FIP-003~~, ~~CONV-FIP-004~~ |
| P2 | 1 (6 fixed) | [NEW IN 15.1] ENG-FIP-002 (XML_FORMAT validation), [NEW IN 15.1] TEST-FIP-002; ~~CONV-FIP-005~~, ~~CONV-FIP-006~~, ~~CONV-FIP-007~~, ~~CONV-FIP-008~~, ~~CONV-FIP-009~~, ~~CONV-FIP-010~~ |
| P3 | 0 | |
| **Total Open** | **2** | (12 fixed) |

### By Category

| Category | Count (open/fixed) | IDs |
| ---------- | ------------------- | ----- |
| Converter (CONV) | 0/10 | ~~CONV-FIP-001~~ through ~~CONV-FIP-010~~ |
| Engine (ENG) | 1/1 | [NEW IN 15.1] ENG-FIP-002; ~~ENG-FIP-001~~ [RESOLVED Phase 14-08] |
| Bug (BUG) | 0/0 | |
| Naming (NAME) | 0/0 | |
| Standards (STD) | 0/0 | |
| Performance (PERF) | 0/0 | |
| Testing (TEST) | 1/1 | [NEW IN 15.1] TEST-FIP-002; ~~TEST-FIP-001~~ [RESOLVED Phase 14-08] |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component | Status |
| ------------- | ---------- | -------------------------- | ------- |
| XCUT-001 | `base_component.py` | `_update_global_map()` crash -- affects NB_LINE put | ~~Resolved~~ [RESOLVED Phase 1, ENG-01] |
| XCUT-002 | `global_map.py` | `GlobalMap.get()` crash -- affects GlobalMap retrieval | ~~Resolved~~ [RESOLVED: BaseComponent fix applies] |

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

~~1. **ENG-FIP-001 (P0)**: Implement a concrete FileInputProperties engine class.~~ [RESOLVED Phase 14-08]
~~2. **TEST-FIP-001 (P0)**: Add engine unit tests.~~ [RESOLVED Phase 14-08]

No P0 blockers remain. Component is production-ready for .properties and .ini use cases.

### Short-term

1. [NEW IN 15.1] Validate XML_FORMAT mode (ENG-FIP-002, P2) against Talaxie _java.xml behavior.
2. [NEW IN 15.1] Add engine test for XML_FORMAT (TEST-FIP-002, P2).

### Short-term (Hardening)

All converter and test issues have been resolved in the v1.1 rewrite. No short-term items remain.

### Long-term (Optimization)

No P3 issues identified. Component is simple and well-contained.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `https://github.com/Talaxie/tdi-studio-se` (tFileInputProperties_java.xml) | Parameter definitions, defaults, types, connectors |
| Engine source | `src/v1/engine/components/file/file_input_properties.py` | Engine implementation (182 lines) |
| Converter source | `src/converters/talend_to_v1/components/file/file_input_properties.py` | Converter audit (72 lines) |
| Converter base class | `src/converters/talend_to_v1/components/base.py` | Helper methods, dataclass definitions |
| Engine tests | `tests/v1/engine/components/file/test_file_input_properties.py` | Engine testing (17 tests) |
| Converter tests | `tests/converters/talend_to_v1/components/test_file_input_properties.py` | Converter testing (35 tests) |
| Contributing guide | `docs/CONTRIBUTING.md` | Standards and patterns reference |
| Manual component authoring | `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md` | Component authoring pattern |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component | Status |
| ------------- | ---------- | -------------------------- | ------- |
| XCUT-001 | `base_component.py` | `_update_global_map()` crash -- affects NB_LINE put in FileInputProperties | ~~Resolved~~ [RESOLVED Phase 1, ENG-01] |
| XCUT-002 | `global_map.py` | `GlobalMap.get()` crash -- affects GlobalMap retrieval | ~~Resolved~~ [RESOLVED: BaseComponent fix applies] |

### Edge-Case Checklist Results

| Check | Result | Notes |
| ------- | -------- | ------- |
| NaN handling | N/A | FileInputProperties outputs string key/value pairs; no NaN |
| Empty strings in config keys | Safe | `_get_str()` returns default for None, handles empty strings |
| Empty file input | Engine handles | Returns 0 rows; NB_LINE=0 |
| HYBRID streaming mode | N/A | Source component; BaseComponent handles mode selection |
| `_update_global_map()` crash | Resolved | Phase 1 ENG-01 fix applies |
| Type demotion through iterrows | N/A | Source component outputs string values only |
| `validate_schema` nullable logic | Safe | Output schema user-defined; engine validates against it |
| `_validate_config()` called or dead code | Engine implements | _validate_config() checks required 'filename' key |

---

*Report generated: 2026-04-03*
*Last updated: 2026-05-11 (Phase 15.1-04 reconciliation -- ENG-FIP-001/TEST-FIP-001 resolved Phase 14-08, broken refs repaired)*
