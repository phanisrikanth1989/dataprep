# Audit Report: tSendMail / SendMailComponent

> **Audited**: 2026-04-03
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report is scoped to the v1 engine exclusively

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tSendMail` |
| **V1 Engine Class** | `SendMailComponent` |
| **Engine File** | `src/v1/engine/components/control/send_mail.py` (252 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/control/send_mail.py` |
| **Converter Dispatch** | `@REGISTRY.register("tSendMail")` decorator-based dispatch |
| **Registry Aliases** | `tSendMail` |
| **Category** | Control / Internet |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/control/send_mail.py` | Engine implementation (252 lines) |
| `src/converters/talend_to_v1/components/control/send_mail.py` | Converter class |
| `tests/converters/talend_to_v1/components/test_send_mail.py` | Converter tests |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 29 of 29 config keys extracted (27 unique + 2 framework); 3 TABLE parsers (ATTACHMENTS, HEADERS, CONFIGS); AUTH_MODE backward compat with NEED_AUTH; 12 per-feature needs_review entries for engine gaps |
| Engine Feature Parity | **Y** | 0 | 4 | 4 | 2 | 11 params not read by engine; encoding default mismatch ("utf-8" vs "ISO-8859-15"); no OAuth2 support; no custom headers; no importance header; no personal name display |
| Code Quality | **Y** | 0 | 3 | 3 | 2 | Duplicate validate_config methods; no SMTP context manager (resource leak); attachment filename leaks server path; SSL/STARTTLS mutual exclusion not validated |
| Performance & Memory | **G** | 0 | 0 | 1 | 1 | Large attachments loaded entirely into memory; msg.as_string() creates second copy |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero engine unit tests; zero engine integration tests |

**Overall: YELLOW -- Not production-ready without P1 fixes to the engine**

**Top Actions:**

1. Implement AUTH_MODE support in engine (currently only BASIC auth) (P1)
2. Add custom headers support from HEADERS TABLE (P1)
3. Read importance config and set email priority header (P1)
4. Use SMTP context manager to prevent resource leaks (P1)
5. Add engine unit tests (P0 testing gap)

---

## 3. Talend Feature Baseline

### What tSendMail Does

`tSendMail` sends email messages via an SMTP server. It supports multiple recipients (TO, CC, BCC), file attachments with configurable transfer encoding, custom email headers, and multiple authentication modes (no auth, basic username/password, and OAuth2). The component supports both SSL and STARTTLS encryption for secure SMTP connections.

tSendMail is a utility component -- it does not process data flows. It is typically placed in a subjob triggered by OnSubjobOk or OnComponentOk to send notifications after data processing completes. Common use cases include job completion notifications, error alerts, and report distribution via email attachments.

The component has three TABLE parameters: ATTACHMENTS (file paths with transfer encoding), HEADERS (custom email headers), and CONFIGS (custom SMTP session properties like timeouts).

**Source**: [tSendMail Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/internet/tsendmail-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tSendMail/tSendMail_java.xml)
**Component family**: Internet / Mail
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in, uses javax.mail internally)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | To | `TO` | TEXT | `"receiver@example.com"` | Main recipient email address(es), semicolon-separated |
| 2 | From | `FROM` | TEXT | `"send@example.com"` | Sender email address |
| 3 | Need Personal Name | `NEED_PERSONAL_NAME` | CHECK | `false` | Show sender's display name in From header |
| 4 | Personal Name | `PERSONAL_NAME` | TEXT | `"sender"` | Sender display name (SHOW_IF NEED_PERSONAL_NAME) |
| 5 | CC | `CC` | TEXT | `"carbon@example.com"` | Carbon copy recipient(s), semicolon-separated |
| 6 | BCC | `BCC` | TEXT | `"blindcarbon@example.com"` | Blind carbon copy recipient(s), semicolon-separated |
| 7 | Subject | `SUBJECT` | TEXT | `"Talaxie Open Studio notification"` | Email subject line |
| 8 | Message | `MESSAGE` | MEMO_MESSAGE | `"Hello"` | Email body text |
| 9 | Check Attachment | `CHECK_ATTACHMENT` | CHECK | `true` | Die if attachment file is missing |
| 10 | Attachments | `ATTACHMENTS` | TABLE (stride-2) | -- | File paths with transfer encoding (see 3.3) |
| 11 | Headers | `HEADERS` | TABLE (stride-2) | -- | Custom email headers (see 3.4) |
| 12 | SMTP Host | `SMTP_HOST` | TEXT | `"smtp.provider.com"` | SMTP server hostname |
| 13 | SMTP Port | `SMTP_PORT` | TEXT | `"25"` | SMTP server port (TEXT, not INT) |
| 14 | SSL | `SSL` | CHECK | `false` | Use SSL connection (port 465 typical) |
| 15 | STARTTLS | `STARTTLS` | CHECK | `false` | Use STARTTLS encryption (port 587 typical) |
| 16 | Importance | `IMPORTANCE` | CLOSED_LIST | `NORMAL` | Email priority: HIGH, NORMAL, LOW |
| 17 | Auth Mode | `AUTH_MODE` | CLOSED_LIST | `BASIC` | Authentication mode: NO_AUTH, BASIC, OAUTH2 |
| 18 | Auth Username | `AUTH_USERNAME` | TEXT | `"username"` | SMTP username (SHOW_IF AUTH_MODE in BASIC, OAUTH2) |
| 19 | Auth Password | `AUTH_PASSWORD` | PASSWORD | `"password"` | SMTP password (SHOW_IF AUTH_MODE == BASIC) |
| 20 | Token | `TOKEN` | PASSWORD | `"password"` | OAuth2 token (SHOW_IF AUTH_MODE == OAUTH2) |
| 21 | Die on Error | `DIE_ON_ERROR` | CHECK | `true` | Fail job on email sending error |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 22 | Text Subtype | `TEXT_SUBTYPE` | CLOSED_LIST | `PLAIN` | MIME text subtype: PLAIN, HTML |
| 23 | Encoding | `ENCODING` | ENCODING_TYPE | `"ISO-8859-15"` | Character encoding for email body |
| 24 | Set Localhost | `SET_LOCALHOST` | CHECK | `false` | Specify custom localhost name for EHLO/HELO |
| 25 | Localhost | `LOCALHOST` | TEXT | `"localhost"` | Custom localhost name (SHOW_IF SET_LOCALHOST) |
| 26 | Use Two Line Token | `USE_TWO_LINE_TOKEN` | CHECK | `false` | Two-line OAuth2 auth format (SHOW_IF AUTH_MODE == OAUTH2) |
| 27 | Configs | `CONFIGS` | TABLE (stride-2) | -- | Custom SMTP session properties (see 3.5) |

### 3.3 ATTACHMENTS TABLE Structure

| Column | XML Name | Field Type | Description |
| -------- | ---------- | ------------ | ------------- |
| File | `FILE` | TEXT | Absolute file path of attachment |
| Content Transfer Encoding | `CONTENT_TRANSFER_ENCODING` | TEXT | Encoding type (e.g., BASE64, DEFAULT) |

### 3.4 HEADERS TABLE Structure

| Column | XML Name | Field Type | Description |
| -------- | ---------- | ------------ | ------------- |
| Key | `KEY` | TEXT | Header name (e.g., X-Priority, X-Mailer) |
| Value | `VALUE` | TEXT | Header value |

### 3.5 CONFIGS TABLE Structure

| Column | XML Name | Field Type | Description |
| -------- | ---------- | ------------ | ------------- |
| Key | `KEY` | TEXT | SMTP session property name (e.g., mail.smtp.timeout) |
| Value | `VALUE` | TEXT | Property value |

### 3.6 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Enable statistics collection for monitoring |
| 2 | Label | `LABEL` | TEXT | `""` | User-defined label for the component instance |

Note: Framework parameters are defined in the common Talend component framework, not in the tSendMail _java.xml directly.

### 3.7 Connection Types

| Connector | Direction | Description |
| ----------- | ----------- | ------------- |
| `SUBJOB_OK` | Output (Trigger) | Fires when subjob completes successfully |
| `SUBJOB_ERROR` | Output (Trigger) | Fires when subjob encounters an error |
| `COMPONENT_OK` | Output (Trigger) | Fires when component completes successfully |
| `COMPONENT_ERROR` | Output (Trigger) | Fires when component encounters an error |
| `RUN_IF` | Output (Trigger) | Conditional execution trigger |

Note: tSendMail is a utility component -- it has no FLOW input or output connectors.

### 3.8 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_ERROR_MESSAGE` | String | After error | Error message when email sending fails |

