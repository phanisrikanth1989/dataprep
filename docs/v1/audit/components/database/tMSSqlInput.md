# Audit Report: tMSSqlInput / (No Engine Implementation)

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
| ------- | ------- |
| **Talend Name** | `tMSSqlInput` |
| **V1 Engine Class** | None -- no concrete engine implementation exists |
| **Engine File** | None -- no engine file for this component |
| **Converter Parser** | `src/converters/talend_to_v1/components/database/mssql_input.py` |
| **Converter Dispatch** | `@REGISTRY.register("tMSSqlInput")` decorator-based dispatch |
| **Registry Aliases** | `tMSSqlInput` (single alias) |
| **Category** | Database / MSSQL |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/converters/talend_to_v1/components/database/mssql_input.py` | Converter class `MSSqlInputConverter` |
| `tests/converters/talend_to_v1/components/test_mssql_input.py` | Converter tests |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 20 of 20 params extracted (100%); USE_EXISTING_CONNECTION, CONNECTION, DRIVER, HOST, PORT, DB_SCHEMA->schema_db, DBNAME, USER, PASS, QUERY, SPECIFY_DATASOURCE_ALIAS, DATASOURCE_ALIAS, PROPERTIES (non-empty default), ACTIVE_DIR_AUTH, ENCODING, TRIM_ALL_COLUMN, TRIM_COLUMN, SET_QUERY_TIMEOUT, QUERY_TIMEOUT_IN_SECONDS + framework params; single consolidated needs_review for engine gap |
| Engine Feature Parity | **R** | 1 | 0 | 0 | 0 | No concrete engine implementation exists; component cannot execute |
| Code Quality | **R** | 1 | 0 | 0 | 0 | Converter code quality is good (follows CONVERTER_PATTERN.md), but no engine code exists at all -- component is incomplete |
| Performance & Memory | **N/A** | 0 | 0 | 0 | 0 | No engine implementation to assess |
| Testing | **R** | 1 | 0 | 0 | 0 | Converter tests pass with full coverage, but 0 engine tests exist because engine is unimplemented. Component is untestable end-to-end. |

**Overall: Red (RED) -- No engine implementation. Converter correctly extracts all 20 params (including DB_SCHEMA->schema_db mapping, PROPERTIES non-empty default "noDatetimeStringSync=true", encrypted password handling) for future engine support, but component cannot execute in production. Engine must be implemented before this component is usable.**

**Top Actions**:

1. Implement concrete MSSqlInput engine class (P0 -- blocks production use)
2. All converter and test issues resolved in v1.1 rewrite
3. Wire TRIM_COLUMN per-column trim logic in engine once implemented

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tMSSqlInput Does

`tMSSqlInput` reads data from a Microsoft SQL Server database by executing a SQL query and producing output rows. It is a source component -- it accepts no input rows and emits rows from the query result set on its FLOW output connector.

The component supports two connection modes: standalone (providing HOST/PORT/DBNAME/USER/PASS directly) or shared (referencing an existing tMSSqlConnection via USE_EXISTING_CONNECTION). It supports Microsoft SQL Server via the JTDS or Microsoft JDBC driver (DRIVER param), Active Directory authentication, configurable JDBC properties, query timeouts, and per-column string trimming.

A notable feature is the PROPERTIES parameter which defaults to "noDatetimeStringSync=true" -- this is a non-empty default, unlike most TEXT parameters. The DB_SCHEMA parameter in _java.xml maps to the `schema_db` config key for consistency with the MSSQL family naming convention (D-30).

**Source**: Talaxie GitHub tdi-studio-se repository (tMSSqlInput_java.xml)
**Component family**: Databases / DB Specifics / MSSQL
**Available in**: All Talend product variants (Open Studio, Enterprise)
**Required JARs**: JTDS or Microsoft JDBC driver (managed by connection setup)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Use Existing Connection | `USE_EXISTING_CONNECTION` | CHECK | `false` | When true, uses a connection opened by a tMSSqlConnection component instead of standalone connection params |
| 2 | Connection | `CONNECTION` | COMPONENT_LIST | `""` | References the tMSSqlConnection component to use. Only shown when USE_EXISTING_CONNECTION is true. Filtered to show only tMSSqlConnection instances. |
| 3 | Driver | `DRIVER` | CLOSED_LIST | `"MSSQL_PROP"` | JDBC driver selection. Options include MSSQL_PROP (Microsoft JDBC), JTDS_PROP (jTDS). |
| 4 | Host | `HOST` | TEXT | `""` | SQL Server hostname or IP address |
| 5 | Port | `PORT` | TEXT | `"1433"` | SQL Server port. Default 1433 is the standard MSSQL port. |
| 6 | Schema | `DB_SCHEMA` | TEXT | `""` | Database schema name. Note: XML name is DB_SCHEMA, config key is `schema_db` per D-30 MSSQL family naming. |
| 7 | Database | `DBNAME` | TEXT | `""` | Database name to connect to |
| 8 | Username | `USER` | TEXT | `""` | Database login username |
| 9 | Password | `PASS` | PASSWORD | `""` | Database login password. Supports encrypted format with `enc:system.encryption.key.v1:` prefix. |
| 10 | Query | `QUERY` | MEMO_SQL | `"select id, name from employee"` | SQL query to execute. Non-empty default provides an example query. |
| 11 | Specify Datasource Alias | `SPECIFY_DATASOURCE_ALIAS` | CHECK | `false` | When true, uses a runtime datasource alias instead of direct connection |
| 12 | Datasource Alias | `DATASOURCE_ALIAS` | TEXT | `""` | The datasource alias value. Only shown when SPECIFY_DATASOURCE_ALIAS is true. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| A1 | Additional JDBC Properties | `PROPERTIES` | TEXT | `"noDatetimeStringSync=true"` | Additional JDBC connection properties. Non-empty default disables datetime string synchronization for MSSQL compatibility. |
| A2 | Active Directory Authentication | `ACTIVE_DIR_AUTH` | CHECK | `false` | Use Active Directory authentication instead of SQL Server authentication |
| A3 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding for string data. Note: default is ISO-8859-15, not UTF-8. |
| A4 | Trim All Columns | `TRIM_ALL_COLUMN` | CHECK | `false` | When true, trims whitespace from all string column values |
| A5 | Trim Column | `TRIM_COLUMN` | TABLE | `[]` | Per-column trim settings. TABLE parameter with per-column configuration for selective trimming. |
| A6 | Set Query Timeout | `SET_QUERY_TIMEOUT` | CHECK | `false` | When true, enables a query execution timeout |
| A7 | Query Timeout (seconds) | `QUERY_TIMEOUT_IN_SECONDS` | TEXT | `30` | Query timeout in seconds. Only effective when SET_QUERY_TIMEOUT is true. Parsed as integer. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Output | Row > Main | Query result rows emitted to downstream components |
| `REJECT` | Output | Row > Reject | Rows that fail processing (if reject link connected) |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful query execution |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires if query execution fails |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Number of rows read from the query result |
| `{id}_QUERY` | String | After execution | The SQL query that was executed |

### 3.5 Behavioral Notes

1. **DB_SCHEMA naming**: The _java.xml parameter is `DB_SCHEMA` (not `SCHEMA_DB`). The config key is mapped to `schema_db` for MSSQL family naming consistency per D-30.
2. **Non-empty PROPERTIES default**: Unlike most TEXT parameters, PROPERTIES defaults to `"noDatetimeStringSync=true"`. This is a Microsoft JDBC driver property that prevents datetime string synchronization issues.
3. **Encrypted password**: The PASS parameter supports Talend's encrypted password format with `enc:system.encryption.key.v1:` prefix. The converter strips this prefix to extract the actual password value.
4. **Port default 1433**: Standard MSSQL port. Different from Oracle's default 1521.
5. **ISO-8859-15 encoding default**: Not UTF-8. This is consistent across Talend database components.
6. **TRIM_COLUMN TABLE**: Per-column trim settings as a TABLE parameter. When TRIM_ALL_COLUMN is false, individual columns can be configured for trimming.
7. **Query timeout**: QUERY_TIMEOUT_IN_SECONDS is only effective when SET_QUERY_TIMEOUT is true. The value is a TEXT type in _java.xml but represents an integer (default 30).
8. **USE_EXISTING_CONNECTION pattern**: When true, HOST/PORT/DBNAME/USER/PASS/DRIVER are hidden in Talend Studio. The component uses the connection from the referenced tMSSqlConnection component.

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The converter uses the flat config dict pattern (no `_build_component_dict()`). All 20 parameters are extracted using `_get_str()`, `_get_bool()`, and `_get_int()` helpers from the base class. Password extraction uses a custom `_extract_password()` static method that handles the encrypted prefix.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `USE_EXISTING_CONNECTION` | Yes | `use_existing_connection` | bool, default False |
| 2 | `CONNECTION` | Yes | `connection` | str, default "" |
| 3 | `DRIVER` | Yes | `driver` | str, default "MSSQL_PROP" |
| 4 | `HOST` | Yes | `host` | str, default "" |
| 5 | `PORT` | Yes | `port` | str, default "1433" |
| 6 | `DB_SCHEMA` | Yes | `schema_db` | str, default "". XML name DB_SCHEMA, config key schema_db per D-30 |
| 7 | `DBNAME` | Yes | `dbname` | str, default "" |
| 8 | `USER` | Yes | `user` | str, default "" |
| 9 | `PASS` | Yes | `password` | str, default "". Encrypted prefix stripped by `_extract_password()` |
| 10 | `QUERY` | Yes | `query` | str, default "select id, name from employee" |
| 11 | `SPECIFY_DATASOURCE_ALIAS` | Yes | `specify_datasource_alias` | bool, default False |
| 12 | `DATASOURCE_ALIAS` | Yes | `datasource_alias` | str, default "" |
| 13 | `PROPERTIES` | Yes | `properties` | str, default "noDatetimeStringSync=true" (non-empty!) |
| 14 | `ACTIVE_DIR_AUTH` | Yes | `active_dir_auth` | bool, default False |
| 15 | `ENCODING` | Yes | `encoding` | str, default "ISO-8859-15" |
| 16 | `TRIM_ALL_COLUMN` | Yes | `trim_all_column` | bool, default False |
| 17 | `TRIM_COLUMN` | Yes | `trim_column` | list, default [] |
| 18 | `SET_QUERY_TIMEOUT` | Yes | `set_query_timeout` | bool, default False |
| 19 | `QUERY_TIMEOUT_IN_SECONDS` | Yes | `query_timeout_in_seconds` | int, default 30 |
| 20 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | bool, default False (framework) |
| 21 | `LABEL` | Yes | `label` | str, default "" (framework) |

**Summary**: 20 of 20 parameters extracted (100%), plus 2 framework params.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Via `_parse_schema()` with `convert_type()` for Talend-to-Python type mapping |
| `nullable` | Yes | Via `_parse_schema()` |
| `key` | Yes | Via `_parse_schema()` |
| `length` | Yes | Via `_parse_schema()`, included when >= 0 |
| `precision` | Yes | Via `_parse_schema()`, included when >= 0 |
| `pattern` | Yes | Via `_parse_schema()` with Java-to-Python date pattern conversion |
| `default` | No | Not extracted by `_parse_schema()` -- base class limitation |

### 4.3 Expression Handling

Context variable expressions (e.g., `context.DB_HOST`) in parameter values are passed through as-is. The converter does not evaluate expressions -- they are preserved for the engine to resolve at runtime. Java expressions wrapped in `{{...}}` are similarly preserved.

### 4.4 Converter Issues

No open issues. Converter follows gold-standard pattern.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | (all keys) | No concrete engine implementation for tMSSqlInput. All config keys are extracted for future engine support. | engine_gap |

Single consolidated needs_review entry per D-27 (entire engine absent).

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | SQL query execution | **No** | N/A | None | No engine implementation exists |
| 2 | MSSQL connection | **No** | N/A | None | No engine implementation exists |
| 3 | Encrypted password | **No** | N/A | None | Converter strips prefix; engine would need to handle at runtime |
| 4 | Query timeout | **No** | N/A | None | No engine implementation exists |
| 5 | Column trimming | **No** | N/A | None | No engine implementation exists |
| 6 | Active Directory auth | **No** | N/A | None | No engine implementation exists |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-MSI-001 | **P0** | No concrete engine implementation for tMSSqlInput. Component cannot execute. All functionality is missing. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | No | N/A | No engine implementation |
| `{id}_QUERY` | Yes | No | N/A | No engine implementation |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

No engine code exists to audit.

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No issues -- converter follows gold-standard naming with snake_case config keys |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| -- | -- | -- | No violations -- converter follows CONVERTER_PATTERN.md |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

Password values are extracted by the converter. The encrypted prefix (`enc:system.encryption.key.v1:`) is stripped, exposing the encrypted value in the config JSON. This is consistent with all other database components that handle passwords.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- `logger = logging.getLogger(__name__)` at module level |
| Level usage | N/A -- converter does not log (appropriate for simple extraction) |
| Sensitive data | Password is extracted to config JSON (standard pattern) |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | N/A -- converters never raise exceptions (by convention) |
| Exception chaining | N/A |
| die_on_error handling | N/A -- no engine implementation |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- full type hints on `convert()` and `_extract_password()` |
| Parameter types | Good -- `Dict[str, Any]`, `List[str]`, typed returns |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No engine implementation to assess |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- no engine implementation |
| Memory threshold | N/A -- no engine implementation |
| Large data handling | N/A -- no engine implementation |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | ~25 | `tests/converters/talend_to_v1/components/test_mssql_input.py` |
| Engine unit tests | 0 | None -- no engine implementation |
| Integration tests | 0 | None |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-MSI-001 | **P0** | No engine tests -- engine is unimplemented |

### 8.3 Recommended Test Cases

Once engine is implemented:

- Happy path: Execute simple SELECT query, verify row count and data
- Connection modes: Standalone vs USE_EXISTING_CONNECTION
- Query timeout: Verify timeout fires after SET_QUERY_TIMEOUT + QUERY_TIMEOUT_IN_SECONDS
- Column trimming: TRIM_ALL_COLUMN=true and per-column TRIM_COLUMN
- Active Directory authentication
- Error handling: Invalid query, connection failure, authentication error
- Encoding: Non-UTF-8 encoding (ISO-8859-15 default)

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **ENG-MSI-001** |
| P1 | 0 | -- |
| P2 | 0 | -- |
| P3 | 0 | -- |
| **Total** | **1** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 1 | **ENG-MSI-001** |
| Bug (BUG) | 0 | -- |
| Naming (NAME) | 0 | -- |
| Standards (STD) | 0 | -- |
| Performance (PERF) | 0 | -- |
| Testing (TEST) | 1 | **TEST-MSI-001** |

### Cross-Cutting Issues

No cross-cutting issues applicable -- no engine implementation exists to share issues with other components.

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

1. **ENG-MSI-001 (P0)**: Implement concrete MSSqlInput engine class with SQL query execution, connection management, query timeout, column trimming, and Active Directory auth support.

### Short-term (Hardening)

No P1 issues.

### Long-term (Optimization)

No P2/P3 issues -- converter is at gold standard.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub tMSSqlInput_java.xml | `<https://github.com/Talaxie/tdi-studio-se/`> | Component definition XML -- 20 parameters |
| Converter source | `src/converters/talend_to_v1/components/database/mssql_input.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_mssql_input.py` | Test coverage audit |
| tMSSqlConnection converter | `src/converters/talend_to_v1/components/database/mssql_connection.py` | MSSQL family naming reference |
| AUDIT_REPORT_TEMPLATE.md | `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` | Report structure |
| CONVERTER_PATTERN.md | `docs/v1/standards/CONVERTER_PATTERN.md` | Converter code standard |
| TEST_PATTERN.md | `docs/v1/standards/TEST_PATTERN.md` | Test case standard |

## Appendix B: Cross-Cutting Issues

No cross-cutting issues applicable -- no engine implementation exists.

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| -- | -- | No engine code to share issues with |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after v1.1 Phase 08 Plan 05 standardization*
