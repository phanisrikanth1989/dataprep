# Audit Report: tMSSqlConnection / (No Engine Implementation)

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
| **Talend Name** | `tMSSqlConnection` |
| **V1 Engine Class** | None -- no concrete engine implementation exists |
| **Engine File** | None -- no engine file for this component |
| **Converter Parser** | `src/converters/talend_to_v1/components/database/mssql_connection.py` |
| **Converter Dispatch** | `@REGISTRY.register("tMSSqlConnection")` decorator-based dispatch |
| **Registry Aliases** | `tMSSqlConnection` (single alias) |
| **Category** | Database / MSSQL |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/converters/talend_to_v1/components/database/mssql_connection.py` | Converter class `MSSqlConnectionConverter` |
| `tests/converters/talend_to_v1/components/test_mssql_connection.py` | Converter tests |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 16 of 16 unique config keys extracted (100%); encrypted password handling retained via `_extract_password()`; MSSQL-specific port 1433 default; single consolidated needs_review for engine gap |
| Engine Feature Parity | **R** | 1 | 0 | 0 | 0 | No concrete engine implementation exists; component cannot execute |
| Code Quality | **R** | 1 | 0 | 0 | 0 | Converter code quality is good (follows CONVERTER_PATTERN.md), but no engine code exists at all -- component is incomplete |
| Performance & Memory | **N/A** | 0 | 0 | 0 | 0 | No engine implementation to assess |
| Testing | **R** | 1 | 0 | 0 | 0 | Converter tests pass with full coverage, but 0 engine tests exist because engine is unimplemented. Component is untestable end-to-end. |

**Overall: Red (RED) -- No engine implementation. Converter correctly extracts all 16 unique params (plus 2 framework) for future engine support, including encrypted password handling and MSSQL-specific defaults, but component cannot execute in production. Engine must be implemented before this component is usable.**

**Top Actions**:

1. Implement concrete MSSqlConnection engine class (P0 -- blocks production use)
2. All converter and test issues resolved in v1.1 rewrite

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tMSSqlConnection Does

`tMSSqlConnection` establishes a Microsoft SQL Server database connection that can be shared by other MSSQL components in the same job. It is the MSSQL family equivalent of `tOracleConnection` -- a lifecycle management component that opens a JDBC connection identified by the component instance name.

In a typical Talend job, tMSSqlConnection opens a connection at the start, multiple components (tMSSqlInput, tMSSqlOutput, tMSSqlRow, etc.) use that connection via the `USE_EXISTING_CONNECTION` / `CONNECTION` parameter pattern, and the connection is implicitly closed when the job completes (there is no dedicated tMSSqlClose component). The connection supports two JDBC driver types: the Microsoft proprietary JDBC driver (`MSSQL_PROP`) and the open-source jTDS driver (`JTDS`).

A notable feature is encrypted password handling: Talend Studio stores passwords with an `enc:system.encryption.key.v1:` prefix when encryption is enabled. The converter must strip this prefix to extract the actual encrypted value for downstream processing. The component also supports Windows Active Directory authentication (MSSQL_PROP driver only), shared connection pooling, and datasource alias configuration for application server deployments.

**Source**: Talaxie GitHub tdi-studio-se repository (tMSSqlConnection_java.xml)
**Component family**: Databases / DB Specifics / MSSQL
**Available in**: All Talend product variants (Open Studio, Enterprise)
**Required JARs**: MSSQL JDBC driver (Microsoft or jTDS, depending on DRIVER selection)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Driver | `DRIVER` | CLOSED_LIST | `"MSSQL_PROP"` | JDBC driver selection: `MSSQL_PROP` (Microsoft proprietary) or `JTDS` (open-source jTDS). Affects connection URL format and available features. |
| 2 | Host | `HOST` | TEXT | `""` | Server hostname or IP address. Required. |
| 3 | Port | `PORT` | TEXT | `"1433"` | Server port. Default 1433 is the standard MSSQL port. |
| 4 | Schema | `SCHEMA_DB` | TEXT | `""` | Database schema (dbo, etc.). |
| 5 | Database | `DBNAME` | TEXT | `""` | Database name. Required. |
| 6 | Username | `USER` | TEXT | `""` | Database username. Required (unless Active Directory auth). |
| 7 | Password | `PASS` | PASSWORD | `""` | Database password. May be encrypted with `enc:system.encryption.key.v1:` prefix in .item files. |
| 8 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding for the connection. Hidden parameter. |
| 9 | Additional JDBC Properties | `PROPERTIES` | TEXT | `""` | Additional JDBC connection string properties (e.g., `encrypt=true;trustServerCertificate=false`). |
| 10 | Use Shared Connection | `USE_SHARED_CONNECTION` | CHECK | `false` | Enable connection pooling / shared connection. |
| 11 | Shared Connection Name | `SHARED_CONNECTION_NAME` | TEXT | `""` | Name for the shared connection. Only relevant when `USE_SHARED_CONNECTION` is true. |
| 12 | Specify Datasource Alias | `SPECIFY_DATASOURCE_ALIAS` | CHECK | `false` | Use a runtime datasource alias instead of direct connection. For application server deployments (JBoss, WebSphere, etc.). |
| 13 | Datasource Alias | `DATASOURCE_ALIAS` | TEXT | `""` | The JNDI datasource alias. Only relevant when `SPECIFY_DATASOURCE_ALIAS` is true. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| A1 | Active Directory Auth | `ACTIVE_DIR_AUTH` | CHECK | `false` | Use Windows Active Directory authentication. Only available with MSSQL_PROP driver. When enabled, USER/PASS may not be required. |
| A2 | Auto Commit | `AUTO_COMMIT` | CHECK | `false` | Enable auto-commit mode for transactions. When false, transactions must be explicitly committed. |
| A3 | Share Identity Setting | `SHARE_IDENTITY_SETTING` | CHECK | `false` | Share identity setting across components using this connection. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` | N/A | Row > Main | Max input 0, max output 0. No data flow. |
| `ITERATE` | N/A | Iterate | Max input 0, max output 0. No iterate flow. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after connection is established successfully |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires if connection establishment fails |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires after component completes |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires if component encounters an error |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution of downstream |