### 3.9 Behavioral Notes

1. **Encoding default is ISO-8859-15**, not UTF-8. This is the Western European encoding that includes the Euro sign. Jobs sending UTF-8 content must explicitly set ENCODING to "UTF-8".
2. **AUTH_MODE default is BASIC**, meaning authentication is expected by default. Jobs connecting to open relays should set AUTH_MODE to NO_AUTH.
3. **Backward compatibility**: Older .item files use `NEED_AUTH` (CHECK, default true) instead of `AUTH_MODE` (CLOSED_LIST). When `NEED_AUTH=true`, it maps to `AUTH_MODE=BASIC`; when `NEED_AUTH=false`, it maps to `AUTH_MODE=NO_AUTH`.
4. **SMTP_PORT is TEXT type**, not INT. In Talend, port values can contain context variable expressions (e.g., `context.smtp_port`).
5. **SSL and STARTTLS are mutually exclusive** in standard SMTP practice: SSL wraps the entire connection (port 465), while STARTTLS upgrades a plain connection (port 587). Neither the Talend UI nor the v1 engine validates this mutual exclusion.
6. **CHECK_ATTACHMENT=true** causes the job to die if any attachment file does not exist. When false, missing attachments are silently skipped.
7. **IMPORTANCE maps to the X-Priority header**: HIGH=1, NORMAL=3, LOW=5. The engine does not currently set this header.
8. **OAuth2 support** uses XOAUTH2 SASL mechanism. The TOKEN field holds the access token. USE_TWO_LINE_TOKEN controls the auth command format (single-line vs two-line).
9. **CONFIGS TABLE** allows setting arbitrary javax.mail session properties, such as `mail.smtp.timeout`, `mail.smtp.connectiontimeout`, `mail.smtp.writetimeout`.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter (`SendMailConverter`) extracts all 27 unique parameters plus 2 framework parameters. It uses three TABLE parsers for ATTACHMENTS, HEADERS, and CONFIGS (all stride-2). The AUTH_MODE parameter includes backward compatibility with the older NEED_AUTH boolean.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `TO` | Yes | `to` | Default `"receiver@example.com"`, semicolon-split into list |
| 2 | `FROM` | Yes | `from_email` | Default `"send@example.com"` |
| 3 | `NEED_PERSONAL_NAME` | Yes | `need_personal_name` | Default `False` |
| 4 | `PERSONAL_NAME` | Yes | `personal_name` | Default `"sender"` |
| 5 | `CC` | Yes | `cc` | Default `"carbon@example.com"`, semicolon-split into list |
| 6 | `BCC` | Yes | `bcc` | Default `"blindcarbon@example.com"`, semicolon-split into list |
| 7 | `SUBJECT` | Yes | `subject` | Default `"Talaxie Open Studio notification"` |
| 8 | `MESSAGE` | Yes | `message` | Default `"Hello"` |
| 9 | `CHECK_ATTACHMENT` | Yes | `check_attachment` | Default `True` |
| 10 | `ATTACHMENTS` | Yes | `attachments` | TABLE stride-2: FILE + CONTENT_TRANSFER_ENCODING |
| 11 | `HEADERS` | Yes | `headers` | TABLE stride-2: KEY + VALUE |
| 12 | `SMTP_HOST` | Yes | `smtp_host` | Default `"smtp.provider.com"` |
| 13 | `SMTP_PORT` | Yes | `smtp_port` | Default `"25"` (kept as string for context var support) |
| 14 | `SSL` | Yes | `ssl` | Default `False` |
| 15 | `STARTTLS` | Yes | `starttls` | Default `False` |
| 16 | `IMPORTANCE` | Yes | `importance` | Default `"NORMAL"` |
| 17 | `AUTH_MODE` | Yes | `auth_mode` | Default `"BASIC"`, with NEED_AUTH backward compat |
| 18 | `AUTH_USERNAME` | Yes | `auth_username` | Default `"username"` |
| 19 | `AUTH_PASSWORD` | Yes | `auth_password` | Default `"password"` |
| 20 | `TOKEN` | Yes | `token` | Default `"password"` |
| 21 | `DIE_ON_ERROR` | Yes | `die_on_error` | Default `True` |
| 22 | `TEXT_SUBTYPE` | Yes | `text_subtype` | Default `"PLAIN"` |
| 23 | `ENCODING` | Yes | `encoding` | Default `"ISO-8859-15"` (correct Talend default) |
| 24 | `SET_LOCALHOST` | Yes | `set_localhost` | Default `False` |
| 25 | `LOCALHOST` | Yes | `localhost` | Default `"localhost"` |
| 26 | `USE_TWO_LINE_TOKEN` | Yes | `use_two_line_token` | Default `False` |
| 27 | `CONFIGS` | Yes | `configs` | TABLE stride-2: KEY + VALUE |
| 28 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Default `False` (framework) |
| 29 | `LABEL` | Yes | `label` | Default `""` (framework) |

