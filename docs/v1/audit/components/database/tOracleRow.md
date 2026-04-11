# Audit Report: tOracleRow / (No Engine Implementation)

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
| **Talend Name** | `tOracleRow` |
| **V1 Engine Class** | None -- no concrete engine implementation exists |
| **Engine File** | None -- no engine file for this component |
| **Converter Parser** | `src/converters/talend_to_v1/components/database/oracle_row.py` |
| **Converter Dispatch** | `@REGISTRY.register("tOracleRow")` decorator-based dispatch |
| **Registry Aliases** | `tOracleRow` (single alias) |
| **Category** | Databases / DB Specifics / Oracle |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/converters/talend_to_v1/components/database/oracle_row.py` | Converter class `OracleRowConverter` |
| `tests/converters/talend_to_v1/components/test_oracle_row.py` | Converter tests |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 26 of 26 unique config keys extracted (100%); all connection, query, prepared statement, datasource, and advanced params extracted; framework params extracted; single consolidated needs_review for engine gap |
| Engine Feature Parity | **R** | 1 | 0 | 0 | 0 | No concrete engine implementation exists; component cannot execute |
| Code Quality | **R** | 1 | 0 | 0 | 0 | Converter code quality is good (follows CONVERTER_PATTERN.md), but no engine code exists at all -- component is incomplete |
| Performance & Memory | **N/A** | 0 | 0 | 0 | 0 | No engine implementation to assess |
| Testing | **R** | 1 | 0 | 0 | 0 | Converter tests pass with full coverage, but 0 engine tests exist because engine is unimplemented. Component is untestable end-to-end. |

**Overall: RED -- No engine implementation. Converter correctly extracts all params for future engine support, but component cannot execute in production. Engine must be implemented before this component is usable.**

**Top Actions**:

1. Implement concrete OracleRow engine class (P0 -- blocks production use)
2. All converter and test issues resolved in v1.1 rewrite

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tOracleRow Does

`tOracleRow` executes arbitrary SQL statements (INSERT, UPDATE, DELETE, or DDL) against an Oracle database. Unlike `tOracleInput` (which is read-only SELECT) or `tOracleOutput` (which is table-oriented DML), tOracleRow is designed for executing free-form SQL queries that may modify data. It supports both direct connections and reuse of an existing connection opened by `tOracleConnection`.

The component accepts an optional input flow (up to 1 row at a time) and can produce an output flow. When an input flow is connected, the SQL query can reference input columns using `?` placeholders via prepared statements. The `USE_NB_LINE` parameter controls which row count metric (inserted/updated/deleted) is tracked in globalMap. The `PROPAGATE_RECORD_SET` option allows the entire JDBC ResultSet to be passed downstream for advanced processing scenarios.

When `DIE_ON_ERROR` is false, a REJECT flow connector becomes available, routing failed rows with `errorCode` and `errorMessage` columns. The component supports all Oracle connection types (SID, Service Name, OCI, RAC) and can use prepared statements with typed parameters for parameterized queries.

**Source**: Talaxie GitHub tdi-studio-se repository (tOracleRow_java.xml)
**Component family**: Databases / DB Specifics / Oracle
**Available in**: All Talend product variants (Open Studio, Enterprise)
**Required JARs**: Oracle JDBC driver (ojdbc8 for Oracle 18, ojdbc7 for Oracle 12, ojdbc6 for Oracle 11)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Use existing connection | `USE_EXISTING_CONNECTION` | CHECK | `false` | When true, reuses a connection opened by tOracleConnection. When false, creates its own connection. |
| 2 | Connection | `CONNECTION` | COMPONENT_LIST | `""` | Required when USE_EXISTING_CONNECTION is true. References the tOracleConnection component. Filter: tOracleConnection only. |
| 3 | Connection type | `CONNECTION_TYPE` | CLOSED_LIST | `"ORACLE_SID"` | Oracle connection method. Options: ORACLE_SID, ORACLE_SERVICE_NAME, ORACLE_OCI, ORACLE_RAC. Shown when not using existing connection. |
| 4 | Database version | `DB_VERSION` | CLOSED_LIST | `"ORACLE_18"` | Oracle database version for JDBC driver selection. Options: ORACLE_18, ORACLE_12, ORACLE_11. Shown when not using existing connection. |
| 5 | RAC URL | `RAC_URL` | TEXT | `""` | Oracle RAC connection URL. Required when CONNECTION_TYPE is ORACLE_RAC. |
| 6 | Host | `HOST` | TEXT | `""` | Database server hostname. Shown for SID and Service Name connection types (not OCI or RAC). |
| 7 | Port | `PORT` | TEXT | `"1521"` | Oracle listener port. Default 1521. Shown for SID and Service Name connection types. |
| 8 | Database name | `DBNAME` | TEXT | `""` | Oracle SID or database name. Shown for SID and Service Name connection types. |
| 9 | Local service name | `LOCAL_SERVICE_NAME` | TEXT | `""` | OCI local service name. Required when CONNECTION_TYPE is ORACLE_OCI. |
| 10 | Schema | `SCHEMA_DB` | TEXT | `""` | Database schema. Shown when not using existing connection. |
| 11 | Username | `USER` | TEXT | `""` | Database username. Shown when not using existing connection. |
| 12 | Password | `PASS` | PASSWORD | `""` | Database password. Note: _java.xml uses `PASS` (not `PASSWORD`). Shown when not using existing connection. |
| 13 | Table | `TABLE` | DBTABLE | `""` | Table name reference for query building assistance. |
| 14 | Query | `QUERY` | MEMO_SQL | `"select id, name from employee"` | SQL query to execute. Can be INSERT, UPDATE, DELETE, or DDL. Supports `?` placeholders for prepared statements. |
| 15 | Use NB Line | `USE_NB_LINE` | CLOSED_LIST | `"NONE"` | Row count tracking mode. Options: NONE, NB_LINE_INSERTED, NB_LINE_UPDATED, NB_LINE_DELETED. Controls which globalMap counter is populated after execution. |
| 16 | Specify datasource alias | `SPECIFY_DATASOURCE_ALIAS` | CHECK | `false` | Enable runtime datasource alias for Talaxie Runtime deployment. Shown when not using existing connection. |
| 17 | Datasource alias | `DATASOURCE_ALIAS` | TEXT | `""` | Datasource alias value. Required when SPECIFY_DATASOURCE_ALIAS is true. |
| 18 | Die on error | `DIE_ON_ERROR` | CHECK | `false` | When true, component throws exception on SQL error. When false, errors are routed to REJECT flow. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| A1 | JDBC properties | `PROPERTIES` | TEXT | `""` | Additional JDBC connection parameters. Format: "param1=value1&&param2=value2". Shown when not using existing connection. |
| A2 | Propagate record set | `PROPAGATE_RECORD_SET` | CHECK | `false` | When true, propagates the JDBC ResultSet object downstream for advanced processing. |
| A3 | Record set column | `RECORD_SET_COLUMN` | COLUMN_LIST | `""` | Column to receive the ResultSet. Shown when PROPAGATE_RECORD_SET is true. |
| A4 | Use prepared statement | `USE_PREPAREDSTATEMENT` | CHECK | `false` | Enable JDBC prepared statements with typed parameters. |
| A5 | Prepared statement parameters | `SET_PREPAREDSTATEMENT_PARAMETERS` | TABLE | `[]` | Table of prepared statement parameter definitions. Stride-3 TABLE with fields: PARAMETER_INDEX (index position), PARAMETER_TYPE (CLOSED_LIST: BigDecimal, Blob, Boolean, Byte, Bytes, Clob, Date, Double, Float, Int, Long, Object, Short, String, Time, Null; default "String"), PARAMETER_VALUE (value expression). Shown when USE_PREPAREDSTATEMENT is true. |
| A6 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding. Hidden field -- not shown in UI but present in _java.xml. |
| A7 | Commit every | `COMMIT_EVERY` | TEXT | `10000` | Number of rows between commits. Shown when not using existing connection. |
| A8 | NLS support | `SUPPORT_NLS` | CHECK | `false` | Oracle NLS (National Language Support). Only available for ORACLE_18 version. Shown when not using existing connection. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input/Output | Row > Main | Input: receives rows for parameterized queries. Output: passes rows through (max 1 in, 1 out). |
| `REJECT` | Output | Row > Reject | Failed rows with errorCode and errorMessage columns. Only available when DIE_ON_ERROR is false. |
| `ITERATE` | Input/Output | Iterate | Iterate connector (max 1 in, 1 out). |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires after subjob encounters an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires after component completes successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires after component encounters an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution of downstream. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_QUERY` | String | During FLOW | The SQL query being executed. |
| `{id}_NB_LINE_UPDATED` | Integer | After execution | Number of rows updated (when USE_NB_LINE == NB_LINE_UPDATED). |
| `{id}_NB_LINE_INSERTED` | Integer | After execution | Number of rows inserted (when USE_NB_LINE == NB_LINE_INSERTED). |
| `{id}_NB_LINE_DELETED` | Integer | After execution | Number of rows deleted (when USE_NB_LINE == NB_LINE_DELETED). |