### 3.4 GlobalMap Variables

No explicit RETURNS section in _java.xml. The connection object itself is stored internally by Talend runtime for reference by other MSSQL components via the component instance name.

### 3.5 Behavioral Notes

1. **Encrypted password handling**: Talend Studio stores passwords with `enc:system.encryption.key.v1:` prefix when project-level encryption is enabled. The converter strips this prefix to extract the encrypted value. The XML parameter name is `PASS` but the config key is `password` per MSSQL family naming convention (D-30).
2. **MSSQL port 1433**: The default port is 1433, the standard Microsoft SQL Server port. This differs from Oracle's 1521.
3. **DRIVER selection**: `MSSQL_PROP` uses Microsoft's proprietary JDBC driver (`com.microsoft.sqlserver.jdbc.SQLServerDriver`). `JTDS` uses the open-source jTDS driver (`net.sourceforge.jtds.jdbc.Driver`). Active Directory auth is only available with MSSQL_PROP.
4. **No data flow**: tMSSqlConnection has MAX_INPUT=0 and MAX_OUTPUT=0 for both FLOW and ITERATE connectors. It is purely a lifecycle management component.
5. **STARTABLE="true"**: The component can be the start of a subjob (typical placement at job start).
6. **LOG4J_ENABLED="true"**: Talend generates log4j logging code for this component.
7. **No dedicated close component**: Unlike Oracle (which has tOracleClose), the MSSQL family does not have a dedicated close component. Connections are closed when the JVM exits or via shared connection pool management.
8. **ISO-8859-15 encoding default**: The ENCODING parameter defaults to ISO-8859-15 (Latin-9), not UTF-8. This matches the _java.xml source of truth.
9. **MSSQL family naming convention** (D-29): tMSSqlConnection and tMSSqlInput share consistent parameter naming for connection-related fields (HOST, PORT, DBNAME, USER, PASS, DRIVER, ENCODING, PROPERTIES, ACTIVE_DIR_AUTH).