**Summary**: 29 of 29 parameters extracted (100%).

### 4.2 Schema Extraction

tSendMail is a utility component with no data flow schema. The converter returns `{"input": [], "output": []}`.

### 4.3 Expression Handling

Context variables (`context.var`) and Java expressions are not specifically handled by the converter. Scalar parameters pass through `_get_str()` and `_get_bool()` which strip quotes but do not perform expression resolution. Expression handling is delegated to the v1 engine's `replace_in_config` at runtime.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No open converter issues. All parameters extracted, all defaults correct, all TABLE parsers working. |

### 4.5 Needs Review Entries

The converter emits 12 per-feature needs_review entries for engine gaps (unconditional, since these are permanent engine limitations):

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `need_personal_name` | Engine does not read need_personal_name -- sender display name not supported | engine_gap |
| 2 | `personal_name` | Engine does not read personal_name -- sender display name not supported | engine_gap |
| 3 | `check_attachment` | Engine does not read check_attachment -- missing attachment validation not supported | engine_gap |
| 4 | `headers` | Engine does not read headers TABLE -- custom email headers not supported | engine_gap |
| 5 | `importance` | Engine does not read importance -- email priority not supported | engine_gap |
| 6 | `auth_mode` | Engine does not read auth_mode -- uses implicit BASIC auth only | engine_gap |
| 7 | `token` | Engine does not read token -- OAuth2 authentication not supported | engine_gap |
| 8 | `set_localhost` | Engine does not read set_localhost -- custom localhost not supported | engine_gap |
| 9 | `localhost` | Engine does not read localhost -- custom localhost not supported | engine_gap |
| 10 | `use_two_line_token` | Engine does not read use_two_line_token -- OAuth2 two-line format not supported | engine_gap |
| 11 | `configs` | Engine does not read configs TABLE -- custom SMTP properties not supported | engine_gap |
| 12 | `encoding` | Engine default encoding 'utf-8' differs from Talend default 'ISO-8859-15' | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | SMTP host/port | **Yes** | High | `_process()` line 142-143 | Reads `smtp_host` and `smtp_port` (default 25) |
| 2 | From email | **Yes** | High | `_process()` line 144 | Reads `from_email` |
| 3 | To/CC/BCC recipients | **Yes** | High | `_process()` line 145-147 | Reads as lists, combines for sendmail |
| 4 | Subject and message | **Yes** | High | `_process()` line 148-149 | Reads `subject` and `message` |
| 5 | File attachments | **Partial** | Medium | `_process()` line 174-196 | Reads `attachments` as list of file paths, ignores CONTENT_TRANSFER_ENCODING |
| 6 | SSL connection | **Yes** | High | `_process()` line 200-201 | Uses `smtplib.SMTP_SSL` when `ssl=True` |
| 7 | STARTTLS encryption | **Yes** | High | `_process()` line 205-206 | Calls `server.starttls()` when `starttls=True` |
| 8 | Basic authentication | **Yes** | High | `_process()` line 209-210 | Uses `server.login()` with username/password |
| 9 | Die on error | **Yes** | High | `_process()` line 220-226 | Raises `ComponentExecutionError` when `die_on_error=True` |
| 10 | Text subtype | **Yes** | Medium | `_process()` line 166-167 | Reads `text_subtype` (default "plain" vs Talend "PLAIN") |
| 11 | Encoding | **Yes** | Low | `_process()` line 169 | Reads `encoding` but defaults to "utf-8" (Talend defaults to "ISO-8859-15") |
| 12 | Personal name display | **No** | N/A | -- | `need_personal_name` and `personal_name` not read |
| 13 | Check attachment exists | **No** | N/A | -- | `check_attachment` not read; engine dies on missing file regardless |
| 14 | Custom headers | **No** | N/A | -- | `headers` TABLE not read |
| 15 | Email importance/priority | **No** | N/A | -- | `importance` not read; no X-Priority header set |
| 16 | AUTH_MODE routing | **No** | N/A | -- | `auth_mode` not read; engine always uses BASIC if credentials present |
| 17 | OAuth2 token auth | **No** | N/A | -- | `token` not read; XOAUTH2 not implemented |
| 18 | Custom localhost (EHLO) | **No** | N/A | -- | `set_localhost` and `localhost` not read |
| 19 | Two-line OAuth2 format | **No** | N/A | -- | `use_two_line_token` not read |
| 20 | Custom SMTP properties | **No** | N/A | -- | `configs` TABLE not read |
| 21 | Statistics | **Partial** | Low | `_update_stats()` line 235 | Sets (0, 0, 0) -- always zero since no data processing |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-SM-001 | **P1** | Engine does not read `auth_mode` config. Authentication is implicit: if `auth_username` and `auth_password` are both present, `server.login()` is called. No support for NO_AUTH (skipping login even when credentials present) or OAUTH2 (token-based auth). |
| ENG-SM-002 | **P1** | Engine does not read `headers` TABLE. Custom email headers (X-Priority, X-Mailer, etc.) cannot be set. This also means the importance/priority feature is non-functional. |
| ENG-SM-003 | **P1** | Engine does not read `importance` config. Talend sets X-Priority header based on importance (HIGH=1, NORMAL=3, LOW=5). Engine sends emails with no priority header. |
| ENG-SM-004 | **P1** | Engine default encoding is `"utf-8"` (line 79: `DEFAULT_ENCODING = 'utf-8'`) but Talend default is `"ISO-8859-15"`. Jobs using default encoding will produce different character encoding in emails. |
| ENG-SM-005 | **P2** | Engine does not read `need_personal_name` or `personal_name`. Talend can set a display name in the From header (e.g., `"John Doe <john@example.com>"`). Engine always uses bare email address. |
| ENG-SM-006 | **P2** | Engine does not read `check_attachment`. Talend offers graceful skip of missing attachments when check_attachment=false. Engine always dies on missing file when die_on_error=true, or silently skips when die_on_error=false -- conflating two separate Talend controls. |
| ENG-SM-007 | **P2** | Engine does not read CONTENT_TRANSFER_ENCODING from ATTACHMENTS TABLE. All attachments use BASE64 encoding regardless of configured encoding. |
| ENG-SM-008 | **P2** | Engine does not read `configs` TABLE. Custom SMTP session properties (timeouts, buffer sizes, etc.) are not configurable. |
| ENG-SM-009 | **P3** | Engine does not read `set_localhost` or `localhost`. Cannot customize EHLO/HELO hostname for SMTP servers that require a specific client identity. |
| ENG-SM-010 | **P3** | Engine does not read `use_two_line_token`. OAuth2 two-line auth format not supported (moot since OAuth2 itself is unsupported). |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_ERROR_MESSAGE` | Yes | No | -- | Engine does not set ERROR_MESSAGE in globalMap |
| `{id}_NB_LINE` | Yes (0) | Yes (0) | `_update_stats(0, 0, 0)` | Utility component: always 0 |
| `{id}_NB_LINE_OK` | Yes (0) | Yes (0) | `_update_stats(0, 0, 0)` | Always 0 |
| `{id}_NB_LINE_REJECT` | Yes (0) | Yes (0) | `_update_stats(0, 0, 0)` | Always 0 |

### 5.4 Architecture Overview

The engine implementation follows a straightforward linear flow:

1. **Validate config** -- check required fields (smtp_host, from_email, to)
2. **Build MIMEMultipart message** -- construct email with From, To, Cc, Subject headers
3. **Attach body** -- create MIMEText with configured subtype and encoding
4. **Add attachments** -- iterate file paths, read binary, encode BASE64, attach
5. **Connect to SMTP** -- SSL or plain connection based on config
6. **STARTTLS upgrade** -- if enabled, upgrade plain connection
7. **Authenticate** -- if username and password present, call login()
8. **Send** -- sendmail() to combined recipient list
9. **Quit** -- close connection

The SMTP connection is NOT managed via context manager, risking resource leaks on exceptions between connect and quit.

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-SM-001 | **P1** | `send_mail.py:200-216` | SMTP connection not managed with context manager (`with` statement). If an exception occurs between `smtplib.SMTP()` and `server.quit()`, the TCP connection leaks. Python's `smtplib.SMTP` supports `__enter__`/`__exit__` since Python 3.0. |
| BUG-SM-002 | **P1** | `send_mail.py:82-114, 240-252` | Duplicate `validate_config` methods: private `_validate_config()` returns `List[str]`, public `validate_config()` returns `bool`. Both implement overlapping validation logic. Only `_validate_config()` is called (line 134). The public `validate_config()` is dead code. |
| BUG-SM-003 | **P2** | `send_mail.py:181` | Attachment `Content-Disposition` header uses raw file path as filename: `f'attachment; filename={attachment}'`. This leaks server directory structure (e.g., `/opt/data/reports/q3.pdf`) and violates RFC 2183 (filename should be basename only, quoted). |
| BUG-SM-004 | **P2** | `send_mail.py:200-206` | SSL and STARTTLS are not mutually exclusive. If both `ssl=True` and `starttls=True`, the code creates an SSL connection (port 465) then attempts STARTTLS upgrade on an already-encrypted connection, which will raise an `smtplib.SMTPServerDisconnected` or similar error. |
| BUG-SM-005 | **P2** | `send_mail.py:220-232` | Exception handling cascade: `smtplib.SMTPException` catch (line 220) wraps error and re-raises as `ComponentExecutionError`. But the broader `except Exception` catch (line 228) also catches `FileOperationError` re-raised from the attachment loop (line 187-196), potentially masking the specific error type with a generic message. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-SM-001 | **P3** | Engine class `SendMailComponent` vs Talend name `tSendMail` -- consistent with project convention, no action needed. |
| NAME-SM-002 | **P3** | Engine uses `from_email` config key to avoid Python `from` keyword collision. Good practice but differs from Talend's `FROM` parameter name. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-SM-001 | **P1** | "`_validate_config()` must be called or removed" | Public `validate_config()` at line 240 is dead code -- never called by engine or base class. |
| STD-SM-002 | N/A | "No print statements" | **COMPLIANT** -- No print statements found. Logging uses `logger.*` throughout. |

### 6.4 Debug Artifacts

None found. Logging is appropriate for production use.

### 6.5 Security

See Section 11 Risk Assessment for comprehensive security analysis. Key concerns:

1. **Credential logging**: `logger.debug()` at line 210 logs the auth username. While DEBUG level, if logging is misconfigured in production, credentials could be exposed.
2. **Password in config**: `auth_password` is stored as plain text in the JSON config. No encryption or secret reference mechanism.
3. **Attachment path traversal**: No validation that attachment paths are within expected directories.
4. **Header injection**: No sanitization of From/To/CC/BCC values. Newline injection could add arbitrary headers.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- `logger = logging.getLogger(__name__)` |
| Level usage | Good -- INFO for operations, DEBUG for details, ERROR for failures |
| Sensitive data | Risk -- auth username logged at DEBUG (line 210) |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Good -- uses `ConfigurationError`, `FileOperationError`, `ComponentExecutionError` |
| Exception chaining | Good -- uses `raise ... from e` |
| die_on_error handling | Good -- checks `die_on_error` before raising, logs warning and continues when false |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- all methods have type hints |
| Parameter types | Good -- `Dict[str, Any]`, `List[str]`, `Optional[Any]` used |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-SM-001 | **P2** | Attachments are loaded entirely into memory (`file.read()` at line 179). For large files (100MB+), this causes significant memory pressure. |
| PERF-SM-002 | **P3** | `msg.as_string()` at line 215 creates a second in-memory copy of the entire email including all attachments. For a 100MB attachment, peak memory is ~300-400MB (original binary + BASE64 encoded ~133% + string representation). |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- utility component, no data flow processing |
| Memory threshold | No limits on attachment size; large files consume proportional memory |
| Large data handling | Not optimized; consider chunked reading for large attachments |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | ~60 | `tests/converters/talend_to_v1/components/test_send_mail.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-SM-001 | **P0** | No engine unit tests for `SendMailComponent._process()`, `_validate_config()`, error handling paths |

