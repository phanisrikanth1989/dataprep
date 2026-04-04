# Audit Report: tOracleInput / (No Engine Implementation)

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
| **Talend Name** | `tOracleInput` |
| **V1 Engine Class** | None -- no concrete engine implementation exists |
| **Engine File** | None -- no engine file for this component |
| **Converter Parser** | `src/converters/talend_to_v1/components/database/oracle_input.py` |
| **Converter Dispatch** | `@REGISTRY.register("tOracleInput")` decorator-based dispatch |
| **Registry Aliases** | `tOracleInput` (single alias) |
| **Category** | Database / Oracle |

### Key Files

| File | Purpose |
|------|---------|
| `src/converters/talend_to_v1/components/database/oracle_input.py` | Converter class `OracleInputConverter` |
| `tests/converters/talend_to_v1/components/test_oracle_input.py` | Converter tests |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 28 of 28 params extracted (100%); USE_EXISTING_CONNECTION, CONNECTION, CONNECTION_TYPE, DB_VERSION, RAC_URL, HOST, PORT, DBNAME, LOCAL_SERVICE_NAME, SCHEMA_DB, USER, PASS->password, JDBC_URL, TABLE, QUERY, SPECIFY_DATASOURCE_ALIAS, DATASOURCE_ALIAS, PROPERTIES, IS_CONVERT_XMLTYPE, CONVERT_XMLTYPE table, ENCODING, USE_CURSOR, CURSOR_SIZE, TRIM_ALL_COLUMN, TRIM_COLUMN table, NO_NULL_VALUES, SUPPORT_NLS + framework params; single consolidated needs_review for engine gap |
| Engine Feature Parity | **R** | 1 | 0 | 0 | 0 | No concrete engine implementation exists; component cannot execute |
| Code Quality | **R** | 1 | 0 | 0 | 0 | Converter code quality is good (follows CONVERTER_PATTERN.md), but no engine code exists at all -- component is incomplete |
| Performance & Memory | **N/A** | 0 | 0 | 0 | 0 | No engine implementation to assess |
| Testing | **R** | 1 | 0 | 0 | 0 | Converter tests pass with full coverage, but 0 engine tests exist because engine is unimplemented. Component is untestable end-to-end. |

**Overall: Red (RED) -- No engine implementation. Converter correctly extracts all 28 params (26 unique + 2 framework, including PASS->password fix, CONVERT_XMLTYPE table, TRIM_COLUMN table, cursor params, NLS support) for future engine support, but component cannot execute in production. Engine must be implemented before this component is usable.**

**Top Actions**:
1. Implement concrete OracleInput engine class (P0 -- blocks production use)
2. All converter and test issues resolved in v1.1 rewrite
3. Wire CONVERT_XMLTYPE XMLType column mapping logic in engine once implemented
4. Wire cursor-based result set fetching in engine once implemented
5. Wire per-column trim logic in engine once implemented

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tOracleInput Does

`tOracleInput` reads data from an Oracle database by executing a SQL query and producing output rows. It is a source component -- it accepts no input rows and emits rows from the query result set on its FLOW output connector.

The component supports multiple connection modes: standalone (providing HOST/PORT/DBNAME/USER/PASS directly), shared (referencing an existing tOracleConnection via USE_EXISTING_CONNECTION), RAC URL, JDBC URL (Wallet), and OCI local service name. It supports Oracle SID or Service Name connection types (CONNECTION_TYPE), multiple Oracle database versions (DB_VERSION), configurable JDBC properties, cursor-based result set fetching (USE_CURSOR/CURSOR_SIZE), XMLType column conversion (IS_CONVERT_XMLTYPE/CONVERT_XMLTYPE table), per-column string trimming (TRIM_ALL_COLUMN/TRIM_COLUMN table), null value replacement (NO_NULL_VALUES), and NLS support (SUPPORT_NLS).

A critical note about the password parameter: the _java.xml definition uses `PASS` (not `PASSWORD`). The prior converter code incorrectly used `PASSWORD` for extraction, which would return empty string when the _java.xml param name is `PASS`. This was fixed in the v1.1 rewrite.