### 3.6 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| F1 | tStatCatcher Stats | `TSTATCATCHER_STATS` | CHECK | `false` | Enable statistics collection for tStatCatcher |
| F2 | Label | `LABEL` | TEXT | `""` | User-defined label for the component instance |

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The converter (`MSSqlConnectionConverter`) uses the flat config dict pattern (no `_build_component_dict`). It extracts all 16 unique parameters via `_get_str()`, `_get_bool()`, and a custom `_extract_password()` static method for encrypted password handling. Framework parameters are extracted last per convention.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `DRIVER` | Yes | `driver` | CLOSED_LIST -> str, default "MSSQL_PROP". |
| 2 | `HOST` | Yes | `host` | TEXT -> str, default "". |
| 3 | `PORT` | Yes | `port` | TEXT -> str, default "1433". MSSQL default port. |
| 4 | `SCHEMA_DB` | Yes | `schema_db` | TEXT -> str, default "". |
| 5 | `DBNAME` | Yes | `dbname` | TEXT -> str, default "". |
| 6 | `USER` | Yes | `user` | TEXT -> str, default "". |
| 7 | `PASS` | Yes | `password` | PASSWORD -> str, default "". XML name is PASS, config key is password per D-30. Encrypted prefix stripped via `_extract_password()`. |
| 8 | `ENCODING` | Yes | `encoding` | ENCODING_TYPE -> str, default "ISO-8859-15". |
| 9 | `PROPERTIES` | Yes | `properties` | TEXT -> str, default "". |
| 10 | `USE_SHARED_CONNECTION` | Yes | `use_shared_connection` | CHECK -> bool, default False. |
| 11 | `SHARED_CONNECTION_NAME` | Yes | `shared_connection_name` | TEXT -> str, default "". |
| 12 | `SPECIFY_DATASOURCE_ALIAS` | Yes | `specify_datasource_alias` | CHECK -> bool, default False. |
| 13 | `DATASOURCE_ALIAS` | Yes | `datasource_alias` | TEXT -> str, default "". |
| 14 | `ACTIVE_DIR_AUTH` | Yes | `active_dir_auth` | CHECK -> bool, default False. MSSQL_PROP only. |
| 15 | `AUTO_COMMIT` | Yes | `auto_commit` | CHECK -> bool, default False. |
| 16 | `SHARE_IDENTITY_SETTING` | Yes | `share_identity_setting` | CHECK -> bool, default False. |
| F1 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | CHECK -> bool, default False. Framework param extracted last. |
| F2 | `LABEL` | Yes | `label` | TEXT -> str, default "". Framework param extracted last. |

**Summary**: 16 of 16 unique parameters extracted (100%). All framework params extracted.

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

Schema extraction is available via the base class but tMSSqlConnection typically has no schema (no data flow). The schema key will be an empty list when no FLOW schema is defined.

### 4.3 Expression Handling

Connection parameters may contain context variable references (e.g., `context.DB_HOST`, `context.DB_PORT`). The `_get_str()` helper preserves these as-is since they are plain strings. No Java expression wrapping is needed for connection parameters.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No converter issues. All parameters correctly extracted per gold standard pattern. |

### 4.5 Needs Review Entries

The converter emits a single consolidated needs_review entry per D-27 (entire engine absent):

| # | Scope | Reason | Severity |
| --- | ------- | -------- | ---------- |
| 1 | Component-level | No concrete engine implementation for tMSSqlConnection. All config keys are extracted for future engine support. | engine_gap |

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

No concrete engine implementation exists for tMSSqlConnection.

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Open MSSQL JDBC connection | **No** | N/A | -- | No engine class exists |
| 2 | MSSQL_PROP driver support | **No** | N/A | -- | No engine class exists |
| 3 | JTDS driver support | **No** | N/A | -- | No engine class exists |
| 4 | Active Directory auth | **No** | N/A | -- | No engine class exists |
| 5 | Shared connection pooling | **No** | N/A | -- | No engine class exists |
| 6 | Datasource alias | **No** | N/A | -- | No engine class exists |
| 7 | Encrypted password decryption | **No** | N/A | -- | No engine class exists |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-MSC-001 | **P0** | **OPEN** -- No concrete MSSqlConnection engine class exists. Jobs using tMSSqlConnection cannot execute in the v1 engine. |

### 5.3 GlobalMap Variable Coverage