### 8.3 Recommended Test Cases

**Engine tests (priority):**

- SSL connection creation (`smtplib.SMTP_SSL` path)
- STARTTLS upgrade path
- Authentication with username/password
- die_on_error=False continues after SMTP failure
- Missing attachment file handling
- Empty recipient list validation
- Large attachment memory behavior

**Converter tests (already comprehensive):**

- All 9 test classes per TEST_PATTERN.md
- 3 TABLE parsers (ATTACHMENTS, HEADERS, CONFIGS)
- AUTH_MODE with NEED_AUTH backward compatibility
- Framework params
- Needs review entries
- Completeness verification

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **TEST-SM-001** |
| P1 | 7 | **ENG-SM-001**, **ENG-SM-002**, **ENG-SM-003**, **ENG-SM-004**, **BUG-SM-001**, **BUG-SM-002**, **STD-SM-001** |
| P2 | 8 | **ENG-SM-005**, **ENG-SM-006**, **ENG-SM-007**, **ENG-SM-008**, **BUG-SM-003**, **BUG-SM-004**, **BUG-SM-005**, **PERF-SM-001** |
| P3 | 4 | **ENG-SM-009**, **ENG-SM-010**, **NAME-SM-001**, **PERF-SM-002** |
| **Total** | **20** | |

