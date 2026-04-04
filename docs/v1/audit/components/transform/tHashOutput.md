# Audit Report: tHashOutput / (No Engine Implementation)

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report covers the v1 engine exclusively

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
|-------|-------|
| **Talend Name** | `tHashOutput` |
| **V1 Engine Class** | None -- no concrete engine implementation exists |
| **Engine File** | No dedicated engine file |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/hash_output.py` (92 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tHashOutput")` decorator-based dispatch |
| **Registry Aliases** | `tHashOutput` (single alias) |
| **Category** | Transform / Hash Lookup |

### Key Files

| File | Purpose |
|------|---------|
| `src/converters/talend_to_v1/components/transform/hash_output.py` | Converter class `HashOutputConverter` (92 lines) |
| `tests/converters/talend_to_v1/components/test_hash_output.py` | Converter tests (42 tests, 9 classes) |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()`, `_build_component_dict()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 8 of 8 _java.xml unique params extracted (100%); CLOSED_LIST values correct for DATA_WRITE_MODEL and KEYS_MANAGEMENT; module docstring follows CONVERTER_PATTERN.md |
| Engine Feature Parity | **R** | 1 | 0 | 0 | 0 | No concrete engine implementation exists; component cannot execute |
| Code Quality | **R** | 1 | 0 | 0 | 0 | Converter code quality is good (follows CONVERTER_PATTERN.md), but no engine code exists -- component is incomplete |
| Performance & Memory | **N/A** | 0 | 0 | 0 | 0 | No engine implementation to assess |
| Testing | **R** | 1 | 0 | 0 | 0 | 42 converter tests pass (9 classes per TEST_PATTERN.md), but 0 engine tests exist because engine is unimplemented |

**Overall: RED -- No engine implementation. Converter correctly extracts all 8 unique params with correct defaults and CLOSED_LIST values for future engine support, but component cannot execute in production. Engine must be implemented before this component is usable.**

**Top Actions**:
1. Implement concrete HashOutput engine class (P0 -- blocks production use)
2. All converter and test issues resolved in v1.1 rewrite

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tHashOutput Does

`tHashOutput` stores incoming data flow rows in an in-memory hash structure (a `java.util.HashMap`) keyed by one or more schema columns marked as key columns. The stored hash data can then be looked up by downstream components, typically `tHashInput`, which reads from the same hash structure by name. This provides a mechanism for hash-based lookups within a Talend job without writing data to disk.

The component supports two storage models: in-memory (`MEMORY`) which keeps all data in JVM heap, and persistent (`PERSISTENT`) which spills data to a file path on disk when the dataset exceeds the configured heap limit. The `KEYS_MANAGEMENT` parameter controls duplicate key behavior -- whether to keep all rows, only the first, or only the last row for each key value. The `LINK_WITH` parameter enables linking this hash output to a specific `tHashInput` component by name.

tHashOutput is commonly used in lookup patterns as an alternative to `tMap` lookups, especially when the same lookup data is needed by multiple downstream components. It is also used for deduplication workflows via the `KEYS_MANAGEMENT` setting.

**Source**: Talaxie GitHub tdi-studio-se repository (tHashOutput_java.xml)
**Component family**: Misc
**Available in**: All Talend product variants (Open Studio, Enterprise)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Link With | `LINK_WITH` | CHECK | `false` | When true, link this hash output to a specific tHashInput component via LIST |
| 2 | List | `LIST` | COMPONENT_LIST | `""` | Target tHashInput component name. Conditional: shown only when LINK_WITH=true |
| 3 | Data Write Model | `DATA_WRITE_MODEL` | CLOSED_LIST | `"MEMORY"` | Storage model. Values: `MEMORY` (in-JVM heap), `PERSISTENT` (spill to disk) |
| 4 | Base File Path | `BASE_FILE_PATH` | FILE | `""` | File path for persistent storage. Conditional: shown only when DATA_WRITE_MODEL=PERSISTENT |
| 5 | Memory Heap Max Size | `MEMORY_HEAP_MAX_SIZE` | TEXT | `"2"` | Max heap size in MB for persistent mode. Conditional: shown only when DATA_WRITE_MODEL=PERSISTENT |
| 6 | Keys Management | `KEYS_MANAGEMENT` | CLOSED_LIST | `"KEEP_ALL"` | Duplicate key handling. Values: `KEEP_FIRST`, `KEEP_LAST`, `KEEP_ALL`. Conditional: shown only when LINK_WITH=false |
| 7 | Append | `APPEND` | CHECK | `true` | Append to existing hash data instead of replacing. Conditional: shown only when LINK_WITH=false |
| 8 | Hash Key From Input Connector | `HASH_KEY_FROM_INPUT_CONNECTOR` | CHECK | `false` | Hidden parameter (show=false). When true, derive hash key from input connector name |