**Source**: Talaxie GitHub tdi-studio-se repository (tOracleInput_java.xml)
**Component family**: Databases / DB Specifics / Oracle
**Available in**: All Talend product variants (Open Studio, Enterprise)
**Required JARs**: Oracle JDBC driver (ojdbc8 or ojdbc11, managed by connection setup)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Use Existing Connection | `USE_EXISTING_CONNECTION` | CHECK | `false` | When true, uses a connection opened by a tOracleConnection component instead of standalone connection params |
| 2 | Connection | `CONNECTION` | COMPONENT_LIST | `""` | References the tOracleConnection component to use. Only shown when USE_EXISTING_CONNECTION is true. Filtered to show only tOracleConnection instances. |
| 3 | Connection Type | `CONNECTION_TYPE` | CLOSED_LIST | `"ORACLE_SID"` | Oracle connection type: ORACLE_SID, ORACLE_SERVICE_NAME, ORACLE_RAC, ORACLE_OCI, ORACLE_WALLET |
| 4 | DB Version | `DB_VERSION` | CLOSED_LIST | `"ORACLE_18"` | Oracle database version: ORACLE_8, ORACLE_9, ORACLE_10, ORACLE_11, ORACLE_12, ORACLE_18 |
| 5 | RAC URL | `RAC_URL` | TEXT | `""` | Oracle RAC JDBC URL. Shown when CONNECTION_TYPE is ORACLE_RAC. |
| 6 | Host | `HOST` | TEXT | `""` | Oracle server hostname |
| 7 | Port | `PORT` | TEXT | `"1521"` | Oracle listener port (default 1521) |
| 8 | Database | `DBNAME` | TEXT | `""` | Oracle SID or service name |
| 9 | Local Service Name | `LOCAL_SERVICE_NAME` | TEXT | `""` | OCI local service name. Shown when CONNECTION_TYPE is ORACLE_OCI. |
| 10 | Schema | `SCHEMA_DB` | TEXT | `""` | Database schema prefix for table references |
| 11 | Username | `USER` | TEXT | `""` | Oracle username |
| 12 | Password | `PASS` | PASSWORD | `""` | Oracle password. NOTE: _java.xml uses `PASS` not `PASSWORD`. Prior converter code incorrectly used `PASSWORD`. |
| 13 | JDBC URL | `JDBC_URL` | TEXT | `""` | JDBC URL for wallet-based connections. Shown when CONNECTION_TYPE is ORACLE_WALLET. |
| 14 | Table Name | `TABLE` | DBTABLE | `""` | Table name for schema auto-detection (not used in query execution) |
| 15 | Query | `QUERY` | MEMO_SQL | `"select id, name from employee"` | SQL query to execute. Multi-line SQL supported. |
| 16 | Specify Datasource Alias | `SPECIFY_DATASOURCE_ALIAS` | CHECK | `false` | When true, enables datasource alias for JNDI lookup |
| 17 | Datasource Alias | `DATASOURCE_ALIAS` | TEXT | `""` | JNDI datasource alias. Shown when SPECIFY_DATASOURCE_ALIAS is true. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| A1 | Additional JDBC Properties | `PROPERTIES` | TEXT | `""` | Additional JDBC connection properties string |
| A2 | Convert XMLType | `IS_CONVERT_XMLTYPE` | CHECK | `false` | When true, enables XMLType column conversion mapping |
| A3 | XMLType Columns | `CONVERT_XMLTYPE` | TABLE | `[]` | Table of XMLType column mappings. Each row maps a schema column to its XMLType source. Shown when IS_CONVERT_XMLTYPE is true. |
| A4 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding for data retrieval. Note: default is ISO-8859-15, not UTF-8. |
| A5 | Use Cursor | `USE_CURSOR` | CHECK | `false` | When true, uses cursor-based result set fetching for large datasets |
| A6 | Cursor Size | `CURSOR_SIZE` | TEXT | `1000` | Number of rows to fetch per cursor round-trip. Shown when USE_CURSOR is true. |
| A7 | Trim All Columns | `TRIM_ALL_COLUMN` | CHECK | `false` | When true, trims whitespace from all string columns |
| A8 | Trim Columns | `TRIM_COLUMN` | TABLE | `[]` | Per-column trim settings. Each row identifies a column to trim. Shown when TRIM_ALL_COLUMN is false. |
| A9 | No Null Values | `NO_NULL_VALUES` | CHECK | `false` | When true, replaces null values with type-appropriate defaults (0 for numbers, empty string for strings) |
| A10 | Support NLS | `SUPPORT_NLS` | CHECK | `false` | When true, enables Oracle NLS (National Language Support) for character set handling. Available for Oracle 18+ (DB_VERSION=ORACLE_18). |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Output | Row > Main | Rows from query result set |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after component completes successfully |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when component encounters an error |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Number of rows read from the query result |
| `{id}_QUERY` | String | After execution | The SQL query that was executed |

### 3.5 Behavioral Notes

