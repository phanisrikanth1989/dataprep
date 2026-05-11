# Audit Report: tOracleOutput / OracleOutput

> **Audited**: 2026-04-03
> **Reconciled**: 2026-05-11
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
| **Talend Name** | `tOracleOutput` |
| **V1 Engine Class** | `OracleOutput` |
| **Engine File** | `src/v1/engine/components/database/oracle_output.py` (1053 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/database/oracle_output.py` |
| **Converter Dispatch** | `@REGISTRY.register("OracleOutput", "tOracleOutput")` decorator-based dispatch |
| **Registry Aliases** | `OracleOutput`, `tOracleOutput` |
| **Category** | Database / Oracle |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/database/oracle_output.py` | Engine implementation `OracleOutput` (1053 lines) |
| `src/converters/talend_to_v1/components/database/oracle_output.py` | Converter class `OracleOutputConverter` |
| `tests/converters/talend_to_v1/components/test_oracle_output.py` | Converter tests |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_get_int()`, `_parse_schema()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 26 of 26 config keys extracted (100%); all _java.xml params mapped to snake_case |
| Engine Feature Parity | **G** | 0 | 0 | 0 | 0 | OracleOutput engine class implemented in Phase 11 (7cdb043). INSERT/UPDATE/DELETE/INSERT_OR_UPDATE, batch processing, DDL table actions, commit management. |
| Code Quality | **G** | 0 | 0 | 0 | 0 | Engine (1053 lines) and converter both follow pattern conventions. |
| Performance & Memory | **G** | 0 | 0 | 0 | 0 | Batch operations with configurable batch size and commit intervals. |
| Testing | **G** | 0 | 0 | 0 | 0 | Converter tests + 120 engine unit tests (Phase 11) + E2E integration tests. Phase 14-04 coverage corners added (d54b5c1). |

**Overall: GREEN -- Engine implemented in Phase 11 (7cdb043). All issues resolved.**

**Top Actions**: None -- all issues resolved.

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tOracleOutput Does

`tOracleOutput` writes data to an Oracle database table. It receives rows from an input flow and inserts, updates, deletes, or upserts them into the specified Oracle table. The component supports both standalone connection configuration and reuse of an existing shared connection (via `tOracleConnection`).

The component provides flexible table management with TABLE_ACTION (CREATE, DROP_CREATE, DROP_IF_EXISTS_AND_CREATE, CREATE_IF_NOT_EXISTS, NONE, CLEAR, TRUNCATE) and DATA_ACTION (INSERT, UPDATE, INSERT_OR_UPDATE, UPDATE_OR_INSERT, DELETE) modes. Batch operations are supported with configurable batch sizes and commit intervals. Advanced features include Oracle-specific settings like NLS support, TIMESTAMP for DATE types, CHAR trimming, column/table uppercase conversion, field options, and query hints.

**Notable:** tOracleOutput uses `TABLESCHEMA` (not `SCHEMA_DB` like other Oracle components such as tOracleRow, tOracleSP). The password parameter is `PASS` in the _java.xml definition (type PASSWORD). Three boolean parameters default to true: USE_BATCH_SIZE, USE_TIMESTAMP_FOR_DATE_TYPE, and TRIM_CHAR.

**Source**: Talaxie GitHub tdi-studio-se repository (_java.xml definition)
**Component family**: Database / Oracle
**Available in**: All Talend product variants (Open Studio, Enterprise)
**Required JARs**: Oracle JDBC driver (ojdbc)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Use Existing Connection | `USE_EXISTING_CONNECTION` | CHECK | false | Reuse a shared Oracle connection from tOracleConnection |
| 2 | Connection | `CONNECTION` | COMPONENT_LIST | "" | Reference to the tOracleConnection component when USE_EXISTING_CONNECTION is true |
| 3 | Connection Type | `CONNECTION_TYPE` | CLOSED_LIST | "ORACLE_SID" | Oracle connection method: ORACLE_SID, ORACLE_SERVICE_NAME, ORACLE_OCI |
| 4 | DB Version | `DB_VERSION` | CLOSED_LIST | "ORACLE_18" | Oracle database version for driver compatibility |
| 5 | Host | `HOST` | TEXT | "" | Oracle server hostname or IP address |
| 6 | Port | `PORT` | TEXT | "1521" | Oracle listener port number |
| 7 | Database | `DBNAME` | TEXT | "" | Oracle database name (SID or service name depending on CONNECTION_TYPE) |
| 8 | Table Schema | `TABLESCHEMA` | TEXT | "" | Schema that contains the target table. NOTE: tOracleOutput uses TABLESCHEMA, not SCHEMA_DB like other Oracle components |
| 9 | Username | `USER` | TEXT | "" | Database login username |
| 10 | Password | `PASS` | PASSWORD | "" | Database login password. NOTE: _java.xml uses PASS (not PASSWORD) |
| 11 | Table | `TABLE` | DBTABLE | "" | Target database table name |
| 12 | Table Action | `TABLE_ACTION` | CLOSED_LIST | "NONE" | DDL action before writing: NONE, CREATE, DROP_CREATE, DROP_IF_EXISTS_AND_CREATE, CREATE_IF_NOT_EXISTS, CLEAR, TRUNCATE |
| 13 | Data Action | `DATA_ACTION` | CLOSED_LIST | "INSERT" | DML action for each row: INSERT, UPDATE, INSERT_OR_UPDATE, UPDATE_OR_INSERT, DELETE |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| A1 | Commit Every | `COMMIT_EVERY` | TEXT | 10000 | Number of rows between commits. Integer stored as TEXT in XML |
| A2 | Use Batch Size | `USE_BATCH_SIZE` | CHECK | true | Enable JDBC batch operations for performance. Default TRUE |
| A3 | Batch Size | `BATCH_SIZE` | TEXT | 10000 | Number of rows per JDBC batch. Only used when USE_BATCH_SIZE is true |
| A4 | Use Field Options | `USE_FIELD_OPTIONS` | CHECK | false | Enable per-field customization (type overrides, expressions) |
| A5 | Use Hint Options | `USE_HINT_OPTIONS` | CHECK | false | Enable Oracle query hints for INSERT/UPDATE/DELETE operations |
| A6 | Die On Error | `DIE_ON_ERROR` | CHECK | false | Stop job execution on first database error |
| A7 | Enable Debug Mode | `ENABLE_DEBUG_MODE` | CHECK | false | Log SQL statements and parameter values for debugging |
| A8 | Convert Column Table To Uppercase | `CONVERT_COLUMN_TABLE_TO_UPPERCASE` | CHECK | false | Convert column and table names to UPPERCASE for Oracle case sensitivity |
| A9 | Use Timestamp For Date Type | `USE_TIMESTAMP_FOR_DATE_TYPE` | CHECK | true | Map Java Date to Oracle TIMESTAMP instead of DATE. Default TRUE |
| A10 | Trim Char | `TRIM_CHAR` | CHECK | true | Trim trailing whitespace from CHAR columns. Default TRUE |
| A11 | Support NLS | `SUPPORT_NLS` | CHECK | false | Enable Oracle NLS (National Language Support) settings |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Input data rows to write to Oracle table |
| `REJECT` | Output | Row > Reject | Rejected rows with errorCode/errorMessage columns |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when subjob completes successfully |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when subjob fails |
| `ON_COMPONENT_OK` | Output (Trigger) | Trigger | Fires when component completes successfully |
| `ON_COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when component fails |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total number of rows written |
| `{id}_NB_LINE_INSERTED` | Integer | After execution | Number of rows inserted |
| `{id}_NB_LINE_UPDATED` | Integer | After execution | Number of rows updated |
| `{id}_NB_LINE_DELETED` | Integer | After execution | Number of rows deleted |
| `{id}_NB_LINE_REJECTED` | Integer | After execution | Number of rows rejected |

### 3.5 Behavioral Notes

1. **TABLESCHEMA vs SCHEMA_DB**: tOracleOutput uniquely uses `TABLESCHEMA` in _java.xml, while other Oracle components (tOracleRow, tOracleSP, tOracleConnection) use `SCHEMA_DB`. The config key maps to `table_schema` (snake_case of TABLESCHEMA).
2. **PASS not PASSWORD**: The _java.xml parameter name is `PASS` (type PASSWORD), not `PASSWORD`. The config key maps to `password`.
3. **Three true-default booleans**: USE_BATCH_SIZE, USE_TIMESTAMP_FOR_DATE_TYPE, and TRIM_CHAR all default to `true`, unlike most CHECK params which default to `false`.
4. **COMMIT_EVERY and BATCH_SIZE are integers stored as TEXT**: The _java.xml type is TEXT but the values are numeric (default 10000). Converter extracts them as `int`.
5. **TABLE_ACTION and DATA_ACTION are CLOSED_LISTs**: TABLE_ACTION controls DDL (schema operations), DATA_ACTION controls DML (row operations). They are independent.
6. **USE_EXISTING_CONNECTION hides direct connection params**: When true, HOST/PORT/DBNAME/USER/PASS/CONNECTION_TYPE/DB_VERSION are hidden in Talend Studio, but the converter always extracts all params regardless.

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

Flat config dict pattern (no-engine component). All parameters extracted via `_get_str()`, `_get_bool()`, `_get_int()` base class helpers.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `USE_EXISTING_CONNECTION` | Yes | `use_existing_connection` | bool, default false |
| 2 | `CONNECTION` | Yes | `connection` | str, default "" |
| 3 | `CONNECTION_TYPE` | Yes | `connection_type` | str, default "ORACLE_SID" |
| 4 | `DB_VERSION` | Yes | `db_version` | str, default "ORACLE_18" |
| 5 | `HOST` | Yes | `host` | str, default "" |
| 6 | `PORT` | Yes | `port` | str, default "1521" |
| 7 | `DBNAME` | Yes | `dbname` | str, default "" |
| 8 | `TABLESCHEMA` | Yes | `table_schema` | str, default "". NOTE: TABLESCHEMA not SCHEMA_DB |
| 9 | `USER` | Yes | `user` | str, default "" |
| 10 | `PASS` | Yes | `password` | str, default "". NOTE: XML name is PASS, not PASSWORD |
| 11 | `TABLE` | Yes | `table` | str, default "" |
| 12 | `TABLE_ACTION` | Yes | `table_action` | str, default "NONE" |
| 13 | `DATA_ACTION` | Yes | `data_action` | str, default "INSERT" |
| A1 | `COMMIT_EVERY` | Yes | `commit_every` | int, default 10000 |
| A2 | `USE_BATCH_SIZE` | Yes | `use_batch_size` | bool, default true |
| A3 | `BATCH_SIZE` | Yes | `batch_size` | int, default 10000 |
| A4 | `USE_FIELD_OPTIONS` | Yes | `use_field_options` | bool, default false |
| A5 | `USE_HINT_OPTIONS` | Yes | `use_hint_options` | bool, default false |
| A6 | `DIE_ON_ERROR` | Yes | `die_on_error` | bool, default false |
| A7 | `ENABLE_DEBUG_MODE` | Yes | `enable_debug_mode` | bool, default false |
| A8 | `CONVERT_COLUMN_TABLE_TO_UPPERCASE` | Yes | `convert_column_table_to_uppercase` | bool, default false |
| A9 | `USE_TIMESTAMP_FOR_DATE_TYPE` | Yes | `use_timestamp_for_date_type` | bool, default true |
| A10 | `TRIM_CHAR` | Yes | `trim_char` | bool, default true |
| A11 | `SUPPORT_NLS` | Yes | `support_nls` | bool, default false |
| F1 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | bool, default false (framework) |
| F2 | `LABEL` | Yes | `label` | str, default "" (framework) |

**Summary**: 26 of 26 parameters extracted (100%). All config keys in snake_case.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | |
| `key` | Yes | |
| `length` | Yes | |
| `precision` | Yes | |
| `pattern` | Yes | Java-to-Python date pattern conversion via `_convert_date_pattern()` |
| `default` | No | Not supported by base class |

### 4.3 Expression Handling

Context variables (`context.var`) and Java expressions in parameter values are passed through as-is in the config. The converter does not evaluate expressions -- they are preserved for engine-time resolution.

### 4.4 Converter Issues

None -- converter follows gold standard pattern after v1.1 rewrite.

### 4.5 Needs Review Entries

Single consolidated needs_review entry per D-27 (no engine implementation).

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | (all) | No concrete engine implementation for tOracleOutput. All config keys extracted for future engine support. | engine_gap |

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | INSERT operation | **Yes** | High | `oracle_output.py` `_process()` | Phase 11-04 (7cdb043) |
| 2 | UPDATE operation | **Yes** | High | `oracle_output.py` | Key-column WHERE clause generation |
| 3 | INSERT_OR_UPDATE / UPDATE_OR_INSERT | **Yes** | High | `oracle_output.py` | Oracle MERGE logic |
| 4 | DELETE operation | **Yes** | High | `oracle_output.py` | Key-column DELETE |
| 5 | Batch processing | **Yes** | High | `oracle_output.py` | USE_BATCH_SIZE + BATCH_SIZE configurable |
| 6 | DDL TABLE_ACTION | **Yes** | High | `oracle_output.py` | CREATE/DROP_CREATE/TRUNCATE/CLEAR/NONE |
| 7 | COMMIT_EVERY transaction batching | **Yes** | High | `oracle_output.py` | Commit after N rows |
| 8 | Shared connection reuse | **Yes** | High | `oracle_output.py` | USE_EXISTING_CONNECTION reads from OracleConnectionManager |
| 9 | Reject flow | **Yes** | High | `oracle_output.py` | DIE_ON_ERROR=false -> rejected rows |
| 10 | TABLESCHEMA qualified table | **Yes** | High | `oracle_output.py` `_qualified_table()` | Fixed by 11-CR-01 (18819c1) |
| 11 | Upsert (Phase 11-05) | **Yes** | High | `oracle_output.py` | Upsert extended in Phase 11-05 (c3eace8) |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ~~ENG-OO-001~~ | ~~**P0**~~ | ~~No engine implementation exists for tOracleOutput. Component cannot execute.~~ [RESOLVED in Phase 11, 7cdb043 -- OracleOutput engine class implemented with full DML/DDL support] |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `oracle_output.py` via `_update_stats()` | Total rows processed |
| `{id}_NB_LINE_INSERTED` | Yes | Yes | `oracle_output.py` | Inserted rows tracked per-batch |
| `{id}_NB_LINE_UPDATED` | Yes | Yes | `oracle_output.py` | Updated rows tracked per-batch |
| `{id}_NB_LINE_DELETED` | Yes | Yes | `oracle_output.py` | Deleted rows tracked per-batch |
| `{id}_NB_LINE_REJECTED` | Yes | Yes | `oracle_output.py` | Rejected rows when die_on_error=false |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

None -- no engine code exists.

### 6.2 Naming Consistency

None -- converter uses snake_case per gold standard.

### 6.3 Standards Compliance

None -- converter follows CONVERTER_PATTERN.md.

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified for converter. Password parameter (`PASS`) is extracted as a plain string -- engine would need to handle secure password storage/transmission when implemented.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Correct -- `logger = logging.getLogger(__name__)` at module level |
| Level usage | N/A -- converter uses warnings list, not logger |
| Sensitive data | Password extracted as plain text into config (standard for converters) |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | N/A -- converters return ComponentResult with warnings |
| Exception chaining | N/A |
| die_on_error handling | Extracted as config param; no engine to implement behavior |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Full type hints on convert() method |
| Parameter types | All helpers properly typed via base class |

---

## 7. Performance & Memory

Will it scale?

No engine implementation exists, so performance cannot be assessed.

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- no engine implementation |
| Memory threshold | N/A |
| Large data handling | N/A |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 30+ | `tests/converters/talend_to_v1/components/database/test_oracle_output.py` |
| Engine unit tests | 120 | `tests/v1/engine/components/database/test_oracle_output.py` (Phase 11; Phase 14-04 d54b5c1 coverage corners) |
| Integration tests (E2E) | Yes | `tests/v1/engine/components/database/integration/test_oracle_output_e2e.py` |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| ~~TEST-OO-001~~ | ~~**P0**~~ | ~~No engine tests exist because engine is unimplemented~~ [RESOLVED in Phase 11 -- 120 engine tests + E2E integration tests] |

### 8.3 Recommended Test Cases

When engine is implemented:

- INSERT with batch operations (use_batch_size=true, batch_size=10000)
- UPDATE with WHERE clause generation from key columns
- INSERT_OR_UPDATE merge operation
- DELETE operation
- TABLE_ACTION=CREATE DDL generation
- TABLE_ACTION=DROP_CREATE DDL sequence
- COMMIT_EVERY transaction batching
- DIE_ON_ERROR=true stops on first error
- DIE_ON_ERROR=false continues after errors (reject flow)
- TABLESCHEMA qualified table name generation
- NLS support settings
- TIMESTAMP vs DATE type mapping
- TRIM_CHAR behavior
- Column/table uppercase conversion

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | ~~ENG-OO-001~~ [RESOLVED Phase 11, 7cdb043], ~~TEST-OO-001~~ [RESOLVED Phase 11] |
| P1 | 0 | |
| P2 | 0 | |
| P3 | 0 | |
| **Total** | **0 open** | (2 resolved in Phase 11) |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | |
| Engine (ENG) | 0 | ~~ENG-OO-001~~ [RESOLVED Phase 11] |
| Bug (BUG) | 0 | |
| Naming (NAME) | 0 | |
| Standards (STD) | 0 | |
| Performance (PERF) | 0 | |
| Testing (TEST) | 0 | ~~TEST-OO-001~~ [RESOLVED Phase 11] |

### Cross-Cutting Issues

No cross-cutting issues -- no engine implementation to share common base class bugs.

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

- ~~**ENG-OO-001**: Implement concrete OracleOutput engine class.~~ [RESOLVED in Phase 11, 7cdb043]
- ~~**TEST-OO-001**: Add comprehensive engine tests once engine is implemented.~~ [RESOLVED in Phase 11 -- 120 tests + E2E]

### Short-term (Hardening)

- None -- all converter issues resolved in v1.1 rewrite

### Long-term (Optimization)

- Consider connection pooling for high-throughput Oracle output scenarios
- Optimize batch size tuning for large data volumes

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `tOracleOutput_java.xml` from tdi-studio-se repository | Parameter definitions, defaults, types |
| Engine source | `src/v1/engine/components/database/oracle_output.py` | Feature parity analysis (1053 lines) |
| Converter source | `src/converters/talend_to_v1/components/database/oracle_output.py` | Converter audit |
| Engine tests | `tests/v1/engine/components/database/test_oracle_output.py` | Engine test coverage (120 tests) |
| CONVERTER_PATTERN.md | `docs/v1/patterns/CONVERTER_PATTERN.md` | Gold standard converter structure (formerly `docs/v1/standards/CONVERTER_PATTERN.md` -- renamed Phase 15) |
| TEST_PATTERN.md | `docs/v1/patterns/TEST_PATTERN.md` | Gold standard test structure (formerly `docs/v1/standards/TEST_PATTERN.md` -- renamed Phase 15) |
| Base class | `src/converters/talend_to_v1/components/base.py` | Helper method signatures |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| ~~XCUT-001~~ | ~~`base_component.py:304`~~ | ~~`_update_global_map()` crash when globalMap set.~~ [RESOLVED in Phase 7.1, 1f7ec81] |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after v1.1 standardization rewrite*
*Reconciled: 2026-05-11 -- Major status flip RED->GREEN (ENG-OO-001 Phase 11, 7cdb043; TEST-OO-001 Phase 11); Registry Aliases OracleOutput/tOracleOutput; engine file 1053 lines; broken standards/ refs fixed*