### 3.2 Advanced Settings

No advanced settings defined in _java.xml.

### 3.3 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 9 | Stat Catcher | `TSTATCATCHER_STATS` | CHECK | `false` | Enable statistics collection for tStatCatcher |
| 10 | Label | `LABEL` | TEXT | `""` | User-defined label for the component instance |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Incoming data rows to store in the hash |
| `FLOW` (Main) | Output | Row > Main | Passthrough of incoming rows (schema preserved) |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after component completes successfully |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires after component completes |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires if component encounters an error |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution of downstream |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Number of rows stored in the hash structure |

### 3.6 Behavioral Notes

1. **CLOSED_LIST: DATA_WRITE_MODEL** has two values: `MEMORY` (default, stores all data in JVM heap) and `PERSISTENT` (spills to disk at BASE_FILE_PATH when heap exceeds MEMORY_HEAP_MAX_SIZE). The PERSISTENT mode conditionally shows BASE_FILE_PATH and MEMORY_HEAP_MAX_SIZE.
2. **CLOSED_LIST: KEYS_MANAGEMENT** has three values: `KEEP_ALL` (default, preserves all rows including duplicate keys), `KEEP_FIRST` (keeps only the first row per key), and `KEEP_LAST` (keeps only the last row per key). Only shown when LINK_WITH=false.
3. **SHOW_IF conditions**: Multiple params have SHOW_IF visibility conditions: LIST shown when LINK_WITH=true; BASE_FILE_PATH and MEMORY_HEAP_MAX_SIZE shown when DATA_WRITE_MODEL=PERSISTENT; KEYS_MANAGEMENT and APPEND shown when LINK_WITH=false. The converter extracts all params regardless of visibility -- the conditions are UI-only.
4. **Hidden parameter**: HASH_KEY_FROM_INPUT_CONNECTOR has `show="false"` in _java.xml. It is always present but never displayed in the Talend UI. The converter extracts it with default False.
5. **Schema passthrough**: All input columns pass through to output unchanged. The hash key is determined by schema columns marked as key=true, not by a separate configuration parameter.
6. **APPEND defaults to True**: Unlike most boolean params which default to False, APPEND defaults to True -- meaning hash data is appended by default when the job runs multiple times.
7. **Generic param dump removed**: The previous converter used a `_normalise_value()` loop to dump all `node.params` into config. The v1.1 rewrite replaced this with explicit `_get_str()`/`_get_bool()` calls per _java.xml parameter definitions, with correct types and defaults.

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The converter uses explicit `_get_str()` and `_get_bool()` calls for each of the 8 unique _java.xml parameters, plus 2 framework parameters. All CLOSED_LIST values are extracted as strings with correct defaults. The converter follows CONVERTER_PATTERN.md with `_build_component_dict()` wrapper and `type_name="tHashOutput"` per D-43 (no-engine).

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `LINK_WITH` | Yes | `link_with` | bool, default False |
| 2 | `LIST` | Yes | `list` | str, default "" (COMPONENT_LIST) |
| 3 | `DATA_WRITE_MODEL` | Yes | `data_write_model` | CLOSED_LIST: MEMORY/PERSISTENT, default "MEMORY" |
| 4 | `BASE_FILE_PATH` | Yes | `base_file_path` | str (FILE type), default "" |
| 5 | `MEMORY_HEAP_MAX_SIZE` | Yes | `memory_heap_max_size` | str (TEXT), default "2" |
| 6 | `KEYS_MANAGEMENT` | Yes | `keys_management` | CLOSED_LIST: KEEP_FIRST/KEEP_LAST/KEEP_ALL, default "KEEP_ALL" |
| 7 | `APPEND` | Yes | `append` | bool, default True |
| 8 | `HASH_KEY_FROM_INPUT_CONNECTOR` | Yes | `hash_key_from_input_connector` | bool, hidden (show=false), default False |
| 9 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, bool, default False |
| 10 | `LABEL` | Yes | `label` | Framework param, str, default "" |

**Summary**: 8 of 8 unique parameters extracted (100%). 2 framework params always extracted.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Via `_parse_schema()` from FLOW connector |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | Direct from SchemaColumn |
| `key` | Yes | Direct from SchemaColumn |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not supported by `_parse_schema()` base helper |

Schema is passthrough: input equals output.

### 4.3 Expression Handling

Context variables (`context.var`) and Java expressions are stored as-is in string parameters (e.g., `BASE_FILE_PATH` may contain context variable references). No expression resolution at converter time -- deferred to engine execution.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No converter issues found. All 8 params extracted correctly with proper types and defaults. |

### 4.5 Needs Review Entries