1. **PASS vs PASSWORD**: The _java.xml definition uses `PASS` for the password parameter, not `PASSWORD`. This is a common source of bugs when copy-pasting from other component templates.
2. **PORT is TEXT type**: Despite being a port number, PORT is defined as TEXT in _java.xml (default "1521"), allowing context variable expressions. The converter extracts it as a string to preserve expression capability.
3. **CURSOR_SIZE is TEXT type**: Despite being a numeric value, CURSOR_SIZE is defined as TEXT in _java.xml (default 1000), allowing context variable expressions. The converter extracts it as an integer.
4. **ISO-8859-15 encoding default**: The default encoding is ISO-8859-15 (Latin-9), not UTF-8. This matches other Oracle/MSSQL components in the Talend ecosystem.
5. **CONNECTION_TYPE controls visibility**: HOST, PORT, DBNAME are hidden when CONNECTION_TYPE is ORACLE_RAC (RAC_URL shown instead) or ORACLE_WALLET (JDBC_URL shown instead). The converter extracts all params regardless of visibility.
6. **CONVERT_XMLTYPE TABLE structure**: The CONVERT_XMLTYPE table maps schema columns to their XMLType source paths for XML data stored in Oracle XMLType columns.
7. **TRIM_COLUMN TABLE structure**: The TRIM_COLUMN table identifies specific columns to trim when TRIM_ALL_COLUMN is false. Uses elementRef/value structure.

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The converter uses the no-engine flat config dict pattern. All 26 unique parameters plus 2 framework parameters are extracted using `_get_str()`, `_get_bool()`, and `_get_int()` base class helpers. TABLE parameters (CONVERT_XMLTYPE, TRIM_COLUMN) use static parser methods. The converter sets `component_type` and `component_id` in the flat config dict, followed by all params in logical sections, framework params last.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
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
| 12 | `PASS` | Yes | `password` | str, default "". XML name is PASS not PASSWORD. |
| 13 | `JDBC_URL` | Yes | `jdbc_url` | str, default "" |
| 14 | `TABLE` | Yes | `table` | str, default "" |
| 15 | `QUERY` | Yes | `query` | str, default "select id, name from employee" |
| 16 | `SPECIFY_DATASOURCE_ALIAS` | Yes | `specify_datasource_alias` | bool, default False |
| 17 | `DATASOURCE_ALIAS` | Yes | `datasource_alias` | str, default "" |
| 18 | `PROPERTIES` | Yes | `properties` | str, default "" |
| 19 | `IS_CONVERT_XMLTYPE` | Yes | `is_convert_xmltype` | bool, default False |
| 20 | `CONVERT_XMLTYPE` | Yes | `convert_xmltype` | list, default []. TABLE param parsed via _parse_convert_xmltype(). |
| 21 | `ENCODING` | Yes | `encoding` | str, default "ISO-8859-15" |
| 22 | `USE_CURSOR` | Yes | `use_cursor` | bool, default False |
| 23 | `CURSOR_SIZE` | Yes | `cursor_size` | int, default 1000 |
| 24 | `TRIM_ALL_COLUMN` | Yes | `trim_all_column` | bool, default False |
| 25 | `TRIM_COLUMN` | Yes | `trim_column` | list, default []. TABLE param parsed via _parse_trim_column(). |
| 26 | `NO_NULL_VALUES` | Yes | `no_null_values` | bool, default False |
| 27 | `SUPPORT_NLS` | Yes | `support_nls` | bool, default False |
| F1 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | bool, default False. Framework param. |
| F2 | `LABEL` | Yes | `label` | str, default "". Framework param. |

**Summary**: 28 of 28 parameters extracted (100%).

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | Boolean |
| `key` | Yes | Boolean |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion via `_convert_date_pattern()` |
| `default` | No | Not extracted by base class `_parse_schema()` |

### 4.3 Expression Handling

Context variable expressions (e.g., `context.hostname`) are preserved as-is in string parameters. The converter does not evaluate expressions -- it passes them through for the engine to resolve at runtime.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-OIN-001 | ~~P0~~ | **FIXED** -- Prior code used `PASSWORD` for extraction but _java.xml uses `PASS`. Fixed in v1.1 rewrite. |
| CONV-OIN-002 | ~~P1~~ | **FIXED** -- Prior code only extracted 6 of 26 params. Now extracts all 28 (26 unique + 2 framework). |
| CONV-OIN-003 | ~~P1~~ | **FIXED** -- Prior code used `_build_component_dict()`. Now uses flat config dict pattern per D-27. |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | (all keys) | No concrete engine implementation for tOracleInput. All config keys are extracted for future engine support. | engine_gap |