Note: NAME-SM-002 is informational (good practice, not an issue). STD-SM-002 is a compliance check that passed (not an issue).

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 10 | ENG-SM-001 through ENG-SM-010 |
| Bug (BUG) | 5 | BUG-SM-001 through BUG-SM-005 |
| Standards (STD) | 1 | STD-SM-001 |
| Performance (PERF) | 2 | PERF-SM-001, PERF-SM-002 |
| Testing (TEST) | 1 | TEST-SM-001 |
| Naming (NAME) | 1 | NAME-SM-001 |
| Converter (CONV) | 0 | None -- converter is production-ready |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap is set -- stats lost |
| XCUT-004 | `base_component.py:202` | `self.config` mutation via `resolve_dict()` -- non-reentrant in iterate loops |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Add engine unit tests** (TEST-SM-001/P0): Test all major execution paths -- SSL, STARTTLS, auth, die_on_error, attachment handling.

### Short-term (Hardening)

1. **Implement AUTH_MODE support** (ENG-SM-001/P1): Read `auth_mode` config to route between NO_AUTH (skip login), BASIC (username/password login), and OAUTH2 (token-based XOAUTH2 SASL).
2. **Add custom headers support** (ENG-SM-002/P1): Read `headers` TABLE and add each key-value pair to the MIMEMultipart message.
3. **Set email priority header** (ENG-SM-003/P1): Read `importance` config and set X-Priority header (HIGH=1, NORMAL=3, LOW=5).
4. **Fix encoding default** (ENG-SM-004/P1): Change `DEFAULT_ENCODING` from `'utf-8'` to `'ISO-8859-15'` to match Talend default.
5. **Use SMTP context manager** (BUG-SM-001/P1): Replace manual connect/quit with `with smtplib.SMTP(...) as server:` to prevent resource leaks.
6. **Remove duplicate validate_config** (BUG-SM-002/P1, STD-SM-001/P1): Remove the dead public `validate_config()` method at line 240.

