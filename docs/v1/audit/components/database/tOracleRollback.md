# Audit Report: tOracleRollback / (No Engine Implementation)

> **Audited**: 2026-04-03
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
| **Talend Name** | `tOracleRollback` |
| **V1 Engine Class** | None -- no concrete engine implementation exists |
| **Engine File** | None -- no engine file for this component |
| **Converter Parser** | `src/converters/talend_to_v1/components/database/oracle_rollback.py` |
| **Converter Dispatch** | `@REGISTRY.register("tOracleRollback")` decorator-based dispatch |
| **Registry Aliases** | `tOracleRollback` (single alias) |
| **Category** | Database / Oracle |

### Key Files

| File | Purpose |
|------|---------|
| `src/converters/talend_to_v1/components/database/oracle_rollback.py` | Converter class `OracleRollbackConverter` |
| `tests/converters/talend_to_v1/components/test_oracle_rollback.py` | Converter tests |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 2 of 2 unique config keys extracted (100%); CONNECTION and CLOSE extracted; framework params extracted; single consolidated needs_review for engine gap; CONNECTION_FORMAT phantom removed |
| Engine Feature Parity | **R** | 1 | 0 | 0 | 0 | No concrete engine implementation exists; component cannot execute |
| Code Quality | **R** | 1 | 0 | 0 | 0 | Converter code quality is good (follows CONVERTER_PATTERN.md), but no engine code exists at all -- component is incomplete |
| Performance & Memory | **N/A** | 0 | 0 | 0 | 0 | No engine implementation to assess |
| Testing | **R** | 1 | 0 | 0 | 0 | Converter tests pass with full coverage, but 0 engine tests exist because engine is unimplemented. Component is untestable end-to-end. |

**Overall: RED -- No engine implementation. Converter correctly extracts all params for future engine support, but component cannot execute in production. Engine must be implemented before this component is usable.**

**Top Actions**:
1. Implement concrete OracleRollback engine class (P0 -- blocks production use)
2. All converter and test issues resolved in v1.1 rewrite

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tOracleRollback Does

`tOracleRollback` rolls back the current transaction on an existing Oracle database connection that was previously opened by a `tOracleConnection` component. It is a transaction management component -- its purpose is to undo all uncommitted changes made through the referenced connection since the last commit or savepoint.

In a typical Talend job, tOracleConnection opens a connection, components like tOracleOutput write data, and either tOracleCommit commits the transaction or tOracleRollback rolls it back (usually on an error trigger). The connection is identified by the component name of the tOracleConnection instance (e.g., "tOracleConnection_1"). tOracleRollback is commonly placed on a SUBJOB_ERROR or COMPONENT_ERROR trigger to ensure data is rolled back when processing fails.

Like tOracleCommit, tOracleRollback has an optional CLOSE parameter that allows the connection to be closed after the rollback operation. This component has exactly 2 unique parameters (CONNECTION and CLOSE).

**Source**: Talaxie GitHub tdi-studio-se repository (tOracleRollback_java.xml)
**Component family**: Databases / DB Specifics / Oracle
**Available in**: All Talend product variants (Open Studio, Enterprise)
**Required JARs**: Oracle JDBC driver (managed by tOracleConnection)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Connection | `CONNECTION` | COMPONENT_LIST | `""` | Required. References the tOracleConnection component whose transaction to roll back. Filtered to show only tOracleConnection instances. |
| 2 | Close Connection | `CLOSE` | CHECK | `true` | When true, closes the JDBC connection after the rollback. When false, the connection remains open for further operations. |

### 3.2 Advanced Settings