Single consolidated needs_review entry per D-27 (entire engine absent).

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Oracle SQL query execution | **No** | N/A | N/A | No engine implementation |
| 2 | USE_EXISTING_CONNECTION | **No** | N/A | N/A | No engine implementation |
| 3 | Multiple connection types (SID/Service/RAC/OCI/Wallet) | **No** | N/A | N/A | No engine implementation |
| 4 | Cursor-based fetching | **No** | N/A | N/A | No engine implementation |
| 5 | XMLType conversion | **No** | N/A | N/A | No engine implementation |
| 6 | Per-column trimming | **No** | N/A | N/A | No engine implementation |
| 7 | NLS support | **No** | N/A | N/A | No engine implementation |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-OIN-001 | **P0** | No engine implementation exists. tOracleInput cannot execute at all. All 28 config keys are extracted by the converter for future engine support. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | No | N/A | No engine implementation |
| `{id}_QUERY` | Yes | No | N/A | No engine implementation |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-OIN-001 | ~~P0~~ | `oracle_input.py` (prior) | **FIXED** -- `_get_str(node, "PASSWORD")` extracted wrong param name. _java.xml uses `PASS`. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No naming issues. All config keys use snake_case per convention. PASS maps to `password` config key per D-30. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| -- | -- | -- | No standards violations. Converter follows CONVERTER_PATTERN.md. |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

Password is extracted as a plain string via `_get_str()`. No encryption handling needed for Oracle components (unlike MSSQL which has `enc:system.encryption.key.v1:` prefix). The password value flows through as-is from the XML.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` present |
| Level usage | N/A -- converter does not log during normal operation |
| Sensitive data | Password not logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | N/A -- converters never raise, return ComponentResult |
| Exception chaining | N/A |
| die_on_error handling | N/A -- no engine implementation |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | Full type hints on `convert()` method |
| Parameter types | All helper methods (`_get_str`, `_get_bool`, etc.) fully typed |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No engine implementation to assess performance. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | N/A -- no engine implementation |
| Memory threshold | N/A -- no engine implementation |
| Large data handling | N/A -- USE_CURSOR/CURSOR_SIZE params extracted for future cursor-based fetching |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 30+ | `tests/converters/talend_to_v1/components/test_oracle_input.py` |
| Engine unit tests | 0 | None -- no engine implementation |
| Integration tests | 0 | None -- no engine implementation |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-OIN-001 | **P0** | No engine tests -- engine is unimplemented |

### 8.3 Recommended Test Cases

Once engine is implemented:
- Query execution with various SQL types (SELECT, PL/SQL blocks)
- USE_EXISTING_CONNECTION shared connection lifecycle
- Cursor-based fetching with various CURSOR_SIZE values
- XMLType column conversion with CONVERT_XMLTYPE mappings
- Per-column trim with TRIM_COLUMN table entries
- NULL value replacement with NO_NULL_VALUES=true
- Connection type variants (SID, Service Name, RAC, OCI, Wallet)
- NLS character set handling with SUPPORT_NLS=true
- Error handling for connection failures, query errors

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 1 | **ENG-OIN-001** |
| P1 | 0 | |
| P2 | 0 | |
| P3 | 0 | |
| **Total** | **1** | |

Note: Prior converter issues (CONV-OIN-001, CONV-OIN-002, CONV-OIN-003, BUG-OIN-001) all FIXED in v1.1 rewrite.

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Converter (CONV) | 0 (3 fixed) | ~~CONV-OIN-001~~, ~~CONV-OIN-002~~, ~~CONV-OIN-003~~ |
| Engine (ENG) | 1 | **ENG-OIN-001** |
| Bug (BUG) | 0 (1 fixed) | ~~BUG-OIN-001~~ |
| Naming (NAME) | 0 | |
| Standards (STD) | 0 | |
| Performance (PERF) | 0 | |
| Testing (TEST) | 1 | **TEST-OIN-001** (blocked by ENG-OIN-001) |

### Cross-Cutting Issues

No cross-cutting issues apply -- no engine implementation exists.

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)
1. **ENG-OIN-001 (P0)**: Implement concrete OracleInput engine class supporting query execution, connection modes, cursor fetching, XMLType conversion, trimming, and NLS support.

### Short-term (Hardening)
1. Add comprehensive engine tests once implementation exists (TEST-OIN-001).
2. Wire CONVERT_XMLTYPE table parsing into engine XMLType handling.
3. Wire TRIM_COLUMN per-column trim logic into engine.

### Long-term (Optimization)
1. Connection pooling for Oracle connections.
2. Streaming mode for large result sets using cursor-based fetching.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub tOracleInput_java.xml | `tdi-studio-se/main/components/tOracleInput/tOracleInput_java.xml` | Parameter definitions, defaults, types |
| Converter source | `src/converters/talend_to_v1/components/database/oracle_input.py` | Converter audit |
| Converter tests | `tests/converters/talend_to_v1/components/test_oracle_input.py` | Test coverage assessment |
| Base class | `src/converters/talend_to_v1/components/base.py` | Helper method analysis |
| Phase 8 Research | `.planning/phases/08-database-components/08-RESEARCH.md` | Parameter analysis, gap assessment |

## Appendix B: Cross-Cutting Issues

No cross-cutting issues apply -- no engine implementation exists.

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after v1.1 full rewrite*