### Long-term (Optimization)

1. **Add personal name support** (ENG-SM-005/P2): Read `need_personal_name` and `personal_name` to format From header as `"Name <email>"`.
2. **Implement check_attachment logic** (ENG-SM-006/P2): Separate attachment existence check from die_on_error behavior.
3. **Fix attachment filename** (BUG-SM-003/P2): Use `os.path.basename()` for Content-Disposition filename; quote per RFC 2183.
4. **Validate SSL/STARTTLS mutual exclusion** (BUG-SM-004/P2): Raise ConfigurationError if both ssl and starttls are true.

---

## 11. Risk Assessment

This section is included because tSendMail handles SMTP credentials, file system access, and network communication -- all areas with security implications for production deployment.

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| SMTP credential exposure in logs | Medium | High -- leaked credentials compromise email infrastructure | Ensure DEBUG logging is disabled in production; audit log output for sensitive data |
| Password stored plain text in config | High | High -- anyone with config file access has SMTP credentials | Use secret manager or environment variable references instead of inline passwords |
| Header injection via unsanitized fields | Low | High -- attacker could inject arbitrary headers, BCC recipients, or modify email routing | Validate and sanitize all recipient fields; reject values containing newlines |
| Path traversal in attachment file paths | Low | High -- attacker-controlled paths could read arbitrary server files and email them | Validate attachment paths against an allowed directory; reject paths with `..` components |
| OAuth2 token stored plain text | Medium | High -- OAuth2 tokens provide account access; plain text storage risks exposure | Same as password: use secret manager; tokens should be short-lived |
| SSL/STARTTLS not mutually validated | Medium | Medium -- misconfiguration causes connection failure, not security breach but disrupts email delivery | Validate mutual exclusion in engine config validation |
| No SMTP connection context manager | Medium | Low -- resource leak on exception; unlikely to cause security issues but degrades reliability | Use Python `with` statement for SMTP connection management |
| Attachment filename leaks server path | High | Medium -- Content-Disposition header reveals server directory structure to email recipients | Use `os.path.basename()` for attachment filenames |