### 3.5 Behavioral Notes

1. **PASS not PASSWORD**: The _java.xml parameter name is `PASS` (PASSWORD type field), not `PASSWORD`. The previous converter code incorrectly used `PASSWORD` which would always extract empty string.
2. **SET_PREPAREDSTATEMENT_PARAMETERS TABLE structure**: Stride-3 with fields PARAMETER_INDEX, PARAMETER_TYPE (CLOSED_LIST with 16 type options, default "String"), and PARAMETER_VALUE. Each group of 3 entries in the TABLE represents one prepared statement parameter.
3. **USE_NB_LINE CLOSED_LIST**: Has 4 values (NONE, NB_LINE_INSERTED, NB_LINE_UPDATED, NB_LINE_DELETED). Controls which row counter globalMap variable is populated.
4. **PROPAGATE_RECORD_SET**: When enabled, the JDBC ResultSet is passed as an object through the specified column rather than being consumed row-by-row. This is an advanced feature for custom ResultSet processing.
5. **DIE_ON_ERROR controls REJECT flow**: When DIE_ON_ERROR is true, the REJECT connector is hidden (NOT_SHOW_IF condition). Errors cause immediate job failure. When false, errors route to REJECT with errorCode/errorMessage.
6. **PORT is TEXT type**: The _java.xml declares PORT as TEXT (not numeric), with default `"1521"`. This is consistent across Oracle components.
7. **CONNECTION_TYPE options**: ORACLE_SID (default), ORACLE_SERVICE_NAME, ORACLE_OCI, ORACLE_RAC. Each type shows/hides different connection fields via SHOW_IF conditions.
8. **RAC_URL**: Required only for ORACLE_RAC connection type. Provides the full RAC connection URL.
9. **ENCODING is hidden**: The ENCODING parameter has `SHOW="false"` -- it exists in _java.xml but is not visible in the Talend Studio UI. Default is ISO-8859-15 (not UTF-8).
10. **COMMIT_EVERY and SUPPORT_NLS**: Both are only relevant when not using an existing connection (SHOW_IF conditions).

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The converter uses the flat config dict pattern (no-engine component). All 26 unique parameters plus 2 framework parameters are extracted via `_get_str()`, `_get_bool()`, `_get_int()`, and a stride-based TABLE parser for SET_PREPAREDSTATEMENT_PARAMETERS.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `USE_EXISTING_CONNECTION` | Yes | `use_existing_connection` | bool, default False |
| 2 | `CONNECTION` | Yes | `connection` | str, default "" |
| 3 | `CONNECTION_TYPE` | Yes | `connection_type` | str, default "ORACLE_SID" |
| 4 | `DB_VERSION` | Yes | `db_version` | str, default "ORACLE_18" |
| 5 | `RAC_URL` | Yes | `rac_url` | str, default "" |
| 6 | `HOST` | Yes | `host` | str, default "" |
| 7 | `PORT` | Yes | `port` | str, default "1521" |
| 8 | `DBNAME` | Yes | `dbname` | str, default "" |
| 9 | `LOCAL_SERVICE_NAME` | Yes | `local_service_name` | str, default "" |
| 10 | `SCHEMA_DB` | Yes | `schema_db` | str, default "" |
| 11 | `USER` | Yes | `user` | str, default "" |
| 12 | `PASS` | Yes | `password` | str, default "" (XML name is PASS, not PASSWORD) |
| 13 | `TABLE` | Yes | `table` | str, default "" |
| 14 | `QUERY` | Yes | `query` | str, default "select id, name from employee" |
| 15 | `USE_NB_LINE` | Yes | `use_nb_line` | str, default "NONE" |
| 16 | `SPECIFY_DATASOURCE_ALIAS` | Yes | `specify_datasource_alias` | bool, default False |
| 17 | `DATASOURCE_ALIAS` | Yes | `datasource_alias` | str, default "" |
| 18 | `DIE_ON_ERROR` | Yes | `die_on_error` | bool, default False |
| 19 | `PROPERTIES` | Yes | `properties` | str, default "" |
| 20 | `PROPAGATE_RECORD_SET` | Yes | `propagate_record_set` | bool, default False |
| 21 | `RECORD_SET_COLUMN` | Yes | `record_set_column` | str, default "" |
| 22 | `USE_PREPAREDSTATEMENT` | Yes | `use_preparedstatement` | bool, default False |
| 23 | `SET_PREPAREDSTATEMENT_PARAMETERS` | Yes | `set_preparedstatement_parameters` | list[dict], stride-3 TABLE parser |
| 24 | `ENCODING` | Yes | `encoding` | str, default "ISO-8859-15" |
| 25 | `COMMIT_EVERY` | Yes | `commit_every` | int, default 10000 |
| 26 | `SUPPORT_NLS` | Yes | `support_nls` | bool, default False |
| F1 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | bool, default False |
| F2 | `LABEL` | Yes | `label` | str, default "" |

