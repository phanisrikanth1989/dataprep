# External Integrations

**Analysis Date:** 2026-04-14

## APIs & External Services

**No external API integrations detected.**

This is a self-contained ETL conversion and execution system. It does not call external HTTP APIs, cloud services, or SaaS platforms. All processing happens locally.

## Data Storage

**Databases (Converter - generates configs for):**
- Oracle Database - Converter generates V1 configs for Oracle components
  - Components: `tOracleConnection`, `tOracleInput`, `tOracleOutput`, `tOracleRow`, `tOracleSP`, `tOracleBulkExec`, `tOracleCommit`, `tOracleClose`, `tOracleRollback`
  - Converter files: `src/converters/talend_to_v1/components/database/oracle_*.py`
  - Test files: `tests/converters/talend_to_v1/components/database/test_oracle_*.py`
- MS SQL Server - Converter generates V1 configs for MSSQL components
  - Components: `tMSSqlConnection`, `tMSSqlInput`
  - Converter files: `src/converters/talend_to_v1/components/database/mssql_*.py`
  - Test files: `tests/converters/talend_to_v1/components/database/test_mssql_*.py`

**Databases (Engine - commented out):**
- Database engine components are fully commented out in `src/v1/engine/engine.py:35-38` and `src/v1/engine/engine.py:182-204`
- No database engine components exist in `src/v1/engine/components/` (no `database/` directory)
- The converter can produce database component configs, but the engine cannot execute them yet

**File Storage:**
- Local filesystem only
- File I/O components handle: CSV, TSV, delimited, positional, Excel (.xls/.xlsx), JSON, XML, raw text, EBCDIC, properties files
- Archive support: ZIP/GZIP via `src/v1/engine/components/file/file_archive.py` and `file_unarchive.py`
- Engine file components: `src/v1/engine/components/file/`

**Caching:**
- None. No Redis, Memcached, or other caching layers.

## Authentication & Identity

**No authentication system.**
- No auth provider, OAuth, JWT, or session management
- Database connection credentials would be embedded in job configs as context variables (when database components are implemented)

## Monitoring & Observability

**Error Tracking:**
- None. No Sentry, Datadog, or external error tracking.

**Logs:**
- Python `logging` module used throughout
- Configured via `logging.basicConfig(level=logging.INFO)` in `src/v1/engine/engine.py:46`
- Logger per module pattern: `logger = logging.getLogger(__name__)`
- No structured logging, log aggregation, or external log shipping

**Execution Statistics:**
- Built-in stats tracking via `GlobalMap` (`src/v1/engine/global_map.py`)
- Per-component stats: `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT`, `NB_LINE_INSERT`, `NB_LINE_UPDATE`, `NB_LINE_DELETE`, `EXECUTION_TIME`
- Job-level stats returned by `ETLEngine.execute()` method

## CI/CD & Deployment

**Hosting:**
- Not detected. No Dockerfile, docker-compose, Kubernetes configs, or cloud deployment files.

**CI Pipeline:**
- Not detected. No `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, or other CI config.

## Inter-Process Communication

**Python-Java Bridge:**
- Protocol: Py4J gateway (TCP socket-based RPC)
- Data Format: Apache Arrow IPC streaming format for DataFrame transfer
- Port: Dynamically allocated per job via `JavaBridgeManager._find_free_port()` in `src/v1/engine/java_bridge_manager.py:102-110`
- Default fallback port: 25333 (in `src/v1/java_bridge/bridge.py:37`)
- Lifecycle: Java process started via `subprocess.Popen` per job, stopped on job completion
- Java entry point: `com.citi.gru.etl.JavaBridge` (Py4J `GatewayServer`)
- Python client: `src/v1/java_bridge/bridge.py` (`JavaBridge` class)
- Manager: `src/v1/engine/java_bridge_manager.py` (`JavaBridgeManager` class)

**Bridge capabilities:**
- `executeJavaRow()` - Execute Java code on DataFrame rows (tJavaRow)
- `executeOneTimeExpression()` - Resolve single Java expressions (config values)
- `executeBatchOneTimeExpressions()` - Batch-resolve Java expressions
- `executeTMapPreprocessing()` - Evaluate tMap filter/join expressions per row
- `executeTMapCompiled()` - Execute compiled tMap scripts on DataFrames
- `compileTMapScript()` / `executeCompiledTMap()` - Compile-once, execute-many pattern for chunked tMap processing
- `loadRoutine()` - Load custom Java routine classes

## Environment Configuration

**Required env vars:**
- None. All configuration is passed via JSON job config files.

**Job Configuration (JSON):**
- `job_name` - Job identifier
- `job_type` - Job type (e.g., "Standard")
- `default_context` - Default context group name
- `context` - Context variables with values and types
- `components` - Array of component definitions
- `flows` - Data flow connections between components
- `triggers` - Trigger connections (OnSubjobOk, OnComponentOk, RunIf, etc.)
- `subjobs` - Subjob groupings
- `java_config.enabled` - Whether Java bridge is needed
- `java_config.routines` - Java routine classes to load
- `java_config.libraries` - Required JAR files to validate

**Secrets location:**
- No dedicated secrets management
- Database credentials would be in context variables within JSON configs (when database components are enabled)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Email Integration

**SMTP:**
- `tSendMail` component (`src/v1/engine/components/control/send_mail.py`) supports sending emails via SMTP
- Uses Python stdlib `smtplib` and `email` modules
- Configuration via component config: SMTP host, port, TLS, auth credentials, recipients
- Converter: `src/converters/talend_to_v1/components/control/send_mail.py`

## Input File Formats

**Talend `.item` XML files (Converter input):**
- Parsed by `src/converters/talend_to_v1/xml_parser.py`
- XML format with `<node>`, `<connection>`, `<context>`, `<metadata>` elements
- Sample files: `tests/talend_xml_samples/*.item`

**V1 Engine JSON configs (Engine input):**
- Produced by converter, consumed by engine
- Sample converted files: `tests/talend_xml_samples/converted_jsons/*.json`

**Data files (Engine processes):**
- Delimited (CSV, TSV, custom delimiter)
- Positional/fixed-width
- Excel (.xls via xlrd, .xlsx via openpyxl)
- JSON
- XML (via stdlib xml.etree and lxml)
- Raw text
- Properties files (key=value)
- Archives (ZIP, GZIP)
- SWIFT financial messages (custom YAML-configured transformer)

---

*Integration audit: 2026-04-14*