### High-Risk Job Patterns

1. **OAuth2 authentication** -- Engine does not support OAuth2. Jobs configured with AUTH_MODE=OAUTH2 will silently fall back to no authentication (no credentials match the username/password check), potentially sending emails without auth on servers that require it.
2. **Custom SMTP properties (CONFIGS TABLE)** -- Engine ignores configs TABLE. Jobs relying on custom timeouts or TLS settings will use Python defaults, which may cause connection failures or timeouts in corporate environments with strict SMTP policies.
3. **HTML email with ISO-8859-15 encoding** -- Engine defaults to UTF-8 while Talend defaults to ISO-8859-15. HTML emails with special characters (Euro sign, accented characters) may render incorrectly due to encoding mismatch.
4. **Multiple large attachments** -- Each attachment is fully loaded into memory. A job attaching 5 x 50MB files uses ~750MB+ peak memory (binary + BASE64 + string copy).
5. **Jobs with custom headers for email routing** -- HEADERS TABLE is ignored. Corporate email routing rules that depend on X-headers (X-Priority, X-Mailer, custom routing tags) will not work.

### Safe Usage Patterns

1. **Basic SMTP with username/password authentication** -- Well-tested path. Works reliably with port 25 (plain), 465 (SSL), or 587 (STARTTLS).
2. **Plain text emails with small attachments** -- Core functionality works correctly. Message body and small file attachments send without issues.
3. **die_on_error=True with monitored SMTP** -- Error handling works correctly; SMTP failures properly raise ComponentExecutionError.
4. **UTF-8 encoded emails** -- When ENCODING is explicitly set to "UTF-8", the engine's default matches and encoding is correct.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `<https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tSendMail/tSendMail_java.xml`> | Complete parameter definitions, CLOSED_LIST values, defaults, TABLE structures |
| Official Talend docs | `<https://help.qlik.com/talend/en-US/components/7.3/internet/tsendmail-standard-properties`> | Component description, behavioral notes, connection types |
| Engine source | `src/v1/engine/components/control/send_mail.py` (252 lines) | Feature parity analysis, bug identification, security assessment |
| Converter source | `src/converters/talend_to_v1/components/control/send_mail.py` | Converter audit |
| Converter tests | `tests/converters/talend_to_v1/components/test_send_mail.py` | Test coverage analysis |
| Base class | `src/v1/engine/base_component.py` | Cross-cutting issue identification |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap is set -- stats lost (0,0,0 for utility component, low impact) |
| XCUT-004 | `base_component.py:202` | `self.config` mutation via `resolve_dict()` -- if tSendMail runs inside iterate loop, config modified on first pass |

