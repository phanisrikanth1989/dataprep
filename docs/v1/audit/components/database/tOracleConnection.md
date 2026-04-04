# Audit Report: tOracleConnection / (No Engine Implementation)

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
| **Talend Name** | `tOracleConnection` |
| **V1 Engine Class** | None -- no concrete engine implementation exists |
| **Engine File** | None -- no engine file for this component |
| **Converter Parser** | `src/converters/talend_to_v1/components/database/oracle_connection.py` |
| **Converter Dispatch** | `@REGISTRY.register("tOracleConnection", "tDBConnection")` decorator-based dispatch |
| **Registry Aliases** | `tOracleConnection`, `tDBConnection` (dual registration) |
| **Category** | Database / Oracle |

### Key Files

| File | Purpose |
|------|---------|
| `src/converters/talend_to_v1/components/database/oracle_connection.py` | Converter class `OracleConnectionConverter` |
| `tests/converters/talend_to_v1/components/test_oracle_connection.py` | Converter tests |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 28 of 28 unique config keys extracted (100%); dual registration preserved (tOracleConnection + tDBConnection); all SSL, TNS, RAC, shared connection, encoding, and advanced params extracted; single consolidated needs_review for engine gap |
| Engine Feature Parity | **R** | 1 | 0 | 0 | 0 | No concrete engine implementation exists; component cannot execute |
| Code Quality | **R** | 1 | 0 | 0 | 0 | Converter code quality is good (follows CONVERTER_PATTERN.md), but no engine code exists at all -- component is incomplete |
| Performance & Memory | **N/A** | 0 | 0 | 0 | 0 | No engine implementation to assess |
| Testing | **R** | 1 | 0 | 0 | 0 | Converter tests pass with full coverage, but 0 engine tests exist because engine is unimplemented. Component is untestable end-to-end. |

**Overall: RED -- No engine implementation. Converter correctly extracts all 28 params for future engine support, but component cannot execute in production. Engine must be implemented before this component is usable.**

**Top Actions**:
1. Implement concrete OracleConnection engine class (P0 -- blocks production use)
2. All converter and test issues resolved in v1.1 rewrite
3. Verify SSL parameter handling in engine once implemented
4. Verify Oracle RAC / Wallet / TNS connection type support in engine
5. Verify shared connection pool behavior in engine

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tOracleConnection Does

`tOracleConnection` establishes an Oracle database connection that can be shared by other Oracle components in the same job. It is the master connection component for the entire Oracle family -- all other Oracle components (tOracleInput, tOracleOutput, tOracleRow, tOracleClose, tOracleCommit, tOracleRollback, tOracleSP, tOracleBulkExec) reference this component via their CONNECTION parameter.

The component supports six connection types: SID (ORACLE_SID), Service Name (ORACLE_SERVICE_NAME), OCI (Oracle Call Interface for local connections), Custom URL, RAC (Real Application Clusters), and Wallet (Oracle Wallet authentication). It also supports SSL encryption with truststore/keystore configuration, TNS file-based connection resolution, shared connection pooling, datasource alias configuration, and Oracle NLS (National Language Support).

This is also registered as `tDBConnection` for backward compatibility, making it a dual-registration component. The dual registration means both `tOracleConnection` and `tDBConnection` Talend type names resolve to the same converter class.