The converter emits a single consolidated needs_review entry per D-84/D-27 (no engine implementation).

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | (all keys) | No v1 engine implementation exists for tHashOutput -- all config keys are unread by the engine | engine_gap |

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | In-memory hash storage | **No** | N/A | No engine file | No engine implementation exists |
| 2 | Persistent storage mode | **No** | N/A | No engine file | DATA_WRITE_MODEL=PERSISTENT not implemented |
| 3 | Key management (dedup) | **No** | N/A | No engine file | KEEP_FIRST/KEEP_LAST/KEEP_ALL not implemented |
| 4 | Component linking | **No** | N/A | No engine file | LINK_WITH to tHashInput not implemented |
| 5 | Append mode | **No** | N/A | No engine file | APPEND not implemented |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-HO-001 | **P0** | No engine implementation exists for tHashOutput. Component cannot execute. All features (hash storage, persistent mode, key management, component linking) are unimplemented. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | No | Not implemented | No engine exists |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-HO-001 | **P0** | No engine file | No engine code to audit. Component is unimplemented. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No naming issues. Converter uses snake_case config keys per D-38. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| -- | -- | -- | Converter follows CONVERTER_PATTERN.md. No violations. |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified. The converter only stores configuration values -- no file operations or code execution.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` present |
| Level usage | N/A -- no engine code; converter has no log calls (appropriate for simple extraction) |
| Sensitive data | No sensitive data in config keys |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | N/A -- no engine code |
| Exception chaining | N/A -- no engine code |
| die_on_error handling | N/A -- no engine code; no DIE_ON_ERROR param in _java.xml |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | Full type hints on `convert()` method |
| Parameter types | All params correctly typed: `_get_str()` for strings, `_get_bool()` for booleans |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No engine implementation to assess. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | N/A -- no engine implementation |
| Memory threshold | N/A -- no engine implementation |
| Large data handling | N/A -- no engine implementation |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 42 | `tests/converters/talend_to_v1/components/test_hash_output.py` |
| Engine unit tests | 0 | None -- no engine implementation |
| Integration tests | 0 | None -- no engine implementation |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-HO-001 | **P0** | No engine unit tests -- engine does not exist |

### 8.3 Recommended Test Cases

When engine is implemented:
- Hash storage with single key column
- Hash storage with multiple key columns
- KEYS_MANAGEMENT: KEEP_ALL preserves all duplicate key rows
- KEYS_MANAGEMENT: KEEP_FIRST retains only the first row per key
- KEYS_MANAGEMENT: KEEP_LAST retains only the last row per key
- DATA_WRITE_MODEL: MEMORY stores data in JVM heap
- DATA_WRITE_MODEL: PERSISTENT spills to disk at BASE_FILE_PATH
- MEMORY_HEAP_MAX_SIZE threshold triggers disk spill
- LINK_WITH=true + LIST links to specific tHashInput
- APPEND=true appends to existing hash data
- APPEND=false replaces existing hash data
- Empty input DataFrame (0 rows)
- Large dataset memory behavior

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 3 | **ENG-HO-001**, **BUG-HO-001**, **TEST-HO-001** |
| P1 | 0 | -- |
| P2 | 0 | -- |
| P3 | 0 | -- |
| **Total** | **3** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Engine (ENG) | 1 | ENG-HO-001 |
| Bug (BUG) | 1 | BUG-HO-001 |
| Testing (TEST) | 1 | TEST-HO-001 |

### Cross-Cutting Issues

No cross-cutting issues apply -- there is no engine code for cross-cutting bugs (e.g., `_update_global_map()` crash) to affect.

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)
1. **ENG-HO-001 (P0)**: Implement concrete HashOutput engine class with in-memory hash storage, key management, persistent mode, and component linking
2. **BUG-HO-001 (P0)**: Engine code quality cannot be assessed until engine exists
3. **TEST-HO-001 (P0)**: Add engine unit tests after engine implementation

### Short-term (Hardening)
- No P1 issues found

### Long-term (Optimization)
- No P2/P3 issues found

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub _java.xml | `https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tHashOutput/tHashOutput_java.xml` | Parameter definitions, defaults, CLOSED_LIST values, SHOW_IF conditions |
| Converter source | `src/converters/talend_to_v1/components/transform/hash_output.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_hash_output.py` | Test coverage assessment |
| Gold standard templates | `docs/v1/standards/CONVERTER_PATTERN.md`, `docs/v1/standards/TEST_PATTERN.md`, `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` | Standards compliance verification |

## Appendix B: Cross-Cutting Issues

No cross-cutting issues apply -- there is no engine implementation for base class bugs to affect.

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | No impact -- no engine class inherits from BaseComponent |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after v1.1 Phase 13 standardization*