No advanced settings defined in _java.xml for tOracleRollback.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` | N/A | Row > Main | Max input 0, max output 0. No data flow. |
| `ITERATE` | N/A | Iterate | Max input 0, max output 0. No iterate flow. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after rollback completes successfully |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires if rollback encounters an error |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires after component completes |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires if component encounters an error |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution of downstream |

### 3.4 GlobalMap Variables

No RETURNS section in _java.xml. tOracleRollback does not set any globalMap variables.

### 3.5 Behavioral Notes

1. **No data flow**: tOracleRollback has MAX_INPUT=0 and MAX_OUTPUT=0 for both FLOW and ITERATE connectors. It is purely a transaction management component.
2. **CONNECTION is required**: The `REQUIRED="true"` attribute in _java.xml means Talend Studio will not allow the job to run without a valid CONNECTION reference.
3. **FILTER="tOracleConnection"**: The COMPONENT_LIST dropdown is filtered to show only tOracleConnection instances in the job.
4. **CLOSE defaults to true**: By default, tOracleRollback closes the connection after rolling back. Set CLOSE=false to keep the connection open for additional operations.
5. **STARTABLE="true"**: The component can be the start of a subjob (typical placement on an error trigger).
6. **LOG4J_ENABLED="true"**: Talend generates log4j logging code for this component.
7. **Identical structure to tOracleCommit**: tOracleRollback has the same 2 parameters (CONNECTION, CLOSE) as tOracleCommit -- the only difference is the SQL operation (ROLLBACK vs COMMIT).

### 3.6 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| F1 | tStatCatcher Stats | `TSTATCATCHER_STATS` | CHECK | `false` | Enable statistics collection for tStatCatcher |
| F2 | Label | `LABEL` | TEXT | `""` | User-defined label for the component instance |

### 3.7 Phantom Parameters

| # | Parameter | Status | Notes |
|---|-----------|--------|-------|
| 1 | `CONNECTION_FORMAT` | **Phantom -- removed** | Not present in _java.xml. Was extracted by the old converter but has no source-of-truth definition. Removed in v1.1 rewrite. |

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The converter (`OracleRollbackConverter`) uses the flat config dict pattern (no `_build_component_dict`). It extracts 2 unique parameters via `_get_str()` and `_get_bool()`, adds framework parameters, schema, and a consolidated needs_review entry.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `CONNECTION` | Yes | `connection` | COMPONENT_LIST -> str, default "". Extracted via `_get_str()`. |
| 2 | `CLOSE` | Yes | `close` | CHECK -> bool, default True. Extracted via `_get_bool()`. |
| F1 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | CHECK -> bool, default False. Framework param extracted last per convention. |
| F2 | `LABEL` | Yes | `label` | TEXT -> str, default "". Framework param extracted last per convention. |
| -- | `CONNECTION_FORMAT` | **Removed** | -- | Phantom param. Not in _java.xml. Not extracted by the v1.1 converter. |

**Summary**: 2 of 2 unique parameters extracted (100%). All framework params extracted. 1 phantom param removed.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Via `_parse_schema()` base class method |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | Boolean |
| `key` | Yes | Boolean |
| `length` | Yes | Only included when >= 0 |
| `precision` | Yes | Only included when >= 0 |
| `pattern` | Yes | Java date pattern converted to Python strftime |
| `default` | No | Not extracted by `_parse_schema()` base method |

Schema extraction is available via the base class but tOracleRollback typically has no schema (no data flow). The schema key will be an empty list when no FLOW schema is defined.

### 4.3 Expression Handling

No expression handling needed for tOracleRollback. The CONNECTION parameter is a COMPONENT_LIST reference (component name string), not a Java expression. The `_get_str()` helper strips surrounding quotes from the parameter value.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No converter issues. All parameters correctly extracted per gold standard pattern. |

### 4.5 Needs Review Entries

The converter emits a single consolidated needs_review entry per D-27 (entire engine absent):

| # | Scope | Reason | Severity |
|---|-------|--------|----------|
| 1 | Component-level | No concrete engine implementation for tOracleRollback. All config keys are extracted for future engine support. | engine_gap |

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

No concrete engine implementation exists for tOracleRollback.

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Rollback Oracle transaction | **No** | N/A | -- | No engine class exists |
| 2 | CONNECTION reference resolution | **No** | N/A | -- | No engine class exists |
| 3 | Close connection after rollback | **No** | N/A | -- | No engine class exists |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-ORR-001 | **P0** | **OPEN** -- No concrete OracleRollback engine class exists. Jobs using tOracleRollback cannot execute in the v1 engine. |

### 5.3 GlobalMap Variable Coverage

tOracleRollback does not set any globalMap variables (no RETURNS section in _java.xml).

---

## 6. Code Quality

How well-written is the converter code?

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| -- | -- | -- | No bugs found in the converter code. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No naming issues. Config keys follow snake_case convention. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| -- | -- | -- | No standards violations. Converter follows CONVERTER_PATTERN.md. |

### 6.4 Debug Artifacts

None found. No print statements, hardcoded paths, or TODO comments.

### 6.5 Security

No concerns identified. The converter only reads XML parameter data and produces config dicts. No file I/O, eval, or injection surface.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Good -- `logger = logging.getLogger(__name__)` at module level |
| Level usage | N/A -- logger not used in the converter (appropriate for simple component) |
| Sensitive data | No concerns |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Good -- no exceptions raised per convention (converters never raise) |
| Exception chaining | N/A |
| die_on_error handling | N/A -- tOracleRollback has no die_on_error parameter |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | Good -- `convert()` fully typed with return type `ComponentResult` |
| Parameter types | Good -- all base class helpers properly typed |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No performance or memory concerns. The converter is a trivial parameter extractor. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | N/A -- no engine implementation to assess |
| Memory threshold | N/A |
| Large data handling | N/A -- no data flow (utility component) |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | Yes | `tests/converters/talend_to_v1/components/test_oracle_rollback.py` |
| Engine unit tests | 0 | None -- no engine implementation |
| Integration tests | 0 | None |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| -- | -- | No test gaps. All required test classes per TEST_PATTERN.md present including TestPhantomParams. |

### 8.3 Recommended Test Cases

- **TestRegistration**: Verify `REGISTRY.get("tOracleRollback")` returns `OracleRollbackConverter`
- **TestDefaults**: connection="" default, close=True default
- **TestParameterExtraction**: CONNECTION extraction with quoted value, CLOSE=false
- **TestFrameworkParams**: tstatcatcher_stats=true, label extraction
- **TestSchema**: Schema extraction (typically empty for utility component)
- **TestNeedsReview**: Single consolidated needs_review with severity="engine_gap"
- **TestCompleteness**: All expected config keys present
- **TestPhantomParams**: CONNECTION_FORMAT not in output even when provided as input

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 1 (open) | **ENG-ORR-001** |
| P1 | 0 | |
| P2 | 0 | |
| P3 | 0 | |
| **Total Open** | **1** | |

### By Category

| Category | Count (open/fixed) | IDs |
|----------|-------------------|-----|
| Converter (CONV) | 0/0 | |
| Engine (ENG) | 1/0 | **ENG-ORR-001** |
| Bug (BUG) | 0/0 | |
| Naming (NAME) | 0/0 | |
| Standards (STD) | 0/0 | |
| Performance (PERF) | 0/0 | |
| Testing (TEST) | 0/0 | |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| -- | -- | No cross-cutting issues affect tOracleRollback directly (no engine implementation to interact with base class bugs) |

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

1. **ENG-ORR-001 (P0)**: Implement a concrete OracleRollback engine class that rolls back the current transaction and optionally closes the named Oracle JDBC connection. This blocks any job using tOracleRollback.

### Short-term (Hardening)

All converter and test issues resolved in v1.1 rewrite. No P1/P2 issues remain.

### Long-term (Optimization)

No P3 issues identified. Component is structurally identical to tOracleCommit.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub _java.xml | `https://github.com/Talaxie/tdi-studio-se` (tOracleRollback_java.xml) | Parameter definitions, connectors, defaults |
| Converter source | `src/converters/talend_to_v1/components/database/oracle_rollback.py` | Converter audit |
| Converter base class | `src/converters/talend_to_v1/components/base.py` | Helper methods, dataclass definitions |
| Test source | `tests/converters/talend_to_v1/components/test_oracle_rollback.py` | Testing audit |
| CONVERTER_PATTERN.md | `docs/v1/standards/CONVERTER_PATTERN.md` | Gold standard converter structure |
| TEST_PATTERN.md | `docs/v1/standards/TEST_PATTERN.md` | Gold standard test structure |
| AUDIT_REPORT_TEMPLATE.md | `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` | Audit report structure |
| METHODOLOGY.md | `docs/v1/standards/METHODOLOGY.md` | Scoring framework, edge-case checklist |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | No impact -- no engine implementation to interact with `_update_global_map()` |
| XCUT-002 | `global_map.py:28` | No impact -- no engine implementation to call `GlobalMap.get()` |

### Edge-Case Checklist Results

| Check | Result | Notes |
|-------|--------|-------|
| NaN handling | N/A | Converter does not process data values |
| Empty strings in config keys | Safe | `_get_str()` returns default for None, handles empty strings |
| Empty DataFrame input | N/A | No data flow (utility component) |
| HYBRID streaming mode | N/A | No engine implementation |
| `_update_global_map()` crash | N/A | No engine implementation |
| Type demotion through iterrows | N/A | No engine implementation |
| `validate_schema` nullable logic | N/A | No engine implementation |
| `_validate_config()` called or dead code | N/A | No engine implementation |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after v1.1 converter rewrite*