**Source**: Talaxie GitHub tdi-studio-se repository (tOracleConnection_java.xml)
**Component family**: Databases / DB Specifics / Oracle
**Available in**: All Talend product variants (Open Studio, Enterprise)
**Required JARs**: Oracle JDBC driver (ojdbc8.jar or equivalent)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Connection Type | `CONNECTION_TYPE` | CLOSED_LIST | `"ORACLE_SID"` | Connection method: ORACLE_SID, ORACLE_SERVICE_NAME, ORACLE_OCI, ORACLE_CUSTOM, ORACLE_RAC, ORACLE_WALLET |
| 2 | DB Version | `DB_VERSION` | CLOSED_LIST | `"ORACLE_18"` | Database version: ORACLE_12, ORACLE_18, etc. Controls available features (SSL, NLS) |
| 3 | RAC URL | `RAC_URL` | TEXT | `""` | RAC connection URL. Shown only when CONNECTION_TYPE is ORACLE_RAC |
| 4 | Use TNS File | `USE_TNS_FILE` | CHECK | `false` | Use TNS names file for connection resolution. Not available for RAC |
| 5 | TNS File | `TNS_FILE` | FILE | `""` | Path to tnsnames.ora file. Shown when USE_TNS_FILE is true |
| 6 | Host | `HOST` | TEXT | `""` | Oracle server hostname or IP address |
| 7 | Port | `PORT` | TEXT | `"1521"` | Oracle listener port. Default 1521 is the standard Oracle port |
| 8 | Database | `DBNAME` | TEXT | `""` | Database name / SID |
| 9 | Local Service Name | `LOCAL_SERVICE_NAME` | TEXT | `""` | OCI local service name. Shown only when CONNECTION_TYPE is ORACLE_OCI |
| 10 | Schema | `SCHEMA_DB` | TEXT | `""` | Database schema to use |
| 11 | Username | `USER` | TEXT | `""` | Database username |
| 12 | Password | `PASS` | PASSWORD | `""` | Database password. XML name is PASS |
| 13 | JDBC URL | `JDBC_URL` | TEXT | `"jdbc:oracle:thin:USER/MDP@server"` | JDBC connection URL. Used for ORACLE_WALLET connection type |
| 14 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding. Hidden parameter -- ISO-8859-15 is the Talend default, not UTF-8 |
| 15 | Properties | `PROPERTIES` | TEXT | `""` | Additional JDBC connection properties (key=value pairs) |
| 16 | Use Shared Connection | `USE_SHARED_CONNECTION` | CHECK | `false` | Enable shared connection pool for multi-threaded access |
| 17 | Shared Connection Name | `SHARED_CONNECTION_NAME` | TEXT | `""` | Name for the shared connection pool |
| 18 | Specify Datasource Alias | `SPECIFY_DATASOURCE_ALIAS` | CHECK | `false` | Use JNDI datasource instead of direct connection |
| 19 | Datasource Alias | `DATASOURCE_ALIAS` | TEXT | `""` | JNDI datasource alias |
| 20 | Use SSL | `USE_SSL` | CHECK | `false` | Enable SSL encryption. Available for RAC + Oracle 12/18 |
| 21 | SSL Truststore | `SSL_TRUSTSERVER_TRUSTSTORE` | FILE | `""` | Path to SSL truststore file |
| 22 | SSL Truststore Password | `SSL_TRUSTSERVER_PASSWORD` | PASSWORD | `""` | Password for the SSL truststore |
| 23 | Need Client Auth | `NEED_CLIENT_AUTH` | CHECK | `false` | Enable mutual (two-way) SSL authentication |
| 24 | SSL Keystore | `SSL_KEYSTORE` | FILE | `""` | Path to SSL keystore file (for client certificate) |
| 25 | SSL Keystore Password | `SSL_KEYSTORE_PASSWORD` | PASSWORD | `""` | Password for the SSL keystore |
| 26 | Disable CBC Protection | `DISABLE_CBC_PROTECTION` | CHECK | `true` | Disable CBC cipher protection. Default is TRUE (disabled). Oracle 12 SSL compatibility setting |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| A1 | Auto Commit | `AUTO_COMMIT` | CHECK | `false` | Enable auto-commit mode for the connection |
| A2 | Support NLS | `SUPPORT_NLS` | CHECK | `false` | Enable Oracle NLS (National Language Support). Only available for ORACLE_18 DB version |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when connection is established successfully |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when connection fails |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Component-level success |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Component-level error |