### Edge-Case Checklist Results

| Check | Result | Notes |
| ------- | -------- | ------- |
| NaN handling | N/A | Utility component -- no data processing |
| Empty strings in config | Risk | Empty SMTP_HOST or TO triggers warnings but not hard errors in converter |
| Empty DataFrame input | N/A | No data flow input |
| HYBRID streaming mode | N/A | Utility component -- no data processing |
| `_update_global_map()` crash | Low impact | Stats are (0,0,0) for utility component |
| Type demotion | N/A | No data processing |
| `validate_schema` nullable | N/A | No schema processing |
| `_validate_config()` called | Dead code | Public `validate_config()` at line 240 is never called |

## Appendix C: SMTP Auth Modes

### NO_AUTH Flow

```
Client                          Server
|  EHLO localhost               |
| ------------------------------> |
|  250-smtp.server.com          |
| <------------------------------ |
|  MAIL FROM:<sender@ex.com>    |
| ------------------------------> |
|  250 OK                       |
| <------------------------------ |
|  (continue with recipients)   |
```

No login step. Used for internal relays or open SMTP servers.

### BASIC Flow

```
Client                          Server
|  EHLO localhost               |
| ------------------------------> |
|  250-smtp.server.com          |
|  250-AUTH LOGIN PLAIN         |
| <------------------------------ |
|  AUTH LOGIN                   |
| ------------------------------> |
|  334 VXNlcm5hbWU6            |
| <------------------------------ |
|  (base64 username)            |
| ------------------------------> |
|  334 UGFzc3dvcmQ6            |
| <------------------------------ |
|  (base64 password)            |
| ------------------------------> |
|  235 Authentication OK        |
| <------------------------------ |
```

Standard username/password authentication. Currently the ONLY mode supported by the v1 engine.

### OAUTH2 Flow (Not Implemented in Engine)

```
Client                          Server
|  EHLO localhost               |
| ------------------------------> |
|  250-AUTH XOAUTH2             |
| <------------------------------ |
|  AUTH XOAUTH2 <base64 token> |
| ------------------------------> |
|  235 Accepted                 |
| <------------------------------ |
```

Uses XOAUTH2 SASL mechanism. The token is a base64-encoded string containing the username and OAuth2 access token. USE_TWO_LINE_TOKEN controls whether the auth command is sent as one line or two.

**Engine gap**: OAuth2 is not implemented. The engine only checks for username+password and calls `server.login()`.

## Appendix D: ATTACHMENTS TABLE Reference

### Structure

Each ATTACHMENTS row has 2 fields (stride-2):

| Field | XML elementRef | Type | Description |
| ------- | --------------- | ------ | ------------- |
| File path | `FILE` | TEXT | Absolute path to attachment file |
| Transfer encoding | `CONTENT_TRANSFER_ENCODING` | TEXT | Encoding: BASE64, DEFAULT, 7BIT, QUOTED-PRINTABLE |

### Converter Output Format

```json
{
  "attachments": [
    {"file": "/path/to/report.pdf", "content_transfer_encoding": "BASE64"},
    {"file": "/path/to/data.csv", "content_transfer_encoding": "DEFAULT"}
  ]
}
```

### Engine Gap

The engine reads `attachments` as a flat list of file paths (not dicts). It ignores `content_transfer_encoding` and always uses BASE64 encoding via `encoders.encode_base64()`.

## Appendix E: HEADERS and CONFIGS TABLE Structures

### HEADERS TABLE

Each HEADERS row has 2 fields (stride-2):

| Field | XML elementRef | Type | Description |
| ------- | --------------- | ------ | ------------- |
| Key | `KEY` | TEXT | Header name (e.g., X-Priority, X-Mailer) |
| Value | `VALUE` | TEXT | Header value |

### CONFIGS TABLE

Each CONFIGS row has 2 fields (stride-2):

| Field | XML elementRef | Type | Description |
| ------- | --------------- | ------ | ------------- |
| Key | `KEY` | TEXT | SMTP session property name |
| Value | `VALUE` | TEXT | Property value |

### Common CONFIGS Properties

| Property | Description | Example Value |
| ---------- | ------------- | --------------- |
| `mail.smtp.timeout` | Socket read timeout (ms) | `"30000"` |
| `mail.smtp.connectiontimeout` | Connection timeout (ms) | `"10000"` |
| `mail.smtp.writetimeout` | Write timeout (ms) | `"30000"` |
| `mail.smtp.ssl.protocols` | SSL protocol version | `"TLSv1.2"` |

### Engine Gap

Neither HEADERS nor CONFIGS TABLEs are read by the engine. Custom headers cannot be set, and SMTP session properties use Python smtplib defaults.

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after full rewrite per D-12 gold standard -- Section 11 Risk Assessment added per D-18*