tMSSqlConnection does not set any explicit globalMap variables per _java.xml. The connection object is stored internally by the Talend runtime.

---

## 6. Code Quality

How well-written is the converter code?

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| -- | -- | -- | No bugs found in the converter code. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No naming issues. Config keys follow snake_case convention. MSSQL family naming per D-29. PASS -> password per D-30. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| -- | -- | -- | No standards violations. Converter follows CONVERTER_PATTERN.md. |

### 6.4 Debug Artifacts

None found. No print statements, hardcoded paths, or TODO comments.

### 6.5 Security

Password handling is the primary security concern. The converter strips the `enc:system.encryption.key.v1:` encrypted prefix, exposing the encrypted value in the config output. This is by design -- the encrypted value needs to be available for downstream processing. No file I/O, eval, or injection surface.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- `logger = logging.getLogger(__name__)` at module level |
| Level usage | N/A -- logger not used in the converter (appropriate for simple component) |
| Sensitive data | Password value is present in config output -- acceptable for converter (encryption handled at engine level) |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Good -- no exceptions raised per convention (converters never raise) |
| Exception chaining | N/A |
| die_on_error handling | N/A -- tMSSqlConnection has no die_on_error parameter |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- `convert()` fully typed with return type `ComponentResult` |
| Parameter types | Good -- all base class helpers properly typed; `_extract_password()` typed with `str` return |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No performance or memory concerns. The converter is a trivial parameter extractor. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- no engine implementation to assess |
| Memory threshold | N/A |
| Large data handling | N/A -- no data flow (connection component) |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | Yes | `tests/converters/talend_to_v1/components/test_mssql_connection.py` |
| Engine unit tests | 0 | None -- no engine implementation |
| Integration tests | 0 | None |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-MSC-001 | **P0** | **OPEN** -- No engine tests exist because no engine implementation exists |

### 8.3 Recommended Test Cases

When the engine is implemented, test:

- Connection establishment with MSSQL_PROP driver
- Connection establishment with JTDS driver
- Active Directory authentication flow
- Encrypted password decryption
- Shared connection pooling
- Datasource alias resolution
- Connection failure handling (wrong host, port, credentials)
- Auto-commit behavior

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 3 | **ENG-MSC-001**, **TEST-MSC-001**, (engine absent -- all dimensions affected) |
| P1 | 0 | -- |
| P2 | 0 | -- |
| P3 | 0 | -- |
| **Total** | **3** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 1 | **ENG-MSC-001** |
| Bug (BUG) | 0 | -- |
| Naming (NAME) | 0 | -- |
| Standards (STD) | 0 | -- |
| Performance (PERF) | 0 | -- |
| Testing (TEST) | 1 | **TEST-MSC-001** |

### Cross-Cutting Issues

No cross-cutting issues apply. tMSSqlConnection has no engine implementation, so engine-level cross-cutting bugs (globalMap crashes, streaming mode, etc.) are not relevant until an engine class is created.

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

1. **ENG-MSC-001 (P0)**: Implement concrete MSSqlConnection engine class with JDBC connection management, driver selection, and Active Directory auth support
2. **TEST-MSC-001 (P0)**: Create engine unit tests covering connection lifecycle, auth modes, and error handling

### Short-term (Hardening)

No P1/P2 issues identified. Converter is fully standardized.

### Long-term (Optimization)

No P3 issues identified.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `tdi-studio-se/main/components/tMSSqlConnection/tMSSqlConnection_java.xml` | Parameter definitions, defaults, types |
| Converter source | `src/converters/talend_to_v1/components/database/mssql_connection.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_mssql_connection.py` | Test coverage audit |
| Phase 8 Research | `.planning/phases/08-database-components/08-RESEARCH.md` | Parameter cross-reference |
| MSSQL documentation | Microsoft SQL Server JDBC documentation | Driver and connection properties |

## Appendix B: Cross-Cutting Issues

No cross-cutting issues apply to tMSSqlConnection at this time. The component has no engine implementation, so engine-level cross-cutting bugs are not relevant.

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| -- | -- | No engine code exists -- cross-cutting engine bugs do not apply |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after v1.1 Phase 08 standardization*