No data flow -- this is a connection-only component with no input or output rows.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_CONNECTION` | Connection | After connect | The JDBC Connection object |
| `{id}_URL` | String | After connect | The constructed JDBC URL |
| `{id}_DRIVER` | String | After connect | The JDBC driver class name |
| `{id}_DB` | String | After connect | The database name |
| `{id}_SCHEMA` | String | After connect | The schema name |

### 3.5 Behavioral Notes

1. **Dual registration**: This component is registered as both `tOracleConnection` and `tDBConnection`. The `tDBConnection` alias exists for backward compatibility with older Talend job exports.
2. **ISO-8859-15 encoding default**: The default encoding is ISO-8859-15, NOT UTF-8. This is consistent across all Talend database connection components.
3. **PASS -> password naming**: The XML parameter name is `PASS` (not `PASSWORD`). The config key maps to `password` per D-30 naming consistency.
4. **DISABLE_CBC_PROTECTION defaults to true**: Unlike most CHECK parameters that default to false, this parameter defaults to TRUE. This disables CBC cipher protection for Oracle 12 SSL compatibility.
5. **PORT is TEXT type**: Although PORT carries a numeric value (default "1521"), the _java.xml defines it as TEXT type. The converter stores it as a string to preserve potential context variable references (e.g., `context.DB_PORT`).
6. **Connection type controls parameter visibility**: Different CONNECTION_TYPE values show/hide different parameter sets (e.g., RAC_URL only shown for ORACLE_RAC, LOCAL_SERVICE_NAME only for ORACLE_OCI).
7. **SSL availability**: SSL settings are only available for RAC connection type and Oracle 12/18 DB versions.
8. **Shared connection vs datasource alias**: These are mutually exclusive patterns -- shared connection for multi-threaded pool sharing within the job, datasource alias for JNDI lookup in application server environments.

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The converter uses the flat config dict pattern (no `_build_component_dict()`). All parameters are extracted using base class helpers (`_get_str`, `_get_bool`). The XML name `PASS` maps to config key `password` per D-30.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `CONNECTION_TYPE` | Yes | `connection_type` | str, default "ORACLE_SID" |
| 2 | `DB_VERSION` | Yes | `db_version` | str, default "ORACLE_18" |
| 3 | `RAC_URL` | Yes | `rac_url` | str, default "" |
| 4 | `USE_TNS_FILE` | Yes | `use_tns_file` | bool, default False |
| 5 | `TNS_FILE` | Yes | `tns_file` | str, default "" |
| 6 | `HOST` | Yes | `host` | str, default "" |
| 7 | `PORT` | Yes | `port` | str, default "1521" |
| 8 | `DBNAME` | Yes | `dbname` | str, default "" |
| 9 | `LOCAL_SERVICE_NAME` | Yes | `local_service_name` | str, default "" |
| 10 | `SCHEMA_DB` | Yes | `schema_db` | str, default "" |
| 11 | `USER` | Yes | `user` | str, default "" |
| 12 | `PASS` | Yes | `password` | str, default "". XML is PASS, config key is password per D-30 |
| 13 | `JDBC_URL` | Yes | `jdbc_url` | str, default "jdbc:oracle:thin:USER/MDP@server" |
| 14 | `ENCODING` | Yes | `encoding` | str, default "ISO-8859-15" |
| 15 | `PROPERTIES` | Yes | `properties` | str, default "" |
| 16 | `USE_SHARED_CONNECTION` | Yes | `use_shared_connection` | bool, default False |
| 17 | `SHARED_CONNECTION_NAME` | Yes | `shared_connection_name` | str, default "" |
| 18 | `SPECIFY_DATASOURCE_ALIAS` | Yes | `specify_datasource_alias` | bool, default False |
| 19 | `DATASOURCE_ALIAS` | Yes | `datasource_alias` | str, default "" |
| 20 | `USE_SSL` | Yes | `use_ssl` | bool, default False |
| 21 | `SSL_TRUSTSERVER_TRUSTSTORE` | Yes | `ssl_trustserver_truststore` | str, default "" |
| 22 | `SSL_TRUSTSERVER_PASSWORD` | Yes | `ssl_trustserver_password` | str, default "" |
| 23 | `NEED_CLIENT_AUTH` | Yes | `need_client_auth` | bool, default False |
| 24 | `SSL_KEYSTORE` | Yes | `ssl_keystore` | str, default "" |
| 25 | `SSL_KEYSTORE_PASSWORD` | Yes | `ssl_keystore_password` | str, default "" |
| 26 | `DISABLE_CBC_PROTECTION` | Yes | `disable_cbc_protection` | bool, default True. NOTE: default TRUE |
| 27 | `AUTO_COMMIT` | Yes | `auto_commit` | bool, default False |
| 28 | `SUPPORT_NLS` | Yes | `support_nls` | bool, default False |
| F1 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | bool, default False (framework) |
| F2 | `LABEL` | Yes | `label` | str, default "" (framework) |

**Summary**: 28 of 28 unique parameters extracted (100%), plus 2 framework params. Total: 30 config keys.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| Full schema | Yes | Via `_parse_schema(node)`. Connection components typically have no schema. |

### 4.3 Expression Handling

Context variables (e.g., `context.DB_HOST`) in parameter values are preserved as-is through `_get_str()`. No special expression handling needed -- connection parameters are passed through to the engine.

### 4.4 Converter Issues

No open converter issues. All 28 params extracted, dual registration preserved, flat config dict pattern used.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | (all keys) | No concrete engine implementation for tOracleConnection. All config keys are extracted for future engine support. | engine_gap |

Single consolidated needs_review entry per D-27 (entire engine absent).

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | SID connection | **No** | N/A | None | No engine implementation |
| 2 | Service Name connection | **No** | N/A | None | No engine implementation |
| 3 | OCI connection | **No** | N/A | None | No engine implementation |
| 4 | Custom URL connection | **No** | N/A | None | No engine implementation |
| 5 | RAC connection | **No** | N/A | None | No engine implementation |
| 6 | Wallet connection | **No** | N/A | None | No engine implementation |
| 7 | SSL encryption | **No** | N/A | None | No engine implementation |
| 8 | TNS file support | **No** | N/A | None | No engine implementation |
| 9 | Shared connection pool | **No** | N/A | None | No engine implementation |
| 10 | Auto-commit mode | **No** | N/A | None | No engine implementation |
| 11 | NLS support | **No** | N/A | None | No engine implementation |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-OC-001 | **P0** | **OPEN** -- No engine implementation exists for tOracleConnection. The component cannot execute at all. Converter extracts all params but engine must be implemented. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_CONNECTION` | Yes | No | N/A | No engine implementation |
| `{id}_URL` | Yes | No | N/A | No engine implementation |
| `{id}_DRIVER` | Yes | No | N/A | No engine implementation |
| `{id}_DB` | Yes | No | N/A | No engine implementation |
| `{id}_SCHEMA` | Yes | No | N/A | No engine implementation |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