**Summary**: 26 of 26 unique parameters extracted (100%), plus 2 framework parameters.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Converted via `convert_type()` |
| `nullable` | Yes | Boolean |
| `key` | Yes | Boolean |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by base `_parse_schema()` |

### 4.3 Expression Handling

Context variables (`context.var`) and Java expressions (`{{java}}`) are passed through as-is in string parameter values. The converter does not evaluate or transform expressions -- they are preserved for engine resolution at runtime.

### 4.4 Converter Issues

None -- all converter issues resolved in v1.1 rewrite.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | (all keys) | No concrete engine implementation for tOracleRow. All config keys are extracted for future engine support. | engine_gap |

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | SQL query execution | **No** | N/A | None | No engine implementation exists |
| 2 | Prepared statements | **No** | N/A | None | No engine implementation exists |
| 3 | Connection management | **No** | N/A | None | No engine implementation exists |
| 4 | REJECT flow | **No** | N/A | None | No engine implementation exists |
| 5 | Row count tracking | **No** | N/A | None | No engine implementation exists |
| 6 | Record set propagation | **No** | N/A | None | No engine implementation exists |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-ORC-001 | **P0** | No engine implementation exists. Component cannot execute any SQL queries. All 26 config keys are extracted by the converter but have no engine to consume them. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_QUERY` | Yes | No | N/A | No engine implementation |
| `{id}_NB_LINE_UPDATED` | Yes | No | N/A | No engine implementation |
| `{id}_NB_LINE_INSERTED` | Yes | No | N/A | No engine implementation |
| `{id}_NB_LINE_DELETED` | Yes | No | N/A | No engine implementation |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

No engine code exists. Converter code has no bugs after v1.1 rewrite.

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No issues. Converter follows snake_case convention for all config keys. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| -- | -- | -- | Converter follows CONVERTER_PATTERN.md. No violations. |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No engine code to assess. Converter passes password values through as-is (no plaintext logging).

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Module-level `logger = logging.getLogger(__name__)` present |
| Level usage | N/A -- converter uses no log statements (appropriate for simple extraction) |
| Sensitive data | Password not logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | N/A -- converters never raise exceptions |
| Exception chaining | N/A |
| die_on_error handling | Extracted as config key; engine handling N/A |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Fully typed: `convert()` with `TalendNode`, `List[TalendConnection]`, `Dict[str, Any]` -> `ComponentResult` |
| Parameter types | All helper calls use typed defaults |

---

## 7. Performance & Memory

Will it scale?

No engine implementation to assess.

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- no engine |
| Memory threshold | N/A |
| Large data handling | N/A |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | ~35 | `tests/converters/talend_to_v1/components/test_oracle_row.py` |
| Engine unit tests | 0 | None -- no engine implementation |
| Integration tests | 0 | None |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-ORC-001 | **P0** | No engine tests (engine is unimplemented) |

### 8.3 Recommended Test Cases

- Engine implementation tests (when engine is built): query execution, prepared statements, REJECT flow, row counting, connection reuse
- Integration tests with actual Oracle database (when engine is built)

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 3 | **ENG-ORC-001**, **TEST-ORC-001**, (engine missing -- affects Engine, Code Quality, Testing dimensions) |
| P1 | 0 | -- |
| P2 | 0 | -- |
| P3 | 0 | -- |
| **Total** | **3** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 1 | **ENG-ORC-001** |
| Bug (BUG) | 0 | -- |
| Naming (NAME) | 0 | -- |
| Standards (STD) | 0 | -- |
| Performance (PERF) | 0 | -- |
| Testing (TEST) | 1 | **TEST-ORC-001** |

### Cross-Cutting Issues

All P0 issues are due to missing engine implementation -- same root cause as all other no-engine database components.

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

1. **Implement OracleRow engine class** (P0 -- ENG-ORC-001): Must support SQL execution, prepared statements, REJECT flow, row count tracking, and connection management.

### Short-term (Hardening)

No P1 issues.

### Long-term (Optimization)

No P2/P3 issues. Converter is fully standardized.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `<https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tOracleRow/tOracleRow_java.xml`> | Parameter definitions, defaults, TABLE structures, connection types |
| Converter source | `src/converters/talend_to_v1/components/database/oracle_row.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_oracle_row.py` | Testing coverage audit |
| Base class | `src/converters/talend_to_v1/components/base.py` | Helper method signatures |

## Appendix B: Cross-Cutting Issues

No engine implementation exists, so no cross-cutting engine issues apply.

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| -- | -- | No engine code to analyze |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after v1.1 standardization rewrite*