No engine code exists to assess.

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No issues -- converter follows snake_case naming convention consistently |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| -- | -- | -- | No violations -- converter follows CONVERTER_PATTERN.md |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

Password parameters (`PASS`, `SSL_TRUSTSERVER_PASSWORD`, `SSL_KEYSTORE_PASSWORD`) are extracted as plain strings. In a production engine implementation, these should be handled securely (masked in logs, encrypted at rest).

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Good -- module-level `logger = logging.getLogger(__name__)` |
| Level usage | N/A -- converter does not emit log messages (correct for simple converters) |
| Sensitive data | Passwords extracted as strings -- engine must mask in logs |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | N/A -- converter returns ComponentResult, no exceptions |
| Exception chaining | N/A |
| die_on_error handling | N/A -- connection component does not have die_on_error |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | Good -- fully typed `convert()` method |
| Parameter types | Good -- uses `Dict[str, Any]`, `List[str]`, etc. |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No engine implementation to assess |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | N/A -- no engine implementation |
| Memory threshold | N/A |
| Large data handling | N/A -- connection component, no data flow |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | ~40 | `tests/converters/talend_to_v1/components/test_oracle_connection.py` |
| Engine unit tests | 0 | None -- no engine implementation |
| Integration tests | 0 | None |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-OC-001 | **P0** | **OPEN** -- No engine tests (engine not implemented) |

### 8.3 Recommended Test Cases

Converter tests should cover:
- Registration for both tOracleConnection and tDBConnection
- All 28 parameter defaults
- All 28 parameters extracted with non-default values
- SSL parameter group extraction
- CONNECTION_TYPE alternatives (SERVICE_NAME, OCI, etc.)
- DISABLE_CBC_PROTECTION default True (unusual default)
- PASS XML name -> password config key mapping
- Framework params (tstatcatcher_stats, label)
- Schema extraction
- NeedsReview entry count and structure
- Completeness (all config keys present)

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 2 | **ENG-OC-001**, **TEST-OC-001** |
| P1 | 0 | -- |
| P2 | 0 | -- |
| P3 | 0 | -- |
| **Total** | **2** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Engine (ENG) | 1 | **ENG-OC-001** |
| Testing (TEST) | 1 | **TEST-OC-001** |

### Cross-Cutting Issues

No cross-cutting issues apply -- no engine code exists.

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)
1. **ENG-OC-001**: Implement OracleConnection engine class with support for all 6 connection types, SSL, TNS, shared connections, and auto-commit
2. **TEST-OC-001**: Add engine tests once implementation exists

### Short-term (Hardening)
- Verify password masking in engine logs
- Test SSL mutual authentication flow
- Test RAC failover behavior

### Long-term (Optimization)
- Connection pooling optimization
- Connection timeout configuration
- Oracle Wallet auto-login support

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub _java.xml | `tdi-studio-se/main/components/tOracleConnection_java.xml` | Parameter definitions, defaults, types |
| Converter source | `src/converters/talend_to_v1/components/database/oracle_connection.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_oracle_connection.py` | Test coverage audit |
| Base class | `src/converters/talend_to_v1/components/base.py` | Helper method signatures |
| Registry | `src/converters/talend_to_v1/components/registry.py` | Dual registration verification |

## Appendix B: Cross-Cutting Issues

No cross-cutting issues -- no engine implementation exists.

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after v1.1 standardization rewrite*
